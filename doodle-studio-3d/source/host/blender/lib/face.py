"""Bunny's face: every Doodle Studio expression, gaze, blink/wink and speech mouth.

face_library.json (made by face_prep.py) holds the exact 2D ink of each face
state in the head's front plane. Here it becomes two hidden library meshes
(fills as triangles, strokes as centre lines) and a geometry-node switch that
keeps only the current state, draws the strokes at the same screen-constant
width as the body outline, boils them, and wraps everything onto the head.
"""
import bpy

import compat
import json
from mathutils import Vector
from mathutils.geometry import tessellate_polygon
from look import G, _sock, pixel_size_group, _drive, settings_object

ROLE = {'eyes': 0, 'mouth': 1, 'speech': 2}


def _attr(me, name, kind, values):
    a = me.attributes.new(name, kind, 'POINT')
    a.data.foreach_set('value', values)


def build_library(lib_path, S, coll):
    L = json.load(open(lib_path))
    fv, ff, fattr = [], [], {k: [] for k in ('role', 'face', 'gaze', 'speech')}
    sv, se, sattr = [], [], {k: [] for k in ('role', 'face', 'gaze', 'speech')}
    for it in L['items']:
        meta = (ROLE[it['role']], it['face'], it['gaze'], it['speech'])
        if it['kind'] == 'fill':
            loops = [it['outer']] + it['holes']
            loops3 = [[Vector((p[0] * S, 0.0, p[1] * S)) for p in lp] for lp in loops]
            tris = tessellate_polygon(loops3)
            flat = [v for lp in loops3 for v in lp]
            base = len(fv)
            fv += flat
            for t in tris:
                ff.append(tuple(base + i for i in t))
            for k, v in zip(fattr, meta):
                fattr[k] += [v] * len(flat)
        else:
            pts = [Vector((p[0] * S, 0.0, p[1] * S)) for p in it['pts']]
            base = len(sv)
            sv += pts
            for i in range(len(pts) - 1):
                se.append((base + i, base + i + 1))
            if it['closed'] and len(pts) > 2:
                se.append((base + len(pts) - 1, base))
            for k, v in zip(sattr, meta):
                sattr[k] += [v] * len(pts)
    objs = []
    for name, verts, edges, faces, attrs in (('BUNNY_facelib_fills', fv, [], ff, fattr),
                                              ('BUNNY_facelib_strokes', sv, se, [], sattr)):
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, edges, faces)
        for k, vals in attrs.items():
            _attr(me, 'ds_' + k, 'INT', vals)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        ob.hide_render = True
        ob.hide_viewport = True
        objs.append(ob)
    # speech-mouth offsets per expression (Doodle Studio source px -> metres)
    offs = [Vector((o[0] * .01 * S, 0.0, -o[1] * .01 * S)) for o in L['speech_offsets_px']]
    me = bpy.data.meshes.new('BUNNY_facelib_offsets')
    me.from_pydata(offs, [], [])
    ob = bpy.data.objects.new('BUNNY_facelib_offsets', me)
    coll.objects.link(ob)
    ob.hide_render = True
    ob.hide_viewport = True
    objs.append(ob)
    return objs, L


def _int_attr(g, name):
    n = g.node('GeometryNodeInputNamedAttribute', data_type='INT')
    n.inputs['Name'].default_value = name
    return n.outputs['Attribute']


def _cmp_int(g, a, b, op='EQUAL'):
    n = g.node('FunctionNodeCompare', data_type='INT', operation=op)
    ia = next((s for s in n.inputs if s.identifier == 'A_INT'), None) or compat.sock(n.inputs, 'A')   # 5.2: only the live pair
    ib = next((s for s in n.inputs if s.identifier == 'B_INT'), None) or compat.sock(n.inputs, 'B')
    for sock, v in ((ia, a), (ib, b)):
        if isinstance(v, int):
            sock.default_value = v
        else:
            g.link(v, sock)
    return n.outputs[0]


def _bool(g, op, a, b=None):
    n = g.node('FunctionNodeBooleanMath', operation=op)
    g.link(a, n.inputs[0])
    if b is not None:
        g.link(b, n.inputs[1])
    return n.outputs[0]


def face_group():
    name = 'DS_Face'
    ng = bpy.data.node_groups.get(name)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    _sock(ng, 'Geometry', 'NodeSocketGeometry')
    _sock(ng, 'Expression', 'NodeSocketInt', default=0, mn=0, mx=999)
    _sock(ng, 'Gaze', 'NodeSocketInt', default=0, mn=0, mx=8)
    _sock(ng, 'Speech Mouth', 'NodeSocketInt', default=0, mn=0, mx=18)
    _sock(ng, 'Blink', 'NodeSocketInt', default=0, mn=0, mx=4)
    _sock(ng, 'Fills', 'NodeSocketObject')
    _sock(ng, 'Strokes', 'NodeSocketObject')
    _sock(ng, 'Offsets', 'NodeSocketObject')
    _sock(ng, 'Head Surface', 'NodeSocketObject')
    _sock(ng, 'Camera', 'NodeSocketObject')
    _sock(ng, 'Orthographic', 'NodeSocketBool', default=False)
    _sock(ng, 'Ortho Scale', 'NodeSocketFloat', default=1.0)
    _sock(ng, 'Sensor / Focal', 'NodeSocketFloat', default=36 / 50)
    _sock(ng, 'Ink Fraction', 'NodeSocketFloat', default=10.5 / 1920)
    _sock(ng, 'Boil Amount', 'NodeSocketFloat', default=0.0)
    _sock(ng, 'Boil Fraction', 'NodeSocketFloat', default=2.5 / 1920)
    _sock(ng, 'Boil Step', 'NodeSocketInt', default=3, mn=1)
    _sock(ng, 'Lift', 'NodeSocketFloat', default=0.0015)
    _sock(ng, 'Material', 'NodeSocketMaterial')
    _sock(ng, 'Geometry', 'NodeSocketGeometry', io='OUTPUT')
    g = G(ng)
    gi = g.node('NodeGroupInput')
    go = g.node('NodeGroupOutput')
    I = gi.outputs

    def obj_geo(sock, space='RELATIVE'):
        # the face library sits in the head's rest frame, so it is read as-is (ORIGINAL);
        # RELATIVE re-applied the posed head transform, which smeared the eyes on turns and at scales other than 1
        oi = g.node('GeometryNodeObjectInfo', transform_space=space)
        g.link(sock, oi.inputs['Object'])
        return oi.outputs['Geometry']

    # which drawn face supplies the eyes: a blink stage overrides the expression
    blink_on = _cmp_int(g, I['Blink'], 0, 'GREATER_THAN')
    blink_face = g.math('ADD', I['Blink'], 32.0)
    eyes_sw = g.node('GeometryNodeSwitch', input_type='INT')
    g.link(blink_on, eyes_sw.inputs['Switch'])
    g.link(I['Expression'], eyes_sw.inputs['False'])
    g.link(blink_face, eyes_sw.inputs['True'])
    eyes_face = eyes_sw.outputs[0]

    def selection():
        role = _int_attr(g, 'ds_role')
        face = _int_attr(g, 'ds_face')
        gaze = _int_attr(g, 'ds_gaze')
        sp = _int_attr(g, 'ds_speech')
        gaze_ok = _bool(g, 'OR', _cmp_int(g, gaze, -1), _cmp_int(g, gaze, I['Gaze']))
        eyes = _bool(g, 'AND', _cmp_int(g, role, 0), _bool(g, 'AND', _cmp_int(g, face, eyes_face), gaze_ok))
        no_speech = _cmp_int(g, I['Speech Mouth'], 0)
        mouth = _bool(g, 'AND', _cmp_int(g, role, 1), _bool(g, 'AND', no_speech, _cmp_int(g, face, I['Expression'])))
        speech = _bool(g, 'AND', _cmp_int(g, role, 2), _cmp_int(g, sp, I['Speech Mouth']))
        keep = _bool(g, 'OR', eyes, _bool(g, 'OR', mouth, speech))
        return _bool(g, 'NOT', keep), _cmp_int(g, role, 2)

    def speech_offset(geom, is_speech):
        si = g.node('GeometryNodeSampleIndex', data_type='FLOAT_VECTOR', domain='POINT')
        g.link(obj_geo(I['Offsets'], 'ORIGINAL'), si.inputs['Geometry'])
        g.link(g.node('GeometryNodeInputPosition').outputs[0], si.inputs['Value'])
        g.link(I['Expression'], si.inputs['Index'])
        sp = g.node('GeometryNodeSetPosition')
        g.link(geom, sp.inputs['Geometry'])
        g.link(is_speech, sp.inputs['Selection'])
        g.link(si.outputs[0], sp.inputs['Offset'])
        return sp.outputs[0]

    # fills
    drop, is_sp = selection()
    dg = g.node('GeometryNodeDeleteGeometry', domain='POINT')
    g.link(obj_geo(I['Fills'], 'ORIGINAL'), dg.inputs['Geometry'])
    g.link(drop, dg.inputs['Selection'])
    fills = speech_offset(dg.outputs[0], is_sp)
    sub = g.node('GeometryNodeSubdivideMesh')
    sub.inputs['Level'].default_value = 3
    g.link(fills, sub.inputs['Mesh'])
    fills = sub.outputs[0]

    # strokes -> resampled centre lines -> round ink dabs at a screen-constant width
    drop2, is_sp2 = selection()
    dg2 = g.node('GeometryNodeDeleteGeometry', domain='POINT')
    g.link(obj_geo(I['Strokes'], 'ORIGINAL'), dg2.inputs['Geometry'])
    g.link(drop2, dg2.inputs['Selection'])
    strokes = speech_offset(dg2.outputs[0], is_sp2)
    m2c = g.node('GeometryNodeMeshToCurve')
    g.link(strokes, m2c.inputs['Mesh'])
    px = g.node('GeometryNodeGroup')
    px.node_tree = pixel_size_group()
    for k in ('Camera', 'Orthographic', 'Ortho Scale', 'Sensor / Focal'):
        g.link(I[k], px.inputs[k])
    ink_w = g.math('MULTIPLY', px.outputs[0], I['Ink Fraction'])
    rs = g.node('GeometryNodeResampleCurve', mode='LENGTH')
    g.link(m2c.outputs[0], rs.inputs['Curve'])
    rs.inputs['Length'].default_value = 0.0007
    circ = g.node('GeometryNodeMeshCircle', fill_type='NGON')
    circ.inputs['Vertices'].default_value = 20
    circ.inputs['Radius'].default_value = 0.5
    tr = g.node('GeometryNodeTransform')
    g.link(circ.outputs[0], tr.inputs['Geometry'])
    tr.inputs['Rotation'].default_value = (1.5707963, 0, 0)
    iop = g.node('GeometryNodeInstanceOnPoints')
    g.link(rs.outputs[0], iop.inputs['Points'])
    g.link(tr.outputs[0], iop.inputs['Instance'])
    g.link(ink_w, iop.inputs['Scale'])
    real = g.node('GeometryNodeRealizeInstances')
    g.link(iop.outputs[0], real.inputs['Geometry'])

    join = g.node('GeometryNodeJoinGeometry')
    g.link(fills, join.inputs[0])
    g.link(real.outputs[0], join.inputs[0])
    ink = join.outputs[0]

    # line boil in the drawing plane (stepped)
    st = g.node('GeometryNodeInputSceneTime')
    stepped = g.math('FLOOR', g.math('DIVIDE', st.outputs['Frame'], I['Boil Step']))
    noise = g.node('ShaderNodeTexNoise', noise_dimensions='4D')
    noise.inputs['Scale'].default_value = 18.0
    noise.inputs['Detail'].default_value = 0.0
    g.link(g.node('GeometryNodeInputPosition').outputs[0], noise.inputs['Vector'])
    g.link(g.math('MULTIPLY', stepped, 1.37), noise.inputs['W'])
    centred = g.vmath('SUBTRACT', noise.outputs['Color'], (0.5, 0.5, 0.5))
    flat = g.vmath('MULTIPLY', centred, (2.0, 0.0, 2.0))
    amp = g.math('MULTIPLY', g.math('MULTIPLY', px.outputs[0], I['Boil Fraction']), I['Boil Amount'])
    boil = g.node('GeometryNodeSetPosition')
    g.link(ink, boil.inputs['Geometry'])
    g.link(g.vmath('SCALE', flat, scale=amp), boil.inputs['Offset'])

    # wrap onto the head: eyes cast straight back onto the skull surface
    head_geo = obj_geo(I['Head Surface'])
    rc = g.node('GeometryNodeRaycast')
    g.link(head_geo, rc.inputs['Target Geometry'])
    pos = g.node('GeometryNodeInputPosition').outputs[0]
    src = g.vmath('MULTIPLY', pos, (1.0, 0.0, 1.0))
    src = g.vmath('ADD', src, (0.0, -5.0, 0.0))
    g.link(src, rc.inputs['Source Position'])
    rc.inputs['Ray Direction'].default_value = (0, 1, 0)
    rc.inputs['Ray Length'].default_value = 10.0
    # mouths go on like a sticker: laid on the tangent plane at the mouth centre and
    # pressed onto the skin along that normal, so a big mouth never smears around the
    # jaw when the head turns
    is_mouth = _cmp_int(g, _int_attr(g, 'ds_role'), 1, 'GREATER_EQUAL')
    stat = g.node('GeometryNodeAttributeStatistic', data_type='FLOAT_VECTOR', domain='POINT')
    g.link(boil.outputs[0], stat.inputs['Geometry'])
    g.link(is_mouth, stat.inputs['Selection'])
    g.link(pos, stat.inputs['Attribute'])
    C = stat.outputs['Mean']
    rcc = g.node('GeometryNodeRaycast')
    g.link(head_geo, rcc.inputs['Target Geometry'])
    g.link(g.vmath('ADD', g.vmath('MULTIPLY', C, (1.0, 0.0, 1.0)), (0.0, -5.0, 0.0)), rcc.inputs['Source Position'])
    rcc.inputs['Ray Direction'].default_value = (0, 1, 0)
    rcc.inputs['Ray Length'].default_value = 10.0
    Pc, Nc = rcc.outputs['Hit Position'], rcc.outputs['Hit Normal']
    d = g.vmath('MULTIPLY', g.vmath('SUBTRACT', pos, C), (1.0, 0.0, 1.0))
    sep = g.node('ShaderNodeSeparateXYZ')
    g.link(Nc, sep.inputs[0])
    ny = g.math('MINIMUM', sep.outputs['Y'], -0.05)
    dy = g.math('DIVIDE', g.vmath('DOT_PRODUCT', d, Nc), ny)
    lift_y = g.node('ShaderNodeCombineXYZ')
    g.link(dy, lift_y.inputs['Y'])
    on_plane = g.vmath('SUBTRACT', g.vmath('ADD', Pc, d), lift_y.outputs[0])
    rcm = g.node('GeometryNodeRaycast')
    g.link(head_geo, rcm.inputs['Target Geometry'])
    g.link(g.vmath('ADD', on_plane, g.vmath('SCALE', Nc, scale=0.5)), rcm.inputs['Source Position'])
    g.link(g.vmath('SCALE', Nc, scale=-1.0), rcm.inputs['Ray Direction'])
    rcm.inputs['Ray Length'].default_value = 1.0
    hp = g.node('GeometryNodeSwitch', input_type='VECTOR')
    g.link(is_mouth, hp.inputs['Switch'])
    g.link(rc.outputs['Hit Position'], hp.inputs['False'])
    g.link(rcm.outputs['Hit Position'], hp.inputs['True'])
    hn = g.node('GeometryNodeSwitch', input_type='VECTOR')
    g.link(is_mouth, hn.inputs['Switch'])
    g.link(rc.outputs['Hit Normal'], hn.inputs['False'])
    g.link(rcm.outputs['Hit Normal'], hn.inputs['True'])
    hit = g.node('GeometryNodeSwitch', input_type='BOOLEAN')
    g.link(is_mouth, hit.inputs['Switch'])
    g.link(rc.outputs['Is Hit'], hit.inputs['False'])
    g.link(rcm.outputs['Is Hit'], hit.inputs['True'])
    hitpos = g.vmath('ADD', hp.outputs[0], g.vmath('SCALE', hn.outputs[0], scale=I['Lift']))
    sp = g.node('GeometryNodeSetPosition')
    g.link(boil.outputs[0], sp.inputs['Geometry'])
    g.link(hitpos, sp.inputs['Position'])
    miss = g.node('GeometryNodeDeleteGeometry', domain='POINT')
    g.link(sp.outputs[0], miss.inputs['Geometry'])
    g.link(_bool(g, 'NOT', hit.outputs[0]), miss.inputs['Selection'])
    sm = g.node('GeometryNodeSetMaterial')
    g.link(miss.outputs[0], sm.inputs['Geometry'])
    g.link(I['Material'], sm.inputs['Material'])
    g.link(sm.outputs[0], go.inputs['Geometry'])
    return ng


def build_face(lib_path, S, coll, head_cage, cam, ink_mat):
    """Create library + head surface proxy + the BUNNY_face object."""
    (fills, strokes, offs), L = build_library(lib_path, S, coll)
    proxy = head_cage.copy()
    proxy.data = head_cage.data.copy()
    proxy.name = 'BUNNY_head_surface'
    for m in list(proxy.modifiers):
        proxy.modifiers.remove(m)
    sub = proxy.modifiers.new('Subdivision', 'SUBSURF')
    sub.levels = 3
    sub.render_levels = 3
    coll.objects.link(proxy)
    proxy.hide_render = True
    proxy.hide_viewport = True
    me = bpy.data.meshes.new('BUNNY_face')
    face = bpy.data.objects.new('BUNNY_face', me)
    coll.objects.link(face)
    face.data.materials.append(ink_mat)
    mod = face.modifiers.new('DS Face', 'NODES')
    mod.node_group = face_group()
    ids = {s.name: s.identifier for s in mod.node_group.interface.items_tree if getattr(s, 'in_out', None) == 'INPUT'}
    compat.gn_set(mod, ids['Fills'], fills)
    compat.gn_set(mod, ids['Strokes'], strokes)
    compat.gn_set(mod, ids['Offsets'], offs)
    compat.gn_set(mod, ids['Head Surface'], proxy)
    compat.gn_set(mod, ids['Camera'], cam)
    compat.gn_set(mod, ids['Material'], ink_mat)
    settings = settings_object()
    _drive(*compat.gn_socket(mod, ids["Orthographic"]), cam.data, 'type', expr="v == 1", id_type='CAMERA')
    _drive(*compat.gn_socket(mod, ids["Ortho Scale"]), cam.data, 'ortho_scale', id_type='CAMERA')
    fc = compat.gn_driver_add(mod, ids["Sensor / Focal"])
    d = fc.driver
    d.type = 'SCRIPTED'
    for nm, path in (('s', 'sensor_width'), ('f', 'lens')):
        v = d.variables.new()
        v.name = nm
        v.targets[0].id_type = 'CAMERA'
        v.targets[0].id = cam.data
        v.targets[0].data_path = path
    d.expression = 's / f'
    _drive(*compat.gn_socket(mod, ids["Ink Fraction"]), settings, '["ink_px"]', expr='v / 1920')
    _drive(*compat.gn_socket(mod, ids["Boil Amount"]), settings, '["boil"]')
    _drive(*compat.gn_socket(mod, ids["Boil Fraction"]), settings, '["boil_px"]', expr='v / 1920')
    _drive(*compat.gn_socket(mod, ids["Boil Step"]), settings, '["boil_step"]')
    return face, proxy, mod, ids, L
