from typing import cast

import bpy
from bpy.types import Panel, Context, UIList

from ...helpers import should_show_bdk_developer_extras
from .operators import BDK_OT_terrain_object_sculpt_layer_add, BDK_OT_terrain_object_sculpt_layer_remove, \
    BDK_OT_terrain_object_paint_layer_add, BDK_OT_terrain_object_paint_layer_remove, \
    BDK_OT_terrain_object_paint_layer_duplicate, BDK_OT_terrain_object_sculpt_layer_duplicate, \
    BDK_OT_terrain_object_bake, BDK_OT_terrain_object_duplicate, BDK_OT_terrain_object_delete
from .properties import BDK_PG_terrain_object


class BDK_UL_terrain_object_sculpt_layers(UIList):

    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', icon='SCULPTMODE_HLT', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_object_paint_layers(UIList):

    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        if item.layer_type == 'PAINT':
            layout.label(text=item.paint_layer_name if item.paint_layer_name else '<no layer selected>', icon='VPAINT_HLT')
        elif item.layer_type == 'DECO':
            layout.label(text=item.deco_layer_name if item.deco_layer_name else '<no layer selected>', icon='MONKEY')
        layout.prop(item, 'operation', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_PT_terrain_object_paint_layer_settings(Panel):

    bl_idname = 'BDK_PT_terrain_object_paint_layer_settings'
    bl_label = 'Settings'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'BDK_PT_terrain_object_paint_layers'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.terrain_object

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_object = context.active_object.bdk.terrain_object
        paint_layer = terrain_object.paint_layers[terrain_object.paint_layers_index]
        flow = layout.grid_flow()

        row = flow.row()
        row.prop(paint_layer, 'layer_type', expand=True)

        if paint_layer.layer_type == 'PAINT':
            flow.prop(paint_layer, 'paint_layer_name')
        elif paint_layer.layer_type == 'DECO':
            row = flow.row()
            row.prop(paint_layer, 'deco_layer_name')
            deco_layer_object = bpy.data.objects[paint_layer.deco_layer_id] if paint_layer.deco_layer_id in bpy.data.objects else None
            if deco_layer_object:
                row.prop(deco_layer_object, 'hide_viewport', icon_only=True)

        flow.separator()

        flow.prop(paint_layer, 'interpolation_type')

        col = flow.column(align=True)
        col.prop(paint_layer, 'radius')
        col.prop(paint_layer, 'falloff_radius')
        col.prop(paint_layer, 'strength')

        flow.prop(paint_layer, 'use_distance_noise')

        if paint_layer.use_distance_noise:
            col = flow.column(align=True)
            col.prop(paint_layer, 'noise_type', icon='MOD_NOISE')
            col.prop(paint_layer, 'distance_noise_offset')
            col.prop(paint_layer, 'distance_noise_factor')
            if paint_layer.noise_type == 'PERLIN':
                col.prop(paint_layer, 'distance_noise_distortion')


class BDK_PT_terrain_object_paint_layers(Panel):
    bl_label = 'Paint Layers'
    bl_idname = 'BDK_PT_terrain_object_paint_layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object'
    bl_order = 1

    @classmethod
    def poll(cls, context: Context):
        # TODO: make sure there is at least one paint layer
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def draw(self, context: Context):
        layout = self.layout
        terrain_object = cast(BDK_PG_terrain_object, context.active_object.bdk.terrain_object)

        # Paint Components
        row = layout.row()

        row.template_list(
            'BDK_UL_terrain_object_paint_layers', '',
            terrain_object, 'paint_layers',
            terrain_object, 'paint_layers_index',
            sort_lock=True, rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_object_paint_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_object_paint_layer_remove.bl_idname, icon='REMOVE', text='')
        col.separator()
        col.operator(BDK_OT_terrain_object_paint_layer_duplicate.bl_idname, icon='DUPLICATE', text='')


class BDK_PT_terrain_object_operators(Panel):
    bl_idname = 'BDK_PT_terrain_object_operators'
    bl_label = 'Operators'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object'
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: 'Context'):
        self.layout.operator(BDK_OT_terrain_object_bake.bl_idname, icon='RENDER_RESULT')
        self.layout.operator(BDK_OT_terrain_object_duplicate.bl_idname, icon='DUPLICATE')
        self.layout.operator(BDK_OT_terrain_object_delete.bl_idname, icon='X')


class BDK_PT_terrain_object_debug(Panel):
    bl_idname = 'BDK_PT_terrain_object_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object'
    bl_order = 100
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        terrain_object: 'BDK_PG_terrain_object' = context.active_object.bdk.terrain_object
        self.layout.prop(terrain_object, 'id')
        self.layout.prop(terrain_object, 'object_type')
        self.layout.prop(terrain_object, 'object')
        self.layout.prop(terrain_object, 'node_tree')
        self.layout.prop(terrain_object, 'terrain_info_object')


class BDK_PT_terrain_object_advanced(Panel):
    bl_idname = 'BDK_PT_terrain_object_advanced'
    bl_label = 'Advanced'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object'
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: 'Context'):
        terrain_object: 'BDK_PG_terrain_object' = context.active_object.bdk.terrain_object
        flow = self.layout.grid_flow(align=True)
        flow.prop(terrain_object, 'sort_order')


class BDK_PT_terrain_object_sculpt_layer_settings(Panel):
    bl_idname = 'BDK_PT_terrain_object_sculpt_layer_settings'
    bl_label = 'Settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object_sculpt_layers'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_object = context.active_object.bdk.terrain_object
        sculpt_layer = terrain_object.sculpt_layers[terrain_object.sculpt_layers_index]
        flow = layout.grid_flow(align=True)
        flow.use_property_split = True

        col = flow.column(align=True)
        col.prop(sculpt_layer, 'radius')
        col.prop(sculpt_layer, 'falloff_radius')
        col.prop(sculpt_layer, 'interpolation_type')

        col.prop(sculpt_layer, 'depth')

        flow.separator()

        flow.prop(sculpt_layer, 'use_noise')

        if sculpt_layer.use_noise:
            flow.prop(sculpt_layer, 'noise_type')

            col = flow.column(align=True)

            if sculpt_layer.use_noise:
                col.prop(sculpt_layer, 'noise_radius_factor')
                if sculpt_layer.noise_type == 'PERLIN':
                    col.prop(sculpt_layer, 'noise_distortion')
                    col.prop(sculpt_layer, 'noise_roughness')
                    col.prop(sculpt_layer, 'noise_strength')


class BDK_PT_terrain_object_sculpt_layers(Panel):
    bl_idname = 'BDK_PT_terrain_object_sculpt_layers'
    bl_label = 'Sculpt Layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object'
    bl_order = 0

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def draw(self, context: Context):
        layout = self.layout
        terrain_object = cast(BDK_PG_terrain_object, context.active_object.bdk.terrain_object)

        row = layout.row()

        row.template_list('BDK_UL_terrain_object_sculpt_layers', '', terrain_object, 'sculpt_layers',
                          terrain_object, 'sculpt_layers_index', sort_lock=True, rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_object_sculpt_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_object_sculpt_layer_remove.bl_idname, icon='REMOVE', text='')

        col.separator()

        # operator = col.operator(BDK_OT_terrain_object_sculpt_layer_move.bl_idname, icon='TRIA_UP', text='')
        # operator.direction = 'UP'
        # operator = col.operator(BDK_OT_terrain_object_sculpt_layer_move.bl_idname, icon='TRIA_DOWN', text='')
        # operator.direction = 'DOWN'

        # col.separator()

        col.operator(BDK_OT_terrain_object_sculpt_layer_duplicate.bl_idname, icon='DUPLICATE', text='')


class BDK_PT_terrain_object(Panel):
    bl_label = 'Terrain Object'
    bl_idname = 'BDK_PT_terrain_object'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def draw(self, context: 'Context'):
        terrain_object = context.active_object.bdk.terrain_object
        layout = self.layout
        row = layout.row()


class BDK_PT_terrain_object_paint_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_object_paint_layer_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object_paint_layers'
    bl_order = 100

    @classmethod
    def poll(cls, context: 'Context'):
        # TODO: also check if we have a paint layer selected
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_object = context.active_object.bdk.terrain_object
        paint_layer = terrain_object.paint_layers[terrain_object.paint_layers_index]
        flow = layout.grid_flow(align=True)
        flow.use_property_split = True
        flow.row().prop(paint_layer, 'id')


class BDK_PT_terrain_object_sculpt_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_object_sculpt_layer_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_object_sculpt_layers'
    bl_order = 100

    @classmethod
    def poll(cls, context: 'Context'):
        # TODO: also check if we have a paint layer selected
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_object = context.active_object.bdk.terrain_object
        sculpt_layer = terrain_object.sculpt_layers[terrain_object.sculpt_layers_index]
        flow = layout.grid_flow(align=True)
        flow.use_property_split = True
        flow.row().prop(sculpt_layer, 'id')


classes = (
    BDK_PT_terrain_object,
    BDK_UL_terrain_object_sculpt_layers,
    BDK_PT_terrain_object_sculpt_layers,
    BDK_PT_terrain_object_sculpt_layer_settings,
    BDK_PT_terrain_object_sculpt_layer_debug,
    BDK_UL_terrain_object_paint_layers,
    BDK_PT_terrain_object_paint_layers,
    BDK_PT_terrain_object_paint_layer_settings,
    BDK_PT_terrain_object_paint_layer_debug,
    BDK_PT_terrain_object_advanced,
    BDK_PT_terrain_object_operators,
    BDK_PT_terrain_object_debug,
)
