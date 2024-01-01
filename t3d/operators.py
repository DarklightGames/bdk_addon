import math
from io import StringIO
from typing import List

import bmesh
import bpy
import numpy
from mathutils import Euler, Matrix
from bpy.types import Operator, Context, Object
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from ..data import UReference
from ..bsp.properties import __poly_flag_keys_to_values__
from ..bsp.builder import create_bsp_brush_polygon
from ..terrain.exporter import create_static_mesh_actor, add_movement_properties_to_actor, create_terrain_info_actor, \
    convert_blender_matrix_to_unreal_movement_units
from .data import T3DObject
from pathlib import Path
from .importer import import_t3d
from .writer import T3DWriter
from ..helpers import are_bdk_dependencies_installed


class BDK_OT_t3d_import_from_clipboard(Operator):
    bl_idname = 'bdk.t3d_import_from_clipboard'
    bl_description = 'Import T3DMap from OS Clipboard'
    bl_label = 'Paste T3D From Clipboard'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context):
        # Return false if the clipboard doesn't contain text
        if not context.window_manager.clipboard:
            cls.poll_message_set('Clipboard is empty')
            return False
        return True

    def execute(self, context: Context):
        try:
            import_t3d(context.window_manager.clipboard, context)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except SyntaxError as e:
            print(e)
            self.report({'ERROR'}, 'Clipboard data is not valid T3DMap syntax. Additional debugging information has been '
                                   'written to the console')
            return {'CANCELLED'}
        self.report({'INFO'}, f'T3DMap Imported successfully')
        return {'FINISHED'}


class BDK_OT_t3d_import_from_file(Operator, ImportHelper):
    bl_idname = 'bdk.t3d_import_from_file'
    bl_description = 'Import T3DMap'
    bl_label = 'Import T3DMap (*.t3d)'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext: StringProperty(default='.t3d', options={'HIDDEN'})
    filter_glob: StringProperty(default='*.t3d', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        description='File path used for importing the T3DMap file',
        maxlen=1024,
        default='')

    @classmethod
    def poll(cls, context: Context):
        if not are_bdk_dependencies_installed():
            cls.poll_message_set('Dependencies are not installed')
            return False
        return True

    def execute(self, context: Context):
        contents = Path(self.filepath).read_text()
        try:
            import_t3d(contents, context)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except SyntaxError as e:
            print(e)
            self.report({'ERROR', 'File contents are not valid T3DMap syntax. Additional debugging information has been '
                                  'written to the console'})
        self.report({'INFO'}, f'T3DMap Imported successfully')
        return {'FINISHED'}


def sanitize_name(name: str) -> str:
    return name.replace('.', '_')


def get_poly_flags_int(poly_flags: set[str]) -> int:
    poly_flags_int = 0
    for flag in poly_flags:
        poly_flags_int |= __poly_flag_keys_to_values__[flag]
    return poly_flags_int


def bsp_brush_to_actor(context: Context, bsp_brush_object: Object) -> T3DObject:
    object_name = sanitize_name(bsp_brush_object.name)

    bsp_brush = bsp_brush_object.bdk.bsp_brush

    actor = T3DObject('Actor')
    actor.properties['Class'] = 'Brush'
    actor.properties['Name'] = object_name
    actor.properties['CsgOper'] = bsp_brush.csg_operation  # Convert the IDs to the expected format
    actor.properties['PolyFlags'] = get_poly_flags_int(bsp_brush.poly_flags)

    add_movement_properties_to_actor(actor, bsp_brush_object, do_rotation=False, do_scale=False)

    brush = T3DObject('Brush')
    brush.properties['Name'] = object_name

    poly_list = T3DObject('PolyList')

    bm = bmesh.new()
    bm.from_object(bsp_brush_object, context.evaluated_depsgraph_get())
    uv_layer = bm.loops.layers.uv.verify()

    bdk_poly_flags_layer = bm.faces.layers.int.get('bdk.poly_flags', None)

    """
    In the engine, BSP brushes ignore scale & rotation during the CSG build.
    Therefore, we need to apply the scale and rotation to the vertices of the brush before exporting.
    We let the actor's location handle the translation.
    """
    scale_matrix = Matrix.Diagonal(bsp_brush_object.scale).to_4x4()
    rotation_matrix = bsp_brush_object.rotation_euler.to_matrix().to_4x4()
    transform_matrix = rotation_matrix @ scale_matrix

    for face_index, face in enumerate(bm.faces):
        material = bsp_brush_object.material_slots[face.material_index].material if face.material_index < len(bsp_brush_object.material_slots) else None
        # T3D texture references only have the package and object name.
        texture = UReference.from_string(material.bdk.package_reference) if material else None
        if texture:
            texture = f'{texture.package_name}.{texture.object_name}'

        poly = T3DObject('Polygon')
        poly.properties['Texture'] = texture if texture else 'None'
        poly.properties['Link'] = face_index
        poly.properties['Flags'] = face[bdk_poly_flags_layer] if bdk_poly_flags_layer is not None else 0
        poly.polygon = create_bsp_brush_polygon(material, uv_layer, face, transform_matrix)
        poly_list.children.append(poly)

    brush.children.append(poly_list)
    actor.children.append(brush)

    actor.properties['Brush'] = f'Model\'myLevel.{object_name}\''

    return actor


def terrain_doodad_to_t3d_objects(context: Context, terrain_doodad_object: Object) -> List[T3DObject]:
    # Look up the seed object for the terrain doodad.
    depsgraph = context.evaluated_depsgraph_get()
    terrain_doodad = terrain_doodad_object.bdk.terrain_doodad

    actors = []

    for scatter_layer in terrain_doodad.scatter_layers:
        if scatter_layer.mute:
            continue

        # Get evaluated mesh data for the seed object.
        mesh_data = scatter_layer.seed_object.evaluated_get(depsgraph).data
        vertex_count = len(mesh_data.vertices)

        # Position
        attribute = mesh_data.attributes['position']
        position_data = [0.0] * vertex_count * 3
        attribute.data.foreach_get('vector', position_data)
        positions = numpy.array(position_data).reshape((vertex_count, 3))

        # Rotation
        attribute = mesh_data.attributes['rotation']
        rotation_data = [0.0] * vertex_count * 3
        attribute.data.foreach_get('vector', rotation_data)
        rotations = numpy.array(rotation_data).reshape((vertex_count, 3))

        # Scale
        attribute = mesh_data.attributes['scale']
        scale_data = [0.0] * vertex_count * 3
        attribute.data.foreach_get('vector', scale_data)
        scales = numpy.array(scale_data).reshape((vertex_count, 3))

        # Object Index
        attribute = mesh_data.attributes['object_index']
        object_index_data = [0] * vertex_count
        attribute.data.foreach_get('value', object_index_data)
        object_indices = numpy.array(object_index_data)

        for position, rotation, scale, object_index in zip(positions, rotations, scales, object_indices):
            matrix = Matrix.Translation(position) @ Euler(rotation).to_matrix().to_4x4() @ Matrix.Diagonal(scale).to_4x4()
            scatter_layer_object = scatter_layer.objects[object_index]
            static_mesh_object = scatter_layer.objects[object_index].object

            actor = T3DObject(type_name='Actor')
            actor.properties['Name'] = static_mesh_object.name
            actor.properties['StaticMesh'] = static_mesh_object.bdk.package_reference

            # Skin Overrides
            for material_slot_index, material_slot in enumerate(static_mesh_object.material_slots):
                if material_slot.link == 'OBJECT' \
                        and material_slot.material is not None \
                        and material_slot.material.bdk.package_reference is not None:
                    actor.properties[f'Skins({material_slot_index})'] = material_slot.material.bdk.package_reference

            location, rotation, scale = convert_blender_matrix_to_unreal_movement_units(matrix)
            actor.properties['Location'] = location
            actor.properties['Rotation'] = rotation
            actor.properties['DrawScale3D'] = scale

            actor_properties = scatter_layer_object.actor_properties
            actor.properties['Class'] = actor_properties.class_name
            if actor_properties.should_use_cull_distance:
                actor.properties['CullDistance'] = actor_properties.cull_distance

            collision_flags = actor_properties.collision_flags
            actor.properties['bBlockActors'] = 'BLOCK_ACTORS' in collision_flags
            actor.properties['bBlockKarma'] = 'BLOCK_KARMA' in collision_flags
            actor.properties['bBlockNonZeroExtentTraces'] = 'BLOCK_NON_ZERO_EXTENT_TRACES' in collision_flags
            actor.properties['bBlockZeroExtentTraces'] = 'BLOCK_ZERO_EXTENT_TRACES' in collision_flags
            actor.properties['bCollideActors'] = 'COLLIDE_ACTORS' in collision_flags

            actors.append(actor)

    return actors


# TODO: Copying from the outliner
def fluid_surface_to_t3d_object(context, obj):
    fluid_surface = obj.bdk.fluid_surface
    actor = T3DObject(type_name='Actor')
    add_movement_properties_to_actor(actor, obj, do_scale=False)
    actor.properties['Class'] = 'FluidSurfaceInfo'
    actor.properties['FluidXSize'] = fluid_surface.fluid_x_size
    actor.properties['FluidYSize'] = fluid_surface.fluid_y_size
    actor.properties['FluidGridSpacing'] = fluid_surface.fluid_grid_spacing
    actor.properties['UOffset'] = fluid_surface.u_offset
    actor.properties['VOffset'] = fluid_surface.v_offset
    actor.properties['UTiles'] = fluid_surface.u_tiles
    actor.properties['VTiles'] = fluid_surface.v_tiles
    if fluid_surface.material is not None:
        actor.properties['Skins'] = [fluid_surface.material.bdk.package_reference]
    return actor


class BDK_OT_t3d_copy_to_clipboard(Operator):
    bl_idname = 'bdk.t3d_copy_objects_to_clipboard'
    bl_description = 'Copy to clipboard as Unreal T3DMap doodad'
    bl_label = 'Copy as Unreal T3DMap'

    @classmethod
    def poll(cls, context: Context):
        # Return false if no objects are selected.
        if len(context.selected_objects) == 0:
            cls.poll_message_set('No object selected')
            return False
        return True

    def execute(self, context: Context):
        copy_actors: list[T3DObject] = []

        map_object = T3DObject('Map')

        def can_copy(bpy_object: Object) -> bool:
            # TODO: SpectatorCam, Projector, FluidSurface etc.
            return bpy_object.type == 'MESH' and bpy_object.data is not None

        bsp_brush_objects = []

        # Start a progress bar.
        wm = context.window_manager
        wm.progress_begin(0, len(context.selected_objects))

        #
        for obj_index, obj in enumerate(context.selected_objects):
            match obj.bdk.type:
                case 'BSP_BRUSH':
                    # Add the brush to the list of brushes to copy, we have to sort them by sort order.
                    bsp_brush_objects.append(obj)
                case 'TERRAIN_DOODAD':
                    copy_actors += terrain_doodad_to_t3d_objects(context, obj)
                case 'FLUID_SURFACE':
                    copy_actors.append(fluid_surface_to_t3d_object(context, obj))
                case 'TERRAIN_INFO':
                    copy_actors.append(create_terrain_info_actor(obj))
                case _:
                    # TODO: add handlers for other object types (outside of this function)
                    if obj.type == 'CAMERA':
                        # Create a SpectatorCam brush_object
                        camera_actor = T3DObject('Actor')
                        camera_actor.properties['Class'] = 'SpectatorCam'
                        camera_actor.properties['Name'] = obj.name
                        add_movement_properties_to_actor(camera_actor, obj)
                        rotation_euler = camera_actor['Rotation']
                        # TODO: make corrective matrix a constant
                        # Correct the rotation here since the blender cameras point down -Z with +X up by default.
                        rotation_euler.z += math.pi / 2
                        rotation_euler.x -= math.pi / 2
                        # Adjust the camera's rotation to match the Unreal coordinate system.
                        map_object.children.append(camera_actor)
                    else:
                        if obj.instance_collection:
                            copy_actors += [create_static_mesh_actor(o, obj)
                                            for o in obj.instance_collection.all_objects
                                            if can_copy(o)]
                        elif can_copy(obj):
                            copy_actors.append(create_static_mesh_actor(obj))

            wm.progress_update(obj_index)

        # TODO: we need a tie breaker for sort order.
        for bsp_brush_object in sorted(bsp_brush_objects, key=lambda obj: obj.bdk.bsp_brush.sort_order):
            copy_actors.append(bsp_brush_to_actor(context, bsp_brush_object))

        for actor in copy_actors:
            map_object.children.append(actor)

        # Write the map object to a string.
        string_io = StringIO()
        T3DWriter(string_io).write(map_object)
        size = string_io.tell()
        string_io.seek(0)

        # Copy the string to the clipboard.
        bpy.context.window_manager.clipboard = string_io.read()

        wm.progress_end()

        self.report({'INFO'}, f'Copied {len(copy_actors)} actors to clipboard ({size} bytes)')

        return {'FINISHED'}


classes = (
    BDK_OT_t3d_copy_to_clipboard,
    BDK_OT_t3d_import_from_file,
    BDK_OT_t3d_import_from_clipboard,
)
