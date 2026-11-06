import sys, os, time, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder.rooms import lounge
from ship_builder import lighting as Li
t = time.time()
room = lounge.build()
Li.space_world()
print('built in', round(time.time() - t, 1), 's; objects', len(bpy.data.objects))
out = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '/tmp/lounge'
os.makedirs(out, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'lounge.blend'))
