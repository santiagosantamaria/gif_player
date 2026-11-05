"""Play GIFs on the Windows desktop with no window chrome.

Change the settings under "Settings", then double-click play.bat.

Every GIF in GIFS opens in its own window, and each one has the same
controls. Drag a picture to move it. Drag an edge or a corner to resize
it; width and height stay in the GIF's original proportion. Nothing is
drawn around the picture, and transparent pixels stay clear.
Right-click and choose Enable rotate, then hover the picture and drag the
round button in its top-left corner to rotate it. Double-click the
picture to stand it upright again.
Right-click a picture and choose Pause or Play to stop or restart its
animation, or Close to close it. Press Ctrl+Shift+Q to close them all.
"""

from __future__ import annotations

import ctypes
import math
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# GIFs to play, from the images folder next to this script. Each one opens
# in its own window. An entry is a file name, or a dict that gives that GIF
# its own settings in place of the ones below. For example:
#     {"file": "sonic_run.gif", "position": "bottom-right", "scale": 2,
#      "speed": 1.5, "rotate": True}
# GIFs without their own "position" are placed side by side around POSITION.
GIFS = [
    "sonic_wait.gif",
    "sonic_run.gif",
]

# 1.0 is the GIF's own frame timing. 2.0 plays twice as fast, 0.5 half speed.
SPEED = 1.0

# Size on first launch, relative to the file. 1.0 is the GIF's own pixel size.
# Dragging an edge afterwards keeps this proportion.
SCALE = 1.0

# "center", "top-left", "top-right", "bottom-left", "bottom-right",
# "top", "bottom", "left", "right", or an (x, y) pixel pair.
POSITION = "center"

# Gap from the screen edge for the named corner and side positions, and
# between GIFs that are placed side by side.
MARGIN = 24

# Keep the pictures above other windows.
ALWAYS_ON_TOP = True

# How thick the invisible resize edge is, at 96 DPI. The edge is not drawn;
# the pointer changes when it is over that strip.
EDGE_PX = 10

# Smallest side, in pixels, while resizing.
MIN_SIZE = 32

# nearest is the light option and keeps pixel art sharp.
# bilinear and lanczos are smoother for photos.
RESAMPLE = "nearest"

# Size of the rotate button that shows on hover, at 96 DPI.
ROTATE_BUTTON_PX = 22

# Whether the rotate button shows on hover when the player starts. Switch it
# any time with Enable rotate / Disable rotate in the right-click menu.
ROTATE_ENABLED = False

# While rotating, snap to upright, sideways or upside down when this many
# degrees away from it. 0 turns snapping off.
ROTATE_SNAP = 3

# Global shortcut that closes every GIF.
QUIT_MODIFIERS = ("ctrl", "shift")
QUIT_KEY = "q"


# ---------------------------------------------------------------------------
# Win32
# ---------------------------------------------------------------------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)

WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOREDIRECTIONBITMAP = 0x00200000
WS_EX_NOACTIVATE = 0x08000000
CS_DBLCLKS = 0x0008

SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_SETCURSOR = 0x0020
WM_MOUSEACTIVATE = 0x0021
WM_SYSCOMMAND = 0x0112
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_NULL = 0x0000
WM_CAPTURECHANGED = 0x0215
WM_NCHITTEST = 0x0084
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

HTCLIENT = 1
MA_NOACTIVATE = 3
SC_MINIMIZE = 0xF020
SC_MAXIMIZE = 0xF030
SC_CLOSE = 0xF060
CMD_CLOSE = 1
CMD_PAUSE = 2
CMD_ROTATE = 3
CMD_CLOSE_ALL = 4
MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
TPM_RIGHTBUTTON = 0x0002
TPM_NONOTIFY = 0x0080
TPM_RETURNCMD = 0x0100

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
BI_RGB = 0
DIB_RGB_COLORS = 0
PM_REMOVE = 0x0001
QS_ALLINPUT = 0x04FF
INFINITE = 0xFFFFFFFF
SPI_GETWORKAREA = 0x0030
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 1

IDC_SIZENWSE = 32642
IDC_SIZENESW = 32643
IDC_SIZEWE = 32644
IDC_SIZENS = 32645
IDC_SIZEALL = 32646
IDC_HAND = 32649

# While the pointer is over a picture's box but not its pixels (they let
# clicks through), check this often whether it has left, to hide the button.
HOVER_TIMER = 7
HOVER_POLL_MS = 250
HANDLE_INSET = 2

_MODIFIERS = {
    "alt": 0x0001,
    "ctrl": 0x0002,
    "control": 0x0002,
    "shift": 0x0004,
    "win": 0x0008,
}
_NAMED_KEYS = {"esc": 0x1B, "escape": 0x1B, "space": 0x20}
_FILTERS = {
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "lanczos": Image.Resampling.LANCZOS,
}
_CURSOR_IDS = {
    "nw": IDC_SIZENWSE,
    "se": IDC_SIZENWSE,
    "ne": IDC_SIZENESW,
    "sw": IDC_SIZENESW,
    "w": IDC_SIZEWE,
    "e": IDC_SIZEWE,
    "n": IDC_SIZENS,
    "s": IDC_SIZENS,
    "move": IDC_SIZEALL,
    "rotate": IDC_HAND,
}
# Pillow's rotate step has no lanczos; bicubic is the closest.
_ROTATE_FILTERS = {
    "nearest": Image.Resampling.NEAREST,
    "bilinear": Image.Resampling.BILINEAR,
    "lanczos": Image.Resampling.BICUBIC,
}
_GIF_OPTIONS = ("file", "position", "scale", "speed", "rotate")


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class Surface:
    def __init__(self) -> None:
        self.mem_dc = None
        self.hbmp = None
        self.old_bmp = None
        self.bits = None
        self.size = (0, 0)
        self.frame = -1

    def rebuild(self, width: int, height: int) -> None:
        self.release_bitmap()
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = BI_RGB
        info.bmiHeader.biSizeImage = width * height * 4
        bits = ctypes.c_void_p()
        screen = user32.GetDC(None)
        if not self.mem_dc:
            self.mem_dc = gdi32.CreateCompatibleDC(screen)
            _check(self.mem_dc, "CreateCompatibleDC")
        bitmap = gdi32.CreateDIBSection(
            screen, ctypes.byref(info), DIB_RGB_COLORS, ctypes.byref(bits), None, 0
        )
        user32.ReleaseDC(None, screen)
        _check(bitmap, "CreateDIBSection")
        self.old_bmp = gdi32.SelectObject(self.mem_dc, bitmap)
        self.hbmp = bitmap
        self.bits = bits
        self.size = (width, height)
        self.frame = -1

    def release_bitmap(self) -> None:
        if self.mem_dc and self.old_bmp:
            gdi32.SelectObject(self.mem_dc, self.old_bmp)
        if self.hbmp:
            gdi32.DeleteObject(self.hbmp)
        self.hbmp = None
        self.old_bmp = None
        self.bits = None
        self.size = (0, 0)
        self.frame = -1

    def close(self) -> None:
        self.release_bitmap()
        if self.mem_dc:
            gdi32.DeleteDC(self.mem_dc)
            self.mem_dc = None


class Drag:
    """Where a picture was when a move, resize or rotate drag started."""

    def __init__(self, player: Player, zone: str, start_x: int, start_y: int) -> None:
        self.zone = zone
        self.start_x = start_x
        self.start_y = start_y
        self.orig_x, self.orig_y = player.x, player.y
        self.orig_w, self.orig_h = player.w, player.h
        self.orig_sw, self.orig_sh = player.sw, player.sh
        self.orig_angle = player.angle
        self.center_x = player.x + player.w / 2
        self.center_y = player.y + player.h / 2
        self.grab_x = start_x - player.x
        self.grab_y = start_y - player.y


class App:
    """What all the GIF windows share."""

    def __init__(self) -> None:
        self.hinstance = None
        self.class_name = "DesktopGifPlayer"
        self.class_registered = False
        self.running = True
        self.error: BaseException | None = None
        self.cursors: dict[str, int] = {}
        self.hotkey = False
        self.players: list[Player] = []
        # Window handle -> (player, is its rotate button)
        self.windows: dict[int, tuple[Player, bool]] = {}


APP = App()
BLEND = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)


def _check(result, action: str):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error(), f"{action} failed")
    return result


def fail(text: str) -> None:
    user32.MessageBoxW(None, str(text), "GIF Player", 0x10)
    raise SystemExit(1)


def enable_dpi() -> None:
    try:
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        shcore.SetProcessDpiAwareness.restype = ctypes.HRESULT
        if shcore.SetProcessDpiAwareness(2) == 0:
            return
    except Exception:
        pass
    user32.SetProcessDPIAware()


def bind_win32() -> None:
    user32.DefWindowProcW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
    ]
    user32.DefWindowProcW.restype = LRESULT
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    user32.UnregisterClassW.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL
    user32.PostQuitMessage.argtypes = [ctypes.c_int]
    user32.MessageBoxW.argtypes = [
        wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT
    ]
    user32.MessageBoxW.restype = ctypes.c_int
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.LoadCursorW.restype = wintypes.HANDLE
    user32.SetCursor.argtypes = [wintypes.HANDLE]
    user32.SetCursor.restype = wintypes.HANDLE
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetCapture.argtypes = [wintypes.HWND]
    user32.SetCapture.restype = wintypes.HWND
    user32.ReleaseCapture.argtypes = []
    user32.ReleaseCapture.restype = wintypes.BOOL
    user32.ValidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p]
    user32.ValidateRect.restype = wintypes.BOOL
    user32.RegisterHotKey.argtypes = [
        wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT
    ]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL
    user32.PeekMessageW.argtypes = [
        ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT
    ]
    user32.PeekMessageW.restype = wintypes.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
    user32.TranslateMessage.restype = wintypes.BOOL
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
    user32.DispatchMessageW.restype = LRESULT
    user32.MsgWaitForMultipleObjects.argtypes = [
        wintypes.DWORD, ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, wintypes.DWORD
    ]
    user32.MsgWaitForMultipleObjects.restype = wintypes.DWORD
    user32.SystemParametersInfoW.argtypes = [
        wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT
    ]
    user32.SystemParametersInfoW.restype = wintypes.BOOL
    user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND, wintypes.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
        wintypes.HDC, ctypes.POINTER(POINT), wintypes.COLORREF,
        ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD,
    ]
    user32.UpdateLayeredWindow.restype = wintypes.BOOL
    user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    user32.GetDpiForWindow.restype = wintypes.UINT
    user32.CreatePopupMenu.argtypes = []
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.AppendMenuW.restype = wintypes.BOOL
    user32.TrackPopupMenu.argtypes = [
        wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, wintypes.HWND, ctypes.c_void_p,
    ]
    user32.TrackPopupMenu.restype = ctypes.c_uint
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.DestroyMenu.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostMessageW.restype = wintypes.BOOL
    user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
    user32.SetTimer.restype = ctypes.c_size_t
    user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
    user32.KillTimer.restype = wintypes.BOOL
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
    ]
    gdi32.CreateDIBSection.restype = wintypes.HBITMAP


# ---------------------------------------------------------------------------
# Loading and settings
# ---------------------------------------------------------------------------

def premultiply(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    red, green, blue, alpha = image.split()
    red = ImageChops.multiply(red, alpha)
    green = ImageChops.multiply(green, alpha)
    blue = ImageChops.multiply(blue, alpha)
    # UpdateLayeredWindow expects premultiplied BGRA. Labelling it "RGBa"
    # (premultiplied) stops Pillow premultiplying it a second time when it
    # smooths a resize or rotation.
    bgra = Image.merge("RGBA", (blue, green, red, alpha))
    return Image.frombytes("RGBa", bgra.size, bgra.tobytes())


def frame_delay_ms(raw_ms: int, speed: float) -> int:
    # GIF delays below 20ms are unspecified; browsers play those at 100ms.
    if raw_ms < 20:
        raw_ms = 100
    return max(10, int(round(raw_ms / speed)))


def load_gif(path: Path, speed: float) -> tuple[list[Image.Image], list[bytes], list[int], tuple[int, int]]:
    frames: list[Image.Image] = []
    delays: list[int] = []
    with Image.open(path) as image:
        count = int(getattr(image, "n_frames", 1) or 1)
        for index in range(count):
            image.seek(index)
            raw = int(image.info.get("duration", 0) or 0)
            frame = image.convert("RGBA").copy()
            frame.load()
            frames.append(premultiply(frame))
            delays.append(frame_delay_ms(raw, speed))
    if not frames:
        raise ValueError(f"No frames in {path.name}")
    native = frames[0].size
    return frames, [frame.tobytes() for frame in frames], delays, native


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check_settings() -> None:
    if RESAMPLE not in _FILTERS:
        fail("RESAMPLE must be nearest, bilinear, or lanczos.")


def gif_specs() -> list[dict]:
    """GIFS as a list of {"file", "position", "scale", "speed", "rotate"}."""
    entries = [GIFS] if isinstance(GIFS, (str, dict)) else list(GIFS or [])
    if not entries:
        fail("Add at least one GIF file name to GIFS.")
    specs = []
    for entry in entries:
        if isinstance(entry, str):
            entry = {"file": entry}
        if not isinstance(entry, dict):
            fail(f"Each GIFS entry must be a file name or a dict, not {entry!r}.")
        unknown = [key for key in entry if key not in _GIF_OPTIONS]
        if unknown:
            fail(f"Unknown GIFS option {unknown[0]!r}. Use: {', '.join(_GIF_OPTIONS)}.")
        name = str(entry.get("file") or "").strip()
        if not name:
            fail(f"This GIFS entry has no file name: {entry!r}")
        speed = entry.get("speed", SPEED)
        if not _is_number(speed) or speed <= 0:
            fail(f"{name}: speed must be a number greater than 0. Use 1 for the GIF's own timing.")
        scale = entry.get("scale", SCALE)
        if not _is_number(scale) or scale <= 0:
            fail(f"{name}: scale must be a number greater than 0.")
        specs.append({
            "file": name,
            "position": entry.get("position"),
            "scale": float(scale),
            "speed": float(speed),
            "rotate": bool(entry.get("rotate", ROTATE_ENABLED)),
        })
    return specs


def gif_path(name: str) -> Path:
    images = Path(__file__).resolve().parent / "images"
    path = images / name
    if path.is_file():
        return path
    found = sorted(item.name for item in images.glob("*.gif")) if images.is_dir() else []
    listing = "\n".join(found) if found else "(no .gif files yet)"
    fail(
        f"Could not find {name} in {images}.\n\n"
        f"Put the GIF in that folder and add its file name to GIFS.\n\n{listing}"
    )
    raise AssertionError


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def size_from_width(width: int, native_w: int, native_h: int, min_size: int) -> tuple[int, int]:
    width = max(min_size, int(round(width)))
    height = max(1, int(round(width * native_h / native_w)))
    if height < min_size:
        height = min_size
        width = max(1, int(round(height * native_w / native_h)))
    return width, height


def size_from_height(height: int, native_w: int, native_h: int, min_size: int) -> tuple[int, int]:
    height = max(min_size, int(round(height)))
    width = max(1, int(round(height * native_w / native_h)))
    if width < min_size:
        width = min_size
        height = max(1, int(round(width * native_h / native_w)))
    return width, height


def size_from_corner(raw_w: int, raw_h: int, native_w: int, native_h: int, min_size: int) -> tuple[int, int]:
    raw_w = max(1, int(round(raw_w)))
    raw_h = max(1, int(round(raw_h)))
    if raw_w * native_h >= raw_h * native_w:
        return size_from_width(raw_w, native_w, native_h, min_size)
    return size_from_height(raw_h, native_w, native_h, min_size)


def resized_rect(zone: str, orig: tuple[int, int, int, int], dx: int, dy: int,
                 native_w: int, native_h: int, min_size: int) -> tuple[int, int, int, int]:
    """Resize from the grabbed edge, keeping the opposite edge fixed."""
    x, y, width, height = orig
    if zone == "e":
        new_w, new_h = size_from_width(width + dx, native_w, native_h, min_size)
        return x, y, new_w, new_h
    if zone == "w":
        new_w, new_h = size_from_width(width - dx, native_w, native_h, min_size)
        return x + width - new_w, y, new_w, new_h
    if zone == "s":
        new_w, new_h = size_from_height(height + dy, native_w, native_h, min_size)
        return x, y, new_w, new_h
    if zone == "n":
        new_w, new_h = size_from_height(height - dy, native_w, native_h, min_size)
        return x, y + height - new_h, new_w, new_h
    if zone == "se":
        new_w, new_h = size_from_corner(width + dx, height + dy, native_w, native_h, min_size)
        return x, y, new_w, new_h
    if zone == "nw":
        new_w, new_h = size_from_corner(width - dx, height - dy, native_w, native_h, min_size)
        return x + width - new_w, y + height - new_h, new_w, new_h
    if zone == "ne":
        new_w, new_h = size_from_corner(width + dx, height - dy, native_w, native_h, min_size)
        return x, y + height - new_h, new_w, new_h
    if zone == "sw":
        new_w, new_h = size_from_corner(width - dx, height + dy, native_w, native_h, min_size)
        return x + width - new_w, y, new_w, new_h
    raise ValueError(f"Unknown resize edge: {zone}")


def hit_zone(px: int, py: int, width: int, height: int, edge: int) -> str:
    thickness = max(2, min(int(edge), width // 5, height // 5))
    west = px < thickness
    east = px >= width - thickness
    north = py < thickness
    south = py >= height - thickness
    if north and west:
        return "nw"
    if north and east:
        return "ne"
    if south and west:
        return "sw"
    if south and east:
        return "se"
    if west:
        return "w"
    if east:
        return "e"
    if north:
        return "n"
    if south:
        return "s"
    return "move"


def rotated_size(width: int, height: int, angle: float) -> tuple[int, int]:
    """The box a width x height picture needs once rotated by angle."""
    if angle % 180 == 0:
        return width, height
    if angle % 180 == 90:
        return height, width
    turn = math.radians(angle)
    cos, sin = abs(math.cos(turn)), abs(math.sin(turn))
    box_w = math.ceil(round(width * cos + height * sin, 6))
    box_h = math.ceil(round(width * sin + height * cos, 6))
    return max(1, box_w), max(1, box_h)


def work_area() -> RECT:
    area = RECT()
    if not user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(area), 0):
        area.right = user32.GetSystemMetrics(0)
        area.bottom = user32.GetSystemMetrics(1)
    return area


def initial_size(native_w: int, native_h: int, scale: float, area: RECT) -> tuple[int, int]:
    width = max(1, int(round(native_w * scale)))
    height = max(1, int(round(width * native_h / native_w)))
    max_w = max(1, int((area.right - area.left) * 0.9))
    max_h = max(1, int((area.bottom - area.top) * 0.9))
    if width > max_w or height > max_h:
        if width * max_h >= height * max_w:
            width = max_w
            height = max(1, int(round(width * native_h / native_w)))
        else:
            height = max_h
            width = max(1, int(round(height * native_w / native_h)))
    return width, height


def resolve_position(position, win_w: int, win_h: int, area: RECT) -> tuple[int, int]:
    if isinstance(position, (tuple, list)) and len(position) == 2:
        return int(position[0]), int(position[1])
    left, top, right, bottom = area.left, area.top, area.right, area.bottom
    center_x = left + (right - left - win_w) // 2
    center_y = top + (bottom - top - win_h) // 2
    anchors = {
        "center": (center_x, center_y),
        "top-left": (left + MARGIN, top + MARGIN),
        "top-right": (right - win_w - MARGIN, top + MARGIN),
        "bottom-left": (left + MARGIN, bottom - win_h - MARGIN),
        "bottom-right": (right - win_w - MARGIN, bottom - win_h - MARGIN),
        "top": (center_x, top + MARGIN),
        "bottom": (center_x, bottom - win_h - MARGIN),
        "left": (left + MARGIN, center_y),
        "right": (right - win_w - MARGIN, center_y),
    }
    name = str(position).strip().lower().replace("_", "-")
    if name not in anchors:
        names = ", ".join(anchors)
        fail(f"Position must be one of: {names}. Or set it to an (x, y) pair. Got {position!r}.")
    return anchors[name]


def lay_out(players: list[Player], area: RECT) -> None:
    """Place GIFs that have their own position there; line up the rest.

    The rest stand side by side on a shared baseline, MARGIN apart, wrapping
    to a new row when the screen is full. The whole group sits at POSITION.
    """
    lined_up = []
    for player in players:
        if player.position is None:
            lined_up.append(player)
        else:
            player.x, player.y = resolve_position(player.position, player.w, player.h, area)
    if not lined_up:
        return
    gap = MARGIN
    max_row_w = max(1, int((area.right - area.left) * 0.9))
    rows: list[list[Player]] = [[]]
    row_w = 0
    for player in lined_up:
        extra = player.w if not rows[-1] else gap + player.w
        if rows[-1] and row_w + extra > max_row_w:
            rows.append([player])
            row_w = player.w
        else:
            rows[-1].append(player)
            row_w += extra
    sizes = [(sum(p.w for p in row) + gap * (len(row) - 1), max(p.h for p in row)) for row in rows]
    group_w = max(width for width, _ in sizes)
    group_h = sum(height for _, height in sizes) + gap * (len(rows) - 1)
    group_x, group_y = resolve_position(POSITION, group_w, group_h, area)
    y = group_y
    for row, (width, height) in zip(rows, sizes):
        x = group_x + (group_w - width) // 2
        for player in row:
            player.x, player.y = x, y + height - player.h
            x += player.w + gap
        y += height + gap


# ---------------------------------------------------------------------------
# Rotate button image
# ---------------------------------------------------------------------------

def handle_icon(size: int) -> bytes:
    """A round dark button with a white clockwise arrow, as premultiplied BGRA."""
    big = size * 4                      # draw large, then shrink for smooth edges
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    ring = max(2, big // 14)
    draw.ellipse((1, 1, big - 2, big - 2), fill=(30, 30, 30, 215),
                 outline=(255, 255, 255, 230), width=ring)
    line = max(3, big // 10)
    pad = big * 0.28
    draw.arc((pad, pad, big - pad, big - pad), start=-50, end=200,
             fill=(255, 255, 255, 255), width=line)
    # Arrow head at the end of the arc, pointing clockwise.
    centre, radius = big / 2, (big - 2 * pad) / 2 - line / 2
    tip_angle = math.radians(200)
    px, py = centre + radius * math.cos(tip_angle), centre + radius * math.sin(tip_angle)
    tx, ty = -math.sin(tip_angle), math.cos(tip_angle)      # clockwise direction
    nx, ny = math.cos(tip_angle), math.sin(tip_angle)       # outward
    head = line * 1.7
    draw.polygon([
        (px + tx * head, py + ty * head),
        (px + nx * head, py + ny * head),
        (px - nx * head, py - ny * head),
    ], fill=(255, 255, 255, 255))
    small = image.resize((size, size), Image.Resampling.LANCZOS)
    return premultiply(small).tobytes()


# ---------------------------------------------------------------------------
# Shared window helpers
# ---------------------------------------------------------------------------

def cursor_pos() -> tuple[int, int]:
    point = POINT()
    _check(user32.GetCursorPos(ctypes.byref(point)), "GetCursorPos")
    return int(point.x), int(point.y)


def apply_cursor(zone: str) -> None:
    cursor = APP.cursors.get(zone) or APP.cursors.get("move")
    if cursor:
        user32.SetCursor(cursor)


def window_dpi(hwnd) -> int:
    try:
        return int(user32.GetDpiForWindow(hwnd) or 96)
    except Exception:
        return 96


def disable_window_chrome(hwnd) -> None:
    """Stop Windows 11 from drawing a border, shadow, or rounded corners."""
    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
    except OSError:
        return
    dwmapi.DwmSetWindowAttribute.argtypes = [
        wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
    ]
    dwmapi.DwmSetWindowAttribute.restype = ctypes.HRESULT

    def set_attr(attribute: int, value: int) -> None:
        data = wintypes.DWORD(value)
        dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(data), ctypes.sizeof(data))

    set_attr(2, 1)             # DWMWA_NCRENDERING_POLICY = disabled
    set_attr(33, 1)            # DWMWA_WINDOW_CORNER_PREFERENCE = do not round
    set_attr(34, 0xFFFFFFFE)   # DWMWA_BORDER_COLOR = none


def request_quit() -> None:
    APP.running = False
    user32.PostQuitMessage(0)


# ---------------------------------------------------------------------------
# One GIF window
# ---------------------------------------------------------------------------

class Player:
    """One GIF in its own window, with its own rotate button."""

    def __init__(self, spec: dict, area: RECT) -> None:
        self.name = spec["file"]
        self.position = spec["position"]
        self.frames, self.native_bytes, self.delays, native = load_gif(
            gif_path(self.name), spec["speed"]
        )
        self.native_w, self.native_h = native
        self.index = 0
        # The window box. When rotated it is larger than the picture.
        self.w, self.h = initial_size(self.native_w, self.native_h, spec["scale"], area)
        self.x = 0
        self.y = 0
        # The picture's own size before rotation, and the rotation in degrees
        # clockwise. 0 is upright.
        self.sw, self.sh = self.w, self.h
        self.angle = 0.0
        self.hwnd = None
        self.edge_px = EDGE_PX
        self.drag: Drag | None = None
        self.surface = Surface()
        self.cache_key: tuple[int, int, float] | None = None
        self.cache: dict[int, bytes] = {}
        self.presented: tuple[int, int, int, int, int] | None = None
        self.in_present = False
        self.next_frame = 0.0
        self.paused = False
        # Time the current frame still had on screen when Pause was chosen.
        self.pause_left = 0.0
        self.closing = False
        # The rotate button: a small window of its own, shown on hover while
        # rotating is enabled from the menu.
        self.rotate_enabled = spec["rotate"]
        self.handle_hwnd = None
        self.handle_surface = Surface()
        self.handle_size = ROTATE_BUTTON_PX
        self.handle_visible = False
        self.handle_pos: tuple[int, int] | None = None

    @property
    def animated(self) -> bool:
        return len(self.frames) > 1

    @property
    def playing(self) -> bool:
        return self.animated and not self.paused and not self.closing

    # -- windows ------------------------------------------------------------

    def create_windows(self) -> None:
        extended = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOREDIRECTIONBITMAP
        if ALWAYS_ON_TOP:
            extended |= WS_EX_TOPMOST
        title = f"GIF Player - {self.name}"
        hwnd = user32.CreateWindowExW(
            extended, APP.class_name, title, WS_POPUP,
            self.x, self.y, self.w, self.h, None, None, APP.hinstance, None,
        )
        if not hwnd:
            extended &= ~WS_EX_NOREDIRECTIONBITMAP
            hwnd = user32.CreateWindowExW(
                extended, APP.class_name, title, WS_POPUP,
                self.x, self.y, self.w, self.h, None, None, APP.hinstance, None,
            )
        self.hwnd = _check(hwnd, "CreateWindowExW")
        APP.windows[self.hwnd] = (self, False)
        dpi = window_dpi(self.hwnd)
        self.edge_px = max(2, int(round(EDGE_PX * dpi / 96)))
        disable_window_chrome(self.hwnd)
        self.create_handle(dpi)

    def create_handle(self, dpi: int) -> None:
        size = max(14, int(round(ROTATE_BUTTON_PX * dpi / 96)))
        extended = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if ALWAYS_ON_TOP:
            extended |= WS_EX_TOPMOST
        # Owned by the picture, so it always sits above it.
        hwnd = user32.CreateWindowExW(
            extended, APP.class_name, "GIF Player rotate", WS_POPUP,
            self.x, self.y, size, size, self.hwnd, None, APP.hinstance, None,
        )
        if not hwnd:
            return                      # no button; everything else still works
        surface = self.handle_surface
        surface.rebuild(size, size)
        ctypes.memmove(surface.bits, handle_icon(size), size * size * 4)
        origin, extent, source = POINT(self.x, self.y), SIZE(size, size), POINT(0, 0)
        if not user32.UpdateLayeredWindow(
            hwnd, None, ctypes.byref(origin), ctypes.byref(extent),
            surface.mem_dc, ctypes.byref(source), 0, ctypes.byref(BLEND), ULW_ALPHA,
        ):
            user32.DestroyWindow(hwnd)
            return
        disable_window_chrome(hwnd)
        self.handle_hwnd = hwnd
        self.handle_size = size
        APP.windows[hwnd] = (self, True)

    def show(self) -> None:
        self.present()
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        if ALWAYS_ON_TOP:
            user32.SetWindowPos(
                self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
        self.present()

    def request_close(self) -> None:
        """Close this GIF. The main loop tears it down after this message."""
        self.closing = True
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)

    def destroy(self) -> None:
        if self.hwnd:
            user32.KillTimer(self.hwnd, HOVER_TIMER)
            # Also destroys the rotate button, which it owns.
            user32.DestroyWindow(self.hwnd)
        APP.windows.pop(self.hwnd, None)
        APP.windows.pop(self.handle_hwnd, None)
        self.hwnd = None
        self.handle_hwnd = None
        self.surface.close()
        self.handle_surface.close()
        self.cache = {}

    # -- frames -------------------------------------------------------------

    def start_clock(self, now: float) -> None:
        self.next_frame = now + self.delays[self.index] / 1000

    def tick(self, now: float) -> None:
        if not self.playing or now < self.next_frame:
            return
        self.index = (self.index + 1) % len(self.frames)
        # Count from the deadline, not from when Windows woke us. Wake-ups
        # land on a ~15.6 ms tick, and counting from "now" made every frame
        # that much too long.
        self.next_frame += self.delays[self.index] / 1000
        if self.next_frame <= now:
            # A whole frame behind (menu open, PC asleep): restart the clock
            # instead of racing through frames to catch up.
            self.next_frame = now + self.delays[self.index] / 1000

    def render_frame(self, index: int, width: int, height: int) -> bytes:
        """Frame `index` at the current size and angle, as premultiplied BGRA."""
        frame = self.frames[index]
        sw, sh, angle = self.sw, self.sh, self.angle
        if angle == 0:
            if frame.size != (sw, sh):
                frame = frame.resize((sw, sh), _FILTERS[RESAMPLE])
            return frame.tobytes()
        # Scale and rotate in one step: map each pixel of the window box back
        # to the GIF frame around both centres.
        native_w, native_h = frame.size
        turn = math.radians(angle)
        cos, sin = round(math.cos(turn), 12), round(math.sin(turn), 12)
        step_x, step_y = native_w / sw, native_h / sh
        a, b = cos * step_x, sin * step_x
        d, e = -sin * step_y, cos * step_y
        c = native_w / 2 - a * width / 2 - b * height / 2
        f = native_h / 2 - d * width / 2 - e * height / 2
        if angle % 90 == 0 or RESAMPLE != "nearest":
            resample = _ROTATE_FILTERS[RESAMPLE]
        else:
            # Hard pixels look torn at a slant; smooth them.
            resample = Image.Resampling.BILINEAR
        rotated = frame.transform(
            (width, height), Image.Transform.AFFINE, (a, b, c, d, e, f), resample
        )
        return rotated.tobytes()

    def frame_pixels(self, index: int, width: int, height: int) -> bytes:
        if self.angle == 0 and (self.sw, self.sh) == (self.native_w, self.native_h):
            return self.native_bytes[index]
        reshaping = self.drag is not None and self.drag.zone != "move"
        if reshaping:
            return self.render_frame(index, width, height)
        frame_bytes = width * height * 4
        if frame_bytes * len(self.frames) > 32 * 1024 * 1024:
            return self.render_frame(index, width, height)
        key = (self.sw, self.sh, self.angle)
        if self.cache_key != key:
            self.cache_key = key
            self.cache = {}
        cached = self.cache.get(index)
        if cached is None:
            cached = self.render_frame(index, width, height)
            self.cache[index] = cached
        return cached

    def present(self) -> None:
        if self.in_present or not self.hwnd or self.closing:
            return
        self.in_present = True
        try:
            width, height = self.w, self.h
            if width < 1 or height < 1:
                return
            if self.surface.size != (width, height):
                self.surface.rebuild(width, height)
            if self.surface.frame != self.index:
                data = self.frame_pixels(self.index, width, height)
                ctypes.memmove(self.surface.bits, data, width * height * 4)
                self.surface.frame = self.index
            key = (self.index, self.x, self.y, width, height)
            if key == self.presented:
                return
            origin = POINT(self.x, self.y)
            size = SIZE(width, height)
            source = POINT(0, 0)
            ok = user32.UpdateLayeredWindow(
                self.hwnd, None, ctypes.byref(origin), ctypes.byref(size),
                self.surface.mem_dc, ctypes.byref(source), 0, ctypes.byref(BLEND), ULW_ALPHA,
            )
            if not ok:
                raise ctypes.WinError(ctypes.get_last_error(), "UpdateLayeredWindow failed")
            self.presented = key
            self.place_handle()
        except Exception as exc:
            APP.error = exc
            APP.running = False
        finally:
            self.in_present = False

    # -- dragging -----------------------------------------------------------

    def current_zone(self) -> str:
        if self.drag is not None:
            return self.drag.zone
        cx, cy = cursor_pos()
        return hit_zone(cx - self.x, cy - self.y, self.w, self.h, self.edge_px)

    def begin_drag(self, zone: str | None = None, capture=None) -> None:
        cx, cy = cursor_pos()
        if zone is None:
            zone = hit_zone(cx - self.x, cy - self.y, self.w, self.h, self.edge_px)
        self.drag = Drag(self, zone, cx, cy)
        user32.SetCapture(capture or self.hwnd)
        apply_cursor(zone)

    def set_angle(self, angle: float, center_x: float, center_y: float) -> None:
        """Rotate to `angle` degrees clockwise, keeping the centre still."""
        angle %= 360.0
        straight = round(angle / 90) * 90
        if abs(angle - straight) < ROTATE_SNAP:
            angle = float(straight % 360)
        if angle == self.angle:
            return
        self.angle = angle
        self.w, self.h = rotated_size(self.sw, self.sh, angle)
        self.x = int(round(center_x - self.w / 2))
        self.y = int(round(center_y - self.h / 2))
        self.surface.frame = -1
        self.presented = None

    def resize_drag(self, drag: Drag, cx: int, cy: int) -> None:
        upright = drag.orig_angle == 0
        # Upright, keep the GIF's own proportion exactly. Rotated, the box
        # keeps its own proportion while the picture inside scales.
        aspect = (self.native_w, self.native_h) if upright else (drag.orig_w, drag.orig_h)
        x, y, w, h = resized_rect(
            drag.zone,
            (drag.orig_x, drag.orig_y, drag.orig_w, drag.orig_h),
            cx - drag.start_x,
            cy - drag.start_y,
            aspect[0],
            aspect[1],
            MIN_SIZE,
        )
        if upright:
            self.sw, self.sh = w, h
        else:
            self.sw = max(1, int(round(drag.orig_sw * w / drag.orig_w)))
            self.sh = max(1, int(round(self.sw * self.native_h / self.native_w)))
            w, h = rotated_size(self.sw, self.sh, self.angle)
            # Keep the edge opposite the one being dragged where it was.
            x = drag.orig_x + drag.orig_w - w if "w" in drag.zone else drag.orig_x
            y = drag.orig_y + drag.orig_h - h if "n" in drag.zone else drag.orig_y
        self.x, self.y, self.w, self.h = x, y, w, h
        self.surface.frame = -1
        self.presented = None

    def update_drag(self) -> None:
        drag = self.drag
        if drag is None:
            apply_cursor(self.current_zone())
            return
        cx, cy = cursor_pos()
        if drag.zone == "move":
            self.x = cx - drag.grab_x
            self.y = cy - drag.grab_y
        elif drag.zone == "rotate":
            start = math.atan2(drag.start_y - drag.center_y, drag.start_x - drag.center_x)
            now = math.atan2(cy - drag.center_y, cx - drag.center_x)
            self.set_angle(drag.orig_angle + math.degrees(now - start), drag.center_x, drag.center_y)
        else:
            self.resize_drag(drag, cx, cy)
        apply_cursor(drag.zone)
        self.present()

    def end_drag(self) -> None:
        drag, self.drag = self.drag, None
        if drag is not None and drag.zone != "move":
            # Size or angle changed: frames are drawn again once, then cached.
            self.cache_key = None
            self.cache = {}
            self.surface.frame = -1
        user32.ReleaseCapture()
        self.present()
        self.place_handle()

    def reset_rotation(self) -> None:
        if self.angle == 0:
            return
        self.set_angle(0.0, self.x + self.w / 2, self.y + self.h / 2)
        self.present()

    # -- rotate button ------------------------------------------------------

    def place_handle(self) -> None:
        """Keep the button on the box's top-left corner, except mid-rotation."""
        if not self.handle_visible:
            return
        if self.drag is not None and self.drag.zone == "rotate":
            return                      # stay under the pointer while turning
        pos = (self.x + HANDLE_INSET, self.y + HANDLE_INSET)
        if pos != self.handle_pos:
            user32.SetWindowPos(
                self.handle_hwnd, None, pos[0], pos[1], 0, 0,
                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
            )
            self.handle_pos = pos

    def show_handle(self) -> None:
        if not self.handle_hwnd or not self.rotate_enabled:
            return
        if not self.handle_visible:
            self.handle_visible = True
            self.handle_pos = None
            self.place_handle()
            user32.ShowWindow(self.handle_hwnd, SW_SHOWNOACTIVATE)
        # Restarting the timer on every move means it only runs once the
        # pointer stops or leaves the picture's pixels.
        user32.SetTimer(self.hwnd, HOVER_TIMER, HOVER_POLL_MS, None)

    def hide_handle(self) -> None:
        user32.KillTimer(self.hwnd, HOVER_TIMER)
        if self.handle_visible:
            user32.ShowWindow(self.handle_hwnd, SW_HIDE)
            self.handle_visible = False

    def check_hover(self) -> None:
        if self.drag is not None:
            return
        x, y = cursor_pos()
        in_box = self.x <= x < self.x + self.w and self.y <= y < self.y + self.h
        hx, hy = self.handle_pos or (self.x, self.y)
        size = self.handle_size
        on_button = hx <= x < hx + size and hy <= y < hy + size
        if not (in_box or on_button):
            self.hide_handle()

    # -- menu ---------------------------------------------------------------

    def toggle_pause(self) -> None:
        now = time.perf_counter()
        if self.paused:
            # Pick up the current frame where it stopped, not from the start.
            self.next_frame = now + self.pause_left
            self.paused = False
        else:
            self.pause_left = max(0.0, self.next_frame - now)
            self.paused = True

    def toggle_rotate(self) -> None:
        self.rotate_enabled = not self.rotate_enabled
        if self.rotate_enabled:
            # The pointer is usually still on the picture after choosing it.
            self.show_handle()
        else:
            self.hide_handle()

    def show_menu(self) -> None:
        if self.drag is not None:
            self.end_drag()
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            if self.animated:
                label = "Play" if self.paused else "Pause"
                if not user32.AppendMenuW(menu, MF_STRING, CMD_PAUSE, label):
                    return
            if self.handle_hwnd:
                label = "Disable rotate" if self.rotate_enabled else "Enable rotate"
                if not user32.AppendMenuW(menu, MF_STRING, CMD_ROTATE, label):
                    return
            if self.animated or self.handle_hwnd:
                user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            if not user32.AppendMenuW(menu, MF_STRING, CMD_CLOSE, "Close"):
                return
            if len(APP.players) > 1:
                user32.AppendMenuW(menu, MF_STRING, CMD_CLOSE_ALL, "Close all")
            x, y = cursor_pos()
            # A popup menu only stays open when its owner is the foreground
            # window.
            user32.SetForegroundWindow(self.hwnd)
            command = user32.TrackPopupMenu(
                menu,
                TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                x, y, 0, self.hwnd, None,
            )
            user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
            if command == CMD_PAUSE:
                self.toggle_pause()
            elif command == CMD_ROTATE:
                self.toggle_rotate()
            elif command == CMD_CLOSE:
                self.request_close()
            elif command == CMD_CLOSE_ALL:
                request_quit()
        finally:
            user32.DestroyMenu(menu)

    # -- messages -----------------------------------------------------------

    def main_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_DESTROY:
            return 0
        if msg == WM_CLOSE:
            self.request_close()
            return 0
        if msg == WM_NCHITTEST:
            return HTCLIENT
        if msg == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if msg == WM_SETCURSOR:
            apply_cursor(self.current_zone())
            return 1
        if msg == WM_LBUTTONDOWN:
            self.begin_drag()
            return 0
        if msg == WM_LBUTTONUP:
            self.end_drag()
            return 0
        if msg == WM_LBUTTONDBLCLK:
            self.reset_rotation()
            return 0
        if msg == WM_RBUTTONUP:
            self.show_menu()
            return 0
        if msg == WM_MOUSEMOVE:
            self.show_handle()
            self.update_drag()
            return 0
        if msg == WM_TIMER and wparam == HOVER_TIMER:
            self.check_hover()
            return 0
        if msg == WM_CAPTURECHANGED:
            self.drag = None
            return 0
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_PAINT:
            user32.ValidateRect(hwnd, None)
            return 0
        if msg == WM_SYSCOMMAND:
            command = int(wparam) & 0xFFF0
            if command in (SC_MINIMIZE, SC_MAXIMIZE):
                return 0
            if command == SC_CLOSE:
                self.request_close()
                return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def handle_proc(self, hwnd, msg, wparam, lparam):
        """Messages for the rotate button window."""
        if msg in (WM_CLOSE, WM_DESTROY):
            return 0                    # it goes away with the picture
        if msg == WM_NCHITTEST:
            return HTCLIENT
        if msg == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if msg == WM_SETCURSOR:
            apply_cursor(self.drag.zone if self.drag is not None else "rotate")
            return 1
        if msg == WM_LBUTTONDOWN:
            self.begin_drag("rotate", capture=hwnd)
            return 0
        if msg == WM_LBUTTONUP:
            self.end_drag()
            return 0
        if msg == WM_LBUTTONDBLCLK:
            self.reset_rotation()
            return 0
        if msg == WM_RBUTTONUP:
            self.show_menu()
            return 0
        if msg == WM_MOUSEMOVE:
            self.show_handle()
            if self.drag is not None:
                self.update_drag()
            else:
                apply_cursor("rotate")
            return 0
        if msg == WM_CAPTURECHANGED:
            self.drag = None
            return 0
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_PAINT:
            user32.ValidateRect(hwnd, None)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


@WNDPROC
def wnd_proc(hwnd, msg, wparam, lparam):
    try:
        entry = APP.windows.get(hwnd)
        if entry is None:
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        player, is_button = entry
        if is_button:
            return player.handle_proc(hwnd, msg, wparam, lparam)
        return player.main_proc(hwnd, msg, wparam, lparam)
    except Exception as exc:
        APP.error = exc
        APP.running = False
        user32.PostQuitMessage(1)
        return 0


# ---------------------------------------------------------------------------
# Start, loop, stop
# ---------------------------------------------------------------------------

def register_class() -> None:
    APP.hinstance = kernel32.GetModuleHandleW(None)
    for zone, cursor_id in _CURSOR_IDS.items():
        APP.cursors[zone] = user32.LoadCursorW(None, ctypes.c_void_p(cursor_id))
    window_class = WNDCLASSW()
    window_class.style = CS_DBLCLKS
    window_class.lpfnWndProc = wnd_proc
    window_class.hInstance = APP.hinstance
    window_class.hCursor = APP.cursors.get("move")
    window_class.lpszClassName = APP.class_name
    atom = user32.RegisterClassW(ctypes.byref(window_class))
    if not atom and ctypes.get_last_error() not in (0, 1410):
        raise ctypes.WinError(ctypes.get_last_error(), "RegisterClassW failed")
    APP.class_registered = True


def register_hotkey() -> None:
    modifiers = MOD_NOREPEAT
    for name in QUIT_MODIFIERS:
        key = str(name).lower()
        if key not in _MODIFIERS:
            fail("QUIT_MODIFIERS can contain ctrl, shift, alt, and win.")
        modifiers |= _MODIFIERS[key]
    quit_key = str(QUIT_KEY).lower()
    virtual_key = _NAMED_KEYS.get(quit_key, ord(quit_key.upper()) if len(quit_key) == 1 else 0)
    if not virtual_key:
        fail("QUIT_KEY must be a single character, esc, or space.")
    # Registered to the thread, not a window, so it keeps working whichever
    # GIFs have been closed.
    APP.hotkey = bool(user32.RegisterHotKey(None, HOTKEY_ID, modifiers, virtual_key))
    if not APP.hotkey:
        user32.MessageBoxW(
            None,
            "Ctrl+Shift+Q is already used by another program.\n"
            "Right-click a GIF and choose Close all to close the player.",
            "GIF Player",
            0x30,
        )


def pump() -> None:
    message = MSG()
    while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
        if message.message == WM_QUIT:
            APP.running = False
            return
        if message.message == WM_HOTKEY and not message.hwnd:
            request_quit()
            continue
        user32.TranslateMessage(ctypes.byref(message))
        user32.DispatchMessageW(ctypes.byref(message))


def reap_closed() -> None:
    for player in [p for p in APP.players if p.closing]:
        player.destroy()
        APP.players.remove(player)
    if not APP.players:
        APP.running = False


def run() -> None:
    for player in APP.players:
        player.show()
    now = time.perf_counter()
    for player in APP.players:
        player.start_clock(now)
    while APP.running:
        now = time.perf_counter()
        wake = None
        for player in APP.players:
            player.tick(now)
            player.present()
            if player.playing:
                wake = player.next_frame if wake is None else min(wake, player.next_frame)
        if not APP.running:
            break
        if wake is None:
            # Every GIF paused or still: sleep until a click, the hotkey or Close.
            wait_ms = INFINITE
        else:
            remaining = wake - time.perf_counter()
            if remaining <= 0:
                continue
            # Round up so the wait never ends just before the deadline and
            # needs a second wake-up for the same frame.
            wait_ms = min(1000, max(1, math.ceil(remaining * 1000)))
        user32.MsgWaitForMultipleObjects(0, None, False, wait_ms, QS_ALLINPUT)
        pump()
        reap_closed()


def cleanup() -> None:
    if APP.hotkey:
        user32.UnregisterHotKey(None, HOTKEY_ID)
        APP.hotkey = False
    for player in APP.players:
        player.destroy()
    APP.players = []
    if APP.class_registered:
        user32.UnregisterClassW(APP.class_name, APP.hinstance)
        APP.class_registered = False


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This player runs on Windows.")
    enable_dpi()
    bind_win32()
    check_settings()
    specs = gif_specs()
    area = work_area()
    APP.players = [Player(spec, area) for spec in specs]
    lay_out(APP.players, area)
    try:
        register_class()
        for player in APP.players:
            player.create_windows()
        register_hotkey()
        run()
    finally:
        cleanup()
    if APP.error:
        fail(APP.error)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(None, str(exc), "GIF Player", 0x10)
        raise
