"""Build the ship in a fresh scene, run the collision audit through every
moving part's range, and optionally render check views.
usage: python build_test.py -- <out_prefix> [views] [--audit] [--set guns=1,gun_yaw=30]"""
import sys, os, math, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.dirname(__file__))
import bpy
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
import hero_ship
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = argv[0] if argv else "/tmp/hs"
views = argv[1] if len(argv) > 1 else ""
t = time.time()
root = hero_ship.build()
print("built in %.1fs" % (time.time() - t))
obs = hero_ship.ship_objects(root)
tris = 0
dg = bpy.context.evaluated_depsgraph_get()
for o in obs:
    if o.type == "MESH":
        tris += sum(len(p.vertices) - 2 for p in o.evaluated_get(dg).data.polygons)
print("objects", len(obs), "tris", tris)

if "--audit" in argv:
    import sb_collide as C
    def aud(label):
        bpy.context.view_layer.update()
        hits = C.audit_objects(obs)
        print("AUDIT", label, len(hits), hits[:8])
        return hits
    total = 0
    states = [dict(gear=g) for g in (0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.0)]
    states += [dict(gear=1, gear_compress=k) for k in (0.15, 0.3)]
    states += [dict(ramp=r) for r in (0.25, 0.5, 0.75, 1.0)]
    states += [dict(nacelle_tilt=v) for v in (0.25, 0.5, 0.75, 1.0)]
    states += [dict(radiators=v) for v in (0.0, 0.33, 0.66)]
    states += [dict(scan_deg=v) for v in (45, 90, 170)]
    states += [dict(engine_extend=v) for v in (0.5, 1.0)]
    states += [dict(spine_lift=v) for v in (0.5, 1.0)]
    states += [dict(canards=v) for v in (0.25, 0.5, 0.75, 1.0)]
    states += [dict(guns=v) for v in (0.15, 0.3, 0.45, 0.6, 0.8, 1.0)]
    states += [dict(guns=1, gun_yaw=y, gun_pitch=p, gun_fire=f)
               for y in (-100, -60, 0, 60, 100) for p in (-5, 20, 40) for f in (0, 1)]
    states += [dict(engine_extend=1, spine_lift=1, guns=1, canards=1, radiators=0, nacelle_tilt=1, gear=1, ramp=1)]
    sc = bpy.context.scene
    for st in states:
        for k, v in hero_ship.parts.PROPS.items():
            root[k] = v[0]
        for k, v in st.items():
            root[k] = v
        root.update_tag()
        sc.frame_set(1)
        total += len(aud(str(st)))
    for f in (1, 40, 80, 120, 160, 200):
        sc.frame_set(f)
        total += len(aud(f"dish frame {f}"))
    for k, v in hero_ship.parts.PROPS.items():
        root[k] = v[0]
    print("AUDIT TOTAL", total)

if "--set" in argv:
    for kv in argv[argv.index("--set") + 1].split(","):
        k, v = kv.split("=")
        root[k] = float(v)
    root.update_tag()
    bpy.context.scene.frame_set(1)

if views:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    if "stage" not in argv:
        w = bpy.data.worlds.new("W"); sc.world = w
        w.use_nodes = True
        bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.55, 0.6, 0.66, 1); bg.inputs[1].default_value = 0.7
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN")); sc.collection.objects.link(sun)
        sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(140)); sun.data.energy = 4
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); sc.collection.objects.link(cam); sc.camera = cam
    V = {"a": ((36, 32, 14), (0, -1, 0), 40), "b": ((-32, -40, 11), (0, -3, 0), 40),
         "c": ((14, -6, -30), (0, -3, -2), 35), "d": ((44, 0, 0), (0, 0, 0), 35),
         "e": ((9, 16, 3), (0, 0, 1), 28), "f": ((0, 0, 60), (0, 0, 0), 35),
         "g": ((16, -22, -7), (0, -8, -3), 35), "n": ((10, 34, 2), (0, 18, 0), 40),
         "t": ((9, 17, 8), (0, 8.2, 3.4), 30), "w": ((-20, -36, 10), (0, -13, 1.5), 32),
         "k": ((14, 26, -1), (0, 15, -0.6), 30)}
    for k, (p, tgt, lens) in V.items():
        if k not in views:
            continue
        cam.location = p
        cam.data.lens = lens
        cam.rotation_euler = (Vector(tgt) - Vector(p)).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = f"{out}_{k}.png"
        bpy.ops.render.render(write_still=True)
    if "save" in argv:
        bpy.ops.wm.save_as_mainfile(filepath=out + ".blend")
print("total %.1fs" % (time.time() - t))
