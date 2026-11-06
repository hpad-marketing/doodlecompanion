"""Realism 4: motion weight, footstep dust, real camera.
- RM_demo_weighted = the 10 s demo plus a body dip on every footfall, spring overshoot/settle on arms, sensor and waist,
  and a faint servo jitter; springs re-baked; every frame checked (clashes, foot slide, reach, floor).
- A dust puff (volume) at every landing. Camera: 40 mm, DOF on the body, motion blur, handheld drift + footfall shake.
python3 weight.py in.blend out.blend"""
import bpy, sys, math, json
from mathutils import Vector
from bpy_extras import anim_utils
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene; arm = bpy.data.objects['RobotRig']; pbs = arm.pose.bones; ad = arm.animation_data
ns = {'__name__': 'robot_rig_ui'}; exec(bpy.data.texts['robot_rig_ui.py'].as_string(), ns)
src = bpy.data.actions['RM_demo_10s']
old = bpy.data.actions.get('RM_demo_weighted')
if old: bpy.data.actions.remove(old)
W = src.copy(); W.name = 'RM_demo_weighted'; W['label'] = 'Demo 10 s (weighted)'; W['order'] = 99
cb = anim_utils.action_get_channelbag_for_slot(W, W.slots[0])
F0, F1 = 1, 240
FR = range(F0, F1 + 1)
def fc(path, i):
    return next((c for c in cb.fcurves if c.data_path == path and c.array_index == i), None)
def rebake(c, vals):
    c.keyframe_points.clear(); c.keyframe_points.add(len(vals))
    for k, (f, v) in zip(c.keyframe_points, vals): k.co = (f, v); k.interpolation = 'LINEAR'
    c.update()

# ---- footfalls: IK foot z drops to the floor
lands = []
for S in 'LR':
    z = fc(f'pose.bones["IK_foot.{S}"].location', 2)
    zs = [z.evaluate(f) if z else 0.0 for f in FR]
    # location is local; the foot is down when it is at its lowest value
    lo = min(zs)
    for i in range(1, len(zs)):
        if zs[i - 1] > lo + 0.003 and zs[i] <= lo + 0.003: lands.append((FR[i], S))
lands.sort(); print('LANDINGS', lands)

# ---- body dip and recoil on each landing (COG z; IK keeps the feet planted)
def dip(f):
    d = 0.0
    for lf, _ in lands:
        t = f - lf
        if 0 <= t < 6: d -= 0.007 * math.sin(math.pi * t / 6)
        elif 6 <= t < 16: d += 0.0018 * math.sin(math.pi * (t - 6) / 10) * math.exp(-(t - 6) / 8)
    return d
cz_path = 'pose.bones["COG"].location'
# COG local axes: z = world z
c = fc(cz_path, 2); rebake(c, [(f, c.evaluate(f) + dip(f)) for f in FR])

# ---- spring follow-through: 2nd-order follower (overshoot + settle), plus faint servo jitter
def follow(vals, hz=2.4, zeta=0.5, sub=8):
    w = 2 * math.pi * hz; dt = 1 / 24 / sub; y = vals[0]; v = 0.0; out = []
    for x in vals:
        for _ in range(sub):
            a = w * w * (x - y) - 2 * zeta * w * v; v += a * dt; y += v * dt
        out.append(y)
    return out
def jitter(f, seed, amp):
    return amp * (math.sin(f * 1.7 + seed) * 0.5 + math.sin(f * 3.1 + seed * 2.3) * 0.3 + math.sin(f * 5.3 + seed * 0.7) * 0.2)
SPRING = [('FK-upper_arm', 2.2, 0.5), ('FK-forearm', 2.6, 0.5), ('FK-hand', 3.0, 0.55), ('sensor', 2.0, 0.45), ('waist', 1.8, 0.6)]
n_sp = 0
for c in list(cb.fcurves):
    if not c.data_path.endswith('rotation_euler'): continue
    bn = c.data_path.split('"')[1]
    spec = next((s for s in SPRING if bn.startswith(s[0])), None)
    if not spec: continue
    vals = [c.evaluate(f) for f in FR]
    if max(vals) - min(vals) < 1e-4: continue
    y = follow(vals, spec[1], spec[2])
    j = math.radians(0.12) if bn.startswith('FK-upper_arm') or bn == 'sensor' else 0.0
    rebake(c, [(f, yy + jitter(f, hash(c.data_path) % 97 + c.array_index * 13, j)) for f, yy in zip(FR, y)]); n_sp += 1
print('SPRUNG channels', n_sp)

# ---- re-bake the antenna/cable springs on the new motion
for c in [c for c in cb.fcurves if 'SPR-' in c.data_path]: cb.fcurves.remove(c)
ad.action = W; ad.action_slot = W.slots[0]
sc.frame_start, sc.frame_end = F0, F1
arm['springs_on'] = 1; ns['_STATE'].clear()
tg = [t for ch in json.loads(arm['springs']) for t in ch['targets']]
hits = {}; slide = reach = 0.0; low = 9.0; prev = {}
def foot_world(S): return arm.matrix_world @ pbs[f'DEF-foot.{S}'].head
for f in FR:
    sc.frame_set(f); ns['spring_step'](sc)
    for t in tg: pbs[t].keyframe_insert('location', frame=f, group='springs')
    for h in ns['find_contacts'](arm, bpy.context): hits.setdefault(f'{h[0]} x {h[1]}', f)
    for S in 'LR':
        tgt = arm.matrix_world @ pbs[f'MCH-ankle.{S}'].head; fcw = foot_world(S)
        reach = max(reach, (fcw - tgt).length)
        if S in prev and (tgt - prev[S][0]).length < 1e-5: slide = max(slide, (fcw - prev[S][1]).length)
        prev[S] = (tgt.copy(), fcw.copy())
    dg = bpy.context.evaluated_depsgraph_get()
    for S in 'LR':
        o = bpy.data.objects[f'foot_block.{S}']; M = o.evaluated_get(dg).matrix_world
        low = min(low, min((M @ v.co).z for v in o.data.vertices))
arm['springs_on'] = 0     # baked
print('CHECK clashes', len(hits), list(hits.items())[:6], 'slide_mm', round(slide * 1000, 2), 'reach_mm', round(reach * 1000, 2), 'floor_mm', round(low * 1000, 2))

# ---- footstep dust: a flat volume puff at each landing
dcol = bpy.data.collections.get('Dust_Steps') or bpy.data.collections.new('Dust_Steps')
if dcol.name not in sc.collection.children: sc.collection.children.link(dcol)
for o in list(dcol.objects): bpy.data.objects.remove(o)
dm = bpy.data.materials.get('RB_step_dust') or bpy.data.materials.new('RB_step_dust'); dm.use_nodes = True
N = dm.node_tree.nodes; L = dm.node_tree.links; N.clear()
o_n = N.new('ShaderNodeOutputMaterial'); vol = N.new('ShaderNodeVolumePrincipled')
vol.inputs['Color'].default_value = (0.42, 0.39, 0.34, 1); vol.inputs['Anisotropy'].default_value = 0.3
at = N.new('ShaderNodeAttribute'); at.attribute_type = 'OBJECT'; at.attribute_name = 'rb_density'
tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 3.5; nz.inputs['Detail'].default_value = 6
L.new(tc.outputs['Object'], nz.inputs['Vector'])
grad = N.new('ShaderNodeVectorMath'); grad.operation = 'LENGTH'; L.new(tc.outputs['Object'], grad.inputs[0])
fall = N.new('ShaderNodeMapRange'); fall.inputs[1].default_value = 1.0; fall.inputs[2].default_value = 0.3; L.new(grad.outputs['Value'], fall.inputs[0])
wisp = N.new('ShaderNodeMapRange'); wisp.inputs[1].default_value = 0.42; wisp.inputs[2].default_value = 0.7; L.new(nz.outputs['Fac'], wisp.inputs[0])
m1 = N.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'; L.new(fall.outputs[0], m1.inputs[0]); L.new(wisp.outputs[0], m1.inputs[1])
m2 = N.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; L.new(m1.outputs[0], m2.inputs[0]); L.new(at.outputs['Fac'], m2.inputs[1])
L.new(m2.outputs[0], vol.inputs['Density']); L.new(vol.outputs[0], o_n.inputs['Volume'])
npuff = 0
for lf, S in lands:
    sc.frame_set(lf); p = foot_world(S)
    for k, off in enumerate((Vector((0.0, -0.18, 0)), Vector((0.0, 0.16, 0)))):   # toe and heel side
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1)
        o = bpy.context.object; o.name = f'dust_{lf}_{S}_{k}'
        for cc in o.users_collection: cc.objects.unlink(o)
        dcol.objects.link(o); o.data.materials.append(dm)
        o.location = Vector((p.x, p.y, 0.0)) + off; o.location.z = 0.02
        o['rb_density'] = 0.0
        for t, s, d in ((-1, 0.05, 0.0), (0, 0.12, 0.0), (2, 0.16, 1.4), (10, 0.28, 0.7), (26, 0.38, 0.0)):
            o.scale = (s, s, s * 0.32); o.location.z = 0.01 + s * 0.2; o['rb_density'] = d
            o.keyframe_insert('scale', frame=lf + t); o.keyframe_insert('location', index=2, frame=lf + t)
            o.keyframe_insert('["rb_density"]', frame=lf + t)
        o.visible_shadow = False; npuff += 1
print('DUST puffs', npuff)

# ---- camera: real lens behaviour
cam = sc.camera; cd = cam.data
cd.lens = 40; cd.sensor_width = 36
cd.dof.use_dof = True; cd.dof.focus_object = bpy.data.objects['body_box']; cd.dof.aperture_fstop = 2.8
cd.dof.aperture_blades = 7; cd.dof.aperture_ratio = 1.0
sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.5
cam.delta_location = (0, 0, 0); cam.delta_rotation_euler = (0, 0, 0)
if cam.animation_data and cam.animation_data.action: cam.animation_data.action = None
cam.keyframe_insert('delta_rotation_euler', frame=F0); cam.keyframe_insert('delta_location', index=2, frame=F0)
cact = cam.animation_data.action; ccb = anim_utils.action_get_channelbag_for_slot(cact, cam.animation_data.action_slot)
for c in ccb.fcurves:
    if c.data_path == 'delta_rotation_euler':     # slow handheld drift
        m = c.modifiers.new('NOISE'); m.scale = 45; m.strength = math.radians(0.35); m.phase = 7 + c.array_index * 11
    if c.data_path == 'delta_location':            # footfall shake, a touch after the impact
        vals = []
        for f in FR:
            d = 0.0
            for lf, _ in lands:
                t = f - lf - 1
                if 0 <= t < 14: d += -0.006 * math.exp(-t / 3.5) * math.cos(t * 1.4)
            vals.append((f, d))
        rebake(c, vals)
print('CAMERA lens 40, f/2.8 on body, motion blur 0.5, shake on', len(lands), 'footfalls')
sc.frame_set(F0)
bpy.ops.wm.save_as_mainfile(filepath=out)
