from bpy.types import NodeTree, ID, bpy_struct
from ..node_helpers import add_combine_xyz_node, add_comparison_nodes, add_index_node, ensure_input_and_output_nodes, ensure_geometry_node_tree, add_integer_math_operation_nodes, add_math_operation_nodes


def ensure_bdk_fluid_surface_square_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInt', 'Size X'),
        ('INPUT', 'NodeSocketInt', 'Size Y'),
        ('INPUT', 'NodeSocketFloat', 'Grid Spacing'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry')
    )
    
    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        grid_node = node_tree.nodes.new('GeometryNodeMeshGrid')
        size_x_socket = add_math_operation_nodes(node_tree, 'MULTIPLY',
            (add_integer_math_operation_nodes(node_tree, 'SUBTRACT', 
                                      (input_node.outputs['Size X'], 1)), input_node.outputs['Grid Spacing']))
        size_y_socket = add_math_operation_nodes(node_tree, 'MULTIPLY',
            (add_integer_math_operation_nodes(node_tree, 'SUBTRACT', 
                                      (input_node.outputs['Size Y'], 1)), input_node.outputs['Grid Spacing']))
    
        node_tree.links.new(size_x_socket, grid_node.inputs['Size X'])
        node_tree.links.new(size_y_socket, grid_node.inputs['Size Y'])
        node_tree.links.new(input_node.outputs['Size X'], grid_node.inputs['Vertices X'])
        node_tree.links.new(input_node.outputs['Size Y'], grid_node.inputs['Vertices Y'])
        node_tree.links.new(grid_node.outputs['Mesh'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Fluid Surface Square', items, build_function)


def ensure_bdk_fluid_surface_hexagonal_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInt', 'Size X'),
        ('INPUT', 'NodeSocketInt', 'Size Y'),
        ('INPUT', 'NodeSocketFloat', 'Grid Spacing'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry')
    )
    
    def build_function(nt: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(nt)

        triangulate_node = nt.nodes.new('GeometryNodeTriangulate')
        triangulate_node.quad_method = 'SHORTEST_DIAGONAL'
        triangulate_node.ngon_method = 'CLIP'

        set_position_node = nt.nodes.new('GeometryNodeSetPosition')

        # Offset
        nt.links.new(set_position_node.inputs['Offset'],
                            add_combine_xyz_node(nt, x_socket=add_math_operation_nodes(nt, 'MULTIPLY', (input_node.outputs['Grid Spacing'], 0.5))))

        # Selection
        nt.links.new(set_position_node.inputs['Selection'],
                        add_comparison_nodes(nt, 'INT', 'EQUAL',
                                             a=add_integer_math_operation_nodes(nt, 'MODULO', 
                                                                                (add_integer_math_operation_nodes(nt, 'FLOORED_MODULO', 
                                                                                                                  (add_index_node(nt), input_node.outputs['Size Y'])), 2)),
                                             b=add_integer_math_operation_nodes(nt, 'MODULO', 
                                                                                (input_node.outputs['Size Y'], 2))
                                             ))
    
        # Grid
        ROOT_3_OVER_2 = 0.866025404
        grid_node = nt.nodes.new('GeometryNodeMeshGrid')
        size_x_socket = add_math_operation_nodes(nt, 'MULTIPLY',
            (add_integer_math_operation_nodes(nt, 'SUBTRACT', 
            (input_node.outputs['Size X'], 1)), input_node.outputs['Grid Spacing']))
        size_y_socket = add_math_operation_nodes(nt, 'MULTIPLY',
            (add_integer_math_operation_nodes(nt, 'SUBTRACT', 
                                      (input_node.outputs['Size Y'], 1)), add_math_operation_nodes(nt, 'MULTIPLY', (input_node.outputs['Grid Spacing'], ROOT_3_OVER_2))))
    
        nt.links.new(size_x_socket, grid_node.inputs['Size X'])
        nt.links.new(size_y_socket, grid_node.inputs['Size Y'])
        nt.links.new(input_node.outputs['Size X'], grid_node.inputs['Vertices X'])
        nt.links.new(input_node.outputs['Size Y'], grid_node.inputs['Vertices Y'])
        nt.links.new(grid_node.outputs['Mesh'], output_node.inputs['Geometry'])

        # Finalize
        nt.links.new(grid_node.outputs['Mesh'], set_position_node.inputs['Geometry'])
        nt.links.new(set_position_node.outputs['Geometry'], triangulate_node.inputs['Mesh'])
        nt.links.new(triangulate_node.outputs['Mesh'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Fluid Surface Hexagonal', items, build_function)


def ensure_bdk_fluid_surface_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketMenu', 'Grid Type'),
        ('INPUT', 'NodeSocketInt', 'Size X'),
        ('INPUT', 'NodeSocketInt', 'Size Y'),
        ('INPUT', 'NodeSocketFloat', 'Grid Spacing'),
        ('INPUT', 'NodeSocketFloat', 'U Offset'),
        ('INPUT', 'NodeSocketFloat', 'V Offset'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry')
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        # Nodes
        grid_type_switch_node = node_tree.nodes.new(type='GeometryNodeMenuSwitch')
        grid_type_switch_node.data_type = 'GEOMETRY'
        grid_type_switch_node.enum_items.clear()
        grid_type_switch_node.enum_items.new('Square')
        grid_type_switch_node.enum_items.new('Hexagonal')

        square_node = node_tree.nodes.new(type='GeometryNodeGroup')
        square_node.node_tree = ensure_bdk_fluid_surface_square_node_tree()
        
        hexagonal_node = node_tree.nodes.new(type='GeometryNodeGroup')
        hexagonal_node.node_tree = ensure_bdk_fluid_surface_hexagonal_node_tree()

        type_nodes = {
            'Square': square_node,
            'Hexagonal': hexagonal_node
        }

        node_tree.links.new(input_node.outputs['Grid Type'], grid_type_switch_node.inputs['Menu'])
        
        for menu_switch_input, type_node in type_nodes.items():
            # Links
            node_tree.links.new(input_node.outputs['Size X'], type_node.inputs['Size X'])
            node_tree.links.new(input_node.outputs['Size Y'], type_node.inputs['Size Y'])
            node_tree.links.new(input_node.outputs['Grid Spacing'], type_node.inputs['Grid Spacing'])
            node_tree.links.new(type_node.outputs['Geometry'], grid_type_switch_node.inputs[menu_switch_input])
        
        node_tree.links.new(grid_type_switch_node.outputs['Output'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Fluid Surface', items, build_function)


def _add_fluid_surface_driver_ex(
        struct: bpy_struct,
        target_id: ID,
        data_path: str,
        index: int = -1,
        path: str = 'default_value'):
    driver = struct.driver_add(path, index).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = target_id
    data_path = f"bdk.fluid_surface.{data_path}"
    if index != -1:
        data_path += f"[{index}]"
    var.targets[0].data_path = data_path


def ensure_fluid_surface_node_tree(fluid_surface: 'BDK_PG_fluid_surface') -> NodeTree:
    items = (
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def add_fluid_surface_driver(struct: bpy_struct, data_path: str, index: int = -1):
        _add_fluid_surface_driver_ex(struct, fluid_surface.object, data_path, index, 'default_value')

    def build_function(node_tree: NodeTree):
        _, output_node = ensure_input_and_output_nodes(node_tree)

        fluid_surface_node = node_tree.nodes.new('GeometryNodeGroup')
        fluid_surface_node.node_tree = ensure_bdk_fluid_surface_node_tree()
        
        set_material_node = node_tree.nodes.new('GeometryNodeSetMaterial')

        set_material_node.inputs['Material'].default_value = fluid_surface.material

        index_switch_node = node_tree.nodes.new('GeometryNodeIndexSwitch')
        index_switch_node.data_type = 'MENU'
        node_tree.links.new(index_switch_node.outputs['Output'], fluid_surface_node.inputs['Grid Type'])
        index_switch_node.inputs[1].default_value = 'Square'
        index_switch_node.inputs[2].default_value = 'Hexagonal'

        add_fluid_surface_driver(index_switch_node.inputs['Index'], 'fluid_grid_type')
        add_fluid_surface_driver(fluid_surface_node.inputs['Size X'], 'fluid_x_size')
        add_fluid_surface_driver(fluid_surface_node.inputs['Size Y'], 'fluid_y_size')
        add_fluid_surface_driver(fluid_surface_node.inputs['Grid Spacing'], 'fluid_grid_spacing')
        add_fluid_surface_driver(fluid_surface_node.inputs['U Offset'], 'u_offset')
        add_fluid_surface_driver(fluid_surface_node.inputs['V Offset'], 'v_offset')

        # Internal
        node_tree.links.new(fluid_surface_node.outputs['Geometry'], set_material_node.inputs['Geometry'])

        # Output
        node_tree.links.new(set_material_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(fluid_surface.id, items, build_function, should_force_build=True)
