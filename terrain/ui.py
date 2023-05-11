from bpy.types import Panel, Context, UIList, UILayout, Mesh, AnyType, Menu
from typing import cast
from .properties import BDK_PG_TerrainDecoLayerPropertyGroup
from .operators import BDK_OT_TerrainLayerAdd, BDK_OT_TerrainLayerRemove, BDK_OT_TerrainLayerMove, \
    BDK_OT_TerrainDecoLayerAdd, BDK_OT_TerrainDecoLayerRemove, BDK_OT_terrain_deco_layers_hide, \
    BDK_OT_terrain_deco_layers_show
from ..helpers import is_active_object_terrain_info, get_terrain_info


class BDK_PT_TerrainLayersPanel(Panel):
    bl_idname = 'BDK_PT_TerrainLayersPanel'
    bl_label = 'Layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Terrain'

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def draw(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        terrain_layers = terrain_info.terrain_layers
        terrain_layers_index = terrain_info.terrain_layers_index

        row = self.layout.row()
        row.template_list('BDK_UL_TerrainLayersUIList', '', terrain_info, 'terrain_layers', terrain_info,
                          'terrain_layers_index', sort_lock=True)

        col = row.column(align=True)
        col.operator(BDK_OT_TerrainLayerAdd.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_TerrainLayerRemove.bl_idname, icon='REMOVE', text='')
        col.separator()
        operator = col.operator(BDK_OT_TerrainLayerMove.bl_idname, icon='TRIA_UP', text='')
        operator.direction = 'UP'
        operator = col.operator(BDK_OT_TerrainLayerMove.bl_idname, icon='TRIA_DOWN', text='')
        operator.direction = 'DOWN'

        col.separator()

        has_terrain_layer_selected = 0 <= terrain_layers_index < len(terrain_layers)

        if has_terrain_layer_selected:
            col.separator()

            row = self.layout.row(align=True)

            terrain_layer = terrain_layers[terrain_layers_index]

            row.prop(terrain_layer, 'material')

            row = self.layout.row(align=True)

            row.label(text='Scale')
            col = row.column(align=True)
            col.prop(terrain_layer, 'u_scale', text='U')
            col.prop(terrain_layer, 'v_scale', text='V')

            row = self.layout.row(align=True)
            row.label(text='Rotation')
            row.prop(terrain_layer, 'texture_rotation', text='')


class BDK_MT_terrain_deco_layers_context_menu(Menu):
    bl_idname = 'BDK_MT_terrain_deco_layers_context_menu'
    bl_label = "Deco Layers Specials"

    def draw(self, context: Context):
        layout: UILayout = self.layout

        operator = layout.operator(BDK_OT_terrain_deco_layers_show.bl_idname, text='Show All', icon='HIDE_OFF')
        operator.mode = 'ALL'

        layout.separator()

        operator = layout.operator(BDK_OT_terrain_deco_layers_hide.bl_idname, text='Hide All', icon='HIDE_ON')
        operator.mode = 'ALL'
        operator = layout.operator(BDK_OT_terrain_deco_layers_hide.bl_idname, text='Hide Unselected')
        operator.mode = 'UNSELECTED'


class BDK_PT_TerrainDecoLayersPanel(Panel):
    bl_idname = 'BDK_PT_TerrainDecoLayersPanel'
    bl_label = 'Deco Layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Terrain'

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def draw(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)

        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index

        row = self.layout.row()
        row.template_list('BDK_UL_TerrainDecoLayersUIList', '', terrain_info, 'deco_layers', terrain_info,
                          'deco_layers_index', sort_lock=True)

        col = row.column(align=True)
        col.operator(BDK_OT_TerrainDecoLayerAdd.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_TerrainDecoLayerRemove.bl_idname, icon='REMOVE', text='')

        col.separator()

        col.menu(BDK_MT_terrain_deco_layers_context_menu.bl_idname, icon='DOWNARROW_HLT', text='')

        has_deco_layer_selected = 0 <= deco_layers_index < len(deco_layers)

        if has_deco_layer_selected:
            deco_layer: 'BDK_PG_TerrainDecoLayerPropertyGroup' = deco_layers[deco_layers_index]

            box = self.layout.box()

            icon_id = 0
            if deco_layer.static_mesh and deco_layer.static_mesh.preview:
                icon_id = deco_layer.static_mesh.preview.icon_id
            box.template_icon(icon_value=icon_id, scale=4)

            self.layout.separator()

            flow = self.layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
            flow.use_property_split = True

            flow.column().prop(deco_layer, 'static_mesh', text='Static Mesh')

            flow.separator()

            flow.column().prop(deco_layer, 'is_linked_to_layer')
            if deco_layer.is_linked_to_layer:
                flow.column().prop(deco_layer, 'linked_layer_name', text='Linked Layer')

            flow.separator()

            flow.column().prop(deco_layer, 'max_per_quad')
            flow.column().prop(deco_layer, 'seed')
            flow.column().prop(deco_layer, 'offset')
            flow.separator()

            col = flow.column(align=True)
            col.prop(deco_layer, 'density_multiplier_min', text='Density Min')
            col.prop(deco_layer, 'density_multiplier_max', text='Max')
            flow.separator()

            col = flow.column(align=True)
            col.prop(deco_layer, 'fadeout_radius_min', text='Fadeout Radius Min')
            col.prop(deco_layer, 'fadeout_radius_max', text='Max')
            flow.separator()

            col = flow.column()
            col.prop(deco_layer, 'scale_multiplier_min', text='Scale Min')
            col.prop(deco_layer, 'scale_multiplier_max', text='Max')
            col.separator()

            flow.column().prop(deco_layer, 'align_to_terrain')
            flow.column().prop(deco_layer, 'show_on_invisible_terrain')
            flow.column().prop(deco_layer, 'random_yaw')
            # flow.column().prop(deco_layer, 'inverted')    # TODO: move this to the top level object
            flow.separator()

            flow.column().prop(deco_layer, 'force_draw')
            flow.column().prop(deco_layer, 'detail_mode')
            flow.column().prop(deco_layer, 'draw_order')


class BDK_UL_TerrainLayersUIList(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        icon = row.icon(item.material) if item.material else None
        if icon:
            row.prop(item, 'name', text='', emboss=False, icon_value=icon)
        else:
            row.prop(item, 'name', text='', emboss=False, icon='IMAGE')

        mesh = cast(Mesh, context.active_object.data)
        color_attribute_index = mesh.color_attributes.find(item.color_attribute_name)
        if color_attribute_index == mesh.color_attributes.active_color_index:
            row.label(text='', icon='VPAINT_HLT')

        row.prop(item, 'is_visible', icon=('HIDE_OFF' if item.is_visible else 'HIDE_ON'), text='', emboss=False)


class BDK_UL_TerrainDecoLayersUIList(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        row.prop(item, 'name', text='', emboss=False)

        mesh = cast(Mesh, context.active_object.data)
        color_attribute_index = mesh.color_attributes.find(item.id)
        if color_attribute_index == mesh.color_attributes.active_color_index:
            row.label(text='', icon='VPAINT_HLT')

        row.prop(item.object, 'hide_viewport', icon='HIDE_OFF' if not item.object.hide_viewport else 'HIDE_ON', text='', emboss=False)


classes = (
    BDK_PT_TerrainLayersPanel,
    BDK_PT_TerrainDecoLayersPanel,
    BDK_UL_TerrainLayersUIList,
    BDK_UL_TerrainDecoLayersUIList,
    BDK_MT_terrain_deco_layers_context_menu,
)
