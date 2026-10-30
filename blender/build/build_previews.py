"""Render library thumbnails as one grid per .blend (much faster than one render each), then cut tiles.

  python build_previews.py LIBRARY_DIR REL_BLEND CATEGORY_FOLDER [--yaw 30 --pitch 18 --cell 256 --cols 10]
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from doodle_library import style  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
lib, rel, folder = args[:3]
opt = lambda k, d: type(d)(args[args.index(k) + 1]) if k in args else d
YAW, PITCH, CELL, COLS = opt('--yaw', 30.0), opt('--pitch', 18.0), opt('--cell', 256), opt('--cols', 10)
FILL = opt('--fill', 0.78)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
path = os.path.join(lib, rel)
with bpy.data.libraries.load(path) as (src, dst):
    dst.objects = list(src.objects)
objs = [o for o in dst.objects if o and o.type == 'MESH']
objs.sort(key=lambda o: o.name)
n = len(objs)
cols = min(COLS, n)
rows = math.ceil(n / cols)
cam = bpy.data.objects.new('CAM', bpy.data.cameras.new('CAM'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.type = 'ORTHO'
cam.data.ortho_scale = max(cols, rows)
cam.location = (cols / 2, -50, -rows / 2)
cam.rotation_euler = (math.pi / 2, 0, 0)
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x = cols * CELL
sc.render.resolution_y = rows * CELL
sc.render.film_transparent = False
sc.eevee.taa_render_samples = 8
w = bpy.data.worlds.new('w')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = common.MUSTARD
mats = style.materials()
bs = style.bunny_settings()
bs['ink_px'] = 1920 * opt('--ink', 0.007) / max(cols, rows)
bs['boil'] = 0.0
R = Matrix.Rotation(math.radians(-PITCH), 4, 'X') @ Matrix.Rotation(math.radians(YAW), 4, 'Z')
for i, ob in enumerate(objs):
    sc.collection.objects.link(ob)
    ob.matrix_world = R
    bpy.context.view_layer.update()
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector([min(p[k] for p in pts) for k in range(3)])
    hi = Vector([max(p[k] for p in pts) for k in range(3)])
    size = max(hi.x - lo.x, hi.z - lo.z, 1e-4)
    s = FILL / size
    c = (lo + hi) / 2
    cx, cz = (i % cols) + 0.5, -((i // cols) + 0.5)
    ob.matrix_world = Matrix.Translation((cx - c.x * s, -c.y * s, cz - c.z * s)) @ Matrix.Scale(s, 4) @ R
    style.apply_style(ob, cam, mats)
sc.render.filepath = os.path.join(lib, 'previews', '_grid_' + folder + '.png')
bpy.ops.render.render(write_still=True)
from PIL import Image  # noqa: E402  (pillow is in the build venv)
im = Image.open(sc.render.filepath)
os.makedirs(os.path.join(lib, 'previews', folder), exist_ok=True)
for i, ob in enumerate(objs):
    x, y = (i % cols) * CELL, (i // cols) * CELL
    im.crop((x, y, x + CELL, y + CELL)).convert('RGB').save(os.path.join(lib, 'previews', folder, ob.name + '.png'))
os.remove(sc.render.filepath)
print('previews', folder, n)
