from bpy.types import Context


def get_selected_particle_system(context: Context):
    if context.active_object is not None and context.active_object.bdk.type =='PARTICLE_SYSTEM':
        return context.active_object.bdk.particle_system
    return None


def has_selected_particle_system(context: Context):
    return get_selected_particle_system(context) is not None


def get_selected_particle_emitter(context):
    particle_system = get_selected_particle_system(context)
    if particle_system is None:
        return None
    if particle_system.emitters_index < 0 or particle_system.emitters_index >= len(particle_system.emitters):
        return None
    return particle_system.emitters[particle_system.emitters_index]

def has_selected_particle_emitter(context):
    return get_selected_particle_emitter(context) is not None
