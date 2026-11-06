"""Kokoro-82M built in (Apache-2.0 model, MIT kokoro-onnx). Runs on the CPU
inside Blender. Model files (~120 MB) download once from the kokoro-onnx
GitHub release into <home>/models."""
import urllib.request

from .. import config

ID, LABEL, LICENCE = "kokoro", "Kokoro 82M (built in)", "Apache-2.0"
SR = 24000
_K = None


def _files():
    s = config.settings()
    m = config.models_dir()
    return s, m / s["kokoro_model"], m / s["kokoro_voices"]


def download():
    s, model, voices = _files()
    for p in (model, voices):
        if not p.exists() or p.stat().st_size < 1_000_000:
            tmp = p.with_suffix(p.suffix + ".part")
            urllib.request.urlretrieve(s["kokoro_url"] + p.name, tmp)
            tmp.replace(p)
    return model, voices


def available():
    config.add_pydeps()
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        return False, "kokoro-onnx isn't installed (run install/install_sushi.ps1)"
    _, model, voices = _files()
    if not (model.exists() and voices.exists()):
        return True, "ready (model downloads on first line)"
    return True, "ready"


def _engine():
    global _K
    if _K is None:
        config.add_pydeps()
        from kokoro_onnx import Kokoro
        model, voices = download()
        _K = Kokoro(str(model), str(voices))
    return _K


def voices():
    return sorted(_engine().get_voices())


def synth(reqs):
    k = _engine()
    out = []
    for r in reqs:
        voice = r.get("voice") or "am_michael"
        lang = "en-gb" if voice[:1] == "b" else "en-us"
        a, sr = k.create(r["text"], voice=voice, speed=float(r.get("speed", 1.0)), lang=lang)
        out.append((a.astype("float64"), sr))
    return out
