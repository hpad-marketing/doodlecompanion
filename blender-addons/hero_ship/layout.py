"""Static airframe: every welded block, the open spine and its mechanics.

Coordinates (metres): nose +Y, starboard +X, up +Z. Ship is ~43 m long.
"""
import math
import random
import bmesh
import bpy
from mathutils import Matrix, Vector
from . import geo, body as B

GROUND_Z = -4.62          # ground height under the landing feet (see parts.GEAR)
RAMP_Y = (-10.6, -4.9)


def _liv_cab(r, ca, fs, rnd):
    m = B._col_marks()
    return ca in (m[2], B.RING - m[3]) and r <= 6


def _liv_aft(r, ca, fs, rnd):
    m = B._col_marks()
    side = ca in range(m[2], m[3]) or ca in range(B.RING - m[3], B.RING - m[2])
    return side and r in (0, 1, 2)


def _liv_engine(r, ca, fs, rnd):
    m = B._col_marks()
    return ca < m[1] or ca >= B.RING - m[1]


def build_hull(c, root, mats, seed=1, detail_density=1.0):
    rnd = random.Random(seed)
    bm = bmesh.new()
    L = B.layers(bm)
    mods = {}

    def M(name, st, **kw):
        kw.setdefault("rnd", random.Random(rnd.random()))
        mods[name] = B.Module(bm, name, st, **kw)
        return mods[name]

    #                y     hw    zlo    zhi   rt    rb   tuck
    M("cab", [(20.2, 3.00, -1.85, 1.55, 0.95, 0.70, 0.0),
              (17.0, 3.30, -2.00, 1.95, 1.00, 0.72, 0.0),
              (12.6, 3.35, -2.00, 2.05, 1.00, 0.72, 0.0)], front_rake=2.1, livery=_liv_cab)
    M("chin", [(19.2, 1.55, -2.55, -1.35, 0.35, 0.35, 0.0),
               (14.6, 1.65, -2.60, -1.35, 0.35, 0.35, 0.0)], front_rake=-0.5, row_len=0.8)
    M("fore", [(13.3, 3.90, -2.45, 2.50, 1.10, 0.80, 0.0),
               (12.6, 4.00, -2.50, 2.60, 1.10, 0.80, 0.0),
               (3.6, 4.05, -2.50, 2.62, 1.10, 0.80, 0.0)])
    M("fore_top", [(11.6, 2.25, 2.30, 3.25, 0.55, 0.10, 0.0),
                   (5.6, 2.35, 2.30, 3.30, 0.55, 0.10, 0.0)], front_rake=0.7, back_rake=0.3, row_len=0.75)
    M("keel", [(4.0, 1.70, -1.50, 1.10, 0.40, 0.40, 0.0),
               (-3.4, 1.70, -1.50, 1.10, 0.40, 0.40, 0.0)], row_len=0.9, mat=B.PRIMER)
    M("aft", [(-3.0, 4.50, -2.92, 2.92, 1.20, 0.90, 0.0),
              (-3.8, 4.60, -3.00, 3.00, 1.20, 0.90, 0.0),
              (-14.0, 4.60, -3.00, 3.00, 1.20, 0.90, 0.0)], livery=_liv_aft)
    M("aft_top", [(-4.6, 2.75, 2.70, 3.80, 0.60, 0.10, 0.0),
                  (-12.4, 2.85, 2.70, 3.85, 0.60, 0.10, 0.0)], front_rake=0.6, back_rake=0.4, row_len=0.8)
    for s in (1, -1):
        M(f"sponson{s}", [(-5.9, 0.85, -0.45, 1.55, 0.40, 0.40, 0.0),
                          (-11.6, 0.90, -0.50, 1.60, 0.40, 0.40, 0.0)], cx=4.95 * s, front_rake=0.4,
          row_len=0.7)
    M("engine", [(-13.6, 3.85, -2.35, 2.60, 1.00, 0.80, 0.0),
                 (-19.0, 3.95, -2.40, 2.65, 1.00, 0.80, 0.0)], livery=_liv_engine)
    # gear pods (open bottoms are cut below)
    M("pod_n", [(11.6, 0.80, -3.30, -2.30, 0.25, 0.22, 0.0),
                (8.4, 0.80, -3.30, -2.30, 0.25, 0.22, 0.0)], front_rake=-0.3, back_rake=-0.3, row_len=0.4)
    for s in (1, -1):
        M(f"pod{s}", [(-10.9, 0.80, -3.85, -2.88, 0.25, 0.22, 0.0),
                      (-13.9, 0.80, -3.85, -2.88, 0.25, 0.22, 0.0)], cx=3.0 * s, front_rake=-0.3,
          back_rake=-0.3, row_len=0.4)

    ramp_pts = mods["aft"].cut_belly(*RAMP_Y, depth=1.75)
    bays = {"ramp": mods["aft"].bay}
    for k in ("pod_n", "pod1", "pod-1"):
        mods[k].cut_belly(-99, 99, depth=0.80, full=True)
        bays[k] = mods[k].bay
    for m in mods.values():
        m.finish(L)
    # windshield: the raked front cap of the cab is glass
    glass = mods["cab"].caps[0]
    glass.material_index = B.GLASS
    done = set(bm.faces)
    _mullions(bm, glass)

    _greebles(bm, mods, rnd)
    from . import detail
    n_items = detail.apply(bm, mods, random.Random(seed * 7 + 3), density=detail_density, base_faces=done)
    ob = B.finish_object("Hull", bm, c, root, mats, done)
    ob["hs_part"] = "hull"
    ob["sb_piece"] = "hs_airframe"
    ob["hs_detail_items"] = n_items
    return ob, ramp_pts, mods


def _mullions(bm, face):
    """Window frame bars across the raked windscreen (proud of the glass)."""
    face.normal_update()
    nrm = face.normal.copy()
    cen = face.calc_center_median()
    up = Vector((0, 0, 1))
    up = (up - nrm * up.dot(nrm)).normalized()
    side = up.cross(nrm).normalized()
    us = [(v.co - cen).dot(side) for v in face.verts]
    vs = [(v.co - cen).dot(up) for v in face.verts]
    w, h = max(us) - min(us), max(vs) - min(vs)
    rot = Matrix((side, up, nrm)).transposed().to_4x4()
    bars = [(0.0, 0.0, 0.14, h), (-w * 0.3, 0.0, 0.1, h * 0.92), (w * 0.3, 0.0, 0.1, h * 0.92),
            (0.0, h * 0.12, w * 0.98, 0.1)]
    for du, dv, bw, bh in bars:
        before = len(bm.faces)
        geo.add_box(bm, cen + side * du + up * dv + nrm * 0.03, (bw, bh, 0.08), rot=rot)
        B._mat_new(bm, before, B.DARK)


def _greebles(bm, mods, rnd):
    P, D = B.PAINT, B.DARK
    for s in (1, -1):
        sx = "x+" if s > 0 else "x-"
        # cab sides: windows band (dark), vents, bolts
        cab = mods["cab"]
        B.vent(bm, (s * (cab.p(15.0)[0] + 0.01), 15.0, -0.4), 1.1, 0.7, sx, slats=5)
        for y in (16.8, 15.7, 14.6, 13.5):
            B.plate(bm, (s * (cab.p(y)[0] + 0.005), y, 0.55), (0.05, 0.8, 0.45), "Y", B.GLASS, bev=0.05)
        B.bolts_row(bm, (s * 3.33, 16.6, -1.15), (s * 3.33, 13.2, -1.15), 7, (s, 0, 0))
        # fore body: crew hatch, vents, conduit, glow line
        B.hatch(bm, (s * 4.07, 8.6, -0.35), 1.2, 2.0, sx)
        B.vent(bm, (s * 4.06, 11.4, 1.0), 1.3, 0.8, sx, slats=6)
        B.vent(bm, (s * 4.06, 5.2, 1.1), 0.8, 1.2, sx, slats=8)
        B.plate(bm, (s * 4.07, 5.4, -1.3), (0.06, 1.6, 0.7), "Y", P, bev=0.05)
        B.strip(bm, [(12.4, 0.35), (10.4, 0.35), (9.9, -0.95), (6.4, -0.95), (5.9, 0.35), (4.0, 0.35)],
                s * 4.05, width=0.075)
        B.tube(bm, [(s * 4.12, 12.3, -1.95), (s * 4.12, 4.1, -1.95)], 0.07, mat=D)
        for y in (11.6, 9.4, 7.4, 5.0):
            B.plate(bm, (s * 4.09, y, -1.95), (0.08, 0.16, 0.22), "Y", D, bev=0.01)
        # aft body sides (sponson occupies y -5.9..-11.6, z -0.5..1.6)
        B.vent(bm, (s * 4.66, -4.4, 0.6), 0.9, 1.6, sx, slats=9)
        B.vent(bm, (s * 4.66, -12.9, 0.9), 1.2, 0.9, sx, slats=6)
        B.hatch(bm, (s * 4.66, -12.9, -1.4), 1.3, 1.1, sx)
        B.strip(bm, [(-3.6, -1.35), (-5.2, -1.35), (-5.7, -2.0), (-11.8, -2.0), (-12.2, -1.35)],
                s * 4.6, width=0.075)
        # sponson: intake grille on its front, bolts
        B.bolts_row(bm, (s * 5.86, -6.4, 1.3), (s * 5.86, -11.2, 1.3), 9, (s, 0, 0), r=0.025)
        # engine block sides
        B.vent(bm, (s * 3.96, -16.3, 0.3), 2.2, 1.0, sx, slats=7)
        B.plate(bm, (s * 3.98, -16.3, -1.5), (0.07, 2.4, 0.5), "Y", D, bev=0.04)
        B.strip(bm, [(-13.9, 1.55), (-18.7, 1.55)], s * 3.97, width=0.06)
        # top: fore deck vents & hatch, aft deck greebles
        B.vent(bm, (s * 1.3, 9.6, 3.27), 0.8, 1.2, "z+", slats=7)
        B.vent(bm, (s * 1.6, -9.2, 3.82), 1.0, 1.4, "z+", slats=8)
        B.vent(bm, (s * 1.7, -15.8, 2.66), 1.2, 2.2, "z+", slats=10)
    B.hatch(bm, (0, 7.6, 3.32), 1.1, 1.1, "z+")
    B.hatch(bm, (0, -11.0, 3.85), 1.0, 1.4, "z+")
    B.plate(bm, (0, -16.0, 2.66), (1.2, 3.0, 0.08), "Z", B.DARK)
    # glow light bars on the cab brow
    B.plate(bm, (0, 17.3, 1.98), (2.6, 0.12, 0.05), "Z", B.GLOW, bev=0.01)
    # keel side detail in the open spine (between the tanks' saddles)
    for s in (1, -1):
        for y in (2.9, -2.7):
            B.plate(bm, (s * 1.72, y, -0.2), (0.07, 0.5, 2.2), "Y", B.DARK, bev=0.02)


def build_mechanics(c, root, mats):
    """Tanks, pipes and cables in the open spine between fore and aft bodies."""
    bm = bmesh.new()
    D, H = B.DARK, B.HEAT
    for s in (1, -1):
        for z, mat in ((0.95, B.PAINT), (-0.65, B.ACCENT)):
            before = len(bm.faces)
            prof = [(0.0, -2.9), (0.35, -2.88), (0.58, -2.78), (0.68, -2.6), (0.70, -2.35),
                    (0.70, 2.35), (0.68, 2.6), (0.58, 2.78), (0.35, 2.88), (0.0, 2.9)]
            m = Matrix.Translation((s * 2.75, 0.3, z)) @ Matrix.Rotation(-math.pi / 2, 4, "X")
            geo.lathe(bm, prof, segs=28, mat=m)
            B._mat_new(bm, before, mat)
            for y in (-1.6, 2.2):
                before = len(bm.faces)
                geo.add_cyl(bm, (s * 2.75, y - 0.09, z), (s * 2.75, y + 0.09, z), 0.735, segs=28)
                B._mat_new(bm, before, D)
                geo.add_box(bm, Vector((s * 1.88, y, z)), (0.40, 0.14, 0.26))
                B._mat_new(bm, before, D)
            # valve on the tank end
            before = len(bm.faces)
            geo.add_cyl(bm, (s * 2.75, 3.15, z), (s * 2.75, 3.45, z), 0.12, segs=10)
            geo.add_cyl(bm, (s * 2.75, 3.45, z), (s * 2.75, 3.55, z), 0.2, segs=12)
            B._mat_new(bm, before, H)
        # cable between the two tanks
        B.tube(bm, [(s * 2.75, 3.7, 0.15), (s * 2.75, 1.0, 0.15), (s * 2.75, -1.0, 0.15), (s * 2.75, -3.1, 0.15)],
               0.07, segs=8, mat=B.RUBBER)
    for x in (-1.2, -0.5, 0.5, 1.2):
        r = 0.14 if abs(x) > 1 else 0.11
        B.tube(bm, [(x, 3.8, 1.38), (x, 1.6, 1.38), (x, 0.9, 1.6), (x, -0.6, 1.6), (x, -1.3, 1.38), (x, -3.2, 1.38)],
               r, segs=12, mat=H if abs(x) > 1 else D)
    for x in (-0.9, 0.0, 0.9):
        B.tube(bm, [(x, 3.8, -1.76), (x, -3.2, -1.76)], 0.12, segs=12, mat=D)
    # flanges where pipes meet the bulkheads
    for x in (-1.2, -0.5, 0.5, 1.2):
        for y, z in ((3.55, 1.38), (-2.95, 1.38)):
            before = len(bm.faces)
            geo.add_cyl(bm, (x, y - 0.06, z), (x, y + 0.06, z), 0.2 if abs(x) > 1 else 0.17, segs=12)
            B._mat_new(bm, before, D)
    ob = B.finish_object("Spine Mechanics", bm, c, root, mats, set(), bevel_w=0.0)
    ob.modifiers.remove(ob.modifiers["Bevel"])
    ob["hs_part"] = "mechanics"
    ob["sb_piece"] = "hs_airframe"
    return ob


def build_engines(c, root, mats):
    """Three main thrusters out of the engine block's back plate (y = -19)."""
    bm = bmesh.new()
    glow = bmesh.new()
    for x, z, r in ((0.0, 0.95, 1.0), (2.0, -0.9, 0.9), (-2.0, -0.9, 0.9)):
        m = Matrix.Translation((x, -19.0, z)) @ Matrix.Rotation(math.pi / 2, 4, "X")
        # housing ring + bell (z of profile runs along -Y after rotation)
        before = len(bm.faces)
        prof = [(r * 1.08, -0.05), (r * 1.12, 0.1), (r * 1.12, 0.55), (r * 1.02, 0.62),
                (r * 0.95, 0.62)]
        geo.lathe(bm, prof, segs=36, mat=m)
        B._mat_new(bm, before, B.DARK)
        before = len(bm.faces)
        bell = [(r * 0.86, 0.6), (r * 0.9, 1.1), (r * 1.0, 1.8), (r * 1.13, 2.6), (r * 1.17, 2.75),
                (r * 1.10, 2.75), (r * 1.06, 2.6), (r * 0.94, 1.8), (r * 0.82, 1.1), (r * 0.76, 0.75)]
        geo.lathe(bm, bell, segs=36, mat=m)
        B._mat_new(bm, before, B.HEAT)
        # actuator rods from the housing to the bell (4 per engine)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            ca, sa = math.cos(a), math.sin(a)
            p0 = Vector((x + ca * r * 1.16, -19.35, z + sa * r * 1.16))
            p1 = Vector((x + ca * r * 1.0, -20.6, z + sa * r * 1.0))
            before = len(bm.faces)
            geo.add_cyl(bm, p0, p1, 0.05, segs=8)
            geo.add_cyl(bm, p0 + (p1 - p0) * 0.15, p0 + (p1 - p0) * 0.55, 0.075, segs=8)
            B._mat_new(bm, before, B.DARK)
        # glowing throat disc (separate, emissive object)
        gprof = [(0.0, 0.8), (r * 0.74, 0.8)]
        geo.lathe(glow, gprof, segs=36, mat=m)
    for f in glow.faces:
        f.material_index = B.ENGINE
    ob = B.finish_object("Main Engines", bm, c, root, mats, set(), bevel_w=0.0)
    ob.modifiers.remove(ob.modifiers["Bevel"])
    ob["sb_piece"] = "hs_airframe"
    g = geo.obj_from_bm("Engine Glow", glow, c, parent=root, mats=mats)
    g["sb_piece"] = "hs_airframe"
    g["engine"] = 0.2
    g.visible_shadow = False
    return ob, g
