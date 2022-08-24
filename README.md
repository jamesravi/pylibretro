# pylibretro

![](https://img.shields.io/pypi/v/pylibretro)
![](https://img.shields.io/pypi/status/pylibretro)
![](https://img.shields.io/pypi/pyversions/pylibretro)
![](https://img.shields.io/badge/platform-linux-lightgrey)
![](https://img.shields.io/pypi/l/pylibretro)

⚠️ This library is currently (and probably will remain) in a **severe pre-alpha state**. At the moment it is however able to load the 2048 core, press buttons and get screen output (as you can see below!). However, many callbacks and functions aren't handled, other cores (such as the PCSX ReARMed core) segfault etc. Use at your peril.

![](https://raw.githubusercontent.com/jamesravi/pylibretro/master/2048example.gif)

## Installation
`pip install pylibretro`

(the only dependency is [Pillow](https://pypi.org/project/Pillow/) if you wish to install it manually)

## Usage
You can create the GIF shown above by using the [example file](example.py) in this repository. However, here's a condensed, minimal usage example:

```python
from pylibretro import Core, buttons

lastframe = None

def on_frame(frame):
    global lastframe
    lastframe = frame

# Load the core
core = Core("./2048_libretro.so")
core.on_video_refresh = on_frame
core.retro_init()
core.retro_load_game(None)

# Start a 2048 game (by pressing the START button for one frame)
core.joystick[buttons.START] = True
core.retro_run()
core.joystick[buttons.START] = False

# Run core for 10 frames
for i in range(10):
    core.retro_run()

# Show the last screen output
lastframe.show()
```

## Licenses
pylibretro is licensed under [AGPLv3 or later](https://github.com/jamesravi/pylibretro/blob/master/LICENSE.md).

Credits to Rob Loach for [noarch](https://github.com/RobLoach/noarch) (which indicated how to call Libretro's API), the RetroArch team for [Libretro](https://www.libretro.com/index.php/api/) itself and also the [2048 core](https://github.com/libretro/libretro-2048) included within this repository as an example. Their corresponding licenses are also included in the [license file](https://github.com/jamesravi/pylibretro/blob/master/LICENSE.md).
