from bpy.types import NodeTree

from ..node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes


def ensure_projector_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketObject', 'Target'),
        ('INPUT', 'NodeSocketFloat', 'MaxTraceDistance'),
        ('INPUT', 'NodeSocketFloat', 'FOV'),
        ('INPUT', 'NodeSocketFloat', 'DrawScale'),
        ('INPUT', 'NodeSocketMaterial', 'ProjTexture'),
        ('INPUT', 'NodeSocketInt', 'USize'),
        ('INPUT', 'NodeSocketInt', 'VSize'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        projector_node = node_tree.nodes.new(type='GeometryNodeBDKProjector')
        set_material_node = node_tree.nodes.new(type='GeometryNodeSetMaterial')
        output_node = node_tree.nodes.new(type='NodeGroupOutput')
        join_geometry_node = node_tree.nodes.new(type='GeometryNodeJoinGeometry')

        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'FLOAT2'
        store_named_attribute_node.domain = 'CORNER'
        store_named_attribute_node.inputs['Name'].default_value = 'UVMap'

        # Add a 'To Radians' node to convert the FOV value from degrees to radians.
        to_radians_node = node_tree.nodes.new(type='ShaderNodeMath')
        to_radians_node.operation = 'RADIANS'

        # Note that the self node is only here so that the geometry is recalculated when the projector object is moved.
        _self_node = node_tree.nodes.new(type='GeometryNodeSelfObject')

        # Input
        node_tree.links.new(input_node.outputs['FOV'], to_radians_node.inputs[0])
        node_tree.links.new(input_node.outputs['Target'], projector_node.inputs['Target'])
        node_tree.links.new(input_node.outputs['ProjTexture'], set_material_node.inputs[2])
        node_tree.links.new(input_node.outputs['MaxTraceDistance'], projector_node.inputs['MaxTraceDistance'])
        node_tree.links.new(input_node.outputs['DrawScale'], projector_node.inputs['DrawScale'])
        node_tree.links.new(input_node.outputs['USize'], projector_node.inputs['USize'])
        node_tree.links.new(input_node.outputs['VSize'], projector_node.inputs['VSize'])

        # Internal
        node_tree.links.new(to_radians_node.outputs['Value'], projector_node.inputs['FOV'])
        node_tree.links.new(projector_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
        node_tree.links.new(projector_node.outputs['UV Map'], store_named_attribute_node.inputs['Value'])
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], set_material_node.inputs['Geometry'])
        node_tree.links.new(set_material_node.outputs['Geometry'], join_geometry_node.inputs['Geometry'])
        node_tree.links.new(projector_node.outputs['Frustum'], join_geometry_node.inputs['Geometry'])

        # Output
        node_tree.links.new(join_geometry_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Projector', items, build_function)
