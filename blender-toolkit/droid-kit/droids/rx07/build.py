"""Build the box-mech robot: rigid plastic parts + articulated rig (IK/FK, fingers, toes, plates).
Run: python3 build.py <out.blend>
"""
import bpy, bmesh, math, sys, json
from mathutils import Vector, Matrix, Euler

OUT = sys.argv[-1] if sys.argv[-1].endswith('.blend') else '/tmp/robot.blend'
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
V = Vector
rad = math.radians

# ---------------------------------------------------------------- materials
def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c] + [1]

PALETTE = {
    'grey':  ('#434E58', 0.55), 'frame': ('#34373B', 0.5), 'tan': ('#C4B28C', 0.6),
    'teal':  ('#6FA9A4', 0.55), 'navy': ('#2B3A5C', 0.5), 'yellow': ('#D8A834', 0.5),
    'sage':  ('#93B49A', 0.55), 'olive': ('#6F7B43', 0.6), 'steel': ('#6B6F73', 0.35),
}
MATS = {}
for k, (hx, rough) in PALETTE.items():
    m = bpy.data.materials.new('RB_' + k)
    nt = m.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = srgb(hx)
    bsdf.inputs['Roughness'].default_value = rough
    if 'Specular IOR Level' in bsdf.inputs:
        bsdf.inputs['Specular IOR Level'].default_value = 0.35
    m.diffuse_color = srgb(hx)
    MATS[k] = m

# ---------------------------------------------------------------- collections
def coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(c)
    return c
C_ROBOT = coll('Robot')
C_PARTS = coll('Robot_Parts', C_ROBOT)
C_WGT = coll('Robot_Widgets', C_ROBOT)

# ---------------------------------------------------------------- bone spec
BONES = {}   # name -> dict(head, tail, z, parent, connect, coll, ctrl)
def B(name, head, tail, z, parent=None, connect=False, coll='Mechanics', ctrl=False):
    BONES[name] = dict(head=V(head), tail=V(tail), z=V(z), parent=parent, connect=connect, coll=coll, ctrl=ctrl)

def frame(name):
    b = BONES[name]
    y = (b['tail'] - b['head']).normalized()
    z = (b['z'] - y * b['z'].dot(y)).normalized()
    x = y.cross(z)
    return b['head'], y, x, z, (b['tail'] - b['head']).length

SIDES = (('L', 1), ('R', -1))
UP, FWD, BACK = (0, 0, 1), (0, -1, 0), (0, 1, 0)

# torso
B('root', (0, 0, 0), (0, -0.6, 0), UP, coll='Body', ctrl=True)
B('COG', (0, 0.0, 1.18), (0, 0.45, 1.18), UP, 'root', coll='Body', ctrl=True)
B('hips', (0, 0, 1.18), (0, 0, 0.98), FWD, 'COG', coll='Body', ctrl=True)
B('waist', (0, 0, 1.18), (0, 0, 1.50), FWD, 'hips', coll='Body', ctrl=True)
B('body', (0, 0, 1.50), (0, 0, 2.00), FWD, 'waist', coll='Body', ctrl=True)
B('hatch', (0, 0.535, 2.12), (0, 0.535, 1.62), BACK, 'body', coll='Armour', ctrl=True)
B('sensor', (0, 0.30, 2.373), (0, 0.30, 2.53), FWD, 'body', coll='Armour', ctrl=True)
B('skirt_front', (0, -0.29, 1.21), (0, -0.30, 1.0), FWD, 'hips', coll='Armour', ctrl=True)
B('skirt_back', (0, 0.29, 1.21), (0, 0.30, 1.0), BACK, 'hips', coll='Armour', ctrl=True)

FINGERS = {  # name: (base y, seg lengths)
    'index': (-0.035, (0.075, 0.060, 0.052)),
    'middle': (0.03, (0.078, 0.062, 0.052)),
    'ring': (0.095, (0.070, 0.057, 0.050)),
}
wrist_pts = {}
R_K, GAP = 0.015, 0.005
FW, FD = 0.042, 0.038   # finger width / depth   # knuckle radius / clearance

for S, s in SIDES:
    # ---- leg
    X = 0.38 * s
    hip, knee, ankle = V((X, 0.02, 1.06)), V((X, -0.07, 0.62)), V((X, 0.0, 0.19))
    ball, toet, heel = V((X, -0.20, 0.06)), V((X, -0.40, 0.05)), V((X, 0.20, 0.0))
    for P, par in (('FK', 'hips'), ('IK', 'hips')):
        cl = 'Leg FK' if P == 'FK' else 'Mechanics'
        B(f'{P}-thigh.{S}', hip, knee, FWD, par, coll=cl, ctrl=P == 'FK')
        B(f'{P}-shin.{S}', knee, ankle, BACK, f'{P}-thigh.{S}', True, coll=cl, ctrl=P == 'FK')
    afwd = ankle + V((0, -0.24, 0))   # ankle motors work on level axes: pitch across, roll straight ahead
    B(f'FK-foot.{S}', ankle, afwd, UP, f'FK-shin.{S}', coll='Leg FK', ctrl=True)
    B(f'FK-toe.{S}', ball, toet, UP, f'FK-foot.{S}', False, coll='Leg FK', ctrl=True)
    B(f'IK_foot.{S}', (X, 0.10, 0.0), (X, -0.25, 0.0), UP, 'root', coll='Leg IK', ctrl=True)
    B(f'roll_heel.{S}', heel, heel + V((0, -0.12, 0)), UP, f'IK_foot.{S}', coll='Leg IK', ctrl=True)
    B(f'roll_toe.{S}', V((X, -0.40, 0.0)), V((X, -0.28, 0.0)), UP, f'roll_heel.{S}', coll='Leg IK', ctrl=True)
    B(f'roll_ball.{S}', ball, ball + V((0, 0.12, 0)), UP, f'roll_toe.{S}', coll='Leg IK', ctrl=True)
    B(f'IK-foot.{S}', ankle, afwd, UP, f'roll_ball.{S}')
    B(f'MCH-ankle.{S}', ankle, ankle + V((0, 0, 0.08)), FWD, f'roll_ball.{S}')
    B(f'IK-toe.{S}', ball, toet, UP, f'roll_toe.{S}', coll='Leg IK', ctrl=True)
    B(f'pole_knee.{S}', V((X, -0.85, 0.62)), V((X, -0.95, 0.62)), UP, f'IK_foot.{S}', coll='Leg IK', ctrl=True)
    for n, par, h, t, z in (('thigh', 'hips', hip, knee, FWD), ('shin', f'DEF-thigh.{S}', knee, ankle, BACK),
                            ('foot', f'DEF-shin.{S}', ankle, afwd, UP), ('toe', f'DEF-foot.{S}', ball, toet, UP)):
        B(f'DEF-{n}.{S}', h, t, z, par, coll='Deform')
    hd = (knee - hip).normalized()
    B(f'plate_thigh.{S}', V((X, -0.165, 0.925)), V((X, -0.165, 0.925)) + hd * 0.225, FWD, f'DEF-thigh.{S}', coll='Armour', ctrl=True)
    B(f'plate_knee.{S}', V((X, -0.185, 0.72)), V((X, -0.19, 0.56)), FWD, f'DEF-shin.{S}', coll='Armour', ctrl=True)
    B(f'skirt_side.{S}', V((0.58 * s, 0.02, 1.175)), V((0.58 * s, 0.02, 1.175)) + hd * 0.2, FWD, 'hips', coll='Armour', ctrl=True)

    # ---- arm
    X = 0.86 * s
    sh_in, sh = V((0.40 * s, 0.06, 1.86)), V((0.80 * s, 0.06, 1.86))
    elbow, wrist, htip = V((X, 0.14, 1.30)), V((X, 0.03, 0.76)), V((X, 0.03, 0.585))
    wrist_pts[S] = wrist
    B(f'shoulder.{S}', sh_in, sh, UP, 'body', coll='Arm FK', ctrl=True)
    for P in ('FK', 'IK'):
        cl = 'Arm FK' if P == 'FK' else 'Mechanics'
        B(f'{P}-upper_arm.{S}', sh, elbow, FWD, f'shoulder.{S}', coll=cl, ctrl=P == 'FK')
        B(f'{P}-forearm.{S}', elbow, wrist, FWD, f'{P}-upper_arm.{S}', True, coll=cl, ctrl=P == 'FK')
    B(f'FK-hand.{S}', wrist, htip, FWD, f'FK-forearm.{S}', True, coll='Arm FK', ctrl=True)
    B(f'IK_hand.{S}', wrist, htip, FWD, 'root', coll='Arm IK', ctrl=True)
    B(f'pole_elbow.{S}', V((X, 0.85, 1.30)), V((X, 0.95, 1.30)), UP, 'body', coll='Arm IK', ctrl=True)
    for n, par, h, t in (('upper_arm', f'shoulder.{S}', sh, elbow), ('forearm', f'DEF-upper_arm.{S}', elbow, wrist),
                         ('hand', f'DEF-forearm.{S}', wrist, htip)):
        B(f'DEF-{n}.{S}', h, t, FWD, par, coll='Deform')
    ad = (elbow - sh).normalized()
    B(f'plate_pauldron.{S}', sh, sh + ad * 0.15, FWD, f'shoulder.{S}', coll='Armour', ctrl=True)
    B(f'plate_elbow.{S}', V((X, 0.262, 1.20)), V((X, 0.262, 1.40)), BACK, f'DEF-forearm.{S}', coll='Armour', ctrl=True)
    B(f'plate_forearm.{S}', V((0.975 * s, 0.115, 1.19)), V((0.975 * s, 0.085, 1.04)), (s, 0, 0), f'DEF-forearm.{S}', coll='Armour', ctrl=True)
    B(f'plate_shield.{S}', V((0.98 * s, 0.078, 1.015)), V((0.98 * s, 0.045, 0.80)), (s, 0, 0), f'DEF-forearm.{S}', coll='Armour', ctrl=True)
    # fingers (palm faces the body: curl toward -s X)
    for fn, (fy, segs) in FINGERS.items():
        p = V((X, fy, htip.z)); par = f'DEF-hand.{S}'
        for i, L in enumerate(segs, 1):
            q = p + V((0, 0, -L))
            nm = f'f_{fn}_{i}.{S}'
            B(nm, p, q, (-s, 0, 0), par, i > 1, coll='Fingers', ctrl=True)
            par, p = nm, q
    tdir = V((0, -0.55, -1)).normalized()
    # robot thumb: rotary swivel base (turret on the palm face) + three single-axis hinges that close toward the fingers
    B(f'f_thumb_0.{S}', V((X, -0.08, 0.66)), V((X, -0.115, 0.66)), (-s, 0, 0), f'DEF-hand.{S}', coll='Fingers', ctrl=True)
    p = V((X, -0.115, 0.66)); par = f'f_thumb_0.{S}'
    for i, L in enumerate((0.062, 0.055, 0.048), 1):
        q = p + tdir * L
        nm = f'f_thumb_{i}.{S}'
        B(nm, p, q, (-0.6 * s, 1, 0), par, True, coll='Fingers', ctrl=True)
        par, p = nm, q
    # grip actuator: one control closes every finger + thumb through their linkages
    B(f'grip.{S}', V((X + 0.12 * s, 0.03, 0.70)), V((X + 0.12 * s, 0.03, 0.62)), FWD, f'DEF-hand.{S}', coll='Fingers', ctrl=True)

# robot joints: multi-axis joints are stacks of single-axis motors (gimbal stages). Each stage bone turns on ONE
# axis (copied from the deform bone with the matching Euler order), and carries the hardware for that axis.
GIMBALS = {}
def gimbal(src, axes, order):
    b = BONES[src]; par = b['parent']; st = []
    base = src[4:] if src.startswith('DEF-') else src
    for i, a in enumerate(axes, 1):
        nm = f'GIM{i}-{base}'
        B(nm, b['head'], b['tail'], b['z'], par, coll='Mechanics'); par = nm; st.append((nm, a))
    GIMBALS[src] = (order, st)
for S, s in SIDES:
    gimbal(f'DEF-upper_arm.{S}', 'xz', 'YZX')   # shoulder: pitch drum -> roll fork -> twist bearing
    gimbal(f'DEF-thigh.{S}', 'xz', 'YZX')       # hip: pitch drum -> roll fork -> yaw bearing
    gimbal(f'DEF-hand.{S}', 'yx', 'ZXY')        # wrist: roll collar -> pitch/yaw cardan cross
    gimbal(f'DEF-foot.{S}', 'y', 'ZXY')         # ankle: roll trunnion -> pitch pin
gimbal('sensor', 'y', 'ZXY')                    # sensor: pan turntable -> tilt yoke

# secondary motion: knee pistons (damped-track pair), sprung antennas, dangling cable
SPRINGS = []
for S, s in SIDES:
    X = 0.38 * s; knee = V((X, -0.07, 0.62))
    A = knee + V((0.175 * s, -0.045, 0.17)); Bp = knee + V((0.175 * s, -0.045, -0.17))
    d = (Bp - A).normalized()
    B(f'piston_house.{S}', A, A + d * 0.20, (s, 0, 0), f'DEF-thigh.{S}', coll='Mechanics')
    B(f'piston_rod.{S}', Bp, Bp - d * 0.26, (s, 0, 0), f'DEF-shin.{S}', coll='Mechanics')
    B(f'MCH-pistonA.{S}', A, A + V((0, 0, 0.04)), FWD, f'DEF-thigh.{S}', coll='Mechanics')
    B(f'MCH-pistonB.{S}', Bp, Bp + V((0, 0, 0.04)), FWD, f'DEF-shin.{S}', coll='Mechanics')
for nm, ax in (('antenna_L', 0.22), ('antenna_R', -0.22)):
    chain, tg = [], []
    par = 'body'
    for i in range(3):
        h = V((ax, 0.38, 2.30 + 0.12 * i)); t = h + V((0, 0, 0.12))
        B(f'{nm}_{i + 1}', h, t, FWD, par, i > 0, coll='Mechanics')
        B(f'SPR-{nm}_{i + 1}', t, t + V((0, 0, 0.03)), FWD, par, coll='Mechanics')
        chain.append(f'{nm}_{i + 1}'); tg.append(f'SPR-{nm}_{i + 1}'); par = f'{nm}_{i + 1}'
    SPRINGS.append(dict(bones=chain, targets=tg, k=0.22, damp=0.22, grav=0.0, max_deg=25))
chain, tg = [], []
par = 'body'
for i in range(4):
    h = V((0.50, 0.635, 2.065 - 0.085 * i)); t = h + V((0, 0, -0.085))
    B(f'cable_{i + 1}', h, t, BACK, par, i > 0, coll='Mechanics')
    B(f'SPR-cable_{i + 1}', t, t + V((0, 0, -0.03)), BACK, par, coll='Mechanics')
    chain.append(f'cable_{i + 1}'); tg.append(f'SPR-cable_{i + 1}'); par = f'cable_{i + 1}'
SPRINGS.append(dict(bones=chain, targets=tg, k=0.05, damp=0.12, grav=0.0012, max_deg=7))

# ---------------------------------------------------------------- armature
arm_data = bpy.data.armatures.new('RobotRig')
arm = bpy.data.objects.new('RobotRig', arm_data)
C_ROBOT.objects.link(arm)
arm.show_in_front = True
arm_data.display_type = 'OCTAHEDRAL'
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
COLL_ORDER = ['Body', 'Arm FK', 'Arm IK', 'Leg FK', 'Leg IK', 'Fingers', 'Armour', 'Mechanics', 'Deform']
bcolls = {n: arm_data.collections.new(n) for n in COLL_ORDER}
ebs = arm_data.edit_bones
for n, b in BONES.items():
    eb = ebs.new(n); eb.head = b['head']; eb.tail = b['tail']; eb.align_roll(b['z'])
    eb.use_deform = False
    bcolls[b['coll']].assign(eb)
for n, b in BONES.items():
    if b['parent']:
        ebs[n].parent = ebs[b['parent']]; ebs[n].use_connect = b['connect']
bpy.ops.object.mode_set(mode='POSE')
for n in ('Mechanics', 'Deform'):
    bcolls[n].is_visible = False

# ---------------------------------------------------------------- parts (meshes)
PARTS = []
def finish(name, bm, mat, bone, bevel):
    if bevel > 0:
        edges = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > 0.6]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=2, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(MATS[mat])
    for pl in me.polygons: pl.use_smooth = True
    me.set_sharp_from_angle(angle=rad(40))
    ob = bpy.data.objects.new(name, me); C_PARTS.objects.link(ob)
    ob['rig_bone'] = bone
    PARTS.append((ob, bone))
    return ob

def box_m(M, size, taper=(1, 1), taper0=(1, 1)):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        if v.co.y > 0: v.co.x *= taper[0]; v.co.z *= taper[1]
        else: v.co.x *= taper0[0]; v.co.z *= taper0[1]
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm

def axes_m(c, x, y, z):
    m = Matrix((x, y, z)).transposed().to_4x4(); m.translation = c; return m

def box(name, center, size, mat, bone, bevel=0.01, rot=(0, 0, 0), taper=(1, 1)):
    """world-aligned box (size x,y,z); taper shrinks the +y end."""
    M = Matrix.Translation(V(center)) @ Euler([rad(a) for a in rot]).to_matrix().to_4x4()
    return finish(name, box_m(M, size, taper), mat, bone, bevel)

def box_on(name, frame_bone, t0, t1, w, d, mat, bone=None, off=(0, 0, 0), bevel=0.01, taper=(1, 1), taper0=(1, 1)):
    """box along a bone from t0..t1 (fraction of length); w along bone X, d along bone Z."""
    h, y, x, z, L = frame(frame_bone)
    c = h + y * (L * (t0 + t1) / 2) + V(off)
    return finish(name, box_m(axes_m(c, x, y, z), (w, L * (t1 - t0), d), taper, taper0), mat, bone or frame_bone, bevel)

def cyl(name, p1, p2, r, mat, bone, segs=24, bevel=0.004, r2=None):
    p1, p2 = V(p1), V(p2); d = p2 - p1
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r2 or r, depth=d.length)
    M = Matrix.Translation((p1 + p2) / 2) @ V((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return finish(name, bm, mat, bone, bevel)

def sphere(name, c, r, mat, bone):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=r)
    bmesh.ops.translate(bm, vec=V(c), verts=bm.verts)
    return finish(name, bm, mat, bone, 0)

def knuckle(name, bone, r, w, mat='frame'):
    h, y, x, z, L = frame(bone)
    return cyl(name, h - x * w / 2, h + x * w / 2, r, mat, bone, segs=16, bevel=0.002)


STRUTS = []

def yoke(child, drum_r, drum_w, t, reach, tongue_len=0, mat='frame', bar_w=None, pin=True):
    """Parent-side clevis (two cheeks + pin) straddling the child's drum, child-side tongue to its body."""
    h, y, x, z, L = frame(child)
    par = BONES[child]['parent']
    py = frame(par)[1]
    clr = drum_r * 0.06 + 0.002
    R = drum_r * 0.85
    bv = min(0.004, t * 0.25)
    for side in (-1, 1):
        c = h + x * (side * (drum_w / 2 + clr + t / 2))
        cyl(f'{child}_cheek{side:+d}', c - x * (t / 2), c + x * (t / 2), R, mat, par, segs=20, bevel=bv)
        bc = c - py * (reach / 2)
        finish(f'{child}_cheekbar{side:+d}', box_m(axes_m(bc, x, -py, x.cross(-py)), (t, reach, bar_w or R * 1.6)), mat, par, bv)
    if pin:
        pw = drum_w + 2 * (clr + t) + 0.012
        cyl(f'{child}_pin', h - x * (pw / 2), h + x * (pw / 2), drum_r * 0.32, 'steel', par, segs=16, bevel=0.002)
    if tongue_len:
        tc = h + y * (tongue_len / 2)
        finish(f'{child}_tongue', box_m(axes_m(tc, x, y, z), (drum_w * 0.8, tongue_len, drum_r * 1.3)), mat, child, 0.006)

def plate_hinge(plate, parent, w, d, r, anchor, strut, mat='frame'):
    """Door hinge: barrels + tabs on the plate's outer thirds, centre knuckle + strut on the parent."""
    h, y, x, z, L = frame(plate)
    seg, g = w / 3, 0.004
    for side in (-1, 1):
        c = h + x * (side * seg)
        cyl(f'{plate}_barrel{side:+d}', c - x * (seg / 2 - g), c + x * (seg / 2 - g), r, 'steel', plate, segs=16, bevel=0.002)
        tc = c + y * ((r + g) / 2 + 0.003)
        finish(f'{plate}_tab{side:+d}', box_m(axes_m(tc, x, y, z), (seg - g * 2, r + g + 0.01, max(d * 0.7, r * 1.2))), mat, plate, 0.003)
    cyl(f'{plate}_knuckle', h - x * (seg / 2 - g), h + x * (seg / 2 - g), r, mat, parent, segs=16, bevel=0.002)
    cyl(f'{plate}_pin', h - x * (w / 2 + 0.006), h + x * (w / 2 + 0.006), r * 0.45, 'steel', parent, segs=12, bevel=0.001)
    for side in (-1, 1):
        cyl(f'{plate}_pincap{side:+d}', h + x * (side * (w / 2)), h + x * (side * (w / 2 + 0.008)), r * 0.7, 'steel', parent, segs=12, bevel=0.001)
    STRUTS.append(dict(name=f'{plate}_strut', h=h, a=V(anchor).normalized(), x=x, w=(seg - 2 * g) * 0.7, d=r * 1.4,
                       parent=parent, skip=plate, r=r, mat=mat))
    return (r + g + 0.003) / L   # where the plate body may start

def pitch_roll_twist(base, S, lo, hi, drum_r, fork_r, d0, d1, disc_r, mat='frame'):
    """3-motor joint: pitch drum (stage 1, local X), roll fork + pin (stage 2, local Z), twist bearing disc (local Y)."""
    g1, g2 = f'GIM1-{base}.{S}', f'GIM2-{base}.{S}'
    h, y, x, z, L = frame(f'DEF-{base}.{S}')
    s = 1 if S == 'L' else -1
    xo = x if x.x * s > 0 else -x
    cyl(f'{base}_pitch_drum.{S}', h + xo * lo, h + xo * hi, drum_r, mat, g1, segs=32)
    off = drum_r + 0.005 + 0.0125
    cyl(f'{base}_roll_pin.{S}', h - z * (off + 0.025), h + z * (off + 0.025), 0.022, 'steel', g1, segs=16)
    for e in (-1, 1):
        c = h + z * (e * off)
        cyl(f'{base}_roll_cheek{e:+d}.{S}', c - z * 0.0125, c + z * 0.0125, fork_r, mat, g2, segs=24)
        finish(f'{base}_roll_bar{e:+d}.{S}', box_m(axes_m(c + y * (d1 / 2), x, y, z), (fork_r, d1, 0.025)), mat, g2, 0.004)
    finish(f'{base}_roll_bridge.{S}', box_m(axes_m(h + y * ((d0 + d1) / 2), x, y, z), (fork_r, d1 - d0, 2 * off + 0.025)), mat, g2, 0.004)
    cyl(f'{base}_twist_disc.{S}', h + y * (d1 - 0.001), h + y * (d1 + 0.0005), disc_r, 'steel', g2, segs=32)
    return h, y, xo, z

# ---- torso
box('body_box', (0, 0, 1.75), (1.10, 0.98, 0.84), 'grey', 'body', bevel=0.04)
for sx in (-0.37, 0.37):
    box(f'body_strap_front_{sx:+.0f}', (sx, -0.495, 1.75), (0.07, 0.03, 0.78), 'grey', 'body', 0.008)
    box(f'body_strap_top_{sx:+.0f}', (sx, -0.06, 2.175), (0.07, 0.80, 0.03), 'grey', 'body', 0.008)
for i, (hx, hz) in enumerate(((0.33, 1.47), (0.12, 1.47))):
    box(f'body_handle_{i}_bar', (hx, -0.53, hz), (0.11, 0.025, 0.035), 'frame', 'body', 0.008)
    for e in (-0.045, 0.045):
        box(f'body_handle_{i}_{e:+.2f}', (hx + e, -0.51, hz), (0.025, 0.04, 0.05), 'frame', 'body', 0.006)
cyl('body_port', (-0.30, -0.50, 1.55), (-0.30, -0.47, 1.55), 0.025, 'frame', 'body')
box('body_seam', (0.0, -0.496, 1.52), (0.50, 0.012, 0.01), 'frame', 'body', 0)
# backpack (teal) on top-rear + hatch
box('pack_base', (0, 0.26, 2.215), (0.78, 0.38, 0.09), 'teal', 'body', 0.015)
for i, x in enumerate((-0.26, -0.09, 0.09, 0.26)):
    cyl(f'pack_bolt_{i}', (x, 0.16, 2.26), (x, 0.16, 2.285), 0.03, 'teal', 'body', segs=6, bevel=0.003)
box('pack_rail_L', (0.33, 0.30, 2.28), (0.06, 0.30, 0.05), 'teal', 'body', 0.008)
box('pack_rail_R', (-0.33, 0.30, 2.28), (0.06, 0.30, 0.05), 'teal', 'body', 0.008)
cyl('sensor_mount', (0, 0.30, 2.26), (0, 0.30, 2.30), 0.07, 'teal', 'GIM1-sensor')   # pan turntable
box('sensor_yoke_base', (0, 0.30, 2.306), (0.228, 0.06, 0.014), 'frame', 'GIM1-sensor', 0.003)
for e in (-1, 1):
    box(f'sensor_yoke_cheek{e:+d}', (e * 0.105, 0.30, 2.352), (0.012, 0.06, 0.106), 'frame', 'GIM1-sensor', 0.003)
cyl('sensor_tilt_pin', (-0.118, 0.30, 2.373), (0.118, 0.30, 2.373), 0.012, 'steel', 'sensor', segs=12)
box('sensor_head', (0, 0.28, 2.373), (0.18, 0.14, 0.09), 'teal', 'sensor', 0.015)
box('sensor_lens', (0, 0.205, 2.38), (0.10, 0.02, 0.04), 'frame', 'sensor', 0.006)
box('hatch_panel', (0, 0.535, 1.86), (0.72, 0.07, 0.46), 'teal', 'hatch', 0.015)
plate_hinge('hatch', 'body', 0.72, 0.07, 0.022, (0, -1, 0), 0.055)
for i, x in enumerate((-0.25, 0, 0.25)):
    box(f'hatch_fin_{i}', (x, 0.578, 1.86), (0.05, 0.02, 0.36), 'teal', 'hatch', 0.005)
# waist + pelvis
cyl('waist_ring', (0, 0, 1.24), (0, 0, 1.345), 0.15, 'frame', 'waist', segs=32)
cyl('waist_turntable_base', (0, 0, 1.185), (0, 0, 1.246), 0.12, 'steel', 'hips', segs=32)   # yaw bearing seat
box('pelvis', (0, 0, 1.10), (0.40, 0.50, 0.18), 'tan', 'hips', 0.02)
box('pelvis_under', (0, 0.0, 0.99), (0.26, 0.34, 0.05), 'frame', 'hips', 0.01)
box('skirt_front_plate', (0, -0.30, 1.09), (0.30, 0.04, 0.18), 'tan', 'skirt_front', 0.01, rot=(6, 0, 0))
plate_hinge('skirt_front', 'hips', 0.30, 0.04, 0.016, (0, 1, -0.3), 0.07)
box('skirt_back_plate', (0, 0.30, 1.09), (0.30, 0.04, 0.18), 'tan', 'skirt_back', 0.01, rot=(-6, 0, 0))
plate_hinge('skirt_back', 'hips', 0.30, 0.04, 0.016, (0, -1, -0.3), 0.07)

for S, s in SIDES:
    # ---- legs
    X = 0.38 * s
    cyl(f'hip_axle.{S}', (0.19 * s, 0.02, 1.06), (0.316 * s, 0.02, 1.06), 0.055, 'frame', 'hips')
    pitch_roll_twist('thigh', S, -0.07, 0.07, 0.085, 0.06, 0.11, 0.13, 0.075)
    box_on(f'thigh_core.{S}', f'DEF-thigh.{S}', 0.294, 0.70, 0.19, 0.19, 'frame', taper=(0.9, 0.7))
    box_on(f'thigh_rear.{S}', f'DEF-thigh.{S}', 0.32, 0.55, 0.13, 0.06, 'frame', off=(0, 0.115, 0))
    t0 = plate_hinge(f'plate_thigh.{S}', f'DEF-thigh.{S}', 0.22, 0.06, 0.02, (0, 1, 0), 0.085)
    box_on(f'thigh_plate.{S}', f'plate_thigh.{S}', t0, 1.0, 0.22, 0.06, 'tan', taper=(0.85, 1), bevel=0.015)
    box_on(f'thigh_plate_side.{S}', f'DEF-thigh.{S}', 0.30, 0.68, 0.035, 0.21, 'tan', off=(0.105 * s, -0.02, 0))
    knuckle(f'knee_joint.{S}', f'DEF-shin.{S}', 0.085, 0.19)
    yoke(f'DEF-shin.{S}', 0.085, 0.19, 0.03, 0.14, 0.15)
    t0 = plate_hinge(f'plate_knee.{S}', f'DEF-shin.{S}', 0.17, 0.045, 0.016, (0, 1, -0.9), 0.09)
    box_on(f'knee_cap_plate.{S}', f'plate_knee.{S}', t0, 1.0, 0.17, 0.045, 'frame', taper=(0.8, 1))
    box_on(f'shin_core.{S}', f'DEF-shin.{S}', 0.33, 0.80, 0.21, 0.20, 'sage', taper=(0.85, 0.9), taper0=(0.9, 0.7), bevel=0.015)
    box_on(f'shin_front.{S}', f'DEF-shin.{S}', 0.38, 0.70, 0.14, 0.05, 'sage', off=(0, -0.10, 0))
    h, y, x, z, L = frame(f'DEF-shin.{S}')
    for e in (-0.07, 0.07):
        a = h + y * (L * 0.40) + x * e + V((0, 0.108, 0))
        cyl(f'shin_piston_{e:+.2f}.{S}', a, a + y * (L * 0.40), 0.022, 'steel', f'DEF-shin.{S}', segs=12)
        for k, tt in enumerate((0.40, 0.80)):
            m = h + y * (L * tt) + x * e
            box(f'shin_piston_clamp{k}_{e:+.2f}.{S}', m + V((0, 0.095, 0)), (0.05, 0.04, 0.03), 'frame', f'DEF-shin.{S}', 0.006)
    fh, fy, fx, fz, fL = frame(f'DEF-foot.{S}')
    # ankle: roll trunnion (stage 1, carried in a bearing behind the joint) -> pitch drum + pin -> foot cheeks
    g1 = f'GIM1-foot.{S}'
    cyl(f'ankle_joint.{S}', fh - fx * 0.085, fh + fx * 0.085, 0.07, 'frame', g1, segs=24)
    box_on(f'ankle_tongue.{S}', f'DEF-shin.{S}', 0.62, 0.77, 0.15, 0.19, 'frame')
    cyl(f'ankle_pin.{S}', fh - fx * 0.168, fh + fx * 0.168, 0.026, 'steel', g1, segs=16)
    cyl(f'ankle_roll_pin.{S}', fh, fh - fy * 0.11, 0.022, 'steel', g1, segs=16)
    rc = fh - fy * 0.0815
    cyl(f'ankle_roll_bearing.{S}', rc - fy * 0.0065, rc + fy * 0.0065, 0.036, 'frame', f'DEF-shin.{S}', segs=20)
    sh_ = frame(f'DEF-shin.{S}'); tz = (sh_[0] + sh_[1] * (sh_[4] * 0.70)).z
    box(f'ankle_roll_bracket.{S}', (X, rc.y, (rc.z + tz) / 2), (0.05, 0.016, tz - rc.z), 'frame', f'DEF-shin.{S}', 0.003)
    box(f'foot_block.{S}', (X, -0.01, 0.0575), (0.34, 0.38, 0.115), 'olive', f'DEF-foot.{S}', 0.025, taper=(1, 0.8))
    for side, nm in ((1, 'o'), (-1, 'i')):
        box(f'foot_cheek_{nm}.{S}', (X + side * 0.145 * s, 0.02, 0.185), (0.035, 0.15, 0.15), 'olive', f'DEF-foot.{S}', 0.01)
    box(f'toe_block.{S}', (X, -0.31, 0.05), (0.34, 0.16, 0.10), 'olive', f'DEF-toe.{S}', 0.025)
    th_, ty_, tx_, tz_, tL_ = frame(f'DEF-toe.{S}')
    cyl(f'toe_drum.{S}', th_ - tx_ * 0.15, th_ + tx_ * 0.15, 0.036, 'frame', f'DEF-toe.{S}', segs=20)
    cyl(f'toe_pin.{S}', th_ - tx_ * 0.172, th_ + tx_ * 0.172, 0.015, 'steel', f'DEF-foot.{S}', segs=12)
    for i, e in enumerate((-0.10, 0, 0.10)):
        box(f'toe_nub_{i}.{S}', (X + e, -0.395, 0.035), (0.075, 0.03, 0.06), 'olive', f'DEF-toe.{S}', 0.012)
    box(f'skirt_side_plate.{S}', (0.58 * s, 0.02, 1.039), (0.045, 0.36, 0.218), 'tan', f'skirt_side.{S}', 0.012)
    kh, ky, kx, kz, kL = frame(f'skirt_side.{S}')   # single hinge along the forward axis
    cyl(f'skirt_side_barrel.{S}', kh - kz * 0.04, kh + kz * 0.04, 0.026, 'steel', f'skirt_side.{S}', segs=16)
    cyl(f'skirt_side_pin.{S}', kh - kz * 0.062, kh + kz * 0.062, 0.010, 'steel', 'hips', segs=12)
    for e in (-1, 1):
        finish(f'skirt_side_lug{e:+d}.{S}', box_m(axes_m(kh + kz * (e * 0.0505) - V((0.012 * s, 0, 0)), kx, ky, kz), (0.05, 0.05, 0.009)), 'frame', 'hips', 0.002)
    # bracket arm rides ABOVE the hip motor's sweep: riser on the pelvis -> bar -> drop link -> hinge lugs
    box(f'skirt_side_riser.{S}', (0.20 * s, 0.02, 1.212), (0.06, 0.06, 0.06), 'frame', 'hips', 0.006)
    cyl(f'skirt_side_bar.{S}', (0.17 * s, 0.02, 1.235), (0.515 * s, 0.02, 1.235), 0.022, 'frame', 'hips', segs=16)
    box(f'skirt_side_drop.{S}', (0.5275 * s, 0.02, 1.206), (0.035, 0.044, 0.062), 'frame', 'hips', 0.004)
    box(f'skirt_side_bridge.{S}', (0.545 * s, 0.02, 1.177), (0.012, 0.11, 0.045), 'frame', 'hips', 0.002)

    # ---- arms
    X = 0.86 * s
    cyl(f'shoulder_socket.{S}', (0.50 * s, 0.06, 1.86), (0.62 * s, 0.06, 1.86), 0.15, 'frame', f'shoulder.{S}', segs=32)
    uh, uy, uxo, uz = pitch_roll_twist('upper_arm', S, -0.19, 0.08, 0.13, 0.07, 0.15, 0.180, 0.10)
    cyl(f'shoulder_axle.{S}', uh + uxo * 0.08, uh + uxo * 0.218, 0.04, 'steel', f'GIM1-upper_arm.{S}', segs=16)
    cyl(f'shoulder_cap.{S}', uh + uxo * 0.08, uh + uxo * 0.10, 0.075, 'grey', f'GIM1-upper_arm.{S}', segs=24)
    box(f'pauldron_top.{S}', (0.94 * s, 0.04, 2.07), (0.28, 0.48, 0.10), 'tan', f'plate_pauldron.{S}', 0.018)
    cyl(f'pauldron_bearing.{S}', uh + uxo * 0.216, uh + uxo * 0.236, 0.07, 'steel', f'plate_pauldron.{S}', segs=24)
    box(f'pauldron_side.{S}', (1.055 * s, 0.04, 1.935), (0.05, 0.46, 0.27), 'tan', f'plate_pauldron.{S}', 0.015)
    for i, vy in enumerate((-0.07, 0.13)):
        box(f'pauldron_vent{i}.{S}', (1.09 * s, vy, 1.93), (0.03, 0.13, 0.14), 'frame', f'plate_pauldron.{S}', 0.008)
    box_on(f'upper_arm_block.{S}', f'DEF-upper_arm.{S}', 0.32, 0.72, 0.24, 0.28, 'tan', taper=(0.9, 0.85), bevel=0.018)
    box_on(f'upper_arm_core.{S}', f'DEF-upper_arm.{S}', 0.70, 0.86, 0.13, 0.13, 'frame')
    knuckle(f'elbow_joint.{S}', f'DEF-forearm.{S}', 0.085, 0.17)
    yoke(f'DEF-forearm.{S}', 0.085, 0.17, 0.025, 0.12, 0.14)
    t0 = plate_hinge(f'plate_elbow.{S}', f'DEF-forearm.{S}', 0.20, 0.05, 0.016, (0, -1, 0), 0.06)
    box_on(f'elbow_guard.{S}', f'plate_elbow.{S}', t0, 1.0, 0.20, 0.05, 'tan', bevel=0.012)
    box_on(f'forearm_core.{S}', f'DEF-forearm.{S}', 0.24, 0.80, 0.16, 0.18, 'frame')
    t0 = plate_hinge(f'plate_forearm.{S}', f'DEF-forearm.{S}', 0.24, 0.045, 0.015, (-s, 0, 0), 0.05)
    box_on(f'forearm_yellow.{S}', f'plate_forearm.{S}', t0, 1.0, 0.24, 0.045, 'yellow', bevel=0.01)
    t0 = plate_hinge(f'plate_shield.{S}', f'DEF-forearm.{S}', 0.30, 0.045, 0.015, (-s, 0, 0), 0.05)
    box_on(f'forearm_shield.{S}', f'plate_shield.{S}', t0, 1.0, 0.30, 0.045, 'navy', taper=(0.8, 1), bevel=0.012)
    box_on(f'wrist_cuff.{S}', f'DEF-forearm.{S}', 0.78, 0.90, 0.22, 0.24, 'tan', bevel=0.015)
    # wrist: roll collar (stage 1) -> cardan cross (stage 2, pitch pin) -> hand fork on the yaw pin
    wh, wy, wx, wz, wL = frame(f'DEF-hand.{S}'); g1, g2 = f'GIM1-hand.{S}', f'GIM2-hand.{S}'
    cyl(f'wrist_roll_collar.{S}', wh - wy * 0.076, wh - wy * 0.05, 0.066, 'steel', g1, segs=28)
    for e in (-1, 1):
        finish(f'wrist_roll_cheek{e:+d}.{S}', box_m(axes_m(wh + wx * (e * 0.045) - wy * 0.017, wx, wy, wz), (0.012, 0.07, 0.05)), 'frame', g1, 0.003)
        finish(f'wrist_yaw_cheek{e:+d}.{S}', box_m(axes_m(wh + wz * (e * 0.045) + wy * 0.021, wx, wy, wz), (0.05, 0.078, 0.012)), 'frame', f'DEF-hand.{S}', 0.003)
    finish(f'wrist_cross.{S}', box_m(axes_m(wh, wx, wy, wz), (0.044, 0.044, 0.044)), 'frame', g2, 0.005)
    cyl(f'wrist_pitch_pin.{S}', wh - wx * 0.057, wh + wx * 0.057, 0.012, 'steel', g2, segs=12)
    cyl(f'wrist_yaw_pin.{S}', wh - wz * 0.057, wh + wz * 0.057, 0.012, 'steel', g2, segs=12)
    box(f'palm.{S}', (X, 0.03, 0.655), (0.15, 0.22, 0.09), 'frame', f'DEF-hand.{S}', 0.015)
    th_h, th_y = frame(f'f_thumb_0.{S}')[:2]
    cyl(f'thumb_turret.{S}', th_h - th_y * 0.003, th_h + th_y * 0.023, 0.022, 'steel', f'f_thumb_0.{S}', segs=20)
    for fn in list(FINGERS) + ['thumb']:
        for i in (1, 2, 3):
            bn = f'f_{fn}_{i}.{S}'
            knuckle(f'{bn}_knuckle', bn, R_K, 0.024)
            yoke(bn, R_K, 0.024, 0.007, R_K + GAP + 0.004, R_K + GAP + 0.004)
            t0 = (R_K + GAP) / frame(bn)[4]
            t1 = 1.0 if i == 3 else 1 - (R_K + GAP) / frame(bn)[4]
            box_on(f'{bn}_seg', bn, t0, t1, FW, FD, 'frame', bevel=0.008 if i < 3 else 0.013,
                   taper=(1, 0.75) if i == 3 else (1, 1))

# ---- secondary-motion parts
for S, s in SIDES:
    h, y, x, z, L = frame(f'piston_house.{S}')
    lat = V((s, 0, 0))
    cyl(f'piston_house_eye.{S}', h - lat * 0.022, h + lat * 0.022, 0.026, 'frame', f'piston_house.{S}', segs=16)
    cyl(f'piston_house_body.{S}', h + y * 0.02, h + y * 0.20, 0.028, 'sage', f'piston_house.{S}', segs=16)
    cyl(f'piston_house_gland.{S}', h + y * 0.195, h + y * 0.215, 0.022, 'frame', f'piston_house.{S}', segs=16)
    cyl(f'piston_mount_A.{S}', h - lat * 0.09, h + lat * 0.03, 0.012, 'steel', f'DEF-thigh.{S}', segs=12)
    h2, y2, x2, z2, L2 = frame(f'piston_rod.{S}')
    cyl(f'piston_rod_eye.{S}', h2 - lat * 0.02, h2 + lat * 0.02, 0.022, 'frame', f'piston_rod.{S}', segs=16)
    cyl(f'piston_rod_body.{S}', h2 + y2 * 0.018, h2 + y2 * 0.26, 0.013, 'steel', f'piston_rod.{S}', segs=12)
    cyl(f'piston_mount_B.{S}', h2 - lat * 0.10, h2 + lat * 0.03, 0.012, 'steel', f'DEF-shin.{S}', segs=12)
for nm in ('antenna_L', 'antenna_R'):
    hb = frame(f'{nm}_1')[0]
    cyl(f'{nm}_base', hb + V((0, 0, -0.05)), hb + V((0, 0, -0.004)), 0.028, 'teal', 'body', segs=16)
    for i in range(1, 4):
        h, y, x, z, L = frame(f'{nm}_{i}')
        cyl(f'{nm}_rod{i}', h + y * 0.006, h + y * (L - 0.006), 0.009 - 0.0015 * i, 'steel', f'{nm}_{i}', segs=10, bevel=0)
        sphere(f'{nm}_joint{i}', h, 0.012, 'frame', f'{nm}_{i}')
    sphere(f'{nm}_tip', h + y * L, 0.02, 'yellow', f'{nm}_3')
box('cable_bracket', (0.50, 0.565, 2.10), (0.05, 0.16, 0.04), 'frame', 'body', 0.008)
cyl('cable_hook', (0.50, 0.635, 2.10), (0.50, 0.635, 2.06), 0.012, 'steel', 'body', segs=10)
for i in range(1, 5):
    h, y, x, z, L = frame(f'cable_{i}')
    sphere(f'cable_bead{i}', h, 0.014, 'frame', f'cable_{i}')
    cyl(f'cable_link{i}', h + y * 0.01, h + y * (L - 0.01), 0.009, 'frame', f'cable_{i}', segs=10, bevel=0)
h, y, x, z, L = frame('cable_4')
cyl('cable_plug', h + y * (L - 0.012), h + y * (L + 0.06), 0.022, 'yellow', 'cable_4', segs=12)

# ---- hoses (curves hooked to bones: they bend and stretch with the joints)
HOSES = []
def hose(name, pts, r=0.016):
    HOSES.append((name, pts, r))
for S, s in SIDES:
    X = 0.86 * s
    ua, fa = frame(f'DEF-upper_arm.{S}'), frame(f'DEF-forearm.{S}')
    lat = V((-s, 0, 0))
    p0 = ua[0] + ua[1] * (ua[4] * 0.62) + lat * 0.135
    p3 = fa[0] + fa[1] * (fa[4] * 0.42) + lat * 0.10
    box(f'hose_fitting_up.{S}', p0 - lat * 0.012, (0.03, 0.04, 0.04), 'steel', f'DEF-upper_arm.{S}', 0.004)
    box(f'hose_fitting_fore.{S}', p3 - lat * 0.012, (0.05, 0.04, 0.04), 'steel', f'DEF-forearm.{S}', 0.004)
    p1 = ua[0] + ua[1] * (ua[4] * 0.95) + lat * 0.17
    p2 = fa[0] + fa[1] * (fa[4] * 0.10) + lat * 0.165
    hose(f'hose_elbow.{S}', [(p0, f'DEF-upper_arm.{S}'), (p1, f'DEF-upper_arm.{S}'), (p2, f'DEF-forearm.{S}'), (p3, f'DEF-forearm.{S}')])
for i, hx in enumerate((-0.10, 0.10)):
    a, b = V((hx, 0.20, 1.322)), V((hx * 1.2, 0.16, 1.19))
    box(f'hose_fitting_box{i}', a + V((0, 0, 0.004)), (0.04, 0.04, 0.02), 'steel', 'body', 0.004)
    box(f'hose_fitting_pelvis{i}', b + V((0, 0, -0.008)), (0.04, 0.04, 0.02), 'steel', 'hips', 0.004)
    hose(f'hose_waist{i}', [(a, 'body'), (a + V((hx * 0.5, 0.06, -0.05)), 'body'), (b + V((hx * 0.5, 0.06, 0.05)), 'hips'), (b, 'hips')], 0.018)

from mathutils.bvhtree import BVHTree
def _bvh(ob):
    me = ob.data
    return BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
for st in STRUTS:
    cands = [o for o, bn in PARTS if bn == st['parent'] and not o.name.startswith(st['skip'])]
    best = None
    for o in cands:
        hit = _bvh(o).ray_cast(st['h'] + st['a'] * (st['r'] * 1.05), st['a'], 0.5)
        if hit[0] is not None and (best is None or hit[3] < best): best = hit[3]
    ln = (best if best is not None else 0.06) + st['r'] * 1.05 + 0.012
    c = st['h'] + st['a'] * (ln / 2)
    finish(st['name'], box_m(axes_m(c, st['x'], st['a'], st['x'].cross(st['a'])), (st['w'], ln, st['d'])), st['mat'], st['parent'], 0.003)
    print('strut', st['name'], round(ln, 3), 'hit' if best is not None else 'NO HIT')

# parent all parts to bones (rigid)
for ob, bn in PARTS:
    b = arm_data.bones[bn]
    ob.parent = arm; ob.parent_type = 'BONE'; ob.parent_bone = bn
    ob.matrix_parent_inverse = (arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()

# ---------------------------------------------------------------- constraints
pbs = arm.pose.bones
for pb in pbs: pb.rotation_mode = 'XYZ'

def add_driver(con, prop_bone, prop):
    fc = con.driver_add('influence'); d = fc.driver; d.type = 'AVERAGE'
    v = d.variables.new(); v.name = 'ikfk'; v.type = 'SINGLE_PROP'
    v.targets[0].id = arm; v.targets[0].data_path = f'pose.bones["{prop_bone}"]["{prop}"]'

def prop(pb, name, val, desc):
    pb[name] = val
    ui = pb.id_properties_ui(name); ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=desc)

def copy_rot(owner, target, axes, infl):
    c = pbs[owner].constraints.new('COPY_ROTATION'); c.name = f'follow {target} {axes}'
    c.target = arm; c.subtarget = target; c.mix_mode = 'ADD'
    c.use_x, c.use_y, c.use_z = ('x' in axes), ('y' in axes), ('z' in axes)
    c.owner_space = c.target_space = 'LOCAL'; c.influence = infl
    return c

for S, s in SIDES:
    # leg IK
    sw = f'IK_foot.{S}'
    prop(pbs[sw], 'ik_fk', 1.0, 'Leg: 0 = FK, 1 = IK')
    ik = pbs[f'IK-shin.{S}'].constraints.new('IK'); ik.name = 'IK'
    ik.target = arm; ik.subtarget = f'MCH-ankle.{S}'; ik.pole_target = arm; ik.pole_subtarget = f'pole_knee.{S}'
    ik.chain_count = 2; ik.use_stretch = False
    # arm IK
    swa = f'IK_hand.{S}'
    prop(pbs[swa], 'ik_fk', 0.0, 'Arm: 0 = FK, 1 = IK')
    ik = pbs[f'IK-forearm.{S}'].constraints.new('IK'); ik.name = 'IK'
    ik.target = arm; ik.subtarget = swa; ik.pole_target = arm; ik.pole_subtarget = f'pole_elbow.{S}'
    ik.chain_count = 2; ik.use_stretch = False
    pbs[f'IK-upper_arm.{S}'].ik_stretch = pbs[f'IK-forearm.{S}'].ik_stretch = 0
    pbs[f'IK-thigh.{S}'].ik_stretch = pbs[f'IK-shin.{S}'].ik_stretch = 0
    # deform chains follow FK, blended to IK by the switch
    for n, ikb, swb in (('thigh', f'IK-thigh.{S}', sw), ('shin', f'IK-shin.{S}', sw), ('foot', f'IK-foot.{S}', sw),
                        ('toe', f'IK-toe.{S}', sw), ('upper_arm', f'IK-upper_arm.{S}', swa),
                        ('forearm', f'IK-forearm.{S}', swa), ('hand', swa, swa)):
        d = pbs[f'DEF-{n}.{S}']
        # hand / foot / toe copy only rotation: they stay pinned on their joint, whatever the controls do
        ct = 'COPY_ROTATION' if n in ('hand', 'foot', 'toe') else 'COPY_TRANSFORMS'
        c1 = d.constraints.new(ct); c1.name = 'FK'; c1.target = arm; c1.subtarget = f'FK-{n}.{S}'
        c2 = d.constraints.new(ct); c2.name = 'IK'; c2.target = arm; c2.subtarget = ikb
        add_driver(c2, swb, 'ik_fk')
    # floor for IK feet and hands
    for b, zmin in ((sw, 0.0), (swa, 0.10)):
        c = pbs[b].constraints.new('LIMIT_LOCATION'); c.name = 'floor'
        c.use_min_z = True; c.min_z = zmin; c.owner_space = 'WORLD'; c.use_transform_limit = True
    # armour auto-follow
    # armour linkages ride single gimbal stages: pauldron on the pitch drum, hip skirts on the roll / pitch stages
    copy_rot(f'plate_pauldron.{S}', f'GIM1-upper_arm.{S}', 'x', 0.30)
    copy_rot(f'skirt_side.{S}', f'GIM2-thigh.{S}', 'z', 1.0)
    copy_rot('skirt_front', f'GIM1-thigh.{S}', 'x', 0.25)
    # grip actuator closes every finger base (the later segments follow through their own linkage below)
    for fn in list(FINGERS) + ['thumb']:
        copy_rot(f'f_{fn}_1.{S}', f'grip.{S}', 'x', 1.0)
    c = pbs[f'grip.{S}'].constraints.new('LIMIT_ROTATION'); c.name = 'joint limits'; c.owner_space = 'LOCAL'
    c.use_limit_x = c.use_limit_y = c.use_limit_z = True; c.min_x, c.max_x = rad(-15), rad(90); c.use_transform_limit = True
    pbs[f'grip.{S}'].lock_rotation = (False, True, True); pbs[f'grip.{S}'].lock_location = (True, True, True)
    # finger base curls the whole finger
    for fn in list(FINGERS) + ['thumb']:
        for i in (2, 3):
            copy_rot(f'f_{fn}_{i}.{S}', f'f_{fn}_1.{S}', 'x', 0.8 if i == 2 else 0.6)

# gimbal stages: each copies ONE axis of its joint, decomposed in the joint's motor order
ORDERS = {}
for src, (order, st) in GIMBALS.items():
    for nm, a in st:
        c = pbs[nm].constraints.new('COPY_ROTATION'); c.name = f'motor {a}'
        c.target = arm; c.subtarget = src; c.mix_mode = 'REPLACE'; c.euler_order = order
        c.use_x, c.use_y, c.use_z = a == 'x', a == 'y', a == 'z'
        c.owner_space = c.target_space = 'LOCAL'
    base = src[4:] if src.startswith('DEF-') else src
    for n in (src, 'FK-' + base, 'IK-' + base):
        if n in pbs: pbs[n].rotation_mode = order; ORDERS[n] = order
arm['euler_orders'] = json.dumps(ORDERS)

rubber = bpy.data.materials.new('RB_rubber')
rubber.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = srgb('#222426')
rubber.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = 0.75
rubber.diffuse_color = srgb('#222426')
bpy.ops.object.mode_set(mode='OBJECT')
for name, pts, r in HOSES:
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = r; cu.bevel_resolution = 3; cu.resolution_u = 18; cu.use_fill_caps = True
    sp = cu.splines.new('NURBS'); sp.points.add(len(pts) - 1)
    for i, (p, bn) in enumerate(pts): sp.points[i].co = (p.x, p.y, p.z, 1)
    sp.order_u = 4; sp.use_endpoint_u = True
    cu.materials.append(rubber)
    ob = bpy.data.objects.new(name, cu); C_PARTS.objects.link(ob); ob['hose'] = True
    for i, (p, bn) in enumerate(pts):
        m = ob.modifiers.new(f'hook{i}', 'HOOK'); m.object = arm; m.subtarget = bn
        m.vertex_indices_set([i])
        b = arm.data.bones[bn]
        m.matrix_inverse = (arm.matrix_world @ b.matrix_local).inverted()
        m.center = p
bpy.ops.object.mode_set(mode='POSE')
for S in ('L', 'R'):
    c = pbs[f'piston_house.{S}'].constraints.new('DAMPED_TRACK'); c.target = arm; c.subtarget = f'MCH-pistonB.{S}'
    c = pbs[f'piston_rod.{S}'].constraints.new('DAMPED_TRACK'); c.target = arm; c.subtarget = f'MCH-pistonA.{S}'
for sp in SPRINGS:
    for bn, tn in zip(sp['bones'], sp['targets']):
        c = pbs[bn].constraints.new('DAMPED_TRACK'); c.name = 'spring'; c.target = arm; c.subtarget = tn
arm['springs'] = json.dumps(SPRINGS)
arm['springs_on'] = 1
arm.id_properties_ui('springs_on').update(min=0, max=1, description='Live spring motion on antennas and cable')

# remember the spec for later scripts
spec = {n: dict(head=list(b['head']), tail=list(b['tail']), z=list(b['z']), parent=b['parent'],
                coll=b['coll'], ctrl=b['ctrl']) for n, b in BONES.items()}
arm['rig_spec'] = json.dumps(spec)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT, len(PARTS), 'parts', len(BONES), 'bones')
