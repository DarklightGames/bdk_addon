import numpy as np
from mathutils import Vector, Quaternion, Matrix

from .builder import ensure_bdk_brush_uv_node_tree
from ..helpers import is_bdk_py_installed
from .data import bsp_optimization_items
from .properties import csg_operation_items
from bpy.props import FloatProperty, EnumProperty, BoolProperty, IntProperty
from bpy.types import Operator, Object, Context, Depsgraph, Mesh, Material
from collections import OrderedDict
from enum import Enum
from typing import Set, cast, List, Optional
import bmesh
import bpy
import sys
import time

BRUSH_INDEX_ATTRIBUTE_NAME = 'bdk.brush_index'
BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME = 'bdk.brush_polygon_index'
ORIGIN_ATTRIBUTE_NAME = 'bdk.origin'
TEXTURE_U_ATTRIBUTE_NAME = 'bdk.texture_u'
TEXTURE_V_ATTRIBUTE_NAME = 'bdk.texture_v'
MATERIAL_INDEX_ATTRIBUTE_NAME = 'material_index'


def ensure_bsp_brush_object(obj: Object, csg_operation: str = 'ADD'):
    """
    Ensure that the given object is set up as a BSP brush object.
    """
    # obj.display_type = 'WIRE'
    obj.show_in_front = True
    obj.show_all_edges = True
    obj.show_wire = True
    obj.display.show_shadows = False
    obj.bdk.type = 'BSP_BRUSH'
    obj.bdk.bsp_brush.object = obj
    obj.bdk.bsp_brush.csg_operation = csg_operation


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

        poly_flags_attribute = mesh.attributes.new('bdk.poly_flags', 'INT', 'FACE')

        obj = bpy.data.objects.new('Brush', mesh)
        _ensure_bsp_brush_object(obj, self.csg_operation)

        obj.location = context.scene.cursor.location

        # Add the object to the active collection.
        context.collection.objects.link(obj)

        # Select the new object and make it active.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        return {'FINISHED'}


class BDK_OT_bsp_brush_set_sort_order(Operator):
    bl_idname = 'bdk.set_sort_order'
    bl_label = 'Set BSP Sort Order'
    bl_description = 'Set the sort order of selected BSP brushes'
    bl_options = {'REGISTER', 'UNDO'}

    sort_order: IntProperty(name='Sort Order', default=0, min=0, max=8)

    @classmethod
    def poll(cls, context):
        if context.selected_objects is None:
            return False
        # Make sure that at least one BSP brush is selected.
        for obj in context.selected_objects:
            if obj.bdk.type == 'BSP_BRUSH':
                return True
        return False

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.bdk.type == 'BSP_BRUSH':
                obj.bdk.bsp_brush.sort_order = self.sort_order
        return {'FINISHED'}


class BDK_OT_convert_to_bsp_brush(Operator):
    bl_idname = 'bdk.convert_to_bsp_brush'
    bl_label = 'Convert to BSP Brush'
    bl_description = 'Convert the active object to a BSP brush'
    bl_options = {'REGISTER', 'UNDO'}

    csg_operation: EnumProperty(
        name='CSG Operation',
        items=csg_operation_items,
        default='ADD',
    )

    @classmethod
    def poll(cls, context):
        if context.active_object is None:
            return False
        if context.active_object.type != 'MESH':
            cls.poll_message_set('Object is not a mesh')
            return False
        if context.active_object.bdk.type != 'NONE':
            cls.poll_message_set('Object is already a BDK object')
            return False
        return True

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, 'csg_operation')

    def execute(self, context):
        _ensure_bsp_brush_object(context.active_object, self.csg_operation)
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

        def is_bsp_brush(obj: Object):
            return obj.bdk.type == 'BSP_BRUSH'

        if self.property == 'CSG_OPERATION':
            def filter_csg_operation(obj: Object):
                return is_bsp_brush(obj) and obj.bdk.bsp_brush.csg_operation == bsp_brush.csg_operation
            filter_function = filter_csg_operation
        elif self.property == 'POLY_FLAGS':
            def filter_poly_flags(obj: Object):
                return is_bsp_brush(obj) and obj.bdk.bsp_brush.poly_flags == bsp_brush.poly_flags
            filter_function = filter_poly_flags
        elif self.property == 'SORT_ORDER':
            def filter_sort_order(obj: Object):
                return is_bsp_brush(obj) and obj.bdk.bsp_brush.sort_order == bsp_brush.sort_order
            filter_function = filter_sort_order
        else:
            self.report({'ERROR'}, f'Invalid property: {self.property}')
            return {'CANCELLED'}

        for obj in filter(filter_function, context.scene.objects):
            obj.select_set(True)

        return {'FINISHED'}


class BspBrushError(Enum):
    NOT_MANIFOLD = 1
    NOT_CONVEX = 2


def get_bsp_brush_errors(obj: Object, depsgraph: Depsgraph) -> Set[BspBrushError]:
    """
    Check the given object for errors and return a set of all the errors that were found.
    """
    evaluated_obj = obj.evaluated_get(depsgraph)
    errors = set()
    bm = bmesh.new()
    bm.from_object(evaluated_obj, depsgraph)
    for edge in bm.edges:
        if not edge.is_manifold:
            errors.add(BspBrushError.NOT_MANIFOLD)
        if not edge.is_convex:
            errors.add(BspBrushError.NOT_CONVEX)
    bm.free()
    return errors


class BDK_OT_bsp_brush_check_for_errors(Operator):
    bl_idname = 'bdk.bsp_brush_check_for_errors'
    bl_label = 'Check BSP Brush for Errors'
    bl_description = 'Check the selected BSP brush for errors'
    bl_options = {'REGISTER', 'UNDO'}

    select: BoolProperty(
        name='Selected',
        description='Select the object if it has errors',
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return poll_has_selected_bsp_brushes(cls, context)

    def draw(self, context: Context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, 'errors')
        layout.prop(self, 'select')

    def execute(self, context):
        depsgraph = context.evaluated_depsgraph_get()
        object_errors = OrderedDict()
        for obj in context.selected_objects:
            if obj.bdk.type == 'BSP_BRUSH':
                bsp_brush_errors = get_bsp_brush_errors(obj, depsgraph)
                if BspBrushError.NOT_MANIFOLD in bsp_brush_errors:
                    object_errors[obj] = BspBrushError.NOT_MANIFOLD
                if BspBrushError.NOT_CONVEX in bsp_brush_errors:
                    object_errors[obj] = BspBrushError.NOT_CONVEX
        if object_errors:
            self.report({'ERROR'}, f'Found {len(object_errors)} errors')
            for obj, error in object_errors.items():
                if error == BspBrushError.NOT_MANIFOLD:
                    self.report({'ERROR'}, f'{obj.name}: Not manifold')
                elif error == BspBrushError.NOT_CONVEX:
                    self.report({'ERROR'}, f'{obj.name}: Not convex')
            if self.select:
                # Go through all selected objects and deselect those that don't have errors.
                for obj in context.selected_objects:
                    if obj not in object_errors:
                        obj.select_set(False)
        self.report({'INFO'}, 'No errors found')
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
        step=0.1,
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

    bsp_optimization: EnumProperty(
        name='Optimization',
        items=bsp_optimization_items,
        default='LAME',
    )
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

        lighting_header, lighting_panel = layout.panel_prop(self, 'should_do_lighting')
        lighting_header.prop(self, 'should_do_lighting', text='Lighting')
        if lighting_panel is not None:
            lighting_panel.use_property_split = True
            lighting_panel.use_property_decorate = False
            lighting_panel.prop(self, 'lightmap_format')
            lighting_panel.prop(self, 'should_dither_lightmaps')


    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        # Make sure that the bdk_py module is available.
        # TODO: Move this to the poll function once we are done debugging.
        if not is_bdk_py_installed():
            self.report({'ERROR'}, 'bdk_py module is not installed')
            return {'CANCELLED'}

        from bdk_py import Poly, Brush, csg_rebuild

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

        def brush_object_filter(obj: Object):
            if not obj.bdk.type == 'BSP_BRUSH':
                return False
            if self.should_do_only_visible and not obj.visible_get():
                return False
            return True

        brush_objects = [obj for obj in context.scene.objects if brush_object_filter(obj)]

        # TODO: Make an algorithm that sorts the brushes based on the hierarchy first, then sort order of siblings.
        # TODO: Evaluate the brush objects in the depsgraph.

        # This is a list of the materials used for the brushes. It is populated as we iterate over the brush objects.
        # We then use this at the end to create the materials for the level object.
        materials: List[Optional[Material]] = []

        def _get_or_add_material(material: Optional[Material]) -> int:
            try:
                return materials.index(material)
            except ValueError:
                materials.append(material)
                return len(materials) - 1

        brushes: List[Brush] = []
        for brush_index, brush_object in enumerate(brush_objects):
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

            # Transform the origin and texture vectors to world-space.
            point_transform_matrix = brush_object.matrix_world
            translation, rotation, scale = brush_object.matrix_world.decompose()
            vector_transform_matrix = rotation.to_matrix().to_4x4() @ Matrix.Diagonal(scale).inverted().to_4x4()
            origin_data = [point_transform_matrix @ Vector(origin) for origin in origin_data]
            texture_u_data = [vector_transform_matrix @ Vector(texture_u) for texture_u in texture_u_data]
            texture_v_data = [vector_transform_matrix @ Vector(texture_v) for texture_v in texture_v_data]

            for polygon in mesh_data.polygons:
                # vertex_indices = [v for v in polygon.vertices]
                vertices = []
                for vertex_index in polygon.vertices:
                    co = mesh_data.vertices[vertex_index].co
                    # Convert brush geometry to world-space.
                    co = point_transform_matrix @ co
                    x, y, z = co
                    vertices.append((x, y, z))

                # Get the material index for the polygon.
                material = mesh_data.materials[polygon.material_index]
                material_index = _get_or_add_material(material)

                polys.append(Poly(
                    vertices,
                    origin=tuple(origin_data[polygon.index]),
                    texture_u=tuple(texture_u_data[polygon.index]),
                    texture_v=tuple(texture_v_data[polygon.index]),
                    poly_flags=set(),   # TODO: populate this with a set of flags (e.g., {'INVISIBLE', 'TWO_SIDED'})
                    material_index=material_index,
                ))

            brush = Brush(id=brush_index,
                          name=brush_object.name,
                          polys=polys,
                          poly_flags=brush_object.bdk.bsp_brush.poly_flags,
                          csg_operation=brush_object.bdk.bsp_brush.csg_operation)

            brushes.append(brush)

        # Start a timer.
        start_time = time.time()

        # Rebuild the level geometry.
        try:
            model = csg_rebuild(brushes)
        except RuntimeError as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        duration = time.time() - start_time

        bdk_level = level_object.bdk.level

        # Update statistics.
        bdk_level.node_count = len(model.nodes)
        bdk_level.surface_count = len(model.surfaces)
        bdk_level.vertex_count = len(model.vertices)
        bdk_level.point_count = len(model.points)

        bm = bmesh.new()

        for point in model.points:
            bm.verts.new(point)

        bm.verts.ensure_lookup_table()

        brush_ids = []
        brush_polygon_indices = []
        origins = []
        texture_us = []
        texture_vs = []
        material_indices = []

        for node in model.nodes:
            if node.vertex_count == 0:
                continue
            vertices = model.vertices[node.vertex_pool_index:node.vertex_pool_index + node.vertex_count]
            point_indices = [vert.vertex_index for vert in vertices]
            surface = model.surfaces[node.surface_index]
            bm.faces.new([bm.verts[i] for i in point_indices])

            brush_ids.append(surface.brush_id)
            brush_polygon_indices.append(surface.brush_polygon_index)
            origins.append(model.points[surface.base_point_index])
            texture_us.append(model.vectors[surface.texture_u_index])
            texture_vs.append(model.vectors[surface.texture_v_index])
            material_indices.append(surface.material_index)

        mesh_data = cast(Mesh, level_object.data)
        bm.to_mesh(mesh_data)
        bm.free()

        # Create materials for the level object.
        mesh_data.materials.clear()
        for material in materials:
            mesh_data.materials.append(material)

        # Add references to brush polygons as face attributes.
        mesh_data.attributes.new(BRUSH_INDEX_ATTRIBUTE_NAME, 'INT', 'FACE')
        mesh_data.attributes.new(BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME, 'INT', 'FACE')
        mesh_data.attributes.new(ORIGIN_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE')
        mesh_data.attributes.new(TEXTURE_U_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE')
        mesh_data.attributes.new(TEXTURE_V_ATTRIBUTE_NAME, 'FLOAT_VECTOR', 'FACE')
        mesh_data.attributes.new(MATERIAL_INDEX_ATTRIBUTE_NAME, 'INT', 'FACE')

        # NOTE: Rather than using the reference returned from `attributes.new`, we need to do the lookup again.
        #  This is because references to the attributes are not stable across calls to `attributes.new`.
        mesh_data.attributes[BRUSH_INDEX_ATTRIBUTE_NAME].data.foreach_set('value', brush_ids)
        mesh_data.attributes[BRUSH_POLYGON_INDEX_ATTRIBUTE_NAME].data.foreach_set('value', brush_polygon_indices)
        mesh_data.attributes[ORIGIN_ATTRIBUTE_NAME].data.foreach_set('vector', np.array(origins).flatten())
        mesh_data.attributes[TEXTURE_U_ATTRIBUTE_NAME].data.foreach_set('vector', np.array(texture_us).flatten())
        mesh_data.attributes[TEXTURE_V_ATTRIBUTE_NAME].data.foreach_set('vector', np.array(texture_vs).flatten())
        mesh_data.attributes[MATERIAL_INDEX_ATTRIBUTE_NAME].data.foreach_set('value', material_indices)

        for region in context.area.regions:
            region.tag_redraw()

        # Make sure the level object has the UV geometry node modifier.
        uv_map_modifier = level_object.modifiers.get('BDK Level UV Mapping')
        if uv_map_modifier is None:
            uv_map_modifier = level_object.modifiers.new(name='BDK Level UV Mapping', type='NODES')
        uv_map_modifier.node_group = ensure_bdk_brush_uv_node_tree()

        self.report({'INFO'}, f'Level built in {duration:.4f} seconds')

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


classes = (
    BDK_OT_bsp_brush_add,
    BDK_OT_bsp_brush_check_for_errors,
    BDK_OT_bsp_brush_select_similar,
    BDK_OT_bsp_brush_set_sort_order,
    BDK_OT_bsp_brush_snap_to_grid,
    BDK_OT_bsp_build,
    BDK_OT_convert_to_bsp_brush,
    BDK_OT_select_brushes_inside,
    BDK_OT_bsp_brush_demote,
)
