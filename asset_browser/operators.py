import bpy
from bpy.types import Operator, FileSelectEntry, Context, bpy_prop_collection, UserAssetLibrary
from pathlib import Path
from typing import Set, Sequence, Optional


class BDK_OT_asset_import_data_linked(Operator):
    bl_idname = 'bdk_asset_browser.import_data_linked'
    bl_description = 'Link asset from a library'
    bl_label = 'Import Data (Linked)'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context: 'Context'):
        # TODO: only allow for materials.
        if context.mode != 'OBJECT':
            cls.poll_message_set('Must be in object mode.')
            return False
        assets: Sequence[FileSelectEntry] = context.selected_assets
        if len(assets) == 0:
            cls.poll_message_set('No assets selected.')
            return False
        if any(map(lambda asset: asset.id_type != 'MATERIAL', assets)):
            cls.poll_message_set('Only materials can be imported.')
            return False
        return True

    def execute(self, context: Context) -> Set[str]:
        library_path: Path
        asset_libraries: bpy_prop_collection[UserAssetLibrary] = context.preferences.filepaths.asset_libraries
        assets: Sequence[FileSelectEntry] = context.selected_assets

        linked_count = 0
        skipped_count = 0

        for asset in assets:
            full_library_path = bpy.types.AssetHandle.get_full_library_path(asset)

            if full_library_path == '':
                # Asset is local.
                skipped_count += 1
                continue

            # Find the asset library that contains the asset.
            library_path: Optional[Path] = None
            for asset_library in asset_libraries:
                if full_library_path.startswith(str(asset_library.path)):
                    library_path = asset_library.path
                    break

            if library_path is None:
                self.report({'ERROR'}, f'Could not find asset library for {asset.name}')
                return {'CANCELLED'}

            asset_path: Path = library_path / Path(asset.relative_path)

            bpy.ops.wm.append(filename=str(asset_path), link=True, instance_object_data=False, instance_collections=False)

            linked_count += 1

        self.report({'INFO'}, f'Linked {linked_count} | Skipped {skipped_count}')

        return {'FINISHED'}


classes = (
    BDK_OT_asset_import_data_linked,
)
