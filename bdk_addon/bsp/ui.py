from bpy.types import Panel, Context

from ..helpers import should_show_bdk_developer_extras
from ..bsp.operators import BDK_OT_apply_level_texturing_to_brushes, BDK_OT_ensure_tool_operators, BDK_OT_bsp_build


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
            flow = poly_flags_panel.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
            flow.use_property_split = True
            flow.use_property_decorate = False

            flow.prop(brush, 'poly_flags')

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
        layout.prop(context.scene.bdk.level_object, 'hide_viewport', text='', icon_only=True, icon='HIDE_ON' if context.scene.bdk.level_object.hide_viewport else 'HIDE_OFF', emboss=False)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        level = context.scene.bdk.level_object.bdk.level
        statistics = level.statistics

        visibility_header, visibility_panel = layout.panel('Visibility', default_closed=True)
        visibility_header.label(text='Visibility')

        if visibility_panel is not None:
            visibility_panel.use_property_split = False
            visibility_properties = ('fake_backdrop', 'invisible', 'portal')
            for visibility_property in visibility_properties:
                visibility_panel.prop(level.visibility, visibility_property, icon='HIDE_ON' if getattr(level.visibility, visibility_property) else 'HIDE_OFF', emboss=False)

        statistics_header, statistics_panel = layout.panel('Statistics', default_closed=True)
        statistics_header.label(text='Statistics')

        if statistics_panel is not None:
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

        performance_header, performance_panel = layout.panel('Performance', default_closed=True)
        performance_header.label(text='Performance')

        if performance_panel is not None:
            performance = level.performance
            performance_panel.prop(performance, 'object_serialization_duration', emboss=False)
            performance_panel.prop(performance, 'csg_build_duration', emboss=False)
            performance_panel.prop(performance, 'mesh_build_duration', emboss=False)

        operators_header, operators_panel = layout.panel('Operators', default_closed=True)
        operators_header.label(text='Operators')

        if operators_panel is not None:
            operators_panel.operator(BDK_OT_apply_level_texturing_to_brushes.bl_idname, icon='TEXTURE')
            operators_panel.operator(BDK_OT_bsp_build.bl_idname, icon='MOD_BUILD')

        if should_show_bdk_developer_extras(context):
            debug_header, debug_panel = layout.panel('Debug', default_closed=True)
            debug_header.label(text='Debug')

            if debug_panel is not None:
                debug_panel.operator(BDK_OT_ensure_tool_operators.bl_idname, icon='TOOL_SETTINGS')


classes = (
    BDK_PT_bsp_brush,
    BDK_PT_level,
)
