from bpy.types import Panel, Context

from .operators import BDK_OT_projector_bake, BDK_OT_projector_unbake


def poll_is_projector_active_object(context: Context) -> bool:
    return context.active_object and context.active_object.bdk.type == 'PROJECTOR'


class BDK_PT_projector(Panel):
    bl_idname = 'BDK_PT_projector'
    bl_label = 'Projector'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    @classmethod
    def poll(cls, context: Context) -> bool:
        return poll_is_projector_active_object(context)

    def draw(self, context: Context):
        depsgraph = context.evaluated_depsgraph_get()

        evaluated_object = context.active_object.evaluated_get(depsgraph)

        projector = context.active_object.bdk.projector
        modifier = evaluated_object.modifiers['Projector']

        layout = self.layout

        if not projector.is_baked:
            layout.operator(BDK_OT_projector_bake.bl_idname, text='Bake')
        else:
            layout.operator(BDK_OT_projector_unbake.bl_idname, text='Unbake')

        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(projector, 'proj_texture')
        layout.separator()
        layout.prop(projector, 'fov')
        layout.prop(projector, 'max_trace_distance')
        layout.prop(projector, 'draw_scale')
        layout.separator()

        appearance_header, appearance_panel = layout.panel('Appearance', default_closed=False)
        appearance_header.label(text='Appearance')

        if appearance_panel:
            appearance_panel.prop(projector, 'gradient')
            appearance_panel.prop(projector, 'material_blending_op', text='Material Blending')
            appearance_panel.prop(projector, 'frame_buffer_blending_op', text='Frame Buffer')

        performance_header, performance_panel = layout.panel('Performance', default_closed=True)
        performance_header.label(text='Performance')
        if performance_panel:
            performance_panel.prop(modifier, 'execution_time', emboss=False)


classes = (
    BDK_PT_projector,
)
