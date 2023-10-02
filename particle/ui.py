from bpy.types import Panel, Context, UIList

from .operators import BDK_OT_particle_system_emitter_add, BDK_OT_particle_system_emitter_remove
from .context import has_selected_particle_emitter, get_selected_particle_emitter


class BDK_PT_particle_emitter(Panel):
    bl_idname = 'BDK_PT_particle_emitter'
    bl_label = 'Emitter'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_parent_id = 'BDK_PT_particle_system'

    @classmethod
    def poll(cls, context: Context):
        return has_selected_particle_emitter(context)

    def draw(self, context: Context):
        pass


class BDK_PT_particle_emitter_general(Panel):
    bl_idname = 'BDK_PT_particle_emitter_general'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'General'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'
    bl_order = 0

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(emitter, 'disable')
        flow.prop(emitter, 'max_particles')
        flow.prop(emitter, 'automatic_initial_spawning')
        flow.prop(emitter, 'particles_per_second')
        flow.prop(emitter, 'scale_size_by_velocity_multiplier')
        flow.prop(emitter, 'scale_size_by_velocity_max')


class BDK_PT_particle_emitter_texture(Panel):
    bl_idname = 'BDK_PT_particle_emitter_texture'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Texture'
    bl_order = 1
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False
        flow.prop(emitter, 'texture')
        flow.prop(emitter, 'draw_style')
        flow.prop(emitter, 'texture_u_subdivisions')
        flow.prop(emitter, 'texture_v_subdivisions')
        flow.prop(emitter, 'blend_between_subdivisions')
        flow.prop(emitter, 'use_random_subdivision')
        flow.prop(emitter, 'use_subdivision_scale')
        if emitter.use_subdivision_scale:
            # TODO: list of scales
            pass
        flow.prop(emitter, 'subdivision_start')
        flow.prop(emitter, 'subdivision_end')

class BDK_PT_particle_emitter_color_and_fading(Panel):
    bl_idname = 'BDK_PT_particle_emitter_color_and_fading'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Color and Fading'
    bl_order = 2
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(emitter, 'opacity')
        flow.prop(emitter, 'fade_in_end_time')
        flow.prop(emitter, 'fade_out_start_time')
        flow.separator()
        flow.prop(emitter, 'fade_out_factor')
        flow.prop(emitter, 'fade_in_factor')
        flow.separator()
        flow.prop(emitter.color_multiplier_range, 'min', text='Color Multiplier Min')
        flow.prop(emitter.color_multiplier_range, 'max')
        flow.separator()
        flow.prop(emitter, 'use_color_scale')
        if emitter.use_color_scale:
            pass
            # TODO: list of color scales
        flow.prop(emitter, 'color_space_repeats')


class BDK_PT_particle_emitter_rendering(Panel):
    bl_idname = 'BDK_PT_particle_emitter_rendering'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Rendering'
    bl_order = 3
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(emitter, 'disable_fogging')
        flow.prop(emitter, 'alpha_test')
        flow.prop(emitter, 'alpha_ref')
        flow.prop(emitter, 'z_test')
        flow.prop(emitter, 'z_write')


class BDK_PT_particle_emitter_time(Panel):
    bl_idname = 'BDK_PT_particle_emitter_time'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Time'
    bl_order = 4
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(emitter.lifetime_range, 'min', text='Lifetime Min')
        flow.prop(emitter.lifetime_range, 'max')
        flow.separator()
        flow.prop(emitter.initial_time_range, 'min', text='Initial Time Min')
        flow.prop(emitter.initial_time_range, 'max')
        flow.separator()
        flow.prop(emitter.initial_delay_range, 'min', text='Initial Delay Min')
        flow.prop(emitter.initial_delay_range, 'max')
        flow.separator()
        flow.prop(emitter, 'seconds_before_inactive')
        flow.separator()
        flow.prop(emitter, 'warmup_relative_time')
        flow.prop(emitter, 'warmup_ticks_per_second')


class BDK_PT_particle_emitter_location(Panel):
    bl_idname = 'BDK_PT_particle_emitter_location'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Location'
    bl_order = 5
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(emitter, 'start_location_shape')
        flow.separator()

        if emitter.start_location_shape == 'PTLS_Box':
            flow.prop(emitter.start_location_range, 'min')
            flow.prop(emitter.start_location_range, 'max')
        elif emitter.start_location_shape == 'PTLS_Sphere':
            flow.prop(emitter.sphere_radius_range, 'min', text='Radius Min')
            flow.prop(emitter.sphere_radius_range, 'max')
        elif emitter.start_location_shape == 'PTLS_Polar':
            flow.prop(emitter.start_location_polar_range, 'min', text='Polar Min')
            flow.prop(emitter.start_location_polar_range, 'max')

        flow.separator()
        flow.prop(emitter, 'start_location_offset')
        flow.separator()
        flow.prop(emitter, 'add_location_from_other_emitter')   # This is an index into the emitters list


class BDK_PT_particle_emitter_movement(Panel):
    bl_idname = 'BDK_PT_particle_emitter_movement'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Movement'
    bl_orderd = 6
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(emitter, 'coordinate_system')
        flow.separator()
        flow.prop(emitter.start_velocity_range, 'min', text='Start Velocity Min')
        flow.prop(emitter.start_velocity_range, 'max')
        flow.separator()
        flow.prop(emitter, 'acceleration')
        flow.separator()
        flow.prop(emitter.velocity_loss_range, 'min', text='Velocity Loss Min')
        flow.prop(emitter.velocity_loss_range, 'max')
        flow.separator()
        flow.prop(emitter, 'max_abs_velocity')
        flow.separator()
        flow.prop(emitter, 'min_squared_velocity')
        flow.separator()
        flow.prop(emitter, 'add_velocity_from_other_emitter')   # This is an index into the emitters list

        if emitter.add_velocity_from_other_emitter != -1:
            flow.prop(emitter.add_velocity_multiplier_range, 'min', text='Add Velocity Multiplier Min')
            flow.prop(emitter.add_velocity_multiplier_range, 'max')

        flow.prop(emitter, 'get_velocity_direction_from')
        flow.separator()
        flow.prop(emitter.start_velocity_radial_range, 'min', text='Start Velocity Radial Min')
        flow.prop(emitter.start_velocity_radial_range, 'max')


class BDK_PT_particle_emitter_rotation(Panel):
    bl_idname = 'BDK_PT_particle_emitter_rotation'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Rotation'
    bl_order = 7
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(emitter, 'spin_particles')

        if emitter.spin_particles:
            flow.prop(emitter.start_spin_range, 'min', text='Start Spin Min')
            flow.prop(emitter.start_spin_range, 'max')
            flow.separator()
            flow.prop(emitter.spins_per_second_range, 'min', 'Spins Per Second Min')
            flow.prop(emitter.spins_per_second_range, 'max')
            flow.separator()
            flow.prop(emitter, 'spin_ccw_or_cw')

        flow.prop(emitter, 'use_direction_as')   # TODO: this is actually called "Facing Direction (pre-spin)"
        if emitter.use_direction_as == 'SPECIFIED_NORMAL':
            flow.prop(emitter, 'projection_normal')

        flow.separator()
        flow.prop(emitter, 'use_rotation_from')

        if emitter.use_rotation_from == 'PTRS_Offset':
            flow.prop(emitter, 'rotation_offset')
        elif emitter.use_rotation_from == 'PTRS_Normal':
            flow.prop(emitter, 'rotation_normal')



class BDK_PT_particle_emitter_size(Panel):
    bl_idname = 'BDK_PT_particle_emitter_size'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Size'
    bl_order = 8
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(emitter, 'uniform_size')
        flow.separator()
        flow.prop(emitter.start_size_range, 'min', text='Start Size Min')
        flow.separator()
        flow.prop(emitter.start_size_range, 'max', text='Max')
        flow.separator()
        flow.prop(emitter, 'use_size_scale')

        if emitter.use_size_scale:
            flow.prop(emitter, 'use_regular_size_scale')
            flow.prop(emitter, 'size_scale_repeats')
            # TODO: list of size scales


class BDK_PT_particle_emitter_collision(Panel):
    bl_idname = 'BDK_PT_particle_emitter_collision'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Collision'
    bl_order = 9
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(emitter, 'use_actor_forces')
        flow.prop(emitter, 'use_collision')

        if emitter.use_collision:
            flow.prop(emitter, 'extent_multiplier')
            flow.separator()
            flow.prop(emitter.damping_factor_range, 'min', text='Damping Factor Min')
            flow.prop(emitter.damping_factor_range, 'max')
            flow.separator()
            flow.prop(emitter, 'damp_rotation')
            if emitter.damp_rotation:
                flow.prop(emitter.rotation_damping_factor_range, 'min', text='Rotation Damping Factor Min')
                flow.prop(emitter.rotation_damping_factor_range, 'max')
            flow.separator()
            flow.prop(emitter, 'use_collision_planes')
            if emitter.use_collision_planes:
                # TODO: list of collision planes
                pass
            flow.prop(emitter, 'use_max_collisions')
            if emitter.use_max_collisions:
                flow.prop(emitter.max_collisions, 'min', text='Max Collisions Min')
                flow.prop(emitter.max_collisions, 'max')
            flow.separator()
            flow.prop(emitter, 'spawn_from_other_emitter')
            flow.separator()
            flow.prop(emitter, 'spawn_amount')
            flow.separator()
            flow.prop(emitter, 'use_spawned_velocity_scale')
            if emitter.use_spawned_velocity_scale:
                flow.prop(emitter.spawned_velocity_scale_range, 'min', text='Spawned Velocity Scale Min')
                flow.prop(emitter.spawned_velocity_scale_range, 'max')
            flow.separator()
            flow.prop(emitter, 'collision_sound')
            if emitter.collision_sound != 'PTCS_None':
                flow.prop(emitter.collision_sound_index, 'min', text='Collision Sound Index Min')
                flow.prop(emitter.collision_sound_index, 'max')
                flow.separator()
                flow.prop(emitter.collision_sound_probability, 'min', text='Collision Sound Probability Min')
                flow.prop(emitter.collision_sound_probability, 'max')
                flow.separator()
                # TODO: collision sound list


class BDK_PT_particle_emitter_mesh(Panel):
    bl_idname = 'BDK_PT_particle_emitter_mesh'
    bl_parent_id = 'BDK_PT_particle_emitter'
    bl_label = 'Mesh'
    bl_order = 10
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    @classmethod
    def poll(cls, context: Context):
        # return has_selected_emitter(context)
        # TODO: not yet implemented
        return False

    def draw(self, context: Context):
        layout = self.layout
        emitter = get_selected_particle_emitter(context)
        flow = layout.grid_flow(columns=1, align=True)
        flow.use_property_split = True
        flow.use_property_decorate = False

        flow.prop(emitter, 'mesh')
        flow.prop(emitter, 'use_mesh_blend_mode')
        flow.prop(emitter, 'render_two_sided')
        flow.prop(emitter, 'use_particle_color')


def has_selected_particle_system(context: Context):
    return context.active_object is not None and context.active_object.bdk.type == 'PARTICLE_SYSTEM'


class BDK_PT_particle_system(Panel):
    bl_idname = 'BDK_PT_particle_system'
    bl_label = 'Particle System'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BDK'

    @classmethod
    def poll(cls, context: Context):
        return has_selected_particle_system(context)

    def draw(self, context: Context):
        layout = self.layout
        row = layout.row()
        row.template_list('BDK_UL_particle_emitters', '', context.active_object.bdk.particle_system, 'emitters', context.active_object.bdk.particle_system, 'emitters_index', rows=3)
        column = row.column(align=True)
        column.operator_menu_enum(BDK_OT_particle_system_emitter_add.bl_idname, 'type', icon='ADD', text='')
        column.operator(BDK_OT_particle_system_emitter_remove.bl_idname, icon='REMOVE', text='')


class BDK_UL_particle_emitters(UIList):
    bl_idname = 'BDK_UL_particle_emitters'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', text='', emboss=False, icon_value=icon)
        layout.prop(item, 'mute', text='', icon='HIDE_OFF' if item.mute else 'HIDE_ON', emboss=False)


classes = (
    BDK_PT_particle_system,
    BDK_PT_particle_emitter,
    BDK_PT_particle_emitter_general,
    BDK_PT_particle_emitter_texture,
    BDK_PT_particle_emitter_color_and_fading,
    BDK_PT_particle_emitter_rendering,
    BDK_PT_particle_emitter_time,
    BDK_PT_particle_emitter_location,
    BDK_PT_particle_emitter_movement,
    BDK_PT_particle_emitter_rotation,
    BDK_PT_particle_emitter_size,
    BDK_PT_particle_emitter_collision,
    # BDK_PT_particle_emitter_mesh,,
    BDK_UL_particle_emitters,
)
