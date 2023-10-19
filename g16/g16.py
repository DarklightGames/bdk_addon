import ctypes
from pathlib import Path

import numpy
from ctypes import c_uint32, c_uint16, c_char, LittleEndianStructure

import numpy as np


class BitmapHeader(LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ('magic', c_char * 2),
        ('size', c_uint32),
        ('reserved', c_uint16 * 2),
        ('data_offset', c_uint32),
    ]


class BitmapCoreHeader(LittleEndianStructure):
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


def write_bmp_g16(path: str, pixels: numpy.ndarray):
    with open(path, 'wb') as fp:
        header = BitmapHeader()
        header.magic = b'BM'
        header.size = ctypes.sizeof(BitmapHeader) + ctypes.sizeof(BitmapCoreHeader) + 2 * pixels.size
        header.reserved = (0, 0)
        header.data_offset = ctypes.sizeof(BitmapHeader) + ctypes.sizeof(BitmapCoreHeader)

        core_header = BitmapCoreHeader()
        core_header.size = ctypes.sizeof(BitmapCoreHeader)
        core_header.width = pixels.shape[0]
        core_header.height = pixels.shape[1]
        core_header.planes = 1
        core_header.bpp = 16
        core_header.compression_method = 0
        core_header.data_size = 2 * pixels.size
        core_header.resolution = (0, 0)
        core_header.palette_color_count = 0
        core_header.important_color_count = 0

        fp.write(bytes(header))
        fp.write(bytes(core_header))
        fp.write(pixels.tobytes())


def read_bmp_g16(path: str) -> np.ndarray:
    """
    Reads a 16-bit grayscale bitmap.
    :param path: The path to the bitmap file.
    :return: The bitmap as a numpy array.
    """
    buffer = Path(path).read_bytes()
    offset = 0

    # Header
    header = BitmapHeader.from_buffer_copy(buffer, offset)
    if header.magic != b'BM':
        raise IOError('Invalid file format')
    offset += ctypes.sizeof(BitmapHeader)

    # Core Header
    core_header = BitmapCoreHeader.from_buffer_copy(buffer, offset)
    offset += ctypes.sizeof(BitmapCoreHeader)
    if core_header.size != ctypes.sizeof(BitmapCoreHeader):
        raise IOError('Invalid file format')

    # Bits-per-pixel
    expected_bpp = 16
    if core_header.bpp != expected_bpp:
        raise IOError(f'Incorrect bits-per-pixels (found {core_header.bpp}, expected {expected_bpp})')

    # Data Size
    expected_data_size = (core_header.bpp / 8) * core_header.width * core_header.height
    if core_header.data_size != expected_data_size:
        raise IOError(f'Incorrect data size (found {core_header.data_size}, expected {expected_data_size})')

    buffer = buffer[header.data_offset:header.data_offset+core_header.data_size]
    return np.frombuffer(buffer, dtype=np.uint16).reshape((core_header.width, core_header.height))


if __name__ == '__main__':
    g16 = read_bmp_g16(r'C:\Users\Owner\Desktop\terrain\TerrainInfo.bmp')
    print(g16)
