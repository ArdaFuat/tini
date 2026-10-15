"""Local CUDA transcription; no audio leaves this process."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DLL_HANDLES = []
CUDA_CONFIGURED = False


def configure_cuda():
    global CUDA_CONFIGURED
    if CUDA_CONFIGURED:
        return
    # NVIDIA wheels ship DLLs but Windows does not automatically search here.
    for root in (Path(sys.prefix) / 'Lib' / 'site-packages' / 'nvidia',):
        if root.exists():
            for folder in root.rglob('bin'):
                if folder.is_dir():
                    os.environ['PATH'] = str(folder) + os.pathsep + os.environ.get('PATH', '')
                    DLL_HANDLES.append(os.add_dll_directory(str(folder)))
    CUDA_CONFIGURED = True


def load_model(status=lambda message: None):
    configure_cuda()
    import ctranslate2
    from faster_whisper import WhisperModel
    if not ctranslate2.get_cuda_device_count():
        raise RuntimeError('NVIDIA GPU bulunamadı. CPU üzerinde sessizce yavaş moda geçilmedi.')
    status('Turbo modeli hazırlanıyor · İlk açılışta yaklaşık 1,6 GB indirilir')
    cached = list((ROOT / '.models' / 'models--mobiuslabsgmbh--faster-whisper-large-v3-turbo' / 'snapshots').glob('*/model.bin'))
    source = str(cached[0].parent) if cached else 'large-v3-turbo'
    model = WhisperModel(source, device='cuda', compute_type='float16',
                         download_root=str(ROOT / '.models'), cpu_threads=4, num_workers=1)
    status('Ekran kartı ısınıyor…')
    import numpy as np
    # Force the CUDA kernels and libraries to load before the first dictation.
    segments, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language='tr',
                                   beam_size=1, condition_on_previous_text=False)
    list(segments)
    return model


def transcribe(model, audio, *, final=True, vocabulary=''):
    started = time.perf_counter()
    segments, _ = model.transcribe(
        audio, language='tr', task='transcribe', beam_size=3 if final else 1,
        temperature=0, condition_on_previous_text=False,
        initial_prompt=vocabulary or None, vad_filter=True,
        vad_parameters={'min_silence_duration_ms': 350, 'speech_pad_ms': 180},
        no_speech_threshold=0.6, hallucination_silence_threshold=1.0,
        max_new_tokens=224 if final else 128,
    )
    # Reject low confidence and repetitive noise/music hallucinations.
    text = ' '.join(segment.text.strip() for segment in segments
                    if segment.compression_ratio < 2.4 and segment.avg_logprob > -1.0
                    and segment.no_speech_prob < 0.75).strip()
    return text, time.perf_counter() - started


if __name__ == '__main__':
    import argparse
    import json
    import numpy as np
    from scipy.io import wavfile
    parser = argparse.ArgumentParser()
    parser.add_argument('--audio', type=Path)
    args = parser.parse_args()
    start = time.perf_counter()
    model = load_model(print)
    print(f'CUDA READY in {time.perf_counter()-start:.2f}s', flush=True)
    if args.audio:
        if args.audio.suffix.lower() == '.wav':
            from scipy.signal import resample_poly
            import math
            rate, audio = wavfile.read(args.audio)
            if audio.dtype.kind in 'iu':
                audio = audio.astype(np.float32) / max(abs(np.iinfo(audio.dtype).min), np.iinfo(audio.dtype).max)
            audio = audio.astype(np.float32)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if rate != 16000:
                divisor = math.gcd(rate, 16000)
                audio = resample_poly(audio, 16000//divisor, rate//divisor).astype(np.float32)
        else:
            from faster_whisper.audio import decode_audio
            audio = decode_audio(str(args.audio), sampling_rate=16000)
        # Keep the user's private words out of terminal output and reports.
        runs = []
        for _ in range(3):
            result, elapsed = transcribe(model, audio)
            runs.append(round(elapsed, 3))
        report = {'device': 'cuda', 'compute_type': 'float16', 'model': 'large-v3-turbo',
                  'audio_seconds': round(len(audio)/16000, 3), 'runs_seconds': runs,
                  'output_characters': len(result)}
        (ROOT / 'benchmark.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)
