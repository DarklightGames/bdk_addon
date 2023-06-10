import math
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
            if paint_layer.terrain_layer_id == self.id:
                paint_layer.terrain_layer_name = self.name

    # Update deco layer names if the linked terrain layer matches.
    # TODO: this will need to change when we add the terrain node system.
    for deco_layer in self.terrain_info_object.bdk.terrain_info.deco_layers:
        if deco_layer.linked_layer_id == self.id:
            deco_layer.linked_layer_name = self.name


terrain_layer_node_type_icons = {
    'GROUP': 'FILE_FOLDER',
    'PAINT': 'BRUSH_DATA',
    'NOISE': 'MOD_NOISE',
    'TERRAIN_LAYER': 'MATERIAL',
    'CONSTANT': 'IMAGE_ALPHA',
    'NORMAL': 'DRIVER_ROTATIONAL_DIFFERENCE',
    'MAP_RANGE': 'FCURVE',
}

terrain_layer_node_type_items = (
    ('GROUP', 'Group', 'Group', terrain_layer_node_type_icons['GROUP'], 0),
    ('PAINT', 'Paint', 'Paint', terrain_layer_node_type_icons['PAINT'], 1),
    ('NOISE', 'Noise', 'Noise', terrain_layer_node_type_icons['NOISE'], 2),
    ('TERRAIN_LAYER', 'Terrain Layer', 'Terrain Layer', terrain_layer_node_type_icons['TERRAIN_LAYER'], 3),
    ('CONSTANT', 'Constant', 'Constant', terrain_layer_node_type_icons['CONSTANT'], 4),
    ('NORMAL', 'Normal', 'Value will be equal to the dot product of the vertex normal and the up vector', terrain_layer_node_type_icons['NORMAL'], 5),
    ('MAP_RANGE', 'Map Range', 'Values will be mapped to the specified range window', terrain_layer_node_type_icons['MAP_RANGE'], 6),
)


def terrain_layer_node_terrain_layer_name_search_cb(self: 'BDK_PG_terrain_layer_node', context: Context,
                                                    edit_text: str) -> List[str]:
    return [terrain_layer.name for terrain_layer in self.terrain_info_object.bdk.terrain_info.terrain_layers]


def terrain_layer_node_terrain_layer_name_update_cb(self: 'BDK_PG_terrain_layer_node', context: Context):
    terrain_layers = self.terrain_info_object.bdk.terrain_info.terrain_layers
    if self.layer_name in terrain_layers:
        self.layer_id = terrain_layers[self.layer_name].id
    else:
        self.layer_id = ''

    # Rebuild the deco node setup.
    build_deco_layers(self.terrain_info_object)


class BDK_PG_terrain_layer_node(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    name: StringProperty(name='Name', default='Node')
    type: EnumProperty(name='Type', items=terrain_layer_node_type_items, default='PAINT')
    operation: EnumProperty(name='Operation', items=[
        ('ADD', 'Add', 'Add'),
        ('SUBTRACT', 'Subtract', 'Subtract'),
        ('MULTIPLY', 'Multiply', 'Multiply'),
        ('MAXIMUM', 'Maximum', 'Maximum'),
        ('MINIMUM', 'Minimum', 'Minimum')
    ], default='ADD')
    factor: FloatProperty(name='Factor', default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    mute: BoolProperty(name='Mute', default=False)
    # Blur (currently not exposed due to performance concerns)
    blur: BoolProperty(name='Blur', default=False)
    blur_iterations: IntProperty(name='Blur Iterations', default=1, min=1, max=10)
    # Layer
    layer_name: StringProperty(name='Layer Name', options={'HIDDEN'},
                               search=terrain_layer_node_terrain_layer_name_search_cb,
                               update=terrain_layer_node_terrain_layer_name_update_cb)
    layer_id: StringProperty(name='Layer ID', options={'HIDDEN'})
    # Map Range
    map_range_from_min: FloatProperty(name='From Min', default=0.0, min=0, max=1.0, subtype='FACTOR')
    map_range_from_max: FloatProperty(name='From Max', default=1.0, min=0, max=1.0, subtype='FACTOR')
    # Normal
    normal_angle_min: FloatProperty(name='Angle Min', default=math.radians(5.0), min=0, max=math.pi / 2, subtype='ANGLE', options=set())
    normal_angle_max: FloatProperty(name='Angle Max', default=math.radians(10.0), min=0, max=math.pi / 2, subtype='ANGLE', options=set())


# Add the children property to the node property group (this must be done after the class is defined).
BDK_PG_terrain_layer_node.__annotations__["children"] = CollectionProperty(name='Children',
                                                                           type=BDK_PG_terrain_layer_node,
                                                                           options={'HIDDEN'})


def terrain_layer_texel_density_get(self: 'BDK_PG_terrain_layer') -> float:
    terrain_info: 'BDK_PG_terrain_info' = get_terrain_info(self.terrain_info_object)
    x = self.material.get('UClamp', 0) if self.material else 0
    y = self.material.get('VClamp', 0) if self.material else 0
    pixels_per_quad = ((x / self.u_scale) * (y / self.v_scale))
    quad_area = pow(terrain_info.terrain_scale, 2)
    return pixels_per_quad / quad_area


class BDK_PG_terrain_layer(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='TerrainLayer', update=terrain_layer_name_update_cb)
    u_scale: FloatProperty(name='UScale', default=2.0, options=set())
    v_scale: FloatProperty(name='VScale', default=2.0, options=set())
    texture_rotation: FloatProperty(name='TextureRotation', subtype='ANGLE', options=set())
    material: PointerProperty(name='Material', type=Material, update=on_material_update, poll=material_poll)
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    is_visible: BoolProperty(options={'HIDDEN'}, default=True)
    nodes: CollectionProperty(name='Nodes', type=BDK_PG_terrain_layer_node, options={'HIDDEN'})
    texel_density: FloatProperty(name='Texel Density', get=terrain_layer_texel_density_get, description='The texel density of the layer measured in pixels per unit squared  (px/u²)',
                                 options={'HIDDEN', 'SKIP_SAVE'})


# def on_deco_layer_index_update(self: 'BDK_PG_terrain_info', _: Context):
#     if not self.terrain_info_object or self.terrain_info_object.type != 'MESH':
#         return
#     mesh_data: Mesh = self.terrain_info_object.data
#     deco_layer: BDK_PG_terrain_deco_layer = self.deco_layers[self.deco_layers_index]
#     color_attribute_index = -1
#
#     for i, color_attribute in enumerate(mesh_data.color_attributes):
#         if color_attribute.name == deco_layer.id:
#             color_attribute_index = i
#             break
#
#     if color_attribute_index == -1:
#         print(f"Could not find color attribute for deco layer '{deco_layer.name}'")
#         return
#     elif mesh_data.color_attributes.active_color_index != color_attribute_index:
#         mesh_data.color_attributes.active_color_index = color_attribute_index
#         # Push an undo state.
#         # This is needed so that if the user selects a new layer, does some operation, and then does an undo,
#         # it won't wipe out the active painting layer.
#         # TODO: replace this with an actual operator with an UNDO_GROUPED option flag so that we consolidate repeated changes into one undo step instead of polluting the undo stack.
#         bpy.ops.ed.undo_push(message=f"Select '{deco_layer.name}' DecoLayer")


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
            self.linked_layer_id = layer.id
            break
    # Trigger an update of the deco layers.
    # TODO: Have the density map attribute ID in the geometry node be driven by a property.
    build_deco_layers(context.active_object)

    # Push an undo state.
    bpy.ops.ed.undo_push(message='Update Linked Layer')


empty_set = set()


def deco_layer_name_update_cb(self, context):
    # Find all terrain objects in the file.
    terrain_object_objects: List[Object] = list(filter(lambda o: o.bdk.type == 'TERRAIN_OBJECT', bpy.data.objects))

    # TODO: add handling for nodes system, once implemented
    # Update terrain object paint component names if the terrain layer's color attribute name matches.
    for terrain_object_object in terrain_object_objects:
        for paint_layer in terrain_object_object.bdk.terrain_object.paint_layers:
            if paint_layer.deco_layer_id == self.id:
                paint_layer.deco_layer_name = self.name


def terrain_deco_layer_nodes_index_update_cb(self: 'BDK_PG_terrain_deco_layer', _: Context):
    if not self.terrain_info_object or self.terrain_info_object.type != 'MESH':
        return
    mesh_data: Mesh = self.terrain_info_object.data
    color_attribute_index = -1
    node: 'BDK_PG_terrain_layer_node' = self.nodes[self.nodes_index]
    if node.type != 'PAINT':
        return
    for i, color_attribute in enumerate(mesh_data.color_attributes):
        if color_attribute.name == node.id:
            color_attribute_index = i
            break
    if mesh_data.color_attributes.active_color_index != color_attribute_index:
        mesh_data.color_attributes.active_color_index = color_attribute_index
        # Push an undo state.
        # This is needed so that if the user selects a new layer, does some operation, and then does an undo,
        # it won't wipe out the active painting layer.
        bpy.ops.ed.undo_push(message=f"Select '{self.name}' Node Paint Layer")


class BDK_PG_terrain_deco_layer(PropertyGroup):
    id: StringProperty(options={'HIDDEN'}, name='ID')
    name: StringProperty(name='Name', default='DecoLayer', options=empty_set, update=deco_layer_name_update_cb)
    align_to_terrain: BoolProperty(name='Align To Terrain', default=False, options=empty_set,
                                   description='Aligned the deco to the terrain surface')
    density_multiplier_max: FloatProperty(name='Density Multiplier Max', min=0.0, max=1.0, default=0.1, options=empty_set, description='The density will be multiplied by a random value between the min and max density multipliers')
    density_multiplier_min: FloatProperty(name='Density Multiplier Min', min=0.0, max=1.0, default=0.1, options=empty_set, description='The density will be multiplied by a random value between the min and max density multipliers')
    detail_mode: EnumProperty(name='Detail Mode', items=[
        ('DM_Low', 'Low', '',),
        ('DM_High', 'High', ''),
        ('DM_SuperHigh', 'Super High', ''),
    ], options=empty_set, description='The minimum detail mode the client must be in for this deco to be '
                                      'drawn.\n\n'
                                      'Note that this has no visible effect within the BDK')
    fadeout_radius_max: FloatProperty(name='Fadeout Radius Max', options=empty_set, subtype='DISTANCE')
    fadeout_radius_min: FloatProperty(name='Fadeout Radius Min', options=empty_set, subtype='DISTANCE')
    force_draw: BoolProperty(name='Force Draw', default=False, options=empty_set,
                             description='Forces the deco to be drawn regardless of the client\'s graphics settings\n\nNote that this has no visible effect within the BDK')
    max_per_quad: IntProperty(name='Max Per Quad', default=1, min=1, max=4, options=empty_set,
                              description='The maximum number of instances of this deco that can be placed on a single quad')
    object: PointerProperty(type=Object, options={'HIDDEN'})
    offset: FloatProperty(name='Offset', options=empty_set, subtype='DISTANCE', default=0.0,
                          description='The distance offset from the terrain')
    random_yaw: BoolProperty(name='Random Yaw',
                             default=True,
                             options=empty_set,
                             description='Randomize the yaw of the object.\n\n'
                                         'It is not recommended to enable this when Align To Terrain is enabled since '
                                         'there is a bug in Unreal Engine that causes the deco to be rotated '
                                         'incorrectly when on slopes')
    scale_multiplier_max: FloatVectorProperty(name='Scale Multiplier Max', min=0.0, max=1.0, default=[1, 1, 1],
                                              options=empty_set, subtype='XYZ')
    scale_multiplier_min: FloatVectorProperty(name='Scale Multiplier Min', min=0.0, max=1.0, default=[1, 1, 1],
                                              options=empty_set, subtype='XYZ')
    seed: IntProperty(name='Seed', options=empty_set, description='The seed used for randomization')
    show_on_invisible_terrain: BoolProperty(name='Show On Invisible Terrain', default=False, options=empty_set,
                                            description='Show the deco on invisible terrain quads')
    show_on_terrain: BoolProperty(name='Show On Terrain', default=True, options=empty_set)
    draw_order: EnumProperty(name='Sort Order', options=empty_set, items=[
        ('SORT_NoSort', 'No Sort', ''),
        ('SORT_BackToFront', 'Back To Front', ''),
        ('SORT_FrontToBack', 'Front To Back', ''),
    ], description='The sorting order for the decos on the this layer\n\n'
                   'Note that this has no visible effect within the BDK')
    static_mesh: PointerProperty(name='Static Mesh', type=Object, update=on_static_mesh_update, poll=static_mesh_poll,
                                 options=empty_set)
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    linked_layer_id: StringProperty(options={'HIDDEN'})
    nodes: CollectionProperty(type=BDK_PG_terrain_layer_node, options=empty_set)
    nodes_index: IntProperty(options=empty_set, update=terrain_deco_layer_nodes_index_update_cb)


# TODO: replace this with
def on_terrain_layer_index_update(self: 'BDK_PG_terrain_info', _: Context):
    if not self.terrain_info_object or self.terrain_info_object.type != 'MESH':
        return
    mesh_data: Mesh = self.terrain_info_object.data
    terrain_layer: BDK_PG_terrain_layer = self.terrain_layers[self.terrain_layers_index]
    color_attribute_index = -1
    for i, color_attribute in enumerate(mesh_data.color_attributes):
        if color_attribute.name == terrain_layer.id:
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
    terrain_scale: FloatProperty(name='TerrainScale', options={'HIDDEN'}, subtype='DISTANCE')
    terrain_layers: CollectionProperty(name='TerrainLayers', type=BDK_PG_terrain_layer)
    terrain_layers_index: IntProperty(options={'HIDDEN'}, update=on_terrain_layer_index_update)
    deco_layers: CollectionProperty(name='DecoLayers', type=BDK_PG_terrain_deco_layer)
    deco_layers_index: IntProperty(options={'HIDDEN'})
    x_size: IntProperty(name='X Size', options={'HIDDEN'})
    y_size: IntProperty(name='Y Size', options={'HIDDEN'})


classes = (
    BDK_PG_terrain_layer_node,
    BDK_PG_terrain_deco_layer,
    BDK_PG_terrain_layer,
    BDK_PG_terrain_info,
)
