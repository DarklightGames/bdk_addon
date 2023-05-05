from typing import cast

from bpy.types import Panel, Context, UIList

from .properties import BDK_PG_terrain_object


class BDK_UL_terrain_object_sculpt_components(UIList):

    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=str(item.name))


class BDK_PT_terrain_object(Panel):
    bl_label = 'Terrain Object'
    bl_idname = 'BDK_PT_terrain_object'
    bl_category = 'Terrain'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def draw(self, context: Context):
        layout = self.layout
        terrain_object = cast(BDK_PG_terrain_object, context.active_object.bdk.terrain_object)

        layout.prop(terrain_object, 'is_3d')

        for paint_component in terrain_object.paint_components:
            layout.label(text=str(paint_component))

            # layout.prop(paint_component, 'radius')

        for sculpt_component in terrain_object.sculpt_components:
            layout.label(text=str(sculpt_component))

            flow = layout.grid_flow()

            col = flow.column(align=True)
            col.prop(sculpt_component, 'radius')
            col.prop(sculpt_component, 'falloff_radius')
            col.prop(sculpt_component, 'depth')

            flow.separator()

            flow.prop(sculpt_component, 'use_noise')

            col = flow.column(align=True)

            if sculpt_component.use_noise:
                col.prop(sculpt_component, 'noise_radius_factor')
                col.prop(sculpt_component, 'noise_distortion')
                col.prop(sculpt_component, 'noise_strength')
                col.prop(sculpt_component, 'noise_roughness')


classes = (
    BDK_PT_terrain_object,
    BDK_UL_terrain_object_sculpt_components,
)
