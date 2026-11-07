"""Droid posing made simple: move a handle to a point, turn a droid or its head,
and one-click pose presets that work on every droid (a preset only touches the
handles a droid has, so the armless porter still crouches and looks around).

    handles(rig)              -> [Handle(key, label, bone, side)]   bone "*" = the whole droid
    point(rig, h)             world position of a handle
    move_to(rig, h, p)        put a handle at world point p
    turn(rig, h, angle)       turn the droid ("*") or a bone about the world up axis
    apply(rig, preset_key)    pose a droid from a preset (rest first, then offsets)
"""
import math

import bpy
from mathutils import Matrix, Vector

from . import rigui


class Handle:
    __slots__ = ("key", "label", "bone", "side")

    def __init__(self, key, label, bone, side):
        self.key, self.label, self.bone, self.side = key, label, bone, side


# key, label, side (colour), bone names to look for ("*" = move the droid object)
SPEC = (
    ("whole", "Whole droid", "C", ("*",)),
    ("body", "Body", "C", ("cog", "torso", "chassis", "body", "hips")),
    ("head", "Head", "C", ("head", "sensor", "neck")),
    ("hand_l", "Left hand", "L", ("ik-hand.l", "hand_ik.l", "ik_hand.l", "fk-hand.l", "grip.l")),
    ("hand_r", "Right hand", "R", ("ik-hand.r", "hand_ik.r", "ik_hand.r", "fk-hand.r", "grip.r")),
    ("foot_l", "Left foot", "L", ("ik_foot.l", "ik-foot.l", "foot_ik.l")),
    ("foot_r", "Right foot", "R", ("ik_foot.r", "ik-foot.r", "foot_ik.r")),
    ("scoop", "Scoop", "C", ("scoop_lift",)),
)
TURNABLE = ("whole", "head")


def handles(rig):
    out = []
    for key, label, side, keys in SPEC:
        bone = "*" if keys == ("*",) else rigui.find(rig, keys)
        if bone:
            out.append(Handle(key, label, bone, side))
    return out


def get(rig, key):
    return next((h for h in handles(rig) if h.key == key), None)


def height(rig):
    try:
        from . import castfit
        return max(0.3, castfit.height(rig))
    except Exception:
        return 1.5


def point(rig, h):
    if h.bone == "*":
        return rig.matrix_world.translation.copy()
    pb = rig.pose.bones.get(h.bone)
    return rig.matrix_world @ pb.head if pb else rig.matrix_world.translation.copy()


def _key(rig, h):
    ts = bpy.context.scene.tool_settings
    if not ts.use_keyframe_insert_auto:
        return
    f = bpy.context.scene.frame_current
    if h.bone == "*":
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_euler", frame=f)
        return
    pb = rig.pose.bones[h.bone]
    pb.keyframe_insert("location", frame=f)
    pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)


def move_to(rig, h, p, key=True):
    p = Vector(p)
    if h.bone == "*":
        rig.location += p - rig.matrix_world.translation
    else:
        pb = rig.pose.bones[h.bone]
        d = rig.matrix_world.inverted().to_3x3() @ (p - rig.matrix_world @ pb.head)
        m = pb.matrix.copy()
        m.translation += d
        pb.matrix = m
    if key:
        _key(rig, h)


def turn(rig, h, angle, key=True):
    """Turn about the world up axis by angle (radians)."""
    if h.bone == "*":
        rig.rotation_euler.z += angle
    else:
        pb = rig.pose.bones[h.bone]
        to_arm = rig.matrix_world.inverted().to_3x3()
        r = (to_arm @ Matrix.Rotation(angle, 3, "Z") @ rig.matrix_world.to_3x3()).normalized().to_4x4()
        pv = pb.head.copy()
        pb.matrix = Matrix.Translation(pv) @ r @ Matrix.Translation(-pv) @ pb.matrix
    if key:
        _key(rig, h)


def tilt(rig, h, angle, key=True):
    """Nod a bone about the droid's own side axis (look up / down, lean)."""
    pb = rig.pose.bones[h.bone]
    side = rig.matrix_world.to_3x3() @ Vector((1, 0, 0))
    to_arm = rig.matrix_world.inverted().to_3x3()
    r = (to_arm @ Matrix.Rotation(angle, 3, side.normalized()) @ rig.matrix_world.to_3x3()).normalized().to_4x4()
    pv = pb.head.copy()
    pb.matrix = Matrix.Translation(pv) @ r @ Matrix.Translation(-pv) @ pb.matrix
    if key:
        _key(rig, h)


def rest(rig):
    for pb in rig.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


# ------------------------------------------------------------------ presets
# Offsets are in droid heights, in the droid's own frame: x to its left, y forward
# (droids face -Y, so forward is -y in the rig), z up. "look": (turn, nod) in degrees.
POSES = {
    "neutral": ("Neutral", {}, None),
    "wave": ("Wave", {"hand_r": (-0.05, -0.08, 0.42)}, (10, 5)),
    "point": ("Point", {"hand_r": (0.0, -0.40, 0.22)}, (0, 0)),
    "hands_up": ("Hands up", {"hand_l": (-0.04, -0.05, 0.40), "hand_r": (0.04, -0.05, 0.40)}, (0, 10)),
    "shrug": ("Shrug", {"hand_l": (0.10, -0.12, 0.10), "hand_r": (-0.10, -0.12, 0.10), "body": (0, 0, -0.01)}, (0, -8)),
    "think": ("Thinking", {"hand_r": (0.12, -0.15, 0.30)}, (-12, -10)),
    "reach": ("Reach out", {"hand_l": (0.0, -0.35, 0.08), "hand_r": (0.0, -0.35, 0.08), "body": (0, -0.04, -0.03)}, (0, -10)),
    "crouch": ("Crouch", {"body": (0, 0.02, -0.12)}, (0, 8)),
    "lean_in": ("Lean in", {"body": (0, -0.07, -0.02)}, (0, -6)),
    "lean_back": ("Lean back", {"body": (0, 0.06, -0.01)}, (0, 12)),
    "look_left": ("Look left", {}, (35, 0)),
    "look_right": ("Look right", {}, (-35, 0)),
    "look_up": ("Look up", {}, (0, 22)),
    "look_down": ("Look down", {}, (0, -22)),
    "step": ("Mid step", {"foot_r": (0.0, -0.18, 0.06), "body": (0, -0.05, 0)}, (0, 0)),
    "scoop_up": ("Scoop up", {"scoop": (0, 0, 0.12)}, (0, 0)),
}


def poses_for(rig):
    have = {h.key for h in handles(rig)}
    out = []
    for k, (lab, offs, look) in POSES.items():
        if all(x in have for x in offs) and (offs or (look and "head" in have) or k == "neutral"):
            out.append((k, lab))
    return out


def apply(rig, key, keyframe=True):
    lab, offs, look = POSES[key]
    rest(rig)
    bpy.context.view_layer.update()
    hh = height(rig)
    basis = rig.matrix_world.to_3x3().normalized()
    order = sorted(offs, key=lambda k: k != "body")   # body first, the hands follow it
    for k in order:
        h = get(rig, k)
        if h is None:
            continue
        x, y, z = offs[k]
        start = point(rig, h)
        move_to(rig, h, start + basis @ Vector((x, y, z)) * hh, key=keyframe)
        bpy.context.view_layer.update()
    if look and (look[0] or look[1]):
        h = get(rig, "head")
        if h is not None:
            if look[0]:
                turn(rig, h, math.radians(look[0]), key=keyframe)
            if look[1]:
                tilt(rig, h, math.radians(look[1]), key=keyframe)
            bpy.context.view_layer.update()
    return lab
