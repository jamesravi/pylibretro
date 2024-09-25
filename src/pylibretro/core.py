# Copyright (C) 2022 James Ravindran
# SPDX-License-Identifier: GPL-3.0-or-later

from cffi import FFI
import logging
from pathlib import Path
import pycparser_fake_libc
import subprocess
import numpy as np

from . import utils

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
    def __init__(self, corepath, systemdir=".", savedir="."):
        self.support_no_game = False # Do I even need this? Is this being used for anything?
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
        logging.debug(f"retro_environment {cmd} {data}")
        # TODO: Could remove this try except and assume every cmd is defined in utils.RETRO_ENVIRONMENT
        try:
            cmd = utils.RETRO_ENVIRONMENT(cmd)
        except ValueError:
            logging.warning(f"Unhandled env {cmd}")
            return False
        match cmd:
            case utils.RETRO_ENVIRONMENT.SET_SUPPORT_NO_GAME:
                bool_no_game = self.ffi.cast("bool *", data)
                self.support_no_game = bool_no_game
            case utils.RETRO_ENVIRONMENT.SET_PIXEL_FORMAT:
                pixel_format_enum = self.ffi.cast("enum retro_pixel_format *", data)
                self.pixel_format = utils.RETRO_PIXEL_FORMAT(pixel_format_enum[0])
            case _:
                logging.warning(f"Unhandled env {cmd}")
                return False
        return True
        
    def retro_video_refresh(self, data, width, height, pitch):    
        logging.debug(f"video_refresh {data} {width} {height} {pitch}")
        imagedata = self.ffi.cast("unsigned char *", data)
        imagedata = bytes(self.ffi.buffer(imagedata, height * pitch))
        if self.pixel_format == utils.RETRO_PIXEL_FORMAT.ZERORGB1555:
            bytes_per_pixel = pitch // 2
            dtype = np.uint16
        elif self.pixel_format == utils.RETRO_PIXEL_FORMAT.XRGB8888:
            bytes_per_pixel = pitch // 4
            dtype = np.uint32
        else:
            raise Exception(self.pixel_format)
        imagearray = np.frombuffer(imagedata, dtype=dtype).reshape((height, bytes_per_pixel))
        image = np.zeros((height, bytes_per_pixel, 3), dtype=np.uint8)
        for y in range(height):
            for x in range(bytes_per_pixel):
                pixel = imagearray[y, x]
                r, g, b = utils.unpack_pixel(pixel, self.pixel_format)
                image[y, x] = [r, g, b]
        self.on_video_refresh(image)
        
    def retro_audio_sample(self, left, right):
        # TODO: Like on_video_refresh and on_input_poll, have a callback function for this the user can redefine
        logging.debug(f"audio_sample {left} {right}")
        
    def retro_audio_sample_batch(self, data, frames):
        # TODO: Like on_video_refresh and on_input_poll, have a callback function for this the user can redefine
        # I assume this logging debug line won't work? (will have to find a core with sound that doesn't segfault to see)
        logging.debug(f"audio_sample_batch {data} {frames}")
        return -1
        
    def retro_input_poll(self):
        logging.debug("input_poll")
        self.on_input_poll()
        
    def retro_input_state(self, port, device, index, theid):
        # c_int16, c_uint, c_uint, c_uint, c_uint
        # TODO: Probably have to re-do with CFFI
        logging.debug("retro_input_state %s %s %s %s", port, device, index, theid)
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

    ###

    def on_input_poll(self):
        pass

    def on_video_refresh(self, image):
        pass
