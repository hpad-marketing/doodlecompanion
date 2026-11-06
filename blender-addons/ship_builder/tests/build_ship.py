"""python build_ship.py -- [layout] [seed]: build a whole ship set, audit it closed and with every door open."""
import sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder import ship, collide
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
layout = a[0] if a else 'deck1'
t = time.time()
info = ship.build(layout, seed=int(a[1]) if len(a) > 1 else 1)
print('BUILT', layout, round(time.time() - t, 1), 's', [(r['key'], round(r['x'], 2), round(r['y'], 2)) for r in info['rooms']])
print('LINKS', info['links'])
print('CAMERAS', [c['name'] for c in info['cameras']])
objs = list(bpy.context.scene.objects)
hits = collide.audit_objects(objs)
print('AUDIT closed', len(hits))
for p, q in hits[:40]:
    print('   ', p, '<->', q)
for d in ship.door_controls().values():
    d['open'] = 1.0
bpy.context.view_layer.update()
hits = collide.audit_objects(objs)
print('AUDIT open', len(hits))
for p, q in hits[:40]:
    print('   ', p, '<->', q)
for d in ship.door_controls().values():
    d['open'] = 0.0
if len(a) > 2:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a[2]))
