"""RX-07 heavy walk (user, 2026-11-06: "the foot is not moving believably, movement is not convincing nor is the weight").
What was wrong:
  - the toe-off pivot (roll_ball) sat 6 cm above the floor, so peeling the heel pushed the front of the foot block into
    the floor; the floor clamp then lifted the whole foot, giving a lift / dip / lift / land double hump
  - low flat swing (8.5 cm), tiny 3 cm body drop, every step the same length and timing
What this does (RM_demo_10s frames 88-170, then RM_demo_weighted is rebuilt from it by weight.py):
  - roll_ball pivot moved down to the floor at the ball edge, so the toe stays planted while the heel peels
  - each step: weight fully over the stance foot first (body drops as it loads), heel peels, toe pushes off,
    high swing, toes up before contact, heel strike, foot slaps flat, body compresses on impact and rebounds
  - hips roll onto the stance leg and pitch on impact, waist counter-turns, arms counter-swing
  - steps differ: 13, 14 and 8 frame swings, the last one a short closing step
python3 walk_fix.py in.blend out.blend"""
import bpy, sys, math
from bpy_extras import anim_utils
src, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=src)
rig = bpy.data.objects['RobotRig']; arm = rig.data
# ---- toe-off pivot on the floor
bpy.context.view_layer.objects.active = rig; rig.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
import os
BALL_Z = float(os.environ.get('RX_BALL_Z', '0.0'))
for S in 'LR':
    b = arm.edit_bones[f'roll_ball.{S}']; b.head.z = BALL_Z; b.tail.z = BALL_Z
bpy.ops.object.mode_set(mode='OBJECT')

A = bpy.data.actions['RM_demo_10s']; cb = anim_utils.action_get_channelbag_for_slot(A, A.slots[0])
def fcurve(path, i):
    c = next((c for c in cb.fcurves if c.data_path == path and c.array_index == i), None)
    return c or cb.fcurves.new(path, index=i, group_name=path.split('"')[1])
def clear(path, f0, f1, idx=(0, 1, 2)):
    for i in idx:
        c = fcurve(path, i)
        for k in [k for k in c.keyframe_points if f0 <= k.co.x <= f1][::-1]: c.keyframe_points.remove(k)
def put(path, keys, deg=False):
    for f, v in keys:
        for i, x in enumerate(v):
            k = fcurve(path, i).keyframe_points.insert(f, math.radians(x) if deg else x, options={'FAST'})
            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
P = lambda b, ch: f'pose.bones["{b}"].{ch}'
W0, W1 = 89, 170
for S in 'LR':
    clear(P(f'IK_foot.{S}', 'location'), W0, W1); clear(P(f'IK_foot.{S}', 'rotation_euler'), W0, W1)
    for r in ('roll_ball', 'roll_heel', 'roll_toe', 'IK-toe'): clear(P(f'{r}.{S}', 'rotation_euler'), W0, W1)
    clear(P(f'FK-upper_arm.{S}', 'rotation_euler'), W0, 163)
clear(P('COG', 'location'), W0, W1); clear(P('hips', 'rotation_euler'), W0, W1); clear(P('waist', 'rotation_euler'), W0, W1)

def step(S, peel, lift, contact, d0, d1, h=0.13, ball=18):
    """peel: heel starts to rise; lift: toe leaves; contact: heel strikes; flat 3 frames later"""
    sw = contact - lift
    f = lambda t: round(lift + sw * t)
    put(P(f'IK_foot.{S}', 'location'), [(peel, (0, d0, 0)), (lift, (0, d0, 0)), (f(0.15), (0, d0 + 0.02 * (d1 - d0), 0.3 * h)),
                                         (f(0.5), (0, d0 + 0.5 * (d1 - d0), h)), (f(0.8), (0, d0 + 0.9 * (d1 - d0), 0.45 * h)),
                                         (contact, (0, d1, 0)), (contact + 3, (0, d1, 0))])
    put(P(f'roll_ball.{S}', 'rotation_euler'), [(peel, (0, 0, 0)), (lift, (ball, 0, 0)), (f(0.3), (ball * 0.75, 0, 0)),
                                                (f(0.5), (ball * 0.2, 0, 0)), (f(0.65), (0, 0, 0))], deg=True)
    # the toe stays flat on the floor while the heel peels (it bends at the ball joint)
    put(P(f'IK-toe.{S}', 'rotation_euler'), [(peel, (0, 0, 0)), (lift, (ball * 0.42, 0, 0)), (f(0.3), (0, 0, 0))], deg=True)
    put(P(f'roll_heel.{S}', 'rotation_euler'), [(f(0.5), (0, 0, 0)), (f(0.8), (7, 0, 0)), (contact - 1, (11, 0, 0)), (contact, (12, 0, 0)),
                                                (contact + 1, (8, 0, 0)), (contact + 2, (3, 0, 0)), (contact + 3, (0, 0, 0))], deg=True)
for S in 'LR':
    put(P(f'IK_foot.{S}', 'location'), [(88, (0, 0, 0))])
    for r in ('roll_ball', 'roll_heel', 'IK-toe'): put(P(f'{r}.{S}', 'rotation_euler'), [(88, (0, 0, 0))], deg=True)
step('L', 92, 99, 112, 0.0, 0.30)
step('R', 120, 126, 140, 0.0, 0.60, h=0.14)
step('L', 148, 152, 160, 0.30, 0.60, h=0.07, ball=12)
for S in 'LR':
    put(P(f'IK_foot.{S}', 'location'), [(170, (0, 0.60, 0))])
# body: load the stance leg (drop), fall forward onto the new foot, compress on impact, rebound
# body, as a human cycle: CONTACT (heel strikes) -> DOWN (weight lands, body lowest) -> PASSING (swing foot under the
# body) -> UP (pushing off, body highest) -> next contact. x: weight over the stance foot; y: forward travel
put(P('COG', 'location'), [(88, (0, 0, -0.03)), (92, (-0.03, -0.005, -0.045)), (98, (-0.085, -0.02, -0.058)),   # load the R leg
                           (105, (-0.075, -0.09, -0.042)),                                                     # passing / up
                           (112, (-0.03, -0.17, -0.052)), (115, (0.0, -0.20, -0.088)),                        # contact, down
                           (120, (0.06, -0.25, -0.06)), (126, (0.085, -0.31, -0.055)),
                           (133, (0.075, -0.38, -0.042)),                                                       # passing / up
                           (140, (0.03, -0.46, -0.054)), (143, (0.0, -0.49, -0.09)),                          # contact, down
                           (148, (-0.055, -0.53, -0.06)), (152, (-0.07, -0.56, -0.055)),
                           (156, (-0.05, -0.58, -0.044)),                                                      # passing / up
                           (160, (-0.02, -0.595, -0.05)), (162, (0.0, -0.60, -0.072)),                        # contact, down
                           (166, (0.012, -0.60, -0.034)), (170, (0.0, -0.60, -0.03))])
put(P('hips', 'rotation_euler'), [(88, (2, 0, 0)), (98, (2, 0, -5)), (112, (1, 0, -1)), (115, (-1.5, 0, 1)), (119, (3, 0, 3)),
                                  (124, (2, 0, 5)), (140, (1, 0, 1)), (143, (-1.5, 0, -1)), (147, (3, 0, -3)), (151, (2, 0, -5)),
                                  (160, (1, 0, -1)), (162, (-0.5, 0, 0.5)), (166, (2.5, 0, 0)), (170, (2, 0, 0))], deg=True)
put(P('waist', 'rotation_euler'), [(88, (0, 0, 0)), (106, (0, 4, 0)), (119, (0, 0, 0)), (133, (0, -4, 0)), (147, (0, 0, 0)),
                                   (156, (0, 2, 0)), (166, (0, 0, 0))], deg=True)
for S, sg in (('L', 1), ('R', -1)):   # arms swing against the stepping leg
    # (and a little out from the body, so the hands clear the knee pistons as they pass)
    put(P(f'FK-upper_arm.{S}', 'rotation_euler'), [(88, (0, 0, 0)), (100, (-8 * sg, 0, 5 * sg)), (106, (-18 * sg, 0, 6 * sg)),
                                                   (133, (18 * sg, 0, 6 * sg)), (156, (-8 * sg, 0, 4 * sg))], deg=True)
for c in cb.fcurves: c.update()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
print('WALK_FIX ok')
