from bpy.types import PropertyGroup, Material, Object
from bpy.props import EnumProperty, IntProperty, FloatProperty, PointerProperty, StringProperty

from .builder import ensure_fluid_surface_node_tree
from ..units import meters_to_unreal

fluid_grid_type_items = (
    ('FGT_Square', 'Square', '', '', 0),
    ('FGT_Hexagonal', 'Hexagonal', '', '', 1),
)

def fluid_surface_material_poll(self, obj):
    # Only display materials that have package references.
    return obj.bdk.package_reference != ''

def fluid_surface_material_update_cb(self, context):
    # Rebuild the node tree when the material changes.
    ensure_fluid_surface_node_tree(self)

class BDK_PG_fluid_surface(PropertyGroup):
    id: StringProperty(name='ID', options={'HIDDEN'})
    object: PointerProperty(name='Object', type=Object, options={'HIDDEN'})
    fluid_grid_type: EnumProperty(name='Grid Type', items=fluid_grid_type_items, default='FGT_Hexagonal')
    fluid_x_size: IntProperty(name='X Size', default=48, min=0) # Set this to 1 after we fix the crashing
    fluid_y_size: IntProperty(name='Y Size', default=48, min=0)
    fluid_grid_spacing: FloatProperty(name='Grid Spacing', default=24.0, min=0.0, subtype='DISTANCE')
    u_offset: FloatProperty(name='U Offset', default=0.0, min=0.0, max=1.0)
    v_offset: FloatProperty(name='V Offset', default=0.0, min=0.0, max=1.0)
    u_tiles: FloatProperty(name='U Tiles', default=1.0, min=0.0)
    v_tiles: FloatProperty(name='V Tiles', default=1.0, min=0.0)
    material: PointerProperty(name='Material', type=Material, update=fluid_surface_material_update_cb, poll=fluid_surface_material_poll)


classes = (
    BDK_PG_fluid_surface,
)
