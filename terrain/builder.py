import bpy
from bpy.types import Mesh
from typing import cast, Union
import uuid


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
        terrain_info: 'BDK_PG_TerrainInfoPropertyGroup' = getattr(terrain_info_object, 'terrain_info')
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
