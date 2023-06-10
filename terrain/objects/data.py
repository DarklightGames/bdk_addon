terrain_object_operation_items = [
    ('ADD', 'Add', 'Add paint to the terrain layer.'),
    ('SUBTRACT', 'Subtract', 'Subtract paint from the terrain layer.'),
]

terrain_object_noise_type_items = [
    ('PERLIN', 'Perlin', 'Perlin noise.'),
    ('WHITE', 'White Noise', 'White noise.'),
]

map_range_interpolation_type_items = [
    ('LINEAR', 'Linear', 'Linear interpolation between From Min and From Max values.', 'LINCURVE', 0),
    ('STEPPED', 'Stepped', 'Stepped linear interpolation between From Min and From Max values.', 'IPO_CONSTANT', 1),
    ('SMOOTHSTEP', 'Smooth Step', 'Smooth Hermite edge interpolation between From Min and From Max values.', 'IPO_EASE_IN', 2),
    ('SMOOTHERSTEP', 'Smoother Step', 'Smoother Hermite edge interpolation between From Min and From Max values.', 'IPO_EASE_IN_OUT', 3),
]

terrain_object_type_items = [
    ('CURVE', 'Curve', '', 'CURVE_DATA', 0),
    ('MESH', 'Mesh', '', 'MESH_DATA', 1),
    ('EMPTY', 'Empty', '', 'EMPTY_DATA', 2),
]
