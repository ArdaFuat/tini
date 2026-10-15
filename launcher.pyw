"""Lightweight desktop entry: restore the existing orb without importing the model/UI."""
from pathlib import Path
import subprocess
import sys


def main():
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtNetwork import QLocalSocket
    app=QCoreApplication([])
    socket=QLocalSocket()
    socket.connectToServer('arda-ses-local-v1')
    if socket.waitForConnected(200):
        socket.write(b'show')
        socket.waitForBytesWritten(1000)
        if not socket.waitForReadyRead(2000):
            raise RuntimeError('Tını yanıt vermiyor. Bildirim alanındaki simgeden çıkıp yeniden açmayı dene.')
        socket.close()
        return
    root=Path(__file__).resolve().parent
    subprocess.Popen([str(root/'.venv/Scripts/pythonw.exe'),str(root/'desktop.py')],cwd=root)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,str(error),'Tını açılamadı',0x10)
