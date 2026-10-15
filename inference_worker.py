"""Speech-only child process. No Qt, windows, microphone capture or text insertion."""
import logging
from logging.handlers import RotatingFileHandler

from engine import ROOT, load_model, transcribe


def run_worker(jobs, output, current_session):
    (ROOT / 'runtime').mkdir(exist_ok=True)
    handler = RotatingFileHandler(ROOT/'runtime'/'worker.log', maxBytes=1024*1024,
                                  backupCount=2, encoding='utf-8')
    logging.basicConfig(handlers=[handler], level=logging.WARNING, force=True)
    logging.getLogger('faster_whisper').setLevel(logging.WARNING)
    try:
        model = load_model(lambda message: output.send(('status', message)))
        output.send(('ready',))
        while True:
            job = jobs.get()
            if job is None:
                break
            session, index, audio, vocabulary = job
            if session != current_session.value:
                del audio, job
                continue
            text, elapsed = transcribe(model, audio, final=True, vocabulary=vocabulary)
            if session == current_session.value:
                output.send(('result', session, index, text, elapsed))
            del audio, job, text
    except Exception as error:
        logging.exception('Speech worker failed')
        try:
            output.send(('error', str(error)))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        try:
            output.send(('stopped',))
        except (BrokenPipeError, EOFError, OSError):
            pass
        output.close()

