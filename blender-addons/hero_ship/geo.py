"""Small mesh helpers shared by every part of the hero ship.

Everything is built with bmesh so the ship needs no external files.
Units are metres. Axes: +Y is the nose, +X is starboard (right), +Z is up.
"""
import math
import bmesh
import bpy
from mathutils import Matrix, Vector

UV_SCALE = 0.25  # 1 UV unit = 4 m, so tiling textures keep one texel density


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def empty(name, c, parent=None, loc=(0, 0, 0), kind="PLAIN_AXES", size=1.0):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = kind
    ob.empty_display_size = size
    c.objects.link(ob)
    if parent:
        ob.parent = parent
    ob.location = loc
    return ob


def obj_from_bm(name, bm, c, parent=None, mats=(), smooth_angle=None, uv=True, loc=None):
    from .body import flush_mats
    flush_mats(bm)
    if uv and not bm.loops.layers.uv:
        box_uv(bm)
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    if loc is not None:
        ob.location = loc
    if smooth_angle is not None:
        for p in me.polygons:
            p.use_smooth = True
        try:
            me.set_sharp_from_angle(angle=math.radians(smooth_angle))
        except AttributeError:
            pass
    return ob


def box_uv(bm, scale=UV_SCALE, name="UVMap"):
    """World-scale cube projection: every face gets the same texel density."""
    uv = bm.loops.layers.uv.get(name) or bm.loops.layers.uv.new(name)
    bm.normal_update()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = l.vert.co
            if ax == 0:
                u, v = co.y * (1 if n.x > 0 else -1), co.z
            elif ax == 1:
                u, v = co.x * (-1 if n.y > 0 else 1), co.z
            else:
                u, v = co.x, co.y * (1 if n.z > 0 else -1)
            l[uv].uv = (u * scale, v * scale)
    return uv


def transform(bm, geom_verts, mat):
    bmesh.ops.transform(bm, matrix=mat, verts=geom_verts)


_CUBE_V = [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
           (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]
_CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]


def _merge(dst, src):
    """Copies src's verts and faces into dst (fast for big dst meshes)."""
    vm = {v: dst.verts.new(v.co) for v in src.verts}
    out = [vm[v] for v in src.verts]
    for f in src.faces:
        try:
            dst.faces.new([vm[v] for v in f.verts])
        except ValueError:
            pass
    src.free()
    return out


def add_box(bm, center, size, rot=None, bevel=0.0):
    """Adds a box (size = full extents) and returns its verts."""
    m = Matrix.Translation(center)
    if rot is not None:
        m = m @ (rot.to_matrix().to_4x4() if hasattr(rot, "to_matrix") else rot)
    m = m @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    if bevel <= 0:
        vs = [bm.verts.new(m @ Vector(p)) for p in _CUBE_V]
        for f in _CUBE_F:
            bm.faces.new([vs[i] for i in f])
        return vs
    tmp = bmesh.new()
    vs = [tmp.verts.new(m @ Vector(p)) for p in _CUBE_V]
    for f in _CUBE_F:
        tmp.faces.new([vs[i] for i in f])
    bmesh.ops.bevel(tmp, geom=list(tmp.edges), offset=bevel, segments=1, affect="EDGES", profile=0.5)
    return _merge(bm, tmp)


def add_cyl(bm, p0, p1, r0, r1=None, segs=16, caps=True):
    """Cylinder/cone from point p0 to p1."""
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    q = d.to_track_quat("Z", "Y")
    a_ring, b_ring = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        ca, sa = math.cos(a), math.sin(a)
        a_ring.append(bm.verts.new(p0 + q @ Vector((r0 * ca, r0 * sa, 0))))
        b_ring.append(bm.verts.new(p1 + q @ Vector((r1 * ca, r1 * sa, 0))))
    for i in range(segs):
        j = (i + 1) % segs
        bm.faces.new((a_ring[i], a_ring[j], b_ring[j], b_ring[i]))
    if caps:
        bm.faces.new(list(reversed(a_ring)))
        bm.faces.new(b_ring)
    return a_ring + b_ring


def lathe(bm, prof, segs=32, mat=None, cap_start=False, cap_end=False):
    """Revolve [(radius, z), ...] around Z. Returns rings of verts."""
    rings = []
    for r, z in prof:
        ring = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for i in range(segs):
            j = (i + 1) % segs
            bm.faces.new((a[i], a[j], b[j], b[i]))
    if cap_start:
        bm.faces.new(list(reversed(rings[0])))
    if cap_end:
        bm.faces.new(rings[-1])
    if mat is not None:
        bmesh.ops.transform(bm, matrix=mat, verts=[v for r in rings for v in r])
    return rings


def loft(bm, sections, closed=True):
    """Bridge a list of equal-length vert loops (lists of Vectors)."""
    rings = [[bm.verts.new(p) for p in s] for s in sections]
    n = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        rng = range(n) if closed else range(n - 1)
        for i in rng:
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    return rings


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def catmull(pts, t):
    """Catmull-Rom through a list of (x, value-tuple) keys; t in key x units."""
    xs = [p[0] for p in pts]
    if t <= xs[0]:
        return pts[0][1]
    if t >= xs[-1]:
        return pts[-1][1]
    i = max(k for k in range(len(xs) - 1) if xs[k] <= t)
    p0 = pts[max(i - 1, 0)][1]
    p1 = pts[i][1]
    p2 = pts[i + 1][1]
    p3 = pts[min(i + 2, len(pts) - 1)][1]
    u = (t - xs[i]) / (xs[i + 1] - xs[i])
    out = []
    for a, b, c, d in zip(p0, p1, p2, p3):
        out.append(0.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u
                          + (-a + 3 * b - 3 * c + d) * u * u * u))
    return tuple(out)


def add_modifier_bevel(ob, width=0.02, segs=2, angle=35):
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segs
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = True
    m.use_clamp_overlap = True
    return m


def weighted_normals(ob):
    m = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
    m.keep_sharp = True
    return m
