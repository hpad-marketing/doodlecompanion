"""Live viewport models for Doodle Studio 3D: each Doodle Library set, prop or scenery
piece is written once as a small GLB the editor shows in its own 3D view, so a shot can
be composed without opening Blender. The models come straight from the library's own
.blend files (the same datablocks the render loads); the editor redraws them in the
Doodle look (mustard fill, ink line), so materials only carry their names.

blender -b --factory-startup --python preview_export.py -- <library dir> <out dir> <id> [<id> ...]
Writes <out dir>/<id>.glb and prints one line per id: OK <id> or FAIL <id>: reason.
Z stays up (Blender axes, as the editor's viewport uses them).
"""
import json
import os
import sys

import bpy

argv = sys.argv[sys.argv.index('--') + 1:]
LIB, OUT, IDS = argv[0], argv[1], argv[2:]
os.makedirs(OUT, exist_ok=True)
rows = {r['id']: r for r in json.load(open(os.path.join(LIB, 'library.json'), encoding='utf-8'))['items']}


def clear():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for block in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.node_groups):
        for b in list(block):
            if b.users == 0:
                block.remove(b)


def load(row):
    f = os.path.join(LIB, row['file'])
    name = row.get('datablock') or row['id']
    sc = bpy.context.scene
    if row['category'] == 'set':
        with bpy.data.libraries.load(f, link=False) as (src, dst):
            dst.collections = [name]
        coll = dst.collections[0]
        sc.collection.children.link(coll)
        obs = list(coll.all_objects)
    else:
        with bpy.data.libraries.load(f, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n == name or n.startswith(name + '.')]
        obs = [o for o in dst.objects if o]
        if not obs:
            raise RuntimeError('no object ' + name)
        for o in obs:
            sc.collection.objects.link(o)
        # children the root brings along (lids, wheels, labels) come with it
        for o in list(obs):
            for c in o.children_recursive:
                if c.name not in sc.objects:
                    sc.collection.objects.link(c)
                    obs.append(c)
    for o in obs:
        o.hide_viewport = o.hide_render = False
        o.hide_set(False)
        o.select_set(o.type in ('MESH', 'CURVE', 'FONT', 'EMPTY'))
        # what the editor needs to switch pieces and recolour: plain extras on the node
        for k in ('dsl_prop', 'dsl_on', 'dsl_shell', 'dsl_default'):
            if k in o.keys():
                o['ds_' + k[4:]] = o[k] if not isinstance(o[k], (bytes,)) else str(o[k])
        for i, slot in enumerate(o.material_slots):
            if slot.material:
                slot.material['ds_ink'] = 1 if 'ink' in slot.material.name.lower() else 0
    return obs


def export(row):
    clear()
    obs = load(row)
    out = os.path.join(OUT, row['id'] + '.glb')
    tmp = out + '.tmp.glb'
    bpy.ops.export_scene.gltf(filepath=tmp, export_format='GLB', use_selection=True, export_yup=False, export_extras=True,
                              export_apply=True, export_animations=False, export_skins=False, export_morph=False,
                              export_lights=False, export_cameras=False, export_image_format='NONE')
    os.replace(tmp, out)
    return len(obs)


for i in IDS:
    row = rows.get(i)
    try:
        if not row:
            raise RuntimeError('not in library.json')
        if row['category'] not in ('set', 'prop', 'scenery'):
            raise RuntimeError('only sets, props and scenery have models')
        n = export(row)
        print('OK %s %d' % (i, n), flush=True)
    except Exception as e:
        print('FAIL %s: %s' % (i, e), flush=True)
