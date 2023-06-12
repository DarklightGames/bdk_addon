import os
import uuid

import bpy.types
from typing import cast

import numpy
from bpy.props import IntProperty, FloatProperty, FloatVectorProperty, BoolProperty, StringProperty, EnumProperty
from bpy.types import Operator, Context, Mesh, Object
from bpy_extras.io_utils import ExportHelper

from .deco import add_terrain_deco_layer, build_deco_layers, update_terrain_layer_node_group
from .exporter import export_terrain_heightmap, export_terrain_paint_layers, export_deco_layers, write_terrain_t3d
from .layers import add_terrain_paint_layer
from .objects.properties import sort_terrain_info_modifiers

from ..helpers import get_terrain_info, is_active_object_terrain_info
from .builder import build_terrain_material, create_terrain_info_object, get_terrain_quad_size, \
    get_terrain_info_vertex_coordinates
from .properties import terrain_layer_node_type_items


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
        active_object = context.active_object

        if active_object is None:
            return {'CANCELLED'}

        terrain_info = get_terrain_info(active_object)
        paint_layers = terrain_info.paint_layers
        paint_layers_index = terrain_info.paint_layers_index

        if paint_layers_index < 0:
            return {'CANCELLED'}

        # Remove color attribute.
        terrain_object = context.active_object
        mesh_data = cast(Mesh, terrain_object.data)
        paint_layer_id = paint_layers[paint_layers_index].id
        if paint_layer_id in mesh_data.color_attributes:
            color_attribute = mesh_data.color_attributes[paint_layer_id]
            mesh_data.color_attributes.remove(color_attribute)

        paint_layers.remove(paint_layers_index)

        terrain_info.paint_layers_index = min(len(paint_layers) - 1, paint_layers_index)

        # Delete the associated modifier and node group.
        if paint_layer_id in terrain_object.modifiers:
            paint_layer_modifier = terrain_object.modifiers[paint_layer_id]
            terrain_object.modifiers.remove(paint_layer_modifier)

        if paint_layer_id in bpy.data.node_groups:
            bpy.data.node_groups.remove(bpy.data.node_groups[paint_layer_id])

        build_terrain_material(terrain_object)

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

        return {'FINISHED'}


class BDK_OT_terrain_deco_layer_add(Operator):
    bl_idname = 'bdk.terrain_deco_layer_add'
    bl_label = 'Add Deco Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        return is_active_object_terrain_info(context)

    def execute(self, context: bpy.types.Context):
        terrain_info = get_terrain_info(context.active_object)
        add_terrain_deco_layer(context.active_object)
        sort_terrain_info_modifiers(context, terrain_info)
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

        # Remove the deco layer modifier from the terrain object.
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
        build_deco_layers(context.active_object)

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
        terrain_info = get_terrain_info(context.active_object)
        try:
            add_terrain_paint_layer(active_object, name='TerrainLayer')
            sort_terrain_info_modifiers(context, terrain_info)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

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
        mesh_object = create_terrain_info_object(resolution=self.resolution, size=self.size)
        mesh_object.location = self.location

        if self.lock_transforms:
            # Lock transforms so that levelers don't accidentally move the terrain.
            mesh_object.lock_location = [True] * 3
            mesh_object.lock_scale = [True] * 3
            mesh_object.lock_rotation = [True] * 3
            mesh_object.lock_rotation_w = True
            mesh_object.lock_rotations_4d = True

        # Add a base layer to start with.
        add_terrain_paint_layer(mesh_object, name='Base')

        context.scene.collection.objects.link(mesh_object)

        # Select the new object.
        context.view_layer.objects.active = mesh_object
        mesh_object.select_set(True)

        return {'FINISHED'}


class BDK_OT_terrain_info_export(Operator, ExportHelper):
    bl_label = 'Export BDK Terrain Info'
    bl_idname = 'bdk.terrain_info_export'

    directory: StringProperty(name='Directory')
    filename_ext: StringProperty(default='.', options={'HIDDEN'})
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})

    @classmethod
    def poll(cls, context: 'Context'):
        if not is_active_object_terrain_info(context):
            cls.poll_message_set('The active object must be a TerrainInfo object')
            return False
        return True

    def invoke(self, context: 'Context', event: 'Event'):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context: Context):
        # Get the depsgraph.
        depsgraph = context.evaluated_depsgraph_get()

        with open(os.path.join(self.directory, f'{context.active_object.name}.t3d'), 'w') as fp:
            write_terrain_t3d(context.active_object, depsgraph, fp)

        export_terrain_heightmap(context.active_object, depsgraph, directory=self.directory)
        export_terrain_paint_layers(context.active_object, depsgraph, directory=self.directory)
        export_deco_layers(context.active_object, depsgraph, directory=self.directory)

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


def add_terrain_layer_node(terrain_info_object: Object, nodes, type: str):
    node = nodes.add()
    node.id = uuid.uuid4().hex
    node.name = type
    node.terrain_info_object = terrain_info_object
    node.type = type

    if type == 'PAINT':
        mesh_data = terrain_info_object.data
        # TODO: when we can paint non-color data, rewrite this!
        # Add the density map attribute to the TerrainInfo mesh.
        attribute = mesh_data.attributes.new(node.id, 'BYTE_COLOR', domain='POINT')
        vertex_count = len(attribute.data)
        color_data = numpy.ndarray(shape=(vertex_count, 4), dtype=float)
        color_data[:] = (0.0, 0.0, 0.0, 0.0)
        attribute.data.foreach_set('color', color_data.flatten())

    # Move the node to the top of the list.
    nodes.move(len(nodes) - 1, 0)
    return node


def remove_terrain_layer_node(terrain_info_object: Object, nodes, nodes_index: int):
    node = nodes[nodes_index]

    if node.type == 'PAINT':
        mesh_data = terrain_info_object.data
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


def poll_is_active_object_terrain_object(cls, context):
    if not is_active_object_terrain_info(context):
        cls.poll_message_set('The active object is not a terrain info object')
        return False
    # TODO: should also have a selected layer.
    return True


terrain_layer_node_move_direction_items = [
    ('UP', 'Up', 'Move the node up'),
    ('DOWN', 'Down', 'Move the node down')
]


class BDK_OT_terrain_deco_layer_nodes_add(Operator):
    bl_idname = 'bdk.terrain_deco_layer_nodes_add'
    bl_label = 'Add Deco Layer Node'
    bl_description = 'Add a node to the selected deco layer'

    type: EnumProperty(name='Type', items=terrain_layer_node_type_items)

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_object(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer = deco_layers[deco_layers_index]

        add_terrain_layer_node(context.active_object, deco_layer.nodes, self.type)

        # TODO: for some reason, the factor driver is invalid when added [is this still true?]
        build_deco_layers(context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_deco_layer_nodes_remove(Operator):
    bl_idname = 'bdk.terrain_deco_layer_nodes_remove'
    bl_label = 'Remove Deco Layer Node'
    bl_description = 'Remove the selected layer node from the selected deco layer'

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_object(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer = deco_layers[deco_layers_index]

        remove_terrain_layer_node(context.active_object, deco_layer.nodes, deco_layer.nodes_index)

        build_deco_layers(context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_deco_layer_nodes_move(Operator):
    bl_idname = 'bdk.terrain_deco_layer_nodes_move'
    bl_label = 'Move Deco Layer Node'
    bl_description = 'Move the selected layer node'

    direction: EnumProperty(name='Direction', items=terrain_layer_node_move_direction_items, default='UP')

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_object(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        deco_layers = terrain_info.deco_layers
        deco_layers_index = terrain_info.deco_layers_index
        deco_layer = deco_layers[deco_layers_index]

        deco_layer.nodes_index = move_terrain_layer_node(self.direction, deco_layer.nodes, deco_layer.nodes_index)

        build_deco_layers(context.active_object)

        return {'FINISHED'}


class BDK_OT_terrain_paint_layer_nodes_add(Operator):
    bl_idname = 'bdk.terrain_paint_layer_nodes_add'
    bl_label = 'Add Paint Layer Node'
    bl_description = 'Add a node to the selected paint layer'

    type: EnumProperty(name='Type', items=terrain_layer_node_type_items)

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_object(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        paint_layers = terrain_info.paint_layers
        paint_layers_index = terrain_info.paint_layers_index
        paint_layer = paint_layers[paint_layers_index]

        add_terrain_layer_node(context.active_object, paint_layer.nodes, self.type)

        if paint_layer.id in bpy.data.node_groups:
            node_tree = bpy.data.node_groups[paint_layer.id]
            update_terrain_layer_node_group(node_tree, 'paint_layers', paint_layers_index, paint_layer.id, paint_layer.nodes)

        return {'FINISHED'}


class BDK_OT_terrain_paint_layer_nodes_remove(Operator):
    bl_idname = 'bdk.terrain_paint_layer_nodes_remove'
    bl_label = 'Remove Paint Layer Node'
    bl_description = 'Remove the selected layer node from the selected paint layer'

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_object(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        paint_layers = terrain_info.paint_layers
        paint_layers_index = terrain_info.paint_layers_index
        paint_layer = paint_layers[paint_layers_index]

        remove_terrain_layer_node(context.active_object, paint_layer.nodes, paint_layer.nodes_index)

        if paint_layer.id in bpy.data.node_groups:
            node_tree = bpy.data.node_groups[paint_layer.id]
            update_terrain_layer_node_group(node_tree, 'paint_layers', paint_layers_index, paint_layer.id, paint_layer.nodes)

        return {'FINISHED'}


class BDK_OT_terrain_paint_layer_nodes_move(Operator):
    bl_idname = 'bdk.terrain_paint_layer_nodes_move'
    bl_label = 'Move Deco Layer Node'
    bl_description = 'Move the selected layer node'

    direction: EnumProperty(name='Direction', items=terrain_layer_node_move_direction_items, default='UP')

    @classmethod
    def poll(cls, context: Context):
        return poll_is_active_object_terrain_object(cls, context)

    def execute(self, context: Context):
        terrain_info = get_terrain_info(context.active_object)
        paint_layers = terrain_info.paint_layers
        paint_layers_index = terrain_info.paint_layers_index
        paint_layer = paint_layers[paint_layers_index]

        paint_layer.nodes_index = move_terrain_layer_node(self.direction, paint_layer.nodes, paint_layer.nodes_index)

        # build_paint_layers(context.active_object)

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
        vertex_coordinates = get_terrain_info_vertex_coordinates(resolution=terrain_info.x_size, size=terrain_info.x_size * terrain_info.terrain_scale)
        mesh_data = context.active_object.data
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
        return {'FINISHED'}


classes = (
    BDK_OT_terrain_info_add,
    BDK_OT_terrain_info_export,
    BDK_OT_terrain_info_repair,

    BDK_OT_terrain_paint_layer_add,
    BDK_OT_terrain_paint_layer_remove,
    BDK_OT_terrain_paint_layer_move,
    BDK_OT_terrain_paint_layers_show,
    BDK_OT_terrain_paint_layers_hide,
    BDK_OT_terrain_paint_layer_nodes_add,
    BDK_OT_terrain_paint_layer_nodes_remove,
    BDK_OT_terrain_paint_layer_nodes_move,

    BDK_OT_terrain_deco_layer_add,
    BDK_OT_terrain_deco_layer_remove,
    BDK_OT_terrain_deco_layers_hide,
    BDK_OT_terrain_deco_layers_show,
    BDK_OT_terrain_deco_layer_nodes_add,
    BDK_OT_terrain_deco_layer_nodes_remove,
    BDK_OT_terrain_deco_layer_nodes_move,
)
