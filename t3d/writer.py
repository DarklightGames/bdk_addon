import io
from types import NoneType
from typing import Any, OrderedDict, List

from mathutils import Vector, Euler

from ..units import radians_to_unreal
from ..t3d.data import T3DMap, T3DActor


class T3DWriter:
    def __init__(self, fp: io.TextIOBase):
        self._indent_count = 0
        self._indent_str = ' ' * 4
        self._fp = fp

    def _indent(self):
        self._indent_count += 1
        return self

    def _dedent(self):
        self._indent_count = max(self._indent_count - 1, 0)
        return self

    def _write_line(self, line: str):
        self._fp.write(f'{self._indent_str * self._indent_count}{line}\n')

    def _write_key_value(self, key: str, value: Any):
        self._write_line(f'{key}={self._value_to_string(value)}')

    def _value_to_string(self, value) -> str:
        if type(value) in {float}:
            return f'{value:0.6f}'
        if type(value) in {int, float, bool, str, NoneType}:
            return str(value)
        elif type(value) in {dict, OrderedDict}:
            return '(' + ','.join(map(lambda item: f'{item[0]}={self._value_to_string(item[1])}', value.items())) + ')'
        elif type(value) == Vector:
            return f'(X={value[0]},Y={value[1]},Z={value[2]})'
        elif type(value) == Euler:
            # Convert from radians to unreal rotation units.
            x, y, z = map(lambda v: radians_to_unreal(v), value)
            return f'(Pitch={-y},Roll={x},Yaw={-z})'
        elif type(value) == list:
            raise ValueError('Lists cannot be written inline...probably?')
        else:
            raise ValueError(f'Unhandled data type: {type(value)}')

    def _write_list(self, key: str, value_list: List):
        for index, value in enumerate(value_list):
            self._write_line(f'{key}({index})={self._value_to_string(value)}')

    def write(self, t3d: T3DMap):
        self._write_line('Begin Map')
        for actor in t3d.actors:
            self._write_actor(actor)
        self._write_line('End Map')

    def _write_actor(self, actor: T3DActor):
        self._write_line(f'Begin Actor Class={actor["Class"]} Name={actor["Name"]}')
        self._indent()

        for key, value in filter(lambda item: item[0] not in {'Class', 'Name'}, actor.items()):
            if type(value) == list:
                self._write_list(key, value)
            else:
                self._write_key_value(key, value)

        self._dedent()
        self._write_line('End Actor')
