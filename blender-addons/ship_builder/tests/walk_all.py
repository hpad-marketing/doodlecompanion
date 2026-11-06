"""python3 walk_all.py -- <out dir> [layout ...]: the walk + foot test on every set.

For each layout: build it, drop a droid in the first room, walk it through every room
and door (recording, as walk mode does), then report:
  feet       worst sink / float per foot over every planted frame (limits 0.5 mm / 2 mm)
  collisions droid parts vs the set, sampled every 6 ticks (0 allowed)
  doors      every door on the route opened and closed again
Default droid is the test biped; pass --rig <blend> <rig name> to use a real droid (on Sushi).
"""
import json, os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
OUT = a[0]
rig_blend = rig_name = None
if '--rig' in a:
    i = a.index('--rig'); rig_blend, rig_name = a[i + 1], a[i + 2]; a = a[:i] + a[i + 3:]
from ship_builder import ship as S, walk as Wk, feet as Ft, collide
layouts = a[1:] or list(S.LAYOUTS)
os.makedirs(OUT, exist_ok=True)
report = {}


def droid(sc):
    if rig_blend:
        with bpy.data.libraries.load(os.path.abspath(rig_blend), link=False) as (src, dst):
            dst.objects = [n for n in src.objects]
            dst.actions = list(src.actions)
        objs = [o for o in dst.objects if o is not None]
        rig = next(o for o in objs if o.name == rig_name)
        for o in [rig] + list(rig.children_recursive):
            if o.name not in sc.collection.objects:
                sc.collection.objects.link(o)
            o["sb_droid"] = 1
        return rig
    from test_biped import make_biped
    return make_biped(sc)


def route(info):
    rs, pts = info["rooms"], []
    by_room = {}
    for d in info["doors"]:
        by_room.setdefault(d["room"], []).append(d)
    for i, r in enumerate(rs):
        pts.append(("centre " + r["key"], Vector((r["x"] + (0.3 if r["key"] == "lounge" else 0), r["y"] + r["D"] * 0.5, 0))))
        if i < len(rs) - 1:
            d = next(d for d in by_room[r["name"]] if d["side"] == "right")
            pts.append(("door " + d["id"], Vector((d["x"] - 0.9, d["yc"], 0))))
            pts.append(("through " + d["id"], Vector((d["x"] + 1.1, d["yc"], 0))))
    return pts


for lay in layouts:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.frame_start = 1
    t0 = time.time()
    info = S.build(lay)
    rig = droid(sc)
    fam = [rig] + list(rig.children_recursive)
    names = {o.name for o in fam}  # droid self-collision is the Droid Kit's collision_check; here: droid vs set
    r0 = info["rooms"][0]
    rig.location = (r0["x"] - r0["W"] * 0.25, r0["y"] + r0["D"] * 0.3, 0)
    bpy.context.view_layer.update()
    w = Wk.Walker(sc, rig)
    pts = route(info)
    w.record(True)
    dt, t, wp, stall, hits, reached, opened = 1 / 24, 0.0, 0, 0.0, [], [], {}
    best = 1e9
    while wp < len(pts) and t < 120:
        name, goal = pts[wp]
        d = goal - w.pos
        d.z = 0
        if d.length < 0.35 or stall > 6:
            reached.append((name, d.length < 0.35))
            wp, stall, best = wp + 1, 0.0, 1e9
            continue
        if d.length < best - 0.05:
            best, stall = d.length, 0.0
        else:
            stall += dt
        right, fwd = w._view_axes()
        dn = d.normalized()
        w.tick(dt, Wk.Input(dn.dot(right), dn.dot(fwd)))
        t += dt
        for dd in w.world.doors:
            opened[dd["id"]] = max(opened.get(dd["id"], 0), dd["ctl"]["open"])
        if int(t / dt) % 6 == 0:
            bpy.context.view_layer.update()
            h = [x for x in collide.audit_objects(list(sc.objects), only=fam) if not (x[0] in names and x[1] in names)]
            if h:
                hits.append((round(t, 2), h[:3]))
    for _ in range(48):
        w.tick(dt, Wk.Input())
    w.record(False)
    f1 = w._frame()
    feet = Ft.audit(rig, sc, (1, f1))
    closed = {d["id"]: round(d["ctl"]["open"], 2) for d in w.world.doors}
    rep = dict(layout=lay, seconds=round(time.time() - t0, 1), walked_s=round(t, 1), frames=f1,
               reached=reached, all_reached=all(ok for _, ok in reached),
               feet=feet["feet"], foot_bad_frames=feet["bad_frames"], foot_bad=feet["bad"][:12],
               collision_samples_with_hits=len(hits), hits=hits[:6],
               doors_opened={k: round(v, 2) for k, v in opened.items() if v > 0.01}, doors_now=closed)
    rep["pass"] = rep["all_reached"] and rep["foot_bad_frames"] == 0 and not hits and all(v < 0.05 for v in closed.values())
    report[lay] = rep
    print("WALK", lay, "PASS" if rep["pass"] else "FAIL", json.dumps({k: rep[k] for k in ("frames", "all_reached", "foot_bad_frames", "collision_samples_with_hits")}), flush=True)
    if not rep["pass"]:
        print(json.dumps(rep, indent=1)[:3000], flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"walk_{lay}.blend"))
    json.dump(report, open(os.path.join(OUT, "walk_report.json"), "w"), indent=1)
