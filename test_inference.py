"""Exercise real Windows child processes without loading the speech model."""
import os
import queue
import time
import unittest

from inference import Inference


def echo_worker(jobs, output, session):
    output.send(('ready',))
    while True:
        job = jobs.get()
        if job is None:
            break
        sid, index, audio, vocabulary = job
        if vocabulary == 'slow':
            output.send(('status', 'busy'))
            time.sleep(.3)
        # Deliberately send stale replies too: the parent must reject them.
        output.send(('result', sid, index, str(audio), .01))
    output.send(('stopped',))


def crashing_worker(jobs, output, session):
    output.send(('ready',))
    time.sleep(.1)
    os._exit(23)


def stuck_worker(jobs, output, session):
    output.send(('ready',))
    time.sleep(60)


class Channel:
    def __init__(self):
        self.messages = queue.Queue()

    def emit(self, *values):
        self.messages.put(values)

    def get(self):
        return self.messages.get(timeout=10)


class Sink:
    def __init__(self):
        for name in ('status', 'ready', 'result', 'error'):
            setattr(self, name, Channel())


class InferenceProcessTests(unittest.TestCase):
    def create(self, target=echo_worker):
        sink = Sink()
        worker = Inference(sink, worker_target=target)
        self.addCleanup(worker.close)
        sink.ready.get()
        return worker, sink

    def test_inference_runs_in_another_process_and_returns_result(self):
        worker, sink = self.create()
        self.assertNotEqual(worker.process.pid, os.getpid())
        worker.session = 7
        worker.submit(7, 3, 'example')
        self.assertEqual(sink.result.get(), (7, 3, True, 'example', .01))

    def test_cancel_discards_late_reply_and_next_session_still_works(self):
        worker, sink = self.create()
        worker.session = 1
        worker.vocabulary = 'slow'
        worker.submit(1, 0, 'canceled')
        self.assertEqual(sink.status.get(), ('busy',))
        worker.session = 2
        worker.vocabulary = ''
        worker.submit(2, 0, 'current')
        self.assertEqual(sink.result.get(), (2, 0, True, 'current', .01))
        self.assertTrue(sink.result.messages.empty())

    def test_crashed_child_is_reported_without_hanging_receiver(self):
        worker, sink = self.create(crashing_worker)
        self.assertTrue(sink.error.get()[0])
        worker.thread.join(timeout=2)
        self.assertFalse(worker.thread.is_alive())
        self.assertFalse(worker.ready)

    def test_quit_terminates_unresponsive_child_and_is_idempotent(self):
        worker, sink = self.create(stuck_worker)
        worker.close()
        worker.close()
        self.assertFalse(worker.process.is_alive())
        self.assertFalse(worker.thread.is_alive())

    def test_quit_immediately_after_launch_leaves_no_child(self):
        worker = Inference(Sink(), worker_target=echo_worker)
        worker.close()
        if worker.process.pid is not None:
            self.assertFalse(worker.process.is_alive())
        self.assertFalse(worker.thread.is_alive())


if __name__ == '__main__':
    unittest.main()
