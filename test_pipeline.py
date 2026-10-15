import unittest
import numpy as np
from types import SimpleNamespace
from engine import transcribe
from audio_pipeline import RATE, Segmenter


class SpeechPipelineTests(unittest.TestCase):
    def test_silence_produces_no_job(self):
        segmenter = Segmenter()
        for _ in range(200):
            chunk, _ = segmenter.feed(np.zeros(480, dtype=np.float32))
            self.assertIsNone(chunk)
        self.assertIsNone(segmenter.flush())
    def test_noise_repetition_is_rejected_but_normal_text_survives(self):
        class Model:
            def transcribe(self, audio, **kwargs):
                return iter([
                    SimpleNamespace(text='UR'*100, compression_ratio=8.2,
                                    avg_logprob=-.2, no_speech_prob=.1),
                    SimpleNamespace(text='Merhaba dünya.', compression_ratio=1.1,
                                    avg_logprob=-.2, no_speech_prob=.01),
                ]), None
        result, _ = transcribe(Model(), np.zeros(16000, dtype=np.float32))
        self.assertEqual(result, 'Merhaba dünya.')

    def test_pause_commits_once_and_keeps_speech(self):
        segmenter = Segmenter()
        voice = np.full(480, .03, dtype=np.float32)
        for _ in range(30):
            segmenter.feed(voice)
        jobs = []
        for _ in range(50):
            chunk, _ = segmenter.feed(np.zeros(480, dtype=np.float32))
            if chunk is not None:
                jobs.append(chunk)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(np.count_nonzero(jobs[0]), 30*480)
        self.assertIsNone(segmenter.flush())

    def test_long_utterance_is_bounded_without_dropping_samples(self):
        segmenter = Segmenter(maximum=1)
        voice = np.full(480, .03, dtype=np.float32)
        jobs = []
        for _ in range(100):
            chunk, _ = segmenter.feed(voice)
            if chunk is not None:
                jobs.append(chunk)
        tail = segmenter.flush()
        if tail is not None:
            jobs.append(tail)
        self.assertEqual(sum(len(chunk) for chunk in jobs), 48000)
        self.assertTrue(all(len(chunk) <= RATE+480 for chunk in jobs))

    def test_stop_retains_unfinished_utterance(self):
        segmenter = Segmenter()
        segmenter.feed(np.full(480, .04, dtype=np.float32))
        self.assertEqual(len(segmenter.flush()), 480)
        self.assertIsNone(segmenter.flush())


if __name__ == '__main__':
    unittest.main()
