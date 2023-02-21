from bpy.types import Operator, Context


def create_fluid_surface(context: Context):
    pass


class BDK_OT_FluidSurfaceAdd(Operator):
    bl_label = 'Add FluidSurface'
    bl_idname = 'bdk.fluid_surface_add'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context):
        # TODO: add a mesh object, attach a geonode to it with a BDK FluidSurface node
        pass


classes = (
    BDK_OT_FluidSurfaceAdd,
)
