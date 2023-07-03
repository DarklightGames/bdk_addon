import math
import uuid

import bpy
from bpy.types import Operator, Context, Material, Object
from bpy.props import StringProperty, FloatProperty
from typing import Union, Set, Optional

from .builder import build_projector_node_tree


class BDK_OT_projector_add(Operator):

    bl_idname = 'bdk.projector_add'
    bl_label = 'Add Projector'
    bl_options = {'REGISTER', 'UNDO'}

    target: StringProperty(name='Target')
    material_name: StringProperty(name='Material')
    fov: FloatProperty(name='FOV', default=90.0, min=0.0, max=180.0)
    max_trace_distance: FloatProperty(name='Max Trace Distance', default=1024.0, min=0.0, soft_min=1.0, soft_max=4096.0, subtype='DISTANCE')

    def draw(self, context: Context):
        self.layout.prop_search(self, 'target', bpy.data, 'doodad')
        self.layout.prop_search(self, 'material_name', bpy.data, 'materials')
        self.layout.prop(self, 'fov')
        self.layout.prop(self, 'max_trace_distance')

    def invoke(self, context: 'Context', event: 'Event'):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: Context) -> Union[Set[int], Set[str]]:

        # Add a new mesh object at the 3D cursor.
        mesh_data = bpy.data.meshes.new(name=uuid.uuid4().hex)

        bpy_object = bpy.data.objects.new("Projector", mesh_data)
        bpy_object.location = context.scene.cursor.location

        material: Optional[Material] = None
        try:
            material = bpy.data.materials[self.material_name]
        except KeyError:
            pass

        target: Optional[Object] = None
        try:
            target = bpy.data.objects[self.target]
        except KeyError:
            pass

        # Rotate the projector so that it is facing down.
        bpy_object.rotation_euler = (0.0, math.pi / 2, 0.0)

        bpy_object['Class'] = 'Projector'
        bpy_object['FOV'] = 90.0
        bpy_object['MaxTraceDistance'] = 1024.0
        bpy_object['DrawScale'] = 1.0

        modifier = bpy_object.modifiers.new(name='Projector', type='NODES')
        modifier.node_group = build_projector_node_tree()

        # TODO: lookup the keys for named inputs.
        modifier["Input_0"] = target
        modifier["Input_4"] = material
        modifier["Input_5"] = material['UClamp'] if material else 256
        modifier["Input_6"] = material['VClamp'] if material else 256

        # Deselect all doodad.
        for obj in context.selected_objects:
            obj.select_set(False)

        # Add the object into the scene and select it.
        context.collection.objects.link(bpy_object)
        context.view_layer.objects.active = bpy_object
        bpy_object.select_set(True)

        return {'FINISHED'}


classes = (
    BDK_OT_projector_add,
)
