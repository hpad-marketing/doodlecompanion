"""Skin weights. Rigid parts get one bone; head/ears and legs blend smoothly."""
import math
from mathutils import Vector


def vgroup(ob, name):
    return ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)


def rigid(ob, bone):
    g = vgroup(ob, bone)
    g.add([v.index for v in ob.data.vertices], 1.0, 'REPLACE')


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


import os
EAR_ROOT = tuple(float(x) for x in os.environ.get('EAR_ROOT', '-0.2,0.25').split(','))


def head_and_ears(ob, ear_info, ear_mid, S):
    """Skull -> head; each ear blends head -> DEF-ear -> DEF-ear_tip along its axis."""
    gh = vgroup(ob, 'head')
    gr = vgroup(ob, 'ear_root')  # not a bone: limits the root smoothing below
    groups = {s: (vgroup(ob, f'DEF-ear.{s}'), vgroup(ob, f'DEF-ear_tip.{s}')) for s in 'LR'}
    for v in ob.data.vertices:
        co = v.co
        w_head = 1.0
        best = None
        best_r = None
        for s, ei in ear_info.items():
            a = ei['axis']
            rel = co - ei['root']
            t = rel.dot(a)
            radial = (rel - a * t).length
            if radial > 0.6 * S * 2.2 or t < -0.25 * S:
                continue
            if best_r is not None and radial >= best_r:
                continue
            best_r = radial
            w_ear = smoothstep(EAR_ROOT[0] * S, EAR_ROOT[1] * S, t)
            tm = (ear_mid[s] - ei['root']).dot(a)
            w_tip = smoothstep(tm - 0.12 * S, tm + 0.12 * S, t)  # bendy bones smooth the joint
            best = (s, w_ear, w_tip, t)
        if best:
            s, w_ear, w_tip, t = best  # t of the chosen ear, not the last one tried
            w_head = 1.0 - w_ear
            ge, gt = groups[s]
            # the band where skull turns into ear, reaching down into the saddle between the ears
            root_w = smoothstep(-0.45 * S, -0.15 * S, t) * (1 - smoothstep(0.2 * S, 0.45 * S, t))
            if root_w > 0.01:
                gr.add([v.index], root_w, 'REPLACE')
            if w_ear * (1 - w_tip) > 0:
                ge.add([v.index], w_ear * (1 - w_tip), 'REPLACE')
            if w_ear * w_tip > 0:
                gt.add([v.index], w_ear * w_tip, 'REPLACE')
        if w_head > 0:
            gh.add([v.index], w_head, 'REPLACE')


def by_targets(ob, targets, sigma):
    """Blend between bones by distance to each bone's own volume (Target objects)."""
    gs = {b: vgroup(ob, b) for b in targets}
    for v in ob.data.vertices:
        ws = {}
        for b, tg in targets.items():
            near = tg.nearest(v.co)
            d = (near - v.co).length
            inside = tg.inside(v.co) if hasattr(tg, 'inside') else False
            ws[b] = 1.0 if inside else math.exp(-(d / sigma) ** 2)
        tot = sum(ws.values()) or 1.0
        for b, w in ws.items():
            if w / tot > 1e-3:
                gs[b].add([v.index], w / tot, 'REPLACE')


def by_height(ob, lo_bone, hi_bone, z0, z1):
    g0, g1 = vgroup(ob, lo_bone), vgroup(ob, hi_bone)
    for v in ob.data.vertices:
        w = smoothstep(z0, z1, v.co.z)
        if 1 - w > 0:
            g0.add([v.index], 1 - w, 'REPLACE')
        if w > 0:
            g1.add([v.index], w, 'REPLACE')


def leg_chain(ob, side, hip_z, knee_z, ankle_z, S, blend=0.07):
    """Thigh / shin / foot by height, with soft knee and ankle blends (rest leg is near vertical)."""
    gt, gs, gf = (vgroup(ob, f'DEF-{b}.{side}') for b in ('thigh', 'shin', 'foot'))
    for v in ob.data.vertices:
        z = v.co.z
        w_up = smoothstep(knee_z - blend * S, knee_z + blend * S, z)        # thigh vs shin
        w_lo = smoothstep(ankle_z - blend * S, ankle_z + blend * S, z)      # shin vs foot
        wt, ws, wf = w_up, (1 - w_up) * w_lo, (1 - w_up) * (1 - w_lo)
        for g, w in ((gt, wt), (gs, ws), (gf, wf)):
            if w > 1e-4:
                g.add([v.index], w, 'REPLACE')


def hem_follow(ob, hip, hem_z, S, front=0.85, back=0.35):
    """The hoodie's lower panel rides on each thigh, so a high knee lifts the hem instead of poking through it."""
    hx, hy, hz = hip
    gt = vgroup(ob, 'torso')
    gl = {s: vgroup(ob, f'DEF-thigh.{s}') for s in 'LR'}
    for v in ob.data.vertices:
        c = v.co
        down = smoothstep(hz, hz - 0.75 * (hz - hem_z), c.z)  # 0 at the hip, 1 near the hem
        if down <= 0:
            continue
        fy = back + (front - back) * smoothstep(0.3 * hx, -0.3 * hx, c.y)
        tot = 0.0
        for s, sx in (('L', -1.0), ('R', 1.0)):
            lat = smoothstep(-0.25 * hx, 0.45 * hx, sx * c.x)
            w = down * fy * lat
            if w > 1e-4:
                gl[s].add([v.index], w, 'REPLACE')
                tot += w
        gt.add([v.index], max(0.0, 1.0 - tot), 'REPLACE')
