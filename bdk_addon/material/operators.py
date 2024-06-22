from bpy.types import Operator, Context
from bpy.props import StringProperty

from ..helpers import load_bdk_material


# This is a wrapper for linking a material
class BDK_OT_link_material(Operator):
    bl_idname = 'bdk.link_material'
    bl_label = 'Load Material'
    bl_options = {'REGISTER', 'INTERNAL'}

    reference: StringProperty()
    repository_id: StringProperty()

    def execute(self, context: Context):
        print(f'Linking material with repository ID {self.repository_id} and reference {self.reference}')
        material = load_bdk_material(self.reference, self.repository_id)
        if material is None:
            return {'CANCELLED'}
        return {'FINISHED'}


classes = (
    BDK_OT_link_material,
)
