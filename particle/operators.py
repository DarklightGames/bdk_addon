import bpy
from bpy.types import Operator, Context
from bpy.props import EnumProperty

from ..helpers import ensure_name_unique
from .context import get_selected_particle_system, has_selected_particle_system
from .properties import emitter_type_items


class BDK_OT_particle_system_add(Operator):
    bl_idname = 'bdk.particle_system_add'
    bl_label = 'Add Particle System'
    bl_description = 'Add a particle system to the scene'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Add a new mesh object at the 3d cursor, link it to the scene, select it, make it active, and set it's BDK type to 'PARTICLE_SYSTEM'

        object_data = bpy.data.meshes.new('ParticleSystem')
        particle_system_object = bpy.data.objects.new('ParticleSystem', object_data)
        context.scene.collection.objects.link(particle_system_object)
        context.view_layer.objects.active = particle_system_object
        particle_system_object.select_set(True)
        particle_system_object.bdk.type = 'PARTICLE_SYSTEM'

        return {'FINISHED'}


class BDK_OT_particle_system_emitter_add(Operator):
    bl_idname = 'bdk.particle_system_emitter_add'
    bl_label = 'Add Particle System Emitter'
    bl_description = 'Add a particle emitter to the particle system'
    bl_options = {'REGISTER', 'UNDO'}

    type: EnumProperty(name='Type', items=emitter_type_items)

    @classmethod
    def poll(cls, context: 'Context'):
        return get_selected_particle_system(context) is not None

    def execute(self, context):
        particle_system = get_selected_particle_system(context)
        emitter =  particle_system.emitters.add()
        emitter.type = self.type
        emitter.name = ensure_name_unique('Emitter', [x.name for x in particle_system.emitters])

        # Select the new emitter.
        particle_system.emitters_index = len(particle_system.emitters) - 1

        return {'FINISHED'}


class BDK_OT_particle_system_emitter_remove(Operator):
    bl_idname = 'bdk.particle_system_emitter_remove'
    bl_label = 'Remove Particle System Emitter'
    bl_description = 'Remove the selected particle emitter from the particle system'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: 'Context'):
        return has_selected_particle_system(context) and context.active_object.bdk.particle_system.emitter_index >= 0

    def execute(self, context):
        particle_system = get_selected_particle_system(context)
        particle_system.emitters.remove(particle_system.emitters_index)
        particle_system.emitters_index = len(particle_system.emitters) - 1
        return {'FINISHED'}


classes = (
    BDK_OT_particle_system_add,
    BDK_OT_particle_system_emitter_add,
    BDK_OT_particle_system_emitter_remove,
)
