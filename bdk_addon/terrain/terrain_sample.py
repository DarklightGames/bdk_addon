from bpy.types import NodeTree, NodeSocket

from ..node_helpers import add_chained_math_nodes, add_combine_xyz_node, add_comparison_nodes, add_float_to_integer_node, add_group_node, add_integer_math_operation_nodes, add_invert_matrix_node, add_node, add_separate_xyz_node, add_transform_point_node, ensure_geometry_node_tree, ensure_input_and_output_nodes, add_vector_math_operation_nodes, add_boolean_math_operation_nodes, add_math_operation_nodes, add_switch_node, ensure_inputs_and_outputs

def ensure_triangle_normal_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('OUTPUT', 'NodeSocketVector', 'Normal'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        result_socket = add_vector_math_operation_nodes(nt, 'NORMALIZE', [
            add_vector_math_operation_nodes(nt,'CROSS_PRODUCT', (
                add_vector_math_operation_nodes(nt, 'SUBTRACT', (inputs['A'], inputs['B'])),
                add_vector_math_operation_nodes(nt, 'SUBTRACT', (inputs['B'], inputs['C'])),
            ))
        ])

        nt.links.new(result_socket, outputs['Normal'])
        
    return ensure_geometry_node_tree('Triangle Normal', items, build_function)


def ensure_bdk_terrain_quad_coordinate_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'Min'),
        ('INPUT', 'NodeSocketVector', 'Max'),
        ('INPUT', 'NodeSocketInt', 'Terrain Resolution'),
        ('INPUT', 'NodeSocketVector', 'Position'),
        ('OUTPUT', 'NodeSocketInt', 'X'),
        ('OUTPUT', 'NodeSocketInt', 'Y'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)
        x, y, _ = add_separate_xyz_node(nt, 
            add_vector_math_operation_nodes(nt, 'SCALE', {
                'Vector': add_vector_math_operation_nodes(nt, 'DIVIDE', (
                    add_vector_math_operation_nodes(nt, 'SUBTRACT', (inputs['Position'], inputs['Min'])),
                    add_vector_math_operation_nodes(nt, 'SUBTRACT', (inputs['Max'], inputs['Min'])),
                )),
                'Scale': add_integer_math_operation_nodes(nt, 'SUBTRACT', (inputs['Terrain Resolution'], 1))
            })
        )
        nt.links.new(add_float_to_integer_node(nt, 'TRUNCATE', x), outputs['X'])
        nt.links.new(add_float_to_integer_node(nt, 'TRUNCATE', y), outputs['Y'])

    return ensure_geometry_node_tree('BDK Terrain Quad Coordinate', items, build_function)


def ensure_bdk_terrain_quad_is_edge_turned() -> NodeTree:
    items = (
        ('OUTPUT', 'NodeSocketBool', 'Result'),
    )

    def build_function(nt: NodeTree):
        outputs = nt.nodes.new(type='NodeGroupOutput').inputs

        corners_of_face_node_1 = nt.nodes.new('GeometryNodeCornersOfFace')
        vertex_of_corner_node_1 = nt.nodes.new('GeometryNodeVertexOfCorner')
        nt.links.new(corners_of_face_node_1.outputs['Corner Index'], vertex_of_corner_node_1.inputs['Corner Index'])

        corners_of_face_node_2 = nt.nodes.new('GeometryNodeCornersOfFace')
        corners_of_face_node_2.inputs['Sort Index'].default_value = 1
        vertex_of_corner_node_2 = nt.nodes.new('GeometryNodeVertexOfCorner')
        nt.links.new(corners_of_face_node_2.outputs['Corner Index'], vertex_of_corner_node_2.inputs['Corner Index'])

        nt.links.new(
            outputs['Result'],
            add_comparison_nodes(nt, 'INT', 'NOT_EQUAL', 
                                 a=(add_integer_math_operation_nodes(nt, 'ABSOLUTE', (
                                     add_integer_math_operation_nodes(nt, 'SUBTRACT', (
                                         vertex_of_corner_node_1.outputs['Vertex Index'],
                                         vertex_of_corner_node_2.outputs['Vertex Index'],
                                         )),
                                         ))
                                    ), b=1)
        )

    return ensure_geometry_node_tree('BDK Terrain Is Edge Turned', items, build_function)


def ensure_bdk_terrain_position_is_inside() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'Position'),
        ('INPUT', 'NodeSocketVector', 'Min'),
        ('INPUT', 'NodeSocketVector', 'Max'),
        ('OUTPUT', 'NodeSocketBool', 'Is Inside'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        pos_x, pos_y, _ = add_separate_xyz_node(nt, inputs["Position"])
        min_x, min_y, _ = add_separate_xyz_node(nt, inputs["Min"])
        max_x, max_y, _ = add_separate_xyz_node(nt, inputs["Max"])

        nt.links.new(
            outputs["Is Inside"],
            add_boolean_math_operation_nodes(nt, 'AND', (
                add_boolean_math_operation_nodes(nt, 'AND', (
                    add_comparison_nodes(nt, 'FLOAT', 'GREATER_EQUAL', pos_x, min_x),
                    add_comparison_nodes(nt, 'FLOAT', 'LESS_THAN', pos_x, max_x),
                )),
                add_boolean_math_operation_nodes(nt, 'AND', (
                    add_comparison_nodes(nt, 'FLOAT', 'GREATER_EQUAL', pos_y, min_y),
                    add_comparison_nodes(nt, 'FLOAT', 'LESS_THAN', pos_y, max_y),
                ))
            ))
        )

    return ensure_geometry_node_tree('BDK Terrain Position Is Inside', items, build_function)


def ensure_bdk_terrain_quad_indices() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInt', 'X'),
        ('INPUT', 'NodeSocketInt', 'Y'),
        ('INPUT', 'NodeSocketInt', 'Terrain Resolution'),
        ('OUTPUT', 'NodeSocketInt', 'Vertex Index'),
        ('OUTPUT', 'NodeSocketInt', 'Face Index'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        x = inputs['X']
        y = inputs['Y']
        terrain_resolution = inputs['Terrain Resolution']

        nt.links.new(
            outputs['Vertex Index'],
            add_integer_math_operation_nodes(nt, 'ADD', (x, add_integer_math_operation_nodes(nt, 'MULTIPLY', (y, terrain_resolution))))
        )

        nt.links.new(
            outputs['Face Index'],
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
        inputs, outputs = ensure_inputs_and_outputs(nt)

        px, py, _ = add_separate_xyz_node(nt, inputs['Position'])
        ax, ay, _ = add_separate_xyz_node(nt, inputs['A'])
        bx, _, _ = add_separate_xyz_node(nt, inputs['B'])
        _, cy, _ = add_separate_xyz_node(nt, inputs['C'])

        nt.links.new(
            outputs['U'],
            add_math_operation_nodes(nt, 'DIVIDE', (
                add_math_operation_nodes(nt, 'SUBTRACT', (px, ax)),
                add_math_operation_nodes(nt, 'SUBTRACT', (bx, ax))
            ))
        )
        nt.links.new(
            outputs['V'],
            add_math_operation_nodes(nt, 'DIVIDE', (
                add_math_operation_nodes(nt, 'SUBTRACT', (py, ay)),
                add_math_operation_nodes(nt, 'SUBTRACT', (cy, ay))
            ))
        )
    
    return ensure_geometry_node_tree('BDK Terrain Quad UV', items, build_function)

def ensure_bdk_terrain_quad_triangle() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketBool', 'Is Edge Turned'),
        ('INPUT', 'NodeSocketFloat', 'Quad U'),
        ('INPUT', 'NodeSocketFloat', 'Quad V'),
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('INPUT', 'NodeSocketVector', 'D'),
        ('OUTPUT', 'NodeSocketVector', 'A'),
        ('OUTPUT', 'NodeSocketVector', 'B'),
        ('OUTPUT', 'NodeSocketVector', 'C'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        a = inputs['A']
        b = inputs['B']
        c = inputs['C']
        d = inputs['D']
        qu = inputs['Quad U']
        qv = inputs['Quad V']
        is_edge_turned = inputs['Is Edge Turned']

        # A
        nt.links.new(outputs['A'], add_switch_node(nt, 'VECTOR', is_edge_turned, a, b))
        
        # B
        nt.links.new(
            outputs['B'],
            add_switch_node(nt,
                            'VECTOR', 
                            is_edge_turned,
                            add_switch_node(nt, 'VECTOR', add_comparison_nodes(nt, 'FLOAT', 'GREATER_THAN', qu, qv), d, b),
                            add_switch_node(nt, 'VECTOR', add_comparison_nodes(nt, 'FLOAT', 'LESS_THAN', add_math_operation_nodes(nt, 'SUBTRACT', (1.0, qu)), qv), c, d)
            ))

        # C
        nt.links.new(
            outputs['C'],
            add_switch_node(nt,
                            'VECTOR', 
                            is_edge_turned,
                            add_switch_node(nt, 'VECTOR', add_comparison_nodes(nt, 'FLOAT', 'GREATER_THAN', qu, qv), c, d),
                            add_switch_node(nt, 'VECTOR', add_comparison_nodes(nt, 'FLOAT', 'LESS_THAN', add_math_operation_nodes(nt, 'SUBTRACT', (1.0, qu)), qv), a, c)
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
        inputs, outputs = ensure_inputs_and_outputs(nt)
        ax, ay, _ = add_separate_xyz_node(nt, inputs['A'])
        bx, by, _ = add_separate_xyz_node(nt, inputs['B'])
        cx, cy, _ = add_separate_xyz_node(nt, inputs['C'])
        nt.links.new(
            outputs['Value'],
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
            node = add_group_node(nt, ensure_scalar_cross_product_node_tree)
            nt.links.new(node.inputs['A'], a)
            nt.links.new(node.inputs['B'], b)
            nt.links.new(node.inputs['C'], c)
            return node.outputs['Value']
    
        inputs, outputs = ensure_inputs_and_outputs(nt)

        a = inputs['A']
        b = inputs['B']
        c = inputs['C']
        position = inputs['Position']

        sx = scalar_cross_product(b, c, position)
        sy = scalar_cross_product(c, a, position)
        sz = scalar_cross_product(a, b, position)

        x, y, _ = add_separate_xyz_node(nt, 
                    add_vector_math_operation_nodes(nt, 'SCALE', {
                        'Vector': add_combine_xyz_node(nt, sx, sy, sz),
                        'Scale': add_math_operation_nodes(nt, 'DIVIDE', (
                            1.0,
                            add_math_operation_nodes(nt, 'ADD', (
                                add_math_operation_nodes(nt, 'ADD', (sx, sy)),
                                sz
                            ))
                        ))
                    }
                    ))
        nt.links.new(x, outputs['X'])
        nt.links.new(y, outputs['Y'])

    return ensure_geometry_node_tree('Barycentric Weights', items, build_function)


def ensure_barycentric_interpolation_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketVector', 'C'),
        ('INPUT', 'NodeSocketFloat', 'U'),
        ('INPUT', 'NodeSocketFloat', 'V'),
        ('OUTPUT', 'NodeSocketVector', 'Result'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)
        a = inputs['A']
        b = inputs['B']
        c = inputs['C']
        u = inputs['U']
        v = inputs['V']
        nt.links.new(
            outputs['Result'],
            add_vector_math_operation_nodes(nt, 'ADD', (
                add_vector_math_operation_nodes(nt, 'ADD', (
                    add_vector_math_operation_nodes(nt, 'SCALE', {'Vector': a, 'Scale': u}),
                    add_vector_math_operation_nodes(nt, 'SCALE', {'Vector': b, 'Scale': v}),
                )),
                add_vector_math_operation_nodes(nt, 'SCALE', {'Vector': c, 'Scale': add_math_operation_nodes(nt, 'SUBTRACT', (
                        add_math_operation_nodes(nt, 'SUBTRACT', (1.0, u)),
                        v
                    ))}
                )
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
        inputs, outputs = ensure_inputs_and_outputs(nt)

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
        nt.links.new(interp_node.outputs['Result'], outputs['Result'])

    return ensure_geometry_node_tree('Barycentric Projection 2D', items, build_function)


def ensure_bdk_terrain_quad_vertex_indices() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInt', 'Terrain Resolution'),
        ('INPUT', 'NodeSocketInt', 'Vertex Index'),
        ('OUTPUT', 'NodeSocketInt', 'A'),
        ('OUTPUT', 'NodeSocketInt', 'B'),
        ('OUTPUT', 'NodeSocketInt', 'C'),
        ('OUTPUT', 'NodeSocketInt', 'D'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        vertex_index = inputs['Vertex Index']
        terrain_resolution = inputs['Terrain Resolution']

        nt.links.new(outputs['A'], vertex_index)
        nt.links.new(outputs['B'], add_math_operation_nodes(nt, 'ADD', (vertex_index, 1)))
        nt.links.new(outputs['C'], add_math_operation_nodes(nt, 'ADD', (terrain_resolution, vertex_index)))
        nt.links.new(outputs['D'], add_chained_math_nodes(nt, 'ADD', (terrain_resolution, vertex_index, 1)))

    return ensure_geometry_node_tree('BDK Terrain Quad Vertex Indices', items, build_function)


def ensure_bdk_terrain_quad_vertices() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Terrain'),
        ('INPUT', 'NodeSocketInt', 'Terrain Resolution'),
        ('INPUT', 'NodeSocketInt', 'Vertex Index'),
        ('OUTPUT', 'NodeSocketVector', 'A'),
        ('OUTPUT', 'NodeSocketVector', 'B'),
        ('OUTPUT', 'NodeSocketVector', 'C'),
        ('OUTPUT', 'NodeSocketVector', 'D'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        quad_vertex_indices_node = add_group_node(nt, ensure_bdk_terrain_quad_vertex_indices, inputs=(
            ('Terrain Resolution', inputs['Terrain Resolution']),
            ('Vertex Index', inputs['Vertex Index'])
        ))
        
        def sample_index(index: NodeSocket) -> NodeSocket:
            position_node = nt.nodes.new('GeometryNodeInputPosition')
            sample_index_node = nt.nodes.new('GeometryNodeSampleIndex')
            sample_index_node.data_type = 'FLOAT_VECTOR'
            sample_index_node.domain = 'POINT'
            nt.links.new(inputs['Terrain'], sample_index_node.inputs['Geometry'])
            nt.links.new(position_node.outputs['Position'], sample_index_node.inputs['Value'])
            nt.links.new(index, sample_index_node.inputs['Index'])
            return sample_index_node.outputs['Value']
    
        nt.links.new(outputs['A'], sample_index(quad_vertex_indices_node.outputs['A']))
        nt.links.new(outputs['B'], sample_index(quad_vertex_indices_node.outputs['B']))
        nt.links.new(outputs['C'], sample_index(quad_vertex_indices_node.outputs['C']))
        nt.links.new(outputs['D'], sample_index(quad_vertex_indices_node.outputs['D']))

    return ensure_geometry_node_tree('BDK Terrain Quad Vertices', items, build_function)


def ensure_bdk_terrain_sample_node_tree() -> NodeTree:
    """
    This is a node group that wraps the BDK Terrain Sample node and adds the terrain transform handling.
    In the future, we should add the handling of hte terrain transform to the BDK Terrain Sample node itself, but for
    the sake of not having to redistribute a new version of the BDK binary, we'll do it this way for now.
    """
    items = (
        ('INPUT', 'NodeSocketInt', 'Terrain Resolution'),
        ('INPUT', 'NodeSocketGeometry', 'Terrain Geometry'),
        ('INPUT', 'NodeSocketMatrix', 'Terrain Transform'),
        ('INPUT', 'NodeSocketVector', 'Position'),
        ('OUTPUT', 'NodeSocketBool', 'Is Inside'),
        ('OUTPUT', 'NodeSocketVector', 'Normal'),
        ('OUTPUT', 'NodeSocketVector', 'Position'),
        ('OUTPUT', 'NodeSocketInt', 'Face Index'),
        ('OUTPUT', 'NodeSocketInt', 'Vertex Index'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        terrain_transform = inputs['Terrain Transform']
        terrain_resolution = inputs['Terrain Resolution']
        terrain_geometry = inputs['Terrain Geometry']

        position = add_transform_point_node(nt, inputs['Position'], add_invert_matrix_node(nt, terrain_transform))
        bounding_box = add_node(nt, 'GeometryNodeBoundBox', inputs=(('Geometry', terrain_geometry),))
        bounding_box_min = bounding_box.outputs['Min']
        bounding_box_max = bounding_box.outputs['Max']

        is_inside = add_group_node(nt, ensure_bdk_terrain_position_is_inside, inputs=(
            ('Position', position),
            ('Min', bounding_box_min),
            ('Max', bounding_box_max)
        )).outputs['Is Inside']

        quad_coordinate_node = add_group_node(nt, ensure_bdk_terrain_quad_coordinate_node_tree, inputs=(
            ('Min', bounding_box_min),
            ('Max', bounding_box_max),
            ('Terrain Resolution', terrain_resolution),
            ('Position', position)
        ))

        quad_indices_node = add_group_node(nt, ensure_bdk_terrain_quad_indices, inputs=(
            ('X', quad_coordinate_node.outputs['X']),
            ('Y', quad_coordinate_node.outputs['Y']),
            ('Terrain Resolution', terrain_resolution)
        ))

        vertex_index = quad_indices_node.outputs['Vertex Index']
        face_index = quad_indices_node.outputs['Face Index']

        quad_vertices_node = add_group_node(nt, ensure_bdk_terrain_quad_vertices, inputs=(
            ('Terrain', terrain_geometry),
            ('Terrain Resolution', terrain_resolution),
            ('Vertex Index', vertex_index)
        ))

        quad_uv_node = add_group_node(nt, ensure_bdk_terrain_quad_uv, inputs=(
            ('Position', position),
            ('A', quad_vertices_node.outputs['A']),
            ('B', quad_vertices_node.outputs['B']),
            ('C', quad_vertices_node.outputs['C']),
        ))

        is_edge_turned_node = add_node(nt, 'GeometryNodeSampleIndex', inputs=(
            ('Geometry', terrain_geometry),
            ('Value', add_group_node(nt, ensure_bdk_terrain_quad_is_edge_turned).outputs['Result']),
            ('Index', face_index)
        ))
        is_edge_turned_node.data_type = 'BOOLEAN'
        is_edge_turned_node.domain = 'FACE'
        is_edge_turned = is_edge_turned_node.outputs['Value']

        quad_triangle_node = add_group_node(nt, ensure_bdk_terrain_quad_triangle, inputs=(
            ('Is Edge Turned', is_edge_turned),
            ('Quad U', quad_uv_node.outputs['U']),
            ('Quad V', quad_uv_node.outputs['V']),
            ('A', quad_vertices_node.outputs['A']),
            ('B', quad_vertices_node.outputs['B']),
            ('C', quad_vertices_node.outputs['C']),
            ('D', quad_vertices_node.outputs['D']),
        ))

        normal = add_group_node(nt, ensure_triangle_normal_node_tree, inputs=(
            ('A', quad_triangle_node.outputs['A']),
            ('B', quad_triangle_node.outputs['B']),
            ('C', quad_triangle_node.outputs['C']),
        )).outputs['Normal']

        barycentric_projection_2d = add_group_node(nt, ensure_barycentric_projection_2d_node_tree, inputs=(
            ('A', quad_triangle_node.outputs['A']),
            ('B', quad_triangle_node.outputs['B']),
            ('C', quad_triangle_node.outputs['C']),
            ('Position', position),
        ))

        position = add_transform_point_node(
            nt,
            add_switch_node(nt, 'VECTOR', is_inside, position, barycentric_projection_2d.outputs['Result']),
            terrain_transform
        )

        # Outputs
        nt.links.new(outputs['Is Inside'], is_inside)
        nt.links.new(outputs['Position'], position)
        nt.links.new(outputs['Normal'], normal)
        nt.links.new(outputs['Face Index'], face_index)
        nt.links.new(outputs['Vertex Index'], vertex_index)

    return ensure_geometry_node_tree('BDK Terrain Sample', items, build_function)
