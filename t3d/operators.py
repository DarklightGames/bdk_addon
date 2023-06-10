import math
from io import StringIO

import bpy
from bpy.types import Operator, Context, Object
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from ..terrain.exporter import create_static_mesh_actor, add_movement_properties_to_actor
from .data import T3DMap, T3DActor
from pathlib import Path
from .importer import import_t3d
from .writer import T3DWriter
from ..helpers import are_bdk_dependencies_installed


class BDK_OT_t3d_import_from_clipboard(Operator):
    bl_idname = 'bdk.t3d_import_from_clipboard'
    bl_description = 'Import T3DMap from OS Clipboard'
    bl_label = 'Paste T3D From Clipboard'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        # Return false if the clipboard doesn't contain text
        if not context.window_manager.clipboard:
            cls.poll_message_set(message='Clipboard is empty')
            return False
        return True

    def execute(self, context: Context):
        try:
            import_t3d(context.window_manager.clipboard, context)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except SyntaxError as e:
            print(e)
            self.report({'ERROR'}, 'Clipboard data is not valid T3DMap syntax. Additional debugging information has been '
                                   'written to the console')
            return {'CANCELLED'}
        self.report({'INFO'}, f'T3DMap Imported successfully')
        return {'FINISHED'}


class BDK_OT_t3d_import_from_file(Operator, ImportHelper):
    bl_idname = 'bdk.t3d_import_from_file'
    bl_description = 'Import T3DMap'
    bl_label = 'Import T3DMap (*.t3d)'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext: StringProperty(default='.t3d', options={'HIDDEN'})
    filepath: StringProperty()
    filter_glob: StringProperty(default='*.t3d', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for importing the T3DMap file',
        maxlen=1024,
        default='')

    @classmethod
    def poll(cls, context: Context):
        if not are_bdk_dependencies_installed():
            cls.poll_message_set(message='Dependencies are not installed')
            return False
        return True

    def execute(self, context: Context):
        contents = Path(self.filepath).read_text()
        try:
            import_t3d(contents, context)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except SyntaxError as e:
            print(e)
            self.report({'ERROR', 'File contents are not valid T3DMap syntax. Additional debugging information has been '
                                  'written to the console'})
        self.report({'INFO'}, f'T3DMap Imported successfully')
        return {'FINISHED'}


# TODO: Copying from the outliner
class BDK_OT_t3d_copy_to_clipboard(Operator):
    bl_idname = 'bdk.t3d_copy_objects_to_clipboard'
    bl_description = 'Copy to clipboard as Unreal T3DMap objects'
    bl_label = 'Copy as Unreal T3DMap'

    @classmethod
    def poll(cls, context: Context):
        # Return false if no objects are selected.
        if len(context.selected_objects) == 0:
            cls.poll_message_set('No objects selected')
            return False
        return True

    def execute(self, context: Context):
        copy_actors: list[T3DActor] = []
        t3d = T3DMap()

        def can_copy(bpy_object: Object) -> bool:
            # TODO: SpectatorCam, Projector, FluidSurface etc.
            return bpy_object.type == 'MESH' and bpy_object.data is not None

        for obj in context.selected_objects:
            # TODO: add handlers for other object types (outside of this function)
            if obj.type == 'CAMERA':
                # Create a SpectatorCam actor
                actor = T3DActor('SpectatorCam', obj.name)
                add_movement_properties_to_actor(actor, obj)
                rotation_euler = actor['Rotation']
                # TODO: make corrective matrix a constant
                # Correct the rotation here since the blender cameras point down -Z with +X up by default.
                rotation_euler.z += math.pi / 2
                rotation_euler.x -= math.pi / 2
                # Adjust the camera's rotation to match the Unreal coordinate system.
                t3d.actors.append(actor)
            else:
                if obj.instance_collection:
                    copy_actors += [create_static_mesh_actor(o, obj)
                                    for o in obj.instance_collection.all_objects
                                    if can_copy(o)]
                elif can_copy(obj):
                    copy_actors.append(create_static_mesh_actor(obj))

        for actor in copy_actors:
            t3d.actors.append(actor)

        string_io = StringIO()
        T3DWriter(string_io).write(t3d)
        string_io.seek(0)

        bpy.context.window_manager.clipboard = string_io.read()

        return {'FINISHED'}


classes = (
    BDK_OT_t3d_copy_to_clipboard,
    BDK_OT_t3d_import_from_file,
    BDK_OT_t3d_import_from_clipboard,
)
