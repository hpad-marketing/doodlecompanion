"""Live check of the easy controls: handles on droids, pose presets, camera moves, scene tab on the PC, with the INSTALLED add-on:

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
PK = importlib.import_module(MOD + ".posekit")
CM = importlib.import_module(MOD + ".cammoves")
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
def warm_up():
    log("waiting for shaders")


@guard
def step_build():
    cube = bpy.data.objects.get("Cube")
    if cube is not None and tuple(cube.dimensions) == (2.0, 2.0, 2.0):
        bpy.data.objects.remove(cube)
    w, a = main_view()
    with bpy.context.temp_override(window=w, screen=w.screen, area=a):
        bpy.ops.screen.screen_full_area()
    S.build("lounge_only", settle=True)
    log("built lounge")


@guard
def step_droids():
    pr = St.prefs()
    for d in Cat.droids(pr):
        if not os.path.isfile(d["blend"]):
            continue

        class It:
            data = d
            label = d["name"]
        St._use_droid(bpy.context, It)
        rig = bpy.context.view_layer.objects.active
        if d["id"] == "rx07":
            G["rx"] = rig
        else:
            G.setdefault("others", []).append(rig)
    r = S.info(bpy.context.scene)["rooms"][0]
    rigs = RU.droids(bpy.context.scene)
    for k, rig in enumerate(rigs):
        rig.location = (r["x"] - 0.9 + k * 1.8, r["y"] + r["D"] * 0.55, 0)
        rig.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    log("droids", n=len(rigs))


@guard
def step_pose():
    rx = G["rx"]
    if rx is not None:
        bpy.ops.ship.pose_preset(rig=rx.name, preset="wave")
    for o in G.get("others", []):
        bpy.ops.ship.pose_preset(rig=o.name, preset="look_left")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    r = S.info(bpy.context.scene)["rooms"][0]
    look((r["x"] + 0.4, r["y"] - 0.6, 1.6), (r["x"], r["y"] + r["D"] * 0.55, 0.7))
    log("posed", handles=[h.key for h in PK.handles(rx)] if rx else None)


@guard
def snap_handles():
    shot("1_handles_on_droids")


@guard
def step_move():
    sc = bpy.context.scene
    cam = next((o for o in sc.objects if o.type == "CAMERA" and "Wide" in o.name), None) or sc.camera
    sc.camera = cam
    sc.frame_set(1)
    log("camera move", result=list(CM.apply(sc, "orbit_left", 1)))


@guard
def open_studio():
    wm = bpy.context.window_manager
    before = set(wm.windows[:])
    w0 = wm.windows[0]
    with bpy.context.temp_override(window=w0, screen=w0.screen, area=w0.screen.areas[0]):
        bpy.ops.ship.open_studio()
    new = [w for w in wm.windows if w not in before]
    G["studio"] = new[0] if new else None
    St.state().cat = "POSES"
    St.state().droid = "rx07"
    log("studio", ok=bool(new))


def tab(cat, name):
    def set_():
        St.state().cat = cat
        log("tab " + cat)

    def snap():
        shot(name, studio=True)
    set_.__name__, snap.__name__ = "tab_" + cat, "snap_" + cat
    return [guard(set_), guard(lambda: log("wait")), guard(snap)]


@guard
def snap_poses():
    shot("2_poses_tab", studio=True)


STEPS = [step_build, step_droids, step_pose, warm_up, warm_up, warm_up, snap_handles, step_move, open_studio, warm_up, warm_up,
         snap_poses] + tab("MOVES", "3_camera_moves_tab") + tab("SCENE", "4_in_this_scene_tab") + tab("DROIDS", "5_droids_tab_controls")


def tick():
    if not STEPS:
        log("done", errors=len(REP["errors"]))
        bpy.ops.wm.quit_blender()
        return None
    STEPS.pop(0)()
    return 2.0


bpy.app.timers.register(tick, first_interval=3.0)
