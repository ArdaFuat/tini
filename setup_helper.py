"""Installer checks and model download; never starts recording or loads GPU weights."""
import importlib.metadata
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def packages_ready():
    for line in (ROOT / 'requirements.txt').read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, version = line.strip().split('==')
        try:
            if importlib.metadata.version(name) != version:
                return False
        except importlib.metadata.PackageNotFoundError:
            return False
    return True


def check_gpu():
    from engine import configure_cuda
    configure_cuda()
    import ctranslate2
    if not ctranslate2.get_cuda_device_count():
        raise RuntimeError('CUDA destekli NVIDIA ekran kartı bulunamadı. NVIDIA sürücüsünü kontrol et.')


def prepare_model():
    from faster_whisper.utils import download_model
    # Same cache and model resolution as engine.py; already downloaded files are reused.
    cache = str(ROOT / '.models')
    try:
        snapshot = Path(download_model('large-v3-turbo', cache_dir=cache, local_files_only=True))
        if all((snapshot / name).is_file() for name in ('model.bin', 'config.json', 'tokenizer.json')):
            return str(snapshot)
    except FileNotFoundError:
        pass
    return download_model('large-v3-turbo', cache_dir=cache)


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'packages':
        sys.exit(0 if packages_ready() else 1)
    elif action == 'gpu':
        check_gpu()
    elif action == 'model':
        prepare_model()
    else:
        raise SystemExit('Unknown installer action')
