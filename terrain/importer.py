from bpy.types import Context, Operator


class BDK_OT_terrain_info_import(Operator):

    @classmethod
    def poll(cls, context: Context):
        if context.mode != 'OBJECT':
            cls.poll_message_set('Must be in object mode')
            return False
        return True
