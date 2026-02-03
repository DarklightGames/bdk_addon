from bpy.types import Panel, Context

from ..fog.ui import draw_fog_settings

from ..bsp.operators import BDK_OT_bsp_build


def poll_is_active_object_bsp_brush(cls, context: Context):
    if context.active_object is None or context.active_object.bdk.type != 'BSP_BRUSH':
        return False
    return True


def poll_is_active_object_level(cls, context: Context):
    if context.object is None or context.active_object.bdk.type != 'LEVEL':
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
        brush = context.object.bdk.bsp_brush

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop(brush, 'csg_operation', text='Operation')

        poly_flags_header, poly_flags_panel = layout.panel('Poly Flags', default_closed=True)
        poly_flags_header.label(text='Poly Flags')

        if poly_flags_panel is not None:
            poly_flags_panel.use_property_split = True
            poly_flags_panel.use_property_decorate = False
            poly_flags_panel.prop(brush, 'poly_flags')

        advanced_header, advanced_panel = layout.panel('Advanced', default_closed=True)
        advanced_header.label(text='Advanced')

        if advanced_panel is not None:
            flow = advanced_panel.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
            flow.use_property_split = True
            flow.use_property_decorate = False
            flow.prop(brush, 'sort_order')


class BDK_PT_level(Panel):
    bl_idname = 'BDK_PT_level'
    bl_label = 'Level'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    @classmethod
    def poll(cls, context):
        return context.scene.bdk.level_object is not None

    def draw_header(self, context):
        layout = self.layout
        row = layout.row(align=True)
        level_object = context.scene.bdk.level_object
        row.prop(level_object, 'hide_select', text='', emboss=False)
        row.prop(level_object, 'hide_viewport', text='', emboss=False)

    def draw(self, context):
        layout = self.layout
        assert layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        level = context.scene.bdk.level_object.bdk.level
        statistics = level.statistics

        layout.operator(BDK_OT_bsp_build.bl_idname, text='Build')

        draw_fog_settings(layout, context)

        visibility_header, visibility_panel = layout.panel('Visibility', default_closed=True)
        visibility_header.label(text='Visibility')

        if visibility_panel is not None:
            col = visibility_panel.column(align=True)
            visibility_properties = ('fake_backdrop', 'invisible', 'portal')
            for visibility_property in visibility_properties:
                col.prop(level.visibility, visibility_property)

        statistics_header, statistics_panel = layout.panel('Statistics', default_closed=True)
        statistics_header.label(text='Statistics')

        if statistics_panel is not None:
            statistics_panel.enabled = False
            geometry_header, geometry_panel = statistics_panel.panel('Geometry', default_closed=True)
            geometry_header.label(text='Geometry')

            if geometry_panel is not None:
                geometry_panel.prop(statistics, 'brush_count', emboss=False)
                geometry_panel.prop(statistics, 'zone_count', emboss=False)

            bsp_header, bsp_panel = statistics_panel.panel('BSP', default_closed=True)
            bsp_header.label(text='BSP')

            if bsp_panel is not None:
                bsp_panel.prop(statistics, 'node_count', emboss=False)
                bsp_panel.prop(statistics, 'depth_count', emboss=False)
                bsp_panel.prop(statistics, 'depth_max', emboss=False)
                bsp_panel.prop(statistics, 'depth_average', emboss=False)

            performance_header, performance_panel = statistics_panel.panel('Performance', default_closed=True)
            performance_header.label(text='Performance')

            if performance_panel is not None:
                performance = level.performance
                performance_panel.prop(performance, 'object_serialization_duration', emboss=False)
                performance_panel.prop(performance, 'csg_build_duration', emboss=False)
                performance_panel.prop(performance, 'mesh_build_duration', emboss=False)


classes = (
    BDK_PT_bsp_brush,
    BDK_PT_level,
)
