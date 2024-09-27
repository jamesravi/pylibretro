# pylibretro

[![](https://img.shields.io/pypi/v/pylibretro)](https://pypi.org/project/pylibretro)
[![](https://img.shields.io/pypi/status/pylibretro)](https://pypi.org/project/pylibretro)
[![](https://img.shields.io/pypi/pyversions/pylibretro)](https://pypi.org/project/pylibretro)
[![](https://img.shields.io/badge/platform-windows%20|%20linux-lightgrey)](https://pypi.org/project/pylibretro)
[![](https://img.shields.io/pypi/l/pylibretro)](https://pypi.org/project/pylibretro)

⚠️ This library is currently in a **severe pre-alpha state**. At the moment it is however able to load the 2048 core, press buttons and get screen output (as you can see below!). However, many callbacks and functions aren't handled, other cores may segfault etc. Use at your peril.

![](https://raw.githubusercontent.com/jamesravi/pylibretro/master/examples/2048example.gif)

## Installation
`pip install pylibretro`

You can install the dependencies for the examples in `examples` or the snippet below by running `pip install pylibretro[examples]`

## Usage
You can create the GIF shown above by using the [example file](examples/producegif.py) in this repository. However, here's a condensed, minimal usage example:

```python
from pylibretro import Core, buttons
import platform

from PIL import Image

lastframe = None

def on_frame(frame):
    global lastframe
    lastframe = frame

# Load the core
if platform.system() == "Linux":
    core = Core("./2048_libretro.so")
elif platform.system() == "Windows":
    core = Core("2048_libretro.dll")

core.on_video_refresh = on_frame
core.init()
core.load_game(None)

# Start a 2048 game (by pressing the START button for one frame)
core.joystick[buttons.START] = True
core.run()
core.joystick[buttons.START] = False

# Run core for 10 frames
for i in range(10):
    core.run()

# Show the last screen output
lastframe = Image.fromarray(lastframe)
lastframe.show()
```

## Licenses
pylibretro is licensed under [GPLv3 or later](https://github.com/jamesravi/pylibretro/blob/master/LICENSE.md).

Credits to the RetroArch team for the [libretro API](https://www.libretro.com/index.php/api/) and also the [2048 core](https://github.com/libretro/libretro-2048) included within this repository as an example. Their corresponding licenses are also included in the [license file](https://github.com/jamesravi/pylibretro/blob/master/LICENSE.md).
