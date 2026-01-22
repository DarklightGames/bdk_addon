import uuid

import bpy
from bpy.types import Context, NodeTree, NodeSocket, Object, bpy_struct, ID, GeometryNodeBake
from typing import cast as typing_cast

from ....terrain.curve_to_equidistant_points import ensure_curve_to_equidistant_points_node_tree
from ...terrain_sample import ensure_bdk_terrain_sample_node_tree
from ....helpers import ensure_name_unique
from ....node_helpers import add_group_node, add_position_input_node, ensure_geometry_node_tree, ensure_input_and_output_nodes, add_chained_math_nodes, \
    ensure_curve_modifier_node_tree, ensure_weighted_index_node_tree, add_geometry_node_switch_nodes, \
    add_repeat_zone_nodes, add_math_operation_nodes, add_comparison_nodes, add_curve_spline_loop_nodes, \
    CurveSplineLoopSockets, add_vector_math_operation_nodes, add_boolean_math_operation_nodes


def add_terrain_doodad_scatter_layer(terrain_doodad: 'BDK_PG_terrain_doodad', name: str = 'Scatter Layer') -> \
        'BDK_PG_terrain_doodad_scatter_layer':
    scatter_layer = terrain_doodad.scatter_layers.add()
    scatter_layer.id = uuid.uuid4().hex
    scatter_layer.terrain_doodad_object = terrain_doodad.object
    scatter_layer.name = ensure_name_unique(name, [x.name for x in terrain_doodad.scatter_layers])
    scatter_layer.mask_attribute_id = uuid.uuid4().hex

    return scatter_layer


def ensure_scatter_layer_seed_and_sprout_collection(context: Context) -> bpy.types.Collection:
    """
    Ensures that the scatter layer seed and sprout collection exists and returns it.
    :param context:
    :return:
    """
    collection_name = 'BDK Scatter Layer Seed and Sprout'
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        collection.hide_select = True
        context.scene.collection.children.link(collection)
    return collection


def ensure_scatter_layer(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer'):
    """
    Ensures that the given scatter layer has a geometry node tree and input and output nodes.
    :param scatter_layer:
    :return:
    """

    seed_and_sprout_collection = ensure_scatter_layer_seed_and_sprout_collection(bpy.context)

    def create_scatter_layer_seed_object() -> Object:
        name = uuid.uuid4().hex
        obj = bpy.data.objects.new(name=name, object_data=bpy.data.meshes.new(name))
        obj.hide_select = True
        obj.lock_location = (True, True, True)
        obj.lock_rotation = (True, True, True)
        obj.lock_scale = (True, True, True)
        return obj

    # The places the "seeds" in the preliminary spots, before they are placed
    if scatter_layer.planter_object is None:
        scatter_layer.planter_object = create_scatter_layer_seed_object()
        scatter_layer.planter_object.hide_viewport = True
        scatter_layer.planter_object.hide_render = True
        seed_and_sprout_collection.objects.link(scatter_layer.planter_object)

    # Create the seed object. This is the object that will have vertices with instance attributes scattered on it.
    # This will be used by the sprout object, but also by the T3D exporter.
    if scatter_layer.seed_object is None:
        scatter_layer.seed_object = create_scatter_layer_seed_object()
        scatter_layer.seed_object.hide_viewport = True
        scatter_layer.seed_object.hide_render = True
        seed_and_sprout_collection.objects.link(scatter_layer.seed_object)

    # Create the sprout object. This is the object that will create the instances from the seed object.
    if scatter_layer.sprout_object is None:
        scatter_layer.sprout_object = create_scatter_layer_seed_object()
        seed_and_sprout_collection.objects.link(scatter_layer.sprout_object)


def add_scatter_layer_object(
        scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> 'BDK_PG_terrain_doodad_scatter_layer_object':
    scatter_layer_object = scatter_layer.objects.add()
    scatter_layer_object.id = uuid.uuid4().hex
    scatter_layer_object.terrain_doodad_object = scatter_layer.terrain_doodad_object
    scatter_layer_object.scatter_layer = scatter_layer
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


def get_data_path_for_scatter_layer_object(scatter_layer_index: int, scatter_layer_object_index: int,
                                           data_path: str) -> str:
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
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketBool', 'Fence Mode'),
        ('INPUT', 'NodeSocketFloat', 'Factor'),
        ('INPUT', 'NodeSocketVector', 'Random Rotation Max'),
        ('INPUT', 'NodeSocketInt', 'Random Rotation Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
        ('INPUT', 'NodeSocketVector', 'Rotation Offset'),
        ('INPUT', 'NodeSocketFloat', 'Rotation Offset Saturation'),
        ('INPUT', 'NodeSocketInt', 'Rotation Offset Saturation Seed'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

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

        normalize_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        normalize_node.operation = 'NORMALIZE'

        align_z_node = node_tree.nodes.new(type='FunctionNodeAlignEulerToVector')
        align_z_node.label = 'Align Z'
        align_z_node.axis = 'Z'
        align_z_node.inputs["Factor"].default_value = 1.0

        random_rotation_seed_socket = add_math_operation_nodes(node_tree, 'ADD', [
            input_node.outputs['Random Rotation Seed'],
            input_node.outputs['Global Seed']])

        rotation_offset_saturation_seed_socket = add_math_operation_nodes(node_tree, 'ADD', [
            input_node.outputs['Rotation Offset Saturation Seed'],
            input_node.outputs['Global Seed']])

        rotation_offset_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        rotation_offset_switch_node.input_type = 'ROTATION'

        random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')

        saturation_compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        saturation_compare_node.data_type = 'FLOAT'
        saturation_compare_node.operation = 'LESS_THAN'

        negate_random_rotation_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        negate_random_rotation_node.label = 'Negate Random Rotation'
        negate_random_rotation_node.operation = 'MULTIPLY'
        negate_random_rotation_node.inputs[1].default_value = (-1, -1, -1)

        random_rotation_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        random_rotation_node.label = 'Random Rotation'
        random_rotation_node.data_type = 'FLOAT_VECTOR'

        random_rotation_rotate_rotation_node = node_tree.nodes.new(type='FunctionNodeRotateRotation')
        random_rotation_rotate_rotation_node.rotation_space = 'LOCAL'
        random_rotation_rotate_rotation_node.label = 'Random Rotation'

        rotation_offset_rotate_rotation_node = node_tree.nodes.new(type='FunctionNodeRotateRotation')
        rotation_offset_rotate_rotation_node.rotation_space = 'LOCAL'
        rotation_offset_rotate_rotation_node.label = 'Rotation Offset'

        curve_normal_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        curve_normal_attribute_node.label = 'Curve Normal Attribute'
        curve_normal_attribute_node.data_type = 'FLOAT_VECTOR'
        curve_normal_attribute_node.inputs["Name"].default_value = 'curve_normal'

        cross_product_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        cross_product_node.operation = 'CROSS_PRODUCT'

        node_tree.links.new(curve_normal_attribute_node.outputs['Attribute'], cross_product_node.inputs[0])
        node_tree.links.new(curve_tangent_attribute_node.outputs['Attribute'], cross_product_node.inputs[1])

        fence_mode_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        fence_mode_switch_node.input_type = 'VECTOR'
        fence_mode_switch_node.label = 'Normal Switch'

        node_tree.links.new(terrain_normal_mix_node.outputs['Result'], fence_mode_switch_node.inputs['False'])
        node_tree.links.new(cross_product_node.outputs['Vector'], fence_mode_switch_node.inputs['True'])

        # Input
        node_tree.links.new(input_node.outputs['Factor'], terrain_normal_mix_node.inputs[0])
        node_tree.links.new(input_node.outputs['Geometry'], store_rotation_attribute_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Random Rotation Max'], negate_random_rotation_node.inputs[0])
        node_tree.links.new(input_node.outputs['Random Rotation Max'], random_rotation_node.inputs[1])
        node_tree.links.new(input_node.outputs['Rotation Offset'],
                            rotation_offset_rotate_rotation_node.inputs['Rotate By'])
        node_tree.links.new(input_node.outputs['Fence Mode'], fence_mode_switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Rotation Offset Saturation'], saturation_compare_node.inputs['B'])

        # Internal
        node_tree.links.new(fence_mode_switch_node.outputs['Output'], normalize_node.inputs['Vector'])
        node_tree.links.new(terrain_normal_attribute_node.outputs['Attribute'], terrain_normal_mix_node.inputs['B'])
        node_tree.links.new(curve_tangent_attribute_node.outputs['Attribute'], align_x_node.inputs['Vector'])
        node_tree.links.new(align_z_node.outputs['Rotation'], rotation_offset_rotate_rotation_node.inputs['Rotation'])
        node_tree.links.new(rotation_offset_switch_node.outputs['Output'],
                            random_rotation_rotate_rotation_node.inputs['Rotation'])
        node_tree.links.new(random_rotation_node.outputs['Value'],
                            random_rotation_rotate_rotation_node.inputs['Rotate By'])
        node_tree.links.new(random_rotation_rotate_rotation_node.outputs['Rotation'],
                            store_rotation_attribute_node.inputs['Value'])
        node_tree.links.new(align_x_node.outputs['Rotation'], align_z_node.inputs['Rotation'])
        node_tree.links.new(normalize_node.outputs['Vector'], align_z_node.inputs['Vector'])
        node_tree.links.new(up_vector_node.outputs['Vector'], terrain_normal_mix_node.inputs['A'])
        node_tree.links.new(negate_random_rotation_node.outputs['Vector'], random_rotation_node.inputs['Min'])
        node_tree.links.new(random_rotation_seed_socket, random_rotation_node.inputs['Seed'])
        node_tree.links.new(rotation_offset_saturation_seed_socket, random_value_node.inputs['Seed'])
        node_tree.links.new(random_value_node.outputs['Value'], saturation_compare_node.inputs['A'])
        node_tree.links.new(saturation_compare_node.outputs['Result'], rotation_offset_switch_node.inputs['Switch'])
        node_tree.links.new(align_z_node.outputs['Rotation'], rotation_offset_switch_node.inputs['False'])
        node_tree.links.new(rotation_offset_rotate_rotation_node.outputs['Rotation'],
                            rotation_offset_switch_node.inputs['True'])

        # Output
        node_tree.links.new(store_rotation_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Terrain Doodad Curve Align To Terrain', items, build_function)


def ensure_snap_to_terrain_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketGeometry', 'Terrain Geometry'),
        ('INPUT', 'NodeSocketMatrix', 'Terrain Transform'),
        ('INPUT', 'NodeSocketInt', 'Terrain Resolution'),
        ('INPUT', 'NodeSocketBool', 'Mute'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')
        terrain_sample_node = add_group_node(node_tree, ensure_bdk_terrain_sample_node_tree)

        store_terrain_normal_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_terrain_normal_attribute_node.inputs['Name'].default_value = 'terrain_normal'
        store_terrain_normal_attribute_node.data_type = 'FLOAT_VECTOR'
        store_terrain_normal_attribute_node.domain = 'POINT'

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'
        mute_switch_node.label = 'Mute'

        # Input
        node_tree.links.new(input_node.outputs['Mute'], mute_switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Terrain Geometry'], terrain_sample_node.inputs['Terrain Geometry'])
        node_tree.links.new(input_node.outputs['Geometry'], set_position_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Terrain Transform'], terrain_sample_node.inputs['Terrain Transform'])
        node_tree.links.new(input_node.outputs['Terrain Resolution'], terrain_sample_node.inputs['Terrain Resolution'])

        # Internal
        node_tree.links.new(add_position_input_node(node_tree), terrain_sample_node.inputs['Position'])
        node_tree.links.new(terrain_sample_node.outputs['Position'], set_position_node.inputs['Position'])
        node_tree.links.new(mute_switch_node.outputs['Output'], store_terrain_normal_attribute_node.inputs['Geometry'])
        node_tree.links.new(terrain_sample_node.outputs['Normal'], store_terrain_normal_attribute_node.inputs['Value'])
        node_tree.links.new(input_node.outputs['Geometry'], mute_switch_node.inputs['False'])
        node_tree.links.new(set_position_node.outputs['Geometry'], mute_switch_node.inputs['True'])

        # Output
        node_tree.links.new(store_terrain_normal_attribute_node.outputs['Geometry'],
                            output_node.inputs['Geometry'])  # Geometry -> Geometry

    return ensure_geometry_node_tree('BDK Snap to Terrain', items, build_function)


def ensure_scatter_layer_sprout_node_tree(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> NodeTree:
    items = (
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

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
        node_tree.links.new(object_index_attribute_node.outputs['Attribute'],
                            instance_on_points_node.inputs['Instance Index'])
        node_tree.links.new(rotation_attribute_node.outputs['Attribute'], instance_on_points_node.inputs['Rotation'])
        node_tree.links.new(scale_attribute_node.outputs['Attribute'], instance_on_points_node.inputs['Scale'])
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
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketVector', 'Size'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        bounding_box_node = node_tree.nodes.new(type='GeometryNodeBoundBox')
        realize_instances_node = node_tree.nodes.new(type='GeometryNodeRealizeInstances')

        # Input
        node_tree.links.new(input_node.outputs['Geometry'], realize_instances_node.inputs['Geometry'])

        # Internal
        node_tree.links.new(realize_instances_node.outputs['Geometry'], bounding_box_node.inputs['Geometry'])

        extends_socket = add_vector_math_operation_nodes(node_tree, 'SUBTRACT', [
            bounding_box_node.outputs['Max'],
            bounding_box_node.outputs['Min']
        ])

        # Output
        node_tree.links.new(extends_socket, output_node.inputs['Size'])

    return ensure_geometry_node_tree('BDK Bounding Box Size', items, build_function)


def ensure_vector_component_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'Vector'),
        ('INPUT', 'NodeSocketInt', 'Index'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    )

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
        node_tree.links.new(input_node.outputs['Index'], compare_index_y_node.inputs['A'])
        node_tree.links.new(input_node.outputs['Vector'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(input_node.outputs['Index'], compare_index_x_node.inputs['A'])

        # Internal
        node_tree.links.new(compare_index_x_node.outputs['Result'], switch_x_yz_node.inputs['Switch'])
        node_tree.links.new(switch_yz_node.outputs['Output'], switch_x_yz_node.inputs['False'])
        node_tree.links.new(separate_xyz_node.outputs['X'], switch_x_yz_node.inputs['True'])
        node_tree.links.new(separate_xyz_node.outputs['Z'], switch_yz_node.inputs['False'])
        node_tree.links.new(compare_index_y_node.outputs['Result'], switch_yz_node.inputs['Switch'])
        node_tree.links.new(separate_xyz_node.outputs['Z'], switch_yz_node.inputs['False'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], switch_yz_node.inputs['True'])

        # Output
        node_tree.links.new(switch_x_yz_node.outputs['Output'], output_node.inputs['Value'])

    return ensure_geometry_node_tree('BDK Vector Component', items, build_function)


def ensure_select_random_node_tree() -> NodeTree:
    inputs = (
        ('OUTPUT', 'NodeSocketBool', 'Selection'),
        ('INPUT', 'NodeSocketFloat', 'Factor'),
        ('INPUT', 'NodeSocketInt', 'Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        random_value_node.data_type = 'BOOLEAN'

        seed_socket = add_math_operation_nodes(node_tree, 'ADD',
                                               [input_node.outputs['Seed'], input_node.outputs['Global Seed']])

        # Input
        node_tree.links.new(input_node.outputs['Factor'], random_value_node.inputs[6])  # Probability

        # Internal
        node_tree.links.new(seed_socket, random_value_node.inputs['Seed'])

        # Output
        node_tree.links.new(random_value_node.outputs[3], output_node.inputs['Selection'])

    return ensure_geometry_node_tree('BDK Select Random Points', inputs, build_function)


def ensure_get_tangent_node_tree() -> NodeTree:
    inputs = (
        ('OUTPUT', 'NodeSocketVector', 'Tangent'),
        ('INPUT', 'NodeSocketInt', 'Index'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        normalize_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        normalize_node.operation = 'NORMALIZE'

        vector_subtract_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_subtract_node.operation = 'SUBTRACT'

        evaluate_position_at_index_node_1 = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_position_at_index_node_1.data_type = 'FLOAT_VECTOR'
        evaluate_position_at_index_node_1.domain = 'POINT'

        evaluate_position_at_index_node_2 = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_position_at_index_node_2.data_type = 'FLOAT_VECTOR'
        evaluate_position_at_index_node_2.domain = 'POINT'

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

        node_tree.links.new(
            add_math_operation_nodes(node_tree, 'ADD', (input_node.outputs['Index'], 1.0)),
            evaluate_position_at_index_node_2.inputs['Index']
        )

        node_tree.links.new(position_node.outputs['Position'], evaluate_position_at_index_node_1.inputs['Value'])
        node_tree.links.new(position_node.outputs['Position'], evaluate_position_at_index_node_2.inputs['Value'])
        node_tree.links.new(input_node.outputs['Index'], evaluate_position_at_index_node_1.inputs['Index'])

        node_tree.links.new(evaluate_position_at_index_node_1.outputs['Value'], vector_subtract_node.inputs[0])
        node_tree.links.new(evaluate_position_at_index_node_2.outputs['Value'], vector_subtract_node.inputs[1])

        node_tree.links.new(vector_subtract_node.outputs['Vector'], normalize_node.inputs['Vector'])
        node_tree.links.new(normalize_node.outputs['Vector'], output_node.inputs['Tangent'])

    return ensure_geometry_node_tree('BDK Get Tangent', inputs, build_function)


def ensure_fence_point_tangent_and_normal_node_tree() -> NodeTree:
    inputs = (
        ('OUTPUT', 'NodeSocketVector', 'Normal'),
        ('OUTPUT', 'NodeSocketVector', 'Tangent'),
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        domain_size_node = node_tree.nodes.new(type='GeometryNodeAttributeDomainSize')
        domain_size_node.component = 'POINTCLOUD'

        tangent_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        tangent_switch_node.input_type = 'VECTOR'
        tangent_switch_node.label = 'Tangent Switch'

        node_tree.links.new(
            add_comparison_nodes(node_tree, 'INT', 'EQUAL',
                                 a=node_tree.nodes.new('GeometryNodeInputIndex').outputs['Index'],
                                 b=add_math_operation_nodes(node_tree, 'SUBTRACT',
                                                            (domain_size_node.outputs['Point Count'], 1.0))),
            tangent_switch_node.inputs['Switch']
        )

        node_tree.links.new(input_node.outputs['Geometry'], domain_size_node.inputs['Geometry'])

        non_cap_tangent_node = node_tree.nodes.new(type='GeometryNodeGroup')
        non_cap_tangent_node.node_tree = ensure_get_tangent_node_tree()

        cap_tangent_node = node_tree.nodes.new(type='GeometryNodeGroup')
        cap_tangent_node.node_tree = ensure_get_tangent_node_tree()

        node_tree.links.new(node_tree.nodes.new(type='GeometryNodeInputIndex').outputs['Index'],
                            non_cap_tangent_node.inputs['Index'])
        node_tree.links.new(
            add_math_operation_nodes(node_tree, 'SUBTRACT', (domain_size_node.outputs['Point Count'], 2.0)),
            cap_tangent_node.inputs['Index'])

        node_tree.links.new(non_cap_tangent_node.outputs['Tangent'], tangent_switch_node.inputs['False'])
        node_tree.links.new(cap_tangent_node.outputs['Tangent'], tangent_switch_node.inputs['True'])

        cross_product_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        cross_product_node.operation = 'CROSS_PRODUCT'

        up_vector_node = node_tree.nodes.new(type='FunctionNodeInputVector')
        up_vector_node.label = 'Up Vector'
        up_vector_node.vector = (0, 0, 1)

        node_tree.links.new(tangent_switch_node.outputs['Output'], cross_product_node.inputs[0])
        node_tree.links.new(up_vector_node.outputs['Vector'], cross_product_node.inputs[1])

        node_tree.links.new(tangent_switch_node.outputs['Output'], output_node.inputs['Tangent'])
        node_tree.links.new(cross_product_node.outputs['Vector'], output_node.inputs['Normal'])

    return ensure_geometry_node_tree('BDK Fence Point Tangent and Normal', inputs, build_function)


def ensure_bdk_curve_to_equidistant_points_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketFloat', 'Spacing Length'),
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
        ('OUTPUT', 'NodeSocketVector', 'Tangent'),
        ('OUTPUT', 'NodeSocketVector', 'Normal'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        def add_fence_mode_spline_loop_nodes(node_tree: NodeTree, loop_sockets: CurveSplineLoopSockets):
            curve_to_points_node = add_group_node(node_tree, ensure_curve_to_equidistant_points_node_tree)

            domain_size_node = node_tree.nodes.new(type='GeometryNodeAttributeDomainSize')
            domain_size_node.component = 'POINTCLOUD'

            store_curve_tangent_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_curve_tangent_attribute_node.label = 'Store Curve Tangent Attribute'
            store_curve_tangent_attribute_node.data_type = 'FLOAT_VECTOR'
            store_curve_tangent_attribute_node.inputs['Name'].default_value = 'curve_tangent'

            store_curve_normal_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_curve_normal_attribute_node.data_type = 'FLOAT_VECTOR'
            store_curve_normal_attribute_node.inputs['Name'].default_value = 'curve_normal'

            store_spline_index_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_spline_index_attribute_node.data_type = 'INT'
            store_spline_index_attribute_node.inputs['Name'].default_value = 'spline_index'

            store_is_cap_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_is_cap_attribute_node.data_type = 'BOOLEAN'
            store_is_cap_attribute_node.inputs['Name'].default_value = 'is_cap'
            store_is_cap_attribute_node.inputs['Value'].default_value = True

            check_is_cap_node = node_tree.nodes.new(type='FunctionNodeCompare')
            check_is_cap_node.data_type = 'INT'
            check_is_cap_node.operation = 'EQUAL'

            index_node = node_tree.nodes.new(type='GeometryNodeInputIndex')

            point_count_subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
            point_count_subtract_node.operation = 'SUBTRACT'
            point_count_subtract_node.inputs[1].default_value = 1.0

            fence_point_tangent_and_normals_node = node_tree.nodes.new(type='GeometryNodeGroup')
            fence_point_tangent_and_normals_node.node_tree = ensure_fence_point_tangent_and_normal_node_tree()

            store_radius_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_radius_attribute_node.data_type = 'FLOAT'
            store_radius_attribute_node.inputs['Name'].default_value = 'radius'

            node_tree.links.new(curve_to_points_node.outputs['Points'], store_radius_attribute_node.inputs['Geometry'])

            points_node = store_radius_attribute_node.outputs['Geometry']

            node_tree.links.new(points_node, fence_point_tangent_and_normals_node.inputs['Geometry'])
            node_tree.links.new(fence_point_tangent_and_normals_node.outputs['Normal'],
                                store_curve_normal_attribute_node.inputs['Value'])
            node_tree.links.new(fence_point_tangent_and_normals_node.outputs['Tangent'],
                                store_curve_tangent_attribute_node.inputs['Value'])
            node_tree.links.new(check_is_cap_node.outputs['Result'], store_is_cap_attribute_node.inputs['Selection'])
            node_tree.links.new(index_node.outputs['Index'], check_is_cap_node.inputs['A'])
            node_tree.links.new(point_count_subtract_node.outputs['Value'], check_is_cap_node.inputs['B'])
            node_tree.links.new(points_node, domain_size_node.inputs['Geometry'])
            node_tree.links.new(domain_size_node.outputs['Point Count'], point_count_subtract_node.inputs[0])
            node_tree.links.new(loop_sockets.spline_geometry_socket, curve_to_points_node.inputs['Curve'])
            node_tree.links.new(input_node.outputs['Spacing Length'], curve_to_points_node.inputs['Length'])
            node_tree.links.new(store_is_cap_attribute_node.outputs['Geometry'],
                                loop_sockets.join_geometry_input_socket)
            node_tree.links.new(points_node, store_curve_tangent_attribute_node.inputs['Geometry'])
            node_tree.links.new(store_curve_tangent_attribute_node.outputs['Geometry'],
                                store_curve_normal_attribute_node.inputs['Geometry'])
            node_tree.links.new(store_curve_normal_attribute_node.outputs['Geometry'],
                                store_spline_index_attribute_node.inputs['Geometry'])
            node_tree.links.new(store_spline_index_attribute_node.outputs['Geometry'],
                                store_is_cap_attribute_node.inputs['Geometry'])
            node_tree.links.new(loop_sockets.spline_index_socket, store_spline_index_attribute_node.inputs['Value'])

        geometry_socket = add_curve_spline_loop_nodes(node_tree, input_node.outputs['Curve'],
                                                      add_fence_mode_spline_loop_nodes)
        node_tree.links.new(geometry_socket, output_node.inputs['Points'])

        # Curve Normal
        evaluate_curve_normal_at_index_node = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_curve_normal_at_index_node.data_type = 'FLOAT_VECTOR'

        curve_normal_named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        curve_normal_named_attribute_node.data_type = 'FLOAT_VECTOR'
        curve_normal_named_attribute_node.inputs['Name'].default_value = 'curve_normal'

        node_tree.links.new(curve_normal_named_attribute_node.outputs['Attribute'],
                            evaluate_curve_normal_at_index_node.inputs['Value'])
        node_tree.links.new(node_tree.nodes.new(type='GeometryNodeInputIndex').outputs['Index'],
                            evaluate_curve_normal_at_index_node.inputs['Index'])
        node_tree.links.new(evaluate_curve_normal_at_index_node.outputs['Value'], output_node.inputs['Normal'])

        # Curve Tangent
        evaluate_curve_tangent_at_index_node = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_curve_tangent_at_index_node.data_type = 'FLOAT_VECTOR'

        curve_tangent_named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        curve_tangent_named_attribute_node.data_type = 'FLOAT_VECTOR'
        curve_tangent_named_attribute_node.inputs['Name'].default_value = 'curve_tangent'

        node_tree.links.new(curve_tangent_named_attribute_node.outputs['Attribute'],
                            evaluate_curve_tangent_at_index_node.inputs['Value'])
        node_tree.links.new(node_tree.nodes.new(type='GeometryNodeInputIndex').outputs['Index'],
                            evaluate_curve_tangent_at_index_node.inputs['Index'])
        node_tree.links.new(evaluate_curve_tangent_at_index_node.outputs['Value'], output_node.inputs['Tangent'])

    return ensure_geometry_node_tree('BDK Curve To Equidistant Points', items, build_function)


def ensure_curve_to_points_node_tree() -> NodeTree:
    inputs = (
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
        ('OUTPUT', 'NodeSocketVector', 'Tangent'),
        ('OUTPUT', 'NodeSocketVector', 'Normal'),
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketFloat', 'Length'),
        ('INPUT', 'NodeSocketBool', 'Fence Mode'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        curve_to_points_node = node_tree.nodes.new(type='GeometryNodeCurveToPoints')
        curve_to_points_node.mode = 'LENGTH'

        curve_to_equidistant_points_node = node_tree.nodes.new(type='GeometryNodeGroup')
        curve_to_equidistant_points_node.node_tree = ensure_bdk_curve_to_equidistant_points_node_tree()

        points_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        points_switch_node.input_type = 'GEOMETRY'

        tangent_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        tangent_switch_node.input_type = 'VECTOR'

        normal_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        normal_switch_node.input_type = 'VECTOR'

        links = [
            (input_node.outputs['Fence Mode'], points_switch_node.inputs['Switch']),
            (input_node.outputs['Fence Mode'], tangent_switch_node.inputs['Switch']),
            (input_node.outputs['Fence Mode'], normal_switch_node.inputs['Switch']),

            (input_node.outputs['Curve'], curve_to_equidistant_points_node.inputs['Curve']),
            (input_node.outputs['Length'], curve_to_equidistant_points_node.inputs['Spacing Length']),

            (input_node.outputs['Curve'], curve_to_points_node.inputs['Curve']),
            (input_node.outputs['Length'], curve_to_points_node.inputs['Length']),

            (curve_to_equidistant_points_node.outputs['Points'], points_switch_node.inputs['True']),
            (curve_to_points_node.outputs['Points'], points_switch_node.inputs['False']),
            (points_switch_node.outputs['Output'], output_node.inputs['Points']),

            (curve_to_equidistant_points_node.outputs['Tangent'], tangent_switch_node.inputs['True']),
            (curve_to_points_node.outputs['Tangent'], tangent_switch_node.inputs['False']),
            (tangent_switch_node.outputs['Output'], output_node.inputs['Tangent']),

            (curve_to_equidistant_points_node.outputs['Normal'], normal_switch_node.inputs['True']),
            (curve_to_points_node.outputs['Normal'], normal_switch_node.inputs['False']),
            (normal_switch_node.outputs['Output'], output_node.inputs['Normal']),
        ]

        for link in links:
            node_tree.links.new(*link)

    return ensure_geometry_node_tree('BDK Curve To Points', inputs, build_function)


def ensure_scatter_layer_origin_offset_node_tree() -> NodeTree:
    inputs = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketVector', 'Origin Offset'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')
        set_position_node.inputs["Selection"].default_value = True

        tangent_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        tangent_attribute_node.label = 'Tangent Attribute'
        tangent_attribute_node.data_type = 'FLOAT_VECTOR'
        tangent_attribute_node.inputs["Name"].default_value = 'curve_tangent'

        scale_tangent_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        scale_tangent_node.label = 'Scale Tangent'
        scale_tangent_node.operation = 'SCALE'

        add_scale_and_tangent_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        add_scale_and_tangent_node.label = 'Add Scale And Tangent'

        normal_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        normal_attribute_node.label = 'Normal Attribute'
        normal_attribute_node.data_type = 'FLOAT_VECTOR'
        normal_attribute_node.inputs["Name"].default_value = 'curve_normal'

        scale_normal_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        scale_normal_node.label = 'Scale Normal'
        scale_normal_node.operation = 'SCALE'

        final_add_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        final_add_node.label = 'Final Add'

        up_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        up_attribute_node.label = 'Up Attribute'
        up_attribute_node.data_type = 'FLOAT_VECTOR'
        up_attribute_node.inputs["Name"].default_value = 'terrain_normal'

        scale_up_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        scale_up_node.label = 'Scale Up'
        scale_up_node.operation = 'SCALE'

        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        scale_multiply_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        scale_multiply_node.label = 'Scale Multiply'
        scale_multiply_node.operation = 'MULTIPLY'

        scale_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        scale_attribute_node.label = 'Scale Attribute'
        scale_attribute_node.data_type = 'FLOAT_VECTOR'
        scale_attribute_node.inputs["Name"].default_value = 'scale'

        # Internal Links
        node_tree.links.new(separate_xyz_node.outputs['X'], scale_tangent_node.inputs['Scale'])  # X -> Scale
        node_tree.links.new(add_scale_and_tangent_node.outputs['Vector'], final_add_node.inputs[0])  # Vector -> Vector
        node_tree.links.new(input_node.outputs['Origin Offset'], separate_xyz_node.inputs['Vector'])  # Vector -> Vector
        node_tree.links.new(up_attribute_node.outputs['Attribute'],
                            scale_up_node.inputs['Vector'])  # Attribute -> Vector
        node_tree.links.new(separate_xyz_node.outputs['Z'], scale_up_node.inputs['Scale'])  # Z -> Scale
        node_tree.links.new(scale_normal_node.outputs['Vector'],
                            add_scale_and_tangent_node.inputs[1])  # Vector -> Vector
        node_tree.links.new(scale_up_node.outputs['Vector'], final_add_node.inputs[1])  # Vector -> Vector
        node_tree.links.new(normal_attribute_node.outputs['Attribute'],
                            scale_normal_node.inputs['Vector'])  # Attribute -> Vector
        node_tree.links.new(separate_xyz_node.outputs['Y'], scale_normal_node.inputs['Scale'])  # Y -> Scale
        node_tree.links.new(tangent_attribute_node.outputs['Attribute'],
                            scale_tangent_node.inputs['Vector'])  # Attribute -> Vector
        node_tree.links.new(scale_tangent_node.outputs['Vector'],
                            add_scale_and_tangent_node.inputs[0])  # Vector -> Vector
        node_tree.links.new(final_add_node.outputs['Vector'], scale_multiply_node.inputs[0])  # Vector -> Vector
        node_tree.links.new(scale_attribute_node.outputs['Attribute'],
                            scale_multiply_node.inputs[1])  # Attribute -> Vector
        node_tree.links.new(scale_multiply_node.outputs['Vector'],
                            set_position_node.inputs['Offset'])  # Vector -> Offset

        # Incoming Links
        node_tree.links.new(input_node.outputs['Geometry'], set_position_node.inputs['Geometry'])

        # Outgoing Links
        node_tree.links.new(set_position_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Scatter Layer Object Origin Offset', inputs, build_function)


def ensure_scatter_layer_curve_to_points_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketBool', 'Fence Mode'),
        ('INPUT', 'NodeSocketFloat', 'Spacing Length'),
        ('INPUT', 'NodeSocketFloat', 'Normal Offset Max'),
        ('INPUT', 'NodeSocketInt', 'Normal Offset Seed'),
        ('INPUT', 'NodeSocketFloat', 'Tangent Offset Max'),
        ('INPUT', 'NodeSocketInt', 'Tangent Offset Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        curve_to_points_node = node_tree.nodes.new(type='GeometryNodeGroup')
        curve_to_points_node.node_tree = ensure_curve_to_points_node_tree()

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

        normal_offset_seed_socket = add_math_operation_nodes(node_tree, 'ADD',
                                                             [input_node.outputs['Normal Offset Seed'],
                                                              input_node.outputs['Global Seed']])
        tangent_offset_seed_socket = add_math_operation_nodes(node_tree, 'ADD',
                                                              [input_node.outputs['Tangent Offset Seed'],
                                                               input_node.outputs['Global Seed']])

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
        node_tree.links.new(input_node.outputs['Normal Offset Max'], normal_offset_random_value_node.inputs['Max'])
        node_tree.links.new(input_node.outputs['Tangent Offset Max'], tangent_offset_negate_node.inputs[0])
        node_tree.links.new(input_node.outputs['Tangent Offset Max'], tangent_offset_random_value_node.inputs['Max'])
        node_tree.links.new(input_node.outputs['Fence Mode'], curve_to_points_node.inputs['Fence Mode'])

        # Internal
        node_tree.links.new(normal_scale_node.outputs['Vector'], add_offsets_node.inputs[0])
        node_tree.links.new(tangent_scale_node.outputs['Vector'], add_offsets_node.inputs[1])
        node_tree.links.new(add_offsets_node.outputs['Vector'], set_position_node.inputs['Offset'])
        node_tree.links.new(normal_offset_random_value_node.outputs['Value'], normal_scale_node.inputs['Scale'])
        node_tree.links.new(curve_to_points_node.outputs['Points'], set_position_node.inputs['Geometry'])
        node_tree.links.new(set_position_node.outputs['Geometry'],
                            store_curve_tangent_attribute_node.inputs['Geometry'])
        node_tree.links.new(curve_to_points_node.outputs['Normal'], store_curve_normal_attribute_node.inputs['Value'])
        node_tree.links.new(curve_to_points_node.outputs['Tangent'], store_curve_tangent_attribute_node.inputs['Value'])
        node_tree.links.new(store_curve_tangent_attribute_node.outputs['Geometry'],
                            store_curve_normal_attribute_node.inputs['Geometry'])
        node_tree.links.new(normal_offset_seed_socket, normal_offset_random_value_node.inputs['Seed'])
        node_tree.links.new(curve_to_points_node.outputs['Normal'], normal_scale_node.inputs[0])  # Normal -> Vector
        node_tree.links.new(normal_offset_negate_node.outputs['Value'], normal_offset_random_value_node.inputs['Min'])
        node_tree.links.new(normal_offset_random_value_node.outputs[1], normal_scale_node.inputs['Scale'])
        node_tree.links.new(curve_to_points_node.outputs['Tangent'], tangent_scale_node.inputs[0])  # Tangent -> Vector
        node_tree.links.new(tangent_offset_negate_node.outputs['Value'], tangent_offset_random_value_node.inputs['Min'])
        node_tree.links.new(tangent_offset_random_value_node.outputs['Value'], tangent_scale_node.inputs['Scale'])
        node_tree.links.new(curve_to_points_node.outputs['Points'], set_position_node.inputs['Geometry'])

        # Output
        node_tree.links.new(store_curve_normal_attribute_node.outputs['Geometry'], output_node.inputs['Points'])

    return ensure_geometry_node_tree('BDK Scatter Layer Curve To Points', items, build_function)


def ensure_select_object_index_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketBool', 'Selection'),
        ('INPUT', 'NodeSocketInt', 'Object Count'),
        ('INPUT', 'NodeSocketInt', 'Object Select Mode'),
        ('INPUT', 'NodeSocketInt', 'Object Index Offset'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
        ('INPUT', 'NodeSocketInt', 'Object Select Seed'),
        ('INPUT', 'NodeSocketFloat', 'Random Weight 0'),
        ('INPUT', 'NodeSocketFloat', 'Random Weight 1'),
        ('INPUT', 'NodeSocketFloat', 'Random Weight 2'),
        ('INPUT', 'NodeSocketFloat', 'Random Weight 3'),
        ('INPUT', 'NodeSocketFloat', 'Random Weight 4'),
        ('INPUT', 'NodeSocketFloat', 'Random Weight 5'),
        ('INPUT', 'NodeSocketFloat', 'Random Weight 6'),
        ('INPUT', 'NodeSocketFloat', 'Random Weight 7'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'INT'
        store_named_attribute_node.domain = 'POINT'
        store_named_attribute_node.inputs['Name'].default_value = 'object_index'

        seed_socket = add_math_operation_nodes(node_tree, 'ADD', [input_node.outputs['Object Select Seed'],
                                                                  input_node.outputs['Global Seed']])

        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = 'FLOORED_MODULO'

        index_node = node_tree.nodes.new(type='GeometryNodeInputIndex')
        random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        random_value_node.data_type = 'INT'

        object_index_offset_node = node_tree.nodes.new(type='ShaderNodeMath')
        object_index_offset_node.label = 'Object Index Offset'

        subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
        subtract_node.operation = 'SUBTRACT'
        subtract_node.inputs[1].default_value = 1

        weighted_index_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        weighted_index_node_group_node.node_tree = ensure_weighted_index_node_tree()

        mode_value_sockets = [
            random_value_node.outputs[2],  # Random,
            math_node.outputs['Value'],  # Cyclic
            weighted_index_node_group_node.outputs['Index'],  # Weighted Random
        ]

        object_index_socket = add_geometry_node_switch_nodes(node_tree, input_node.outputs['Object Select Mode'],
                                                             mode_value_sockets)

        # Input
        node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Object Count'], subtract_node.inputs[0])
        node_tree.links.new(input_node.outputs['Object Index Offset'], object_index_offset_node.inputs[1])
        node_tree.links.new(input_node.outputs['Object Count'], math_node.inputs[1])
        node_tree.links.new(input_node.outputs['Random Weight 0'], weighted_index_node_group_node.inputs['Weight 0'])
        node_tree.links.new(input_node.outputs['Random Weight 1'], weighted_index_node_group_node.inputs['Weight 1'])
        node_tree.links.new(input_node.outputs['Random Weight 2'], weighted_index_node_group_node.inputs['Weight 2'])
        node_tree.links.new(input_node.outputs['Random Weight 3'], weighted_index_node_group_node.inputs['Weight 3'])
        node_tree.links.new(input_node.outputs['Random Weight 4'], weighted_index_node_group_node.inputs['Weight 4'])
        node_tree.links.new(input_node.outputs['Random Weight 5'], weighted_index_node_group_node.inputs['Weight 5'])
        node_tree.links.new(input_node.outputs['Random Weight 6'], weighted_index_node_group_node.inputs['Weight 6'])
        node_tree.links.new(input_node.outputs['Random Weight 7'], weighted_index_node_group_node.inputs['Weight 7'])
        node_tree.links.new(seed_socket, weighted_index_node_group_node.inputs['Seed'])
        node_tree.links.new(input_node.outputs['Selection'], store_named_attribute_node.inputs['Selection'])

        # Internal
        node_tree.links.new(seed_socket, random_value_node.inputs['Seed'])
        node_tree.links.new(subtract_node.outputs['Value'], random_value_node.inputs['Max'])
        node_tree.links.new(object_index_socket, store_named_attribute_node.inputs['Value'])
        node_tree.links.new(index_node.outputs['Index'], object_index_offset_node.inputs[0])
        node_tree.links.new(object_index_offset_node.outputs['Value'], math_node.inputs[0])

        # Output
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Select Object Index', items, build_function)


def ensure_terrain_normal_offset_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketFloat', 'Terrain Normal Offset Min'),
        ('INPUT', 'NodeSocketFloat', 'Terrain Normal Offset Max'),
        ('INPUT', 'NodeSocketInt', 'Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        seed_socket = add_math_operation_nodes(node_tree, 'ADD',
                                               [input_node.outputs['Seed'], input_node.outputs['Global Seed']])

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
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Points'),
        ('INPUT', 'NodeSocketGeometry', 'Terrain Geometry'),
        ('INPUT', 'NodeSocketMatrix', 'Terrain Transform'),
        ('INPUT', 'NodeSocketInt', 'Terrain Resolution'),
        ('INPUT', 'NodeSocketInt', 'Object Index'),
        ('INPUT', 'NodeSocketInt', 'Scale Mode'),
        ('INPUT', 'NodeSocketFloat', 'Scale Uniform'),
        ('INPUT', 'NodeSocketVector', 'Scale'),
        ('INPUT', 'NodeSocketFloat', 'Scale Uniform Min'),
        ('INPUT', 'NodeSocketFloat', 'Scale Uniform Max'),
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
        ('INPUT', 'NodeSocketVector', 'Rotation Offset'),
        ('INPUT', 'NodeSocketFloat', 'Rotation Offset Saturation'),
        ('INPUT', 'NodeSocketInt', 'Rotation Offset Saturation Seed'),
        ('INPUT', 'NodeSocketVector', 'Random Rotation Max'),
        ('INPUT', 'NodeSocketInt', 'Random Rotation Seed'),
        ('INPUT', 'NodeSocketBool', 'Fence Mode'),
        ('INPUT', 'NodeSocketVector', 'Origin Offset'),
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
    )

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
        scale_mix_node.label = 'Scale Mix'

        scale_uniform_mix_node = node_tree.nodes.new(type='ShaderNodeMix')
        scale_uniform_mix_node.data_type = 'VECTOR'
        scale_uniform_mix_node.label = 'Scale Uniform Mix'

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

        scale_seed_socket = add_math_operation_nodes(node_tree, 'ADD', [input_node.outputs['Scale Seed'],
                                                                        input_node.outputs['Global Seed']])

        scale_multiply_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        scale_multiply_node.operation = 'MULTIPLY'

        scale_uniform_multiply_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        scale_uniform_multiply_node.operation = 'MULTIPLY'

        scale_output_socket = add_geometry_node_switch_nodes(node_tree, input_node.outputs['Scale Mode'],
                                                             [scale_uniform_multiply_node.outputs[0],
                                                              scale_multiply_node.outputs[0]], input_type='VECTOR')

        origin_offset_node = node_tree.nodes.new(type='GeometryNodeGroup')
        origin_offset_node.node_tree = ensure_scatter_layer_origin_offset_node_tree()

        # Input
        node_tree.links.new(input_node.outputs['Scale Min'], scale_mix_node.inputs[4])
        node_tree.links.new(input_node.outputs['Scale Max'], scale_mix_node.inputs[5])
        node_tree.links.new(input_node.outputs['Mute'], mute_switch_node.inputs[1])
        node_tree.links.new(input_node.outputs['Align to Terrain Factor'],
                            align_to_terrain_node_group_node.inputs['Factor'])
        node_tree.links.new(input_node.outputs['Terrain Geometry'],
                            snap_to_terrain_group_node.inputs['Terrain Geometry'])
        node_tree.links.new(input_node.outputs['Terrain Resolution'], snap_to_terrain_group_node.inputs['Terrain Resolution'])
        node_tree.links.new(input_node.outputs['Snap to Terrain'], snap_to_terrain_group_node.inputs['Mute'])
        node_tree.links.new(input_node.outputs['Object Index'], compare_node.inputs[3])
        node_tree.links.new(input_node.outputs['Points'], separate_geometry_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Terrain Normal Offset Min'],
                            terrain_normal_offset_node_group_node.inputs['Terrain Normal Offset Min'])
        node_tree.links.new(input_node.outputs['Terrain Normal Offset Max'],
                            terrain_normal_offset_node_group_node.inputs['Terrain Normal Offset Max'])
        node_tree.links.new(input_node.outputs['Terrain Normal Offset Seed'],
                            terrain_normal_offset_node_group_node.inputs['Seed'])
        node_tree.links.new(input_node.outputs['Global Seed'],
                            terrain_normal_offset_node_group_node.inputs['Global Seed'])
        node_tree.links.new(input_node.outputs['Rotation Offset'],
                            align_to_terrain_node_group_node.inputs['Rotation Offset'])
        node_tree.links.new(input_node.outputs['Rotation Offset Saturation'],
                            align_to_terrain_node_group_node.inputs['Rotation Offset Saturation'])
        node_tree.links.new(input_node.outputs['Rotation Offset Saturation Seed'],
                            align_to_terrain_node_group_node.inputs['Rotation Offset Saturation Seed'])
        node_tree.links.new(input_node.outputs['Random Rotation Max'],
                            align_to_terrain_node_group_node.inputs['Random Rotation Max'])
        node_tree.links.new(input_node.outputs['Random Rotation Seed'],
                            align_to_terrain_node_group_node.inputs['Random Rotation Seed'])
        node_tree.links.new(input_node.outputs['Global Seed'], align_to_terrain_node_group_node.inputs['Global Seed'])
        node_tree.links.new(input_node.outputs['Scale Uniform'], scale_uniform_multiply_node.inputs[1])
        node_tree.links.new(input_node.outputs['Scale Uniform Min'], scale_uniform_mix_node.inputs[4])
        node_tree.links.new(input_node.outputs['Scale Uniform Max'], scale_uniform_mix_node.inputs[5])
        node_tree.links.new(input_node.outputs['Scale'], scale_multiply_node.inputs[1])  # Scale -> Vector
        node_tree.links.new(input_node.outputs['Fence Mode'], align_to_terrain_node_group_node.inputs['Fence Mode'])
        node_tree.links.new(input_node.outputs['Origin Offset'], origin_offset_node.inputs['Origin Offset'])
        node_tree.links.new(input_node.outputs['Terrain Transform'], snap_to_terrain_group_node.inputs['Terrain Transform'])

        # Internal
        node_tree.links.new(scale_seed_socket, scale_random_value_node.inputs['Seed'])
        node_tree.links.new(object_index_attribute_node.outputs['Attribute'], compare_node.inputs['A'])
        node_tree.links.new(compare_node.outputs['Result'], separate_geometry_node.inputs['Selection'])
        node_tree.links.new(scale_output_socket, store_scale_attribute_node.inputs['Value'])
        node_tree.links.new(snap_to_terrain_group_node.outputs['Geometry'],
                            align_to_terrain_node_group_node.inputs['Geometry'])
        node_tree.links.new(align_to_terrain_node_group_node.outputs['Geometry'],
                            terrain_normal_offset_node_group_node.inputs['Geometry'])
        node_tree.links.new(terrain_normal_offset_node_group_node.outputs['Geometry'],
                            store_scale_attribute_node.inputs['Geometry'])
        node_tree.links.new(store_scale_attribute_node.outputs['Geometry'], origin_offset_node.inputs['Geometry'])
        node_tree.links.new(origin_offset_node.outputs['Geometry'], mute_switch_node.inputs['False'])
        node_tree.links.new(scale_random_value_node.outputs[1], scale_mix_node.inputs['Factor'])
        node_tree.links.new(scale_random_value_node.outputs[1], scale_uniform_mix_node.inputs['Factor'])
        node_tree.links.new(separate_geometry_node.outputs['Selection'], snap_to_terrain_group_node.inputs['Geometry'])
        node_tree.links.new(scale_uniform_mix_node.outputs['Result'], scale_uniform_multiply_node.inputs[0])
        node_tree.links.new(scale_mix_node.outputs['Result'], scale_multiply_node.inputs[0])

        # Output
        node_tree.links.new(mute_switch_node.outputs['Output'], output_node.inputs['Points'])

    return ensure_geometry_node_tree('BDK Scatter Layer Object', items, build_function)


def ensure_scatter_layer_mesh_to_points_node_tree() -> NodeTree:
    inputs = (
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
        ('INPUT', 'NodeSocketGeometry', 'Mesh'),
        ('INPUT', 'NodeSocketInt', 'Element Mode'),
        ('INPUT', 'NodeSocketInt', 'Face Distribute Method'),
        ('INPUT', 'NodeSocketFloat', 'Face Distribute Random Density'),
        ('INPUT', 'NodeSocketFloat', 'Face Distribute Poisson Distance Min'),
        ('INPUT', 'NodeSocketFloat', 'Face Distribute Poisson Density Max'),
        ('INPUT', 'NodeSocketFloat', 'Face Distribute Poisson Density Factor'),
        ('INPUT', 'NodeSocketInt', 'Face Distribute Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        seed_socket = add_math_operation_nodes(node_tree, 'ADD', [input_node.outputs['Face Distribute Seed'],
                                                                  input_node.outputs['Global Seed']])

        distribute_points_on_faces_random_node = node_tree.nodes.new(type='GeometryNodeDistributePointsOnFaces')
        distribute_points_on_faces_random_node.distribute_method = 'RANDOM'

        distribute_points_on_faces_poisson_node = node_tree.nodes.new(type='GeometryNodeDistributePointsOnFaces')
        distribute_points_on_faces_poisson_node.distribute_method = 'POISSON'

        mesh_to_points_node = node_tree.nodes.new(type='GeometryNodeMeshToPoints')

        face_distributed_points_socket = add_geometry_node_switch_nodes(
            node_tree,
            input_node.outputs['Face Distribute Method'],
            [distribute_points_on_faces_random_node.outputs['Points'],
             distribute_points_on_faces_poisson_node.outputs['Points']],
            input_type='GEOMETRY'
        )

        element_mode_switch_socket = add_geometry_node_switch_nodes(
            node_tree,
            input_node.outputs['Element Mode'],
            [face_distributed_points_socket, mesh_to_points_node.outputs['Points']],
            input_type='GEOMETRY'
        )

        # Input
        node_tree.links.new(input_node.outputs['Mesh'], mesh_to_points_node.inputs['Mesh'])
        node_tree.links.new(input_node.outputs['Mesh'], distribute_points_on_faces_random_node.inputs['Mesh'])
        node_tree.links.new(input_node.outputs['Mesh'], distribute_points_on_faces_poisson_node.inputs['Mesh'])
        node_tree.links.new(input_node.outputs['Face Distribute Random Density'],
                            distribute_points_on_faces_random_node.inputs['Density'])
        node_tree.links.new(input_node.outputs['Face Distribute Poisson Distance Min'],
                            distribute_points_on_faces_poisson_node.inputs['Distance Min'])
        node_tree.links.new(input_node.outputs['Face Distribute Poisson Density Max'],
                            distribute_points_on_faces_poisson_node.inputs['Density Max'])
        node_tree.links.new(input_node.outputs['Face Distribute Poisson Density Factor'],
                            distribute_points_on_faces_poisson_node.inputs['Density Factor'])

        # Internal
        node_tree.links.new(seed_socket, distribute_points_on_faces_random_node.inputs['Seed'])
        node_tree.links.new(seed_socket, distribute_points_on_faces_poisson_node.inputs['Seed'])

        # Output
        node_tree.links.new(element_mode_switch_socket, output_node.inputs['Points'])

    return ensure_geometry_node_tree('BDK Scatter Layer Mesh To Points', inputs, build_function)


def ensure_scatter_layer_position_deviation_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Points'),
        ('INPUT', 'NodeSocketFloat', 'Deviation Min'),
        ('INPUT', 'NodeSocketFloat', 'Deviation Max'),
        ('INPUT', 'NodeSocketInt', 'Seed'),
        ('INPUT', 'NodeSocketInt', 'Global Seed'),
        ('INPUT', 'NodeSocketBool', 'Selection'),
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')
        rotate_vector_node = node_tree.nodes.new(type='FunctionNodeRotateVector')
        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')
        euler_to_rotation_node = node_tree.nodes.new(type='FunctionNodeEulerToRotation')
        combine_xyz_node_2 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        random_direction_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        random_direction_node.label = 'Random Direction'
        random_direction_node.inputs['Max'].default_value = 360.0

        random_value_node = node_tree.nodes.new(type='FunctionNodeRandomValue')
        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = 'ADD'

        # Input
        node_tree.links.new(input_node.outputs['Points'], set_position_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Seed'], math_node.inputs[0])
        node_tree.links.new(input_node.outputs['Global Seed'], math_node.inputs[1])
        node_tree.links.new(input_node.outputs['Deviation Min'], random_value_node.inputs['Min'])
        node_tree.links.new(input_node.outputs['Deviation Max'], random_value_node.inputs['Max'])
        node_tree.links.new(input_node.outputs['Selection'], set_position_node.inputs['Selection'])

        # Internal
        node_tree.links.new(combine_xyz_node.outputs['Vector'], euler_to_rotation_node.inputs['Euler'])
        node_tree.links.new(math_node.outputs['Value'], random_value_node.inputs['Seed'])
        node_tree.links.new(rotate_vector_node.outputs['Vector'], set_position_node.inputs['Offset'])
        node_tree.links.new(math_node.outputs['Value'], random_direction_node.inputs['Seed'])
        node_tree.links.new(random_direction_node.outputs['Value'], combine_xyz_node.inputs['Z'])
        node_tree.links.new(euler_to_rotation_node.outputs['Rotation'], rotate_vector_node.inputs['Rotation'])
        node_tree.links.new(combine_xyz_node_2.outputs['Vector'], rotate_vector_node.inputs['Vector'])
        node_tree.links.new(random_value_node.outputs['Value'], combine_xyz_node_2.inputs['X'])

        # Output
        node_tree.links.new(set_position_node.outputs['Geometry'], output_node.inputs['Points'])

    return ensure_geometry_node_tree('BDK Scatter Layer Deviation', items, build_function)


def ensure_scatter_layer_planter_node_tree(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> NodeTree:
    terrain_doodad_object = scatter_layer.terrain_doodad_object
    terrain_info = terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info

    items = (
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        def add_scatter_layer_driver(struct: bpy_struct, data_path: str, index: int = -1, path: str = 'default_value'):
            _add_scatter_layer_driver_ex(
                struct,
                terrain_doodad_object,
                data_path,
                index,
                path,
                scatter_layer_index=scatter_layer.index
            )

        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        terrain_doodad_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
        terrain_doodad_object_info_node.inputs['Object'].default_value = terrain_doodad_object
        terrain_doodad_object_info_node.transform_space = 'RELATIVE'

        points_socket = None

        match scatter_layer.geometry_source:
            case 'SCATTER_LAYER':
                terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
                # Find the scatter layer that the current scatter layer is based on.
                geometry_source_scatter_layer = None
                for doodad_scatter_layer in terrain_doodad.scatter_layers:
                    if doodad_scatter_layer.id == scatter_layer.geometry_source_id:
                        geometry_source_scatter_layer = doodad_scatter_layer
                if geometry_source_scatter_layer:
                    scatter_layer_seed_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
                    scatter_layer_seed_object_info_node.inputs[
                        'Object'].default_value = geometry_source_scatter_layer.seed_object

                    mesh_to_points_node = node_tree.nodes.new(type='GeometryNodeMeshToPoints')

                    node_tree.links.new(scatter_layer_seed_object_info_node.outputs['Geometry'],
                                        mesh_to_points_node.inputs['Mesh'])

                    points_socket = mesh_to_points_node.outputs['Points']
            case 'DOODAD':
                match scatter_layer.terrain_doodad_object.type:
                    case 'CURVE':
                        # Get the maximum length of all the objects in the scatter layer.
                        length_sockets = []
                        for scatter_layer_object in scatter_layer.objects:
                            size_socket = add_object_extents(node_tree, scatter_layer_object.object)
                            vector_component_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
                            vector_component_group_node.node_tree = ensure_vector_component_node_tree()
                            node_tree.links.new(size_socket, vector_component_group_node.inputs['Vector'])
                            add_scatter_layer_driver(vector_component_group_node.inputs['Index'],
                                                     'curve_spacing_relative_axis')
                            length_sockets.append(vector_component_group_node.outputs['Value'])
                        spacing_length_socket = add_chained_math_nodes(node_tree, 'MAXIMUM', length_sockets)

                        spacing_mode_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
                        spacing_mode_switch_node.input_type = 'FLOAT'
                        add_scatter_layer_driver(spacing_mode_switch_node.inputs['Switch'], 'curve_spacing_method')
                        add_scatter_layer_driver(spacing_mode_switch_node.inputs['True'], 'curve_spacing_absolute')

                        spacing_relative_factor_node = node_tree.nodes.new(type='ShaderNodeMath')
                        spacing_relative_factor_node.operation = 'MULTIPLY'

                        if spacing_length_socket:
                            node_tree.links.new(spacing_length_socket, spacing_relative_factor_node.inputs[0])

                        add_scatter_layer_driver(spacing_relative_factor_node.inputs[1],
                                                 'curve_spacing_relative_factor')

                        node_tree.links.new(spacing_relative_factor_node.outputs['Value'],
                                            spacing_mode_switch_node.inputs['False'])

                        spacing_length_socket = spacing_mode_switch_node.outputs['Output']

                        curve_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
                        curve_switch_node.input_type = 'GEOMETRY'

                        add_scatter_layer_driver(curve_switch_node.inputs['Switch'], 'use_curve_modifiers')

                        curve_modifier_node = node_tree.nodes.new(type='GeometryNodeGroup')
                        curve_modifier_node.node_tree = ensure_curve_modifier_node_tree()
                        add_scatter_layer_driver(curve_modifier_node.inputs['Is Curve Reversed'], 'is_curve_reversed')
                        add_scatter_layer_driver(curve_modifier_node.inputs['Trim Mode'], 'curve_trim_mode')
                        add_scatter_layer_driver(curve_modifier_node.inputs['Trim Factor Start'], 'curve_trim_factor_start')
                        add_scatter_layer_driver(curve_modifier_node.inputs['Trim Factor End'], 'curve_trim_factor_end')
                        add_scatter_layer_driver(curve_modifier_node.inputs['Trim Length Start'], 'curve_trim_length_start')
                        add_scatter_layer_driver(curve_modifier_node.inputs['Trim Length End'], 'curve_trim_length_end')
                        add_scatter_layer_driver(curve_modifier_node.inputs['Normal Offset'], 'curve_normal_offset')

                        curve_to_points_node = node_tree.nodes.new(type='GeometryNodeGroup')
                        curve_to_points_node.node_tree = ensure_scatter_layer_curve_to_points_node_tree()
                        add_scatter_layer_driver(curve_to_points_node.inputs['Normal Offset Max'], 'curve_normal_offset_max')
                        add_scatter_layer_driver(curve_to_points_node.inputs['Normal Offset Seed'], 'curve_normal_offset_seed')
                        add_scatter_layer_driver(curve_to_points_node.inputs['Tangent Offset Max'], 'curve_tangent_offset_max')
                        add_scatter_layer_driver(curve_to_points_node.inputs['Tangent Offset Seed'], 'curve_tangent_offset_seed')
                        add_scatter_layer_driver(curve_to_points_node.inputs['Global Seed'], 'global_seed')
                        add_scatter_layer_driver(curve_to_points_node.inputs['Fence Mode'], 'fence_mode')

                        shrinkwrap_curve_to_terrain_node = node_tree.nodes.new(type='GeometryNodeGroup')
                        shrinkwrap_curve_to_terrain_node.node_tree = ensure_shrinkwrap_curve_to_terrain_node_tree()
                        shrinkwrap_curve_to_terrain_node.inputs['Terrain Resolution'].default_value = terrain_info.x_size

                        shrinkwrap_curve_to_terrain_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
                        shrinkwrap_curve_to_terrain_switch_node.input_type = 'GEOMETRY'

                        add_scatter_layer_driver(shrinkwrap_curve_to_terrain_switch_node.inputs['Switch'], 'fence_mode')

                        terrain_info_object_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
                        terrain_info_object_node.inputs['Object'].default_value = terrain_info.terrain_info_object

                        node_tree.links.new(terrain_doodad_object_info_node.outputs['Geometry'], curve_modifier_node.inputs['Curve'])
                        node_tree.links.new(curve_switch_node.outputs['Output'], shrinkwrap_curve_to_terrain_node.inputs['Curve'])
                        node_tree.links.new(terrain_info_object_node.outputs['Geometry'], shrinkwrap_curve_to_terrain_node.inputs['Terrain Geometry'])
                        node_tree.links.new(terrain_info_object_node.outputs['Transform'], shrinkwrap_curve_to_terrain_node.inputs['Terrain Transform'])

                        node_tree.links.new(shrinkwrap_curve_to_terrain_node.outputs['Curve'], shrinkwrap_curve_to_terrain_switch_node.inputs['True'])
                        node_tree.links.new(curve_switch_node.outputs['Output'], shrinkwrap_curve_to_terrain_switch_node.inputs['False'])

                        node_tree.links.new(terrain_doodad_object_info_node.outputs['Geometry'], curve_switch_node.inputs['False'])
                        node_tree.links.new(curve_modifier_node.outputs['Curve'], curve_switch_node.inputs['True'])
                        node_tree.links.new(shrinkwrap_curve_to_terrain_switch_node.outputs['Output'], curve_to_points_node.inputs['Curve'])

                        if spacing_length_socket is not None:
                            node_tree.links.new(spacing_length_socket, curve_to_points_node.inputs['Spacing Length'])

                        points_socket = curve_to_points_node.outputs['Points']
                    case 'EMPTY':
                        # TODO: we're gonna certainly want more options here (e.g., random distance/angle from the
                        #  center)
                        points_node = node_tree.nodes.new(type='GeometryNodePoints')
                        node_tree.links.new(terrain_doodad_object_info_node.outputs['Location'],
                                            points_node.inputs['Position'])
                        points_socket = points_node.outputs['Geometry']
                    case 'MESH':
                        mesh_to_points_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
                        mesh_to_points_node_group_node.node_tree = ensure_scatter_layer_mesh_to_points_node_tree()

                        add_scatter_layer_driver(mesh_to_points_node_group_node.inputs['Face Distribute Method'],
                                                 'mesh_face_distribute_method')
                        add_scatter_layer_driver(
                            mesh_to_points_node_group_node.inputs['Face Distribute Random Density'],
                            'mesh_face_distribute_random_density')
                        add_scatter_layer_driver(
                            mesh_to_points_node_group_node.inputs['Face Distribute Poisson Distance Min'],
                            'mesh_face_distribute_poisson_distance_min')
                        add_scatter_layer_driver(
                            mesh_to_points_node_group_node.inputs['Face Distribute Poisson Density Max'],
                            'mesh_face_distribute_poisson_density_max')
                        add_scatter_layer_driver(
                            mesh_to_points_node_group_node.inputs['Face Distribute Poisson Density Factor'],
                            'mesh_face_distribute_poisson_density_factor')
                        add_scatter_layer_driver(mesh_to_points_node_group_node.inputs['Face Distribute Seed'],
                                                 'mesh_face_distribute_seed')
                        add_scatter_layer_driver(mesh_to_points_node_group_node.inputs['Global Seed'], 'global_seed')
                        add_scatter_layer_driver(mesh_to_points_node_group_node.inputs['Element Mode'],
                                                 'mesh_element_mode')

                        node_tree.links.new(terrain_doodad_object_info_node.outputs['Geometry'],
                                            mesh_to_points_node_group_node.inputs['Mesh'])

                        points_socket = mesh_to_points_node_group_node.outputs['Points']
                    case _:
                        raise RuntimeError(
                            'Unsupported terrain doodad object type: ' + scatter_layer.terrain_doodad_object.type)

        # Position Deviation
        use_deviation_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        use_deviation_switch_node.input_type = 'GEOMETRY'
        add_scatter_layer_driver(use_deviation_switch_node.inputs['Switch'], 'use_position_deviation')

        deviation_node = node_tree.nodes.new(type='GeometryNodeGroup')
        deviation_node.node_tree = ensure_scatter_layer_position_deviation_node_tree()

        # TODO: have this in the node itself
        deviation_node.inputs['Selection'].default_value = True

        add_scatter_layer_driver(deviation_node.inputs['Deviation Min'], 'position_deviation_min')
        add_scatter_layer_driver(deviation_node.inputs['Deviation Max'], 'position_deviation_max')
        add_scatter_layer_driver(deviation_node.inputs['Seed'], 'position_deviation_seed')
        add_scatter_layer_driver(deviation_node.inputs['Global Seed'], 'global_seed')

        if points_socket:
            # Density modifier.
            select_random_node = node_tree.nodes.new(type='GeometryNodeGroup')
            select_random_node.node_tree = ensure_select_random_node_tree()
            add_scatter_layer_driver(select_random_node.inputs['Factor'], 'density')
            add_scatter_layer_driver(select_random_node.inputs['Seed'], 'density_seed')
            add_scatter_layer_driver(select_random_node.inputs['Global Seed'], 'global_seed')
            delete_geometry_node = node_tree.nodes.new(type='GeometryNodeDeleteGeometry')
            node_tree.links.new(points_socket, delete_geometry_node.inputs['Geometry'])
            node_tree.links.new(
                add_boolean_math_operation_nodes(node_tree, 'NOT', [select_random_node.outputs['Selection']]),
                delete_geometry_node.inputs['Selection']
            )
            points_socket = delete_geometry_node.outputs['Geometry']

            node_tree.links.new(points_socket, use_deviation_switch_node.inputs['False'])
            node_tree.links.new(points_socket, deviation_node.inputs['Points'])
        node_tree.links.new(deviation_node.outputs['Points'], use_deviation_switch_node.inputs['True'])

        points_socket = use_deviation_switch_node.outputs['Output']

        # Snap to Terrain Vertices
        snap_to_terrain_vertices_node = node_tree.nodes.new(type='GeometryNodeGroup')
        snap_to_terrain_vertices_node.node_tree = ensure_snap_to_terrain_vertex_node_tree()

        snap_to_terrain_vertices_node.inputs['Quad Size'].default_value = terrain_info.terrain_scale
        snap_to_terrain_vertices_node.inputs['Resolution'].default_value = terrain_info.x_size

        add_scatter_layer_driver(snap_to_terrain_vertices_node.inputs['Factor'], 'snap_to_vertex_factor')

        node_tree.links.new(points_socket, snap_to_terrain_vertices_node.inputs['Points'])
        points_socket = snap_to_terrain_vertices_node.outputs['Points']

        # Count the number of non-cap objects.
        # TODO: make sure that the cap object is always the last object in the list.
        non_cap_object_count = sum(
            1 for scatter_layer_object in scatter_layer.objects if not scatter_layer_object.is_cap)

        # Select Object Index
        select_object_index_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        select_object_index_node_group_node.node_tree = ensure_select_object_index_node_tree()
        select_object_index_node_group_node.inputs['Object Count'].default_value = non_cap_object_count

        add_scatter_layer_driver(select_object_index_node_group_node.inputs['Object Select Mode'], 'object_select_mode')
        add_scatter_layer_driver(select_object_index_node_group_node.inputs['Object Index Offset'],
                                 'object_select_cyclic_offset')
        add_scatter_layer_driver(select_object_index_node_group_node.inputs['Object Select Seed'],
                                 'object_select_random_seed')
        add_scatter_layer_driver(select_object_index_node_group_node.inputs['Global Seed'], 'global_seed')

        for i in range(non_cap_object_count):
            _add_scatter_layer_object_driver_ex(select_object_index_node_group_node.inputs['Random Weight ' + str(i)],
                                                terrain_doodad_object,
                                                'random_weight',
                                                scatter_layer_index=scatter_layer.index,
                                                scatter_layer_object_index=i)

        node_tree.links.new(points_socket, select_object_index_node_group_node.inputs['Geometry'])

        is_cap_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        is_cap_attribute_node.data_type = 'BOOLEAN'
        is_cap_attribute_node.inputs['Name'].default_value = 'is_cap'

        is_not_cap_node = node_tree.nodes.new(type='FunctionNodeBooleanMath')
        is_not_cap_node.operation = 'NOT'

        node_tree.links.new(is_cap_attribute_node.outputs['Attribute'], is_not_cap_node.inputs['Boolean'])
        node_tree.links.new(is_not_cap_node.outputs['Boolean'], select_object_index_node_group_node.inputs['Selection'])

        geometry_socket = select_object_index_node_group_node.outputs['Geometry']

        # Get the index of the cap object, if any.
        cap_object_index = None
        for scatter_layer_object_index, scatter_layer_object in enumerate(scatter_layer.objects):
            if scatter_layer_object.is_cap:
                cap_object_index = scatter_layer_object_index
                break

        if cap_object_index is not None:
            cap_store_object_index_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            cap_store_object_index_node.inputs['Name'].default_value = 'object_index'
            cap_store_object_index_node.domain = 'POINT'
            cap_store_object_index_node.data_type = 'INT'
            cap_store_object_index_node.inputs['Value'].default_value = cap_object_index

            node_tree.links.new(geometry_socket, cap_store_object_index_node.inputs['Geometry'])
            node_tree.links.new(is_cap_attribute_node.outputs['Attribute'],
                                cap_store_object_index_node.inputs['Selection'])

            geometry_socket = cap_store_object_index_node.outputs['Geometry']

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(scatter_layer.planter_object.name, items, build_function, should_force_build=True)


def ensure_scatter_layer_seed_node_tree(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer') -> NodeTree:
    terrain_doodad_object = scatter_layer.terrain_doodad_object
    terrain_info_object = scatter_layer.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object
    terrain_info = terrain_info_object.bdk.terrain_info

    items = (
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        def _add_terrain_doodad_driver(struct: bpy_struct, terrain_doodad: 'BDK_PG_terrain_doodad', data_path: str,
                                       path: str = 'default_value'):
            driver = struct.driver_add(path).driver
            driver.type = 'AVERAGE'
            var = driver.variables.new()
            var.name = data_path
            var.type = 'SINGLE_PROP'
            var.targets[0].id = terrain_doodad.object
            var.targets[0].data_path = f"bdk.terrain_doodad.{data_path}"

        def add_scatter_layer_object_driver(struct: bpy_struct, data_path: str, index: int = -1,
                                            path: str = 'default_value'):
            _add_scatter_layer_object_driver_ex(
                struct, terrain_doodad_object, data_path, index, path,
                scatter_layer_index=scatter_layer.index,
                scatter_layer_object_index=scatter_layer_object_index
            )

        def add_scatter_layer_driver(struct: bpy_struct, data_path: str, index: int = -1, path: str = 'default_value'):
            _add_scatter_layer_driver_ex(
                struct, terrain_doodad_object, data_path, index, path, scatter_layer_index=scatter_layer.index
            )

        _, output_node = ensure_input_and_output_nodes(node_tree)

        planter_object_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
        planter_object_node.transform_space = 'RELATIVE'
        planter_object_node.inputs['Object'].default_value = scatter_layer.planter_object

        terrain_info_object_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
        terrain_info_object_node.inputs['Object'].default_value = terrain_info_object

        join_geometry_node = node_tree.nodes.new(type='GeometryNodeJoinGeometry')

        for scatter_layer_object_index, scatter_layer_object in enumerate(scatter_layer.objects):
            scatter_layer_object_node_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
            scatter_layer_object_node_group_node.node_tree = ensure_scatter_layer_object_node_tree()

            scatter_layer_object_node_group_node.inputs['Object Index'].default_value = scatter_layer_object_index
            scatter_layer_object_node_group_node.inputs['Terrain Resolution'].default_value = terrain_info.x_size

            inputs = scatter_layer_object_node_group_node.inputs

            # Add drivers etc.
            add_scatter_layer_object_driver(inputs['Scale Mode'], 'scale_mode')
            add_scatter_layer_object_driver(inputs['Scale Uniform'], 'scale_uniform')
            add_scatter_layer_object_driver(inputs['Scale'], 'scale', 0)
            add_scatter_layer_object_driver(inputs['Scale'], 'scale', 1)
            add_scatter_layer_object_driver(inputs['Scale'], 'scale', 2)
            add_scatter_layer_object_driver(inputs['Scale Uniform Min'], 'scale_random_uniform_min')
            add_scatter_layer_object_driver(inputs['Scale Uniform Max'], 'scale_random_uniform_max')
            add_scatter_layer_object_driver(inputs['Scale Min'], 'scale_random_min', 0)
            add_scatter_layer_object_driver(inputs['Scale Min'], 'scale_random_min', 0)
            add_scatter_layer_object_driver(inputs['Scale Min'], 'scale_random_min', 1)
            add_scatter_layer_object_driver(inputs['Scale Min'], 'scale_random_min', 2)
            add_scatter_layer_object_driver(inputs['Scale Max'], 'scale_random_max', 0)
            add_scatter_layer_object_driver(inputs['Scale Max'], 'scale_random_max', 1)
            add_scatter_layer_object_driver(inputs['Scale Max'], 'scale_random_max', 2)
            add_scatter_layer_object_driver(inputs['Scale Seed'], 'scale_seed')
            add_scatter_layer_object_driver(inputs['Snap to Terrain'], 'snap_to_terrain')
            add_scatter_layer_object_driver(inputs['Mute'], 'mute')
            add_scatter_layer_object_driver(inputs['Global Seed'], 'global_seed')
            add_scatter_layer_object_driver(inputs['Align to Terrain Factor'], 'align_to_terrain_factor')
            add_scatter_layer_object_driver(inputs['Terrain Normal Offset Min'], 'terrain_normal_offset_min')
            add_scatter_layer_object_driver(inputs['Terrain Normal Offset Max'], 'terrain_normal_offset_max')
            add_scatter_layer_object_driver(inputs['Terrain Normal Offset Seed'], 'terrain_normal_offset_seed')
            add_scatter_layer_object_driver(inputs['Rotation Offset'], 'rotation_offset', 0)
            add_scatter_layer_object_driver(inputs['Rotation Offset'], 'rotation_offset', 1)
            add_scatter_layer_object_driver(inputs['Rotation Offset'], 'rotation_offset', 2)
            add_scatter_layer_object_driver(inputs['Rotation Offset Saturation'], 'rotation_offset_saturation')
            add_scatter_layer_object_driver(inputs['Rotation Offset Saturation Seed'],
                                            'rotation_offset_saturation_seed')
            add_scatter_layer_object_driver(inputs['Random Rotation Max'], 'random_rotation_max', 0)
            add_scatter_layer_object_driver(inputs['Random Rotation Max'], 'random_rotation_max', 1)
            add_scatter_layer_object_driver(inputs['Random Rotation Max'], 'random_rotation_max', 2)
            add_scatter_layer_object_driver(inputs['Random Rotation Seed'], 'random_rotation_max_seed')
            add_scatter_layer_object_driver(inputs['Origin Offset'], 'origin_offset', 0)
            add_scatter_layer_object_driver(inputs['Origin Offset'], 'origin_offset', 1)
            add_scatter_layer_object_driver(inputs['Origin Offset'], 'origin_offset', 2)
            add_scatter_layer_driver(inputs['Fence Mode'], 'fence_mode')

            node_tree.links.new(planter_object_node.outputs['Geometry'],
                                scatter_layer_object_node_group_node.inputs['Points'])
            node_tree.links.new(terrain_info_object_node.outputs['Geometry'],
                                scatter_layer_object_node_group_node.inputs['Terrain Geometry'])
            node_tree.links.new(scatter_layer_object_node_group_node.outputs['Points'],
                                join_geometry_node.inputs['Geometry'])
            node_tree.links.new(terrain_info_object_node.outputs['Transform'],
                                scatter_layer_object_node_group_node.inputs['Terrain Transform'])

        # Mask
        mask_node = node_tree.nodes.new(type='GeometryNodeGroup')
        mask_node.node_tree = ensure_scatter_layer_mask_node_tree()

        add_scatter_layer_driver(mask_node.inputs['Invert'], 'mask_invert')
        add_scatter_layer_driver(mask_node.inputs['Threshold'], 'mask_threshold')

        mask_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mask_switch_node.label = 'Mask Switch'
        add_scatter_layer_driver(mask_switch_node.inputs['Switch'], 'use_mask')

        mask_node.inputs['Attribute Name'].default_value = scatter_layer.mask_attribute_id

        node_tree.links.new(mask_node.outputs['Points'], mask_switch_node.inputs['True'])

        # Convert the point cloud to a mesh so that we can inspect the attributes for T3D export.
        points_to_vertices_node = node_tree.nodes.new(type='GeometryNodePointsToVertices')
        node_tree.links.new(join_geometry_node.outputs['Geometry'], points_to_vertices_node.inputs['Points'])

        # Add a mute switch.
        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'
        mute_switch_node.label = 'Mute'

        is_frozen_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        is_frozen_switch_node.input_type = 'GEOMETRY'
        is_frozen_switch_node.label = 'Is Frozen'

        # Add driver to the frozen switch node.
        _add_terrain_doodad_driver(is_frozen_switch_node.inputs['Switch'],
                                   scatter_layer.terrain_doodad_object.bdk.terrain_doodad, 'is_frozen')

        bake_node = typing_cast(GeometryNodeBake, node_tree.nodes.new(type='GeometryNodeBake'))
        bake_node.bake_items.new('GEOMETRY', 'Geometry')

        node_tree.links.new(mask_switch_node.outputs['Output'], is_frozen_switch_node.inputs['False'])
        node_tree.links.new(mask_switch_node.outputs['Output'], bake_node.inputs['Geometry'])
        node_tree.links.new(bake_node.outputs['Geometry'], is_frozen_switch_node.inputs['True'])

        node_tree.links.new(points_to_vertices_node.outputs['Mesh'], mask_switch_node.inputs['False'])
        node_tree.links.new(points_to_vertices_node.outputs['Mesh'], mask_node.inputs['Points'])
        node_tree.links.new(terrain_info_object_node.outputs['Geometry'], mask_node.inputs['Terrain Geometry'])
        node_tree.links.new(is_frozen_switch_node.outputs['Output'], mute_switch_node.inputs['False'])

        add_scatter_layer_driver(mute_switch_node.inputs['Switch'], 'mute')

        node_tree.links.new(mute_switch_node.outputs['Output'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(scatter_layer.seed_object.name, items, build_function, should_force_build=True)


def ensure_scatter_layer_modifiers(context: Context, terrain_doodad: 'BDK_PG_terrain_doodad'):
    # Add modifiers for any scatter layers that do not have a modifier and ensure the node tree.
    for scatter_layer in terrain_doodad.scatter_layers:

        # Ensure that the seed & sprout objects exist and have the correct modifiers.
        ensure_scatter_layer(scatter_layer)

        # Planter object
        planter_object = scatter_layer.planter_object
        if scatter_layer.id not in planter_object.modifiers.keys():
            modifier = planter_object.modifiers.new(name=scatter_layer.id, type='NODES')
        else:
            modifier = planter_object.modifiers[scatter_layer.id]
        # TODO: switch which node tree is used based on the fence mode.
        modifier.node_group = ensure_scatter_layer_planter_node_tree(scatter_layer)

        # Seed object
        seed_object = scatter_layer.seed_object
        if scatter_layer.id not in seed_object.modifiers.keys():
            modifier = seed_object.modifiers.new(name=scatter_layer.id, type='NODES')
        else:
            modifier = seed_object.modifiers[scatter_layer.id]
        modifier.node_group = ensure_scatter_layer_seed_node_tree(scatter_layer)

        # Sprout object
        sprout_object = scatter_layer.sprout_object
        if scatter_layer.id not in sprout_object.modifiers.keys():
            modifier = sprout_object.modifiers.new(name=scatter_layer.id, type='NODES')
        else:
            modifier = sprout_object.modifiers[scatter_layer.id]
        modifier.node_group = ensure_scatter_layer_sprout_node_tree(scatter_layer)


def ensure_round_to_interval_node_tree() -> NodeTree:
    inputs = (
        ('INPUT', 'NodeSocketFloat', 'Value'),
        ('INPUT', 'NodeSocketFloat', 'Interval'),
        ('OUTPUT', 'NodeSocketFloat', 'Value')
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        divide_node = node_tree.nodes.new(type='ShaderNodeMath')
        divide_node.label = 'Divide'
        divide_node.operation = 'DIVIDE'

        float_to_integer_node = node_tree.nodes.new(type='FunctionNodeFloatToInt')

        multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        multiply_node.label = 'Multiply'
        multiply_node.operation = 'MULTIPLY'

        node_tree.links.new(input_node.outputs['Interval'], multiply_node.inputs[1])
        node_tree.links.new(input_node.outputs['Value'], divide_node.inputs[0])
        node_tree.links.new(input_node.outputs['Interval'], divide_node.inputs[1])

        node_tree.links.new(divide_node.outputs['Value'], float_to_integer_node.inputs['Float'])
        node_tree.links.new(float_to_integer_node.outputs['Integer'], multiply_node.inputs[0])

        node_tree.links.new(multiply_node.outputs['Value'], output_node.inputs['Value'])

    return ensure_geometry_node_tree('BDK Round To Interval', inputs, build_function)


def ensure_snap_to_terrain_vertex_node_tree() -> NodeTree:
    inputs = (
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
        ('INPUT', 'NodeSocketGeometry', 'Points'),
        ('INPUT', 'NodeSocketFloat', 'Quad Size'),
        ('INPUT', 'NodeSocketInt', 'Resolution'),
        ('INPUT', 'NodeSocketFloat', 'Factor'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        terrain_size_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        terrain_size_multiply_node.operation = 'MULTIPLY'
        terrain_size_multiply_node.label = 'Terrain Size'

        terrain_half_size_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        terrain_half_size_multiply_node.operation = 'MULTIPLY'
        terrain_half_size_multiply_node.inputs[1].default_value = 0.5

        half_size_socket = terrain_half_size_multiply_node.outputs['Value']

        node_tree.links.new(separate_xyz_node.inputs['Vector'], position_node.outputs['Position'])
        node_tree.links.new(terrain_size_multiply_node.inputs[0], input_node.outputs['Quad Size'])
        node_tree.links.new(terrain_size_multiply_node.inputs[1], input_node.outputs['Resolution'])
        node_tree.links.new(terrain_half_size_multiply_node.inputs[0], terrain_size_multiply_node.outputs['Value'])

        def add_snap_value_nodes(value_socket: NodeSocket) -> NodeSocket:
            round_to_interval_node = node_tree.nodes.new(type='GeometryNodeGroup')
            round_to_interval_node.node_tree = ensure_round_to_interval_node_tree()

            subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
            subtract_node.operation = 'SUBTRACT'

            add_node = node_tree.nodes.new(type='ShaderNodeMath')
            add_node.operation = 'ADD'

            node_tree.links.new(subtract_node.inputs[0], value_socket)
            node_tree.links.new(subtract_node.inputs[1], half_size_socket)
            node_tree.links.new(round_to_interval_node.inputs['Value'], subtract_node.outputs['Value'])
            node_tree.links.new(round_to_interval_node.inputs['Interval'], input_node.outputs['Quad Size'])
            node_tree.links.new(add_node.inputs[0], round_to_interval_node.outputs['Value'])
            node_tree.links.new(add_node.inputs[1], half_size_socket)

            return add_node.outputs['Value']

        x_socket = add_snap_value_nodes(separate_xyz_node.outputs['X'])
        y_socket = add_snap_value_nodes(separate_xyz_node.outputs['Y'])

        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        node_tree.links.new(combine_xyz_node.inputs['X'], x_socket)
        node_tree.links.new(combine_xyz_node.inputs['Y'], y_socket)
        node_tree.links.new(combine_xyz_node.inputs['Z'], separate_xyz_node.outputs['Z'])

        vector_mix_node = node_tree.nodes.new(type='ShaderNodeMix')
        vector_mix_node.data_type = 'VECTOR'

        node_tree.links.new(vector_mix_node.inputs['Factor'], input_node.outputs['Factor'])
        node_tree.links.new(vector_mix_node.inputs['B'], combine_xyz_node.outputs['Vector'])
        node_tree.links.new(vector_mix_node.inputs['A'], position_node.outputs['Position'])

        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

        node_tree.links.new(set_position_node.inputs['Geometry'], input_node.outputs['Points'])
        node_tree.links.new(set_position_node.inputs['Position'], vector_mix_node.outputs['Result'])

        node_tree.links.new(set_position_node.outputs['Geometry'], output_node.inputs['Points'])

    return ensure_geometry_node_tree('BDK Snap To Terrain Vertex', inputs, build_function)


def ensure_shrinkwrap_curve_to_terrain_node_tree() -> NodeTree:
    """
    Creates a node tree that will shrinkwrap a curve to the terrain geometry.
    """
    inputs = (
        ('OUTPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketGeometry', 'Terrain Geometry'),
        ('INPUT', 'NodeSocketMatrix', 'Terrain Transform'),
        ('INPUT', 'NodeSocketInt', 'Terrain Resolution'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        terrain_sample_node = add_group_node(node_tree, ensure_bdk_terrain_sample_node_tree)

        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')
        curve_to_points_node = node_tree.nodes.new(type='GeometryNodeCurveToPoints')
        curve_to_points_node.mode = 'EVALUATED'
        points_to_curves_node = node_tree.nodes.new(type='GeometryNodePointsToCurves')

        domain_size_node = node_tree.nodes.new(type='GeometryNodeAttributeDomainSize')
        domain_size_node.component = 'CURVE'

        repeat_input_node, repeat_output_node = add_repeat_zone_nodes(node_tree, (('INT', 'Spline Index'),))

        separate_geometry_node = node_tree.nodes.new(type='GeometryNodeSeparateGeometry')
        separate_geometry_node.domain = 'CURVE'

        spline_index_compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        spline_index_compare_node.data_type = 'INT'
        spline_index_compare_node.operation = 'EQUAL'

        spline_index_node = node_tree.nodes.new(type='GeometryNodeInputIndex')

        join_geometry_node = node_tree.nodes.new(type='GeometryNodeJoinGeometry')

        increment_spline_index_node = node_tree.nodes.new(type='ShaderNodeMath')
        increment_spline_index_node.operation = 'ADD'
        increment_spline_index_node.inputs[1].default_value = 1

        # Input
        node_tree.links.new(input_node.outputs['Curve'], separate_geometry_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Curve'], domain_size_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Terrain Geometry'], terrain_sample_node.inputs['Terrain Geometry'])
        node_tree.links.new(input_node.outputs['Terrain Transform'], terrain_sample_node.inputs['Terrain Transform'])
        node_tree.links.new(input_node.outputs['Terrain Resolution'], terrain_sample_node.inputs['Terrain Resolution'])

        # Internal
        node_tree.links.new(add_position_input_node(node_tree), terrain_sample_node.inputs['Position'])
        node_tree.links.new(separate_geometry_node.outputs['Selection'], curve_to_points_node.inputs['Curve'])
        node_tree.links.new(curve_to_points_node.outputs['Points'], set_position_node.inputs['Geometry'])
        node_tree.links.new(terrain_sample_node.outputs['Position'], set_position_node.inputs['Position'])
        node_tree.links.new(set_position_node.outputs['Geometry'], points_to_curves_node.inputs['Points'])
        node_tree.links.new(repeat_input_node.outputs['Spline Index'], increment_spline_index_node.inputs[0])
        node_tree.links.new(increment_spline_index_node.outputs['Value'], repeat_output_node.inputs['Spline Index'])
        node_tree.links.new(repeat_input_node.outputs['Geometry'], join_geometry_node.inputs['Geometry'])
        node_tree.links.new(points_to_curves_node.outputs['Curves'], join_geometry_node.inputs['Geometry'])
        node_tree.links.new(join_geometry_node.outputs['Geometry'], repeat_output_node.inputs['Geometry'])
        node_tree.links.new(repeat_input_node.outputs['Spline Index'], spline_index_compare_node.inputs['A'])
        node_tree.links.new(spline_index_node.outputs['Index'], spline_index_compare_node.inputs['B'])
        node_tree.links.new(spline_index_compare_node.outputs['Result'], separate_geometry_node.inputs['Selection'])
        node_tree.links.new(domain_size_node.outputs['Spline Count'], repeat_input_node.inputs['Iterations'])

        # Output
        node_tree.links.new(repeat_output_node.outputs['Geometry'], output_node.inputs['Curve'])

    return ensure_geometry_node_tree('BDK Shrinkwrap Curve To Terrain', inputs, build_function)


def ensure_scatter_layer_mask_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Points'),
        ('INPUT', 'NodeSocketGeometry', 'Terrain Geometry'),
        ('INPUT', 'NodeSocketString', 'Attribute Name'),
        ('INPUT', 'NodeSocketFloat', 'Threshold'),
        ('INPUT', 'NodeSocketBool', 'Invert'),
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        terrain_sample_node = add_group_node(node_tree, ensure_bdk_terrain_sample_node_tree)

        delete_geometry_node = node_tree.nodes.new(type='GeometryNodeDeleteGeometry')

        sample_index_node = node_tree.nodes.new(type='GeometryNodeSampleIndex')
        sample_index_node.data_type = 'FLOAT'
        sample_index_node.domain = 'POINT'

        named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')

        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.operation = 'GREATER_EQUAL'

        invert_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        invert_switch_node.input_type = 'BOOLEAN'

        boolean_not_node = node_tree.nodes.new(type='FunctionNodeBooleanMath')
        boolean_not_node.operation = 'NOT'

        # Input
        node_tree.links.new(input_node.outputs['Points'], delete_geometry_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Terrain Geometry'], terrain_sample_node.inputs['Terrain Geometry'])
        node_tree.links.new(input_node.outputs['Terrain Geometry'], sample_index_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Threshold'], compare_node.inputs['B'])
        node_tree.links.new(input_node.outputs['Invert'], invert_switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Attribute Name'], named_attribute_node.inputs['Name'])

        # Internal
        node_tree.links.new(add_position_input_node(node_tree), terrain_sample_node.inputs['Position'])
        node_tree.links.new(terrain_sample_node.outputs['Vertex Index'], sample_index_node.inputs['Index'])
        node_tree.links.new(named_attribute_node.outputs['Attribute'], sample_index_node.inputs['Value'])
        node_tree.links.new(sample_index_node.outputs['Value'], compare_node.inputs['A'])
        node_tree.links.new(compare_node.outputs['Result'], boolean_not_node.inputs['Boolean'])
        node_tree.links.new(compare_node.outputs['Result'], invert_switch_node.inputs['False'])
        node_tree.links.new(invert_switch_node.outputs['Output'], delete_geometry_node.inputs['Selection'])
        node_tree.links.new(boolean_not_node.outputs['Boolean'], invert_switch_node.inputs['True'])

        # Output
        node_tree.links.new(delete_geometry_node.outputs['Geometry'], output_node.inputs['Points'])

    return ensure_geometry_node_tree('BDK Scatter Layer Mask', items, build_function)
