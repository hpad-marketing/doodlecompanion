"""List every mechanism found on a droid file and what kind of sound it gets,
then bake a motion and report each group's level.

  python tests/mech_report.py -- <droid.blend> <action> <out_dir> [door]
"""
import os, sys
argv = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
import numpy as np
bpy.ops.wm.open_mainfile(filepath=argv[0])
import ship_foley as F
F.register()
sc = bpy.context.scene
arm = [o for o in sc.objects if o.type == "ARMATURE"][0]
act = bpy.data.actions[argv[1]]
arm.animation_data_create().action = act
try:
    arm.animation_data.action_slot = act.slots[0]
except Exception:
    pass
sc.frame_start, sc.frame_end = int(act.frame_range[0]), int(act.frame_range[1])
if len(argv) > 3 and argv[3] == "door":       # a ship door that slides open and a hatch that swings
    bpy.ops.mesh.primitive_cube_add(size=1, location=(2.5, 1.5, 1.1))
    door = bpy.context.active_object; door.name = "Door Leaf"; door.scale = (0.08, 0.75, 1.1)
    for fr, y in ((sc.frame_start, 1.5), (sc.frame_start + 12, 1.5), (sc.frame_start + 26, 2.3)):
        door.location.y = y; door.keyframe_insert("location", index=1, frame=fr)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-2.5, 1.5, 0.6))
    hatch = bpy.context.active_object; hatch.name = "Floor Hatch"; hatch.scale = (0.6, 0.6, 0.03)
    for fr, r in ((sc.frame_start + 20, 0.0), (sc.frame_start + 40, 1.4)):
        hatch.rotation_euler.x = r; hatch.keyframe_insert("rotation_euler", index=0, frame=fr)
kinds = {}
for j in F.motors.joints(arm):
    kinds.setdefault(j.kind, []).append(j.name)
for k, v in sorted(kinds.items()):
    print("%-8s %3d  %s" % (k, len(v), ", ".join(v[:14]) + (" ..." if len(v) > 14 else "")))
os.makedirs(argv[2], exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(argv[2], "mech.blend"))
ev, made, js = F.bake_scene(sc)
for s in sc.sequence_editor.strips:
    if "motors" in s.name:
        import wave
        w = wave.open(bpy.path.abspath(s.sound.filepath))
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2") / 32768
        print("  %-36s peak %6.1f dB" % (s.name[3:], 20 * np.log10(abs(x).max() + 1e-9)))
print("clunks", sum(e["kind"] == "clunk" for e in ev), "strips", made)
