import io
import os

import bmesh
import bpy
import numpy as np
from bpy.types import Object, Mesh, Image, Depsgraph
from typing import cast, Optional

from mathutils import Vector, Matrix

from ..t3d.data import T3DActor, T3DMap
from ..t3d.writer import T3DWriter
from ..helpers import get_terrain_info
from .g16 import write_bmp_g16


def get_instance_offset(asset_instance: Object) -> Matrix:
    try:
        local_offset: Vector = asset_instance.instance_collection.instance_offset
        return Matrix().Translation(local_offset).inverted()
    except AttributeError:
        return Matrix()


# TODO: kind of ugly
def add_movement_properties_to_actor(actor: T3DActor, bpy_object: Object, asset_instance: Optional[Object] = None) -> None:
    if asset_instance:
        matrix_world: Matrix = asset_instance.matrix_world @ get_instance_offset(asset_instance) @ bpy_object.matrix_local
    else:
        matrix_world = bpy_object.matrix_world

    # Location is corrected by 32 units as it gets offset when actor
    # is pasted into the Unreal Editor.
    loc: Vector = matrix_world.to_translation() - Vector((32.0, -32.0, 32.0))
    # Y-Axis is inverted in UE.
    loc.y = -loc.y

    actor['Location'] = loc
    actor['Rotation'] = matrix_world.to_euler('XYZ')
    actor['DrawScale3D'] = matrix_world.to_scale()


def create_static_mesh_actor(static_mesh_object: Object, asset_instance: Optional[Object] = None) -> T3DActor:
    actor = T3DActor(class_='StaticMeshActor', name=static_mesh_object.name)

    actor['StaticMesh'] = static_mesh_object.data.name
    add_movement_properties_to_actor(actor, static_mesh_object, asset_instance)

    # Skin Overrides
    for material_index, material_slot in enumerate(static_mesh_object.material_slots):
        if material_slot.link == 'OBJECT' and material_slot.material is not None and 'bdk.reference' in material_slot.material:
            actor[f'Skins({material_index})'] = material_slot.material['bdk.reference']

    return actor


def create_terrain_info_actor(terrain_info_object: Object, terrain_scale_z: float) -> T3DActor:
    terrain_info = get_terrain_info(terrain_info_object)

    actor = T3DActor(class_='TerrainInfo', name='TerrainInfo0')

    # Paint Layers
    layers = []
    for paint_layer in terrain_info.paint_layers:
        name = paint_layer.id
        texture = paint_layer.material.get('bdk.reference', None) if paint_layer.material else None
        layers.append({
            'Texture': texture,
            'AlphaMap': f'Texture\'myLevel.Terrain.{name}\'',  # TODO: make "reference" class, handle strings differently in writer
            'UScale': paint_layer.u_scale,
            'VScale': paint_layer.v_scale,
            'TextureRotation': paint_layer.texture_rotation,
        })

    # Deco Layers
    deco_layers = []
    for deco_layer in terrain_info.deco_layers:
        deco_layers.append({
            'ShowOnTerrain': int(deco_layer.show_on_terrain),
            'DensityMap': f'Texture\'myLevel.Terrain.{deco_layer.id}\'',
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

    actor['TerrainMap'] = f'Texture\'myLevel.Terrain.{terrain_info_object.name}\''
    actor['Layers'] = layers
    actor['DecoLayers'] = deco_layers
    actor['EdgeTurnBitmap'] = edge_turn_bitmap.tolist()
    actor['QuadVisibilityBitmap'] = quad_visibility_bitmap.tolist()
    actor['bNoDelete'] = True
    actor['bMoveable'] = False
    actor['bLockLocation'] = True
    actor['TerrainSectorSize'] = min(16, terrain_info.y_size, terrain_info.x_size)
    actor['TerrainScale'] = Vector((
        terrain_info.terrain_scale,
        terrain_info.terrain_scale,
        max(1.0, terrain_scale_z / 256.0)))  # A scale of 0 makes the terrain not display.
    actor['DecoLayerOffset'] = 0.0
    actor['Location'] = Vector(terrain_info_object.location) - Vector((32.0, 32.0, 32.0))

    return actor


def sanitize_name(name: str) -> str:
    # TODO: remove special characters etc.
    return name.replace(' ', '_')


def export_deco_layers(terrain_info_object: Object, depsgraph: Depsgraph, directory: str):
    terrain_info = get_terrain_info(terrain_info_object)

    if terrain_info is None:
        raise RuntimeError('Invalid object')

    for deco_layer in terrain_info.deco_layers:
        image = create_image_from_color_attribute(terrain_info_object, depsgraph, deco_layer.id)
        # Write the image out to a file.
        image.save(filepath=os.path.join(directory, f'{image.name}.tga'))
        # Now remove the image data block.
        bpy.data.images.remove(image)


def export_terrain_paint_layers(terrain_info_object: Object, depsgraph: Depsgraph, directory: str):
    terrain_info = get_terrain_info(terrain_info_object)

    if terrain_info is None:
        raise RuntimeError('Invalid object')

    for paint_layer in terrain_info.paint_layers:
        image = create_image_from_color_attribute(terrain_info_object, depsgraph, paint_layer.id)
        # Write the image out to a file.
        image.save(filepath=os.path.join(directory, f'{image.name}.tga'))
        # Now remove the image data block.
        bpy.data.images.remove(image)


def create_image_from_color_attribute(terrain_info_object: Object, depsgraph: Depsgraph, color_attribute_name: str) -> Image:
    terrain_info = get_terrain_info(terrain_info_object)

    if terrain_info is None:
        raise RuntimeError('Invalid object')

    # Get evaluated mesh data.
    terrain_info_object = terrain_info_object.evaluated_get(depsgraph)
    mesh_data = cast(Mesh, terrain_info_object.data)

    attribute = mesh_data.color_attributes[color_attribute_name]
    pixel_count = len(attribute.data)

    image = bpy.data.images.new(name=color_attribute_name, width=terrain_info.x_size, height=terrain_info.y_size, alpha=True)
    image.file_format = 'TARGA'

    rgb_colors = np.ndarray(shape=(pixel_count, 3), dtype=float)

    rgb_colors[:] = [datum.color[:3] for datum in attribute.data]

    # Reshape this to a 2D array based on the terrain size.
    rgb_colors = rgb_colors.reshape((terrain_info.y_size, terrain_info.x_size, 3))

    # Flip along the first axis and then the second axis.
    rgb_colors = np.flip(rgb_colors, axis=0)

    # Now set the shape back to a 1D array.
    rgb_colors = rgb_colors.reshape((pixel_count, 3))

    # Fill the data in with a middle-grey RGB layer and a 100% alpha.
    data = np.ndarray(shape=(pixel_count, 4), dtype=float)
    data[:] = (0.5, 0.5, 0.5, 1.0)

    # Convert the RGB values to B/W values and assign those to the alpha channel of the data.
    '''
    Note that these coefficients are identical to the ones that Blender uses
    when it converts an RGB color to a B/W value. Our terrain shader uses
    the behavior, so we must replicate it here.
    '''
    luma_coefficients = (0.2126, 0.7152, 0.0722)
    data[:, 3] = np.dot(rgb_colors, luma_coefficients)

    # Assign the image pixels.
    image.pixels[:] = data.flatten()

    return image


def get_terrain_heightmap(terrain_info_object: Object, depsgraph: Depsgraph) -> (np.ndarray, float):
    terrain_info = get_terrain_info(terrain_info_object)
    if terrain_info is None:
        raise RuntimeError('Invalid object')

    terrain_info_object = terrain_info_object.evaluated_get(depsgraph)
    mesh_data = cast(Mesh, terrain_info_object.data)

    # TODO: support "multiple terrains"
    shape = (terrain_info.x_size, terrain_info.y_size)
    heightmap = np.array([v.co[2] for v in mesh_data.vertices], dtype=float)
    heightmap, terrain_scale_z = normalize_and_quantize_heights(heightmap)
    return heightmap.reshape(shape), terrain_scale_z


def export_terrain_heightmap(terrain_info_object: Object, depsgraph: Depsgraph, directory: str):
    heightmap, _ = get_terrain_heightmap(terrain_info_object, depsgraph)
    path = os.path.join(directory, f'{terrain_info_object.name}.bmp')
    write_bmp_g16(path, pixels=heightmap)


def write_terrain_t3d(terrain_info_object: Object, depsgraph: Depsgraph, fp: io.TextIOBase):
    heightmap, terrain_scale_z = get_terrain_heightmap(terrain_info_object, depsgraph)
    t3d = T3DMap()
    t3d.actors.append(create_terrain_info_actor(terrain_info_object, terrain_scale_z))
    T3DWriter(fp).write(t3d)


def get_terrain_height_range(heightmap: np.ndarray) -> (float, float):
    height_max = np.max(heightmap)
    height_min = np.min(heightmap)
    max_extent = max(np.fabs(height_max), np.fabs(height_min))
    height_max = max_extent
    height_min = -max_extent
    return height_min, height_max


def normalize_and_quantize_heights(heightmap: np.array) -> (np.array, float):
    height_min, height_max = get_terrain_height_range(heightmap)
    terrain_scale_z = height_max - height_min
    if terrain_scale_z == 0:
        heightmap.fill(0.5)
    else:
        heightmap = (heightmap - height_min) / terrain_scale_z
    heightmap = np.uint16(heightmap * 65535)
    return heightmap, terrain_scale_z
