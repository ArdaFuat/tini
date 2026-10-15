import unittest
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


if __name__=='__main__':
    unittest.main()
