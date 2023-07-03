import bpy
from bpy.types import NodeTree
from ..helpers import ensure_input_and_output_nodes


def create_fluid_surface_node_tree() -> NodeTree:
    node_tree = bpy.data.node_groups.new('FluidSurface', 'GeometryNodeTree')

    node_tree.inputs.new('NodeSocketFloat', 'FluidGridSpacing')
    node_tree.inputs.new('NodeSocketFloat', 'UOffset')
    node_tree.inputs.new('NodeSocketFloat', 'VOffset')
    node_tree.inputs.new('NodeSocketInt', 'FluidXSize')
    node_tree.inputs.new('NodeSocketInt', 'FluidYSize')

    node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    fluid_surface_node = node_tree.nodes.new('GeometryNodeBDKFluidSurface')

    # Hook up the inputs to the fluid surface node.
    node_tree.links.new(input_node.outputs['FluidGridSpacing'], fluid_surface_node.inputs['FluidGridSpacing'])
    node_tree.links.new(input_node.outputs['UOffset'], fluid_surface_node.inputs['UOffset'])
    node_tree.links.new(input_node.outputs['VOffset'], fluid_surface_node.inputs['VOffset'])
    node_tree.links.new(input_node.outputs['FluidXSize'], fluid_surface_node.inputs['FluidXSize'])
    node_tree.links.new(input_node.outputs['FluidYSize'], fluid_surface_node.inputs['FluidYSize'])

    node_tree.links.new(fluid_surface_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return node_tree
