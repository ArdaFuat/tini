import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from orb import Orb
from orb import microphone_strength


class VisualAudioTests(unittest.TestCase):
    def test_silence_and_low_noise_remain_still(self):
        for rms in (0,.0001,.0005,.0008):
            self.assertEqual(microphone_strength(rms),0)

    def test_soft_voice_is_visible_and_louder_voice_grows(self):
        levels=[microphone_strength(x) for x in (.0015,.003,.006,.012,.025,.06)]
        self.assertGreater(levels[0],.2)
        self.assertGreater(levels[1],.4)
        self.assertEqual(levels,sorted(levels))
        self.assertLessEqual(max(levels),1)

    def test_soft_voice_is_more_responsive_than_previous_linear_mapping(self):
        for rms in (.003,.006,.012):
            old=max(0,(rms-.002)*22)
            self.assertGreater(microphone_strength(rms),old*3)


class AnimationCadenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.orb=Orb(QSettings('runtime/cadence-test.ini',QSettings.Format.IniFormat))

    def tearDown(self):
        self.orb.timer.stop()
        self.orb.close()

    def test_small_rotating_orb_keeps_smooth_idle_cadence(self):
        self.orb.set_mode('idle')
        self.orb.expansion=0
        self.orb.tick()
        self.assertLessEqual(self.orb.timer.interval(),34)

    def test_active_animation_uses_precise_timer_with_60fps_budget(self):
        for mode in ('recording','processing','loading'):
            self.orb.set_mode(mode)
            self.assertLessEqual(self.orb.timer.interval(),17)
            self.assertEqual(self.orb.timer.timerType(),Qt.TimerType.PreciseTimer)


if __name__=='__main__':
    unittest.main()
