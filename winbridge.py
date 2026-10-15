"""Small Win32 surface: global hotkeys, target verification and paste."""
import ctypes
from ctypes import wintypes as W

user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.GetForegroundWindow.restype = W.HWND
user32.IsWindow.argtypes = [W.HWND]
user32.IsWindow.restype = W.BOOL
user32.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
user32.RegisterHotKey.argtypes = [W.HWND, ctypes.c_int, W.UINT, W.UINT]
user32.UnregisterHotKey.argtypes = [W.HWND, ctypes.c_int]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', W.WORD), ('wScan', W.WORD), ('dwFlags', W.DWORD),
                ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('mouseData', W.DWORD),
                ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class INPUT_UNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('type', W.DWORD), ('data', INPUT_UNION)]


user32.SendInput.argtypes = [W.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = W.UINT


def foreground():
    return user32.GetForegroundWindow()


def own_window(hwnd):
    import os
    pid = W.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


def modifiers_down():
    return any(user32.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C))


def valid_paste_target(hwnd):
    return bool(hwnd and foreground()==hwnd and not own_window(hwnd) and user32.IsWindow(hwnd))


def paste_shortcut(hwnd):
    # Recheck after clipboard preparation: the user may have changed focus.
    if not valid_paste_target(hwnd):
        return False
    events = (INPUT * 4)()
    for event, vk, flags in zip(events, (0x11, 0x56, 0x56, 0x11), (0, 0, 2, 2)):
        event.type = 1
        event.ki = KEYBDINPUT(vk, 0, flags, 0, 0)
    return user32.SendInput(4, events, ctypes.sizeof(INPUT)) == 4
