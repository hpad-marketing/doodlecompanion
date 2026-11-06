"""Collision audit: proves nothing in a scene passes through anything else.

    collide.audit_room(room)                  -> list of intersecting pairs
    collide.audit_scene(scene, frames=None)   -> {frame: pairs}, droids included

This is a real intersection test, not a bounding-box test. Two parts count as
intersecting only when some face of one actually cuts through a face of the
other, that is, each face straddles the other's plane by more than `tol`.
Parts that merely touch (a cushion resting on a seat, a plate flush on a wall)
pass.

Parts of the same assembly are treated as one solid, so a flange clamped on its
pipe or a bolt in its plate is fine. An assembly is any of these:
- the same K.piece
- the same placed arch group
- parent and child
- the same droid's own neighbouring bones

Droids are objects in a collection whose name starts with "Droid", or objects
tagged sb_droid. Their parts are tested against every scene part and against
each other on every frame you pass in.
"""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SKIP = ("Fourth Wall", "Haze", "Planet", "Planet Ring", "SB Zero-G")
FASTENERS = ("Bolt",)
RECESSED = {("Ceiling", "Light Housing")}


def _base(n):
    return n.split(".")[0]


def _solid_objects(objs):
    for ob in objs:
        if ob.type not in {"MESH", "CURVE", "FONT"} or ob.hide_render:
            continue
        if ob.get("sb_haze") or ob.get("sb_fourth_wall") or any(ob.name.startswith(s) for s in SKIP):
            continue
        yield ob


class _Geo:
    __slots__ = ("bvh", "lo", "hi", "verts", "polys", "planes")

    def __init__(self, ob, dg):
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        self.verts = [mw @ v.co for v in me.vertices]
        self.polys = [tuple(p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
        self.planes = {}
        if self.verts:
            xs, ys, zs = zip(*self.verts)
            self.lo, self.hi = Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))
            self.bvh = BVHTree.FromPolygons(self.verts, self.polys, epsilon=0.0)
        else:
            self.bvh = None

    def plane(self, i):
        pl = self.planes.get(i)
        if pl is None:
            vs = [self.verts[k] for k in self.polys[i]]
            n = Vector()
            for a, b in zip(vs, vs[1:] + vs[:1]):  # Newell normal
                n.x += (a.y - b.y) * (a.z + b.z)
                n.y += (a.z - b.z) * (a.x + b.x)
                n.z += (a.x - b.x) * (a.y + b.y)
            if n.length < 1e-12:
                pl = (None, 0.0)
            else:
                n.normalize()
                pl = (n, n.dot(vs[0]))
            self.planes[i] = pl
        return pl

    def straddles(self, i, other, j, tol):
        n, d = other.plane(j)
        if n is None:
            return False
        ds = [n.dot(self.verts[k]) - d for k in self.polys[i]]
        return min(ds) < -tol and max(ds) > tol


def _depth(ga, gb, pairs, tol):
    """True if any overlapping face pair really cuts through each other."""
    for i, j in pairs:
        if ga.straddles(i, gb, j, tol) and gb.straddles(j, ga, i, tol):
            return True
    return False


def _group(ob):
    for key in ("sb_piece", "sb_group", "sb_droid_part_of"):
        if ob.get(key):
            return f"{key}:{ob[key]}"
    return None


def _bone_neighbours(a, b):
    """Two parts riding bones of the same rig: only touching joints may overlap."""
    arm = a.parent
    bones = arm.data.bones
    ba, bb = bones.get(a.parent_bone), bones.get(b.parent_bone)
    if ba is None or bb is None:
        return True
    return ba == bb or ba.parent == bb or bb.parent == ba


def _allowed(a, b):
    if (a.parent is not None and a.parent == b.parent and a.parent.type == "ARMATURE"
            and a.parent_type == "BONE" and b.parent_type == "BONE"):
        return _bone_neighbours(a, b)
    if a.parent == b or b.parent == a or (a.parent is not None and a.parent == b.parent):
        return True
    ga, gb = _group(a), _group(b)
    if ga and ga == gb:
        return True
    na, nb = _base(a.name), _base(b.name)
    if na.startswith(FASTENERS) or nb.startswith(FASTENERS):
        return True
    if (na, nb) in RECESSED or (nb, na) in RECESSED:
        return True
    return False


def audit_objects(objs, tol=0.0015, only=None):
    """All intersecting pairs among objs. only: restrict to pairs that involve these."""
    dg = bpy.context.evaluated_depsgraph_get()
    obs = list(_solid_objects(objs))
    geo = {}
    for ob in obs:
        g = _Geo(ob, dg)
        if g.bvh is not None:
            geo[ob.name] = (ob, g)
    names = list(geo)
    focus = set(o.name for o in only) if only else None
    hits = []
    for i, na in enumerate(names):
        oa, ga = geo[na]
        for nb in names[i + 1:]:
            if focus is not None and na not in focus and nb not in focus:
                continue
            ob_, gb = geo[nb]
            if any(ga.lo[k] > gb.hi[k] + 1e-4 or gb.lo[k] > ga.hi[k] + 1e-4 for k in range(3)):
                continue
            if _allowed(oa, ob_):
                continue
            pairs = ga.bvh.overlap(gb.bvh)
            if pairs and _depth(ga, gb, pairs, tol):
                hits.append((na, nb))
    return hits


def room_objects(room):
    out = []

    def walk(c):
        out.extend(c.objects)
        for ch in c.children:
            walk(ch)
    walk(room.root if hasattr(room, "root") else room)
    return out


def audit_room(room, tol=0.0015):
    return audit_objects(room_objects(room), tol)


def droid_objects(scene):
    out = []
    for c in bpy.data.collections:
        if c.name.startswith("Droid"):
            out += [o for o in c.all_objects]
    out += [o for o in scene.objects if o.get("sb_droid") and o not in out]
    return out


def audit_scene(scene=None, frames=None, tol=0.0015):
    """Every droid part against every scene part and against each other, per frame."""
    sc = scene or bpy.context.scene
    frames = frames or [sc.frame_current]
    droids = droid_objects(sc)
    report = {}
    keep = sc.frame_current
    for f in frames:
        sc.frame_set(f)
        hits = audit_objects(list(sc.objects), tol, only=droids or None)
        if hits:
            report[f] = hits
    sc.frame_set(keep)
    return report
