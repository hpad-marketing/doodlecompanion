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


def add_box(bm, center, size, rot=None, bevel=0.0):
    """Adds a box (size = full extents) and returns its verts."""
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r["verts"]
    m = Matrix.Translation(center)
    if rot is not None:
        m = m @ (rot.to_matrix().to_4x4() if hasattr(rot, "to_matrix") else rot)
    m = m @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
    bmesh.ops.transform(bm, matrix=m, verts=vs)
    if bevel > 0:
        edges = list({e for v in vs for e in v.link_edges})
        bmesh.ops.bevel(bm, geom=edges, offset=bevel, segments=1, affect="EDGES", profile=0.5)
    return vs


def add_cyl(bm, p0, p1, r0, r1=None, segs=16, caps=True):
    """Cylinder/cone from point p0 to p1."""
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    res = bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=segs,
                                radius1=r0, radius2=r1, depth=L)
    vs = res["verts"]
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    m = Matrix.Translation((p0 + p1) / 2) @ rot
    bmesh.ops.transform(bm, matrix=m, verts=vs)
    return vs


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
