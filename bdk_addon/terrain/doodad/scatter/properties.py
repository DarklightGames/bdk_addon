import math

from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, PointerProperty, CollectionProperty, \
    FloatProperty, FloatVectorProperty
from bpy.types import PropertyGroup, Object, Context

from ..data import terrain_doodad_geometry_source_items
from ....actor.properties import BDK_PG_actor_properties
from ....helpers import get_terrain_doodad
from ....property_group_helpers import CurveModifierMixin
from ....units import meters_to_unreal
from ...properties import get_terrain_info_paint_layer_by_name
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


def terrain_doodad_scatter_layer_object_object_poll_cb(_self, obj: Object):
    if obj is None:
        return False
    # TODO: in future, we would like to handle collection instances here!
    # if obj.type == 'EMPTY' and obj.instance_collection is not None:
    #     return True
    # Only allow objects that are static meshes.
    return obj.type == 'MESH' and obj.get('Class', None) == 'StaticMeshActor'


def terrain_doodad_scatter_layer_update_cb(self: 'BDK_PG_terrain_doodad_scatter_layer_object', context: Context):
    terrain_doodad = get_terrain_doodad(self.terrain_doodad_object)
    ensure_scatter_layer_modifiers(context, terrain_doodad)


class BDK_PG_terrain_doodad_scatter_layer_object(PropertyGroup, CurveModifierMixin):
    id: StringProperty(name='ID', options={'HIDDEN'})
    name: StringProperty(name='Name', default='Name')
    mute: BoolProperty(name='Mute', default=False)

    terrain_doodad_object: PointerProperty(type=Object, name='Object', options={'HIDDEN'})
    object: PointerProperty(type=Object, name='Object',
                            poll=terrain_doodad_scatter_layer_object_object_poll_cb,
                            update=terrain_doodad_scatter_layer_update_cb)

    random_weight: FloatProperty(name='Random Weight', default=1.0, min=0.0, soft_max=10.0, subtype='FACTOR')

    is_cap: BoolProperty(name='Is Cap', default=False, options=empty_set,
                         description='The object may only be placed at the end of the curve')

    is_aligned_to_curve: BoolProperty(name='Aligned to Curve', default=False)
    align_axis: EnumProperty(name='Align Axis', items=axis_signed_enum_items, default='Z')

    rotation_offset: FloatVectorProperty(name='Rotation Offset', subtype='EULER', default=(0.0, 0.0, 0.0))
    rotation_offset_saturation: FloatProperty(name='Rotation Offset Saturation', default=1.0, min=0.0, max=1.0,
                                              subtype='FACTOR')
    rotation_offset_saturation_seed: IntProperty(name='Rotation Offset Saturation Seed', default=0, min=0)

    random_rotation_max: FloatVectorProperty(name='Random Rotation', subtype='EULER', min=0.0, max=math.pi,
                                             default=(0.0, 0.0, 0.0))
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
    align_to_terrain_factor: FloatProperty(name='Align to Terrain', min=0.0, max=1.0, default=1.0,
                                           description='Align the Z axis to the terrain normal', subtype='FACTOR')
    terrain_normal_offset_min: FloatProperty(name='Terrain Normal Offset Min', default=0.0, subtype='DISTANCE')
    terrain_normal_offset_max: FloatProperty(name='Terrain Normal Offset Max', default=0.0, subtype='DISTANCE')
    terrain_normal_offset_seed: IntProperty(name='Terrain Normal Offset Seed', default=0, min=0)

    # Origin Offset
    origin_offset: FloatVectorProperty(name='Origin Offset', subtype='TRANSLATION', default=(0.0, 0.0, 0.0))

    # Actor Properties
    actor_properties: PointerProperty(type=BDK_PG_actor_properties, name='Actor Properties', options={'HIDDEN'})


def terrain_doodad_paint_layer_name_search_cb(self: 'BDK_PG_terrain_doodad_scatter_layer', context: Context,
                                              edit_text: str):
    paint_layers = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info.paint_layers
    return [paint_layer.name for paint_layer in paint_layers]


def terrain_doodad_scatter_layer_mask_attribute_name_update_cb(self: 'BDK_PG_terrain_doodad_scatter_layer',
                                                               context: Context):
    if self.mask_type != 'ATTRIBUTE':
        return
    # TODO: update this when we have named attribute layers
    self.mask_attribute_id = self.mask_attribute_name

    terrain_doodad = self.terrain_doodad_object.bdk.terrain_doodad
    ensure_scatter_layer_modifiers(context, terrain_doodad)


def terrain_doodad_mask_paint_layer_name_update_cb(self: 'BDK_PG_terrain_doodad_scatter_layer', context: Context):
    if self.mask_type != 'PAINT_LAYER':
        return

    terrain_info = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info
    paint_layer = get_terrain_info_paint_layer_by_name(terrain_info, self.mask_paint_layer_name)
    self.mask_attribute_id = paint_layer.id if paint_layer else ''

    terrain_doodad = self.terrain_doodad_object.bdk.terrain_doodad
    ensure_scatter_layer_modifiers(context, terrain_doodad)


def terrain_doodad_scatter_layer_mask_type_update_cb(self: 'BDK_PG_terrain_doodad_scatter_layer', context: Context):
    terrain_info = self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info
    match self.mask_type:
        case 'PAINT_LAYER':
            paint_layer = get_terrain_info_paint_layer_by_name(terrain_info, self.mask_paint_layer_name)
            self.mask_attribute_id = paint_layer.id if paint_layer else ''
        case 'ATTRIBUTE':
            self.mask_attribute_id = self.mask_attribute_name
        case _:
            raise ValueError(f'Invalid mask type: {self.mask_type}')

    terrain_doodad = self.terrain_doodad_object.bdk.terrain_doodad
    ensure_scatter_layer_modifiers(context, terrain_doodad)


def terrain_doodad_scatter_layer_geometry_source_name_search_cb(self: 'BDK_PG_terrain_doodad_scatter_layer',
                                                                context: Context, edit_text: str):
    return [scatter_layer.name for scatter_layer in
            filter(lambda x: x != self, self.terrain_doodad_object.bdk.terrain_doodad.scatter_layers)]


def terrain_doodad_scatter_layer_geometry_source_name_update_cb(self: 'BDK_PG_terrain_doodad_scatter_layer',
                                                                context: Context):
    scatter_layer = next(
        (scatter_layer for scatter_layer in self.terrain_doodad_object.bdk.terrain_doodad.scatter_layers if
         scatter_layer.name == self.geometry_source_name), None)
    self.geometry_source_id = scatter_layer.id if scatter_layer else ''
    ensure_scatter_layer_modifiers(context, self.terrain_doodad_object.bdk.terrain_doodad)


class BDK_PG_terrain_doodad_scatter_layer(PropertyGroup, CurveModifierMixin):
    id: StringProperty(name='ID', options={'HIDDEN'})
    index: IntProperty(options={'HIDDEN'})
    name: StringProperty(name='Name', default='Scatter Layer')
    mute: BoolProperty(name='Mute', default=False)
    terrain_doodad_object: PointerProperty(type=Object, name='Terrain Doodad Object', options={'HIDDEN'})
    geometry_source: EnumProperty(name='Geometry Source', items=terrain_doodad_geometry_source_items,
                                  default='DOODAD', update=terrain_doodad_scatter_layer_update_cb)
    geometry_source_name: StringProperty(name='Geometry Source Name', default='', options={'HIDDEN'},
                                         search=terrain_doodad_scatter_layer_geometry_source_name_search_cb,
                                         update=terrain_doodad_scatter_layer_geometry_source_name_update_cb)
    geometry_source_id: StringProperty(name='Geometry Source ID', default='', options={'HIDDEN'},
                                       update=terrain_doodad_scatter_layer_update_cb)
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
    seed_bake_id: IntProperty(name='Bake ID', default=0, min=0, options={'HIDDEN'})
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
    curve_spacing_relative_factor: FloatProperty(name='Spacing Relative Factor', default=1.0, min=0.1, soft_max=10.0,
                                                 subtype='FACTOR')
    curve_spacing_absolute: FloatProperty(name='Spacing', default=meters_to_unreal(1.0), min=1, subtype='DISTANCE')
    curve_spacing_relative_axis: EnumProperty(name='Spacing Relative Axis', items=axis_enum_items, default='X')

    curve_normal_offset_max: FloatProperty(name='Normal Offset Max', default=0.0, subtype='DISTANCE')
    curve_normal_offset_seed: IntProperty(name='Normal Offset Seed', default=0, min=0)

    curve_tangent_offset_max: FloatProperty(name='Tangent Offset Max', default=0.0, subtype='DISTANCE')
    curve_tangent_offset_seed: IntProperty(name='Tangent Offset Seed', default=0, min=0)

    fence_mode: BoolProperty(name='Fence Mode', default=False, options=empty_set,
                             description='Adjacent objects will always be the same distance apart and will face '
                                         'towards the next object.\n\nUse this when creating fences or walls')

    # Mesh Settings
    mesh_element_mode: EnumProperty(name='Element Mode', items=(
        ('FACE', 'Face', '', 'FACESEL', 0),
        ('VERT', 'Vertex', '', 'VERTEXSEL', 1),
    ), default='FACE')
    mesh_face_distribute_method: EnumProperty(name='Distribution Method', items=(
        ('RANDOM', 'Random', 'Points will be distributed randomly'),
        ('POISSON_DISK', 'Poisson Disk', 'Poisson-disc sampling produces points that are tightly-packed, but no closer '
                                         'to each other than a specified minimum distance, resulting in a more '
                                         'natural pattern'),
    ), default='POISSON_DISK')
    mesh_face_distribute_random_density: FloatProperty(name='Density', default=0.001, min=0.0, soft_max=0.1)
    mesh_face_distribute_poisson_distance_min: FloatProperty(name='Distance Min', default=meters_to_unreal(2.0),
                                                             min=0.0, subtype='DISTANCE')
    # TODO:  We could make this a more sensible unit. IIRC, the current unit is the number of points per square meter.
    #  This causes issues when the object is scaled, causing the program to freeze even with small increases to this
    #  number.
    mesh_face_distribute_poisson_density_max: FloatProperty(name='Density', default=0.0001, min=0.0, max=0.001,
                                                            options={'HIDDEN'})
    mesh_face_distribute_poisson_density_factor: FloatProperty(name='Density Factor', default=1.0, min=0.0, max=1.0,
                                                               subtype='FACTOR')
    mesh_face_distribute_seed: IntProperty(name='Distribution Seed', default=0, min=0)

    # Snap to Vertex
    snap_to_vertex_factor: FloatProperty(name='Snap to Vertex Factor', default=0.0, min=0.0, max=1.0, subtype='FACTOR',
                                         options=empty_set,
                                         description='Bias the objects towards the nearest vertex on the terrain '
                                                     'along the X and Y axes.\n\nThis is useful when you want each '
                                                     'object to make full sculpt or paint contributions to nearest '
                                                     'vertex')

    # Position Deviation
    use_position_deviation: BoolProperty(name='Use Position Deviation', default=False, options=empty_set,
                                         description='Randomly offset the position of the scatter object in a circle '
                                                     'around the scatter point')
    position_deviation_min: FloatProperty(name='Position Deviation Min', subtype='DISTANCE')
    position_deviation_max: FloatProperty(name='Position Deviation Max', subtype='DISTANCE')
    position_deviation_seed: IntProperty(name='Position Offset Seed', default=0, min=0)

    # Mask Settings
    use_mask: BoolProperty(name='Use Mask', default=False, options=empty_set,
                           description='Use a layer or attribute mask to control where the scatter objects will be '
                                       'placed')
    mask_type: EnumProperty(name='Mask Type', items=(
        ('ATTRIBUTE', 'Attribute', ''),
        ('PAINT_LAYER', 'Paint Layer', ''),
    ), default='ATTRIBUTE', update=terrain_doodad_scatter_layer_mask_type_update_cb)
    mask_attribute_name: StringProperty(name='Mask Attribute Name', default='', options={'HIDDEN'},
                                        update=terrain_doodad_scatter_layer_mask_attribute_name_update_cb)
    mask_paint_layer_name: StringProperty(name='Mask Paint Layer Name', default='', options={'HIDDEN'},
                                          search=terrain_doodad_paint_layer_name_search_cb,
                                          update=terrain_doodad_mask_paint_layer_name_update_cb)
    mask_attribute_id: StringProperty(name='Mask Attribute ID', default='', options={'HIDDEN'})
    mask_threshold: FloatProperty(name='Mask Threshold', default=0.5, min=0.0, max=1.0, subtype='FACTOR',
                                  description='The value at which the mask will be applied')
    mask_invert: BoolProperty(name='Invert', default=False, options=empty_set, description='Invert the mask')

    # Actor Settings
    actor_group: StringProperty(name='Group', default='', options={'HIDDEN'}, description='')

classes = (
    BDK_PG_terrain_doodad_scatter_layer_object,
    BDK_PG_terrain_doodad_scatter_layer,
)
