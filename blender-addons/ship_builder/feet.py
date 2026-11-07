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
GAP = 0.006         # seams up to 2 x this wide are bridged by the sole
SOLE = 0.012        # sole points: vertices within 12 mm of the foot's lowest point
CLEAR = 0.03        # a swinging foot clears edges by 3 cm
FOOT_RX = r"(foot|toe|heel|sole|ankle)[^.]*\.{s}$"

# Called once each time a foot lands (walk mode and Planter runs), for footstep sounds:
#   cb(rig, side, point, normal, speed, surface_object)
# speed is the foot's speed just before contact in m/s; surface_object is what it landed on.
ON_PLANT = []
# Heel and toe contacts, for a heel-then-toe footstep: cb(rig, side, part, point, normal, speed, surface_object)
# part is "heel" (or "flat") at strike, then "toe" when the front of the sole rolls down.
ON_CONTACT = []
DEBUG = bool(__import__('os').environ.get('SB_FEET_DEBUG'))
MIN_SWING = 4       # frames a lifted foot must swing before it may land again
FADE = 10           # frames over which a foothold slide eases out after push-off
STRETCH = 0.22      # a planted foot this far off its landing spot takes a catch-up step
FSTEP = 7           # frames of a catch-up step (lift, carry, set down)
STEP_ARC = 0.045    # its toe clearance at the top of the arc
MIN_STANCE = 5      # frames a landed foot stays down before it may lift again
OVERHANG = 0.012    # sole overhang past an edge that counts as hanging (bevels are smaller)
ROOM = 0.035        # clear floor kept ahead of a planted toe, for the roll
LAND = 0.03         # below this height a descending foot blends into its landing spot


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


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
        # sliding doors move: a leaf is never floor, open or shut (it would linger in the
        # ground as a phantom ledge once it slides away)
        if ob.get("sb_door") or (ob.parent is not None and ob.parent.get("sb_door")):
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
    # a sole bridges seams narrower than about a centimetre (tile joints, panel gaps):
    # take the highest of a small cross of rays so a seam doesn't read as a drop
    for dx, dy in ((GAP, 0), (-GAP, 0), (0, GAP), (0, -GAP)):
        l2, n2, i2, _ = ground.bvh.ray_cast(o + Vector((dx, dy, 0)), Vector((0, 0, -1)), above + below)
        if l2 is not None and (loc is None or l2.z > loc.z + 1e-5):
            hi_side = [ground.bvh.ray_cast(o + Vector((-dx, -dy, 0)), Vector((0, 0, -1)), above + below)[0]]
            if hi_side[0] is not None and hi_side[0].z > l2.z - 0.002:   # high on both sides: a seam, not an edge
                loc, nrm, idx = Vector((p.x, p.y, min(l2.z, hi_side[0].z))), n2, i2
    if loc is None:
        return None, None
    if clutter is not None and idx in ground.clutter:
        clutter.append(idx)
    if nrm.z < 0:
        nrm = -nrm
    return loc.z, nrm


def _hull(pts):
    """2D convex hull (monotone chain), counter-clockwise."""
    P = sorted({(round(p.x, 5), round(p.y, 5)) for p in pts})
    if len(P) < 3:
        return [Vector(p) for p in P]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(P):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return [Vector(p) for p in lo[:-1] + hi[:-1]]


def _inside(hull, x, y):
    n = len(hull)
    for i in range(n):
        a, b = hull[i], hull[(i + 1) % n]
        if (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x) < -1e-9:
            return False
    return True


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
            # read the sole off the rest pose (standing flat), whatever pose the rig is in now,
            # so a foot first seen mid-roll still gets its whole sole
            arm = self.rig.data
            keep = arm.pose_position
            arm.pose_position = "REST"
            bpy.context.view_layer.update()
            try:
                self._local = self._read_sole()
                self._rim = self._read_rim()
            finally:
                arm.pose_position = keep
                bpy.context.view_layer.update()
        return [o.matrix_world @ co for o, co in self._local]

    def rim_points(self):
        """The rest of the foot's underside (toe spring, heel curve, a front lip) in world space:
        it doesn't carry weight, but nothing on the floor may poke up into it."""
        if self._local is None:
            self.sole_points()
        return [o.matrix_world @ co for o, co in getattr(self, "_rim", [])]

    def _read_rim(self, rise=0.08):
        dg = bpy.context.evaluated_depsgraph_get()
        out, seen = [], set()
        allz = []
        for o in self.parts:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            allz.extend((o.matrix_world @ v.co) for v in me.vertices)
            ev.to_mesh_clear()
        if not allz:
            return out
        zmin = min(w.z for w in allz)
        for o in self.parts:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            mw = o.matrix_world
            ws = [mw @ v.co for v in me.vertices]
            tree = BVHTree.FromPolygons(ws, [tuple(f.vertices) for f in me.polygons])
            ev.to_mesh_clear()
            hull = _hull([w.xy for w in ws if w.z < zmin + rise])
            if len(hull) < 3:
                continue
            inv = mw.inverted()
            x0, x1 = min(v.x for v in hull), max(v.x for v in hull)
            y0, y1 = min(v.y for v in hull), max(v.y for v in hull)
            x = x0 + 0.005
            while x < x1:
                y = y0 + 0.005
                while y < y1:
                    if _inside(hull, x, y):
                        hit = tree.ray_cast(Vector((x, y, zmin - 0.05)), Vector((0, 0, 1)), 0.05 + rise)
                        if hit[0] is not None and hit[0].z >= zmin + SOLE:
                            key = (round(x / 0.02), round(y / 0.02))
                            if key not in seen:
                                seen.add(key)
                                out.append((o, inv @ hit[0]))
                    y += 0.02
                x += 0.02
        return out

    def _read_sole(self):
        if True:
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
            # a sole is mostly flat faces with few vertices, so a thin stripe or a scrap of
            # paper can sit between them: fill the sole outline with a 1 cm grid as well
            keep, seen = [], set()

            def add(o, co):
                w = o.matrix_world @ co
                key = (round(w.x / 0.01), round(w.y / 0.01))
                if key not in seen:
                    seen.add(key)
                    keep.append((o, co))
            for o, co in low:
                add(o, co)
            for o in {o for o, _ in low}:
                inv = o.matrix_world.inverted()
                ws = [o.matrix_world @ co for oo, co in low if oo is o]
                hull = _hull([w.xy for w in ws])
                if len(hull) < 3:
                    continue
                zs = min(w.z for w in ws)
                ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
                me = ev.to_mesh()
                mw = o.matrix_world
                tree = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(f.vertices) for f in me.polygons])
                ev.to_mesh_clear()
                x0, x1 = min(v.x for v in hull), max(v.x for v in hull)
                y0, y1 = min(v.y for v in hull), max(v.y for v in hull)
                x = x0 + 0.005
                while x < x1:
                    y = y0 + 0.005
                    while y < y1:
                        if _inside(hull, x, y):
                            hit = tree.ray_cast(Vector((x, y, zs - 0.05)), Vector((0, 0, 1)), 0.05 + SOLE)
                            if hit[0] is not None:   # the real underside of the sole here
                                add(o, inv @ hit[0])
                        y += 0.01
                    x += 0.01
            return keep

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
        d0 = Vector((travel.x, travel.y, 0))
        d0 = d0.normalized() if d0.length > 1e-6 else Vector((1, 0, 0))
        # room for the roll: the sole rotates over its toe at push-off, so the ground just
        # ahead of the toe must be no higher than the sole's own level
        front = max((p - sum(pts, Vector()) / len(pts)).dot(d0) for p in pts)
        c0 = sum(pts, Vector()) / len(pts)
        toes = [p for p in pts if (p - c0).dot(d0) > front - 0.02]
        rim = [r + (pts[0] - f.sole_points()[0]) for r in f.rim_points()] if f.rim_points() else []

        def spread(off):
            junk = []
            hs = [surface(self.bvh, p + off, clutter=junk)[0] for p in pts]
            if any(h is None for h in hs) or junk:  # never plant on a bolt or a rag
                return 1.0
            # ground just ahead of the toe may drop away (a step down is fine for the roll),
            # but it must never rise above the sole, or the toe rolls into it
            ahead = [surface(self.bvh, t + off + d0 * ROOM)[0] for t in toes]
            if any(h is not None and h > max(hs) + FLOAT for h in ahead):
                return 1.0
            # the raised parts of the underside (toe spring, heel curve) must clear the floor too:
            # a tile or plate edge must never end up inside the front of the foot
            base, top = min(p.z for p in pts), max(hs)
            for r in rim:
                h = surface(self.bvh, r + off)[0]
                if h is not None and h - top > (r.z - base) - 0.001:
                    return 1.0
            return max(hs) - min(hs)
        if spread(Vector()) <= FLOAT:
            return Vector()
        d = Vector((travel.x, travel.y, 0))
        d = d.normalized() if d.length > 1e-6 else Vector((1, 0, 0))
        side = Vector((-d.y, d.x, 0))
        reach = max((a - b).length for a in pts for b in pts) + 0.03
        def level(off):
            hs = [surface(self.bvh, p + off)[0] for p in pts]
            return max(h for h in hs if h is not None) if any(h is not None for h in hs) else 0.0
        here = min(p.z for p in pts)
        k = 0.01
        while k <= reach:
            ok = [v * k for v in (d, -d, side, -side) if spread(v * k) <= FLOAT]
            if ok:
                # of the equally short slides, keep the foot on the level it is reaching for
                # (stay on the step or ramp rather than slipping off its edge)
                return min(ok, key=lambda off: abs(level(off) - here))
            k += 0.01
        return Vector()

    def _contact(self, f, pts, fwd, landed, fps):
        """Fire heel (or flat) at strike, toe when the front of the sole comes down."""
        d = Vector((fwd.x, fwd.y, 0)).normalized()
        c = sum(pts, Vector()) / len(pts)
        along = [((p - c).dot(d), p) for p in pts]
        L = max(a for a, _ in along) - min(a for a, _ in along) or 1.0
        es = [(a, p, p.z - (surface(self.bvh, p)[0] or 0.0)) for a, p in along]
        down = [a for a, _p, e in es if e < 0.002]
        if not down:
            return
        if landed:
            part = "heel" if max(down) < 0.0 else ("toe" if min(down) > 0.0 else "flat")
            f.toe_down = part in ("flat", "toe")
            hit_p = min(es, key=lambda x: x[2])[1]
        elif max(down) > L * 0.25:
            part, f.toe_down = "toe", True
            hit_p = max(es, key=lambda x: x[0])[1]
        else:
            return
        h, n = surface(self.bvh, hit_p)
        hit = self.bvh.bvh.ray_cast(hit_p + Vector((0, 0, 0.25)), Vector((0, 0, -1)), 0.6) if self.bvh.bvh else (None,) * 4
        obj = self.bvh.owner(hit[2]) if hit[2] is not None else None
        speed = getattr(f, "last_travel", Vector()).length * fps
        for cb in list(ON_CONTACT):
            try:
                cb(self.rig, f.side, part, hit_p, n, speed, obj)
            except Exception as e:
                print("feet.ON_CONTACT hook failed:", e)

    def plant(self, key=False, frame=None, contact=None):
        """Correct both feet for the current frame. Returns {side: world move applied}.

        contact: optional {side: True/False} from the walk cycle (stance or swing). Walk mode
        passes it, so turning or braking on the spot never reads as a foot lifting."""
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
            travel = (pos - f.prev) if f.prev is not None else Vector()
            f.prev = pos.copy()
            errs = [e for e in f.errors(self.bvh) if e[1] is not None]
            if not errs:
                continue
            low = min(e for _, e in errs)
            was = getattr(f, "planted", False)
            f.swing = getattr(f, "swing", 99)
            # one plant per step: a planted foot stays planted through heel strike, roll and
            # push-off (small sole motion), and a lifted foot must swing a few frames before
            # it may land again, so a foot never touches down twice in one step
            hint = None if contact is None else contact.get(f.side)
            # a foot pinned this far behind the body (walking backwards off a step, a shove)
            # cannot stay down: it lifts and takes a real step instead of being dragged or snapped
            last = getattr(f, "contact", None)
            if was and last and len(last) == len(pts):
                i = min(range(len(pts)), key=lambda j: last[j][1])
                # measured against where the foothold put the foot at landing, so a normal
                # foothold slide (up to a foot length onto a step) never counts as dragging
                stretch = (last[i][0] - pts[i]).xy - getattr(f, "land_off", Vector()).xy
                if stretch.length > STRETCH:
                    was, f.planted, f.contact = False, False, None
                    f.fade, f.swing = FADE, 0
                    hint = False
                    f.stance = MIN_STANCE
                    f.lift_from = None
                    f.forced, f.forced_k = FSTEP, 0
            if getattr(f, "forced", 0) > 0:
                hint = False   # mid catch-up step: the foot is in the air whatever the cycle says
            if hint is not None:
                planted = hint and (was or f.swing >= MIN_SWING)
                # a foot that lands stays down for a real stance: when the walk reverses or
                # stalls on a boundary, the cycle can flick to swing for a frame; a touch and
                # lift in two frames is exactly the double step people notice
                if was and not planted and getattr(f, "stance", MIN_STANCE) < MIN_STANCE:
                    planted = True
                # ... and the other way round: a lift that the cycle takes back a frame or two
                # later never left the floor, so the foot simply stays where it was
                if hint and not was and f.swing <= 2 and getattr(f, "lift_from", None) is not None:
                    f.contact, f.hold = f.lift_from
                    was = planted = True
                    f.planted = True
            elif was:
                planted = travel.xy.length < STILL * 4 and low < 0.03
            else:
                planted = travel.xy.length < STILL * 1.5 and low < 0.02 and f.swing >= MIN_SWING
            if planted:
                if not was:
                    pred = getattr(f, "pred", None)
                    trav = f.last_travel if getattr(f, "last_travel", None) else fwd
                    f.hold = (pred + self._foothold(f, [p + pred for p in pts], trav)) if pred is not None else self._foothold(f, pts, f.last_travel if getattr(f, "last_travel", None) else fwd)
                    landed = True
                    f.pred, f.toe_down = None, False
                    f.land_off = f.hold.copy()
                f.stance = 0 if not was else getattr(f, "stance", 0) + 1
                f.planted, f.fade, f.swing = True, 0, 0
                off = f.hold
                # foot lock: the part of the sole that was on the floor last frame stays exactly
                # where it was (no skating when the body turns, brakes or leans), while the rest
                # of the foot is free to roll from heel to toe
                last = getattr(f, "contact", None) if not landed else None
                if last and len(last) == len(pts):
                    touching = [i for i, (_q, e) in enumerate(last) if e < 0.003] or list(range(len(pts)))
                    i = min(touching, key=lambda j: pts[j].z)
                    d = last[i][0] - pts[i]
                    off = Vector((d.x, d.y, 0.0))
                    # a lock that has to stretch this far means the body has walked off the
                    # foot (a reversal or a shove): let the foot go rather than drag the leg
                    # turning on a planted foot can swing part of the sole out over an edge
                    # (a sill, a pad, a tile): shuffle it back onto one level, at most 1 cm a frame
                    fix = self._foothold(f, [p + off for p in pts], f.last_travel if getattr(f, "last_travel", None) else fwd)
                    if fix.length > 1e-6:
                        off = off + fix * min(1.0, 0.01 / fix.length)
                f.hold = off
            else:
                if was:
                    f.fade = FADE  # ease the foothold slide out across the swing
                    f.lift_from = (f.contact, getattr(f, "hold", Vector()).copy())
                    f.contact = None
                elif f.swing > 2:
                    f.lift_from = None
                f.planted = False
                f.swing += 1
                f.last_travel = travel if travel.xy.length > 1e-5 else getattr(f, "last_travel", None)
                fade = getattr(f, "fade", 0)
                off = getattr(f, "hold", Vector()) * _smooth(fade / FADE)
                f.fade = max(0, fade - 1)
                # coming down: find the landing spot now and blend into it before contact,
                # so the foot never snaps sideways at heel strike
                if travel.z < 0 and low < LAND and f.swing >= MIN_SWING:
                    if getattr(f, "pred", None) is None:
                        f.pred = self._foothold(f, pts, f.last_travel if getattr(f, "last_travel", None) else fwd)
                    off = off + f.pred * _smooth(1.0 - max(0.0, low) / LAND)
            if off.length:
                pts = [p + off for p in pts]
            hs = [surface(self.bvh, p) for p in pts]
            es = [p.z - h for p, (h, _n) in zip(pts, hs) if h is not None]
            if not es:
                continue
            low = min(es)
            if planted:
                _h, n = surface(self.bvh, sum(pts, Vector()) / len(pts))
                # follow real slopes (ramps), never the bevel or riser of a step edge
                tilt = n if n is not None and 0.85 < n.z < 0.9999 else None
                if tilt is not None:
                    # a true slope runs under the whole sole; a bevel or sill edge does not
                    for q in (min(pts, key=lambda p: p.dot(fwd)), max(pts, key=lambda p: p.dot(fwd))):
                        _hq, nq = surface(self.bvh, q)
                        if nq is None or nq.dot(tilt) < 0.995:
                            tilt = None
                            break
                move = off + Vector((0, 0, -low + 0.0002))
                self._nudge(f, move, tilt)
                fin = [p + Vector((0, 0, -low + 0.0002)) for p in pts]
                f.contact = [(q, q.z - (surface(self.bvh, q)[0] or q.z)) for q in fin]
                if ON_CONTACT and (landed or not getattr(f, "toe_down", True)):
                    self._contact(f, pts, fwd, landed, fps)
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
                    # look only as far as the foot will still travel before it lands: rising,
                    # up to about half a stride; coming down, what's left of this swing
                    reach = 0.27
                    short = False
                    if travel.z < -1e-5:
                        reach = min(reach, travel.xy.length * max(0.0, low) / -travel.z)
                        if reach < 0.06:   # about to land: still clear a low lip under the toe
                            reach, short = 0.06, True
                    for k in (0.02, 0.05, 0.09, 0.14, 0.2, 0.27):
                        if k > reach + 0.02:
                            break
                        for p in pts:
                            h, _n = surface(self.bvh, p + ahead * k, above=0.3)
                            if h is not None and not (short and h - lowest > 0.06):
                                lift = max(lift, h + 0.004 - lowest)
                # one clean arc: while the swing is still rising the clearance lift only grows;
                # once the foot is coming down it eases off instead of dropping (no dip, no hop)
                if getattr(f, "forced", 0) > 0:
                    # catch-up step (the body turned or walked off a planted foot): a real little
                    # step with its own arc, never a slide along the floor
                    k = f.forced_k
                    lift = max(lift, -low + 0.0002 + STEP_ARC * math.sin(math.pi * (k + 1) / (FSTEP + 1)))
                    f.forced_k, f.forced = k + 1, f.forced - 1
                prev_lift = getattr(f, "lift", 0.0) if f.swing > 1 else 0.0
                lift = max(lift, prev_lift if travel.z >= 0 else prev_lift * 0.8)
                # one arc in the world: once the foot has started down it never climbs again;
                # it holds its height instead (and only rises if the floor itself comes up to it)
                zr = min(p.z for p in pts)          # raw sole height this frame (with any slide)
                z = zr + max(0.0, lift)
                if f.swing <= 1:
                    f.zlast, f.falling = z, False
                else:
                    if z < getattr(f, "zlast", z) - 1e-4:
                        f.falling = True
                    elif getattr(f, "falling", False) and z > f.zlast:
                        z = max(f.zlast, zr - low + 0.0002)
                        lift = z - zr
                    f.zlast = z
                f.lift = max(0.0, lift)
                if lift <= 0 and not off.length:
                    continue
                move = off + Vector((0, 0, max(0.0, lift)))
                self._nudge(f, move)
            done[f.side] = move
            if DEBUG:
                print("FOOTDBG", self.scene.frame_current, f.side, hint, planted, round(low * 1000, 1), [round(v, 3) for v in move])
            if key:
                f.ik.keyframe_insert("location", frame=frame)
                rot = "rotation_quaternion" if f.ik.rotation_mode == "QUATERNION" else "rotation_euler"
                f.ik.keyframe_insert(rot, frame=frame)
        if done:
            bpy.context.view_layer.update()
            self._reach(key, frame)
        return done

    def _chain(self, f):
        """(pelvis bone, hip bone, leg length) of the IK chain that drives foot f."""
        c = getattr(f, "_chain", None)
        if c is None:
            c = False
            for pb in self.rig.pose.bones:
                for k in pb.constraints:
                    if k.type == "IK" and k.subtarget == f.ik.name:
                        n = k.chain_count or 2
                        bones, b = [], pb
                        while b is not None and len(bones) < n:
                            bones.append(b)
                            b = b.parent
                        if b is not None:
                            c = (b, bones[-1], sum(x.length for x in bones))
            f._chain = c
        return c or None

    def _reach(self, key, frame):
        """A leg can only reach so far. When a planted foot is farther from its hip than the
        leg is long (end of a stride, one foot up on a sill), the pelvis drops just enough,
        the way a person's hips sink at full stride, instead of the foot lifting off the floor."""
        mw = self.rig.matrix_world
        last = getattr(self, "_pel", None)
        if last is not None:
            pb, base, mine = last
            # if nothing re-posed the pelvis since last frame, take last frame's drop back off
            if (pb.location - mine).length < 1e-7:
                pb.location = base
                bpy.context.view_layer.update()
            self._pel = None
        need, pelvis = 0.0, None
        for f in self.feet:
            c = self._chain(f)
            if not c or not getattr(f, "planted", False):
                continue
            pel, hip, L = c
            h = mw @ hip.head
            t = mw @ f.ik.head
            d = t - h
            lim = L * 0.995
            if d.length > lim:
                # lower the hip until the target is within reach: solve |d + (0,0,s)| = lim
                xy2 = d.x * d.x + d.y * d.y
                if xy2 < lim * lim:
                    s = -d.z - (lim * lim - xy2) ** 0.5
                    need, pelvis = max(need, s), pel
        drop = getattr(self, "drop", 0.0)
        # sink at once, come back up over a few frames (no bounce)
        drop = need if need > drop else drop + (need - drop) * 0.35
        self.drop = drop
        if pelvis is None:
            pelvis = next((c[0] for c in (self._chain(f) for f in self.feet) if c), None)
        if pelvis is None or drop < 1e-5:
            return
        base = pelvis.location.copy()
        M = pelvis.matrix.copy()
        M.translation += mw.inverted().to_3x3() @ Vector((0, 0, -drop))
        pelvis.matrix = M
        self._pel = (pelvis, base, pelvis.location.copy())
        bpy.context.view_layer.update()
        if key:
            pelvis.keyframe_insert("location", frame=frame)


def steps(track, up=0.005, down=0.002, dip=0.008):
    """Human-style step check on one foot's (frame, height above floor, centre, world z) track.

    steps:  touchdowns (height falls below `down` after being above `up`)
    double: touchdowns that land again almost where the last one did, while the droid
            walks on (a foot that touches down twice in one step)
    dips:   swings whose height falls by more than `dip` between two highs before the
            foot lands (the arc sags and rises again), so every swing is one clean arc
    """
    downs, dips, air, peak, sag = [], [], False, 0.0, None
    for row in track:   # h: height above the floor (touchdowns); z: world height (the arc)
        fr, h, c, z = row[:4]
        body = row[4] if len(row) > 4 else c
        if not air and h > up:
            air, peak, sag = True, z, None
        elif air:
            if h < down:
                downs.append((fr, c, body))
                air = False
                continue
            if z > peak:
                if sag is not None and peak - sag > dip:
                    dips.append((fr, round((peak - sag) * 1000, 1)))
                peak, sag = z, None
            elif sag is None or z < sag:
                sag = z
    dist = [(b[1] - a[1]).xy.length for a, b in zip(downs, downs[1:])]
    med = sorted(dist)[len(dist) // 2] if dist else 0.0
    # a short step is only a double step if the body walked on meanwhile: settling or
    # turning on the spot at a stop takes small steps, the way a person shuffles to face
    moved = [(b[2] - a[2]).xy.length for a, b in zip(downs, downs[1:])]
    double = [downs[i + 1][0] for i, d in enumerate(dist) if med > 0.05 and d < 0.35 * med and moved[i] > 0.35 * med]
    return {"steps": len(downs), "double": double, "dips": dips}


def audit(rig, scene, frames, bvh=None, feet=None, step=1):
    """The foot test. Returns a report dict; ok is True only with 0 frames over the limits."""
    bvh = bvh or ground_bvh(scene, ignore=[rig] + list(rig.children_recursive))
    feet = [Foot(rig, s, (feet or {}).get(s, {}).get("ik"), (feet or {}).get(s, {}).get("parts")) for s in "LR"]
    feet = [f for f in feet if f.parts]
    rep = {"frames": 0, "feet": {}, "bad": []}
    for f in feet:
        rep["feet"][f.side] = {"planted_frames": 0, "worst_sink_mm": 0.0, "worst_float_mm": 0.0, "no_floor": 0}
    prev = {}
    track = {f.side: [] for f in feet}   # (frame, lowest height, sole centre) for the step checks
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
            track[f.side].append((fr, min((e for _, e in errs if e is not None), default=1.0), c.copy(), min(p.z for p in pts), rig.matrix_world.translation.copy()))
            for p, e in errs:
                if e is None:
                    if planted:
                        r["no_floor"] += 1
                    continue
                if e < -SINK:  # sinking is never allowed, planted or not
                    r["worst_sink_mm"] = max(r["worst_sink_mm"], round(-e * 1000, 2))
                    rep["bad"].append(dict(frame=fr, foot=f.side, kind="sink", mm=round(-e * 1000, 2), at=[round(v, 3) for v in p]))
            for q in f.rim_points():   # nothing pokes up into the toe spring or heel curve
                h, _n = surface(bvh, q)
                if h is not None and q.z - h < -SINK:
                    r["worst_sink_mm"] = max(r["worst_sink_mm"], round((h - q.z) * 1000, 2))
                    rep["bad"].append(dict(frame=fr, foot=f.side, kind="sink", mm=round((h - q.z) * 1000, 2), at=[round(v, 3) for v in q]))
                    break
            if planted:
                r["planted_frames"] += 1
                good = [(p, e) for p, e in errs if e is not None]
                lo_p, lo_e = min(good, key=lambda x: x[1]) if good else (None, 0.0)
                # a planted foot touches the floor (heel, flat or toe while it rolls) ...
                hi = lo_e
                # ... and no part of the sole that is down flat hangs over a lower level (a step edge)
                zc = lo_p.z if lo_p is not None else 0.0
                flat = [(p, e) for p, e in good if p.z - zc < 0.002]
                # how far the floor drops away under each flat point (a heel-strike pitch of a
                # millimetre or two is the foot's own roll, not a gap)
                drop = lambda p, e: e - lo_e - (p.z - zc)
                hang = [(p, drop(p, e)) for p, e in flat if drop(p, e) > FLOAT]
                rest = [p for p, e in flat if drop(p, e) <= FLOAT]
                # an edge rolling under the last centimetre of the sole is a bevel (every plate
                # and sill has one, 3-6 mm), not a step edge: count a hang only when the sole
                # sticks out over the lower level by more than OVERHANG
                for p, e in hang:
                    if rest and min((p - q).xy.length for q in rest) < OVERHANG:
                        continue
                    hi = max(hi, e)
                if hi > FLOAT:
                    r["worst_float_mm"] = max(r["worst_float_mm"], round(hi * 1000, 2))
                    p = max(good, key=lambda x: x[1])[0]
                    rep["bad"].append(dict(frame=fr, foot=f.side, kind="float", mm=round(hi * 1000, 2), at=[round(v, 3) for v in p]))
    for side, tr in track.items():
        st = steps(tr)
        rep["feet"][side].update(steps=st["steps"], double_steps=len(st["double"]), swing_dips=len(st["dips"]))
        for fr in st["double"]:
            rep["bad"].append(dict(frame=fr, foot=side, kind="double step", mm=0, at=[]))
        for fr, mm in st["dips"]:
            rep["bad"].append(dict(frame=fr, foot=side, kind="swing dip", mm=mm, at=[]))
    rep["bad_frames"] = len({(b["frame"], b["foot"]) for b in rep["bad"]})
    rep["bad"] = rep["bad"][:40]
    rep["ok"] = rep["bad_frames"] == 0
    return rep
