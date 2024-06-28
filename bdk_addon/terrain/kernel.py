from bpy.types import Object, NodeTree, NodeSocket, bpy_struct, ID
from typing import Optional, Iterable, Callable

from ..helpers import get_terrain_info
from ..node_helpers import ensure_input_and_output_nodes, ensure_geometry_node_tree, \
    ensure_terrain_layer_node_operation_node_tree


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


def _terrain_layer_node_data_path_get(dataptr_name: str, dataptr_index: int, node_index: int, property_name: str, index: Optional[int] = None) -> str:
    if index is not None:
        return f'bdk.terrain_info.{dataptr_name}[{dataptr_index}].nodes[{node_index}].{property_name}[{index}]'
    else:
        return f'bdk.terrain_info.{dataptr_name}[{dataptr_index}].nodes[{node_index}].{property_name}'


NodeDataPathFunctionType = Callable[[str, int, int, str, Optional[int]], str]


def add_terrain_layer_node_driver(
        dataptr_name: str,
        dataptr_index: int,
        node_index: int,
        target_id: ID,
        struct: bpy_struct,
        path: str,
        property_name: str,
        data_path_function: NodeDataPathFunctionType,
        index: Optional[int] = None,
        invert: bool = False
):
    if index is None:
        fcurve = struct.driver_add(path)
    else:
        fcurve = struct.driver_add(path, index)

    # TODO: i don't like the idea of slowing down the driver evaluation by using a scripted expression, let's refactor this later.
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
    target.id = target_id
    target.data_path = data_path_function(dataptr_name, dataptr_index, node_index, property_name, index)


def ensure_terrain_layer_node_group(name: str, dataptr_name: str, dataptr_index: int, dataptr_id: str, nodes: Iterable, target_id: ID) -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        named_attribute_node.data_type = 'FLOAT'
        named_attribute_node.inputs['Name'].default_value = dataptr_id

        add_node = node_tree.nodes.new('ShaderNodeMath')
        add_node.inputs[0].default_value = 0.0
        add_node.inputs[1].default_value = 0.0
        add_node.operation = 'ADD'

        density_socket = add_density_from_terrain_layer_nodes(node_tree, target_id, dataptr_name, dataptr_index, nodes, _terrain_layer_node_data_path_get)

        if density_socket is not None:
            node_tree.links.new(density_socket, add_node.inputs[1])

        node_tree.links.new(named_attribute_node.outputs['Attribute'], add_node.inputs[0])

        store_named_attribute_node = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'FLOAT'
        store_named_attribute_node.domain = 'POINT'
        store_named_attribute_node.inputs['Name'].default_value = dataptr_id

        # Add a clamp node to clamp the density values between 0 and 1.
        clamp_node = node_tree.nodes.new('ShaderNodeClamp')
        clamp_node.inputs['Value'].default_value = 0.0
        clamp_node.inputs['Min'].default_value = 0.0
        clamp_node.inputs['Max'].default_value = 1.0

        node_tree.links.new(add_node.outputs['Value'], clamp_node.inputs['Value'])
        node_tree.links.new(clamp_node.outputs['Result'], store_named_attribute_node.inputs['Value'])

        node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def ensure_noise_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInt', 'Noise Type'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Scale'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Detail'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Roughness'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Lacunarity'),
        ('INPUT', 'NodeSocketFloat', 'Perlin Noise Distortion'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        noise_type_switch_node = node_tree.nodes.new('GeometryNodeSwitch')
        noise_type_switch_node.input_type = 'FLOAT'

        white_noise_node = node_tree.nodes.new('ShaderNodeTexWhiteNoise')
        white_noise_node.noise_dimensions = '2D'

        perlin_noise_node = node_tree.nodes.new('ShaderNodeTexNoise')
        perlin_noise_node.noise_dimensions = '2D'
        perlin_noise_node.normalize = True
        perlin_noise_node.noise_type = 'MULTIFRACTAL'

        compare_node = node_tree.nodes.new('FunctionNodeCompare')
        compare_node.data_type = 'INT'
        compare_node.operation = 'EQUAL'
        compare_node.inputs['B'].default_value = 0

        node_tree.links.new(input_node.outputs['Noise Type'], compare_node.inputs['A'])
        node_tree.links.new(input_node.outputs['Perlin Noise Scale'], perlin_noise_node.inputs['Scale'])
        node_tree.links.new(input_node.outputs['Perlin Noise Detail'], perlin_noise_node.inputs['Detail'])
        node_tree.links.new(input_node.outputs['Perlin Noise Roughness'], perlin_noise_node.inputs['Roughness'])
        node_tree.links.new(input_node.outputs['Perlin Noise Lacunarity'], perlin_noise_node.inputs['Lacunarity'])
        node_tree.links.new(input_node.outputs['Perlin Noise Distortion'], perlin_noise_node.inputs['Distortion'])

        node_tree.links.new(compare_node.outputs['Result'], noise_type_switch_node.inputs['Switch'])
        node_tree.links.new(white_noise_node.outputs['Value'], noise_type_switch_node.inputs['True'])
        node_tree.links.new(perlin_noise_node.outputs['Fac'], noise_type_switch_node.inputs['False'])

        node_tree.links.new(noise_type_switch_node.outputs['Output'], output_node.inputs['Value'])

    return ensure_geometry_node_tree('BDK Noise', items, build_function)


def add_density_from_terrain_layer_node(
        node: 'BDK_PG_terrain_layer_node',
        node_tree: NodeTree,
        target_id: ID,
        dataptr_name: str,
        dataptr_index: int,
        node_index: int,
        data_path_function: NodeDataPathFunctionType
) -> Optional[NodeSocket]:
    def _add_terrain_layer_node_driver(struct: bpy_struct, property_name: str):
        add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, target_id, struct, 'default_value', property_name, data_path_function)

    if node.type in ['PAINT', 'FIELD']:
        paint_named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        paint_named_attribute_node.data_type = 'FLOAT'
        paint_named_attribute_node.inputs['Name'].default_value = node.id
        return paint_named_attribute_node.outputs['Attribute']
    elif node.type == 'PAINT_LAYER':
        layer_named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        layer_named_attribute_node.data_type = 'FLOAT'
        layer_named_attribute_node.inputs['Name'].default_value = node.paint_layer_id

        blur_switch_node = node_tree.nodes.new('GeometryNodeSwitch')
        blur_switch_node.input_type = 'FLOAT'
        _add_terrain_layer_node_driver(blur_switch_node.inputs['Switch'], 'blur')

        # Add a modifier that turns any non-zero value into 1.0.
        blur_attribute_node = node_tree.nodes.new('GeometryNodeBlurAttribute')
        blur_attribute_node.data_type = 'FLOAT'
        _add_terrain_layer_node_driver(blur_attribute_node.inputs['Iterations'], 'blur_iterations')

        node_tree.links.new(layer_named_attribute_node.outputs['Attribute'], blur_attribute_node.inputs['Value'])
        node_tree.links.new(layer_named_attribute_node.outputs['Attribute'], blur_switch_node.inputs['False'])
        node_tree.links.new(blur_attribute_node.outputs['Value'], blur_switch_node.inputs['True'])

        return blur_switch_node.outputs['Output']
    elif node.type == 'CONSTANT':
        value_node = node_tree.nodes.new('ShaderNodeValue')
        value_node.outputs['Value'].default_value = 1.0
        return value_node.outputs['Value']
    elif node.type == 'GROUP':
        if len(node.children) == 0:
            # Group is empty, skip it.
            return None
        return add_density_from_terrain_layer_nodes(node_tree, target_id, dataptr_name, dataptr_index, node.children, data_path_function)
    elif node.type == 'NOISE':
        noise_node_group_node = node_tree.nodes.new('GeometryNodeGroup')
        noise_node_group_node.node_tree = ensure_noise_node_group()

        _add_terrain_layer_node_driver(noise_node_group_node.inputs['Noise Type'], 'noise_type')
        _add_terrain_layer_node_driver(noise_node_group_node.inputs['Perlin Noise Scale'], 'noise_perlin_scale')
        _add_terrain_layer_node_driver(noise_node_group_node.inputs['Perlin Noise Detail'], 'noise_perlin_detail')
        _add_terrain_layer_node_driver(noise_node_group_node.inputs['Perlin Noise Roughness'], 'noise_perlin_roughness')
        _add_terrain_layer_node_driver(noise_node_group_node.inputs['Perlin Noise Lacunarity'], 'noise_perlin_lacunarity')
        _add_terrain_layer_node_driver(noise_node_group_node.inputs['Perlin Noise Distortion'], 'noise_perlin_distortion')

        return noise_node_group_node.outputs['Value']
    elif node.type == 'NORMAL':
        normal_node = node_tree.nodes.new('GeometryNodeInputNormal')

        dot_product_node = node_tree.nodes.new('ShaderNodeVectorMath')
        dot_product_node.operation = 'DOT_PRODUCT'
        dot_product_node.inputs[1].default_value = (0.0, 0.0, 1.0)

        arccosine_node = node_tree.nodes.new('ShaderNodeMath')
        arccosine_node.operation = 'ARCCOSINE'

        map_range_node = node_tree.nodes.new('ShaderNodeMapRange')
        _add_terrain_layer_node_driver(map_range_node.inputs['From Min'], 'normal_angle_min')
        _add_terrain_layer_node_driver(map_range_node.inputs['From Max'], 'normal_angle_max')

        node_tree.links.new(normal_node.outputs['Normal'], dot_product_node.inputs[0])
        node_tree.links.new(dot_product_node.outputs['Value'], arccosine_node.inputs[0])
        node_tree.links.new(arccosine_node.outputs['Value'], map_range_node.inputs['Value'])

        return map_range_node.outputs['Result']
    else:
        raise RuntimeError(f'Unknown node type: {node.type}')


def ensure_terrain_layer_node_density_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketFloat', 'Value'),
        ('INPUT', 'NodeSocketFloat', 'Factor'),
        ('INPUT', 'NodeSocketBool', 'Use Map Range'),
        ('INPUT', 'NodeSocketFloat', 'Map Range From Min'),
        ('INPUT', 'NodeSocketFloat', 'Map Range From Max'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        map_range_node = node_tree.nodes.new('ShaderNodeMapRange')

        map_range_switch_node = node_tree.nodes.new('GeometryNodeSwitch')
        map_range_switch_node.input_type = 'FLOAT'
        map_range_switch_node.label = 'Use Map Range?'

        factor_multiply_node = node_tree.nodes.new('ShaderNodeMath')
        factor_multiply_node.operation = 'MULTIPLY'

        node_tree.links.new(input_node.outputs['Value'], map_range_node.inputs['Value'])
        node_tree.links.new(input_node.outputs['Value'], map_range_switch_node.inputs['False'])
        node_tree.links.new(map_range_node.outputs['Result'], map_range_switch_node.inputs['True'])

        node_tree.links.new(input_node.outputs['Map Range From Min'], map_range_node.inputs['From Min'])
        node_tree.links.new(input_node.outputs['Map Range From Max'], map_range_node.inputs['From Max'])

        node_tree.links.new(input_node.outputs['Use Map Range'], map_range_switch_node.inputs['Switch'])

        node_tree.links.new(input_node.outputs['Factor'], factor_multiply_node.inputs[0])
        node_tree.links.new(map_range_switch_node.outputs['Output'], factor_multiply_node.inputs[1])
        node_tree.links.new(output_node.inputs['Value'], factor_multiply_node.outputs['Value'])

    return ensure_geometry_node_tree('BDK Terrain Layer Node Density', items, build_function)


def add_density_from_terrain_layer_nodes(node_tree: NodeTree, target_id: ID, dataptr_name: str, dataptr_index: int, nodes: Iterable, data_path_function: NodeDataPathFunctionType) -> Optional[NodeSocket]:
    last_density_socket = None

    for node_index, node in reversed(list(enumerate(nodes))):
        density_socket = add_density_from_terrain_layer_node(node, node_tree, target_id, dataptr_name, dataptr_index, node_index, data_path_function)

        if density_socket is None:
            continue

        # Density Node
        terrain_layer_node_density_node_group_node = node_tree.nodes.new('GeometryNodeGroup')
        terrain_layer_node_density_node_group_node.node_tree = ensure_terrain_layer_node_density_node_group()

        node_tree.links.new(density_socket, terrain_layer_node_density_node_group_node.inputs['Value'])

        def add_terrain_layer_density_driver(struct: bpy_struct, property_name: str, invert: bool = False):
            add_terrain_layer_node_driver(dataptr_name, dataptr_index, node_index, node.terrain_info_object, struct,
                                          'default_value', property_name, data_path_function, invert=invert)

        add_terrain_layer_density_driver(terrain_layer_node_density_node_group_node.inputs['Map Range From Min'],
                                         'map_range_from_min')
        add_terrain_layer_density_driver(terrain_layer_node_density_node_group_node.inputs['Map Range From Max'],
                                         'map_range_from_max')
        add_terrain_layer_density_driver(terrain_layer_node_density_node_group_node.inputs['Use Map Range'],
                                         'use_map_range')
        add_terrain_layer_density_driver(terrain_layer_node_density_node_group_node.inputs['Factor'], 'factor')

        density_socket = terrain_layer_node_density_node_group_node.outputs['Value']

        # Operation Node
        operation_node_group_node = node_tree.nodes.new('GeometryNodeGroup')
        operation_node_group_node.node_tree = ensure_terrain_layer_node_operation_node_tree()

        add_terrain_layer_density_driver(operation_node_group_node.inputs['Operation'], 'operation')

        if last_density_socket:
            node_tree.links.new(last_density_socket, operation_node_group_node.inputs['Value 1'])

        node_tree.links.new(density_socket, operation_node_group_node.inputs['Value 2'])

        density_socket = operation_node_group_node.outputs['Value']

        switch_node = node_tree.nodes.new('GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'
        switch_node.inputs[2].default_value = 0.0

        # Link the previous switch output to the false input of the new switch.
        if last_density_socket:
            node_tree.links.new(last_density_socket, switch_node.inputs['False'])

        node_tree.links.new(density_socket, switch_node.inputs['True'])

        # Attach the mute property as a driver for the switch node's switch input.
        add_terrain_layer_density_driver(switch_node.inputs['Switch'], 'mute', True)

        last_density_socket = switch_node.outputs[0]

    return last_density_socket


def build_deco_layer_node_group(terrain_info_object: Object, deco_layer) -> NodeTree:
    items = (
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        terrain_info = get_terrain_info(terrain_info_object)
        # TODO: don't we store the index in the deco layer itself?
        deco_layer_index = list(terrain_info.deco_layers).index(deco_layer)

        # Nodes
        terrain_doodad_info_node = node_tree.nodes.new('GeometryNodeObjectInfo')
        terrain_doodad_info_node.inputs[0].default_value = terrain_info_object

        deco_layer_node = node_tree.nodes.new('GeometryNodeBDKDecoLayer')
        deco_layer_node.inputs['Heightmap X'].default_value = terrain_info.x_size
        deco_layer_node.inputs['Heightmap Y'].default_value = terrain_info.y_size
        deco_layer_node.inputs['Density Map'].default_value = 0.0

        realize_instances_node = node_tree.nodes.new('GeometryNodeRealizeInstances')

        static_mesh_object_info_node = node_tree.nodes.new('GeometryNodeObjectInfo')
        static_mesh_object_info_node.inputs[0].default_value = deco_layer.static_mesh

        named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        named_attribute_node.inputs['Name'].default_value = deco_layer.id
        named_attribute_node.data_type = 'FLOAT'

        capture_attribute_node = node_tree.nodes.new('GeometryNodeCaptureAttribute')
        capture_attribute_node.name = 'Density'
        capture_attribute_node.domain = 'POINT'
        # capture_attribute_node.data_type = 'FLOAT'

        instance_on_points_node = node_tree.nodes.new('GeometryNodeInstanceOnPoints')

        # Drivers
        def get_deco_layer_target_data_path(property_name: str, index: Optional[int] = None) -> str:
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
        def add_driver_ex(struct: bpy_struct, target_id: ID, target_data_path: str, path: str = 'default_value',
                          index: Optional[int] = None):
            fcurve = struct.driver_add(path, index) if index is not None else struct.driver_add(path)
            fcurve.driver.type = 'AVERAGE'
            variable = fcurve.driver.variables.new()
            variable.type = 'SINGLE_PROP'
            target = variable.targets[0]
            target.id_type = 'OBJECT'
            target.id = target_id
            target.data_path = target_data_path

        def add_deco_layer_driver_ex(struct: bpy_struct, target_id: ID, property_name: str, path: str = 'default_value',
                                     index: Optional[int] = None):
            add_driver_ex(struct, target_id, get_deco_layer_target_data_path(property_name, index), path, index)

        def add_terrain_info_driver_ex(struct: bpy_struct, property_name: str, path: str = 'default_value',
                                       index: Optional[int] = None):
            add_driver_ex(struct, terrain_info_object, get_terrain_info_target_data_path(property_name, index), path, index)

        def add_deco_layer_driver(input_name: str, property_name: str, index: Optional[int] = None):
            add_deco_layer_driver_ex(deco_layer_node.inputs[input_name], target_id=terrain_info_object,
                                     property_name=property_name, index=index)

        def add_terrain_info_driver(input_name: str, property_name: str, index: Optional[int] = None):
            add_terrain_info_driver_ex(deco_layer_node.inputs[input_name], property_name, index=index)

        add_terrain_info_driver('Offset', 'deco_layer_offset')

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

        # Internal
        node_tree.links.new(instance_on_points_node.inputs['Instance'], static_mesh_object_info_node.outputs['Geometry'])
        node_tree.links.new(instance_on_points_node.inputs['Points'], deco_layer_node.outputs['Points'])
        node_tree.links.new(instance_on_points_node.inputs['Rotation'], deco_layer_node.outputs['Rotation'])
        node_tree.links.new(instance_on_points_node.inputs['Scale'], deco_layer_node.outputs['Scale'])
        node_tree.links.new(capture_attribute_node.inputs[1], named_attribute_node.outputs['Attribute'])
        node_tree.links.new(capture_attribute_node.inputs['Geometry'], terrain_doodad_info_node.outputs['Geometry'])
        node_tree.links.new(deco_layer_node.inputs['Terrain'], capture_attribute_node.outputs['Geometry'])
        node_tree.links.new(deco_layer_node.inputs['Density Map'], capture_attribute_node.outputs[1])
        node_tree.links.new(realize_instances_node.inputs['Geometry'], instance_on_points_node.outputs['Instances'])

        # Output
        node_tree.links.new(output_node.inputs['Geometry'], realize_instances_node.outputs['Geometry'])

    return ensure_geometry_node_tree(deco_layer.id, items, build_function, should_force_build=True)


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
        modifier.node_group = ensure_terrain_layer_node_group(paint_layer.id, 'paint_layers', paint_layer_index, paint_layer.id, paint_layer.nodes, terrain_info_object)


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
        modifier.node_group = ensure_terrain_layer_node_group(deco_layer.modifier_name, 'deco_layers', deco_layer_index, deco_layer.id, deco_layer.nodes, terrain_info_object)

        # TODO: Extract this to a function.
        if deco_layer.id not in deco_layer.object.modifiers:
            # Create the geometry nodes modifier and assign the node group.
            modifier = deco_layer.object.modifiers.new(name=deco_layer.id, type='NODES')
            modifier.node_group = build_deco_layer_node_group(terrain_info_object, deco_layer)


# TODO: the naming is ugly and unwieldy here
def create_terrain_paint_layer_node_convert_to_paint_layer_node_tree(node, target_id: ID, paint_layer_index: int, node_index: int) -> NodeTree:
    return _create_convert_node_to_paint_node_node_tree(node, target_id, 'paint_layers', paint_layer_index, node_index, _terrain_layer_node_data_path_get)


def create_terrain_deco_layer_node_convert_to_paint_layer_node_tree(node, target_id: ID, deco_layer_index: int, node_index: int) -> NodeTree:
    return _create_convert_node_to_paint_node_node_tree(node, target_id, 'deco_layers', deco_layer_index, node_index, _terrain_layer_node_data_path_get)


def _create_convert_node_to_paint_node_node_tree(node, target_id: ID, dataptr_name: str, dataptr_index: int, node_index: int, data_path_function: NodeDataPathFunctionType) -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        store_named_attribute_node = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'BYTE_COLOR'
        store_named_attribute_node.domain = 'POINT'
        store_named_attribute_node.inputs['Name'].default_value = node.id

        node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
        density_socket = add_density_from_terrain_layer_node(node, node_tree, target_id, dataptr_name, dataptr_index, node_index, data_path_function)

        if density_socket is not None:
            node_tree.links.new(density_socket, store_named_attribute_node.inputs['Value'])

        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(node.id, items, build_function, should_force_build=True)
