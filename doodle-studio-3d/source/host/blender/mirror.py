"""Live mirror between Doodle Studio 3D and an open Blender window.

ds_bridge.py builds the shot as usual (with --live: no render, no physics bakes, no rule
nudges) and then calls start(ctx). From then on, every 50 ms on Blender's main thread:

  app -> Blender   frame (playhead), pose (the current frame's values, shown at once),
                   shot (every frame's values plus item and set-piece placement: keys are
                   rewritten in bulk), rebuild (props added or removed, a new set, another
                   shot: the shot file is reopened and built again), bye
  Blender -> app   hello, frame, edit (pose controls, camera, items, set pieces, sun),
                   closed

Pose edits are read back from the rig's control bones (the same bones ds_map poses), so a
bone turned in Blender becomes Doodle Studio's own control values, inside its joint limits.
Two background threads talk to the app over its local server (127.0.0.1 only, with a token);
bpy is touched only from the timer.
"""
import json
import math
import os
import queue
import threading
import time
import urllib.request

import bpy
from mathutils import Matrix, Quaternion, Vector

import ds_map

TICK = 0.05
QUIET = 0.45        # seconds after the last Blender-side edit before app updates are applied
EPS_DEG = 0.05

S = {'ctx': None, 'url': None, 'token': None, 'inbox': queue.Queue(), 'outbox': queue.Queue(),
     'threads': False, 'alive': True, 'connected': False, 'snap': None, 'frame': None,
     'last_local': 0.0, 'pending_shot': None, 'pending_rebuild': None, 'status': 'starting',
     'item_off': {}, 'piece_base': {}, 'rebuild': None, 'header': False}


def log(m):
    print('mirror:', m, flush=True)


# ---------------------------------------------------------------- network (background threads)
def _post(path, body, timeout):
    req = urllib.request.Request(S['url'] + '/api/' + path, data=json.dumps(body).encode(),
                                 headers={'content-type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b'{}')


def _puller():
    since = 0
    fails = 0
    while S['alive']:
        try:
            r = _post('mirror-pull', {'token': S['token'], 'since': since}, 30)
            fails = 0
            S['connected'] = True
            if r.get('closed'):
                S['inbox'].put({'t': 'bye'})
                S['alive'] = False
                break
            for m in r.get('msgs') or []:
                since = max(since, int(m.get('seq', since)))
                S['inbox'].put(m)
        except Exception:
            fails += 1
            S['connected'] = False
            if fails > 40:      # the app has been gone for a minute or more
                S['inbox'].put({'t': 'bye', 'why': 'Doodle Studio 3D is not answering'})
                S['alive'] = False
                break
            time.sleep(1.5)


def _pusher():
    while S['alive']:
        try:
            m = S['outbox'].get(timeout=1)
        except queue.Empty:
            continue
        batch = [m]
        while True:
            try:
                batch.append(S['outbox'].get_nowait())
            except queue.Empty:
                break
        try:
            _post('mirror-push', {'token': S['token'], 'msgs': batch}, 10)
            S['connected'] = True
        except Exception:
            time.sleep(0.5)


def send(m):
    S['outbox'].put(m)


# ---------------------------------------------------------------- the rig <-> Doodle Studio values
def _ctrl_by_bone(controls):
    out = {}
    for c in controls:
        if c.get('owner') in ds_map.BONE_MAP and ds_map.TRACK_IDS.get(c['name']):
            out.setdefault(c['owner'], []).append(c)
    return out


def _local_q(pb):
    if pb.rotation_mode == 'QUATERNION':
        return pb.rotation_quaternion.copy()
    if pb.rotation_mode == 'AXIS_ANGLE':
        a = pb.rotation_axis_angle
        return Quaternion(Vector(a[1:]), a[0])
    return pb.rotation_euler.to_quaternion()


def bone_values(pb, ctrls):
    """Doodle Studio control values (degrees) that pose this bone as it is now."""
    B0 = pb.bone.matrix_local.to_3x3()
    M = B0 @ _local_q(pb).to_matrix() @ B0.inverted()
    axes = [c['axis'] for c in ctrls]
    out = {}
    if len(axes) == 1:
        ax = Vector([1.0 if axes[0] == k else 0.0 for k in (1, 2, 3)])
        q = M.to_quaternion()
        ang = 2 * math.atan2(Vector(q[1:]).dot(ax), q[0])
        ang = (ang + math.pi) % (2 * math.pi) - math.pi
        degs = [math.degrees(ang)]
    else:
        # M = R(a1) R(a2) [R(a3)]: Blender's Euler order string lists the rightmost rotation first
        order = [ds_map.AXES[a] for a in axes]
        if len(order) == 2:
            order.append(({'X', 'Y', 'Z'} - set(order)).pop())
        e = M.to_euler(''.join(reversed(order)))
        by = {'X': e.x, 'Y': e.y, 'Z': e.z}
        degs = [math.degrees(by[ds_map.AXES[a]]) for a in axes]
    for c, d in zip(ctrls, degs):
        v = d * c['sign']
        out[ds_map.TRACK_IDS[c['name']]] = max(c['min'], min(c['max'], v))
    return out


def rig_values(ctx):
    arm, meta, Sk = ctx['arm'], ctx['meta'], ctx['S']
    pb = arm.pose.bones
    out = {}
    for ds_bone, ctrls in _ctrl_by_bone(meta['controls']).items():
        b = pb.get(ds_map.BONE_MAP[ds_bone])
        if b is not None:
            out.update(bone_values(b, ctrls))
    root = pb['root']
    B0 = root.bone.matrix_local.to_3x3()
    off = B0 @ root.location
    # the armature object moved as a whole (G in object mode): that is the same as moving the root
    base = S.get('arm_base')
    if base is not None:
        d = base.inverted() @ arm.matrix_basis.translation
        off = off + d
    out['bodyX'] = off.x / Sk * ds_map.BODY_UNIT
    out['depth'] = off.y / Sk
    out['bodyY'] = -off.z / Sk * ds_map.BODY_UNIT
    M = B0 @ _local_q(root).to_matrix() @ B0.inverted()
    turn = math.degrees(math.atan2(M[1][0], M[0][0]))
    if base is not None:
        turn += math.degrees(arm.matrix_basis.to_euler().z - base.to_euler().z)
    out['turn'] = (turn + 180) % 360 - 180
    out['s'] = root.scale.x / float(arm.get('species_scale', 1.0))
    br = pb.get('body_rot')
    if br is not None:
        Bb = br.bone.matrix_local.to_3x3()
        Mb = Bb @ _local_q(br).to_matrix() @ Bb.inverted()
        out['bodyRot'] = math.degrees(math.atan2(Mb[0][2], Mb[0][0]))
    f = pb.get('face')
    if f is not None:
        for k, tid in (('expression', 'expression'), ('gaze', 'gaze'), ('speech_mouth', 'mouth'), ('blink', 'blink')):
            if k in f:
                out[tid] = int(f[k])
    return out


def cam_values(ctx, prev):
    """The camera as Doodle Studio's orbit camera: aim point, yaw, pitch, distance, lens, roll."""
    cam = ctx['cam']
    mw = cam.matrix_basis   # the camera is not parented: its own transform is where it is, with no wait for a depsgraph update
    L = mw.translation
    fwd = (mw.to_3x3() @ Vector((0, 0, -1))).normalized()
    dist = float(prev.get('dist', 3.0)) or 3.0
    T = L + fwd * dist
    d = -fwd
    out = {'dist': dist, 'tx': T.x, 'ty': T.y, 'tz': T.z, 'lens': cam.data.lens,
           'pitch': math.degrees(math.asin(max(-1, min(1, d.z)))), 'yaw': math.degrees(math.atan2(d.x, -d.y))}
    q0 = fwd.to_track_quat('-Z', 'Y')
    rel = q0.inverted() @ mw.to_quaternion()
    out['roll'] = math.degrees(2 * math.atan2(rel.z, rel.w))
    out['roll'] = (out['roll'] + 180) % 360 - 180
    if cam.data.dof.use_dof:
        out['focus'] = cam.data.dof.focus_distance
        out['fstop'] = cam.data.dof.aperture_fstop
    return out


# ---------------------------------------------------------------- what Blender shows that the app owns
def _items():
    return [o for o in bpy.data.objects if 'ds_item' in o.keys() and not o.get('dsl_held_side')]


def _pieces():
    coll = bpy.data.collections.get('Doodle Set')
    if not coll:
        return []
    return [o for o in coll.all_objects if o.get('dsl_prop') and not o.get('dsl_shell')]


def _on(pid):
    coll = bpy.data.collections.get('Doodle Set')
    return [o for o in (coll.all_objects if coll else []) if o.get('dsl_on') == pid]


def _sun():
    return bpy.data.objects.get('DSL_Sun')


def remember_layout(shot):
    """Where the library put each item and piece before the app's own moves, so moves map 1:1."""
    items = shot.get('items') or []
    S['item_off'] = {}
    for o in _items():
        it = items[o['ds_item']] if o['ds_item'] < len(items) else {}
        at = Vector(it.get('at') or o.location)
        S['item_off'][o.name] = o.location - at
    pieces = (shot.get('stage') or {}).get('pieces') or {}
    S['piece_base'] = {}
    for o in _pieces():
        xf = pieces.get(o['dsl_prop']) or {}
        at, rot, sc = Vector(xf.get('at') or (0, 0, 0)), math.radians(float(xf.get('rot') or 0)), float(xf.get('scale') or 1)
        S['piece_base'][o.name] = (o.location - at, o.rotation_euler.z - rot, o.scale / sc, (o.rotation_euler.x, o.rotation_euler.y))
    for pid in {o['dsl_prop'] for o in _pieces()}:
        xf = pieces.get(pid) or {}
        at = Vector(xf.get('at') or (0, 0, 0))
        for o in _on(pid):
            S['piece_base'].setdefault(o.name, (o.location - at, o.rotation_euler.z, o.scale.copy()))
    S['arm_base'] = S['ctx']['arm'].matrix_world.copy()


def place_items(shot):
    items = shot.get('items') or []
    for o in _items():
        i = o['ds_item']
        if i >= len(items) or items[i].get('hold'):
            continue
        it = items[i]
        if it.get('at') is not None:
            o.location = Vector(it['at']) + S['item_off'].get(o.name, Vector())
        if it.get('rot') is not None:
            o.rotation_euler = [math.radians(float(a)) for a in it['rot']]
        if it.get('scale') is not None:
            o.scale = [float(a) for a in it['scale']]


def place_pieces(shot):
    pieces = (shot.get('stage') or {}).get('pieces') or {}
    for o in _pieces():
        b = S['piece_base'].get(o.name)
        if not b:
            continue
        xf = pieces.get(o['dsl_prop']) or {}
        at, rot, sc = Vector(xf.get('at') or (0, 0, 0)), math.radians(float(xf.get('rot') or 0)), float(xf.get('scale') or 1)
        o.location = b[0] + at
        o.rotation_euler.x, o.rotation_euler.y = b[3]
        o.rotation_euler.z = b[1] + rot
        o.scale = b[2] * sc
        for c in _on(o['dsl_prop']):
            cb = S['piece_base'].get(c.name)
            if cb:
                c.location = cb[0] + at


def place_sun(shot):
    sun, st = _sun(), (shot.get('stage') or {}).get('sun')
    if sun is None or not st:
        return
    if st.get('rot'):
        sun.rotation_euler = [math.radians(float(a)) for a in st['rot']]
    if st.get('energy') is not None and sun.data:
        sun.data.energy = float(st['energy'])


# ---------------------------------------------------------------- keys, rewritten in bulk
def _channels_for(idb, values_by_path, n):
    """Write n per-frame values into idb's existing F-curves (keyframe_insert makes any missing)."""
    from compat import fcurves
    have = {(fc.data_path, fc.array_index): fc for fc in fcurves(idb)}
    for (path, idx), vals in values_by_path.items():
        fc = have.get((path, idx))
        if fc is None:
            continue
        kp = fc.keyframe_points
        if len(kp) < n:
            kp.add(n - len(kp))
        while len(kp) > n:
            kp.remove(kp[len(kp) - 1], fast=True)
        co = [0.0] * (2 * n)
        co[0::2] = [float(i + 1) for i in range(n)]
        co[1::2] = vals
        kp.foreach_set('co', co)
        kp.foreach_set('handle_left', co)
        kp.foreach_set('handle_right', co)
        fc.update()


def rebake(shot):
    """Every frame's values become the rig's and the camera's keys again (no collision pass:
    the live view shows exactly what the app has; renders still apply every rule)."""
    ctx = S['ctx']
    arm, cam, settings, sc = ctx['arm'], ctx['cam'], ctx['settings'], bpy.context.scene
    frames = shot.get('frames') or []
    n = len(frames)
    if not n:
        return
    t0 = time.time()
    fps = int(shot.get('fps', sc.render.fps))
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, n
    sc.render.resolution_x = int(shot.get('width', sc.render.resolution_x))
    sc.render.resolution_y = int(shot.get('height', sc.render.resolution_y))
    bones = ctx['pose_bones']
    rig, camv, setv = {}, {}, {}
    face_keys = ('expression', 'gaze', 'speech_mouth', 'blink')
    fb = arm.pose.bones.get('face')
    for i, vals in enumerate(frames):
        ctx['apply'](vals)
        if 'cam' in vals:
            ctx['camera_3d'](vals['cam'], i / fps)
        if ctx.get('ink_follow') and 'ink_px' in settings.keys():
            settings['ink_px'] = ink_now(ctx)
        for b in bones:
            path = ds_map.rotation_path(b)
            r = getattr(b, path)
            for k in range(len(r)):
                rig.setdefault((f'pose.bones["{b.name}"].{path}', k), []).append(r[k])
            for k in range(3):
                rig.setdefault((f'pose.bones["{b.name}"].location', k), []).append(b.location[k])
                rig.setdefault((f'pose.bones["{b.name}"].scale', k), []).append(b.scale[k])
        if fb is not None:
            for k in face_keys:
                if k in fb:
                    rig.setdefault((f'pose.bones["face"]["{k}"]', 0), []).append(float(fb[k]))
        for k in range(3):
            camv.setdefault(('location', k), []).append(cam.location[k])
            camv.setdefault(('rotation_euler', k), []).append(cam.rotation_euler[k])
        camv.setdefault(('lens', 0), []).append(cam.data.lens)
        camv.setdefault(('dof.focus_distance', 0), []).append(cam.data.dof.focus_distance)
        camv.setdefault(('dof.aperture_fstop', 0), []).append(cam.data.dof.aperture_fstop)
        camv.setdefault(('dof.use_dof', 0), []).append(float(cam.data.dof.use_dof))
        for k in ('boil', 'ink_px'):
            if k in settings.keys():
                setv.setdefault((f'["{k}"]', 0), []).append(float(settings[k]))
    _channels_for(arm, rig, n)
    _channels_for(cam, {k: v for k, v in camv.items() if k[0] in ('location', 'rotation_euler')}, n)
    _channels_for(cam.data, {k: v for k, v in camv.items() if k[0] not in ('location', 'rotation_euler')}, n)
    _channels_for(settings, setv, n)
    from compat import fcurves
    for fc in fcurves(arm):
        if fc.data_path.startswith('pose.bones["face"]'):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    place_items(shot)
    place_pieces(shot)
    place_sun(shot)
    ctx['shot'] = shot
    f = min(max(1, sc.frame_current), n)
    sc.frame_set(f)
    log(f'rebaked {n} frames in {time.time() - t0:.2f} s')


def ink_now(ctx):
    """ds_bridge's ink_for_camera without a depsgraph update per frame (camera and root are
    read from their own transforms)."""
    arm, cam = ctx['arm'], ctx['cam']
    fwd = cam.matrix_basis.to_3x3() @ Vector((0, 0, -1))
    root = arm.pose.bones['root']
    head = root.bone.head_local + root.bone.matrix_local.to_3x3() @ root.location
    P = arm.matrix_basis @ head + Vector((0, 0, ctx['pivot_z']))
    depth = max(0.05, (P - cam.matrix_basis.translation).dot(fwd))
    zoom = ctx['base_ortho'] / (depth * 36.0 / max(1.0, cam.data.lens))
    return ctx['ink_base'] * max(0.4, min(3.5, zoom))


def show_pose(values, camv):
    """The app's current frame, shown at once (the next shot message keys it)."""
    ctx = S['ctx']
    cur = dict(frame_values(bpy.context.scene.frame_current))
    cur.update(values or {})
    ctx['apply'](cur)
    if camv:
        c = dict(cur.get('cam') or {})
        c.update(camv)
        ctx['camera_3d'](c, 0)
    if ctx.get('ink_follow') and 'ink_px' in ctx['settings'].keys():
        ctx['settings']['ink_px'] = ink_now(ctx)


def frame_values(f):
    frames = (S['ctx'].get('shot') or {}).get('frames') or []
    return frames[min(max(f - 1, 0), len(frames) - 1)] if frames else {}


# ---------------------------------------------------------------- change detection
def _r(v, k=4):
    return tuple(round(x, k) for x in v)


def snapshot():
    ctx = S['ctx']
    arm, cam = ctx['arm'], ctx['cam']
    s = {'frame': bpy.context.scene.frame_current}
    pb = arm.pose.bones
    bones = {}
    for name in list(ds_map.BONE_MAP.values()) + ['root', 'body_rot', 'face']:
        b = pb.get(name)
        if b is None:
            continue
        key = _r(_local_q(b)) + _r(b.location) + _r(b.scale)
        if name == 'face':
            key += tuple(int(b[k]) for k in ('expression', 'gaze', 'speech_mouth', 'blink') if k in b)
        bones[name] = key
    s['bones'] = bones
    s['arm'] = _r(v for row in arm.matrix_basis for v in row)
    s['cam'] = _r([v for row in cam.matrix_basis for v in row] + [cam.data.lens, cam.data.dof.focus_distance, cam.data.dof.aperture_fstop])
    s['items'] = {o.name: _r([v for row in o.matrix_basis for v in row]) for o in _items()}
    s['pieces'] = {o.name: _r([v for row in o.matrix_basis for v in row]) for o in _pieces()}
    sun = _sun()
    s['sun'] = _r(list(sun.rotation_euler) + [sun.data.energy if sun.data else 0]) if sun else None
    return s


def _modal_running():
    try:
        for w in bpy.context.window_manager.windows:
            if len(w.modal_operators):
                return True
    except Exception:
        pass
    return False


def detect():
    """Compare with the last look; send what the user changed in Blender."""
    old, new = S['snap'], snapshot()
    S['snap'] = new
    if old is None:
        return
    if new['frame'] != old['frame']:
        send({'t': 'frame', 'f': new['frame'] - 1})
        return
    msg = {'t': 'edit', 'f': new['frame'] - 1}
    ctx = S['ctx']
    cur = frame_values(new['frame'])
    if new['bones'] != old['bones'] or new['arm'] != old['arm']:
        vals = rig_values(ctx)
        changed = {k: round(v, 3) for k, v in vals.items() if abs(float(cur.get(k, 0 if k != 's' else 1)) - v) > (1e-3 if k in ('depth', 's') else EPS_DEG)}
        if changed:
            msg['values'] = changed
    if new['cam'] != old['cam']:
        cv = cam_values(ctx, cur.get('cam') or {})
        prev = cur.get('cam') or {}
        changed = {('cam.' + k): round(v, 4) for k, v in cv.items() if abs(float(prev.get(k, 0)) - v) > 1e-3}
        if changed:
            msg.setdefault('values', {}).update(changed)
    if new['items'] != old['items']:
        out = {}
        for o in _items():
            if new['items'].get(o.name) != old['items'].get(o.name):
                at = o.location - S['item_off'].get(o.name, Vector())
                out[str(o['ds_item'])] = {'at': [round(x, 3) for x in at], 'rot': [round(math.degrees(a), 2) for a in o.rotation_euler],
                                          'scale': [round(x, 3) for x in o.scale]}
        if out:
            msg['items'] = out
    if new['pieces'] != old['pieces']:
        out = {}
        for o in _pieces():
            b = S['piece_base'].get(o.name)
            if b and new['pieces'].get(o.name) != old['pieces'].get(o.name):
                out[o['dsl_prop']] = {'at': [round(x, 3) for x in (o.location - b[0])], 'rot': round(math.degrees(o.rotation_euler.z - b[1]), 2),
                                      'scale': round(o.scale.x / (b[2].x or 1), 3)}
        if out:
            msg['pieces'] = out
    if new['sun'] != old['sun'] and new['sun']:
        sun = _sun()
        msg['sun'] = {'rot': [round(math.degrees(a), 2) for a in sun.rotation_euler], 'energy': round(sun.data.energy, 3)}
    if len(msg) > 2:
        if os.environ.get('DS3D_LIVE_DEBUG'):
            log('edit ' + json.dumps(msg)[:300])
        S['last_local'] = time.time()
        send(msg)
        # keep the shot data in step, so the next look compares against what the app now has
        if 'values' in msg and S['ctx'].get('shot'):
            fr = frame_values(new['frame'])
            for k, v in msg['values'].items():
                if k.startswith('cam.'):
                    fr.setdefault('cam', {})[k[4:]] = v
                else:
                    fr[k] = v


def _piece_xf(o, shot):
    xf = ((shot.get('stage') or {}).get('pieces') or {}).get(o['dsl_prop']) or {}
    return Vector(xf.get('at') or (0, 0, 0)), math.radians(float(xf.get('rot') or 0)), float(xf.get('scale') or 1)


def settle():
    """After a drag ends: an armature moved as a whole hands its move to the root bone, and the
    other parts of a moved set piece (and what stands on it) follow the part that was moved."""
    ctx = S['ctx']
    arm, base = ctx['arm'], S.get('arm_base')
    if base is not None and ((arm.matrix_basis.translation - base.translation).length > 1e-5 or
                             abs(arm.matrix_basis.to_euler().z - base.to_euler().z) > 1e-5):
        vals = rig_values(ctx)
        arm.matrix_basis = base
        cur = dict(frame_values(bpy.context.scene.frame_current))
        cur.update(vals)
        ctx['apply'](cur)
    shot = ctx.get('shot') or {}
    pieces = shot.setdefault('stage', {}).setdefault('pieces', {})
    for o in _pieces():
        b = S['piece_base'].get(o.name)
        if not b:
            continue
        at0, rot0, sc0 = _piece_xf(o, shot)
        at, rot, sc = o.location - b[0], o.rotation_euler.z - b[1], o.scale.x / (b[2].x or 1)
        if (at - at0).length > 1e-4 or abs(rot - rot0) > 1e-4 or abs(sc - sc0) > 1e-4:
            if at.length > 1e-4 or abs(rot) > 1e-4 or abs(sc - 1) > 1e-4:
                pieces[o['dsl_prop']] = {'at': list(at), 'rot': math.degrees(rot), 'scale': sc}
            else:
                pieces.pop(o['dsl_prop'], None)
    place_pieces(shot)
    bpy.context.view_layer.update()
    S['snap'] = snapshot()


# ---------------------------------------------------------------- the timer
def _playing():
    try:
        return any(w.screen.is_animation_playing for w in bpy.context.window_manager.windows)
    except Exception:
        return False


def apply_incoming():
    busy = _modal_running() or time.time() - S['last_local'] < QUIET
    playing = _playing()
    took = False
    while True:
        try:
            m = S['inbox'].get_nowait()
        except queue.Empty:
            break
        t = m.get('t')
        if t == 'frame':
            S['pending_frame'] = int(m['f'])
        elif t == 'pose':
            if not busy and int(m.get('f', -1)) + 1 == bpy.context.scene.frame_current:
                show_pose(m.get('values'), m.get('cam'))
                took = True
        elif t == 'shot':
            S['pending_shot'] = m
        elif t == 'rebuild':
            S['pending_rebuild'] = m
        elif t == 'bye':
            S['status'] = m.get('why') or 'Doodle Studio 3D closed the live link'
            S['alive'] = False
            log(S['status'])
    if not busy and S.get('pending_frame') is not None:
        f, S['pending_frame'] = S['pending_frame'], None
        if f + 1 != bpy.context.scene.frame_current:
            bpy.context.scene.frame_set(f + 1)
            took = True
    if not busy and not playing and S['pending_rebuild']:
        m, S['pending_rebuild'], S['pending_shot'] = S['pending_rebuild'], None, None
        rebuild(m)
        return
    if not busy and not playing and S['pending_shot']:
        m, S['pending_shot'] = S['pending_shot'], None
        try:
            rebake(m['shot'])   # the playhead has its own messages: this shot's frame may be stale
        except Exception as e:
            log(f'could not update the keys: {e}')
        took = True
    if took:
        bpy.context.view_layer.update()
        S['snap'] = snapshot()


def tick():
    if S['ctx'] is None:
        return TICK
    try:
        if not S['alive']:
            redraw_header()
            return None
        if S['rebuild']:
            return TICK
        modal = _modal_running()
        if S.get('was_modal') and not modal:
            S['last_local'] = time.time()   # what the drag left is read and answered first
        S['was_modal'] = modal
        apply_incoming()
        if S['rebuild']:
            return TICK
        before = S['last_local']
        detect()
        if S['last_local'] != before:
            S['dirty_layout'] = True
        # after detect: settle() takes a new snapshot, and what a drag left (a cancel) must be sent first
        if not modal and S['snap'] is not None and S.get('dirty_layout'):
            S['dirty_layout'] = False
            settle()
        redraw_header()
    except Exception as e:
        log(f'tick: {e}')
    return TICK


# ---------------------------------------------------------------- reopening for big changes
def rebuild(m):
    """Props added or removed, another set or shot: build the shot again from the clean file."""
    ctx = S['ctx']
    with open(ctx['shot_path'], 'w') as f:
        json.dump(m['shot'], f)
    S['rebuild'] = {'frame': m.get('f')}
    S['status'] = 'rebuilding'
    log('rebuilding the shot')
    wm = bpy.context.window_manager
    win = wm.windows[0] if wm.windows else None
    try:
        if win is not None:
            with bpy.context.temp_override(window=win):
                bpy.ops.wm.open_mainfile(filepath=ctx['source_blend'], load_ui=False)
        else:
            bpy.ops.wm.open_mainfile(filepath=ctx['source_blend'], load_ui=False)
    except Exception as e:
        log(f'rebuild failed: {e}')
        S['rebuild'] = None


@bpy.app.handlers.persistent
def _after_load(_):
    if S['rebuild'] is not None:
        S['rebuild_ready'] = True
        bpy.app.timers.register(_run_bridge_timer, first_interval=0.05)


def _run_bridge_timer():
    if S.get('rebuild_ready'):
        S['rebuild_ready'] = False
        _run_bridge()
    return None


def _rebuild_failed(ctx):
    """Save must not reach the clean file that is open now, and the old objects are gone."""
    try:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ctx['out_dir'], 'rebuild_failed.blend'))
    except Exception as e:
        log(f'could not leave the clean file: {e}')
    S['status'] = 'Doodle Studio 3D could not rebuild the shot'
    log(S['status'])
    try:
        _post('mirror-push', {'token': S['token'], 'msgs': [{'t': 'failed'}]}, 5)
    except Exception:
        pass
    S['alive'] = False


def _run_bridge():
    import runpy
    import sys
    ctx = S['ctx']
    sys.argv = ['blender', '--', ctx['shot_path'], ctx['out_dir'], *ctx['argv_rest']]
    try:
        runpy.run_path(ctx['bridge_path'], run_name='__ds_live__')
    except SystemExit:
        pass
    except Exception as e:
        log(f'rebuild: {e}')
    fr = (S['rebuild'] or {}).get('frame')
    S['rebuild'] = None
    if S['ctx'] is ctx:     # start() never ran again: the build stopped before the link came back
        _rebuild_failed(ctx)
        return None
    if fr is not None:
        bpy.context.scene.frame_set(int(fr) + 1)
    S['snap'] = snapshot()
    send({'t': 'rebuilt'})
    return None


# ---------------------------------------------------------------- the header badge
def _draw_header(self, context):
    row = self.layout.row()
    if not S['alive']:
        row.label(text='Doodle Studio 3D: link closed', icon='UNLINKED')
    elif S['rebuild']:
        row.label(text='Doodle Studio 3D: rebuilding the shot', icon='FILE_REFRESH')
    else:
        row.label(text='Live with Doodle Studio 3D' if S['connected'] else 'Doodle Studio 3D: connecting', icon='LINKED' if S['connected'] else 'TIME')


def redraw_header():
    try:
        st = (S['alive'], S['connected'], bool(S['rebuild']))
        if st == S.get('header_state'):
            return
        S['header_state'] = st
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == 'VIEW_3D':
                    a.tag_redraw()
    except Exception:
        pass


def _look_through_camera():
    try:
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == 'VIEW_3D':
                    for sp in a.spaces:
                        if sp.type == 'VIEW_3D':
                            sp.region_3d.view_perspective = 'CAMERA'
    except Exception:
        pass
    return None


def start(ctx):
    """Called by ds_bridge.py --live once the shot is built (again after every rebuild)."""
    S['ctx'] = ctx
    S['url'], S['token'] = ctx['url'], ctx['token']
    remember_layout(ctx['shot'])
    for name in ds_map.BONE_MAP.values():
        b = ctx['arm'].pose.bones.get(name)
        if b is not None:
            b.lock_location = (True, True, True)
            b.lock_scale = (True, True, True)
    S['snap'] = None
    if not S['threads']:
        S['threads'] = True
        threading.Thread(target=_puller, daemon=True).start()
        threading.Thread(target=_pusher, daemon=True).start()
        bpy.app.timers.register(tick, first_interval=TICK, persistent=True)
        bpy.app.handlers.load_post.append(_after_load)
        bpy.types.VIEW3D_HT_header.append(_draw_header)
        send({'t': 'hello', 'blender': bpy.app.version_string, 'file': bpy.data.filepath})
    if ctx.get('frame') is not None:
        bpy.context.scene.frame_set(int(ctx['frame']) + 1)
    bpy.context.view_layer.update()
    if not bpy.app.background:
        bpy.app.timers.register(_look_through_camera, first_interval=0.5)
    S['snap'] = snapshot()
    S['status'] = 'live'
    log('live link up')
