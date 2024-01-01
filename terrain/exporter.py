import io
import os

import bmesh
import bpy
import numpy as np
from bpy.types import Object, Mesh, Image, Depsgraph
from typing import cast, Optional, Callable

from mathutils import Vector, Matrix, Euler

from ..t3d.data import T3DObject
from ..t3d.writer import T3DWriter
from ..helpers import get_terrain_info, sanitize_name_for_unreal
from ..g16.g16 import write_bmp_g16


def get_instance_offset(asset_instance: Object) -> Matrix:  # TODO: move to generic helpers
    try:
        local_offset: Vector = asset_instance.instance_collection.instance_offset
        return Matrix().Translation(local_offset).inverted()
    except AttributeError:
        return Matrix()


# TODO: just make a conversion matrix?
def convert_blender_matrix_to_unreal_movement_units(matrix: Matrix) -> (Vector, Euler, Vector):
    """
    Converts a Blender world matrix to units suitable for exporting to Unreal Engine.
    This also corrects for the offset that occurs when pasting a brush object into the Unreal Editor.
    :param matrix: The Blender world matrix.
    :return: The location, rotation and scale.
    """
    # Location is corrected by 32 units as it gets offset when brush_object is pasted into the Unreal Editor.
    loc: Vector = matrix.to_translation() - Vector((32.0, -32.0, 32.0))
    # Y-Axis is inverted in Unreal Engine.
    loc.y = -loc.y
    return loc, matrix.to_euler('XYZ'), matrix.to_scale()


# TODO: kind of ugly
def add_movement_properties_to_actor(actor: T3DObject, bpy_object: Object, asset_instance: Optional[Object] = None, do_location = True, do_rotation = True, do_scale = True) -> None:
    if asset_instance:
        matrix_world: Matrix = asset_instance.matrix_world @ get_instance_offset(asset_instance) @ bpy_object.matrix_local
    else:
        matrix_world = bpy_object.matrix_world

    location, rotation, scale = convert_blender_matrix_to_unreal_movement_units(matrix_world)
    if do_location:
        actor.properties['Location'] = location
    if do_rotation:
        actor.properties['Rotation'] = rotation
    if do_scale:
        actor.properties['DrawScale3D'] = scale


def create_static_mesh_actor(static_mesh_object: Object, asset_instance: Optional[Object] = None) -> T3DObject:
    actor = T3DObject('Actor')
    actor.properties['Class'] = 'StaticMeshActor'
    actor.properties['Name'] = static_mesh_object.name
    actor.properties['StaticMesh'] = static_mesh_object.bdk.package_reference
    add_movement_properties_to_actor(actor, static_mesh_object, asset_instance)

    # Skin Overrides
    for material_index, material_slot in enumerate(static_mesh_object.material_slots):
        if material_slot.link == 'OBJECT' \
                and material_slot.material is not None \
                and material_slot.material.bdk.package_reference:
            actor.properties[f'Skins({material_index})'] = material_slot.material.bdk.package_reference

    return actor


def create_terrain_info_actor(terrain_info_object: Object) -> T3DObject:
    terrain_info = get_terrain_info(terrain_info_object)

    terrain_info_name = sanitize_name_for_unreal(terrain_info_object.name)

    actor = T3DObject('Actor')
    actor.properties['Class'] = 'TerrainInfo'
    actor.properties['Name'] = terrain_info_name

    # Paint Layers
    layers = []
    for paint_layer in terrain_info.paint_layers:
        texture = paint_layer.material.bdk.package_reference if paint_layer.material else None
        layers.append({
            'Texture': texture,
            'AlphaMap': f'Texture\'myLevel.{sanitize_name_for_unreal(paint_layer.name)}\'',
            'UScale': paint_layer.u_scale,
            'VScale': paint_layer.v_scale,
            'TextureRotation': paint_layer.texture_rotation,
        })

    # Deco Layers
    deco_layers = []
    for deco_layer in terrain_info.deco_layers:
        deco_layers.append({
            'ShowOnTerrain': int(deco_layer.show_on_terrain),
            'DensityMap': f'Texture\'myLevel.{sanitize_name_for_unreal(deco_layer.name)}\'',
            'StaticMesh': deco_layer.static_mesh.data.name if deco_layer.static_mesh else None,
            'ScaleMultiplier': {
                'X': {
                    'Min': deco_layer.scale_multiplier_min[0],
                    'Max': deco_layer.scale_multiplier_max[0]
                },
                'Y': {
                    'Min': deco_layer.scale_multiplier_min[1],
                    'Max': deco_layer.scale_multiplier_max[1]
                },
                'Z': {
                    'Min': deco_layer.scale_multiplier_min[2],
                    'Max': deco_layer.scale_multiplier_max[2]
                }
            },
            'DensityMultiplier': {
                'Min': deco_layer.density_multiplier_min,
                'Max': deco_layer.density_multiplier_max
            },
            'FadeoutRadius': {
                'Min': deco_layer.fadeout_radius_min,
                'Max': deco_layer.fadeout_radius_max
            },
            'MaxPerQuad': deco_layer.max_per_quad,
            'Seed': deco_layer.seed,
            'AlignToTerrain': int(deco_layer.align_to_terrain),
            'RandomYaw': int(deco_layer.random_yaw),
            'ForceDraw': int(deco_layer.force_draw)
        })

    mesh = cast(Mesh, terrain_info_object.data)
    bm = bmesh.new()
    bm.from_mesh(mesh)

    bitmap_size = max(1, int(terrain_info.x_size * terrain_info.y_size / 32))

    bm.faces.ensure_lookup_table()

    # Edge Turn Bitmap
    edge_turn_bitmap = np.zeros(bitmap_size, dtype=np.int32)
    vertex_index = terrain_info.x_size * (terrain_info.y_size - 2)        # the vert index is wrong here
    bitmap_index = 0
    for y in reversed(range(terrain_info.y_size - 1)):
        for x in range(terrain_info.x_size - 1):
            face_index = (y * terrain_info.x_size) - y + x
            face = bm.faces[face_index]
            # Check if the first vertex in the loop for this face coincides with the natural first vertex or the vertex
            # diagonal to it.
            loop_vertex_index = face.loops[0].vert.index
            if loop_vertex_index == vertex_index or loop_vertex_index == vertex_index + terrain_info.x_size + 1:
                array_index = bitmap_index >> 5
                bit_mask = bitmap_index & 0x1F
                edge_turn_bitmap[array_index] |= (np.int32(1) << bit_mask)
            vertex_index += 1
            bitmap_index += 1
        vertex_index -= (terrain_info.x_size * 2) - 1
        bitmap_index += 1

    # Quad Visibility Bitmap
    quad_visibility_bitmap = np.full(bitmap_size, fill_value=-1, dtype=np.int32)
    bitmap_index = 0
    for y in reversed(range(terrain_info.y_size - 1)):
        for x in range(terrain_info.x_size - 1):
            face_index = (y * terrain_info.x_size) - y + x
            face = bm.faces[face_index]
            if face.material_index == 1:
                array_index = bitmap_index >> 5
                bit_mask = bitmap_index & 0x1F
                quad_visibility_bitmap[array_index] &= ~(np.int32(1) << bit_mask)
            bitmap_index += 1
        bitmap_index += 1

    actor.properties['TerrainMap'] = f'Texture\'myLevel.{terrain_info_name}\''
    actor.properties['Layers'] = layers
    actor.properties['DecoLayers'] = deco_layers
    actor.properties['EdgeTurnBitmap'] = edge_turn_bitmap.tolist()
    actor.properties['QuadVisibilityBitmap'] = quad_visibility_bitmap.tolist()
    actor.properties['bNoDelete'] = True
    actor.properties['bLockLocation'] = True
    actor.properties['TerrainSectorSize'] = min(16, terrain_info.y_size, terrain_info.x_size)
    actor.properties['TerrainScale'] = Vector((
        terrain_info.terrain_scale,
        terrain_info.terrain_scale,
        terrain_info.terrain_scale_z))
    actor.properties['DecoLayerOffset'] = terrain_info_object.bdk.terrain_info.deco_layer_offset

    add_movement_properties_to_actor(actor, terrain_info_object)

    return actor


def export_terrain_deco_layers(terrain_info_object: Object, depsgraph: Depsgraph, directory: str, progress_cb: Callable[[int, int], None] = None):
    terrain_info = get_terrain_info(terrain_info_object)

    if terrain_info is None:
        raise RuntimeError('Invalid object')

    for deco_layer_index, deco_layer in enumerate(terrain_info.deco_layers):
        image = create_image_from_attribute(terrain_info_object, depsgraph, deco_layer.id)
        # Write the image out to a file.
        file_name = f'{sanitize_name_for_unreal(deco_layer.name)}.tga'
        image.save(filepath=os.path.join(directory, file_name))
        # Now remove the image data block.
        bpy.data.images.remove(image)

        if progress_cb:
            progress_cb(deco_layer_index, len(terrain_info.deco_layers))


def export_terrain_paint_layers(terrain_info_object: Object, depsgraph: Depsgraph, directory: str, progress_cb: Callable[[int, int], None] = None):
    terrain_info = get_terrain_info(terrain_info_object)

    if terrain_info is None:
        raise RuntimeError('Invalid object')

    for paint_layer_index, paint_layer in enumerate(terrain_info.paint_layers):
        image = create_image_from_attribute(terrain_info_object, depsgraph, paint_layer.id)
        # Write the image out to a file.
        file_name = f'{sanitize_name_for_unreal(paint_layer.name)}.tga'
        image.save(filepath=os.path.join(directory, file_name))
        # Now remove the image data block.
        bpy.data.images.remove(image)

        if progress_cb:
            progress_cb(paint_layer_index, len(terrain_info.paint_layers))


def create_image_from_attribute(terrain_info_object: Object, depsgraph: Depsgraph, attribute_name: str) -> Image:
    terrain_info = get_terrain_info(terrain_info_object)

    if terrain_info is None:
        raise RuntimeError('Invalid object')

    # Get evaluated mesh data.
    terrain_info_object = terrain_info_object.evaluated_get(depsgraph)
    mesh_data = cast(Mesh, terrain_info_object.data)

    if attribute_name not in mesh_data.attributes:
        raise RuntimeError(f'Attribute {attribute_name} not found')

    attribute = mesh_data.attributes[attribute_name]

    if attribute.domain != 'POINT':
        raise RuntimeError(f'Attribute {attribute_name} has unexpected domain ({attribute.domain})')

    if attribute.data_type not in {'FLOAT', 'FLOAT_COLOR', 'BYTE_COLOR'}:
        raise RuntimeError(f'Attribute {attribute_name} is not a float or color attribute')

    pixel_count = len(attribute.data)

    image = bpy.data.images.new(name=attribute_name, width=terrain_info.x_size, height=terrain_info.y_size, alpha=True)
    image.file_format = 'TARGA'

    # Fill the data in with a middle-grey RGB layer and a 100% alpha.
    data = np.ndarray(shape=(pixel_count, 4), dtype=float)
    data[:] = (0.5, 0.5, 0.5, 1.0)

    if attribute.data_type in {'FLOAT_COLOR', 'BYTE_COLOR'}:
        # TODO: this whole thing is undesirable, we want all of our attributes to be floats.
        rgb_colors = np.ndarray(shape=(pixel_count, 3), dtype=float)
        rgb_colors[:] = [datum.color[:3] for datum in attribute.data]

        # Reshape this to a 2D array based on the terrain size.
        rgb_colors = rgb_colors.reshape((terrain_info.y_size, terrain_info.x_size, 3))

        # Flip along the first axis and then the second axis.
        rgb_colors = np.flip(rgb_colors, axis=0)

        # Now set the shape back to a 1D array.
        rgb_colors = rgb_colors.reshape((pixel_count, 3))

        # Convert the RGB values to B/W values and assign those to the alpha channel of the data.
        '''
        Note that these coefficients are identical to the ones that Blender uses
        when it converts an RGB color to a B/W value. Our terrain shader uses
        the behavior, so we must replicate it here.

        When we can finally just paint float values, this will be unnecessary.
        '''
        luma_coefficients = (0.2126, 0.7152, 0.0722)
        data[:, 3] = np.dot(rgb_colors, luma_coefficients)
    else:
        # Reshape this to a 2D array based on the terrain size.
        attribute_data = np.array([x.value for x in attribute.data], dtype=float)
        attribute_data.resize((terrain_info.y_size, terrain_info.x_size))
        attribute_data = np.flip(attribute_data, axis=0)

        # Reshape this to a 2D array based on the terrain size.
        # data = data.reshape((terrain_info.y_size, terrain_info.x_size, 4))

        data[:, 3] = attribute_data.flatten()

    # Assign the image pixels.
    image.pixels[:] = data.flatten()

    return image


def get_terrain_heightmap(terrain_info_object: Object, depsgraph: Depsgraph) -> np.ndarray:
    terrain_info = get_terrain_info(terrain_info_object)
    if terrain_info is None:
        raise RuntimeError('Invalid object')

    terrain_info_object = terrain_info_object.evaluated_get(depsgraph)
    mesh_data = cast(Mesh, terrain_info_object.data)

    # TODO: support "multiple terrains"
    shape = (terrain_info.x_size, terrain_info.y_size)
    heightmap = np.array([v.co[2] for v in mesh_data.vertices], dtype=float)
    heightmap = quantize_heightmap(heightmap, terrain_info.terrain_scale_z)
    return heightmap.reshape(shape)


def export_terrain_heightmap(terrain_info_object: Object, depsgraph: Depsgraph, directory: str):
    heightmap = get_terrain_heightmap(terrain_info_object, depsgraph)
    file_name = f'{sanitize_name_for_unreal(terrain_info_object.name)}.bmp'
    path = os.path.join(directory, file_name)
    write_bmp_g16(path, pixels=heightmap)


def write_terrain_t3d(terrain_info_object: Object, depsgraph: Depsgraph, fp: io.TextIOBase):
    t3d = T3DObject('Map')
    t3d.children.append(create_terrain_info_actor(terrain_info_object))
    T3DWriter(fp).write(t3d)


def get_terrain_height_range(heightmap: np.ndarray) -> (float, float):
    height_max = np.max(heightmap)
    height_min = np.min(heightmap)
    max_extent = max(np.fabs(height_max), np.fabs(height_min))
    height_max = max_extent
    height_min = -max_extent
    return height_min, height_max


def get_best_terrain_scale_z(heightmap: np.ndarray) -> float:
    height_min, height_max = get_terrain_height_range(heightmap)
    return height_max - height_min


def quantize_heightmap(heightmap: np.array, terrain_scale_z: float) -> np.array:
    if terrain_scale_z == 0:
        heightmap.fill(0.5)
    else:
        # Calculate the maximum height value based on the terrain scale.
        terrain_max_height = terrain_scale_z * 256.0
        # Raise the heightmap so that the minimum height is >=0.
        heightmap = (heightmap / terrain_max_height) + 0.5
        # If the heightmap has any values outside the range [0, 1], throw an error.
        if np.any(heightmap < 0) or np.any(heightmap > 1):
            raise RuntimeError('The TerrainScale.Z value is too small for the heightmap.')
    heightmap = np.uint16(heightmap * 65535)
    return heightmap
