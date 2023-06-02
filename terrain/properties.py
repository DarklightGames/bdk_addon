from typing import cast, List

import bpy.ops
from bpy.types import PropertyGroup, Object, Context, Mesh, Material
from bpy.props import PointerProperty, BoolProperty, FloatProperty, CollectionProperty, IntProperty, StringProperty, \
    FloatVectorProperty, EnumProperty

from .deco import build_deco_layers
from ..helpers import is_bdk_material, is_bdk_static_mesh_actor, get_terrain_info
from .builder import build_terrain_material


def on_material_update(self, _: Context):
    build_terrain_material(self.terrain_info_object)


def material_poll(_: Context, material: Material) -> bool:
    return is_bdk_material(material)


def terrain_layer_name_update_cb(self, context: Context):
    # Find all terrain objects in the file.
    terrain_object_objects: List[Object] = list(filter(lambda o: o.bdk.type == 'TERRAIN_OBJECT', bpy.data.objects))

    # Update terrain object paint component names if the terrain layer's color attribute name matches.
    for terrain_object_object in terrain_object_objects:
        for paint_layer in terrain_object_object.bdk.terrain_object.paint_layers:
            if paint_layer.terrain_layer_id == self.color_attribute_name:
                paint_layer.terrain_layer_name = self.name

    # Update deco layer names if the linked terrain layer matches.
    # TODO: this will need to change when we add the terrain node system.
    for deco_layer in self.terrain_info_object.bdk.terrain_info.deco_layers:
        if deco_layer.linked_layer_id == self.color_attribute_name:
            deco_layer.linked_layer_name = self.name


# what is another name for layer? component?
class BDK_PG_terrain_layer_node(PropertyGroup):
    name: StringProperty(name='Name', default='Paint')
    type: EnumProperty(name='Type', items=[
        ('PAINT', 'Paint', 'Paint'),
        ('NOISE', 'Noise', 'Noise'),
        ('FILL', 'Fill', 'Fill'),
    ], default='PAINT')
    operation: EnumProperty(name='Operation', items=[
        ('ADD', 'Add', 'Add'),
        ('SUBTRACT', 'Subtract', 'Subtract'),
        ('MULTIPLY', 'Multiply', 'Multiply'),
        ('DIVIDE', 'Divide', 'Divide'),
    ], default='ADD')
    attribute_name: StringProperty(name='Attribute Name', options={'HIDDEN'})


# Add the children property to the node property group (this must be done after the class is defined).
BDK_PG_terrain_layer_node.__annotations__["children"] = CollectionProperty(name='Children',
                                                                           type=BDK_PG_terrain_layer_node,
                                                                           options={'HIDDEN'})


class BDK_PG_terrain_layer(PropertyGroup):
    color_attribute_name: StringProperty(options={'HIDDEN'})    # TOD: this will be the responsibility of the nodes now (rename this to ID to convey uniqueness)
    name: StringProperty(name='Name', default='TerrainLayer', update=terrain_layer_name_update_cb)
    u_scale: FloatProperty(name='UScale', default=2.0)
    v_scale: FloatProperty(name='VScale', default=2.0)
    texture_rotation: FloatProperty(name='TextureRotation', subtype='ANGLE')
    material: PointerProperty(name='Material', type=Material, update=on_material_update, poll=material_poll)
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    is_visible: BoolProperty(options={'HIDDEN'}, default=True)
    nodes: CollectionProperty(name='Nodes', type=BDK_PG_terrain_layer_node, options={'HIDDEN'})


def on_deco_layer_index_update(self: 'BDK_PG_terrain_info', _: Context):
    if not self.terrain_info_object or self.terrain_info_object.type != 'MESH':
        return
    mesh_data: Mesh = self.terrain_info_object.data
    deco_layer: BDK_PG_terrain_deco_layer = self.deco_layers[self.deco_layers_index]
    color_attribute_index = -1

    for i, color_attribute in enumerate(mesh_data.color_attributes):
        if color_attribute.name == deco_layer.id:
            color_attribute_index = i
            break

    if color_attribute_index == -1:
        print(f"Could not find color attribute for deco layer '{deco_layer.name}'")
        return
    elif mesh_data.color_attributes.active_color_index != color_attribute_index:
        mesh_data.color_attributes.active_color_index = color_attribute_index
        # Push an undo state.
        # This is needed so that if the user selects a new layer, does some operation, and then does an undo,
        # it won't wipe out the active painting layer.
        # TODO: replace this with an actual operator with an UNDO_GROUPED option flag so that we consolidate repeated changes into one undo step instead of polluting the undo stack.
        bpy.ops.ed.undo_push(message=f"Select '{deco_layer.name}' DecoLayer")


def on_static_mesh_update(self: 'BDK_PG_terrain_deco_layer', context: Context):
    if self.object is None:
        return
    deco_layer_object = cast(Object, self.object)
    node_group = deco_layer_object.modifiers[self.id].node_group
    # TODO: this is brittle but will work for now
    object_info_node = node_group.nodes['Object Info.001']
    object_info_node.inputs[0].default_value = self.static_mesh


def static_mesh_poll(_: Context, obj: Object) -> bool:
    return is_bdk_static_mesh_actor(obj)


def deco_layer_linked_layer_name_search(self: 'BDK_PG_terrain_deco_layer', context: Context, edit_text: str) -> List[
    str]:
    # Get a list of terrain layer names for the selected terrain info object.
    terrain_info = get_terrain_info(context.active_object)
    if terrain_info is None:
        return []
    return [layer.name for layer in terrain_info.terrain_layers]


def deco_layer_is_linked_to_layer_update(self: 'BDK_PG_terrain_deco_layer', context: Context):
    build_deco_layers(context.active_object)

    # Push an undo state.
    bpy.ops.ed.undo_push(message='Update Linked Layer')


def deco_layer_linked_layer_name_update(self: 'BDK_PG_terrain_deco_layer', context: Context):
    # Try to find a terrain layer with the same name as the selected linked layer name.
    terrain_info = get_terrain_info(context.active_object)
    if terrain_info is None:
        return
    self.linked_layer_id = ''
    for i, layer in enumerate(terrain_info.terrain_layers):
        if layer.name == self.linked_layer_name:
            self.linked_layer_id = layer.color_attribute_name  # TODO: Fix the naming of this to be more consistent.
            break
    # Trigger an update of the deco layers.
    # TODO: Have the density map attribute ID in the geometry node be driven by a property.
    build_deco_layers(context.active_object)

    # Push an undo state.
    bpy.ops.ed.undo_push(message='Update Linked Layer')


empty_set = set()


def deco_layer_name_update_cb(self, context):
    print('deco_layer_name_update_cb')

    # Find all terrain objects in the file.
    terrain_object_objects: List[Object] = list(filter(lambda o: o.bdk.type == 'TERRAIN_OBJECT', bpy.data.objects))

    # Update terrain object paint component names if the terrain layer's color attribute name matches.
    for terrain_object_object in terrain_object_objects:
        for paint_layer in terrain_object_object.bdk.terrain_object.paint_layers:
            if paint_layer.deco_layer_id == self.id:
                paint_layer.deco_layer_name = self.name

    # TODO: add additional handling for nodes system, once implemented


class BDK_PG_terrain_deco_layer(PropertyGroup):
    id: StringProperty(options={'HIDDEN'})
    name: StringProperty(name='Name', default='DecoLayer', options=empty_set, update=deco_layer_name_update_cb)
    align_to_terrain: BoolProperty(name='Align To Terrain', default=False, options=empty_set)
    density_multiplier_max: FloatProperty('Density Multiplier Max', min=0.0, max=1.0, default=0.1, options=empty_set)
    density_multiplier_min: FloatProperty('Density Multiplier Min', min=0.0, max=1.0, default=0.1, options=empty_set)
    detail_mode: EnumProperty(name='Detail Mode', items=[
        ('DM_Low', 'Low', '',),
        ('DM_High', 'High', ''),
        ('DM_SuperHigh', 'Super High', ''),
    ], options=empty_set)
    fadeout_radius_max: FloatProperty(name='Fadeout Radius Max', options=empty_set, subtype='DISTANCE')
    fadeout_radius_min: FloatProperty(name='Fadeout Radius Min', options=empty_set, subtype='DISTANCE')
    force_draw: BoolProperty(name='Force Draw', default=False, options=empty_set)
    max_per_quad: IntProperty(name='Max Per Quad', default=1, min=1, max=4, options=empty_set)
    object: PointerProperty(type=Object, options={'HIDDEN'})
    offset: FloatProperty(name='Offset', options=empty_set, subtype='DISTANCE')
    random_yaw: BoolProperty(name='Random Yaw', default=True, options=empty_set)
    scale_multiplier_max: FloatVectorProperty('Scale Multiplier Max', min=0.0, max=1.0, default=[1, 1, 1],
                                              options=empty_set, subtype='XYZ')
    scale_multiplier_min: FloatVectorProperty('Scale Multiplier Min', min=0.0, max=1.0, default=[1, 1, 1],
                                              options=empty_set, subtype='XYZ')
    seed: IntProperty(name='Seed', options=empty_set)
    show_on_invisible_terrain: BoolProperty(name='Show On Invisible Terrain', default=False, options=empty_set)
    show_on_terrain: BoolProperty(name='Show On Terrain', default=True, options=empty_set)
    draw_order: EnumProperty(name='Sort Order', options=empty_set, items=[
        ('SORT_NoSort', 'No Sort', ''),
        ('SORT_BackToFront', 'Back To Front', ''),
        ('SORT_FrontToBack', 'Front To Back', ''),
    ])
    static_mesh: PointerProperty(name='Static Mesh', type=Object, update=on_static_mesh_update, poll=static_mesh_poll,
                                 options=empty_set)
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    is_linked_to_layer: BoolProperty(options={'HIDDEN'}, default=False, update=deco_layer_is_linked_to_layer_update,
                                     name='Linked To Layer',
                                     description='Use the alpha map of the selected terrain layer as the density map')
    linked_layer_name: StringProperty(options={'HIDDEN'}, update=deco_layer_linked_layer_name_update,
                                      search=deco_layer_linked_layer_name_search, name='Linked Layer')
    linked_layer_id: StringProperty(options={'HIDDEN'})

    def get_density_color_attribute_id(self) -> str:
        if self.is_linked_to_layer:
            return self.linked_layer_id
        return self.id


def on_terrain_layer_index_update(self: 'BDK_PG_terrain_info', _: Context):
    if not self.terrain_info_object or self.terrain_info_object.type != 'MESH':
        return
    mesh_data: Mesh = self.terrain_info_object.data
    terrain_layer: BDK_PG_terrain_layer = self.terrain_layers[self.terrain_layers_index]
    color_attribute_index = -1
    for i, color_attribute in enumerate(mesh_data.color_attributes):
        if color_attribute.name == terrain_layer.color_attribute_name:
            color_attribute_index = i
            break
    if mesh_data.color_attributes.active_color_index != color_attribute_index:
        mesh_data.color_attributes.active_color_index = color_attribute_index
        # Push an undo state.
        # This is needed so that if the user selects a new layer, does some operation, and then does an undo,
        # it won't wipe out the active painting layer.
        bpy.ops.ed.undo_push(message=f"Select '{terrain_layer.name}' Layer")


class BDK_PG_terrain_info(PropertyGroup):
    terrain_info_object: PointerProperty(type=Object)
    terrain_scale: FloatProperty(name='TerrainScale')
    terrain_layers: CollectionProperty(name='TerrainLayers', type=BDK_PG_terrain_layer)
    terrain_layers_index: IntProperty(options={'HIDDEN'}, update=on_terrain_layer_index_update)
    deco_layers: CollectionProperty(name='DecoLayers', type=BDK_PG_terrain_deco_layer)
    deco_layers_index: IntProperty(options={'HIDDEN'}, update=on_deco_layer_index_update)
    x_size: IntProperty(options={'HIDDEN'})
    y_size: IntProperty(options={'HIDDEN'})


classes = (
    BDK_PG_terrain_layer_node,
    BDK_PG_terrain_deco_layer,
    BDK_PG_terrain_layer,
    BDK_PG_terrain_info,
)
