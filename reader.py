import enum
import typing
from pathlib import Path
from typing import get_type_hints, Any

from .convert_props_txt_to_json import parse_props_txt_file_content
from .data import UMaterial, URotator, get_material_type_from_string, UReference, UColor


def transform_value(property_type: type, value: Any):
    if property_type == int:
        return int(value)
    elif property_type == bool:
        return bool(value)
    elif property_type == float:
        return float(value)
    elif property_type == str:
        return value
    elif property_type.__class__ == enum.EnumMeta:
        return property_type[str(value).split(' ')[0]]
    elif property_type.__class__ == typing._UnionGenericAlias and len(property_type.__args__) == 2 and \
            property_type.__args__[1] == type(None):
        if value is None:
            return None
        return transform_value(property_type.__args__[0], value)
    elif property_type == URotator:
        rotator = URotator()
        rotator.Roll = value['Roll']
        rotator.Pitch = value['Pitch']
        rotator.Yaw = value['Yaw']
        return rotator
    elif property_type == UReference:
        return UReference.from_string(value)
    elif property_type == UColor:
        return UColor(r=value['R'], g=value['G'], b=value['B'], a=value['A'])
    else:
        raise RuntimeError(f'Unhandled type: {property_type}')


# def read_props_txt(path: str) -> Dict[str, str]:
#     import re
#     props = {}
#     lines = list(reversed(Path(path).read_text().splitlines()))
#     print(lines)
#     while len(lines) > 0:
#         line = lines.pop()
#         # array indicator
#         array_match = re.match(r'([\w\d]+)\[(\d)] =', line)
#         if array_match:
#             array = []
#             nextline = lines.pop()
#             print(f'"{nextline}" : "{nextline}"')
#             if nextline != "{":
#                 raise RuntimeError('Expected \"{\", found ' + nextline)
#             while True:
#                 line = lines.pop()
#                 if line == '}':
#                     break
#                 _, value = line.split(' = ', maxsplit=1)
#                 array.append(value)
#         else:
#             key, value = line.split(' = ', maxsplit=1)
#             props[key] = value
#     return props


def read_material(path: str) -> UMaterial:
    # We are assuming that the file structure is laid out as it is by default in umodel exports.
    material_type = get_material_type_from_string(Path(path).parts[-2])
    if not issubclass(material_type, UMaterial):
        raise TypeError(f'{material_type} is not a material type')

    from pprint import pprint

    # Read the .props.txt file into a property dictionary
    with open(path, 'r') as file:
        properties = parse_props_txt_file_content(file.read())

    reference = UReference.from_path(Path(path))

    material = material_type(reference)

    material_type_hints = get_type_hints(type(material))
    for name, value in properties.items():
        try:
            property_type = material_type_hints[name]
            value = transform_value(property_type, value)
            setattr(material, name, value)
        except KeyError:
            continue

    return material
