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
    if pb is None:
        return rig.matrix_world.translation.copy()
    if "ik_fk" in pb.keys() and _fk_live(rig, pb):
        m = _fk_matrix(rig, pb)      # the limb is in FK: the handle sits on the visible hand
        if m is not None:
            return rig.matrix_world @ m.translation
    return rig.matrix_world @ pb.head


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


LIMB = {"hand": ("upper_arm", "forearm", "hand"), "foot": ("thigh", "shin", "foot")}


def _limb_switch(rig, stem, side, ik):
    """Blend a limb's deform bones to their IK (1) or FK (0) chain. Works whether the rig
    drives this from its ik_fk property or not (RX-07 keeps the influences static)."""
    names = {f"DEF-{p}{side}" for p in LIMB[stem]}
    for pb in rig.pose.bones:
        if pb.name not in names:
            continue
        for c in pb.constraints:
            if c.type in ("COPY_TRANSFORMS", "COPY_ROTATION") and c.name.upper() in ("IK", "FK"):
                c.influence = ik if c.name.upper() == "IK" else 1.0 - ik


def _ensure_ik(rig, pb):
    """A limb in FK ignores its IK handle: snap the handle onto the hand and switch to IK,
    so dragging the hand works and nothing jumps."""
    if "ik_fk" not in pb.keys() or float(pb["ik_fk"]) >= 0.5 and not _fk_live(rig, pb):
        return
    m = _fk_matrix(rig, pb)
    if m is not None:
        pb.matrix = m
    side = pb.name[-2:] if pb.name[-2:].lower() in (".l", ".r") else ""
    pb["ik_fk"] = 1.0
    _limb_switch(rig, "hand" if "hand" in pb.name.lower() else "foot", side, 1.0)
    bpy.context.view_layer.update()


def fk_arms(rig):
    """Hand the arms back to FK (the droid's own motions animate its FK arms)."""
    for pb in rig.pose.bones:
        if "ik_fk" in pb.keys() and "hand" in pb.name.lower():
            side = pb.name[-2:] if pb.name[-2:].lower() in (".l", ".r") else ""
            pb["ik_fk"] = 0.0
            _limb_switch(rig, "hand", side, 0.0)


def _fk_matrix(rig, pb):
    """Where the IK handle would sit on the hand/foot as the FK chain holds it now."""
    side = pb.name[-2:] if pb.name[-2:].lower() in (".l", ".r") else ""
    stem = "hand" if "hand" in pb.name.lower() else "foot"
    for name in (f"DEF-{stem}{side}", f"FK-{stem}{side}", f"{stem}{side}"):
        src = rig.pose.bones.get(name)
        if src is not None:
            # keep the handle's own offset from the hand (it may sit at the palm, not the wrist)
            off = rig.data.bones[src.name].matrix_local.inverted() @ rig.data.bones[pb.name].matrix_local
            return src.matrix @ off
    return None


def _fk_live(rig, pb):
    side = pb.name[-2:] if pb.name[-2:].lower() in (".l", ".r") else ""
    stem = "hand" if "hand" in pb.name.lower() else "foot"
    d = rig.pose.bones.get(f"DEF-{LIMB[stem][0]}{side}")
    c = d.constraints.get("IK") if d else None
    return c is not None and c.influence < 0.5


def move_to(rig, h, p, key=True):
    p = Vector(p)
    if h.bone == "*":
        rig.location += p - rig.matrix_world.translation
    else:
        pb = rig.pose.bones[h.bone]
        _ensure_ik(rig, pb)
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
        if "ik_fk" in pb.keys() and rig.data.bones.get(pb.name) and not rig.data.bones[pb.name].parent or "ik_fk" in pb.keys():
            pb["ik_fk"] = 0.0       # presets pose through the IK handles: _ensure_ik snaps and switches
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


def _parts(rig):
    return [o for o in rig.children_recursive if o.type in {"MESH", "CURVE"}]


def _near(rig, hh):
    c = rig.matrix_world.translation
    out = []
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or o is rig or o.parent is rig or o in rig.children_recursive or o.get("sb_widget"):
            continue
        if (o.matrix_world.translation - c).length < hh * 2.5 + max(o.dimensions) * 0.5:
            out.append(o)
    return out


def _hits(rig, parts, others):
    from . import collide
    bpy.context.view_layer.update()
    return {tuple(sorted(h[:2])) for h in collide.audit_objects(parts + others, 0.0015, only=parts)}


def _pose(rig, offs, look, hh, out, scale, keyframe):
    rest(rig)
    bpy.context.view_layer.update()
    basis = rig.matrix_world.to_3x3().normalized()
    for k in sorted(offs, key=lambda k: k != "body"):   # body first, the hands follow it
        h = get(rig, k)
        if h is None:
            continue
        x, y, z = offs[k]
        if k == "hand_l":
            x += out          # its left is +X
        elif k == "hand_r":
            x -= out
        start = point(rig, h)
        move_to(rig, h, start + basis @ Vector((x * scale, y * scale, z * scale)) * hh, key=keyframe)
        bpy.context.view_layer.update()
    if look and (look[0] or look[1]):
        h = get(rig, "head")
        if h is not None:
            if look[0]:
                turn(rig, h, math.radians(look[0] * scale), key=keyframe)
            if look[1]:
                tilt(rig, h, math.radians(look[1] * scale), key=keyframe)
            bpy.context.view_layer.update()


# hands swing out from the body first, then the pose shrinks, until nothing passes through anything
TRIES = [(o, 1.0) for o in (0.0, 0.06, 0.12, 0.18, 0.26)] + [(0.18, f) for f in (0.85, 0.7, 0.55, 0.4)]


def apply(rig, key, keyframe=True, safe=True):
    """Pose from a preset. With safe=True the pose is checked for intersections (the droid
    against itself and the set around it) and eased until it is clean: the hard rule."""
    lab, offs, look = POSES[key]
    rest(rig)
    if key == "neutral":
        fk_arms(rig)
    bpy.context.view_layer.update()
    if key == "neutral" or not offs and not look:
        return lab
    hh = height(rig)
    if not safe:
        _pose(rig, offs, look, hh, 0.0, 1.0, keyframe)
        return lab
    parts, others = _parts(rig), _near(rig, hh)
    base = _hits(rig, parts, others)
    for out, scale in TRIES:
        _pose(rig, offs, look, hh, out, scale, False)
        if not (_hits(rig, parts, others) - base):
            if keyframe:
                _pose(rig, offs, look, hh, out, scale, True)
            return lab if (out, scale) == (0.0, 1.0) else f"{lab} (eased so nothing touches)"
    rest(rig)
    bpy.context.view_layer.update()
    return f"{lab} doesn't fit here without touching something: left at rest"
