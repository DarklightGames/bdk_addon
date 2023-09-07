import bpy
import uuid

from bpy.types import Object, NodeTree, Collection, NodeSocket, bpy_struct, ID
from typing import Optional, Iterable

from ..helpers import get_terrain_info
from ..node_helpers import add_operation_switch_nodes, ensure_input_and_output_nodes, ensure_geometry_node_tree, \
    ensure_terrain_layer_node_operation_node_tree


# TODO: this file needs to be renamed.


def add_terrain_deco_layer(terrain_info_object: Object, name: str = 'DecoLayer'):
    """
    Adds a deco layer to the terrain.
    This adds a new entry to the deco layers array in the terrain info and creates the associated deco layer object and
    mesh attributes.
    """
    terrain_info = get_terrain_info(terrain_info_object)

    # Create the deco layer object.
    deco_layer = terrain_info.deco_layers.add()
    deco_layer.name = name
    deco_layer.id = uuid.uuid4().hex
    deco_layer.modifier_name = uuid.uuid4().hex
    deco_layer.object = create_deco_layer_object(deco_layer)
    deco_layer.terrain_info_object = terrain_info_object

    # Link and parent the deco layer object to the terrain info object.
    collection: Collection = terrain_info_object.users_collection[0]
    collection.objects.link(deco_layer.object)
    deco_layer.object.parent = terrain_info_object

    return deco_layer


def add_terrain_deco_layer_node_driver(
        dataptr_index: int,
        node_index: int,
        terrain_info_object: Object,
        struct: bpy_struct,
        path: str,
        property_name: str,
        index: Optional[int] = None,
        invert: bool = False
):
    add_terrain_layer_node_driver('deco_layers', dataptr_index, node_index, terrain_info_object, struct, path, property_name, index, invert)


def add_terrain_layer_node_driver(
        dataptr_name: str,
        dataptr_index: int,
        node_index: int,
        terrain_info_object: Object,
        struct: bpy_struct,
        path: str,
        property_name: str,
        index: Optional[int] = None,
        invert: bool = False
):
    if index is None:
        fcurve = struct.driver_add(path)
    else:
        fcurve = struct.driver_add(path, index)

    if invert:
        fcurve.driver.type = 'SCRIPTED'
        fcurve.driver.expression = '1.0 - var'
    else:
        fcurve.driver.type = 'AVERAGE'

    variable = fcurve.driver.variables.new()
    variable.name = 'var'
    variable.type = 'SINGLE_PROP'
    target = variable.targets[0]
    target.id_type = 'OBJECT'
    target.id = terrain_info_object

    if index is not None:
        target.data_path = f'bdk.terrain_info.{dataptr_name}[{dataptr_index}].nodes[{node_index}].{property_name}[{index}]'
    else:
        target.data_path = f'bdk.terrain_info.{dataptr_name}[{dataptr_index}].nodes[{node_index}].{property_name}'


def ensure_terrain_layer_node_group(name: str, dataptr_name: str, dataptr_index: int, dataptr_id: str, nodes: Iterable) -> NodeTree:
    items = {('BOTH', 'NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(name, items)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    named_attribute_node.data_type = 'FLOAT_COLOR'
    named_attribute_node.inputs['Name'].default_value = dataptr_id

    add_node = node_tree.nodes.new('ShaderNodeMath')
    add_node.inputs[0].default_value = 0.0
    add_node.inputs[1].default_value = 0.0
    add_node.operation = 'ADD'

    density_socket = add_density_from_terrain_layer_nodes(node_tree, dataptr_name, dataptr_index, nodes)

    if density_socket is not None:
        node_tree.links.new(density_socket, add_node.inputs[1])

    node_tree.links.new(named_attribute_node.outputs[2], add_node.inputs[0])

    store_named_attribute_node = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
    store_named_attribute_node.data_type = 'BYTE_COLOR'
    store_named_attribute_node.domain = 'POINT'
    store_named_attribute_node.inputs['Name'].default_value = dataptr_id

    # Add a clamp node to clamp the density values between 0 and 1.
    clamp_node = node_tree.nodes.new('ShaderNodeClamp')
    clamp_node.inputs['Value'].default_value = 0.0
    clamp_node.inputs['Min'].default_value = 0.0
    clamp_node.inputs['Max'].default_value = 1.0

    node_tree.links.new(add_node.outputs['Value'], clamp_node.inputs['Value'])
    node_tree.links.new(clamp_node.outputs['Result'], store_named_attribute_node.inputs[5])

    node_tree.links.new(input_node.outputs[0], store_named_attribute_node.inputs['Geometry'])
    node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return node_tree


def ensure_noise_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketInt', 'Noise Type'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Scale'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Detail'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Roughness'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Lacunarity'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Distortion'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    }
    node_tree = ensure_geometry_node_tree('BDK Noise', items)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    noise_type_switch_node = node_tree.nodes.new('GeometryNodeSwitch')
    noise_type_switch_node.input_type = 'FLOAT'

    white_noise_node = node_tree.nodes.new('ShaderNodeTexWhiteNoise')
    white_noise_node.noise_dimensions = '2D'

    perlin_noise_node = node_tree.nodes.new('ShaderNodeTexNoise')
    perlin_noise_node.noise_dimensions = '2D'
    perlin_noise_node.normalize = True

    compare_node = node_tree.nodes.new('FunctionNodeCompare')
    compare_node.data_type = 'INT'
    compare_node.operation = 'EQUAL'
    compare_node.inputs[3].default_value = 0

    node_tree.links.new(input_node.outputs['Noise Type'], compare_node.inputs[2])
    node_tree.links.new(input_node.outputs['Perlin Noise Scale'], perlin_noise_node.inputs['Scale'])
    node_tree.links.new(input_node.outputs['Perlin Noise Detail'], perlin_noise_node.inputs['Detail'])
    node_tree.links.new(input_node.outputs['Perlin Noise Roughness'], perlin_noise_node.inputs['Roughness'])
    node_tree.links.new(input_node.outputs['Perlin Noise Lacunarity'], perlin_noise_node.inputs['Lacunarity'])
    node_tree.links.new(input_node.outputs['Perlin Noise Distortion'], perlin_noise_node.inputs['Distortion'])

    node_tree.links.new(compare_node.outputs['Result'], noise_type_switch_node.inputs['Switch'])
    node_tree.links.new(white_noise_node.outputs['Value'], noise_type_switch_node.inputs[3])  # True
    node_tree.links.new(perlin_noise_node.outputs['Fac'], noise_type_switch_node.inputs[2])   # False

    node_tree.links.new(noise_type_switch_node.outputs['Output'], output_node.inputs['Value'])

    return node_tree

def add_density_from_terrain_layer_node(node: 'BDK_PG_terrain_layer_node', node_tree: NodeTree, dataptr_name: str, dataptr_index: int, node_index: int) -> Optional[NodeSocket]:
    if node.type == 'PAINT':
        paint_named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        paint_named_attribute_node.data_type = 'FLOAT'
        paint_named_attribute_node.inputs['Name'].default_value = node.id
        return paint_named_attribute_node.outputs[1]
    elif node.type == 'PAINT_LAYER':
        layer_named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        layer_named_attribute_node.data_type = 'FLOAT'
        layer_named_attribute_node.inputs['Name'].default_value = node.paint_layer_id

        blur_switch_node = node_tree.nodes.new('GeometryNodeSwitch')
        blur_switch_node.input_type = 'FLOAT'
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object,
                                      blur_switch_node.inputs['Switch'], 'default_value', 'blur')

        # Add a modifier that turns any non-zero value into 1.0.
        blur_attribute_node = node_tree.nodes.new('GeometryNodeBlurAttribute')
        blur_attribute_node.data_type = 'FLOAT'
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object,
                                      blur_attribute_node.inputs['Iterations'], 'default_value', 'blur_iterations')

        node_tree.links.new(layer_named_attribute_node.outputs[1], blur_attribute_node.inputs[0])

        node_tree.links.new(layer_named_attribute_node.outputs[1], blur_switch_node.inputs[2])
        node_tree.links.new(blur_attribute_node.outputs[0], blur_switch_node.inputs[3])

        return blur_switch_node.outputs[0]
    elif node.type == 'CONSTANT':
        value_node = node_tree.nodes.new('ShaderNodeValue')
        value_node.outputs[0].default_value = 1.0
        return value_node.outputs[0]
    elif node.type == 'GROUP':
        if len(node.children) == 0:
            # Group is empty, skip it.
            return None
        return add_density_from_terrain_layer_nodes(node_tree, dataptr_name, dataptr_index, node.children)
    elif node.type == 'NOISE':
        noise_node_group_node = node_tree.nodes.new('GeometryNodeGroup')
        noise_node_group_node.node_tree = ensure_noise_node_group()

        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, noise_node_group_node.inputs['Noise Type'], 'default_value', 'noise_type')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, noise_node_group_node.inputs['Perlin Noise Scale'], 'default_value', 'noise_perlin_scale')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, noise_node_group_node.inputs['Perlin Noise Detail'], 'default_value', 'noise_perlin_detail')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, noise_node_group_node.inputs['Perlin Noise Roughness'], 'default_value', 'noise_perlin_roughness')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, noise_node_group_node.inputs['Perlin Noise Lacunarity'], 'default_value', 'noise_perlin_lacunarity')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, noise_node_group_node.inputs['Perlin Noise Distortion'], 'default_value', 'noise_perlin_distortion')

        return noise_node_group_node.outputs['Value']
    elif node.type == 'NORMAL':
        normal_node = node_tree.nodes.new('GeometryNodeInputNormal')

        dot_product_node = node_tree.nodes.new('ShaderNodeVectorMath')
        dot_product_node.operation = 'DOT_PRODUCT'
        dot_product_node.inputs[1].default_value = (0.0, 0.0, 1.0)

        arccosine_node = node_tree.nodes.new('ShaderNodeMath')
        arccosine_node.operation = 'ARCCOSINE'

        map_range_node = node_tree.nodes.new('ShaderNodeMapRange')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object,
                                      map_range_node.inputs['From Min'], 'default_value', 'normal_angle_min')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object,
                                      map_range_node.inputs['From Max'], 'default_value', 'normal_angle_max')

        node_tree.links.new(normal_node.outputs['Normal'], dot_product_node.inputs[0])
        node_tree.links.new(dot_product_node.outputs['Value'], arccosine_node.inputs[0])
        node_tree.links.new(arccosine_node.outputs['Value'], map_range_node.inputs['Value'])

        return map_range_node.outputs['Result']
    else:
        raise RuntimeError(f'Unknown node type: {node.type}')


def ensure_terrain_layer_node_density_node_group() -> NodeTree:
    items = {
        ('BOTH', 'NodeSocketFloat', 'Value'),
        ('INPUT', 'NodeSocketFloat', 'Factor'),
        ('INPUT', 'NodeSocketBool', 'Use Map Range'),
        ('INPUT', 'NodeSocketFloat', 'Map Range From Min'),
        ('INPUT', 'NodeSocketFloat', 'Map Range From Max'),
    }
    node_tree = ensure_geometry_node_tree('BDK Terrain Layer Node Density', items)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    map_range_node = node_tree.nodes.new('ShaderNodeMapRange')

    map_range_switch_node = node_tree.nodes.new('GeometryNodeSwitch')
    map_range_switch_node.input_type = 'FLOAT'
    map_range_switch_node.label = 'Use Map Range?'

    factor_multiply_node = node_tree.nodes.new('ShaderNodeMath')
    factor_multiply_node.operation = 'MULTIPLY'

    node_tree.links.new(input_node.outputs['Value'], map_range_node.inputs['Value'])
    node_tree.links.new(input_node.outputs['Value'], map_range_switch_node.inputs[2])  # False
    node_tree.links.new(map_range_node.outputs['Result'], map_range_switch_node.inputs[3])  # True

    node_tree.links.new(input_node.outputs['Map Range From Min'], map_range_node.inputs['From Min'])
    node_tree.links.new(input_node.outputs['Map Range From Max'], map_range_node.inputs['From Max'])

    node_tree.links.new(input_node.outputs['Use Map Range'], map_range_switch_node.inputs[0])

    node_tree.links.new(input_node.outputs['Factor'], factor_multiply_node.inputs[0])
    node_tree.links.new(map_range_switch_node.outputs['Output'], factor_multiply_node.inputs[1])
    node_tree.links.new(output_node.inputs['Value'], factor_multiply_node.outputs['Value'])

    return node_tree


def add_density_from_terrain_layer_nodes(node_tree: NodeTree, dataptr_name: str, dataptr_index: int, nodes: Iterable) -> Optional[NodeSocket]:
    last_density_socket = None

    for node_index, node in reversed(list(enumerate(nodes))):
        density_socket = add_density_from_terrain_layer_node(node, node_tree, dataptr_name, dataptr_index, node_index)

        if density_socket is None:
            continue

        # Density Node
        terrain_layer_node_density_node_group_node = node_tree.nodes.new('GeometryNodeGroup')
        terrain_layer_node_density_node_group_node.node_tree = ensure_terrain_layer_node_density_node_group()

        node_tree.links.new(density_socket, terrain_layer_node_density_node_group_node.inputs['Value'])

        # TODO: extremely verbose, refactor this.
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, terrain_layer_node_density_node_group_node.inputs['Map Range From Min'], 'default_value', 'map_range_from_min')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, terrain_layer_node_density_node_group_node.inputs['Map Range From Max'], 'default_value', 'map_range_from_max')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, terrain_layer_node_density_node_group_node.inputs['Use Map Range'], 'default_value', 'use_map_range')
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, terrain_layer_node_density_node_group_node.inputs['Factor'], 'default_value', 'factor')

        density_socket = terrain_layer_node_density_node_group_node.outputs['Value']

        # Operation Node
        operation_node_group_node = node_tree.nodes.new('GeometryNodeGroup')
        operation_node_group_node.node_tree = ensure_terrain_layer_node_operation_node_tree()

        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object,
                                      operation_node_group_node.inputs['Operation'],
                                      'default_value', 'operation')

        if last_density_socket:
            node_tree.links.new(last_density_socket, operation_node_group_node.inputs['Value 1'])

        node_tree.links.new(density_socket, operation_node_group_node.inputs['Value 2'])

        density_socket = operation_node_group_node.outputs['Value']

        switch_node = node_tree.nodes.new('GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'
        switch_node.inputs[2].default_value = 0.0

        # Link the previous switch output to the false input of the new switch.
        if last_density_socket:
            node_tree.links.new(last_density_socket, switch_node.inputs[2])

        node_tree.links.new(density_socket, switch_node.inputs[3])  # True input.

        # Attach the mute property as a driver for the switch node's switch input.
        add_terrain_layer_node_driver(
            dataptr_name,
            dataptr_index,
            node_index,
            node.terrain_info_object,
            switch_node.inputs['Switch'],
            'default_value',
            'mute',
            invert=True
        )

        last_density_socket = switch_node.outputs[0]

    return last_density_socket


def build_deco_layer_node_group(terrain_info_object: Object, deco_layer) -> NodeTree:
    terrain_info = get_terrain_info(terrain_info_object)
    deco_layer_index = list(terrain_info.deco_layers).index(deco_layer)

    items = {('OUTPUT', 'NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(deco_layer.id, items)

    terrain_doodad_info_node = node_tree.nodes.new('GeometryNodeObjectInfo')
    terrain_doodad_info_node.inputs[0].default_value = terrain_info_object

    deco_layer_node = node_tree.nodes.new('GeometryNodeBDKDecoLayer')
    deco_layer_node.inputs['Heightmap X'].default_value = terrain_info.x_size
    deco_layer_node.inputs['Heightmap Y'].default_value = terrain_info.y_size
    deco_layer_node.inputs['Density Map'].default_value = 0.0

    def get_deco_layer_target_data_path(deco_layer_index: int, property_name: str, index: Optional[int] = None) -> str:
        target_data_path = f'bdk.terrain_info.deco_layers[{deco_layer_index}].{property_name}'
        if index is not None:
            target_data_path += f'[{index}]'
        return target_data_path

    def get_terrain_info_target_data_path(property_name: str, index: Optional[int] = None) -> str:
        target_data_path = f'bdk.terrain_info.{property_name}'
        if index is not None:
            target_data_path += f'[{index}]'
        return target_data_path

    # TODO: move this to a helper file that can be used elsewhere (this pattern is very common!)
    def add_driver_ex(struct: bpy_struct, target_id: ID, target_data_path: str, path: str = 'default_value', index: Optional[int] = None):
        fcurve = struct.driver_add(path, index) if index is not None else struct.driver_add(path)
        fcurve.driver.type = 'AVERAGE'
        variable = fcurve.driver.variables.new()
        variable.type = 'SINGLE_PROP'
        target = variable.targets[0]
        target.id_type = 'OBJECT'
        target.id = target_id
        target.data_path = target_data_path

    def add_deco_layer_driver_ex(struct: bpy_struct, target_id: ID, property_name: str, path: str = 'default_value', index: Optional[int] = None):
        add_driver_ex(struct, target_id, get_deco_layer_target_data_path(deco_layer_index, property_name, index), path, index)

    def add_terrain_info_driver_ex(struct: bpy_struct, property_name: str, path: str = 'default_value', index: Optional[int] = None):
        add_driver_ex(struct, terrain_info_object, get_terrain_info_target_data_path(property_name, index), path, index)

    def add_deco_layer_driver(input_name: str, property_name: str, index: Optional[int] = None):
        add_deco_layer_driver_ex(deco_layer_node.inputs[input_name], target_id=terrain_info_object, property_name=property_name, index=index)

    def add_terrain_info_driver(input_name: str, property_name: str, index: Optional[int] = None):
        add_terrain_info_driver_ex(deco_layer_node.inputs[input_name], property_name, index=index)

    add_terrain_info_driver('Offset', 'deco_layer_offset')
    # add_terrain_info_driver('Inverted', 'inverted')

    add_deco_layer_driver('Max Per Quad', 'max_per_quad')
    add_deco_layer_driver('Seed', 'seed')
    add_deco_layer_driver('Offset', 'offset')
    add_deco_layer_driver('Show On Invisible Terrain', 'show_on_invisible_terrain')
    add_deco_layer_driver('Align To Terrain', 'align_to_terrain')
    add_deco_layer_driver('Random Yaw', 'random_yaw')
    add_deco_layer_driver('Density Multiplier Min', 'density_multiplier_min')
    add_deco_layer_driver('Density Multiplier Max', 'density_multiplier_max')
    add_deco_layer_driver('Scale Multiplier Min', 'scale_multiplier_min', 0)
    add_deco_layer_driver('Scale Multiplier Min', 'scale_multiplier_min', 1)
    add_deco_layer_driver('Scale Multiplier Min', 'scale_multiplier_min', 2)
    add_deco_layer_driver('Scale Multiplier Max', 'scale_multiplier_max', 0)
    add_deco_layer_driver('Scale Multiplier Max', 'scale_multiplier_max', 1)
    add_deco_layer_driver('Scale Multiplier Max', 'scale_multiplier_max', 2)

    static_mesh_object_info_node = node_tree.nodes.new('GeometryNodeObjectInfo')
    static_mesh_object_info_node.inputs[0].default_value = deco_layer.static_mesh

    # Add a named attribute node.
    named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
    named_attribute_node.inputs['Name'].default_value = deco_layer.id
    named_attribute_node.data_type = 'FLOAT'

    # Add a capture attribute node to capture the density from the geometry.
    capture_attribute_node = node_tree.nodes.new('GeometryNodeCaptureAttribute')
    capture_attribute_node.name = 'Density'
    capture_attribute_node.data_type = 'FLOAT'
    capture_attribute_node.domain = 'POINT'

    # Link the attribute output of the named attribute node to the capture attribute node.
    node_tree.links.new(named_attribute_node.outputs[1], capture_attribute_node.inputs[2])

    node_tree.links.new(capture_attribute_node.inputs['Geometry'], terrain_doodad_info_node.outputs['Geometry'])
    node_tree.links.new(deco_layer_node.inputs['Terrain'], capture_attribute_node.outputs['Geometry'])

    node_tree.links.new(capture_attribute_node.outputs[2], deco_layer_node.inputs['Density Map'])

    # Instance on Points
    instance_on_points_node = node_tree.nodes.new('GeometryNodeInstanceOnPoints')
    node_tree.links.new(instance_on_points_node.inputs['Instance'], static_mesh_object_info_node.outputs['Geometry'])
    node_tree.links.new(instance_on_points_node.inputs['Points'], deco_layer_node.outputs['Points'])
    node_tree.links.new(instance_on_points_node.inputs['Rotation'], deco_layer_node.outputs['Rotation'])
    node_tree.links.new(instance_on_points_node.inputs['Scale'], deco_layer_node.outputs['Scale'])

    # Realize Instances
    realize_instances_node = node_tree.nodes.new('GeometryNodeRealizeInstances')
    node_tree.links.new(instance_on_points_node.outputs['Instances'], realize_instances_node.inputs['Geometry'])

    output_node = node_tree.nodes.new('NodeGroupOutput')
    node_tree.links.new(output_node.inputs['Geometry'], realize_instances_node.outputs['Geometry'])

    return node_tree


def ensure_paint_layers(terrain_info_object: Object):
    terrain_info = get_terrain_info(terrain_info_object)

    # REALIZATION: we can't have paint layers with paint layer nodes due to circular dependencies.
    #  This could be possible though, if we police what layers are allowed to be painted in each layer.
    for paint_layer_index, paint_layer in enumerate(terrain_info.paint_layers):
        # Ensure the terrain info object has a geometry nodes modifier for the paint layer.
        if paint_layer.id == '':
            # TODO: Somehow, we have a paint layer with no id. Track this down!
            continue
        if  paint_layer.id not in terrain_info_object.modifiers.keys():
            modifier = terrain_info_object.modifiers.new(name=paint_layer.id, type='NODES')
        else:
            modifier = terrain_info_object.modifiers[paint_layer.id]
        # Rebuild the paint layer node group.
        modifier.node_group = ensure_terrain_layer_node_group(paint_layer.id, 'paint_layers', paint_layer_index, paint_layer.id, paint_layer.nodes)


def ensure_deco_layers(terrain_info_object: Object):
    terrain_info = get_terrain_info(terrain_info_object)

    for deco_layer_index, deco_layer in enumerate(terrain_info.deco_layers):
        if deco_layer.id == '' or deco_layer.modifier_name == '':
            # Paranoid check for empty deco layers.
            continue
        # Ensure the terrain info object has a geometry nodes modifier for the deco layer.
        if deco_layer.modifier_name not in terrain_info_object.modifiers.keys():
            modifier = terrain_info_object.modifiers.new(name=deco_layer.modifier_name, type='NODES')
        else:
            modifier = terrain_info_object.modifiers[deco_layer.modifier_name]

        # Rebuild the deco layer node group.
        modifier.node_group = ensure_terrain_layer_node_group(deco_layer.modifier_name, 'deco_layers', deco_layer_index, deco_layer.id, deco_layer.nodes)

        # TODO: Extract this to a function.
        if deco_layer.id not in deco_layer.object.modifiers:
            # Create the geometry nodes modifier and assign the node group.
            modifier = deco_layer.object.modifiers.new(name=deco_layer.id, type='NODES')
            modifier.node_group = build_deco_layer_node_group(terrain_info_object, deco_layer)


def create_deco_layer_object(deco_layer) -> Object:
    # Create a new mesh object with empty data.
    mesh_data = bpy.data.meshes.new(deco_layer.id)
    deco_layer_object = bpy.data.objects.new(deco_layer.id, mesh_data)
    deco_layer_object.hide_select = True
    return deco_layer_object


# TODO: the naming is ugly and unwieldy here
def create_terrain_paint_layer_node_convert_to_paint_layer_node_tree(node, paint_layer_index: int, node_index: int) -> NodeTree:
    return _create_terrain_layer_convert_node_to_paint_node_node_tree(node, 'paint_layers', paint_layer_index, node_index)


def create_terrain_deco_layer_node_convert_to_paint_layer_node_tree(node, deco_layer_index: int, node_index: int) -> NodeTree:
    return _create_terrain_layer_convert_node_to_paint_node_node_tree(node, 'deco_layers', deco_layer_index, node_index)


def _create_terrain_layer_convert_node_to_paint_node_node_tree(node, dataptr_name: str, dataptr_index: int, node_index: int) -> NodeTree:
    items = {('BOTH', 'NodeSocketGeometry', 'Geometry')}
    node_tree = ensure_geometry_node_tree(node.id, items)
    input_node, output_node = ensure_input_and_output_nodes(node_tree)

    store_named_attribute_node = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
    store_named_attribute_node.data_type = 'BYTE_COLOR'
    store_named_attribute_node.domain = 'POINT'
    store_named_attribute_node.inputs['Name'].default_value = node.id

    node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
    density_socket = add_density_from_terrain_layer_node(node, node_tree, dataptr_name, dataptr_index, node_index)

    if density_socket is not None:
        node_tree.links.new(density_socket, store_named_attribute_node.inputs[5])

    node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return node_tree
