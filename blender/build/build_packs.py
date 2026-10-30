"""Build packs/packs.blend: every asset-pack piece (models3.py) as its own object.

  python build_packs.py OUT_LIBRARY_DIR

Hand props become 'prop' rows (they get a researched grip), everything else 'scenery'.
Moving parts (lids, wheels, wings) are saved as their own objects named <model>__<part>
with the origin on the hinge; the add-on parents them back when you insert the piece.
Effect particles (fx_*) are saved too but get no row: the Effects panel uses them.
"""
import json
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import models3 as M3  # noqa: E402
import rooms as R  # noqa: E402

out = (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
mats = common.placeholder_materials()

PACK_NAMES = {
    'reveal': 'Reveal props', 'boards': 'Explainer boards', 'signs': 'Signs and placards', 'bubbles': '3D speech bubbles',
    'reactions': 'Reaction symbols', 'screens': 'Screens with your clips', 'frames': 'Photo frames and posters',
    'weather': 'Rain and puddles', 'snowwind': 'Snow, wind and leaves', 'party': 'Party pack', 'impact': 'Impact effects',
    'smoke': 'Toon smoke and steam', 'lights': 'Practical lights', 'magic': 'Sparkle and teleport',
    'crowd': 'Background crowd', 'critters': 'Small critters', 'talkobj': 'Talking objects', 'cars': 'Cars and city rides',
    'bikes': 'Bikes and boards', 'fantasy': 'Fantasy rides', 'food': 'Food and chai kit', 'festival': 'Festival kits',
    'music': 'Music kit', 'creator': 'Creator desk kit', 'sports': 'Sports kit', 'foreground': 'Foreground framing',
    'backdrop': 'Clean backdrops', 'skydomes': 'Doodle skies', 'skyline': 'Distant skylines',
}
META_KEYS = ('text', 'screen', 'surface', 'place', 'light', 'neon', 'seat', 'mouth', 'talker', 'reaction', 'steam',
             'foreground', 'sky', 'beams', 'breathe', 'float')


def mesh_of(piece, name, pivot=None):
    ob = piece.build(mats)
    me = ob.data
    bpy.data.objects.remove(ob)
    me.name = name
    if pivot is not None:
        me.transform(__import__('mathutils').Matrix.Translation(-Vector(pivot)))
    common.finish_mesh(me, merge=0.00005)
    return me


objs, rows = [], []
for name, fn in M3.M3.items():
    res = fn()
    piece, parts = (res if isinstance(res, tuple) else (res, []))
    hold = name in M3.HOLD
    ob = bpy.data.objects.new(('prop-' if hold else 'scenery-') + name, mesh_of(piece, 'DSL_' + name))
    s = 1.0 if hold or name.startswith('fx_') else R.WORLD
    ob.scale = (s, s, s)
    did = ob.name
    ob['dsl_id'] = did
    ob['dsl_kind'] = 'prop' if hold else 'scenery'
    ob['dsl_pack'] = M3.PACK[name]
    for k in META_KEYS:
        if k in piece.meta:
            ob['dsl_' + k] = json.dumps(piece.meta[k])
    pnames = []
    for pt in parts:
        pob = bpy.data.objects.new('%s__%s' % (did, pt['name']), mesh_of(pt['piece'], 'DSL_%s_%s' % (name, pt['name']),
                                                                             pt['pivot']))
        pob['dsl_part'] = pt['kind']
        pob['dsl_axis'] = pt['axis']
        pob['dsl_amount'] = float(pt['amount'])
        pob['dsl_pivot'] = list(pt['pivot'])
        objs.append(pob)
        pnames.append(pob.name)
    if pnames:
        ob['dsl_parts'] = json.dumps(pnames)
    if not name.startswith('fx_'):
        ob.asset_mark()
        ob.asset_data.tags.new(PACK_NAMES[M3.PACK[name]])
        label = name.replace('_', ' ').capitalize()
        row = {'id': did, 'name': label, 'category': 'prop' if hold else 'scenery', 'kind': 'object',
               'sub': PACK_NAMES[M3.PACK[name]], 'file': 'packs/packs.blend', 'datablock': did,
               'tags': ['pack', M3.PACK[name]] + (['moving parts'] if pnames else []), 'source': 'doodle-library packs',
               'data': {'pack': M3.PACK[name]}}
        if hold:
            row['data']['grip'] = list(M3.HOLD[name])
        if 'place' in piece.meta:
            row['data']['place'] = piece.meta['place']
        rows.append(row)
    objs.append(ob)

common.save_blend(os.path.join(out, 'packs', 'packs.blend'), objs)
common.write_part(out, 'packs', rows)
json.dump(M3.HOLD, open(os.path.join(out, 'packs', 'grips.json'), 'w'), indent=0)
print('packs', len(rows), 'objects', len(objs))
