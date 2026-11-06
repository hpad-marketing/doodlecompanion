"""Apply every preset, audit collisions on sampled frames (ship parts against
each other and against the ground), and render one check still per preset.
usage: python preset_test.py -- <out_prefix> [preset_ids,comma] [--render] [--res 640]"""
import sys, os, math, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.dirname(__file__))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
import hero_ship
from hero_ship import presets
import sb_collide as C
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = argv[0] if argv else "/tmp/hp"
ids = argv[1].split(",") if len(argv) > 1 and not argv[1].startswith("--") else [p["id"] for p in presets.PRESETS]
res = int(argv[argv.index("--res") + 1]) if "--res" in argv else 640
root = hero_ship.build()
obs = hero_ship.ship_objects(root)
meshes = [o for o in obs if o.type == "MESH"]
sc = bpy.context.scene
grand = 0
for pid in ids:
    t = time.time()
    n = presets.apply(root, pid, 1)
    hits_total, low = 0, []
    step = 6 if n > 200 else 4
    frames = list(range(1, n + 1, step))
    if pid == "planet_landing":
        frames += list(range(286, 320)) + [n]
    for f in sorted(set(frames)):
        sc.frame_set(f)
        hits = C.audit_objects(obs)
        if hits:
            print("  HIT", pid, f, hits[:5])
        hits_total += len(hits)
        if presets.BY_ID[pid]["needs_stage"] == "planet":
            dg = bpy.context.evaluated_depsgraph_get()
            mz, who = 1e9, None
            for o in meshes:
                ev = o.evaluated_get(dg)
                mw = o.matrix_world
                for v in ev.data.vertices:
                    z = (mw @ v.co).z
                    if z < mz:
                        mz, who = z, o.name
            low.append((f, round(mz, 4), who))
            if mz < -0.003:
                print("  GROUND HIT", pid, f, round(mz, 4), who)
                hits_total += 1
    if low:
        print("  lowest points (frame, z, part):", [l for l in low if l[0] >= 280][:12], low[-1])
    print("PRESET", pid, "frames", n, "audited", len(set(frames)), "hits", hits_total, "%.0fs" % (time.time() - t))
    grand += hits_total
    if "--render" in argv:
        sc.cycles.samples = 24
        sc.cycles.use_denoising = True
        sc.render.resolution_x, sc.render.resolution_y = res, res * 9 // 16
        for f in [int(x) for x in (argv[argv.index("--frames") + 1].split(",") if "--frames" in argv else [n // 2])]:
            sc.frame_set(f)
            sc.render.filepath = f"{out}_{pid}_{f}.png"
            bpy.ops.render.render(write_still=True)
print("GRAND TOTAL", grand)
