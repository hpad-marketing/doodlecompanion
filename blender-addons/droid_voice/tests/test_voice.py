"""Droid Voice tests that run without Blender or a GPU.

    python tests/test_voice.py            (from blender-addons/)

Uses Kokoro for real speech (needs kokoro-onnx; model files are fetched or
taken from $KOKORO_DIR), a fake Voicebox server for the REST path, and fake
runner programs for the Dia2/Zonos runner contract. Writes listening copies to
$DV_TEST_OUT if set."""
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))     # blender-addons/

HOME = tempfile.mkdtemp(prefix="dv_home_")
os.environ["DROID_VOICE_HOME"] = HOME
if os.environ.get("KOKORO_DIR"):
    os.makedirs(os.path.join(HOME, "models"), exist_ok=True)
    for f in ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin"):
        src = os.path.join(os.environ["KOKORO_DIR"], f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(HOME, "models", f))

from droid_voice import cast, config, engines, mcp, robotfx, script, voice, wavio  # noqa: E402

FAILS = []


def check(name, cond, info=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({info})" if info else ""))
    if not cond:
        FAILS.append(name)


# ------------------------------------------------------------ fake Voicebox
CALLS = []


def _tone(sec=1.2, hz=180, sr=24000):
    t = np.arange(int(sec * sr)) / sr
    env = (np.sin(np.pi * t * 4) > 0).astype(float)          # 4 "syllables"
    return 0.4 * np.sin(2 * np.pi * hz * t) * env, sr


class VB(http.server.BaseHTTPRequestHandler):
    profiles = []

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        CALLS.append(("GET", self.path, None))
        if self.path == "/profiles":
            return self._send(200, VB.profiles)
        self._send(404, {"detail": "nf"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        ct = self.headers.get("Content-Type", "")
        body = json.loads(raw) if ct.startswith("application/json") else raw
        CALLS.append(("POST", self.path, body))
        if self.path == "/profiles":
            p = dict(body, id=f"p{len(VB.profiles)}")
            VB.profiles.append(p)
            return self._send(200, p)
        if self.path.endswith("/samples"):
            ok = b'name="reference_text"' in raw and b'name="file"' in raw and b"RIFF" in raw
            return self._send(200 if ok else 422, {"ok": ok})
        if self.path == "/v1/audio/speech":
            import io
            a, sr = _tone()
            buf = io.BytesIO()
            import wave
            with wave.open(buf, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
                w.writeframes((a * 32767).astype("<i2").tobytes())
            return self._send(200, buf.getvalue(), "audio/wav")
        self._send(404, {"detail": "nf"})


def start_vb():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), VB)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


FAKE_RUNNER = r'''
import json, sys, wave
import numpy as np
job = json.load(open(sys.argv[1]))
def w(path, sec, hz):
    sr = 22050; t = np.arange(int(sec*sr))/sr
    a = 0.4*np.sin(2*np.pi*hz*t)*(np.sin(np.pi*t*3) > 0)
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr); f.writeframes((a*32767).astype("<i2").tobytes())
for i, l in enumerate(job["lines"]):
    for k, o in enumerate(l.get("outs") or [l["out"]]):
        w(o, 0.8 + 0.2*k, 150 + 40*k)
print("ran", job["engine"], len(job["lines"]))
'''


def main():
    out_dir = os.environ.get("DV_TEST_OUT")
    # --- robotfx
    a, sr = _tone(2.0)
    for ch in robotfx.CHAINS:
        y = robotfx.process(a, ch, size_m=1.5, hollow=0.4, glitch_amount=0.5, seed=3)
        check(f"chain {ch} keeps length", abs(len(y) - len(a)) <= 2, f"{len(y)} vs {len(a)}")
        check(f"chain {ch} finite + audible", np.isfinite(y).all() and np.abs(y).max() > 0.1)
    ps = robotfx.pitch_shift(a, 4)
    check("pitch shift keeps duration", len(ps) == len(a))
    beeps = robotfx.cadence_beeps(a)
    on, off = np.abs(beeps[int(0.05 * sr):int(0.2 * sr)]).mean(), np.abs(beeps[int(0.27 * sr):int(0.47 * sr)]).mean()
    check("beeps pause where speech pauses", on > 5 * off, f"on {on:.3f} off {off:.4f}")

    # --- script
    items = script.parse("HAZARD: Still no plan. [sigh]\n[Drone zooms in]\n(beat)\nDrone: A button!\n  I'm pressing it.\n")
    check("script parse", [i["kind"] for i in items] == ["line", "action", "beat", "line"], str(items))
    check("wrapped line joins", items[3]["text"] == "A button! I'm pressing it.")
    check("tags per engine", script.convert_tags("No. [laugh] Fine.", "paren") == "No. (laughs) Fine."
          and script.convert_tags("No. [laugh] Fine.", "angle") == "No. <laugh> Fine."
          and script.convert_tags("No. [laugh] Fine.", "strip") == "No. Fine.")

    # --- engine status with nothing running
    st = engines.status()
    check("status lists every engine", set(st) >= {"kokoro", "espeak", "voicebox", "dia2", "zonos", "orpheus", "openvoice"})
    check("voicebox off -> not ok", st["voicebox"][0] is False)

    # --- Kokoro fallback voices every droid
    for d in ["hazard", "drone", "computer", "rx07"]:
        c = voice.speak(d, "Hull integrity is fine. Morale is not my department.")
        check(f"{d} voiced via fallback", c["engine"] == "kokoro" and os.path.exists(c["robot"]), c["engine"])
        check(f"{d} lipsync frames", abs(len(c["lipsync"]["level"]) - c["duration"] * 24) < 3)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            shutil.copy(c["robot"], os.path.join(out_dir, f"{d}_robot.wav"))
    c2 = voice.speak("hazard", "Hull integrity is fine. Morale is not my department.")
    check("cache hit", c2["cached"] is True)
    tk = voice.takes("drone", "Ooh! A button!")
    sigs = [hash(wavio.read(t["dry"])[0][:24000].round(3).tobytes()) for t in tk]
    check("3 takes differ", len(set(sigs)) == 3, str([round(t["duration"], 3) for t in tk]))
    g = voice.speak("computer", "Guide track.", clean=True)
    check("clean guide = dry", g["robot"] == g["dry"])

    # --- whole script
    v = voice.voice_script("HAZARD: Day four hundred and twelve. Still no plan.\n[Drone enters]\n"
                           "DRONE: Ooh! A button!\n(beat)\nRX-07: Who moved my charging pad?\n")
    starts = [l["start_s"] for l in v["lines"]]
    check("script voiced in order", len(v["lines"]) == 3 and starts == sorted(starts) and v["actions"])
    check("beat adds a pause", starts[2] - (starts[1] + v["lines"][1]["duration"]) > 0.9)

    # --- booth
    rec = os.path.join(HOME, "my_take.wav")
    wavio.write(rec, *_tone(1.5, 140))
    b = voice.booth(rec, "hazard")
    check("booth robotises a recording", os.path.exists(b["robot"]) and b["engine"] == "booth")

    # --- Voicebox path (fake server)
    srv = start_vb()
    s = config.settings()
    s["voicebox_url"] = f"http://127.0.0.1:{srv.server_address[1]}"
    config.save_settings(s)
    check("voicebox up -> ok", engines.status()["voicebox"][0])
    c = voice.speak("hazard", "Designed voice line.")
    check("hazard prefers Qwen voice design", c["engine"] == "voicebox:qwen_voice_design", c["engine"])
    made = [b for (m, p, b) in CALLS if m == "POST" and p == "/profiles"]
    check("designed profile created", made and made[0]["voice_type"] == "designed" and made[0]["design_prompt"])
    sp = [b for (m, p, b) in CALLS if p == "/v1/audio/speech"][-1]
    check("speech call uses engine + profile", sp["model"] == "qwen_voice_design" and sp["voice"] == "Droid - Hazard")
    c = voice.speak("drone", "Cloned voice line. [laugh]", engine="voicebox:chatterbox_turbo")
    sp = [b for (m, p, b) in CALLS if p == "/v1/audio/speech"][-1]
    check("chatterbox keeps [laugh]", "[laugh]" in sp["input"], sp["input"])
    check("clone sample uploaded", any(p.endswith("/samples") for (m, p, b) in CALLS))
    voice.speak("hazard", "Designed voice line again.")
    check("profile made once", len([1 for (m, p, b) in CALLS if m == "POST" and p == "/profiles"]) == 2)
    srv.shutdown()
    s["voicebox_url"] = "http://127.0.0.1:9"
    config.save_settings(s)

    # --- runner contract (fake engines)
    rpath = os.path.join(HOME, "fake_runner.py")
    open(rpath, "w").write(FAKE_RUNNER)
    s = config.settings()
    s["runners"] = {"zonos": {"cmd": [sys.executable, rpath]}, "dia2": {"cmd": [sys.executable, rpath]}}
    config.save_settings(s)
    c = voice.speak("computer", "Runner line.", engine="zonos")
    check("runner engine voices a line", c["engine"] == "zonos" and os.path.exists(c["robot"]))
    v = voice.voice_script("HAZARD: You pressed it.\nDRONE: I pressed it! [laugh]\nHAZARD: Of course you did.\n",
                           dialogue_engine="dia2")
    check("dia2 run voices the exchange", [l["engine"] for l in v["lines"]] == ["dia2"] * 3,
          str([l["engine"] for l in v["lines"]]))
    check("dia2 turns keep their droid chain", [l["droid"] for l in v["lines"]] == ["hazard", "drone", "hazard"])

    # --- MCP
    r = mcp.handle({"action": "speak", "droid": "rx-07", "text": "Beep test.", "engine": "kokoro"})
    check("mcp speak", r["droid"] == "rx07" and r["frames"] > 0)
    check("mcp status", "kokoro" in mcp.handle({"action": "status"}))

    # --- new droid joins
    cast.register_droid("loader", "Tread loader", 2.6, voice="am_onyx")
    c = voice.speak("tread loader", "Lifting.")
    check("registered droid speaks", c["droid"] == "loader")

    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
