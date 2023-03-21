from bpy.types import PropertyGroup
from bpy.props import StringProperty


class BDK_PG_SceneInfoPropertyGroup(PropertyGroup):
    my_level_package_name: StringProperty(name='myLevel Package Name')


classes = (
    BDK_PG_SceneInfoPropertyGroup,
)
