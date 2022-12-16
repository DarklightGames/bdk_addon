import enum
import os.path
import typing
from pathlib import Path
from typing import get_type_hints, Any, Dict, Optional

from .data import UMaterial, URotator, get_material_type_from_string, UReference


def transform_value(property_type: type, value: Any):
    if property_type == int:
        return int(value)
    elif property_type == bool:
        return value.lower() == 'true'
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
        return URotator.from_string(value)
    elif property_type == UReference:
        return UReference.from_string(value)
    else:
        raise RuntimeError(f'Unhandled type: {property_type}')


def read_props_txt(path: str) -> Dict[str, str]:
    lines = Path(path).read_text().splitlines()
    props = {}
    for line in lines:
        key, value = line.split(' = ', maxsplit=1)
        props[key] = value
    return props


def read_material(path: str) -> UMaterial:
    # We are assuming that the file structure is laid out as it is by default in umodel exports.
    material_type = get_material_type_from_string(Path(path).parts[-2])
    if not issubclass(material_type, UMaterial):
        raise TypeError(f'{material_type} is not a material type')

    # Read the .props.txt file into a property dictionary
    properties = read_props_txt(path)

    reference = UReference.from_path(Path(path))

    print('-----')
    print(path)
    print(reference)

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
