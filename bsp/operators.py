from collections import OrderedDict
from enum import Enum

import bpy
from bpy.types import Operator, Object, Context
import bmesh

from .properties import csg_operation_items


class BDK_OT_bsp_brush_add(Operator):
    bl_idname = 'bdk.bsp_brush_add'
    bl_label = 'Add BSP Brush'
    bl_description = 'Add a BSP brush to the scene'
    bl_options = {'REGISTER', 'UNDO'}

    csg_operation: bpy.props.EnumProperty(
        name='CSG Operation',
        items=csg_operation_items,
        default='Csg_Add',
    )

    # TODO: options for shape, size etc.

    def draw(self, context: 'Context'):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, 'csg_operation')

    def execute(self, context):

        # Create a new square mesh object and add it to the scene.
        mesh = bpy.data.meshes.new('Brush')

        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=64.0)
        bm.to_mesh(mesh)

        obj = bpy.data.objects.new('Brush', mesh)
        obj.display_type = 'WIRE'
        obj.bdk.type = 'BSP_BRUSH'
        obj.bdk.bsp_brush.object = obj
        obj.bdk.bsp_brush.csg_operation = self.csg_operation
        obj.bdk.bsp_brush.object = obj

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

    sort_order: bpy.props.IntProperty(
        name='Sort Order',
        default=0,
        min=0,
        max=8,
    )

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

    def execute(self, context):
        obj = context.active_object
        obj.bdk.type = 'BSP_BRUSH'
        obj.bdk.bsp_brush.object = obj
        context.active_object.display_type = 'WIRE'
        return {'FINISHED'}


def poll_is_active_object_bsp_brush(cls, context: 'Context'):
    if context.object is None:
        cls.poll_message_set('No object selected')
        return False
    if context.object.bdk.type != 'BSP_BRUSH':
        cls.poll_message_set('Selected object is not a BSP brush')
        return False
    return True

def poll_has_selected_bsp_brushes(cls, context: 'Context'):
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

    property: bpy.props.EnumProperty(
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

        for obj in filter(filter_function, context.scene.objects):
            obj.select_set(True)

        return {'FINISHED'}


class BDK_OT_bsp_brush_check_for_errors(Operator):
    bl_idname = 'bdk.bsp_brush_check_for_errors'
    bl_label = 'Check BSP Brush for Errors'
    bl_description = 'Check the selected BSP brush for errors'
    bl_options = {'REGISTER', 'UNDO'}

    errors: bpy.props.EnumProperty(
        name='Errors',
        items=(
            ('NOT_MANIFOLD', 'Not Manifold', 'The brush is not manifold'),
            ('NOT_CONVEX', 'Not Convex', 'The brush is not convex')
        ),
        default={'NOT_MANIFOLD', 'NOT_CONVEX'},
        options={'ENUM_FLAG'},
    )
    select: bpy.props.BoolProperty(
        name='Select',
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
        class BspBrushError(Enum):
            NOT_MANIFOLD = 1
            NOT_CONVEX = 2
        object_errors = OrderedDict()
        for obj in context.selected_objects:
            if obj.bdk.type == 'BSP_BRUSH':
                # Check that the object is manifold.
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                if 'NOT_MANIFOLD' in self.errors:
                    for edge_index, edge in enumerate(bm.edges):
                        if not edge.is_manifold:
                            object_errors[obj] = BspBrushError.NOT_MANIFOLD
                if 'NOT_CONVEX' in self.errors:
                    for edge_index, edge in enumerate(bm.edges):
                        if not edge.is_convex:
                            object_errors[obj] = BspBrushError.NOT_CONVEX
                bm.free()
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
    bl_description = 'Snap the selected BSP brushe vertices to the grid'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return poll_has_selected_bsp_brushes(cls, context)

    def execute(self, context):
        obj = context.object
        snap_count = 0
        for obj in context.selected_objects:
            for vertex in obj.data.vertices:
                # Check if any of the vertex coordinates are not on the grid.
                if any(map(lambda v: v % 1 != 0, vertex.co)):
                    snap_count += 1
                vertex.co.x = round(vertex.co.x)
                vertex.co.y = round(vertex.co.y)
                vertex.co.z = round(vertex.co.z)
        self.report({'INFO'}, f'Snapped {snap_count} vertices to the grid')
        return {'FINISHED'}


classes = (
    BDK_OT_bsp_brush_add,
    BDK_OT_convert_to_bsp_brush,
    BDK_OT_bsp_brush_set_sort_order,
    BDK_OT_bsp_brush_select_similar,
    BDK_OT_bsp_brush_snap_to_grid,
    BDK_OT_bsp_brush_check_for_errors
)
