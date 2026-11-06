"""Lip sync from audio: key mouth shapes from a voice file (Rhubarb if installed, loudness otherwise)."""
import os
import subprocess
import bpy
from . import _util
from ..compat import strips_all, fcurves_of
from .. import uxfit

LABEL, ICON, GROUP = 'Lip sync', 'SPEAKER', 'Animation'
# Rhubarb mouth letters: A closed (M,B,P), B slightly open, C open (eh), D wide (aa), E round (oh),
# F pucker (oo), G f/v, H l, X rest
SHAPES = 'XABCDEFGH'
DEFAULT_MAP = 'X=rest, A=closed, B=mid, C=open, D=wide, E=round, F=oo, G=fv, H=l'


class CTK_LipProps(bpy.types.PropertyGroup):
    source: bpy.props.EnumProperty(name='Audio', items=[('STRIPS', 'Sound strips in this scene', ''), ('FILE', 'A file', '')])
    filepath: bpy.props.StringProperty(name='Voice file', subtype='FILE_PATH')
    target: bpy.props.EnumProperty(name='Mouth is', items=[
        ('SHAPEKEYS', 'Shape keys', 'One shape key per mouth (names in the map)'),
        ('PROPERTY', 'A number (2D swaps / mouth sets)', 'Writes the mouth index into a custom property'),
        ('BONE', 'A jaw bone', 'Opens a jaw bone by rotation')])
    mapping: bpy.props.StringProperty(name='Map', default=DEFAULT_MAP,
                                      description='Which of your shapes each mouth letter uses. For a number, write X=0, A=1 ...')
    prop_name: bpy.props.StringProperty(name='Property', default='mouth')
    bone: bpy.props.StringProperty(name='Jaw bone', default='jaw')
    open_angle: bpy.props.FloatProperty(name='Jaw open', default=0.35, subtype='ANGLE')
    hold: bpy.props.IntProperty(name='Hold each mouth (frames)', default=2, min=1, max=10)
    sensitivity: bpy.props.FloatProperty(name='Sensitivity', default=1.0, min=0.2, max=4)


def _parse_map(text):
    out = {}
    for part in text.split(','):
        if '=' in part:
            a, b = part.split('=', 1)
            out[a.strip().upper()] = b.strip()
    return out


def _sounds(context, props):
    """[(path, start_frame)]"""
    if props.source == 'FILE':
        return [(bpy.path.abspath(props.filepath), context.scene.frame_start)] if props.filepath else []
    out = []
    for s in strips_all(context.scene):
        if s.type == 'SOUND' and s.sound and not s.mute:
            out.append((bpy.path.abspath(s.sound.filepath), s.frame_start))
    return out


def analyse_loudness(path, fps, sensitivity=1.0):
    """Return one mouth letter per frame from loudness + brightness."""
    import aud
    import numpy as np
    snd = aud.Sound(path).resample(16000, False) if hasattr(aud.Sound, 'resample') else aud.Sound(path)
    data = np.asarray(snd.data())
    if data.ndim > 1:
        data = data.mean(axis=1)
    rate = 16000
    hop = rate / fps
    n = int(len(data) / hop)
    rms = np.zeros(n)
    zcr = np.zeros(n)
    for i in range(n):
        seg = data[int(i * hop):int((i + 1) * hop)]
        if len(seg) == 0:
            continue
        rms[i] = float(np.sqrt((seg ** 2).mean()))
        zcr[i] = float((np.abs(np.diff(np.sign(seg))) > 0).mean())
    if n == 0 or rms.max() <= 0:
        return []
    ref = np.percentile(rms[rms > 0], 90) if (rms > 0).any() else 1
    lv = np.clip(rms / max(ref, 1e-6) * sensitivity, 0, 2)
    zmed = np.median(zcr[lv > 0.2]) if (lv > 0.2).any() else 0.1
    out = []
    for i in range(n):
        v = lv[i]
        if v < 0.12:
            out.append('X')
        elif v < 0.3:
            out.append('B' if zcr[i] > zmed else 'A')
        elif v < 0.6:
            out.append('C' if zcr[i] >= zmed else 'E')
        else:
            out.append('D' if zcr[i] >= zmed * 0.8 else 'F')
    return out


def analyse_rhubarb(exe, path, fps):
    r = subprocess.run([exe, '-f', 'tsv', '--extendedShapes', 'GHX', path], capture_output=True, text=True, timeout=600)
    rows = []
    for line in r.stdout.splitlines():
        parts = line.strip().split('\t')
        if len(parts) == 2:
            try:
                rows.append((float(parts[0]), parts[1].strip()))
            except ValueError:
                pass
    if not rows:
        raise RuntimeError(r.stderr.strip()[-200:] or 'Rhubarb gave no output')
    end = rows[-1][0]
    n = int(end * fps) + 1
    out = []
    j = 0
    for i in range(n):
        t = i / fps
        while j + 1 < len(rows) and rows[j + 1][0] <= t:
            j += 1
        out.append(rows[j][1])
    return out


def enforce_hold(letters, hold):
    out = list(letters)
    i = 0
    while i < len(out):
        j = i
        while j < len(out) and out[j] == out[i]:
            j += 1
        if j - i < hold and i > 0:
            for k in range(i, min(j, len(out))):
                out[k] = out[i - 1]
        i = j
    return out


def write_keys(context, obj, props, letters, start):
    m = _parse_map(props.mapping)
    prev = None
    keyed = 0
    if props.target == 'SHAPEKEYS':
        keys = obj.data.shape_keys.key_blocks if obj.data and getattr(obj.data, 'shape_keys', None) else None
        if not keys:
            raise RuntimeError('The active object has no shape keys')
        names = {m.get(L, L) for L in SHAPES} & set(keys.keys())
        if not names:
            raise RuntimeError('None of the mapped names match the shape keys. Edit the map')
    for i, L in enumerate(letters):
        if L == prev:
            continue
        f = start + i
        if props.target == 'SHAPEKEYS':
            want = m.get(L, L)
            for nm in names:
                kb = keys[nm]
                kb.value = 1.0 if nm == want else 0.0
                kb.keyframe_insert('value', frame=f)
        elif props.target == 'PROPERTY':
            try:
                val = int(m.get(L, SHAPES.index(L)))
            except ValueError:
                val = SHAPES.index(L)
            obj[props.prop_name] = val
            obj.keyframe_insert(f'["{props.prop_name}"]', frame=f)
        else:
            pb = obj.pose.bones.get(props.bone)
            if not pb:
                raise RuntimeError(f'No bone named {props.bone}')
            amount = {'X': 0, 'A': 0, 'B': .3, 'C': .6, 'D': 1, 'E': .5, 'F': .3, 'G': .15, 'H': .4}.get(L, .3)
            pb.rotation_mode = 'XYZ'
            pb.rotation_euler.x = amount * props.open_angle
            pb.keyframe_insert('rotation_euler', index=0, frame=f, group=pb.name)
        prev = L
        keyed += 1
    if props.target == 'PROPERTY':
        for fc in fcurves_of(obj):
            if fc.data_path == f'["{props.prop_name}"]':
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    return keyed


class CTK_OT_lipsync(bpy.types.Operator):
    """Key the mouth of the active object from the voice audio"""
    bl_idname = 'ctk.lipsync'
    bl_label = 'Sync lips'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.ctk_lip
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, 'Select the character or mouth object')
            return {'CANCELLED'}
        sounds = _sounds(context, props)
        if not sounds:
            self.report({'WARNING'}, 'No audio found: add a sound strip or choose a file')
            return {'CANCELLED'}
        fps = context.scene.render.fps / context.scene.render.fps_base
        from . import _util as U
        pr = U.addon_prefs()
        exe = bpy.path.abspath(pr.rhubarb_path) if pr and pr.rhubarb_path else ''
        total = 0
        how = 'loudness'
        for path, start in sounds:
            try:
                if exe and os.path.exists(exe):
                    letters = analyse_rhubarb(exe, path, fps)
                    how = 'Rhubarb'
                else:
                    letters = analyse_loudness(path, fps, props.sensitivity)
                letters = enforce_hold(letters, props.hold)
                total += write_keys(context, obj, props, letters, int(start))
            except Exception as e:
                self.report({'WARNING'}, f'{os.path.basename(path)}: {e}')
                return {'CANCELLED'}
        self.report({'INFO'}, f'{total} mouth changes keyed ({how})')
        return {'FINISHED'}


CLASSES = (CTK_LipProps, CTK_OT_lipsync)


def register_extra():
    bpy.types.Scene.ctk_lip = bpy.props.PointerProperty(type=CTK_LipProps)


def unregister_extra():
    del bpy.types.Scene.ctk_lip


def draw(layout, context):
    p = context.scene.ctk_lip
    col = layout.column(align=True)
    col.prop(p, 'source', text='')
    if p.source == 'FILE':
        col.prop(p, 'filepath', text='')
    col.prop(p, 'target', text='')
    if p.target == 'PROPERTY':
        col.prop(p, 'prop_name')
    elif p.target == 'BONE':
        col.prop(p, 'bone')
        col.prop(p, 'open_angle')
    if p.target != 'BONE':
        col.prop(p, 'mapping', text='Map')
    row = col.row(align=True)
    row.prop(p, 'hold', text='Hold')
    row.prop(p, 'sensitivity', text='Sens.')
    r = layout.row()
    r.scale_y = 1.3
    r.operator('ctk.lipsync', icon='SPEAKER')
    pr = _util.addon_prefs()
    if pr and not pr.rhubarb_path:
        uxfit.wrap(layout, context, 'Sharper sync: add rhubarb.exe in Preferences', icon='INFO')
