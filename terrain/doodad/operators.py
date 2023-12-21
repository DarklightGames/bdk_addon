import uuid
from typing import cast

import bpy
import mathutils
from bpy.types import Operator, Context, Collection, Event, Object, Mesh
from bpy.props import EnumProperty, StringProperty, BoolProperty

from .kernel import add_terrain_doodad_sculpt_layer, add_terrain_doodad_paint_layer
from .properties import ensure_terrain_info_modifiers, BDK_PG_terrain_doodad_scatter_layer
from .scatter.builder import ensure_scatter_layer_modifiers, add_terrain_doodad_scatter_layer, \
    ensure_scatter_layer
from ..operators import merge_down_terrain_layer_node_data
from ..properties import BDK_PG_terrain_layer_node, get_terrain_info_paint_layer_by_id, \
    get_terrain_info_deco_layer_by_id, node_type_item_names
from ...helpers import is_active_object_terrain_info, copy_simple_property_group, get_terrain_doodad, \
    is_active_object_terrain_doodad, should_show_bdk_developer_extras, ensure_name_unique
from .builder import create_terrain_doodad_object, create_terrain_doodad_bake_node_tree, \
    convert_object_to_terrain_doodad, ensure_terrain_doodad_freeze_node_group


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
        terrain_doodad = create_terrain_doodad_object(context, terrain_info_object, self.object_type)

        """
        BUG: If the terrain info object has been added as rigid body, the collection will be the
        RigidBodyWorld collection, which isn't actually a collection that shows up in the outliner or the view layer,
        and makes the function fail.
        
        How can we get the *actual* collection that the terrain info object is in (the one that shows up in the outliner)?
        """

        # Link and parent the terrain doodad to the terrain info.
        collection: Collection = terrain_info_object.users_collection[0]

        collection.objects.link(terrain_doodad)

        # Deselect the terrain info object.
        terrain_info_object.select_set(False)

        # Select the terrain doodad.
        context.view_layer.objects.active = terrain_doodad
        terrain_doodad.select_set(True)

        # This needs to be called after the terrain doodad's parent is set.
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

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

        copy_simple_property_group(terrain_doodad_object.bdk.terrain_doodad, object_copy.bdk.terrain_doodad, ignore={'is_frozen'})

        terrain_doodad = object_copy.bdk.terrain_doodad
        terrain_doodad.id = new_id
        terrain_doodad.object = object_copy

        # Go through the layers and sub-objects and assign them new IDs.
        for sculpt_layer in terrain_doodad.sculpt_layers:
            sculpt_layer.id = uuid.uuid4().hex

        for scatter_layer in terrain_doodad.scatter_layers:
            scatter_layer.id = uuid.uuid4().hex
            scatter_layer.seed_object = None
            scatter_layer.sprout_object = None
            for scatter_layer_object in scatter_layer.objects:
                scatter_layer_object.id = uuid.uuid4().hex
            ensure_scatter_layer(scatter_layer)

        for paint_layer in terrain_doodad.paint_layers:
            paint_layer.id = uuid.uuid4().hex

        ensure_scatter_layer_modifiers(context, terrain_doodad)

        # Add a new modifier to the terrain info object.
        terrain_info_object = terrain_doodad.terrain_info_object
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        # Deselect the active object.
        terrain_doodad_object.select_set(False)

        # Set the new object as the active object.
        context.view_layer.objects.active = object_copy

        return {'FINISHED'}


def get_terrain_doodad_paint_layer_nodes(doodad_paint_layer: 'BDK_PG_terrain_doodad_paint_layer'):
    terrain_info = doodad_paint_layer.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info
    if doodad_paint_layer.layer_type == 'PAINT':
        # Get the terrain layer from the paint layer ID.
        terrain_info_paint_layer = get_terrain_info_paint_layer_by_id(terrain_info, doodad_paint_layer.paint_layer_id)
        return terrain_info_paint_layer.nodes if terrain_info_paint_layer is not None else None
    elif doodad_paint_layer.layer_type == 'DECO':
        # Get the terrain layer from the deco layer ID.
        terrain_info_deco_layer = get_terrain_info_deco_layer_by_id(terrain_info, doodad_paint_layer.deco_layer_id)
        return terrain_info_deco_layer.nodes if terrain_info_deco_layer is not None else None
    return None


class BDK_OT_terrain_doodad_freeze(Operator):
    bl_label = 'Freeze Terrain Doodad'
    bl_idname = 'bdk.terrain_doodad_freeze'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Freeze the terrain doodad by caching the current state of all layers instead of recalculating '\
                     'them when the terrain is modified.'

    @classmethod
    def poll(cls, context: Context):
        # TODO: maybe some things cannot be frozen, i.e., using a set operator on a sculpt layer.
        if not poll_has_terrain_doodad_selected(cls, context):
            return False
        terrain_doodad = get_terrain_doodad(context.active_object)
        if terrain_doodad.is_frozen:
            cls.poll_message_set('Terrain doodad is already frozen')
            return False
        return True

    def execute(self, context: Context):
        depsgraph = context.evaluated_depsgraph_get()

        terrain_doodad_object = context.active_object
        terrain_doodad = get_terrain_doodad(terrain_doodad_object)
        terrain_info_object = terrain_doodad.terrain_info_object

        # Add the freeze modifier to the top of the terrain info's modifier stack.
        modifier_id = uuid.uuid4().hex
        freeze_modifier = terrain_info_object.modifiers.new(modifier_id, 'NODES')
        freeze_modifier.node_group = ensure_terrain_doodad_freeze_node_group(terrain_doodad)

        # Move the freeze modifier to the top of the stack and apply it.
        terrain_info_object.modifiers.move(len(terrain_info_object.modifiers) - 1, 0)

        # Make the terrain info object the selected and active object.
        context.view_layer.objects.active = terrain_info_object
        terrain_info_object.select_set(True)

        # Apply the freeze modifier.
        bpy.ops.object.modifier_apply(modifier=modifier_id)

        terrain_doodad.is_frozen = True

        terrain_info_object.update_tag()
        terrain_doodad_object.update_tag()

        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        # Deselect the terrain info object.
        terrain_info_object.select_set(False)

        # Make the terrain doodad the active object again.
        context.view_layer.objects.active = terrain_doodad_object

        self.report({'INFO'}, f'Terrain doodad \'{terrain_doodad_object.name}\' frozen')  # TODO: give stats on how many layers were frozen

        return {'FINISHED'}


class BDK_OT_terrain_doodad_unfreeze(Operator):
    bl_label = 'Unfreeze Terrain Doodad'
    bl_idname = 'bdk.terrain_doodad_unfreeze'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Unfreeze the terrain doodad by recalculating all layers.'

    @classmethod
    def poll(cls, context: Context):
        if not poll_has_terrain_doodad_selected(cls, context):
            return False
        terrain_doodad = get_terrain_doodad(context.active_object)
        if not terrain_doodad.is_frozen:
            cls.poll_message_set('Terrain doodad is not frozen')
            return False
        return True

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        terrain_info_object = terrain_doodad.terrain_info_object
        mesh_data = cast(Mesh, terrain_info_object.data)
        attributes = mesh_data.attributes

        # Delete the frozen attributes.
        for sculpt_layer in terrain_doodad.sculpt_layers:
            if sculpt_layer.frozen_attribute_id not in attributes:
                self.report({'WARNING'}, f'Frozen attribute for sculpt layer \'{sculpt_layer.name}\' {sculpt_layer.frozen_attribute_id} not found')
                continue
            attributes.remove(attributes[sculpt_layer.frozen_attribute_id])
            sculpt_layer.is_frozen = False

        for paint_layer in terrain_doodad.paint_layers:
            if paint_layer.frozen_attribute_id not in attributes:
                self.report({'WARNING'}, f'Frozen attribute for paint layer \'{paint_layer.name}\' {paint_layer.frozen_attribute_id} not found')
                continue
            attributes.remove(attributes[paint_layer.frozen_attribute_id])
            paint_layer.is_frozen = False

        # TODO: unfreeze scatter layers.

        # Mark the doodad as not frozen.
        terrain_doodad.is_frozen = False

        terrain_info_object.update_tag()
        terrain_doodad.object.update_tag()

        # Update the terrain info modifiers.
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_bake(Operator):
    bl_label = 'Bake Terrain Doodad'
    bl_idname = 'bdk.terrain_doodad_bake'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Bake the terrain doodad to the terrain'

    should_delete_terrain_doodad: BoolProperty(
        name='Delete Terrain Doodad',
        description='Delete the terrain doodad after baking',
        default=True
    )
    # Create an enum flag property for the bake options.
    layers: EnumProperty(
        name='Bake Options',
        description='Bake options',
        items=(
            ('SCULPT', 'Sculpt', 'Sculpting layers will be baked to the terrain geometry'),
            ('PAINT', 'Paint', 'Paint layers will be baked to the associated paint layer nodes as new paint nodes'),
            ('SCATTER', 'Scatter', 'Scatter objects will be instances as new objects')
        ),
        default={'SCULPT', 'PAINT', 'SCATTER'},
        options={'ENUM_FLAG'}
    )
    should_merge_down_nodes: BoolProperty(
        name='Merge Down Nodes',
        description='Merge down paint and deco nodes after baking when possible.\n\nBaked paint layers will be added '
                    'to the top of the stack, and merged with the node below if it has the same operation',
        default=True
    )

    should_add_scatter_objects_to_collection: BoolProperty(
        name='Add Scatter Objects to Collection',
        description='Add the scatter objects to a collection with the name of the terrain doodad',
        default=True
    )

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_doodad(context):
            cls.poll_message_set('Active object must be a terrain doodad')
            return False
        return True

    def draw(self, context: 'Context'):
        layout = self.layout
        layout.prop(self, 'layers')
        layout.prop(self, 'should_delete_terrain_doodad')
        layout.prop(self, 'should_merge_down_nodes')
        layout.prop(self, 'should_add_scatter_objects_to_collection')

    def execute(self, context: Context):
        """
        We need to bake the sculpting layer directly to the terrain geometry.
        The paint and deco layers need to be written out as additive nodes for the affected layers.

        The order of operations for sculpt layers is irrelevant, but the order of operations for paint and
        deco layers is important, but it's probably not something that we should concern ourselves with.

        How I imagine the baking working is this:

        1. A new modifier is added to the terrain info object that emulates the sculpting and painting.
        2. Instead of writing to the attributes they are associated with, write it to new attributes, then apply the
            modifier.
        3. Add a new terrain paint nodes for each affected layer with the IDs we generated during the bake.

        When the user does the bake, they should be given the option to bake to a new paint node or to an exiting one.

        The user will want a way to combine or "flatten" the layers, so we'll need to add a new operator to do that.
        """

        depsgraph = context.evaluated_depsgraph_get()

        terrain_doodad_object = context.active_object
        terrain_doodad = get_terrain_doodad(terrain_doodad_object)
        terrain_info_object = terrain_doodad.terrain_info_object

        # Select the terrain info object and make it the active object.
        context.view_layer.objects.active = terrain_info_object
        terrain_info_object.select_set(True)

        # Bake the scatter layers first, otherwise the bake modifier will stack with the sculpt layers.
        if 'SCATTER' in self.layers:
            if self.should_add_scatter_objects_to_collection:
                # Add a new collection with the name of the terrain doodad.
                scatter_object_collection = bpy.data.collections.new(terrain_doodad_object.name)
                context.scene.collection.children.link(scatter_object_collection)
            else:
                scatter_object_collection = terrain_doodad_object.users_collection[0]

            for scatter_layer in terrain_doodad.scatter_layers:
                seed_object_eval = scatter_layer.seed_object.evaluated_get(depsgraph)

                # Create a new linked duplicate for each scatter layer object.
                mesh_data: Mesh = seed_object_eval.data
                for vertex_index, vertex in enumerate(mesh_data.vertices):
                    object_index = mesh_data.attributes['object_index'].data[vertex_index].value

                    location = vertex.co
                    rotation = mathutils.Euler(mesh_data.attributes['rotation'].data[vertex_index].vector)
                    scale = mesh_data.attributes['scale'].data[vertex_index].vector

                    new_object = bpy.data.objects.new('StaticMesh', scatter_layer.objects[object_index].object.data)
                    new_object.matrix_local = mathutils.Matrix.LocRotScale(location, rotation, scale)

                    # Link the new object to scatter object collection.
                    scatter_object_collection.objects.link(new_object)

        # Create a new modifier for the terrain doodad bake.
        bake_node_tree, paint_layer_attribute_map = create_terrain_doodad_bake_node_tree(terrain_doodad, self.layers)

        modifier = terrain_info_object.modifiers.new(terrain_doodad.id, 'NODES')
        modifier.node_group = bake_node_tree

        # Move the modifier to the top of the stack and apply it.
        # TODO: use the data API instead of the operator API
        bpy.ops.object.modifier_move_to_index(modifier=terrain_doodad.id, index=0)
        bpy.ops.object.modifier_apply(modifier=terrain_doodad.id)

        # Create new terrain paint nodes for each paint layer.
        if 'PAINT' in self.layers:
            for doodad_paint_layer in terrain_doodad.paint_layers:
                nodes = get_terrain_doodad_paint_layer_nodes(doodad_paint_layer)
                if nodes is None:
                    continue
                node: BDK_PG_terrain_layer_node = nodes.add()
                node.terrain_info_object = terrain_info_object
                # The node ID is synonymous with the attribute ID.
                # Set this new node's name to the attribute ID of the baked paint layer.
                node.id = paint_layer_attribute_map[doodad_paint_layer.id]
                node.type = 'PAINT'
                node.operation = doodad_paint_layer.operation
                node.name = terrain_doodad_object.name
                node.paint_layer_name = doodad_paint_layer.paint_layer_name

                # Move the new node to the top of the list.
                nodes.move(len(nodes) - 1, 0)

                if self.should_merge_down_nodes:
                    # If the node below us has the same operation, merge it down.
                    if len(nodes) > 1 and nodes[1].operation == node.operation and nodes[1].type == 'PAINT':  # TODO: make this a "can merge down" function
                        merge_down_terrain_layer_node_data(terrain_info_object, nodes, 0)

        # Delete the bake node tree.
        bpy.data.node_groups.remove(bake_node_tree)

        if self.should_delete_terrain_doodad:
            # Delete the terrain doodad object.
            delete_terrain_doodad(context, terrain_doodad_object)
        else:
            # Make the terrain doodad the active object again.
            context.view_layer.objects.active = terrain_doodad_object

        # Deselect the terrain info object.
        terrain_info_object.select_set(False)

        # Rebuild the terrain info modifiers so that the now-deleted doodad is removed.
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


def poll_has_terrain_doodad_selected(cls, context: Context) -> bool:
    terrain_doodad = get_terrain_doodad(context.active_object)
    if terrain_doodad is None:
        cls.poll_message_set('Must have a terrain doodad selected')
        return False
    return True


def poll_has_terrain_doodad_selected_paint_layer(cls, context: Context) -> bool:
    if not poll_has_terrain_doodad_selected(cls, context):
        return False
    terrain_doodad = get_terrain_doodad(context.active_object)
    if len(terrain_doodad.paint_layers) == 0 or terrain_doodad.paint_layers_index < 0:
        cls.poll_message_set('Must have a paint layer selected')
        return False
    return True


def poll_has_terrain_doodad_selected_scatter_layer(cls, context: Context) -> bool:
    if not poll_has_terrain_doodad_selected(cls, context):
        return False
    terrain_doodad = get_terrain_doodad(context.active_object)
    if len(terrain_doodad.scatter_layers) == 0 or terrain_doodad.scatter_layers_index < 0:
        cls.poll_message_set('Must have a sculpt layer selected')
        return False
    return True


def poll_has_terrain_doodad_selected_scatter_layer_object(cls, context: Context) -> bool:
    if not poll_has_terrain_doodad_selected_scatter_layer(cls, context):
        return False
    terrain_doodad = get_terrain_doodad(context.active_object)
    scatter_layer = terrain_doodad.scatter_layers[terrain_doodad.scatter_layers_index]
    if len(scatter_layer.objects) == 0 or scatter_layer.objects_index < 0:
        cls.poll_message_set('Must have a scatter layer object selected')
        return False
    return True


def delete_terrain_doodad(context: Context, terrain_doodad_object: Object):
    terrain_doodad = terrain_doodad_object.bdk.terrain_doodad

    # Delete the modifier from the terrain info object.
    terrain_info_object = terrain_doodad.terrain_info_object

    # Delete the scatter layers objects.
    for scatter_layer in terrain_doodad.scatter_layers:
        if scatter_layer.planter_object:
            bpy.data.objects.remove(scatter_layer.planter_object)
        if scatter_layer.seed_object:
            bpy.data.objects.remove(scatter_layer.seed_object)
        if scatter_layer.sprout_object:
            bpy.data.objects.remove(scatter_layer.sprout_object)

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
        return poll_has_terrain_doodad_selected(cls, context)

    def execute(self, context: Context):
        delete_terrain_doodad(context, context.active_object)
        return {'FINISHED'}


def get_selected_terrain_info_object(context: Context) -> Object:
    for selected_object in context.selected_objects:
        if selected_object.bdk.type == 'TERRAIN_INFO':
            return selected_object
    return None



class BDK_OT_convert_to_terrain_doodad(Operator):
    bl_idname = 'bdk.convert_to_terrain_doodad'
    bl_label = 'Convert to Terrain Doodad'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        terrain_doodad_object_types = {'MESH', 'CURVE', 'EMPTY'}

        # Check if object is already a terrain doodad.
        if is_active_object_terrain_doodad(context):
            cls.poll_message_set('Object is already a terrain doodad')
            return False

        # Check if object is a mesh, curve or empty.
        if context.active_object is None or context.active_object.type not in terrain_doodad_object_types:
            cls.poll_message_set('Active object must be a mesh, curve or empty')
            return False

        # Make sure that the only other selected object is a terrain info object.
        terrain_info_object = get_selected_terrain_info_object(context)

        if terrain_info_object is None:
            cls.poll_message_set('Must have a terrain info object selected')
            return False

        return True

    def execute(self, context: Context):
        # Get the selected terrain info object.
        terrain_info_object = get_selected_terrain_info_object(context)

        # Convert the object to a terrain doodad.
        convert_object_to_terrain_doodad(context.active_object, terrain_info_object)

        # Update the terrain info modifiers.
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_doodad_bake_debug(Operator):
    bl_label = 'Bake Debug'
    bl_idname = 'bdk.terrain_doodad_bake_debug'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_doodad(context) and should_show_bdk_developer_extras(context)

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)
        if terrain_doodad is None:
            return {'CANCELLED'}

        node_tree, attribute_map = create_terrain_doodad_bake_node_tree(terrain_doodad)

        # Add a muted modifier to the active object.
        modifier = terrain_doodad.terrain_info_object.modifiers.new(name='Bake', type='NODES')
        modifier.node_group = node_tree
        modifier.show_viewport = True

        return {'FINISHED'}


class BDK_OT_terrain_doodad_demote(Operator):
    bl_idname = 'bdk.terrain_doodad_demote'
    bl_label = 'Demote Terrain Doodad'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_doodad(context)

    def execute(self, context: Context):
        # Remove the terrain doodad from object.
        terrain_doodad_object = context.active_object
        terrain_doodad_object.bdk.type = 'NONE'

        ensure_terrain_info_modifiers(context, terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}

# TODO: this should be generic for all node trees.
def add_scatter_layer_mask_node(scatter_layer: 'BDK_PG_terrain_doodad_scatter_layer', node_type: str):
    node = scatter_layer.mask_nodes.add()
    node.terrain_info_object = scatter_layer.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object
    node.type = node_type
    node.id = uuid.uuid4().hex
    node.name = ensure_name_unique(node_type_item_names[node_type], [n.name for n in scatter_layer.mask_nodes])
    return node


class BDK_OT_terrain_doodad_save_preset(Operator):
    bl_idname = 'bdk.terrain_doodad_save_preset'
    bl_label = 'Save Terrain Doodad Preset'
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name='Name')

    def invoke(self, context: Context, event: Event):
        # Pre-populate the name field with the name of the active object.
        self.name = context.active_object.name
        return context.window_manager.invoke_props_dialog(self)

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected(cls, context)

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)

        # Save the settings to the scene.
        terrain_doodad_preset = context.scene.bdk.terrain_doodad_presets.add()
        terrain_doodad_preset.id = uuid.uuid4().hex
        terrain_doodad_preset.name = self.name
        copy_simple_property_group(terrain_doodad, terrain_doodad_preset.settings, ignore={'id', 'terrain_info_object'})

        return {'FINISHED'}

def terrain_doodad_load_preset_name_search_cb(self, context: Context, edit_text: str):
    return [x.name for x in context.scene.bdk.terrain_doodad_presets]


class BDK_OT_terrain_doodad_load_preset(Operator):
    bl_idname = 'bdk.terrain_doodad_load_preset'
    bl_label = 'Load Terrain Doodad Preset'
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(name='Name', search=terrain_doodad_load_preset_name_search_cb, search_options={'SORT'})

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    @classmethod
    def poll(cls, context: Context):
        return poll_has_terrain_doodad_selected(cls, context)

    def execute(self, context: Context):
        terrain_doodad = get_terrain_doodad(context.active_object)

        terrain_info_object = terrain_doodad.terrain_info_object

        # Find the preset with the given name.
        for terrain_doodad_preset in context.scene.bdk.terrain_doodad_presets:
            if terrain_doodad_preset.name == self.name:
                terrain_doodad.sculpt_layers.clear()
                for sculpt_layer in terrain_doodad_preset.settings.sculpt_layers:
                    new_sculpt_layer = add_terrain_doodad_sculpt_layer(terrain_doodad, sculpt_layer.name)
                    copy_simple_property_group(sculpt_layer, new_sculpt_layer, ignore={'id', 'terrain_doodad_object', 'index'})

                terrain_doodad.paint_layers.clear()
                for paint_layer in terrain_doodad_preset.settings.paint_layers:
                    new_paint_layer = add_terrain_doodad_paint_layer(terrain_doodad, paint_layer.name)
                    copy_simple_property_group(paint_layer, new_paint_layer, ignore={'id', 'terrain_doodad_object'})

                terrain_doodad.scatter_layers.clear()
                for scatter_layer in terrain_doodad_preset.settings.scatter_layers:
                    new_scatter_layer = add_terrain_doodad_scatter_layer(terrain_doodad, scatter_layer.name)
                    copy_simple_property_group(scatter_layer, new_scatter_layer, ignore={'id', 'objects', 'terrain_doodad_object'})
                break

        # Ensure the modifiers
        ensure_terrain_info_modifiers(context, terrain_info_object.bdk.terrain_info)

        return {'FINISHED'}


classes = (
    BDK_OT_convert_to_terrain_doodad,
    BDK_OT_terrain_doodad_add,
    BDK_OT_terrain_doodad_freeze,
    BDK_OT_terrain_doodad_unfreeze,
    BDK_OT_terrain_doodad_bake,
    BDK_OT_terrain_doodad_bake_debug,
    BDK_OT_terrain_doodad_delete,
    BDK_OT_terrain_doodad_duplicate,
    BDK_OT_terrain_doodad_demote,
    BDK_OT_terrain_doodad_save_preset,
    BDK_OT_terrain_doodad_load_preset,
)
