from typing import cast, Optional, Any

import bpy
from bpy.types import Panel, Context, UIList, UILayout, Curve, AnyType

from .sculpt.operators import BDK_OT_terrain_doodad_sculpt_layer_add, BDK_OT_terrain_doodad_sculpt_layer_remove, \
    BDK_OT_terrain_doodad_sculpt_layer_duplicate, BDK_OT_terrain_doodad_sculpt_layer_move
from ..ui import draw_terrain_layer_node_item
from ...helpers import should_show_bdk_developer_extras, get_terrain_doodad, is_active_object_terrain_doodad
from .paint.operators import BDK_OT_terrain_doodad_paint_layer_add, BDK_OT_terrain_doodad_paint_layer_remove, \
    BDK_OT_terrain_doodad_paint_layer_duplicate, BDK_OT_terrain_doodad_paint_layer_move
from .operators import BDK_OT_terrain_doodad_bake, BDK_OT_terrain_doodad_duplicate, BDK_OT_terrain_doodad_delete, \
    BDK_OT_terrain_doodad_demote, BDK_OT_terrain_doodad_unfreeze, BDK_OT_terrain_doodad_freeze
from .scatter.operators import BDK_OT_terrain_doodad_scatter_layer_add, BDK_OT_terrain_doodad_scatter_layer_remove, \
    BDK_OT_terrain_doodad_scatter_layer_objects_add, BDK_OT_terrain_doodad_scatter_layer_objects_remove, \
    BDK_OT_terrain_doodad_scatter_layer_duplicate, BDK_OT_terrain_doodad_scatter_layer_objects_duplicate
from .properties import BDK_PG_terrain_doodad


class BDK_UL_terrain_doodad_scatter_layer_objects(UIList):
    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.object.name if item.object is not None else '<no object selected>', icon='OBJECT_DATA')
        layout.prop(item, 'is_cap', text='', icon='GP_SELECT_POINTS' if item.is_cap else 'SNAP_MIDPOINT', emboss=False)
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_doodad_scatter_layers(UIList):
    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', icon='PARTICLE_POINT', emboss=False, text='')
        layout.prop(item, 'mute', text='', icon='HIDE_ON' if item.mute else 'HIDE_OFF', emboss=False)


class BDK_UL_terrain_doodad_sculpt_layers(UIList):
    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', icon='SCULPTMODE_HLT', emboss=False, text='')
        row = layout.row(align=True)
        row.prop(item, 'operation', text='', emboss=False)
        row.prop(item, 'mute', text='', emboss=False, icon='HIDE_OFF' if not item.mute else 'HIDE_ON')


class BDK_UL_terrain_doodad_paint_layers(UIList):

    def draw_item(self, context: Context, layout, data, item, icon, active_data, active_propname, index):
        if item.layer_type == 'PAINT':
            layout.label(text=item.paint_layer_name if item.paint_layer_name else '<no layer selected>', icon='BRUSH_TEXFILL')
        elif item.layer_type == 'DECO':
            layout.label(text=item.deco_layer_name if item.deco_layer_name else '<no layer selected>', icon='MONKEY')
        elif item.layer_type == 'ATTRIBUTE':
            layout.label(text=item.attribute_layer_id if item.attribute_layer_id else '<no attribute>', icon='MODIFIER_DATA')
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
        if not is_active_object_terrain_doodad(context):
            return False
        terrain_doodad = context.active_object.bdk.terrain_doodad
        return len(terrain_doodad.paint_layers) > 0 and terrain_doodad.paint_layers_index >= 0

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        paint_layer = terrain_doodad.paint_layers[terrain_doodad.paint_layers_index]

        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.separator()

        flow.prop(paint_layer, 'geometry_source')

        match paint_layer.geometry_source:
            case 'SCATTER_LAYER':
                flow.prop(paint_layer, 'scatter_layer_name')
            case 'DOODAD':
                if terrain_doodad.object.type == 'MESH':
                    flow.prop(paint_layer, 'element_mode')

        row = flow.row()

        row.prop(paint_layer, 'layer_type')

        if paint_layer.layer_type == 'PAINT':
            flow.prop(paint_layer, 'paint_layer_name')
        elif paint_layer.layer_type == 'DECO':
            row = flow.row()
            row.prop(paint_layer, 'deco_layer_name')
            deco_layer_object = bpy.data.objects[paint_layer.deco_layer_id] if paint_layer.deco_layer_id in bpy.data.objects else None
            if deco_layer_object:
                row.prop(deco_layer_object, 'hide_viewport', icon_only=True)
        elif paint_layer.layer_type == 'ATTRIBUTE':
            flow.prop(paint_layer, 'attribute_layer_id')

        flow.separator()

        flow.prop(paint_layer, 'interpolation_type')

        col = flow.column()

        col.prop(paint_layer, 'radius')
        col.prop(paint_layer, 'falloff_radius')
        col.prop(paint_layer, 'strength')

        if terrain_doodad.object.type == 'CURVE':
            draw_curve_modifier_settings(flow, paint_layer)
            flow.separator()

        flow.prop(paint_layer, 'use_distance_noise')

        if paint_layer.use_distance_noise:
            col = flow.column(align=True)
            col.prop(paint_layer, 'noise_type', icon='MOD_NOISE')
            col.prop(paint_layer, 'distance_noise_offset', text='Offset')
            col.prop(paint_layer, 'distance_noise_factor', text='Factor')
            if paint_layer.noise_type == 'PERLIN':
                col.prop(paint_layer, 'distance_noise_distortion', text='Distortion')


class BDK_PT_terrain_doodad_paint_layers(Panel):
    bl_label = 'Paint Layers'
    bl_idname = 'BDK_PT_terrain_doodad_paint_layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        # TODO: make sure there is at least one paint layer
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def draw(self, context: Context):
        layout = self.layout
        terrain_doodad = cast(BDK_PG_terrain_doodad, context.active_object.bdk.terrain_doodad)

        # Paint Layers
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
        operator = col.operator(BDK_OT_terrain_doodad_paint_layer_move.bl_idname, icon='TRIA_UP', text='')
        operator.direction = 'UP'
        operator = col.operator(BDK_OT_terrain_doodad_paint_layer_move.bl_idname, icon='TRIA_DOWN', text='')
        operator.direction = 'DOWN'
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
        self.layout.operator(BDK_OT_terrain_doodad_bake.bl_idname, icon='RENDER_RESULT', text='Bake')
        self.layout.operator(BDK_OT_terrain_doodad_duplicate.bl_idname, icon='DUPLICATE', text='Duplicate')
        self.layout.operator(BDK_OT_terrain_doodad_delete.bl_idname, icon='X', text='Delete')
        self.layout.operator(BDK_OT_terrain_doodad_demote.bl_idname, icon='TRIA_DOWN', text='Demote')
        # self.layout.operator(BDK_OT_terrain_doodad_save_preset.bl_idname, icon='FILE_TICK', text='Save Preset')
        # self.layout.operator(BDK_OT_terrain_doodad_load_preset.bl_idname, icon='FILE_FOLDER', text='Load Preset')


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
        layout = self.layout
        terrain_doodad: 'BDK_PG_terrain_doodad' = context.active_object.bdk.terrain_doodad
        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(terrain_doodad, 'id', emboss=False)
        flow.prop(terrain_doodad, 'object', emboss=False)
        flow.prop(terrain_doodad, 'node_tree', emboss=False)
        flow.prop(terrain_doodad, 'terrain_info_object', emboss=False)


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
        flow = self.layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(terrain_doodad, 'sort_order')


def has_terrain_doodad_sculpt_layer_selected(context: Context):
    terrain_doodad = get_terrain_doodad(context.active_object)
    return terrain_doodad is not None and len(terrain_doodad.sculpt_layers) > 0 and terrain_doodad.sculpt_layers_index >= 0


def get_terrain_doodad_selected_sculpt_layer(context: Context):
    terrain_doodad = get_terrain_doodad(context.active_object)
    return terrain_doodad.sculpt_layers[terrain_doodad.sculpt_layers_index]


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
        return has_terrain_doodad_sculpt_layer_selected(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        sculpt_layer = get_terrain_doodad_selected_sculpt_layer(context)

        flow = layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(sculpt_layer, 'geometry_source')

        match sculpt_layer.geometry_source:
            case 'SCATTER_LAYER':
                flow.prop(sculpt_layer, 'scatter_layer_name')
            case 'DOODAD':
                if sculpt_layer.terrain_doodad_object.type == 'MESH':
                    flow.prop(sculpt_layer, 'element_mode')

        flow.separator()

        flow.prop(sculpt_layer, 'depth')

        col = flow.column(align=True)
        col.prop(sculpt_layer, 'radius')
        col.prop(sculpt_layer, 'falloff_radius')
        col.prop(sculpt_layer, 'interpolation_type')


class BDK_PT_terrain_doodad_sculpt_layer_curve_settings(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_sculpt_layer_curve_settings'
    bl_label = 'Curve Settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_sculpt_layer_settings'

    @classmethod
    def poll(cls, context: Context):
        if not has_terrain_doodad_sculpt_layer_selected(context):
            return False
        terrain_doodad = get_terrain_doodad(context.active_object)
        return terrain_doodad.object.type == 'CURVE'

    def draw(self, context: Context):
        sculpt_layer = get_terrain_doodad_selected_sculpt_layer(context)
        flow = self.layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        draw_curve_modifier_settings(flow, sculpt_layer)


class BDK_PT_terrain_doodad_sculpt_layer_noise(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_sculpt_layer_noise'
    bl_label = 'Noise'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_sculpt_layers'

    @classmethod
    def poll(cls, context: 'Context'):
        return has_terrain_doodad_sculpt_layer_selected(context)

    def draw_header(self, context: Context):
        sculpt_layer = get_terrain_doodad_selected_sculpt_layer(context)
        self.layout.prop(sculpt_layer, 'use_noise', text='')

    def draw(self, context: 'Context'):
        flow = self.layout.grid_flow(columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        sculpt_layer = get_terrain_doodad_selected_sculpt_layer(context)

        col = flow.column(align=True)
        col.prop(sculpt_layer, 'noise_radius_factor', text='Radius Factor')
        col.prop(sculpt_layer, 'noise_strength', text='Strength')

        flow.prop(sculpt_layer, 'noise_type', text='Type')

        if sculpt_layer.noise_type == 'PERLIN':
            col = flow.column(align=True)
            col.prop(sculpt_layer, 'perlin_noise_distortion', text='Distortion')
            col.prop(sculpt_layer, 'perlin_noise_roughness', text='Roughness')
            col.prop(sculpt_layer, 'perlin_noise_scale', text='Scale')
            col.prop(sculpt_layer, 'perlin_noise_lacunarity', text='Lacunarity')
            col.prop(sculpt_layer, 'perlin_noise_detail', text='Detail')


class BDK_PT_terrain_doodad_sculpt_layers(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_sculpt_layers'
    bl_label = 'Sculpt Layers'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad'
    bl_options = {'DEFAULT_CLOSED'}

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

        col.operator(BDK_OT_terrain_doodad_sculpt_layer_move.bl_idname, icon='TRIA_UP', text='').direction = 'UP'
        col.operator(BDK_OT_terrain_doodad_sculpt_layer_move.bl_idname, icon='TRIA_DOWN', text='').direction = 'DOWN'

        col.separator()

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
        layout = self.layout
        terrain_doodad = cast(BDK_PG_terrain_doodad, context.active_object.bdk.terrain_doodad)
        if terrain_doodad.is_frozen:
            layout.operator(BDK_OT_terrain_doodad_unfreeze.bl_idname, text='Unfreeze', icon='FREEZE')
        else:
            layout.operator(BDK_OT_terrain_doodad_freeze.bl_idname, text='Freeze', icon='LIGHT_SUN')


class BDK_PT_terrain_doodad_scatter_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_debug'
    bl_label = 'Debug'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_order = 100

    @classmethod
    def poll(cls, context: 'Context'):
        terrain_doodad = get_terrain_doodad(context.active_object)
        return len(terrain_doodad.scatter_layers) > 0

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]
        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(scatter_layer, 'id', emboss=False)

        depsgraph = context.evaluated_depsgraph_get()

        if scatter_layer.planter_object:
            flow.prop(scatter_layer, 'planter_object', emboss=False, text='Planter')
            planter_object_evaluated = scatter_layer.planter_object.evaluated_get(depsgraph)
            for modifier in planter_object_evaluated.modifiers:
                flow.prop(modifier, 'execution_time', emboss=False)

        if scatter_layer.seed_object:
            flow.prop(scatter_layer, 'seed_object', emboss=False, text='Seed')
            seed_object_evaluated = scatter_layer.seed_object.evaluated_get(depsgraph)
            for modifier in seed_object_evaluated.modifiers:
                flow.prop(modifier, 'execution_time', emboss=False)

        if scatter_layer.sprout_object:
            flow.prop(scatter_layer, 'sprout_object', emboss=False, text='Sprout')
            sprout_object_evaluated = scatter_layer.sprout_object.evaluated_get(depsgraph)
            for modifier in sprout_object_evaluated.modifiers:
                flow.prop(modifier, 'execution_time', emboss=False)


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
        col.separator()
        col.operator(BDK_OT_terrain_doodad_scatter_layer_duplicate.bl_idname, icon='DUPLICATE', text='')


class BDK_PT_terrain_doodad_scatter_layer_mesh_settings(Panel):
    bl_label = 'Mesh Settings'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_mesh_settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_order = 10

    @classmethod
    def poll(cls, context: 'Context'):
        terrain_doodad = get_terrain_doodad(context.active_object)
        if terrain_doodad.object.type != 'MESH':
            return False
        # Get selected scatter layer.
        if len(terrain_doodad.scatter_layers) == 0:
            return False
        if terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index].geometry_source == 'SCATTER_LAYER':
            return False
        return True

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer, 'mesh_element_mode')

        flow.separator()

        if scatter_layer.mesh_element_mode == 'VERTEX':
            pass
        if scatter_layer.mesh_element_mode == 'FACE':
            flow.prop(scatter_layer, 'mesh_face_distribute_method')

            if scatter_layer.mesh_face_distribute_method == 'RANDOM':
                flow.prop(scatter_layer, 'mesh_face_distribute_random_density')
            elif scatter_layer.mesh_face_distribute_method == 'POISSON_DISK':
                flow.prop(scatter_layer, 'mesh_face_distribute_poisson_distance_min')
                flow.prop(scatter_layer, 'mesh_face_distribute_poisson_density_factor')


def poll_has_terrain_doodad_scatter_layer_selected(cls, context: Context):
    terrain_doodad = get_terrain_doodad(context.active_object)
    return len(terrain_doodad.scatter_layers) > 0 and terrain_doodad.scatter_layers_index >= 0


class BDK_PT_terrain_doodad_scatter_layer_curve_settings(Panel):
    bl_label = 'Curve Settings'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_curve_settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_order = 10

    @classmethod
    def poll(cls, context: 'Context'):
        terrain_doodad = get_terrain_doodad(context.active_object)
        if terrain_doodad.object.type != 'CURVE':
            return False
        if len(terrain_doodad.scatter_layers) == 0:
            return False
        if terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index].geometry_source == 'SCATTER_LAYER':
            return False
        return True

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer, 'fence_mode')
        flow.separator()

        # Curve settings
        draw_curve_modifier_settings(flow, scatter_layer, curve_data=terrain_doodad.object.data)

        flow.separator()
        flow.prop(scatter_layer, 'curve_spacing_method')

        match scatter_layer.curve_spacing_method:
            case'RELATIVE':
                flow.prop(scatter_layer, 'curve_spacing_relative_axis', text='Axis')
                flow.prop(scatter_layer, 'curve_spacing_relative_factor', text='Factor')
            case 'ABSOLUTE':
                flow.prop(scatter_layer, 'curve_spacing_absolute', text='Distance')

        flow.separator()

        flow.prop(scatter_layer, 'curve_normal_offset_max', text='Normal Offset Max')
        flow.prop(scatter_layer, 'curve_normal_offset_seed', text='Seed')

        flow.separator()

        flow.prop(scatter_layer, 'curve_tangent_offset_max', text='Tangent Offset Max')
        flow.prop(scatter_layer, 'curve_tangent_offset_seed', text='Seed')


def get_selected_terrain_doodad_scatter_layer_object(context: Context):
    terrain_doodad = get_terrain_doodad(context.active_object)
    if terrain_doodad is None:
        return None
    if len(terrain_doodad.scatter_layers) == 0 or terrain_doodad.scatter_layers_index < 0:
        return None
    scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]
    if len(scatter_layer.objects) == 0:
        return None
    return scatter_layer.objects[scatter_layer.objects_index]


def poll_has_selected_scatter_layer_object(cls, context: Context) -> bool:
    return get_selected_terrain_doodad_scatter_layer_object(context) is not None


class BDK_PT_terrain_doodad_scatter_layer_object_position(Panel):
    bl_label = 'Position'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_object_position'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layer_objects'
    bl_order = 0

    @classmethod
    def poll(cls, context: Context):
        return poll_has_selected_scatter_layer_object(cls, context)

    def draw(self, context: Context):
        scatter_layer_object = get_selected_terrain_doodad_scatter_layer_object(context)

        flow = self.layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer_object, 'origin_offset')


class BDK_PT_terrain_doodad_scatter_layer_object_snap_to_terrain(Panel):
    bl_label = 'Snap to Terrain'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_object_snap_to_terrain'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layer_objects'
    bl_order = 10

    @classmethod
    def poll(cls, context: Context):
        return poll_has_selected_scatter_layer_object(cls, context)

    def draw_header(self, context: Context):
        scatter_layer_object = get_selected_terrain_doodad_scatter_layer_object(context)
        self.layout.prop(scatter_layer_object, 'snap_to_terrain', text='')

    def draw(self, context: Context):
        scatter_layer_object = get_selected_terrain_doodad_scatter_layer_object(context)

        flow = self.layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer_object, 'align_to_terrain_factor')
        flow.separator()
        flow.prop(scatter_layer_object, 'terrain_normal_offset_min', text='Terrain Offset Min')
        flow.prop(scatter_layer_object, 'terrain_normal_offset_max', text='Max')
        flow.prop(scatter_layer_object, 'terrain_normal_offset_seed', text='Seed')


class BDK_PT_terrain_doodad_scatter_layer_object_rotation(Panel):
    bl_label = 'Rotation'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_object_rotation'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layer_objects'
    bl_order = 30

    @classmethod
    def poll(cls, context: Context):
        return poll_has_selected_scatter_layer_object(cls, context)

    def draw(self, context: Context):
        scatter_layer_object = get_selected_terrain_doodad_scatter_layer_object(context)

        flow = self.layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer_object, 'rotation_offset')
        flow.prop(scatter_layer_object, 'rotation_offset_saturation', text='Saturation')
        flow.prop(scatter_layer_object, 'rotation_offset_saturation_seed', text='Seed')

        flow.separator()

        flow.prop(scatter_layer_object, 'random_rotation_max')
        flow.prop(scatter_layer_object, 'random_rotation_max_seed', text='Seed')


class BDK_PT_terrain_doodad_scatter_layer_object_scale(Panel):
    bl_label = 'Scale'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_object_scale'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layer_objects'
    bl_order = 20

    @classmethod
    def poll(cls, context: Context):
        return poll_has_selected_scatter_layer_object(cls, context)

    def draw(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]
        scatter_layer_object = scatter_layer.objects[scatter_layer.objects_index]

        flow = self.layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer_object, 'scale_mode')

        flow.separator()

        if scatter_layer_object.scale_mode == 'UNIFORM':
            flow.prop(scatter_layer_object, 'scale_uniform', text='Scale')
        elif scatter_layer_object.scale_mode == 'NON_UNIFORM':
            flow.prop(scatter_layer_object, 'scale', text='Scale')

        flow.separator()

        if scatter_layer_object.scale_mode == 'UNIFORM':
            flow.prop(scatter_layer_object, 'scale_random_uniform_min', text='Random Scale Min')
            flow.prop(scatter_layer_object, 'scale_random_uniform_max', text='Max')
        elif scatter_layer_object.scale_mode == 'NON_UNIFORM':
            flow.prop(scatter_layer_object, 'scale_random_min', text='Random Scale Min')
            flow.prop(scatter_layer_object, 'scale_random_max', text='Max')

        flow.prop(scatter_layer_object, 'scale_seed', text='Seed')


class BDK_PT_terrain_doodad_scatter_layer_objects(Panel):
    bl_label = 'Objects'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_objects'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_order = 20

    @classmethod
    def poll(cls, context: 'Context'):
        return poll_has_terrain_doodad_scatter_layer_selected(cls, context)

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer, 'object_select_mode', text='Select Mode')

        if scatter_layer.object_select_mode in {'RANDOM', 'WEIGHTED_RANDOM'}:
            flow.prop(scatter_layer, 'object_select_random_seed', text='Seed')
        elif scatter_layer.object_select_mode == 'CYCLIC':
            flow.prop(scatter_layer, 'object_select_cyclic_offset', text='Offset')

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

        col.separator()

        col.operator(BDK_OT_terrain_doodad_scatter_layer_objects_duplicate.bl_idname, icon='DUPLICATE', text='')

        scatter_layer_object = scatter_layer.objects[scatter_layer.objects_index] if len(scatter_layer.objects) else \
            None

        if scatter_layer_object:
            flow = layout.grid_flow(align=True, columns=1)
            flow.use_property_split = True
            flow.use_property_decorate = False

            flow.prop(scatter_layer_object, 'object', text='Object')
            flow.separator()

            # If the object mode is weighted random, show the weight slider.
            if scatter_layer.object_select_mode == 'WEIGHTED_RANDOM':
                flow.prop(scatter_layer_object, 'random_weight')
                flow.separator()


class BDK_PT_terrain_doodad_scatter_layer_mask(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_mask'
    bl_label = 'Mask'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 30
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'

    @classmethod
    def poll(cls, context: 'Context'):
        return poll_has_terrain_doodad_scatter_layer_selected(cls, context)

    def draw_header(self, context):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        layout.prop(scatter_layer, 'use_mask', text='')

    def draw(self, context):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer, 'mask_type', text='Type')

        if not scatter_layer.use_mask:
            layout.active = False

        match scatter_layer.mask_type:
            case 'ATTRIBUTE':
                flow.prop(scatter_layer, 'mask_attribute_name', text='Attribute')
            case 'PAINT_LAYER':
                flow.prop(scatter_layer, 'mask_paint_layer_name', text='Paint Layer')

        flow.prop(scatter_layer, 'mask_threshold', text='Threshold')
        flow.prop(scatter_layer, 'mask_invert', text='Invert')

        flow.separator()

        flow.prop(scatter_layer, 'mask_attribute_id', emboss=False)


# TODO: rename this "actor properties" or something
class BDK_PT_terrain_doodad_scatter_layer_advanced(Panel):
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_advanced'
    bl_label = 'Advanced'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 31
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'

    @classmethod
    def poll(cls, context: 'Context'):
        return poll_has_terrain_doodad_scatter_layer_selected(cls, context)

    def draw(self, context):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(scatter_layer, 'actor_group', text='Group')


def draw_curve_modifier_settings(layout: UILayout, data, curve_data: Curve = None):
    layout.prop(data, 'is_curve_reversed')
    layout.prop(data, 'curve_normal_offset')

    layout.separator()

    layout.prop(data, 'curve_trim_mode')

    if data.curve_trim_mode == 'FACTOR':
        col = layout.column(align=True)
        col.prop(data, 'curve_trim_factor_start', text='Trim Start')
        col.prop(data, 'curve_trim_factor_end', text='End')
        if data.curve_trim_factor_start >= data.curve_trim_factor_end:
            layout.label(text='Trim start should be less than trim end', icon='ERROR')
    elif data.curve_trim_mode == 'LENGTH':
        col = layout.column(align=True)
        col.prop(data, 'curve_trim_length_start', text='Trim Start')
        col.prop(data, 'curve_trim_length_end', text='End')


class BDK_PT_terrain_doodad_scatter_layer_settings(Panel):
    bl_label = 'Settings'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_settings'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layers'
    bl_order = 0

    @classmethod
    def poll(cls, context: 'Context'):
        terrain_doodad = get_terrain_doodad(context.active_object)
        return terrain_doodad and len(terrain_doodad.scatter_layers) and terrain_doodad.scatter_layers_index >= 0

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(scatter_layer, 'geometry_source')

        if scatter_layer.geometry_source == 'SCATTER_LAYER':
            flow.prop(scatter_layer, 'geometry_source_name', text='Scatter Layer')

        flow.separator()
        flow.prop(scatter_layer, 'global_seed')
        flow.separator()
        flow.prop(scatter_layer, 'density')
        flow.prop(scatter_layer, 'density_seed')
        flow.separator()
        flow.prop(scatter_layer, 'snap_to_vertex_factor', text='Snap to Vertex')
        flow.separator()
        flow.prop(scatter_layer, 'use_position_deviation')

        if scatter_layer.use_position_deviation:
            flow.prop(scatter_layer, 'position_deviation_min', text='Min')
            flow.prop(scatter_layer, 'position_deviation_max', text='Max')
            flow.separator()
            flow.prop(scatter_layer, 'position_deviation_seed')


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
        terrain_doodad = get_terrain_doodad(context.active_object)
        if not terrain_doodad or len(terrain_doodad.paint_layers) == 0 or terrain_doodad.paint_layers_index < 0:
            return False
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        terrain_doodad = context.active_object.bdk.terrain_doodad
        paint_layer = terrain_doodad.paint_layers[terrain_doodad.paint_layers_index]
        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.row().prop(paint_layer, 'id', emboss=False)
        flow.row().prop(paint_layer, 'frozen_attribute_id', emboss=False)


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
        terrain_doodad = get_terrain_doodad(context.active_object)
        if not terrain_doodad or len(terrain_doodad.sculpt_layers) == 0 or terrain_doodad.sculpt_layers_index < 0:
            return False
        return should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        sculpt_layer = get_terrain_doodad_selected_sculpt_layer(context)
        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.prop(sculpt_layer, 'id', emboss=False)
        flow.prop(sculpt_layer, 'frozen_attribute_id', emboss=False)


class BDK_UL_terrain_doodad_scatter_layer_nodes(UIList):

    def draw_item(self,
                  context: Optional['Context'],
                  layout: 'UILayout',
                  data: Optional[AnyType],
                  item: Optional[AnyType],
                  icon: Optional[int],
                  active_data: 'AnyType',
                  active_property: str,
                  index: Optional[Any] = 0,
                  flt_flag: Optional[Any] = 0):
        terrain_doodad = get_terrain_doodad(context.active_object)
        mesh = terrain_doodad.terrain_info_object.data
        draw_terrain_layer_node_item(layout, item, mesh)


class BDK_PT_terrain_doodad_scatter_layer_object_actor_properties(Panel):
    bl_label = 'Actor Properties'
    bl_idname = 'BDK_PT_terrain_doodad_scatter_layer_object_actor_properties'
    bl_category = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_doodad_scatter_layer_objects'
    bl_order = 100

    @classmethod
    def poll(cls, context: Context):
        return poll_has_selected_scatter_layer_object(cls, context)

    def draw(self, context: Context):
        layout = self.layout

        scatter_layer_object = get_selected_terrain_doodad_scatter_layer_object(context)
        actor_properties = scatter_layer_object.actor_properties

        flow = layout.grid_flow(align=True, columns=1)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(actor_properties, 'class_name')

        flow.separator()

        # TODO: put this in it's own panel for collision stuff.
        flow.prop(actor_properties, 'should_use_cull_distance')
        if actor_properties.should_use_cull_distance:
            flow.prop(actor_properties, 'cull_distance')

        flow.prop(actor_properties, 'accepts_projectors')

        flow.separator()
        flow.prop(actor_properties, 'collision_flags')


classes = (
    BDK_UL_terrain_doodad_sculpt_layers,
    BDK_UL_terrain_doodad_paint_layers,
    BDK_UL_terrain_doodad_scatter_layers,
    BDK_UL_terrain_doodad_scatter_layer_objects,
    BDK_UL_terrain_doodad_scatter_layer_nodes,
    BDK_PT_terrain_doodad,
    BDK_PT_terrain_doodad_sculpt_layers,
    BDK_PT_terrain_doodad_sculpt_layer_settings,
    BDK_PT_terrain_doodad_sculpt_layer_noise,
    BDK_PT_terrain_doodad_sculpt_layer_curve_settings,
    BDK_PT_terrain_doodad_sculpt_layer_debug,
    BDK_PT_terrain_doodad_paint_layers,
    BDK_PT_terrain_doodad_paint_layer_settings,
    BDK_PT_terrain_doodad_paint_layer_debug,
    BDK_PT_terrain_doodad_scatter_layers,
    BDK_PT_terrain_doodad_scatter_layer_objects,
    BDK_PT_terrain_doodad_scatter_layer_object_position,
    BDK_PT_terrain_doodad_scatter_layer_object_scale,
    BDK_PT_terrain_doodad_scatter_layer_object_rotation,
    BDK_PT_terrain_doodad_scatter_layer_object_snap_to_terrain,
    BDK_PT_terrain_doodad_scatter_layer_object_actor_properties,
    BDK_PT_terrain_doodad_scatter_layer_settings,
    BDK_PT_terrain_doodad_scatter_layer_curve_settings,
    BDK_PT_terrain_doodad_scatter_layer_mesh_settings,
    BDK_PT_terrain_doodad_scatter_layer_mask,
    BDK_PT_terrain_doodad_scatter_layer_advanced,
    BDK_PT_terrain_doodad_scatter_layer_debug,
    BDK_PT_terrain_doodad_advanced,
    BDK_PT_terrain_doodad_operators,
    BDK_PT_terrain_doodad_debug,
)
