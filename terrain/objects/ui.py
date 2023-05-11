from typing import cast

from bpy.types import Panel, Context, UIList

from .operators import BDK_OT_terrain_object_bake, BDK_OT_terrain_object_sculpt_component_add, \
    BDK_OT_terrain_object_sculpt_component_remove, BDK_OT_terrain_object_sculpt_component_move, \
    BDK_OT_terrain_object_paint_component_add, BDK_OT_terrain_object_paint_component_remove
from .properties import BDK_PG_terrain_object


class BDK_UL_terrain_object_sculpt_components(UIList):

    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', icon='SCULPTMODE_HLT', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_object_paint_components(UIList):

    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.terrain_layer_name if item.terrain_layer_name else '<no layer selected>', icon='VPAINT_HLT')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_PT_terrain_object_paint_layers(Panel):
    bl_label = 'Paint Layers'
    bl_idname = 'BDK_PT_terrain_object_paint_layers'
    bl_category = 'Terrain'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def draw(self, context: Context):
        layout = self.layout
        terrain_object = cast(BDK_PG_terrain_object, context.active_object.bdk.terrain_object)

        # Paint Components
        row = layout.row()

        row.template_list('BDK_UL_terrain_object_paint_components', '', terrain_object, 'paint_components',
                          terrain_object, 'paint_components_index', sort_lock=True, rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_object_paint_component_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_object_paint_component_remove.bl_idname, icon='REMOVE', text='')

        layout.separator()

        paint_component = terrain_object.paint_components[terrain_object.paint_components_index]

        if paint_component:
            flow = layout.grid_flow()

            flow.prop(paint_component, 'terrain_layer_name')

            flow.prop(paint_component, 'operation')
            flow.prop(paint_component, 'interpolation_type')

            col = flow.column(align=True)
            col.prop(paint_component, 'radius')
            col.prop(paint_component, 'falloff_radius')
            col.prop(paint_component, 'strength')

            flow.prop(paint_component, 'use_distance_noise')

            if paint_component.use_distance_noise:
                col = flow.column(align=True)
                col.prop(paint_component, 'distance_noise_factor')
                col.prop(paint_component, 'distance_noise_distortion')
                col.prop(paint_component, 'distance_noise_offset')


class BDK_PT_terrain_object_sculpt_players(Panel):
    bl_idname = 'BDK_PT_terrain_object_sculpt_players'
    bl_label = 'Sculpt Layers'
    bl_category = 'Terrain'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def draw(self, context: Context):
        layout = self.layout
        terrain_object = cast(BDK_PG_terrain_object, context.active_object.bdk.terrain_object)

        row = layout.row()

        row.template_list('BDK_UL_terrain_object_sculpt_components', '', terrain_object, 'sculpt_components',
                          terrain_object, 'sculpt_components_index', sort_lock=True, rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_object_sculpt_component_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_object_sculpt_component_remove.bl_idname, icon='REMOVE', text='')
        col.separator()
        operator = col.operator(BDK_OT_terrain_object_sculpt_component_move.bl_idname, icon='TRIA_UP', text='')
        operator.direction = 'UP'
        operator = col.operator(BDK_OT_terrain_object_sculpt_component_move.bl_idname, icon='TRIA_DOWN', text='')
        operator.direction = 'DOWN'

        sculpt_component = terrain_object.sculpt_components[terrain_object.sculpt_components_index]

        if sculpt_component:
            flow = layout.grid_flow()

            col = flow.column(align=True)
            col.prop(sculpt_component, 'radius')
            col.prop(sculpt_component, 'falloff_radius')
            col.prop(sculpt_component, 'interpolation_type')

            col.prop(sculpt_component, 'depth')

            flow.separator()

            flow.prop(sculpt_component, 'use_noise')

            col = flow.column(align=True)

            if sculpt_component.use_noise:
                col.prop(sculpt_component, 'noise_radius_factor')
                col.prop(sculpt_component, 'noise_distortion')
                col.prop(sculpt_component, 'noise_strength')
                col.prop(sculpt_component, 'noise_roughness')


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
        # layout.prop(terrain_object, 'is_3d')
        layout.operator(BDK_OT_terrain_object_bake.bl_idname)


classes = (
    BDK_PT_terrain_object,
    BDK_UL_terrain_object_sculpt_components,
    BDK_UL_terrain_object_paint_components,
    BDK_PT_terrain_object_sculpt_players,
    BDK_PT_terrain_object_paint_layers,
)
