from bpy.types import Menu

from ..terrain import operators as terrain_operators
from ..terrain.objects import operators as terrain_object_operators
from ..projector import operators as projector_operators
from ..fluid_surface import operators as fluid_surface_operators


class BDK_MT_object_add_menu(Menu):
    bl_idname = 'BDK_MT_object_add_menu'
    bl_label = 'BDK'

    def draw(self, context):
        self.layout.operator(terrain_operators.BDK_OT_terrain_info_add.bl_idname, text='Terrain Info', icon='GRID')
        self.layout.operator_menu_enum(terrain_object_operators.BDK_OT_terrain_object_add.bl_idname, 'object_type',
                                       text='Terrain Object', icon='CURVE_DATA')
        self.layout.operator(projector_operators.BDK_OT_projector_add.bl_idname, text='Projector', icon='CAMERA_DATA')
        self.layout.operator(fluid_surface_operators.BDK_OT_fluid_surface_add.bl_idname, text='Fluid Surface',
                             icon='MOD_FLUIDSIM')


classes = (
    BDK_MT_object_add_menu,
)
