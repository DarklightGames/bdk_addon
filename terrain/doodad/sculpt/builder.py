from bpy.types import NodeTree

from ....node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, ensure_interpolation_node_tree


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

    # Add interpolation node group.
    interpolation_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
    interpolation_group_node.node_tree = ensure_interpolation_node_tree()
    node_tree.links.new(input_node.outputs['Interpolation Type'], interpolation_group_node.inputs['Interpolation Type'])
    node_tree.links.new(divide_node.outputs['Value'], interpolation_group_node.inputs['Value'])

    # Add a new multiply node.
    multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node.operation = 'MULTIPLY'

    # Link the map range node to the first input of the multiply node.
    node_tree.links.new(interpolation_group_node.outputs['Value'], multiply_node.inputs[0])
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
    noise_node.node_tree = ensure_sculpt_noise_node_group()

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
