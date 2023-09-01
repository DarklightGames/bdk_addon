import bpy
from bpy.types import Operator
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
        default='ADD',
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
        obj.bdk.type = 'BSP_BRUSH'
        obj.bdk.bsp_brush.csg_operation = self.csg_operation
        obj.bdk.bsp_brush.object = obj
        obj.display_type = 'WIRE'

        # Add the object to the active collection.
        context.collection.objects.link(obj)

        # Select the new object and make it active.
        context.view_layer.objects.active = obj
        obj.select_set(True)

        return {'FINISHED'}


class BDK_OT_set_sort_order(Operator):
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
        if context.active_object.bdk.type != '':
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
        return False
    if context.object.bdk.type != 'BSP_BRUSH':
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
        obj = context.object
        if self.property == 'CSG_OPERATION':
            csg_operation = obj.bdk.bsp_brush.csg_operation
            for obj in context.scene.objects:
                if obj.bdk.type == 'BSP_BRUSH' and obj.bdk.bsp_brush.csg_operation == csg_operation:
                    obj.select_set(True)
        elif self.property == 'POLY_FLAGS':
            poly_flags = obj.bdk.bsp_brush.poly_flags
            for obj in context.scene.objects:
                if obj.bdk.type == 'BSP_BRUSH' and obj.bdk.bsp_brush.poly_flags == poly_flags:
                    obj.select_set(True)
        elif self.property == 'SORT_ORDER':
            sort_order = obj.bdk.bsp_brush.sort_order
            for obj in context.scene.objects:
                if obj.bdk.type == 'BSP_BRUSH' and obj.bdk.bsp_brush.sort_order == sort_order:
                    obj.select_set(True)
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
    BDK_OT_set_sort_order,
    BDK_OT_bsp_brush_select_similar,
    BDK_OT_bsp_brush_snap_to_grid
)
