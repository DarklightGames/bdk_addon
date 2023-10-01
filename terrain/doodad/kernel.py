
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
