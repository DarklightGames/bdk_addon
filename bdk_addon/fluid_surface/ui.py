from bpy.types import Panel


class BDK_PT_fluid_surface(Panel):
    bl_label = 'Fluid Surface'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.bdk.type == 'FLUID_SURFACE'

    def draw(self, context):
        layout = self.layout
        fluid_surface = context.active_object.bdk.fluid_surface

        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(fluid_surface, 'fluid_grid_type')
        flow.prop(fluid_surface, 'material')
        flow.prop(fluid_surface, 'fluid_x_size')
        flow.prop(fluid_surface, 'fluid_y_size')
        flow.prop(fluid_surface, 'fluid_grid_spacing')
        flow.prop(fluid_surface, 'u_offset')
        flow.prop(fluid_surface, 'v_offset')


classes = (
    BDK_PT_fluid_surface,
)
