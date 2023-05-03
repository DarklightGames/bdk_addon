from typing import Union, Optional


class TerrainObjectAttribute:
    pass


class TerrainObjectComponent:
    is_3d: Union[bool, str] = False


class TerrainObjectPaintComponent(TerrainObjectComponent):
    operation: str = 'ADD'
    radius: Union[float, str] = 0.0
    falloff_radius: Union[float, str] = 0.0
    falloff_profile: str = 'LINEAR'


class TerrainObjectSculptComponent(TerrainObjectComponent):
    depth: Union[float, str] = 0.0
    pass


class CustomPropertyAttribute(TerrainObjectAttribute):
    def __init__(self, name: Optional[str] = None):
        self.name = name


class TerrainLayerAttribute(TerrainObjectAttribute):
    def __init__(self, layer_id: str):
        self.layer_id = layer_id


class TerrainDecoLayerAttribute(TerrainObjectAttribute):
    def __init__(self, deco_layer_id: str):
        self.deco_layer_id = deco_layer_id


TerrainObjectPropertyValueType = Union[float, int, str, TerrainObjectAttribute]
