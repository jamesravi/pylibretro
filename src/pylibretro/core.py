# Copyright (C) 2022 James Ravindran
# SPDX-License-Identifier: GPL-3.0-or-later

from cffi import FFI
import logging
from pathlib import Path
import pycparser_fake_libc
import subprocess
import numpy as np

from . import utils

logger = logging.getLogger("pylibretro")
logger.setLevel(logging.ERROR)

def preprocess_header(header_file):
    cmd = ["gcc", "-E", str(header_file), "-D__attribute__(x)=", "-I"+pycparser_fake_libc.directory]
    #print(" ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        error = f"Unable to preprocess {header_file}, is gcc installed?"
        error += f"\nCommand to test with: {' '.join(cmd)}"
        raise RuntimeError(error)

class Core:
    def __init__(self, corepath, system_dir=".", save_dir="."):
        self.system_dir = system_dir
        self.save_dir = save_dir
        self.pixel_format = utils.RETRO_PIXEL_FORMAT.ZERORGB1555
        self.joystick = {button: False for button in utils.RETRO_DEVICE_ID_JOYPAD}
    
        self.ffi = FFI()

        preprocessed_header = preprocess_header(Path(__file__).parent / "libretro.h")
        self.ffi.cdef(preprocessed_header)
        
        self.core = self.ffi.dlopen(corepath)
        
        self.ffi.cdef("""
        typedef struct {
            char* key;
            char* value;
        } VARIABLE;
        """)
        
        self.environment_cb = self.ffi.callback("retro_environment_t", self.retro_environment)
        self.video_refresh_cb = self.ffi.callback("retro_video_refresh_t", self.retro_video_refresh)
        self.audio_sample_cb = self.ffi.callback("retro_audio_sample_t", self.retro_audio_sample)
        self.audio_sample_batch_cb = self.ffi.callback("retro_audio_sample_batch_t", self.retro_audio_sample_batch)
        self.input_poll_cb = self.ffi.callback("retro_input_poll_t", self.retro_input_poll)
        self.input_state_cb = self.ffi.callback("retro_input_state_t", self.retro_input_state)
        
        self.core.retro_set_environment(self.environment_cb)
        self.core.retro_set_video_refresh(self.video_refresh_cb)
        self.core.retro_set_audio_sample(self.audio_sample_cb)
        self.core.retro_set_audio_sample_batch(self.audio_sample_batch_cb)
        self.core.retro_set_input_poll(self.input_poll_cb)
        self.core.retro_set_input_state(self.input_state_cb)

        # libretro.h says retro_get_system_info can be called at any time, even before retro_init
        self.need_fullpath = self.get_system_info()["need_fullpath"]
        
    def retro_environment(self, cmd, data):
        # TODO: Not sure when to return True/False, maybe dependant on cmd?
        logger.debug(f"retro_environment {cmd} {data}")
        cmd = utils.RETRO_ENVIRONMENT(cmd)
        match cmd:
            case utils.RETRO_ENVIRONMENT.SET_PIXEL_FORMAT:
                pixel_format_enum = self.ffi.cast("enum retro_pixel_format *", data)
                self.pixel_format = utils.RETRO_PIXEL_FORMAT(pixel_format_enum[0])
                return True
            case utils.RETRO_ENVIRONMENT.GET_SYSTEM_DIRECTORY:
                c_system_dir = self.ffi.new("char[]", self.system_dir.encode("ascii"))
                self.ffi.cast("const char **", data)[0] = c_system_dir
                return True
            case utils.RETRO_ENVIRONMENT.GET_SAVE_DIRECTORY:
                c_save_dir = self.ffi.new("char[]", self.save_dir.encode("ascii"))
                self.ffi.cast("const char **", data)[0] = c_save_dir
                return True
            case _:
                logger.warning(f"Unhandled env {cmd}")
                return False
        return False
        
    def retro_video_refresh(self, data, width, height, pitch):    
        logger.debug(f"video_refresh {data} {width} {height} {pitch}")
        imagedata = self.ffi.cast("unsigned char *", data)
        imagedata = bytes(self.ffi.buffer(imagedata, height * pitch))
        if self.pixel_format in [utils.RETRO_PIXEL_FORMAT.ZERORGB1555, utils.RETRO_PIXEL_FORMAT.RGB565]:
            dtype = np.uint16
        elif self.pixel_format == utils.RETRO_PIXEL_FORMAT.XRGB8888:
            dtype = np.uint32
        else:
            raise Exception(self.pixel_format)
        imagearray = np.frombuffer(imagedata, dtype=dtype).reshape((height, width))
        image = np.zeros((height, width, 3), dtype=np.uint8)
        if self.pixel_format == utils.RETRO_PIXEL_FORMAT.ZERORGB1555:
            r = (imagearray >> 10) & 0x1F
            g = (imagearray >> 5) & 0x1F
            b = imagearray & 0x1F
            image[..., 0] = (r * 255) // 31
            image[..., 1] = (g * 255) // 31
            image[..., 2] = (b * 255) // 31
        elif self.pixel_format == utils.RETRO_PIXEL_FORMAT.XRGB8888:
            image[..., 0] = (imagearray >> 16) & 0xFF
            image[..., 1] = (imagearray >> 8) & 0xFF
            image[..., 2] = imagearray & 0xFF
        elif self.pixel_format == utils.RETRO_PIXEL_FORMAT.RGB565:
            r = (imagearray >> 11) & 0x1F
            g = (imagearray >> 5) & 0x3F
            b = imagearray & 0x1F
            image[..., 0] = (r * 255) // 31
            image[..., 1] = (g * 255) // 63
            image[..., 2] = (b * 255) // 31
        self.on_video_refresh(image)
        
    def retro_audio_sample(self, left, right):
        # TODO: Like on_video_refresh and on_input_poll, have a callback function for this the user can redefine
        logger.debug(f"audio_sample {left} {right}")
        
    def retro_audio_sample_batch(self, data, frames):
        # TODO: Like on_video_refresh and on_input_poll, have a callback function for this the user can redefine
        # I assume this logging debug line won't work? (will have to find a core with sound that doesn't segfault to see)
        logger.debug(f"audio_sample_batch {data} {frames}")
        return -1
        
    def retro_input_poll(self):
        logger.debug("input_poll")
        self.on_input_poll()
        
    def retro_input_state(self, port, device, index, theid):
        # c_int16, c_uint, c_uint, c_uint, c_uint
        # TODO: Probably have to re-do with CFFI
        logger.debug("retro_input_state %s %s %s %s", port, device, index, theid)
        if port or index or device != utils.RETRO_DEVICE_JOYPAD:
            return 0
        return self.joystick[utils.RETRO_DEVICE_ID_JOYPAD(theid)]
    
    ###

    def get_system_info(self):
        system_info = self.ffi.new("struct retro_system_info *")
        self.core.retro_get_system_info(system_info)
        return utils.cdata_dict(system_info, self.ffi)

    def get_system_av_info(self):
        system_av_info = self.ffi.new("struct retro_system_av_info *")
        self.core.retro_get_system_av_info(system_av_info)
        return utils.cdata_dict(system_av_info, self.ffi)

    def init(self):
        self.core.retro_init()

    def run(self):
        self.core.retro_run()

    def load_game(self, rompath):
        game_info = self.ffi.new("struct retro_game_info *")
        if rompath is not None:
            if self.need_fullpath:
                game_info.path = self.ffi.new("char[]", rompath.encode("ascii"))
            else:
                with open(rompath, "rb") as file:
                    content = file.read()
                game_info.data = content
                game_info.size = len(content)
        self.core.retro_load_game(game_info)
    
    def get_ram(self, mem_type=utils.RETRO_MEMORY.SYSTEM_RAM):
        if type(mem_type) is utils.RETRO_MEMORY:
            mem_type = mem_type.value
        size = self.core.retro_get_memory_size(mem_type)
        if size == 0:
            return None
        mem_ptr = self.core.retro_get_memory_data(mem_type)
        if mem_ptr == self.ffi.NULL:
            return None
        mem_array = np.frombuffer(self.ffi.buffer(mem_ptr, size), dtype=np.uint8)
        return mem_array

    def get_state(self):
        size = self.core.retro_serialize_size()
        if size == 0:
            return None
        state_data = self.ffi.new(f"char[{size}]")
        success = self.core.retro_serialize(state_data, size)
        if success:
            return bytes(self.ffi.buffer(state_data, size))
        else:
            return None

    def set_state(self, state_data):
        size = len(state_data)
        state_buffer = self.ffi.new(f"char[{size}]", state_data)
        success = self.core.retro_unserialize(state_buffer, size)
        return success

    ###

    def on_input_poll(self):
        pass

    def on_video_refresh(self, image):
        pass
