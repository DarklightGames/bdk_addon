from bpy.types import Menu

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


classes = (
    BDK_MT_object_add_menu,
)
