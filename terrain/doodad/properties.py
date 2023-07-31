from typing import List

from bpy.props import IntProperty, PointerProperty, CollectionProperty, FloatProperty, BoolProperty, StringProperty, \
    EnumProperty, FloatVectorProperty
from bpy.types import PropertyGroup, Object, NodeTree, Context

from .scatter.builder import ensure_scatter_layer_modifiers
from ...helpers import get_terrain_info, get_terrain_doodad
from ...units import meters_to_unreal
from .builder import ensure_terrain_info_modifiers
from .data import terrain_doodad_noise_type_items, terrain_doodad_operation_items, map_range_interpolation_type_items, \
    terrain_doodad_type_items


def terrain_doodad_sort_order_update_cb(self: 'BDK_PG_terrain_doodad', context: Context):
    terrain_info: 'BDK_PG_terrain_info' = get_terrain_info(self.terrain_info_object)
    ensure_terrain_info_modifiers(context, terrain_info)


def terrain_doodad_update_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context):
    # We update the node group whe the operation is changed since we don't want to use drivers to control the
    # operation for performance reasons. (TODO: NOT TRUE!)
    ensure_terrain_info_modifiers(context, self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info)


class BDK_PG_terrain_doodad_sculpt_layer(PropertyGroup):
    id: StringProperty(name='ID', default='')
    name: StringProperty(name='Name', default='Sculpt Layer')
    terrain_doodad_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', default=meters_to_unreal(1.0), subtype='DISTANCE')
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    depth: FloatProperty(name='Depth', default=meters_to_unreal(0.5), subtype='DISTANCE')
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    use_noise: BoolProperty(name='Use Noise', default=False)
    noise_type: EnumProperty(name='Noise Type', items=terrain_doodad_noise_type_items, default='WHITE')
    noise_radius_factor: FloatProperty(name='Noise Radius Factor', default=1.0, subtype='FACTOR', min=0.0, soft_max=8.0)
    noise_strength: FloatProperty(name='Noise Strength', default=meters_to_unreal(0.25), subtype='DISTANCE', min=0.0, soft_max=meters_to_unreal(2.0))
    noise_distortion: FloatProperty(name='Noise Distortion', default=1.0, min=0.0)
    noise_roughness: FloatProperty(name='Noise Roughness', default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    mute: BoolProperty(name='Mute', default=False)
    interpolation_type: EnumProperty(name='Interpolation Type', items=map_range_interpolation_type_items, default='LINEAR')


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


class BDK_PG_terrain_doodad_paint_layer(PropertyGroup): # TODO: rename this to something less confusing and ambiguous.
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Paint Layer')
    operation: EnumProperty(name='Operation', items=terrain_doodad_operation_items, default='ADD')
    interpolation_type: EnumProperty(
        name='Interpolation Type', items=map_range_interpolation_type_items, default='LINEAR')
    index: IntProperty(options={'HIDDEN'})
    terrain_doodad_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', subtype='DISTANCE', default=meters_to_unreal(1.0))
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    layer_type: EnumProperty(name='Layer Type', items=(
        ('PAINT', 'Paint', 'Paint layer.'),
        ('DECO', 'Deco', 'Deco layer.'),
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


axis_enum_items = [
    ('X', 'X', ''),
    ('Y', 'Y', ''),
    ('Z', 'Z', ''),
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


class BDK_PG_terrain_doodad_scatter_layer_object(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Name')
    mute: BoolProperty(name='Mute', default=False)

    terrain_doodad_object: PointerProperty(type=Object, name='Object', options={'HIDDEN'})
    object: PointerProperty(type=Object, name='Object',
                            poll=terrain_doodad_scatter_layer_object_object_poll_cb,
                            update=terrain_doodad_scatter_layer_update_cb)

    random_weight: FloatProperty(name='Random Weight', default=1.0, min=0.0, max=1.0)

    is_aligned_to_curve: BoolProperty(name='Aligned to Curve', default=False)
    align_axis: EnumProperty(name='Align Axis', items=axis_enum_items, default='Z')

    curve_normal_offset_min: FloatProperty(name='Normal Offset Min', default=0.0, subtype='DISTANCE')
    curve_normal_offset_max: FloatProperty(name='Normal Offset Max', default=0.0, subtype='DISTANCE')
    curve_normal_offset_seed: IntProperty(name='Normal Offset Seed', default=0, min=0)

    random_rotation_max: FloatProperty(name='Random Rotation', default=0.0, min=0.0, max=360.0, subtype='ANGLE')
    random_rotation_seed: IntProperty(name='Random Rotation Seed', default=0, min=0)

    scale_min: FloatVectorProperty(name='Scale Min', min=0.0, default=(1.0, 1.0, 1.0))
    scale_max: FloatVectorProperty(name='Scale Max', min=0.0, default=(1.0, 1.0, 1.0))
    scale_seed: IntProperty(name='Random Scale Seed', default=0, min=0)


class BDK_PG_terrain_doodad_scatter_layer(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    index: IntProperty(name='Index', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Scatter Layer')
    mute: BoolProperty(name='Mute', default=False)
    terrain_doodad_object: PointerProperty(type=Object, name='Terrain Doodad Object', options={'HIDDEN'})
    scatter_type: EnumProperty(name='Scatter Type', items=(
        ('ORDER', 'Order', 'The objects will be scattered in the order that they appear in the object list.'),
        ('RANDOM', 'Random', 'The objects will be scattered randomly based on the probability weight.'),
    ))
    objects: CollectionProperty(name='Scatter Objects', type=BDK_PG_terrain_doodad_scatter_layer_object)
    objects_index: IntProperty()

    snap_to_terrain: BoolProperty(name='Snap to Terrain', default=False)
    align_to_terrain: BoolProperty(name='Align to Terrain', default=False, description='Align the Z axis to the terrain normal')

    seed_object: PointerProperty(type=Object, name='Seed Object', options={'HIDDEN'})
    sprout_object: PointerProperty(type=Object, name='Sprout Object', options={'HIDDEN'})
    global_seed: IntProperty(name='Global Seed', default=0, min=0, description='Used to randomize the scatter without changing the seed of each option')
    rotation_seed: IntProperty(name='Rotation Seed', default=0, min=0)

    # Curve Settings
    curve_spacing_method: EnumProperty(name='Spacing Method', items=(
        ('RELATIVE', 'Relative', ''),
        ('ABSOLUTE', 'Absolute', ''),
    ), default='RELATIVE')
    curve_spacing_relative: FloatProperty(name='Spacing Min', default=1.0, min=0.1, soft_max=10.0, subtype='FACTOR')
    curve_spacing_absolute: FloatProperty(name='Spacing', default=1.0, min=0.0, subtype='DISTANCE')
    is_curve_reversed: BoolProperty(name='Reverse Curve', default=False)

    curve_trim_mode: EnumProperty(name='Trim Mode', items=(
        ('FACTOR', 'Factor', '', 0),
        ('LENGTH', 'Distance', '', 1),
    ), default='FACTOR')
    curve_trim_factor_start: FloatProperty(name='Trim Factor Start', default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    curve_trim_factor_end: FloatProperty(name='Trim Factor End', default=1.0, min=0.0, max=1.0, subtype='FACTOR')
    curve_trim_length_start: FloatProperty(name='Trim Length Start', default=0.0, min=0.0, subtype='DISTANCE')
    curve_trim_length_end: FloatProperty(name='Trim Length End', default=0.0, min=0.0, subtype='DISTANCE')

    curve_normal_offset: FloatProperty(name='Normal Offset', default=0.0, subtype='DISTANCE')
    curve_align_to_tangent: BoolProperty(name='Align to Tangent', default=False, description='Align the X axis of the object to the tangent of the curve')

    # Mesh Settings
    mesh_spacing_method: EnumProperty(name='Spacing Method', items=(
        ('RANDOM', 'Random', ''),
        ('POISSON_DISK', 'Poisson Disk', ''),
    ), default='RANDOM')
    mesh_density: FloatProperty(name='Density', default=1.0, min=0.0)
    mesh_distribution_seed: IntProperty(name='Distribution Seed', default=0, min=0)


class BDK_PG_terrain_doodad(PropertyGroup):
    id: StringProperty(options={'HIDDEN'}, name='ID')
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'}, name='Terrain Info Object')
    node_tree: PointerProperty(type=NodeTree, options={'HIDDEN'}, name='Node Tree')
    object: PointerProperty(type=Object, name='Object')
    is_3d: BoolProperty(name='3D', default=False)
    paint_layers: CollectionProperty(name='Paint Layers', type=BDK_PG_terrain_doodad_paint_layer)
    paint_layers_index: IntProperty()
    sculpt_layers: CollectionProperty(name='Sculpt Components', type=BDK_PG_terrain_doodad_sculpt_layer)
    sculpt_layers_index: IntProperty()
    # TODO: we probably need a "creation index" to use a stable tie-breaker for the sort order of the terrain doodad.
    #  we are currently using the ID of the terrain doodad, but this isn't ideal because the sort order is effectively
    #  random for terrain doodad that share the same sort order.
    sort_order: IntProperty(name='Sort Order', default=0, description='The order in which the terrain doodad are '
                                                                      'evaluated (lower values are evaluated first)',
                            update=terrain_doodad_sort_order_update_cb)
    scatter_layers: CollectionProperty(name='Scatter Layers', type=BDK_PG_terrain_doodad_scatter_layer)
    scatter_layers_index: IntProperty()


classes = (
    BDK_PG_terrain_doodad_paint_layer,
    BDK_PG_terrain_doodad_sculpt_layer,
    BDK_PG_terrain_doodad_scatter_layer_object,
    BDK_PG_terrain_doodad_scatter_layer,
    BDK_PG_terrain_doodad,
)
