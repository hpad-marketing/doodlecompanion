"""Realism 1: industrial set. Worn concrete floor (cracks, oil, dust, footprints where the demo steps), scale props,
hard warm key + cool rim + dim world, volumetric haze with floating dust motes.
python3 world.py in.blend out.blend
"""
import bpy, bmesh, sys, math, random
from mathutils import Vector, Matrix
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene; r = math.radians
random.seed(7)
arm = bpy.data.objects['RobotRig']; pbs = arm.pose.bones

def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c] + [1]

old = bpy.data.collections.get('Studio')
for o in list(old.objects) if old else []:
    o.hide_render = True; o.hide_viewport = True
W = bpy.data.collections.get('World_Set') or bpy.data.collections.new('World_Set')
if W.name not in sc.collection.children: sc.collection.children.link(W)
for o in list(W.objects): bpy.data.objects.remove(o)

def link(o): W.objects.link(o); return o

# ---------------------------------------------------------------- footprints from the demo walk
fp = []
demo = bpy.data.actions.get('RM_demo_10s')
ad = arm.animation_data
saved = ad.action
if demo:
    ad.action = demo
    if demo.slots: ad.action_slot = demo.slots[0]
    for f in range(1, 241, 2):
        sc.frame_set(f)
        for S in 'LR':
            m = arm.matrix_world @ pbs[f'IK_foot.{S}'].matrix
            if m.translation.z < 0.003:
                p = m.translation; yaw = m.to_euler().z
                if not any((p - q).length < 0.05 for q, _ in fp): fp.append((p.copy(), yaw))
    ad.action = saved
    if saved and saved.slots: ad.action_slot = saved.slots[0]
SIZE, RES = 6.0, 1024
img = bpy.data.images.get('RB_footprints') or bpy.data.images.new('RB_footprints', RES, RES, float_buffer=False)
px = [0.0] * (RES * RES * 4)
for p, yaw in fp:
    c, s = math.cos(yaw), math.sin(yaw)
    for i in range(-30, 31):
        for j in range(-60, 61):
            lx, ly = i * 0.0045, j * 0.0045        # foot sole ~0.27 x 0.54 m in robot frame (toe at -y)
            if abs(lx) > 0.13 or not (-0.42 < ly < 0.13): continue
            wx = p.x + lx * c - ly * s; wy = p.y + lx * s + ly * c
            u = int((wx / SIZE + 0.5) * RES); v = int((wy / SIZE + 0.5) * RES)
            if 0 <= u < RES and 0 <= v < RES:
                k = (v * RES + u) * 4
                edge = 1.0 - max(abs(lx) / 0.13, (ly + 0.145) / 0.275 if ly > -0.145 else (-0.145 - ly) / 0.275)
                val = 0.85 if edge > 0.08 else 1.0                      # pressed sole, darker rim
                px[k] = px[k + 1] = px[k + 2] = max(px[k], val); px[k + 3] = 1
img.pixels = px; img.pack()

# ---------------------------------------------------------------- concrete floor
me = bpy.data.meshes.new('ground'); bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=15)
bm.to_mesh(me); bm.free()
floor = link(bpy.data.objects.new('Ground_Concrete', me))
me.uv_layers.new(name='UVMap')
m = bpy.data.materials.new('RB_concrete'); nt = m.node_tree; N = nt.nodes; L = nt.links; N.clear()
out_n = N.new('ShaderNodeOutputMaterial'); b = N.new('ShaderNodeBsdfPrincipled'); L.new(b.outputs[0], out_n.inputs[0])
tc = N.new('ShaderNodeTexCoord')
def noise(scale, detail=8, rough=0.6, dist=0.0, vec=None):
    n = N.new('ShaderNodeTexNoise'); n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough; n.inputs['Distortion'].default_value = dist
    L.new(vec or tc.outputs['Object'], n.inputs['Vector']); return n.outputs['Fac']
def mr(x, a, b, c=0.0, d=1.0):
    n = N.new('ShaderNodeMapRange'); n.clamp = True; L.new(x, n.inputs[0])
    n.inputs[1].default_value, n.inputs[2].default_value, n.inputs[3].default_value, n.inputs[4].default_value = a, b, c, d
    return n.outputs[0]
def mix(f, a, bb, t='MIX'):
    n = N.new('ShaderNodeMix'); n.data_type = 'RGBA'; n.blend_type = t; n.clamp_result = True
    for i, x in ((0, f), (6, a), (7, bb)):
        if isinstance(x, (tuple, list)) or isinstance(x, float): n.inputs[i].default_value = x
        else: L.new(x, n.inputs[i])
    return n.outputs[2]
def mth(op, a, bb):
    n = N.new('ShaderNodeMath'); n.operation = op
    for i, x in enumerate((a, bb)):
        if isinstance(x, float): n.inputs[i].default_value = x
        else: L.new(x, n.inputs[i])
    return n.outputs[0]
base = mix(noise(0.6, 6), (0.30, 0.29, 0.27, 1), (0.42, 0.41, 0.38, 1))
base = mix(mr(noise(14, 10, 0.7), 0.45, 0.7, 0.0, 0.25), base, (0.2, 0.19, 0.18, 1))
vor = N.new('ShaderNodeTexVoronoi'); vor.feature = 'DISTANCE_TO_EDGE'; vor.inputs['Scale'].default_value = 0.45
wob = N.new('ShaderNodeVectorMath'); wob.operation = 'ADD'; L.new(tc.outputs['Object'], wob.inputs[0])
nv = N.new('ShaderNodeTexNoise'); nv.inputs['Scale'].default_value = 3; L.new(tc.outputs['Object'], nv.inputs['Vector'])
sc_v = N.new('ShaderNodeVectorMath'); sc_v.operation = 'SCALE'; sc_v.inputs['Scale'].default_value = 0.25
L.new(nv.outputs['Color'], sc_v.inputs[0]); L.new(sc_v.outputs[0], wob.inputs[1]); L.new(wob.outputs[0], vor.inputs['Vector'])
crack = mr(vor.outputs['Distance'], 0.005, 0.0)                     # thin dark cracks
joints = N.new('ShaderNodeTexBrick'); joints.inputs['Scale'].default_value = 0.25; joints.inputs['Mortar Size'].default_value = 0.006
joints.inputs['Color1'].default_value = joints.inputs['Color2'].default_value = (1, 1, 1, 1); joints.inputs['Mortar'].default_value = (0, 0, 0, 1)
joints.offset = 0.0; L.new(tc.outputs['Object'], joints.inputs['Vector'])
saw = joints.outputs['Fac']                                         # saw-cut slab joints (Fac = 1 in the joint)
gap = mth('MAXIMUM', crack, saw)
oil = mr(noise(0.9, 4, 0.5, 1.5), 0.62, 0.7)
dust = mr(noise(1.4, 5), 0.3, 0.7, 0.3, 0.85)
fpi = N.new('ShaderNodeTexImage'); fpi.image = img; fpi.extension = 'CLIP'
mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (1 / SIZE, 1 / SIZE, 1); mp.inputs['Location'].default_value = (0.5, 0.5, 0)
L.new(tc.outputs['Object'], mp.inputs[0]); L.new(mp.outputs[0], fpi.inputs['Vector'])
foot = fpi.outputs['Color']
dust = mth('MULTIPLY', dust, mth('SUBTRACT', 1.0, mth('MULTIPLY', foot, 0.9)))   # feet pressed the dust away
col = mix(oil, base, (0.05, 0.045, 0.04, 1))
col = mix(dust, col, (0.58, 0.54, 0.47, 1))
col = mix(mth('MULTIPLY', gap, 0.85), col, (0.03, 0.03, 0.03, 1))
L.new(col, b.inputs['Base Color'])
rough = mr(noise(2.0, 4), 0.3, 0.7, 0.62, 0.88)
rough = mth('SUBTRACT', rough, mth('MULTIPLY', oil, 0.45))
rough = mth('ADD', rough, mth('MULTIPLY', dust, 0.1)); L.new(rough, b.inputs['Roughness'])
bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.3; bump.inputs['Distance'].default_value = 0.004
h = mth('ADD', mth('MULTIPLY', noise(30, 8, 0.75), 0.3), mth('MULTIPLY', gap, -1.0))
h = mth('ADD', h, mth('MULTIPLY', foot, -0.15)); L.new(h, bump.inputs['Height']); L.new(bump.outputs[0], b.inputs['Normal'])
me.materials.append(m)

# ---------------------------------------------------------------- props (true scale), reusing the robot's weathered metal
MG = bpy.data.node_groups['RB Weathered Metal']
def metal(name, hexcol, paint=1.0):
    mm = bpy.data.materials.new(name); t = mm.node_tree; t.nodes.clear()
    g = t.nodes.new('ShaderNodeGroup'); g.node_tree = MG; g.name = 'Look'
    g.inputs['Paint Colour'].default_value = srgb(hexcol); g.inputs['Paint'].default_value = paint
    o = t.nodes.new('ShaderNodeOutputMaterial'); t.links.new(g.outputs[0], o.inputs['Surface']); return mm
def box(name, c, s, mat, rot=0.0, bevel=0.012):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=s, verts=bm.verts)
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=2, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.set_sharp_from_angle(angle=r(40))
    o = link(bpy.data.objects.new(name, me)); o.location = c; o.rotation_euler = (0, 0, rot); me.materials.append(mat); return o
def drum(name, c, rad, hgt, mat):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=rad, radius2=rad, depth=hgt)
    for z in (-0.3, 0.0, 0.3):   # rolling hoops
        for v in bm.verts: pass
    bmesh.ops.bevel(bm, geom=[e for e in bm.edges if e.calc_face_angle(0) > 0.6], offset=0.01, segments=2, affect='EDGES')
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.set_sharp_from_angle(angle=r(40))
    o = link(bpy.data.objects.new(name, me)); o.location = c; me.materials.append(mat); return o
crate_m = metal('RB_prop_crate', '#4F5A3A'); drum_m = metal('RB_prop_drum', '#8A3B22'); pal_m = metal('RB_prop_pallet', '#6B5B44', 0.6)
box('Prop_crate_A', (2.1, 0.9, 0.45), (1.2, 0.9, 0.9), crate_m, r(12))
box('Prop_crate_B', (2.15, 0.95, 1.2), (0.7, 0.6, 0.6), crate_m, r(-8))
for i in range(5):
    box(f'Prop_pallet_slat{i}', (-2.0 + 0.22 * i - 0.44, 1.6, 0.14), (0.14, 1.2, 0.025), pal_m, 0, 0.004)
for i, x in enumerate((-0.52, 0.0, 0.52)):
    box(f'Prop_pallet_block{i}', (-2.0, 1.6 + x, 0.06), (1.0, 0.1, 0.1), pal_m, r(90), 0.004)
drum('Prop_drum_A', (-1.9, 1.6, 0.6), 0.29, 0.88, drum_m)
drum('Prop_drum_B', (-2.6, 2.3, 0.44), 0.29, 0.88, drum_m)

# ---------------------------------------------------------------- lights: hard warm key, cool rim, soft fill, dim world
for o in [o for o in W.objects if o.type == 'LIGHT']: bpy.data.objects.remove(o)
def light(name, kind, loc, aim, energy, color, size=0.2, spot=None):
    Ld = bpy.data.lights.new(name, kind); Ld.energy = energy; Ld.color = color
    if kind == 'AREA': Ld.size = size
    if kind == 'SPOT': Ld.spot_size = r(spot or 45); Ld.spot_blend = 0.35; Ld.shadow_soft_size = size
    if kind == 'SUN': Ld.angle = r(size)
    o = link(bpy.data.objects.new(name, Ld)); o.location = loc
    o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
light('Key_Spot', 'SPOT', (-3.2, -3.4, 5.2), (0, -0.2, 0.9), 6000, (1.0, 0.86, 0.68), 0.12, 34)
light('Rim_Spot', 'SPOT', (2.6, 3.4, 4.0), (0, 0, 1.4), 3000, (0.62, 0.78, 1.0), 0.25, 40)
light('Fill_Area', 'AREA', (4.0, -3.0, 2.2), (0, 0, 1.1), 160, (0.8, 0.86, 0.95), 4.0)
light('Back_Bounce', 'AREA', (-4.5, 4.5, 3.0), (0, 0, 0.5), 120, (1.0, 0.9, 0.8), 6.0)
w = bpy.data.worlds.new('RB_Hangar'); sc.world = w; bg = w.node_tree.nodes['Background']
bg.inputs[0].default_value = (0.045, 0.05, 0.058, 1); bg.inputs[1].default_value = 1.0

# ---------------------------------------------------------------- haze + dust motes
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); bmesh.ops.scale(bm, vec=(16, 16, 8), verts=bm.verts)
hz = bpy.data.meshes.new('haze'); bm.to_mesh(hz); bm.free()
haze = link(bpy.data.objects.new('Haze_Volume', hz)); haze.location = (0, 0, 4.0)
hm = bpy.data.materials.new('RB_haze'); t = hm.node_tree; t.nodes.clear()
vs = t.nodes.new('ShaderNodeVolumePrincipled'); vs.inputs['Density'].default_value = 0.018
vs.inputs['Anisotropy'].default_value = 0.35; vs.inputs['Color'].default_value = (0.85, 0.85, 0.85, 1)
o_ = t.nodes.new('ShaderNodeOutputMaterial'); t.links.new(vs.outputs[0], o_.inputs['Volume']); hz.materials.append(hm)
haze.display_type = 'BOUNDS'; haze.hide_viewport = True     # render-only: keeps the viewport fast
bm = bmesh.new()
for i in range(500):
    c = Vector((random.uniform(-3, 3), random.uniform(-3, 2), random.uniform(0.2, 3.5)))
    rr = random.uniform(0.0015, 0.0035)
    m_ = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=rr, matrix=Matrix.Translation(c))
motes_me = bpy.data.meshes.new('motes'); bm.to_mesh(motes_me); bm.free()
motes = link(bpy.data.objects.new('Dust_Motes', motes_me))
mm = bpy.data.materials.new('RB_mote'); t = mm.node_tree; bb = t.nodes['Principled BSDF']
bb.inputs['Base Color'].default_value = (0.8, 0.75, 0.65, 1); bb.inputs['Roughness'].default_value = 0.9
bb.inputs['Transmission Weight'].default_value = 0.4; motes_me.materials.append(mm)
# slow drift: animate the whole cloud with a gentle noise path
motes.animation_data_create()
for f, (x, y, z) in ((1, (0, 0, 0)), (120, (0.06, -0.03, 0.04)), (240, (0.1, -0.02, 0.0))):
    motes.location = (x, y, z); motes.keyframe_insert('location', frame=f)

# ---------------------------------------------------------------- render settings
sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'AgX'
try: sc.view_settings.look = 'AgX - Medium High Contrast'
except TypeError: pass
sc.cycles.volume_step_rate = 4.0; sc.cycles.volume_max_steps = 256
print('WORLD footprints', len(fp), 'objects', len(W.objects))
bpy.ops.wm.save_as_mainfile(filepath=out)
