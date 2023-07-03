from bpy.types import PropertyGroup
from bpy.props import PointerProperty, EnumProperty, StringProperty
from ..terrain.properties import BDK_PG_terrain_info
from ..terrain.doodad.properties import BDK_PG_terrain_doodad


class BDK_PG_object(PropertyGroup):
    """
    This property group is a container for all the different types of BDK property groups.
    """
    type: EnumProperty(name='Type',
                       items=(
                           ('NONE', 'None', ''),
                           ('TERRAIN_INFO', 'Terrain Info', ''),
                           ('TERRAIN_DOODAD', 'Terrain Doodad', ''),
                       ),
                       default='NONE')
    terrain_info: PointerProperty(type=BDK_PG_terrain_info)
    terrain_doodad: PointerProperty(type=BDK_PG_terrain_doodad)
    package_reference: StringProperty(name='Package Reference', options={'HIDDEN'})


class BDK_PG_material(PropertyGroup):
    package_reference: StringProperty(name='Package Reference', options={'HIDDEN'})


classes = (
    BDK_PG_object,
    BDK_PG_material,
)
