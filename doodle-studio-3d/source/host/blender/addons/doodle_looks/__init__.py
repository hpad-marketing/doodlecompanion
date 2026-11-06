"""Doodle Looks: the built-in materials of Doodle Studio 3D's Materials tab.

This package is also the reference for the look add-on contract (CONTRACT.md next to
this file). Doodle Studio 3D reads doodle_look.json to fill the Materials tab, then, in
Blender, calls

    material(look_id, rgb, params) -> bpy.types.Material

once per colour the palette needs. rgb is linear 0..1 (r, g, b); params holds the values
from the tab's sliders, keyed by the ids in doodle_look.json (missing ones take their
defaults). The returned material is put on the object's fill slots; the ink outline stays
the studio's own.
"""
import colorsys
import hashlib
import json
import os

bl_info = {
    'name': 'Doodle Looks',
    'author': 'Doodle Studio',
    'version': (1, 0, 0),
    'blender': (4, 5, 0),
    'location': 'Doodle Studio 3D › Materials',
    'description': 'Built-in materials for Doodle Studio 3D (clay, cel toon, soft vinyl, felt, paper, ceramic)',
    'category': 'Material',
}

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = json.load(open(os.path.join(HERE, 'doodle_look.json'), encoding='utf-8'))
LOOKS = {lk['id']: lk for lk in MANIFEST['looks']}


def defaults(look):
    return {p['id']: p['default'] for p in LOOKS[look]['params']}


def register():   # nothing to register: Doodle Studio 3D calls material() directly
    pass


def unregister():
    pass


# ---------------------------------------------------------------- node helpers
class _T:
    def __init__(self, mat):
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.x = 0

    def n(self, kind, **inputs):
        node = self.nt.nodes.new(kind)
        node.location = (self.x, 0)
        self.x += 180
        for k, v in inputs.items():
            if k.startswith('_'):
                setattr(node, k[1:], v)
            else:
                node.inputs[k].default_value = v
        return node

    def link(self, a, b):
        self.nt.links.new(a, b)


def _mix(t, fac, a, b):
    """colour mix: fac, a and b are each a value or a socket; returns the colour socket"""
    m = t.n('ShaderNodeMix', _data_type='RGBA')
    sock = lambda nm, ty: next(x for x in m.inputs if x.name == nm and x.type == ty)
    for nm, ty, v in (('Factor', 'VALUE', fac), ('A', 'RGBA', a), ('B', 'RGBA', b)):
        if isinstance(v, (int, float, tuple)):
            sock(nm, ty).default_value = v
        else:
            t.link(v, sock(nm, ty))
    return next(x for x in m.outputs if x.type == 'RGBA')


def _lin(c):
    return tuple(max(0.0, min(1.0, x)) for x in c[:3]) + (1.0,)


def _shift(rgb, dv=1.0, dh=0.0, ds=1.0):
    h, s, v = colorsys.rgb_to_hsv(*rgb[:3])
    return colorsys.hsv_to_rgb((h + dh) % 1.0, max(0.0, min(1.0, s * ds)), max(0.0, min(1.0, v * dv)))


def _coords(t):
    return t.n('ShaderNodeTexCoord').outputs['Object']


def _bump(t, height, strength, distance=0.02):
    b = t.n('ShaderNodeBump', Strength=strength, Distance=distance)
    t.link(height, b.inputs['Height'])
    return b.outputs['Normal']


def _wobble(t, base, amount, scale=3.0):
    """base colour with a slow light/dark wobble, as hand-mixed material has"""
    if amount <= 0:
        return None
    nz = t.n('ShaderNodeTexNoise', Scale=scale, Detail=2.0)
    t.link(_coords(t), nz.inputs['Vector'])
    return _mix(t, nz.outputs['Fac'], _lin(_shift(base, 1 - amount * 1.6)), _lin(_shift(base, 1 + amount, ds=1 - amount)))


def _principled(t, base, **kw):
    p = t.n('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = _lin(base)
    for k, v in kw.items():
        p.inputs[k].default_value = v
    return p


# ---------------------------------------------------------------- the looks
def _speckle(t, base, amount, scale, lo=0.8, hi=1.15):
    """colour that varies in tiny flecks (felt fibres, glaze specks)"""
    nz = t.n('ShaderNodeTexNoise', Scale=scale, Detail=3.0, Roughness=0.8)
    t.link(_coords(t), nz.inputs['Vector'])
    k = t.n('ShaderNodeMapRange', **{'From Min': 0.35, 'From Max': 0.65})
    t.link(nz.outputs['Fac'], k.inputs['Value'])
    return _mix(t, k.outputs['Result'], _lin(_shift(base, 1 - (1 - lo) * amount)), _lin(_shift(base, 1 + (hi - 1) * amount, ds=1 - 0.2 * amount)))


def _clay(t, base, P):
    # matte modelling clay: soft lumps, big thumb dents, fine tool scratches, colour blotches
    p = _principled(t, base, Roughness=P['roughness'], **{'Specular IOR Level': 0.18})
    if P['glow'] > 0:
        p.inputs['Subsurface Weight'].default_value = P['glow']
        p.inputs['Subsurface Radius'].default_value = (1.0, 0.45, 0.25)
        p.inputs['Subsurface Scale'].default_value = 0.02
    col = _wobble(t, base, P['wobble'], scale=4.0)
    if col:
        t.link(col, p.inputs['Base Color'])
    co = _coords(t)
    dent = t.n('ShaderNodeTexVoronoi', Scale=5.0 / max(0.05, P['dentSize']), Randomness=1.0, _feature='SMOOTH_F1')
    t.link(co, dent.inputs['Vector'])
    dent.inputs['Smoothness'].default_value = 0.6
    lump = t.n('ShaderNodeTexNoise', Scale=2.5, Detail=2.0)
    t.link(co, lump.inputs['Vector'])
    scratch = t.n('ShaderNodeTexNoise', Scale=70.0, Detail=8.0, Roughness=0.65)
    t.link(co, scratch.inputs['Vector'])
    h1 = t.n('ShaderNodeMath', _operation='MULTIPLY_ADD')
    h1.inputs[1].default_value = 0.6
    t.link(lump.outputs['Fac'], h1.inputs[0])
    t.link(dent.outputs['Distance'], h1.inputs[2])
    h = t.n('ShaderNodeMath', _operation='MULTIPLY_ADD')
    h.inputs[1].default_value = 0.025
    t.link(scratch.outputs['Fac'], h.inputs[0])
    t.link(h1.outputs['Value'], h.inputs[2])
    t.link(_bump(t, h.outputs['Value'], 0.2 + 0.8 * P['dents'], 0.12), p.inputs['Normal'])
    return p.outputs['BSDF']


def _cel(t, base, P):
    n = max(2, min(4, int(round(P['bands']))))
    dif = t.n('ShaderNodeBsdfDiffuse', Color=(1, 1, 1, 1))
    s2r = t.n('ShaderNodeShaderToRGB')
    t.link(dif.outputs['BSDF'], s2r.inputs['Shader'])
    bw = t.n('ShaderNodeRGBToBW')
    t.link(s2r.outputs['Color'], bw.inputs['Color'])
    # light on a surface runs from the ambient (about 0.5) to key + fill + ambient (about 1.8)
    span = t.n('ShaderNodeMapRange', **{'From Min': 0.5, 'From Max': 1.8, 'To Min': 0.0, 'To Max': 1.0})
    t.link(bw.outputs['Val'], span.inputs['Value'])
    ramp = t.n('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.interpolation = 'LINEAR' if P['edge'] > 0.001 else 'CONSTANT'
    cols = [_lin(_shift(base, 1 - P['shadow'] * (1 - k / (n - 1)), dh=P['shadowHue'] * (1 - k / (n - 1)), ds=1 + 0.25 * P['shadow'] * (1 - k / (n - 1)))) for k in range(n)]
    stops = []
    for k in range(n):
        lo = 0.0 if k == 0 else 0.15 + 0.6 * k / n
        if cr.interpolation == 'LINEAR' and k > 0:
            stops.append((max(0.0, lo - P['edge']), cols[k - 1]))
            stops.append((min(1.0, lo + P['edge']), cols[k]))
        else:
            stops.append((lo, cols[k]))
    # the two default stops become the first and last; the rest are added at their place
    # (Blender re-sorts stops as positions change, so never move one past another)
    first, last = cr.elements[0], cr.elements[1]
    first.position, first.color = stops[0]
    last.position, last.color = stops[-1]
    for pos, c in stops[1:-1]:
        cr.elements.new(pos).color = c
    t.link(span.outputs['Result'], ramp.inputs['Fac'])
    em = t.n('ShaderNodeEmission', Strength=1.0)
    t.link(ramp.outputs['Color'], em.inputs['Color'])
    return em.outputs['Emission']


def _vinyl(t, base, P):
    # soft vinyl toy: satin body, one broad soft highlight, slightly richer colour, no texture
    rich = _shift(base, 1.0, ds=1.12)
    p = _principled(t, rich, Roughness=P['roughness'], **{'Coat Weight': P['coat'], 'Coat Roughness': 0.12 + 0.3 * (1 - P['coatGloss']), 'Specular IOR Level': 0.35,
                                                           'Subsurface Weight': 0.12, 'Subsurface Scale': 0.01})
    p.inputs['Subsurface Radius'].default_value = (1.0, 0.5, 0.3)
    return p.outputs['BSDF']


def _felt(t, base, P):
    # wool felt: no shine, dense fibre flecks, fuzzy surface, light halo at the edges
    p = _principled(t, base, Roughness=1.0, **{'Sheen Weight': P['sheen'], 'Sheen Roughness': 0.5, 'Specular IOR Level': 0.0})
    p.inputs['Sheen Tint'].default_value = _lin(_shift(base, 1.25, ds=0.75))
    sc = 320.0 / max(0.1, P['fibres'])
    t.link(_speckle(t, base, 0.5 + 0.5 * P['fuzz'], sc, 0.72, 1.2), p.inputs['Base Color'])
    co = _coords(t)
    fz = t.n('ShaderNodeTexNoise', Scale=sc * 1.6, Detail=10.0, Roughness=0.85)
    t.link(co, fz.inputs['Vector'])
    pill = t.n('ShaderNodeTexNoise', Scale=18.0, Detail=3.0)
    t.link(co, pill.inputs['Vector'])
    h = t.n('ShaderNodeMath', _operation='MULTIPLY_ADD')
    h.inputs[1].default_value = 0.25
    t.link(pill.outputs['Fac'], h.inputs[0])
    t.link(fz.outputs['Fac'], h.inputs[2])
    t.link(_bump(t, h.outputs['Value'], 0.3 + 0.7 * P['fuzz'], 0.012), p.inputs['Normal'])
    return p.outputs['BSDF']


def _paper(t, base, P):
    # crumpled card: each facet catches the light a little differently, with a fine grain
    co = _coords(t)
    fac = t.n('ShaderNodeTexVoronoi', Scale=3.0 + 4.0 * P['fibres'], Randomness=1.0)
    t.link(co, fac.inputs['Vector'])
    grain = t.n('ShaderNodeTexNoise', Scale=420.0, Detail=4.0, Roughness=0.7)
    t.link(co, grain.inputs['Vector'])
    # facet tone: a random light level per facet
    bw0 = t.n('ShaderNodeRGBToBW')
    t.link(fac.outputs['Color'], bw0.inputs['Color'])
    tone = t.n('ShaderNodeMapRange', **{'From Min': 0.25, 'From Max': 0.75, 'To Min': 0.0, 'To Max': 1.0})
    t.link(bw0.outputs['Val'], tone.inputs['Value'])
    # overall light from the key, softened: card never goes dark
    dif = t.n('ShaderNodeBsdfDiffuse', Color=(1, 1, 1, 1))
    t.link(_bump(t, grain.outputs['Fac'], 0.1 + 0.4 * P['grain'], 0.004), dif.inputs['Normal'])
    s2r = t.n('ShaderNodeShaderToRGB')
    t.link(dif.outputs['BSDF'], s2r.inputs['Shader'])
    bw = t.n('ShaderNodeRGBToBW')
    t.link(s2r.outputs['Color'], bw.inputs['Color'])
    lit = t.n('ShaderNodeMapRange', **{'From Min': 0.3, 'From Max': 1.6, 'To Min': 0.0, 'To Max': 1.0})
    t.link(bw.outputs['Val'], lit.inputs['Value'])
    f = t.n('ShaderNodeMath', _operation='MULTIPLY_ADD')
    f.inputs[1].default_value = 0.75 * P['shade']
    t.link(tone.outputs['Result'], f.inputs[0])
    lw = t.n('ShaderNodeMath', _operation='MULTIPLY')
    lw.inputs[1].default_value = 0.3
    t.link(lit.outputs['Result'], lw.inputs[0])
    t.link(lw.outputs['Value'], f.inputs[2])
    lo = _lin(_shift(base, 1 - 0.5 * P['shade'], dh=-0.015, ds=1.1))
    hi = _lin(_shift(base, 1.15, ds=0.95))
    col = _mix(t, f.outputs['Value'], lo, hi)
    em = t.n('ShaderNodeEmission', Strength=1.0)
    t.link(col, em.inputs['Color'])
    return em.outputs['Emission']


def _ceramic(t, base, P):
    # glazed pottery: mirror-sharp highlights, dark crackle lines, glaze speckles, colour pooled in dips
    p = _principled(t, base, Roughness=0.02 + 0.3 * (1 - P['gloss']), **{'Coat Weight': 1.0 * P['gloss'], 'Coat Roughness': 0.0, 'Specular IOR Level': 0.7})
    co = _coords(t)
    col = _speckle(t, base, 0.7, 90.0, 0.7, 1.05)
    if P['pool'] > 0:
        ao = t.n('ShaderNodeAmbientOcclusion', Distance=0.1)
        col = _mix(t, ao.outputs['AO'], _lin(_shift(base, 1 - 0.55 * P['pool'], ds=1 + 0.35 * P['pool'])), col)
    if P['crackle'] > 0:
        vor = t.n('ShaderNodeTexVoronoi', Scale=11.0, _feature='DISTANCE_TO_EDGE')
        t.link(co, vor.inputs['Vector'])
        line = t.n('ShaderNodeMath', _operation='LESS_THAN')
        line.inputs[1].default_value = 0.035 * P['crackle']
        t.link(vor.outputs['Distance'], line.inputs[0])
        col = _mix(t, line.outputs['Value'], col, _lin(_shift(base, 0.35)))
    t.link(col, p.inputs['Base Color'])
    return p.outputs['BSDF']


def _plush(t, base, P):
    # plush toy: soft fur (the strands are grown by Doodle Studio), velvet halo, darker roots
    p = _principled(t, base, Roughness=1.0, **{'Sheen Weight': P['sheen'], 'Sheen Roughness': 0.3, 'Specular IOR Level': 0.0})
    p.inputs['Sheen Tint'].default_value = _lin(_shift(base, 1.3, ds=0.7))
    ao = t.n('ShaderNodeAmbientOcclusion', Distance=0.03)
    t.link(_mix(t, ao.outputs['AO'], _lin(_shift(base, 0.6, ds=1.1)), _speckle(t, base, 0.4, 200.0, 0.85, 1.1)), p.inputs['Base Color'])
    return p.outputs['BSDF']


BUILD = {'clay': _clay, 'cel': _cel, 'vinyl': _vinyl, 'felt': _felt, 'paper': _paper, 'ceramic': _ceramic, 'plush': _plush}


def material(look, rgb, params=None):
    """A material for this look in this colour (linear rgb). Same inputs give the same material."""
    import bpy
    if look not in BUILD:
        raise KeyError(f'no look {look!r} in Doodle Looks')
    P = defaults(look)
    P.update({k: v for k, v in (params or {}).items() if k in P})
    key = hashlib.sha1(json.dumps([look, [round(c, 4) for c in rgb[:3]], P], sort_keys=True).encode()).hexdigest()[:10]
    name = f'DSM {look} {key}'
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = _T(m)
    out = t.n('ShaderNodeOutputMaterial')
    t.link(BUILD[look](t, rgb, P), out.inputs['Surface'])
    out.location = (t.x + 200, 0)
    m.diffuse_color = _lin(rgb)
    m['dsm_look'] = look
    return m
