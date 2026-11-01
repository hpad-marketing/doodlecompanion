"""Side-cast accessories for Bunny, Koala and Frog (one set, fitted per head at dress time).

Rules (user, 2026-10-30): brand black only, details as a few ochre strokes at the line weight,
minimal. Head pieces ride the 'head' bone, neck pieces the 'chest' bone. Every piece is placed
from the character's own face (eye centres measured off BUNNY_face) and head surface, so the
same accessory fits all three heads.
"""
import bpy, bmesh, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import garmentlib as G
from garmentlib import INK, OCHRE

STROKE_R = G.LINE_W / 2


def _eval_world(ob, drop=('NODES',)):
    off = [m for m in ob.modifiers if m.type in drop and m.show_viewport]
    for m in off:
        m.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = ob.evaluated_get(dg).to_mesh()
    vs = [ob.matrix_world @ v.co for v in me.vertices]
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(ob.matrix_world)
    ob.evaluated_get(dg).to_mesh_clear()
    for m in off:
        m.show_viewport = True
    return vs, BVHTree.FromBMesh(bm)


def _eye_boxes():
    """Per expression and side, the box of the eye fills (whites + pupils, no brows) in world space,
    read straight from the face library (the face modifier only shows one drawing at a time)."""
    face = bpy.data.objects['BUNNY_face']
    me = bpy.data.objects['BUNNY_facelib_fills'].data
    fa, ro = me.attributes['ds_face'].data, me.attributes['ds_role'].data
    M = face.matrix_world
    box = {}
    for i, v in enumerate(me.vertices):
        if ro[i].value != 0:
            continue
        p = M @ v.co
        if abs(p.x) < 0.02:
            continue
        k = (fa[i].value, 1 if p.x > 0 else -1)
        b = box.get(k)
        box[k] = [p.x, p.x, p.z, p.z, p.y] if b is None else [min(b[0], p.x), max(b[1], p.x), min(b[2], p.z), max(b[3], p.z), b[4]]
    return box


def anchors():
    """Eye centres/sizes, head surface and top for whichever character is in the file.
    Rims are centred on the neutral eyes with a lens margin; the biggest expressions (shock, tears,
    dizzy spirals) can reach past the rim, like eyes behind real lenses."""
    box = _eye_boxes()
    eyes = []
    for side in (-1, 1):
        x0, x1, z0, z1, y = box[(0, side)]
        c = Vector(((x0 + x1) / 2, y, (z0 + z1) / 2))
        # rims: the neutral eye plus a lens margin (the look picked on the review page)
        eyes.append((c, (x1 - x0) / 2 * 1.45, (z1 - z0) / 2 * 1.6))
    hv, head = _eval_world(bpy.data.objects['BUNNY_head'])
    cz = sum(v.z for v in hv) / len(hv)
    crown = max((v for v in hv if abs(v.x) < 0.015 and v.y < 0.05), key=lambda v: v.z)
    # chin: the lowest front point of the head near the centre line (neck pieces sit just below it)
    chin = min((v for v in hv if abs(v.x) < 0.03 and v.y < 0), key=lambda v: v.z)
    return dict(eyes=eyes, head=head, crown=crown, centre=Vector((0, 0, cz)), chin=chin)


def clear_of(tree, p, gap):
    """Push p out of the surface until it sits at least gap in front of it (iterated, so a point
    in a crease, such as between Frog's eye bumps, ends up clear of both sides)."""
    for _ in range(8):
        hit = tree.find_nearest(p)
        if hit[0] is None:
            return p
        out = (p - hit[0]).dot(hit[1])
        if out >= gap * 0.98:
            return p
        p = hit[0] + hit[1] * gap
    return p


def onto_head(head, p, d=Vector((0, 1, 0)), lift=0.012):
    """Shoot from in front along d and land on the head surface, lifted off it."""
    hit = head.ray_cast(p - d * 0.6, d, 2.0)
    if hit[0] is None:
        return p
    return hit[0] + hit[1] * lift


def _finish(ob, mat, rig, src, bone, outline=True, subsurf=1):
    if mat is not None:
        ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    if bone is None:
        pass
    else:
        g = ob.vertex_groups.new(name=bone)
        g.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
    md = ob.modifiers.new('Armature', 'ARMATURE')
    md.object = rig
    ob.parent = rig
    if subsurf:
        sd = ob.modifiers.new('Subdivision', 'SUBSURF')
        sd.levels = sd.render_levels = subsurf
    if outline:
        srcm = next(m for m in src.modifiers if m.type == 'NODES')
        m = ob.modifiers.new('Ink', 'NODES')
        m.node_group = srcm.node_group
        for k, v in G.gn_values(srcm).items():
            G.gn_set(m, k, v)
        G._copy_drivers(src, srcm, ob, m)
    stroke_last(ob)
    return ob


def stroke_last(ob):
    i = ob.modifiers.find('Stroke')
    if i >= 0 and i != len(ob.modifiers) - 1:
        ob.modifiers.move(i, len(ob.modifiers) - 1)


def _stroke_group():
    """Geometry nodes: polyline -> round tube whose radius is a driven input (one ink width on screen)."""
    ng = bpy.data.node_groups.get('DS_StrokeTube')
    if ng:
        return ng
    ng = bpy.data.node_groups.new('DS_StrokeTube', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    r = ng.interface.new_socket('Radius', in_out='INPUT', socket_type='NodeSocketFloat')
    r.default_value = STROKE_R
    ng.interface.new_socket('Material', in_out='INPUT', socket_type='NodeSocketMaterial')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    m2c = N.new('GeometryNodeMeshToCurve')
    circ = N.new('GeometryNodeCurvePrimitiveCircle')
    circ.inputs['Resolution'].default_value = 8
    c2m = N.new('GeometryNodeCurveToMesh')
    c2m.inputs['Fill Caps'].default_value = True
    mat = N.new('GeometryNodeSetMaterial')
    smooth = N.new('GeometryNodeSetShadeSmooth')
    L.new(gi.outputs['Geometry'], m2c.inputs['Mesh'])
    L.new(gi.outputs['Radius'], circ.inputs['Radius'])
    L.new(m2c.outputs['Curve'], c2m.inputs['Curve'])
    L.new(circ.outputs['Curve'], c2m.inputs['Profile Curve'])
    L.new(c2m.outputs['Mesh'], smooth.inputs['Geometry'])
    L.new(smooth.outputs['Geometry'], mat.inputs['Geometry'])
    L.new(gi.outputs['Material'], mat.inputs['Material'])
    L.new(mat.outputs['Geometry'], go.inputs['Geometry'])
    return ng


def stroke(name, pts, coll, mat, closed=True):
    """An ink-width stroke along pts: a polyline turned into a tube at render time, its radius
    driven by the same ink_px / camera driver as Bunny's outline (see drive_strokes)."""
    n = len(pts)
    edges = [(i, i + 1) for i in range(n - 1)] + ([(n - 1, 0)] if closed else [])
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in pts], edges, [])
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.data.materials.append(mat)
    m = ob.modifiers.new('Stroke', 'NODES')
    m.node_group = _stroke_group()
    ids = {s.name: s.identifier for s in m.node_group.interface.items_tree if s.in_out == 'INPUT'}
    G.gn_set(m, ids['Material'], mat)
    ob['ds_stroke_socket'] = ids['Radius']
    return ob


def drive_strokes(ob, cam, settings):
    sock = ob.get('ds_stroke_socket')
    m = ob.modifiers.get('Stroke')
    if not sock or not m:
        return
    d = ob.driver_add(G.gn_path(m, sock)).driver
    d.type = 'SCRIPTED'
    for name, idt, idv, path in (('ink', 'OBJECT', settings, '["ink_px"]'), ('ortho', 'CAMERA', cam.data, 'ortho_scale')):
        v = d.variables.new()
        v.name = name
        v.targets[0].id_type = idt
        v.targets[0].id = idv
        v.targets[0].data_path = path
    d.expression = 'ink / 1920 * ortho * 0.5'


def ring(name, pts, coll, mat=None):
    return stroke(name, pts, coll, mat or G.flat('DS_ink', INK), closed=True)


def glasses(A, rig, src, coll, square=False):
    obs = []
    ink = G.flat('DS_ink', INK)
    inner = []
    for i, (c, rx, rz) in enumerate(A['eyes']):
        rx, rz = rx + 0.01, rz + 0.01
        pts = []
        for k in range(48):
            a = 2 * math.pi * k / 48
            if square:  # rounded rectangle (superellipse)
                x = rx * math.copysign(abs(math.cos(a)) ** 0.35, math.cos(a))
                z = rz * math.copysign(abs(math.sin(a)) ** 0.35, math.sin(a))
            else:
                x, z = rx * math.cos(a), rz * math.sin(a)
            pts.append(clear_of(A['head'], onto_head(A['head'], Vector((c.x + x, 0, c.z + z)), lift=0.016), 0.016))
        ob = ring(f'ACC_glasses_rim{i}', pts, coll, ink)
        obs.append(_finish(ob, None, rig, src, 'head', outline=False, subsurf=0))
        inner.append(min(pts, key=lambda p: abs(p.x) + 5 * abs(p.z - c.z)))  # inner side, at eye height
    # bridge between the rims, arched a little
    a, b = inner
    mid = (a + b) / 2 + Vector((0, -0.004, 0.008))  # a small arch over the nose line
    sp = G.smooth_path([a, mid, b], 6)
    dense = [sp[i].lerp(sp[i + 1], t / 4) for i in range(len(sp) - 1) for t in range(4)] + [sp[-1]]
    path = [clear_of(A['head'], p, 0.02) for p in dense]
    br = stroke('ACC_glasses_bridge', path, coll, ink, closed=False)
    obs.append(_finish(br, None, rig, src, 'head', outline=False, subsurf=0))
    return obs


def hair_tuft(A, rig, src, coll):
    """Three small flicks from the crown, leaning forward: a doodle cowlick."""
    base = A['crown'] + Vector((0, -0.03, -0.012))
    obs = []
    for i, (dx, lean, h) in enumerate(((-0.025, -0.02, 0.07), (0.0, -0.035, 0.095), (0.026, -0.02, 0.065))):
        p0 = base + Vector((dx, 0, 0))
        path = G.smooth_path([p0, p0 + Vector((dx * 0.6, lean * 0.5, h * 0.6)), p0 + Vector((dx * 1.4, lean, h))], 6)
        ob = G.tube(f'ACC_tuft{i}', path, lambda t: 0.016 * (1 - t) + 0.002, M=12, flat=0.6, coll=coll)
        obs.append(_finish(ob, G.flat('DS_ink', INK), rig, src, 'head'))
    return obs


def hair_bun(A, rig, src, coll):
    c = A['crown'] + Vector((0, 0.05, 0.02))
    ob = G.ellipsoid('ACC_bun', c, (0.06, 0.055, 0.05), coll=coll, seg=20, ring=12)
    obs = [_finish(ob, G.flat('DS_ink', INK), rig, src, 'head')]
    # one ochre stroke for the band where the bun meets the head
    band = [Vector((c.x + 0.055 * math.cos(a), c.y + 0.05 * math.sin(a), c.z - 0.03)) for a in [2 * math.pi * k / 24 for k in range(24)]]
    obs.append(_finish(ring('ACC_bun_band', band, coll, G.flat('OUT_ochre_stroke', OCHRE)), None, rig, src, 'head', outline=False, subsurf=0))
    return obs


def drop_until_clear(head, zx, off, gap=0.008):
    """How far a neck piece must move down so every probe (z, x) sits gap clear of the chin."""
    dz = 0.0
    while dz > -0.08:
        if all(head.find_nearest(_front0(z + dz, x, off))[0] is None or
               (lambda h, p: (p - h[0]).dot(h[1]))(head.find_nearest(_front0(z + dz, x, off)), _front0(z + dz, x, off)) >= gap
               for z, x in zx):
            return dz
        dz -= 0.003
    return dz


TOP = None  # BVH of the worn top (hoodie shirt or outfit body) in rest pose, set by apply_accessory


def _front0(z, x=0.0, off=0.016):
    if TOP is not None:
        rx, ry = G.profile_at(z)
        o = Vector((G.CX + x, G.CY - ry - 0.3, z))
        hit = TOP.ray_cast(o, Vector((0, 1, 0)), 0.6)
        if hit[0] is not None:
            return clear_of(TOP, Vector((hit[0].x, hit[0].y - off, hit[0].z)), off * 0.9)
    rx, ry = G.profile_at(z)
    return Vector((G.CX + x, G.CY - ry - off, z))


def _tie_outline(z):
    """Half-width of the tie blade at height z (knot at the top, point at the bottom)."""
    if z >= 0.245:
        return 0.018 - (0.268 - z) / 0.023 * 0.006
    if z >= 0.15:
        return 0.012 + (0.245 - z) / 0.095 * 0.014
    return 0.026 * max(0.0, (z - 0.125) / 0.025)


def necktie(A, rig, src, coll):
    """Black tie on the black top. The shape reads through one ochre outline stroke.
    The tie itself is a small cloth panel: pinned at the knot, the blade lags and swings on turns
    and hops, then a goal spring settles it back flat against the chest. The outline rides the
    cloth through Surface Deform, so stroke and panel never part."""
    o = G.flat('OUT_ochre_stroke', OCHRE)
    ink = G.flat('DS_ink', INK)
    dz = drop_until_clear(A['head'], [(0.268, -0.018), (0.268, 0.018), (0.262, 0.0)], 0.018)
    _front = lambda z, x=0.0, off=0.016: _front0(z + dz, x, off)
    rows, cols = 16, 5
    zs = [0.268 - (0.268 - 0.127) * r / (rows - 1) for r in range(rows)]
    verts, faces = [], []
    for z in zs:
        w = max(_tie_outline(z), 0.002)
        for c in range(cols):
            x = -w + 2 * w * c / (cols - 1)
            verts.append(_front(z, x, off=0.014))
    for r in range(rows - 1):
        for c in range(cols - 1):
            a = r * cols + c
            faces.append((a, a + 1, a + cols + 1, a + cols))
    me = bpy.data.meshes.new('ACC_tie')
    me.from_pydata([tuple(v) for v in verts], [], faces)
    panel = bpy.data.objects.new('ACC_tie', me)
    coll.objects.link(panel)
    _finish(panel, ink, rig, src, 'chest', outline=False, subsurf=0)
    pin = panel.vertex_groups.new(name='pin')
    for i, v in enumerate(verts):
        t = (0.268 - (v.z - dz)) / (0.268 - 0.127)  # 0 at the knot, 1 at the tip
        pin.add([i], 1.0 if t < 0.18 else max(0.15, 1.0 - (t - 0.18) * 1.1), 'REPLACE')
    cl = panel.modifiers.new('Cloth', 'CLOTH')
    s = cl.settings
    s.quality = 8
    s.mass = 0.05
    s.tension_stiffness = s.compression_stiffness = 60
    s.shear_stiffness = 40
    s.bending_stiffness = 4
    s.air_damping = 2.0
    s.vertex_group_mass = 'pin'
    s.pin_stiffness = 3
    s.effector_weights.gravity = 0.35
    cl.collision_settings.use_collision = False
    cl.collision_settings.use_self_collision = False
    # keep the cloth right after the armature, before any subdivision
    knot = [_front(0.268, -0.018, 0.026), _front(0.268, 0.018, 0.026), _front(0.245, 0.012, 0.022), _front(0.245, -0.012, 0.022)]
    obs = [panel, _finish(ring('ACC_tie_knot', knot, coll, o), None, rig, src, 'chest', outline=False, subsurf=0)]
    # outline traced just in front of the panel border, then bound to the panel
    edge = [_front(z, -max(_tie_outline(z), 0.0015), 0.017) for z in zs[1:]] + \
           [_front(z, max(_tie_outline(z), 0.0015), 0.017) for z in reversed(zs[1:])]
    line = ring('ACC_tie_blade', edge, coll, o)
    line.parent = rig
    sd = line.modifiers.new('Ride the tie', 'SURFACE_DEFORM')
    sd.target = panel
    sd.falloff = 4
    stroke_last(line)
    obs.append(line)
    bpy.context.view_layer.update()
    with bpy.context.temp_override(object=line, active_object=line):
        bpy.ops.object.surfacedeform_bind(modifier=sd.name)
    return obs


def bowtie(A, rig, src, coll):
    o = G.flat('OUT_ochre_stroke', OCHRE)
    z = 0.258 + drop_until_clear(A['head'], [(0.284, -0.05), (0.284, 0.05), (0.271, 0.0), (0.284, -0.03), (0.284, 0.03)], 0.016)
    _front = _front0
    left = [_front(z + 0.012, -0.012, 0.022), _front(z + 0.026, -0.05, 0.022), _front(z - 0.026, -0.05, 0.022), _front(z - 0.012, -0.012, 0.022)]
    right = [Vector((-p.x + 2 * G.CX, p.y, p.z)) for p in left]
    knot = [_front(z + 0.013, -0.012, 0.024), _front(z + 0.013, 0.012, 0.024), _front(z - 0.013, 0.012, 0.024), _front(z - 0.013, -0.012, 0.024)]
    return [_finish(ring(f'ACC_bow{n}', pts, coll, o), None, rig, src, 'chest', outline=False, subsurf=0)
            for n, pts in (('L', left), ('R', right), ('knot', knot))]


ACCESSORIES = {
    'glasses_round': ('Round glasses', lambda A, r, s, c: glasses(A, r, s, c)),
    'glasses_square': ('Square glasses', lambda A, r, s, c: glasses(A, r, s, c, square=True)),
    'hair_tuft': ('Hair tuft', hair_tuft),
    'hair_bun': ('Hair bun', hair_bun),
    'necktie': ('Necktie', necktie),
    'bowtie': ('Bow tie', bowtie),
}
