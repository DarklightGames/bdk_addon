import bpy
from bpy.types import Operator, FileSelectEntry, Space, Context, Object
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from typing import Sequence, Set
from .data import UStaticMeshActor, UActor, UMap
from pathlib import Path
from .importer import import_t3d
from ..helpers import are_bdk_dependencies_installed


class BDK_OT_T3DImportFromClipboard(Operator):
    bl_idname = 'bdk.t3d_import_from_clipboard'
    bl_description = 'Import T3D from OS Clipboard'
    bl_label = 'Import T3D from Clipboard'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        if not are_bdk_dependencies_installed():
            cls.poll_message_set(message='Dependencies are not installed')
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


class BDK_OT_T3DImportFromFile(Operator, ImportHelper):
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


# TODO: Copying assets from the asset browser
class BDK_OT_CopyAsset(Operator):
    bl_idname = 'bdk_t3d.copy_asset'
    bl_description = 'Copy assets to clipboard as Unreal T3D objects. Only local assets are supported'
    bl_label = 'Copy as Unreal T3D'
    bl_options = {'INTERNAL'}

    def execute(self, context: Context) -> Set[str]:
        assets: Sequence[FileSelectEntry] = context.selected_asset_files
        library: str | int = ''
        active: Space = context.area.spaces.active

        for asset in assets:
            asset_path: Path = Path(asset.relative_path)
            print(asset_path.parent)

        # if isinstance(active, SpaceFileBrowser) and isinstance(active.params, FileAssetSelectParams):
        #     library = active.params.asset_library_ref

        # library_path: Path
        # asset_libraries: bpy_prop_collection[UserAssetLibrary] = context.preferences.filepaths.asset_libraries

        # try:
        #     library_path = Path(asset_libraries.get(str(library)).path) # type: ignore
        # except AttributeError:
        #     library_path = Path(bpy.data.filepath) # will be '.' if file has never been saved

        return {'FINISHED'}


# TODO: Copying from the outliner
class BDK_OT_CopyObject(Operator):
    bl_idname = 'bdk_t3d.copy_object'
    bl_description = 'Copy to clipboard as Unreal T3D objects'
    bl_label = 'Copy as Unreal T3D'

    def execute(self, context: Context) -> Set[str]:
        copy_actors: list[UActor] = []

        def can_copy(object: Object) -> bool:
            return object.type == 'MESH' and object.data is not None

        for obj in context.selected_objects:
            if obj.instance_collection:
                copy_actors += [UStaticMeshActor(o, obj) \
                                for o in obj.instance_collection.all_objects \
                                if can_copy(o)]
            elif can_copy(obj):
                copy_actors.append(UStaticMeshActor(obj))

        map = UMap()

        for actor in copy_actors:
            map.add_actor(actor)

        bpy.context.window_manager.clipboard = map.to_text()
        print(map.to_text())

        return {'FINISHED'}


classes = (
    BDK_OT_CopyObject,
    BDK_OT_T3DImportFromFile,
    BDK_OT_T3DImportFromClipboard,
)
