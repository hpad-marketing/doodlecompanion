"""Sushi GPU stills: blender -b --factory-startup --python pc_stills.py -- <out_dir> <scans_dir> [res] [spp]"""
import sys, os, time, json
args = sys.argv[sys.argv.index('--') + 1:]
out, scans = args[0], args[1]
res = int(args[2]) if len(args) > 2 else 1080
spp = int(args[3]) if len(args) > 3 else 256
os.environ['SB_SCANS'] = scans
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder.rooms import lounge
from ship_builder import lighting as Li, physics as P
os.makedirs(out, exist_ok=True)
rep = {}
t = time.time(); room = lounge.build(); Li.space_world(); rep['build_s'] = round(time.time() - t, 1)
sc = bpy.context.scene
Li.render_setup(sc)
sc.cycles.samples = spp
rep['device'] = sc.cycles.device
rep['settled'] = P.settle(sc); rep['contacts'] = P.contacts(sc)
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 1.25)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'Ship_lounge.blend'))
shots = [(c, 'NORMAL') for c in sc.objects if c.get('sb_cam')]
wide = [c for c in sc.objects if c.get('sb_cam') == 'Wide master'][0]
shots += [(wide, 'RED_ALERT'), (wide, 'NIGHT')]
rep['times'] = {}
for cam, mood in shots:
    Li.set_mood(mood, sc); sc.camera = cam
    sc.render.filepath = os.path.join(out, f"{cam['sb_cam'].replace(' ', '_')}_{mood}.png")
    t = time.time(); bpy.ops.render.render(write_still=True)
    rep['times'][os.path.basename(sc.render.filepath)] = round(time.time() - t, 1)
Li.set_mood('NORMAL', sc)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'Ship_lounge.blend'))
json.dump(rep, open(os.path.join(out, 'report.json'), 'w'), indent=1)
print('REPORT', json.dumps(rep))
