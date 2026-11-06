"""python3 feet_test.py: a test biped walks over deck, a 12 mm rug, a 15 cm step, a 10 deg ramp and a sill.
The foot test runs before and after the Planter; after must be 0 frames over the limits."""
import os, sys, math
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import bpy
from mathutils import Vector, Matrix
bpy.ops.wm.read_factory_settings(use_empty=True)
from ship_builder import feet as F
sc = bpy.context.scene

def box(name, size, loc, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.object; o.name = name; o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return o
box("Deck", (20, 4, 0.1), (5, 0, -0.05))
box("Rug", (1.2, 2, 0.012), (1.6, 0, 0.006))
box("Step plate", (1.5, 2, 0.15), (3.6, 0, 0.075))
box("Door Sill", (0.4, 2, 0.02), (5.2, 0, 0.01))
r = box("Ramp", (2.0, 2, 0.05), (7.2, 0, 0.0), (0, -math.radians(10), 0))
# armature: root > hips > thigh > shin, IK targets IK_foot.L/R (feet are children of the IK bones)
arm = bpy.data.armatures.new("TestRig"); rig = bpy.data.objects.new("TestRig", arm); sc.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig; bpy.ops.object.mode_set(mode="EDIT")
eb = arm.edit_bones
root = eb.new("root"); root.head, root.tail = (0, 0, 0), (0, 0.3, 0)
hips = eb.new("hips"); hips.head, hips.tail = (0, 0, 0.9), (0, 0, 1.1); hips.parent = root
for s, y in (("L", 0.12), ("R", -0.12)):
    th = eb.new(f"thigh.{s}"); th.head, th.tail = (0, y, 0.9), (0.02, y, 0.5); th.parent = hips
    sh = eb.new(f"shin.{s}"); sh.head, sh.tail = (0.02, y, 0.5), (0, y, 0.1); sh.parent = th; sh.use_connect = True
    ik = eb.new(f"IK_foot.{s}"); ik.head, ik.tail = (0, y, 0.1), (0.15, y, 0.1); ik.parent = root
    ft = eb.new(f"foot.{s}"); ft.head, ft.tail = (0, y, 0.1), (0.15, y, 0.1); ft.parent = ik
bpy.ops.object.mode_set(mode="POSE")
for s in "LR":
    c = rig.pose.bones[f"shin.{s}"].constraints.new("IK"); c.target = rig; c.subtarget = f"IK_foot.{s}"; c.chain_count = 2
bpy.ops.object.mode_set(mode="OBJECT")
for s, y in (("L", 0.12), ("R", -0.12)):
    o = box(f"foot_part.{s}", (0.26, 0.11, 0.1), (0.05, y, 0.05))
    o.parent = rig; o.parent_type = "BONE"; o.parent_bone = f"foot.{s}"
    o.matrix_world = Matrix.Translation((0.05, y, 0.05)); o["rig_bone"] = f"foot.{s}"
# a flat-ground walk: the cycle knows nothing about the floor (as a library motion wouldn't)
sc.frame_start, sc.frame_end = 1, 240
stride, speed = 0.7, 1.0 / 24 * 1.2
for f in range(1, 241):
    x = (f - 1) * speed
    rig.location = (x, 0, 0); rig.keyframe_insert("location", frame=f)
    for s, ph in (("L", 0.0), ("R", 0.5)):
        u = ((x / stride) + ph) % 1.0
        n = math.floor((x / stride) + ph)
        if u < 0.6:   # stance: the foot stays put in the world
            wx = (n + 0.0) * stride + 0.3 - ph * stride
            wz = 0.0
        else:         # swing
            k = (u - 0.6) / 0.4
            wx = (n + k) * stride + 0.3 - ph * stride
            wz = 0.08 * math.sin(math.pi * k)
        pb = rig.pose.bones[f"IK_foot.{s}"]
        pb.location = (0, 0, 0)
        bpy.context.view_layer.update()
        rest = pb.bone.head_local
        pb.location = (wx - x - rest.x, wz, 0)  # bone space: x along the bone, y = up? solved below
        bpy.context.view_layer.update()
        # put the bone where we want in world space directly
        M = rig.matrix_world.inverted() @ Matrix.Translation((wx, rest.y, 0.1 + wz))
        pb.matrix = M @ pb.bone.matrix_local.to_3x3().to_4x4()
        pb.keyframe_insert("location", frame=f); pb.keyframe_insert("rotation_quaternion", frame=f)
before = F.audit(rig, sc, (1, 240))
print("BEFORE", before["bad_frames"], {s: (v["worst_sink_mm"], v["worst_float_mm"], v["planted_frames"]) for s, v in before["feet"].items()})
pl = F.Planter(rig, sc)
for f in range(1, 241):
    sc.frame_set(f)
    pl.plant(key=True, frame=f)
after = F.audit(rig, sc, (1, 240))
print("AFTER", after["bad_frames"], {s: (v["worst_sink_mm"], v["worst_float_mm"], v["planted_frames"], v["no_floor"]) for s, v in after["feet"].items()})
for b in after["bad"][:12]:
    print("  ", b)
# footstep hook: one call per landing, with the surface it landed on
got = []
F.ON_PLANT.append(lambda rig, side, p, n, v, ob: got.append((side, ob.name if ob else None)))
pl2 = F.Planter(rig, sc)
for f in range(1, 241):
    sc.frame_set(f)
    pl2.plant()
print("LANDINGS", len(got), sorted({o for _, o in got if o}))
