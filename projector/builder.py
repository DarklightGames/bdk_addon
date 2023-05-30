import bpy
import uuid

from bpy.types import NodeTree


def build_projector_node_tree() -> NodeTree:
    node_tree = bpy.data.node_groups.new(name=uuid.uuid4().hex, type="GeometryNodeTree")
    node_tree.inputs.clear()

    node_tree.inputs.new("NodeSocketObject", "Target")
    node_tree.inputs.new("NodeSocketFloatDistance", "MaxTraceDistance")
    node_tree.inputs.new("NodeSocketFloat", "FOV")
    node_tree.inputs.new("NodeSocketFloat", "DrawScale")
    node_tree.inputs.new("NodeSocketMaterial", "ProjTexture")
    node_tree.inputs.new("NodeSocketInt", "USize")
    node_tree.inputs.new("NodeSocketInt", "VSize")
    node_tree.outputs.new("NodeSocketGeometry", "Geometry")

    node_tree.inputs["DrawScale"].default_value = 1.0
    node_tree.inputs["MaxTraceDistance"].default_value = 1024.0
    node_tree.inputs["FOV"].default_value = 90.0

    input_node = node_tree.nodes.new(type="NodeGroupInput")

    # object_info_node = node_tree.nodes.new(type="GeometryNodeObjectInfo")
    projector_node = node_tree.nodes.new(type="GeometryNodeBDKProjector")
    set_material_node = node_tree.nodes.new(type="GeometryNodeSetMaterial")
    output_node = node_tree.nodes.new(type="NodeGroupOutput")
    join_geometry_node = node_tree.nodes.new(type="GeometryNodeJoinGeometry")
    # transform_geometry_node = node_tree.nodes.new(type="GeometryNodeTransform")

    store_named_attribute_node = node_tree.nodes.new(type="GeometryNodeStoreNamedAttribute")
    store_named_attribute_node.data_type = 'FLOAT2'
    store_named_attribute_node.domain = 'CORNER'
    store_named_attribute_node.inputs["Name"].default_value = "UVMap"

    # Add a "To Radians" node to convert the FOV value from degrees to radians.
    to_radians_node = node_tree.nodes.new(type="ShaderNodeMath")
    to_radians_node.operation = "RADIANS"

    node_tree.links.new(input_node.outputs["FOV"], to_radians_node.inputs[0])

    # Connect theo "To Radians" node to the projector node's "FOV" input.
    node_tree.links.new(to_radians_node.outputs["Value"], projector_node.inputs["FOV"])

    # Note that the self node is only here so that the geometry is recalculated when the projector object is moved.
    node_tree.nodes.new(type="GeometryNodeSelfObject")

    node_tree.links.new(input_node.outputs["Target"], projector_node.inputs['Target'])

    # node_tree.links.new(object_info_node.outputs["Location"], transform_geometry_node.inputs["Translation"])
    # node_tree.links.new(object_info_node.outputs["Rotation"], transform_geometry_node.inputs["Rotation"])
    # node_tree.links.new(object_info_node.outputs["Scale"], transform_geometry_node.inputs["Scale"])
    # node_tree.links.new(object_info_node.outputs["Geometry"], transform_geometry_node.inputs["Geometry"])

    # node_tree.links.new(transform_geometry_node.outputs["Geometry"], projector_node.inputs["Target"])

    node_tree.links.new(projector_node.outputs["Geometry"], store_named_attribute_node.inputs["Geometry"])
    node_tree.links.new(projector_node.outputs["UV Map"], store_named_attribute_node.inputs["Value"])
    node_tree.links.new(store_named_attribute_node.outputs["Geometry"], set_material_node.inputs["Geometry"])

    node_tree.links.new(set_material_node.outputs["Geometry"], join_geometry_node.inputs["Geometry"])
    node_tree.links.new(projector_node.outputs["Frustum"], join_geometry_node.inputs["Geometry"])
    node_tree.links.new(join_geometry_node.outputs["Geometry"], output_node.inputs["Geometry"])

    node_tree.links.new(input_node.outputs["ProjTexture"], set_material_node.inputs[2])
    node_tree.links.new(input_node.outputs["MaxTraceDistance"], projector_node.inputs["MaxTraceDistance"])
    node_tree.links.new(input_node.outputs["DrawScale"], projector_node.inputs["DrawScale"])

    node_tree.links.new(input_node.outputs["USize"], projector_node.inputs["USize"])
    node_tree.links.new(input_node.outputs["VSize"], projector_node.inputs["VSize"])

    return node_tree
