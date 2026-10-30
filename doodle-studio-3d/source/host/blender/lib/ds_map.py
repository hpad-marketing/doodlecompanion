"""Doodle Studio track values -> Bunny rig pose (and camera).

Doodle Studio rotates each native bone about the world X/Y/Z axes of the rest
pose, around the bone's pivot, in the order its controls are listed. A Blender
pose bone rotates in its own rest frame, so each Doodle Studio rotation R is
converted with  q_local = B0^-1 * R * B0  (B0 = the bone's rest orientation).
Because every bone's pivot equals its Doodle Studio pivot, positions match.
"""
import math
from mathutils import Matrix, Vector, Quaternion

AXES = {1: 'X', 2: 'Y', 3: 'Z'}

# Doodle Studio native bone -> control bone here
BONE_MAP = {
    'ROOT': 'body', 'TORSO': 'torso', 'HEAD': 'head',
    'EAR.L': 'ear.L', 'EAR.R': 'ear.R',
    'UPPER_ARM.L': 'upper_arm_fk.L', 'FOREARM.L': 'forearm_fk.L', 'WRIST.L': 'hand_fk.L',
    'UPPER_ARM.R': 'upper_arm_fk.R', 'FOREARM.R': 'forearm_fk.R', 'WRIST.R': 'hand_fk.R',
    'THIGH.L': 'thigh_fk.L', 'SHIN.L': 'shin_fk.L', 'ANKLE.L': 'foot_fk.L',
    'THIGH.R': 'thigh_fk.R', 'SHIN.R': 'shin_fk.R', 'ANKLE.R': 'foot_fk.R',
}

# Doodle Studio control name -> track id (BunnyRig.ids)
TRACK_IDS = {
    "TURN 360": "turn", "VIEW Above": "view", "HEAD Yaw": "headYaw", "HEAD Nod": "headNod", "HEAD Tilt": "rot",
    "BODY Tilt": "bodyTilt", "TORSO Bow": "torsoBow", "TORSO Twist": "torsoTwist",
    "ARM L Raise": "armL", "ARM L Forward": "armLForward", "ELBOW L Bend": "elbowL", "WRIST L Roll": "wristL",
    "LEG L Lift": "legL", "LEG L Out": "legLOut", "KNEE L Bend": "kneeL", "FOOT L Roll": "footL",
    "ARM R Raise": "armR", "ARM R Forward": "armRForward", "ELBOW R Bend": "elbowR", "WRIST R Roll": "wristR",
    "LEG R Lift": "legR", "LEG R Out": "legROut", "KNEE R Bend": "kneeR", "FOOT R Roll": "footR",
    "EAR L Fold": "earLFold", "EAR L Forward": "earLForward", "EAR R Fold": "earRFold", "EAR R Forward": "earRForward",
    "STYLE Line boil": "lineBoil", "BODY Breath": "breath", "FACE Speech mode": "speechMode",
}

STAGE_PER_DS = 40.0  # 1 Doodle Studio unit = 100 source px = 40 stage units
BODY_UNIT = 100 * 0.00205066345 * 490 * .4  # rigBodyOffset unit


def ds_world_rotation(controls, values, ds_bone):
    """3x3 rotation Doodle Studio applies at a native bone (degrees in values)."""
    M = Matrix.Identity(3)
    for c in controls:
        if c['owner'] != ds_bone:
            continue
        tid = TRACK_IDS.get(c['name'])
        deg = float(values.get(tid, 0.0)) if tid else 0.0
        deg = max(c['min'], min(c['max'], deg))  # Doodle Studio's joint range
        if deg:
            M = M @ Matrix.Rotation(math.radians(deg * c['sign']), 3, AXES[c['axis']])
    return M


def hinge_offset(radii, e1, e2, axis, M):
    """Pivot (from the bone head, rest space) at the edge of the ear base on the
    side the ear bends toward; zero when it doesn't bend."""
    tip = M @ axis
    bend = tip - axis * tip.dot(axis)
    x, y = bend.dot(e1), bend.dot(e2)
    if x * x + y * y < 1e-12:
        return Vector((0, 0, 0))
    ang = math.atan2(y, x) % (2 * math.pi)
    f = ang / (2 * math.pi) * len(radii)
    i = int(f) % len(radii)
    r = radii[i] + (radii[(i + 1) % len(radii)] - radii[i]) * (f - int(f))
    return (e1 * math.cos(ang) + e2 * math.sin(ang)) * r


def hinge_location(pose_bone, M):
    """Pose location that turns a rotation about the bone head into the same
    rotation about the ear's hinge."""
    b = pose_bone.bone
    B0 = b.matrix_local.to_3x3()
    axis = (B0 @ Vector((0, 1, 0))).normalized()
    p = hinge_offset(list(pose_bone['hinge_r']), Vector(pose_bone['hinge_e1']), Vector(pose_bone['hinge_e2']), axis, M)
    return B0.inverted() @ (p - M @ p)


def to_local(pose_bone, M):
    B0 = pose_bone.bone.matrix_local.to_3x3()
    return (B0.inverted() @ M @ B0).to_quaternion()


def set_rotation(pose_bone, q):
    """Write a local rotation in whatever rotation mode the bone uses."""
    if pose_bone.rotation_mode == 'QUATERNION':
        pose_bone.rotation_quaternion = q
    elif pose_bone.rotation_mode == 'AXIS_ANGLE':
        ax, ang = q.to_axis_angle()
        pose_bone.rotation_axis_angle = (ang, *ax)
    else:
        pose_bone.rotation_euler = q.to_euler(pose_bone.rotation_mode)


def rotation_path(pose_bone):
    return {'QUATERNION': 'rotation_quaternion', 'AXIS_ANGLE': 'rotation_axis_angle'}.get(pose_bone.rotation_mode, 'rotation_euler')


def apply_pose(arm, controls, values, S, settings=None, face_bone='face'):
    """Pose the rig from one frame of Doodle Studio track values (degrees)."""
    pb = arm.pose.bones
    for ds_bone, ctrl in BONE_MAP.items():
        M = ds_world_rotation(controls, values, ds_bone)
        set_rotation(pb[ctrl], to_local(pb[ctrl], M))
        if 'hinge_r' in pb[ctrl]:
            pb[ctrl].location = hinge_location(pb[ctrl], M)
    # app body motion: rotation about the hoodie base (Doodle Studio bodyRot)
    br = float(values.get('bodyRot', 0.0))
    pb['body_rot'].rotation_quaternion = to_local(pb['body_rot'], Matrix.Rotation(math.radians(br), 3, 'Y'))
    # whole-character turn and placement
    turn = float(values.get('turn', 0.0))
    x, y, d = (float(values.get(k, 0.0)) for k in ('bodyX', 'bodyY', 'depth'))
    root = pb['root']
    root.rotation_quaternion = to_local(root, Matrix.Rotation(math.radians(turn), 3, 'Z'))
    root.location = Vector((0, 0, 0))
    off = Vector((x / BODY_UNIT, d, -y / BODY_UNIT)) * S
    root.location = root.bone.matrix_local.to_3x3().inverted() @ off
    s = float(values.get('s', 1.0)) * float(arm.get('species_scale', 1.0))  # Frog 0.75: real size vs Bunny
    root.scale = (s, s, s)
    # breathing lifts the hoodie mass
    breath = max(0.0, min(1.0, float(values.get('breath', 0.0)) / 90.0))
    t = pb['torso']
    t.location = t.bone.matrix_local.to_3x3().inverted() @ (Vector((0, -.015 * breath, .07 * breath)) * S)
    # ear / eye-bump size: EAR Scale (100 = normal), EAR Squash (+ flattens, - stretches tall, volume kept)
    for side, k in (('L', 'earL'), ('R', 'earR')):
        e = pb.get(f'ear.{side}')
        if e is None:
            continue
        u = max(0.5, min(1.5, float(values.get(k + 'Scale', 100.0)) / 100.0))
        qm = 0.12 if arm.get('ear_width_lock') else 0.3  # past this the Frog bumps meet the eyes / Koala ears melt into the head
        q = max(-0.5, min(qm, float(values.get(k + 'Squash', 0.0)) / 100.0))
        w = u / math.sqrt(1.0 - q)
        e.scale = (min(w, 1.0) if arm.get('ear_width_lock') else w, u * (1.0 - q), w)
    # species nose (Koala): NOSE Wiggle -100..100 nudges it sideways, NOSE Sniff 0-100 lifts and puffs it
    n = pb.get('nose')
    if n is not None:
        wig = max(-1.0, min(1.0, float(values.get('noseWiggle', 0.0)) / 100.0))
        sn = max(0.0, min(1.0, float(values.get('noseSniff', 0.0)) / 100.0))
        n.location = n.bone.matrix_local.to_3x3().inverted() @ (Vector((0.06 * wig, 0, 0.05 * sn)) * S)
        n.scale = (1 + 0.12 * sn,) * 3
    # sitting leg reach (Doodle Studio 0-100 %)
    if 'leg_reach' in arm:
        arm['leg_reach'] = max(0.0, min(1.0, float(values.get('legReach', 0.0)) / 100.0))
    # face states
    f = pb.get(face_bone)
    if f is not None:
        for k, tid in (('expression', 'expression'), ('gaze', 'gaze'), ('speech_mouth', 'mouth'), ('blink', 'blink')):
            f[k] = int(round(float(values.get(tid, 0))))
    if settings is not None:
        if 'lineBoil' in values:
            settings['boil'] = max(0.0, min(1.0, float(values['lineBoil']) / 90.0))


def apply_camera(cam, values, S, pivot_z, base_ortho=None, distance=12.0, settings=None, ink_base=12.73):
    """VIEW Above orbits the camera (the room moves with it); camFov 0 = flat."""
    view = math.radians(float(values.get('view', 0.0)))
    fov = float(values.get('camFov', 0.0))
    zoom = float(values.get('camZoom', 1.0)) or 1.0
    pivot = Vector((0, 0, pivot_z))
    d = distance
    cam.location = pivot + Vector((0, -math.cos(view) * d, math.sin(view) * d))
    cam.rotation_euler = (math.pi / 2 - view, 0, 0)
    if fov <= 0:
        cam.data.type = 'ORTHO'
        if base_ortho:
            cam.data.ortho_scale = base_ortho / zoom
    else:
        cam.data.type = 'PERSP'
        cam.data.sensor_fit = 'AUTO'
        cam.data.angle = math.radians(min(fov, 170.0))
    if settings is not None:
        # Doodle Studio's camera zoom scales the drawing, ink included
        settings['ink_px'] = ink_base * zoom
    return zoom
