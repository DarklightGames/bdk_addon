from bpy.props import IntProperty, PointerProperty, CollectionProperty, FloatProperty, BoolProperty, StringProperty
from bpy.types import PropertyGroup, Object

from ...units import meters_to_unreal


class BDK_PG_terrain_object_sculpt_component(PropertyGroup):
    name: StringProperty(name='Name', default='Sculpt Component')
    terrain_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    radius: FloatProperty(name='Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=0.0)
    depth: FloatProperty(name='Depth', default=meters_to_unreal(0.5), subtype='DISTANCE')
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    use_noise: BoolProperty(name='Use Noise', default=False)
    noise_radius_factor: FloatProperty(name='Noise Radius Factor', default=1.0, subtype='FACTOR', min=0.0, soft_max=8.0)
    noise_strength: FloatProperty(name='Noise Strength', default=1.0, subtype='FACTOR', min=0.0)
    noise_distortion: FloatProperty(name='Noise Distortion', default=1.0, min=0.0)
    noise_roughness: FloatProperty(name='Noise Roughness', default=0.5, min=0.0, max=1.0, subtype='FACTOR')


class BDK_PG_terrain_object_paint_component(PropertyGroup):
    inner_radius: FloatProperty(name='Radius', default=1.0, subtype='DISTANCE')
    slope_radius: FloatProperty(name='Falloff Radius', default=1.0, subtype='DISTANCE')


class BDK_PG_terrain_object(PropertyGroup):
    terrain_info_object: PointerProperty(type=Object)
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
