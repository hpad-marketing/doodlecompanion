"""After install: voice one line per droid with every engine that's ready and
write a report. Run with Blender's Python or plain Python 3.10+:
    python install/check_sushi.py   (from blender-addons/droid_voice/..)"""
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from droid_voice import config, engines, voice  # noqa: E402

import subprocess  # noqa: E402
import threading  # noqa: E402


def vram_mb():
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10).stdout
        return int(o.split()[0])
    except Exception:
        return None


class Peak:
    """Polls nvidia-smi while a line is voiced; VRAM peak over the start level.
    Voicebox keeps its models in its own process, so its number is the
    increase while that line ran (plus the earlier load, in vram_start_mb)."""
    def __init__(self):
        self.start = vram_mb()
        self.peak = self.start
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def _run(self):
        while not self._stop.wait(0.5):
            v = vram_mb()
            if v is not None and (self.peak is None or v > self.peak):
                self.peak = v

    def done(self):
        self._stop.set()
        self._t.join(2)
        return self.start, self.peak


LINE = "Day four hundred and twelve. Still no plan. [sigh]"
rep = {"status": {k: list(v) for k, v in engines.status().items()}, "vram_baseline_mb": vram_mb(), "lines": []}
for eng, droid in [("kokoro", "hazard"), ("espeak", "rx07"), ("voicebox:qwen_voice_design", "hazard"),
                   ("voicebox:chatterbox_turbo", "drone"), ("dia2", "hazard"), ("zonos", "computer"),
                   ("orpheus", "drone"), ("openvoice", "computer")]:
    t0 = time.time()
    pk = Peak()
    try:
        c = voice.speak(droid, LINE, engine=eng, refresh=True)
        first = round(time.time() - t0, 1)
        # second line: model already loaded (GPU runners reload per batch, so it shows load + generate)
        t1 = time.time()
        voice.speak(droid, "Hull integrity is fine. Morale is not my department.", engine=eng, refresh=True)
        s, p = pk.done()
        rep["lines"].append({"engine": eng, "droid": droid, "ok": True, "secs": first,
                             "secs_second_line": round(time.time() - t1, 1),
                             "vram_start_mb": s, "vram_peak_mb": p,
                             "vram_delta_mb": (p - s) if (s is not None and p is not None) else None,
                             "robot": c["robot"], "duration": round(c["duration"], 2)})
    except Exception as e:
        s, p = pk.done()
        rep["lines"].append({"engine": eng, "droid": droid, "ok": False, "secs": round(time.time() - t0, 1),
                             "vram_start_mb": s, "vram_peak_mb": p, "error": str(e)[-400:],
                             "trace": traceback.format_exc()[-800:]})
    print(json.dumps(rep["lines"][-1])[:600], flush=True)
out = config.home() / "check_report.json"
out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
print(json.dumps(rep, indent=2))
