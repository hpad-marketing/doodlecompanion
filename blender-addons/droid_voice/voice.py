"""Voicing lines: engine choice, takes, cache, robot chain, lip-sync curve."""
import hashlib
import json
import os

import numpy as np

from . import cast as castmod
from . import config, engines, lipsync, robotfx, script, wavio

TAKES = 3
_SPEED_JITTER = (1.0, 0.92, 1.12)     # deterministic engines vary takes by pace


class Clip(dict):
    """dict with: droid, text, engine, take, dry, robot (wav paths), duration,
    lipsync {fps, level[], on[], accents[]}, cached."""


def _key(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def pick_engine(entry, force=None):
    """First engine in the droid's list that works on this PC."""
    prefs = entry["engines"]
    if force:
        prefs = [p for p in prefs if p["engine"] == force] or [{"engine": force}]
    why = []
    for p in prefs:
        mod, _ = engines.get(p["engine"])
        ok, reason = mod.available()
        if ok:
            return p
        why.append(f"{p['engine']}: {reason}")
    raise RuntimeError("No voice engine available. " + "; ".join(why))


def _voicebox_profile(entry, pref):
    """Make sure the droid has its Voicebox profile; returns the profile name."""
    from .engines import voicebox
    sub = pref["engine"].split(":", 1)[1]
    name = pref.get("profile") or f"Droid - {entry['name']}"
    sample = text = None
    if sub in ("chatterbox", "chatterbox_turbo", "qwen", "luxtts", "tada") and pref.get("clone_from"):
        # Cloning engines need a sample: speak one with the droid's base voice.
        text = "Systems nominal. I have checked everything twice and I still do not like it."
        src = pref["clone_from"]
        mod, _ = engines.get(src["engine"])
        a, sr = mod.synth([{"text": text, "voice": src.get("voice")}])[0]
        sample = str(config.cache_dir() / f"_sample_{_key(name)}.wav")
        wavio.write(sample, a, sr)
    voicebox.ensure_profile(name, sub, design_prompt=pref.get("design"), preset_voice=pref.get("voice"),
                            sample_wav=sample, sample_text=text)
    return name


def _request(entry, pref, text, take, seed):
    style = engines.TAG_STYLE.get(pref["engine"], "strip")
    speed = float(pref.get("speed", 1.0))
    if pref["engine"] in ("kokoro", "espeak", "voicebox:kokoro"):
        speed *= _SPEED_JITTER[take % len(_SPEED_JITTER)]
    r = {"text": script.convert_tags(text, style), "voice": pref.get("voice"), "speed": speed,
         "seed": seed, "instruct": pref.get("instruct"), "emotion": pref.get("emotion"),
         "ref_wav": pref.get("ref_wav")}
    if pref["engine"].startswith("voicebox:"):
        r["engine"] = pref["engine"].split(":", 1)[1]
        r["voice"] = _voicebox_profile(entry, pref)
    return r


def _finish(droid_id, entry, text, engine_id, take, seed, audio, sr, fps, folder, key, dry_only=False):
    dry = os.path.join(folder, f"{key}_dry.wav")
    wavio.write(dry, audio, sr)
    a24 = robotfx.to_rate(audio, sr, robotfx.SR)
    if dry_only:
        robot, rob_path = a24, dry
    else:
        robot = robotfx.process(a24, entry.get("chain", "crush"), strength=entry.get("strength", 1.0),
                                size_m=entry.get("size_m"), hollow=entry.get("hollow", 0.0),
                                glitch_amount=entry.get("glitch", 0.0), seed=seed, **entry.get("dials", {}))
        rob_path = os.path.join(folder, f"{key}_robot.wav")
        wavio.write(rob_path, robot, robotfx.SR)
    # Lights follow what you hear: beeps drive from the beeps, speech from the dry voice.
    src = robot if entry.get("chain") == "beeps" else a24
    clip = Clip(droid=droid_id, name=entry["name"], text=text, caption=script.spoken(text), engine=engine_id,
                take=take, seed=seed, dry=dry, robot=rob_path, duration=len(robot) / robotfx.SR,
                lipsync=lipsync.curve(src, robotfx.SR, fps), cached=False)
    with open(os.path.join(folder, f"{key}.json"), "w", encoding="utf-8") as f:
        json.dump(clip, f)
    return clip


def speak(droid, text, take=0, engine=None, fps=24, refresh=False, clean=False):
    """Voice one line for a droid. Same droid + text + take = same file (cached).
    ``take`` 0..2 gives different deliveries. ``clean`` skips the robot chain
    (a guide track to record over)."""
    cast = castmod.load()
    droid_id, entry = castmod.find(droid, cast)
    pref = pick_engine(entry, engine)
    seed = int(_key(droid_id, text, take), 16) % (2 ** 31)
    key = _key(droid_id, text, take, pref, entry.get("chain"), entry.get("dials"), entry.get("size_m"),
               entry.get("hollow"), entry.get("glitch"), entry.get("strength"), clean, fps)
    folder = str(config.cache_dir() / droid_id)
    os.makedirs(folder, exist_ok=True)
    meta = os.path.join(folder, f"{key}.json")
    if os.path.exists(meta) and not refresh:
        with open(meta, encoding="utf-8") as f:
            c = Clip(json.load(f))
        c["cached"] = True
        return c
    mod, sub = engines.get(pref["engine"])
    req = _request(entry, pref, text, take, seed)
    a, sr = (mod.synth([req], engine=sub) if sub else mod.synth([req]))[0]
    return _finish(droid_id, entry, text, pref["engine"], take, seed, a, sr, fps, folder, key, dry_only=clean)


def takes(droid, text, n=TAKES, **kw):
    return [speak(droid, text, take=t, **kw) for t in range(n)]


def booth(wav_path, droid, fps=24):
    """Run your own recording through the droid's chain, so it matches the
    generated lines."""
    droid_id, entry = castmod.find(droid)
    a, sr = wavio.read(wav_path)
    folder = str(config.cache_dir() / droid_id)
    os.makedirs(folder, exist_ok=True)
    st = os.stat(wav_path)
    key = "booth_" + _key(os.path.abspath(wav_path), st.st_mtime, st.st_size, entry)
    text = os.path.splitext(os.path.basename(wav_path))[0]
    return _finish(droid_id, entry, text, "booth", 0, 0, a, sr, fps, folder, key)


def voice_script(text, fps=24, gap_s=0.35, beat_s=0.8, dialogue_engine=None, takes_by_line=None):
    """Voice a whole sitcom script. Returns {"lines": [clip + start_s], "length_s",
    "actions": [...]}. ``dialogue_engine="dia2"`` voices back-and-forth runs
    between two droids in one pass (natural timing), then each turn still gets
    its own droid's robot chain. ``takes_by_line`` {index: take} picks takes."""
    items = script.parse(text)
    takes_by_line = takes_by_line or {}
    out, actions, t = [], [], 0.0
    pre = {}
    if dialogue_engine == "dia2":
        pre = _dia2_runs(items, fps)
    for i, it in enumerate(items):
        if it["kind"] == "beat":
            t += beat_s
            continue
        if it["kind"] == "action":
            actions.append({"at_s": t, "text": it["text"]})
            continue
        c = pre.get(i) or speak(it["who"], it["text"], take=takes_by_line.get(i, 0), fps=fps)
        c = Clip(c)
        c["index"], c["start_s"] = i, round(t, 3)
        out.append(c)
        t += c["duration"] + gap_s
    return {"lines": out, "actions": actions, "length_s": round(t, 3), "fps": fps}


def _dia2_runs(items, fps):
    """Group consecutive lines between exactly two droids and voice each run
    with Dia2 in one go. Falls back silently if Dia2 isn't installed."""
    dia = engines.ENGINES["dia2"]
    if not dia.available()[0]:
        return {}
    cast = castmod.load()
    runs, cur = [], []
    for i, it in enumerate(items):
        if it["kind"] != "line":
            if it["kind"] == "beat" and cur:
                runs.append(cur)
                cur = []
            continue
        did = castmod.find(it["who"], cast)[0]
        who = {castmod.find(items[j]["who"], cast)[0] for j in cur}
        if cur and did not in who and len(who) >= 2:
            runs.append(cur)
            cur = []
        cur.append(i)
    if cur:
        runs.append(cur)
    result = {}
    for run in runs:
        ids = [castmod.find(items[j]["who"], cast)[0] for j in run]
        if len(run) < 2 or len(set(ids)) != 2 or any(cast[d].get("silent") for d in ids):
            continue
        order = list(dict.fromkeys(ids))
        turns = [{"speaker": order.index(d) + 1, "text": script.convert_tags(items[j]["text"], "paren")}
                 for d, j in zip(ids, run)]
        folder = str(config.cache_dir() / "_dia2")
        os.makedirs(folder, exist_ok=True)
        key = _key("dia2", turns)
        outs = [os.path.join(folder, f"{key}_{n}.wav") for n in range(len(run))]
        if not all(os.path.exists(o) for o in outs):
            # The runner writes every turn; we call it through the batch API.
            import subprocess
            import tempfile
            job = os.path.join(tempfile.mkdtemp(prefix="dv_dia2_"), "job.json")
            with open(job, "w", encoding="utf-8") as f:
                json.dump({"engine": "dia2", "lines": [{"text": "", "turns": turns, "outs": outs,
                                                        "seed": int(key, 16) % (2 ** 31)}]}, f)
            p = subprocess.run(dia._cmd() + [job], capture_output=True, text=True,
                               timeout=config.settings()["timeout_s"])
            if p.returncode != 0:
                continue        # leave these lines to the droids' own engines
        for n, (d, j) in enumerate(zip(ids, run)):
            entry = cast[d]
            a, sr = wavio.read(outs[n])
            dfold = str(config.cache_dir() / d)
            os.makedirs(dfold, exist_ok=True)
            result[j] = _finish(d, entry, items[j]["text"], "dia2", 0, int(key, 16) % (2 ** 31), a, sr, fps,
                                dfold, f"dia2_{key}_{n}")
    return result
