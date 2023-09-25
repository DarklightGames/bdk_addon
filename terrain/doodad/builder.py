import uuid
from typing import List, Iterable, Optional, Dict, Set

import bmesh
import bpy
from uuid import uuid4
from bpy.types import NodeTree, Context, Object, NodeSocket, bpy_struct

from .sculpt.builder import ensure_sculpt_node_group
from ..deco import ensure_paint_layers, ensure_deco_layers
from ...node_helpers import ensure_interpolation_node_tree, add_operation_switch_nodes, \
    add_noise_type_switch_nodes, ensure_geometry_node_tree, ensure_input_and_output_nodes, ensure_trim_curve_node_tree, \
    ensure_curve_normal_offset_node_tree
from .data import terrain_doodad_operation_items
from ...units import meters_to_unreal


distance_to_mesh_node_group_id = 'BDK Distance to Mesh'
distance_to_empty_node_group_id = 'BDK Distance to Empty'
distance_to_curve_node_group_id = 'BDK Distance to Curve'


def ensure_distance_to_curve_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        curve_to_mesh_node = node_tree.nodes.new(type='GeometryNodeCurveToMesh')

        geometry_proximity_node = node_tree.nodes.new(type='GeometryNodeProximity')
        geometry_proximity_node.target_element = 'EDGES'

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        combine_xyz_node_2 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        # Input
        node_tree.links.new(input_node.outputs['Curve'], curve_to_mesh_node.inputs['Curve'])
        node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])

        # Internal
        node_tree.links.new(curve_to_mesh_node.outputs['Mesh'], geometry_proximity_node.inputs['Target'])
        node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(separate_xyz_node.outputs['Z'], switch_node.inputs['True'])
        node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node_2.inputs['X'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node_2.inputs['Y'])
        node_tree.links.new(switch_node.outputs['Output'], combine_xyz_node_2.inputs['Z'])
        node_tree.links.new(combine_xyz_node_2.outputs['Vector'], geometry_proximity_node.inputs['Source Position'])

        # Output
        node_tree.links.new(geometry_proximity_node.outputs['Distance'], output_node.inputs['Distance'])

    return ensure_geometry_node_tree(distance_to_curve_node_group_id, items, build_function)


def ensure_distance_noise_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketFloat', 'Distance'),
        ('INPUT', 'NodeSocketInt', 'Type'),
        ('INPUT', 'NodeSocketFloat', 'Factor'),
        ('INPUT', 'NodeSocketFloat', 'Distortion'),
        ('INPUT', 'NodeSocketFloat', 'Offset'),
        ('INPUT', 'NodeSocketBool', 'Use Noise'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

        noise_value_socket = add_noise_type_switch_nodes(
            node_tree,
            position_node.outputs['Position'],
            input_node.outputs['Type'],
            input_node.outputs['Distortion'],
            None
        )

        add_distance_noise_node = node_tree.nodes.new(type='ShaderNodeMath')
        add_distance_noise_node.operation = 'ADD'
        add_distance_noise_node.label = 'Add Noise'

        use_noise_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        use_noise_switch_node.input_type = 'FLOAT'
        use_noise_switch_node.label = 'Use Noise'

        distance_noise_factor_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        distance_noise_factor_multiply_node.operation = 'MULTIPLY'
        distance_noise_factor_multiply_node.label = 'Factor'

        distance_noise_offset_subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
        distance_noise_offset_subtract_node.operation = 'SUBTRACT'
        distance_noise_offset_subtract_node.label = 'Offset'

        # Input
        node_tree.links.new(input_node.outputs['Distance'], add_distance_noise_node.inputs[0])
        node_tree.links.new(input_node.outputs['Offset'], distance_noise_offset_subtract_node.inputs[1])
        node_tree.links.new(input_node.outputs['Factor'], distance_noise_factor_multiply_node.inputs[1])
        node_tree.links.new(input_node.outputs['Use Noise'], use_noise_switch_node.inputs[0])
        node_tree.links.new(input_node.outputs['Distance'], use_noise_switch_node.inputs[2])

        # Internal
        node_tree.links.new(noise_value_socket, distance_noise_offset_subtract_node.inputs[0])
        node_tree.links.new(distance_noise_offset_subtract_node.outputs['Value'], distance_noise_factor_multiply_node.inputs[0])
        node_tree.links.new(distance_noise_factor_multiply_node.outputs['Value'], add_distance_noise_node.inputs[1])
        node_tree.links.new(add_distance_noise_node.outputs['Value'], use_noise_switch_node.inputs[3])

        # Output
        node_tree.links.new(use_noise_switch_node.outputs[0], output_node.inputs['Distance'])

    return ensure_geometry_node_tree('BDK Distance Noise', items, build_function)


def ensure_doodad_paint_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Interpolation Type'),
        ('INPUT', 'NodeSocketInt', 'Operation'),
        ('INPUT', 'NodeSocketInt', 'Noise Type'),
        ('INPUT', 'NodeSocketFloat', 'Distance'),
        ('INPUT', 'NodeSocketString', 'Attribute'),
        ('INPUT', 'NodeSocketFloat', 'Radius'),
        ('INPUT', 'NodeSocketFloat', 'Falloff Radius'),
        ('INPUT', 'NodeSocketFloat', 'Strength'),
        ('INPUT', 'NodeSocketFloat', 'Distance Noise Factor'),
        ('INPUT', 'NodeSocketFloat', 'Distance Noise Distortion'),
        ('INPUT', 'NodeSocketFloat', 'Distance Noise Offset'),
        ('INPUT', 'NodeSocketBool', 'Use Distance Noise'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        # Create a new Store Named Attribute node.
        store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_named_attribute_node.data_type = 'BYTE_COLOR'
        store_named_attribute_node.domain = 'POINT'

        # Create a Named Attribute node.
        named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        named_attribute_node.data_type = 'FLOAT'

        # Link the Attribute output of the input node to the name input of the named attribute node.
        node_tree.links.new(input_node.outputs['Attribute'], named_attribute_node.inputs['Name'])
        node_tree.links.new(input_node.outputs['Attribute'], store_named_attribute_node.inputs['Name'])

        # Pass the geometry from the input to the output.
        node_tree.links.new(input_node.outputs['Geometry'], output_node.inputs['Geometry'])

        # Add a subtract node.
        subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
        subtract_node.operation = 'SUBTRACT'

        # Link the distance output of the input node to the first input of the subtraction node.
        node_tree.links.new(input_node.outputs['Radius'], subtract_node.inputs[1])

        # Add a divide node.
        divide_node = node_tree.nodes.new(type='ShaderNodeMath')
        divide_node.operation = 'DIVIDE'

        # Link the output of the subtraction node to the first input of the divide node.
        node_tree.links.new(subtract_node.outputs['Value'], divide_node.inputs[0])
        node_tree.links.new(input_node.outputs['Falloff Radius'], divide_node.inputs[1])

        # Add an interpolation group node.
        interpolation_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        interpolation_group_node.node_tree = ensure_interpolation_node_tree()

        # Add a multiply node.
        strength_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        strength_multiply_node.operation = 'MULTIPLY'
        strength_multiply_node.label = 'Strength Multiply'

        value_socket = add_operation_switch_nodes(
            node_tree,
            input_node.outputs['Operation'],
            named_attribute_node.outputs[1],
            strength_multiply_node.outputs['Value'],
            [x[0] for x in terrain_doodad_operation_items]
        )

        # Add the distance noise node group.
        distance_noise_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_noise_group_node.node_tree = ensure_distance_noise_node_group()

        # Input
        node_tree.links.new(input_node.outputs['Geometry'], store_named_attribute_node.inputs['Geometry'])
        node_tree.links.new(input_node.outputs['Distance'], distance_noise_group_node.inputs['Distance'])
        node_tree.links.new(input_node.outputs['Noise Type'], distance_noise_group_node.inputs['Type'])
        node_tree.links.new(input_node.outputs['Distance Noise Factor'], distance_noise_group_node.inputs['Factor'])
        node_tree.links.new(input_node.outputs['Distance Noise Distortion'], distance_noise_group_node.inputs['Distortion'])
        node_tree.links.new(input_node.outputs['Distance Noise Offset'], distance_noise_group_node.inputs['Offset'])
        node_tree.links.new(input_node.outputs['Use Distance Noise'], distance_noise_group_node.inputs['Use Noise'])
        node_tree.links.new(input_node.outputs['Interpolation Type'], interpolation_group_node.inputs['Interpolation Type'])
        node_tree.links.new(input_node.outputs['Strength'], strength_multiply_node.inputs[1])

        # Internal
        node_tree.links.new(divide_node.outputs['Value'], interpolation_group_node.inputs['Value'])
        node_tree.links.new(interpolation_group_node.outputs['Value'], strength_multiply_node.inputs[0])
        node_tree.links.new(value_socket, store_named_attribute_node.inputs[5])
        node_tree.links.new(distance_noise_group_node.outputs['Distance'], subtract_node.inputs[0])

        # Output
        node_tree.links.new(store_named_attribute_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree('BDK Doodad Paint', items, build_function)


def ensure_distance_to_mesh_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')

        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        geometry_proximity_node = node_tree.nodes.new(type='GeometryNodeProximity')
        geometry_proximity_node.target_element = 'FACES'

        transform_geometry_node = node_tree.nodes.new(type='GeometryNodeTransform')
        transform_geometry_node.inputs['Scale'].default_value = (1.0, 1.0, 0.0)

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'VECTOR'

        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        # Input
        node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Geometry'], transform_geometry_node.inputs['Geometry'])

        # Internal
        node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node.inputs['X'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node.inputs['Y'])
        node_tree.links.new(combine_xyz_node.outputs['Vector'], switch_node.inputs[8])
        node_tree.links.new(position_node.outputs['Position'], switch_node.inputs[9])
        node_tree.links.new(switch_node.outputs[3], geometry_proximity_node.inputs['Source Position'])
        node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(transform_geometry_node.outputs['Geometry'], geometry_proximity_node.inputs['Target'])

        # Output
        node_tree.links.new(geometry_proximity_node.outputs['Distance'], output_node.inputs['Distance'])

    return ensure_geometry_node_tree(distance_to_mesh_node_group_id, items, build_function)


def ensure_distance_to_empty_node_group() -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketVector', 'Location'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance')
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'FLOAT'

        combine_xyz_node_2 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        vector_subtract_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_subtract_node.operation = 'SUBTRACT'

        vector_length_node = node_tree.nodes.new(type='ShaderNodeVectorMath')
        vector_length_node.operation = 'LENGTH'

        # Input
        node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Location'], vector_subtract_node.inputs[0])

        # Internal
        node_tree.links.new(separate_xyz_node.outputs['Z'], switch_node.inputs['True'])
        node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node_2.inputs['X'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node_2.inputs['Y'])
        node_tree.links.new(switch_node.outputs['Output'], combine_xyz_node_2.inputs['Z'])
        node_tree.links.new(position_node.outputs['Position'], vector_subtract_node.inputs[1])
        node_tree.links.new(vector_subtract_node.outputs['Vector'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(combine_xyz_node_2.outputs['Vector'], vector_length_node.inputs['Vector'])

        # Output
        node_tree.links.new(vector_length_node.outputs['Value'], output_node.inputs['Distance'])

    return ensure_geometry_node_tree(distance_to_empty_node_group_id, items, build_function)


def create_terrain_doodad_object(context: Context, terrain_info_object: Object, object_type: str = 'CURVE') -> Object:
    """
    Creates a terrain doodad of the specified type.
    Note that this function does not add the terrain doodad object to the scene. That is the responsibility of the caller.
    :param context:
    :param terrain_info_object:
    :param object_type: The type of object to create. Valid values are 'CURVE', 'MESH' and 'EMPTY'
    :return:
    """
    terrain_doodad_id = uuid4().hex

    if object_type == 'CURVE':
        object_data = bpy.data.curves.new(name=terrain_doodad_id, type='CURVE')
        spline = object_data.splines.new(type='BEZIER')

        # Add some points to the spline.
        spline.bezier_points.add(count=1)

        # Add a set of aligned meandering points.
        for i, point in enumerate(spline.bezier_points):
            point.co = (i, 0, 0)
            point.handle_left_type = 'AUTO'
            point.handle_right_type = 'AUTO'
            point.handle_left = (i - 0.25, -0.25, 0)
            point.handle_right = (i + 0.25, 0.25, 0)

        # Scale the points.
        scale = meters_to_unreal(10.0)
        for point in spline.bezier_points:
            point.co *= scale
            point.handle_left *= scale
            point.handle_right *= scale
    elif object_type == 'EMPTY':
        object_data = None
    elif object_type == 'MESH':
        object_data = bpy.data.meshes.new(name=terrain_doodad_id)
        # Create a plane using bmesh.
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=meters_to_unreal(1.0))
        bm.to_mesh(object_data)
        del bm

    bpy_object = bpy.data.objects.new(name='Doodad', object_data=object_data)

    if object_type == 'EMPTY':
        bpy_object.empty_display_type = 'SPHERE'
        bpy_object.empty_display_size = meters_to_unreal(1.0)
        # Set the delta transform to the terrain info object's rotation.
        bpy_object.delta_rotation_euler = (0, 0, 0)
    elif object_type == 'MESH':
        bpy_object.display_type = 'WIRE'

    # Hide from rendering and Cycles passes.
    bpy_object.hide_render = True

    # Disable all ray visibility settings (this stops it from being visible in Cycles rendering in the viewport).
    bpy_object.visible_camera = False
    bpy_object.visible_diffuse = False
    bpy_object.visible_glossy = False
    bpy_object.visible_transmission = False
    bpy_object.visible_volume_scatter = False
    bpy_object.visible_shadow = False

    bpy_object.bdk.type = 'TERRAIN_DOODAD'
    bpy_object.bdk.terrain_doodad.id = terrain_doodad_id
    bpy_object.bdk.terrain_doodad.terrain_info_object = terrain_info_object
    bpy_object.bdk.terrain_doodad.object = bpy_object
    bpy_object.bdk.terrain_doodad.node_tree = bpy.data.node_groups.new(name=terrain_doodad_id, type='GeometryNodeTree')
    bpy_object.show_in_front = True
    bpy_object.lock_location = (False, False, True)
    bpy_object.lock_rotation = (True, True, False)

    terrain_doodad = bpy_object.bdk.terrain_doodad

    # Add sculpt and paint layers.
    # In the future, we will allow the user to select a preset for the terrain doodad.
    sculpt_layer = terrain_doodad.sculpt_layers.add()
    sculpt_layer.id = uuid4().hex
    sculpt_layer.terrain_doodad_object = terrain_doodad.object

    paint_layer = terrain_doodad.paint_layers.add()
    paint_layer.id = uuid4().hex
    paint_layer.terrain_doodad_object = terrain_doodad.object

    # Set the location of the curve object to the 3D cursor.
    bpy_object.location = context.scene.cursor.location

    return bpy_object


def get_terrain_doodads_for_terrain_info_object(context: Context, terrain_info_object: Object) -> List['BDK_PG_terrain_doodad']:
    return [obj.bdk.terrain_doodad for obj in context.scene.objects if obj.bdk.type == 'TERRAIN_DOODAD' and obj.bdk.terrain_doodad.terrain_info_object == terrain_info_object]


def ensure_terrain_info_modifiers(context: Context, terrain_info: 'BDK_PG_terrain_info'):
    terrain_info_object: Object = terrain_info.terrain_info_object

    # Ensure that the modifier IDs have been generated.
    if terrain_info.doodad_sculpt_modifier_name == '':
        terrain_info.doodad_sculpt_modifier_name = uuid.uuid4().hex

    if terrain_info.doodad_attribute_modifier_name == '':
        terrain_info.doodad_attribute_modifier_name = uuid.uuid4().hex

    if terrain_info.doodad_paint_modifier_name == '':
        terrain_info.doodad_paint_modifier_name = uuid.uuid4().hex

    if terrain_info.doodad_deco_modifier_name == '':
        terrain_info.doodad_deco_modifier_name = uuid.uuid4().hex

    # Gather and sort the terrain doodad by the sort order and ID.
    terrain_doodads = get_terrain_doodads_for_terrain_info_object(context, terrain_info.terrain_info_object)
    terrain_doodads.sort(key=lambda x: (x.sort_order, x.id))

    # Ensure that the terrain info object has the required pass modifiers.
    modifier_names = [
        terrain_info.doodad_sculpt_modifier_name,
        terrain_info.doodad_attribute_modifier_name,
        terrain_info.doodad_paint_modifier_name,
        terrain_info.doodad_deco_modifier_name,
    ]
    for modifier_name in modifier_names:
        if modifier_name not in terrain_info_object.modifiers:
            modifier = terrain_info_object.modifiers.new(name=modifier_name, type='NODES')
            modifier.show_on_cage = True

    # Ensure the node groups for the pass modifiers.
    modifiers = terrain_info_object.modifiers
    modifiers[terrain_info.doodad_sculpt_modifier_name].node_group = _ensure_terrain_doodad_sculpt_modifier_node_group(terrain_info.doodad_sculpt_modifier_name, terrain_doodads)
    modifiers[terrain_info.doodad_attribute_modifier_name].node_group = _ensure_terrain_doodad_attribute_modifier_node_group(terrain_info.doodad_attribute_modifier_name, terrain_doodads)
    modifiers[terrain_info.doodad_paint_modifier_name].node_group = _ensure_terrain_doodad_paint_modifier_node_group(terrain_info.doodad_paint_modifier_name, terrain_doodads)
    modifiers[terrain_info.doodad_deco_modifier_name].node_group = _ensure_terrain_doodad_deco_modifier_node_group(terrain_info.doodad_deco_modifier_name, terrain_doodads)

    # Rebuild the modifier node trees for the paint and deco layers.
    ensure_paint_layers(terrain_info_object)
    ensure_deco_layers(terrain_info_object)

    """
    Sort the modifiers on the terrain info object in the following order:
    1. Terrain Doodad Sculpt
    2. Terrain Doodad Attribute
    3. Terrain Info Paint Layer Nodes
    4. Terrain Doodad Paint Layers
    5. Terrain Info Deco Layer Nodes
    6. Terrain Doodad Deco Layers
    """

    # The modifier ID list will contain a list of modifier IDs in the order that they should be sorted.
    modifier_ids = list()
    modifier_ids.append(terrain_info.doodad_sculpt_modifier_name)
    modifier_ids.append(terrain_info.doodad_attribute_modifier_name)
    modifier_ids.extend(map(lambda paint_layer: paint_layer.id, terrain_info.paint_layers))
    modifier_ids.append(terrain_info.doodad_paint_modifier_name)
    modifier_ids.extend(map(lambda deco_layer: deco_layer.modifier_name, terrain_info.deco_layers))  # TODO: something weird going down here, we shouldn't be using the deco layer ID
    modifier_ids.append(terrain_info.doodad_deco_modifier_name)

    # Make note of what the current mode is so that we can restore it later.
    current_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    current_active_object = bpy.context.view_layer.objects.active

    # Make the active object the terrain info object.
    bpy.context.view_layer.objects.active = terrain_info_object

    # Set the mode to OBJECT so that we can move the modifiers.
    bpy.ops.object.mode_set(mode='OBJECT')

    # It's theoretically possible that the modifiers don't exist (e.g., having been deleted by the user, debugging etc.)
    # Get a list of missing modifiers.
    missing_modifier_ids = set(modifier_ids).difference(set(terrain_info_object.modifiers.keys()))
    # Add any missing modifiers.
    for modifier_id in missing_modifier_ids:
        if modifier_id not in bpy.data.node_groups:
            print('Missing node group: ' + modifier_id)
            continue
        modifier = terrain_info_object.modifiers.new(name=modifier_id, type='NODES')
        modifier.node_group = bpy.data.node_groups[modifier_id]
        modifier.show_on_cage = True

    # Remove any modifier IDs that do not have a corresponding modifier in the terrain info object.
    superfluous_modifier_ids = set(terrain_info_object.modifiers.keys()).difference(set(modifier_ids))

    # Remove any superfluous modifiers.
    for modifier_id in superfluous_modifier_ids:
        terrain_info_object.modifiers.remove(terrain_info_object.modifiers[modifier_id])

    modifier_ids = [x for x in modifier_ids if x in terrain_info_object.modifiers]

    # TODO: it would be nice if we could move the modifiers without needing to use the ops API, or at
    #  least suspend evaluation of the node tree while we do it.
    # TODO: we can use the data API to do this, but we need to know the index of the modifier in the list.
    # Update the modifiers on the terrain info object to reflect the new sort order.
    for i, modifier_id in enumerate(modifier_ids):
        bpy.ops.object.modifier_move_to_index(modifier=modifier_id, index=i)

    # Restore the mode and active object to what it was before.
    bpy.context.view_layer.objects.active = current_active_object

    if bpy.context.view_layer.objects.active:
        bpy.ops.object.mode_set(mode=current_mode)


def _add_doodad_driver(struct: bpy_struct, terrain_doodad: 'BDK_PG_terrain_doodad', data_path: str,
                              path: str = 'default_value'):
    driver = struct.driver_add(path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = terrain_doodad.object
    var.targets[0].data_path = f"bdk.terrain_doodad.{data_path}"


def add_curve_modifier_nodes(node_tree: NodeTree, curve_socket: NodeSocket, layer, layer_type: str) -> NodeSocket:

    reverse_curve_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    reverse_curve_switch_node.input_type = 'GEOMETRY'
    reverse_curve_switch_node.label = 'Reverse Curve?'

    reverse_curve_node = node_tree.nodes.new(type='GeometryNodeReverseCurve')

    add_doodad_layer_driver(reverse_curve_switch_node.inputs[1], layer, layer_type, 'is_curve_reversed')

    node_tree.links.new(curve_socket, reverse_curve_node.inputs['Curve'])
    node_tree.links.new(curve_socket, reverse_curve_switch_node.inputs[14])  # False
    node_tree.links.new(reverse_curve_node.outputs['Curve'], reverse_curve_switch_node.inputs[15])  # True

    # Add BDK Curve Trim node.
    trim_curve_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
    trim_curve_group_node.node_tree = ensure_trim_curve_node_tree()
    node_tree.links.new(curve_socket, trim_curve_group_node.outputs['Curve'])

    add_doodad_layer_driver(trim_curve_group_node.inputs['Mode'], layer, layer_type, 'curve_trim_mode')
    add_doodad_layer_driver(trim_curve_group_node.inputs['Factor Start'], layer, layer_type, 'curve_trim_factor_start')
    add_doodad_layer_driver(trim_curve_group_node.inputs['Factor End'], layer, layer_type, 'curve_trim_factor_end')
    add_doodad_layer_driver(trim_curve_group_node.inputs['Length Start'], layer, layer_type, 'curve_trim_length_start')
    add_doodad_layer_driver(trim_curve_group_node.inputs['Length End'], layer, layer_type, 'curve_trim_length_end')

    # Add BDK Curve Normal Offset node.
    curve_normal_offset_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
    curve_normal_offset_group_node.node_tree = ensure_curve_normal_offset_node_tree()

    add_doodad_layer_driver(curve_normal_offset_group_node.inputs['Normal Offset'], layer, layer_type,
                            'curve_normal_offset')

    node_tree.links.new(reverse_curve_switch_node.outputs[6], trim_curve_group_node.inputs['Curve'])
    node_tree.links.new(trim_curve_group_node.outputs['Curve'], curve_normal_offset_group_node.inputs['Curve'])

    return curve_normal_offset_group_node.outputs['Curve']


def add_distance_to_doodad_layer_nodes(node_tree: NodeTree, layer, layer_type: str, doodad_object_info_node: bpy.types.Node) -> NodeSocket:
    terrain_doodad = layer.terrain_doodad_object.bdk.terrain_doodad

    if terrain_doodad.object.type == 'CURVE':
        # Add curve modifier nodes.
        curve_socket = add_curve_modifier_nodes(node_tree, doodad_object_info_node.outputs['Geometry'], layer, layer_type)

        # Add a distance to curve node group.
        distance_to_curve_node_group = ensure_distance_to_curve_node_group()
        distance_to_curve_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_curve_node.node_tree = distance_to_curve_node_group

        node_tree.links.new(curve_socket, distance_to_curve_node.inputs['Curve'])
        _add_doodad_driver(distance_to_curve_node.inputs['Is 3D'], terrain_doodad, 'is_3d')

        return distance_to_curve_node.outputs['Distance']
    elif terrain_doodad.object.type == 'MESH':
        distance_to_mesh_node_group = ensure_distance_to_mesh_node_group()

        # Add a new node group node.
        distance_to_mesh_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_mesh_node.node_tree = distance_to_mesh_node_group
        distance_to_mesh_node.label = 'Distance to Mesh'

        node_tree.links.new(doodad_object_info_node.outputs['Geometry'], distance_to_mesh_node.inputs['Geometry'])

        return distance_to_mesh_node.outputs['Distance']
    elif terrain_doodad.object.type == 'EMPTY':
        distance_to_empty_node_group = ensure_distance_to_empty_node_group()

        distance_to_empty_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_to_empty_node.node_tree = distance_to_empty_node_group
        distance_to_empty_node.label = 'Distance to Empty'

        node_tree.links.new(doodad_object_info_node.outputs['Location'], distance_to_empty_node.inputs['Location'])
        _add_doodad_driver(distance_to_empty_node.inputs['Is 3D'], terrain_doodad, 'is_3d')

        return distance_to_empty_node.outputs['Distance']
    else:
        raise Exception(f"Unsupported terrain doodad type: {terrain_doodad.object.type}")


def add_doodad_layer_driver(
        struct: bpy_struct,
        layer,
        layer_type: str,
        data_path: str,
        path: str = 'default_value'
):
    driver = struct.driver_add(path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = layer.terrain_doodad_object
    if layer_type == 'SCULPT':
        data_path = f"bdk.terrain_doodad.sculpt_layers[{layer.index}].{data_path}"
    elif layer_type == 'PAINT':
        data_path = f"bdk.terrain_doodad.paint_layers[{layer.index}].{data_path}"
    elif layer_type == 'DECO':
        data_path = f"bdk.terrain_doodad.deco_layers[{layer.index}].{data_path}"
    else:
        raise Exception(f"Unknown layer type: {layer_type}")
    var.targets[0].data_path = data_path


def add_doodad_sculpt_layer_driver(struct: bpy_struct, layer, data_path: str, path: str = 'default_value'):
    add_doodad_layer_driver(struct, layer, 'SCULPT', data_path, path)


def add_doodad_paint_layer_driver(struct: bpy_struct, layer, data_path: str, path: str = 'default_value'):
    add_doodad_layer_driver(struct, layer, 'PAINT', data_path, path)


def add_doodad_deco_layer_driver(struct: bpy_struct, layer, data_path: str, path: str = 'default_value'):
    add_doodad_layer_driver(struct, layer, 'DECO', data_path, path)


def _add_sculpt_layers_to_node_tree(node_tree: NodeTree, geometry_socket: NodeSocket, terrain_doodad) -> NodeSocket:
    """
    Adds the nodes for a doodad's sculpt layers.
    :param node_tree: The node tree to add the nodes to.
    :param geometry_socket: The geometry socket to connect the nodes to.
    :param terrain_doodad: The terrain doodad to add the sculpt layers for.
    :return: The geometry output socket (either the one passed in or the one from the last node added).
    """

    # Add an object info node and set the object to the terrain doodad.
    object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    object_info_node.inputs[0].default_value = terrain_doodad.object
    object_info_node.transform_space = 'RELATIVE'

    # Now chain the node components together.
    for sculpt_layer in terrain_doodad.sculpt_layers:
        # Add the distance to doodad layer nodes.
        distance_socket = add_distance_to_doodad_layer_nodes(node_tree, sculpt_layer, 'SCULPT', doodad_object_info_node=object_info_node)

        # Store the calculated distance to a named attribute.
        # This is faster than recalculating the distance when evaluating each layer. (~20% faster)
        store_distance_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
        store_distance_attribute_node.inputs['Name'].default_value = sculpt_layer.id
        store_distance_attribute_node.data_type = 'FLOAT'
        store_distance_attribute_node.domain = 'POINT'

        # Link the geometry from the input node to the input of the store distance attribute node.
        node_tree.links.new(geometry_socket, store_distance_attribute_node.inputs['Geometry'])

        # Link the distance socket to the input of the store distance attribute node.
        node_tree.links.new(distance_socket, store_distance_attribute_node.inputs[4])

        # Create a named attribute node for the distance.
        distance_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        distance_attribute_node.inputs['Name'].default_value = sculpt_layer.id
        distance_attribute_node.data_type = 'FLOAT'

        distance_socket = distance_attribute_node.outputs[1]
        geometry_socket = store_distance_attribute_node.outputs['Geometry']

        # =============================================================

        sculpt_node = node_tree.nodes.new(type='GeometryNodeGroup')
        sculpt_node.node_tree = ensure_sculpt_node_group()
        sculpt_node.label = 'Sculpt'

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'GEOMETRY'

        add_doodad_sculpt_layer_driver(switch_node.inputs[1], sculpt_layer, 'mute')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Radius'], sculpt_layer, 'radius')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Falloff Radius'], sculpt_layer, 'falloff_radius')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Depth'], sculpt_layer, 'depth')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Noise Strength'], sculpt_layer, 'noise_strength')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Perlin Noise Roughness'], sculpt_layer, 'perlin_noise_roughness')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Perlin Noise Distortion'], sculpt_layer, 'perlin_noise_distortion')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Perlin Noise Scale'], sculpt_layer, 'perlin_noise_scale')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Perlin Noise Lacunarity'], sculpt_layer, 'perlin_noise_lacunarity')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Perlin Noise Detail'], sculpt_layer, 'perlin_noise_detail')

        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Use Noise'], sculpt_layer, 'use_noise')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Noise Radius Factor'], sculpt_layer, 'noise_radius_factor')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Interpolation Type'], sculpt_layer, 'interpolation_type')
        add_doodad_sculpt_layer_driver(sculpt_node.inputs['Noise Type'], sculpt_layer, 'noise_type')

        # Link the geometry socket of the object info node to the geometry socket of the sculpting node.
        node_tree.links.new(geometry_socket, sculpt_node.inputs['Geometry'])
        node_tree.links.new(distance_socket, sculpt_node.inputs['Distance'])

        node_tree.links.new(sculpt_node.outputs['Geometry'], switch_node.inputs[14])  # False (not muted)
        node_tree.links.new(geometry_socket, switch_node.inputs[15])  # True (muted)

        geometry_socket = switch_node.outputs[6]

    return geometry_socket


def _ensure_terrain_doodad_sculpt_modifier_node_group(name: str, terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        for terrain_doodad in terrain_doodads:
            geometry_socket = _add_sculpt_layers_to_node_tree(node_tree, geometry_socket, terrain_doodad)

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def _add_paint_layer_to_node_tree(node_tree: NodeTree, geometry_socket: NodeSocket,
                                  paint_layer: 'BDK_PG_terrain_doodad_paint_layer',
                                  attribute_override: Optional[str] = None,
                                  operation_override: Optional[str] = None) -> NodeSocket:

    def add_paint_layer_driver(struct: bpy_struct, paint_layer: 'BDK_PG_terrain_doodad_paint_layer', data_path: str,
                               path: str = 'default_value'):
        driver = struct.driver_add(path).driver
        driver.type = 'AVERAGE'
        var = driver.variables.new()
        var.name = data_path
        var.type = 'SINGLE_PROP'
        var.targets[0].id = paint_layer.terrain_doodad_object
        var.targets[0].data_path = f"bdk.terrain_doodad.paint_layers[{paint_layer.index}].{data_path}"

    doodad_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    doodad_object_info_node.inputs[0].default_value = paint_layer.terrain_doodad_object
    doodad_object_info_node.transform_space = 'RELATIVE'

    distance_socket = add_distance_to_doodad_layer_nodes(node_tree, paint_layer, 'PAINT', doodad_object_info_node)

    store_distance_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
    store_distance_attribute_node.inputs['Name'].default_value = paint_layer.id
    store_distance_attribute_node.data_type = 'FLOAT'
    store_distance_attribute_node.domain = 'POINT'

    node_tree.links.new(geometry_socket, store_distance_attribute_node.inputs['Geometry'])

    geometry_socket = store_distance_attribute_node.outputs['Geometry']

    paint_node = node_tree.nodes.new(type='GeometryNodeGroup')
    paint_node.node_tree = ensure_doodad_paint_node_group()
    paint_node.label = 'Paint'

    if attribute_override is not None:
        paint_node.inputs['Attribute'].default_value = attribute_override
    else:
        # These attributes are not pre-calculated anymore, so we need to do it here.
        if paint_layer.layer_type == 'PAINT':
            paint_node.inputs['Attribute'].default_value = paint_layer.paint_layer_id
        elif paint_layer.layer_type == 'DECO':
            paint_node.inputs['Attribute'].default_value = paint_layer.deco_layer_id
        elif paint_layer.layer_type == 'ATTRIBUTE':
            paint_node.inputs['Attribute'].default_value = paint_layer.attribute_layer_id

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'GEOMETRY'

    add_paint_layer_driver(switch_node.inputs[1], paint_layer, 'mute')
    add_paint_layer_driver(paint_node.inputs['Radius'], paint_layer, 'radius')
    add_paint_layer_driver(paint_node.inputs['Falloff Radius'], paint_layer, 'falloff_radius')
    add_paint_layer_driver(paint_node.inputs['Strength'], paint_layer, 'strength')
    add_paint_layer_driver(paint_node.inputs['Use Distance Noise'], paint_layer, 'use_distance_noise')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Distortion'], paint_layer, 'distance_noise_distortion')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Factor'], paint_layer, 'distance_noise_factor')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Offset'], paint_layer, 'distance_noise_offset')
    add_paint_layer_driver(paint_node.inputs['Interpolation Type'], paint_layer, 'interpolation_type')

    if operation_override is not None:
        # Handle operation override. This is used when baking.
        operation_keys = [item[0] for item in terrain_doodad_operation_items]
        paint_node.inputs['Operation'].default_value = operation_keys.index(operation_override)
    else:
        add_paint_layer_driver(paint_node.inputs['Operation'], paint_layer, 'operation')

    add_paint_layer_driver(paint_node.inputs['Noise Type'], paint_layer, 'noise_type')

    node_tree.links.new(geometry_socket, paint_node.inputs['Geometry'])
    node_tree.links.new(distance_socket, paint_node.inputs['Distance'])
    node_tree.links.new(paint_node.outputs['Geometry'], switch_node.inputs[14])  # False (not muted)
    node_tree.links.new(geometry_socket, switch_node.inputs[15])  # True (muted)

    return switch_node.outputs[6]  # Output


def _ensure_terrain_doodad_paint_modifier_node_group(name: str, terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        for terrain_doodad in terrain_doodads:
            for paint_layer in filter(lambda x: x.layer_type == 'PAINT', terrain_doodad.paint_layers):
                geometry_socket = _add_paint_layer_to_node_tree(node_tree, geometry_socket, paint_layer)

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def _ensure_terrain_doodad_deco_modifier_node_group(name: str, terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        for terrain_doodad in terrain_doodads:
            for paint_layer in filter(lambda x: x.layer_type == 'DECO', terrain_doodad.paint_layers):
                geometry_socket = _add_paint_layer_to_node_tree(node_tree, geometry_socket, paint_layer)

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)

def _ensure_terrain_doodad_attribute_modifier_node_group(name: str, terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    }

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        for terrain_doodad in terrain_doodads:
            for paint_layer in filter(lambda x: x.layer_type == 'ATTRIBUTE', terrain_doodad.paint_layers):
                geometry_socket = _add_paint_layer_to_node_tree(node_tree, geometry_socket, paint_layer)

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def create_terrain_doodad_bake_node_tree(terrain_doodad: 'BDK_PG_terrain_doodad', layers: Set[str]) -> (NodeTree, Dict[str, str]):
    """
    Creates a node tree for baking a terrain doodad.
    :param terrain_doodad: The terrain doodad to make a baking node tree for.
    :return: The terrain doodad baking node tree and a mapping of the paint layer IDs to the baked attribute names.
    """
    items = {
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry')
    }

    # Build a mapping of the paint layer IDs to the baked attribute names.
    attribute_map: Dict[str, str] = {}
    for paint_layer in terrain_doodad.paint_layers:
        attribute_map[paint_layer.id] = uuid4().hex

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        if 'SCULPT' in layers:
            # Add sculpt layers for the doodad.
            geometry_socket = _add_sculpt_layers_to_node_tree(node_tree, geometry_socket, terrain_doodad)

        # Add the paint layers for the doodad.
        if 'PAINT' in layers:
            for doodad_paint_layer in terrain_doodad.paint_layers:
                attribute_name = attribute_map[doodad_paint_layer.id]
                # We override the operation here because we want the influence of each layer to be additive for the bake.
                # Without this, if a "SUBTRACT" operation were used, the resulting bake for the attribute would be
                # completely black (painted with 0). The actual operation will be transferred to the associated node in the
                # layer node tree.
                # TODO: Ideally, we would not need these overrides because it is a little hacky. It would be cleaner to
                #  separate out the operation from the "Paint Layer" node group, although we would need a compelling reason
                #  to do so.
                geometry_socket = _add_paint_layer_to_node_tree(node_tree, geometry_socket, doodad_paint_layer,
                                                                attribute_override=attribute_name,
                                                                operation_override='ADD')

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    node_tree = ensure_geometry_node_tree(uuid.uuid4().hex, items, build_function, should_force_build=True)

    return node_tree, attribute_map
