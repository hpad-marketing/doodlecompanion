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


# floor collision: the parts that can reach the floor, measured with their ink outline on
FLOOR_PARTS = ('leg.L', 'leg.R', 'pelvis', 'shirt', 'hand.L', 'hand.R', 'cuff.L', 'cuff.R')
FLOOR_AIR = 0.001   # a millimetre of air under the stroke (covers line boil)


def _depth_bias(ob):
    """(modifier, input id) of each ink shell's Depth Bias. The shell is pushed a few ink widths
    away from the camera so creases stop drawing; that push is hidden behind the body, not a
    stroke, and from above it points straight down, so floor checks must leave it out."""
    out = []
    for m in ob.modifiers:
        if m.type == 'NODES' and m.node_group is not None:
            for it in m.node_group.interface.items_tree:
                if getattr(it, 'in_out', None) == 'INPUT' and it.name == 'Depth Bias':
                    out.append((m, it.identifier))
    return out


def hold_depth_bias():
    """Zero every ink shell's Depth Bias while the floor is worked out frame by frame (the bridge
    loop); returns a restore function. Switching it per measurement can lag one evaluation."""
    held = [(m, k, m[k]) for ob in bpy.data.objects if ob.type == 'MESH' for m, k in _depth_bias(ob)]
    for m, k, _ in held:
        m[k] = 0.0
    for ob in {m.id_data for m, _, _ in held}:
        ob.update_tag()

    def restore():
        for m, k, v in held:
            m[k] = v
        for ob in {m.id_data for m, _, _ in held}:
            ob.update_tag()
    return restore


def drawn_zmin(obs):
    """Lowest world z of the drawn surfaces, ink stroke included: the outline's real width round
    the body, without its push away from the camera (see _depth_bias)."""
    bias = [(m, k, m[k]) for ob in obs for m, k in _depth_bias(ob) if m[k] != 0.0]
    for m, k, _ in bias:
        m[k] = 0.0
    for ob in obs:
        ob.update_tag()
    try:
        return _zmin_eval(obs)
    finally:
        for m, k, v in bias:
            m[k] = v
        for ob in obs:
            ob.update_tag()


def _zmin_eval(obs):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    # the ink drivers read the camera and the keyed ink width, and can settle one pass late
    # (a camera's first move, a fresh frame_set): evaluate the measured parts once more
    for ob in obs:
        ob.update_tag()
    dg.update()
    z = None
    for ob in obs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        lo = min(((mw @ v.co).z for v in me.vertices), default=None)
        ev.to_mesh_clear()
        if lo is not None and (z is None or lo < z):
            z = lo
    return z


def body_zmin(obs):
    """Lowest world z of the body surface itself, ink off."""
    ink = [m for ob in obs for m in ob.modifiers if m.type == 'NODES' and m.show_viewport]
    for m in ink:
        m.show_viewport = False
    try:
        return _zmin_eval(obs)
    finally:
        for m in ink:
            m.show_viewport = True


def _is_character(ob):
    p = ob
    while p is not None:
        if p.type == 'ARMATURE' or p.name.startswith(('BUNNY_', 'DS_costar')):
            return True
        p = p.parent
    return False


def ground_z(arm, obs):
    """The floor under the character: the rig's own ground (z of the armature object), or a set
    floor or backdrop that sits higher right under the feet (found by casting straight down
    under each leg, skipping every character). Never a table or shelf: only surfaces within a
    few centimetres of the rig's ground count."""
    from mathutils import Vector
    base = arm.matrix_world.translation.z
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    best = base
    for ob in obs:
        if 'leg' not in ob.name:
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        pts = sorted(((mw @ v.co) for v in me.vertices), key=lambda p: p.z)[:1]
        ev.to_mesh_clear()
        for p in pts:
            o = Vector((p.x, p.y, base + 0.3))
            for _ in range(12):
                hit, loc, nrm, _i, hob, _m = sc.ray_cast(dg, o, Vector((0, 0, -1)), distance=0.4)
                if not hit:
                    break
                if hob is not None and (hob.hide_render or _is_character(hob)):
                    o = loc - Vector((0, 0, 1e-4))
                    continue
                if base - 0.05 <= loc.z <= base + GROUND_RISE and nrm.z > 0.5:
                    best = max(best, loc.z)
                break
    return best


GROUND_RISE = 0.06   # a set floor up to 6 cm above the rig's ground still counts as the floor


def floor_target(arm, obs=None):
    """The lowest the ink stroke may go: the floor plus a hair of air. Poses above it stay as they
    are (standing height, jumps); only a pose that would dig in is raised to it."""
    return (ground_z(arm, obs) if obs else arm.matrix_world.translation.z) + FLOOR_AIR


def floor_keyed_target(arm):
    """The target floor_lift found for the current frame (keyed), for the rule check."""
    return arm.matrix_world.translation.z + FLOOR_AIR + float(arm.get('ds_floor_up', 0.0))


def floor_lift(arm, objs):
    """Floor collision: when the lowest ink stroke of the legs (or a hand or the hoodie) would
    go under the floor, raise the character by exactly how deep it went. Anything that already
    clears the floor (standing, jumping) is never moved. The whole character moves on its root bone; the rig is untouched.
    The floor is the rig's own ground (z of the armature object: the set floors sit there).
    Returns the lift in metres (0 when nothing reached the floor)."""
    from mathutils import Vector
    obs = [objs[k] for k in FLOOR_PARTS if k in objs and not objs[k].hide_render]
    if not obs:
        return 0.0
    root = arm.pose.bones['root']
    to_bone = root.bone.matrix_local.to_3x3().inverted() @ arm.matrix_world.to_3x3().inverted()
    # this frame's camera and ink width first: twice, because the ink drivers read the camera's
    # type and lens, and on a camera's first move they settle one evaluation late
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()
    target = floor_target(arm, obs)
    arm['ds_floor_up'] = target - FLOOR_AIR - arm.matrix_world.translation.z   # the floor's rise here, for the check   # kept keyed for older checks: the target is the floor itself
    total = 0.0
    for _ in range(3):   # a rigid move shifts everything equally; the repeats only mop up perspective ink
        lo = drawn_zmin(obs)
        d = target - lo if lo is not None else 0.0
        if d <= 2e-4:   # lift only: a pose that clears the floor is never moved
            break
        root.location = root.location + to_bone @ Vector((0.0, 0.0, d))
        total += d
    return total


def floor_settle(arm, objs, frames, log=None):
    """After everything is keyed and baked: step through the frames once more, measure the
    stroke where it really ended up, and fix the root key by whatever is left (a millimetre or
    two of perspective, or a first frame whose ink settled late). Returns the biggest fix (m)."""
    from mathutils import Vector
    sc = bpy.context.scene
    obs = [objs[k] for k in FLOOR_PARTS if k in objs and not objs[k].hide_render]
    root = arm.pose.bones['root']
    worst = 0.0
    if not obs:
        return worst
    restore = hold_depth_bias()
    try:
        for f in frames:
            sc.frame_set(f)
            lo = drawn_zmin(obs)
            d = floor_target(arm, obs) - lo if lo is not None else 0.0
            if d > 5e-4:
                to_bone = root.bone.matrix_local.to_3x3().inverted() @ arm.matrix_world.to_3x3().inverted()
                root.location = root.location + to_bone @ Vector((0.0, 0.0, d))
                root.keyframe_insert('location', frame=f, group=root.name)
                worst = max(worst, abs(d))
    finally:
        restore()
    return worst
