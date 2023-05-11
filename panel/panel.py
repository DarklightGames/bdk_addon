from bpy.types import Panel
from ..t3d.operators import BDK_OT_t3d_copy_to_clipboard, BDK_OT_t3d_import_from_clipboard


class BDK_PT_clipboard(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_label = 'Clipboard'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator(BDK_OT_t3d_copy_to_clipboard.bl_idname, icon='COPYDOWN', text=f'Copy Object(s)')
        layout.operator(BDK_OT_t3d_import_from_clipboard.bl_idname, icon='PASTEDOWN')


classes = (
    BDK_PT_clipboard,
)
