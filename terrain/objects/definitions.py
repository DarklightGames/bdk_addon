from typing import Dict

from .components import TerrainObjectPaintComponent, CustomPropertyAttribute, TerrainObjectPropertyValueType, \
    TerrainObjectSculptComponent
from ...units import meters_to_unreal


class TerrainObjectDefinition:
    def __init__(self, name: str):
        self.name = name
        self.properties: Dict[str, TerrainObjectPropertyValueType] = {}
        self.components = []


def create_road_terrain_object_definition():
    # We will want each terrain object to have its own properties that can be referenced by the components.
    # For example, the radius of the paint and sculpt components could be driven by a single property.
    terrain_object = TerrainObjectDefinition('Road')
    terrain_object.properties['is_3d'] = True
    terrain_object.properties['radius'] = meters_to_unreal(2.0)
    terrain_object.properties['falloff_radius'] = meters_to_unreal(1.0)
    terrain_object.properties['terrain_layer'] = CustomPropertyAttribute()
    terrain_object.properties['depth'] = meters_to_unreal(1.0)

    paint_component = TerrainObjectPaintComponent()
    paint_component.radius = 'radius'
    paint_component.falloff_radius = 'falloff_radius'
    paint_component.falloff_profile = 'LINEAR'
    terrain_object.components.append(paint_component)

    sculpt_component = TerrainObjectSculptComponent()
    sculpt_component.depth = meters_to_unreal(-0.5)
    terrain_object.components.append(sculpt_component)

    return terrain_object
