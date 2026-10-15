"""A lightweight, audio-reactive wire sphere drawn with Qt's raster painter."""
import math
import time
import logging

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRectF, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QApplication, QMenu, QWidget


def microphone_strength(rms):
    """Perceptual visual gain: soft speech remains visible; silence stays still."""
    signal=max(0.,rms-.0008)
    return min(1.,math.sqrt(math.log1p(signal*180)/math.log1p(.035*180)))


class Orb(QWidget):
    toggle = Signal()
    settings = Signal()
    exit_requested = Signal()
    SIZE = 144
    ACTIVE_INTERVAL = 16
    IDLE_INTERVAL = 33

    def __init__(self, config):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('Tını • Mikrofon')
        self.setAccessibleName('Tını mikrofon düğmesi')
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.config = config
        self.can_toggle = False
        self.mode = 'loading'
        self.origin = self.pressed_at = None
        self.dragged = False
        self.level = self.target = 0.0
        self.last_audio = 0.0
        self.phase = 0.0
        self.expansion = self.expansion_target = 1.0
        self.color = QColor('#799ed7')
        self.color_target = QColor(self.color)
        self.last_tick = time.monotonic()
        self._renderer = None
        # A 3D latitude/longitude mesh. Geometry is reused, only deformation changes.
        # About half the previous mesh: 612 vertices / 1768 edges, down from
        # 1200 / 3504. Preserve the silhouette and audio-driven deformation.
        rows, columns = 18, 34
        self.theta = np.repeat(np.linspace(.055, math.pi-.055, rows), columns)
        self.phi = np.tile(np.linspace(0, 2*math.pi, columns, endpoint=False), rows)
        self.base = np.column_stack((np.sin(self.theta)*np.cos(self.phi),
                                     np.cos(self.theta), np.sin(self.theta)*np.sin(self.phi)))
        edges = []
        for row in range(rows):
            for col in range(columns):
                vertex = row*columns+col
                edges.append((vertex, row*columns+(col+1)%columns))
                if row < rows-1:
                    edges.append((vertex, vertex+columns))
                    edges.append((vertex, (row+1)*columns+(col+1)%columns))
        self.edges = np.asarray(edges)
        self.idle_edges = self.edges[::3]
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(self.ACTIVE_INTERVAL)
        position = config.value('pill_position', None)
        self.move(self.clamp(position) if isinstance(position, QPoint) else self.home())
        if QApplication.platformName() != 'offscreen':
            try:
                from native_orb import NativeOrbRenderer
                self._renderer = NativeOrbRenderer(self)
                self._renderer.failed.connect(self.use_raster_fallback)
                self.timer.stop()
            except Exception:
                logging.exception('Native animation unavailable; using raster fallback')
        self.level_timeout = QTimer(self)
        self.level_timeout.setSingleShot(True)
        self.level_timeout.setInterval(180)
        self.level_timeout.timeout.connect(self.clear_level)
        self.set_mode('loading')

    def home(self):
        screen = QApplication.primaryScreen().availableGeometry()
        return QPoint(screen.left()+18, screen.bottom()-self.height()-20)

    def clamp(self, point):
        screen = QApplication.screenAt(point+QPoint(self.width()//2, self.height()//2))
        if screen is None:
            return self.home()
        area = screen.availableGeometry()
        return QPoint(max(area.left(), min(point.x(), area.right()-self.width()+1)),
                      max(area.top(), min(point.y(), area.bottom()-self.height()+1)))

    def reveal(self, reset_position=False):
        needs_show = not self.isVisible() or self.isMinimized() or reset_position
        self.move(self.home() if reset_position else self.clamp(self.pos()))
        if not needs_show:
            return
        self.showNormal()
        self.raise_()
        # Keep the orb visible without taking the caret from the target app.
        if __import__('sys').platform == 'win32' and QApplication.platformName() != 'offscreen':
            import ctypes
            from ctypes import wintypes
            api = ctypes.WinDLL('user32', use_last_error=True)
            api.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
            api.ShowWindow(int(self.winId()), 4)  # SW_SHOWNOACTIVATE
            api.SetWindowPos(int(self.winId()), -1, 0, 0, 0, 0, 0x0013)  # TOPMOST, no activate/move/resize
        if self._renderer is not None:
            self._renderer.show(self)
        self.update()

    def set_level(self, level):
        self.target = microphone_strength(level)
        self.last_audio = time.monotonic()
        if self._renderer is not None:
            self._renderer.set_level(self.target)
            self.level_timeout.start()

    def clear_level(self):
        if self._renderer is not None:
            self._renderer.set_level(0.)

    def use_raster_fallback(self, message):
        if self._renderer is None:
            return
        logging.warning('Switching to raster animation: %s',message)
        renderer,self._renderer = self._renderer,None
        renderer.hide()
        renderer.view.close()
        renderer.view.deleteLater()
        renderer.deleteLater()
        self.level_timeout.stop()
        self.color = QColor(self.color_target)
        self.expansion = self.expansion_target
        self.timer.start(self.ACTIVE_INTERVAL)
        self.last_tick = time.monotonic()
        self.update()

    def set_mode(self, mode):
        self.mode = mode
        self.expansion_target = 0.0 if mode == 'idle' else 1.0
        self.color_target = QColor({'idle':'#469caf', 'recording':'#469caf',
                                    'processing':'#e6cc83', 'loading':'#91a3d4',
                                    'error':'#ef7988'}[mode])
        if mode != 'recording':
            self.target = 0.0
        self.timer.setInterval(self.ACTIVE_INTERVAL)
        self.last_tick = time.monotonic()
        if self._renderer is not None:
            self._renderer.set_mode(mode,self.color_target)
        self.update()

    def tick(self):
        now = time.monotonic()
        dt = min(now-self.last_tick, .15)
        self.last_tick = now
        target = self.target if self.mode == 'recording' and now-self.last_audio < .18 else 0.
        self.level += (target-self.level)*(1-math.exp(-dt/(.045 if target > self.level else .38)))
        if self.mode == 'recording':
            blend=max(0.,min(1.,(self.level-.18)/.24))
            quiet,talking=QColor('#469caf'),QColor('#e78faf')
            self.color_target=QColor.fromRgbF(*[a+(b-a)*blend for a,b in zip(
                quiet.getRgbF()[:3],talking.getRgbF()[:3])])
        self.expansion += (self.expansion_target-self.expansion)*(1-math.exp(-dt/.16))
        # Windows layered windows already hit-test their nonzero-alpha pixels.
        # The faint disk in draw() fills mesh gaps and grows with the orb.
        # Rebuilding the native window region here stalls SetWindowRgn/DWM
        # during expansion, sometimes for more than 100 ms per frame.
        mix = 1-math.exp(-dt/.18)
        self.color = QColor.fromRgbF(*[a+(b-a)*mix for a,b in zip(self.color.getRgbF()[:3],self.color_target.getRgbF()[:3])])
        self.phase += dt*(.24 + self.level*4.0 if self.mode == 'recording' else .18)
        # A rotating idle sphere also needs a smooth cadence. PreciseTimer avoids
        # coarse Windows timer rounding stretching active frames to about 47 ms.
        interval = self.IDLE_INTERVAL if self.mode == 'idle' and self.expansion < .015 else self.ACTIVE_INTERVAL
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._renderer is not None:
            # Stable, almost transparent input surface. Pixel alpha provides a
            # circular hit target; the separate GPU window passes all input on.
            painter.setBrush(QColor(15,25,28,1))
            painter.setPen(Qt.PenStyle.NoPen)
            radius = 24 if self.mode == 'idle' else 70
            painter.drawEllipse(QRectF(72-radius,72-radius,radius*2,radius*2))
            return
        self.draw(painter)

    def draw(self, painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = cy = self.SIZE/2
        radius = 16 + 39*self.expansion
        # A layered Windows window hit-tests alpha pixels, including mesh gaps.
        painter.setBrush(QColor(15,25,28,12))
        painter.setPen(Qt.PenStyle.NoPen)
        hit_radius = 23+47*self.expansion
        painter.drawEllipse(QRectF(cx-hit_radius,cy-hit_radius,hit_radius*2,hit_radius*2))
        phase = self.phase
        deformation = self.expansion*(.035 + .20*self.level if self.mode == 'recording' else .035)
        if self.mode == 'processing':
            deformation = .095
        ripple = (np.sin(self.theta*4 + phase*2.1)*np.cos(self.phi*3-phase*1.3)
                  + .4*np.sin(self.phi*5+self.theta*3+phase))
        vertices = self.base*(1+deformation*ripple[:,None])
        angle = phase*.45
        cosine, sine = math.cos(angle), math.sin(angle)
        x = vertices[:,0]*cosine + vertices[:,2]*sine
        z = -vertices[:,0]*sine + vertices[:,2]*cosine
        y = vertices[:,1]*.94 + z*.18
        # Gentle perspective; never scale beyond the reserved canvas.
        scale = radius/(1-z*.11)
        projected = np.column_stack((cx+x*scale, cy+y*scale))
        if self.expansion > .05:
            gradient = QRadialGradient(QPointF(cx,cy), radius*1.2)
            glow = QColor(self.color)
            glow.setAlpha(int(16*self.expansion))
            gradient.setColorAt(0,glow)
            gradient.setColorAt(1,QColor(0,0,0,0))
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(cx-radius*1.2,cy-radius*1.2,radius*2.4,radius*2.4))
        back, front = QPainterPath(), QPainterPath()
        # Gather coordinates and depth in NumPy once, rather than indexing and
        # converting scalar arrays for every edge on the UI thread. Keep exactly
        # the same subpaths and painter, so the mesh's appearance stays intact.
        edges = self.edges if self.expansion > .15 else self.idle_edges
        coordinates = projected[edges].reshape(-1,4)
        visible = z[edges].sum(axis=1) > 0
        for path, mask in ((back,~visible),(front,visible)):
            lines = coordinates[mask].tolist()
            path.reserve(len(lines)*2)
            for x1,y1,x2,y2 in lines:
                path.moveTo(x1,y1)
                path.lineTo(x2,y2)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for path,alpha,width in ((back,45,.5),(front,180,.6)):
            color = QColor(self.color)
            color.setAlpha(alpha)
            painter.setPen(QPen(color,width))
            painter.drawPath(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.globalPosition().toPoint()-self.pos()
            self.pressed_at = event.globalPosition().toPoint()
            self.dragged = False

    def moveEvent(self,event):
        if self._renderer is not None:
            self._renderer.move(self.pos())
        super().moveEvent(event)

    def showEvent(self,event):
        super().showEvent(event)
        if self._renderer is not None:
            self._renderer.show(self)

    def hideEvent(self,event):
        if self._renderer is not None:
            self._renderer.hide()
        super().hideEvent(event)

    def shutdown_animation(self):
        self.timer.stop()
        self.level_timeout.stop()
        if self._renderer is not None:
            self._renderer.hide()
            self._renderer.view.close()
            self._renderer.view.releaseResources()

    def mouseMoveEvent(self, event):
        if self.origin is not None:
            if (event.globalPosition().toPoint()-self.pressed_at).manhattanLength() >= QApplication.startDragDistance():
                self.dragged = True
            if self.dragged:
                self.move(self.clamp(event.globalPosition().toPoint()-self.origin))

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.origin is None:
            return
        self.origin = None
        if self.dragged:
            self.config.setValue('pill_position',self.pos())
            self.config.sync()
        elif self.can_toggle:
            self.toggle.emit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction('Görünür konuma getir',lambda:self.reveal(True))
        menu.addAction('Ayarlar',self.settings.emit)
        menu.addAction('Çıkış',self.exit_requested.emit)
        menu.exec(event.globalPos())

    def closeEvent(self, event):
        event.accept()
        self.exit_requested.emit()
