# https://beyondunrealwiki.github.io/pages/package-file-format.html
# https://beyondunrealwiki.github.io/pages/package-file-format-data-de.html

from ctypes import Structure, c_uint32, c_uint16, sizeof
import struct
from typing import BinaryIO, List
from enum import Enum


class UnrealPackageHeader(Structure):
    _fields_ = [
        ('signature', c_uint32),
        ('version', c_uint16),
        ('license_mode', c_uint16),
        ('package_flags', c_uint32),
        ('name_count', c_uint32),
        ('name_offset', c_uint32),
        ('export_count', c_uint32),
        ('export_offset', c_uint32),
        ('import_count', c_uint32),
        ('import_offset', c_uint32),
    ]


class ObjectReferenceType(Enum):
    """
    An enumeration of object reference types.
    """
    NULL = 0
    IMPORT_TABLE = 1
    EXPORT_TABLE = 2


class ObjectReference:
    def __init__(self, type: ObjectReferenceType = ObjectReferenceType.NULL, index: int = 0):
        self.type = type
        self.index = index

    @staticmethod
    def from_buffer_copy(stream: BinaryIO):
        index = struct.unpack('i', stream.read(4))[0]
        if index < 0:
            index = -index - 1
            object_reference_type = ObjectReferenceType.IMPORT_TABLE
        elif index > 0:
            index = index - 1
            object_reference_type = ObjectReferenceType.EXPORT_TABLE
        else:
            object_reference_type = ObjectReferenceType.NULL

        return ObjectReference(object_reference_type, index)


class UnrealPackageImport:
    def __init__(self, class_package: int = 0, class_name: int = 0, object_name: int = 0, package: ObjectReference = ObjectReference()):
        self.class_package = class_package
        self.class_name = class_name
        self.object_name = object_name
        self.package = package

    @staticmethod
    def from_buffer_copy(stream: BinaryIO):
        return UnrealPackageImport(
            class_package=compact_integer_from_buffer(stream),
            class_name=compact_integer_from_buffer(stream),
            package=ObjectReference.from_buffer_copy(stream),
            object_name=compact_integer_from_buffer(stream),
        )


def compact_integer_from_buffer(stream: BinaryIO) -> int:
    output = 0
    signed = False
    for i in range(5):
        x = struct.unpack('B', stream.read(1))[0]
        if i == 0:
            if x & 0x80 > 0:
                signed = True
            output |= x & 0x3F
            if x & 0x40 == 0:
                break
        elif i == 4:
            output |= (x & 0x1F) << (6 + (3 * 7))
        else:
            output |= (x & 0x7F) << (6 + ((i - 1) * 7))
            if x & 0x80 == 0:
                break

    if signed:
        output *= -1

    return output


def name_from_buffer(package_version: int, stream: BinaryIO) -> str:
    name = bytearray()
    if package_version < 64:
        # Read null-terminated string.
        while True:
            char = stream.read(1)
            if char == b'\x00':
                break
            name.append(char[0])
    else:
        # Read single byte for the length of the string (this is definitely a compact integer!)
        length = compact_integer_from_buffer(stream)
        name = stream.read(length)
        # Assert if the string is not null-terminated.
        assert name[-1] == 0, f'Name is not null-terminated: {name}'
        # Lop off the null-terminator.
        name = name[:-1]

    return name.decode('windows-1252')


def read_package_dependencies(path: str):
    """
    Load an Unreal package file.
    """
    # Load the package file.
    with open(path, 'rb') as stream:
        # Parse the header.
        offset = 0
        header = UnrealPackageHeader.from_buffer_copy(stream.read(sizeof(UnrealPackageHeader)))
        offset += sizeof(UnrealPackageHeader)

        # Read the name table.
        stream.seek(header.name_offset)

        name_table: List[str] = []
        for i in range(header.name_count):
            name = name_from_buffer(header.version, stream)
            _flags = struct.unpack('I', stream.read(4))[0]
            name_table.append(name)

        # Read the import table.
        stream.seek(header.import_offset)

        import_table: List[UnrealPackageImport] = []
        for i in range(header.import_count):
            entry = UnrealPackageImport.from_buffer_copy(stream)
            import_table.append(entry)

        import_packages = set()

        for entry in import_table:
            # Recurse through the package hierarchy.
            if entry.package.type == ObjectReferenceType.IMPORT_TABLE:
                def recurse_import_table(import_table: List[UnrealPackageImport], index: int) -> UnrealPackageImport:
                    entry = import_table[index]
                    if entry.package.type == ObjectReferenceType.IMPORT_TABLE:
                        return recurse_import_table(import_table, entry.package.index)
                    else:
                        return entry

                package = recurse_import_table(import_table, entry.package.index)
                package_name = name_table[package.object_name]

                import_packages.add(package_name)

        return import_packages
