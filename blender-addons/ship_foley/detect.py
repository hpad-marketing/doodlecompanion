"""Find every contact in a shot: soles on the deck, fingertips on a prop, a
crate set down on a table, a drone bumping a console.

How it works:
* Probes. For each droid the rest pose is read once. Sole probes are the
  lowest vertices of the parts riding on foot/toe bones (heel, toe, ball,
  inner and outer edge). Fingertip probes are the far ends of the last finger
  or claw segments. A droid with no feet, like the hover drone, gets probes on
  its underside. Every loose prop gets probes on its corners.
* Surfaces. Everything that is not a droid becomes one BVH that never moves.
  Props that move (rigid bodies, keyed or constrained objects, anything that
  actually changes between frames) are rebuilt each frame from their own
  meshes.
* Events. Each probe is followed through the frame range, with sub-frames.
  When it closes to within 4 mm of a surface, that's a touch. Its strength is
  the peak approach speed in the 0.1 s before contact, measured against the
  surface, so a hand closing on a moving prop counts the relative speed. The
  exact moment is interpolated between samples and placed to the sample.
  Sliding while in contact becomes a scrape; a hand letting go of a prop
  makes a small release tick.
"""
import math
import re

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import profiles as P
from . import motors as MO

EPS_ON = 0.004       # metres: closer than this is touching
EPS_OFF = 0.009      # metres: further than this has let go
LOOKBACK = 0.10      # seconds of approach speed history behind a touch
MIN_SPEED = 0.03     # m/s: slower than this is resting, not a hit
MERGE = 0.035        # seconds: touches of one limb this close become one
SLIDE_MIN = 0.12     # m/s tangential speed that counts as a scrape
SKIP_TAGS = ("sb_haze", "sb_fourth_wall", "sb_ghost", "foley_ignore")
SKIP_NAMES = ("Fourth Wall", "Haze", "Planet", "SB Zero-G", "Door Sweep")
FOOT_BONE = re.compile(r"(foot|toe|heel|sole|ankle_roll)", re.I)
TIP_BONE = re.compile(r"^(f_[a-z]+_3|claw_\d_2)\.[LR]$", re.I)
FX_NAME = re.compile(r"dust|smoke|spark|steam|puff|mote|haze|fog|glow|beam|flare|vfx|^fx[ _]|particle|debris_fx|light_?cone|WGT_", re.I)
HOLLOW_NAME = re.compile(r"crate|locker|can\b|oil can|toolbox|bin|drum|barrel|box|cabinet|duct|tank", re.I)


# --- scene reading ----------------------------------------------------------

def _side(name):
    m = re.search(r"\.([LR])$", name or "")
    return m.group(1) if m else "C"


def _droid_parts(arm):
    out = []
    for ob in arm.children_recursive:
        if ob.type == "MESH" and not ob.hide_render:
            out.append(ob)
    return out


def _bone_of(ob, arm):
    o = ob
    while o is not None and o.parent is not None:
        if o.parent == arm and o.parent_type == "BONE":
            return o.parent_bone
        o = o.parent
    return ""


def _mat_name(ob, poly_index=None, me=None):
    if me is not None and poly_index is not None and 0 <= poly_index < len(me.polygons):
        mi = me.polygons[poly_index].material_index
        if mi < len(ob.material_slots) and ob.material_slots[mi].material:
            return ob.material_slots[mi].material.name
    m = ob.active_material
    return m.name if m else ob.name


def droids(scene):
    """Armatures that are droids: anything with mesh parts riding on its bones."""
    out = []
    for ob in scene.objects:
        if ob.type == "ARMATURE" and not ob.get("foley_ignore") and _droid_parts(ob):
            out.append(ob)
    return out


def profile_for(arm):
    pid = arm.get("foley_profile") or P.droid_id(
        [arm.get("droid"), arm.get("character"), arm.name, arm.data.name,
         " ".join(c.name for c in arm.users_collection), bpy.path.basename(bpy.data.filepath)])
    prof = dict(P.DROIDS.get(pid, P.DROIDS["generic"]))
    prof["id"] = pid
    if arm.get("foley_mass_kg"):
        prof["mass_kg"] = float(arm["foley_mass_kg"])
    return prof


class Probe:
    __slots__ = ("owner", "label", "limb", "kind", "part", "co", "mass", "mat", "size", "hand")

    def __init__(self, owner, label, limb, kind, part, co, mass, mat, size, hand=False):
        self.owner, self.label, self.limb, self.kind = owner, label, limb, kind
        self.part, self.co = part, co.copy()
        self.mass, self.mat, self.size, self.hand = mass, mat, size, hand

    def world(self):
        return self.part.matrix_world @ self.co


def _world_verts(ob, dg):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ob.matrix_world.copy()
    vs = [(mw @ v.co, v.co.copy()) for v in me.vertices]
    ev.to_mesh_clear()
    return vs


def _pick_sole(points, n_keep=5):
    """From sole vertices [(world, part, local)], keep heel, toe, middle and
    the two side edges."""
    if len(points) <= n_keep:
        return points
    ys = [p[0].y for p in points]
    xs = [p[0].x for p in points]
    cy, cx = sum(ys) / len(ys), sum(xs) / len(xs)
    picks = [min(points, key=lambda p: p[0].y), max(points, key=lambda p: p[0].y),
             min(points, key=lambda p: p[0].x), max(points, key=lambda p: p[0].x),
             min(points, key=lambda p: (p[0].x - cx) ** 2 + (p[0].y - cy) ** 2)]
    seen, out = set(), []
    for p in picks:
        k = (p[1].name, round(p[2].x, 4), round(p[2].y, 4), round(p[2].z, 4))
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def droid_probes(arm, scene):
    """Sole, fingertip (and underside) probes, read from the rest pose."""
    prof = profile_for(arm)
    label = prof["label"]
    old = arm.data.pose_position
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    probes = []
    try:
        parts = _droid_parts(arm)
        feet = {}
        tips = []
        allpts = []
        for ob in parts:
            bone = _bone_of(ob, arm)
            vs = _world_verts(ob, dg)
            if not vs:
                continue
            allpts.extend((w, ob, l) for w, l in vs)
            if FOOT_BONE.search(bone):
                feet.setdefault(_side(bone), []).extend((w, ob, l) for w, l in vs)
            elif TIP_BONE.match(bone):
                head = arm.matrix_world @ arm.data.bones[bone].head_local
                w, l = max(vs, key=lambda wl: (wl[0] - head).length)
                tips.append((_side(bone), ob, l))
        m_leg = prof["mass_kg"] * prof["leg"]
        for side, pts in feet.items():
            zmin = min(p[0].z for p in pts)
            sole = [p for p in pts if p[0].z <= zmin + 0.004]
            for w, ob, l in _pick_sole(sole):
                probes.append(Probe(arm, label, "foot." + side, "step", ob, l, m_leg,
                                    prof["foot"], prof["foot_size"]))
        if not feet and allpts and prof["leg"] > 0:   # no feet: the underside lands
            zmin = min(p[0].z for p in allpts)
            under = [p for p in allpts if p[0].z <= zmin + 0.01]
            for w, ob, l in _pick_sole(under):
                probes.append(Probe(arm, label, "body", "bump", ob, l, m_leg,
                                    P.classify(_mat_name(ob)), prof["foot_size"]))
        m_arm = prof["mass_kg"] * prof["arm"]
        for side, ob, l in tips:
            probes.append(Probe(arm, label, "hand." + side, "grab", ob, l, m_arm,
                                prof["hand"], prof["hand_size"], hand=True))
    finally:
        arm.data.pose_position = old
        bpy.context.view_layer.update()
    return probes


def _eligible(ob, droid_set):
    if ob.type not in {"MESH", "CURVE", "FONT"} or ob.hide_render or not ob.visible_get():
        return False
    if any(ob.get(t) for t in SKIP_TAGS) or any(ob.name.startswith(s) for s in SKIP_NAMES):
        return False
    if FX_NAME.search(ob.name) or any(FX_NAME.search(c.name) for c in ob.users_collection):
        return False           # puffs, sparks and haze are not solid
    if ob in droid_set or ob.get("sb_droid"):
        return False
    if ob.display_type in {"BOUNDS", "WIRE"} and ob.type == "MESH" and len(ob.data.polygons) < 13:
        return False
    return True


def _is_dynamic(ob, moved):
    if ob in moved or ob.get("sb_prop") or ob.get("foley_prop"):
        return True
    rb = ob.rigid_body
    if rb is not None and rb.type == "ACTIVE" and rb.enabled:
        return True
    if any(c.name == "Loose props" for c in ob.users_collection):
        return True
    return False


def _moved_objects(scene, objs, frames):
    first = {}
    moved = set()
    for f in frames:
        scene.frame_set(f)
        for ob in objs:
            m = ob.matrix_world.copy()
            if ob not in first:
                first[ob] = m
            elif any(abs(a - b) > 1e-5 for ra, rb in zip(m, first[ob]) for a, b in zip(ra, rb)):
                moved.add(ob)
    return moved


def _root_prop(ob, dyn):
    """Props are built as a main object with painted-on children; group them."""
    while ob.parent is not None and ob.parent in dyn:
        ob = ob.parent
    return ob


class Surface:
    """A mesh the probes can hit: static ones share one BVH, moving ones
    carry their own and are re-placed each frame."""

    def __init__(self, ob, me):
        self.ob = ob
        self.local = [v.co.copy() for v in me.vertices]
        self.polys = [tuple(p.vertices) for p in me.polygons]
        tag = ob.get("sb_surface") or (ob.parent.get("sb_surface") if ob.parent else None)
        if tag in P.MATERIALS:      # Ship Builder stamps this at build time
            self.mats = [tag] * len(me.polygons)
        else:
            self.mats = [P.classify(_mat_name(ob, p.index, me)) for p in me.polygons]
        dims = ob.dimensions
        self.size = max(min(max(dims), 1.2), 0.03)
        hollow = ob.get("foley_hollow")
        if hollow is None:
            hollow = 0.7 if HOLLOW_NAME.search(ob.name) else 0.0
        self.hollow = float(hollow)
        rb = ob.rigid_body
        self.mass = float(rb.mass) if rb is not None else None
        self.bvh = None
        self.mw_prev = ob.matrix_world.copy()
        self.mw = ob.matrix_world.copy()

    def place(self, t=None, frame_len=None):
        if t is None:
            self.mw_prev = self.mw
        else:
            self.hist = [h for h in getattr(self, "hist", []) if h[0] >= t - frame_len - 1e-6]
            self.mw_prev = self.hist[0][1] if self.hist else self.ob.matrix_world.copy()
            self.hist.append((t, self.ob.matrix_world.copy()))
        self.mw = self.ob.matrix_world.copy()
        vs = [self.mw @ v for v in self.local]
        self.bvh = BVHTree.FromPolygons(vs, self.polys, epsilon=0.0) if self.polys else None
        self.centre = sum(vs, Vector()) / max(len(vs), 1)
        self.radius = max(((v - self.centre).length for v in vs), default=0.0)

    def velocity_at(self, p, dt):
        if dt <= 0:
            return Vector()
        loc = self.mw.inverted_safe() @ p
        return (self.mw @ loc - self.mw_prev @ loc) / dt


class StaticWorld:
    def __init__(self, surfaces):
        verts, polys, owner = [], [], []
        for s in surfaces:
            base = len(verts)
            verts.extend(s.mw @ v for v in s.local)
            for i, p in enumerate(s.polys):
                polys.append(tuple(base + j for j in p))
                owner.append((s, i))
        self.owner = owner
        self.bvh = BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None


def _mesh_of(ob, dg):
    ev = ob.evaluated_get(dg)
    try:
        me = ev.to_mesh()
    except RuntimeError:
        return None
    return me if me is not None and len(me.polygons) else None


def _prop_probes(surf):
    """Corner and bottom-centre probes for a loose prop (its own mesh space)."""
    ob = surf.ob
    bb = [Vector(c) for c in ob.bound_box]
    lo = Vector((min(c.x for c in bb), min(c.y for c in bb), min(c.z for c in bb)))
    hi = Vector((max(c.x for c in bb), max(c.y for c in bb), max(c.z for c in bb)))
    pts = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    pts.append(Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z)))
    mat = max(set(surf.mats), key=surf.mats.count) if surf.mats else "metal"
    dims = ob.dimensions
    vol = max(dims.x * dims.y * dims.z, 1e-6)
    mass = surf.mass if surf.mass is not None else vol * P.MATERIALS[mat]["density"] * (0.3 if surf.hollow else 0.8)
    return [Probe(ob, ob.name, "prop", "place", ob, p, mass, mat, max(dims)) for p in pts]


# --- the scan ---------------------------------------------------------------

class _Track:
    __slots__ = ("touch", "hist", "last_t", "surf", "slide_t0", "slide_env", "prev_p", "prev_d", "path")

    def __init__(self):
        self.touch = False
        self.hist = []          # (t, approach speed)
        self.last_t = -9.0
        self.surf = None
        self.slide_t0 = None
        self.slide_env = []
        self.prev_p = None
        self.prev_d = None
        self.path = []          # (t, world point) over the last frame


def _nearest(p, world, movers, skip_ob, reach=0.25):
    best = None
    if world.bvh is not None:
        loc, nrm, idx, d = world.bvh.find_nearest(p, reach)
        if loc is not None:
            s, pi = world.owner[idx]
            best = (d, loc, nrm, s, pi)
    for s in movers:
        if s.ob is skip_ob or s.bvh is None:
            continue
        if (p - s.centre).length > s.radius + reach:
            continue
        loc, nrm, idx, d = s.bvh.find_nearest(p, reach)
        if loc is not None and (best is None or d < best[0]):
            best = (d, loc, nrm, s, idx)
    return best


def _cam_info(scene, p):
    cam = scene.camera
    if cam is None:
        return 0.0, 3.0, True
    from bpy_extras.object_utils import world_to_camera_view
    v = world_to_camera_view(scene, cam, p)
    pan = max(-1.0, min(1.0, (v.x - 0.5) * 2.0)) * 0.85
    dist = (cam.matrix_world.translation - p).length
    seen = v.z > 0 and -0.1 <= v.x <= 1.1 and -0.1 <= v.y <= 1.1
    return pan, dist, seen


def scan(scene=None, frame_start=None, frame_end=None, substeps=2, include_props=True, report=None,
         motors_out=None):
    """Return the shot's contact events, sorted by time.

    Each event is a dict: frame (float), time, kind, who, limb, loc, pan,
    dist, on_screen, and hit (the synth.Hit arguments)."""
    scene = scene or bpy.context.scene
    f0 = scene.frame_start if frame_start is None else frame_start
    f1 = scene.frame_end if frame_end is None else frame_end
    fps = scene.render.fps / scene.render.fps_base
    keep = scene.frame_current

    arms = droids(scene)
    droid_set = set()
    for a in arms:
        droid_set.add(a)
        droid_set.update(a.children_recursive)

    cands = [ob for ob in scene.objects if _eligible(ob, droid_set)]
    samples = sorted({f0, (f0 + f1) // 2, f1, f0 + (f1 - f0) // 4, f0 + 3 * (f1 - f0) // 4})
    moved = _moved_objects(scene, cands, samples)
    dyn = {ob for ob in cands if _is_dynamic(ob, moved)}

    scene.frame_set(f0)
    probes = []
    for a in arms:
        probes.extend(droid_probes(a, scene))
    dg = bpy.context.evaluated_depsgraph_get()
    statics, movers = [], []
    for ob in cands:
        me = _mesh_of(ob, dg)
        if me is None:
            continue
        s = Surface(ob, me)
        ob.evaluated_get(dg).to_mesh_clear()
        (movers if ob in dyn else statics).append(s)
    world = StaticWorld(statics)
    if include_props:
        for s in movers:
            if _root_prop(s.ob, dyn) is s.ob:
                probes.extend(_prop_probes(s))
    if report:
        report(f"{len(arms)} droids, {len(probes)} probes, {len(statics)} fixed surfaces, {len(movers)} moving props")

    tracks = [_Track() for _ in probes]
    events = []
    steps = [(f, k / substeps) for f in range(f0, f1 + 1) for k in range(substeps)]
    dt = 1.0 / (fps * substeps)
    t_prev = None
    motor_js = {a: MO.joints(a) for a in arms} if motors_out is not None else {}
    for f, sub in steps:
        if f == f1 and sub > 0:
            break
        scene.frame_set(f, subframe=sub)
        t = (f + sub - f0) / fps
        for s in movers:
            s.place(t, 1.0 / fps)
        for a, js in motor_js.items():
            MO.sample(a, js, t, 1.0 / fps)
        for pr, tr in zip(probes, tracks):
            p = pr.world()
            hit = _nearest(p, world, movers, pr.part if pr.limb == "prop" else None)
            if hit is None:
                d, n, surf, pi, v_n, v_t = 1.0, Vector((0, 0, 1)), None, None, 0.0, 0.0
            else:
                d, loc, nrm, surf, pi = hit
                off = p - loc
                n = off.normalized() if off.length > 1e-6 else nrm
                if off.dot(nrm) < 0 and d < 0.03:   # slightly inside: touching
                    d, n = 0.0, nrm
                if tr.path:
                    # velocity over a whole frame: rigid-body sims only step on
                    # whole frames, so a sub-frame difference would double it
                    t_old, p_old = tr.path[0]
                    span = max(t - t_old, dt)
                    v = (p - p_old) / span
                    if surf in movers:
                        v = v - surf.velocity_at(p, span)
                    v_n = -v.dot(n)
                    v_t = (v + n * v_n).length
                else:
                    v_n = v_t = 0.0
            tr.hist.append((t, max(v_n, 0.0)))
            while tr.hist and tr.hist[0][0] < t - LOOKBACK:
                tr.hist.pop(0)

            if t_prev is None:
                tr.touch = d <= EPS_ON
            elif not tr.touch and d <= EPS_ON and surf is not None:
                speed = max(s for _, s in tr.hist)
                dp = tr.prev_d if tr.prev_d is not None else d
                frac = 0.0 if dp <= d else min(max((dp - EPS_ON) / (dp - d), 0.0), 1.0)
                tc = t_prev + frac * dt
                tr.touch = True
                tr.surf = surf
                if speed >= MIN_SPEED and tc - tr.last_t > 0.08:
                    tr.last_t = tc
                    events.append(_event(scene, pr, surf, pi, speed, tc, f0, fps, p))
            elif tr.touch and d > EPS_OFF:
                if pr.hand and tr.surf is not None and tr.surf in movers:
                    sep = max(-v_n, 0.0)
                    if sep >= MIN_SPEED:
                        e = _event(scene, pr, tr.surf, None, sep * 0.35, t, f0, fps, p)
                        e["kind"] = e["hit"]["kind"] = "release"
                        events.append(e)
                _end_slide(scene, pr, tr, events, f0, fps, p)
                tr.touch = False
                tr.surf = None

            if pr.limb == "prop" and tr.touch and surf is not None and d <= EPS_OFF:
                # only props scrape: planted feet never slide (foot rule), and an
                # in-place walk cycle would otherwise read as one long scrape
                if v_t >= SLIDE_MIN:
                    if tr.slide_t0 is None:
                        tr.slide_t0 = t
                        tr.slide_env = []
                    tr.slide_env.append(v_t)
                    tr.surf = surf
                elif tr.slide_t0 is not None:
                    _end_slide(scene, pr, tr, events, f0, fps, p)
            tr.prev_p, tr.prev_d = p, d
            tr.path.append((t, p))
            while len(tr.path) > 1 and tr.path[0][0] < t - 1.0 / fps + 1e-6:
                tr.path.pop(0)
        t_prev = t
    for pr, tr in zip(probes, tracks):
        _end_slide(scene, pr, tr, events, f0, fps, pr.world())
    events = _hold_signal(scene, arms, movers, events, f0, f1, fps)
    for a, js in motor_js.items():
        prof = profile_for(a)
        clunks = MO.stop_clunks(prof["label"], js, prof, fps, f0)
        for e in clunks:
            e["pan"], e["dist"], e["on_screen"] = _cam_info(scene, Vector(e["loc"]))
        events.extend(clunks)
        motors_out[a.name] = dict(prof=prof, joints=js, f0=f0, f1=f1, fps=fps)
    scene.frame_set(keep)
    return merge(events)


# --- Hold / Release keys (droid kit rig_ui: hold_prop / release_prop) --------

PALM = ("hold.{s}", "socket_hand.{s}", "hand_socket.{s}", "DEF-hand.{s}", "grip.{s}")


def _palm(arm, side):
    pb = arm.pose.bones
    for pat in PALM:
        b = pb.get(pat.format(s=side))
        if b is not None:
            return lambda b=b: arm.matrix_world @ b.head
    return None


def _hold_keys(arm, side):
    """(frame, 'grab'|'release') from the keys on ["hold_L"] / ["hold_R"]."""
    ad = arm.animation_data
    act = ad.action if ad else None
    if act is None:
        return []
    fc = None
    path = '["hold_%s"]' % side
    try:
        fcs = list(act.fcurves)
    except AttributeError:          # layered actions (Blender 4.4+)
        fcs = []
        for layer in getattr(act, "layers", ()):
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", ()):
                    fcs.extend(bag.fcurves)
    for c in fcs:
        if c.data_path == path:
            fc = c
            break
    if fc is None:
        return []
    out, prev = [], None
    for k in sorted(fc.keyframe_points, key=lambda k: k.co.x):
        on = k.co.y >= 0.5
        if prev is not None and on != prev:
            out.append((k.co.x, "grab" if on else "release"))
        elif prev is None and on:
            out.append((k.co.x, "grab"))
        prev = on
    return out


def _held_prop(arm, side, movers, p):
    tag = "%s:%s" % (arm.name, side)
    for s in movers:
        if s.ob.get("held_by") == tag:
            return s
    best = None
    for s in movers:
        s.place()
        if s.bvh is None:
            continue
        loc, _n, _i, d = s.bvh.find_nearest(p, 0.4)
        if loc is not None and (best is None or d < best[0]):
            best = (d, s)
    return best[1] if best else None


def _hold_signal(scene, arms, movers, events, f0, f1, fps):
    """Hold/Release keys are the authored grab moments: they replace the
    fingertip guesses for that hand within 0.3 s, and get their own sound
    sized by how fast the palm was moving into the grab."""
    for arm in arms:
        prof = profile_for(arm)
        for side in ("L", "R"):
            keys = [k for k in _hold_keys(arm, side) if f0 <= k[0] <= f1]
            palm = _palm(arm, side)
            if not keys or palm is None:
                continue
            limb = "hand." + side
            # while held, fingers shifting on the handle stay quiet: the keys own it
            spans, t_on = [], None
            for fr, what in keys:
                tk = (fr - f0) / fps
                if what == "grab":
                    t_on = tk
                elif t_on is not None:
                    spans.append((t_on - 0.4, tk + 0.1))
                    t_on = None
            if t_on is not None:
                spans.append((t_on - 0.4, 1e9))
            events = [e for e in events if not (e["who"] == prof["label"] and e["limb"] == limb
                                                and e["kind"] in ("grab", "release") and not e.get("signal")
                                                and any(a <= e["time"] <= b for a, b in spans))]
            for fr, what in keys:
                pts = []
                for i in range(4, -1, -1):          # 0.1 s of palm path up to the key
                    tf = fr - i * LOOKBACK * fps / 4
                    scene.frame_set(int(math.floor(tf)), subframe=tf - math.floor(tf))
                    pts.append(palm())
                step = LOOKBACK / 4
                speed = max((b - a).length / step for a, b in zip(pts, pts[1:]))
                if what == "release":
                    speed *= 0.35
                p = pts[-1]
                surf = _held_prop(arm, side, movers, p)
                if surf is None:
                    continue
                t = (fr - f0) / fps
                limb = "hand." + side
                events = [e for e in events if not (e["who"] == prof["label"] and e["limb"] == limb
                                                    and e["kind"] in ("grab", "release") and abs(e["time"] - t) < 0.3)]
                pr = Probe(arm, prof["label"], limb, what, surf.ob, Vector(), prof["mass_kg"] * prof["arm"],
                           prof["hand"], prof["hand_size"], hand=True)
                e = _event(scene, pr, surf, None, max(speed, MIN_SPEED), t, f0, fps, p)
                e["kind"] = e["hit"]["kind"] = what
                e["signal"] = "hold key"
                events.append(e)
    return events


def _event(scene, pr, surf, pi, speed, t, f0, fps, p):
    b_mat = surf.mats[pi] if pi is not None and pi < len(surf.mats) else (
        max(set(surf.mats), key=surf.mats.count) if surf.mats else "metal")
    kind = pr.kind
    if pr.limb == "prop":
        kind = "place" if speed < 0.6 else "bump"
    pan, dist, seen = _cam_info(scene, p)
    return dict(
        frame=f0 + t * fps, time=t, kind=kind, who=pr.label, limb=pr.limb,
        loc=tuple(round(x, 4) for x in p), surface=surf.ob.name, pan=pan, dist=dist, on_screen=seen,
        hit=dict(kind=kind, mass=pr.mass, speed=speed, a_mat=pr.mat, a_size=pr.size,
                 b_mat=b_mat, b_size=surf.size, b_hollow=surf.hollow, b_mass=surf.mass))


def _end_slide(scene, pr, tr, events, f0, fps, p):
    if tr.slide_t0 is None:
        return
    env = tr.slide_env
    n = len(env)
    if n >= 3 and tr.surf is not None:
        dur = n / (fps * 2)
        e = _event(scene, pr, tr.surf, None, max(env), tr.slide_t0, f0, fps, p)
        e["kind"] = e["hit"]["kind"] = "slide"
        e["hit"]["slide"] = (dur, [0.0] + list(env) + [0.0])
        e["duration"] = dur
        events.append(e)
    tr.slide_t0 = None
    tr.slide_env = []


def merge(events):
    """One limb touching at several probes at once is one sound: keep the
    strongest, and let the extra contact add a little weight."""
    events = sorted(events, key=lambda e: e["time"])
    out = []
    for e in events:
        if e["kind"] != "slide":
            for o in reversed(out[-12:]):
                if (o["who"], o["limb"], o["kind"]) == (e["who"], e["limb"], e["kind"]) and e["time"] - o["time"] <= MERGE:
                    if e["hit"]["speed"] > o["hit"]["speed"]:
                        e["time"], e["frame"] = o["time"], o["frame"]
                        o.update(e)
                    o["hit"]["mass"] = max(o["hit"]["mass"], e["hit"]["mass"])
                    break
            else:
                out.append(e)
        else:
            out.append(e)
    for i, e in enumerate(out):
        e["id"] = i
    return out
