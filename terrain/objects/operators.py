import uuid

import bpy
from bpy.types import Operator, Context, Collection, Event
from bpy.props import EnumProperty

from ...helpers import is_active_object_terrain_info, copy_simple_property_group
from .builder import create_terrain_object, update_terrain_object_geometry_node_group


class BDK_OT_terrain_object_add(Operator):
    bl_label = 'Add Terrain Object'
    bl_idname = 'bdk.terrain_object_add'
    bl_description = 'Add a terrain object to the scene'

    object_type: EnumProperty(
        name='Type',
        items=(
            ('CURVE', 'Curve', 'A terrain object that uses a curve to define the shape', 'CURVE_DATA', 0),
            ('MESH', 'Mesh', 'A terrain object that uses a mesh to define the shape', 'MESH_DATA', 1),
            ('EMPTY', 'Empty', 'A terrain object that uses an empty to define the shape', 'EMPTY_DATA', 2),
        )
    )

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            cls.poll_message_set('The active object must be a terrain info object')
            return False
        return True

    def execute(self, context: Context):
        # TODO: have a way to select the terrain object definition.
        terrain_info_object = context.active_object
        terrain_object = create_terrain_object(context, terrain_info_object, self.object_type)

        """
        BUG: If the terrain object has been added as rigid body, the collection will be the
        RigidBodyWorld collection, which isn't actually a collection that shows up in the outliner or the view layer,
        and makes the function fail.
        
        How can we get the *actual* collection that the terrain object is in (the one that shows up in the outliner)?
        """

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
    # Sculpt Components
    for i, sculpt_layer in enumerate(terrain_object.sculpt_layers):
        sculpt_layer.index = i
    # Paint Components
    for i, paint_layer in enumerate(terrain_object.paint_layers):
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


# TODO: Make this a macro operator that duplicates and then moves mode (same behavior as native duplicate).

class BDK_OT_terrain_object_duplicate(Operator):
    bl_idname = 'bdk.terrain_object_duplicate'
    bl_label = 'Duplicate Terrain Object'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Duplicate the terrain object'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object is not None and context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        new_id = uuid.uuid4().hex
        terrain_object_object = context.active_object
        object_copy = terrain_object_object.copy()
        object_copy.name = new_id
        if terrain_object_object.data:
            data_copy = terrain_object_object.data.copy()
            data_copy.name = new_id
            object_copy.data = data_copy
        collection = terrain_object_object.users_collection[0]  # TODO: issue with RigidBody collection
        collection.objects.link(object_copy)

        copy_simple_property_group(terrain_object_object.bdk.terrain_object, object_copy.bdk.terrain_object)

        # Make a new node group for the new object.
        node_group = bpy.data.node_groups.new(name=new_id, type='GeometryNodeTree')

        terrain_object = object_copy.bdk.terrain_object
        terrain_object.id = new_id
        terrain_object.object = object_copy
        terrain_object.node_tree = node_group

        # Build the geometry node tree.
        update_terrain_object_geometry_node_group(terrain_object)

        # Add a new modifier to the terrain info object.
        terrain_info_object = terrain_object.terrain_info_object
        modifier = terrain_info_object.modifiers.new(name=new_id, type='NODES')
        modifier.node_group = node_group

        # Deselect the active object.
        terrain_object_object.select_set(False)

        # Set the new object as the active object.
        context.view_layer.objects.active = object_copy

        return {'FINISHED'}


class BDK_OT_terrain_object_bake(Operator):
    bl_label = 'Bake Terrain Object'
    bl_idname = 'bdk.terrain_object_bake'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Bake the terrain object to the terrain'

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        active_object = context.active_object
        terrain_object = active_object.bdk.terrain_object
        terrain_info_object = terrain_object.terrain_info_object

        # Select the terrain info object and make it the active object.
        context.view_layer.objects.active = terrain_info_object
        terrain_info_object.select_set(True)

        # Find the modifier associated with the terrain object.
        did_find_modifier = False
        for modifier in terrain_info_object.modifiers:
            if modifier.name == terrain_object.id:
                did_find_modifier = True

        if not did_find_modifier:
            self.report({'ERROR'}, 'Could not find the associated modifier in the terrain info object.')
            return {'CANCELLED'}

        # Move the modifier to the top of the stack.
        bpy.ops.object.modifier_move_to_index(modifier=terrain_object.id, index=0)
        # Apply the modifier.
        bpy.ops.object.modifier_apply(modifier=terrain_object.id)

        # Delete the terrain object node group.
        bpy.data.node_groups.remove(terrain_object.node_tree)

        # Delete the terrain object.
        bpy.data.objects.remove(active_object)

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


class BDK_OT_terrain_object_paint_layer_duplicate(Operator):
    bl_label = 'Duplicate Paint Component'
    bl_idname = 'bdk.terrain_object_paint_layer_duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_object = terrain_info_object.bdk.terrain_object
        paint_layer_copy = terrain_object.paint_layers.add()

        copy_simple_property_group(terrain_object.paint_layers[terrain_object.paint_layers_index], paint_layer_copy)

        # Update all the indices of the components.
        update_terrain_object_indices(terrain_object)

        # Update the geometry node tree.
        update_terrain_object_geometry_node_group(terrain_object)

        return {'FINISHED'}


class BDK_OT_terrain_object_sculpt_layer_duplicate(Operator):
    bl_label = 'Duplicate Sculpt Component'
    bl_idname = 'bdk.terrain_object_sculpt_layer_duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_object = terrain_info_object.bdk.terrain_object
        sculpt_layer_copy = terrain_object.sculpt_layers.add()

        copy_simple_property_group(terrain_object.sculpt_layers[terrain_object.sculpt_layers_index], sculpt_layer_copy)

        # Update all the indices of the components.
        update_terrain_object_indices(terrain_object)

        # Update the geometry node tree.
        update_terrain_object_geometry_node_group(terrain_object)

        return {'FINISHED'}


class BDK_OT_terrain_object_delete(Operator):
    bl_idname = 'bdk.terrain_object_delete'
    bl_label = 'Delete Terrain Object'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_OBJECT'

    def execute(self, context: Context):
        terrain_object_object = context.active_object
        terrain_object = terrain_object_object.bdk.terrain_object

        # Delete the modifier from the terrain info object.
        terrain_info_object = terrain_object.terrain_info_object
        terrain_info_object.modifiers.remove(terrain_info_object.modifiers[terrain_object.id])

        # Delete the node group.
        bpy.data.node_groups.remove(terrain_object.node_tree)

        # Delete the terrain object.
        bpy.data.objects.remove(terrain_object_object)

        return {'FINISHED'}


class BDK_OT_convert_to_terrain_object(Operator):
    bl_idname = 'bdk.convert_to_terrain_object'
    bl_label = 'Convert to Terrain Object'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        # Check if object is already a terrain object
        if context.active_object.bdk.type == 'TERRAIN_OBJECT':
            cls.poll_message_set('Object is already a terrain object')
            return False
        # Check if object is a mesh, curve or empty.
        if context.active_object.type not in ('MESH', 'CURVE', 'EMPTY'):
            cls.poll_message_set('Active object must be a mesh, curve or empty.')
            return False
        return context.active_object and context.active_object.type in ('MESH', 'CURVE', 'EMPTY')

    def execute(self, context: Context):
        # TODO: convert to terrain object (refactor from terrain object add)
        return {'FINISHED'}


classes = (
    BDK_OT_convert_to_terrain_object,
    BDK_OT_terrain_object_add,
    BDK_OT_terrain_object_bake,
    BDK_OT_terrain_object_delete,
    BDK_OT_terrain_object_duplicate,
    BDK_OT_terrain_object_sculpt_layer_add,
    BDK_OT_terrain_object_sculpt_layer_remove,
    BDK_OT_terrain_object_sculpt_layer_move,
    BDK_OT_terrain_object_sculpt_layer_duplicate,
    BDK_OT_terrain_object_paint_layer_add,
    BDK_OT_terrain_object_paint_layer_remove,
    BDK_OT_terrain_object_paint_layer_duplicate
)
