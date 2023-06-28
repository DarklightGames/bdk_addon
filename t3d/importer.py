import math
import uuid

import bpy
import mathutils
import numpy as np
import t3dpy
from bpy.types import Context, Object, Mesh, Image, Camera
from typing import List, Optional, Dict, Any, cast, Type

from ..terrain.operators import add_terrain_layer_node
from ..projector.builder import build_projector_node_tree
from ..terrain.builder import create_terrain_info_object
from ..terrain.layers import add_terrain_paint_layer
from ..terrain.deco import add_terrain_deco_layer, update_terrain_layer_node_group
from ..data import URotator, UReference
from ..helpers import load_bdk_static_mesh, load_bdk_material
from ..units import unreal_to_radians


# TODO: move these to a separate file.

class ActorImporter:

    @classmethod
    def create_object(cls, t3d_actor: t3dpy.T3dObject, context: Context) -> Optional[Object]:
        """
        Creates a new Blender object for the given T3DMap actor.
        """
        raise NotImplementedError()

    @classmethod
    def on_properties_hydrated(cls, t3d_actor: t3dpy.T3dObject, bpy_object: Object, context: Context):
        """
        Called when the object has been created and all properties have been hydrated.
        """
        pass

    @classmethod
    def on_object_linked(cls, t3d_actor: t3dpy.T3dObject, bpy_object: Object, context: Context):
        """
        Called when the object has been linked to the scene.
        """
        pass


class DefaultActorImporter(ActorImporter):
    """
    Default actor importer used when no other importer is found.
    """

    @classmethod
    def _create_static_mesh_object(cls, t3d_actor: t3dpy.T3dObject) -> Optional[Object]:
        static_mesh_reference = t3d_actor['StaticMesh']

        # Load the static mesh data from the BDK asset library.
        mesh = load_bdk_static_mesh(str(static_mesh_reference))

        if mesh is None:
            print(f"Failed to load static mesh {static_mesh_reference} for actor {t3d_actor['Name']}.")
            return None

        # Create a new mesh object, matching the name of the actor.
        bpy_object = bpy.data.objects.new(t3d_actor['Name'], mesh)

        return bpy_object

    @classmethod
    def create_object(cls, t3d_actor: t3dpy.T3dObject, context: Context) -> Optional[Object]:
        """
        Creates a new Blender object for the given T3DMap actor.
        """
        if 'StaticMesh' in t3d_actor.properties:
            return cls._create_static_mesh_object(t3d_actor)
        else:
            return bpy.data.objects.new(t3d_actor['Name'], None)

    @classmethod
    def on_properties_hydrated(cls, t3d_actor: t3dpy.T3dObject, bpy_object: Object, context: Context):
        """
        Called when the object has been created and all properties have been hydrated.
        """
        # Handle skin overrides.
        skins = t3d_actor.properties.get('Skins', [])
        for index, texture_reference in skins:
            if index >= len(bpy_object.material_slots):
                # Material slot index out of range.
                continue

            material = load_bdk_material(str(texture_reference))
            if material is None:
                print(f'Failed to load material for {texture_reference}')
                continue

            material_slot = bpy_object.material_slots[index]
            material_slot.link = 'OBJECT'
            material_slot.material = material

    @classmethod
    def on_object_linked(cls, t3d_actor: t3dpy.T3dObject, bpy_object: Object, context: Context):
        """
        Called when the object has been linked to the scene.
        """
        pass


class FluidSurfaceInfoImporter(ActorImporter):
    @classmethod
    def create_object(cls, t3d_actor: t3dpy.T3dObject, context: Context) -> Optional[Object]:
        name = t3d_actor.properties.get('Name')
        mesh_data: Mesh = cast(Mesh, bpy.data.meshes.new(name))
        return bpy.data.objects.new(name, mesh_data)

    @classmethod
    def on_properties_hydrated(cls, t3d_actor: t3dpy.T3dObject, bpy_object: Object, context: Context):
        # Create a new geometry node tree.
        geometry_node_tree = bpy.data.node_groups.new(name=bpy_object.name, type="GeometryNodeTree")
        geometry_node_tree.inputs.clear()

        geometry_node_tree.outputs.new("NodeSocketGeometry", "Geometry")

        fluid_surface_node = geometry_node_tree.nodes.new(type="GeometryNodeBDKFluidSurface")
        set_material_node = geometry_node_tree.nodes.new(type="GeometryNodeSetMaterial")
        output_node = geometry_node_tree.nodes.new(type="NodeGroupOutput")

        geometry_node_tree.links.new(fluid_surface_node.outputs["Geometry"], set_material_node.inputs["Geometry"])
        geometry_node_tree.links.new(set_material_node.outputs["Geometry"], output_node.inputs["Geometry"])

        # Add geometry node modifier to fluid_surface_object.
        geometry_node_modifier = bpy_object.modifiers.new(name="FluidSurfaceInfo", type="NODES")
        geometry_node_modifier.node_group = geometry_node_tree

        input_names = [
            "FluidGridType",
            "FluidGridSpacing",
            "FluidXSize",
            "FluidYSize",
            "UTiles",
            "UOffset",
            "VTiles",
            "VOffset"
        ]

        # Create drivers on fluid surface node inputs that map to the properties on the fluid surface object.
        for input_name in input_names:
            driver = fluid_surface_node.inputs[input_name].driver_add("default_value").driver
            driver.type = 'AVERAGE'
            var = driver.variables.new()
            var.name = input_name
            var.type = 'SINGLE_PROP'
            var.targets[0].id = bpy_object
            var.targets[0].data_path = f"[\"{input_name}\"]"


class ProjectorImporter(ActorImporter):
    @classmethod
    def create_object(cls, t3d_actor: t3dpy.T3dObject, context: Context) -> Optional[Object]:
        name = t3d_actor.properties.get('Name')
        mesh_data: Mesh = cast(Mesh, bpy.data.meshes.new(name))
        return bpy.data.objects.new(name, mesh_data)

    @classmethod
    def on_properties_hydrated(cls, t3d_actor: t3dpy.T3dObject, bpy_object: Object, context: Context):
        # Create a new geometry node tree.
        node_tree = build_projector_node_tree()

        # Add geometry node modifier to projector_object.
        geometry_node_modifier = bpy_object.modifiers.new(name="Projector", type="NODES")
        geometry_node_modifier.node_group = node_tree

        # T3D STUFF BELOW:

        # value_node = node_tree.nodes.new(type="ShaderNodeValue")
        # # Add a driver to the default value of the value node corresponding to the projector object's "FOV" property.
        # driver = value_node.outputs[0].driver_add("default_value").driver
        # driver.type = 'AVERAGE'
        # var = driver.variables.new()
        # var.name = "FOV"
        # var.type = 'SINGLE_PROP'
        # var.targets[0].id = bpy_object
        # var.targets[0].data_path = "[\"FOV\"]"

        # # Load the projector material.
        # projector_material = t3d_actor.properties.get('ProjTexture', 'None')
        # material = load_bdk_material(str(projector_material))
        # if material is not None:
        #     # Set the material input for the set material node.
        #     set_material_node.inputs["Material"].default_value = material
        #
        # input_names = [
        #     "MaxTraceDistance",
        #     "DrawScale"
        # ]
        #
        # # Create drivers on projector node inputs that map to the properties on projector object.
        # for input_name in input_names:
        #     # Check that the properties exist on the projector object, and if not, create them.
        #     # TODO: In the future, we need to do type lookups for these properties and set the correct default value
        #     #  based on the type.
        #     if input_name not in bpy_object:
        #         bpy_object[input_name] = 0.0
        #     driver = projector_node.inputs[input_name].driver_add("default_value").driver
        #     driver.type = 'AVERAGE'
        #     var = driver.variables.new()
        #     var.name = input_name
        #     var.type = 'SINGLE_PROP'
        #     var.targets[0].id = bpy_object
        #     var.targets[0].data_path = f"[\"{input_name}\"]"


class TerrainInfoImporter(ActorImporter):
    @classmethod
    def create_object(cls, t3d_actor: t3dpy.T3dObject, context: Context) -> Optional[Object]:
        terrain_map_reference = UReference.from_string(str(t3d_actor.properties.get('TerrainMap', 'None')))
        terrain_scale: Dict[str, float] = t3d_actor.properties.get('TerrainScale', {'X': 0.0, 'Y': 0.0, 'Z': 0.0})
        layers: List[(int, Dict[str, Any])] = t3d_actor.properties.get('Layers', [])
        deco_layers: List[(int, Dict[str, Any])] = t3d_actor.properties.get('DecoLayers', [])
        deco_layer_offset: float = t3d_actor.properties.get('DecoLayerOffset', 0.0)  # TODO: handle this
        quad_visibility_bitmap_entries: List[(int, int)] = t3d_actor.properties.get('QuadVisibilityBitmap', [])
        edge_turn_bitmap_entries: List[(int, int)] = t3d_actor.properties.get('EdgeTurnBitmap', [])

        size = terrain_scale.get('X', 1.0)
        terrain_scale_z = terrain_scale.get('Z', 64.0)

        if terrain_map_reference is None:
            raise RuntimeError('No terrain map, nothing to import')

        # Check that the terrain map exists in the package.
        terrain_map_image_name = f'{terrain_map_reference.object_name}.tga'
        if terrain_map_image_name not in bpy.data.images:
            raise RuntimeError(f'Terrain map image {terrain_map_image_name} not found in local blend file')

        # Load the terrain map image.
        terrain_map_image = bpy.data.images[f'{terrain_map_reference.object_name}.tga']
        resolution = int(terrain_map_image.size[0])
        heightmap = height_map_data_from_image(terrain_map_image)

        # Translate the height values based on the terrain scale.
        heightmap = (0.5 - heightmap) * terrain_scale_z * -256.0  # TODO: i think umodel might be doing this wrong!

        # Edge Turn Bitmap
        edge_turn_bitmap = np.zeros(shape=int(math.ceil((resolution * resolution) / 32)), dtype=np.int32)
        for index, value in edge_turn_bitmap_entries:
            edge_turn_bitmap[index] = value

        # TODO: make create_terrain_info_object take quad_size instead of full resolution
        mesh_object = create_terrain_info_object(resolution=resolution, size=resolution * size, heightmap=heightmap,
                                                 edge_turn_bitmap=edge_turn_bitmap)
        mesh_data: Mesh = cast(Mesh, mesh_object.data)

        # Link the new object to the scene.
        # Note that it is necessary to do this here because the code below relies on the terrain info object already
        # existing in the scene.
        if mesh_object is not None:
            context.scene.collection.objects.link(mesh_object)

        # Layers
        for layer_index, layer in layers:
            # Alpha Map
            alpha_map_reference = layer.get('AlphaMap', None)

            if alpha_map_reference is not None:
                paint_layer_name = UReference.from_string(str(alpha_map_reference)).object_name
            else:
                paint_layer_name = uuid.uuid4().hex

            paint_layer = add_terrain_paint_layer(mesh_object, paint_layer_name)
            paint_layer.u_scale = layer.get('UScale', 1.0)
            paint_layer.v_scale = layer.get('VScale', 1.0)
            paint_layer.texture_rotation = unreal_to_radians(layer.get('TextureRotation', 0))

            # Add the node group and rebuild the node tree.
            paint_node = add_terrain_layer_node(mesh_object, paint_layer.nodes, type='PAINT')

            if paint_layer.id in bpy.data.node_groups:
                node_tree = bpy.data.node_groups[paint_layer.id]
                update_terrain_layer_node_group(node_tree, 'paint_layers', layer_index, paint_layer.id, paint_layer.nodes)

            # Alpha Map
            alpha_map_image_name = f'{paint_layer_name}.tga'
            alpha_map_image = bpy.data.images[alpha_map_image_name]
            if alpha_map_image:
                if terrain_map_image.size != alpha_map_image.size:
                    # Print out a warning if the alpha map image is not the same size as the terrain map image.
                    print(f'Warning: Alpha map image {alpha_map_image_name} is not the same size as the terrain map '
                          f'image {terrain_map_image_name}. The alpha map image will be resized to match the terrain '
                          f'map image.')
                    # Resize the alpha map image to match the terrain map image.
                    alpha_map_image.scale(terrain_map_image.size[0], terrain_map_image.size[1])
                alpha_map_attribute = mesh_data.attributes[paint_node.id]
                alpha_map_attribute.data.foreach_set('color', density_map_data_from_image(alpha_map_image))

            # Texture
            texture_reference = layer.get('Texture', None)
            if texture_reference is not None:
                paint_layer.material = load_bdk_material(str(texture_reference))

        deco_density_maps: Dict[str, bpy.types.Attribute] = {}

        # Deco Layers
        for deco_layer_index, deco_layer_data in deco_layers:
            static_mesh = UReference.from_string(str(deco_layer_data.get('StaticMesh', 'None')))

            deco_layer_name = static_mesh.object_name if static_mesh else 'DecoLayer'

            # TODO: current scheme assumes 1:1 density map; provide a way to flag that we have our own density map we
            #  want to use (i.e. reuse the deco layers)
            deco_layer = add_terrain_deco_layer(mesh_object, name=deco_layer_name)

            static_mesh_data = load_bdk_static_mesh(str(static_mesh))
            deco_static_mesh_object = bpy.data.objects.new(uuid.uuid4().hex, static_mesh_data)
            deco_layer.static_mesh = deco_static_mesh_object
            deco_layer.detail_mode = deco_layer_data.get('DetailMode', 'DM_Low')
            deco_layer.show_on_terrain = deco_layer_data.get('ShowOnTerrain', 0)
            deco_layer.max_per_quad = deco_layer_data.get('MaxPerQuad', 0)
            deco_layer.seed = deco_layer_data.get('Seed', 0)
            deco_layer.align_to_terrain = deco_layer_data.get('AlignToTerrain', 0)
            deco_layer.force_draw = deco_layer_data.get('ForceDraw', 0)
            deco_layer.show_on_invisible_terrain = deco_layer_data.get('ShowOnInvisibleTerrain', 0)
            deco_layer.random_yaw = deco_layer_data.get('RandomYaw', 0)
            deco_layer.draw_order = deco_layer_data.get('DrawOrder', 'SORT_NoSort')

            # Density Multiplier
            density_multiplier = deco_layer_data.get('DensityMultiplier', None)
            if density_multiplier:
                deco_layer.density_multiplier_min = density_multiplier.get('Min', 0.0)
                deco_layer.density_multiplier_max = density_multiplier.get('Max', 0.0)

            # Fadeout Radius
            fadeout_radius = deco_layer_data.get('FadeoutRadius', None)
            if fadeout_radius:
                deco_layer.fadeout_radius_min = fadeout_radius.get('Min', 0.0)
                deco_layer.fadeout_radius_max = fadeout_radius.get('Max', 0.0)

            # Scale Multiplier
            scale_multiplier = deco_layer_data.get('ScaleMultiplier', None)
            if scale_multiplier:
                scale_multiplier_x = scale_multiplier.get('X', None)
                scale_multiplier_y = scale_multiplier.get('Y', None)
                scale_multiplier_z = scale_multiplier.get('Z', None)
                if scale_multiplier_x:
                    deco_layer.scale_multiplier_min.x = scale_multiplier_x.get('Min', 0.0)
                    deco_layer.scale_multiplier_max.x = scale_multiplier_x.get('Max', 0.0)
                if scale_multiplier_y:
                    deco_layer.scale_multiplier_min.y = scale_multiplier_y.get('Min', 0.0)
                    deco_layer.scale_multiplier_max.y = scale_multiplier_y.get('Max', 0.0)
                if scale_multiplier_y:
                    deco_layer.scale_multiplier_min.z = scale_multiplier_z.get('Min', 0.0)
                    deco_layer.scale_multiplier_max.z = scale_multiplier_z.get('Max', 0.0)

            # TODO: we need to make sure we don't delete attributes that are shared by multiple painting layers
            #  (current system assumes 1:1)

            # Density Map
            density_map_reference = UReference.from_string(str(deco_layer_data.get('DensityMap', 'None')))

            # TODO: create the density maps for each unique texture/image (map the name to a generated uuid attribute)
            if density_map_reference:
                density_map_image_name = f'{density_map_reference.object_name}.tga'
                density_map_image = bpy.data.images[density_map_image_name]
                if density_map_image:
                    print(f'density map image found for deco layer {density_map_image}')
                    # Create the paint node for the deco layer.
                    paint_node = add_terrain_layer_node(mesh_object, deco_layer.nodes, type='PAINT')
                    if terrain_map_image.size != density_map_image.size:
                        # Print out a warning if the alpha map image is not the same size as the terrain map image.
                        print(
                            f'Warning: Deco density map {density_map_image} is not the same size as the terrain map'
                            f'The density map will be resized to match the terrain '
                            f'map image.')
                        # Resize the alpha map image to match the terrain map image.
                        density_map_image.scale(terrain_map_image.size[0], terrain_map_image.size[1])

                    density_map_attribute = mesh_data.attributes[paint_node.id]
                    density_map_attribute.data.foreach_set('color', density_map_data_from_image(density_map_image))
                    deco_density_maps[density_map_image_name] = density_map_attribute
                else:
                    print(f'Could not find density map image: {density_map_image_name}')

        # Quad Visibility Bitmap.
        quad_visibility_bitmap = np.zeros(shape=int(math.ceil((resolution * resolution) / 32)), dtype=np.int32)
        for index, value in quad_visibility_bitmap_entries:
            quad_visibility_bitmap[index] = value

        bitmap_index = 0
        for y in reversed(range(resolution - 1)):
            for x in range(resolution - 1):
                polygon_index = (y * resolution) - y + x
                array_index = bitmap_index >> 5
                bit_mask = bitmap_index & 0x1F
                if (quad_visibility_bitmap[array_index] & (1 << bit_mask)) == 0:
                    mesh_data.polygons[polygon_index].material_index = 1
                bitmap_index += 1
            bitmap_index += 1

        return mesh_object

    @classmethod
    def on_properties_hydrated(cls, t3d_actor: t3dpy.T3dObject, bpy_object: Object, context: Context):
        # The scale and rotation properties are not used by the terrain geometry, so we can reset them.
        bpy_object.scale = (1.0, 1.0, 1.0)
        bpy_object.rotation_euler = (0.0, 0.0, 0.0)


class SpectatorCamImporter(ActorImporter):
    @classmethod
    def create_object(cls, t3d_actor: t3dpy.T3dObject, context: Context) -> Optional[Object]:
        name = t3d_actor.properties.get('Name')
        camera_data: Camera = cast(Camera, bpy.data.cameras.new(name))
        camera_data.clip_start = 2
        camera_data.clip_end = 65536
        camera_data.lens = 35.0  # Approximately 90 degrees FOV.
        camera_object = bpy.data.objects.new(name, camera_data)
        context.scene.collection.objects.link(camera_object)
        return camera_object

    @classmethod
    def on_properties_hydrated(cls, t3d_actor: t3dpy.T3dObject, bpy_object: Object, context: Context):
        # Correct the rotation here since the blender cameras point down -Z with +X up by default.
        # TODO: use transform matrix
        bpy_object.rotation_euler.z -= math.pi / 2
        bpy_object.rotation_euler.x += math.pi / 2


__actor_type_importers__ = {
    'FluidSurfaceInfo': FluidSurfaceInfoImporter,
    'TerrainInfo': TerrainInfoImporter,
    'SpectatorCam': SpectatorCamImporter,
    'Projector': ProjectorImporter,
}


def get_actor_type_importer(actor_type: str) -> Type[ActorImporter]:
    return __actor_type_importers__.get(actor_type, DefaultActorImporter)


def height_map_data_from_image(image: Image) -> np.array:
    r = [int(x * 255) for x in list(image.pixels)[0::4]]
    g = [int(x * 255) for x in list(image.pixels)[1::4]]
    h = []
    for i in range(len(r)):
        b = (r[i] << 8) | g[i]
        h.append(b / 65536)
    return np.array(h, dtype=float)


def density_map_data_from_image(image: Image) -> np.array:
    """
    Converts the alpha channel of an image to RGBA data used for density maps. [THIS IS TECHNICALLY WRONG, WE NEED TO FIGURE OUT HOW TO DO THE LUMA CALCULATION CORRECTLY]
    :param image:
    :return:
    """
    if image.channels != 4:
        raise RuntimeError('image does not have an alpha channel!')
    alpha_data = np.array(list(image.pixels)[3::4], dtype=float)
    color_data = np.ones(len(alpha_data) * 4, dtype=float)
    luma_coefficients = np.array((0.2126, 0.7152, 0.0722))
    for index, datum in enumerate(alpha_data):
        # Sets the first three values to the alpha value.
        start = index * 4
        stop = start + 3
        color_data[start:stop] = datum
    color_data[:] = tuple(color_data)
    # Multiply every value by 255 and change the type to int.
    color_data *= 255
    return color_data.astype(int)


def import_t3d(contents: str, context: Context):
    def set_custom_properties(t3d_actor: t3dpy.T3dObject, bpy_object: Object):
        scale = mathutils.Vector((1.0, 1.0, 1.0))
        for key, value in t3d_actor.properties.items():
            if key == 'Location':
                bpy_object.location = value.get('X', 0.0), -value.get('Y', 0.0), value.get('Z', 0.0)
            elif key == 'Rotation':
                yaw = -value.get('Yaw', 0)
                pitch = -value.get('Pitch', 0)
                roll = value.get('Roll', 0)
                rotation_euler = URotator(pitch, yaw, roll).get_radians()
                bpy_object.rotation_euler = rotation_euler
            elif key == 'DrawScale':
                scale *= value
            elif key == 'DrawScale3D':
                scale *= mathutils.Vector((value.get('X', 1.0), value.get('Y', 1.0), value.get('Z', 1.0)))
            if type(value) == t3dpy.T3dReference:
                value = str(value)
            elif type(value) == dict:
                continue
            elif type(value) == list:
                continue
            bpy_object[key] = value
        bpy_object.scale = scale

    def import_t3d_object(t3d_object: t3dpy.T3dObject, context: Context):
        if t3d_object.type_ == 'Map':
            import_t3d_map(t3d_object, context)
        elif t3d_object.type_ == 'Actor':
            import_t3d_actor(t3d_object, context)

    def import_t3d_actor(t3d_actor, context: Context) -> Optional[Object]:
        actor_class = t3d_actor.properties.get('Class', None)

        if actor_class is None:
            print('Failed to import actor: ' + str(t3d_actor['Name']) + ' (no class)')
            return None

        print('Importing actor: ' + str(t3d_actor['Name']) + ' (' + str(actor_class) + ')')

        # Get the actor importer for this actor type.
        actor_importer = get_actor_type_importer(actor_class)

        bpy_object = actor_importer.create_object(t3d_actor, context)

        if bpy_object is None:
            print('Failed to import actor: ' + str(t3d_actor['Name']) + ' (' + str(actor_class) + ')')
            return None

        set_custom_properties(t3d_actor, bpy_object)

        # Allow the actor importer to do any additional work after the properties have been set.
        actor_importer.on_properties_hydrated(t3d_actor, bpy_object, context)

        # Link the new object to the scene.
        context.scene.collection.objects.link(bpy_object)

        # Allow the actor importer to do any additional work after the object has been linked.
        actor_importer.on_object_linked(t3d_actor, bpy_object, context)

        bpy_object.select_set(True)

        return bpy_object

    def import_t3d_map(t3d_map, context: Context):
        for child in t3d_map.children:
            import_t3d_object(child, context)

    print(f'Reading T3DMap ({len(contents)})...')

    t3d_objects: List[t3dpy.T3dObject] = t3dpy.read_t3d(contents)

    print(f'T3DMap reading completed')
    print(f'Importing {len(t3d_objects)} objects...')

    for t3d_object in t3d_objects:
        import_t3d_object(t3d_object, context)
