from collections import OrderedDict
from typing import List, Optional, OrderedDict as OrderedDictType, Any, Tuple


class T3DObject:
    def __init__(self, type_name: str):
        self.type_ = type_name
        self.properties: OrderedDictType[str, Any] = OrderedDict()
        self.children: List['T3DObject'] = []
        self.polygon: Optional[Polygon] = None  # Slightly janky, but will work for now (blame the crappy T3D format)

    def __getitem__(self, key: str):
        return self.properties[key]
    
    def __setitem__(self, key: str, value: Any):
        self.properties[key] = value
    
    def __delitem__(self, key: str):
        del self.properties[key]


class Polygon:
    def __init__(self, link: int,
                 origin: Tuple[float, float, float],
                 normal: Tuple[float, float, float],
                 texture_u: Tuple[float, float, float],
                 texture_v: Tuple[float, float, float],
                 vertices: List[Tuple[float, float, float]]
                 ):
        self.link = link
        self.origin = origin
        self.normal = normal
        self.texture_u = texture_u
        self.texture_v = texture_v
        self.vertices = vertices
