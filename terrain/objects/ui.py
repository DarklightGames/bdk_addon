from bpy.types import Panel, Context


class BDK_PT_terrain_object(Panel):
    bl_label = 'Terrain Object'
    bl_idname = 'BDK_PT_terrain_object'
    bl_category = 'Terrain'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context: Context):
        if context.active_object is None:
            return False
        # TODO: how to determine if the active object is a terrain object?
        return False

    def draw(self, context: Context):
        pass


classes = (
    BDK_PT_terrain_object,
)
