"""Video editing helpers for the Video Sequencer.

Captions: brand caption styles for text strips, your own saved styles, and .srt/.vtt import that
lays every line out as a styled text strip inside the Instagram safe zone.

Looks (Blender 5.2): one-click looks for any strip, built as Compositor strip modifiers, so they
stay live and editable: grain, glow, vignette, halftone, colour pop, VHS, brand grade and a
sticker border/glow for cut-outs with alpha. The sticker border can also go on the 3D render."""
import json
import os
import re
import bpy
from . import _util

LABEL, ICON, GROUP = 'Captions + video looks', 'SEQUENCE', 'Output'

INK, MUSTARD, CREAM = '#1F1F1D', '#E0A64B', '#F2E6CF'


def _srgb(h, a=1.0):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


def _lin(h, a=1.0):
    return (*_util.hex_to_linear(h), a)


def strips_of(ed):
    return ed.strips if hasattr(ed, 'strips') else ed.sequences


def all_strips(ed):
    return ed.strips_all if hasattr(ed, 'strips_all') else ed.sequences_all


def new_text_strip(ed, name, channel, start, length):
    st = strips_of(ed)
    try:
        return st.new_effect(name=name, type='TEXT', channel=channel, frame_start=start, length=length)
    except TypeError:
        return st.new_effect(name=name, type='TEXT', channel=channel, frame_start=start, frame_end=start + length)


def looks_available():
    try:
        return 'COMPOSITOR' in [e.identifier for e in
                                bpy.types.StripModifiers.bl_rna.functions['new'].parameters['type'].enum_items]
    except Exception:
        return False


# ------------------------------------------------------------------ caption styles

# sizes are a fraction of the frame height, so styles work at any resolution
STYLES = {
    'Ink on mustard': {'color': _srgb(INK), 'use_box': True, 'box_color': _srgb(MUSTARD), 'box_margin': 0.015,
                       'box_roundness': 0.5, 'use_bold': True, 'use_outline': False, 'use_shadow': False, 'size': 0.042},
    'Mustard outline': {'color': _srgb(MUSTARD), 'use_outline': True, 'outline_color': _srgb(INK), 'outline_width': 0.12,
                        'use_box': False, 'use_bold': True, 'use_shadow': False, 'size': 0.045},
    'Ink clean': {'color': _srgb(INK), 'use_outline': True, 'outline_color': _srgb(CREAM), 'outline_width': 0.08,
                  'use_box': False, 'use_bold': True, 'use_shadow': False, 'size': 0.04},
    'Cream shadow': {'color': _srgb(CREAM), 'use_shadow': True, 'shadow_color': _srgb(INK), 'use_outline': True,
                     'outline_color': _srgb(INK), 'outline_width': 0.05, 'use_box': False, 'use_bold': True, 'size': 0.044},
}
SAVE_KEYS = ['color', 'use_box', 'box_color', 'box_margin', 'box_roundness', 'use_bold', 'use_italic', 'use_outline',
             'outline_color', 'outline_width', 'use_shadow', 'shadow_color', 'shadow_offset', 'shadow_blur',
             'shadow_angle', 'wrap_width', 'alignment_x']


def _styles_dir():
    return os.path.join(_util.vault_dir(), 'Captions')


def styles():
    out = dict(STYLES)
    d = _styles_dir()
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(d, f), encoding='utf-8') as fh:
                        out[f[:-5]] = json.load(fh)
                except Exception:
                    pass
    return out


def apply_style(strip, style, scene):
    h = scene.render.resolution_y * scene.render.resolution_percentage / 100.0
    for k, v in style.items():
        if k == 'size':
            strip.font_size = max(8, round(v * h))
        elif k == 'font':
            if v and os.path.exists(v):
                strip.font = bpy.data.fonts.load(v, check_existing=True)
        elif hasattr(strip, k):
            try:
                setattr(strip, k, tuple(v) if isinstance(v, list) else v)
            except Exception:
                pass
    strip['ctk_style'] = 1


def place_caption(strip, text):
    """Inside the IG safe zone, below the face, never at the very bottom. 1-3 words stay on one
    line; longer captions wrap to two."""
    strip.anchor_x, strip.anchor_y = 'CENTER', 'CENTER'
    strip.alignment_x = 'CENTER'
    strip.location = (0.5, 0.30)
    strip.wrap_width = 1.0 if len(text.split()) <= 3 else 0.78


def save_style(strip, name):
    d = _styles_dir()
    os.makedirs(d, exist_ok=True)
    data = {}
    for k in SAVE_KEYS:
        if hasattr(strip, k):
            v = getattr(strip, k)
            data[k] = list(v) if hasattr(v, '__len__') and not isinstance(v, str) else v
    sc = bpy.context.scene
    h = sc.render.resolution_y * sc.render.resolution_percentage / 100.0
    data['size'] = strip.font_size / max(h, 1)
    if strip.font and strip.font.filepath not in ('', '<builtin>'):
        data['font'] = bpy.path.abspath(strip.font.filepath)
    safe = re.sub(r'[\\/:*?"<>|]+', '_', name).strip() or 'My style'
    path = os.path.join(d, safe + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    return path


# ------------------------------------------------------------------ subtitles

_TIME = re.compile(r'(?:(\d+):)?(\d+):(\d+)[,.](\d+)\s*-->\s*(?:(\d+):)?(\d+):(\d+)[,.](\d+)')


def parse_subs(text):
    """[(start_seconds, end_seconds, text)] from .srt or .vtt text."""
    out = []
    for block in re.split(r'\n\s*\n', text.replace('\r', '').strip()):
        lines = [l for l in block.split('\n') if l.strip()]
        for i, l in enumerate(lines):
            m = _TIME.search(l)
            if m:
                g = [int(x) if x else 0 for x in m.groups()]
                a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / (10 ** len(m.group(4)))
                b = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / (10 ** len(m.group(8)))
                words = ' '.join(re.sub(r'<[^>]+>', '', x).strip() for x in lines[i + 1:])
                if words:
                    out.append((a, b, words))
                break
    return out


def import_subs(scene, path, style_name='Ink on mustard', channel=0):
    with open(path, encoding='utf-8-sig') as f:
        subs = parse_subs(f.read())
    ed = scene.sequence_editor or scene.sequence_editor_create()
    if not channel:
        used = [s.channel for s in all_strips(ed)]
        channel = (max(used) + 1) if used else 2
    fps = scene.render.fps / scene.render.fps_base
    st = styles().get(style_name) or STYLES['Ink on mustard']
    made = []
    for i, (a, b, words) in enumerate(subs):
        f0 = scene.frame_start + round(a * fps)
        ln = max(1, round((b - a) * fps))
        s = new_text_strip(ed, 'Caption %03d' % (i + 1), channel, f0, ln)
        s.text = words
        apply_style(s, st, scene)
        place_caption(s, words)
        made.append(s)
    return made


# ------------------------------------------------------------------ looks (5.2 compositor strip modifiers)

LOOKS = [('GRAIN', 'Grain', 'Fine moving film grain'),
         ('GLOW', 'Glow', 'Soft bloom on the bright parts'),
         ('VIGNETTE', 'Vignette', 'Darker corners'),
         ('HALFTONE', 'Halftone', 'Ink dots on cream, like print'),
         ('POP', 'Colour pop', 'Richer colour and a little contrast'),
         ('VHS', 'VHS', 'Colour fringes, soft smear and scanlines'),
         ('BRAND', 'Brand grade', 'Warm mustard grade with inky shadows'),
         ('STICKER', 'Sticker border', 'Border and glow around a cut-out with alpha')]


class _C:
    def __init__(self, name):
        self.tree = bpy.data.node_groups.new(name, 'CompositorNodeTree')
        self.tree['ctk_built'] = 1
        it = self.tree.interface
        it.new_socket('Image', in_out='INPUT', socket_type='NodeSocketColor')
        it.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        s = it.new_socket('Amount', in_out='INPUT', socket_type='NodeSocketFloat')
        s.default_value, s.min_value, s.max_value = 1.0, 0.0, 2.0
        self.gi = self.n('NodeGroupInput')
        self.go = self.n('NodeGroupOutput')
        self.x = 0

    def n(self, idname, **kw):
        node = self.tree.nodes.new(idname)
        for k, v in kw.items():
            from ._nodes import setting
            setting(node, k, v)
        return node

    def L(self, a, b):
        self.tree.links.new(a, b)

    def m(self, op, a, b=None):
        n = self.n('ShaderNodeMath')
        n.operation = op
        for k, v in ((0, a), (1, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = v
            else:
                self.L(v, n.inputs[k])
        return n.outputs[0]

    def mix(self, blend, fac, a, b):
        n = self.n('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = blend
        n.clamp_result = False
        for sock, v in (('Factor', fac), ('A', a), ('B', b)):
            target = next(s for s in n.inputs if s.name == sock and s.enabled)
            if isinstance(v, (int, float)):
                target.default_value = v
            elif isinstance(v, tuple):
                target.default_value = v
            else:
                self.L(v, target)
        return next(s for s in n.outputs if s.name == 'Result' and s.enabled)

    def img(self):
        return self.gi.outputs['Image']

    def amount(self):
        return self.gi.outputs['Amount']

    def coords(self, kind='Pixel'):
        ic = self.n('CompositorNodeImageCoordinates')
        self.L(self.img(), ic.inputs[0])
        sep = self.n('ShaderNodeSeparateXYZ')
        self.L(ic.outputs[kind], sep.inputs[0])
        return sep

    def finish(self, result, blend=True):
        out = self.mix('MIX', self.amount(), self.img(), result) if blend else result
        self.L(out, self.go.inputs['Image'])
        return self.tree


def build_look(kind):
    name = 'CTK Look ' + dict((k, l) for k, l, _ in LOOKS)[kind]
    old = bpy.data.node_groups.get(name)
    if old and old.get('ctk_built'):
        return old
    c = _C(name)
    img = c.img()
    if kind == 'GRAIN':
        p = c.coords('Pixel')
        st = c.n('CompositorNodeSceneTime')
        v = c.n('ShaderNodeCombineXYZ')
        c.L(p.outputs['X'], v.inputs['X'])
        c.L(p.outputs['Y'], v.inputs['Y'])
        c.L(c.m('MULTIPLY', st.outputs['Frame'], 0.731), v.inputs['Z'])
        wn = c.n('ShaderNodeTexWhiteNoise')
        wn.noise_dimensions = '3D'
        c.L(v.outputs[0], wn.inputs['Vector'])
        return c.finish(c.mix('LINEAR_LIGHT', 0.08, img, c._grey(wn.outputs['Value'])))
    if kind == 'GLOW':
        gl = c.n('CompositorNodeGlare', glare_type='BLOOM')
        c.L(img, gl.inputs['Image'])
        for nm, v in (('Threshold', 0.6), ('Strength', 0.8), ('Size', 0.5)):
            s = next((s for s in gl.inputs if s.name == nm), None)
            if s is not None:
                s.default_value = v
        return c.finish(gl.outputs['Image'])
    if kind == 'VIGNETTE':
        p = c.coords('Normalized')
        dx = c.m('SUBTRACT', p.outputs['X'], 0.5)
        dy = c.m('SUBTRACT', p.outputs['Y'], 0.5)
        d = c.m('SQRT', c.m('ADD', c.m('MULTIPLY', dx, dx), c.m('MULTIPLY', dy, dy)))
        mr = c.n('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        c.L(d, mr.inputs['Value'])
        mr.inputs['From Min'].default_value, mr.inputs['From Max'].default_value = 0.35, 0.75
        mr.inputs['To Min'].default_value, mr.inputs['To Max'].default_value = 1.0, 0.45
        return c.finish(c.mix('MULTIPLY', 1.0, img, c._grey(mr.outputs['Result'])))
    if kind == 'HALFTONE':
        cell = 8.0
        p = c.coords('Pixel')
        lx = c.m('SUBTRACT', c.m('FLOORED_MODULO', p.outputs['X'], cell), cell / 2)
        ly = c.m('SUBTRACT', c.m('FLOORED_MODULO', p.outputs['Y'], cell), cell / 2)
        d = c.m('SQRT', c.m('ADD', c.m('MULTIPLY', lx, lx), c.m('MULTIPLY', ly, ly)))
        px = c.n('CompositorNodePixelate')
        c.L(img, px.inputs[0])
        px.inputs['Size'].default_value = int(cell)
        sep = c.n('CompositorNodeSeparateColor')
        c.L(px.outputs[0], sep.inputs['Image'])
        lum = c.m('ADD', c.m('ADD', c.m('MULTIPLY', sep.outputs['Red'], 0.2126), c.m('MULTIPLY', sep.outputs['Green'], 0.7152)),
                  c.m('MULTIPLY', sep.outputs['Blue'], 0.0722))
        radius = c.m('MULTIPLY', c.m('SUBTRACT', 1.0, c.m('MINIMUM', lum, 1.0)), cell * 0.72)
        dot = c.m('LESS_THAN', d, radius)
        return c.finish(c.mix('MIX', dot, _lin(CREAM), _lin(INK)))
    if kind == 'POP':
        hs = c.n('CompositorNodeHueSat')
        c.L(img, hs.inputs['Image'])
        hs.inputs['Saturation'].default_value = 1.3
        bc = c.n('CompositorNodeBrightContrast')
        c.L(hs.outputs[0], bc.inputs[0])
        s = next((s for s in bc.inputs if s.name == 'Contrast'), None)
        if s is not None:
            s.default_value = 5.0
        return c.finish(bc.outputs[0])
    if kind == 'VHS':
        ld = c.n('CompositorNodeLensdist')
        c.L(img, ld.inputs['Image'])
        ld.inputs['Dispersion'].default_value = 0.06
        bl = c.n('CompositorNodeBlur')
        c.L(ld.outputs[0], bl.inputs['Image'])
        bl.inputs['Size'].default_value = (4.0, 0.0)
        p = c.coords('Pixel')
        scan = c.m('ADD', c.m('MULTIPLY', c.m('SINE', c.m('MULTIPLY', p.outputs['Y'], 1.5708)), 0.08), 0.92)
        hs = c.n('CompositorNodeHueSat')
        c.L(bl.outputs[0], hs.inputs['Image'])
        hs.inputs['Saturation'].default_value = 1.25
        return c.finish(c.mix('MULTIPLY', 1.0, hs.outputs[0], c._grey(scan)))
    if kind == 'BRAND':
        soft = c.mix('SOFT_LIGHT', 0.45, img, _lin(MUSTARD))
        shadows = c.mix('LIGHTEN', 1.0, soft, _lin(INK))  # lift blacks to brand ink
        hs = c.n('CompositorNodeHueSat')
        c.L(shadows, hs.inputs['Image'])
        hs.inputs['Saturation'].default_value = 0.92
        return c.finish(hs.outputs[0])
    if kind == 'STICKER':
        it = c.tree.interface
        w = it.new_socket('Border (px)', in_out='INPUT', socket_type='NodeSocketFloat')
        w.default_value, w.min_value = 12.0, 0.0
        gw = it.new_socket('Glow (px)', in_out='INPUT', socket_type='NodeSocketFloat')
        gw.default_value, gw.min_value = 24.0, 0.0
        bcs = it.new_socket('Border colour', in_out='INPUT', socket_type='NodeSocketColor')
        bcs.default_value = _lin(CREAM)
        gcs = it.new_socket('Glow colour', in_out='INPUT', socket_type='NodeSocketColor')
        gcs.default_value = _lin(MUSTARD)
        sep = c.n('CompositorNodeSeparateColor')
        c.L(img, sep.inputs['Image'])
        inside = c.m('GREATER_THAN', sep.outputs['Alpha'], 0.5)
        sdf = c.n('CompositorNodeMaskToSDF')
        c.L(inside, sdf.inputs['Mask'])
        dist = sdf.outputs['SDF']  # pixels: negative inside, positive outside
        border = c.m('LESS_THAN', dist, c.gi.outputs['Border (px)'])
        outside_border = c.m('SUBTRACT', dist, c.gi.outputs['Border (px)'])
        glow = c.m('MULTIPLY', c.m('SUBTRACT', 1.0, c.m('MINIMUM', c.m('DIVIDE', c.m('MAXIMUM', outside_border, 0.0),
                                                                      c.m('MAXIMUM', c.gi.outputs['Glow (px)'], 0.001)), 1.0)),
                   c.m('GREATER_THAN', c.gi.outputs['Glow (px)'], 0.0))
        glow = c.m('MULTIPLY', glow, glow)
        glow_l = c.n('CompositorNodeSetAlpha')
        c.L(c.gi.outputs['Glow colour'], glow_l.inputs['Image'])
        c.L(c.m('MULTIPLY', glow, 0.8), glow_l.inputs['Alpha'])
        bord_l = c.n('CompositorNodeSetAlpha')
        c.L(c.gi.outputs['Border colour'], bord_l.inputs['Image'])
        c.L(border, bord_l.inputs['Alpha'])
        a1 = c.n('CompositorNodeAlphaOver')
        c.L(glow_l.outputs[0], a1.inputs['Background'])
        c.L(bord_l.outputs[0], a1.inputs['Foreground'])
        a2 = c.n('CompositorNodeAlphaOver')
        c.L(a1.outputs[0], a2.inputs['Background'])
        c.L(img, a2.inputs['Foreground'])
        return c.finish(a2.outputs[0], blend=False)
    raise KeyError(kind)


def _grey(self, value_sock):
    cc = self.n('CompositorNodeCombineColor')
    for i in range(3):
        self.L(value_sock, cc.inputs[i])
    return cc.outputs[0]


_C._grey = _grey


def add_look(strip, kind):
    if not looks_available():
        raise RuntimeError('Needs Blender 5.2 (Compositor strip modifiers)')
    name = 'CTK ' + dict((k, l) for k, l, _ in LOOKS)[kind]
    m = strip.modifiers.get(name) or strip.modifiers.new(name, 'COMPOSITOR')
    m.node_group = build_look(kind)
    return m


def sticker_render(scene):
    """Border + glow around everything in the 3D render (transparent film, scene compositor)."""
    if not looks_available() or not hasattr(scene, 'compositing_node_group'):
        raise RuntimeError('Needs Blender 5.2')
    scene.render.film_transparent = True
    tree = bpy.data.node_groups.new('CTK Sticker render', 'CompositorNodeTree')
    tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = tree.nodes.new('CompositorNodeRLayers')
    rl.scene = scene
    grp = tree.nodes.new('CompositorNodeGroup')
    grp.node_tree = build_look('STICKER')
    go = tree.nodes.new('NodeGroupOutput')
    tree.links.new(rl.outputs['Image'], grp.inputs['Image'])
    tree.links.new(grp.outputs['Image'], go.inputs['Image'])
    scene.compositing_node_group = tree
    scene.render.use_compositing = True
    return tree


# ------------------------------------------------------------------ operators

def _style_items(self, context):
    return [(k, k, '') for k in styles()]


class CTK_OT_caption_style(bpy.types.Operator):
    """Give the selected text strips a caption style"""
    bl_idname = 'ctk.caption_style'
    bl_label = 'Apply caption style'
    bl_options = {'REGISTER', 'UNDO'}
    style: bpy.props.EnumProperty(name='Style', items=_style_items)
    place: bpy.props.BoolProperty(name='Place in the safe zone', default=True)

    def execute(self, context):
        ed = context.scene.sequence_editor
        sel = [s for s in all_strips(ed) if s.select and s.type == 'TEXT'] if ed else []
        if not sel:
            self.report({'WARNING'}, 'Select text strips first')
            return {'CANCELLED'}
        st = styles()[self.style]
        for s in sel:
            apply_style(s, st, context.scene)
            if self.place:
                place_caption(s, s.text)
        return {'FINISHED'}


class CTK_OT_caption_save(bpy.types.Operator):
    """Save the active text strip's look as your own caption style (kept in the Vault)"""
    bl_idname = 'ctk.caption_save'
    bl_label = 'Save as my style'
    name: bpy.props.StringProperty(name='Name', default='My captions')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        ed = context.scene.sequence_editor
        s = ed.active_strip if ed and hasattr(ed, 'active_strip') else None
        if not s or s.type != 'TEXT':
            self.report({'WARNING'}, 'Make a text strip active first')
            return {'CANCELLED'}
        save_style(s, self.name)
        return {'FINISHED'}


class CTK_OT_subs_import(bpy.types.Operator):
    """Import an .srt or .vtt file as styled caption strips"""
    bl_idname = 'ctk.subs_import'
    bl_label = 'Import subtitles'
    bl_options = {'REGISTER', 'UNDO'}
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*.srt;*.vtt', options={'HIDDEN'})
    style: bpy.props.EnumProperty(name='Style', items=_style_items)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            made = import_subs(context.scene, self.filepath, self.style)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{len(made)} captions')
        return {'FINISHED'}


class CTK_OT_strip_look(bpy.types.Operator):
    """Add a one-click look to the selected strips (stays editable as a strip modifier)"""
    bl_idname = 'ctk.strip_look'
    bl_label = 'Add look'
    bl_options = {'REGISTER', 'UNDO'}
    look: bpy.props.EnumProperty(name='Look', items=LOOKS)

    @classmethod
    def poll(cls, context):
        return looks_available()

    def execute(self, context):
        ed = context.scene.sequence_editor
        sel = [s for s in all_strips(ed) if s.select and hasattr(s, 'modifiers')] if ed else []
        if not sel:
            self.report({'WARNING'}, 'Select strips first')
            return {'CANCELLED'}
        for s in sel:
            add_look(s, self.look)
        return {'FINISHED'}


class CTK_OT_sticker_render(bpy.types.Operator):
    """Put a sticker border and glow around everything in the render (turns on transparent film)"""
    bl_idname = 'ctk.sticker_render'
    bl_label = 'Sticker the render'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return looks_available()

    def execute(self, context):
        sticker_render(context.scene)
        return {'FINISHED'}


CLASSES = (CTK_OT_caption_style, CTK_OT_caption_save, CTK_OT_subs_import, CTK_OT_strip_look, CTK_OT_sticker_render)


def draw(layout, context):
    layout.label(text='Captions')
    row = layout.row(align=True)
    row.operator('ctk.subs_import', icon='IMPORT')
    row.operator_menu_enum('ctk.caption_style', 'style', text='Style', icon='FONT_DATA')
    layout.operator('ctk.caption_save', icon='FILE_TICK')
    layout.label(text='Looks')
    if not looks_available():
        layout.label(text='Needs Blender 5.2', icon='INFO')
        return
    grid = layout.grid_flow(columns=4, align=True)
    for k, label, _ in LOOKS:
        grid.operator('ctk.strip_look', text=label).look = k
    layout.operator('ctk.sticker_render', icon='OUTLINER_OB_IMAGE')
