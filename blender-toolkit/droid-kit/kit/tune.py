"""Fix IK pole angles, find collision-free joint limits by sweeping, verify with random poses, write limits.
python3 tune.py in.blend out.blend report.json
"""
import bpy, math, random, json, sys, time
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

IN, OUT, REP = sys.argv[-3:]
bpy.ops.wm.open_mainfile(filepath=IN)
arm = bpy.data.objects['RobotRig']; pbs = arm.pose.bones; vl = bpy.context.view_layer
rad, deg = math.radians, math.degrees
SIDES = ('L', 'R')

def upd(): vl.update()

def set_switch(v):
    for S in SIDES:
        pbs[f'IK_foot.{S}']['ik_fk'] = v; pbs[f'IK_hand.{S}']['ik_fk'] = v
    arm.update_tag(); upd()

def reset():
    for pb in pbs:
        pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)
    upd()

# ------------------------------------------------------------ IK pole angles
def ik_error():
    e = 0
    for n in ('thigh', 'shin', 'upper_arm', 'forearm'):
        for S in SIDES:
            pb = pbs[f'DEF-{n}.{S}']; b = arm.data.bones[pb.name]
            e += (pb.matrix.to_3x3() - b.matrix_local.to_3x3()).median_scale if False else \
                 sum((pb.matrix.col[i].to_3d() - b.matrix_local.col[i].to_3d()).length for i in range(3))
    return e

reset(); set_switch(1.0)
pole_report = {}
for chain in ('IK-shin', 'IK-forearm'):
    for S in SIDES:
        c = pbs[f'{chain}.{S}'].constraints['IK']
        best = None
        for a in range(-180, 181, 1):
            c.pole_angle = rad(a); upd()
            pb = pbs[f'{chain}.{S}']; b = arm.data.bones[pb.name]
            err = sum((pb.matrix.col[i].to_3d() - b.matrix_local.col[i].to_3d()).length for i in range(4))
            if best is None or err < best[0]: best = (err, a)
        c.pole_angle = rad(best[1]); pole_report[f'{chain}.{S}'] = best
upd()
pole_report['total_rest_error'] = ik_error()
print('poles', pole_report)

# ------------------------------------------------------------ collision setup
parts = [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o]
LOCAL = {}
for o in parts:
    me = o.data
    LOCAL[o.name] = ([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])

def bone_of(o): return o['rig_bone']

def snapshot():
    out = {}
    for o in parts:
        M = o.matrix_world
        vs = [M @ v for v in LOCAL[o.name][0]]
        mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        out[o.name] = (vs, mn, mx)
    return out

def collisions(skip, only=None):
    snap = snapshot(); hits = []; trees = {}
    names = [o.name for o in parts]
    for i, a in enumerate(names):
        va, amn, amx = snap[a]
        for b in names[i + 1:]:
            if (a, b) in skip: continue
            if only and a not in only and b not in only: continue
            vb, bmn, bmx = snap[b]
            if amx.x < bmn.x or bmx.x < amn.x or amx.y < bmn.y or bmx.y < amn.y or amx.z < bmn.z or bmx.z < amn.z:
                continue
            ta = trees.get(a) or trees.setdefault(a, BVHTree.FromPolygons(va, LOCAL[a][1]))
            tb = trees.get(b) or trees.setdefault(b, BVHTree.FromPolygons(vb, LOCAL[b][1]))
            if ta.overlap(tb): hits.append((a, b))
    return hits


def region(o):
    b = o['rig_bone'] if not isinstance(o, str) else o
    side = b[-1] if b[-2:] in ('.L', '.R') else ''
    if not side: return 'torso'
    if any(k in b for k in ('thigh', 'shin', 'foot', 'toe', 'plate_knee', 'skirt_side', 'piston')): return 'leg' + side
    return 'arm' + side

def self_hits(hits):
    out = []
    for a, b in hits:
        ra, rb = region(bpy.data.objects[a]), region(bpy.data.objects[b])
        if ra == rb: out.append((a, b)); continue
        if 'torso' in (ra, rb):
            limb = b if ra == 'torso' else a
            bn = bpy.data.objects[limb]['rig_bone']
            # a hand or foot touching the torso is limb-vs-body contact (shown by the Check button), not a joint fault
            if not any(k in bn for k in ('forearm', 'hand', 'f_', 'grip', 'shin', 'foot', 'toe', 'plate_forearm', 'plate_shield', 'plate_elbow', 'plate_knee')):
                out.append((a, b))
    return out

reset(); set_switch(0.0)
SKIP = set()
names = [o.name for o in parts]
for i, a in enumerate(names):
    for b in names[i + 1:]:
        if bone_of(bpy.data.objects[a]) == bone_of(bpy.data.objects[b]): SKIP.add((a, b))
rest_hits = collisions(SKIP)
SKIP |= set(rest_hits)
print('rest contacts (designed joints):', len(rest_hits))

# ------------------------------------------------------------ DOF design ranges (deg)
D = {}
def dof(b, **ax): D[b] = ax
dof('hips', x=(-20, 20), y=(-30, 30), z=(-12, 12))
dof('waist', y=(-40, 40))          # turntable: yaw only
dof('body')                        # fixed to the waist turntable
dof('hatch', x=(0, 110)); dof('sensor', x=(-30, 30), y=(-120, 120))
dof('skirt_front', x=(-10, 45)); dof('skirt_back', x=(-10, 45))
for S in SIDES:
    dof(f'shoulder.{S}')               # shoulder frame is fixed to the torso
    dof(f'FK-upper_arm.{S}', x=(-80, 170), y=(-70, 70), z=(-100, 100))
    dof(f'FK-forearm.{S}', x=(0, 155))
    dof(f'FK-hand.{S}', x=(-80, 80), y=(-90, 90), z=(-45, 45))
    for fn in ('index', 'middle', 'ring', 'thumb'):
        dof(f'f_{fn}_1.{S}', x=(-25, 100))   # single-axis hinge
        dof(f'f_{fn}_2.{S}', x=(-10, 110)); dof(f'f_{fn}_3.{S}', x=(-10, 110))
    dof(f'FK-thigh.{S}', x=(-70, 130), y=(-50, 50), z=(-70, 70))
    dof(f'FK-shin.{S}', x=(0, 160))
    dof(f'f_thumb_0.{S}', y=(-90, 90))      # thumb swivel turret
    dof(f'FK-foot.{S}', x=(-60, 60), y=(-25, 25))   # ankle: pitch + roll
    dof(f'FK-toe.{S}', x=(-50, 70))
    for p, rng in (('plate_pauldron', dict(x=(-12, 12))), ('plate_elbow', dict(x=(-5, 40))),
                   ('plate_forearm', dict(x=(-5, 45))), ('plate_shield', dict(x=(-5, 45))),
                   ('plate_thigh', dict(x=(-5, 45))), ('plate_knee', dict(x=(-5, 40))),
                   ('skirt_side', dict(z=(-30, 30)))):
        dof(f'{p}.{S}', **rng)
AXI = {'x': 0, 'y': 1, 'z': 2}

MARGIN = 1.0
def apply_limits(b, lim):
    pb = pbs[b]
    for c in [c for c in pb.constraints if c.type == 'LIMIT_ROTATION']: pb.constraints.remove(c)
    c = pb.constraints.new('LIMIT_ROTATION'); c.name = 'joint limits'
    if b.startswith(('plate_pauldron', 'skirt_side')):   # limit the user's own rotation, auto-follow adds on top
        pb.constraints.move(len(pb.constraints) - 1, 0)
    c.owner_space = 'LOCAL'; c.use_transform_limit = True
    if pb.rotation_mode in ('XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'): c.euler_order = pb.rotation_mode
    lock = [True, True, True]
    for a in 'xyz':
        lo, hi = lim.get(a, (0, 0))
        lo = min(0, lo + MARGIN) if lo < 0 else lo; hi = max(0, hi - MARGIN) if hi > 0 else hi
        setattr(c, f'use_limit_{a}', True); setattr(c, f'min_{a}', rad(lo)); setattr(c, f'max_{a}', rad(hi))
        if a in lim and (hi - lo) > 0.5: lock[AXI[a]] = False
    pb.lock_rotation = lock
    return lock

STEP = 2.5
LIM = {b: {a: [0.0, 0.0] for a in ax} for b, ax in D.items()}
log = []
t0 = time.time()
reset()
ARMOUR_FIRST = sorted(D, key=lambda b: 0 if b.startswith(('plate', 'skirt', 'hatch', 'sensor')) else 1)
for b in ARMOUR_FIRST:
    ax = D[b]
    for a, (lo, hi) in ax.items():
        for sign, end in ((1, hi), (-1, lo)):
            if end == 0: continue
            ok = 0.0; ang = 0.0
            while abs(ang) < abs(end):
                ang = min(abs(ang) + STEP, abs(end)) * sign
                e = [0, 0, 0]; e[AXI[a]] = rad(ang); pbs[b].rotation_euler = e; upd()
                h = self_hits(collisions(SKIP))
                if h:
                    log.append(dict(bone=b, axis=a, at=ang, hit=h[:3])); break
                ok = ang
            LIM[b][a][0 if sign < 0 else 1] = ok
            pbs[b].rotation_euler = (0, 0, 0)
    apply_limits(b, LIM[b])
    upd()
print('sweep done %.0fs' % (time.time() - t0))

# ------------------------------------------------------------ random combo poses
def bone_chain(name):
    out = []; b = arm.data.bones[name]
    while b: out.append(b.name); b = b.parent
    return out

def dkey(n):
    if n.startswith('GIM'):
        n = n.split('-', 1)[1]
        return 'FK-' + n if 'FK-' + n in D else n
    return n.replace('DEF-', 'FK-')

def dofs_between(pa, pb_):
    A, Bc = bone_chain(pa), bone_chain(pb_)
    path = (set(A) ^ set(Bc))
    res = set()
    for n in path:
        b = arm.data.bones[n]
        while b is not None and dkey(b.name) not in D:
            b = b.parent
        if b is not None:
            n2 = dkey(b.name)
            if n2 in D: res.add(n2)
    # plates that follow limbs
    for n in list(res) + [pa, pb_]:
        for k, src in (('plate_pauldron', 'FK-upper_arm'), ('skirt_side', 'FK-thigh'), ('skirt_front', 'FK-thigh')):
            if n.startswith(k): res.add(src + n[len(k):] if n[len(k):] else src + '.L')
    return res

GROUPS = {}
for S in SIDES:
    GROUPS[f'arm.{S}'] = [b for b in D if b.endswith('.' + S) and (b.startswith(('FK-upper', 'FK-fore', 'FK-hand', 'f_', 'shoulder', 'plate_pa', 'plate_el', 'plate_fo', 'plate_sh')))]
    GROUPS[f'hand.{S}'] = [b for b in D if b.endswith('.' + S) and b.startswith(('f_', 'FK-hand'))]
    GROUPS[f'leg.{S}'] = [b for b in D if b.endswith('.' + S) and b.startswith(('FK-thigh', 'FK-shin', 'FK-foot', 'FK-toe', 'plate_th', 'plate_kn', 'skirt_side'))]
GROUPS['torso'] = ['hips', 'waist', 'body', 'hatch', 'sensor', 'skirt_front', 'skirt_back']
GROUPS['all'] = list(D)

rng = random.Random(7)
def random_pose(bones, bias=0.85):
    vals = {}
    for b in bones:
        e = [0, 0, 0]
        for a, (lo, hi) in LIM[b].items():
            u = rng.random() * bias
            v = (hi if rng.random() < 0.5 else lo) * u
            e[AXI[a]] = rad(v); vals[(b, a)] = v
        pbs[b].rotation_euler = e
    upd(); return vals

# working ranges the walk / crouch / reach need: random combos may not shrink these joints below them
FLOOR = {('FK-thigh', 'x', 1): 60, ('FK-thigh', 'x', 0): 45, ('FK-shin', 'x', 1): 95, ('FK-forearm', 'x', 1): 80,
         ('FK-upper_arm', 'x', 1): 70, ('FK-upper_arm', 'x', 0): 45}
shrinks = 0; combo_log = []
for gname, bones in GROUPS.items():
    n = 140 if gname != 'all' else 220
    clean = 0; tries = 0
    while clean < n and tries < n * 8:
        tries += 1
        reset(); vals = random_pose(bones, 1.0)
        h = self_hits(collisions(SKIP))
        if not h: clean += 1; continue
        clean = 0
        a, b = h[0]
        cand = dofs_between(bpy.data.objects[a]['rig_bone'], bpy.data.objects[b]['rig_bone'])
        cand = [c for c in cand if c in bones]
        if not cand: continue
        combo_log.append(dict(group=gname, hit=[a, b], dofs=sorted(cand)))
        best = None
        for c in cand:
            for ax_ in LIM[c]:
                v = vals.get((c, ax_), 0); i = 1 if v > 0 else 0
                lim = LIM[c][ax_][i]
                if abs(lim) < 1 or abs(v) < 1: continue
                fl = FLOOR.get((c.split('.')[0], ax_, i))
                if fl is not None and abs(lim) <= fl: continue
                r = abs(v) / abs(lim) * (2.0 if c.startswith(('plate', 'skirt')) else 1.0)
                if best is None or r > best[0]: best = (r, c, ax_, i)
        if best:
            _, c, ax_, i = best
            LIM[c][ax_][i] *= 0.96; shrinks += 1
            apply_limits(c, LIM[c])
    print(gname, 'clean run', clean, 'tries', tries)
reset()

# final verification (fresh seed)
rng = random.Random(1234); fails = []; cross = []
for k in range(400):
    reset(); random_pose(GROUPS['all'] if k % 2 else GROUPS[rng.choice(list(GROUPS))], 1.0)
    hh = collisions(SKIP); h = self_hits(hh)
    if h: fails.append(h[:2])
    if len(hh) > len(h): cross.append([x for x in hh if x not in h][:2])
reset()
print('verification self-collision fails', len(fails), 'cross-limb contacts', len(cross))

# ------------------------------------------------------------ write limits into the rig
FINAL = {}
for b, lim in LIM.items():
    apply_limits(b, lim); FINAL[b] = {a: [round(v, 1) for v in r] for a, r in lim.items()}
# IK chain gets the same limits
for S in SIDES:
    for n in ('thigh', 'shin', 'upper_arm', 'forearm'):
        src = LIM[f'FK-{n}.{S}']; pb = pbs[f'IK-{n}.{S}']
        for a in 'xyz':
            lo, hi = src.get(a, (0, 0))
            setattr(pb, f'use_ik_limit_{a}', True)
            setattr(pb, f'ik_min_{a}', rad(min(0, lo + MARGIN) if lo < 0 else lo))
            setattr(pb, f'ik_max_{a}', rad(max(0, hi - MARGIN) if hi > 0 else hi))
            if a not in src or (hi - lo) < 0.5: setattr(pb, f'lock_ik_{a}', True)
    # robot logic in IK too: the deform hand / foot can only turn on the wrist / ankle motors' axes and ranges
    apply_limits(f'DEF-hand.{S}', LIM[f'FK-hand.{S}']); apply_limits(f'DEF-foot.{S}', LIM[f'FK-foot.{S}']); apply_limits(f'DEF-toe.{S}', LIM[f'FK-toe.{S}'])
    # IK hand / foot controls rotate within the FK hand/foot ranges
    apply_limits(f'IK_hand.{S}', LIM[f'FK-hand.{S}'])
    apply_limits(f'IK-toe.{S}', LIM[f'FK-toe.{S}'])
    for r, rngd in (('roll_heel', dict(x=(0, 40))), ('roll_toe', dict(x=(0, 60))), ('roll_ball', dict(x=(0, 55)))):
        apply_limits(f'{r}.{S}', rngd); FINAL[f'{r}.{S}'] = rngd
set_switch(0.0)
for S in SIDES:
    pbs[f'IK_foot.{S}']['ik_fk'] = 1.0
upd()
bpy.ops.wm.save_as_mainfile(filepath=OUT)
json.dump(dict(poles=pole_report, rest_contacts=len(rest_hits), sweep_hits=log, limits=FINAL,
               combo_shrinks=shrinks, combo_log=combo_log[:600], verify_fails=fails[:20], verify_n=400,
               n_fails=len(fails), n_cross=len(cross), cross=cross[:20]), open(REP, 'w'), indent=1, default=str)
print('saved', OUT)
