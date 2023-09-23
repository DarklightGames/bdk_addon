import bpy
import uuid
from bpy.types import Object

from ..helpers import get_terrain_info, ensure_name_unique
from .builder import build_terrain_material
from .properties import BDK_PG_terrain_paint_layer


def add_terrain_paint_layer(terrain_info_object: Object, name: str) -> BDK_PG_terrain_paint_layer:
    """
    Adds a new paint layer to the given terrain info object.
    Note that it is the responsibility of the caller to call ensure_paint_layers().
    :param terrain_info_object:
    :param name:
    :return:
    """
    terrain_info = get_terrain_info(terrain_info_object)

    # Add the paint layer.
    paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers.add()
    paint_layer.terrain_info_object = terrain_info_object
    paint_layer.id = uuid.uuid4().hex
    paint_layer.name = ensure_name_unique(name, [x.name for x in terrain_info.paint_layers])

    # Create the associated modifier and node group.
    paint_layer_modifier = terrain_info_object.modifiers.new(name=paint_layer.id, type='NODES')
    node_tree = bpy.data.node_groups.new(paint_layer.id, 'GeometryNodeTree')
    paint_layer_modifier.node_group = node_tree

    # Regenerate the terrain material.
    build_terrain_material(terrain_info_object)

    # Tag window regions for redraw so that the new layer is displayed in terrain layer lists immediately.
    for region in filter(lambda r: r.type == 'WINDOW', bpy.context.area.regions):
        region.tag_redraw()

    return paint_layer
