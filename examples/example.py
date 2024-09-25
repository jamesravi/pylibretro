# Copyright (C) 2022 James Ravindran
# SPDX-License-Identifier: AGPL-3.0-or-later

r"""
Example on loading the 2048 core, pressing random buttons for a number of frames, then creating an animated GIF
of the screen's output.
"""

# This allows you to run this file without installing the package (assuming you've cloned the repo) 
import sys
sys.path.append("..")

from pylibretro import Core, buttons
from PIL import Image
from tqdm import tqdm
import random
import platform

frames = []

# Just to avoid getting the starting frames so the GIF doesn't flash when it loops back around
started = False

def on_frame(frame):
    r"""
    For some reason the 2048 core occasionally returns black (or mostly black) images
    Not sure if it's something wrong with my implementation instead of the core, but to avoid making this
    example more convoluted, we'll simply ignore them.
    Unfortunately, this results in even worse performance (hence the progress bar).
    """

    # TODO: Don't use PIL, use OpenCV/Numpy, it should be faster

    global frames
    frame = Image.fromarray(frame)
    if not any(pixel == (0, 0, 0) for pixel in frame.getdata()) and started:
        frames.append(frame)
    else:
        print(started)

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
pbar = tqdm(total=number_of_frames)
while len(frames) < number_of_frames:
    for key in directional_keys:
        core.joystick[key] = random.choice([False, True])
    core.run()
    pbar.n = len(frames)
    pbar.refresh()

# Create an animated GIF of the screen's output
# (adapted from https://stackoverflow.com/a/57751793)
frames[0].save(fp="2048example.gif", format="GIF", append_images=frames[1:],
               save_all=True, duration=1000/15, loop=0)

print("Done! (produced GIF)")
