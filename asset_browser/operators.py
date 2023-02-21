import bpy
from bpy.types import (Operator, FileSelectEntry, Space, Context, 
                       bpy_prop_collection, SpaceFileBrowser, 
                       FileAssetSelectParams, UserAssetLibrary)
from pathlib import Path
from typing import Set, Sequence


class BDK_OT_ImportDataLinked(Operator):
    bl_idname = 'bdk_asset_browser.import_data_linked'
    bl_description = 'Link asset from a library'
    bl_label = 'Import Data (Linked)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context: 'Context'):
        return context.mode == 'OBJECT'

    def execute(self, context: Context) -> Set[str]:
        library: str | int = ''
        active: Space = context.area.spaces.active

        if isinstance(active, SpaceFileBrowser) and \
           isinstance(active.params, FileAssetSelectParams):
            library = active.params.asset_library_ref

        library_path: Path
        asset_libraries: bpy_prop_collection[UserAssetLibrary] = context.preferences.filepaths.asset_libraries

        try:
            library_path = Path(asset_libraries.get(str(library)).path) # type: ignore
        except AttributeError:
            # TODO: We don't need to link local assets.
            library_path = Path(bpy.data.filepath) # will be '.' if file has never been saved

        assets: Sequence[FileSelectEntry] = context.selected_asset_files

        for asset in assets:
            asset_path: Path = library_path / Path(asset.relative_path)
            bpy.ops.wm.append(filename=str(asset_path), link=True)

        return {'FINISHED'}


classes = ( 
    BDK_OT_ImportDataLinked,
)
