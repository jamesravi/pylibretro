# Copyright (C) 2022 James Ravindran
# SPDX-License-Identifier: AGPL-3.0-or-later

from ctypes import Structure, cast, POINTER, sizeof
from ctypes import c_uint, c_float, c_double, c_char_p, c_bool, c_void_p, c_size_t
from enum import Enum

RETRO_DEVICE_JOYPAD = 1

class RETRO_ENVIRONMENT(Enum):
    SET_PIXEL_FORMAT = 10
    GET_VARIABLE = 15
    SET_VARIABLES = 16
    SET_SUPPORT_NO_GAME = 18

class RETRO_DEVICE_ID_JOYPAD(Enum):
    B = 0
    Y = 1
    SELECT = 2
    START = 3
    UP = 4
    DOWN = 5
    LEFT = 6
    RIGHT = 7
    A = 8
    X = 9
    L = 10
    R = 11
    L2 = 12
    R2 = 13
    L3 = 14
    R3 = 15

class RETRO_PIXEL_FORMAT(Enum):
    ZERORGB1555 = 0
    XRGB8888 = 1
    RGB565 = 2

class GAME_GEOMETRY(Structure):
    _fields_ = [("base_width", c_uint),
                ("base_height", c_uint),
                ("max_width", c_uint),
                ("max_height", c_uint),
                ("aspect_ratio", c_float)]

class SYSTEM_TIMING(Structure):
    _fields_ = [("fps", c_double),
                ("sample_rate", c_double)]

class SYSTEM_AV_INFO(Structure):
    _fields_ = [("geometry", GAME_GEOMETRY),
                ("timing", SYSTEM_TIMING)]

class SYSTEM_INFO(Structure):
    _fields_ = [("library_name", c_char_p),
                ("library_version", c_char_p),
                ("valid_extensions", c_char_p),
                ("need_fullpath", c_bool),
                ("block_extract", c_bool)]

class GAME_INFO(Structure):
    _fields_ = [("path", c_char_p),
                ("data", c_void_p),
                ("size", c_size_t),
                ("meta", c_char_p)]

class VARIABLE(Structure):
    _fields_ = [("key", c_char_p),
                ("value", c_char_p)]

def struct_to_dict(struct):
    return {key:getattr(struct, key) for key in dict(struct._fields_).keys()}

def increment_pointer(pointer):
    void_p = cast(pointer, c_void_p).value + sizeof(VARIABLE)
    return cast(void_p, POINTER(VARIABLE))

def read_array_of_variables(data):
    variables = {}
    pointer = cast(data, POINTER(VARIABLE))
    while True:
        contents = pointer.contents
        key, value = contents.key, contents.value
        if key is None and value is None:
            break
        else:
            description, choices = list(map(str.strip, value.decode("ascii").split(";")))
            variables[key] = {"description":description, "choices":choices.split("|"), "value":None}
        pointer = increment_pointer(pointer)
    return variables

def zerorgb1555_to_rgb888(data):
    # TODO: Absolutely no idea if this works, will have to find a core to test with
    newdata = []
    for pixel in zip(data[::2],data[1::2]):
        pixel = (pixel[0] << 16) | pixel[1]
        #pixel = int.from_bytes(pixel, "big")
        red_value = ((pixel & 0x7C00) >> 10) << 3
        green_value = ((pixel & 0x3E0) >> 5) << 3
        blue_value = (pixel & 0x1F) << 3
        #print((red_value , green_value , blue_value))
        newdata.append((red_value, green_value, blue_value))
    #print(len(newdata))
    return newdata

def group_argb8888(data):
    allofthem = []
    for pixels in zip(*[iter(data)] * 4):
        allofthem.append(pixels[:-1])
    return allofthem