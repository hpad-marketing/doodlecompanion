"""Bake on Export, with Unbake.

Everything live in the Toolkit (spring bones, camera shake, stop-motion stepping, jitter and
flicker, rope/cloth/hair and speed-line simulations) is turned into plain keys and caches in one
go, so an export or render gets exactly what you saw. Unbake puts every live tool back.

The Master Launcher calls this automatically when you press Export (DOODLE_MASTER['bake']).
The buttons here do the same by hand."""
import json
import bpy
from ..compat import fcurves_of

LABEL, ICON, GROUP = 'Bake for export', 'FILE_CACHE', 'Output'
KEY = 'ctk_baked'


def _ids(scene):
    seen = []
    for o in scene.objects:
        for idb in (o, getattr(o, 'data', None), getattr(getattr(o, 'data', None), 'shape_keys', None)):
            if idb is not None and idb not in seen and getattr(idb, 'animation_data', None):
                seen.append(idb)
    return seen


def _coll(idb):
    for name in ('objects', 'lights', 'cameras', 'shape_keys', 'meshes', 'curves', 'armatures'):
        c = getattr(bpy.data, name)
        if idb.name in c and c[idb.name] == idb:
            return name
    return None


def _has_sim(tree, seen=None):
    seen = seen if seen is not None else set()
    if tree is None or tree.name in seen:
        return False
    seen.add(tree.name)
    for n in tree.nodes:
        if n.bl_idname == 'GeometryNodeSimulationOutput':
            return True
        if getattr(n, 'node_tree', None) is not None and _has_sim(n.node_tree, seen):
            return True
    return False


def _sim_objects(scene):
    return [o for o in scene.objects
            if any(m.type == 'NODES' and _has_sim(m.node_group) for m in o.modifiers)]


def _keep_action(idb, token):
    ad = idb.animation_data
    if not ad or not ad.action:
        return
    if any(r[1] == idb.name and r[0] == _coll(idb) for r in token['actions']):
        return
    copy = ad.action.copy()
    copy.name = ad.action.name + ' (before bake)'
    copy.use_fake_user = True
    token['actions'].append([_coll(idb), idb.name, copy.name, ad.action.name])


def _bake_curves(idb, f0, f1):
    """Write what the curve modifiers make as keys, then drop the modifiers."""
    n = 0
    for fc in fcurves_of(idb):
        if not len(fc.modifiers):
            continue
        stepped = any(m.type == 'STEPPED' for m in fc.modifiers)
        vals = [(f, fc.evaluate(f)) for f in range(f0, f1 + 1)]
        for m in list(fc.modifiers):
            fc.modifiers.remove(m)
        for i in reversed(range(len(fc.keyframe_points))):
            if f0 <= fc.keyframe_points[i].co.x <= f1:
                fc.keyframe_points.remove(fc.keyframe_points[i], fast=True)
        for f, v in vals:
            k = fc.keyframe_points.insert(f, v, options={'FAST'})
            k.interpolation = 'CONSTANT' if stepped else 'LINEAR'
        fc.update()
        n += 1
    return n


def _sim_bake(scene, objs, f0, f1, delete=False):
    if not objs:
        return
    keep = scene.frame_start, scene.frame_end
    scene.frame_start, scene.frame_end = f0, f1
    try:
        with bpy.context.temp_override(selected_objects=objs, selected_editable_objects=objs,
                                       active_object=objs[0], object=objs[0], scene=scene):
            if delete:
                return bpy.ops.object.simulation_nodes_cache_delete(selected=True) == {'FINISHED'}
            return bpy.ops.object.simulation_nodes_cache_bake(selected=True) == {'FINISHED'}
    finally:
        scene.frame_start, scene.frame_end = keep


def bake(scene, frame_start=None, frame_end=None):
    """Bake every live Toolkit effect in the scene. Returns a JSON-friendly token for unbake()."""
    from . import springs, stopmo
    f0 = scene.frame_start if frame_start is None else int(frame_start)
    f1 = scene.frame_end if frame_end is None else int(frame_end)
    token = {'range': [f0, f1], 'actions': [], 'springs': [], 'sims': [], 'curves': 0,
             'stopmo': bool(stopmo.is_on(scene)), 'new_actions': []}
    # keep a copy of every action we are about to change
    spring_rigs = springs._rigs(scene)
    for idb in _ids(scene):
        if any(len(fc.modifiers) for fc in fcurves_of(idb)) or idb in spring_rigs:
            _keep_action(idb, token)
    for rig in spring_rigs:
        if not (rig.animation_data and rig.animation_data.action):
            token['new_actions'].append(rig.name)
    # springs -> keys (stepped too, when stop motion is on)
    if spring_rigs:
        token['springs'] = springs.bake(scene, f0, f1)
        if token['stopmo']:
            step = stopmo.state(scene)['step']
            for rig in spring_rigs:
                for fc in fcurves_of(rig):
                    if not any(m.type == 'STEPPED' for m in fc.modifiers):
                        s = fc.modifiers.new('STEPPED')
                        s.frame_step, s.frame_offset = step, scene.frame_start
    # shake, stepping, jitter, flicker -> keys
    for idb in _ids(scene):
        token['curves'] += _bake_curves(idb, f0, f1)
    if token['stopmo']:
        token['stopmo_info'] = scene[stopmo.TAG]
        del scene[stopmo.TAG]
    # simulations -> caches
    sims = _sim_objects(scene)
    if sims:
        if _sim_bake(scene, sims, f0, f1):
            token['sims'] = [o.name for o in sims]
    scene[KEY] = json.dumps(token)
    return token


def unbake(scene, token=None):
    from . import springs, stopmo
    token = token or (json.loads(scene[KEY]) if scene.get(KEY) else None)
    if not token:
        return False
    f0, f1 = token['range']
    for coll, name, copy_name, orig_name in token['actions']:
        idb = getattr(bpy.data, coll).get(name) if coll else None
        copy = bpy.data.actions.get(copy_name)
        if idb is None or copy is None:
            continue
        ad = idb.animation_data or idb.animation_data_create()
        baked = ad.action
        slot_id = getattr(getattr(ad, 'action_slot', None), 'identifier', None)
        ad.action = copy
        if hasattr(ad, 'action_slot') and ad.action_slot is None and len(getattr(copy, 'slots', [])):
            slot = next((s for s in copy.slots if s.identifier == slot_id), copy.slots[0])
            ad.action_slot = slot
        copy.use_fake_user = False
        if baked is not None and baked != copy and baked.users == 0:
            bpy.data.actions.remove(baked)
        copy.name = orig_name
    for name in token.get('new_actions', []):
        o = bpy.data.objects.get(name)
        if o and o.animation_data and o.animation_data.action:
            a = o.animation_data.action
            o.animation_data.action = None
            if a.users == 0:
                bpy.data.actions.remove(a)
    springs.unbake_flags(token.get('springs', []))
    if token.get('stopmo_info'):
        scene[stopmo.TAG] = token['stopmo_info']
    sims = [bpy.data.objects[n] for n in token.get('sims', []) if n in bpy.data.objects]
    if sims:
        _sim_bake(scene, sims, f0, f1, delete=True)
    if KEY in scene:
        del scene[KEY]
    return True


def is_baked(scene):
    return bool(scene.get(KEY))


class CTK_OT_bake_all(bpy.types.Operator):
    """Bake every live effect (springs, shake, stop motion, simulations) for export"""
    bl_idname = 'ctk.bake_all'
    bl_label = 'Bake everything'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if is_baked(context.scene):
            self.report({'INFO'}, 'Already baked. Unbake first to bake again')
            return {'CANCELLED'}
        t = bake(context.scene)
        self.report({'INFO'}, f"Baked {len(t['springs'])} spring bones, {t['curves']} curves, {len(t['sims'])} simulations")
        return {'FINISHED'}


class CTK_OT_unbake_all(bpy.types.Operator):
    """Put every live effect back the way it was before baking"""
    bl_idname = 'ctk.unbake_all'
    bl_label = 'Unbake'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not unbake(context.scene):
            self.report({'INFO'}, 'Nothing is baked')
            return {'CANCELLED'}
        return {'FINISHED'}


CLASSES = (CTK_OT_bake_all, CTK_OT_unbake_all)


def draw(layout, context):
    row = layout.row(align=True)
    row.scale_y = 1.2
    if is_baked(context.scene):
        row.label(text='Baked for export', icon='CHECKMARK')
        row.operator('ctk.unbake_all', icon='LOOP_BACK')
    else:
        row.operator('ctk.bake_all', icon='FILE_CACHE')
    layout.label(text='Export from the Launcher bakes this for you', icon='INFO')
