from .data import PolyFlags, bsp_optimization_items
from bpy.props import EnumProperty, PointerProperty, IntProperty, CollectionProperty, FloatProperty, FloatVectorProperty
from bpy.types import PropertyGroup, Object, Context, Material
from enum import Enum
from typing import Set


class BrushColors(Enum):
    Subtract = (1.0, 0.75, 0.25, 1.0)
    Add = (0.5, 0.5, 1.0, 1.0)
    Grey = (0.6367, 0.6367, 0.6367, 1.0)
    Portal = (0.5, 1.0, 0.0, 1.0)
    NotSolid = (0.25, 0.75, 0.125, 1.0)
    SemiSolid = (0.875, 0.6, 0.6, 1.0)


def get_brush_color(csg_operation: str, poly_flags: Set[str]) -> tuple[float, float, float, float]:
    if csg_operation == 'ADD':
        if 'PORTAL' in poly_flags:
            return BrushColors.Portal.value
        elif 'NOT_SOLID' in poly_flags:
            return BrushColors.NotSolid.value
        elif 'SEMI_SOLID' in poly_flags:
            return BrushColors.SemiSolid.value
        else:
            return BrushColors.Add.value
    elif csg_operation == 'SUBTRACT':
        return BrushColors.Subtract.value
    else:
        # This should never happen, but it was used for intersect and de-intersect brushes in the original editor.
        return BrushColors.Grey.value


csg_operation_items = (
    ('ADD', 'Add', 'Add to world', 1),
    ('SUBTRACT', 'Subtract', 'Subtract from world', 2),
)

poly_flags_items = (
    ('ADDITIVE', 'Additive', 'sjs - additive blending, (Aliases PF_DirtyShadows).', 0, PolyFlags.Additive.value),
    ('ALPHA_TEXTURE', 'Alpha Texture', 'Honor texture alpha (reuse BigWavy and SpecialPoly flags)', 0,
     PolyFlags.AlphaTexture.value),
    ('ANTI_PORTAL', 'Anti-Portal', 'Antiportal', 0, PolyFlags.AntiPortal.value),
    ('ENVIRONMENT', 'Environment', 'Poly should be drawn environment mapped.', 0, PolyFlags.Environment.value),
    ('FAKE_BACKDROP', 'Fake Backdrop', 'Poly looks exactly like backdrop.', 0, PolyFlags.FakeBackdrop.value),
    ('FLAT', 'Flat', 'Flat surface.', 0, PolyFlags.Flat.value),
    ('INVISIBLE', 'Invisible', 'Poly is invisible.', 0, PolyFlags.Invisible.value),
    ('MASKED', 'Masked', 'Poly should be drawn masked.', 0, PolyFlags.Masked.value),
    ('MIRRORED', 'Mirrored', 'Mirrored BSP surface.', 0, PolyFlags.Mirrored.value),
    ('MODULATED', 'Modulated', 'Modulation transparency.', 0, PolyFlags.Modulated.value),
    ('NOT_SOLID', 'Not Solid', 'Poly is not solid, doesn\'t block.', 0, PolyFlags.NotSolid.value),
    ('NO_MERGE', 'No Merge', 'Don\'t merge poly\'s nodes before lighting when rendering.', 0, PolyFlags.NoMerge.value),
    ('NO_SMOOTH', 'No Smooth', 'Don\'t smooth textures.', 0, PolyFlags.NoSmooth.value),
    ('NO_Z_TEST', 'No Z Test', 'Don\'t test Z buffer', 0, PolyFlags.NoZTest.value),
    ('PORTAL', 'Portal', 'Portal between iZones.', 0, PolyFlags.Portal.value),
    ('SEMI_SOLID', 'Semi-Solid', 'Poly is semi-solid = collision solid, Csg nonsolid.', 0, PolyFlags.SemiSolid.value),
    ('SPECIAL_LIT', 'Special Lit', 'Only speciallit lights apply to this poly.', 0, PolyFlags.SpecialLit.value),
    ('TRANSLUCENT', 'Translucent', 'Poly is transparent.', 0, PolyFlags.Translucent.value),
    ('TWO_SIDED', 'Two-Sided', 'Poly is visible from both sides.', 0, PolyFlags.TwoSided.value),
    ('UNLIT', 'Unlit', 'Unlit.', 0, PolyFlags.Unlit.value),
    ('WIREFRAME', 'Wireframe', 'Render as wireframe', 0, PolyFlags.Wireframe.value),
)

__poly_flag_keys_to_values__ = {key: value for key, _, _, _, value in poly_flags_items}
__poly_flag_values_to_keys__ = {value: key for key, _, _, _, value in poly_flags_items}


def get_poly_flags_value_from_keys(keys: Set[str]) -> int:
    poly_flags: int = 0
    for key in keys:
        poly_flags |= __poly_flag_keys_to_values__[key]
    return poly_flags


def get_poly_flags_keys_from_value(values: int) -> Set[str]:
    poly_flags: Set[str] = set()
    for value, key in __poly_flag_values_to_keys__.items():
        if values & value:
            poly_flags.add(key)
    return poly_flags


def bsp_brush_update(self, context: Context):
    self.object.color = get_brush_color(self.csg_operation, self.poly_flags)


empty_set = set()


class BDK_PG_level_brush(PropertyGroup):
    index: IntProperty('ID')
    brush_object: PointerProperty(type=Object, name='Brush Object')


class BDK_PG_bsp_brush(PropertyGroup):
    object: PointerProperty(type=Object, name='Object', description='The object this property group is attached to',
                            options={'HIDDEN'})
    csg_operation: EnumProperty(
        name='CSG Operation',
        description='The CSG operation to perform when this brush is applied to the world',
        items=csg_operation_items,
        default='ADD',
        update=bsp_brush_update,
        options=empty_set
    )
    poly_flags: EnumProperty(
        name='Poly Flags',
        description='The flags to apply to the polygons of this brush',
        items=poly_flags_items,
        default=empty_set,
        options={'ENUM_FLAG'},
        update=bsp_brush_update,
    )
    sort_order: IntProperty(
        name='Sort Order',
        description='The sort order of this brush. Lower values are evaluated first',
        default=0,
        min=0,
        max=8,  # This is not strictly necessary, but will stop the levelers from using insane values.
    )


class BDK_PG_level_performance(PropertyGroup):
    object_serialization_duration: FloatProperty(name='Object Serialization', unit='TIME_ABSOLUTE')
    csg_build_duration: FloatProperty(name='CSG Build', unit='TIME_ABSOLUTE')
    mesh_build_duration: FloatProperty(name='Mesh Build', unit='TIME_ABSOLUTE')


class BDK_PG_level_statistics(PropertyGroup):
    brush_count: IntProperty(name='Brush Count')
    zone_count: IntProperty(name='Zone Count')
    node_count: IntProperty(name='Node Count')
    # TODO: section count?
    surface_count: IntProperty(name='Surface Count')
    depth_count: IntProperty(name='Depth Count')
    depth_max: IntProperty(name='Depth Max', description='The maximum depth of any BSP leaf node')
    depth_average: FloatProperty(name='Depth Average', precision=2, description='The average depth of each BSP leaf node')


class BDK_PG_level(PropertyGroup):
    brushes: CollectionProperty(type=BDK_PG_level_brush, options={'HIDDEN'},
                                description='The list of brush objects used in generating the level geometry. '
                                            'This is used as a look-up table so that texturing work done on the '
                                            'level geometry can be applied to the associated brush polygons')
    statistics: PointerProperty(type=BDK_PG_level_statistics, options={'HIDDEN'})
    performance: PointerProperty(type=BDK_PG_level_performance, options={'HIDDEN'})
    bsp_optimization: EnumProperty(items=bsp_optimization_items, name='Optimization', default='LAME')


classes = (
    BDK_PG_bsp_brush,
    BDK_PG_level_performance,
    BDK_PG_level_statistics,
    BDK_PG_level_brush,
    BDK_PG_level,
)
