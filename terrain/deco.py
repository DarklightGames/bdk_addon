import bpy
from bpy.types import Context, Object, Mesh
import numpy as np
from typing import cast, Optional
from .types import BDK_PG_TerrainDecoLayerPropertyGroup, BDK_PG_TerrainInfoPropertyGroup


class TerrainDecoLayerBuilder:
    def __init__(self):
        pass

    def build(self, context: Context, terrain_info_object: Object, deco_layer: BDK_PG_TerrainDecoLayerPropertyGroup) -> Object:
        # TODO: create an empty mesh object, slap a geonode setup on it and set up all the drivers
        if terrain_info_object is None or deco_layer is None:
            raise ValueError('Bad arguments!')

        terrain_info: BDK_PG_TerrainInfoPropertyGroup = getattr(terrain_info_object, 'terrain_info')

        # Get the index of the deco layer (it will be used for drivers)
        deco_layer_index = list(terrain_info.deco_layers).index(deco_layer)

        if deco_layer_index == -1:
            raise RuntimeError(f'Could not find deco layer {deco_layer.id}')

        mesh_data = bpy.data.meshes.new(deco_layer.id)
        deco_layer_object = bpy.data.objects.new(deco_layer.id, mesh_data)
        deco_layer_object.hide_select = True

        if terrain_info_object is None or terrain_info_object.type != 'MESH':
            raise ValueError('Bad terrain object')

        terrain_info_mesh_data = cast(Mesh, terrain_info_object.data)

        # TODO: this needs to be added on the terrain object
        density_map_attribute = terrain_info_mesh_data.color_attributes.new(deco_layer.id, type='BYTE_COLOR', domain='POINT')
        vertex_count = len(density_map_attribute.data)
        color_data = np.ndarray(shape=(vertex_count, 4), dtype=float)
        color_data[:] = (0.0, 0.0, 0.0, 0.0)
        density_map_attribute.data.foreach_set('color', color_data.flatten())

        node_tree = bpy.data.node_groups.new(deco_layer.id, type='GeometryNodeTree')

        node_tree.outputs.new(type='NodeSocketGeometry', name='Geometry')

        node_tree.nodes.clear()

        terrain_object_info_node = node_tree.nodes.new('GeometryNodeObjectInfo')
        terrain_object_info_node.inputs[0].default_value = terrain_info_object

        deco_layer_node = node_tree.nodes.new('GeometryNodeBDKDecoLayer')
        deco_layer_node.inputs['Heightmap X'].default_value = terrain_info.x_size
        deco_layer_node.inputs['Heightmap Y'].default_value = terrain_info.y_size
        node_tree.links.new(deco_layer_node.inputs['Terrain'], terrain_object_info_node.outputs['Geometry'])

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
                target.data_path = f'terrain_info.deco_layers[{deco_layer_index}].{property_name}[{index}]'
            else:
                target.data_path = f'terrain_info.deco_layers[{deco_layer_index}].{property_name}'

        add_deco_layer_driver('Max Per Quad', 'max_per_quad')
        add_deco_layer_driver('Seed', 'seed')
        add_deco_layer_driver('Offset', 'offset')
        add_deco_layer_driver('Show On Invisible Terrain', 'show_on_invisible_terrain')
        add_deco_layer_driver('Align To Terrain', 'align_to_terrain')
        add_deco_layer_driver('Random Yaw', 'random_yaw')
        add_deco_layer_driver('Inverted', 'inverted')
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

        density_named_attribute_node = node_tree.nodes.new('GeometryNodeInputNamedAttribute')
        density_named_attribute_node.data_type = 'FLOAT'
        density_named_attribute_node.inputs['Name'].default_value = deco_layer.id

        instance_on_points_node = node_tree.nodes.new('GeometryNodeInstanceOnPoints')
        node_tree.links.new(instance_on_points_node.inputs['Instance'], static_mesh_object_info_node.outputs['Geometry'])
        node_tree.links.new(instance_on_points_node.inputs['Points'], deco_layer_node.outputs['Points'])
        node_tree.links.new(instance_on_points_node.inputs['Rotation'], deco_layer_node.outputs['Rotation'])
        node_tree.links.new(instance_on_points_node.inputs['Scale'], deco_layer_node.outputs['Scale'])

        node_tree.links.new(deco_layer_node.inputs['Density Map'], density_named_attribute_node.outputs[1])

        output_node = node_tree.nodes.new('NodeGroupOutput')
        node_tree.links.new(output_node.inputs['Geometry'], instance_on_points_node.outputs['Instances'])

        modifier = deco_layer_object.modifiers.new(name=deco_layer.id, type='NODES')
        modifier.node_group = node_tree

        return deco_layer_object
