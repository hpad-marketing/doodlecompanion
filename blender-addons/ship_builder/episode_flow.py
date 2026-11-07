"""Ship Studio episode workflow: everything a station works out, with no bpy.

Each function reads and writes the episode's data (episode.json) so every
station, the timeline and the tests share one source of truth. The Blender side
(stations.py) turns these plans into scenes, strips and renders.

    voice_lines(ep, speak)      V1 V2   voice every line (or only changed), three takes each
    retime(ep)                  V4      shot timing follows the voices, laugh pause after punchlines
    coverage(ep)                S3 S5   sitcom shot plan per line (+ exterior cutaways)
    emotion_look(emotion)       P2      pose set + LED colour for a line's emotion chip
    ACTING / acting_layers(ep)  P1      auto acting layers, each on/off + strength
    add_event(ep, kind, t)      P5      ship events on the events track
    track_items(ep)             A3      the six timeline tracks, identical in every station
    check_chips(ep, results)    R1      the episode check strip (reports, never blocks)
    queue_jobs(ep, root, mode)  X1 X2   one render job per shot in DeepInDoodles/_queue
    mix_plan(ep) / ffmpeg_mix   X3      edit order, panning, room reverb, ducking, -14 LUFS
    thumbnail_frames(ep)        U1      the six most expressive moments
    srt(ep, lang)               U2      captions word for word from the script
    shorts(ep)                  U3      the three strongest moments, 9:16 crop centres
    upload_pack(ep)             U4      folder with everything YouTube needs
"""
import hashlib
import json
import math
import os
import re
import time

from . import episode as E

IST = 5.5 * 3600

# ------------------------------------------------------------------ helpers
def _lines(ep):
    return ep.data.get("parsed", {}).get("lines", [])


def _scenes(ep):
    return ep.data.get("parsed", {}).get("scenes", [])


def line_hash(ln):
    return hashlib.sha1(json.dumps([ln.get("who"), ln.get("text"), ln.get("emotion")]).encode()).hexdigest()[:12]


def ist(ts=None):
    """Clock time in IST, e.g. '06:40 IST'."""
    t = time.gmtime((ts or time.time()) + IST)
    return time.strftime("%H:%M IST", t)


# ------------------------------------------------------------------ V1 V2 voices
VOICE_ID = {"RX07": "rx07", "HAZARD": "hazard", "DRONE": "drone", "COMPUTER": "computer"}


def voice_lines(ep, speak=None, only_changed=True, takes=3, fps=24):
    """Voice every dialogue line with each droid's set voice, three takes per line.

    speak(droid_id, text, take, fps) -> {"robot": wav, "duration": s, "lipsync": {...}}
    (droid_voice.voice.speak). Without it, a silent timing guide is used so the
    rest of the pipeline still works. Only lines whose text, speaker or emotion
    changed are re-voiced when only_changed is set. Returns the count voiced."""
    vo = ep.data.setdefault("voices", {})
    n = 0
    for i, ln in enumerate(_lines(ep)):
        if ln["kind"] != "dialogue" or not ln.get("who"):
            continue
        h = line_hash(ln)
        key = str(ln["line_no"])
        cur = vo.get(key)
        if only_changed and cur and cur.get("hash") == h and cur.get("takes"):
            continue
        out = []
        for t in range(takes):
            if speak:
                c = speak(VOICE_ID.get(ln["who"], ln["who"].lower()), ln["text"] or "...", t, fps)
                out.append({"wav": c.get("robot") or c.get("dry"), "duration": float(c.get("duration", 1.0)),
                            "lipsync": c.get("lipsync")})
            else:
                out.append({"wav": None, "duration": round(E.line_seconds(ln, 0.0) * (1.0, 0.94, 1.08)[t % 3], 2), "lipsync": None})
        vo[key] = {"hash": h, "who": ln["who"], "takes": out, "pick": cur.get("pick", 0) if cur else 0}
        n += 1
    # drop voices for lines that no longer exist
    live = {str(l["line_no"]) for l in _lines(ep) if l["kind"] == "dialogue"}
    for k in [k for k in vo if k not in live]:
        del vo[k]
    if n or vo:
        ep.set_station("voice", "doing" if any(not v["takes"][v["pick"]].get("wav") for v in vo.values()) else "done")
    return n


def pick_take(ep, line_no, take):
    v = ep.data.get("voices", {}).get(str(line_no))
    if v and 0 <= take < len(v["takes"]):
        v["pick"] = take
    return v


# ------------------------------------------------------------------ V4 timing
def retime(ep, laugh=None, gap=0.3):
    """Clip start/end for every line from its picked take. A line ending in ! or ?
    (or marked punchline) holds a laugh pause after it. Returns [{line_no, start, end}]."""
    laugh = ep.data.get("laugh_pause", E.LAUGH) if laugh is None else laugh
    vo = ep.data.get("voices", {})
    t, out = 0.0, []
    last_scene = None
    for ln in _lines(ep):
        if ln["scene"] != last_scene:
            t += E.SCENE_S if last_scene is not None or t == 0 else 0
            last_scene = ln["scene"]
        v = vo.get(str(ln["line_no"]))
        if ln["kind"] == "dialogue" and v:
            d = v["takes"][v["pick"]]["duration"]
        else:
            d = E.line_seconds(ln, 0.0)
        start = t
        t += d
        if ln["kind"] == "dialogue" and (ln["text"].rstrip().endswith(("!", "?")) or ln.get("punchline")):
            t += laugh
        out.append({"line_no": ln["line_no"], "start": round(start, 3), "end": round(start + d, 3), "who": ln.get("who"),
                    "scene": ln["scene"], "kind": ln["kind"]})
        t += gap
    ep.data["timing"] = out
    ep.data["length_s"] = round(t, 3)
    return out


# ------------------------------------------------------------------ S3 S5 coverage
SITCOM_PACK = {   # Director shot presets used for sitcom coverage (names from the 248 approved shots)
    "master": "Wide master", "two": "Two-shot", "single": "Medium close single", "reaction": "Reaction close",
    "insert": "Insert", "exterior": "Hero ship cruise",
}
EXTERIORS = ("Hero ship cruise", "Hero ship drift", "Hero ship hyperdrive jump", "Hero ship landing")


def coverage(ep, cutaways=True):
    """Shot plan from the timing: a wide master to open each scene, a single on
    whoever speaks, a reaction on whoever listens after a punchline, inserts on
    [action] lines, and an exterior cutaway at each scene change (S5)."""
    timing = {t["line_no"]: t for t in (ep.data.get("timing") or retime(ep))}
    shots, lines = [], _lines(ep)
    cast_in_scene = {}
    for ln in lines:
        if ln.get("who"):
            cast_in_scene.setdefault(ln["scene"], [])
            if ln["who"] not in cast_in_scene[ln["scene"]]:
                cast_in_scene[ln["scene"]].append(ln["who"])
    keep = {s["id"]: s for s in ep.data.get("shots", []) if s.get("locked")}
    for si, sc in enumerate(_scenes(ep)):
        idx = [i for i in sc["lines"]]
        if not idx:
            continue
        t0 = timing[lines[idx[0]]["line_no"]]["start"]
        if sc["room"] == E.EXTERIOR or (cutaways and si > 0):
            shots.append({"preset": EXTERIORS[si % len(EXTERIORS)], "kind": "exterior", "scene": si, "start": max(0.0, t0 - E.SCENE_S),
                          "end": t0, "subject": None})
        if sc["room"] == E.EXTERIOR:
            continue
        cast = cast_in_scene.get(si, [])
        first = timing[lines[idx[0]]["line_no"]]
        shots.append({"preset": SITCOM_PACK["master"] if len(cast) != 2 else SITCOM_PACK["two"], "kind": "master",
                      "scene": si, "start": first["start"], "end": first["end"], "subject": None})
        for k, i in enumerate(idx[1:], 1):
            ln = lines[i]
            tm = timing[ln["line_no"]]
            if ln["kind"] == "action" or ln.get("actions") and not ln.get("text"):
                shots.append({"preset": SITCOM_PACK["insert"], "kind": "insert", "scene": si, "start": tm["start"], "end": tm["end"],
                              "subject": ln.get("who"), "note": (ln.get("actions") or [ln["text"]])[0]})
                continue
            prev = lines[idx[k - 1]]
            if prev.get("kind") == "dialogue" and prev["text"].rstrip().endswith(("!", "?")) and ln.get("who") and ln["who"] != prev.get("who"):
                ptm = timing[prev["line_no"]]
                shots.append({"preset": SITCOM_PACK["reaction"], "kind": "reaction", "scene": si, "start": ptm["end"],
                              "end": tm["start"], "subject": ln["who"]})
            shots.append({"preset": SITCOM_PACK["single"], "kind": "single", "scene": si, "start": tm["start"], "end": tm["end"],
                          "subject": ln.get("who")})
    shots.sort(key=lambda s: s["start"])
    for n, s in enumerate(shots, 1):
        s["id"] = f"S{n:03d}"
        if s["id"] in keep:   # a shot you swapped by hand keeps its preset
            s["preset"] = keep[s["id"]]["preset"]
            s["locked"] = True
        s["start"], s["end"] = round(s["start"], 3), round(max(s["end"], s["start"] + 0.5), 3)
    ep.data["shots"] = shots
    ep.set_station("stage", "doing")
    return shots


def swap_shot(ep, shot_id, preset):
    for s in ep.data.get("shots", []):
        if s["id"] == shot_id:
            s["preset"], s["locked"] = preset, True
            return s


# ------------------------------------------------------------------ P1 P2 acting
EMOTION_LOOK = {   # pose set, LED colour (linear RGB), idle speed
    "calm": ("calm", (0.35, 0.75, 1.0), 1.0),
    "worried": ("worried", (1.0, 0.7, 0.2), 1.3),
    "alarmed": ("alarmed", (1.0, 0.12, 0.08), 1.8),
    "happy": ("happy", (0.4, 1.0, 0.45), 1.2),
    "annoyed": ("annoyed", (1.0, 0.4, 0.1), 1.1),
    "sleepy": ("sleepy", (0.35, 0.35, 0.8), 0.6),
}


def emotion_look(emotion):
    pose, led, speed = EMOTION_LOOK.get(emotion or "calm", EMOTION_LOOK["calm"])
    return {"pose_set": pose, "led": led, "idle_speed": speed}


def set_emotion(ep, line_no, emotion):
    assert emotion in E.EMOTIONS
    over = ep.data.setdefault("emotion_over", {})
    over[str(line_no)] = emotion
    return emotion_look(emotion)


def line_emotion(ep, ln):
    return ep.data.get("emotion_over", {}).get(str(ln["line_no"]), ln.get("emotion") or "calm")


ACTING = (   # key, label, default strength
    ("gestures", "Gestures from voice", 0.7),
    ("look", "Look at speaker", 0.8),
    ("idle", "Idle life", 0.5),
    ("led", "LED lip sync", 1.0),
    ("contact", "Contact sounds", 0.8),
    ("tone", "Room tone", 0.4),
    ("touch", "Two-droid contact", 0.5),
)


def acting_layers(ep):
    cur = ep.data.setdefault("acting", {})
    for k, _l, s in ACTING:
        cur.setdefault(k, {"on": True, "strength": s})
    return cur


# ------------------------------------------------------------------ P5 events
EVENTS = {   # kind: (label, default length s, what it drives)
    "shake": ("Ship shake", 1.5, "camera shake, props rattle, rumble"),
    "red_alert": ("Red alert", 4.0, "lights to red, klaxon, screens flash"),
    "lights_out": ("Lights out", 3.0, "practicals off, emergency glow, power-down whine"),
    "meteors": ("Meteors", 5.0, "window streaks, small shakes, impacts"),
    "jump": ("Jump", 2.5, "window view streak, rising whine, flash, thump"),
}


def add_event(ep, kind, start, length=None):
    lab, d, _ = EVENTS[kind]
    evs = ep.data.setdefault("events", [])
    ev = {"kind": kind, "label": lab, "start": round(start, 3), "end": round(start + (length or d), 3)}
    evs.append(ev)
    evs.sort(key=lambda e: e["start"])
    return ev


# ------------------------------------------------------------------ A3 timeline
def track_items(ep):
    """The six tracks, the same in every station: [(track, [(start, end, label, rgb)])]."""
    timing = ep.data.get("timing") or []
    total = ep.data.get("length_s") or (timing[-1]["end"] if timing else ep.data.get("runtime_target", 300))
    out = {k: [] for k in E.TRACKS}
    for name, col, s, e in ep.beat_spans(total):
        out["beats"].append((s, e, name, col))
    for s in ep.data.get("shots", []):
        out["shots"].append((s["start"], s["end"], f"{s['id']} {s['preset']}", (0.5, 0.55, 0.62) if s["kind"] != "exterior" else (0.3, 0.4, 0.7)))
    for t in timing:
        if t["kind"] == "dialogue" and t["who"] in E.CAST:
            c = E.CAST[t["who"]]
            out["voices"].append((t["start"], t["end"], c["name"], c["color"]))
    lines = {l["line_no"]: l for l in _lines(ep)}
    for t in timing:
        ln = lines.get(t["line_no"])
        if ln and ln["kind"] == "dialogue":
            emo = line_emotion(ep, ln)
            out["acting"].append((t["start"], t["end"], emo, emotion_look(emo)["led"]))
    for f in ep.data.get("sound", []):
        out["sound"].append((f["start"], f["end"], f.get("label", "fx"), (0.45, 0.5, 0.45)))
    for ev in ep.data.get("events", []):
        out["events"].append((ev["start"], ev["end"], ev["label"], (0.85, 0.3, 0.25)))
    return [(k, out[k]) for k in E.TRACKS], total


# ------------------------------------------------------------------ R1 check
CHIPS = (("intersect", "Nothing intersects"), ("feet", "Feet planted"), ("frame", "Frame edges"),
         ("voiced", "Every line voiced"), ("props", "Props in hand"), ("dead_air", "Dead air"))


def check_chips(ep, results=None):
    """results: {chip: [(shot_id, note)]} from the Blender side for the scene checks.
    'voiced' and 'dead_air' are worked out here. Returns [(chip, label, issues)]."""
    results = dict(results or {})
    vo = ep.data.get("voices", {})
    miss = []
    for ln in _lines(ep):
        if ln["kind"] == "dialogue":
            v = vo.get(str(ln["line_no"]))
            if not v or not v["takes"][v["pick"]].get("wav"):
                miss.append((None, f"line {ln['line_no']}: {E.CAST.get(ln['who'], {}).get('name', ln['who'])} not voiced"))
    results["voiced"] = miss
    timing = ep.data.get("timing") or []
    gaps = []
    for a, b in zip(timing, timing[1:]):
        if b["start"] - a["end"] > 3.0:
            gaps.append((None, f"{b['start'] - a['end']:.1f} s of silence before line {b['line_no']}"))
    results["dead_air"] = gaps
    out = [(k, lab, results.get(k, [])) for k, lab in CHIPS]
    ep.data["check"] = {k: [list(i) for i in v] for k, _l, v in out}
    ep.set_station("check", "done" if all(not v for _k, _l, v in out) else "doing")
    return out


def stills_state(ep):
    st = ep.data.setdefault("stills", {})
    shots = [s["id"] for s in ep.data.get("shots", [])]
    return {sid: st.get(sid, {"approved": False, "note": ""}) for sid in shots}


def approve_all(ep):
    st = ep.data.setdefault("stills", {})
    for s in ep.data.get("shots", []):
        st.setdefault(s["id"], {"note": ""})["approved"] = True
    return st


def render_unlocked(ep):
    s = stills_state(ep)
    return bool(s) and all(v.get("approved") for v in s.values())


# ------------------------------------------------------------------ X1 X2 render queue
MODES = {"draft": {"engine": "BLENDER_EEVEE_NEXT", "res": (1280, 720), "samples": 16, "label": "Draft (EEVEE 720p)"},
         "final": {"engine": "CYCLES", "res": (3840, 2160), "samples": 256, "device": "OPTIX", "label": "Final (Cycles 4K)"}}
SEC_PER_FRAME = {"draft": 0.6, "final": 38.0}   # Sushi RTX 5080 estimates


def _job_name(ep, sid, mode):
    return f"ship-{ep.name}-{sid}-{mode}"


def queue_jobs(ep, root, blend, mode="draft", fps=24):
    """One job per shot on the shared GPU queue (<root>/_queue/jobs, see
    queue_runner). A shot that already has its output is skipped, so a crash
    resumes from the last finished shot. Returns (job paths, eta_ist)."""
    from . import queue_runner as Q
    cfg = MODES[mode]
    jobs, frames = [], 0
    for s in ep.data.get("shots", []):
        f0, f1 = int(round(s["start"] * fps)) + 1, max(int(round(s["end"] * fps)), int(round(s["start"] * fps)) + 1)
        out = ep.path("work", "shots", mode, s["id"] + ".mp4")
        if os.path.isfile(out):
            continue
        spec = {"episode": ep.name, "shot": s["id"], "blend": blend, "scene": s.get("scene_name") or f"Shot {s['id']}",
                "camera": s.get("camera"), "frames": [f0, f1],
                "mode": mode, "engine": cfg["engine"], "resolution": list(cfg["res"]), "samples": cfg["samples"],
                "device": cfg.get("device"), "output": out, "created": time.time()}
        jobs.append(Q.submit(root, _job_name(ep, s["id"], mode), spec))
        frames += f1 - f0 + 1
    eta = time.time() + frames * SEC_PER_FRAME[mode]
    ep.data["render"] = {"mode": mode, "queued": len(jobs), "eta": eta, "eta_ist": ist(eta)}
    ep.set_station("render", "doing")
    return jobs, ist(eta)


def queue_progress(ep, root, mode=None):
    """[(shot id, preset, state)], state = done | rendering | queued | failed | not queued."""
    from . import queue_runner as Q
    mode = mode or ep.data.get("render", {}).get("mode", "draft")
    return [(s["id"], s["preset"], Q.state(root, _job_name(ep, s["id"], mode), ep.path("work", "shots", mode, s["id"] + ".mp4")))
            for s in ep.data.get("shots", [])]


# ------------------------------------------------------------------ X3 edit + mix
def mix_plan(ep, mode="draft"):
    """Edit list in timeline order and the audio plan: each voice panned to where
    its droid stands in frame (from the shot's subject position), room reverb per
    room, foley and room tone under, music ducked under every line, -14 LUFS."""
    shots = [s for s in ep.data.get("shots", [])]
    vo = ep.data.get("voices", {})
    pan = ep.data.get("pan", {})   # line_no -> -1..1, written by the Blender side from droid screen x
    rooms = {i: sc["room"] for i, sc in enumerate(_scenes(ep))}
    voices = []
    for t in ep.data.get("timing", []):
        v = vo.get(str(t["line_no"]))
        if t["kind"] == "dialogue" and v:
            tk = v["takes"][v["pick"]]
            voices.append({"wav": tk.get("wav"), "start": t["start"], "pan": float(pan.get(str(t["line_no"]), 0.0)),
                           "room": rooms.get(t["scene"])})
    return {"video": [ep.path("work", "shots", mode, s["id"] + ".mp4") for s in shots], "voices": voices,
            "music": ep.data.get("music"), "tone": ep.data.get("room_tone"), "lufs": -14, "duck_db": -12,
            "out": ep.final if mode == "final" else ep.path("work", f"{ep.name}_draft.mp4")}


REVERB = {"lounge": (0.25, 40), "bridge": (0.3, 55), "corridor": (0.45, 70), "cargo": (0.55, 90), "engine": (0.5, 80),
          "airlock": (0.4, 60)}


def ffmpeg_mix(plan, ffmpeg="ffmpeg"):
    """-> argv list that cuts the shots together and mixes the audio locally."""
    args = [ffmpeg, "-y"]
    vids = [v for v in plan["video"] if v]
    for v in vids:
        args += ["-i", v]
    n = len(vids)
    vo = [v for v in plan["voices"] if v["wav"]]
    for v in vo:
        args += ["-i", v["wav"]]
    extra = []
    if plan.get("music"):
        args += ["-stream_loop", "-1", "-i", plan["music"]]
        extra.append("music")
    if plan.get("tone"):
        args += ["-stream_loop", "-1", "-i", plan["tone"]]
        extra.append("tone")
    f = []
    f.append("".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]" if n else "")
    vlabels = []
    for k, v in enumerate(vo):
        i = n + k
        dec, ms = REVERB.get(v["room"] or "", (0.3, 50))
        p = max(-1.0, min(1.0, v["pan"]))
        l, r = round(min(1.0, 1 - p), 3), round(min(1.0, 1 + p), 3)
        f.append(f"[{i}:a]aformat=channel_layouts=stereo,aecho=0.8:{dec}:{ms}:0.25,pan=stereo|c0={l}*c0|c1={r}*c1,"
                 f"adelay={int(v['start'] * 1000)}|{int(v['start'] * 1000)}[vo{k}]")
        vlabels.append(f"[vo{k}]")
    if vlabels:
        f.append("".join(vlabels) + f"amix=inputs={len(vlabels)}:normalize=0[voices]")
    under = []
    base = n + len(vo)
    for k, name in enumerate(extra):
        if name == "music" and vlabels:
            f.append(f"[voices]asplit=2[vkey][vmix]")
            f.append(f"[{base + k}:a]volume=0.5[mus];[mus][vkey]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck]")
            under.append("[duck]")
        else:
            f.append(f"[{base + k}:a]volume=0.25[{name}]")
            under.append(f"[{name}]")
    vmain = "[vmix]" if "music" in extra and vlabels else ("[voices]" if vlabels else "")
    ins = vmain + "".join(under)
    cnt = (1 if vmain else 0) + len(under)
    if cnt:
        f.append(f"{ins}amix=inputs={cnt}:duration=first:normalize=0,loudnorm=I={plan['lufs']}:TP=-1.5:LRA=11[a]")
    args += ["-filter_complex", ";".join(x for x in f if x)]
    if n:
        args += ["-map", "[v]"]
    if cnt:
        args += ["-map", "[a]"]
    args += ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", plan["out"]]
    return args


# ------------------------------------------------------------------ U1 U2 U3 U4 publish
INTENSITY = {"alarmed": 1.0, "annoyed": 0.8, "happy": 0.75, "worried": 0.7, "sleepy": 0.4, "calm": 0.2}


def moments(ep):
    """Every line scored by how expressive and how funny it is."""
    lines = {l["line_no"]: l for l in _lines(ep)}
    out = []
    for t in ep.data.get("timing", []):
        ln = lines.get(t["line_no"])
        if not ln or ln["kind"] != "dialogue":
            continue
        s = INTENSITY.get(line_emotion(ep, ln), 0.3)
        if ln["text"].rstrip().endswith("!"):
            s += 0.3
        if ln["text"].rstrip().endswith("?"):
            s += 0.15
        s += 0.1 * len(ln.get("actions", []))
        out.append((round(s, 3), t))
    out.sort(key=lambda x: (-x[0], x[1]["start"]))
    return out


def thumbnail_frames(ep, fps=24, n=6):
    """Frames for the six most expressive moments, spread out (no two within 4 s)."""
    pick = []
    for s, t in moments(ep):
        mid = (t["start"] + t["end"]) / 2
        if all(abs(mid - p) > 4 for p in pick):
            pick.append(mid)
        if len(pick) == n:
            break
    return [int(round(p * fps)) + 1 for p in pick]


def _ts(s):
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def srt(ep, lang="en"):
    """Captions word for word from the script, timed to the voice clips. Hindi
    uses each line's Hindi text from the Write station (hi_text); lines without
    one are listed so nothing is machine-translated silently."""
    lines = {l["line_no"]: l for l in _lines(ep)}
    hi = ep.data.get("hi_text", {})
    out, missing, n = [], [], 0
    for t in ep.data.get("timing", []):
        ln = lines.get(t["line_no"])
        if not ln or ln["kind"] != "dialogue" or not ln["text"]:
            continue
        if not E.CAST.get(ln["who"], {}).get("words", True):
            continue   # beeps are not captioned
        text = ln["text"] if lang == "en" else hi.get(str(ln["line_no"]))
        if not text:
            missing.append(ln["line_no"])
            continue
        n += 1
        who = E.CAST.get(ln["who"], {}).get("name", "")
        out.append(f"{n}\n{_ts(t['start'])} --> {_ts(t['end'])}\n{who}: {text}\n")
    return "\n".join(out), missing


def shorts(ep, n=3, length=30.0):
    """The n strongest moments as 9:16 windows. Each window starts a little before
    its line and keeps the speaking droid centred (crop_x from the Blender side)."""
    total = ep.data.get("length_s", 0)
    crop = ep.data.get("crop_x", {})
    out = []
    for s, t in moments(ep):
        a = max(0.0, t["start"] - 6.0)
        b = min(total or a + length, a + length)
        if all(b <= o["start"] or a >= o["end"] for o in out):
            out.append({"start": round(a, 2), "end": round(b, 2), "line_no": t["line_no"], "score": s,
                        "crop_x": float(crop.get(str(t["line_no"]), 0.5))})
        if len(out) == n:
            break
    return out


def shorts_ffmpeg(src, sh, out, ffmpeg="ffmpeg"):
    """9:16 crop centred on the speaker, kept inside the frame and away from the safe-zone edges."""
    cx = min(0.78, max(0.22, sh["crop_x"]))
    return [ffmpeg, "-y", "-ss", str(sh["start"]), "-to", str(sh["end"]), "-i", src, "-vf",
            f"crop=ih*9/16:ih:max(0\\,min(iw-ih*9/16\\,iw*{cx:.3f}-ih*9/32)):0,scale=1080:1920",
            "-c:v", "libx264", "-crf", "18", "-c:a", "aac", out]


def description(ep):
    lines = [l for l in _lines(ep) if l["kind"] == "dialogue" and l.get("text") and E.CAST.get(l["who"], {}).get("words")]
    hook = lines[0]["text"] if lines else ""
    cast = sorted({E.CAST[l["who"]]["name"] for l in _lines(ep) if l.get("who") in E.CAST})
    rooms = sorted({sc["room"] for sc in _scenes(ep) if sc.get("room")})
    body = [f"Episode {ep.data.get('number', '')}: {ep.data.get('title', '')}", "", f"\"{hook}\"" if hook else "",
            "", "Starring " + ", ".join(cast) if cast else "", "", "Chapters:"] + ep.chapters()
    return "\n".join(x for x in body if x is not None).strip(), cast, rooms


def upload_pack(ep, final=None, thumb=None, shorts_files=()):
    """Write the publish folder: final mp4, thumbnail, title, description, tags,
    chapters, captions (en, hi), end screen notes and the Shorts. Returns the folder."""
    import shutil
    pub = ep.path("work", "publish")
    os.makedirs(pub, exist_ok=True)
    title = f"{ep.data.get('title', 'Untitled')} | Ship Sitcom Ep {ep.data.get('number', 0)}"
    desc, cast, rooms = description(ep)
    tags = ["droid sitcom", "robots", "animation", "spaceship", "blender"] + [c.lower() for c in cast] + [r.replace("_", " ") for r in rooms]
    files = {"title.txt": title, "description.txt": desc, "tags.txt": ", ".join(dict.fromkeys(tags)),
             "chapters.txt": "\n".join(ep.chapters()),
             "end_screen.txt": "End screen (last 20 s): Subscribe button left, next episode right."}
    en, _ = srt(ep, "en")
    hi, missing = srt(ep, "hi")
    files["captions_en.srt"] = en
    if hi:
        files["captions_hi.srt"] = hi
    for name, text in files.items():
        with open(os.path.join(pub, name), "w", encoding="utf-8") as f:
            f.write(text)
    for src, name in ((final, os.path.basename(final or "")), (thumb, "thumbnail.jpg")):
        if src and os.path.isfile(src):
            shutil.copy2(src, os.path.join(pub, name))
    for k, s in enumerate(shorts_files, 1):
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(pub, f"short_{k}.mp4"))
    ep.data["publish"] = {"folder": pub, "hi_missing": missing, "title": title}
    ep.set_station("publish", "doing")
    return pub


# ------------------------------------------------------------------ W3 bible + running gags (library level)
def bible_path(root):
    return os.path.join(E.Episode.library(root), "bible.json")


def load_bible(root):
    p = bible_path(root)
    data = {"cast": {k: {kk: v[kk] for kk in ("wants", "fears", "speaks")} for k, v in E.CAST.items()}, "gags": []}
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            saved = json.load(f)
        data["cast"].update(saved.get("cast", {}))
        data["gags"] = saved.get("gags", [])
    return data


def save_bible(root, data):
    os.makedirs(E.Episode.library(root), exist_ok=True)
    with open(bible_path(root), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def gag_hits(root, eps=None):
    """Each running gag with the episodes whose script mentions one of its cue words."""
    b = load_bible(root)
    eps = eps if eps is not None else E.Episode.all(root)
    out = []
    for g in b["gags"]:
        cues = [c.lower() for c in g.get("cues", []) if c]
        hit = [e.name for e in eps if cues and any(c in e.script.lower() for c in cues)]
        out.append({**g, "episodes": hit})
    return out
