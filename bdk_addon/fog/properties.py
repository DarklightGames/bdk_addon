from bpy.types import PropertyGroup
from bpy.props import BoolProperty, FloatVectorProperty, FloatProperty

from ..units import meters_to_unreal

# TODO: when enabled, we need to build the compositor 

class BDK_PG_fog(PropertyGroup):
    is_enabled: BoolProperty(name='Enable Fog', default=False)
    color: FloatVectorProperty(name='Fog Color', subtype='COLOR', size=3, default=(0.5, 0.5, 0.5), min=0.0, max=1.0)
    distance_start: FloatProperty(name='Fog Start Distance', default=meters_to_unreal(100.0), min=0.0, subtype='DISTANCE', description='Distance at which fog begins to appear')
    distance_end: FloatProperty(name='Fog End Distance', default=meters_to_unreal(1000.0), min=0.0, subtype='DISTANCE', description='Distance at which fog is fully opaque')

classes = (
    BDK_PG_fog,
)
