"""Organic shapes for the later rooms: leafy plants and a scrap mound.

Plants are real leaves (thin curved blades on a stem), never merged balls of
foliage, in one or two greens. A plant is built from a seed, so the same seed
always grows the same plant.
"""
import math
import random
import bmesh
import bpy
from mathutils import Vector, Matrix

from .. import kit as K
from .. import mats as M


def _leaf_mesh(name, length, width, curl, segs=7):
    """One blade: a lens outline along +Y, bent down (curl) towards its tip, 1.5 mm thick."""
    bm = bmesh.new()
    rows = []
    t_half = 0.00075
    for i in range(segs + 1):
        t = i / segs
        y = t * length
        half = width / 2 * math.sin(math.pi * min(1.0, t * 1.08)) ** 0.8
        z = -curl * t * t
        row = []
        for x in (-half, 0.0, half):
            dip = abs(x) / max(width / 2, 1e-6) * 0.18 * width  # midrib fold
            row.append((x, y, z + dip))
        rows.append(row)
    top, bot = [], []
    for row in rows:
        top.append([bm.verts.new((x, y, z + t_half)) for x, y, z in row])
        bot.append([bm.verts.new((x, y, z - t_half)) for x, y, z in row])
    for i in range(segs):
        for j in range(2):
            bm.faces.new((top[i][j], top[i][j + 1], top[i + 1][j + 1], top[i + 1][j]))
            bm.faces.new((bot[i][j], bot[i + 1][j], bot[i + 1][j + 1], bot[i][j + 1]))
    for i in range(segs):  # edges
        bm.faces.new((top[i][0], top[i + 1][0], bot[i + 1][0], bot[i][0]))
        bm.faces.new((top[i][2], bot[i][2], bot[i + 1][2], top[i + 1][2]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def greens():
    return (M.plastic("SB Leaf Green", (0.09, 0.22, 0.06, 1), 0.55),
            M.plastic("SB Leaf Olive", (0.16, 0.24, 0.06, 1), 0.6))


def plant(room, base, height, rng, mat, leaves=7, leaf_len=0.09, name="Plant"):
    """Stem plus leaves spiralling up it. Returns the joined object, which reaches
    at most leaf_len sideways from the stem and height + 0.02 above the base."""
    base = Vector(base)
    parts = [K.cyl(f"{name} Stem", 0.0045, height, base + Vector((0, 0, height / 2)), mat, room.dress, verts=8, bevel=0)]
    phi = rng.uniform(0, math.tau)
    for k in range(leaves):
        t = 0.25 + 0.75 * k / max(1, leaves - 1)
        L = leaf_len * rng.uniform(0.75, 1.0) * (1.15 - 0.4 * t)
        me = _leaf_mesh(f"{name} Leaf", L, L * rng.uniform(0.38, 0.5), L * rng.uniform(0.15, 0.35))
        ob = K._obj(f"{name} Leaf", me, room.dress, mat)
        phi += math.radians(137.5)
        pitch = math.radians(rng.uniform(25, 55))
        R = Matrix.Rotation(phi, 4, "Z") @ Matrix.Rotation(pitch, 4, "X")
        ob.matrix_world = Matrix.Translation(base + Vector((0, 0, height * t))) @ R
        parts.append(ob)
    bpy.context.view_layer.update()
    return K.join(parts, name)


def mound(room, centre, rx, ry, h, mat, name="Scrap Mound"):
    """Half ellipsoid sitting flat on the deck (closed underside)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1.0)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0.0), plane_no=(0, 0, 1),
                           clear_inner=True)
    edges = [e for e in bm.edges if e.is_boundary]
    bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    for v in bm.verts:
        v.co = Vector((v.co.x * rx, v.co.y * ry, max(0.0, v.co.z) * h))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = p.normal.z > -0.5
    ob = K._obj(name, me, room.dress, mat)
    ob.location = Vector(centre)
    return ob


def mound_z(dx, dy, rx, ry, h):
    q = 1.0 - (dx / rx) ** 2 - (dy / ry) ** 2
    return h * math.sqrt(q) if q > 0 else 0.0
