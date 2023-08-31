from enum import Enum, IntFlag
from typing import Set

from bpy.types import PropertyGroup, Object, Context
from bpy.props import EnumProperty, PointerProperty, IntProperty


class BrushColors(Enum):
    Subtract    = (1.0, 0.75, 0.25, 1.0)
    Add         = (0.5, 0.5, 1.0, 1.0)
    Grey        = (0.6367, 0.6367, 0.6367, 1.0)
    Portal      = (0.5, 1.0, 0.0, 1.0)
    NotSolid    = (0.25, 0.75, 0.125, 1.0)
    SemiSolid   = (0.875, 0.6, 0.6, 1.0)


class PolyFlags(IntFlag):
    Invisible       = 0x00000001
    Masked          = 0x00000002
    Translucent     = 0x00000004
    NotSolid        = 0x00000008
    Environment     = 0x00000010
    SemiSolid       = 0x00000020
    Modulated       = 0x00000040
    FakeBackdrop    = 0x00000080
    TwoSided        = 0x00000100
    NoSmooth        = 0x00000800
    AlphaTexture    = 0x00001000
    Flat            = 0x00004000
    NoMerge         = 0x00010000
    NoZTest         = 0x00020000
    Additive        = 0x00040000
    SpecialLit      = 0x00100000
    Wireframe       = 0x00200000
    Unlit           = 0x00400000
    Portal          = 0x04000000
    AntiPortal      = 0x08000000
    Mirrored        = 0x20000000


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
        return BrushColors.Grey.value


csg_operation_items = (
    ('CSG_Add', 'Add', 'Add to world', 1),
    ('CSG_Subtract', 'Subtract', 'Subtract from world', 2),
    ('CSG_Intersect', 'Intersect', 'Form from intersection with world', 3),
    ('CSG_Deintersect', 'De-intersect', 'Form from negative intersection with world', 4),
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

poly_flag_values = {key: value for key, _, _, _, value in poly_flags_items}


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