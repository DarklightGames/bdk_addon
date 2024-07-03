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
        return context.material is not None and context.material.bdk.package_reference != ''

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        bdk = context.material.bdk
        layout.prop(bdk, 'package_reference')
        layout.prop(bdk, 'size_x')
        layout.prop(bdk, 'size_y')


classes = (
    BDK_PT_material,
)
