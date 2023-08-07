from typing import Optional
from pathlib import Path
import re
from .units import unreal_to_radians


class UColor:
    def __init__(self, r: int, g: int, b: int, a: int):
        self.R = r
        self.G = g
        self.B = b
        self.A = a


class UReference:
    def __init__(self, type_name: str, package_name: str, object_name: str, group_name: Optional[str] = None):
        self.type_name = type_name
        self.package_name = package_name
        self.object_name = object_name
        self.group_name = group_name

    @staticmethod
    def from_string(string: str) -> Optional['UReference']:
        if string == 'None':
            return None
        pattern = r'(\w+)\'([\w\.\d\-\_]+)\''
        match = re.match(pattern, string)
        type_name = match.group(1)
        object_name = match.group(2)
        pattern = r'([\w\d\-\_]+)'
        values = re.findall(pattern, object_name)
        package_name = values[0]
        object_name = values[-1]
        return UReference(type_name, package_name, object_name, group_name=None)

    @staticmethod
    def from_path(path: Path):
        parts = path.parts[-3:]
        package_name = parts[0]
        type_name = parts[1]
        object_name = parts[2][0:parts[2].index('.')]
        return UReference(type_name, package_name, object_name)

    def __str__(self):
        string = f"{self.type_name}'{self.package_name}"
        if self.group_name is not None:
            string += f'.{self.group_name}'
        string += f".{self.object_name}'"
        return string


class URotator:
    def __init__(self, pitch: int = 0, yaw: int = 0, roll: int = 0):
        self.Pitch = pitch
        self.Yaw = yaw
        self.Roll = roll

    def get_radians(self) -> (float, float, float):
        return (
            unreal_to_radians(self.Roll),
            unreal_to_radians(self.Pitch),
            unreal_to_radians(self.Yaw)
        )

    def __repr__(self):
        return f'{{ Yaw={self.Yaw}, Pitch={self.Pitch}, Roll={self.Roll} }}'


map_range_interpolation_type_items = [
    ('LINEAR', 'Linear', 'Linear interpolation between From Min and From Max values.', 'LINCURVE', 0),
    ('STEPPED', 'Stepped', 'Stepped linear interpolation between From Min and From Max values.', 'IPO_CONSTANT', 1),
    ('SMOOTHSTEP', 'Smooth Step', 'Smooth Hermite edge interpolation between From Min and From Max values.', 'IPO_EASE_IN', 2),
    ('SMOOTHERSTEP', 'Smoother Step', 'Smoother Hermite edge interpolation between From Min and From Max values.', 'IPO_EASE_IN_OUT', 3),
]
