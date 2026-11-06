import sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
args = sys.argv[sys.argv.index('--') + 1:]
blend, out, res, spp = args[0], args[1], int(args[2]), int(args[3])
cams = args[4].split(',') if len(args) > 4 else None
mood = args[5] if len(args) > 5 else 'NORMAL'
bpy.ops.wm.open_mainfile(filepath=blend)
from ship_builder import lighting as Li, physics as P
sc = bpy.context.scene
Li.render_setup(sc, preview=True)
sc.cycles.samples = spp
n = P.settle(sc)
print('settled', n, 'props; contacts', P.contacts(sc))
Li.set_mood(mood, sc)
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 1.25)
os.makedirs(out, exist_ok=True)
for c in [o for o in sc.objects if o.get('sb_cam')]:
    if cams and not any(k in c.name for k in cams):
        continue
    sc.camera = c
    sc.render.filepath = os.path.join(out, c['sb_cam'].replace(' ', '_') + '_' + mood + '.png')
    t = time.time(); bpy.ops.render.render(write_still=True); print(c.name, round(time.time() - t, 1), 's')
