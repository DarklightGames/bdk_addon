import bpy
from bpy.types import Operator, Context
from bpy.props import StringProperty, FloatProperty
from typing import Union

from .builder import create_projector


def bake_projector(projector_object: bpy.types.Object):
    projector = projector_object.bdk.projector
    modifier = projector_object.modifiers['Projector']
    session_uid = projector_object.session_uid
    for bake in modifier.bakes:
        bpy.ops.object.geometry_node_bake_single(
            session_uid=session_uid,
            modifier_name=modifier.name,
            bake_id=bake.bake_id
        )
    projector.is_baked = True


def unbake_projector(projector_object: bpy.types.Object):
    projector = projector_object.bdk.projector
    modifier = projector_object.modifiers['Projector']
    session_uid = projector_object.session_uid
    for bake in modifier.bakes:
        bpy.ops.object.geometry_node_bake_delete_single(
            session_uid=session_uid,
            modifier_name=modifier.name,
            bake_id=bake.bake_id
        )
    projector.is_baked = False


class BDK_OT_projector_bake(Operator):
    bl_idname = 'bdk.projector_bake'
    bl_label = 'Bake Projector'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        if context.active_object is None or context.active_object.bdk.type != 'PROJECTOR':
            return False
        projector = context.active_object.bdk.projector
        if projector.is_baked:
            cls.poll_message_set(f'Projector is already baked')
            return False
        return True

    def execute(self, context: Context) -> set[str]:
        bake_projector(context.active_object)
        self.report({'INFO'}, 'Baked projector')
        return {'FINISHED'}


class BDK_OT_projector_unbake(Operator):
    bl_idname = 'bdk.projector_unbake'
    bl_label = 'Unbake Projector'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        if context.active_object is None or context.active_object.bdk.type != 'PROJECTOR':
            return False
        projector = context.active_object.bdk.projector
        if not projector.is_baked:
            cls.poll_message_set(f'Projector is not baked')
            return False
        return True

    def execute(self, context: Context) -> set[str]:
        unbake_projector(context.active_object)
        self.report({'INFO'}, 'Unbaked projector')
        return {'FINISHED'}


class BDK_OT_projector_add(Operator):

    bl_idname = 'bdk.projector_add'
    bl_label = 'Add Projector'
    bl_options = {'REGISTER', 'UNDO'}

    target: StringProperty(name='Target')
    material_name: StringProperty(name='Material')
    fov: FloatProperty(name='FOV', default=0.0, min=0.0, max=180.0)
    max_trace_distance: FloatProperty(name='Max Trace Distance', default=1024.0, min=0.0, soft_min=1.0, soft_max=4096.0, subtype='DISTANCE')

    def draw(self, context: Context):
        self.layout.prop_search(self, 'target', bpy.data, 'doodad')
        self.layout.prop_search(self, 'material_name', bpy.data, 'materials')
        self.layout.prop(self, 'fov')
        self.layout.prop(self, 'max_trace_distance')

    def invoke(self, context: 'Context', event: 'Event'):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: Context) -> Union[set[int], set[str]]:

        obj = create_projector(context)
        obj.bdk.projector.material = bpy.data.materials.get(self.material_name, None)
        obj.bdk.projector.fov = self.fov
        obj.bdk.projector.max_trace_distance = self.max_trace_distance
        obj.bdk.projector.target = bpy.data.objects.get(self.target, None)

        # Add the object into the scene and select it.
        context.collection.objects.link(obj)
        context.view_layer.objects.active = obj
        obj.select_set(True)

        return {'FINISHED'}




class BDK_OT_projectors_bake(Operator):
    bl_idname = 'bdk.projectors_bake'
    bl_label = 'Bake Projectors'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> set[str]:
        count = 0
        for obj in context.selected_objects:
            if obj.bdk.type == 'PROJECTOR' and not obj.bdk.projector.is_baked:
                bake_projector(obj)
                count += 1
        if count == 0:
            self.report({'WARNING'}, 'No projectors to bake')
        else:
            self.report({'INFO'}, f'Baked {count} projectors')
        return {'FINISHED'}


class BDK_OT_projectors_unbake(Operator):
    bl_idname = 'bdk.projectors_unbake'
    bl_label = 'Unbake Projectors'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> set[str]:
        count = 0
        for obj in context.selected_objects:
            if obj.bdk.type == 'PROJECTOR' and obj.bdk.projector.is_baked:
                unbake_projector(obj)
                count += 1
        if count == 0:
            self.report({'WARNING'}, 'No projectors to unbake')
        else:
            self.report({'INFO'}, f'Unbaked {count} projectors')
        return {'FINISHED'}


classes = (
    BDK_OT_projector_add,
    BDK_OT_projector_bake,
    BDK_OT_projector_unbake,
    BDK_OT_projectors_bake,
    BDK_OT_projectors_unbake,
)
