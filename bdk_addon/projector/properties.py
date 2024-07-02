import math

from bpy.props import PointerProperty, FloatProperty, BoolProperty, EnumProperty, IntProperty
from bpy.types import PropertyGroup, Material

from ..node_helpers import get_socket_identifier_from_name

blending_op_items = (
    ('NONE', 'None', ''),
    ('MODULATE', 'Modulate', ''),
    ('ALPHA_BLEND', 'Alpha Blend', ''),
    ('ADD', 'Add', ''),
)

# TODO: come up with a better way to handle these (also will depend on the engine!)
blending_op_blender_to_unreal_map = {
    'NONE': 'PB_None',
    'MODULATE': 'PB_Modulate',
    'ALPHA_BLEND': 'PB_AlphaBlend',
    'ADD': 'PB_Add'
}

blending_op_unreal_to_blender_map = {
    'PB_None': 'NONE',
    'PB_Modulate': 'MODULATE',
    'PB_AlphaBlend': 'ALPHA_BLEND',
    'PB_Add': 'ADD'
}

def projector_proj_texture_update_cb(self, context):
    projector_object = self.id_data

    modifier = projector_object.modifiers['Projector']
    node_tree = modifier.node_group

    socket_identifier = get_socket_identifier_from_name(node_tree, 'ProjTexture')

    if socket_identifier is None:
        return

    setattr(modifier, 'ProjTexture', self.proj_texture)


class BDK_PG_projector(PropertyGroup):
    bl_idname = 'BDK_PG_projector'

    is_baked: BoolProperty(name='Is Baked', default=False)
    bake_id: IntProperty(name='Bake ID', default=0)
    frame_buffer_blending_op: EnumProperty(name='Frame Buffer Blending Operation', items=blending_op_items, default='ALPHA_BLEND')
    material_blending_op: EnumProperty(name='Material Blending Operation', items=blending_op_items, default='NONE')
    fov: FloatProperty(name='FOV', default=math.pi / 4, min=0.0, max=math.pi / 2, subtype='ANGLE')
    max_trace_distance: FloatProperty(name='Max Trace Distance', default=1024.0, min=0.0, soft_min=1.0, soft_max=4096.0, subtype='DISTANCE')
    proj_texture: PointerProperty(name='Material', type=Material, update=projector_proj_texture_update_cb)
    gradient: BoolProperty(name='Gradient', default=False)
    draw_scale: FloatProperty(name='Draw Scale', default=1.0, min=0.0)


classes = (
    BDK_PG_projector,
)
