# GIF Player

Plays GIFs on the Windows desktop with no window around them: no title bar,
no border, no shadow. Transparent parts stay see-through and let clicks pass
to whatever is behind. Play one GIF or several at once; each gets its own
window with the same controls.

It is built to use almost no CPU. Frames are prepared once at startup, and
between frames the player sleeps until the next one is due. All GIFs share
one program and one clock, so several cost little more than one. A typical
GIF uses under 1% of one CPU core, and nothing while paused.

## Run it

1. Install [Python 3](https://www.python.org/downloads/) and turn on
   **Add python.exe to PATH** during setup.
2. Put your GIFs in the `images` folder.
3. Open `gif_player.py` and list their file names in `GIFS`.
4. Double-click `play.bat`.

The first time, `play.bat` installs [Pillow](https://pypi.org/project/pillow/)
if it is missing.

## Several GIFs

`GIFS` is a list. Each file name opens in its own window:

```python
GIFS = [
    "sonic_wait.gif",
    "sonic_run.gif",
]
```

GIFs line up side by side at `POSITION`, `MARGIN` apart, and stand on a
shared baseline. They wrap to a new row when the screen is full.

To give one GIF its own settings, write it as a dict instead of a file name:

```python
GIFS = [
    "sonic_wait.gif",
    {"file": "sonic_run.gif", "position": "bottom-right", "scale": 2,
     "speed": 1.5, "rotate": True},
]
```

| Key | What it sets | When left out |
|---|---|---|
| `file` | GIF file name in `images` (required) | |
| `position` | Where this GIF opens, same choices as `POSITION` | Lined up with the others |
| `scale` | Size on launch | `SCALE` |
| `speed` | Playback speed | `SPEED` |
| `rotate` | Whether the rotate button starts enabled | `ROTATE_ENABLED` |

The same file can be listed more than once.

## Controls

Each GIF has its own controls, so you can move, pause or rotate one without
touching the others.

| Do this | What happens |
|---|---|
| Drag the picture | Moves it |
| Drag an edge or a corner | Resizes it; the picture keeps its proportions |
| Right-click → **Pause** / **Play** | Stops or restarts the animation |
| Right-click → **Enable rotate** / **Disable rotate** | Shows or hides the rotate button |
| Hover, then drag the round button in the top-left corner | Rotates the picture around its center (only while rotate is enabled) |
| Double-click the picture | Stands it upright again |
| Right-click → **Close** | Closes that GIF. The player quits when the last one closes |
| Right-click → **Close all**, or `Ctrl+Shift+Q` | Closes every GIF and quits |

Notes:

- The edges you drag to resize are invisible. The pointer changes when it is
  over one.
- While rotating, the picture snaps to upright, sideways or upside down when
  you get within 3° of it.
- When the rotate button is showing, it covers the top-left corner, so resize
  from one of the other corners or an edge.
- A rotated picture can still be moved and resized.
- **Close all** only shows when more than one GIF is open.
- `Ctrl+Shift+Q` works even when the GIFs are hidden behind other windows.
  If another program already uses it, the player says so when it starts.

## Settings

All settings are at the top of `gif_player.py`, under **Settings**. Save the
file and run `play.bat` again to apply them.

| Setting | Default | What it does |
|---|---|---|
| `GIFS` | `["sonic_wait.gif", "sonic_run.gif"]` | GIFs to play, from the `images` folder. See [Several GIFs](#several-gifs) |
| `SPEED` | `1.0` | Playback speed. `2.0` is twice as fast, `0.5` half speed |
| `SCALE` | `1.0` | Size on launch. `1.0` is the GIF's own size, `2.0` double |
| `POSITION` | `"center"` | Where the GIFs open: `"center"`, `"top-left"`, `"top-right"`, `"bottom-left"`, `"bottom-right"`, `"top"`, `"bottom"`, `"left"`, `"right"`, or an `(x, y)` pixel pair |
| `MARGIN` | `24` | Gap from the screen edge for the named positions, and between GIFs side by side, in pixels |
| `ALWAYS_ON_TOP` | `True` | Keep the GIFs above other windows |
| `EDGE_PX` | `10` | Width of the invisible resize edge, in pixels |
| `MIN_SIZE` | `32` | Smallest the picture can be resized to, in pixels |
| `RESAMPLE` | `"nearest"` | How resizing smooths pixels. `"nearest"` keeps pixel art sharp; `"bilinear"` or `"lanczos"` suit photos |
| `ROTATE_ENABLED` | `False` | Whether the rotate button is enabled when the player starts |
| `ROTATE_BUTTON_PX` | `22` | Size of the rotate button, in pixels |
| `ROTATE_SNAP` | `3` | How close, in degrees, rotation must get to snap straight. `0` turns snapping off |
| `QUIT_MODIFIERS`, `QUIT_KEY` | `("ctrl", "shift")`, `"q"` | The shortcut that closes every GIF. Modifiers can be `ctrl`, `shift`, `alt` and `win`; the key can be one character, `esc` or `space` |

Pixel sizes are at 100% display scaling and grow with your Windows scaling.

## Desktop shortcut

To start the player from a desktop or taskbar icon:

1. Right-click `play.bat`, choose **Show more options**, then
   **Send to → Desktop (create shortcut)**.
2. Right-click the new shortcut, choose **Properties**, and set:
   - **Target:** `C:\Windows\System32\cmd.exe /c "<this folder>\play.bat"`.
     This is what lets Windows pin the shortcut to the taskbar.
   - **Run:** Minimized, so no console window flashes up.
   - **Change Icon…:** pick `icon.ico` from this folder.
3. To pin it, right-click the shortcut, choose **Show more options**, then
   **Pin to taskbar** or **Pin to Start**.

## Files

- `gif_player.py`: the player, with its settings at the top
- `play.bat`: starts the player without a console window
- `images/`: GIFs to play
- `icon.ico`: icon for a desktop shortcut
- `requirements.txt`: the one dependency, Pillow
