from bpy.types import NodeTree

from ...kernel import ensure_noise_node_group
from ....node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, ensure_interpolation_node_tree, \
    ensure_trim_curve_node_tree, ensure_curve_normal_offset_node_tree


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


def ensure_curve_modifier_node_group():
    items = {
        ('INPUT', 'NodeSocketObject', 'Terrain Doodad Object'),
        ('INPUT', 'NodeSocketBool', 'Reverse Curve'),
        ('INPUT', 'NodeSocketFloat', 'Curve Trim Factor Start'),
        ('INPUT', 'NodeSocketFloat', 'Curve Trim Factor End'),
        ('INPUT', 'NodeSocketFloat', 'Curve Trim Mode'),
        ('INPUT', 'NodeSocketFloat', 'Curve Trim Length Start'),
        ('INPUT', 'NodeSocketFloat', 'Curve Trim Length End'),
        ('INPUT', 'NodeSocketFloat', 'Curve Normal Offset'),
        ('OUTPUT', 'NodeSocketGeometry', 'Curve'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
        object_info_node.transform_space = 'RELATIVE'

        reverse_curve_node = node_tree.nodes.new(type='GeometryNodeReverseCurve')

        reverse_curve_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        reverse_curve_switch_node.input_type = 'GEOMETRY'

        curve_trim_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        curve_trim_node_group_node.node_tree = ensure_trim_curve_node_tree()

        offset_curve_normal_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        offset_curve_normal_node_group_node.node_tree = ensure_curve_normal_offset_node_tree()

        node_tree.links.new(input_node.outputs['Terrain Doodad Object'], object_info_node.inputs['Object'])
        node_tree.links.new(object_info_node.outputs['Curve'], reverse_curve_node.inputs['Curve'])
        node_tree.links.new(object_info_node.outputs['Curve'], curve_trim_node_group_node.inputs[14])  # False
        node_tree.links.new(reverse_curve_node.outputs['Curve'], reverse_curve_switch_node.inputs[15])  # True
        node_tree.links.new(reverse_curve_switch_node.outputs['Output'], curve_trim_node_group_node.inputs['Curve'])
        node_tree.links.new(curve_trim_node_group_node.outputs['Curve'], offset_curve_normal_node_group_node.inputs['Curve'])
        node_tree.links.new(input_node.outputs['Reverse Curve'], reverse_curve_switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Curve Trim Factor Start'], curve_trim_node_group_node.inputs['Factor Start'])
        node_tree.links.new(input_node.outputs['Curve Trim Factor End'], curve_trim_node_group_node.inputs['Factor End'])
        node_tree.links.new(input_node.outputs['Curve Trim Mode'], curve_trim_node_group_node.inputs['Trim Mode'])
        node_tree.links.new(input_node.outputs['Curve Trim Length Start'], curve_trim_node_group_node.inputs['Length Start'])
        node_tree.links.new(input_node.outputs['Curve Trim Length End'], curve_trim_node_group_node.inputs['Length End'])
        node_tree.links.new(input_node.outputs['Curve Normal Offset'], offset_curve_normal_node_group_node.inputs['Offset'])
        node_tree.links.new(offset_curve_normal_node_group_node.outputs['Curve'], output_node.inputs['Curve'])

    return ensure_geometry_node_tree('BDK Curve Modifier', items, build_function)

def ensure_sculpt_value_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketInt', 'Interpolation Type'),
        ('INPUT', 'NodeSocketFloat', 'Distance'),
        ('INPUT', 'NodeSocketFloat', 'Radius'),
        ('INPUT', 'NodeSocketFloat', 'Falloff Radius'),
        ('INPUT', 'NodeSocketFloat', 'Noise Strength'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Roughness'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Distortion'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Scale'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Lacunarity'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Detail'),
        ('INPUT', 'NodeSocketBool', 'Use Noise'),
        ('INPUT', 'NodeSocketFloat', 'Noise Radius Factor'),
        ('INPUT', 'NodeSocketInt', 'Noise Type'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
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

        noise_node = node_tree.nodes.new(type='GeometryNodeGroup')
        noise_node.node_tree = ensure_sculpt_noise_node_group()

        use_noise_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        use_noise_switch_node.input_type = 'FLOAT'
        use_noise_switch_node.label = 'Use Distance Noise'

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
        node_tree.links.new(input_node.outputs['Noise Strength'], noise_node.inputs['Noise Strength'])
        node_tree.links.new(input_node.outputs['Noise Type'], noise_node.inputs['Noise Type'])
        node_tree.links.new(input_node.outputs['Perlin Noise Roughness'], noise_node.inputs['Perlin Noise Roughness'])
        node_tree.links.new(input_node.outputs['Perlin Noise Distortion'], noise_node.inputs['Perlin Noise Distortion'])
        node_tree.links.new(input_node.outputs['Perlin Noise Scale'], noise_node.inputs['Perlin Noise Scale'])
        node_tree.links.new(input_node.outputs['Perlin Noise Lacunarity'], noise_node.inputs['Perlin Noise Lacunarity'])
        node_tree.links.new(input_node.outputs['Perlin Noise Detail'], noise_node.inputs['Perlin Noise Detail'])
        node_tree.links.new(input_node.outputs['Use Noise'], use_noise_switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Distance'], noise_node.inputs['Distance'])
        node_tree.links.new(input_node.outputs['Radius'], add_node_2.inputs[0])
        node_tree.links.new(input_node.outputs['Falloff Radius'], add_node_2.inputs[1])
        node_tree.links.new(input_node.outputs['Noise Radius Factor'], noise_radius_multiply_node.inputs[1])
        node_tree.links.new(input_node.outputs['Falloff Radius'], divide_node.inputs[1])

        # Internal
        node_tree.links.new(divide_node.outputs['Value'], interpolation_group_node.inputs['Value'])
        node_tree.links.new(interpolation_group_node.outputs['Value'], add_node.inputs[0])
        node_tree.links.new(use_noise_switch_node.outputs['Output'], add_node.inputs[1])

        # TODO: add_node.outputs['Value'] or interpolation_group_node.outputs['Value']
        #  I think this is the thing we want, as it is the raw influence value after noise, interpolation etc.
        #  Right now, our "set" operation is ignoring noise and is using the raw [0..1] influence value from the
        #  interpolation output, prior to being multiplied by the distance factor and having the noise added.
        #  We could have the noise changed to use a factor value instead of a distance value, which would allow us to
        #  use the noise values in the "set" operation. I think this would also be a bit cleaner.

        node_tree.links.new(add_node_2.outputs['Value'], noise_radius_multiply_node.inputs[0])
        node_tree.links.new(noise_radius_multiply_node.outputs['Value'], noise_node.inputs['Radius'])
        node_tree.links.new(noise_node.outputs['Offset'], use_noise_switch_node.inputs['True'])
        node_tree.links.new(subtract_node_2.outputs['Value'], divide_node.inputs[0])

        # Output
        node_tree.links.new(add_node.outputs['Value'], output_node.inputs['Value'])

    return ensure_geometry_node_tree('BDK Terrain Doodad Sculpt Layer', items, build_function)
