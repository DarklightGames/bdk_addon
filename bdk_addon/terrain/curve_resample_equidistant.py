from bpy.types import NodeTree, NodeSocket
from ..node_helpers import add_comparison_nodes, add_float_to_integer_node, add_index_node, add_switch_node, ensure_geometry_node_tree, ensure_inputs_and_outputs, add_vector_math_operation_nodes, add_separate_xyz_node, add_chained_math_nodes, add_group_node, add_math_operation_nodes, add_boolean_math_operation_nodes, add_integer_math_operation_nodes


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
        nt.links.new(outputs['Value'], add_chained_math_nodes(x, y, z))

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
        b = add_vector_math_operation_nodes(nt, 'MULTIPLY', [
            2.0,
            vector_sum(mag, add_vector_math_operation_nodes(nt, 'SUBTRACT', [
                inputs['Line Start'],
                inputs['Sphere Origin']
                ]))
            ])
        
        # C
        c = add_math_operation_nodes(nt, 'SUBTRACT', [
            add_math_operation_nodes(nt, 'SUBTRACT', [
                add_math_operation_nodes(nt, 'ADD', [length_squared(nt, inputs['Line Start'], length_squared(nt, inputs['Sphere Origin']))]),
                add_math_operation_nodes(nt, 'MULTIPLY', [
                    add_vector_math_operation_nodes(nt, 'DOT_PRODUCT', [inputs['Sphere Origin'], inputs['Line Start']]),
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
        u_dot_h = add_vector_math_operation_nodes(nt, 'DOT_PRODUCT', [u, h])

        nt.links.new(
            outputs['Value'],
            add_switch_node(nt, 'FLOAT', add_comparison_nodes(
                nt, 'FLOAT', 'GREATER', u_length_squared, inputs['Epsilon']
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
        ('INPUT', 'NodeSocketBool', 'Use A'),
        ('INPUT', 'NodeSocketBool', 'Use B'),
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

        count = nt.links.new(
            points_node.inputs['Count'],
            add_integer_math_operation_nodes(nt, 'ADD', [
                1,
                add_float_to_integer_node(nt, 'TRUNCATE', add_math_operation_nodes(nt, 'DIVIDE', [
                    add_vector_math_operation_nodes(nt, 'LENGTH', [b_sub_a], output_socket_name='Value'),
                    inputs['Length']
                ]))
            ])
            )
        
        position = nt.links.new(
            add_vector_math_operation_nodes(nt, 'ADD', [
                inputs['A'],
                add_vector_math_operation_nodes(nt, 'SCALE',
                    add_vector_math_operation_nodes(nt, 'NORMALIZE', [b_sub_a]),
                    add_math_operation_nodes(nt, 'MULTIPLY', [inputs['Length'], add_index_node(nt)])
                )])
        )

        delete_geometry_node = nt.nodes.new('GeometryNodeDeleteGeometry')
        delete_geometry_node.domain = 'POINT'
        delete_geometry_node.mode = 'ALL'

        nt.links.new(points_node.outputs['Points'], delete_geometry_node.inputs['Geometry'])
        nt.links.new(add_comparison_nodes(nt, 'INT', 'EQUAL', add_index_node(nt), 0), delete_geometry_node.inputs['Selection'])
        nt.links.new(delete_geometry_node.outputs['Geometry'], outputs['Points'])

    return ensure_geometry_node_tree('Interpolate Points', items, build_function)
