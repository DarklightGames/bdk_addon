from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty, IntProperty, FloatVectorProperty
from bpy.types import PropertyGroup

from ..units import meters_to_unreal

collision_flags_enum_items = (
    ('BLOCK_ACTORS', 'Block Actors', 'Blocks other non-player actors'),
    ('BLOCK_KARMA', 'Block Karma', 'Block actors being simulated with Karma such as vehicles and rag-dolls'),
    ('BLOCK_NON_ZERO_EXTENT_TRACES', 'Block Non-Zero Extent Traces', 'Block non-zero extent traces such as pawn capsules'),
    ('BLOCK_ZERO_EXTENT_TRACES', 'Block Zero Extent Traces', 'Block zero extent traces such as projectiles'),
    ('COLLIDE_ACTORS', 'Collide Actors', 'Collides with other actors'),
)


class BDK_PG_actor_properties(PropertyGroup):
    class_name: StringProperty(name='Class Name', default='StaticMeshActor')
    should_use_cull_distance: BoolProperty(name='Use Culling', default=True)
    cull_distance: FloatProperty(name='Cull Distance', default=meters_to_unreal(50.0), min=0.0, subtype='DISTANCE', description='The distance beyond which the actor will not be rendered')
    collision_flags: EnumProperty(name='Collision Flags', items=collision_flags_enum_items, options={'ENUM_FLAG'})


classes = (
    BDK_PG_actor_properties,
)
