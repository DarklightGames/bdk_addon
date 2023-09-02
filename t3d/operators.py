import math
from io import StringIO
from typing import List, cast

import bmesh
import bpy
import numpy
from mathutils import Euler, Matrix
from bpy.types import Operator, Context, Object, Mesh
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from ..bsp.properties import __poly_flag_keys_to_values__
from ..bsp.builder import create_bsp_brush_polygon
from ..terrain.exporter import create_static_mesh_actor, add_movement_properties_to_actor, get_terrain_heightmap, \
    create_terrain_info_actor, convert_blender_matrix_to_unreal_movement_units
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
    filepath: StringProperty()
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

    add_movement_properties_to_actor(actor, bsp_brush_object)

    brush = T3DObject('Brush')
    brush.properties['Name'] = object_name

    poly_list = T3DObject('PolyList')

    mesh_object = bsp_brush_object
    mesh_data = cast(Mesh, bsp_brush_object.data)

    for polygon_index, polygon in enumerate(mesh_data.polygons):
        poly = T3DObject('Polygon')
        poly.properties['Texture'] = 'None'
        poly.properties['Link'] = polygon_index
        poly.polygon = create_bsp_brush_polygon(mesh_object, polygon)
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
            # TODO: The order of operations here is probably wrong.
            matrix = Matrix.Translation(position) @ Euler(rotation).to_matrix().to_4x4() @ Matrix.Diagonal(scale).to_4x4()

            static_mesh_object = scatter_layer.objects[object_index].object
            actor = T3DObject(type_name='Actor')
            actor.properties['Class'] = 'StaticMeshActor'
            actor.properties['Name'] = static_mesh_object.name
            actor.properties['StaticMesh'] = static_mesh_object.bdk.package_reference
            location, rotation, scale = convert_blender_matrix_to_unreal_movement_units(matrix)
            actor.properties['Location'] = location
            actor.properties['Rotation'] = rotation
            actor.properties['DrawScale3D'] = scale
            actors.append(actor)

    return actors


# TODO: Copying from the outliner
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
        t3d = T3DObject('Map')

        def can_copy(bpy_object: Object) -> bool:
            # TODO: SpectatorCam, Projector, FluidSurface etc.
            return bpy_object.type == 'MESH' and bpy_object.data is not None

        depsgraph = context.evaluated_depsgraph_get()

        bsp_brush_objects = []

        for obj in context.selected_objects:
            if obj.bdk.type == 'TERRAIN_DOODAD':
                copy_actors += terrain_doodad_to_t3d_objects(context, obj)
            elif obj.bdk.type == 'TERRAIN_INFO':
                # TODO: terrain scale might be an issue for people just editing existing maps
                heightmap, terrain_scale_z = get_terrain_heightmap(obj, depsgraph)
                copy_actors.append(create_terrain_info_actor(obj, terrain_scale_z))
            # TODO: add handlers for other object types (outside of this function)
            elif obj.type == 'CAMERA':
                # Create a SpectatorCam actor
                actor = T3DObject('Actor')
                actor['Class'] = 'SpectatorCam'
                actor['Name'] = obj.name
                add_movement_properties_to_actor(actor, obj)
                rotation_euler = actor['Rotation']
                # TODO: make corrective matrix a constant
                # Correct the rotation here since the blender cameras point down -Z with +X up by default.
                rotation_euler.z += math.pi / 2
                rotation_euler.x -= math.pi / 2
                # Adjust the camera's rotation to match the Unreal coordinate system.
                t3d.children.append(actor)
            elif obj.bdk.type == 'BSP_BRUSH':
                # Add the brush to the list of brushes to copy, we have to sort them by sort order.
                bsp_brush_objects.append(obj)
            else:
                if obj.instance_collection:
                    copy_actors += [create_static_mesh_actor(o, obj)
                                    for o in obj.instance_collection.all_objects
                                    if can_copy(o)]
                elif can_copy(obj):
                    copy_actors.append(create_static_mesh_actor(obj))

        for bsp_brush_object in sorted(bsp_brush_objects, key=lambda obj: obj.bdk.bsp_brush.sort_order):
            copy_actors.append(bsp_brush_to_actor(context, bsp_brush_object))

        for actor in copy_actors:
            t3d.children.append(actor)

        string_io = StringIO()
        T3DWriter(string_io).write(t3d)
        string_io.seek(0)

        bpy.context.window_manager.clipboard = string_io.read()

        return {'FINISHED'}


classes = (
    BDK_OT_t3d_copy_to_clipboard,
    BDK_OT_t3d_import_from_file,
    BDK_OT_t3d_import_from_clipboard,
)
