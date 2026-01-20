from collections import OrderedDict
from typing import OrderedDict as OrderedDictType, Any


class T3DObject:
    def __init__(self, type_name: str):
        self.type_ = type_name
        self.properties: OrderedDictType[str, Any] = OrderedDict()
        self.children: list['T3DObject'] = []
        self.polygon: Polygon | None = None  # Slightly janky, but will work for now (blame the crappy T3D format)

    def __getitem__(self, key: str):
        return self.properties[key]
    
    def __setitem__(self, key: str, value: Any):
        self.properties[key] = value
    
    def __delitem__(self, key: str):
        del self.properties[key]


class Polygon:
    def __init__(self, link: int,
                 origin: tuple[float, float, float],
                 normal: tuple[float, float, float],
                 texture_u: tuple[float, float, float],
                 texture_v: tuple[float, float, float],
                 vertices: list[tuple[float, float, float]]
                 ):
        self.link = link
        self.origin = origin
        self.normal = normal
        self.texture_u = texture_u
        self.texture_v = texture_v
        self.vertices = vertices
