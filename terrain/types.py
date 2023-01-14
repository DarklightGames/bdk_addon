from bpy.types import PropertyGroup, Object, Image, Context, Mesh
from bpy.props import PointerProperty, BoolProperty, FloatProperty, CollectionProperty, IntProperty, StringProperty
from .builder import TerrainMaterialBuilder


def on_material_update(self, _: Context):
    TerrainMaterialBuilder().build(self.terrain_info_object)


class BDK_PG_TerrainLayerPropertyGroup(PropertyGroup):
    name: StringProperty(name='Name', default='TerrainLayer')
    u_scale: FloatProperty(name='UScale', default=2.0)
    v_scale: FloatProperty(name='VScale', default=2.0)
    texture_rotation: FloatProperty(name='TextureRotation', subtype='ANGLE')
    image: PointerProperty(name='Image', type=Image, update=on_material_update)
    color_attribute_name: StringProperty(options={'HIDDEN'})
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'})
    is_visible: BoolProperty(options={'HIDDEN'}, default=True)


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
    mesh_data.color_attributes.active_color_index = color_attribute_index


class BDK_PG_TerrainInfoPropertyGroup(PropertyGroup):
    terrain_info_object: PointerProperty(type=Object)
    is_terrain_info: BoolProperty(default=False, options={'HIDDEN'})
    terrain_scale: FloatProperty(name='TerrainScale')
    terrain_layers: CollectionProperty(name='TerrainLayers', type=BDK_PG_TerrainLayerPropertyGroup)
    terrain_layers_index: IntProperty(options={'HIDDEN'}, update=on_terrain_layer_index_update)


classes = (
    BDK_PG_TerrainLayerPropertyGroup,
    BDK_PG_TerrainInfoPropertyGroup,
)
