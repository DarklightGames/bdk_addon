from collections import OrderedDict
from typing import List, Optional, OrderedDict as OrderedDictType, Any


class T3DObject:
    def __init__(self, type_name: str):
        self.type_name = type_name
        self.properties: OrderedDictType[str, Any] = OrderedDict()
        self.children: List['T3DObject'] = []
        self.polygon: Optional[Polygon] = None  # Slightly janky, but will work for now (blame the crappy T3D format)


class Polygon:
    def __init__(self, link: int,
                 origin: (float, float, float),
                 normal: (float, float, float),
                 texture_u: (float, float, float),
                 texture_v: (float, float, float),
                 vertices: ((float, float, float), (float, float, float), (float, float, float))):
        self.link = link
        self.origin = origin
        self.normal = normal
        self.texture_u = texture_u
        self.texture_v = texture_v
        self.vertices = vertices
