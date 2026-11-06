"""RX-07 'step forward' (3 steps, 0.6 m), rebuilt like the demo walk (user, 2026-11-06: "all walkcycles tested?").
The old version lifted each foot in two humps (the raised toe pivot) and had no heel-to-toe roll timing.
Each step now: weight onto the stance foot, heel peels with the toe planted, toe pushes off, one swing arc, toes up,
heel strike, foot slaps flat, body drops on impact and rebounds. Side-to-side balance comes from tools/balance_fix.py,
arm clearance from arm_clear.py.
python3 step_forward.py in.blend out.blend"""
import bpy, sys, math
from bpy_extras import anim_utils
src, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=src)
A = bpy.data.actions['RM_step_forward']; cb = anim_utils.action_get_channelbag_for_slot(A, A.slots[0])
WIPE = ('IK_foot', 'roll_ball', 'roll_heel', 'roll_toe', 'IK-toe', 'COG', 'hips', 'waist', 'FK-upper_arm')
for c in [c for c in cb.fcurves if any(f'"{w}' in c.data_path for w in WIPE)]: cb.fcurves.remove(c)
P = lambda b, ch: f'pose.bones["{b}"].{ch}'
def fc(path, i):
    return next((c for c in cb.fcurves if c.data_path == path and c.array_index == i), None) or \
        cb.fcurves.new(path, index=i, group_name=path.split('"')[1])
def put(path, keys, deg=False):
    for f, v in keys:
        for i, x in enumerate(v):
            k = fc(path, i).keyframe_points.insert(f, math.radians(x) if deg else x, options={'FAST'})
            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
TOE_K = 0.375
def step(S, peel, lift, contact, d0, d1, h=0.12, ball=18):
    sw = contact - lift; f = lambda t: round(lift + sw * t)
    put(P(f'IK_foot.{S}', 'location'), [(peel, (0, d0, 0)), (lift, (0, d0, 0)), (f(0.15), (0, d0 + 0.02 * (d1 - d0), 0.3 * h)),
                                         (f(0.5), (0, d0 + 0.5 * (d1 - d0), h)), (f(0.8), (0, d0 + 0.9 * (d1 - d0), 0.45 * h)),
                                         (contact, (0, d1, 0)), (contact + 3, (0, d1, 0))])
    put(P(f'roll_ball.{S}', 'rotation_euler'), [(peel, (0, 0, 0)), (lift, (ball, 0, 0)), (f(0.3), (ball * 0.75, 0, 0)),
                                                (f(0.5), (ball * 0.2, 0, 0)), (f(0.65), (0, 0, 0))], deg=True)
    put(P(f'IK-toe.{S}', 'rotation_euler'), [(peel, (0, 0, 0)), (lift, (ball * TOE_K, 0, 0)), (f(0.3), (0, 0, 0))], deg=True)
    put(P(f'roll_heel.{S}', 'rotation_euler'), [(f(0.5), (0, 0, 0)), (f(0.8), (7, 0, 0)), (contact - 1, (11, 0, 0)), (contact, (12, 0, 0)),
                                                (contact + 1, (8, 0, 0)), (contact + 2, (3, 0, 0)), (contact + 3, (0, 0, 0))], deg=True)
for S in 'LR':
    put(P(f'IK_foot.{S}', 'location'), [(1, (0, 0, 0))])
    for r in ('roll_ball', 'roll_heel', 'IK-toe'): put(P(f'{r}.{S}', 'rotation_euler'), [(1, (0, 0, 0))], deg=True)
step('L', 6, 12, 26, 0.0, 0.30)
step('R', 32, 38, 52, 0.0, 0.60, h=0.13)
step('L', 58, 63, 72, 0.30, 0.60, h=0.07, ball=12)
for S in 'LR': put(P(f'IK_foot.{S}', 'location'), [(80, (0, 0.60, 0))])
# contact -> down -> passing (up) -> next contact; y = forward travel (COG local y = world +y, so forward is negative)
put(P('COG', 'location'), [(1, (0, 0, -0.03)), (6, (0, -0.005, -0.045)), (12, (0, -0.03, -0.055)), (19, (0, -0.09, -0.042)),
                           (26, (0, -0.16, -0.052)), (29, (0, -0.19, -0.088)), (34, (0, -0.25, -0.06)), (38, (0, -0.31, -0.055)),
                           (45, (0, -0.38, -0.042)), (52, (0, -0.46, -0.054)), (55, (0, -0.49, -0.09)), (58, (0, -0.53, -0.06)),
                           (63, (0, -0.56, -0.055)), (67, (0, -0.58, -0.044)), (72, (0, -0.595, -0.05)), (74, (0, -0.60, -0.072)),
                           (80, (0, -0.60, -0.035))])
put(P('hips', 'rotation_euler'), [(1, (2, 0, 0)), (12, (2, 0, -5)), (26, (1, 0, -1)), (29, (-1, 0, 1)), (33, (3, 0, 3)),
                                  (38, (2, 0, 5)), (52, (1, 0, 1)), (55, (-1, 0, -1)), (59, (3, 0, -3)), (63, (2, 0, -4)),
                                  (72, (1, 0, -1)), (74, (0.5, 0, 0.3)), (80, (2, 0, 0))], deg=True)
put(P('waist', 'rotation_euler'), [(1, (0, 0, 0)), (19, (0, 4, 0)), (32, (0, 0, 0)), (45, (0, -4, 0)), (58, (0, 0, 0)),
                                   (67, (0, 2, 0)), (78, (0, 0, 0))], deg=True)
for S, sg in (('L', 1), ('R', -1)):   # arms swing against the stepping leg, a little out from the body
    put(P(f'FK-upper_arm.{S}', 'rotation_euler'), [(1, (0, 0, 0)), (19, (-14 * sg, 0, 5 * sg)), (45, (14 * sg, 0, 5 * sg)),
                                                   (67, (-6 * sg, 0, 4 * sg)), (80, (0, 0, 0))], deg=True)
for c in cb.fcurves: c.update()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
print('STEP_FORWARD ok')
