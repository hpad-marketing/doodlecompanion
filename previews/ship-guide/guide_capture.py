"""Ship Builder guide: capture real UI screenshots on Sushi.

Run in a normal Blender 5.0 window (installed add-on, no --factory-startup):
    blender.exe --python guide_capture.py -- <out dir>

Opens Ship Studio, walks through: set/room, droid, handles + pose, motion,
prop, mood, window view, camera + camera move, In this scene, Episodes bar,
then saves a .blend, renders one small still and quits. Every screenshot is the
full window plus a JSON record of where each area sits, so the guide can crop
and annotate. Never touches any other .blend.
"""
import json
import os
import sys
import time
import traceback

import bpy

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(args[0] if args else os.path.join(os.path.expanduser("~"), "Documents", "DeepInDoodles", "Ship", "guide_shots"))
os.makedirs(OUT, exist_ok=True)
REP = {"shots": [], "errors": [], "log": []}
T0 = time.time()


def mod(tail):
    for n, m in list(sys.modules.items()):
        if n.endswith("ship_builder." + tail) or n == "ship_builder." + tail:
            return m
    raise RuntimeError("module not loaded: " + tail)


def save_rep():
    json.dump(REP, open(os.path.join(OUT, "report.json"), "w"), indent=1)


def log(*a):
    s = " ".join(str(x) for x in a)
    REP["log"].append(f"{time.time() - T0:6.1f} {s}")
    print("GUIDE", s, flush=True)
    save_rep()


W = {"studio": None, "main": None}


def areas_of(win):
    out = []
    for a in win.screen.areas:
        out.append({"type": a.type, "ui": a.ui_type, "x": a.x, "y": a.y, "w": a.width, "h": a.height})
    return out


def shot(name, win=None, note=""):
    win = win or W["studio"] or bpy.context.window_manager.windows[0]
    path = os.path.join(OUT, name + ".png")
    a0 = win.screen.areas[0]
    with bpy.context.temp_override(window=win, screen=win.screen, area=a0):
        bpy.ops.screen.screenshot(filepath=path)
    REP["shots"].append({"name": name, "note": note, "win": {"w": win.width, "h": win.height},
                         "areas": areas_of(win)})
    log("shot", name)


def ov(win=None, kind=None):
    win = win or W["studio"]
    area = next((a for a in win.screen.areas if kind is None or a.type == kind), win.screen.areas[0])
    reg = next((r for r in area.regions if r.type == "WINDOW"), None)
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=reg, scene=win.scene)


def St():
    return mod("studio")


def pick(cat, prefer=()):
    s = St()
    st = s.state()
    st.cat = cat
    items = s.current_items(bpy.context)
    if not items:
        log("no items in", cat)
        return None
    it = next((i for p in prefer for i in items if p.lower() in (i.id + " " + i.label).lower()), items[0])
    with ov():
        bpy.ops.ship.pick(key=it.key)
    log("picked", cat, it.key, "of", len(items), "with pictures", sum(1 for i in items if i.thumb or i.movie))
    return it


def use():
    with ov():
        r = bpy.ops.ship.use()
    log("use ->", r)


def view3d_studio():
    return next(a for a in W["studio"].screen.areas if a.type == "VIEW_3D")


def free_view_on(ob, dist_mul=1.0):
    a = view3d_studio()
    sp = a.spaces.active
    sp.region_3d.view_perspective = "PERSP"
    reg = next(r for r in a.regions if r.type == "WINDOW")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    with bpy.context.temp_override(window=W["studio"], screen=W["studio"].screen, area=a, region=reg):
        bpy.ops.view3d.view_selected()
    sp.region_3d.view_distance *= dist_mul


def camera_view():
    a = view3d_studio()
    a.spaces.active.region_3d.view_perspective = "CAMERA"


def rig():
    return next((o for o in bpy.context.scene.objects if o.type == "ARMATURE" and o.get("sb_droid")), None)


# ------------------------------------------------------------------ steps
def s00_main():
    W["main"] = bpy.context.window_manager.windows[0]
    shot("00_blender_main", W["main"], "plain Blender, Window menu at top")


def set_droid(did="rx07"):
    try:
        St().state().droid = did
    except Exception:
        log("droid enum set failed", did)


def tidy_view():
    sp = view3d_studio().spaces.active
    try:
        sp.overlay.show_relationship_lines = False
        sp.overlay.show_extras = False
    except Exception:
        pass


def s01_window_menu():
    try:
        with ov(W["main"]):
            bpy.ops.wm.call_menu(name="TOPBAR_MT_window")
    except Exception:
        log("menu open failed")


def s02_menu_shot():
    shot("01_window_menu", W["main"], "Window menu open, Ship Studio at the bottom")


def s03_open():
    wm = bpy.context.window_manager
    before = set(wm.windows[:])
    with ov(W["main"]):
        bpy.ops.ship.open_studio()
    new = [w for w in wm.windows if w not in before]
    W["studio"] = new[0] if new else wm.windows[-1]
    log("studio window", W["studio"].width, W["studio"].height)


def s04_max():
    try:
        with ov():
            bpy.ops.wm.window_fullscreen_toggle()
    except Exception:
        log("fullscreen toggle failed")


def s05_sets():
    pick("SETS", ("deck1",))


def s06_sets_shot():
    shot("02_sets_tab", note="Library > Sets, a set picked, big preview")


def s07_rooms():
    pick("ROOMS", ("lounge",))


def s08_rooms_shot():
    shot("03_rooms_tab", note="Rooms tab, lounge picked, Build room button")


def s09_build():
    use()


def s09b_cam():
    tidy_view()
    pick("CAMERAS", ("wide master", "wide"))
    use()
    camera_view()


def s10_built():
    camera_view()
    shot("04_room_built", note="room built, live camera view on the right")


def s11_droids():
    pick("DROIDS", ("rx07", "rx-07"))


def s12_droids_shot():
    shot("05_droids_tab", note="Droids tab, RX-07 picked, Add droid button")


def s13_add_droid():
    use()


def s14_droid_added():
    r = rig()
    if r:
        bpy.context.scene.cursor.location = (r.location.x + 1.2, r.location.y, 0)
    shot("06_droid_added", note="droid in the room, Droid controls box in the panel")


def s15_handles():
    r = rig()
    if r:
        free_view_on(r, 0.75)
        bpy.context.scene["sb_handles"] = 1


def s16_handles_shot():
    shot("07_handles", note="drag handles on the droid (blue left, red right, yellow middle)")


def s17_pose_mode():
    r = rig()
    if r:
        with ov(kind="VIEW_3D"):
            try:
                bpy.ops.ship.pose(rig=r.name)
            except Exception:
                log("ship.pose failed", traceback.format_exc()[-300:])


def s18_pose_mode_shot():
    shot("08_pose_mode", note="Pose mode via Pose button")


def s19_poses():
    set_droid()
    pick("POSES", ("wave", "point", "think"))


def s20_poses_shot():
    shot("09_poses_tab", note="Poses tab, a pose picked")


def s21_apply_pose():
    use()


def s22_posed():
    r = rig()
    if r:
        free_view_on(r, 0.75)
    shot("10_posed", note="pose applied")


def s23_motions():
    try:
        with ov():
            if bpy.context.mode == "POSE":
                bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass
    set_droid()
    pick("MOTIONS", ("walk", "idle"))


def s24_motions_shot():
    shot("11_motions_tab", note="Motions tab with clip preview")


def s25_props():
    pick("PROPS", ("couch", "chair", "crate"))


def s26_props_shot():
    shot("12_props_tab", note="Props tab, prop picked")


def s27_add_prop():
    use()


def s28_prop_added():
    props = [o for o in bpy.context.scene.objects if o.get("sb_prop") and o.parent is None]
    ob = props[-1] if props else None
    if ob:
        free_view_on(ob, 1.6)
    shot("13_prop_added", note="prop added at the 3D cursor")


def s29_moods():
    camera_view()
    pick("MOODS", ("red", "alert"))


def s30_moods_shot():
    shot("14_moods_tab", note="Moods tab")


def s31_apply_mood():
    use()


def s32_mood_applied():
    shot("15_mood_applied", note="mood applied in the live view")


def s33_views():
    pick("VIEWS", ("hyper", "nebula", "planet"))


def s34_views_shot():
    shot("16_window_views", note="Window views tab")


def s35_cams():
    pick("CAMERAS", ("wide",))


def s36_cams_shot():
    shot("17_cameras_tab", note="Cameras tab")


def s37_look():
    use()


def s38_moves():
    pick("MOVES", ("push", "dolly", "orbit"))


def s39_moves_shot():
    shot("18_camera_moves", note="Camera moves tab")


def s40_key_move():
    use()


def s41_scene():
    pick("SCENE")


def s42_scene_shot():
    shot("19_in_this_scene", note="In this scene tab")


def s43_episodes():
    with ov():
        bpy.ops.ship.station(station="BOARD")


def s44_episodes_shot():
    shot("20_episodes_board", note="Episodes board and seven stations")


def s45_back():
    with ov():
        bpy.ops.ship.station(station="LIBRARY")
    sc = bpy.context.scene
    sc.render.filepath = os.path.join(OUT, "render", "frame_")
    # show Output properties in the main window for the export page
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Guide_scene.blend"), copy=True)
    log("saved guide blend")


def s46_output_win():
    wm = bpy.context.window_manager
    before = set(wm.windows[:])
    with ov():
        bpy.ops.wm.window_new()
    new = [w for w in wm.windows if w not in before]
    W["out"] = new[0] if new else None
    if W["out"]:
        W["out"].scene = W["studio"].scene
        a = max(W["out"].screen.areas, key=lambda a: a.width * a.height)
        a.ui_type = "PROPERTIES"
        a.spaces.active.context = "OUTPUT"


def s46b_output_shot():
    if W.get("out"):
        shot("21_output_props", W["out"], "Output properties: frame range, file path, format")


def s47_render():
    if "trial" in args:
        log("trial: render skipped")
        return
    sc = W["studio"].scene
    sc.render.resolution_percentage = 50
    try:
        sc.cycles.samples = 64
    except Exception:
        pass
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = os.path.join(OUT, "22_render_result.png")
    t = time.time()
    with ov():
        bpy.ops.render.render(write_still=True)
    log("render still", round(time.time() - t, 1), "s", sc.render.engine)


def s99_quit():
    save_rep()
    bpy.ops.wm.quit_blender()


STEPS = [v for k, v in sorted(globals().items()) if k[:1] == "s" and k[1:3].isdigit() and callable(v) and k[3:4] in ("_", "b")]
I = {"n": 0}


def tick():
    if I["n"] >= len(STEPS):
        return None
    fn = STEPS[I["n"]]
    I["n"] += 1
    try:
        fn()
    except Exception:
        REP["errors"].append(fn.__name__ + "\n" + traceback.format_exc())
        log("ERROR in", fn.__name__)
    for w in bpy.context.window_manager.windows:
        for ar in w.screen.areas:
            ar.tag_redraw()
    # building and loading pictures need time to settle and redraw
    slow = fn.__name__ in ("s09_build", "s09b_cam", "s13_add_droid", "s47_render", "s03_open", "s04_max", "s31_apply_mood")
    return 14.0 if slow else 3.5


bpy.app.timers.register(tick, first_interval=6.0, persistent=True)
log("guide capture armed", bpy.app.version_string, len(STEPS), "steps")
