"""Headless test of drive mode: scripted stick input through DriveCore, checks every tick."""
import bpy, sys, math, json
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=sys.argv[-2])
txt = bpy.data.texts['robot_rig_ui.py']; txt.clear(); txt.write(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rig_ui.py')).read())
ns = {'__name__': 'robot_rig_ui'}; exec(compile(txt.as_string(), 'robot_rig_ui.py', 'exec'), ns)
import stage
sc = bpy.context.scene; ob = bpy.data.objects['RobotRig']; pbs = ob.pose.bones
ad = ob.animation_data; ad.action = None; ad.use_nla = False; ob['springs_on'] = 1
for p in pbs:
    if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()
core = ns['DriveCore'](ob)
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
            F = core.feet[S]
            if F['step'] is None and S in prev and prev[S][2] is None:
                slide = max(slide, (fc - prev[S][1]).length)
            prev[S] = (tgt.copy(), fc.copy(), F['step'])
        dg = bpy.context.evaluated_depsgraph_get()
        for S in 'LR':
            for nm in ('foot_block', 'toe_block'):
                o = bpy.data.objects[f'{nm}.{S}']; Mw = o.evaluated_get(dg).matrix_world
                low = min(low, min((Mw @ v.co).z for v in o.data.vertices))
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
print('SNAPS', {k: (v[0], [round(x, 2) for x in v[1]], round(math.degrees(v[2]))) for k, v in snaps.items()})
