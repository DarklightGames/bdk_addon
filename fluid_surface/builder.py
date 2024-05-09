from bpy.types import NodeTree, ID, bpy_struct
from ..node_helpers import ensure_input_and_output_nodes, ensure_geometry_node_tree


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

        fluid_surface_node = node_tree.nodes.new('GeometryNodeBDKFluidSurface')
        set_material_node = node_tree.nodes.new('GeometryNodeSetMaterial')

        set_material_node.inputs[2].default_value = fluid_surface.material

        add_fluid_surface_driver(fluid_surface_node.inputs['FluidGridType'], 'fluid_grid_type')
        add_fluid_surface_driver(fluid_surface_node.inputs['FluidXSize'], 'fluid_x_size')
        add_fluid_surface_driver(fluid_surface_node.inputs['FluidYSize'], 'fluid_y_size')
        add_fluid_surface_driver(fluid_surface_node.inputs['FluidGridSpacing'], 'fluid_grid_spacing')
        add_fluid_surface_driver(fluid_surface_node.inputs['UOffset'], 'u_offset')
        add_fluid_surface_driver(fluid_surface_node.inputs['VOffset'], 'v_offset')

        # Internal
        node_tree.links.new(fluid_surface_node.outputs['Geometry'], set_material_node.inputs['Geometry'])

        # Output
        node_tree.links.new(set_material_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(fluid_surface.id, items, build_function, should_force_build=True)
