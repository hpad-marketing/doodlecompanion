"""quick look renders: python3 preview.py in.blend outprefix [pose-json]"""
import bpy, sys, math, json
sys.path.insert(0, __file__.rsplit('/', 1)[0])
blend, pre = sys.argv[1], sys.argv[2]
pose = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
bpy.ops.wm.open_mainfile(filepath=blend)
import stage
stage.setup_studio(engine_gpu=False)
sc = bpy.context.scene; sc.view_settings.view_transform = 'Khronos PBR Neutral'
arm = bpy.data.objects['TrackerRig']; arm.hide_render = True
for k, v in pose.items():
    if k.startswith('@'): arm[k[1:]] = v; continue
    bn, ch, i = k.split(':'); pb = arm.pose.bones[bn]
    getattr(pb, ch)[int(i)] = v
import os
if os.environ.get('ACTION'):
    arm.animation_data.action = bpy.data.actions[os.environ['ACTION']]
    arm.animation_data.action_slot = arm.animation_data.action.slots[0]
    sc.frame_set(int(os.environ.get('FRAME', 1)))
cam = sc.camera
views = {'front34': ((-1.55, -2.0, 1.05), (0, -0.05, 0.45)), 'side': ((-2.5, 0.0, 0.6), (0, 0, 0.45)),
         'back34': ((1.6, 1.9, 1.1), (0, 0.05, 0.45)), 'front': ((0, -2.6, 0.62), (0, 0, 0.45)), 'face': ((0.25, -1.5, 0.75), (0, -0.18, 0.69))}
only = sys.argv[4].split(',') if len(sys.argv) > 4 else list(views)
for n in only:
    loc, tg = views[n]; stage.aim(cam, loc, tg, 50)
    stage.render(f'{pre}_{n}.png', res=int(__import__('os').environ.get('RES', 700)), samples=int(__import__('os').environ.get('SAMP', 24)))
