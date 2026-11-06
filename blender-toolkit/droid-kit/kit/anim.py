"""Robot demo animation (10 s @ 24 fps): power-up, sensor scan, waist turn, two planted-foot steps,
wrist + gripper demo, hatch open. Every move is one motor at a time or a few overlapping, servo-eased.
python3 anim.py [norender|stills|full] in.blend outdir
Checks every frame: part collisions, planted feet never slide, IK feet reach their targets, nothing under the floor.
"""
import bpy, sys, math, json
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Vector
mode = next((a for a in sys.argv if a in ('norender', 'stills', 'full')), 'norender')
blend, outdir = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
import stage
ns = {'__name__': 'robot_rig_ui'}; exec(bpy.data.texts['robot_rig_ui.py'].as_string(), ns)
sc = bpy.context.scene; sc.cycles.device = 'CPU'   # cloud render box has no GPU; the saved file is set back to GPU
arm = bpy.data.objects['RobotRig']; arm.hide_render = True; pbs = arm.pose.bones
sc.frame_start, sc.frame_end = 1, 240; sc.render.fps = 24
r = math.radians
for pb in pbs:
    pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0)

if arm.animation_data: arm.animation_data_clear()

def key(b, f, rot=None, loc=None):
    pb = pbs[b]
    if rot is not None:
        pb.rotation_euler = [r(a) for a in rot]; pb.keyframe_insert('rotation_euler', frame=f)
    if loc is not None:
        pb.location = loc; pb.keyframe_insert('location', frame=f)

def seq(b, frames, rot=None, loc=None):
    """frames: list of (frame, value) for one channel set"""
    for f, v in frames:
        key(b, f, rot=v if rot else None, loc=v if loc else None)

# ---------------------------------------------------------------- 1. power-up settle (1-24)
seq('COG', [(1, (0, 0, 0.0)), (14, (0, 0, -0.035)), (20, (0, 0, -0.025)), (24, (0, 0, -0.03))], loc=True)
seq('hips', [(1, (0, 0, 0)), (14, (3, 0, 0)), (24, (2, 0, 0))], rot=True)
# ---------------------------------------------------------------- 2. sensor scan: discrete servo moves (24-62)
seq('sensor', [(1, (0, 0, 0)), (24, (0, 0, 0)), (32, (8, -45, 0)), (38, (8, -45, 0)), (48, (8, 45, 0)),
               (54, (8, 45, 0)), (62, (0, 0, 0))], rot=True)
# ---------------------------------------------------------------- 3. waist turntable (60-86)
seq('waist', [(1, (0, 0, 0)), (60, (0, 0, 0)), (70, (0, -22, 0)), (78, (0, -22, 0)), (88, (0, 0, 0))], rot=True)
for S, sg in (('L', 1), ('R', -1)):
    seq(f'FK-upper_arm.{S}', [(1, (0, 0, 0)), (60, (0, 0, 0)), (70, (6 * sg, 0, 0)), (88, (0, 0, 0))], rot=True)
    seq(f'FK-forearm.{S}', [(1, (12, 0, 0)), (88, (12, 0, 0))], rot=True)
    seq(f'grip.{S}', [(1, (20, 0, 0)), (88, (20, 0, 0))], rot=True)

# ---------------------------------------------------------------- 4. walk: L step, R step, L closes (88-160)
STEP = 0.30
def foot(S, t0, t1, d0, d1, lift=0.09):
    """foot leaves at t0 (heel already rolled up), lands heel-first at t1, flat at t1+4"""
    tm = (t0 + t1) / 2
    seq(f'IK_foot.{S}', [(t0 - 6, (0, d0, 0)), (t0, (0, d0, 0.0)), (tm, (0, (d0 + d1) / 2, lift)),
                         (t1, (0, d1, 0.0)), (t1 + 4, (0, d1, 0.0))], loc=True)
    seq(f'roll_ball.{S}', [(t0 - 6, (0, 0, 0)), (t0, (22, 0, 0)), (t0 + 3, (0, 0, 0))], rot=True)
    seq(f'roll_heel.{S}', [(t1 - 3, (0, 0, 0)), (t1, (14, 0, 0)), (t1 + 4, (0, 0, 0))], rot=True)
for S in 'LR':
    key(f'IK_foot.{S}', 1, loc=(0, 0, 0)); key(f'roll_ball.{S}', 1, rot=(0, 0, 0)); key(f'roll_heel.{S}', 1, rot=(0, 0, 0))
foot('L', 98, 112, 0.0, STEP)
foot('R', 124, 138, 0.0, 2 * STEP)
foot('L', 150, 160, STEP, 2 * STEP, lift=0.05)
# COG: weight over the support foot before each lift, forward travel while the foot swings.
# The robot faces world -y. IK_foot local y = world -y and COG local y = world +y, so forward = foot y > 0, COG y < 0
seq('COG', [(88, (0, 0, -0.03)), (96, (-0.07, 0, -0.04)), (112, (-0.02, -0.16, -0.06)), (120, (0.07, -0.30, -0.04)),
            (138, (0.02, -0.46, -0.06)), (146, (-0.06, -0.58, -0.04)), (160, (0, -0.60, -0.03))], loc=True)
seq('hips', [(88, (2, 0, 0)), (96, (2, 0, -4)), (112, (3, 0, 0)), (120, (2, 0, 4)), (138, (3, 0, 0)),
             (146, (2, 0, -3)), (160, (2, 0, 0))], rot=True)
for S, sg in (('L', 1), ('R', -1)):   # arms swing against the stepping leg
    seq(f'FK-upper_arm.{S}', [(88, (0, 0, 0)), (104, (-14 * sg, 0, 0)), (130, (14 * sg, 0, 0)), (154, (-6 * sg, 0, 0)),
                              (164, (0, 0, 0))], rot=True)
seq('pole_knee.L', [(1, (0, 0, 0))], loc=True); seq('pole_knee.R', [(1, (0, 0, 0))], loc=True)

# ---------------------------------------------------------------- 5. right arm: raise, wrist roll, gripper open/close (164-212)
seq('FK-upper_arm.R', [(164, (0, 0, 0)), (176, (62, 0, -8)), (206, (62, 0, -8)), (218, (0, 0, 0))], rot=True)
seq('FK-forearm.R', [(164, (12, 0, 0)), (176, (38, 0, 0)), (206, (38, 0, 0)), (218, (12, 0, 0))], rot=True)
seq('FK-hand.R', [(164, (0, 0, 0)), (176, (-10, 0, 0)), (182, (-10, 60, 0)), (188, (-10, 60, 12)),
                  (196, (-10, 0, 0)), (218, (0, 0, 0))], rot=True)
seq('grip.R', [(164, (20, 0, 0)), (178, (-12, 0, 0)), (190, (-12, 0, 0)), (198, (62, 0, 0)), (206, (62, 0, 0)), (218, (20, 0, 0))], rot=True)
seq('f_thumb_0.R', [(164, (0, 0, 0)), (180, (0, 0, 0)), (188, (0, 55, 0)), (208, (0, 55, 0)), (218, (0, 0, 0))], rot=True)
# ---------------------------------------------------------------- 6. hatch opens, sensor nods, everything settles (200-240)
seq('hatch', [(1, (0, 0, 0)), (200, (0, 0, 0)), (214, (65, 0, 0)), (226, (65, 0, 0)), (238, (0, 0, 0))], rot=True)
seq('sensor', [(200, (0, 0, 0)), (210, (-10, 0, 0)), (222, (-10, 0, 0)), (232, (0, 0, 0))], rot=True)

# ---------------------------------------------------------------- per-frame checks
cam = sc.camera
stage.aim(cam, (-3.6, -4.6, 1.7), (0, -0.30, 1.05), 40)
sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
hits = {}; bad = {}; slide = 0.0; reach = 0.0; low = 9.0; swing = []
prev = {}
def foot_world(S):
    return arm.matrix_world @ pbs[f'DEF-foot.{S}'].head
for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    ns['spring_step'](sc)
    for h in ns['find_contacts'](arm, bpy.context): hits.setdefault(f'{h[0]} x {h[1]}', f)
    for S in 'LR':
        tgt = arm.matrix_world @ pbs[f'MCH-ankle.{S}'].head
        er = (foot_world(S) - tgt).length
        if er > 0.002: bad.setdefault(S, []).append((f, round(er * 1000)))
        reach = max(reach, er)
        # planted = IK target did not move since last frame
        fc = foot_world(S)
        if S in prev and (tgt - prev[S][0]).length < 1e-5:
            slide = max(slide, (fc - prev[S][1]).length)
        prev[S] = (tgt.copy(), fc.copy())
    dg = bpy.context.evaluated_depsgraph_get()
    for S in 'LR':
        o = bpy.data.objects[f'foot_block.{S}']; M = o.evaluated_get(dg).matrix_world
        low = min(low, min((M @ v.co).z for v in o.data.vertices))
    up = (pbs['body'].tail - pbs['body'].head).normalized()
    swing.append(round(math.degrees(((pbs['antenna_L_3'].tail - pbs['antenna_L_1'].head).normalized()).angle(up)), 1))
print('ANIM clashes', hits)
print('ANIM planted-foot slide max mm', round(slide * 1000, 2), 'IK reach error max mm', round(reach * 1000, 2),
      'lowest foot z mm', round(low * 1000, 2))
print('IK miss frames', {k: v[:3] + v[-2:] for k, v in bad.items()}, {k: len(v) for k, v in bad.items()})
print('antenna deflection every 12 frames', swing[::12])

# bake springs so the render matches the checked motion exactly
_ = bpy.ops.robot.bake_springs() if hasattr(bpy.ops.robot, 'bake_springs') else None
if mode == 'stills':
    for f in (1, 32, 48, 70, 104, 118, 132, 160, 184, 198, 216, 240):
        sc.frame_set(f); ns['spring_step'](sc)
        stage.render(f'{outdir}/a_{f:03d}.png', res=None, samples=24)
elif mode == 'full':
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f); ns['spring_step'](sc)
        stage.render(f'{outdir}/f_{f:03d}.png', res=None, samples=48)
sc.cycles.device = 'GPU'
bpy.ops.wm.save_as_mainfile(filepath=f'{outdir}/Robot_anim.blend')
