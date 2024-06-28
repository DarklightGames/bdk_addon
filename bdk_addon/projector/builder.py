from bpy.types import NodeTree

from ..node_helpers import ensure_geometry_node_tree, ensure_input_and_output_nodes


def ensure_projector_uv_scale_node_tree() -> NodeTree:
    # TODO: Once we confirm that this is correct and stable, move it to the native code so we don't have to maintain it
    #  here.
    items = (
        ('INPUT', 'NodeSocketMaterial', 'ProjTexture'),
        ('INPUT', 'NodeSocketVector', 'UV Map'),
        ('OUTPUT', 'NodeSocketVector', 'UV Map'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        material_size_node = node_tree.nodes.new(type='GeometryNodeBDKMaterialSize')

        divide_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        divide_node.operation = 'DIVIDE'

        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        vu_ratio_node = node_tree.nodes.new(type='ShaderNodeMath')
        vu_ratio_node.operation = 'DIVIDE'
        vu_ratio_node.use_clamp = True
        vu_ratio_node.label = 'VU Ratio'

        uv_ratio_node = node_tree.nodes.new(type='ShaderNodeMath')
        uv_ratio_node.operation = 'DIVIDE'
        uv_ratio_node.use_clamp = True
        uv_ratio_node.label = 'UV Ratio'

        subtract_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        subtract_node.operation = 'SUBTRACT'

        v_compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        v_compare_node.operation = 'NOT_EQUAL'
        v_compare_node.inputs['B'].default_value = 1.0

        v_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        v_switch_node.input_type = 'FLOAT'
        v_switch_node.inputs['True'].default_value = 0.5
        v_switch_node.label = 'V Switch'

        u_compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        u_compare_node.operation = 'NOT_EQUAL'
        u_compare_node.inputs['B'].default_value = 1.0

        u_switch_node_ = node_tree.nodes.new(type='GeometryNodeSwitch')
        u_switch_node_.input_type = 'FLOAT'
        u_switch_node_.inputs['True'].default_value = 0.5
        u_switch_node_.label = 'U Switch'

        combine_xyz_node_1 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        # Input
        node_tree.links.new(input_node.outputs['ProjTexture'], material_size_node.inputs['Material'])
        node_tree.links.new(input_node.outputs['UV Map'], divide_node.inputs[0])

        # Internal
        node_tree.links.new(u_compare_node.outputs['Result'], u_switch_node_.inputs['Switch'])
        node_tree.links.new(vu_ratio_node.outputs['Value'], combine_xyz_node.inputs['Y'])
        node_tree.links.new(vu_ratio_node.outputs['Value'], v_compare_node.inputs['A'])
        node_tree.links.new(uv_ratio_node.outputs['Value'], combine_xyz_node.inputs['X'])
        node_tree.links.new(uv_ratio_node.outputs['Value'], u_compare_node.inputs['A'])
        node_tree.links.new(u_switch_node_.outputs['Output'], combine_xyz_node_1.inputs['X'])
        node_tree.links.new(v_compare_node.outputs['Result'], v_switch_node.inputs['Switch'])
        node_tree.links.new(combine_xyz_node_1.outputs['Vector'], subtract_node.inputs[1])
        node_tree.links.new(divide_node.outputs['Vector'], subtract_node.inputs[0])
        node_tree.links.new(v_switch_node.outputs['Output'], combine_xyz_node_1.inputs['Y'])
        node_tree.links.new(combine_xyz_node.outputs['Vector'], divide_node.inputs[1])
        node_tree.links.new(material_size_node.outputs['U'], vu_ratio_node.inputs[1])
        node_tree.links.new(material_size_node.outputs['V'], vu_ratio_node.inputs[0])
        node_tree.links.new(material_size_node.outputs['U'], uv_ratio_node.inputs[0])
        node_tree.links.new(material_size_node.outputs['V'], uv_ratio_node.inputs[1])

        # Output
        node_tree.links.new(subtract_node.outputs['Vector'], output_node.inputs['UV Map'])  # Vector -> Vector

    return ensure_geometry_node_tree('BDK Projector UV Scale', items, build_function)



def ensure_projector_node_tree() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketObject', 'Target'),
        ('INPUT', 'NodeSocketFloat', 'MaxTraceDistance'),
        ('INPUT', 'NodeSocketFloat', 'FOV'),
        ('INPUT', 'NodeSocketFloat', 'DrawScale'),
        ('INPUT', 'NodeSocketMaterial', 'ProjTexture'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        projector_node = node_tree.nodes.new(type='GeometryNodeBDKProjector')
        set_material_node = node_tree.nodes.new(type='GeometryNodeSetMaterial')
        join_geometry_node = node_tree.nodes.new(type='GeometryNodeJoinGeometry')

        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'FLOAT2'
        store_named_attribute_node.domain = 'CORNER'
        store_named_attribute_node.inputs['Name'].default_value = 'UVMap'

        scale_uv_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        scale_uv_group_node.node_tree = ensure_projector_uv_scale_node_tree()

        material_size_node = node_tree.nodes.new(type='GeometryNodeBDKMaterialSize')

        bake_node = node_tree.nodes.new(type='GeometryNodeBake')

        # Note that the self node is only here so that the geometry is recalculated when the projector object is moved.
        _self_node = node_tree.nodes.new(type='GeometryNodeSelfObject')

        # Input
        node_tree.links.new(input_node.outputs['FOV'], projector_node.inputs['FOV'])
        node_tree.links.new(input_node.outputs['Target'], projector_node.inputs['Target'])
        node_tree.links.new(input_node.outputs['ProjTexture'], material_size_node.inputs['Material'])
        node_tree.links.new(input_node.outputs['ProjTexture'], set_material_node.inputs['Material'])
        node_tree.links.new(input_node.outputs['MaxTraceDistance'], projector_node.inputs['MaxTraceDistance'])
        node_tree.links.new(input_node.outputs['DrawScale'], projector_node.inputs['DrawScale'])
        node_tree.links.new(input_node.outputs['ProjTexture'], scale_uv_group_node.inputs['ProjTexture'])

        # Internal
        node_tree.links.new(set_material_node.outputs['Geometry'], bake_node.inputs['Geometry'])
        node_tree.links.new(projector_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
        node_tree.links.new(scale_uv_group_node.outputs['UV Map'], store_named_attribute_node.inputs['Value'])
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], set_material_node.inputs['Geometry'])
        node_tree.links.new(bake_node.outputs['Geometry'], join_geometry_node.inputs['Geometry'])
        node_tree.links.new(projector_node.outputs['Frustum'], join_geometry_node.inputs['Geometry'])
        node_tree.links.new(material_size_node.outputs['U'], projector_node.inputs['USize'])
        node_tree.links.new(material_size_node.outputs['V'], projector_node.inputs['VSize'])
        node_tree.links.new(projector_node.outputs['UV Map'], scale_uv_group_node.inputs['UV Map'])

        # Output
        node_tree.links.new(join_geometry_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Projector', items, build_function)
