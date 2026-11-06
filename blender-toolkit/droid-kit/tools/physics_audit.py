"""Physics audit (user, 2026-11-06: "figure weight and actual physical logic of each part, then see if they are working
logically"). Gives every part a mass from its shape and material, then plays every library motion and checks:
  - balance: the centre of mass, and the ZMP (where the ground reaction must act, CoM height x acceleration), stay
    inside the support polygon of the planted feet
  - joint loads: torque each joint motor must hold (gravity on everything beyond it, plus the ground reaction on a
    standing leg), and how fast each joint turns
Mass model in kit/physics.py (settings 'physics' can override): painted panels and armour are 4 mm steel shells (or solid if thinner),
frames, pins and joint hardware are solid steel unless thicker than 12 mm walls, polymer parts 6 mm shells,
plus internal equipment (batteries, computer, motors) as point masses in 'physics.internal'.
DROID=<id> python3 physics_audit.py in.blend report.json [frame_step]"""
import bpy, sys, os, json, math, re
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit, physics
from physics import Body, hull, margin, G
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
src, rep = a[0], a[1]; step = int(a[2]) if len(a) > 2 else 2
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(src))
PH = kit.get('physics', {}) or {}
rig = bpy.data.objects[kit.rig_name()]; pbs = rig.pose.bones; sc = bpy.context.scene; fps = sc.render.fps
B = Body(rig); parts, total, INTERNAL, Z0 = B.parts, B.total, B.internal, B.Z0
world_points, support = B.world_points, B.support
by_bone = {}
for p in parts: by_bone[p['bone']] = by_bone.get(p['bone'], 0) + p['m']

def desc(bone):   # bone and every bone below it
    out = set(); st = [rig.data.bones[bone]]
    while st:
        b = st.pop(); out.add(b.name); st += list(b.children)
    return out
JOINTS = PH.get('joints', {
    'waist': 'waist', 'hip.L': 'DEF-thigh.L', 'hip.R': 'DEF-thigh.R', 'knee.L': 'DEF-shin.L', 'knee.R': 'DEF-shin.R',
    'ankle.L': 'DEF-foot.L', 'ankle.R': 'DEF-foot.R', 'shoulder.L': 'DEF-upper_arm.L', 'shoulder.R': 'DEF-upper_arm.R',
    'elbow.L': 'DEF-forearm.L', 'elbow.R': 'DEF-forearm.R', 'wrist.L': 'DEF-hand.L', 'wrist.R': 'DEF-hand.R'})
JD = {j: desc(b) for j, b in JOINTS.items() if b in rig.data.bones}


ad = rig.animation_data; keep = (ad.action, ad.action_slot)
acts = [x for x in bpy.data.actions if x.name.startswith('RM_') and re.search(os.environ.get('PA_ONLY', ''), x.name)]
report = dict(total_kg=round(total, 1), mass_by_group={}, motions={}, joints={})
GROUPS = [('body (box, pack, hatch, sensor, armour on it)', r'^(body|waist|hatch|sensor|antenna|cable|pack|COG|hips|skirt|root)'),
          ('legs', r'(thigh|shin|foot|toe|knee|piston|heel|ankle)'), ('arms and hands', r'(arm|forearm|hand|f_|grip|shoulder|elbow|wrist|hold|plate_(pauld|shield|forearm|elbow))')]
for nm, rx in GROUPS:
    report['mass_by_group'][nm] = round(sum(m for b, m in by_bone.items() if re.search(rx, b)), 1)
report['mass_by_group']['internal equipment'] = round(sum(it['kg'] for it in INTERNAL), 1)
peak = {j: [0.0, '', 0.0, ''] for j in JD}   # N·m, where, deg/s, where
for act in acts:
    ad.action = None; physics.reset_pose(rig)
    ad.action = act
    if act.slots: ad.action_slot = act.slots[0]
    f0, f1 = map(int, act.frame_range); frames = list(range(f0, f1 + 1, step))
    com = []; sup = []; jang = {}
    for f in frames:
        sc.frame_set(f)
        W = world_points(); c = sum((p['m'] * x for p, x in W), Vector()) / total
        com.append(c); s = support(); sup.append(s)
        for j, bones in JD.items():
            b = pbs[JOINTS[j]]; Mp = b.parent.matrix if b.parent else Matrix()
            jang.setdefault(j, []).append((Mp.inverted() @ b.matrix).to_quaternion())   # the joint's own turn, relative to its parent
        # static torques now; the leg ones get the ground reaction below once accelerations are known
        fr = []
        for j, bones in JD.items():
            J = rig.matrix_world @ pbs[JOINTS[j]].head
            t = Vector()
            for p, x in W:
                if p['bone'] in bones: t += (x - J).cross(Vector((0, 0, -p['m'] * G)))
            fr.append((j, J, t))
        com[-1] = (c, fr)
    if os.environ.get('PA_DEBUG'): print('DBG', act.name, len(frames), sum(1 for x in sup if x))
    worst = dict(com_out=0, zmp_out=0, min_zmp_margin_mm=1e9, where='')
    dt = step / fps
    for i in range(1, len(frames) - 1):
        c, fr = com[i]; acc = (com[i + 1][0] - 2 * c + com[i - 1][0]) / (dt * dt)
        s = sup[i]
        if not s: continue
        h = hull([p for v in s.values() for p in v])
        zx = c.x - (c.z - Z0) * acc.x / (G + acc.z); zy = c.y - (c.z - Z0) * acc.y / (G + acc.z)
        mc, mz = margin(h, c.x, c.y), margin(h, zx, zy)
        if os.environ.get('PA_DEBUG') == '2' or (os.environ.get('PA_DEBUG') and i == 1): print('DBG', act.name, frames[i], ''.join(sorted(s)), 'com', tuple(round(x, 3) for x in c), 'zmp', round(zx, 3), round(zy, 3), 'mc', round(mc * 1000), 'mz', round(mz * 1000), 'hull', h if os.environ.get('PA_HULL') else len(h))
        if mc < 0: worst['com_out'] += 1
        if mz < 0: worst['zmp_out'] += 1
        if mz * 1000 < worst['min_zmp_margin_mm']: worst['min_zmp_margin_mm'] = round(mz * 1000); worst['where'] = f'f{frames[i]}'
        # ground reaction: total weight + inertia at the ZMP, shared between planted feet by distance
        F = Vector((-total * acc.x, -total * acc.y, total * (G + acc.z)))
        cent = {S: sum(v, Vector()) / len(v) for S, v in s.items()}
        if len(cent) == 2:
            dL = (Vector((zx, zy)) - cent['L'].xy).length; dR = (Vector((zx, zy)) - cent['R'].xy).length
            share = {'L': dR / (dL + dR + 1e-9), 'R': dL / (dL + dR + 1e-9)}
        else: share = {S: 1.0 for S in cent}
        for j, J, t in fr:
            S = j[-1] if j[-2:] in ('.L', '.R') else ''
            tt = t.copy()
            if S in share and j.split('.')[0] in ('hip', 'knee', 'ankle'):
                P = Vector((zx, zy, Z0)) if len(cent) == 1 else Vector((cent[S].x, cent[S].y, Z0))
                tt += (P - J).cross(F * share[S])
            if tt.length > peak[j][0]: peak[j][0], peak[j][1] = tt.length, f'{act.name} f{frames[i]}'
    for j, qs in jang.items():
        for i in range(1, len(qs)):
            a_ = qs[i - 1].rotation_difference(qs[i]).angle; a_ = min(a_, 2 * math.pi - a_)   # q and -q are the same turn
            w = math.degrees(a_) / dt
            if w > peak[j][2]: peak[j][2], peak[j][3] = w, f'{act.name} f{frames[i]}'
    report['motions'][act.name] = worst
    print('MOTION', act.name, worst, flush=True)
ad.action = keep[0]
if keep[0]: ad.action_slot = keep[1]
for j, (tq, where, w, wat) in peak.items():
    report['joints'][j] = dict(peak_Nm=round(tq), at=where, peak_deg_s=round(w), speed_at=wat)
report['heaviest_parts'] = [[p['o'].name if p['o'] else p['name'], round(p['m'], 1)] for p in sorted(parts, key=lambda p: -p['m'])[:25]]
json.dump(report, open(rep, 'w'), indent=1)
print('TOTAL kg', report['total_kg'], report['mass_by_group'])
print('HEAVIEST', report['heaviest_parts'])
for j, v in report['joints'].items(): print('JOINT', j, v)
print('PHYSICS_AUDIT ok')
