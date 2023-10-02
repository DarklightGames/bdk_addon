from bpy.types import NodeTree, bpy_struct, ID, NodeSocket
from ..node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes, add_simulation_input_and_output_nodes
from .properties import BDK_PG_particle_system, BDK_PG_particle_emitter


def ensure_particle_system_emitter_indices(particle_system: BDK_PG_particle_system):
    """
    Ensures that the indices of the particle emitters are correct.
    """
    for index, particle_emitter in enumerate(particle_system.emitters):
        particle_emitter.index = index


def ensure_particle_system_node_tree(particle_system: BDK_PG_particle_system) -> NodeTree:
    items = {
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    ensure_particle_system_emitter_indices(particle_system)

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        join_geometry_node = node_tree.nodes.new('GeometryNodeJoinGeometry')

        for particle_emitter in particle_system.emitters:
            particle_system_node_group_node = node_tree.nodes.new('GeometryNodeGroup')
            particle_system_node_group_node.node_tree = ensure_particle_emitter_node_tree(particle_system, particle_emitter)

            node_tree.links.new(particle_system_node_group_node.outputs['Geometry'], join_geometry_node.inputs['Geometry'])

        node_tree.links.new(join_geometry_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(particle_system.id, items, build_function, should_force_build=True)


def _add_particle_emitter_driver(struct: bpy_struct, struct_path: str, target_id: ID, particle_emitter_index: int, particle_emitter_path: str, struct_index: int = None, particle_emitter_path_index: int = None):
    fcurve = struct.driver_add(struct_path, struct_index) if struct_index is not None else struct.driver_add(struct_path)
    fcurve.driver.type = 'AVERAGE'
    variable = fcurve.driver.variables.new()
    variable.type = 'SINGLE_PROP'
    target = variable.targets[0]
    target.id_type = 'OBJECT'
    target.id = target_id

    if struct_index is not None:
        target.data_path = f'bdk.particle_system.emitters[{particle_emitter_index}].{particle_emitter_path}[{particle_emitter_path_index}]'
    else:
        target.data_path = f'bdk.particle_system.emitters[{particle_emitter_index}].{particle_emitter_path}'

def ensure_particle_emitter_node_tree(particle_system: BDK_PG_particle_system, particle_emitter: BDK_PG_particle_emitter) -> NodeTree:
    items = {
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def add_particle_emitter_driver(struct: bpy_struct, particle_emitter_path: str, struct_path: str = 'default_value', particle_emitter_path_index: int = None, struct_index: int = None):
        """
        Convenience function for adding a driver to a particle emitter property.
        """
        _add_particle_emitter_driver(struct,
                                     struct_path,
                                     particle_system.object,
                                     particle_emitter_index=particle_emitter.index,
                                     particle_emitter_path=particle_emitter_path,
                                     struct_index=struct_index,
                                     particle_emitter_path_index=particle_emitter_path_index)


    def add_driven_vector_node(node_tree: NodeTree, particle_emitter_path: str, label: str) -> NodeSocket:
        vector_node = node_tree.nodes.new('FunctionNodeInputVector')
        vector_node.label = label
        add_particle_emitter_driver(vector_node, particle_emitter_path, 'vector', 0, 0)
        add_particle_emitter_driver(vector_node, particle_emitter_path, 'vector', 1, 1)
        add_particle_emitter_driver(vector_node, particle_emitter_path, 'vector', 2, 2)
        return vector_node.outputs['Vector']


    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        points_node = node_tree.nodes.new('GeometryNodePoints')

        # TODO: loads more here to set up the state for the particles.

        geometry_socket = points_node.outputs['Geometry']

        add_particle_emitter_driver(points_node.inputs['Count'], 'max_particles')

        simulation_input_node, simulation_output_node = add_simulation_input_and_output_nodes(node_tree)

        start_location_offset_socket = add_driven_vector_node(node_tree, 'start_location_offset', 'Start Location Offset')

        # Box
        start_location_range_min_socket = add_driven_vector_node(node_tree, 'start_location_range.min', 'Start Location Range Min')
        start_location_range_max_socket = add_driven_vector_node(node_tree, 'start_location_range.max', 'Start Location Range Max')

        # Sphere
        pass

        # Polar
        pass

        random_value_node = node_tree.nodes.new('GeometryNodeRandomValue')
        random_value_node.label = 'Start Location Random Value'

        node_tree.links.new(geometry_socket, simulation_input_node.inputs['Geometry'])
        node_tree.links.new(simulation_output_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(particle_emitter.id, items, build_function, should_force_build=True)
