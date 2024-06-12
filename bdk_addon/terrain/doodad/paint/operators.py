from bpy.props import EnumProperty
from bpy.types import Operator, Context

from ....data import move_direction_items
from ....helpers import get_terrain_doodad, is_active_object_terrain_doodad, copy_simple_property_group
from ..builder import ensure_terrain_info_modifiers
from ..kernel import add_terrain_doodad_paint_layer, ensure_terrain_doodad_layer_indices
from ..operators import poll_has_terrain_doodad_selected_paint_layer


class BDK_OT_terrain_doodad_paint_layer_add(Operator):
    bl_label = 'Add Paint Layer'
    bl_idname = 'bdk.terrain_doodad_paint_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_doodad(context):
            cls.poll_message_set('Active object must be a terrain doodad')
            return False
        return True

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = get_terrain_doodad(terrain_doodad_object)

        add_terrain_doodad_paint_layer(terrain_doodad, 'Paint Layer')

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        # Set the paint layer index to the new paint layer.
        terrain_doodad.paint_layers_index = len(terrain_doodad.paint_layers) - 1

        return {'FINISHED'}


class BDK_OT_terrain_doodad_paint_layer_move(Operator):
    bl_idname = 'bdk.terrain_doodad_paint_layer_move'
    bl_label = 'Move Paint Layer'
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name='Direction',
        description='The direction to move the layer',
        items=move_direction_items
    )

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected_paint_layer(cls, context)

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        paint_layers = terrain_doodad.paint_layers
        paint_layers_index = terrain_doodad.paint_layers_index

        if self.direction == 'UP' and paint_layers_index > 0:
            paint_layers.move(paint_layers_index, paint_layers_index - 1)
            terrain_doodad.paint_layers_index -= 1
        elif self.direction == 'DOWN' and paint_layers_index < len(paint_layers) - 1:
            paint_layers.move(paint_layers_index, paint_layers_index + 1)
            terrain_doodad.paint_layers_index += 1

        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_paint_layer_remove(Operator):
    bl_label = 'Remove Paint Layer'
    bl_idname = 'bdk.terrain_doodad_paint_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected_paint_layer(cls, context)

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        paint_layers_index = terrain_doodad.paint_layers_index

        terrain_doodad.paint_layers.remove(paint_layers_index)
        terrain_doodad.paint_layers_index = min(len(terrain_doodad.paint_layers) - 1, paint_layers_index)

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


def get_terrain_doodad_selected_paint_layer(context: Context):
    terrain_doodad = get_terrain_doodad(context.active_object)
    if terrain_doodad is None:
        return None
    if len(terrain_doodad.paint_layers) == 0 or terrain_doodad.paint_layers_index < 0:
        return None
    return terrain_doodad.paint_layers[terrain_doodad.paint_layers_index]


class BDK_OT_terrain_doodad_paint_layer_duplicate(Operator):
    bl_label = 'Duplicate Paint Layer'
    bl_idname = 'bdk.terrain_doodad_paint_layer_duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected_paint_layer(cls, context)

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        paint_layer = get_terrain_doodad_selected_paint_layer(context)
        paint_layer_copy = add_terrain_doodad_paint_layer(terrain_doodad, paint_layer.name)

        # Copy the paint layer. Ignore the name because changing it will trigger the name change callback.
        copy_simple_property_group(paint_layer, paint_layer_copy, ignore={'id', 'name'})

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


classes = (
    BDK_OT_terrain_doodad_paint_layer_add,
    BDK_OT_terrain_doodad_paint_layer_remove,
    BDK_OT_terrain_doodad_paint_layer_duplicate,
    BDK_OT_terrain_doodad_paint_layer_move,
)
