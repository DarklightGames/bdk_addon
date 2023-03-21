from bpy.types import Panel
from ..t3d.operators import BDK_OT_CopyObject, BDK_OT_T3DImportFromClipboard


class BDK_PT_Panel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_label = 'BDK'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator(BDK_OT_CopyObject.bl_idname, icon='COPYDOWN', text=f'Copy Object(s)')
        layout.operator(BDK_OT_T3DImportFromClipboard.bl_idname, icon='PASTEDOWN')


class BDK_PT_SceneInfoPanel(Panel):
    bl_label = "BDK Properties"
    bl_idname = "SCENE_PT_layout"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"

    def draw(self, context: 'Context'):
        layout = self.layout
        layout.prop(getattr(context.scene, 'bdk_info'), 'my_level_package_name')


classes = (
    BDK_PT_Panel,
    BDK_PT_SceneInfoPanel,
)
