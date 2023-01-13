import numpy as np
import uuid
import re
import bpy.types
import bmesh
from typing import Tuple, cast, Union
from bpy.props import IntProperty, FloatProperty, FloatVectorProperty, BoolProperty, StringProperty, PointerProperty, \
    EnumProperty, CollectionProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList, Context, UILayout, AnyType, Mesh, Object, Image


def build_terrain_material(active_object: Object):
    TerrainMaterialBuilder().build(active_object)


def on_material_update(self, _: Context):
    TerrainMaterialBuilder().build(self.terrain_info_object)


class BDK_PG_TerrainLayerPropertyGroup(PropertyGroup):
    name: StringProperty(name='Name')
    u_scale: FloatProperty(name='UScale')
    v_scale: FloatProperty(name='VScale')
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
    terrain_info_object: PointerProperty(type=bpy.types.Object)
    is_terrain_info: BoolProperty(default=False, options={'HIDDEN'})
    terrain_scale: FloatProperty(name='TerrainScale')
    terrain_layers: CollectionProperty(name='TerrainLayers', type=BDK_PG_TerrainLayerPropertyGroup)
    terrain_layers_index: IntProperty(options={'HIDDEN'}, update=on_terrain_layer_index_update)


class BDK_UL_TerrainLayersUIList(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()

        icon = row.icon(item.image) if item.image else None
        if icon:
            row.prop(item, 'name', text='', emboss=False, icon_value=icon)
        else:
            row.prop(item, 'name', text='', emboss=False, icon='IMAGE')

        row.prop(item, 'is_visible', icon='HIDE_OFF' if item.is_visible else 'HIDE_ON', text='', emboss=False)


class BDK_PT_TerrainLayersPanel(Panel):
    bl_idname = 'BDK_PT_TerrainLayersPanel'
    bl_label = 'Terrain Layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"

    @classmethod
    def poll(cls, context: Context):
        active_object = context.active_object
        return active_object and active_object.terrain_info.is_terrain_info

    def draw(self, context: Context):
        active_object = context.active_object
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')
        terrain_layers = terrain_info.terrain_layers
        terrain_layers_index = terrain_info.terrain_layers_index

        row = self.layout.row()
        row.template_list('BDK_UL_TerrainLayersUIList', '', terrain_info, 'terrain_layers', terrain_info,
                          'terrain_layers_index', sort_lock=True)

        col = row.column(align=True)
        col.operator(BDK_OT_TerrainLayerAdd.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_TerrainLayerRemove.bl_idname, icon='REMOVE', text='')
        col.separator()
        operator = col.operator(BDK_OT_TerrainLayerMove.bl_idname, icon='TRIA_UP', text='')
        operator.direction = 'UP'
        operator = col.operator(BDK_OT_TerrainLayerMove.bl_idname, icon='TRIA_DOWN', text='')
        operator.direction = 'DOWN'

        col.separator()

        has_terrain_layer_selected = 0 <= terrain_layers_index < len(terrain_layers)

        if has_terrain_layer_selected:
            col.separator()

            row = self.layout.row(align=True)

            terrain_layer = terrain_layers[terrain_layers_index]

            row.prop(terrain_layer, 'image')

            row = self.layout.row(align=True)

            row.label(text='Scale')
            col = row.column(align=True)
            col.prop(terrain_layer, 'u_scale', text='U')
            col.prop(terrain_layer, 'v_scale', text='V')

            row = self.layout.row(align=True)
            row.label(text='Rotation')
            row.prop(terrain_layer, 'texture_rotation', text='')


class BDK_OT_TerrainLayerRemove(Operator):
    bl_idname = 'bdk.terrain_layer_remove'
    bl_label = 'Remove Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        active_object = context.active_object
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')
        return terrain_info.terrain_layers_index >= 0

    def execute(self, context: Context):
        active_object = context.active_object

        if active_object is None:
            return {'CANCELLED'}

        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')
        terrain_layers = terrain_info.terrain_layers
        terrain_layers_index = terrain_info.terrain_layers_index

        if terrain_layers_index >= 0:
            # Remove color attribute.
            terrain_object = context.active_object
            mesh_data = cast(Mesh, terrain_object.data)
            color_attribute_name = terrain_layers[terrain_layers_index].color_attribute_name
            if color_attribute_name in mesh_data.color_attributes:
                color_attribute = mesh_data.color_attributes[color_attribute_name]
                mesh_data.color_attributes.remove(color_attribute)

            terrain_layers.remove(terrain_layers_index)

            terrain_info.terrain_layers_index = min(len(terrain_layers) - 2, terrain_layers_index)

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
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(active_object, 'terrain_info')
        terrain_layers = terrain_info.terrain_layers
        terrain_layers_index = terrain_info.terrain_layers_index

        if self.direction == 'UP' and terrain_layers_index > 0:
            terrain_layers.move(terrain_layers_index, terrain_layers_index - 1)
            terrain_info.terrain_layers_index -= 1
            build_terrain_material(active_object)
        elif self.direction == 'DOWN' and terrain_layers_index < len(terrain_layers) - 1:
            terrain_info.terrain_layers_index += 1
            build_terrain_material(active_object)

        return {'FINISHED'}


def add_terrain_layer(terrain_info_object: Object, name: str,
                      fill: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)):
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object for operation')

    # Auto-increment the names if there is a conflict.
    while name in map(lambda x: x.name, terrain_info.terrain_layers):
        match = re.match(r'(.+)\.(\d+)', name)
        if match:
            name = match.group(1)
            number = int(match.group(2)) + 1
        else:
            number = 1
        name = f'{name}.{number:03d}'

    mesh_data = cast(Mesh, terrain_info_object.data)

    # Create the associated color attribute.
    # TODO: in future, we will be able to paint non-color attributes, so use those once that's possible.
    color_attribute = mesh_data.color_attributes.new(uuid.uuid4().hex, type='FLOAT_COLOR', domain='POINT')
    vertex_count = len(color_attribute.data)
    color_data = np.ndarray(shape=(vertex_count, 4), dtype=float)
    color_data[:] = tuple(fill)
    color_attribute.data.foreach_set('color', color_data.flatten())

    # Add the terrain layer.
    terrain_layer: BDK_PG_TerrainLayerPropertyGroup = terrain_info.terrain_layers.add()
    terrain_layer.terrain_info_object = terrain_info_object
    terrain_layer.name = name
    terrain_layer.color_attribute_name = color_attribute.name

    # Regenerate the terrain material.
    build_terrain_material(terrain_info_object)

    # Tag window regions for redraw so that the new layer is displayed in terrain layer lists immediately.
    for region in filter(lambda r: r.type == 'WINDOW', bpy.context.area.regions):
        region.tag_redraw()

    return terrain_layer


class BDK_OT_TerrainLayerAdd(Operator):
    bl_idname = 'bdk.terrain_layer_add'
    bl_label = 'Add Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name='Name')
    alpha_fill: FloatVectorProperty(name='Alpha Fill', subtype='COLOR', min=0.0, max=1.0, size=4,
                                    default=(0.0, 0.0, 0.0, 1.0))
    u_scale: FloatProperty(name='UScale', default=1.0)
    v_scale: FloatProperty(name='VScale', default=1.0)

    def execute(self, context: bpy.types.Context):
        active_object = context.active_object

        try:
            add_terrain_layer(active_object, name='TerrainLayer', fill=self.alpha_fill)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        return {'FINISHED'}


class TerrainMaterialBuilder:
    def __init__(self):
        pass

    @staticmethod
    def _build_or_get_terrain_layer_uv_group_node() -> bpy.types.NodeTree:
        group_name = 'BDK TerrainLayerUV'
        version = 1  # increment this if we need to regenerate this (for example, if we update this code)

        should_create = False
        if group_name in bpy.data.node_groups:
            node_tree = bpy.data.node_groups[group_name]
            if 'version' not in node_tree or version >= node_tree['version']:
                node_tree['version'] = version
                should_create = True
        else:
            should_create = True

        if should_create:
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
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')
        terrain_layers = terrain_info.terrain_layers

        mesh_data = cast(Mesh, terrain_info_object.data)

        if len(mesh_data.materials) == 0:
            material = bpy.data.materials.new(uuid.uuid4().hex)
            material.use_nodes = True
            mesh_data.materials.append(material)
        else:
            material = mesh_data.materials[0]

        node_tree = material.node_tree
        node_tree.nodes.clear()

        last_shader_socket = None

        for terrain_layer_index, terrain_layer in enumerate(terrain_layers):
            terrain_layer_uv_node = node_tree.nodes.new('ShaderNodeGroup')
            terrain_layer_uv_node.node_tree = self._build_or_get_terrain_layer_uv_group_node()

            def add_terrain_layer_input_driver(node, input_prop: Union[str | int], terrain_layer_prop: str):
                fcurve = node.inputs[input_prop].driver_add('default_value')
                fcurve.driver.type = 'AVERAGE'
                variable = fcurve.driver.variables.new()
                variable.type = 'SINGLE_PROP'
                variable.name = 'u_scale'
                target = variable.targets[0]
                target.id_type = 'OBJECT'
                target.id = terrain_info_object
                target.data_path = f'terrain_info.terrain_layers[{terrain_layer_index}].{terrain_layer_prop}'

            add_terrain_layer_input_driver(terrain_layer_uv_node, 'UScale', 'u_scale')
            add_terrain_layer_input_driver(terrain_layer_uv_node, 'VScale', 'v_scale')
            add_terrain_layer_input_driver(terrain_layer_uv_node, 'TextureRotation', 'texture_rotation')

            terrain_layer_uv_node.inputs['TerrainScale'].default_value = terrain_info.terrain_scale

            image_node = node_tree.nodes.new('ShaderNodeTexImage')
            image_node.image = terrain_layer.image

            color_attribute_node = node_tree.nodes.new('ShaderNodeVertexColor')
            color_attribute_node.layer_name = terrain_layer.color_attribute_name

            hide_node = node_tree.nodes.new('ShaderNodeMath')
            hide_node.operation = 'MULTIPLY'
            add_terrain_layer_input_driver(hide_node, 1, 'is_visible')

            node_tree.links.new(hide_node.inputs[0], color_attribute_node.outputs['Color'])

            diffuse_node = node_tree.nodes.new('ShaderNodeBsdfDiffuse')
            mix_shader_node = node_tree.nodes.new('ShaderNodeMixShader')

            node_tree.links.new(image_node.inputs['Vector'], terrain_layer_uv_node.outputs['UV'])

            node_tree.links.new(diffuse_node.inputs['Color'], image_node.outputs['Color'])
            node_tree.links.new(mix_shader_node.inputs['Fac'], hide_node.outputs['Value'])

            if last_shader_socket is not None:
                node_tree.links.new(mix_shader_node.inputs[1], last_shader_socket)

            node_tree.links.new(mix_shader_node.inputs[2], diffuse_node.outputs['BSDF'])

            last_shader_socket = mix_shader_node.outputs['Shader']

        output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')

        if last_shader_socket is not None:
            node_tree.links.new(output_node.inputs['Surface'], last_shader_socket)


def quad_size_get(self):
    return self.size / self.resolution


class BDK_OT_TerrainInfoAdd(Operator):
    bl_idname = 'bdk.create_terrain_info'
    bl_label = 'Add Terrain Info'
    bl_options = {'REGISTER', 'UNDO'}

    resolution: IntProperty(name='Resolution', default=512, min=2, max=512, description='The number of quads')
    size: FloatProperty(name='Size', default=500 * 60.352, subtype='DISTANCE',
                        description='The length and width of the terrain')
    quad_size: FloatProperty(name='Quad Size', get=quad_size_get, set=None, subtype='DISTANCE')
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
        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(mesh_object, 'terrain_info')
        terrain_info.is_terrain_info = True
        terrain_info.terrain_info_object = mesh_object
        terrain_info.terrain_scale = self.size / self.resolution

        # Add a base layer to start with.
        add_terrain_layer(mesh_object, name='Base', fill=(1.0, 1.0, 1.0, 1.0))

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
