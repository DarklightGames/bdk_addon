from bpy.types import Operator, Context
from bpy.props import StringProperty

from ..helpers import load_bdk_material


# This is a wrapper for linking a material
class BDK_OT_LinkMaterial(Operator):
    bl_idname = 'bdk.link_material'
    bl_label = 'Load Material'
    bl_options = {'REGISTER', 'INTERNAL'}

    reference: StringProperty()

    def execute(self, context: Context):
        material = load_bdk_material(self.reference)
        if material is None:
            return {'CANCELLED'}
        return {'FINISHED'}


classes = (
    BDK_OT_LinkMaterial,
)
