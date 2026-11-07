"""Ship set: rooms that dock door to door and load into one scene at once.

    ship.LAYOUTS                       -> {id: {label, rooms, blurb}}
    ship.build("deck1", wear=1.0, seed=1) -> info dict (also stored on the scene)
    ship.info(scene)                   -> the stored info, for walk mode and the UI

Rooms are built one after another at the origin, then slid sideways into place,
so every room keeps its own collision-checked build. Neighbouring rooms leave a
small gap between their outer wall skins; at each docked door the blank door
back is removed and a short lined passage bridges the gap. A bulkhead rib in
front of every joint hides the seam from the cameras.
"""
import json
import bpy
from mathutils import Vector

from . import kit as K
from . import mats as M
from . import lighting as Li
from . import physics as P
from .rooms import ROOMS

GAP = 0.16          # outer wall face to outer wall face (wall skins reach 0.065 out)
PASS_H = 1.95       # clear height under the door lintel

LAYOUTS = {
    "deck1": {"label": "Deck 1", "rooms": ["lounge", "corridor", "bridge"],
              "blurb": "Crew lounge, corridor and command centre"},
    "lounge_only": {"label": "Lounge", "rooms": ["lounge"], "blurb": "Just the crew lounge"},
    "bridge_only": {"label": "Command centre", "rooms": ["bridge"], "blurb": "Just the command centre"},
    "deck2": {"label": "Deck 2", "rooms": ["charging", "corridor", "repair"],
              "blurb": "Charging stations, corridor and repair bay"},
    "charging_only": {"label": "Charging stations", "rooms": ["charging"], "blurb": "Just the charging stations"},
    "repair_only": {"label": "Repair bay", "rooms": ["repair"], "blurb": "Just the repair bay"},
    "deck3": {"label": "Deck 3", "rooms": ["observation", "corridor", "engine"],
              "blurb": "Observation deck, corridor and engine room"},
    "deck4": {"label": "Deck 4", "rooms": ["workshop", "corridor", "cargo"],
              "blurb": "Workshop, corridor and cargo hold"},
    "deck5": {"label": "Deck 5", "rooms": ["rest", "corridor", "plants"],
              "blurb": "Rest pods, corridor and plant room"},
    "deck6": {"label": "Deck 6", "rooms": ["junk", "corridor", "airlock"],
              "blurb": "Junk room, corridor and airlock"},
}
for _k in ("observation", "engine", "cargo", "airlock", "workshop", "rest", "junk", "plants"):
    LAYOUTS[f"{_k}_only"] = {"label": ROOMS[_k].INFO["label"], "rooms": [_k], "blurb": f"Just the {ROOMS[_k].INFO['label'].lower()}"}


def _doors(key):
    return ROOMS[key].INFO.get("doors", {})


def plan(keys):
    """Offsets for a chain of rooms: each room's right door docks to the next one's left door."""
    out, x, y = [], 0.0, 0.0
    for i, key in enumerate(keys):
        W = ROOMS[key].INFO["size"][0]
        if i:
            prev = keys[i - 1]
            pW = ROOMS[prev].INFO["size"][0]
            pr, nl = _doors(prev).get("right"), _doors(key).get("left")
            if pr is None or nl is None:
                raise ValueError(f"{prev} has no right door or {key} has no left door to dock")
            x += pW / 2 + GAP + W / 2
            y = out[-1][2] + pr - nl
        out.append((key, x, y))
    return out


def _shift(room, d):
    """Slide a finished room by d (world). Door leaf drivers carry absolute rest
    positions, so they are rewritten too."""
    objs = list(room.root.all_objects)
    for ob in objs:
        if ob.parent is None:
            ob.location += d
    for ob in objs:
        ad = ob.animation_data
        if not ad:
            continue
        for fc in ad.drivers:
            if fc.data_path == "location" and fc.array_index in (0, 1) and " + " in fc.driver.expression:
                a, b = fc.driver.expression.split(" + ", 1)
                fc.driver.expression = f"{float(a) + d[fc.array_index]:.5f} + {b}"
    for dr in getattr(room, "doors", []):
        dr["x"] += d.x
        dr["yc"] += d.y


def _joint(col, xa, yc, h_max, depth_a, depth_b, name):
    """Passage lining and seam cover between wall face xa and xa + GAP."""
    pal_hull = M.painted_metal("SB Paint Graphite", (0.045, 0.047, 0.05, 1), 0.42)
    dark = M.brushed_steel("SB Dark Steel", (0.25, 0.25, 0.26, 1), 0.35)
    deck = M.deck_plate()
    xb = xa + GAP
    xc, wx = (xa + xb) / 2, GAP - 0.004
    half = 0.74
    parts = []
    parts.append(K.box("Joint Deck", (wx, 2 * half + 0.04, 0.06), (xc, yc, -0.03), deck, col, bevel=0.002))
    # one continuous threshold: the gap between the two door sills is filled flush with them,
    # so a foot never has to stand half in a 15 cm dip between two raised strips
    parts.append(K.box("Joint Sill", (GAP - 0.006, 2 * half - 0.006, 0.02), (xc, yc, 0.0105), M.hazard(), col, bevel=0.003))
    parts.append(K.box("Joint Top", (wx, 2 * half + 0.04, 0.02), (xc, yc, PASS_H + 0.01), dark, col, bevel=0.002))
    for sd in (-1, 1):
        parts.append(K.box("Joint Side", (wx, 0.02, PASS_H), (xc, yc + sd * (half + 0.01), PASS_H / 2), dark, col, bevel=0.002))
    # a plate in the middle of the gap closes everything around the passage
    t = 0.016
    y0, y1 = yc - half - 0.02, yc + half + 0.02
    lo, hi = -0.06, h_max + 0.08
    d0, d1 = 0.0, max(depth_a, depth_b)
    if y0 - d0 > 0.01:
        parts.append(K.box("Joint Plate", (t, y0 - d0, hi - lo), (xc, (d0 + y0) / 2, (lo + hi) / 2), pal_hull, col, bevel=0))
    if d1 - y1 > 0.01:
        parts.append(K.box("Joint Plate", (t, d1 - y1, hi - lo), (xc, (y1 + d1) / 2, (lo + hi) / 2), pal_hull, col, bevel=0))
    parts.append(K.box("Joint Plate", (t, y1 - y0, hi - PASS_H - 0.02), (xc, yc, (PASS_H + 0.02 + hi) / 2), pal_hull, col, bevel=0))
    # bulkhead rib just in front of the fourth wall plane
    rib = K.box("Bulkhead Rib", (GAP + 0.12, 0.22, hi - lo), (xc, -0.17, (lo + hi) / 2), pal_hull, col, bevel=0.012)
    parts.append(rib)
    parts.append(K.box("Bulkhead Hazard", (GAP + 0.124, 0.004, 0.09), (xc, -0.282, 1.0), M.hazard(), col, bevel=0.001, segs=1))
    for p in parts:
        p["sb_group"] = f"joint:{name}"
        p["sb_joint"] = name
    return parts


def build(layout="deck1", wear=1.0, seed=1, settle=True):
    keys = LAYOUTS[layout]["rooms"] if isinstance(layout, str) else list(layout)
    steps = plan(keys)
    rooms, info = [], {"layout": layout if isinstance(layout, str) else "custom", "rooms": [], "doors": [], "links": [], "cameras": []}
    for i, (key, ox, oy) in enumerate(steps):
        room = ROOMS[key].build(wear=wear, wear_seed=seed + i)
        _shift(room, Vector((ox, oy, 0.0)))
        if i:  # one planet in the sky, not one per room
            for ob in list(room.root.all_objects):
                if ob.name.startswith(("Planet", "SB Ring")) or ob.get("sb_planet"):
                    bpy.data.objects.remove(ob)
        rooms.append(room)
        info["rooms"].append({"key": key, "name": room.name, "x": ox, "y": oy, "W": room.W, "D": room.D, "H": room.H,
                              "collection": room.root.name})
        for d in getattr(room, "doors", []):
            info["doors"].append({"id": d["id"], "room": room.name, "side": d["side"], "x": d["x"], "yc": d["yc"],
                                  "half": d["half"], "link": None})
    joints = K.coll("SB Ship Joints")
    by_id = {d["id"]: d for d in info["doors"]}
    for i in range(len(rooms) - 1):
        a, b = rooms[i], rooms[i + 1]
        da = next(d for d in a.doors if d["side"] == "right")
        db = next(d for d in b.doors if d["side"] == "left")
        for d in (da, db):
            for ob in list(bpy.data.objects):
                if ob.get("sb_door_back") == d["id"]:
                    bpy.data.objects.remove(ob)
        _joint(joints, da["x"], da["yc"], max(a.H, b.H), a.D + info["rooms"][i]["y"], b.D + info["rooms"][i + 1]["y"], f"{a.name}|{b.name}")
        by_id[da["id"]]["link"], by_id[db["id"]]["link"] = db["id"], da["id"]
        info["links"].append([da["id"], db["id"]])
    # one camera that sees the whole set, plus every room's own cameras
    x0 = info["rooms"][0]["x"] - info["rooms"][0]["W"] / 2
    x1 = info["rooms"][-1]["x"] + info["rooms"][-1]["W"] / 2
    span = x1 - x0
    hmax = max(r["H"] for r in info["rooms"])
    cam = Li.camera(rooms[0], "Ship wide", 24, ((x0 + x1) / 2, -max(4.0, span * 0.62), hmax * 0.75), ((x0 + x1) / 2, 2.5, hmax * 0.45), 11.0)
    cam.name = "Ship Wide"
    cam.data.dof.use_dof = False
    cam.parent = None
    for r in rooms:
        for ob in r.root.all_objects:
            if ob.type == "CAMERA":
                info["cameras"].append({"name": ob.name, "room": r.name, "label": ob.get("sb_cam", ob.name)})
    if settle:
        P.settle(bpy.context.scene)
    sc = bpy.context.scene
    sc["sb_ship"] = json.dumps(info)
    from . import screens as Sc
    info["screens"] = Sc.feeds(sc, seed=seed)  # every display plays live feeds and cuts at random
    first = next((bpy.data.objects.get(c["name"]) for c in info["cameras"] if c["room"] == rooms[0].name), None)
    if first:
        sc.camera = first
    return info


def info(scene=None):
    sc = scene or bpy.context.scene
    raw = sc.get("sb_ship")
    return json.loads(raw) if raw else None


def door_controls(scene=None):
    """{door id: control empty} for every door in the scene."""
    return {o["sb_door"]: o for o in bpy.data.objects if o.type == "EMPTY" and o.get("sb_door")}
