"""The Doodle Studio look for library assets.

Reuses the 3D Bunny's own look module (materials, DS_InkOutline, the pixel
size group), so props and scenery get exactly Bunny's ink: one screen-constant
weight driven from BUNNY_settings.ink_px. On top of the silhouette hull this
adds crease lines (edges marked `dsl_crease`) drawn as tubes of the same
screen width, so a table top, a book spine or a window frame gets its line.

Shadows are optional: library fills use DSL_mustard, a two-tone material that
is flat brand mustard until DSL_settings.shadows > 0, then shows cast shadows
(and form shading if `form` > 0) in a darker mustard mixed from the two brand
colours. Off by default, so the flat Doodle Studio look stays the default.
"""
import math

import bpy
import bmesh

from . import paths

MOD_NAME = 'DSL Ink'
INK_HEX = '#1F1F1D'
MUSTARD_HEX = '#E0A64B'


def look():
    return paths.bunny_module('look')


# ---------------------------------------------------------------- settings
SETTINGS_NIGHT = 'Night: unlit surfaces sink toward ink, lamps light pools around them'


def settings():
    ob = bpy.data.objects.get('DSL_settings')
    if ob:
        if 'night' not in ob:  # files saved before time of day
            ob['night'] = 0.0
            ob.id_properties_ui('night').update(min=0.0, max=1.0, description=SETTINGS_NIGHT)
        return ob
    ob = bpy.data.objects.new('DSL_settings', None)
    ob.empty_display_size = 0.05
    ob.hide_render = True
    coll = bpy.data.collections.get('Doodle Library') or bpy.data.collections.new('Doodle Library')
    if coll.name not in bpy.context.scene.collection.children:
        try:
            bpy.context.scene.collection.children.link(coll)
        except RuntimeError:
            pass
    coll.objects.link(ob)
    props = {
        'shadows': (0.0, 0.0, 1.0, 'Show shadows on library assets (0 = flat Doodle Studio look)'),
        'shade_mix': (0.32, 0.0, 1.0, 'How far the shadow colour moves from mustard toward ink'),
        'form': (0.0, 0.0, 1.0, 'Also shade the sides turned away from the light (toon form shading)'),
        'ambient': (0.45, 0.0, 5.0, 'World light level an unlit surface still gets (tunes the cast-shadow test)'),
        'night': (0.0, 0.0, 1.0, SETTINGS_NIGHT),
    }
    for k, (v, mn, mx, desc) in props.items():
        ob[k] = v
        ob.id_properties_ui(k).update(min=mn, max=mx, description=desc)
    return ob


def bunny_settings():
    return look().settings_object(bpy.data.collections.get('Doodle Library'))


# ---------------------------------------------------------------- materials
def _driver(sock_owner, path, target, data_path, expr='v'):
    fc = sock_owner.driver_add(path)
    d = fc.driver
    d.type = 'SCRIPTED'
    v = d.variables.new()
    v.name = 'v'
    v.targets[0].id = target
    v.targets[0].data_path = data_path
    d.expression = expr
    return fc


TOON_VERSION = 2   # bump when the toon shader changes: older materials get rebuilt
NIGHT_DIM = 0.72   # how far toward ink an unlit surface goes at night


def toon_material(name, hexcol, driven=True):
    """Flat brand colour; with DSL_settings.shadows up, shadowed parts darken toward ink.

    Cast shadow test: the light that actually arrives (Diffuse -> Shader to RGB)
    is compared with what an unshadowed surface at that angle would get
    (ambient + sun * N.L / pi). Clearly less = in a cast shadow. With `form` up,
    sides turned away from the sun are shaded too (toon form shading).
    """
    lk = look()
    m = bpy.data.materials.get(name)
    if m and m.get('dsl_toon', 0) >= TOON_VERSION:
        return m
    m = m or bpy.data.materials.new(name)
    m['dsl_toon'] = TOON_VERSION
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links

    def node(kind, x, y, **kw):
        n = N.new(kind)
        n.location = (x, y)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def math(op, a, b, x, y):
        n = node('ShaderNodeMath', x, y, operation=op)
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    out = node('ShaderNodeOutputMaterial', 1300, 0)
    em = node('ShaderNodeEmission', 1100, 0)
    L.new(em.outputs[0], out.inputs['Surface'])
    diff = node('ShaderNodeBsdfDiffuse', -900, 200)
    diff.inputs['Color'].default_value = (1, 1, 1, 1)
    s2r = node('ShaderNodeShaderToRGB', -700, 200)
    L.new(diff.outputs[0], s2r.inputs[0])
    bw = node('ShaderNodeRGBToBW', -500, 200)
    L.new(s2r.outputs['Color'], bw.inputs[0])
    vals = {}
    for i, (k, default) in enumerate((('shadows', 0.0), ('shade_mix', 0.32), ('form', 0.0), ('ambient', 0.45),
                                      ('energy', 6.0), ('lx', 0.0), ('ly', 0.0), ('lz', 1.0), ('night', 0.0))):
        v = node('ShaderNodeValue', -900, -100 - 90 * i)
        v.name = v.label = 'DSL ' + k
        v.outputs[0].default_value = default
        vals[k] = v
    ldir = node('ShaderNodeCombineXYZ', -700, -500)
    for ax in 'xyz':
        L.new(vals['l' + ax].outputs[0], ldir.inputs[ax.upper()])
    geo = node('ShaderNodeNewGeometry', -700, -250)
    dot = node('ShaderNodeVectorMath', -500, -300, operation='DOT_PRODUCT')
    L.new(geo.outputs['Normal'], dot.inputs[0])
    L.new(ldir.outputs[0], dot.inputs[1])
    ndl = dot.outputs['Value']
    expect = math('ADD', vals['ambient'].outputs[0],
                  math('MULTIPLY', math('MULTIPLY', vals['energy'].outputs[0], 0.5 / 3.14159, -300, -350),
                       math('MAXIMUM', ndl, 0.0, -300, -450), -150, -400), 0, -350)
    cast = math('MULTIPLY', math('LESS_THAN', bw.outputs[0], expect, 200, 100),
                math('GREATER_THAN', ndl, 0.08, 200, -100), 400, 0)
    away = math('MULTIPLY', math('LESS_THAN', ndl, 0.08, 200, -250), vals['form'].outputs[0], 400, -200)
    dark = math('MINIMUM', math('ADD', cast, away, 550, -50), 1.0, 700, -50)
    fac = math('MULTIPLY', dark, vals['shadows'].outputs[0], 850, -50)
    shade = node('ShaderNodeMix', 700, -300, data_type='RGBA')
    shade.inputs['A'].default_value = lk.hex_linear(hexcol)
    shade.inputs['B'].default_value = lk.hex_linear(INK_HEX)
    L.new(vals['shade_mix'].outputs[0], shade.inputs['Factor'])
    mix = node('ShaderNodeMix', 950, 0, data_type='RGBA')
    mix.inputs['A'].default_value = lk.hex_linear(hexcol)
    L.new(shade.outputs['Result'], mix.inputs['B'])
    L.new(fac, mix.inputs['Factor'])
    # night: everything sinks toward ink except where a lamp's light lands (sun is off at night)
    dim = node('ShaderNodeMix', 950, -250, data_type='RGBA')
    dim.inputs['A'].default_value = lk.hex_linear(hexcol)
    dim.inputs['B'].default_value = lk.hex_linear(INK_HEX)
    dim.inputs['Factor'].default_value = NIGHT_DIM
    lit = math('MINIMUM', math('MULTIPLY', bw.outputs[0], 1.6, 800, -450), 1.0, 950, -450)
    lamp = node('ShaderNodeMix', 1050, -300, data_type='RGBA')
    L.new(dim.outputs['Result'], lamp.inputs['A'])
    lamp.inputs['B'].default_value = lk.hex_linear(hexcol)
    L.new(lit, lamp.inputs['Factor'])
    night = node('ShaderNodeMix', 1100, -100, data_type='RGBA')
    L.new(mix.outputs['Result'], night.inputs['A'])
    L.new(lamp.outputs['Result'], night.inputs['B'])
    L.new(vals['night'].outputs[0], night.inputs['Factor'])
    L.new(night.outputs['Result'], em.inputs['Color'])
    m.diffuse_color = lk.hex_linear(hexcol)
    if driven:
        st = settings()
        sun = ensure_sun()
        for k in ('shadows', 'shade_mix', 'form', 'ambient', 'night'):
            _driver(vals[k].outputs[0], 'default_value', st, '["%s"]' % k)
        _driver(vals['energy'].outputs[0], 'default_value', sun, 'data.energy')
        for i, ax in enumerate('xyz'):
            _driver(vals['l' + ax].outputs[0], 'default_value', sun, 'matrix_world[2][%d]' % i)
    return m


def materials():
    lk = look()
    base = lk.materials()  # DS_mustard, DS_ink, DS_ink_outline (shared with Bunny)
    return dict(mustard=toon_material('DSL_mustard', MUSTARD_HEX), ink=base['ink'], shell=base['shell'],
                bunny_mustard=base['mustard'])


def remap_materials(ob, mats=None):
    """Library files carry placeholder materials; point them at this file's real ones."""
    mats = mats or materials()
    for slot in ob.material_slots:
        m = slot.material
        if not m:
            continue
        nm = m.name.split('.')[0]
        new = {'DSL_mustard': mats['mustard'], 'DS_mustard': mats['mustard'], 'DS_ink': mats['ink'],
               'DSL_ink': mats['ink']}.get(nm)
        if new and new is not m:
            slot.material = new
            if m.users == 0:
                bpy.data.materials.remove(m)


# ---------------------------------------------------------------- crease lines
def compute_creases(me, angle_deg=32.0, groups_attr='dsl_group'):
    """Mark edges that get a line: sharp creases, open borders, part boundaries."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    gl = bm.faces.layers.int.get(groups_attr)
    lim = math.radians(angle_deg)
    flags = []
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            flags.append(len(lf) == 1)
            continue
        on = e.calc_face_angle(0.0) > lim
        if not on and gl is not None and lf[0][gl] != lf[1][gl]:
            on = True
        flags.append(on)
    bm.free()
    a = me.attributes.get('dsl_crease')
    if a and (a.domain != 'EDGE' or a.data_type != 'BOOLEAN'):
        me.attributes.remove(a)
        a = None
    a = a or me.attributes.new('dsl_crease', 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', flags)
    return sum(flags)


def ink_group():
    """DSL_Ink: Bunny's DS_InkOutline (fill + silhouette) plus crease tubes."""
    name = 'DSL_Ink'
    ng = bpy.data.node_groups.get(name)
    if ng:
        return ng
    lk = look()
    G, _sock = lk.G, lk._sock
    hull_tree = lk.ink_group()
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    _sock(ng, 'Geometry', 'NodeSocketGeometry')
    for item in hull_tree.interface.items_tree:
        if getattr(item, 'in_out', None) == 'INPUT' and item.name != 'Geometry':
            s = ng.interface.new_socket(item.name, in_out='INPUT', socket_type=item.socket_type)
            if hasattr(item, 'default_value') and hasattr(s, 'default_value'):
                s.default_value = item.default_value
    _sock(ng, 'Lines', 'NodeSocketBool', default=True)
    _sock(ng, 'Line Material', 'NodeSocketMaterial')
    _sock(ng, 'Geometry', 'NodeSocketGeometry', io='OUTPUT')
    g = G(ng)
    gi = g.node('NodeGroupInput')
    go = g.node('NodeGroupOutput')
    hull = g.node('GeometryNodeGroup')
    hull.node_tree = hull_tree
    for s in hull.inputs:
        if s.name in gi.outputs:
            g.link(gi.outputs[s.name], s)
    # crease edges -> curves -> tubes one ink wide (screen-constant)
    att = g.node('GeometryNodeInputNamedAttribute', data_type='BOOLEAN')
    att.inputs['Name'].default_value = 'dsl_crease'
    # lift the line half a stroke off the surface along the vertex normal, so lines in
    # inside corners (floor meets wall) show their full width instead of a buried sliver
    px0 = g.node('GeometryNodeGroup')
    px0.node_tree = lk.pixel_size_group()
    for k in ('Camera', 'Orthographic', 'Ortho Scale', 'Sensor / Focal'):
        g.link(gi.outputs[k], px0.inputs[k])
    lift = g.node('GeometryNodeSetPosition')
    g.link(gi.outputs['Geometry'], lift.inputs['Geometry'])
    g.link(g.vmath('SCALE', g.node('GeometryNodeInputNormal').outputs[0],
                   scale=g.math('MULTIPLY', g.math('MULTIPLY', px0.outputs[0], gi.outputs['Ink Fraction']), 0.5)),
           lift.inputs['Offset'])
    m2c = g.node('GeometryNodeMeshToCurve')
    g.link(lift.outputs[0], m2c.inputs['Mesh'])
    g.link(att.outputs['Attribute'], m2c.inputs['Selection'])
    px = g.node('GeometryNodeGroup')
    px.node_tree = lk.pixel_size_group()
    for k in ('Camera', 'Orthographic', 'Ortho Scale', 'Sensor / Focal'):
        g.link(gi.outputs[k], px.inputs[k])
    ink_w = g.math('MULTIPLY', px.outputs[0], gi.outputs['Ink Fraction'])
    # stepped boil, same rhythm as the hull
    st = g.node('GeometryNodeInputSceneTime')
    stepped = g.math('FLOOR', g.math('DIVIDE', st.outputs['Frame'], gi.outputs['Boil Step']))
    w = g.math('ADD', g.math('MULTIPLY', stepped, 1.37), gi.outputs['Seed'])
    noise = g.node('ShaderNodeTexNoise', noise_dimensions='4D')
    noise.inputs['Scale'].default_value = 3.0
    noise.inputs['Detail'].default_value = 1.0
    g.link(g.node('GeometryNodeInputPosition').outputs[0], noise.inputs['Vector'])
    g.link(w, noise.inputs['W'])
    cen = g.vmath('SUBTRACT', noise.outputs['Color'], (0.5, 0.5, 0.5))
    amp = g.math('MULTIPLY', g.math('MULTIPLY', px.outputs[0], gi.outputs['Boil Fraction']), gi.outputs['Boil Amount'])
    sp = g.node('GeometryNodeSetPosition')
    g.link(m2c.outputs[0], sp.inputs['Geometry'])
    g.link(g.vmath('SCALE', cen, scale=g.math('MULTIPLY', amp, 2.0)), sp.inputs['Offset'])
    rad = g.node('GeometryNodeSetCurveRadius')
    g.link(sp.outputs[0], rad.inputs['Curve'])
    g.link(g.math('MULTIPLY', ink_w, 0.5), rad.inputs['Radius'])
    prof = g.node('GeometryNodeCurvePrimitiveCircle')
    prof.inputs['Resolution'].default_value = 8
    prof.inputs['Radius'].default_value = 1.0
    c2m = g.node('GeometryNodeCurveToMesh')
    g.link(rad.outputs[0], c2m.inputs['Curve'])
    g.link(prof.outputs[0], c2m.inputs['Profile Curve'])
    c2m.inputs['Fill Caps'].default_value = True
    if 'Scale' in c2m.inputs:  # 4.2+: the profile follows Scale, not the radius attribute
        rr = g.node('GeometryNodeInputRadius')
        g.link(rr.outputs[0], c2m.inputs['Scale'])
    smat = g.node('GeometryNodeSetMaterial')
    g.link(c2m.outputs[0], smat.inputs['Geometry'])
    g.link(gi.outputs['Line Material'], smat.inputs['Material'])
    sw = g.node('GeometryNodeSwitch', input_type='GEOMETRY')
    g.link(gi.outputs['Lines'], sw.inputs['Switch'])
    g.link(smat.outputs[0], sw.inputs['True'])
    join = g.node('GeometryNodeJoinGeometry')
    g.link(hull.outputs[0], join.inputs[0])
    g.link(sw.outputs[0], join.inputs[0])
    g.link(join.outputs[0], go.inputs['Geometry'])
    return ng


def apply_style(ob, cam=None, mats=None, outline=True, lines=True, seed=0.0):
    """Give an object Bunny's ink, driven by the scene camera and BUNNY_settings."""
    if ob.type != 'MESH':
        return None
    lk = look()
    mats = mats or materials()
    remap_materials(ob, mats)
    cam = cam or bpy.context.scene.camera
    old = ob.modifiers.get(MOD_NAME)
    if old:
        ob.modifiers.remove(old)
    if 'dsl_crease' not in ob.data.attributes:
        compute_creases(ob.data)
    mod = ob.modifiers.new(MOD_NAME, 'NODES')
    mod.node_group = ink_group()
    ids = {s.name: s.identifier for s in mod.node_group.interface.items_tree if getattr(s, 'in_out', None) == 'INPUT'}
    mod[ids['Outline Material']] = mats['shell']
    mod[ids['Line Material']] = mats['ink']
    mod[ids['Outline']] = outline
    mod[ids['Lines']] = lines
    mod[ids['Seed']] = seed
    ob['dsl_seed'] = seed
    bset = bunny_settings()
    if cam:
        mod[ids['Camera']] = cam
        lk._drive(mod, f'["{ids["Orthographic"]}"]', cam.data, 'type', expr="v == 1", id_type='CAMERA')
        lk._drive(mod, f'["{ids["Ortho Scale"]}"]', cam.data, 'ortho_scale', id_type='CAMERA')
        fc = mod.driver_add(f'["{ids["Sensor / Focal"]}"]')
        d = fc.driver
        d.type = 'SCRIPTED'
        for nm, p in (('s', 'sensor_width'), ('f', 'lens')):
            v = d.variables.new()
            v.name = nm
            v.targets[0].id_type = 'CAMERA'
            v.targets[0].id = cam.data
            v.targets[0].data_path = p
        d.expression = 's / f'
    lk._drive(mod, f'["{ids["Ink Fraction"]}"]', bset, '["ink_px"]', expr='v / 1920')
    lk._drive(mod, f'["{ids["Boil Amount"]}"]', bset, '["boil"]')
    lk._drive(mod, f'["{ids["Boil Fraction"]}"]', bset, '["boil_px"]', expr='v / 1920')
    lk._drive(mod, f'["{ids["Boil Step"]}"]', bset, '["boil_step"]')
    return mod


def retarget_camera(cam):
    """Point every library ink modifier at `cam` (after switching cameras)."""
    n = 0
    for ob in bpy.data.objects:
        if ob.modifiers.get(MOD_NAME):
            apply_style(ob, cam, seed=ob.get('dsl_seed', 0.0))
            n += 1
    return n


# ---------------------------------------------------------------- light
def ensure_sun(scene=None):
    scene = scene or bpy.context.scene
    sun = bpy.data.objects.get('DSL_Sun')
    if not sun:
        data = bpy.data.lights.new('DSL_Sun', 'SUN')
        data.energy = 6.0
        data.angle = math.radians(0.5)  # crisp, toon-like shadow edges
        data.color = (1, 1, 1)
        sun = bpy.data.objects.new('DSL_Sun', data)
        coll = bpy.data.collections.get('Doodle Library') or scene.collection
        coll.objects.link(sun)
        sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
    if hasattr(sun.data, 'use_shadow'):
        sun.data.use_shadow = True
    return sun


def set_shadows(on, strength=None, form=None, bunny_too=False):
    st = settings()
    st['shadows'] = 1.0 if on else 0.0
    if strength is not None:
        st['shade_mix'] = strength
    if form is not None:
        st['form'] = form
    if on:
        ensure_sun()
    # Bunny's own mustard (flat emission) can take shadows too, on request
    m = bpy.data.materials.get('DS_mustard')
    if m is not None:
        if on and bunny_too and not m.get('dsl_toon'):
            m['dsl_was_flat'] = 1
            toon_material('DS_mustard', MUSTARD_HEX)
        elif (not on or not bunny_too) and m.get('dsl_was_flat'):
            m.pop('dsl_toon', None)
            m.pop('dsl_was_flat', None)
            look().flat_material('DS_mustard', MUSTARD_HEX)
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            ob.update_tag()
