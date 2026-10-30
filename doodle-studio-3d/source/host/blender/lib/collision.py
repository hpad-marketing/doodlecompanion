"""Pose-level collision solver (same idea as Doodle Studio's head-collision.js).

Arms move freely, but where a hand, cuff or sleeve would cut into the head
(skull + ears), the arm is turned the smallest amount that clears it. Ears
that would touch each other are opened up the same way. Runs per frame in the
bridge before keys are written, so renders never contain the violation.
The test uses the deformed cage meshes, which enclose the smooth surface, so a
cleared pose is guaranteed clear after subdivision too.
"""
import bpy
import bmesh
import math
from mathutils.bvhtree import BVHTree

ARM_PARTS = ('hand', 'cuff', 'sleeve_fore')  # upper sleeve tucks under the jaw by design (as in Doodle Studio)


def _cage_bvh(ob, face_pred=None):
    mods = [(m, m.show_viewport) for m in ob.modifiers if m.type != 'ARMATURE']
    for m, _ in mods:
        m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(ob.matrix_world)
    if face_pred is not None:
        drop = [f for f in bm.faces if not face_pred(f)]
        bmesh.ops.delete(bm, geom=drop, context='FACES')
    bvh = BVHTree.FromBMesh(bm)
    bm.free()
    ev.to_mesh_clear()
    for m, was in mods:
        m.show_viewport = was
    return bvh


def objects():
    return {o.name[6:]: o for o in bpy.data.objects if o.name.startswith('BUNNY_') and o.type == 'MESH'}


def arm_hits_head(objs, side, hb=None):
    if hb is None:
        hb = _cage_bvh(objs['head'])
    for part in ARM_PARTS:
        ob = objs.get(f'{part}.{side}')
        if ob and hb.overlap(_cage_bvh(ob)):
            return True
    return False


def ear_vertex_sets(head):
    out = {}
    for side in 'LR':
        ids = {head.vertex_groups[f'DEF-ear.{side}'].index, head.vertex_groups[f'DEF-ear_tip.{side}'].index}
        out[side] = {v.index for v in head.data.vertices if sum(g.weight for g in v.groups if g.group in ids) > 0.5}
    return out


def ears_touch(head, ear_sets):
    bvhs = [_cage_bvh(head, lambda f, s=s: all(v.index in ear_sets[s] for v in f.verts)) for s in 'LR']
    return bool(bvhs[0].overlap(bvhs[1]))


def _smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


EAR_GAP = 15.0  # degrees between the two ears' forward angles in a side view


def ear_spread(vals):
    """Side views: two ears tipped the same way sit exactly behind each other and
    draw a doubled line. Ease one of them EAR_GAP degrees less far so the back ear
    reads as its own shape. Fades in from 40 to 65 degrees of turn (and out again
    toward the back view), so nothing pops. Returns the change made, or None."""
    turn = ((vals.get('turn', 0) + 180) % 360) - 180
    a = abs(turn)
    w = _smoothstep(40, 65, a) * (1 - _smoothstep(115, 140, a))
    fl, fr = vals.get('earLForward', 0), vals.get('earRForward', 0)
    avg = (fl + fr) / 2
    if w <= 0 or abs(avg) < 5:
        return None
    gap = EAR_GAP * w * min(1.0, abs(avg) / 15)
    sign = 1 if avg > 0 else -1
    # the ear that eases is the one that then peeks out cleanly (checked by render)
    ease_l = (avg > 0) == (turn > 0)
    k, other = ('earLForward', fr) if ease_l else ('earRForward', fl)
    mine = vals.get(k, 0)
    if sign * (other - mine) >= gap:
        return None
    vals[k] = other - sign * gap
    return {k: round(vals[k] - mine, 2)}


def solve_frame(apply, values, objs, ear_sets=None, scan=140, step=5, hint=None):
    """apply(values) poses the rig. Returns (values, report).
    hint: the previous frame's report; its correction is tried first (shots move smoothly)."""
    report = {'arm_fix': {}, 'ear_fix': None}
    vals = dict(values)
    # search from the pose the rig can actually reach, not the raw request
    for side in 'LR':
        for k, lo, hi in ((f'arm{side}', -10, 145), (f'arm{side}Forward', -60, 110), (f'elbow{side}', 0, 140)):
            if k in vals:
                vals[k] = max(lo, min(hi, vals[k]))
    report['ear_spread'] = ear_spread(vals)
    apply(vals)
    bpy.context.view_layer.update()
    hb = _cage_bvh(objs['head'])  # arm candidates never move the head
    for side in 'LR':
        if not arm_hits_head(objs, side, hb):
            continue
        r_id, f_id, e_id = (f'arm{side}', f'arm{side}Forward', f'elbow{side}')
        base = (vals.get(r_id, 0.0), vals.get(f_id, 0.0), vals.get(e_id, 0.0))
        prev = (hint or {}).get('arm_fix', {}).get(side)
        found = None
        if isinstance(prev, dict):
            cand = dict(vals)
            for k in (r_id, f_id, e_id):
                cand[k] = vals.get(k, 0.0) + prev.get(k, 0.0) * 1.15
            apply(cand)
            bpy.context.view_layer.update()
            if not arm_hits_head(objs, side, hb):
                found = cand
        dirs = []
        for k in range(16):
            a = 2 * math.pi * k / 16
            dirs.append((math.cos(a), math.sin(a), 0.0))
        dirs += [(0, 0, -1), (0, 0, 1)]
        rad = step
        while rad <= scan and not found:
            for d in sorted(dirs, key=lambda d: (round(-d[0], 3) if d[0] < 0 else 2 + abs(d[1]), abs(d[2]))):  # lower the arm first, then swing it
                cand = dict(vals)
                cand[r_id] = max(-10, min(145, base[0] + d[0] * rad))
                cand[f_id] = max(-60, min(110, base[1] + d[1] * rad))
                cand[e_id] = max(0, min(140, base[2] + d[2] * rad))
                apply(cand)
                bpy.context.view_layer.update()
                if not arm_hits_head(objs, side, hb):
                    found = cand
                    break
            rad += step
        if found:
            # bisect back toward the authored pose for the smallest correction
            lo, hi = 0.0, 1.0
            for _ in range(5):
                mid = (lo + hi) / 2
                cand = dict(vals)
                for k in (r_id, f_id, e_id):
                    cand[k] = vals.get(k, 0.0) + (found[k] - vals.get(k, 0.0)) * mid
                apply(cand)
                bpy.context.view_layer.update()
                if arm_hits_head(objs, side, hb):
                    lo = mid
                else:
                    hi = mid
            for k in (r_id, f_id, e_id):
                vals[k] = vals.get(k, 0.0) + (found[k] - vals.get(k, 0.0)) * hi
            report['arm_fix'][side] = {k: round(vals[k] - values.get(k, 0.0), 2) for k in (r_id, f_id, e_id)}
        else:
            report['arm_fix'][side] = 'unresolved'
        apply(vals)
        bpy.context.view_layer.update()
    if ear_sets is not None and ears_touch(objs['head'], ear_sets):
        for t in (0.8, 0.6, 0.4, 0.2, 0.0):
            cand = dict(vals)
            for k in ('earLFold', 'earRFold', 'earLForward', 'earRForward'):
                if k in cand:
                    cand[k] = cand[k] * t
            apply(cand)
            bpy.context.view_layer.update()
            if not ears_touch(objs['head'], ear_sets):
                vals = cand
                report['ear_fix'] = t
                break
        apply(vals)
        bpy.context.view_layer.update()
    return vals, report
