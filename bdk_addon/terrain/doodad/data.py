terrain_doodad_operation_items = [
    ('ADD', 'Add', 'Add paint to the terrain layer'),
    ('SUBTRACT', 'Subtract', 'Subtract paint from the terrain layer'),
]

terrain_doodad_noise_type_items = [
    ('WHITE', 'White Noise', 'White noise', '', 0),
    ('PERLIN', 'Perlin', 'Perlin noise', '', 1),
]

terrain_doodad_type_items = [
    ('CURVE', 'Curve', '', 'CURVE_DATA', 0),
    ('MESH', 'Mesh', '', 'MESH_DATA', 1),
    ('EMPTY', 'Empty', '', 'EMPTY_DATA', 2),
]

terrain_doodad_geometry_source_items = (
    ('DOODAD', 'Doodad', 'Use the terrain doodad object\'s geometry'),
    ('SCATTER_LAYER', 'Scatter Layer', 'Use the points of a scatter layer')
)
