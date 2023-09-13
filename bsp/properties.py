from enum import Enum
from typing import Set

from bpy.types import PropertyGroup, Object, Context
from bpy.props import EnumProperty, PointerProperty, IntProperty

from .data import PolyFlags


class BrushColors(Enum):
    Subtract    = (1.0, 0.75, 0.25, 1.0)
    Add         = (0.5, 0.5, 1.0, 1.0)
    Grey        = (0.6367, 0.6367, 0.6367, 1.0)
    Portal      = (0.5, 1.0, 0.0, 1.0)
    NotSolid    = (0.25, 0.75, 0.125, 1.0)
    SemiSolid   = (0.875, 0.6, 0.6, 1.0)


def get_brush_color(csg_operation: str, poly_flags: Set[str]) -> tuple[float, float, float, float]:
    if csg_operation == 'CSG_Add':
        if 'PORTAL' in poly_flags:
            return BrushColors.Portal.value
        elif 'NOT_SOLID' in poly_flags:
            return BrushColors.NotSolid.value
        elif 'SEMI_SOLID' in poly_flags:
            return BrushColors.SemiSolid.value
        else:
            return BrushColors.Add.value
    elif csg_operation == 'CSG_Subtract':
        return BrushColors.Subtract.value
    else:
        # This should never happen, but it was used for intersect and de-intersect brushes in the original editor.
        return BrushColors.Grey.value


csg_operation_items = (
    ('CSG_Add', 'Add', 'Add to world', 1),
    ('CSG_Subtract', 'Subtract', 'Subtract from world', 2),
)

poly_flags_items = (
    ('INVISIBLE', 'Invisible', 'Poly is invisible.', 0, PolyFlags.Invisible.value),
    ('MASKED', 'Masked', 'Poly should be drawn masked.', 0, PolyFlags.Masked.value),
    ('TRANSLUCENT', 'Translucent', 'Poly is transparent.', 0, PolyFlags.Translucent.value),
    ('NOT_SOLID', 'Not Solid', 'Poly is not solid, doesn\'t block.', 0, PolyFlags.NotSolid.value),
    ('ENVIRONMENT', 'Environment', 'Poly should be drawn environment mapped.', 0, PolyFlags.Environment.value),
    ('SEMI_SOLID', 'Semi-Solid', 'Poly is semi-solid = collision solid, Csg nonsolid.', 0, PolyFlags.SemiSolid.value),
    ('MODULATED', 'Modulated', 'Modulation transparency.', 0, PolyFlags.Modulated.value),
    ('FAKE_BACKDROP', 'Fake Backdrop', 'Poly looks exactly like backdrop.', 0, PolyFlags.FakeBackdrop.value),
    ('TWO_SIDED', 'Two-Sided', 'Poly is visible from both sides.', 0, PolyFlags.TwoSided.value),
    ('NO_SMOOTH', 'No Smooth', 'Don\'t smooth textures.', 0, PolyFlags.NoSmooth.value),
    ('ALPHA_TEXTURE', 'Alpha Texture', 'Honor texture alpha (reuse BigWavy and SpecialPoly flags)', 0, PolyFlags.AlphaTexture.value),
    ('FLAT', 'Flat', 'Flat surface.', 0, PolyFlags.Flat.value),
    ('NO_MERGE', 'No Merge', 'Don\'t merge poly\'s nodes before lighting when rendering.', 0, PolyFlags.NoMerge.value),
    ('NO_Z_TEST', 'No Z Test', 'Don\'t test Z buffer', 0, PolyFlags.NoZTest.value),
    ('ADDITIVE', 'Additive', 'sjs - additive blending, (Aliases PF_DirtyShadows).', 0, PolyFlags.Additive.value),
    ('SPECIAL_LIT', 'Special Lit', 'Only speciallit lights apply to this poly.', 0, PolyFlags.SpecialLit.value),
    ('WIREFRAME', 'Wireframe', 'Render as wireframe', 0, PolyFlags.Wireframe.value),
    ('UNLIT', 'Unlit', 'Unlit.', 0, PolyFlags.Unlit.value),
    ('PORTAL', 'Portal', 'Portal between iZones.', 0, PolyFlags.Portal.value),
    ('ANTI_PORTAL', 'Anti-Portal', 'Antiportal', 0, PolyFlags.AntiPortal.value),
    ('MIRRORED', 'Mirrored', 'Mirrored BSP surface.', 0, PolyFlags.Mirrored.value),
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

class BDK_PG_bsp_brush(PropertyGroup):
    object: PointerProperty(type=Object, name='Object', description='The object this property group is attached to', options={'HIDDEN'})
    csg_operation: EnumProperty(
        name='CSG Operation',
        description='The CSG operation to perform when this brush is applied to the world',
        items=csg_operation_items,
        default='CSG_Add',
        update=bsp_brush_update,
        options=empty_set
    )
    poly_flags: EnumProperty(
        name='Poly Flags',
        description='The flags to apply to the polygons of this brush',
        items=poly_flags_items,
        default=set(),
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


classes = (
    BDK_PG_bsp_brush,
)
