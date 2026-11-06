"""Turn contact events into sound strips on the shot's timeline.

Every event becomes one short WAV (cached by its physics, so re-baking an
unchanged shot is instant) and one sound strip in the Video Sequencer on the
event's frame. The sub-frame part of the moment is baked into the WAV as
leading silence, so hits land to the sample. The strip is panned to where the
contact sits in the camera frame and turned down with distance.

Channels: 24 feet, 25 hands, 26 props, 27 scrapes. All strips are named
"FX ..." and Clear removes only those, so dialogue and music are never touched.
"""
import json
import math
import os
import zlib

import bpy
import numpy as np

from . import synth as S
from . import motors as MO

CHANNELS = {"step": 24, "bump": 24, "grab": 25, "release": 25, "clunk": 25, "place": 26, "slide": 27}
MOTOR_CH = 28
PREFIX = "FX "


def cache_dir():
    if bpy.data.filepath:
        d = os.path.join(os.path.dirname(bpy.data.filepath), "foley_cache")
    else:
        d = os.path.join(bpy.app.tempdir or "/tmp", "foley_cache")
    os.makedirs(d, exist_ok=True)
    return d


def _strips(scene):
    sed = scene.sequence_editor or scene.sequence_editor_create()
    return sed.strips if hasattr(sed, "strips") else sed.sequences


def clear(scene=None):
    scene = scene or bpy.context.scene
    if scene.sequence_editor is None:
        return 0
    col = _strips(scene)
    gone = [s for s in col if s.name.startswith(PREFIX)]
    for s in gone:
        col.remove(s)
    return len(gone)


def distance_gain(dist, ref=3.0):
    """Inverse distance beyond ref metres, gentler than real life so far
    contacts stay audible."""
    return min(1.0, (ref / max(dist, 0.1)) ** 0.8)


def bake(events, scene=None, master=1.0, room_wet=0.12, room_rt60=0.45, offscreen=0.6):
    """Write WAVs and lay the strips. Returns (strips made, json path)."""
    scene = scene or bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    clear(scene)
    col = _strips(scene)
    d = cache_dir()
    made = 0
    for e in events:
        frame = e["frame"]
        start = int(math.floor(frame))
        offset = (frame - start) / fps
        args = dict(e["hit"])
        args["offset"] = offset
        args["seed"] = e["id"]
        h = S.Hit(**args)
        path = os.path.join(d, "fx_%08x.wav" % zlib.crc32((h.key() + "|%.3f|%.3f" % (room_wet, room_rt60)).encode()))
        if not os.path.exists(path):
            S.write_wav(path, S.render(h, room_wet, room_rt60))
        name = "%s%s %s %s" % (PREFIX, e["who"], e["limb"], e["kind"])
        strip = col.new_sound(name[:60], path, CHANNELS.get(e["kind"], 27), start)
        strip.sound.use_mono = True
        g = master * distance_gain(e.get("dist", 3.0)) * (1.0 if e.get("on_screen", True) else offscreen)
        strip.volume = g
        strip.pan = e.get("pan", 0.0)
        strip["foley"] = json.dumps({k: v for k, v in e.items() if k != "hit"} | {"speed": e["hit"]["speed"]},
                                    default=str)
        made += 1
    js = os.path.join(d, "events_%s.json" % bpy.path.clean_name(scene.name))
    with open(js, "w") as fh:
        json.dump(events, fh, indent=1, default=str)
    return made, js


def mixdown(path, scene=None):
    """Write the whole shot's audio (foley plus anything else in the VSE)."""
    scene = scene or bpy.context.scene
    with bpy.context.temp_override(scene=scene):
        bpy.ops.sound.mixdown(filepath=path, check_existing=False, container="WAV", codec="PCM",
                              format="S16", mixrate=S.RATE, split_channels=False)
    return path


def bake_motors(motors, events, scene=None, master=1.0, room_wet=0.08):
    """One motor track per droid limb group, laid from the shot's first frame.
    The leg that just landed strains: its motors swell as it takes the weight."""
    scene = scene or bpy.context.scene
    col = _strips(scene)
    d = cache_dir()
    made = 0
    ch = MOTOR_CH
    for name, m in motors.items():
        prof, js, f0, f1, fps = m["prof"], m["joints"], m["f0"], m["f1"], m["fps"]
        dur = (f1 - f0 + 1) / fps
        mine = [e for e in events if e["who"] == prof["label"]]
        pan = sum(e["pan"] for e in mine) / len(mine) if mine else 0.0
        dist = min((e["dist"] for e in mine), default=3.0)
        groups = {}
        for j in js:
            groups.setdefault(j.group, []).append(j)
        for gi, (g, gj) in enumerate(sorted(groups.items())):
            side = g.split(".")[-1] if "." in g else None
            strain = []
            if g.startswith("leg"):
                for e in mine:
                    if e["kind"] in ("step", "bump") and (side is None or e["limb"].endswith(side)):
                        strain.append((e["time"], min(0.6 * (prof["mass_kg"] / 120.0) ** 0.5 * (0.5 + e["hit"]["speed"]), 1.4)))
            x = MO.render_group(gj, prof, dur, strain, seed=gi, level=master)
            if float(np.max(np.abs(x))) < 1e-4:
                continue
            rng = np.random.default_rng(gi)
            x = S._room(x.astype(float), rng, 0.4, room_wet)
            path = os.path.join(d, "motor_%s_%s_%d_%d.wav" % (bpy.path.clean_name(name), g, f0, f1))
            S.write_wav(path, x)
            strip = col.new_sound(("%s%s motors %s" % (PREFIX, prof["label"], g))[:60], path, ch, f0)
            ch = ch + 1 if ch < 40 else MOTOR_CH
            strip.sound.use_mono = True
            strip.volume = distance_gain(dist)
            lr = {"L": 0.15, "R": -0.15}.get(side, 0.0)   # droid faces camera: its left is screen right
            strip.pan = max(-1.0, min(1.0, pan + lr))
            made += 1
    return made
