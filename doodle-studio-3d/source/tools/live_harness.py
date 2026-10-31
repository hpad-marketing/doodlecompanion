"""Stand-in for an open Blender window in tests (see fakeblender_live.sh)."""
import json, os, runpy, sys, time
import bpy

blend, bridge = sys.argv[1], sys.argv[2]
rest = sys.argv[sys.argv.index('--') + 1:]
out_dir = rest[1]
sys.path.insert(0, os.path.dirname(bridge))
bpy.ops.wm.open_mainfile(filepath=blend)
sys.argv = ['blender', '--', *rest]
runpy.run_path(bridge, run_name='__main__')
import mirror
cmd = os.path.join(out_dir, 'cmd.json')
ns = {'bpy': bpy, 'mirror': mirror}
t_end = time.time() + float(os.environ.get('DS3D_LIVE_SECONDS', '120'))
while time.time() < t_end and mirror.S['alive']:
    if mirror.S.get('rebuild_ready'):
        mirror.S['rebuild_ready'] = False
        mirror._run_bridge()
    mirror.tick()
    if os.path.exists(cmd):
        try:
            c = json.load(open(cmd))
            os.remove(cmd)
            exec(c['code'], ns)
            res = ns.get('result')
            json.dump({'ok': True, 'result': res}, open(cmd + '.done', 'w'))
        except Exception as e:
            json.dump({'ok': False, 'error': repr(e)}, open(cmd + '.done', 'w'))
    time.sleep(0.05)
print('harness: done', flush=True)
