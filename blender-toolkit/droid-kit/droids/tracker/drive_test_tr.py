"""Headless Drive-mode test: scripted stick input through the in-file DriveCore, every tick checked for clashes,
floor contact and strut/ram stroke.  python3 drive_test_tr.py in.blend"""
import bpy, sys, math, json
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
from trcheck import Checker
src = bpy.data.texts['tracker_rig_ui.py'].as_string()
ns = {'__name__': 'tracker_rig_ui'}; exec(compile(src, 'tracker_rig_ui.py', 'exec'), ns)
arm = bpy.data.objects['TrackerRig']; ad = arm.animation_data
if ad: ad.action = None
ns['reset_pose'](arm)
core = ns['DriveCore'](arm); ck = Checker(arm); sc = bpy.context.scene
plan = [(48, dict(thr=1.0)), (30, dict(thr=1.0, steer=0.8)), (24, dict(thr=0.0)),            # drive, arc, coast to a stop
        (36, dict(steer=1.0)), (36, dict(steer=-1.0, waist=1.0)), (20, dict(thr=-1.0)),       # spin in place, waist, reverse
        (10, dict(thr=1.0)), (6, dict(thr=0.0)),                                               # hard stop -> dive
        (48, dict(lift=1.0, tilt=1.0)), (40, dict(thr=0.6)), (12, dict()),                    # scoop all the way down, scoop scrap
        (6, dict(fire={'dump'})), (90, dict()),                                                # tip it into the bin
        (30, dict(look=1.0, ext=1.0)), (30, dict(look=-1.0, ext=-1.0)), (6, dict(fire={'happy'})), (40, dict()),
        (6, dict(fire={'scan'})), (60, dict(waist=-1.0)), (6, dict(fire={'talk'})), (30, dict()),
        (6, dict(fire={'surprised'})), (30, dict()), (6, dict(fire={'vent', 'lights'})), (40, dict(thr=0.5)),
        (24, dict(lift=1.0, tilt=1.0, thr=1.0, steer=1.0)), (20, dict(thr=-1.0, lift=1.0)),  # abuse: scoop down while driving hard
        (6, dict(fire={'power'})), (60, dict(thr=1.0)), (6, dict(fire={'power'})), (40, dict(lift=-1.0, tilt=-1.0))]
hits = {}; lowest = 9; n = 0; mx = dict(pitch=0, roll=0, lean=0); loads = set(); bad_stroke = {}
for ticks, kw in plan:
    for t in range(ticks):
        i = ns['DriveInput']()
        for k, v in kw.items():
            if k == 'fire': i.fire = set(v) if t == 0 else set()
            else: setattr(i, k, v)
        st = core.tick(i, 1 / 24); n += 1
        bpy.context.view_layer.update()
        for h in ck.hits(): hits.setdefault(' | '.join(map(str, h[:2])), n)
        for s in ck.strokes(): bad_stroke.setdefault(str(s[0]), n)
        sp = [o for o in ck.parts if o['rig_bone'] in ('scoop_lift', 'scoop_tilt')]
        lowest = min(lowest, min(float(ck.world(o)[:, 2].min()) for o in sp))
        mx['pitch'] = max(mx['pitch'], abs(math.degrees(st['sus_pitch']))); mx['roll'] = max(mx['roll'], abs(math.degrees(st['sus_roll'])))
        mx['lean'] = max(mx['lean'], abs(math.degrees(st['lean']))); loads.add(core.d.load)
print('DRIVETEST', json.dumps(dict(ticks=n, clashes=hits, strokes=bad_stroke, scoop_lowest_mm=round(lowest * 1000, 2),
                                   max_deg={k: round(v, 2) for k, v in mx.items()}, loads=sorted(loads),
                                   end=[round(core.d.x, 2), round(core.d.y, 2), round(math.degrees(core.d.yaw), 1)],
                                   powered=core.powered, whirr_groups=sorted({k for w in core.whirr_log for k in w}))))
