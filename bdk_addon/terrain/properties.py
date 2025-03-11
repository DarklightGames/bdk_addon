import math
from typing import cast, List, Optional

import bpy.ops
from bpy.types import PropertyGroup, Object, Context, Mesh, Material
from bpy.props import PointerProperty, BoolProperty, FloatProperty, CollectionProperty, IntProperty, StringProperty, \
    FloatVectorProperty, EnumProperty

from .kernel import ensure_deco_layers
from ..helpers import is_bdk_material, is_bdk_static_mesh_actor, get_terrain_info
from .builder import build_terrain_material


def on_material_update(self, _: Context):
    build_terrain_material(self.terrain_info_object)


def material_poll(_: Context, material: Material) -> bool:
    return is_bdk_material(material)


def terrain_paint_layer_name_update_cb(self, context: Context):
    # Find all terrain doodad in the file.
    terrain_doodad_objects: List[Object] = list(filter(lambda o: o.bdk.type == 'TERRAIN_DOODAD', bpy.data.objects))

    # Update terrain doodad paint layer names if the terrain layer's color attribute name matches.
    for terrain_doodad_object in terrain_doodad_objects:
        for paint_layer in terrain_doodad_object.bdk.terrain_doodad.paint_layers:
            if paint_layer.paint_layer_id == self.id:
                paint_layer.paint_layer_name = self.name

    # Update the name of the paint layer in terrain info nodes.
    for paint_layer in self.terrain_info_object.bdk.terrain_info.paint_layers:
        for node in paint_layer.nodes:
            if node.paint_layer_id == self.id:
                node.paint_layer_name = self.name

    for deco_layer in self.terrain_info_object.bdk.terrain_info.deco_layers:
        for node in deco_layer.nodes:
            if node.paint_layer_id == self.id:
                node.paint_layer_name = self.name


node_type_icons = {
    'GROUP': 'FILE_FOLDER',
    'PAINT': 'BRUSH_DATA',
    'NOISE': 'MOD_NOISE',
    'PAINT_LAYER': 'TEXTURE',
    'CONSTANT': 'IMAGE_ALPHA',
    'NORMAL': 'DRIVER_ROTATIONAL_DIFFERENCE',
    'PLANE_DISTANCE': 'GRADIENT',
    'FIELD': 'IMAGE_ALPHA',
}

node_type_items = (
    ('GROUP', 'Group', 'Group', node_type_icons['GROUP'], 0),
    ('PAINT', 'Paint', 'Paint', node_type_icons['PAINT'], 1),
    ('NOISE', 'Noise', 'Noise', node_type_icons['NOISE'], 2),
    ('PAINT_LAYER', 'Paint Layer', 'Paint Layer', node_type_icons['PAINT_LAYER'], 3),
    ('CONSTANT', 'Constant', 'Constant', node_type_icons['CONSTANT'], 4),
    ('NORMAL', 'Normal', 'Value will be equal to the dot product of the vertex normal and the up vector',
     node_type_icons['NORMAL'], 5),
    ('PLANE_DISTANCE', 'Plane Distance', 'Plane Distance', node_type_icons['PLANE_DISTANCE'], 6),
    ('FIELD', 'Field', 'A straight float field', node_type_icons['FIELD'], 7),
)

node_type_item_names = {item[0]: item[1] for item in node_type_items}

empty_set = set()


def terrain_layer_node_terrain_paint_layer_name_search_cb(self: 'BDK_PG_terrain_layer_node', context: Context,
                                                          edit_text: str) -> List[str]:
    return [paint_layer.name for paint_layer in self.terrain_info_object.bdk.terrain_info.paint_layers]


def terrain_layer_node_terrain_paint_layer_name_update_cb(self: 'BDK_PG_terrain_layer_node', context: Context):
    paint_layers = self.terrain_info_object.bdk.terrain_info.paint_layers
    if self.paint_layer_name in paint_layers:
        self.paint_layer_id = paint_layers[self.paint_layer_name].id
    else:
        self.paint_layer_id = ''

    # Rebuild the deco node setup.
    ensure_deco_layers(self.terrain_info_object)


class BDK_PG_terrain_layer_node(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    name: StringProperty(name='Name', default='Node')
    type: EnumProperty(name='Type', items=node_type_items, default='PAINT')
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
    paint_layer_name: StringProperty(name='Paint Layer', options={'HIDDEN'},
                                     search=terrain_layer_node_terrain_paint_layer_name_search_cb,
                                     update=terrain_layer_node_terrain_paint_layer_name_update_cb)
    paint_layer_id: StringProperty(name='Paint Layer ID', options={'HIDDEN'})

    # Normal
    normal_angle_min: FloatProperty(name='Angle Min', default=math.radians(5.0), min=0, max=math.pi / 2, subtype='ANGLE', options=empty_set)
    normal_angle_max: FloatProperty(name='Angle Max', default=math.radians(10.0), min=0, max=math.pi / 2, subtype='ANGLE', options=empty_set)

    # Map Range
    use_map_range: BoolProperty(name='Map Range', default=False, options=empty_set)
    map_range_from_min: FloatProperty(name='From Min', default=0.0, min=0, max=1.0, subtype='FACTOR', options=empty_set)
    map_range_from_max: FloatProperty(name='From Max', default=1.0, min=0, max=1.0, subtype='FACTOR', options=empty_set)

    # Noise
    noise_type: EnumProperty(name='Noise Type', items=(
        ('WHITE', 'White', 'White Noise', 0),
        ('PERLIN', 'Perlin', 'Perlin Noise')
    ))
    noise_perlin_scale: FloatProperty(name='Perlin Noise Scale', default=5.0, options=empty_set)
    noise_perlin_detail: FloatProperty(name='Perlin Noise Detail', default=2.0, options=empty_set)
    noise_perlin_roughness: FloatProperty(name='Perlin Noise Roughness', default=0.5, min=0.0, max=1.0, options=empty_set)
    noise_perlin_lacunarity: FloatProperty(name='Perlin Noise Lacunarity', default=2.0, options=empty_set)
    noise_perlin_distortion: FloatProperty(name='Perlin Noise Distortion', default=0.0, options=empty_set)


# Add the children property to the node property group (this must be done after the class is defined).
# This is because the parent/child relationship is a circular reference.
BDK_PG_terrain_layer_node.__annotations__["parent"] = PointerProperty(name='Parent', type=BDK_PG_terrain_layer_node,
                                                                       options={'HIDDEN'})
BDK_PG_terrain_layer_node.__annotations__["children"] = CollectionProperty(name='Children',
                                                                           type=BDK_PG_terrain_layer_node,
                                                                           options={'HIDDEN'})


def terrain_paint_layer_texel_density_get(self: 'BDK_PG_terrain_paint_layer') -> float:
    terrain_info: 'BDK_PG_terrain_info' = get_terrain_info(self.terrain_info_object)
    x = self.material.bdk.size_x if self.material else 0
    y = self.material.bdk.size_y if self.material else 0
    pixels_per_quad = ((x / self.u_scale) * (y / self.v_scale))
    quad_area = pow(terrain_info.terrain_scale, 2)
    return abs(pixels_per_quad / quad_area)


def terrain_paint_layer_texel_density_set(self, texel_density: float):
    """
    Calculate the U & V scale based on the target texel density.
    :param self:
    :param texel_density:
    :return:
    """
    terrain_info: 'BDK_PG_terrain_info' = get_terrain_info(self.terrain_info_object)
    x = self.material.bdk.size_x if self.material else 0
    y = self.material.bdk.size_y if self.material else 0
    quad_area = pow(terrain_info.terrain_scale, 2)
    scale = math.sqrt((x * y) / (texel_density * quad_area))
    self.u_scale = scale
    self.v_scale = scale


def terrain_paint_layer_nodes_index_update_cb(self: 'BDK_PG_terrain_paint_layer', context: Context):
    node = self.nodes[self.nodes_index]
    if node.type == 'PAINT':
        pass
    node: 'BDK_PG_terrain_layer_node' = self.nodes[self.nodes_index]
    set_active_color_index_for_terrain_layer_node(node, self.terrain_info_object)


class BDK_PG_terrain_paint_layer(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Paint Layer', update=terrain_paint_layer_name_update_cb)
    u_scale: FloatProperty(name='UScale', default=2.0, options=empty_set)
    v_scale: FloatProperty(name='VScale', default=2.0, options=empty_set)
    texture_rotation: FloatProperty(name='TextureRotation', subtype='ANGLE', options=empty_set)
    material: PointerProperty(name='Material', type=Material, update=on_material_update, poll=material_poll)
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    is_visible: BoolProperty(options={'HIDDEN'}, default=True)
    nodes: CollectionProperty(name='Nodes', type=BDK_PG_terrain_layer_node, options={'HIDDEN'})
    nodes_index: IntProperty(name='Nodes Index', options={'HIDDEN'}, update=terrain_paint_layer_nodes_index_update_cb)
    texel_density: FloatProperty(name='Texel Density', get=terrain_paint_layer_texel_density_get,
                                 set=terrain_paint_layer_texel_density_set,
                                 description='The texel density of the layer measured in pixels per unit squared  ('
                                             'px/u²)',
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
    return [layer.name for layer in terrain_info.paint_layers]


def deco_layer_is_linked_to_layer_update(self: 'BDK_PG_terrain_deco_layer', context: Context):
    ensure_deco_layers(context.active_object)

    # Push an undo state.
    bpy.ops.ed.undo_push(message='Update Linked Layer')


def deco_layer_linked_layer_name_update(self: 'BDK_PG_terrain_deco_layer', context: Context):
    # Try to find a terrain layer with the same name as the selected linked layer name.
    terrain_info = get_terrain_info(context.active_object)
    if terrain_info is None:
        return
    self.linked_layer_id = ''
    for i, layer in enumerate(terrain_info.paint_layers):
        if layer.name == self.linked_layer_id:
            self.linked_layer_id = layer.id
            break
    # Trigger an update of the deco layers.
    ensure_deco_layers(context.active_object)

    # Push an undo state.
    bpy.ops.ed.undo_push(message='Update Linked Layer')


empty_set = set()


def deco_layer_name_update_cb(self, context):
    # Find all terrain doodad in the file.
    terrain_doodad_objects: List[Object] = list(filter(lambda o: o.bdk.type == 'TERRAIN_DOODAD', bpy.data.objects))

    # TODO: add handling for nodes system, once implemented
    # Update terrain doodad paint layer names if the terrain layer's color attribute name matches.
    for terrain_doodad_object in terrain_doodad_objects:
        for paint_layer in terrain_doodad_object.bdk.terrain_doodad.paint_layers:
            if paint_layer.deco_layer_id == self.id:
                paint_layer.deco_layer_name = self.name


def set_active_color_index_for_terrain_layer_node(node: 'BDK_PG_terrain_layer_node', terrain_info_object: Object):
    if node.type != 'PAINT':
        return
    active_vertex_group_index = -1
    for i, vertex_group in enumerate(terrain_info_object.vertex_groups):
        if vertex_group.name == node.id:
            active_vertex_group_index = i
            break
    if terrain_info_object.vertex_groups.active_index != active_vertex_group_index:
        terrain_info_object.vertex_groups.active_index = active_vertex_group_index
        # Push an undo state.
        # This is needed so that if the user selects a new layer, does some operation, and then does an undo,
        # it won't wipe out the active painting layer.
        bpy.ops.ed.undo_push(message=f"Select '{node.name}' Node Paint Layer")


def terrain_deco_layer_nodes_index_update_cb(self: 'BDK_PG_terrain_deco_layer', _: Context):
    if not self.terrain_info_object or self.nodes_index < 0:
        return
    node: 'BDK_PG_terrain_layer_node' = self.nodes[self.nodes_index]
    set_active_color_index_for_terrain_layer_node(node, self.terrain_info_object)


class BDK_PG_terrain_deco_layer(PropertyGroup):
    id: StringProperty(options={'HIDDEN'}, name='ID')
    modifier_name: StringProperty(options={'HIDDEN'}, description='The name of the modifier that this deco layer is associated with')
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
                             description='Forces the deco to be drawn regardless of the client\'s graphics settings. Enable this when the decos provide the player with concealment.\n\nNote that this has no visible effect within the BDK')
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
    nodes_dfs: CollectionProperty(type=BDK_PG_terrain_layer_node, options={'HIDDEN'})


# TODO: this shouldn't be necessary anymore
def on_terrain_info_paint_layers_index_update(self: 'BDK_PG_terrain_info', _: Context):
    if not self.terrain_info_object or self.terrain_info_object.type != 'MESH':
        return
    mesh_data: Mesh = self.terrain_info_object.data
    paint_layer: BDK_PG_terrain_paint_layer = self.paint_layers[self.paint_layers_index] if self.paint_layers_index >= 0 else None
    color_attribute_index = -1
    for i, color_attribute in enumerate(mesh_data.color_attributes):
        if color_attribute.name == paint_layer.id:
            color_attribute_index = i
            break
    if mesh_data.color_attributes.active_color_index != color_attribute_index:
        mesh_data.color_attributes.active_color_index = color_attribute_index
        # Push an undo state.
        # This is needed so that if the user selects a new layer, does some operation, and then does an undo,
        # it won't wipe out the active painting layer.
        bpy.ops.ed.undo_push(message=f"Select '{paint_layer.name}' Layer")


def terrain_info_max_elevation_get(self: 'BDK_PG_terrain_info') -> float:
    return self.terrain_scale_z * 256 * 2

def terrain_info_heightmap_resolution_get(self: 'BDK_PG_terrain_info') -> float:
    # TODO: should be based on the scene units, not arbitrary values.
    return self.max_elevation / 65536.0

class BDK_PG_terrain_info(PropertyGroup):
    terrain_info_object: PointerProperty(type=Object)
    terrain_scale: FloatProperty(name='Terrain Scale', options={'HIDDEN'}, subtype='DISTANCE')
    terrain_scale_z: FloatProperty(name='Heightmap Scale', options={'HIDDEN'}, default=64.0, min=0, soft_min=16.0, soft_max=128.0, max=512)
    max_elevation: FloatProperty(name='Max Elevation Range', options={'HIDDEN'}, subtype='DISTANCE', get=terrain_info_max_elevation_get,
                                 description='The maximum elevation range of the terrain given the heightmap scale.')
    heightmap_resolution: FloatProperty(name='Heightmap Resolution', options={'HIDDEN'}, subtype='DISTANCE', get=terrain_info_heightmap_resolution_get,
                                        description='The z-resolution of the heightmap when exported to a heightmap image. Lower values are better')
    paint_layers: CollectionProperty(name='Paint Layers', type=BDK_PG_terrain_paint_layer)
    paint_layers_index: IntProperty(options={'HIDDEN'}, update=on_terrain_info_paint_layers_index_update)
    deco_layers: CollectionProperty(name='Deco Layers', type=BDK_PG_terrain_deco_layer)
    deco_layers_index: IntProperty(options={'HIDDEN'})
    deco_layer_offset: FloatProperty(name='Deco Layer Offset', options={'HIDDEN'}, subtype='DISTANCE', description='Global z-offset for all deco layers')
    x_size: IntProperty(name='X Size', options={'HIDDEN'})
    y_size: IntProperty(name='Y Size', options={'HIDDEN'})
    deco_layer_offset: FloatProperty(name='Deco Layer Offset', options={'HIDDEN'}, subtype='DISTANCE')

    # Modifier IDs for the terrain doodad passes. (why not just have a pointer to the modifier?)
    doodad_sculpt_modifier_name: StringProperty(options={'HIDDEN'}, name='Sculpt Modifier Name')
    doodad_attribute_modifier_name: StringProperty(options={'HIDDEN'}, name='Attribute Modifier Name')
    doodad_paint_modifier_name: StringProperty(options={'HIDDEN'}, name='Paint Modifier Name')
    doodad_deco_modifier_name: StringProperty(options={'HIDDEN'}, name='Deco Modifier Name')

    is_sculpt_modifier_muted: BoolProperty(options={'HIDDEN'}, name='Mute Sculpt Modifier')
    is_attribute_modifier_muted: BoolProperty(options={'HIDDEN'}, name='Mute Attribute Modifier')
    is_paint_modifier_muted: BoolProperty(options={'HIDDEN'}, name='Mute Paint Modifier')
    is_deco_modifier_muted: BoolProperty(options={'HIDDEN'}, name='Mute Deco Modifier')


def get_terrain_info_paint_layer_by_id(terrain_info: 'BDK_PG_terrain_info', layer_id: str) -> Optional[BDK_PG_terrain_paint_layer]:
    """
    Gets the paint layer with the given id, or None if no such layer exists.
    :param terrain_info:
    :param layer_id:
    :return:
    """
    for paint_layer in terrain_info.paint_layers:
        if paint_layer.id == layer_id:
            return paint_layer
    return None

def get_terrain_info_paint_layer_by_name(terrain_info: 'BDK_PG_terrain_info', layer_name: str) -> Optional[BDK_PG_terrain_paint_layer]:
    """
    Gets the paint layer with the given name, or None if no such layer exists.
    :param terrain_info:
    :param layer_name:
    :return:
    """
    for paint_layer in terrain_info.paint_layers:
        if paint_layer.name == layer_name:
            return paint_layer
    return None


def get_terrain_info_deco_layer_by_id(terrain_info: 'BDK_PG_terrain_info', layer_id: str) -> Optional[BDK_PG_terrain_deco_layer]:
    """
    Gets the deco layer with the given id, or None if no such layer exists.
    :param terrain_info:
    :param layer_id:
    :return:
    """
    for deco_layer in terrain_info.deco_layers:
        if deco_layer.id == layer_id:
            return deco_layer
    return None


classes = (
    BDK_PG_terrain_layer_node,
    BDK_PG_terrain_deco_layer,
    BDK_PG_terrain_paint_layer,
    BDK_PG_terrain_info,
)
