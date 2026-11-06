"""Floor clamp: no droid part may sink into the floor in any library motion.
For every frame where a foot side dips below the floor (beyond touch tolerance), that foot's IK control is lifted
by exactly the dip, keyed frame by frame over the dip plus a few frames either side so the motion stays smooth.
DROID=<id> python3 floor_clamp.py in.blend out.blend [action_regex]
Settings: feet = {"L": {"ik": "IK_foot.L", "parts": "regex of part names"}, "R": {...}}, floor_z (default 0), collision.touch_mm."""
import bpy, sys, os, re, json
from mathutils import Vector
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
src, out = a[0], a[1]; arx = re.compile(a[2] if len(a) > 2 else '^RM_')
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(src))
sc = bpy.context.scene; rig = bpy.data.objects[kit.rig_name()]; ad = rig.animation_data
FEET = kit.get('feet', {s: {'ik': f'IK_foot.{s}', 'parts': rf'(foot|toe|heel|sole|ankle)[^.]*\.{s}$'} for s in 'LR'})
Z0 = kit.get('floor_z', 0.0); TOL = (kit.get('collision', {}) or {}).get('touch_mm', 0.5) / 1000; PAD = 3
parts = {s: [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o and re.search(f['parts'], o.name)] for s, f in FEET.items()}
def lowest(s):
    dg = bpy.context.evaluated_depsgraph_get(); m = 1e9
    for o in parts[s]:
        e = o.evaluated_get(dg); me = e.to_mesh(); M = e.matrix_world
        if me.vertices: m = min(m, min((M @ v.co).z for v in me.vertices))
        e.to_mesh_clear()
    return m
total = {}
keep = (ad.action, ad.action_slot)   # put the rig's own action back at the end, or an unassigned motion could be lost on save
for act in [x for x in bpy.data.actions if arx.search(x.name)]:
    ad.action = act
    if act.slots: ad.action_slot = act.slots[0]
    f0, f1 = map(int, act.frame_range)
    for s, f in FEET.items():
        pb = rig.pose.bones[f['ik']]
        for it in range(3):   # repeat: lifting one frame can change its neighbours slightly
            dips = {}
            for fr in range(f0, f1 + 1):
                sc.frame_set(fr); d = Z0 - lowest(s)
                if d > TOL: dips[fr] = d + 0.0003
            if not dips: break
            win = sorted({g for fr in dips for g in range(max(f0, fr - PAD), min(f1, fr + PAD) + 1)})
            base = {}
            for fr in win: sc.frame_set(fr); base[fr] = pb.matrix.copy()   # where the foot is now, frame by frame
            for fr in win:
                lift = max([dips[g] * max(0.0, 1 - abs(g - fr) / (PAD + 1)) for g in dips if abs(g - fr) <= PAD] + [0])
                lift = max(lift, dips.get(fr, 0))
                sc.frame_set(fr); M = base[fr].copy(); M.translation += rig.matrix_world.inverted().to_3x3() @ Vector((0, 0, lift))
                pb.matrix = M; bpy.context.view_layer.update()
                pb.keyframe_insert('location', frame=fr); pb.keyframe_insert('rotation_euler' if pb.rotation_mode != 'QUATERNION' else 'rotation_quaternion', frame=fr)
            total[(act.name, s)] = total.get((act.name, s), 0) + len(dips)
            print('CLAMP', act.name, s, 'pass', it, 'frames', len(dips), 'max dip mm', round(max(dips.values()) * 1000, 2), flush=True)
ad.action = keep[0]
if keep[1]: ad.action_slot = keep[1]
for x in bpy.data.actions:
    if arx.search(x.name): x.use_fake_user = True
print('FLOOR_CLAMP', {f'{k[0]} {k[1]}': v for k, v in total.items()} or 'nothing sank')
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True, relative_remap=False)
