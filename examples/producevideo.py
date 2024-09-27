# Copyright (C) 2022 James Ravindran
# SPDX-License-Identifier: GPL-3.0-or-later

r"""
Example on loading the 2048 core, pressing random buttons for a number of frames, then creates a video
of the screen's output.
"""

from pylibretro import Core, buttons
import cv2
from tqdm import tqdm
import random
import platform
import numpy as np

frames = []

def on_frame(frame):
    global frames
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

directional_keys = [getattr(buttons, x) for x in ["UP", "DOWN", "LEFT", "RIGHT"]]

# Randomly press directional buttons for a certain number of frames
print("Running 2048 core...")
number_of_frames = 200
with tqdm(total=number_of_frames) as pbar:
    while len(frames) < number_of_frames:
        for key in directional_keys:
            core.joystick[key] = random.choice([False, True])
        core.run()
        pbar.n = len(frames)
        pbar.refresh()

# Calculate maximum resolution (for video output)
max_res = (max(frame.shape[0] for frame in frames), max(frame.shape[1] for frame in frames))
print("Maximum resolution:", max_res)

# Create a video of the screen's output
video = cv2.VideoWriter("2048example.mp4", cv2.VideoWriter_fourcc(*'mp4v'), fps, tuple(reversed(max_res)))
for frame in frames:
    #current_res = list(frame.shape)[:-1]
    #videoframe = cv2.copyMakeBorder(frame, 0, max_res[1]-current_res[1], 0, current_res[0]-current_res[0], cv2.BORDER_CONSTANT)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    video.write(frame)
video.release()

print("Done! (produced video)")