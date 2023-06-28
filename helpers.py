import os
import re
import bpy
from typing import Iterable, Optional, Dict, Tuple, AbstractSet
from bpy.types import Material, Object, Context, Mesh, NodeTree, NodeSocket
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
    return 'bdk.reference' in material.keys()


def is_bdk_actor(obj: Object) -> bool:
    return 'Class' in obj.keys()


def is_bdk_static_mesh_actor(obj: Object) -> bool:
    return is_bdk_actor(obj) and obj.type == 'MESH' and obj['Class'] == 'StaticMeshActor'


def get_terrain_info(terrain_info_object: Object):
    if terrain_info_object.bdk.type == 'TERRAIN_INFO':
        return terrain_info_object.bdk.terrain_info
    return None


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
def copy_simple_property_group(source, target):
    if not hasattr(source, "__annotations__"):
        return
    for prop_name in source.__annotations__.keys():
        try:
            setattr(target, prop_name, getattr(source, prop_name))
        except (AttributeError, TypeError):
            pass


def should_show_bdk_developer_extras(context: Context):
    return getattr(context.preferences.addons['bdk_addon'].preferences, 'developer_extras', False)


def add_operation_switch_nodes(
        node_tree: NodeTree,
        operation_socket: NodeSocket,
        value_1_socket: Optional[NodeSocket],
        value_2_socket: Optional[NodeSocket],
        operations: Iterable[str]
) -> NodeSocket:

    last_output_node_socket: Optional[NodeSocket] = None

    for index, operation in enumerate(operations):
        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'
        compare_node.inputs[3].default_value = index
        node_tree.links.new(operation_socket, compare_node.inputs[2])

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])

        math_node = node_tree.nodes.new(type='ShaderNodeMath')
        math_node.operation = operation
        math_node.inputs[0].default_value = 0.0
        math_node.inputs[1].default_value = 0.0

        if value_1_socket:
            node_tree.links.new(value_1_socket, math_node.inputs[0])

        if value_2_socket:
            node_tree.links.new(value_2_socket, math_node.inputs[1])

        node_tree.links.new(math_node.outputs['Value'], switch_node.inputs['True'])

        if last_output_node_socket:
            node_tree.links.new(last_output_node_socket, switch_node.inputs['False'])

        last_output_node_socket = switch_node.outputs[0]  # Output

    return last_output_node_socket


def add_interpolation_type_switch_nodes(
        node_tree: NodeTree,
        interpolation_type_socket: NodeSocket,
        value_socket: NodeSocket,
        interpolation_types: Iterable[str]
) -> NodeSocket:

    last_output_node_socket: Optional[NodeSocket] = None

    for index, interpolation_type in enumerate(interpolation_types):
        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'
        compare_node.inputs[3].default_value = index
        node_tree.links.new(interpolation_type_socket, compare_node.inputs[2])

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])

        map_range_node = node_tree.nodes.new(type='ShaderNodeMapRange')
        map_range_node.data_type = 'FLOAT'
        map_range_node.interpolation_type = interpolation_type
        map_range_node.inputs[3].default_value = 1.0  # To Min
        map_range_node.inputs[4].default_value = 0.0  # To Max

        node_tree.links.new(value_socket, map_range_node.inputs[0])
        node_tree.links.new(map_range_node.outputs[0], switch_node.inputs['True'])

        if last_output_node_socket:
            node_tree.links.new(last_output_node_socket, switch_node.inputs['False'])

        last_output_node_socket = switch_node.outputs[0]  # Output

    return last_output_node_socket


def add_noise_type_switch_nodes(
        node_tree: NodeTree,
        vector_socket: NodeSocket,
        noise_type_socket: NodeSocket,
        noise_distortion_socket: NodeSocket,
        noise_types: Iterable[str]
) -> NodeSocket:

    last_output_node_socket: Optional[NodeSocket] = None

    for index, noise_type in enumerate(noise_types):
        compare_node = node_tree.nodes.new(type='FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'
        compare_node.inputs[3].default_value = index
        node_tree.links.new(noise_type_socket, compare_node.inputs[2])

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        node_tree.links.new(compare_node.outputs['Result'], switch_node.inputs['Switch'])

        noise_value_socket = None

        if noise_type == 'PERLIN':
            noise_node = node_tree.nodes.new(type='ShaderNodeTexNoise')
            noise_node.noise_dimensions = '2D'
            noise_node.inputs['Scale'].default_value = 0.5
            noise_node.inputs['Detail'].default_value = 16
            noise_node.inputs['Distortion'].default_value = 0.5

            node_tree.links.new(noise_distortion_socket, noise_node.inputs['Distortion'])
            node_tree.links.new(vector_socket, noise_node.inputs['Vector'])
            noise_value_socket = noise_node.outputs['Fac']
        elif noise_type == 'WHITE':
            noise_node = node_tree.nodes.new(type='ShaderNodeTexWhiteNoise')
            noise_node.noise_dimensions = '2D'
            noise_value_socket = noise_node.outputs['Value']

        node_tree.links.new(noise_value_socket, switch_node.inputs['True'])

        if last_output_node_socket:
            node_tree.links.new(last_output_node_socket, switch_node.inputs['False'])

        last_output_node_socket = switch_node.outputs[0]  # Output

    return last_output_node_socket


def ensure_node_tree_inputs_and_outputs(node_group_id: str, inputs: AbstractSet[Tuple[str, str]], output_names: AbstractSet[Tuple[str, str]]) -> NodeTree:
    if node_group_id in bpy.data.node_groups:
        node_tree = bpy.data.node_groups[node_group_id]
    else:
        node_tree = bpy.data.node_groups.new(name=node_group_id, type='GeometryNodeTree')

    # Compare the inputs and outputs of the node tree with the given inputs and outputs.
    # If they are different, clear the inputs and outputs and add the new ones.
    node_tree_inputs = set(map(lambda x: (x.type, x.name), node_tree.inputs))
    node_tree_outputs = set(map(lambda x: (x.type, x.name), node_tree.outputs))

    # For inputs that do not exist in the node tree, add them.
    for input_type, input_name in inputs - node_tree_inputs:
        node_tree.inputs.new(input_type, input_name)

    # For inputs that exist in the node tree but not in the given inputs, remove them.
    for input_type, input_name in node_tree_inputs - inputs:
        node_tree.inputs.remove(node_tree.inputs[input_name])

    # For outputs that do not exist in the node tree, add them.
    for output_type, output_name in output_names - node_tree_outputs:
        node_tree.outputs.new(output_type, output_name)

    # For outputs that exist in the node tree but not in the given outputs, remove them.
    for output_type, output_name in node_tree_outputs - output_names:
        node_tree.outputs.remove(node_tree.outputs[output_name])

    return node_tree
