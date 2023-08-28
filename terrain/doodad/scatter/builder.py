import uuid
from typing import Iterable, List

import bpy
from bpy.types import Context, NodeTree, NodeSocket, Object, bpy_struct, ID, Node

from ....units import meters_to_unreal
from ....node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, \
    ensure_curve_normal_offset_node_tree, add_chained_math_nodes, ensure_trim_curve_node_tree


def add_scatter_layer(terrain_doodad: 'BDK_PG_terrain_doodad') -> 'BDK_PG_terrain_doodad_scatter_layer':
    scatter_layer = terrain_doodad.scatter_layers.add()
    scatter_layer.id = uuid.uuid4().hex
    scatter_layer.terrain_doodad_object = terrain_doodad.object

    return scatter_layer


def ensure_scatter_layer(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer'):
    """
    Ensures that the given scatter layer has a geometry node tree and input and output nodes.
    :param scatter_layer:
    :return:
    """
    # Create the seed object. This is the object that will have vertices with instance attributes scattered on it.
    # This will be used by the sprout object, but also by the T3D exporter.
    if scatter_layer.seed_object is None:
        name = uuid.uuid4().hex
        seed_object = bpy.data.objects.new(name=name, object_data=bpy.data.meshes.new(name))
        seed_object.hide_select = True
        seed_object.lock_location = (True, True, True)
        seed_object.lock_rotation = (True, True, True)
        seed_object.lock_scale = (True, True, True)
        scatter_layer.seed_object = seed_object

    # Create the sprout object. This is the object that will create the instances from the seed object.
    if scatter_layer.sprout_object is None:
        name = uuid.uuid4().hex
        sprout_object = bpy.data.objects.new(name=name, object_data=bpy.data.meshes.new(name))
        sprout_object.hide_select = True
        sprout_object.lock_location = (True, True, True)
        sprout_object.lock_rotation = (True, True, True)
        sprout_object.lock_scale = (True, True, True)
        scatter_layer.sprout_object = sprout_object

    # Add the seed object and the sprout object into the scene and parent them to the terrain doodad.
    bpy.context.scene.collection.objects.link(scatter_layer.seed_object)
    bpy.context.scene.collection.objects.link(scatter_layer.sprout_object)

    scatter_layer.seed_object.parent = scatter_layer.terrain_doodad_object
    scatter_layer.sprout_object.parent = scatter_layer.terrain_doodad_object


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


def add_object_extents(node_tree: NodeTree, bpy_object: Object) -> NodeSocket:
    """
    Adds a set of nodes to the node tree that will output the extents of the object.
    :param node_tree:
    :param bpy_object:
    :return: The output socket representing the extents of the object.
    """
    object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    object_info_node.inputs[0].default_value = bpy_object

    geometry_size_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
    geometry_size_group_node.node_tree = ensure_geometry_size_node_tree()

    node_tree.links.new(object_info_node.outputs['Geometry'], geometry_size_group_node.inputs['Geometry'])

    return geometry_size_group_node.outputs['Size']


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
    node_tree = ensure_geometry_node_tree('BDK Snap and Align to Terrain', inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')
    terrain_sample_node = node_tree.nodes.new(type='GeometryNodeBDKTerrainSample')

    object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    object_info_node.transform_space = 'RELATIVE'

    node_tree.links.new(input_node.outputs['Terrain Info Object'], object_info_node.inputs['Object'])
    node_tree.links.new(object_info_node.outputs['Geometry'], terrain_sample_node.inputs['Terrain'])
    node_tree.links.new(input_node.outputs['Geometry'], set_position_node.inputs['Geometry'])
    node_tree.links.new(terrain_sample_node.outputs['Position'], set_position_node.inputs['Position'])

    store_terrain_normal_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
    store_terrain_normal_attribute_node.inputs['Name'].default_value = 'terrain_normal'
    store_terrain_normal_attribute_node.data_type = 'FLOAT_VECTOR'
    store_terrain_normal_attribute_node.domain = 'POINT'

    node_tree.links.new(set_position_node.outputs['Geometry'], store_terrain_normal_attribute_node.inputs['Geometry'])
    node_tree.links.new(terrain_sample_node.outputs['Normal'], store_terrain_normal_attribute_node.inputs[3])  # Value

    node_tree.links.new(store_terrain_normal_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return node_tree


def ensure_scatter_layer_sprout_node_tree(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> NodeTree:
    inputs = set()
    outputs = {('NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(scatter_layer.sprout_object.name, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    seed_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    seed_object_info_node.transform_space = 'RELATIVE'
    seed_object_info_node.inputs['Object'].default_value = scatter_layer.seed_object

    join_geometry_node = node_tree.nodes.new(type='GeometryNodeJoinGeometry')
    # For each scatter layer, add an object info node and pipe them all into a join geometry node.
    # Then pipe that into the instance on points node.
    for obj in scatter_layer.objects:
        object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
        object_info_node.inputs['Object'].default_value = obj.object
        object_info_node.inputs['As Instance'].default_value = True
        node_tree.links.new(object_info_node.outputs['Geometry'], join_geometry_node.inputs['Geometry'])

    instance_on_points_node = node_tree.nodes.new(type='GeometryNodeInstanceOnPoints')

    rotation_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
    rotation_attribute_node.inputs['Name'].default_value = 'rotation'
    rotation_attribute_node.data_type = 'FLOAT_VECTOR'

    scale_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
    scale_attribute_node.inputs['Name'].default_value = 'scale'
    scale_attribute_node.data_type = 'FLOAT_VECTOR'

    node_tree.links.new(rotation_attribute_node.outputs[0], instance_on_points_node.inputs['Rotation'])
    node_tree.links.new(scale_attribute_node.outputs[0], instance_on_points_node.inputs['Scale'])

    node_tree.links.new(join_geometry_node.outputs['Geometry'], instance_on_points_node.inputs['Instance'])
    node_tree.links.new(seed_object_info_node.outputs['Geometry'], instance_on_points_node.inputs['Points'])
    node_tree.links.new(instance_on_points_node.outputs['Instances'], output_node.inputs['Geometry'])

    return node_tree


def ensure_geometry_size_node_tree() -> NodeTree:
    inputs = {('NodeSocketGeometry', 'Geometry')}
    outputs = {('NodeSocketVector', 'Size')}
    node_tree = ensure_geometry_node_tree('BDK Bounding Box Size', inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    # Add Bounding Box node
    bounding_box_node = node_tree.nodes.new(type='GeometryNodeBoundBox')

    # Subtract Vector node
    subtract_vector_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
    subtract_vector_node.operation = 'SUBTRACT'

    node_tree.links.new(input_node.outputs['Geometry'], bounding_box_node.inputs['Geometry'])
    node_tree.links.new(bounding_box_node.outputs['Max'], subtract_vector_node.inputs[0])
    node_tree.links.new(bounding_box_node.outputs['Min'], subtract_vector_node.inputs[1])
    node_tree.links.new(subtract_vector_node.outputs['Vector'], output_node.inputs['Size'])

    return node_tree


def ensure_vector_component_node_tree() -> NodeTree:
    inputs = {('NodeSocketVector', 'Vector'), ('NodeSocketInt', 'Index')}
    outputs = {('NodeSocketFloat', 'Value')}
    node_tree = ensure_geometry_node_tree('BDK Vector Component', inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    # Separate XYZ node
    separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
    node_tree.links.new(input_node.outputs['Vector'], separate_xyz_node.inputs['Vector'])

    compare_index_x_node = node_tree.nodes.new(type='FunctionNodeCompare')
    compare_index_x_node.data_type = 'INT'
    compare_index_x_node.operation = 'EQUAL'

    node_tree.links.new(input_node.outputs['Index'], compare_index_x_node.inputs[2])  # A

    switch_x_yz_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_x_yz_node.input_type = 'FLOAT'
    switch_x_yz_node.label = 'Switch X/YZ'

    node_tree.links.new(compare_index_x_node.outputs['Result'], switch_x_yz_node.inputs[0])  # Result -> Switch
    node_tree.links.new(separate_xyz_node.outputs['X'], switch_x_yz_node.inputs[3])  # True

    compare_index_y_node = node_tree.nodes.new(type='FunctionNodeCompare')
    compare_index_y_node.data_type = 'INT'
    compare_index_y_node.operation = 'EQUAL'
    compare_index_y_node.inputs[3].default_value = 1

    switch_yz_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_yz_node.input_type = 'FLOAT'
    switch_yz_node.label = 'Switch Y/Z'

    node_tree.links.new(switch_yz_node.outputs[0], switch_x_yz_node.inputs[2])  # False
    node_tree.links.new(separate_xyz_node.outputs['Z'], switch_yz_node.inputs[2])  # False
    node_tree.links.new(input_node.outputs['Index'], compare_index_y_node.inputs[2])  # A
    node_tree.links.new(compare_index_y_node.outputs['Result'], switch_yz_node.inputs[0])  # Result -> Switch
    node_tree.links.new(separate_xyz_node.outputs['Y'], switch_yz_node.inputs[3])  # True
    node_tree.links.new(separate_xyz_node.outputs['Z'], switch_yz_node.inputs[4])  # False
    node_tree.links.new(switch_yz_node.outputs[0], switch_x_yz_node.inputs[4])  # False
    node_tree.links.new(switch_x_yz_node.outputs[0], output_node.inputs['Value'])

    return node_tree


def ensure_scatter_layer_curve_to_points_node_tree() -> NodeTree:
    inputs = {('NodeSocketGeometry', 'Curve'),
              ('NodeSocketInt', 'Trim Mode'),
              ('NodeSocketFloat', 'Trim Factor Start'),
              ('NodeSocketFloat', 'Trim Factor End'),
              ('NodeSocketFloat', 'Trim Length Start'),
              ('NodeSocketFloat', 'Trim Length End'),
              ('NodeSocketFloat', 'Normal Offset'),
              ('NodeSocketFloat', 'Spacing Length'),
              ('NodeSocketBool', 'Is Curve Reversed'),
              }
    outputs = {('NodeSocketGeometry', 'Points'),
               ('NodeSocketVector', 'Normal'),
               ('NodeSocketVector', 'Tangent'),
               }
    node_tree = ensure_geometry_node_tree('BDK Scatter Layer Curve To Points', inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

    reverse_curve_node = node_tree.nodes.new(type='GeometryNodeReverseCurve')

    reverse_curve_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    reverse_curve_switch_node.input_type = 'GEOMETRY'
    reverse_curve_switch_node.label = 'Reverse Curve?'

    node_tree.links.new(input_node.outputs['Is Curve Reversed'], reverse_curve_switch_node.inputs[1])
    node_tree.links.new(input_node.outputs['Curve'], reverse_curve_switch_node.inputs[14])  # False
    node_tree.links.new(input_node.outputs['Curve'], reverse_curve_node.inputs['Curve'])
    node_tree.links.new(reverse_curve_node.outputs['Curve'], reverse_curve_switch_node.inputs[15])  # True

    # Add "Curve Trim" node.
    trim_curve_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
    trim_curve_group_node.node_tree = ensure_trim_curve_node_tree()
    node_tree.links.new(reverse_curve_switch_node.outputs[6], trim_curve_group_node.outputs['Curve'])
    node_tree.links.new(input_node.outputs['Trim Mode'], trim_curve_group_node.inputs['Mode'])
    node_tree.links.new(input_node.outputs['Trim Factor Start'], trim_curve_group_node.inputs['Factor Start'])
    node_tree.links.new(input_node.outputs['Trim Factor End'], trim_curve_group_node.inputs['Factor End'])
    node_tree.links.new(input_node.outputs['Trim Length Start'], trim_curve_group_node.inputs['Length Start'])
    node_tree.links.new(input_node.outputs['Trim Length End'], trim_curve_group_node.inputs['Length End'])

    # Add BDK Normal Offset node.
    curve_normal_offset_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
    curve_normal_offset_group_node.node_tree = ensure_curve_normal_offset_node_tree()
    node_tree.links.new(input_node.outputs['Normal Offset'], curve_normal_offset_group_node.inputs['Normal Offset'])

    node_tree.links.new(reverse_curve_switch_node.outputs[6], trim_curve_group_node.inputs['Curve'])
    node_tree.links.new(trim_curve_group_node.outputs['Curve'], curve_normal_offset_group_node.inputs['Curve'])

    # Add "Curve to Points" node.
    curve_to_points_node = node_tree.nodes.new(type='GeometryNodeCurveToPoints')
    curve_to_points_node.mode = 'LENGTH'

    node_tree.links.new(input_node.outputs['Spacing Length'], curve_to_points_node.inputs['Length'])
    node_tree.links.new(curve_normal_offset_group_node.outputs['Curve'], curve_to_points_node.inputs['Curve'])

    node_tree.links.new(curve_to_points_node.outputs['Normal'], output_node.inputs['Normal'])
    node_tree.links.new(curve_to_points_node.outputs['Points'], set_position_node.inputs['Geometry'])

    normal_offset_random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
    normal_offset_random_value_node.label = 'Normal Random Scale'
    normal_offset_random_value_node.data_type = 'FLOAT'

    node_tree.links.new(set_position_node.outputs['Geometry'], output_node.inputs['Points'])

    # node_tree.links.new(add_scatter_object_seed_node('curve_normal_offset_seed'), normal_offset_random_value_node.inputs['Seed'])
    # add_scatter_layer_object_driver(normal_offset_random_value_node.inputs[2], 'curve_normal_offset_min')
    # add_scatter_layer_object_driver(normal_offset_random_value_node.inputs[3], 'curve_normal_offset_max')
    # node_tree.links.new(normal_offset_random_value_node.outputs[1], vector_scale_node.inputs['Scale'])

    return node_tree


def ensure_scatter_layer_seed_node_tree(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> NodeTree:
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

    def add_scatter_object_seed_node(scatter_object_path: str) -> NodeSocket:
        seed_add_node = node_tree.nodes.new(type='ShaderNodeMath')
        seed_add_node.operation = 'ADD'
        add_scatter_layer_object_driver(seed_add_node.inputs[0], scatter_object_path)
        add_scatter_layer_driver(seed_add_node.inputs[1], 'global_seed')
        return seed_add_node.outputs['Value']

    inputs = set()
    outputs = {('NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(scatter_layer.seed_object.name, inputs, outputs)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    join_geometry_node = node_tree.nodes.new(type='GeometryNodeJoinGeometry')

    if scatter_layer.terrain_doodad_object.type == 'CURVE':
        # Get the maximum length of all the objects in the scatter layer.
        length_sockets = []
        for scatter_layer_object in scatter_layer.objects:
            size_socket = add_object_extents(node_tree, scatter_layer_object.object)
            vector_component_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
            vector_component_group_node.node_tree = ensure_vector_component_node_tree()
            node_tree.links.new(size_socket, vector_component_group_node.inputs['Vector'])
            add_scatter_layer_driver(vector_component_group_node.inputs['Index'], 'curve_spacing_relative_axis')
            length_sockets.append(vector_component_group_node.outputs['Value'])
        spacing_length = add_chained_math_nodes(node_tree, 'MAXIMUM', length_sockets)

        spacing_mode_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        spacing_mode_switch_node.input_type = 'FLOAT'
        add_scatter_layer_driver(spacing_mode_switch_node.inputs['Switch'], 'curve_spacing_method')
        add_scatter_layer_driver(spacing_mode_switch_node.inputs[3], 'curve_spacing_absolute')  # False

        spacing_relative_factor_node = node_tree.nodes.new(type='ShaderNodeMath')
        spacing_relative_factor_node.operation = 'MULTIPLY'
        node_tree.links.new(spacing_length, spacing_relative_factor_node.inputs[0])
        add_scatter_layer_driver(spacing_relative_factor_node.inputs[1], 'curve_spacing_relative_factor')

        node_tree.links.new(spacing_relative_factor_node.outputs['Value'], spacing_mode_switch_node.inputs[2])

        spacing_length = spacing_mode_switch_node.outputs[0]

        curve_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
        curve_object_info_node.inputs['Object'].default_value = terrain_doodad_object

        curve_to_points_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        curve_to_points_group_node.node_tree = ensure_scatter_layer_curve_to_points_node_tree()
        node_tree.links.new(curve_object_info_node.outputs['Geometry'], curve_to_points_group_node.inputs['Curve'])
        add_scatter_layer_driver(curve_to_points_group_node.inputs['Is Curve Reversed'], 'is_curve_reversed')
        add_scatter_layer_driver(curve_to_points_group_node.inputs['Trim Mode'], 'curve_trim_mode')
        add_scatter_layer_driver(curve_to_points_group_node.inputs['Trim Factor Start'], 'curve_trim_factor_start')
        add_scatter_layer_driver(curve_to_points_group_node.inputs['Trim Factor End'], 'curve_trim_factor_end')
        add_scatter_layer_driver(curve_to_points_group_node.inputs['Trim Length Start'], 'curve_trim_length_start')
        add_scatter_layer_driver(curve_to_points_group_node.inputs['Trim Length End'], 'curve_trim_length_end')
        add_scatter_layer_driver(curve_to_points_group_node.inputs['Normal Offset'], 'curve_normal_offset')

        # TODO: Add a Reverse Curve node here.


        if spacing_length is not None:
            node_tree.links.new(spacing_length, curve_to_points_group_node.inputs['Spacing Length'])

        points_socket = curve_to_points_group_node.outputs['Points']
    else:
        raise RuntimeError('Unsupported terrain doodad object type: ' + scatter_layer.terrain_doodad_object.type)

    # TODO: we need to refactor this so that the objects are just here to be selected at random (aside from perhaps the scale)
    for scatter_layer_object_index, scatter_layer_object in enumerate(scatter_layer.objects):
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

        node_tree.links.new(add_scatter_object_seed_node('scale_seed'), scale_random_value_node.inputs['Seed'])
        node_tree.links.new(scale_random_value_node.outputs[1], scale_mix_node.inputs['Factor'])

        # Snap and Align to Terrain
        snap_and_align_to_terrain_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        snap_and_align_to_terrain_group_node.node_tree = ensure_terrain_snap_and_align_node_tree()
        snap_and_align_to_terrain_group_node.inputs['Terrain Info Object'].default_value = terrain_info_object

        snap_and_align_to_terrain_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        snap_and_align_to_terrain_switch_node.input_type = 'GEOMETRY'
        snap_and_align_to_terrain_switch_node.label = 'Snap and Align to Terrain?'
        add_scatter_layer_driver(snap_and_align_to_terrain_switch_node.inputs[1], 'snap_to_terrain')

        node_tree.links.new(points_socket, snap_and_align_to_terrain_group_node.inputs['Geometry'])
        node_tree.links.new(points_socket, snap_and_align_to_terrain_switch_node.inputs[14])  # False
        node_tree.links.new(snap_and_align_to_terrain_group_node.outputs['Geometry'], snap_and_align_to_terrain_switch_node.inputs[15])  # True

        # Mute Switch
        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'
        mute_switch_node.label = 'Mute'
        add_scatter_layer_object_driver(mute_switch_node.inputs[1], 'mute')

        # Store Rotation Attribute
        store_rotation_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_rotation_attribute_node.inputs['Name'].default_value = 'rotation'
        store_rotation_attribute_node.domain = 'POINT'
        store_rotation_attribute_node.data_type = 'FLOAT_VECTOR'
        store_rotation_attribute_node.label = 'Store Rotation Attribute'

        # Store Scale Attribute
        store_scale_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_scale_attribute_node.inputs['Name'].default_value = 'scale'
        store_scale_attribute_node.domain = 'POINT'
        store_scale_attribute_node.data_type = 'FLOAT_VECTOR'
        store_scale_attribute_node.label = 'Store Scale Attribute'

        node_tree.links.new(scale_mix_node.outputs[1], store_scale_attribute_node.inputs[3])  # Result -> Value
        # node_tree.links.new(curve_to_points_node.outputs['Rotation'], store_rotation_attribute_node.inputs[3])  # Value
        node_tree.links.new(snap_and_align_to_terrain_switch_node.outputs[6], store_rotation_attribute_node.inputs['Geometry'])
        node_tree.links.new(store_rotation_attribute_node.outputs['Geometry'], store_scale_attribute_node.inputs['Geometry'])
        node_tree.links.new(store_scale_attribute_node.outputs['Geometry'], mute_switch_node.inputs[14])  # False

        # Link the geometry from the join geometry node to the output node.
        node_tree.links.new(mute_switch_node.outputs[6], join_geometry_node.inputs['Geometry'])

    # We need to convert the point cloud to a mesh so that we can inspect the attributes for T3D export.
    points_to_vertices_node = node_tree.nodes.new(type='GeometryNodePointsToVertices')
    node_tree.links.new(join_geometry_node.outputs['Geometry'], points_to_vertices_node.inputs['Points'])
    node_tree.links.new(points_to_vertices_node.outputs['Mesh'], output_node.inputs['Geometry'])

    return node_tree


def ensure_scatter_layer_modifiers(context: Context, terrain_doodad: 'BDK_PG_terrain_doodad'):
    # Add modifiers for any scatter layers that do not have a modifier and ensure the node tree.
    for scatter_layer in terrain_doodad.scatter_layers:
        # Seed
        seed_object = scatter_layer.seed_object
        if scatter_layer.id not in seed_object.modifiers.keys():
            modifier = seed_object.modifiers.new(name=scatter_layer.id, type='NODES')
        else:
            modifier = seed_object.modifiers[scatter_layer.id]
        modifier.node_group = ensure_scatter_layer_seed_node_tree(scatter_layer)
        # Sprout
        sprout_object = scatter_layer.sprout_object
        if scatter_layer.id not in sprout_object.modifiers.keys():
            modifier = sprout_object.modifiers.new(name=scatter_layer.id, type='NODES')
        else:
            modifier = sprout_object.modifiers[scatter_layer.id]
        modifier.node_group = ensure_scatter_layer_sprout_node_tree(scatter_layer)
