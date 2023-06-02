from typing import List

import bpy
from bpy.props import IntProperty, PointerProperty, CollectionProperty, FloatProperty, BoolProperty, StringProperty, \
    EnumProperty
from bpy.types import PropertyGroup, Object, NodeTree, Context

from .builder import update_terrain_object_geometry_node_group
from ...units import meters_to_unreal


def get_terrain_objects_for_terrain_info_object(context: Context, terrain_info_object: Object) -> List:
    return [obj.bdk.terrain_object for obj in context.scene.objects if obj.bdk.type == 'TERRAIN_OBJECT' and obj.bdk.terrain_object.terrain_info_object == terrain_info_object]


def terrain_object_sort_order_update_cb(self: 'BDK_PG_terrain_object', context: Context):
    # Get list of all terrain objects that are part of the same terrain info object.
    terrain_objects = get_terrain_objects_for_terrain_info_object(context, self.terrain_info_object)

    # Sort the terrain objects by sort order, then ID.
    terrain_objects.sort(key=lambda x: (x.sort_order, x.id))
    terrain_info_object = self.terrain_info_object

    # Make note of what the current mode is so we can restore it later.
    current_mode = bpy.context.object.mode
    current_active_object = bpy.context.view_layer.objects.active

    # Set the mode to OBJECT so that we can move the modifiers.
    bpy.ops.object.mode_set(mode='OBJECT')

    # Make the active object the terrain info object.
    bpy.context.view_layer.objects.active = terrain_info_object

    # Update the modifiers on the terrain info object to reflect the new sort order.
    for i, terrain_object in enumerate(terrain_objects):
        bpy.ops.object.modifier_move_to_index(modifier=terrain_object.id, index=i)

    # Restore the mode and active object to what it was before.
    bpy.context.view_layer.objects.active = current_active_object
    bpy.ops.object.mode_set(mode=current_mode)


def terrain_object_update_cb(self: 'BDK_PG_terrain_object_paint_layer', context: Context):
    # We update the node group whe the operation is changed since we don't want to use drivers to control the
    # operation for performance reasons.
    update_terrain_object_geometry_node_group(self.terrain_object.bdk.terrain_object)


class BDK_PG_terrain_object_sculpt_layer(PropertyGroup):
    name: StringProperty(name='Name', default='Sculpt Layer')
    terrain_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', default=meters_to_unreal(1.0), subtype='DISTANCE')
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    depth: FloatProperty(name='Depth', default=meters_to_unreal(0.5), subtype='DISTANCE')
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    use_noise: BoolProperty(name='Use Noise', default=False)
    noise_type: EnumProperty(name='Noise Type', items=(
        ('WHITE', 'White', 'White noise'),
        ('PERLIN', 'Perlin', 'Perlin noise'),
    ), default='WHITE')
    noise_radius_factor: FloatProperty(name='Noise Radius Factor', default=1.0, subtype='FACTOR', min=0.0, soft_max=8.0)
    noise_strength: FloatProperty(name='Noise Strength', default=meters_to_unreal(0.25), subtype='DISTANCE', min=0.0, soft_max=meters_to_unreal(2.0))
    noise_distortion: FloatProperty(name='Noise Distortion', default=1.0, min=0.0)
    noise_roughness: FloatProperty(name='Noise Roughness', default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    mute: BoolProperty(name='Mute', default=False)
    interpolation_type: EnumProperty(name='Interpolation Type', items=(
        ('LINEAR', 'Linear', 'Linear interpolation between From Min and From Max values.', 'LINCURVE', 0),
        ('STEPPED', 'Stepped', 'Stepped linear interpolation between From Min and From Max values.', 'IPO_CONSTANT', 1),
        ('SMOOTHSTEP', 'Smooth Step', 'Smooth Hermite edge interpolation between From Min and From Max values.', 'IPO_EASE_IN', 2),
        ('SMOOTHERSTEP', 'Smoother Step', 'Smoother Hermite edge interpolation between From Min and From Max values.', 'IPO_EASE_IN_OUT', 3),
    ), default='LINEAR', update=terrain_object_update_cb)


def terrain_object_paint_layer_terrain_layer_name_search_cb(self: 'BDK_PG_terrain_object_paint_layer', context: Context, edit_text: str) -> List[str]:
    # Get a list of terrain layer names for the selected terrain info object.
    # TODO: This is insanely verbose.
    terrain_layers = self.terrain_object.bdk.terrain_object.terrain_info_object.bdk.terrain_info.terrain_layers
    return [terrain_layer.name for terrain_layer in terrain_layers]


def terrain_object_paint_layer_deco_layer_name_search_cb(self: 'BDK_PG_terrain_object_paint_layer', context: Context, edit_text: str) -> List[str]:
    # Get a list of deco layer names for the selected terrain info object.
    deco_layers = self.terrain_object.bdk.terrain_object.terrain_info_object.bdk.terrain_info.deco_layers
    return [deco_layer.name for deco_layer in deco_layers]


def terrain_object_paint_layer_terrain_layer_name_update_cb(self: 'BDK_PG_terrain_object_paint_layer', context: Context):
    # Update the terrain layer ID when the terrain layer name is changed.
    terrain_layers = self.terrain_object.bdk.terrain_object.terrain_info_object.bdk.terrain_info.terrain_layers

    # Get the index of the terrain layer with the given name.
    terrain_layer_names = [terrain_layer.name for terrain_layer in terrain_layers]

    try:
        terrain_layer_index = terrain_layer_names.index(self.terrain_layer_name)
        self.terrain_layer_id = terrain_layers[terrain_layer_index].color_attribute_name
    except ValueError:
        self.terrain_layer_id = ''

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


class BDK_PG_terrain_object_paint_layer(PropertyGroup):
    name: StringProperty(name='Name', default='Paint Layer')
    operation: EnumProperty(name='Operation', items=(
        ('ADD', 'Add', 'Add paint to the terrain layer.'),
        ('SUBTRACT', 'Subtract', 'Subtract paint from the terrain layer.'),
    ), default='ADD', update=terrain_object_update_cb)
    interpolation_type: EnumProperty(name='Interpolation Type', items=(
        ('LINEAR', 'Linear', 'Linear interpolation between From Min and From Max values.', 'IPO_LINEAR', 0),
        ('STEPPED', 'Stepped', 'Stepped linear interpolation between From Min and From Max values.', 'IPO_CONSTANT', 1),
        ('SMOOTHSTEP', 'Smooth Step', 'Smooth Hermite edge interpolation between From Min and From Max values.', 'IPO_EASE_IN', 2),
        ('SMOOTHERSTEP', 'Smoother Step', 'Smoother Hermite edge interpolation between From Min and From Max values.', 'IPO_EASE_IN_OUT', 3),
    ), default='LINEAR', update=terrain_object_update_cb)
    index: IntProperty(options={'HIDDEN'})
    terrain_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', subtype='DISTANCE', default=meters_to_unreal(1.0))
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    layer_type: EnumProperty(name='Layer Type', items=(
        ('TERRAIN', 'Terrain', 'Terrain layer.'),
        ('DECO', 'Deco', 'Deco layer.'),
    ), default='TERRAIN', update=terrain_object_update_cb)
    terrain_layer_name: StringProperty(
        name='Terrain Layer',
        search=terrain_object_paint_layer_terrain_layer_name_search_cb,
        update=terrain_object_paint_layer_terrain_layer_name_update_cb,
        search_options={'SORT'}
    )
    deco_layer_name: StringProperty(
        name='Deco Layer',
        search=terrain_object_paint_layer_deco_layer_name_search_cb,
        update=terrain_object_paint_layer_deco_layer_name_update_cb,
        search_options={'SORT'}
    )
    terrain_layer_id: StringProperty(name='Terrain Layer ID', default='', options={'HIDDEN'})
    deco_layer_id: StringProperty(name='Deco Layer ID', default='', options={'HIDDEN'})
    mute: BoolProperty(name='Mute', default=False)

    use_distance_noise: BoolProperty(name='Distance Noise', default=False)
    noise_type: EnumProperty(name='Noise Type', items=(
        ('PERLIN', 'Perlin', 'Perlin noise.'),
        ('WHITE', 'White', 'White noise.'),
    ), default='WHITE', update=terrain_object_update_cb)
    distance_noise_factor: FloatProperty(name='Distance Noise Factor', default=meters_to_unreal(0.5), subtype='DISTANCE', min=0.0)
    distance_noise_distortion: FloatProperty(name='Distance Noise Distortion', default=1.0, min=0.0)
    distance_noise_offset: FloatProperty(name='Distance Noise Offset', default=0.5, min=0.0, max=1.0, subtype='FACTOR')


class BDK_PG_terrain_object(PropertyGroup):
    id: StringProperty(options={'HIDDEN'}, name='ID')
    object_type: EnumProperty(name='Object Type', items=(
        ('CURVE', 'Curve', '', 'CURVE_DATA', 0),
        ('MESH', 'Mesh', '', 'MESH_DATA', 1),
        ('EMPTY', 'Empty', '', 'EMPTY_DATA', 2),
    ), default='CURVE')
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'}, name='Terrain Info Object')
    node_tree: PointerProperty(type=NodeTree, options={'HIDDEN'}, name='Node Tree')
    object: PointerProperty(type=Object, name='Object')
    is_3d: BoolProperty(name='3D', default=False)
    paint_layers: CollectionProperty(name='Paint Components', type=BDK_PG_terrain_object_paint_layer)
    paint_layers_index: IntProperty()
    sculpt_layers: CollectionProperty(name='Sculpt Components', type=BDK_PG_terrain_object_sculpt_layer)
    sculpt_layers_index: IntProperty()
    # TODO: we probably need a "creation index" to use a stable tie-breaker for the sort order of the terrain objects.
    sort_order: IntProperty(name='Sort Order', default=0, description='The order in which the terrain objects are '
                                                                      'evaluated (lower values are evaluated first)',
                            update=terrain_object_sort_order_update_cb)


classes = (
    BDK_PG_terrain_object_paint_layer,
    BDK_PG_terrain_object_sculpt_layer,
    BDK_PG_terrain_object,
)
