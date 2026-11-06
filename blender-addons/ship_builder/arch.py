"""Architecture and greebles: the pass that stops a room reading as a box.

    arch.detail(room, seed=1, density=1.0)

Runs after a room's furniture is placed and before the wear pass.
- Chamfered corner columns at the back corners. Each has an inset panel, a light
  slot and a pipe pair running up into the ceiling cove.
- Overhead services:
  - rectangular air ducts with flanges, hangers and grilles
  - cable trays loaded with cable bundles
  - sprinkler heads
- Wall services: conduit bundles with clamps, vertical risers, junction boxes.
- Wall fixtures:
  - fire extinguishers
  - intercoms
  - pressure gauges
  - access hatches
  - emergency lamps
  - data ports
  - labelled sign plates
- Deck details: lane markings, tie-down rings, bolted floor hatches.

Every group is placed, checked against everything already in the room with a
BVH, and removed again if it would touch anything. So nothing intersects, and a
crowded spot simply gets skipped.
"""
import math
import random
import bpy
from mathutils import Vector, Matrix

from . import kit as K
from . import mats as M
from .wear import Collider, _panels

SIGNS = ["O2 LINE 3", "COOLANT", "AUX PWR B", "DO NOT VENT", "STOW LOOSE ITEMS", "HULL ACCESS",
         "DATA BUS 7", "NO OIL PAST HERE", "PRESSURE DOOR", "FIRE SUPPRESS", "SERVICE ONLY", "LIFE SUPPORT"]


# ---------------------------------------------------------------- framework
def _new_objects(fn):
    before = set(bpy.data.objects)
    fn()
    return [o for o in bpy.data.objects if o not in before]


def _place(col, fn, ignore=()):
    """Build a group with fn(); keep it only if it touches nothing already in the room."""
    objs = _new_objects(fn)
    if not objs:
        return []
    bpy.context.view_layer.update()
    col.dg = bpy.context.evaluated_depsgraph_get()
    for o in objs:
        col._cache(o)
    names = [o.name for o in objs]
    hits = [m for _, m in col.pairs(names) if not any(m.startswith(i) for i in ignore)]
    if hits:
        for o in objs:
            col.forget(o)
            bpy.data.objects.remove(o)
        return []
    _place.n = getattr(_place, "n", 0) + 1
    for o in objs:
        o["sb_group"] = f"arch{_place.n}"
    return objs


def _rot(u, v, n):
    return Matrix((u, v, n)).transposed().to_euler()


def walls(room):
    """(name, origin, u, n, length) for the three solid walls; up is +Z."""
    W, D = room.W, room.D
    return [
        ("back", Vector((-W / 2, D, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)), W),
        ("left", Vector((-W / 2, 0, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)), D),
        ("right", Vector((W / 2, D, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0)), D),
    ]


def _on_panel(room, p, n):
    """True if a wall panel (not a hole) sits behind world point p."""
    for pan in _panels(room):
        if pan.hide_render:
            continue
        mw = pan.matrix_world
        if (mw.to_3x3() @ Vector((0, 0, 1))).dot(n) < 0.9:
            continue
        q = mw.inverted() @ p
        if abs(q.x) < pan.dimensions.x / 2 - 0.02 and abs(q.y) < pan.dimensions.y / 2 - 0.02 and abs(q.z) < 0.2:
            return True
    return False


# ---------------------------------------------------------------- corner columns
def corners(room, accent=(1.0, 0.6, 0.3, 1)):
    """Chamfered back corners: a 45-degree column face hides each 90-degree corner."""
    c = getattr(room, "chamfer", 0.0)
    if not c:
        return
    W, D, H = room.W, room.D, room.H
    top = H - getattr(room, "cove", 0.0) - 0.006
    o = 0.065
    pal = room.pal
    for sx in (-1, 1):
        xw = sx * (W / 2 - o)
        a = Vector((xw, D - o - c, 0.002))
        b = Vector((xw - sx * c, D - o, 0.002))
        w = Vector((xw, D - o, 0.002))
        me = bpy.data.meshes.new("Corner Column")
        vs = [a, b, w, a + Vector((0, 0, top)), b + Vector((0, 0, top)), w + Vector((0, 0, top))]
        me.from_pydata([tuple(v) for v in vs], [], [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)])
        me.validate()
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        before = set(bpy.data.objects)
        ob = K._obj("Corner Column", me, room.shell, pal["hull"])
        K._finish(ob, bevel=0.008, segs=2, smooth=False)
        # details on the 45-degree face
        u = (b - a).normalized()
        n = Vector((-sx, -1, 0)).normalized()
        mid = (a + b) / 2
        rot = _rot(u, Vector((0, 0, 1)), n)
        fw = (b - a).length
        for z0, h in ((0.25, 0.9), (1.25, top - 1.45)):
            p = K.box("Column Panel", (fw - 0.14, h, 0.02), mid + n * 0.011 + Vector((0, 0, z0 + h / 2)), pal["panel"], room.shell, bevel=0.005)
            p.rotation_euler = rot
        slot = K.box("Column Light Slot", (0.035, top - 0.6, 0.01), mid + n * 0.0275 + Vector((0, 0, 0.3 + (top - 0.6) / 2)),
                     M.emissive(f"SB Column Glow {tuple(round(x, 2) for x in accent[:3])}", accent, 2.5), room.dress, bevel=0.002)
        slot.rotation_euler = rot
        slot["sb_light"] = "practical"
        slot.data.materials[0]["sb_role"] = "practical"
        for k in (-1, 1):
            K.pipe(room, [tuple(mid + n * 0.07 + u * k * (fw / 2 - 0.16) + Vector((0, 0, 0.13))),
                          tuple(mid + n * 0.07 + u * k * (fw / 2 - 0.16) + Vector((0, 0, top - 0.03)))],
                   0.022, pal["dark_steel"] if k < 0 else M.painted_metal("SB Pipe Oxide", (0.4, 0.13, 0.05, 1), 0.4), name="Riser Pipe")
            for z in (0.4, 1.3, 2.2):
                if z < top - 0.1:
                    cl = K.box("Pipe Clamp", (0.07, 0.025, 0.05), mid + n * 0.045 + u * k * (fw / 2 - 0.16) + Vector((0, 0, z)), pal["steel"], room.dress, bevel=0.004)
                    cl.rotation_euler = rot
        for part in set(bpy.data.objects) - before:
            part["sb_group"] = f"corner{sx}"


# ---------------------------------------------------------------- overhead
def _hangers(room, x, y0, y1, ztop, width, mat):
    H = room.H
    y = math.floor(y0) + 0.56
    while y < y1:
        for k in (-1, 1):
            K.cyl("Hanger Rod", 0.006, H - ztop - 0.004, (x + k * (width / 2 - 0.02), y, (H + ztop) / 2), mat, room.dress, verts=8, bevel=0)
        y += 1.0


def duct(room, x, z, y0, y1, w=0.42, h=0.26):
    pal = room.pal
    L = y1 - y0
    zc = z - h / 2
    sheet = M.brushed_steel("SB Galvanised", (0.42, 0.43, 0.42, 1), 0.45)
    K.box("Air Duct", (w, L, h), (x, (y0 + y1) / 2, zc), sheet, room.dress, bevel=0.004, segs=1)
    k = y0 + 0.6
    while k < y1 - 0.2:
        K.box("Duct Flange", (w + 0.03, 0.03, h + 0.03), (x, k, zc), pal["dark_steel"], room.dress, bevel=0.003, segs=1)
        k += 1.2
    for yy in (y0 + 0.9, y0 + L * 0.6):
        if yy < y1 - 0.4:
            K.box("Duct Grille", (w - 0.08, 0.36, 0.015), (x, yy, z - h - 0.006), pal["dark_steel"], room.dress, bevel=0.002, segs=1)
            for s in range(7):
                K.box("Grille Slat", (w - 0.1, 0.012, 0.012), (x, yy - 0.15 + s * 0.05, z - h - 0.016), pal["steel"], room.dress, bevel=0.002, segs=1)
    K.box("Duct Cap", (w + 0.02, 0.02, h + 0.02), (x, y0 + 0.01, zc), pal["dark_steel"], room.dress, bevel=0.003, segs=1)
    _hangers(room, x, y0, y1, z, w, pal["dark_steel"])


def tray(room, x, z, y0, y1, w=0.3, rng=None):
    pal = room.pal
    L = y1 - y0
    rng = rng or random.Random(3)
    K.box("Cable Tray", (w, L, 0.008), (x, (y0 + y1) / 2, z - 0.07), pal["dark_steel"], room.dress, bevel=0.002, segs=1)
    for k in (-1, 1):
        K.box("Tray Lip", (0.008, L, 0.07), (x + k * w / 2, (y0 + y1) / 2, z - 0.035), pal["dark_steel"], room.dress, bevel=0.002, segs=1)
    cols = [pal["rubber"], M.plastic("SB Cable Red", (0.35, 0.03, 0.02, 1), 0.45), M.plastic("SB Cable Yellow", (0.6, 0.42, 0.04, 1), 0.45),
            M.plastic("SB Cable Blue", (0.04, 0.12, 0.35, 1), 0.45)]
    xs = [-w / 2 + 0.03 + i * (w - 0.06) / 5 for i in range(6)]
    for i, dx in enumerate(xs):
        r = rng.choice((0.009, 0.012, 0.016))
        K.pipe(room, [(x + dx, y0 + 0.02, z - 0.066 + r), (x + dx, y1 - 0.02, z - 0.066 + r)], r, cols[i % len(cols)], flanges=False, name="Tray Cable")
    _hangers(room, x, y0, y1, z, w + 0.04, pal["dark_steel"])


def sprinkler(room, x, y):
    H = room.H
    K.cyl("Sprinkler Pipe", 0.01, 0.1, (x, y, H - 0.052), room.pal["steel"], room.dress, verts=12, bevel=0)
    K.cyl("Sprinkler Head", 0.022, 0.018, (x, y, H - 0.112), M.brushed_steel("SB Brass", (0.55, 0.4, 0.18, 1), 0.35), room.dress, verts=16, bevel=0.003)
    K.cyl("Sprinkler Bulb", 0.006, 0.02, (x, y, H - 0.132), M.liquid("SB Sprinkler Red", (0.6, 0.02, 0.02, 1)), room.dress, verts=10, bevel=0)


# ---------------------------------------------------------------- wall fixtures
def _frame(origin, u, n, s, z, stand=0.032):
    up = Vector((0, 0, 1))
    return origin + u * s + up * z + n * stand, u, up, n


def extinguisher(room, P, u, v, n):
    rot = _rot(u, v, n)
    red = M.painted_metal("SB Fire Red", (0.45, 0.025, 0.02, 1), 0.3)
    b = K.box("Extinguisher Bracket", (0.14, 0.42, 0.01), P + n * 0.005, room.pal["dark_steel"], room.dress, bevel=0.003)
    b.rotation_euler = rot
    K.cyl("Extinguisher", 0.07, 0.42, P + n * 0.083 + v * 0.0, red, room.dress, verts=32, bevel=0.02)
    K.cyl("Extinguisher Valve", 0.025, 0.06, P + n * 0.083 + v * 0.24, room.pal["steel"], room.dress, verts=16, bevel=0.004)
    h = K.box("Extinguisher Handle", (0.11, 0.015, 0.02), P + n * 0.083 + v * 0.28 + u * 0.03, room.pal["plastic"], room.dress, bevel=0.004)
    h.rotation_euler = rot
    K.pipe(room, [tuple(P + n * 0.083 + v * 0.27 - u * 0.03), tuple(P + n * 0.16 + v * 0.2 - u * 0.05), tuple(P + n * 0.16 + v * -0.1 - u * 0.05)],
           0.008, room.pal["rubber"], flanges=False, name="Extinguisher Hose")
    lab = K.box("Extinguisher Label", (0.07, 0.1, 0.002), P + n * 0.154 + v * 0.02, M.plastic("SB Label White", (0.6, 0.58, 0.52, 1), 0.5), room.dress, bevel=0.0005, segs=1)
    lab.rotation_euler = rot


def intercom(room, P, u, v, n):
    rot = _rot(u, v, n)
    b = K.box("Intercom", (0.18, 0.28, 0.045), P + n * 0.0225, room.pal["plastic_grey"], room.dress, bevel=0.008)
    b.rotation_euler = rot
    for k in range(6):
        s = K.box("Intercom Grille", (0.11, 0.006, 0.004), P + n * 0.047 + v * (0.06 + k * 0.014), room.pal["plastic"], room.dress, bevel=0.001, segs=1)
        s.rotation_euler = rot
    K.screen(room, P + n * 0.046 + v * -0.03, u, v, n, 0.11, 0.06, (0.4, 1.0, 0.5, 1), "ui", light=False, name="Intercom Screen", strength=1.0)
    bt = K.cyl("Intercom Button", 0.014, 0.012, P + n * 0.051 + v * -0.1, M.emissive("SB Button Green", (0.3, 1.0, 0.4, 1), 3), room.dress, verts=16, bevel=0.002)
    bt.rotation_euler = Vector((0, 0, 1)).rotation_difference(n).to_euler()


def gauge(room, P, u, v, n):
    q = Vector((0, 0, 1)).rotation_difference(n).to_euler()
    K.cyl("Gauge Body", 0.075, 0.04, P + n * 0.02, room.pal["steel"], room.dress, verts=32, bevel=0.006, rot=q)
    K.cyl("Gauge Face", 0.064, 0.004, P + n * 0.042, M.plastic("SB Gauge Face", (0.36, 0.34, 0.28, 1), 0.45), room.dress, verts=32, bevel=0, rot=q)
    nd = K.box("Gauge Needle", (0.004, 0.05, 0.002), P + n * 0.046 + v * 0.015, M.plastic("SB Needle Red", (0.5, 0.03, 0.02, 1), 0.4), room.dress, bevel=0, segs=1)
    nd.rotation_euler = (Matrix((u, v, n)).transposed() @ Matrix.Rotation(math.radians(random.uniform(-70, 70)), 3, "Z")).to_euler()
    K.cyl("Gauge Glass", 0.066, 0.003, P + n * 0.05, M.glass(), room.dress, verts=32, bevel=0, rot=q)
    K.pipe(room, [tuple(P + n * 0.02 - v * 0.075), tuple(P + n * 0.02 - v * 0.35)], 0.012, room.pal["steel"], flanges=False, name="Gauge Pipe")


def hatch(room, P, u, v, n):
    rot = _rot(u, v, n)
    p = K.box("Access Hatch", (0.46, 0.46, 0.014), P + n * 0.007, room.pal["accent"], room.dress, bevel=0.006)
    p.rotation_euler = rot
    h = K.box("Hatch Handle", (0.16, 0.025, 0.025), P + n * 0.03 + v * -0.12, room.pal["steel"], room.dress, bevel=0.006)
    h.rotation_euler = rot
    for a in (-1, 1):
        for b in (-1, 1):
            K.bolt(P + n * 0.0165 + u * a * 0.19 + v * b * 0.19, n, room.dress)
    hz = K.box("Hatch Stripe", (0.44, 0.04, 0.002), P + n * 0.0152 + v * 0.18, M.hazard(), room.dress, bevel=0.0005, segs=1)
    hz.rotation_euler = rot


def junction(room, P, u, v, n, H):
    rot = _rot(u, v, n)
    b = K.box("Junction Box", (0.3, 0.4, 0.11), P + n * 0.055, room.pal["plastic_grey"], room.dress, bevel=0.008)
    b.rotation_euler = rot
    lid = K.box("Junction Lid Seam", (0.26, 0.004, 0.003), P + n * 0.1115 + v * 0.12, room.pal["plastic"], room.dress, bevel=0, segs=1)
    lid.rotation_euler = rot
    lab = K.box("Junction Warning", (0.09, 0.09, 0.002), P + n * 0.1115 + v * -0.05, M.hazard(), room.dress, bevel=0.0005, segs=1)
    lab.rotation_euler = rot
    for k in (-1, 0, 1):
        K.pipe(room, [tuple(P + n * 0.05 + u * k * 0.08 + v * 0.2), tuple(P + n * 0.05 + u * k * 0.08 + Vector((0, 0, H - P.z - 0.12)))],
               0.014, room.pal["dark_steel"], flanges=False, name="Conduit Riser")


def lamp(room, P, u, v, n):
    rot = _rot(u, v, n)
    b = K.box("Emergency Lamp", (0.26, 0.1, 0.07), P + n * 0.035, room.pal["plastic"], room.dress, bevel=0.01)
    b.rotation_euler = rot
    lens = K.box("Emergency Lens", (0.2, 0.06, 0.01), P + n * 0.0755, M.emissive("SB Emergency Lens", (1.0, 0.35, 0.08, 1), 0.0), room.dress, bevel=0.004)
    lens.rotation_euler = rot
    lens.data.materials[0]["sb_role"] = "emergency"
    lens.data.materials[0]["sb_strength"] = 6.0


def ports(room, P, u, v, n):
    rot = _rot(u, v, n)
    b = K.box("Data Port Plate", (0.22, 0.12, 0.012), P + n * 0.006, room.pal["dark_steel"], room.dress, bevel=0.003)
    b.rotation_euler = rot
    for k in range(4):
        s = K.box("Data Socket", (0.03, 0.022, 0.006), P + n * 0.0155 + u * (-0.075 + k * 0.05), room.pal["plastic"], room.dress, bevel=0.002, segs=1)
        s.rotation_euler = rot
    g = K.cyl("Port LED", 0.004, 0.004, P + n * 0.0145 + v * 0.04, M.emissive("SB LED Amber", (1.0, 0.55, 0.1, 1), 4), room.dress, verts=8, bevel=0)
    g.rotation_euler = Vector((0, 0, 1)).rotation_difference(n).to_euler()


def sign(room, P, u, v, n, text):
    rot = _rot(u, v, n)
    w = 0.06 + 0.045 * len(text)
    b = K.box("Sign Plate", (w, 0.08, 0.006), P + n * 0.003, room.pal["cream"], room.dress, bevel=0.002)
    b.rotation_euler = rot
    st = K.stencil(room, text, P + n * 0.0064 - v * 0.018, rot, 0.045, (0.03, 0.03, 0.03, 1))
    st.data.extrude = 0.0003


def conduit_run(room, origin, u, n, s0, s1, z):
    """Three conduits with clamps along a wall at height z, elbowing into wall plates at both ends."""
    up = Vector((0, 0, 1))
    rot = _rot(u, up, n)
    mats_ = [room.pal["dark_steel"], room.pal["steel"], M.painted_metal("SB Pipe Teal", (0.08, 0.2, 0.21, 1), 0.4)]
    for k, r in enumerate((0.016, 0.012, 0.012)):
        h = up * (z + k * 0.045)
        a = origin + u * s0 + h
        b = origin + u * s1 + h
        K.pipe(room, [tuple(a + n * 0.05), tuple(a + n * 0.07 + u * 0.06), tuple(b + n * 0.07 - u * 0.06), tuple(b + n * 0.05)],
               r, mats_[k], flanges=False, name="Wall Conduit")
        for e in (a, b):
            pl = K.box("Conduit Wall Plate", (0.06, 0.05, 0.01), e + n * 0.036, room.pal["dark_steel"], room.dress, bevel=0.002)
            pl.rotation_euler = rot
    s = s0 + 0.35
    while s < s1 - 0.25:
        c = K.box("Conduit Clamp", (0.035, 0.13, 0.03), origin + u * s + n * 0.07 + up * (z + 0.045), room.pal["dark_steel"], room.dress, bevel=0.004)
        c.rotation_euler = rot
        s += 0.5


# ---------------------------------------------------------------- deck
def lane(room, a, b, width=0.05):
    a, b = Vector(a), Vector(b)
    d = b - a
    yellow = M.painted_metal("SB Lane Paint", (0.55, 0.38, 0.04, 1), 0.5)
    ob = K.box("Lane Line", (d.length, width, 0.0012), ((a + b) / 2).to_3d() + Vector((0, 0, 0.0009)), yellow, room.dress, bevel=0, segs=1)
    ob.rotation_euler = (0, 0, math.atan2(d.y, d.x))


def tie_down(room, x, y):
    K.cyl("Tie-down Plate", 0.06, 0.008, (x, y, 0.0045), room.pal["dark_steel"], room.dress, verts=24, bevel=0.002)
    cu = bpy.data.curves.new("Tie-down Ring", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 0.006
    sp = cu.splines.new("NURBS")
    sp.points.add(6)
    for i, p in enumerate(sp.points):
        t = math.pi * i / 6
        p.co = (x + math.cos(t) * 0.035, y, 0.0145 + math.sin(t) * 0.028, 1)
    sp.use_endpoint_u = True
    ob = bpy.data.objects.new("Tie-down Ring", cu)
    room.dress.objects.link(ob)
    cu.materials.append(room.pal["steel"])


def floor_hatch(room, x, y, yaw=0.0):
    p = K.box("Floor Hatch", (0.7, 0.7, 0.008), (x, y, 0.0045), M.diamond_plate(), room.dress, bevel=0.003, rot=(0, 0, yaw))
    R = Matrix.Rotation(yaw, 3, "Z")
    for a in (-1, 1):
        for b in (-1, 1):
            K.bolt(Vector((x, y, 0.0105)) + R @ Vector((a * 0.31, b * 0.31, 0)), (0, 0, 1), room.dress)
    h = K.box("Hatch Pull", (0.14, 0.03, 0.006), Vector((x, y, 0.0115)) + R @ Vector((0, -0.25, 0)), room.pal["steel"], room.dress, bevel=0.002, rot=(0, 0, yaw))


# ---------------------------------------------------------------- floor services
def trench(room, col):
    """Cable trench with a grating along the back wall, laid in 0.6 m sections that skip furniture."""
    W, D = room.W, room.D
    ch = getattr(room, "chamfer", 0.0)
    x0, x1 = -W / 2 + ch + 0.55, W / 2 - ch - 0.55
    n, x = 0, x0
    tr = M.painted_metal("SB Trench", (0.015, 0.015, 0.015, 1), 0.7)

    def sec(a, b):
        K.box("Trench", (b - a, 0.3, 0.012), ((a + b) / 2, D - 0.35, 0.0065), tr, room.shell, bevel=0)
        k = a + 0.025
        while k < b - 0.02:
            K.box("Grate Bar", (0.008, 0.3, 0.012), (k, D - 0.35, 0.0195), room.pal["dark_steel"], room.dress, bevel=0.002, segs=1)
            k += 0.05
    while x < x1 - 0.2:
        b = min(x1, x + 0.6)
        if _place(col, lambda a=x, b=b: sec(a, b), ignore=("Deck",)):
            n += 1
        x = b + 0.004
    return n


def walk_tiles(room, col, x0, x1, y0, y1, size=0.6):
    """Diamond-plate walkway laid as tiles; tiles under furniture are left out (cut around it)."""
    dp = M.diamond_plate()
    y = y0
    while y < y1 - 0.1:
        x = x0
        while x < x1 - 0.1:
            w, d = min(size, x1 - x) - 0.004, min(size, y1 - y) - 0.004
            _place(col, lambda x=x, y=y, w=w, d=d: K.box("Walkway Tile", (w, d, 0.01), (x + w / 2, y + d / 2, 0.0055), dp, room.dress, bevel=0.002),
                   ignore=("Deck",))
            x += size
        y += size


# ---------------------------------------------------------------- orchestration
def detail(room, seed=1, density=1.0, accent=None, ducts=True, frame_step=1.75, frame_avoid=(), walkway=None):
    """Fill the room with architecture and greebles. Returns counts."""
    rng = random.Random(seed * 31 + 5)
    random.seed(seed)
    W, D, H = room.W, room.D, room.H
    accent = accent or (1.0, 0.6, 0.3, 1)
    corners(room, accent)
    col = Collider(room)
    K.frames(room, step=frame_step, avoid=frame_avoid,
             place=lambda fn: _place(col, fn, ignore=("Deck", "Bolt")))
    out_t = trench(room, col)
    if walkway:
        walk_tiles(room, col, *walkway)
    out = {"ducts": 0, "trays": 0, "sprinklers": 0, "fixtures": 0, "conduits": 0, "deck": 0}
    cv = getattr(room, "cove", 0.0)
    # overhead: one duct and one tray, tried at several x positions
    if ducts:
        xs = [x for x in (-W * 0.36, W * 0.36, -W * 0.18, W * 0.18, 0.0)]
        rng.shuffle(xs)
        done_d = done_t = False
        for x in xs:
            if not done_d and _place(col, lambda x=x: duct(room, x, H - 0.19, 0.25, D - 0.9 - cv)):
                done_d, out["ducts"] = True, 1
                continue
            if not done_t and _place(col, lambda x=x: tray(room, x, H - 0.2, 0.25, D - 0.7 - cv, rng=rng)):
                done_t, out["trays"] = True, 1
    for k in range(int(10 * density)):
        x, y = rng.uniform(-W / 2 + 0.8, W / 2 - 0.8), rng.uniform(0.6, D - 0.8)
        if _place(col, lambda x=x, y=y: sprinkler(room, x, y)):
            out["sprinklers"] += 1
    # wall fixtures: try spots on panels until each kind is placed
    kinds = [("ext", extinguisher, (1.0, 1.1)), ("intercom", intercom, (1.35, 1.5)), ("gauge", gauge, (1.4, 1.7)),
             ("hatch", hatch, (0.55, 0.75)), ("junction", junction, (1.6, 1.9)), ("lamp", lamp, (2.0, 2.25)),
             ("ports", ports, (0.35, 0.5)), ("gauge", gauge, (1.2, 1.6)), ("hatch", hatch, (1.3, 1.6)),
             ("lamp", lamp, (2.0, 2.2)), ("ports", ports, (0.4, 0.6))]
    signs = list(SIGNS)
    rng.shuffle(signs)
    kinds += [("sign", None, (1.75, 2.05))] * int(5 * density)
    wl = walls(room)
    for key, fn, (z0, z1) in kinds[: int(len(kinds) * density) + 1]:
        for attempt in range(30):
            name, origin, u, n, L = rng.choice(wl)
            s = rng.uniform(0.6, L - 0.6)
            z = rng.uniform(z0, min(z1, H - cv - 0.35))
            P, uu, vv, nn = _frame(origin, u, n, s, z)
            if not _on_panel(room, origin + u * s + Vector((0, 0, z)) + n * 0.02, n):
                continue
            if key == "sign":
                text = signs[out["fixtures"] % len(signs)]
                ok = _place(col, lambda: sign(room, P, uu, vv, nn, text))
            elif key == "junction":
                ok = _place(col, lambda: junction(room, P, uu, vv, nn, H - cv))
            else:
                ok = _place(col, lambda fn=fn: fn(room, P, uu, vv, nn))
            if ok:
                out["fixtures"] += 1
                break
    # conduit runs along the walls
    # conduit runs along the walls, in short spans between frames and fittings
    for z in (2.2, 0.3, 1.8):
        for name, origin, u, n, L in wl:
            s = 0.35
            while s < L - 0.9:
                span = rng.uniform(0.9, 1.6)
                e = min(L - 0.35, s + span)
                if _place(col, lambda origin=origin, u=u, n=n, s=s, e=e, z=z: conduit_run(room, origin, u, n, s, e, z)):
                    out["conduits"] += 1
                    s = e + rng.uniform(0.3, 1.2)
                else:
                    s += 0.25
    # deck: lane lines, tie-downs, hatches
    for a, b in (((-W / 2 + 0.7, 0.3), (-W / 2 + 0.7, D - 0.9)), ((W / 2 - 0.7, 0.3), (W / 2 - 0.7, D - 0.9))):
        seg = 0.0
        a, b = Vector(a), Vector(b)
        L = (b - a).length
        while seg < L:
            e = min(L, seg + 0.9)
            if _place(col, lambda s=seg, e=e: lane(room, a + (b - a) * (s / L), a + (b - a) * (e / L)), ignore=("Deck",)):
                out["deck"] += 1
            seg = e + 0.25
    for k in range(int(8 * density)):
        x, y = rng.uniform(-W / 2 + 0.5, W / 2 - 0.5), rng.uniform(0.4, D - 0.5)
        if _place(col, lambda x=x, y=y: tie_down(room, x, y), ignore=("Deck",)):
            out["deck"] += 1
    for k in range(int(3 * density)):
        x, y = rng.uniform(-W / 2 + 0.8, W / 2 - 0.8), rng.uniform(0.6, D - 1.0)
        if _place(col, lambda x=x, y=y: floor_hatch(room, x, y, rng.choice((0.0, math.pi / 2))), ignore=("Deck",)):
            out["deck"] += 1
    return out
