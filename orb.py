"""A lightweight, audio-reactive wire sphere drawn with Qt's raster painter."""
import math
import time

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRectF, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient, QRegion
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
        self.last_hit_radius = None
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
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        position = config.value('pill_position', None)
        self.move(self.clamp(position) if isinstance(position, QPoint) else self.home())
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
        self.move(self.home() if reset_position else self.clamp(self.pos()))
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
        self.update()

    def set_level(self, level):
        self.target = microphone_strength(level)
        self.last_audio = time.monotonic()

    def set_mode(self, mode):
        self.mode = mode
        self.expansion_target = 0.0 if mode == 'idle' else 1.0
        self.color_target = QColor({'idle':'#469caf', 'recording':'#e78faf',
                                    'processing':'#e6cc83', 'loading':'#91a3d4',
                                    'error':'#ef7988'}[mode])
        if mode != 'recording':
            self.target = 0.0
        self.timer.setInterval(33)
        self.last_tick = time.monotonic()
        self.update()

    def tick(self):
        now = time.monotonic()
        dt = min(now-self.last_tick, .15)
        self.last_tick = now
        target = self.target if self.mode == 'recording' and now-self.last_audio < .18 else 0.
        self.level += (target-self.level)*(1-math.exp(-dt/(.045 if target > self.level else .38)))
        self.expansion += (self.expansion_target-self.expansion)*(1-math.exp(-dt/.16))
        hit_radius = int(24+47*self.expansion)
        if hit_radius != self.last_hit_radius:
            self.setMask(QRegion(self.SIZE//2-hit_radius,self.SIZE//2-hit_radius,
                                 hit_radius*2,hit_radius*2,QRegion.RegionType.Ellipse))
            self.last_hit_radius = hit_radius
        mix = 1-math.exp(-dt/.18)
        self.color = QColor.fromRgbF(*[a+(b-a)*mix for a,b in zip(self.color.getRgbF()[:3],self.color_target.getRgbF()[:3])])
        self.phase += dt*(.24 + self.level*4.0 if self.mode == 'recording' else .18)
        # Eight frames/sec for the tiny idle orb; 30 while opening or listening.
        interval = 125 if self.mode == 'idle' and self.expansion < .015 else 33
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
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
        # A reduced mesh is sufficient when the orb is only 24px across.
        edges = self.edges if self.expansion > .15 else self.edges[::3]
        for a,b in edges:
            path = front if (z[a]+z[b]) > 0 else back
            path.moveTo(float(projected[a,0]),float(projected[a,1]))
            path.lineTo(float(projected[b,0]),float(projected[b,1]))
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
