import uuid

import bpy
from bpy.types import Operator, Context, Object

from ....helpers import get_terrain_doodad, copy_simple_property_group
from .builder import add_terrain_doodad_scatter_layer, ensure_scatter_layer, add_scatter_layer_object, \
    ensure_scatter_layer_modifiers
from ..kernel import ensure_terrain_doodad_layer_indices
from ..operators import poll_has_terrain_doodad_selected, poll_has_terrain_doodad_selected_scatter_layer, \
    poll_has_terrain_doodad_selected_scatter_layer_object


class BDK_OT_terrain_doodad_scatter_layer_add(Operator):
    bl_label = 'Add Scatter Layer'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected(cls, context)

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad

        # Add a new sculpting layer.
        scatter_layer = add_terrain_doodad_scatter_layer(terrain_doodad)

        ensure_scatter_layer(scatter_layer)

        # Add an object to the scatter layer.
        add_scatter_layer_object(scatter_layer)

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        terrain_doodad.scatter_layers_index = len(terrain_doodad.scatter_layers) - 1

        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_scatter_layer_remove(Operator):
    bl_label = 'Remove Scatter Layer'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected_scatter_layer(cls, context)

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        scatter_layers_index = terrain_doodad.scatter_layers_index

        scatter_layer = terrain_doodad.scatter_layers[scatter_layers_index]

        def delete_scatter_layer_seed_object(obj: Object):
            if obj is None:
                return
            # Delete the node trees for all modifiers.
            for modifier in obj.modifiers:
                if modifier.type == 'NODES' and modifier.node_group is not None:
                    bpy.data.node_groups.remove(modifier.node_group)
                bpy.data.meshes.remove(obj.data)

        delete_scatter_layer_seed_object(scatter_layer.planter_object)
        delete_scatter_layer_seed_object(scatter_layer.seed_object)
        delete_scatter_layer_seed_object(scatter_layer.sprout_object)

        scatter_layer_id = scatter_layer.id

        # TODO: delete references to this scatter layer in the paint & sculpt layers
        for sculpt_layer in terrain_doodad.sculpt_layers:
            if sculpt_layer.scatter_layer_id == scatter_layer_id:
                sculpt_layer.scatter_layer_id = ''

        for paint_layer in terrain_doodad.paint_layers:
            if paint_layer.scatter_layer_id == scatter_layer_id:
                paint_layer.scatter_layer_id = ''

        terrain_doodad.scatter_layers.remove(scatter_layers_index)
        terrain_doodad.scatter_layers_index = min(len(terrain_doodad.scatter_layers) - 1, scatter_layers_index)

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Delete the associated node group.
        if scatter_layer_id in bpy.data.node_groups:
            bpy.data.node_groups.remove(bpy.data.node_groups[scatter_layer_id])

        # Update the scatter layer modifiers.
        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


def poll_can_add_scatter_layer_object(cls, context: Context) -> bool:
    if not poll_has_terrain_doodad_selected_scatter_layer(cls, context):
        return False
    terrain_doodad = get_terrain_doodad(context.active_object)
    scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]
    if len(scatter_layer.objects) >= 8:
        cls.poll_message_set('Cannot add more than 8 scatter layer objects')
        return False
    return True


class BDK_OT_terrain_doodad_scatter_layer_objects_add(Operator):
    bl_label = 'Add Scatter Layer Object'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_objects_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_can_add_scatter_layer_object(cls, context)

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        # Add a new scatter layer object.
        add_scatter_layer_object(scatter_layer)

        # Set the sculpting component index to the new sculpting component.
        scatter_layer.objects_index = len(scatter_layer.objects) - 1

        # TODO: do less here, just ensure the modifier for this scatter layer.
        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_scatter_layer_objects_remove(Operator):
    bl_label = 'Remove Scatter Layer Object'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_objects_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected_scatter_layer_object(cls, context)

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        objects_index = scatter_layer.objects_index
        scatter_layer.objects.remove(scatter_layer.objects_index)
        scatter_layer.objects_index = min(len(scatter_layer.objects) - 1, objects_index)

        # TODO: do less here, just ensure the modifier for this scatter layer.
        # Update the scatter layer modifiers.
        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_scatter_layer_duplicate(Operator):
    bl_label = 'Duplicate Scatter Layer'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected_scatter_layer(cls, context)

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]
        scatter_layer_copy = add_terrain_doodad_scatter_layer(terrain_doodad, scatter_layer.name)
        copy_simple_property_group(scatter_layer, scatter_layer_copy,
                                   {'id', 'name', 'planter_object', 'seed_object', 'sprout_object', 'mask_attribute_id'}
                                   )

        # Copy the scatter layer objects.
        for scatter_layer_object in scatter_layer.objects:
            scatter_layer_object_copy = scatter_layer_copy.objects.add()
            scatter_layer_object_copy.id = uuid.uuid4().hex
            copy_simple_property_group(scatter_layer_object, scatter_layer_object_copy, {'id'})

        # Select the new scatter layer.
        terrain_doodad.scatter_layers_index = len(terrain_doodad.scatter_layers) - 1

        ensure_scatter_layer(scatter_layer_copy)
        ensure_terrain_doodad_layer_indices(terrain_doodad)
        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_scatter_layer_objects_duplicate(Operator):
    bl_label = 'Duplicate Scatter Layer Object'
    bl_idname = 'bdk.terrain_doodad_scatter_layer_objects_duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_can_add_scatter_layer_object(cls, context) and \
            poll_has_terrain_doodad_selected_scatter_layer_object(cls, context)

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]

        scatter_layer_object = scatter_layer.objects[scatter_layer.objects_index]
        scatter_layer_object_copy = add_scatter_layer_object(scatter_layer)

        # TODO: This doesn't do a recursive copy on PointerProperties.
        copy_simple_property_group(scatter_layer_object, scatter_layer_object_copy, {'id'})

        # Set the scatter layer object index to the new scatter layer object.
        scatter_layer.objects_index = len(scatter_layer.objects) - 1

        ensure_scatter_layer(scatter_layer)
        ensure_terrain_doodad_layer_indices(terrain_doodad)
        ensure_scatter_layer_modifiers(context, terrain_doodad)

        return {'FINISHED'}


classes = (
    BDK_OT_terrain_doodad_scatter_layer_add,
    BDK_OT_terrain_doodad_scatter_layer_remove,
    BDK_OT_terrain_doodad_scatter_layer_duplicate,
    BDK_OT_terrain_doodad_scatter_layer_objects_add,
    BDK_OT_terrain_doodad_scatter_layer_objects_remove,
    BDK_OT_terrain_doodad_scatter_layer_objects_duplicate,
)
