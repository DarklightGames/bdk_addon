import bpy
from bpy.types import Operator, Context, Collection

from ...helpers import is_active_object_terrain_info
from .builder import create_terrain_object


class BDK_OT_terrain_object_add(Operator):
    bl_label = 'Add Terrain Object'
    bl_idname = 'bdk.terrain_object_add'

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            cls.poll_message_set('The active object must be a terrain info object')
            return False
        return True

    def execute(self, context: Context):
        # TODO: have a way to select the terrain object definition.
        terrain_info_object = context.active_object
        terrain_object = create_terrain_object(context, terrain_info_object)

        # Link and parent the terrain object to the terrain info.
        collection: Collection = terrain_info_object.users_collection[0]
        collection.objects.link(terrain_object)
        terrain_object.parent = terrain_info_object

        # Select the terrain object.
        context.view_layer.objects.active = terrain_object
        terrain_object.select_set(True)

        return {'FINISHED'}


class BDK_OT_terrain_object_bake(Operator):
    bl_label = 'Bake Terrain Object'
    bl_idname = 'bdk.terrain_object_bake'

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            cls.poll_message_set('The active object must be a terrain info object')
            return False
        return True

    def execute(self, context: Context):
        # TODO: Apply the associated modifier in the terrain info object, then delete the terrain object.
        terrain_object = context.active_object
        terrain_info_object = terrain_object.parent  # TODO: technically this can be manually changed, so we should probably store a reference to the terrain info object in the terrain object.
        context.view_layer.objects.remove(terrain_object, do_unlink=True)
        return {'FINISHED'}


classes = (
    BDK_OT_terrain_object_add,
)
