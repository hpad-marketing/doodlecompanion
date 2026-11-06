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

from . import synth as S

CHANNELS = {"step": 24, "bump": 24, "grab": 25, "release": 25, "place": 26, "slide": 27}
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
