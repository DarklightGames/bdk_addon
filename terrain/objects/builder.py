from typing import cast

import bpy
from uuid import uuid4
from bpy.types import NodeTree, Context, Object, NodeSocket, Node

from .components import TerrainObjectSculptComponent, CustomPropertyAttribute, TerrainObjectPaintComponent
from .definitions import TerrainObjectDefinition
from ...units import meters_to_unreal


def add_driver_to_node(node_socket: Node, path: str, target_object: Object, data_path: str):
    driver = node_socket.driver_add(path).driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = target_object
    var.targets[0].data_path = f"[\"{data_path}\"]"


def add_driver_to_node_socket(node_socket: NodeSocket, target_object: Object, data_path: str):
    driver = node_socket.driver_add('default_value').driver
    driver.type = 'AVERAGE'
    var = driver.variables.new()
    var.name = data_path
    var.type = 'SINGLE_PROP'
    var.targets[0].id = target_object
    var.targets[0].data_path = f"[\"{data_path}\"]"


def create_distance_to_curve_node_group(terrain_object: Object) -> NodeTree:
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')
    node_tree.inputs.new('NodeSocketGeometry', 'Curve')
    node_tree.outputs.new('NodeSocketFloat', 'Distance')

    # Create input and output nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

    # Add a curve to mesh node.
    curve_to_mesh_node = node_tree.nodes.new(type='GeometryNodeCurveToMesh')

    # Add a geometry proximity node.
    geometry_proximity_node = node_tree.nodes.new(type='GeometryNodeProximity')
    geometry_proximity_node.target_element = 'EDGES'

    # Link the geometry output of the object info node to the geometry input of the curve to mesh node.
    node_tree.links.new(input_node.outputs['Curve'], curve_to_mesh_node.inputs['Curve'])

    # Link the mesh output of the curve to mesh node to the geometry input of the proximity node.
    node_tree.links.new(curve_to_mesh_node.outputs['Mesh'], geometry_proximity_node.inputs['Target'])

    # Create a value node and add a driver mapping the "radius" custom property of the terrain object.
    radius_value_node = node_tree.nodes.new(type='ShaderNodeValue')
    radius_value_node.label = 'radius'
    add_driver_to_node_socket(radius_value_node.outputs[0], terrain_object, 'radius')

    # Add a divide math node.
    divide_node = node_tree.nodes.new(type='ShaderNodeMath')
    divide_node.operation = 'DIVIDE'
    divide_node.use_clamp = True

    # Link the distance output of the geometry proximity node to the first input of the divide node.
    node_tree.links.new(geometry_proximity_node.outputs['Distance'], divide_node.inputs[0])

    # Link the radius value node to the second input of the divide node.
    node_tree.links.new(radius_value_node.outputs['Value'], divide_node.inputs[1])

    # Add a subtract node.
    subtract_node = node_tree.nodes.new(type='ShaderNodeMath')
    subtract_node.operation = 'SUBTRACT'
    subtract_node.inputs[0].default_value = 1.0

    # Link the divide node to the second input of the subtract node.
    node_tree.links.new(divide_node.outputs['Value'], subtract_node.inputs[1])

    # Link subtract node value output to the distance output of the node group.
    node_tree.links.new(subtract_node.outputs['Value'], output_node.inputs['Distance'])

    # Add a new Position and Separate XYZ node.
    position_node = node_tree.nodes.new(type='GeometryNodeInputPosition')
    separate_xyz_node = node_tree.nodes.new(type='ShaderNodeSeparateXYZ')

    # Link the position node to the input of the separate XYZ node.
    node_tree.links.new(position_node.outputs['Position'], separate_xyz_node.inputs['Vector'])

    switch_node = node_tree.nodes.new(type='GeometryNodeSwitch')
    switch_node.input_type = 'FLOAT'

    # Add a new boolean node.
    boolean_node = node_tree.nodes.new(type='FunctionNodeInputBool')
    add_driver_to_node(boolean_node, 'boolean', terrain_object, 'is_3d')

    # Link the output of the boolean node to the switch input of the switch node.
    node_tree.links.new(boolean_node.outputs['Boolean'], switch_node.inputs['Switch'])

    # Link the Z output of the separate XYZ node to the True input of the switch node.
    node_tree.links.new(separate_xyz_node.outputs['Z'], switch_node.inputs['True'])

    combine_xyz_node_2 = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

    # Link the X and Y outputs of the separate XYZ node to the X and Y inputs of the combine XYZ node.
    node_tree.links.new(separate_xyz_node.outputs['X'], combine_xyz_node_2.inputs['X'])
    node_tree.links.new(separate_xyz_node.outputs['Y'], combine_xyz_node_2.inputs['Y'])
    node_tree.links.new(switch_node.outputs['Output'], combine_xyz_node_2.inputs['Z'])

    # Link the output of the combine XYZ node to the source position input of the geometry proximity node.
    node_tree.links.new(combine_xyz_node_2.outputs['Vector'], geometry_proximity_node.inputs['Source Position'])

    return node_tree


def create_sculpt_node_group(terrain_object: Object) -> NodeTree:
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')
    node_tree.inputs.new('NodeSocketGeometry', 'Geometry')
    node_tree.inputs.new('NodeSocketFloat', 'Distance')
    node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

    # Create the input nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')

    # Create the output nodes.
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

    # Create a Float Curve node.
    float_curve_node = node_tree.nodes.new(type='ShaderNodeFloatCurve')
    float_curve_node.mapping.curves[0].points[0].location = (0.0, 0.5)
    float_curve_node.mapping.curves[0].points[1].location = (1.0, 0.0)

    # Link subtract node to the value input of the float curve node.
    node_tree.links.new(input_node.outputs['Distance'], float_curve_node.inputs['Value'])

    # Add another subtract node.
    subtract_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
    subtract_node_2.operation = 'SUBTRACT'
    subtract_node_2.inputs[1].default_value = 0.5

    # Link the float curve node to the first input of the subtract node.
    node_tree.links.new(float_curve_node.outputs['Value'], subtract_node_2.inputs[0])

    # Create a new value node and add a driver mapping to the depth custom property of the terrain object.
    depth_node = node_tree.nodes.new(type='ShaderNodeValue')
    depth_node.label = 'depth'
    add_driver_to_node_socket(depth_node.outputs[0], terrain_object, 'depth')

    # Add a new multiply node.
    multiply_node = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node.operation = 'MULTIPLY'

    # Link the values of the second subtract node and the depth node to the inputs of the multiply node.
    node_tree.links.new(subtract_node_2.outputs['Value'], multiply_node.inputs[0])
    node_tree.links.new(depth_node.outputs['Value'], multiply_node.inputs[1])

    # Add a new multiply node that multiplies the output of the previous multiply node by 2.
    multiply_node_2 = node_tree.nodes.new(type='ShaderNodeMath')
    multiply_node_2.operation = 'MULTIPLY'
    multiply_node_2.inputs[1].default_value = 2.0
    node_tree.links.new(multiply_node.outputs['Value'], multiply_node_2.inputs[0])

    # Add a combine XYZ node.
    combine_xyz_node = node_tree.nodes.new(type='ShaderNodeCombineXYZ')

    # Link the output of the second multiply node to the Z input of the combine XYZ node.
    node_tree.links.new(multiply_node_2.outputs['Value'], combine_xyz_node.inputs['Z'])

    # Add a Set Position node.
    set_position_node = node_tree.nodes.new(type='GeometryNodeSetPosition')

    # Link the output of the combine XYZ node to the offset input of the set position node.
    node_tree.links.new(combine_xyz_node.outputs['Vector'], set_position_node.inputs['Offset'])

    # Link the geometry socket of the input to the output through the set position node.
    node_tree.links.new(input_node.outputs['Geometry'], set_position_node.inputs['Geometry'])
    node_tree.links.new(set_position_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return node_tree


def create_paint_node_group(terrain_object: Object) -> NodeTree:
    # Create a new node group.
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')
    node_tree.inputs.new('NodeSocketGeometry', 'Geometry')
    node_tree.inputs.new('NodeSocketFloat', 'Distance')
    node_tree.inputs.new('NodeSocketString', 'Attribute')
    node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

    # Create the input and output nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

    # Pass the geometry from the input to the output.
    node_tree.links.new(input_node.outputs['Geometry'], output_node.inputs['Geometry'])

    return node_tree


def create_terrain_object_geometry_node_group(terrain_object: Object,
                                              terrain_object_definition: TerrainObjectDefinition) -> NodeTree:
    node_tree = bpy.data.node_groups.new(name=uuid4().hex, type='GeometryNodeTree')
    node_tree.inputs.new('NodeSocketGeometry', 'Geometry')
    node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

    # Create the input nodes.
    input_node = node_tree.nodes.new(type='NodeGroupInput')

    # Create the output nodes.
    output_node = node_tree.nodes.new(type='NodeGroupOutput')

    # Add an object info node and set the object to the terrain object.
    object_info_node = node_tree.nodes.new(type='GeometryNodeObjectInfo')
    object_info_node.inputs[0].default_value = terrain_object
    object_info_node.transform_space = 'RELATIVE'

    # Create a new distance to curve node group.
    distance_to_curve_node_group = create_distance_to_curve_node_group(terrain_object)

    # Add a new node group node.
    distance_to_curve_node = node_tree.nodes.new(type='GeometryNodeGroup')
    distance_to_curve_node.node_tree = distance_to_curve_node_group
    distance_to_curve_node.label = 'Distance to Curve'

    geometry_node_socket = input_node.outputs['Geometry']

    # Now chain the node components together.
    for component in terrain_object_definition.components:
        if type(component) == TerrainObjectSculptComponent:
            sculpt_node_group = create_sculpt_node_group(terrain_object)
            sculpt_node = node_tree.nodes.new(type='GeometryNodeGroup')
            sculpt_node.node_tree = sculpt_node_group
            sculpt_node.label = 'Sculpt'

            # Link the geometry socket of the object info node to the geometry socket of the sculpt node.
            node_tree.links.new(geometry_node_socket, sculpt_node.inputs['Geometry'])
            node_tree.links.new(distance_to_curve_node.outputs['Distance'], sculpt_node.inputs['Distance'])
            node_tree.links.new(object_info_node.outputs['Geometry'], distance_to_curve_node.inputs['Curve'])

            geometry_node_socket = sculpt_node.outputs['Geometry']
        elif type(component) == TerrainObjectPaintComponent:
            paint_node_group = create_paint_node_group(terrain_object)
            paint_node = node_tree.nodes.new(type='GeometryNodeGroup')
            paint_node.node_tree = paint_node_group
            paint_node.label = 'Paint'

            node_tree.links.new(geometry_node_socket, paint_node.inputs['Geometry'])
            node_tree.links.new(distance_to_curve_node.outputs['Distance'], paint_node.inputs['Distance'])
            node_tree.links.new(object_info_node.outputs['Geometry'], distance_to_curve_node.inputs['Curve'])

            geometry_node_socket = paint_node.outputs['Geometry']

    # Link the last geometry node socket to the output node's geometry socket.
    node_tree.links.new(geometry_node_socket, output_node.inputs['Geometry'])

    return node_tree


def create_terrain_object(context: Context,
                          terrain_object_definition: TerrainObjectDefinition,
                          terrain_info_object: Object) -> Object:
    """
    Creates a terrain object from the given definition and connects it to the given terrain info object. Note that this
    function does not add the terrain object to the scene. That is the responsibility of the caller.
    :param context:
    :param terrain_object_definition:
    :param terrain_info_object:
    :return:
    """
    name = uuid4().hex
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    spline = curve_data.splines.new(type='BEZIER')

    # Add some points to the spline.
    spline.bezier_points.add(count=1)

    # Add a set of meandering points.
    for i, point in enumerate(spline.bezier_points):
        point.co = (i, 0, 0)
        point.handle_left = (i - 0.25, -0.25, 0)
        point.handle_right = (i + 0.25, 0.25, 0)

    # Scale the points.
    for point in spline.bezier_points:
        point.co *= meters_to_unreal(5.0)
        point.handle_left *= meters_to_unreal(5.0)
        point.handle_right *= meters_to_unreal(5.0)

    curve_object = bpy.data.objects.new(name=name, object_data=curve_data)
    curve_object.show_in_front = True

    # Add custom properties from the terrain object definition.
    for key, value in terrain_object_definition.properties.items():
        if type(value) is CustomPropertyAttribute:
            value = cast(CustomPropertyAttribute, value)
            curve_object[key] = str(value.name)
        else:
            curve_object[key] = value

    # Set the location of the curve object to the 3D cursor.
    curve_object.location = context.scene.cursor.location

    # Add a geometry node modifier to the terrain info object.
    modifier = terrain_info_object.modifiers.new(name=name, type='NODES')
    modifier.node_group = create_terrain_object_geometry_node_group(curve_object, terrain_object_definition)
    modifier.show_on_cage = True

    return curve_object
