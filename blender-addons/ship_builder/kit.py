"""Snap-together ship kit: real geometry for panels, seams, bolts, pipes, cables,
vents, light strips, screens and props. Every piece is built on a 1 m grid in a
room space where the back wall is at y = depth, the floor at z = 0 and the open
fourth wall (camera side) at y = 0.
"""
import math
import random
import bpy
import bmesh
from mathutils import Vector, Matrix

from . import mats as M

DETAIL = {"level": 2}
RNG = random.Random(7)


# ---------------------------------------------------------------- basics
class piece:
    """with K.piece(room, "Couch", shift=0.05, yaw=4): ...
    Tags everything built inside as one movable piece, so the wear pass can nudge
    and turn it as a unit (a couch never loses its legs)."""
    _n = [0]

    def __init__(self, room, name, shift=0.04, yaw=3.0, tip=False):
        self.room, self.name, self.shift, self.yaw, self.tip = room, name, shift, yaw, tip

    def __enter__(self):
        self.before = set(bpy.data.objects)
        return self

    def __exit__(self, *exc):
        piece._n[0] += 1
        pid = f"{self.name}#{piece._n[0]}"
        for ob in set(bpy.data.objects) - self.before:
            ob["sb_piece"] = pid
            ob["sb_shift"] = self.shift
            ob["sb_yaw"] = self.yaw
        return False


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


class Room:
    """Holds the collections a room builds into."""

    def __init__(self, name, width, depth, height):
        self.name, self.W, self.D, self.H = name, width, depth, height
        self.root = coll("SB " + name)
        self.root["sb_room"] = name
        self.shell = coll(f"{name} Shell", self.root)
        self.dress = coll(f"{name} Dressing", self.root)
        self.props = coll(f"{name} Props", self.root)
        self.lights = coll(f"{name} Lights", self.root)
        self.pal = M.palette()


def _obj(name, me, c, mat=None):
    ob = bpy.data.objects.new(name, me)
    c.objects.link(ob)
    if mat is not None:
        if isinstance(mat, (list, tuple)):
            for m in mat:
                me.materials.append(m)
        else:
            me.materials.append(mat)
    return ob


def _finish(ob, bevel=0.006, segs=3, smooth=True, angle=35):
    me = ob.data
    for p in me.polygons:
        p.use_smooth = smooth
    if bevel and DETAIL["level"] >= 1:
        b = ob.modifiers.new("Bevel", "BEVEL")
        b.width = bevel
        b.segments = segs if DETAIL["level"] >= 2 else 1
        b.limit_method = "ANGLE"
        b.angle_limit = math.radians(angle)
        b.harden_normals = True
        b.miter_outer = "MITER_ARC"
    if smooth:
        w = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL")
        w.keep_sharp = True
    return ob


def box(name, size, loc, mat, c, bevel=0.006, rot=(0, 0, 0), segs=3):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = _obj(name, me, c, mat)
    ob.location = loc
    ob.rotation_euler = rot
    return _finish(ob, min(bevel, min(size) * 0.45), segs)


def cyl(name, r, h, loc, mat, c, verts=32, rot=(0, 0, 0), bevel=0.004, cap_fill="NGON"):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts, radius1=r, radius2=r, depth=h)
    bm.to_mesh(me)
    bm.free()
    ob = _obj(name, me, c, mat)
    ob.location = loc
    ob.rotation_euler = rot
    return _finish(ob, min(bevel, r * 0.4, h * 0.4), 2, angle=50)


def rounded(name, size, loc, mat, c, soft=2, rot=(0, 0, 0), wrinkle=0.0):
    """Soft cushion-like block: a box with subdivision and a crease-free bevel."""
    ob = box(name, size, loc, mat, c, bevel=min(size) * 0.25, rot=rot, segs=4)
    s = ob.modifiers.new("Soft", "SUBSURF")
    s.levels = 1
    s.render_levels = max(soft, 3)
    if wrinkle and DETAIL["level"] >= 2:
        tx = bpy.data.textures.get("SB Wrinkle") or bpy.data.textures.new("SB Wrinkle", "CLOUDS")
        tx.noise_scale = 0.14
        tx.noise_depth = 3
        d = ob.modifiers.new("Wrinkles", "DISPLACE")
        d.texture = tx
        d.texture_coords = "GLOBAL"
        d.strength = wrinkle
        d.mid_level = 0.5
    return ob


def join(objs, name):
    """Merge many small parts into one object (keeps modifiers applied)."""
    if not objs:
        return None
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats_all = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev)
        me.transform(o.matrix_world)
        offset = len(mats_all)
        for m in me.materials:
            mats_all.append(m)
        for p in me.polygons:
            p.material_index += offset
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats_all:
        me.materials.append(m)
    c = objs[0].users_collection[0]
    for o in objs:
        bpy.data.objects.remove(o)
    ob = _obj(name, me, c)
    return ob


# ---------------------------------------------------------------- hardware
_BOLT = {}


def bolt_mesh():
    if "m" in _BOLT and _BOLT["m"].name in bpy.data.meshes:
        return _BOLT["m"]
    me = bpy.data.meshes.new("SB_Bolt")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.007, radius2=0.007, depth=0.004)
    w = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.011, radius2=0.011, depth=0.0015)
    bmesh.ops.translate(bm, vec=(0, 0, -0.0025), verts=w["verts"])
    bm.to_mesh(me)
    bm.free()
    me.materials.append(M.brushed_steel("SB Bolt Steel", (0.5, 0.48, 0.45, 1), 0.35))
    _BOLT["m"] = me
    return me


def bolt(loc, normal, c):
    ob = bpy.data.objects.new("Bolt", bolt_mesh())
    c.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = Vector((0, 0, 1)).rotation_difference(Vector(normal)).to_euler()
    ob.rotation_euler.rotate_axis("Z", RNG.random() * 6.28)
    return ob


# ---------------------------------------------------------------- walls
def wall(room, origin, u, v, width, height, normal, pal_key="panel", panel=(1.0, 0.75),
         skip=None, name="Wall", trim_start=0.0, trim_end=0.0):
    """A wall face made of real inset panels over a dark backing.

    origin: bottom-left corner. u: unit vector along the width, v: up.
    normal: points into the room. skip(i, j) -> True leaves a hole (doors, windows).
    """
    u, v, n = Vector(u), Vector(v), Vector(normal)
    pal = room.pal
    parts = []
    backing = M.painted_metal("SB Backing", (0.02, 0.021, 0.023, 1), 0.6)
    rot = Matrix((u, v, n)).transposed().to_euler()
    nx, ny = max(1, round(width / panel[0])), max(1, round(height / panel[1]))
    pw, ph = width / nx, height / ny
    gap = 0.008
    for i in range(nx):
        for j in range(ny):
            if skip and skip(i, j, pw, ph):
                continue
            key = pal_key
            if j == 0:
                key = "hull"  # kick plate
            # trim: the first/last column is narrowed so it stops short of a meeting wall
            ts = trim_start if i == 0 else 0.0
            te = trim_end if i == nx - 1 else 0.0
            pwi = pw - ts - te
            c0 = Vector(origin) + u * (pw * (i + 0.5) + (ts - te) / 2) + v * (ph * (j + 0.5))
            bk = box(f"{name} Backing", (pwi, ph, 0.05), c0 - n * 0.04, backing, room.shell, bevel=0)
            bk.rotation_euler = rot
            depth = 0.03 + (0.012 if (i + j) % 3 == 0 and j > 0 else 0)
            p = box(f"{name} Panel", (pwi - gap, ph - gap, depth), (0, 0, 0), pal[key], room.shell, bevel=0.006)
            p.rotation_euler = Matrix((u, v, n)).transposed().to_euler()
            p.location = c0 + n * (depth / 2 - 0.015)
            parts.append(p)
            if DETAIL["level"] >= 2:
                for a in (-1, 1):
                    for b in (-1, 1):
                        bolt(c0 + u * a * (pwi / 2 - 0.035) + v * b * (ph / 2 - 0.035) + n * (depth - 0.013), n, room.dress)
            if DETAIL["level"] >= 3 and RNG.random() < 0.18 and j > 0:
                vent(room, c0 + n * (depth - 0.012), u, v, n, pwi * 0.55, ph * 0.35)
    return parts


def vent(room, centre, u, v, n, w, h, slats=9):
    rot = Matrix((u, v, n)).transposed().to_euler()
    fr = box("Vent Frame", (w, h, 0.012), centre + n * 0.006, room.pal["dark_steel"], room.dress, bevel=0.003)
    fr.rotation_euler = rot
    hole = box("Vent Hole", (w - 0.03, h - 0.03, 0.004), centre + n * 0.011, M.painted_metal("SB Vent Black", (0.01, 0.01, 0.01, 1), 0.7), room.dress, bevel=0)
    hole.rotation_euler = rot
    for k in range(slats):
        t = (k + 0.5) / slats - 0.5
        s = box("Vent Slat", (w - 0.035, 0.004, 0.018), centre + v * t * (h - 0.03) + n * 0.016, room.pal["dark_steel"], room.dress, bevel=0.0015)
        s.rotation_euler = rot
        s.rotation_euler.rotate_axis("X", math.radians(35))


def floor(room, mat=None, trench=True):
    W, D = room.W, room.D
    f = box("Deck", (W, D, 0.06), (0, D / 2, -0.03), mat or room.pal["deck"], room.shell, bevel=0.002)
    f.data.uv_layers.new()
    if False and trench and DETAIL["level"] >= 2:  # see arch.trench (placed around furniture)
        # cable trench with grating along the back wall
        tw = W - 0.2 - 2 * (getattr(room, "chamfer", 0.0) and getattr(room, "chamfer", 0.0) + 0.45)
        box("Trench", (tw, 0.3, 0.02), (0, D - 0.35, 0.001), M.painted_metal("SB Trench", (0.015, 0.015, 0.015, 1), 0.7), room.shell, bevel=0)
        for k in range(int((tw - 0.1) / 0.05)):
            x = -tw / 2 + 0.1 + k * 0.05
            box("Grate Bar", (0.008, 0.3, 0.012), (x, D - 0.35, 0.012), room.pal["dark_steel"], room.dress, bevel=0.002, segs=1)
    # skirting kick line
    return f


def ceiling(room, light_rows=2, color=(1.0, 0.86, 0.7, 1), power=60, cols=2,
            cove=0.0, cove_back=True, cove_color=None, cove_power=6):
    """Ceiling with structural ribs and recessed panel lights in a grid.

    cove > 0 adds a chamfered cove where the ceiling meets the walls (a sloped,
    mitred band of that width), so the room is no longer a box, with a
    wall-wash light tucked under its lower lip."""
    W, D, H = room.W, room.D, room.H
    room.cove, room.cove_back = cove, cove_back
    box("Ceiling", (W, D, 0.08), (0, D / 2, H + 0.04), room.pal["hull"], room.shell, bevel=0.004)
    o = 0.05
    side_in = (o + cove + 0.1) if cove else 0.0
    for k in range(int(D) + 1):
        y = min(D - 0.06, k + 0.06)
        if y > D - 0.2 or (cove and cove_back and y > D - o - cove - 0.12):
            continue
        box("Ceiling Rib", (W - 2 * side_in, 0.12, 0.16), (0, y, H - 0.08), room.pal["panel"], room.shell, bevel=0.01)
    for r in range(light_rows):
        y = math.floor(D * (r + 0.5) / light_rows) + 0.56  # between two ribs
        for c in range(cols):
            x = -W / 2 + W * (c + 1) / (cols + 1)
            light_strip(room, (x, y, H - 0.02), 1.2, "X", (0, 0, -1), color, power, role="ceiling", width=0.28)
    if cove:
        _cove(room, cove, cove_back, o)
        cc = cove_color or color
        ch = getattr(room, "chamfer", 0.0)
        zl = H - cove - 0.05
        y1 = D - o - ch - 0.1 if ch else D - 0.4
        for sx in (-1, 1):
            light_strip(room, (sx * (W / 2 - 0.095), (0.15 + y1) / 2, zl), y1 - 0.15, "Y", (0, 0, -1), cc, cove_power, role="practical", width=0.03)
        if cove_back:
            x1 = W / 2 - o - (ch if ch else 0.3) - 0.1
            light_strip(room, (0, D - 0.095, zl), 2 * x1, "X", (0, 0, -1), cc, cove_power, role="practical", width=0.03)


def _cove(room, c, back, o):
    W, D, H = room.W, room.D, room.H
    lo, hi, t = H - c, H - 0.025, 0.021
    paths = ([[(-1, 0), (-1, 1), (1, 1), (1, 0)]] if back else [[(-1, 0), (-1, 1)], [(1, 1), (1, 0)]])
    verts, faces = [], []
    for path in paths:
        ring = []
        for sx, back_pt in path:
            yo = D - o if back_pt and back else (D - o if back_pt else 0.0)
            yi = D - o - c if back_pt and back else yo
            outer = Vector((sx * (W / 2 - o), yo, lo))
            inner = Vector((sx * (W / 2 - o - c), yi, hi))
            nh = Vector((sx, 1 if (back_pt and back) else 0, 0))
            up = Vector((0, 0, t)) + nh * t
            base = len(verts)
            verts += [outer, inner, outer + up, inner + up]
            ring.append(base)
        for i, j in zip(ring[:-1], ring[1:]):
            faces += [(i, j, j + 1, i + 1), (i + 2, i + 3, j + 3, j + 2), (i, i + 2, j + 2, j), (i + 1, j + 1, j + 3, i + 3)]
        for e in (ring[0], ring[-1]):
            faces.append((e, e + 1, e + 3, e + 2))
    me = bpy.data.meshes.new("Ceiling Cove")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.uv_layers.new()
    ob = _obj("Ceiling Cove", me, room.shell, room.pal["panel"])
    _finish(ob, bevel=0.006, segs=2, smooth=False)
    return ob


def frames(room, step=1.75, rail=True, avoid=(), place=None):
    """Structural wall frames (vertical ribs) and a steel handrail on the side walls.

    place(fn) -> list: optional collision-checked placement (arch._place); a
    frame or rail bay that would hit a door, screen or counter is then skipped."""
    W, D, H = room.W, room.D, room.H
    pal = room.pal
    cv, ch = getattr(room, "cove", 0.0), getattr(room, "chamfer", 0.0)
    fh = H - cv - 0.1 if cv else H
    put = place or (lambda fn: fn())
    bh = fh if (cv and getattr(room, "cove_back", True)) else H - 0.17
    k = step
    while k < W - 0.4:
        x = -W / 2 + k
        if not any(a - 0.1 < x < b + 0.1 for a, b in avoid):
            put(lambda x=x: (box("Wall Frame", (0.14, 0.12, bh - 0.125), (x, D - 0.09, 0.125 + (bh - 0.125) / 2), pal["hull"], room.shell, bevel=0.012),
                             box("Frame Foot", (0.16, 0.06, 0.124), (x, D - 0.117, 0.0625), pal["dark_steel"], room.shell, bevel=0.006)))
        k += step
    k = step
    while k < D - 0.3 - ch:
        for sx in (-1, 1):
            put(lambda sx=sx, k=k: (box("Wall Frame", (0.12, 0.14, fh - 0.125), (sx * (W / 2 - 0.09), k, 0.125 + (fh - 0.125) / 2), pal["hull"], room.shell, bevel=0.012),
                                    box("Frame Foot", (0.06, 0.16, 0.124), (sx * (W / 2 - 0.117), k, 0.0625), pal["dark_steel"], room.shell, bevel=0.006)))
        k += step
    if rail:
        ye = D - 0.45 - ch
        for sx in (-1, 1):
            x = sx * (W / 2 - 0.2)
            yy = 0.0
            while yy < ye - 0.3:
                y2 = min(ye, yy + 1.2)

                def bay(yy=yy, y2=y2, x=x, sx=sx):
                    pipe(room, [(x, yy + 0.002, 1.0), (x, y2 - 0.002, 1.0)], 0.02, pal["steel"], flanges=False, name="Handrail")
                    if yy > 0:
                        box("Rail Bracket", (0.16, 0.03, 0.03), (sx * (W / 2 - 0.12), yy + 0.03, 1.0), pal["dark_steel"], room.dress, bevel=0.006)
                    box("Rail Bracket", (0.16, 0.03, 0.03), (sx * (W / 2 - 0.12), y2 - 0.03, 1.0), pal["dark_steel"], room.dress, bevel=0.006)
                put(bay)
                yy = y2


def stencil(room, text, loc, rot, size=0.12, color=(0.62, 0.55, 0.4, 1)):
    """Painted stencil lettering on a surface."""
    cu = bpy.data.curves.new("Stencil", "FONT")
    cu.body = text
    cu.size = size
    cu.align_x = "CENTER"
    cu.extrude = 0.0006
    try:
        cu.font = bpy.data.fonts.load("<builtin>") if "Bfont Regular" not in bpy.data.fonts else bpy.data.fonts["Bfont Regular"]
    except Exception:
        pass
    ob = bpy.data.objects.new("Stencil " + text[:12], cu)
    room.dress.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    cu.materials.append(M.painted_metal("SB Stencil Paint", color, 0.55))
    return ob


# ---------------------------------------------------------------- services
def pipe(room, pts, r, mat=None, flanges=True, name="Pipe"):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (*q, 1)
    ob = bpy.data.objects.new(name, cu)
    room.dress.objects.link(ob)
    cu.materials.append(mat or room.pal["steel"])
    ob["sb_group"] = "pipe:" + ob.name
    if flanges and DETAIL["level"] >= 2:
        for a, b in zip(pts[:-1], pts[1:]):
            a, b = Vector(a), Vector(b)
            L = (b - a).length
            d = (b - a).normalized()
            k = 0.6
            while k < L - 0.3:
                q = a + d * k
                f = cyl("Flange", r * 1.45, 0.025, q, room.pal["dark_steel"], room.dress, verts=24)
                f["sb_group"] = "pipe:" + ob.name
                f.rotation_euler = Vector((0, 0, 1)).rotation_difference(d).to_euler()
                k += 1.2
    return ob


def cable(room, a, b, sag=0.25, r=0.012, mat=None, name="Cable"):
    a, b = Vector(a), Vector(b)
    pts = []
    for i in range(13):
        t = i / 12
        p = a.lerp(b, t)
        p.z -= sag * 4 * t * (1 - t)
        pts.append(p)
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 4
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (*q, 1)
    sp.use_endpoint_u = True
    sp.order_u = 3
    ob = bpy.data.objects.new(name, cu)
    room.dress.objects.link(ob)
    cu.materials.append(mat or room.pal["rubber"])
    return ob


def light_strip(room, loc, length, axis, facing, color, power, role="practical", width=0.06):
    """A real light fixture: housing, glowing diffuser and a matching area light."""
    loc, facing = Vector(loc), Vector(facing)
    size = {"X": (length, width, 0.03), "Y": (width, length, 0.03), "Z": (width, 0.03, length)}[axis]
    hs = {"X": (length + 0.04, width + 0.04, 0.05), "Y": (width + 0.04, length + 0.04, 0.05), "Z": (width + 0.04, 0.05, length + 0.04)}[axis]
    hous = box("Light Housing", hs, loc - facing * 0.015, room.pal["dark_steel"], room.dress, bevel=0.004)
    em = M.emissive(f"SB Light {role} {tuple(round(c, 2) for c in color)}", color, 5)
    em["sb_role"] = role
    d = box("Light Diffuser", size, loc + facing * 0.012, em, room.dress, bevel=0.003)
    d["sb_light"] = role
    hous["sb_group"] = d["sb_group"] = "fixture:" + hous.name
    L = bpy.data.lights.new(f"SB {role}", "AREA")
    L.shape = "RECTANGLE"
    if axis == "X":
        L.size, L.size_y = length, width * 2
    elif axis == "Y":
        L.size, L.size_y = width * 2, length
    else:
        L.size, L.size_y = width * 2, length
    L.color = color[:3]
    L.energy = power * length
    if hasattr(L, "use_soft_falloff"):
        L.use_soft_falloff = True
    lo = bpy.data.objects.new(f"SB {role} Light", L)
    room.lights.objects.link(lo)
    lo.location = loc + facing * 0.03
    lo.rotation_euler = Vector((0, 0, -1)).rotation_difference(facing).to_euler()
    if axis == "Z":
        lo.rotation_euler.rotate_axis("Z", math.radians(90))
    lo["sb_light"] = role
    lo["sb_energy"] = L.energy
    lo["sb_color"] = list(color[:3])
    return lo


def point_glow(room, loc, color, power=5, radius=0.02, role="practical"):
    L = bpy.data.lights.new(f"SB {role}", "POINT")
    L.color = color[:3]
    L.energy = power
    L.shadow_soft_size = radius
    lo = bpy.data.objects.new(f"SB {role} Glow", L)
    room.lights.objects.link(lo)
    lo.location = loc
    lo["sb_light"] = role
    lo["sb_energy"] = power
    lo["sb_color"] = list(color[:3])
    return lo


def screen(room, centre, u, v, n, w, h, color=(0.3, 0.85, 1, 1), kind="ui", light=True, name="Screen", strength=3.0,
           depth=0.05, margin=0.03):
    """depth/margin size the bezel: a wall monitor is 5 cm deep, a datapad's glass is flush."""
    u, v, n = Vector(u), Vector(v), Vector(n)
    rot = Matrix((u, v, n)).transposed().to_euler()
    bz = box(f"{name} Bezel", (w + 2 * margin, h + 2 * margin, depth), Vector(centre) + n * depth / 2, room.pal["plastic"], room.dress, bevel=min(0.008, depth * 0.4))
    bz.rotation_euler = rot
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    bmesh.ops.scale(bm, vec=(w, h, 1), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    me.uv_layers.new()
    for l, uv in zip(me.loops, me.uv_layers[0].data):
        co = me.vertices[l.vertex_index].co
        uv.uv = (co.x / w + 0.5, co.y / h + 0.5)
    smat = M.screen(f"SB Screen {kind} {strength} {tuple(round(c, 2) for c in color)}", color, strength, kind)
    smat["sb_role"] = "screen"
    sc = _obj(name, me, room.dress, smat)
    sc.location = Vector(centre) + n * (depth + 0.001)
    sc.rotation_euler = rot
    sc["sb_light"] = "screen"
    if light:
        L = bpy.data.lights.new("SB screen", "AREA")
        L.shape = "RECTANGLE"
        L.size, L.size_y = w, h
        L.color = color[:3]
        L.energy = 25 * w * h
        lo = bpy.data.objects.new("SB screen Light", L)
        room.lights.objects.link(lo)
        lo.location = Vector(centre) + n * 0.07
        lo.rotation_euler = Vector((0, 0, -1)).rotation_difference(n).to_euler()
        lo["sb_light"] = "screen"
        lo["sb_energy"] = L.energy
        lo["sb_color"] = list(color[:3])
    return sc


# ---------------------------------------------------------------- physics
def rigid(ob, mass=1.0, passive=False, friction=0.7, bounce=0.1, shape="CONVEX_HULL"):
    sc = bpy.context.scene
    if sc.rigidbody_world is None:
        with bpy.context.temp_override(scene=sc):
            bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    if rbw.collection is None:
        rbw.collection = bpy.data.collections.new("SB RigidBodies")
    if ob.name not in rbw.collection.objects:
        rbw.collection.objects.link(ob)
    rb = ob.rigid_body
    rb.type = "PASSIVE" if passive else "ACTIVE"
    rb.mass = mass
    rb.friction = friction
    rb.restitution = bounce
    rb.collision_shape = shape
    rb.collision_margin = 0.002
    rb.use_margin = True
    ob["sb_physics"] = "passive" if passive else "prop"
    return ob
