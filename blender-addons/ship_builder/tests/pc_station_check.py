"""Live UX check of the episode stations on the PC, with the INSTALLED add-on:

    blender --python pc_station_check.py -- <out dir>        (your own prefs, never saved)

Opens Ship Studio in its own window, starts a test episode in <out dir>/root
(never the real DeepInDoodles folder: preferences are not saved), runs the rough
cut (real voices, rooms, marks, cameras, acting, check) and screenshots every
station. Writes report.json and quits.
"""
import importlib
import json
import os
import sys
import time
import traceback

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(args[0])
os.makedirs(OUT, exist_ok=True)
REP = {"steps": [], "errors": []}
T0 = time.time()
bpy.context.preferences.use_preferences_save = False


def log(name, **kw):
    REP["steps"].append(dict(step=name, t=round(time.time() - T0, 1), **kw))
    print("CHECK", name, kw, flush=True)
    with open(os.path.join(OUT, "report.json"), "w", encoding="utf-8") as f:
        json.dump(REP, f, indent=1)


def guard(fn):
    def run():
        try:
            return fn()
        except Exception:
            REP["errors"].append(fn.__name__ + ": " + traceback.format_exc())
            log("error in " + fn.__name__)
    run.__name__ = fn.__name__
    return run


import addon_utils
MOD = "bl_ext.user_default.ship_builder"
if not addon_utils.check(MOD)[1]:
    addon_utils.enable(MOD, default_set=True)
for m in ("bl_ext.user_default.ship_foley",):
    if not addon_utils.check(m)[1]:
        try:
            addon_utils.enable(m, default_set=True)
        except Exception as e:
            log("foley not enabled", error=str(e))
SB = importlib.import_module(MOD)
S = importlib.import_module(MOD + ".stations")
St = importlib.import_module(MOD + ".studio")
F = importlib.import_module(MOD + ".episode_flow")
pr = St.prefs()
pr.deep_root = os.path.join(OUT, "root")
os.makedirs(pr.deep_root, exist_ok=True)
STATE = {"win": None}

SCRIPT = """INT. COMMAND CENTRE
COMPUTER: Minor anomaly detected in the coolant line.
HAZARD: (happy) Minor means fine!
RX-07: (worried) It is dripping. [points at the ceiling]
HAZARD: (annoyed) Everything drips. That's what ships do.
INT. ENGINE ROOM
HAZARD: (scared) Who touched the valve?
RX-07: (calm) You did.
"""


def win_ctx():
    w = STATE["win"] or bpy.context.window_manager.windows[0]
    a = max(w.screen.areas, key=lambda a: a.width * a.height)
    return dict(window=w, screen=w.screen, area=a)


def shot(name):
    path = os.path.join(OUT, name + ".png")
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()
    with bpy.context.temp_override(**win_ctx()):
        bpy.ops.screen.screenshot(filepath=path)
    log("screenshot", file=name + ".png")


def station(key):
    with bpy.context.temp_override(**win_ctx()):
        bpy.ops.ship.station(station=key)


@guard
def step_open():
    wm = bpy.context.window_manager
    before = set(wm.windows[:])
    w0 = wm.windows[0]
    with bpy.context.temp_override(window=w0, screen=w0.screen, area=w0.screen.areas[0]):
        bpy.ops.ship.open_studio()
    new = [w for w in wm.windows if w not in before]
    STATE["win"] = new[0] if new else None
    log("studio opened", areas=[a.type for a in (new[0].screen.areas if new else [])])


@guard
def step_board():
    station("BOARD")


@guard
def shot_board():
    shot("1_board_empty")


@guard
def step_new():
    S.st().new_title = "The Leak"
    with bpy.context.temp_override(**win_ctx()):
        bpy.ops.ship.ep_new(template="blank")
    t = bpy.data.texts.get(f"{S.ep().name} script")
    t.from_string(SCRIPT)
    with bpy.context.temp_override(**win_ctx()):
        bpy.ops.ship.ep_script()
    log("episode", folder=S.ep().folder, voice=bool(S.droid_voice()))


@guard
def shot_write():
    shot("2_write")


@guard
def step_rough():
    t = time.time()
    with bpy.context.temp_override(**win_ctx()):
        bpy.ops.ship.ep_rough()
    e = S.ep()
    vo = e.data.get("voices", {})
    real = sum(1 for v in vo.values() if v.get("takes") and v["takes"][v.get("pick", 0)].get("wav"))
    chips = e.data.get("check", {})
    log("rough cut", seconds=round(time.time() - t, 1), shots=len(e.data.get("shots", [])), voiced_with_audio=real,
        lines=len(vo), check={k: (len(v) if isinstance(v, list) else v) for k, v in chips.items()} if isinstance(chips, dict) else chips)


def make_station_shots():
    out = []
    for n, key in enumerate(("VOICE", "STAGE", "PERFORM", "CHECK", "RENDER", "PUBLISH", "BOARD", "LIBRARY"), 3):
        def go(key=key):
            station(key)
        def snap(key=key, n=n):
            shot(f"{n}_{key.lower()}")
        go.__name__ = snap.__name__ = "station_" + key
        out += [guard(go), guard(snap)]
    return out


STEPS = [step_open, step_board, shot_board, step_new, shot_write, step_rough] + make_station_shots()


def tick():
    if not STEPS:
        log("done", errors=len(REP["errors"]))
        bpy.ops.wm.quit_blender()
        return None
    STEPS.pop(0)()
    return 1.5   # let the windows redraw before the next step


bpy.app.timers.register(tick, first_interval=3.0)
