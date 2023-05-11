from typing import List

from bpy.props import IntProperty, PointerProperty, CollectionProperty, FloatProperty, BoolProperty, StringProperty, \
    EnumProperty
from bpy.types import PropertyGroup, Object, NodeTree, Context

from .builder import update_terrain_object_geometry_node_group
from ...units import meters_to_unreal


def terrain_object_update_cb(self: 'BDK_PG_terrain_object_paint_component', context: Context):
    # We update the node group whe the operation is changed since we don't want to use drivers to control the
    # operation for performance reasons.
    update_terrain_object_geometry_node_group(self.terrain_object.bdk.terrain_object)


class BDK_PG_terrain_object_sculpt_component(PropertyGroup):
    name: StringProperty(name='Name', default='Sculpt Layer')
    terrain_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    depth: FloatProperty(name='Depth', default=meters_to_unreal(0.5), subtype='DISTANCE')
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    use_noise: BoolProperty(name='Use Noise', default=False)
    noise_radius_factor: FloatProperty(name='Noise Radius Factor', default=1.0, subtype='FACTOR', min=0.0, soft_max=8.0)
    noise_strength: FloatProperty(name='Noise Strength', default=meters_to_unreal(0.25), subtype='DISTANCE', min=0.0, soft_max=meters_to_unreal(2.0))
    noise_distortion: FloatProperty(name='Noise Distortion', default=1.0, min=0.0)
    noise_roughness: FloatProperty(name='Noise Roughness', default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    mute: BoolProperty(name='Mute', default=False)
    interpolation_type: EnumProperty(name='Interpolation Type', items=(
        ('LINEAR', 'Linear', 'Linear interpolation between From Min and From Max values.'),
        ('STEPPED', 'Stepped', 'Stepped linear interpolation between From Min and From Max values.'),
        ('SMOOTHSTEP', 'Smooth Step', 'Smooth Hermite edge interpolation between From Min and From Max values.'),
        ('SMOOTHERSTEP', 'Smoother Step', 'Smoother Hermite edge interpolation between From Min and From Max values.'),
    ), default='LINEAR', update=terrain_object_update_cb)


def terrain_object_paint_component_terrain_layer_name_search_cb(self: 'BDK_PG_terrain_object_paint_component', context: Context, edit_text: str) -> List[str]:
    # Get a list of terrain layer names for the selected terrain info object.
    # TODO: This is insanely verbose.
    terrain_layers = self.terrain_object.bdk.terrain_object.terrain_info_object.bdk.terrain_info.terrain_layers
    return [terrain_layer.name for terrain_layer in terrain_layers]


def terrain_object_paint_component_terrain_layer_name_update_cb(self: 'BDK_PG_terrain_object_paint_component', context: Context):
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


class BDK_PG_terrain_object_paint_component(PropertyGroup):
    name: StringProperty(name='Name', default='Paint Layer')
    operation: EnumProperty(name='Operation', items=(
        ('ADD', 'Add', 'Add paint to the terrain layer.'),
        ('SUBTRACT', 'Subtract', 'Subtract paint from the terrain layer.'),
    ), default='ADD', update=terrain_object_update_cb)
    interpolation_type: EnumProperty(name='Interpolation Type', items=(
        ('LINEAR', 'Linear', 'Linear interpolation between From Min and From Max values.'),
        ('STEPPED', 'Stepped', 'Stepped linear interpolation between From Min and From Max values.'),
        ('SMOOTHSTEP', 'Smooth Step', 'Smooth Hermite edge interpolation between From Min and From Max values.'),
        ('SMOOTHERSTEP', 'Smoother Step', 'Smoother Hermite edge interpolation between From Min and From Max values.'),
    ), default='LINEAR', update=terrain_object_update_cb)
    index: IntProperty(options={'HIDDEN'})
    terrain_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', subtype='DISTANCE', default=meters_to_unreal(1.0), min=0.0)
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    terrain_layer_name: StringProperty(
        name='Terrain Layer',
        search=terrain_object_paint_component_terrain_layer_name_search_cb,
        update=terrain_object_paint_component_terrain_layer_name_update_cb,
        search_options={'SORT'}
    )
    terrain_layer_id: StringProperty(name='Terrain Layer ID', default='')
    mute: BoolProperty(name='Mute', default=False)

    use_distance_noise: BoolProperty(name='Distance Noise', default=False)
    distance_noise_factor: FloatProperty(name='Distance Noise Factor', default=meters_to_unreal(0.5), subtype='DISTANCE', min=0.0)
    distance_noise_distortion: FloatProperty(name='Distance Noise Distortion', default=1.0, min=0.0)
    distance_noise_offset: FloatProperty(name='Distance Noise Offset', default=0.5, min=0.0, max=1.0, subtype='FACTOR')


class BDK_PG_terrain_object(PropertyGroup):
    id: StringProperty(options={'HIDDEN'})
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    node_tree: PointerProperty(type=NodeTree, options={'HIDDEN'})
    object: PointerProperty(type=Object)
    is_3d: BoolProperty(name='3D', default=False)
    paint_components: CollectionProperty(name='Paint Components', type=BDK_PG_terrain_object_paint_component)
    paint_components_index: IntProperty()
    sculpt_components: CollectionProperty(name='Sculpt Components', type=BDK_PG_terrain_object_sculpt_component)
    sculpt_components_index: IntProperty()


classes = (
    BDK_PG_terrain_object_paint_component,
    BDK_PG_terrain_object_sculpt_component,
    BDK_PG_terrain_object,
)
