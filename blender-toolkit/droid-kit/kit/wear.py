"""Per-part functional wear values (read by the metal shader as object attributes rb_oil/rb_mud/rb_heat/rb_touch).
python3 wear.py in.blend out.blend   (run after edges.py)"""
import bpy, sys, re, collections
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import kit
RULES = [tuple(r) for r in kit.get('wear', [])]   # [attr, regex on part name + bone, value]
cnt = collections.Counter()
for o in bpy.data.objects:
    if o.type != 'MESH' or 'rig_bone' not in o: continue
    key = (o.name + ' ' + str(o['rig_bone'])).lower()
    for a, rx, v in RULES:
        if re.search(rx, key) and o.get(a, 0) < v: o[a] = v; cnt[a] += 1
print('WEAR', dict(cnt))
bpy.ops.wm.save_as_mainfile(filepath=out)
