import math

from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, PointerProperty, CollectionProperty, \
    FloatProperty, FloatVectorProperty
from bpy.types import PropertyGroup, Object, Context

from ....actor.properties import BDK_PG_actor_properties
from ....helpers import get_terrain_doodad
from ....property_group_helpers import add_curve_modifier_properties
from ....units import meters_to_unreal
from ...properties import BDK_PG_terrain_layer_node
from .builder import ensure_scatter_layer_modifiers


axis_enum_items = [
    ('X', 'X', '', 0),
    ('Y', 'Y', '', 1),
    ('Z', 'Z', '', 2),
]

axis_signed_enum_items = [
    ('X', 'X', '', 0),
    ('Y', 'Y', '', 1),
    ('Z', 'Z', '', 2),
    ('-X', '-X', ''),
    ('-Y', '-Y', ''),
    ('-Z', '-Z', ''),
]

empty_set = set()


def terrain_doodad_scatter_layer_object_object_poll_cb(_self, bpy_object: Object):
    # Only allow objects that are static meshes.
    return bpy_object.type == 'MESH' and bpy_object.get('Class', None) == 'StaticMeshActor'


def terrain_doodad_scatter_layer_update_cb(self: 'BDK_PG_terrain_doodad_scatter_layer_object', context: Context):
    terrain_doodad = get_terrain_doodad(self.terrain_doodad_object)
    ensure_scatter_layer_modifiers(context, terrain_doodad)


class BDK_PG_terrain_doodad_scatter_layer_sculpt_layer(PropertyGroup):
    pass


class BDK_PG_terrain_doodad_scatter_layer_paint_layer(PropertyGroup):
    pass


class BDK_PG_terrain_doodad_scatter_layer_object(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Name')
    mute: BoolProperty(name='Mute', default=False)

    terrain_doodad_object: PointerProperty(type=Object, name='Object', options={'HIDDEN'})
    object: PointerProperty(type=Object, name='Object',
                            poll=terrain_doodad_scatter_layer_object_object_poll_cb,
                            update=terrain_doodad_scatter_layer_update_cb)

    random_weight: FloatProperty(name='Random Weight', default=1.0, min=0.0, soft_max=10.0, subtype='FACTOR')

    is_aligned_to_curve: BoolProperty(name='Aligned to Curve', default=False)
    align_axis: EnumProperty(name='Align Axis', items=axis_signed_enum_items, default='Z')

    rotation_offset: FloatVectorProperty(name='Rotation Offset', subtype='EULER', default=(0.0, 0.0, 0.0))

    random_rotation_max: FloatVectorProperty(name='Random Rotation', subtype='EULER', min=0.0, max=math.pi, default=(0.0, 0.0, 0.0))
    random_rotation_max_seed: IntProperty(name='Random Rotation Seed', default=0, min=0)

    scale_mode: EnumProperty(name='Scale Mode', items=(
        ('UNIFORM', 'Uniform', 'All axes will be scaled by the same amount', '', 0),
        ('NON_UNIFORM', 'Non-Uniform', 'Each axis will be scaled independently', '', 1),
    ), default='UNIFORM')
    scale_uniform: FloatProperty(name='Scale', default=1.0, min=0.0)
    scale: FloatVectorProperty(name='Scale', min=0.0, default=(1.0, 1.0, 1.0))
    scale_random_uniform_min: FloatProperty(name='Scale Min', default=1.0, min=0.0)
    scale_random_uniform_max: FloatProperty(name='Scale Max', default=1.0, min=0.0)
    scale_random_min: FloatVectorProperty(name='Scale Min', min=0.0, default=(1.0, 1.0, 1.0))
    scale_random_max: FloatVectorProperty(name='Scale Max', min=0.0, default=(1.0, 1.0, 1.0))
    scale_random_distribution: EnumProperty(name='Scale Random Distribution', items=(
        ('UNIFORM', 'Uniform', 'Uniform distribution', '', 0),
        ('GAUSSIAN', 'Gaussian', 'Gaussian distribution', '', 1),
    ), default='UNIFORM')
    scale_seed: IntProperty(name='Random Scale Seed', default=0, min=0)

    # Snap & Align to Terrain
    snap_to_terrain: BoolProperty(name='Snap to Terrain', default=True)
    align_to_terrain_factor: FloatProperty(name='Align to Terrain', min=0.0, max=1.0, default=1.0, description='Align the Z axis to the terrain normal', subtype='FACTOR')
    terrain_normal_offset_min: FloatProperty(name='Terrain Normal Offset Min', default=0.0, subtype='DISTANCE')
    terrain_normal_offset_max: FloatProperty(name='Terrain Normal Offset Max', default=0.0, subtype='DISTANCE')
    terrain_normal_offset_seed: IntProperty(name='Terrain Normal Offset Seed', default=0, min=0)

    # Actor Properties
    actor_properties: PointerProperty(type=BDK_PG_actor_properties, name='Actor Properties', options={'HIDDEN'})


class BDK_PG_terrain_doodad_scatter_layer(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    name: StringProperty(name='Name', default='Scatter Layer')
    mute: BoolProperty(name='Mute', default=False)
    terrain_doodad_object: PointerProperty(type=Object, name='Terrain Doodad Object', options={'HIDDEN'})
    scatter_type: EnumProperty(name='Scatter Type', items=(
        ('ORDER', 'Order', 'The objects will be scattered in the order that they appear in the object list.'),
        ('RANDOM', 'Random', 'The objects will be scattered randomly based on the probability weight.'),
    ))

    # Objects
    objects: CollectionProperty(name='Scatter Objects', type=BDK_PG_terrain_doodad_scatter_layer_object)
    objects_index: IntProperty()

    # Object Selection
    object_select_mode: EnumProperty(name='Object Select Mode', items=(
        ('RANDOM', 'Random', 'Select a random object from the list', '', 0),
        ('CYCLIC', 'Cyclic', 'Select an object in the order that they appear in the list', '', 1),
        ('WEIGHTED_RANDOM', 'Weighted Random', 'Select an object based on the relative probability weight', '', 2)
    ), default='RANDOM')
    object_select_random_seed: IntProperty(name='Object Select Random Seed', default=0, min=0)
    object_select_cyclic_offset: IntProperty(name='Object Select Cyclic Offset', default=0, min=0)

    planter_object: PointerProperty(type=Object, name='Planter Object', options={'HIDDEN'})
    seed_object: PointerProperty(type=Object, name='Seed Object', options={'HIDDEN'})
    sprout_object: PointerProperty(type=Object, name='Sprout Object', options={'HIDDEN'})

    global_seed: IntProperty(name='Global Seed', default=0, min=0,
                             description='Used to randomize the scatter without changing the seed of each option')
    density: FloatProperty(name='Density', default=1.0, min=0.0, max=1.0, subtype='FACTOR',
                           description='The probability that the object will be scattered')
    density_seed: IntProperty(name='Density Seed', default=0, min=0,
                              description='Used to randomize the scatter without changing the seed of each option')

    # Curve Settings
    curve_spacing_method: EnumProperty(name='Spacing Method', items=(
        ('RELATIVE', 'Relative', ''),
        ('ABSOLUTE', 'Absolute', ''),
    ), default='RELATIVE')
    curve_spacing_relative_factor: FloatProperty(name='Spacing Relative Factor', default=1.0, min=0.1, soft_max=10.0, subtype='FACTOR')
    curve_spacing_absolute: FloatProperty(name='Spacing', default=meters_to_unreal(1.0), min=1, subtype='DISTANCE')
    curve_spacing_relative_axis: EnumProperty(name='Spacing Relative Axis', items=axis_enum_items, default='X')

    curve_normal_offset_max: FloatProperty(name='Normal Offset Max', default=0.0, subtype='DISTANCE')
    curve_normal_offset_seed: IntProperty(name='Normal Offset Seed', default=0, min=0)

    curve_tangent_offset_max: FloatProperty(name='Tangent Offset Max', default=0.0, subtype='DISTANCE')
    curve_tangent_offset_seed: IntProperty(name='Tangent Offset Seed', default=0, min=0)

    # Mesh Settings
    mesh_element_mode: EnumProperty(name='Element Mode', items=(
        ('FACE', 'Face', '', 'FACESEL', 0),
        ('VERT', 'Vertex', '', 'VERTEXSEL', 1),
    ), default='FACE')
    mesh_face_distribute_method: EnumProperty(name='Distribution Method', items=(
        ('RANDOM', 'Random', 'Points will be distributed randomly'),
        ('POISSON_DISK', 'Poisson Disk', 'Poisson-disc sampling produces points that are tightly-packed, but no closer '
         'to each other than a specified minimum distance, resulting in a more natural pattern'),
    ), default='POISSON_DISK')
    mesh_face_distribute_random_density: FloatProperty(name='Density', default=0.001, min=0.0, soft_max=0.1)
    mesh_face_distribute_poisson_distance_min: FloatProperty(name='Distance Min', default=meters_to_unreal(2.0),
                                                             min=0.0, subtype='DISTANCE')
    # TODO:  We could make this a more sensible unit. IIRC, the current unit is the number of points per square meter.
    #  This causes issues when the object is scaled, causing the program to freeze even with small increases to this
    #  number.
    mesh_face_distribute_poisson_density_max: FloatProperty(name='Density', default=0.001, min=0.0)
    mesh_face_distribute_poisson_density_factor: FloatProperty(name='Density Factor', default=1.0, min=0.0, max=1.0,
                                                               subtype='FACTOR')
    mesh_face_distribute_seed: IntProperty(name='Distribution Seed', default=0, min=0)

    # Snap to Vertex
    snap_to_vertex_factor: FloatProperty(name='Snap to Vertex Factor', default=0.0, min=0.0, max=1.0, subtype='FACTOR',
                                         options=empty_set,
                                         description='Bias the objects towards the nearest vertex on the terrain along the X and Y axes.\n\nThis is useful when you want each object to make full sculpt or paint contributions to nearest vertex')

    # Mask Settings
    use_mask_nodes: BoolProperty(name='Use Mask Nodes', default=False, options=empty_set)
    mask_nodes: CollectionProperty(name='Mask Nodes', type=BDK_PG_terrain_layer_node, options=empty_set)
    mask_nodes_index: IntProperty(options={'HIDDEN'})
    mask_attribute_id: StringProperty(name='Mask Attribute ID', default='', options={'HIDDEN'})

    # Paint Layers
    paint_layers: CollectionProperty(name='Paint Layers', type=BDK_PG_terrain_doodad_scatter_layer_paint_layer,
                                     options={'HIDDEN'})
    paint_layers_index: IntProperty(options={'HIDDEN'})

    # Sculpt Layers
    sculpt_layers: CollectionProperty(name='Sculpt Layers', type=BDK_PG_terrain_doodad_scatter_layer_sculpt_layer,
                                      options={'HIDDEN'})
    sculpt_layers_index: IntProperty(options={'HIDDEN'})


add_curve_modifier_properties(BDK_PG_terrain_doodad_scatter_layer)


classes = (
    BDK_PG_terrain_doodad_scatter_layer_paint_layer,
    BDK_PG_terrain_doodad_scatter_layer_sculpt_layer,
    BDK_PG_terrain_doodad_scatter_layer_object,
    BDK_PG_terrain_doodad_scatter_layer,
)
