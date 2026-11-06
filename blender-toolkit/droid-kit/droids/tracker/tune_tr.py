"""Sweep every motor both ways until something touches (or a strut/ram runs out of stroke); write limits.
python3 tune_tr.py in.blend out.blend"""
import bpy, sys, json, math
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from trcheck import Checker
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
arm = bpy.data.objects['TrackerRig']; pbs = arm.pose.bones
bpy.context.view_layer.update()
ck = Checker(arm)
rest = [h for h in ck.hits() if len(h) == 2 and h[1] != 'FLOOR' and not str(h[0]).endswith('stroke')]
print('REST', len(rest)); print('REST_PAIRS', rest)
print('REST_OTHER', [h for h in ck.hits() if h not in rest])
ck.skip = set(rest); arm['rest_contacts'] = json.dumps(sorted(rest))
SWEEPS = [  # bone, channel, axis, design lo, hi, step, margin
    ('suspension', 'location', 'y', -0.04, 0.04, 0.001, 0.002), ('suspension', 'rotation_euler', 'x', -12, 12, 0.5, 0.5),
    ('suspension', 'rotation_euler', 'z', -12, 12, 0.5, 0.5),
    ('scoop_lift', 'rotation_euler', 'x', -90, 20, 1, 2), ('scoop_tilt', 'rotation_euler', 'x', -90, 90, 1, 2),
    ('tow_hook', 'rotation_euler', 'x', -90, 90, 1, 2), ('waist', 'rotation_euler', 'y', -180, 180, 2, 0),
    ('lean', 'rotation_euler', 'x', -40, 40, 0.5, 1), ('body', 'rotation_euler', 'y', -25, 25, 0.5, 1),
    ('bin_lid', 'rotation_euler', 'x', -10, 150, 1, 2),
]
for S in 'LR':
    SWEEPS += [(f'stalk_roll.{S}', 'rotation_euler', 'z', -80, 80, 1, 2), (f'stalk_pitch.{S}', 'rotation_euler', 'x', -80, 80, 1, 2),
               (f'stalk_ext.{S}', 'location', 'y', 0.0, 0.12, 0.002, 0.002), (f'stalk_tip.{S}', 'rotation_euler', 'x', -40, 40, 1, 2),
               (f'stalk_tip.{S}', 'rotation_euler', 'z', -40, 40, 1, 2)]
def subtree(b):
    s = {b}
    for c in pbs[b].children_recursive: s.add(c.name)
    return s
for pb in pbs:
    for c in pb.constraints:
        if c.name in ('joint limits', 'travel', 'spring'): c.mute = True
LIM = {}
for b, ch, a, lo, hi, step, margin in SWEEPS:
    i = 'xyz'.index(a); only = subtree(b)
    if b == 'suspension': only |= {o for o in pbs.keys() if o.startswith(('strut_low', 'strut_coil'))}
    if b == 'scoop_lift': only |= {'ram_house'}
    res = {}
    for sgn, end in ((-1, lo), (1, hi)):
        if end == 0: res[sgn] = (0.0, None); continue
        v = 0.0; last = 0.0; hit = None
        while abs(v) < abs(end) - 1e-9:
            v = sgn * min(abs(v) + step, abs(end))
            val = list(getattr(pbs[b], ch)); val[i] = math.radians(v) if ch.startswith('rot') else v
            setattr(pbs[b], ch, val); bpy.context.view_layer.update()
            h = ck.hits(only=only, limit=2)
            if h: hit = h[:2]; break
            last = v
        res[sgn] = (last, hit)
        val = list(getattr(pbs[b], ch)); val[i] = 0.0; setattr(pbs[b], ch, val)
    bpy.context.view_layer.update()
    lo_ok = res[-1][0] + (margin if res[-1][1] else 0) * (1 if res[-1][0] < 0 else 0)
    hi_ok = res[1][0] - (margin if res[1][1] else 0) * (1 if res[1][0] > 0 else 0)
    LIM[f'{b}:{ch}:{a}'] = dict(lo=lo_ok, hi=hi_ok, hit_lo=res[-1][1], hit_hi=res[1][1])
    print('LIM', b, ch[:3], a, round(lo_ok, 4), round(hi_ok, 4), '|', res[-1][1], '|', res[1][1])
json.dump(LIM, open('out/tune_raw.json', 'w'), indent=1, default=str)
for pb in pbs:
    for c in pb.constraints:
        if c.name in ('joint limits', 'travel', 'spring'): c.mute = False
bpy.ops.wm.save_as_mainfile(filepath=out)
