from typing import Optional

from bpy.types import Context
from .properties import BDK_PG_terrain_deco_layer, BDK_PG_terrain_paint_layer, BDK_PG_terrain_layer_node
from ..helpers import get_terrain_info

def has_deco_layer_selected(context: Context) -> bool:
    terrain_info = get_terrain_info(context.active_object)
    return terrain_info and 0 <= terrain_info.deco_layers_index < len(terrain_info.deco_layers)


def get_selected_deco_layer(context: Context) -> BDK_PG_terrain_deco_layer:
    terrain_info = get_terrain_info(context.active_object)
    return terrain_info.deco_layers[terrain_info.deco_layers_index]


def has_terrain_paint_layer_selected(context: Context) -> bool:
    terrain_info = get_terrain_info(context.active_object)
    return terrain_info and 0 <= terrain_info.paint_layers_index < len(terrain_info.paint_layers)


# TODO: replace this with a context property (i.e. context.terrain_layer)
def get_selected_terrain_paint_layer(context: Context) -> BDK_PG_terrain_paint_layer:
    terrain_info = get_terrain_info(context.active_object)
    return terrain_info.paint_layers[terrain_info.paint_layers_index]


def get_selected_terrain_paint_layer_node(context: Context) -> Optional[BDK_PG_terrain_layer_node]:
    if not has_terrain_paint_layer_selected(context):
        return None
    paint_layer = get_selected_terrain_paint_layer(context)
    nodes_index = paint_layer.nodes_index
    nodes = paint_layer.nodes
    return nodes[nodes_index] if 0 <= nodes_index < len(nodes) else None


def has_selected_terrain_paint_layer_node(context: Context) -> bool:
    return get_selected_terrain_paint_layer_node(context) is not None
