from bpy.types import NodeTree, NodeSocket
from ..node_helpers import add_comparison_nodes, add_domain_size_node, add_float_to_integer_node, add_index_node, add_node, add_position_input_node, add_repeat_zone_nodes, add_switch_node, ensure_geometry_node_tree, ensure_inputs_and_outputs, add_vector_math_operation_nodes, add_separate_xyz_node, add_chained_math_nodes, add_group_node, add_math_operation_nodes, add_boolean_math_operation_nodes, add_integer_math_operation_nodes, join_geometry


def ensure_length_squared_node_tree():
    inputs = (
        ('INPUT', 'NodeSocketVector', 'Vector'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)
        x, y, z = add_separate_xyz_node(
            nt, add_vector_math_operation_nodes(nt, 'MULTIPLY', (inputs['Vector'], inputs['Vector'])))
        nt.links.new(outputs['Value'], add_chained_math_nodes(nt, 'ADD', (x, y, z)))
    
    return ensure_geometry_node_tree('Length Squared', inputs, build_function)


def ensure_vector_sum_node_tree():
    inputs = (
        ('INPUT', 'NodeSocketVector', 'Vector'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)
        x, y, z = add_separate_xyz_node(nt, inputs['Vector'])
        nt.links.new(outputs['Value'], add_chained_math_nodes(nt, 'ADD', (x, y, z)))

    return ensure_geometry_node_tree('Vector Sum', inputs, build_function)


def length_squared(nt: NodeTree, vector: NodeSocket) -> NodeSocket:
    length_squared_node = add_group_node(nt, ensure_length_squared_node_tree, [('Vector', vector)])
    return length_squared_node.outputs['Value']


def ensure_line_sphere_intersect_abc_node_tree():
    items = (
        ('INPUT', 'NodeSocketVector', 'Line Start'),
        ('INPUT', 'NodeSocketVector', 'Line End'),
        ('INPUT', 'NodeSocketVector', 'Sphere Origin'),
        ('INPUT', 'NodeSocketFloat', 'Sphere Radius'),
        ('OUTPUT', 'NodeSocketFloat', 'A'),
        ('OUTPUT', 'NodeSocketFloat', 'B'),
        ('OUTPUT', 'NodeSocketFloat', 'C'),
    )

    def build_function(nt: NodeTree):
    
        def vector_sum(vector: NodeSocket) -> NodeSocket:
            length_squared_node = add_group_node(nt, ensure_vector_sum_node_tree, [('Vector', vector)])
            return length_squared_node.outputs['Value']
    
        inputs, outputs = ensure_inputs_and_outputs(nt)

        mag = add_vector_math_operation_nodes(nt, 'SUBTRACT', [inputs['Line End'], inputs['Line Start']])

        # A
        a = length_squared(nt, mag)
        
        # B
        b = add_math_operation_nodes(nt, 'MULTIPLY', [
            2.0,
            vector_sum(add_vector_math_operation_nodes(nt, 'MULTIPLY', [
                mag,
                add_vector_math_operation_nodes(nt, 'SUBTRACT', [
                    inputs['Line Start'],
                    inputs['Sphere Origin']
                    ])
                ]))
            ])
        
        # C
        c = add_math_operation_nodes(nt, 'SUBTRACT', [
            add_math_operation_nodes(nt, 'SUBTRACT', [
                add_math_operation_nodes(nt, 'ADD', [length_squared(nt, inputs['Line Start']), length_squared(nt, inputs['Sphere Origin'])]),
                add_math_operation_nodes(nt, 'MULTIPLY', [
                    add_vector_math_operation_nodes(nt, 'DOT_PRODUCT', [inputs['Sphere Origin'], inputs['Line Start']], 'Value'),
                    2.0
                ])
            ]),
            add_math_operation_nodes(nt, 'MULTIPLY', [inputs['Sphere Radius'], inputs['Sphere Radius']])
        ])

        nt.links.new(a, outputs['A'])
        nt.links.new(b, outputs['B'])
        nt.links.new(c, outputs['C'])

    return ensure_geometry_node_tree('Line-Sphere Intersect ABC', items, build_function)


def ensure_line_sphere_intersect_i_node_tree():
    items = (
        ('INPUT', 'NodeSocketFloat', 'A'),
        ('INPUT', 'NodeSocketFloat', 'B'),
        ('INPUT', 'NodeSocketFloat', 'C'),
        ('OUTPUT', 'NodeSocketFloat', 'i'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        a = inputs['A']
        b = inputs['B']
        c = inputs['C']

        nt.links.new(
            outputs['i'], 
            add_math_operation_nodes(nt, 'SUBTRACT', [
                add_math_operation_nodes(nt, 'MULTIPLY', [b, b]),
                add_math_operation_nodes(nt, 'MULTIPLY', [
                    add_math_operation_nodes(nt, 'MULTIPLY', [4.0, a]),
                    c
                ])
            ]),
        )

    return ensure_geometry_node_tree('Line-Sphere Intersect i', items, build_function)


def ensure_line_point_factor_node_tree():
    items = (
        ('INPUT', 'NodeSocketVector', 'P'),
        ('INPUT', 'NodeSocketVector', 'L1'),
        ('INPUT', 'NodeSocketVector', 'L2'),
        ('INPUT', 'NodeSocketFloat', 'Epsilon'),
        ('INPUT', 'NodeSocketFloat', 'Fallback'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        h = add_vector_math_operation_nodes(nt, 'SUBTRACT', [inputs['P'], inputs['L1']])
        u = add_vector_math_operation_nodes(nt, 'SUBTRACT', [inputs['L2'], inputs['L1']])
        u_length_squared = length_squared(nt, u)
        u_dot_h = add_vector_math_operation_nodes(nt, 'DOT_PRODUCT', [u, h], 'Value')

        nt.links.new(
            outputs['Value'],
            add_switch_node(nt, 'FLOAT', add_comparison_nodes(
                nt, 'FLOAT', 'GREATER_THAN', u_length_squared, inputs['Epsilon']
            ), inputs['Fallback'], add_math_operation_nodes(nt, 'DIVIDE', [u_dot_h, u_length_squared]))
        )

    return ensure_geometry_node_tree('Line Point Factor', items, build_function)


def ensure_use_intersects_node_tree():
    items = (
        ('INPUT', 'NodeSocketInt', 'Intersections'),
        ('INPUT', 'NodeSocketVector', 'Line Start'),
        ('INPUT', 'NodeSocketVector', 'Line End'),
        ('INPUT', 'NodeSocketVector', 'Intersection 1'),
        ('INPUT', 'NodeSocketVector', 'Intersection 2'),
        ('OUTPUT', 'NodeSocketBool', 'Use A'),
        ('OUTPUT', 'NodeSocketBool', 'Use B'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        # Use A
        lpf1 = add_group_node(nt, ensure_line_point_factor_node_tree, [
            ('P', inputs['Intersection 1']),
            ('L1', inputs['Line Start']),
            ('L2', inputs['Line End']),
        ]).outputs['Value']
        use_a = add_boolean_math_operation_nodes(nt, 'AND', [
            add_comparison_nodes(nt, 'INT', 'GREATER_EQUAL', inputs['Intersections'], 1),
            add_boolean_math_operation_nodes(nt, 'AND', [
                add_comparison_nodes(nt, 'FLOAT', 'GREATER_EQUAL', lpf1, 0.0),
                add_comparison_nodes(nt, 'FLOAT', 'LESS_EQUAL', lpf1, 1.0),
            ])
        ])
        nt.links.new(outputs['Use A'], use_a)

        # Use B
        lpf2 = add_group_node(nt, ensure_line_point_factor_node_tree, [
            ('P', inputs['Intersection 2']),
            ('L1', inputs['Line Start']),
            ('L2', inputs['Line End']),
        ]).outputs['Value']
        use_b = add_boolean_math_operation_nodes(nt, 'AND', [
            add_comparison_nodes(nt, 'INT', 'GREATER_EQUAL', inputs['Intersections'], 2),
            add_boolean_math_operation_nodes(nt, 'AND', [
                add_comparison_nodes(nt, 'FLOAT', 'GREATER_EQUAL', lpf2, 0.0),
                add_comparison_nodes(nt, 'FLOAT', 'LESS_EQUAL', lpf2, 1.0),
            ])
        ])
        nt.links.new(outputs['Use B'], use_b)
    
    return ensure_geometry_node_tree('Use Intersects', items, build_function)


def ensure_interpolate_points_node_tree():
    items = (
        ('INPUT', 'NodeSocketVector', 'A'),
        ('INPUT', 'NodeSocketVector', 'B'),
        ('INPUT', 'NodeSocketFloat', 'Length'),
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        points_node = nt.nodes.new('GeometryNodePoints')

        b_sub_a = add_vector_math_operation_nodes(nt, 'SUBTRACT', [inputs['B'], inputs['A']])

        nt.links.new(
            points_node.inputs['Count'],
            add_integer_math_operation_nodes(nt, 'ADD', [
                1,
                add_float_to_integer_node(nt, 'TRUNCATE', add_math_operation_nodes(nt, 'DIVIDE', [
                    add_vector_math_operation_nodes(nt, 'LENGTH', [b_sub_a], output_socket_name='Value'),
                    inputs['Length']
                ]))
            ])
            )
        
        nt.links.new(
            points_node.inputs['Position'],
            add_vector_math_operation_nodes(nt, 'ADD', [
                inputs['A'],
                add_vector_math_operation_nodes(nt, 'SCALE', {
                    'Vector': add_vector_math_operation_nodes(nt, 'NORMALIZE', [b_sub_a]),
                    'Scale': add_math_operation_nodes(nt, 'MULTIPLY', [inputs['Length'], add_index_node(nt)])
                })
                ])
        )

        delete_geometry_node = nt.nodes.new('GeometryNodeDeleteGeometry')
        delete_geometry_node.domain = 'POINT'
        delete_geometry_node.mode = 'ALL'

        nt.links.new(points_node.outputs['Points'], delete_geometry_node.inputs['Geometry'])
        nt.links.new(add_comparison_nodes(nt, 'INT', 'EQUAL', add_index_node(nt), 0), delete_geometry_node.inputs['Selection'])
        nt.links.new(delete_geometry_node.outputs['Geometry'], outputs['Points'])

    return ensure_geometry_node_tree('Interpolate Points', items, build_function)

def ensure_line_sphere_intersect_node_tree():
    items = (
        ('INPUT', 'NodeSocketVector', 'Line Start'),
        ('INPUT', 'NodeSocketVector', 'Line End'),
        ('INPUT', 'NodeSocketVector', 'Sphere Origin'),
        ('INPUT', 'NodeSocketFloat', 'Sphere Radius'),
        ('OUTPUT', 'NodeSocketInt', 'Intersect Count'),
        ('OUTPUT', 'NodeSocketVector', 'Intersection 1'),
        ('OUTPUT', 'NodeSocketVector', 'Intersection 2'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        abc_node = add_group_node(nt, ensure_line_sphere_intersect_abc_node_tree, (
            ('Line Start', inputs['Line Start']),
            ('Line End', inputs['Line End']),
            ('Sphere Origin', inputs['Sphere Origin']),
            ('Sphere Radius', inputs['Sphere Radius']),
        ))
        a = abc_node.outputs['A']
        b = abc_node.outputs['B']
        c = abc_node.outputs['C']
        i = add_group_node(nt, ensure_line_sphere_intersect_i_node_tree, (('A', a), ('B', b), ('C', c))).outputs['i']
        sqrt_i = add_math_operation_nodes(nt, 'SQRT', [i])
        intersections = add_switch_node(nt, 'INT',
                                        add_comparison_nodes(nt, 'FLOAT', 'LESS_THAN', i, 0.0),
                                        add_switch_node(nt, 'INT', add_comparison_nodes(nt, 'FLOAT', 'EQUAL', i, 0.0),
                                                        2,
                                                        1),
                                        0)
        
        # Intersection 1
        intersection_1 = add_vector_math_operation_nodes(nt, 'ADD', [
            inputs['Line Start'],
            add_vector_math_operation_nodes(nt, 'SCALE', {
                'Vector': add_vector_math_operation_nodes(nt, 'SUBTRACT', [inputs['Line End'], inputs['Line Start']]),
                'Scale': add_math_operation_nodes(nt, 'DIVIDE', [
                    add_math_operation_nodes(nt, 'ADD', [
                        add_math_operation_nodes(nt, 'MULTIPLY', [b, -1.0]),
                        sqrt_i
                    ]),
                    add_math_operation_nodes(nt, 'MULTIPLY', [2.0, a])
                ])
            })
            ])
        
        # Intersection 2 (same as above except 'ADD' is 'SUBTRACT')
        intersection_2 = add_vector_math_operation_nodes(nt, 'ADD', [
            inputs['Line Start'],
            add_vector_math_operation_nodes(nt, 'SCALE', {
                'Vector': add_vector_math_operation_nodes(nt, 'SUBTRACT', [inputs['Line End'], inputs['Line Start']]),
                'Scale': add_math_operation_nodes(nt, 'DIVIDE', [
                    add_math_operation_nodes(nt, 'SUBTRACT', [
                        add_math_operation_nodes(nt, 'MULTIPLY', [b, -1.0]),
                        sqrt_i
                    ]),
                    add_math_operation_nodes(nt, 'MULTIPLY', [2.0, a])
                ])
            })
            ])
    
        use_intersects = add_group_node(nt, ensure_use_intersects_node_tree, [
            ('Intersections', intersections),
            ('Line Start', inputs['Line Start']),
            ('Line End', inputs['Line End']),
            ('Intersection 1', intersection_1),
            ('Intersection 2', intersection_2),
        ])
        use_a = use_intersects.outputs['Use A']
        use_b = use_intersects.outputs['Use B']

        nt.links.new(
            outputs['Intersect Count'],
            add_integer_math_operation_nodes(nt, 'ADD', [
                add_switch_node(nt, 'INT', use_a, 0, 1),
                add_switch_node(nt, 'INT', use_b, 0, 1)
            ]))
        nt.links.new(
            outputs['Intersection 1'],
            add_switch_node(nt, 'VECTOR',
                            add_boolean_math_operation_nodes(nt, 'AND', [use_b, add_boolean_math_operation_nodes(nt, 'NOT', [use_a])]),
                            intersection_1,
                            intersection_2
                            )
        )
        nt.links.new(outputs['Intersection 2'], intersection_2)

    return ensure_geometry_node_tree('Line-Sphere Intersect', items, build_function)


def ensure_curve_to_equidistant_points_node_tree():
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketFloat', 'Length'),
        ('OUTPUT', 'NodeSocketGeometry', 'Points'),
    )

    def build_function(nt: NodeTree):
        inputs, outputs = ensure_inputs_and_outputs(nt)

        mesh = add_node(nt, 'GeometryNodeCurveToMesh', [('Curve', inputs['Curve'])]).outputs['Mesh']

        def sample_index(geometry: NodeSocket, value: NodeSocket = None, index: NodeSocket | int = 0) -> NodeSocket:
            return add_node(nt, 'GeometryNodeSampleIndex', [
                ('Geometry', geometry),
                ('Value', value),
                ('Index', index),
                ], data_type='FLOAT_VECTOR', domain='POINT').outputs['Value']

        add_group_node(nt, ensure_line_sphere_intersect_node_tree)

        edge_count = add_domain_size_node(nt, 'MESH', mesh, 'Edge Count')
        first_point = sample_index(mesh, add_position_input_node(nt))
        
        repeat_input_node, repeat_output_node = add_repeat_zone_nodes(nt, [('VECTOR', 'Position')])

        repeat_points = repeat_input_node.outputs['Geometry']

        nt.links.new(repeat_input_node.inputs['Iterations'], edge_count)
        nt.links.new(repeat_input_node.inputs['Geometry'], add_node(nt, 'GeometryNodePoints', [
            ('Count', 1),
            ('Position', first_point)
            ]).outputs['Points'])
        nt.links.new(repeat_input_node.inputs['Position'], first_point)

        # Repeat zone.
        iteration = repeat_input_node.outputs['Iteration']
        line_start = sample_index(mesh, add_position_input_node(nt), iteration)
        line_end = sample_index(mesh, add_position_input_node(nt), add_integer_math_operation_nodes(nt, 'ADD', [iteration, 1]))

        intersect_node = add_group_node(nt, ensure_line_sphere_intersect_node_tree, [
            ('Line Start', line_start),
            ('Line End', line_end),
            ('Sphere Origin', repeat_input_node.outputs['Position']),
            ('Sphere Radius', inputs['Length'])
        ])
        intersection_point = add_switch_node(nt, 'GEOMETRY',
            add_comparison_nodes(nt, 'INT', 'GREATER_THAN',  intersect_node.outputs['Intersect Count'], 0),
            None,
            add_node(nt, 'GeometryNodePoints', [('Position', intersect_node.outputs['Intersection 1'])]).outputs['Points']
        )

        interpolate_points = add_group_node(nt, ensure_interpolate_points_node_tree, [
            ('A', sample_index(intersection_point, add_position_input_node(nt), 0)),
            ('B', line_end),
            ('Length', inputs['Length'])
        ]).outputs['Points']

        did_intersect = add_comparison_nodes(nt, 'INT', 'GREATER_THAN', add_domain_size_node(nt, 'POINTCLOUD', intersection_point, 'Point Count'), 0)

        # The points added for this edge.
        edge_points = add_switch_node(nt, 'GEOMETRY', did_intersect, None, join_geometry(nt, (intersection_point, interpolate_points)))

        # Add the new edge points after the existing ones.
        final_points = join_geometry(nt, (repeat_points, edge_points))
        nt.links.new(final_points, repeat_output_node.inputs['Geometry'])

        # Calculate the new position for the next loop iteration.
        nt.links.new(
            repeat_output_node.inputs['Position'],
            sample_index(final_points, add_position_input_node(nt), add_integer_math_operation_nodes(nt, 'SUBTRACT', [
                add_domain_size_node(nt, 'POINTCLOUD', final_points, 'Point Count'),
                1
                ]))
            )

        nt.links.new(outputs['Points'], repeat_output_node.outputs['Geometry'])

    return ensure_geometry_node_tree('BDK Curve to Equidistant Points', items, build_function)
