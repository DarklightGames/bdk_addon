from typing import List

from bpy.props import IntProperty, BoolProperty, FloatProperty, PointerProperty, StringProperty, EnumProperty
from bpy.types import Context, PropertyGroup, Object

from ....constants import RADIUS_EPSILON
from ....data import map_range_interpolation_type_items
from ....property_group_helpers import CurveModifierMixin
from ....units import meters_to_unreal
from ..builder import ensure_terrain_info_modifiers
from ..data import terrain_doodad_noise_type_items, terrain_doodad_operation_items, terrain_doodad_geometry_source_items


def terrain_doodad_paint_layer_paint_layer_name_search_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context,
                                                          edit_text: str) -> list[str]:
    # Get a list of terrain layer names for the selected terrain info object.
    # TODO: This is insanely verbose.
    paint_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.paint_layers
    return [paint_layer.name for paint_layer in paint_layers]


def terrain_doodad_paint_layer_deco_layer_name_search_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context,
                                                         edit_text: str) -> list[str]:
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

    terrain_info = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info
    ensure_terrain_info_modifiers(context, terrain_info)


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

    terrain_info = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info
    ensure_terrain_info_modifiers(context, terrain_info)


def terrain_doodad_paint_layer_geometry_source_update_cb(self, context):
    terrain_info = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info
    ensure_terrain_info_modifiers(context, terrain_info)


def terrain_doodad_paint_layer_scatter_layer_id_update_cb(self, context):
    terrain_info = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info
    ensure_terrain_info_modifiers(context, terrain_info)


def terrain_doodad_paint_layer_scatter_layer_name_update_cb(self, context):
    scatter_layers = self.terrain_doodad_object.bdk.terrain_doodad.scatter_layers
    for scatter_layer in scatter_layers:
        if scatter_layer.name == self.scatter_layer_name:
            self.scatter_layer_id = scatter_layer.id
            return
    self.scatter_layer_id = ''


def terrain_doodad_scatter_layer_name_search_cb(self, context: Context, edit_text: str):
    return [scatter_layer.name for scatter_layer in self.terrain_doodad_object.bdk.terrain_doodad.scatter_layers]


class BDK_PG_terrain_doodad_paint_layer(PropertyGroup, CurveModifierMixin):
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Paint Layer')
    operation: EnumProperty(name='Operation', items=terrain_doodad_operation_items, default='ADD')
    interpolation_type: EnumProperty(
        name='Interpolation Type', items=map_range_interpolation_type_items, default='LINEAR')
    index: IntProperty(options={'HIDDEN'})
    terrain_doodad_object: PointerProperty(type=Object, options={'HIDDEN'})
    radius: FloatProperty(name='Radius', subtype='DISTANCE', default=meters_to_unreal(1.0), min=RADIUS_EPSILON)
    falloff_radius: FloatProperty(name='Falloff Radius', default=meters_to_unreal(1.0), subtype='DISTANCE',
                                  min=RADIUS_EPSILON)
    strength: FloatProperty(name='Strength', default=1.0, subtype='FACTOR', min=0.0, max=1.0)
    layer_type: EnumProperty(name='Layer Type', items=(
        ('PAINT', 'Paint', 'Paint layer'),
        ('DECO', 'Deco', 'Deco layer'),
        ('ATTRIBUTE', 'Attribute', 'Attribute layer')
    ), default='PAINT')
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
    # TODO: make sure that this is now using a switch node
    noise_type: EnumProperty(name='Noise Type', items=terrain_doodad_noise_type_items, default='WHITE')
    distance_noise_factor: FloatProperty(
        name='Distance Noise Factor', default=meters_to_unreal(0.5), subtype='DISTANCE', min=0.0)
    distance_noise_distortion: FloatProperty(name='Distance Noise Distortion', default=1.0, min=0.0)
    distance_noise_offset: FloatProperty(name='Distance Noise Offset', default=0.5, min=0.0, max=1.0, subtype='FACTOR')

    # Geometry Source
    geometry_source: EnumProperty(name='Geometry Source', items=terrain_doodad_geometry_source_items,
                                  update=terrain_doodad_paint_layer_geometry_source_update_cb)
    element_mode: EnumProperty(name='Element Mode', items=(
        ('VERTEX', 'Vertex', '', 'VERTEXSEL', 0),
        ('EDGE', 'Edge', '', 'EDGESEL', 1),
        ('FACE', 'Face', '', 'FACESEL', 2)), default='FACE',
                               description='The element of geometry that will be used to determine the area of effect.')
    scatter_layer_id: StringProperty(name='Scatter Layer ID', default='', options={'HIDDEN'},
                                     update=terrain_doodad_paint_layer_scatter_layer_id_update_cb)
    scatter_layer_name: StringProperty(name='Scatter Layer Name', default='', options={'HIDDEN'},
                                       update=terrain_doodad_paint_layer_scatter_layer_name_update_cb,
                                       search=terrain_doodad_scatter_layer_name_search_cb)

    frozen_attribute_id: StringProperty(name='Frozen Attribute ID', default='', options={'HIDDEN'})


classes = (
    BDK_PG_terrain_doodad_paint_layer,
)
