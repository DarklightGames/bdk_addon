import uuid

import bpy
from bpy.types import Operator, Context, Object

from .builder import ensure_fluid_surface_node_tree


def create_fluid_surface_object(name: str) -> Object:
    # Create a new mesh object and add a geometry node modifier.
    mesh_data = bpy.data.meshes.new(uuid.uuid4().hex)
    fluid_surface_object = bpy.data.objects.new(name, mesh_data)
    fluid_surface_object.bdk.type = 'FLUID_SURFACE'
    fluid_surface_object.bdk.fluid_surface.id = uuid.uuid4().hex
    fluid_surface_object.bdk.fluid_surface.object = fluid_surface_object

    modifier = fluid_surface_object.modifiers.new(name=uuid.uuid4().hex, type='NODES')
    modifier.node_group = ensure_fluid_surface_node_tree(fluid_surface_object.bdk.fluid_surface)

    return fluid_surface_object


class BDK_OT_fluid_surface_add(Operator):
    bl_label = 'Add FluidSurface'
    bl_idname = 'bdk.fluid_surface_add'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context):
        fluid_surface_object = create_fluid_surface_object('FluidSurfaceInfo')
        fluid_surface_object.location = context.scene.cursor.location

        # TODO: Lock the object's scale and delta scale to 1.0.
        fluid_surface_object.lock_scale = (True, True, True)

        context.collection.objects.link(fluid_surface_object)

        return {'FINISHED'}


classes = (
    BDK_OT_fluid_surface_add,
)
