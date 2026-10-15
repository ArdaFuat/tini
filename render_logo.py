"""Export Tını's orb-inspired vector mark, transparent PNG and Windows icon."""
import math
import os
import struct
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'assets' / 'branding'


def sphere():
    rows, columns = 12, 24
    points = []
    for row in range(rows + 1):
        theta = .035 + (math.pi - .07) * row / rows
        for column in range(columns):
            phi = 2 * math.pi * column / columns
            x, y, z = math.sin(theta)*math.cos(phi), math.cos(theta), math.sin(theta)*math.sin(phi)
            # Same globe as the idle widget, with a slight diagonal tilt for its mark.
            x, z = x*.866 + z*.5, -x*.5 + z*.866
            y, z = y*.976 - z*.216, y*.216 + z*.976
            x, y = x*.966 - y*.259, x*.259 + y*.966
            scale = 188 / (1 - z*.075)
            points.append((256+x*scale, 256+y*scale, z))
    edges = []
    for row in range(rows + 1):
        for col in range(columns):
            a = row*columns+col
            edges.append((a, row*columns+(col+1)%columns))
            if row < rows:
                edges.append((a, a+columns))
                # Sparse diagonals retain the geometric mesh without filling every cell.
                if row % 2 == 0 and col % 2 == 0:
                    edges.append((a, (row+1)*columns+(col+1)%columns))
    back, front = [], []
    for a, b in edges:
        x1,y1,z1 = points[a]
        x2,y2,z2 = points[b]
        depth = (z1+z2)/2
        path = f'M{x1:.2f},{y1:.2f}L{x2:.2f},{y2:.2f}'
        if depth < 0:
            back.append(f'<path d="{path}" opacity="{.10+.10*(1+depth):.2f}"/>')
        else:
            front.append(f'<path d="{path}" opacity="{.55+.45*depth:.2f}"/>')
    return ('<g fill="none" stroke-linecap="round" stroke-linejoin="round">'
            '<g stroke="#469caf" stroke-width="1.8">'+''.join(back)+'</g>'
            '<g stroke="url(#turquoise)" stroke-width="3.1">'+''.join(front)+'</g></g>')


def svg(tile=False):
    background = ('<rect x="20" y="20" width="472" height="472" rx="112" fill="#101c26"/>'
                  '<rect x="21" y="21" width="470" height="470" rx="111" fill="none" stroke="#23414f" stroke-width="2"/>') if tile else ''
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
            '<title>Tını</title><desc>Turkuaz geometrik küre; Tını konuşarak yazma uygulaması.</desc>'
            '<defs><linearGradient id="turquoise" x1=".15" y1="1" x2=".85" y2="0" gradientUnits="objectBoundingBox">'
            '<stop offset="0" stop-color="#2885a8"/><stop offset=".5" stop-color="#4abacb"/>'
            '<stop offset="1" stop-color="#a8f0e4"/></linearGradient></defs>'
            +background+sphere()+'</svg>')


def raster(source, size):
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(source.encode('utf-8'))).render(painter)
    painter.end()
    return image


def ico(source):
    sizes = (16, 24, 32, 48, 64, 128, 256)
    entries, images = [], []
    offset = 6 + 16*len(sizes)
    for size in sizes:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        raster(source, size).save(buffer, 'PNG')
        payload = bytes(data)
        entries.append(struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(payload), offset))
        images.append(payload)
        offset += len(payload)
    return struct.pack('<HHH', 0, 1, len(sizes)) + b''.join(entries+images)


def main():
    app = QApplication.instance() or QApplication([])
    OUT.mkdir(parents=True, exist_ok=True)
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/seguisb.ttf')
    mark, tile = svg(), svg(True)
    for name, source in (('tini-logo', mark), ('tini-icon', tile)):
        (OUT / f'{name}.svg').write_text(source, encoding='utf-8')
        raster(source, 1024).save(str(OUT / f'{name}.png'))
    (OUT / 'tini.ico').write_bytes(ico(tile))
    sheet = QImage(1440, 660, QImage.Format.Format_RGB32)
    sheet.fill(QColor('#f2f5f5'))
    p = QPainter(sheet)
    p.fillRect(0, 0, 720, 660, QColor('#101c26'))
    p.drawImage(QRectF(144, 44, 432, 432), raster(mark, 864))
    p.drawImage(QRectF(864, 44, 432, 432), raster(tile, 864))
    p.setFont(QFont('Segoe UI', 31, QFont.Weight.DemiBold))
    for x, color, title, caption in ((0,'#edf6f6','Tını','Turkuaz küre'),
                                     (720,'#173743','Tını','Uygulama simgesi')):
        p.setPen(QColor(color))
        p.drawText(QRectF(x, 470, 720, 66), Qt.AlignmentFlag.AlignCenter, title)
        p.setFont(QFont('Segoe UI', 12))
        p.drawText(QRectF(x, 544, 720, 35), Qt.AlignmentFlag.AlignCenter, caption)
        p.setFont(QFont('Segoe UI', 31, QFont.Weight.DemiBold))
    p.end()
    sheet.save(str(OUT / 'preview.png'))
    print(OUT)


if __name__ == '__main__':
    main()
