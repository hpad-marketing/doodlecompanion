"""Keep a heavy droid balanced the way a real biped has to (physics audit, 2026-11-06).
The ZMP is the point where the floor has to push so the body doesn't tip: the centre of mass shifted against its
acceleration (CoM - height x acceleration / g). It must stay inside what the feet stand on. Two fixes, both made by
moving only the body (COG bone) and solved as an inverted pendulum (least squares, smooth):
  - side to side (x), walks: while one foot is up the ZMP must sit over the planted foot, so the body sways over it
    (target = that foot's inner edge + physics.zmp_margin), gliding across in double support. Where the sway takes the
    hip past what the planted leg reaches, the body is lowered a little there (more knee bend), eased in and out.
  - forward/back (y), every motion: where a quick move (arms thrown up, a stop at the end of a walk) would push the ZMP
    off the front or back of the feet, the hips counter-shift just enough to keep it inside, like a person bracing.
Feet, arms and every other channel stay as animated.
DROID=<id> python3 balance_fix.py in.blend out.blend RM_walk_loop,RM_demo_10s|all [lead_frames]"""
import bpy, sys, os, math
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit, physics
from physics import Body, G, hull, zmp
from bpy_extras import anim_utils
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
src, out = a[0], a[1]
LEAD = int(a[3]) if len(a) > 3 else 30
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(src))
rig = bpy.data.objects[kit.rig_name()]; sc = bpy.context.scene; fps = sc.render.fps; dt = 1 / fps
ad = rig.animation_data; keep = (ad.action, ad.action_slot)
names = [x.name for x in bpy.data.actions if x.name.startswith('RM_')] if a[2] == 'all' else a[2].split(',')
B = Body(rig)
PH = kit.get('physics', {}) or {}
MARGIN = PH.get('zmp_margin', 0.05)
COG = PH.get('sway_bone', 'COG'); PATH = f'pose.bones["{COG}"].location'
AX = {'x': 0, 'y': 1}


def sample(frames):
    """per frame: CoM, and per planted foot its support points"""
    cs, sup = [], []
    for f in frames:
        sc.frame_set(f); cs.append(B.com()); sup.append(B.support())
    return cs, sup


def zmps(cs, ax):
    i = AX[ax]; out = [None] * len(cs)
    for k in range(1, len(cs) - 1):
        acc = (cs[k + 1] - 2 * cs[k] + cs[k - 1]) / dt ** 2
        out[k] = zmp(cs[k], acc, B.Z0)[i]
    out[0], out[-1] = out[1], out[-2]
    return out


def span_at(h, ax, other):
    """the support polygon's extent along ax, on the line through `other` on the other axis"""
    i = AX[ax]; j = 1 - i
    if len(h) < 3: return None
    lo_o = min(p[j] for p in h); hi_o = max(p[j] for p in h); other = min(max(other, lo_o + 1e-4), hi_o - 1e-4)
    hits = []
    for k in range(len(h)):
        p, q = h[k], h[(k + 1) % len(h)]
        if (p[j] - other) * (q[j] - other) <= 0 and p[j] != q[j]:
            t = (other - p[j]) / (q[j] - p[j]); hits.append(p[i] + t * (q[i] - p[i]))
    return (min(hits), max(hits)) if hits else None


def solve(cs, ax, p, w, w0, w1):
    """smoothest CoM path on axis ax whose ZMP follows p (weights w), frames w0..w1; outside stays put"""
    i = AX[ax]; n = w1 - w0 + 1; rows, rhs = [], []
    for k in range(w0, w1 + 1):
        kk = (cs[k].z - B.Z0) / G / dt ** 2   # zmp_k = x_k - kk (x_{k+1} - 2x_k + x_{k-1})
        r = np.zeros(n); c0 = p[k]
        for j, cf in ((k - 1, -kk), (k, 1 + 2 * kk), (k + 1, -kk)):
            if w0 <= j <= w1: r[j - w0] += cf
            else: c0 -= cf * cs[j][i]
        rows.append(r * w[k]); rhs.append(c0 * w[k])
        r = np.zeros(n); r[k - w0] = 0.05; rows.append(r); rhs.append(0.05 * cs[k][i])   # stay near the original
    for k in range(w0, w1 - 1):   # smooth: small jerk
        r = np.zeros(n)
        for j, cf in ((k - 1, -1), (k, 3), (k + 1, -3), (k + 2, 1)):
            if w0 <= j <= w1: r[j - w0] += cf * 0.4
        rows.append(r); rhs.append(0.0)
    return np.linalg.lstsq(np.array(rows), np.array(rhs), rcond=None)[0]


def gain_of(ax, f):
    """how far the CoM moves when the COG bone moves 1 m on this axis (legs stay planted)"""
    sc.frame_set(f); c0 = B.com()[AX[ax]]
    rig.pose.bones[COG].location[AX[ax]] += 0.02; bpy.context.view_layer.update()
    return (B.com()[AX[ax]] - c0) / 0.02


def apply(act, frames, ax, want, w0, w1, gain):
    cb = anim_utils.action_get_channelbag_for_slot(act, act.slots[0])
    fc = next((c for c in cb.fcurves if c.data_path == PATH and c.array_index == AX[ax]), None) or \
        cb.fcurves.new(PATH, index=AX[ax], group_name=COG)
    base = {f: fc.evaluate(f) for f in frames}
    cs, sup = sample(frames)
    for it in range(3):
        for j, k in enumerate(range(w0, w1 + 1)): base[frames[k]] += (want[j] - cs[k][AX[ax]]) / gain
        for k_ in [k_ for k_ in fc.keyframe_points if frames[w0] <= k_.co.x <= frames[w1]][::-1]: fc.keyframe_points.remove(k_)
        for k in range(w0, w1 + 1):
            kp = fc.keyframe_points.insert(frames[k], base[frames[k]], options={'FAST'}); kp.interpolation = 'BEZIER'
            kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
        fc.update(); cs, sup = sample(frames)
        err = max(abs(want[j] - cs[k][AX[ax]]) for j, k in enumerate(range(w0, w1 + 1)))
        if err < 0.003: break
    return cb, cs, sup, err


def keep_reach(act, cb, frames, sup0):
    """lower the body where a planted foot came off the floor (the leg ran out of length), eased in and out"""
    _, sup = sample(frames)
    lost = [k for k in range(len(frames)) if set(sup0[k]) - set(sup[k])]
    if not lost: return 0.0
    zc = next(c for c in cb.fcurves if c.data_path == PATH and c.array_index == 2)
    drop = [0.0] * len(frames)
    for k in lost:
        sc.frame_set(frames[k]); z0 = rig.pose.bones[COG].location.z; d = 0.0
        while d < 0.08:
            d += 0.004; rig.pose.bones[COG].location.z = z0 - d; bpy.context.view_layer.update()
            if not (set(sup0[k]) - set(B.support())): break
        drop[k] = d + 0.003
    R = 6
    sm = [max(drop[j] * (0.5 + 0.5 * math.cos(math.pi * (j - k) / (R + 1))) for j in range(max(0, k - R), min(len(frames), k + R + 1)))
          for k in range(len(frames))]
    zb = {f: zc.evaluate(f) for f in frames}
    span = [k for k in range(len(frames)) if sm[k] > 0]
    for k_ in [k_ for k_ in zc.keyframe_points if frames[span[0]] <= k_.co.x <= frames[span[-1]]][::-1]: zc.keyframe_points.remove(k_)
    for k in span:
        kp = zc.keyframe_points.insert(frames[k], zb[frames[k]] - sm[k], options={'FAST'}); kp.interpolation = 'BEZIER'
        kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    zc.update()
    return max(drop)


for name in names:
    act = bpy.data.actions[name]
    ad.action = None; physics.reset_pose(rig); ad.action = act; ad.action_slot = act.slots[0]
    f0, f1 = map(int, act.frame_range); frames = list(range(f0, f1 + 1)); N = len(frames)
    cs, sup0 = sample(frames)
    single = [k for k, s in enumerate(sup0) if len(s) == 1]
    msg = []
    # ---- side to side: sway over the planted foot
    if single:
        tgt = [None] * N
        for k in single:
            (S, v), = sup0[k].items(); xs = [q.x for q in v]; mid = sum(xs) / len(xs)
            tgt[k] = min(min(xs) + MARGIN, mid) if mid > 0 else max(max(xs) - MARGIN, mid)
        w0, w1 = max(1, single[0] - LEAD), min(N - 2, single[-1] + LEAD)
        tgt[w0 - 1] = cs[w0 - 1].x; tgt[w1 + 1] = cs[w1 + 1].x
        known = [k for k in range(N) if tgt[k] is not None]
        p = np.interp(range(N), known, [tgt[k] for k in known])
        w = [1.0 if len(s) == 1 else 0.35 for s in sup0]   # double support has slack: anywhere between the feet is fine
        want = solve(cs, 'x', p, w, w0, w1)
        cb, cs, sup, err = apply(act, frames, 'x', want, w0, w1, gain_of('x', frames[single[len(single) // 2]]))
        d = keep_reach(act, cb, frames, sup0)
        msg.append(f'sway frames {frames[w0]}-{frames[w1]} (CoM error {err * 1000:.1f} mm' + (f', body lowered up to {d * 1000:.0f} mm)' if d else ')'))
        cs, sup = sample(frames)
    # ---- forward/back (and sideways when standing): only where the ZMP leaves the feet
    for ax in ('y',) + (() if single else ('x',)):
        z = zmps(cs, ax); p = list(z); w = [0.15] * N; bad = []
        for k in range(N):
            if not sup0[k]: continue
            h = hull([q for v in sup0[k].values() for q in v])
            r = span_at(h, ax, cs[k][1 - AX[ax]])
            if not r: continue
            lo, hi = r[0] + MARGIN, r[1] - MARGIN
            if lo > hi: lo = hi = (r[0] + r[1]) / 2
            if not lo <= z[k] <= hi: p[k] = min(max(z[k], lo), hi); w[k] = 1.0; bad.append(k)
        if not bad: continue
        w0, w1 = max(1, bad[0] - 12), min(N - 2, bad[-1] + 12)
        want = solve(cs, ax, p, w, w0, w1)
        cb, cs, sup, err = apply(act, frames, ax, want, w0, w1, gain_of(ax, frames[bad[0]]))
        d = keep_reach(act, cb, frames, sup0)
        msg.append(f'{ax} brace on {len(bad)} frames ({frames[bad[0]]}-{frames[bad[-1]]})' + (f', body lowered {d * 1000:.0f} mm' if d else ''))
        cs, sup = sample(frames)
    _, sup = sample(frames)
    lost = [frames[k] for k in range(N) if set(sup0[k]) - set(sup[k])]
    print(name, '; '.join(msg) or 'balanced as animated', '| planted feet lifted:', lost[:10], flush=True)
ad.action = keep[0]
if keep[0]: ad.action_slot = keep[1]
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True, relative_remap=False)
print('BALANCE_FIX ok')
