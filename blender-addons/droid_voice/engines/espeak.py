"""Classic formant robot through eSpeak NG (GPL-3). Called as a separate
program, so nothing GPL is linked into the add-on."""
import os
import shutil
import subprocess
import tempfile

from .. import config, wavio

ID, LABEL, LICENCE = "espeak", "eSpeak NG (classic robot)", "GPL-3.0 (separate program)"

_WIN_PATHS = [r"C:\Program Files\eSpeak NG\espeak-ng.exe", r"C:\Program Files (x86)\eSpeak NG\espeak-ng.exe"]


def exe():
    e = config.settings()["espeak"]
    found = shutil.which(e)
    if found:
        return found
    for p in _WIN_PATHS:
        if os.path.exists(p):
            return p
    return None


def available():
    return (True, "ready") if exe() else (False, "eSpeak NG isn't installed")


def synth(reqs):
    out = []
    for r in reqs:
        voice = r.get("voice") or "en-us+m3"
        wpm = int(175 * float(r.get("speed", 1.0)))
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            subprocess.run([exe(), "-v", voice, "-s", str(wpm), "-w", tmp, r["text"]],
                           check=True, capture_output=True, timeout=60)
            out.append(wavio.read(tmp))
        finally:
            os.remove(tmp)
    return out
