import os.path
from typing import Optional, Iterable, AbstractSet, Tuple, List, Callable

import bpy
from bpy.types import NodeTree, NodeSocket, Node

from .data import map_range_interpolation_type_items


def should_rebuild_node_tree(node_tree: NodeTree, source_file: str) -> bool:
    """
    Determines if the node tree should be rebuilt.
    :param node_tree: The node tree to check.
    :param source_file: The file that the node tree was created from.
    :return: True if the node tree should be rebuilt, otherwise False.
    """

    # Check if the node tree was created by a different version of the addon.
    mtime = os.path.getmtime(source_file)
    if mtime != node_tree.bdk.mtime:
        return True
    return False

def ensure_terrain_layer_node_operation_node_tree() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketInt', 'Operation'),
        ('INPUT', 'NodeSocketFloat', 'Value 1'),
        ('INPUT', 'NodeSocketFloat', 'Value 2'),
        ('OUTPUT', 'NodeSocketFloat', 'Value')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)
        output_socket = add_operation_switch_nodes(
            node_tree,
            input_node.outputs['Operation'],
            input_node.outputs['Value 1'],
            input_node.outputs['Value 2'],
            ['ADD', 'SUBTRACT', 'MULTIPLY', 'MAXIMUM', 'MINIMUM'],
        )
        node_tree.links.new(output_socket, output_node.inputs['Value'])

    return ensure_geometry_node_tree('BDK Terrain Layer Node Operation', items, build_function)


def add_operation_switch_nodes(
        node_tree: NodeTree,
        operation_socket: NodeSocket,
        value_1_socket: Optional[NodeSocket],
        value_2_socket: Optional[NodeSocket],
        operations: Iterable[str]
) -> NodeSocket:

    last_output_node_socket: Optional[NodeSocket] = None

    for index, operation in enumerate(operations):
        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'
        compare_node.inputs[3].default_value = index
        node_tree.links.new(operation_socket, compare_node.inputs[2])

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])

        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = operation
        math_node.inputs[0].default_value = 0.0
        math_node.inputs[1].default_value = 0.0

        if value_1_socket:
            node_tree.links.new(value_1_socket, math_node.inputs[0])

        if value_2_socket:
            node_tree.links.new(value_2_socket, math_node.inputs[1])

        node_tree.links.new(math_node.outputs['Value'], switch_node.inputs['True'])

        if last_output_node_socket:
            node_tree.links.new(last_output_node_socket, switch_node.inputs['False'])

        last_output_node_socket = switch_node.outputs[0]  # Output

    return last_output_node_socket


def ensure_interpolation_node_tree() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketInt', 'Interpolation Type'),
        ('INPUT', 'NodeSocketFloat', 'Value'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        last_output_node_socket: Optional[NodeSocket] = None

        for index, interpolation_type in enumerate(map_range_interpolation_type_items):
            compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
            compare_node.data_type = 'INT'
            compare_node.operation = 'EQUAL'
            compare_node.inputs[3].default_value = index
            node_tree.links.new(input_node.outputs['Interpolation Type'], compare_node.inputs[2])

            switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
            switch_node.input_type = 'FLOAT'

            node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])

            map_range_node = node_tree.nodes.new(type='ShaderNodeMapRange')
            map_range_node.data_type = 'FLOAT'
            map_range_node.interpolation_type = interpolation_type[0]
            map_range_node.inputs[3].default_value = 1.0  # To Min
            map_range_node.inputs[4].default_value = 0.0  # To Max

            node_tree.links.new(input_node.outputs['Value'], map_range_node.inputs[0])
            node_tree.links.new(map_range_node.outputs[0], switch_node.inputs['True'])

            if last_output_node_socket:
                node_tree.links.new(last_output_node_socket, switch_node.inputs['False'])

            last_output_node_socket = switch_node.outputs[0]  # Output

        if last_output_node_socket:
            node_tree.links.new(last_output_node_socket, output_node.inputs['Value'])

    return ensure_geometry_node_tree('BDK Interpolation', items, build_function)


def add_noise_type_switch_nodes(
        node_tree: NodeTree,
        vector_socket: NodeSocket,
        noise_type_socket: NodeSocket,
        noise_distortion_socket: Optional[NodeSocket],
        noise_roughness_socket: Optional[NodeSocket],
) -> NodeSocket:

    """
    Adds a noise type node setup to the node tree.
    :param node_tree: The node tree to add the nodes to.
    :param vector_socket: The node socket that has the vector value.
    :param noise_type_socket: The node socket that has the noise type value.
    :param noise_distortion_socket: The node socket for the noise distortion value.
    :param noise_roughness_socket:
    :return: The noise value node socket.
    """

    noise_types = ['PERLIN', 'WHITE']

    last_output_node_socket: Optional[NodeSocket] = None

    for index, noise_type in enumerate(noise_types):
        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'
        compare_node.inputs[3].default_value = index
        node_tree.links.new(noise_type_socket, compare_node.inputs[2])

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])

        noise_value_socket = None

        if noise_type == 'PERLIN':
            noise_node = node_tree.nodes.new(type='ShaderNodeTexNoise')
            noise_node.noise_dimensions = '2D'
            noise_node.inputs['Scale'].default_value = 0.5
            noise_node.inputs['Detail'].default_value = 16
            noise_node.inputs['Distortion'].default_value = 0.5

            if noise_distortion_socket:
                node_tree.links.new(noise_distortion_socket, noise_node.inputs['Distortion'])

            if noise_roughness_socket:
                node_tree.links.new(noise_roughness_socket, noise_node.inputs['Roughness'])

            node_tree.links.new(vector_socket, noise_node.inputs['Vector'])
            noise_value_socket = noise_node.outputs['Fac']
        elif noise_type == 'WHITE':
            noise_node = node_tree.nodes.new(type='ShaderNodeTexWhiteNoise')
            noise_node.noise_dimensions = '2D'
            noise_value_socket = noise_node.outputs['Value']

        node_tree.links.new(noise_value_socket, switch_node.inputs['True'])

        if last_output_node_socket:
            node_tree.links.new(last_output_node_socket, switch_node.inputs['False'])

        last_output_node_socket = switch_node.outputs[0]  # Output

    return last_output_node_socket


def ensure_geometry_node_tree(name: str, items: AbstractSet[Tuple[str, str, str]], build_function: Callable[[NodeTree], None], should_force_build: bool = False) -> NodeTree:
    """
    Ensures that a geometry node tree with the given name, inputs and outputs exists.
    """
    return ensure_node_tree(name, 'GeometryNodeTree', items, build_function, should_force_build)


def ensure_shader_node_tree(
    name: str, items: AbstractSet[Tuple[str, str, str]], build_function: Callable[[NodeTree], None], should_force_build: bool = False) -> NodeTree:
    """
    Ensures that a shader node tree with the given name, inputs and outputs exists.
    """
    return ensure_node_tree(name, 'ShaderNodeTree', items, build_function, should_force_build)


def ensure_node_tree(name: str,
                     node_group_type: str,
                     items: AbstractSet[Tuple[str, str, str]],
                     build_function: Callable[[NodeTree], None],
                     should_force_build: bool = False
                     ) -> NodeTree:
    """
    Gets or creates a node tree with the given name, type, inputs and outputs.
    """
    if name in bpy.data.node_groups:
        node_tree = bpy.data.node_groups[name]
    else:
        node_tree = bpy.data.node_groups.new(name=name, type=node_group_type)

    def get_node_tree_socket_interface_item(node_tree: NodeTree, in_out: str, name: str, socket_type: str):
        for index, item in enumerate(node_tree.interface.items_tree):
            if item.item_type == 'SOCKET' and item.in_out ==  in_out and item.name == name and item.socket_type == socket_type:
                return item
        return None

    # Compare the inputs and outputs of the node tree with the given inputs and outputs.
    # If they are different, clear the inputs and outputs and add the new ones.
    node_tree_items = set(map(lambda x: (x.in_out, x.bl_socket_idname, x.name), node_tree.interface.items_tree))

    # For items that do not exist in the node tree, add them.
    items_to_add = (items - node_tree_items)
    for in_out, socket_type, name in items_to_add:
        node_tree.interface.new_socket(name, in_out=in_out, socket_type=socket_type)

    # For items that exist in the node tree but not in the given items, remove them.
    inputs_to_remove = (node_tree_items - items)
    for in_out, socket_type, name in inputs_to_remove:
        item = get_node_tree_socket_interface_item(node_tree, in_out, name, socket_type)
        node_tree.interface.remove(item)

    # Hash the build function byte-code.
    build_hash = hex(hash(build_function.__code__.co_code))

    # Check if the node tree needs to be rebuilt.
    should_build = False
    if should_force_build:
        should_build = True
    else:
        build_hash_changed = node_tree.bdk.build_hash != build_hash
        if build_hash_changed:
            should_build = True

    if should_build:
        # Clear the node tree.
        node_tree.nodes.clear()

        # Rebuild the node tree using the given build function.
        build_function(node_tree)

        # Update the node tree's build code
        node_tree.bdk.build_hash = build_hash

    return node_tree


def ensure_input_and_output_nodes(node_tree: NodeTree) -> Tuple[Node, Node]:
    """
    Ensures that the node tree has input and output nodes.
    :param node_tree: The node tree to check and potentially add input and output nodes to.
    :return: The input and output nodes.
    """

    # Check if the node tree already has input and output nodes.
    # If it does, return them.
    input_node = None
    output_node = None
    for node in node_tree.nodes:
        if node.bl_idname == 'NodeGroupInput':
            input_node = node
        elif node.bl_idname == 'NodeGroupOutput':
            output_node = node

    input_node = node_tree.nodes.new(type='NodeGroupInput') if input_node is None else input_node
    output_node = node_tree.nodes.new(type='NodeGroupOutput') if output_node is None else output_node

    return input_node, output_node


def ensure_curve_modifier_node_tree() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketInt', 'Trim Mode'),
        ('INPUT', 'NodeSocketFloat', 'Trim Factor Start'),
        ('INPUT', 'NodeSocketFloat', 'Trim Factor End'),
        ('INPUT', 'NodeSocketFloat', 'Trim Length Start'),
        ('INPUT', 'NodeSocketFloat', 'Trim Length End'),
        ('INPUT', 'NodeSocketFloat', 'Normal Offset'),
        ('INPUT', 'NodeSocketBool', 'Is Curve Reversed'),
        ('OUTPUT', 'NodeSocketGeometry', 'Curve'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        reverse_curve_node = node_tree.nodes.new(type='GeometryNodeReverseCurve')

        reverse_curve_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        reverse_curve_switch_node.input_type = 'GEOMETRY'
        reverse_curve_switch_node.label = 'Reverse Curve?'

        trim_curve_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        trim_curve_group_node.node_tree = ensure_trim_curve_node_tree()

        curve_normal_offset_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        curve_normal_offset_group_node.node_tree = ensure_curve_normal_offset_node_tree()

        # Input
        node_tree.links.new(input_node.outputs['Normal Offset'], curve_normal_offset_group_node.inputs['Normal Offset'])
        node_tree.links.new(input_node.outputs['Is Curve Reversed'], reverse_curve_switch_node.inputs[1])
        node_tree.links.new(input_node.outputs['Curve'], reverse_curve_switch_node.inputs[14])  # False
        node_tree.links.new(input_node.outputs['Curve'], reverse_curve_node.inputs['Curve'])
        node_tree.links.new(input_node.outputs['Trim Mode'], trim_curve_group_node.inputs['Mode'])
        node_tree.links.new(input_node.outputs['Trim Factor Start'], trim_curve_group_node.inputs['Factor Start'])
        node_tree.links.new(input_node.outputs['Trim Factor End'], trim_curve_group_node.inputs['Factor End'])
        node_tree.links.new(input_node.outputs['Trim Length Start'], trim_curve_group_node.inputs['Length Start'])
        node_tree.links.new(input_node.outputs['Trim Length End'], trim_curve_group_node.inputs['Length End'])

        # Internal
        node_tree.links.new(reverse_curve_node.outputs['Curve'], reverse_curve_switch_node.inputs[15])  # True
        node_tree.links.new(reverse_curve_switch_node.outputs[6], trim_curve_group_node.outputs['Curve'])
        node_tree.links.new(reverse_curve_switch_node.outputs[6], trim_curve_group_node.inputs['Curve'])
        node_tree.links.new(trim_curve_group_node.outputs['Curve'], curve_normal_offset_group_node.inputs['Curve'])

        # Output
        node_tree.links.new(curve_normal_offset_group_node.outputs['Curve'], output_node.inputs['Curve'])

    return ensure_geometry_node_tree('BDK Curve Modifier', items, build_function)


def ensure_curve_normal_offset_node_tree() -> NodeTree:
    node_tree_items = {
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketFloat', 'Normal Offset'),
        ('OUTPUT', 'NodeSocketGeometry', 'Curve'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        # Add Set Position Node
        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

        # Add Resample Curve node.
        resample_curve_node = node_tree.nodes.new(type='GeometryNodeResampleCurve')
        resample_curve_node.mode = 'EVALUATED'

        # Add Vector Scale node.
        vector_scale_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_scale_node.operation = 'SCALE'

        # Add Input Normal node.
        input_normal_node = node_tree.nodes.new(type='GeometryNodeInputNormal')

        # Add Switch node.
        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'GEOMETRY'

        # Add Compare node.
        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.operation = 'EQUAL'

        node_tree.links.new(input_node.outputs['Normal Offset'], compare_node.inputs[0])  # A
        node_tree.links.new(input_node.outputs['Normal Offset'], vector_scale_node.inputs[3])  # Scale
        node_tree.links.new(input_node.outputs['Curve'], resample_curve_node.inputs['Curve'])
        node_tree.links.new(resample_curve_node.outputs['Curve'], set_position_node.inputs['Geometry'])

        node_tree.links.new(input_normal_node.outputs['Normal'], vector_scale_node.inputs[0])
        node_tree.links.new(input_node.outputs['Normal Offset'], vector_scale_node.inputs[1])

        node_tree.links.new(input_node.outputs['Curve'], switch_node.inputs[15])  # True
        node_tree.links.new(set_position_node.outputs['Geometry'], switch_node.inputs[14])  # False
        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs[1])  # Switch

        node_tree.links.new(vector_scale_node.outputs['Vector'], set_position_node.inputs['Offset'])
        node_tree.links.new(switch_node.outputs[6], output_node.inputs['Curve'])

    return ensure_geometry_node_tree('BDK Offset Curve Normal', node_tree_items, build_function)


def ensure_trim_curve_node_tree() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketInt', 'Mode'),
        ('INPUT', 'NodeSocketFloat', 'Factor Start'),
        ('INPUT', 'NodeSocketFloat', 'Factor End'),
        ('INPUT', 'NodeSocketFloat', 'Length Start'),
        ('INPUT', 'NodeSocketFloat', 'Length End'),
        ('OUTPUT', 'NodeSocketGeometry', 'Curve'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        trim_curve_factor_node = node_tree.nodes.new(type='GeometryNodeTrimCurve')
        trim_curve_factor_node.mode = 'FACTOR'

        trim_curve_length_node = node_tree.nodes.new(type='GeometryNodeTrimCurve')
        trim_curve_length_node.mode = 'LENGTH'

        curve_length_node = node_tree.nodes.new(type='GeometryNodeCurveLength')

        subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
        subtract_node.operation = 'SUBTRACT'

        trim_curve_output_socket = add_geometry_node_switch_nodes(
            node_tree,
            input_node.outputs['Mode'],
            [input_node.outputs['Curve'], trim_curve_factor_node.outputs['Curve'], trim_curve_length_node.outputs['Curve']],
            'GEOMETRY')

        # Inputs
        node_tree.links.new(input_node.outputs['Curve'], trim_curve_factor_node.inputs['Curve'])
        node_tree.links.new(input_node.outputs['Curve'], trim_curve_length_node.inputs['Curve'])
        node_tree.links.new(input_node.outputs['Curve'], curve_length_node.inputs['Curve'])
        node_tree.links.new(input_node.outputs['Factor Start'], trim_curve_factor_node.inputs['Start'])
        node_tree.links.new(input_node.outputs['Factor End'], trim_curve_factor_node.inputs['End'])
        node_tree.links.new(input_node.outputs['Length End'], subtract_node.inputs[1])
        node_tree.links.new(input_node.outputs['Length Start'], trim_curve_length_node.inputs[4])

        # Internal
        node_tree.links.new(curve_length_node.outputs['Length'], subtract_node.inputs[0])
        node_tree.links.new(subtract_node.outputs[0], trim_curve_length_node.inputs[5])
        node_tree.links.new(trim_curve_output_socket, output_node.inputs['Curve'])

        # Outputs
        node_tree.links.new(subtract_node.outputs['Value'], trim_curve_length_node.inputs[5])

    return ensure_geometry_node_tree('BDK Curve Trim', items, build_function)


def add_chained_math_nodes(node_tree: NodeTree, operation: str, value_sockets: List[NodeSocket]) -> Optional[NodeSocket]:
    if not value_sockets:
        return None
    output_socket = value_sockets[0]
    for value_socket in value_sockets[1:]:
        operation_node = node_tree.nodes.new(type='ShaderNodeMath')
        operation_node.operation = operation
        node_tree.links.new(output_socket, operation_node.inputs[0])
        node_tree.links.new(value_socket, operation_node.inputs[1])
        output_socket = operation_node.outputs[0]
    return output_socket


def add_geometry_node_switch_nodes(node_tree: NodeTree, switch_value_socket: NodeSocket, output_value_sockets: Iterable[NodeSocket], input_type: str = 'INT') -> Optional[NodeSocket]:
    previous_switch_output_socket = None
    output_socket = None

    valid_input_types = {'INT', 'GEOMETRY', 'VECTOR', 'FLOAT'}
    if input_type not in valid_input_types:
        raise ValueError(f'input_type must be {valid_input_types}, got {input_type}')

    for value_index, output_value_socket in enumerate(output_value_sockets):
        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = input_type

        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.operation = 'EQUAL'
        compare_node.data_type = 'INT'

        compare_node.inputs[3].default_value = value_index  # B
        switch_node.inputs[4].default_value = 0

        node_tree.links.new(switch_value_socket, compare_node.inputs[2])  # True

        match input_type:
            case 'INT':
                switch_switch_input_socket = switch_node.inputs[0]
                switch_false_input_socket = switch_node.inputs[4]
                switch_true_input_socket = switch_node.inputs[5]
                switch_output_socket = switch_node.outputs[1]
            case 'GEOMETRY':
                switch_switch_input_socket = switch_node.inputs[1]
                switch_false_input_socket = switch_node.inputs[14]
                switch_true_input_socket = switch_node.inputs[15]
                switch_output_socket = switch_node.outputs[6]
            case 'VECTOR':
                switch_switch_input_socket = switch_node.inputs[0]
                switch_false_input_socket = switch_node.inputs[8]
                switch_true_input_socket = switch_node.inputs[9]
                switch_output_socket = switch_node.outputs[3]
            case 'FLOAT':
                switch_switch_input_socket = switch_node.inputs[0]
                switch_false_input_socket = switch_node.inputs[2]
                switch_true_input_socket = switch_node.inputs[3]
                switch_output_socket = switch_node.outputs[0]
            case _:
                raise ValueError(f'input_type must be {valid_input_types}, got {input_type}')

        node_tree.links.new(compare_node.outputs[0], switch_switch_input_socket)  # Result -> Switch
        node_tree.links.new(output_value_socket, switch_true_input_socket)  # True
        output_socket = switch_output_socket

        if previous_switch_output_socket is not None:
            node_tree.links.new(previous_switch_output_socket, switch_false_input_socket)  # Output -> False

        previous_switch_output_socket = output_socket

    return output_socket


def ensure_weighted_index_node_tree() -> NodeTree:
    inputs = {
        ('OUTPUT', 'NodeSocketInt', 'Index'),
        ('INPUT', 'NodeSocketInt', 'Seed'),
        ('INPUT', 'NodeSocketFloat', 'Weight 0'),
        ('INPUT', 'NodeSocketFloat', 'Weight 1'),
        ('INPUT', 'NodeSocketFloat', 'Weight 2'),
        ('INPUT', 'NodeSocketFloat', 'Weight 3'),
        ('INPUT', 'NodeSocketFloat', 'Weight 4'),
        ('INPUT', 'NodeSocketFloat', 'Weight 5'),
        ('INPUT', 'NodeSocketFloat', 'Weight 6'),
        ('INPUT', 'NodeSocketFloat', 'Weight 7')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        last_sum_socket = None
        last_switch_false_socket = None
        first_switch_output_socket = None

        random_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        random_node.data_type = 'FLOAT'

        node_tree.links.new(input_node.outputs['Seed'], random_node.inputs['Seed'])

        for weight_index in range(8):
            sum_node = node_tree.nodes.new(type='ShaderNodeMath')
            sum_node.operation = 'ADD'
            sum_node.inputs[0].default_value = 0.0
            sum_node.inputs[1].default_value = 0.0
            sum_node.label = f'Sum {weight_index}'

            if last_sum_socket is not None:
                node_tree.links.new(last_sum_socket, sum_node.inputs[0])

            weight_socket = input_node.outputs[f'Weight {weight_index}']

            node_tree.links.new(weight_socket, sum_node.inputs[1])

            compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
            compare_node.operation = 'LESS_THAN'

            switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
            switch_node.input_type = 'INT'

            node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])
            switch_node.inputs[5].default_value = weight_index


            last_sum_socket = sum_node.outputs[0]

            if first_switch_output_socket is None:
                first_switch_output_socket = switch_node.outputs[1]

            if last_switch_false_socket is not None:
                node_tree.links.new(switch_node.outputs[1], last_switch_false_socket)

            last_switch_false_socket = switch_node.inputs[4]

            node_tree.links.new(random_node.outputs[1], compare_node.inputs[0])  # A
            node_tree.links.new(sum_node.outputs[0], compare_node.inputs[1])  # B

        node_tree.links.new(last_sum_socket, random_node.inputs[3])  # Sum of all weight used as the Max value of the random node.
        node_tree.links.new(first_switch_output_socket, output_node.inputs['Index'])

    return ensure_geometry_node_tree('BDK Weighted Index', inputs, build_function)


# def ensure_curve_extend_node_tree() -> NodeTree:
#     inputs = {('NodeSocketGeometry', 'Geometry'), ('NodeSocketFloat', 'Root Length'), ('NodeSocketFloat', 'Tip Length')}
#     outputs = {('NodeSocketGeometry', 'Geometry')}
#     node_tree = ensure_geometry_node_tree('BDK Extend Curve', inputs, outputs)
#     input_node, output_node = ensure_input_and_output_nodes(node_tree)
#
#     # Add Mesh to Curve node.
#     mesh_to_curve_node = node_tree.nodes.new(type='GeometryNodeMeshToCurve')
#     node_tree.links.new(mesh_to_curve_node.outputs['Curve'], output_node.inputs['Geometry'])
#
#     # Create a Curve tip and Curve root node group. (don't reuse the assets since they can change underfoot)
#
#     # Add Set Position nodes.
#     tip_set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')
#     root_set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')
#
#     # Add Curve Tip node group node.
#     curve_tip_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
#     curve_tip_node_group_node.node_tree = bpy.data.
