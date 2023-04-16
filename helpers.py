import re
import bpy
from typing import Iterable, Optional
from bpy.types import Material, Object, Context, Mesh
from pathlib import Path
from .data import UReference


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


def get_bdk_asset_library_path() -> Optional[Path]:
    asset_libraries = bpy.context.preferences.filepaths.asset_libraries
    asset_library_name = 'BDK Library'

    try:
        asset_library = next(filter(lambda x: x.name == asset_library_name, asset_libraries))
    except StopIteration:
        print(f'BDK asset library could not be found (expected to find library with name "{asset_library_name}")')
        return None

    return Path(asset_library.path)


def get_blend_file_for_package(package_name: str) -> Optional[str]:
    asset_library_path = get_bdk_asset_library_path()

    if asset_library_path is None:
        return None

    blend_files = [fp for fp in asset_library_path.glob(f'**/{package_name}.blend') if fp.is_file()]

    if len(blend_files) == 0:
        return None

    return str(blend_files[0])


def load_bdk_material(reference: str):
    reference = UReference.from_string(reference)
    if reference is None:
        return None

    if reference.package_name == 'myLevel':
        return bpy.data.materials[reference.object_name]

    blend_file = get_blend_file_for_package(reference.package_name)

    if blend_file is None:
        return None

    with bpy.data.libraries.load(blend_file, link=True, relative=False, assets_only=True) as (data_in, data_out):
        if reference.object_name in data_in.materials:
            data_out.materials = [reference.object_name]
        else:
            return None

    # TODO: there is (i think) a bug here if we try to load the same material multiple times;
    #  it's making loads of local materials for skin overrides for some reason.
    material = bpy.data.materials[reference.object_name]

    return material


# TODO: should actually do the object, not the mesh data
def load_bdk_static_mesh(reference: str) -> Optional[Mesh]:

    reference = UReference.from_string(reference)

    if reference is None:
        return None

    if reference.package_name == 'myLevel':
        if reference.object_name in bpy.data.objects:
            return bpy.data.objects[reference.object_name].data
        # Name look-up failed, sometimes the names can differ only by case, so manually check the names of each object
        for object in bpy.data.objects:
            if object.name.upper() == reference.object_name.upper():
                return bpy.data.objects[reference.object_name].data
        # Failed to find object in myLevel package. (handle reporting this errors downstream)
        return None

    # Strip the group name since we don't use it in the BDK library files.
    reference.group_name = None

    blend_file = get_blend_file_for_package(reference.package_name)

    if blend_file is None:
        return None

    with bpy.data.libraries.load(blend_file, link=True, relative=False, assets_only=False) as (data_in, data_out):
        if str(reference) in data_in.meshes:
            data_out.meshes = [str(reference)]
        else:
            return None

    mesh = bpy.data.meshes[str(reference)]

    return mesh
