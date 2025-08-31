import math
from io import StringIO
from typing import List, Tuple

import bmesh
import bpy
import numpy
from mathutils import Euler, Matrix, Vector
from bpy.types import Operator, Context, Object
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from ..data import UReference
from ..bsp.properties import get_poly_flags_value_from_keys
from ..bsp.data import POLY_FLAGS_ATTRIBUTE_NAME, TEXTURE_U_ATTRIBUTE_NAME, TEXTURE_V_ATTRIBUTE_NAME, \
    ORIGIN_ATTRIBUTE_NAME
from ..projector.properties import blending_op_blender_to_unreal_map
from ..terrain.exporter import add_movement_properties_to_actor, terrain_info_to_t3d_object, \
    convert_blender_matrix_to_unreal_movement_units
from .data import T3DObject, Polygon
from pathlib import Path
from .importer import import_t3d
from .writer import T3DWriter
from ..helpers import dfs_view_layer_objects, sanitize_name_for_unreal, humanize_size


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
            import_t3d(context.window_manager, context.window_manager.clipboard, context)
            self.report({'INFO'}, f'Imported actors from clipboard')
            return {'FINISHED'}
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except SyntaxError as e:
            print(e)
            self.report({'ERROR'}, 'Clipboard data is not valid T3DMap syntax. Additional debugging information has been '
                                   'written to the console')
            return {'CANCELLED'}


class BDK_OT_t3d_import_from_file(Operator, ImportHelper):
    bl_idname = 'bdk.t3d_import_from_file'
    bl_description = 'Import T3DMap'
    bl_label = 'Import T3DMap (*.t3d)'
    bl_options = {'REGISTER', 'UNDO'}
    filename_ext: StringProperty(default='.t3d', options={'HIDDEN'})
    filter_glob: StringProperty(default='*.t3d', options={'HIDDEN'})
    filepath: StringProperty(
        name='File Path',
        subtype='FILE_PATH',
        description='File path used for importing the T3DMap file',
        maxlen=1024,
        default='')

    def execute(self, context: Context):
        contents = Path(self.filepath).read_text()
        try:
            import_t3d(context.window_manager, contents, context)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        except SyntaxError as e:
            print(e)
            self.report({'ERROR'}, 'File contents are not valid T3DMap syntax. Additional debugging information has '
                                   'been written to the console')
            return {'CANCELLED'}
        self.report({'INFO'}, f'T3DMap Imported successfully')
        return {'FINISHED'}


class ObjectToT3DConverter:
    def can_convert(self, _obj: Object) -> bool:
        return False

    def convert(self, _context: Context, _obj: Object, _matrix_world: Matrix) -> List[T3DObject]:
        raise NotImplementedError


class TerrainDoodadToT3DConverter(ObjectToT3DConverter):
    def can_convert(self, obj: Object) -> bool:
        return obj.bdk.type == 'TERRAIN_DOODAD'

    @staticmethod
    def convert_scatter_layer_to_t3d_objects(context, scatter_layer):
        # Get evaluated mesh data for the seed object.
        mesh_data = scatter_layer.seed_object.evaluated_get(context.evaluated_depsgraph_get()).data
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
            matrix = Matrix.Translation(position) @ Euler(rotation).to_matrix().to_4x4() @ Matrix.Diagonal(
                scale).to_4x4()
            scatter_layer_object = scatter_layer.objects[object_index]
            scatter_layer_object_object = scatter_layer.objects[object_index].object

            actor = T3DObject(type_name='Actor')
            actor.properties['Name'] = scatter_layer_object_object.name
            actor.properties['StaticMesh'] = scatter_layer_object_object.bdk.package_reference

            # Skin Overrides
            for material_slot_index, material_slot in enumerate(scatter_layer_object_object.material_slots):
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

            actor.properties['bAcceptsProjectors'] = actor_properties.accepts_projectors

            # TODO: Individual actors should also have their own group. Just append the groups.
            #  Also make sure that there are no commas, since it's used as a delimiter.
            if scatter_layer.actor_group != '':
                actor.properties['Group'] = scatter_layer.actor_group

            yield actor

    def convert(self, context: Context, obj: Object, matrix_world: Matrix) -> List[T3DObject]:
        terrain_doodad = obj.bdk.terrain_doodad
        actors = []
        for scatter_layer in filter(lambda x: not x.mute, terrain_doodad.scatter_layers):
            actors.extend(self.convert_scatter_layer_to_t3d_objects(context, scatter_layer))
        return actors


class ProjectorToT3DConverter(ObjectToT3DConverter):
    def can_convert(self, obj: Object) -> bool:
        return obj.bdk.type == 'PROJECTOR'

    def convert(self, context: Context, obj: Object, matrix_world: Matrix) -> List[T3DObject]:
        projector = obj.bdk.projector

        actor = T3DObject('Actor')
        actor.properties['Class'] = 'Projector'
        actor.properties['Name'] = obj.name
        actor.properties['MaxTraceDistance'] = projector.max_trace_distance
        actor.properties['FOV'] = int(math.degrees(projector.fov))
        actor.properties['DrawScale'] = projector.draw_scale
        actor.properties['FrameBufferBlendingOp'] = blending_op_blender_to_unreal_map[projector.frame_buffer_blending_op]
        actor.properties['MaterialBlendingOp'] = blending_op_blender_to_unreal_map[projector.material_blending_op]

        if projector.proj_texture is not None:
            actor.properties['ProjTexture'] = projector.proj_texture.bdk.package_reference

        add_movement_properties_to_actor(actor, matrix_world, do_scale=False)

        return [actor]


class FluidSurfaceToT3DConverter(ObjectToT3DConverter):
    def can_convert(self, obj: Object) -> bool:
        return obj.bdk.type == 'FLUID_SURFACE'

    def convert(self, context: Context, obj: Object, matrix_world: Matrix) -> List[T3DObject]:
        fluid_surface = obj.bdk.fluid_surface
        actor = T3DObject(type_name='Actor')
        add_movement_properties_to_actor(actor, matrix_world, do_scale=False)
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
        return [actor]


class TerrainInfoToT3DConverter(ObjectToT3DConverter):
    def can_convert(self, obj: Object) -> bool:
        return obj.bdk.type == 'TERRAIN_INFO'

    def convert(self, context: Context, obj: Object, matrix_world: Matrix) -> List[T3DObject]:
        actor = terrain_info_to_t3d_object(obj, matrix_world)
        return [actor]


class CameraToT3DConverter(ObjectToT3DConverter):
    def can_convert(self, obj: Object) -> bool:
        return obj.type == 'CAMERA'

    def convert(self, context: Context, obj: Object, matrix_world: Matrix) -> List[T3DObject]:
        # Create a SpectatorCam brush_object
        actor = T3DObject('Actor')
        actor.properties['Class'] = 'SpectatorCam'
        actor.properties['Name'] = obj.name
        add_movement_properties_to_actor(actor, matrix_world)
        rotation_euler = actor.properties['Rotation']
        # TODO: make corrective matrix a constant
        # Adjust the camera's rotation to match the Unreal coordinate system.
        # Correct the rotation here since the blender cameras point down -Z with +X up by default.
        rotation_euler.z += math.pi / 2
        rotation_euler.x -= math.pi / 2
        return [actor]


class StaticMeshToT3DConverter(ObjectToT3DConverter):
    def can_convert(self, obj: Object) -> bool:
        return obj.type == 'MESH' and obj.get('Class', None) == 'StaticMeshActor'

    def convert(self, context: Context, obj: Object, matrix_world: Matrix) -> List[T3DObject]:
        actor = T3DObject('Actor')
        actor.properties['Class'] = 'StaticMeshActor'
        actor.properties['Name'] = obj.name
        actor.properties['StaticMesh'] = obj.bdk.package_reference

        add_movement_properties_to_actor(actor, matrix_world)

        # Skin Overrides
        for material_index, material_slot in enumerate(obj.material_slots):
            if material_slot.link == 'OBJECT' \
                    and material_slot.material is not None \
                    and material_slot.material.bdk.package_reference:
                actor.properties[f'Skins({material_index})'] = material_slot.material.bdk.package_reference

        return [actor]


class BspBrushToT3DConverter(ObjectToT3DConverter):
    def can_convert(self, obj: Object) -> bool:
        return obj.bdk.type == 'BSP_BRUSH'

    def convert(self, context: Context, obj: Object, matrix_world: Matrix) -> List[T3DObject]:
        object_name = sanitize_name_for_unreal(obj.name)

        bsp_brush = obj.bdk.bsp_brush

        actor = T3DObject('Actor')
        actor.properties['Class'] = 'Brush'
        actor.properties['Name'] = object_name

        # TODO: Bidirectional mapping would be nice!
        csg_oper = 'CSG_Add'
        match bsp_brush.csg_operation:
            case 'ADD':
                csg_oper = 'CSG_Add'
            case 'SUBTRACT':
                csg_oper = 'CSG_Subtract'

        actor.properties['CsgOper'] = csg_oper
        actor.properties['PolyFlags'] = get_poly_flags_value_from_keys(bsp_brush.poly_flags)

        point_transform_matrix = matrix_world
        location = point_transform_matrix.translation
        location.y = -location.y
        actor.properties['Location'] = location

        brush = T3DObject('Brush')
        brush.properties['Name'] = object_name

        poly_list = T3DObject('PolyList')

        bm = bmesh.new()
        bm.from_object(obj, context.evaluated_depsgraph_get())

        bdk_poly_flags_layer = bm.faces.layers.int.get(POLY_FLAGS_ATTRIBUTE_NAME, None)
        bdk_texture_u_layer = bm.faces.layers.float_vector.get(TEXTURE_U_ATTRIBUTE_NAME, None)
        bdk_texture_v_layer = bm.faces.layers.float_vector.get(TEXTURE_V_ATTRIBUTE_NAME, None)
        bdk_origin_layer = bm.faces.layers.float_vector.get(ORIGIN_ATTRIBUTE_NAME, None)

        """
        In the engine, BSP brushes ignore scale & rotation during the CSG build.
        Therefore, we need to apply the scale and rotation to the vertices of the brush before exporting.
        We let the actor's location handle the translation.
        """
        translation, rotation, scale = point_transform_matrix.decompose()
        point_transform_matrix = rotation.to_matrix().to_4x4() @ Matrix.Diagonal(scale).to_4x4()
        vector_transform_matrix = rotation.to_matrix().to_4x4() @ Matrix.Diagonal(scale).inverted().to_4x4()

        # Calculate normals.
        bm.normal_update()

        for face_index, face in enumerate(bm.faces):
            material = obj.material_slots[face.material_index].material if face.material_index < len(obj.material_slots) else None
            # T3D texture references only have the package and object name.
            texture = UReference.from_string(material.bdk.package_reference) if material else None
            if texture:
                texture = f'{texture.package_name}.{texture.object_name}'

            poly = T3DObject('Polygon')
            poly.properties['Texture'] = texture if texture else 'None'
            poly.properties['Link'] = face_index
            poly.properties['Flags'] = face[bdk_poly_flags_layer] if bdk_poly_flags_layer is not None else 0

            # Apply the transformation matrix to the vertices of the face. Also reverse the order of the vertices to match
            # Unreal's winding order.
            vertices = [point_transform_matrix @ Vector(vert.co) for vert in reversed(face.verts)]
            # Reverse the Y component of the vertices to match Unreal's coordinate system.
            vertices = [(vert.x, -vert.y, vert.z) for vert in vertices]

            texture_u = face[bdk_texture_u_layer] if bdk_texture_u_layer is not None else (1.0, 0.0, 0.0)
            texture_v = face[bdk_texture_v_layer] if bdk_texture_v_layer is not None else (0.0, 1.0, 0.0)
            origin = face[bdk_origin_layer] if bdk_origin_layer is not None else (0.0, 0.0, 0.0)

            # Apply the transformation matrix to the texture U, texture V, and origin.
            texture_u = vector_transform_matrix @ Vector(texture_u)
            texture_v = vector_transform_matrix @ Vector(texture_v)
            origin = point_transform_matrix @ Vector(origin)

            # Reverse the Y component of the TextureU, TextureV, and Origin to match Unreal's coordinate system.
            poly.polygon = Polygon(
                link=face_index,
                origin=Vector((origin.x, -origin.y, origin.z)),
                normal=face.normal,
                texture_u=Vector((texture_u.x, -texture_u.y, texture_u.z)),
                texture_v=Vector((texture_v.x, -texture_v.y, texture_v.z)),
                vertices=vertices,
            )

            poly_list.children.append(poly)

        brush.children.append(poly_list)
        actor.children.append(brush)

        actor.properties['Brush'] = f'Model\'myLevel.{object_name}\''

        return [actor]


object_to_t3d_converters: List[ObjectToT3DConverter] = [
    TerrainDoodadToT3DConverter(),
    ProjectorToT3DConverter(),
    FluidSurfaceToT3DConverter(),
    TerrainInfoToT3DConverter(),
    CameraToT3DConverter(),
    StaticMeshToT3DConverter(),
    BspBrushToT3DConverter(),
]


class BDK_OT_t3d_copy_to_clipboard(Operator):
    bl_idname = 'bdk.t3d_copy_objects_to_clipboard'
    bl_description = 'Copy to clipboard as Unreal T3DMap'
    bl_label = 'Copy as Unreal T3DMap'

    @classmethod
    def poll(cls, context: Context):
        # Return false if no objects are selected.
        if len(context.selected_objects) == 0:
            cls.poll_message_set('No object selected')
            return False
        return True

    def execute(self, context: Context):
        # Use the depth-first iterator to get all the objects in the view layer.
        dfs_objects = list(dfs_view_layer_objects(context.view_layer))

        # Filter only the selected objects.
        selected_objects: List[Tuple[Object, Matrix]] = list()
        for obj, instance_objects, matrix_world in dfs_objects:
            if instance_objects:
                if instance_objects[0].select_get():
                    selected_objects.append((obj, matrix_world))
            else:
                if obj.select_get():
                    selected_objects.append((obj, matrix_world))

        # selected_objects = list(filter(lambda obj: obj[0].select_get() or (obj[1] is not None and obj[1].select_get()), dfs_objects))

        # Start a progress bar.
        wm = context.window_manager
        wm.progress_begin(0, len(selected_objects))

        # Iterate over all the selected objects and attempt to convert them to T3D actors using the registered
        # converters. Note that the order of the converters is important, and that the first converter that can
        # convert the object will be used. Any objects that cannot be converted will be ignored.
        copy_actors: list[T3DObject] = []
        for obj_index, selected_object in enumerate(selected_objects):
            obj, matrix_world = selected_object

            for converter in object_to_t3d_converters:
                if converter.can_convert(obj):
                    copy_actors.extend(converter.convert(context, obj, matrix_world))
                    break

            wm.progress_update(obj_index)

        wm.progress_end()

        # Mark all the actors as selected.
        for actor in copy_actors:
            actor.properties['bSelected'] = True

        # Add the actors to the map object.
        map_object = T3DObject('Map')
        for actor in copy_actors:
            map_object.children.append(actor)

        # Write the map object to a string.
        string_io = StringIO()
        T3DWriter(string_io).write(map_object)
        size = string_io.tell()
        string_io.seek(0)

        if len(copy_actors) == 0:
            self.report({'WARNING'}, 'Current selection does not contain any objects that can be converted to T3D actors')
        else:
            self.report({'INFO'}, f'Copied {len(copy_actors)} actors to clipboard ({humanize_size(size)})')

        contents = string_io.read()

        bpy.context.window_manager.clipboard = contents

        return {'FINISHED'}


classes = (
    BDK_OT_t3d_copy_to_clipboard,
    BDK_OT_t3d_import_from_file,
    BDK_OT_t3d_import_from_clipboard,
)
