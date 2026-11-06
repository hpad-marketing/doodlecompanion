"""Feet on the floor: no sinking, no floating, on every surface of every set.

Planter  - per frame, drops a ray from each sole point to the walkable ground
           (deck, plates, grating, steps, ramps, rugs, sills) and moves the IK
           foot so the lowest sole point rests exactly on it. A planted foot also
           tilts to the surface. A swinging foot is only ever lifted clear.
audit    - the foot test: over a frame range, every frame a foot is planted
           (not moving), every sole point (heel, ball, toe ...) must sit between
           SINK below and FLOAT above the surface under it. Reports the worst
           sink and float per foot, with frame and floor position.

Droid parts follow the Droid Kit contract: rigid part objects carry
ob["rig_bone"]; feet are the parts whose names match FOOT_RX for each side,
and IK controls are IK_foot.L / IK_foot.R (overridable per droid).
"""
import math
import re

import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

SINK = 0.0005       # 0.5 mm into the floor at most (the Droid Kit touch tolerance)
FLOAT = 0.002       # 2 mm above the floor at most, while planted
STILL = 0.002       # a foot moving less than this per frame (m) is planted
SOLE = 0.012        # sole points: vertices within 12 mm of the foot's lowest point
CLEAR = 0.03        # a swinging foot clears edges by 3 cm
FOOT_RX = r"(foot|toe|heel|sole|ankle)[^.]*\.{s}$"

# Called once each time a foot lands (walk mode and Planter runs), for footstep sounds:
#   cb(rig, side, point, normal, speed, surface_object)
# speed is the foot's speed just before contact in m/s; surface_object is what it landed on.
ON_PLANT = []


class Ground:
    """Walkable surfaces as one BVH. Faces of loose clutter (bolts, rags, scraps) are
    remembered: a foot may pass over them but never be planted on them."""

    def __init__(self, bvh, clutter, owners=()):
        self.bvh, self.clutter = bvh, clutter
        self.owners = list(owners)  # [(first poly index, object name)] in order

    def owner(self, idx):
        """The object a ground face belongs to (for footstep sounds and debugging)."""
        import bisect
        i = bisect.bisect_right([o[0] for o in self.owners], idx) - 1
        return bpy.data.objects.get(self.owners[i][1]) if i >= 0 else None


def ground_bvh(scene, ignore=()):
    """Walkable surfaces: upward faces of everything low enough to stand on, droids and haze excluded."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys, clutter, owners = [], [], set(), []
    for ob in scene.objects:
        if ob in ignore or ob.type not in {"MESH", "CURVE", "FONT"} or ob.hide_render:
            continue
        if ob.get("sb_haze") or ob.get("sb_fourth_wall") or ob.get("sb_droid") or ob.get("rig_bone") or ob.get("sb_ghost"):
            continue
        if ob.name.startswith(("Planet", "SB Planet", "Fourth Wall")):
            continue
        ev = ob.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        if me is None or not me.polygons:
            ev.to_mesh_clear()
            continue
        mw = ob.matrix_world
        vs = [mw @ v.co for v in me.vertices]
        if min(v.z for v in vs) > 0.6:  # nothing up high is floor
            ev.to_mesh_clear()
            continue
        b, pb = len(verts), len(polys)
        verts.extend(vs)
        polys.extend(tuple(b + i for i in p.vertices) for p in me.polygons)
        owners.append((pb, ob.name))
        if ob.get("sb_wear") == "debris":
            clutter.update(range(pb, len(polys)))
        ev.to_mesh_clear()
    return Ground(BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None, clutter, owners)


def surface(ground, p, above=0.25, below=0.6, clutter=None):
    """(height, normal) of the walkable surface under point p, or (None, None).
    Pass a list as clutter to learn whether the hit was loose debris."""
    if ground is None or ground.bvh is None:
        return 0.0, Vector((0, 0, 1))
    o = Vector((p.x, p.y, p.z + above))
    loc, nrm, idx, _d = ground.bvh.ray_cast(o, Vector((0, 0, -1)), above + below)
    if loc is None:
        return None, None
    if clutter is not None and idx in ground.clutter:
        clutter.append(idx)
    if nrm.z < 0:
        nrm = -nrm
    return loc.z, nrm


class Foot:
    def __init__(self, rig, side, ik=None, parts_rx=None):
        self.rig, self.side = rig, side
        self.ik = rig.pose.bones.get(ik or f"IK_foot.{side}")
        rx = re.compile(parts_rx or FOOT_RX.format(s=side))
        self.parts = [o for o in rig.children_recursive if o.type == "MESH" and "rig_bone" in o and rx.search(o.name)]
        if not self.parts:  # fall back: meshes on the foot bones
            names = {b.name for b in rig.pose.bones if re.search(rf"(foot|toe|heel)[^.]*\.{side}$", b.name, re.I)}
            self.parts = [o for o in rig.children_recursive if o.type == "MESH" and o.parent_bone in names]
        self._local = None
        self.prev = None

    def sole_points(self):
        """Sole sample points in world space (cached in each part's local space at first use)."""
        if self._local is None:
            dg = bpy.context.evaluated_depsgraph_get()
            pts = []
            for o in self.parts:
                ev = o.evaluated_get(dg)
                me = ev.to_mesh()
                pts.extend((o, v.co.copy(), (o.matrix_world @ v.co).z) for v in me.vertices)
                ev.to_mesh_clear()
            if not pts:
                self._local = []
                return []
            zmin = min(p[2] for p in pts)
            low = [(o, co) for o, co, z in pts if z < zmin + SOLE]
            # thin to an even spread: heel, ball, toe and the edges are what matter
            keep, seen = [], set()
            for o, co in low:
                w = o.matrix_world @ co
                key = (round(w.x / 0.01), round(w.y / 0.01))
                if key not in seen:
                    seen.add(key)
                    keep.append((o, co))
            self._local = keep
        return [o.matrix_world @ co for o, co in self._local]

    def errors(self, bvh):
        """[(point, height above surface)] for each sole point; None where there is no floor."""
        out = []
        for p in self.sole_points():
            h, _n = surface(bvh, p)
            out.append((p, None if h is None else p.z - h))
        return out


class Planter:
    """Keeps a rig's feet on the floor frame by frame (walk mode and recorded motions)."""

    def __init__(self, rig, scene, bvh=None, feet=None):
        self.rig, self.scene = rig, scene
        self.bvh = bvh or ground_bvh(scene, ignore=[rig] + list(rig.children_recursive))
        feet = feet or {s: {} for s in "LR"}
        self.feet = [Foot(rig, s, f.get("ik"), f.get("parts")) for s, f in feet.items()]
        self.feet = [f for f in self.feet if f.ik is not None and f.parts]

    def _nudge(self, foot, move, tilt=None):
        """Move the IK foot by a world-space vector, optionally tilting the sole to a surface normal."""
        pb = foot.ik
        M = pb.matrix.copy()
        inv = self.rig.matrix_world.inverted().to_3x3()
        M.translation += inv @ move
        if tilt is not None:
            q = Vector((0, 0, 1)).rotation_difference(tilt)
            R = (inv @ q.to_matrix()) @ self.rig.matrix_world.to_3x3()
            M = Matrix.Translation(M.translation) @ R.to_4x4() @ M.to_3x3().to_4x4()
        pb.matrix = M

    def _foothold(self, f, pts, travel):
        """Smallest slide along the walk direction that puts the whole sole on one level
        (so no heel or toe hangs over a step, rug or sill edge)."""
        def spread(off):
            junk = []
            hs = [surface(self.bvh, p + off, clutter=junk)[0] for p in pts]
            if any(h is None for h in hs) or junk:  # never plant on a bolt or a rag
                return 1.0
            return max(hs) - min(hs)
        if spread(Vector()) <= FLOAT:
            return Vector()
        d = Vector((travel.x, travel.y, 0))
        d = d.normalized() if d.length > 1e-6 else Vector((1, 0, 0))
        side = Vector((-d.y, d.x, 0))
        reach = max((a - b).length for a in pts for b in pts) + 0.03
        k = 0.01
        while k <= reach:
            for v in (d, -d, side, -side):  # forward first, then back, then to the sides
                off = v * k
                if spread(off) <= FLOAT:
                    return off
            k += 0.01
        return Vector()

    def plant(self, key=False, frame=None):
        """Correct both feet for the current frame. Returns {side: world move applied}."""
        bpy.context.view_layer.update()
        done = {}
        fwd = self.rig.matrix_world.to_3x3() @ Vector((0, -1, 0))  # droids face -Y
        fps = self.scene.render.fps / self.scene.render.fps_base
        for f in self.feet:
            landed = False
            pts = f.sole_points()
            if not pts:
                continue
            pos = sum(pts, Vector()) / len(pts)
            travel = (pos - f.prev) if f.prev is not None else fwd
            moving = f.prev is not None and travel.xy.length > STILL * 1.5  # looser than the audit, so it never misses a plant
            f.prev = pos.copy()
            errs = [e for e in f.errors(self.bvh) if e[1] is not None]
            if not errs:
                continue
            low = min(e for _, e in errs)
            planted = not moving and low < 0.02
            if planted:
                if not getattr(f, "planted", False):
                    f.hold = self._foothold(f, pts, f.last_travel if getattr(f, "last_travel", None) else fwd)
                    landed = True
                f.planted, f.fade = True, 0
                off = f.hold
            else:
                if getattr(f, "planted", False):
                    f.fade = 6  # ease the foothold slide out over the first frames of the swing
                f.planted = False
                f.last_travel = travel if travel.xy.length > 1e-5 else getattr(f, "last_travel", None)
                fade = getattr(f, "fade", 0)
                off = getattr(f, "hold", Vector()) * (fade / 6.0)
                f.fade = max(0, fade - 1)
            if off.length:
                pts = [p + off for p in pts]
            hs = [surface(self.bvh, p) for p in pts]
            es = [p.z - h for p, (h, _n) in zip(pts, hs) if h is not None]
            if not es:
                continue
            low = min(es)
            if planted:
                _h, n = surface(self.bvh, sum(pts, Vector()) / len(pts))
                tilt = n if n is not None and n.z < 0.9999 else None
                move = off + Vector((0, 0, -low + 0.0002))
                self._nudge(f, move, tilt)
                if landed and ON_PLANT:
                    c = sum(pts, Vector()) / len(pts)
                    hit = self.bvh.bvh.ray_cast(c + Vector((0, 0, 0.25)), Vector((0, 0, -1)), 0.6) if self.bvh.bvh else (None,) * 4
                    obj = self.bvh.owner(hit[2]) if hit[2] is not None else None
                    speed = getattr(f, "last_travel", Vector()).length * fps
                    for cb in list(ON_PLANT):
                        try:
                            cb(self.rig, f.side, c, n, speed, obj)
                        except Exception as e:  # a sound hook must never break walking
                            print("feet.ON_PLANT hook failed:", e)
            else:
                # swinging: clear whatever is just ahead (rug edge, sill, rag, step lip) by a few mm
                ahead = Vector((travel.x, travel.y, 0))
                lift = -low + 0.0002
                if ahead.length > 1e-5:
                    ahead.normalize()
                    lowest = min(p.z for p in pts)
                    for k in (0.02, 0.05, 0.09):
                        for p in pts:
                            h, _n = surface(self.bvh, p + ahead * k, above=0.3)
                            if h is not None:
                                lift = max(lift, h + 0.004 - lowest)
                if lift <= 0 and not off.length:
                    continue
                move = off + Vector((0, 0, max(0.0, lift)))
                self._nudge(f, move)
            done[f.side] = move
            if key:
                f.ik.keyframe_insert("location", frame=frame)
                rot = "rotation_quaternion" if f.ik.rotation_mode == "QUATERNION" else "rotation_euler"
                f.ik.keyframe_insert(rot, frame=frame)
        if done:
            bpy.context.view_layer.update()
        return done


def audit(rig, scene, frames, bvh=None, feet=None, step=1):
    """The foot test. Returns a report dict; ok is True only with 0 frames over the limits."""
    bvh = bvh or ground_bvh(scene, ignore=[rig] + list(rig.children_recursive))
    feet = [Foot(rig, s, (feet or {}).get(s, {}).get("ik"), (feet or {}).get(s, {}).get("parts")) for s in "LR"]
    feet = [f for f in feet if f.parts]
    rep = {"frames": 0, "feet": {}, "bad": []}
    for f in feet:
        rep["feet"][f.side] = {"planted_frames": 0, "worst_sink_mm": 0.0, "worst_float_mm": 0.0, "no_floor": 0}
    prev = {}
    for fr in range(frames[0], frames[1] + 1, step):
        scene.frame_set(fr)
        rep["frames"] += 1
        for f in feet:
            errs = f.errors(bvh)
            pts = [p for p, _ in errs]
            if not pts:
                continue
            c = sum(pts, Vector()) / len(pts)
            planted = f.side in prev and (c.xy - prev[f.side].xy).length <= STILL * step and \
                min((e for _, e in errs if e is not None), default=1) < 0.02
            prev[f.side] = c
            r = rep["feet"][f.side]
            for p, e in errs:
                if e is None:
                    if planted:
                        r["no_floor"] += 1
                    continue
                if e < -SINK:  # sinking is never allowed, planted or not
                    r["worst_sink_mm"] = max(r["worst_sink_mm"], round(-e * 1000, 2))
                    rep["bad"].append(dict(frame=fr, foot=f.side, kind="sink", mm=round(-e * 1000, 2), at=[round(v, 3) for v in p]))
            if planted:
                r["planted_frames"] += 1
                hi = max(e for _, e in errs if e is not None) if any(e is not None for _, e in errs) else 0
                # a planted foot: every sole point within FLOAT, so no corner hangs over a step edge
                if hi > FLOAT:
                    r["worst_float_mm"] = max(r["worst_float_mm"], round(hi * 1000, 2))
                    p = max(errs, key=lambda x: -1 if x[1] is None else x[1])[0]
                    rep["bad"].append(dict(frame=fr, foot=f.side, kind="float", mm=round(hi * 1000, 2), at=[round(v, 3) for v in p]))
    rep["bad_frames"] = len({(b["frame"], b["foot"]) for b in rep["bad"]})
    rep["bad"] = rep["bad"][:40]
    rep["ok"] = rep["bad_frames"] == 0
    return rep
