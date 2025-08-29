import ctypes
import subprocess
from ctypes import wintypes
import logging

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

HWND = wintypes.HWND
LPARAM = wintypes.LPARAM
LPVOID = wintypes.LPVOID
LONG = wintypes.LONG
UINT = wintypes.UINT
BOOL = wintypes.BOOL
WPARAM = wintypes.WPARAM

# Constants
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
LWA_ALPHA = 0x02
LWA_COLORKEY = 0x01

import ctypes
from ctypes import wintypes
import logging

user32 = ctypes.windll.user32

HWND = wintypes.HWND
LONG = wintypes.LONG
UINT = wintypes.UINT
BOOL = wintypes.BOOL

# 常量
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
LWA_ALPHA = 0x02
GWL_EXSTYLE = -20

# 热键常量
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# 指针尺寸 Get/SetWindowLong 绑定
if hasattr(user32, 'GetWindowLongPtrW'):
    GetWindowLongPtrW = user32.GetWindowLongPtrW
    GetWindowLongPtrW.argtypes = [HWND, ctypes.c_int]
    GetWindowLongPtrW.restype = ctypes.c_longlong
else:
    GetWindowLongPtrW = user32.GetWindowLongW

if hasattr(user32, 'SetWindowLongPtrW'):
    SetWindowLongPtrW = user32.SetWindowLongPtrW
    SetWindowLongPtrW.argtypes = [HWND, ctypes.c_int, ctypes.c_longlong]
    SetWindowLongPtrW.restype = ctypes.c_longlong
else:
    SetWindowLongPtrW = user32.SetWindowLongW

SetLayeredWindowAttributes = user32.SetLayeredWindowAttributes
SetLayeredWindowAttributes.argtypes = [HWND, wintypes.COLORREF, ctypes.c_ubyte, UINT]
SetLayeredWindowAttributes.restype = BOOL

RegisterHotKey = user32.RegisterHotKey
RegisterHotKey.argtypes = [HWND, ctypes.c_int, UINT, UINT]
RegisterHotKey.restype = BOOL

UnregisterHotKey = user32.UnregisterHotKey
UnregisterHotKey.argtypes = [HWND, ctypes.c_int]
UnregisterHotKey.restype = BOOL

logger = logging.getLogger(__name__)


def set_window_click_through(hwnd: int):
    ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    new = ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
    SetWindowLongPtrW(hwnd, GWL_EXSTYLE, new)
    SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
    logger.debug("set_window_click_through: hwnd=%s ex=0x%X -> 0x%X", hwnd, ex, new)


def set_window_layered(hwnd: int):
    ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    new = ex | WS_EX_LAYERED | WS_EX_TOOLWINDOW
    SetWindowLongPtrW(hwnd, GWL_EXSTYLE, new)
    SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
    logger.debug("set_window_layered: hwnd=%s ex=0x%X -> 0x%X", hwnd, ex, new)


def unset_window_layered(hwnd: int):
    ex = GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    new = ex & ~WS_EX_LAYERED & ~WS_EX_TOOLWINDOW
    SetWindowLongPtrW(hwnd, GWL_EXSTYLE, new)
    logger.debug("unset_window_layered: hwnd=%s ex=0x%X -> 0x%X", hwnd, ex, new)


def get_window_exstyle(hwnd: int):
    return GetWindowLongPtrW(hwnd, GWL_EXSTYLE)


def parse_hotkey_to_vk(hk: str):
    parts = [p.strip().lower() for p in hk.split("+") if p.strip()]
    mods = 0
    vk = 0
    for p in parts:
        if p in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif p == "alt":
            mods |= MOD_ALT
        elif p == "shift":
            mods |= MOD_SHIFT
        elif p in ("win", "meta"):
            mods |= MOD_WIN
        else:
            if len(p) == 1:
                vk = ord(p.upper())
            elif p.startswith('f') and p[1:].isdigit():
                fnum = int(p[1:])
                if 1 <= fnum <= 24:
                    vk = 0x70 + (fnum - 1)
            elif p == 'space':
                vk = 0x20
            elif p == 'enter':
                vk = 0x0D
            elif p == 'tab':
                vk = 0x09
            elif p in ('esc', 'escape'):
                vk = 0x1B
    return mods, vk
    SetParent(hwnd, workerw)

    ShowWindow(hwnd, SW_SHOW)
