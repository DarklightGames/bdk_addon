import io
import os
from collections import OrderedDict
from types import NoneType

import bmesh
import bpy
import numpy as np
from bpy.types import Object, Mesh, Image
from typing import cast, Any, List

from mathutils import Vector

from .properties import BDK_PG_TerrainInfoPropertyGroup, BDK_PG_TerrainLayerPropertyGroup, \
    BDK_PG_TerrainDecoLayerPropertyGroup
from .g16 import write_bmp_g16


class Actor(OrderedDict):
    def __init__(self, class_: str, name: str):
        super().__init__()
        self['Class'] = class_
        self['Name'] = name


class T3D:
    def __init__(self):
        self.actors = []


class T3DWriter:
    def __init__(self, fp: io.TextIOBase):
        self._indent_count = 0
        self._indent_str = ' ' * 4
        self._fp = fp

    def _indent(self):
        self._indent_count += 1
        return self

    def _dedent(self):
        self._indent_count = max(self._indent_count - 1, 0)
        return self

    def _write_line(self, line: str):
        self._fp.write(f'{self._indent_str * self._indent_count}{line}\n')

    def _write_key_value(self, key: str, value: Any):
        self._write_line(f'{key}={self._value_to_string(value)}')

    def _value_to_string(self, value) -> str:
        if type(value) in {float}:
            return f'{value:0.6f}'
        if type(value) in {int, float, bool, str, NoneType}:
            return str(value)
        elif type(value) in {dict, OrderedDict}:
            return '(' + ','.join(map(lambda item: f'{item[0]}={self._value_to_string(item[1])}', value.items())) + ')'
        elif type(value) == Vector:
            return f'(X={value[0]},Y={value[1]},Z={value[2]})'
        elif type(value) == list:
            raise ValueError('Lists cannot be written inline...probably?')
        else:
            raise ValueError(f'Unhandled data type: {type(value)}')

    def _write_list(self, key: str, value_list: List):
        for index, value in enumerate(value_list):
            self._write_line(f'{key}({index})={self._value_to_string(value)}')

    def write(self, t3d: T3D):
        self._write_line('Begin Map')
        for actor in t3d.actors:
            self._write_actor(actor)
        self._write_line('End Map')

    def _write_actor(self, actor: Actor):
        self._write_line(f'Begin Actor Class={actor["Class"]} Name={actor["Name"]}')
        self._indent()

        for key, value in filter(lambda item: item[0] not in {'Class', 'Name'}, actor.items()):
            if type(value) == list:
                self._write_list(key, value)
            else:
                self._write_key_value(key, value)

        self._dedent()
        self._write_line('End Actor')


def create_terrain_info_actor(terrain_info_object: Object, terrain_scale_z: float) -> Actor:
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

    actor = Actor(class_='TerrainInfo', name='TerrainInfo0')

    layers = []
    for terrain_layer in terrain_info.terrain_layers:
        name = terrain_layer.color_attribute_name

        texture = terrain_layer.material.get('bdk.reference', None) if terrain_layer.material else None

        layers.append({
            'Texture': texture,
            'AlphaMap': f'Texture\'myLevel.Terrain.{name}\'',  # TODO: make "reference" class, handle strings differently in writer
            'UScale': terrain_layer.u_scale,
            'VScale': terrain_layer.v_scale,
            'TextureRotation': terrain_layer.texture_rotation,
        })

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
    actor['DecoLayerOffset'] = 0.0  # ?f
    actor['Location'] = Vector(terrain_info_object.location) - Vector((32.0, 32.0, 32.0))

    return actor


def sanitize_name(name: str) -> str:
    # TODO: remove special characters etc.
    return name.replace(' ', '_')


def export_deco_layers(terrain_info_object: Object, directory: str):
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object')

    for deco_layer in terrain_info.deco_layers:
        image = create_image_from_color_attribute(terrain_info_object, deco_layer.id)
        # Write the image out to a file.
        image.save(filepath=os.path.join(directory, f'{image.name}.tga'))
        # Now remove the image data block.
        bpy.data.images.remove(image)


def export_terrain_layers(terrain_info_object: Object, directory: str):
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object')

    for terrain_layer in terrain_info.terrain_layers:
        image = create_image_from_color_attribute(terrain_info_object, terrain_layer.color_attribute_name)
        # Write the image out to a file.
        image.save(filepath=os.path.join(directory, f'{image.name}.tga'))
        # Now remove the image data block.
        bpy.data.images.remove(image)


def create_image_from_color_attribute(terrain_info_object: Object, color_attribute_name: str) -> Image:
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object')

    mesh_data = cast(Mesh, terrain_info_object.data)

    attribute = mesh_data.color_attributes[color_attribute_name]
    pixel_count = len(attribute.data)

    image = bpy.data.images.new(name=color_attribute_name, width=terrain_info.x_size, height=terrain_info.y_size, alpha=True)
    image.file_format = 'TARGA'

    rgb_colors = np.ndarray(shape=(pixel_count, 3), dtype=float)
    rgb_colors[:] = [datum.color[:3] for datum in attribute.data]

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


def get_terrain_heightmap(terrain_info_object: Object) -> (np.ndarray, float):
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object')

    mesh_data = cast(Mesh, terrain_info_object.data)

    # TODO: support "multiple terrains"
    shape = (terrain_info.x_size, terrain_info.y_size)
    heightmap = np.array([v.co[2] for v in mesh_data.vertices], dtype=float)
    heightmap, terrain_scale_z = normalize_and_quantize_heights(heightmap)
    return heightmap.reshape(shape), terrain_scale_z


def export_terrain_heightmap(terrain_info_object: Object, directory: str):
    heightmap, _ = get_terrain_heightmap(terrain_info_object)
    path = os.path.join(directory, f'{terrain_info_object.name}.bmp')
    write_bmp_g16(path, pixels=heightmap)


def write_terrain_t3d(terrain_info_object: Object, fp: io.TextIOBase):
    heightmap, terrain_scale_z = get_terrain_heightmap(terrain_info_object)
    print(heightmap, terrain_scale_z)
    t3d = T3D()
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
