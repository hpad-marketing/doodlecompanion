"""python3 views_test.py -- <out dir>: render each outside view looking out of a window (+Y)."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder import views as V
OUT = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 16; sc.cycles.device = "CPU"
sc.render.resolution_x, sc.render.resolution_y = 384, 216
sc.view_settings.view_transform = "AgX"
V.build(sc)
cd = bpy.data.cameras.new("c"); cd.lens = 18
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam)
import math
cam.rotation_euler = (math.radians(90), 0, 0)  # looks +Y
sc.camera = cam
for k in V.KEYS:
    V.set_view(k, sc)
    sc.render.filepath = os.path.join(OUT, f"view_{k}.png")
    bpy.ops.render.render(write_still=True)
    print("WROTE", k)
