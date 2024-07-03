import uuid
from typing import List, Iterable, Optional, Dict, Set

import bmesh
import bpy
from uuid import uuid4
from bpy.types import NodeTree, Context, Object, NodeSocket, bpy_struct, Node
from itertools import chain

from ...units import meters_to_unreal
from ...node_helpers import ensure_interpolation_node_tree, add_operation_switch_nodes, \
    add_noise_type_switch_nodes, ensure_geometry_node_tree, ensure_input_and_output_nodes, \
    add_geometry_node_switch_nodes, ensure_curve_modifier_node_tree
from ..kernel import ensure_paint_layers, ensure_deco_layers
from .kernel import get_terrain_doodad_scatter_layer_by_id
from .sculpt.builder import ensure_sculpt_value_node_group
from .data import terrain_doodad_operation_items


def ensure_distance_noise_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketFloat', 'Distance'),
        ('INPUT', 'NodeSocketInt', 'Type'),
        ('INPUT', 'NodeSocketFloat', 'Factor'),
        ('INPUT', 'NodeSocketFloat', 'Distortion'),
        ('INPUT', 'NodeSocketFloat', 'Offset'),
        ('INPUT', 'NodeSocketBool', 'Use Noise'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance'),
    )

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
        node_tree.links.new(input_node.outputs['Use Noise'], use_noise_switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Distance'], use_noise_switch_node.inputs['False'])

        # Internal
        node_tree.links.new(noise_value_socket, distance_noise_offset_subtract_node.inputs[0])
        node_tree.links.new(distance_noise_offset_subtract_node.outputs['Value'],
                            distance_noise_factor_multiply_node.inputs[0])
        node_tree.links.new(distance_noise_factor_multiply_node.outputs['Value'], add_distance_noise_node.inputs[1])
        node_tree.links.new(add_distance_noise_node.outputs['Value'], use_noise_switch_node.inputs['True'])

        # Output
        node_tree.links.new(use_noise_switch_node.outputs['Output'], output_node.inputs['Distance'])

    return ensure_geometry_node_tree('BDK Distance Noise', items, build_function)


def ensure_terrain_doodad_paint_operation_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInt', 'Operation'),
        ('INPUT', 'NodeSocketFloat', 'Value 1'),
        ('INPUT', 'NodeSocketFloat', 'Value 2'),
        ('OUTPUT', 'NodeSocketFloat', 'Output'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        value_socket = add_operation_switch_nodes(
            node_tree,
            input_node.outputs['Operation'],
            input_node.outputs['Value 1'],
            input_node.outputs['Value 2'],
            [x[0] for x in terrain_doodad_operation_items]
        )

        node_tree.links.new(value_socket, output_node.inputs['Output'])

    return ensure_geometry_node_tree('BDK Terrain Doodad Paint Operation', items, build_function)


def ensure_terrain_doodad_paint_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketInt', 'Interpolation Type'),
        ('INPUT', 'NodeSocketInt', 'Noise Type'),
        ('INPUT', 'NodeSocketFloat', 'Distance'),
        ('INPUT', 'NodeSocketFloat', 'Radius'),
        ('INPUT', 'NodeSocketFloat', 'Falloff Radius'),
        ('INPUT', 'NodeSocketFloat', 'Strength'),
        ('INPUT', 'NodeSocketFloat', 'Distance Noise Factor'),
        ('INPUT', 'NodeSocketFloat', 'Distance Noise Distortion'),
        ('INPUT', 'NodeSocketFloat', 'Distance Noise Offset'),
        ('INPUT', 'NodeSocketBool', 'Use Distance Noise'),
        ('OUTPUT', 'NodeSocketFloat', 'Value'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

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

        # Add the distance noise node group.
        distance_noise_group_node = node_tree.nodes.new(type='GeometryNodeGroup')
        distance_noise_group_node.node_tree = ensure_distance_noise_node_group()

        # Input
        node_tree.links.new(input_node.outputs['Distance'], distance_noise_group_node.inputs['Distance'])
        node_tree.links.new(input_node.outputs['Noise Type'], distance_noise_group_node.inputs['Type'])
        node_tree.links.new(input_node.outputs['Distance Noise Factor'], distance_noise_group_node.inputs['Factor'])
        node_tree.links.new(input_node.outputs['Distance Noise Distortion'],
                            distance_noise_group_node.inputs['Distortion'])
        node_tree.links.new(input_node.outputs['Distance Noise Offset'], distance_noise_group_node.inputs['Offset'])
        node_tree.links.new(input_node.outputs['Use Distance Noise'], distance_noise_group_node.inputs['Use Noise'])
        node_tree.links.new(input_node.outputs['Interpolation Type'],
                            interpolation_group_node.inputs['Interpolation Type'])
        node_tree.links.new(input_node.outputs['Strength'], strength_multiply_node.inputs[1])

        # Internal
        node_tree.links.new(divide_node.outputs['Value'], interpolation_group_node.inputs['Value'])
        node_tree.links.new(interpolation_group_node.outputs['Value'], strength_multiply_node.inputs[0])
        node_tree.links.new(distance_noise_group_node.outputs['Distance'], subtract_node.inputs[0])

        # Output
        node_tree.links.new(strength_multiply_node.outputs['Value'], output_node.inputs['Value'])

    return ensure_geometry_node_tree('BDK Doodad Paint', items, build_function)


def ensure_distance_to_curve_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Curve'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance'),
    )

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

    return ensure_geometry_node_tree('BDK Distance to Curve', items, build_function)


def ensure_distance_to_points_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Points'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),  # TODO
        ('OUTPUT', 'NodeSocketFloat', 'Distance'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
        geometry_proximity_node = node_tree.nodes.new(type='GeometryNodeProximity')
        geometry_proximity_node.target_element = 'POINTS'

        # TODO: transform geometry might be slower, might be better to use a set position node and strip out the Z.
        transform_geometry_node = node_tree.nodes.new(type='GeometryNodeTransform')
        transform_geometry_node.inputs['Scale'].default_value = (1.0, 1.0, 0.0)

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'VECTOR'

        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        # Input
        node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Points'], transform_geometry_node.inputs['Geometry'])

        # Internal
        node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node.inputs['X'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node.inputs['Y'])
        node_tree.links.new(combine_xyz_node.outputs['Vector'], switch_node.inputs['False'])
        node_tree.links.new(position_node.outputs['Position'], switch_node.inputs['True'])
        node_tree.links.new(switch_node.outputs['Output'], geometry_proximity_node.inputs['Source Position'])
        node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])
        node_tree.links.new(transform_geometry_node.outputs['Geometry'], geometry_proximity_node.inputs['Target'])

        # Output
        node_tree.links.new(geometry_proximity_node.outputs['Distance'], output_node.inputs['Distance'])

    return ensure_geometry_node_tree('BDK Distance to Points', items, build_function)


def ensure_distance_to_mesh_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('INPUT', 'NodeSocketInt', 'Element Mode'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

        transform_geometry_node = node_tree.nodes.new(type='GeometryNodeTransform')
        transform_geometry_node.inputs['Scale'].default_value = (1.0, 1.0, 0.0)

        switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        switch_node.input_type = 'VECTOR'

        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

        target_elements = ['POINTS', 'EDGES', 'FACES']
        distance_sockets = []

        for target_element in target_elements:
            geometry_proximity_node = node_tree.nodes.new(type='GeometryNodeProximity')
            geometry_proximity_node.target_element = target_element

            node_tree.links.new(switch_node.outputs['Output'], geometry_proximity_node.inputs['Source Position'])
            node_tree.links.new(transform_geometry_node.outputs['Geometry'], geometry_proximity_node.inputs['Target'])

            distance_sockets.append(geometry_proximity_node.outputs['Distance'])

        geometry_distance_socket = add_geometry_node_switch_nodes(node_tree, input_node.outputs['Element Mode'],
                                                                  distance_sockets, 'FLOAT')

        # Input
        node_tree.links.new(input_node.outputs['Is 3D'], switch_node.inputs['Switch'])
        node_tree.links.new(input_node.outputs['Geometry'], transform_geometry_node.inputs['Geometry'])

        # Internal
        node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node.inputs['X'])
        node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node.inputs['Y'])
        node_tree.links.new(combine_xyz_node.outputs['Vector'], switch_node.inputs['False'])
        node_tree.links.new(position_node.outputs['Position'], switch_node.inputs['True'])
        node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])

        # Output
        node_tree.links.new(geometry_distance_socket, output_node.inputs['Distance'])

    return ensure_geometry_node_tree('BDK Distance to Mesh', items, build_function)


def ensure_distance_to_empty_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketVector', 'Location'),
        ('INPUT', 'NodeSocketBool', 'Is 3D'),
        ('OUTPUT', 'NodeSocketFloat', 'Distance'),
    )

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

    return ensure_geometry_node_tree('BDK Distance to Empty', items, build_function)


def create_terrain_doodad_object(context: Context, terrain_info_object: Object, object_type: str = 'CURVE') -> Object:
    """
    Creates a terrain doodad of the specified type.
    Note that this function does not add the terrain doodad object to the scene. That is the responsibility of the caller.
    :param context:
    :param terrain_info_object:
    :param object_type: The type of object to create. Valid values are 'CURVE', 'MESH' and 'EMPTY'
    :return:
    """
    match object_type:
        case 'CURVE':
            object_data = bpy.data.curves.new(name=uuid4().hex, type='CURVE')
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
        case 'EMPTY':
            object_data = None
        case 'MESH':
            object_data = bpy.data.meshes.new(name=uuid4().hex)
            # Create a plane using bmesh.
            bm = bmesh.new()
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=meters_to_unreal(1.0))
            bm.to_mesh(object_data)
            del bm
        case _:
            # Unreachable.
            raise NotImplementedError(f'{object_type} is unhandled')

    bpy_object = bpy.data.objects.new(name='Doodad', object_data=object_data)

    if object_type == 'EMPTY':
        bpy_object.empty_display_type = 'SPHERE'
        bpy_object.empty_display_size = meters_to_unreal(1.0)
        # Set the delta transform to the terrain info object's rotation.
        bpy_object.delta_rotation_euler = (0, 0, 0)
    elif object_type == 'MESH':
        bpy_object.display_type = 'WIRE'

    # Set the location of the curve object to the 3D cursor.
    bpy_object.location = context.scene.cursor.location

    # Convert the newly made object to a terrain doodad.
    convert_object_to_terrain_doodad(bpy_object, terrain_info_object)

    return bpy_object


def convert_object_to_terrain_doodad(obj: Object, terrain_info_object: Object):
    # Hide from rendering and Cycles passes.
    obj.hide_render = True

    # Disable all ray visibility settings (this stops it from being visible in Cycles rendering in the viewport).
    obj.visible_camera = False
    obj.visible_diffuse = False
    obj.visible_glossy = False
    obj.visible_transmission = False
    obj.visible_volume_scatter = False
    obj.visible_shadow = False

    terrain_doodad_id = uuid4().hex
    obj.bdk.type = 'TERRAIN_DOODAD'
    obj.bdk.terrain_doodad.id = terrain_doodad_id
    obj.bdk.terrain_doodad.terrain_info_object = terrain_info_object
    obj.bdk.terrain_doodad.object = obj
    obj.bdk.terrain_doodad.node_tree = bpy.data.node_groups.new(name=terrain_doodad_id, type='GeometryNodeTree')

    obj.show_in_front = True
    obj.lock_location = (False, False, True)
    obj.lock_rotation = (True, True, False)


def get_terrain_doodads_for_terrain_info_object(context: Context, terrain_info_object: Object) ->\
        List['BDK_PG_terrain_doodad']:
    return [obj.bdk.terrain_doodad for obj in context.scene.objects if
            obj.bdk.type == 'TERRAIN_DOODAD' and obj.bdk.terrain_doodad.terrain_info_object == terrain_info_object]


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

    if terrain_info.doodad_mask_modifier_name == '':
        terrain_info.doodad_mask_modifier_name = uuid.uuid4().hex

    # Gather and sort the terrain doodad by the sort order and ID.
    terrain_doodads = get_terrain_doodads_for_terrain_info_object(context, terrain_info.terrain_info_object)
    terrain_doodads.sort(key=lambda x: (x.sort_order, x.id))

    # Ensure that the terrain info object has the required pass modifiers.
    modifier_names = [
        terrain_info.doodad_sculpt_modifier_name,
        terrain_info.doodad_attribute_modifier_name,
        terrain_info.doodad_paint_modifier_name,
        terrain_info.doodad_deco_modifier_name,
        terrain_info.doodad_mask_modifier_name,
    ]

    for modifier_name in modifier_names:
        if modifier_name not in terrain_info_object.modifiers:
            modifier = terrain_info_object.modifiers.new(name=modifier_name, type='NODES')
            modifier.show_on_cage = True

    # Ensure the node groups for the pass modifiers.
    modifiers = terrain_info_object.modifiers
    modifiers[terrain_info.doodad_sculpt_modifier_name].node_group = _ensure_terrain_doodad_sculpt_modifier_node_group(
        terrain_info.doodad_sculpt_modifier_name, terrain_info, terrain_doodads)
    modifiers[
        terrain_info.doodad_attribute_modifier_name].node_group = _ensure_terrain_doodad_attribute_modifier_node_group(
        terrain_info.doodad_attribute_modifier_name, terrain_info, terrain_doodads)
    modifiers[terrain_info.doodad_paint_modifier_name].node_group = _ensure_terrain_doodad_paint_modifier_node_group(
        terrain_info.doodad_paint_modifier_name, terrain_info, terrain_doodads)

    modifiers[terrain_info.doodad_deco_modifier_name].node_group = _ensure_terrain_doodad_deco_modifier_node_group(
        terrain_info.doodad_deco_modifier_name, terrain_info, terrain_doodads)

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
    modifier_ids.extend(map(lambda deco_layer: deco_layer.modifier_name,
                            terrain_info.deco_layers))  # TODO: something weird going down here, we shouldn't be using the deco layer ID
    modifier_ids.append(terrain_info.doodad_deco_modifier_name)
    modifier_ids.append(terrain_info.doodad_mask_modifier_name)

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


def _add_terrain_info_driver(struct: bpy_struct, terrain_info: 'BDK_PG_terrain_info', data_path: str,
                             path: str = 'default_value'):
    driver = struct.driver_add(path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = terrain_info.terrain_info_object
    var.targets[0].data_path = f"bdk.terrain_info.{data_path}"


def _add_terrain_doodad_driver(struct: bpy_struct, terrain_doodad: 'BDK_PG_terrain_doodad', data_path: str,
                               path: str = 'default_value'):
    driver = struct.driver_add(path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = terrain_doodad.object
    var.targets[0].data_path = f"bdk.terrain_doodad.{data_path}"


# TODO: combine the two functions below into something more unified.
def add_distance_to_points_nodes(node_tree: NodeTree, object_info_node: Node) -> NodeSocket:
    distance_to_points_node = node_tree.nodes.new(type='GeometryNodeGroup')
    distance_to_points_node.node_tree = ensure_distance_to_points_node_group()

    node_tree.links.new(object_info_node.outputs['Geometry'], distance_to_points_node.inputs['Points'])

    return distance_to_points_node.outputs['Distance']


def add_distance_to_doodad_layer_nodes(node_tree: NodeTree, layer, layer_type: str,
                                       terrain_doodad_object_info_node: Node,
                                       element_mode_socket: NodeSocket,
                                       ) -> NodeSocket:
    terrain_doodad = layer.terrain_doodad_object.bdk.terrain_doodad

    match terrain_doodad.object.type:
        case 'CURVE':
            curve_modifier_node = node_tree.nodes.new(type='GeometryNodeGroup')
            curve_modifier_node.node_tree = ensure_curve_modifier_node_tree()

            distance_to_curve_node = node_tree.nodes.new(type='GeometryNodeGroup')
            distance_to_curve_node.node_tree = ensure_distance_to_curve_node_group()

            def add_curve_modifier_driver(input_name: str, data_path: str):
                add_doodad_layer_driver(curve_modifier_node.inputs[input_name], layer, layer_type, data_path)

            # Drivers
            add_curve_modifier_driver('Is Curve Reversed', 'is_curve_reversed')
            add_curve_modifier_driver('Trim Mode', 'curve_trim_mode')
            add_curve_modifier_driver('Trim Factor Start', 'curve_trim_factor_start')
            add_curve_modifier_driver('Trim Factor End', 'curve_trim_factor_end')
            add_curve_modifier_driver('Trim Length Start', 'curve_trim_length_start')
            add_curve_modifier_driver('Trim Length End', 'curve_trim_length_end')
            add_curve_modifier_driver('Normal Offset', 'curve_normal_offset')

            # Links
            node_tree.links.new(terrain_doodad_object_info_node.outputs['Geometry'],
                                curve_modifier_node.inputs['Curve'])
            node_tree.links.new(curve_modifier_node.outputs['Curve'], distance_to_curve_node.inputs['Curve'])

            return distance_to_curve_node.outputs['Distance']
        case 'MESH':
            # TODO: set up a switch for points vs. faces
            distance_to_mesh_node_group = ensure_distance_to_mesh_node_group()

            # Add a new node group node.
            distance_to_mesh_node = node_tree.nodes.new(type='GeometryNodeGroup')
            distance_to_mesh_node.node_tree = distance_to_mesh_node_group

            node_tree.links.new(element_mode_socket, distance_to_mesh_node.inputs['Element Mode'])
            node_tree.links.new(terrain_doodad_object_info_node.outputs['Geometry'],
                                distance_to_mesh_node.inputs['Geometry'])

            return distance_to_mesh_node.outputs['Distance']
        case 'EMPTY':
            distance_to_empty_node_group = ensure_distance_to_empty_node_group()

            distance_to_empty_node = node_tree.nodes.new(type='GeometryNodeGroup')
            distance_to_empty_node.node_tree = distance_to_empty_node_group

            node_tree.links.new(terrain_doodad_object_info_node.outputs['Location'],
                                distance_to_empty_node.inputs['Location'])

            return distance_to_empty_node.outputs['Distance']
        case _:
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


def ensure_sculpt_operation_node_group() -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketFloat', 'Value 1'),
        ('INPUT', 'NodeSocketFloat', 'Value 2'),
        ('INPUT', 'NodeSocketFloat', 'Depth'),
        ('INPUT', 'NodeSocketInt', 'Operation'),
        ('OUTPUT', 'NodeSocketFloat', 'Output'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        # Nodes
        set_mix_node = node_tree.nodes.new(type='ShaderNodeMix')
        set_socket = set_mix_node.outputs['Result']

        add_node = node_tree.nodes.new(type='ShaderNodeMath')
        add_node.operation = 'ADD'
        add_socket = add_node.outputs['Value']

        add_multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
        add_multiply_node.operation = 'MULTIPLY'

        # Links
        node_tree.links.new(input_node.outputs['Value 2'], add_multiply_node.inputs[0])
        node_tree.links.new(input_node.outputs['Depth'], add_multiply_node.inputs[1])
        node_tree.links.new(input_node.outputs['Value 1'], add_node.inputs[0])
        node_tree.links.new(add_multiply_node.outputs['Value'], add_node.inputs[1])
        node_tree.links.new(input_node.outputs['Value 2'], set_mix_node.inputs['Factor'])
        node_tree.links.new(input_node.outputs['Value 1'], set_mix_node.inputs['A'])
        node_tree.links.new(input_node.outputs['Depth'], set_mix_node.inputs['B'])

        operation_result_socket = add_geometry_node_switch_nodes(node_tree, input_node.outputs['Operation'],
                                                                 [add_socket, set_socket], 'FLOAT')

        node_tree.links.new(operation_result_socket, output_node.inputs['Output'])

    return ensure_geometry_node_tree('BDK Sculpt Operation', items, build_function)


def get_terrain_doodad_layer_geometry_object(terrain_doodad_layer):
    match terrain_doodad_layer.geometry_source:
        case 'DOODAD':
            return terrain_doodad_layer.terrain_doodad_object
        case 'SCATTER_LAYER':
            terrain_doodad = terrain_doodad_layer.terrain_doodad_object.bdk.terrain_doodad
            scatter_layer = get_terrain_doodad_scatter_layer_by_id(terrain_doodad,
                                                                   terrain_doodad_layer.scatter_layer_id)
            if scatter_layer is None:
                return None
            return scatter_layer.planter_object
        case _:
            raise Exception(f"Unknown geometry source: {terrain_doodad_layer.geometry_source}")


def add_terrain_doodad_sculpt_layer_value_nodes(node_tree: NodeTree,
                                                sculpt_layer: 'BDK_PG_terrain_doodad_sculpt_layer') -> Optional[
    NodeSocket]:
    geometry_object = get_terrain_doodad_layer_geometry_object(sculpt_layer)

    if geometry_object is None:
        return None

    geometry_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    geometry_object_info_node.transform_space = 'RELATIVE'
    geometry_object_info_node.inputs[0].default_value = geometry_object

    element_mode_integer_node = node_tree.nodes.new(type='FunctionNodeInputInt')
    element_mode_integer_node.label = 'Element Mode'
    add_doodad_sculpt_layer_driver(element_mode_integer_node, sculpt_layer, 'element_mode', 'integer')

    element_mode_socket = element_mode_integer_node.outputs['Integer']

    sculpt_value_node = node_tree.nodes.new(type='GeometryNodeGroup')
    sculpt_value_node.node_tree = ensure_sculpt_value_node_group()

    # TODO: this is re-stated in the paint layer code, we should probably refactor this so that it's a common function.
    # Depending on the geometry source, we either use the doodad's geometry or the point cloud of a scatter layer
    # planter object.
    match sculpt_layer.geometry_source:
        case 'DOODAD':
            distance_socket = add_distance_to_doodad_layer_nodes(node_tree, sculpt_layer, 'SCULPT',
                                                                 geometry_object_info_node, element_mode_socket)
        case 'SCATTER_LAYER':
            distance_socket = add_distance_to_points_nodes(node_tree, geometry_object_info_node)
        case _:
            raise Exception(f"Unknown geometry source: {sculpt_layer.geometry_source}")

    def add_sculpt_value_node_driver(input_name: str, path: str):
        add_doodad_sculpt_layer_driver(sculpt_value_node.inputs[input_name], sculpt_layer, path)

    # Drivers
    add_sculpt_value_node_driver('Radius', 'radius')
    add_sculpt_value_node_driver('Falloff Radius', 'falloff_radius')
    add_sculpt_value_node_driver('Noise Strength', 'noise_strength')
    add_sculpt_value_node_driver('Perlin Noise Roughness', 'perlin_noise_roughness')
    add_sculpt_value_node_driver('Perlin Noise Distortion', 'perlin_noise_distortion')
    add_sculpt_value_node_driver('Perlin Noise Scale', 'perlin_noise_scale')
    add_sculpt_value_node_driver('Perlin Noise Lacunarity', 'perlin_noise_lacunarity')
    add_sculpt_value_node_driver('Perlin Noise Detail', 'perlin_noise_detail')
    add_sculpt_value_node_driver('Use Noise', 'use_noise')
    add_sculpt_value_node_driver('Noise Radius Factor', 'noise_radius_factor')
    add_sculpt_value_node_driver('Interpolation Type', 'interpolation_type')
    add_sculpt_value_node_driver('Noise Type', 'noise_type')

    node_tree.links.new(distance_socket, sculpt_value_node.inputs['Distance'])

    return sculpt_value_node.outputs['Value']


def _add_sculpt_layers_to_node_tree(node_tree: NodeTree, z_socket: Optional[NodeSocket], terrain_doodad) -> NodeSocket:
    """
    Adds the nodes for a doodad's sculpt layers.
    :param node_tree: The node tree to add the nodes to.
    :param z_socket: The incoming z value socket.
    :param terrain_doodad: The terrain doodad to add the sculpt layers for.
    :return: The Z value output socket (either the one passed in or the one from the last node added).
    """
    # Now chain the node components together.
    for sculpt_layer in terrain_doodad.sculpt_layers:
        value_socket = add_terrain_doodad_sculpt_layer_value_nodes(node_tree, sculpt_layer)

        if value_socket is None:
            continue

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'FLOAT'

        frozen_named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
        frozen_named_attribute_node.inputs['Name'].default_value = sculpt_layer.frozen_attribute_id

        is_frozen_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        is_frozen_switch_node.input_type = 'FLOAT'

        sculpt_operation_node = node_tree.nodes.new(type='GeometryNodeGroup')
        sculpt_operation_node.node_tree = ensure_sculpt_operation_node_group()

        # Drivers
        _add_terrain_doodad_driver(is_frozen_switch_node.inputs['Switch'], terrain_doodad, 'is_frozen')

        add_doodad_sculpt_layer_driver(mute_switch_node.inputs['Switch'], sculpt_layer, 'mute')
        add_doodad_sculpt_layer_driver(sculpt_operation_node.inputs['Operation'], sculpt_layer, 'operation')
        add_doodad_sculpt_layer_driver(sculpt_operation_node.inputs['Depth'], sculpt_layer, 'depth')

        # Links
        node_tree.links.new(sculpt_operation_node.outputs['Output'], mute_switch_node.inputs['False'])
        node_tree.links.new(value_socket, is_frozen_switch_node.inputs['False'])
        node_tree.links.new(frozen_named_attribute_node.outputs['Attribute'], is_frozen_switch_node.inputs['True'])

        if z_socket:
            node_tree.links.new(z_socket, mute_switch_node.inputs['True'])
            node_tree.links.new(z_socket, sculpt_operation_node.inputs['Value 1'])

        node_tree.links.new(is_frozen_switch_node.outputs['Output'], sculpt_operation_node.inputs['Value 2'])

        z_socket = mute_switch_node.outputs['Output']

    return z_socket


def _ensure_terrain_doodad_sculpt_modifier_node_group(name: str, terrain_info: 'BDK_PG_terrain_info',
                                                      terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'

        position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
        separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')
        combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')
        set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

        z_socket = separate_xyz_node.outputs['Z']

        for terrain_doodad in terrain_doodads:
            ensure_terrain_doodad_freeze_attribute_ids(terrain_doodad)
            z_socket = _add_sculpt_layers_to_node_tree(node_tree, z_socket, terrain_doodad)

        # Drivers
        _add_terrain_info_driver(mute_switch_node.inputs['Switch'], terrain_info, 'is_sculpt_modifier_muted')

        # Links
        node_tree.links.new(mute_switch_node.inputs['False'], set_position_node.outputs['Geometry'])
        node_tree.links.new(mute_switch_node.inputs['True'], input_node.outputs['Geometry'])
        node_tree.links.new(separate_xyz_node.inputs['Vector'], position_node.outputs['Position'])
        node_tree.links.new(set_position_node.inputs['Position'], combine_xyz_node.outputs['Vector'])
        node_tree.links.new(set_position_node.inputs['Geometry'], input_node.outputs['Geometry'])
        node_tree.links.new(combine_xyz_node.inputs['X'], separate_xyz_node.outputs['X'])
        node_tree.links.new(combine_xyz_node.inputs['Y'], separate_xyz_node.outputs['Y'])
        node_tree.links.new(combine_xyz_node.inputs['Z'], z_socket)
        node_tree.links.new(output_node.inputs['Geometry'], mute_switch_node.outputs['Output'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def add_paint_layer_driver(struct: bpy_struct, paint_layer: 'BDK_PG_terrain_doodad_paint_layer', data_path: str,
                           path: str = 'default_value'):
    driver = struct.driver_add(path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = paint_layer.terrain_doodad_object
    var.targets[0].data_path = f"bdk.terrain_doodad.paint_layers[{paint_layer.index}].{data_path}"


def _add_terrain_doodad_paint_layer_value_nodes(node_tree: NodeTree,
                                                paint_layer: 'BDK_PG_terrain_doodad_paint_layer') -> Optional[
    NodeSocket]:
    geometry_object = get_terrain_doodad_layer_geometry_object(paint_layer)

    if geometry_object is None:
        return None

    geometry_object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    geometry_object_info_node.transform_space = 'RELATIVE'
    geometry_object_info_node.inputs[0].default_value = geometry_object

    element_mode_integer_node = node_tree.nodes.new(type='FunctionNodeInputInt')
    element_mode_integer_node.label = 'Element Mode'
    add_doodad_paint_layer_driver(element_mode_integer_node, paint_layer, 'element_mode', 'integer')
    element_mode_socket = element_mode_integer_node.outputs['Integer']

    match paint_layer.geometry_source:
        case 'DOODAD':
            distance_socket = add_distance_to_doodad_layer_nodes(node_tree, paint_layer, 'PAINT',
                                                                 geometry_object_info_node, element_mode_socket)
        case 'SCATTER_LAYER':
            distance_socket = add_distance_to_points_nodes(node_tree, geometry_object_info_node)
        case _:
            raise Exception(f"Unknown geometry source: {paint_layer.geometry_source}")

    paint_node = node_tree.nodes.new(type='GeometryNodeGroup')
    paint_node.node_tree = ensure_terrain_doodad_paint_node_group()

    add_paint_layer_driver(paint_node.inputs['Radius'], paint_layer, 'radius')
    add_paint_layer_driver(paint_node.inputs['Falloff Radius'], paint_layer, 'falloff_radius')
    add_paint_layer_driver(paint_node.inputs['Strength'], paint_layer, 'strength')
    add_paint_layer_driver(paint_node.inputs['Use Distance Noise'], paint_layer, 'use_distance_noise')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Distortion'], paint_layer, 'distance_noise_distortion')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Factor'], paint_layer, 'distance_noise_factor')
    add_paint_layer_driver(paint_node.inputs['Distance Noise Offset'], paint_layer, 'distance_noise_offset')
    add_paint_layer_driver(paint_node.inputs['Interpolation Type'], paint_layer, 'interpolation_type')
    add_paint_layer_driver(paint_node.inputs['Noise Type'], paint_layer, 'noise_type')

    node_tree.links.new(distance_socket, paint_node.inputs['Distance'])

    return paint_node.outputs['Value']


def _add_terrain_doodad_paint_layer_to_node_tree(node_tree: NodeTree,
                                                 terrain_doodad_paint_layer: 'BDK_PG_terrain_doodad_paint_layer',
                                                 operand_value_socket: Optional[NodeSocket] = None,
                                                 operation_override: Optional[str] = None) -> NodeSocket:
    paint_value_socket = _add_terrain_doodad_paint_layer_value_nodes(node_tree, terrain_doodad_paint_layer)

    if paint_value_socket is None:
        return operand_value_socket

    terrain_doodad = terrain_doodad_paint_layer.terrain_doodad_object.bdk.terrain_doodad

    frozen_named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
    frozen_named_attribute_node.inputs['Name'].default_value = terrain_doodad_paint_layer.frozen_attribute_id

    frozen_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    frozen_switch_node.input_type = 'FLOAT'
    frozen_switch_node.label = 'Frozen'

    mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    mute_switch_node.input_type = 'FLOAT'
    mute_switch_node.label = 'Mute'

    paint_operation_node = node_tree.nodes.new(type='GeometryNodeGroup')
    paint_operation_node.node_tree = ensure_terrain_doodad_paint_operation_node_group()

    if operand_value_socket is not None:
        node_tree.links.new(operand_value_socket, paint_operation_node.inputs['Value 1'])
        node_tree.links.new(operand_value_socket, mute_switch_node.inputs['True'])

    node_tree.links.new(paint_operation_node.outputs['Output'], mute_switch_node.inputs['False'])

    if operation_override is not None:
        # Handle operation override. This is used when baking.
        operation_keys = [item[0] for item in terrain_doodad_operation_items]
        paint_operation_node.inputs['Operation'].default_value = operation_keys.index(operation_override)
    else:
        add_paint_layer_driver(paint_operation_node.inputs['Operation'], terrain_doodad_paint_layer, 'operation')

    # Drivers
    _add_terrain_doodad_driver(frozen_switch_node.inputs['Switch'], terrain_doodad, 'is_frozen')
    add_paint_layer_driver(mute_switch_node.inputs['Switch'], terrain_doodad_paint_layer, 'mute')

    # Links
    node_tree.links.new(paint_value_socket, frozen_switch_node.inputs['False'])
    node_tree.links.new(frozen_named_attribute_node.outputs['Attribute'], frozen_switch_node.inputs['True'])
    node_tree.links.new(frozen_switch_node.outputs['Output'], paint_operation_node.inputs['Value 2'])

    return mute_switch_node.outputs['Output']


# TODO: this thing can probably be made generic for any layer type
def _ensure_terrain_doodad_paint_modifier_node_group(
        name: str, terrain_info: 'BDK_PG_terrain_info', terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    print(terrain_doodads)

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'

        geometry_socket = input_node.outputs['Geometry']

        # Paint Layers
        paint_layers = list(filter(lambda x: x.layer_type == 'PAINT',
                                   chain.from_iterable(map(lambda x: x.paint_layers, terrain_doodads))))
        paint_layer_ids = set(map(lambda x: x.paint_layer_id, paint_layers))

        for paint_layer_id in paint_layer_ids:
            named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
            named_attribute_node.data_type = 'FLOAT'
            named_attribute_node.inputs['Name'].default_value = paint_layer_id

            value_socket = named_attribute_node.outputs['Attribute']

            for paint_layer in filter(lambda x: x.paint_layer_id == paint_layer_id, paint_layers):
                value_socket = _add_terrain_doodad_paint_layer_to_node_tree(node_tree, paint_layer, value_socket)

            store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_named_attribute_node.data_type = 'FLOAT'
            store_named_attribute_node.domain = 'POINT'
            store_named_attribute_node.inputs['Name'].default_value = paint_layer_id

            node_tree.links.new(value_socket, store_named_attribute_node.inputs['Value'])
            node_tree.links.new(geometry_socket, store_named_attribute_node.inputs['Geometry'])

            geometry_socket = store_named_attribute_node.outputs['Geometry']

        # Drivers
        _add_terrain_info_driver(mute_switch_node.inputs['Switch'], terrain_info, 'is_paint_modifier_muted')

        # Inputs
        node_tree.links.new(input_node.outputs['Geometry'], mute_switch_node.inputs['False'])

        # Internal
        node_tree.links.new(geometry_socket, mute_switch_node.inputs['False'])

        # Outputs
        node_tree.links.new(mute_switch_node.outputs['Output'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def _ensure_terrain_doodad_deco_modifier_node_group(name: str, terrain_info: 'BDK_PG_terrain_info',
                                                    terrain_doodads: Iterable['BDK_PG_terrain_doodad']) -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'

        geometry_socket = input_node.outputs['Geometry']

        # Paint Layers
        deco_layers = list(filter(lambda x: x.layer_type == 'DECO',
                                  chain.from_iterable(map(lambda x: x.paint_layers, terrain_doodads))))
        deco_layer_ids = set(map(lambda x: x.deco_layer_id, deco_layers))

        for deco_layer_id in deco_layer_ids:
            named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
            named_attribute_node.data_type = 'FLOAT'
            named_attribute_node.inputs['Name'].default_value = deco_layer_id

            value_socket = named_attribute_node.outputs['Attribute']

            for paint_layer in filter(lambda x: x.deco_layer_id == deco_layer_id, deco_layers):
                value_socket = _add_terrain_doodad_paint_layer_to_node_tree(node_tree, paint_layer, value_socket)

            store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_named_attribute_node.data_type = 'FLOAT'
            store_named_attribute_node.domain = 'POINT'
            store_named_attribute_node.inputs['Name'].default_value = deco_layer_id

            node_tree.links.new(value_socket, store_named_attribute_node.inputs['Value'])
            node_tree.links.new(geometry_socket, store_named_attribute_node.inputs['Geometry'])

            geometry_socket = store_named_attribute_node.outputs['Geometry']

        # Drivers
        _add_terrain_info_driver(mute_switch_node.inputs['Switch'], terrain_info, 'is_deco_modifier_muted')

        # Inputs
        node_tree.links.new(input_node.outputs['Geometry'], mute_switch_node.inputs['True'])

        # Internal
        node_tree.links.new(geometry_socket, mute_switch_node.inputs['False'])

        # Outputs
        node_tree.links.new(mute_switch_node.outputs['Output'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def _ensure_terrain_doodad_attribute_modifier_node_group(
        name: str, terrain_info: 'BDK_PG_terrain_info', terrain_doodads: Iterable['BDK_PG_terrain_doodad']
) -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        mute_switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
        mute_switch_node.input_type = 'GEOMETRY'

        geometry_socket = input_node.outputs['Geometry']

        # Paint Layers
        attribute_layers = list(filter(lambda x: x.layer_type == 'ATTRIBUTE',
                                       chain.from_iterable(map(lambda x: x.paint_layers, terrain_doodads))))
        attribute_layer_ids = set(map(lambda x: x.attribute_layer_id, attribute_layers))

        for attribute_layer_id in attribute_layer_ids:
            named_attribute_node = node_tree.nodes.new(type='GeometryNodeInputNamedAttribute')
            named_attribute_node.data_type = 'FLOAT'
            named_attribute_node.inputs['Name'].default_value = attribute_layer_id

            value_socket = named_attribute_node.outputs['Attribute']

            for paint_layer in filter(lambda x: x.attribute_layer_id == attribute_layer_id, attribute_layers):
                value_socket = _add_terrain_doodad_paint_layer_to_node_tree(node_tree, paint_layer, value_socket)

            store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_named_attribute_node.data_type = 'FLOAT'
            store_named_attribute_node.domain = 'POINT'
            store_named_attribute_node.inputs['Name'].default_value = attribute_layer_id

            node_tree.links.new(value_socket, store_named_attribute_node.inputs['Value'])
            node_tree.links.new(geometry_socket, store_named_attribute_node.inputs['Geometry'])

            geometry_socket = store_named_attribute_node.outputs['Geometry']

        # Drivers
        _add_terrain_info_driver(mute_switch_node.inputs['Switch'], terrain_info, 'is_attribute_modifier_muted')

        # Inputs
        node_tree.links.new(input_node.outputs['Geometry'], mute_switch_node.inputs['True'])

        # Internal
        node_tree.links.new(geometry_socket, mute_switch_node.inputs['False'])

        # Outputs
        node_tree.links.new(mute_switch_node.outputs['Output'], output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(name, items, build_function, should_force_build=True)


def create_terrain_doodad_bake_node_tree(terrain_doodad: 'BDK_PG_terrain_doodad', layers: Set[str]) -> (
NodeTree, Dict[str, str]):
    """
    Creates a node tree for baking a terrain doodad.
    :param terrain_doodad: The terrain doodad to make a baking node tree for.
    :param layers: Set containing any of ['SCULPT', 'PAINT'].
    :return: The terrain doodad baking node tree and a mapping of the paint layer IDs to the baked attribute names.
    """
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    # Build a mapping of the paint layer IDs to the baked attribute names.
    attribute_map: Dict[str, str] = {paint_layer.id: uuid4().hex for paint_layer in terrain_doodad.paint_layers}

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        if 'SCULPT' in layers:
            # Add sculpt layers for the doodad.
            position_node = node_tree.nodes.new('GeometryNodeInputPosition')
            separate_xyz_node = node_tree.nodes.new('ShaderNodeSeparateXYZ')

            node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])

            z_socket = _add_sculpt_layers_to_node_tree(node_tree, separate_xyz_node.outputs['Z'], terrain_doodad)

            if z_socket is not None:
                set_position_node = node_tree.nodes.new('GeometryNodeSetPosition')
                combine_xyz_node = node_tree.nodes.new('ShaderNodeCombineXYZ')

                node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node.inputs['X'])
                node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node.inputs['Y'])
                node_tree.links.new(combine_xyz_node.inputs['Z'], z_socket)
                node_tree.links.new(set_position_node.inputs['Geometry'], geometry_socket)
                node_tree.links.new(set_position_node.inputs['Position'], combine_xyz_node.outputs['Vector'])

                geometry_socket = set_position_node.outputs['Geometry']

        if 'PAINT' in layers:
            # Add the paint layers for the doodad.
            for doodad_paint_layer in terrain_doodad.paint_layers:
                """
                We override the operation here because we want the influence of each layer to be additive for the bake.
                Without this, if a "SUBTRACT" operation were used, the resulting bake for the attribute would be
                completely black (painted with 0). The actual operation will be transferred to the associated node in
                the layer node tree.
                """
                store_named_attribute_node = node_tree.nodes.new('GeometryNodeStoreNamedAttribute')
                store_named_attribute_node.data_type = 'BYTE_COLOR'
                store_named_attribute_node.inputs['Name'].default_value = attribute_map[doodad_paint_layer.id]

                value_socket = _add_terrain_doodad_paint_layer_to_node_tree(
                    node_tree, doodad_paint_layer, operation_override='ADD'
                )

                node_tree.links.new(store_named_attribute_node.inputs['Value'], value_socket)
                node_tree.links.new(store_named_attribute_node.inputs['Geometry'], geometry_socket)

                geometry_socket = store_named_attribute_node.outputs['Geometry']

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(uuid.uuid4().hex, items, build_function, should_force_build=True), attribute_map


def ensure_terrain_doodad_freeze_attribute_ids(terrain_doodad: 'BDK_PG_terrain_doodad'):
    """
    Ensures that all the freeze attribute IDs are set for the given terrain doodad.
    This is only used because previous versions didn't have this attribute. This can be removed in the future.
    :param terrain_doodad:
    :return:
    """
    for sculpt_layer in terrain_doodad.sculpt_layers:
        if sculpt_layer.frozen_attribute_id == '':
            sculpt_layer.frozen_attribute_id = uuid4().hex

    for paint_layer in terrain_doodad.paint_layers:
        if paint_layer.frozen_attribute_id == '':
            paint_layer.frozen_attribute_id = uuid4().hex


def ensure_terrain_doodad_freeze_node_group(terrain_doodad: 'BDK_PG_terrain_doodad') -> NodeTree:
    items = (
        ('INPUT', 'NodeSocketGeometry', 'Geometry'),
        ('OUTPUT', 'NodeSocketGeometry', 'Geometry'),
    )

    ensure_terrain_doodad_freeze_attribute_ids(terrain_doodad)

    def build_function(node_tree: NodeTree):
        input_node, output_node = ensure_input_and_output_nodes(node_tree)

        geometry_socket = input_node.outputs['Geometry']

        for sculpt_layer in terrain_doodad.sculpt_layers:
            store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_named_attribute_node.domain = 'POINT'
            store_named_attribute_node.data_type = 'FLOAT'
            store_named_attribute_node.inputs['Name'].default_value = sculpt_layer.frozen_attribute_id

            value_socket = add_terrain_doodad_sculpt_layer_value_nodes(node_tree, sculpt_layer)

            node_tree.links.new(geometry_socket, store_named_attribute_node.inputs['Geometry'])
            node_tree.links.new(value_socket, store_named_attribute_node.inputs['Value'])

            geometry_socket = store_named_attribute_node.outputs['Geometry']

        for paint_layer in terrain_doodad.paint_layers:
            store_named_attribute_node = node_tree.nodes.new(type='GeometryNodeStoreNamedAttribute')
            store_named_attribute_node.domain = 'POINT'
            store_named_attribute_node.data_type = 'FLOAT'
            store_named_attribute_node.inputs['Name'].default_value = paint_layer.frozen_attribute_id

            value_socket = _add_terrain_doodad_paint_layer_value_nodes(node_tree, paint_layer)

            node_tree.links.new(geometry_socket, store_named_attribute_node.inputs['Geometry'])
            node_tree.links.new(value_socket, store_named_attribute_node.inputs['Value'])

            geometry_socket = store_named_attribute_node.outputs['Geometry']

        node_tree.links.new(geometry_socket, output_node.inputs['Geometry'])

    return ensure_geometry_node_tree(f'BDK Terrain Doodad Freeze {terrain_doodad.id}', items, build_function,
                                     should_force_build=True)
