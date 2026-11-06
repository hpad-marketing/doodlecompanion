"""Swap in the edge- and seam-aware shader groups from weather.py, keeping every material's settings and look drivers.
python3 edges.py in.blend out.blend"""
import bpy, sys, os, glob
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weather.py')).read()
defs = src[src.index('def srgb'):src.index('MG, PG = ')]
import os, glob
TEX = os.environ.get('RB_TEX', '')
SCAN = {}
for f in sorted(glob.glob(os.path.join(TEX, '*.jpg'))) if TEX else []:
    k = os.path.basename(f).replace('_2k.jpg', '')
    im = bpy.data.images.get(k) or bpy.data.images.load(f); im.name = k
    if not k.endswith('_diff'): im.colorspace_settings.name = 'Non-Color'
    if not im.packed_file: im.pack()
    im.use_fake_user = True
    SCAN[k] = im
ns = {'bpy': bpy, 're': __import__('re'), 'SCAN': SCAN, '__file__': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weather.py')}; exec(defs, ns)
print('SCANS', sorted(SCAN))
old = {n: bpy.data.node_groups[n] for n in ('RB Weathered Metal', 'RB Black Polymer')}
for g in old.values(): g.name += ' OLD'
MG, PG = ns['metal_group'](), ns['polymer_group']()
swap = 0
for m in bpy.data.materials:
    if not m.node_tree or 'Look' not in m.node_tree.nodes: continue
    gn = m.node_tree.nodes['Look']
    vals = {s.name: (tuple(s.default_value) if hasattr(s.default_value, '__len__') else s.default_value) for s in gn.inputs}
    gn.node_tree = MG if gn.node_tree == old['RB Weathered Metal'] else PG
    for s in gn.inputs:
        if s.name in vals: s.default_value = vals[s.name]
    swap += 1
for g in old.values(): bpy.data.node_groups.remove(g)
bad = [(m.name, d.data_path) for m in bpy.data.materials if m.node_tree and m.node_tree.animation_data
       for d in m.node_tree.animation_data.drivers if not d.driver.is_valid]
print('EDGES swapped', swap, 'broken drivers', bad)
bpy.ops.wm.save_as_mainfile(filepath=out)
