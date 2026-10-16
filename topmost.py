"""Keep both orb windows above overlapping apps without activating either one."""
import ctypes
from ctypes import wintypes as W

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication


class TopmostGuard(QObject):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        self.api.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int, W.UINT]
        self.api.SetWindowPos.restype = W.BOOL
        self.api.GetWindow.argtypes = [W.HWND, W.UINT]
        self.api.GetWindow.restype = W.HWND
        self.api.GetWindowLongPtrW.argtypes = [W.HWND, ctypes.c_int]
        self.api.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.api.IsWindowVisible.argtypes = [W.HWND]
        self.api.IsIconic.argtypes = [W.HWND]
        self.api.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
        self.timer = QTimer(self)
        self.timer.setInterval(600)
        self.timer.timeout.connect(self.ensure)

    def handles(self):
        handles = [int(self.owner.winId())]
        renderer = self.owner._renderer
        if renderer is not None and renderer.view.isVisible():
            handles.append(int(renderer.view.winId()))
        return handles

    def needs_raise(self, handles):
        if any(not self.api.GetWindowLongPtrW(hwnd, -20) & 0x8 for hwnd in handles):
            return True
        target = W.RECT()
        if not self.api.GetWindowRect(handles[-1], ctypes.byref(target)):
            return False
        # Inspect only windows above the rendered orb. Usually this is empty;
        # no native reordering occurs while the orb is already unobstructed.
        above = self.api.GetWindow(handles[-1], 3)  # GW_HWNDPREV
        visited = set()
        while above and above not in visited:
            visited.add(above)
            if above not in handles and self.api.IsWindowVisible(above) and not self.api.IsIconic(above):
                other = W.RECT()
                if self.api.GetWindowRect(above, ctypes.byref(other)) and (
                    other.left < target.right and other.right > target.left and
                    other.top < target.bottom and other.bottom > target.top
                ):
                    return True
            above = self.api.GetWindow(above, 3)
        return False

    def ensure(self, force=False):
        if not self.owner.isVisible() or QApplication.activePopupWidget() is not None:
            return
        handles = self.handles()
        if force or self.needs_raise(handles):
            # HWND_TOPMOST; preserve size, position, and the user's typing focus.
            for hwnd in handles:
                self.api.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0013)

    def start(self):
        self.ensure(True)
        self.timer.start()

    def stop(self):
        self.timer.stop()
