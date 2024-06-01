# NOTE: This is taken more or less verbatim from the ase2t3d source, adopted for Python.
# In the future, clean this up so that it's more clear what is going on.

import time
import uuid
from enum import Enum

from .properties import poly_flags_items
from ..node_helpers import ensure_input_and_output_nodes, ensure_geometry_node_tree, add_chained_bitwise_operation_nodes
from mathutils import Vector, Quaternion
from bmesh.types import BMFace
from bpy.types import Object, Mesh, NodeTree, bpy_struct
from math import isnan
from typing import Optional, Dict, cast, List
import mathutils
import numpy as np

ORIGIN_ATTRIBUTE_NAME = 'bdk.origin'
TEXTURE_U_ATTRIBUTE_NAME = 'bdk.texture_u'
TEXTURE_V_ATTRIBUTE_NAME = 'bdk.texture_v'
POLY_FLAGS_ATTRIBUTE_NAME = 'bdk.poly_flags'
MATERIAL_SLOT_ATTRIBUTE_NAME = 'material_index'
BRUSH_INDEX_ATTRIBUTE_NAME = 'bdk.brush_index'
BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME = 'bdk.brush_polygon_index'


def _ensure_bsp_surface_attributes(mesh_data: Mesh):
    attributes = (
        (ORIGIN_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE'),
        (TEXTURE_U_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE'),
        (TEXTURE_V_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE'),
        (POLY_FLAGS_ATTRIBUTE_NAME, 'INT', 'FACE'),
        (MATERIAL_SLOT_ATTRIBUTE_NAME, 'INT', 'FACE'),
    )

    for (name, type_, domain) in attributes:
        if name not in mesh_data.attributes:
            mesh_data.attributes.new(name, type_, domain)


def get_level_face_data(level_object: Object) -> (np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray):
    """
    Get the origin, texture U, and texture V data for the faces of the level object.
    """
    mesh_data = cast(Mesh, level_object.data)

    polygon_count = len(mesh_data.polygons)
    origins = np.zeros(polygon_count * 3, dtype=np.float32)
    texture_us = np.zeros(polygon_count * 3, dtype=np.float32)
    texture_vs = np.zeros(polygon_count * 3, dtype=np.float32)
    poly_flags = np.zeros(polygon_count, dtype=np.int32)
    material_indices = np.zeros(polygon_count, dtype=np.int32)

    if ORIGIN_ATTRIBUTE_NAME in mesh_data.attributes:
        mesh_data.attributes[ORIGIN_ATTRIBUTE_NAME].data.foreach_get('vector', origins)

    if TEXTURE_U_ATTRIBUTE_NAME in mesh_data.attributes:
        mesh_data.attributes[TEXTURE_U_ATTRIBUTE_NAME].data.foreach_get('vector', texture_us)

    if TEXTURE_V_ATTRIBUTE_NAME in mesh_data.attributes:
        mesh_data.attributes[TEXTURE_V_ATTRIBUTE_NAME].data.foreach_get('vector', texture_vs)

    if POLY_FLAGS_ATTRIBUTE_NAME in mesh_data.attributes:
        mesh_data.attributes[POLY_FLAGS_ATTRIBUTE_NAME].data.foreach_get('value', poly_flags)

    if MATERIAL_SLOT_ATTRIBUTE_NAME in mesh_data.attributes:
        mesh_data.attributes[MATERIAL_SLOT_ATTRIBUTE_NAME].data.foreach_get('value', material_indices)

    # Reshape in-place.
    origins.shape = (polygon_count, 3)
    texture_us.shape = (polygon_count, 3)
    texture_vs.shape = (polygon_count, 3)

    return origins, texture_us, texture_vs, material_indices, poly_flags


class BrushMappingErrorType(Enum):
    BRUSH_NOT_FOUND = 0
    BRUSH_POLYGON_NOT_FOUND = 1


class BrushMappingError:
    def __init__(self, brush_index: int, error_type: BrushMappingErrorType, level_polygon_index: Optional[int] = None, brush_polygon_index: Optional[int] = None) -> None:
        self.brush_index = brush_index
        self.error_type = error_type
        self.level_polygon_index = level_polygon_index
        self.brush_polygon_index = brush_polygon_index

    def __str__(self):
        if self.error_type == BrushMappingErrorType.BRUSH_NOT_FOUND:
            return f'Brush {self.brush_index} not found.'
        elif self.error_type == BrushMappingErrorType.BRUSH_POLYGON_NOT_FOUND:
            return f'Polygon {self.level_polygon_index} not found in brush {self.brush_index}.'


class BrushMappingResult:
    def __init__(self):
        self.face_count = 0
        self.brush_count = 0
        self.missing_brush_count = 0
        self.errors: List[BrushMappingError] = []
        self.duration = 0.0

def apply_level_to_brush_mapping(level_object: Object) -> BrushMappingResult:
    result = BrushMappingResult()

    timer = time.time()

    mapping = build_level_to_brush_mapping(level_object)

    origins, texture_us, texture_vs, level_material_indices, poly_flags = get_level_face_data(level_object)
    # Possible scenarios where this will break:
    # 1. If the brush mesh topology has changed since the mapping was created.
    # 2. If the brush has been deleted (in this case it's just a no-op).

    for brush_index, brush in enumerate(level_object.bdk.level.brushes):

        if brush.brush_object is None:
            # The brush object has been deleted.
            result.missing_brush_count += 1
            result.errors.append(BrushMappingError(brush_index, BrushMappingErrorType.BRUSH_NOT_FOUND))
            continue

        if brush_index not in mapping:
            # The brush has no polygons in the level.
            continue

        result.brush_count += 1

        brush_object = cast(Object, brush.brush_object)
        brush_mesh = cast(Mesh, brush_object.data)

        # Ensure that the brush mesh has the necessary attributes.
        _ensure_bsp_surface_attributes(brush_mesh)

        brush_origin_attribute = brush_mesh.attributes['bdk.origin']
        brush_texture_u_attribute = brush_mesh.attributes['bdk.texture_u']
        brush_texture_v_attribute = brush_mesh.attributes['bdk.texture_v']
        brush_poly_flags_attribute = brush_mesh.attributes['bdk.poly_flags']
        brush_material_index_attribute = brush_mesh.attributes['material_index']

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
            brush_material_slot_index = brush_object.material_slots.find(level_material.name if level_material is not None else '')
            if brush_material_slot_index == -1:
                # The material is not in the brush, so add it.
                brush_material_slot_index = len(brush_object.material_slots)
                brush_object.data.materials.append(level_material)
            material_index_mapping[level_material_index] = brush_material_slot_index

        for brush_polygon_index, level_polygon_index in mapping[brush_index].items():
            if brush_polygon_index >= len(brush_mesh.polygons):
                # The cached brush polygon index is out of range.
                result.errors.append(
                    BrushMappingError(brush_index, BrushMappingErrorType.BRUSH_POLYGON_NOT_FOUND,
                                      level_polygon_index=level_polygon_index,
                                      brush_polygon_index=brush_polygon_index))
                continue

            origin = Vector(origins[level_polygon_index])
            texture_u = Vector(texture_us[level_polygon_index])
            texture_v = Vector(texture_vs[level_polygon_index])

            # Transform the texturing plane from level-space to brush space.
            inverse_brush_world_matrix = brush_object.matrix_world.inverted()
            translation, rotation, scale = inverse_brush_world_matrix.decompose()
            rotation_matrix = rotation.to_matrix().to_4x4()
            scale_matrix = mathutils.Matrix.Diagonal(scale.to_4d()).inverted()  # The scale matrix is inverted again.
            points_matrix = inverse_brush_world_matrix
            vectors_matrix = rotation_matrix @ scale_matrix

            origin = points_matrix @ origin
            texture_u = vectors_matrix @ texture_u
            texture_v = vectors_matrix @ texture_v

            # TODO: To make this stable regardless of brush transform, store the original brush transform in the level
            #  object.

            brush_origin_attribute.data[brush_polygon_index].vector = origin
            brush_texture_u_attribute.data[brush_polygon_index].vector = texture_u
            brush_texture_v_attribute.data[brush_polygon_index].vector = texture_v
            brush_poly_flags_attribute.data[brush_polygon_index].value = poly_flags[level_polygon_index]
            brush_material_index_attribute.data[brush_polygon_index].value = material_index_mapping[level_material_indices[level_polygon_index]]

            result.face_count += 1

    result.duration = time.time() - timer

    return result


def build_level_to_brush_mapping(level_object: Object) -> Dict[int, Dict[int, int]]:
    mesh_data = cast(Mesh, level_object.data)
    polygon_count = len(mesh_data.polygons)
    brush_indices = np.zeros(polygon_count, dtype=np.int32)
    brush_polygon_indices = np.zeros(polygon_count, dtype=np.int32)

    if BRUSH_INDEX_ATTRIBUTE_NAME in mesh_data.attributes:
        mesh_data.attributes[BRUSH_INDEX_ATTRIBUTE_NAME].data.foreach_get('value', brush_indices)

    if BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME in mesh_data.attributes:
        mesh_data.attributes[BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME].data.foreach_get('value', brush_polygon_indices)

    mapping: Dict[int, Dict[int, int]] = {}

    for polygon_index, (brush_index, brush_polygon_index) in enumerate(zip(brush_indices, brush_polygon_indices)):
        if brush_index not in mapping:
            mapping[brush_index] = {}
        if brush_polygon_index not in mapping[brush_index]:
            mapping[brush_index][brush_polygon_index] = polygon_index

    return mapping


def ensure_bdk_brush_uv_node_tree():

    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

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

        subtract_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        subtract_node.operation = 'SUBTRACT'
        subtract_node.inputs[0].default_value = (0.0, 1.0, 0.0)

        material_size_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        material_size_switch_node.input_type = 'VECTOR'

        material_size_fallback_vector_node = node_tree.nodes.new(type='FunctionNodeInputVector')
        material_size_fallback_vector_node.vector = (512.0, 512.0, 0.0)

        try:
            object_material_size_node = node_tree.nodes.new(type='GeometryNodeBDKObjectMaterialSize')
            combine_material_size_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')
            evaluate_at_index_material_index_node = node_tree.nodes.new(type='GeometryNodeFieldAtIndex')
            evaluate_at_index_material_index_node.data_type = 'INT'
            evaluate_at_index_material_index_node.domain = 'FACE'
            self_object_node = node_tree.nodes.new(type='GeometryNodeSelfObject')
            material_index_node = node_tree.nodes.new(type='GeometryNodeInputMaterialIndex')

            node_tree.links.new(evaluate_at_index_material_index_node.outputs['Value'],
                                object_material_size_node.inputs['Material Index'])
            node_tree.links.new(self_object_node.outputs['Self Object'], object_material_size_node.inputs['Object'])
            node_tree.links.new(object_material_size_node.outputs['Exists'], material_size_switch_node.inputs['Switch'])
            node_tree.links.new(object_material_size_node.outputs['U'], combine_material_size_node.inputs['X'])
            node_tree.links.new(object_material_size_node.outputs['V'], combine_material_size_node.inputs['Y'])
            node_tree.links.new(combine_material_size_node.outputs['Vector'], material_size_switch_node.inputs['True'])
            node_tree.links.new(face_of_corner_node.outputs['Face Index'],
                                evaluate_at_index_material_index_node.inputs['Index'])
            node_tree.links.new(material_index_node.outputs['Material Index'],
                                evaluate_at_index_material_index_node.inputs['Value'])
        except RuntimeError:
            pass

        node_tree.links.new(material_size_fallback_vector_node.outputs['Vector'], material_size_switch_node.inputs['False'])

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
        node_tree.links.new(combine_xyz_node.outputs['Vector'], texture_scale_node.inputs[0])
        node_tree.links.new(material_size_switch_node.outputs['Output'], texture_scale_node.inputs[1])

        # Output
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Brush UV', items, build_function)


def ensure_bdk_bsp_poly_flags_node_tree():
    items = [
        ('OUTPUT', 'NodeSocketInt', 'Poly Flags'),
    ]

    for poly_flag_item in poly_flags_items:
        items.append(('INPUT', 'NodeSocketBool', poly_flag_item[1]))

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        flag_value_sockets = []

        for _, name, _, _, value in poly_flags_items:
            poly_flag_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
            poly_flag_switch_node.input_type = 'INT'
            poly_flag_switch_node.inputs['True'].default_value = value

            node_tree.links.new(input_node.outputs[name], poly_flag_switch_node.inputs['Switch'])

            flag_value_sockets.append(poly_flag_switch_node.outputs['Output'])

        output_socket = add_chained_bitwise_operation_nodes(node_tree, 'OR', flag_value_sockets)

        node_tree.links.new(output_socket, output_node.inputs['Poly Flags'])

    return ensure_geometry_node_tree('BDK BSP Poly Flags', items, build_function)


def ensure_bdk_level_visibility_modifier(level_object: Object):
    # Make sure that the level object has the level visibility modifier. If it already exists, update the node tree.
    modifier_name = 'BDK Level Visibility'
    modifier = level_object.modifiers.get(modifier_name)

    if modifier is None:
        modifier = level_object.modifiers.new(name=modifier_name, type='NODES')

    modifier.node_group = ensure_bdk_level_visibility_node_tree(level_object)


def ensure_bdk_level_visibility_node_tree(level_object: Object):
    items = (
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        poly_flags_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        poly_flags_group_node.node_tree = ensure_bdk_bsp_poly_flags_node_tree()

        # Add drivers for the relevant inputs.
        def add_level_visibility_driver(id: bpy_struct, data_path_name: str):
            driver = id.driver_add('default_value').driver
            driver.type = 'AVERAGE'
            variable = driver.variables.new()
            variable.name = 'visibility'
            variable.targets[0].id = level_object
            variable.targets[0].data_path = f'bdk.level.visibility.{data_path_name}'

        drivers = (
            ('Fake Backdrop', 'fake_backdrop'),
            ('Invisible', 'invisible'),
            ('Portal', 'portal'),
        )

        for (input_socket_name, data_path_name) in drivers:
            add_level_visibility_driver(poly_flags_group_node.inputs[input_socket_name], data_path_name)

        poly_flags_named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        poly_flags_named_attribute_node.data_type = 'INT'
        poly_flags_named_attribute_node.inputs['Name'].default_value = POLY_FLAGS_ATTRIBUTE_NAME

        delete_geometry_node = node_tree.nodes.new(type='GeometryNodeDeleteGeometry')
        delete_geometry_node.domain = 'FACE'
        delete_geometry_node.mode = 'ONLY_FACE'

        bitwise_and_operation_node = node_tree.nodes.new(type='FunctionNodeBitwiseOperation')
        bitwise_and_operation_node.operation = 'AND'

        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'NOT_EQUAL'
        compare_node.inputs[1].default_value = 0

        node_tree.links.new(input_node.outputs['Geometry'], delete_geometry_node.inputs['Geometry'])
        node_tree.links.new(poly_flags_group_node.outputs['Poly Flags'], bitwise_and_operation_node.inputs[0])
        node_tree.links.new(poly_flags_named_attribute_node.outputs['Attribute'], bitwise_and_operation_node.inputs[1])
        node_tree.links.new(bitwise_and_operation_node.outputs['Result'], compare_node.inputs['A'])
        node_tree.links.new(compare_node.outputs['Result'], delete_geometry_node.inputs['Selection'])
        node_tree.links.new(delete_geometry_node.outputs['Geometry'], output_node.inputs['Geometry'])

    if level_object.bdk.level.visibility_modifier_id == '':
        level_object.bdk.level.visibility_modifier_id = uuid.uuid4().hex

    return ensure_geometry_node_tree(level_object.bdk.level.visibility_modifier_id, items, build_function, should_force_build=True)


# TODO: We can use this, or something like it, when we to create a brush from an existing mesh that doesn't have the BDK
#  brush attributes. It's logic may even be able to be converted to a geonode operator.
def create_bsp_brush_polygon(texture_width: int, texture_height: int, uv_layer, face: BMFace, transform_matrix) -> (Vector, Quaternion, Vector):
    texture_coordinates = [loop[uv_layer].uv for loop in face.loops[0:3]]

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
