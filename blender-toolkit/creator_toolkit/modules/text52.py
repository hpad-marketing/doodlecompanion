"""Procedural text: text that types itself, counts up, rides along a curve, waves, or pops in
word by word. All live Geometry Nodes, so the words stay editable and timing is in frames.

Counters can write thousands with commas ("10,000 followers") on Blender 5.2. Word pop needs
5.2 too (String to Curves gives each word a number there)."""
import bpy
from . import _util
from ._nodes import Tree, O, I, set_input, setting, draw_modifier_inputs

LABEL, ICON, GROUP = 'Procedural text', 'FONT_DATA', 'Motion design'

KINDS = [('TYPEWRITER', 'Types itself', 'Letters appear one by one', 'FONT_DATA'),
         ('COUNTER', 'Counter', 'A number that counts up, like 0 to 10,000 followers', 'LINENUMBERS_ON'),
         ('ALONG_CURVE', 'Along a curve', 'Letters ride along a curve, optionally sliding', 'CURVE_BEZCURVE'),
         ('WAVE', 'Wave', 'Letters bob up and down in a wave', 'MOD_WAVE'),
         ('WORDS', 'Word pop', 'Words pop in one after another', 'OUTLINER_OB_FONT')]
MOD = 'CTK Text'


def new_52():
    return hasattr(bpy.types, 'GeometryNodeInputFont')


def available(kind):
    return kind != 'WORDS' or new_52()


class _B:
    """Small helpers over a Tree for maths and links."""
    def __init__(self, t):
        self.t = t

    def m(self, op, a, b=None):
        n = self.t.n('ShaderNodeMath', operation=op)
        for k, v in ((0, a), (1, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = v
            else:
                self.t.link(v, n.inputs[k])
        return n.outputs[0]

    def progress(self):
        """0 -> 1 between Start frame and Start + Duration, eased."""
        t = self.t
        st = t.n('GeometryNodeInputSceneTime')
        mr = t.n('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        mr.clamp = True
        t.link(O(st, 'Frame'), I(mr, 'Value'))
        t.link(t.i('Start frame'), I(mr, 'From Min'))
        t.link(self.m('ADD', t.i('Start frame'), t.i('Duration (frames)')), I(mr, 'From Max'))
        return O(mr, 'Result')

    def join(self, *parts, delim=''):
        """Join strings left to right (two at a time, so the order is certain)."""
        out = parts[0]
        for p in parts[1:]:
            j = self.t.n('GeometryNodeStringJoin')
            I(j, 'Delimiter').default_value = delim
            # a multi-input socket lists its newest link first, so link right-hand side first
            for v in (p, out):
                if isinstance(v, str):
                    s = self.t.n('FunctionNodeInputString')
                    s.string = v
                    v = s.outputs[0]
                self.t.link(v, I(j, 'Strings'))
            out = O(j, 'String')
        return out

    def num(self, v, decimals=0, pad=0):
        n = self.t.n('FunctionNodeValueToString')
        if pad and hasattr(n, 'data_type'):
            n.data_type = 'INT'  # padding only exists for whole numbers
        self.t.link(v, I(n, 'Value'))
        dec = [x for x in n.inputs if x.name == 'Decimals' and x.enabled]
        if dec and isinstance(decimals, int):
            dec[0].default_value = decimals
        elif dec:
            self.t.link(decimals, dec[0])
        if pad and any(s.name == 'Padding' for s in n.inputs):
            I(n, 'Padding').default_value = pad
        return O(n, 'String')

    def switch(self, kind, cond, false, true):
        n = self.t.n('GeometryNodeSwitch', input_type=kind)
        self.t.link(cond, I(n, 'Switch'))
        self.t.link(false, I(n, 'False'))
        self.t.link(true, I(n, 'True'))
        return O(n, 'Output')


def _counter_string(t, b):
    p = b.progress()
    val = b.m('ADD', t.i('From'), b.m('MULTIPLY', p, b.m('SUBTRACT', t.i('To'), t.i('From'))))
    plain = b.num(val, t.i('Decimals'))
    if new_52():
        r = b.m('ROUND', val)
        big = b.m('FLOOR', b.m('DIVIDE', r, 1e6))
        mid = b.m('FLOORED_MODULO', b.m('FLOOR', b.m('DIVIDE', r, 1000.0)), 1000.0)
        low = b.m('FLOORED_MODULO', r, 1000.0)
        thousands = b.join(b.num(b.m('FLOOR', b.m('DIVIDE', r, 1000.0))), b.num(low, 0, 3), delim=',')
        millions = b.join(b.num(big), b.num(mid, 0, 3), b.num(low, 0, 3), delim=',')
        ge3 = b.m('GREATER_THAN', r, 999.5)
        ge6 = b.m('GREATER_THAN', r, 999999.5)
        cm = b.switch('STRING', _bool(t, ge3), b.num(r), thousands)
        cm = b.switch('STRING', _bool(t, ge6), cm, millions)
        use = t.n('FunctionNodeBooleanMath', operation='AND')
        t.link(t.i('Commas'), use.inputs[0])
        nd = b.m('LESS_THAN', t.i('Decimals'), 0.5)
        t.link(_bool(t, nd), use.inputs[1])
        plain = b.switch('STRING', use.outputs[0], plain, cm)
    return b.join(t.i('Before'), plain, t.i('After'))


def _bool(t, value_sock):
    c = t.n('FunctionNodeCompare', data_type='FLOAT', operation='GREATER_THAN')
    t.link(value_sock, I(c, 'A'))
    I(c, 'B').default_value = 0.5
    return O(c, 'Result')


def build(kind):
    t = Tree('CTK Text ' + kind.title().replace('_', ' '))
    if not t.fresh:
        return t.tree
    b = _B(t)
    t.geo_io()
    t.socket('Text', 'INPUT', 'NodeSocketString', 'Doodle time' if kind != 'COUNTER' else '')
    if kind == 'COUNTER':
        t.socket('From', 'INPUT', 'NodeSocketFloat', 0.0)
        t.socket('To', 'INPUT', 'NodeSocketFloat', 10000.0)
        t.socket('Decimals', 'INPUT', 'NodeSocketInt', 0, 0, 6)
        if new_52():
            t.socket('Commas', 'INPUT', 'NodeSocketBool', True)
        t.socket('Before', 'INPUT', 'NodeSocketString', '')
        t.socket('After', 'INPUT', 'NodeSocketString', ' followers')
    if kind in ('TYPEWRITER', 'COUNTER', 'WORDS'):
        t.socket('Start frame', 'INPUT', 'NodeSocketInt', 1)
        t.socket('Duration (frames)', 'INPUT', 'NodeSocketInt', 48, 1, 100000)
    if kind == 'ALONG_CURVE':
        t.socket('Curve', 'INPUT', 'NodeSocketObject')
        t.socket('Offset', 'INPUT', 'NodeSocketFloat', 0.0)
        t.socket('Slide speed', 'INPUT', 'NodeSocketFloat', 0.0)
    if kind == 'WAVE':
        t.socket('Height', 'INPUT', 'NodeSocketFloat', 0.15, 0.0, 100.0)
        t.socket('Speed', 'INPUT', 'NodeSocketFloat', 4.0)
        t.socket('Spread', 'INPUT', 'NodeSocketFloat', 0.8)
    if kind == 'WORDS':
        t.socket('Pop frames', 'INPUT', 'NodeSocketInt', 6, 1, 1000)
    t.socket('Size', 'INPUT', 'NodeSocketFloat', 1.0, 0.0, 1000.0)
    if new_52():
        fs = t.socket('Font', 'INPUT', 'NodeSocketFont')
        try:
            fs.default_value = builtin_font()
        except Exception:
            pass
    t.socket('Depth', 'INPUT', 'NodeSocketFloat', 0.0, 0.0, 100.0)
    t.socket('Material', 'INPUT', 'NodeSocketMaterial')

    # the string
    text = t.i('Text')
    if kind == 'COUNTER':
        text = _counter_string(t, b)
    elif kind == 'TYPEWRITER':
        ln = t.n('FunctionNodeStringLength')
        t.link(text, I(ln, 'String'))
        cnt = b.m('FLOOR', b.m('MULTIPLY', b.progress(), O(ln, 'Length')))
        sl = t.n('FunctionNodeSliceString')
        I(sl, 'Position').default_value = 0
        t.link(text, I(sl, 'String'))
        t.link(cnt, I(sl, 'Length'))
        text = O(sl, 'String')

    s2c = t.n('GeometryNodeStringToCurves')
    setting(s2c, 'align_x', 'LEFT' if kind == 'ALONG_CURVE' else 'CENTER', menu='Align X')
    t.link(text, I(s2c, 'String'))
    t.link(t.i('Size'), I(s2c, 'Size'))
    if new_52():
        t.link(t.i('Font'), I(s2c, 'Font'))
    inst = O(s2c, 'Curve Instances')

    if kind == 'WAVE':
        pos = t.n('GeometryNodeInputPosition')
        sep = t.n('ShaderNodeSeparateXYZ')
        t.link(O(pos, 'Position'), I(sep, 'Vector'))
        st = t.n('GeometryNodeInputSceneTime')
        ph = b.m('ADD', b.m('MULTIPLY', O(st, 'Seconds'), t.i('Speed')),
                 b.m('MULTIPLY', O(sep, 'X'), b.m('DIVIDE', t.i('Spread'), b.m('MAXIMUM', t.i('Size'), 0.001))))
        dy = b.m('MULTIPLY', b.m('SINE', ph), t.i('Height'))
        cx = t.n('ShaderNodeCombineXYZ')
        t.link(dy, I(cx, 'Y'))
        tr = t.n('GeometryNodeTranslateInstances')
        t.link(inst, I(tr, 'Instances'))
        t.link(O(cx, 'Vector'), I(tr, 'Translation'))
        I(tr, 'Local Space').default_value = False
        inst = O(tr, 'Instances')
    elif kind == 'WORDS':
        st = t.n('GeometryNodeInputSceneTime')
        word = O(s2c, 'Word')
        # each word starts Duration/words apart; scale goes 0 -> 1 over Pop frames with overshoot
        local = b.m('SUBTRACT', b.m('SUBTRACT', O(st, 'Frame'), t.i('Start frame')),
                    b.m('MULTIPLY', word, b.m('DIVIDE', t.i('Duration (frames)'), 6.0)))
        k = b.m('MINIMUM', b.m('MAXIMUM', b.m('DIVIDE', local, t.i('Pop frames')), 0.0), 1.0)
        over = b.m('ADD', k, b.m('MULTIPLY', b.m('SINE', b.m('MULTIPLY', k, 3.14159)), 0.25))
        sc = t.n('GeometryNodeScaleInstances')
        t.link(inst, I(sc, 'Instances'))
        t.link(over, I(sc, 'Scale'))
        inst = O(sc, 'Instances')
    elif kind == 'ALONG_CURVE':
        oi = t.n('GeometryNodeObjectInfo', transform_space='RELATIVE')
        t.link(t.i('Curve'), I(oi, 'Object'))
        pos = t.n('GeometryNodeInputPosition')
        sep = t.n('ShaderNodeSeparateXYZ')
        t.link(O(pos, 'Position'), I(sep, 'Vector'))
        st = t.n('GeometryNodeInputSceneTime')
        cl = t.n('GeometryNodeCurveLength')
        t.link(O(oi, 'Geometry'), I(cl, 'Curve'))
        length = b.m('MAXIMUM', O(cl, 'Length'), 0.001)
        # sliding loops around the curve; text longer than the curve is cut at its end
        slide = b.m('FLOORED_MODULO', b.m('ADD', t.i('Offset'), b.m('MULTIPLY', O(st, 'Seconds'), t.i('Slide speed'))), length)
        along = b.m('ADD', O(sep, 'X'), slide)
        along = b.m('FLOORED_MODULO', along, length)
        off = b.m('GREATER_THAN', O(sep, 'X'), length)
        dl = t.n('GeometryNodeDeleteGeometry', domain='INSTANCE')
        t.link(inst, I(dl, 'Geometry'))
        t.link(_bool(t, off), I(dl, 'Selection'))
        inst = O(dl, 'Geometry')
        sc_ = t.n('GeometryNodeSampleCurve', mode='LENGTH')
        t.link(O(oi, 'Geometry'), I(sc_, 'Curves'))
        t.link(along, I(sc_, 'Length'))
        # turn each letter to the curve first (about its own spot), then move it onto the curve
        al = t.n('FunctionNodeAlignRotationToVector', axis='X')
        t.link(O(sc_, 'Tangent'), I(al, 'Vector'))
        ri = t.n('GeometryNodeRotateInstances')
        t.link(inst, I(ri, 'Instances'))
        t.link(O(al, 'Rotation'), I(ri, 'Rotation'))
        t.link(O(pos, 'Position'), I(ri, 'Pivot Point'))
        I(ri, 'Local Space').default_value = False
        sp = t.n('GeometryNodeSetPosition')
        t.link(O(ri, 'Instances'), I(sp, 'Geometry'))
        t.link(O(sc_, 'Position'), I(sp, 'Position'))
        inst = O(sp, 'Geometry')

    real = t.n('GeometryNodeRealizeInstances')
    t.link(inst, I(real, 'Geometry'))
    fill = t.n('GeometryNodeFillCurve', mode='NGONS')
    t.link(O(real, 'Geometry'), I(fill, 'Curve'))
    flat = O(fill, 'Mesh')
    # optional depth: extrude, keep a flipped cap underneath
    ex = t.n('GeometryNodeExtrudeMesh', mode='FACES')
    t.link(flat, I(ex, 'Mesh'))
    t.link(t.i('Depth'), I(ex, 'Offset Scale'))
    ff = t.n('GeometryNodeFlipFaces')
    t.link(flat, I(ff, 'Mesh'))
    jn = t.n('GeometryNodeJoinGeometry')
    t.link(O(ex, 'Mesh'), I(jn, 'Geometry'))
    t.link(O(ff, 'Mesh'), I(jn, 'Geometry'))
    mg = t.n('GeometryNodeMergeByDistance')
    t.link(O(jn, 'Geometry'), I(mg, 'Geometry'))
    solid = O(mg, 'Geometry')
    deep = b.m('GREATER_THAN', t.i('Depth'), 0.0)
    geo = b.switch('GEOMETRY', _bool(t, deep), flat, solid)
    sm = t.n('GeometryNodeSetMaterial')
    t.link(geo, I(sm, 'Geometry'))
    t.link(t.i('Material'), I(sm, 'Material'))
    t.out(O(sm, 'Geometry'))
    return t.tree


def builtin_font():
    f = next((f for f in bpy.data.fonts if f.filepath == '<builtin>'), None)
    return f or bpy.data.fonts.load('<builtin>')


def ink_material(colour='#1F1F1D'):
    name = 'CTK Text ' + colour
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*_util.hex_to_linear(colour), 1)
    b.inputs['Roughness'].default_value = 0.8
    m.diffuse_color = (*_util.hex_to_linear(colour), 1)
    return m


def add_text(context, kind='TYPEWRITER', text='Doodle time', curve=None, colour='#1F1F1D'):
    if not available(kind):
        raise RuntimeError('Word pop needs Blender 5.2')
    me = bpy.data.meshes.new('Text')
    o = bpy.data.objects.new(KINDS[[k[0] for k in KINDS].index(kind)][1], me)
    context.scene.collection.objects.link(o)
    o.location = context.scene.cursor.location
    o.rotation_euler = (1.5708, 0, 0)
    m = o.modifiers.new(MOD, 'NODES')
    m.node_group = build(kind)
    if kind != 'COUNTER':
        set_input(m, 'Text', text)
    if kind == 'ALONG_CURVE':
        if curve is None:
            cd = bpy.data.curves.new('Text path', 'CURVE')
            cd.dimensions = '3D'
            sp = cd.splines.new('BEZIER')
            sp.bezier_points.add(2)
            for p, co in zip(sp.bezier_points, ((-4, 0, 0), (0, 2.5, 0), (4, 0, 0))):
                p.co = co
                p.handle_left_type = p.handle_right_type = 'AUTO'
            curve = bpy.data.objects.new('Text path', cd)
            context.scene.collection.objects.link(curve)
            curve.location = o.location
            curve.rotation_euler = o.rotation_euler
        set_input(m, 'Curve', curve)
        o.location, o.rotation_euler = curve.location.copy(), curve.rotation_euler.copy()
    set_input(m, 'Material', ink_material(colour))
    if new_52():
        set_input(m, 'Font', builtin_font())
    o.data.materials.append(ink_material(colour))
    return o


class CTK_OT_text_add(bpy.types.Operator):
    """Add live procedural text"""
    bl_idname = 'ctk.text_add'
    bl_label = 'Add procedural text'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(name='Kind', items=[k[:3] for k in KINDS])
    text: bpy.props.StringProperty(name='Text', default='Doodle time')

    def execute(self, context):
        if not available(self.kind):
            self.report({'ERROR'}, 'Word pop needs Blender 5.2')
            return {'CANCELLED'}
        curve = None
        if self.kind == 'ALONG_CURVE':
            curve = next((o for o in context.selected_objects if o.type == 'CURVE'), None)
        o = add_text(context, self.kind, self.text, curve)
        for s in context.selected_objects:
            s.select_set(False)
        o.select_set(True)
        context.view_layer.objects.active = o
        return {'FINISHED'}


CLASSES = (CTK_OT_text_add,)


def draw(layout, context):
    grid = layout.grid_flow(columns=2, align=True)
    for k, label, _d, icon in KINDS:
        r = grid.row(align=True)
        r.enabled = available(k)
        r.operator('ctk.text_add', text=label, icon=icon).kind = k
    o = context.active_object
    if o and MOD in o.modifiers:
        draw_modifier_inputs(layout.box(), o.modifiers[MOD])
    if not new_52():
        layout.label(text='Commas, fonts and word pop need Blender 5.2', icon='INFO')
