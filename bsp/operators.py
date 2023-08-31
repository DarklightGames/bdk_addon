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


classes = (
    BDK_OT_bsp_brush_add,
    BDK_OT_convert_to_bsp_brush,
    BDK_OT_set_sort_order,
)
