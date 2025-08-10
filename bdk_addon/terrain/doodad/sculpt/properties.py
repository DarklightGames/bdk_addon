from bpy.props import StringProperty, PointerProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty
from bpy.types import PropertyGroup, Object, Context

from ....constants import RADIUS_EPSILON
from ....data import map_range_interpolation_type_items
from ....property_group_helpers import CurveModifierMixin
from ....units import meters_to_unreal
from ..data import terrain_doodad_noise_type_items, terrain_doodad_geometry_source_items
from ..builder import ensure_terrain_info_modifiers

terrain_doodad_sculpt_layer_operation_items = (
    ('ADD', 'Add', '', 0),
    ('SET', 'Set', '', 1),
)


def terrain_doodad_sculpt_layer_geometry_source_update_cb(self, context):
    terrain_info = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info
    ensure_terrain_info_modifiers(context, terrain_info)


def terrain_doodad_sculpt_layer_scatter_layer_id_update_cb(self, context):
    terrain_info = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info
    ensure_terrain_info_modifiers(context, terrain_info)


def terrain_doodad_sculpt_layer_scatter_layer_name_update_cb(self, context):
    scatter_layers = self.terrain_doodad_object.bdk.terrain_doodad.scatter_layers
    for scatter_layer in scatter_layers:
        if scatter_layer.name == self.scatter_layer_name:
            self.scatter_layer_id = scatter_layer.id
            return
    self.scatter_layer_id = ''


def terrain_doodad_scatter_layer_name_search_cb(self, context: Context, edit_text: str):
    return [scatter_layer.name for scatter_layer in self.terrain_doodad_object.bdk.terrain_doodad.scatter_layers]


# TODO: make sure that when a scatter layer is deleted, the sculpt layer is updated to reflect that

class BDK_PG_terrain_doodad_sculpt_layer(PropertyGroup, CurveModifierMixin):
    id: StringProperty(name='ID', default='')
    name: StringProperty(name='Name', default='Sculpt Layer')
    operation: EnumProperty(name='Operation', items=terrain_doodad_sculpt_layer_operation_items)
    terrain_doodad_object: PointerProperty(type=Object, options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    mute: BoolProperty(name='Mute', default=False)
    radius: FloatProperty(name='Radius', default=meters_to_unreal(1.0), subtype='DISTANCE', min=RADIUS_EPSILON)
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE',
                                  min=RADIUS_EPSILON)
    depth: FloatProperty(name='Distance', default=meters_to_unreal(0.5), subtype='DISTANCE')
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    use_noise: BoolProperty(name='Use Noise', default=False)
    noise_type: EnumProperty(name='Noise Type', items=terrain_doodad_noise_type_items, default='WHITE')
    noise_radius_factor: FloatProperty(name='Noise Radius Factor', default=1.0, subtype='FACTOR', min=RADIUS_EPSILON,
                                       soft_max=2.0)
    noise_strength: FloatProperty(name='Noise Strength', default=0.125, subtype='FACTOR', min=0.0, soft_max=1.0)
    perlin_noise_distortion: FloatProperty(name='Noise Distortion', default=1.0, min=0.0)
    perlin_noise_roughness: FloatProperty(name='Noise Roughness', default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    perlin_noise_scale: FloatProperty(name='Noise Scale', default=1.0, min=0.0)
    perlin_noise_lacunarity: FloatProperty(name='Noise Lacunarity', default=2.0, min=0.0)
    perlin_noise_detail: FloatProperty(name='Noise Detail', default=8.0, min=0.0)
    interpolation_type: EnumProperty(name='Interpolation Type', items=map_range_interpolation_type_items,
                                     default='LINEAR')

    geometry_source: EnumProperty(name='Geometry Source', items=terrain_doodad_geometry_source_items,
                                  update=terrain_doodad_sculpt_layer_geometry_source_update_cb)

    element_mode: EnumProperty(name='Element Mode', items=(
        ('VERTEX', 'Vertex', '', 'VERTEXSEL', 0),
        ('EDGE', 'Edge', '', 'EDGESEL', 1),
        ('FACE', 'Face', '', 'FACESEL', 2)), default='FACE',
                               description='The element of geometry that will be used to determine the area of effect')

    scatter_layer_id: StringProperty(name='Scatter Layer ID', default='', options={'HIDDEN'},
                                     update=terrain_doodad_sculpt_layer_scatter_layer_id_update_cb)
    scatter_layer_name: StringProperty(name='Scatter Layer Name', default='', options={'HIDDEN'},
                                       update=terrain_doodad_sculpt_layer_scatter_layer_name_update_cb,
                                       search=terrain_doodad_scatter_layer_name_search_cb)

    frozen_attribute_id: StringProperty(name='Frozen Attribute ID', default='')


classes = (
    BDK_PG_terrain_doodad_sculpt_layer,
)
