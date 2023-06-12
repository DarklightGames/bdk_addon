import bpy
import numpy as np
import uuid
from typing import cast, Tuple
from bpy.types import Mesh, Object

from ..helpers import get_terrain_info, auto_increment_name
from .builder import build_terrain_material
from .properties import BDK_PG_terrain_paint_layer


def add_terrain_paint_layer(terrain_info_object: Object, name: str,
                            fill: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)):
    terrain_info = get_terrain_info(terrain_info_object)

    # Auto-increment the names if there is a conflict.
    name = auto_increment_name(name, map(lambda x: x.name, terrain_info.paint_layers))

    mesh_data = cast(Mesh, terrain_info_object.data)

    # Add the terrain layer.
    paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers.add()
    paint_layer.terrain_info_object = terrain_info_object
    paint_layer.name = name
    paint_layer.id = uuid.uuid4().hex

    # Create the associated color attribute.
    # TODO: in future, we will be able to paint non-color attributes, so use those once that's possible.
    color_attribute = mesh_data.color_attributes.new(paint_layer.id, type='FLOAT_COLOR', domain='POINT')
    vertex_count = len(color_attribute.data)
    color_data = np.ndarray(shape=(vertex_count, 4), dtype=float)
    color_data[:] = tuple(fill)
    color_attribute.data.foreach_set('color', color_data.flatten())

    # Regenerate the terrain material.
    build_terrain_material(terrain_info_object)

    # Tag window regions for redraw so that the new layer is displayed in terrain layer lists immediately.
    for region in filter(lambda r: r.type == 'WINDOW', bpy.context.area.regions):
        region.tag_redraw()

    return paint_layer
