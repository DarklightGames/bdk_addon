from bpy.types import Panel, Context


class BDK_PT_material(Panel):
    bl_idname = 'BDK_PT_material'
    bl_label = 'BDK'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'
    bl_order = 100

    @classmethod
    def poll(cls, context: Context):
        return context.material is not None and hasattr(context.material, 'bdk') and context.material.bdk.package_reference is not None

    def draw(self, context):
        self.layout.label(text=context.material.bdk.package_reference)


classes = (
    BDK_PT_material,
)
