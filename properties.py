from bpy.types import PropertyGroup
from bpy.props import PointerProperty, EnumProperty
from .terrain.properties import BDK_PG_TerrainInfoPropertyGroup
from .terrain.objects.properties import BDK_PG_terrain_object


class BDK_PG_object(PropertyGroup):
    """
    This property group is a container for all the different types of BDK property groups.
    """
    type: EnumProperty(name='Type',
                       items=(
                           ('NONE', 'None', ''),
                           ('TERRAIN_INFO', 'Terrain Info', ''),
                           ('TERRAIN_OBJECT', 'Terrain Object', ''),
                       ),
                       default='NONE'
                       )
    terrain_info: PointerProperty(type=BDK_PG_TerrainInfoPropertyGroup)
    terrain_object: PointerProperty(type=BDK_PG_terrain_object)


classes = (
    BDK_PG_object,
)
