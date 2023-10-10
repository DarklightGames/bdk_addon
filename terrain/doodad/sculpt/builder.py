from bpy.types import NodeTree

from ...kernel import ensure_noise_node_group
from ....node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, ensure_interpolation_node_tree


def ensure_sculpt_noise_node_group():
    # Create a new geometry node group.
    items = {
        ('INPUT', 'NodeSocketFloat', 'Distance'),
        ('INPUT', 'NodeSocketFloat', 'Radius'),
        ('INPUT', 'NodeSocketInt', 'Noise Type'),
        ('INPUT', 'NodeSocketFloat', 'Noise Strength'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Roughness'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Distortion'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Scale'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Lacunarity'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Detail'),
        ('OUTPUT', 'NodeSocketFloat', 'Offset')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        # Nodes
        multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        multiply_node.operation = 'MULTIPLY'

        multiply_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
        multiply_node_2.operation = 'MULTIPLY'

        noise_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        noise_group_node.node_tree = ensure_noise_node_group()

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
        node_tree.links.new(input_node.outputs['Noise Type'], noise_group_node.inputs['Noise Type'])
        node_tree.links.new(input_node.outputs['Perlin Noise Roughness'], noise_group_node.inputs['Perlin Noise Roughness'])
        node_tree.links.new(input_node.outputs['Perlin Noise Distortion'], noise_group_node.inputs['Perlin Noise Distortion'])
        node_tree.links.new(input_node.outputs['Perlin Noise Scale'], noise_group_node.inputs['Perlin Noise Scale'])
        node_tree.links.new(input_node.outputs['Perlin Noise Lacunarity'], noise_group_node.inputs['Perlin Noise Lacunarity'])
        node_tree.links.new(input_node.outputs['Perlin Noise Detail'], noise_group_node.inputs['Perlin Noise Detail'])

        # Internal
        node_tree.links.new(noise_group_node.outputs['Value'], map_range_node.inputs['Value'])
        node_tree.links.new(divide_node.outputs['Value'], subtract_node.inputs[1])
        node_tree.links.new(subtract_node.outputs['Value'], multiply_node_2.inputs[0])
        node_tree.links.new(map_range_node.outputs['Result'], multiply_node_2.inputs[1])
        node_tree.links.new(multiply_node_2.outputs['Value'], multiply_node.inputs[0])

        # Output
        node_tree.links.new(multiply_node.outputs['Value'], output_node.inputs['Offset'])

    return ensure_geometry_node_tree('BDK Noise 2 (deprecated)', items, build_function)


def ensure_sculpt_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT','NodeSocketFloat', 'Distance'),
        ('INPUT','NodeSocketInt', 'Interpolation Type'),
        ('INPUT','NodeSocketFloat', 'Radius'),
        ('INPUT','NodeSocketFloat', 'Falloff Radius'),
        ('INPUT','NodeSocketFloat', 'Depth'),
        ('INPUT','NodeSocketFloat', 'Noise Strength'),
        ('INPUT','NodeSocketFloat', 'Perlin Noise Roughness'),
        ('INPUT','NodeSocketFloat', 'Perlin Noise Distortion'),
        ('INPUT','NodeSocketFloat', 'Perlin Noise Scale'),
        ('INPUT','NodeSocketFloat', 'Perlin Noise Lacunarity'),
        ('INPUT','NodeSocketFloat', 'Perlin Noise Detail'),
        ('INPUT','NodeSocketBool', 'Use Noise'),
        ('INPUT','NodeSocketFloat', 'Noise Radius Factor'),
        ('INPUT', 'NodeSocketInt', 'Noise Type'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
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
        node_tree.links.new(input_node.outputs['Noise Type'], noise_node.inputs['Noise Type'])
        node_tree.links.new(input_node.outputs['Perlin Noise Roughness'], noise_node.inputs['Perlin Noise Roughness'])
        node_tree.links.new(input_node.outputs['Perlin Noise Distortion'], noise_node.inputs['Perlin Noise Distortion'])
        node_tree.links.new(input_node.outputs['Perlin Noise Scale'], noise_node.inputs['Perlin Noise Scale'])
        node_tree.links.new(input_node.outputs['Perlin Noise Lacunarity'], noise_node.inputs['Perlin Noise Lacunarity'])
        node_tree.links.new(input_node.outputs['Perlin Noise Detail'], noise_node.inputs['Perlin Noise Detail'])
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

    return ensure_geometry_node_tree('BDK Terrain Doodad Sculpt Layer', items, build_function)
