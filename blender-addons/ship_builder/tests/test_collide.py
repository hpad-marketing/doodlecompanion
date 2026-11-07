"""Self-test of collide.py: a planted intersection must be caught, a resting contact must not,
and a droid's parts are tested against the set and against each other per frame."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder import collide, kit as K, mats as M
from ship_builder.rooms import ROOMS
room = ROOMS['lounge'].build(wear_seed=1)
ok = True
# 1) resting contact: a box sitting exactly on the deck -> no hit
a = K.box("Test Rest", (0.3, 0.3, 0.3), (0, 1.0, 0.15), room.pal["hull"], room.dress, bevel=0)
# 2) planted intersection: a rod pushed through the couch base
b = K.cyl("Test Rod", 0.03, 1.2, (0.3, room.D - 0.75, 0.35), room.pal["steel"], room.dress, rot=(1.5708, 0, 0), bevel=0)
hits = collide.audit_room(room)
names = {n for p in hits for n in p}
print('rest caught (should be False):', any(n.startswith('Test Rest') for n in names))
print('rod caught (should be True):', any(n.startswith('Test Rod') for n in names))
ok &= not any(n.startswith('Test Rest') for n in names) and any(n.startswith('Test Rod') for n in names)
bpy.data.objects.remove(a); bpy.data.objects.remove(b)
# 3) droid: an armature with an upper arm and forearm (neighbours, may touch) and a hand
dc = bpy.data.collections.new("Droid Test"); bpy.context.scene.collection.children.link(dc)
arm = bpy.data.objects.new("Droid Rig", bpy.data.armatures.new("Droid Rig")); dc.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
b1 = eb.new("upper"); b1.head, b1.tail = (0, 1.0, 1.0), (0, 1.0, 0.7)
b2 = eb.new("fore"); b2.head, b2.tail = (0, 1.0, 0.7), (0, 1.0, 0.4); b2.parent = b1
b3 = eb.new("hand"); b3.head, b3.tail = (0, 1.0, 0.4), (0, 1.0, 0.3); b3.parent = b2
bpy.ops.object.mode_set(mode='OBJECT')
parts = []
for bn, z in (("upper", 0.85), ("fore", 0.55), ("hand", 0.35)):
    o = K.box(f"Droid {bn}", (0.08, 0.08, 0.32), (0, 1.0, z), room.pal["steel"], dc, bevel=0)
    for c in list(o.users_collection):
        if c != dc: c.objects.unlink(o)
    bpy.context.view_layer.update()
    mw = o.matrix_world.copy()
    o.parent = arm; o.parent_type = 'BONE'; o.parent_bone = bn
    bpy.context.view_layer.update()
    o.matrix_world = mw  # keep place
    parts.append(o)
bpy.context.view_layer.update()
sc = bpy.context.scene
for o in parts: print("POS", o.name, tuple(round(v,3) for v in o.matrix_world.translation), o.users_collection[0].name)
rep = collide.audit_scene(sc, frames=[1])
print('droid at rest, hits:', rep)
ok &= not rep
# bend the forearm back through the upper arm (non-neighbour hand hits upper)
pb = arm.pose.bones["fore"]; pb.rotation_mode = 'XYZ'; pb.rotation_euler = (3.0, 0, 0)
pb.keyframe_insert("rotation_euler", frame=2)
rep = collide.audit_scene(sc, frames=[2])
print('droid folded, hits:', rep)
ok &= bool(rep)
print('SELFTEST', 'PASS' if ok else 'FAIL')
