"""Fit the photo-overlay camera to a reference photo automatically, then store it in the droid's settings.
DROID=<id> python3 fit_camera.py in.blend photo.jpg [pose] [ground_y_fraction]
The droid's outline in the photo is found by removing the plain light wall behind it (rows below ground_y_fraction,
default 0.71, are ignored because the floor is hard to separate). A low-res silhouette is rendered and the camera
(azimuth, elevation, distance, lens, aim height, shift) is nudged until the overlap with the photo outline stops improving.
Writes settings reference.camera / reference.pose / reference.fit_iou. Run tools/overlay.py afterwards to see the result."""
import bpy, sys, os, json, math, tempfile
import numpy as np
from mathutils import Vector
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
blend, photo = a[0], a[1]; pose = a[2] if len(a) > 2 else 'Stand'; gy = float(a[3]) if len(a) > 3 else 0.71
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(blend))
W, H = 184, int(184 * Image.open(photo).height / Image.open(photo).width)
hsv = np.asarray(Image.open(photo).convert('HSV').resize((W, H))).astype(int)
ref = ~((hsv[..., 2] > 165) & (hsv[..., 1] < 40)); valid = np.zeros_like(ref); valid[:int(H * gy)] = True
sc = bpy.context.scene; cam = sc.camera; cam.animation_data_clear(); cam.delta_location = (0, 0, 0); cam.delta_rotation_euler = (0, 0, 0)
rig = bpy.data.objects[kit.rig_name()]
if rig.animation_data: rig.animation_data.action = None
for p in rig.pose.bones:
    if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0)
for b, (rot, l) in json.loads(rig.get('pose_presets', '{}')).get(pose, {}).items():
    if b in rig.pose.bones: rig.pose.bones[b].rotation_euler = [math.radians(v) for v in rot]; rig.pose.bones[b].location = l
for o in bpy.data.objects:
    if (o.type == 'MESH' and 'rig_bone' not in o and o.parent is None) or o.type == 'VOLUME': o.hide_render = True   # keep hose curves
sc.render.engine = 'CYCLES'; sc.cycles.samples = 1; sc.cycles.use_denoising = False; sc.cycles.max_bounces = 0
sc.render.film_transparent = True; sc.render.resolution_x, sc.render.resolution_y = W, H; sc.render.resolution_percentage = 100
sc.render.use_motion_blur = False; cam.data.dof.use_dof = False; cam.data.sensor_width = 36
tmp = os.path.join(tempfile.gettempdir(), 'droid_fit.png')
def setc(P):
    az, el, d, lens, tz, sx, sy = P; ar, er = math.radians(az), math.radians(el); t = Vector((0, 0.05, tz))
    cam.location = t + Vector((math.sin(ar) * math.cos(er), -math.cos(ar) * math.cos(er), math.sin(er))) * d
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = lens; cam.data.shift_x, cam.data.shift_y = sx, sy
    return t
def score(P):
    setc(P); sc.render.filepath = tmp; bpy.ops.render.render(write_still=True)
    m = np.asarray(Image.open(tmp))[..., 3] > 128
    return (m & ref & valid).sum() / max(((m | ref) & valid).sum(), 1)
best_all = None
for az0 in kit.get('reference', {}).get('fit_start_az', [315, 45, 0]):   # try a few starting sides, keep the best
    P = [az0, 8, 4.0, 30, 1.1, 0, 0]; steps = [12, 5, 0.6, 6, 0.15, 0.06, 0.06]; best = score(P)
    for rnd in range(12):
        for k in range(len(P)):
            for sgn in (1, -1):
                Q = list(P); Q[k] += sgn * steps[k]; s = score(Q)
                if s > best: best, P = s, Q; break
        steps = [s * 0.75 for s in steps]
    print('START', az0, 'IOU', round(best, 3), [round(v, 3) for v in P], flush=True)
    if not best_all or best > best_all[0]: best_all = (best, P)
best, P = best_all; t = setc(P)
S = kit.settings(); R = S.setdefault('reference', {})
R.update(pose=pose, fit_iou=round(float(best), 3), camera={'loc': [round(v, 3) for v in cam.location], 'target': [round(v, 3) for v in t], 'lens': round(P[3], 2), 'sensor': 36, 'shift': [round(P[5], 3), round(P[6], 3)]})
sp = os.environ.get('DROID_SETTINGS') or os.path.join(kit.ROOT, 'droids', os.environ['DROID'] + '.json')
json.dump(S, open(sp, 'w'), indent=1); print('FIT', R)
