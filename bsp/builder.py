# NOTE: This is taken more or less verbatim from the ase2t3d source, adopted for Python.
# In the future, clean this up so that it's more clear what is going on.
from typing import cast, Iterable, Optional

import mathutils
from bmesh.types import BMFace
from bpy.types import Object, Material

from ..t3d.data import Polygon
import numpy as np
from math import isnan


def get_uvs_for_vertices(polygon: Polygon, material: Material, vertices: Iterable[mathutils.Vector]):
    # Create a rotation & scale matrix from the UV-space vectors.
    rotation_matrix = mathutils.Matrix.Identity(3)
    rotation_matrix[0][0:3] = polygon.texture_u
    rotation_matrix[1][0:3] = polygon.texture_v
    rotation_matrix[2][0:3] = polygon.normal

    # Create a translation matrix from the origin.
    translation_matrix = mathutils.Matrix.Translation(polygon.origin)

    # Create a scale matrix from the material's texture size.
    scale_matrix = mathutils.Matrix.Identity(3)
    scale_matrix[0][0] = material.bdk.size_x
    scale_matrix[1][1] = material.bdk.size_y

    # Create the final transformation matrix.
    transform_matrix = translation_matrix @ rotation_matrix @ scale_matrix
    transform_matrix.invert()

    # Transform the vertices.
    return [transform_matrix @ vertex for vertex in vertices]


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

    # Calculate Normals. These are ignored anyway but make an effort...
    a = np.subtract(pt1, pt0)
    b = np.subtract(pt2, pt0)
    c = np.cross(a, b)

    normal = tuple(c / np.linalg.norm(c))

    # Check for error values
    impossible2 = isnan(p_base[0]) or isnan(p_base[1]) or isnan(p_base[2]) \
                  or isnan(p_grad_u[0]) or isnan(p_grad_u[1]) or isnan(p_grad_u[2]) \
                  or isnan(p_grad_v[0]) or isnan(p_grad_v[1]) or isnan(p_grad_v[2])

    impossible = impossible1 or impossible2

    origin = pt1 if impossible else p_base
    texture_u = normal if impossible else p_grad_u
    texture_v = normal if impossible else p_grad_v

    return Polygon(
        link=0,
        origin=origin,
        normal=normal,
        texture_u=texture_u,
        texture_v=texture_v,
        vertices=vertices
    )
