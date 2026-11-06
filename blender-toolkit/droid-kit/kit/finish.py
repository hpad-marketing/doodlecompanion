"""Widgets, colours, panel, studio. python3 finish.py in.blend out.blend"""
import bpy, math, json, sys, bmesh
import os
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
IN, OUT = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=IN)
arm = bpy.data.objects['RobotRig']; pbs = arm.pose.bones
C_W = bpy.data.collections['Robot_Widgets']

def wgt(name, verts, edges):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, edges, []); me.update()
    o = bpy.data.objects.new(name, me); C_W.objects.link(o); return o
def circle(plane, n=32):
    vs = []
    for i in range(n):
        a = 2 * math.pi * i / n; c, s = math.cos(a), math.sin(a)
        vs.append((c, 0, s) if plane == 'xz' else (c, s, 0) if plane == 'xy' else (0, c, s))
    return vs, [(i, (i + 1) % n) for i in range(n)]
W = {}
W['circle'] = wgt('WGT_circle', *circle('xz'))
W['flat'] = wgt('WGT_circle_flat', *circle('xy'))
v1, e1 = circle('xz', 16); v2, e2 = circle('xy', 16); v3, e3 = circle('yz', 16)
W['sphere'] = wgt('WGT_sphere', v1 + v2 + v3, e1 + [(a + 16, b + 16) for a, b in e2] + [(a + 32, b + 32) for a, b in e3])
cv = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
ce = [(i, j) for i in range(8) for j in range(i + 1, 8) if sum(a != b for a, b in zip(cv[i], cv[j])) == 1]
W['cube'] = wgt('WGT_cube', cv, ce)
W['square'] = wgt('WGT_square', [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)], [(0, 1), (1, 2), (2, 3), (3, 0)])
rv, re_ = circle('xy', 48)
rv += [(0, -1.0, 0), (-0.18, -1.25, 0), (0, -1.45, 0), (0.18, -1.25, 0)]; re_ += [(48, 49), (49, 50), (50, 51), (51, 48)]
W['root'] = wgt('WGT_root', rv, re_)
C_W.hide_render = True; C_W.hide_viewport = True
for o in C_W.objects: o.hide_render = True

def shape(b, w, r, t=0.5, sc=None):
    pb = pbs[b]; L = arm.data.bones[b].length
    pb.custom_shape = W[w]; pb.use_custom_shape_bone_size = False
    pb.custom_shape_scale_xyz = sc or (r, r, r); pb.custom_shape_translation = (0, L * t, 0)
    pb.custom_shape_wire_width = 2.0

shape('root', 'root', 0.9, 0); shape('COG', 'flat', 0.45, 0, (0.45, 0.45, 0.45))
shape('hips', 'circle', 0.36, 0.3); shape('waist', 'circle', 0.28, 0.4); shape('body', 'circle', 0.66, 0.5)
shape('hatch', 'square', 0.12, 0.5); shape('sensor', 'square', 0.1, 0.6)
shape('skirt_front', 'square', 0.1, 0.5); shape('skirt_back', 'square', 0.1, 0.5)
for S in ('L', 'R'):
    shape(f'shoulder.{S}', 'sphere', 0.07, 1.0)
    for b, r in (('FK-upper_arm', 0.18), ('FK-forearm', 0.15), ('FK-hand', 0.13), ('FK-thigh', 0.2), ('FK-shin', 0.17), ('FK-foot', 0.15), ('FK-toe', 0.12)):
        shape(f'{b}.{S}', 'circle', r)
    shape(f'IK_hand.{S}', 'cube', 0.11); shape(f'IK_foot.{S}', 'cube', 0, 0.45, (0.2, 0.28, 0.03))
    for r in ('roll_heel', 'roll_toe', 'roll_ball'): shape(f'{r}.{S}', 'sphere', 0.035, 0)
    shape(f'IK-toe.{S}', 'circle', 0.12)
    shape(f'pole_knee.{S}', 'sphere', 0.06, 0); shape(f'pole_elbow.{S}', 'sphere', 0.06, 0)
    for p in ('plate_pauldron', 'plate_elbow', 'plate_forearm', 'plate_shield', 'plate_thigh', 'plate_knee', 'skirt_side'):
        shape(f'{p}.{S}', 'square', 0.07, 0.6)
    for fn in ('index', 'middle', 'ring', 'thumb'):
        for i in (1, 2, 3): shape(f'f_{fn}_{i}.{S}', 'circle', 0.03)
    shape(f'f_thumb_0.{S}', 'circle', 0.04, 0.5); shape(f'grip.{S}', 'square', 0.05, 0.5)

spec = json.loads(arm['rig_spec'])
for pb in pbs:
    n = pb.name
    pal = 'THEME09' if not n.endswith(('.L', '.R')) else ('THEME04' if n.endswith('.L') else 'THEME01')
    if n.startswith(('plate', 'skirt', 'hatch', 'sensor')): pal = 'THEME07'
    if n.startswith('f_'): pal = 'THEME03' if n.endswith('.L') else 'THEME06'
    pb.color.palette = pal
    arm.data.bones[n].hide = False
for c in arm.data.collections:
    c.is_visible = c.name not in ('Mechanics', 'Deform', 'Arm IK', 'Leg FK')
arm.data.display_type = 'WIRE'; arm.show_in_front = True

# rest contacts list for the Check button (same rule as the tuning)
from mathutils.bvhtree import BVHTree
for pb in pbs: pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0)
bpy.context.view_layer.update()
parts = [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o]
data = []
for o in parts:
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    data.append((o, vs, [min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]))
rest = []
for i, (a, va, amn, amx) in enumerate(data):
    for b, vb, bmn, bmx in data[i + 1:]:
        if a['rig_bone'] == b['rig_bone'] or any(amx[k] < bmn[k] or bmx[k] < amn[k] for k in range(3)): continue
        if BVHTree.FromPolygons(va, [tuple(p.vertices) for p in a.data.polygons]).overlap(
           BVHTree.FromPolygons(vb, [tuple(p.vertices) for p in b.data.polygons])): rest.append((a.name, b.name))
arm['rest_contacts'] = json.dumps(rest)
print('rest contacts', len(rest))

txt = bpy.data.texts.new('robot_rig_ui.py'); txt.write(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rig_ui.py')).read()); txt.use_module = True
exec(compile(txt.as_string(), 'robot_rig_ui.py', 'exec'), {'__name__': 'robot_rig_ui'})

import stage
stage.setup_studio(engine_gpu=True)
sc = bpy.context.scene
stage.aim(sc.camera, (3.6, -3.4, 1.5), (0, 0, 1.05), 40)
sc.cycles.samples = 128
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
try:
    sc.cycles.denoiser = 'OPTIX'
except Exception: pass
sc.frame_start, sc.frame_end = 1, 120
for o in bpy.context.view_layer.objects: o.select_set(False)
arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT)
