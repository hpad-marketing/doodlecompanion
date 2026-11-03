"""Music visualizer kit + react to the music, on Blender 5.2's Sample Sound Frequencies node
(live, no baking). Bones (e.g. Bunny's ears) bop by baked keys, which works in any version."""
import math
import os
import bpy
from . import _util
from ._nodes import Tree, O, I, set_input, draw_modifier_inputs

LABEL, ICON, GROUP = 'Music visualizer + react', 'SOUND', 'Motion design'
LOOKS = [('BARS', 'Bars', 'Equalizer bars'), ('RINGS', 'Ring', 'Bars around a circle'),
         ('WAVE', 'Wave ribbon', 'A ribbon shaped by the frequencies'), ('DOTS', 'Pulsing dots', 'Dots that grow with the music')]
REACTS = [('SCALE', 'Pulse', 'Grows with the beat'), ('BOUNCE', 'Bounce', 'Jumps up with the beat'),
          ('WIGGLE', 'Wiggle', 'Wobbles with the music'), ('GLOW', 'Glow', 'Lights up with the music')]
BANDS = {'Bass': (30, 160), 'Mids': (300, 2000), 'Highs': (3000, 12000)}


def available():
    return hasattr(bpy.types, 'GeometryNodeSampleSoundFrequencies')


def scene_sound(scene):
    """(sound, start seconds) from the first sound strip."""
    from ..compat import strips_all
    fps = scene.render.fps / scene.render.fps_base
    for s in strips_all(scene):
        if s.type == 'SOUND' and s.sound:
            return s.sound, (s.frame_start - scene.frame_start) / fps
    return None, 0.0


def _sample(t, low, high):
    st = t.n('GeometryNodeInputSceneTime')
    tm = t.n('ShaderNodeMath', operation='SUBTRACT')
    t.link(O(st, 'Seconds'), tm.inputs[0])
    t.link(t.i('Start (seconds)'), tm.inputs[1])
    ss = t.n('GeometryNodeSampleSoundFrequencies')
    t.link(t.i('Sound'), I(ss, 'Sound'))
    t.link(tm.outputs[0], I(ss, 'Time'))
    for sock, v in ((I(ss, 'Low'), low), (I(ss, 'High'), high)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        else:
            t.link(v, sock)
    return O(ss, 'Amplitude')


def _m(t, op, a, b):
    n = t.n('ShaderNodeMath', operation=op)
    for k, v in ((0, a), (1, b)):
        if isinstance(v, (int, float)):
            n.inputs[k].default_value = v
        else:
            t.link(v, n.inputs[k])
    return n.outputs[0]


def _common(t):
    t.socket('Geometry', 'OUTPUT', 'NodeSocketGeometry')
    t.socket('Sound', 'INPUT', 'NodeSocketSound')
    t.socket('Start (seconds)', 'INPUT', 'NodeSocketFloat', 0.0)


def build_visualizer(look):
    t = Tree('CTK Visualizer ' + look.title())
    if not t.fresh:
        return t.tree
    _common(t)
    t.socket('Bars', 'INPUT', 'NodeSocketInt', 24, 2, 256)
    t.socket('Lowest note (Hz)', 'INPUT', 'NodeSocketFloat', 40.0, 10.0, 2000.0)
    t.socket('Highest note (Hz)', 'INPUT', 'NodeSocketFloat', 10000.0, 200.0, 20000.0)
    t.socket('Height', 'INPUT', 'NodeSocketFloat', 3.0, 0.0, 100.0)
    t.socket('Width', 'INPUT', 'NodeSocketFloat', 6.0, 0.1, 100.0)
    t.socket('Thickness', 'INPUT', 'NodeSocketFloat', 0.7, 0.05, 1.0)
    t.socket('Material', 'INPUT', 'NodeSocketMaterial')
    # band per point: log-spaced between low and high
    idx = t.n('GeometryNodeInputIndex')
    n_f = t.i('Bars')
    ratio = _m(t, 'DIVIDE', t.i('Highest note (Hz)'), t.i('Lowest note (Hz)'))
    f0 = _m(t, 'DIVIDE', O(idx, 'Index'), n_f)
    f1 = _m(t, 'DIVIDE', _m(t, 'ADD', O(idx, 'Index'), 1.0), n_f)
    lo = _m(t, 'MULTIPLY', t.i('Lowest note (Hz)'), _m(t, 'POWER', ratio, f0))
    hi = _m(t, 'MULTIPLY', t.i('Lowest note (Hz)'), _m(t, 'POWER', ratio, f1))
    # louder highs look flat: lift them a little
    amp = _m(t, 'MULTIPLY', _sample(t, lo, hi), _m(t, 'ADD', 1.0, _m(t, 'MULTIPLY', f0, 3.0)))
    h = _m(t, 'MAXIMUM', _m(t, 'MULTIPLY', amp, t.i('Height')), 0.02)
    if look in ('BARS', 'DOTS', 'RINGS'):
        if look == 'RINGS':
            base = t.n('GeometryNodeCurvePrimitiveCircle')
            t.link(t.i('Bars'), I(base, 'Resolution'))
            t.link(_m(t, 'DIVIDE', t.i('Width'), 2.0), I(base, 'Radius'))
            pts = t.n('GeometryNodeCurveToPoints', mode='EVALUATED')
            t.link(O(base, 'Curve'), I(pts, 'Curve'))
            points, rot = O(pts, 'Points'), O(pts, 'Rotation')
        else:
            ml = t.n('GeometryNodeMeshLine', mode='END_POINTS')
            t.link(t.i('Bars'), I(ml, 'Count'))
            half = _m(t, 'MULTIPLY', t.i('Width'), -0.5)
            cs = t.n('ShaderNodeCombineXYZ')
            t.link(half, I(cs, 'X'))
            ce = t.n('ShaderNodeCombineXYZ')
            t.link(_m(t, 'MULTIPLY', t.i('Width'), 0.5), I(ce, 'X'))
            t.link(O(cs, 'Vector'), I(ml, 'Start Location'))
            t.link(O(ce, 'Vector'), I(ml, 'Offset'))
            mp = t.n('GeometryNodeMeshToPoints')
            t.link(O(ml, 'Mesh'), I(mp, 'Mesh'))
            points, rot = O(mp, 'Points'), None
        step = _m(t, 'MULTIPLY', _m(t, 'DIVIDE', t.i('Width'), n_f), t.i('Thickness'))
        if look == 'DOTS':
            shape = t.n('GeometryNodeMeshUVSphere')
            t.link(_m(t, 'MULTIPLY', step, 0.5), I(shape, 'Radius'))
            scale = _m(t, 'ADD', 0.3, _m(t, 'MULTIPLY', amp, 2.0))
        else:
            shape = t.n('GeometryNodeMeshCube')
            sz = t.n('ShaderNodeCombineXYZ')
            t.link(step, I(sz, 'X'))
            t.link(step, I(sz, 'Y'))
            I(sz, 'Z').default_value = 1.0
            t.link(O(sz, 'Vector'), I(shape, 'Size'))
            tr = t.n('GeometryNodeTransform')
            I(tr, 'Translation').default_value = (0, 0, 0.5)
            t.link(O(shape, 'Mesh'), I(tr, 'Geometry'))
            shape_out = O(tr, 'Geometry')
            sv = t.n('ShaderNodeCombineXYZ')
            I(sv, 'X').default_value = 1.0
            I(sv, 'Y').default_value = 1.0
            t.link(h, I(sv, 'Z'))
            scale = O(sv, 'Vector')
        inst = t.n('GeometryNodeInstanceOnPoints')
        t.link(points, I(inst, 'Points'))
        t.link(shape_out if look != 'DOTS' else O(shape, 'Mesh'), I(inst, 'Instance'))
        t.link(scale, I(inst, 'Scale'))
        if rot is not None:
            # bars stand out from the ring, along its plane
            rt = t.n('FunctionNodeRotateRotation') if hasattr(bpy.types, 'FunctionNodeRotateRotation') else None
            if rt:
                t.link(rot, rt.inputs[0])
                rt.inputs[1].default_value = (math.pi / 2, 0, 0)
                t.link(rt.outputs[0], I(inst, 'Rotation'))
            else:
                t.link(rot, I(inst, 'Rotation'))
        real = t.n('GeometryNodeRealizeInstances')
        t.link(O(inst, 'Instances'), I(real, 'Geometry'))
        geo = O(real, 'Geometry')
    else:  # WAVE ribbon
        line = t.n('GeometryNodeCurvePrimitiveLine')
        a = t.n('ShaderNodeCombineXYZ')
        t.link(_m(t, 'MULTIPLY', t.i('Width'), -0.5), I(a, 'X'))
        b = t.n('ShaderNodeCombineXYZ')
        t.link(_m(t, 'MULTIPLY', t.i('Width'), 0.5), I(b, 'X'))
        t.link(O(a, 'Vector'), I(line, 'Start'))
        t.link(O(b, 'Vector'), I(line, 'End'))
        rs = t.n('GeometryNodeResampleCurve', mode='COUNT')
        t.link(O(line, 'Curve'), I(rs, 'Curve'))
        t.link(t.i('Bars'), I(rs, 'Count'))
        off = t.n('ShaderNodeCombineXYZ')
        t.link(h, I(off, 'Z'))
        sp = t.n('GeometryNodeSetPosition')
        t.link(O(rs, 'Curve'), I(sp, 'Geometry'))
        t.link(O(off, 'Vector'), I(sp, 'Offset'))
        prof = t.n('GeometryNodeCurvePrimitiveLine')
        p1 = t.n('ShaderNodeCombineXYZ')
        t.link(_m(t, 'MULTIPLY', t.i('Thickness'), 0.3), I(p1, 'Y'))
        t.link(O(p1, 'Vector'), I(prof, 'End'))
        c2m = t.n('GeometryNodeCurveToMesh')
        t.link(O(sp, 'Geometry'), I(c2m, 'Curve'))
        t.link(O(prof, 'Curve'), I(c2m, 'Profile Curve'))
        geo = O(c2m, 'Mesh')
    sm = t.n('GeometryNodeSetMaterial')
    t.link(geo, I(sm, 'Geometry'))
    t.link(t.i('Material'), I(sm, 'Material'))
    t.out(O(sm, 'Geometry'))
    return t.tree


def build_react():
    t = Tree('CTK React To Music')
    if not t.fresh:
        return t.tree
    t.socket('Geometry', 'INPUT', 'NodeSocketGeometry')
    _common(t)
    for nm, dv in (('Bass', 1.0), ('Mids', 0.3), ('Highs', 0.0)):
        t.socket(nm, 'INPUT', 'NodeSocketFloat', dv, 0.0, 10.0)
    for nm, dv in (('Pulse', 0.3), ('Bounce', 0.0), ('Wiggle', 0.0)):
        t.socket(nm, 'INPUT', 'NodeSocketFloat', dv, 0.0, 10.0)
    amp = None
    for nm, (lo, hi) in BANDS.items():
        a = _m(t, 'MULTIPLY', _sample(t, float(lo), float(hi)), t.i(nm))
        amp = a if amp is None else _m(t, 'ADD', amp, a)
    # pulse: scale around the origin
    s = _m(t, 'ADD', 1.0, _m(t, 'MULTIPLY', amp, t.i('Pulse')))
    tr = t.n('GeometryNodeTransform')
    t.link(t.i('Geometry'), I(tr, 'Geometry'))
    sv = t.n('ShaderNodeCombineXYZ')
    for ax in 'XYZ':
        t.link(s, I(sv, ax))
    t.link(O(sv, 'Vector'), I(tr, 'Scale'))
    bz = t.n('ShaderNodeCombineXYZ')
    t.link(_m(t, 'MULTIPLY', amp, t.i('Bounce')), I(bz, 'Z'))
    t.link(O(bz, 'Vector'), I(tr, 'Translation'))
    # wiggle: noise offset that grows with the music
    pos = t.n('GeometryNodeInputPosition')
    st = t.n('GeometryNodeInputSceneTime')
    nz = t.n('ShaderNodeTexNoise', noise_dimensions='4D')
    t.link(O(pos, 'Position'), I(nz, 'Vector'))
    t.link(O(st, 'Seconds'), I(nz, 'W'))
    I(nz, 'Scale').default_value = 2.0
    cen = t.n('ShaderNodeVectorMath', operation='SUBTRACT')
    t.link(O(nz, 'Color'), cen.inputs[0])
    cen.inputs[1].default_value = (0.5, 0.5, 0.5)
    sc = t.n('ShaderNodeVectorMath', operation='SCALE')
    t.link(cen.outputs[0], sc.inputs[0])
    t.link(_m(t, 'MULTIPLY', amp, _m(t, 'MULTIPLY', t.i('Wiggle'), 0.3)), I(sc, 'Scale'))
    sp = t.n('GeometryNodeSetPosition')
    t.link(O(tr, 'Geometry'), I(sp, 'Geometry'))
    t.link(sc.outputs[0], I(sp, 'Offset'))
    # glow: the materials read 'ctk_glow'
    sto = t.n('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    I(sto, 'Name').default_value = 'ctk_glow'
    t.link(O(sp, 'Geometry'), I(sto, 'Geometry'))
    t.link(amp, I(sto, 'Value'))
    t.out(O(sto, 'Geometry'))
    return t.tree


def add_glow(obj, strength=4.0):
    """Material emission follows the 'ctk_glow' attribute."""
    for slot in obj.material_slots:
        m = slot.material
        if not m or not m.use_nodes or 'CTK glow' in m.node_tree.nodes:
            continue
        nt = m.node_tree
        b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not b:
            continue
        at = nt.nodes.new('ShaderNodeAttribute')
        at.name = 'CTK glow'
        at.attribute_name = 'ctk_glow'
        mul = nt.nodes.new('ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        mul.inputs[1].default_value = strength
        nt.links.new(at.outputs['Fac'], mul.inputs[0])
        nt.links.new(mul.outputs[0], b.inputs['Emission Strength'])
        ec = b.inputs['Emission Color']
        ec.default_value = b.inputs['Base Color'].default_value


def _setup_mod(obj, group, context):
    m = obj.modifiers.new(group.name, 'NODES')
    m.node_group = group
    snd, start = scene_sound(context.scene)
    if snd:
        set_input(m, 'Sound', snd)
        set_input(m, 'Start (seconds)', start)
    return m, snd


# ---------------------------------------------------------- bones: baked keys (any version)

def band_envelope(path, fps, start_frame, frames, low, high):
    import aud
    import numpy as np
    snd = aud.Sound(path).resample(44100, False).rechannel(1)
    data = snd.data().reshape(-1)
    sr = 44100
    out = []
    win = int(sr / fps) * 2
    for f in range(frames):
        c = int((f + 0.5) * sr / fps)
        seg = data[max(0, c - win // 2): c + win // 2]
        if len(seg) < 64:
            out.append(0.0)
            continue
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        freqs = np.fft.rfftfreq(len(seg), 1 / sr)
        band = spec[(freqs >= low) & (freqs < high)]
        out.append(float(band.mean()) if len(band) else 0.0)
    peak = max(out) or 1.0
    return [v / peak for v in out]


def bop_bones(context, bones, amount_deg=20.0, band='Bass', path=None, start_frame=None):
    sc = context.scene
    if path is None:
        snd, start = scene_sound(sc)
        if not snd:
            raise RuntimeError('Add a sound strip (or pick a song) first')
        path = bpy.path.abspath(snd.filepath)
        start_frame = sc.frame_start + int(round(start * sc.render.fps / sc.render.fps_base))
    fps = sc.render.fps / sc.render.fps_base
    frames = sc.frame_end - start_frame + 1
    lo, hi = BANDS[band]
    env = band_envelope(path, fps, start_frame, frames, lo, hi)
    for pb in bones:
        pb.rotation_mode = 'XYZ' if pb.rotation_mode in ('QUATERNION', 'AXIS_ANGLE') else pb.rotation_mode
        base = pb.rotation_euler.x
        last = None
        for i, v in enumerate(env):
            val = base + math.radians(amount_deg) * v
            if last is not None and abs(val - last) < 0.01 and i % 4:
                continue
            pb.rotation_euler.x = val
            pb.keyframe_insert('rotation_euler', index=0, frame=start_frame + i)
            last = val
        pb.rotation_euler.x = base
    return len(env)


# ---------------------------------------------------------- operators

class CTK_OT_music_load(bpy.types.Operator):
    """Pick a song: it goes on the timeline as a sound strip at the start"""
    bl_idname = 'ctk.music_load'
    bl_label = 'Pick a song'
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.wav;*.mp3;*.ogg;*.flac;*.m4a;*.aac', options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from ..compat import strips
        sc = context.scene
        s = strips(sc).new_sound(os.path.basename(self.filepath), self.filepath, 1, sc.frame_start)
        fps = sc.render.fps / sc.render.fps_base
        sc.frame_end = max(sc.frame_end, int(sc.frame_start + s.frame_final_duration - 1))
        for o in sc.objects:
            for m in o.modifiers:
                if m.type == 'NODES' and m.node_group and m.node_group.name.startswith(('CTK Visualizer', 'CTK React')):
                    set_input(m, 'Sound', s.sound)
        self.report({'INFO'}, 'Song added (%.1f s)' % (s.frame_final_duration / fps))
        return {'FINISHED'}


class CTK_OT_visualizer(bpy.types.Operator):
    """Add a music visualizer that moves with the song on the timeline"""
    bl_idname = 'ctk.visualizer'
    bl_label = 'Add visualizer'
    bl_options = {'REGISTER', 'UNDO'}
    look: bpy.props.EnumProperty(items=LOOKS)

    @classmethod
    def poll(cls, context):
        return available()

    def execute(self, context):
        me = bpy.data.meshes.new('Visualizer')
        o = bpy.data.objects.new('Visualizer ' + self.look.title(), me)
        context.scene.collection.objects.link(o)
        o.location = context.scene.cursor.location
        m, snd = _setup_mod(o, build_visualizer(self.look), context)
        mat = bpy.data.materials.get('CTK Visualizer') or bpy.data.materials.new('CTK Visualizer')
        mat.use_nodes = True
        mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*_util.hex_to_linear('#E0A64B'), 1)
        set_input(m, 'Material', mat)
        if not snd:
            self.report({'WARNING'}, 'Added. Now pick a song so it can move')
        return {'FINISHED'}


class CTK_OT_react(bpy.types.Operator):
    """Make the selected objects react to the music"""
    bl_idname = 'ctk.react'
    bl_label = 'React to music'
    bl_options = {'REGISTER', 'UNDO'}
    how: bpy.props.EnumProperty(items=REACTS)

    @classmethod
    def poll(cls, context):
        return available()

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type == 'MESH']
        if not obs:
            self.report({'ERROR'}, 'Select meshes (for bones, use Bop bones)')
            return {'CANCELLED'}
        for o in obs:
            m = next((x for x in o.modifiers if x.node_group and x.node_group.name == 'CTK React To Music'), None)
            if not m:
                m, _ = _setup_mod(o, build_react(), context)
            for k in ('Pulse', 'Bounce', 'Wiggle'):
                set_input(m, k, 0.0)
            if self.how == 'SCALE':
                set_input(m, 'Pulse', 0.3)
            elif self.how == 'BOUNCE':
                set_input(m, 'Bounce', 0.6)
            elif self.how == 'WIGGLE':
                set_input(m, 'Wiggle', 1.0)
            else:
                add_glow(o)
        return {'FINISHED'}


class CTK_OT_bop_bones(bpy.types.Operator):
    """Key the selected bones (e.g. Bunny's ears) to bop to the music"""
    bl_idname = 'ctk.bop_bones'
    bl_label = 'Bop bones'
    bl_options = {'REGISTER', 'UNDO'}
    band: bpy.props.EnumProperty(items=[(k, k, '') for k in BANDS])
    amount: bpy.props.FloatProperty(name='Angle', default=20, min=1, max=90)

    def execute(self, context):
        bones = list(context.selected_pose_bones or [])
        if not bones:
            self.report({'ERROR'}, 'Select bones in Pose Mode')
            return {'CANCELLED'}
        try:
            n = bop_bones(context, bones, self.amount, self.band)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{len(bones)} bones keyed over {n} frames')
        return {'FINISHED'}


CLASSES = (CTK_OT_music_load, CTK_OT_visualizer, CTK_OT_react, CTK_OT_bop_bones)


def draw(layout, context):
    snd, _ = scene_sound(context.scene)
    layout.operator('ctk.music_load', text='Song: ' + (snd.name if snd else 'pick one'), icon='SOUND')
    if not available():
        layout.label(text='Visualizers need Blender 5.2', icon='INFO')
    else:
        g = layout.grid_flow(columns=2, align=True)
        for k, l, _ in LOOKS:
            g.operator('ctk.visualizer', text=l).look = k
        layout.label(text='Selected objects:')
        g = layout.grid_flow(columns=4, align=True)
        for k, l, _ in REACTS:
            g.operator('ctk.react', text=l).how = k
    layout.operator('ctk.bop_bones', icon='BONE_DATA')
    o = context.active_object
    if o:
        for m in o.modifiers:
            if m.type == 'NODES' and m.node_group and m.node_group.name.startswith(('CTK Visualizer', 'CTK React')):
                draw_modifier_inputs(layout.box(), m)
