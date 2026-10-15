"""Render the actual widget offscreen for visual review; does not open the mic."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import time
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import QSettings, Qt, QRect
from PySide6.QtGui import QColor, QPainter, QPixmap, QFont, QFontDatabase
from orb import Orb

app=QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
orb=Orb(QSettings('runtime/render.ini',QSettings.Format.IniFormat))
orb.show()
orb.timer.stop()
canvas=QPixmap(144*5,180)
canvas.fill(QColor('#101618'))
painter=QPainter(canvas)
for index,(mode,label,level) in enumerate([
    ('idle','Bekliyor',0), ('recording','Dinliyor',.08), ('recording','Konuşuyor',.85),
    ('processing','Yazıyor',0), ('idle','Küçülüyor',0)]):
    orb.set_mode(mode)
    orb.expansion=.42 if index==4 else (0 if mode=='idle' else 1)
    orb.level=level
    orb.phase=1.2
    orb.color=QColor(orb.color_target)
    orb.clearMask()
    app.processEvents()
    painter.drawPixmap(index*144,0,orb.grab())
    painter.setPen(QColor('#cad5d7'))
    painter.setFont(QFont('Segoe UI',10))
    painter.drawText(QRect(index*144,146,144,30),Qt.AlignmentFlag.AlignCenter,label)
painter.end()
canvas.save('runtime/orb-preview.png')

# Check speech response, smooth decay and low-frequency idle operation.
orb.set_mode('recording')
for _ in range(30):
    orb.last_tick=time.monotonic()-.033
    orb.set_level(.06)
    orb.tick()
assert orb.level > .95
assert orb.expansion > .98
orb.last_audio=time.monotonic()-3
for _ in range(50):
    orb.last_tick=time.monotonic()-.033
    orb.tick()
assert orb.level < .02
orb.set_mode('idle')
for _ in range(35):
    orb.last_tick=time.monotonic()-.033
    orb.tick()
assert orb.expansion < .015 and orb.timer.interval()==orb.IDLE_INTERVAL
assert not orb.findChildren(QLabel)
assert orb.clamp(__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(99999,99999))==orb.home()
print('PASS: expansion, speech response, release, idle cadence, offscreen recovery, no overlay text')
