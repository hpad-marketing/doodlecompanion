"""Stop-motion mode: the whole scene animates on 2s, 3s or 4s with one switch.

Non-destructive: it adds Stepped (and, if you want them, Noise) modifiers to the animation
curves and takes them away again when switched off. Your keys never change. Touches:
  jitter   small hand-placed wobble on every moving object and the camera
  boil     Grease Pencil lines (and Line Art ink) redraw a little on each step
  flicker  lights breathe a little, like practical lamps on a set
  hold     procedural text, visualizers, ropes, cloth and simulations step too (a hold modifier)
  models   solid 3D models boil a little on each step"""
import json
import bpy
from ..compat import fcurves_of
from .. import uxfit

LABEL, ICON, GROUP = 'Stop-motion mode', 'RENDER_ANIMATION', 'Animation'
TAG = 'ctk_stopmo_state'  # JSON text on the scene while stop motion is on


class CTK_StopmoProps(bpy.types.PropertyGroup):
    step: bpy.props.IntProperty(name='On', default=2, min=1, max=12,
                                description='Hold every pose this many frames (2 = on twos)')
    jitter: bpy.props.FloatProperty(name='Jitter', default=0.0, min=0.0, max=0.2, unit='LENGTH',
                                    description='Hand-placed wobble on moving objects and the camera')
    boil: bpy.props.BoolProperty(name='Line boil', default=True,
                                 description='Grease Pencil lines redraw a little each step')
    flicker: bpy.props.FloatProperty(name='Light flicker', default=0.0, min=0.0, max=0.5, subtype='FACTOR')
    hold: bpy.props.BoolProperty(name='Step procedural too', default=True,
                                 description='Procedural text, visualizers, ropes, cloth and simulations hold for the same frames')
    boil_models: bpy.props.BoolProperty(name='Boil 3D models', default=False,
                                        description='Solid models shift a hair on every step, like hand-made puppets')


def _ids(scene):
    seen = []
    for o in scene.objects:
        for idb in (o, getattr(o, 'data', None), getattr(getattr(o, 'data', None), 'shape_keys', None)):
            if idb is not None and idb not in seen:
                seen.append(idb)
    return seen


def _key_once(idb, path, index=-1):
    """Make sure a curve exists so a modifier has something to sit on. Returns True if we made it."""
    before = {(fc.data_path, fc.array_index) for fc in fcurves_of(idb)}
    idb.keyframe_insert(path, index=index, frame=bpy.context.scene.frame_start)
    after = {(fc.data_path, fc.array_index) for fc in fcurves_of(idb)}
    return sorted(after - before)


def state(scene):
    try:
        return json.loads(scene.get(TAG, '')) if scene.get(TAG) else None
    except ValueError:
        return None


def is_on(scene):
    return bool(scene.get(TAG))


def switch_on(scene):
    if is_on(scene):
        switch_off(scene)
    p = scene.ctk_stopmo
    made = []  # [id kind, name, owner, data_path, index] curves we created
    import random
    rnd = random.Random(7)
    if p.jitter > 0:
        for o in scene.objects:
            moving = bool(fcurves_of(o)) or o.type == 'CAMERA'
            if not moving or o.type == 'LIGHT':
                continue
            if not any(fc.data_path == 'location' for fc in fcurves_of(o)):
                for path, idx in _key_once(o, 'location'):
                    made.append(['OBJECT', o.name, path, idx, o.location[idx]])
            for fc in fcurves_of(o):
                if fc.data_path == 'location':
                    n = fc.modifiers.new('NOISE')
                    n.strength = p.jitter * 2
                    n.scale = 1.0
                    n.phase = rnd.uniform(0, 1000)
                    n.blend_type = 'ADD'
    if p.flicker > 0:
        for o in scene.objects:
            if o.type != 'LIGHT':
                continue
            L = o.data
            if not any(fc.data_path == 'energy' for fc in fcurves_of(L)):
                for path, idx in _key_once(L, 'energy'):
                    made.append(['LIGHT', L.name, path, idx, L.energy])
            for fc in fcurves_of(L):
                if fc.data_path == 'energy':
                    n = fc.modifiers.new('NOISE')
                    n.strength = L.energy * p.flicker * 2
                    n.scale = 1.0
                    n.phase = rnd.uniform(0, 1000)
                    n.blend_type = 'ADD'
    # step everything (added last so it holds jitter and flicker too)
    for idb in _ids(scene):
        for fc in fcurves_of(idb):
            s = fc.modifiers.new('STEPPED')
            s.frame_step = p.step
            s.frame_offset = scene.frame_start
    boiled = []
    if p.boil:
        from . import gpkit
        for o in scene.objects:
            if o.type in {'GREASEPENCIL', 'GPENCIL'} and not any(m.name == 'CTK Line boil' for m in o.modifiers):
                gpkit.boil(o, 0.35, p.step)
                boiled.append(o.name)
    from . import boil3d
    held, mboiled = [], []
    for o in scene.objects:
        if p.hold and boil3d.is_live(o) and not o.modifiers.get(boil3d.HOLD):
            boil3d.add_hold(o, p.step, scene.frame_start)
            held.append(o.name)
        if p.boil_models and o.type == 'MESH' and not o.hide_render and not boil3d.is_flat(o) \
                and not o.modifiers.get(boil3d.BOIL):
            boil3d.add_boil(o, 0.006, p.step)
            mboiled.append(o.name)
    scene[TAG] = json.dumps({'made': made, 'boiled': boiled, 'held': held, 'mboiled': mboiled, 'step': p.step,
                             'jitter': p.jitter > 0, 'flicker': p.flicker > 0})
    return True


def switch_off(scene):
    info = state(scene)
    if not info:
        return False
    for idb in _ids(scene):
        for fc in fcurves_of(idb):
            for m in list(fc.modifiers):
                if m.type == 'STEPPED':
                    fc.modifiers.remove(m)
                elif m.type == 'NOISE' and m.scale == 1.0 and (
                        (fc.data_path == 'location' and info.get('jitter')) or
                        (fc.data_path == 'energy' and info.get('flicker'))):
                    fc.modifiers.remove(m)
    for kind, name, path, idx, value in info.get('made', []):
        idb = (bpy.data.objects if kind == 'OBJECT' else bpy.data.lights).get(name)
        if idb is None:
            continue
        if idb.animation_data and idb.animation_data.action:
            try:
                idb.keyframe_delete(path, index=idx, frame=scene.frame_start)
            except Exception:
                pass
        # put the value back as it was before the helper key
        cur = getattr(idb, path)
        if hasattr(cur, '__setitem__'):
            cur[idx] = value
        else:
            setattr(idb, path, value)
    for name in info.get('boiled', []):
        o = bpy.data.objects.get(name)
        if o:
            m = o.modifiers.get('CTK Line boil')
            if m:
                o.modifiers.remove(m)
    from . import boil3d
    for name in info.get('held', []):
        o = bpy.data.objects.get(name)
        if o:
            boil3d.remove(o, boil3d.HOLD)
    for name in info.get('mboiled', []):
        o = bpy.data.objects.get(name)
        if o:
            boil3d.remove(o, boil3d.BOIL)
    del scene[TAG]
    return True


class CTK_OT_stopmo(bpy.types.Operator):
    """Stop-motion mode on or off for the whole scene (your keys stay as they are)"""
    bl_idname = 'ctk.stopmo'
    bl_label = 'Stop-motion mode'
    bl_options = {'REGISTER', 'UNDO'}
    on: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        sc = context.scene
        if self.on:
            switch_on(sc)
            self.report({'INFO'}, f'Stop motion on {sc.ctk_stopmo.step}s')
        else:
            switch_off(sc)
        return {'FINISHED'}


CLASSES = (CTK_StopmoProps, CTK_OT_stopmo)


def register_extra():
    bpy.types.Scene.ctk_stopmo = bpy.props.PointerProperty(type=CTK_StopmoProps)


def unregister_extra():
    del bpy.types.Scene.ctk_stopmo


def draw(layout, context):
    sc = context.scene
    p = sc.ctk_stopmo
    on = is_on(sc)
    row = layout.row(align=True)
    row.scale_y = 1.3
    if on:
        row.operator('ctk.stopmo', text=f'Stop motion is on ({state(sc)["step"]}s): turn off', icon='CANCEL', depress=True).on = False
    else:
        row.operator('ctk.stopmo', text='Turn on stop motion', icon='RENDER_ANIMATION').on = True
    row = layout.row(align=True)
    row.prop(p, 'step', text='On')
    row.prop(p, 'jitter')
    row.prop(p, 'flicker', text='Flicker')
    row = uxfit.flow(layout, context, ['Line boil', 'Procedural', 'Boil models'], most=3)
    row.prop(p, 'boil', text='Line boil', toggle=True)
    row.prop(p, 'hold', text='Procedural', toggle=True)
    row.prop(p, 'boil_models', text='Boil models', toggle=True)
    if on:
        uxfit.wrap(layout, context, 'Changed a setting? Turn on again to apply', icon='INFO')
