"""Sushi GPU stills: blender -b --factory-startup --python pc_stills.py -- <out_dir> <scans_dir> [res] [spp] [room] [seed]"""
import sys, os, time, json
args = sys.argv[sys.argv.index('--') + 1:]
out, scans = args[0], args[1]
res = int(args[2]) if len(args) > 2 else 1080
spp = int(args[3]) if len(args) > 3 else 256
key = args[4] if len(args) > 4 else 'lounge'
seed = int(args[5]) if len(args) > 5 else 1
os.environ['SB_SCANS'] = scans
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder.rooms import ROOMS
from mathutils import Vector
from ship_builder import lighting as Li, physics as P
os.makedirs(out, exist_ok=True)
rep = {}
t = time.time(); room = ROOMS[key].build(wear_seed=seed); rep['wear'] = getattr(room, 'wear', {}); rep['arch'] = getattr(room, 'arch', {}); Li.space_world(); rep['build_s'] = round(time.time() - t, 1)
sc = bpy.context.scene
Li.render_setup(sc)
Li.camera_finish(sc)
sc.cycles.samples = spp
rep['device'] = sc.cycles.device
rep['settled'] = P.settle(sc); rep['contacts'] = P.contacts(sc)
from ship_builder import collide
rep['intersections'] = collide.audit_room(room)
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 1.25)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f'Ship_{key}.blend'))
shots = [(c, 'NORMAL') for c in sc.objects if c.get('sb_cam')]
wide = [c for c in sc.objects if c.get('sb_cam') == 'Wide master'][0]
shots += [(wide, 'RED_ALERT'), (wide, 'NIGHT')]
# close-up of the missing wall panel, to check the wear pass
gone = [o for o in sc.objects if o.get('sb_wear') == 'missing' and ' Panel' in o.name]
if gone:
    p = gone[0]
    n = p.matrix_world.to_3x3() @ Vector((0, 0, 1))
    c = p.matrix_world.translation
    Li.camera(room, 'Wear detail', 35, tuple(c + n * 1.6 + Vector((0.3, 0, -0.1))), tuple(c), 4.0)
    shots.append(([o for o in sc.objects if o.get('sb_cam') == 'Wear detail'][0], 'NORMAL'))
rep['times'] = {}
for cam, mood in shots:
    Li.set_mood(mood, sc); sc.camera = cam
    sc.render.filepath = os.path.join(out, f"{cam['sb_cam'].replace(' ', '_')}_{mood}.png")
    t = time.time(); bpy.ops.render.render(write_still=True)
    rep['times'][os.path.basename(sc.render.filepath)] = round(time.time() - t, 1)
Li.set_mood('NORMAL', sc)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f'Ship_{key}.blend'))
json.dump(rep, open(os.path.join(out, 'report.json'), 'w'), indent=1)
print('REPORT', json.dumps(rep))
