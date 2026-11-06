"""RX-07 arms out while the body sways (physics audit, 2026-11-06).
With the weight now carried over the planted foot, the body swings ~20 cm sideways at each step, which carried the
far hand over the lifting foot (fingers into the foot cheek) and the knee piston. A heavy biped also holds its arms
out a little on one foot for balance, so the arm on the swing-leg side lifts out (shoulder abduction) for each step.
Applied to RM_demo_10s, RM_demo_weighted and RM_step_forward (after balance_fix / weight.py), on top of the existing arm swing.
python3 arm_clear.py in.blend out.blend"""
import bpy, sys, math
from bpy_extras import anim_utils
src, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=src)
# (side, degrees out, first frame, last frame): the arm on the swing-leg side, for each step of the demo walk
DEMO = ([('L', 9, 84, 116), ('R', 9, 114, 144), ('L', 8, 142, 180)], 80, 184)
PLAN = {'RM_demo_10s': DEMO, 'RM_demo_weighted': DEMO,
        'RM_step_forward': ([('L', 9, 2, 32), ('R', 9, 28, 58), ('L', 9, 54, 80)], 1, 80)}
import os
ONLY = os.environ.get('ARM_ONLY')   # re-apply to one motion after it's rebuilt
for an, (BUMPS, F0, F1) in PLAN.items():
    if ONLY and an != ONLY: continue
    a = bpy.data.actions[an]; cb = anim_utils.action_get_channelbag_for_slot(a, a.slots[0])
    for S, sg in (('L', 1), ('R', -1)):
        c = next(c for c in cb.fcurves if c.data_path == f'pose.bones["FK-upper_arm.{S}"].rotation_euler' and c.array_index == 2)
        vals = {f: c.evaluate(f) for f in range(F0, F1 + 1)}
        for s_, deg, b0, b1 in BUMPS:
            if s_ != S: continue
            for f in range(max(b0, F0), min(b1, F1) + 1):
                vals[f] += sg * math.radians(deg) * 0.5 * (1 - math.cos(2 * math.pi * (f - b0) / (b1 - b0)))
        for k in [k for k in c.keyframe_points if F0 <= k.co.x <= F1][::-1]: c.keyframe_points.remove(k)
        for f, v in vals.items():
            k = c.keyframe_points.insert(f, v, options={'FAST'}); k.interpolation = 'BEZIER'
            k.handle_left_type = k.handle_right_type = 'AUTO_CLAMPED'
        c.update()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, relative_remap=False)
print('ARM_CLEAR ok')
