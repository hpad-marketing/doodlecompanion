"""Live check on the PC (Blender with its window, NOT installed as an add-on):

    blender --factory-startup --python pc_studio_check.py -- <out dir> [thumbs dir]

1. loads Ship Builder straight from the repo and registers it for this session only
2. builds Deck 1 (lounge, corridor, command centre) and audits it
3. opens Ship Studio, picks a few items and screenshots the window
4. renders GPU stills of the joined ship (Ship Wide, corridor, joint close-up)
5. bakes the missing library previews into the thumbs dir
6. writes report.json and quits
"""
import json
import os
import sys
import time
import traceback

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(args[0])
THUMBS = os.path.abspath(args[1]) if len(args) > 1 and not args[1].startswith("--") else os.path.join(OUT, "thumbs")
os.makedirs(OUT, exist_ok=True)
os.makedirs(THUMBS, exist_ok=True)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
REP = {"steps": [], "errors": []}


def log(name, **kw):
    REP["steps"].append(dict(step=name, t=round(time.time() - T0, 1), **kw))
    print("CHECK", name, kw, flush=True)
    json.dump(REP, open(os.path.join(OUT, "report.json"), "w"), indent=1)


def guard(fn):
    def run():
        try:
            return fn()
        except Exception:
            REP["errors"].append(traceback.format_exc())
            log("error in " + fn.__name__)
            return None
    run.__name__ = fn.__name__
    return run


T0 = time.time()
import ship_builder as SB
SB.register()
from ship_builder import ship as S, studio as St, collide, lighting as Li
pr = St.prefs()
STATE = {"studio_win": None}


def shot(name):
    win = STATE["studio_win"] or bpy.context.window_manager.windows[0]
    path = os.path.join(OUT, name + ".png")
    with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
        bpy.ops.screen.screenshot(filepath=path)
    log("screenshot", file=name + ".png")


@guard
def step_build():
    win = bpy.context.window_manager.windows[0]
    sc = bpy.data.scenes.new("Ship Deck 1")
    win.scene = sc
    with bpy.context.temp_override(window=win, scene=sc):
        Li.render_setup(sc)
        Li.space_world()
        t = time.time()
        info = S.build("deck1")
        hits = collide.audit_objects(list(sc.objects))
        for d in S.door_controls().values():
            d["open"] = 1.0
        bpy.context.view_layer.update()
        hits_open = collide.audit_objects(list(sc.objects))
        for d in S.door_controls().values():
            d["open"] = 0.0
        bpy.context.view_layer.update()
    log("build", seconds=round(time.time() - t, 1), rooms=[r["key"] for r in info["rooms"]], device=sc.cycles.device,
        intersections=len(hits), intersections_doors_open=len(hits_open), pairs=hits[:10] + hits_open[:10])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Ship_deck1.blend"))


@guard
def step_studio():
    wm = bpy.context.window_manager
    win = wm.windows[0]
    before = set(wm.windows[:])
    with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
        bpy.ops.ship.open_studio()
    new = [w for w in wm.windows if w not in before]
    STATE["studio_win"] = new[0] if new else None
    log("studio opened", windows=len(wm.windows), areas=[a.type for a in (new[0].screen.areas if new else [])])


@guard
def step_pick_set():
    st = St.state()
    st.cat = "SETS"
    st.selected = "SETS:deck1"
    St.show_preview(St.selected_item(bpy.context))
    shot("studio_sets")


@guard
def step_pick_room():
    st = St.state()
    st.cat = "ROOMS"
    st.selected = "ROOMS:bridge"
    St.show_preview(St.selected_item(bpy.context))
    shot("studio_rooms")


@guard
def step_pick_mood():
    st = St.state()
    st.cat = "MOODS"
    st.selected = "MOODS:RED_ALERT"
    St.show_preview(St.selected_item(bpy.context))
    shot("studio_moods")


@guard
def step_stills():
    sc = bpy.data.scenes["Ship Deck 1"]
    Li.camera_finish(sc)
    sc.cycles.samples = 128
    cams = [("Ship Wide", 1920, 1080), ("Corridor Walkthrough", 1080, 1350), ("Command centre Wide master", 1080, 1350)]
    # a close look at one docked doorway, from inside the corridor, door open
    from mathutils import Vector
    info = S.info(sc)
    corr = next(r for r in info["rooms"] if r["key"] == "corridor")
    cd = bpy.data.cameras.new("Joint check")
    cd.lens = 24
    cam = bpy.data.objects.new("Joint check", cd)
    sc.collection.objects.link(cam)
    cam.location = (corr["x"] + 0.6, 0.35, 1.5)
    tgt = Vector((corr["x"] + corr["W"] / 2 + 1.0, 1.5, 1.0))
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    for d in S.door_controls().values():
        if d["sb_door"] in ("Corridor Door 2", "Command centre Door 1"):
            d["open"] = 1.0
    cams.append(("Joint check", 1080, 1350))
    times = {}
    for name, w, h in cams:
        sc.camera = bpy.data.objects[name]
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.image_settings.file_format = "JPEG"
        sc.render.filepath = os.path.join(OUT, "ship_" + name.replace(" ", "_") + ".jpg")
        t = time.time()
        with bpy.context.temp_override(scene=sc):
            bpy.ops.render.render(write_still=True, scene=sc.name)
        times[name] = round(time.time() - t, 1)
    for d in S.door_controls().values():
        d["open"] = 0.0
    log("stills", times=times)


@guard
def step_bake():
    import subprocess
    script = os.path.join(os.path.dirname(SB.__file__), "bake_previews.py")
    t = time.time()
    p = subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "--python", script, "--",
                        os.path.dirname(os.path.dirname(SB.__file__)), "ship_builder", THUMBS, "ALL",
                        bpy.path.abspath(pr.kit_dir if pr else ""), bpy.path.abspath(pr.deep_root if pr else "")],
                       capture_output=True, text=True, timeout=5400)
    lines = [l for l in (p.stdout + p.stderr).splitlines() if l.startswith("BAKE") or "Error" in l][-60:]
    log("bake", seconds=round(time.time() - t, 1), returncode=p.returncode, lines=lines, files=sorted(os.listdir(THUMBS)))


@guard
def step_studio_after_bake():
    if pr:
        pr.thumbs_dir = THUMBS
    st = St.state()
    st.cat = "PROPS"
    st.selected = "PROPS:crate"
    St.show_preview(St.selected_item(bpy.context))
    shot("studio_props")
    st.cat = "SETS"
    st.selected = "SETS:deck1"
    St.show_preview(St.selected_item(bpy.context))
    shot("studio_sets_baked")


STEPS = [step_build, step_studio, step_pick_set, step_pick_room, step_pick_mood, step_stills, step_bake, step_studio_after_bake]
if "--quick" in args:  # layout check only: no stills, no bake
    STEPS = [step_build, step_studio, step_pick_set, step_pick_room, step_pick_mood, step_studio_after_bake]


def tick():
    if not STEPS:
        log("done", errors=len(REP["errors"]))
        bpy.ops.wm.quit_blender()
        return None
    STEPS.pop(0)()
    return 1.0  # let the windows redraw before the next step


bpy.app.timers.register(tick, first_interval=3.0)
