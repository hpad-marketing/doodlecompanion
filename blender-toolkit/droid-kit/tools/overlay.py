"""Photo-overlay check: render the model from a camera matched to the reference photo, then lay it over the photo
at 50% opacity (plus an outline) so proportions can be compared part by part.
DROID=<id> python3 overlay.py in.blend photo.jpg out.png
Camera comes from settings reference.camera {loc, target, lens, sensor} and frame; fit it once, then reuse."""
import bpy, sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit
from mathutils import Vector
blend, photo, out = sys.argv[-3:]
bpy.ops.wm.open_mainfile(filepath=blend)
from PIL import Image, ImageFilter, ImageChops
ref = Image.open(photo).convert('RGB'); W, H = ref.size
sc = bpy.context.scene; cam = sc.camera; cam.animation_data_clear(); cam.delta_location = (0, 0, 0); cam.delta_rotation_euler = (0, 0, 0)
R = kit.get('reference', {}); C = R.get('camera', {})
rig = bpy.data.objects[kit.rig_name()]
if rig.animation_data: rig.animation_data.action = None
P = json.loads(rig.get('pose_presets', '{}')).get(R.get('pose', ''), {})
import math
for p in rig.pose.bones:
    if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0)
for b, (rot, loc) in P.items():
    if b in rig.pose.bones: rig.pose.bones[b].rotation_euler = [math.radians(v) for v in rot]; rig.pose.bones[b].location = loc
loc, tgt = Vector(C.get('loc', (-2.2, -2.6, 0.9))), Vector(C.get('target', (0, -0.5, 0.9)))
cam.location = loc; cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = C.get('lens', 35); cam.data.sensor_width = C.get('sensor', 36); cam.data.dof.use_dof = False
cam.data.shift_x, cam.data.shift_y = C.get('shift', (0, 0))
sc.render.resolution_x, sc.render.resolution_y = W, H; sc.render.film_transparent = True; sc.cycles.samples = 12
sc.render.use_motion_blur = False
for o in bpy.data.objects:   # model only
    if (o.type == 'MESH' and 'rig_bone' not in o and o.parent is None) or o.type == 'VOLUME': o.hide_render = True   # keep hose curves
tmp = out + '.model.png'; sc.render.filepath = tmp; bpy.ops.render.render(write_still=True)
mdl = Image.open(tmp).convert('RGBA'); a = mdl.split()[3]
blend_ = Image.composite(Image.blend(ref, mdl.convert('RGB'), 0.5), ref, a)
edge = a.point(lambda v: 255 if v > 128 else 0).filter(ImageFilter.FIND_EDGES)
blend_.paste((255, 60, 40), mask=edge)
blend_.save(out); print('OVERLAY ->', out)
