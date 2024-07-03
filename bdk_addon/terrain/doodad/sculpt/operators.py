import uuid

from bpy.props import EnumProperty
from bpy.types import Operator, Context

from ..builder import ensure_terrain_info_modifiers
from ..kernel import ensure_terrain_doodad_layer_indices, add_terrain_doodad_sculpt_layer
from ..operators import poll_has_terrain_doodad_selected
from ....helpers import copy_simple_property_group, get_terrain_doodad, ensure_name_unique


def poll_has_terrain_doodad_selected_sculpt_layer(cls, context: Context) -> bool:
    if not poll_has_terrain_doodad_selected(cls, context):
        return False
    terrain_doodad = get_terrain_doodad(context.active_object)
    if len(terrain_doodad.sculpt_layers) == 0 or terrain_doodad.sculpt_layers_index < 0:
        cls.poll_message_set('Must have a sculpt layer selected')
        return False
    return True


class BDK_OT_terrain_doodad_sculpt_layer_add(Operator):
    bl_label = 'Add Sculpt Layer'
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad

        # Add a new sculpting layer.
        add_terrain_doodad_sculpt_layer(terrain_doodad)

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Set the sculpting component index to the new sculpting component.
        terrain_doodad.sculpt_layers_index = len(terrain_doodad.sculpt_layers) - 1

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        # Mark the terrain info object as needing to be updated in the dependency graph.
        terrain_doodad_object.update_tag()
        terrain_doodad.terrain_info_object.update_tag()

        return {'FINISHED'}


class BDK_OT_terrain_doodad_sculpt_layer_move(Operator):
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_move'
    bl_label = 'Move Sculpt Layer'
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(name='Direction', items=(('UP', 'Up', ''), ('DOWN', 'Down', '')))

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected_sculpt_layer(cls, context)

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        sculpt_layers = terrain_doodad.sculpt_layers
        sculpt_layers_index = terrain_doodad.sculpt_layers_index

        if self.direction == 'UP' and sculpt_layers_index > 0:
            sculpt_layers.move(sculpt_layers_index, sculpt_layers_index - 1)
            terrain_doodad.sculpt_layers_index -= 1
        elif self.direction == 'DOWN' and sculpt_layers_index < len(sculpt_layers) - 1:
            sculpt_layers.move(sculpt_layers_index, sculpt_layers_index + 1)
            terrain_doodad.sculpt_layers_index += 1

        # The order of the sculpt layers has changed, so we need to rebuild the geometry node tree (perhaps just limit
        # this to the appropriate modifiers instead of doing everything!)
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_sculpt_layer_remove(Operator):
    bl_label = 'Remove Sculpt Layer'
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Remove the selected sculpt layer'

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected_sculpt_layer(cls, context)

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        sculpt_layers_index = terrain_doodad.sculpt_layers_index

        terrain_doodad.sculpt_layers.remove(sculpt_layers_index)
        terrain_doodad.sculpt_layers_index = min(len(terrain_doodad.sculpt_layers) - 1, sculpt_layers_index)

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        # Mark the terrain info object as needing to be updated in the dependency graph.
        terrain_doodad_object.update_tag()
        terrain_doodad.terrain_info_object.update_tag()

        return {'FINISHED'}


class BDK_OT_terrain_doodad_sculpt_layer_duplicate(Operator):
    bl_label = 'Duplicate Sculpt Layers'
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_duplicate'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Duplicate the selected sculpt layer'

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected_sculpt_layer(cls, context)

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        sculpt_layer_copy = terrain_doodad.sculpt_layers.add()

        copy_simple_property_group(terrain_doodad.sculpt_layers[terrain_doodad.sculpt_layers_index], sculpt_layer_copy)

        # Make sure the copy has a unique id.
        sculpt_layer_copy.id = uuid.uuid4().hex
        sculpt_layer_copy.name = ensure_name_unique(sculpt_layer_copy.name, [layer.name for layer in terrain_doodad.sculpt_layers])

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


classes = (
    BDK_OT_terrain_doodad_sculpt_layer_add,
    BDK_OT_terrain_doodad_sculpt_layer_move,
    BDK_OT_terrain_doodad_sculpt_layer_remove,
    BDK_OT_terrain_doodad_sculpt_layer_duplicate,
)
