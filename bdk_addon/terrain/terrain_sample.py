from bpy.types import NodeTree, NodeSocket

from ..node_helpers import add_combine_xyz_node, add_comparison_nodes, add_float_to_integer_node, add_integer_math_operation_nodes, add_separate_xyz_node, ensure_geometry_node_tree, ensure_input_and_output_nodes, add_vector_math_operation_nodes, add_boolean_math_operation_nodes, add_math_operation_nodes, add_switch_node

def ensure_triangle_normal_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('OUTPUT', 'NodeSocketVector', 'Normal'),
    )

    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)

        result_socket = add_vector_math_operation_nodes(nt, 'NORMALIZE', (
            add_vector_math_operation_nodes(nt,'CROSS_PRODUCT', (
                add_vector_math_operation_nodes(nt, 'SUBTRACT', (input_node.outputs['A'], input_node.outputs['B'])),
                add_vector_math_operation_nodes(nt, 'SUBTRACT', (input_node.outputs['B'], input_node.outputs['C'])),
            ))
        ))

        nt.links.new(result_socket, output_node.inputs['Normal'])
        
    return ensure_geometry_node_tree('Triangle Normal', items, build_function)


def ensure_bdk_terrain_quad_coordinate_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'Min'),
        ('INPUT', 'NodeSocketVector', 'Max'),
        ('INPUT', 'NodeSocketInteger', 'Terrain Resolution'),
        ('INPUT', 'NodeSocketVector', 'Position'),
        ('OUTPUT', 'NodeSocketInteger', 'X'),
        ('OUTPUT', 'NodeSocketInteger', 'Y'),
    )

    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)
        x, y, _ = add_separate_xyz_node(nt, 
            add_vector_math_operation_nodes(nt, 'SCALE', (
                add_vector_math_operation_nodes(nt, 'DIVIDE', (
                    add_vector_math_operation_nodes(nt, 'SUBTRACT', (input_node.outputs['Position'], input_node.outputs['Min'])),
                    add_vector_math_operation_nodes(nt, 'SUBTRACT', (input_node.outputs['Max'], input_node.outputs['Min'])),
                )),
                add_integer_math_operation_nodes(nt, 'SUBTRACT', (input_node.outputs['Terrain Resolution'], 1))
            ))
        )
        nt.links.new(add_float_to_integer_node(x, 'TRUNCATE'), output_node.inputs['X'])
        nt.links.new(add_float_to_integer_node(y, 'TRUNCATE'), output_node.inputs['Y'])

    return ensure_geometry_node_tree('BDK Terrain Squad Coordinate', items, build_function)


def ensure_bdk_terrain_quad_is_edge_turned_node_tree() -> NodeTree:
    items = (
        ('OUTPUT', 'NodeSocketBoolean', 'Result'),
    )

    def build_function(nt: NodeTree):
        output_node = nt.nodes.new(type='NodeGroupOutput')

        corners_of_face_node_1 = nt.nodes.new('GeometryNodeCornersOfFace')
        vertex_of_corner_node_1 = nt.nodes.new('GeometryNodeVertexOfCorner')
        nt.links.new(corners_of_face_node_1.outputs['Corner Index'], vertex_of_corner_node_1.inputs['Corner Index'])

        corners_of_face_node_2 = nt.nodes.new('GeometryNodeCornersOfFace')
        corners_of_face_node_2.inputs['Sort Index'].default_value = 1
        vertex_of_corner_node_2 = nt.nodes.new('GeometryNodeVertexOfCorner')
        nt.links.new(corners_of_face_node_2.outputs['Corner Index'], vertex_of_corner_node_2.inputs['Corner Index'])

        nt.links.new(
            add_comparison_nodes(nt, 'INT', 'NOT_EQUAL', (
                add_integer_math_operation_nodes(nt, 'ABSOLUTE', (
                    add_integer_math_operation_nodes(nt, 'SUBTRACT', (
                        vertex_of_corner_node_1.outputs['Vertex Index'],
                        vertex_of_corner_node_2.outputs['Vertex Index'],
                    ))
                )),
                1
            )),
            output_node.inputs['Result']
        )

    return ensure_geometry_node_tree('BDK Terrain Is Edge Turned', items, build_function)


def ensure_bdk_terrain_position_is_inside() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'Position'),
        ('INPUT', 'NodeSocketVector', 'Min'),
        ('INPUT', 'NodeSocketVector', 'Max'),
        ('OUTPUT', 'NodeSocketBoolean', 'Is Inside'),
    )

    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)

        pos_x, pos_y, _ = add_separate_xyz_node(nt, input_node.outputs["Position"])
        min_x, min_y, _ = add_separate_xyz_node(nt, input_node.outputs["Min"])
        max_x, max_y, _ = add_separate_xyz_node(nt, input_node.outputs["Max"])

        nt.links.new(
            output_node.inputs["Is Inside"],
            add_boolean_math_operation_nodes(nt, 'AND', (
                add_boolean_math_operation_nodes(nt, 'AND', (
                    add_comparison_nodes(nt, 'FLOAT', 'GREATER_THAN_OR_EQUAL', (pos_x, min_x)),
                    add_comparison_nodes(nt, 'FLOAT', 'LESS_THAN', (pos_x, max_x)),
                )),
                add_boolean_math_operation_nodes(nt, 'AND', (
                    add_comparison_nodes(nt, 'FLOAT', 'GREATER_THAN_OR_EQUAL', (pos_y, min_y)),
                    add_comparison_nodes(nt, 'FLOAT', 'LESS_THAN', (pos_y, max_y)),
                ))
            ))
        )

    return ensure_geometry_node_tree('BDK Terrain Position Is Inside', items, build_function)


def ensure_bdk_terrain_quad_indices() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInteger', 'X'),
        ('INPUT', 'NodeSocketInteger', 'Y'),
        ('INPUT', 'NodeSocketInteger', 'Terrain Resolution'),
        ('OUTPUT', 'NodeSocketInteger', 'Vertex Index'),
        ('OUTPUT', 'NodeSocketInteger', 'Face Index'),
    )

    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)

        x = input_node.outputs['X']
        y = input_node.outputs['Y']
        terrain_resolution = input_node.outputs['Terrain Resolution']

        nt.links.new(
            output_node.inputs['Vertex Index'],
            add_integer_math_operation_nodes(nt, 'ADD', (x, add_integer_math_operation_nodes(nt, 'MULTIPLY', (y, terrain_resolution))))
        )

        nt.links.new(
            output_node.inputs['Face Index'],
            add_integer_math_operation_nodes(nt, 'ADD', (
                x,
                add_integer_math_operation_nodes(nt, 'MULTIPLY', (
                    y,
                    add_integer_math_operation_nodes(nt, 'SUBTRACT', (terrain_resolution, 1))
                ))
            ))
        )

    return ensure_geometry_node_tree('BDK Terrain Quad Indices', items, build_function)

def ensure_bdk_terrain_quad_uv() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'Position'),
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('OUTPUT', 'NodeSocketFloat', 'U'),
        ('OUTPUT', 'NodeSocketFloat', 'V'),
    )

    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)

        px, py, _ = add_separate_xyz_node(nt, input_node.outputs['Position'])
        ax, ay, _ = add_separate_xyz_node(nt, input_node.outputs['A'])
        bx, _, _ = add_separate_xyz_node(nt, input_node.outputs['B'])
        _, cy, _ = add_separate_xyz_node(nt, input_node.outputs['C'])

        nt.links.new(
            output_node.inputs['U'],
            add_math_operation_nodes(nt, 'DIVIDE', (
                add_math_operation_nodes(nt, 'SUBTRACT', (px, ax)),
                add_math_operation_nodes(nt, 'SUBTRACT', (bx, ax))
            ))
        )
        nt.links.new(
            output_node.inputs['V'],
            add_math_operation_nodes(nt, 'DIVIDE', (
                add_math_operation_nodes(nt, 'SUBTRACT', (py, ay)),
                add_math_operation_nodes(nt, 'SUBTRACT', (cy, ay))
            ))
        )
    
    return ensure_geometry_node_tree('BDK Terrain Quad UV', items, build_function)

def ensure_bdk_terrain_quad_triangle() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketBoolean', 'Is Edge Turned'),
        ('INPUT', 'NodeSocketFloat', 'Quad U'),
        ('INPUT', 'NodeSocketFloat', 'Quad V'),
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('INPUT', 'NodeSocketVector', 'D'),
    )


    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)

        a = input_node.outputs['A']
        b = input_node.outputs['B']
        c = input_node.outputs['C']
        d = input_node.outputs['D']
        qu = input_node.outputs['Quad U']
        qv = input_node.outputs['Quad V']
        is_edge_turned = input_node.outputs['Is Edge Turned']

        # A
        nt.links.new(
            output_node.inputs['A'],
            add_switch_node(nt, 'VECTOR', is_edge_turned, b, a)
            )
        
        # B
        nt.links.new(
            output_node.inputs['B'],
            add_switch_node(nt,
                            'VECTOR', 
                            is_edge_turned,
                            add_switch_node(nt, 'VECTOR', add_comparison_nodes(nt, 'FLOAT', 'GREATER_THAN', qu, qv), d, b),
                            add_switch_node(nt, 'VECTOR', add_comparison_nodes(nt, 'FLOAT', 'LESS_THAN', add_math_operation_nodes(nt, 'SUBTRACT', 1.0, qu), qv), c, d)
            ))

        # C
        nt.links.new(
            output_node.inputs['C'],
            add_switch_node(nt,
                            'VECTOR', 
                            is_edge_turned,
                            add_switch_node(nt, 'VECTOR', add_comparison_nodes(nt, 'FLOAT', 'GREATER_THAN', qu, qv), d, b),
                            add_switch_node(nt, 'VECTOR', add_comparison_nodes(nt, 'FLOAT', 'LESS_THAN', add_math_operation_nodes(nt, 'SUBTRACT', 1.0, qu), qv), c, d)
        ))

    return ensure_geometry_node_tree('BDK Terrain Quad Triangle', items, build_function)


def ensure_scalar_cross_product_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    )

    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)
        ax, ay, _ = add_separate_xyz_node(nt, input_node.outputs['A'])
        bx, by, _ = add_separate_xyz_node(nt, input_node.outputs['B'])
        cx, cy, _ = add_separate_xyz_node(nt, input_node.outputs['C'])
        nt.links.new(
            output_node.inputs['Result'],
            add_math_operation_nodes(nt, 'ADD', (
                add_math_operation_nodes(nt, 'MULTIPLY', (
                    add_math_operation_nodes(nt, 'SUBTRACT', (ax, bx)),
                    add_math_operation_nodes(nt, 'SUBTRACT', (by, cy))
                )),
                add_math_operation_nodes(nt, 'MULTIPLY', (
                    add_math_operation_nodes(nt, 'SUBTRACT', (cx, bx)),
                    add_math_operation_nodes(nt, 'SUBTRACT', (ay, by))
                ))
            )
        ))

    return ensure_geometry_node_tree('Scalar Cross Product', items, build_function)


def ensure_barycentric_weights_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('INPUT', 'NodeSocketVector', 'Position'),
        ('OUTPUT', 'NodeSocketFloat', 'X'),
        ('OUTPUT', 'NodeSocketFloat', 'Y'),
    )

    def build_function(nt: NodeTree):
        def scalar_cross_product(a: NodeSocket, b: NodeSocket, c: NodeSocket) -> NodeSocket:
            node = nt.nodes.new('GeometryNodeGroup')
            nt.links.new(node.inputs['A'], a)
            nt.links.new(node.inputs['B'], b)
            nt.links.new(node.inputs['C'], c)
            return node.outputs['Value']
    
        input_node, output_node = ensure_input_and_output_nodes(nt)

        a = input_node.outputs['A']
        b = input_node.outputs['A']
        c = input_node.outputs['A']
        position = input_node.outputs['Position']

        sx = scalar_cross_product(b, c, position)
        sy = scalar_cross_product(c, a, position)
        sz = scalar_cross_product(a, b, position)

        x, y, _ = add_separate_xyz_node(nt, 
                    add_vector_math_operation_nodes(nt, 'SCALE', (
                        add_combine_xyz_node(nt, sx, sy, sz),
                        add_math_operation_nodes(nt, 'DIVIDE', (
                            1.0,
                            add_math_operation_nodes(nt, 'ADD', (
                                add_math_operation_nodes(nt, 'ADD', (sx, sy)),
                                sz
                            ))
                        ))
        )))
        nt.links.new(x, output_node.inputs['X'])
        nt.links.new(y, output_node.inputs['Y'])

    return ensure_geometry_node_tree('Barycentric Weights', items, build_function)


def ensure_barycentric_interpolation_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('INPUT', 'NodeSocketFloat', 'X'),
        ('INPUT', 'NodeSocketFloat', 'Y'),
        ('OUTPUT', 'NodeSocketVector', 'Result'),
    )

    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)
        inputs = input_node.outputs
        outputs = output_node.inputs
        a = inputs['A']
        b = inputs['B']
        c = inputs['C']
        u = inputs['U']
        v = inputs['V']
        nt.links.new(
            outputs['Result'],
            add_vector_math_operation_nodes(nt, 'ADD', (
                add_vector_math_operation_nodes(nt, 'ADD', (
                    add_vector_math_operation_nodes(nt, 'SCALE', (a, u)),
                    add_vector_math_operation_nodes(nt, 'SCALE', (b, v)),
                )),
                add_vector_math_operation_nodes(nt, 'SCALE', (c,
                    add_math_operation_nodes(nt, 'SUBTRACT', (
                        add_math_operation_nodes(nt, 'SUBTRACT', (1.0, u)),
                        v
                    ))
                ))
            ))
        )

    return ensure_geometry_node_tree('Barycentric Interpolation', items, build_function)


def ensure_barycentric_projection_2d_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('INPUT', 'NodeSocketVector', 'Position'),
        ('OUTPUT', 'NodeSocketVector', 'Result'),
    )

    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)
        inputs = input_node.outputs

        weights_node = nt.nodes.new(type='GeometryNodeGroup')
        weights_node.node_tree = ensure_barycentric_weights_node_tree()

        interp_node = nt.nodes.new(type='GeometryNodeGroup')
        interp_node.node_tree = ensure_barycentric_interpolation_node_tree()

        nt.links.new(inputs['A'], weights_node.inputs['A'])
        nt.links.new(inputs['B'], weights_node.inputs['B'])
        nt.links.new(inputs['C'], weights_node.inputs['C'])
        nt.links.new(inputs['Position'], weights_node.inputs['Position'])
        nt.links.new(inputs['A'], interp_node.inputs['A'])
        nt.links.new(inputs['B'], interp_node.inputs['B'])
        nt.links.new(inputs['C'], interp_node.inputs['C'])
        nt.links.new(weights_node.outputs['X'], interp_node.inputs['U'])
        nt.links.new(weights_node.outputs['Y'], interp_node.inputs['V'])
        nt.links.new(interp_node.outputs['Result'], output_node.inputs['Result'])

    return ensure_geometry_node_tree('Barycentric Projection 2D', items, build_function)


def ensure_bdk_terrain_sample_node_tree() -> NodeTree:
    inputs = (
        ('INPUT', 'NodeSocketObject', 'Terrain Object'),
        ('INPUT', 'NodeSocketInteger', 'Terrain Resolution'),
        ('INPUT', 'NodeSocketVector', 'Position'),
        ('OUTPUT', 'NodeSocketVector', 'Is Inside'),
        ('OUTPUT', 'NodeSocketVector', 'Position'),
        ('OUTPUT', 'NodeSocketVector', 'Normal'),
        ('OUTPUT', 'NodeSocketInt', 'Face Index'),
        ('OUTPUT', 'NodeSocketInt', 'Vertex Index'),
    )
