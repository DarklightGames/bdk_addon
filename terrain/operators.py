import os

import bpy.types
from typing import cast
from bpy.props import IntProperty, FloatProperty, FloatVectorProperty, BoolProperty, StringProperty, EnumProperty
from bpy.types import Operator, Context, Mesh, Object
from bpy_extras.io_utils import ExportHelper

from .deco import add_terrain_deco_layer, build_deco_layers
from .exporter import export_terrain_heightmap, export_terrain_layers, export_deco_layers, write_terrain_t3d
from .layers import add_terrain_layer

from ..helpers import get_terrain_info, is_active_object_terrain_info
from .builder import build_terrain_material, create_terrain_info_object, get_terrain_quad_size
from .properties import BDK_PG_terrain_info


class BDK_OT_terrain_layer_remove(Operator):
    bl_idname = 'bdk.terrain_layer_remove'
    bl_label = 'Remove Terrain Layer'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        if not is_active_object_terrain_info(context):
            return False
        return get_terrain_info(context.active_object).terrain_layers_index >= 0

    def execute(self, context: Context):
        active_object = context.active_object

        if active_object is None:
            return {'CANCELLED'}

        terrain_info = get_terrain_info(active_object)
        terrain_layers = terrain_info.terrain_layers
        terrain_layers_index = terrain_info.terrain_layers_index

        if terrain_layers_index >= 0:
            # Remove color attribute.
            terrain_object = context.active_object
            mesh_data = cast(Mesh, terrain_object.data)
            color_attribute_name = terrain_layers[terrain_layers_index].color_attribute_name
            if color_attribute_name in mesh_data.color_attributes:
                color_attribute = mesh_data.color_attributes[color_attribute_name]
                mesh_data.color_attributes.remove(color_attribute)

            terrain_layers.remove(terrain_layers_index)

            terrain_info.terrain_layers_index = min(len(terrain_layers) - 1, terrain_layers_index)

            build_terrain_material(terrain_object)

        return {'FINISHED'}


class BDK_OT_terrain_layer_move(Operator):
    bl_idname = 'bdk.terrain_layer_move'
    bl_label = 'Move Terrain Layer'
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
        terrain_layers = terrain_info.terrain_layers
        terrain_layers_index = terrain_info.terrain_layers_index

        if self.direction == 'UP' and terrain_layers_index > 0:
            terrain_layers.move(terrain_layers_index, terrain_layers_index - 1)
            terrain_info.terrain_layers_index -= 1
            build_terrain_material(active_object)
        elif self.direction == 'DOWN' and terrain_layers_index < len(terrain_layers) - 1:
            terrain_layers.move(terrain_layers_index, terrain_layers_index + 1)
            terrain_info.terrain_layers_index += 1
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
        add_terrain_deco_layer(context, context.active_object)

        build_deco_layers(context.active_object)

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


class BDK_OT_terrain_layer_add(Operator):
    bl_idname = 'bdk.terrain_layer_add'
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
        return len(terrain_info.terrain_layers) < 32

    def execute(self, context: bpy.types.Context):
        active_object = context.active_object

        try:
            add_terrain_layer(active_object, name='TerrainLayer', fill=self.alpha_fill)
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
        add_terrain_layer(mesh_object, name='Base', fill=(1.0, 1.0, 1.0, 1.0))

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
        export_terrain_layers(context.active_object, depsgraph, directory=self.directory)
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


classes = (
    BDK_OT_terrain_info_add,
    BDK_OT_terrain_layer_add,
    BDK_OT_terrain_layer_remove,
    BDK_OT_terrain_layer_move,
    BDK_OT_terrain_deco_layer_add,
    BDK_OT_terrain_deco_layer_remove,
    BDK_OT_terrain_info_export,
    BDK_OT_terrain_deco_layers_hide,
    BDK_OT_terrain_deco_layers_show
)
