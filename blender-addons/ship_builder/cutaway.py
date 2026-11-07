"""Set view: work in the rooms like a sitcom set.

The front of every room is open (its fourth wall is camera-transparent for
renders and hidden in the viewport). On top of that, while you orbit, any wall
or ceiling that stands between your eye and a room is cut away, together with
what is mounted on it (screens, pipes, lights), so you always see into the set.
Renders are untouched: only viewport visibility changes.

    cutaway.tag(scene)   once after a build: which side of its room each part sits on
    cutaway.start()      the timer that follows the view (Ship Studio starts it)
"""
import bpy
from mathutils import Vector

MOUNT = 0.35        # parts within this of a wall plane belong to that wall
CEIL = 0.6          # parts this close under the ceiling belong to the ceiling
TAG_V = 3           # sets tagged by an older build are tagged again on first view
CAM_SIZE = 0.25
_STATE = {"on": False, "eye": None, "hidden": set()}


def _objects(col):
    seen = set()
    stack = [col]
    while stack:
        c = stack.pop()
        for o in c.objects:
            if o.name not in seen:
                seen.add(o.name)
                yield o
        stack.extend(c.children)


def tag(scene=None):
    """Mark every wall, ceiling and wall-mounted part with the side(s) it belongs to."""
    from . import ship as S
    sc = scene or bpy.context.scene
    info = S.info(sc)
    if not info:
        return 0
    n = 0
    for r in info["rooms"]:
        col = bpy.data.collections.get(r.get("collection", ""))
        if col is None:
            continue
        ox, oy, W, D, H = r["x"], r["y"], r["W"], r["D"], r["H"]
        for ob in _objects(col):
            if ob.get("sb_fourth_wall"):
                ob.hide_viewport = True     # the open front of the set, always
                continue
            if ob.get("sb_haze") or ob.get("sb_view_only") or ob.name.startswith("Planet"):
                ob["sb_cut"] = "open"       # room fog and window scenery: only through the camera
                ob["sb_room"] = r["name"]
                n += 1
                continue
            if ob.type not in {"MESH", "CURVE", "FONT", "LIGHT"} or ob.get("sb_droid") or ob.get("sb_door"):
                continue
            bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box] if ob.type != "LIGHT" else [ob.matrix_world.translation]
            xs = [v.x - ox for v in bb]
            ys = [v.y - oy for v in bb]
            zs = [v.z for v in bb]
            sides = []
            if min(xs) < -W / 2 + MOUNT:
                sides.append("left")
            if max(xs) > W / 2 - MOUNT:
                sides.append("right")
            if max(ys) > D - MOUNT:
                sides.append("back")
            if min(zs) > H - CEIL:
                sides.append("ceiling")
            # a room-sized part (the floor, a whole shell) is not one wall's
            if (max(xs) - min(xs) > W * 0.9 and max(ys) - min(ys) > D * 0.9 and "ceiling" not in sides) or max(zs) < 0.05:
                sides = []
            # furniture standing near a wall stays: only parts that reach high up the wall or hang on it go
            if sides and sides != ["ceiling"] and max(zs) < 1.2 and min(zs) < 0.05 and not ob.name.startswith(("Wall", "Skirting", "Corner", "Back", "Left", "Right", "Panel", "Rib", "Pillar", "Column")):
                sides = [s for s in sides if s == "ceiling"]
            if sides:
                ob["sb_cut"] = ",".join(sides)
                ob["sb_room"] = r["name"]
                n += 1
    for ob in sc.objects:              # a set camera drawn at 1 m blacks out the view when you walk past it
        if ob.type == "CAMERA" and ob.data.display_size > CAM_SIZE:
            ob.data.display_size = CAM_SIZE
    sc["sb_cut_v"] = TAG_V
    return n


def _eye():
    """Eye of the biggest 3D view (the camera when it looks through one)."""
    e = _view()
    return e[0], e[1]


def _view():
    """(eye, scene, through_camera) of the biggest 3D view."""
    best = None
    for win in bpy.context.window_manager.windows:
        for a in win.screen.areas:
            if a.type != "VIEW_3D":
                continue
            r3 = a.spaces.active.region_3d
            if r3 is None:
                continue
            cam = r3.view_perspective == "CAMERA" and win.scene.camera is not None
            if cam:
                eye = win.scene.camera.matrix_world.translation.copy()
            else:
                eye = r3.view_matrix.inverted().translation.copy()
            if best is None or a.width * a.height > best[0]:
                best = (a.width * a.height, eye, win.scene, cam)
    return (best[1], best[2], best[3]) if best else (None, None, False)


def update(scene=None, eye=None, camera=None):
    from . import ship as S
    if eye is None:
        eye, scene, camera = _view()
    if eye is None or scene is None:
        return
    info = S.info(scene)
    if not info:
        return
    if scene.get("sb_cut_v") != TAG_V:
        tag(scene)
    on = scene.get("sb_set_view", 1)
    rooms = {r["name"]: r for r in info["rooms"]}
    want = set()
    if on:
        for r in rooms.values():
            lx, ly = eye.x - r["x"], eye.y - r["y"]
            cut = set()
            if lx < -r["W"] / 2:
                cut.add("left")
            if lx > r["W"] / 2:
                cut.add("right")
            if ly > r["D"]:
                cut.add("back")
            if eye.z > r["H"]:
                cut.add("ceiling")
            if not camera:
                cut.add("open")
            r["_cut"] = cut
    vl = bpy.context.view_layer
    for ob in scene.objects:
        tags = ob.get("sb_cut")
        if not tags:
            continue
        r = rooms.get(ob.get("sb_room"))
        hide = bool(on and r and any(t in r.get("_cut", ()) for t in tags.split(",")))
        if hide:
            want.add(ob.name)
        if hide != ob.hide_get(view_layer=vl):
            try:
                ob.hide_set(hide, view_layer=vl)
            except RuntimeError:
                pass
    _STATE["hidden"] = want


def _tick():
    if not _STATE["on"]:
        return None
    eye, sc, cam = _view()
    if eye is not None and (_STATE["eye"] is None or (eye - _STATE["eye"]).length > 0.05 or cam != _STATE.get("cam")):
        _STATE["eye"], _STATE["cam"] = eye, cam
        try:
            update(sc, eye, cam)
        except Exception as e:   # a view helper must never break the studio
            print("Ship Studio set view:", e)
    return 0.15


def start():
    if not _STATE["on"]:
        _STATE["on"] = True
        bpy.app.timers.register(_tick, first_interval=0.3, persistent=True)


def stop():
    _STATE["on"] = False
