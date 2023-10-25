import bpy
from bpy.types import Operator, Context
from pathlib import Path
from typing import Set


class BDK_OT_asset_import_data_linked(Operator):
    bl_idname = 'bdk_asset_browser.import_data_linked'
    bl_description = 'Link asset from a library'
    bl_label = 'Import Data (Linked)'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context: 'Context'):
        if context.mode != 'OBJECT':
            # TODO: why is this a requirement?
            cls.poll_message_set('Must be in object mode')
            return False
        assets = context.selected_assets
        if len(assets) == 0:
            cls.poll_message_set('No assets selected')
            return False
        if any(map(lambda asset: asset.id_type != 'MATERIAL', assets)):
            cls.poll_message_set('Only materials can be imported')
            return False
        return True

    def execute(self, context: Context) -> Set[str]:
        library_path: Path
        assets = context.selected_assets

        linked_count = 0
        skipped_count = 0

        for asset in assets:
            if asset.local_id is not None:
                # Asset is local to this file.
                skipped_count += 1
                continue

            bpy.ops.wm.append(filename=asset.full_path, link=True, instance_object_data=False, instance_collections=False)

            linked_count += 1

        self.report({'INFO'}, f'Linked {linked_count} | Skipped {skipped_count}')

        return {'FINISHED'}


classes = (
    BDK_OT_asset_import_data_linked,
)
