from bpy.props import FloatProperty, FloatVectorProperty, BoolProperty, CollectionProperty, IntProperty, \
    PointerProperty, EnumProperty, StringProperty

from .data import *
from bpy.types import PropertyGroup, Object, Material, Sound


coordinate_system_items = (
    ('PTCS_Independent', 'Independent', '', 0, ParticleCoordinateSystem.Independent.value),
    ('PTCS_Relative', 'Relative', '', 0, ParticleCoordinateSystem.Relative.value),
    ('PTCS_Absolute', 'Absolute', '', 0, ParticleCoordinateSystem.Absolute.value)
)

print(coordinate_system_items)

effect_axis_items = (
    ('NegativeX', 'Negative X', '', 0, ParticleEffectAxis.NegativeX.value),
    ('PositiveY', 'Positive Y', '', 0, ParticleEffectAxis.PositiveY.value)
)

detail_mode_items = (
    ('Low', 'Low', '', 0, DetailMode.Low.value),
    ('High', 'High', '', 0, DetailMode.High.value),
    ('SuperHigh', 'Super High', '', 0, DetailMode.SuperHigh.value)
)

particle_draw_style_items = (
    ('PTDS_Regular', 'Regular', '', 0, ParticleDrawStyle.Regular.value),
    ('PTDS_AlphaBlend', 'Alpha Blend', '', 0, ParticleDrawStyle.AlphaBlend.value),
    ('PTDS_Modulated', 'Modulated', '', 0, ParticleDrawStyle.Modulated.value),
    ('PTDS_Translucent', 'Translucent', '', 0, ParticleDrawStyle.Translucent.value),
    ('PTDS_AlphaModulate_MightNotFogCorrectly', 'Alpha Modulate (Might Not Fog Correctly)', '', 0, ParticleDrawStyle.AlphaModulate_MightNotFogCorrectly.value),
    ('PTDS_Darken', 'Darken', '', 0, ParticleDrawStyle.Darken.value),
    ('PTDS_Brighten', 'Brighten', '', 0, ParticleDrawStyle.Brighten.value)
)

start_location_shape_items = (
    ('PTLS_Box', 'Box', '', 0, ParticleStartLocationShape.Box.value),
    ('PTLS_Sphere', 'Sphere', '', 0, ParticleStartLocationShape.Sphere.value),
    ('PTLS_Polar', 'Polar', '', 0, ParticleStartLocationShape.Polar.value),
    # ('PTLS_All', 'All', '', 0,  ParticleStartLocationShape.All.value)
)

mesh_spawning_items = (
    ('PTMS_None', 'None', '', 0, ParticleMeshSpawning.None_.value),
    ('PTMS_Linear', 'Linear', '', 0, ParticleMeshSpawning.Linear.value),
    ('PTMS_Random', 'Random', '', 0, ParticleMeshSpawning.Random.value)
)

particle_rotation_source_items = (
    ('PTRS_None', 'None', '', 0, ParticleRotationSource.None_.value),
    ('PTRS_Actor', 'Actor', '', 0, ParticleRotationSource.Actor.value),
    ('PTRS_Offset', 'Offset', '', 0, ParticleRotationSource.Offset.value),
    ('PTRS_Normal', 'Normal', '', 0, ParticleRotationSource.Normal.value)
)

skel_location_update_items = (
    ('PTSU_None', 'None', '', 0, ParticleSkelLocationUpdate.None_.value),
    ('PTSU_SpawnOffset', 'Spawn Offset', '', 0, ParticleSkelLocationUpdate.SpawnOffset.value),
    ('PTSU_Location', 'Location', '', 0, ParticleSkelLocationUpdate.Location.value)
)

particle_collision_sound_items = (
    ('PTSC_None', 'None', '', 0, ParticleCollisionSound.None_.value),
    ('PTSC_LinearGlobal', 'Linear Global', '', 0, ParticleCollisionSound.LinearGlobal.value),
    ('PTSC_LinearLocal', 'Linear Local', '', 0, ParticleCollisionSound.LinearLocal.value),
    ('PTSC_Random', 'Random', '', 0, ParticleCollisionSound.Random.value)
)

particle_velocity_direction_items = (
    ('PTVD_None', 'None', '', 0, ParticleVelocityDirection.None_.value),
    ('PTVD_StartPositionAndOwner', 'Start Position And Owner', '', 0, ParticleVelocityDirection.StartPositionAndOwner.value),
    ('PTVD_OwnerAndStartPosition', 'Owner And Start Position', '', 0, ParticleVelocityDirection.OwnerAndStartPosition.value),
    ('PTVD_AddRadial', 'Add Radial', '', 0, ParticleVelocityDirection.AddRadial.value)
)

particle_direction_usage_items = (
    ('PTDU_None', 'None', '', 0, ParticleDirectionUsage.None_.value),
    ('PTDU_Up', 'Up', '', 0, ParticleDirectionUsage.Up.value),
    ('PTDU_Right', 'Right', '', 0, ParticleDirectionUsage.Right.value),
    ('PTDU_Forward', 'Forward', '', 0, ParticleDirectionUsage.Forward.value),
    ('PTDU_Normal', 'Normal', '', 0, ParticleDirectionUsage.Normal.value),
    ('PTDU_UpAndNormal', 'Up And Normal', '', 0, ParticleDirectionUsage.UpAndNormal.value),
    ('PTDU_RightAndNormal', 'Right And Normal', '', 0, ParticleDirectionUsage.RightAndNormal.value),
    ('PTDU_Scale', 'Scale', '', 0, ParticleDirectionUsage.Scale.value)
)

class BDK_PG_particle_time_scale(PropertyGroup):
    relative_time: FloatProperty(name='Relative Time', default=0.0, min=0.0, max=1.0)
    relative_size: FloatProperty(name='Relative Size')


class BDK_PG_particle_revolution_scale(PropertyGroup):
    relative_time: FloatProperty(name='Relative Time', default=0.0, min=0.0, max=1.0)
    relative_revolution: FloatVectorProperty(name='Relative Revolution', size=3)


class BDK_PG_particle_color_scale(PropertyGroup):
    relative_time: FloatProperty(name='Relative Time', default=0.0, min=0.0, max=1.0)
    color: FloatVectorProperty(name='Relative Color', subtype='COLOR', size=4)


class BDK_PG_particle_velocity_scale(PropertyGroup):
    relative_time: FloatProperty(name='Relative Time', default=0.0, min=0.0, max=1.0)
    velocity: FloatVectorProperty(name='Relative Velocity', size=3)


class BDK_PG_plane(PropertyGroup):
    normal: FloatVectorProperty(name='Normal', size=3)
    distance: FloatProperty(name='Distance')


class BDK_PG_range(PropertyGroup):
    min: FloatProperty(name='Min')
    max: FloatProperty(name='Max')


class BDK_PG_range_vector(PropertyGroup):
    min: FloatVectorProperty(name='Min', size=3)
    max: FloatVectorProperty(name='Max', size=3)

class BDK_PG_particle_sound(PropertyGroup):
    sound: PointerProperty(name='Sound', type=Sound)
    radius: PointerProperty(name='Radius', type=BDK_PG_range)
    pitch: PointerProperty(name='Pitch', type=BDK_PG_range)
    weight: IntProperty(name='Weight', min=0)
    volume: PointerProperty(name='Volume', type=BDK_PG_range)
    probability: PointerProperty(name='Probability', type=BDK_PG_range)


class BDK_PG_particle_subdivision_scale(PropertyGroup):
    value: FloatProperty(name='Value')


emitter_type_items = (
    ('BEAM', 'Beam', ''),
    ('MESH', 'Mesh', ''),
    ('SPARK', 'Spark', ''),
    ('SPRITE', 'Sprite', '')
)


class BDK_PG_particle_emitter(PropertyGroup):

    type: EnumProperty(name='Type', items=emitter_type_items, default='SPRITE')

    # Collision
    use_collision: BoolProperty(name='Use Collision', default=False)
    use_collision_planes: BoolProperty(name='Use Collision Planes', default=False)
    use_max_collisions: BoolProperty(name='Use Max Collisions', default=False)
    use_spawned_velocity_scale: BoolProperty(name='Use Spawned Velocity Scale', default=False)
    extent_multiplier: FloatVectorProperty(name='Extent Multiplier', size=3)
    damping_factor_range: PointerProperty(name='Damping Factor Range', type=BDK_PG_range_vector)
    collision_planes: CollectionProperty(name='Collision Planes', type=BDK_PG_plane)
    max_collisions: PointerProperty(name='Max Collisions', type=BDK_PG_range)
    spawn_from_other_emitter: IntProperty(name='Spawn From Other Emitter', default=-1)
    spawn_amount: IntProperty(name='Spawn Amount', min=0)
    spawned_velocity_scale_range: PointerProperty(name='Spawned Velocity Scale Range', type=BDK_PG_range_vector)

    # Fading
    fade_out: BoolProperty(name='Fade Out', default=False)
    fade_in: BoolProperty(name='Fade In', default=False)
    fade_out_factor: FloatVectorProperty(name='Fade Out Factor', size=4, subtype='COLOR')
    fade_out_start_time: FloatProperty(name='Fade Out Start Time', default=1.0)
    fade_in_factor: FloatVectorProperty(name='Fade In Factor', size=4, subtype='COLOR')
    fade_in_end_time: FloatProperty(name='Fade In End Time')

    # Force
    use_actor_forces: BoolProperty(name='Use Actor Forces', default=False)

    # Local
    respawn_dead_particles: BoolProperty(name='Respawn Dead Particles', default=False)
    auto_destroy: BoolProperty(name='Auto Destroy', default=False)
    auto_reset: BoolProperty(name='Auto Reset', default=False)
    disabled: BoolProperty(name='Disabled', default=False)
    disable_fogging: BoolProperty(name='Disable Fogging', default=False)

    # Mesh Spawning
    velocity_from_mesh: BoolProperty(name='Velocity From Mesh', default=False)
    uniform_mesh_scale: BoolProperty(name='Uniform Mesh Scale', default=False)
    uniform_velocity_scale: BoolProperty(name='Uniform Velocity Scale', default=False)
    use_color_from_mesh: BoolProperty(name='Use Color From Mesh', default=False)
    spawn_only_in_direction_of_normal: BoolProperty(name='Spawn Only In Direction Of Normal', default=False)

    # Rendering
    alpha_test: BoolProperty(name='Alpha Test', default=False)
    accepts_projectors: BoolProperty(name='Accepts Projectors', default=False)
    z_test: BoolProperty(name='Z Test', default=True)
    z_write: BoolProperty(name='Z Write', default=False)

    # Revolution
    use_revolution: BoolProperty(name='Use Revolution', default=False)
    use_revolution_scale: BoolProperty(name='Use Revolution Scale', default=False)

    # Rotation
    spin_particles: BoolProperty(name='Spin Particles', default=False)
    damp_rotation: BoolProperty(name='Damp Rotation', default=False)

    # Size
    use_size_scale: BoolProperty(name='Use Size Scale', default=True)
    use_absolute_time_for_size_scale: BoolProperty(name='Use Absolute Time For Size Scale', default=False)
    use_regular_size_scale: BoolProperty(name='Shrink Particles Exponentially', default=False)
    uniform_size: BoolProperty(name='Uniform Size', default=True)
    determine_velocity_by_location_difference: BoolProperty(name='Determine Velocity By Location Difference', default=False)
    scale_size_x_by_velocity: BoolProperty(name='Scale Size X By Velocity', default=False)
    scale_size_y_by_velocity: BoolProperty(name='Scale Size Y By Velocity', default=False)
    scale_size_z_by_velocity: BoolProperty(name='Scale Size Z By Velocity', default=False)

    # Spawning
    automatic_initial_spawning: BoolProperty(name='Automatic Initial Spawning', default=False)

    # Trigger
    trigger_disabled: BoolProperty(name='Trigger Disabled', default=False)
    reset_on_trigger: BoolProperty(name='Reset On Trigger', default=False)

    # Velocity
    use_velocity_scale: BoolProperty(name='Use Velocity Scale', default=False)
    add_velocity_from_owner: BoolProperty(name='Add Velocity From Owner', default=False)

    # Performance
    low_detail_factor: FloatProperty(name='Low Detail Factor')

    # Acceleration
    acceleration: FloatVectorProperty(name='Acceleration', size=3)

    # Color
    use_color_scale: BoolProperty(name='Use Color Scale', default=False)
    color_scale: CollectionProperty(name='Color Scale', type=BDK_PG_particle_color_scale)
    color_scale_repeats: FloatProperty(name='Color Scale Repeats')
    color_multiplier_range: PointerProperty(name='Color Multiplier Range', type=BDK_PG_range_vector)
    opacity: FloatProperty(name='Opacity', min=0.0, max=1.0, subtype='FACTOR')

    # General
    reset_after_change: BoolProperty(name='Reset After Change', default=False)
    coordinate_system: EnumProperty(name='Coordinate System', items=coordinate_system_items)
    max_particles: IntProperty(name='Max Particles')
    effect_axis: EnumProperty(name='Effect Axis', items=effect_axis_items)

    # Local
    auto_reset_time_range: PointerProperty(name='Auto Reset Time Range', type=BDK_PG_range)
    name: StringProperty(name='Name')
    detail_mode: EnumProperty(name='Detail Mode', items=detail_mode_items)

    # Location
    start_location_offset: FloatVectorProperty(name='Start Location Offset', size=3)
    start_location_range: PointerProperty(name='Start Location Range', type=BDK_PG_range_vector)
    add_location_from_other_emitter: IntProperty(name='Add Location From Other Emitter')
    start_location_shape: EnumProperty(name='Start Location Shape', items=start_location_shape_items)
    sphere_radius_range: PointerProperty(name='Sphere Radius Range', type=BDK_PG_range)
    start_location_polar_range: PointerProperty(name='Start Location Polar Range', type=BDK_PG_range_vector)

    # Mass
    start_mass_range: PointerProperty(name='Start Mass Range', type=BDK_PG_range)

    # Mesh Spawning
    mesh_spawning_static_mesh: PointerProperty(name='Mesh Spawning Static Mesh', type=Object)
    mesh_spawning: EnumProperty(name='Mesh Spawning', items=mesh_spawning_items)
    velocity_scale_range: PointerProperty(name='Velocity Scale Range', type=BDK_PG_range_vector)
    mesh_scale_range: PointerProperty(name='Mesh Scale Range', type=BDK_PG_range_vector)
    mesh_normal: FloatVectorProperty(name='Mesh Normal', size=3)
    mesh_normal_threshold_range: PointerProperty(name='Mesh Normal Threshold Range', type=BDK_PG_range)

    # Rendering
    alpha_ref: FloatProperty(name='Alpha Ref')

    # Revolution
    revolution_center_offset_Range: PointerProperty(name='Revolution Center Offset Range', type=BDK_PG_range_vector)
    revolutions_per_second_range: PointerProperty(name='Revolutions Per Second Range', type=BDK_PG_range_vector)
    revolution_scale: CollectionProperty(name='Revolution Scale', type=BDK_PG_particle_revolution_scale)
    revolution_scale_repeats: FloatProperty(name='Revolution Scale Repeats')

    # Rotation
    use_rotation_from: EnumProperty(name='Use Rotation From', items=particle_rotation_source_items)
    rotation_offset: FloatVectorProperty(name='Rotation Offset', size=3, subtype='EULER')
    # spin_ccw_or_cw: FloatVectorProperty(name='Spin CCW Or CW', size=3)
    spin_ccw_or_cw: FloatProperty(name='Spin CCW Or CW', default=0.5, min=0.0, max=1.0, subtype='FACTOR')
    spins_per_second_range: PointerProperty(name='Spins Per Second Range', type=BDK_PG_range_vector)
    start_spin_range: PointerProperty(name='Start Spin Range', type=BDK_PG_range)
    rotation_damping_factor_range: PointerProperty(name='Rotation Damping Factor Range', type=BDK_PG_range_vector)  # TODO: This should be in rotation units
    rotation_normal: FloatVectorProperty(name='Rotation Normal', size=3)

    # Size
    size_scale: CollectionProperty(name='Size Scale', type=BDK_PG_particle_time_scale)
    size_scale_repeats: FloatProperty(name='Size Scale Repeats')
    start_size_range: PointerProperty(name='Start Size Range', type=BDK_PG_range_vector)
    scale_size_by_velocity_multiplier: FloatVectorProperty(name='Scale Size By Velocity Multiplier', size=3)
    scale_size_by_velocity_max: FloatProperty(name='Scale Size By Velocity Max')

    # Skeletal Mesh
    use_skeletal_location_as: EnumProperty(name='Use Skeletal Location As', items=skel_location_update_items)
    skeletal_mesh_actor: PointerProperty(name='Skeletal Mesh Actor', type=Object)
    skeletal_scale: FloatVectorProperty(name='Skeletal Scale', size=3)
    relative_bone_index_range: PointerProperty(name='Relative Bone Index Range', type=BDK_PG_range)

    # Sounds
    sounds: CollectionProperty(name='Sounds', type=BDK_PG_particle_sound)
    spawning_sound: EnumProperty(name='Spawning Sound', items=particle_collision_sound_items)
    spawning_sound_index: PointerProperty(name='Spawning Sound Index', type=BDK_PG_range)
    spawning_sound_probability: PointerProperty(name='Spawning Sound Probability', type=BDK_PG_range)
    collision_sound: EnumProperty(name='Collision Sound', items=particle_collision_sound_items)
    collision_sound_index: PointerProperty(name='Collision Sound Index', type=BDK_PG_range)
    collision_sound_probability: PointerProperty(name='Collision Sound Probability', type=BDK_PG_range)

    # Spawning
    particles_per_second: FloatProperty(name='Particles Per Second', min=0.0)
    initial_particles_per_second: FloatProperty(name='Initial Particles Per Second', min=0.0)

    # Texture
    draw_style: EnumProperty(name='Draw Style', items=particle_draw_style_items)
    texture: PointerProperty(name='Texture', type=Material)
    texture_u_subdivisions: IntProperty(name='Texture U Subdivisions', min=0)
    texture_v_subdivisions: IntProperty(name='Texture V Subdivisions', min=0)
    subdivision_scale: CollectionProperty(name='Subdivision Scale', type=BDK_PG_particle_subdivision_scale)
    subdivision_start: IntProperty(name='Subdivision Start')
    subdivision_end: IntProperty(name='Subdivision End')
    blend_between_subdivisions: BoolProperty(name='Blend Between Subdivisions', default=False)
    use_subdivision_scale: BoolProperty(name='Use Subdivision Scale', default=False)
    use_random_subdivision: BoolProperty(name='Use Random Subdivision', default=False)

    # Tick
    seconds_before_inactive: FloatProperty(name='Seconds Before Tick')
    min_squared_velocity: FloatProperty(name='Min Squared Velocity')

    # Time
    initial_time_range: PointerProperty(name='Initial Time Range', type=BDK_PG_range)
    lifetime_range: PointerProperty(name='Lifetime Range', type=BDK_PG_range)
    initial_delay_range: PointerProperty(name='Initial Delay Range', type=BDK_PG_range)

    # Trigger
    spawn_on_trigger_range: PointerProperty(name='Spawn On Trigger Range', type=BDK_PG_range)
    spawn_on_trigger_pps: PointerProperty(name='Spawn On Trigger PPS', type=BDK_PG_range)

    # Velocity
    start_velocity_range: PointerProperty(name='Start Velocity Range', type=BDK_PG_range_vector)
    start_velocity_radial_range: PointerProperty(name='Start Velocity Radial Range', type=BDK_PG_range)
    max_abs_velocity: FloatVectorProperty(name='Max Velocity (Absolute)', size=3)
    velocity_loss_range: PointerProperty(name='Velocity Loss Range', type=BDK_PG_range_vector)
    rotation_velocity_loss_range: BoolProperty(name='Rotation Velocity Loss Range')
    add_velocity_from_other_emitter: IntProperty(name='Add Velocity From Other Emitter', default=-1)
    add_velocity_multiplier_range: PointerProperty(name='Add Velocity Multiplier Range', type=BDK_PG_range_vector)
    get_velocity_direction_from: EnumProperty(name='Get Velocity Direction From', items=particle_velocity_direction_items)
    velocity_scale: CollectionProperty(name='Velocity Scale', type=BDK_PG_particle_velocity_scale)
    velocity_scale_repeats: FloatProperty(name='Velocity Scale Repeats')

    # Warmup
    warmup_ticks_per_second: FloatProperty(name='Warmup Ticks Per Second', min=0.0)
    warmup_relative_time: FloatProperty(name='Warmup Relative Time', min=0.0, max=1.0)

     # Sprite Emitter
    use_direction_as: EnumProperty(name='Use Direction As', items=particle_direction_usage_items)
    projection_normal: FloatVectorProperty(name='Projection Normal', size=3)

class BDK_PG_particle_system(PropertyGroup):
    emitters: CollectionProperty(name='Emitters', type=BDK_PG_particle_emitter)
    emitters_index: IntProperty(name='Emitter Index', default=-1)


classes = (
    BDK_PG_particle_time_scale,
    BDK_PG_particle_revolution_scale,
    BDK_PG_particle_color_scale,
    BDK_PG_particle_velocity_scale,
    BDK_PG_particle_subdivision_scale,
    BDK_PG_plane,
    BDK_PG_range,
    BDK_PG_range_vector,
    BDK_PG_particle_sound,
    BDK_PG_particle_emitter,
    BDK_PG_particle_system
)
