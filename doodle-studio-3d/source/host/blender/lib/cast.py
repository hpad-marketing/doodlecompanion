"""Co-stars: more characters in one shot (shot['costars']).

  costars [{character: bunny|koala|frog, blend?, x, y, turn, frames: [{control: value}, ...]}]

Each co-star's whole rig is appended from its own .blend into this scene, re-pointed at this
camera (its ink keeps Bunny's screen weight), and stood on the floor at (x, y) turned `turn`
degrees. Every frame it is posed from its own track values, its arms are kept out of its own
head like the lead's, and it is pushed apart from the lead (and from the other co-stars) until
no part of one body touches another. Pushes are logged in collision.json.
"""
import json
import math
import os
import re

import bpy
from mathutils import Vector

import collision
import ds_map

GAP = 0.04   # metres of air between two bodies at their closest


def _blend(entry, here):
    if entry.get('blend') and os.path.exists(entry['blend']):
        return entry['blend']
    c = re.sub(r'[^a-z0-9_-]', '', str(entry.get('character') or 'bunny').lower())
    return os.path.join(here, 'Bunny3D_v2.blend') if c == 'bunny' else os.path.join(here, 'chars', c + '.blend')


def _objs(new):
    # the same keys the lead's collision objects use ('head', 'sleeve_up.L', ...), suffix dropped
    return {re.sub(r'\.\d{3}$', '', o.name[6:]): o for o in new if o.type == 'MESH' and o.name.startswith('BUNNY_')}


def setup(shot, cam, here, log):
    out = []
    for i, entry in enumerate((shot.get('costars') or [])[:3]):
        path = _blend(entry, here)
        if not os.path.exists(path):
            log(f'cast: no file for {entry.get("character")}')
            continue
        before, before_t = set(bpy.data.objects), set(bpy.data.texts)
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            dst.collections = ['Bunny']
            dst.texts = ['DOODLE_STUDIO_RIG.json']
        col = dst.collections[0]
        col.name = f'Costar {i + 1}'
        bpy.context.scene.collection.children.link(col)
        # its own camera goes: everything (ink drivers included) follows this shot's camera
        for o in [o for o in bpy.data.objects if o not in before and o.type == 'CAMERA']:
            d = o.data
            d.user_remap(cam.data)
            o.user_remap(cam)
            bpy.data.objects.remove(o)
            if d.users == 0:
                bpy.data.cameras.remove(d)
        new = [o for o in bpy.data.objects if o not in before]
        rig = next(o for o in new if o.type == 'ARMATURE')
        settings = next(o for o in new if o.name.startswith('BUNNY_settings'))
        text = next(t for t in bpy.data.texts if t not in before_t)
        meta = json.loads(text.as_string())
        root = bpy.data.objects.new(f'DS_costar{i + 1}', None)
        bpy.context.scene.collection.objects.link(root)
        root.location = (float(entry.get('x', 0.75)), float(entry.get('y', 0.0)), 0.0)
        root.rotation_euler = (0.0, 0.0, math.radians(float(entry.get('turn', 0.0))))
        rig.parent = root
        objs = _objs(new)
        c = {'name': entry.get('character', 'bunny'), 'rig': rig, 'settings': settings, 'meta': meta, 'S': meta['S'], 'root': root,
             'objs': objs, 'ears': collision.ear_vertex_sets(objs['head']), 'frames': entry.get('frames') or [], 'home': root.location.copy(),
             'pose_bones': [b for b in rig.pose.bones if not b.name.startswith(('MCH-', 'DEF-'))], 'hint': None, 'pushes': []}
        out.append(c)
        log(f'cast: {c["name"]} at ({root.location.x:.2f}, {root.location.y:.2f}) turned {entry.get("turn", 0)}°')
    return out


def pose_frame(c, i, f, lead_settings, collide=True):
    vals = c['frames'][min(i, len(c['frames']) - 1)] if c['frames'] else {}
    apply = lambda v: ds_map.apply_pose(c['rig'], c['meta']['controls'], v, c['S'], c['settings'])
    if collide:
        vals, c['hint'] = collision.solve_frame(apply, vals, c['objs'], c['ears'], hint=c['hint'])
    else:
        apply(vals)
    # one ink weight for everyone: the lead's (it follows the camera zoom)
    for k in ('ink_px', 'boil'):
        if k in lead_settings.keys() and k in c['settings'].keys():
            c['settings'][k] = lead_settings[k]
            c['settings'].keyframe_insert(f'["{k}"]', frame=f)
    rig = c['rig']
    for b in c['pose_bones']:
        b.keyframe_insert(ds_map.rotation_path(b), frame=f, group=b.name)
        b.keyframe_insert('location', frame=f, group=b.name)
        b.keyframe_insert('scale', frame=f, group=b.name)
    fb = rig.pose.bones.get('face')
    if fb is not None:
        for k in ('expression', 'gaze', 'speech_mouth', 'blink'):
            if k in fb.keys():
                fb.keyframe_insert(f'["{k}"]', frame=f, group='face')


def _cages(objs):
    """World-space cage meshes (armature only, like the collision solver), all evaluated in one go."""
    obs = [o for o in objs.values() if not o.hide_render]
    mods = [(m, m.show_viewport) for o in obs for m in o.modifiers if m.type != 'ARMATURE']
    for m, _ in mods:
        m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in obs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        out.append(([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]))
        ev.to_mesh_clear()
    for m, was in mods:
        m.show_viewport = was
    return out


def _bvhs(objs, cages=None, shift=None):
    from mathutils.bvhtree import BVHTree
    cages = cages if cages is not None else _cages(objs)
    return [BVHTree.FromPolygons([v + shift for v in vs] if shift is not None else vs, ps) for vs, ps in cages]


def _touch(a, b):
    return any(x.overlap(y) for x in a for y in b)


def _centre(rig):
    return rig.matrix_world @ rig.pose.bones['body'].head


def keep_apart(lead_objs, lead_arm, cast, f, log):
    """Push each co-star straight away from the lead (and earlier co-stars) until nothing touches."""
    others = [(lead_objs, lead_arm)]
    for c in cast:
        root = c['root']
        root.location = c['home'].copy()   # every frame starts from where it was placed
        bpy.context.view_layer.update()
        pushed = 0.0
        for objs, arm in others:
            away = _centre(c['rig']) - _centre(arm)
            away.z = 0
            if away.length < 1e-4:
                away = Vector((1, 0, 0))
            away.normalize()
            if (_centre(c['rig']) - _centre(arm)).length > 1.6:
                continue
            theirs = _bvhs(objs)
            base = root.location.copy()
            mine = _cages(c['objs'])   # moving the root moves the whole body rigidly: shift, don't re-evaluate

            def clear(d):
                return not _touch(_bvhs(None, mine, away * d), theirs)
            if clear(0.0):
                continue
            # double out until clear, then halve back in: about eight checks instead of one per 2 cm
            lo, hi = 0.0, 0.08
            while not clear(hi) and hi < 1.6:
                lo, hi = hi, hi * 2
            for _ in range(4):
                mid = (lo + hi) / 2
                if clear(mid):
                    hi = mid
                else:
                    lo = mid
            root.location = base + away * (hi + GAP)   # a little air between them
            bpy.context.view_layer.update()
            pushed += hi + GAP
        c.setdefault('offsets', {})[f] = root.location - c['home']
        if pushed:
            c['pushes'].append({'frame': f, 'cm': round(pushed * 100, 1)})
        others.append((c['objs'], c['rig']))


def finish(cast, n):
    """Key the pushes eased: a push starts early and lets go slowly, never a jump."""
    R = 8
    for c in cast:
        off = c.get('offsets', {})
        for f in range(1, n + 1):
            best = Vector((0, 0, 0))
            for k in range(-R, R + 1):
                v = off.get(f + k)
                if v is None or v.length == 0:
                    continue
                t = abs(k) / (R + 1)
                w = 1 - t * t * (3 - 2 * t)
                if v.length * w > best.length:
                    best = v * w
            c['root'].location = c['home'] + best
            c['root'].keyframe_insert('location', frame=f)


def touching(lead_objs, cast):
    """Rule check: does any body touch another this frame?"""
    groups = [_bvhs(lead_objs)] + [_bvhs(c['objs']) for c in cast]
    return any(_touch(groups[i], groups[j]) for i in range(len(groups)) for j in range(i + 1, len(groups)))
