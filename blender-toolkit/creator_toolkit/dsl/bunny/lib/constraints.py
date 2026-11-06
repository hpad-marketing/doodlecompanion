"""Always-on defaults: the animation rules built into the render so they can't go wrong.

Nothing here checks, blocks or rejects a shot. Each default quietly shapes the pose or the set
while the shot is built, the way the floor lift keeps strokes off the floor:

  armInFront    a hand, cuff or forearm never sits hidden behind the head from the camera:
                the arm takes the smallest turn that brings it out in front of the face (or
                clear of the head's outline), eased in and out over a few frames
  faceClear     a set piece or placed prop never blocks the face from the camera: it slides
                sideways just far enough (set pieces that can't move hide on those frames)
  propsOnFloor  props and set pieces that stand on the floor rest their ink stroke a hair above
                the floor you see under them (the set's own floor, never an outline or a hidden plane), the same lift the characters get (lift only: a prop on a table, in the air
                or deliberately sunk deep stays where it was put)
  eyeSize       eyes keep one size: the Frog's eye bumps ignore EAR Scale / EAR Squash

Every default can be turned off per shot: shot['rules'] = {'armInFront': False, ...}.
A single frame can let the arm go behind the head with the frame value freeArms = 1.
"""
import math

import bpy
from mathutils import Vector

import collision

DEFAULTS = {'armInFront': True, 'faceClear': True, 'propsOnFloor': True, 'eyeSize': True}
_rules = dict(DEFAULTS)
_cam = None


def configure(shot, cam):
    """Read the shot's overrides (anything not set stays on)."""
    global _cam
    _rules.clear()
    _rules.update(DEFAULTS)
    for k, v in (shot.get('rules') or {}).items():
        if k in DEFAULTS:
            _rules[k] = v is not False and v != 0
    _cam = cam
    return dict(_rules)


def on(name):
    return bool(_rules.get(name, True))


# ---------------------------------------------------------------- eye size
EYE_TRACKS = ('earLScale', 'earRScale', 'earLSquash', 'earRSquash')


def prepare(vals, rig):
    """Frame values with the size defaults applied (a new dict; the input is left alone)."""
    if on('eyeSize') and rig.get('ear_width_lock') and any(k in vals for k in EYE_TRACKS):
        vals = {k: v for k, v in vals.items() if k not in EYE_TRACKS}
    return vals


# ---------------------------------------------------------------- arm in front of the face
ARM_PARTS = collision.ARM_PARTS          # hand, cuff, forearm sleeve
LIMITS = {'arm': (-10, 145), 'Forward': (-60, 110), 'elbow': (0, 140)}
HIDDEN_TOL = 0.0                        # share of sampled arm points the head may hide


def _cam_ray(cam, p):
    """(origin, direction, distance) of the camera's line of sight to world point p."""
    if cam.data.type == 'ORTHO':
        fwd = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
        o = p - fwd * 100.0
        return o, fwd, 100.0
    o = cam.matrix_world.translation
    d = p - o
    L = d.length
    return o, d / max(L, 1e-9), L


def _points(obs, every=3):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for ob in obs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        vs = me.vertices
        out += [mw @ vs[i].co for i in range(0, len(vs), every)]
        ev.to_mesh_clear()
    return out


def hidden_share(objs, side, cam, head_bvh):
    """Share of the arm's surface points that the head hides from the camera (0..1)."""
    obs = [objs[f'{p}.{side}'] for p in ARM_PARTS if f'{p}.{side}' in objs and not objs[f'{p}.{side}'].hide_render]
    pts = _points(obs, every=6)
    if not pts:
        return 0.0, None
    hid = front = 0
    for p in pts:
        o, d, L = _cam_ray(cam, p)
        if head_bvh.ray_cast(o, d, L - 0.004)[0] is not None:
            hid += 1
        elif head_bvh.ray_cast(p + d * 0.004, d, 3.0)[0] is not None:
            front += 1          # the head is right behind this point: the arm is over the face
    return hid / len(pts), front / len(pts)


def _facing_away(head, vals, cam):
    """True when the face points more than ~100 degrees away from the camera."""
    rig = head.find_armature() or head.parent
    yaw = math.radians(float(vals.get('turn', 0.0)) + float(vals.get('headYaw', 0.0)))
    face = Vector((math.sin(yaw), -math.cos(yaw), 0.0))
    if rig is not None:
        face = rig.matrix_world.to_3x3() @ face
    hp = sum((head.matrix_world @ Vector(b) for b in head.bound_box), Vector()) / 8
    if cam.data.type == 'ORTHO':
        to_cam = -(cam.matrix_world.to_3x3() @ Vector((0, 0, -1)))
    else:
        to_cam = cam.matrix_world.translation - hp
    to_cam.z = 0
    if to_cam.length < 1e-4:
        return False
    return face.normalized().dot(to_cam.normalized()) < -0.17


def _clamp(k, v):
    for key, (lo, hi) in LIMITS.items():
        if (key == 'Forward' and k.endswith('Forward')) or (key != 'Forward' and k.startswith(key) and not k.endswith('Forward')):
            return max(lo, min(hi, v))
    return v


FORWARD_COST = 0.6   # a forward move costs this share of its size when choosing the fix
IN_FRONT = 4.0   # over the face this many times more than hidden: the hand reads as in front


def _clear(share, front):
    """The arm reads clean: nothing of it hidden by the head, or it clearly crosses in front of
    the face (a mic at the mouth, a hand on the cheek: only its contact side is out of sight)."""
    return share <= HIDDEN_TOL or front >= IN_FRONT * share


def _ok(apply, cand, objs, side, cam, hb):
    apply(cand)
    bpy.context.view_layer.update()
    if collision.arm_hits_head(objs, side, hb):
        return False, None
    s, fr = hidden_share(objs, side, cam, hb)
    obs = [objs[f'hand.{side}']] if f'hand.{side}' in objs else []
    pts = _points(obs, 9)
    c = sum(pts, Vector()) / len(pts) if pts else None
    return _clear(s, fr), c


STEEP = 45.0     # degrees: a camera looking down (or up) steeper than this sees hands under the head naturally
BUDGET = 48      # most candidate poses tried per arm per frame (keeps renders fast)


def _steep(cam):
    fwd = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    return abs(math.degrees(math.asin(max(-1.0, min(1.0, fwd.z))))) > STEEP


def arm_in_front(apply, vals, objs, cam=None, hint=None, scan=90, step=10):
    """Pose `vals` (already collision-solved) so that neither arm hides behind the head as the
    camera sees it. Returns (vals, fix) where fix maps side -> {track: delta}."""
    cam = cam or _cam
    fix = {}
    if cam is None or not on('armInFront') or float(vals.get('freeArms', 0) or 0) >= 0.5 or 'head' not in objs:
        return vals, fix
    apply(vals)
    bpy.context.view_layer.update()
    if _steep(cam) or _facing_away(objs['head'], vals, cam):
        return vals, fix      # his back is to the camera: a hand at his face is simply out of sight
    hb = collision._cage_bvh(objs['head'])
    for side in 'LR':
        share, fr = hidden_share(objs, side, cam, hb)
        if _clear(share, fr):
            continue
        ids = (f'arm{side}', f'arm{side}Forward', f'elbow{side}')
        base = {k: float(vals.get(k, 0.0)) for k in ids}
        found = None
        prev = (hint or {}).get(side)
        if isinstance(prev, dict):
            cand = dict(vals)
            for k in ids:
                cand[k] = _clamp(k, base[k] + prev.get(k, 0.0))
            ok, _ = _ok(apply, cand, objs, side, cam, hb)
            if ok:
                found = cand
        # forward (toward the camera, in front of the face) first, then down, then out
        dirs = [(0, 1, 0), (-1, 1, 0), (1, 1, 0), (-1, 0, 0), (0, 1, -1), (0, 1, 1), (1, 0, 0), (-1, -1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        # bringing the hand forward, in front of the face, is preferred: it keeps the gesture
        # (a raised arm stays raised) and counts as a smaller change than lowering or swinging
        if not found:
            best, rad, left, tries = None, step, list(dirs), 0
            while left and rad <= scan and tries < BUDGET and (best is None or rad * FORWARD_COST < best[0]):
                for d in list(left):
                    tries += 1
                    cand = dict(vals)
                    n = math.sqrt(sum(x * x for x in d))
                    for k, dk in zip(ids, d):
                        cand[k] = _clamp(k, base[k] + dk / n * rad)
                    ok, _ = _ok(apply, cand, objs, side, cam, hb)
                    if ok:
                        cost = rad * (FORWARD_COST if d[1] > 0 else 1.0)
                        if best is None or cost < best[0]:
                            best = (cost, cand)
                        left.remove(d)
                rad += step
            found = best[1] if best else None
        if not found:
            apply(vals)
            bpy.context.view_layer.update()
            continue
        # bisect back toward the authored pose: the smallest move that still clears
        lo, hi = 0.0, 1.0
        for _ in range(5):
            mid = (lo + hi) / 2
            cand = dict(vals)
            for k in ids:
                cand[k] = base[k] + (found[k] - base[k]) * mid
            ok, _ = _ok(apply, cand, objs, side, cam, hb)
            lo, hi = (lo, mid) if ok else (mid, hi)
        for k in ids:
            vals[k] = base[k] + (found[k] - base[k]) * hi
        fix[side] = {k: round(vals[k] - base[k], 3) for k in ids}
        apply(vals)
        bpy.context.view_layer.update()
    return vals, fix


ARM_BONES = ('upper_arm_fk', 'forearm_fk', 'hand_fk')
EASE = 4   # frames to ease a correction in before it starts and out after it ends


def ease_fixes(rig, apply, frames_vals, fixes, objs, log=None):
    """A correction that starts or stops on one frame would pop the arm. Spread each one over
    EASE frames either side (smoothstep), re-keying only the arm bones (the root keeps its floor
    lift). A ramp frame that would bring the hand into the head keeps its own pose."""
    sc = bpy.context.scene
    n = len(frames_vals)
    eased = 0
    for side in 'LR':
        fixed = {f: fx[side] for f, fx in fixes.items() if side in fx}
        if not fixed:
            continue
        bones = [rig.pose.bones.get(f'{b}.{side}') for b in ARM_BONES]
        bones = [b for b in bones if b is not None]
        for f in range(1, n + 1):
            if f in fixed:
                continue
            near = [(abs(f - g), g) for g in fixed if abs(f - g) <= EASE]
            if not near:
                continue
            dist, g = min(near)
            t = 1 - dist / (EASE + 1)
            w = t * t * (3 - 2 * t)
            vals = dict(frames_vals[f - 1])
            for k, dv in fixed[g].items():
                vals[k] = _clamp(k, float(vals.get(k, 0.0)) + dv * w)
            sc.frame_set(f)
            apply(vals)
            bpy.context.view_layer.update()
            if collision.arm_hits_head(objs, side):
                continue
            for b in bones:
                b.keyframe_insert(__import__('ds_map').rotation_path(b), frame=f, group=b.name)
                if 'hinge_r' in b:
                    b.keyframe_insert('location', frame=f, group=b.name)
            eased += 1
    sc.frame_set(1)
    if eased and log:
        log(f'rules: arm-in-front eased over {eased} frames')
    return eased


# ---------------------------------------------------------------- props rest on the floor
def _descendants(ob):
    out = [ob]
    for c in ob.children:
        out += _descendants(c)
    return out


def _animated_location(ob):
    ad = ob.animation_data
    return bool(ad and ad.action and any(getattr(fc, 'data_path', '') == 'location' for fc in __import__('compat').fcurves(ob)))


def _surface_under(obs, lo, ground):
    """Height of the visible surface under the piece's lowest points: cast straight down with
    every ink outline switched off (outlines are never a floor), skipping the piece itself and
    the characters. Nothing found: the ground plane."""
    sc = bpy.context.scene
    ink = [m for ob in sc.objects if ob.type == 'MESH' for m in ob.modifiers if m.type == 'NODES' and m.show_viewport]
    for m in ink:
        m.show_viewport = False
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        mine = set(obs)
        pts = sorted(_points(obs, every=3), key=lambda p: p.z)[:24:4]
        best = None
        for p in pts:
            o = Vector((p.x, p.y, lo + SINK))
            for _ in range(16):
                hit, loc, nrm, _i, hob, _m = sc.ray_cast(dg, o, Vector((0, 0, -1)), distance=2 * SINK + 0.05)
                if not hit:
                    break
                if hob in mine or (hob is not None and (hob.hide_render or collision._is_character(hob))) or abs(nrm.z) < 0.5:
                    o = loc - Vector((0, 0, 1e-4))
                    continue
                best = loc.z if best is None else max(best, loc.z)
                break
        return ground if best is None else best
    finally:
        for m in ink:
            m.show_viewport = True
        bpy.context.view_layer.update()


SINK = 0.15   # a prop whose stroke goes deeper than this into the floor was sunk on purpose


def props_on_floor(pieces, ground, log=None):
    """Lift each free-standing piece whose lowest stroke dips into the floor (or sits within a
    hair of it) so the stroke rests FLOOR_AIR above. Pieces higher up are left alone."""
    if not on('propsOnFloor'):
        return []
    lifted = []
    tops = []
    for ob in pieces:
        t = ob
        while t.parent is not None and t.parent.type != 'ARMATURE' and t.parent in pieces:
            t = t.parent
        if t not in tops:
            tops.append(t)
    for top in tops:
        if _animated_location(top) or max(top.dimensions) > 2.0:
            continue
        obs = [o for o in _descendants(top) if o.type == 'MESH' and not o.hide_render]
        if not obs:
            continue
        lo = collision.drawn_zmin(obs)
        if lo is None:
            continue
        # the floor is the surface you see in the scene right under the piece (user, 2026-10-31):
        # the set's own floor mesh, never an ink outline or a hidden plane at another height
        target = _surface_under(obs, lo, ground) + collision.FLOOR_AIR
        d = target - lo
        if d <= 2e-4 or d > SINK:
            continue
        if top.parent is None:
            top.location.z += d
        else:
            mw = top.matrix_world.copy()
            mw.translation.z += d
            top.matrix_world = mw
        bpy.context.view_layer.update()
        lifted.append((top.name, round(d * 100, 2)))
    if lifted and log:
        log('rules: rested on the floor ' + ', '.join(f'{n} (+{cm} cm)' for n, cm in lifted))
    return lifted


# ---------------------------------------------------------------- nothing blocks the face (or the body under it)
CLEAR_PARTS = ('head', 'shirt')   # the face and the body under it: never hidden behind a prop
CLEAR_MARGIN = 2                  # extra steps past the first clear spot, so edges don't kiss


def _face_points(objs, every=10):
    obs = [objs[k] for k in CLEAR_PARTS if k in objs and not objs[k].hide_render]
    return _points(obs, every) if obs else []


def _blocks(bvh, cam, pts):
    for p in pts:
        o, d, L = _cam_ray(cam, p)
        if bvh.ray_cast(o, d, L - 0.01)[0] is not None:
            return True
    return False


def face_clear(pieces, faces, cam, n, room_prefix=None, log=None, every=4, reach=1.5, stepm=0.04):
    """faces: list of character object dicts (lead first, then co-stars). Each piece that hides
    a face from the camera on any sampled frame slides sideways (across the camera's view) to
    the nearest clear spot; a set piece that can't move far enough hides on those frames.
    Props the user placed are moved, never hidden."""
    if not on('faceClear') or cam is None:
        return [], {}
    import rules_scene
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    frames = sorted(set([1, n] + list(range(1, n + 1, every))))
    moved, hidden = [], {}

    def _screen_box(pts):
        q = [world_to_camera_view(sc, cam, p) for p in pts]
        q = [x for x in q if x.z > 0]
        if not q:
            return None
        return min(x.x for x in q), max(x.x for x in q), min(x.y for x in q), max(x.y for x in q), min(x.z for x in q)

    def maybe(ob):
        """Cheap test first: the piece's box overlaps a face's box on screen and is nearer the camera."""
        a = _screen_box([ob.matrix_world @ Vector(b) for b in ob.bound_box])
        if a is None:
            return False
        for o in faces:
            fo = [objs_[k] for objs_ in (o,) for k in CLEAR_PARTS if k in objs_]
            b = _screen_box([x.matrix_world @ Vector(c) for x in fo for c in x.bound_box])
            if b and a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3] and a[4] < b[4] + 0.3:
                return True
        return False

    def blockers(ob, fset):
        out = []
        for f in fset:
            sc.frame_set(f)
            if not maybe(ob):
                continue
            t = rules_scene._world_bvh(ob)
            if any(_blocks(t, cam, _face_points(o)) for o in faces):
                out.append(f)
        return out

    for ob in pieces:
        if ob.hide_render or max(ob.dimensions) > 3.0:
            continue
        bad = blockers(ob, frames)
        if not bad:
            continue
        top = ob
        while top.parent is not None and top.parent.type != 'ARMATURE':
            top = top.parent
        if _animated_location(top):
            continue
        sc.frame_set(bad[0])
        right = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
        right.z = 0
        if right.length < 1e-4:
            right = Vector((1, 0, 0))
        right.normalize()
        face_c = sum((sum(_face_points(o, 40), Vector()) / max(1, len(_face_points(o, 40))) for o in faces), Vector()) / len(faces)
        c = sum((ob.matrix_world @ Vector(b) for b in ob.bound_box), Vector()) / 8
        sides = [1, -1] if (c - face_c).dot(right) >= 0 else [-1, 1]
        start = top.location.copy()
        done = False
        for k in range(1, int(reach / stepm) + 1):
            for s in sides:
                top.location = start + right * (s * k * stepm) if top.parent is None else start + (top.parent.matrix_world.to_3x3().inverted() @ right) * (s * k * stepm)
                bpy.context.view_layer.update()
                if not blockers(ob, bad):
                    done = True
                    k2 = k + CLEAR_MARGIN
                    top.location = start + right * (s * k2 * stepm) if top.parent is None else start + (top.parent.matrix_world.to_3x3().inverted() @ right) * (s * k2 * stepm)
                    bpy.context.view_layer.update()
                    break
            if done:
                break
        if done and not blockers(ob, frames):
            moved.append(f'{ob.name} {round((top.location - start).length * 100)} cm')
            continue
        top.location = start
        bpy.context.view_layer.update()
        if room_prefix and ob.name.startswith(room_prefix + ':'):
            # a set piece that can't clear: hidden only while it would block (and one frame round it)
            still = blockers(ob, range(1, n + 1))
            for f in range(1, n + 1):
                block = any(abs(f - b) <= 1 for b in still)
                ob.hide_render = block
                ob.keyframe_insert('hide_render', frame=f)
            ob.hide_render = False
            hidden[ob.name] = len(still)
    sc.frame_set(1)
    if log and moved:
        log('rules: slid clear of the face ' + ', '.join(moved))
    if log and hidden:
        log('rules: hid while blocking the face ' + ', '.join(f'{k} ({v} frames)' for k, v in hidden.items()))
    return moved, hidden
