from bpy.types import NodeTree

from ....node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, ensure_interpolation_node_tree


def ensure_sculpt_noise_node_group():
    # Create a new geometry node group.
    inputs = {
        ('NodeSocketFloat', 'Distance'),
        ('NodeSocketFloat', 'Radius'),
        ('NodeSocketFloat', 'Noise Strength'),
        ('NodeSocketFloat', 'Noise Roughness'),
        ('NodeSocketFloat', 'Noise Distortion'),
    }
    outputs = {('NodeSocketFloat', 'Offset')}
    node_tree = ensure_geometry_node_tree('BDK Noise 2 (deprecated)', inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    # Nodes
    multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node.operation = 'MULTIPLY'

    multiply_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node_2.operation = 'MULTIPLY'

    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

    noise_texture_node = node_tree.nodes.new(type='ShaderNodeTexNoise')
    noise_texture_node.noise_dimensions = '2D'
    noise_texture_node.inputs['Scale'].default_value = 1.0

    map_range_node = node_tree.nodes.new(type='ShaderNodeMapRange')
    map_range_node.data_type = 'FLOAT'
    map_range_node.inputs['To Min'].default_value = -0.5
    map_range_node.inputs['To Max'].default_value = 0.5

    subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
    subtract_node.operation = 'SUBTRACT'
    subtract_node.inputs[0].default_value = 1.0

    divide_node = node_tree.nodes.new(type='ShaderNodeMath')
    divide_node.operation = 'DIVIDE'
    divide_node.use_clamp = True

    # Input
    node_tree.links.new(input_node.outputs['Distance'], divide_node.inputs[0])
    node_tree.links.new(input_node.outputs['Radius'], divide_node.inputs[1])
    node_tree.links.new(input_node.outputs['Noise Strength'], multiply_node.inputs[1])
    node_tree.links.new(input_node.outputs['Noise Roughness'], noise_texture_node.inputs['Roughness'])
    node_tree.links.new(input_node.outputs['Noise Distortion'], noise_texture_node.inputs['Distortion'])

    # Internal
    node_tree.links.new(position_node.outputs['Position'], noise_texture_node.inputs['Vector'])
    node_tree.links.new(noise_texture_node.outputs['Fac'], map_range_node.inputs['Value'])
    node_tree.links.new(divide_node.outputs['Value'], subtract_node.inputs[1])
    node_tree.links.new(subtract_node.outputs['Value'], multiply_node_2.inputs[0])
    node_tree.links.new(map_range_node.outputs['Result'], multiply_node_2.inputs[1])
    node_tree.links.new(multiply_node_2.outputs['Value'], multiply_node.inputs[0])

    # Output
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

    subtract_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
    subtract_node_2.operation = 'SUBTRACT'

    divide_node = node_tree.nodes.new(type='ShaderNodeMath')
    divide_node.operation = 'DIVIDE'
    divide_node.use_clamp = True

    interpolation_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
    interpolation_group_node.node_tree = ensure_interpolation_node_tree()

    multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node.operation = 'MULTIPLY'

    combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

    set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

    noise_node = node_tree.nodes.new(type='GeometryNodeGroup')
    noise_node.node_tree = ensure_sculpt_noise_node_group()

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'FLOAT'
    switch_node.label = 'Use Distance Noise'

    add_node = node_tree.nodes.new(type='ShaderNodeMath')
    add_node.operation = 'ADD'

    add_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
    add_node_2.operation = 'ADD'

    noise_radius_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    noise_radius_multiply_node.operation = 'MULTIPLY'

    # Input
    node_tree.links.new(input_node.outputs['Distance'], subtract_node_2.inputs[0])
    node_tree.links.new(input_node.outputs['Radius'], subtract_node_2.inputs[1])
    node_tree.links.new(input_node.outputs['Interpolation Type'], interpolation_group_node.inputs['Interpolation Type'])
    node_tree.links.new(input_node.outputs['Depth'], multiply_node.inputs[1])
    node_tree.links.new(input_node.outputs['Noise Strength'], noise_node.inputs['Noise Strength'])
    node_tree.links.new(input_node.outputs['Noise Roughness'], noise_node.inputs['Noise Roughness'])
    node_tree.links.new(input_node.outputs['Noise Distortion'], noise_node.inputs['Noise Distortion'])
    node_tree.links.new(input_node.outputs['Use Noise'], switch_node.inputs['Switch'])
    node_tree.links.new(input_node.outputs['Geometry'], set_position_node.inputs['Geometry'])
    node_tree.links.new(input_node.outputs['Distance'], noise_node.inputs['Distance'])
    node_tree.links.new(input_node.outputs['Radius'], add_node_2.inputs[0])
    node_tree.links.new(input_node.outputs['Falloff Radius'], add_node_2.inputs[1])
    node_tree.links.new(input_node.outputs['Noise Radius Factor'], noise_radius_multiply_node.inputs[1])
    node_tree.links.new(input_node.outputs['Falloff Radius'], divide_node.inputs[1])

    # Internal
    node_tree.links.new(divide_node.outputs['Value'], interpolation_group_node.inputs['Value'])
    node_tree.links.new(interpolation_group_node.outputs['Value'], multiply_node.inputs[0])
    node_tree.links.new(combine_xyz_node.outputs['Vector'], set_position_node.inputs['Offset'])
    node_tree.links.new(noise_node.outputs['Offset'], switch_node.inputs['True'])
    node_tree.links.new(multiply_node.outputs['Value'], add_node.inputs[0])
    node_tree.links.new(switch_node.outputs['Output'], add_node.inputs[1])
    node_tree.links.new(add_node.outputs['Value'], combine_xyz_node.inputs['Z'])
    node_tree.links.new(add_node_2.outputs['Value'], noise_radius_multiply_node.inputs[0])
    node_tree.links.new(noise_radius_multiply_node.outputs['Value'], noise_node.inputs['Radius'])
    node_tree.links.new(subtract_node_2.outputs['Value'], divide_node.inputs[0])

    # Output
    node_tree.links.new(set_position_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return node_tree
