import re
from typing import Iterable
from bpy.types import Material, Object, Context


def auto_increment_name(name, names: Iterable[str]):
    while name in names:
        match = re.match(r'(.+)\.(\d+)', name)
        if match:
            name = match.group(1)
            number = int(match.group(2)) + 1
        else:
            number = 1
        name = f'{name}.{number:03d}'
    return name


def is_bdk_material(material: Material) -> bool:
    return 'bdk.reference' in material.keys()


def is_bdk_actor(obj: Object) -> bool:
    return 'Class' in obj.keys()


def is_bdk_static_mesh_actor(obj: Object) -> bool:
    return is_bdk_actor(obj) and obj.type == 'MESH' and obj['Class'] == 'StaticMeshActor'


def get_terrain_info(terrain_info_object: Object):
    terrain_info = getattr(terrain_info_object, 'terrain_info')
    if terrain_info is None or not terrain_info.is_terrain_info:
        raise RuntimeError('Invalid object for operation')
    return terrain_info


def is_active_object_terrain_info(context: Context):
    if context.active_object is None:
        return False
    return get_terrain_info(context.active_object) is not None
