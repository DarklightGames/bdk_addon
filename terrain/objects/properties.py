from typing import List

import bpy
from bpy.props import IntProperty, PointerProperty, CollectionProperty, FloatProperty, BoolProperty, StringProperty, \
    EnumProperty
from bpy.types import PropertyGroup, Object, NodeTree, Context

from ...helpers import get_terrain_info
from .builder import update_terrain_object_geometry_node_group
from ...units import meters_to_unreal
from .data import terrain_object_noise_type_items, terrain_object_operation_items, map_range_interpolation_type_items, \
    terrain_object_type_items


def get_terrain_objects_for_terrain_info_object(context: Context, terrain_info_object: Object) -> List['BDK_PG_terrain_object']:
    return [obj.bdk.terrain_object for obj in context.scene.objects if obj.bdk.type == 'TERRAIN_OBJECT' and obj.bdk.terrain_object.terrain_info_object == terrain_info_object]


def sort_terrain_info_modifiers(context: Context, terrain_info: 'BDK_PG_terrain_info'):
    """
    Sort the modifiers on the terrain info object in the following order:
    1. Terrain Object Sculpt (so that the 3D geometry is locked in for the other modifiers)
     > the question is whether or not we should combine all sculpts into one mega-modifier or have them separated.
     > might need to inquire about performance implications of either approach.
    2. Paint Nodes (so that deco layers can read the paint layer alpha values)
    3. Deco Nodes (final consumer of the geo & paint layer alpha values)
    :param context:
    :param terrain_info:
    :return:
    """

    terrain_info_object = terrain_info.terrain_info_object

    # The modifier ID list will contain a list of modifier IDs in the order that they should be sorted.
    modifier_ids = []

    # Add in the list of all paint and deco layers.
    modifier_ids.extend(map(lambda paint_layer: paint_layer.id, terrain_info.paint_layers))
    modifier_ids.extend(map(lambda deco_layer: deco_layer.id, terrain_info.deco_layers))

    # Get list of all terrain objects that are part of the same terrain info object.
    terrain_objects = get_terrain_objects_for_terrain_info_object(context, terrain_info_object)

    # Sort the terrain objects by sort order, then ID.
    terrain_objects.sort(key=lambda x: (x.sort_order, x.id))

    for terrain_object in terrain_objects:
        for sculpt_layer in terrain_object.sculpt_layers:
            pass

    for terrain_object in terrain_objects:
        for paint_layer in terrain_object.paint_layers:
            if paint_layer.layer_type == 'PAINT':
                pass

    for terrain_object in terrain_objects:
        for paint_layer in terrain_object.paint_layers:
            if paint_layer.layer_type == 'DECO':
                pass

    # TODO: we need to split the terrain objects into two passes of modifiers each terrain object then needs two
    #  modifier IDs (maybe even 3 if we have one for the deco?)
    # Make note of what the current mode is so that we can restore it later.
    current_mode = bpy.context.object.mode
    current_active_object = bpy.context.view_layer.objects.active

    # Set the mode to OBJECT so that we can move the modifiers.
    bpy.ops.object.mode_set(mode='OBJECT')

    # Make the active object the terrain info object.
    bpy.context.view_layer.objects.active = terrain_info_object

    # It's theoretically possible that the modifiers don't exist (e.g., having been deleted by the user, debugging etc.)
    # Get a list of missing modifiers.
    missing_modifier_ids = set(modifier_ids).difference(set(terrain_info_object.modifiers.keys()))
    if len(missing_modifier_ids) > 0:
        print(f'Missing modifiers: {missing_modifier_ids}')

    # Remove any modifier IDs that do not have a corresponding modifier in the terrain info object.
    modifier_ids = [x for x in modifier_ids if x in terrain_info_object.modifiers]

    # TODO: it would be nice if we could move the modifiers without needing to use the ops API, or at least suspend
    #  evaluation of the node tree while we do it.

    # TODO: we can use the data API to do this, but we need to know the index of the modifier in the list.
    # Update the modifiers on the terrain info object to reflect the new sort order.
    for i, modifier_id in enumerate(modifier_ids):
        bpy.ops.object.modifier_move_to_index(modifier=modifier_id, index=i)

    # Restore the mode and active object to what it was before.
    bpy.context.view_layer.objects.active = current_active_object
    bpy.ops.object.mode_set(mode=current_mode)


def terrain_object_sort_order_update_cb(self: 'BDK_PG_terrain_object', context: Context):
    terrain_info: 'BDK_PG_terrain_info' = get_terrain_info(self.terrain_info_object)
    sort_terrain_info_modifiers(context, terrain_info)


def terrain_object_update_cb(self: 'BDK_PG_terrain_object_paint_layer', context: Context):
    # We update the node group whe the operation is changed since we don't want to use drivers to control the
    # operation for performance reasons.
    update_terrain_object_geometry_node_group(self.terrain_object.bdk.terrain_object)


class BDK_PG_terrain_object_sculpt_layer(PropertyGroup):
    id: StringProperty(name='ID', default='')
    name: StringProperty(name='Name', default='Sculpt Layer')
    terrain_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', default=meters_to_unreal(1.0), subtype='DISTANCE')
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    depth: FloatProperty(name='Depth', default=meters_to_unreal(0.5), subtype='DISTANCE')
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    use_noise: BoolProperty(name='Use Noise', default=False)
    noise_type: EnumProperty(name='Noise Type', items=terrain_object_noise_type_items, default='WHITE')
    noise_radius_factor: FloatProperty(name='Noise Radius Factor', default=1.0, subtype='FACTOR', min=0.0, soft_max=8.0)
    noise_strength: FloatProperty(name='Noise Strength', default=meters_to_unreal(0.25), subtype='DISTANCE', min=0.0, soft_max=meters_to_unreal(2.0))
    noise_distortion: FloatProperty(name='Noise Distortion', default=1.0, min=0.0)
    noise_roughness: FloatProperty(name='Noise Roughness', default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    mute: BoolProperty(name='Mute', default=False)
    interpolation_type: EnumProperty(name='Interpolation Type', items=map_range_interpolation_type_items, default='LINEAR')


def terrain_object_paint_layer_paint_layer_name_search_cb(self: 'BDK_PG_terrain_object_paint_layer', context: Context, edit_text: str) -> List[str]:
    # Get a list of terrain layer names for the selected terrain info object.
    # TODO: This is insanely verbose.
    paint_layers = self.terrain_object.bdk.terrain_object.terrain_info_object.bdk.terrain_info.paint_layers
    return [paint_layer.name for paint_layer in paint_layers]


def terrain_object_paint_layer_deco_layer_name_search_cb(self: 'BDK_PG_terrain_object_paint_layer', context: Context, edit_text: str) -> List[str]:
    # Get a list of deco layer names for the selected terrain info object.
    deco_layers = self.terrain_object.bdk.terrain_object.terrain_info_object.bdk.terrain_info.deco_layers
    return [deco_layer.name for deco_layer in deco_layers]


def terrain_object_paint_layer_paint_layer_name_update_cb(self: 'BDK_PG_terrain_object_paint_layer', context: Context):
    # Update the terrain layer ID when the terrain layer name is changed.
    paint_layers = self.terrain_object.bdk.terrain_object.terrain_info_object.bdk.terrain_info.paint_layers

    # Get the index of the terrain layer with the given name.
    paint_layer_names = [paint_layer.name for paint_layer in paint_layers]

    try:
        paint_layer_index = paint_layer_names.index(self.paint_layer_name)
        self.paint_layer_id = paint_layers[paint_layer_index].id
    except ValueError:
        self.paint_layer_id = ''

    update_terrain_object_geometry_node_group(self.terrain_object.bdk.terrain_object)


def terrain_object_paint_layer_deco_layer_name_update_cb(self: 'BDK_PG_terrain_object_paint_layer', context: Context):
    # Update the deco layer ID when the deco layer name is changed.
    deco_layers = self.terrain_object.bdk.terrain_object.terrain_info_object.bdk.terrain_info.deco_layers

    # Get the index of the deco layer with the given name.
    deco_layer_names = [deco_layer.name for deco_layer in deco_layers]

    try:
        deco_layer_index = deco_layer_names.index(self.deco_layer_name)
        self.deco_layer_id = deco_layers[deco_layer_index].id
    except ValueError:
        self.deco_layer_id = ''

    update_terrain_object_geometry_node_group(self.terrain_object.bdk.terrain_object)


class BDK_PG_terrain_object_paint_layer(PropertyGroup): # TODO: rename this to something less confusing and ambiguous.
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Paint Layer')
    operation: EnumProperty(name='Operation', items=terrain_object_operation_items, default='ADD')
    interpolation_type: EnumProperty(name='Interpolation Type', items=map_range_interpolation_type_items, default='LINEAR')
    index: IntProperty(options={'HIDDEN'})
    terrain_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', subtype='DISTANCE', default=meters_to_unreal(1.0))
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    layer_type: EnumProperty(name='Layer Type', items=(
        ('PAINT', 'Paint', 'Paint layer.'),
        ('DECO', 'Deco', 'Deco layer.'),
    ), default='PAINT', update=terrain_object_update_cb)  # TODO: switch node this as well
    paint_layer_name: StringProperty(
        name='Paint Layer',
        search=terrain_object_paint_layer_paint_layer_name_search_cb,
        update=terrain_object_paint_layer_paint_layer_name_update_cb,
        search_options={'SORT'}
    )
    deco_layer_name: StringProperty(
        name='Deco Layer',
        search=terrain_object_paint_layer_deco_layer_name_search_cb,
        update=terrain_object_paint_layer_deco_layer_name_update_cb,
        search_options={'SORT'}
    )
    paint_layer_id: StringProperty(name='Terrain Layer ID', default='', options={'HIDDEN'})
    deco_layer_id: StringProperty(name='Deco Layer ID', default='', options={'HIDDEN'})
    mute: BoolProperty(name='Mute', default=False)

    use_distance_noise: BoolProperty(name='Distance Noise', default=False)
    noise_type: EnumProperty(name='Noise Type', items=terrain_object_noise_type_items, default='WHITE', update=terrain_object_update_cb)
    distance_noise_factor: FloatProperty(name='Distance Noise Factor', default=meters_to_unreal(0.5), subtype='DISTANCE', min=0.0)
    distance_noise_distortion: FloatProperty(name='Distance Noise Distortion', default=1.0, min=0.0)
    distance_noise_offset: FloatProperty(name='Distance Noise Offset', default=0.5, min=0.0, max=1.0, subtype='FACTOR')


class BDK_PG_terrain_object(PropertyGroup):
    id: StringProperty(options={'HIDDEN'}, name='ID')
    object_type: EnumProperty(name='Object Type', items=terrain_object_type_items, default='CURVE')
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'}, name='Terrain Info Object')
    node_tree: PointerProperty(type=NodeTree, options={'HIDDEN'}, name='Node Tree')
    object: PointerProperty(type=Object, name='Object')
    is_3d: BoolProperty(name='3D', default=False)
    paint_layers: CollectionProperty(name='Paint Components', type=BDK_PG_terrain_object_paint_layer)
    paint_layers_index: IntProperty()
    sculpt_layers: CollectionProperty(name='Sculpt Components', type=BDK_PG_terrain_object_sculpt_layer)
    sculpt_layers_index: IntProperty()
    # TODO: we probably need a "creation index" to use a stable tie-breaker for the sort order of the terrain objects.
    #  we are currently using the ID of the terrain object, but this isn't ideal because the sort order is effectively
    #  random for terrain objects that share the same sort order.
    sort_order: IntProperty(name='Sort Order', default=0, description='The order in which the terrain objects are '
                                                                      'evaluated (lower values are evaluated first)',
                            update=terrain_object_sort_order_update_cb)


classes = (
    BDK_PG_terrain_object_paint_layer,
    BDK_PG_terrain_object_sculpt_layer,
    BDK_PG_terrain_object,
)
