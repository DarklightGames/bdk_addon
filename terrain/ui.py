from bpy.types import Panel, Context, UIList, UILayout, Mesh, AnyType, Menu
from typing import cast, Optional
from .properties import BDK_PG_terrain_deco_layer, terrain_layer_node_type_icons, BDK_PG_terrain_layer_node, \
    BDK_PG_terrain_layer
from .operators import BDK_OT_terrain_layer_add, BDK_OT_terrain_layer_remove, BDK_OT_terrain_layer_move, \
    BDK_OT_terrain_deco_layer_add, BDK_OT_terrain_deco_layer_remove, BDK_OT_terrain_deco_layers_hide, \
    BDK_OT_terrain_deco_layers_show, BDK_OT_terrain_layers_show, BDK_OT_terrain_layers_hide, \
    BDK_OT_terrain_deco_layer_nodes_add, BDK_OT_terrain_deco_layer_nodes_remove, BDK_OT_terrain_deco_layer_nodes_move, \
    BDK_OT_terrain_info_repair
from ..helpers import is_active_object_terrain_info, get_terrain_info, should_show_bdk_developer_extras


class BDK_PT_terrain_info(Panel):
    bl_idname = 'BDK_PT_terrain_info'
    bl_label = 'Terrain Info'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_INFO'

    def draw(self, context: Context):
        self.layout.operator(BDK_OT_terrain_info_repair.bl_idname, icon='FILE_REFRESH', text='Repair')


class BDK_PT_terrain_info_debug(Panel):
    bl_idname = 'BDK_PT_terrain_info_debug'
    bl_label = 'Debug'
    bl_parent_id = 'BDK_PT_terrain_info'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 100

    @classmethod
    def poll(cls, context: Context):
        return should_show_bdk_developer_extras(context)

    def draw(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        self.layout.prop(terrain_info, 'x_size')
        self.layout.prop(terrain_info, 'y_size')
        self.layout.prop(terrain_info, 'terrain_scale')


class BDK_PT_terrain_layers(Panel):
    bl_idname = 'BDK_PT_terrain_layers'
    bl_label = 'Layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Terrain'
    bl_parent_id = 'BDK_PT_terrain_info'
    bl_order = 0

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def draw(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)

        row = self.layout.row()
        row.template_list('BDK_UL_terrain_layers', '', terrain_info, 'terrain_layers', terrain_info,
                          'terrain_layers_index', sort_lock=True)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_layer_remove.bl_idname, icon='REMOVE', text='')
        col.separator()
        operator = col.operator(BDK_OT_terrain_layer_move.bl_idname, icon='TRIA_UP', text='')
        operator.direction = 'UP'
        operator = col.operator(BDK_OT_terrain_layer_move.bl_idname, icon='TRIA_DOWN', text='')
        operator.direction = 'DOWN'

        col.separator()
        col.menu(BDK_MT_terrain_layers_context_menu.bl_idname, icon='DOWNARROW_HLT', text='')


class BDK_PT_terrain_layer_settings(Panel):
    bl_idname = 'BDK_PT_terrain_layer_settings'
    bl_label = 'Settings'
    bl_parent_id = 'BDK_PT_terrain_layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return has_terrain_layer_selected(context)

    def draw(self, context: Context):
        terrain_layer = get_selected_terrain_layer(context)

        flow = self.layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        flow.use_property_split = True

        flow.column(align=True).prop(terrain_layer, 'material')

        col = flow.row().column(align=True)
        col.prop(terrain_layer, 'u_scale', text='U Scale')
        col.prop(terrain_layer, 'v_scale', text='V')
        col.prop(terrain_layer, 'texel_density', emboss=False)

        col = flow.row().column(align=True)
        col.prop(terrain_layer, 'texture_rotation', text='Rotation')


class BDK_MT_terrain_layers_context_menu(Menu):
    bl_idname = 'BDK_MT_terrain_layers_context_menu'
    bl_label = "Layers Specials"

    def draw(self, context: Context):
        layout: UILayout = self.layout

        operator = layout.operator(BDK_OT_terrain_layers_show.bl_idname, text='Show All', icon='HIDE_OFF')
        operator.mode = 'ALL'

        layout.separator()

        operator = layout.operator(BDK_OT_terrain_layers_hide.bl_idname, text='Hide All', icon='HIDE_ON')
        operator.mode = 'ALL'
        operator = layout.operator(BDK_OT_terrain_layers_hide.bl_idname, text='Hide Unselected')
        operator.mode = 'UNSELECTED'


class BDK_PT_terrain_layer_debug(Panel):
    bl_idname = 'BDK_PT_terrain_layer_debug'
    bl_label = 'Debug'
    bl_parent_id = 'BDK_PT_terrain_layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: Context):
        return should_show_bdk_developer_extras(context) and has_terrain_layer_selected(context)

    def draw(self, context: Context):
        terrain_layer = get_selected_terrain_layer(context)
        self.layout.prop(terrain_layer, 'id')



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


def has_deco_layer_selected(context: Context) -> bool:
    terrain_info = get_terrain_info(context.active_object)
    return terrain_info and 0 <= terrain_info.deco_layers_index < len(terrain_info.deco_layers)


def get_selected_deco_layer(context: Context) -> BDK_PG_terrain_deco_layer:
    terrain_info = get_terrain_info(context.active_object)
    return terrain_info.deco_layers[terrain_info.deco_layers_index]


def has_terrain_layer_selected(context: Context) -> bool:
    terrain_info = get_terrain_info(context.active_object)
    return terrain_info and 0 <= terrain_info.terrain_layers_index < len(terrain_info.terrain_layers)


# TODO: replace this with a context property (i.e. context.terrain_layer)
def get_selected_terrain_layer(context: Context) -> BDK_PG_terrain_layer:
    terrain_info = get_terrain_info(context.active_object)
    return terrain_info.terrain_layers[terrain_info.terrain_layers_index]


def has_selected_deco_layer_node(context: Context) -> bool:
    deco_layer = get_selected_deco_layer(context)
    deco_layer_nodes = deco_layer.nodes
    deco_layer_nodes_index = deco_layer.nodes_index
    return 0 <= deco_layer_nodes_index < len(deco_layer_nodes)


def get_selected_deco_layer_node(context: Context) -> Optional[BDK_PG_terrain_layer_node]:
    if not has_selected_deco_layer_node(context):
        return None
    deco_layer = get_selected_deco_layer(context)
    return deco_layer.nodes[deco_layer.nodes_index]


class BDK_PT_terrain_deco_layer_nodes(Panel):
    bl_parent_id = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Nodes'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 2

    @classmethod
    def poll(cls, context: 'Context'):
        return has_deco_layer_selected(context)

    def draw(self, context: 'Context'):
        layout = self.layout
        deco_layer = get_selected_deco_layer(context)
        row = layout.row()
        row.column().template_list(
            'BDK_UL_terrain_deco_layer_nodes', '',
            deco_layer, 'nodes',
            deco_layer, 'nodes_index',
            sort_lock=True, rows=3)
        col = row.column(align=True)
        col.operator_menu_enum(BDK_OT_terrain_deco_layer_nodes_add.bl_idname, 'type', icon='ADD', text='')
        col.operator(BDK_OT_terrain_deco_layer_nodes_remove.bl_idname, icon='REMOVE', text='')
        col.separator()
        col.operator(BDK_OT_terrain_deco_layer_nodes_move.bl_idname, icon='TRIA_UP', text='').direction = 'UP'
        col.operator(BDK_OT_terrain_deco_layer_nodes_move.bl_idname, icon='TRIA_DOWN', text='').direction = 'DOWN'

        selected_deco_layer_node = get_selected_deco_layer_node(context)
        if selected_deco_layer_node:
            layout.separator()
            if selected_deco_layer_node.type == 'TERRAIN_LAYER':
                layout.prop(selected_deco_layer_node, 'layer_name')
            elif selected_deco_layer_node.type == 'NORMAL':
                flow = layout.grid_flow(align=True, columns=2)
                flow.use_property_split = True

                col = flow.column(align=True)

                col.prop(selected_deco_layer_node, 'normal_angle_min')
                col.prop(selected_deco_layer_node, 'normal_angle_max', text='Max')
                # The blur node is *extremely* expensive, so we don't want to show it for now.
                # self.layout.prop(selected_deco_layer_node, 'blur')
                # if selected_deco_layer_node.blur:
                #     self.layout.prop(selected_deco_layer_node, 'blur_iterations')


class BDK_PT_terrain_deco_layer_debug(Panel):
    bl_parent_id = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Debug'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 100
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: 'Context'):
        return has_deco_layer_selected(context) and should_show_bdk_developer_extras(context)

    def draw(self, context: 'Context'):
        deco_layer = get_selected_deco_layer(context)
        self.layout.prop(deco_layer, 'id')


class BDK_PT_terrain_deco_layers_mesh(Panel):
    bl_parent_id = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Mesh'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 0

    @classmethod
    def poll(cls, context: 'Context'):
        return has_deco_layer_selected(context)

    def draw(self, context: 'Context'):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer = deco_layers[deco_layers_index]

        box = self.layout.box()

        icon_id = 0
        if deco_layer.static_mesh and deco_layer.static_mesh.preview:
            icon_id = deco_layer.static_mesh.preview.icon_id
        box.template_icon(icon_value=icon_id, scale=4)

        self.layout.separator()

        flow = self.layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        flow.use_property_split = True

        flow.column().prop(deco_layer, 'static_mesh', text='Static Mesh')


class BDK_PT_terrain_deco_layers_settings(Panel):
    bl_parent_id = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Settings'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_order = 1
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context: 'Context'):
        return has_deco_layer_selected(context)

    def draw(self, context: 'Context'):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer = deco_layers[deco_layers_index]

        flow = self.layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        flow.use_property_split = True

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
        row = flow.column(align=True)
        row.prop(deco_layer, 'random_yaw')
        flow.separator()

        flow.column().prop(deco_layer, 'force_draw')
        flow.column().prop(deco_layer, 'detail_mode')
        flow.column().prop(deco_layer, 'draw_order')


class BDK_PT_terrain_deco_layers(Panel):
    bl_idname = 'BDK_PT_terrain_deco_layers'
    bl_label = 'Deco Layers'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = 'BDK_PT_terrain_info'
    bl_order = 1

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def draw(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)

        row = self.layout.row()
        row.template_list('BDK_UL_terrain_deco_layers', '',
                          terrain_info, 'deco_layers',
                          terrain_info, 'deco_layers_index', rows=3, sort_lock=True)

        col = row.column(align=True)
        col.operator(BDK_OT_terrain_deco_layer_add.bl_idname, icon='ADD', text='')
        col.operator(BDK_OT_terrain_deco_layer_remove.bl_idname, icon='REMOVE', text='')

        col.separator()

        col.menu(BDK_MT_terrain_deco_layers_context_menu.bl_idname, icon='DOWNARROW_HLT', text='')


class BDK_UL_terrain_layers(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        icon = row.icon(item.material) if item.material else None
        if icon:
            row.prop(item, 'name', text='', emboss=False, icon_value=icon)
        else:
            row.prop(item, 'name', text='', emboss=False, icon='IMAGE')

        mesh = cast(Mesh, context.active_object.data)
        color_attribute_index = mesh.color_attributes.find(item.id)
        if color_attribute_index == mesh.color_attributes.active_color_index:
            row.label(text='', icon='VPAINT_HLT')

        row.prop(item, 'is_visible', icon=('HIDE_OFF' if item.is_visible else 'HIDE_ON'), text='', emboss=False)


class BDK_UL_terrain_deco_layers(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        row.prop(item, 'name', text='', emboss=False)

        mesh = cast(Mesh, context.active_object.data)
        color_attribute_index = mesh.color_attributes.find(item.id)
        if color_attribute_index == mesh.color_attributes.active_color_index:
            row.label(text='', icon='VPAINT_HLT')

        row.prop(item.object, 'hide_viewport', icon='HIDE_OFF' if not item.object.hide_viewport else 'HIDE_ON', text='', emboss=False)


class BDK_UL_terrain_deco_layer_nodes(UIList):
    def draw_item(self, context: Context, layout: UILayout, data: AnyType, item: AnyType, icon: int,
                  active_data: AnyType, active_property: str, index: int = 0, flt_flag: int = 0):
        row = layout.row()
        col = row.column(align=True)

        mesh = cast(Mesh, context.active_object.data)
        color_attribute_index = mesh.color_attributes.find(item.id)
        if color_attribute_index == mesh.color_attributes.active_color_index:
            row.label(text='', icon='VPAINT_HLT')

        if item.type == 'TERRAIN_LAYER':
            if item.layer_name:
                col.label(text=item.layer_name, icon=terrain_layer_node_type_icons[item.type])
            else:
                col.label(text='<no layer selected>', icon=terrain_layer_node_type_icons[item.type])
        else:
            col.prop(item, 'name', text='', emboss=False, icon=terrain_layer_node_type_icons[item.type])

        row = row.row(align=True)

        if item.type not in ('MAP_RANGE',):  # add a function to get the meta-type of the node
            row.prop(item, 'operation', text='', emboss=False)
            row.prop(item, 'factor', text='', emboss=False)

        if item.type == 'MAP_RANGE':
            row.prop(item, 'map_range_from_min', text='')
            row.prop(item, 'map_range_from_max', text='')

        row.prop(item, 'mute', text='', emboss=False, icon='HIDE_OFF' if not item.mute else 'HIDE_ON')


classes = (
    BDK_PT_terrain_info,
    BDK_PT_terrain_info_debug,
    BDK_PT_terrain_layers,
    BDK_PT_terrain_deco_layers,
    BDK_UL_terrain_layers,
    BDK_PT_terrain_layer_settings,
    BDK_PT_terrain_layer_debug,
    BDK_UL_terrain_deco_layers,
    BDK_UL_terrain_deco_layer_nodes,
    BDK_PT_terrain_deco_layers_mesh,
    BDK_PT_terrain_deco_layers_settings,  # TODO: rename with singular name
    BDK_PT_terrain_deco_layer_nodes,
    BDK_PT_terrain_deco_layer_debug,
    BDK_MT_terrain_deco_layers_context_menu,
    BDK_MT_terrain_layers_context_menu,
)
