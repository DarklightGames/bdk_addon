import os
import re
import bpy
from typing import Iterable, Optional, Dict, List, Tuple

import numpy
from bpy.types import Material, Object, Context, Mesh, Attribute, ByteColorAttribute
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


def get_bdk_asset_library_paths() -> List[Path]:
    asset_library_paths = []
    asset_libraries = bpy.context.preferences.filepaths.asset_libraries
    # TODO: this is very janky; come up with a better way to handle the BDK asset libraries.
    asset_library_name = 'BDK Library'
    for asset_library in asset_libraries:
        if asset_library.name.startswith(asset_library_name):
            asset_library_paths.append(Path(asset_library.path))
    return asset_library_paths


def get_blend_file_for_package(package_name: str) -> Optional[str]:
    asset_library_paths = get_bdk_asset_library_paths()
    for asset_library_path in asset_library_paths:
        blend_files = [fp for fp in asset_library_path.glob(f'**/{package_name}.blend') if fp.is_file()]
        if len(blend_files) > 0:
            return str(blend_files[0])
    return None


def guess_package_reference_from_names(names: Iterable[str]) -> Dict[str, Optional[UReference]]:
    """
    Guesses a package reference from a name. Returns None if no reference could be guessed.
    :param names:
    :return:
    """
    # Iterate through all the libraries in the asset library and try to find a match.
    asset_library_paths = get_bdk_asset_library_paths()
    name_references = dict()

    if not asset_library_paths:
        return name_references

    for asset_library_path in asset_library_paths:
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
    # TODO: this doesn't work for inherited annotations
    for prop_name in source.__annotations__.keys():
        if prop_name in ignore:
            continue
        try:
            setattr(target, prop_name, getattr(source, prop_name))
        except (AttributeError, TypeError):
            pass


def should_show_bdk_developer_extras(context: Context):
    return getattr(context.preferences.addons['bdk_addon'].preferences, 'developer_extras', False)


# TODO: maybe put all these attribute functions in their own file?

def fill_byte_color_attribute_data(attribute: ByteColorAttribute, color: Tuple[float, float, float, float]):
    vertex_count = len(attribute.data)
    color_data = numpy.ndarray(shape=(vertex_count, 4), dtype=float)
    color_data[:] = color
    attribute.data.foreach_set('color', color_data.flatten())  # TODO: Might be possible to do this with .flat to avoid the copy


def invert_byte_color_attribute_data(attribute: ByteColorAttribute):
    vertex_count = len(attribute.data)
    color_data = [0.0] * vertex_count * 4
    attribute.data.foreach_get('color', color_data)
    color_data = numpy.array(color_data)
    color_data.resize((vertex_count, 4))
    color_data[:, 0:3] = 1.0 - color_data[:, 0:3]
    attribute.data.foreach_set('color', color_data.flatten())


def accumulate_byte_color_attribute_data(attribute: ByteColorAttribute, other_attribute: ByteColorAttribute):
    """
    Accumulates the color data of two paint nodes and stores the result in the first paint node.
    :param attribute:
    :param other_attribute:
    """
    vertex_count = len(attribute.data)
    other_vertex_count = len(other_attribute.data)
    if vertex_count != other_vertex_count:
        raise RuntimeError(
            f'Vertex count mismatch between paint nodes ({attribute.name} has {vertex_count} vertices, {other_attribute.name} has {other_vertex_count} vertices)')
    color_data = [0.0] * vertex_count * 4
    attribute.data.foreach_get('color', color_data)
    color_data = numpy.array(color_data)
    color_data.resize((vertex_count, 4))
    other_color_data = [0.0] * vertex_count * 4
    other_attribute.data.foreach_get('color', other_color_data)
    other_color_data = numpy.array(other_color_data)
    other_color_data.resize((vertex_count, 4))
    color_data[:, 0:3] = numpy.clip(color_data[:, 0:3] + other_color_data[:, 0:3], 0.0, 1.0)
    attribute.data.foreach_set('color', color_data.flatten())


def padded_roll(array, shift):
    """
    Pad the array with zeros in the direction of the shift, then roll the array and remove the padding.

    For our purposes, the padding preserves the relationships between the terrain vertices and quad-level data (i.e.
    holes & edge turns) as those quad-level data cross and wrap around the edges of the terrain during a shift.

    :param array:
    :param shift:
    :return:
    """
    x = shift[0]
    y = shift[1]
    pad_x_sign = -1 if x < 0 else 1
    pad_y_sign = -1 if y < 0 else 1
    pad_x_negative = 1 if x < 0 else 0
    pad_x_positive = 1 if x >= 0 else 0
    pad_y_negative = 1 if y < 0 else 0
    pad_y_positive = 1 if y >= 0 else 0
    pad_width = (
        (pad_x_negative, pad_x_positive),
        (pad_y_negative, pad_y_positive)
    )
    array = numpy.pad(array, pad_width)
    array = numpy.roll(array, shift, (1, 0))

    x_start = 1 if pad_x_sign == -1 else 0
    x_end = None if pad_x_sign == -1 else -1
    y_start = 1 if pad_y_sign == -1 else 0
    y_end = None if pad_y_sign == -1 else -1

    array = array[x_start:x_end, y_start:y_end]

    return array
