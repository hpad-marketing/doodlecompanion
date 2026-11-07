"""Everything the Ship Studio library shows, as plain data with a picture each.

    catalog.items(category, prefs) -> [Item]
    CATEGORIES -> [(id, label, icon)]

Pictures come from, in order: the user's thumbnail cache (filled by "Bake
previews"), the add-on's own thumbs/ folder, and the scans folder. Moving
previews (.mp4) are used when present. Nothing heavy is loaded to list items:
droid motions are read from the droid's .blend without opening it.
"""
import json
import os

import bpy

from . import ship as S
from . import props as Pr
from . import lighting as Li

HERE = os.path.dirname(__file__)
CATEGORIES = [
    ("SETS", "Sets", "HOME"),
    ("ROOMS", "Rooms", "MESH_CUBE"),
    ("DROIDS", "Droids", "ARMATURE_DATA"),
    ("MOTIONS", "Motions", "ACTION"),
    ("PROPS", "Props", "PACKAGE"),
    ("CAMERAS", "Cameras", "CAMERA_DATA"),
    ("MOODS", "Moods", "LIGHT_SUN"),
    ("VIEWS", "Window views", "WORLD"),
    ("SHIP", "Hero ship", "OUTLINER_OB_FORCE_FIELD"),
    ("POSES", "Poses", "POSE_HLT"),
    ("MOVES", "Camera moves", "VIEW_CAMERA"),
    ("SCENE", "In this scene", "OUTLINER"),
]
ROOM_LABELS = {"lounge": "Oil lounge", "bridge": "Command centre", "corridor": "Corridor"}


class Item:
    __slots__ = ("cat", "id", "label", "blurb", "thumb", "movie", "data")

    def __init__(self, cat, id, label, blurb="", thumb=None, movie=None, data=None):
        self.cat, self.id, self.label, self.blurb = cat, id, label, blurb
        self.thumb, self.movie, self.data = thumb, movie, data or {}

    @property
    def key(self):
        return f"{self.cat}:{self.id}"


def _dirs(prefs):
    out = []
    if prefs is not None and getattr(prefs, "thumbs_dir", ""):
        out.append(bpy.path.abspath(prefs.thumbs_dir))
    out.append(os.path.join(HERE, "thumbs"))
    if prefs is not None and getattr(prefs, "scans_dir", ""):
        out.append(bpy.path.abspath(prefs.scans_dir))
    return [d for d in out if d and os.path.isdir(d)]


def find(prefs, *names, movie=False):
    exts = (".mp4", ".mov") if movie else (".jpg", ".png", ".jpeg")
    for d in _dirs(prefs):
        for n in names:
            for e in exts:
                p = os.path.join(d, n + e)
                if os.path.isfile(p):
                    return p
    return None


def _safe(s):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s)


# ------------------------------------------------------------------ droids
def droids(prefs):
    """Droid kit entries: droids/<id>.json with folder + current_file."""
    kit = bpy.path.abspath(getattr(prefs, "kit_dir", "") or "")
    root = bpy.path.abspath(getattr(prefs, "deep_root", "") or "")
    out = []
    d = os.path.join(kit, "droids")
    if not os.path.isdir(d):
        return out


def _diagram_dir(prefs):
    d = bpy.path.abspath(getattr(prefs, "thumbs_dir", "") or "") if prefs is not None else ""
    return d or os.path.join(bpy.app.tempdir or os.path.expanduser("~"), "sb_thumbs")


def _room_key(sc):
    try:
        info = json.loads(sc["sb_ship"])
        return [r.get("key") for r in info.get("rooms", []) if r.get("key")]
    except (KeyError, ValueError, TypeError):
        return []


def scene_items(prefs):
    """Everything in the open file and scene, each with the best picture we have."""
    out = []
    sc = bpy.context.scene
    for s in bpy.data.scenes:
        keys = _room_key(s)
        th = next((find(prefs, f"room_{k}") for k in keys if find(prefs, f"room_{k}")), None)
        here = " (open)" if s == sc else ""
        out.append(Item("SCENE", f"scene:{s.name}", s.name + here, "Scene: click Use to switch to it", th, None,
                        dict(kind="scene", name=s.name)))
    for o in sc.objects:
        if o.type == "ARMATURE" and (o.get("sb_droid") or o.get("sb_cast")):
            did = str(o.get("sb_droid") or o.get("sb_cast"))
            name = next((c.name[6:].split(" (")[0] for c in o.users_collection if c.name.startswith("Droid ")), o.name)
            out.append(Item("SCENE", f"obj:{o.name}", name, "Droid", find(prefs, f"droid_{did}"), find(prefs, f"droid_{did}", movie=True),
                            dict(kind="droid", name=o.name)))
    seen = set()
    for o in sc.objects:
        pid = o.get("sb_prop")
        if pid and o.parent is None and o.name not in seen:
            seen.add(o.name)
            lab = Pr.PROPS.get(pid, (pid,))[0]
            out.append(Item("SCENE", f"obj:{o.name}", lab, "Prop", find(prefs, f"prop_{pid}"), None, dict(kind="object", name=o.name)))
    for o in sc.objects:
        if o.type == "CAMERA":
            out.append(Item("SCENE", f"obj:{o.name}", o.name, "Camera: Use looks through it",
                            find(prefs, f"cam_{_safe(o.name)}"), None, dict(kind="camera", name=o.name)))
    return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                j = json.load(f)
        except (OSError, ValueError):
            continue
        blend = os.path.join(root, j.get("folder", ""), j.get("current_file", ""))
        out.append(dict(id=j.get("id", fn[:-5]), name=j.get("name", fn[:-5]), blend=blend, rig=j.get("rig", ""),
                        folder=os.path.join(root, j.get("folder", "")),
                        **{k: j[k] for k in ("set_height", "mass_kg") if k in j}))
    return out


_MOTION_CACHE = {}


def motions(blend):
    """Action names in a droid .blend, read without opening it (cached by mtime)."""
    if not blend or not os.path.isfile(blend):
        return []
    mt = os.path.getmtime(blend)
    hit = _MOTION_CACHE.get(blend)
    if hit and hit[0] == mt:
        return hit[1]
    with bpy.data.libraries.load(blend, link=False) as (src, _dst):
        names = sorted(n for n in src.actions)
    _MOTION_CACHE[blend] = (mt, names)
    return names


# ------------------------------------------------------------------ hero ship
def hero_manifest(prefs):
    d = bpy.path.abspath(getattr(prefs, "hero_dir", "") or "")
    p = os.path.join(d, "manifest.json")
    if not os.path.isfile(p):
        return d, []
    try:
        with open(p, encoding="utf-8") as f:
            m = json.load(f)
    except (OSError, ValueError):
        return d, []
    return d, (m.get("presets", m) if isinstance(m, dict) else m)


# ------------------------------------------------------------------ items
def items(cat, prefs=None, droid=None):
    out = []
    if cat == "SETS":
        for k, v in S.LAYOUTS.items():
            if len(v["rooms"]) > 1:
                out.append(Item(cat, k, v["label"], v["blurb"], find(prefs, f"set_{k}"), find(prefs, f"set_{k}", movie=True)))
    elif cat == "ROOMS":
        from .rooms import ROOMS
        for k, mod in ROOMS.items():
            lab = mod.INFO.get("label", k)
            out.append(Item(cat, k, lab, f"{mod.INFO['size'][0]:g} x {mod.INFO['size'][1]:g} m",
                            find(prefs, f"room_{k}", f"{k}_Wide_master_NORMAL", f"{k}_Walkthrough_NORMAL")))
    elif cat == "DROIDS":
        for d in droids(prefs):
            out.append(Item(cat, d["id"], d["name"], os.path.basename(d["blend"]),
                            find(prefs, f"droid_{d['id']}"), find(prefs, f"droid_{d['id']}", movie=True), d))
    elif cat == "MOTIONS":
        ds = droids(prefs)
        d = next((x for x in ds if x["id"] == droid), ds[0] if ds else None)
        if d:
            for a in motions(d["blend"]):
                n = f"motion_{d['id']}_{_safe(a)}"
                out.append(Item(cat, a, a.replace("RM_", "").replace("_", " ").capitalize(), d["name"],
                                find(prefs, n), find(prefs, n, movie=True), dict(droid=d["id"], blend=d["blend"], rig=d["rig"])))
    elif cat == "PROPS":
        for k, (lab, _fn) in Pr.PROPS.items():
            out.append(Item(cat, k, lab, "", find(prefs, f"prop_{k}")))
    elif cat == "CAMERAS":
        info = S.info(bpy.context.scene)
        cams = [c["name"] for c in info["cameras"]] if info else [o.name for o in bpy.context.scene.objects if o.type == "CAMERA"]
        for c in cams:
            if c in bpy.data.objects:
                out.append(Item(cat, c, c, "", find(prefs, f"cam_{_safe(c)}", _safe(c).replace("Oil_lounge_", "lounge_").replace("Command_centre_", "bridge_") + "_NORMAL")))
    elif cat == "MOODS":
        for k in Li.MOODS:
            out.append(Item(cat, k, k.replace("_", " ").capitalize(), "", find(prefs, f"mood_{k}", f"lounge_Wide_master_{k}", f"bridge_Wide_master_{k}")))
    elif cat == "VIEWS":
        from . import views as V
        for k, (lab, *_r) in V.VIEWS.items():
            out.append(Item(cat, k, lab, "Seen through every window; the sunlight follows it", find(prefs, f"view_{k}")))
    elif cat == "POSES":
        from . import posekit as PK
        ds = droids(prefs)
        d = next((x for x in ds if x["id"] == droid), ds[0] if ds else None)
        did = d["id"] if d else "droid"
        for k, (lab, _o, _l) in PK.POSES.items():
            out.append(Item(cat, k, lab, f"{d['name'] if d else 'Droid'}: click Use to pose the droid in the scene",
                            find(prefs, f"pose_{did}_{k}") or find(prefs, f"droid_{did}"), None, dict(droid=did)))
    elif cat == "MOVES":
        from . import cammoves as CM
        dd = _diagram_dir(prefs)
        for k, (lab, secs, blurb) in CM.MOVES.items():
            th = find(prefs, f"move_{k}")
            if th is None:
                try:
                    th = CM.diagram(k, dd)
                except OSError:
                    th = None
            out.append(Item(cat, k, lab, f"{blurb} ({secs:g} s from the playhead)", th, find(prefs, f"move_{k}", movie=True)))
    elif cat == "SCENE":
        out = scene_items(prefs)
    elif cat == "SHIP":
        d, pres = hero_manifest(prefs)
        for p in pres:
            pid = p.get("id")
            th = os.path.join(d, p["thumb"]) if p.get("thumb") else None
            mv = os.path.join(d, p["mp4"]) if p.get("mp4") else None
            out.append(Item(cat, pid, p.get("label", pid), f"{p.get('frames', '')} frames", th if th and os.path.isfile(th) else None,
                            mv if mv and os.path.isfile(mv) else None, p))
    return out
