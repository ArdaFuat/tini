"""Run separately on Windows: python -m unittest test_native_orb.

Real GPU/window integration checks; the ordinary offscreen suite skips these.
Only this test's own windows are inspected. No microphone or model is opened.
"""
import ctypes
from ctypes import wintypes as W
import os
from pathlib import Path
import sys
import unittest

import numpy as np
from PySide6.QtCore import QObject, QPoint, QSettings, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from orb import Orb


def pixels(image):
    image=image.convertToFormat(QImage.Format.Format_RGBA8888)
    return np.frombuffer(image.bits(),dtype=np.uint8).reshape(
        image.height(),image.bytesPerLine()//4,4)[:,:image.width()].copy()


@unittest.skipUnless(sys.platform=='win32' and os.environ.get('QT_QPA_PLATFORM')!='offscreen',
                     'Requires a visible Windows GPU session')
class NativeOrbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.api=ctypes.WinDLL('user32')
        cls.api.WindowFromPoint.argtypes=[W.POINT]
        cls.api.WindowFromPoint.restype=W.HWND
        cls.api.ClientToScreen.argtypes=[W.HWND,ctypes.POINTER(W.POINT)]

    def setUp(self):
        Path('runtime').mkdir(exist_ok=True)
        self.orb=Orb(QSettings('runtime/native-tests.ini',QSettings.Format.IniFormat))
        self.orb.reveal()
        QTest.qWait(400)
        self.assertIsNotNone(self.orb._renderer)
        self.view=self.orb._renderer.view

    def tearDown(self):
        self.orb.shutdown_animation()
        self.orb.hide()
        self.orb.close()
        self.orb.deleteLater()
        QTest.qWait(50)

    def test_visible_mesh_expands_and_really_moves(self):
        self.orb.set_mode('idle')
        QTest.qWait(400)
        before=pixels(self.view.grabWindow())
        QTest.qWait(600)
        after=pixels(self.view.grabWindow())
        self.assertGreater(np.count_nonzero(before!=after),100)
        self.orb.set_mode('recording')
        QTest.qWait(400)
        frame=pixels(self.view.grabWindow())
        _,x=np.where(frame[:,:,3]>20)
        self.assertGreater(x.max()-x.min(),80*self.view.devicePixelRatio())

    def test_speech_has_fast_attack_and_smooth_release(self):
        self.orb.set_mode('recording')
        QTest.qWait(300)
        mesh=self.view.rootObject().findChild(QObject,'orbMesh')
        self.orb.set_level(.025)
        QTest.qWait(120)
        self.assertGreater(mesh.property('voice'),.6)
        self.orb.set_level(0)
        QTest.qWait(120)
        self.assertGreater(mesh.property('voice'),.2)

    def test_input_passes_through_visual_overlay_and_transparent_margin(self):
        self.orb.set_mode('idle')
        QTest.qWait(400)
        owner=int(self.orb.winId())
        render=int(self.view.winId())
        def hit(x,y):
            ratio=self.orb.devicePixelRatioF()
            point=W.POINT(round(x*ratio),round(y*ratio))
            self.assertTrue(self.api.ClientToScreen(owner,ctypes.byref(point)))
            return int(self.api.WindowFromPoint(point))
        self.assertEqual(hit(72,72),owner)
        self.assertNotIn(hit(5,5),(owner,render))

    def test_monitor_movement_and_visibility_recovery(self):
        for screen in self.app.screens():
            self.orb.move(screen.availableGeometry().topLeft()+QPoint(30,30))
            QTest.qWait(150)
            self.assertEqual(self.view.position(),self.orb.pos())
            self.assertEqual(self.view.screen(),screen)
        self.orb.hide()
        self.assertFalse(self.view.isVisible())
        self.orb.reveal(True)
        QTest.qWait(100)
        self.assertTrue(self.view.isVisible())


if __name__=='__main__':
    unittest.main()
