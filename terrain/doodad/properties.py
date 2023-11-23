from bpy.props import IntProperty, PointerProperty, CollectionProperty, FloatProperty, BoolProperty, StringProperty
from bpy.types import PropertyGroup, Object, NodeTree, Context

from ...constants import RADIUS_EPSILON
from ...helpers import get_terrain_info
from .builder import ensure_terrain_info_modifiers
from .scatter.properties import BDK_PG_terrain_doodad_scatter_layer
from .sculpt.properties import BDK_PG_terrain_doodad_sculpt_layer
from .paint.properties import BDK_PG_terrain_doodad_paint_layer

empty_set = set()


def terrain_doodad_sort_order_update_cb(self: 'BDK_PG_terrain_doodad', context: Context):
    terrain_info: 'BDK_PG_terrain_info' = get_terrain_info(self.terrain_info_object)
    ensure_terrain_info_modifiers(context, terrain_info)


def terrain_doodad_update_cb(self: 'BDK_PG_terrain_doodad_paint_layer', context: Context):
    # We update the node group whe the operation is changed since we don't want to use drivers to control the
    # operation for performance reasons. (TODO: NOT TRUE!)
    ensure_terrain_info_modifiers(context, self.terrain_doodad_object.bdk.terrain_doodad.terrain_info_object.bdk.terrain_info)


class BDK_PG_terrain_doodad(PropertyGroup):
    id: StringProperty(options={'HIDDEN'}, name='ID')
    terrain_info_object: PointerProperty(type=Object, options={'HIDDEN'}, name='Terrain Info Object')
    node_tree: PointerProperty(type=NodeTree, options={'HIDDEN'}, name='Node Tree')
    object: PointerProperty(type=Object, name='Object')
    is_3d: BoolProperty(name='3D', default=False)
    paint_layers: CollectionProperty(name='Paint Layers', type=BDK_PG_terrain_doodad_paint_layer)
    paint_layers_index: IntProperty()
    sculpt_layers: CollectionProperty(name='Sculpt Layers', type=BDK_PG_terrain_doodad_sculpt_layer)
    sculpt_layers_index: IntProperty()

    # TODO: not yet implemented
    radius_factor: FloatProperty(name='Radius Factor', default=1.0, min=RADIUS_EPSILON, soft_max=10, subtype='FACTOR',
                                 description='All radius values will be multiplied by this value. This is useful for '
                                                'scaling the radius of all layers at once.')

    # TODO: we probably need a "creation index" to use a stable tie-breaker for the sort order of the terrain doodad.
    #  we are currently using the ID of the terrain doodad, but this isn't ideal because the sort order is effectively
    #  random for terrain doodad that share the same sort order.
    sort_order: IntProperty(name='Sort Order', default=0, description='The order in which the terrain doodad are '
                                                                      'evaluated (lower values are evaluated first)',
                            update=terrain_doodad_sort_order_update_cb)
    scatter_layers: CollectionProperty(name='Scatter Layers', type=BDK_PG_terrain_doodad_scatter_layer)
    scatter_layers_index: IntProperty()

    is_frozen: BoolProperty(name='Is Frozen', default=False)


classes = (
    BDK_PG_terrain_doodad,
)
