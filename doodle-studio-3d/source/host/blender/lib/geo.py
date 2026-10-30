"""Geometry: clean all-quad cages fitted to Doodle Studio's native volumes.

Every Doodle Studio part is a cloud of 3D points; the 2D app draws the convex
hull of each projected cloud. Here each part becomes a quad cage whose
Catmull-Clark limit surface sits on that hull (or on the union of hulls for
head+ears and for each leg), so a subdivision-surface modifier gives the same
silhouette from every angle.
"""
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

S = 0.125  # Doodle Studio unit -> metres (Bunny is ~1 m tall)


def part_points(rig, pid):
    p = rig['parts'][pid]
    if p.get('shape') == 'sphere':
        c = Vector(p['centre']) * S
        r = p['radius'] * S
        return sphere_points(c, r)
    return [Vector(v) * S for v in p['vertices']]


def sphere_points(c, r, n=24):
    out = []
    for i in range(n + 1):
        th = math.pi * i / n
        for j in range(2 * n):
            ph = math.pi * j / n
            out.append(c + Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th))) * r)
    return out


def hull_bmesh(points):
    bm = bmesh.new()
    for v in points:
        bm.verts.new(v)
    r = bmesh.ops.convex_hull(bm, input=bm.verts)
    junk = list({g for g in r['geom_interior'] + r['geom_unused'] if isinstance(g, bmesh.types.BMVert)})
    if junk:
        bmesh.ops.delete(bm, geom=junk, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def object_from_bmesh(name, bm, coll=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


class Target:
    """Closed surface used to fit cages (a hull or a union of hulls)."""

    def __init__(self, point_sets, voxel=None, name='target'):
        if len(point_sets) == 1 and voxel is None:
            bm = hull_bmesh(point_sets[0])
            self.bvh = BVHTree.FromBMesh(bm)
            self.bm = bm
            self.obj = None
            return
        objs = [object_from_bmesh(f'{name}_{i}', hull_bmesh(ps)) for i, ps in enumerate(point_sets)]
        base = objs[0]
        bpy.context.view_layer.objects.active = base
        for o in objs[1:]:
            m = base.modifiers.new('u', 'BOOLEAN')
            m.operation = 'UNION'
            m.object = o
            m.solver = 'EXACT'
            bpy.ops.object.modifier_apply(modifier=m.name)
            bpy.data.objects.remove(o)
        m = base.modifiers.new('r', 'REMESH')
        m.mode = 'VOXEL'
        m.voxel_size = voxel or 0.004
        bpy.ops.object.modifier_apply(modifier='r')
        bm = bmesh.new()
        bm.from_mesh(base.data)
        self.bvh = BVHTree.FromBMesh(bm)
        self.bm = bm
        self.obj = base
        base.name = name

    def nearest(self, p):
        hit = self.bvh.find_nearest(p)
        return hit[0] if hit and hit[0] is not None else p

    def inside(self, p):
        hit = self.bvh.find_nearest(p)
        if not hit or hit[0] is None:
            return False
        return (p - hit[0]).dot(hit[1]) < 0

    def ray(self, origin, direction):
        hit = self.bvh.ray_cast(origin, direction)
        return hit[0]

    def dispose(self):
        if self.obj:
            bpy.data.objects.remove(self.obj)
        self.bm.free()


def cube_sphere(n):
    """All-quad sphere: a subdivided cube pushed onto the unit sphere."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    if n > 1:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=n - 1, use_grid_fill=True)
    for v in bm.verts:
        # spherified cube (even spacing): map cube point to sphere
        x, y, z = v.co
        x2, y2, z2 = x * x, y * y, z * z
        v.co = Vector((x * math.sqrt(1 - y2 / 2 - z2 / 2 + y2 * z2 / 3),
                       y * math.sqrt(1 - z2 / 2 - x2 / 2 + z2 * x2 / 3),
                       z * math.sqrt(1 - x2 / 2 - y2 / 2 + x2 * y2 / 3)))
    bm.normal_update()
    return bm


def pca(points):
    a = np.array([tuple(p) for p in points])
    c = a.mean(0)
    u, s, vt = np.linalg.svd(a - c, full_matrices=False)
    sd = s / math.sqrt(len(a))
    R = Matrix([list(vt[0]), list(vt[1]), list(vt[2])]).transposed()  # columns = axes
    if R.determinant() < 0:
        R.col[2] = -R.col[2]
    return Vector(c), R, sd


def project_star(bm, target, centre, R, sd):
    """Place unit-sphere cage verts on the target by casting rays from the centre."""
    for v in bm.verts:
        u = v.co.normalized()
        local = Vector((u.x * sd[0], u.y * sd[1], u.z * sd[2]))
        d = (R @ local).normalized()
        hit = target.ray(centre, d)
        if hit is None:
            hit = target.nearest(centre + d)
        v.co = hit


def relax(bm, target, iters=10, factor=0.5, pin=None):
    """Tangential Laplacian relax + snap back to the target surface."""
    pin = pin or set()
    for _ in range(iters):
        new = {}
        for v in bm.verts:
            if v.index in pin:
                continue
            nb = [e.other_vert(v).co for e in v.link_edges]
            avg = sum(nb, Vector()) / len(nb)
            new[v] = v.co.lerp(avg, factor)
        for v, co in new.items():
            v.co = target.nearest(co)
        bm.normal_update()


def limit_bvh(ob, levels=3):
    m = ob.modifiers.new('_limit', 'SUBSURF')
    m.levels = levels
    m.render_levels = levels
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(ob.matrix_world)
    bvh = BVHTree.FromBMesh(bm)
    ev.to_mesh_clear()
    ob.modifiers.remove(m)
    return bvh, bm


def compensate_subsurf(ob, target, iters=5, levels=3, gain=1.0):
    """Push cage verts so the subdivided (limit) surface lands on the target."""
    mw = ob.matrix_world
    mwi = mw.inverted()
    for _ in range(iters):
        lbvh, lbm = limit_bvh(ob, levels)
        me = ob.data
        for v in me.vertices:
            w = mw @ v.co
            L = lbvh.find_nearest(w)[0]
            T = target.nearest(L)
            v.co = mwi @ (w + (T - L) * gain)
        lbm.free()
        me.update()


def max_error(ob, target, levels=3):
    lbvh, lbm = limit_bvh(ob, levels)
    err = 0.0
    for v in lbm.verts:
        err = max(err, (target.nearest(v.co) - v.co).length)
    lbm.free()
    return err


def fit_convex_part(name, points, n=6, coll=None, target=None, comp_iters=5):
    target = target or Target([points])
    c, R, sd = pca(points)
    bm = cube_sphere(n)
    project_star(bm, target, c, R, sd)
    relax(bm, target, iters=6, factor=0.4)
    ob = object_from_bmesh(name, bm, coll)
    bm.free()
    compensate_subsurf(ob, target, iters=comp_iters)
    return ob, target


def ear_frame(points):
    """Ear axis (root->tip), cross axes and length from its points."""
    c, R, sd = pca(points)
    a = R.col[0].copy()
    if a.z < 0:
        a = -a
    return c, a, sd


def build_head(rig, coll=None, n=8, ear_segments=8):
    head_pts = part_points(rig, 'p8')
    earL = part_points(rig, 'p2')
    earR = part_points(rig, 'p3')
    head_t = Target([head_pts])
    union = Target([head_pts, earL, earR], voxel=0.003, name='_head_union')
    c, R, sd = pca(head_pts)
    bm = cube_sphere(n)
    project_star(bm, head_t, c, Matrix.Identity(3), (1, 1, 1))
    relax(bm, head_t, iters=4, factor=0.3)
    bm.verts.ensure_lookup_table()
    ear_info = {}
    ear_verts = set()
    for side, pts in (('L', earL), ('R', earR)):
        ear_t = Target([pts])
        ec, a, esd = ear_frame(pts)
        proj = [(p - ec).dot(a) for p in pts]
        tip = ec + a * max(proj)
        root = head_t.ray(tip, -a) or head_t.nearest(ec)
        vc = min(bm.verts, key=lambda v: (v.co - root).length)
        faces = list(vc.link_faces)
        patch_c = vc.co.copy()
        length = (tip - root).length
        cur_faces = faces
        layers = []
        for k in range(ear_segments):
            res = bmesh.ops.extrude_face_region(bm, geom=cur_faces)
            new_v = [v for v in res['geom'] if isinstance(v, bmesh.types.BMVert)]
            new_f = [f for f in res['geom'] if isinstance(f, bmesh.types.BMFace)]
            bmesh.ops.delete(bm, geom=cur_faces, context='FACES')
            layers.append(new_v)
            cur_faces = new_f
        # cross-section frame
        ref = Vector((0, 1, 0))
        b1 = a.cross(ref).normalized()
        b2 = a.cross(b1).normalized()
        for k, layer in enumerate(layers):
            t = (k + 1) / ear_segments
            # ease the rings toward the tip so the cap stays round
            h = length * (1 - (1 - t) ** 1.0)
            for v in layer:
                if not v.is_valid:
                    continue
                off = v.co - patch_c
                off -= a * off.dot(a)
                if off.length < 1e-6:  # cap centre
                    v.co = tip
                    continue
                d = (b1 * off.dot(b1) + b2 * off.dot(b2)).normalized()
                if k == ear_segments - 1:
                    base = root + a * (length * 0.9)
                else:
                    base = root + a * h
                hit = ear_t.ray(base, d) or ear_t.nearest(base + d * 0.05)
                v.co = hit
                ear_verts.add(v)
        ear_t.dispose()
        ear_info[side] = dict(root=root, tip=tip, axis=a, centre=ec)
    bm.normal_update()
    bm.verts.ensure_lookup_table()
    pin = {v.index for v in ear_verts}
    relax(bm, union, iters=25, factor=0.5, pin=pin)
    # light relax of the ear rings along the union surface as well
    relax(bm, union, iters=6, factor=0.25)
    ob = object_from_bmesh('BUNNY_head', bm, coll)
    bm.free()
    compensate_subsurf(ob, union, iters=6)
    return ob, union, ear_info


# Walking leg under the hoodie (Doodle Studio units). The visible stub below the
# hem is Doodle Studio's foot volume exactly; above it the leg carries on as a
# full limb (thigh, knee, shin) up to a ball-and-socket hip on the pelvis.
LEG_HIP = (0.50, 0.0, 1.30)
LEG_KNEE = (0.545, -0.03, 0.96)
PELVIS = ((0.0, 0.0, 1.30), (0.80, 0.50, 0.30))
_HEM = 0.72


def _square_ring(n_side=4):
    """Boundary of an (n_side+1)^2 grid, counter-clockwise: matches a grid cap exactly."""
    k = n_side // 2
    pts = [(k, y) for y in range(-k, k)] + [(x, k) for x in range(k, -k, -1)] + \
          [(-k, y) for y in range(k, -k, -1)] + [(x, -k) for x in range(-k, k)]
    return pts, k


def _leg_profile(rig, pid, sx):
    """Rings (z, cx, cy, rx, ry) in DS units: DS foot volume to the hem, then the limb."""
    v = np.array(rig['parts'][pid]['vertices'])
    rings = []
    for z in (0.205, 0.24, 0.29, 0.35, 0.42, 0.50, 0.58, 0.65, _HEM):
        sl = v[np.abs(v[:, 2] - z) < 0.035]
        rings.append((z, (sl[:, 0].min() + sl[:, 0].max()) / 2, 0.0,
                      (sl[:, 0].max() - sl[:, 0].min()) / 2, (sl[:, 1].max() - sl[:, 1].min()) / 2))
    z0, cx0, _, rx0, ry0 = rings[-1]
    hx, hy, hz = LEG_HIP
    kx, ky, kz = LEG_KNEE
    # hidden limb: tapers gently from the stub into a thigh, never into a point
    for z, r in ((0.82, 0.95), (kz, 0.90), (1.10, 0.86), (1.22, 0.82), (hz, 0.78), (1.37, 0.66), (1.43, 0.42)):
        t = (z - z0) / (hz - z0)
        cx = cx0 + (sx * hx - cx0) * min(1.0, t)
        cy = (sx * 0 + ky) * max(0.0, 1 - abs(z - kz) / 0.25)
        rings.append((z, cx, cy, rx0 * r, ry0 * r))
    return rings


def build_leg(rig, side, coll=None):
    """All-quad leg: ringed limb with grid caps (flat sole, round hip ball)."""
    pid = 'p4' if side == 'L' else 'p5'
    sx = -1.0 if side == 'L' else 1.0
    rings = _leg_profile(rig, pid, sx)
    sq, k = _square_ring(4)
    dirs = [Vector((x, y, 0)).normalized() for x, y in sq]
    n = len(dirs)
    bm = bmesh.new()
    vr = []
    for z, cx, cy, rx, ry in rings:
        vr.append([bm.verts.new(Vector((cx + d.x * rx, cy + d.y * ry, z)) * S) for d in dirs])
    for a, b in zip(vr, vr[1:]):
        for i in range(n):
            bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))

    def cap(ring, z, cx, cy, rx, ry):
        grid = {}
        for i, (x, y) in enumerate(sq):
            grid[(x, y)] = ring[i]
        for x in range(-k + 1, k):
            for y in range(-k + 1, k):
                d = Vector((x, y, 0)) / k
                grid[(x, y)] = bm.verts.new(Vector((cx + d.x * rx * 0.8, cy + d.y * ry * 0.8, z)) * S)
        for x in range(-k, k):
            for y in range(-k, k):
                bm.faces.new((grid[(x, y)], grid[(x + 1, y)], grid[(x + 1, y + 1)], grid[(x, y + 1)]))
    z, cx, cy, rx, ry = rings[0]
    cap(vr[0], 0.20, cx, cy, rx, ry)
    z, cx, cy, rx, ry = rings[-1]
    cap(vr[-1], 1.45, cx, cy, rx, ry)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = object_from_bmesh(f'BUNNY_leg.{side}', bm, coll)
    bm.free()
    # the visible stub keeps Doodle Studio's foot silhouette after subdivision
    tgt = Target([part_points(rig, pid)])
    _compensate_below(ob, tgt, (_HEM - 0.02) * S)
    return ob, tgt


def _compensate_below(ob, target, zmax, iters=4, levels=3):
    mw, mwi = ob.matrix_world, ob.matrix_world.inverted()
    for _ in range(iters):
        lbvh, lbm = limit_bvh(ob, levels)
        for v in ob.data.vertices:
            w = mw @ v.co
            if w.z > zmax:
                continue
            L = lbvh.find_nearest(w)[0]
            v.co = mwi @ (w + (target.nearest(L) - L) * 0.8)
        lbm.free()
        ob.data.update()


TAIL = ((0.0, 0.93, 0.98), 0.17)


def build_tail(coll=None):
    """Round bunny tail on the back of the hoodie."""
    (cx, cy, cz), r = TAIL
    bm = cube_sphere(3)
    for v in bm.verts:
        v.co = (Vector((cx, cy, cz)) + v.co * r) * S
    ob = object_from_bmesh('BUNNY_tail', bm, coll)
    bm.free()
    return ob


def shade_under_hoodie(ob, mat_index=1, z=_HEM + 0.03):
    """Leg above the hem is in the hoodie's shadow: ink, so no crease reads from a low angle."""
    for f in ob.data.polygons:
        if f.center.z > z * S:
            f.material_index = mat_index


def build_pelvis(coll=None):
    """Hidden pelvis the hip balls sit in; gives the hoodie hem something to drape over."""
    (cx, cy, cz), (rx, ry, rz) = PELVIS
    bm = cube_sphere(4)
    for v in bm.verts:
        v.co = Vector((cx + v.co.x * rx, cy + v.co.y * ry, cz + v.co.z * rz)) * S
    ob = object_from_bmesh('BUNNY_pelvis', bm, coll)
    bm.free()
    return ob


def open_hem(ob, S_, cut=0.80):
    """Remove the hoodie's bottom cap so the legs come out of a real opening."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    drop = [f for f in bm.faces if f.normal.z < -0.55 and f.calc_center_median().z < cut * S_]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bm.to_mesh(ob.data)
    bm.free()
    return len(drop)
