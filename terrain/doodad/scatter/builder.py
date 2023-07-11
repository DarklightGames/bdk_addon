import uuid

from bpy.types import Context, NodeTree, NodeSocket, Object, bpy_struct, ID

from ....units import meters_to_unreal
from ....helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes


snap_and_align_to_terrain_node_group_name = 'Snap and Align to Terrain'


def add_scatter_layer(terrain_doodad: 'BDK_PG_terrain_doodad') -> 'BDK_PG_terrain_doodad_scatter_layer':
    scatter_layer = terrain_doodad.scatter_layers.add()
    scatter_layer.id = uuid.uuid4().hex
    scatter_layer.terrain_doodad_object = terrain_doodad.object
    return scatter_layer


def add_scatter_layer_object(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> 'BDK_PG_terrain_doodad_scatter_layer_object':
    scatter_layer_object = scatter_layer.objects.add()
    scatter_layer_object.id = uuid.uuid4().hex
    scatter_layer_object.terrain_doodad_object = scatter_layer.terrain_doodad_object
    return scatter_layer_object


class TrimCurveSockets:
    def __init__(self, curve_socket: NodeSocket, factor_start_socket: NodeSocket, factor_end_socket: NodeSocket,
                    length_start_socket: NodeSocket, length_end_socket: NodeSocket
                 ):
        self.curve_socket = curve_socket
        self.factor_start_socket = factor_start_socket
        self.factor_end_socket = factor_end_socket
        self.length_start_socket = length_start_socket
        self.length_end_socket = length_end_socket


def add_trim_curve(node_tree: NodeTree, curve_socket: NodeSocket, mode_socket: NodeSocket) -> TrimCurveSockets:
    """
    Adds a set of nodes to the node tree that will output a trim curve based on the mode specified by the socket.
    :param node_tree:
    :param curve_socket:
    :param mode_socket:
    :return: The output socket of the trim curve node.
    """
    trim_curve_factor_node = node_tree.nodes.new(type='GeometryNodeTrimCurve')
    trim_curve_factor_node.mode = 'FACTOR'

    trim_curve_length_node = node_tree.nodes.new(type='GeometryNodeTrimCurve')
    trim_curve_length_node.mode = 'LENGTH'

    node_tree.links.new(curve_socket, trim_curve_factor_node.inputs['Curve'])
    node_tree.links.new(curve_socket, trim_curve_length_node.inputs['Curve'])

    compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
    compare_node.data_type = 'INT'
    compare_node.operation = 'EQUAL'

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'GEOMETRY'

    node_tree.links.new(mode_socket, compare_node.inputs[2])

    node_tree.links.new(compare_node.outputs[0], switch_node.inputs[1])  # Result -> Switch
    node_tree.links.new(trim_curve_factor_node.outputs['Curve'], switch_node.inputs[15])  # True
    node_tree.links.new(trim_curve_length_node.outputs['Curve'], switch_node.inputs[14])  # False

    # Add curve length subtract node.
    curve_length_node = node_tree.nodes.new(type='GeometryNodeCurveLength')
    node_tree.links.new(curve_socket, curve_length_node.inputs['Curve'])
    subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
    subtract_node.operation = 'SUBTRACT'
    node_tree.links.new(curve_length_node.outputs['Length'], subtract_node.inputs[0])
    node_tree.links.new(subtract_node.outputs[0], trim_curve_length_node.inputs[5])

    sockets = TrimCurveSockets(
        curve_socket=switch_node.outputs[6],
        factor_start_socket=trim_curve_factor_node.inputs[2],
        factor_end_socket=trim_curve_factor_node.inputs[3],
        length_start_socket=trim_curve_length_node.inputs[4],
        length_end_socket=subtract_node.inputs[1]
    )

    return sockets


def add_vector_xyz_switch(node_tree: NodeTree, vector_socket: NodeSocket, index_socket: NodeSocket) -> NodeSocket:
    """
    Adds a set of nodes to the node tree that will output the vector component specified by the index socket.
    :param node_tree:
    :param vector_socket:
    :param index_socket:
    :return:
    """
    separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
    node_tree.links.new(vector_socket, separate_xyz_node.inputs['Vector'])

    compare_index_x_node = node_tree.nodes.new(type='FunctionNodeCompare')
    compare_index_x_node.data_type = 'INT'
    compare_index_x_node.operation = 'EQUAL'

    node_tree.links.new(index_socket, compare_index_x_node.inputs[2])  # A

    switch_x_yz_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_x_yz_node.input_type = 'FLOAT'

    node_tree.links.new(compare_index_x_node.outputs['Result'], switch_x_yz_node.inputs[0])  # Result -> Switch
    node_tree.links.new(separate_xyz_node.outputs['X'], switch_x_yz_node.inputs[3])  # True

    compare_index_y_node = node_tree.nodes.new(type='FunctionNodeCompare')
    compare_index_y_node.data_type = 'INT'
    compare_index_y_node.operation = 'EQUAL'
    compare_index_y_node.inputs[3].default_value = 1

    switch_yz_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_yz_node.input_type = 'FLOAT'

    node_tree.links.new(index_socket, compare_index_y_node.inputs[2])  # A

    node_tree.links.new(compare_index_y_node.outputs['Result'], switch_yz_node.inputs[0])  # Result -> Switch
    node_tree.links.new(separate_xyz_node.outputs['Y'], switch_yz_node.inputs[3])  # True
    node_tree.links.new(separate_xyz_node.outputs['Z'], switch_yz_node.inputs[4])  # False

    node_tree.links.new(switch_yz_node.outputs[0], switch_x_yz_node.inputs[4])  # False

    return switch_x_yz_node.outputs[0]  # Output


def add_object_extents(node_tree: NodeTree, bpy_object: Object) -> NodeSocket:
    """
    Adds a set of nodes to the node tree that will output the extents of the object.
    :param node_tree:
    :param bpy_object:
    :return: The output socket representing the extents of the object.
    """
    object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    object_info_node.inputs[0].default_value = bpy_object

    bounding_box_node = node_tree.nodes.new(type='GeometryNodeBoundBox')

    vector_math_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
    vector_math_node.operation = 'SUBTRACT'

    node_tree.links.new(object_info_node.outputs['Geometry'], bounding_box_node.inputs['Geometry'])
    node_tree.links.new(bounding_box_node.outputs['Max'], vector_math_node.inputs[0])
    node_tree.links.new(bounding_box_node.outputs['Min'], vector_math_node.inputs[1])

    return vector_math_node.outputs['Vector']


def get_data_path_for_scatter_layer_object(scatter_layer_index: int, scatter_layer_object_index: int, data_path: str) -> str:
    return f"bdk.terrain_doodad.scatter_layers[{scatter_layer_index}].objects[{scatter_layer_object_index}].{data_path}"


def _add_scatter_layer_driver_ex(
        struct: bpy_struct, target_id: ID, data_path: str, index: int = -1, path: str = 'default_value',
        scatter_layer_index: int = 0):
    driver = struct.driver_add(path, index).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = target_id
    data_path = f"bdk.terrain_doodad.scatter_layers[{scatter_layer_index}].{data_path}"
    if index != -1:
        data_path += f"[{index}]"
    var.targets[0].data_path = data_path


def _add_scatter_layer_object_driver_ex(
        struct: bpy_struct, target_id: ID, data_path: str, index: int = -1, path: str = 'default_value',
        scatter_layer_index: int = 0, scatter_layer_object_index: int = 0):
    driver = struct.driver_add(path, index).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = target_id
    data_path = get_data_path_for_scatter_layer_object(scatter_layer_index, scatter_layer_object_index, data_path)
    if index != -1:
        data_path += f"[{index}]"
    var.targets[0].data_path = data_path


def ensure_terrain_snap_and_align_node_tree() -> NodeTree:
    inputs = {
        ('NodeSocketGeometry', 'Geometry'),
        ('NodeSocketObject', 'Terrain Info Object'),
    }
    outputs = {
        ('NodeSocketGeometry', 'Geometry'),
    }
    node_tree = ensure_geometry_node_tree(snap_and_align_to_terrain_node_group_name, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

    is_hit_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    is_hit_switch_node.input_type = 'VECTOR'

    raycast_node = node_tree.nodes.new(type='GeometryNodeRaycast')
    raycast_node.inputs['Ray Length'].default_value = meters_to_unreal(100)

    input_position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

    vector_math_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
    vector_math_node.operation = 'ADD'
    vector_math_node.inputs[1].default_value = (0, 0, meters_to_unreal(100))

    node_tree.links.new(input_position_node.outputs['Position'], vector_math_node.inputs[0])

    object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    object_info_node.transform_space = 'RELATIVE'

    node_tree.links.new(input_node.outputs['Terrain Info Object'], object_info_node.inputs['Object'])

    node_tree.links.new(object_info_node.outputs['Geometry'], raycast_node.inputs['Target Geometry'])
    node_tree.links.new(raycast_node.outputs['Is Hit'], is_hit_switch_node.inputs[0])
    node_tree.links.new(input_position_node.outputs['Position'], is_hit_switch_node.inputs[8])  # False
    node_tree.links.new(raycast_node.outputs['Hit Position'], is_hit_switch_node.inputs[9])  # True
    node_tree.links.new(vector_math_node.outputs['Vector'], raycast_node.inputs['Source Position'])

    node_tree.links.new(input_node.outputs['Geometry'], set_position_node.inputs['Geometry'])
    node_tree.links.new(is_hit_switch_node.outputs[3], set_position_node.inputs['Position'])

    node_tree.links.new(set_position_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return node_tree


def ensure_scatter_layer_node_tree(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> NodeTree:
    terrain_doodad_object = scatter_layer.terrain_doodad_object
    terrain_info_object = scatter_layer.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object

    def add_scatter_layer_object_driver(struct: bpy_struct, data_path: str, index: int = -1, path: str = 'default_value'):
        _add_scatter_layer_object_driver_ex(
            struct,
            terrain_doodad_object,
            data_path,
            index,
            path,
            scatter_layer_index=scatter_layer.index,
            scatter_layer_object_index=scatter_layer_object_index
        )

    def add_scatter_layer_driver(struct: bpy_struct, data_path: str, index: int = -1, path: str = 'default_value'):
        _add_scatter_layer_driver_ex(
            struct,
            terrain_doodad_object,
            data_path,
            index,
            path,
            scatter_layer_index=scatter_layer.index
        )

    inputs = {('NodeSocketGeometry', 'Geometry')}
    outputs = {('NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(scatter_layer.id, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    join_geometry_node = node_tree.nodes.new(type='GeometryNodeJoinGeometry')

    for scatter_layer_object_index, scatter_layer_object in enumerate(scatter_layer.objects):
        # Add an Object Info node.
        object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
        object_info_node.inputs[0].default_value = scatter_layer_object.object
        object_info_node.inputs['As Instance'].default_value = True

        separate_components_node = node_tree.nodes.new(type='GeometryNodeSeparateComponents')
        instance_on_points_node = node_tree.nodes.new(type='GeometryNodeInstanceOnPoints')
        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

        trim_curve_mode_node = node_tree.nodes.new(type='FunctionNodeInputInt')
        add_scatter_layer_object_driver(trim_curve_mode_node, 'curve_trim_mode', path='integer')

        trim_curve_sockets = add_trim_curve(
            node_tree,
            separate_components_node.outputs['Curve'],
            trim_curve_mode_node.outputs['Integer']
        )

        add_scatter_layer_object_driver(trim_curve_sockets.factor_start_socket, 'curve_trim_factor_start')
        add_scatter_layer_object_driver(trim_curve_sockets.factor_end_socket, 'curve_trim_factor_end')
        add_scatter_layer_object_driver(trim_curve_sockets.length_start_socket, 'curve_trim_length_start')
        add_scatter_layer_object_driver(trim_curve_sockets.length_end_socket, 'curve_trim_length_end')

        # Add "Curve to Points" node.
        curve_to_points_node = node_tree.nodes.new(type='GeometryNodeCurveToPoints')
        curve_to_points_node.mode = 'LENGTH'

        # Length axis.
        length_axis_node = node_tree.nodes.new(type='FunctionNodeInputInt')
        length_axis_node.integer = 0
        extents_socket = add_object_extents(node_tree, scatter_layer_object.object)
        length_socket = add_vector_xyz_switch(node_tree, extents_socket, length_axis_node.outputs['Integer'])
        node_tree.links.new(length_socket, curve_to_points_node.inputs['Length'])

        vector_scale_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_scale_node.operation = 'SCALE'

        node_tree.links.new(curve_to_points_node.outputs['Normal'], vector_scale_node.inputs[0])
        node_tree.links.new(vector_scale_node.outputs['Vector'], set_position_node.inputs['Offset'])

        normal_offset_random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        normal_offset_random_value_node.label = 'Normal Random Scale'
        normal_offset_random_value_node.data_type = 'FLOAT'

        add_scatter_layer_object_driver(normal_offset_random_value_node.inputs[2], 'curve_normal_offset_min')
        add_scatter_layer_object_driver(normal_offset_random_value_node.inputs[3], 'curve_normal_offset_max')
        add_scatter_layer_object_driver(normal_offset_random_value_node.inputs['Seed'], 'curve_normal_offset_seed')

        # Scale Mix
        scale_mix_node = node_tree.nodes.new(type='ShaderNodeMix')
        scale_mix_node.data_type = 'VECTOR'

        add_scatter_layer_object_driver(scale_mix_node.inputs[4], 'scale_min', 0)
        add_scatter_layer_object_driver(scale_mix_node.inputs[4], 'scale_min', 1)
        add_scatter_layer_object_driver(scale_mix_node.inputs[4], 'scale_min', 2)
        add_scatter_layer_object_driver(scale_mix_node.inputs[5], 'scale_max', 0)
        add_scatter_layer_object_driver(scale_mix_node.inputs[5], 'scale_max', 1)
        add_scatter_layer_object_driver(scale_mix_node.inputs[5], 'scale_max', 2)

        scale_random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        scale_random_value_node.label = 'Scale Random'
        scale_random_value_node.data_type = 'FLOAT'

        add_scatter_layer_object_driver(scale_random_value_node.inputs['Seed'], 'scale_seed')

        node_tree.links.new(scale_random_value_node.outputs[1], scale_mix_node.inputs['Factor'])

        index_node = node_tree.nodes.new(type='GeometryNodeInputIndex')
        node_tree.links.new(index_node.outputs['Index'], normal_offset_random_value_node.inputs['ID'])
        node_tree.links.new(index_node.outputs['Index'], scale_random_value_node.inputs['ID'])

        # Snap and Align to Terrain
        snap_and_align_to_terrain_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        snap_and_align_to_terrain_group_node.node_tree = ensure_terrain_snap_and_align_node_tree()
        snap_and_align_to_terrain_group_node.inputs['Terrain Info Object'].default_value = terrain_info_object

        snap_and_align_to_terrain_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        snap_and_align_to_terrain_switch_node.input_type = 'GEOMETRY'
        snap_and_align_to_terrain_switch_node.label = 'Snap and Align to Terrain'
        add_scatter_layer_driver(snap_and_align_to_terrain_switch_node.inputs[1], 'snap_to_terrain')

        node_tree.links.new(set_position_node.outputs['Geometry'], snap_and_align_to_terrain_group_node.inputs['Geometry'])
        node_tree.links.new(set_position_node.outputs['Geometry'], snap_and_align_to_terrain_switch_node.inputs[14])  # False
        node_tree.links.new(snap_and_align_to_terrain_group_node.outputs['Geometry'], snap_and_align_to_terrain_switch_node.inputs[15])  # True

        node_tree.links.new(input_node.outputs['Geometry'], separate_components_node.inputs['Geometry'])
        node_tree.links.new(trim_curve_sockets.curve_socket, curve_to_points_node.inputs['Curve'])
        node_tree.links.new(curve_to_points_node.outputs['Points'], set_position_node.inputs['Geometry'])
        node_tree.links.new(object_info_node.outputs['Geometry'], instance_on_points_node.inputs['Instance'])
        node_tree.links.new(scale_mix_node.outputs[1], instance_on_points_node.inputs['Scale'])
        node_tree.links.new(normal_offset_random_value_node.outputs[1], vector_scale_node.inputs['Scale'])

        # Mute
        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'GEOMETRY'
        add_scatter_layer_object_driver(switch_node.inputs[1], 'mute')

        node_tree.links.new(instance_on_points_node.outputs['Instances'], switch_node.inputs[14])    # False
        node_tree.links.new(switch_node.outputs[6], join_geometry_node.inputs['Geometry'])

        # Add store named attribute node.
        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.inputs['Name'].default_value = 'rotation'
        store_named_attribute_node.domain = 'POINT'
        store_named_attribute_node.data_type = 'FLOAT_VECTOR'

        node_tree.links.new(curve_to_points_node.outputs['Rotation'], store_named_attribute_node.inputs[3])  # Value

        # Add named attribute node.
        named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        named_attribute_node.inputs['Name'].default_value = 'rotation'
        named_attribute_node.data_type = 'FLOAT_VECTOR'

        node_tree.links.new(named_attribute_node.outputs[0], instance_on_points_node.inputs['Rotation'])  # Attribute -> Rotation

        node_tree.links.new(snap_and_align_to_terrain_switch_node.outputs[6], store_named_attribute_node.inputs['Geometry'])
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], instance_on_points_node.inputs['Points'])

    # Join the geometry from the join geometry node to the output node.
    node_tree.links.new(input_node.outputs['Geometry'], join_geometry_node.inputs['Geometry'])

    # Link the geometry from the join geometry node to the output node.
    node_tree.links.new(join_geometry_node.outputs['Geometry'], output_node.inputs['Geometry'])

    # Add named attribute node.

    return node_tree


def ensure_scatter_layer_modifiers(context: Context, terrain_doodad: 'BDK_PG_terrain_doodad'):
    terrain_doodad_object = terrain_doodad.object

    scatter_layer_ids = {scatter_layer.id for scatter_layer in terrain_doodad.scatter_layers}
    modifier_names = {modifier.name for modifier in terrain_doodad_object.modifiers}

    # Remove any modifiers that are not associated with a scatter layer.
    for modifier_name in modifier_names:
        if modifier_name not in scatter_layer_ids:
            terrain_doodad_object.modifiers.remove(terrain_doodad_object.modifiers[modifier_name])

    # Add modifiers for any scatter layers that do not have a modifier and ensure the node tree.
    for scatter_layer in terrain_doodad.scatter_layers:
        if scatter_layer.id not in terrain_doodad_object.modifiers:
            modifier = terrain_doodad_object.modifiers.new(name=scatter_layer.name, type='NODES')
        else:
            modifier = terrain_doodad_object.modifiers[scatter_layer.id]
        modifier.node_group = ensure_scatter_layer_node_tree(scatter_layer)
