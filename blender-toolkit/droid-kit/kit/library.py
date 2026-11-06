"""Robot motion library + easy controls + look sliders.
python3 library.py [check|thumbs] in.blend out.blend
Every motion is servo-eased, keyed only on the motors it uses, clamped to the tuned joint limits, and checked
frame by frame: part clashes, IK feet reach, planted feet never slide, nothing under the floor.
"""
import bpy, sys, math, json
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Vector
mode = 'thumbs' if 'thumbs' in sys.argv else 'check'
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
import stage

# fresh UI script (easy controls, motion library, look)
txt = bpy.data.texts['robot_rig_ui.py']; txt.clear(); txt.write(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rig_ui.py')).read())
ns = {'__name__': 'robot_rig_ui'}; exec(compile(txt.as_string(), 'robot_rig_ui.py', 'exec'), ns)

sc = bpy.context.scene; sc.cycles.device = 'CPU'
arm = bpy.data.objects['RobotRig']; pbs = arm.pose.bones
LIM = json.load(open('out/tune_report.json'))['limits']
LIM['grip.L'] = LIM['grip.R'] = {'x': [-15, 60]}
r = math.radians
AX = 'xyz'

# limits show on the sliders: transform UI is clamped by the Limit Rotation constraints
n_lim = 0
for pb in pbs:
    for c in pb.constraints:
        if c.type in ('LIMIT_ROTATION', 'LIMIT_LOCATION'):
            c.use_transform_limit = True; n_lim += 1

# ---------------------------------------------------------------- look sliders (drivers into every material)
for k, v in (('look_wear', 0.75), ('look_rust', 0.6), ('look_grime', 0.75), ('look_scuffs', 0.5)):
    arm[k] = v
    arm.id_properties_ui(k).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
def drive(sock, prop, scale=1.0):
    sock.driver_remove('default_value')
    d = sock.driver_add('default_value').driver; d.type = 'SCRIPTED'
    v = d.variables.new(); v.name = 'v'; v.type = 'SINGLE_PROP'
    v.targets[0].id_type = 'OBJECT'; v.targets[0].id = arm; v.targets[0].data_path = f'["{prop}"]'
    d.expression = f'v * {scale}' if scale != 1 else 'v'
nd = 0
for m in bpy.data.materials:
    if not m.node_tree or 'Look' not in m.node_tree.nodes: continue
    gn = m.node_tree.nodes['Look']
    if gn.node_tree.name == 'RB Weathered Metal':
        base_rust = gn.inputs['Rust'].default_value / 0.6
        drive(gn.inputs['Wear'], 'look_wear'); drive(gn.inputs['Grime'], 'look_grime')
        drive(gn.inputs['Rust'], 'look_rust', round(base_rust, 3)); nd += 3
    elif m.name == 'RB_polymer':
        drive(gn.inputs['Scuffs'], 'look_scuffs'); drive(gn.inputs['Grime'], 'look_grime'); nd += 2

# ---------------------------------------------------------------- motion helpers
def clampv(b, rot):
    L = LIM.get(b, {})
    return [max(L[a][0], min(L[a][1], v)) if a in L else v for a, v in zip(AX, rot)]

def rest():
    for pb in pbs:
        pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0)
    for S in 'LR':
        pbs[f'IK_foot.{S}']['ik_fk'] = 1.0; pbs[f'IK_hand.{S}']['ik_fk'] = 0.0

def R(b, keys):
    for f, v in keys:
        pbs[b].rotation_euler = [r(a) for a in clampv(b, v)]; pbs[b].keyframe_insert('rotation_euler', frame=f)
def Lo(b, keys):
    for f, v in keys:
        pbs[b].location = v; pbs[b].keyframe_insert('location', frame=f)
def side(S, v):   # mirror y/z rotations onto the right side
    return v if S == 'L' else (v[0], -v[1], -v[2])
GRIP = 20   # relaxed hand

M = []   # (name, label, frames, loop, builder, thumb_frame, cam)
def motion(name, label, n, loop=False, thumb=None, cam='front'):
    def deco(fn): M.append((name, label, n, loop, fn, thumb or n // 2, cam)); return fn
    return deco

@motion('idle', 'Idle (breathing)', 72, loop=True, thumb=1)
def _():
    Lo('COG', [(1, (0, 0, -0.03)), (37, (0, 0, -0.042)), (73, (0, 0, -0.03))])
    R('hips', [(1, (2, 0, 0)), (37, (3, 0, 0)), (73, (2, 0, 0))])
    R('sensor', [(1, (0, 0, 0)), (20, (0, 0, 0)), (28, (3, 8, 0)), (48, (3, 8, 0)), (56, (0, 0, 0)), (73, (0, 0, 0))])
    for S in 'LR':
        R(f'grip.{S}', [(1, (GRIP, 0, 0)), (73, (GRIP, 0, 0))])
        R(f'FK-forearm.{S}', [(1, (12, 0, 0)), (37, (15, 0, 0)), (73, (12, 0, 0))])

@motion('look_around', 'Look around', 96, thumb=24)
def _():
    R('sensor', [(1, (0, 0, 0)), (20, (8, -60, 0)), (34, (8, -60, 0)), (58, (8, 60, 0)), (72, (8, 60, 0)), (90, (0, 0, 0)), (96, (0, 0, 0))])
    R('waist', [(1, (0, 0, 0)), (24, (0, -14, 0)), (34, (0, -14, 0)), (62, (0, 14, 0)), (72, (0, 14, 0)), (92, (0, 0, 0))])

@motion('walk_loop', 'Walk (in place, loops)', 48, loop=True, thumb=12, cam='side')
def _():
    A, lift = 0.15, 0.08
    # R swings f1-25 while L is planted and slides back; then swap
    Lo('IK_foot.L', [(1, (0, A, 0)), (25, (0, -A, 0.002)), (37, (0, 0, lift)), (49, (0, A, 0))])
    Lo('IK_foot.R', [(1, (0, -A, 0.002)), (13, (0, 0, lift)), (25, (0, A, 0)), (49, (0, -A, 0.002))])
    R('roll_ball.R', [(1, (12, 0, 0)), (5, (0, 0, 0)), (45, (0, 0, 0)), (49, (12, 0, 0))])
    R('roll_heel.R', [(1, (0, 0, 0)), (19, (0, 0, 0)), (25, (5, 0, 0)), (29, (0, 0, 0)), (49, (0, 0, 0))])
    R('roll_ball.L', [(1, (0, 0, 0)), (21, (0, 0, 0)), (25, (12, 0, 0)), (29, (0, 0, 0)), (49, (0, 0, 0))])
    R('roll_heel.L', [(1, (5, 0, 0)), (5, (0, 0, 0)), (43, (0, 0, 0)), (49, (5, 0, 0))])
    Lo('COG', [(1, (0, 0, -0.06)), (13, (0.05, 0, -0.035)), (25, (0, 0, -0.06)), (37, (-0.05, 0, -0.035)), (49, (0, 0, -0.06))])
    R('hips', [(1, (3, 0, 0)), (13, (3, 0, 4)), (25, (3, 0, 0)), (37, (3, 0, -4)), (49, (3, 0, 0))])
    for S, sg in (('L', 1), ('R', -1)):
        R(f'FK-upper_arm.{S}', [(1, (0, 0, 0)), (13, (12 * sg, 0, 0)), (25, (0, 0, 0)), (37, (-12 * sg, 0, 0)), (49, (0, 0, 0))])
        R(f'FK-forearm.{S}', [(1, (15, 0, 0)), (49, (15, 0, 0))])
        R(f'grip.{S}', [(1, (GRIP, 0, 0)), (49, (GRIP, 0, 0))])

@motion('wave', 'Wave hello (right arm)', 72, thumb=30)
def _():
    R('FK-upper_arm.R', [(1, (0, 0, 0)), (14, (62, 0, -12)), (58, (62, 0, -12)), (72, (0, 0, 0))])
    R('FK-forearm.R', [(1, (12, 0, 0)), (14, (55, 0, 0)), (58, (55, 0, 0)), (72, (12, 0, 0))])
    R('FK-hand.R', [(1, (0, 0, 0)), (14, (0, 0, 0))] + [(18 + 8 * i, (0, 0, 28 if i % 2 == 0 else -28)) for i in range(5)] +
      [(58, (0, 0, 0)), (72, (0, 0, 0))])
    R('grip.R', [(1, (GRIP, 0, 0)), (14, (-12, 0, 0)), (58, (-12, 0, 0)), (72, (GRIP, 0, 0))])
    R('sensor', [(1, (0, 0, 0)), (12, (0, 20, 0)), (60, (0, 20, 0)), (72, (0, 0, 0))])

@motion('grab_lift', 'Reach, grab and lift (right)', 80, thumb=36)
def _():
    R('FK-upper_arm.R', [(1, (0, 0, 0)), (16, (42, 0, -6)), (36, (42, 0, -6)), (52, (52, 0, -6)), (64, (52, 0, -6)), (80, (0, 0, 0))])
    R('FK-forearm.R', [(1, (12, 0, 0)), (16, (22, 0, 0)), (36, (22, 0, 0)), (52, (72, 0, 0)), (64, (72, 0, 0)), (80, (12, 0, 0))])
    R('FK-hand.R', [(1, (0, 0, 0)), (16, (-15, 0, 0)), (36, (-15, 0, 0)), (52, (10, 0, 0)), (64, (10, 0, 0)), (80, (0, 0, 0))])
    R('grip.R', [(1, (GRIP, 0, 0)), (14, (-12, 0, 0)), (28, (-12, 0, 0)), (36, (58, 0, 0)), (66, (58, 0, 0)), (80, (GRIP, 0, 0))])
    R('sensor', [(1, (0, 0, 0)), (12, (14, 10, 0)), (52, (14, 10, 0)), (64, (0, 0, 0))])
    R('hips', [(1, (0, 0, 0)), (16, (-6, 0, 0)), (40, (-6, 0, 0)), (56, (0, 0, 0))])
    Lo('COG', [(1, (0, 0, 0)), (16, (0, 0, -0.03)), (40, (0, 0, -0.03)), (56, (0, 0, 0))])

@motion('thumbs_up', 'Thumbs up (left)', 56, thumb=28)
def _():
    R('FK-upper_arm.L', [(1, (0, 0, 0)), (14, (35, 0, 10)), (42, (35, 0, 10)), (56, (0, 0, 0))])
    R('FK-forearm.L', [(1, (12, 0, 0)), (14, (80, 0, 0)), (42, (80, 0, 0)), (56, (12, 0, 0))])
    R('FK-hand.L', [(1, (0, 0, 0)), (14, (0, 60, 0)), (42, (0, 60, 0)), (56, (0, 0, 0))])
    R('grip.L', [(1, (GRIP, 0, 0)), (14, (58, 0, 0)), (42, (58, 0, 0)), (56, (GRIP, 0, 0))])
    R('f_thumb_0.L', [(1, (0, 0, 0)), (16, (0, 55, 0)), (42, (0, 55, 0)), (56, (0, 0, 0))])

@motion('celebrate', 'Celebrate (both arms up)', 64, thumb=22)
def _():
    for S in 'LR':
        R(f'FK-upper_arm.{S}', [(1, (0, 0, 0)), (14, side(S, (68, 0, 14))), (50, side(S, (68, 0, 14))), (64, (0, 0, 0))])
        R(f'FK-forearm.{S}', [(1, (12, 0, 0)), (14, (25, 0, 0)), (22, (55, 0, 0)), (30, (25, 0, 0)), (38, (55, 0, 0)),
                              (46, (25, 0, 0)), (64, (12, 0, 0))])
        R(f'grip.{S}', [(1, (GRIP, 0, 0)), (12, (-12, 0, 0)), (52, (-12, 0, 0)), (64, (GRIP, 0, 0))])
    Lo('COG', [(1, (0, 0, 0)), (10, (0, 0, -0.06)), (18, (0, 0, -0.01)), (50, (0, 0, -0.01)), (64, (0, 0, 0))])
    R('sensor', [(1, (0, 0, 0)), (14, (-12, 0, 0)), (50, (-12, 0, 0)), (64, (0, 0, 0))])

@motion('crouch', 'Crouch and stand', 64, thumb=28, cam='side')
def _():
    Lo('COG', [(1, (0, 0, 0)), (20, (0, 0, -0.2)), (40, (0, 0, -0.2)), (60, (0, 0, 0)), (64, (0, 0, 0))])
    R('hips', [(1, (0, 0, 0)), (20, (-8, 0, 0)), (40, (-8, 0, 0)), (60, (0, 0, 0))])
    for S in 'LR':
        R(f'FK-upper_arm.{S}', [(1, (0, 0, 0)), (20, (25, 0, 0)), (40, (25, 0, 0)), (60, (0, 0, 0))])
        R(f'FK-forearm.{S}', [(1, (12, 0, 0)), (20, (35, 0, 0)), (40, (35, 0, 0)), (60, (12, 0, 0))])
    R('sensor', [(1, (0, 0, 0)), (20, (-10, 0, 0)), (40, (-10, 0, 0)), (60, (0, 0, 0))])

@motion('power_down', 'Power down', 48, thumb=40, cam='side')
def _():
    Lo('COG', [(1, (0, 0, 0)), (30, (0, 0, -0.12)), (34, (0, 0, -0.115)), (48, (0, 0, -0.12))])
    R('hips', [(1, (0, 0, 0)), (30, (-12, 0, 0)), (48, (-12, 0, 0))])
    R('sensor', [(1, (0, 0, 0)), (12, (0, 0, 0)), (34, (20, 0, 0)), (48, (20, 0, 0))])
    for S in 'LR':
        R(f'FK-upper_arm.{S}', [(1, (0, 0, 0)), (30, (-6, 0, 0)), (48, (-6, 0, 0))])
        R(f'FK-forearm.{S}', [(1, (12, 0, 0)), (30, (4, 0, 0)), (48, (4, 0, 0))])
        R(f'grip.{S}', [(1, (GRIP, 0, 0)), (24, (0, 0, 0)), (48, (0, 0, 0))])

@motion('power_up', 'Power up', 48, thumb=30, cam='side')
def _():
    Lo('COG', [(1, (0, 0, -0.12)), (12, (0, 0, -0.12)), (34, (0, 0, -0.015)), (40, (0, 0, -0.03)), (48, (0, 0, -0.025))])
    R('hips', [(1, (-12, 0, 0)), (10, (-12, 0, 0)), (44, (0, 0, 0)), (48, (0, 0, 0))])
    R('sensor', [(1, (20, 0, 0)), (20, (20, 0, 0)), (32, (-4, 0, 0)), (38, (0, 0, 0)), (48, (0, 0, 0))])
    for S in 'LR':
        R(f'FK-upper_arm.{S}', [(1, (-6, 0, 0)), (14, (-6, 0, 0)), (32, (0, 0, 0))])
        R(f'FK-forearm.{S}', [(1, (4, 0, 0)), (14, (4, 0, 0)), (32, (12, 0, 0))])
        R(f'grip.{S}', [(1, (0, 0, 0)), (30, (0, 0, 0)), (36, (40, 0, 0)), (42, (GRIP, 0, 0))])

@motion('turn_waist', 'Turn at the waist', 60, thumb=16)
def _():
    R('waist', [(1, (0, 0, 0)), (16, (0, -35, 0)), (26, (0, -35, 0)), (42, (0, 35, 0)), (52, (0, 35, 0)), (60, (0, 0, 0))])
    R('sensor', [(1, (0, 0, 0)), (14, (0, -15, 0)), (26, (0, -15, 0)), (40, (0, 15, 0)), (52, (0, 15, 0)), (60, (0, 0, 0))])

@motion('hatch', 'Open and close the back hatch', 60, thumb=30, cam='back')
def _():
    R('hatch', [(1, (0, 0, 0)), (20, (75, 0, 0)), (40, (75, 0, 0)), (56, (0, 0, 0)), (60, (0, 0, 0))])
    R('sensor', [(1, (0, 0, 0)), (14, (0, 100, 0)), (44, (0, 100, 0)), (58, (0, 0, 0))])

@motion('step_forward', 'Three steps forward', 80, thumb=26, cam='side')
def _():
    def foot(S, t0, t1, d0, d1, lift=0.09):
        tm = (t0 + t1) // 2
        Lo(f'IK_foot.{S}', [(t0 - 6, (0, d0, 0))] + [(t0 - 6 + k, (0, d0, 0.0088 * (0.5 - 0.5 * math.cos(math.pi * k / 6)))) for k in range(1, 7)] + [ (tm, (0, (d0 + d1) / 2, lift)), (t1, (0, d1, 0)), (t1 + 4, (0, d1, 0))])
        R(f'roll_ball.{S}', [(t0 - 6, (0, 0, 0)), (t0, (22, 0, 0)), (t0 + 3, (0, 0, 0))])
        R(f'roll_heel.{S}', [(t1 - 3, (0, 0, 0)), (t1, (14, 0, 0)), (t1 + 4, (0, 0, 0))])
    for S in 'LR':
        Lo(f'IK_foot.{S}', [(1, (0, 0, 0))]); R(f'roll_ball.{S}', [(1, (0, 0, 0))]); R(f'roll_heel.{S}', [(1, (0, 0, 0))])
    foot('L', 12, 26, 0.0, 0.30); foot('R', 38, 52, 0.0, 0.60); foot('L', 64, 74, 0.30, 0.60, 0.05)
    Lo('COG', [(1, (0, 0, -0.03)), (10, (-0.07, 0, -0.04)), (26, (-0.02, -0.16, -0.06)), (34, (0.07, -0.30, -0.04)),
               (52, (0.02, -0.46, -0.06)), (60, (-0.06, -0.58, -0.04)), (74, (0, -0.60, -0.03))])
    R('hips', [(2, (2, 0, 0)), (10, (2, 0, -4)), (26, (3, 0, 0)), (34, (2, 0, 4)), (52, (3, 0, 0)), (60, (2, 0, -3)), (74, (2, 0, 0))])
    for S, sg in (('L', 1), ('R', -1)):
        R(f'FK-upper_arm.{S}', [(1, (0, 0, 0)), (18, (-14 * sg, 0, 0)), (44, (14 * sg, 0, 0)), (68, (-6 * sg, 0, 0)), (78, (0, 0, 0))])

PRESETS = {
    'Stand': {},
    'Ready': {'COG': ((0, 0, 0), (0, 0, -0.08)), 'hips': ((-6, 0, 0), (0, 0, 0)),
              'FK-upper_arm.L': ((30, 0, 6), (0, 0, 0)), 'FK-upper_arm.R': ((30, 0, -6), (0, 0, 0)),
              'FK-forearm.L': ((60, 0, 0), (0, 0, 0)), 'FK-forearm.R': ((60, 0, 0), (0, 0, 0)),
              'grip.L': ((58, 0, 0), (0, 0, 0)), 'grip.R': ((58, 0, 0), (0, 0, 0))},
    'Arms up': {'FK-upper_arm.L': ((68, 0, 14), (0, 0, 0)), 'FK-upper_arm.R': ((68, 0, -14), (0, 0, 0)),
                'FK-forearm.L': ((25, 0, 0), (0, 0, 0)), 'FK-forearm.R': ((25, 0, 0), (0, 0, 0)),
                'grip.L': ((-12, 0, 0), (0, 0, 0)), 'grip.R': ((-12, 0, 0), (0, 0, 0)), 'sensor': ((-12, 0, 0), (0, 0, 0))},
    'Reach': {'FK-upper_arm.R': ((42, 0, -6), (0, 0, 0)), 'FK-forearm.R': ((22, 0, 0), (0, 0, 0)),
              'FK-hand.R': ((-15, 0, 0), (0, 0, 0)), 'grip.R': ((-12, 0, 0), (0, 0, 0)), 'hips': ((-6, 0, 0), (0, 0, 0)),
              'sensor': ((14, 10, 0), (0, 0, 0))},
    'Crouch': {'COG': ((0, 0, 0), (0, 0, -0.2)), 'hips': ((-8, 0, 0), (0, 0, 0)),
               'FK-upper_arm.L': ((25, 0, 0), (0, 0, 0)), 'FK-upper_arm.R': ((25, 0, 0), (0, 0, 0)),
               'FK-forearm.L': ((35, 0, 0), (0, 0, 0)), 'FK-forearm.R': ((35, 0, 0), (0, 0, 0))},
    'Powered off': {'COG': ((0, 0, 0), (0, 0, -0.12)), 'hips': ((-12, 0, 0), (0, 0, 0)), 'sensor': ((20, 0, 0), (0, 0, 0)),
                    'FK-upper_arm.L': ((-6, 0, 0), (0, 0, 0)), 'FK-upper_arm.R': ((-6, 0, 0), (0, 0, 0)),
                    'FK-forearm.L': ((4, 0, 0), (0, 0, 0)), 'FK-forearm.R': ((4, 0, 0), (0, 0, 0))},
}
for P in PRESETS.values():
    for b, (rot, loc) in P.items(): P[b] = (clampv(b, rot), loc)
arm['pose_presets'] = json.dumps(PRESETS)
arm['springs_on'] = 1   # live antenna/cable springs on: every motion is checked with them swinging
_S = json.loads(arm['springs'])
for ch in _S:
    if ch['bones'][0].startswith('cable'): ch['k'], ch['damp'] = 0.15, 0.25   # follows the body; no whip into the box
arm['springs'] = json.dumps(_S)

# ---------------------------------------------------------------- build + check
ad = arm.animation_data or arm.animation_data_create()
demo = ad.action
for t in list(ad.nla_tracks): ad.nla_tracks.remove(t)
for a in [a for a in bpy.data.actions if a.get('robot_motion')]:
    if a != demo: bpy.data.actions.remove(a)

def check(n, label):
    hits = {}; slide = reach = 0.0; low = 9.0; prev = {}
    ns['_STATE'].clear()
    for f in range(1, n + 1):
        sc.frame_set(f); ns['spring_step'](sc)
        for h in ns['find_contacts'](arm, bpy.context): hits.setdefault(f'{h[0]} x {h[1]}', f)
        for S in 'LR':
            tgt = arm.matrix_world @ pbs[f'MCH-ankle.{S}'].head
            fc = arm.matrix_world @ pbs[f'DEF-foot.{S}'].head
            reach = max(reach, (fc - tgt).length)
            if S in prev and (tgt - prev[S][0]).length < 1e-5: slide = max(slide, (fc - prev[S][1]).length)
            prev[S] = (tgt.copy(), fc.copy())
        dg = bpy.context.evaluated_depsgraph_get()
        for S in 'LR':
            for nm in ('foot_block', 'toe_block'):
                o = bpy.data.objects[f'{nm}.{S}']; Mw = o.evaluated_get(dg).matrix_world
                low = min(low, min((Mw @ v.co).z for v in o.data.vertices))
    return dict(clashes=hits, slide_mm=round(slide * 1000, 2), reach_mm=round(reach * 1000, 2), lowest_mm=round(low * 1000, 2))

report = {}
acts = []
for i, (name, label, n, loop, fn, thumb, cam) in enumerate(M):
    rest()
    act = bpy.data.actions.new(f'RM_{name}')
    ad.action = act
    for S in 'LR':   # pin IK/FK state so every motion plays the same however the rig was left
        pbs[f'IK_foot.{S}'].keyframe_insert('["ik_fk"]', frame=1); pbs[f'IK_hand.{S}'].keyframe_insert('["ik_fk"]', frame=1)
    fn()
    for fc in (act.fcurves if hasattr(act, 'fcurves') else []):
        pass
    if name == 'walk_loop':   # planted feet slide back at constant speed
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    for fc in cb.fcurves:
                        if 'IK_foot' in fc.data_path and fc.array_index == 1:
                            for k in fc.keyframe_points: k.interpolation = 'LINEAR'
    act['robot_motion'] = 1; act['label'] = label; act['loop'] = int(loop); act['order'] = i
    act.frame_range = (1, n) if not loop else (1, n + 1)
    act.use_frame_range = True; act.use_cyclic = loop
    act.use_fake_user = True
    report[name] = check(n, label)
    print('MOTION', name, n, report[name], flush=True)
    acts.append((act, thumb, cam))

# the 10 s demo joins the library
demo.name = 'RM_demo_10s'; demo['robot_motion'] = 1; demo['label'] = 'Demo reel (10 s)'; demo['order'] = 99; demo['loop'] = 0
demo.use_fake_user = True
acts.append((demo, 184, 'front'))
for p in PRESETS:
    rest(); ad.action = None
    bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.object and bpy.context.object.mode != 'OBJECT' else None
    for b, (rot, loc) in PRESETS[p].items(): pbs[b].rotation_euler = [r(v) for v in rot]; pbs[b].location = loc
    bpy.context.view_layer.update()
    report['pose:' + p] = {'clashes': ns['find_contacts'](arm, bpy.context)}
    print('POSE', p, report['pose:' + p], flush=True)

# ---------------------------------------------------------------- thumbnails -> previews (panel grid + Asset Browser)
cat_id = None
try:
    import uuid
    cats = '/tmp/blender_assets.cats.txt'
except Exception: pass
if mode == 'thumbs':
    import os
    os.makedirs('out/thumbs', exist_ok=True)
    arm.hide_render = True; cam = sc.camera
    sc.render.resolution_x = sc.render.resolution_y = 256
    CAMS = {'front': ((-2.9, -4.3, 1.7), (0, -0.25, 1.05)), 'side': ((-5.0, -1.6, 1.5), (0, -0.3, 1.0)),
            'back': ((-2.6, 4.2, 2.3), (0, 0, 1.25))}
    for act, f, cv in acts:
        rest(); ad.action = act
        if hasattr(ad, 'action_slot') and act.slots: ad.action_slot = act.slots[0]
        ns['_STATE'].clear()
        for k in range(max(1, f - 12), f + 1): sc.frame_set(k); ns['spring_step'](sc)
        loc, tgt = CAMS[cv]
        if act.name == 'RM_step_forward': tgt = (tgt[0], tgt[1] - 0.3, tgt[2]); loc = (loc[0], loc[1] - 0.3, loc[2])
        stage.aim(cam, loc, (tgt[0], tgt[1], tgt[2] + 0.1), 52)
        path = f'out/thumbs/{act.name}.png'
        stage.render(path, res=None, samples=10)
        img = bpy.data.images.load(os.path.abspath(path))
        px = list(img.pixels); W, H = img.size
        act.asset_mark()
        act.asset_data.description = act.get('label', act.name)
        act.asset_data.tags.new('robot')
        pv = act.preview_ensure(); pv.image_size = (W, H); pv.image_pixels_float = px
        bpy.data.images.remove(img)
    rest(); ad.action = demo
    if hasattr(ad, 'action_slot') and demo.slots: ad.action_slot = demo.slots[0]
    sc.frame_start, sc.frame_end = 1, 240

json.dump(report, open('out/library_report.json', 'w'), indent=1)
print('LIBRARY', len(acts), 'motions', len(PRESETS), 'poses', 'limit constraints clamped', n_lim, 'look drivers', nd)
sc.frame_set(1)
sc.cycles.device = 'GPU'
bpy.ops.wm.save_as_mainfile(filepath=out)
