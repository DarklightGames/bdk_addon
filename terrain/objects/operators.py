import bpy
from bpy.types import Operator, Context, Collection

from ...helpers import is_active_object_terrain_info
from .builder import create_terrain_object, update_terrain_object_geometry_node_group


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

        # Deselect the terrain info object.
        terrain_info_object.select_set(False)

        # Select the terrain object.
        context.view_layer.objects.active = terrain_object
        terrain_object.select_set(True)

        return {'FINISHED'}


def update_terrain_object_indices(terrain_object):
    print('Updating terrain object indices')

    # Sculpt Components
    for i, sculpt_layer in enumerate(terrain_object.sculpt_layers):
        sculpt_layer.index = i
        print(f'Sculpt component {sculpt_layer.name} index: {sculpt_layer.index}')
    # Paint Components
    for i, paint_layer in enumerate(terrain_object.paint_layers):
        print(f'Paint component {paint_layer.terrain_layer_name} index: {paint_layer.index}')
        paint_layer.index = i


class BDK_OT_terrain_object_sculpt_layer_add(Operator):
    bl_label = 'Add Sculpt Component'
    bl_idname = 'bdk.terrain_object_sculpt_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_object = terrain_info_object.bdk.terrain_object
        sculpt_layer = terrain_object.sculpt_layers.add()
        sculpt_layer.terrain_object = terrain_object.object

        # Update all the indices of the components.
        update_terrain_object_indices(terrain_object)

        # Update the geometry node tree.
        update_terrain_object_geometry_node_group(terrain_object)

        # Set the sculpt component index to the new sculpt component.
        terrain_object.sculpt_layers_index = len(terrain_object.sculpt_layers) - 1

        return {'FINISHED'}


class BDK_OT_terrain_object_sculpt_layer_remove(Operator):
    bl_label = 'Remove Sculpt Component'
    bl_idname = 'bdk.terrain_object_sculpt_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_object = terrain_info_object.bdk.terrain_object
        sculpt_layers_index = terrain_object.sculpt_layers_index

        terrain_object.sculpt_layers.remove(sculpt_layers_index)
        terrain_object.sculpt_layers_index = min(len(terrain_object.sculpt_layers) - 1, sculpt_layers_index)

        # Update all the indices of the components.
        update_terrain_object_indices(terrain_object)

        # Update the geometry node tree.
        update_terrain_object_geometry_node_group(terrain_object)

        return {'FINISHED'}


# Add an operator that moves the sculpt component up and down in the list.
class BDK_OT_terrain_object_sculpt_layer_move(Operator):
    bl_idname = 'bdk.terrain_object_sculpt_layer_move'
    bl_label = 'Move Sculpt Component'
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        name='Direction',
        items=(
            ('UP', 'Up', ''),
            ('DOWN', 'Down', '')
        )
    )

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_object = terrain_info_object.bdk.terrain_object
        sculpt_layers_index = terrain_object.sculpt_layers_index
        if self.direction == 'UP':
            terrain_object.sculpt_layers.move(sculpt_layers_index, sculpt_layers_index - 1)
            terrain_object.sculpt_layers_index -= 1
        elif self.direction == 'DOWN':
            terrain_object.sculpt_layers.move(sculpt_layers_index, sculpt_layers_index + 1)
            terrain_object.sculpt_layers_index += 1

        update_terrain_object_indices(terrain_object)
        update_terrain_object_geometry_node_group(terrain_object)

        return {'FINISHED'}


class BDK_OT_terrain_object_bake(Operator):
    bl_label = 'Bake Terrain Object'
    bl_idname = 'bdk.terrain_object_bake'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        # TODO: Apply the associated modifier in the terrain info object, then delete the terrain object.
        terrain_object_object = context.active_object
        terrain_info_object = terrain_object_object.parent  # TODO: technically this can be manually changed, so we should probably store a reference to the terrain info object in the terrain object.

        terrain_object = terrain_object_object.bdk.terrain_object

        # Select the terrain info object and make it the active object.
        context.view_layer.objects.active = terrain_info_object
        terrain_info_object.select_set(True)

        # Apply the associated modifier in the terrain info object. (we are just deleting it for now)
        for modifier in terrain_info_object.modifiers:
            if modifier.name == terrain_object.id:
                bpy.ops.object.modifier_apply(modifier=modifier.name)
                break

        # Delete the terrain object node group.
        bpy.data.node_groups.remove(terrain_object.node_tree)

        # Delete the terrain object.
        bpy.data.objects.remove(terrain_object_object)

        # Deselect the terrain info object.
        terrain_info_object.select_set(False)

        return {'FINISHED'}


class BDK_OT_terrain_object_paint_layer_add(Operator):
    bl_label = 'Add Paint Component'
    bl_idname = 'bdk.terrain_object_paint_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_object = terrain_info_object.bdk.terrain_object
        paint_layer = terrain_object.paint_layers.add()
        paint_layer.terrain_object = terrain_object.object

        # Update all the indices of the components.
        update_terrain_object_indices(terrain_object)

        # Update the geometry node tree.
        update_terrain_object_geometry_node_group(terrain_object)

        # Set the paint component index to the new paint component.
        terrain_object.paint_layers_index = len(terrain_object.paint_layers) - 1

        return {'FINISHED'}


class BDK_OT_terrain_object_paint_layer_remove(Operator):
    bl_label = 'Remove Paint Component'
    bl_idname = 'bdk.terrain_object_paint_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_object = terrain_info_object.bdk.terrain_object
        paint_layers_index = terrain_object.paint_layers_index

        terrain_object.paint_layers.remove(paint_layers_index)
        terrain_object.paint_layers_index = min(len(terrain_object.paint_layers) - 1, paint_layers_index)

        # Update all the indices of the components.
        update_terrain_object_indices(terrain_object)

        # Update the geometry node tree.
        update_terrain_object_geometry_node_group(terrain_object)

        return {'FINISHED'}


classes = (
    BDK_OT_terrain_object_add,
    BDK_OT_terrain_object_bake,
    BDK_OT_terrain_object_sculpt_layer_add,
    BDK_OT_terrain_object_sculpt_layer_remove,
    BDK_OT_terrain_object_sculpt_layer_move,
    BDK_OT_terrain_object_paint_layer_add,
    BDK_OT_terrain_object_paint_layer_remove
)
