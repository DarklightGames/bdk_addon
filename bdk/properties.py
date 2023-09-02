from bpy.types import PropertyGroup
from bpy.props import PointerProperty, EnumProperty, StringProperty, IntProperty
from ..terrain.properties import BDK_PG_terrain_info
from ..terrain.doodad.properties import BDK_PG_terrain_doodad
from ..bsp.properties import BDK_PG_bsp_brush


class BDK_PG_object(PropertyGroup):
    """
    This property group is a container for all the different types of BDK property groups.
    """
    type: EnumProperty(name='Type',
                       items=(
                           ('NONE', 'None', ''),
                           ('TERRAIN_INFO', 'Terrain Info', ''),
                           ('TERRAIN_DOODAD', 'Terrain Doodad', ''),
                           ('BSP_BRUSH', 'BSP Brush', ''),
                       ),
                       default='NONE')
    terrain_info: PointerProperty(type=BDK_PG_terrain_info)
    terrain_doodad: PointerProperty(type=BDK_PG_terrain_doodad)
    bsp_brush: PointerProperty(type=BDK_PG_bsp_brush)
    package_reference: StringProperty(name='Package Reference', options={'HIDDEN'})


class BDK_PG_material(PropertyGroup):
    package_reference: StringProperty(name='Package Reference', options={'HIDDEN'})
    size_x: IntProperty(name='Size X', default=512, min=1)
    size_y: IntProperty(name='Size Y', default=512, min=1)


classes = (
    BDK_PG_object,
    BDK_PG_material,
)
