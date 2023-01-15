import ctypes
from ctypes import Structure, c_uint32, c_uint16, c_uint8, c_char, LittleEndianStructure

import numpy


class BITMAPHEADER(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('magic', c_char * 2),
        ('size', c_uint32),
        ('reserved', c_uint16 * 2),
        ('data_offset', c_uint32),
    ]


class BITMAPCOREHEADER(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('size', c_uint32),
        ('width', c_uint32),
        ('height', c_uint32),
        ('planes', c_uint16),
        ('bpp', c_uint16),
        ('compression_method', c_uint32),
        ('data_size', c_uint32),
        ('resolution', c_uint32 * 2),
        ('palette_color_count', c_uint32),
        ('important_color_count', c_uint32),
    ]


def write_bmp_g16(path: str, pixels: numpy.array, shape: (int, int)):
    with open(path, 'wb') as fp:
        header = BITMAPHEADER()
        header.magic = b'BM'
        header.size = ctypes.sizeof(BITMAPHEADER) + ctypes.sizeof(BITMAPCOREHEADER) + 2 * len(pixels)
        header.reserved = (0, 0)
        header.data_offset = ctypes.sizeof(BITMAPHEADER) + ctypes.sizeof(BITMAPCOREHEADER)

        core_header = BITMAPCOREHEADER()
        core_header.size = ctypes.sizeof(BITMAPCOREHEADER)
        core_header.width = shape[0]
        core_header.height = shape[1]
        core_header.planes = 1
        core_header.bpp = 16
        core_header.compression_method = 0  # TODO: might be a special value for this for G16s
        core_header.data_size = 2 * len(pixels)
        core_header.resolution = (0, 0)
        core_header.palette_color_count = 0
        core_header.important_color_count = 0

        fp.write(bytes(header))
        fp.write(bytes(core_header))
        fp.write(pixels.tobytes())
