from bpy.types import Panel, Context


def poll_is_active_object_bsp_brush(cls, context: Context):
    if context.object is None:
        return False
    if context.object.bdk.type != 'BSP_BRUSH':
        return False
    return True


class BDK_PT_bsp_brush(Panel):
    bl_idname = 'BDK_PT_bsp_brush'
    bl_label = 'Brush'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    @classmethod
    def poll(cls, context):
        return poll_is_active_object_bsp_brush(cls, context)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        brush = context.object.bdk.bsp_brush
        layout.prop(brush, 'csg_operation')
        layout.prop(brush, 'sort_order')


class BDK_PT_bsp_brush_poly_flags(Panel):
    bl_idname = 'BDK_PT_bsp_brush_poly_flags'
    bl_label = 'Poly Flags'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_parent_id = 'BDK_PT_bsp_brush'

    @classmethod
    def poll(cls, context):
        return poll_is_active_object_bsp_brush(cls, context)

    def draw(self, context):
        layout = self.layout

        flow = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        brush = context.object.bdk.bsp_brush

        flow.prop(brush, 'poly_flags')


classes = (
    BDK_PT_bsp_brush,
    BDK_PT_bsp_brush_poly_flags,
)
