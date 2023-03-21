import math
import uuid

import bpy
import bmesh
import mathutils
import numpy as np
from bmesh.types import BMesh
from bpy.types import Context, Object, Mesh
from typing import List, Optional, Dict, Any, cast

from ..terrain.builder import create_terrain_info_object
from ..terrain.layers import add_terrain_layer
from ..terrain.deco import add_terrain_deco_layer
from ..data import URotator, UReference
from ..helpers import load_bdk_static_mesh, load_bdk_material
from ..units import unreal_to_radians


def import_t3d(contents: str, context: Context):
    import t3dpy

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

    def import_t3d_object(t3d_object, context: Context):
        if t3d_object.type_ == 'Map':
            import_t3d_map(t3d_object, context)
        elif t3d_object.type_ == 'Actor':
            import_t3d_actor(t3d_object, context)

    def import_t3d_actor(t3d_actor, context: Context) -> Optional[Object]:
        # Create a new actor, name it appropriately and fill in the custom properties.
        actor_class = t3d_actor.properties.get('Class', None)

        if actor_class == 'TerrainInfo':
            bpy_object = import_terrain_info_actor(t3d_actor, context)
        elif 'StaticMesh' in t3d_actor.properties:
            bpy_object = import_static_mesh_actor(t3d_actor, context)
        else:
            # Just do an empty object for now.
            bpy_object = bpy.data.objects.new(t3d_actor['Name'], None)
            if bpy_object is not None:
                context.scene.collection.objects.link(bpy_object)

        if bpy_object is None:
            return None

        # TODO: sometimes we very much do NOT WANT the scale to be set (for example, TerrainInfo visually ignores Scale)
        set_custom_properties(t3d_actor, bpy_object)

        # HACK: ignore the scale for now
        if actor_class == 'TerrainInfo':
            bpy_object.scale = (1.0, 1.0, 1.0)

        return bpy_object

    def import_terrain_info_actor(t3d_actor, context: Context) -> Optional[Object]:
        terrain_map = t3d_actor.properties.get('TerrainMap', None)  # T3dReference
        terrain_scale: Dict[str, float] = t3d_actor.properties.get('TerrainScale', {'X': 0.0, 'Y': 0.0, 'Z': 0.0})
        layers: List[(int, Dict[str, Any])] = t3d_actor.properties.get('Layers', [])
        deco_layers: List[(int, Dict[str, Any])] = t3d_actor.properties.get('DecoLayers', [])
        deco_layer_offset: float = t3d_actor.properties.get('DecoLayerOffset', 0.0)
        quad_visibility_bitmap_entries: List[(int, int)] = t3d_actor.properties.get('QuadVisibilityBitmap', [])
        edge_turn_bitmap_entries: List[(int, int)] = t3d_actor.properties.get('EdgeTurnBitmap', [])

        # have a universal way to transform myLevel packages to a

        # TODO: we make the assumption here that the scale & resolution is homogenous.
        # If it isn't, we should throw an error.
        resolution = 256
        quads_per_row = resolution - 1
        quads_per_column = quads_per_row
        quad_count = quads_per_row * quads_per_column

        size = terrain_scale.get('X', 1.0)

        # Edge Turn Bitmap
        edge_turn_bitmap = np.zeros(shape=int(math.ceil((resolution * resolution) / 32)), dtype=np.int32)
        for index, value in edge_turn_bitmap_entries:
            edge_turn_bitmap[index] = value

        # TODO: make create_terrain_info_object take quad_size instead of full resolution
        mesh_object = create_terrain_info_object(resolution=resolution, size=(resolution - 1) * size, edge_turn_bitmap=edge_turn_bitmap)
        mesh_data: Mesh = cast(Mesh, mesh_object.data)

        # Link the new object to the scene.
        # Note that it is necessary to do this here because the code below relies on the terrain info object already
        # existing in the scene.
        if mesh_object is not None:
            context.scene.collection.objects.link(mesh_object)

        for layer_index, layer in layers:
            alpha_map_reference = layer.get('AlphaMap', None)
            if alpha_map_reference is not None:
                terrain_layer_name = UReference.from_string(str(alpha_map_reference)).object_name
            else:
                terrain_layer_name = uuid.uuid4().hex
            terrain_layer = add_terrain_layer(mesh_object, terrain_layer_name)
            terrain_layer.u_scale = layer.get('UScale', 1.0)
            terrain_layer.v_scale = layer.get('VScale', 1.0)
            terrain_layer.texture_rotation = unreal_to_radians(layer.get('TextureRotation', 0))

        deco_density_maps: Dict[str, bpy.types.Attribute] = {}

        # Deco Layers
        for deco_layer_index, deco_layer in deco_layers:
            static_mesh = UReference.from_string(str(deco_layer.get('StaticMesh', 'None')))
            deco_layer_name = static_mesh.object_name if static_mesh else 'DecoLayer'
            # TODO: current scheme assumes 1:1 density map; provide a way to flag that we have our own density map we want to use
            terrain_deco_layer = add_terrain_deco_layer(context, mesh_object, name=deco_layer_name)
            terrain_deco_layer.detail_mode = deco_layer.get('DetailMode', 'DM_Low')
            terrain_deco_layer.show_on_terrain = deco_layer.get('ShowOnTerrain', 0)
            terrain_deco_layer.max_per_quad = deco_layer.get('MaxPerQuad', 0)
            terrain_deco_layer.seed = deco_layer.get('Seed', 0)
            terrain_deco_layer.align_to_terrain = deco_layer.get('AlignToTerrain', 0)
            terrain_deco_layer.force_draw = deco_layer.get('ForceDraw', 0)
            terrain_deco_layer.show_on_invisible_terrain = deco_layer.get('ShowOnInvisibleTerrain', 0)
            terrain_deco_layer.random_yaw = deco_layer.get('RandomYaw', 0)
            terrain_deco_layer.draw_order = deco_layer.get('DrawOrder', 'SORT_NoSort')

            # Density Multiplier
            density_multiplier = deco_layer.get('DensityMultiplier', None)
            if density_multiplier:
                terrain_deco_layer.density_multiplier_min = density_multiplier.get('Min', 0.0)
                terrain_deco_layer.density_multiplier_max = density_multiplier.get('Max', 0.0)

            # Fadeout Radius
            fadeout_radius = deco_layer.get('FadeoutRadius', None)
            if fadeout_radius:
                terrain_deco_layer.fadeout_radius_min = fadeout_radius.get('Min', 0.0)
                terrain_deco_layer.fadeout_radius_max = fadeout_radius.get('Max', 0.0)

            # Scale Multiplier
            scale_multiplier = deco_layer.get('ScaleMultiplier', None)
            if scale_multiplier:
                scale_multiplier_x = scale_multiplier.get('X', None)
                scale_multiplier_y = scale_multiplier.get('Y', None)
                scale_multiplier_z = scale_multiplier.get('Z', None)
                if scale_multiplier_x:
                    terrain_deco_layer.scale_multiplier_min.x = scale_multiplier_x.get('Min', 0.0)
                    terrain_deco_layer.scale_multiplier_max.x = scale_multiplier_x.get('Max', 0.0)
                if scale_multiplier_y:
                    terrain_deco_layer.scale_multiplier_min.y = scale_multiplier_y.get('Min', 0.0)
                    terrain_deco_layer.scale_multiplier_max.y = scale_multiplier_y.get('Max', 0.0)
                if scale_multiplier_y:
                    terrain_deco_layer.scale_multiplier_min.z = scale_multiplier_z.get('Min', 0.0)
                    terrain_deco_layer.scale_multiplier_max.z = scale_multiplier_z.get('Max', 0.0)

            # Density Map
            density_map_reference = UReference.from_string(str(deco_layer.get('DensityMap', 'None')))

            # TODO: create the density maps for each unique texture/image (map the name to a generated uuid attribute)
            if density_map_reference:
                density_map_image_name = f'{density_map_reference.object_name}.tga'
                density_map_image_pixels = bpy.data.images[density_map_image_name].pixels

                # TODO: we need to make sure we don't delete attributes that are shared by multiple painting layers
                #  (current system assumes 1:1)
                density_map_attribute = mesh_data.attributes[terrain_deco_layer.id]
                deco_density_maps[density_map_image_name] = density_map_attribute

                deco_density_map_attribute = deco_density_maps[density_map_image_name]

                # TODO: need to convert the alpha values into wacky SRGB values
                density_map_attribute_data = np.array(list(density_map_image_pixels)[3::4], dtype=float)
                density_map_attribute_color_data = np.ones(len(density_map_attribute_data) * 4, dtype=float)

                for index, datum in enumerate(density_map_attribute_data):
                    start = index * 4
                    stop = start + 3
                    density_map_attribute_color_data[start:stop] = datum
                density_map_attribute_color_data[:] = tuple(density_map_attribute_color_data)
                deco_density_map_attribute.data.foreach_set('color', density_map_attribute_color_data)

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

    def import_static_mesh_actor(t3d_actor, context: Context) -> Optional[Object]:
        static_mesh_reference = t3d_actor['StaticMesh']

        # Load the static mesh data from the BDK asset library.
        mesh = load_bdk_static_mesh(str(static_mesh_reference))

        if mesh is None:
            return None

        # Create a new mesh object, matching the name of the actor.
        bpy_object = bpy.data.objects.new(t3d_actor['Name'], mesh)

        # Handle skin overrides.
        skins = t3d_actor.properties.get('Skins', [])
        for index, texture_reference in skins:
            if index >= len(bpy_object.material_slots):
                # Material slot index out of range.
                continue

            material = load_bdk_material(str(texture_reference))
            if material is None:
                # Material could not be loaded.
                continue

            material_slot = bpy_object.material_slots[index]
            material_slot.link = 'OBJECT'
            material_slot.material = material

        # Link the new object to the scene.
        if bpy_object is not None:
            context.scene.collection.objects.link(bpy_object)

        return bpy_object

    def import_t3d_map(t3d_map, context: Context):
        for child in t3d_map.children:
            import_t3d_object(child, context)

    t3d_objects: List[t3dpy.T3dObject] = t3dpy.read_t3d(contents)

    for t3d_object in t3d_objects:
        import_t3d_object(t3d_object, context)
