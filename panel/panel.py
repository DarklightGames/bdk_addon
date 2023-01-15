from bpy.types import Panel
from ..t3d.operators import BDK_OP_CopyObject


class BDK_PT_Panel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_label = 'BDK'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator(BDK_OP_CopyObject.bl_idname, icon='COPYDOWN', text=f'Copy Object(s)')


classes = (
    BDK_PT_Panel,
)