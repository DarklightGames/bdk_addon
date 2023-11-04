import math
from typing import List

from bpy.props import IntProperty, PointerProperty, CollectionProperty, FloatProperty, BoolProperty, StringProperty, \
    EnumProperty, FloatVectorProperty
from bpy.types import PropertyGroup, Object, NodeTree, Context

from ...constants import RADIUS_EPSILON
from .sculpt.properties import BDK_PG_terrain_doodad_sculpt_layer
from ...property_group_helpers import add_curve_modifier_properties
from ..properties import BDK_PG_terrain_layer_node
from ...data import map_range_interpolation_type_items
from ...helpers import get_terrain_info, get_terrain_doodad
from ...units import meters_to_unreal
from .builder import ensure_terrain_info_modifiers
from .data import terrain_doodad_noise_type_items, terrain_doodad_operation_items
from .scatter.builder import ensure_scatter_layer_modifiers

empty_set = set()


def terrain_doodad_sort_order_update_cb(self: 'BDK_PG_terrain_doodad', context: Context):
    terrain_info: 'BDK_PG_terrain_info' = get_terrain_info(self.terrain_info_object)
    ensure_terrain_info_modifiers(context, terrain_info)


def terrain_doodad_update_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context):
    # We update the node group whe the operation is changed since we don't want to use drivers to control the
    # operation for performance reasons. (TODO: NOT TRUE!)
    ensure_terrain_info_modifiers(context, self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info)


def terrain_doodad_paint_layer_paint_layer_name_search_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context, edit_text: str) -> List[str]:
    # Get a list of terrain layer names for the selected terrain info object.
    # TODO: This is insanely verbose.
    paint_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.paint_layers
    return [paint_layer.name for paint_layer in paint_layers]


def terrain_doodad_paint_layer_deco_layer_name_search_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context, edit_text: str) -> List[str]:
    # Get a list of deco layer names for the selected terrain info object.
    deco_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.deco_layers
    return [deco_layer.name for deco_layer in deco_layers]


def terrain_doodad_paint_layer_paint_layer_name_update_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context):
    # Update the terrain layer ID when the terrain layer name is changed.
    paint_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.paint_layers

    # Get the index of the terrain layer with the given name.
    paint_layer_names = [paint_layer.name for paint_layer in paint_layers]

    try:
        paint_layer_index = paint_layer_names.index(self.paint_layer_name)
        self.paint_layer_id = paint_layers[paint_layer_index].id
    except ValueError:
        self.paint_layer_id = ''

    ensure_terrain_info_modifiers(context, self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info)


def terrain_doodad_paint_layer_deco_layer_name_update_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context):
    # Update the deco layer ID when the deco layer name is changed.
    deco_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.deco_layers

    # Get the index of the deco layer with the given name.
    deco_layer_names = [deco_layer.name for deco_layer in deco_layers]

    try:
        deco_layer_index = deco_layer_names.index(self.deco_layer_name)
        self.deco_layer_id = deco_layers[deco_layer_index].id
    except ValueError:
        self.deco_layer_id = ''

    ensure_terrain_info_modifiers(context, self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info)


class BDK_PG_terrain_doodad_paint_layer(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Paint Layer')
    operation: EnumProperty(name='Operation', items=terrain_doodad_operation_items, default='ADD')
    interpolation_type: EnumProperty(
        name='Interpolation Type', items=map_range_interpolation_type_items, default='LINEAR')
    index: IntProperty(options={'HIDDEN'})
    terrain_doodad_object: PointerProperty(type=Object, options={'HIDDEN'})
    radius: FloatProperty(name='Radius', subtype='DISTANCE', default=meters_to_unreal(1.0), min=RADIUS_EPSILON)
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=RADIUS_EPSILON)
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    layer_type: EnumProperty(name='Layer Type', items=(
        ('PAINT', 'Paint', 'Paint layer'),
        ('DECO', 'Deco', 'Deco layer'),
        ('ATTRIBUTE', 'Attribute', 'Attribute layer')
    ), default='PAINT', update=terrain_doodad_update_cb)  # TODO: switch node this as well
    paint_layer_name: StringProperty(
        name='Paint Layer',
        search=terrain_doodad_paint_layer_paint_layer_name_search_cb,
        update=terrain_doodad_paint_layer_paint_layer_name_update_cb,
        search_options={'SORT'}
    )
    deco_layer_name: StringProperty(
        name='Deco Layer',
        search=terrain_doodad_paint_layer_deco_layer_name_search_cb,
        update=terrain_doodad_paint_layer_deco_layer_name_update_cb,
        search_options={'SORT'}
    )
    attribute_layer_id: StringProperty(name='Attribute Layer ID', default='')
    paint_layer_id: StringProperty(name='Terrain Layer ID', default='', options={'HIDDEN'})
    deco_layer_id: StringProperty(name='Deco Layer ID', default='', options={'HIDDEN'})
    mute: BoolProperty(name='Mute', default=False)

    use_distance_noise: BoolProperty(name='Distance Noise', default=False)
    # TODO: Convert this to just use a switch node
    noise_type: EnumProperty(
        name='Noise Type', items=terrain_doodad_noise_type_items, default='WHITE', update=terrain_doodad_update_cb)
    distance_noise_factor: FloatProperty(
        name='Distance Noise Factor', default=meters_to_unreal(0.5), subtype='DISTANCE', min=0.0)
    distance_noise_distortion: FloatProperty(name='Distance Noise Distortion', default=1.0, min=0.0)
    distance_noise_offset: FloatProperty(name='Distance Noise Offset', default=0.5, min=0.0, max=1.0, subtype='FACTOR')

    frozen_attribute_id: StringProperty(name='Frozen Attribute ID', default='', options={'HIDDEN'})


add_curve_modifier_properties(BDK_PG_terrain_doodad_paint_layer)

axis_enum_items = [
    ('X', 'X', '', 0),
    ('Y', 'Y', '', 1),
    ('Z', 'Z', '', 2),
]

axis_signed_enum_items = [
    ('X', 'X', '', 0),
    ('Y', 'Y', '', 1),
    ('Z', 'Z', '', 2),
    ('-X', '-X', ''),
    ('-Y', '-Y', ''),
    ('-Z', '-Z', ''),
]


def terrain_doodad_scatter_layer_object_object_poll_cb(_self, bpy_object: Object):
    # Only allow objects that are static meshes.
    return bpy_object.type == 'MESH' and bpy_object.get('Class', None) == 'StaticMeshActor'


def terrain_doodad_scatter_layer_update_cb(self: 'BDK_PG_terrain_doodad_scatter_layer_object', context: Context):
    terrain_doodad = get_terrain_doodad(self.terrain_doodad_object)
    ensure_scatter_layer_modifiers(context, terrain_doodad)


collision_flags_enum_items = (
    ('BLOCK_ACTORS', 'Block Actors', 'Blocks other non-player actors'),
    ('BLOCK_KARMA', 'Block Karma', 'Block actors being simulated with Karma such as vehicles and rag-dolls'),
    ('BLOCK_NON_ZERO_EXTENT_TRACES', 'Block Non-Zero Extent Traces', 'Block non-zero extent traces such as pawn capsules'),
    ('BLOCK_ZERO_EXTENT_TRACES', 'Block Zero Extent Traces', 'Block zero extent traces such as projectiles'),
    ('COLLIDE_ACTORS', 'Collide Actors', 'Collides with other actors'),
)


class BDK_PG_actor_properties(PropertyGroup):
    class_name: StringProperty(name='Class Name', default='StaticMeshActor')
    should_use_cull_distance: BoolProperty(name='Use Culling', default=True)
    cull_distance: FloatProperty(name='Cull Distance', default=meters_to_unreal(50.0), min=0.0, subtype='DISTANCE', description='The distance beyond which the actor will not be rendered')
    collision_flags: EnumProperty(name='Collision Flags', items=collision_flags_enum_items, options={'ENUM_FLAG'})


class BDK_PG_terrain_doodad_scatter_layer_object(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Name')
    mute: BoolProperty(name='Mute', default=False)

    terrain_doodad_object: PointerProperty(type=Object, name='Object', options={'HIDDEN'})
    object: PointerProperty(type=Object, name='Object',
                            poll=terrain_doodad_scatter_layer_object_object_poll_cb,
                            update=terrain_doodad_scatter_layer_update_cb)

    random_weight: FloatProperty(name='Random Weight', default=1.0, min=0.0, soft_max=10.0, subtype='FACTOR')

    is_aligned_to_curve: BoolProperty(name='Aligned to Curve', default=False)
    align_axis: EnumProperty(name='Align Axis', items=axis_signed_enum_items, default='Z')

    rotation_offset: FloatVectorProperty(name='Rotation Offset', subtype='EULER', default=(0.0, 0.0, 0.0))

    random_rotation_max: FloatVectorProperty(name='Random Rotation', subtype='EULER', min=0.0, max=math.pi, default=(0.0, 0.0, 0.0))
    random_rotation_max_seed: IntProperty(name='Random Rotation Seed', default=0, min=0)

    scale_mode: EnumProperty(name='Scale Mode', items=(
        ('UNIFORM', 'Uniform', 'All axes will be scaled by the same amount', '', 0),
        ('NON_UNIFORM', 'Non-Uniform', 'Each axis will be scaled independently', '', 1),
    ), default='UNIFORM')
    scale_uniform: FloatProperty(name='Scale', default=1.0, min=0.0)
    scale: FloatVectorProperty(name='Scale', min=0.0, default=(1.0, 1.0, 1.0))
    scale_random_uniform_min: FloatProperty(name='Scale Min', default=1.0, min=0.0)
    scale_random_uniform_max: FloatProperty(name='Scale Max', default=1.0, min=0.0)
    scale_random_min: FloatVectorProperty(name='Scale Min', min=0.0, default=(1.0, 1.0, 1.0))
    scale_random_max: FloatVectorProperty(name='Scale Max', min=0.0, default=(1.0, 1.0, 1.0))
    scale_random_distribution: EnumProperty(name='Scale Random Distribution', items=(
        ('UNIFORM', 'Uniform', 'Uniform distribution', '', 0),
        ('GAUSSIAN', 'Gaussian', 'Gaussian distribution', '', 1),
    ), default='UNIFORM')
    scale_seed: IntProperty(name='Random Scale Seed', default=0, min=0)

    # Snap & Align to Terrain
    snap_to_terrain: BoolProperty(name='Snap to Terrain', default=True)
    align_to_terrain_factor: FloatProperty(name='Align to Terrain', min=0.0, max=1.0, default=1.0, description='Align the Z axis to the terrain normal', subtype='FACTOR')
    terrain_normal_offset_min: FloatProperty(name='Terrain Normal Offset Min', default=0.0, subtype='DISTANCE')
    terrain_normal_offset_max: FloatProperty(name='Terrain Normal Offset Max', default=0.0, subtype='DISTANCE')
    terrain_normal_offset_seed: IntProperty(name='Terrain Normal Offset Seed', default=0, min=0)

    # Actor Properties
    actor_properties: PointerProperty(type=BDK_PG_actor_properties, name='Actor Properties', options={'HIDDEN'})



class BDK_PG_terrain_doodad_scatter_layer(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    name: StringProperty(name='Name', default='Scatter Layer')
    mute: BoolProperty(name='Mute', default=False)
    terrain_doodad_object: PointerProperty(type=Object, name='Terrain Doodad Object', options={'HIDDEN'})
    scatter_type: EnumProperty(name='Scatter Type', items=(
        ('ORDER', 'Order', 'The objects will be scattered in the order that they appear in the object list.'),
        ('RANDOM', 'Random', 'The objects will be scattered randomly based on the probability weight.'),
    ))

    # Objects
    objects: CollectionProperty(name='Scatter Objects', type=BDK_PG_terrain_doodad_scatter_layer_object)
    objects_index: IntProperty()

    # Object Selection
    object_select_mode: EnumProperty(name='Object Select Mode', items=(
        ('RANDOM', 'Random', 'Select a random object from the list', '', 0),
        ('CYCLIC', 'Cyclic', 'Select from the list in the order that they appear', '', 1),
        ('WEIGHTED_RANDOM', 'Weighted Random', 'Select a random object from the list based on the relative probability weight', '', 2)
    ), default='RANDOM')
    object_select_random_seed: IntProperty(name='Object Select Random Seed', default=0, min=0)
    object_select_cyclic_offset: IntProperty(name='Object Select Cyclic Offset', default=0, min=0)

    seed_object: PointerProperty(type=Object, name='Seed Object', options={'HIDDEN'})
    sprout_object: PointerProperty(type=Object, name='Sprout Object', options={'HIDDEN'})

    global_seed: IntProperty(name='Global Seed', default=0, min=0, description='Used to randomize the scatter without changing the seed of each option')
    density: FloatProperty(name='Density', default=1.0, min=0.0, max=1.0, subtype='FACTOR', description='The probability that the object will be scattered')
    density_seed: IntProperty(name='Density Seed', default=0, min=0, description='Used to randomize the scatter without changing the seed of each option')

    # Curve Settings
    curve_spacing_method: EnumProperty(name='Spacing Method', items=(
        ('RELATIVE', 'Relative', ''),
        ('ABSOLUTE', 'Absolute', ''),
    ), default='RELATIVE')
    curve_spacing_relative_factor: FloatProperty(name='Spacing Relative Factor', default=1.0, min=0.1, soft_max=10.0, subtype='FACTOR')
    curve_spacing_absolute: FloatProperty(name='Spacing', default=meters_to_unreal(1.0), min=1, subtype='DISTANCE')
    curve_spacing_relative_axis: EnumProperty(name='Spacing Relative Axis', items=axis_enum_items, default='X')

    curve_normal_offset_max: FloatProperty(name='Normal Offset Max', default=0.0, subtype='DISTANCE')
    curve_normal_offset_seed: IntProperty(name='Normal Offset Seed', default=0, min=0)

    curve_tangent_offset_max: FloatProperty(name='Tangent Offset Max', default=0.0, subtype='DISTANCE')
    curve_tangent_offset_seed: IntProperty(name='Tangent Offset Seed', default=0, min=0)

    # Mesh Settings
    mesh_element_mode: EnumProperty(name='Element Mode', items=(
        ('FACE', 'Face', '', 'FACESEL', 0),
        ('VERT', 'Vertex', '', 'VERTEXSEL', 1),
    ), default='FACE')
    mesh_face_distribute_method: EnumProperty(name='Distribution Method', items=(
        ('RANDOM', 'Random', 'Points will be distributed randomly'),
        ('POISSON_DISK', 'Poisson Disk', 'Poisson-disc sampling produces points that are tightly-packed, but no closer to each other than a specified minimum distance, resulting in a more natural pattern'),
    ), default='POISSON_DISK')
    mesh_face_distribute_random_density: FloatProperty(name='Density', default=0.001, min=0.0, soft_max=0.1)
    mesh_face_distribute_poisson_distance_min: FloatProperty(name='Distance Min', default=meters_to_unreal(1.0), min=0.0, subtype='DISTANCE')
    mesh_face_distribute_poisson_density_max: FloatProperty(name='Density', default=0.001, min=0.0)  # We could make this a more sensible unit. IIRC, the current unit is the number of points per square unit, which is bonkers.
    mesh_face_distribute_poisson_density_factor: FloatProperty(name='Density Factor', default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    mesh_face_distribute_seed: IntProperty(name='Distribution Seed', default=0, min=0)

    # Mask Settings
    use_mask_nodes: BoolProperty(name='Use Mask Nodes', default=False, options=set())
    mask_nodes: CollectionProperty(name='Mask Nodes', type=BDK_PG_terrain_layer_node)
    mask_nodes_index: IntProperty(options={'HIDDEN'})
    mask_attribute_id: StringProperty(name='Mask Attribute ID', default='', options={'HIDDEN'})

add_curve_modifier_properties(BDK_PG_terrain_doodad_scatter_layer)


class BDK_PG_terrain_doodad(PropertyGroup):
    id: StringProperty(options={'HIDDEN'}, name='ID')
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'}, name='Terrain Info Object')
    node_tree: PointerProperty(type=NodeTree, options={'HIDDEN'}, name='Node Tree')
    object: PointerProperty(type=Object, name='Object')
    is_3d: BoolProperty(name='3D', default=False)
    paint_layers: CollectionProperty(name='Paint Layers', type=BDK_PG_terrain_doodad_paint_layer)
    paint_layers_index: IntProperty()
    sculpt_layers: CollectionProperty(name='Sculpt Layers', type=BDK_PG_terrain_doodad_sculpt_layer)
    sculpt_layers_index: IntProperty()

    # TODO: not yet implemented
    radius_factor: FloatProperty(name='Radius Factor', default=1.0, min=RADIUS_EPSILON, soft_max=10, subtype='FACTOR',
                                 description='All radius values will be multiplied by this value. This is useful for '
                                                'scaling the radius of all layers at once.')

    # TODO: we probably need a "creation index" to use a stable tie-breaker for the sort order of the terrain doodad.
    #  we are currently using the ID of the terrain doodad, but this isn't ideal because the sort order is effectively
    #  random for terrain doodad that share the same sort order.
    sort_order: IntProperty(name='Sort Order', default=0, description='The order in which the terrain doodad are '
                                                                      'evaluated (lower values are evaluated first)',
                            update=terrain_doodad_sort_order_update_cb)
    scatter_layers: CollectionProperty(name='Scatter Layers', type=BDK_PG_terrain_doodad_scatter_layer)
    scatter_layers_index: IntProperty()

    is_frozen: BoolProperty(name='Is Frozen', default=False)


classes = (
    BDK_PG_actor_properties,
    BDK_PG_terrain_doodad_paint_layer,
    BDK_PG_terrain_doodad_scatter_layer_object,
    BDK_PG_terrain_doodad_scatter_layer,
    BDK_PG_terrain_doodad,
)
