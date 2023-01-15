import bpy
from bpy.types import Operator, FileSelectEntry, Space, Context, Object
from typing import Sequence, Set
from .data import UStaticMeshActor, UActor, UMap
from pathlib import Path


# TODO: Copying assets from the asset browser
class BDK_OP_CopyAsset(Operator):
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
class BDK_OP_CopyObject(Operator):
    bl_idname = 'bdk_t3d.copy_object'
    bl_description = 'Copy to clipboard as Unreal T3D objects'
    bl_label = 'Copy as Unreal T3D'

    def execute(self, context: Context) -> Set[str]:
        copy_objects: list[Object] = []

        for obj in context.selected_objects:
            if obj.instance_collection:
                copy_objects += [*obj.instance_collection.all_objects]
            else:
                copy_objects.append(obj)

        map = UMap()

        for obj in copy_objects:
            if obj.type == 'MESH' and obj.data is not None:
                map.add_actor(UStaticMeshActor(obj))

        bpy.context.window_manager.clipboard = map.to_text()
        print(map.to_text())

        return {'FINISHED'}


classes = ( 
    BDK_OP_CopyObject,
)
