from typing import cast

import bpy
from uuid import uuid4
from bpy.types import NodeTree, Context, Object, NodeSocket, Node

from ...units import meters_to_unreal


def add_driver_to_node_socket(node_socket: NodeSocket, target_object: Object, data_path: str):
    driver = node_socket.driver_add('default_value').driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = target_object
    var.targets[0].data_path = f"[\"{data_path}\"]"


def add_sculpt_layer_driver_to_node(node: Node,
                                        node_path: str,
                                        sculpt_layer: 'BDK_PG_terrain_object_sculpt_layer',
                                        data_path: str):
    driver = node.driver_add(node_path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = sculpt_layer.terrain_object
    var.targets[0].data_path = f"bdk.terrain_object.sculpt_layers[{sculpt_layer.index}].{data_path}"


def add_paint_layer_driver_to_node(node: Node,
                                       node_path: str,
                                       paint_layer: 'BDK_PG_terrain_object_paint_layer',
                                       data_path: str):
    driver = node.driver_add(node_path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = paint_layer.terrain_object
    var.targets[0].data_path = f"bdk.terrain_object.paint_layers[{paint_layer.index}].{data_path}"


def add_sculpt_layer_driver_to_node_socket(node_socket: NodeSocket, sculpt_layer: 'BDK_PG_terrain_object_sculpt_layer', data_path: str):
    driver = node_socket.driver_add('default_value').driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = sculpt_layer.terrain_object
    var.targets[0].data_path = f"bdk.terrain_object.sculpt_layers[{sculpt_layer.index}].{data_path}"


def add_paint_layer_driver_to_node_socket(node_socket: NodeSocket, paint_layer: 'BDK_PG_terrain_object_paint_layer', data_path: str):
    driver = node_socket.driver_add('default_value').driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = paint_layer.terrain_object
    var.targets[0].data_path = f"bdk.terrain_object.paint_layers[{paint_layer.index}].{data_path}"


def add_terrain_object_driver_to_node(node: Node, node_path: str, terrain_object: 'BDK_PG_terrain_object', data_path: str):
    driver = node.driver_add(node_path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = terrain_object.object
    var.targets[0].data_path = f"bdk.terrain_object.{data_path}"


def create_distance_to_curve_node_group(terrain_object: 'BDK_PG_terrain_object') -> NodeTree:
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')
    node_tree.inputs.new('NodeSocketGeometry', 'Curve')
    node_tree.outputs.new('NodeSocketFloat', 'Distance')

    # Create input and output nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

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

    # Add a new boolean node.
    boolean_node = node_tree.nodes.new(type='FunctionNodeInputBool')
    add_terrain_object_driver_to_node(boolean_node, 'boolean', terrain_object, 'is_3d')

    # Link the output of the boolean node to the switch input of the switch node.
    node_tree.links.new(boolean_node.outputs['Boolean'], switch_node.inputs['Switch'])

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
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')

    node_tree.inputs.new('NodeSocketFloat', 'Distance')
    node_tree.inputs.new('NodeSocketFloat', 'Radius')
    node_tree.inputs.new('NodeSocketFloat', 'Noise Strength')
    node_tree.inputs.new('NodeSocketFloat', 'Noise Roughness')
    node_tree.inputs.new('NodeSocketFloat', 'Noise Distortion')

    node_tree.outputs.new('NodeSocketFloat', 'Offset')

    # Create an input and output node.
    input_node = node_tree.nodes.new(type='NodeGroupInput')
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

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

    # Link the output of the divide node to the second input of the subtract node.
    node_tree.links.new(divide_node.outputs['Value'], subtract_node.inputs[1])

    # Link the output of the subtract node to the first input of the second multiply node.
    node_tree.links.new(subtract_node.outputs['Value'], multiply_node_2.inputs[0])

    # Link the map range result to the second input of the second multiply node.
    node_tree.links.new(map_range_node.outputs['Result'], multiply_node_2.inputs[1])

    node_tree.links.new(multiply_node.outputs['Value'], output_node.inputs['Offset'])

    return node_tree


def create_sculpt_node_group(terrain_object: 'BDK_PG_terrain_object', sculpt_layer: 'BDK_PG_terrain_object_sculpt_layer') -> NodeTree:
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')
    node_tree.inputs.new('NodeSocketGeometry', 'Geometry')
    node_tree.inputs.new('NodeSocketFloat', 'Distance')
    node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

    # Create the input nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')

    # Create the output nodes.
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

    # Add a value node and add a driver that maps to the component's radius.
    radius_value_node = node_tree.nodes.new(type='ShaderNodeValue')
    radius_value_node.label = 'Radius'
    add_sculpt_layer_driver_to_node_socket(radius_value_node.outputs[0], sculpt_layer, 'radius')

    # Add a subtract node.
    subtract_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
    subtract_node_2.operation = 'SUBTRACT'

    # Link the distance from the input node to the first input of the subtract node.
    node_tree.links.new(input_node.outputs['Distance'], subtract_node_2.inputs[0])
    node_tree.links.new(radius_value_node.outputs['Value'], subtract_node_2.inputs[1])

    # Add a value node and add a driver that maps to the component's falloff radius.
    falloff_radius_value_node = node_tree.nodes.new(type='ShaderNodeValue')
    falloff_radius_value_node.label = 'Falloff Radius'
    add_sculpt_layer_driver_to_node_socket(falloff_radius_value_node.outputs[0], sculpt_layer, 'falloff_radius')

    # Add a divide math node.
    divide_node = node_tree.nodes.new(type='ShaderNodeMath')
    divide_node.operation = 'DIVIDE'
    divide_node.use_clamp = True

    # Link the distance output of the geometry proximity node to the first input of the divide node.
    node_tree.links.new(subtract_node_2.outputs['Value'], divide_node.inputs[0])

    # Link the radius value node to the second input of the divide node.
    node_tree.links.new(falloff_radius_value_node.outputs['Value'], divide_node.inputs[1])

    # --------------------

    map_range_node = node_tree.nodes.new(type='ShaderNodeMapRange')
    map_range_node.data_type = 'FLOAT'
    map_range_node.interpolation_type = sculpt_layer.interpolation_type
    map_range_node.inputs['To Min'].default_value = 1.0
    map_range_node.inputs['To Max'].default_value = 0.0

    # Link the divide node to the second input of the subtract node.
    node_tree.links.new(divide_node.outputs['Value'], map_range_node.inputs[0])

    # Create a new value node and add a driver mapping to the depth custom property of the terrain object.
    depth_node = node_tree.nodes.new(type='ShaderNodeValue')
    depth_node.label = 'Depth'
    add_sculpt_layer_driver_to_node_socket(depth_node.outputs[0], sculpt_layer, 'depth')

    # Add a new multiply node.
    multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node.operation = 'MULTIPLY'

    # Link the values of the second subtract node and the depth node to the inputs of the multiply node.

    # Link the map range node to the first input of the multiply node.
    node_tree.links.new(map_range_node.outputs[0], multiply_node.inputs[0])
    node_tree.links.new(depth_node.outputs['Value'], multiply_node.inputs[1])

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

    add_sculpt_layer_driver_to_node_socket(noise_node.inputs['Noise Strength'], sculpt_layer, 'noise_strength')
    add_sculpt_layer_driver_to_node_socket(noise_node.inputs['Noise Roughness'], sculpt_layer, 'noise_roughness')
    add_sculpt_layer_driver_to_node_socket(noise_node.inputs['Noise Distortion'], sculpt_layer, 'noise_distortion')

    # Add a switch node of with input type float.
    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'FLOAT'
    switch_node.label = 'Use Noise'

    add_sculpt_layer_driver_to_node_socket(switch_node.inputs['Switch'], sculpt_layer, 'use_noise')

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
    node_tree.links.new(radius_value_node.outputs['Value'], add_node_2.inputs[0])
    node_tree.links.new(falloff_radius_value_node.outputs['Value'], add_node_2.inputs[1])

    # Add a new multiply node that multiplies the output of the add node by a second value driven by the noise radius factor.
    noise_radius_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    noise_radius_multiply_node.operation = 'MULTIPLY'

    node_tree.links.new(add_node_2.outputs['Value'], noise_radius_multiply_node.inputs[0])
    add_sculpt_layer_driver_to_node_socket(noise_radius_multiply_node.inputs[1], sculpt_layer, 'noise_radius_factor')

    # Link the value output of the add node to the radius input of the noise node.
    node_tree.links.new(noise_radius_multiply_node.outputs['Value'], noise_node.inputs['Radius'])

    return node_tree


def create_paint_node_group(terrain_object: Object, paint_layer: 'BDK_PG_terrain_object_paint_layer') -> NodeTree:
    # Create a new node group.
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')
    node_tree.inputs.new('NodeSocketGeometry', 'Geometry')
    node_tree.inputs.new('NodeSocketFloat', 'Distance')
    node_tree.inputs.new('NodeSocketString', 'Attribute')
    node_tree.outputs.new('NodeSocketGeometry', 'Geometry')
    node_tree.inputs.new('NodeSocketFloat', 'Radius')
    node_tree.inputs.new('NodeSocketFloat', 'Falloff Radius')
    node_tree.inputs.new('NodeSocketFloat', 'Strength')
    node_tree.inputs.new('NodeSocketFloat', 'Distance Noise Factor')
    node_tree.inputs.new('NodeSocketFloat', 'Distance Noise Distortion')
    node_tree.inputs.new('NodeSocketFloat', 'Distance Noise Offset')
    node_tree.inputs.new('NodeSocketBool', 'Use Distance Noise')

    # Create the input and output nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

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

    # Link the distance output of the input node to the first input of the subtract node.
    node_tree.links.new(input_node.outputs['Radius'], subtract_node.inputs[1])

    # Add a divide node.
    divide_node = node_tree.nodes.new(type='ShaderNodeMath')
    divide_node.operation = 'DIVIDE'

    # Link the output of the subtract node to the first input of the divide node.
    node_tree.links.new(subtract_node.outputs['Value'], divide_node.inputs[0])
    node_tree.links.new(input_node.outputs['Falloff Radius'], divide_node.inputs[1])

    # Add a map range node.
    map_range_node = node_tree.nodes.new(type='ShaderNodeMapRange')
    map_range_node.data_type = 'FLOAT'
    map_range_node.interpolation_type = paint_layer.interpolation_type
    map_range_node.inputs['To Min'].default_value = 1.0
    map_range_node.inputs['To Max'].default_value = 0.0

    # Link the value of the divide node to the value input of the float curve node.
    node_tree.links.new(divide_node.outputs['Value'], map_range_node.inputs[0])

    # Add an operation node.
    operation_node = node_tree.nodes.new(type='ShaderNodeMath')
    operation_node.operation = paint_layer.operation
    operation_node.use_clamp = True
    operation_node.label = 'Operation'

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
    node_tree.links.new(map_range_node.outputs[0], strength_multiply_node.inputs[0])
    node_tree.links.new(input_node.outputs['Strength'], strength_multiply_node.inputs[1])

    # Link the add node output value to the value input of the store named attribute node.
    node_tree.links.new(named_attribute_node.outputs[1], operation_node.inputs[0])
    node_tree.links.new(strength_multiply_node.outputs['Value'], operation_node.inputs[1])

    # Link the output of the add node to the value input of the store named attribute node.
    node_tree.links.new(operation_node.outputs['Value'], store_named_attribute_node.inputs[5])

    # Add a position input node.
    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

    # Add noise nodes.
    if paint_layer.noise_type == 'PERLIN':
        noise_node = node_tree.nodes.new(type='ShaderNodeTexNoise')
        noise_node.noise_dimensions = '2D'
        noise_node.inputs['Scale'].default_value = 0.5
        noise_node.inputs['Detail'].default_value = 16
        noise_node.inputs['Distortion'].default_value = 0.5

        node_tree.links.new(input_node.outputs['Distance Noise Distortion'], noise_node.inputs['Distortion'])
        node_tree.links.new(position_node.outputs['Position'], noise_node.inputs['Vector'])

        noise_value_socket = noise_node.outputs['Fac']
    elif paint_layer.noise_type == 'WHITE':
        noise_node = node_tree.nodes.new(type='ShaderNodeTexWhiteNoise')
        noise_node.label = 'Distance Noise'
        noise_node.noise_dimensions = '2D'

        node_tree.links.new(position_node.outputs['Position'], noise_node.inputs['Vector'])

        noise_value_socket = noise_node.outputs['Value']
    else:
        raise ValueError('Invalid noise type: %s' % paint_layer.noise_type)

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


def creat_distance_to_mesh_node_group(terrain_object):
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')
    node_tree.inputs.new('NodeSocketVector', 'Location')
    node_tree.outputs.new('NodeSocketFloat', 'Distance')

    # Create input and output nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

    # Add a new Position and Separate XYZ node.
    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
    separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'FLOAT'

    # Add a new boolean node.
    boolean_node = node_tree.nodes.new(type='FunctionNode')
    add_terrain_object_driver_to_node(boolean_node, 'boolean', terrain_object, 'is_3d')

    # Link the output of the boolean node to the switch input of the switch node.
    node_tree.links.new(boolean_node.outputs['Boolean'], switch_node.inputs['Switch'])

    return node_tree


def create_distance_to_empty_node_group(terrain_object):
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')
    node_tree.inputs.new('NodeSocketVector', 'Location')
    node_tree.outputs.new('NodeSocketFloat', 'Distance')

    # Create input and output nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

    # Add a new Position and Separate XYZ node.
    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
    separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'FLOAT'

    # Add a new boolean node.
    boolean_node = node_tree.nodes.new(type='FunctionNodeInputBool')
    add_terrain_object_driver_to_node(boolean_node, 'boolean', terrain_object, 'is_3d')

    # Link the output of the boolean node to the switch input of the switch node.
    node_tree.links.new(boolean_node.outputs['Boolean'], switch_node.inputs['Switch'])

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


def update_terrain_object_geometry_node_group(terrain_object: 'BDK_PG_terrain_object'):
    node_tree = terrain_object.node_tree

    node_tree.nodes.clear()
    node_tree.inputs.clear()
    node_tree.outputs.clear()

    node_tree.inputs.new('NodeSocketGeometry', 'Geometry')
    node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

    # Create the input nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')

    # Create the output nodes.
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

    # Add an object info node and set the object to the terrain object.
    object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    object_info_node.inputs[0].default_value = terrain_object.object
    object_info_node.transform_space = 'RELATIVE'

    distance_socket = None

    if terrain_object.object_type == 'CURVE':
        # Create a new distance to curve node group.
        distance_to_curve_node_group = create_distance_to_curve_node_group(terrain_object)

        # Add a new node group node.
        distance_to_curve_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_curve_node.node_tree = distance_to_curve_node_group
        distance_to_curve_node.label = 'Distance to Curve'

        node_tree.links.new(object_info_node.outputs['Geometry'], distance_to_curve_node.inputs['Curve'])

        distance_socket = distance_to_curve_node.outputs['Distance']

    elif terrain_object.object_type == 'MESH':
        pass
    elif terrain_object.object_type == 'EMPTY':
        distance_to_empty_node_group = create_distance_to_empty_node_group(terrain_object)

        distance_to_empty_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_empty_node.node_tree = distance_to_empty_node_group
        distance_to_empty_node.label = 'Distance to Empty'

        node_tree.links.new(object_info_node.outputs['Location'], distance_to_empty_node.inputs['Location'])

        distance_socket = distance_to_empty_node.outputs['Distance']

    # Store the calculated distance to a named attribute.
    # This is faster than recalculating the distance when evaluating each layer. (~20% faster)
    store_distance_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
    store_distance_attribute_node.inputs['Name'].default_value = 'distance'
    store_distance_attribute_node.data_type = 'FLOAT'
    store_distance_attribute_node.domain = 'POINT'

    # Link the geometry from the input node to the input of the store distance attribute node.
    node_tree.links.new(input_node.outputs['Geometry'], store_distance_attribute_node.inputs['Geometry'])

    # Link the distance socket to the input of the store distance attribute node.
    node_tree.links.new(distance_socket, store_distance_attribute_node.inputs[4])

    # Create a named attribute node for the distance.
    distance_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
    distance_attribute_node.inputs['Name'].default_value = 'distance'
    distance_attribute_node.data_type = 'FLOAT'

    distance_socket = distance_attribute_node.outputs[1]
    geometry_node_socket = store_distance_attribute_node.outputs['Geometry']

    # Now chain the node components together.
    for sculpt_layer in terrain_object.sculpt_layers:
        sculpt_node_group = create_sculpt_node_group(terrain_object, sculpt_layer)
        sculpt_node = node_tree.nodes.new(type='GeometryNodeGroup')
        sculpt_node.node_tree = sculpt_node_group
        sculpt_node.label = 'Sculpt'

        add_sculpt_layer_driver_to_node(sculpt_node, 'mute', sculpt_layer, 'mute')

        # Link the geometry socket of the object info node to the geometry socket of the sculpt node.
        node_tree.links.new(geometry_node_socket, sculpt_node.inputs['Geometry'])
        node_tree.links.new(distance_socket, sculpt_node.inputs['Distance'])

        geometry_node_socket = sculpt_node.outputs['Geometry']

    for paint_layer in terrain_object.paint_layers:
        paint_node_group = create_paint_node_group(terrain_object, paint_layer)
        paint_node = node_tree.nodes.new(type='GeometryNodeGroup')
        paint_node.node_tree = paint_node_group
        paint_node.label = 'Paint'
        paint_node.inputs['Attribute'].default_value = paint_layer.terrain_layer_id

        add_paint_layer_driver_to_node(paint_node, 'mute', paint_layer, 'mute')
        add_paint_layer_driver_to_node_socket(paint_node.inputs['Radius'], paint_layer, 'radius')
        add_paint_layer_driver_to_node_socket(paint_node.inputs['Falloff Radius'], paint_layer, 'falloff_radius')
        add_paint_layer_driver_to_node_socket(paint_node.inputs['Strength'], paint_layer, 'strength')
        add_paint_layer_driver_to_node_socket(paint_node.inputs['Use Distance Noise'], paint_layer, 'use_distance_noise')
        add_paint_layer_driver_to_node_socket(paint_node.inputs['Distance Noise Distortion'], paint_layer, 'distance_noise_distortion')
        add_paint_layer_driver_to_node_socket(paint_node.inputs['Distance Noise Factor'], paint_layer, 'distance_noise_factor')
        add_paint_layer_driver_to_node_socket(paint_node.inputs['Distance Noise Offset'], paint_layer, 'distance_noise_offset')

        node_tree.links.new(geometry_node_socket, paint_node.inputs['Geometry'])
        node_tree.links.new(distance_socket, paint_node.inputs['Distance'])

        geometry_node_socket = paint_node.outputs['Geometry']

    # Add a remove attribute node to remove the distance attribute.
    remove_distance_attribute_node = node_tree.nodes.new(type='GeometryNodeRemoveAttribute')
    remove_distance_attribute_node.inputs['Name'].default_value = 'distance'

    # Link the last geometry node socket to the output node's geometry socket.
    node_tree.links.new(geometry_node_socket, remove_distance_attribute_node.inputs['Geometry'])
    node_tree.links.new(remove_distance_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])


def create_terrain_object(context: Context,
                          terrain_info_object: Object,
                          object_type: str = 'CURVE'
                          ) -> Object:
    """
    Creates a terrain object of the specified type.
    Note that this function does not add the terrain object to the scene. That is the responsibility of the caller.
    :param context:
    :param terrain_info_object:
    :param object_type: The type of object to create. Valid values are 'CURVE', 'MESH' and 'EMPTY'
    :return:
    """
    terrain_object_name = uuid4().hex

    if object_type == 'CURVE':
        object_data = bpy.data.curves.new(name=terrain_object_name, type='CURVE')
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
        object_data = bpy.data.meshes.new(name=terrain_object_name)
        # TODO: Add a default mesh (just a square plane for now).

    bpy_object = bpy.data.objects.new(name=terrain_object_name, object_data=object_data)

    if object_type == 'EMPTY':
        bpy_object.empty_display_type = 'CIRCLE'
        bpy_object.empty_display_size = meters_to_unreal(10.0)
        # Set the delta transform to the terrain info object's rotation.
        bpy_object.delta_rotation_euler = (0, 0, 0)

    bpy_object.bdk.type = 'TERRAIN_OBJECT'
    bpy_object.bdk.terrain_object.id = terrain_object_name
    bpy_object.bdk.terrain_object.object_type = object_type
    bpy_object.bdk.terrain_object.terrain_info_object = terrain_info_object
    bpy_object.bdk.terrain_object.object = bpy_object
    bpy_object.bdk.terrain_object.node_tree = bpy.data.node_groups.new(name=terrain_object_name, type='GeometryNodeTree')
    bpy_object.show_in_front = True
    bpy_object.lock_location = (False, False, True)

    terrain_object = bpy_object.bdk.terrain_object

    # Add sculpt and paint components.
    # In the future, we will allow the user to select a preset for the terrain object.
    sculpt_layer = terrain_object.sculpt_layers.add()
    sculpt_layer.terrain_object = terrain_object.object

    paint_layer = terrain_object.paint_layers.add()
    paint_layer.terrain_object = terrain_object.object

    # Set the location of the curve object to the 3D cursor.
    bpy_object.location = context.scene.cursor.location

    # Add a geometry node modifier to the terrain info object.
    modifier = terrain_info_object.modifiers.new(name=terrain_object_name, type='NODES')
    modifier.node_group = bpy_object.bdk.terrain_object.node_tree
    modifier.show_on_cage = True

    update_terrain_object_geometry_node_group(bpy_object.bdk.terrain_object)

    return bpy_object
