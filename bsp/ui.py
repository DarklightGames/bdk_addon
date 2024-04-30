from bpy.types import Panel, Context


def poll_is_active_object_bsp_brush(cls, context: Context):
    if context.active_object is None:
        return False
    if context.active_object.bdk.type != 'BSP_BRUSH':
        return False
    return True


def poll_is_active_object_level(cls, context: Context):
    if context.object is None:
        return False
    if context.object.bdk.type != 'LEVEL':
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

        brush = context.active_object.bdk.bsp_brush

        flow.prop(brush, 'poly_flags')


class BDK_PT_level(Panel):
    bl_idname = 'BDK_PT_level'
    bl_label = 'Level'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    @classmethod
    def poll(cls, context):
        return poll_is_active_object_level(cls, context)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        level = context.active_object.bdk.level

        geometry_header, geometry_panel = layout.panel('Geometry', default_closed=False)
        geometry_header.label(text='Geometry')

        if geometry_panel is not None:
            geometry_panel.prop(level, 'brush_count', emboss=False)
            geometry_panel.prop(level, 'zone_count', emboss=False)

        bsp_header, bsp_panel = layout.panel('BSP', default_closed=False)
        bsp_header.label(text='BSP')

        if bsp_panel is not None:
            layout.prop(level, 'poly_count', emboss=False)
            layout.prop(level, 'node_count', emboss=False)
            layout.prop(level, 'max_depth', emboss=False)
            layout.prop(level, 'average_depth', emboss=False)


classes = (
    BDK_PT_bsp_brush,
    BDK_PT_bsp_brush_poly_flags,
    BDK_PT_level,
)
