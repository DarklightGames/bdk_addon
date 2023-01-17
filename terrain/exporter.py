import io
import os
from collections import OrderedDict
from types import NoneType

import bpy
import numpy as np
from bpy.props import StringProperty
from bpy.types import Object, Mesh, Context, Operator
from typing import cast, Any, List

from bpy_extras.io_utils import ExportHelper
from mathutils import Vector

from .types import BDK_PG_TerrainInfoPropertyGroup, BDK_PG_TerrainLayerPropertyGroup
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
    def __init__(self, fp: io.StringIO):
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

    quad_visibility_bitmap = [-1] * int(terrain_info.x_size * terrain_info.y_size / 32)
    layers = []

    for terrain_layer in terrain_info.terrain_layers:
        name = get_terrain_layer_human_readable_name(terrain_layer)
        layers.append({
            'Texture': None,
            'AlphaMap': f'Texture\'myLevel.Terrain.{name}\'',  # TODO: make "reference" class, handle strings differently in writer
            'UScale': terrain_layer.u_scale,
            'VScale': terrain_layer.v_scale,
            'TextureRotation': terrain_layer.texture_rotation,
        })

    actor['TerrainMap'] = f'Texture\'myLevel.Terrain.{terrain_info_object.name}\''
    actor['Layers'] = layers
    actor['EdgeTurnBitmap'] = []  # TODO: fill this in
    actor['bNoDelete'] = True
    actor['bMoveable'] = False
    actor['bLockLocation'] = True
    actor['TerrainScale'] = Vector((terrain_info.terrain_scale, terrain_info.terrain_scale, terrain_scale_z / 256.0))
    actor['DecoLayerOffset'] = 0.0
    actor['QuadVisibilityBitmap'] = quad_visibility_bitmap

    return actor


def sanitize_name(name: str) -> str:
    # TODO: remove special characters etc.
    return name.replace(' ', '_')


def get_terrain_layer_human_readable_name(terrain_layer: BDK_PG_TerrainLayerPropertyGroup):
    return f'{sanitize_name(terrain_layer.name)}-{terrain_layer.color_attribute_name[-6:]}'


def export_terrain_layers(terrain_info_object: Object, directory: str):
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object')

    mesh_data = cast(Mesh, terrain_info_object.data)

    for terrain_layer in terrain_info.terrain_layers:
        attribute = mesh_data.color_attributes[terrain_layer.color_attribute_name]
        pixel_count = len(attribute.data)

        image_name = get_terrain_layer_human_readable_name(terrain_layer)

        image = bpy.data.images.new(name=image_name, width=terrain_info.x_size, height=terrain_info.y_size, alpha=True)
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
        filepath = os.path.join(directory, f'{image_name}.tga')
        image.save(filepath=filepath)

        # Now remove the image, since we don't actually need to save this.
        bpy.data.images.remove(image)


def export_terrain_heightmap(terrain_info_object: Object, directory: str):
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object')

    mesh_data = cast(Mesh, terrain_info_object.data)

    # TODO: support "multiple terrains"
    shape = (terrain_info.x_size, terrain_info.y_size)

    heightmap = np.array([v.co[2] for v in mesh_data.vertices], dtype=float)
    heightmap, terrain_scale_z = normalize_and_quantize_heights(heightmap)
    heightmap.reshape(shape)

    path = os.path.join(directory, f'{terrain_info_object.name}.bmp')
    write_bmp_g16(path, pixels=heightmap, shape=shape)

    fp = io.StringIO()

    t3d = T3D()
    t3d.actors.append(create_terrain_info_actor(terrain_info_object, terrain_scale_z))
    T3DWriter(fp).write(t3d)

    bpy.context.window_manager.clipboard = fp.getvalue()


def normalize_and_quantize_heights(heightmap: np.array) -> (np.array, float):
    height_max = np.max(heightmap)
    height_min = np.min(heightmap)
    max_extent = max(np.fabs(height_max), np.fabs(height_min))
    height_max = max_extent
    height_min = -max_extent
    terrain_scale_z = height_max - height_min
    if terrain_scale_z == 0:
        heightmap.fill(0.5)
    else:
        heightmap = (heightmap - height_min) / terrain_scale_z
    heightmap = np.uint16(heightmap * 65535)
    return heightmap, terrain_scale_z


class BDK_OT_TerrainInfoExport(Operator, ExportHelper):
    bl_label = 'Export Terrain Info'
    bl_idname = 'bdk.export_terrain_info'

    directory: StringProperty(name='Directory')
    filename_ext: StringProperty(default='.', options={'HIDDEN'})
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})

    def invoke(self, context: 'Context', event: 'Event'):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: Context):
        export_terrain_heightmap(context.active_object, directory=self.directory)
        export_terrain_layers(context.active_object, directory=self.directory)
        return {'FINISHED'}


classes = (
    BDK_OT_TerrainInfoExport,
)
