from bpy.types import Menu, Panel

from ..bsp import operators as bsp_operators
from ..fluid_surface import operators as fluid_surface_operators
from ..projector import operators as projector_operators
from ..projector.operators import BDK_OT_projectors_bake, BDK_OT_projectors_unbake
from ..terrain import operators as terrain_operators
from ..terrain.doodad import operators as terrain_doodad_operators
from ..t3d import operators as t3d_operators


class BDK_MT_object_add_menu(Menu):
    bl_idname = 'BDK_MT_object_add_menu'
    bl_label = 'BDK'

    def draw(self, context):
        self.layout.operator(terrain_operators.BDK_OT_terrain_info_add.bl_idname, text='Terrain Info', icon='GRID')
        self.layout.operator_menu_enum(terrain_doodad_operators.BDK_OT_terrain_doodad_add.bl_idname, 'object_type',
                                       text='Terrain Doodad', icon='CURVE_DATA')
        self.layout.operator(projector_operators.BDK_OT_projector_add.bl_idname, text='Projector', icon='CAMERA_DATA')
        self.layout.operator(fluid_surface_operators.BDK_OT_fluid_surface_add.bl_idname, text='Fluid Surface',
                             icon='MOD_FLUIDSIM')
        self.layout.operator(bsp_operators.BDK_OT_bsp_brush_add.bl_idname, text='BSP Brush', icon='MOD_BUILD')


class BDK_PT_node_tree(Panel):
    bl_idname = 'BDK_PT_node_tree'
    bl_label = 'BDK'
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Group'
    bl_order = 100

    @classmethod
    def poll(cls, context):
        node_tree = context.space_data.edit_tree
        return node_tree is not None and node_tree.bdk.build_hash != ''

    def draw(self, context):
        node_tree = context.space_data.edit_tree
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(node_tree.bdk, 'build_hash', text='Build Hash', icon='KEYINGSET', emboss=False)


class BDK_PT_scene(Panel):
    bl_idname = 'BDK_PT_scene'
    bl_label = 'BDK'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        scene = context.scene

        row = layout.row()
        row.enabled = False
        row.prop(scene.bdk, 'repository_id', text='Repository ID')

        layout.prop(scene.bdk, 'level_object', text='Level Object')


class BDK_PT_bdk(Panel):
    bl_idname = 'BDK_PT_bdk'
    bl_label = 'BDK'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context):
        layout = self.layout

        # # Projectors
        # projectors_header, projectors_panel = layout.panel('Projectors', default_closed=True)
        # projectors_header.label(text='Projectors')
        # if projectors_panel:
        #     row = projectors_panel.row(align=True)
        #     row.operator(BDK_OT_projectors_bake.bl_idname, text='Bake')
        #     row.operator(BDK_OT_projectors_unbake.bl_idname, text='Unbake')

        # T3D
        t3d_header, t3d_panel = layout.panel('T3D', default_closed=True)
        t3d_header.label(text='T3D')
        if t3d_panel:
            col = t3d_panel.column(align=True)
            col.operator(t3d_operators.BDK_OT_t3d_copy_to_clipboard.bl_idname, text='Copy to Clipboard', icon='COPYDOWN')
            col.operator(t3d_operators.BDK_OT_t3d_import_from_clipboard.bl_idname, text='Import from Clipboard', icon='PASTEDOWN')


class BDK_MT_object_menu(Menu):
    bl_idname = 'BDK_MT_object_menu'
    bl_label = 'BDK'

    def draw(self, context):
        self.layout.operator(bsp_operators.BDK_OT_convert_to_bsp_brush.bl_idname)
        self.layout.operator(terrain_doodad_operators.BDK_OT_convert_to_terrain_doodad.bl_idname)


classes = (
    BDK_MT_object_add_menu,
    BDK_MT_object_menu,
    BDK_PT_node_tree,
    BDK_PT_scene,
    BDK_PT_bdk,
)
