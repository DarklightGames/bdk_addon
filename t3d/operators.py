import bpy
from bpy.types import Operator, Context, Object
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from typing import  Set
from .data import UStaticMeshActor, UActor
from pathlib import Path
from .importer import import_t3d
from ..helpers import are_bdk_dependencies_installed
from t3dpy import T3dObject


class BDK_OT_t3d_import_from_clipboard(Operator):
    bl_idname = 'bdk.t3d_import_from_clipboard'
    bl_description = 'Import T3D from OS Clipboard'
    bl_label = 'Import T3D from Clipboard'
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
            self.report({'ERROR'}, 'Clipboard data is not valid T3D syntax. Additional debugging information has been '
                                   'written to the console')
            return {'CANCELLED'}
        self.report({'INFO'}, f'T3D Imported successfully')
        return {'FINISHED'}


class BDK_OT_t3d_import_from_file(Operator, ImportHelper):
    bl_idname = 'bdk.t3d_import_from_file'
    bl_description = 'Import T3D'
    bl_label = 'Import T3D (*.t3d)'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext: StringProperty(default='.t3d', options={'HIDDEN'})
    filepath: StringProperty()
    filter_glob: StringProperty(default='*.t3d', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for importing the T3D file',
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
            self.report({'ERROR', 'File contents are not valid T3D syntax. Additional debugging information has been '
                                  'written to the console'})
        self.report({'INFO'}, f'T3D Imported successfully')
        return {'FINISHED'}


# TODO: Copying from the outliner
class BDK_OT_t3d_copy_to_clipboard(Operator):
    bl_idname = 'bdk.t3d_copy_objects_to_clipboard'
    bl_description = 'Copy to clipboard as Unreal T3D objects'
    bl_label = 'Copy as Unreal T3D'

    @classmethod
    def poll(cls, context: Context):
        # Return false if no objects are selected.
        if len(context.selected_objects) == 0:
            cls.poll_message_set('No objects selected')
            return False
        return True

    def execute(self, context: Context) -> Set[str]:
        copy_actors: list[UActor] = []

        def can_copy(object: Object) -> bool:
            # TODO: SpectatorCam, Projector, FluidSurface etc.
            return object.type == 'MESH' and object.data is not None

        for obj in context.selected_objects:
            if obj.instance_collection:
                copy_actors += [UStaticMeshActor(o, obj) \
                                for o in obj.instance_collection.all_objects \
                                if can_copy(o)]
            elif can_copy(obj):
                copy_actors.append(UStaticMeshActor(obj))

        t3d = T3D()

        for actor in copy_actors:
            map.add_actor(actor)

        bpy.context.window_manager.clipboard = map.to_text()

        return {'FINISHED'}


classes = (
    BDK_OT_t3d_copy_to_clipboard,
    BDK_OT_t3d_import_from_file,
    BDK_OT_t3d_import_from_clipboard,
)
