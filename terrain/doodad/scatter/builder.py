import uuid
from typing import Iterable, List

import bpy
from bpy.types import Context, NodeTree, NodeSocket, Object, bpy_struct, ID, Node

from ....units import meters_to_unreal
from ....node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, \
    ensure_curve_normal_offset_node_tree, add_chained_math_nodes, ensure_trim_curve_node_tree, \
    ensure_curve_modifier_node_tree


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
        scatter_layer.seed_object.parent = scatter_layer.terrain_doodad_object
        bpy.context.scene.collection.objects.link(scatter_layer.seed_object)

    # Create the sprout object. This is the object that will create the instances from the seed object.
    if scatter_layer.sprout_object is None:
        name = uuid.uuid4().hex
        sprout_object = bpy.data.objects.new(name=name, object_data=bpy.data.meshes.new(name))
        sprout_object.hide_select = True
        sprout_object.lock_location = (True, True, True)
        sprout_object.lock_rotation = (True, True, True)
        sprout_object.lock_scale = (True, True, True)
        scatter_layer.sprout_object = sprout_object
        scatter_layer.sprout_object.parent = scatter_layer.terrain_doodad_object
        bpy.context.scene.collection.objects.link(scatter_layer.sprout_object)


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


def ensure_terrain_doodad_curve_align_to_terrain_node_tree() -> NodeTree:
    items = {
        ('BOTH', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT','NodeSocketFloat', 'Factor'),
        ('INPUT', 'NodeSocketVector', 'Random Rotation Max'),
        ('INPUT', 'NodeSocketInt', 'Random Rotation Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        store_rotation_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_rotation_attribute_node.label = 'Store Rotation Attribute'
        store_rotation_attribute_node.data_type = 'FLOAT_VECTOR'
        store_rotation_attribute_node.inputs["Selection"].default_value = True
        store_rotation_attribute_node.inputs["Name"].default_value = 'rotation'

        up_vector_node = node_tree.nodes.new(type='FunctionNodeInputVector')
        up_vector_node.label = 'Up Vector'
        up_vector_node.vector = (0, 0, 1)

        terrain_normal_mix_node = node_tree.nodes.new(type='ShaderNodeMix')
        terrain_normal_mix_node.label = 'Terrain Normal Mix'
        terrain_normal_mix_node.data_type = 'VECTOR'
        terrain_normal_mix_node.clamp_factor = True

        terrain_normal_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        terrain_normal_attribute_node.label = 'Terrain Normal Attribute'
        terrain_normal_attribute_node.data_type = 'FLOAT_VECTOR'
        terrain_normal_attribute_node.inputs["Name"].default_value = 'terrain_normal'

        curve_tangent_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        curve_tangent_attribute_node.label = 'Curve Tangent Attribute'
        curve_tangent_attribute_node.data_type = 'FLOAT_VECTOR'
        curve_tangent_attribute_node.inputs["Name"].default_value = 'curve_tangent'

        align_x_node = node_tree.nodes.new(type='FunctionNodeAlignEulerToVector')
        align_x_node.label = 'Align X'

        vector_math_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node.operation = 'NORMALIZE'

        align_z_node = node_tree.nodes.new(type='FunctionNodeAlignEulerToVector')
        align_z_node.label = 'Align Z'
        align_z_node.axis = 'Z'
        align_z_node.inputs["Factor"].default_value = 1.0

        seed_socket = add_chained_math_nodes(node_tree, 'ADD', [input_node.outputs['Random Rotation Seed'],
                                                                input_node.outputs['Global Seed']])

        negate_random_rotation_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        negate_random_rotation_node.label = 'Negate Random Rotation'
        negate_random_rotation_node.operation = 'MULTIPLY'
        negate_random_rotation_node.inputs[1].default_value = (-1, -1, -1)

        random_rotation_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        random_rotation_node.label = 'Random Rotation'
        random_rotation_node.data_type = 'FLOAT_VECTOR'

        rotate_euler_node = node_tree.nodes.new(type='FunctionNodeRotateEuler')
        rotate_euler_node.space = 'LOCAL'

        # Input
        node_tree.links.new(input_node.outputs['Factor'], terrain_normal_mix_node.inputs[0])
        node_tree.links.new(input_node.outputs['Geometry'], store_rotation_attribute_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Random Rotation Max'], negate_random_rotation_node.inputs[0])
        node_tree.links.new(input_node.outputs['Random Rotation Max'], random_rotation_node.inputs[1])

        # Internal
        node_tree.links.new(terrain_normal_mix_node.outputs[1], vector_math_node.inputs[0])  # Result -> Vector
        node_tree.links.new(terrain_normal_attribute_node.outputs[0], terrain_normal_mix_node.inputs[5])  # Attribute -> B
        node_tree.links.new(curve_tangent_attribute_node.outputs[0], align_x_node.inputs[2])  # Attribute -> Vector
        node_tree.links.new(align_z_node.outputs[0], rotate_euler_node.inputs[0])  # Rotation -> Rotation
        node_tree.links.new(rotate_euler_node.outputs['Rotation'], store_rotation_attribute_node.inputs[3])  # Rotation -> Value
        node_tree.links.new(align_x_node.outputs[0], align_z_node.inputs[0])  # Rotation -> Rotation
        node_tree.links.new(vector_math_node.outputs[0], align_z_node.inputs[2])  # Vector -> Vector
        node_tree.links.new(up_vector_node.outputs[0], terrain_normal_mix_node.inputs[4])  # Vector -> A
        node_tree.links.new(random_rotation_node.outputs[0], rotate_euler_node.inputs[1])  # Value -> Rotate By
        node_tree.links.new(negate_random_rotation_node.outputs[0], random_rotation_node.inputs[0])  # Vector -> Min
        node_tree.links.new(seed_socket, random_rotation_node.inputs[8])
        node_tree.links.new(align_z_node.outputs['Rotation'], rotate_euler_node.inputs[0])

        # Output
        node_tree.links.new(store_rotation_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Terrain Doodad Curve Align To Terrain', items, build_function)


def ensure_snap_to_terrain_node_tree() -> NodeTree:
    items = {
        ('BOTH',  'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketGeometry', 'Terrain Geometry'),
        ('INPUT', 'NodeSocketBool', 'Mute'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

        terrain_sample_node = node_tree.nodes.new(type='GeometryNodeBDKTerrainSample')

        store_terrain_normal_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_terrain_normal_attribute_node.inputs['Name'].default_value = 'terrain_normal'
        store_terrain_normal_attribute_node.data_type = 'FLOAT_VECTOR'
        store_terrain_normal_attribute_node.domain = 'POINT'

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'
        mute_switch_node.label = 'Mute'

        # Input
        node_tree.links.new(input_node.outputs['Mute'], mute_switch_node.inputs[1])
        node_tree.links.new(input_node.outputs['Terrain Geometry'], terrain_sample_node.inputs['Terrain'])
        node_tree.links.new(input_node.outputs['Geometry'], set_position_node.inputs['Geometry'])

        # Internal
        node_tree.links.new(terrain_sample_node.outputs['Position'], set_position_node.inputs['Position'])
        node_tree.links.new(mute_switch_node.outputs[6], store_terrain_normal_attribute_node.inputs['Geometry'])  # Output -> Geometry
        node_tree.links.new(terrain_sample_node.outputs['Normal'], store_terrain_normal_attribute_node.inputs[3])  # Value
        node_tree.links.new(input_node.outputs['Geometry'], mute_switch_node.inputs[14])  # Geometry -> False
        node_tree.links.new(set_position_node.outputs['Geometry'], mute_switch_node.inputs[15])  # True

        # Output
        node_tree.links.new(store_terrain_normal_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])  # Geometry -> Geometry

    return ensure_geometry_node_tree('BDK Snap to Terrain', items, build_function)


def ensure_scatter_layer_sprout_node_tree(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> NodeTree:
    items = {('OUTPUT','NodeSocketGeometry', 'Geometry')}

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        seed_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
        seed_object_info_node.transform_space = 'RELATIVE'
        seed_object_info_node.inputs['Object'].default_value = scatter_layer.seed_object

        join_geometry_node = node_tree.nodes.new(type='GeometryNodeJoinGeometry')

        # Gather all the object instance geometry sockets.
        object_geometry_output_sockets = []
        for obj in scatter_layer.objects:
            object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
            object_info_node.inputs['Object'].default_value = obj.object
            object_info_node.inputs['As Instance'].default_value = True
            object_geometry_output_sockets.append(object_info_node.outputs['Geometry'])

        instance_on_points_node = node_tree.nodes.new(type='GeometryNodeInstanceOnPoints')
        instance_on_points_node.inputs['Pick Instance'].default_value = True

        rotation_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        rotation_attribute_node.inputs['Name'].default_value = 'rotation'
        rotation_attribute_node.data_type = 'FLOAT_VECTOR'

        scale_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        scale_attribute_node.inputs['Name'].default_value = 'scale'
        scale_attribute_node.data_type = 'FLOAT_VECTOR'

        object_index_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        object_index_attribute_node.data_type = 'INT'
        object_index_attribute_node.inputs['Name'].default_value = 'object_index'

        # Internal
        node_tree.links.new(object_index_attribute_node.outputs[4], instance_on_points_node.inputs[4])
        node_tree.links.new(rotation_attribute_node.outputs[0], instance_on_points_node.inputs['Rotation'])
        node_tree.links.new(scale_attribute_node.outputs[0], instance_on_points_node.inputs['Scale'])
        node_tree.links.new(join_geometry_node.outputs['Geometry'], instance_on_points_node.inputs['Instance'])
        node_tree.links.new(seed_object_info_node.outputs['Geometry'], instance_on_points_node.inputs['Points'])

        # Link the object geometry output sockets to the join geometry node.
        # This needs to be done in reverse order.
        for object_geometry_output_socket in reversed(object_geometry_output_sockets):
            node_tree.links.new(object_geometry_output_socket, join_geometry_node.inputs['Geometry'])

        # Output
        node_tree.links.new(instance_on_points_node.outputs['Instances'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(scatter_layer.sprout_object.name, items, build_function, should_force_build=True)


def ensure_geometry_size_node_tree() -> NodeTree:
    items = {('INPUT','NodeSocketGeometry', 'Geometry'), ('OUTPUT','NodeSocketVector', 'Size')}

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        bounding_box_node = node_tree.nodes.new(type='GeometryNodeBoundBox')

        subtract_vector_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        subtract_vector_node.operation = 'SUBTRACT'

        # Input
        node_tree.links.new(input_node.outputs['Geometry'], bounding_box_node.inputs['Geometry'])

        # Internal
        node_tree.links.new(bounding_box_node.outputs['Max'], subtract_vector_node.inputs[0])
        node_tree.links.new(bounding_box_node.outputs['Min'], subtract_vector_node.inputs[1])

        # Output
        node_tree.links.new(subtract_vector_node.outputs['Vector'], output_node.inputs['Size'])

    return ensure_geometry_node_tree('BDK Bounding Box Size', items, build_function)


def ensure_vector_component_node_tree() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketVector', 'Vector'),
        ('INPUT','NodeSocketInt', 'Index'),
        ('OUTPUT', 'NodeSocketFloat', 'Value')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        compare_index_x_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_index_x_node.data_type = 'INT'
        compare_index_x_node.operation = 'EQUAL'

        switch_x_yz_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_x_yz_node.input_type = 'FLOAT'
        switch_x_yz_node.label = 'Switch X/YZ'

        compare_index_y_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_index_y_node.data_type = 'INT'
        compare_index_y_node.operation = 'EQUAL'
        compare_index_y_node.inputs[3].default_value = 1

        switch_yz_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_yz_node.input_type = 'FLOAT'
        switch_yz_node.label = 'Switch Y/Z'

        # Input
        node_tree.links.new(input_node.outputs['Index'], compare_index_y_node.inputs[2])  # A
        node_tree.links.new(input_node.outputs['Vector'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(input_node.outputs['Index'], compare_index_x_node.inputs[2])  # A

        # Internal
        node_tree.links.new(compare_index_x_node.outputs['Result'], switch_x_yz_node.inputs[0])  # Result -> Switch
        node_tree.links.new(separate_xyz_node.outputs['X'], switch_x_yz_node.inputs[3])  # True
        node_tree.links.new(switch_yz_node.outputs[0], switch_x_yz_node.inputs[2])  # False
        node_tree.links.new(separate_xyz_node.outputs['Z'], switch_yz_node.inputs[2])  # False
        node_tree.links.new(compare_index_y_node.outputs['Result'], switch_yz_node.inputs[0])  # Result -> Switch
        node_tree.links.new(separate_xyz_node.outputs['Y'], switch_yz_node.inputs[3])  # True
        node_tree.links.new(separate_xyz_node.outputs['Z'], switch_yz_node.inputs[4])  # False
        node_tree.links.new(switch_yz_node.outputs[0], switch_x_yz_node.inputs[4])  # False

        # Output
        node_tree.links.new(switch_x_yz_node.outputs[0], output_node.inputs['Value'])

    return ensure_geometry_node_tree('BDK Vector Component', items, build_function)


def ensure_delete_random_points_node_tree() -> NodeTree:
    inputs = {
        ('BOTH', 'NodeSocketGeometry', 'Points'),
        ('INPUT', 'NodeSocketFloat', 'Factor'),
        ('INPUT', 'NodeSocketInt', 'Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        inert_random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        inert_random_value_node.label = 'Inert Random Value'
        inert_random_value_node.data_type = 'BOOLEAN'

        delete_geometry_node = node_tree.nodes.new(type='GeometryNodeDeleteGeometry')

        inert_seed_socket = add_chained_math_nodes(node_tree, 'ADD', [input_node.outputs['Seed'],
                                                                      input_node.outputs['Global Seed']])

        # Input
        node_tree.links.new(input_node.outputs['Factor'], inert_random_value_node.inputs[6]) # Probability
        node_tree.links.new(input_node.outputs['Points'], delete_geometry_node.inputs['Geometry'])

        # Internal
        node_tree.links.new(inert_seed_socket, inert_random_value_node.inputs['Seed'])
        node_tree.links.new(inert_random_value_node.outputs[3], delete_geometry_node.inputs[1])  # Value -> Selection

        # Output
        node_tree.links.new(delete_geometry_node.outputs['Geometry'], output_node.inputs['Points'])

    return ensure_geometry_node_tree('BDK Delete Random Points', inputs, build_function)


def ensure_scatter_layer_curve_to_points_node_tree() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketFloat', 'Spacing Length'),
        ('INPUT', 'NodeSocketFloat', 'Normal Offset Max'),
        ('INPUT', 'NodeSocketInt', 'Normal Offset Seed'),
        ('INPUT', 'NodeSocketFloat', 'Tangent Offset Max'),
        ('INPUT', 'NodeSocketInt', 'Tangent Offset Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
        ('OUTPUT', 'NodeSocketGeometry', 'Points')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        curve_to_points_node = node_tree.nodes.new(type='GeometryNodeCurveToPoints')
        curve_to_points_node.mode = 'LENGTH'

        # Nodes
        store_curve_tangent_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_curve_tangent_attribute_node.data_type = 'FLOAT_VECTOR'
        store_curve_tangent_attribute_node.domain = 'POINT'
        store_curve_tangent_attribute_node.inputs['Name'].default_value = 'curve_tangent'

        store_curve_normal_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_curve_normal_attribute_node.data_type = 'FLOAT_VECTOR'
        store_curve_normal_attribute_node.domain = 'POINT'
        store_curve_normal_attribute_node.inputs['Name'].default_value = 'curve_normal'

        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

        normal_scale_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        normal_scale_node.operation = 'SCALE'

        tangent_scale_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        tangent_scale_node.operation = 'SCALE'

        normal_offset_random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        tangent_offset_random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')

        normal_offset_seed_socket = add_chained_math_nodes(node_tree, 'ADD', [input_node.outputs['Normal Offset Seed'], input_node.outputs['Global Seed']])
        tangent_offset_seed_socket = add_chained_math_nodes(node_tree, 'ADD', [input_node.outputs['Tangent Offset Seed'], input_node.outputs['Global Seed']])

        node_tree.links.new(tangent_offset_seed_socket, tangent_offset_random_value_node.inputs['Seed'])

        add_offsets_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        add_offsets_node.operation = 'ADD'

        normal_offset_negate_node = node_tree.nodes.new(type='ShaderNodeMath')
        normal_offset_negate_node.operation = 'MULTIPLY'
        normal_offset_negate_node.inputs[1].default_value = -1.0

        tangent_offset_negate_node = node_tree.nodes.new(type='ShaderNodeMath')
        tangent_offset_negate_node.operation = 'MULTIPLY'
        tangent_offset_negate_node.inputs[1].default_value = -1.0

        # Input
        node_tree.links.new(input_node.outputs['Normal Offset Max'], normal_offset_negate_node.inputs[0])
        node_tree.links.new(input_node.outputs['Curve'], curve_to_points_node.inputs['Curve'])
        node_tree.links.new(input_node.outputs['Spacing Length'], curve_to_points_node.inputs['Length'])
        node_tree.links.new(input_node.outputs['Normal Offset Max'], normal_offset_random_value_node.inputs[3]) # Max
        node_tree.links.new(input_node.outputs['Tangent Offset Max'], tangent_offset_negate_node.inputs[0])
        node_tree.links.new(input_node.outputs['Tangent Offset Max'], tangent_offset_random_value_node.inputs[3]) # Max

        # Internal
        node_tree.links.new(normal_scale_node.outputs['Vector'], add_offsets_node.inputs[0])  # Result -> Vector
        node_tree.links.new(tangent_scale_node.outputs['Vector'], add_offsets_node.inputs[1])  # Result -> Vector
        node_tree.links.new(add_offsets_node.outputs['Vector'], set_position_node.inputs['Offset'])  # Vector -> Offset
        node_tree.links.new(normal_offset_random_value_node.outputs[1], normal_scale_node.inputs[3])  # Result -> Scale
        node_tree.links.new(curve_to_points_node.outputs['Points'], set_position_node.inputs['Geometry'])
        node_tree.links.new(set_position_node.outputs['Geometry'], store_curve_tangent_attribute_node.inputs['Geometry'])
        node_tree.links.new(curve_to_points_node.outputs['Normal'], store_curve_normal_attribute_node.inputs[3])  # Normal -> Value
        node_tree.links.new(curve_to_points_node.outputs['Tangent'], store_curve_tangent_attribute_node.inputs[3])  # Tangent -> Value
        node_tree.links.new(store_curve_tangent_attribute_node.outputs['Geometry'], store_curve_normal_attribute_node.inputs['Geometry'])
        node_tree.links.new(normal_offset_seed_socket, normal_offset_random_value_node.inputs['Seed'])
        node_tree.links.new(curve_to_points_node.outputs['Normal'], normal_scale_node.inputs[0]) # Normal -> Vector
        node_tree.links.new(normal_offset_negate_node.outputs[0], normal_offset_random_value_node.inputs[2]) # Min
        node_tree.links.new(normal_offset_random_value_node.outputs[1], normal_scale_node.inputs['Scale'])
        node_tree.links.new(curve_to_points_node.outputs['Tangent'], tangent_scale_node.inputs[0]) # Tangent -> Vector
        node_tree.links.new(tangent_offset_negate_node.outputs[0], tangent_offset_random_value_node.inputs[2]) # Min
        node_tree.links.new(tangent_offset_random_value_node.outputs[1], tangent_scale_node.inputs['Scale'])
        node_tree.links.new(curve_to_points_node.outputs['Points'], set_position_node.inputs['Geometry'])

        # Output
        node_tree.links.new(store_curve_normal_attribute_node.outputs['Geometry'], output_node.inputs['Points'])

    return ensure_geometry_node_tree('BDK Scatter Layer Curve To Points', items, build_function)


def ensure_select_object_index_node_tree() -> NodeTree:
    items = {
        ('BOTH', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Object Count'),
        ('INPUT', 'NodeSocketInt', 'Object Select Mode'),
        ('INPUT', 'NodeSocketInt', 'Object Index Offset'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
        ('INPUT', 'NodeSocketInt', 'Object Select Seed')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'INT'
        store_named_attribute_node.domain = 'POINT'
        store_named_attribute_node.inputs['Name'].default_value = 'object_index'

        seed_socket = add_chained_math_nodes(node_tree, 'ADD', [input_node.outputs['Object Select Seed'],
                                                                input_node.outputs['Global Seed']])

        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = 'FLOORED_MODULO'

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'INT'

        index_node = node_tree.nodes.new(type='GeometryNodeInputIndex')
        random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        random_value_node.data_type = 'INT'

        object_index_offset_node = node_tree.nodes.new(type='ShaderNodeMath')
        object_index_offset_node.label = 'Object Index Offset'

        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'

        subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
        subtract_node.operation = 'SUBTRACT'
        subtract_node.inputs[1].default_value = 1

        # Input
        node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Object Count'], subtract_node.inputs[0])
        node_tree.links.new(input_node.outputs['Object Index Offset'], object_index_offset_node.inputs[1])
        node_tree.links.new(input_node.outputs['Object Count'], math_node.inputs[1])
        node_tree.links.new(input_node.outputs['Object Select Mode'], compare_node.inputs[2])

        # Internal
        node_tree.links.new(seed_socket, random_value_node.inputs['Seed'])
        node_tree.links.new(subtract_node.outputs['Value'], random_value_node.inputs[5])
        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])
        node_tree.links.new(random_value_node.outputs[2], switch_node.inputs[4])
        node_tree.links.new(switch_node.outputs['Output'], store_named_attribute_node.inputs[7])
        node_tree.links.new(math_node.outputs['Value'], switch_node.inputs[5])
        node_tree.links.new(index_node.outputs['Index'], object_index_offset_node.inputs[0])
        node_tree.links.new(object_index_offset_node.outputs['Value'], math_node.inputs[0])
        node_tree.links.new(switch_node.outputs[1], store_named_attribute_node.inputs[7])

        # Output
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Select Object Index', items, build_function)


def ensure_terrain_normal_offset_node_tree() -> NodeTree:
    items = {
        ('BOTH', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketFloat', 'Terrain Normal Offset Min'),
        ('INPUT', 'NodeSocketFloat', 'Terrain Normal Offset Max'),
        ('INPUT', 'NodeSocketInt', 'Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        seed_socket = add_chained_math_nodes(node_tree, 'ADD', [input_node.outputs['Seed'], input_node.outputs['Global Seed']])

        vector_math_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node.operation = 'SCALE'

        random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')

        named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        named_attribute_node.data_type = 'FLOAT_VECTOR'
        named_attribute_node.inputs["Name"].default_value = 'terrain_normal'

        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

        # Input
        node_tree.links.new(input_node.outputs['Terrain Normal Offset Min'], random_value_node.inputs[2])  # Min
        node_tree.links.new(input_node.outputs['Terrain Normal Offset Max'], random_value_node.inputs[3])  # Max
        node_tree.links.new(input_node.outputs['Geometry'], set_position_node.inputs['Geometry'])

        # Internal Links
        node_tree.links.new(random_value_node.outputs[1], vector_math_node.inputs[3])  # Value -> Scale
        node_tree.links.new(vector_math_node.outputs[0], set_position_node.inputs[3])  # Vector -> Offset
        node_tree.links.new(named_attribute_node.outputs[0], vector_math_node.inputs[0])  # Attribute -> Vector
        node_tree.links.new(seed_socket, random_value_node.inputs['Seed'])

        # Outputs
        node_tree.links.new(set_position_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Terrain Normal Offset', items, build_function)


def ensure_scatter_layer_object_node_tree() -> NodeTree:
    items = {
        ('BOTH', 'NodeSocketGeometry', 'Points'),
        ('INPUT', 'NodeSocketGeometry', 'Terrain Geometry'),
        ('INPUT', 'NodeSocketInt', 'Object Index'),
        ('INPUT', 'NodeSocketVector', 'Scale Min'),
        ('INPUT', 'NodeSocketVector', 'Scale Max'),
        ('INPUT', 'NodeSocketInt', 'Scale Seed'),
        ('INPUT', 'NodeSocketBool', 'Snap to Terrain'),
        ('INPUT', 'NodeSocketBool', 'Mute'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
        ('INPUT', 'NodeSocketFloat', 'Align to Terrain Factor'),
        ('INPUT', 'NodeSocketFloat', 'Terrain Normal Offset Min'),
        ('INPUT', 'NodeSocketFloat', 'Terrain Normal Offset Max'),
        ('INPUT', 'NodeSocketInt', 'Terrain Normal Offset Seed'),
        ('INPUT', 'NodeSocketVector', 'Random Rotation Max'),
        ('INPUT', 'NodeSocketInt', 'Random Rotation Seed'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'

        object_index_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        object_index_attribute_node.data_type = 'INT'
        object_index_attribute_node.inputs['Name'].default_value = 'object_index'

        separate_geometry_node = node_tree.nodes.new(type='GeometryNodeSeparateGeometry')

        scale_mix_node = node_tree.nodes.new(type='ShaderNodeMix')
        scale_mix_node.data_type = 'VECTOR'

        scale_random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        scale_random_value_node.label = 'Scale Random'
        scale_random_value_node.data_type = 'FLOAT'

        snap_to_terrain_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        snap_to_terrain_group_node.node_tree = ensure_snap_to_terrain_node_tree()

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'
        mute_switch_node.label = 'Mute'

        align_to_terrain_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        align_to_terrain_node_group_node.node_tree = ensure_terrain_doodad_curve_align_to_terrain_node_tree()

        terrain_normal_offset_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        terrain_normal_offset_node_group_node.node_tree = ensure_terrain_normal_offset_node_tree()

        store_scale_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_scale_attribute_node.inputs['Name'].default_value = 'scale'
        store_scale_attribute_node.domain = 'POINT'
        store_scale_attribute_node.data_type = 'FLOAT_VECTOR'
        store_scale_attribute_node.label = 'Store Scale Attribute'

        scale_seed_socket = add_chained_math_nodes(node_tree, 'ADD',
                                                   [input_node.outputs['Scale Seed'], input_node.outputs['Global Seed']])

        # Input
        node_tree.links.new(input_node.outputs['Scale Min'], scale_mix_node.inputs[4])
        node_tree.links.new(input_node.outputs['Scale Max'], scale_mix_node.inputs[5])
        node_tree.links.new(input_node.outputs['Mute'], mute_switch_node.inputs[1])
        node_tree.links.new(input_node.outputs['Align to Terrain Factor'], align_to_terrain_node_group_node.inputs['Factor'])
        node_tree.links.new(input_node.outputs['Terrain Geometry'], snap_to_terrain_group_node.inputs['Terrain Geometry'])
        node_tree.links.new(input_node.outputs['Snap to Terrain'], snap_to_terrain_group_node.inputs['Mute'])
        node_tree.links.new(input_node.outputs['Object Index'], compare_node.inputs[3])
        node_tree.links.new(input_node.outputs['Points'], separate_geometry_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Terrain Normal Offset Min'], terrain_normal_offset_node_group_node.inputs['Terrain Normal Offset Min'])
        node_tree.links.new(input_node.outputs['Terrain Normal Offset Max'], terrain_normal_offset_node_group_node.inputs['Terrain Normal Offset Max'])
        node_tree.links.new(input_node.outputs['Terrain Normal Offset Seed'], terrain_normal_offset_node_group_node.inputs['Seed'])
        node_tree.links.new(input_node.outputs['Global Seed'], terrain_normal_offset_node_group_node.inputs['Global Seed'])
        node_tree.links.new(input_node.outputs['Random Rotation Max'], align_to_terrain_node_group_node.inputs['Random Rotation Max'])
        node_tree.links.new(input_node.outputs['Random Rotation Seed'], align_to_terrain_node_group_node.inputs['Random Rotation Seed'])
        node_tree.links.new(input_node.outputs['Global Seed'], align_to_terrain_node_group_node.inputs['Global Seed'])


        # Internal
        node_tree.links.new(scale_seed_socket, scale_random_value_node.inputs['Seed'])
        node_tree.links.new(object_index_attribute_node.outputs[4], compare_node.inputs[2])
        node_tree.links.new(compare_node.outputs['Result'], separate_geometry_node.inputs['Selection'])
        node_tree.links.new(scale_mix_node.outputs[1], store_scale_attribute_node.inputs[3])  # Result -> Value
        node_tree.links.new(snap_to_terrain_group_node.outputs['Geometry'], align_to_terrain_node_group_node.inputs['Geometry'])
        node_tree.links.new(align_to_terrain_node_group_node.outputs['Geometry'], terrain_normal_offset_node_group_node.inputs['Geometry'])
        node_tree.links.new(terrain_normal_offset_node_group_node.outputs['Geometry'], store_scale_attribute_node.inputs['Geometry'])
        node_tree.links.new(store_scale_attribute_node.outputs['Geometry'], mute_switch_node.inputs[14])  # False
        node_tree.links.new(scale_random_value_node.outputs[1], scale_mix_node.inputs['Factor'])
        node_tree.links.new(separate_geometry_node.outputs['Selection'], snap_to_terrain_group_node.inputs['Geometry'])

        # Output
        node_tree.links.new(mute_switch_node.outputs[6], output_node.inputs['Points'])

    return ensure_geometry_node_tree('BDK Scatter Layer Object', items, build_function)


def ensure_scatter_layer_seed_node_tree(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> NodeTree:
    terrain_doodad_object = scatter_layer.terrain_doodad_object
    terrain_info_object = scatter_layer.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object

    items = {('OUTPUT', 'NodeSocketGeometry', 'Geometry')}

    def build_function(node_tree: NodeTree):
        def add_scatter_layer_object_driver(struct: bpy_struct, data_path: str, index: int = -1,
                                            path: str = 'default_value'):
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

        # TODO: Why is this not being called??
        def add_scatter_object_seed_node(scatter_object_path: str) -> NodeSocket:
            seed_add_node = node_tree.nodes.new(type='ShaderNodeMath')
            seed_add_node.operation = 'ADD'
            add_scatter_layer_object_driver(seed_add_node.inputs[0], scatter_object_path)
            add_scatter_layer_driver(seed_add_node.inputs[1], 'global_seed')
            return seed_add_node.outputs['Value']

        input_node, output_node = ensure_input_and_output_nodes(node_tree)

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
            spacing_length_socket = add_chained_math_nodes(node_tree, 'MAXIMUM', length_sockets)

            spacing_mode_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
            spacing_mode_switch_node.input_type = 'FLOAT'
            add_scatter_layer_driver(spacing_mode_switch_node.inputs['Switch'], 'curve_spacing_method')
            add_scatter_layer_driver(spacing_mode_switch_node.inputs[3], 'curve_spacing_absolute')  # False

            spacing_relative_factor_node = node_tree.nodes.new(type='ShaderNodeMath')
            spacing_relative_factor_node.operation = 'MULTIPLY'

            if spacing_length_socket:
                node_tree.links.new(spacing_length_socket, spacing_relative_factor_node.inputs[0])

            add_scatter_layer_driver(spacing_relative_factor_node.inputs[1], 'curve_spacing_relative_factor')

            node_tree.links.new(spacing_relative_factor_node.outputs['Value'], spacing_mode_switch_node.inputs[2])

            spacing_length_socket = spacing_mode_switch_node.outputs[0]

            curve_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
            curve_object_info_node.inputs['Object'].default_value = terrain_doodad_object

            curve_modifier_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
            curve_modifier_group_node.node_tree = ensure_curve_modifier_node_tree()

            add_scatter_layer_driver(curve_modifier_group_node.inputs['Is Curve Reversed'], 'is_curve_reversed')
            add_scatter_layer_driver(curve_modifier_group_node.inputs['Trim Mode'], 'curve_trim_mode')
            add_scatter_layer_driver(curve_modifier_group_node.inputs['Trim Factor Start'], 'curve_trim_factor_start')
            add_scatter_layer_driver(curve_modifier_group_node.inputs['Trim Factor End'], 'curve_trim_factor_end')
            add_scatter_layer_driver(curve_modifier_group_node.inputs['Trim Length Start'], 'curve_trim_length_start')
            add_scatter_layer_driver(curve_modifier_group_node.inputs['Trim Length End'], 'curve_trim_length_end')
            add_scatter_layer_driver(curve_modifier_group_node.inputs['Normal Offset'], 'curve_normal_offset')

            curve_to_points_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
            curve_to_points_group_node.node_tree = ensure_scatter_layer_curve_to_points_node_tree()

            add_scatter_layer_driver(curve_to_points_group_node.inputs['Normal Offset Max'], 'curve_normal_offset_max')
            add_scatter_layer_driver(curve_to_points_group_node.inputs['Normal Offset Seed'], 'curve_normal_offset_seed')
            add_scatter_layer_driver(curve_to_points_group_node.inputs['Tangent Offset Max'], 'curve_tangent_offset_max')
            add_scatter_layer_driver(curve_to_points_group_node.inputs['Tangent Offset Seed'], 'curve_tangent_offset_seed')
            add_scatter_layer_driver(curve_to_points_group_node.inputs['Global Seed'], 'global_seed')

            node_tree.links.new(curve_object_info_node.outputs['Geometry'], curve_modifier_group_node.inputs['Curve'])
            node_tree.links.new(curve_modifier_group_node.outputs['Curve'], curve_to_points_group_node.inputs['Curve'])

            if spacing_length_socket is not None:
                node_tree.links.new(spacing_length_socket, curve_to_points_group_node.inputs['Spacing Length'])

            points_socket = curve_to_points_group_node.outputs['Points']
        else:
            raise RuntimeError('Unsupported terrain doodad object type: ' + scatter_layer.terrain_doodad_object.type)

        # Select Object Index
        select_object_index_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        select_object_index_node_group_node.node_tree = ensure_select_object_index_node_tree()
        select_object_index_node_group_node.inputs['Object Count'].default_value = len(scatter_layer.objects)
        add_scatter_layer_driver(select_object_index_node_group_node.inputs['Object Select Mode'], 'object_select_mode')
        add_scatter_layer_driver(select_object_index_node_group_node.inputs['Object Index Offset'],
                                 'object_select_cyclic_offset')
        add_scatter_layer_driver(select_object_index_node_group_node.inputs['Object Select Seed'],
                                 'object_select_random_seed')
        add_scatter_layer_driver(select_object_index_node_group_node.inputs['Global Seed'], 'global_seed')

        node_tree.links.new(points_socket, select_object_index_node_group_node.inputs['Geometry'])

        points_socket = select_object_index_node_group_node.outputs['Geometry']

        terrain_info_object_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
        terrain_info_object_node.transform_space = 'RELATIVE'
        terrain_info_object_node.inputs['Object'].default_value = terrain_info_object

        join_geometry_node = node_tree.nodes.new(type='GeometryNodeJoinGeometry')

        for scatter_layer_object_index, scatter_layer_object in enumerate(scatter_layer.objects):
            scatter_layer_object_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
            scatter_layer_object_node_group_node.node_tree = ensure_scatter_layer_object_node_tree()

            scatter_layer_object_node_group_node.inputs['Object Index'].default_value = scatter_layer_object_index

            # Add drivers etc.
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Scale Min'], 'scale_min', 0)
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Scale Min'], 'scale_min', 1)
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Scale Min'], 'scale_min', 2)
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Scale Max'], 'scale_max', 0)
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Scale Max'], 'scale_max', 1)
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Scale Max'], 'scale_max', 2)
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Scale Seed'], 'scale_seed')
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Snap to Terrain'],
                                            'snap_to_terrain')
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Mute'], 'mute')
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Global Seed'], 'global_seed')
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Align to Terrain Factor'],
                                            'align_to_terrain_factor')
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Terrain Normal Offset Min'],
                                            'terrain_normal_offset_min')
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Terrain Normal Offset Max'],
                                            'terrain_normal_offset_max')
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Terrain Normal Offset Seed'],
                                            'terrain_normal_offset_seed')
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Random Rotation Max'], 'random_rotation_max', 0)
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Random Rotation Max'], 'random_rotation_max', 1)
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Random Rotation Max'], 'random_rotation_max', 2)
            add_scatter_layer_object_driver(scatter_layer_object_node_group_node.inputs['Random Rotation Seed'], 'random_rotation_max_seed')

            node_tree.links.new(points_socket, scatter_layer_object_node_group_node.inputs['Points'])
            node_tree.links.new(terrain_info_object_node.outputs['Geometry'],
                                scatter_layer_object_node_group_node.inputs['Terrain Geometry'])
            node_tree.links.new(scatter_layer_object_node_group_node.outputs['Points'],
                                join_geometry_node.inputs['Geometry'])

        # Pass through inertion.
        delete_random_points_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        delete_random_points_node_group_node.node_tree = ensure_delete_random_points_node_tree()
        node_tree.links.new(join_geometry_node.outputs['Geometry'], delete_random_points_node_group_node.inputs['Points'])
        add_scatter_layer_driver(delete_random_points_node_group_node.inputs['Factor'], 'inert_factor')
        add_scatter_layer_driver(delete_random_points_node_group_node.inputs['Seed'], 'inert_seed')
        add_scatter_layer_driver(delete_random_points_node_group_node.inputs['Global Seed'], 'global_seed')

        # We need to convert the point cloud to a mesh so that we can inspect the attributes for T3D export.
        points_to_vertices_node = node_tree.nodes.new(type='GeometryNodePointsToVertices')
        node_tree.links.new(delete_random_points_node_group_node.outputs['Points'], points_to_vertices_node.inputs['Points'])

        # Add a mute switch.
        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'
        mute_switch_node.label = 'Mute'

        node_tree.links.new(points_to_vertices_node.outputs['Mesh'], mute_switch_node.inputs[14])  # False
        add_scatter_layer_driver(mute_switch_node.inputs[1], 'mute')

        node_tree.links.new(mute_switch_node.outputs[6], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(scatter_layer.seed_object.name, items, build_function, should_force_build=True)


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
