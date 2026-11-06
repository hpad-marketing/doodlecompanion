"""Headless test of drive mode: scripted stick input through DriveCore, checks every tick."""
import bpy, sys, math, json
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=sys.argv[-2])
txt = bpy.data.texts['robot_rig_ui.py']; txt.clear(); txt.write(open(os.environ.get('DRIVE_UI') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rig_ui.py')).read())
ns = {'__name__': 'robot_rig_ui'}; exec(compile(txt.as_string(), 'robot_rig_ui.py', 'exec'), ns)
import stage
import physics
sc = bpy.context.scene; ob = bpy.data.objects['RobotRig']; pbs = ob.pose.bones
ad = ob.animation_data; ad.action = None; ad.use_nla = False; ob['springs_on'] = 1
for p in pbs:
    if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()
core = ns['DriveCore'](ob)
for k, v in os.environ.items():          # DRIVE_SWAY=0.3 etc. try gait values without editing the rig
    if k.startswith('DRIVE_') and hasattr(core, k[6:]): setattr(core, k[6:], float(v))
B = physics.Body(ob); coms, sups, toe_lift, reach_at, dbg = [], [], 0.0, {}, []
# script: (seconds, dict of input)
plan = [(1.0, {}), (3.0, dict(move=1)), (2.0, dict(move=1, turn=1)), (1.5, dict(turn=-1)), (2.0, dict(move=1, run=True)),
        (1.0, dict(move=-0.6)), (0.1, dict(fire={'wave'})), (3.0, dict(look_x=0.8, look_y=0.5)), (1.2, dict(crouch=True, grip_l=1, arm_r=True)),
        (0.1, dict(fire={'hatch'})), (2.0, {}), (0.1, dict(fire={'power'})), (2.5, {}), (0.1, dict(fire={'power'})), (2.5, dict(move=1)), (1.5, {})]
dt = 1 / 24; t = 0; hits = {}; slide = 0.0; reach = 0.0; low = 9.0; prev = {}; frames = 0; snaps = {}
snap_at = {30: 'walk', 110: 'turn', 175: 'run', 260: 'wave+look', 330: 'crouch+arm', 400: 'power off', 520: 'walk again'}
for dur, d in plan:
    n = max(1, round(dur / dt))
    for k in range(n):
        inp = ns['DriveInput']()
        for kk, v in d.items():
            if kk == 'fire':
                if k == 0: inp.fire = set(v)
            else: setattr(inp, kk, v)
        core.tick(inp, dt); frames += 1
        sc.frame_current = frames
        bpy.context.view_layer.update()
        ns['_STATE']['frame'] = frames - 1; ns['spring_step'](sc)
        for S in 'LR':
            tgt = ob.matrix_world @ pbs[f'MCH-ankle.{S}'].head
            fc = ob.matrix_world @ pbs[f'DEF-foot.{S}'].head
            reach = max(reach, (fc - tgt).length)
            if (fc - tgt).length > 0.005: reach_at.setdefault(S, []).append(frames)
            F = core.feet[S]
            if F['step'] is None and S in prev and prev[S][2] is None and F.get('ball', 0) < 0.5 and F.get('heel', 0) < 0.5 \
                    and prev[S][3] < 0.5:   # heel peel / heel strike move the ankle on purpose
                slide = max(slide, (fc - prev[S][1]).length)
            prev[S] = (tgt.copy(), fc.copy(), F['step'], F.get('ball', 0) + F.get('heel', 0))
        dg = bpy.context.evaluated_depsgraph_get()
        for S in 'LR':
            for nm in ('foot_block', 'toe_block'):
                o = bpy.data.objects[f'{nm}.{S}']; Mw = o.evaluated_get(dg).matrix_world
                low = min(low, min((Mw @ v.co).z for v in o.data.vertices))
        coms.append(B.com()); sups.append(B.support())
        dbg.append((frames, round(core.ph, 3), round(core.ch.get('env', 0), 2), round(core.ch.get('sway', 0), 3), round(coms[-1].x, 3),
                    ''.join(S if core.feet[S]['step'] else '.' for S in 'LR'), ''.join(sorted(sups[-1])),
                    [round(core.feet[S].get(k, 0)) for S in 'LR' for k in ('ball', 'heel')]))
        for S in 'LR':                      # while the heel peels, the toe must stay on the floor
            if core.feet[S]['step'] is None and core.feet[S].get('ball', 0) > 3:
                o = bpy.data.objects[f'toe_block.{S}']; Mw = o.evaluated_get(dg).matrix_world
                toe_lift = max(toe_lift, min((Mw @ v.co).z for v in o.data.vertices))
        if frames % 3 == 0:
            for h in ns['find_contacts'](ob, bpy.context): hits.setdefault(f'{h[0]} x {h[1]}', frames)
        if frames in snap_at:
            snaps[frames] = (snap_at[frames], core.pos.copy(), core.yaw)
            if 'render' in sys.argv:
                ob.hide_render = True; cam = sc.camera
                p = core.pos; fwd = Vector((-math.sin(core.yaw) * -1, -math.cos(core.yaw), 0))
                stage.aim(cam, (p.x - 3.2, p.y - 3.6, 1.8), (p.x, p.y, 1.0), 35)
                sc.render.resolution_x, sc.render.resolution_y = 400, 400
                stage.render(f'out/drive_{frames:04d}.png', res=None, samples=8)
print('DRIVE frames', frames, 'travel', [round(x, 2) for x in core.pos], 'yaw deg', round(math.degrees(core.yaw)),
      'clashes', hits, 'planted slide mm', round(slide * 1000, 2), 'IK reach mm', round(reach * 1000, 2), 'lowest mm', round(low * 1000, 2))
# physics: ZMP (CoM shifted against its acceleration) must stay inside what the planted feet stand on
out, worst, ds_n, ss_n = [], 0.0, 0, 0
for k in range(1, len(coms) - 1):
    if not sups[k]: continue
    acc = (coms[k + 1] - 2 * coms[k] + coms[k - 1]) / dt ** 2
    zx, zy = physics.zmp(coms[k], acc, B.Z0)
    h = physics.hull([q for v in sups[k].values() for q in v]); m = physics.margin(h, zx, zy)
    if len(sups[k]) == 1: ss_n += 1
    else: ds_n += 1
    if m < 0:
        out.append((k + 1, len(sups[k]), round(m * 1000))); worst = min(worst, m)
        if os.environ.get('DRIVE_DEBUG'):
            print('Z', k + 1, 'zmp', round(zx - coms[k].x, 3), round(zy - coms[k].y, 3), 'com', round(coms[k].x, 3), round(coms[k].y, 3),
                  'hull x', round(min(p[0] for p in h), 3) if h else '-', round(max(p[0] for p in h), 3) if h else '-',
                  'y', round(min(p[1] for p in h), 3) if h else '-', round(max(p[1] for p in h), 3) if h else '-', 'n', len(h))
print('PHYSICS ticks single', ss_n, 'double', ds_n, '| ZMP outside feet on', len(out), 'ticks, worst', round(worst * 1000), 'mm',
      '| toe lift during heel peel', round(toe_lift * 1000, 1), 'mm | mass', round(B.total), 'kg')
seg, f = [], 0
for dur, d in plan:
    n = max(1, round(dur / dt)); seg.append((f + 1, f + n, '+'.join(sorted(k if k != 'fire' else '/'.join(v) for k, v in d.items())) or 'stand')); f += n
for a, b, nm in seg:
    o = [m for fr, nn, m in out if a <= fr <= b]
    print(f'SEG {a:4d}-{b:4d} {nm:28s} ZMP out {len(o):3d} ticks, worst {min(o) if o else 0} mm')
print('ZMP_OUT', out[:40]); print('REACH_AT', {S: v[:30] for S, v in reach_at.items()})
if os.environ.get('DRIVE_DEBUG'):
    zm = {f: m for f, n, m in out}
    for d in dbg[int(os.environ.get('DRIVE_DEBUG').split(':')[0]):int(os.environ.get('DRIVE_DEBUG').split(':')[1])]: print('T', *d, zm.get(d[0], ''))
print('SNAPS', {k: (v[0], [round(x, 2) for x in v[1]], round(math.degrees(v[2]))) for k, v in snaps.items()})
