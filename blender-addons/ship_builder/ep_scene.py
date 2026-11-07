"""Ship Studio episode scenes: the Blender side of the episode workflow.

Every room the episode uses is built once into its own scene ("Ep03 · Engine
room"). All scenes share the episode clock, so frame 240 is the same moment
everywhere. Each story scene places its droids on marks in its room during its
own time range. The edit scene ("Ep03 · Edit") holds one scene strip per shot
(with the shot's camera) plus the voice clips, so playing it is the animatic and
rendering it is the episode.

    build(ep)                 rooms, droids on marks, cameras for every shot, edit
    voices_to_edit(ep)        sound strips for the picked takes
    apply_acting(ep)          P1 layers onto every droid (your own keys win)
    apply_events(ep)          P5 ship events drive lights, shake and screens
    run_check(ep)             R1 scene checks (intersections, feet, frame edges, props)
    still_frames(ep)          R2 one key frame per shot
"""
import json
import math
import os
import random

import bpy
from mathutils import Vector

from . import episode as E
from . import episode_flow as F
from . import ship as S
from . import lighting as Li
from . import pathing as PA
from .rooms import ROOMS

FPS = 24
EDIT = "{ep} · Edit"


def sec2f(s):
    return int(round(s * FPS)) + 1


def _scene(name):
    sc = bpy.data.scenes.get(name)
    if sc is None:
        sc = bpy.data.scenes.new(name)
    sc.render.fps = FPS
    return sc


def short(ep):
    return f"Ep{ep.data.get('number', 0):02d}"


def room_scene_name(ep, key):
    return f"{short(ep)} · {ROOMS[key].INFO['label']}" if key in ROOMS else f"{short(ep)} · Exterior"


# ------------------------------------------------------------------ droids
def _stand_in(sc, key):
    """Placeholder until the cast is locked: a capsule in the droid's colour, facing -Y."""
    c = E.CAST[key]
    name = f"Stand-in {c['name']}"
    ob = bpy.data.objects.get(name)
    if ob is None or ob.name not in sc.objects:
        me = bpy.data.meshes.new(name)
        import bmesh
        bm = bmesh.new()
        h = 0.9 if key != "DRONE" else 0.35
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.24, radius2=0.2, depth=h)
        for v in bm.verts:
            v.co.z += h / 2
        bmesh.ops.create_cube(bm, size=0.16, matrix=__import__("mathutils").Matrix.Translation((0, -0.2, h * 0.8)))
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        mat = bpy.data.materials.new(f"SB {name}")
        mat.diffuse_color = (*c["color"], 1)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*c["color"], 1)
        me.materials.append(mat)
        col = bpy.data.collections.get(f"{sc.name} Cast") or bpy.data.collections.new(f"{sc.name} Cast")
        if col.name not in sc.collection.children:
            sc.collection.children.link(col)
        col.objects.link(ob)
    ob["sb_cast"] = key
    ob["sb_droid"] = key
    if key == "DRONE":
        ob["sb_hover"] = 0.9
    return ob


def cast_object(sc, key, prefs=None):
    """The droid for a cast key in this scene: the Droid Kit rig when the kit has
    it, a stand-in otherwise."""
    for o in sc.objects:
        if o.get("sb_cast") == key:
            return o
    try:
        from . import catalog as Cat
        name = E.CAST[key]["name"].replace("-", "").lower()
        ds = [d for d in Cat.droids(prefs) if name in d["name"].replace("-", "").lower() or d["id"].lower() == key.lower()]
    except Exception:
        ds = []
    if ds and os.path.isfile(ds[0]["blend"]):
        d = ds[0]
        with bpy.data.libraries.load(d["blend"], link=False) as (src, dst):
            dst.objects = list(src.objects)
        objs = [o for o in dst.objects if o is not None]
        rig = next((o for o in objs if o.name.split(".")[0] == d["rig"]), None) or next((o for o in objs if o.type == "ARMATURE"), None)
        if rig is not None:
            fam = {rig} | set(rig.children_recursive)
            col = bpy.data.collections.new(f"Droid {d['name']}")
            sc.collection.children.link(col)
            for o in objs:
                if o in fam:
                    col.objects.link(o)
                    o["sb_droid"] = d["id"]
                else:
                    bpy.data.objects.remove(o)
            rig["sb_cast"] = key
            return rig
    return _stand_in(sc, key)


NOD_BONES = ("chest", "spine", "torso", "neck", "head")


def _nod(ob, fr, strength):
    """A beat on a stressed word: the upper body nods a few degrees and settles.
    Only bones move; the droid's feet and base stay where they stand (a whole
    droid dipping would push it into the floor). Stand-ins have no upper body,
    so they keep still."""
    if ob.type != "ARMATURE" or ob.pose is None:
        return
    pb = next((b for key in NOD_BONES for b in ob.pose.bones if key in b.name.lower()), None)
    if pb is None:
        return
    pb.rotation_mode = "XYZ"
    x0 = pb.rotation_euler.x
    pb.keyframe_insert("rotation_euler", index=0, frame=fr - 2)
    pb.rotation_euler.x = x0 + math.radians(4.0) * strength
    pb.keyframe_insert("rotation_euler", index=0, frame=fr + 1)
    pb.rotation_euler.x = x0
    pb.keyframe_insert("rotation_euler", index=0, frame=fr + 5)


# ------------------------------------------------------------------ marks
def marks(info, n, seed=1):
    """n floor marks in the room's open floor, spread across the middle third,
    clear of the furniture (pathing grid), in a gentle arc facing the camera side."""
    r = info["rooms"][0]
    grid = PA.Grid.from_scene(bpy.context.scene, radius=0.35, step_max=0.012, head=2.4, walkable=())
    out = []
    span = min(r["W"] * 0.5, 0.9 * max(1, n))
    for k in range(n):
        t = 0.5 if n == 1 else k / (n - 1)
        x = r["x"] - span / 2 + span * t
        y = r["y"] + r["D"] * 0.42 - 0.25 * math.sin(math.pi * t)
        near = grid.nearest_free((x, y), reach=25)
        p = grid.xy(*near) if near else Vector((x, y, 0))
        out.append(Vector((p.x, p.y, 0.0)))
    marks.grid = grid
    return out


def _floor_z(sc, p, ignore):
    """Height of whatever a droid would stand on at p (deck, walkway tile, pad)."""
    dg = bpy.context.evaluated_depsgraph_get()
    o = Vector((p.x, p.y, 1.2))
    for _ in range(8):
        hit, loc, nrm, _i, ob, _m = sc.ray_cast(dg, o, Vector((0, 0, -1)), distance=2.0)
        if not hit:
            return 0.0
        if ob in ignore or ob.get("sb_decal") or nrm.z < 0.7:
            o = loc - Vector((0, 0, 0.001))
            continue
        return loc.z + 0.0005
    return 0.0


def _flat_spot(sc, p, ignore, others, grid, r=0.3):
    """A mark where the floor under the whole footprint is level (no tile edge or
    floor light under one side), searched outwards from p. -> (point, floor z)."""
    ring = [Vector((math.cos(a) * r, math.sin(a) * r, 0)) for a in [k * math.pi / 4 for k in range(8)]] + [Vector()]
    for step in range(0, 13):
        for sgn in ((1, -1) if step else (1,)):
            for dy in (0.0, -0.3, 0.3):
                q = Vector((p.x + sgn * step * 0.12, p.y + dy, 0.0))
                if any((q - o).to_2d().length < 0.75 for o in others) or grid.blocked(*grid.ij(q)):
                    continue
                zs = [_floor_z(sc, q + d, ignore) for d in ring]
                if max(zs) - min(zs) < 0.003:
                    return q, max(zs)
    return p, max(_floor_z(sc, p + d, ignore) for d in ring)


def _face(ob, target):
    d = (Vector(target) - ob.location).to_2d()
    if d.length > 1e-4:
        ob.rotation_euler.z = math.atan2(-d.x, d.y) + math.pi  # droids face -Y at yaw 0


# ------------------------------------------------------------------ cameras for shots
def _cam(sc, name, loc, target, lens):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, cd)
    if ob.name not in sc.objects:
        col = bpy.data.collections.get(f"{sc.name} Shots") or bpy.data.collections.new(f"{sc.name} Shots")
        if col.name not in sc.collection.children:
            sc.collection.children.link(col)
        col.objects.link(ob)
    ob.location = Vector(loc)
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start = 0.05
    ob["sb_shot_cam"] = 1
    return ob


def _height(ob):
    return max(0.35, ob.dimensions.z if ob.type == "MESH" else 1.2) + (ob.get("sb_hover", 0.0) or 0.0)


def shot_camera(sc, shot, people, line_axis):
    """Camera for one shot. Every camera stays on the audience side (-Y) of the
    line between the two droids talking, so the 180° rule holds."""
    name = f"Cam {shot['id']}"
    ids = list(people)
    pos = [people[k].location.copy() for k in ids]
    mid = sum(pos, Vector()) / max(1, len(pos)) if pos else Vector((0, 2.5, 0))
    side = Vector((0, -1, 0))
    if line_axis is not None:
        n = Vector((-line_axis.y, line_axis.x, 0)).normalized()
        side = n if n.y < 0 else -n
    subj = people.get(shot.get("subject")) if shot.get("subject") else None
    kind = shot["kind"]
    if kind in ("master",) or not pos:
        return None   # the room's own wide master
    if kind == "two" or (kind == "master" and len(pos) == 2):
        h = max(_height(people[k]) for k in ids)
        return _cam(sc, name, mid + side * 3.4 + Vector((0, 0, h * 0.85)), mid + Vector((0, 0, h * 0.6)), 32)
    if subj is None:
        subj = people[ids[0]]
    h = _height(subj)
    head = subj.location + Vector((0, 0, h * 0.78))
    other = [people[k].location for k in ids if people[k] is not subj]
    lean = ((other[0] - subj.location).normalized() * 0.5) if other else Vector()
    if kind == "single":
        return _cam(sc, name, head + side * 2.1 + lean + Vector((0, 0, 0.05)), head, 50)
    if kind == "reaction":
        return _cam(sc, name, head + side * 1.6 + lean * 0.6, head, 70)
    if kind == "insert":
        hands = subj.location + Vector((0, 0, h * 0.5))
        return _cam(sc, name, hands + side * 1.1 + Vector((0.3, 0, 0.35)), hands, 70)
    return None


# ------------------------------------------------------------------ build
def build(ep, prefs=None):
    """Make (or refresh) every room scene, droid mark, shot camera and the edit."""
    F.retime(ep) if not ep.data.get("timing") else None
    if not ep.data.get("shots"):
        F.coverage(ep)
    scenes = ep.data["parsed"]["scenes"]
    lines = ep.data["parsed"]["lines"]
    timing = {t["line_no"]: t for t in ep.data["timing"]}
    total_f = sec2f(ep.data.get("length_s", 10)) + FPS
    made = {}
    report = {"rooms": [], "cams": 0, "warnings": []}
    for si, scn in enumerate(scenes):
        key = scn["room"] if scn["room"] in ROOMS else None
        sname = room_scene_name(ep, key) if key else f"{short(ep)} · Exterior"
        sc = _scene(sname)
        sc.frame_start, sc.frame_end = 1, total_f
        with bpy.context.temp_override(scene=sc):
            if key and not sc.get("sb_ship"):
                Li.render_setup(sc)
                Li.space_world()
                S.build([key])
                report["rooms"].append(key)
            elif not key and not sc.world:
                Li.render_setup(sc)
                Li.space_world()
            made[si] = sc
            if not key:
                continue
            info = json.loads(sc["sb_ship"])
            who = []
            for i in scn["lines"]:
                k = lines[i].get("who")
                if k and k not in who and E.CAST.get(k, {}).get("body", True):
                    who.append(k)
            people = {k: cast_object(sc, k, prefs) for k in who}
            pts = marks(info, len(who), seed=si)
            f0 = sec2f(min((timing[lines[i]["line_no"]]["start"] for i in scn["lines"]), default=0))
            ignore = set()
            for o in people.values():
                ignore |= {o} | set(o.children_recursive)
            for k, p in zip(who, pts):
                ob = people[k]
                p, z = _flat_spot(sc, p, ignore, [q for q in pts if q is not p], marks.grid)
                ob.location = p + Vector((0, 0, z + (ob.get("sb_hover", 0.0) or 0.0)))
                ob.keyframe_insert("location", frame=f0)
            for k in who:   # face the room centre between the others
                others = [people[o].location for o in who if o != k]
                tgt = sum(others, Vector()) / len(others) if others else people[k].location + Vector((0, -1, 0))
                _face(people[k], tgt)
                people[k].keyframe_insert("rotation_euler", frame=f0)
            axis = (people[who[1]].location - people[who[0]].location) if len(who) >= 2 else None
            for shot in [s for s in ep.data["shots"] if s["scene"] == si]:
                if shot.get("subject") and shot["subject"] not in people and who:
                    # the ship computer has no body: cover its lines on whoever listens
                    shot["kind"], shot["subject"], shot["preset"] = "reaction", who[0], F.SITCOM_PACK["reaction"]
                cam = shot_camera(sc, shot, people, axis)
                if cam is None:
                    cam = next((o for o in sc.objects if o.type == "CAMERA" and o.get("sb_cam") == "Wide master"), sc.camera)
                shot["scene_name"], shot["camera"] = sc.name, cam.name if cam else None
                if cam is not None and len(who) >= 2:
                    a, b = people[who[0]].location, people[who[1]].location
                    ab = (b - a).to_2d()
                    ac = (cam.location - a).to_2d()
                    side = ab.x * ac.y - ab.y * ac.x
                    aud = ab.x * (-1.0)   # where the audience-side point (0,-1) falls
                    if side * aud < 0 and shot["kind"] != "exterior":
                        report["warnings"].append(f"{shot['id']}: camera crosses the 180° line")
                report["cams"] += 1
    for shot in ep.data["shots"]:
        if shot["kind"] == "exterior":
            ext = made.get(shot["scene"]) or _scene(f"{short(ep)} · Exterior")
            shot["scene_name"] = ext.name
            with bpy.context.temp_override(scene=ext):
                cam = _cam(ext, f"Cam {shot['id']}", (0, -12, 2), (0, 40, 6), 35)
            shot["camera"] = cam.name
            _hero_shot(ext, shot)
    edit(ep)
    ep.data["blocking_warnings"] = report["warnings"]
    ep.set_station("stage", "done" if not report["warnings"] else "doing")
    return report


def _hero_shot(sc, shot):
    """Exterior cutaway: the Hero Ship add-on's preset when it's installed, else just the stars."""
    import sys
    hs = next((m for n, m in sys.modules.items() if n.split(".")[-1] == "hero_ship" and hasattr(m, "build")), None)
    if hs is None:
        return False
    try:
        pres = __import__(hs.__name__ + ".presets", fromlist=["apply"])
        with bpy.context.temp_override(scene=sc):
            root = bpy.data.objects.get("Hero Ship") or hs.build()
            pres.apply(root, shot["preset"].replace("Hero ship ", "").lower(), frame_start=sec2f(shot["start"]))
        return True
    except Exception as e:
        print("hero ship cutaway:", e)
        return False


def edit(ep):
    """The edit scene: one scene strip per shot with its camera, voices underneath."""
    ed = _scene(EDIT.format(ep=short(ep)))
    ed.frame_start, ed.frame_end = 1, sec2f(ep.data.get("length_s", 10)) + FPS
    se = ed.sequence_editor or ed.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences
    for st in [s for s in strips if s.get("sb_shot")]:
        strips.remove(st)
    for shot in ep.data.get("shots", []):
        src = bpy.data.scenes.get(shot.get("scene_name") or "")
        if src is None:
            continue
        f0, f1 = sec2f(shot["start"]), max(sec2f(shot["end"]), sec2f(shot["start"]) + 1)
        st = strips.new_scene(shot["id"], src, 1, f0)
        st.frame_offset_start = f0 - 1
        st.frame_final_end = f1
        st.frame_final_start = f0
        if shot.get("camera") and bpy.data.objects.get(shot["camera"]):
            st.scene_camera = bpy.data.objects[shot["camera"]]
        st["sb_shot"] = shot["id"]
    voices_to_edit(ep)
    return ed


def voices_to_edit(ep):
    ed = bpy.data.scenes.get(EDIT.format(ep=short(ep)))
    if ed is None:
        return 0
    se = ed.sequence_editor or ed.sequence_editor_create()
    strips = se.strips if hasattr(se, "strips") else se.sequences
    for st in [s for s in strips if s.get("sb_voice")]:
        strips.remove(st)
    n = 0
    vo = ep.data.get("voices", {})
    for t in ep.data.get("timing", []):
        v = vo.get(str(t["line_no"]))
        if not v:
            continue
        wav = v["takes"][v["pick"]].get("wav")
        if wav and os.path.isfile(wav):
            st = strips.new_sound(f"L{t['line_no']}", wav, 3 + (n % 2), sec2f(t["start"]))
            st["sb_voice"] = t["line_no"]
            n += 1
    return n


# ------------------------------------------------------------------ P1 acting
def _led_targets(ob):
    out = []
    for o in [ob] + list(ob.children_recursive):
        for slot in getattr(o, "material_slots", []):
            m = slot.material
            if m and m.use_nodes and any(w in m.name.lower() for w in ("led", "visor", "eye", "screen", "lamp")):
                em = next((n for n in m.node_tree.nodes if n.type == "EMISSION" or n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
                if em is not None:
                    out.append((m, em))
    return out


def apply_acting(ep):
    """Every layer that is switched on is keyed onto an NLA track named 'Auto acting'
    under the droid's own action, so your keys always win."""
    layers = F.acting_layers(ep)
    lines = {l["line_no"]: l for l in ep.data["parsed"]["lines"]}
    vo = ep.data.get("voices", {})
    done = 0
    for sc in [s for s in bpy.data.scenes if s.name.startswith(short(ep) + " · ") and s.get("sb_ship")]:
        cast = {o["sb_cast"]: o for o in sc.objects if o.get("sb_cast")}
        for t in ep.data.get("timing", []):
            ln = lines.get(t["line_no"])
            if not ln or ln["kind"] != "dialogue" or ln["who"] not in cast:
                continue
            spk = cast[ln["who"]]
            f0, f1 = sec2f(t["start"]), sec2f(t["end"])
            look = layers["look"]
            if look["on"]:
                for k, o in cast.items():
                    if o is spk:
                        continue
                    d = (spk.location - o.location).to_2d()
                    yaw = math.atan2(-d.x, d.y) + math.pi
                    cur = o.rotation_euler.z
                    o.rotation_euler.z = cur + (math.remainder(yaw - cur, math.tau)) * look["strength"]
                    o.keyframe_insert("rotation_euler", index=2, frame=f0 + 3)
            v = vo.get(str(t["line_no"]))
            ls = v["takes"][v["pick"]].get("lipsync") if v else None
            if layers["led"]["on"] and ls:
                for m, node in _led_targets(spk):
                    inp = node.inputs.get("Strength") or node.inputs.get("Emission Strength")
                    if inp is None:
                        continue
                    base = inp.default_value or 1.0
                    for k, lvl in enumerate(ls.get("level", [])[:: max(1, ls.get("fps", FPS) // 12)]):
                        inp.default_value = base * (0.3 + 1.4 * lvl * layers["led"]["strength"])
                        inp.keyframe_insert("default_value", frame=f0 + k * 2)
                    inp.default_value = base
                    inp.keyframe_insert("default_value", frame=f1 + 2)
            if layers["gestures"]["on"] and ls:
                for a in ls.get("accents", [])[:6]:
                    fr = f0 + int(a * FPS / max(1, ls.get("fps", FPS)))
                    _nod(spk, fr, layers["gestures"]["strength"])
            emo = F.line_emotion(ep, ln)
            spk["sb_emotion"] = emo
            spk["sb_pose_set"] = F.emotion_look(emo)["pose_set"]
            done += 1
        if layers["idle"]["on"]:
            for o in cast.values():
                ad = o.animation_data
                if ad and ad.action:
                    for fc in ad.action.fcurves if hasattr(ad.action, "fcurves") else []:
                        if fc.data_path == "rotation_euler" and fc.array_index == 2 and not any(m.type == "NOISE" for m in fc.modifiers):
                            nz = fc.modifiers.new("NOISE")
                            nz.scale, nz.strength = 48, 0.04 * layers["idle"]["strength"]
        if layers["contact"]["on"]:
            try:
                import sys
                foley = next(m for n, m in sys.modules.items() if n.split(".")[-1] == "ship_foley" and hasattr(m, "bake_scene"))
                foley.bake_scene(sc)
            except StopIteration:
                pass
            except Exception as e:
                print("contact sounds:", e)
    ep.set_station("perform", "doing")
    return done


# ------------------------------------------------------------------ P5 events
def apply_events(ep):
    n = 0
    for sc in [s for s in bpy.data.scenes if s.name.startswith(short(ep) + " · ") and s.get("sb_ship")]:
        lights = [o for o in sc.objects if o.type == "LIGHT"]
        cams = [o for o in sc.objects if o.type == "CAMERA"]
        for ev in ep.data.get("events", []):
            f0, f1 = sec2f(ev["start"]), sec2f(ev["end"])
            if ev["kind"] in ("red_alert", "lights_out"):
                for L in lights:
                    col, en = tuple(L.data.color), L.data.energy
                    L.data.keyframe_insert("color", frame=f0 - 1)
                    L.data.keyframe_insert("energy", frame=f0 - 1)
                    if ev["kind"] == "red_alert":
                        L.data.color = (1.0, 0.1, 0.06)
                    else:
                        L.data.energy = en * (0.05 if L.get("sb_role") != "emergency" else 3.0)
                    L.data.keyframe_insert("color", frame=f0 + 2)
                    L.data.keyframe_insert("energy", frame=f0 + 2)
                    L.data.keyframe_insert("color", frame=f1 - 2)
                    L.data.keyframe_insert("energy", frame=f1 - 2)
                    L.data.color, L.data.energy = col, en
                    L.data.keyframe_insert("color", frame=f1 + 4)
                    L.data.keyframe_insert("energy", frame=f1 + 4)
            if ev["kind"] in ("shake", "meteors", "jump"):
                rng = random.Random(f0)
                for c in cams:
                    r0 = c.rotation_euler.copy()
                    c.keyframe_insert("rotation_euler", frame=f0 - 1)
                    for f in range(f0, f1, 2):
                        k = 1.0 - (f - f0) / max(1, f1 - f0)
                        c.rotation_euler = (r0.x + rng.uniform(-1, 1) * 0.012 * k, r0.y, r0.z + rng.uniform(-1, 1) * 0.012 * k)
                        c.keyframe_insert("rotation_euler", frame=f)
                    c.rotation_euler = r0
                    c.keyframe_insert("rotation_euler", frame=f1)
            if ev["kind"] == "jump":
                try:
                    from . import views as V
                    V.set_view("hyperspace", sc, frame=f0)
                    V.set_view(sc.get("sb_view", "deep_space"), sc, frame=f1)
                except Exception as e:
                    print("jump view:", e)
            n += 1
    return n


# ------------------------------------------------------------------ R1 R2
def run_check(ep, step=6):
    """Scene checks per shot. Returns {chip: [(shot_id, note)]}; never blocks."""
    from . import collide, feet as Ft
    res = {"intersect": [], "feet": [], "frame": [], "props": []}
    from bpy_extras.object_utils import world_to_camera_view
    for shot in ep.data.get("shots", []):
        sc = bpy.data.scenes.get(shot.get("scene_name") or "")
        if sc is None or not sc.get("sb_ship"):
            continue
        f0, f1 = sec2f(shot["start"]), sec2f(shot["end"])
        frames = list(range(f0, f1 + 1, step))
        hits = collide.audit_scene(sc, frames)
        for f, pairs in hits.items():
            if pairs:
                res["intersect"].append((shot["id"], f"frame {f}: {pairs[0][0]} touches {pairs[0][1]}"))
                break
        for rig in [o for o in sc.objects if o.type == "ARMATURE" and o.get("sb_cast")]:
            try:
                rep = Ft.audit(rig, sc, (f0, f1), step=step)
                if rep.get("bad_frames"):
                    res["feet"].append((shot["id"], f"{rig.name}: {rep['bad_frames']} frames off the floor"))
            except Exception:
                pass
        cam = bpy.data.objects.get(shot.get("camera") or "")
        subj = next((o for o in sc.objects if o.get("sb_cast") == shot.get("subject")), None)
        if cam and subj:
            sc.frame_set((f0 + f1) // 2)
            pts = [world_to_camera_view(sc, cam, subj.matrix_world @ Vector(c)) for c in subj.bound_box]
            if any(p.x < 0.02 or p.x > 0.98 or p.y > 0.98 for p in pts) and shot["kind"] in ("single", "two"):
                res["frame"].append((shot["id"], f"{E.CAST[shot['subject']]['name']} cut by the frame edge"))
        for o in sc.objects:
            for c in getattr(o, "constraints", []):
                if c.type == "CHILD_OF" and c.target is None:
                    res["props"].append((shot["id"], f"{o.name} lost its hand"))
    return res


def still_frames(ep):
    return {s["id"]: (s.get("scene_name"), s.get("camera"), (sec2f(s["start"]) + sec2f(s["end"])) // 2) for s in ep.data.get("shots", [])}


def render_still(ep, shot_id, path, res=(960, 540), samples=24):
    s = next(x for x in ep.data["shots"] if x["id"] == shot_id)
    sc = bpy.data.scenes.get(s.get("scene_name") or "")
    cam = bpy.data.objects.get(s.get("camera") or "")
    if sc is None:
        return None
    sc.camera = cam or sc.camera
    sc.frame_set((sec2f(s["start"]) + sec2f(s["end"])) // 2)
    r = sc.render
    keep = (r.resolution_x, r.resolution_y, r.filepath, r.resolution_percentage)
    r.resolution_x, r.resolution_y, r.resolution_percentage = res[0], res[1], 100
    if r.engine == "CYCLES":
        sc.cycles.samples = samples
    r.filepath = path
    with bpy.context.temp_override(scene=sc):
        bpy.ops.render.render(write_still=True, scene=sc.name)
    r.resolution_x, r.resolution_y, r.filepath, r.resolution_percentage = keep
    return path
