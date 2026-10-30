"""360° prop library -> props/props.blend (one 3D object per approved prop, grip at the origin).

  python build_props.py PROPS_LIBRARY_DIR PICKS.json OUT_LIBRARY_DIR
"""
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

lib_dir, picks_path, out = sys.argv[sys.argv.index('--') + 1:][:3] if '--' in sys.argv else sys.argv[1:4]
K = 0.58 / 230  # prop model units: Bunny's head is ~230 wide, 0.58 m in the 3D rig
approved = json.load(open(picks_path))['approved']
bpy.ops.wm.read_factory_settings(use_empty=True)
mats = common.placeholder_materials()
objs, rows = [], []
for pid in approved:
    d = json.load(open(os.path.join(lib_dir, 'props', pid + '.json')))
    M = d['model']
    verts = [(x * K, -z * K, y * K) for x, y, z in M['vertices']]
    me = bpy.data.meshes.new('prop-' + pid)
    me.from_pydata(verts, [], [tuple(f) for f in M['faces']])
    a = me.attributes.new('dsl_group', 'INT', 'FACE')
    a.data.foreach_set('value', M['faceGroups'])
    me.materials.append(mats['DSL_mustard'])
    common.finish_mesh(me)
    ob = bpy.data.objects.new('prop-' + pid, me)
    ob['dsl_id'] = 'prop-' + pid
    ob['dsl_kind'] = 'prop'
    ob.asset_mark()
    ob.asset_data.description = d.get('grip', '')
    ob.asset_data.tags.new(d.get('category', 'Props'))
    objs.append(ob)
    h = d.get('hold') or {}
    rows.append({'id': 'prop-' + pid, 'name': d['label'], 'category': 'prop', 'kind': 'object',
                 'sub': d.get('category', 'Props'), 'file': 'props/props.blend', 'datablock': 'prop-' + pid,
                 'tags': [d.get('category', '')], 'source': 'doodle-studio 360 props',
                 'description': d.get('grip', ''),
                 'data': {'grip': d.get('grip', ''), 'hold': {k: h.get(k) for k in ('hand', 'attach', 'pose', 'orientation')}
                          if h else None}})
common.save_blend(os.path.join(out, 'props', 'props.blend'), objs)
common.write_part(out, 'props', rows)
print('props', len(rows))
