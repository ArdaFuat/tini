import faulthandler
import json
import logging
from logging.handlers import RotatingFileHandler
import math
import os
import queue
import sys
import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QMimeData, QObject, QRectF, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout,
    QLabel, QMainWindow, QMenu, QPushButton, QSystemTrayIcon, QTextEdit,
    QVBoxLayout, QWidget)

from audio_pipeline import RATE, Segmenter
from engine import ROOT
import winbridge as win
from orb import Orb as Pill

(ROOT / 'runtime').mkdir(exist_ok=True)
logging.basicConfig(handlers=[RotatingFileHandler(ROOT/'runtime'/'app.log',maxBytes=1024*1024,backupCount=2,encoding='utf-8')], level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logging.getLogger('faster_whisper').setLevel(logging.WARNING)
CRASH_LOG = open(ROOT / 'runtime' / 'crash.log', 'a', encoding='utf-8')
# Enable native stack dumps only on demand. COM can raise handled exceptions
# during Windows UI callbacks; production keeps regular Python error logging.
if os.environ.get('SES_DEBUG_CRASHES')=='1':
    faulthandler.enable(CRASH_LOG)
if sys.stderr is None:
    sys.stderr = CRASH_LOG


def report_exception(kind, error, traceback):
    logging.error('Unhandled application error', exc_info=(kind, error, traceback))


sys.excepthook = report_exception


class Events(QObject):
    status = Signal(str)
    ready = Signal()
    result = Signal(int, int, bool, str, float)
    error = Signal(str)
    hotkey = Signal()
    cancel = Signal()
    exit_requested = Signal()


from inference import Inference


from hotkeys import Hotkeys


STYLE = '''
QMainWindow, QWidget#main {background:#101915;color:#e6efe9;}
QLabel {color:#e6efe9;} QLabel#sub {color:#94ab9c;font-size:13px;}
QPushButton {background:#a6f0cb;color:#13291e;border:0;border-radius:10px;padding:12px 18px;font-weight:600;}
QPushButton:disabled {background:#304237;color:#849b8d;}
QPushButton#secondary {background:#23352b;color:#dce9e1;}
QComboBox,QTextEdit {background:#1a2a21;color:#e6efe9;border:1px solid #354b3c;border-radius:8px;padding:10px;}
QComboBox QAbstractItemView {background:#1a2a21;color:#e6efe9;selection-background-color:#345842;}
QCheckBox {color:#dce9e1;spacing:10px;}
'''


class Window(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle('Tını • Kişisel dikte')
        self.resize(650, 720)
        self.setStyleSheet(STYLE)
        body = QWidget()
        body.setObjectName('main')
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(32, 30, 32, 28)
        brand = QLabel('Tını')
        brand.setStyleSheet('font-size:42px;font-weight:700;color:#a6f0cb;')
        layout.addWidget(brand)
        subtitle = QLabel('Sen konuş. Kelimelerin yerini bulsun.')
        subtitle.setObjectName('sub')
        layout.addWidget(subtitle)
        self.status = QLabel('Turbo modeli hazırlanıyor…')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        instructions = QLabel('Ctrl + Alt + Boşluk → başlat / durdur\nEsc → iptal\nKüçük çubuğu sürükleyerek taşıyabilirsin.')
        instructions.setStyleSheet('line-height:1.5;color:#94ab9c;padding:12px 0;')
        layout.addWidget(instructions)
        layout.addWidget(QLabel('Mikrofon'))
        self.mics = QComboBox()
        self.mics.addItem('Windows varsayılan mikrofonu', None)
        try:
            hosts = sd.query_hostapis()
            for index, device in enumerate(sd.query_devices()):
                if device['max_input_channels'] > 0 and 'WASAPI' in hosts[device['hostapi']]['name']:
                    self.mics.addItem(device['name'], index)
        except Exception:
            logging.exception('Cannot enumerate microphones')
        selected=self.mics.findData(controller.microphone)
        if selected>=0:
            self.mics.setCurrentIndex(selected)
        self.mics.currentIndexChanged.connect(lambda: setattr(controller,'microphone',self.mics.currentData()))
        self.mics.setEnabled(not controller.recording)
        layout.addWidget(self.mics)
        layout.addWidget(QLabel('Kişisel kelimeler · model için ipucu'))
        self.words = QTextEdit()
        self.words.setPlaceholderText('Örnek: Arda, ChatGPT, GitHub, Unity, C#')
        self.words.setMaximumHeight(70)
        self.words.setPlainText(controller.config.value('vocabulary', 'ChatGPT, GitHub, Unity, Python, OpenAI'))
        self.words.textChanged.connect(self.save_words)
        layout.addWidget(self.words)
        layout.addWidget(QLabel('Son metin'))
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText('Konuştuğun metin burada da görünecek. Ses kaydı tutulmaz.')
        layout.addWidget(self.transcript, 1)
        row = QHBoxLayout()
        copy = QPushButton('Metni kopyala')
        copy.setObjectName('secondary')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.transcript.toPlainText()))
        row.addWidget(copy)
        show = QPushButton('Çubuğu göster')
        show.clicked.connect(lambda: controller.pill.reveal(True))
        row.addWidget(show)
        layout.addLayout(row)
        footer = QLabel('Yerel • Whisper large-v3-turbo • NVIDIA CUDA\nİnternet yalnızca ilk model indirmesinde kullanılır.')
        footer.setObjectName('sub')
        layout.addWidget(footer)

    def save_words(self):
        self.controller.vocabulary=self.words.toPlainText()
        self.controller.config.setValue('vocabulary', self.controller.vocabulary)

    def closeEvent(self, event):
        if getattr(self.controller,'quitting',False):
            event.accept()
        elif self.controller.tray.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            self.controller.quit()


class Controller(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.quitting = False
        self.config = QSettings('Arda', 'Ses')
        self.microphone=None
        self.vocabulary=self.config.value('vocabulary','ChatGPT, GitHub, Unity, Python, OpenAI')
        self.last_transcript=''
        self.status_text='Turbo modeli hazırlanıyor…'
        self.events = Events()
        self.pill = Pill(self.config)
        self.tray = QSystemTrayIcon(self.make_icon(), self)
        self.window = None
        self.tray.setToolTip('Tını • Ctrl + Alt + Boşluk')
        menu = QMenu()
        self.tray_menu=menu
        menu.addAction('Ayarlar', self.show_settings)
        menu.addAction('Animasyonu geri getir', lambda: self.pill.reveal(True))
        menu.addSeparator()
        menu.addAction('Çıkış', self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.pill.reveal(True) if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()
        self.pill.toggle.connect(self.toggle)
        self.pill.settings.connect(self.show_settings)
        self.pill.exit_requested.connect(self.quit)
        self.events.status.connect(self.set_status)
        self.events.ready.connect(self.on_ready)
        self.events.error.connect(self.on_error)
        self.events.result.connect(self.on_result)
        self.events.hotkey.connect(self.toggle)
        self.events.cancel.connect(self.cancel)
        self.events.exit_requested.connect(self.quit)
        self.hotkeys = Hotkeys(self.events)
        self.stream = None
        self.recording = False
        self.finishing = False
        self.sid = 0
        self.segment_index = 0
        self.expected = 0
        self.parts = {}
        self.audio_queue = queue.Queue(maxsize=200)
        self.capture_error = None
        self.worker = Inference(self.events)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.pill.reveal()
        if not self.hotkeys.ok:
            self.set_status('Kısayol başka uygulamada kullanılıyor. Yuvarlak düğmeye tıklayabilirsin.')

    def make_icon(self):
        icon_path=ROOT/'assets'/'branding'/'tini.ico'
        if icon_path.exists():
            return QIcon(str(icon_path))
        image = QPixmap(64, 64)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor('#101c26'))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(2, 2, 60, 60), 18, 18)
        painter.setPen(QColor('#4abacb'))
        painter.setFont(QFont('Segoe UI', 32, QFont.Weight.Bold))
        painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, 't')
        painter.end()
        return QIcon(image)

    def show_settings(self):
        if self.window is None:
            self.window=Window(self)
            self.window.setWindowIcon(self.tray.icon())
        self.window.status.setText(self.status_text)
        self.window.transcript.setPlainText(self.last_transcript)
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def set_status(self, text):
        self.status_text=text
        if self.window is not None:
            self.window.status.setText(text)
        self.pill.setToolTip(text)
        self.pill.setAccessibleDescription(text)

    def on_ready(self):
        self.pill.can_toggle = True
        self.pill.set_mode('idle')
        self.set_status('Hazır · Ctrl + Alt + Boşluk: konuş · Ctrl + Alt + Q: çıkış')
        logging.info('Orb ready; position=%s,%s',self.pill.x(),self.pill.y())

    def on_error(self, text):
        self.cancel()
        self.set_status(text)
        self.pill.set_mode('error')
        if not self.worker.ready:
            self.pill.can_toggle = False

    def toggle(self):
        if not self.worker.ready or self.finishing:
            return
        if self.recording:
            self.stop()
        else:
            self.start()

    def callback(self, indata, frames, timing, status):
        if status:
            self.capture_error = str(status)
        try:
            self.audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            self.capture_error = 'Ses işleme yetişemedi; metin gönderilmedi. Yeniden dene.'

    def start(self):
        self.target = win.foreground()
        self.pill.reveal()
        self.sid += 1
        self.worker.session = self.sid
        self.worker.vocabulary = self.vocabulary.strip()[:1000]
        self.segment_index = 0
        self.parts = {}
        self.segmenter = Segmenter()
        self.expected = 0
        self.audio_queue = queue.Queue(maxsize=200)
        self.capture_error = None
        self.started = time.monotonic()
        device = self.microphone
        try:
            try:
                sd.check_input_settings(device=device, samplerate=RATE, channels=1)
                self.sample_rate = RATE
            except Exception:
                self.sample_rate = int(sd.query_devices(device, 'input')['default_samplerate'])
            self.stream = sd.InputStream(device=device, channels=1, samplerate=self.sample_rate,
                dtype='float32', blocksize=int(self.sample_rate*.03), callback=self.callback)
            self.stream.start()
        except Exception as error:
            if self.stream:
                self.stream.close()
            self.stream = None
            self.pill.set_mode('error')
            self.set_status(f'Mikrofon açılamadı: {error}')
            return
        self.recording = True
        self.timer.start(30)
        if self.window is not None:
            self.window.mics.setEnabled(False)
        self.hotkeys.arm_cancel(True)
        self.pill.set_mode('recording')
        self.set_status('Dinliyor · Ctrl + Alt + Boşluk ile bitir')

    def drain(self):
        while True:
            try:
                block = self.audio_queue.get_nowait()
            except queue.Empty:
                break
            if self.sample_rate != RATE:
                from scipy.signal import resample_poly
                divisor = math.gcd(self.sample_rate, RATE)
                block = resample_poly(block, RATE//divisor, self.sample_rate//divisor).astype(np.float32)
            chunk, level = self.segmenter.feed(block)
            self.pill.set_level(level)
            if chunk is not None:
                self.submit_final(chunk)

    def submit_final(self, chunk):
        self.worker.submit(self.sid, self.segment_index, chunk)
        self.segment_index += 1

    def tick(self):
        if not self.recording:
            return
        if self.capture_error:
            error = self.capture_error
            self.cancel()
            self.set_status(f'Mikrofon sorunu: {error}')
            return
        self.drain()
        now = time.monotonic()
        if now - self.started > 300:
            self.stop()
            return

    def stop_stream(self):
        self.timer.stop()
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.recording = False
        if self.window is not None:
            self.window.mics.setEnabled(True)

    def stop(self):
        self.stop_stream()
        self.drain()
        if self.capture_error:
            self.cancel()
            self.set_status('Ses kesintisi oldu; metin gönderilmedi. Yeniden dene.')
            return
        tail = self.segmenter.flush()
        if tail is not None:
            self.submit_final(tail)
        self.expected = self.segment_index
        self.finishing = True
        self.stopped = time.perf_counter()
        self.pill.can_toggle = False
        self.pill.set_mode('processing')
        self.set_status('Son kelimeler işleniyor…')
        self.maybe_finish()

    def on_result(self, sid, index, final, text, elapsed):
        if sid != self.sid:
            return
        if final:
            self.parts[index] = text
            self.last_inference = elapsed
        combined = ' '.join(self.parts[i] for i in sorted(self.parts))
        self.last_transcript=combined
        if self.window is not None and self.window.isVisible():
            self.window.transcript.setPlainText(combined)
        self.maybe_finish()

    def maybe_finish(self):
        if not self.finishing or len(self.parts) != self.expected:
            return
        text = ' '.join(self.parts[i] for i in range(self.expected)).strip()
        self.finishing = False
        self.hotkeys.arm_cancel(False)
        self.pill.can_toggle = True
        self.pill.set_mode('idle')
        self.last_transcript=text
        self.segmenter=None
        if self.window is not None and self.window.isVisible():
            self.window.transcript.setPlainText(text)
        if not text:
            self.set_status('Konuşma algılanmadı. Mikrofon seçimini kontrol et.')
            return
        latency = time.perf_counter() - self.stopped
        self.set_status(f'Hazır · Son işlem {latency:.2f} sn')
        self.pending_paste = (self.sid, text, time.monotonic())
        QTimer.singleShot(80, self.paste_when_released)

    def paste_when_released(self):
        sid, text, started = self.pending_paste
        if sid != self.sid or self.recording:
            return
        if win.modifiers_down() and time.monotonic() - started < 3:
            QTimer.singleShot(50, self.paste_when_released)
            return
        clipboard = QApplication.clipboard()
        # When no paste is possible, leave the text on the clipboard without
        # materializing its previous image/file formats just to discard them.
        if win.modifiers_down() or not win.valid_paste_target(self.target):
            clipboard.setText(text)
            self.set_status('Metin panoya kopyalandı · İstediğin alana Ctrl + V')
            return
        saved = QMimeData()
        old = clipboard.mimeData()
        if old is not None:
            for format_name in old.formats():
                saved.setData(format_name, old.data(format_name))
        clipboard.setText(text)
        if not win.modifiers_down() and win.paste_shortcut(self.target):
            QTimer.singleShot(1200, lambda: clipboard.setMimeData(saved) if clipboard.text() == text else None)
        else:
            self.set_status('Metin panoya kopyalandı · İstediğin alana Ctrl + V')

    def cancel(self):
        self.stop_stream()
        self.sid += 1
        self.worker.session = self.sid
        self.finishing = False
        self.last_transcript=''
        self.segmenter=None
        self.audio_queue=queue.Queue(maxsize=200)
        if self.window is not None:
            self.window.transcript.clear()
        self.hotkeys.arm_cancel(False)
        self.pill.can_toggle = self.worker.ready
        self.pill.set_mode('idle' if self.worker.ready else 'loading')
        self.set_status('İptal edildi · Metin gönderilmedi')

    def quit(self):
        if self.quitting:
            return
        self.quitting = True
        logging.info('Exit requested; stopping audio and shortcuts')
        self.stop_stream()
        self.hotkeys.close()
        self.pill.shutdown_animation()
        self.pill.hide()
        if self.window is not None:
            self.window.hide()
        self.tray.hide()
        self.config.sync()
        self.worker.close()
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Tını')
    app.setApplicationDisplayName('Tını')
    app.setFont(QFont('Segoe UI', 10))
    app.setQuitOnLastWindowClosed(False)
    app.aboutToQuit.connect(lambda:logging.info('Application exit requested'))
    socket = QLocalSocket()
    socket.connectToServer('arda-ses-local-v1')
    if socket.waitForConnected(300):
        socket.write(b'show')
        socket.waitForBytesWritten(500)
        socket.waitForReadyRead(1500)
        return 0
    server = QLocalServer()
    QLocalServer.removeServer('arda-ses-local-v1')
    if not server.listen('arda-ses-local-v1'):
        raise RuntimeError('Uygulama kilidi açılamadı.')
    controller = Controller(app)
    def show_existing():
        connection = server.nextPendingConnection()
        def respond():
            if not connection.bytesAvailable():
                return
            request=bytes(connection.readAll())
            if request == b'show':
                controller.pill.reveal(True)
            response={'visible':controller.pill.isVisible(), 'minimized':controller.pill.isMinimized(),
                      'mode':controller.pill.mode, 'position':[controller.pill.x(),controller.pill.y()],
                      'animation_ms':controller.pill.timer.interval(),
                      'audio_timer_active':controller.timer.isActive(), 'hotkey_ok':controller.hotkeys.ok,
                      'settings_created':controller.window is not None,
                      'pid':os.getpid(), 'exit_hotkey_ok':getattr(controller.hotkeys,'exit_ok',False)}
            response['animation_backend']='gpu' if controller.pill._renderer is not None else 'raster'
            response['speech_pid']=getattr(getattr(controller.worker,'process',None),'pid',None)
            connection.write(json.dumps(response).encode('utf-8'))
            connection.flush()
            connection.disconnectFromServer()
            if request == b'quit':
                QTimer.singleShot(0,controller.quit)
        connection.readyRead.connect(respond)
        connection.disconnected.connect(connection.deleteLater)
        respond()
    server.newConnection.connect(show_existing)
    return app.exec()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        logging.exception('Application startup failed')
        raise
