"""blender -b --python build_room.py -- <room key> <out dir> [seed] [amount]"""
import sys, os, time, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder.rooms import ROOMS
from ship_builder import lighting as Li
a = sys.argv[sys.argv.index('--') + 1:]
key, out = a[0], a[1]
seed = int(a[2]) if len(a) > 2 else 1
amount = float(a[3]) if len(a) > 3 else 1.0
t = time.time()
room = ROOMS[key].build(wear=amount, wear_seed=seed)
Li.space_world()
print('built', key, 'in', round(time.time() - t, 1), 's; objects', len(bpy.data.objects))
print('WEAR', json.dumps(getattr(room, 'wear', {})))
os.makedirs(out, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, key + '.blend'))
