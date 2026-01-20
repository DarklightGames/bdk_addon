import io
from types import NoneType
from typing import Any, OrderedDict, Iterable

from mathutils import Vector, Euler

from ..units import radians_to_unreal
from ..t3d.data import T3DObject


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

    def _write_list(self, key: str, value_list: list):
        for index, value in enumerate(value_list):
            self._write_line(f'{key}({index})={self._value_to_string(value)}')

    def write(self, object: T3DObject):
        self._write_object(object)

    def _write_object(self, object: T3DObject):
        def format_vector(vector: Iterable[float]) -> str:
            return ','.join(map(lambda element: '%+013.6f' % element, vector))

        # Begin
        first_line = f'Begin {object.type_}'

        type_inline_properties = {
            'Polygon': ('Texture', 'Flags', 'Link')
        }
        universal_inline_properties = ('Class', 'Name')
        inline_properties = list()

        # Gather the inline properties for this object type.
        if object.type_ in type_inline_properties:
            inline_properties.extend(type_inline_properties[object.type_])
        inline_properties.extend(universal_inline_properties)

        # Inline Properties
        for key in inline_properties:
            if key in object.properties:
                first_line += f' {key}={object.properties[key]}'

        self._write_line(first_line)

        self._indent()

        # Polygon
        if object.polygon:
            self._write_line(f'{"Origin":8} {format_vector(object.polygon.origin)}')
            self._write_line(f'{"Normal":8} {format_vector(object.polygon.normal)}')
            self._write_line(f'{"TextureU":8} {format_vector(object.polygon.texture_u)}')
            self._write_line(f'{"TextureV":8} {format_vector(object.polygon.texture_v)}')
            for vertex in object.polygon.vertices:
                self._write_line(f'{"Vertex":8} {format_vector(vertex)}')

        # Children
        for child in object.children:
            self._write_object(child)

        # Properties
        for key, value in filter(lambda item: item[0] not in inline_properties, object.properties.items()):
            if type(value) == list:
                self._write_list(key, value)
            else:
                self._write_key_value(key, value)

        # End
        self._dedent()
        self._write_line(f'End {object.type_}')
