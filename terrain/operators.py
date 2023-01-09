import math
import typing
import numpy as np

import bpy.types
import bmesh
from bpy.props import IntProperty, FloatProperty, FloatVectorProperty, BoolProperty, StringProperty, PointerProperty, \
    EnumProperty, CollectionProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList, Context, UILayout, AnyType, Mesh, Material, Object


def build_terrain_material(active_object: Object):
    TerrainMaterialBuilder().build(active_object)


class BDK_PG_TerrainLayerPropertyGroup(PropertyGroup):
    name: StringProperty(name='Name')
    u_scale: FloatProperty(name='UScale')
    v_scale: FloatProperty(name='VScale')
    texture_rotation: FloatProperty(name='TextureRotation', subtype='ANGLE')
    color_attribute_name: StringProperty(options={'HIDDEN'})


class BDK_PG_TerrainInfoPropertyGroup(PropertyGroup):
    terrain_scale: FloatProperty(name='TerrainScale')
    terrain_layers: CollectionProperty(name='TerrainLayers', type=BDK_PG_TerrainLayerPropertyGroup)
    terrain_layers_index: IntProperty(options={'HIDDEN'})


class BDK_UL_TerrainLayersUIList(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        row.label(text=str(getattr(item, 'name')), icon='VPAINT_HLT')


class BDK_PT_TerrainLayersPanel(Panel):
    bl_idname = 'BDK_PT_TerrainLayersPanel'
    bl_label = 'Terrain Layers'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'object'

    @classmethod
    def poll(cls, context: Context):
        active_object = context.active_object
        if active_object is not None and active_object.type == 'MESH':
            # TODO: imbue the thing with the knowledge of whether or not it is a TerrainInfo ojbect
            return True
        return False

    def draw(self, context):
        active_object = context.active_object
        terrain_info = getattr(active_object, 'terrain_info')

        row = self.layout.row()
        row.template_list('BDK_UL_TerrainLayersUIList', '', terrain_info, 'terrain_layers', terrain_info, 'terrain_layers_index')

        col = row.column(align=True)
        col.operator(BDK_OT_TerrainLayerAdd.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_TerrainLayerRemove.bl_idname, icon='REMOVE', text='')
        col.separator()
        operator = col.operator(BDK_OT_TerrainLayerMove.bl_idname, icon='TRIA_UP', text='')
        operator.direction = 'UP'
        operator = col.operator(BDK_OT_TerrainLayerMove.bl_idname, icon='TRIA_DOWN', text='')
        operator.direction = 'DOWN'


class BDK_OT_TerrainLayerRemove(Operator):
    bl_idname = 'bdk.terrain_layer_remove'
    bl_label = 'Remove Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        active_object = context.active_object
        terrain_info = getattr(active_object, 'terrain_info')
        index = getattr(terrain_info, 'terrain_layers_index')
        return index >= 0

    def execute(self, context: Context):
        active_object = context.active_object
        terrain_info = getattr(active_object, 'terrain_info')
        terrain_layers: typing.List[BDK_PG_TerrainLayerPropertyGroup] = getattr(terrain_info, 'terrain_layers')
        index = getattr(terrain_info, 'terrain_layers_index')
        if index >= 0:
            # Remove color attribute.
            terrain_object = context.active_object
            mesh_data = typing.cast(Mesh, terrain_object.data)
            color_attribute_name = terrain_layers[index].color_attribute_name
            if color_attribute_name in mesh_data.color_attributes:
                color_attribute = mesh_data.color_attributes[color_attribute_name]
                mesh_data.color_attributes.remove(color_attribute)

            terrain_layers.remove(index)

            setattr(terrain_info, 'terrain_layers_index', min(len(terrain_layers) - 2, index))

            build_terrain_material(terrain_object)

        return {'FINISHED'}


class BDK_OT_TerrainLayerMove(Operator):
    bl_idname = 'bdk.terrain_layer_move'
    bl_label = 'Move Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name='Direction',
        options=set(),
        items=(
            ('UP', 'Up', 'The selected terrain layer will be moved up'),
            ('DOWN', 'Down', 'The selected terrain layer will be moved down')
        ),
    )

    def execute(self, context: Context):
        active_object = context.active_object
        terrain_info = getattr(active_object, 'terrain_info')
        terrain_layers = getattr(terrain_info, 'terrain_layers')
        index = getattr(terrain_info, 'terrain_layers_index')
        if self.direction == 'UP' and index > 0:
            terrain_layers.move(index, index - 1)
            setattr(terrain_info, 'terrain_layers_index', index - 1)
            build_terrain_material(active_object)
        elif self.direction == 'DOWN' and index < len(terrain_layers) - 1:
            terrain_layers.move(index, index + 1)
            setattr(terrain_info, 'terrain_layers_index', index + 1)
            build_terrain_material(active_object)
        return {'FINISHED'}


class BDK_OT_TerrainLayerAdd(Operator):
    bl_idname = 'bdk.terrain_layer_add'
    bl_label = 'Add Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name='Name')
    alpha_fill: FloatVectorProperty(name='Alpha Fill', subtype='COLOR', min=0.0, max=1.0, size=4, default=(0.0, 0.0, 0.0, 1.0))
    u_scale: FloatProperty(name='UScale', default=32.0)
    v_scale: FloatProperty(name='VScale', default=32.0)
    texture_rotation: FloatProperty(name='TextureRotation', default=0.0, subtype='ANGLE')

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        if self.name == '':
            self.report({'ERROR'}, 'Terrain layers must have a name')
            return {'CANCELLED'}

        active_object = context.active_object
        terrain_info = getattr(active_object, 'terrain_info')
        terrain_layers = getattr(terrain_info, 'terrain_layers')

        if self.name in map(lambda x: x.name, terrain_layers):
            self.report({'ERROR'}, f'There is already a terrain layer named \'{self.name}\'')
            return {'CANCELLED'}

        terrain_layer: BDK_PG_TerrainLayerPropertyGroup = terrain_layers.add()
        terrain_layer.name = self.name
        terrain_layer.u_scale = self.u_scale
        terrain_layer.v_scale = self.v_scale

        for region in filter(lambda r: r.type == 'WINDOW', bpy.context.area.regions):
            region.tag_redraw()

        terrain_object = context.active_object
        mesh_data = typing.cast(Mesh, terrain_object.data)

        # Create the associated color attribute.
        color_attribute = mesh_data.color_attributes.new(self.name, type='FLOAT_COLOR', domain='POINT')

        vertex_count = len(color_attribute.data)

        color_data = np.ndarray(shape=(vertex_count, 4), dtype=float)
        color_data[:] = tuple(self.alpha_fill)

        color_attribute.data.foreach_set('color', color_data.flatten())
        terrain_layer.color_attribute_name = color_attribute.name

        # Regenerate the material.
        build_terrain_material(active_object)

        return {'FINISHED'}


class TerrainMaterialBuilder:
    def __init__(self):
        pass

    @staticmethod
    def _build_or_get_terrain_layer_uv_group_node() -> bpy.types.NodeTree:
        group_name = 'BDK TerrainLayerUV'

        if group_name in bpy.data.node_groups:
            node_tree = bpy.data.node_groups[group_name]
        else:
            node_tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

        node_tree.nodes.clear()
        node_tree.inputs.clear()
        node_tree.inputs.new('NodeSocketFloat', 'UScale')
        node_tree.inputs.new('NodeSocketFloat', 'VScale')
        node_tree.inputs.new('NodeSocketFloat', 'TextureRotation')
        node_tree.inputs.new('NodeSocketFloat', 'TerrainScale')
        node_tree.outputs.clear()
        node_tree.outputs.new('NodeSocketVector', 'UV')

        group_input_node = node_tree.nodes.new('NodeGroupInput')

        # UScale Multiply
        u_multiply_node = node_tree.nodes.new('ShaderNodeMath')
        u_multiply_node.operation = 'MULTIPLY'

        node_tree.links.new(u_multiply_node.inputs[0], group_input_node.outputs['UScale'])
        node_tree.links.new(u_multiply_node.inputs[1], group_input_node.outputs['TerrainScale'])

        # VScale Multiply
        v_multiply_node = node_tree.nodes.new('ShaderNodeMath')
        v_multiply_node.operation = 'MULTIPLY'

        node_tree.links.new(v_multiply_node.inputs[0], group_input_node.outputs['VScale'])
        node_tree.links.new(v_multiply_node.inputs[1], group_input_node.outputs['TerrainScale'])

        # Combine XYZ
        combine_xyz_node = node_tree.nodes.new('ShaderNodeCombineXYZ')

        node_tree.links.new(combine_xyz_node.inputs['X'], u_multiply_node.outputs['Value'])
        node_tree.links.new(combine_xyz_node.inputs['Y'], v_multiply_node.outputs['Value'])

        # Geometry
        geometry_node = node_tree.nodes.new('ShaderNodeNewGeometry')

        # Divide
        divide_node = node_tree.nodes.new('ShaderNodeVectorMath')
        divide_node.operation = 'DIVIDE'

        node_tree.links.new(divide_node.inputs[0], geometry_node.outputs['Position'])
        node_tree.links.new(divide_node.inputs[1], combine_xyz_node.outputs['Vector'])

        # Vector Rotate
        rotate_node = node_tree.nodes.new('ShaderNodeVectorRotate')
        rotate_node.rotation_type = 'Z_AXIS'

        node_tree.links.new(rotate_node.inputs['Vector'], divide_node.outputs['Vector'])
        node_tree.links.new(rotate_node.inputs['Angle'], group_input_node.outputs['TextureRotation'])

        # Group Output
        group_output_node = node_tree.nodes.new('NodeGroupOutput')

        node_tree.links.new(group_output_node.inputs['UV'], rotate_node.outputs['Vector'])

        return node_tree

    def build(self, terrain_info_object: bpy.types.Object):
        terrain_info = getattr(terrain_info_object, 'terrain_info')
        terrain_layers = getattr(terrain_info, 'terrain_layers')

        mesh_data = typing.cast(Mesh, terrain_info_object.data)
        material = mesh_data.materials[0]
        node_tree = material.node_tree
        node_tree.nodes.clear()

        last_shader_socket = None

        for terrain_layer in terrain_layers:
            terrain_layer_uv_node = node_tree.nodes.new('ShaderNodeGroup')
            terrain_layer_uv_node.node_tree = self._build_or_get_terrain_layer_uv_group_node()

            terrain_layer_uv_node.inputs['UScale'].default_value = terrain_layer.u_scale
            terrain_layer_uv_node.inputs['VScale'].default_value = terrain_layer.v_scale
            terrain_layer_uv_node.inputs['TextureRotation'].default_value = terrain_layer.texture_rotation
            terrain_layer_uv_node.inputs['TerrainScale'].default_value = terrain_info.terrain_scale

            image_node = node_tree.nodes.new('ShaderNodeTexImage')
            # TODO: fill this in with something eventually (or better yet, recreate/reuse the materials!)

            color_attribute_node = node_tree.nodes.new('ShaderNodeVertexColor')
            color_attribute_node.layer_name = terrain_layer.color_attribute_name

            diffuse_node = node_tree.nodes.new('ShaderNodeBsdfDiffuse')
            mix_shader_node = node_tree.nodes.new('ShaderNodeMixShader')

            node_tree.links.new(image_node.inputs['Vector'], terrain_layer_uv_node.outputs['UV'])

            node_tree.links.new(diffuse_node.inputs['Color'], image_node.outputs['Color'])
            node_tree.links.new(mix_shader_node.inputs['Fac'], color_attribute_node.outputs['Color'])

            if last_shader_socket is not None:
                node_tree.links.new(mix_shader_node.inputs[1], last_shader_socket)

            node_tree.links.new(mix_shader_node.inputs[2], diffuse_node.outputs['BSDF'])

            last_shader_socket = mix_shader_node.outputs['Shader']

        output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')

        if last_shader_socket is not None:
            node_tree.links.new(output_node.inputs['Surface'], last_shader_socket)


class BDK_OT_TerrainInfoAdd(Operator):

    bl_idname = 'bdk.create_terrain_info'
    bl_label = 'Create TerrainInfo'
    bl_options = {'REGISTER', 'UNDO'}

    resolution: IntProperty(name='Resolution', default=512, min=2, max=512)
    size: FloatProperty(name='Size', default=1000*60.352, subtype='DISTANCE')
    location: FloatVectorProperty(name='Location', unit='LENGTH')
    lock_transforms: BoolProperty(name='Lock Transforms', default=True)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return True

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        return self.execute(context)

    def execute(self, context: bpy.types.Context):

        step = float(self.size) / self.resolution
        size_half = 0.5 * self.size

        bm = bmesh.new()

        # Vertices
        for y in range(self.resolution + 1):
            for x in range(self.resolution + 1):
                co = (step * x - size_half, step * y - size_half, 0.0)
                bm.verts.new(co)

        bm.verts.ensure_lookup_table()

        # Faces
        z = 0
        indices = [0, 1, self.resolution + 2, self.resolution + 1]
        for y in range(self.resolution):
            for x in range(self.resolution):
                face = bm.faces.new(tuple([bm.verts[z + x] for x in indices]))
                face.smooth = True
                z += 1
            z += 1

        mesh_data = bpy.data.meshes.new('TerrainInfo')
        bm.to_mesh(mesh_data)
        del bm

        mesh_object = bpy.data.objects.new('TerrainInfo', mesh_data)
        mesh_object.location = self.location

        if self.lock_transforms:
            # Lock transforms so that levelers don't accidentally move the terrain.
            mesh_object.lock_location = [True] * 3
            mesh_object.lock_scale = [True] * 3
            mesh_object.lock_rotation = [True] * 3
            mesh_object.lock_rotation_w = True
            mesh_object.lock_rotations_4d = True

        # Custom properties
        terrain_info = getattr(mesh_object, 'terrain_info')
        setattr(terrain_info, 'terrain_scale', self.size / self.resolution)

        context.scene.collection.objects.link(mesh_object)

        return {'FINISHED'}


classes = (
    BDK_OT_TerrainInfoAdd,
    BDK_OT_TerrainLayerAdd,
    BDK_OT_TerrainLayerRemove,
    BDK_OT_TerrainLayerMove,
    BDK_PG_TerrainLayerPropertyGroup,
    BDK_PG_TerrainInfoPropertyGroup,
    BDK_PT_TerrainLayersPanel,
    BDK_UL_TerrainLayersUIList,
)
