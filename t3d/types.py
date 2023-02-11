from bpy.types import Panel, Context, PropertyGroup
from bpy.props import FloatProperty, FloatVectorProperty


class BDK_PG_SurfacePropertyGroup(PropertyGroup):
    scale: FloatVectorProperty(name='Scale', size=2)
    offset: FloatVectorProperty(name='Offset', size=2)
    rotation: FloatProperty(name='Rotation', subtype='ANGLE')


class BDK_PT_SurfacePropertiesPanel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_label = 'Surface Properties'

    @classmethod
    def poll(cls, context: Context):
        return context and context.mode == 'EDIT_MESH'

    def draw(self, context: Context):
        pass


classes = (
    BDK_PG_SurfacePropertyGroup,
    BDK_PT_SurfacePropertiesPanel,
)

# use_restrict_tag=%b
