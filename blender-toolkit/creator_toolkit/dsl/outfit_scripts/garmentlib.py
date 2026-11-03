"""Garment building blocks for 3D Bunny outfits (concept + build).

Everything sits on BUNNY_rig without touching it: garments are new objects
parented to the rig with an Armature modifier, flat brand materials and the
same DS_InkOutline modifier Bunny's own parts use (same ink width).
"""
import bpy, bmesh, math
from mathutils import Vector


# Blender 5.2 keeps Geometry Nodes modifier inputs off ID properties: m['Socket_2'] and m.keys()
# raise there. These read and write them on 4.x-5.1 and 5.2 alike.
def gn_values(m):
    """{socket identifier: value} of a nodes modifier's inputs."""
    ins = getattr(getattr(m, 'properties', None), 'inputs', None)
    if ins is None:
        return {k: m[k] for k in m.keys() if k.startswith('Socket_') and not k.endswith(('_use_attribute', '_attribute_name'))}
    out = {}
    for it in m.node_group.interface.items_tree:
        s = getattr(ins, it.identifier, None) if getattr(it, 'in_out', None) == 'INPUT' else None
        if s is not None and hasattr(s, 'value'):
            out[it.identifier] = s.value
    return out


def gn_set(m, k, v):
    ins = getattr(getattr(m, 'properties', None), 'inputs', None)
    if ins is None:
        m[k] = v
    else:
        getattr(ins, k).value = v


def gn_path(m, k):
    """Data path of one input, from the object (for driver_add)."""
    ins = getattr(getattr(m, 'properties', None), 'inputs', None)
    return f'modifiers["{m.name}"]["{k}"]' if ins is None else f'modifiers["{m.name}"].properties.inputs.{k}.value'

INK, MUSTARD, OCHRE, BUTTER = '#1F1F1D', '#E0A64B', '#B87D2E', '#F0C77A'
LINE_W = 0.0141  # Bunny's ink width in world units at camZoom 1 (12.73 px / 1920 * ortho 2.134)

# torso profile measured from BUNNY_shirt (z, half-width x, half-depth y)
CX, CY = -0.003, -0.0065
PROFILE = [(0.087, .100, .072), (0.104, .125, .104), (0.121, .132, .115), (0.138, .135, .121),
           (0.155, .135, .123), (0.189, .134, .123), (0.223, .135, .116), (0.241, .134, .110),
           (0.258, .131, .101), (0.275, .122, .088), (0.292, .093, .063), (0.305, .045, .040)]
DEFORM = ['body', 'torso', 'chest', 'DEF-upper_arm.L', 'DEF-forearm.L', 'DEF-upper_arm.R', 'DEF-forearm.R']


def lin(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1,)


def flat(name, hexcol):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = lin(hexcol)
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    m.diffuse_color = lin(hexcol)
    return m


def banded(name, base, line, positions, width=LINE_W, attr='g'):
    """Flat fill with ink-weight lines where attribute `attr` hits each position."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = attr
    mask = None
    for p in positions:
        c = nt.nodes.new('ShaderNodeMath')
        c.operation = 'COMPARE'
        nt.links.new(at.outputs['Fac'], c.inputs[0])
        c.inputs[1].default_value = p
        c.inputs[2].default_value = width / 2
        _ink_driver(c.inputs[2], 'default_value', width / LINE_W * 0.5)
        if mask is None:
            mask = c.outputs[0]
        else:
            mx = nt.nodes.new('ShaderNodeMath')
            mx.operation = 'MAXIMUM'
            nt.links.new(mask, mx.inputs[0])
            nt.links.new(c.outputs[0], mx.inputs[1])
            mask = mx.outputs[0]
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = lin(base)
    mix.inputs['B'].default_value = lin(line)
    nt.links.new(mask, mix.inputs['Factor'])
    nt.links.new(mix.outputs['Result'], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    m.diffuse_color = lin(base)
    return m


def _ink_driver(owner, prop, factor):
    """Keep a shader line exactly one ink width on screen (same driver inputs as the outline)."""
    scn = bpy.context.scene
    st = bpy.data.objects.get('BUNNY_settings')
    if not (scn.camera and st):
        return
    d = owner.driver_add(prop).driver
    d.type = 'SCRIPTED'
    for nm, idt, idv, path in (('ink', 'OBJECT', st, '["ink_px"]'), ('ortho', 'CAMERA', scn.camera.data, 'ortho_scale')):
        v = d.variables.new()
        v.name = nm
        v.targets[0].id_type = idt
        v.targets[0].id = idv
        v.targets[0].data_path = path
    d.expression = f'ink / 1920 * ortho * {factor:.4f}'


def _copy_drivers(src_ob, src_md, dst_ob, dst_md):
    ad = src_ob.animation_data
    if not ad:
        return
    key = f'modifiers["{src_md.name}"]'
    for fc in ad.drivers:
        if not fc.data_path.startswith(key):
            continue
        path = fc.data_path.replace(key, f'modifiers["{dst_md.name}"]')
        try:
            nf = dst_ob.driver_add(path, fc.array_index)
        except TypeError:
            nf = dst_ob.driver_add(path)
        nd, od = nf.driver, fc.driver
        nd.type = od.type
        nd.expression = od.expression
        for ov in od.variables:
            v = nd.variables.new()
            v.name, v.type = ov.name, ov.type
            for i, t in enumerate(ov.targets):
                v.targets[i].id_type = t.id_type
                v.targets[i].id = t.id
                v.targets[i].data_path = t.data_path


def stroke_material(name, base, line, zlines=(), segs=(), side_lines=(), front_only=True):
    """Fill colour plus ink-weight lines that ride on the garment (shader, so they follow cloth):
    zlines: rings at rest height z; segs: ((x0,z0),(x1,z1)) segments on the front, in rest x/z;
    side_lines: ('gs', max_g) a stripe along a tube's chosen side up to length max_g."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')

    def attr(n):
        a = nt.nodes.new('ShaderNodeAttribute')
        a.attribute_name = n
        return a.outputs['Fac']

    def math_(op, a, b=None, c=None):
        nd = nt.nodes.new('ShaderNodeMath')
        nd.operation = op
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                nd.inputs[i].default_value = v
            else:
                nt.links.new(v, nd.inputs[i])
        return nd

    def halfw():
        # a value node driven to half an ink width
        v = nt.nodes.new('ShaderNodeValue')
        v.outputs[0].default_value = LINE_W / 2
        v.label = 'ink_half_width'
        _ink_driver(v.outputs[0], 'default_value', 0.5)
        return v.outputs[0]
    masks = []
    gz = attr('g') if (zlines or segs) else None
    for z in zlines:
        masks.append(math_('COMPARE', gz, z, halfw()).outputs[0])
    if segs:
        gx = attr('gx')
        front = math_('LESS_THAN', attr('gy'), CY).outputs[0] if front_only else None
        comb = nt.nodes.new('ShaderNodeCombineXYZ')
        nt.links.new(gx, comb.inputs[0])
        nt.links.new(gz, comb.inputs[1])
        for (x0, z0), (x1, z1) in segs:
            # distance from (gx, gz) to the segment
            vm = nt.nodes.new('ShaderNodeVectorMath')
            vm.operation = 'SUBTRACT'
            nt.links.new(comb.outputs[0], vm.inputs[0])
            vm.inputs[1].default_value = (x0, z0, 0)
            ab = Vector((x1 - x0, z1 - z0, 0))
            t = nt.nodes.new('ShaderNodeVectorMath')
            t.operation = 'DOT_PRODUCT'
            nt.links.new(vm.outputs[0], t.inputs[0])
            t.inputs[1].default_value = ab / max(ab.length_squared, 1e-9)
            tc = math_('MINIMUM', math_('MAXIMUM', t.outputs['Value'], 0.0).outputs[0], 1.0).outputs[0]
            sc_ = nt.nodes.new('ShaderNodeVectorMath')
            sc_.operation = 'SCALE'
            sc_.inputs[0].default_value = ab
            nt.links.new(tc, sc_.inputs['Scale'])
            d = nt.nodes.new('ShaderNodeVectorMath')
            d.operation = 'DISTANCE'
            nt.links.new(vm.outputs[0], d.inputs[0])
            nt.links.new(sc_.outputs[0], d.inputs[1])
            mk = math_('LESS_THAN', d.outputs['Value'], halfw()).outputs[0]
            if front is not None:
                mk = math_('MULTIPLY', mk, front).outputs[0]
            masks.append(mk)
    for attr_name, gmax in side_lines:
        a = math_('LESS_THAN', attr(attr_name), halfw()).outputs[0]
        b = math_('LESS_THAN', attr('g'), gmax).outputs[0]
        masks.append(math_('MULTIPLY', a, b).outputs[0])
    mask = None
    for mk in masks:
        mask = mk if mask is None else math_('MAXIMUM', mask, mk).outputs[0]
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['A'].default_value = lin(base)
    mix.inputs['B'].default_value = lin(line)
    if mask is not None:
        nt.links.new(mask, mix.inputs['Factor'])
    else:
        mix.inputs['Factor'].default_value = 0.0
    nt.links.new(mix.outputs['Result'], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    m.diffuse_color = lin(base)
    return m


def profile_at(z):
    P = PROFILE
    if z <= P[0][0]:
        return P[0][1], P[0][2]
    for a, b in zip(P, P[1:]):
        if z <= b[0]:
            t = (z - a[0]) / (b[0] - a[0])
            return a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t
    return P[-1][1], P[-1][2]


def superellipse(rx, ry, n=2.5, M=48, a0=0.0, a1=2 * math.pi, closed=True):
    pts = []
    cnt = M if closed else M + 1
    for i in range(cnt):
        a = a0 + (a1 - a0) * i / M
        c, s = math.cos(a), math.sin(a)
        x = rx * math.copysign(abs(c) ** (2 / n), c)
        y = ry * math.copysign(abs(s) ** (2 / n), s)
        pts.append((x, y))
    return pts


def tail_hole(c):
    """Opening for Bunny's tail (v2 rig: DEF-tail at y 0.10-0.14, z 0.123)."""
    return c.y > 0.06 and abs(c.x) < 0.036 and abs(c.z - 0.123) < 0.036


def mesh_from_grid(name, grid, closed_u=True, cap_start=False, cap_end=False, attrs=None, coll=None, skip=None):
    """grid: list of rings (list of Vector). attrs: {name: [[val per vert]]}."""
    bm = bmesh.new()
    rows = [[bm.verts.new(p) for p in ring] for ring in grid]
    M = len(grid[0])
    for r0, r1 in zip(rows, rows[1:]):
        for i in range(M if closed_u else M - 1):
            j = (i + 1) % M
            q = (r0[i], r0[j], r1[j], r1[i])
            if skip and skip(sum((v.co for v in q), Vector()) / 4):
                continue
            bm.faces.new(q)
    if cap_start:
        bm.faces.new(list(reversed(rows[0])))
    if cap_end:
        bm.faces.new(rows[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if attrs:
        for an, vals in attrs.items():
            flat_vals = [v for row in vals for v in row]
            a = me.attributes.new(an, 'FLOAT', 'POINT')
            a.data.foreach_set('value', flat_vals)
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def torso_shell(name, z0, z1, off, rows=24, n=2.5, shape=None, a0=0.0, a1=2 * math.pi, closed=True, M=48, coll=None, cap_end=False, skip=tail_hole):
    """Loft around Bunny's torso. shape(z, angle, r) -> extra radial offset."""
    grid, g, gx, gy = [], [], [], []
    for k in range(rows + 1):
        z = z0 + (z1 - z0) * k / rows
        rx, ry = profile_at(z)
        ring = []
        for i, (x, y) in enumerate(superellipse(rx + off, ry + off, n, M, a0, a1, closed)):
            ang = a0 + (a1 - a0) * i / M
            d = shape(z, ang) if shape else 0.0
            L = math.hypot(x, y) or 1
            ring.append(Vector((CX + x + x / L * d, CY + y + y / L * d, z)))
        grid.append(ring)
        g.append([z] * len(ring))
        gx.append([p.x for p in ring])
        gy.append([p.y for p in ring])
    return mesh_from_grid(name, grid, closed_u=closed, attrs={'g': g, 'gx': gx, 'gy': gy}, coll=coll, cap_end=cap_end, skip=skip)


def frames(path):
    """Parallel-transport frames along a polyline."""
    T = []
    for i in range(len(path)):
        a = path[max(i - 1, 0)]
        b = path[min(i + 1, len(path) - 1)]
        T.append((b - a).normalized())
    up = Vector((0, 0, 1)) if abs(T[0].z) < 0.9 else Vector((1, 0, 0))
    N = [T[0].cross(up).normalized()]
    for i in range(1, len(path)):
        n = N[-1] - T[i] * N[-1].dot(T[i])
        N.append(n.normalized())
    B = [t.cross(n) for t, n in zip(T, N)]
    return T, N, B


def smooth_path(ctrl, steps=8):
    """Catmull-Rom through control points."""
    P = [Vector(c) for c in ctrl]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return out


def tube(name, path, radius, M=20, flat=1.0, caps=True, coll=None, twist=0.0, stripe_dir=None):
    """radius: float or fn(t). flat: squash of the cross-section (scarves/straps)."""
    T, N, B = frames(path)
    L = [0.0]
    for a, b in zip(path, path[1:]):
        L.append(L[-1] + (b - a).length)
    grid, g, gs = [], [], []
    k0 = 0
    if stripe_dir is not None:
        sd = Vector(stripe_dir).normalized()
        k0 = max(range(M), key=lambda k: (N[0] * math.cos(2 * math.pi * k / M) + B[0] * math.sin(2 * math.pi * k / M)).dot(sd))
    for i, p in enumerate(path):
        t = L[i] / L[-1]
        r = radius(t) if callable(radius) else radius
        ring = []
        for k in range(M):
            a = 2 * math.pi * k / M + twist * t
            ring.append(p + N[i] * (math.cos(a) * r) + B[i] * (math.sin(a) * r * flat))
        grid.append(ring)
        g.append([L[i]] * M)
        gs.append([2 * math.pi * r * min((k - k0) % M, (k0 - k) % M) / M for k in range(M)])
    return mesh_from_grid(name, grid, cap_start=caps, cap_end=caps, attrs={'g': g, 'gs': gs}, coll=coll)


def ellipsoid(name, centre, size, coll=None, seg=24, ring=12):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=ring, radius=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0] + centre[0], v.co.y * size[1] + centre[1], v.co.z * size[2] + centre[2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    a = me.attributes.new('g', 'FLOAT', 'POINT')
    a.data.foreach_set('value', [v.co.z for v in me.vertices])
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def _seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (p - (a + ab * t)).length


def skin_to_rig(ob, rig, bones=DEFORM, falloff=0.03):
    """Soft weights from distance to bone segments (rest pose)."""
    segs = {b: (rig.data.bones[b].head_local, rig.data.bones[b].tail_local) for b in bones}
    groups = {b: ob.vertex_groups.new(name=b) for b in bones}
    for v in ob.data.vertices:
        d = {b: _seg_dist(v.co, *segs[b]) for b in bones}
        dmin = min(d.values())
        w = {b: math.exp(-((d[b] - dmin) / falloff) ** 2) for b in bones}
        s = sum(w.values())
        for b in bones:
            if w[b] / s > 0.02:
                groups[b].add([v.index], w[b] / s, 'REPLACE')
    md = ob.modifiers.new('Armature', 'ARMATURE')
    md.object = rig
    ob.parent = rig


def finish(ob, mat, rig, outline_src, subsurf=2, bones=DEFORM, outline=True):
    ob.data.materials.append(mat)
    for p in ob.data.polygons:
        p.use_smooth = True
    skin_to_rig(ob, rig, bones)
    sd = ob.modifiers.new('Subdivision', 'SUBSURF')
    sd.levels = sd.render_levels = subsurf
    if not outline:  # tiny solid ink details (buttons): an outline would ring them
        return ob
    src = next(m for m in outline_src.modifiers if m.type == 'NODES')
    md = ob.modifiers.new('Ink', 'NODES')
    md.node_group = src.node_group
    for k in src.keys():
        if k.startswith('Socket_') and not k.endswith(('_use_attribute', '_attribute_name')):
            md[k] = src[k]
    md['Socket_11'] = float(sum(map(ord, ob.name)) % 97)  # own boil seed
    _copy_drivers(outline_src, src, ob, md)
    return ob
