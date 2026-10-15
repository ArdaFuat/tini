"""Repeatable local performance checks. Output words stay in ignored runtime files."""
import argparse
import json
import os
from pathlib import Path
import statistics
import time

ROOT=Path(__file__).resolve().parent


def draw_benchmark():
    os.environ['QT_QPA_PLATFORM']='offscreen'
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    from orb import Orb
    app=QApplication.instance() or QApplication([])
    orb=Orb(QSettings(str(ROOT/'runtime/benchmark.ini'),QSettings.Format.IniFormat))
    orb.show();orb.timer.stop()
    result={}
    for mode in ('idle','recording'):
        orb.set_mode(mode);orb.timer.stop()
        orb.expansion=0 if mode=='idle' else 1
        orb.color=orb.color_target
        orb.level=0 if mode=='idle' else .65
        orb.clearMask()
        samples=[]
        for frame in range(140):
            orb.phase=frame*.03
            start=time.perf_counter()
            orb.grab()
            if frame>=20:samples.append((time.perf_counter()-start)*1000)
        result[mode]={'median_ms':round(statistics.median(samples),3),
                      'p95_ms':round(sorted(samples)[int(.95*len(samples))-1],3)}
    orb.hide()
    return result


def speech_benchmark():
    import numpy as np
    from scipy.io import wavfile
    from engine import load_model,transcribe
    model=load_model()
    result=[]
    for audio_path in sorted((ROOT/'runtime').glob('perf-sample-*.wav')):
        rate,audio=wavfile.read(audio_path)
        assert rate==16000
        audio=audio.astype(np.float32)/32768
        if audio.ndim>1:audio=audio.mean(axis=1)
        timings=[];outputs=[]
        for _ in range(4):
            text,elapsed=transcribe(model,audio)
            timings.append(round(elapsed*1000,3));outputs.append(text)
        result.append({'sample':audio_path.name,'audio_seconds':len(audio)/rate,
                       'median_ms':round(statistics.median(timings[1:]),3),
                       'runs_ms':timings,'outputs':outputs})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('kind',choices=['draw','speech'])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=draw_benchmark() if args.kind=='draw' else speech_benchmark()
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if args.kind=='speech':
        for row in result:row.pop('outputs')
    print(json.dumps(result,ensure_ascii=False))
