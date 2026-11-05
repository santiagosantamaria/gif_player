"""Play a GIF on the Windows desktop with no window chrome.

Change the settings under "Settings", then double-click play.bat.

Drag anywhere inside the picture to move it. Drag an edge or a corner
to resize it; width and height stay in the GIF's original proportion.
Nothing is drawn around the picture, and transparent pixels stay clear.
Right-click the picture and choose Pause or Play to stop or restart
the animation. Choose Close, or press Ctrl+Shift+Q, to quit.
"""

from __future__ import annotations

import ctypes
import math
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import Image, ImageChops


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

# File name inside the images folder next to this script.
GIF_NAME = "sonic_wait.gif"

# 1.0 is the GIF's own frame timing. 2.0 plays twice as fast, 0.5 half speed.
SPEED = 1.0

# Size on first launch, relative to the file. 1.0 is the GIF's own pixel size.
# Dragging an edge afterwards keeps this proportion.
SCALE = 1.0

# "center", "top-left", "top-right", "bottom-left", "bottom-right",
# "top", "bottom", "left", "right", or an (x, y) pixel pair.
POSITION = "center"

# Gap from the screen edge for the named corner and side positions.
MARGIN = 24

# Keep the picture above other windows.
ALWAYS_ON_TOP = True

# How thick the invisible resize edge is, at 96 DPI. The edge is not drawn;
# the pointer changes when it is over that strip.
EDGE_PX = 10

# Smallest side, in pixels, while resizing.
MIN_SIZE = 32

# nearest is the light option and keeps pixel art sharp.
# bilinear and lanczos are smoother for photos.
RESAMPLE = "nearest"

# Global quit shortcut.
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

SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
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
WM_RBUTTONUP = 0x0205
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

IDC_SIZENWSE = 32642
IDC_SIZENESW = 32643
IDC_SIZEWE = 32644
IDC_SIZENS = 32645
IDC_SIZEALL = 32646

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
}


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
    def __init__(self, zone, start_x, start_y, orig_x, orig_y, orig_w, orig_h, grab_x, grab_y):
        self.zone = zone
        self.start_x = start_x
        self.start_y = start_y
        self.orig_x = orig_x
        self.orig_y = orig_y
        self.orig_w = orig_w
        self.orig_h = orig_h
        self.grab_x = grab_x
        self.grab_y = grab_y


class App:
    def __init__(self) -> None:
        self.hwnd = None
        self.hinstance = None
        self.class_name = "DesktopGifPlayer"
        self.running = True
        self.frames: list[Image.Image] = []
        self.native_bytes: list[bytes] = []
        self.delays: list[int] = []
        self.index = 0
        self.native_w = 1
        self.native_h = 1
        self.x = 0
        self.y = 0
        self.w = 1
        self.h = 1
        self.drag: Drag | None = None
        self.surface = Surface()
        self.cache_size: tuple[int, int] | None = None
        self.cache: dict[int, bytes] = {}
        self.presented: tuple[int, int, int, int] | None = None
        self.in_present = False
        self.error: BaseException | None = None
        self.cursors: dict[str, int] = {}
        self.hotkey = False
        self.edge_px = EDGE_PX
        self.next_frame = 0.0
        self.paused = False
        # Time the current frame still had on screen when Pause was chosen.
        self.pause_left = 0.0


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


def premultiply(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    red, green, blue, alpha = image.split()
    red = ImageChops.multiply(red, alpha)
    green = ImageChops.multiply(green, alpha)
    blue = ImageChops.multiply(blue, alpha)
    # UpdateLayeredWindow expects premultiplied BGRA.
    return Image.merge("RGBA", (blue, green, red, alpha))


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
        fail(f"POSITION must be one of: {names}. Or set it to an (x, y) pair.")
    return anchors[name]


def check_settings() -> None:
    if not isinstance(SPEED, (int, float)) or isinstance(SPEED, bool) or SPEED <= 0:
        fail("SPEED must be a number greater than 0. Use 1 for the GIF's own timing.")
    if not isinstance(SCALE, (int, float)) or isinstance(SCALE, bool) or SCALE <= 0:
        fail("SCALE must be a number greater than 0.")
    if RESAMPLE not in _FILTERS:
        fail("RESAMPLE must be nearest, bilinear, or lanczos.")
    if not GIF_NAME or not str(GIF_NAME).strip():
        fail("Set GIF_NAME to a file inside the images folder.")


def gif_path() -> Path:
    images = Path(__file__).resolve().parent / "images"
    path = images / GIF_NAME
    if path.is_file():
        return path
    found = sorted(item.name for item in images.glob("*.gif")) if images.is_dir() else []
    listing = "\n".join(found) if found else "(no .gif files yet)"
    fail(
        f"Could not find {GIF_NAME} in {images}.\n\n"
        f"Put the GIF in that folder and set GIF_NAME to its file name.\n\n{listing}"
    )
    raise AssertionError


def cursor_pos() -> tuple[int, int]:
    point = POINT()
    _check(user32.GetCursorPos(ctypes.byref(point)), "GetCursorPos")
    return int(point.x), int(point.y)


def apply_cursor(zone: str) -> None:
    cursor = APP.cursors.get(zone) or APP.cursors.get("move")
    if cursor:
        user32.SetCursor(cursor)


def current_zone() -> str:
    if APP.drag is not None:
        return APP.drag.zone
    cx, cy = cursor_pos()
    return hit_zone(cx - APP.x, cy - APP.y, APP.w, APP.h, APP.edge_px)


def scale_frame(index: int, width: int, height: int) -> bytes:
    frame = APP.frames[index]
    if frame.size != (width, height):
        frame = frame.resize((width, height), _FILTERS[RESAMPLE])
    return frame.tobytes()


def frame_pixels(index: int, width: int, height: int) -> bytes:
    if (width, height) == (APP.native_w, APP.native_h):
        return APP.native_bytes[index]
    resizing = APP.drag is not None and APP.drag.zone != "move"
    if resizing:
        return scale_frame(index, width, height)
    frame_bytes = width * height * 4
    if frame_bytes * len(APP.frames) > 32 * 1024 * 1024:
        return scale_frame(index, width, height)
    if APP.cache_size != (width, height):
        APP.cache_size = (width, height)
        APP.cache = {}
    cached = APP.cache.get(index)
    if cached is None:
        cached = scale_frame(index, width, height)
        APP.cache[index] = cached
    return cached


def present() -> None:
    if APP.in_present or not APP.hwnd:
        return
    APP.in_present = True
    try:
        width, height = APP.w, APP.h
        if width < 1 or height < 1:
            return
        if APP.surface.size != (width, height):
            APP.surface.rebuild(width, height)
        if APP.surface.frame != APP.index:
            data = frame_pixels(APP.index, width, height)
            ctypes.memmove(APP.surface.bits, data, width * height * 4)
            APP.surface.frame = APP.index
        key = (APP.index, APP.x, APP.y, width, height)
        if key == APP.presented:
            return
        origin = POINT(APP.x, APP.y)
        size = SIZE(width, height)
        source = POINT(0, 0)
        ok = user32.UpdateLayeredWindow(
            APP.hwnd, None, ctypes.byref(origin), ctypes.byref(size),
            APP.surface.mem_dc, ctypes.byref(source), 0, ctypes.byref(BLEND), ULW_ALPHA,
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error(), "UpdateLayeredWindow failed")
        APP.presented = key
    except Exception as exc:
        APP.error = exc
        APP.running = False
    finally:
        APP.in_present = False


def begin_drag() -> None:
    cx, cy = cursor_pos()
    zone = hit_zone(cx - APP.x, cy - APP.y, APP.w, APP.h, APP.edge_px)
    APP.drag = Drag(zone, cx, cy, APP.x, APP.y, APP.w, APP.h, cx - APP.x, cy - APP.y)
    user32.SetCapture(APP.hwnd)
    apply_cursor(zone)


def update_drag() -> None:
    drag = APP.drag
    if drag is None:
        apply_cursor(current_zone())
        return
    cx, cy = cursor_pos()
    if drag.zone == "move":
        APP.x = cx - drag.grab_x
        APP.y = cy - drag.grab_y
    else:
        APP.x, APP.y, APP.w, APP.h = resized_rect(
            drag.zone,
            (drag.orig_x, drag.orig_y, drag.orig_w, drag.orig_h),
            cx - drag.start_x,
            cy - drag.start_y,
            APP.native_w,
            APP.native_h,
            MIN_SIZE,
        )
        APP.presented = None
    apply_cursor(drag.zone)
    present()


def end_drag() -> None:
    APP.drag = None
    APP.cache_size = None
    APP.cache = {}
    APP.surface.frame = -1
    user32.ReleaseCapture()
    present()


def request_quit() -> None:
    APP.running = False
    user32.PostQuitMessage(0)


def toggle_pause() -> None:
    now = time.perf_counter()
    if APP.paused:
        # Pick up the current frame where it stopped, not from the start.
        APP.next_frame = now + APP.pause_left
        APP.paused = False
    else:
        APP.pause_left = max(0.0, APP.next_frame - now)
        APP.paused = True


def show_menu(hwnd) -> None:
    if APP.drag is not None:
        end_drag()
    menu = user32.CreatePopupMenu()
    if not menu:
        return
    try:
        if len(APP.frames) > 1:
            label = "Play" if APP.paused else "Pause"
            if not user32.AppendMenuW(menu, MF_STRING, CMD_PAUSE, label):
                return
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        if not user32.AppendMenuW(menu, MF_STRING, CMD_CLOSE, "Close"):
            return
        x, y = cursor_pos()
        # A popup menu only stays open when its owner is the foreground window.
        user32.SetForegroundWindow(hwnd)
        command = user32.TrackPopupMenu(
            menu,
            TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
            x, y, 0, hwnd, None,
        )
        user32.PostMessageW(hwnd, WM_NULL, 0, 0)
        if command == CMD_PAUSE:
            toggle_pause()
        elif command == CMD_CLOSE:
            request_quit()
    finally:
        user32.DestroyMenu(menu)


@WNDPROC
def wnd_proc(hwnd, msg, wparam, lparam):
    try:
        if msg in (WM_DESTROY, WM_CLOSE):
            APP.running = False
            if msg == WM_CLOSE:
                user32.PostQuitMessage(0)
            return 0
        if msg == WM_HOTKEY:
            request_quit()
            return 0
        if msg == WM_NCHITTEST:
            return HTCLIENT
        if msg == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if msg == WM_SETCURSOR:
            apply_cursor(current_zone())
            return 1
        if msg == WM_LBUTTONDOWN:
            begin_drag()
            return 0
        if msg == WM_LBUTTONUP:
            end_drag()
            return 0
        if msg == WM_RBUTTONUP:
            show_menu(hwnd)
            return 0
        if msg == WM_MOUSEMOVE:
            update_drag()
            return 0
        if msg == WM_CAPTURECHANGED:
            APP.drag = None
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
                request_quit()
                return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
    except Exception as exc:
        APP.error = exc
        APP.running = False
        user32.PostQuitMessage(1)
        return 0


def create_window() -> None:
    APP.hinstance = kernel32.GetModuleHandleW(None)
    for zone, cursor_id in _CURSOR_IDS.items():
        APP.cursors[zone] = user32.LoadCursorW(None, ctypes.c_void_p(cursor_id))

    window_class = WNDCLASSW()
    window_class.lpfnWndProc = wnd_proc
    window_class.hInstance = APP.hinstance
    window_class.hCursor = APP.cursors.get("move")
    window_class.lpszClassName = APP.class_name
    atom = user32.RegisterClassW(ctypes.byref(window_class))
    if not atom and ctypes.get_last_error() not in (0, 1410):
        raise ctypes.WinError(ctypes.get_last_error(), "RegisterClassW failed")

    extended = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOREDIRECTIONBITMAP
    if ALWAYS_ON_TOP:
        extended |= WS_EX_TOPMOST
    hwnd = user32.CreateWindowExW(
        extended, APP.class_name, "GIF Player", WS_POPUP,
        APP.x, APP.y, APP.w, APP.h, None, None, APP.hinstance, None,
    )
    if not hwnd:
        extended &= ~WS_EX_NOREDIRECTIONBITMAP
        hwnd = user32.CreateWindowExW(
            extended, APP.class_name, "GIF Player", WS_POPUP,
            APP.x, APP.y, APP.w, APP.h, None, None, APP.hinstance, None,
        )
    APP.hwnd = _check(hwnd, "CreateWindowExW")
    try:
        dpi = int(user32.GetDpiForWindow(APP.hwnd) or 96)
    except Exception:
        dpi = 96
    APP.edge_px = max(2, int(round(EDGE_PX * dpi / 96)))

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
    APP.hotkey = bool(user32.RegisterHotKey(APP.hwnd, 1, modifiers, virtual_key))
    if not APP.hotkey:
        user32.MessageBoxW(
            None,
            "Ctrl+Shift+Q is already used by another program.\n"
            "End pythonw.exe in Task Manager to close the player.",
            "GIF Player",
            0x30,
        )
    disable_window_chrome(APP.hwnd)


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


def pump() -> None:
    message = MSG()
    while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
        if message.message == WM_QUIT:
            APP.running = False
            return
        user32.TranslateMessage(ctypes.byref(message))
        user32.DispatchMessageW(ctypes.byref(message))


def run() -> None:
    present()
    user32.ShowWindow(APP.hwnd, SW_SHOWNOACTIVATE)
    if ALWAYS_ON_TOP:
        user32.SetWindowPos(
            APP.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    present()
    APP.next_frame = time.perf_counter() + APP.delays[APP.index] / 1000
    animated = len(APP.frames) > 1
    while APP.running:
        playing = animated and not APP.paused
        now = time.perf_counter()
        if playing and now >= APP.next_frame:
            APP.index = (APP.index + 1) % len(APP.frames)
            # Count from the deadline, not from when Windows woke us. Wake-ups
            # land on a ~15.6 ms tick, and counting from "now" made every frame
            # that much too long.
            APP.next_frame += APP.delays[APP.index] / 1000
            if APP.next_frame <= now:
                # A whole frame behind (menu open, PC asleep): restart the clock
                # instead of racing through frames to catch up.
                APP.next_frame = now + APP.delays[APP.index] / 1000
        present()
        if not APP.running:
            break
        if playing:
            remaining = APP.next_frame - time.perf_counter()
            if remaining <= 0:
                continue
            # Round up so the wait never ends just before the deadline and
            # needs a second wake-up for the same frame.
            wait_ms = min(1000, max(1, math.ceil(remaining * 1000)))
        else:
            # Paused or a still image: sleep until a click, the hotkey or Close.
            wait_ms = INFINITE
        user32.MsgWaitForMultipleObjects(0, None, False, wait_ms, QS_ALLINPUT)
        pump()


def cleanup() -> None:
    if APP.hotkey and APP.hwnd:
        user32.UnregisterHotKey(APP.hwnd, 1)
    APP.surface.close()
    if APP.hwnd:
        user32.DestroyWindow(APP.hwnd)
        APP.hwnd = None
    if APP.hinstance:
        user32.UnregisterClassW(APP.class_name, APP.hinstance)


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This player runs on Windows.")
    enable_dpi()
    bind_win32()
    check_settings()
    frames, native_bytes, delays, native = load_gif(gif_path(), float(SPEED))
    APP.frames = frames
    APP.native_bytes = native_bytes
    APP.delays = delays
    APP.native_w, APP.native_h = native
    area = work_area()
    APP.w, APP.h = initial_size(APP.native_w, APP.native_h, float(SCALE), area)
    APP.x, APP.y = resolve_position(POSITION, APP.w, APP.h, area)
    create_window()
    try:
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
