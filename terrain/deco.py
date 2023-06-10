import bpy
import uuid

from bpy.types import Context, Object, NodeTree, Collection, NodeSocket, bpy_struct
from typing import Optional, Iterable

from ..helpers import get_terrain_info, auto_increment_name


def add_terrain_deco_layer(context: Context, terrain_info_object: Object, name: str = 'DecoLayer'):
    """
    Adds a deco layer to the terrain.
    This adds a new entry to the deco layers array in the terrain info and creates the associated deco layer object and
    mesh attributes.
    """
    terrain_info = get_terrain_info(terrain_info_object)

    deco_layer_index = len(terrain_info.deco_layers)

    # Create the deco layer object.
    deco_layer = terrain_info.deco_layers.add()
    deco_layer.name = auto_increment_name(name, map(lambda x: x.name, terrain_info.deco_layers))
    deco_layer.id = uuid.uuid4().hex
    deco_layer.object = create_deco_layer_object(context, terrain_info_object, deco_layer)
    deco_layer.terrain_info_object = terrain_info_object

    # Link and parent the deco layer object to the terrain object.
    collection: Collection = terrain_info_object.users_collection[0]
    collection.objects.link(deco_layer.object)
    deco_layer.object.parent = terrain_info_object

    # Create the deco layer modifier for the terrain.
    # This will write the density map attribute to be used by the deco layer object.
    deco_layer_modifier = terrain_info_object.modifiers.new(name=deco_layer.id, type='NODES')
    node_tree = bpy.data.node_groups.new(uuid.uuid4().hex, 'GeometryNodeTree')
    deco_layer_modifier.node_group = node_tree
    update_terrain_deco_layer_node_group(node_tree, deco_layer, deco_layer_index)

    # TODO: Re-sort the modifiers on the terrain object in the following order:
    # 1. Terrain Object Sculpt (so that the 3D geometry is locked in for the other modifiers)
    # 2. Layer Nodes (so that deco layers can read the layer attributes)
    # 3. Deco Layer Nodes (final consumer of the geo & layer attributes)
    # We also need to make the terrain objects insert un-editable TERRAIN_OBJECT into the layer and deco layer nodes,
    # thus unify the systems.
    # This should completely resolve the issue of the modifiers not being applied in the correct order, so long as the
    # sort order of the terrain objects triggers a recalculation of the modifier stack.

    # Generates the deco layer geometry node.
    build_deco_layers(terrain_info_object)

    return deco_layer


def add_deco_layer_node_driver(deco_layer_index: int, node_index: int, terrain_info_object: Object, struct: bpy_struct, path: str, property_name: str, index: Optional[int] = None, invert: bool = False):
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
        target.data_path = f'bdk.terrain_info.deco_layers[{deco_layer_index}].nodes[{node_index}].{property_name}[{index}]'
    else:
        target.data_path = f'bdk.terrain_info.deco_layers[{deco_layer_index}].nodes[{node_index}].{property_name}'


def update_terrain_deco_layer_node_group(node_tree: NodeTree, deco_layer, deco_layer_index: int):
    node_tree.inputs.clear()
    node_tree.outputs.clear()
    node_tree.nodes.clear()
    node_tree.links.clear()

    density_socket = add_density_from_deco_layer_nodes(node_tree, deco_layer_index, deco_layer.nodes)

    node_tree.inputs.new('NodeSocketGeometry', 'Geometry')
    node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

    input_node = node_tree.nodes.new('NodeGroupInput')
    output_node = node_tree.nodes.new('NodeGroupOutput')

    density_store_named_attribute_node = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
    density_store_named_attribute_node.data_type = 'FLOAT'
    density_store_named_attribute_node.domain = 'POINT'
    density_store_named_attribute_node.inputs['Name'].default_value = deco_layer.id

    if density_socket:
        node_tree.links.new(density_socket, density_store_named_attribute_node.inputs[4])

    node_tree.links.new(input_node.outputs[0], density_store_named_attribute_node.inputs['Geometry'])
    node_tree.links.new(density_store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])


def add_density_from_deco_layer_nodes(node_tree: NodeTree, deco_layer_index: int, nodes: Iterable) -> NodeSocket:
    last_density_socket = None

    for node_index, node in reversed(list(enumerate(nodes))):
        if node.type == 'PAINT':
            paint_named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
            paint_named_attribute_node.data_type = 'FLOAT'
            paint_named_attribute_node.inputs['Name'].default_value = node.id
            density_socket = paint_named_attribute_node.outputs[1]
        elif node.type == 'TERRAIN_LAYER':
            layer_named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
            layer_named_attribute_node.data_type = 'FLOAT'
            layer_named_attribute_node.inputs['Name'].default_value = node.layer_id

            # Add a modifier that turns any non-zero value into 1.0.

            blur_attribute_node = node_tree.nodes.new('GeometryNodeBlurAttribute')
            blur_attribute_node.data_type = 'FLOAT'
            node_tree.links.new(layer_named_attribute_node.outputs[1], blur_attribute_node.inputs[0])
            add_deco_layer_node_driver(deco_layer_index, node_index, node.terrain_info_object, blur_attribute_node.inputs['Weight'], 'default_value', 'blur')
            add_deco_layer_node_driver(deco_layer_index, node_index, node.terrain_info_object, blur_attribute_node.inputs['Iterations'], 'default_value', 'blur_iterations')

            density_socket = blur_attribute_node.outputs[0]
        elif node.type == 'CONSTANT':
            value_node = node_tree.nodes.new('ShaderNodeValue')
            value_node.outputs[0].default_value = 1.0
            density_socket = value_node.outputs[0]
        elif node.type == 'GROUP':
            if len(node.children) == 0:
                # Group is empty, skip it.
                continue
            # TODO: figure out how to mute this...route it through a math node?
            density_socket = add_density_from_deco_layer_nodes(node_tree, deco_layer_index, node.children)
        elif node.type == 'NOISE':
            white_noise_node = node_tree.nodes.new('ShaderNodeTexWhiteNoise')
            white_noise_node.noise_dimensions = '2D'
            density_socket = white_noise_node.outputs['Value']
        elif node.type == 'NORMAL':
            normal_node = node_tree.nodes.new('GeometryNodeInputNormal')
            dot_product_node = node_tree.nodes.new('ShaderNodeVectorMath')
            dot_product_node.operation = 'DOT_PRODUCT'
            dot_product_node.inputs[1].default_value = (0.0, 0.0, 1.0)
            node_tree.links.new(normal_node.outputs['Normal'], dot_product_node.inputs[0])
            density_socket = dot_product_node.outputs['Value']
        else:
            raise RuntimeError(f'Unknown node type: {node.type}')

        # Add a math node to multiply the density socket by the node's opacity.
        factor_node = node_tree.nodes.new('ShaderNodeMath')
        factor_node.operation = 'MULTIPLY'
        add_deco_layer_node_driver(deco_layer_index, node_index, node.terrain_info_object, factor_node.inputs[0], 'default_value', 'factor')
        node_tree.links.new(density_socket, factor_node.inputs[1])
        density_socket = factor_node.outputs['Value']

        math_node = node_tree.nodes.new('ShaderNodeMath')
        math_node.operation = node.operation
        if last_density_socket:
            node_tree.links.new(last_density_socket, math_node.inputs[0])
        else:
            math_node.inputs[0].default_value = 0.0
        node_tree.links.new(density_socket, math_node.inputs[1])
        density_socket = math_node.outputs['Value']

        switch_node = node_tree.nodes.new('GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'
        switch_node.inputs[2].default_value = 0.0
        node_tree.links.new(density_socket, switch_node.inputs[3])
        # Attach the mute property as a driver for the switch node's switch input.
        add_deco_layer_node_driver(deco_layer_index, node_index, node.terrain_info_object, switch_node.inputs['Switch'], 'default_value', 'mute', invert=True)

        last_density_socket = switch_node.outputs[0]

    return last_density_socket


def build_deco_layer_node_group(terrain_info_object: Object, deco_layer) -> NodeTree:
    terrain_info = get_terrain_info(terrain_info_object)

    deco_layer_index = list(terrain_info.deco_layers).index(deco_layer)

    if deco_layer.id in bpy.data.node_groups:
        node_tree = bpy.data.node_groups[deco_layer.id]
    else:
        node_tree = bpy.data.node_groups.new(deco_layer.id, type='GeometryNodeTree')

    node_tree.outputs.clear()
    node_tree.outputs.new(type='NodeSocketGeometry', name='Geometry')

    node_tree.nodes.clear()

    terrain_object_info_node = node_tree.nodes.new('GeometryNodeObjectInfo')
    terrain_object_info_node.inputs[0].default_value = terrain_info_object

    deco_layer_node = node_tree.nodes.new('GeometryNodeBDKDecoLayer')
    deco_layer_node.inputs['Heightmap X'].default_value = terrain_info.x_size
    deco_layer_node.inputs['Heightmap Y'].default_value = terrain_info.y_size
    deco_layer_node.inputs['Density Map'].default_value = 0.0

    def add_deco_layer_driver(input_name: str, property_name: str, index: Optional[int] = None):
        if index is None:
            fcurve = deco_layer_node.inputs[input_name].driver_add('default_value')
        else:
            fcurve = deco_layer_node.inputs[input_name].driver_add('default_value', index)

        fcurve.driver.type = 'AVERAGE'
        variable = fcurve.driver.variables.new()
        variable.type = 'SINGLE_PROP'
        target = variable.targets[0]
        target.id_type = 'OBJECT'
        target.id = terrain_info_object
        if index is not None:
            target.data_path = f'bdk.terrain_info.deco_layers[{deco_layer_index}].{property_name}[{index}]'
        else:
            target.data_path = f'bdk.terrain_info.deco_layers[{deco_layer_index}].{property_name}'

    add_deco_layer_driver('Max Per Quad', 'max_per_quad')
    add_deco_layer_driver('Seed', 'seed')
    add_deco_layer_driver('Offset', 'offset')
    add_deco_layer_driver('Show On Invisible Terrain', 'show_on_invisible_terrain')
    add_deco_layer_driver('Align To Terrain', 'align_to_terrain')
    add_deco_layer_driver('Random Yaw', 'random_yaw')
    # add_deco_layer_driver('Inverted', 'inverted')  # TODO: point to the top level object
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

    node_tree.links.new(capture_attribute_node.inputs['Geometry'], terrain_object_info_node.outputs['Geometry'])
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


def build_deco_layers(terrain_info_object: Object):
    terrain_info = get_terrain_info(terrain_info_object)

    for deco_layer_index, deco_layer in enumerate(terrain_info.deco_layers):
        # Rebuild the terrain info's deco layer node group.
        if deco_layer.id in terrain_info_object.modifiers:
            modifier = terrain_info_object.modifiers[deco_layer.id]
            update_terrain_deco_layer_node_group(modifier.node_group, deco_layer, deco_layer_index)

        if deco_layer.id not in deco_layer.object.modifiers:
            # Create the geometry nodes modifier and assign the node group.
            modifier = deco_layer.object.modifiers.new(name=deco_layer.id, type='NODES')
            modifier.node_group = build_deco_layer_node_group(terrain_info_object, deco_layer)


def create_deco_layer_object(context: Context, terrain_info_object: Object, deco_layer) -> Object:
    # Create a new mesh object with empty data.
    mesh_data = bpy.data.meshes.new(deco_layer.id)
    deco_layer_object = bpy.data.objects.new(deco_layer.id, mesh_data)
    deco_layer_object.hide_select = True
    return deco_layer_object
