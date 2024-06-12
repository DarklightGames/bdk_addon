from typing import Callable, List

import bpy
from bpy.types import NodeTree

from ..node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, add_vector_math_operation_nodes, \
    add_math_operation_nodes
from ..bsp.data import *


def ensure_bdk_bsp_surface_info_node_tree() -> NodeTree:

    items = (
        ('OUTPUT', 'NodeSocketVector', 'U'),
        ('OUTPUT', 'NodeSocketVector', 'V'),
        ('OUTPUT', 'NodeSocketVector', 'Origin'),
        ('OUTPUT', 'NodeSocketFloat', 'Light Map Scale'),
        ('OUTPUT', 'NodeSocketInt', 'Brush Index'),
        ('OUTPUT', 'NodeSocketInt', 'Brush Polygon Index'),
    )

    def build_function(node_tree: NodeTree):
        _, output_node = ensure_input_and_output_nodes(node_tree)

        attributes = (
            (TEXTURE_U_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'U'),
            (TEXTURE_V_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'V'),
            (ORIGIN_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'Origin'),
            (LIGHT_MAP_SCALE_ATTRIBUTE_NAME, 'FLOAT', 'Light Map Scale'),
            (BRUSH_INDEX_ATTRIBUTE_NAME, 'INT', 'Brush Index'),
            (BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME, 'INT', 'Brush Polygon Index'),
        )

        for (name, data_type, output_name) in attributes:
            named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
            named_attribute_node.inputs['Name'].default_value = name
            named_attribute_node.data_type = data_type

            node_tree.links.new(named_attribute_node.outputs['Attribute'], output_node.inputs[output_name])

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


def ensure_bdk_bsp_set_face_attributes_node_tree() -> NodeTree:
    items = (
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Face Index'),
        ('INPUT', 'NodeSocketVector', 'Origin'),
        ('INPUT', 'NodeSocketVector', 'U'),
        ('INPUT', 'NodeSocketVector', 'V'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'FLOAT_VECTOR'
        store_named_attribute_node.domain = 'FACE'
        store_named_attribute_node.inputs['Name'].default_value = ORIGIN_ATTRIBUTE_NAME

        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'

        index_node = node_tree.nodes.new(type='GeometryNodeInputIndex')

        store_named_attribute_node_1 = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node_1.data_type = 'FLOAT_VECTOR'
        store_named_attribute_node_1.domain = 'FACE'
        store_named_attribute_node_1.inputs['Name'].default_value = TEXTURE_U_ATTRIBUTE_NAME

        store_named_attribute_node_2 = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node_2.data_type = 'FLOAT_VECTOR'
        store_named_attribute_node_2.domain = 'FACE'
        store_named_attribute_node_2.inputs['Name'].default_value = TEXTURE_V_ATTRIBUTE_NAME

        # Input
        node_tree.links.new(input_node.outputs['V'], store_named_attribute_node_2.inputs['Value'])
        node_tree.links.new(input_node.outputs['U'], store_named_attribute_node_1.inputs['Value'])
        node_tree.links.new(input_node.outputs['Face Index'], compare_node.inputs['A'])
        node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Origin'], store_named_attribute_node.inputs['Value'])

        # Internal
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], store_named_attribute_node_1.inputs['Geometry'])
        node_tree.links.new(index_node.outputs['Index'], compare_node.inputs['B'])
        node_tree.links.new(store_named_attribute_node_1.outputs['Geometry'], store_named_attribute_node_2.inputs['Geometry'])
        node_tree.links.new(compare_node.outputs['Result'], store_named_attribute_node_2.inputs['Selection'])
        node_tree.links.new(compare_node.outputs['Result'], store_named_attribute_node.inputs['Selection'])
        node_tree.links.new(compare_node.outputs['Result'], store_named_attribute_node_1.inputs['Selection'])

        # Output
        node_tree.links.new(store_named_attribute_node_2.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK BSP Surface Set Face Attributes', items, build_function)


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
        store_named_attribute_node.inputs['Name'].default_value = TEXTURE_U_ATTRIBUTE_NAME

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


def ensure_bdk_bsp_matching_brush_face_selection_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInt', 'Face Index'),
        ('OUTPUT', 'NodeSocketBool', 'Selection'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        named_attribute_node.data_type = 'INT'
        named_attribute_node.inputs['Name'].default_value = BRUSH_INDEX_ATTRIBUTE_NAME

        named_attribute_node_1 = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        named_attribute_node_1.data_type = 'INT'
        named_attribute_node_1.inputs['Name'].default_value = BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME

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
        evaluate_at_index_node_3.domain = 'FACE'
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

        # Input
        node_tree.links.new(input_node.outputs['Face Index'], evaluate_at_index_node.inputs['Index'])  # Face Index -> Index
        node_tree.links.new(input_node.outputs['Face Index'], evaluate_at_index_node_2.inputs['Index'])  # Face Index -> Index
        node_tree.links.new(input_node.outputs['Face Index'], compare_node_2.inputs['B'])  # Face Index -> B

        # Internal
        node_tree.links.new(index_node.outputs['Index'], evaluate_at_index_node_1.inputs['Index'])  # Index -> Index
        node_tree.links.new(named_attribute_node_1.outputs['Exists'], boolean_math_node_2.inputs[1])  # Exists -> Boolean
        node_tree.links.new(named_attribute_node_1.outputs['Attribute'], evaluate_at_index_node_2.inputs['Value'])  # Attribute -> Value
        node_tree.links.new(named_attribute_node.outputs['Attribute'], evaluate_at_index_node.inputs['Value'])  # Attribute -> Value
        node_tree.links.new(named_attribute_node_1.outputs['Attribute'], evaluate_at_index_node_3.inputs['Value'])  # Attribute -> Value
        node_tree.links.new(evaluate_at_index_node_1.outputs['Value'], compare_node.inputs['A'])  # Value -> A
        node_tree.links.new(index_node_1.outputs['Index'], evaluate_at_index_node_3.inputs['Index'])  # Index -> Index
        node_tree.links.new(compare_node_1.outputs['Result'], boolean_math_node_2.inputs[0])  # Result -> Boolean
        node_tree.links.new(evaluate_at_index_node.outputs['Value'], compare_node.inputs['B'])  # Value -> B
        node_tree.links.new(boolean_math_node.outputs['Boolean'], boolean_math_node_1.inputs[1])  # Boolean -> Boolean
        node_tree.links.new(named_attribute_node.outputs['Exists'], boolean_math_node_3.inputs[1])  # Exists -> Boolean
        node_tree.links.new(index_node_2.outputs['Index'], compare_node_2.inputs['A'])  # Index -> A
        node_tree.links.new(evaluate_at_index_node_3.outputs['Value'], compare_node_1.inputs['A'])  # Value -> A
        node_tree.links.new(named_attribute_node.outputs['Attribute'], evaluate_at_index_node_1.inputs['Value'])  # Attribute -> Value
        node_tree.links.new(compare_node.outputs['Result'], boolean_math_node_3.inputs[0])  # Result -> Boolean
        node_tree.links.new(boolean_math_node_2.outputs['Boolean'], boolean_math_node.inputs[1])  # Boolean -> Boolean
        node_tree.links.new(boolean_math_node_3.outputs['Boolean'], boolean_math_node.inputs[0])  # Boolean -> Boolean
        node_tree.links.new(evaluate_at_index_node_2.outputs['Value'], compare_node_1.inputs['B'])  # Value -> B
        node_tree.links.new(compare_node_2.outputs['Result'], boolean_math_node_1.inputs[0])  # Result -> Boolean

        # Output
        node_tree.links.new(boolean_math_node_1.outputs['Boolean'], output_node.inputs['Selection'])  # Boolean -> Selection

    return ensure_geometry_node_tree('BDK Brush Surface Matching Brush Polygon Selection', items, build_function)


def ensure_bdk_duplicate_active_face_node_tree() -> NodeTree:

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


def ensure_bdk_move_edge_to_origin_node_tree() -> NodeTree:
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


def ensure_bdk_face_edge_direction_node_tree() -> NodeTree:
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


def ensure_bdk_bsp_align_face_to_xy_plane_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Edge Index'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketMatrix', 'Matrix'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        normal_node = node_tree.nodes.new(type='GeometryNodeInputNormal')

        cross_product_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        cross_product_node.operation = 'CROSS_PRODUCT'

        face_edge_direction_node = node_tree.nodes.new(type='GeometryNodeGroup')
        face_edge_direction_node.node_tree = ensure_bdk_face_edge_direction_node_tree()

        transform_geometry_node = node_tree.nodes.new(type='GeometryNodeTransform')

        sample_index_node = node_tree.nodes.new(type='GeometryNodeSampleIndex')
        sample_index_node.data_type = 'FLOAT_VECTOR'
        sample_index_node.domain = 'FACE'
        sample_index_node.clamp = True

        invert_matrix_node = node_tree.nodes.new(type='FunctionNodeInvertMatrix')

        axes_to_matrix_node = node_tree.nodes.new(type='GeometryNodeGroup')
        axes_to_matrix_node.node_tree = ensure_bdk_axes_to_matrix_node_tree()

        # Input Links
        node_tree.links.new(input_node.outputs['Geometry'], sample_index_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Geometry'], face_edge_direction_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Geometry'], transform_geometry_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Edge Index'], face_edge_direction_node.inputs['Edge Index'])

        # Internal Links
        node_tree.links.new(cross_product_node.outputs['Vector'], axes_to_matrix_node.inputs['X'])
        node_tree.links.new(axes_to_matrix_node.outputs['Matrix'], invert_matrix_node.inputs['Matrix'])
        node_tree.links.new(face_edge_direction_node.outputs['Vector'], axes_to_matrix_node.inputs['Y'])
        node_tree.links.new(invert_matrix_node.outputs['Matrix'], transform_geometry_node.inputs['Rotation'])
        node_tree.links.new(sample_index_node.outputs['Value'], cross_product_node.inputs[1])
        node_tree.links.new(normal_node.outputs['Normal'], sample_index_node.inputs['Value'])
        node_tree.links.new(sample_index_node.outputs['Value'], axes_to_matrix_node.inputs['Z'])
        node_tree.links.new(face_edge_direction_node.outputs['Vector'], cross_product_node.inputs[0])

        # Outgoing Links
        node_tree.links.new(transform_geometry_node.outputs['Geometry'], output_node.inputs['Geometry'])
        node_tree.links.new(invert_matrix_node.outputs['Matrix'], output_node.inputs['Matrix'])

    return ensure_geometry_node_tree('BDK BSP Align Face to XY Plane', items, build_function)


def ensure_bdk_bsp_align_to_edge_tool_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketMenu', 'Horizontal'),
        ('INPUT', 'NodeSocketMenu', 'Vertical'),
        ('INPUT', 'NodeSocketInt', 'Edge Index'),
        ('INPUT', 'NodeSocketMenu', 'Fit Mode'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        make_tool_node_tree(node_tree)

        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        multiply_matrices_node = node_tree.nodes.new(type='FunctionNodeMatrixMultiply')

        invert_matrix_node = node_tree.nodes.new(type='FunctionNodeInvertMatrix')

        copy_face_info_to_matching_brush_polygons_node = node_tree.nodes.new(type='GeometryNodeGroup')
        copy_face_info_to_matching_brush_polygons_node.node_tree = ensure_bdk_bsp_copy_face_info_to_matching_brush_polygon_node_tree()

        duplicate_active_face_node = node_tree.nodes.new(type='GeometryNodeGroup')
        duplicate_active_face_node.node_tree = ensure_bdk_duplicate_active_face_node_tree()

        domain_size_node = node_tree.nodes.new(type='GeometryNodeAttributeDomainSize')

        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = 'MODULO'

        move_edge_to_origin_node = node_tree.nodes.new(type='GeometryNodeGroup')
        move_edge_to_origin_node.node_tree = ensure_bdk_move_edge_to_origin_node_tree()

        reroute_node = node_tree.nodes.new(type='NodeReroute')

        surface_alignment_translation_matrix_node = node_tree.nodes.new(type='GeometryNodeGroup')
        surface_alignment_translation_matrix_node.node_tree = ensure_bdk_bsp_surface_alignment_translation_matrix_node_tree()

        transform_to_texture_plane_node = node_tree.nodes.new(type='GeometryNodeGroup')
        transform_to_texture_plane_node.node_tree = ensure_bdk_bsp_transform_to_plane_node_tree()

        active_element_node = node_tree.nodes.new(type='GeometryNodeToolActiveElement')
        active_element_node.domain = 'FACE'

        set_face_attributes_node = node_tree.nodes.new(type='GeometryNodeGroup')
        set_face_attributes_node.node_tree = ensure_bdk_bsp_set_face_attributes_node_tree()

        scale_uv_and_offset_node = node_tree.nodes.new(type='GeometryNodeGroup')
        scale_uv_and_offset_node.node_tree = ensure_bdk_bsp_surface_scale_uv_and_offset_node_tree()

        align_face_to_xy_plane_node = node_tree.nodes.new(type='GeometryNodeGroup')
        align_face_to_xy_plane_node.node_tree = ensure_bdk_bsp_align_face_to_xy_plane_node_tree()

        object_self_node = node_tree.nodes.new('GeometryNodeSelfObject')

        # Input
        node_tree.links.new(input_node.outputs['Horizontal'], surface_alignment_translation_matrix_node.inputs['Horizontal'])
        node_tree.links.new(input_node.outputs['Vertical'], surface_alignment_translation_matrix_node.inputs['Vertical'])
        node_tree.links.new(input_node.outputs['Geometry'], duplicate_active_face_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Geometry'], scale_uv_and_offset_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Edge Index'], math_node.inputs['Value'])
        node_tree.links.new(input_node.outputs['Geometry'], set_face_attributes_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Fit Mode'], scale_uv_and_offset_node.inputs['Fit'])

        # Internal
        node_tree.links.new(object_self_node.outputs['Self Object'], scale_uv_and_offset_node.inputs['Object'])
        node_tree.links.new(duplicate_active_face_node.outputs['Geometry'], domain_size_node.inputs['Geometry'])
        node_tree.links.new(align_face_to_xy_plane_node.outputs['Geometry'], surface_alignment_translation_matrix_node.inputs['Geometry'])
        node_tree.links.new(math_node.outputs['Value'], move_edge_to_origin_node.inputs['Edge Index'])
        node_tree.links.new(transform_to_texture_plane_node.outputs['Location'], scale_uv_and_offset_node.inputs['Location'])
        node_tree.links.new(invert_matrix_node.outputs['Matrix'], transform_to_texture_plane_node.inputs['Matrix'])
        node_tree.links.new(domain_size_node.outputs['Edge Count'], math_node.inputs[1])
        node_tree.links.new(reroute_node.outputs['Output'], align_face_to_xy_plane_node.inputs['Edge Index'])
        node_tree.links.new(active_element_node.outputs['Index'], set_face_attributes_node.inputs['Face Index'])
        node_tree.links.new(multiply_matrices_node.outputs['Matrix'], invert_matrix_node.inputs['Matrix'])
        node_tree.links.new(scale_uv_and_offset_node.outputs['Location'], set_face_attributes_node.inputs['Origin'])
        node_tree.links.new(transform_to_texture_plane_node.outputs['U'], scale_uv_and_offset_node.inputs['U'])
        node_tree.links.new(scale_uv_and_offset_node.outputs['V'], set_face_attributes_node.inputs['V'])
        node_tree.links.new(scale_uv_and_offset_node.outputs['U'], set_face_attributes_node.inputs['U'])
        node_tree.links.new(align_face_to_xy_plane_node.outputs['Matrix'], multiply_matrices_node.inputs[1])
        node_tree.links.new(math_node.outputs['Value'], reroute_node.inputs['Input'])
        node_tree.links.new(transform_to_texture_plane_node.outputs['V'], scale_uv_and_offset_node.inputs['V'])
        node_tree.links.new(set_face_attributes_node.outputs['Geometry'], copy_face_info_to_matching_brush_polygons_node.inputs['Geometry'])
        node_tree.links.new(duplicate_active_face_node.outputs['Geometry'], move_edge_to_origin_node.inputs['Geometry'])
        node_tree.links.new(move_edge_to_origin_node.outputs['Geometry'], align_face_to_xy_plane_node.inputs['Geometry'])
        node_tree.links.new(active_element_node.outputs['Index'], copy_face_info_to_matching_brush_polygons_node.inputs['Face Index'])
        node_tree.links.new(reroute_node.outputs['Output'], scale_uv_and_offset_node.inputs['Edge Index'])
        node_tree.links.new(surface_alignment_translation_matrix_node.outputs['Matrix'], multiply_matrices_node.inputs[0])
        node_tree.links.new(surface_alignment_translation_matrix_node.outputs['Extents'], scale_uv_and_offset_node.inputs['Face Extents'])

        # Output
        node_tree.links.new(copy_face_info_to_matching_brush_polygons_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK BSP Surface Align To Edge', items, build_function)


def ensure_bdk_bsp_surface_sample_face_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Face Index'),
        ('OUTPUT', 'NodeSocketVector', 'Origin'),
        ('OUTPUT', 'NodeSocketVector', 'Normal'),
        ('OUTPUT', 'NodeSocketVector', 'U'),
        ('OUTPUT', 'NodeSocketVector', 'V'),
        ('OUTPUT', 'NodeSocketInt', 'Material Index'),
        ('OUTPUT', 'NodeSocketInt', 'Poly Flags'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        values = (
            (MATERIAL_INDEX_ATTRIBUTE_NAME, 'INT', 'Material Index'),
            (ORIGIN_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'Origin'),
            (NORMAL_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'Normal'),
            (TEXTURE_U_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'U'),
            (TEXTURE_V_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'V'),
            (POLY_FLAGS_ATTRIBUTE_NAME, 'INT', 'Poly Flags'),
        )

        for (name, data_type, output_name) in values:
            named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
            named_attribute_node.inputs['Name'].default_value = name
            named_attribute_node.data_type = data_type

            sample_index_node = node_tree.nodes.new('GeometryNodeSampleIndex')
            sample_index_node.data_type = data_type
            sample_index_node.domain = 'FACE'

            node_tree.links.new(input_node.outputs['Geometry'], sample_index_node.inputs['Geometry'])
            node_tree.links.new(input_node.outputs['Face Index'], sample_index_node.inputs['Index'])
            node_tree.links.new(named_attribute_node.outputs['Attribute'], sample_index_node.inputs['Value'])

            node_tree.links.new(sample_index_node.outputs['Value'], output_node.inputs[output_name])

    return ensure_geometry_node_tree('BDK BSP Surface Sample Face', items, build_function)


def ensure_bdk_bsp_surface_texture_world_scale_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Face Index'),
        ('OUTPUT', 'NodeSocketFloat', 'U'),
        ('OUTPUT', 'NodeSocketFloat', 'V'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        bdk_object_material_size_node = node_tree.nodes.new(type='GeometryNodeBDKObjectMaterialSize')

        self_object_node = node_tree.nodes.new(type='GeometryNodeSelfObject')

        vector_math_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node.operation = 'LENGTH'

        vector_math_node_1 = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node_1.operation = 'LENGTH'

        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = 'DIVIDE'

        math_node_1 = node_tree.nodes.new(type='ShaderNodeMath')
        math_node_1.operation = 'DIVIDE'

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'
        switch_node.inputs['False'].default_value = 512.0

        switch_node_1 = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node_1.input_type = 'FLOAT'
        switch_node_1.inputs['False'].default_value = 512.0

        sample_face_node = node_tree.nodes.new(type='GeometryNodeGroup')
        sample_face_node.node_tree = ensure_bdk_bsp_surface_sample_face_node_tree()

        # Internal Links
        node_tree.links.new(bdk_object_material_size_node.outputs['V'], switch_node_1.inputs['True'])
        node_tree.links.new(sample_face_node.outputs['U'], vector_math_node.inputs['Vector'])
        node_tree.links.new(switch_node_1.outputs['Output'], math_node_1.inputs[0])
        node_tree.links.new(switch_node.outputs['Output'], math_node.inputs[0])
        node_tree.links.new(vector_math_node.outputs['Value'], math_node.inputs[1])
        node_tree.links.new(self_object_node.outputs['Self Object'], bdk_object_material_size_node.inputs['Object'])
        node_tree.links.new(bdk_object_material_size_node.outputs['Exists'], switch_node_1.inputs['Switch'])
        node_tree.links.new(bdk_object_material_size_node.outputs['Exists'], switch_node.inputs['Switch'])
        node_tree.links.new(sample_face_node.outputs['V'], vector_math_node_1.inputs['Vector'])
        node_tree.links.new(vector_math_node_1.outputs['Value'], math_node_1.inputs[1])
        node_tree.links.new(bdk_object_material_size_node.outputs['U'], switch_node.inputs['True'])
        node_tree.links.new(sample_face_node.outputs['Material Index'], bdk_object_material_size_node.inputs['Material Index'])

        # Incoming Links
        node_tree.links.new(input_node.outputs['Geometry'], sample_face_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Face Index'], sample_face_node.inputs['Face Index'])

        # Outgoing Links
        node_tree.links.new(math_node.outputs['Value'], output_node.inputs['U'])
        node_tree.links.new(math_node_1.outputs['Value'], output_node.inputs['V'])

    return ensure_geometry_node_tree('BDK BSP Surface Texture World Scale', items, build_function)


def ensure_bdk_bsp_surface_alignment_translation_matrix_node_tree() -> NodeTree:
    items = (
        ('OUTPUT', 'NodeSocketMatrix', 'Matrix'),
        ('OUTPUT', 'NodeSocketVector', 'Extents'),
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketMenu', 'Horizontal', 'Left'),
        ('INPUT', 'NodeSocketMenu', 'Vertical', 'Bottom'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        horizontal_menu_switch_node = node_tree.nodes.new(type='GeometryNodeMenuSwitch')
        horizontal_menu_switch_node.data_type = 'FLOAT'
        horizontal_menu_switch_node.enum_items.clear()
        horizontal_menu_switch_node.enum_items.new('Left')
        horizontal_menu_switch_node.enum_items.new('Center')
        horizontal_menu_switch_node.enum_items.new('Right')

        vertical_menu_switch_node = node_tree.nodes.new(type='GeometryNodeMenuSwitch')
        vertical_menu_switch_node.data_type = 'FLOAT'
        vertical_menu_switch_node.enum_items.clear()
        vertical_menu_switch_node.enum_items.new('Top')
        vertical_menu_switch_node.enum_items.new('Center')
        vertical_menu_switch_node.enum_items.new('Bottom')

        node_tree.links.new(input_node.outputs['Horizontal'], horizontal_menu_switch_node.inputs[0])
        node_tree.links.new(input_node.outputs['Vertical'], vertical_menu_switch_node.inputs[0])

        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
        separate_xyz_node_1 = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')
        vector_math_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node.operation = 'SCALE'
        vector_math_node.inputs['Scale'].default_value = -1.0
        vector_math_node_1 = node_tree.nodes.new(type='ShaderNodeVectorMath')
        separate_xyz_node_2 = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
        combine_xyz_node_1 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')
        vector_math_node_2 = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node_2.operation = 'SCALE'
        vector_math_node_2.inputs['Scale'].default_value = 0.5
        vector_math_node_3 = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node_3.operation = 'SCALE'
        vector_math_node_3.inputs['Scale'].default_value = 0.5
        vector_math_node_4 = node_tree.nodes.new(type='ShaderNodeVectorMath')
        bounding_box_node = node_tree.nodes.new(type='GeometryNodeBoundBox')
        group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        group_node.node_tree = ensure_bdk_bsp_surface_texture_world_scale_node_tree()
        separate_xyz_node_3 = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
        combine_matrix_node = node_tree.nodes.new(type='FunctionNodeCombineMatrix')
        vector_math_node_5 = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node_5.operation = 'SUBTRACT'

        node_tree.links.new(bounding_box_node.outputs['Max'], vector_math_node_5.inputs[0])
        node_tree.links.new(bounding_box_node.outputs['Min'], vector_math_node_5.inputs[1])

        # Incoming Links
        node_tree.links.new(input_node.outputs['Geometry'], bounding_box_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Horizontal'], horizontal_menu_switch_node.inputs['Menu'])
        node_tree.links.new(input_node.outputs['Geometry'], group_node.inputs['Geometry'])

        # Internal Links
        node_tree.links.new(vertical_menu_switch_node.outputs['Output'], combine_xyz_node.inputs['Y'])
        node_tree.links.new(separate_xyz_node_1.outputs['Y'], vertical_menu_switch_node.inputs['Top'])
        node_tree.links.new(horizontal_menu_switch_node.outputs['Output'], combine_xyz_node.inputs['X'])
        node_tree.links.new(group_node.outputs['U'], combine_xyz_node_1.inputs['X'])
        node_tree.links.new(group_node.outputs['V'], combine_xyz_node_1.inputs['Y'])
        node_tree.links.new(separate_xyz_node.outputs['X'], horizontal_menu_switch_node.inputs['Left'])
        node_tree.links.new(separate_xyz_node_2.outputs['Y'], vertical_menu_switch_node.inputs['Center'])
        node_tree.links.new(separate_xyz_node_2.outputs['X'], horizontal_menu_switch_node.inputs['Center'])
        node_tree.links.new(separate_xyz_node_3.outputs['Z'], combine_matrix_node.inputs['Column 4 Row 3'])
        node_tree.links.new(bounding_box_node.outputs['Min'], vector_math_node_1.inputs[1])
        node_tree.links.new(vector_math_node.outputs['Vector'], separate_xyz_node_3.inputs['Vector'])
        node_tree.links.new(bounding_box_node.outputs['Max'], vector_math_node_1.inputs[0])
        node_tree.links.new(vector_math_node_3.outputs['Vector'], vector_math_node_4.inputs[1])
        node_tree.links.new(vector_math_node_1.outputs['Vector'], vector_math_node_2.inputs['Vector'])
        node_tree.links.new(separate_xyz_node_3.outputs['X'], combine_matrix_node.inputs['Column 4 Row 1'])
        node_tree.links.new(combine_xyz_node_1.outputs['Vector'], vector_math_node_3.inputs['Vector'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], vertical_menu_switch_node.inputs['Bottom'])
        node_tree.links.new(vector_math_node_4.outputs['Vector'], separate_xyz_node_2.inputs['Vector'])
        node_tree.links.new(bounding_box_node.outputs['Min'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(combine_xyz_node.outputs['Vector'], vector_math_node.inputs['Vector'])
        node_tree.links.new(input_node.outputs['Vertical'], vertical_menu_switch_node.inputs['Menu'])
        node_tree.links.new(bounding_box_node.outputs['Max'], separate_xyz_node_1.inputs['Vector'])
        node_tree.links.new(separate_xyz_node_3.outputs['Y'], combine_matrix_node.inputs['Column 4 Row 2'])
        node_tree.links.new(separate_xyz_node_1.outputs['X'], horizontal_menu_switch_node.inputs['Right'])
        node_tree.links.new(vector_math_node_2.outputs['Vector'], vector_math_node_4.inputs['Vector'])

        # Outgoing Links
        node_tree.links.new(combine_matrix_node.outputs['Matrix'], output_node.inputs['Matrix'])
        node_tree.links.new(vector_math_node_5.outputs['Vector'], output_node.inputs['Extents'])

    return ensure_geometry_node_tree('BDK BSP Surface Alignment Translation Matrix', items, build_function)


def ensure_bdk_bsp_surface_copy_face_attributes_to_selection_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Face Index'),
        ('INPUT', 'NodeSocketBool', 'Selection'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        bsp_surface_sample_face_node_group = node_tree.nodes.new('GeometryNodeGroup')
        bsp_surface_sample_face_node_group.node_tree = ensure_bdk_bsp_surface_sample_face_node_tree()

        node_tree.links.new(input_node.outputs['Geometry'], bsp_surface_sample_face_node_group.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Face Index'], bsp_surface_sample_face_node_group.inputs['Face Index'])

        attributes = (
            (ORIGIN_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'Origin'),
            (TEXTURE_U_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'U'),
            (TEXTURE_V_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'V'),
            (POLY_FLAGS_ATTRIBUTE_NAME, 'INT', 'Poly Flags'),
            (MATERIAL_INDEX_ATTRIBUTE_NAME, 'INT', 'Material Index'),
        )

        geometry_socket = input_node.outputs['Geometry']

        for (name, data_type, sample_socket_name) in attributes:
            store_named_attribute_node = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
            store_named_attribute_node.data_type = data_type
            store_named_attribute_node.domain = 'FACE'
            store_named_attribute_node.inputs['Name'].default_value = name

            node_tree.links.new(geometry_socket, store_named_attribute_node.inputs['Geometry'])
            node_tree.links.new(input_node.outputs['Selection'], store_named_attribute_node.inputs['Selection'])
            node_tree.links.new(bsp_surface_sample_face_node_group.outputs[sample_socket_name], store_named_attribute_node.inputs['Value'])

            geometry_socket = store_named_attribute_node.outputs['Geometry']

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK BSP Surface Copy Face Attributes To Selection', items, build_function)


def ensure_bdk_bsp_transform_to_plane_node_tree() -> NodeTree:
    inputs = (
        ('OUTPUT', 'NodeSocketVector', 'Location'),
        ('OUTPUT', 'NodeSocketVector', 'U'),
        ('OUTPUT', 'NodeSocketVector', 'V'),
        ('INPUT', 'NodeSocketMatrix', 'Matrix'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        separate_transform_node = node_tree.nodes.new(type='FunctionNodeSeparateTransform')

        vector_node = node_tree.nodes.new(type='FunctionNodeInputVector')
        vector_node.vector = (1.0, 0.0, 0.0)

        vector_node_1 = node_tree.nodes.new(type='FunctionNodeInputVector')
        vector_node_1.vector = (0.0, -1.0, 0.0)

        transform_direction_node = node_tree.nodes.new(type='FunctionNodeTransformDirection')

        transform_direction_node_1 = node_tree.nodes.new(type='FunctionNodeTransformDirection')

        # Incoming Links
        node_tree.links.new(input_node.outputs['Matrix'], separate_transform_node.inputs['Transform'])

        # Internal Links
        node_tree.links.new(vector_node_1.outputs['Vector'], transform_direction_node_1.inputs['Direction'])
        node_tree.links.new(separate_transform_node.outputs['Rotation'], transform_direction_node.inputs['Transform'])
        node_tree.links.new(vector_node.outputs['Vector'], transform_direction_node.inputs['Direction'])
        node_tree.links.new(separate_transform_node.outputs['Rotation'], transform_direction_node_1.inputs['Transform'])

        # Outgoing Links
        node_tree.links.new(separate_transform_node.outputs['Translation'], output_node.inputs['Location'])
        node_tree.links.new(transform_direction_node.outputs['Direction'], output_node.inputs['U'])
        node_tree.links.new(transform_direction_node_1.outputs['Direction'], output_node.inputs['V'])

    return ensure_geometry_node_tree('BDK BSP Transform To Plane', inputs, build_function)


def ensure_bdk_bsp_surface_get_uv_scale() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Face Index'),
        ('OUTPUT', 'NodeSocketFloat', 'U Scale'),
        ('OUTPUT', 'NodeSocketFloat', 'V Scale'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        bsp_surface_sample_face_node = node_tree.nodes.new('GeometryNodeGroup')
        bsp_surface_sample_face_node.node_tree = ensure_bdk_bsp_surface_sample_face_node_tree()

        vector_math_node = node_tree.nodes.new('ShaderNodeVectorMath')
        vector_math_node.operation = 'LENGTH'

        vector_math_node_1 = node_tree.nodes.new('ShaderNodeVectorMath')
        vector_math_node_1.operation = 'LENGTH'

        node_tree.links.new(input_node.outputs['Geometry'], bsp_surface_sample_face_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Face Index'], bsp_surface_sample_face_node.inputs['Face Index'])

        node_tree.links.new(bsp_surface_sample_face_node.outputs['U'], vector_math_node.inputs['Vector'])
        node_tree.links.new(bsp_surface_sample_face_node.outputs['V'], vector_math_node_1.inputs['Vector'])

        node_tree.links.new(vector_math_node.outputs['Value'], output_node.inputs['U Scale'])
        node_tree.links.new(vector_math_node_1.outputs['Value'], output_node.inputs['V Scale'])

    return ensure_geometry_node_tree('BDK BSP Surface Get UV Scale', items, build_function)


def ensure_bdk_bsp_surface_scale_uv_and_offset_node_tree() -> NodeTree:
    inputs = (
        ('OUTPUT', 'NodeSocketVector', 'Location'),
        ('OUTPUT', 'NodeSocketVector', 'U'),
        ('OUTPUT', 'NodeSocketVector', 'V'),
        ('INPUT', 'NodeSocketObject', 'Object'),
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketVector', 'U'),
        ('INPUT', 'NodeSocketVector', 'V'),
        ('INPUT', 'NodeSocketVector', 'Location'),
        ('INPUT', 'NodeSocketInt', 'Edge Index'),
        ('INPUT', 'NodeSocketMenu', 'Fit', 'Maximum'),
        ('INPUT', 'NodeSocketVector', 'Face Extents'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        u_scale_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        u_scale_node.operation = 'SCALE'

        v_scale_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        v_scale_node.operation = 'SCALE'

        vector_math_node_2 = node_tree.nodes.new(type='ShaderNodeVectorMath')

        u_length_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        u_length_node.operation = 'LENGTH'

        v_length_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        v_length_node.operation = 'LENGTH'

        sample_index_node = node_tree.nodes.new(type='GeometryNodeSampleIndex')
        sample_index_node.data_type = 'FLOAT_VECTOR'

        duplicate_active_face_node = node_tree.nodes.new(type='GeometryNodeGroup')
        duplicate_active_face_node.node_tree = ensure_bdk_duplicate_active_face_node_tree()

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

        active_element_node = node_tree.nodes.new(type='GeometryNodeToolActiveElement')
        active_element_node.domain = 'FACE'

        sample_face_node = node_tree.nodes.new(type='GeometryNodeGroup')
        sample_face_node.node_tree = ensure_bdk_bsp_surface_sample_face_node_tree()

        active_face_material_size_node = node_tree.nodes.new(type='GeometryNodeGroup')
        active_face_material_size_node.node_tree = ensure_bdk_bsp_surface_active_face_material_size_node_tree()

        vector_divide_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_divide_node.operation = 'DIVIDE'

        node_tree.links.new(active_face_material_size_node.outputs['Size'], vector_divide_node.inputs[0])
        node_tree.links.new(input_node.outputs['Face Extents'], vector_divide_node.inputs[1])

        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        math_minimum_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_minimum_node.operation = 'MINIMUM'

        math_maximum_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_maximum_node.operation = 'MAXIMUM'

        fit_mode_menu_switch_node = node_tree.nodes.new(type='GeometryNodeMenuSwitch')
        fit_mode_menu_switch_node.data_type = 'INT'
        fit_mode_menu_switch_node.enum_items.clear()
        fit_mode_menu_switch_node.enum_items.new('None')
        fit_mode_menu_switch_node.enum_items.new('Maximum')
        fit_mode_menu_switch_node.enum_items.new('Minimum')
        fit_mode_menu_switch_node.inputs['None'].default_value = -1
        fit_mode_menu_switch_node.inputs['Minimum'].default_value = 0
        fit_mode_menu_switch_node.inputs['Maximum'].default_value = 1

        min_max_index_switch_node = node_tree.nodes.new(type='GeometryNodeIndexSwitch')
        min_max_index_switch_node.data_type = 'FLOAT'

        is_fitting_compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        is_fitting_compare_node.data_type = 'INT'
        is_fitting_compare_node.operation = 'NOT_EQUAL'
        is_fitting_compare_node.inputs['B'].default_value = -1

        u_scale_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        u_scale_switch_node.input_type = 'FLOAT'

        v_scale_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        v_scale_switch_node.input_type = 'FLOAT'

        node_tree.links.new(u_length_node.outputs['Value'], u_scale_switch_node.inputs['False'])
        node_tree.links.new(v_length_node.outputs['Value'], v_scale_switch_node.inputs['False'])

        node_tree.links.new(min_max_index_switch_node.outputs['Output'], u_scale_switch_node.inputs['True'])
        node_tree.links.new(min_max_index_switch_node.outputs['Output'], v_scale_switch_node.inputs['True'])

        node_tree.links.new(fit_mode_menu_switch_node.outputs['Output'], is_fitting_compare_node.inputs['A'])

        node_tree.links.new(is_fitting_compare_node.outputs['Result'], u_scale_switch_node.inputs['Switch'])
        node_tree.links.new(is_fitting_compare_node.outputs['Result'], v_scale_switch_node.inputs['Switch'])

        node_tree.links.new(fit_mode_menu_switch_node.outputs['Output'], min_max_index_switch_node.inputs['Index'])
        node_tree.links.new(math_maximum_node.outputs['Value'], min_max_index_switch_node.inputs['0'])
        node_tree.links.new(math_minimum_node.outputs['Value'], min_max_index_switch_node.inputs['1'])

        node_tree.links.new(input_node.outputs['Fit'], fit_mode_menu_switch_node.inputs['Menu'])

        node_tree.links.new(separate_xyz_node.outputs['X'], math_minimum_node.inputs[0])
        node_tree.links.new(separate_xyz_node.outputs['Y'], math_minimum_node.inputs[1])

        node_tree.links.new(separate_xyz_node.outputs['X'], math_maximum_node.inputs[0])
        node_tree.links.new(separate_xyz_node.outputs['Y'], math_maximum_node.inputs[1])

        node_tree.links.new(vector_divide_node.outputs['Vector'], separate_xyz_node.inputs['Vector'])

        node_tree.links.new(input_node.outputs['Geometry'], active_face_material_size_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Object'], active_face_material_size_node.inputs['Object'])

        # Input
        node_tree.links.new(input_node.outputs['V'], v_scale_node.inputs['Vector'])
        node_tree.links.new(input_node.outputs['Geometry'], duplicate_active_face_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Location'], vector_math_node_2.inputs[0])
        node_tree.links.new(input_node.outputs['Geometry'], sample_face_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['U'], u_scale_node.inputs['Vector'])
        node_tree.links.new(input_node.outputs['Edge Index'], sample_index_node.inputs['Index'])

        # Internal
        node_tree.links.new(position_node.outputs['Position'], sample_index_node.inputs['Value'])
        node_tree.links.new(active_element_node.outputs['Index'], sample_face_node.inputs['Face Index'])
        node_tree.links.new(sample_face_node.outputs['U'], u_length_node.inputs['Vector'])
        node_tree.links.new(u_scale_switch_node.outputs['Output'], u_scale_node.inputs['Scale'])
        node_tree.links.new(sample_face_node.outputs['V'], v_length_node.inputs['Vector'])
        node_tree.links.new(v_scale_switch_node.outputs['Output'], v_scale_node.inputs['Scale'])
        node_tree.links.new(duplicate_active_face_node.outputs['Geometry'], sample_index_node.inputs['Geometry'])
        node_tree.links.new(sample_index_node.outputs['Value'], vector_math_node_2.inputs[1])

        # Output
        node_tree.links.new(u_scale_node.outputs['Vector'], output_node.inputs['U'])
        node_tree.links.new(v_scale_node.outputs['Vector'], output_node.inputs['V'])
        node_tree.links.new(vector_math_node_2.outputs['Vector'], output_node.inputs['Location'])

    return ensure_geometry_node_tree('BDK BSP Scale UV and Offset', inputs, build_function)


def ensure_bdk_bsp_copy_face_info_to_matching_brush_polygon_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Face Index'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        matching_brush_polygon_selection_node = node_tree.nodes.new(type='GeometryNodeGroup')
        matching_brush_polygon_selection_node.node_tree = ensure_bdk_bsp_matching_brush_face_selection_node_tree()

        copy_face_attributes_to_selection_node = node_tree.nodes.new(type='GeometryNodeGroup')
        copy_face_attributes_to_selection_node.node_tree = ensure_bdk_bsp_surface_copy_face_attributes_to_selection_node_tree()

        # Internal Links
        node_tree.links.new(input_node.outputs['Face Index'], copy_face_attributes_to_selection_node.inputs['Face Index'])  # Face Index -> Face Index
        node_tree.links.new(input_node.outputs['Geometry'], copy_face_attributes_to_selection_node.inputs['Geometry'])  # Geometry -> Geometry
        node_tree.links.new(input_node.outputs['Face Index'], matching_brush_polygon_selection_node.inputs['Face Index'])  # Face Index -> Face Index
        node_tree.links.new(matching_brush_polygon_selection_node.outputs['Selection'], copy_face_attributes_to_selection_node.inputs['Selection'])  # Selection -> Selection
        node_tree.links.new(copy_face_attributes_to_selection_node.outputs['Geometry'], output_node.inputs['Geometry'])  # Geometry -> Geometry

    return ensure_geometry_node_tree('BDK Brush Surface Copy Face Info To Matching Brush Polygons', items, build_function)


def ensure_bdk_axes_to_matrix_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'X'),
        ('INPUT', 'NodeSocketVector', 'Y'),
        ('INPUT', 'NodeSocketVector', 'Z'),
        ('OUTPUT', 'NodeSocketMatrix', 'Matrix'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        combine_matrix_node = node_tree.nodes.new(type='FunctionNodeCombineMatrix')
        separate_xyz_x_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
        separate_xyz_y_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
        separate_xyz_z_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        node_tree.links.new(input_node.outputs['X'], separate_xyz_x_node.inputs['Vector'])
        node_tree.links.new(input_node.outputs['Y'], separate_xyz_y_node.inputs['Vector'])
        node_tree.links.new(input_node.outputs['Z'], separate_xyz_z_node.inputs['Vector'])

        node_tree.links.new(separate_xyz_x_node.outputs['X'], combine_matrix_node.inputs['Column 1 Row 1'])
        node_tree.links.new(separate_xyz_x_node.outputs['Y'], combine_matrix_node.inputs['Column 1 Row 2'])
        node_tree.links.new(separate_xyz_x_node.outputs['Z'], combine_matrix_node.inputs['Column 1 Row 3'])

        node_tree.links.new(separate_xyz_y_node.outputs['X'], combine_matrix_node.inputs['Column 2 Row 1'])
        node_tree.links.new(separate_xyz_y_node.outputs['Y'], combine_matrix_node.inputs['Column 2 Row 2'])
        node_tree.links.new(separate_xyz_y_node.outputs['Z'], combine_matrix_node.inputs['Column 2 Row 3'])

        node_tree.links.new(separate_xyz_z_node.outputs['X'], combine_matrix_node.inputs['Column 3 Row 1'])
        node_tree.links.new(separate_xyz_z_node.outputs['Y'], combine_matrix_node.inputs['Column 3 Row 2'])
        node_tree.links.new(separate_xyz_z_node.outputs['Z'], combine_matrix_node.inputs['Column 3 Row 3'])

        node_tree.links.new(combine_matrix_node.outputs['Matrix'], output_node.inputs['Matrix'])

    return ensure_geometry_node_tree('BDK Axes to Matrix', items, build_function)


def ensure_bdk_bsp_surface_active_face_material_size_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketObject', 'Object'),
        ('OUTPUT', 'NodeSocketVector', 'Size'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        bdk_object_material_size_node = node_tree.nodes.new(type='GeometryNodeBDKObjectMaterialSize')

        active_element_node = node_tree.nodes.new(type='GeometryNodeToolActiveElement')
        active_element_node.domain = 'FACE'

        material_index_node = node_tree.nodes.new(type='GeometryNodeInputMaterialIndex')

        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        sample_index_node = node_tree.nodes.new(type='GeometryNodeSampleIndex')
        sample_index_node.data_type = 'INT'
        sample_index_node.domain = 'FACE'

        # Input
        node_tree.links.new(input_node.outputs['Geometry'], sample_index_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Object'], bdk_object_material_size_node.inputs['Object'])

        # Internal
        node_tree.links.new(sample_index_node.outputs['Value'], bdk_object_material_size_node.inputs['Material Index'])
        node_tree.links.new(bdk_object_material_size_node.outputs['U'], combine_xyz_node.inputs['X'])
        node_tree.links.new(bdk_object_material_size_node.outputs['V'], combine_xyz_node.inputs['Y'])
        node_tree.links.new(active_element_node.outputs['Index'], sample_index_node.inputs['Index'])
        node_tree.links.new(material_index_node.outputs['Material Index'], sample_index_node.inputs['Value'])

        # Output
        node_tree.links.new(combine_xyz_node.outputs['Vector'], output_node.inputs['Size'])

    return ensure_geometry_node_tree('BDK BSP Surface Active Face Material Size', items, build_function)


ensure_functions: List[Callable[[], NodeTree]] = [
    ensure_bdk_axes_to_matrix_node_tree,
    ensure_bdk_duplicate_active_face_node_tree,
    ensure_bdk_move_edge_to_origin_node_tree,
    ensure_bdk_face_edge_direction_node_tree,

    ensure_bdk_bsp_surface_info_node_tree,
    ensure_bdk_bsp_surface_pan_node_tree,
    ensure_bdk_bsp_surface_rotate_node_tree,
    ensure_bdk_bsp_surface_scale_uniform,
    ensure_bdk_bsp_surface_sample_face_node_tree,
    ensure_bdk_bsp_surface_texture_world_scale_node_tree,
    ensure_bdk_bsp_surface_alignment_translation_matrix_node_tree,
    ensure_bdk_bsp_transform_to_plane_node_tree,
    ensure_bdk_bsp_surface_copy_face_attributes_to_selection_node_tree,
    ensure_bdk_bsp_set_face_attributes_node_tree,
    ensure_bdk_bsp_surface_get_uv_scale,
    ensure_bdk_bsp_surface_scale_uv_and_offset_node_tree,
    ensure_bdk_bsp_align_to_edge_tool_node_tree,
    ensure_bdk_bsp_copy_face_info_to_matching_brush_polygon_node_tree,
    ensure_bdk_bsp_matching_brush_face_selection_node_tree,
    ensure_bdk_bsp_align_face_to_xy_plane_node_tree,
    ensure_bdk_bsp_surface_active_face_material_size_node_tree,
]


def ensure_bdk_bsp_tool_node_trees():
    for ensure_function in ensure_functions:
        ensure_function()
