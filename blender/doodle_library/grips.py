"""Real grips: every held prop touches Bunny's mitten at the right spot and can only move
the way the real object can move in a hand.

Grip kinds (Bunny has mittens, so a grip is about where the prop meets the mitten):
  fist   a handle runs through the closed fist (mic, sword, bat). Overlap is the point.
  hook   a handle or ring hangs off the fingers (mug, bag, lantern). Stays upright.
  pinch  a thin edge sits in the mitten tip, between thumb and fingers (card, pencil).
  palm   the object rests on top of the hand, fingers curled round its base (apple, cake).
  two    both hands: palms on the sides, under the base, or fists on two ends (tablet, chest).

The prop origin is the researched grip point from the 360 prop library. A socket empty is
parented to the hand bone (never to the rig file itself), the prop is parented to the socket,
and Limit Location / Limit Rotation constraints with transform limits clamp what you can do
to it with G and R in the viewport. Two-hand props switch the arms to IK and pin the IK hand
controls to the prop with constraints named 'DSL hold'; release() takes all of it away again.
"""
import math
import os

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import index

HOLD_TAG = 'DSL hold'
D = math.radians

# kind, handle axis (prop local), extra: upright (spillable/hanging), two-hand contact mode
GRIPS = {
    'apple': ('palm', 'z', 'upright'), 'banana': ('fist', 'pca', ''), 'basketball': ('two', 'x', 'side'),
    'bat': ('fist', 'z', ''), 'book': ('palm', 'z', ''), 'bowl': ('palm', 'z', 'upright'),
    'broom': ('fist', 'z', ''), 'brush': ('pinch', 'z', ''), 'bulb': ('pinch', 'z', ''),
    'burger': ('two', 'x', 'side'), 'cake': ('two', 'x', 'under'), 'calculator': ('palm', 'z', ''),
    'camera': ('two', 'x', 'side'), 'candle': ('hook', 'z', 'upright'), 'card': ('pinch', 'z', ''),
    'carrot': ('fist', 'z', ''), 'chest': ('two', 'x', 'under'), 'clipboard': ('pinch', 'x', ''),
    'controller': ('two', 'x', 'side'), 'cookie': ('pinch', 'z', ''), 'crown': ('pinch', 'z', ''),
    'cupcake': ('palm', 'z', 'upright'), 'donut': ('pinch', 'z', ''), 'drumsticks': ('fist', 'z', ''),
    'duck': ('palm', 'z', ''), 'dumbbell': ('fist', 'x', ''), 'envelope': ('pinch', 'x', ''),
    'flashlight': ('fist', 'z', ''), 'flask': ('fist', 'z', 'upright'), 'flower': ('pinch', 'z', ''),
    'fork': ('pinch', 'z', ''), 'frisbee': ('pinch', 'x', ''), 'gift': ('two', 'x', 'side'),
    'glass': ('fist', 'z', 'upright'), 'globe': ('palm', 'z', 'upright'), 'guitar': ('two', 'x', 'ends'),
    'hammer': ('fist', 'z', ''), 'headphones': ('fist', 'pca', ''), 'hourglass': ('fist', 'z', 'upright'),
    'icecream': ('fist', 'z', 'upright'), 'lantern': ('hook', 'x', 'upright'), 'laptop': ('two', 'x', 'under'),
    'letter': ('two', 'x', 'top'), 'lollipop': ('fist', 'z', ''), 'magnifier': ('fist', 'z', ''),
    'maracas': ('fist', 'z', ''), 'medal': ('hook', 'x', 'upright'), 'mic': ('fist', 'z', ''),
    'money': ('pinch', 'x', ''), 'mug': ('hook', 'z', 'upright'), 'newspaper': ('two', 'x', 'side'),
    'paddle': ('fist', 'z', ''), 'palette': ('palm', 'z', ''), 'pan': ('fist', 'x', ''),
    'partyhat': ('pinch', 'z', ''), 'pencil': ('pinch', 'z', ''), 'pizza': ('pinch', 'z', ''),
    'plant': ('palm', 'z', 'upright'), 'popcorn': ('hook', 'y', 'upright'), 'popper': ('fist', 'z', ''),
    'potion': ('palm', 'z', 'upright'), 'quill': ('pinch', 'z', ''), 'racket': ('fist', 'z', ''),
    'remote': ('fist', 'z', ''), 'ruler': ('pinch', 'x', ''), 'scissors': ('fist', 'pca', ''),
    'screwdriver': ('fist', 'z', ''), 'scroll': ('two', 'x', 'ends'), 'selfie': ('fist', 'z', ''),
    'shield': ('fist', 'pca', ''), 'shoppingbag': ('hook', 'x', 'upright'), 'shovel': ('fist', 'x', ''),
    'sign': ('fist', 'z', ''), 'skateboard': ('pinch', 'y', ''), 'spatula': ('fist', 'z', ''),
    'suitcase': ('hook', 'x', 'upright'), 'sword': ('fist', 'z', ''), 'tablet': ('two', 'x', 'side'),
    'tambourine': ('pinch', 'z', ''), 'teacup': ('palm', 'z', 'upright'), 'teddy': ('palm', 'z', ''),
    'telescope': ('fist', 'z', ''), 'testtube': ('fist', 'z', 'upright'), 'toothbrush': ('fist', 'z', ''),
    'torch': ('fist', 'z', 'upright'), 'trumpet': ('fist', 'x', ''), 'wallet': ('pinch', 'z', ''),
    'wand': ('fist', 'z', ''), 'watch': ('hook', 'z', 'upright'), 'wrench': ('fist', 'z', ''),
}

# how far you may push a held prop with G / R, per kind: (twist about the handle, other tilts,
# slide along the handle (fraction of the handle length beyond the hand), sideways slack in m)
LIMITS = {
    'fist': (35, 6, 1.0, 0.004),
    'hook': (30, 10, 0.0, 0.003),
    'pinch': (25, 6, 0.0, 0.008),
    'palm': (180, 4, 0.0, 0.012),
    'two': (20, 4, 0.0, 0.03),
}
BODY_PARTS = ('BUNNY_head', 'BUNNY_hood', 'BUNNY_shirt', 'BUNNY_pelvis', 'BUNNY_leg.L', 'BUNNY_leg.R',
              'BUNNY_neck')
WEARABLE = ('glove', 'mitten', 'oven-mitt', 'boxing', 'puppet')  # worn over the hand (user rule)
AXES = {'x': Vector((1, 0, 0)), 'y': Vector((0, 1, 0)), 'z': Vector((0, 0, 1))}


def spec(ob_or_id):
    pid = ob_or_id if isinstance(ob_or_id, str) else ob_or_id.get('dsl_id', '')
    key = pid[5:] if pid.startswith('prop-') else pid
    if any(w in key for w in WEARABLE):
        kind, axis, extra = 'wear', 'z', ''
    elif key in GRIPS:
        kind, axis, extra = GRIPS[key]
    else:  # your own props: guess from the shape
        kind, axis, extra = _guess(ob_or_id) if not isinstance(ob_or_id, str) else ('fist', 'z', '')
    return {'kind': kind, 'axis': axis, 'upright': extra == 'upright',
            'contact': extra if kind == 'two' else '', 'id': pid}


def _guess(ob):
    d = ob.dimensions
    s = sorted(d)
    if s[0] < 0.02 and s[1] > 0.06:
        return 'pinch', 'z', ''
    if max(d) > 0.3 and s[1] > 0.15:
        return 'two', 'x', 'side'
    if d.z < 0.2 and s[0] > 0.06:
        return 'palm', 'z', 'upright'
    return 'fist', 'z', ''


# ---------------------------------------------------------------- Bunny's mitten
def rig():
    return bpy.data.objects.get('BUNNY_rig')


def _hand_bone(side):
    arm = rig()
    for n in ('DEF-hand.' + side, 'hand_fk.' + side):
        if arm and n in arm.pose.bones:
            return n
    return None


def _mesh_points(ob, skip_ink=True):
    """Evaluated vertex positions (world) without the ink hull."""
    mods = [m for m in ob.modifiers if m.type == 'NODES' and m.show_viewport] if skip_ink else []
    for m in mods:
        m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world.copy()
    pts = [mw @ v.co for v in me.vertices]
    tris = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    for m in mods:
        m.show_viewport = True
    return pts, tris


def hand_frame(side='R'):
    """The mitten in hand-bone space: centre, length/palm/width axes and half sizes.

    Computed from the mesh each time, so it follows whatever rig version is loaded.
    The palm is the side that faces the body in the rest pose."""
    arm = rig()
    bone = _hand_bone(side)
    hob = bpy.data.objects.get('BUNNY_hand.' + side)
    if not (arm and bone and hob):
        raise RuntimeError('Bunny (BUNNY_rig with BUNNY_hand.%s) is not in this file.' % side)
    old = arm.data.pose_position
    arm.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    B = arm.matrix_world @ arm.pose.bones[bone].matrix
    Bi = B.inverted()
    pts, _ = _mesh_points(hob)
    local = [Bi @ p for p in pts]
    root = arm.matrix_world @ arm.pose.bones['root'].matrix
    centre_world = sum(pts, Vector()) / len(pts)
    mid = root.inverted() @ centre_world
    mid.x = 0.0  # body centre line, at the hand's own height and depth
    medial_world = (root @ mid) - centre_world
    arm.data.pose_position = old
    bpy.context.view_layer.update()

    C = sum(local, Vector()) / len(local)
    # principal axes
    cov = [[0.0] * 3 for _ in range(3)]
    for p in local:
        d = p - C
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]
    L = _largest_eigen(cov)
    if sum(((p - C).dot(L) for p in local), 0.0) < 0 or (C.dot(L) < 0):
        L = -L
    N = (Bi.to_3x3() @ medial_world)
    N = (N - L * N.dot(L)).normalized()
    W = L.cross(N).normalized()

    def half(ax):
        v = [(p - C).dot(ax) for p in local]
        return (max(v) - min(v)) / 2, (max(v) + min(v)) / 2

    hl, ol = half(L)
    ht, ot = half(N)
    hw, ow = half(W)
    C = C + L * ol + N * ot + W * ow  # box centre
    return {'C': C, 'L': L, 'N': N, 'W': W, 'hl': hl, 'ht': ht, 'hw': hw, 'bone': bone, 'side': side}


def _largest_eigen(m):
    v = Vector((0.3, 0.5, 0.8))
    M = Matrix(m)
    for _ in range(60):
        v = (M @ v).normalized()
    return v


def _frame_matrix(L, N, W, origin):
    """Bone-space matrix whose columns are (W, L, N): x across the knuckles, y to the
    fingertips, z out of the palm."""
    R = Matrix((W, L, N)).transposed()
    return Matrix.Translation(origin) @ R.to_4x4()


# ---------------------------------------------------------------- prop geometry
def _prop_local_points(ob):
    me = ob.data
    return [v.co.copy() for v in me.vertices]


def _handle_axis(ob, axis):
    if axis in AXES:
        return AXES[axis].copy()
    pts = [p for p in _prop_local_points(ob) if p.length < 0.035] or _prop_local_points(ob)
    C = sum(pts, Vector()) / len(pts)
    cov = [[sum((p - C)[i] * (p - C)[j] for p in pts) for j in range(3)] for i in range(3)]
    return _largest_eigen(cov)


def _handle_span(ob, A):
    """How far the prop runs either way along its handle axis from the grip origin."""
    v = [p.dot(A) for p in _prop_local_points(ob)]
    return min(v), max(v)


# ---------------------------------------------------------------- attach / release
def release(ob):
    """Let go: the prop stays where it is in the world; IK pins and limits go away."""
    mw = ob.matrix_world.copy()
    sock = ob.parent if ob.parent and ob.parent.get('dsl_socket') else None
    for c in [c for c in ob.constraints if c.name.startswith(HOLD_TAG) or c.name == 'Held by Bunny']:
        ob.constraints.remove(c)
    ob.parent = None
    ob.matrix_world = mw
    if sock:
        bpy.data.objects.remove(sock)
    arm = rig()
    if arm:
        for pb in arm.pose.bones:
            for c in [c for c in pb.constraints if c.name.startswith(HOLD_TAG) and c.target == ob]:
                pb.constraints.remove(c)
    for k in ('dsl_held_side', 'dsl_grip_kind', 'dsl_holder', 'dsl_contact'):
        if k in ob:
            del ob[k]


def _socket(name, arm, bone, matrix_world):
    s = bpy.data.objects.new(name, None)
    s.empty_display_type = 'ARROWS'
    s.empty_display_size = 0.04
    s['dsl_socket'] = True
    s.hide_render = True
    coll = bpy.data.collections.get('Doodle Library') or bpy.context.scene.collection
    coll.objects.link(s)
    s.parent = arm
    s.parent_type = 'BONE'
    s.parent_bone = bone
    bpy.context.view_layer.update()
    s.matrix_world = matrix_world
    return s


def _limits(ob, kind, A, slide, upright, lean=0.0):
    """Clamp G/R on the prop to what the real grip allows (local to the socket)."""
    twist, tilt, _, slack = LIMITS[kind]
    lo = ob.constraints.new('LIMIT_LOCATION')
    lo.name = HOLD_TAG + ' reach'
    lo.owner_space = 'LOCAL'
    lo.use_transform_limit = True
    ax = max(range(3), key=lambda i: abs(A[i]))
    for i, a in enumerate('xyz'):
        mn, mx = (-slack, slack)
        if i == ax and slide:
            mn, mx = slide
        if kind == 'palm' and a == 'z':
            mn, mx = 0.0, 0.0  # stays on the palm
        setattr(lo, 'use_min_' + a, True)
        setattr(lo, 'use_max_' + a, True)
        setattr(lo, 'min_' + a, mn)
        setattr(lo, 'max_' + a, mx)
    ro = ob.constraints.new('LIMIT_ROTATION')
    ro.name = HOLD_TAG + ' twist'
    ro.owner_space = 'LOCAL'
    ro.use_transform_limit = True
    for i, a in enumerate('xyz'):
        lim = D(twist if i == ax else tilt)
        setattr(ro, 'use_limit_' + a, True)
        setattr(ro, 'min_' + a, -lim)
        setattr(ro, 'max_' + a, lim)
    if upright:
        up = ob.constraints.new('LIMIT_ROTATION')
        up.name = HOLD_TAG + ' upright'
        up.owner_space = 'WORLD'
        tilt_max = max(12.0, abs(lean) + 8.0)  # the lean chosen to clear his head is allowed
        for a in 'xy':
            setattr(up, 'use_limit_' + a, True)
            setattr(up, 'min_' + a, D(-tilt_max))
            setattr(up, 'max_' + a, D(tilt_max))


# ---------------------------------------------------------------- body + reach
class Body:
    """Every character body in the file (Bunny, Koala, Frog ...) for clip tests. The holding
    hand, its cuff and forearm sleeve are left out: they are meant to touch the prop."""

    def __init__(self, sides=('R',), holder='BUNNY'):
        from . import collide
        self._b = collide.Bodies(exclude=collide.holder_parts(holder, sides))

    def clips(self, pts):
        return self._b.count(pts)


def _root():
    arm = rig()
    return arm.matrix_world @ arm.pose.bones['root'].matrix


def _shoulder(side):
    arm = rig()
    for n in ('DEF-upper_arm.' + side, 'upper_arm_fk.' + side):
        if n in arm.pose.bones:
            return arm.matrix_world @ arm.pose.bones[n].head
    raise RuntimeError('No upper arm bone for side ' + side)


def _reach(side):
    arm = rig()
    tot = 0.0
    for n in ('DEF-upper_arm.', 'DEF-forearm.'):
        pb = arm.pose.bones.get(n + side)
        tot += pb.length if pb else 0.0
    return tot


def _mitten_rot(hf, W, L, N):
    """World-from-bone rotation that puts the mitten's (W, L, N) on the given world axes."""
    Rw = Matrix((W, L, N)).transposed()
    Rb = Matrix((hf['W'], hf['L'], hf['N'])).transposed()
    return Rw @ Rb.inverted()


def _hand_axes(kind, side, R, A_local, pts_local):
    """World axes (W, L, N) for the mitten, given the prop's world rotation R."""
    root = _root().to_3x3().normalized()
    out = root @ Vector((1 if side == 'R' else -1, 0, 0))
    fwd = root @ Vector((0, -1, 0))
    up = root @ Vector((0, 0, 1))
    medial = -out
    if kind in ('fist', 'hook'):
        W = (R @ A_local).normalized()
        N = (medial - W * medial.dot(W))
        if N.length < 1e-3:
            N = fwd - W * fwd.dot(W)
        N.normalize()
        L = N.cross(W)
        if L.dot(fwd) + 0.5 * L.dot(-up) < 0:
            W, L = -W, -L
    elif kind == 'pinch':
        # palm against the flat side, fingers pointing into the prop
        ext = [max(p[i] for p in pts_local) - min(p[i] for p in pts_local) for i in range(3)]
        thin = min(range(3), key=lambda i: ext[i])
        N = (R @ Vector([1.0 if i == thin else 0.0 for i in range(3)])).normalized()
        if N.dot(medial) < 0:
            N = -N
        c = sum(pts_local, Vector()) / len(pts_local)
        L = R @ c
        L = L - N * L.dot(N)
        L = L.normalized() if L.length > 1e-4 else (fwd - N * fwd.dot(N)).normalized()
        W = L.cross(N)
    else:  # palm: palm up, fingers forward
        N = up
        L = (fwd - N * fwd.dot(N)).normalized()
        W = L.cross(N)
    return W.normalized(), L.normalized(), N.normalized()


def _grip_point(kind, hf):
    """Where the prop's grip origin sits inside/on the mitten (bone space)."""
    C, L, N = hf['C'], hf['L'], hf['N']
    if kind in ('fist', 'hook'):
        return C + L * (0.12 * hf['hl']) + N * (0.2 * hf['ht'])
    if kind == 'pinch':
        return C + L * (0.55 * hf['hl'])
    return C + N * (0.8 * hf['ht'])  # palm surface (the prop base goes here)


def _orientations(kind, upright):
    """Candidate prop turns in Bunny's body frame, best first: (yaw, lean outward) degrees.
    Spillable things may tilt a little (30 degrees), everything else up to 75."""
    yaws = (0, 180, 90, -90, 45, -45, 135, -135)
    leans = (0, 15, 30) if upright else (0, 15, 30, 45, 60, 75)
    return [(y, l) for l in leans for y in yaws]


def _sample(pts, n=400):
    if len(pts) <= n:
        return pts
    step = len(pts) / n
    return [pts[int(i * step)] for i in range(n)]


def _search(kind, side, hf, A, local, samp, upright, body, budget=5000, reach_k=0.97):
    """Find the hand spot, prop turn, lean and grip slide that keep the prop out of Bunny.

    Candidates are ranked by how natural they look (facing the camera, upright, arm relaxed,
    gripped at the researched spot) and tried in that order until one is clip-free."""
    root = _root().to_3x3().normalized()
    out = root @ Vector((1 if side == 'R' else -1, 0, 0))
    fwd = root @ Vector((0, -1, 0))
    up = root @ Vector((0, 0, 1))
    sh = _shoulder(side)
    reach = _reach(side) * reach_k
    P = _grip_point(kind, hf)
    spots = []
    for f in (0.35, 0.6, 0.15, 0.0):
        for dn in (0.55, 0.3, 0.8, 1.2):
            spots.append(sh + (out + fwd * f - up * dn).normalized() * reach)
    yaws = (0, 180, 90, -90, 45, -45, 135, -135)
    leans = (0, 15, 30, 45, 60, 75)  # upright things pay extra to tilt past 30 (see cost)
    fbs = (0, 20, -20)
    drops = (0.0,) if kind == 'palm' else (0.0, 0.3, 0.55)
    # how far the prop can slide down through the hand (hand moves up the prop)
    tops = [q.z for q in local]
    span = max(0.0, max(tops) - hf['hl'])
    cands = []
    for yi, yaw in enumerate(yaws):
        for lean in leans:
            for fb in fbs:
                for di, dr in enumerate(drops):
                    for si in range(len(spots)):
                        cost = (0 if yaw == 0 else 1.5 + yi * 0.05) + lean / 15.0 + abs(fb) / 20.0 + si * 0.4 + di * 1.2
                        if upright and lean > 30:
                            cost += 3 + (lean - 30) / 10.0  # only when nothing upright clears his head
                        cands.append((cost, yaw, lean, fb, dr, si))
    cands.sort(key=lambda c: c[0])
    best = None
    cache = {}
    for n, (cost, yaw, lean, fb, dr, si) in enumerate(cands):
        if n >= budget:
            break
        key = (yaw, lean, fb)
        if key not in cache:
            tilt = (Matrix.Rotation(math.radians(fb), 3, out) @
                    Matrix.Rotation(math.radians(-lean if side == 'R' else lean), 3, fwd))
            Rp = tilt @ Matrix.Rotation(math.radians(yaw), 3, up) @ root
            if kind == 'palm':
                Rp = Matrix.Rotation(math.radians(lean if side == 'L' else -lean), 3, fwd) @ \
                    Matrix.Rotation(math.radians(yaw), 3, up) @ root
            W, L, N = _hand_axes(kind, side, Rp, A, local)
            Rb = _mitten_rot(hf, W, L, N)
            pr = [Rp @ q for q in local]
            cache[key] = (Rp, Rb, pr, min(q.dot(up) for q in pr), [Rp @ q for q in samp])
        Rp, Rb, pr, base, ps = cache[key]
        H = spots[si]
        G = H + Rb @ P - (Rp @ Vector((0, 0, 1))) * (dr * span)
        opts = [(G, 0.0, False)]
        if kind == 'palm':
            G = G - up * (base + 0.2 * hf['ht'])  # sits on the palm, fingers 20% up the base
            opts = [(G, 0.0, False), (G + out * (0.5 * hf['hw']), 0.5, False), (G + out * (0.9 * hf['hw']), 0.9, False)]
            # or cupped against the outer side of the mitten, level with the hand
            r_out = -min(q.dot(out) for q in pr)
            cz = sum((q.dot(up) for q in pr), 0.0) / len(pr)
            opts.append((H + Rb @ hf['C'] + out * (hf['hw'] * 0.6 + r_out) - up * cz, 1.5, True))
        for Gs, extra, cup in opts:
            clip = body.clips([Gs + q for q in ps])
            score = clip * 10 + cost + extra
            if best is None or score < best['score']:
                best = dict(score=score, clip=clip, Rp=Rp, Rb=Rb, H=H, G=Gs, yaw=yaw, lean=lean, fb=fb,
                            drop=dr * span, kind=kind, base=base, cup=cup, hand_offset=Gs - H)
        if best['clip'] == 0:
            return best
    return best


def attach(ob, side=None, pose=True, frame=None, check=True, force_kind=None):
    """Hold `ob`, then look again from the pose the arm ended in: moving the arm moves his
    sleeve, so a spot that was clear before the arm moved can be blocked after. Up to three
    looks; the cleanest one is kept."""
    arm = rig()
    start = _arm_pose(arm) if arm else None
    rep = _attach_once(ob, side, pose, frame, check, force_kind)
    if not check or rep.get('ok') or rep.get('kind') in ('two', 'wear') or rep.get('note'):
        return rep
    best = (_badness(rep), start)
    for _ in range(2):
        start = _arm_pose(arm)
        rep = _attach_once(ob, side, pose, frame, check, force_kind)
        if rep.get('ok'):
            return rep
        if _badness(rep) < best[0]:
            best = (_badness(rep), start)
    if _badness(rep) > best[0]:  # go back to the cleanest look: same arm pose in, same answer out
        _arm_pose(arm, best[1])
        rep = _attach_once(ob, side, pose, frame, check, force_kind)
    return rep


def _badness(rep):
    return (0 if rep.get('touch', True) else 100) + rep.get('stray_mm', 0) + rep.get('clip_mm', 0)


def _arm_pose(arm, pose=None):
    """Read (or put back) the pose of every bone: a snapshot to retry a grip from."""
    if pose is None:
        return {pb.name: (pb.location.copy(), pb.rotation_quaternion.copy(), pb.rotation_euler.copy())
                for pb in arm.pose.bones}
    for pb in arm.pose.bones:
        if pb.name in pose:
            pb.location, pb.rotation_quaternion, pb.rotation_euler = pose[pb.name]
    bpy.context.view_layer.update()


def _attach_once(ob, side=None, pose=True, frame=None, check=True, force_kind=None):
    """Hold `ob` properly. Returns a report dict (kind, side, contact result).

    One hand: the arm switches to IK and carries at the side (Bunny's arms are short and
    his head overhangs his body, so the side is the only place a prop stays visible and clear).
    The prop's turn and outward lean are searched so nothing cuts into his head or body.
    A palm hold that can't clear his head becomes a cupped (fist) hold."""
    release(ob)
    sp = spec(ob)
    item = index.get(ob.get('dsl_id', '')) or {}
    hold = (item.get('data') or {}).get('hold') or {}
    side = side or ('L' if hold.get('attach') == 'armL' else 'R')
    sc = bpy.context.scene
    frame = sc.frame_current if frame is None else frame
    arm = rig()
    if arm is None:
        raise RuntimeError('Bunny (BUNNY_rig) is not in this file.')
    if force_kind:
        sp = dict(sp, kind=force_kind, axis='x' if sp.get('contact') == 'ends' else 'z')
    if sp['kind'] == 'two':
        rep = _attach_two(ob, sp, frame, check)
        if rep.get('ok', True) or rep.get('gap_mm', 0) <= 3:
            return rep
        # his arms are too short to reach round it: carry it in one hand at his side instead
        alt_kind = 'fist' if sp['contact'] == 'ends' else 'palm'
        rep2 = _attach_once(ob, side='R', pose=pose, frame=frame, check=check, force_kind=alt_kind)
        rep2['note'] = 'too big for both of his short arms, so he carries it in one hand'
        if not rep2.get('ok'):
            return rep2
        return rep2
    if sp['kind'] == 'wear':
        return wear(ob, side)
    hf = hand_frame(side)
    scale = ob.matrix_world.to_scale()[0]
    A = _handle_axis(ob, sp['axis'])
    local = [p * scale for p in _prop_local_points(ob)]
    samp = _sample(local, 600)
    body = Body((side,))
    best = _search(sp['kind'], side, hf, A, local, samp, sp['upright'], body)
    if best['clip'] and sp['kind'] == 'palm':
        alt = _search('fist', side, hf, AXES['z'], local, samp, sp['upright'], body)
        if alt['clip'] < best['clip']:
            best = alt
    kind, Rp, Rb, H = best['kind'], best['Rp'], best['Rb'], best['H']
    if os.environ.get('DSL_DEBUG'):
        print('GRIPDBG search', ob.name, 'clip', best['clip'], 'yaw', best['yaw'], 'lean', best['lean'], 'kind', kind)
    _set_ik(arm, side, 1.0, frame)
    for k in (0.9, 0.82, 0.74):
        _pose_ik_hand(arm, side, hf, Matrix.Translation(H) @ Rb.to_4x4(), frame)
        B = arm.matrix_world @ arm.pose.bones[hf['bone']].matrix
        if (B.translation - H).length < 0.003:
            break
        # the arm couldn't reach that spot: search again inside a shorter reach
        best = _search(kind if kind != 'fist' or sp['kind'] != 'palm' else 'fist', side, hf,
                       A if best['kind'] == sp['kind'] else AXES['z'], local, samp, sp['upright'], body, reach_k=k)
        kind, Rp, Rb, H = best['kind'], best['Rp'], best['Rb'], best['H']
    # the IK may land a hair off: put the prop on the real hand (same offset in hand space)
    B = arm.matrix_world @ arm.pose.bones[hf['bone']].matrix
    Bw = Matrix.Translation(H) @ Rb.to_4x4()
    G = B @ (Bw.inverted() @ best['G'])
    Rp = (B.to_3x3().normalized() @ Rb.inverted()) @ Rp
    ob.matrix_world = Matrix.Translation(G) @ Rp.to_4x4() @ Matrix.Scale(scale, 4)
    bpy.context.view_layer.update()
    if os.environ.get('DSL_DEBUG'):
        from .grips import _mesh_points as _mp
        print('GRIPDBG placed clip', body.clips(_sample(_mp(ob)[0], 1500)), 'Bdiff', (B.translation - H).length,
              'predicted', body.clips([best['G'] + best['Rp'] @ q for q in samp]))
    # remember which part of the prop is meant to be in the hand (checked every frame)
    if best.get('cup'):
        root3 = _root().to_3x3().normalized()
        out = root3 @ Vector((1 if side == 'R' else -1, 0, 0))
        contact = B @ hf['C'] + out * (hf['hw'] * 0.6)
    else:
        contact = B @ _grip_point(kind, hf)
        if best.get('drop'):
            contact = contact  # the hand point; the prop slid down through it
    ob['dsl_contact'] = list(ob.matrix_world.inverted() @ contact)
    sock = _socket('%s grip' % ob.name, arm, hf['bone'], ob.matrix_world.normalized())
    mw = ob.matrix_world.copy()
    ob.parent = sock
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_world = mw
    slide = None
    if kind == 'fist':
        lo, hi = _handle_span(ob, A)
        hand_w = hf['hw'] * 2 / scale
        slide = (min(0.0, -(hi - hand_w) * 0.35 * scale), max(0.0, (-lo - hand_w) * 0.35 * scale))
    _limits(ob, kind, A, slide, sp['upright'], lean=best['lean'] + abs(best.get('fb', 0)))
    ob['dsl_held_side'] = side
    ob['dsl_grip_kind'] = kind
    ob['dsl_holder'] = arm.name[:-4] if arm.name.endswith('_rig') else 'BUNNY'
    rep = {'prop': ob.name, 'kind': kind, 'side': side, 'turn': best['yaw'], 'lean': best['lean'],
           'slide_mm': round(best['drop'] * 1000)}
    if check:
        settle(ob, side)
        from . import collide
        keep = ob.matrix_basis.copy()
        collide.resolve(ob)  # the IK may land a hair off the searched spot: turn it clear in-grip
        if not check_contact(ob, body=False)['touch']:
            ob.matrix_basis = keep  # never trade the grip for clearance
            bpy.context.view_layer.update()
        rep.update(check_contact(ob))
    return rep


def wear(ob, side='R'):
    """Gloves and mittens go OVER the hand: fitted to the mitten (8% bigger all round),
    centred on it and following it. Worn items may enclose the hand; nothing else may."""
    release(ob)
    arm = rig()
    hf = hand_frame(side)
    B = arm.matrix_world @ arm.pose.bones[hf['bone']].matrix
    pts = _prop_local_points(ob)
    mn = Vector([min(p[i] for p in pts) for i in range(3)])
    mx = Vector([max(p[i] for p in pts) for i in range(3)])
    size = mx - mn
    # the glove's longest side runs along the mitten's length, its thinnest through the palm
    order = sorted(range(3), key=lambda i: size[i])
    want = {order[2]: hf['hl'] * 2, order[1]: hf['hw'] * 2, order[0]: hf['ht'] * 2}
    S = Matrix.Diagonal([want[i] * 1.08 / max(size[i], 1e-6) for i in range(3)]).to_4x4()
    axes = {order[2]: hf['L'], order[1]: hf['W'], order[0]: hf['N']}
    R = Matrix((axes[0], axes[1], axes[2])).transposed()
    if R.determinant() < 0:
        R = Matrix((axes[0], axes[1], -axes[2])).transposed()
    centre = (mn + mx) / 2
    local = Matrix.Translation(hf['C']) @ R.to_4x4() @ S @ Matrix.Translation(-centre)
    sock = _socket('%s worn' % ob.name, arm, hf['bone'], B @ Matrix.Translation(hf['C']))
    ob.parent = sock
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_world = B @ local
    ob['dsl_held_side'] = side
    ob['dsl_grip_kind'] = 'wear'
    ob['dsl_holder'] = arm.name[:-4] if arm.name.endswith('_rig') else 'BUNNY'
    return {'prop': ob.name, 'kind': 'wear', 'side': side, 'ok': True, 'touch': True}


def _set_prop(owner, path, value):
    try:
        owner[path] = value
        return True
    except Exception:
        return False


def _arm_ik_owner(arm):
    """The ID that holds arm_ik.L/R (it drives the IK constraints)."""
    ad = arm.animation_data
    for d in (ad.drivers if ad else []):
        if 'MCH-hand_target' in d.data_path:
            for v in d.driver.variables:
                t = v.targets[0]
                if 'arm_ik' in t.data_path:
                    return t.id or arm, t.data_path
    return arm, None


def _set_ik(arm, side, value, frame):
    owner, _ = _arm_ik_owner(arm)
    prop = 'arm_ik.' + side
    if _set_prop(owner, prop, value):
        try:
            owner.keyframe_insert('["%s"]' % prop, frame=frame)
        except Exception:
            pass
    bpy.context.view_layer.update()


def _pose_ik_hand(arm, side, hf, want, frame):
    """Move hand_ik.<side> so the deforming hand bone ends up at `want` (world)."""
    pb = arm.pose.bones.get('hand_ik.' + side)
    if not pb:
        return
    def_bone = arm.pose.bones[hf['bone']]
    target = want.copy()
    for _ in range(6):
        pb.matrix = arm.matrix_world.inverted() @ target
        bpy.context.view_layer.update()
        got = arm.matrix_world @ def_bone.matrix
        err = want.translation - got.translation
        rerr = want.to_3x3().normalized() @ got.to_3x3().normalized().inverted()
        ang = rerr.to_quaternion().angle
        if err.length < 0.001 and ang < 0.01:
            break
        # the DEF hand may sit at an offset from the IK control: correct turn, then place
        R = rerr @ target.to_3x3().normalized()
        target = Matrix.Translation(target.translation + err) @ R.to_4x4()
    rp = {'QUATERNION': 'rotation_quaternion', 'AXIS_ANGLE': 'rotation_axis_angle'}.get(pb.rotation_mode, 'rotation_euler')
    pb.keyframe_insert('location', frame=frame, group=pb.name)
    pb.keyframe_insert(rp, frame=frame, group=pb.name)


# ---------------------------------------------------------------- two hands
def _attach_two(ob, sp, frame, check):
    """Both hands. The prop rests against his tummy (his arms can't reach further) and is
    lowered or moved until it clears his head; the IK hands sit on its sides or under it."""
    arm = rig()
    hR, hL = hand_frame('R'), hand_frame('L')
    scale = ob.matrix_world.to_scale()[0]
    local = [p * scale for p in _prop_local_points(ob)]
    samp = _sample(local, 1500)
    root = _root()
    R0 = root.to_3x3().normalized()
    fwd = R0 @ Vector((0, -1, 0))
    up = R0 @ Vector((0, 0, 1))
    body = Body(('L', 'R'))
    shirt = bpy.data.objects.get('BUNNY_shirt')
    spts, _ = _mesh_points(shirt) if shirt else ([root.translation], None)
    front = min((root.inverted() @ p).y for p in spts)  # shirt front, body frame
    xs, ys, zs = ([p[i] for p in local] for i in range(3))
    xmin, xmax, ymin, ymax, zmin, zmax = min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)
    w = xmax - xmin
    yb = ymax - min(0.3 * (ymax - ymin), 0.03)   # hands near the back edge: his arms are short
    zc = (zmin + zmax) / 2
    mode = sp['contact']
    if mode == 'under':  # palms under the back rim, next to his tummy: his arms are short
        cl, cr = Vector((xmin + 0.12 * w, yb, zmin)), Vector((xmax - 0.12 * w, yb, zmin))
        nl = nr = Vector((0, 0, -1))
    elif mode == 'top':
        cl, cr = Vector((xmin + 0.04 * w, yb, zmax - 0.02)), Vector((xmax - 0.04 * w, yb, zmax - 0.02))
        nl, nr = Vector((-1, 0, 0)), Vector((1, 0, 0))
    elif mode == 'ends':
        cl, cr = Vector((xmin + 0.05 * w, yb, zc)), Vector((xmax - 0.05 * w, yb, zc))
        nl, nr = Vector((-1, 0, 0)), Vector((1, 0, 0))
    else:
        cl, cr = Vector((xmin, yb, zc)), Vector((xmax, yb, zc))
        nl, nr = Vector((-1, 0, 0)), Vector((1, 0, 0))
    # side and end grips may sit higher up the prop, so it hangs lower, clear of his head
    fracs = (0.5, 0.7, 0.85) if mode in ('side', 'ends') else (None,)
    shR, shL = _shoulder('R'), _shoulder('L')
    reach = _reach('R') * 0.97

    def hand_pose(M, c, n, hf):
        cw = M @ c
        nw = (M.to_3x3() @ n).normalized()
        Nm = Vector((0, 0, 1)) if mode == 'under' else -nw
        sh = shR if hf is hR else shL
        # fingers carry on from the arm (pointing away from the shoulder), so the palm reaches
        # as far as it can; under a tray they point forward
        aim = fwd if mode == 'under' else (cw - sh)
        if abs(aim.normalized().dot(Nm)) > 0.95:
            aim = -up
        L = (aim - Nm * aim.dot(Nm)).normalized()
        if mode == 'hug':
            # fingertips on the surface, pointing into it (how you hold a ball you can't wrap)
            L = -nw
            Nm = (fwd - L * fwd.dot(L))
            Nm = Nm.normalized() if Nm.length > 1e-3 else (up - L * up.dot(L)).normalized()
        W = L.cross(Nm).normalized()
        Rb = _mitten_rot(hf, W, L, Nm)
        if mode == 'hug':
            palm = hf['C'] + hf['L'] * (hf['hl'] * 0.9)
        else:
            depth = 0.8 if mode != 'ends' else 0.1
            palm = hf['C'] + hf['N'] * (hf['ht'] * depth)
        return cw - Rb @ palm, Rb

    me = ob.data
    Ml = Matrix.Scale(scale, 4)
    pbvh = BVHTree.FromPolygons([Ml @ v.co for v in me.vertices], [tuple(f.vertices) for f in me.polygons])
    outR, outL = R0 @ Vector((1, 0, 0)), R0 @ Vector((-1, 0, 0))

    def hug_contacts(M):
        """Too wide or deep for his short arms: hug it to the tummy, palms on the nearest surface."""
        Minv = M.inverted()
        res = []
        for sh, o in ((shR, outR), (shL, outL)):
            q, nrm, _, _ = pbvh.find_nearest(Minv @ (sh + (o + fwd - up * 0.5).normalized() * 0.07))
            res.append((q, nrm.normalized()))
        return res

    std_mode = mode
    best = None
    for fr in fracs:
        if fr is not None:
            zf = zmin + fr * (zmax - zmin)
            cl, cr = Vector((cl.x, cl.y, zf)), Vector((cr.x, cr.y, zf))
        for dz in [i * 0.02 for i in range(-12, 6)]:
            for gap in (0.004, 0.02, -0.015):
                # prop back face against the front of the shirt; centred; contact height near the shoulders
                off = Vector((-(cl.x + cr.x) / 2, front - gap - ymax, 0))
                zbase = (root.inverted() @ ((shR + shL) / 2)).z - 0.05 + dz
                off.z = zbase - (cl.z + cr.z) / 2
                M = root @ Matrix.Translation(off)
                opts = [(std_mode, cl, cr, nl, nr, 0.0)]
                (hcr, hnr), (hcl, hnl) = hug_contacts(M)
                opts.append(('hug', hcl, hcr, hnl, hnr, 1.0))
                clip = None
                for md, a_l, a_r, n_l, n_r, pen in opts:
                    mode = md
                    HR, _ = hand_pose(M, a_r, n_r, hR)
                    HL, _ = hand_pose(M, a_l, n_l, hL)
                    short = max(0.0, (HR - shR).length - reach) + max(0.0, (HL - shL).length - reach)
                    if best is not None and short * 400 + pen > best[0]:
                        continue
                    if clip is None:
                        clip = body.clips([M @ q for q in samp])
                    score = (clip * 10 + short * 400 + abs(dz) * 5 + (abs(gap) * 20 if gap > 0 else 3) +
                             (fr or 0.5) - 0.5 + pen)
                    if best is None or score < best[0]:
                        best = (score, M, clip, short, a_l.copy(), a_r.copy(), n_l.copy(), n_r.copy(), md)
    _, M, clip, short, cl, cr, nl, nr, mode = best
    ob.matrix_world = M @ Matrix.Scale(scale, 4)
    bpy.context.view_layer.update()
    for it in range(4):
        errs = []
        for side, c, n, hf in (('R', cr, nr, hR), ('L', cl, nl, hL)):
            H, Rb = hand_pose(M, c, n, hf)
            _set_ik(arm, side, 1.0, frame)
            _pose_ik_hand(arm, side, hf, Matrix.Translation(H) @ Rb.to_4x4(), frame)
            tip = hf['C'] + hf['L'] * (hf['hl'] * 0.9) if mode == 'hug' else \
                hf['C'] + hf['N'] * hf['ht'] * (0.8 if mode != 'ends' else 0.1)
            got = (arm.matrix_world @ arm.pose.bones[hf['bone']].matrix) @ tip
            errs.append(got - M @ c)
            if os.environ.get('DSL_DEBUG'):
                sh = shR if side == 'R' else shL
                print('GRIPDBG two', side, mode, 'err mm', round((got - M @ c).length * 1000, 1), 'H-sh', round((H - sh).length, 3),
                      'reach', round(reach, 3), 'ik', round(((arm.matrix_world @ arm.pose.bones['hand_ik.' + side].matrix).translation - H).length * 1000, 1),
                      'def', round(((arm.matrix_world @ arm.pose.bones[hf['bone']].matrix).translation - H).length * 1000, 1))
        e = (errs[0] + errs[1]) / 2
        e.x = 0.0  # stay centred on his body
        if max(x.length for x in errs) < 0.004 or it == 3:
            break
        # arms fall short: bring the prop to the hands (it may press into the hoodie a little),
        # but never up into his head
        moved = None
        for step in (e, Vector((e.x, e.y, min(e.z, 0.0))), Vector((e.x, e.y, 0.0))):
            M2 = Matrix.Translation(step) @ M
            if body.clips([M2 @ q for q in samp]) <= clip:
                moved = M2
                break
        if moved is None:
            break
        M = moved
        ob.matrix_world = M @ Matrix.Scale(scale, 4)
        bpy.context.view_layer.update()
    tor = 'torso' if 'torso' in arm.pose.bones else 'body'
    c = ob.constraints.new('CHILD_OF')
    c.name = HOLD_TAG + ' carry'
    c.target = arm
    c.subtarget = tor
    bpy.context.view_layer.update()
    c.inverse_matrix = (arm.matrix_world @ arm.pose.bones[tor].matrix).inverted()
    for side in 'RL':
        pb = arm.pose.bones.get('hand_ik.' + side)
        if not pb:
            continue
        cc = pb.constraints.new('CHILD_OF')
        cc.name = HOLD_TAG + ' hand'
        cc.target = ob
        bpy.context.view_layer.update()
        cc.inverse_matrix = ob.matrix_world.inverted()
    ob['dsl_held_side'] = 'both'
    ob['dsl_grip_kind'] = 'two'
    ob['dsl_holder'] = arm.name[:-4] if arm.name.endswith('_rig') else 'BUNNY'
    rep = {'prop': ob.name, 'kind': 'two', 'side': 'both', 'contact': mode}
    ob['dsl_contact_mode'] = mode
    if check:
        from . import collide
        collide.resolve(ob)
        rep.update(check_contact(ob))
    return rep


# ---------------------------------------------------------------- contact check
def _bvh(ob):
    pts, tris = _mesh_points(ob)
    return BVHTree.FromPolygons(pts, tris), pts


_DIRS = (Vector((0.577, 0.577, 0.577)), Vector((-0.6, 0.3, -0.742)))


def _inside(bvh, p, far=10.0):
    """Point-in-mesh by ray parity (robust to flipped normals); both rays must agree."""
    votes = 0
    for d in _DIRS:
        n, o = 0, p.copy()
        for _ in range(64):
            loc, _, _, _ = bvh.ray_cast(o, d, far)
            if loc is None:
                break
            n += 1
            o = loc + d * 1e-5
        votes += n % 2
    return votes == 2, 0.0


def check_contact(ob, body=True):
    """Does the prop really touch the hand(s), overlap only round the grip, and stay out of Bunny?

    touch      the prop overlaps the mitten or is within 3 mm of it
    stray_mm   how far from the grip point the deepest overlap reaches beyond 6 cm (0 = fine)
    body_clip  prop points inside Bunny's head, hood, shirt, pelvis or legs"""
    kind = ob.get('dsl_grip_kind', '')
    side = ob.get('dsl_held_side', 'R')
    sides = ['L', 'R'] if side == 'both' else [side]
    pbvh, ppts = _bvh(ob)
    grip = ob.matrix_world @ Vector(ob.get('dsl_contact', (0, 0, 0)))
    res = {'touch': True, 'gap_mm': 0.0, 'stray_mm': 0.0, 'body_clip': 0}
    for sd in sides:
        hbvh, hpts = _bvh(bpy.data.objects.get('BUNNY_hand.' + sd))
        overlap = bool(pbvh.overlap(hbvh))
        gap = 0.0 if overlap else min(pbvh.find_nearest(p)[3] for p in hpts)
        if gap > 0.003:
            res['touch'] = False
            res['gap_mm'] = max(res['gap_mm'], round(gap * 1000, 1))
        if kind != 'two' and overlap:
            far = [(p - grip).length for p in ppts if _inside(hbvh, p)[0]]
            if far and max(far) > 0.06:
                res['stray_mm'] = round((max(far) - 0.06) * 1000, 1)
    if body:
        from . import collide
        from .collide import holder_parts
        bods = collide.Bodies(exclude=holder_parts(ob.get('dsl_holder', 'BUNNY'), tuple(sides)))
        hits = bods.inside(_sample(ppts, 1500))
        res['body_clip'] = len(hits)
        res['clip_mm'] = round(max(((h[1] - h[0]).length for h in hits), default=0.0) * 1000, 1)
    # a graze under 3 mm sits inside the ink line (a stroke is ~6 mm at this size): not visible
    res['ok'] = res['touch'] and not res['stray_mm'] and res.get('clip_mm', 0.0) <= 3.0
    return res


def settle(ob, side):
    """If the prop floats off the mitten, slide it along the grip direction until it touches."""
    res = check_contact(ob, body=False)
    if res['touch']:
        return check_contact(ob)
    hob = bpy.data.objects.get('BUNNY_hand.' + side)
    hpts, _ = _mesh_points(hob)
    hc = sum(hpts, Vector()) / len(hpts)
    start = ob.matrix_world.translation.copy()
    d = hc - start
    lo, hi = 0.0, 1.0
    for _ in range(12):
        mid = (lo + hi) / 2
        _move_world(ob, start + d * mid)
        if check_contact(ob, body=False)['touch']:
            hi = mid
        else:
            lo = mid
    _move_world(ob, start + d * hi)
    res = check_contact(ob)
    res['settled_mm'] = round(d.length * hi * 1000, 1)
    # bake the new spot into the socket so the limits stay centred on it
    sock = ob.parent
    if sock and sock.get('dsl_socket'):
        mw = ob.matrix_world.copy()
        sock.matrix_world = Matrix.Translation(mw.translation) @ sock.matrix_world.to_3x3().to_4x4()
        bpy.context.view_layer.update()
        ob.matrix_world = mw
    return res


def _move_world(ob, p):
    mw = ob.matrix_world.copy()
    mw.translation = p
    ob.matrix_world = mw
    bpy.context.view_layer.update()


def check_range(ob, frames):
    """Contact report over a frame range (use after keying a motion)."""
    sc = bpy.context.scene
    cur = sc.frame_current
    bad = []
    for f in frames:
        sc.frame_set(f)
        r = check_contact(ob)
        if not r['ok']:
            bad.append((f, r))
    sc.frame_set(cur)
    return bad


def describe(r):
    if r.get('note') and r.get('ok', True):
        return '%s grip: %s, touching the hand, no clipping' % (r.get('kind', ''), r['note'])
    if r.get('kind') == 'wear':
        return 'Worn over the %s hand' % ('left' if r.get('side') == 'L' else 'right')
    if r.get('ok', True) and r.get('touch', True):
        s = '%s grip: touching the hand, no clipping' % r.get('kind', ob_kind(r))
        if r.get('settled_mm'):
            s += ' (moved %.0f mm onto the mitten)' % r['settled_mm']
        return s
    bits = []
    if not r.get('touch', True):
        bits.append('%.0f mm off the hand' % r.get('gap_mm', 0))
    if r.get('stray_mm'):
        bits.append('overlaps the hand %.0f mm away from the grip' % r['stray_mm'])
    if r.get('clip_mm', 0) > 3.0:
        bits.append('goes %.0f mm into a body' % r['clip_mm'])
    return '%s grip: ' % r.get('kind', '') + ', '.join(bits)


def ob_kind(r):
    return r.get('kind', '')
