"""RX-07 walk loop, rebuilt like the demo walk (physics audit, 2026-11-06).
The old 48-frame loop had each foot in the air exactly half the time, so there was never a moment with both feet
down: at every heel strike the trailing toe had already lifted and the robot balanced on one heel edge. It also
used the old raised toe pivot (lift / dip / lift).
This loop (in place, the feet slide back under the body as on a treadmill, 0.30 m stride, 2 s per cycle):
  - each foot stands 28 frames and swings 20, so both feet are down for 4 frames at every step (heavy, careful gait)
  - stance: heel strike -> foot slaps flat -> rolls over -> heel peels while the toe stays planted -> toe pushes off
  - one swing arc per step, toes up before contact
  - body lowest just after each contact, highest at passing; hips roll onto the stance leg; arms counter-swing
  - every channel loops seamlessly (Cycles modifiers, cycle-aware handles)
Side-to-side balance is solved afterwards by tools/balance_fix.py.
python3 walk_loop.py in.blend out.blend"""
import bpy, sys, math
from bpy_extras import anim_utils
src, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=src)
A = bpy.data.actions['RM_walk_loop']; cb = anim_utils.action_get_channelbag_for_slot(A, A.slots[0])
P = lambda b, ch: f'pose.bones["{b}"].{ch}'
T, STANCE, STRIDE, H, BALL = 48, 28, 0.30, 0.10, 18
import os; TOE_K = float(os.environ.get('TOE_K', '0.15'))   # toe counter-turn during the peel, so it stays flat on the floor
SWING = T - STANCE; v = STRIDE / STANCE
WIPE = ('IK_foot', 'roll_ball', 'roll_heel', 'roll_toe', 'IK-toe', 'COG', 'hips', 'waist', 'FK-upper_arm')
for c in [c for c in cb.fcurves if any(f'"{w}' in c.data_path for w in WIPE)]: cb.fcurves.remove(c)


def fc(path, i):
    return next((c for c in cb.fcurves if c.data_path == path and c.array_index == i), None) or \
        cb.fcurves.new(path, index=i, group_name=path.split('"')[1])


def put(path, keys, deg=False, lin=()):
    """keys for one cycle, in order; a copy of the first key is added one period later and a Cycles modifier repeats it"""
    keys = sorted(keys); keys.append((keys[0][0] + T, keys[0][1]))
    for i in range(len(keys[0][1])):
        c = fc(path, i)
        for f, val in keys:
            x = val[i]; k = c.keyframe_points.insert(f, math.radians(x) if deg else x, options={'FAST'})
            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
            k.interpolation = 'LINEAR' if f in lin else 'BEZIER'


def foot(S, contact):
    """contact = heel strike frame; the foot stands STANCE frames, then swings back in front"""
    lift = contact + STANCE; peel = lift - 6; land = contact + T
    y = lambda f: 0.15 - v * (f - contact)            # stance: slides back at body speed
    f = lambda t: round(lift + SWING * t)
    keys = [(contact, (0, 0.15, 0)), (peel, (0, y(peel), 0)), (lift, (0, -0.15, 0)),
            (f(0.15), (0, -0.15 + 0.02 * STRIDE, 0.3 * H)), (f(0.5), (0, 0.0, H)), (f(0.8), (0, 0.15 - 0.1 * STRIDE, 0.45 * H))]
    put(P(f'IK_foot.{S}', 'location'), keys, lin={contact, peel, contact + T})
    put(P(f'roll_ball.{S}', 'rotation_euler'), [(contact, (0, 0, 0)), (peel, (0, 0, 0)), (lift, (BALL, 0, 0)), (f(0.3), (BALL * 0.75, 0, 0)),
                                               (f(0.5), (BALL * 0.2, 0, 0)), (f(0.65), (0, 0, 0))], deg=True)
    put(P(f'IK-toe.{S}', 'rotation_euler'), [(contact, (0, 0, 0)), (peel, (0, 0, 0)), (lift, (BALL * TOE_K, 0, 0)), (f(0.3), (0, 0, 0))], deg=True)
    put(P(f'roll_heel.{S}', 'rotation_euler'), [(land - T + 3, (0, 0, 0)), (f(0.5), (0, 0, 0)), (f(0.8), (7, 0, 0)), (land - 1, (11, 0, 0)), (land, (12, 0, 0)),
                                               (land + 1 - T, (8, 0, 0)), (land + 2 - T, (3, 0, 0))], deg=True)


foot('L', 1); foot('R', 1 + T // 2)
# body: down just after each contact, up at passing (mid stance)
put(P('COG', 'location'), [(1, (0, 0, -0.055)), (4, (0, 0, -0.075)), (13, (0, 0, -0.045)), (25, (0, 0, -0.055)), (28, (0, 0, -0.075)),
                           (37, (0, 0, -0.045))])
put(P('hips', 'rotation_euler'), [(1, (2, 0, 0)), (4, (3.2, 0, 1)), (13, (2, 0, 4)), (25, (2, 0, 0)), (28, (3.2, 0, -1)), (37, (2, 0, -4))], deg=True)
put(P('waist', 'rotation_euler'), [(1, (0, 0, 0)), (13, (0, 3, 0)), (25, (0, 0, 0)), (37, (0, -3, 0))], deg=True)
for S, sg in (('L', 1), ('R', -1)):   # each arm swings with the opposite leg, a little out to clear the knee pistons
    put(P(f'FK-upper_arm.{S}', 'rotation_euler'), [(1, (-12 * sg, 0, 5 * sg)), (25, (12 * sg, 0, 5 * sg))], deg=True)
for c in cb.fcurves:
    if not any(m.type == 'CYCLES' for m in c.modifiers): c.modifiers.new('CYCLES')
    c.update()
A.use_cyclic = True; A.use_frame_range = True; A.frame_start, A.frame_end = 1, 1 + T
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
print('WALK_LOOP ok')
