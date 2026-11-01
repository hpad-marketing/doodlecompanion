"""Faces and mouths.

Expressions are face-bone states (expression, gaze, blink, mouth) plus optional
ear values, keyed with constant interpolation like Doodle Studio's drawings.
Mouth sets reuse the 3D Bunny's DS_Face node group on a second face object,
so each of the 14 approved sets wraps onto the head with the same ink, boil and
per-expression mouth offsets as the built-in mouths.
"""
import json

import bpy

from . import index, paths
from . import gnodes

FACE_PROPS = ('expression', 'gaze', 'speech_mouth', 'blink')
SET_STRIDE = 100  # speech index = set * 100 + mouth key


def face_bone():
    arm = bpy.data.objects.get('BUNNY_rig')
    fb = arm and arm.pose.bones.get('face')
    if fb is None:
        raise RuntimeError('No BUNNY_rig face bone in this file.')
    return arm, fb


def apply_expression(item, frame=None, key=True):
    arm, fb = face_bone()
    frame = bpy.context.scene.frame_current if frame is None else frame
    data = _resolve_story_face(arm, fb, item['data'])
    if data is None:
        return  # this face was made for another character
    _plan_cache.clear()
    for k in FACE_PROPS:
        if k in data and k in fb.keys():
            fb[k] = int(data[k])
            if key:
                fb.keyframe_insert(f'["{k}"]', frame=frame, group='face')
    ears = data.get('ears')
    if ears:
        meta = paths.bunny_module('ds_map')
        txt = bpy.data.texts.get('DOODLE_STUDIO_RIG.json')
        if txt:
            import json
            m = json.loads(txt.as_string())
            for side, ds in (('L', 'EAR.L'), ('R', 'EAR.R')):
                vals = {'ear%sFold' % side: ears.get('ear%sFold' % side, 0), 'ear%sForward' % side: ears.get('ear%sForward' % side, 0)}
                M = meta.ds_world_rotation(m['controls'], vals, ds)
                pb = arm.pose.bones['ear.' + side]
                from .motions import set_rot, rot_path
                set_rot(pb, meta.to_local(pb, M))
                if key:
                    pb.keyframe_insert(rot_path(pb), frame=frame, group=pb.name)
            _ear_size_and_nose(arm, ears, float(m.get('S', 1.0)), frame if key else None)
    if key and arm.animation_data and arm.animation_data.action:
        from .motions import _fcurves
        for fc in _fcurves(arm):
            if fc.data_path.startswith('pose.bones["face"]'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    index.mark_used(item['id'])


def _ear_size_and_nose(arm, vals, S, frame=None):
    """EAR Scale / Squash and NOSE Wiggle / Sniff from a face's ears block, with the
    same limits as the rig's ds_map.apply_pose (kept in step with it). Always keys the
    defaults too, so a face without them undoes the last one's bump pop or sniff."""
    import math
    from mathutils import Vector
    for side in ('L', 'R'):
        e = arm.pose.bones.get('ear.' + side)
        if e is None:
            continue
        k = 'ear' + side
        u = max(0.5, min(1.5, float(vals.get(k + 'Scale', 100.0)) / 100.0))
        qm = 0.12 if arm.get('ear_width_lock') else 0.3
        q = max(-0.5, min(qm, float(vals.get(k + 'Squash', 0.0)) / 100.0))
        w = u / math.sqrt(1.0 - q)
        e.scale = (min(w, 1.0) if arm.get('ear_width_lock') else w, u * (1.0 - q), w)
        if frame is not None:
            e.keyframe_insert('scale', frame=frame, group=e.name)
    n = arm.pose.bones.get('nose')
    if n is not None:
        wig = max(-1.0, min(1.0, float(vals.get('noseWiggle', 0.0)) / 100.0))
        sn = max(0.0, min(1.0, float(vals.get('noseSniff', 0.0)) / 100.0))
        n.location = n.bone.matrix_local.to_3x3().inverted() @ (Vector((0.06 * wig, 0, 0.05 * sn)) * S)
        n.scale = (1 + 0.12 * sn,) * 3
        if frame is not None:
            n.keyframe_insert('location', frame=frame, group=n.name)
            n.keyframe_insert('scale', frame=frame, group=n.name)


def save_expression(name, include_ears=False):
    arm, fb = face_bone()
    data = {k: int(fb.get(k, 0)) for k in FACE_PROPS}
    item_id = index.unique_id('face-' + name)
    return index.add({'id': item_id, 'name': name, 'category': 'expression', 'kind': 'face', 'sub': 'My faces',
                      'data': data, 'source': 'blender', 'tags': []})


# ------------------------------------------------------------------ mouth sets
def _library_meshes():
    """Build (once per file) the hidden fill/stroke meshes holding every mouth set."""
    fills = bpy.data.objects.get('DSL_mouthsets_fills')
    strokes = bpy.data.objects.get('DSL_mouthsets_strokes')
    if fills and strokes:
        return fills, strokes
    face = paths.bunny_module('face')
    import json
    import os
    import tempfile
    sets = index.blob('mouths/mouth_sets.json')
    lib = {'items': []}
    for si, s in enumerate(sets['sets'], start=1):
        for it in s['items']:
            it = dict(it)
            it['speech'] = si * SET_STRIDE + it['speech']
            lib['items'].append(it)
    lib['speech_offsets_px'] = [[0, 0]]
    tmp = os.path.join(tempfile.gettempdir(), 'dsl_mouthsets_lib.json')
    with open(tmp, 'w') as f:
        json.dump(lib, f)
    coll = bpy.data.collections.get('Bunny internals') or bpy.context.scene.collection
    meta = json.loads(bpy.data.texts['DOODLE_STUDIO_RIG.json'].as_string())
    (fobj, sobj, offs), _ = face.build_library(tmp, meta['S'], coll)
    bpy.data.objects.remove(offs)
    fobj.name, sobj.name = 'DSL_mouthsets_fills', 'DSL_mouthsets_strokes'
    return fobj, sobj


def _drive_face_mod(mod, ids, arm, set_expr):
    fc = gnodes.gn_driver_add(mod, ids["Speech Mouth"])
    d = fc.driver
    d.type = 'SCRIPTED'
    for v in list(d.variables):
        d.variables.remove(v)
    for nm, prop in (('m', 'speech_mouth'), ('s', 'mouth_set')):
        var = d.variables.new()
        var.name = nm
        var.targets[0].id = arm
        var.targets[0].data_path = f'pose.bones["face"]["{prop}"]'
    d.expression = set_expr


def use_mouth_set(item):
    """Switch Bunny's speech mouths to a library set (0 / None = Doodle Studio's own)."""
    arm, fb = face_bone()
    if 'mouth_set' not in fb.keys():
        fb['mouth_set'] = 0
        fb.id_properties_ui('mouth_set').update(min=0, max=99, description='Doodle Library mouth set (0 = built-in mouths)')
    base = bpy.data.objects.get('BUNNY_face')
    bmod = base and base.modifiers.get('DS Face')
    if not bmod:
        raise RuntimeError('BUNNY_face not found')
    bids = {s.name: s.identifier for s in bmod.node_group.interface.items_tree if getattr(s, 'in_out', None) == 'INPUT'}
    # built-in face: hide its speech mouths while a set is on (99 matches nothing)
    _drive_face_mod(bmod, bids, arm, 'm if s == 0 else (99 if m > 0 else 0)')
    ob = bpy.data.objects.get('DSL_mouth_set')
    if not ob:
        fills, strokes = _library_meshes()
        ob = bpy.data.objects.new('DSL_mouth_set', bpy.data.meshes.new('DSL_mouth_set'))
        for c in base.users_collection:
            c.objects.link(ob)
        ob.data.materials.append(base.data.materials[0])
        mod = ob.modifiers.new('DS Face', 'NODES')
        mod.node_group = bmod.node_group
        for s in bmod.node_group.interface.items_tree:
            if getattr(s, 'in_out', None) == 'INPUT' and s.socket_type != 'NodeSocketGeometry':
                try:
                    gnodes.gn_set(mod, s.identifier, gnodes.gn_get(bmod, s.identifier))
                except Exception:
                    pass
        gnodes.gn_set(mod, bids['Fills'], fills)
        gnodes.gn_set(mod, bids['Strokes'], strokes)
        gnodes.gn_set(mod, bids['Blink'], 0)
        # copy every driver except Speech Mouth (that one is set-aware)
        if base.animation_data:
            for fc in base.animation_data.drivers:
                if bids['Speech Mouth'] in fc.data_path or bids['Blink'] in fc.data_path:
                    continue
                try:
                    nfc = ob.driver_add(fc.data_path)
                except TypeError:
                    nfc = ob.driver_add(fc.data_path, fc.array_index)
                nfc.driver.type = fc.driver.type
                nfc.driver.expression = fc.driver.expression
                for v in fc.driver.variables:
                    nv = nfc.driver.variables.new()
                    nv.name, nv.type = v.name, v.type
                    for i, t in enumerate(v.targets):
                        nt = nv.targets[i]
                        if v.type == 'SINGLE_PROP':
                            nt.id_type = t.id_type
                        nt.id = t.id
                        nt.data_path = t.data_path
        _drive_face_mod(mod, bids, arm, f's * {SET_STRIDE} + m if (s > 0 and m > 0) else 0')
        ob.parent = base.parent
        ob.parent_type = base.parent_type
        ob.parent_bone = base.parent_bone
        ob.matrix_world = base.matrix_world.copy()
    sets = index.blob('mouths/mouth_sets.json')['sets']
    n = 0
    if item:
        n = [s['id'] for s in sets].index(item['data']['set']) + 1
        index.mark_used(item['id'])
    fb['mouth_set'] = n
    arm.update_tag()
    return n


# ---------------------------------------------------------------- story-beat faces (expressions-v2)
def rig_species(arm):
    return str(arm.get('species', 'bunny')).lower()


def _resolve_story_face(arm, fb, data):
    """Turn a by-name story-beat row into face-bone values for THIS rig.

    - species: rows made for one character are skipped on the others
    - expression_name: Bunny, Koala and Frog number faces differently, so look it up
    - mouth_set: talking mouths switch to the named set ('mouths-x-through-teeth')
    - speech_map: lip sync remaps visemes (pucker faces talk through Pucker 01-04)
    """
    sp = data.get('species')
    if sp and rig_species(arm) not in sp:
        return None
    if 'expression_name' not in data:
        return data
    txt = bpy.data.texts.get('DOODLE_STUDIO_RIG.json')
    names = json.loads(txt.as_string()).get('faces', []) if txt else []
    names = [n if isinstance(n, str) else n.get('name') for n in names]
    if data['expression_name'] not in names:
        raise RuntimeError('This rig has no face "%s". Rebuild it with the story-beat face library.' % data['expression_name'])
    out = dict(data)
    out['expression'] = names.index(data['expression_name'])
    if out.get('gaze', -1) < 0:
        out.pop('gaze', None)
    # talking plan, read by lip sync (keyed alongside the face, constant interpolation)
    fb['talk_mode'] = data.get('talk', 'own')
    fb['speech_map'] = json.dumps(data.get('speech_map') or {})
    want = data.get('mouth_set')
    if want:
        from . import index
        ids = [s['id'] for s in index.blob('mouths/mouth_sets.json')['sets']]
        if want in ids:
            use_mouth_set({'id': want, 'data': {'set': want}})
    elif 'mouth_set' in fb.keys():
        fb['mouth_set'] = 0
    return out


# ---------------------------------------------------------------- lip sync that fits the face
TALK_MODES = ('own', 'pucker', 'teeth', 'side', 'none')
_plan_cache = {}


def talk_plan(arm, expr):
    """(talk mode, speech map) for face number `expr` on this rig. Faces without a story-beat
    row talk with their own mouths."""
    txt = bpy.data.texts.get('DOODLE_STUDIO_RIG.json')
    names = json.loads(txt.as_string()).get('faces', []) if txt else []
    names = [n if isinstance(n, str) else n.get('name') for n in names]
    if not (0 <= expr < len(names)):
        return 'own', {}
    if not _plan_cache:
        for it in index.items('expression'):
            d = it.get('data') or {}
            if d.get('expression_name'):
                _plan_cache[d['expression_name']] = (d.get('talk', 'own'), d.get('speech_map') or {})
    return _plan_cache.get(names[expr], ('own', {}))


def fit_speech(arm=None, frames=None):
    """Make every keyed speech mouth fit the face showing on that frame (the face can change
    mid-clip, so it is read at each key, never once per clip):
      pucker  visemes go through the face's speech map (the pout talks on Pucker 01-04)
      teeth   speaks through the active mouth set (the face already switched it)
      side    normal visemes
      none    on spoken keys the face drops back to the normal face (0) and comes back after
    Returns how many keys it changed."""
    if arm is None:
        arm, fb = face_bone()
    else:
        fb = arm.pose.bones.get('face')
    from .motions import _fcurves
    curves = {c.data_path: c for c in _fcurves(arm)}
    sp = curves.get('pose.bones["face"]["speech_mouth"]')
    ex = curves.get('pose.bones["face"]["expression"]')
    if not sp:
        return 0
    keys = sorted(sp.keyframe_points, key=lambda k: k.co.x)
    if frames:
        keys = [k for k in keys if frames[0] <= k.co.x <= frames[-1]]
    face_at = lambda f: int(round(ex.evaluate(f))) if ex else int(fb.get('expression', 0))
    plan = [(k, face_at(k.co.x)) for k in keys]
    changed, dropped = 0, None
    for k, face in plan:
        f = int(k.co.x)
        talk, smap = talk_plan(arm, face if dropped is None else dropped)
        vis = int(round(k.co.y))
        if talk == 'pucker' and smap:
            new = int(smap.get(str(vis), vis))
            if new != vis:
                k.co.y = new
                changed += 1
        elif talk == 'none':
            if vis and dropped is None:        # line starts: back to the normal face
                dropped = face
                fb['expression'] = 0
                fb.keyframe_insert('["expression"]', frame=f, group='face')
                changed += 1
            elif not vis and dropped is not None:  # line over: the story face returns
                fb['expression'] = dropped
                fb.keyframe_insert('["expression"]', frame=f, group='face')
                dropped = None
                changed += 1
        if dropped is not None and vis == 0 and talk != 'none':
            dropped = None
    for c in (sp, ex):
        if c:
            for k in c.keyframe_points:
                k.interpolation = 'CONSTANT'
            c.update()
    return changed
