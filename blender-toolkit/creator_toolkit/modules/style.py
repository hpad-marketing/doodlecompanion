"""Style Switcher: flat, cel toon, ink, comic halftone, clay, paper and doodle on any model."""
import bpy
from . import _util
from .. import uxfit

LABEL, ICON, GROUP = 'Style Switcher', 'SHADING_TEXTURE', 'Look'
STYLES = [('FLAT', 'Flat colour', ''), ('CEL', 'Cel toon', ''), ('INK', 'Ink outline only', ''),
          ('COMIC', 'Comic halftone', ''), ('CLAY', 'Clay', ''), ('PAPER', 'Paper', ''),
          ('DOODLE', 'Doodle (flat + ink)', '')]
INK_MOD = 'CTK Ink'


def base_color(m):
    if not m:
        return (0.8, 0.8, 0.8)
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == 'GROUP' and 'Color' in n.inputs:
                return tuple(n.inputs['Color'].default_value[:3])
            if n.type == 'BSDF_PRINCIPLED':
                return tuple(n.inputs['Base Color'].default_value[:3])
            if n.type in ('EMISSION', 'BSDF_DIFFUSE'):
                return tuple(n.inputs['Color'].default_value[:3])
    return tuple(m.diffuse_color[:3])


def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (600, 0)
    return m, nt, out


def ink_material(color=(0.02, 0.02, 0.02)):
    name = 'CTK Ink %02X%02X%02X' % tuple(int(c * 255) for c in color)
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, nt, out = _new(name)
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*color, 1)
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    m.use_backface_culling = True
    m.diffuse_color = (*color, 1)
    return m


def style_material(style, col, shades=3):
    m, nt, out = _new(f'CTK {style.title()}')
    N, L = nt.nodes, nt.links
    m.diffuse_color = (*col, 1)
    if style in ('FLAT', 'DOODLE'):
        em = N.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*col, 1)
        L.new(em.outputs[0], out.inputs['Surface'])
    elif style in ('CEL', 'COMIC'):
        d = N.new('ShaderNodeBsdfDiffuse'); d.location = (-500, 0)
        s = N.new('ShaderNodeShaderToRGB'); s.location = (-300, 0)
        L.new(d.outputs[0], s.inputs[0])
        r = N.new('ShaderNodeValToRGB'); r.location = (-100, 0)
        r.color_ramp.interpolation = 'CONSTANT'
        els = r.color_ramp.elements
        els[0].color = (0.45, 0.45, 0.45, 1); els[1].position = 0.55; els[1].color = (1, 1, 1, 1)
        if shades >= 3:
            e = els.new(0.2); e.color = (0.7, 0.7, 0.7, 1)
        L.new(s.outputs['Color'], r.inputs['Fac'])
        light = r.outputs['Color']
        if style == 'COMIC':
            # screen-space dots that grow in the shadows
            tc = N.new('ShaderNodeTexCoord'); tc.location = (-700, -300)
            mp = N.new('ShaderNodeMapping'); mp.location = (-500, -300)
            mp.inputs['Scale'].default_value = (90, 90, 90)
            L.new(tc.outputs['Window'], mp.inputs['Vector'])
            vor = N.new('ShaderNodeTexVoronoi'); vor.location = (-300, -300)
            vor.inputs['Randomness'].default_value = 0.0
            L.new(mp.outputs['Vector'], vor.inputs['Vector'])
            dist = vor.outputs['Distance']
            inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.location = (-100, -300)
            inv.inputs[0].default_value = 1.15
            L.new(s.outputs['Color'], inv.inputs[1])
            cmp = N.new('ShaderNodeMath'); cmp.operation = 'LESS_THAN'; cmp.location = (100, -300)
            L.new(dist, cmp.inputs[0]); L.new(inv.outputs[0], cmp.inputs[1])
            dots = N.new('ShaderNodeMixRGB'); dots.location = (300, -150)
            L.new(cmp.outputs[0], dots.inputs['Fac'])
            dots.inputs[1].default_value = (1, 1, 1, 1)
            dots.inputs[2].default_value = (0.25, 0.25, 0.25, 1)
            light = dots.outputs['Color']
        mul = N.new('ShaderNodeMixRGB'); mul.blend_type = 'MULTIPLY'; mul.inputs['Fac'].default_value = 1
        mul.location = (300, 50)
        L.new(light, mul.inputs[1]); mul.inputs[2].default_value = (*col, 1)
        em = N.new('ShaderNodeEmission'); em.location = (450, 0)
        L.new(mul.outputs['Color'], em.inputs['Color'])
        L.new(em.outputs[0], out.inputs['Surface'])
    else:  # CLAY / PAPER
        p = N.new('ShaderNodeBsdfPrincipled'); p.location = (0, 0)
        p.inputs['Base Color'].default_value = (*col, 1)
        p.inputs['Roughness'].default_value = 0.85 if style == 'CLAY' else 0.95
        tc = N.new('ShaderNodeTexCoord'); tc.location = (-700, -300)
        nz = N.new('ShaderNodeTexNoise' if style == 'CLAY' else 'ShaderNodeTexVoronoi'); nz.location = (-500, -300)
        nz.inputs['Scale'].default_value = 6 if style == 'CLAY' else 14
        L.new(tc.outputs['Object'], nz.inputs['Vector'])
        b = N.new('ShaderNodeBump'); b.location = (-250, -300)
        b.inputs['Strength'].default_value = 0.25 if style == 'CLAY' else 0.15
        L.new(nz.outputs[0], b.inputs['Height'])
        L.new(b.outputs[0], p.inputs['Normal'])
        L.new(p.outputs[0], out.inputs['Surface'])
    m['ctk_style'] = style
    return m


def apply_style(context, objs, style, line=0.02, ink_color=(0.02, 0.02, 0.02), shades=3):
    done = 0
    for o in objs:
        if o.type not in ('MESH', 'CURVE', 'FONT', 'SURFACE', 'META'):
            continue
        if not o.get('ctk_style_orig'):
            o['ctk_style_orig'] = [s.material.name if s.material else '' for s in o.material_slots] or ['']
        mats = getattr(o.data, 'materials', None)
        if mats is None:
            continue
        if style != 'INK':
            cache = {}
            if not o.material_slots:
                mats.append(None)
            origs = list(o['ctk_style_orig'])
            for i, s in enumerate(o.material_slots):
                nm = origs[i] if i < len(origs) else ''
                orig = bpy.data.materials.get(nm) if nm else None
                if s.material and s.material.name.startswith('CTK Ink'):
                    continue
                src = orig or s.material
                col = base_color(src)
                key = (style, tuple(round(c, 3) for c in col))
                if key not in cache:
                    cache[key] = style_material(style, col, shades)
                s.material = cache[key]
        ink = style in ('INK', 'DOODLE', 'CEL', 'COMIC')
        mod = o.modifiers.get(INK_MOD)
        if ink:
            im = ink_material(ink_color)
            if im.name not in [m.name for m in mats if m]:
                mats.append(im)
            if not mod and o.type == 'MESH':
                mod = o.modifiers.new(INK_MOD, 'SOLIDIFY')
            if mod:
                mod.thickness = line
                mod.offset = 1.0
                mod.use_flip_normals = True
                mod.use_rim = False
                mod.material_offset = [m.name if m else '' for m in mats].index(im.name)
        elif mod:
            o.modifiers.remove(mod)
        done += 1
    return done


def revert(objs):
    for o in objs:
        orig = o.get('ctk_style_orig')
        mod = o.modifiers.get(INK_MOD) if hasattr(o, 'modifiers') else None
        if mod:
            o.modifiers.remove(mod)
        if orig is None:
            continue
        mats = o.data.materials
        mats.clear()
        for n in orig:
            mats.append(bpy.data.materials.get(n) if n else None)
        del o['ctk_style_orig']


class CTK_OT_style_apply(bpy.types.Operator):
    """Switch the selected objects (or the whole scene) to an art style. Revert brings the originals back"""
    bl_idname = 'ctk.style_apply'
    bl_label = 'Apply style'
    bl_options = {'REGISTER', 'UNDO'}
    style: bpy.props.EnumProperty(items=STYLES)
    whole_scene: bpy.props.BoolProperty(name='Whole scene', default=False)
    line: bpy.props.FloatProperty(name='Line weight', default=0.015, min=0.001, max=0.2, unit='LENGTH')
    ink_color: bpy.props.FloatVectorProperty(name='Ink colour', subtype='COLOR', size=3, default=(0.12, 0.12, 0.11), min=0, max=1)
    shades: bpy.props.IntProperty(name='Toon steps', default=3, min=2, max=3)

    def execute(self, context):
        objs = list(context.scene.objects) if self.whole_scene else list(context.selected_objects)
        n = apply_style(context, objs, self.style, self.line, tuple(self.ink_color), self.shades)
        if self.style in ('FLAT', 'DOODLE', 'CEL', 'COMIC'):
            context.scene.view_settings.view_transform = 'Standard'
        self.report({'INFO'}, f'{n} objects styled')
        return {'FINISHED'}


class CTK_OT_style_revert(bpy.types.Operator):
    """Put the original materials back"""
    bl_idname = 'ctk.style_revert'
    bl_label = 'Revert style'
    bl_options = {'REGISTER', 'UNDO'}
    whole_scene: bpy.props.BoolProperty(name='Whole scene', default=False)

    def execute(self, context):
        revert(list(context.scene.objects) if self.whole_scene else list(context.selected_objects))
        return {'FINISHED'}


CLASSES = (CTK_OT_style_apply, CTK_OT_style_revert)


def draw(layout, context):
    grid = uxfit.flow(layout, context, [str(_t[1]) for _t in STYLES], most=2)
    for k, label, _ in STYLES:
        grid.operator('ctk.style_apply', text=label).style = k
    row = layout.row(align=True)
    row.operator('ctk.style_revert', icon='LOOP_BACK')
    op = row.operator('ctk.style_revert', text='Revert scene')
    op.whole_scene = True
    uxfit.wrap(layout, context, 'Line weight and colour: see the Adjust panel after applying', icon='INFO')
