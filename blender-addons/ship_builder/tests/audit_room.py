"""blender -b --python audit_room.py -- <room key> [seed]: build, then list every intersecting pair."""
import sys, os, time, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder.rooms import ROOMS
from ship_builder import collide, physics as P
a = sys.argv[sys.argv.index('--') + 1:]
room = ROOMS[a[0]].build(wear_seed=int(a[1]) if len(a) > 1 else 1)
P.settle(bpy.context.scene)
t = time.time()
hits = collide.audit_room(room)
print('AUDIT', a[0], len(hits), 'hits in', round(time.time() - t, 1), 's')
from collections import Counter
for (x, y), n in Counter(tuple(sorted((collide._base(p), collide._base(q)))) for p, q in hits).most_common():
    print('  ', n, x, '<->', y)
# doors fully open: the leaves sit in their pockets and must still touch nothing
doors = [o for o in bpy.data.objects if o.get('sb_door') and o.type == 'EMPTY']
for d in doors:
    d['open'] = 1.0
bpy.context.view_layer.update()
hits = collide.audit_room(room)
print('AUDIT', a[0], 'doors open:', len(doors), 'doors,', len(hits), 'hits')
for p, q in hits:
    print('   open:', p, '<->', q)
