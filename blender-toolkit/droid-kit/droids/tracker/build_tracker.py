"""Tracked porter droid (droid 5): twin rubber-padded tracks on a pivoting frame, sprung chassis, scoop lift,
turret waist, leaning body with a dark-glass screen face, two telescoping sensor stalks, scrap bin with a lid, tow hook.
Robot-logic rig: every moving bone turns (or slides) on ONE axis and shows the pin / hub / rail that carries it.
Run: python3 build_tracker.py out.blend
Droid faces -Y, its left side is +X (same as the other droids). Ground is z = 0.
"""
import bpy, bmesh, math, sys, json
from mathutils import Vector, Matrix

OUT = sys.argv[-1] if sys.argv[-1].endswith('.blend') else '/tmp/tracker.blend'
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
V = Vector
rad = math.radians


def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c] + [1]


PALETTE = {
    'paint': ('#2C6764', 0.55),   # body, chassis, track skirts: worn deep teal
    'accent': ('#D8642A', 0.5),   # warning accents: scoop lip, stalk collars, bin lid stripe
    'cream': ('#E6D3A3', 0.55),   # trim
    'grey': ('#3D4349', 0.5),     # turret, bezel, lift arms: gunmetal
    'frame': ('#2A2C2F', 0.5),    # mechanics (polymer where the name says joint, bare metal otherwise)
    'steel': ('#6B6F73', 0.35),   # pins, bolts, axles, track links
    'core': ('#1C1E20', 0.7),     # inner parts
    'rubber': ('#1E1F20', 0.85),  # track pads, tyres
}
MATS = {}
for k, (hx, rough) in PALETTE.items():
    m = bpy.data.materials.new('RB_' + k)
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = srgb(hx); b.inputs['Roughness'].default_value = rough
    m.diffuse_color = srgb(hx)
    MATS[k] = m


def emissive(name, hx, strength):
    m = bpy.data.materials.new(name); nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = srgb('#111111')
    b.inputs['Emission Color'].default_value = srgb(hx)
    b.inputs['Emission Strength'].default_value = strength
    b.inputs['Roughness'].default_value = 0.25
    m.diffuse_color = srgb(hx)
    gl = nt.nodes.new('ShaderNodeEmission'); gl.name = gl.label = 'Glow'
    gl.inputs['Color'].default_value = srgb(hx); gl.inputs['Strength'].default_value = 0.0
    add = nt.nodes.new('ShaderNodeAddShader'); out = nt.nodes.get('Material Output')
    nt.links.new(b.outputs[0], add.inputs[0]); nt.links.new(gl.outputs[0], add.inputs[1]); nt.links.new(add.outputs[0], out.inputs['Surface'])
    return m


MATS['face'] = emissive('TR_face_glow', '#43E4FF', 6.0)          # eyes + mouth on the screen
MATS['stalk'] = emissive('RB_Stalk_Glow', '#43E4FF', 4.0)        # stalk cap rings (antenna-tip hook)
MATS['lamp'] = emissive('TR_headlamp', '#FFE3B0', 3.0)
LEDCOL = {'green': '#5CFF7A', 'amber': '#FFB13B', 'red': '#FF3B2E'}
for k, hx in LEDCOL.items(): MATS['RB_LED_' + k] = emissive('RB_LED_' + k, hx, 4.0)
scr = bpy.data.materials.new('TR_screen'); sb = scr.node_tree.nodes.get('Principled BSDF')
sb.inputs['Base Color'].default_value = srgb('#06080A'); sb.inputs['Roughness'].default_value = 0.6
scr.diffuse_color = srgb('#0E1214'); MATS['screen'] = scr
glass = bpy.data.materials.new('TR_glass'); gb = glass.node_tree.nodes.get('Principled BSDF')
gb.inputs['Base Color'].default_value = (0.9, 0.95, 1, 1); gb.inputs['Roughness'].default_value = 0.03
gb.inputs['Transmission Weight'].default_value = 1.0; gb.inputs['IOR'].default_value = 1.2
glass.diffuse_color = (0.3, 0.4, 0.5, 0.3); MATS['glass'] = glass


def coll(name, parent=None):
    c = bpy.data.collections.new(name); (parent or scene.collection).children.link(c); return c
C_ROBOT = coll('Tracker'); C_PARTS = coll('Tracker_Parts', C_ROBOT); C_LIGHTS = coll('Tracker_Lights', C_ROBOT)
C_TREAD = coll('Tracker_Treads', C_ROBOT)

# ================================================================ layout
TX = 0.29            # track centre line (x)
TW = 0.11            # track width
TI = TX - TW / 2     # inner edge of the links (0.235)
TO = TX + TW / 2
LT = 0.018           # link thickness incl. the cleat
GAP = 0.005          # wheel to link clearance
SPR = (0.215, 0.125, 0.098)    # sprocket (y, z, r): rear, drives the track
IDL = (-0.225, 0.142, 0.085)   # idler: front, raised
RW_R = 0.040
RW_Z = 0.0020 + LT + GAP + RW_R
ROAD = [(y, RW_Z, RW_R) for y in (-0.100, -0.015, 0.070)]
WHEELS = [('sprocket', SPR), ('idler', IDL)] + [(f'road_{i}', w) for i, w in enumerate(ROAD)]
PLATE_IN = TI - 0.010          # inner frame plate x range
PLATE_OUT = TO + 0.002         # outer skirt x range
CH = dict(x=0.172, y0=-0.250, y1=0.250, z0=0.180, z1=0.310)   # chassis box
BEAM_Z = 0.120
WAIST_Z = CH['z1']
LEAN_Z = WAIST_Z + 0.056
BODY = dict(w=0.42, d=0.36, z0=LEAN_Z + 0.040, h=0.46, r=0.065)
BZ1 = BODY['z0'] + BODY['h']
FRONT_Y = -BODY['d'] / 2
SCREEN_Z = BODY['z0'] + 0.285
SCR_W, SCR_H = 0.270, 0.205

# ================================================================ bones
BONES = {}
def B(name, head, tail, z, parent=None, coll='Mechanics', ctrl=False, connect=False):
    BONES[name] = dict(head=V(head), tail=V(tail), z=V(z), parent=parent, connect=connect, coll=coll, ctrl=ctrl)

def frame(name):
    b = BONES[name]
    y = (b['tail'] - b['head']).normalized()
    z = (b['z'] - y * b['z'].dot(y)).normalized()
    x = y.cross(z)
    return b['head'], y, x, z, (b['tail'] - b['head']).length

def zfor(y, xaxis):
    return V(xaxis).cross(V(y).normalized())

UP, FWD, BACK, XA = V((0, 0, 1)), V((0, -1, 0)), V((0, 1, 0)), V((1, 0, 0))
SIDES = (('L', 1), ('R', -1))

B('root', (0, 0, 0), (0, -0.45, 0), UP, coll='Body', ctrl=True)
# tracks: each frame pitches on the cross beam (hinge X); wheels spin on their axles (bone along +X, spin = rot Y)
for S, s in SIDES:
    B(f'track_frame.{S}', (s * PLATE_IN, 0, BEAM_Z), (s * PLATE_IN + 0.06, 0, BEAM_Z), UP, 'root', coll='Tracks', ctrl=True)
    for wn, (y, z, r) in WHEELS:
        B(f'{wn}.{S}', (TX * s - 0.02, y, z), (TX * s + 0.02, y, z), UP, f'track_frame.{S}', coll='Tracks')
# chassis on its suspension: heave (slide local Y = up), pitch (X), roll (Z = forward axis)
B('suspension', (0, 0, CH['z0'] + 0.04), (0, 0, CH['z0'] + 0.12), FWD, 'root', coll='Body', ctrl=True)
B('chassis', (0, 0, CH['z0'] + 0.04), (0, 0, CH['z0'] + 0.10), FWD, 'suspension', coll='Body')
# struts: housing on the track frame, rod on the chassis, coil stretches between them
STRUTS = []
for S, s in SIDES:
    for k, y in (('f', -0.135), ('b', 0.135)):
        lo = V((s * 0.1945, y, 0.175)); hi = V((s * 0.1945, y + 0.0, 0.292))
        d = (hi - lo).normalized()
        STRUTS.append((S, s, k, lo, hi))
        B(f'strut_low.{S}{k}', lo, lo + d * 0.06, FWD, f'track_frame.{S}')
        B(f'strut_rod.{S}{k}', hi, hi - d * 0.06, FWD, 'chassis')
        B(f'strut_coil.{S}{k}', lo + d * 0.022, hi - d * 0.022, FWD, f'strut_low.{S}{k}')
        B(f'MCH-strut_lo.{S}{k}', lo, lo + V((0, 0, -0.02)), FWD, f'track_frame.{S}')
        B(f'MCH-strut_hi.{S}{k}', hi, hi + V((0, 0, 0.02)), FWD, 'chassis')
# scoop: lift arms hinge on the chassis front (X), scoop tilts at the arm tips (X); lift ram between them
PIV = V((0, CH['y0'] - 0.026, 0.272))
TIP = V((0, -0.445, 0.125))
B('scoop_lift', PIV, TIP, zfor(TIP - PIV, XA), 'chassis', coll='Scoop', ctrl=True)
B('scoop_tilt', TIP, TIP + V((0, -0.06, 0)), zfor((0, -1, 0), XA), 'scoop_lift', coll='Scoop', ctrl=True)
RAM_A = V((0, CH['y0'] - 0.014, CH['z0'] + 0.036))
RAM_B = PIV + (TIP - PIV) * 0.62 + V((0, 0, -0.024))
B('ram_house', RAM_A, RAM_A + (RAM_B - RAM_A).normalized() * 0.06, XA, 'chassis')
B('ram_rod', RAM_B, RAM_B - (RAM_B - RAM_A).normalized() * 0.06, XA, 'scoop_lift')
B('MCH-ramA', RAM_A, RAM_A + V((0, 0, -0.02)), FWD, 'chassis')
B('MCH-ramB', RAM_B, RAM_B + V((0, 0, -0.02)), FWD, 'scoop_lift')
# tow hook: swings on a pin at the chassis rear (X), dangles on a spring
HK = V((0, CH['y1'] + 0.030, CH['z0'] + 0.030))
B('tow_hook', HK, HK + V((0, 0, -0.07)), BACK, 'chassis', coll='Body', ctrl=True)
B('SPR-tow_hook', HK + V((0, 0, -0.07)), HK + V((0, 0, -0.09)), BACK, 'chassis')
# waist turret (yaw), lean yoke (pitch on side pins), body (sway roll on a centre bearing)
B('waist', (0, 0, WAIST_Z), (0, 0, WAIST_Z + 0.04), FWD, 'chassis', coll='Body', ctrl=True)
B('lean', (0, 0, LEAN_Z), (0, 0, LEAN_Z + 0.08), FWD, 'waist', coll='Body', ctrl=True)
B('body', (0, 0, LEAN_Z + 0.040), (0, -0.1, LEAN_Z + 0.040), UP, 'lean', coll='Body', ctrl=True)
# face: eyes and mouth slide on the screen (bone local X/Z) and scale (blink / squash); bones point out of the screen
EYE_Y = FRONT_Y - 0.0085
for S, s in SIDES:
    p = V((s * 0.062, EYE_Y, SCREEN_Z + 0.018))
    B(f'eye.{S}', p, p + V((0, -0.04, 0)), UP, 'body', coll='Face', ctrl=True)
MO = V((0, EYE_Y, SCREEN_Z - 0.052))
B('mouth', MO, MO + V((0, -0.04, 0)), UP, 'body', coll='Face', ctrl=True)
# stalks: roll stage (sideways droop, about forward axis = local Z) -> pitch stage (X) -> telescope (slide local Y) -> sprung tip
SPRINGS = []
STK = {}
for S, s in SIDES:
    base = V((s * 0.115, 0.035, BZ1))
    STK[S] = base
    B(f'stalk_roll.{S}', base + V((0, 0, 0.024)), base + V((0, 0, 0.05)), FWD, 'body', coll='Stalks', ctrl=True)
    B(f'stalk_pitch.{S}', base + V((0, 0, 0.032)), base + V((0, 0, 0.09)), FWD, f'stalk_roll.{S}', coll='Stalks', ctrl=True)
    B(f'stalk_ext.{S}', base + V((0, 0, 0.060)), base + V((0, 0, 0.17)), FWD, f'stalk_pitch.{S}', coll='Stalks', ctrl=True)
    B(f'stalk_tip.{S}', base + V((0, 0, 0.182)), base + V((0, 0, 0.247)), FWD, f'stalk_ext.{S}', coll='Stalks')
    B(f'SPR-stalk_tip.{S}', base + V((0, 0, 0.247)), base + V((0, 0, 0.267)), FWD, f'stalk_ext.{S}')
    SPRINGS.append(dict(bones=[f'stalk_tip.{S}'], targets=[f'SPR-stalk_tip.{S}'], k=0.16, damp=0.14, grav=0.0, max_deg=12))
SPRINGS.append(dict(bones=['tow_hook'], targets=['SPR-tow_hook'], k=0.08, damp=0.10, grav=0.0015, max_deg=35))
# scrap bin on the back: lid hinges on the top-back edge (X)
BIN = dict(x=0.150, y0=BODY['d'] / 2 + 0.006, y1=BODY['d'] / 2 + 0.130, z0=BODY['z0'] + 0.090, z1=BODY['z0'] + 0.330)
LH = V((0, BIN['y1'] - 0.004, BIN['z1'] + 0.010))
B('bin_lid', LH, LH + V((0, -0.10, 0)), UP, 'body', coll='Body', ctrl=True)

# ---------------------------------------------------------------- armature
arm_data = bpy.data.armatures.new('TrackerRig'); arm = bpy.data.objects.new('TrackerRig', arm_data)
C_ROBOT.objects.link(arm); arm.show_in_front = True
bpy.context.view_layer.objects.active = arm; arm.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
ORDER = ['Body', 'Face', 'Stalks', 'Tracks', 'Scoop', 'Mechanics']
bcolls = {n: arm_data.collections.new(n) for n in ORDER}
ebs = arm_data.edit_bones
for n, b in BONES.items():
    eb = ebs.new(n); eb.head = b['head']; eb.tail = b['tail']; eb.align_roll(b['z']); eb.use_deform = False
    bcolls[b['coll']].assign(eb)
for n, b in BONES.items():
    if b['parent']: ebs[n].parent = ebs[b['parent']]; ebs[n].use_connect = b['connect']
bpy.ops.object.mode_set(mode='POSE')
bcolls['Mechanics'].is_visible = False

# ================================================================ geometry helpers
PARTS = []
def finish(name, bm, mat, bone, bevel=0.0, smooth=40, led=None, segs=2, coll_=None):
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    if bevel > 0:
        edges = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > 0.6]
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=segs, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    me.materials.append(MATS[mat])
    for pl in me.polygons: pl.use_smooth = True
    me.set_sharp_from_angle(angle=rad(smooth))
    ob = bpy.data.objects.new(name, me); (coll_ or (C_LIGHTS if led else C_PARTS)).objects.link(ob)
    ob['rig_bone'] = bone
    if led: ob['rb_led'] = led
    PARTS.append((ob, bone))
    return ob

def axes_m(c, x, y, z):
    m = Matrix((x, y, z)).transposed().to_4x4(); m.translation = V(c); return m
IDM = lambda c: axes_m(c, (1, 0, 0), (0, 1, 0), (0, 0, 1))

def frame_m(c, d):
    d = V(d).normalized()
    x = d.orthogonal().normalized(); y = d.cross(x)
    return axes_m(c, x, y, d)

def box_m(M, size, taper=(1, 1)):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        if v.co.z > 0: v.co.x *= taper[0]; v.co.y *= taper[1]
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm

def box(name, M, size, mat, bone, bevel=0.003, taper=(1, 1), segs=2, led=None):
    return finish(name, box_m(M, size, taper), mat, bone, bevel, segs=segs, led=led)

def bbox(name, lo, hi, mat, bone, bevel=0.003, segs=2, taper=(1, 1)):
    lo, hi = V(lo), V(hi)
    return box(name, IDM((lo + hi) / 2), hi - lo, mat, bone, bevel, taper, segs)

def cyl(name, p1, p2, r, mat, bone, segs=24, bevel=0.0015, r2=None, led=None):
    p1, p2 = V(p1), V(p2); d = p2 - p1
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs, radius1=r, radius2=r2 or r, depth=d.length)
    M = Matrix.Translation((p1 + p2) / 2) @ V((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return finish(name, bm, mat, bone, bevel, led=led)

def hexbolt(name, p, n, r, mat='steel', bone='body', h=None):
    n = V(n).normalized(); h = h or r * 0.7
    return cyl(name, V(p) - n * 0.002, V(p) + n * h, r, mat, bone, segs=6, bevel=min(0.0008, r * 0.2))

def lathe(name, prof, M, mat, bone, segs=64, ph0=0.0, ph1=360.0, bevel=0.0, smooth=40, led=None):
    """revolve a closed (r, z) profile about local Z, place with M"""
    full = abs(ph1 - ph0) >= 359.999
    n = segs if full else max(2, int(round(segs * abs(ph1 - ph0) / 360.0)) + 1)
    bm = bmesh.new(); rings = []
    for i in range(n):
        a = rad(ph0 + (ph1 - ph0) * i / (n if full else n - 1))
        rings.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in prof])
    m = len(prof)
    for i in range(n if full else n - 1):
        A, Bv = rings[i], rings[(i + 1) % n]
        for j in range(m):
            k = (j + 1) % m
            try: bm.faces.new((A[j], A[k], Bv[k], Bv[j]))
            except ValueError: pass
    if not full:
        try: bm.faces.new(list(reversed(rings[0])))
        except ValueError: pass
        try: bm.faces.new(rings[-1])
        except ValueError: pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return finish(name, bm, mat, bone, bevel, smooth, led)

def ring_prof(r0, r1, z0, z1):
    return [(r0, z0), (r1, z0), (r1, z1), (r0, z1)]

def prism(name, pts2d, M, depth, mat, bone, bevel=0.002, segs=2, z0=None):
    """extrude a closed 2D outline (local XY) along local Z by depth, place with M"""
    bm = bmesh.new()
    z0 = -depth / 2 if z0 is None else z0
    vs = [bm.verts.new((x, y, z0)) for x, y in pts2d]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in ext['geom']:
        if isinstance(v, bmesh.types.BMVert): v.co.z += depth
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return finish(name, bm, mat, bone, bevel, segs=segs)

def rrect(w, h, r, n=8):
    """rounded rectangle outline, centred, counter-clockwise"""
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = rad(a0 + 90 * i / n); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts

def rbox(name, c, size, r, mat, bone, segs=6):
    """box with big rounded edges (all edges radius r)"""
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=r, offset_type='OFFSET', segments=segs, profile=0.5, affect='EDGES', clamp_overlap=True)
    bmesh.ops.transform(bm, matrix=IDM(c), verts=bm.verts)
    return finish(name, bm, mat, bone, 0.0, smooth=35)

def hull2d(circles, n=96):
    """belt path round a set of circles (u, v, r): convex hull of their samples, counter-clockwise"""
    pts = []
    for u, v, r in circles:
        for i in range(n): a = 2 * math.pi * i / n; pts.append((u + r * math.cos(a), v + r * math.sin(a)))
    pts = sorted(set(pts))
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]

def resample(loop, step):
    L = [V((p[0], p[1], 0)) for p in loop]
    seg = [(L[i], L[(i + 1) % len(L)]) for i in range(len(L))]
    tot = sum((b - a).length for a, b in seg)
    n = max(8, int(round(tot / step))); st = tot / n
    out, acc, i, a, b = [], 0.0, 0, *seg[0]
    t = 0.0
    for k in range(n):
        target = k * st
        while acc + (seg[i][1] - seg[i][0]).length < target - 1e-12:
            acc += (seg[i][1] - seg[i][0]).length; i = (i + 1) % len(seg)
        a, b = seg[i]; f = (target - acc) / max((b - a).length, 1e-12)
        out.append(a.lerp(b, f))
    return out, tot

# ================================================================ TRACKS
TRACK = {}
for S, s in SIDES:
    fb = f'track_frame.{S}'
    # belt path (u = y, v = z) round the wheels, offset to the link centre line
    path_c = [(y, z, r + GAP + LT / 2) for _, (y, z, r) in WHEELS]
    loop = hull2d(path_c, 180)
    pts, Lloop = resample(loop, 0.004)
    NL = int(round(Lloop / 0.045)); PITCH = Lloop / NL
    TRACK[S] = dict(L=Lloop, N=NL, pitch=PITCH)
    cu = bpy.data.curves.new(f'track_path.{S}', 'CURVE'); cu.dimensions = '2D'; cu.use_path = True
    cu.path_duration = 1000
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts): sp.points[i].co = (p.x, p.y, 0, 1)
    sp.use_cyclic_u = True
    path_ob = bpy.data.objects.new(f'track_path.{S}', cu); C_TREAD.objects.link(path_ob)
    path_ob.matrix_world = axes_m((TX * s, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))   # local XY = world YZ, local Z = +X
    path_ob['rig_bone'] = fb; path_ob['track_path'] = S
    path_ob.hide_render = True
    PARTS.append((path_ob, fb))
    TRACK[S]['path'] = path_ob
    # one link: local X along the path, local Z across the track, local Y = inward (path is counter-clockwise)
    bm = bmesh.new()
    lk = PITCH * 0.86
    plate = box_m(IDM((PITCH / 2, LT / 2 - 0.006, 0)), (lk, 0.012, TW), (1, 1))
    bm.free(); bm = plate
    cle = box_m(IDM((PITCH / 2, -LT / 2 + 0.003, 0)), (lk * 0.42, 0.0061, TW * 0.92))
    me_c = bpy.data.meshes.new('tmp'); cle.to_mesh(me_c); cle.free(); bm.from_mesh(me_c); bpy.data.meshes.remove(me_c)
    # guide horn on the inner side, between the wheel halves
    horn = box_m(IDM((PITCH / 2, LT / 2 + 0.0, 0)), (lk * 0.36, 0.003, 0.012))
    me_h = bpy.data.meshes.new('tmp'); horn.to_mesh(me_h); horn.free(); bm.from_mesh(me_h); bpy.data.meshes.remove(me_h)
    link_me = bpy.data.meshes.new(f'track_link.{S}'); bm.to_mesh(link_me); bm.free()
    link_me.materials.append(MATS['steel'])
    for pl in link_me.polygons: pl.use_smooth = False
    links = []
    for i in range(NL):
        ob = bpy.data.objects.new(f'track_link_{i:02d}.{S}', link_me); C_TREAD.objects.link(ob)
        ob['rig_bone'] = fb; ob['tread'] = S
        c = ob.constraints.new('FOLLOW_PATH'); c.target = path_ob; c.use_curve_follow = True; c.use_fixed_location = True
        c.forward_axis = 'FORWARD_X'; c.up_axis = 'UP_Z'
        c.offset_factor = i / NL
        pin = bpy.data.objects.new(f'track_pin_{i:02d}.{S}', None); C_TREAD.objects.link(pin)
        pin.empty_display_size = 0.004; pin['rig_bone'] = fb
        pc = pin.constraints.new('FOLLOW_PATH'); pc.target = path_ob; pc.use_fixed_location = True; pc.offset_factor = i / NL
        links.append((ob, c, pin, pc))
    # each link spans pin i -> pin i+1 (a chord, like a real pinned track): aim its X at the next pin
    for i, (ob, c, pin, pc) in enumerate(links):
        dt = ob.constraints.new('DAMPED_TRACK'); dt.target = links[(i + 1) % NL][2]; dt.track_axis = 'TRACK_X'
    TRACK[S]['links'] = links

    # ---- wheels: sprocket (drive, rear), idler (front), road wheels (bottom); each spins on its own axle bone
    AX = lambda y, z, x0, x1: (V((x0, y, z)), V((x1, y, z)))
    for wn, (y, z, r) in WHEELS:
        bone = f'{wn}.{S}'
        M = axes_m((TX * s, y, z), (0, 1, 0), (0, 0, 1), (1, 0, 0))   # lathe axis = world X
        hw = 0.040
        if wn == 'sprocket':
            prof = [(0.0145, -hw), (r - 0.010, -hw), (r, -hw + 0.008), (r, -0.010), (r - 0.012, -0.004),
                    (r - 0.012, 0.004), (r, 0.010), (r, hw - 0.008), (r - 0.010, hw), (0.0145, hw)]
            lathe(f'sprocket_wheel.{S}', prof, M, 'grey', bone, segs=72)
            for k in range(6):
                a = 2 * math.pi * k / 6
                for e in (-1, 1):
                    p = V((TX * s + e * (hw + 0.0005), y + 0.045 * math.cos(a), z + 0.045 * math.sin(a)))
                    hexbolt(f'sprocket_bolt_{k}_{e:+d}.{S}', p, (e, 0, 0), 0.0045, bone=bone, h=0.004)
            lathe(f'sprocket_hub.{S}', ring_prof(0.0145, 0.028, hw, hw + 0.012), M, 'frame', bone, segs=36)
            lathe(f'sprocket_hub_in.{S}', ring_prof(0.0145, 0.028, -hw - 0.012, -hw), M, 'frame', bone, segs=36)
        else:
            tyre = 0.012 if wn.startswith('road') else 0.014
            prof = [(0.0145, -hw), (r - tyre, -hw), (r - tyre, -hw + 0.002), (0.0145, -hw + 0.002)]
            # two discs with a rubber tyre each, a gap in the middle for the guide horns
            for e, nm in ((-1, 'a'), (1, 'b')):
                z0, z1 = (-hw, -0.009) if e < 0 else (0.009, hw)
                lathe(f'{wn}_disc_{nm}.{S}', [(0.0145, z0), (r - tyre + 0.001, z0), (r - tyre + 0.001, z1), (0.0145, z1)], M, 'grey', bone, segs=48, bevel=0.0)
                lathe(f'{wn}_tyre_{nm}.{S}', [(r - tyre, z0 + 0.001), (r - 0.002, z0 + 0.001), (r, z0 + 0.004), (r, z1 - 0.004),
                                             (r - 0.002, z1 - 0.001), (r - tyre, z1 - 0.001)], M, 'rubber', bone, segs=64)
            lathe(f'{wn}_web.{S}', ring_prof(0.0145, r - tyre - 0.004, -0.009, 0.009), M, 'grey', bone, segs=40)
            for k in range(5 if wn == 'idler' else 4):
                a = 2 * math.pi * k / (5 if wn == 'idler' else 4) + 0.3
                p = V((TX * s + s * (hw + 0.0005), y + r * 0.42 * math.cos(a), z + r * 0.42 * math.sin(a)))
                hexbolt(f'{wn}_bolt_{k}.{S}', p, (s, 0, 0), 0.0035, bone=bone, h=0.003)
        # axle: from the inner plate to the outer skirt (on the frame), hub caps on the outer skirt
        cyl(f'{wn}_axle.{S}', (s * (PLATE_IN + 0.004), y, z), (s * (PLATE_OUT + 0.004), y, z), 0.013, 'steel', fb, segs=18, bevel=0)
        cyl(f'{wn}_cap.{S}', (s * (PLATE_OUT + 0.008), y, z), (s * (PLATE_OUT + 0.018), y, z), 0.020, 'frame', fb, segs=20)
    # frame plates: inner plate and outer skirt follow the wheel layout, inset so the links clear them
    plate_c = [(y, z, max(r - 0.012, 0.03)) for _, (y, z, r) in WHEELS]
    outline = hull2d(plate_c, 48)
    Mp_in = axes_m((s * (PLATE_IN - 0.004), 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))
    prism(f'track_plate_in.{S}', outline, Mp_in, 0.008, 'grey', fb, bevel=0.0025)
    Mp_out = axes_m((s * (PLATE_OUT + 0.004), 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))
    # outer skirt: painted, with a big oval lightening cut-out look done as a raised rim
    prism(f'track_skirt.{S}', outline, Mp_out, 0.008, 'paint', fb, bevel=0.003)
    inner = hull2d([(y, z, max(r - 0.040, 0.012)) for _, (y, z, r) in WHEELS if not _.startswith('road_1')], 32)
    # pivot hub on the inner plate round the cross beam (bore clears the beam by 1 mm)
    lathe(f'track_pivot_hub.{S}', ring_prof(0.019, 0.034, -0.026, 0.0), axes_m((s * (PLATE_IN - 0.008), 0, BEAM_Z), (0, 1, 0), (0, 0, 1) if s > 0 else (0, 0, -1), (s, 0, 0) if True else None) if False else
          axes_m((s * (PLATE_IN - 0.008), 0, BEAM_Z), (0, s, 0), (0, 0, 1), (s, 0, 0)), 'frame', fb, segs=36)
    # strut lugs on the inner plate
    for _, s2, k, lo, hi in [t for t in STRUTS if t[0] == S]:
        xa, xb = sorted((lo.x + s * 0.0115, s * (PLATE_IN - 0.0082)))
        bbox(f'strut_lug_low.{S}{k}', (xa, lo.y - 0.013, lo.z - 0.013), (xb, lo.y + 0.013, lo.z + 0.013), 'frame', fb, 0.002)
    # bolt row on the skirt
    for k in range(7):
        yy = -0.17 + k * 0.058
        hexbolt(f'skirt_bolt_{k}.{S}', (s * (PLATE_OUT + 0.008), yy, 0.20 - 0.0 * k), (s, 0, 0), 0.004, bone=fb, h=0.003)

# cross beam on the root (the track frames pivot on its ends)
cyl('cross_beam', (-(PLATE_IN - 0.0095), 0, BEAM_Z), ((PLATE_IN - 0.0095), 0, BEAM_Z), 0.018, 'steel', 'root', segs=24, bevel=0.001)
for s in (-1, 1):
    cyl(f'cross_beam_collar{s:+d}', (s * 0.10, 0, BEAM_Z), (s * 0.14, 0, BEAM_Z), 0.024, 'frame', 'root', segs=24)

# ================================================================ CHASSIS
ch = CH
rbox('chassis_hull', ((0, 0, (ch['z0'] + ch['z1']) / 2)), (2 * ch['x'], ch['y1'] - ch['y0'], ch['z1'] - ch['z0']), 0.028, 'paint', 'chassis')
bbox('chassis_deck_plate', (-0.15, -0.21, ch['z1'] - 0.002), (0.15, 0.21, ch['z1'] + 0.004), 'grey', 'chassis', 0.002)
# front bumper bar with rubber blocks, rear hitch plate
bbox('bumper_bar', (-0.17, ch['y0'] - 0.010, ch['z0'] + 0.002), (0.17, ch['y0'] + 0.004, ch['z0'] + 0.020), 'frame', 'chassis', 0.003)
bbox('hitch_plate', (-0.06, ch['y1'] - 0.004, ch['z0'] + 0.010), (0.06, ch['y1'] + 0.012, ch['z0'] + 0.070), 'grey', 'chassis', 0.003)
for e in (-1, 1):
    bbox(f'hitch_cheek{e:+d}', (e * 0.024 - 0.006, ch['y1'] + 0.012, HK.z - 0.014), (e * 0.024 + 0.006, ch['y1'] + 0.042, HK.z + 0.014), 'frame', 'chassis', 0.002)
cyl('hitch_pin', (-0.033, HK.y, HK.z), (0.033, HK.y, HK.z), 0.004, 'steel', 'chassis', segs=12, bevel=0)
# tow hook: eye round the pin, shank, hook
lathe('tow_hook_eye', ring_prof(0.0052, 0.012, -0.008, 0.008), axes_m(HK, (0, 1, 0), (0, 0, 1), (1, 0, 0)), 'steel', 'tow_hook', segs=24)
cyl('tow_hook_shank', HK + V((0, 0, -0.011)), HK + V((0, 0, -0.052)), 0.0065, 'steel', 'tow_hook', segs=12)
hk_c = HK + V((0, 0.0, -0.068))
lathe('tow_hook_hook', [(0.012, -0.004), (0.020, -0.004), (0.020, 0.004), (0.012, 0.004)], axes_m(hk_c, (0, 1, 0), (0, 0, 1), (1, 0, 0)), 'steel', 'tow_hook', segs=32, ph0=90, ph1=330)
# side vents and grab handles on the chassis
for S, s in SIDES:
    for k in range(5):
        bbox(f'chassis_vent_{k}.{S}', (s * ch['x'] - 0.003, -0.080 + k * 0.024, ch['z0'] + 0.050), (s * ch['x'] + 0.003, -0.068 + k * 0.024, ch['z0'] + 0.095), 'frame', 'chassis', 0.001)
# headlamps on the chassis front corners
for S, s in SIDES:
    c = V((s * 0.115, ch['y0'] - 0.004, ch['z1'] - 0.040))
    cyl(f'headlamp_housing.{S}', c + V((0, 0.010, 0)), c + V((0, -0.016, 0)), 0.024, 'grey', 'chassis', segs=28)
    cyl(f'headlamp.{S}', c + V((0, -0.016, 0)), c + V((0, -0.019, 0)), 0.019, 'lamp', 'chassis', segs=28, led='lamp')
# struts: housing (track frame) + rod (chassis) + coil; mounts
for S, s, k, lo, hi in STRUTS:
    d = (hi - lo).normalized()
    lathe(f'strut_house.{S}{k}', [(0.0068, 0.012), (0.0105, 0.004), (0.0105, 0.062), (0.0068, 0.062)], frame_m(lo, d), 'frame', f'strut_low.{S}{k}', segs=16)
    cyl(f'strut_rodpart.{S}{k}', hi - d * 0.004, hi - d * 0.075, 0.0055, 'steel', f'strut_rod.{S}{k}', segs=12, bevel=0)
    cyl(f'strut_eye_hi.{S}{k}', hi + V((-0.010, 0, 0)), hi + V((0.010, 0, 0)), 0.008, 'frame', f'strut_rod.{S}{k}', segs=14)
    bbox(f'strut_lug_hi.{S}{k}', (s * ch['x'] - (0.0 if s > 0 else 0.018) if s > 0 else -ch['x'] - 0.018 + 0.0, hi.y - 0.012, hi.z - 0.006),
         (s * ch['x'] + 0.018 if s > 0 else -ch['x'] + 0.0, hi.y + 0.012, hi.z + 0.012), 'frame', 'chassis', 0.002) if False else None
# coils as one mesh each, stretched by their bone
def coil(name, p0, p1, r, wire, turns, bone):
    d = (p1 - p0); L = d.length; n = int(turns * 24)
    bm = bmesh.new()
    prof = [V((wire * math.cos(2 * math.pi * j / 8), 0, wire * math.sin(2 * math.pi * j / 8))) for j in range(8)]
    rings = []
    for i in range(n + 1):
        t = i / n; a = 2 * math.pi * turns * t
        c = V((r * math.cos(a), r * math.sin(a), L * t))
        tang = V((-r * math.sin(a) * 2 * math.pi * turns, r * math.cos(a) * 2 * math.pi * turns, L)).normalized()
        nrm = V((math.cos(a), math.sin(a), 0)); bin_ = tang.cross(nrm)
        rings.append([bm.verts.new(c + nrm * p.x + bin_ * p.z) for p in prof])
    for i in range(n):
        for j in range(8):
            bm.faces.new((rings[i][j], rings[i][(j + 1) % 8], rings[i + 1][(j + 1) % 8], rings[i + 1][j]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    bmesh.ops.transform(bm, matrix=frame_m(p0, d), verts=bm.verts)
    return finish(name, bm, 'accent', bone, 0.0, smooth=60)
for S, s, k, lo, hi in STRUTS:
    h, y, x, z, L = frame(f'strut_coil.{S}{k}')
    coil(f'strut_spring.{S}{k}', h, h + y * L, 0.0165, 0.0028, 5.5, f'strut_coil.{S}{k}')
    # lower spring seat on the housing, upper seat on the rod
    lathe(f'strut_seat_lo.{S}{k}', ring_prof(0.0095, 0.021, -0.006, -0.001), frame_m(h, y), 'frame', f'strut_low.{S}{k}', segs=20)
    cyl(f'strut_seat_hi.{S}{k}', h + y * (L + 0.001), h + y * (L + 0.006), 0.021, 'frame', f'strut_rod.{S}{k}', segs=20)
    # mounts: eye on the track plate, eye on the chassis side
    cyl(f'strut_mount_lo.{S}{k}', lo + V((-0.012, 0, 0)), lo + V((0.012, 0, 0)), 0.0085, 'frame', f'track_frame.{S}', segs=14)
    cyl(f'strut_mount_hi.{S}{k}', hi + V((-0.012, 0, 0)), hi + V((0.012, 0, 0)), 0.0085, 'frame', 'chassis', segs=14)

# ================================================================ SCOOP (lift arms + bucket + ram)
for S, s in SIDES:
    x = s * 0.158
    pa, pb = PIV + V((x, 0, 0)), TIP + V((x, 0, 0))
    d = (pb - pa).normalized()
    # flat lift arm with a bend: drawn as two boxes along the arm line
    L = (pb - pa).length
    yb = d; zb = XA.cross(yb).normalized() * -1
    box(f'lift_arm.{S}', axes_m(pa + d * (L / 2), (1, 0, 0), yb, zb if zb.z > 0 else -zb), (0.014, L + 0.020, 0.030), 'grey', 'scoop_lift', 0.003)
    cyl(f'lift_pivot_boss.{S}', pa + V((-0.010, 0, 0)), pa + V((0.010, 0, 0)), 0.020, 'grey', 'scoop_lift', segs=20)
    cyl(f'lift_tip_boss.{S}', pb + V((-0.010, 0, 0)), pb + V((0.010, 0, 0)), 0.017, 'grey', 'scoop_lift', segs=20)
    # chassis brackets either side of the arm root
    for e in (-1, 1):
        bbox(f'lift_bracket{e:+d}.{S}', (x + e * 0.0125 - 0.0035, ch['y0'] - 0.028, PIV.z - 0.025), (x + e * 0.0125 + 0.0035, ch['y0'] + 0.002, PIV.z + 0.022), 'frame', 'chassis', 0.0015)
    cyl(f'lift_pin.{S}', pa + V((-0.018, 0, 0)), pa + V((0.018, 0, 0)), 0.006, 'steel', 'chassis', segs=12, bevel=0)
    cyl(f'tilt_pin.{S}', pb + V((-0.017 * s, 0, 0)), pb + V((0.012 * s, 0, 0)), 0.0055, 'steel', 'scoop_tilt', segs=12, bevel=0)
# cross tube joining the arms (the ram pushes on it)
cyl('lift_crosstube', RAM_B + V((-0.150, 0, 0.024)), RAM_B + V((0.150, 0, 0.024)), 0.010, 'grey', 'scoop_lift', segs=18)
lathe('ram_eye_rod', ring_prof(0.0, 0.010, -0.010, 0.010), axes_m(RAM_B, (0, 1, 0), (0, 0, 1), (1, 0, 0)), 'frame', 'scoop_lift', segs=16)
cyl('ram_rod_bar', RAM_B + V((0, 0, 0.0)), RAM_B + V((0, 0, 0.020)), 0.005, 'frame', 'scoop_lift', segs=10, bevel=0)
cyl('ram_eye_base', RAM_A + V((-0.012, 0, 0)), RAM_A + V((0.012, 0, 0)), 0.010, 'frame', 'chassis', segs=16)
RAM_D0 = (RAM_B - RAM_A).length
RAM_CYL = 0.012 + 0.58 * RAM_D0          # cylinder end, measured from A
RAM_ROD = RAM_D0 - 0.034                 # rod length from B: its end sits 34 mm from A at rest
h, y, x_, z, L = frame('ram_house')
cyl('ram_cylinder', h + y * 0.012, h + y * RAM_CYL, 0.0135, 'accent', 'ram_house', segs=20)
h, y, x_, z, L = frame('ram_rod')
cyl('ram_piston_rod', h + y * 0.012, h + y * RAM_ROD, 0.0065, 'steel', 'ram_rod', segs=14, bevel=0)
arm['ram_stroke'] = [RAM_ROD + 0.016, RAM_ROD + RAM_CYL - 0.010]    # allowed A-B distance
# bucket on the tilt bone: floor, back, cheeks, a lip with teeth
T0 = TIP
bw = 0.135
bbox('scoop_floor', (-bw, T0.y - 0.130, T0.z - 0.066), (bw, T0.y + 0.006, T0.z - 0.058), 'grey', 'scoop_tilt', 0.002)
bbox('scoop_back', (-bw, T0.y - 0.004, T0.z - 0.066), (bw, T0.y + 0.006, T0.z + 0.045), 'grey', 'scoop_tilt', 0.002)
for e in (-1, 1):
    prism(f'scoop_cheek{e:+d}', [(T0.y + 0.006, T0.z - 0.066), (T0.y - 0.130, T0.z - 0.066), (T0.y - 0.130, T0.z - 0.050), (T0.y - 0.004, T0.z + 0.045), (T0.y + 0.006, T0.z + 0.045)],
          axes_m((e * (bw + 0.004), 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), 0.008, 'grey', 'scoop_tilt', bevel=0.0015)
    bbox(f'scoop_ear{e:+d}', (e * 0.1435 - 0.003, T0.y - 0.012, T0.z - 0.012), (e * 0.1435 + 0.003, T0.y + 0.012, T0.z + 0.040), 'frame', 'scoop_tilt', 0.0015)
bbox('scoop_lip', (-bw, T0.y - 0.140, T0.z - 0.066), (bw, T0.y - 0.126, T0.z - 0.056), 'accent', 'scoop_tilt', 0.002)
for k in range(7):
    xx = -0.114 + k * 0.038
    box(f'scoop_tooth_{k}', IDM((xx, T0.y - 0.150, T0.z - 0.062)), (0.016, 0.020, 0.007), 'steel', 'scoop_tilt', 0.0015, taper=(0.6, 1.0))

# ================================================================ WAIST TURRET + LEAN YOKE
lathe('turret_ring_base', ring_prof(0.020, 0.150, WAIST_Z - 0.0, WAIST_Z + 0.006), IDM((0, 0, 0)), 'frame', 'chassis', segs=72)
lathe('turret', [(0.020, WAIST_Z + 0.007), (0.140, WAIST_Z + 0.007), (0.146, WAIST_Z + 0.012), (0.146, WAIST_Z + 0.026), (0.128, WAIST_Z + 0.034), (0.020, WAIST_Z + 0.034)],
      IDM((0, 0, 0)), 'grey', 'waist', segs=72)
for k in range(12):
    a = 2 * math.pi * k / 12
    p = V((0.133 * math.cos(a), 0.133 * math.sin(a), WAIST_Z + 0.031)); hexbolt(f'turret_bolt_{k}', p, (0, 0, 1), 0.004, bone='waist', h=0.003)
for e in (-1, 1):
    bbox(f'yoke_cheek{e:+d}', (e * 0.105 - 0.008, -0.030, WAIST_Z + 0.034), (e * 0.105 + 0.008, 0.030, LEAN_Z + 0.010), 'frame', 'waist', 0.003)
    cyl(f'lean_pin{e:+d}', (e * 0.090, 0, LEAN_Z), (e * 0.118, 0, LEAN_Z), 0.007, 'steel', 'waist', segs=12, bevel=0)
    cyl(f'lean_trunnion{e:+d}', (e * 0.080, 0, LEAN_Z), (e * 0.096, 0, LEAN_Z), 0.016, 'frame', 'lean', segs=20)
bbox('lean_saddle', (-0.080, -0.040, LEAN_Z - 0.010), (0.080, 0.040, LEAN_Z + 0.010), 'frame', 'lean', 0.003)
cyl('sway_bearing', (0, 0, LEAN_Z + 0.009), (0, 0, BODY['z0'] - 0.0), 0.040, 'steel', 'lean', segs=24, bevel=0.0)

# ================================================================ BODY
bz0 = BODY['z0']; bw2 = BODY['w'] / 2; bd2 = BODY['d'] / 2
rbox('body_shell', (0, 0, bz0 + BODY['h'] / 2), (BODY['w'], BODY['d'], BODY['h']), BODY['r'], 'paint', 'body', segs=8)
# seam band round the waist of the body
lathe('body_band_dummy', [(0, 0), (0, 0), (0, 0)], IDM((0, 0, 0)), 'grey', 'body') if False else None
band_z = bz0 + 0.150
prism('body_band', rrect(BODY['w'] + 0.008, BODY['d'] + 0.008, BODY['r'] + 0.004, 10), IDM((0, 0, band_z)), 0.014, 'grey', 'body', bevel=0.002)
# screen: bezel ring proud of the front face, dark screen behind thin glass
bez_o = rrect(SCR_W + 0.030, SCR_H + 0.030, 0.034, 8); bez_i = rrect(SCR_W, SCR_H, 0.022, 8)
def ring2d(name, outer, inner, M, depth, mat, bone, z0):
    bm = bmesh.new()
    vo = [bm.verts.new((x, y, z0)) for x, y in outer]; vi = [bm.verts.new((x, y, z0)) for x, y in inner]
    n = len(outer)
    for i in range(n):
        bm.faces.new((vo[i], vo[(i + 1) % n], vi[(i + 1) % n], vi[i]))
    ext = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    for v in ext['geom']:
        if isinstance(v, bmesh.types.BMVert): v.co.z += depth
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return finish(name, bm, mat, bone, 0.0015)
FM = axes_m((0, FRONT_Y, SCREEN_Z), (-1, 0, 0), (0, 0, 1), (0, -1, 0))     # face frame: local Z out of the screen (-Y)
ring2d('screen_bezel', bez_o, bez_i, FM, 0.013, 'grey', 'body', -0.001)
prism('screen_panel', rrect(SCR_W + 0.002, SCR_H + 0.002, 0.023, 8), FM, 0.004, 'screen', 'body', bevel=0.0, z0=0.0005)
prism('screen_glass', rrect(SCR_W + 0.002, SCR_H + 0.002, 0.023, 8), FM, 0.0015, 'glass', 'body', bevel=0.0, z0=0.0105)
for k, (xx, zz) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
    p = V((xx * (SCR_W / 2 + 0.008), FRONT_Y - 0.0125, SCREEN_Z + zz * (SCR_H / 2 + 0.008)))
    hexbolt(f'bezel_screw_{k}', p, (0, -1, 0), 0.0035, bone='body', h=0.002)

# face shapes (emissive, between the screen and the glass); shape keys give the expressions
def face_shape(name, bone, outline_fn, keys, mat='face'):
    n = 48
    h, y, x, z, L = frame(bone)
    bm = bmesh.new()
    base = [outline_fn(2 * math.pi * i / n, None) for i in range(n)]
    top = [bm.verts.new((u, v, 0.0006)) for u, v in base]; bot = [bm.verts.new((u, v, -0.0006)) for u, v in base]
    bm.faces.new(top); bm.faces.new(bot[::-1])
    for i in range(n):
        j = (i + 1) % n; bm.faces.new((bot[i], bot[j], top[j], top[i]))
    # face plane: u = screen right (-X), v = up, w = out of the screen (-Y)
    M = axes_m(h, (-1, 0, 0), (0, 0, 1), (0, -1, 0))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    ob = finish(name, bm, mat, bone, 0.0, smooth=10, led='face')
    ob.shape_key_add(name='Basis')
    Minv = M.inverted()
    for kname in keys:
        sk = ob.shape_key_add(name=kname, from_mix=False)
        for i in range(n):
            u, v = outline_fn(2 * math.pi * i / n, kname)
            for idx, w in ((i, 0.0006), (n + i, -0.0006)):
                sk.data[idx].co = M @ V((u, v, w))
    return ob

ER = 0.030
def eye_fn(side):
    s = 1 if side == 'L' else -1      # +u is screen right = droid's left... u = -X, so droid L eye sits at negative u
    def f(a, key):
        cu, sv = math.cos(a), math.sin(a)
        r = ER
        u, v = r * cu, r * 1.12 * sv
        if key == 'blink':
            v = r * 0.10 * sv
        elif key == 'happy':     # upward crescent
            if sv >= 0: u, v = r * cu, r * 0.75 * sv
            else: u, v = r * 0.72 * cu, r * 0.75 * 0.45 * (-sv)
            v -= r * 0.15
        elif key == 'sad':       # top edge falls toward the outside
            if sv > 0: v = r * 1.12 * sv * 0.75 - (u * -s) * 0.45
        elif key == 'angry':     # top edge falls toward the inside
            if sv > 0: v = r * 1.12 * sv * 0.75 + (u * -s) * 0.45
        elif key == 'wide':
            u, v = r * 1.18 * cu, r * 1.30 * sv
        elif key == 'heart':
            t = a + math.pi / 2
            hx = 16 * math.sin(t) ** 3; hy = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            u, v = hx * r / 15.0, hy * r / 15.0 + r * 0.1
        elif key == 'x':          # dizzy/broken: a squashed diamond
            u, v = r * 0.9 * (abs(cu) ** 2.2) * (1 if cu >= 0 else -1), r * 0.9 * (abs(sv) ** 2.2) * (1 if sv >= 0 else -1)
        return u, v
    return f

def mouth_fn(a, key):
    cu, sv = math.cos(a), math.sin(a)
    w, h = 0.040, 0.0055
    u, v = w * cu, h * sv
    if key == 'smile':
        v = h * sv + 0.016 * (cu ** 2) - 0.008
        if sv < 0: v -= 0.004 * (1 - cu ** 2)
    elif key == 'frown':
        v = h * sv - 0.016 * (cu ** 2) + 0.008
    elif key == 'open':          # talking: a D shape opening downward
        u = w * 0.78 * cu
        v = h * sv if sv > 0 else h * sv + 0.026 * sv
    elif key == 'oh':
        u, v = 0.016 * cu, 0.019 * sv
    elif key == 'wavy':
        v = h * sv * 0.8 + 0.0055 * math.sin(cu * 3 * math.pi)
    return u, v

EYE_KEYS = ['blink', 'happy', 'sad', 'angry', 'wide', 'heart', 'x']
MOUTH_KEYS = ['smile', 'frown', 'open', 'oh', 'wavy']
for S, s in SIDES:
    face_shape(f'face_eye.{S}', f'eye.{S}', eye_fn(S), EYE_KEYS)
face_shape('face_mouth', 'mouth', mouth_fn, MOUTH_KEYS)

# body details: speaker grille (left side), status LEDs + hatch (right side), lifting eye, front lamp strip
for k in range(6):
    zz = bz0 + 0.240 + k * 0.016
    bbox(f'speaker_slot_{k}', (bw2 - 0.0005, -0.060, zz), (bw2 + 0.0035, 0.060, zz + 0.007), 'frame', 'body', 0.0012)
bbox('speaker_frame', (bw2 - 0.001, -0.072, bz0 + 0.228), (bw2 + 0.002, 0.072, bz0 + 0.338), 'grey', 'body', 0.002)
for i, col in enumerate(('green', 'amber', 'red')):
    c = V((-bw2, -0.050 + i * 0.030, bz0 + 0.330))
    cyl(f'status_bezel_{i + 1}', c + V((0.002, 0, 0)), c + V((-0.005, 0, 0)), 0.0085, 'frame', 'body', segs=18)
    cyl(f'RB_LED_{col}', c + V((-0.005, 0, 0)), c + V((-0.0075, 0, 0)), 0.0062, 'RB_LED_' + col, 'body', segs=18, led='status')
# side access panel on the right (screwed)
bbox('access_panel.R', (-bw2 - 0.004, -0.090, bz0 + 0.190), (-bw2 + 0.001, 0.090, bz0 + 0.300), 'grey', 'body', 0.002)
for k, (yy, zz) in enumerate(((-0.08, 0.20), (0.08, 0.20), (-0.08, 0.29), (0.08, 0.29))):
    hexbolt(f'access_screw_{k}', (-bw2 - 0.004, yy, bz0 + zz), (-1, 0, 0), 0.003, bone='body', h=0.002)
# lifting eye on top-centre, chin lamp under the screen
lathe('lift_eye', ring_prof(0.010, 0.017, -0.004, 0.004), axes_m((0, -0.06, BZ1 + 0.021), (0, 1, 0), (0, 0, 1), (1, 0, 0)), 'steel', 'body', segs=28)
bbox('lift_eye_base', (-0.014, -0.074, BZ1 - 0.003), (0.014, -0.046, BZ1 + 0.006), 'frame', 'body', 0.002)
bbox('chin_lamp_frame', (-0.075, FRONT_Y - 0.006, bz0 + 0.070), (0.075, FRONT_Y + 0.002, bz0 + 0.098), 'grey', 'body', 0.003)
bbox('chin_lamp', (-0.066, FRONT_Y - 0.0075, bz0 + 0.076), (0.066, FRONT_Y - 0.005, bz0 + 0.092), 'lamp', 'body', 0.001).__setitem__('rb_led', 'lamp')
# corner rivets on the front face
for k, (xx, zz) in enumerate(((1, 0.04), (-1, 0.04))):
    hexbolt(f'front_rivet_{k}', (xx * 0.165, FRONT_Y + 0.0005, bz0 + zz), (0, -1, 0), 0.004, bone='body', h=0.0025)

# ================================================================ STALKS
for S, s in SIDES:
    b0 = STK[S]
    # socket on the body top: collar + roll knuckle (roll axis = forward)
    cyl(f'stalk_socket.{S}', b0 + V((0, 0, -0.004)), b0 + V((0, 0, 0.010)), 0.030, 'grey', 'body', segs=28)
    h, y, x, z, L = frame(f'stalk_roll.{S}')
    cyl(f'stalk_roll_knuckle.{S}', h + V((0, -0.0145, 0)), h + V((0, 0.0145, 0)), 0.0125, 'frame', f'stalk_roll.{S}', segs=18)
    cyl(f'stalk_roll_pin.{S}', h + V((0, -0.022, 0)), h + V((0, 0.022, 0)), 0.0045, 'steel', 'body', segs=10, bevel=0)
    for e in (-1, 1):
        bbox(f'stalk_roll_cheek{e:+d}.{S}', (b0.x - 0.010, b0.y + e * 0.019 - 0.003, b0.z + 0.008), (b0.x + 0.010, b0.y + e * 0.019 + 0.003, b0.z + 0.030), 'frame', 'body', 0.0015)
    # pitch stage: yoke on the roll knuckle, pin across X
    pp = frame(f'stalk_pitch.{S}')[0]
    for e in (-1, 1):
        bbox(f'stalk_yoke{e:+d}.{S}', (pp.x + e * 0.0145 - 0.0028, pp.y - 0.011, pp.z - 0.011), (pp.x + e * 0.0145 + 0.0028, pp.y + 0.011, pp.z + 0.007), 'frame', f'stalk_roll.{S}', 0.001)
    cyl(f'stalk_pitch_pin.{S}', pp + V((-0.0185, 0, 0)), pp + V((0.0185, 0, 0)), 0.0042, 'steel', f'stalk_roll.{S}', segs=10, bevel=0)
    cyl(f'stalk_pitch_knuckle.{S}', pp + V((-0.0110, 0, 0)), pp + V((0.0110, 0, 0)), 0.0110, 'frame', f'stalk_pitch.{S}', segs=18)
    # outer tube (pitch stage) and inner tube (telescope)
    cyl(f'stalk_neck_lo.{S}', pp + V((0, 0, 0.0115)), pp + V((0, 0, 0.024)), 0.0090, 'frame', f'stalk_pitch.{S}', segs=16)
    lathe(f'stalk_tube.{S}', [(0.0125, 0.022), (0.0170, 0.022), (0.0170, 0.122), (0.0125, 0.122)], IDM(pp), 'paint', f'stalk_pitch.{S}', segs=24)
    lathe(f'stalk_collar.{S}', ring_prof(0.0122, 0.0200, 0.112, 0.126), IDM(pp), 'accent', f'stalk_pitch.{S}', segs=24)
    eh = frame(f'stalk_ext.{S}')[0]
    cyl(f'stalk_inner.{S}', eh + V((0, 0, -0.012)), eh + V((0, 0, 0.110)), 0.0115, 'steel', f'stalk_ext.{S}', segs=20, bevel=0)
    # sprung cap on the tip: dark housing with a glowing ring band, small lens on the front
    th = frame(f'stalk_tip.{S}')[0]
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=0.0108); bmesh.ops.translate(bm, vec=th, verts=bm.verts)
    finish(f'stalk_ball.{S}', bm, 'frame', f'stalk_tip.{S}')
    lathe(f'stalk_cup.{S}', ring_prof(0.0085, 0.0128, -0.008, -0.002), IDM(eh + V((0, 0, 0.110))), 'frame', f'stalk_ext.{S}', segs=24)
    cyl(f'stalk_neck.{S}', th + V((0, 0, 0.006)), th + V((0, 0, 0.013)), 0.0080, 'frame', f'stalk_tip.{S}', segs=16)
    cyl(f'stalk_cap.{S}', th + V((0, 0, 0.012)), th + V((0, 0, 0.064)), 0.031, 'grey', f'stalk_tip.{S}', segs=28, bevel=0.003)
    cyl(f'stalk_ring.{S}', th + V((0, 0, 0.044)), th + V((0, 0, 0.053)), 0.0315, 'stalk', f'stalk_tip.{S}', segs=28, bevel=0.0, led='antenna')
    cyl(f'stalk_lens.{S}', th + V((0, -0.030, 0.030)), th + V((0, -0.035, 0.030)), 0.009, 'screen', f'stalk_tip.{S}', segs=16, bevel=0.0)

# ================================================================ SCRAP BIN on the back
bi = BIN
rbox('bin_body', (0, (bi['y0'] + bi['y1']) / 2, (bi['z0'] + bi['z1']) / 2), (2 * bi['x'], bi['y1'] - bi['y0'], bi['z1'] - bi['z0']), 0.018, 'grey', 'body', segs=4)
for e in (-1, 1):
    bbox(f'bin_strap{e:+d}', (e * 0.100 - 0.010, bi['y0'] - 0.004, bi['z0'] + 0.010), (e * 0.100 + 0.010, bi['y1'] + 0.003, bi['z0'] + 0.020), 'frame', 'body', 0.002)
# lid: a slightly domed plate hinged at the back edge, knuckles + pin
lid = rrect(2 * bi['x'] + 0.010, (bi['y1'] - bi['y0']) + 0.002, 0.020, 6)
prism('bin_lid_plate', [(x_, y_) for x_, y_ in lid], IDM((0, (bi['y0'] + bi['y1']) / 2 + 0.003, bi['z1'] + 0.003)), 0.012, 'paint', 'bin_lid', bevel=0.003, z0=0.0)
bbox('bin_lid_stripe', (-0.12, bi['y0'] + 0.010, bi['z1'] + 0.0145), (0.12, bi['y0'] + 0.030, bi['z1'] + 0.0160), 'accent', 'bin_lid', 0.0005)
bbox('bin_lid_handle', (-0.040, bi['y0'] + 0.008, bi['z1'] + 0.015), (0.040, bi['y0'] + 0.018, bi['z1'] + 0.024), 'frame', 'bin_lid', 0.002)
for e in (-1, 1):
    cyl(f'bin_lid_knuckle{e:+d}', LH + V((e * 0.040, 0, 0)), LH + V((e * 0.110, 0, 0)), 0.0065, 'paint', 'bin_lid', segs=16)
cyl('bin_hinge_knuckle', LH + V((-0.038, 0, 0)), LH + V((0.038, 0, 0)), 0.0065, 'grey', 'body', segs=16)
cyl('bin_hinge_pin', LH + V((-0.114, 0, 0)), LH + V((0.114, 0, 0)), 0.0028, 'steel', 'body', segs=10, bevel=0)
# scrap inside the bin (seen when the lid opens): a pipe, a gear and a bent plate
cyl('scrap_pipe', (-0.08, bi['y0'] + 0.04, bi['z1'] - 0.040), (0.03, bi['y0'] + 0.07, bi['z1'] - 0.014), 0.010, 'steel', 'body', segs=14)
lathe('scrap_gear', ring_prof(0.008, 0.026, -0.005, 0.005), axes_m((0.07, bi['y0'] + 0.06, bi['z1'] - 0.030), (1, 0, 0), (0, 0.6, 0.8), (0, -0.8, 0.6)), 'accent', 'body', segs=24)

# ================================================================ parent parts to bones
for ob, bn in PARTS:
    b = arm_data.bones[bn]
    mw = ob.matrix_world.copy()
    ob.parent = arm; ob.parent_type = 'BONE'; ob.parent_bone = bn
    ob.matrix_parent_inverse = (arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()
for S in ('L', 'R'):
    pth = TRACK[S]['path']; fb = arm_data.bones[f'track_frame.{S}']
    pth.matrix_parent_inverse = (arm.matrix_world @ fb.matrix_local @ Matrix.Translation((0, fb.length, 0))).inverted()
    pth.matrix_basis = axes_m((TX * (1 if S == 'L' else -1), 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))

# ================================================================ constraints + locks
pbs = arm.pose.bones
for pb in pbs: pb.rotation_mode = 'XYZ'
def lock(bn, rot='', loc='', scl=''):
    pb = pbs[bn]
    pb.lock_rotation = tuple(a not in rot for a in 'xyz'); pb.lock_location = tuple(a not in loc for a in 'xyz')
    pb.lock_scale = tuple(a not in scl for a in 'xyz')
def limit(bn, **kw):
    c = pbs[bn].constraints.new('LIMIT_ROTATION'); c.name = 'joint limits'; c.owner_space = 'LOCAL'; c.use_transform_limit = True
    c.use_limit_x = c.use_limit_y = c.use_limit_z = True
    for a in 'xyz':
        lo, hi = kw.get(a, (0, 0)); setattr(c, f'min_{a}', rad(lo)); setattr(c, f'max_{a}', rad(hi))
def limit_loc(bn, **kw):
    c = pbs[bn].constraints.new('LIMIT_LOCATION'); c.name = 'travel'; c.owner_space = 'LOCAL'; c.use_transform_limit = True
    for a in 'xyz':
        if a in kw:
            lo, hi = kw[a]; setattr(c, f'use_min_{a}', True); setattr(c, f'use_max_{a}', True)
            setattr(c, f'min_{a}', lo); setattr(c, f'max_{a}', hi)
def limit_scale(bn, **kw):
    c = pbs[bn].constraints.new('LIMIT_SCALE'); c.name = 'scale range'; c.owner_space = 'LOCAL'; c.use_transform_limit = True
    for a in 'xyz':
        if a in kw:
            lo, hi = kw[a]; setattr(c, f'use_min_{a}', True); setattr(c, f'use_max_{a}', True)
            setattr(c, f'min_{a}', lo); setattr(c, f'max_{a}', hi)
def copy_rot(owner, target, axes, infl, mix='ADD', inv=False):
    c = pbs[owner].constraints.new('COPY_ROTATION'); c.name = f'follow {target}'
    c.target = arm; c.subtarget = target; c.mix_mode = mix
    c.use_x, c.use_y, c.use_z = ('x' in axes), ('y' in axes), ('z' in axes)
    if inv: c.invert_x = c.invert_y = c.invert_z = True
    c.owner_space = c.target_space = 'LOCAL'; c.influence = infl
    return c

lock('root', 'z', 'xy')
lock('suspension', 'xz', 'y'); limit('suspension', x=(-5, 4), z=(-4, 4)); limit_loc('suspension', y=(-0.017, 0.012))
lock('chassis')
for S, s in SIDES:
    lock(f'track_frame.{S}', 'y'); limit(f'track_frame.{S}', y=(-10, 10))
    for wn, _ in WHEELS: lock(f'{wn}.{S}', 'y')
for S, s, k, lo, hi in STRUTS:
    for bn in (f'strut_low.{S}{k}', f'strut_rod.{S}{k}', f'strut_coil.{S}{k}'): lock(bn)
    c = pbs[f'strut_low.{S}{k}'].constraints.new('DAMPED_TRACK'); c.target = arm; c.subtarget = f'MCH-strut_hi.{S}{k}'
    c = pbs[f'strut_rod.{S}{k}'].constraints.new('DAMPED_TRACK'); c.target = arm; c.subtarget = f'MCH-strut_lo.{S}{k}'
    c = pbs[f'strut_coil.{S}{k}'].constraints.new('STRETCH_TO'); c.target = arm; c.subtarget = f'strut_rod.{S}{k}'
    c.head_tail = 0.0; c.volume = 'NO_VOLUME'; c.keep_axis = 'PLANE_X'
    # the coil ends 22 mm short of each eye; stretch to the rod's seat point instead of its head
    c.subtarget = f'MCH-strut_hi.{S}{k}'
lock('scoop_lift', 'x'); limit('scoop_lift', x=(-41, 8))
lock('scoop_tilt', 'x'); limit('scoop_tilt', x=(-75, 20))
for bn, tg in (('ram_house', 'MCH-ramB'), ('ram_rod', 'MCH-ramA')):
    lock(bn); c = pbs[bn].constraints.new('DAMPED_TRACK'); c.target = arm; c.subtarget = tg
lock('tow_hook', 'x'); limit('tow_hook', x=(-26, 60))
lock('waist', 'y'); limit('waist', y=(-150, 150))
lock('lean', 'x'); limit('lean', x=(-16, 16))
lock('body', 'y'); limit('body', y=(-8, 8))     # sway (roll about the forward axis = the body bone's own axis)
for S, s in SIDES:
    lock(f'eye.{S}', loc='xz', scl='xz'); limit_loc(f'eye.{S}', x=(-0.030, 0.030), z=(-0.030, 0.030))
    limit_scale(f'eye.{S}', x=(0.5, 1.5), z=(0.05, 1.6))
    lock(f'stalk_roll.{S}', 'z'); limit(f'stalk_roll.{S}', z=(-40, 8) if s > 0 else (-8, 40))   # + = inward for L, outward for R
    lock(f'stalk_pitch.{S}', 'x'); limit(f'stalk_pitch.{S}', x=(-33, 33))
    lock(f'stalk_ext.{S}', loc='y'); limit_loc(f'stalk_ext.{S}', y=(0.0, 0.085))
    lock(f'stalk_tip.{S}', 'xz'); limit(f'stalk_tip.{S}', x=(-15, 15), z=(-15, 15))
lock('mouth', loc='xz', scl='xz'); limit_loc('mouth', x=(-0.03, 0.03), z=(-0.02, 0.02)); limit_scale('mouth', x=(0.4, 1.6), z=(0.4, 1.8))
lock('bin_lid', 'x'); limit('bin_lid', x=(0, 115))
for sp in SPRINGS:
    for bn, tn in zip(sp['bones'], sp['targets']):
        c = pbs[bn].constraints.new('DAMPED_TRACK'); c.name = 'spring'; c.target = arm; c.subtarget = tn
FOLEY = {'root': 'none', 'chassis': 'none', 'suspension': 'piston', 'scoop_lift': 'motor', 'scoop_tilt': 'motor', 'ram_house': 'piston',
         'ram_rod': 'piston', 'tow_hook': 'hinge', 'waist': 'motor', 'lean': 'motor', 'body': 'hinge', 'mouth': 'none', 'bin_lid': 'motor'}
for S in 'LR':
    FOLEY.update({f'track_frame.{S}': 'hinge', f'eye.{S}': 'none', f'stalk_roll.{S}': 'motor', f'stalk_pitch.{S}': 'motor',
                  f'stalk_ext.{S}': 'piston', f'stalk_tip.{S}': 'hinge'})
    for wn, _ in WHEELS: FOLEY[f'{wn}.{S}'] = 'spinner'
for pb in pbs:
    if pb.name.startswith(('strut_low', 'strut_rod', 'strut_coil')): pb['foley_mech'] = 'piston'
    elif pb.name.startswith(('MCH-', 'SPR-')): pb['foley_mech'] = 'none'
    elif pb.name in FOLEY: pb['foley_mech'] = FOLEY[pb.name]
for o in bpy.data.objects:
    if o.name.startswith(('track_link_', 'track_path', 'track_pin_')): o['foley_mech'] = 'none'   # the sprocket spinner carries the tread clatter; 68 links would each get a strip
    elif o.name.startswith('face_'): o['foley_mech'] = 'none'
arm['springs'] = json.dumps(SPRINGS); arm['springs_on'] = 1
arm.id_properties_ui('springs_on').update(min=0, max=1, description='Live spring motion on the stalk caps and the tow hook')

# ---------------------------------------------------------------- rig properties + drivers
def sprop(name, val, lo, hi, desc):
    arm[name] = val; arm.id_properties_ui(name).update(min=lo, max=hi, soft_min=lo, soft_max=hi, description=desc)
sprop('track_L', 0.0, -1000.0, 1000.0, 'Left track travel in metres (key it, or let Drive mode write it)')
sprop('track_R', 0.0, -1000.0, 1000.0, 'Right track travel in metres')
sprop('face_glow', 1.0, 0.0, 3.0, 'Screen face brightness')
sprop('stalk_glow', 1.0, 0.0, 3.0, 'Stalk ring glow')
sprop('lamps', 0.0, 0.0, 2.0, 'Headlamps and chin lamp')
sprop('led_glow', 1.0, 0.0, 3.0, 'Status LEDs')
sprop('power', 1.0, 0.0, 1.0, 'Power: 0 switches every light off')
sprop('talk', 0.0, 0.0, 1.0, 'Mouth open (the voice slot keys this)')
for k in EYE_KEYS: sprop('eyes_' + k, 0.0, 0.0, 1.0, f'Eyes: {k}')
for k in MOUTH_KEYS:
    if k != 'open': sprop('mouth_' + k, 0.0, 0.0, 1.0, f'Mouth: {k}')

def var(d, nm, path, idt='OBJECT', ido=None):
    v = d.variables.new(); v.name = nm; v.type = 'SINGLE_PROP'; v.targets[0].id_type = idt; v.targets[0].id = ido or arm
    v.targets[0].data_path = path
def drive_emit(mat, expr, props):
    b = mat.node_tree.nodes.get('Principled BSDF'); s = b.inputs['Emission Strength']
    base = s.default_value
    d = s.driver_add('default_value').driver; d.type = 'SCRIPTED'
    for p in props: var(d, p, f'["{p}"]')
    d.expression = expr.format(base=base)
drive_emit(MATS['face'], '{base} * face_glow * power', ['face_glow', 'power'])
drive_emit(MATS['stalk'], '{base} * stalk_glow * power', ['stalk_glow', 'power'])
drive_emit(MATS['lamp'], '{base} * lamps * power', ['lamps', 'power'])
for c in LEDCOL: drive_emit(MATS['RB_LED_' + c], '{base} * led_glow * power', ['led_glow', 'power'])

# tread links ride the path: offset = fract(i/N + travel/L); wheels spin = travel / radius
for S in ('L', 'R'):
    T = TRACK[S]
    for i, (ob, c, pin, pc) in enumerate(T['links']):
        base = i / T['N']
        for con in (c, pc):
            d = con.driver_add('offset_factor').driver; d.type = 'SCRIPTED'
            var(d, 't', f'["track_{S}"]')
            d.expression = f'({base:.6f} + t / {T["L"]:.6f}) - floor({base:.6f} + t / {T["L"]:.6f})'
    for wn, (y, z, r) in WHEELS:
        fc = pbs[f'{wn}.{S}'].driver_add('rotation_euler', 1); d = fc.driver; d.type = 'SCRIPTED'
        var(d, 't', f'["track_{S}"]'); d.expression = f't / {r:.4f}'
# face shape keys follow the rig props
for ob in [o for o in bpy.data.objects if o.name.startswith('face_')]:
    for kb in ob.data.shape_keys.key_blocks[1:]:
        prop = 'talk' if kb.name == 'open' else (('eyes_' if 'eye' in ob.name else 'mouth_') + kb.name)
        d = kb.driver_add('value').driver; d.type = 'SCRIPTED'; var(d, 'v', f'["{prop}"]'); d.expression = 'v'

# simple-expression check (no auto-run needed)
bad = []
for o in [arm] + list(bpy.data.objects) + list(bpy.data.materials) + [o.data.shape_keys for o in bpy.data.objects if o.type == 'MESH' and o.data.shape_keys]:
    ad = getattr(o, 'animation_data', None)
    if ad:
        for fc in ad.drivers:
            if not fc.driver.is_simple_expression: bad.append((o.name, fc.data_path, fc.driver.expression))
print('NON_SIMPLE_DRIVERS', len(bad), bad[:3])

spec = {n: dict(head=list(b['head']), tail=list(b['tail']), z=list(b['z']), parent=b['parent'], coll=b['coll'], ctrl=b['ctrl'])
        for n, b in BONES.items()}
arm['rig_spec'] = json.dumps(spec)
arm['track_info'] = json.dumps({S: dict(L=TRACK[S]['L'], N=TRACK[S]['N'], pitch=TRACK[S]['pitch']) for S in TRACK})
arm['droid'] = 'tracker'
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT, len(PARTS), 'parts', len(BONES), 'bones', 'links', {S: TRACK[S]['N'] for S in TRACK})
