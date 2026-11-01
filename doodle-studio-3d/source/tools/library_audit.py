"""Doodle Library health audit: floor contact in every set, thin ink details, grips, prop sizes.

Run on the PC against the real library (Blender 4.5/5.0, nothing is saved):
    blender -b host/blender/Bunny3D_v2.blend --python tools/library_audit.py -- OUT.json [--grips]
DSL_LIBRARY points at the library folder (default Documents/Talking Character App/blender-library).
--grips adds the hand test for every held prop (about 30 s a prop).

Checks
  floor   every set piece's lowest point against its set's floor: 'sunk' (more than 5 mm below)
          and 'float' (above the floor with nothing under it and no wall behind it). Rocks,
          bushes, ferns and other pieces bedded in on purpose show up as sunk: read the list.
  thin    ink-coloured parts thin enough to become one-stroke lines (style.thin_ink_to_lines).
  grips   grips.attach + check_contact for each held prop: touching, no stray overlap, no body clip.
  sizes   each held prop's longest side in cm, to compare with its real size.
"""
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'host', 'blender', 'addons'))
import doodle_library.api as dl  # noqa: E402
from doodle_library import grips, index, style  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out_path = next((a for a in argv if not a.startswith('--')), 'library-audit.json')


def extents(ob):
    """World-space min and max of the mesh's own vertices (a rotated bound box overshoots)."""
    vs = [ob.matrix_world @ v.co for v in ob.data.vertices] or [ob.matrix_world.translation]
    return [min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]


def overlap_xy(a, b):
    return a['min'][0] < b['max'][0] and a['max'][0] > b['min'][0] and a['min'][1] < b['max'][1] and a['max'][1] > b['min'][1]


report = {'floor': {'sunk': [], 'float': []}, 'thin': {}, 'grips': {}, 'sizes': {}}
for s in dl.sets_list():
    sid = s['id']
    dl.switch_set(sid)
    bpy.context.view_layer.update()
    rows = []
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and ob.get('dsl_set') == sid and ob.visible_get():
            lo, hi = extents(ob)
            rows.append({'prop': ob.get('dsl_prop'), 'model': ob.get('dsl_model'), 'shell': bool(ob.get('dsl_shell')),
                         'min': lo, 'max': hi, 'thin': int(ob.data.get('dsl_thin_lines') or 0)})
    shell = [r for r in rows if r['shell']]
    fz = min((r['min'][2] for r in shell), default=0.0)
    sh = shell[0] if shell else None
    for r in rows:
        if r['thin']:
            report['thin']['%s:%s' % (sid, r['prop'])] = r['thin']
        if r['shell']:
            continue
        z = r['min'][2] - fz
        if z < -0.005:
            report['floor']['sunk'].append([sid, r['prop'], r['model'], round(z * 100, 1)])
        elif z > 0.005:
            under = [p for p in rows if p is not r and not p['shell'] and abs(p['max'][2] - r['min'][2]) < 0.03 and overlap_xy(p, r)]
            wall = sh and (r['max'][1] >= sh['max'][1] - 0.06 or r['min'][0] <= sh['min'][0] + 0.06
                           or r['max'][0] >= sh['max'][0] - 0.06 or r['max'][2] >= sh['max'][2] - 0.06)
            far = r['min'][1] > (sh['max'][1] if sh else 3) + 0.5 or z > 1.2
            if not under and not wall and not far:
                report['floor']['float'].append([sid, r['prop'], r['model'], round(z * 100, 1)])
    print('set', sid, flush=True)

held = [r['id'] for r in index.items('prop')]
for pid in held:
    ob = dl.insert(pid)
    report['sizes'][pid] = round(max(ob.dimensions) * 100)
    if '--grips' in argv:
        try:
            r = grips.attach(ob)
            report['grips'][pid] = {'ok': bool(r.get('ok')), 'kind': r.get('kind'), 'says': grips.describe(r)}
        except Exception as e:
            report['grips'][pid] = {'ok': False, 'says': 'error: %s' % e}
        print('grip', pid, report['grips'][pid]['says'], flush=True)
        try:
            grips.release(ob)
        except Exception:
            pass
    bpy.data.objects.remove(ob)

json.dump(report, open(out_path, 'w'), indent=1)
g = report['grips']
print('floor: %d sunk, %d floating; thin lines: %d parts; grips: %s' % (
    len(report['floor']['sunk']), len(report['floor']['float']), sum(report['thin'].values()),
    '%d of %d pass' % (sum(1 for v in g.values() if v['ok']), len(g)) if g else 'not run'))
