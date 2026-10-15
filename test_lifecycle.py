import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import queue
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from app import Controller


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt=QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine=SimpleNamespace(ready=True,session=0,vocabulary='',close=Mock())
        self.keys=SimpleNamespace(ok=True,arm_cancel=Mock(),close=Mock())
        self.app=SimpleNamespace(quit=Mock())
        with patch('app.Inference',return_value=self.engine), patch('app.Hotkeys',return_value=self.keys):
            self.controller=Controller(self.app)
        self.controller.on_ready()

    def tearDown(self):
        self.controller.quit()

    def test_start_stop_without_speech_returns_to_idle(self):
        stream=Mock()
        with patch('app.sd.check_input_settings'), patch('app.sd.InputStream',return_value=stream):
            self.controller.toggle()
            self.assertTrue(self.controller.recording)
            self.assertEqual(self.controller.pill.mode,'recording')
            self.controller.toggle()
        stream.stop.assert_called_once()
        stream.close.assert_called_once()
        self.assertFalse(self.controller.recording)
        self.assertEqual(self.controller.pill.mode,'idle')
        self.assertFalse(self.controller.timer.isActive())

    def test_quit_releases_window_audio_and_hotkeys_once(self):
        self.controller.show_settings()
        self.controller.quit()
        self.controller.quit()
        self.keys.close.assert_called_once()
        self.app.quit.assert_called_once()
        self.engine.close.assert_called_once()
        self.assertFalse(self.controller.pill.isVisible())
        self.assertFalse(self.controller.window.isVisible())
        self.assertFalse(self.controller.pill.timer.isActive())

    def test_settings_created_only_on_request_and_reused(self):
        self.assertIsNone(self.controller.window)
        self.controller.last_transcript='Örnek metin'
        self.controller.show_settings()
        window=self.controller.window
        self.assertEqual(window.transcript.toPlainText(),'Örnek metin')
        self.controller.show_settings()
        self.assertIs(self.controller.window,window)

    def test_cancel_releases_pending_audio_without_creating_settings(self):
        import numpy as np
        stream=Mock()
        with patch('app.sd.check_input_settings'), patch('app.sd.InputStream',return_value=stream):
            self.controller.start()
            self.controller.audio_queue.put(np.ones(480,dtype=np.float32))
            self.controller.cancel()
        self.assertIsNone(self.controller.segmenter)
        self.assertTrue(self.controller.audio_queue.empty())
        self.assertIsNone(self.controller.window)

    def test_orb_close_requests_full_exit(self):
        self.controller.pill.close()
        self.app.quit.assert_called_once()
        self.assertTrue(self.controller.quitting)

    def test_gpu_failure_restores_visible_raster_animation(self):
        orb=self.controller.pill
        renderer=Mock()
        orb._renderer=renderer
        orb.timer.stop()
        orb.use_raster_fallback('test device lost')
        self.assertIsNone(orb._renderer)
        self.assertTrue(orb.timer.isActive())
        renderer.hide.assert_called_once()
        renderer.view.close.assert_called_once()

    def test_clipboard_fallback_does_not_copy_old_large_contents(self):
        import time
        clipboard=Mock()
        self.controller.target=123
        self.controller.pending_paste=(self.controller.sid,'Merhaba',time.monotonic())
        with patch('app.win.modifiers_down',return_value=False),patch('app.win.valid_paste_target',return_value=False),patch('app.QApplication.clipboard',return_value=clipboard):
            self.controller.paste_when_released()
        clipboard.setText.assert_called_once_with('Merhaba')
        clipboard.mimeData.assert_not_called()


if __name__=='__main__':
    unittest.main()
