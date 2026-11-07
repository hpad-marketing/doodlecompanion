"""A small stand-in biped with the Droid Kit contract (IK_foot.L/R, rigid parts with rig_bone)
and an in-place "Walk cycle" made on flat ground, so the floor tests run without the real droids."""
import math
import bpy
from mathutils import Vector, Matrix


def _box(sc, name, size, loc):
    me = bpy.data.meshes.new(name)
    sx, sy, sz = (s / 2 for s in size)
    v = [(x, y, z) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    o = bpy.data.objects.new(name, me)
    sc.collection.objects.link(o)
    o.location = loc
    return o


def make_biped(sc, name="Test Biped", hip=0.9, stride=0.62, cycle=24):
    """Faces -Y like the droids. Returns the rig; its parts are bone children."""
    arm = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, arm)
    sc.collection.objects.link(rig)
    rig["sb_droid"] = 1
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    root = eb.new("root"); root.head, root.tail = (0, 0, 0), (0, 0.3, 0)
    hips = eb.new("hips"); hips.head, hips.tail = (0, 0, hip), (0, 0, hip + 0.3); hips.parent = root
    for s, x in (("L", 0.12), ("R", -0.12)):
        th = eb.new(f"thigh.{s}"); th.head, th.tail = (x, 0, hip), (x, -0.02, 0.5); th.parent = hips
        sh = eb.new(f"shin.{s}"); sh.head, sh.tail = (x, -0.02, 0.5), (x, 0, 0.1); sh.parent = th; sh.use_connect = True
        ik = eb.new(f"IK_foot.{s}"); ik.head, ik.tail = (x, 0, 0.1), (x, -0.15, 0.1); ik.parent = root
        ft = eb.new(f"foot.{s}"); ft.head, ft.tail = (x, 0, 0.1), (x, -0.15, 0.1); ft.parent = ik
    bpy.ops.object.mode_set(mode="POSE")
    for s in "LR":
        c = rig.pose.bones[f"shin.{s}"].constraints.new("IK")
        c.target, c.subtarget, c.chain_count = rig, f"IK_foot.{s}", 2
        c.pole_target, c.pole_subtarget, c.pole_angle = None, "", 0
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    parts = [("body", (0.42, 0.3, 0.5), (0, 0, hip + 0.2), "hips")]
    for s, x in (("L", 0.12), ("R", -0.12)):
        parts += [(f"thigh_part.{s}", (0.1, 0.1, 0.34), (x, -0.01, 0.7), f"thigh.{s}"),
                  (f"shin_part.{s}", (0.08, 0.08, 0.3), (x, -0.01, 0.3), f"shin.{s}"),
                  (f"foot_part.{s}", (0.11, 0.26, 0.08), (x, -0.05, 0.04), f"foot.{s}")]
    for pn, size, loc, bone in parts:
        o = _box(sc, f"{name} {pn}", size, loc)
        b = rig.data.bones[bone]
        pm = rig.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))  # bone parents sit at the tail
        o.parent, o.parent_type, o.parent_bone = rig, "BONE", bone
        o.matrix_parent_inverse = pm.inverted()
        o["rig_bone"] = bone
        o["sb_droid"] = 1
    # in-place cycle: stance feet slide back at walk speed, swing feet arc forward
    act = bpy.data.actions.new("Walk cycle")
    rig.animation_data_create()
    rig.animation_data.action = act
    # human-style: heel strike with the toes up, roll to flat, heel lifts and the foot
    # pivots on the toe at push-off, then one clean arc forward; the hips drop a little
    # at each contact and sway over the stance foot (weight shift)
    heel_y, toe_y = 0.08, -0.18
    for fr in range(cycle + 1):
        for s, ph in (("L", 0.0), ("R", 0.5)):
            u = (fr / cycle + ph) % 1.0
            pitch, pivot = 0.0, None
            if u < 0.6:
                y = stride * (0.5 - u / 0.6) * -1   # forward (-Y) at contact, back at toe-off
                z = 0.0
                if u < 0.1:                       # heel strike -> foot flat
                    pitch, pivot = -math.radians(14) * (1 - u / 0.1), heel_y
                elif u > 0.45:                    # heel off, roll onto the toe
                    pitch, pivot = math.radians(32) * ((u - 0.45) / 0.15), toe_y
            else:
                k = (u - 0.6) / 0.4
                y = -stride * (k - 0.5)
                z = 0.07 * math.sin(math.pi * k)
                # toe stays down off the push, then lifts for the reach to the next heel strike
                pitch = math.radians(32) * (1 - k) ** 2 - math.radians(14) * k ** 2
                pivot = toe_y if pitch > 0 else heel_y   # turn about whichever end is lowest
            pb = rig.pose.bones[f"IK_foot.{s}"]
            rest = pb.bone.matrix_local
            x = rest.translation.x
            M = Matrix.Translation(rest.translation + Vector((0, y, z))) @ rest.to_3x3().to_4x4()
            if pitch:
                pv = Vector((x, y + pivot, z))
                M = Matrix.Translation(pv) @ Matrix.Rotation(pitch, 4, "X") @ Matrix.Translation(-pv) @ M
            pb.matrix = M
            bpy.context.view_layer.update()
            pb.keyframe_insert("location", frame=fr + 1)
            pb.keyframe_insert("rotation_quaternion", frame=fr + 1)
        u = fr / cycle
        hp = rig.pose.bones["hips"]
        hp.location = (0.0, 0.0, 0.0)
        # bone-local axes of the hips bone (it points up): x = sideways, y = up, z = forward
        hp.location = (0.025 * math.cos(2 * math.pi * u), -0.02 * (0.5 + 0.5 * math.cos(4 * math.pi * u)), 0.0)
        hp.keyframe_insert("location", frame=fr + 1)
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
    return rig
