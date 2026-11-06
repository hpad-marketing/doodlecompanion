"""Headless: open a droid .blend, play an action, scan, bake, mix down.

  python tests/scan_blend.py -- <file.blend> <action or -> <out_dir> [frame_end]
(with the bpy wheel) or  blender -b <file> --python tests/scan_blend.py -- ...
"""
import os, sys
argv = sys.argv[sys.argv.index("--") + 1:]
blend, action, out = argv[0], argv[1], argv[2]
fend = int(argv[3]) if len(argv) > 3 else None
here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, here)
import bpy
bpy.ops.wm.open_mainfile(filepath=blend)
import ship_foley as F
F.register()
sc = bpy.context.scene
arm = [o for o in sc.objects if o.type == "ARMATURE"][0]
if action != "-":
    act = bpy.data.actions[action]
    arm.animation_data_create().action = act
    try:
        arm.animation_data.action_slot = act.slots[0]
    except Exception:
        pass
    sc.frame_start, sc.frame_end = int(act.frame_range[0]), int(act.frame_range[1])
if fend:
    sc.frame_end = fend
os.makedirs(out, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "shot.blend"))
events, made, js = F.bake_scene(sc, report=print)
for e in events:
    print("%7.2f  %-14s %-7s %-8s %-6s on %-28s %-10s v=%.2f m/s  pan=%+.2f" % (
        e["frame"], e["who"], e["limb"], e["kind"], e["hit"]["a_mat"], e["surface"][:28], e["hit"]["b_mat"],
        e["hit"]["speed"], e["pan"]))
print("strips", made, js)
F.place.mixdown(os.path.join(out, "foley.wav"), sc)
