import uuid

import bpy
from bpy.types import Operator, Context, Object

from .builder import create_fluid_surface_node_tree


def create_fluid_surface_object() -> Object:
    # Create a new mesh object and add a geometry node modifier.
    mesh_data = bpy.data.meshes.new(uuid.uuid4().hex)
    fluid_surface_object = bpy.data.objects.new('FluidSurface', mesh_data)
    modifier = fluid_surface_object.modifiers.new(name=uuid.uuid4().hex, type='NODES')
    modifier.node_group = create_fluid_surface_node_tree()
    return fluid_surface_object


class BDK_OT_fluid_surface_add(Operator):
    bl_label = 'Add FluidSurface'
    bl_idname = 'bdk.fluid_surface_add'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context):
        fluid_surface_object = create_fluid_surface_object()
        fluid_surface_object.location = context.scene.cursor.location

        # TODO: Lock the object's scale and delta scale to 1.0.
        fluid_surface_object.lock_scale = (True, True, True)

        context.collection.objects.link(fluid_surface_object)

        return {'FINISHED'}


classes = (
    BDK_OT_fluid_surface_add,
)
