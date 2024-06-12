import bpy
import uuid
from bpy.types import Object, Collection

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


def create_deco_layer_object(deco_layer) -> Object:
    # Create a new mesh object with empty data.
    mesh_data = bpy.data.meshes.new(deco_layer.id)
    deco_layer_object = bpy.data.objects.new(deco_layer.id, mesh_data)
    deco_layer_object.hide_select = True
    return deco_layer_object


def add_terrain_deco_layer(terrain_info_object: Object, name: str = 'DecoLayer'):
    """
    Adds a deco layer to the terrain.
    This adds a new entry to the deco layers array in the terrain info and creates the associated deco layer object and
    mesh attributes.
    """
    terrain_info = get_terrain_info(terrain_info_object)

    # Create the deco layer object.
    deco_layer = terrain_info.deco_layers.add()
    deco_layer.name = name
    deco_layer.id = uuid.uuid4().hex
    deco_layer.modifier_name = uuid.uuid4().hex
    deco_layer.object = create_deco_layer_object(deco_layer)
    deco_layer.terrain_info_object = terrain_info_object

    # Link and parent the deco layer object to the terrain info object.
    collection: Collection = terrain_info_object.users_collection[0]
    collection.objects.link(deco_layer.object)
    deco_layer.object.parent = terrain_info_object

    return deco_layer
