# Copyright (C) 2022 James Ravindran
# SPDX-License-Identifier: AGPL-3.0-or-later

from ctypes import Structure, cast, POINTER, sizeof
from ctypes import c_uint, c_float, c_double, c_char_p, c_bool, c_void_p, c_size_t
from enum import Enum

RETRO_DEVICE_JOYPAD = 1

EXPERIMENTAL = 0x10000
PRIVATE = 0x20000

class RETRO_ENVIRONMENT(Enum):
    # TODO: Extend these I think
    SET_ROTATION = 1
    GET_OVERSCAN = 2
    GET_CAN_DUPE = 3
    SET_MESSAGE = 6
    SHUTDOWN = 7
    SET_PERFORMANCE_LEVEL = 8
    GET_SYSTEM_DIRECTORY = 9
    SET_PIXEL_FORMAT = 10
    SET_INPUT_DESCRIPTORS = 11
    SET_KEYBOARD_CALLBACK = 12
    SET_DISK_CONTROL_INTERFACE = 13
    SET_HW_RENDER = 14
    GET_VARIABLE = 15
    SET_VARIABLES = 16
    GET_VARIABLE_UPDATE = 17
    SET_SUPPORT_NO_GAME = 18
    GET_LIBRETRO_PATH = 19
    SET_FRAME_TIME_CALLBACK = 21
    SET_AUDIO_CALLBACK = 22
    GET_RUMBLE_INTERFACE = 23
    GET_INPUT_DEVICE_CAPABILITIES = 24

    GET_SENSOR_INTERFACE = 25 | EXPERIMENTAL
    GET_CAMERA_INTERFACE = 26 | EXPERIMENTAL

    GET_LOG_INTERFACE = 27
    GET_PERF_INTERFACE = 28
    GET_LOCATION_INTERFACE = 29
    GET_CONTENT_DIRECTORY = 30
    GET_CORE_ASSETS_DIRECTORY = 30
    GET_SAVE_DIRECTORY = 31
    SET_SYSTEM_AV_INFO = 32
    SET_PROC_ADDRESS_CALLBACK = 33
    SET_SUBSYSTEM_INFO = 34
    SET_CONTROLLER_INFO = 35

    SET_MEMORY_MAPS = 36 | EXPERIMENTAL

    SET_GEOMETRY = 37
    GET_USERNAME = 38
    GET_LANGUAGE = 39

    GET_CURRENT_SOFTWARE_FRAMEBUFFER = 40 | EXPERIMENTAL
    GET_HW_RENDER_INTERFACE = 41 | EXPERIMENTAL
    SET_SUPPORT_ACHIEVEMENTS = 42 | EXPERIMENTAL
    SET_HW_RENDER_CONTEXT_NEGOTIATION_INTERFACE = 43 | EXPERIMENTAL

    SET_SERIALIZATION_QUIRKS = 44

    SET_HW_SHARED_CONTEXT = 44 | EXPERIMENTAL
    GET_VFS_INTERFACE = 45 | EXPERIMENTAL
    GET_LED_INTERFACE = 46 | EXPERIMENTAL
    GET_AUDIO_VIDEO_ENABLE = 47 | EXPERIMENTAL
    GET_MIDI_INTERFACE = 48 | EXPERIMENTAL
    GET_FASTFORWARDING = 49 | EXPERIMENTAL
    GET_TARGET_REFRESH_RATE = 50 | EXPERIMENTAL
    GET_INPUT_BITMASKS = 51 | EXPERIMENTAL

    GET_CORE_OPTIONS_VERSION = 52
    SET_CORE_OPTIONS = 53
    SET_CORE_OPTIONS_INTL = 54
    SET_CORE_OPTIONS_DISPLAY = 55
    GET_PREFERRED_HW_RENDER = 56
    GET_DISK_CONTROL_INTERFACE_VERSION = 57
    SET_DISK_CONTROL_EXT_INTERFACE = 58
    GET_MESSAGE_INTERFACE_VERSION = 59
    SET_MESSAGE_EXT = 60
    GET_INPUT_MAX_USERS = 61
    SET_AUDIO_BUFFER_STATUS_CALLBACK = 62
    SET_MINIMUM_AUDIO_LATENCY = 63
    SET_FASTFORWARDING_OVERRIDE = 64
    SET_CONTENT_INFO_OVERRIDE = 65
    GET_GAME_INFO_EXT = 66
    SET_CORE_OPTIONS_V2 = 67
    SET_CORE_OPTIONS_V2_INTL = 68
    SET_CORE_OPTIONS_UPDATE_DISPLAY_CALLBACK = 69
    SET_VARIABLE = 70

    GET_THROTTLE_STATE = 71 | EXPERIMENTAL
    GET_SAVESTATE_CONTEXT = 72 | EXPERIMENTAL
    GET_HW_RENDER_CONTEXT_NEGOTIATION_INTERFACE_SUPPORT = 73 | EXPERIMENTAL

    GET_JIT_CAPABLE = 74

    GET_MICROPHONE_INTERFACE = 75 | EXPERIMENTAL

    SET_NETPACKET_INTERFACE = 76

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
