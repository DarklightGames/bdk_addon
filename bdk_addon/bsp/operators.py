import numpy as np
from bmesh.types import BMFace
from mathutils import Vector, Matrix

from .builder import ensure_bdk_brush_uv_node_tree, create_bsp_brush_polygon, apply_level_to_brush_mapping, \
    ensure_bdk_level_visibility_modifier
from ..helpers import should_show_bdk_developer_extras, dfs_view_layer_objects, humanize_time
from .data import bsp_optimization_items, ORIGIN_ATTRIBUTE_NAME, TEXTURE_U_ATTRIBUTE_NAME, TEXTURE_V_ATTRIBUTE_NAME, \
    POLY_FLAGS_ATTRIBUTE_NAME, BRUSH_INDEX_ATTRIBUTE_NAME, BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME, \
    MATERIAL_INDEX_ATTRIBUTE_NAME, READ_ONLY_ATTRIBUTE_NAME, bsp_surface_attributes
from .properties import csg_operation_items, poly_flags_items, BDK_PG_bsp_brush, get_poly_flags_keys_from_value
from bpy.props import FloatProperty, EnumProperty, BoolProperty, IntProperty
from bpy.types import Operator, Object, Context, Depsgraph, Mesh, Material, Event
from collections import OrderedDict
from enum import Enum
from typing import cast, List, Optional, Tuple, Set
from bdk_py import Poly, Brush, csg_rebuild, BspBuildOptions
import bmesh
import bpy
import sys
import time

PLANAR_TEXTURE_MAPPING_MODIFIER_NAME = 'BDK Planar Texture Mapping'


def _ensure_planar_texture_mapping_modifier(obj: Object):
    uv_map_modifier = obj.modifiers.get(PLANAR_TEXTURE_MAPPING_MODIFIER_NAME)
    if uv_map_modifier is None:
        uv_map_modifier = obj.modifiers.new(name=PLANAR_TEXTURE_MAPPING_MODIFIER_NAME, type='NODES')
    uv_map_modifier.node_group = ensure_bdk_brush_uv_node_tree()


def _ensure_bsp_brush_object(obj: Object, csg_operation: str = 'ADD'):
    """
    Ensure that the given object is set up as a BSP brush object.
    """
    # TODO: perhaps set these up as drivers instead!
    obj.display_type = 'WIRE'
    obj.show_in_front = True
    obj.show_all_edges = True
    obj.show_wire = True
    obj.display.show_shadows = False
    obj.bdk.type = 'BSP_BRUSH'
    obj.bdk.bsp_brush.object = obj
    obj.bdk.bsp_brush.csg_operation = csg_operation

    _ensure_bdk_brush_attributes(obj.data)
    _ensure_planar_texture_mapping_modifier(obj)


class BDK_OT_bsp_brush_add(Operator):
    bl_idname = 'bdk.bsp_brush_add'
    bl_label = 'Add BSP Brush'
    bl_description = 'Add a BSP brush to the scene'
    bl_options = {'REGISTER', 'UNDO'}

    csg_operation: EnumProperty(name='CSG Operation', items=csg_operation_items, default='ADD')
    size: FloatProperty(name='Size', default=256.0, min=0.0)

    # TODO: options for shape, size etc.

    def draw(self, context: Context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, 'csg_operation')
        layout.prop(self, 'size')

    def execute(self, context):
        # Create a new square mesh object and add it to the scene.
        mesh = bpy.data.meshes.new('Brush')

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=self.size)
        bm.to_mesh(mesh)
        bm.free()

        obj = bpy.data.objects.new('Brush', mesh)

        _ensure_bsp_brush_object(obj, self.csg_operation)

        obj.location = context.scene.cursor.location

        # Add the object to the active collection.
        context.collection.objects.link(obj)

        # Select the new object and make it active.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        return {'FINISHED'}


class BDK_OT_bsp_brush_sort_order_set(Operator):
    bl_idname = 'bdk.set_sort_order'
    bl_label = 'Set BSP Sort Order'
    bl_description = 'Set the sort order of selected BSP brushes'
    bl_options = {'REGISTER', 'UNDO'}

    sort_order: IntProperty(name='Sort Order', default=0, min=0, max=8)

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.bdk.type == 'BSP_BRUSH':
                obj.bdk.bsp_brush.sort_order = self.sort_order
        return {'FINISHED'}


brush_poly_flags_operation_items = (('SET', 'Set', ''), ('ADD', 'Add', ''), ('REMOVE', 'Remove', ''))


class BDK_OT_bsp_brush_poly_flags_set(Operator):
    bl_idname = 'bdk.set_poly_flags'
    bl_label = 'Set BSP Poly Flags'
    bl_description = 'Set the poly flags of selected BSP brushes'
    bl_options = {'REGISTER', 'UNDO'}

    poly_flags: EnumProperty(name='Poly Flags', items=poly_flags_items, options={'ENUM_FLAG'})
    operation: EnumProperty(name='Operation', items=brush_poly_flags_operation_items, default='SET')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, 'operation')

        poly_flags_header, poly_flags_panel = layout.panel('Poly Flags', default_closed=True)
        poly_flags_header.label(text='Poly Flags')

        if poly_flags_panel is not None:
            flow = poly_flags_panel.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
            flow.use_property_split = True
            flow.use_property_decorate = False

            flow.prop(self, 'poly_flags')

    def execute(self, context):
        def set_flags(bsp_brush: BDK_PG_bsp_brush, flags: Set[str]):
            bsp_brush.poly_flags = flags

        def add_flags(bsp_brush: BDK_PG_bsp_brush, flags: Set[str]):
            bsp_brush.poly_flags |= flags

        def remove_flags(bsp_brush: BDK_PG_bsp_brush, flags: Set[str]):
            bsp_brush.poly_flags -= flags

        def get_operation_function(operation: str):
            match operation:
                case 'SET':
                    return set_flags
                case 'ADD':
                    return add_flags
                case 'REMOVE':
                    return remove_flags

        operation_function = get_operation_function(self.operation)

        for obj in context.selected_objects:
            if obj.bdk.type == 'BSP_BRUSH':
                operation_function(obj.bdk.bsp_brush, self.poly_flags)

        return {'FINISHED'}


def _ensure_bdk_brush_attributes(mesh_data: Mesh):
    if ORIGIN_ATTRIBUTE_NAME not in mesh_data.attributes:
        mesh_data.attributes.new(ORIGIN_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE')
    if TEXTURE_U_ATTRIBUTE_NAME not in mesh_data.attributes:
        mesh_data.attributes.new(TEXTURE_U_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE')
    if TEXTURE_V_ATTRIBUTE_NAME not in mesh_data.attributes:
        mesh_data.attributes.new(TEXTURE_V_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE')
    if POLY_FLAGS_ATTRIBUTE_NAME not in mesh_data.attributes:
        mesh_data.attributes.new(POLY_FLAGS_ATTRIBUTE_NAME, 'INT', 'FACE')


def _create_planar_texture_mapping_attributes(obj: Object, texture_width_fallback: int, texture_height_fallback: int):
    """
    Creates and populates the planar texture mapping attributes from the mesh's UV mapping.

    Accurate mapping relies on the texture dimension information that is available in BDK materials. If a face has a
    non-BDK material or the material is missing, the fallback values will be used.
    :param obj: A Blender mesh object.
    :return: The number of faces that were mapped using the fallback texture dimensions.
    """
    if obj.type != 'MESH':
        raise RuntimeError('Object must be a mesh object')

    mesh_data: Mesh = cast(Mesh, obj.data)

    _ensure_bdk_brush_attributes(mesh_data)

    bm = bmesh.new()
    bm.from_mesh(mesh_data)

    uv_layer = bm.loops.layers.uv.verify()

    translation, rotation, scale = obj.matrix_world.decompose()
    rotation_matrix = rotation.to_matrix().to_4x4()
    scale_matrix = Matrix.Diagonal(scale).to_4x4()
    transform_matrix = rotation_matrix @ scale_matrix

    origins = []
    texture_us = []
    texture_vs = []

    unsupported_face_count = 0

    for face in bm.faces:
        texture_width = texture_width_fallback
        texture_height = texture_height_fallback
        if face.material_index >= len(mesh_data.materials):
            unsupported_face_count += 1
        else:
            material = mesh_data.materials[face.material_index]
            if material is None:
                texture_width = 512
                texture_height = 512
            elif material.bdk.package_reference == '':
                unsupported_face_count += 1
            else:
                texture_width = material.bdk.size_x
                texture_height = material.bdk.size_y

        # Calculate the texture plane.
        origin, texture_u, texture_v = create_bsp_brush_polygon(
            texture_width, texture_height, uv_layer, face, transform_matrix
        )

        origins.append(origin)
        texture_us.append(texture_u)
        texture_vs.append(texture_v)

    bm.free()

    mesh_data.attributes[ORIGIN_ATTRIBUTE_NAME].data.foreach_set('vector', np.array(origins).flatten())
    mesh_data.attributes[TEXTURE_U_ATTRIBUTE_NAME].data.foreach_set('vector', np.array(texture_us).flatten())
    mesh_data.attributes[TEXTURE_V_ATTRIBUTE_NAME].data.foreach_set('vector', np.array(texture_vs).flatten())

    return unsupported_face_count


def can_convert_object_to_bsp_brush(obj: Object):
    if obj.type != 'MESH':
        return False
    if obj.bdk.type != 'NONE':
        return False
    return True


class BDK_OT_convert_to_bsp_brush(Operator):
    bl_idname = 'bdk.convert_to_bsp_brush'
    bl_label = 'Convert to BSP Brush'
    bl_description = 'Convert the selected objects to BSP brushes'
    bl_options = {'REGISTER', 'UNDO'}

    csg_operation: EnumProperty(items=csg_operation_items, name='CSG Operation', default='ADD')
    texture_width_fallback: IntProperty(name='Texture Width Fallback', default=512, min=1)
    texture_height_fallback: IntProperty(name='Texture Height Fallback', default=512, min=1)

    @classmethod
    def poll(cls, context):
        for obj in context.selected_objects:
            if can_convert_object_to_bsp_brush(obj):
                return True
        cls.poll_message_set('At least one selected object must be a mesh')
        return False

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, 'csg_operation')
        advanced_header, advanced_panel = layout.panel('Advanced', default_closed=True)
        advanced_header.label(text='Advanced')
        if advanced_panel:
            advanced_panel.prop(self, 'texture_width_fallback')
            advanced_panel.prop(self, 'texture_height_fallback')

    def invoke(self, context: Context, event: Event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        for obj in context.selected_objects:
            if not can_convert_object_to_bsp_brush(obj):
                continue
            # Create the planar texture mapping from the UV mapping.
            bad_face_count = _create_planar_texture_mapping_attributes(
                obj, self.texture_width_fallback, self.texture_height_fallback
            )
            if bad_face_count > 0:
                self.report({'WARNING'}, f'{bad_face_count} faces used fallback texture dimensions')

            # Ensure that the object is set up as a BSP brush object.
            _ensure_bsp_brush_object(obj, self.csg_operation)

        return {'FINISHED'}


def poll_is_active_object_bsp_brush(cls, context: Context):
    if context.object is None:
        cls.poll_message_set('No object selected')
        return False
    if context.object.bdk.type != 'BSP_BRUSH':
        cls.poll_message_set('Selected object is not a BSP brush')
        return False
    return True


def poll_has_selected_bsp_brushes(cls, context: Context):
    if context.selected_objects is None:
        cls.poll_message_set('No objects selected')
        return False
    # Make sure that at least one BSP brush is selected.
    for obj in context.selected_objects:
        if obj.bdk.type == 'BSP_BRUSH':
            return True
    cls.poll_message_set('No BSP brushes selected')
    return False


class BDK_OT_bsp_brush_select_similar(Operator):
    bl_idname = 'bdk.bsp_brush_select_similar'
    bl_label = 'Select Similar BSP Brushes'
    bl_description = 'Select all BSP brushes with similar properties'
    bl_options = {'REGISTER', 'UNDO'}

    property: EnumProperty(
        name='Property',
        items=(
            ('CSG_OPERATION', 'CSG Operation', 'The CSG operation of the brush'),
            ('POLY_FLAGS', 'Poly Flags', 'The poly flags of the brush'),
            ('SORT_ORDER', 'Sort Order', 'The sort order of the brush'),
        ),
    )

    @classmethod
    def poll(cls, context):
        if not poll_is_active_object_bsp_brush(cls, context):
            return False
        return True

    def execute(self, context):
        active_object = context.object
        bsp_brush = active_object.bdk.bsp_brush

        if self.property == 'CSG_OPERATION':
            def filter_csg_operation(obj: Object):
                return obj.bdk.bsp_brush.csg_operation == bsp_brush.csg_operation

            filter_function = filter_csg_operation
        elif self.property == 'POLY_FLAGS':
            def filter_poly_flags(obj: Object):
                return obj.bdk.bsp_brush.poly_flags == bsp_brush.poly_flags

            filter_function = filter_poly_flags
        elif self.property == 'SORT_ORDER':
            def filter_sort_order(obj: Object):
                return obj.bdk.bsp_brush.sort_order == bsp_brush.sort_order

            filter_function = filter_sort_order
        else:
            self.report({'ERROR'}, f'Invalid property: {self.property}')
            return {'CANCELLED'}

        for obj in filter(filter_function, filter(lambda x: x.bdk.type == 'BSP_BRUSH', context.scene.objects)):
            obj.select_set(True)

        return {'FINISHED'}


class BspBrushError(Enum):
    NOT_MANIFOLD = 1
    NOT_CONVEX = 2
    TWISTED_FACE = 3


def get_bsp_brush_errors(obj: Object, depsgraph: Depsgraph) -> List[Tuple[BspBrushError, int]]:
    """
    Check the given object for errors and return a set of all the errors that were found.
    """
    evaluated_obj = obj.evaluated_get(depsgraph)
    errors = list()
    bm = bmesh.new()
    bm.from_object(evaluated_obj, depsgraph)

    poly_flags = obj.bdk.bsp_brush.poly_flags

    should_check_manifold = poly_flags.isdisjoint({'PORTAL'})
    if should_check_manifold:
        for edge_index, edge in enumerate(bm.edges):
            if not edge.is_manifold:
                errors.append((BspBrushError.NOT_MANIFOLD, edge_index))
                break

    should_check_convex = poly_flags.isdisjoint({'PORTAL', 'SEMI_SOLID'})
    if should_check_convex:
        for edge_index, edge in enumerate(bm.edges):
            if not edge.is_convex:
                errors.append((BspBrushError.NOT_CONVEX, edge_index))
                break

    # This value is copied from the BSP build code.
    # TODO: Have these constants available to import from bdk_py.
    THRESH_NORMALS_ARE_SAME = 0.00002

    def _is_face_twisted(face: BMFace, threshold: float = THRESH_NORMALS_ARE_SAME):
        """
        Return true if a face is "twisted". A twisted face is one where the triangles that make up the face have normals
        that differ by greater than the specified threshold.

        :param face: The face to check.
        :param threshold: The threshold to test against. This is compared against the dot product delta.
        :return: Returns `True` if the face is twisted, `False` if it is not.
        """
        if len(face.verts) <= 3:
            return False

        normals = set()
        for i in range(len(face.verts) - 2):
            a = face.verts[i + 1].co - face.verts[i].co
            b = face.verts[i + 2].co - face.verts[i + 1].co
            normal = a.cross(b).normalized().freeze()
            normals.add(normal)
        normals = list(normals)

        # Compare each normal against the first one. This ensures the checks are stable and that errors do not compound.
        for normal in normals[1:]:
            dot_product = normals[0].dot(normal)
            diff = abs(1.0 - dot_product)
            if diff > threshold:
                return True

        return False

    # Check for polygons whose triangulated faces have differing normals. This is the classic "twisted quad" scenario
    # that can lead to BSP holes.
    for face_index, face in enumerate(bm.faces):
        if _is_face_twisted(face):
            errors.append((BspBrushError.TWISTED_FACE, face_index))
            break

    bm.free()

    return errors


class BDK_OT_bsp_brush_check_for_errors(Operator):
    bl_idname = 'bdk.bsp_brush_check_for_errors'
    bl_label = 'Check BSP Brush for Errors'
    bl_description = 'Check the selected BSP brush for errors'
    bl_options = {'REGISTER', 'UNDO'}

    deselect_ok: BoolProperty(
        name='Deselect Brushes Without Errors',
        description='Deselect brushes that do not have any errors',
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return poll_has_selected_bsp_brushes(cls, context)

    def draw(self, context: Context):
        layout = self.layout
        layout.prop(self, 'deselect_ok')

    def execute(self, context):
        depsgraph = context.evaluated_depsgraph_get()
        object_errors = OrderedDict()

        brush_objects = [obj for obj in context.selected_objects if obj.bdk.type == 'BSP_BRUSH']

        context.window_manager.progress_begin(0, len(brush_objects))

        for obj_index, obj in enumerate(brush_objects):
            bsp_brush_errors = get_bsp_brush_errors(obj, depsgraph)
            if bsp_brush_errors:
                object_errors[obj] = bsp_brush_errors
            context.window_manager.progress_update(obj_index)

        if len(object_errors) > 0:
            self.report({'ERROR'}, f'Found {len(object_errors)} brush(es) with errors')
            for obj, errors in object_errors.items():
                for (error, index) in errors:
                    print(error, index)
                    if error == BspBrushError.NOT_MANIFOLD:
                        self.report({'ERROR'}, f'{obj.name}: Edge {index} is not manifold')
                    elif error == BspBrushError.NOT_CONVEX:
                        self.report({'ERROR'}, f'{obj.name}: Edge {index} is not convex')
                    elif error == BspBrushError.TWISTED_FACE:
                        self.report({'ERROR'}, f'{obj.name}: Face {index} is twisted')
            if self.deselect_ok:
                # Go through all selected objects and deselect those that don't have errors.
                for obj in context.selected_objects:
                    if obj not in object_errors:
                        obj.select_set(False)
        else:
            self.report({'INFO'}, 'No errors found')

        context.window_manager.progress_end()

        return {'FINISHED'}


class BDK_OT_bsp_brush_snap_to_grid(Operator):
    bl_idname = 'bdk.bsp_brush_snap_to_grid'
    bl_label = 'Snap BSP Brush to Grid'
    bl_description = 'Snap the selected BSP brush vertices to the grid'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return poll_has_selected_bsp_brushes(cls, context)

    def execute(self, context):
        snap_count = 0
        for obj in context.selected_objects:
            if obj.bdk.type != 'BSP_BRUSH':
                continue
            mesh_data = cast(Mesh, obj.data)
            for vertex in mesh_data.vertices:
                # Check if any of the vertex coordinates are not on the grid.
                if any(map(lambda v: v % 1 != 0, vertex.co)):
                    snap_count += 1
                vertex.co.x = round(vertex.co.x)
                vertex.co.y = round(vertex.co.y)
                vertex.co.z = round(vertex.co.z)
        self.report({'INFO'}, f'Snapped {snap_count} vertices to the grid')
        return {'FINISHED'}


class BDK_OT_select_brushes_inside(Operator):
    bl_idname = 'bdk.select_brushes_inside'
    bl_label = 'Select Brushes Inside'
    bl_description = 'Select all BSP brushes that are inside the active BSP brush'
    bl_options = {'REGISTER', 'UNDO'}

    deselect_active: BoolProperty(
        name='Deselect Active',
        description='Deselect the active brush',
        default=True,
    )
    visible_only: BoolProperty(
        name='Visible Only',
        description='Only select brushes that are visible',
        default=True,
    )
    point_on_plane_threshold: FloatProperty(
        name='Planar Threshold',
        description='Threshold for determining if a point is on a plane',
        default=0.1,
        min=0.0,
        step=0.1
    )
    filter: EnumProperty(
        name='Filter',
        items=(
            ('INSIDE', 'Inside', 'Select brushes that are inside the active brush'),
            ('INTERSECT', 'Intersect', 'Select brushes that intersect the active brush'),
            ('DISJOINT', 'Disjoint', 'Select brushes that are disjoint from the active brush'),
            ('TOUCH', 'Touch', 'Select brushes that touch the active brush'),
        ),
        options={'ENUM_FLAG'},
        default={'INSIDE', 'INTERSECT'},
    )

    @classmethod
    def poll(cls, context):
        if not poll_is_active_object_bsp_brush(cls, context):
            return False
        return True

    def execute(self, context):
        depsgraph = context.evaluated_depsgraph_get()
        brush_errors = get_bsp_brush_errors(context.active_object, depsgraph)

        if brush_errors:
            self.report({'ERROR'}, 'Active brush has errors')
            return {'CANCELLED'}

        # Get the planes of all the faces of the active brush.
        active_object = context.object
        planes = []
        bm = bmesh.new()
        bm.from_object(active_object, depsgraph, vertex_normals=False)
        for face in bm.faces:
            origin = face.verts[0].co.copy()
            normal = face.normal.copy()
            planes.append((origin, normal))
        bm.free()

        # Iterate over all BSP brushes in the scene and select those that are inside the active brush.
        for obj in context.scene.objects:

            if obj.bdk.type != 'BSP_BRUSH' or obj == active_object:
                continue

            if self.visible_only and not obj.visible_get():
                continue

            bm = bmesh.new()
            bm.from_object(obj, depsgraph)

            inside_count = 0
            outside_count = 0
            on_plane_count = 0

            for vertex_index, vertex in enumerate(bm.verts):
                max_t = -sys.float_info.max

                for plane_index, (origin, normal) in enumerate(planes):
                    max_t = max(max_t, normal.dot(vertex.co - origin))

                if max_t > self.point_on_plane_threshold:
                    outside_count += 1
                elif max_t < -self.point_on_plane_threshold:
                    inside_count += 1
                else:
                    on_plane_count += 1

            bm.free()

            print(f'{obj.name}: inside={inside_count}, outside={outside_count}, on_plane={on_plane_count}')

            if 'INSIDE' in self.filter and inside_count > 0 and outside_count == 0:
                obj.select_set(True)
            elif 'DISJOINT' in self.filter and inside_count == 0 and outside_count > 0 and on_plane_count == 0:
                obj.select_set(True)
            elif 'INTERSECT' in self.filter and inside_count > 0 and (outside_count > 0 or on_plane_count > 0):
                obj.select_set(True)
            elif 'TOUCH' in self.filter and inside_count == 0 and on_plane_count > 0:
                obj.select_set(True)

        if self.deselect_active:
            active_object.select_set(False)

        return {'FINISHED'}


class BDK_OT_bsp_build(Operator):
    bl_idname = 'bdk.bsp_build'
    bl_label = 'Build Level'
    bl_description = 'Build the level'
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    bsp_optimization: EnumProperty(name='Optimization', items=bsp_optimization_items, default='LAME')
    bsp_balance: IntProperty(name='Balance', default=15, min=0, max=100, description='Balance of the BSP tree')
    bsp_portal_bias: IntProperty(name='Portal Bias', default=70, min=0, max=100, description='Portal cutting strength')

    should_do_only_visible: BoolProperty(name='Only Visible', default=False)
    should_do_geometry: BoolProperty(name='Geometry', default=True)
    should_do_bsp: BoolProperty(name='BSP', default=True)
    should_do_lighting: BoolProperty(name='Lighting', default=True)
    should_dither_lightmaps: BoolProperty(name='Dither', default=True)
    lightmap_format: EnumProperty(
        name='Lightmap Format',
        items=(
            ('DXT1', 'DXT1', ''),
            ('DXT3', 'DXT3', ''),
            ('RGB8', 'RGB8', ''),
        ),
        default='RGB8',
    )

    should_optimize_geometry: BoolProperty(name='Optimize Geometry', default=True)

    def draw(self, context):
        layout = self.layout

        geometry_header, geometry_panel = layout.panel_prop(self, 'should_do_geometry')
        geometry_header.prop(self, 'should_do_geometry', text='Geometry')
        if geometry_panel is not None:
            geometry_panel.use_property_split = True
            geometry_panel.use_property_decorate = False
            geometry_panel.prop(self, 'should_do_only_visible')

        bsp_header, bsp_panel = layout.panel_prop(self, 'should_do_bsp')
        bsp_header.prop(self, 'should_do_bsp', text='BSP')
        if bsp_panel is not None:
            bsp_panel.use_property_split = True
            bsp_panel.use_property_decorate = False
            bsp_panel.prop(self, 'bsp_optimization')
            bsp_panel.prop(self, 'bsp_balance')
            bsp_panel.prop(self, 'bsp_portal_bias')

        # TODO: Lighting is not yet implemented, so this is disabled.
        # lighting_header, lighting_panel = layout.panel_prop(self, 'should_do_lighting')
        # lighting_header.prop(self, 'should_do_lighting', text='Lighting')
        # if lighting_panel is not None:
        #     lighting_panel.use_property_split = True
        #     lighting_panel.use_property_decorate = False
        #     lighting_panel.prop(self, 'lightmap_format')
        #     lighting_panel.prop(self, 'should_dither_lightmaps')

        if should_show_bdk_developer_extras(context):
            debug_header, debug_panel = layout.panel('Debug', default_closed=True)
            debug_header.label(text='Debug')
            if debug_panel:
                debug_panel.use_property_split = True
                debug_panel.use_property_decorate = False
                debug_panel.prop(self, 'should_optimize_geometry')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        # Go to object mode, if we are not already in object mode.
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Iterate over all the BSP brushes in the scene and create a list of all the brush objects.
        context.view_layer.update()
        scene = context.scene

        # The user may have deleted the old object, but the scene could still be referencing it.
        # If the linked level object is not None, but it is not linked in the scene, unlink it so a new one is created.
        if scene.bdk.level_object is not None and scene.bdk.level_object.name not in scene.objects:
            scene.bdk.level_object = None

        if scene.bdk.level_object is None:
            # Create a new mesh object to hold the level geometry.
            mesh_data = bpy.data.meshes.new('Level')
            level_object = bpy.data.objects.new('Level', mesh_data)
            level_object.bdk.type = 'LEVEL'
            level_object.lock_location = (True, True, True)
            level_object.lock_rotation = (True, True, True)
            level_object.lock_scale = (True, True, True)

            # Add the object to the top-most collection.
            collection = scene.collection
            collection.objects.link(level_object)

            # Set the level object in the scene.1
            scene.bdk.level_object = level_object

        level_object = scene.bdk.level_object

        # Apply the texturing to the brushes.
        result = apply_level_to_brush_mapping(level_object)
        brush_faces_textured_count = result.face_count
        for error in result.errors:
            self.report({'WARNING'}, str(error))

        def brush_object_filter(obj: Object, instance_objects: List[Object]):
            if not obj.bdk.type == 'BSP_BRUSH':
                return False
            if self.should_do_only_visible:
                if instance_objects:
                    if not instance_objects[0].visible_get():
                        return False
                elif not obj.visible_get():
                    return False
            return True

        brush_objects = [(obj, instance_objects, matrix_world) for (obj, instance_objects, matrix_world) in
                         dfs_view_layer_objects(context.view_layer) if brush_object_filter(obj, instance_objects)]

        # This is a list of the materials used for the brushes. It is populated as we iterate over the brush objects.
        # We then use this at the end to create the materials for the level object.
        materials: List[Optional[Material]] = []

        def _get_or_add_material(material: Optional[Material]) -> int:
            try:
                return materials.index(material)
            except ValueError:
                materials.append(material)
                return len(materials) - 1

        # Add the brushes to the level object.
        level_object.bdk.level.brushes.clear()

        for brush_index, (brush_object, instance_collections, _) in enumerate(brush_objects):
            is_instanced_brush = len(instance_collections) > 0
            if is_instanced_brush:
                # Skip brushes that are instanced, as we cannot change their texturing.
                continue
            level_brush = level_object.bdk.level.brushes.add()
            level_brush.index = brush_index
            level_brush.brush_object = brush_object

        timer = time.time()

        # A list of brush indices that are instances and not the original brush object.
        # We keep track of these so that we can mark these brushes and their associated BSP surface as read-only in the
        # level object and exclude them from BSP surface tool operations.
        instanced_brush_indices = []

        brushes: List[Brush] = []
        for brush_index, (brush_object, asset_instances, matrix_world) in enumerate(brush_objects):

            if asset_instances:
                instanced_brush_indices.append(brush_index)

            # Create a new Poly object for each face of the brush.
            polys = []
            mesh_data = brush_object.data

            polygon_count = len(mesh_data.polygons)

            # Origin
            origin_data = np.zeros(polygon_count * 3, dtype=np.float32)
            mesh_data.attributes.get(ORIGIN_ATTRIBUTE_NAME).data.foreach_get('vector', origin_data)
            origin_data = origin_data.reshape((polygon_count, 3))

            # Texture U
            texture_u_data = np.zeros(polygon_count * 3, dtype=np.float32)
            mesh_data.attributes.get(TEXTURE_U_ATTRIBUTE_NAME).data.foreach_get('vector', texture_u_data)
            texture_u_data = texture_u_data.reshape((polygon_count, 3))

            # Texture V
            texture_v_data = np.zeros(polygon_count * 3, dtype=np.float32)
            mesh_data.attributes.get(TEXTURE_V_ATTRIBUTE_NAME).data.foreach_get('vector', texture_v_data)
            texture_v_data = texture_v_data.reshape((polygon_count, 3))

            # Poly Flags
            poly_flags_data = np.zeros(polygon_count, dtype=np.int32)
            mesh_data.attributes.get(POLY_FLAGS_ATTRIBUTE_NAME).data.foreach_get('value', poly_flags_data)

            # Transform the origin and texture vectors to world-space.
            # TODO: extract this to a function so we can re-use it in the remapping operator.

            point_transform_matrix = matrix_world @ brush_object.matrix_local
            translation, rotation, scale = point_transform_matrix.decompose()
            vector_transform_matrix = rotation.to_matrix().to_4x4() @ Matrix.Diagonal(scale).inverted().to_4x4()

            origin_data = [point_transform_matrix @ Vector(origin) for origin in origin_data]
            texture_u_data = [vector_transform_matrix @ Vector(texture_u) for texture_u in texture_u_data]
            texture_v_data = [vector_transform_matrix @ Vector(texture_v) for texture_v in texture_v_data]

            for polygon in mesh_data.polygons:
                vertices = []
                for vertex_index in polygon.vertices:
                    co = mesh_data.vertices[vertex_index].co
                    # Convert brush geometry to world-space.
                    co = point_transform_matrix @ co
                    x, y, z = co
                    vertices.append((x, y, z))

                # Get the material index for the polygon.
                material = mesh_data.materials[polygon.material_index] if polygon.material_index < len(
                    mesh_data.materials) else None
                material_index = _get_or_add_material(material)

                polys.append(Poly(
                    vertices,
                    origin=tuple(origin_data[polygon.index]),
                    texture_u=tuple(texture_u_data[polygon.index]),
                    texture_v=tuple(texture_v_data[polygon.index]),
                    poly_flags=get_poly_flags_keys_from_value(poly_flags_data[polygon.index]),
                    material_index=material_index,
                ))

            brush = Brush(id=brush_index,
                          name=brush_object.name,
                          polys=polys,
                          poly_flags=brush_object.bdk.bsp_brush.poly_flags,
                          csg_operation=brush_object.bdk.bsp_brush.csg_operation
                          )

            brushes.append(brush)

        if not brushes:
            self.report({'WARNING'}, 'No brushes to build')
            return {'CANCELLED'}

        # TODO: Display a warning if the first brush's operation is not a subtraction.

        level = level_object.bdk.level
        level.performance.object_serialization_duration = time.time() - timer

        start_time = time.time()

        context.window_manager.progress_begin(0, 1)

        # Rebuild the level geometry.
        try:
            options = BspBuildOptions()
            options.bsp_optimization = self.bsp_optimization
            options.bsp_balance = self.bsp_balance
            options.bsp_portal_bias = self.bsp_portal_bias
            options.do_geometry = self.should_do_geometry
            options.do_bsp = self.should_do_bsp
            options.do_lighting = self.should_do_lighting
            options.dither_lightmaps = self.should_dither_lightmaps
            options.lightmap_format = self.lightmap_format
            options.should_optimize_geometry = self.should_optimize_geometry

            def progress_cb():
                print('we called the progress callback')
                context.window_manager.progress_update(0.5)

            model = csg_rebuild(brushes, options, progress_callback=progress_cb)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        context.window_manager.progress_end()

        level.performance.csg_build_duration = time.time() - start_time

        # Update statistics.
        level.statistics.node_count = len(model.nodes)
        level.statistics.brush_count = len(brushes)
        level.statistics.depth_count = model.stats.depth_count
        level.statistics.depth_max = model.stats.depth_max
        level.statistics.depth_average = model.stats.depth_average

        # Build the mesh.
        timer = time.time()
        bm = bmesh.new()

        for point in model.points:
            bm.verts.new(point)

        bm.verts.ensure_lookup_table()

        # Pre-allocate the arrays for the number of faces.
        valid_node_count = 0
        for node in model.nodes:
            if node.vertex_count > 0:
                valid_node_count += 1

        brush_ids = np.zeros(valid_node_count, dtype=np.int32)
        brush_polygon_indices = np.zeros(valid_node_count, dtype=np.int32)
        material_indices = np.zeros(valid_node_count, dtype=np.int32)
        origins = np.zeros((valid_node_count, 3), dtype=np.float32)
        texture_us = np.zeros((valid_node_count, 3), dtype=np.float32)
        texture_vs = np.zeros((valid_node_count, 3), dtype=np.float32)
        poly_flags = np.zeros(valid_node_count, dtype=np.int32)
        read_only = np.zeros(valid_node_count, dtype=np.bool_)

        # NOTE: For the sake of performance, we copy the data from the model to numpy arrays instead of accessing them
        #  directly. It is dramatically slower if accessed directly (1500ms vs 45ms). There is probably some sort of
        #  overhead or inefficiency in the way the data is accessed in the model object.
        vertices = np.array(model.vertices)
        points = np.array(model.points)
        vectors = np.array(model.vectors)

        invalid_face_indices = []

        # Convert the list of instanced brush indices to a set for faster lookups.
        instanced_brush_indices = set(instanced_brush_indices)

        node_index = 0
        for node in model.nodes:
            if node.vertex_count == 0:
                continue

            point_indices = [vert.point_index for vert in
                             vertices[node.vertex_pool_index:node.vertex_pool_index + node.vertex_count]]

            try:
                bm.faces.new(map(lambda i: bm.verts[i], point_indices))

                surface = model.surfaces[node.surface_index]
                brush_ids[node_index] = surface.brush_id
                brush_polygon_indices[node_index] = surface.brush_polygon_index
                material_indices[node_index] = surface.material_index
                read_only[node_index] = surface.brush_id in instanced_brush_indices

                origins[node_index] = points[surface.base_point_index]
                texture_us[node_index] = vectors[surface.texture_u_index]
                texture_vs[node_index] = vectors[surface.texture_v_index]
                poly_flags[node_index] = surface.poly_flags

            except ValueError:
                invalid_face_indices.append(node_index)

            node_index += 1

        if invalid_face_indices:
            self.report({'WARNING'}, f'Discarded {len(invalid_face_indices)} duplicate faces')

        # Remove the data at the indices that were not added to the mesh due to invalid faces.
        brush_ids = np.delete(brush_ids, invalid_face_indices)
        brush_polygon_indices = np.delete(brush_polygon_indices, invalid_face_indices)
        material_indices = np.delete(material_indices, invalid_face_indices)
        origins = np.delete(origins, invalid_face_indices, axis=0)
        texture_us = np.delete(texture_us, invalid_face_indices, axis=0)
        texture_vs = np.delete(texture_vs, invalid_face_indices, axis=0)
        poly_flags = np.delete(poly_flags, invalid_face_indices)
        read_only = np.delete(read_only, invalid_face_indices)

        mesh_data = cast(Mesh, level_object.data)
        bm.to_mesh(mesh_data)
        bm.free()

        level.performance.mesh_build_duration = time.time() - timer

        # Add references to brush polygons as face attributes.
        # TODO: add section index. this way, when we make edits to the texturing, we can apply it to all the faces in
        #  the associated section.

        # Create materials for the level object.
        mesh_data.materials.clear()
        for material in materials:
            mesh_data.materials.append(material)

        # Add references to brush polygons as face attributes.
        for (name, type, domain) in bsp_surface_attributes:
            mesh_data.attributes.new(name, type, domain)

        # NOTE: Rather than using the reference returned from `attributes.new`, we need to do the lookup again.
        #  This is because references to the attributes are not stable across calls to `attributes.new`.
        mesh_data.attributes[BRUSH_INDEX_ATTRIBUTE_NAME].data.foreach_set('value', brush_ids)
        mesh_data.attributes[BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME].data.foreach_set('value', brush_polygon_indices)
        mesh_data.attributes[ORIGIN_ATTRIBUTE_NAME].data.foreach_set('vector', origins.flatten())
        mesh_data.attributes[TEXTURE_U_ATTRIBUTE_NAME].data.foreach_set('vector', texture_us.flatten())
        mesh_data.attributes[TEXTURE_V_ATTRIBUTE_NAME].data.foreach_set('vector', texture_vs.flatten())
        mesh_data.attributes[MATERIAL_INDEX_ATTRIBUTE_NAME].data.foreach_set('value', material_indices)
        mesh_data.attributes[POLY_FLAGS_ATTRIBUTE_NAME].data.foreach_set('value', poly_flags)
        mesh_data.attributes[READ_ONLY_ATTRIBUTE_NAME].data.foreach_set('value', read_only)

        # Make sure the level object has the UV geometry node modifier.
        _ensure_planar_texture_mapping_modifier(level_object)
        ensure_bdk_level_visibility_modifier(level_object)

        end_time = time.time()
        duration = end_time - start_time

        self.report({'INFO'}, f'Level built in {humanize_time(duration)} | {brush_faces_textured_count} brush faces changed')

        for region in context.area.regions:
            region.tag_redraw()

        return {'FINISHED'}


class BDK_OT_bsp_brush_demote(Operator):
    bl_idname = 'bdk.bsp_brush_demote'
    bl_label = 'Demote BSP Brush'
    bl_description = 'Demote the selected BSP brush'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.active_object is None:
            cls.poll_message_set('No object selected')
            return False
        if context.active_object.bdk.type != 'BSP_BRUSH':
            cls.poll_message_set('Selected object is not a BSP brush')
            return False
        return True

    def execute(self, context):
        obj = context.active_object
        obj.bdk.type = 'NONE'
        return {'FINISHED'}


class BDK_OT_bsp_brush_operation_toggle(Operator):
    bl_idname = 'bdk.bsp_brush_operation_toggle'
    bl_label = 'Toggle BSP Brush Operation'
    bl_description = 'Toggle the CSG operation of the active BSP brush'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return poll_is_active_object_bsp_brush(cls, context)

    def execute(self, context: Context):
        bsp_brush = context.active_object.bdk.bsp_brush
        match bsp_brush.csg_operation:
            case 'ADD':
                bsp_brush.csg_operation = 'SUBTRACT'
            case 'SUBTRACT':
                bsp_brush.csg_operation = 'ADD'
        return {'FINISHED'}


select_with_poly_flags_mode_items = (
    ('ALL', 'All', 'Select BSP brushes that have all the specified poly flags'),
    ('ANY', 'Any', 'Select BSP brushes that have any of the specified poly flags'),
    ('NONE', 'None', 'Select BSP brushes that do not have any of the specified poly flags'),
)


class BDK_OT_bsp_brush_select_with_poly_flags(Operator):
    bl_idname = 'bdk.bsp_brush_select_with_poly_flags'
    bl_label = 'Select BSP Brushes with Poly Flags'
    bl_description = 'Select all BSP brushes with the specified poly flags'
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(name='Mode', items=select_with_poly_flags_mode_items, default='ALL')
    poly_flags: EnumProperty(name='Poly Flags', items=poly_flags_items, options={'ENUM_FLAG'})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'mode')

        flow = layout.grid_flow(row_major=True, columns=2, even_columns=True, even_rows=True, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(self, 'poly_flags')

    def execute(self, context: Context):
        bsp_brush_objects = [obj for obj in context.scene.objects if obj.bdk.type == 'BSP_BRUSH']

        def all_filter_function(poly_flags: int):
            return poly_flags & self.poly_flags == self.poly_flags

        def any_filter_function(poly_flags: int):
            return poly_flags & self.poly_flags != 0

        def none_filter_function(poly_flags: int):
            return poly_flags & self.poly_flags == 0

        match self.mode:
            case 'ALL':
                filter_function = all_filter_function
            case 'ANY':
                filter_function = any_filter_function
            case _:  # NONE
                filter_function = none_filter_function

        for obj in bsp_brush_objects:
            if not filter_function(obj.bdk.bsp_brush.poly_flags):
                continue
            obj.select_set(True)

        return {'FINISHED'}


class BDK_OT_ensure_tool_operators(Operator):
    bl_idname = 'bdk.ensure_tool_operators'
    bl_label = 'Ensure Tool Operators'
    bl_description = 'Ensure that the tool operators are registered'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from .tools import ensure_bdk_bsp_tool_node_trees
        ensure_bdk_bsp_tool_node_trees()
        return {'FINISHED'}


classes = (
    BDK_OT_bsp_brush_add,
    BDK_OT_bsp_brush_check_for_errors,
    BDK_OT_bsp_brush_operation_toggle,
    BDK_OT_bsp_brush_select_similar,
    BDK_OT_bsp_brush_select_with_poly_flags,
    BDK_OT_bsp_brush_poly_flags_set,
    BDK_OT_bsp_brush_sort_order_set,
    BDK_OT_bsp_brush_snap_to_grid,
    BDK_OT_bsp_build,
    BDK_OT_convert_to_bsp_brush,
    BDK_OT_select_brushes_inside,
    BDK_OT_bsp_brush_demote,
    BDK_OT_ensure_tool_operators,
)
