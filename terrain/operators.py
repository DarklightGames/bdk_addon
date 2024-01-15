import os
import uuid
from collections import deque

from typing import cast

import bpy
import mathutils
import numpy
from bpy.props import IntProperty, FloatProperty, FloatVectorProperty, BoolProperty, StringProperty, EnumProperty
from bpy.types import Operator, Context, Mesh, Object, Event
from bpy_extras.io_utils import ExportHelper

from ..g16.g16 import read_bmp_g16
from ..data import move_direction_items
from .context import get_selected_terrain_paint_layer_node
from .layers import add_terrain_deco_layer
from .kernel import ensure_deco_layers, ensure_terrain_layer_node_group, ensure_paint_layers, \
    create_terrain_paint_layer_node_convert_to_paint_layer_node_tree
from .exporter import export_terrain_heightmap, export_terrain_paint_layers, export_terrain_deco_layers, write_terrain_t3d
from .layers import add_terrain_paint_layer
from .doodad.builder import ensure_terrain_info_modifiers

from ..helpers import get_terrain_info, is_active_object_terrain_info, fill_byte_color_attribute_data, \
    invert_byte_color_attribute_data, accumulate_byte_color_attribute_data, copy_simple_property_group, \
    ensure_name_unique, padded_roll, sanitize_name_for_unreal
from .builder import build_terrain_material, create_terrain_info_object, get_terrain_quad_size, \
    get_terrain_info_vertex_xy_coordinates
from .properties import node_type_items, node_type_item_names, BDK_PG_terrain_info, BDK_PG_terrain_paint_layer, \
    BDK_PG_terrain_layer_node, BDK_PG_terrain_deco_layer, get_terrain_info_paint_layer_by_id


class BDK_OT_terrain_paint_layer_remove(Operator):
    bl_idname = 'bdk.terrain_paint_layer_remove'
    bl_label = 'Remove Terrain Paint Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            return False
        return get_terrain_info(context.active_object).paint_layers_index >= 0

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_info = get_terrain_info(terrain_info_object)
        paint_layers = terrain_info.paint_layers
        paint_layers_index = terrain_info.paint_layers_index

        if paint_layers_index < 0:
            return {'CANCELLED'}

        # Remove color attribute.
        mesh_data = cast(Mesh, terrain_info_object.data)
        paint_layer_id = paint_layers[paint_layers_index].id
        if paint_layer_id in mesh_data.color_attributes:
            color_attribute = mesh_data.color_attributes[paint_layer_id]
            mesh_data.color_attributes.remove(color_attribute)

        paint_layers.remove(paint_layers_index)

        terrain_info.paint_layers_index = min(len(paint_layers) - 1, paint_layers_index)

        # Delete the associated modifier and node group.
        if paint_layer_id in terrain_info_object.modifiers:
            paint_layer_modifier = terrain_info_object.modifiers[paint_layer_id]
            terrain_info_object.modifiers.remove(paint_layer_modifier)

        if paint_layer_id in bpy.data.node_groups:
            bpy.data.node_groups.remove(bpy.data.node_groups[paint_layer_id])

        build_terrain_material(terrain_info_object)

        ensure_paint_layers(terrain_info_object)

        return {'FINISHED'}


class BDK_OT_terrain_paint_layer_move(Operator):
    bl_idname = 'bdk.terrain_paint_layer_move'
    bl_label = 'Move Terrain Paint Layer'
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name='Direction',
        options=set(),
        items=(
            ('UP', 'Up', 'The selected terrain layer will be moved up'),
            ('DOWN', 'Down', 'The selected terrain layer will be moved down')
        ),
    )

    @classmethod
    def poll(cls, context: 'Context'):
        return is_active_object_terrain_info(context)

    def execute(self, context: Context):
        active_object = context.active_object
        terrain_info = get_terrain_info(context.active_object)
        paint_layers = terrain_info.paint_layers
        paint_layers_index = terrain_info.paint_layers_index

        if self.direction == 'UP' and paint_layers_index > 0:
            paint_layers.move(paint_layers_index, paint_layers_index - 1)
            terrain_info.paint_layers_index -= 1
            build_terrain_material(active_object)
        elif self.direction == 'DOWN' and paint_layers_index < len(paint_layers) - 1:
            paint_layers.move(paint_layers_index, paint_layers_index + 1)
            terrain_info.paint_layers_index += 1
            build_terrain_material(active_object)

        # The order of the paint layers changed. Therefore, we need to:
        # 1. Rebuild the paint layer node groups.
        # 2. Ensure the sorting of the paint layer modifiers.
        # TODO: For now, we just rebuild the whole thing, but this should be optimized later.
        ensure_terrain_info_modifiers(context, terrain_info)

        return {'FINISHED'}


class BDK_OT_terrain_deco_layer_add(Operator):
    bl_idname = 'bdk.terrain_deco_layer_add'
    bl_label = 'Add Deco Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def execute(self, context: bpy.types.Context):
        add_terrain_deco_layer(context.active_object)
        ensure_terrain_info_modifiers(context, get_terrain_info(context.active_object))
        return {'FINISHED'}


class BDK_OT_terrain_deco_layer_remove(Operator):
    bl_idname = 'bdk.terrain_deco_layer_remove'
    bl_label = 'Remove Deco Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            return False

        terrain_info = get_terrain_info(context.active_object)

        if len(terrain_info.deco_layers) == 0 or terrain_info.deco_layers_index == -1:
            return False

        return True

    def execute(self, context: bpy.types.Context):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index

        deco_layer = deco_layers[deco_layers_index]
        deco_layer_object = cast(Object, deco_layers[deco_layers_index].object)

        # Remove the deco layer modifier from the terrain info object.
        if deco_layer.id in context.active_object.modifiers:
            context.active_object.modifiers.remove(context.active_object.modifiers[deco_layer.id])

        if deco_layer_object is not None:
            # Unlink the deco layer object from any collections it belongs to.
            for collection in deco_layer_object.users_collection:
                collection.objects.unlink(deco_layer_object)

            # Remove the density map color attribute.
            mesh_data = cast(Mesh, context.active_object.data)
            if mesh_data is not None:
                attribute = mesh_data.color_attributes.get(deco_layer.id, None)
                if attribute is not None:
                    mesh_data.attributes.remove(attribute)

            # Remove the deco layer object data block.
            bpy.data.objects.remove(deco_layer_object)

        # Remove the deco layer entry.
        deco_layers.remove(deco_layers_index)

        # Set the new deco layer index to occupy the same index.
        terrain_info.deco_layers_index = min(len(terrain_info.deco_layers) - 1, deco_layers_index)

        # Build all deco layers. This is necessary because the drivers in the geometry node modifiers
        # reference the deco_layers array by index, and removing an entry can mess up other node setups.
        ensure_deco_layers(context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_paint_layer_add(Operator):
    bl_idname = 'bdk.terrain_paint_layer_add'
    bl_label = 'Add Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    alpha_fill: FloatVectorProperty(name='Alpha Fill', subtype='COLOR', min=0.0, max=1.0, size=4,
                                    default=(0.0, 0.0, 0.0, 1.0))
    u_scale: FloatProperty(name='UScale', default=1.0)
    v_scale: FloatProperty(name='VScale', default=1.0)

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            return False
        terrain_info = get_terrain_info(context.active_object)
        if len(terrain_info.paint_layers) >= 32:
            cls.poll_message_set('Cannot have more than 32 terrain layers')
            return False
        return True

    def execute(self, context: bpy.types.Context):
        active_object = context.active_object
        add_terrain_paint_layer(active_object, name='TerrainLayer')
        ensure_paint_layers(active_object)
        return {'FINISHED'}


def quad_size_get(self):
    return get_terrain_quad_size(self.size, self.resolution)


class BDK_OT_terrain_info_add(Operator):
    bl_idname = 'bdk.terrain_info_add'
    bl_label = 'Add Terrain Info'
    bl_options = {'REGISTER', 'UNDO'}

    resolution: IntProperty(name='Resolution', default=512, min=2, max=512, description='The number of quads')
    size: FloatProperty(name='Size', default=500 * 60.352, subtype='DISTANCE',
                        description='The length and width of the terrain')
    quad_size: FloatProperty(name='Quad Size', get=quad_size_get, set=None, subtype='DISTANCE')
    location: FloatVectorProperty(name='Location', unit='LENGTH')
    lock_transforms: BoolProperty(name='Lock Transforms', default=True)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return True

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        terrain_info_object = create_terrain_info_object(name='TerrainInfo', resolution=self.resolution, size=self.size)
        terrain_info_object.location = self.location

        if self.lock_transforms:
            # Lock transforms so that levelers don't accidentally move the terrain.
            terrain_info_object.lock_location = [True] * 3
            terrain_info_object.lock_scale = [True] * 3
            terrain_info_object.lock_rotation = [True] * 3
            terrain_info_object.lock_rotation_w = True
            terrain_info_object.lock_rotations_4d = True

        # Add a constant base layer to start with.
        paint_layer = add_terrain_paint_layer(terrain_info_object, name='Base')
        add_terrain_layer_node(terrain_info_object, paint_layer.nodes, type='CONSTANT')
        ensure_paint_layers(terrain_info_object)

        context.scene.collection.objects.link(terrain_info_object)

        # Select the new object.
        context.view_layer.objects.active = terrain_info_object
        terrain_info_object.select_set(True)

        return {'FINISHED'}


class BDK_OT_terrain_info_export(Operator, ExportHelper):
    bl_label = 'Export BDK Terrain Info'
    bl_idname = 'bdk.terrain_info_export'

    directory: StringProperty(name='Directory')
    filename_ext: StringProperty(default='.', options={'HIDDEN'})
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            cls.poll_message_set('The active object must be a TerrainInfo object')
            return False
        return True

    def invoke(self, context: Context, event: Event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)

        current_progress = 0
        progress_max = 2 + len(terrain_info.paint_layers) + len(terrain_info.deco_layers)

        wm = context.window_manager
        wm.progress_begin(0, progress_max)

        file_name = f'{sanitize_name_for_unreal(context.active_object.name)}.t3d'
        t3d_path = os.path.join(self.directory, file_name)

        def progress_increment():
            nonlocal current_progress
            current_progress += 1
            wm.progress_update(current_progress)

        # Get the depsgraph.
        depsgraph = context.evaluated_depsgraph_get()

        with open(t3d_path, 'w') as fp:
            write_terrain_t3d(context.active_object, depsgraph, fp)
            progress_increment()

        # Export the heightmap and paint layers.
        export_terrain_heightmap(context.active_object, depsgraph, directory=self.directory)
        progress_increment()

        def progress_cb(current: int, max: int):
            progress_increment()

        export_terrain_paint_layers(context.active_object, depsgraph, directory=self.directory, progress_cb=progress_cb)
        export_terrain_deco_layers(context.active_object, depsgraph, directory=self.directory, progress_cb=progress_cb)

        wm.progress_end()

        self.report({'INFO'}, 'Exported TerrainInfo')

        return {'FINISHED'}


class BDK_OT_terrain_deco_layers_hide(Operator):
    bl_idname = 'bdk.terrain_deco_layers_hide'
    bl_label = 'Hide Deco Layers'

    mode: EnumProperty(name='Operation', items=(
        ('ALL', 'All', 'Hide all deco layers'),
        ('UNSELECTED', 'Unselected', 'Hide all deco layers except the selected one')
    ), default='ALL')

    @classmethod
    def poll(cls, context: Context):
        return True

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index

        for (deco_layer_index, deco_layer) in enumerate(deco_layers):
            if self.mode == 'UNSELECTED' and deco_layer_index == deco_layers_index:
                continue
            deco_layer.object.hide_viewport = True

        return {'FINISHED'}


class BDK_OT_terrain_deco_layers_show(Operator):
    bl_idname = 'bdk.terrain_deco_layers_show'
    bl_label = 'Show Deco Layers'

    mode: EnumProperty(name='Operation', items=(
        ('ALL', 'All', 'Hide all deco layers'),
        ('UNSELECTED', 'Unselected', 'Hide all deco layers except the selected one')
    ), default='ALL')

    @classmethod
    def poll(cls, context: Context):
        return True

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index

        for (deco_layer_index, deco_layer) in enumerate(deco_layers):
            if self.mode == 'UNSELECTED' and deco_layer_index == deco_layers_index:
                continue
            deco_layer.object.hide_viewport = False

        return {'FINISHED'}


class BDK_OT_terrain_paint_layers_show(Operator):
    bl_idname = 'bdk.terrain_paint_layers_show'
    bl_label = 'Show Layers'

    mode: EnumProperty(name='Operation', items=(
        ('ALL', 'All', 'Show all layers'),
        ('UNSELECTED', 'Unselected', 'Show all layers except the selected one')
    ), default='ALL')

    @classmethod
    def poll(cls, context: Context):
        return True

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        layers = terrain_info.paint_layers
        layers_index = terrain_info.paint_layers_index

        for (layer_index, layer) in enumerate(layers):
            if self.mode == 'UNSELECTED' and layer_index == layers_index:
                continue
            layer.is_visible = True

        # Tag the object to be updated and redraw all regions.
        context.active_object.update_tag()
        for region in context.area.regions:
            region.tag_redraw()

        return {'FINISHED'}


class BDK_OT_terrain_paint_layers_hide(Operator):
    bl_idname = 'bdk.terrain_paint_layers_hide'
    bl_label = 'Hide Layers'

    mode: EnumProperty(name='Operation', items=(
        ('ALL', 'All', 'Hide all layers'),
        ('UNSELECTED', 'Unselected', 'Hide all layers except the selected one')
    ), default='ALL')

    @classmethod
    def poll(cls, context: Context):
        return True

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        layers = terrain_info.paint_layers
        layers_index = terrain_info.paint_layers_index

        for (layer_index, layer) in enumerate(layers):
            if self.mode == 'UNSELECTED' and layer_index == layers_index:
                continue
            layer.is_visible = False

        # Tag the object to be updated and redraw all regions.
        context.active_object.update_tag()
        for region in context.area.regions:
            region.tag_redraw()

        return {'FINISHED'}


def move_node_between_node_lists(source_nodes, source_nodes_index: int, target_nodes):
    new_node = target_nodes.add()
    copy_simple_property_group(source_nodes[source_nodes_index], new_node)
    source_nodes.remove(source_nodes_index)


def add_terrain_layer_node(terrain_info_object: Object, nodes, type: str):
    node_name = ensure_name_unique(node_type_item_names[type], [n.name for n in nodes])
    node = nodes.add()
    node.id = uuid.uuid4().hex
    node.name = node_name
    node.terrain_info_object = terrain_info_object
    node.type = type

    if type == 'PAINT':
        mesh_data = cast(Mesh, terrain_info_object.data)
        # TODO: when we can paint non-color data, rewrite this!
        # Add the density map attribute to the TerrainInfo mesh.
        attribute = mesh_data.attributes.new(node.id, 'BYTE_COLOR', domain='POINT')
        vertex_count = len(attribute.data)
        color_data = numpy.ndarray(shape=(vertex_count, 4), dtype=float)
        color_data[:] = (0.0, 0.0, 0.0, 0.0)
        attribute.data.foreach_set('color', color_data.flatten())
    elif type == 'FIELD':
        mesh_data = cast(Mesh, terrain_info_object.data)
        mesh_data.attributes.new(node.id, 'FLOAT', domain='POINT')

    # Move the node to the top of the list.
    nodes.move(len(nodes) - 1, 0)

    return node


def remove_terrain_layer_node(terrain_info_object: Object, nodes, nodes_index: int):
    node = nodes[nodes_index]

    if node.type == 'PAINT':
        mesh_data = cast(Mesh, terrain_info_object.data)
        if node.id in mesh_data.attributes:
            attribute = mesh_data.attributes[node.id]
            mesh_data.attributes.remove(attribute)

    nodes.remove(nodes_index)


def move_terrain_layer_node(direction: str, nodes, nodes_index: int) -> int:
    if direction == 'UP':
        if nodes_index > 0:
            nodes.move(nodes_index, nodes_index - 1)
            nodes_index -= 1
    elif direction == 'DOWN':
        if nodes_index < len(nodes) - 1:
            nodes.move(nodes_index, nodes_index + 1)
            nodes_index += 1
    return nodes_index


def poll_is_active_object_terrain_info(cls, context):
    if not is_active_object_terrain_info(context):
        cls.poll_message_set('The active object is not a terrain info object')
        return False
    # TODO: should also have a selected layer.
    return True



class BDK_OT_terrain_deco_layer_nodes_add(Operator):
    bl_idname = 'bdk.terrain_deco_layer_nodes_add'
    bl_label = 'Add Deco Layer Node'
    bl_description = 'Add a node to the selected deco layer'
    bl_options = {'REGISTER', 'UNDO'}

    type: EnumProperty(name='Type', items=node_type_items)

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_info(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer = deco_layers[deco_layers_index]

        add_terrain_layer_node(context.active_object, deco_layer.nodes, self.type)

        # TODO: for some reason, the factor driver is invalid when added [is this still true?]
        ensure_deco_layers(context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_deco_layer_nodes_remove(Operator):
    bl_idname = 'bdk.terrain_deco_layer_nodes_remove'
    bl_label = 'Remove Deco Layer Node'
    bl_description = 'Remove the selected layer node from the selected deco layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_info(cls, context)

    def execute(self, context: Context):
        terrain_info: 'BDK_PG_terrain_info' = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer: 'BDK_PG_terrain_deco_layer' = deco_layers[deco_layers_index]

        remove_terrain_layer_node(context.active_object, deco_layer.nodes, deco_layer.nodes_index)

        ensure_deco_layers(context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_deco_layer_nodes_move(Operator):
    bl_idname = 'bdk.terrain_deco_layer_nodes_move'
    bl_label = 'Move Deco Layer Node'
    bl_description = 'Move the selected layer node'
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(name='Direction', items=move_direction_items, default='UP')

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_info(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer = deco_layers[deco_layers_index]

        deco_layer.nodes_index = move_terrain_layer_node(self.direction, deco_layer.nodes, deco_layer.nodes_index)

        ensure_deco_layers(context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_paint_layer_nodes_add(Operator):
    bl_idname = 'bdk.terrain_paint_layer_nodes_add'
    bl_label = 'Add Paint Layer Node'
    bl_description = 'Add a node to the selected paint layer'
    bl_options = {'REGISTER', 'UNDO'}

    type: EnumProperty(name='Type', items=node_type_items)

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_info(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        paint_layers = terrain_info.paint_layers
        paint_layers_index = terrain_info.paint_layers_index
        paint_layer = paint_layers[paint_layers_index]

        add_terrain_layer_node(context.active_object, paint_layer.nodes, self.type)
        ensure_terrain_layer_node_group(paint_layer.id, 'paint_layers', paint_layers_index, paint_layer.id, paint_layer.nodes, context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_paint_layer_nodes_remove(Operator):
    bl_idname = 'bdk.terrain_paint_layer_nodes_remove'
    bl_label = 'Remove Paint Layer Node'
    bl_description = 'Remove the selected layer node from the selected paint layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_info(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        paint_layers = terrain_info.paint_layers
        paint_layers_index = terrain_info.paint_layers_index
        paint_layer = paint_layers[paint_layers_index]

        remove_terrain_layer_node(context.active_object, paint_layer.nodes, paint_layer.nodes_index)

        ensure_terrain_layer_node_group(paint_layer.id, 'paint_layers', paint_layers_index, paint_layer.id, paint_layer.nodes, context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_paint_layer_nodes_move(Operator):
    bl_idname = 'bdk.terrain_paint_layer_nodes_move'
    bl_label = 'Move Deco Layer Node'
    bl_description = 'Move the selected layer node'
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(name='Direction', items=move_direction_items, default='UP')

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_info(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        paint_layers = terrain_info.paint_layers
        paint_layers_index = terrain_info.paint_layers_index
        paint_layer = paint_layers[paint_layers_index]
        paint_layer.nodes_index = move_terrain_layer_node(self.direction, paint_layer.nodes, paint_layer.nodes_index)

        ensure_terrain_layer_node_group(paint_layer.id, 'paint_layers', paint_layers_index, paint_layer.id, paint_layer.nodes, context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_info_repair(Operator):
    """
    Repairs the terrain info mesh by ensuring that the X & Y coordinates of each vertex are correct.
    This is needed because it is possible to manually edit the mesh and cause the coordinates to be misaligned.
    In the future, we should also make sure that the rest of the topology is correct (e.g. the faces are all quads).
    """
    bl_idname = 'bdk.terrain_info_repair'
    bl_label = 'Repair Terrain Info'
    bl_description = 'Repair the terrain info by ensuring that the X & Y coordinates of each vertex are correct'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        vertex_coordinates = get_terrain_info_vertex_xy_coordinates(resolution=terrain_info.x_size, terrain_scale=terrain_info.terrain_scale)
        mesh_data = cast(Mesh, context.active_object.data)
        vertex_repair_count = 0
        for vertex in mesh_data.vertices:
            co = next(vertex_coordinates)
            if co[0] != vertex.co.x or co[1] != vertex.co.y:
                vertex_repair_count += 1
                vertex.co.x, vertex.co.y = co
        if vertex_repair_count == 0:
            self.report({'INFO'}, 'No repairs needed')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Repaired {vertex_repair_count} vertices')

        ensure_terrain_info_modifiers(context, terrain_info)

        return {'FINISHED'}


def poll_selected_terrain_layer_node_is_paint(cls, context):
    node = get_selected_terrain_paint_layer_node(context)
    if node is None:
        cls.poll_message_set('No node selected')
        return False
    if node.type != 'PAINT':
        cls.poll_message_set('Selected node is not a paint layer node')
        return False
    if node.id not in node.terrain_info_object.data.attributes:
        cls.poll_message_set(f'Layer node attribute {node.id} does not exist')
        return False
    return True


class BDK_OT_terrain_paint_layer_node_fill(Operator):
    bl_idname = 'bdk.terrain_paint_layer_node_fill'
    bl_label = 'Fill Terrain Paint Layer Node'
    bl_description = 'Fill the selected paint layer node with the selected value'
    bl_options = {'REGISTER', 'UNDO'}

    value: FloatProperty(name='Value', default=1.0, min=0.0, max=1.0)

    @classmethod
    def poll(cls, context: Context):
        return poll_selected_terrain_layer_node_is_paint(cls, context)

    def execute(self, context: Context):
        node = get_selected_terrain_paint_layer_node(context)
        attribute = node.terrain_info_object.data.attributes[node.id]
        fill_color = (self.value, self.value, self.value, 0.0)
        fill_byte_color_attribute_data(attribute, fill_color)
        # Tag the object to be updated and redraw all regions.
        context.active_object.update_tag()
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        return {'FINISHED'}


class BDK_OT_terrain_paint_layer_node_invert(Operator):
    bl_idname = 'bdk.terrain_paint_layer_node_invert'
    bl_label = 'Invert Terrain Paint Layer Node'
    bl_description = 'Invert the selected paint layer node'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_selected_terrain_layer_node_is_paint(cls, context)

    def execute(self, context: Context):
        node = get_selected_terrain_paint_layer_node(context)
        attribute = node.terrain_info_object.data.attributes[node.id]
        invert_byte_color_attribute_data(attribute)
        # Tag the object to be updated and redraw all regions.
        context.active_object.update_tag()
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        return {'FINISHED'}


def merge_down_terrain_layer_node_data(terrain_info_object: Object, nodes, nodes_index: int):
    """
    Merges the data from the node at the specified index and node below it then removes the node below it.
    :param terrain_info_object:
    :param nodes:
    :param nodes_index:
    :return:
    """
    mesh_data = cast(Mesh, terrain_info_object.data)

    node = nodes[nodes_index]
    other_node = nodes[nodes_index + 1]

    if node.id not in node.terrain_info_object.data.attributes:
        raise RuntimeError(f'Layer node attribute {node.id} does not exist')
    if other_node.id not in other_node.terrain_info_object.data.attributes:
        raise RuntimeError(f'Layer node attribute {other_node.id} does not exist')

    attribute = mesh_data.attributes[node.id]
    other_attribute = mesh_data.attributes[other_node.id]

    # Accumulate the data into the first node.
    accumulate_byte_color_attribute_data(attribute, other_attribute)

    # Remove the other node.
    remove_terrain_layer_node(terrain_info_object, nodes, nodes_index + 1)


class BDK_OT_terrain_layer_node_merge_down(Operator):
    bl_idname = 'bdk.terrain_layer_node_merge_down'
    bl_label = 'Merge Terrain Layer Nodes'
    bl_description = 'Merge the selected paint layer node and the one below it into a single node'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            cls.poll_message_set('Active object is not a terrain info object')
            return False
        terrain_info: BDK_PG_terrain_info = get_terrain_info(context.active_object)
        paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers[terrain_info.paint_layers_index]
        nodes = paint_layer.nodes
        node = nodes[paint_layer.nodes_index] if len(nodes) > paint_layer.nodes_index else None
        other_node = nodes[paint_layer.nodes_index + 1] if len(nodes) > paint_layer.nodes_index + 1 else None
        if node is None:
            cls.poll_message_set('No node selected')
            return False
        if node.type != 'PAINT':
            cls.poll_message_set('Selected node is not a paint node')
            return False
        if other_node is None:
            cls.poll_message_set('No node below selected node')
            return False
        if other_node.type != 'PAINT':
            cls.poll_message_set('Node below selected node is not a paint node')
            return False
        return True

    def execute(self, context: Context):
        # TODO: this only works for paint layers currently (make a switch to use this for deco layers too)
        terrain_info_object = context.active_object
        terrain_info: BDK_PG_terrain_info = get_terrain_info(terrain_info_object)
        paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers[terrain_info.paint_layers_index]

        # Add the attribute data of the other node to the node (with clamping).
        try:
            merge_down_terrain_layer_node_data(terrain_info_object, paint_layer.nodes, paint_layer.nodes_index)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        # Rebuild the modifier stack.
        ensure_terrain_info_modifiers(context, terrain_info)

        # Tag the object to be updated and redraw all regions.
        context.active_object.update_tag()
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

        return {'FINISHED'}


def poll_has_selected_terrain_layer_node(cls, context):
    if not is_active_object_terrain_info(context):
        cls.poll_message_set('Active object is not a terrain info object')
        return False
    terrain_info: BDK_PG_terrain_info = get_terrain_info(context.active_object)
    paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers[terrain_info.paint_layers_index]
    nodes = paint_layer.nodes
    node = nodes[paint_layer.nodes_index] if len(nodes) > paint_layer.nodes_index else None
    if node is None:
        cls.poll_message_set('No node selected')
        return False
    return True


class BDK_OT_terrain_paint_layer_node_duplicate(Operator):
    bl_idname = 'bdk.terrain_paint_layer_node_duplicate'
    bl_label = 'Duplicate Terrain Paint Layer Node'
    bl_description = 'Duplicate the selected paint layer node'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return poll_has_selected_terrain_layer_node(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        paint_layer = terrain_info.paint_layers[terrain_info.paint_layers_index]
        nodes = paint_layer.nodes
        node = nodes[paint_layer.nodes_index]

        # Duplicate the node.
        duplicate_node = nodes.add()
        duplicate_node.id = uuid.uuid4().hex
        duplicate_node.name = ensure_name_unique(node.name, [n.name for n in nodes])

        # Copy all the settings.
        copy_simple_property_group(node, duplicate_node, {'id', 'name'})

        if node.type == 'PAINT':
            # Duplicate the attribute.
            mesh_data = node.terrain_info_object.data
            attribute = mesh_data.attributes[node.id]
            duplicate_attribute = mesh_data.attributes.new(duplicate_node.id, 'BYTE_COLOR', domain='POINT')
            duplicate_attribute.data.foreach_set('color', attribute.data.foreach_get('color'))

        # Move the node to below the selected node.
        nodes.move(len(nodes) - 1, paint_layer.nodes_index + 1)

        # TODO: check the ordering as well? or does the modifier stack fn take care of that?

        # Rebuild the modifier stack.
        ensure_terrain_info_modifiers(context, terrain_info)

        return {'FINISHED'}


# TODO: this only works for paint layers atm
class BDK_OT_terrain_layer_node_convert_to_paint_node(Operator):
    bl_idname = 'bdk.terrain_layer_node_convert_to_paint_node'
    bl_label = 'Convert Terrain Layer Node to Paint Node'
    bl_description = 'Convert the selected terrain layer node to a paint node'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            cls.poll_message_set('Active object is not a terrain info object')
            return False
        terrain_info: BDK_PG_terrain_info = get_terrain_info(context.active_object)
        paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers[terrain_info.paint_layers_index]
        nodes = paint_layer.nodes
        node = nodes[paint_layer.nodes_index] if len(nodes) > paint_layer.nodes_index else None
        if node is None:
            cls.poll_message_set('No node selected')
            return False
        if node.type == 'PAINT':
            cls.poll_message_set('Selected node is already a paint node')
            return False
        convertible_types = {'CONSTANT', 'NOISE', 'NORMAL', 'FIELD'}
        if node.type not in convertible_types:
            cls.poll_message_set(f'Cannot convert node of type {node.type} to a paint node')
            return False
        return True

    def execute(self, context: Context):
        # Create a bake modifier for the selected node.
        # Depending on the context (paint vs. deco), we need to insert the bake modifier after the last
        # paint or deco node modifier (before doodads are applied). This will ensure that we are baking
        # the correct data. We will have a similar scheme to the other baking where we bake to a new
        # attribute and create a new paint node with that attribute.
        terrain_info_object = context.active_object
        terrain_info = get_terrain_info(terrain_info_object)
        paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers[terrain_info.paint_layers_index]
        nodes = paint_layer.nodes
        node: 'BDK_PG_terrain_layer_node' = nodes[paint_layer.nodes_index] if len(nodes) > paint_layer.nodes_index else None

        modifier = terrain_info_object.modifiers.new(node.id, 'NODES')
        bake_node_tree = create_terrain_paint_layer_node_convert_to_paint_layer_node_tree(node, terrain_info_object, terrain_info.paint_layers_index, paint_layer.nodes_index)
        modifier.node_group = bake_node_tree

        # TODO: get the index of the sculpt modifier and add one? (wouldn't that just be the first one?)
        bake_modifier_index = 1

        # Insert the modifier at the appropriate place.
        bpy.ops.object.modifier_move_to_index(modifier=modifier.name, index=bake_modifier_index)

        # Apply the modifier.
        bpy.ops.object.modifier_apply(modifier=modifier.name)

        # Delete the bake node tree.
        bpy.data.node_groups.remove(bake_node_tree)

        # Change the type of the node to a paint node.
        node.type = 'PAINT'

        # Rebuild the modifier stack.
        ensure_terrain_info_modifiers(context, terrain_info)

        return {'FINISHED'}


def group_items(self, context):
    terrain_info_object = context.active_object
    terrain_info: BDK_PG_terrain_info = get_terrain_info(terrain_info_object)
    # Get selected paint layer.
    paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers[terrain_info.paint_layers_index]
    # Get a list of all the group nodes.
    return [(node.id, node.name, '') for node in paint_layer.nodes if node.type == 'GROUP']


class BDK_OT_terrain_layer_paint_node_move_to_group(Operator):
    bl_idname = 'bdk.terrain_layer_paint_node_move_to_group'
    bl_label = 'Move Node to Group'
    bl_description = 'Move the selected paint layer node to a group'
    bl_options = {'REGISTER', 'UNDO'}

    group_id: EnumProperty(name='Group', items=group_items)

    @classmethod
    def poll(cls, context: Context):
        cls.poll_message_set('Not implemented yet')
        return False

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: Context):
        layout = self.layout
        layout.prop(self, 'group_id')

    def execute(self, context: Context):
        return {'FINISHED'}


def terrain_shift_x_get(self):
    terrain_info = get_terrain_info(bpy.context.active_object)
    return int(self.x_distance / terrain_info.terrain_scale)

def terrain_shift_y_get(self):
    terrain_info = get_terrain_info(bpy.context.active_object)
    return int(self.y_distance / terrain_info.terrain_scale)


class BDK_OT_terrain_info_shift(Operator):
    bl_idname = 'bdk.terrain_info_shift'
    bl_label = 'Shift Terrain'
    bl_description = 'Shift the terrain data (heightmap, paint layers, doodads, etc.) by the specified distance'
    bl_options = {'REGISTER', 'UNDO'}

    x: IntProperty(name='X', get=terrain_shift_x_get)
    y: IntProperty(name='Y', get=terrain_shift_y_get)
    x_distance: FloatProperty(name='X Distance', subtype='DISTANCE')
    y_distance: FloatProperty(name='Y Distance', subtype='DISTANCE')

    selected: BoolProperty(name='Selected Objects Only', default=False)

    data_types: EnumProperty(name='Data', items=(
        ('OBJECTS', 'Actors', 'Shift objects'),
        ('HEIGHTMAP', 'Heightmap', 'Shift the heightmap'),
        ('PAINT_LAYERS', 'Paint Layers', 'Shift the paint layers'),
        ('QUAD_TESSELATION', 'Quad Tesselation', 'Shift the quad tesselation'),
        ('TERRAIN_HOLES', 'Terrain Holes', 'Shift the terrain holes'),
    ), default={'OBJECTS', 'HEIGHTMAP', 'PAINT_LAYERS', 'QUAD_TESSELATION', 'TERRAIN_HOLES'}, options={'ENUM_FLAG'})

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def invoke(self, context: Context, event: Event):
        # Show a dialog
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: Context):
        layout = self.layout

        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(self, 'x_distance', text='Distance X')
        flow.prop(self, 'y_distance', text='Y')
        flow.separator()
        flow.prop(self, 'x')
        flow.prop(self, 'y')
        flow.separator()
        flow.prop(self, 'selected')
        flow.separator()
        flow.prop(self, 'data_types')

    def execute(self, context: Context):
        if self.x == 0.0 and self.y == 0.0:
            return {'FINISHED'}

        terrain_info_object = context.active_object
        terrain_info = get_terrain_info(terrain_info_object)
        mesh_data: Mesh = cast(Mesh, terrain_info_object.data)

        translation = mathutils.Vector((self.x * terrain_info.terrain_scale, self.y * terrain_info.terrain_scale, 0.0))

        if 'OBJECTS' in self.data_types:
            # Iterate over all other objects in the scene.
            for obj in bpy.data.objects:
                if obj.parent is not None:
                    # We don't want to move objects that are parented to other objects, or else we will move them twice.
                    continue
                if self.selected and not obj.select_get():
                    continue
                if obj != terrain_info_object:
                    obj.location += translation

        # Convert the z-values of the terrain info vertices to a numpy array.
        if 'HEIGHTMAP' in self.data_types:
            shape = terrain_info.x_size, terrain_info.y_size
            count = terrain_info.x_size * terrain_info.y_size
            z_values = numpy.fromiter(map(lambda v: v.co.z, mesh_data.vertices), dtype=float, count=count).reshape(shape)
            z_values = numpy.roll(z_values, (self.x, self.y), axis=(1, 0))

            # Reassign the z-values to the terrain info vertices.
            for (vertex, z) in zip(mesh_data.vertices, z_values.flat):
                vertex.co.z = z

        if 'PAINT_LAYERS' in self.data_types:
            for attribute in mesh_data.attributes:
                if attribute.data_type == 'BYTE_COLOR':
                    # Convert the attribute values to a numpy array.
                    shape = (terrain_info.x_size, terrain_info.y_size, 4)
                    count = terrain_info.x_size * terrain_info.y_size
                    attribute_values = numpy.fromiter(map(lambda v: v.color, attribute.data), dtype=(float, 4), count=count).reshape(shape)
                    attribute_values = numpy.roll(attribute_values, (self.x, self.y), axis=(1, 0))
                    # Reassign the attribute values.
                    attribute.data.foreach_set('color', attribute_values.flatten())

        # Shift the quad tesselation.
        if 'QUAD_TESSELATION' in self.data_types:
            quad_edge_turns = numpy.zeros(len(mesh_data.polygons), dtype=int)
            vertex_index = 0
            for y in range(terrain_info.y_size - 1):
                for x in range(terrain_info.x_size - 1):
                    polygon_index = y * (terrain_info.x_size - 1) + x
                    polygon = mesh_data.polygons[polygon_index]
                    loop_vertex_index = mesh_data.loops[polygon.loop_start].vertex_index
                    # Check if the first vertex in the loop for this face coincides with the natural first vertex or the vertex
                    # diagonal to it.
                    if loop_vertex_index == vertex_index or loop_vertex_index == vertex_index + terrain_info.x_size + 1:
                        quad_edge_turns[polygon_index] = 1
                    vertex_index += 1
                vertex_index += 1

            quad_edge_turns = quad_edge_turns.reshape((terrain_info.x_size - 1, terrain_info.y_size - 1))

            # Store the original quad edge turns.
            original_quad_edge_turns = quad_edge_turns.flatten()

            # Do a padded roll to shift the quad edge turns.
            new_quad_edge_turns = padded_roll(quad_edge_turns, (self.x, self.y)).flatten()

            # Turn the edges of the quads that have changed.
            for polygon_index in range(len(original_quad_edge_turns)):
                if original_quad_edge_turns[polygon_index] != new_quad_edge_turns[polygon_index]:
                    polygon = mesh_data.polygons[polygon_index]
                    loops = [mesh_data.loops[i] for i in range(polygon.loop_start, polygon.loop_start + polygon.loop_total)]
                    loop_vertex_indices = deque(map(lambda l: l.vertex_index, loops))
                    loop_vertex_indices.rotate(1)
                    for (loop, vertex_index) in zip(loops, loop_vertex_indices):
                        loop.vertex_index = vertex_index

            mesh_data.update(calc_edges=True)

        if 'TERRAIN_HOLES' in self.data_types:
            # Move the terrain holes (material indices).
            # Convert all the material indices to a numpy array (used for terrain holes)
            shape = (terrain_info.x_size - 1, terrain_info.y_size - 1)
            count = terrain_info.x_size - 1 * terrain_info.y_size - 1
            material_indices = numpy.fromiter(map(lambda f: f.material_index, mesh_data.polygons),
                                              dtype=int, count=count).reshape(shape)  # Can we avoid the reshape?
            material_indices = padded_roll(material_indices, (self.x, self.y))
            # Reassign the material indices.
            for (face, material_index) in zip(mesh_data.polygons, material_indices.flat):
                face.material_index = material_index

        return {'FINISHED'}


class BDK_OT_terrain_info_set_terrain_scale(Operator):
    bl_idname = 'bdk.terrain_info_set_terrain_scale'
    bl_label = 'Set Terrain Scale'
    bl_description = 'Set the terrain scale'
    bl_options = {'REGISTER', 'UNDO'}

    terrain_scale: FloatProperty(name='Terrain Scale', default=64.0, min=0, soft_min=16.0, soft_max=128.0, max=512, subtype='DISTANCE')

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)

        # TODO: this isn't tested yet!
        xy_coordinates_iter = get_terrain_info_vertex_xy_coordinates(terrain_info.x_size, self.terrain_scale)

        mesh_data = cast(Mesh, context.active_object.data)
        for vertex in mesh_data.vertices:
            x, y = next(xy_coordinates_iter)
            vertex.co.x = x
            vertex.co.y = y

        terrain_info.terrain_scale = self.terrain_scale

        return {'FINISHED'}


class BDK_OT_terrain_info_heightmap_import(Operator):
    bl_idname = 'bdk.terrain_info_heightmap_import'
    bl_label = 'Import Heightmap'
    bl_description = 'Import a heightmap image'
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(name='File Path', subtype='FILE_PATH')
    filter_glob: StringProperty(default='*.tga;*.bmp', options={'HIDDEN'})

    terrain_scale_z: FloatProperty(name='Heightmap Scale', default=64.0, min=0, soft_min=16.0, soft_max=128.0, max=512)

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def invoke(self, context: Context, event: Event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: Context):
        extension = os.path.splitext(self.filepath)[1]

        if extension == '.tga':
            # TODO: assume we are dealing with a UModel TGA file, where the heights are stored in the RGB channels.
            self.report({'ERROR'}, 'TGA files are not supported yet')
            return {'CANCELLED'}
        elif extension == '.bmp':
            # Read the G16 BMP file.
            try:
                heightmap = read_bmp_g16(self.filepath)
            except IOError as e:
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}

            # Make sure the heightmap is the correct size.
            terrain_info = get_terrain_info(context.active_object)
            if heightmap.shape != (terrain_info.x_size, terrain_info.y_size):
                self.report({'ERROR'}, f'Heightmap is the wrong size. Expected {terrain_info.x_size}x{terrain_info.y_size}, got {heightmap.shape[0]}x{heightmap.shape[1]}')
                return {'CANCELLED'}

            # Convert the heightmap to floating point values.
            heightmap = heightmap.astype(float)
            # De-quantize the heightmap.
            heightmap = (heightmap / 65535.0) - 0.5
        else:
            self.report({'ERROR'}, f'Unsupported file extension {extension}')
            return {'CANCELLED'}

        # Apply the heightmap to the mesh.
        mesh_data = cast(Mesh, context.active_object.data)
        for (vertex, z) in zip(mesh_data.vertices, heightmap.flat):
            vertex.co.z = z * self.terrain_scale_z * 256.0

        return {'FINISHED'}


def terrain_layer_items_cb(self, context):
    terrain_info = get_terrain_info(context.active_object)
    return [(layer.id, layer.name, '') for layer in terrain_info.paint_layers]


class BDK_OT_terrain_paint_layer_node_transfer(Operator):
    bl_idname = 'bdk.terrain_paint_layer_node_transfer'
    bl_label = 'Transfer Node to Paint Layer'
    bl_description = 'Move the selected node to another terrain paint layer'
    bl_options = {'REGISTER', 'UNDO'}

    layer_id: EnumProperty(name='Terrain Layer', items=terrain_layer_items_cb)

    @classmethod
    def poll(cls, context: Context):
        return poll_has_selected_terrain_layer_node(cls, context)

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context: Context):
        layout = self.layout
        layout.prop(self, 'layer_id')

    def execute(self, context: Context):
        terrain_info_object = context.active_object
        terrain_info = get_terrain_info(terrain_info_object)

        # Get the source and target paint layers.
        source_paint_layer: BDK_PG_terrain_paint_layer = terrain_info.paint_layers[terrain_info.paint_layers_index]
        target_paint_layer = get_terrain_info_paint_layer_by_id(terrain_info, self.layer_id)

        if target_paint_layer is None:
            self.report({'ERROR'}, f'Terrain layer {self.layer_id} does not exist')
            return {'CANCELLED'}

        # TODO: when we have groups, we'll need to move the whole hierarchy of nodes.

        move_node_between_node_lists(source_paint_layer.nodes, source_paint_layer.nodes_index, target_paint_layer.nodes)

        ensure_paint_layers(terrain_info_object)

        return {'FINISHED'}


classes = (
    BDK_OT_terrain_info_add,
    BDK_OT_terrain_info_export,
    BDK_OT_terrain_info_repair,
    BDK_OT_terrain_info_shift,
    BDK_OT_terrain_info_heightmap_import,
    BDK_OT_terrain_info_set_terrain_scale,

    BDK_OT_terrain_paint_layer_add,
    BDK_OT_terrain_paint_layer_remove,
    BDK_OT_terrain_paint_layer_move,
    BDK_OT_terrain_paint_layers_show,
    BDK_OT_terrain_paint_layers_hide,

    BDK_OT_terrain_paint_layer_nodes_add,
    BDK_OT_terrain_paint_layer_nodes_remove,
    BDK_OT_terrain_paint_layer_node_duplicate,

    BDK_OT_terrain_layer_node_merge_down,
    BDK_OT_terrain_layer_node_convert_to_paint_node,
    BDK_OT_terrain_paint_layer_node_transfer,
    BDK_OT_terrain_layer_paint_node_move_to_group,

    # TODO: these node operators below should be renamed (they are not specific to "paint" layers)
    BDK_OT_terrain_paint_layer_nodes_move,
    BDK_OT_terrain_paint_layer_node_fill,
    BDK_OT_terrain_paint_layer_node_invert,

    BDK_OT_terrain_deco_layer_add,
    BDK_OT_terrain_deco_layer_remove,
    BDK_OT_terrain_deco_layers_hide,
    BDK_OT_terrain_deco_layers_show,
    BDK_OT_terrain_deco_layer_nodes_add,
    BDK_OT_terrain_deco_layer_nodes_remove,
    BDK_OT_terrain_deco_layer_nodes_move,
)
