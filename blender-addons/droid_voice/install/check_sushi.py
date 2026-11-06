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

LINE = "Day four hundred and twelve. Still no plan. [sigh]"
rep = {"status": {k: list(v) for k, v in engines.status().items()}, "lines": []}
for eng, droid in [("kokoro", "hazard"), ("espeak", "rx07"), ("voicebox:qwen_voice_design", "hazard"),
                   ("voicebox:chatterbox_turbo", "drone"), ("dia2", "hazard"), ("zonos", "computer"),
                   ("orpheus", "drone"), ("openvoice", "computer")]:
    t0 = time.time()
    try:
        c = voice.speak(droid, LINE, engine=eng, refresh=True)
        rep["lines"].append({"engine": eng, "droid": droid, "ok": True, "secs": round(time.time() - t0, 1),
                             "robot": c["robot"], "duration": round(c["duration"], 2)})
    except Exception as e:
        rep["lines"].append({"engine": eng, "droid": droid, "ok": False, "error": str(e)[-400:],
                             "trace": traceback.format_exc()[-800:]})
out = config.home() / "check_report.json"
out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
print(json.dumps(rep, indent=2))
