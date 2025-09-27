from mathutils import Matrix

from .data import UReference
from bpy.types import Material, Object, Context, ByteColorAttribute, ViewLayer, LayerCollection, Collection, Mesh
from pathlib import Path
from typing import Iterable, Optional, Tuple, Set, List, cast as typing_cast
import bpy
import numpy
import re


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


def sanitize_name_for_unreal(name: str) -> str:
    # Remove trailing and leading whitespace.
    name = name.strip()
    # Replace spaces with underscores.
    name = name.replace(' ', '_')
    # Replace periods with underscores.
    name = name.replace('.', '_')
    return name


def is_bdk_material(material: Material) -> bool:
    # TOD: don't use custom properties for this, use a property group instead.
    return material.bdk.package_reference != ''


def is_bdk_actor(obj: Object) -> bool:
    return 'Class' in obj.keys()


def is_bdk_static_mesh_actor(obj: Object) -> bool:
    return is_bdk_actor(obj) and obj.type == 'MESH' and obj['Class'] == 'StaticMeshActor'


def get_terrain_info(terrain_info_object: Object):
    if terrain_info_object is not None and terrain_info_object.bdk.type == 'TERRAIN_INFO':
        return terrain_info_object.bdk.terrain_info
    return None


def get_terrain_doodad(terrain_doodad_object: Object):
    if terrain_doodad_object is not None and terrain_doodad_object.bdk.type == 'TERRAIN_DOODAD':
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


def is_active_object_bdk_object(context: Context):
    if context.active_object is None:
        return False
    return context.active_object.bdk.type != 'NONE'


def are_any_selected_objects_bdk_objects(context: Context):
    for obj in context.selected_objects:
        if obj.bdk.type != 'NONE':
            return True
    return False


def is_repository_id_valid(context: Context, repository_id: str) -> bool:
    addon_prefs = get_addon_preferences(context)
    for repository in addon_prefs.repositories:
        if repository.id == repository_id:
            return True
    return False


def get_repository_index_by_id(context: Context, repository_id: str) -> Optional[int]:
    addon_prefs = get_addon_preferences(context)
    for i, repository in enumerate(addon_prefs.repositories):
        if repository.id == repository_id:
            return i
    return None


def get_repository_by_id(context: Context, repository_id: str) -> Optional['BDK_PG_repository']:
    addon_prefs = get_addon_preferences(context)
    for repository in addon_prefs.repositories:
        if repository.id == repository_id:
            return repository
    return None


def get_blend_file_for_package(context: Context, package_name: str, repository_id: Optional[str] = None) -> Optional[str]:
    from .bdk.repository.kernel import get_repository_cache_directory
    if repository_id is None:
        repository_id = get_active_repository_id(context)
    repository = get_repository_by_id(context, repository_id)
    if repository is None:
        return None
    asset_library_path = get_repository_cache_directory(repository) / 'assets'
    blend_files = [fp for fp in asset_library_path.glob(f'**/{package_name}.blend') if fp.is_file()]
    if len(blend_files) > 0:
        return str(blend_files[0])
    return None


def get_addon_preferences(context: Context):
    """
    Get the preferences for the BDK addon.
    """
    from .bdk.preferences import BdkAddonPreferences
    addon_prefs = context.preferences.addons[BdkAddonPreferences.bl_idname].preferences
    return addon_prefs


def get_active_repository_id(context: Context) -> Optional[str]:
    """
    Get the active repository ID from the scene, or the default repository ID from the addon preferences if the scene
    repository ID is not set or invalid.
    """
    repository_id = None
    addon_prefs = get_addon_preferences(context)

    if is_repository_id_valid(context, context.scene.bdk.repository_id):
        repository_id = context.scene.bdk.repository_id
    elif is_repository_id_valid(context, addon_prefs.default_repository_id):
        repository_id = addon_prefs.default_repository_id

    return repository_id


def get_active_repository(context: Context) -> Optional['BDK_PG_repository']:
    repository_id = get_active_repository_id(context)
    return get_repository_by_id(context, repository_id)


def load_bdk_material(context: Context, reference: str, repository_id: Optional[str] = None) -> Optional[Material]:
    """
    Loads a material from a BDK repository.
    :param context: The Blender context.
    :param reference: The reference to the material.
    :param repository_id: The ID of the repository to load the material from. If None, the repository ID from the scene.
    """
    reference = UReference.from_string(reference)

    if reference is None:
        return None

    # Strip the group name (useless for materials).
    reference.group_name = None

    if reference.package_name == 'myLevel':
        # The second argument is a library, which we pass as None to get the local material.
        # https://blender.stackexchange.com/questions/238342/how-to-recognize-local-and-linked-material-with-python
        material = bpy.data.materials.get((reference.object_name, None), None)
    else:
        # See if we already have the material linked from elsewhere.
        material = bpy.data.materials.get(reference.object_name, None)
        if material is not None:
            # Make sure the material reference matches the package reference.
            # TODO: for some reason I can't remember, the full reference is not passed in here (the class type is missing).
            #  Which is why we only check the package name and object name.
            material_package_reference = UReference.from_string(material.bdk.package_reference)
            if material_package_reference.package_name == reference.package_name and material_package_reference.object_name == reference.object_name:
                return material
        # TODO: There is a bug here where if you linked a material with the same name as another package, depending on the
        #  order it may try to load the "wrong" one, then it will always go and fetch the linked material instead of the
        #  local one. Not the end of the world, but it makes things slightly slower.
        #  A strategy here would be to traverse all the materials and check if the package reference matches, then return
        #  that material if it does. Traversing all the materials is still faster than trying to load from a file.

    if material is not None and material.bdk.package_reference == str(reference):
        return material

    if repository_id is None:
        repository_id = get_active_repository_id(context)

    blend_file = get_blend_file_for_package(context, reference.package_name, repository_id)

    if blend_file is None:
        print('Failed to find blend file for package reference: ' + reference.package_name)
        return None

    print(f'Loading material {reference} from blend file: {blend_file}')

    blend_file = Path(blend_file).resolve().absolute()

    with bpy.data.libraries.load(str(blend_file), link=True, relative=True, assets_only=True) as (data_in, data_out):
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
def load_bdk_static_mesh(context: Context, reference: str, repository_id: Optional[str] = None) -> Optional[Collection]:
    reference = UReference.from_string(reference)

    if reference is None:
        return None

    if reference.package_name == 'myLevel':
        # Failed to find object in myLevel package. (handle reporting this error downstream)
        return bpy.data.collections.get(reference.object_name, None)

    # TODO: we need to check if the collection is already linked into the scene (make sure the package reference matches as well!)
    # This will dramatically improve the performance of this because it won't need to do any File I/O.

    # Strip the group name since we don't use it in the BDK library files.
    reference.group_name = None

    blend_file = get_blend_file_for_package(context, reference.package_name, repository_id)

    if blend_file is None:
        return None

    blend_file = Path(blend_file).resolve().absolute()

    with bpy.data.libraries.load(str(blend_file), link=True, relative=True, assets_only=False) as (data_in, data_out):
        if reference.object_name in data_in.collections:
            data_out.collections = [reference.object_name]
        else:
            return None

    collection = bpy.data.collections[reference.object_name]

    return collection


# https://blenderartists.org/t/duplicating-pointerproperty-propertygroup-and-collectionproperty/1419096/2
def copy_simple_property_group(source, target, ignore: Optional[Set[str]] = None):
    if ignore is None:
        ignore = set()
    if not hasattr(source, "__annotations__"):
        return
    # TODO: this doesn't work for inherited annotations or PointerProperty types.
    #  Top have this work, we'll need to inspect the type of the property. If it's a PointerProperty, drill into it
    #  and copy all the properties to the target.
    for prop_name in source.__annotations__.keys():
        if prop_name in ignore:
            continue
        try:
            setattr(target, prop_name, getattr(source, prop_name))
        except (AttributeError, TypeError):
            pass


def should_show_bdk_developer_extras(context: Context):
    addon_prefs = get_addon_preferences(context)
    return getattr(addon_prefs, 'developer_extras', False)


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

def dfs_collection_objects(
        collection: Collection,
        visited: Set[Tuple[Object, Optional[Object]]],
        instance_objects: Optional[List[Object]] = None,
        matrix_world: Matrix = Matrix.Identity(4)
        ):
    # TODO: We want to also yield the top-level instance object so that callers can inspect the selection status etc.
    if instance_objects is None:
        instance_objects = list()

    # Sort the objects in the collection to return non-BSP brushes first.
    # Next, return the BSP brushes in ascending order of their sort order.
    collection_objects = list(collection.objects)
    collection_objects.sort(
        key=lambda obj: (obj.bdk.type != 'BSP_BRUSH', obj.bdk.bsp_brush.sort_order if obj.bdk.type == 'BSP_BRUSH' else 0))

    for obj in collection_objects:
        if obj.parent is None or obj.parent not in set(collection.objects) and obj not in visited:
            # If this an instance, we need to recurse into it.
            if obj.instance_collection is not None:
                # Calculate the instance transform.
                instance_offset_matrix = Matrix.Translation(-obj.instance_collection.instance_offset)
                # Recurse into the instance collection.
                yield from dfs_collection_objects(
                    collection=obj.instance_collection,
                    visited=visited,
                    instance_objects=instance_objects + [obj],
                    matrix_world=matrix_world @ (obj.matrix_local @ instance_offset_matrix)
                    )
            else:
                yield (obj, instance_objects, matrix_world @ obj.matrix_local)
                visited.add((obj, instance_objects[0] if instance_objects else None))
                # `children_recursive` returns objects regardless of collection, so we need to make sure
                # that the children are in this collection.
                # TODO: this needs to be changed so that we walk the hierarchy. this may have instances inside.
                #  Also, the obj.matrix_local is only relevant for direct descendants of `obj`.
                for child_obj in obj.children_recursive:
                    if child_obj not in visited and child_obj in set(collection.objects):
                        yield (child_obj, instance_objects, matrix_world @ obj.matrix_local @ child_obj.matrix_local)
                        visited.add((child_obj, instance_objects[0] if instance_objects else None))


def dfs_view_layer_objects(view_layer: ViewLayer) -> Iterable[Tuple[Object, List[Object], Matrix]]:
    """
    A BDK-specific depth-first iterator of objects in a view layer meant to provide a means
    for level authors to create and maintain stable CSG brush ordering.
    * Collections are evaluated recursively.
    * Object ordering respects object hierarchy (i.e., the parent object will be returned first, then all children,
    recursively).
    Note that all sibling objects within a hierarchy level will be returned in an unpredictable order.
    """
    visited: Set[Tuple[Object, Optional[Object]]] = set()

    # TODO: Handle instance collections.
    # In order to do this, we will need to also output the instance in the iterator. It is then the responsibility of
    # the caller to handle the tuple of object and instance.
    # TODO: How to handle nested instances? (create a hierarchy of instances; just a flat list?)
    # TODO: Make a function that takes an object and a list of (parent) asset objects and returns the world matrix.

    def layer_collection_objects_recursive(layer_collection: LayerCollection):
        for child in layer_collection.children:
            yield from layer_collection_objects_recursive(child)
        # Iterate only the top-level objects in this collection first.
        yield from dfs_collection_objects(layer_collection.collection, visited)

    yield from layer_collection_objects_recursive(view_layer.layer_collection)


def tag_redraw_all_windows(context):
    for region in filter(lambda r: r.type == 'WINDOW', context.area.regions):
        region.tag_redraw()


def humanize_size(bytes: int):
    """
    Convert a byte count to a human-readable size string.
    """
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']:
        if bytes < 1024.0:
            break
        bytes /= 1024.0
    # Don't show decimal places for whole numbers.
    if isinstance(bytes, int):
        return f"{int(bytes)} {unit}"
    else:
        return f"{bytes:.2f} {unit}"


def humanize_time(seconds: float):
    """
    Convert a time duration in seconds to a human-readable time string (from nanoseconds to hours).
    """
    if seconds < 1e-6:
        return f"{seconds * 1e9:.2f} ns"
    elif seconds < 1e-3:
        return f"{seconds * 1e6:.2f} µs"
    elif seconds < 1:
        return f"{seconds * 1e3:.2f} ms"
    elif seconds < 60:
        return f"{seconds:.2f} s"
    elif seconds < 3600:
        # Minutes and seconds.
        minutes = int(seconds // 60)
        seconds = seconds % 60
        return f"{minutes}m {seconds:.2f}s"
    else:
        # Hours, minutes, and seconds.
        hours = int(seconds // 3600)
        seconds = seconds % 3600
        minutes = int(seconds // 60)
        seconds = seconds % 60
        return f"{hours}h {minutes}m {seconds:.2f}s"


def get_vertex_group_weights(obj: Object, vertex_group_name: str):
    vertex_group = obj.vertex_groups.get(vertex_group_name)
    assert vertex_group
    mesh_data = typing_cast(Mesh, obj.data)
    weights = numpy.zeros(len(mesh_data.vertices), dtype=float)
    # TODO: This is MASSIVELY inefficient but as far as I can tell there's no way to just dump out
    #  a nice flat list of indexed vertex weights.
    for i in range(len(mesh_data.vertices)):
        try:
            weights[i] = vertex_group.weight(i)
        except RuntimeError:
            continue
    return vertex_group, weights
