"""Vsync-driven GPU animation. No Python callback runs for each rendered frame."""
import logging
import os
from pathlib import Path

# Keep animation speed tied to elapsed time on mixed 60/240 Hz desktops.
os.environ.setdefault('QSG_USE_SIMPLE_ANIMATION_DRIVER','1')

from PySide6.QtCore import QObject, QSize, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickView, QQuickWindow, QSGRendererInterface
from PySide6.QtWidgets import QApplication


class NativeOrbRenderer(QObject):
    failed = Signal(str)

    def __init__(self, owner):
        super().__init__(owner)
        QQuickWindow.setDefaultAlphaBuffer(True)
        self.view = QQuickView()
        self.view.setTitle('Tını • Animasyon')
        # The lightweight QWidget below owns input. This window only renders.
        self.view.setFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.WindowTransparentForInput)
        fmt = self.view.format()
        fmt.setAlphaBufferSize(8)
        self.view.setFormat(fmt)
        self.view.setColor(QColor(0,0,0,0))
        self.view.resize(owner.SIZE, owner.SIZE)
        self.view.setMinimumSize(QSize(owner.SIZE,owner.SIZE))
        self.view.setMaximumSize(QSize(owner.SIZE,owner.SIZE))
        self._owner = owner
        # Windows can preserve physical window dimensions on a DPI transition,
        # despite fixed logical size hints (144 DIP becomes 96 at 150%). Repair
        # after the native resize event, rather than only before moving screens.
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setSingleShot(True)
        self._geometry_timer.timeout.connect(self.sync_geometry)
        self.view.widthChanged.connect(self.schedule_geometry)
        self.view.heightChanged.connect(self.schedule_geometry)
        self.view.screenChanged.connect(self.schedule_geometry)
        self.move(owner.pos())
        source = Path(__file__).resolve().parent/'assets'/'orb'/'Orb.qml'
        self.view.setSource(QUrl.fromLocalFile(str(source)))
        if self.view.status() == QQuickView.Status.Error or self.view.rootObject() is None:
            errors = '; '.join(error.toString() for error in self.view.errors())
            self.view.close()
            self.view.deleteLater()
            raise RuntimeError(f'Animasyon yüklenemedi: {errors}')
        self.root = self.view.rootObject()
        if self.view.rendererInterface().graphicsApi() == QSGRendererInterface.GraphicsApi.Software:
            self.view.close()
            self.view.deleteLater()
            raise RuntimeError('GPU çizimi kullanılamıyor; yazılımsal çizime dönülüyor.')
        self.view.sceneGraphError.connect(self.on_error)

    def on_error(self, error, message):
        logging.error('Native orb scene graph: %s',message)
        self.failed.emit(message)

    def set_mode(self, mode, color):
        self.root.setProperty('mode', {'idle':0,'recording':1,'processing':2,'loading':3,'error':4}[mode])
        self.root.setProperty('expansion', 0. if mode == 'idle' else 1.)
        self.root.setProperty('orbColor', color)
        if mode != 'recording':
            self.set_level(0.)

    def set_level(self, strength):
        self.root.setProperty('speechLevel',strength)

    def move(self, point):
        screen = QApplication.screenAt(point)
        if screen is not None and self.view.screen() != screen:
            self.view.setScreen(screen)
        self.view.setPosition(point)
        self.schedule_geometry()

    def schedule_geometry(self, *_):
        self._geometry_timer.start(0)

    def sync_geometry(self):
        if self.view.size() != self._owner.size():
            self.view.resize(self._owner.size())
        if self.view.position() != self._owner.pos():
            self.view.setPosition(self._owner.pos())

    def show(self, owner):
        self.move(owner.pos())
        self.view.setTransientParent(owner.windowHandle())
        self.root.setProperty('running',True)
        self.view.showNormal()
        self.view.raise_()

    def hide(self):
        self.view.hide()
        self.root.setProperty('running',False)
