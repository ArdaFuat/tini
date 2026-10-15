"""Keep speech inference's Python/GIL work out of the animation process."""
import logging
import multiprocessing as mp
from multiprocessing.connection import wait
import threading

from inference_worker import run_worker


class Inference:
    def __init__(self, events, *, worker_target=run_worker):
        self.events = events
        context = mp.get_context('spawn')
        self.jobs = context.Queue()
        self._session = context.Value('q', 0)
        self._reader, self._writer = context.Pipe(duplex=False)
        self.process = context.Process(target=worker_target,
            args=(self.jobs, self._writer, self._session), name='TiniSpeech', daemon=True)
        self.vocabulary = ''
        self.stopping = False
        self.ready = False
        self.thread = threading.Thread(target=self.run, name='TiniSpeechEvents', daemon=True)
        self.thread.start()

    @property
    def session(self):
        return self._session.value

    @session.setter
    def session(self, value):
        self._session.value = value

    def submit(self, session, index, audio):
        if not self.stopping:
            # Queue's feeder handles serialization outside the GUI thread.
            self.jobs.put((session, index, audio, self.vocabulary))

    def run(self):
        try:
            if self.stopping:
                return
            self.process.start()
            self._writer.close()
            while True:
                available = wait([self._reader, self.process.sentinel])
                if self._reader in available:
                    try:
                        message = self._reader.recv()
                    except EOFError:
                        self.ready = False
                        if not self.stopping:
                            self.events.error.emit('Ses motoruyla bağlantı kesildi. Tını’yı yeniden aç.')
                        break
                    kind = message[0]
                    if kind == 'stopped':
                        break
                    if self.stopping:
                        continue
                    if kind == 'status':
                        self.events.status.emit(message[1])
                    elif kind == 'ready':
                        self.ready = True
                        self.events.ready.emit()
                    elif kind == 'result':
                        _, session, index, text, elapsed = message
                        if session == self.session:
                            self.events.result.emit(session, index, True, text, elapsed)
                    elif kind == 'error':
                        self.ready = False
                        self.events.error.emit(f'Model hatası: {message[1]}')
                elif self.process.sentinel in available:
                    self.ready = False
                    if not self.stopping:
                        self.events.error.emit('Ses motoru beklenmedik şekilde kapandı. Tını’yı yeniden aç.')
                    break
        except Exception as error:
            logging.exception('Speech process connection failed')
            if not self.stopping:
                self.events.error.emit(f'Ses motoru başlatılamadı: {error}')
        finally:
            self.ready = False
            self._reader.close()
            self._writer.close()

    def close(self):
        if self.stopping:
            return
        self.stopping = True
        self.ready = False
        self.session += 1
        self.jobs.put(None)
        self.thread.join(timeout=2)
        if self.process.pid is not None:
            self.process.join(timeout=.5)
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
        self.thread.join(timeout=1)
        # A canceled queue must never keep Python alive while exiting.
        self.jobs.cancel_join_thread()
        self.jobs.close()

