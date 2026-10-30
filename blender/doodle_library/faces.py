"""Faces and mouths.

Expressions are face-bone states (expression, gaze, blink, mouth) plus optional
ear values, keyed with constant interpolation like Doodle Studio's drawings.
Mouth sets reuse the 3D Bunny's DS_Face node group on a second face object,
so each of the 14 approved sets wraps onto the head with the same ink, boil and
per-expression mouth offsets as the built-in mouths.
"""
import bpy

from . import index, paths

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
    data = item['data']
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
    if key and arm.animation_data and arm.animation_data.action:
        from .motions import _fcurves
        for fc in _fcurves(arm):
            if fc.data_path.startswith('pose.bones["face"]'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    index.mark_used(item['id'])


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
    fc = mod.driver_add(f'["{ids["Speech Mouth"]}"]')
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
                    mod[s.identifier] = bmod[s.identifier]
                except Exception:
                    pass
        mod[bids['Fills']] = fills
        mod[bids['Strokes']] = strokes
        mod[bids['Blink']] = 0
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
