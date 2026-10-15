"""Bounded speech segmentation, independent of the UI."""
from collections import deque
import numpy as np

RATE = 16000


class Segmenter:
    def __init__(self, threshold=0.006, pause=0.7, maximum=18):
        self.threshold = threshold
        self.pause_samples = int(pause * RATE)
        self.maximum_samples = int(maximum * RATE)
        self.preroll = deque(maxlen=7)
        self.frames = []
        self.samples = 0
        self.quiet_samples = 0

    def feed(self, block):
        level = float(np.sqrt(np.dot(block,block)/len(block)))
        voiced = level >= self.threshold
        if not self.frames:
            self.preroll.append(block)
            if not voiced:
                return None, level
            self.frames = list(self.preroll)
            self.preroll.clear()
            self.samples = sum(len(frame) for frame in self.frames)
        else:
            self.frames.append(block)
            self.samples += len(block)
        self.quiet_samples = 0 if voiced else self.quiet_samples + len(block)
        if self.quiet_samples >= self.pause_samples or self.samples >= self.maximum_samples:
            return self.flush(), level
        return None, level

    def flush(self):
        if not self.frames:
            self.preroll.clear()
            return None
        result = np.concatenate(self.frames)
        self.frames = []
        self.samples = self.quiet_samples = 0
        self.preroll.clear()
        return result
