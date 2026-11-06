"""Re-find the finger joint limits after a hand is reshaped, without re-tuning the whole rig.
Sweeps every f_* finger bone on its hinge (and the grip control that closes them all) until any part of that hand
touches another part it doesn't rest against, then writes the 'joint limits' constraints.
python3 hand_tune.py in.blend out.blend [report.json]"""
import bpy, sys, json, math
from mathutils.bvhtree import BVHTree
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
IN, OUT = a[0], a[1]; REP = a[2] if len(a) > 2 else ''
bpy.ops.wm.open_mainfile(filepath=IN)
rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.pose.bones.get('grip.L'))
pbs = rig.pose.bones; vl = bpy.context.view_layer
if rig.animation_data: rig.animation_data.action = None
RANGE = {1: (-25, 100), 2: (-10, 110), 3: (-10, 110)}
STEP, MARGIN = 2.5, 1.0

def reset():
    for p in pbs:
        if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): p.rotation_euler = (0, 0, 0); p.location = (0, 0, 0)
    vl.update()

def hand_parts(S):
    # everything on the hand and fingers, plus the wrist and forearm parts a curled finger could reach
    keep = ('f_', f'DEF-hand.{S}', f'hold.{S}', f'DEF-forearm.{S}', f'GIM1-hand.{S}', f'GIM2-hand.{S}', f'plate_shield.{S}', f'plate_forearm.{S}')
    return [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == rig and str(o.get('rig_bone', '')).startswith(keep)
            and str(o.get('rig_bone', '')).endswith('.' + S)]

def hits(parts, skip):
    dg = bpy.context.evaluated_depsgraph_get(); T = {}
    for o in parts:
        e = o.evaluated_get(dg); me = e.to_mesh(); M = e.matrix_world
        T[o.name] = BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]); e.to_mesh_clear()
    out = []
    for i, x in enumerate(parts):
        for y in parts[i + 1:]:
            if frozenset((x.name, y.name)) in skip: continue
            if T[x.name].overlap(T[y.name]): out.append((x.name, y.name))
    return out

def set_limit(b, lo, hi):
    pb = pbs[b]; c = next((c for c in pb.constraints if c.type == 'LIMIT_ROTATION'), None)
    if c is None:
        c = pb.constraints.new('LIMIT_ROTATION'); c.name = 'joint limits'; c.owner_space = 'LOCAL'; c.use_transform_limit = True
    c.use_limit_x = c.use_limit_y = c.use_limit_z = True
    c.min_x = math.radians(min(0, lo + MARGIN) if lo < 0 else lo); c.max_x = math.radians(max(0, hi - MARGIN) if hi > 0 else hi)

def unlimit(b):
    for c in pbs[b].constraints:
        if c.type == 'LIMIT_ROTATION': c.min_x, c.max_x = math.radians(-180), math.radians(180)

report = {}
for S in ('L', 'R'):
    reset(); parts = hand_parts(S)
    skip = {frozenset((x.name, y.name)) for x in parts for y in parts if x.get('rig_bone') == y.get('rig_bone')}
    rest = hits(parts, skip); skip |= {frozenset(p) for p in rest}
    fingers = [p.name for p in pbs if p.name.startswith('f_') and p.name.endswith('.' + S) and p.name[-3] in '123']
    for b in fingers: unlimit(b)
    unlimit(f'grip.{S}')
    lim = {}
    for b in sorted(fingers, key=lambda n: -int(n[-3])):   # tips first: a segment's sweep carries the ones after it
        lo_d, hi_d = RANGE[int(b[-3])]; res = [0.0, 0.0]
        for k, (sign, end) in enumerate(((-1, lo_d), (1, hi_d))):
            ang = ok = 0.0
            while abs(ang) < abs(end):
                ang = min(abs(ang) + STEP, abs(end)) * sign
                pbs[b].rotation_euler.x = math.radians(ang); vl.update()
                h = hits(parts, skip)
                if h: report.setdefault(S, {}).setdefault('stops', []).append([b, ang, h[:2]]); break
                ok = ang
            res[k] = ok; pbs[b].rotation_euler.x = 0.0; vl.update()
        lim[b] = res; set_limit(b, *res); vl.update()
    g = f'grip.{S}'; ok = 0.0; ang = 0.0   # the grip closes every finger together: stop at the first touch
    while ang < 90:
        ang += STEP; pbs[g].rotation_euler.x = math.radians(ang); vl.update()
        h = hits(parts, skip)
        if h: report.setdefault(S, {})['grip_stop'] = [ang, h[:3]]; break
        ok = ang
    pbs[g].rotation_euler.x = 0.0; set_limit(g, -15, ok); lim[g] = [-15, ok]
    report.setdefault(S, {})['limits'] = lim; report[S]['rest_contacts'] = len(rest)
    print(S, 'grip max', ok, {b: v for b, v in lim.items() if 'thumb' in b or b.startswith('f_index')})
reset()
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
if REP: json.dump(report, open(REP, 'w'), indent=1)
print('HAND_TUNE ok')
