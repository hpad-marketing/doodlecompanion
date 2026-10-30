"""Motions: Doodle Studio track keyframes -> keys on BUNNY_rig, and back to the library.

Ported Doodle Studio motions stay in their native form (track values per frame,
plus the face beats), so they never break when the rig is rebuilt: on insert
they go through the 3D Bunny's own ds_map.apply_pose, exactly like ds_bridge.
Motions made in Blender are stored as Blender actions.
"""
import json
import math
import os

import bpy

from . import index, paths

CATEGORICAL = {'expression', 'gaze', 'mouth', 'blink'}
FACE_KEYS = {'expression': 'expression', 'gaze': 'gaze', 'mouth': 'speech_mouth', 'blink': 'blink'}
# layering hints that only mean something in the 2D app
IGNORE = {'headNear', 'handNearL', 'handNearR'}
CAMERA = {'view', 'camFov', 'camZoom', 'camX', 'camY'}


def smooth(p):
    return p * p * (3 - 2 * p)


def track_keys(motion):
    keys = {}
    for f, pose in motion['poses']:
        for k, v in pose.items():
            keys.setdefault(k, []).append((float(f), v))
    for k in keys:
        keys[k].sort()
    return keys


def sample(keys, track, f, linear=()):
    ks = keys[track]
    if f <= ks[0][0]:
        return ks[0][1]
    if f >= ks[-1][0]:
        return ks[-1][1]
    for (fa, a), (fb, b) in zip(ks, ks[1:]):
        if fa <= f < fb:
            if track in CATEGORICAL:
                return a
            p = (f - fa) / (fb - fa)
            p = p if track in linear else smooth(p)
            d = b - a
            if track == 'turn':
                d = ((d + 180) % 360 + 360) % 360 - 180
            return a + d * p
    return ks[-1][1]


def key_frames(motion, keys, every=0):
    fs = sorted({f for k in keys.values() for f, _ in k})
    n = int(motion.get('frames', fs[-1] if fs else 0))
    if every:
        fs = sorted(set(fs) | set(range(0, n + 1, every)))
    # quaternions can't swing more than ~90 degrees between keys: add in-betweens for big turns
    if 'turn' in keys:
        out = [fs[0]]
        for a, b in zip(fs, fs[1:]):
            ta, tb = sample(keys, 'turn', a), sample(keys, 'turn', b)
            steps = int(abs(((tb - ta + 180) % 360) - 180) // 45)
            out += [a + (b - a) * i / (steps + 1) for i in range(1, steps + 1)] + [b]
        fs = out
    return fs


def rig():
    arm = bpy.data.objects.get('BUNNY_rig')
    if not arm:
        raise RuntimeError('No BUNNY_rig in this file. Open or link Bunny3D.blend first.')
    return arm


def rig_meta():
    t = bpy.data.texts.get('DOODLE_STUDIO_RIG.json')
    return json.loads(t.as_string()) if t else None


def ds_motion(item_id):
    """Track data for a Doodle Studio-format motion. Rows may name their own json in 'file'
    (motions/mocap.json, motions/performance.json ...); the default is doodle_studio.json."""
    it = index.get(item_id) or {}
    f = it.get('file') or ''
    rel = f if f.endswith('.json') else 'motions/doodle_studio.json'
    return index.blob(rel)['motions'][item_id]


def rot_path(b):
    """Key path for a bone's rotation in whatever mode the rig uses (v2 ears are Euler)."""
    return {'QUATERNION': 'rotation_quaternion', 'AXIS_ANGLE': 'rotation_axis_angle'}.get(b.rotation_mode, 'rotation_euler')


def set_rot(b, q):
    if b.rotation_mode == 'QUATERNION':
        b.rotation_quaternion = q
    elif b.rotation_mode == 'AXIS_ANGLE':
        ax, ang = q.to_axis_angle()
        b.rotation_axis_angle = (ang, *ax)
    else:
        b.rotation_euler = q.to_euler(b.rotation_mode)


def _key_pose(arm, frame, bones, face=True):
    for b in bones:
        b.keyframe_insert(rot_path(b), frame=frame, group=b.name)
        b.keyframe_insert('location', frame=frame, group=b.name)
        b.keyframe_insert('scale', frame=frame, group=b.name)
    fb = arm.pose.bones.get('face')
    if face and fb is not None:
        for k in ('expression', 'gaze', 'speech_mouth', 'blink'):
            if k in fb.keys():
                fb.keyframe_insert(f'["{k}"]', frame=frame, group='face')


def _fcurves(arm):
    ad = arm.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        return list(act.fcurves)
    except Exception:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out += list(bag.fcurves)
        return out


def insert_ds(item_id, start=None, include_camera=False, fix_clipping=True, mirror=False):
    """Key a Doodle Studio motion onto Bunny from `start` (default: playhead)."""
    arm = rig()
    meta = rig_meta()
    ds_map = paths.bunny_module('ds_map')
    sc = bpy.context.scene
    start = sc.frame_current if start is None else start
    m = ds_motion(item_id)
    keys = track_keys(m)
    for k in list(keys):
        if k in IGNORE or (k in CAMERA and not include_camera):
            keys.pop(k)
    if 'y' in keys and 'bodyY' not in keys:
        keys['bodyY'] = keys.pop('y')
    linear = set(m.get('linearTracks', []))
    frames = key_frames(m, keys, every=2 if linear else 0)
    bones = [b for b in arm.pose.bones if not b.name.startswith(('MCH-', 'DEF-'))]
    settings = bpy.data.objects.get('BUNNY_settings')
    collision = None
    objs = ear_sets = None
    if fix_clipping:
        try:
            collision = paths.bunny_module('collision')
            objs = collision.objects()
            ear_sets = collision.ear_vertex_sets(objs['head'])
        except Exception as e:  # rig mid-rebuild: still insert, just unsolved
            print('Doodle Library: clipping solver unavailable:', e)
            collision = None
    apply = lambda v: ds_map.apply_pose(arm, meta['controls'], v, meta['S'], None)
    rep = None
    fixes = 0
    for f in frames:
        vals = {k: sample(keys, k, f, linear) for k in keys}
        if mirror:
            vals = mirror_values(vals)
        if collision:
            vals, rep = collision.solve_frame(apply, vals, objs, ear_sets, hint=rep)
            fixes += bool(rep.get('arm_fix') or rep.get('ear_fix') is not None)
        else:
            apply(vals)
        _key_pose(arm, start + f, bones, face=any(k in keys for k in CATEGORICAL))
        if include_camera and sc.camera:
            ds_map.apply_camera(sc.camera, vals, meta['S'], 4.145 * meta['S'], base_ortho=17.07 * meta['S'])
            sc.camera.keyframe_insert('location', frame=start + f)
            sc.camera.keyframe_insert('rotation_euler', frame=start + f)
    for fc in _fcurves(arm):
        for kp in fc.keyframe_points:
            if not (start <= kp.co[0] <= start + frames[-1]):
                continue
            if fc.data_path.startswith('pose.bones["face"]'):
                kp.interpolation = 'CONSTANT'
            else:
                kp.interpolation = 'LINEAR' if linear else 'BEZIER'
                kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    index.mark_used(item_id)
    from .faces import fit_speech
    fitted = fit_speech(arm, (start, start + frames[-1]))  # speech mouths that fit the story face
    return {'frames': int(frames[-1]), 'keys': len(frames), 'clip_fixes': fixes, 'speech_fitted': fitted}


MIRROR_PAIRS = [('armL', 'armR'), ('armLForward', 'armRForward'), ('elbowL', 'elbowR'), ('wristL', 'wristR'),
                ('legL', 'legR'), ('legLOut', 'legROut'), ('kneeL', 'kneeR'), ('footL', 'footR'),
                ('earLFold', 'earRFold'), ('earLForward', 'earRForward')]
MIRROR_NEG = {'turn', 'headYaw', 'rot', 'bodyTilt', 'torsoTwist', 'bodyRot', 'bodyX'}


def mirror_values(v):
    out = dict(v)
    for a, b in MIRROR_PAIRS:
        if a in v or b in v:
            out[a], out[b] = v.get(b, 0.0), v.get(a, 0.0)
    for k in MIRROR_NEG:
        if k in v:
            out[k] = -v[k]
    g = v.get('gaze')
    if g is not None:  # 1 Left <-> 2 Right, 5<->6, 7<->8
        out['gaze'] = {1: 2, 2: 1, 5: 6, 6: 5, 7: 8, 8: 7}.get(int(g), g)
    return out


# ------------------------------------------------------------------ Blender actions
def insert_action(item, start=None):
    """Append a saved action and copy its keys onto Bunny at the playhead."""
    arm = rig()
    sc = bpy.context.scene
    start = sc.frame_current if start is None else start
    path = paths.lib_path(item['file'])
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.actions = [item['datablock']]
    act = dst.actions[0]
    try:
        src_curves = list(act.fcurves)
    except Exception:
        src_curves = [fc for l in act.layers for s in l.strips for b in s.channelbags for fc in b.fcurves]
    f0 = min((kp.co[0] for fc in src_curves for kp in fc.keyframe_points), default=0)
    arm.animation_data_create()
    if not arm.animation_data.action:
        # first motion on a fresh rig: key the rest pose once so an action exists
        arm.keyframe_insert('location', frame=start)
    target = arm.animation_data.action
    n = 0
    for fc in src_curves:
        try:
            dfc = target.fcurves.find(fc.data_path, index=fc.array_index) or \
                target.fcurves.new(fc.data_path, index=fc.array_index, action_group=fc.group.name if fc.group else '')
        except Exception:
            arm.keyframe_insert(fc.data_path, index=fc.array_index, frame=start)
            dfc = [c for c in _fcurves(arm) if c.data_path == fc.data_path and c.array_index == fc.array_index][0]
        for kp in fc.keyframe_points:
            k = dfc.keyframe_points.insert(kp.co[0] - f0 + start, kp.co[1], options={'FAST'})
            k.interpolation = kp.interpolation
            n += 1
        dfc.update()
    bpy.data.actions.remove(act)
    index.mark_used(item['id'])
    return {'keys': n}


def save_action(name, frame_range=None, category='My motions', tags=()):
    """Store Bunny's current action (or a frame range of it) in the library."""
    arm = rig()
    if not arm.animation_data or not arm.animation_data.action:
        raise RuntimeError('Bunny has no animation to save.')
    src = arm.animation_data.action
    act = src.copy()
    if frame_range:
        a, b = frame_range
        try:
            curves = list(act.fcurves)
        except Exception:
            curves = []
        for fc in curves:
            for kp in reversed(list(fc.keyframe_points)):
                if not (a <= kp.co[0] <= b):
                    fc.keyframe_points.remove(kp)
    item_id = index.unique_id('motion-' + name)
    act.name = 'DSL ' + name
    act['dsl_id'] = item_id
    act.use_fake_user = True
    rel = os.path.join('motions', 'user', item_id + '.blend')
    os.makedirs(os.path.dirname(paths.lib_path(rel)), exist_ok=True)
    bpy.data.libraries.write(paths.lib_path(rel), {act}, fake_user=True, compress=True)
    fr = act.frame_range
    bpy.data.actions.remove(act)
    src['dsl_id'] = item_id
    return index.add({'id': item_id, 'name': name, 'category': 'motion', 'kind': 'action', 'sub': category,
                      'file': rel.replace('\\', '/'), 'datablock': 'DSL ' + name, 'tags': list(tags),
                      'source': 'blender', 'frames': int(fr[1] - fr[0])})
