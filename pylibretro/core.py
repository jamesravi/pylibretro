# Copyright (C) 2022 James Ravindran
# SPDX-License-Identifier: AGPL-3.0-or-later

from ctypes import cdll, CFUNCTYPE, POINTER, cast
from ctypes import c_bool, c_int, c_uint, c_int16, c_char_p, c_void_p, c_size_t
from PIL import Image
import logging
import os

from . import utils

logging.basicConfig(level=logging.INFO)

class Core:
    def __init__(self, filename):
        self.support_no_game = None
        self.pixel_format = utils.RETRO_PIXEL_FORMAT.ZERORGB1555
        self.variables = {}
        self.joystick = {button: False for button in utils.RETRO_DEVICE_ID_JOYPAD}
        self.gamefilename = None

        self.environment_cb = self.get_environment_cb()
        self.video_refresh_cb = self.get_video_refresh_cb()
        self.audio_sample_cb = self.get_audio_sample_cb()
        self.audio_sample_batch_cb = self.get_audio_sample_batch_cb()
        self.input_poll_cb = self.get_input_poll_cb()
        self.input_state_cb = self.get_input_state_cb()

        self.core = cdll.LoadLibrary(filename)
        self.core.retro_set_environment(self.environment_cb)
        self.core.retro_set_video_refresh(self.video_refresh_cb)
        self.core.retro_set_audio_sample(self.audio_sample_cb)
        self.core.retro_set_audio_sample_batch(self.audio_sample_batch_cb)
        self.core.retro_set_input_poll(self.input_poll_cb)
        self.core.retro_set_input_state(self.input_state_cb)

    def get_environment_cb(self):
        # TODO: Not sure when to return True/False, maybe dependant on cmd?
        @CFUNCTYPE(c_bool, c_uint, POINTER(c_void_p))
        def retro_environment(cmd, data):
            logging.debug(f"retro_environment {cmd} {data}")
            try:
                cmd = utils.RETRO_ENVIRONMENT(cmd)
            except ValueError:
                logging.warning(f"Unhandled env {cmd}")
                return False
            match cmd:
                case utils.RETRO_ENVIRONMENT.SET_PIXEL_FORMAT:
                    self.pixel_format = utils.RETRO_PIXEL_FORMAT(cast(data, POINTER(c_int)).contents.value)
                case utils.RETRO_ENVIRONMENT.SET_SUPPORT_NO_GAME:
                    self.support_no_game = cast(data, POINTER(c_bool)).contents.value
                case utils.RETRO_ENVIRONMENT.GET_VARIABLE:
                    contents = cast(data, POINTER(utils.VARIABLE)).contents
                    key, value = contents.key, contents.value
                    if key in self.variables:
                        # TODO: Not sure if this works
                        contents.value = self.variables[key]["value"]
                    else:
                        contents.value = None
                    return True
                case utils.RETRO_ENVIRONMENT.SET_VARIABLES:
                    self.variables = {**self.variables, **utils.read_array_of_variables(data)}
                #case RETRO_ENVIRONMENT_GET_LOG_INTERFACE:
                #case RETRO_ENVIRONMENT_GET_CAN_DUPE:
                #case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT:
                #case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY | RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY | RETRO_ENVIRONMENT_GET_CONTENT_DIRECTORY | RETRO_ENVIRONMENT_GET_LIBRETRO_PATH:
                #case RETRO_ENVIRONMENT_SET_MESSAGE:
                #case RETRO_ENVIRONMENT_SHUTDOWN:
                case _:
                    logging.warning(f"Unhandled env {cmd}")
                    return False
            return True

        return retro_environment

    def get_video_refresh_cb(self):
        @CFUNCTYPE(None, POINTER(c_void_p), c_uint, c_uint, c_size_t)
        def retro_video_refresh(data, width, height, pitch):
            logging.debug("video_refresh %s %s", width, height, pitch)
            if self.pixel_format == utils.RETRO_PIXEL_FORMAT.ZERORGB1555:
                imagedata = cast(data, c_char_p).value[0:width * height * 2]
                imagedata = utils.zerorgb1555_to_rgb888(imagedata)
            elif self.pixel_format == utils.RETRO_PIXEL_FORMAT.XRGB8888:
                imagedata = cast(data, c_char_p).value[0:width * height * 4]
                imagedata = utils.group_argb8888(imagedata)
            else:
                raise Exception(self.pixel_format)
            image = Image.new("RGB", (width, height))
            image.putdata(imagedata)
            self.on_video_refresh(image)

        return retro_video_refresh

    def get_audio_sample_cb(self):
        @CFUNCTYPE(None, c_int16, c_int16)
        def retro_audio_sample(left, right):
            logging.debug("audio_sample %s %s", left, right)
            pass

        return retro_audio_sample

    def get_audio_sample_batch_cb(self):
        @CFUNCTYPE(c_size_t, c_int16, c_size_t)
        def retro_audio_sample_batch(data, frames):
            # I assume this logging debug line won't work? (will have to find a core with sound that doesn't segfault to see)
            logging.debug("audio_sample_batch %s %s", data, frames)
            pass

        return retro_audio_sample_batch

    def get_input_poll_cb(self):
        @CFUNCTYPE(None)
        def retro_input_poll():
            logging.debug("input_poll")
            self.on_input_poll()

        return retro_input_poll

    def get_input_state_cb(self):
        @CFUNCTYPE(c_int16, c_uint, c_uint, c_uint, c_uint)
        def retro_input_state(port, device, index, theid):
            logging.debug("retro_input_state %s %s %s %s", port, device, index, theid)
            if port or index or device != utils.RETRO_DEVICE_JOYPAD:
                return 0
            return self.joystick[utils.RETRO_DEVICE_ID_JOYPAD(theid)]

        return retro_input_state

    def get_system_info(self):
        self.core.retro_get_system_info.argtypes = [POINTER(utils.SYSTEM_INFO)]
        self.core.retro_get_system_info.restype = None
        system_info = utils.SYSTEM_INFO()
        self.core.retro_get_system_info(system_info)
        return utils.struct_to_dict(system_info)

    def get_system_av_info(self):
        self.core.retro_get_system_info.argtypes = [POINTER(utils.SYSTEM_AV_INFO)]
        self.core.retro_get_system_info.restype = None
        system_av_info = utils.SYSTEM_AV_INFO()
        self.core.retro_get_system_info(system_av_info)
        result = {**utils.struct_to_dict(system_av_info.geometry), **utils.struct_to_dict(system_av_info.timing)}
        return result

    def set_controller_port_device(self, port=0, device=utils.RETRO_DEVICE_JOYPAD):
        self.core.retro_set_controller_port_device.argtypes = [c_uint, c_uint]
        self.core.retro_set_controller_port_device.restype = None
        self.core.retro_set_controller_port_device(port, device)

    def retro_init(self):
        self.core.retro_init()

    def retro_run(self):
        self.core.retro_run()

    def retro_load_game(self, filename):
        self.core.retro_load_game.argtypes = [POINTER(utils.GAME_INFO)]
        self.core.retro_load_game.restype = c_bool
        if filename is None:
            size = 0
        else:
            size = os.path.getsize(filename)
        # Attempt here to prevent a segfault (assuming filename is deallocated or something), but doesn't seem to work
        self.gamefilename = filename
        system_av_info = utils.GAME_INFO(self.gamefilename, 0, size, None)
        self.core.retro_load_game(system_av_info)

    ###

    def on_input_poll(self):
        pass

    def on_video_refresh(self, image):
        pass
