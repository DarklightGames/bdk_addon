from bpy.types import PropertyGroup, Object
from bpy.props import PointerProperty, EnumProperty, StringProperty, IntProperty, CollectionProperty

from ..fluid_surface.properties import BDK_PG_fluid_surface
from ..terrain.properties import BDK_PG_terrain_info
from ..terrain.doodad.properties import BDK_PG_terrain_doodad
from ..bsp.properties import BDK_PG_bsp_brush, BDK_PG_level


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
                           ('FLUID_SURFACE', 'Fluid Surface', ''),
                           ('LEVEL', 'Level', ''),
                       ),
                       default='NONE')
    terrain_info: PointerProperty(type=BDK_PG_terrain_info)
    terrain_doodad: PointerProperty(type=BDK_PG_terrain_doodad)
    bsp_brush: PointerProperty(type=BDK_PG_bsp_brush)
    fluid_surface: PointerProperty(type=BDK_PG_fluid_surface)
    level: PointerProperty(type=BDK_PG_level)
    package_reference: StringProperty(name='Package Reference', options={'HIDDEN'})


class BDK_PG_material(PropertyGroup):
    package_reference: StringProperty(name='Package Reference', options={'HIDDEN'})
    size_x: IntProperty(name='Size X', default=512, min=1)
    size_y: IntProperty(name='Size Y', default=512, min=1)


class BDK_PG_node_tree(PropertyGroup):
    build_hash: StringProperty(name='Build Function Byte-Code Hash',
                               options={'HIDDEN'},
                               description='Python byte-code hash for the function that built this node tree. Used to '
                                           'trigger rebuilds when build functions change')


class BDK_PG_terrain_doodad_preset(PropertyGroup):
    id: StringProperty(name='ID', default='')
    name: StringProperty(name='Name', default='Terrain Doodad')
    settings: PointerProperty(type=BDK_PG_terrain_doodad)


class BDK_PG_scene(PropertyGroup):
    level_object: PointerProperty(type=Object, poll=lambda self, obj: obj.bdk.type == 'LEVEL', name='Level Object',
                                  description='The mesh object to use for the level geometry')
    repository_id: StringProperty(name='Repository ID', default='')
    terrain_doodad_presets: CollectionProperty(name='Terrain Doodad Presets', type=BDK_PG_terrain_doodad_preset)
    terrain_doodad_presets_index: IntProperty(options={'HIDDEN'})


classes = (
    BDK_PG_object,
    BDK_PG_material,
    BDK_PG_node_tree,
    BDK_PG_terrain_doodad_preset,
    BDK_PG_scene,
)
