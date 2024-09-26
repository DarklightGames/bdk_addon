from enum import IntFlag, Enum


class PolyFlags(IntFlag):
    Invisible = 0x00000001
    Masked = 0x00000002
    Translucent = 0x00000004
    NotSolid = 0x00000008
    Environment = 0x00000010
    SemiSolid = 0x00000020
    Modulated = 0x00000040
    FakeBackdrop = 0x00000080
    TwoSided = 0x00000100
    NoSmooth = 0x00000800
    AlphaTexture = 0x00001000
    Flat = 0x00004000
    NoMerge = 0x00010000
    NoZTest = 0x00020000
    Additive = 0x00040000
    SpecialLit = 0x00100000
    Wireframe = 0x00200000
    Unlit = 0x00400000
    Portal = 0x04000000
    AntiPortal = 0x08000000
    Mirrored = 0x20000000
    EdProcessed = 0x40000000
    EdCut = 0x80000000


class CsgOperation(Enum):
    Add = 0
    Subtract = 1


bsp_optimization_items = (
    ('LAME', 'Lame', '', 0),
    ('GOOD', 'Good', '', 1),
    ('OPTIMAL', 'Optimal', '', 2),
)

BRUSH_INDEX_ATTRIBUTE_NAME = 'bdk.brush_index'
BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME = 'bdk.brush_polygon_index'
DIRTY_ATTRIBUTE_NAME = 'bdk.dirty'
LIGHT_MAP_SCALE_ATTRIBUTE_NAME = 'bdk.light_map_scale'
MATERIAL_INDEX_ATTRIBUTE_NAME = 'material_index'
NORMAL_ATTRIBUTE_NAME = 'normal'
ORIGIN_ATTRIBUTE_NAME = 'bdk.origin'
POLY_FLAGS_ATTRIBUTE_NAME = 'bdk.poly_flags'
TEXTURE_U_ATTRIBUTE_NAME = 'bdk.texture_u'
TEXTURE_V_ATTRIBUTE_NAME = 'bdk.texture_v'
READ_ONLY_ATTRIBUTE_NAME = 'bdk.read_only'

bsp_surface_attributes = (
    (BRUSH_INDEX_ATTRIBUTE_NAME, 'INT', 'FACE'),
    (BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME, 'INT', 'FACE'),
    (DIRTY_ATTRIBUTE_NAME, 'BOOLEAN', 'FACE'),
    (ORIGIN_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE'),
    (TEXTURE_U_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE'),
    (TEXTURE_V_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE'),
    (MATERIAL_INDEX_ATTRIBUTE_NAME, 'INT', 'FACE'),
    (POLY_FLAGS_ATTRIBUTE_NAME, 'INT', 'FACE'),
    (READ_ONLY_ATTRIBUTE_NAME, 'BOOLEAN', 'FACE'),
)
