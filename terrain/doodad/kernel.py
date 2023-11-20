import uuid

from ...helpers import ensure_name_unique
from .paint.properties import BDK_PG_terrain_doodad_paint_layer
from .properties import BDK_PG_terrain_doodad
from .sculpt.properties import BDK_PG_terrain_doodad_sculpt_layer


def ensure_terrain_doodad_layer_indices(terrain_doodad):
    """
    Ensures that the layer indices of the given terrain doodad are correct.
    This is necessary because the indices are used in the driver expressions.
    Any change to the indices requires the driver expressions to be updated.
    :param terrain_doodad:
    """
    # Sculpt Layers
    for i, sculpt_layer in enumerate(terrain_doodad.sculpt_layers):
        sculpt_layer.index = i
    # Paint Layers
    for i, paint_layer in enumerate(terrain_doodad.paint_layers):
        paint_layer.index = i
    # Scatter Layers
    for i, scatter_layer in enumerate(terrain_doodad.scatter_layers):
        scatter_layer.index = i


def add_terrain_doodad_sculpt_layer(terrain_doodad: BDK_PG_terrain_doodad, name: str = 'Sculpt Layer') -> BDK_PG_terrain_doodad_sculpt_layer:
    sculpt_layer = terrain_doodad.sculpt_layers.add()
    sculpt_layer.id = uuid.uuid4().hex
    sculpt_layer.frozen_attribute_id = uuid.uuid4().hex
    sculpt_layer.terrain_doodad_object = terrain_doodad.object
    sculpt_layer.name = ensure_name_unique(name, [layer.name for layer in terrain_doodad.sculpt_layers])
    return sculpt_layer

def add_terrain_doodad_paint_layer(terrain_doodad: BDK_PG_terrain_doodad, name: str = 'Paint Layer') -> BDK_PG_terrain_doodad_paint_layer:
    paint_layer = terrain_doodad.paint_layers.add()
    paint_layer.id = uuid.uuid4().hex
    paint_layer.frozen_attribute_id = uuid.uuid4().hex
    paint_layer.terrain_doodad_object = terrain_doodad.object
    paint_layer.name = ensure_name_unique(name, [layer.name for layer in terrain_doodad.paint_layers])
    return paint_layer
