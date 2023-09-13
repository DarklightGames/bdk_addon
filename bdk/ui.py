from bpy.types import Menu, Panel

from ..bsp import operators as bsp_operators
from ..fluid_surface import operators as fluid_surface_operators
from ..projector import operators as projector_operators
from ..terrain import operators as terrain_operators
from ..terrain.doodad import operators as terrain_doodad_operators


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

classes = (
    BDK_MT_object_add_menu,
    BDK_PT_node_tree
)
