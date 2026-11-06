"""Detail pass: makes the hull dense, slightly worn and lived in.

Runs after the modules and the big greebles. It walks every hull panel and
fills it with small hardware chosen for where the panel is (top, side, belly,
rounded edge): rivet rows, access plates, latches, small vents, conduits with
clamps, grab rails, junction boxes with sagging cables, sensor domes, lights,
hazard stripes, crooked repair patches with weld beads. Then it adds the
lived-in extras: thruster quads at the block corners, cargo crates strapped
to the decks, a hose coil, extra antennas.

Nothing is allowed to overlap anything else: every item is checked against
the existing greebles, the other modules, the decals and the sweep volumes of
the moving parts (radiators, dish, ramp, gear doors) before it is placed.
"""
import math
import random
import bmesh
from mathutils import Matrix, Vector
from . import geo, body as B

PAD = 0.03


class Occ:
    """Axis-aligned boxes already taken (world space, the hull sits at the origin)."""

    def __init__(self):
        self.boxes = []

    def add(self, lo, hi, pad=PAD):
        self.boxes.append((Vector(lo) - Vector((pad,) * 3), Vector(hi) + Vector((pad,) * 3)))

    def hit(self, lo, hi):
        for a, b in self.boxes:
            if all(lo[k] < b[k] and hi[k] > a[k] for k in range(3)):
                return True
        return False


def _islands(bm, faces):
    """AABBs of the connected pieces made of `faces`."""
    faces = set(faces)
    seen = set()
    out = []
    for f in faces:
        if f in seen:
            continue
        stack, lo, hi = [f], Vector((1e9,) * 3), Vector((-1e9,) * 3)
        seen.add(f)
        while stack:
            g = stack.pop()
            for v in g.verts:
                for k in range(3):
                    lo[k] = min(lo[k], v.co[k])
                    hi[k] = max(hi[k], v.co[k])
                for h in v.link_faces:
                    if h in faces and h not in seen:
                        seen.add(h)
                        stack.append(h)
        out.append((lo, hi))
    return out


def _inside_other(p, mods, own):
    for name, m in mods.items():
        if m is own:
            continue
        ys = (m.y_front, m.y_back)
        if not (min(ys) + 0.02 < p.y < max(ys) - 0.02):
            continue
        hw, zlo, zhi = m.p(p.y)[:3]
        if abs(p.x - m.cx) < hw - 0.02 and zlo + 0.02 < p.z < zhi - 0.02:
            return True
    return False


class Placer:
    def __init__(self, bm, mods, occ, rnd):
        self.bm, self.mods, self.occ, self.rnd = bm, mods, occ, rnd
        self.count = 0

    def frame(self, c, n):
        n = n.normalized()
        u = Vector((0, 1, 0))
        u = (u - n * u.dot(n))
        if u.length < 0.2:
            u = Vector((1, 0, 0)) - n * n.x
        u.normalize()
        v = n.cross(u).normalized()
        return u, v, n

    def fits(self, c, u, v, n, hu, hv, hn, own):
        corners = [c + u * a * hu + v * b * hv + n * h for a in (-1, 1) for b in (-1, 1) for h in (-0.01, hn)]
        lo = Vector([min(p[k] for p in corners) for k in range(3)])
        hi = Vector([max(p[k] for p in corners) for k in range(3)])
        if self.occ.hit(lo, hi):
            return None
        for p in corners:
            if _inside_other(p, self.mods, own):
                return None
        return lo, hi

    def take(self, box):
        self.occ.add(*box)
        self.count += 1

    # -- primitive in a local frame -------------------------------------------
    def box(self, c, u, v, n, du, dv, dn, su, sv, sn, mat, bev=0.0, spin=0.0):
        rot = Matrix((u, v, n)).transposed().to_4x4()
        if spin:
            rot = rot @ Matrix.Rotation(spin, 4, "Z")
        p = c + u * du + v * dv + n * dn
        before = len(self.bm.faces)
        geo.add_box(self.bm, p, (su, sv, sn), rot=rot, bevel=bev)
        B._mat_new(self.bm, before, mat)

    def cyl(self, c, u, v, n, a, b, r, mat, segs=8, r1=None):
        before = len(self.bm.faces)
        geo.add_cyl(self.bm, c + u * a[0] + v * a[1] + n * a[2], c + u * b[0] + v * b[1] + n * b[2], r,
                    r1=r1, segs=segs)
        B._mat_new(self.bm, before, mat)

    def pipe(self, pts, r, mat, segs=8):
        B.tube(self.bm, pts, r, segs=segs, mat=mat)


# ---------------------------------------------------------------------------
# items: each takes (P, c, u, v, n, hu, hv) and returns True if placed

def rivets(P, c, u, v, n, hu, hv, own):
    k = max(2, int(hu * 2 / 0.22))
    placed = False
    for side in (-1, 1):
        off = side * (hv - 0.07)
        box = P.fits(c + v * off, u, v, n, hu - 0.05, 0.03, 0.02, own)
        if not box:
            continue
        for i in range(k):
            a = -hu + 0.08 + (2 * hu - 0.16) * i / (k - 1)
            P.cyl(c, u, v, n, (a, off, -0.01), (a, off, 0.012), 0.017, B.DARK, segs=6)
        P.take(box)
        placed = True
    return placed


def access_plate(P, c, u, v, n, hu, hv, own):
    w, h = min(hu * 1.2, 0.7), min(hv * 1.2, 0.5)
    box = P.fits(c, u, v, n, w / 2, h / 2, 0.04, own)
    if not box:
        return False
    P.box(c, u, v, n, 0, 0, 0.005, w, h, 0.03, P.rnd.choice((B.PAINT, B.PAINT, B.PRIMER, B.ACCENT)), bev=0.008)
    for a in (-1, 1):
        for b in (-1, 1):
            P.cyl(c, u, v, n, (a * (w / 2 - 0.05), b * (h / 2 - 0.05), 0.0), (a * (w / 2 - 0.05), b * (h / 2 - 0.05), 0.03),
                  0.018, B.DARK, segs=6)
    P.box(c, u, v, n, w * 0.25, 0, 0.025, 0.12, 0.05, 0.02, B.DARK)
    P.take(box)
    return True


def small_vent(P, c, u, v, n, hu, hv, own):
    w, h = min(hu * 1.4, 0.8), min(hv * 1.2, 0.36)
    box = P.fits(c, u, v, n, w / 2 + 0.03, h / 2 + 0.03, 0.06, own)
    if not box:
        return False
    P.box(c, u, v, n, 0, 0, 0.005, w + 0.06, h + 0.06, 0.03, B.PAINT, bev=0.01)
    P.box(c, u, v, n, 0, 0, 0.012, w, h, 0.03, B.DARK)
    k = max(3, int(w / 0.07))
    for i in range(k):
        a = -w / 2 + w * (i + 0.5) / k
        P.box(c, u, v, n, a, 0, 0.03, 0.02, h - 0.02, 0.03, B.PAINT)
    P.take(box)
    return True


def conduit(P, c, u, v, n, hu, hv, own):
    L = hu * 0.9
    off = P.rnd.uniform(-hv * 0.4, hv * 0.4)
    box = P.fits(c + v * off, u, v, n, L, 0.08, 0.14, own)
    if not box:
        return False
    r = P.rnd.choice((0.035, 0.045, 0.055))
    h = r + 0.025
    p = lambda a, z: c + u * a + v * off + n * z
    P.pipe([p(-L, -0.03), p(-L + 0.05, h * 0.8), p(-L + 0.15, h), p(L - 0.15, h), p(L - 0.05, h * 0.8), p(L, -0.03)],
           r, P.rnd.choice((B.DARK, B.HEAT, B.RUBBER)))
    for a in (-L * 0.45, L * 0.45):
        P.box(c, u, v, n, a, off, h * 0.5, 0.05, 2 * r + 0.04, h + 0.02, B.DARK)
    P.take(box)
    return True


def grab_rail(P, c, u, v, n, hu, hv, own):
    L = min(hu * 1.6, 0.9)
    box = P.fits(c, u, v, n, L / 2 + 0.04, 0.05, 0.13, own)
    if not box:
        return False
    p = lambda a, z: c + u * a + n * z
    P.pipe([p(-L / 2, -0.02), p(-L / 2, 0.1), p(L / 2, 0.1), p(L / 2, -0.02)], 0.022,
           P.rnd.choice((B.ACCENT, B.DARK)), segs=8)
    for a in (-L / 2, L / 2):
        P.cyl(c, u, v, n, (a, 0, -0.01), (a, 0, 0.02), 0.045, B.DARK, segs=8)
    P.take(box)
    return True


def junction(P, c, u, v, n, hu, hv, own):
    w = 0.3
    a0 = -hu * 0.45
    box = P.fits(c + u * (a0 * 0.2), u, v, n, hu * 0.8, 0.2, 0.22, own)
    if not box:
        return False
    P.box(c, u, v, n, a0, 0, 0.09, w, 0.24, 0.2, P.rnd.choice((B.PRIMER, B.DARK, B.PAINT)), bev=0.02)
    P.box(c, u, v, n, a0, 0, 0.2, w * 0.6, 0.06, 0.03, B.DARK)
    a1 = hu * 0.6
    P.box(c, u, v, n, a1, 0, 0.04, 0.16, 0.16, 0.1, B.DARK, bev=0.01)
    pts = []
    for i in range(9):
        t = i / 8
        a = (a0 + w / 2) + (a1 - 0.08 - a0 - w / 2) * t
        sag = 0.11 - 0.07 * math.sin(math.pi * t)
        pts.append(c + u * a + n * sag)
    P.pipe(pts, 0.022, B.RUBBER, segs=6)
    P.take(box)
    return True


def dome(P, c, u, v, n, hu, hv, own):
    r = min(hu, hv, 0.22)
    box = P.fits(c, u, v, n, r + 0.02, r + 0.02, r * 0.8, own)
    if not box:
        return False
    m = Matrix((u, v, n)).transposed().to_4x4()
    before = len(P.bm.faces)
    geo.lathe(P.bm, [(r + 0.02, -0.01), (r + 0.02, 0.03), (r, 0.04), (r * 0.8, r * 0.5), (0.0, r * 0.7)], segs=16,
              mat=Matrix.Translation(c) @ m)
    B._mat_new(P.bm, before, P.rnd.choice((B.PAINT, B.DARK, B.GLASS)))
    P.take(box)
    return True


def light_box(P, c, u, v, n, hu, hv, own):
    box = P.fits(c, u, v, n, 0.16, 0.1, 0.1, own)
    if not box:
        return False
    P.box(c, u, v, n, 0, 0, 0.04, 0.3, 0.18, 0.09, B.DARK, bev=0.015)
    P.box(c, u, v, n, 0, 0, 0.085, 0.22, 0.1, 0.02, B.WHITE)
    P.take(box)
    return True


def hazard(P, c, u, v, n, hu, hv, own):
    w, h = min(hu * 1.5, 0.9), 0.14
    off = P.rnd.choice((-1, 1)) * (hv - 0.14)
    box = P.fits(c + v * off, u, v, n, w / 2, h / 2, 0.012, own)
    if not box:
        return False
    k = int(w / 0.09)
    for i in range(k):
        a = -w / 2 + w * (i + 0.5) / k
        P.box(c, u, v, n, a, off, 0.001, w / k * 0.98, h, 0.006, B.ACCENT if i % 2 else B.DARK,
              spin=0.0)
    P.take(box)
    return True


def patch(P, c, u, v, n, hu, hv, own):
    w, h = min(hu * 1.3, 0.8) * P.rnd.uniform(0.6, 1.0), min(hv * 1.3, 0.6) * P.rnd.uniform(0.6, 1.0)
    sp = P.rnd.uniform(-0.12, 0.12)
    box = P.fits(c, u, v, n, (w + h) / 2 * 0.75 + 0.03, (w + h) / 2 * 0.75 + 0.03, 0.035, own)
    if not box:
        return False
    P.box(c, u, v, n, 0, 0, 0.004, w, h, 0.02, P.rnd.choice((B.PRIMER, B.PRIMER, B.PAINT, B.DARK)), bev=0.004, spin=sp)
    rot = Matrix.Rotation(sp, 3, "Z")
    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        q = rot @ Vector((a * (w / 2 - 0.04), b * (h / 2 - 0.04), 0))
        P.cyl(c, u, v, n, (q.x, q.y, 0.0), (q.x, q.y, 0.024), 0.016, B.DARK, segs=6)
    # weld bead along one edge
    q0 = rot @ Vector((-w / 2, -h / 2 - 0.006, 0))
    q1 = rot @ Vector((w / 2, -h / 2 - 0.006, 0))
    P.cyl(c, u, v, n, (q0.x, q0.y, 0.004), (q1.x, q1.y, 0.004), 0.012, B.HEAT, segs=5)
    P.take(box)
    return True


def latches(P, c, u, v, n, hu, hv, own):
    placed = False
    for a in (-hu * 0.55, hu * 0.55):
        b = hv - 0.05
        box = P.fits(c + u * a + v * b, u, v, n, 0.06, 0.06, 0.04, own)
        if not box:
            continue
        P.box(c, u, v, n, a, b, 0.012, 0.1, 0.07, 0.03, B.DARK, bev=0.006)
        P.box(c, u, v, n, a, b - 0.02, 0.03, 0.04, 0.09, 0.012, B.HEAT)
        P.take(box)
        placed = True
    return placed


def antenna(P, c, u, v, n, hu, hv, own):
    hgt = P.rnd.uniform(0.5, 1.4)
    box = P.fits(c, u, v, n, 0.08, 0.08, hgt + 0.05, own)
    if not box:
        return False
    P.cyl(c, u, v, n, (0, 0, -0.01), (0, 0, 0.08), 0.06, B.DARK, segs=8)
    P.cyl(c, u, v, n, (0, 0, 0.08), (0, 0, hgt), 0.012, B.DARK, segs=6)
    P.cyl(c, u, v, n, (0, 0, hgt), (0, 0, hgt + 0.04), 0.025, B.NAV_R if P.rnd.random() < 0.3 else B.DARK, segs=8)
    P.take(box)
    return True


TOP = [(conduit, 3), (access_plate, 3), (small_vent, 2), (grab_rail, 2), (hazard, 1), (patch, 2), (dome, 1),
       (junction, 2), (latches, 2), (antenna, 1)]
SIDE = [(access_plate, 3), (small_vent, 3), (conduit, 3), (grab_rail, 1), (patch, 3), (junction, 2), (latches, 2),
        (light_box, 1), (hazard, 1)]
BOTTOM = [(access_plate, 2), (conduit, 3), (small_vent, 2), (patch, 2), (light_box, 1), (dome, 1)]


def _pick(rnd, table):
    tot = sum(w for _, w in table)
    r = rnd.uniform(0, tot)
    for f, w in table:
        r -= w
        if r <= 0:
            return f
    return table[-1][0]


# ---------------------------------------------------------------------------
def exclusions(occ):
    """Sweep volumes of moving parts and the spots of separate objects."""
    Z = [
        ((-4.3, -2.8, 1.75), (4.3, 3.4, 4.6)),          # radiators fold/stand
        ((-1.4, -7.8, 3.7), (1.4, -5.0, 5.6)),          # dish turns
        ((-2.9, -11.0, -3.6), (2.9, -4.5, -2.7)),       # belly ramp swing + bay edge
        ((-4.6, -14.3, -4.5), (-1.4, -10.5, -2.7)),     # main gear pods/doors L
        ((1.4, -14.3, -4.5), (4.6, -10.5, -2.7)),       # main gear pods/doors R
        ((-1.6, 8.0, -4.2), (1.6, 12.2, -2.2)),         # nose gear pod/doors
        ((-0.8, 16.3, -3.4), (0.8, 17.7, -2.4)),        # chin scanner
        ((-1.2, 18.6, -2.4), (1.2, 25.2, -1.7)),        # booms
        ((-7.3, -10.3, 0.15), (-5.3, -7.2, 1.15)),      # pylon L
        ((5.3, -10.3, 0.15), (7.3, -7.2, 1.15)),        # pylon R
        ((-2.0, -12.0, 3.7), (2.0, -11.2, 6.4)),        # masts
        ((-1.2, 10.3, 3.45), (1.2, 11.0, 5.15)),        # front spikes (on the gun hood)
        ((0.2, 0.1, -1.8), (0.7, 0.7, -1.4)),           # belly beacon
        ((-0.3, 5.7, 3.55), (0.3, 6.3, 3.95)),          # hood beacon
        ((-4.7, -14.4, -3.1), (4.7, -13.85, 3.1)),      # engine section joint (slides apart)
        ((-3.0, 4.2, 2.55), (3.0, 5.95, 4.1)),          # gun hood swings back over this
        ((-2.6, 5.4, 2.55), (2.6, 11.8, 3.8)),          # deck under the gun hood (turret bay)
        ((-3.05, 5.3, 2.55), (3.05, 11.9, 2.86)),       # gap along the hood skirts
        ((-3.5, -12.8, 2.95), (3.5, -4.2, 3.14)),       # spine rams, vents and the gap under the spine
        ((-0.3, -18.7, 2.5), (0.3, -18.1, 2.9)),        # tail strobe
        ((-4.0, -21.0, -2.6), (4.0, -18.8, 2.6)),       # engine bells
    ]
    for s in (1, -1):
        # engine guide rails and carriages along the engine section's flanks
        Z.append(((min(s * 3.85, s * 4.7), -17.0, 0.85), (max(s * 3.85, s * 4.7), -13.9, 1.65)))
        Z.append(((min(s * 3.85, s * 4.7), -17.0, -1.40), (max(s * 3.85, s * 4.7), -13.9, -0.60)))
        # canard fins: stowed along the cab side, swing out for landing
        Z.append(((min(s * 3.15, s * 6.7), 12.4, -1.25), (max(s * 3.15, s * 6.7), 17.8, -0.62)))
        # decals on the aft side, NO STEP on the fore side
        Z.append(((min(s * 4.5, s * 4.75), -10.3, -2.0), (max(s * 4.5, s * 4.75), -6.9, -0.4)))
        Z.append(((min(s * 3.95, s * 4.2), 8.0, 0.82), (max(s * 3.95, s * 4.2), 9.2, 1.08)))
    for lo, hi in Z:
        occ.add(lo, hi, pad=0.0)


def rcs(P, mods):
    """Thruster quads high on the block corners: a block with three nozzles."""
    spots = [("fore", 12.2), ("aft", -13.3), ("engine", -18.3), ("cab", 13.6)]
    for name, y in spots:
        m = mods[name]
        hw, zlo, zhi, rt = m.p(y)[:4]
        for s in (1, -1):
            n = Vector((s, 0, 0))
            c = Vector((s * hw, y, zhi - rt - 0.35))
            u, v, nn = P.frame(c, n)
            box = P.fits(c, u, v, nn, 0.3, 0.3, 0.42, m)
            if not box:
                continue
            P.box(c, u, v, nn, 0, 0, 0.12, 0.5, 0.5, 0.26, B.DARK, bev=0.03)
            for d, a in (((0, 0, 1), 0), ((1, 0, 0), 1), ((-1, 0, 0), 1), ((0, 1, 0), 1)):
                dd = u * d[0] + v * d[1] + nn * d[2]
                base = c + nn * 0.12 + dd * 0.25
                before = len(P.bm.faces)
                geo.add_cyl(P.bm, base - dd * 0.02, base + dd * 0.14, 0.05, r1=0.08, segs=10)
                B._mat_new(P.bm, before, B.HEAT)
            P.take(box)


def crates(P, mods):
    """Cargo strapped to the decks: the crew ran out of room inside."""
    spots = [("aft_top", (0.0, -9.2), (1.3, 0.9, 0.7)), ("engine", (1.75, -17.85), (0.9, 0.8, 0.6)),
             ("engine", (-1.65, -17.75), (0.8, 0.8, 0.8)), ("fore_top", (-1.1, 6.3), (0.8, 0.7, 0.5)),
             ("fore", (-3.1, 4.4), (0.9, 1.0, 0.6))]
    for name, (x, y), (sx, sy, sz) in spots:
        m = mods[name]
        zt = m.p(y)[2]
        c = Vector((x, y, zt))
        u, v, n = Vector((0, 1, 0)), Vector((-1, 0, 0)), Vector((0, 0, 1))
        box = P.fits(c, u, v, n, sy / 2 + 0.08, sx / 2 + 0.08, sz + 0.05, m)
        if not box:
            continue
        mat = P.rnd.choice((B.ACCENT, B.PRIMER, B.DARK))
        spin = P.rnd.uniform(-0.12, 0.12)
        P.box(c, u, v, n, 0, 0, sz / 2 - 0.005, sy, sx, sz, mat, bev=0.03, spin=spin)
        rot = Matrix.Rotation(spin, 3, "Z")
        for k in (-0.3, 0.3):
            q = rot @ Vector((k * sy, 0, 0))
            # strap over the top, hooked to deck cleats
            a = c + u * q.x + v * q.y
            side = rot @ Vector((0, sx / 2 + 0.012, 0))
            sd = u * side.x + v * side.y
            P.pipe([a - sd - n * 0.01, a - sd + n * (sz + 0.012), a + sd + n * (sz + 0.012), a + sd - n * 0.01],
                   0.015, B.RUBBER, segs=6)
            for sgn in (-1, 1):
                P.box(a + sd * sgn * 1.25, u, v, n, 0, 0, 0.02, 0.12, 0.12, 0.05, B.DARK)
        P.take(box)


def apply(bm, mods, rnd, density=1.0, base_faces=None):
    """base_faces: the faces of the modules themselves (before any greeble)."""
    occ = Occ()
    base = base_faces or set()
    gfaces = [f for f in bm.faces if f not in base]
    for lo, hi in _islands(bm, gfaces):
        occ.add(lo, hi, pad=0.02)
    exclusions(occ)
    P = Placer(bm, mods, occ, rnd)
    rcs(P, mods)
    crates(P, mods)
    items = []
    for name, m in mods.items():
        if name.startswith("pod") or name == "keel":
            continue
        for (ri, ci), f in m.grid.items():
            if not f.is_valid:
                continue
            items.append((m, f))
    rnd.shuffle(items)
    for m, f in items:
        f.normal_update()
        n = f.normal
        c = f.calc_center_median()
        vs = [v.co for v in f.verts]
        u, v, nn = P.frame(c, n)
        hu = max(abs((p - c).dot(u)) for p in vs) - 0.04
        hv = max(abs((p - c).dot(v)) for p in vs) - 0.04
        if hu < 0.12 or hv < 0.1:
            continue
        if nn.z > 0.85:
            table = TOP
        elif abs(nn.x) > 0.85:
            table = SIDE
        elif nn.z < -0.85:
            table = BOTTOM
        else:
            if rnd.random() < 0.7 * density:
                latches(P, c, u, v, nn, hu, hv, m) or rivets(P, c, u, v, nn, hu, hv, m)
            continue
        if rnd.random() < 0.82 * density:
            fn = _pick(rnd, table)
            fn(P, c, u, v, nn, hu, hv, m)
        if rnd.random() < 0.55 * density:
            rivets(P, c, u, v, nn, hu, hv, m)
    return P.count
