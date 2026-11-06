import sys, os, math, importlib
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
import bpy
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
import hero_ship.geo as geo, hero_ship.layout as lay, hero_ship.mats as mats
import time
t=time.time()
c = geo.coll("Hero Ship")
root = geo.empty("Hero Ship", c)
M = mats.build_all()
hull, ramp, mods = lay.build_hull(c, root, M)
lay.build_mechanics(c, root, M)
lay.build_engines(c, root, M)
print("built", time.time()-t, len(hull.data.polygons))
out = sys.argv[sys.argv.index("--")+1] if "--" in sys.argv else "/tmp/q"
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE" if "eevee" in out else "CYCLES"
sc.cycles.samples = 16; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 960, 540
w = bpy.data.worlds.new("W"); w.use_nodes=True; w.node_tree.nodes["Background"].inputs[0].default_value=(0.6,0.65,0.7,1); w.node_tree.nodes["Background"].inputs[1].default_value=0.6; sc.world=w
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun","SUN")); sc.collection.objects.link(sun); sun.rotation_euler=(math.radians(50),math.radians(10),math.radians(140)); sun.data.energy=4
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera=cam
cam.data.lens=40
views = {"a": ((34, 30, 14), (0,-1,0)), "b": ((-30,-38,10),(0,-2,0)), "c": ((0,-10,-40),(0,-3,0)), "d":((40,0,0),(0,0,0))}
for k,(p,tgt) in views.items():
    if len(sys.argv)>sys.argv.index("--")+2 and k not in sys.argv[sys.argv.index("--")+2]: continue
    cam.location=p
    d=Vector(tgt)-Vector(p); cam.rotation_euler=d.to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=f"{out}_{k}.png"
    bpy.ops.render.render(write_still=True)
print("done", time.time()-t)
