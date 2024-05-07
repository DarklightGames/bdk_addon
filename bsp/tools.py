from bpy.types import NodeTree

from ..node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, add_vector_math_operation_nodes, \
    add_math_operation_nodes

ORIGIN_ATTRIBUTE_NAME = 'bdk.origin'
TEXTURE_U_ATTRIBUTE_NAME = 'bdk.texture_u'
TEXTURE_V_ATTRIBUTE_NAME = 'bdk.texture_v'
LIGHT_MAP_SCALE_ATTRIBUTE_NAME = 'bdk.light_map_scale'


def ensure_bdk_bsp_surface_info_node_tree() -> NodeTree:

    items = {
        ('OUTPUT', 'NodeSocketVector', 'U'),
        ('OUTPUT', 'NodeSocketVector', 'V'),
        ('OUTPUT', 'NodeSocketVector', 'Origin'),
        ('OUTPUT', 'NodeSocketFloat', 'Light Map Scale')
    }

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
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketFloat', 'U'),
        ('INPUT', 'NodeSocketFloat', 'V'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

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
    inputs = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketFloat', 'Angle'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

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

    return ensure_geometry_node_tree('BDK BSP Surface Rotate', inputs, build_function)


def ensure_bdk_bsp_surface_align_node_tree() -> NodeTree:
    # 1. Move the face geometry to the origin of the world (put it in the XY plane [assuming it's flat])\
    return None


def ensure_bdk_bsp_tool_node_trees():
    ensure_bdk_bsp_surface_info_node_tree()
    ensure_bdk_bsp_surface_pan_node_tree()
    ensure_bdk_bsp_surface_rotate_node_tree()
    ensure_bdk_bsp_surface_align_node_tree()
