from typing import cast

import bpy
from bpy.types import Panel, Context, UIList

from ...helpers import should_show_bdk_developer_extras, get_terrain_doodad
from .operators import BDK_OT_terrain_doodad_sculpt_layer_add, BDK_OT_terrain_doodad_sculpt_layer_remove, \
    BDK_OT_terrain_doodad_paint_layer_add, BDK_OT_terrain_doodad_paint_layer_remove, \
    BDK_OT_terrain_doodad_paint_layer_duplicate, BDK_OT_terrain_doodad_sculpt_layer_duplicate, \
    BDK_OT_terrain_doodad_bake, BDK_OT_terrain_doodad_duplicate, BDK_OT_terrain_doodad_delete, \
    BDK_OT_terrain_doodad_scatter_layer_add, BDK_OT_terrain_doodad_scatter_layer_remove, \
    BDK_OT_terrain_doodad_scatter_layer_objects_add, BDK_OT_terrain_doodad_scatter_layer_objects_remove
from .properties import BDK_PG_terrain_doodad


class BDK_UL_terrain_doodad_scatter_layer_objects(UIList):
    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', emboss=False, text='', icon='OBJECT_DATA')
        layout.prop(item, 'random_weight', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_doodad_scatter_layers(UIList):
    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', icon='PARTICLE_POINT', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_doodad_sculpt_layers(UIList):
    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', icon='SCULPTMODE_HLT', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_doodad_paint_layers(UIList):

    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        if item.layer_type == 'PAINT':
            layout.label(text=item.paint_layer_name if item.paint_layer_name else '<no layer selected>', icon='VPAINT_HLT')
        elif item.layer_type == 'DECO':
            layout.label(text=item.deco_layer_name if item.deco_layer_name else '<no layer selected>', icon='MONKEY')
        layout.prop(item, 'operation', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_PT_terrain_doodad_paint_layer_settings(Panel):

    bl_idname = 'BDK_PT_terrain_doodad_paint_layer_settings'
    bl_label = 'Settings'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'BDK_PT_terrain_doodad_paint_layers'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.terrain_doodad

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        paint_layer = terrain_doodad.paint_layers[terrain_doodad.paint_layers_index]
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


class BDK_PT_terrain_doodad_paint_layers(Panel):
    bl_label = 'Paint Layers'
    bl_idname = 'BDK_PT_terrain_doodad_paint_layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 1

    @classmethod
    def poll(cls, context: Context):
        # TODO: make sure there is at least one paint layer
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: Context):
        layout = self.layout
        terrain_doodad = cast(BDK_PG_terrain_doodad, context.active_object.bdk.terrain_doodad)

        # Paint Components
        row = layout.row()

        row.template_list(
            'BDK_UL_terrain_doodad_paint_layers', '',
            terrain_doodad, 'paint_layers',
            terrain_doodad, 'paint_layers_index',
            sort_lock=True, rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_doodad_paint_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_doodad_paint_layer_remove.bl_idname, icon='REMOVE', text='')
        col.separator()
        col.operator(BDK_OT_terrain_doodad_paint_layer_duplicate.bl_idname, icon='DUPLICATE', text='')


class BDK_PT_terrain_doodad_operators(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_operators'
    bl_label = 'Operators'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: 'Context'):
        self.layout.operator(BDK_OT_terrain_doodad_bake.bl_idname, icon='RENDER_RESULT')
        self.layout.operator(BDK_OT_terrain_doodad_duplicate.bl_idname, icon='DUPLICATE')
        self.layout.operator(BDK_OT_terrain_doodad_delete.bl_idname, icon='X')


class BDK_PT_terrain_doodad_debug(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 100
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        terrain_doodad: 'BDK_PG_terrain_doodad' = context.active_object.bdk.terrain_doodad
        self.layout.prop(terrain_doodad, 'id')
        self.layout.prop(terrain_doodad, 'object_type')
        self.layout.prop(terrain_doodad, 'object')
        self.layout.prop(terrain_doodad, 'node_tree')
        self.layout.prop(terrain_doodad, 'terrain_info_object')


class BDK_PT_terrain_doodad_advanced(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_advanced'
    bl_label = 'Advanced'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context: 'Context'):
        terrain_doodad: 'BDK_PG_terrain_doodad' = context.active_object.bdk.terrain_doodad
        flow = self.layout.grid_flow(align=True)
        flow.prop(terrain_doodad, 'sort_order')


class BDK_PT_terrain_doodad_sculpt_layer_settings(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_sculpt_layer_settings'
    bl_label = 'Settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_sculpt_layers'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        sculpt_layer = terrain_doodad.sculpt_layers[terrain_doodad.sculpt_layers_index]
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


class BDK_PT_terrain_doodad_sculpt_layers(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_sculpt_layers'
    bl_label = 'Sculpt Layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 0

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: Context):
        layout = self.layout
        terrain_doodad = cast(BDK_PG_terrain_doodad, context.active_object.bdk.terrain_doodad)

        row = layout.row()

        row.template_list('BDK_UL_terrain_doodad_sculpt_layers',
                          '',
                          terrain_doodad,
                          'sculpt_layers',
                          terrain_doodad,
                          'sculpt_layers_index',
                          sort_lock=True,
                          rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_doodad_sculpt_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_doodad_sculpt_layer_remove.bl_idname, icon='REMOVE', text='')

        col.separator()

        # operator = col.operator(BDK_OT_terrain_doodad_sculpt_layer_move.bl_idname, icon='TRIA_UP', text='')
        # operator.direction = 'UP'
        # operator = col.operator(BDK_OT_terrain_doodad_sculpt_layer_move.bl_idname, icon='TRIA_DOWN', text='')
        # operator.direction = 'DOWN'

        # col.separator()

        col.operator(BDK_OT_terrain_doodad_sculpt_layer_duplicate.bl_idname, icon='DUPLICATE', text='')


class BDK_PT_terrain_doodad(Panel):
    bl_label = 'Terrain Doodad'
    bl_idname = 'BDK_PT_terrain_doodad'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: 'Context'):
        pass


class BDK_PT_terrain_doodad_scatter_layers(Panel):
    bl_label = 'Scatter Layers'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = 'BDK_PT_terrain_doodad'

    @classmethod
    def poll(cls, context: 'Context'):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = cast(BDK_PG_terrain_doodad, context.active_object.bdk.terrain_doodad)

        row = layout.row()

        row.template_list('BDK_UL_terrain_doodad_scatter_layers', '',
                          terrain_doodad,
                          'scatter_layers',
                          terrain_doodad,
                          'scatter_layers_index',
                          sort_lock=True,
                          rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_doodad_scatter_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_doodad_scatter_layer_remove.bl_idname, icon='REMOVE', text='')


class BDK_PT_terrain_doodad_scatter_layer_settings(Panel):
    bl_label = 'Settings'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'

    @classmethod
    def poll(cls, context: 'Context'):
        terrain_doodad = get_terrain_doodad(context.active_object)
        return terrain_doodad and len(terrain_doodad.scatter_layers) and terrain_doodad.scatter_layers_index >= 0

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        row = layout.row()

        row.template_list('BDK_UL_terrain_doodad_scatter_layer_objects', '',
                          scatter_layer,
                          'objects',
                          scatter_layer,
                          'objects_index',
                          sort_lock=True,
                          rows=3)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_doodad_scatter_layer_objects_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_doodad_scatter_layer_objects_remove.bl_idname, icon='REMOVE', text='')

        scatter_layer_object = scatter_layer.objects[scatter_layer.objects_index] if len(scatter_layer.objects) else None

        if scatter_layer_object:
            row = layout.row()
            row.prop(scatter_layer_object, 'object', text='Object')

            flow = layout.grid_flow(align=True)
            flow.use_property_split = True
            flow.use_property_decorate = False

            flow.prop(scatter_layer_object, 'scale_min')
            flow.prop(scatter_layer_object, 'scale_max', text='Max')
            flow.prop(scatter_layer_object, 'scale_seed', text='Seed')

            flow.separator()

            flow.prop(scatter_layer_object, 'random_rotation_max')

            if terrain_doodad.object_type == 'CURVE':
                flow.separator()

                # flow.prop(scatter_layer_object, 'is_aligned_to_curve')
                # flow.prop(scatter_layer_object, 'align_axis')
                # flow.prop(scatter_layer_object, 'curve_spacing_method')

                flow.prop(scatter_layer_object, 'curve_trim_mode')

                if scatter_layer_object.curve_trim_mode == 'FACTOR':
                    col = flow.column(align=True)
                    col.prop(scatter_layer_object, 'curve_trim_factor_start', text='Trim Start')
                    col.prop(scatter_layer_object, 'curve_trim_factor_end', text='End')
                elif scatter_layer_object.curve_trim_mode == 'LENGTH':
                    col = flow.column(align=True)
                    col.prop(scatter_layer_object, 'curve_trim_length_start', text='Trim Start')
                    col.prop(scatter_layer_object, 'curve_trim_length_end', text='End')

                flow.separator()

                if scatter_layer_object.curve_spacing_method == 'RELATIVE':
                    col = flow.column(align=True)
                    col.prop(scatter_layer_object, 'curve_spacing_relative_min', text='Spacing Min')
                    col.prop(scatter_layer_object, 'curve_spacing_relative_max', text='Max')
                elif scatter_layer_object.curve_spacing_method == 'ABSOLUTE':
                    col = flow.column(align=True)
                    col.prop(scatter_layer_object, 'curve_spacing_absolute_min', text='Spacing Min')
                    col.prop(scatter_layer_object, 'curve_spacing_absolute_min', text='Max')

                flow.separator()

                col = flow.column(align=True)
                col.prop(scatter_layer_object, 'curve_normal_offset_min')
                col.prop(scatter_layer_object, 'curve_normal_offset_max', text='Max')
                col.prop(scatter_layer_object, 'curve_normal_offset_seed', text='Seed')

                flow.separator()

                col = flow.column(align=True)
                col.prop(scatter_layer_object, 'curve_tangent_offset_min')
                col.prop(scatter_layer_object, 'curve_tangent_offset_max', text='Max')
                col.prop(scatter_layer_object, 'curve_tangent_offset_seed', text='Seed')


class BDK_PT_terrain_doodad_paint_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_paint_layer_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_paint_layers'
    bl_order = 100

    @classmethod
    def poll(cls, context: 'Context'):
        # TODO: also check if we have a paint layer selected
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        paint_layer = terrain_doodad.paint_layers[terrain_doodad.paint_layers_index]
        flow = layout.grid_flow(align=True)
        flow.use_property_split = True
        flow.row().prop(paint_layer, 'id')


class BDK_PT_terrain_doodad_sculpt_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_sculpt_layer_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_sculpt_layers'
    bl_order = 100

    @classmethod
    def poll(cls, context: 'Context'):
        # TODO: also check if we have a paint layer selected
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        sculpt_layer = terrain_doodad.sculpt_layers[terrain_doodad.sculpt_layers_index]
        flow = layout.grid_flow(align=True)
        flow.use_property_split = True
        flow.row().prop(sculpt_layer, 'id')


classes = (
    BDK_PT_terrain_doodad,
    BDK_UL_terrain_doodad_sculpt_layers,
    BDK_PT_terrain_doodad_sculpt_layers,
    BDK_PT_terrain_doodad_sculpt_layer_settings,
    BDK_PT_terrain_doodad_sculpt_layer_debug,
    BDK_UL_terrain_doodad_paint_layers,
    BDK_PT_terrain_doodad_paint_layers,
    BDK_PT_terrain_doodad_paint_layer_settings,
    BDK_PT_terrain_doodad_paint_layer_debug,
    BDK_UL_terrain_doodad_scatter_layers,
    BDK_PT_terrain_doodad_scatter_layers,
    BDK_UL_terrain_doodad_scatter_layer_objects,
    BDK_PT_terrain_doodad_scatter_layer_settings,
    BDK_PT_terrain_doodad_advanced,
    BDK_PT_terrain_doodad_operators,
    BDK_PT_terrain_doodad_debug,
)
