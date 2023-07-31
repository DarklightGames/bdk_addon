import uuid
from typing import List, Iterable, Optional

import bmesh
import bpy
from uuid import uuid4
from bpy.types import NodeTree, Context, Object, NodeSocket, bpy_struct

from ..deco import ensure_paint_layers, ensure_deco_layers
from ...node_helpers import add_interpolation_type_switch_nodes, add_operation_switch_nodes,\
    add_noise_type_switch_nodes, ensure_geometry_node_tree, ensure_input_and_output_nodes
from .data import map_range_interpolation_type_items, terrain_doodad_operation_items
from ...units import meters_to_unreal


distance_to_mesh_node_group_id = 'BDK Distance to Mesh'
distance_to_empty_node_group_id = 'BDK Distance to Empty'
distance_to_curve_node_group_id = 'BDK Distance to Curve'


def ensure_distance_to_curve_node_group() -> NodeTree:
    inputs = {
        ('NodeSocketGeometry', 'Curve'),
        ('NodeSocketBool', 'Is 3D'),
    }
    outputs = {
        ('NodeSocketFloat', 'Distance'),
    }
    node_tree = ensure_geometry_node_tree(distance_to_curve_node_group_id, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    # Add a curve to mesh node.
    curve_to_mesh_node = node_tree.nodes.new(type='GeometryNodeCurveToMesh')

    # Add a geometry proximity node.
    geometry_proximity_node = node_tree.nodes.new(type='GeometryNodeProximity')
    geometry_proximity_node.target_element = 'EDGES'

    # Link the geometry output of the object info node to the geometry input of the curve to mesh node.
    node_tree.links.new(input_node.outputs['Curve'], curve_to_mesh_node.inputs['Curve'])

    # Link the mesh output of the curve to mesh node to the geometry input of the proximity node.
    node_tree.links.new(curve_to_mesh_node.outputs['Mesh'], geometry_proximity_node.inputs['Target'])

    # Add a new Position and Separate XYZ node.
    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
    separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

    # Link the position node to the input of the separate XYZ node.
    node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'FLOAT'

    # Link the output of the boolean node to the switch input of the switch node.
    node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])

    # Link the Z output of the separate XYZ node to the True input of the switch node.
    node_tree.links.new(separate_xyz_node.outputs['Z'], switch_node.inputs['True'])

    combine_xyz_node_2 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

    # Link the X and Y outputs of the separate XYZ node to the X and Y inputs of the combine XYZ node.
    node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node_2.inputs['X'])
    node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node_2.inputs['Y'])
    node_tree.links.new(switch_node.outputs['Output'], combine_xyz_node_2.inputs['Z'])

    # Link the output of the combine XYZ node to the source position input of the geometry proximity node.
    node_tree.links.new(combine_xyz_node_2.outputs['Vector'], geometry_proximity_node.inputs['Source Position'])

    # Link the output of the geometry proximity node to the distance output of the node group.
    node_tree.links.new(geometry_proximity_node.outputs['Distance'], output_node.inputs['Distance'])

    return node_tree


def create_noise_node_group():
    # Create a new geometry node group.
    inputs = {
        ('NodeSocketFloat', 'Distance'),
        ('NodeSocketFloat', 'Radius'),
        ('NodeSocketFloat', 'Noise Strength'),
        ('NodeSocketFloat', 'Noise Roughness'),
        ('NodeSocketFloat', 'Noise Distortion'),
    }
    outputs = {('NodeSocketFloat', 'Offset')}
    node_tree = ensure_geometry_node_tree(uuid.uuid4().hex, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    # Add a multiply node.
    multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node.operation = 'MULTIPLY'

    # Add another multiply node.
    multiply_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node_2.operation = 'MULTIPLY'

    node_tree.links.new(multiply_node_2.outputs['Value'], multiply_node.inputs[0])
    node_tree.links.new(input_node.outputs['Noise Strength'], multiply_node.inputs[1])

    # Add a position input node.
    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

    # Add a noise texture node.
    noise_texture_node = node_tree.nodes.new(type='ShaderNodeTexNoise')
    noise_texture_node.noise_dimensions = '2D'
    noise_texture_node.inputs['Scale'].default_value = 1.0

    # Link the roughness input of the input node to the roughness input of the noise texture node.
    node_tree.links.new(input_node.outputs['Noise Roughness'], noise_texture_node.inputs['Roughness'])
    node_tree.links.new(input_node.outputs['Noise Distortion'], noise_texture_node.inputs['Distortion'])

    # Link the position output of the position node to the vector input of the noise texture node.
    node_tree.links.new(position_node.outputs['Position'], noise_texture_node.inputs['Vector'])

    # Add a Map Range node.
    map_range_node = node_tree.nodes.new(type='ShaderNodeMapRange')
    map_range_node.data_type = 'FLOAT'
    map_range_node.inputs['To Min'].default_value = -0.5
    map_range_node.inputs['To Max'].default_value = 0.5

    # Link the factor output of the noise texture to the value input of the map range node.
    node_tree.links.new(noise_texture_node.outputs['Fac'], map_range_node.inputs['Value'])

    # Add a Subtract node.
    subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
    subtract_node.operation = 'SUBTRACT'
    subtract_node.inputs[0].default_value = 1.0

    # Add a Divide node.
    divide_node = node_tree.nodes.new(type='ShaderNodeMath')
    divide_node.operation = 'DIVIDE'
    divide_node.use_clamp = True

    node_tree.links.new(input_node.outputs['Distance'], divide_node.inputs[0])
    node_tree.links.new(input_node.outputs['Radius'], divide_node.inputs[1])

    # Link the output of the divide node to the second input of the subtraction node.
    node_tree.links.new(divide_node.outputs['Value'], subtract_node.inputs[1])

    # Link the output of the subtraction node to the first input of the second multiply node.
    node_tree.links.new(subtract_node.outputs['Value'], multiply_node_2.inputs[0])

    # Link the map range result to the second input of the second multiply node.
    node_tree.links.new(map_range_node.outputs['Result'], multiply_node_2.inputs[1])

    node_tree.links.new(multiply_node.outputs['Value'], output_node.inputs['Offset'])

    return node_tree


def ensure_sculpt_node_group(sculpt_layer_id: str) -> NodeTree:
    inputs = {
        ('NodeSocketGeometry', 'Geometry'),
        ('NodeSocketFloat', 'Distance'),
        ('NodeSocketInt', 'Interpolation Type'),
        ('NodeSocketFloat', 'Radius'),
        ('NodeSocketFloat', 'Falloff Radius'),
        ('NodeSocketFloat', 'Depth'),
        ('NodeSocketFloat', 'Noise Strength'),
        ('NodeSocketFloat', 'Noise Roughness'),
        ('NodeSocketFloat', 'Noise Distortion'),
        ('NodeSocketBool', 'Use Noise'),
        ('NodeSocketFloat', 'Noise Radius Factor'),
    }
    outputs = {
        ('NodeSocketGeometry', 'Geometry'),
    }
    node_tree = ensure_geometry_node_tree(sculpt_layer_id, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    # Add a subtract node.
    subtract_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
    subtract_node_2.operation = 'SUBTRACT'

    # Link the distance from the input node to the first input of the subtraction node.
    node_tree.links.new(input_node.outputs['Distance'], subtract_node_2.inputs[0])
    node_tree.links.new(input_node.outputs['Radius'], subtract_node_2.inputs[1])

    # Add a divide math node.
    divide_node = node_tree.nodes.new(type='ShaderNodeMath')
    divide_node.operation = 'DIVIDE'
    divide_node.use_clamp = True

    # Link the distance output of the geometry proximity node to the first input of the divide node.
    node_tree.links.new(subtract_node_2.outputs['Value'], divide_node.inputs[0])

    # Link the radius value node to the second input of the divide node.
    node_tree.links.new(input_node.outputs['Falloff Radius'], divide_node.inputs[1])

    # --------------------

    value_node = add_interpolation_type_switch_nodes(
        node_tree,
        input_node.outputs['Interpolation Type'],
        divide_node.outputs['Value'],
        [x[0] for x in map_range_interpolation_type_items]
    )

    # Add a new multiply node.
    multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node.operation = 'MULTIPLY'

    # Link the map range node to the first input of the multiply node.
    node_tree.links.new(value_node, multiply_node.inputs[0])
    node_tree.links.new(input_node.outputs['Depth'], multiply_node.inputs[1])

    # Add a combine XYZ node.
    combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

    # Add a Set Position node.
    set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

    # Link the output of the combine XYZ node to the offset input of the set position node.
    node_tree.links.new(combine_xyz_node.outputs['Vector'], set_position_node.inputs['Offset'])

    # Link the geometry socket of the input to the output through the set position node.
    node_tree.links.new(input_node.outputs['Geometry'], set_position_node.inputs['Geometry'])
    node_tree.links.new(set_position_node.outputs['Geometry'], output_node.inputs['Geometry'])

    # Create the noise node.
    noise_node = node_tree.nodes.new(type='GeometryNodeGroup')
    noise_node.node_tree = create_noise_node_group()

    node_tree.links.new(input_node.outputs['Noise Strength'], noise_node.inputs['Noise Strength'])
    node_tree.links.new(input_node.outputs['Noise Roughness'], noise_node.inputs['Noise Roughness'])
    node_tree.links.new(input_node.outputs['Noise Distortion'], noise_node.inputs['Noise Distortion'])

    # Add a switch node of with input type float.
    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'FLOAT'
    switch_node.label = 'Use Distance Noise'

    node_tree.links.new(input_node.outputs['Use Noise'], switch_node.inputs['Switch'])

    # Link the offset output of the noise node to the True input of the switch node.
    node_tree.links.new(noise_node.outputs['Offset'], switch_node.inputs['True'])

    # Add a new add node.
    add_node = node_tree.nodes.new(type='ShaderNodeMath')
    add_node.operation = 'ADD'

    node_tree.links.new(multiply_node.outputs['Value'], add_node.inputs[0])
    node_tree.links.new(switch_node.outputs['Output'], add_node.inputs[1])
    node_tree.links.new(add_node.outputs['Value'], combine_xyz_node.inputs['Z'])

    # Link the distance output of the input node to the distance input of the noise node.
    node_tree.links.new(input_node.outputs['Distance'], noise_node.inputs['Distance'])

    # Add a new add node that adds the output values of the radius and the falloff radius nodes.
    add_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
    add_node_2.operation = 'ADD'
    node_tree.links.new(input_node.outputs['Radius'], add_node_2.inputs[0])
    node_tree.links.new(input_node.outputs['Falloff Radius'], add_node_2.inputs[1])

    # Add a new node that multiplies the output of the add node by a second value driven by the noise radius factor.
    noise_radius_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    noise_radius_multiply_node.operation = 'MULTIPLY'

    node_tree.links.new(add_node_2.outputs['Value'], noise_radius_multiply_node.inputs[0])
    node_tree.links.new(input_node.outputs['Noise Radius Factor'], noise_radius_multiply_node.inputs[1])

    # Link the value output of the add node to the radius input of the noise node.
    node_tree.links.new(noise_radius_multiply_node.outputs['Value'], noise_node.inputs['Radius'])

    return node_tree


def ensure_paint_node_group() -> NodeTree:
    inputs = {
        ('NodeSocketGeometry', 'Geometry'),
        ('NodeSocketInt', 'Interpolation Type'),
        ('NodeSocketInt', 'Operation'),
        ('NodeSocketInt', 'Noise Type'),
        ('NodeSocketFloat', 'Distance'),
        ('NodeSocketString', 'Attribute'),
        ('NodeSocketFloat', 'Radius'),
        ('NodeSocketFloat', 'Falloff Radius'),
        ('NodeSocketFloat', 'Strength'),
        ('NodeSocketFloat', 'Distance Noise Factor'),
        ('NodeSocketFloat', 'Distance Noise Distortion'),
        ('NodeSocketFloat', 'Distance Noise Offset'),
        ('NodeSocketBool', 'Use Distance Noise'),
    }
    outputs = {
        ('NodeSocketGeometry', 'Geometry'),
    }
    node_tree = ensure_geometry_node_tree(uuid4().hex, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    # Create a new Store Named Attribute node.
    store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
    store_named_attribute_node.data_type = 'BYTE_COLOR'
    store_named_attribute_node.domain = 'POINT'

    # Create a Named Attribute node.
    named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
    named_attribute_node.data_type = 'FLOAT'

    # Link the Attribute output of the input node to the name input of the named attribute node.
    node_tree.links.new(input_node.outputs['Attribute'], named_attribute_node.inputs['Name'])
    node_tree.links.new(input_node.outputs['Attribute'], store_named_attribute_node.inputs['Name'])

    # Pass the geometry from the input to the output.
    node_tree.links.new(input_node.outputs['Geometry'], output_node.inputs['Geometry'])

    # Add a subtract node.
    subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
    subtract_node.operation = 'SUBTRACT'

    # Link the distance output of the input node to the first input of the subtraction node.
    node_tree.links.new(input_node.outputs['Radius'], subtract_node.inputs[1])

    # Add a divide node.
    divide_node = node_tree.nodes.new(type='ShaderNodeMath')
    divide_node.operation = 'DIVIDE'

    # Link the output of the subtraction node to the first input of the divide node.
    node_tree.links.new(subtract_node.outputs['Value'], divide_node.inputs[0])
    node_tree.links.new(input_node.outputs['Falloff Radius'], divide_node.inputs[1])

    # Add a map range node. (maybe just make a node group for this specifically)
    value_socket = add_interpolation_type_switch_nodes(
        node_tree,
        input_node.outputs['Interpolation Type'],
        divide_node.outputs['Value'],
        [x[0] for x in map_range_interpolation_type_items],
    )

    # Link the geometry output of the input node to the geometry input of the store named attribute node.
    node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])

    # Link the geometry output of the store named attribute node to the geometry input of the output node.
    node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    # Link the attribute output of the named attribute node to the second input of the add node.

    # Add a multiply node.
    strength_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    strength_multiply_node.operation = 'MULTIPLY'
    strength_multiply_node.label = 'Strength Multiply'

    # Link the value output of the add node to the value input of the store named attribute node.
    node_tree.links.new(value_socket, strength_multiply_node.inputs[0])
    node_tree.links.new(input_node.outputs['Strength'], strength_multiply_node.inputs[1])

    value_socket = add_operation_switch_nodes(
        node_tree,
        input_node.outputs['Operation'],
        named_attribute_node.outputs[1],
        strength_multiply_node.outputs['Value'],
        [x[0] for x in terrain_doodad_operation_items]
    )

    # Link the output of the add node to the value input of the store named attribute node.
    node_tree.links.new(value_socket, store_named_attribute_node.inputs[5])

    # Add a position input node.
    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

    noise_value_socket = add_noise_type_switch_nodes(
        node_tree,
        position_node.outputs['Position'],
        input_node.outputs['Noise Type'],
        input_node.outputs['Distance Noise Distortion'],
        None
    )

    # Add an add noise node.
    add_distance_noise_node = node_tree.nodes.new(type='ShaderNodeMath')
    add_distance_noise_node.operation = 'ADD'
    add_distance_noise_node.label = 'Add Distance Noise'

    node_tree.links.new(input_node.outputs['Distance'], add_distance_noise_node.inputs[0])

    use_noise_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    use_noise_switch_node.input_type = 'FLOAT'
    use_noise_switch_node.label = 'Use Distance Noise'

    node_tree.links.new(input_node.outputs['Use Distance Noise'], use_noise_switch_node.inputs[0])

    node_tree.links.new(input_node.outputs['Distance'], use_noise_switch_node.inputs[2])
    node_tree.links.new(add_distance_noise_node.outputs['Value'], use_noise_switch_node.inputs[3])

    node_tree.links.new(use_noise_switch_node.outputs[0], subtract_node.inputs[0])

    distance_noise_factor_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    distance_noise_factor_multiply_node.operation = 'MULTIPLY'
    distance_noise_factor_multiply_node.label = 'Distance Noise Factor'

    node_tree.links.new(input_node.outputs['Distance Noise Factor'], distance_noise_factor_multiply_node.inputs[1])
    node_tree.links.new(distance_noise_factor_multiply_node.outputs['Value'], add_distance_noise_node.inputs[1])

    distance_noise_offset_subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
    distance_noise_offset_subtract_node.operation = 'SUBTRACT'
    distance_noise_offset_subtract_node.label = 'Distance Noise Offset'

    node_tree.links.new(noise_value_socket, distance_noise_offset_subtract_node.inputs[0])
    node_tree.links.new(input_node.outputs['Distance Noise Offset'], distance_noise_offset_subtract_node.inputs[1])
    node_tree.links.new(distance_noise_offset_subtract_node.outputs['Value'], distance_noise_factor_multiply_node.inputs[0])

    return node_tree


def ensure_distance_to_mesh_node_group() -> NodeTree:
    inputs = {('NodeSocketGeometry', 'Geometry'), ('NodeSocketBool', 'Is 3D')}
    outputs = {('NodeSocketFloat', 'Distance')}
    node_tree = ensure_geometry_node_tree(distance_to_mesh_node_group_id, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

    # Add a new Position and Separate XYZ node.
    separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

    # Add geometry proximity node.
    geometry_proximity_node = node_tree.nodes.new(type='GeometryNodeProximity')
    geometry_proximity_node.target_element = 'FACES'

    # Add transform geometry node.
    transform_geometry_node = node_tree.nodes.new(type='GeometryNodeTransform')
    transform_geometry_node.inputs['Scale'].default_value = (1.0, 1.0, 0.0)

    # Link the geometry node from the input node to the geometry input of the transform geometry node.
    node_tree.links.new(input_node.outputs['Geometry'], transform_geometry_node.inputs['Geometry'])

    # Link the geometry node from the transform geometry node to the geometry input of the geometry proximity node.
    node_tree.links.new(transform_geometry_node.outputs['Geometry'], geometry_proximity_node.inputs['Target'])

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'VECTOR'

    # Link the output of the boolean node to the switch input of the switch node.
    node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])

    # Link the distance output of the geometry proximity node to the distance input of the output node.
    node_tree.links.new(geometry_proximity_node.outputs['Distance'], output_node.inputs['Distance'])

    # Link the position output of the position node to the vector input of the separate XYZ node.
    node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])

    # Link the position output of the position node to the true input of the switch node.

    # Add a combine XYZ node.
    combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

    # Link the X and Y output of the separate XYZ node to the X and Y input of the combine XYZ node.
    node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node.inputs['X'])
    node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node.inputs['Y'])

    # Link the output of the combine XYZ node to the false input of the switch node.
    node_tree.links.new(combine_xyz_node.outputs['Vector'], switch_node.inputs[8])
    node_tree.links.new(position_node.outputs['Position'], switch_node.inputs[9])

    # Link the vector output of the switch node to the source position input of the geometry proximity node.
    node_tree.links.new(switch_node.outputs[3], geometry_proximity_node.inputs['Source Position'])

    return node_tree


def ensure_distance_to_empty_node_group() -> NodeTree:
    inputs = {
        ('NodeSocketVector', 'Location'),
        ('NodeSocketBool', 'Is 3D')
    }
    outputs = {('NodeSocketFloat', 'Distance')}
    node_tree = ensure_geometry_node_tree(distance_to_empty_node_group_id, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    # Add a new Position and Separate XYZ node.
    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
    separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'FLOAT'

    # Link the output of the boolean node to the switch input of the switch node.
    node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])

    # Link the Z output of the separate XYZ node to the True input of the switch node.
    node_tree.links.new(separate_xyz_node.outputs['Z'], switch_node.inputs['True'])

    combine_xyz_node_2 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

    # Link the X and Y outputs of the separate XYZ node to the X and Y inputs of the combine XYZ node.
    node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node_2.inputs['X'])
    node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node_2.inputs['Y'])
    node_tree.links.new(switch_node.outputs['Output'], combine_xyz_node_2.inputs['Z'])

    vector_subtract_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
    vector_subtract_node.operation = 'SUBTRACT'

    node_tree.links.new(input_node.outputs['Location'], vector_subtract_node.inputs[0])
    node_tree.links.new(position_node.outputs['Position'], vector_subtract_node.inputs[1])

    # Link the position node to the input of the separate XYZ node.
    node_tree.links.new(vector_subtract_node.outputs['Vector'], separate_xyz_node.inputs['Vector'])

    # Add a new vector length node.
    vector_length_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
    vector_length_node.operation = 'LENGTH'

    # Link the output of the combine XYZ node to the input of the vector length node.
    node_tree.links.new(combine_xyz_node_2.outputs['Vector'], vector_length_node.inputs['Vector'])

    # Link the output of the vector length node to the input of the output node.
    node_tree.links.new(vector_length_node.outputs['Value'], output_node.inputs['Distance'])

    return node_tree


def create_terrain_doodad(context: Context, terrain_info_object: Object, object_type: str = 'CURVE') -> Object:
    """
    Creates a terrain doodad of the specified type.
    Note that this function does not add the terrain doodad object to the scene. That is the responsibility of the caller.
    :param context:
    :param terrain_info_object:
    :param object_type: The type of object to create. Valid values are 'CURVE', 'MESH' and 'EMPTY'
    :return:
    """
    terrain_doodad_id = uuid4().hex

    if object_type == 'CURVE':
        object_data = bpy.data.curves.new(name=terrain_doodad_id, type='CURVE')
        spline = object_data.splines.new(type='BEZIER')

        # Add some points to the spline.
        spline.bezier_points.add(count=1)

        # Add a set of aligned meandering points.
        for i, point in enumerate(spline.bezier_points):
            point.co = (i, 0, 0)
            point.handle_left_type = 'AUTO'
            point.handle_right_type = 'AUTO'
            point.handle_left = (i - 0.25, -0.25, 0)
            point.handle_right = (i + 0.25, 0.25, 0)

        # Scale the points.
        scale = meters_to_unreal(10.0)
        for point in spline.bezier_points:
            point.co *= scale
            point.handle_left *= scale
            point.handle_right *= scale
    elif object_type == 'EMPTY':
        object_data = None
    elif object_type == 'MESH':
        object_data = bpy.data.meshes.new(name=terrain_doodad_id)
        # Create a plane using bmesh.
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=meters_to_unreal(1.0))
        bm.to_mesh(object_data)
        del bm

    bpy_object = bpy.data.objects.new(name='Doodad', object_data=object_data)

    if object_type == 'EMPTY':
        bpy_object.empty_display_type = 'SPHERE'
        bpy_object.empty_display_size = meters_to_unreal(1.0)
        # Set the delta transform to the terrain info object's rotation.
        bpy_object.delta_rotation_euler = (0, 0, 0)
    elif object_type == 'MESH':
        bpy_object.display_type = 'WIRE'

    # Hide from rendering and Cycles passes.
    bpy_object.hide_render = True

    # Disable all ray visibility settings (this stops it from being visible in Cycles rendering in the viewport).
    bpy_object.visible_camera = False
    bpy_object.visible_diffuse = False
    bpy_object.visible_glossy = False
    bpy_object.visible_transmission = False
    bpy_object.visible_volume_scatter = False
    bpy_object.visible_shadow = False

    bpy_object.bdk.type = 'TERRAIN_DOODAD'
    bpy_object.bdk.terrain_doodad.id = terrain_doodad_id
    bpy_object.bdk.terrain_doodad.terrain_info_object = terrain_info_object
    bpy_object.bdk.terrain_doodad.object = bpy_object
    bpy_object.bdk.terrain_doodad.node_tree = bpy.data.node_groups.new(name=terrain_doodad_id, type='GeometryNodeTree')
    bpy_object.show_in_front = True
    bpy_object.lock_location = (False, False, True)
    bpy_object.lock_rotation = (True, True, False)

    terrain_doodad = bpy_object.bdk.terrain_doodad

    # Add sculpt and paint layers.
    # In the future, we will allow the user to select a preset for the terrain doodad.
    sculpt_layer = terrain_doodad.sculpt_layers.add()
    sculpt_layer.id = uuid4().hex
    sculpt_layer.terrain_doodad_object = terrain_doodad.object

    paint_layer = terrain_doodad.paint_layers.add()
    paint_layer.id = uuid4().hex
    paint_layer.terrain_doodad_object = terrain_doodad.object

    # Set the location of the curve object to the 3D cursor.
    bpy_object.location = context.scene.cursor.location

    return bpy_object


def get_terrain_doodads_for_terrain_info_object(context: Context, terrain_info_object: Object) -> List['BDK_PG_terrain_doodad']:
    return [obj.bdk.terrain_doodad for obj in context.scene.objects if obj.bdk.type == 'TERRAIN_DOODAD' and obj.bdk.terrain_doodad.terrain_info_object == terrain_info_object]


def ensure_terrain_info_modifiers(context: Context, terrain_info: 'BDK_PG_terrain_info'):
    print('ensure_terrain_info_modifiers')

    terrain_info_object = terrain_info.terrain_info_object

    # Ensure that the modifier IDs have been generated.
    if terrain_info.doodad_sculpt_modifier_name == '':
        terrain_info.doodad_sculpt_modifier_name = uuid.uuid4().hex

    if terrain_info.doodad_paint_modifier_name == '':
        terrain_info.doodad_paint_modifier_name = uuid.uuid4().hex

    if terrain_info.doodad_deco_modifier_name == '':
        terrain_info.doodad_deco_modifier_name = uuid.uuid4().hex

    # Gather and sort the terrain doodad by the sort order and ID.
    terrain_doodads = get_terrain_doodads_for_terrain_info_object(context, terrain_info.terrain_info_object)
    terrain_doodads.sort(key=lambda x: (x.sort_order, x.id))

    # Ensure that the terrain info object has the required pass modifiers.
    modifier_names = [
        terrain_info.doodad_sculpt_modifier_name,
        terrain_info.doodad_paint_modifier_name,
        terrain_info.doodad_deco_modifier_name
    ]
    for modifier_name in modifier_names:
        if modifier_name not in terrain_info_object.modifiers:
            modifier = terrain_info_object.modifiers.new(name=modifier_name, type='NODES')
            modifier.show_on_cage = True

    # Ensure the node groups for the pass modifiers.
    modifiers = terrain_info_object.modifiers
    modifiers[terrain_info.doodad_sculpt_modifier_name].node_group = _ensure_terrain_doodad_sculpt_modifier_node_group(terrain_info.doodad_sculpt_modifier_name, terrain_doodads)
    modifiers[terrain_info.doodad_paint_modifier_name].node_group = _ensure_terrain_doodad_paint_modifier_node_group(terrain_info.doodad_paint_modifier_name, terrain_doodads)
    modifiers[terrain_info.doodad_deco_modifier_name].node_group = _ensure_terrain_doodad_deco_modifier_node_group(terrain_info.doodad_deco_modifier_name, terrain_doodads)

    # Rebuild the modifier node trees for the paint and deco layers.
    ensure_paint_layers(terrain_info_object)
    ensure_deco_layers(terrain_info_object)

    """
    Sort the modifiers on the terrain info object in the following order:
    1. Terrain Doodad Sculpt
    2. Terrain Info Paint Layer Nodes
    3. Terrain Doodad Paint Layers
    4. Terrain Info Deco Layer Nodes
    5. Terrain Doodad Deco Layers
    """

    # The modifier ID list will contain a list of modifier IDs in the order that they should be sorted.
    modifier_ids = list()
    modifier_ids.append(terrain_info.doodad_sculpt_modifier_name)
    modifier_ids.extend(map(lambda paint_layer: paint_layer.id, terrain_info.paint_layers))
    modifier_ids.append(terrain_info.doodad_paint_modifier_name)
    modifier_ids.extend(map(lambda deco_layer: deco_layer.id, terrain_info.deco_layers))
    modifier_ids.append(terrain_info.doodad_deco_modifier_name)

    # print([(i, modifier_id) for (i, modifier_id) in enumerate(modifier_ids)])

    # Make note of what the current mode is so that we can restore it later.
    current_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    current_active_object = bpy.context.view_layer.objects.active

    # Make the active object the terrain info object.
    bpy.context.view_layer.objects.active = terrain_info_object

    # Set the mode to OBJECT so that we can move the modifiers.
    bpy.ops.object.mode_set(mode='OBJECT')

    # It's theoretically possible that the modifiers don't exist (e.g., having been deleted by the user, debugging etc.)
    # Get a list of missing modifiers.
    missing_modifier_ids = set(modifier_ids).difference(set(terrain_info_object.modifiers.keys()))
    if len(missing_modifier_ids) > 0:
        print(f'Missing modifiers: {missing_modifier_ids}')

    # Remove any modifier IDs that do not have a corresponding modifier in the terrain info object.
    modifier_ids = [x for x in modifier_ids if x in terrain_info_object.modifiers]

    # TODO: it would be nice if we could move the modifiers without needing to use the ops API, or at
    #  least suspend evaluation of the node tree while we do it.
    # TODO: we can use the data API to do this, but we need to know the index of the modifier in the list.
    # Update the modifiers on the terrain info object to reflect the new sort order.
    for i, modifier_id in enumerate(modifier_ids):
        bpy.ops.object.modifier_move_to_index(modifier=modifier_id, index=i)

    # Restore the mode and active object to what it was before.
    bpy.context.view_layer.objects.active = current_active_object

    if bpy.context.view_layer.objects.active:
        bpy.ops.object.mode_set(mode=current_mode)


def _add_sculpt_layers_to_node_tree(node_tree: NodeTree, geometry_socket: NodeSocket, terrain_doodad) -> NodeSocket:
    """
    Adds the nodes for a terrain doodad's sculpt layers.
    :param node_tree: The node tree to add the nodes to.
    :param geometry_socket: The geometry socket to connect the nodes to.
    :param terrain_doodad: The terrain doodad to add the sculpt layers for.
    :return: The geometry output socket (either the one passed in or the one from the last node added).
    """

    def add_doodad_sculpt_layer_driver(struct: bpy_struct, sculpt_layer: 'BDK_PG_terrain_doodad_sculpt_layer', data_path: str,
                                path: str = 'default_value'):
        driver = struct.driver_add(path).driver
        driver.type = 'AVERAGE'
        var = driver.variables.new()
        var.name = data_path
        var.type = 'SINGLE_PROP'
        var.targets[0].id = sculpt_layer.terrain_doodad_object
        var.targets[0].data_path = f"bdk.terrain_doodad.sculpt_layers[{sculpt_layer.index}].{data_path}"

    def add_doodad_driver(struct: bpy_struct, terrain_doodad: 'BDK_PG_terrain_doodad', data_path: str,
                                  path: str = 'default_value'):
        driver = struct.driver_add(path).driver
        driver.type = 'AVERAGE'
        var = driver.variables.new()
        var.name = data_path
        var.type = 'SINGLE_PROP'
        var.targets[0].id = terrain_doodad.object
        var.targets[0].data_path = f"bdk.terrain_doodad.{data_path}"

    # Add an object info node and set the object to the terrain doodad.
    object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    object_info_node.inputs[0].default_value = terrain_doodad.object
    object_info_node.transform_space = 'RELATIVE'

    distance_socket = None

    if terrain_doodad.object.type == 'CURVE':
        # Create a new distance to curve node group.
        distance_to_curve_node_group = ensure_distance_to_curve_node_group()

        # Add a new node group node.
        distance_to_curve_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_curve_node.node_tree = distance_to_curve_node_group
        distance_to_curve_node.label = 'Distance to Curve'

        node_tree.links.new(object_info_node.outputs['Geometry'], distance_to_curve_node.inputs['Curve'])
        add_doodad_driver(distance_to_curve_node.inputs['Is 3D'], terrain_doodad, 'is_3d')

        distance_socket = distance_to_curve_node.outputs['Distance']
    elif terrain_doodad.object.type == 'MESH':
        distance_to_mesh_node_group = ensure_distance_to_mesh_node_group()

        # Add a new node group node.
        distance_to_mesh_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_mesh_node.node_tree = distance_to_mesh_node_group
        distance_to_mesh_node.label = 'Distance to Mesh'

        node_tree.links.new(object_info_node.outputs['Geometry'], distance_to_mesh_node.inputs['Geometry'])

        distance_socket = distance_to_mesh_node.outputs['Distance']
    elif terrain_doodad.object.type == 'EMPTY':
        distance_to_empty_node_group = ensure_distance_to_empty_node_group()

        distance_to_empty_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_empty_node.node_tree = distance_to_empty_node_group
        distance_to_empty_node.label = 'Distance to Empty'

        node_tree.links.new(object_info_node.outputs['Location'], distance_to_empty_node.inputs['Location'])
        add_doodad_driver(distance_to_empty_node.inputs['Is 3D'], terrain_doodad, 'is_3d')

        distance_socket = distance_to_empty_node.outputs['Distance']

    # Store the calculated distance to a named attribute.
    # This is faster than recalculating the distance when evaluating each layer. (~20% faster)
    store_distance_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
    store_distance_attribute_node.inputs['Name'].default_value = terrain_doodad.id
    store_distance_attribute_node.data_type = 'FLOAT'
    store_distance_attribute_node.domain = 'POINT'

    # Link the geometry from the input node to the input of the store distance attribute node.
    node_tree.links.new(geometry_socket, store_distance_attribute_node.inputs['Geometry'])

    # Link the distance socket to the input of the store distance attribute node.
    node_tree.links.new(distance_socket, store_distance_attribute_node.inputs[4])

    # Create a named attribute node for the distance.
    distance_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
    distance_attribute_node.inputs['Name'].default_value = terrain_doodad.id
    distance_attribute_node.data_type = 'FLOAT'

    distance_socket = distance_attribute_node.outputs[1]
    geometry_socket = store_distance_attribute_node.outputs['Geometry']

    # Now chain the node components together.
    for sculpt_layer in terrain_doodad.sculpt_layers:
        sculpt_node = node_tree.nodes.new(type='GeometryNodeGroup')
        sculpt_node.node_tree = ensure_sculpt_node_group(sculpt_layer.id)
        sculpt_node.label = 'Sculpt'

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'GEOMETRY'

        add_doodad_sculpt_layer_driver(switch_node.inputs[1], sculpt_layer, 'mute')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Radius'], sculpt_layer, 'radius')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Falloff Radius'], sculpt_layer, 'falloff_radius')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Depth'], sculpt_layer, 'depth')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Noise Strength'], sculpt_layer, 'noise_strength')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Noise Roughness'], sculpt_layer, 'noise_roughness')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Noise Distortion'], sculpt_layer, 'noise_distortion')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Use Noise'], sculpt_layer, 'use_noise')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Noise Radius Factor'], sculpt_layer, 'noise_radius_factor')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Interpolation Type'], sculpt_layer, 'interpolation_type')

        # Link the geometry socket of the object info node to the geometry socket of the sculpting node.
        node_tree.links.new(geometry_socket, sculpt_node.inputs['Geometry'])
        node_tree.links.new(distance_socket, sculpt_node.inputs['Distance'])

        node_tree.links.new(sculpt_node.outputs['Geometry'], switch_node.inputs[14])  # False (not muted)
        node_tree.links.new(geometry_socket, switch_node.inputs[15])  # True (muted)

        geometry_socket = switch_node.outputs[6]

    return geometry_socket


def _ensure_terrain_doodad_sculpt_modifier_node_group(name: str, terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    inputs = {('NodeSocketGeometry', 'Geometry')}
    outputs = {('NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(name, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    geometry_socket = input_node.outputs['Geometry']

    for terrain_doodad in terrain_doodads:
        geometry_socket = _add_sculpt_layers_to_node_tree(node_tree, geometry_socket, terrain_doodad)

    node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return node_tree


def _add_paint_layer_to_node_tree(node_tree: NodeTree, geometry_socket: NodeSocket,
                                  paint_layer: 'BDK_PG_terrain_doodad_paint_layer',
                                  attribute_name: Optional[str] = None) -> NodeSocket:

    def add_paint_layer_driver(struct: bpy_struct, paint_layer: 'BDK_PG_terrain_doodad_paint_layer', data_path: str,
                               path: str = 'default_value'):
        driver = struct.driver_add(path).driver
        driver.type = 'AVERAGE'
        var = driver.variables.new()
        var.name = data_path
        var.type = 'SINGLE_PROP'
        var.targets[0].id = paint_layer.terrain_doodad_object
        var.targets[0].data_path = f"bdk.terrain_doodad.paint_layers[{paint_layer.index}].{data_path}"

    # Create a named attribute node for the distance.
    distance_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
    distance_attribute_node.inputs['Name'].default_value = paint_layer.terrain_doodad_object.bdk.terrain_doodad.id
    distance_attribute_node.data_type = 'FLOAT'
    distance_socket = distance_attribute_node.outputs[1]

    paint_node = node_tree.nodes.new(type='GeometryNodeGroup')
    paint_node.node_tree = ensure_paint_node_group()
    paint_node.label = 'Paint'

    if attribute_name is not None:
        paint_node.inputs['Attribute'].default_value = attribute_name
    else:
        if paint_layer.layer_type == 'PAINT':
            paint_node.inputs['Attribute'].default_value = paint_layer.paint_layer_id
        elif paint_layer.layer_type == 'DECO':
            paint_node.inputs['Attribute'].default_value = paint_layer.deco_layer_id

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'GEOMETRY'

    add_paint_layer_driver(switch_node.inputs[1], paint_layer, 'mute')
    add_paint_layer_driver(paint_node.inputs['Radius'], paint_layer, 'radius')
    add_paint_layer_driver(paint_node.inputs['Falloff Radius'], paint_layer, 'falloff_radius')
    add_paint_layer_driver(paint_node.inputs['Strength'], paint_layer, 'strength')
    add_paint_layer_driver(paint_node.inputs['Use Distance Noise'], paint_layer, 'use_distance_noise')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Distortion'], paint_layer, 'distance_noise_distortion')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Factor'], paint_layer, 'distance_noise_factor')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Offset'], paint_layer, 'distance_noise_offset')
    add_paint_layer_driver(paint_node.inputs['Interpolation Type'], paint_layer, 'interpolation_type')
    add_paint_layer_driver(paint_node.inputs['Operation'], paint_layer, 'operation')
    add_paint_layer_driver(paint_node.inputs['Noise Type'], paint_layer, 'noise_type')

    node_tree.links.new(geometry_socket, paint_node.inputs['Geometry'])
    node_tree.links.new(distance_socket, paint_node.inputs['Distance'])
    node_tree.links.new(paint_node.outputs['Geometry'], switch_node.inputs[14])  # False (not muted)
    node_tree.links.new(geometry_socket, switch_node.inputs[15])  # True (muted)

    geometry_socket = switch_node.outputs[6]  # Output
    return geometry_socket


def _ensure_terrain_doodad_paint_modifier_node_group(name: str, terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    inputs = {('NodeSocketGeometry', 'Geometry')}
    outputs = {('NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(name, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    geometry_socket = input_node.outputs['Geometry']

    for terrain_doodad in terrain_doodads:
        for paint_layer in filter(lambda x: x.layer_type == 'PAINT', terrain_doodad.paint_layers):
            geometry_socket = _add_paint_layer_to_node_tree(node_tree, geometry_socket, paint_layer)

    node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return node_tree


def _ensure_terrain_doodad_deco_modifier_node_group(name: str, terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    inputs = {('NodeSocketGeometry', 'Geometry')}
    outputs = {('NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(name, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    geometry_socket = input_node.outputs['Geometry']

    node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    for terrain_doodad in terrain_doodads:
        for paint_layer in filter(lambda x: x.layer_type == 'DECO', terrain_doodad.paint_layers):
            geometry_socket = _add_paint_layer_to_node_tree(node_tree, geometry_socket, paint_layer)

    node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return node_tree


def create_terrain_doodad_bake_node_tree(terrain_doodad: 'BDK_PG_terrain_doodad') -> NodeTree:
    """
    Creates a node tree for baking a terrain doodad.
    :param terrain_doodad: The terrain doodad to make a baking node tree for.
    :return: The terrain doodad baking node tree.
    """
    inputs = {('NodeSocketGeometry', 'Geometry')}
    outputs = {('NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(uuid.uuid4().hex, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    geometry_socket = input_node.outputs['Geometry']

    # Add sculpt layers for the doodad.
    geometry_socket = _add_sculpt_layers_to_node_tree(node_tree, geometry_socket, terrain_doodad)

    # Add the paint layers for the doodad.
    for paint_layer in terrain_doodad.paint_layers:
        geometry_socket = _add_paint_layer_to_node_tree(node_tree, geometry_socket, paint_layer)

    node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return node_tree
