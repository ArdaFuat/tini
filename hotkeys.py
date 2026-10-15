"""Global shortcuts on a dedicated Win32 message loop, including tool-only apps."""
import ctypes
import logging
import threading
from ctypes import wintypes as W


class Hotkeys:
    TOGGLE, CANCEL, EXIT = 0x6211, 0x6212, 0x6213
    ARM_CANCEL = 0x8001

    def __init__(self, events):
        self.events = events
        self.ok = False
        self.thread_id = None
        self.started = threading.Event()
        self.thread = threading.Thread(target=self.run, name='SesHotkeys', daemon=True)
        self.thread.start()
        self.started.wait(1)

    def run(self):
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentThreadId.restype = W.DWORD
        self.api.RegisterHotKey.argtypes = [W.HWND,ctypes.c_int,W.UINT,W.UINT]
        self.api.UnregisterHotKey.argtypes = [W.HWND,ctypes.c_int]
        self.api.GetMessageW.argtypes = [ctypes.POINTER(W.MSG),W.HWND,W.UINT,W.UINT]
        self.api.GetMessageW.restype = W.BOOL
        self.api.PeekMessageW.argtypes = [ctypes.POINTER(W.MSG),W.HWND,W.UINT,W.UINT,W.UINT]
        self.api.PostThreadMessageW.argtypes = [W.DWORD,W.UINT,W.WPARAM,W.LPARAM]
        message = W.MSG()
        self.api.PeekMessageW(ctypes.byref(message),None,0,0,0)
        self.thread_id = kernel.GetCurrentThreadId()
        self.ok = bool(self.api.RegisterHotKey(None,self.TOGGLE,0x4003,0x20))
        logging.info('Global dictation hotkey registered=%s error=%s',self.ok,ctypes.get_last_error())
        self.exit_ok=bool(self.api.RegisterHotKey(None,self.EXIT,0x4003,ord('Q')))
        logging.info('Global exit hotkey registered=%s error=%s',self.exit_ok,ctypes.get_last_error())
        self.started.set()
        try:
            while self.api.GetMessageW(ctypes.byref(message),None,0,0) > 0:
                if message.message == self.ARM_CANCEL:
                    self.api.UnregisterHotKey(None,self.CANCEL)
                    if message.wParam:
                        self.api.RegisterHotKey(None,self.CANCEL,0x4000,0x1B)
                elif message.message == 0x0312:
                    logging.info('Hotkey received id=%s',message.wParam)
                    if message.wParam == self.TOGGLE:
                        self.events.hotkey.emit()
                    elif message.wParam == self.CANCEL:
                        self.events.cancel.emit()
                    elif message.wParam == self.EXIT:
                        self.events.exit_requested.emit()
        finally:
            for shortcut in (self.TOGGLE,self.CANCEL,self.EXIT):
                self.api.UnregisterHotKey(None,shortcut)

    def arm_cancel(self, active):
        if self.thread_id:
            self.api.PostThreadMessageW(self.thread_id,self.ARM_CANCEL,int(active),0)

    def close(self):
        if self.thread_id:
            self.api.PostThreadMessageW(self.thread_id,0x0012,0,0)
            self.thread.join(timeout=1)
