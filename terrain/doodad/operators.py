import uuid

import bpy
from bpy.types import Operator, Context, Collection, Event, Object
from bpy.props import EnumProperty

from .properties import ensure_terrain_info_modifiers
from ...helpers import is_active_object_terrain_info, copy_simple_property_group
from .builder import create_terrain_doodad


class BDK_OT_terrain_doodad_add(Operator):
    bl_label = 'Add Terrain Doodad'
    bl_idname = 'bdk.terrain_doodad_add'
    bl_description = 'Add a terrain doodad to the scene'

    object_type: EnumProperty(
        name='Type',
        items=(
            ('CURVE', 'Curve', 'A terrain doodad that uses a curve to define the shape', 'CURVE_DATA', 0),
            ('MESH', 'Mesh', 'A terrain doodad that uses a mesh to define the shape', 'MESH_DATA', 1),
            ('EMPTY', 'Empty', 'A terrain doodad that uses an empty to define the shape', 'EMPTY_DATA', 2),
        )
    )

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            cls.poll_message_set('The active object must be a terrain info object')
            return False
        return True

    def execute(self, context: Context):
        # TODO: have a way to select the terrain info object definition.
        terrain_info_object = context.active_object
        terrain_doodad = create_terrain_doodad(context, terrain_info_object, self.object_type)

        """
        BUG: If the terrain info object has been added as rigid body, the collection will be the
        RigidBodyWorld collection, which isn't actually a collection that shows up in the outliner or the view layer,
        and makes the function fail.
        
        How can we get the *actual* collection that the terrain info object is in (the one that shows up in the outliner)?
        """

        # Link and parent the terrain doodad to the terrain info.
        collection: Collection = terrain_info_object.users_collection[0]

        collection.objects.link(terrain_doodad)
        terrain_doodad.parent = terrain_info_object

        # Deselect the terrain info object.
        terrain_info_object.select_set(False)

        # Select the terrain doodad.
        context.view_layer.objects.active = terrain_doodad
        terrain_doodad.select_set(True)

        # This needs to be called after the terrain doodad's parent is set.
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


def ensure_terrain_doodad_layer_indices(terrain_doodad):
    # Sculpt Components
    for i, sculpt_layer in enumerate(terrain_doodad.sculpt_layers):
        sculpt_layer.index = i
    # Paint Components
    for i, paint_layer in enumerate(terrain_doodad.paint_layers):
        paint_layer.index = i


class BDK_OT_terrain_doodad_sculpt_layer_add(Operator):
    bl_label = 'Add Sculpt Component'
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad

        # Add a new sculpting layer.
        sculpt_layer = terrain_doodad.sculpt_layers.add()
        sculpt_layer.id = uuid.uuid4().hex
        sculpt_layer.terrain_doodad = terrain_doodad.object

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Set the sculpting component index to the new sculpting component.
        terrain_doodad.sculpt_layers_index = len(terrain_doodad.sculpt_layers) - 1

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_sculpt_layer_remove(Operator):
    bl_label = 'Remove Sculpt Component'
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

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

        return {'FINISHED'}


# Add an operator that moves the sculpting component up and down in the list.
class BDK_OT_terrain_doodad_sculpt_layer_move(Operator):
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_move'
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
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        sculpt_layers_index = terrain_doodad.sculpt_layers_index
        if self.direction == 'UP':
            terrain_doodad.sculpt_layers.move(sculpt_layers_index, sculpt_layers_index - 1)
            terrain_doodad.sculpt_layers_index -= 1
        elif self.direction == 'DOWN':
            terrain_doodad.sculpt_layers.move(sculpt_layers_index, sculpt_layers_index + 1)
            terrain_doodad.sculpt_layers_index += 1

        ensure_terrain_doodad_layer_indices(terrain_doodad)
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


# TODO: Make this a macro operator that duplicates and then moves mode (same behavior as native duplicate).

class BDK_OT_terrain_doodad_duplicate(Operator):
    bl_idname = 'bdk.terrain_doodad_duplicate'
    bl_label = 'Duplicate Terrain Doodad'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Duplicate the terrain doodad'

    @classmethod
    def poll(cls, context: Context):
        return context.active_object is not None and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        new_id = uuid.uuid4().hex
        terrain_doodad_object = context.active_object
        object_copy = terrain_doodad_object.copy()
        object_copy.name = new_id
        if terrain_doodad_object.data:
            data_copy = terrain_doodad_object.data.copy()
            data_copy.name = new_id
            object_copy.data = data_copy
        collection = terrain_doodad_object.users_collection[0]  # TODO: issue with RigidBody collection
        collection.objects.link(object_copy)

        copy_simple_property_group(terrain_doodad_object.bdk.terrain_doodad, object_copy.bdk.terrain_doodad)

        terrain_doodad = object_copy.bdk.terrain_doodad
        terrain_doodad.id = new_id
        terrain_doodad.object = object_copy

        # Add a new modifier to the terrain info object.
        terrain_info_object = terrain_doodad.terrain_info_object
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        # Deselect the active object.
        terrain_doodad_object.select_set(False)

        # Set the new object as the active object.
        context.view_layer.objects.active = object_copy

        return {'FINISHED'}


class BDK_OT_terrain_doodad_bake(Operator):
    bl_label = 'Bake Terrain Doodad'
    bl_idname = 'bdk.terrain_doodad_bake'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Bake the terrain doodad to the terrain'

    @classmethod
    def create_bake_node_tree(cls, context: Context, terrain_doodad: 'BDK_PG_terrain_doodad'):
        pass

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    @classmethod
    def poll(cls, context: Context):
        cls.poll_message_set('Not yet implemented')
        return False
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        """
        This whole thing will need to be reworked.

        We need to bake the sculpting layer directly to the terrain geometry.
        The paint and deco layers need to be written out as additive nodes for the affected layers.
        If the paint layers simply just *were* nodes, that may make things considerably easier conceptually, but
        would complicate the UI.

        The order of operations for sculpt layers is irrelevant, but the order of operations for paint and
        deco layers is important, but it's probably not something that we should concern ourselves with.

        How I imagine the baking working is this:

        1. A new modifier is added to the terrain info object that emulates the sculpting and painting.
        2. Instead of writing to the attributes they are associated with, write it to new attributes, then apply the
            modifier.
        3. Add a new terrain paint nodes for each affected layer with the IDs we generated during the bake.

        When the user does the bake, they should be given the option to bake to a new paint node or to an exiting one.

        Alternatively, we could make sure there is always an implicit paint node for each layer, and then just update
        the values of the paint node.

        The user will want a way to combine or "flatten" the layers, so we'll need to add a new operator to do that.
        """

        active_object = context.active_object
        terrain_doodad = active_object.bdk.terrain_doodad
        terrain_info_object = terrain_doodad.terrain_info_object

        # Select the terrain info object and make it the active object.
        context.view_layer.objects.active = terrain_info_object
        terrain_info_object.select_set(True)

        # TODO: create a new baking node tree for the terrain doodad.

        # Move the modifier to the top of the stack.
        bpy.ops.object.modifier_move_to_index(modifier=terrain_doodad.id, index=0)
        # Apply the modifier.
        bpy.ops.object.modifier_apply(modifier=terrain_doodad.id)

        # Delete the terrain doodad node group.
        bpy.data.node_groups.remove(terrain_doodad.node_tree)

        # Delete the terrain doodad.
        bpy.data.objects.remove(active_object)

        # Deselect the terrain info object.
        terrain_info_object.select_set(False)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_paint_layer_add(Operator):
    bl_label = 'Add Paint Component'
    bl_idname = 'bdk.terrain_doodad_paint_layer_add'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        paint_layer = terrain_doodad.paint_layers.add()
        paint_layer.id = uuid.uuid4().hex
        paint_layer.terrain_doodad = terrain_doodad.object

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        # Set the paint component index to the new paint component.
        terrain_doodad.paint_layers_index = len(terrain_doodad.paint_layers) - 1

        return {'FINISHED'}


class BDK_OT_terrain_doodad_paint_layer_remove(Operator):
    bl_label = 'Remove Paint Component'
    bl_idname = 'bdk.terrain_doodad_paint_layer_remove'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

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


class BDK_OT_terrain_doodad_paint_layer_duplicate(Operator):
    bl_label = 'Duplicate Paint Component'
    bl_idname = 'bdk.terrain_doodad_paint_layer_duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        # TODO: wrap this into a function.
        terrain_doodad_object = context.active_object
        terrain_doodad = terrain_doodad_object.bdk.terrain_doodad
        paint_layer_copy = terrain_doodad.paint_layers.add()

        copy_simple_property_group(terrain_doodad.paint_layers[terrain_doodad.paint_layers_index], paint_layer_copy)

        paint_layer_copy.id = uuid.uuid4().hex

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_sculpt_layer_duplicate(Operator):
    bl_label = 'Duplicate Sculpt Component'
    bl_idname = 'bdk.terrain_doodad_sculpt_layer_duplicate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_doodad = terrain_info_object.bdk.terrain_doodad
        sculpt_layer_copy = terrain_doodad.sculpt_layers.add()

        copy_simple_property_group(terrain_doodad.sculpt_layers[terrain_doodad.sculpt_layers_index], sculpt_layer_copy)

        # Make sure the copy has a unique id.
        sculpt_layer_copy.id = uuid.uuid4().hex

        # Update all the indices of the components.
        ensure_terrain_doodad_layer_indices(terrain_doodad)

        # Update the geometry node tree.
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


def delete_terrain_doodad(context: Context, terrain_doodad_object: Object):
    terrain_doodad = terrain_doodad_object.bdk.terrain_doodad

    # Delete the modifier from the terrain info object.
    terrain_info_object = terrain_doodad.terrain_info_object

    # Delete the terrain doodad.
    bpy.data.objects.remove(terrain_doodad_object)

    # Rebuild the terrain doodad modifiers.
    ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)


class BDK_OT_terrain_doodad_delete(Operator):
    bl_idname = 'bdk.terrain_doodad_delete'
    bl_label = 'Delete Terrain Doodad'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return context.active_object and context.active_object.bdk.type == 'TERRAIN_DOODAD'

    def execute(self, context: Context):
        delete_terrain_doodad(context, context.active_object)
        return {'FINISHED'}


class BDK_OT_convert_to_terrain_doodad(Operator):
    bl_idname = 'bdk.convert_to_terrain_doodad'
    bl_label = 'Convert to Terrain Doodad'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        # Check if object is already a terrain doodad.
        if context.active_object.bdk.type == 'TERRAIN_DOODAD':
            cls.poll_message_set('Object is already a terrain doodad')
            return False
        # Check if object is a mesh, curve or empty.
        if context.active_object.type not in ('MESH', 'CURVE', 'EMPTY'):
            cls.poll_message_set('Active object must be a mesh, curve or empty.')
            return False
        return context.active_object and context.active_object.type in ('MESH', 'CURVE', 'EMPTY')

    def execute(self, context: Context):
        # TODO: convert to terrain doodad (refactor from terrain doodad add)
        return {'FINISHED'}


classes = (
    BDK_OT_convert_to_terrain_doodad,
    BDK_OT_terrain_doodad_add,
    BDK_OT_terrain_doodad_bake,
    BDK_OT_terrain_doodad_delete,
    BDK_OT_terrain_doodad_duplicate,
    BDK_OT_terrain_doodad_sculpt_layer_add,
    BDK_OT_terrain_doodad_sculpt_layer_remove,
    BDK_OT_terrain_doodad_sculpt_layer_move,
    BDK_OT_terrain_doodad_sculpt_layer_duplicate,
    BDK_OT_terrain_doodad_paint_layer_add,
    BDK_OT_terrain_doodad_paint_layer_remove,
    BDK_OT_terrain_doodad_paint_layer_duplicate
)
