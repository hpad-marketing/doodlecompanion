"""Bunny's armature: Doodle Studio pivots, FK + IK limbs, safety constraints.

Layers
  Controls (what an animator or Doodle Studio moves)
    root, body_rot, body, torso, chest, head, face, ear.L/R, ear_tip.L/R,
    upper_arm_fk / forearm_fk / hand_fk, thigh_fk / shin_fk / foot_fk,
    hand_ik, elbow_pole, foot_ik, foot_roll, knee_pole
  Mechanism (MCH-*, hidden)
    IK targets that follow FK or IK controls, push hands out of the head
    and keep feet above the floor; foot-roll pivots; spring (dynamics) bones.
  Deform (DEF-*)
    The chain that skins the meshes. Arms and legs are always solved by IK
    toward the chosen target, so even pure FK poses cannot put a hand inside
    the head or a foot through the floor.

Pivots come straight from Doodle Studio's rig, so a Doodle Studio rotation of
bone X maps onto the matching control here (see ds_map.py).
"""
import bpy
import math
from mathutils import Vector, Matrix

ARM = 'BUNNY_rig'


JOINTS = {}  # pivots that differ from Doodle Studio's (DS units), e.g. the walking-leg hips and knees


def P(rig, name, S):
    if name in JOINTS:
        return Vector(JOINTS[name]) * S
    return Vector(rig['config']['bones'][name]['pivot']) * S


def widget(name, kind, coll, size=1.0):
    ob = bpy.data.objects.get(name)
    if ob:
        return ob
    me = bpy.data.meshes.new(name)
    verts, edges = [], []
    if kind == 'circle':
        n = 32
        verts = [(math.cos(2 * math.pi * i / n) * size, math.sin(2 * math.pi * i / n) * size, 0) for i in range(n)]
        edges = [(i, (i + 1) % n) for i in range(n)]
    elif kind == 'circle_y':  # circle facing the bone's Y axis (around the bone)
        n = 32
        verts = [(math.cos(2 * math.pi * i / n) * size, 0, math.sin(2 * math.pi * i / n) * size) for i in range(n)]
        edges = [(i, (i + 1) % n) for i in range(n)]
    elif kind == 'cube':
        s = size
        verts = [(x, y, z) for x in (-s, s) for y in (-s, s) for z in (-s, s)]
        edges = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]
    elif kind == 'sphere':
        n = 24
        for ax in range(3):
            base = len(verts)
            for i in range(n):
                a = 2 * math.pi * i / n
                c, s = math.cos(a) * size, math.sin(a) * size
                verts.append((c, s, 0) if ax == 0 else (c, 0, s) if ax == 1 else (0, c, s))
            edges += [(base + i, base + (i + 1) % n) for i in range(n)]
    elif kind == 'diamond':
        s = size
        verts = [(s, 0, 0), (0, s, 0), (-s, 0, 0), (0, -s, 0), (0, 0, s), (0, 0, -s)]
        edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4), (0, 5), (1, 5), (2, 5), (3, 5)]
    me.from_pydata(verts, edges, [])
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


import os
EAR_ROOT_EASE = float(os.environ.get('EAR_ROOT_EASE', '1.0'))


def build_armature(rig, S, coll, wgt_coll, ear_info, part_centres):
    """Create bones. Returns the armature object."""
    arm_data = bpy.data.armatures.new(ARM)
    ob = bpy.data.objects.new(ARM, arm_data)
    coll.objects.link(ob)
    ob.show_in_front = True
    arm_data.display_type = 'OCTAHEDRAL'
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm_data.edit_bones
    B = {}

    def bone(name, head, tail, parent=None, deform=False, connect=False, roll=0.0):
        b = eb.new(name)
        b.head = head
        b.tail = tail
        b.roll = roll
        b.use_deform = deform
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect
        B[name] = b
        return b

    p = lambda n: P(rig, n, S)
    up = Vector((0, 0, 1))
    # trunk (Doodle Studio: ROOT pivot for BODY Tilt, TORSO pivot for bodyRot/Bow/Twist)
    bone('root', Vector((0, 0, 0)), Vector((0, 0.9 * S * 4, 0)))
    bone('body_rot', p('TORSO'), p('TORSO') + up * 0.6 * S, 'root')
    bone('body', p('ROOT'), p('ROOT') + up * 0.6 * S, 'body_rot', deform=True)  # the pelvis is skinned to it
    bone('torso', p('TORSO'), Vector((p('TORSO').x, 0, 1.6 * S)), 'body', deform=True)
    bone('chest', Vector((p('TORSO').x, 0, 1.6 * S)), Vector((p('TORSO').x, 0, 2.04 * S)), 'torso', deform=True, connect=True)
    bone('head', p('HEAD'), Vector((p('HEAD').x, 0, 5.94 * S)), 'chest', deform=True)
    bone('MCH-head_collider', Vector((0.005 * S, 0, 3.99 * S)), Vector((0.005 * S, 0, 4.5 * S)), 'head')
    bone('face', Vector((0.005 * S, -2.6 * S, 4.15 * S)), Vector((0.005 * S, -3.2 * S, 4.15 * S)), 'head')
    for side in 'LR':
        ei = ear_info[side]
        root_p = p('EAR.' + side)
        mid_p = p('EAR_TIP.' + side)
        tip = ei['tip']
        bone(f'ear.{side}', root_p, mid_p, 'head')
        bone(f'DEF-ear.{side}', root_p, mid_p, f'ear.{side}', deform=True)
        bone(f'ear_tip.{side}', mid_p, tip, f'DEF-ear.{side}', connect=False)
        bone(f'DEF-ear_tip.{side}', mid_p, tip, f'ear_tip.{side}', deform=True)
    # arms
    for side in 'LR':
        sh, el, wr = p('UPPER_ARM.' + side), p('FOREARM.' + side), p('WRIST.' + side)
        hc = part_centres['hand.' + side]
        hand_tail = wr + (hc - wr) * 2.0
        bone(f'upper_arm_fk.{side}', sh, el, 'chest')
        bone(f'forearm_fk.{side}', el, wr, f'upper_arm_fk.{side}', connect=True)
        bone(f'hand_fk.{side}', wr, hand_tail, f'forearm_fk.{side}', connect=True)
        bone(f'DEF-upper_arm.{side}', sh, el, 'chest', deform=True)
        bone(f'DEF-forearm.{side}', el, wr, f'DEF-upper_arm.{side}', deform=True, connect=True)
        bone(f'DEF-hand.{side}', wr, hand_tail, f'DEF-forearm.{side}', deform=True, connect=True)
        bone(f'hand_ik.{side}', wr, hand_tail, 'root')
        bone(f'MCH-hand_target.{side}', wr, wr + Vector((0, 0, -0.2 * S)), None)
        bone(f'elbow_pole.{side}', el, el + Vector((0, 0.3 * S, 0)), 'root')
        bone(f'MCH-elbow_pole_fk.{side}', el, el + Vector((0, 0.3 * S, 0)), f'upper_arm_fk.{side}')
        bone(f'MCH-elbow_pole.{side}', el, el + Vector((0, 0.3 * S, 0)), None)
    # legs
    for side in 'LR':
        hip, kn, an = p('THIGH.' + side), p('SHIN.' + side), p('ANKLE.' + side)
        fc = part_centres['foot.' + side]
        toe = Vector((an.x, fc.y - 0.38 * S, 0.22 * S))
        heel = Vector((an.x, fc.y + 0.36 * S, 0.22 * S))
        bone(f'thigh_fk.{side}', hip, kn, 'body')
        bone(f'shin_fk.{side}', kn, an, f'thigh_fk.{side}', connect=True)
        bone(f'foot_fk.{side}', an, toe, f'shin_fk.{side}', connect=True)
        bone(f'DEF-thigh.{side}', hip, kn, 'body', deform=True)
        bone(f'DEF-shin.{side}', kn, an, f'DEF-thigh.{side}', deform=True, connect=True)
        bone(f'DEF-foot.{side}', an, toe, f'DEF-shin.{side}', deform=True, connect=True)
        # IK foot with roll pivots: foot_ik -> heel pivot -> toe pivot -> ankle target
        bone(f'foot_ik.{side}', Vector((an.x, an.y, 0.0)), Vector((an.x, an.y - 0.5 * S, 0.0)), 'root')
        bone(f'foot_roll.{side}', heel + Vector((0, 0.25 * S, 0)), heel + Vector((0, 0.25 * S, 0.3 * S)), f'foot_ik.{side}')
        bone(f'MCH-heel.{side}', heel, heel + Vector((0, 0.15 * S, 0)), f'foot_ik.{side}')
        bone(f'MCH-toe.{side}', toe, toe + Vector((0, -0.15 * S, 0)), f'MCH-heel.{side}')
        bone(f'MCH-ankle_ik.{side}', an, toe, f'MCH-toe.{side}')
        bone(f'MCH-foot_target.{side}', an, an + Vector((0, 0, -0.2 * S)), None)
        bone(f'knee_pole.{side}', kn, kn + Vector((0, -0.3 * S, 0)), 'root')
        bone(f'MCH-knee_pole_fk.{side}', kn, kn + Vector((0, -0.3 * S, 0)), f'thigh_fk.{side}')
        bone(f'MCH-knee_pole.{side}', kn, kn + Vector((0, -0.3 * S, 0)), None)
    import geo
    (tx, ty, tz), tr = geo.TAIL
    bone('DEF-tail', Vector((tx, ty - tr * 0.6, tz)) * S, Vector((tx, ty + tr * 1.2, tz)) * S, 'torso', deform=True)
    # rest reference for the sleeve-bunch drivers (angle of the upper arm away from rest)
    for side in 'LR':
        src = eb[f'DEF-upper_arm.{side}']
        bone(f'MCH-arm_rest.{side}', src.head.copy(), src.tail.copy(), 'chest', roll=src.roll)
    # sockets: carry each FK control's motion to its deform bone's own rest orientation
    for side in 'LR':
        for d, c in (('upper_arm', 'upper_arm_fk'), ('forearm', 'forearm_fk'), ('hand', 'hand_fk'),
                     ('thigh', 'thigh_fk'), ('shin', 'shin_fk'), ('foot', 'foot_fk')):
            src = eb[f'DEF-{d}.{side}']
            bone(f'MCH-{d}_sock.{side}', src.head.copy(), src.tail.copy(), f'{c}.{side}', roll=src.roll)
    world_align(eb, [f'{n}.{s}' for s in 'LR' for n in CONTROL_LIMBS])
    # ears deform with bendy bones: one continuous curve from root to tip, no corner at the joint
    for side in 'LR':
        e, t = eb[f'DEF-ear.{side}'], eb[f'DEF-ear_tip.{side}']
        for b in (e, t):
            b.bbone_segments = 10
        e.bbone_handle_type_end = 'ABSOLUTE'  # AUTO ignores custom handles unless the bones are connected
        e.bbone_custom_handle_end = t
        t.bbone_handle_type_start = 'ABSOLUTE'
        t.bbone_custom_handle_start = e
        e.bbone_easeout = t.bbone_easein = 1.0
        # the root leaves the skull along the skull's own direction, so a wide fold
        # curves out of the head instead of hinging (and pinching) at the root
        e.bbone_handle_type_start = 'ABSOLUTE'
        e.bbone_custom_handle_start = eb['head']
        e.bbone_easein = EAR_ROOT_EASE
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


CONTROL_LIMBS = ('upper_arm_fk', 'forearm_fk', 'hand_fk', 'thigh_fk', 'shin_fk', 'foot_fk', 'ear', 'ear_tip')


def world_align(eb, names):
    """Controls point straight up with no roll, so their local axes are the world axes
    Doodle Studio rotates about. Joint limits can then be Doodle Studio's own ranges."""
    for n in names:
        b = eb[n]
        b.use_connect = False
    for n in names:
        b = eb[n]
        length = max(b.length, 0.05)
        b.tail = b.head + Vector((0, 0, length))
        b.roll = 0.0


def place_poles(ob, rig, S, ds_controls):
    """Put the FK pole helpers on the outside of each bend, from the DS bend axis."""
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ob.data.edit_bones
    p = lambda n: P(rig, n, S)
    axes = {1: Vector((1, 0, 0)), 2: Vector((0, 1, 0)), 3: Vector((0, 0, 1))}
    for limb, a, b, c, ctrl in (('elbow_pole', 'UPPER_ARM', 'FOREARM', 'WRIST', 'ELBOW {} Bend'),
                                ('knee_pole', 'THIGH', 'SHIN', 'ANKLE', 'KNEE {} Bend')):
        for side in 'LR':
            A, Bp, C = p(f'{a}.{side}'), p(f'{b}.{side}'), p(f'{c}.{side}')
            cd = [x for x in ds_controls if x['name'] == ctrl.format(side)][0]
            ang = math.radians(60 * (1 if cd['max'] > 0 else -1)) * cd['sign']
            R = Matrix.Rotation(ang, 3, axes[cd['axis']])
            C2 = Bp + R @ (C - Bp)
            line = (C2 - A).normalized()
            off = (Bp - A) - line * (Bp - A).dot(line)
            if off.length < 1e-6:
                off = axes[cd['axis']].cross(line)
            d = off.normalized() * 0.9 * S
            for nm in (f'{limb}.{side}', f'MCH-{limb}_fk.{side}', f'MCH-{limb}.{side}'):
                e = eb[nm]
                e.head = Bp + d
                e.tail = Bp + d + d.normalized() * 0.25 * S
    bpy.ops.object.mode_set(mode='OBJECT')


def _con(pb, kind, name=None, **kw):
    c = pb.constraints.new(kind)
    if name:
        c.name = name
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _drive_infl(con, ob, prop, expr=None):
    fc = con.driver_add('influence')
    d = fc.driver
    v = d.variables.new()
    v.name = 'v'
    v.type = 'SINGLE_PROP'
    v.targets[0].id = ob
    v.targets[0].data_path = f'["{prop}"]'
    if expr:
        d.type = 'SCRIPTED'
        d.expression = expr
    else:
        d.type = 'AVERAGE'


def add_prop(holder, name, value, mn, mx, desc):
    holder[name] = value
    holder.id_properties_ui(name).update(min=mn, max=mx, soft_min=mn, soft_max=mx, description=desc)


def setup_constraints(ob, S, head_radius, hand_radius, ankle_height):
    pb = ob.pose.bones
    for side in 'LR':
        add_prop(ob, f'arm_ik.{side}', 0.0, 0.0, 1.0, f'Arm {side}: 0 = FK (Doodle Studio angles), 1 = IK (hand control)')
        add_prop(ob, f'leg_ik.{side}', 0.0, 0.0, 1.0, f'Leg {side}: 0 = FK (Doodle Studio angles), 1 = IK (foot control)')
    add_prop(ob, 'floor', 1.0, 0.0, 1.0, 'Keep feet on or above the floor (rule: grounding)')
    for side in 'LR':
        # ---- arm
        t = pb[f'MCH-hand_target.{side}']
        c1 = _con(t, 'COPY_LOCATION', 'From FK', target=ob, subtarget=f'MCH-hand_sock.{side}')
        c2 = _con(t, 'COPY_LOCATION', 'From IK', target=ob, subtarget=f'hand_ik.{side}')
        _drive_infl(c2, ob, f'arm_ik.{side}')
        pole = pb[f'MCH-elbow_pole.{side}']
        _con(pole, 'COPY_TRANSFORMS', 'From FK', target=ob, subtarget=f'MCH-elbow_pole_fk.{side}')
        c = _con(pole, 'COPY_TRANSFORMS', 'From IK', target=ob, subtarget=f'elbow_pole.{side}')
        _drive_infl(c, ob, f'arm_ik.{side}')
        ik = _con(pb[f'DEF-forearm.{side}'], 'IK', 'IK', target=ob, subtarget=f'MCH-hand_target.{side}',
                  pole_target=ob, pole_subtarget=f'MCH-elbow_pole.{side}', chain_count=2)
        _drive_infl(ik, ob, f'arm_ik.{side}')
        # FK mode copies the FK chain exactly; IK mode uses the solver
        for d, f in ((f'DEF-upper_arm.{side}', f'MCH-upper_arm_sock.{side}'), (f'DEF-forearm.{side}', f'MCH-forearm_sock.{side}')):
            c = _con(pb[d], 'COPY_TRANSFORMS', 'FK', target=ob, subtarget=f)
            _drive_infl(c, ob, f'arm_ik.{side}', expr='1 - v')
        h = pb[f'DEF-hand.{side}']
        _con(h, 'COPY_ROTATION', 'FK hand', target=ob, subtarget=f'MCH-hand_sock.{side}')
        c = _con(h, 'COPY_ROTATION', 'IK hand', target=ob, subtarget=f'hand_ik.{side}')
        _drive_infl(c, ob, f'arm_ik.{side}')
        # ---- leg
        t = pb[f'MCH-foot_target.{side}']
        _con(t, 'COPY_LOCATION', 'From FK', target=ob, subtarget=f'MCH-foot_sock.{side}')
        c = _con(t, 'COPY_LOCATION', 'From IK', target=ob, subtarget=f'MCH-ankle_ik.{side}')
        _drive_infl(c, ob, f'leg_ik.{side}')
        c = _con(t, 'LIMIT_LOCATION', 'Floor', use_min_z=True, min_z=ankle_height, owner_space='CUSTOM',
                 space_object=ob, space_subtarget='root', use_transform_limit=True)
        _drive_infl(c, ob, 'floor')
        pole = pb[f'MCH-knee_pole.{side}']
        _con(pole, 'COPY_TRANSFORMS', 'From FK', target=ob, subtarget=f'MCH-knee_pole_fk.{side}')
        c = _con(pole, 'COPY_TRANSFORMS', 'From IK', target=ob, subtarget=f'knee_pole.{side}')
        _drive_infl(c, ob, f'leg_ik.{side}')
        ik = _con(pb[f'DEF-shin.{side}'], 'IK', 'IK', target=ob, subtarget=f'MCH-foot_target.{side}',
                  pole_target=ob, pole_subtarget=f'MCH-knee_pole.{side}', chain_count=2)
        _drive_infl(ik, ob, f'leg_ik.{side}')  # the solver would otherwise twist the FK leg
        # FK mode copies the FK chain exactly (no IK twist); IK mode uses the solver and the floor
        for d, f in ((f'DEF-thigh.{side}', f'MCH-thigh_sock.{side}'), (f'DEF-shin.{side}', f'MCH-shin_sock.{side}')):
            c = _con(pb[d], 'COPY_TRANSFORMS', 'FK', target=ob, subtarget=f)
            _drive_infl(c, ob, f'leg_ik.{side}', expr='1 - v')
        f = pb[f'DEF-foot.{side}']
        _con(f, 'COPY_ROTATION', 'FK foot', target=ob, subtarget=f'MCH-foot_sock.{side}')
        c = _con(f, 'COPY_ROTATION', 'IK foot', target=ob, subtarget=f'MCH-ankle_ik.{side}')
        _drive_infl(c, ob, f'leg_ik.{side}')
        # foot roll: +X rolls onto the toe, -X rocks back on the heel
        roll = pb[f'foot_roll.{side}']
        roll.rotation_mode = 'XYZ'
        for nm, lo, hi in ((f'MCH-heel.{side}', -90, 0), (f'MCH-toe.{side}', 0, 90)):
            c = _con(pb[nm], 'TRANSFORM', 'Roll', target=ob, subtarget=f'foot_roll.{side}',
                     map_from='ROTATION', map_to='ROTATION', owner_space='LOCAL', target_space='LOCAL')
            c.from_min_x_rot = math.radians(lo)
            c.from_max_x_rot = math.radians(hi)
            c.to_min_x_rot = math.radians(lo)
            c.to_max_x_rot = math.radians(hi)
    # trunk / arms / legs: quaternions; setup_limits() switches the controls to Euler
    for b in pb:
        b.rotation_mode = 'QUATERNION'


# extra freedom on axes Doodle Studio doesn't drive (twist etc.), degrees either way
SPARE = {'upper_arm_fk': 20, 'forearm_fk': 10, 'hand_fk': 30, 'thigh_fk': 15, 'shin_fk': 5, 'foot_fk': 15,
         'ear': 10, 'body': 0, 'torso': 0, 'head': 0}
EAR_TIP_RANGE = (60, 10, 60)  # local Y is the ear's own axis (twist); X and Z are the fold directions


def setup_limits(ob, rig):
    """Joint limits on every control, in Doodle Studio's own ranges.

    Each control's local axes are world axes (see world_align), so a Doodle Studio
    control 'rotate N degrees about world X' is a plain Euler channel here. The
    Euler order follows the order Doodle Studio applies its controls in.
    """
    import ds_map
    pb = ob.pose.bones
    controls = rig['config']['controls']
    for ds_bone, name in ds_map.BONE_MAP.items():
        b = pb[name]
        B0i = b.bone.matrix_local.to_3x3().inverted()
        owned = [c for c in controls if c['owner'] == ds_bone]
        rng = {}
        order = []
        for c in reversed(owned):  # Doodle Studio multiplies in list order: the last listed applies first
            A = Vector([1.0 if i == c['axis'] - 1 else 0.0 for i in range(3)])
            loc = B0i @ A
            k = max(range(3), key=lambda i: abs(loc[i]))
            sg = (1 if loc[k] > 0 else -1) * c['sign']
            lo, hi = sorted((c['min'] * sg, c['max'] * sg))
            rng[k] = (lo, hi)
            order.append('XYZ'[k])
        for k in range(3):
            if 'XYZ'[k] not in order:
                order.append('XYZ'[k])
        spare = SPARE[name.split('.')[0]]
        for k in range(3):
            rng.setdefault(k, (-spare, spare))
        mode = ''.join(order)
        b.rotation_mode = mode
        c = b.constraints.new('LIMIT_ROTATION')
        c.name = 'Joint limit'
        c.owner_space = 'LOCAL'
        c.euler_order = mode
        for k, ax in enumerate('xyz'):
            lo, hi = rng[k]
            setattr(c, f'use_limit_{ax}', True)
            setattr(c, f'min_{ax}', math.radians(lo))
            setattr(c, f'max_{ax}', math.radians(hi))
        b['ds_euler'] = mode
    add_prop(ob, 'ear_curl', 0.6, 0.0, 1.0, 'How much of an ear fold carries on into the tip, so ears bend in a smooth arc')
    for side in 'LR':
        b = pb[f'ear_tip.{side}']
        b.rotation_mode = 'XYZ'
        # the tip follows the root's fold: one fold control gives a soft curl, not a hinge
        cr = b.constraints.new('COPY_ROTATION')
        cr.name = 'Curl'
        cr.target = ob
        cr.subtarget = f'ear.{side}'
        cr.mix_mode = 'AFTER'  # whole rotation, so the tip curls about the same axis as the fold
        cr.owner_space = cr.target_space = 'LOCAL'
        _drive_infl(cr, ob, 'ear_curl')
        c = b.constraints.new('LIMIT_ROTATION')
        c.name = 'Joint limit'
        c.owner_space = 'LOCAL'
        for ax, r in zip('xyz', EAR_TIP_RANGE):
            setattr(c, f'use_limit_{ax}', True)
            setattr(c, f'min_{ax}', math.radians(-r))
            setattr(c, f'max_{ax}', math.radians(r))


def calibrate_pole_angles(ob, rig, S):
    """Pick each IK pole angle so the IK solve reproduces a bent FK pose exactly."""
    import ds_map
    controls = rig['config']['controls']
    pb = ob.pose.bones
    tests = {'arm': {'L': {'armL': 35, 'armLForward': 25, 'elbowL': 70}, 'R': {'armR': 35, 'armRForward': 25, 'elbowR': 70}},
             'leg': {'L': {'legL': 40, 'kneeL': 80}, 'R': {'legR': 40, 'kneeR': 80}}}
    out = {}
    for limb, def_b, fk_mid in (('arm', 'DEF-forearm', 'forearm_fk'), ('leg', 'DEF-shin', 'shin_fk')):
        for side in 'LR':
            ds_map.apply_pose(ob, controls, tests[limb][side], S)
            ik = pb[f'{def_b}.{side}'].constraints['IK']
            best = (1e9, 0)
            for coarse in (range(-180, 180, 10), None):
                rng = coarse if coarse is not None else range(best[1] - 10, best[1] + 11)
                for ang in rng:
                    ik.pole_angle = math.radians(ang)
                    bpy.context.view_layer.update()
                    e = (pb[f'{fk_mid}.{side}'].head - pb[f'{def_b}.{side}'].head).length
                    if e < best[0]:
                        best = (e, ang)
            ik.pole_angle = math.radians(best[1])
            out[f'{limb}.{side}'] = best
            ds_map.apply_pose(ob, controls, {}, S)
    bpy.context.view_layer.update()
    return out


def style_controls(ob, wgt_coll, S):
    pb = ob.pose.bones
    circ = widget('WGT-circle', 'circle', wgt_coll, 1.0)
    circ_y = widget('WGT-circle_y', 'circle_y', wgt_coll, 1.0)
    cube = widget('WGT-cube', 'cube', wgt_coll, 1.0)
    sph = widget('WGT-sphere', 'sphere', wgt_coll, 1.0)
    dia = widget('WGT-diamond', 'diamond', wgt_coll, 1.0)
    shapes = {
        'root': (circ, 1.2), 'body_rot': (circ_y, 1.6), 'body': (circ_y, 1.0), 'torso': (circ_y, 1.3), 'chest': (circ_y, 1.6),
        'head': (circ_y, 0.9), 'face': (dia, 0.6),
    }
    for side in 'LR':
        shapes.update({f'ear.{side}': (circ_y, 0.5), f'ear_tip.{side}': (circ_y, 0.45),
                       f'upper_arm_fk.{side}': (circ_y, 0.5), f'forearm_fk.{side}': (circ_y, 0.5), f'hand_fk.{side}': (circ_y, 0.4),
                       f'thigh_fk.{side}': (circ_y, 0.6), f'shin_fk.{side}': (circ_y, 0.6), f'foot_fk.{side}': (circ_y, 0.4),
                       f'hand_ik.{side}': (cube, 0.4), f'foot_ik.{side}': (cube, 0.5), f'foot_roll.{side}': (circ, 0.5),
                       f'elbow_pole.{side}': (sph, 0.25), f'knee_pole.{side}': (sph, 0.25)})
    for name, (w, sc) in shapes.items():
        b = pb.get(name)
        if not b:
            continue
        b.custom_shape = w
        b.custom_shape_scale_xyz = (sc, sc, sc)
        b.use_custom_shape_bone_size = True
    # bone collections: Controls / IK / Mechanism / Deform
    arm = ob.data
    cols = {n: arm.collections.new(n) for n in ('Controls', 'IK', 'Face', 'Mechanism', 'Deform')}
    for b in arm.bones:
        n = b.name
        if n.startswith('DEF-'):
            cols['Deform'].assign(b)
        elif n.startswith('MCH-'):
            cols['Mechanism'].assign(b)
        elif n.startswith(('hand_ik', 'foot_ik', 'foot_roll', 'elbow_pole', 'knee_pole')):
            cols['IK'].assign(b)
        elif n == 'face':
            cols['Face'].assign(b)
        else:
            cols['Controls'].assign(b)
    cols['Mechanism'].is_visible = False
    cols['Deform'].is_visible = False
    cols['IK'].is_visible = False


REACH_MAX = 1.0  # leg_reach 1 = thigh and shin twice their length


def setup_leg_reach(ob):
    """Sitting leg reach. 'leg_reach' (0-1) lengthens the hidden thigh and shin so a sitting
    character's legs come out from under the hoodie; the stub feet keep their size and shape.
    The front of the hem follows the thighs less as the legs reach, so they show (back panel
    keeps following). leg_reach 0 is exactly the standing rig."""
    add_prop(ob, 'leg_reach', 0.0, 0.0, 1.0, 'Sitting: 0 = normal legs, 1 = thigh and shin twice as long, hem front stays up (FK legs)')
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ob.data.edit_bones
    for side in 'LR':
        src = eb[f'DEF-thigh.{side}']
        for part in ('front', 'back'):
            b = eb.new(f'MCH-hem_{part}.{side}')
            b.head, b.tail, b.roll = src.head.copy(), src.tail.copy(), src.roll
            b.parent = eb['body']
            b.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')
    pb = ob.pose.bones
    for side in 'LR':
        # the length lives on the FK controls; the feet stop inheriting it but keep the character's scale
        for bn in (f'thigh_fk.{side}', f'shin_fk.{side}'):
            fc = pb[bn].driver_add('scale', 1)
            d = fc.driver
            d.type = 'SCRIPTED'
            v = d.variables.new(); v.name = 'r'; v.type = 'SINGLE_PROP'
            v.targets[0].id = ob; v.targets[0].data_path = '["leg_reach"]'
            d.expression = f'1 + {REACH_MAX} * r'
        for bn in (f'shin_fk.{side}', f'foot_fk.{side}', f'DEF-foot.{side}'):
            ob.data.bones[bn].inherit_scale = 'NONE'
            c = _con(pb[bn], 'COPY_SCALE', 'Character scale', target=ob, subtarget='root',
                     owner_space='WORLD', target_space='WORLD', use_offset=True)
            pb[bn].constraints.move(len(pb[bn].constraints) - 1, 0)  # before the FK/IK copies
        for part in ('front', 'back'):
            c = _con(pb[f'MCH-hem_{part}.{side}'], 'COPY_ROTATION', 'Thigh', target=ob, subtarget=f'DEF-thigh.{side}')
            if part == 'front':
                _drive_infl(c, ob, 'leg_reach', expr='1 - v')
