import bpy
import uuid
from bpy.types import Object

from .deco import ensure_terrain_layer_node_group, ensure_paint_layers
from ..helpers import get_terrain_info, ensure_name_unique
from .builder import build_terrain_material
from .properties import BDK_PG_terrain_paint_layer


def add_terrain_paint_layer(terrain_info_object: Object, name: str):
    terrain_info = get_terrain_info(terrain_info_object)

    # Auto-increment the names if there is a conflict.
    name = ensure_name_unique(name, map(lambda x: x.name, terrain_info.paint_layers))

    # Add the paint layer.
    paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers.add()
    paint_layer.terrain_info_object = terrain_info_object
    paint_layer.name = name
    paint_layer.id = uuid.uuid4().hex

    # Create the associated modifier and node group.
    paint_layer_modifier = terrain_info_object.modifiers.new(name=paint_layer.id, type='NODES')
    node_tree = bpy.data.node_groups.new(paint_layer.id, 'GeometryNodeTree')
    paint_layer_modifier.node_group = node_tree

    # TODO: this is overkill since we could just ensure the newly added one, but we may at some point want to
    #  allow the user to add a layer at a specific index.
    ensure_paint_layers(terrain_info_object)

    # Regenerate the terrain material.
    build_terrain_material(terrain_info_object)

    # Tag window regions for redraw so that the new layer is displayed in terrain layer lists immediately.
    for region in filter(lambda r: r.type == 'WINDOW', bpy.context.area.regions):
        region.tag_redraw()

    return paint_layer
