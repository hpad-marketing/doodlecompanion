"""Surface pass: old weathered painted metal on the body, black polymer on every joint.
python3 weather.py in.blend out.blend
Every look is one shared node group with sliders (Paint, Wear, Rust, Grime, Scale), so the whole robot
can be aged or cleaned from one place (Robot panel > Look).
"""
import bpy, sys, re
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)


def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c] + [1]


# ------------------------------------------------------------------ weathered metal group
def metal_group():
    g = bpy.data.node_groups.get('RB Weathered Metal')
    if g: return g
    g = bpy.data.node_groups.new('RB Weathered Metal', 'ShaderNodeTree')
    I = g.interface
    def inp(n, t, d, lo=0.0, hi=1.0):
        s = I.new_socket(n, in_out='INPUT', socket_type=t); s.default_value = d
        if t == 'NodeSocketFloat': s.min_value, s.max_value = lo, hi
    inp('Paint Colour', 'NodeSocketColor', (0.2, 0.2, 0.2, 1))
    inp('Paint', 'NodeSocketFloat', 1.0)        # 0 = bare steel, 1 = painted
    inp('Wear', 'NodeSocketFloat', 0.75)         # chipped edges exposing steel
    inp('Rust', 'NodeSocketFloat', 0.6)
    inp('Grime', 'NodeSocketFloat', 0.75)        # dirt in cavities + rain streaks
    inp('Scale', 'NodeSocketFloat', 1.0, 0.1, 10)
    I.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    N = g.nodes; L = g.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')

    def node(t, **kw):
        n = N.new(t)
        for k, v in kw.items():
            if k.startswith('i_'): n.inputs[int(k[2:])].default_value = v
            else: setattr(n, k, v)
        return n
    def math(op, a, b=None, clamp=False):
        n = node('ShaderNodeMath', operation=op, use_clamp=clamp)
        for i, x in enumerate((a, b)):
            if x is None: continue
            if isinstance(x, (int, float)): n.inputs[i].default_value = x
            else: L.new(x, n.inputs[i])
        return n.outputs[0]
    def mix(fac, a, b, blend='MIX'):
        n = node('ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_result=True)
        for sock, x in ((0, fac), (6, a), (7, b)):
            if isinstance(x, (tuple, list)): n.inputs[sock].default_value = x
            elif isinstance(x, (int, float)): n.inputs[sock].default_value = x
            else: L.new(x, n.inputs[sock])
        return n.outputs[2]
    def ramp(x, a, b):
        n = node('ShaderNodeMapRange', clamp=True); L.new(x, n.inputs[0])
        n.inputs[1].default_value, n.inputs[2].default_value = a, b
        return n.outputs[0]

    tc = node('ShaderNodeTexCoord')
    sc = node('ShaderNodeVectorMath', operation='SCALE'); L.new(tc.outputs['Object'], sc.inputs[0]); L.new(gi.outputs['Scale'], sc.inputs['Scale'])
    P = sc.outputs[0]
    streak = node('ShaderNodeMapping', vector_type='POINT'); streak.inputs['Scale'].default_value = (2.5, 2.5, 0.35)
    L.new(P, streak.inputs[0])

    def noise(vec, scale, detail=6, rough=0.6, dist=0.0, dims='3D'):
        n = node('ShaderNodeTexNoise', noise_dimensions=dims)
        n.inputs['Scale'].default_value = scale; n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough; n.inputs['Distortion'].default_value = dist
        L.new(vec, n.inputs['Vector']); return n.outputs['Fac']

    S = globals().get('SCAN') or {}           # scanned CC0 maps (Poly Haven), box-projected in object space
    def scan(key, scale, colour=False):
        if key not in S: return None
        t = node('ShaderNodeTexImage', projection='BOX', projection_blend=0.25, interpolation='Cubic'); t.image = S[key]
        m = node('ShaderNodeMapping', vector_type='POINT'); m.inputs['Scale'].default_value = (scale, scale, scale)
        L.new(P, m.inputs[0]); L.new(m.outputs[0], t.inputs['Vector'])
        return t.outputs['Color'] if colour else math('ADD', t.outputs['Color'], 0.0)   # float via implicit convert

    # convex edges + cavities from AO (works in Cycles and EEVEE)
    ao_in = node('ShaderNodeAmbientOcclusion', inside=True, samples=8); ao_in.inputs['Distance'].default_value = 0.012
    ao_out = node('ShaderNodeAmbientOcclusion', samples=8); ao_out.inputs['Distance'].default_value = 0.04
    # EDGES: bevel-normal test (true geometric edges, any size) + AO-inside; SEAMS: tight AO line + wider cavity
    bev = node('ShaderNodeBevel', samples=12); bev.inputs['Radius'].default_value = 0.016
    geo = node('ShaderNodeNewGeometry')
    bdot = node('ShaderNodeVectorMath', operation='DOT_PRODUCT')
    L.new(bev.outputs['Normal'], bdot.inputs[0]); L.new(geo.outputs['Normal'], bdot.inputs[1])
    edge = ramp(bdot.outputs['Value'], 0.975, 0.88)   # bevel test only: AO-inside flags whole thin pins
    ao_seam = node('ShaderNodeAmbientOcclusion', samples=8); ao_seam.inputs['Distance'].default_value = 0.01
    seam = ramp(ao_seam.outputs['AO'], 0.93, 0.5)        # 1 in the narrow gaps where two parts or panels meet
    cavity = math('MAXIMUM', ramp(ao_out.outputs['AO'], 0.92, 0.45), seam)

    n_chip = noise(P, 38, 10, 0.68, 0.4)
    n_big = noise(P, 5, 4, 0.5)
    n_rust = noise(P, 11, 12, 0.7, 0.8)
    n_str = noise(streak.outputs[0], 2.2, 2, 0.45)
    n_fine = noise(P, 160, 4, 0.5)

    # paint chips: edges first, plus a few scattered flake spots, grown by Wear
    chip_src = math('ADD', math('MULTIPLY', edge, 1.3), math('MULTIPLY', n_big, 0.55))
    chip_src = math('ADD', chip_src, math('MULTIPLY', n_chip, 0.9))
    thr = math('SUBTRACT', 1.45, math('MULTIPLY', gi.outputs['Wear'], 0.7))
    chips = ramp(math('SUBTRACT', chip_src, thr), 0.0, 0.04)
    bare = math('MAXIMUM', chips, math('SUBTRACT', 1.0, gi.outputs['Paint']))

    # rust: ONLY along seams, worn edges, cavities and inside chips (never whole faces), broken up by noise
    where = math('MAXIMUM', seam, math('MULTIPLY', edge, math('ADD', 0.35, math('MULTIPLY', bare, 0.4))))
    where = math('MAXIMUM', where, math('MAXIMUM', math('MULTIPLY', cavity, 0.6), math('MULTIPLY', chips, 0.55)))
    rust_src = math('MULTIPLY', where, math('ADD', 0.35, math('MULTIPLY', n_rust, 0.9)))
    rust = ramp(math('SUBTRACT', rust_src, math('SUBTRACT', 0.6, math('MULTIPLY', gi.outputs['Rust'], 0.5))), 0.0, 0.1)

    # grime: cavities + vertical rain streaks
    grime = math('MULTIPLY', math('ADD', math('MULTIPLY', cavity, 0.9), math('MULTIPLY', ramp(n_str, 0.45, 0.7), 0.5)),
                 gi.outputs['Grime'], clamp=True)

    # colours
    paint_var = mix(ramp(n_big, 0.3, 0.75), gi.outputs['Paint Colour'], (0.62, 0.6, 0.56, 1), 'MULTIPLY')
    faded = mix(0.07, paint_var, (0.55, 0.54, 0.5, 1), 'MIX')                                 # sun-bleached
    steel = mix(n_fine, (0.17, 0.17, 0.18, 1), (0.36, 0.35, 0.34, 1))
    scr_map = node('ShaderNodeMapping', vector_type='POINT'); scr_map.inputs['Scale'].default_value = (90, 90, 4)
    scr_map.inputs['Rotation'].default_value = (0.3, 0.5, 0.2); L.new(P, scr_map.inputs[0])
    n_scr = noise(scr_map.outputs[0], 1.5, 2, 0.5, 2.5)
    scratch = math('MULTIPLY', ramp(math('ABSOLUTE', math('SUBTRACT', n_scr, 0.5)), 0.012, 0.0), gi.outputs['Wear'])
    faded = mix(math('MULTIPLY', scratch, 0.7), faded, (0.42, 0.41, 0.39, 1))
    col = mix(bare, faded, steel)
    rust_col = mix(n_chip, (0.07, 0.03, 0.012, 1), (0.2, 0.075, 0.025, 1))
    rust_col = mix(ramp(n_fine, 0.45, 0.65), rust_col, (0.03, 0.018, 0.01, 1))
    s_rust = scan('rust_coarse_01_diff', 2.2, True)
    if s_rust:                                                   # real rust photo over the procedural one
        s_rust = mix(0.35, s_rust, (0.05, 0.025, 0.012, 1), 'MULTIPLY')
        rust_col = mix(0.7, rust_col, s_rust)
    col = mix(rust, col, rust_col)
    col = mix(grime, col, (0.035, 0.03, 0.025, 1), 'MULTIPLY')
    col = mix(math('MULTIPLY', grime, 0.6), col, (0.06, 0.05, 0.04, 1))
    col = mix(math('MULTIPLY', seam, 0.75), col, (0.025, 0.02, 0.015, 1))        # dark line in every seam
    polish = math('MULTIPLY', math('MULTIPLY', edge, bare), math('SUBTRACT', 1.0, rust))
    col = mix(math('MULTIPLY', polish, 0.6), col, (0.62, 0.6, 0.57, 1))            # rubbed-bright steel on worn edges

    # ---- wear that fits the job: per-part object attributes (0 = off) ----
    def oattr(name):
        a = node('ShaderNodeAttribute', attribute_type='OBJECT', attribute_name=name); return a.outputs['Fac']
    gz = node('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Generated'], gz.inputs[0]); Z = gz.outputs['Z']
    # oil: weeps from the top of the part (seals) and runs down in thin streaks
    oil_run = math('MULTIPLY', ramp(Z, 0.05, 0.9), ramp(noise(streak.outputs[0], 7, 3, 0.55), 0.47, 0.56))
    oil = math('MULTIPLY', math('MAXIMUM', oil_run, math('MULTIPLY', seam, 0.8)), oattr('rb_oil'), clamp=True)
    # mud: crust from the bottom up with a ragged line, thicker in cavities
    m_amt = oattr('rb_mud')
    mud_line = math('ADD', math('SUBTRACT', 1.0, Z), math('MULTIPLY', n_big, 0.35))
    mud_line = math('ADD', mud_line, math('MULTIPLY', m_amt, 0.45))           # 1.0 = crust up to about half the part
    mud = math('MULTIPLY', ramp(mud_line, 0.95, 1.08), math('MINIMUM', math('MULTIPLY', m_amt, 4.0), 1.0), clamp=True)
    splat = ramp(noise(P, 14, 3, 0.6, 0.6), 0.66, 0.7)                        # thrown-up splashes higher up
    mud = math('MAXIMUM', mud, math('MULTIPLY', splat, math('MULTIPLY', m_amt, 0.9)))
    mud = math('MAXIMUM', mud, math('MULTIPLY', math('MULTIPLY', cavity, oattr('rb_mud')), 0.8))
    mud = math('MULTIPLY', mud, ramp(n_chip, 0.25, 0.45))        # flaked off in places
    mud.node.label = 'MUD'; oil.node.label = 'OIL'
    # heat: temper colours on bare steel near vents (straw > purple > blue by noise)
    heat = math('MULTIPLY', oattr('rb_heat'), ramp(n_big, 0.35, 0.7))
    # touch: greasy finger smudges, glossy and slightly dark
    touch = math('MULTIPLY', oattr('rb_touch'), ramp(noise(P, 24, 2, 0.4), 0.55, 0.68))
    tint = node('ShaderNodeValToRGB'); L.new(math('ADD', math('MULTIPLY', Z, 0.6), math('MULTIPLY', n_big, 0.5)), tint.inputs[0]); E = tint.color_ramp.elements
    E[0].position, E[0].color = 0.3, (0.48, 0.33, 0.12, 1); E[1].position, E[1].color = 0.7, (0.09, 0.12, 0.3, 1)
    e3 = E.new(0.5); e3.color = (0.26, 0.11, 0.2, 1)
    col = mix(math('MULTIPLY', heat, math('ADD', math('MULTIPLY', bare, 0.45), 0.25)), col, tint.outputs['Color'])
    col = mix(math('MULTIPLY', oil, 0.85), col, (0.02, 0.016, 0.01, 1))
    mud_col = mix(ramp(n_rust, 0.35, 0.65), (0.2, 0.16, 0.11, 1), (0.42, 0.36, 0.27, 1))      # dry, pale crust
    mud_col = mix(math('MULTIPLY', ramp(n_big, 0.55, 0.75), 0.8), mud_col, (0.1, 0.075, 0.05, 1))  # still-damp patches
    col = mix(math('MULTIPLY', mud, ramp(n_fine, 0.3, 0.45)), col, mud_col)
    col = mix(math('MULTIPLY', touch, 0.35), col, (0.04, 0.035, 0.03, 1))

    metallic = math('MULTIPLY', bare, math('SUBTRACT', 1.0, rust))
    metallic = math('MULTIPLY', metallic, math('SUBTRACT', 1.0, mud))
    rough = math('ADD', math('MULTIPLY', n_big, 0.18), 0.5)
    rough = math('ADD', rough, math('MULTIPLY', oil, -0.4))
    rough = math('ADD', rough, math('MULTIPLY', touch, -0.25))
    rough = math('ADD', rough, math('MULTIPLY', mud, 0.45))
    s_pr = scan('blue_metal_plate_rough', 1.6); s_br = scan('metal_plate_rough', 1.3)
    if s_pr: rough = math('ADD', rough, math('MULTIPLY', math('SUBTRACT', s_pr, 0.5), math('MULTIPLY', math('SUBTRACT', 1.0, bare), 0.35)))
    if s_br: rough = math('ADD', rough, math('MULTIPLY', math('SUBTRACT', s_br, 0.45), math('MULTIPLY', bare, 0.45)))
    rough = math('ADD', rough, math('MULTIPLY', bare, -0.16))
    rough = math('ADD', rough, math('MULTIPLY', rust, 0.5))
    rough = math('ADD', rough, math('MULTIPLY', grime, 0.1))
    rough = math('ADD', rough, math('MULTIPLY', polish, -0.18), clamp=True)

    # bump: chip rims step down, rust is pitted
    height = math('ADD', math('MULTIPLY', math('SUBTRACT', 1.0, chips), 0.5), math('MULTIPLY', math('MULTIPLY', rust, n_rust), 0.5))
    height = math('ADD', height, math('MULTIPLY', n_fine, 0.08))
    height = math('ADD', height, math('MULTIPLY', mud, math('ADD', 0.6, math('MULTIPLY', n_chip, 0.6))))   # mud crust stands proud
    s_rh = scan('rust_coarse_01_rough', 2.2)
    if s_rh: height = math('ADD', height, math('MULTIPLY', math('MULTIPLY', s_rh, rust), 0.45))     # real pitting
    if s_br: height = math('ADD', height, math('MULTIPLY', s_br, 0.04))
    bump = node('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.35; bump.inputs['Distance'].default_value = 0.002
    L.new(height, bump.inputs['Height']); L.new(bev.outputs['Normal'], bump.inputs['Normal'])   # rounded edge highlights
    # dents: soft voronoi dimples, mostly on big flat panels, scaled by Wear
    vor = node('ShaderNodeTexVoronoi', feature='SMOOTH_F1'); vor.inputs['Scale'].default_value = 4.0
    vor.inputs['Smoothness'].default_value = 1.0; vor.inputs['Randomness'].default_value = 1.0; L.new(P, vor.inputs['Vector'])
    dent_mask = ramp(noise(P, 3, 2, 0.5), 0.55, 0.7)
    dent = math('MULTIPLY', math('MULTIPLY', ramp(vor.outputs['Distance'], 0.0, 0.32), dent_mask), gi.outputs['Wear'])
    bump2 = node('ShaderNodeBump'); bump2.inputs['Strength'].default_value = 0.6; bump2.inputs['Distance'].default_value = 0.006
    L.new(dent, bump2.inputs['Height']); L.new(bump.outputs[0], bump2.inputs['Normal']); bump = bump2

    b = node('ShaderNodeBsdfPrincipled')
    L.new(col, b.inputs['Base Color']); L.new(metallic, b.inputs['Metallic']); L.new(rough, b.inputs['Roughness'])
    L.new(bump.outputs[0], b.inputs['Normal'])
    L.new(b.outputs[0], go.inputs[0])
    return g


def polymer_group():
    g = bpy.data.node_groups.get('RB Black Polymer')
    if g: return g
    g = bpy.data.node_groups.new('RB Black Polymer', 'ShaderNodeTree')
    I = g.interface
    s = I.new_socket('Colour', in_out='INPUT', socket_type='NodeSocketColor'); s.default_value = srgb('#151617')
    s = I.new_socket('Scuffs', in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = 0.5; s.min_value, s.max_value = 0, 1
    s = I.new_socket('Grime', in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = 0.5; s.min_value, s.max_value = 0, 1
    I.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    N = g.nodes; L = g.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    tc = N.new('ShaderNodeTexCoord')
    fine = N.new('ShaderNodeTexNoise'); fine.inputs['Scale'].default_value = 220; fine.inputs['Detail'].default_value = 3
    L.new(tc.outputs['Object'], fine.inputs['Vector'])
    blot = N.new('ShaderNodeTexNoise'); blot.inputs['Scale'].default_value = 9; blot.inputs['Detail'].default_value = 5
    L.new(tc.outputs['Object'], blot.inputs['Vector'])
    ao = N.new('ShaderNodeAmbientOcclusion'); ao.inside = True; ao.samples = 8; ao.inputs['Distance'].default_value = 0.01
    edge0 = N.new('ShaderNodeMapRange'); edge0.inputs[1].default_value = 0.98; edge0.inputs[2].default_value = 0.75
    L.new(ao.outputs['AO'], edge0.inputs[0])
    bev = N.new('ShaderNodeBevel'); bev.samples = 12; bev.inputs['Radius'].default_value = 0.006
    geo = N.new('ShaderNodeNewGeometry')
    bd = N.new('ShaderNodeVectorMath'); bd.operation = 'DOT_PRODUCT'
    L.new(bev.outputs['Normal'], bd.inputs[0]); L.new(geo.outputs['Normal'], bd.inputs[1])
    edge1 = N.new('ShaderNodeMapRange'); edge1.inputs[1].default_value = 0.975; edge1.inputs[2].default_value = 0.88
    L.new(bd.outputs['Value'], edge1.inputs[0])
    edge = N.new('ShaderNodeMath'); edge.operation = 'MAXIMUM'; L.new(edge1.outputs[0], edge.inputs[0]); L.new(edge1.outputs[0], edge.inputs[1])
    aos = N.new('ShaderNodeAmbientOcclusion'); aos.samples = 8; aos.inputs['Distance'].default_value = 0.012
    seam = N.new('ShaderNodeMapRange'); seam.inputs[1].default_value = 0.93; seam.inputs[2].default_value = 0.5
    L.new(aos.outputs['AO'], seam.inputs[0])
    sg = N.new('ShaderNodeMath'); sg.operation = 'MULTIPLY'; L.new(seam.outputs[0], sg.inputs[0]); L.new(gi.outputs['Grime'], sg.inputs[1])
    sc = N.new('ShaderNodeMath'); sc.operation = 'MULTIPLY'; L.new(edge.outputs[0], sc.inputs[0]); L.new(gi.outputs['Scuffs'], sc.inputs[1])
    worn = N.new('ShaderNodeMix'); worn.data_type = 'RGBA'; L.new(sc.outputs[0], worn.inputs[0])
    L.new(gi.outputs['Colour'], worn.inputs[6]); worn.inputs[7].default_value = srgb('#3A3B3C')
    rough = N.new('ShaderNodeMapRange'); rough.inputs[3].default_value = 0.38; rough.inputs[4].default_value = 0.62
    L.new(blot.outputs['Fac'], rough.inputs[0])
    dirt = N.new('ShaderNodeMix'); dirt.data_type = 'RGBA'; L.new(sg.outputs[0], dirt.inputs[0])
    L.new(worn.outputs[2], dirt.inputs[6]); dirt.inputs[7].default_value = srgb('#0A0A09')
    rs = N.new('ShaderNodeMath'); rs.operation = 'ADD'; L.new(rough.outputs[0], rs.inputs[0]); L.new(sc.outputs[0], rs.inputs[1])
    rs2 = N.new('ShaderNodeMath'); rs2.operation = 'MULTIPLY_ADD'; L.new(sg.outputs[0], rs2.inputs[0]); rs2.inputs[1].default_value = 0.25
    L.new(rs.outputs[0], rs2.inputs[2]); rs2.use_clamp = True
    rs.use_clamp = True
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08; bump.inputs['Distance'].default_value = 0.001
    L.new(fine.outputs['Fac'], bump.inputs['Height']); L.new(bev.outputs['Normal'], bump.inputs['Normal'])
    b = N.new('ShaderNodeBsdfPrincipled')
    L.new(dirt.outputs[2], b.inputs['Base Color']); L.new(rs2.outputs[0], b.inputs['Roughness'])
    b.inputs['Coat Weight'].default_value = 0.15; b.inputs['Coat Roughness'].default_value = 0.35
    b.inputs['Specular IOR Level'].default_value = 0.45
    L.new(bump.outputs[0], b.inputs['Normal'])
    L.new(b.outputs[0], go.inputs[0])
    return g


def material(name, group, vals, viewport):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    nt = m.node_tree; nt.nodes.clear()
    gn = nt.nodes.new('ShaderNodeGroup'); gn.node_tree = group; gn.name = 'Look'
    vals = dict(vals); vals['Scale'] = vals.get('Scale', 1.0) * (globals()['kit'].get('weather_scale', 1.0) if 'kit' in globals() else 1.0)   # small droids: finer wear
    for k, v in vals.items():
        if k in gn.inputs: gn.inputs[k].default_value = v   # the polymer group has no Scale input
    o = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(gn.outputs[0], o.inputs['Surface'])
    m.diffuse_color = viewport; m.roughness = 0.6
    return m


import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import kit
MG, PG = metal_group(), polymer_group()
PAINT = kit.get('paint', {  # paint colour under the wear, per role (material RB_metal_<role>)
    'grey': '#434E58', 'tan': '#A38F68', 'teal': '#5F9692', 'navy': '#2B3A5C', 'yellow': '#C99A2E',
    'sage': '#85A68C', 'olive': '#66713D'})
NEW = {}
for k, hx in PAINT.items():
    NEW['RB_' + k] = material(f'RB_metal_{k}', MG, {'Paint Colour': srgb(hx)}, srgb(hx))
NEW['bare'] = material('RB_metal_bare', MG, {'Paint Colour': srgb('#3A3D40'), 'Paint': 0.0, 'Rust': 0.7}, srgb('#55585B'))
NEW['RB_steel'] = material('RB_metal_pin', MG, {'Paint': 0.0, 'Rust': 0.15, 'Grime': 0.35, 'Scale': 3.0}, srgb('#7A7D80'))
NEW['poly'] = material('RB_polymer', PG, {}, srgb('#151617'))
lens = material('RB_lens', PG, {'Colour': srgb('#0B0C0D'), 'Scuffs': 0.1}, srgb('#0B0C0D'))
lb = lens.node_tree.nodes['Look']

JOINT = re.compile(kit.get('joint_regex', r'(cheek|tongue|knuckle|_joint|joint\d|drum|bearing|bracket|roll_bar|bridge|collar|wrist_cross|disc|turret|'
                   r'turntable|socket|waist_ring|yoke|lug|_tab[+-]|_eye|gland|clamp|riser|_drop|elbow_joint|knee_joint|hip_axle)'))
count = {}
for o in bpy.data.objects:
    if o.type != 'MESH' or not o.material_slots or not o.material_slots[0].material: continue
    old = o.material_slots[0].material.name
    if not old.startswith('RB_') or old.startswith(('RB_metal', 'RB_polymer', 'RB_lens')): continue
    if o.name.startswith('sensor_lens'): m = lens
    elif old == 'RB_frame': m = NEW['poly'] if JOINT.search(o.name) else NEW['bare']
    elif old == 'RB_steel': m = NEW['RB_steel']
    elif old in NEW: m = NEW[old]
    else: continue
    for s in o.material_slots: s.material = m
    count[m.name] = count.get(m.name, 0) + 1
for pat, role in kit.get('material_overrides', {}).items():   # e.g. {"pauldron_vent0": "yellow"}: part painted in a palette role
    rx = re.compile(pat)
    for o in bpy.data.objects:
        if o.type == 'MESH' and rx.search(o.name) and ('RB_' + role) in NEW:
            for s_ in o.material_slots: s_.material = NEW['RB_' + role]
for o in bpy.data.objects:   # hoses are curves: black polymer too
    if o.type == 'CURVE' and o.name.startswith('hose'):
        o.data.materials.clear(); o.data.materials.append(NEW['poly']); count['RB_polymer'] = count.get('RB_polymer', 0) + 1
for m in [m for m in bpy.data.materials if m.users == 0]: bpy.data.materials.remove(m)
print('WEATHER', count)
bpy.ops.wm.save_as_mainfile(filepath=out)
