"""Where Droid Voice keeps models, runners and its line cache.

Home folder, in order:
  1. env DROID_VOICE_HOME
  2. <Documents>/DeepInDoodles/_voice   (Sushi and the work PC)
  3. ~/.droid_voice
Settings live in <home>/settings.json and can be edited by hand.
"""
import json
import os
import sys
from pathlib import Path


def home():
    env = os.environ.get("DROID_VOICE_HOME")
    if env:
        p = Path(env)
    else:
        docs = Path.home() / "Documents" / "DeepInDoodles"
        p = docs / "_voice" if docs.is_dir() else Path.home() / ".droid_voice"
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULTS = {
    "voicebox_url": "http://127.0.0.1:17493",
    "espeak": "espeak-ng",               # exe name or full path
    "kokoro_model": "kokoro-v1.0.int8.onnx",
    "kokoro_voices": "voices-v1.0.bin",
    "kokoro_url": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/",
    # External engines run in their own Python env, one process per batch.
    # "cmd" gets the job.json path appended. Filled in by install/install_sushi.ps1.
    "runners": {},
    "timeout_s": 900,
}


def settings():
    s = json.loads(json.dumps(DEFAULTS))
    f = home() / "settings.json"
    if f.exists():
        try:
            # utf-8-sig: PowerShell 5.1 (install_sushi.ps1) writes a BOM
            s.update(json.loads(f.read_text(encoding="utf-8-sig")))
        except ValueError:
            pass
    return s


def save_settings(s):
    (home() / "settings.json").write_text(json.dumps(s, indent=2), encoding="utf-8")


def cache_dir():
    p = home() / "lines"
    p.mkdir(exist_ok=True)
    return p


def models_dir():
    p = home() / "models"
    p.mkdir(exist_ok=True)
    return p


def add_pydeps():
    """Extra Python packages for Blender (kokoro-onnx, onnxruntime) are
    installed with pip --target into <home>/pydeps so Blender's own
    site-packages are never touched."""
    d = home() / "pydeps"
    if d.is_dir() and str(d) not in sys.path:
        sys.path.append(str(d))
    return d
