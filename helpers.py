import os
import re
import bpy
from typing import Iterable, Optional, Dict
from bpy.types import Material, Object, Context, Mesh
from pathlib import Path
from .data import UReference


def ensure_name_unique(name, names: Iterable[str]):
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
    # TOD: don't use custom properties for this, use a property group instead.
    return material.bdk.package_reference != ''


def is_bdk_actor(obj: Object) -> bool:
    return 'Class' in obj.keys()


def is_bdk_static_mesh_actor(obj: Object) -> bool:
    return is_bdk_actor(obj) and obj.type == 'MESH' and obj['Class'] == 'StaticMeshActor'


def get_terrain_info(terrain_info_object: Object):
    if terrain_info_object.bdk.type == 'TERRAIN_INFO':
        return terrain_info_object.bdk.terrain_info
    return None


def get_terrain_doodad(terrain_doodad_object: Object):
    if terrain_doodad_object.bdk.type == 'TERRAIN_DOODAD':
        return terrain_doodad_object.bdk.terrain_doodad
    return None


def is_active_object_terrain_info(context: Context):
    if context.active_object is None:
        return False
    return get_terrain_info(context.active_object) is not None


def is_active_object_terrain_doodad(context: Context):
    if context.active_object is None:
        return False
    return get_terrain_doodad(context.active_object) is not None


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


def guess_package_reference_from_names(names: Iterable[str]) -> Dict[str, Optional[UReference]]:
    """
    Guesses a package reference from a name. Returns None if no reference could be guessed.
    :param names:
    :return:
    """
    # Iterate through all the libraries in the asset library and try to find a match.
    asset_library_path = get_bdk_asset_library_path()
    name_references = dict()

    if asset_library_path is None:
        return name_references

    for blend_file in asset_library_path.glob('**/*.blend'):
        if not blend_file.is_file():
            continue
        package = os.path.splitext(os.path.basename(blend_file))[0]
        with bpy.data.libraries.load(str(blend_file), link=True, relative=False, assets_only=True) as (data_in, data_out):
            for name in set(data_in.materials).intersection(names):
                name_references[name] = UReference.from_string(f'Texture\'{package}.{name}\'')

    return name_references


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

    # The bug here is that NAMES are the same! You can have a material with the same name as another material, but
    #  only if one is linked and the other is local. So we need to check if the material is local or not.
    materials = [material for material in bpy.data.materials if material.name == reference.object_name]

    if len(materials) == 0:
        return None

    # If there are multiple materials with the same name, we need to find the one that is linked.
    # If there are no linked materials, we just return the first one.
    for material in materials:
        if material.library is not None:
            return material

    return materials[0]


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


def are_bdk_dependencies_installed() -> bool:
    try:
        import t3dpy
    except ModuleNotFoundError:
        return False
    return True


# https://blenderartists.org/t/duplicating-pointerproperty-propertygroup-and-collectionproperty/1419096/2
def copy_simple_property_group(source, target, ignore: Iterable[str] = set()):
    if not hasattr(source, "__annotations__"):
        return
    for prop_name in source.__annotations__.keys():
        if prop_name in ignore:
            continue
        try:
            setattr(target, prop_name, getattr(source, prop_name))
        except (AttributeError, TypeError):
            pass


def should_show_bdk_developer_extras(context: Context):
    return getattr(context.preferences.addons['bdk_addon'].preferences, 'developer_extras', False)
