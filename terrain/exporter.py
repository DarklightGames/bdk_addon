import os
import bpy
import numpy as np
from bpy.props import StringProperty
from bpy.types import Object, Mesh, Context, Operator
from typing import cast

from bpy_extras.io_utils import ExportHelper

from .types import BDK_PG_TerrainInfoPropertyGroup
from .g16 import write_bmp_g16


def export_terrain_layers(terrain_info_object: Object, directory: str):
    terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')\

    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object')

    mesh_data = cast(Mesh, terrain_info_object.data)

    for terrain_layer in terrain_info.terrain_layers:
        attribute = mesh_data.color_attributes[terrain_layer.color_attribute_name]
        pixel_count = len(attribute.data)

        image = bpy.data.images.new(name=terrain_layer.color_attribute_name, width=terrain_info.x_size, height=terrain_info.y_size, alpha=True)
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
        filepath = os.path.join(directory, f'{terrain_layer.color_attribute_name}.tga')
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
    filename_ext: StringProperty(default='.')
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
