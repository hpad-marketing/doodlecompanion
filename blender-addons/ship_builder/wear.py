"""Wear and tear: the pass that makes a freshly built room look lived in.

    wear.apply(room, seed=1, amount=1.0)

Runs after a room is built. Everything is seeded, so one seed always gives the
same mess and a new seed rerolls it. `amount` scales how much happens (0 = off).

- Furniture built inside K.piece() is nudged and turned a little as one unit.
  A move is kept only if it creates no new collision with anything.
- Loose props get any heading, and the odd one is knocked over. Physics settles them.
- Wall panels: some sit proud, some sunk, a few slightly skewed. One hangs open on
  its hinge edge, and one is missing with cables spilling out. A taped-over crack
  goes on another.
- Ceiling fixtures drift in colour temperature. One is dead and one flickers
  (the flicker survives mood changes).
- Debris (nuts, washers, a loose bolt, paper, a rag, a spent cell) lies on the
  deck, mostly along the walls, touching nothing.
"""
import math
import random
import bpy
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

from . import kit as K
from . import mats as M

SKIP_NAMES = ("Fourth Wall", "Haze", "Planet", "Planet Ring")


# ---------------------------------------------------------------- collision
class Collider:
    """BVH collision against every solid object in a room (world space)."""

    def __init__(self, room):
        self.room = room
        self.dg = bpy.context.evaluated_depsgraph_get()
        self.local = {}   # name -> (verts in object space, polys)
        self.world = {}   # name -> (bvh, (min, max))
        for ob in self._objects():
            self._cache(ob)

    def _objects(self):
        seen = []

        def walk(c):
            for ob in c.objects:
                if ob.type in {"MESH", "CURVE", "FONT"} and not ob.get("sb_haze") and not ob.get("sb_fourth_wall") \
                        and not any(ob.name.startswith(s) for s in SKIP_NAMES) and (not ob.hide_render or ob.get("sb_ghost")):
                    seen.append(ob)
            for ch in c.children:
                walk(ch)
        walk(self.room.root)
        return seen

    def _cache(self, ob):
        ev = ob.evaluated_get(self.dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            return
        if me is None or not me.polygons:
            ev.to_mesh_clear()
            return
        verts = [v.co.copy() for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
        self.local[ob.name] = (verts, polys)
        self.world[ob.name] = self._build(ob.name, ob.matrix_world)

    def _build(self, name, mw):
        verts, polys = self.local[name]
        wv = [mw @ v for v in verts]
        lo = Vector((min(v.x for v in wv), min(v.y for v in wv), min(v.z for v in wv)))
        hi = Vector((max(v.x for v in wv), max(v.y for v in wv), max(v.z for v in wv)))
        return BVHTree.FromPolygons(wv, polys, epsilon=0.0), (lo, hi)

    def add(self, ob):
        bpy.context.view_layer.update()
        self.dg = bpy.context.evaluated_depsgraph_get()
        self._cache(ob)

    def forget(self, ob):
        self.local.pop(ob.name, None)
        self.world.pop(ob.name, None)

    @staticmethod
    def _boxes_touch(a, b, pad=0.001):
        return all(a[0][i] - pad <= b[1][i] and b[0][i] - pad <= a[1][i] for i in range(3))

    def pairs(self, names, mats=None):
        """Set of (mine, other) pairs that overlap. mats: proposed world matrices."""
        mats = mats or {}
        group = set(names)
        mine = {}
        for n in names:
            if n not in self.local:
                continue
            mine[n] = self._build(n, mats[n]) if n in mats else self.world[n]
        hits = set()
        for n, (bvh, box) in mine.items():
            for m, (obvh, obox) in self.world.items():
                if m in group or not self._boxes_touch(box, obox):
                    continue
                if bvh.overlap(obvh):
                    hits.add((n, m))
        return hits

    def commit(self, names, mats):
        for n in names:
            if n in self.local and n in mats:
                self.world[n] = self._build(n, mats[n])


# ---------------------------------------------------------------- helpers
def _try_move(col, obs, make_mats, tries=4):
    """Propose transforms (shrinking each try); keep the first that adds no collision."""
    names = [o.name for o in obs]
    before = col.pairs(names)
    for k in range(tries):
        mats = make_mats(1.0 / (1 + k))
        after = col.pairs(names, mats)
        if after <= before:
            roots = [o for o in obs if o.parent is None or o.parent not in obs]
            for o in roots:
                o.matrix_world = mats[o.name]
            col.commit(names, mats)
            return True
    return False


def _attached(room, panel):
    """Dressing that sits on a wall panel's face (bolts, vents), in its own slab."""
    inv = panel.matrix_world.inverted()
    hx, hy = panel.dimensions.x / 2, panel.dimensions.y / 2
    out = []
    for ob in room.dress.objects:
        p = inv @ ob.matrix_world.translation
        if abs(p.x) <= hx + 0.005 and abs(p.y) <= hy + 0.005 and -0.03 < p.z < 0.07:
            out.append(ob)
    return out


def _panels(room):
    return [o for o in room.shell.objects if " Panel" in o.name and o.type == "MESH"]


# ---------------------------------------------------------------- passes
def nudge_pieces(room, col, rng, amount):
    groups = {}
    for ob in room.root.all_objects:  # only this room: other rooms of a ship may already exist
        pid = ob.get("sb_piece")
        if pid and ob.name in col.local or (pid and ob.type in {"LIGHT", "EMPTY"}):
            groups.setdefault(pid, []).append(ob)
    moved = 0
    for pid, obs in sorted(groups.items()):
        shift = obs[0].get("sb_shift", 0.04) * amount
        yaw = math.radians(obs[0].get("sb_yaw", 3.0)) * amount
        if shift <= 0 and yaw <= 0:
            continue
        dx, dy = rng.uniform(-shift, shift), rng.uniform(-shift, shift)
        a = rng.uniform(-yaw, yaw)
        pts = [o.matrix_world.translation for o in obs]
        pivot = Vector((sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts), 0))

        def make(s, obs=obs, dx=dx, dy=dy, a=a, pivot=pivot):
            T = Matrix.Translation(Vector((dx * s, dy * s, 0)) + pivot) @ Matrix.Rotation(a * s, 4, "Z") @ Matrix.Translation(-pivot)
            return {o.name: T @ o.matrix_world for o in obs}
        moved += _try_move(col, obs, make)
    # cushions get sat on: each one shifts and turns a little on its own
    for ob in [o for o in bpy.data.objects if "Cushion" in o.name and o.name in col.local]:
        c = ob.matrix_world.translation.copy()
        dx, dy, a = rng.uniform(-0.025, 0.025) * amount, rng.uniform(-0.02, 0.02) * amount, math.radians(rng.uniform(-4, 4)) * amount

        def make(s, ob=ob, c=c, dx=dx, dy=dy, a=a):
            T = Matrix.Translation(c + Vector((dx * s, dy * s, 0))) @ Matrix.Rotation(a * s, 4, "Z") @ Matrix.Translation(-c)
            return {ob.name: T @ ob.matrix_world}
        _try_move(col, [ob], make)
    return moved


def scatter_props(room, col, rng, amount):
    props = [o for o in room.props.objects if o.get("sb_physics") == "prop" and o.parent is None]
    tipped = 0
    for ob in props:
        fam = [ob] + [c for c in ob.children_recursive]
        spin = rng.uniform(-math.pi, math.pi) * min(1.0, amount)
        dx, dy = rng.uniform(-0.03, 0.03) * amount, rng.uniform(-0.03, 0.03) * amount
        tip = tipped == 0 and "Can" in ob.name and rng.random() < 0.6 * amount
        c = ob.matrix_world.translation.copy()

        def make(s, fam=fam, spin=spin, dx=dx, dy=dy, tip=tip, c=c):
            T = Matrix.Translation(c + Vector((dx * s, dy * s, 0.0)))
            R = Matrix.Rotation(spin * s, 4, "Z")
            if tip and s == 1.0:
                # laid on its side and lifted clear; settle() drops it
                R = R @ Matrix.Rotation(math.radians(90), 4, "X")
                T = Matrix.Translation(c + Vector((dx, dy, 0.06)))
            return {o.name: T @ R @ Matrix.Translation(-c) @ o.matrix_world for o in fam}
        if _try_move(col, fam, make) and tip:
            tipped += 1
            ob["sb_knocked"] = 1
    return tipped


def panels(room, col, rng, amount):
    out = {"proud": 0, "skew": 0, "open": 0, "missing": 0, "tape": 0}
    pan = _panels(room)
    rng.shuffle(pan)
    tall = [p for p in pan if 0.9 < p.matrix_world.translation.z < 2.0 and p.dimensions.x > 0.5]
    # one panel off, cables spilling out
    if amount > 0.3 and tall:
        for p in tall[:6]:
            att = _attached(room, p)
            mw = p.matrix_world.copy()
            u, v, n = (mw.to_3x3() @ Vector(ax) for ax in ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
            c = mw.translation
            hy = p.dimensions.y / 2
            cabs = []
            mats_ = [room.pal["rubber"], M.plastic("SB Cable Red", (0.35, 0.03, 0.02, 1), 0.45),
                     M.plastic("SB Cable Yellow", (0.6, 0.42, 0.04, 1), 0.45)]
            for k in range(3):
                # out of the hole, over the lip, then hanging loose down the panel below
                x0 = rng.uniform(-0.3, 0.3) * p.dimensions.x
                dx = rng.uniform(-0.12, 0.12)
                drop = rng.uniform(0.08, 0.35)
                out_ = rng.uniform(0.1, 0.16)
                rel = [(x0, hy - 0.05, 0.0), (x0 + dx * 0.3, hy * 0.25, out_ * 0.5),
                       (x0 + dx * 0.6, -hy + 0.04, out_), (x0 + dx * 0.9, -hy - 0.12, out_ * 0.8),
                       (x0 + dx, -hy - 0.12 - drop, out_ * 0.7)]
                pts = [c + u * x + v * y + n * z for x, y, z in rel]
                cu = bpy.data.curves.new("Loose Cable", "CURVE")
                cu.dimensions = "3D"
                cu.bevel_depth = rng.choice((0.007, 0.01, 0.013))
                cu.bevel_resolution = 4
                cu.use_fill_caps = True
                sp = cu.splines.new("NURBS")
                sp.points.add(len(pts) - 1)
                for q, w in zip(sp.points, pts):
                    q.co = (*w, 1)
                sp.use_endpoint_u = True
                sp.order_u = 3
                sp.resolution_u = 16
                cb = bpy.data.objects.new("Loose Cable", cu)
                room.dress.objects.link(cb)
                cu.materials.append(mats_[k])
                cabs.append(cb)
            hidden = [p] + att
            for o in hidden:
                o.hide_render = o.hide_viewport = True
                col.forget(o)
            ok = True
            for cb in cabs:
                col.add(cb)
                if col.pairs([cb.name]):
                    ok = False
            if ok:
                for o in hidden:
                    o["sb_wear"] = "missing"
                out["missing"] = 1
                tall.remove(p)
                break
            for cb in cabs:
                col.forget(cb)
                bpy.data.objects.remove(cb)
            for o in hidden:
                o.hide_render = o.hide_viewport = False
                col._cache(o)
    # one panel hanging open on its hinge edge
    if amount > 0.3:
        for p in tall[:8]:
            att = _attached(room, p)
            fam = [p] + att
            mw = p.matrix_world.copy()
            side = rng.choice((-1, 1))
            hinge = mw @ Vector((side * p.dimensions.x / 2, 0, -p.dimensions.z / 2))
            axis = mw.to_3x3() @ Vector((0, 1, 0))
            ang = math.radians(rng.uniform(6, 11)) * side

            def make(s, fam=fam, hinge=hinge, axis=axis, ang=ang):
                T = Matrix.Translation(hinge) @ Matrix.Rotation(ang * s, 4, axis) @ Matrix.Translation(-hinge)
                return {o.name: T @ o.matrix_world for o in fam}
            if _try_move(col, fam, make, tries=2):
                p["sb_wear"] = "open"
                out["open"] = 1
                tall.remove(p)
                break
    # proud, sunk and skewed panels
    for p in pan:
        if p.get("sb_wear"):
            continue
        r = rng.random()
        if r < 0.22 * amount:
            fam = [p] + _attached(room, p)
            m3 = p.matrix_world.to_3x3()
            n = m3 @ Vector((0, 0, 1))
            sk = math.radians(rng.uniform(-0.7, 0.7)) if rng.random() < 0.45 else 0.0
            about_u = rng.random() < 0.5
            ax = m3 @ Vector((1, 0, 0) if about_u else (0, 1, 0))
            ext = p.dimensions.y / 2 if about_u else p.dimensions.x / 2
            # only ever proud of the backing, never sunk into it
            d = ext * math.sin(abs(sk)) + rng.uniform(0.001, 0.006)
            c = p.matrix_world.translation.copy()

            def make(s, fam=fam, n=n, d=d, sk=sk, ax=ax, c=c):
                T = Matrix.Translation(c + n * d * s) @ Matrix.Rotation(sk * s, 4, ax) @ Matrix.Translation(-c)
                return {o.name: T @ o.matrix_world for o in fam}
            if _try_move(col, fam, make, tries=2):
                p["sb_wear"] = "skew" if sk else "proud"
                out["skew" if sk else "proud"] += 1
    # a taped-over crack
    tape = M.plastic("SB Duct Tape", (0.3, 0.3, 0.29, 1), 0.62)
    for p in tall[:5]:
        if p.get("sb_wear") or amount < 0.3:
            continue
        mw = p.matrix_world
        u, v, n = (mw.to_3x3() @ Vector(ax) for ax in ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        face = mw.translation + n * (p.dimensions.z / 2 + 0.0012)
        off = u * rng.uniform(-0.15, 0.15) + v * rng.uniform(-0.1, 0.1)
        strips = []
        for k, a in enumerate((rng.uniform(25, 40), -rng.uniform(25, 40))):
            t = K.box("Repair Tape", (0.32, 0.05, 0.0015), face + off + n * 0.0016 * k, tape, room.dress, bevel=0.0004, segs=1)
            t.rotation_euler = (Matrix((u, v, n)).transposed() @ Matrix.Rotation(math.radians(a), 3, "Z")).to_euler()
            strips.append(t)
        ok = True
        for t in strips:
            col.add(t)
        for t in strips:
            hits = {m for _, m in col.pairs([t.name]) if m != p.name and m not in [s.name for s in strips]}
            if hits:
                ok = False
        if ok:
            out["tape"] = 1
            break
        for t in strips:
            col.forget(t)
            bpy.data.objects.remove(t)
    return out


def _diffuser_for(light, room):
    best, bd = None, 1e9
    for o in room.dress.objects:
        if o.name.startswith("Light Diffuser"):
            d = (o.matrix_world.translation - light.matrix_world.translation).length
            if d < bd:
                best, bd = o, d
    return best if bd < 0.1 else None


def flicker_pattern(rng, frames=600):
    """(frame, factor) keys: mostly on, with short stuttering dropouts."""
    keys, f = [(1, 1.0)], rng.randint(20, 60)
    while f < frames:
        for _ in range(rng.randint(2, 6)):
            keys.append((f, rng.choice((0.05, 0.15, 0.6, 0.02))))
            f += rng.randint(1, 3)
            keys.append((f, rng.choice((1.0, 0.85))))
            f += rng.randint(1, 2)
        f += rng.randint(40, 140)
    return keys


def _fcurves(action):
    if action is None:
        return []
    try:
        return list(action.fcurves)
    except AttributeError:  # Blender 5 layered actions
        out = []
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out.extend(bag.fcurves)
        return out


def write_flicker(owner, attr, base, keys):
    """Constant-step keys of base*factor on owner.attr. set_mood re-runs this,
    so a flickering tube still follows the mood's brightness."""
    for f, k in keys:
        setattr(owner, attr, base * k)
        owner.keyframe_insert(attr, frame=f)
    ad = owner.id_data.animation_data
    for fc in _fcurves(ad.action if ad else None):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"


def fixtures(room, rng, amount):
    lights = [o for o in room.lights.objects if o.type == "LIGHT" and o.get("sb_light") == "ceiling"]
    rng.shuffle(lights)
    out = {"dead": 0, "flicker": 0}
    for i, lo in enumerate(lights):
        dif = _diffuser_for(lo, room)
        warm = rng.uniform(-0.08, 0.08) * amount
        col = Vector(lo.get("sb_color", lo.data.color))
        col = Vector((min(1, col.x * (1 + warm)), col.y, min(1, col.z * (1 - warm))))
        lo.data.color = col
        lo["sb_color"] = list(col)
        if dif is None:
            continue
        m = dif.active_material.copy()
        m.name = f"{dif.active_material.name} #{i}"
        dif.active_material = m
        m["sb_color"] = list(col) + [1]
        nd = m.node_tree.nodes.get("SB_Emit")
        nd.inputs["Emission Color"].default_value = tuple(col) + (1,)
        if amount > 0.3 and i == 0 and len(lights) > 3:
            # dead tube: dark diffuser, light off for good
            lo["sb_energy"] = 0.0
            lo.data.energy = 0.0
            m["sb_strength"] = 0.0
            nd.inputs["Emission Strength"].default_value = 0.0
            nd.inputs["Base Color"].default_value = (0.35, 0.33, 0.3, 1)
            lo["sb_wear"] = "dead"
            out["dead"] = 1
        elif amount > 0.3 and i == 1:
            keys = flicker_pattern(rng)
            lo["sb_flicker"] = [k for kv in keys for k in kv]
            m["sb_flicker"] = lo["sb_flicker"]
            write_flicker(lo.data, "energy", lo["sb_energy"], keys)
            write_flicker(nd.inputs["Emission Strength"], "default_value", m.get("sb_strength", 5.0), keys)
            out["flicker"] = 1
    return out


def flicker_keys(flat):
    return [(int(flat[i]), float(flat[i + 1])) for i in range(0, len(flat), 2)]


def debris(room, col, rng, amount):
    W, D = room.W, room.D
    pal = room.pal
    paper = M.plastic("SB Paper", (0.5, 0.47, 0.4, 1), 0.85)
    rag = M.fabric("SB Rag", (0.12, 0.085, 0.05, 1), 0.3)
    cell = M.plastic("SB Spent Cell", (0.45, 0.2, 0.05, 1), 0.4)

    def nut(loc, yaw):
        return K.cyl("Loose Nut", 0.011, 0.009, loc + Vector((0, 0, 0.0047)), pal["dark_steel"], room.dress, verts=6, bevel=0.0012, rot=(0, 0, yaw))

    def washer(loc, yaw):
        return K.cyl("Loose Washer", 0.012, 0.002, loc + Vector((0, 0, 0.0012)), pal["steel"], room.dress, verts=24, bevel=0.0005)

    def bolt(loc, yaw):
        return K.cyl("Loose Bolt", 0.0055, 0.05, loc + Vector((0, 0, 0.0058)), pal["dark_steel"], room.dress, verts=12, bevel=0.001, rot=(math.radians(90), 0, yaw))

    def scrap(loc, yaw):
        return K.box("Paper Scrap", (0.1, 0.14, 0.0008), loc + Vector((0, 0, 0.0006)), paper, room.dress, bevel=0, segs=1, rot=(0, 0, yaw))

    def crumple(loc, yaw):
        return K.rounded("Crumpled Paper", (0.06, 0.055, 0.045), loc + Vector((0, 0, 0.0295)), paper, room.dress, soft=2, rot=(0, 0, yaw), wrinkle=0.012)

    def rag_(loc, yaw):
        return K.rounded("Oily Rag", (0.26, 0.18, 0.025), loc + Vector((0, 0, 0.0215)), rag, room.dress, soft=2, rot=(0, 0, yaw), wrinkle=0.015)

    def spent(loc, yaw):
        return K.cyl("Spent Cell", 0.016, 0.07, loc + Vector((0, 0, 0.0166)), cell, room.dress, verts=20, bevel=0.002, rot=(math.radians(90), 0, yaw))

    kinds = [nut, nut, washer, washer, bolt, scrap, crumple, spent, nut, washer, bolt, rag_, scrap]
    want = int(len(kinds) * amount)
    placed = 0
    for k in range(want):
        make = kinds[k % len(kinds)]
        for attempt in range(25):
            edge = rng.random()
            if edge < 0.75:  # along a wall
                wall = rng.choice(("back", "left", "right"))
                off = rng.uniform(0.14, 0.5)
                if wall == "back":
                    loc = Vector((rng.uniform(-W / 2 + 0.3, W / 2 - 0.3), D - off, 0))
                elif wall == "left":
                    loc = Vector((-W / 2 + off, rng.uniform(0.5, D - 0.3), 0))
                else:
                    loc = Vector((W / 2 - off, rng.uniform(0.5, D - 0.3), 0))
            else:
                loc = Vector((rng.uniform(-W / 2 + 0.4, W / 2 - 0.4), rng.uniform(0.4, D - 0.4), 0))
            ob = make(loc, rng.uniform(0, 6.283))
            col.add(ob)
            hits = {m for _, m in col.pairs([ob.name]) if not m.startswith("Deck")}
            if not hits:
                ob["sb_wear"] = "debris"
                placed += 1
                break
            col.forget(ob)
            bpy.data.objects.remove(ob)
    return placed


def apply(room, seed=1, amount=1.0):
    """Run every wear pass on a built room. Returns a small report dict."""
    if amount <= 0:
        return {}
    bpy.context.view_layer.update()
    rng = random.Random(seed * 7919 + len(room.name))
    col = Collider(room)
    rep = {
        "pieces_moved": nudge_pieces(room, col, rng, amount),
        "props_knocked": scatter_props(room, col, rng, amount),
        "panels": panels(room, col, rng, amount),
        "lights": fixtures(room, rng, amount),
        "debris": debris(room, col, rng, amount),
    }
    room.root["sb_wear_seed"] = seed
    room.root["sb_wear_amount"] = amount
    return rep
