import bmesh
import bpy
from bpy.types import Mesh, Object
from typing import cast, Union, Optional, Tuple, Iterator
import uuid
import numpy as np

from ..helpers import get_terrain_info
from ..data import UReference
from ..material.importer import MaterialBuilder, MaterialCache


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


def build_terrain_material(terrain_info_object: bpy.types.Object):
    terrain_info = get_terrain_info(terrain_info_object)
    if terrain_info is None:
        raise RuntimeError('Invalid object')
    terrain_layers = terrain_info.terrain_layers

    mesh_data = cast(Mesh, terrain_info_object.data)

    # TODO: assuming it's slot 0 is perilous.
    material = mesh_data.materials[0]

    node_tree = material.node_tree
    node_tree.nodes.clear()

    last_shader_socket = None

    bdk_build_path = getattr(bpy.context.preferences.addons['bdk_addon'].preferences, 'build_path')
    material_cache = MaterialCache(bdk_build_path)
    material_builder = MaterialBuilder(material_cache, node_tree)

    for terrain_layer_index, terrain_layer in enumerate(terrain_layers):
        terrain_layer_uv_node = node_tree.nodes.new('ShaderNodeGroup')
        terrain_layer_uv_node.node_tree = _build_or_get_terrain_layer_uv_group_node()

        def add_terrain_layer_input_driver(node, input_prop: Union[str | int], terrain_layer_prop: str):
            fcurve = node.inputs[input_prop].driver_add('default_value')
            fcurve.driver.type = 'AVERAGE'
            variable = fcurve.driver.variables.new()
            variable.type = 'SINGLE_PROP'
            target = variable.targets[0]
            target.id_type = 'OBJECT'
            target.id = terrain_info_object
            target.data_path = f'bdk.terrain_info.terrain_layers[{terrain_layer_index}].{terrain_layer_prop}'

        add_terrain_layer_input_driver(terrain_layer_uv_node, 'UScale', 'u_scale')
        add_terrain_layer_input_driver(terrain_layer_uv_node, 'VScale', 'v_scale')
        add_terrain_layer_input_driver(terrain_layer_uv_node, 'TextureRotation', 'texture_rotation')

        terrain_layer_uv_node.inputs['TerrainScale'].default_value = terrain_info.terrain_scale

        material = terrain_layer.material
        material_outputs = None
        if material and 'bdk.reference' in material:
            reference = UReference.from_string(material['bdk.reference'])
            unreal_material = material_cache.load_material(reference)
            material_outputs = material_builder.build(unreal_material, terrain_layer_uv_node.outputs['UV'])

        color_attribute_node = node_tree.nodes.new('ShaderNodeVertexColor')
        color_attribute_node.layer_name = terrain_layer.id

        hide_node = node_tree.nodes.new('ShaderNodeMath')
        hide_node.operation = 'MULTIPLY'
        add_terrain_layer_input_driver(hide_node, 1, 'is_visible')

        node_tree.links.new(hide_node.inputs[0], color_attribute_node.outputs['Color'])

        diffuse_node = node_tree.nodes.new('ShaderNodeBsdfDiffuse')
        mix_shader_node = node_tree.nodes.new('ShaderNodeMixShader')

        if material_outputs and material_outputs.color_socket:
            node_tree.links.new(diffuse_node.inputs['Color'], material_outputs.color_socket)

        node_tree.links.new(mix_shader_node.inputs['Fac'], hide_node.outputs['Value'])

        if last_shader_socket is not None:
            node_tree.links.new(mix_shader_node.inputs[1], last_shader_socket)

        node_tree.links.new(mix_shader_node.inputs[2], diffuse_node.outputs['BSDF'])

        last_shader_socket = mix_shader_node.outputs['Shader']

    output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')

    if last_shader_socket is not None:
        node_tree.links.new(output_node.inputs['Surface'], last_shader_socket)


def get_terrain_quad_size(size: float, resolution: int) -> float:
    return size / (resolution - 1)


def get_terrain_info_vertex_coordinates(resolution: int, size: float) -> Iterator[Tuple[float, float]]:
    """
    Gets the horizontal (X,Y) coordinates of the vertices for a terrain info object given the resolution and size.
    """
    quad_length = float(size) / resolution
    size_half = 0.5 * size
    for y in range(resolution):
        for x in range(resolution):
            yield quad_length * x - size_half, quad_length * y - size_half + quad_length


def create_terrain_info_object(resolution: int, size: float, heightmap: Optional[np.array] = None, edge_turn_bitmap: Optional[np.array] = None) -> Object:
    # NOTE: There is a bug in Unreal where the terrain is off-center, so we deliberately
    # have to miscalculate things in order to replicate the behavior seen in the engine.

    bm = bmesh.new()

    if heightmap is None:
        heightmap = np.full(resolution * resolution, fill_value=0, dtype=float)

    coordinates_iter = get_terrain_info_vertex_coordinates(resolution, size)
    coordinates = np.fromiter(((x, y, z) for ((x, y), z) in zip(coordinates_iter, heightmap)), dtype=np.dtype((float, 3)))

    for co in coordinates:
        bm.verts.new(co)

    bm.verts.ensure_lookup_table()

    # Build the edge turn face indices set.
    # TODO: Would be nice to make a common function that can do this for both the edge turn bitmap and the quad vis.
    # TODO: Inefficient to be doing look-ups here I think. Would probably make more sense to build an actual bitmap
    # and then flip it over Y so that the indexing of the edge turn bitmap and the quads lines up.
    edge_turn_face_indices = set()
    if edge_turn_bitmap is not None:
        edge_turn_bitmap_index = 0
        for y in reversed(range(resolution - 1)):
            for x in range(resolution - 1):
                face_index = (y * resolution) - y + x
                array_index = edge_turn_bitmap_index >> 5
                bit_mask = edge_turn_bitmap_index & 0x1F
                if (edge_turn_bitmap[array_index] & (1 << bit_mask)) == 0:
                    edge_turn_face_indices.add(face_index)
                edge_turn_bitmap_index += 1
            edge_turn_bitmap_index += 1

    # Faces
    vertex_index = 0
    indices = [0, 1, resolution + 1, resolution]
    turned_indices = [resolution, 0, 1, resolution + 1]
    for y in range(resolution - 1):
        for x in range(resolution - 1):
            face_index = (y * resolution) - y + x
            if face_index in edge_turn_face_indices:
                face = bm.faces.new(tuple([bm.verts[vertex_index + i] for i in turned_indices]))
            else:
                face = bm.faces.new(tuple([bm.verts[vertex_index + i] for i in indices]))
            face.smooth = True
            vertex_index += 1
            face_index += 1
        vertex_index += 1

    mesh_data = bpy.data.meshes.new('TerrainInfo')
    bm.to_mesh(mesh_data)
    del bm

    mesh_object = bpy.data.objects.new('TerrainInfo', mesh_data)

    # Set the BDK object type.
    mesh_object.bdk.type = 'TERRAIN_INFO'

    # Custom properties
    terrain_info: 'BDK_PG_terrain_info' = getattr(mesh_object.bdk, 'terrain_info')
    terrain_info.terrain_info_object = mesh_object
    terrain_info.x_size = resolution
    terrain_info.y_size = resolution
    terrain_info.size = size
    terrain_info.terrain_scale = size / resolution

    # Create an empty material that will be used as the terrain material downstream.
    terrain_material = bpy.data.materials.new(uuid.uuid4().hex)
    terrain_material.use_nodes = True
    terrain_material.node_tree.nodes.clear()

    # Create the "hidden" material we will use for hiding quads.
    # TODO: in future, use boolean attribute on the face domain once we can paint it
    hidden_material = bpy.data.materials.new(uuid.uuid4().hex)
    hidden_material.use_nodes = True
    hidden_material.node_tree.nodes.clear()
    hidden_material.blend_method = 'CLIP'
    node_tree = hidden_material.node_tree
    output_node = node_tree.nodes.new('ShaderNodeOutputMaterial')

    transparent_node = node_tree.nodes.new('ShaderNodeBsdfTransparent')
    node_tree.links.new(output_node.inputs['Surface'], transparent_node.outputs['BSDF'])

    mesh_data.materials.append(terrain_material)
    mesh_data.materials.append(hidden_material)

    return mesh_object
