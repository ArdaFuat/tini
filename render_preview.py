"""Capture the current GPU orb for README images, without a mic or speech model."""
from pathlib import Path

from PySide6.QtCore import QRect, QSettings, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from orb import Orb


def main():
    root = Path(__file__).resolve().parent
    (root/'runtime').mkdir(exist_ok=True)
    output = root/'assets'/'screenshots'
    output.mkdir(exist_ok=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    orb = Orb(QSettings(str(root/'runtime'/'preview.ini'), QSettings.Format.IniFormat))
    try:
        orb.reveal()
        if orb._renderer is None:
            raise RuntimeError('The README preview requires the current GPU renderer.')
        frames = []
        for name, label, mode, rms in (
            ('idle', 'Bekliyor', 'idle', 0),
            ('listening', 'Dinliyor', 'recording', 0),
            ('speaking', 'Konuşuyor', 'recording', .025),
            ('processing', 'Yazıyor', 'processing', 0),
        ):
            orb.set_mode(mode)
            for _ in range(12):
                orb.set_level(rms)
                QTest.qWait(40)
            frame = orb._renderer.view.grabWindow()
            if frame.isNull():
                raise RuntimeError(f'Could not capture {name}.')
            frame.save(str(output/f'{name}.png'))
            frames.append((frame, label))

        size = max(frame.width() for frame, _ in frames)
        cell = size+32
        canvas = QImage(cell*4, size+76, QImage.Format.Format_RGB32)
        canvas.fill(QColor('#101618'))
        painter = QPainter(canvas)
        painter.setFont(QFont('Segoe UI', 12))
        painter.setPen(QColor('#cad5d7'))
        for index, (frame, label) in enumerate(frames):
            target = QRect(index*cell+(cell-frame.width())//2, 12, frame.width(), frame.height())
            painter.drawImage(target, frame)
            painter.drawText(QRect(index*cell, size+28, cell, 30), Qt.AlignmentFlag.AlignCenter, label)
        painter.end()
        canvas.save(str(root/'assets'/'preview.png'))
        print('Saved GPU preview and four transparent state images; no microphone or model used.')
    finally:
        orb.shutdown_animation()
        orb.hide()
        orb.close()


if __name__ == '__main__':
    main()
