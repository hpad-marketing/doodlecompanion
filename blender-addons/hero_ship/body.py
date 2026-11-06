"""Hull modules: chunky rounded blocks with real panel seams and greebles.

The ship is built like the reference sheet: stacked, rounded, panelled blocks
(cab, fore body, aft body, engine block), an open 'spine' between fore and aft
where the mechanics show (keel, tanks, pipes), side sponsons for the engine pods.

A module is a rounded-rectangle profile lofted along Y. Every quad of the loft
belongs to a panel; panels are inset as real seams. Greebles are added into the
same mesh, so they are welded to their module and never float.
"""
import math
import random
import bmesh
from mathutils import Matrix, Vector
from . import geo

# material slots shared by every ship object (see mats.SLOTS)
PAINT, DARK, GLOW, ACCENT, BAY, GLASS, RUBBER, HEAT, ENGINE, NAV_R, NAV_G, WHITE, PRIMER = range(13)

N_TOP, N_ARC, N_SIDE, N_BOT = 4, 5, 4, 3


def profile(hw, zlo, zhi, rt, rb, tuck=0.0):
    """Half profile from top centre clockwise (+X side) to bottom centre.
    Returns points and the column groups (start, end) for panelling."""
    pts = []
    for i in range(N_TOP + 1):
        pts.append(((hw - rt) * i / N_TOP, zhi))
    cx, cz = hw - rt, zhi - rt
    for i in range(1, N_ARC + 1):
        a = math.pi / 2 * (1 - i / N_ARC)
        pts.append((cx + rt * math.cos(a), cz + rt * math.sin(a)))
    x0, z0 = hw, zhi - rt
    x1, z1 = hw - tuck, zlo + rb
    for i in range(1, N_SIDE + 1):
        t = i / N_SIDE
        pts.append((x0 + (x1 - x0) * t, z0 + (z1 - z0) * t))
    cx, cz = hw - tuck - rb, zlo + rb
    for i in range(1, N_ARC + 1):
        a = -math.pi / 2 * i / N_ARC
        pts.append((cx + rb * math.cos(a), cz + rb * math.sin(a)))
    for i in range(1, N_BOT + 1):
        pts.append(((hw - tuck - rb) * (1 - i / N_BOT), zlo))
    return pts


def _col_marks():
    m = [0, N_TOP, N_TOP + N_ARC, N_TOP + N_ARC + N_SIDE, N_TOP + 2 * N_ARC + N_SIDE,
         N_TOP + 2 * N_ARC + N_SIDE + N_BOT]
    return m


HALF = N_TOP + 2 * N_ARC + N_SIDE + N_BOT     # segments on one half
RING = 2 * HALF                               # verts in a full ring


def ring(cx, y, prof, yfn=None):
    full = prof + [(-x, z) for x, z in reversed(prof[1:-1])]
    out = []
    for x, z in full:
        yy = y if yfn is None else yfn(x, z)
        out.append(Vector((cx + x, yy, z)))
    return out


def col_groups(rnd, split=True):
    m = _col_marks()
    halves = []
    for a, b in zip(m, m[1:]):
        if split and b - a >= 4 and rnd.random() < 0.6:
            k = a + (b - a) // 2
            halves += [(a, k), (k, b)]
        else:
            halves.append((a, b))
    out = list(halves)
    for a, b in halves:
        out.append((RING - b, RING - a))
    return out


class Module:
    """One rounded block. stations: [(y, hw, zlo, zhi, rt, rb, tuck)] front to back."""

    def __init__(self, bm, name, stations, cx=0.0, rnd=None, row_len=0.6, front_rake=0.0,
                 back_rake=0.0, cap_front=True, cap_back=True, livery=None, panel_seed=0,
                 mat=PAINT):
        self.bm = bm
        self.name = name
        self.cx = cx
        self.rnd = rnd or random.Random(panel_seed)
        self.mat = mat
        # resample stations into rows
        ys = []
        for (y0, *p0), (y1, *p1) in zip(stations, stations[1:]):
            n = max(1, int(round(abs(y1 - y0) / row_len)))
            for i in range(n):
                t = i / n
                ys.append((y0 + (y1 - y0) * t, [a + (b - a) * t for a, b in zip(p0, p1)]))
        ys.append((stations[-1][0], list(stations[-1][1:])))
        self.rows = ys
        self.y_front, self.y_back = ys[0][0], ys[-1][0]
        secs = []
        last = len(ys) - 1
        for i, (y, p) in enumerate(ys):
            prof = profile(*p)
            yfn = None
            if i == 0 and front_rake:
                zlo, zhi = p[1], p[2]
                yfn = (lambda x, z, y=y, zlo=zlo, zhi=zhi: y - front_rake * (z - zlo) / (zhi - zlo))
            if i == last and back_rake:
                zlo, zhi = p[1], p[2]
                yfn = (lambda x, z, y=y, zlo=zlo, zhi=zhi: y + back_rake * (z - zlo) / (zhi - zlo))
            secs.append(ring(cx, y, prof, yfn))
        self.rings = geo.loft(bm, secs)
        self.vidx = {v: (ri, ci) for ri, r in enumerate(self.rings) for ci, v in enumerate(r)}
        self.grid = {}
        for ri in range(len(self.rings) - 1):
            a, b = self.rings[ri], self.rings[ri + 1]
            for ci in range(RING):
                cj = (ci + 1) % RING
                for f in a[ci].link_faces:
                    if b[cj] in f.verts and a[cj] in f.verts:
                        self.grid[(ri, ci)] = f
        self.loft_faces = set(self.grid.values())
        self.caps = []
        if cap_front:
            self.caps.append(bm.faces.new(list(reversed(self.rings[0]))))
        if cap_back:
            self.caps.append(bm.faces.new(self.rings[-1]))
        self.livery = livery
        self.cut = set()

    def p(self, y):
        """Profile params at y (nearest row)."""
        best = min(self.rows, key=lambda r: abs(r[0] - y))
        return best[1]

    def faces_in(self, y0, y1, cols):
        out = []
        for (ri, ci), f in self.grid.items():
            ya, yb = self.rows[ri][0], self.rows[ri + 1][0]
            if min(ya, yb) >= y0 - 1e-4 and max(ya, yb) <= y1 + 1e-4 and ci in cols:
                out.append(f)
        return out

    def cut_belly(self, y0, y1, depth=1.6, full=False):
        """Removes the belly faces between y0..y1 (bottom flat) and returns
        (outline points of the removed faces, bay faces created)."""
        m = _col_marks()
        a = m[4] if full else m[4] + 1
        cols = set(range(a, m[5])) | set(range(RING - m[5], RING - a))
        faces = self.faces_in(y0, y1, cols)
        pts = [[tuple(v.co) for v in f.verts] for f in faces]
        fs = set(faces)
        edges = {e for f in faces for e in f.edges if sum(1 for lf in e.link_faces if lf in fs) == 1}
        bmesh.ops.delete(self.bm, geom=faces, context="FACES_ONLY")
        ext = bmesh.ops.extrude_edge_only(self.bm, edges=list(edges))
        nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(self.bm, vec=(0, 0, depth), verts=nv)
        ne = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMEdge) and all(v in nv for v in g.verts)]
        cap = bmesh.ops.holes_fill(self.bm, edges=ne, sides=0)
        bay = set(cap["faces"]) | {g for g in ext["geom"] if isinstance(g, bmesh.types.BMFace)}
        for f in bay:
            f.material_index = BAY
        self.loft_faces -= fs
        self.cut |= fs
        self.bay = bay
        return pts

    def finish(self, layers):
        """UVs, panels, cap insets, bevel weights."""
        bm, rnd = self.bm, self.rnd
        uv, pl, kl, bw = layers
        # UV: arc length around (seam on the belly centre) x length along
        n = RING
        arcs = []
        for r in self.rings:
            acc = [0.0]
            for i in range(n):
                acc.append(acc[-1] + (r[(i + 1) % n].co - r[i].co).length)
            arcs.append(acc)
        for (ri, ci), f in self.grid.items():
            if not f.is_valid:
                continue
            for l in f.loops:
                rr, cc = self.vidx[l.vert]
                a = arcs[rr][cc]
                if ci == n - 1 and cc == 0:
                    a = arcs[rr][n]
                a -= arcs[rr][n] * (HALF / n)
                l[uv].uv = (a * geo.UV_SCALE + self.cx * 0.37, l.vert.co.y * geo.UV_SCALE)
        for f in self.caps:
            for l in f.loops:
                l[uv].uv = ((l.vert.co.x) * geo.UV_SCALE, l.vert.co.z * geo.UV_SCALE + 2.0)
        # bevel weights on the cap rims (rounded block ends)
        for f in self.caps:
            for e in f.edges:
                e[bw] = 1.0
        # panels
        rows = len(self.rings) - 1
        groups = col_groups(rnd)
        panels = []
        for ca, cb in groups:
            r = 0
            while r < rows:
                ln = rnd.choice((2, 2, 3, 3, 4))
                rb = min(r + ln, rows)
                fs = [self.grid.get((ri, ci)) for ri in range(r, rb) for ci in range(ca, cb)]
                fs = [f for f in fs if f is not None and f.is_valid and f in self.loft_faces]
                if fs:
                    panels.append((r, ca, fs))
                r = rb
        for r, ca, fs in panels:
            pv = rnd.random()
            kind, depth = 0, rnd.uniform(-0.004, 0.004)
            roll = rnd.random()
            if roll < 0.10:
                kind, depth = 1, rnd.uniform(0.02, 0.035)
            elif roll < 0.17:
                kind, depth = 2, -rnd.uniform(0.02, 0.03)
            mat = self.mat
            if self.livery and self.livery(r, ca, fs, rnd):
                mat = ACCENT
            elif rnd.random() < 0.05:
                mat = PRIMER
            res = bmesh.ops.inset_region(bm, faces=fs, thickness=0.024, depth=depth,
                                         use_even_offset=True, use_boundary=True)
            for f in fs:
                f[pl] = pv
                f[kl] = kind
                f.material_index = mat
            for f in res["faces"]:
                f[pl] = -1.0
                f[kl] = 9
                f.material_index = mat
        # cap: framed end plate
        for f in self.caps:
            f.material_index = self.mat
            r1 = bmesh.ops.inset_individual(bm, faces=[f], thickness=0.22, depth=-0.03, use_even_offset=True)
            r2 = bmesh.ops.inset_individual(bm, faces=[f], thickness=0.05, depth=0.015, use_even_offset=True)
            f[pl] = rnd.random()
            for g in r1["faces"]:
                g[pl] = rnd.random()
                g.material_index = self.mat
            for g in r2["faces"]:
                g[pl] = -1.0
                g.material_index = self.mat


# ---------------------------------------------------------------------------
# greebles (added straight into a module's bmesh)

def _mat_new(bm, before, mat):
    for f in bm.faces:
        if f.index == -2:
            pass
    for f in set(bm.faces) - before:
        f.material_index = mat


def plate(bm, c, size, axis, mat, rot=0.0, bev=0.02):
    """Rounded plate centred at c lying on a face whose normal is ±axis."""
    before = set(bm.faces)
    sx, sy, sz = size
    m = Matrix.Rotation(rot, 4, axis.replace("-", ""))
    geo.add_box(bm, Vector(c), (sx, sy, sz), rot=m, bevel=bev)
    _mat_new(bm, before, mat)


def vent(bm, c, w, h, normal, slats=6, mat=DARK, frame_mat=PAINT):
    """A louvred vent on a side (normal 'x+','x-') or top ('z+') face."""
    c = Vector(c)
    before = set(bm.faces)
    if normal[0] == "x":
        s = 1 if normal[1] == "+" else -1
        geo.add_box(bm, c, (0.06, w + 0.12, h + 0.12), bevel=0.02)
        _mat_new(bm, before, frame_mat)
        before = set(bm.faces)
        geo.add_box(bm, c + Vector((s * 0.02, 0, 0)), (0.04, w, h))
        _mat_new(bm, before, mat)
        for i in range(slats):
            before = set(bm.faces)
            z = c.z - h / 2 + h * (i + 0.5) / slats
            geo.add_box(bm, Vector((c.x + s * 0.035, c.y, z)), (0.035, w - 0.04, h / slats * 0.45),
                        rot=Matrix.Rotation(s * math.radians(35), 4, "Y"))
            _mat_new(bm, before, frame_mat)
    else:
        geo.add_box(bm, c, (w + 0.12, h + 0.12, 0.06), bevel=0.02)
        _mat_new(bm, before, frame_mat)
        before = set(bm.faces)
        geo.add_box(bm, c + Vector((0, 0, 0.02)), (w, h, 0.04))
        _mat_new(bm, before, mat)
        for i in range(slats):
            before = set(bm.faces)
            y = c.y - h / 2 + h * (i + 0.5) / slats
            geo.add_box(bm, Vector((c.x, y, c.z + 0.035)), (w - 0.04, h / slats * 0.45, 0.035),
                        rot=Matrix.Rotation(math.radians(35), 4, "X"))
            _mat_new(bm, before, frame_mat)


def hatch(bm, c, w, h, normal, mat=PAINT):
    c = Vector(c)
    s = 1 if normal[1] == "+" else -1
    before = set(bm.faces)
    if normal[0] == "x":
        geo.add_box(bm, c, (0.05, w, h), bevel=0.03)
        _mat_new(bm, before, mat)
        before = set(bm.faces)
        geo.add_box(bm, c + Vector((s * 0.045, 0, h * 0.3)), (0.05, w * 0.35, 0.06), bevel=0.01)
        for dz in (-h * 0.35, h * 0.35):
            geo.add_cyl(bm, c + Vector((s * 0.03, -w / 2 - 0.01, dz - 0.12)),
                        c + Vector((s * 0.03, -w / 2 - 0.01, dz + 0.12)), 0.035, segs=8)
        _mat_new(bm, before, DARK)
    else:
        geo.add_box(bm, c, (w, h, 0.05), bevel=0.03)
        _mat_new(bm, before, mat)
        before = set(bm.faces)
        geo.add_box(bm, c + Vector((w * 0.3, 0, 0.045)), (0.06, h * 0.35, 0.05), bevel=0.01)
        _mat_new(bm, before, DARK)


def bolts_row(bm, p0, p1, n, normal, r=0.03):
    p0, p1 = Vector(p0), Vector(p1)
    nv = Vector(normal)
    before = set(bm.faces)
    for i in range(n):
        p = p0 + (p1 - p0) * (i / max(1, n - 1))
        geo.add_cyl(bm, p - nv * 0.01, p + nv * 0.025, r, segs=6)
    _mat_new(bm, before, DARK)


def strip(bm, pts, x, width=0.07, mat=GLOW, proud=0.012):
    """Glowing inlay line on a side wall at x (sign gives the side): pts=[(y,z)...]."""
    s = 1 if x > 0 else -1
    before = set(bm.faces)
    for (y0, z0), (y1, z1) in zip(pts, pts[1:]):
        a = Vector((x, y0, z0))
        b = Vector((x, y1, z1))
        d = b - a
        L = d.length + width
        ang = math.atan2(d.z, d.y)
        geo.add_box(bm, (a + b) / 2 + Vector((s * proud / 2, 0, 0)), (proud * 2, L, width),
                    rot=Matrix.Rotation(-ang, 4, "X") if False else Matrix.Rotation(ang, 4, "X"))
    _mat_new(bm, before, mat)


def tube(bm, pts, r, segs=10, mat=DARK):
    """Pipe through a polyline with mitred joints."""
    pts = [Vector(p) for p in pts]
    before = set(bm.faces)
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            t = (pts[1] - p).normalized()
        elif i == len(pts) - 1:
            t = (p - pts[i - 1]).normalized()
        else:
            t = ((p - pts[i - 1]).normalized() + (pts[i + 1] - p).normalized()).normalized()
        q = t.to_track_quat("Z", "Y")
        ring_ = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            ring_.append(bm.verts.new(p + q @ Vector((r * math.cos(a), r * math.sin(a), 0))))
        rings.append(ring_)
    for a, b in zip(rings, rings[1:]):
        for k in range(segs):
            j = (k + 1) % segs
            bm.faces.new((a[k], a[j], b[j], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    _mat_new(bm, before, mat)


def layers(bm):
    uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    pl = bm.faces.layers.float.get("panel") or bm.faces.layers.float.new("panel")
    kl = bm.faces.layers.int.get("panel_kind") or bm.faces.layers.int.new("panel_kind")
    bw = bm.edges.layers.float.get("bevel_weight_edge") or bm.edges.layers.float.new("bevel_weight_edge")
    return uv, pl, kl, bw


def uv_rest(bm, done):
    """World-scale box UVs for every face the module loft did not unwrap."""
    uv = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        if f in done:
            continue
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
            l[uv].uv = (u * geo.UV_SCALE, v * geo.UV_SCALE)


def finish_object(name, bm, c, parent, mats, done_faces, bevel_w=0.10):
    bm.normal_update()
    uv_rest(bm, done_faces)
    ob = geo.obj_from_bm(name, bm, c, parent=parent, mats=mats, uv=False, smooth_angle=40)
    mod = ob.modifiers.new("Bevel", "BEVEL")
    mod.limit_method = "WEIGHT"
    mod.width = bevel_w
    mod.segments = 3
    mod.harden_normals = False
    mod.use_clamp_overlap = True
    geo.weighted_normals(ob)
    return ob
