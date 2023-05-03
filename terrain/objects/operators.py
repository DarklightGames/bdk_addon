from bpy.types import Operator, Context, Collection

from ...helpers import is_active_object_terrain_info
from .builder import create_terrain_object
from .definitions import create_road_terrain_object_definition


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
        definition = create_road_terrain_object_definition()
        terrain_info_object = context.active_object
        terrain_object = create_terrain_object(context, definition, terrain_info_object)

        # Link and parent the terrain object to the terrain info.
        collection: Collection = terrain_info_object.users_collection[0]
        collection.objects.link(terrain_object)
        terrain_object.parent = terrain_info_object

        # Select the terrain object.
        context.view_layer.objects.active = terrain_object
        terrain_object.select_set(True)

        return {'FINISHED'}


classes = (
    BDK_OT_terrain_object_add,
)
