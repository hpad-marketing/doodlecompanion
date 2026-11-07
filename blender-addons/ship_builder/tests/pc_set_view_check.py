"""Live check of the set view and droid controls on the PC, with the INSTALLED add-on:

    blender --python pc_set_view_check.py -- <out dir>        (preferences never saved)

Builds deck 1, brings in every kit droid (RX-07 scaled to 1.5 m), orbits the view
outside the rooms with set view on and off, poses RX-07 with its controls lit, and
screenshots each step plus the studio's Controls panel. Writes report.json and quits.
"""
import importlib
import json
import math
import os
import sys
import time
import traceback

import bpy
from mathutils import Euler, Vector

args = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(args[0])
os.makedirs(OUT, exist_ok=True)
REP = {"steps": [], "errors": []}
T0 = time.time()
bpy.context.preferences.use_preferences_save = False
MOD = "bl_ext.user_default.ship_builder"
SB = importlib.import_module(MOD)
S = importlib.import_module(MOD + ".ship")
St = importlib.import_module(MOD + ".studio")
Cat = importlib.import_module(MOD + ".catalog")
CF = importlib.import_module(MOD + ".castfit")
RU = importlib.import_module(MOD + ".rigui")
CW = importlib.import_module(MOD + ".cutaway")
G = {"studio": None, "rx": None}


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


def main_view():
    w = bpy.context.window_manager.windows[0]
    a = max((a for a in w.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    return w, a


def shot(name, studio=False):
    w = G["studio"] if studio and G["studio"] else bpy.context.window_manager.windows[0]
    for a in w.screen.areas:
        a.tag_redraw()
    a = max(w.screen.areas, key=lambda a: a.width * a.height)
    over = dict(window=w, area=a) if studio else dict(window=w, screen=w.screen, area=a)
    with bpy.context.temp_override(**over):
        bpy.ops.screen.screenshot(filepath=os.path.join(OUT, name + ".png"))
    log("screenshot", file=name + ".png")


def look(eye, target, dist_scale=1.0):
    w, a = main_view()
    r3 = a.spaces.active.region_3d
    eye, target = Vector(eye), Vector(target)
    d = eye - target
    r3.view_perspective = "PERSP"
    r3.view_location = target
    r3.view_distance = d.length * dist_scale
    r3.view_rotation = d.to_track_quat("Z", "Y")
    a.spaces.active.shading.type = "MATERIAL"
    a.spaces.active.overlay.show_overlays = True
    a.spaces.active.lens = 28
    CW._STATE["eye"] = None
    CW.update(bpy.context.scene, r3.view_matrix.inverted().translation)


@guard
def step_build():
    w, a = main_view()
    with bpy.context.temp_override(window=w, screen=w.screen, area=a):
        bpy.ops.screen.screen_full_area()
    cube = bpy.data.objects.get("Cube")          # the startup file's cube, not part of the set
    if cube is not None and tuple(cube.dimensions) == (2.0, 2.0, 2.0):
        bpy.data.objects.remove(cube)
    S.build("deck1", settle=True)
    n = CW.tag(bpy.context.scene)
    log("built deck1", tagged=n, rooms=[r["name"] for r in S.info(bpy.context.scene)["rooms"]])


@guard
def step_droids():
    pr = St.prefs()
    ds = Cat.droids(pr)
    added = []
    for d in ds:
        if not os.path.isfile(d["blend"]):
            continue

        class It:
            data = d
            label = d["name"]
        try:
            St._use_droid(bpy.context, It)
            rig = bpy.context.view_layer.objects.active
            bpy.context.view_layer.update()
            added.append(dict(id=d["id"], height=round(CF.height(rig), 2), kg=rig.get("foley_mass_kg"),
                              scale=round(rig.get("sb_set_scale", 1), 3),
                              shapes=sum(1 for pb in rig.pose.bones if pb.custom_shape)))
            if d["id"] == "rx07":
                G["rx"] = rig
        except Exception as e:
            added.append(dict(id=d["id"], error=str(e)))
    # stand them side by side in the first room, facing the open front
    r = S.info(bpy.context.scene)["rooms"][0]
    rigs = RU.droids(bpy.context.scene)
    for k, rig in enumerate(rigs):
        rig.location = (r["x"] - r["W"] * 0.25 + k * r["W"] * 0.5 / max(1, len(rigs) - 1), r["y"] + r["D"] * 0.45, 0)
        rig.rotation_euler = (0, 0, math.pi)
    log("droids", added=added, room=r["name"])


def room0():
    return S.info(bpy.context.scene)["rooms"][0]


@guard
def view_outside_on():
    bpy.context.scene["sb_set_view"] = 1
    r = room0()
    look((r["x"] - r["W"] * 0.9, r["y"] + r["D"] * 1.6, r["H"] * 2.2), (r["x"], r["y"] + r["D"] * 0.45, 0.8))
    log("set view on", hidden=len(CW._STATE["hidden"]))


@guard
def warm_up():
    log("waiting for shaders")


@guard
def snap_outside_on():
    shot("1_set_view_on_back_left")


@guard
def view_outside_off():
    bpy.context.scene["sb_set_view"] = 0
    r = room0()
    look((r["x"] - r["W"] * 0.9, r["y"] + r["D"] * 1.6, r["H"] * 2.2), (r["x"], r["y"] + r["D"] * 0.45, 0.8))
    log("set view off", hidden=len(CW._STATE["hidden"]))


@guard
def snap_outside_off():
    shot("2_set_view_off_same_angle")


@guard
def view_above():
    bpy.context.scene["sb_set_view"] = 1
    r = room0()
    look((r["x"] + r["W"] * 0.2, r["y"] - r["D"] * 0.2, r["H"] * 3.2), (r["x"], r["y"] + r["D"] * 0.5, 0.0))
    log("above", hidden=len(CW._STATE["hidden"]))


@guard
def snap_above():
    shot("3_set_view_from_above")


@guard
def pose_rx():
    rig = G["rx"]
    if rig is None:
        log("no rx07")
        return
    w, a = main_view()
    with bpy.context.temp_override(window=w, screen=w.screen, area=a):
        bpy.ops.ship.pose(rig=rig.name, bone=RU.find(rig, dict(RU.MAIN)["Right hand"]) or "")
    r = room0()
    p = rig.matrix_world.translation
    look((p.x + 1.4, p.y - 2.4, 1.7), (p.x, p.y, 0.75))
    log("posing", mode=bpy.context.mode, active=rig.data.bones.active.name if rig.data.bones.active else None)


@guard
def snap_pose():
    shot("4_rx07_controls_close")


@guard
def open_studio():
    wm = bpy.context.window_manager
    before = set(wm.windows[:])
    w0 = wm.windows[0]
    with bpy.context.temp_override(window=w0, screen=w0.screen, area=w0.screen.areas[0]):
        bpy.ops.ship.open_studio()
    new = [w for w in wm.windows if w not in before]
    G["studio"] = new[0] if new else None
    St.state().cat = "DROIDS"
    log("studio", ok=bool(new))


@guard
def snap_studio():
    shot("5_studio_droid_controls", studio=True)


STEPS = [step_build, step_droids, view_outside_on, warm_up, warm_up, warm_up, snap_outside_on, view_outside_off, snap_outside_off,
         view_above, snap_above, pose_rx, snap_pose, open_studio, snap_studio]


def tick():
    if not STEPS:
        log("done", errors=len(REP["errors"]))
        bpy.ops.wm.quit_blender()
        return None
    STEPS.pop(0)()
    return 2.0


bpy.app.timers.register(tick, first_interval=3.0)
