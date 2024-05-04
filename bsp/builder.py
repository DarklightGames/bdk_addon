# NOTE: This is taken more or less verbatim from the ase2t3d source, adopted for Python.
# In the future, clean this up so that it's more clear what is going on.
from ..node_helpers import ensure_input_and_output_nodes, ensure_geometry_node_tree
from ..t3d.data import Polygon
from bmesh.types import BMFace
from bpy.types import Object, Mesh, Material, NodeTree
from math import isnan
from typing import Optional, Dict, cast
import mathutils
import numpy as np


def get_level_face_data(level_object: Object) -> (np.ndarray, np.ndarray, np.ndarray, np.ndarray):
    """
    Get the origin, texture U, and texture V data for the faces of the level object.
    """
    mesh_data = cast(Mesh, level_object.data)

    polygon_count = len(mesh_data.polygons)
    origins = np.zeros(polygon_count * 3, dtype=np.float32)
    texture_us = np.zeros(polygon_count * 3, dtype=np.float32)
    texture_vs = np.zeros(polygon_count * 3, dtype=np.float32)
    material_indices = np.zeros(polygon_count, dtype=np.int32)

    mesh_data.attributes['bdk.origin'].data.foreach_get(origins)
    mesh_data.attributes['bdk.texture_u'].data.foreach_get(texture_us)
    mesh_data.attributes['bdk.texture_v'].data.foreach_get(texture_vs)
    mesh_data.attributes['material_index'].data.foreach_get(material_indices)

    # Reshape in-place.
    origins.shape = (polygon_count, 3)
    texture_us.shape = (polygon_count, 3)
    texture_vs.shape = (polygon_count, 3)

    return origins, texture_us, texture_vs, material_indices


class BrushMappingErrorType(Enum):
    BRUSH_NOT_FOUND = 0
    BRUSH_POLYGON_NOT_FOUND = 1


class BrushMappingError:
    def __init__(self, brush_index: int, error_type: BrushMappingErrorType, level_polygon_index: Optional[int] = None), brush_polygon_index: Optional[int] = None) -> None
        self.brush_index = brush_index
        self.error_type = error_type
        self.level_polygon_index = level_polygon_index
        self.brush_polygon_index = brush_polygon_index


class BrushMappingResult:
    def __init__(self):
        self.errors: List[BrushMappingError] = []

def apply_level_to_brush_mapping(level_object: Object) -> BrushMappingResult:
    result = BrushMappingResult()

    mapping = build_level_to_brush_mapping(level_object)
    origins, texture_us, texture_vs, level_material_indices = get_level_face_data(level_object)

    # Possible scenarios where this will break:
    # 1. If the brush mesh topology has changed since the mapping was created.
    # 2. If the brush has been deleted (in this case it's just a no-op).

    for brush_index, brush in enumerate(level_object.brushes):

        if brush.brush_object is None:
            # The brush object has been deleted.
            result.errors.append(BrushMappingError(brush_index, BrushMappingErrorType.BRUSH_NOT_FOUND))
            continue

        if brush_index not in mapping:
            # The brush has no polygons in the level.
            continue

        brush_mesh = cast(Mesh, brush_object.data)

        # TODO: should probably ensure that these exist.
        brush_origin_attribute = brush_mesh.attributes['bdk.origin']
        brush_texture_u_attribute = brush_mesh.attributes['bdk.texture_u']
        brush_texture_v_attribute = brush_mesh.attributes['bdk.texture_v']

        material_index_mapping = {}  # Level material index to brush material index mapping.

        # Get a set of the level material indices that are used by the polygons in this brush.
        brush_level_material_indices = set(map(lambda i: level_material_indices[i], mapping[brush_index].values()))

        # Map the material indices from the level to the brush.
        #  1. Fetch the material data block from the level material.
        #  2. Do a look-up to see if this material is already in the brush. If so, map the index.
        #  3. If not, create a new material slot in the brush, and map the index.
        for level_material_index in brush_level_material_indices:
            level_material = level_object.material_slots[level_material_index].material
            # Find the material in the brush.
            brush_material_slot_index = brush_object.material_slots.find(level_material.name)
            if brush_material_slot_index == -1:
                # The material is not in the brush, so add it.
                brush_material_slot_index = len(brush_object.material_slots)
                brush_object.material_slots.append(level_material)
            material_index_mapping[level_material_index] = brush_material_slot_index

        for brush_polygon_index, level_polygon_index in mapping[brush_index].items():
            if brush_polygon_index >= len(brush_mesh.polygons):
                # The cached brush polygon index is out of range.
                result.errors.append(
                    BrushMappingError(brush_index, BrushMappingErrorType.BRUSH_POLYGON_NOT_FOUND,
                                      level_polygon_index=level_polygon_index,
                                      brush_polygon_index=brush_polygon_index))
                continue

            origin = origins[level_polygon_index]
            texture_u = texture_us[level_polygon_index]
            texture_v = texture_vs[level_polygon_index]
            material_index = material_index_mapping[material_indices[level_polygon_index]]

            # TODO: transform the U/V/origin data from level-space to brush space
            #  (just needs to do the inverse of the BSP build code).

            # NOTE: if we want to make this stable regardless of brush transform, we need to store the original
            #  brush transform in the level object.

            brush_origin_attribute.data[brush_polygon_index].vector = origin
            brush_texture_u_attribute.data[brush_polygon_index].vector = texture_u
            brush_texture_v_attribute.data[brush_polygon_index].vector = texture_v
            brush_material_index_attribute.data[brush_polygon_index].value = material_index


def build_level_to_brush_mapping(level_object: Object) -> Dict[int, Dict[int, int]]:
    mesh_data = cast(Mesh, level_object.data)
    polygon_count = len(mesh_data.polygons)
    brush_indices = np.zeros(polygon_count, dtype=np.int32)
    brush_polygon_indices = np.zeros(polygon_count, dtype=np.int32)

    mesh_data.attributes['bdk.brush_index'].data.foreach_get(brush_indices)
    mesh_data.attributes['bdk.brush_polygon_index'].data.foreach_get(brush_polygon_indices)

    mapping: Dict[int, Dict[int, int]] = {}

    for polygon_index, (brush_index, brush_polygon_index) in enumerate(zip(brush_indices, brush_polygon_indices)):
        if brush_index not in mapping:
            mapping[brush_index] = {}
        if brush_polygon_index not in mapping[brush_index]:
            mapping[brush_index][brush_polygon_index] = polygon_index

    return mapping


def ensure_bdk_brush_uv_node_tree():

    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        texture_u_named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        texture_u_named_attribute_node.data_type = 'FLOAT_VECTOR'
        texture_u_named_attribute_node.inputs['Name'].default_value = 'bdk.texture_u'

        texture_v_named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        texture_v_named_attribute_node.data_type = 'FLOAT_VECTOR'
        texture_v_named_attribute_node.inputs['Name'].default_value = 'bdk.texture_v'

        origin_named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        origin_named_attribute_node.data_type = 'FLOAT_VECTOR'
        origin_named_attribute_node.inputs['Name'].default_value = 'bdk.origin'

        face_of_corner_node = node_tree.nodes.new(type='GeometryNodeFaceOfCorner')

        face_index_socket = face_of_corner_node.outputs['Face Index']

        evaluate_at_index_texture_u_node = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_at_index_texture_u_node.data_type = 'FLOAT_VECTOR'
        evaluate_at_index_texture_u_node.domain = 'FACE'

        evaluate_at_index_texture_v_node = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_at_index_texture_v_node.data_type = 'FLOAT_VECTOR'
        evaluate_at_index_texture_v_node.domain = 'FACE'

        evaluate_at_index_origin_node = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_at_index_origin_node.data_type = 'FLOAT_VECTOR'
        evaluate_at_index_origin_node.domain = 'FACE'

        vertex_of_corner_node = node_tree.nodes.new(type='GeometryNodeVertexOfCorner')

        evaluate_at_index_position_node = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_at_index_position_node.data_type = 'FLOAT_VECTOR'
        evaluate_at_index_position_node.domain = 'POINT'

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

        vector_math_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_math_node.operation = 'SUBTRACT'

        # This socket is the result subtracting the origin from the position, essentially the face-space position.
        vertex_position_socket = vector_math_node.outputs['Vector']

        texture_u_dot_product_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        texture_u_dot_product_node.operation = 'DOT_PRODUCT'

        texture_v_dot_product_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        texture_v_dot_product_node.operation = 'DOT_PRODUCT'

        invert_u_dot_product_node = node_tree.nodes.new(type='ShaderNodeMath')
        invert_u_dot_product_node.operation = 'MULTIPLY'
        invert_u_dot_product_node.inputs[1].default_value = -1.0

        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.domain = 'CORNER'
        store_named_attribute_node.data_type = 'FLOAT2'
        store_named_attribute_node.inputs['Name'].default_value = 'UVMap'

        texture_scale_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        texture_scale_node.operation = 'DIVIDE'

        self_object_node = node_tree.nodes.new(type='GeometryNodeSelfObject')

        object_material_size_node = node_tree.nodes.new(type='GeometryNodeBDKObjectMaterialSize')
        combine_material_size_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        subtract_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        subtract_node.operation = 'SUBTRACT'
        subtract_node.inputs[0].default_value = (0.0, 1.0, 0.0)

        evaluate_at_index_material_index_node = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
        evaluate_at_index_material_index_node.data_type = 'INT'
        evaluate_at_index_material_index_node.domain = 'FACE'

        material_index_node = node_tree.nodes.new(type='GeometryNodeInputMaterialIndex')

        # Inputs
        node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])

        # Internal
        node_tree.links.new(face_index_socket, evaluate_at_index_texture_u_node.inputs['Index'])
        node_tree.links.new(face_index_socket, evaluate_at_index_texture_v_node.inputs['Index'])
        node_tree.links.new(face_index_socket, evaluate_at_index_origin_node.inputs['Index'])
        node_tree.links.new(position_node.outputs['Position'], evaluate_at_index_position_node.inputs['Value'])
        node_tree.links.new(vertex_of_corner_node.outputs['Vertex Index'], evaluate_at_index_position_node.inputs['Index'])
        node_tree.links.new(evaluate_at_index_origin_node.outputs['Value'], vector_math_node.inputs[1])
        node_tree.links.new(evaluate_at_index_position_node.outputs['Value'], vector_math_node.inputs[0])
        node_tree.links.new(evaluate_at_index_texture_u_node.outputs['Value'], texture_u_dot_product_node.inputs[0])
        node_tree.links.new(vertex_position_socket, texture_u_dot_product_node.inputs[1])
        node_tree.links.new(evaluate_at_index_texture_v_node.outputs['Value'], texture_v_dot_product_node.inputs[0])
        node_tree.links.new(vertex_position_socket, texture_v_dot_product_node.inputs[1])
        node_tree.links.new(texture_u_dot_product_node.outputs['Value'], invert_u_dot_product_node.inputs[0])
        node_tree.links.new(invert_u_dot_product_node.outputs['Value'], combine_xyz_node.inputs['X'])
        node_tree.links.new(texture_v_dot_product_node.outputs['Value'], combine_xyz_node.inputs['Y'])
        node_tree.links.new(texture_u_named_attribute_node.outputs['Attribute'], evaluate_at_index_texture_u_node.inputs['Value'])
        node_tree.links.new(texture_v_named_attribute_node.outputs['Attribute'], evaluate_at_index_texture_v_node.inputs['Value'])
        node_tree.links.new(origin_named_attribute_node.outputs['Attribute'], evaluate_at_index_origin_node.inputs['Value'])
        node_tree.links.new(texture_scale_node.outputs['Vector'], subtract_node.inputs[1])
        node_tree.links.new(subtract_node.outputs['Vector'], store_named_attribute_node.inputs['Value'])
        node_tree.links.new(self_object_node.outputs['Self Object'], object_material_size_node.inputs['Object'])
        node_tree.links.new(object_material_size_node.outputs['U'], combine_material_size_node.inputs['X'])
        node_tree.links.new(object_material_size_node.outputs['V'], combine_material_size_node.inputs['Y'])
        node_tree.links.new(combine_xyz_node.outputs['Vector'], texture_scale_node.inputs[0])
        node_tree.links.new(combine_material_size_node.outputs['Vector'], texture_scale_node.inputs[1])
        node_tree.links.new(evaluate_at_index_material_index_node.outputs['Value'], object_material_size_node.inputs['Material Index'])
        node_tree.links.new(face_of_corner_node.outputs['Face Index'], evaluate_at_index_material_index_node.inputs['Index'])
        node_tree.links.new(material_index_node.outputs['Material Index'], evaluate_at_index_material_index_node.inputs['Value'])

        # Output
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Brush UV', items, build_function)


# TODO: We can use this, or something like it, when we to create a brush from an existing mesh that doesn't have the BDK
#  brush attributes. It's logic may even be able to be converted to a geonode operator.
def create_bsp_brush_polygon(material: Optional[Material], uv_layer, face: BMFace, transform_matrix) -> Polygon:
    texture_coordinates = [loop[uv_layer].uv for loop in face.loops[0:3]]

    texture_width = material.bdk.size_x if material else 512
    texture_height = material.bdk.size_y if material else 512

    u_tiling = 1
    v_tiling = 1
    u_offset = 0
    v_offset = 0

    scale_u_offset = -0.5 - (u_tiling / 2.0)
    scale_v_offset = -0.5 - (v_tiling / 2.0)

    # Texture Coordinates
    s0 = texture_coordinates[0][0]
    t0 = texture_coordinates[0][1]

    s1 = texture_coordinates[1][0]
    t1 = texture_coordinates[1][1]

    s2 = texture_coordinates[2][0]
    t2 = texture_coordinates[2][1]

    s0 *= u_tiling
    s1 *= u_tiling
    s2 *= u_tiling

    t0 *= v_tiling
    t1 *= v_tiling
    t2 *= v_tiling

    # Scale
    s0 = (-u_offset * u_tiling) + scale_u_offset + s0
    s1 = (-u_offset * u_tiling) + scale_u_offset + s1
    s2 = (-u_offset * u_tiling) + scale_u_offset + s2

    #
    t0 = -((-v_offset * v_tiling) + scale_v_offset + t0 - 1.0)
    t1 = -((-v_offset * v_tiling) + scale_v_offset + t1 - 1.0)
    t2 = -((-v_offset * v_tiling) + scale_v_offset + t2 - 1.0)

    # Translate so that coord one is minimum possible
    u_translate = float(int(s0))
    v_translate = float(int(t0))

    s0 -= u_translate
    s1 -= u_translate
    s2 -= u_translate

    t0 -= v_translate
    t1 -= v_translate
    t2 -= v_translate

    # Flip the Y axis
    vertices = [transform_matrix @ mathutils.Vector(vert.co) for vert in face.verts]
    for vert in vertices:
        vert[1] = -vert[1]
    vertices.reverse()

    # Coordinates
    pt0, pt1, pt2 = vertices[0:3]

    dpt1 = np.subtract(pt1, pt0)
    dpt2 = np.subtract(pt2, pt0)

    dv1 = np.array((s1 - s0, t1 - t0, 0.0))
    dv2 = np.array((s2 - s0, t2 - t0, 0.0))

    # Compute the 2D matrix values, and invert the matrix.
    dpt11 = np.dot(dpt1, dpt1)
    dpt12 = np.dot(dpt1, dpt2)
    dpt22 = np.dot(dpt2, dpt2)

    factor = 1.0 / np.subtract(dpt11 * dpt22, dpt12 * dpt12)

    # Compute the two gradients.
    g1 = np.subtract((dv1 * dpt22), (dv2 * dpt12)) * factor
    g2 = np.subtract((dv2 * dpt11), (dv1 * dpt12)) * factor

    p_grad_u = (dpt1 * g1[0]) + (dpt2 * g2[0])
    p_grad_v = (dpt1 * g1[1]) + (dpt2 * g2[1])

    # Repeat process above, computing just one vector in the plane.
    dup1: float = np.dot(dpt1, p_grad_u)
    dup2: float = np.dot(dpt2, p_grad_u)
    dvp1: float = np.dot(dpt1, p_grad_v)
    dvp2: float = np.dot(dpt2, p_grad_v)

    # Impossible values may occur here, and cause divide by zero problems.
    # Handle these by setting the divisor to a safe value then flagging
    # that it is impossible. Impossible textured polygons use the normal
    # to the polygon, which makes no texture appear.
    minimum_divisor = 0.00000000001  # change to epsilon
    divisor = dup1 * dvp2 - dvp1 * dup2
    impossible1 = abs(divisor) <= minimum_divisor

    if impossible1:
        divisor = 1.0

    fuctor = 1.0 / divisor
    b1 = (s0 * dvp2 - t0 * dup2) * fuctor
    b2 = (t0 * dup1 - s0 * dvp1) * fuctor

    p_base = np.subtract(pt0, (dpt1 * b1) + (dpt2 * b2))
    p_grad_u *= texture_width
    p_grad_v *= texture_height

    # Check for error values
    impossible2 = isnan(p_base[0]) or isnan(p_base[1]) or isnan(p_base[2]) \
                  or isnan(p_grad_u[0]) or isnan(p_grad_u[1]) or isnan(p_grad_u[2]) \
                  or isnan(p_grad_v[0]) or isnan(p_grad_v[1]) or isnan(p_grad_v[2])

    impossible = impossible1 or impossible2

    origin = pt1 if impossible else p_base
    texture_u = p_grad_u
    texture_v = p_grad_v

    return origin, texture_u, texture_v
