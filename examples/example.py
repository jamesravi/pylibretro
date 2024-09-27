# Copyright (C) 2022 James Ravindran
# SPDX-License-Identifier: GPL-3.0-or-later

r"""
Example on loading the 2048 core, pressing random buttons for a number of frames, then creating an animated GIF
of the screen's output.
"""

from pylibretro import Core, buttons
import imageio
from tqdm import tqdm
import random
import platform
import numpy as np

frames = []

# Just to avoid getting the starting frames so the GIF doesn't flash when it loops back around
started = False

def on_frame(frame):
    global frames
    if not np.any(np.all(frame == [0, 0, 0], axis=-1)) and started:
        frames.append(frame)

# Load the core
if platform.system() == "Linux":
    core = Core("./2048_libretro.so")
elif platform.system() == "Windows":
    core = Core("2048_libretro.dll")
else:
    raise Exception("Unsupported OS")
core.on_video_refresh = on_frame
print("System info:", core.get_system_info())
print("System AV info:", core.get_system_av_info())
fps = int(core.get_system_av_info()["timing"]["fps"])
core.init()
core.load_game(None)

# Start a 2048 game (by pressing the START button for one frame)
core.joystick[buttons.START] = True
core.run()
core.joystick[buttons.START] = False
started = True

directional_keys = [getattr(buttons, x) for x in ["UP", "DOWN", "LEFT", "RIGHT"]]

# Just randomly press directional buttons until we get a certain number of good frames (see on_frame function)
print("Running 2048 core...")
number_of_frames = 150
with tqdm(total=number_of_frames) as pbar:
    while len(frames) < number_of_frames:
        for key in directional_keys:
            core.joystick[key] = random.choice([False, True])
        core.run()
        pbar.n = len(frames)
        pbar.refresh()

# Create an animated GIF of the screen's output
imageio.mimsave("2048example.gif", frames, loop=0, fps=fps/4)

print("Done! (produced GIF)")
