"""python3 window_view_test.py -- <out> [views...]: lounge wide shot through the window, one still per view."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder import ship, lighting as Li, views as V
a = sys.argv[sys.argv.index('--') + 1:]
OUT, keys = a[0], a[1:] or ["SUNRISE", "RINGED_PLANET"]
sc = bpy.context.scene
Li.render_setup(sc, preview=True)
Li.space_world()
info = ship.build(["lounge"])
Li.camera_finish(sc)
cam = next(bpy.data.objects[c["name"]] for c in info["cameras"] if c["label"] == "Wide master")
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = 480, 600
sc.cycles.samples = 24
sc.frame_set(60)
for k in keys:
    V.set_view(k, sc)
    sc.render.filepath = os.path.join(OUT, f"lounge_{k}.jpg")
    sc.render.image_settings.file_format = "JPEG"
    bpy.ops.render.render(write_still=True)
    print("WROTE", k, flush=True)
