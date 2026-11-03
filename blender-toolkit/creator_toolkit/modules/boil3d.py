"""Line boil on 3D models, and stop-motion hold for procedural animation.

Boil: the surface (and its ink outline) shifts a hair on every step, like a model re-sculpted or
redrawn each frame. Non-destructive: one Geometry Nodes modifier, first in the stack.

Hold: a Geometry Nodes modifier, last in the stack, that keeps whatever the modifiers above make
(procedural text, music visualizers, ropes, cloth, simulations) for N frames, so they step on 2s
with everything else. It uses a simulation zone, so play from the start once; Bake on Export
caches it."""
import bpy
from . import _nodes as N

LABEL, ICON, GROUP = 'Boil + hold for 3D', 'MOD_NOISE', 'Procedural & 2D'
BOIL, HOLD = 'CTK Mesh boil', 'CTK Stop-motion hold'
LIVE_MODS = {'NODES', 'CLOTH', 'SOFT_BODY', 'OCEAN', 'WAVE', 'DYNAMIC_PAINT', 'EXPLODE', 'COLLISION'}
HOLD_TYPES = {'MESH', 'CURVE', 'FONT', 'CURVES', 'POINTCLOUD', 'SURFACE'}


def _math(t, op, a=None, b=None, va=None, vb=None):
    m = t.n('ShaderNodeMath', operation=op)
    for k, s, v in ((0, a, va), (1, b, vb)):
        if s is not None:
            t.link(s, m.inputs[k])
        elif v is not None:
            m.inputs[k].default_value = v
    return m.outputs[0]


def boil_group():
    t = N.Tree(BOIL)
    if not t.fresh:
        return t.tree
    t.geo_io()
    t.socket('Amount', 'INPUT', 'NodeSocketFloat', 0.004, 0.0, 1.0)
    t.socket('Every', 'INPUT', 'NodeSocketInt', 2, 1, 24)
    t.socket('Size', 'INPUT', 'NodeSocketFloat', 3.0, 0.01, 100.0)
    st = t.n('GeometryNodeInputSceneTime')
    held = _math(t, 'FLOOR', _math(t, 'DIVIDE', N.O(st, 'Frame'), t.i('Every')))
    w = _math(t, 'MULTIPLY', held, vb=1.37)
    pos = t.n('GeometryNodeInputPosition')
    scaled = t.n('ShaderNodeVectorMath', operation='SCALE')
    t.link(N.O(pos, 'Position'), scaled.inputs[0])
    t.link(t.i('Size'), N.I(scaled, 'Scale'))
    noise = t.n('ShaderNodeTexNoise', noise_dimensions='4D')
    t.link(N.O(scaled, 'Vector'), N.I(noise, 'Vector'))
    t.link(w, N.I(noise, 'W'))
    centred = t.n('ShaderNodeVectorMath', operation='SUBTRACT')
    t.link(N.O(noise, 'Color'), centred.inputs[0])
    centred.inputs[1].default_value = (0.5, 0.5, 0.5)
    amt = _math(t, 'MULTIPLY', t.i('Amount'), vb=2.0)
    off = t.n('ShaderNodeVectorMath', operation='SCALE')
    t.link(N.O(centred, 'Vector'), off.inputs[0])
    t.link(amt, N.I(off, 'Scale'))
    sp = t.n('GeometryNodeSetPosition')
    t.link(t.i('Geometry'), N.I(sp, 'Geometry'))
    t.link(N.O(off, 'Vector'), N.I(sp, 'Offset'))
    t.out(N.O(sp, 'Geometry'))
    return t.tree


def hold_group():
    t = N.Tree(HOLD)
    if not t.fresh:
        return t.tree
    t.geo_io()
    t.socket('Every', 'INPUT', 'NodeSocketInt', 2, 1, 24)
    t.socket('Start', 'INPUT', 'NodeSocketInt', 1)
    sin = t.n('GeometryNodeSimulationInput')
    sout = t.n('GeometryNodeSimulationOutput')
    sin.pair_with_output(sout)
    t.link(t.i('Geometry'), N.I(sin, 'Geometry'))
    st = t.n('GeometryNodeInputSceneTime')
    since = _math(t, 'SUBTRACT', N.O(st, 'Frame'), t.i('Start'))
    mod = _math(t, 'FLOORED_MODULO', since, t.i('Every'))
    is_new = _math(t, 'COMPARE', mod, vb=0.0)  # 1 when this frame starts a new step
    t.tree.nodes[-1].inputs[2].default_value = 0.5
    sw = t.n('GeometryNodeSwitch', input_type='GEOMETRY')
    t.link(is_new, N.I(sw, 'Switch'))
    t.link(N.O(sin, 'Geometry'), N.I(sw, 'False'))
    t.link(t.i('Geometry'), N.I(sw, 'True'))
    t.link(N.O(sw, 'Output'), N.I(sout, 'Geometry'))
    t.out(N.O(sout, 'Geometry'))
    return t.tree


def _to_top(o, m):
    i = list(o.modifiers).index(m)
    if i == 0:
        return
    if hasattr(o.modifiers, 'move'):
        o.modifiers.move(i, 0)
    else:
        with bpy.context.temp_override(object=o, active_object=o):
            bpy.ops.object.modifier_move_to_index(modifier=m.name, index=0)


def add_boil(o, amount=0.006, every=2):
    """Boil one mesh. amount is a share of the model's size."""
    m = o.modifiers.get(BOIL) or o.modifiers.new(BOIL, 'NODES')
    m.node_group = boil_group()
    size = max(o.dimensions) or 1.0
    scale = max(o.scale) or 1.0
    N.set_input(m, 'Amount', amount * size / scale)
    N.set_input(m, 'Every', int(every))
    N.set_input(m, 'Size', 3.0 / (size / scale))
    _to_top(o, m)
    return m


def remove(o, name):
    m = o.modifiers.get(name)
    if m:
        o.modifiers.remove(m)
        return True
    return False


def is_live(o):
    return o.type in HOLD_TYPES and any(m.type in LIVE_MODS and m.name not in (BOIL, HOLD) for m in o.modifiers)


def add_hold(o, every=2, start=1):
    m = o.modifiers.get(HOLD) or o.modifiers.new(HOLD, 'NODES')
    m.node_group = hold_group()
    N.set_input(m, 'Every', int(every))
    N.set_input(m, 'Start', int(start))
    return m


def is_flat(o):
    d = sorted(o.dimensions)
    return d[-1] > 0 and d[0] < d[-1] * 0.01


class CTK_OT_boil3d(bpy.types.Operator):
    """Line boil on the selected 3D models (non-destructive)"""
    bl_idname = 'ctk.boil3d'
    bl_label = 'Boil models'
    bl_options = {'REGISTER', 'UNDO'}
    amount: bpy.props.FloatProperty(name='Amount', default=0.006, min=0.0005, max=0.05, subtype='FACTOR')
    every: bpy.props.IntProperty(name='Every', default=2, min=1, max=12)
    off: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type == 'MESH']
        if not obs:
            self.report({'ERROR'}, 'Select the models to boil')
            return {'CANCELLED'}
        for o in obs:
            remove(o, BOIL) if self.off else add_boil(o, self.amount, self.every)
        return {'FINISHED'}


class CTK_OT_hold3d(bpy.types.Operator):
    """Step procedural animation (text, visualizers, simulations) on the selected objects"""
    bl_idname = 'ctk.hold3d'
    bl_label = 'Hold frames'
    bl_options = {'REGISTER', 'UNDO'}
    every: bpy.props.IntProperty(name='Every', default=2, min=1, max=12)
    off: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type in HOLD_TYPES]
        for o in obs:
            remove(o, HOLD) if self.off else add_hold(o, self.every, context.scene.frame_start)
        self.report({'INFO'}, f'{len(obs)} objects')
        return {'FINISHED'}


CLASSES = (CTK_OT_boil3d, CTK_OT_hold3d)


def draw(layout, context):
    row = layout.row(align=True)
    row.operator('ctk.boil3d', text='Boil selected', icon='MOD_NOISE')
    row.operator('ctk.boil3d', text='', icon='X').off = True
    row = layout.row(align=True)
    row.operator('ctk.hold3d', text='Hold on 2s', icon='RENDER_ANIMATION')
    row.operator('ctk.hold3d', text='', icon='X').off = True
    layout.label(text='Stop-motion mode can do both for the whole scene', icon='INFO')
