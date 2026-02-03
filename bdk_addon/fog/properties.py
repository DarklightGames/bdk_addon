from bpy.types import PropertyGroup, Context
from bpy.props import BoolProperty, FloatVectorProperty, FloatProperty
from .builder import ensure_bdk_scene_compositor_node_tree
from ..units import meters_to_unreal

def fog_is_enabled_update(self, context: Context):
    if context.scene is None:
        return
    
    if self.is_enabled:
        for view_layer in context.scene.view_layers:
            # Make sure we can get the depth value from the view layer.
            view_layer.use_pass_z = True
        node_tree = ensure_bdk_scene_compositor_node_tree()
        context.scene.compositing_node_group = node_tree
    else:
        context.scene.compositing_node_group = None


class BDK_PG_fog(PropertyGroup):
    is_enabled: BoolProperty(name='Enable Fog', default=False, update=fog_is_enabled_update)
    color: FloatVectorProperty(name='Fog Color', subtype='COLOR', size=3, default=(0.5, 0.5, 0.5), min=0.0, max=1.0)
    distance_start: FloatProperty(name='Fog Start Distance', default=meters_to_unreal(100.0), min=0.0, subtype='DISTANCE', description='Distance at which fog begins to appear')
    distance_end: FloatProperty(name='Fog End Distance', default=meters_to_unreal(1000.0), min=0.0, subtype='DISTANCE', description='Distance at which fog is fully opaque')


classes = (
    BDK_PG_fog,
)
