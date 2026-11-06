"""RX-07 hands v2 (user, 2026-11-06: "closer to human palms, like in the reference; the current one is flat,
how would it hold objects?"). Runs on the current file, touches only the hands:
  - palm: taller (fingers start lower, like a human hand's palm-to-finger ratio), tapers thinner toward the
    knuckles, knuckle line arched (middle finger lowest), inner face cupped
  - black rubber grip ribs across the cupped palm face, tan back plate like the photo
  - fingers splay slightly and rest in a relaxed curl (index least, ring most); black polymer grip pads on the
    inside of every finger segment (the photo's fingers are black)
  - thumb base lower and nearer the palm, swivelled so it sits opposite the fingers
  - hold.L / hold.R bones: where a held prop is centred (used by Hold/Release in the rig panel)
python3 hands_v2.py in.blend out.blend"""
import bpy, bmesh, sys, math
from mathutils import Vector as V, Matrix
src, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=src)
rig = bpy.data.objects['RobotRig']; arm = rig.data
FINGERS = ('index', 'middle', 'ring')
DROP = {'index': 0.047, 'middle': 0.049, 'ring': 0.047}       # finger roots move down: taller palm
SPLAY = {'index': -5, 'middle': 0, 'ring': 5}                  # degrees, toward -y / +y
CURL = {'index': (9, 11, 9), 'middle': (12, 14, 11), 'ring': (15, 16, 13)}   # rest curl per joint, degrees
THUMB_MOVE = (0.05, -0.0055, -0.035)   # (toward the palm side, y, z)
THUMB_SWIVEL = 20
import os   # tuning overrides: HV2_THUMB='x,y,z,swivel'
if os.environ.get('HV2_THUMB'):
    *_m, THUMB_SWIVEL = map(float, os.environ['HV2_THUMB'].split(',')); THUMB_MOVE = tuple(_m)
PALM_Y, PALM_TOP = (-0.085, 0.145), 0.70
R_K, GAP, FD = 0.015, 0.005, 0.038      # from build.py

def xform_all(bones, M):
    """move edit bones rigidly by a world matrix. New values are computed first: setting a connected child's head
    also drags its parent's tail, so moving bones one by one would move the chain twice."""
    new = [(M @ b.head, M @ b.tail, M.to_3x3() @ b.z_axis) for b in bones]
    for b, (h, t, z) in zip(bones, new): b.head = h; b.tail = t
    for b, (h, t, z) in zip(bones, new): b.align_roll(z)
def about(piv, ax, deg):
    return Matrix.Translation(piv) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-piv)

bpy.context.view_layer.objects.active = rig; rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); E = arm.edit_bones
SIDE = {}; MOUNT = {}
for S, s in (('L', 1), ('R', -1)):
    X = E[f'DEF-hand.{S}'].head.x; SIDE[S] = (X, s)
    for fn in FINGERS:
        chain = [E[f'f_{fn}_{i}.{S}'] for i in (1, 2, 3)]
        xform_all(chain, Matrix.Translation((0, 0, -DROP[fn])))
        piv = chain[0].head.copy()
        # splay: turn the whole chain about world X at its root; pick the sign that moves the tip the asked way
        if SPLAY[fn]:
            Ms = [about(piv, V((1, 0, 0)), SPLAY[fn] * g) for g in (1, -1)]
            M = max(Ms, key=lambda m: (m @ chain[-1].tail).y * (1 if SPLAY[fn] > 0 else -1))
            xform_all(chain, M)
        else: M = Matrix.Identity(4)
        MOUNT[S, fn] = M @ Matrix.Translation((0, 0, -DROP[fn]))   # the palm-side clevis moves with the finger root
        for k, a in enumerate(CURL[fn]):   # +x about each hinge curls toward the palm side
            b = chain[k]; M = about(b.head.copy(), b.x_axis.copy(), a)
            xform_all(chain[k:], M)
    t0 = E[f'f_thumb_0.{S}']; th = [t0] + [E[f'f_thumb_{i}.{S}'] for i in (1, 2, 3)]
    mv = Matrix.Translation((-s * THUMB_MOVE[0], THUMB_MOVE[1], THUMB_MOVE[2]))
    xform_all(th, mv)
    piv = t0.head.copy(); ax = (t0.tail - t0.head).normalized()
    M = max((about(piv, ax, THUMB_SWIVEL * g) for g in (1, -1)), key=lambda m: (m @ th[-1].tail).x * -s)
    xform_all(th, M)
    hb = E.get(f'hold.{S}') or E.new(f'hold.{S}')
    hb.head = V((X - s * 0.09, 0.03, 0.525))   # inside the finger curl, below the palm face
    hb.tail = hb.head + V((0, 0.06, 0)); hb.align_roll(V((0, 0, 1)))
    hb.parent = E[f'DEF-hand.{S}']; hb.use_deform = False
bpy.ops.object.mode_set(mode='OBJECT')
for S in 'LR':
    pb = rig.pose.bones[f'hold.{S}']; pb.custom_shape = bpy.data.objects.get('WGT_circle'); pb.custom_shape_scale_xyz = (0.5, 0.5, 0.5)
    for c in arm.collections:
        if c.name == 'Fingers': c.assign(arm.bones[f'hold.{S}'])

# palm-side clevis, cheeks and pin of each finger's first joint sit on DEF-hand: move them with the finger root
arm.pose_position = 'REST'; bpy.context.view_layer.update()
for (S, fn), M in MOUNT.items():
    for o in bpy.data.objects:
        if o.name.startswith(f'f_{fn}_1.{S}_') and o.parent_bone == f'DEF-hand.{S}':
            o.matrix_world = M @ o.matrix_world
bpy.context.view_layer.update(); arm.pose_position = 'POSE'

def rest_tail(bone):
    b = arm.bones[bone]; return rig.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))
def put(name, bm, mat, bone, bevel=0.0, like='palm.L'):
    """make or replace object `name` with world-rest geometry bm, parented to `bone` (rest pose = geometry)"""
    if bevel:
        edges = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > 0.6]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=2, profile=0.5, affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(bpy.data.materials[mat])
    for p in me.polygons: p.use_smooth = True
    me.set_sharp_from_angle(angle=math.radians(40))
    ob = bpy.data.objects.get(name)
    if ob:
        old = ob.data; ob.data = me
        if old.users == 0: bpy.data.meshes.remove(old)
    else:
        ob = bpy.data.objects.new(name, me); bpy.data.objects[like].users_collection[0].objects.link(ob)
        for k in ('rb_oil', 'rb_mud', 'rb_heat', 'rb_touch'):
            if k in bpy.data.objects[like]: ob[k] = bpy.data.objects[like][k]
    ob['rig_bone'] = bone; ob.parent = rig; ob.parent_type = 'BONE'; ob.parent_bone = bone
    ob.matrix_basis = Matrix.Identity(4); ob.matrix_parent_inverse = rest_tail(bone).inverted()
    return ob

def solid(f_out, f_in, nu=12, nw=10):
    """closed solid between two surfaces given as functions of (u, w) in [-1, 1]^2"""
    bm = bmesh.new(); A, B = {}, {}
    for i in range(nu + 1):
        for j in range(nw + 1):
            u, w = 2 * i / nu - 1, 2 * j / nw - 1
            A[i, j] = bm.verts.new(f_out(u, w)); B[i, j] = bm.verts.new(f_in(u, w))
    for i in range(nu):
        for j in range(nw):
            bm.faces.new([A[i, j], A[i + 1, j], A[i + 1, j + 1], A[i, j + 1]])
            bm.faces.new([B[i, j], B[i, j + 1], B[i + 1, j + 1], B[i + 1, j]])
    rim = [(i, 0) for i in range(nu)] + [(nu, j) for j in range(nw)] + [(i, nw) for i in range(nu, 0, -1)] + [(0, j) for j in range(nw, 0, -1)]
    for a, b in zip(rim, rim[1:] + rim[:1]):
        bm.faces.new([A[a], B[a], B[b], A[b]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

for S, (X, s) in SIDE.items():
    inward = -s   # the palm faces the body
    y0, y1 = PALM_Y
    def Y(u): return y0 + (y1 - y0) * (u + 1) / 2
    def Zb(u): return 0.562 - 0.006 * (1 - u * u)          # arched knuckle line, middle finger lowest
    def Z(u, w): return Zb(u) + (PALM_TOP - Zb(u)) * (w + 1) / 2
    def half(w): return 0.052 + 0.021 * (w + 1) / 2         # thinner toward the knuckles
    def cup(u, w): return 0.011 * (1 - u * u) * math.sin(math.pi * (w + 1) / 2) ** 0.7
    def p_out(u, w): return V((X - inward * half(w), Y(u), Z(u, w)))
    def p_in(u, w): return V((X + inward * (half(w) - cup(u, w)), Y(u), Z(u, w)))
    put(f'palm.{S}', solid(p_out, p_in), 'RB_metal_bare' if 'RB_metal_bare' in bpy.data.materials else 'RB_frame',
        f'DEF-hand.{S}', 0.008)
    # rubber grip ribs across the cupped palm face (they follow the cup), plus a short thumb-side rib
    ribs = [('rib0', -0.9, 0.9, -0.62, 0.11), ('rib1', -0.9, 0.9, -0.12, 0.11), ('rib2', -0.9, 0.9, 0.38, 0.11), ('rib3', -0.9, -0.25, 0.8, 0.07)]
    for nm, ua, ub, wc, wh in ribs:
        def r_in(u, w, ua=ua, ub=ub, wc=wc, wh=wh): return p_in(ua + (ub - ua) * (u + 1) / 2, wc + wh * w) - V((inward * 0.001, 0, 0))
        def r_out(u, w, ua=ua, ub=ub, wc=wc, wh=wh): return p_in(ua + (ub - ua) * (u + 1) / 2, wc + wh * w) + V((inward * 0.0075 * (1 - 0.5 * w * w), 0, 0))
        put(f'palm_{nm}.{S}', solid(r_out, r_in, 16, 4), 'RB_polymer', f'DEF-hand.{S}', 0.002)
    # tan back plate over the back of the hand (the photo's hand shell)
    def g_in(u, w): return p_out(0.94 * u, -0.55 + 0.75 * (w + 1)) + V((inward * 0.001, 0, 0))
    def g_out(u, w): return g_in(u, w) - V((inward * (0.012 + 0.004 * (1 - u * u)), 0, 0))
    g = put(f'hand_guard.{S}', solid(g_out, g_in), 'RB_metal_tan', f'DEF-hand.{S}', 0.004)
    if 'RB_soft' not in g.modifiers:
        m = g.modifiers.new('RB_soft', 'BEVEL'); m.width = 0.0025; m.limit_method = 'ANGLE'
    # grip pads on the inside of every finger segment
    for fn in FINGERS:
        for i in (1, 2, 3):
            bn = f'f_{fn}_{i}.{S}'; b = arm.bones[bn]; M = rig.matrix_world @ b.matrix_local
            x, y, z, h, L = M.col[0].xyz.normalized(), M.col[1].xyz.normalized(), M.col[2].xyz.normalized(), M.translation, b.length
            t0 = (R_K + GAP) / L; t1 = 1.0 if i == 3 else 1 - (R_K + GAP) / L
            c = h + y * (L * (t0 + t1) / 2) + z * (FD / 2 + 0.0035)
            bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
            for v in bm.verts:
                v.co.x *= 0.032 * (0.85 if (i == 3 and v.co.y > 0) else 1); v.co.y *= L * (t1 - t0) * 0.82; v.co.z *= 0.009
            bmesh.ops.transform(bm, matrix=Matrix((x, y, z)).transposed().to_4x4() @ Matrix.Identity(4), verts=bm.verts)
            bmesh.ops.translate(bm, vec=c, verts=bm.verts)
            put(f'{bn}_pad', bm, 'RB_polymer', bn, 0.003)
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
print('HANDS_V2 ok')
