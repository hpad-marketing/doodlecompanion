"""Thumbnails that need Bunny: faces, mouth sets, motions, room sets.

  DSL_LIBRARY=... DSL_BUNNY=... python build_bunny_previews.py faces|mouths|motions|sets [SIZE]
"""
import json
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from doodle_library import index, paths, motions, faces, sets as dsets  # noqa: E402

mode = sys.argv[1]
SIZE = int(sys.argv[2]) if len(sys.argv) > 2 else 192
lib = paths.library_root()
bpy.ops.wm.open_mainfile(filepath=os.path.join(paths.bunny_dir(), 'Bunny3D.blend'))
sc = bpy.context.scene
cam = sc.camera
arm = bpy.data.objects['BUNNY_rig']
fb = arm.pose.bones['face']
meta = motions.rig_meta()
ds_map = paths.bunny_module('ds_map')
sc.eevee.taa_render_samples = 4
sc.render.resolution_x = sc.render.resolution_y = SIZE
sc.render.resolution_percentage = 100
bs = bpy.data.objects['BUNNY_settings']
bs['boil'] = 0.0
out = os.path.join(lib, 'previews', {'faces': 'expression', 'mouths': 'mouth_set', 'motions': 'motion', 'sets': 'set'}[mode])
os.makedirs(out, exist_ok=True)


def shoot(name):
    sc.render.filepath = os.path.join(out, name + '.png')
    bpy.ops.render.render(write_still=True)


def frame(z, h):
    cam.data.type = 'ORTHO'
    cam.data.ortho_scale = h
    cam.location = (0, -12, z)
    bs['ink_px'] = 12.73 * 2.134 / h * (1.0 if h < 1 else 1.5)  # same world width as in a shot (thicker for tiny full-body icons)


if mode == 'faces':
    frame(0.66, 0.62)
    for it in index.items('expression'):
        d = it['data']
        for k in faces.FACE_PROPS:
            fb[k] = int(d.get(k, 0))
        arm.update_tag()
        shoot(it['id'])
elif mode == 'mouths':
    frame(0.49, 0.26)
    for it in index.items('mouth_set'):
        faces.use_mouth_set(it if it['data'].get('set') else None)
        fb['expression'] = 0
        fb['speech_mouth'] = 2
        arm.update_tag()
        shoot(it['id'])
elif mode == 'motions':
    frame(0.56, 1.35)
    for it in index.items('motion'):
        if it['kind'] != 'ds':
            continue
        m = motions.ds_motion(it['id'])
        keys = motions.track_keys(m)
        for k in list(keys):
            if k in motions.IGNORE or k in motions.CAMERA:
                keys.pop(k)
        if 'y' in keys:
            keys['bodyY'] = keys.pop('y')
        # the most expressive moment: the key furthest from rest
        best = max((f for f, _ in m['poses']), key=lambda f: sum(abs(float(motions.sample(keys, k, f)))
                   for k in keys if k not in motions.CATEGORICAL and k not in ('turn', 'bodyX', 'bodyY')))
        vals = {k: motions.sample(keys, k, best) for k in keys}
        ds_map.apply_pose(arm, meta['controls'], vals, meta['S'], None)
        for k, tid in (('expression', 'expression'), ('gaze', 'gaze'), ('speech_mouth', 'mouth')):
            fb[k] = int(vals.get(tid, 0)) if tid in vals else 0
        arm.update_tag()
        shoot(it['id'])
elif mode == 'sets':
    sc.render.resolution_x, sc.render.resolution_y = SIZE, int(SIZE * 16 / 9)
    for s in dsets.sets():
        dsets.switch_set(s['id'])
        shoot('set-' + s['id'])
    from PIL import Image
    for s in dsets.sets():  # square crop around Bunny for the list icon
        p = os.path.join(out, 'set-' + s['id'] + '.png')
        im = Image.open(p)
        w, h = im.size
        im.crop((0, int(h * 0.12), w, int(h * 0.12) + w)).save(p)
print('done', mode)
sys.stdout.flush()
os._exit(0)
