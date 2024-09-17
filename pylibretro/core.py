# Copyright (C) 2022 James Ravindran
# SPDX-License-Identifier: AGPL-3.0-or-later

from cffi import FFI
from inspect import getmembers
from PIL import Image
import logging
import os
from pathlib import Path
import pycparser_fake_libc
import subprocess

from . import utils

logging.basicConfig(level=logging.INFO)

def cdata_dict(ffi, cd):
    if isinstance(cd, ffi.CData):
        try:
            return ffi.string(cd)
        except TypeError:
            try:
                return [cdata_dict(ffi, x) for x in cd]
            except TypeError:
                return {k: cdata_dict(ffi, v) for k, v in getmembers(cd)}
    else:
        return cd

def parse_variables(ffi, data):
    variables = {}
    pointer = ffi.cast("VARIABLE *", data)

    while True:
        key = ffi.string(pointer.key).decode("ascii") if pointer.key else None
        value = ffi.string(pointer.value).decode("ascii") if pointer.value else None

        if key is None and value is None:
            break
        else:
            description, choices = list(map(str.strip, value.split(";")))
            variables[key] = {"description": description, "choices": choices.split("|"), "value": None}

        pointer = ffi.cast("VARIABLE *", ffi.cast("char *", pointer) + ffi.sizeof("VARIABLE"))

    return variables

def preprocess_header(header_file):
    cmd = ["gcc", "-E", str(header_file), "-D__attribute__(x)=", "-I"+pycparser_fake_libc.directory]
    #print(" ".join(cmd))

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Unable to preprocess {header_file}, is gcc installed?")

class Core:
    def __init__(self, corepath, systemdir=".", savedir=".", render=False):
        self.systemdir = systemdir
        self.savedir = savedir
        self.render = render
        
        self.support_no_game = None
        self.pixel_format = utils.RETRO_PIXEL_FORMAT.ZERORGB1555
        self.variables = {}
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
            case utils.RETRO_ENVIRONMENT.GET_SYSTEM_DIRECTORY:
                char_pp = self.ffi.cast("char **", data)
                char_pp[0] = self.ffi.new("char[]", self.systemdir.encode("ascii"))
            case utils.RETRO_ENVIRONMENT.GET_SAVE_DIRECTORY:
                char_pp = self.ffi.cast("char **", data)
                char_pp[0] = self.ffi.new("char[]", self.savedir.encode("ascii"))
            case utils.RETRO_ENVIRONMENT.SET_PIXEL_FORMAT:
                pixel_format_enum = self.ffi.cast("enum retro_pixel_format *", data)
                self.pixel_format = utils.RETRO_PIXEL_FORMAT(pixel_format_enum[0])
            case utils.RETRO_ENVIRONMENT.SET_SUPPORT_NO_GAME:
                bool_no_game = self.ffi.cast("bool *", data)
                self.support_no_game = bool_no_game
            case utils.RETRO_ENVIRONMENT.GET_PREFERRED_HW_RENDER:
                return False
            case utils.RETRO_ENVIRONMENT.SET_VARIABLES:
                self.variables = {**self.variables, **parse_variables(self.ffi, data)}
            case utils.RETRO_ENVIRONMENT.GET_VARIABLE:
                variable_ptr = self.ffi.cast("struct retro_variable *", data)
                key = self.ffi.string(variable_ptr.key).decode()
                if key in self.variables and self.variables[key]["value"] is not None:
                    variable_ptr.value = self.ffi.new("char[]", self.variables[key]["value"].encode("utf-8"))
            case utils.RETRO_ENVIRONMENT.GET_LOG_INTERFACE:
                # Apparently, CFFI does not support callbacks with variadic arguments, so this is impossible to implement
                # Logging seems to work with some cores anyway (e.g. Swanstation) so we can ignore it though
                return False # or just return True regardless?
            #case RETRO_ENVIRONMENT_GET_CAN_DUPE:
            #case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY | RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY | RETRO_ENVIRONMENT_GET_CONTENT_DIRECTORY | RETRO_ENVIRONMENT_GET_LIBRETRO_PATH:
            #case RETRO_ENVIRONMENT_SET_MESSAGE:
            #case RETRO_ENVIRONMENT_SHUTDOWN:
            case _:
                logging.warning(f"Unhandled env {cmd}")
                return False
        return True
        
    def retro_video_refresh(self, data, width, height, pitch):
        """
        TODO: Interestingly from libretro.h it seems dropped frames are intentional behaviour:
        
        If a frame is not rendered for reasons where a game "dropped" a frame,
        this still counts as a frame, and retro_run() should explicitly dupe
        a frame if RETRO_ENVIRONMENT_GET_CAN_DUPE returns true. In this case,
        the video callback can take a NULL argument for data.
        """
    
        logging.debug("video_refresh %s %s", width, height, pitch)
        if self.render:
            if self.pixel_format == utils.RETRO_PIXEL_FORMAT.ZERORGB1555:
                imagedata = self.ffi.cast("unsigned char *", data)
                imagedata = bytes(self.ffi.buffer(imagedata, width * height * 2))
                imagedata = utils.zerorgb1555_to_rgb888(imagedata)
            elif self.pixel_format == utils.RETRO_PIXEL_FORMAT.XRGB8888:
                imagedata = self.ffi.cast("unsigned char *", data)
                imagedata = bytes(self.ffi.buffer(imagedata, width * height * 4))
                imagedata = utils.group_argb8888(imagedata)
            else:
                raise Exception(self.pixel_format)
            image = Image.new("RGB", (width, height))
            image.putdata(imagedata)
            self.on_video_refresh(image)
        
    def retro_audio_sample(self, left, right):
        # TODO: Like on_video_refresh and on_input_poll, have a callback function for this the user can redefine
        logging.debug("audio_sample %s %s", left, right)
        pass
        
    def retro_audio_sample_batch(self, data, frames):
        # TODO: Like on_video_refresh and on_input_poll, have a callback function for this the user can redefine
        # I assume this logging debug line won't work? (will have to find a core with sound that doesn't segfault to see)
        logging.debug("audio_sample_batch %s %s", data, frames)
        pass
        
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
        return cdata_dict(self.ffi, system_info)

    def get_system_av_info(self):
        system_av_info = self.ffi.new("struct retro_system_av_info *")
        self.core.retro_get_system_av_info(system_av_info)
        return cdata_dict(self.ffi, system_av_info)
        
    def set_controller_port_device(self, port=0, device=utils.RETRO_DEVICE_JOYPAD):
        self.core.retro_set_controller_port_device(port, device)

    def init(self):
        self.core.retro_init()

    def run(self):
        self.core.retro_run()

    def load_game(self, rompath=None):
        """
        TODO: If need_fullpath in get_system_info() is True, rompath should be a valid path,
        and there shouldn't need to be a need to load the entire rom in memory I don't think.
        Could write a high level wrapper around this class (rename this low-level one RetroCore or core_ or something)
        and the high level wrapper could mimic JSNES's API (or PyBoy's) or something
        """
        if rompath is None:
            raise Exception("Empty rom path not implemented yet")
            """
            size = 0
            rompath_bytes = ""
            # From libretro.h: "...it is preferable to fabricate something here instead of passing NULL, which will help more cores to succeed."
            """
        else:
            #size = os.path.getsize(rompath)
            rompath_bytes = rompath.encode("utf-8")
        #game_info = utils.GAME_INFO(rompath_bytes, None, 0, None)
        game_info = self.ffi.new("struct retro_game_info *")
        game_info.path = self.ffi.new("char[]", rompath_bytes)
        game_info.size = len(rompath_bytes)
        self.core.retro_load_game(game_info)

    ###

    def on_input_poll(self):
        pass

    def on_video_refresh(self, image):
        pass
