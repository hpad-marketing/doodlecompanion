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
    """The floor under the character: the floor you see in the scene is the base (user rule,
    31 Oct). That is the rig's own ground (z of the armature object), or the set's floor or a
    broad surface (a stage, a sweep) up to 25 cm higher right under the feet, found by casting
    straight down under each leg. Skipped on the way down: every character, every ink face (a
    set's outline hull floats 5-10 cm off the floor in a high shot and was once taken for the
    ground), and small scenery (a bench, a bin, a stone). A table top is never the floor."""
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
        pts = sorted(((mw @ v.co) for v in me.vertices), key=lambda p: p.z)[:24:6]   # a few of the lowest, toe to heel
        ev.to_mesh_clear()
        for p in pts:
            o = Vector((p.x, p.y, base + 0.3))
            for _ in range(12):
                hit, loc, nrm, _i, hob, _m = sc.ray_cast(dg, o, Vector((0, 0, -1)), distance=0.4)
                if not hit:
                    break
                if hob is not None and (hob.hide_render or _is_character(hob) or not _floor_like(hob) or _is_ink_face(hob, _i, dg)):
                    o = loc - Vector((0, 0, 1e-4))
                    continue
                # a real floor faces up; the set's outline hull (flipped, pushed off the floor by
                # the ink width, 5-10 cm in a high shot) faces down and is never the ground
                if base - 0.05 <= loc.z <= base + GROUND_RISE and nrm.z > 0.5:
                    best = max(best, loc.z)
                    break
                if loc.z < base - 0.05:
                    break
                # grass, a flower, a kerb edge or a table top above the feet: look on below it
                o = loc - Vector((0, 0, 1e-4))
    return best


def _floor_like(ob):
    """Only a set's room shell or a broad surface (a stage, a sweep, a big floor plane) can be the
    floor. A bench, a bin or a kerb a foot steps beside is scenery, never the ground."""
    return bool(ob.get('dsl_shell')) or min(ob.dimensions.x, ob.dimensions.y) >= 1.5


def _is_ink_face(ob, index, dg):
    """True when a ray hit landed on ink: the outline hull (the inverted shell DS/DSL Ink adds,
    pushed off the surface) or a drawn stroke, not on the surface itself."""
    try:
        me = ob.evaluated_get(dg).data
        mat = me.materials[me.polygons[index].material_index]
        return mat is not None and ('outline' in mat.name or mat.name.startswith(('DS_ink', 'DSL_ink')))
    except (IndexError, AttributeError, TypeError):
        return False


GROUND_RISE = 0.25   # the floor you see (a raised park floor, a stage) up to 25 cm above the rig's ground is the floor


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
    arm['ds_floor_target'] = target   # the ink shell is clamped here too (set_floor_z)
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


# ---------------------------------------------------------------- the ink shell stays above the floor
# The outline shell is pushed a few ink widths away from the camera (Depth Bias) so creases don't
# draw. From a high camera "away" points down, so under the feet the shell went through the floor
# and the floor hid the bottom of the foot strokes. The shell's push is now clamped at the floor:
# a shell point that started above the floor never ends below it (one that started below, a foot
# really dug in, is left alone for the floor lift to fix). The floor height comes from the rig
# (world z on the rig's floor holder, keyed per frame by the bridge).
FLOOR_OFF = -1000.0
SHELL_FADE = 0.06   # the push away from the camera fades in over this height above the floor


def _ink_groups():
    return [ng for ng in bpy.data.node_groups if ng.bl_idname == 'GeometryNodeTree'
            and any(getattr(it, 'in_out', None) == 'INPUT' and it.name == 'Depth Bias' for it in ng.interface.items_tree)]


def clamp_shell_group(ng):
    """Add the floor clamp to an ink node group (old saved files included). Idempotent."""
    if any(getattr(it, 'in_out', None) == 'INPUT' and it.name == 'Floor Z' for it in ng.interface.items_tree):
        return False
    flip = next((n for n in ng.nodes if n.bl_idname == 'GeometryNodeFlipFaces'), None)
    sp = flip.inputs['Mesh'].links[0].from_node if flip and flip.inputs['Mesh'].links else None   # the shell's Set Position
    if sp is None or sp.bl_idname != 'GeometryNodeSetPosition' or not sp.inputs['Offset'].links:
        return False                                                # not a shell group (a fill-only ink)
    sock = ng.interface.new_socket('Floor Z', in_out='INPUT', socket_type='NodeSocketFloat')
    sock.default_value = FLOOR_OFF
    off_link = sp.inputs['Offset'].links[0]
    off = off_link.from_socket
    gi = next(n for n in ng.nodes if n.bl_idname == 'NodeGroupInput')
    N, L = ng.nodes.new, ng.links.new
    pos = N('GeometryNodeInputPosition').outputs[0]
    me = N('GeometryNodeSelfObject')
    oi = N('GeometryNodeObjectInfo'); oi.transform_space = 'ORIGINAL'
    L(me.outputs[0], oi.inputs['Object'])
    M = oi.outputs['Transform']
    tw = lambda v: (lambda n: (L(M, n.inputs['Transform']), L(v, n.inputs['Vector']), n.outputs[0])[-1])(N('FunctionNodeTransformPoint'))
    pw = tw(pos)
    sz = lambda v: (lambda n: (L(v, n.inputs[0]), n.outputs['Z'])[-1])(N('ShaderNodeSeparateXYZ'))
    def m(op, a, b):
        n = N('ShaderNodeMath'); n.operation = op
        L(a, n.inputs[0]) if not isinstance(a, (int, float)) else setattr(n.inputs[0], 'default_value', a)
        L(b, n.inputs[1]) if not isinstance(b, (int, float)) else setattr(n.inputs[1], 'default_value', b)
        return n.outputs[0]
    # near the floor the push away from the camera fades out (gone at the floor, full 6 cm up):
    # behind a foot the ground can rise (a slope, a sweep, a bump), and a pushed outline would
    # sink into it. Down there the outline is just the stroke around the form.
    add = off_link.from_node
    if add.bl_idname == 'ShaderNodeVectorMath' and add.operation == 'ADD' and add.inputs[0].links and add.inputs[1].links:
        fade = m('MINIMUM', m('MAXIMUM', m('DIVIDE', m('SUBTRACT', sz(pw), gi.outputs['Floor Z']), SHELL_FADE), 0.0), 1.0)
        sc_away = N('ShaderNodeVectorMath'); sc_away.operation = 'SCALE'
        L(add.inputs[1].links[0].from_socket, sc_away.inputs[0]); L(fade, sc_away.inputs['Scale'])
        off2 = N('ShaderNodeVectorMath'); off2.operation = 'ADD'
        L(add.inputs[0].links[0].from_socket, off2.inputs[0]); L(sc_away.outputs[0], off2.inputs[1])
        off = off2.outputs[0]
    tgt = N('ShaderNodeVectorMath'); tgt.operation = 'ADD'; L(pos, tgt.inputs[0]); L(off, tgt.inputs[1])
    qw = tw(tgt.outputs[0])
    lift = m('MAXIMUM', m('SUBTRACT', m('MINIMUM', sz(pw), gi.outputs['Floor Z']), sz(qw)), 0.0)
    cz = N('ShaderNodeCombineXYZ'); L(lift, cz.inputs['Z'])
    inv = N('FunctionNodeInvertMatrix'); L(M, inv.inputs[0])
    td = N('FunctionNodeTransformDirection'); L(inv.outputs[0], td.inputs['Transform']); L(cz.outputs[0], td.inputs['Direction'])
    tot = N('ShaderNodeVectorMath'); tot.operation = 'ADD'; L(off, tot.inputs[0]); L(td.outputs[0], tot.inputs[1])
    ng.links.remove(off_link)
    L(tot.outputs[0], sp.inputs['Offset'])
    return True


def _rig_of(ob):
    p = ob
    while p is not None and p.type != 'ARMATURE':
        p = p.parent
    if p is not None:
        return p
    for m in ob.modifiers:
        if m.type == 'ARMATURE' and m.object:
            return m.object
    return None


def floor_holder(arm):
    """An empty beside each rig that carries its floor height ('ds_floor_z', world z). A property
    on the rig itself can't drive the ink: the legs already depend on the rig, so the driver
    would loop."""
    name = arm.name + '.floor'
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, None)
        ob.hide_render = True; ob.hide_viewport = True
        (arm.users_collection[0] if arm.users_collection else bpy.context.scene.collection).objects.link(ob)
        ob['ds_floor_z'] = FLOOR_OFF
    return ob


def set_floor_z(arm, z, frame=None):
    h = floor_holder(arm)
    h['ds_floor_z'] = z
    h.update_tag()
    if frame is not None:
        h.keyframe_insert('["ds_floor_z"]', frame=frame)


def _floor_sid(md):
    return next((it.identifier for it in md.node_group.interface.items_tree if getattr(it, 'in_out', None) == 'INPUT' and it.name == 'Floor Z'), None)


def bind_shell_floor():
    """Clamp every ink group and drive each ink modifier's Floor Z from its character's rig."""
    groups = _ink_groups()
    for ng in groups:
        clamp_shell_group(ng)
    groups = [ng for ng in groups if any(getattr(it, 'in_out', None) == 'INPUT' and it.name == 'Floor Z' for it in ng.interface.items_tree)]
    n = 0
    for ob in bpy.data.objects:
        for md in ob.modifiers:
            if md.type != 'NODES' or md.node_group not in groups:
                continue
            if _floor_sid(md) not in md.keys():
                md.node_group = md.node_group          # pick up the new input on an old modifier
            arm = _rig_of(ob)
            sid = next(it.identifier for it in md.node_group.interface.items_tree if getattr(it, 'in_out', None) == 'INPUT' and it.name == 'Floor Z')
            if arm is None:
                md[sid] = FLOOR_OFF
                continue
            h = floor_holder(arm)
            path = f'modifiers["{md.name}"]["{sid}"]'
            ob.driver_remove(path)
            d = ob.driver_add(path).driver
            d.type = 'AVERAGE'
            v = d.variables.new(); v.type = 'SINGLE_PROP'
            v.targets[0].id = h; v.targets[0].data_path = '["ds_floor_z"]'
            d.is_valid = True
            n += 1
    bpy.context.view_layer.update()
    return n
