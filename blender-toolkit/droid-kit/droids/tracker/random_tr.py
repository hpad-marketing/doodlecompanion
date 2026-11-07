"""Random mixed poses inside the limits: every part vs every part and the floor. python3 random_tr.py N in.blend"""
import bpy, sys, json, math, random, time
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from trcheck import Checker
N, blend = int(sys.argv[-2]), sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=blend)
arm = bpy.data.objects['TrackerRig']; p = arm.pose.bones
ck = Checker(arm)
CH = []
for pb in p:
    for c in pb.constraints:
        if c.mute: continue
        if c.type == 'LIMIT_ROTATION':
            for a, l in zip('xyz', pb.lock_rotation):
                if not l: CH.append((pb.name, 'rotation_euler', 'xyz'.index(a), getattr(c, f'min_{a}'), getattr(c, f'max_{a}')))
        if c.type == 'LIMIT_LOCATION':
            for a, l in zip('xyz', pb.lock_location):
                if not l and getattr(c, f'use_min_{a}'): CH.append((pb.name, 'location', 'xyz'.index(a), getattr(c, f'min_{a}'), getattr(c, f'max_{a}')))
CH = [c for c in CH if not c[0].startswith(('eye.', 'mouth', 'track_frame'))]
print('channels', len(CH))
random.seed(int(sys.argv[-3]) if len(sys.argv) > 3 and sys.argv[-3].isdigit() else 5)
bad = {}; t = time.time()
for n in range(N):
    for b, ch, i, lo, hi in CH:
        v = random.choice((lo, hi, random.uniform(lo, hi), random.uniform(lo, hi), 0.0))
        val = list(getattr(p[b], ch)); val[i] = v; setattr(p[b], ch, val)
    arm['track_L'] = random.uniform(-3, 3); arm['track_R'] = random.uniform(-3, 3)
    bpy.context.view_layer.update()
    # the chassis can only reach poses its four struts allow, and the scoop stops on the floor: resample those
    for tries in range(40):
        bad_s = ck.strokes() and any('strut' in x[0] for x in ck.strokes())
        sc = min(ck.world(o)[:, 2].min() for o in ck.parts if o['rig_bone'] in ('scoop_tilt', 'scoop_lift')) < -0.0005
        if not bad_s and not sc: break
        for b, ch, i, lo, hi in CH:
            if (bad_s and b == 'suspension') or (sc and b in ('scoop_lift', 'scoop_tilt', 'suspension')):
                val = list(getattr(p[b], ch)); val[i] = random.uniform(lo, hi) * (0.5 if tries > 10 else 1); setattr(p[b], ch, val)
        bpy.context.view_layer.update()
    for k in ck.hits():
        kk = ' | '.join(map(str, k[:2]))
        if kk not in bad: bad[kk] = {f'{b}:{ch}:{i}': round(getattr(p[b], ch)[i], 3) for b, ch, i, lo, hi in CH}
print('time', round(time.time() - t, 1), 'poses', N, 'clash pairs', len(bad))
for k in list(bad)[:30]: print('BAD', k)
json.dump(bad, open('out/random_bad.json', 'w'), indent=1)
