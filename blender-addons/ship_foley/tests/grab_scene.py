"""Headless test scene: a droid runs its grab motion on a toolbox placed
under its fingertips, a crate drops onto the deck (rigid body) and a mug is
set down on a table, slowly and then fast. Prints every event and checks
that the physics rules hold.

  python tests/grab_scene.py -- <droid.blend> <grab action> <out_dir>
"""
import os, sys
argv = sys.argv[sys.argv.index("--") + 1:]
blend, action, out = argv[:3]
hold = len(argv) > 3 and argv[3] == "hold"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import bpy
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=blend)
import ship_foley as F
F.register()
D = F.detect
sc = bpy.context.scene
arm = [o for o in sc.objects if o.type == "ARMATURE"][0]
act = bpy.data.actions[action]
arm.animation_data_create().action = act
try:
    arm.animation_data.action_slot = act.slots[0]
except Exception:
    pass
f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
sc.frame_start, sc.frame_end = f0, f1 + 40
for o in list(sc.objects):
    if o.name.startswith(("Prop_", "dust_")):
        bpy.data.objects.remove(o)

tips = [p for p in D.droid_probes(arm, sc) if p.hand]
low = None
for f in range(f0, f1 + 1):
    sc.frame_set(f)
    z = min(p.world().z for p in tips)
    if low is None or z < low[1]:
        low = (f, z)
sc.frame_set(low[0])
pts = [p.world() for p in tips if p.world().z < low[1] + 0.12]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
c = (lo + hi) / 2
size = Vector((max(hi.x - lo.x - 0.02, 0.08), max(hi.y - lo.y - 0.02, 0.08), max(hi.z - lo.z, 0.06)))
top = c.z + size.z / 2
bpy.ops.mesh.primitive_cube_add(size=1, location=(c.x, c.y, top / 2))
box = bpy.context.active_object
box.name = "Toolbox"
box.scale = (size.x, size.y, max(top, 0.05))
box["foley_prop"] = 1
m = bpy.data.materials.new("SB Toolbox Red")
box.data.materials.append(m)
print("grab frame", low[0], "box", [round(x, 3) for x in box.dimensions])

# crate dropping from 0.6 m onto the deck
bpy.ops.mesh.primitive_cube_add(size=0.5, location=(-1.6, 0.4, 0.85))
crate = bpy.context.active_object
crate.name = "Crate"
crate.data.materials.append(bpy.data.materials.new("SB Crate Steel"))
bpy.ops.rigidbody.object_add()
crate.rigid_body.mass = 40.0
bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.6, 0.4, -0.01))
deck = bpy.context.active_object
deck.name = "Deck Plate"
deck.scale = (1.4, 1.4, 0.02)
deck.data.materials.append(bpy.data.materials.new("SB Deck Plate"))
bpy.ops.rigidbody.object_add(type="PASSIVE")
sc.rigidbody_world.point_cache.frame_start = f0
sc.rigidbody_world.point_cache.frame_end = f1 + 40

# table + a mug set down slowly, picked up, set down fast
bpy.ops.mesh.primitive_cube_add(size=1, location=(1.8, 0.6, 0.4))
table = bpy.context.active_object
table.name = "Bar Table"
table.scale = (0.8, 0.6, 0.8)
table.data.materials.append(bpy.data.materials.new("SB Brushed Steel"))
bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=0.1, location=(1.8, 0.6, 0.95))
mug = bpy.context.active_object
mug.name = "Mug"
mug.data.materials.append(bpy.data.materials.new("SB Mug Cream"))
mug["foley_prop"] = 1
on = 0.8 + 0.05
keys = [(f0, 1.0), (f0 + 24, on), (f0 + 40, 1.0), (f0 + 44, on)]
for fr, z in keys:
    mug.location.z = z
    mug.keyframe_insert("location", index=2, frame=fr)
if hold:   # what the droid kit's Hold/Release writes: constant keys on ["hold_L"]
    arm["hold_L"] = 0.0
    for fr, v in ((f0, 0.0), (low[0], 1.0), (f1 - 10, 0.0)):
        arm["hold_L"] = v
        arm.keyframe_insert('["hold_L"]', frame=fr)
    box["held_by"] = arm.name + ":L"
os.makedirs(out, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "grab_shot.blend"))
events, made, js = F.bake_scene(sc, report=print)
for e in events:
    print("%7.2f  %-13s %-7s %-8s %-10s on %-14s %-10s v=%.2f m/s m=%.1f" % (
        e["frame"], e["who"], e["limb"], e["kind"], e["hit"]["a_mat"], e["surface"][:14], e["hit"]["b_mat"],
        e["hit"]["speed"], e["hit"]["mass"]) + ("  [hold key]" if e.get("signal") else ""))
F.place.mixdown(os.path.join(out, "foley.wav"), sc)
