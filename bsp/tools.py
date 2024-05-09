from typing import Callable, List

import bpy
from bpy.types import NodeTree

from ..node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, add_vector_math_operation_nodes, \
    add_math_operation_nodes

ORIGIN_ATTRIBUTE_NAME = 'bdk.origin'
TEXTURE_U_ATTRIBUTE_NAME = 'bdk.texture_u'
TEXTURE_V_ATTRIBUTE_NAME = 'bdk.texture_v'
LIGHT_MAP_SCALE_ATTRIBUTE_NAME = 'bdk.light_map_scale'


def ensure_bdk_bsp_surface_info_node_tree() -> NodeTree:

    items = (
        ('OUTPUT', 'NodeSocketVector', 'U'),
        ('OUTPUT', 'NodeSocketVector', 'V'),
        ('OUTPUT', 'NodeSocketVector', 'Origin'),
        ('OUTPUT', 'NodeSocketFloat', 'Light Map Scale'),
    )

    def build_function(node_tree: NodeTree):
        _, output_node = ensure_input_and_output_nodes(node_tree)

        texture_u_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        texture_u_attribute_node.inputs['Name'].default_value = TEXTURE_U_ATTRIBUTE_NAME
        texture_u_attribute_node.data_type = 'FLOAT_VECTOR'

        texture_v_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        texture_v_attribute_node.inputs['Name'].default_value = TEXTURE_V_ATTRIBUTE_NAME
        texture_v_attribute_node.data_type = 'FLOAT_VECTOR'

        origin_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        origin_attribute_node.inputs['Name'].default_value = ORIGIN_ATTRIBUTE_NAME
        origin_attribute_node.data_type = 'FLOAT_VECTOR'

        light_map_scale_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        light_map_scale_attribute_node.inputs['Name'].default_value = LIGHT_MAP_SCALE_ATTRIBUTE_NAME

        node_tree.links.new(texture_u_attribute_node.outputs['Attribute'], output_node.inputs['U'])
        node_tree.links.new(texture_v_attribute_node.outputs['Attribute'], output_node.inputs['V'])
        node_tree.links.new(origin_attribute_node.outputs['Attribute'], output_node.inputs['Origin'])
        node_tree.links.new(light_map_scale_attribute_node.outputs['Attribute'], output_node.inputs['Light Map Scale'])

    return ensure_geometry_node_tree('BDK BSP Surface Info', items, build_function)


def make_tool_node_tree(node_tree: NodeTree):
    node_tree.is_modifier = False
    node_tree.is_tool = True
    node_tree.is_mode_object = False
    node_tree.is_mode_edit = True
    node_tree.is_mode_sculpt = False
    node_tree.is_type_mesh = True
    node_tree.use_fake_user = True


def ensure_bdk_bsp_surface_pan_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketFloat', 'U'),
        ('INPUT', 'NodeSocketFloat', 'V'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        make_tool_node_tree(node_tree)

        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        store_origin_attribute = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
        store_origin_attribute.inputs['Name'].default_value = ORIGIN_ATTRIBUTE_NAME
        store_origin_attribute.data_type = 'FLOAT_VECTOR'
        store_origin_attribute.domain = 'FACE'

        bsp_face_info_node_group = node_tree.nodes.new('GeometryNodeGroup')
        bsp_face_info_node_group.node_tree = ensure_bdk_bsp_surface_info_node_tree()

        selection_node = node_tree.nodes.new('GeometryNodeToolSelection')

        origin_socket = add_vector_math_operation_nodes(node_tree, 'ADD', [
            bsp_face_info_node_group.outputs['Origin'],
            add_vector_math_operation_nodes(node_tree, 'ADD', [
                add_vector_math_operation_nodes(node_tree, 'SCALE', {
                    'Vector': add_vector_math_operation_nodes(node_tree, 'NORMALIZE', [bsp_face_info_node_group.outputs['U']]),
                    'Scale': input_node.outputs['U']
                }),
                add_vector_math_operation_nodes(node_tree, 'SCALE',{
                    'Vector': add_vector_math_operation_nodes(node_tree, 'NORMALIZE', [bsp_face_info_node_group.outputs['V']]),
                    'Scale': add_math_operation_nodes(node_tree, 'MULTIPLY', [input_node.outputs['V'], -1.0])
                })
            ])
        ])

        # Internal
        node_tree.links.new(input_node.outputs['Geometry'], store_origin_attribute.inputs['Geometry'])

        # Internal
        node_tree.links.new(origin_socket, store_origin_attribute.inputs['Value'])
        node_tree.links.new(selection_node.outputs['Selection'], store_origin_attribute.inputs['Selection'])

        # Output
        node_tree.links.new(store_origin_attribute.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK BSP Surface Pan', items, build_function)


def ensure_bdk_bsp_surface_rotate_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketFloat', 'Angle'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        make_tool_node_tree(node_tree)

        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        store_texture_u_attribute = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
        store_texture_u_attribute.data_type = 'FLOAT_VECTOR'
        store_texture_u_attribute.domain = 'FACE'
        store_texture_u_attribute.inputs['Name'].default_value = TEXTURE_U_ATTRIBUTE_NAME

        store_texture_v_attribute = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
        store_texture_v_attribute.data_type = 'FLOAT_VECTOR'
        store_texture_v_attribute.domain = 'FACE'
        store_texture_v_attribute.inputs['Name'].default_value = TEXTURE_V_ATTRIBUTE_NAME

        bsp_brush_surface_info_node = node_tree.nodes.new('GeometryNodeGroup')
        bsp_brush_surface_info_node.node_tree = ensure_bdk_bsp_surface_info_node_tree()
        selection_node = node_tree.nodes.new('GeometryNodeToolSelection')
        normal_node = node_tree.nodes.new('GeometryNodeInputNormal')
        axis_angle_to_rotation_node = node_tree.nodes.new('FunctionNodeAxisAngleToRotation')
        rotate_vector_u_node = node_tree.nodes.new('FunctionNodeRotateVector')
        rotate_vector_v_node = node_tree.nodes.new('FunctionNodeRotateVector')

        node_tree.links.new(normal_node.outputs['Normal'], axis_angle_to_rotation_node.inputs['Axis'])
        node_tree.links.new(input_node.outputs['Angle'], axis_angle_to_rotation_node.inputs['Angle'])
        node_tree.links.new(bsp_brush_surface_info_node.outputs['U'], rotate_vector_u_node.inputs['Vector'])
        node_tree.links.new(bsp_brush_surface_info_node.outputs['V'], rotate_vector_v_node.inputs['Vector'])
        node_tree.links.new(axis_angle_to_rotation_node.outputs['Rotation'], rotate_vector_u_node.inputs['Rotation'])
        node_tree.links.new(axis_angle_to_rotation_node.outputs['Rotation'], rotate_vector_v_node.inputs['Rotation'])
        node_tree.links.new(rotate_vector_u_node.outputs['Vector'], store_texture_u_attribute.inputs['Value'])
        node_tree.links.new(rotate_vector_v_node.outputs['Vector'], store_texture_v_attribute.inputs['Value'])
        node_tree.links.new(input_node.outputs['Geometry'], store_texture_u_attribute.inputs['Geometry'])
        node_tree.links.new(store_texture_u_attribute.outputs['Geometry'], store_texture_v_attribute.inputs['Geometry'])
        node_tree.links.new(store_texture_v_attribute.outputs['Geometry'], output_node.inputs['Geometry'])
        node_tree.links.new(selection_node.outputs['Selection'], store_texture_u_attribute.inputs['Selection'])
        node_tree.links.new(selection_node.outputs['Selection'], store_texture_v_attribute.inputs['Selection'])

    return ensure_geometry_node_tree('BDK BSP Surface Rotate', items, build_function)


def ensure_bdk_bsp_set_scale_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketFloat', 'Scale'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        make_tool_node_tree(node_tree)

        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'FLOAT_VECTOR'
        store_named_attribute_node.domain = 'FACE'
        store_named_attribute_node.inputs["Selection"].default_value = True
        store_named_attribute_node.inputs["Name"].default_value = 'bdk.texture_u'

    return ensure_geometry_node_tree('BDK BSP Surface Set Scale', items, build_function)


def ensure_bdk_bsp_surface_scale_uniform() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        make_tool_node_tree(node_tree)
        pass

    return ensure_geometry_node_tree('BDK BSP Surface Scale Uniform', items, build_function)


def ensure_matching_brush_face_selection_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInt', 'Face Index'),
        ('OUTPUT', 'NodeSocketBool', 'Selection'),
    )

    def build_function(node_tree: NodeTree):
        group_input_node = node_tree.nodes.new(type='NodeGroupInput')

        group_output_node = node_tree.nodes.new(type='NodeGroupOutput')

        named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        named_attribute_node.data_type = 'INT'
        named_attribute_node.inputs['Name'].default_value = 'bdk.brush_index'

        named_attribute_node_1 = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        named_attribute_node_1.data_type = 'INT'
        named_attribute_node_1.inputs['Name'].default_value = 'bdk.brush_polygon_index'

        evaluate_at_index_node = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_at_index_node.domain = 'FACE'
        evaluate_at_index_node.data_type = 'INT'

        evaluate_at_index_node_1 = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_at_index_node_1.domain = 'FACE'
        evaluate_at_index_node_1.data_type = 'INT'

        index_node = node_tree.nodes.new(type='GeometryNodeInputIndex')

        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'

        evaluate_at_index_node_2 = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_at_index_node_2.domain = 'FACE'
        evaluate_at_index_node_2.data_type = 'INT'

        evaluate_at_index_node_3 = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_at_index_node_3.data_type = 'INT'

        compare_node_1 = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node_1.data_type = 'INT'
        compare_node_1.operation = 'EQUAL'

        index_node_1 = node_tree.nodes.new(type='GeometryNodeInputIndex')

        boolean_math_node = node_tree.nodes.new(type='FunctionNodeBooleanMath')

        index_node_2 = node_tree.nodes.new(type='GeometryNodeInputIndex')

        compare_node_2 = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node_2.data_type = 'INT'
        compare_node_2.operation = 'EQUAL'

        boolean_math_node_1 = node_tree.nodes.new(type='FunctionNodeBooleanMath')
        boolean_math_node_1.operation = 'OR'

        boolean_math_node_2 = node_tree.nodes.new(type='FunctionNodeBooleanMath')

        boolean_math_node_3 = node_tree.nodes.new(type='FunctionNodeBooleanMath')

        # Internal Links
        node_tree.links.new(group_input_node.outputs['Socket_1'],
                            evaluate_at_index_node.inputs['Index'])  # Face Index -> Index
        node_tree.links.new(index_node.outputs['Index'], evaluate_at_index_node_1.inputs['Index'])  # Index -> Index
        node_tree.links.new(named_attribute_node_1.outputs['Exists'],
                            boolean_math_node_2.inputs['Boolean_001'])  # Exists -> Boolean
        node_tree.links.new(named_attribute_node_1.outputs['Attribute'],
                            evaluate_at_index_node_2.inputs['Value'])  # Attribute -> Value
        node_tree.links.new(group_input_node.outputs['Socket_1'],
                            evaluate_at_index_node_2.inputs['Index'])  # Face Index -> Index
        node_tree.links.new(named_attribute_node.outputs['Attribute'],
                            evaluate_at_index_node.inputs['Value'])  # Attribute -> Value
        node_tree.links.new(group_input_node.outputs['Socket_1'], compare_node_2.inputs['B'])  # Face Index -> B
        node_tree.links.new(named_attribute_node_1.outputs['Attribute'],
                            evaluate_at_index_node_3.inputs['Value'])  # Attribute -> Value
        node_tree.links.new(boolean_math_node_1.outputs['Boolean'],
                            group_output_node.inputs['Socket_2'])  # Boolean -> Selection
        node_tree.links.new(evaluate_at_index_node_1.outputs['Value'], compare_node.inputs['A'])  # Value -> A
        node_tree.links.new(index_node_1.outputs['Index'], evaluate_at_index_node_3.inputs['Index'])  # Index -> Index
        node_tree.links.new(compare_node_1.outputs['Result'],
                            boolean_math_node_2.inputs['Boolean'])  # Result -> Boolean
        node_tree.links.new(evaluate_at_index_node.outputs['Value'], compare_node.inputs['B'])  # Value -> B
        node_tree.links.new(boolean_math_node.outputs['Boolean'],
                            boolean_math_node_1.inputs['Boolean_001'])  # Boolean -> Boolean
        node_tree.links.new(named_attribute_node.outputs['Exists'],
                            boolean_math_node_3.inputs['Boolean_001'])  # Exists -> Boolean
        node_tree.links.new(index_node_2.outputs['Index'], compare_node_2.inputs['A'])  # Index -> A
        node_tree.links.new(evaluate_at_index_node_3.outputs['Value'], compare_node_1.inputs['A'])  # Value -> A
        node_tree.links.new(named_attribute_node.outputs['Attribute'],
                            evaluate_at_index_node_1.inputs['Value'])  # Attribute -> Value
        node_tree.links.new(compare_node.outputs['Result'], boolean_math_node_3.inputs['Boolean'])  # Result -> Boolean
        node_tree.links.new(boolean_math_node_2.outputs['Boolean'],
                            boolean_math_node.inputs['Boolean_001'])  # Boolean -> Boolean
        node_tree.links.new(boolean_math_node_3.outputs['Boolean'],
                            boolean_math_node.inputs['Boolean'])  # Boolean -> Boolean
        node_tree.links.new(evaluate_at_index_node_2.outputs['Value'], compare_node_1.inputs['B'])  # Value -> B
        node_tree.links.new(compare_node_2.outputs['Result'],
                            boolean_math_node_1.inputs['Boolean'])  # Result -> Boolean

    return ensure_geometry_node_tree('BDK Brush Surface Matching Brush Polygon Selection', items, build_function)


def duplicate_active_face_node_tree() -> NodeTree:

    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        duplicate_elements_node = node_tree.nodes.new(type='GeometryNodeDuplicateElements')
        duplicate_elements_node.domain = 'FACE'
        duplicate_elements_node.inputs['Amount'].default_value = 1

        index_node = node_tree.nodes.new(type='GeometryNodeInputIndex')

        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'

        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = 'MODULO'

        domain_size_node = node_tree.nodes.new(type='GeometryNodeAttributeDomainSize')

        active_element_node = node_tree.nodes.new(type='GeometryNodeToolActiveElement')
        active_element_node.domain = 'FACE'

        # Internal Links
        node_tree.links.new(active_element_node.outputs['Index'], math_node.inputs[0])
        node_tree.links.new(domain_size_node.outputs['Face Count'], math_node.inputs[1])
        node_tree.links.new(input_node.outputs['Geometry'], domain_size_node.inputs['Geometry'])
        node_tree.links.new(math_node.outputs['Value'], compare_node.inputs['B'])
        node_tree.links.new(compare_node.outputs['Result'], duplicate_elements_node.inputs['Selection'])
        node_tree.links.new(index_node.outputs['Index'], compare_node.inputs['A'])
        node_tree.links.new(input_node.outputs['Geometry'], duplicate_elements_node.inputs['Geometry'])

        # Outgoing Links
        node_tree.links.new(duplicate_elements_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Duplicate Active Face', items, build_function)


def move_edge_to_origin_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Edge Index'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        transform_geometry_node = node_tree.nodes.new(type='GeometryNodeTransform')

        sample_index_node = node_tree.nodes.new(type='GeometryNodeSampleIndex')
        sample_index_node.data_type = 'FLOAT_VECTOR'

        vector_math_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node.operation = 'MULTIPLY'
        vector_math_node.inputs[1].default_value = (-1.0, -1.0, -1.0)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

        # Internal Links
        node_tree.links.new(sample_index_node.outputs['Value'], vector_math_node.inputs['Vector'])  # Value -> Vector
        node_tree.links.new(vector_math_node.outputs['Vector'],
                            transform_geometry_node.inputs['Translation'])  # Vector -> Translation
        node_tree.links.new(position_node.outputs['Position'], sample_index_node.inputs['Value'])  # Position -> Value

        # Incoming Links
        node_tree.links.new(input_node.outputs['Geometry'], transform_geometry_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Geometry'], sample_index_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Edge Index'], sample_index_node.inputs['Index'])

        # Outgoing Links
        node_tree.links.new(transform_geometry_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Move Edge To Origin', items, build_function)


def ensure_face_edge_direction_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Edge Index'),
        ('OUTPUT', 'NodeSocketVector', 'Vector'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.inputs[1].default_value = 1.0

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

        subtract_vector_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        subtract_vector_node.operation = 'SUBTRACT'

        normalize_vector_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        normalize_vector_node.operation = 'NORMALIZE'

        sample_index_node = node_tree.nodes.new(type='GeometryNodeSampleIndex')
        sample_index_node.data_type = 'FLOAT_VECTOR'

        sample_index_node_1 = node_tree.nodes.new(type='GeometryNodeSampleIndex')
        sample_index_node_1.data_type = 'FLOAT_VECTOR'

        domain_size_node = node_tree.nodes.new(type='GeometryNodeAttributeDomainSize')

        modulo_math_node = node_tree.nodes.new(type='ShaderNodeMath')
        modulo_math_node.operation = 'MODULO'

        # Input Links
        node_tree.links.new(input_node.outputs['Geometry'], sample_index_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Edge Index'], math_node.inputs['Value'])
        node_tree.links.new(input_node.outputs['Edge Index'], sample_index_node.inputs['Index'])
        node_tree.links.new(input_node.outputs['Geometry'], sample_index_node_1.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Geometry'], domain_size_node.inputs['Geometry'])

        # Internal Links
        node_tree.links.new(subtract_vector_node.outputs['Vector'], normalize_vector_node.inputs['Vector'])
        node_tree.links.new(math_node.outputs['Value'], modulo_math_node.inputs[0])
        node_tree.links.new(position_node.outputs['Position'], sample_index_node_1.inputs['Value'])
        node_tree.links.new(modulo_math_node.outputs['Value'], sample_index_node_1.inputs['Index'])
        node_tree.links.new(domain_size_node.outputs['Edge Count'], modulo_math_node.inputs[1])
        node_tree.links.new(position_node.outputs['Position'], sample_index_node.inputs['Value'])
        node_tree.links.new(sample_index_node_1.outputs['Value'], subtract_vector_node.inputs[0])
        node_tree.links.new(sample_index_node.outputs['Value'], subtract_vector_node.inputs[1])

        # Output Links
        node_tree.links.new(normalize_vector_node.outputs['Vector'], output_node.inputs['Vector'])

    return ensure_geometry_node_tree('Face Edge Direction', items, build_function)


def align_face_to_xy_plane_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketMatrix', 'Matrix'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        normal_node = node_tree.nodes.new(type='GeometryNodeInputNormal')

        cross_product_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        cross_product_node.operation = 'CROSS_PRODUCT'

        face_edge_direction_node = node_tree.nodes.new(type='GeometryNodeGroup')
        face_edge_direction_node.node_tree = ensure_face_edge_direction_node_tree()

        transform_geometry_node = node_tree.nodes.new(type='GeometryNodeTransform')

        sample_index_node = node_tree.nodes.new(type='GeometryNodeSampleIndex')
        sample_index_node.data_type = 'FLOAT_VECTOR'
        sample_index_node.domain = 'FACE'
        sample_index_node.clamp = True

        invert_matrix_node = node_tree.nodes.new(type='FunctionNodeInvertMatrix')

        axes_to_matrix_node = node_tree.nodes.new(type='GeometryNodeGroup')
        axes_to_matrix_node.node_tree = bpy.data.node_groups['Axes to Matrix']  # TODO: load from asset?

        # Input Links
        node_tree.links.new(input_node.outputs['Geometry'], sample_index_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Geometry'], face_edge_direction_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Geometry'], transform_geometry_node.inputs['Geometry'])

        # Internal Links
        node_tree.links.new(cross_product_node.outputs['Vector'], axes_to_matrix_node.inputs['X'])  # Vector -> X
        node_tree.links.new(axes_to_matrix_node.outputs['Matrix'], invert_matrix_node.inputs['Matrix'])  # Matrix -> Matrix
        node_tree.links.new(face_edge_direction_node.outputs['Vector'], axes_to_matrix_node.inputs['Y'])  # Vector -> Y
        node_tree.links.new(invert_matrix_node.outputs['Matrix'], transform_geometry_node.inputs['Rotation'])
        node_tree.links.new(sample_index_node.outputs['Value'], cross_product_node.inputs[1])  # Value -> Vector
        node_tree.links.new(normal_node.outputs['Normal'], sample_index_node.inputs['Value'])  # Normal -> Value
        node_tree.links.new(sample_index_node.outputs['Value'], axes_to_matrix_node.inputs['Z'])
        node_tree.links.new(face_edge_direction_node.outputs['Vector'], cross_product_node.inputs[0])

        # Outgoing Links
        node_tree.links.new(transform_geometry_node.outputs['Geometry'], output_node.inputs['Geometry'])
        node_tree.links.new(invert_matrix_node.outputs['Matrix'], output_node.inputs['Matrix'])

    return ensure_geometry_node_tree('Align Face to XY Plane', items, build_function)


def ensure_bdk_bsp_surface_align_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        make_tool_node_tree(node_tree)
        pass

    return ensure_geometry_node_tree('BDK BSP Surface Scale Uniform', items, build_function)


ensure_functions: List[Callable[[], NodeTree]] = [
    ensure_bdk_bsp_surface_info_node_tree,
    ensure_bdk_bsp_surface_pan_node_tree,
    ensure_bdk_bsp_surface_rotate_node_tree,
    ensure_bdk_bsp_surface_align_node_tree,
    ensure_bdk_bsp_surface_scale_uniform,
    ensure_matching_brush_face_selection_node_tree,

    duplicate_active_face_node_tree,
    move_edge_to_origin_node_tree,
    ensure_face_edge_direction_node_tree,
    align_face_to_xy_plane_node_tree,
]


def ensure_bdk_bsp_tool_node_trees():
    for ensure_function in ensure_functions:
        ensure_function()
