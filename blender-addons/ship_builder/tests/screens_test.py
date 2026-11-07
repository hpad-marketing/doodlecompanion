"""python3 screens_test.py -- <out dir>: build the command centre, give screens live feeds,
render a contact sheet of one screen per feed (flat camera, Eevee-free Cycles CPU, tiny)."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder.rooms import ROOMS
from ship_builder import screens as Sc
OUT = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, 240
room = ROOMS["bridge"].build()
n = Sc.feeds(sc, seed=3)
print("SCREENS", n)
star = bpy.data.objects["Star Map"]
cuts = []
for f in range(1, 241):
    sc.frame_set(f)
    cuts.append(int(star["sb_feed"]))
print("STAR MAP feeds over 10 s:", [Sc.FEEDS[c] for i, c in enumerate(cuts) if i == 0 or c != cuts[i - 1]])
# feed sheet: a flat card per feed, lit only by its own emission
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 8; sc.cycles.device = "CPU"
sc.render.resolution_x, sc.render.resolution_y = 900, 330
sc.view_settings.view_transform = "Standard"
for i, f in enumerate(Sc.FEEDS):
    bpy.ops.mesh.primitive_plane_add(size=1, location=((i % 5) * 1.1, -(i // 5) * 0.75, 0))
    p = bpy.context.object
    p.scale = (1.0, 0.62, 1)
    p.data.uv_layers.active  # plane has UVs
    p.data.materials.append(Sc.feed_material("feed", (0.35, 0.85, 1.0, 1), 1.5))
    p["sb_feed"] = float(i); p["sb_glitch"] = 0.0
cd = bpy.data.cameras.new("c"); cd.type = "ORTHO"; cd.ortho_scale = 5.6
cam = bpy.data.objects.new("c", cd); sc.collection.objects.link(cam)
cam.location = (2.2, -0.37, 5); sc.camera = cam
sc.frame_set(37)
sc.render.filepath = os.path.join(OUT, "feeds.png")
bpy.ops.render.render(write_still=True)
print("WROTE", sc.render.filepath)
