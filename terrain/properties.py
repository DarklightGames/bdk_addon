from typing import cast

import bpy.ops
from bpy.types import PropertyGroup, Object, Context, Mesh, Material
from bpy.props import PointerProperty, BoolProperty, FloatProperty, CollectionProperty, IntProperty, StringProperty, \
    FloatVectorProperty, EnumProperty

from ..helpers import is_bdk_material, is_bdk_static_mesh_actor
from .builder import build_terrain_material


def on_material_update(self, _: Context):
    build_terrain_material(self.terrain_info_object)


def material_poll(_: Context, material: Material) -> bool:
    return is_bdk_material(material)


class BDK_PG_TerrainLayerPropertyGroup(PropertyGroup):
    name: StringProperty(name='Name', default='TerrainLayer')
    u_scale: FloatProperty(name='UScale', default=2.0)
    v_scale: FloatProperty(name='VScale', default=2.0)
    texture_rotation: FloatProperty(name='TextureRotation', subtype='ANGLE')
    material: PointerProperty(name='Material', type=Material, update=on_material_update, poll=material_poll)
    color_attribute_name: StringProperty(options={'HIDDEN'})
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    is_visible: BoolProperty(options={'HIDDEN'}, default=True)


def on_deco_layer_index_update(self: 'BDK_PG_TerrainInfoPropertyGroup', _: Context):
    if not self.terrain_info_object or self.terrain_info_object.type != 'MESH':
        return
    mesh_data: Mesh = self.terrain_info_object.data
    deco_layer: BDK_PG_TerrainDecoLayerPropertyGroup = self.deco_layers[self.deco_layers_index]
    color_attribute_index = -1
    for i, color_attribute in enumerate(mesh_data.color_attributes):
        if color_attribute.name == deco_layer.id:
            color_attribute_index = i
            break
    if mesh_data.color_attributes.active_color_index != color_attribute_index:
        mesh_data.color_attributes.active_color_index = color_attribute_index
        # Push an undo state.
        # This is needed so that if the user selects a new layer, does some operation, and then does an undo,
        # it won't wipe out the active painting layer.
        # TODO: replace this with an actual operator with an UNDO_GROUPED option flag so that we consolidate repeated changes into one undo step instead of polluting the undo stack.
        bpy.ops.ed.undo_push(message=f"Select '{deco_layer.name}' DecoLayer")


def on_static_mesh_update(self: 'BDK_PG_TerrainDecoLayerPropertyGroup', context: Context):
    if self.object is None:
        return
    deco_layer_object = cast(Object, self.object)
    node_group = deco_layer_object.modifiers[self.id].node_group
    # TODO: this is brittle but will work for now
    object_info_node = node_group.nodes['Object Info.001']
    object_info_node.inputs[0].default_value = self.static_mesh


def static_mesh_poll(_: Context, obj: Object) -> bool:
    return is_bdk_static_mesh_actor(obj)


empty_set = set()


class BDK_PG_TerrainDecoLayerPropertyGroup(PropertyGroup):
    align_to_terrain: BoolProperty(name='Align To Terrain', default=False, options=empty_set)
    density_multiplier_max: FloatProperty('Density Multiplier Max', min=0.0, max=1.0, default=0.1, options=empty_set)
    density_multiplier_min: FloatProperty('Density Multiplier Min', min=0.0, max=1.0, default=0.1, options=empty_set)
    detail_mode: EnumProperty(name='Detail Mode', items=[
        ('DM_Low', 'Low', '',),
        ('DM_High', 'High', ''),
        ('DM_SuperHigh', 'Super High', ''),
    ], options=empty_set)
    fadeout_radius_max: FloatProperty(name='Fadeout Radius Max', options=empty_set, subtype='DISTANCE')
    fadeout_radius_min: FloatProperty(name='Fadeout Radius Min', options=empty_set, subtype='DISTANCE')
    force_draw: BoolProperty(name='Force Draw', default=False, options=empty_set)
    id: StringProperty(options={'HIDDEN'})
    is_visible: BoolProperty(options={'HIDDEN'}, default=True)
    max_per_quad: IntProperty(name='Max Per Quad', default=1, min=1, max=4, options=empty_set)
    name: StringProperty(name='Name', default='DecoLayer', options=empty_set)
    object: PointerProperty(type=Object, options={'HIDDEN'})
    offset: FloatProperty(name='Offset', options=empty_set, subtype='DISTANCE')
    random_yaw: BoolProperty(name='Random Yaw', default=True, options=empty_set)
    scale_multiplier_max: FloatVectorProperty('Scale Multiplier Max', min=0.0, max=1.0, default=[1, 1, 1], options=empty_set, subtype='XYZ')
    scale_multiplier_min: FloatVectorProperty('Scale Multiplier Min', min=0.0, max=1.0, default=[1, 1, 1], options=empty_set, subtype='XYZ')
    seed: IntProperty(name='Seed', options=empty_set)
    show_on_invisible_terrain: BoolProperty(name='Show On Invisible Terrain', default=False, options=empty_set)
    show_on_terrain: BoolProperty(name='Show On Terrain', default=True, options=empty_set)
    draw_order: EnumProperty(name='Sort Order', options=empty_set, items=[
        ('SORT_NoSort', 'No Sort', ''),
        ('SORT_BackToFront', 'Back To Front', ''),
        ('SORT_FrontToBack', 'Front To Back', ''),
    ])
    static_mesh: PointerProperty(name='Static Mesh', type=Object, update=on_static_mesh_update, poll=static_mesh_poll, options=empty_set)
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})


def on_terrain_layer_index_update(self: 'BDK_PG_TerrainInfoPropertyGroup', _: Context):
    if not self.terrain_info_object or self.terrain_info_object.type != 'MESH':
        return
    mesh_data: Mesh = self.terrain_info_object.data
    terrain_layer: BDK_PG_TerrainLayerPropertyGroup = self.terrain_layers[self.terrain_layers_index]
    color_attribute_index = -1
    for i, color_attribute in enumerate(mesh_data.color_attributes):
        if color_attribute.name == terrain_layer.color_attribute_name:
            color_attribute_index = i
            break
    if mesh_data.color_attributes.active_color_index != color_attribute_index:
        mesh_data.color_attributes.active_color_index = color_attribute_index
        # Push an undo state.
        # This is needed so that if the user selects a new layer, does some operation, and then does an undo,
        # it won't wipe out the active painting layer.
        bpy.ops.ed.undo_push(message=f"Select '{terrain_layer.name}' Layer")


class BDK_PG_TerrainInfoPropertyGroup(PropertyGroup):
    terrain_info_object: PointerProperty(type=Object)
    is_terrain_info: BoolProperty(default=False, options={'HIDDEN'})
    terrain_scale: FloatProperty(name='TerrainScale')
    terrain_layers: CollectionProperty(name='TerrainLayers', type=BDK_PG_TerrainLayerPropertyGroup)
    terrain_layers_index: IntProperty(options={'HIDDEN'}, update=on_terrain_layer_index_update)
    deco_layers: CollectionProperty(name='DecoLayers', type=BDK_PG_TerrainDecoLayerPropertyGroup)
    deco_layers_index: IntProperty(options={'HIDDEN'}, update=on_deco_layer_index_update)
    x_size: IntProperty(options={'HIDDEN'})
    y_size: IntProperty(options={'HIDDEN'})


classes = (
    BDK_PG_TerrainDecoLayerPropertyGroup,
    BDK_PG_TerrainLayerPropertyGroup,
    BDK_PG_TerrainInfoPropertyGroup,
)
