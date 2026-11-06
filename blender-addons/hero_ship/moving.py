"""Moving hull sections and the pop-up gun.

Big pieces of the hull itself move, so the ship changes shape in a preset:

    engine section   slides back on the warp ("engine_extend"), a glowing drive core shows in the gap
    dorsal spine     rises on four rams to dump heat ("spine_lift"), dish and masts ride along
    gun hood         swings up and back ("guns"), a twin-barrel turret rises, aims ("gun_yaw",
                     "gun_pitch") and fires with recoil and muzzle flash ("gun_fire")
    canards          fins swing out from the cab sides for an atmospheric approach ("canards")

The sections are cut out of the finished Hull by mesh island, so every rivet, vent and crate on
a section travels with it. Rest positions leave a small air gap to the hull: nothing overlaps
when stowed, so the collision audit checks these pieces against everything else.
"""
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from . import geo
from . import body as B
from .parts import drv, _part, _mat
from .layout import HOOD_Z, HOOD_DEPTH, SPINE_Z, ENGINE_Y0

ENGINE_TRAVEL = 1.6      # m the engine section slides back
SPINE_TRAVEL = 0.9       # m the spine rises
HOOD_OPEN_DEG = 78.0     # hood swings up and back
TURRET = (0.0, 7.6)      # turret axis (x, y) on the fore deck
TURRET_BASE = 2.648    # turret base plate height (clears the raised deck panels)
TURRET_RISE = 0.95
CANARD = {"y": 16.4, "z": -0.93, "span": 2.6, "chord": 1.25}

# gating: hood opens over the first 45 % of "guns", the turret rises over the rest,
# aiming only works once it is up
HOOD_EXPR = "min(max(g/0.45,0),1)"
RISE_EXPR = "min(max((g-0.4)/0.55,0),1)"
AIM_GATE = "min(max((g-0.9)/0.1,0),1)"


# ---------------------------------------------------------------------------
def _islands(me):
    """Union-find on mesh vertices -> per-vertex island root, per-root bbox."""
    n = len(me.vertices)
    par = list(range(n))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    ev = [0] * (len(me.edges) * 2)
    me.edges.foreach_get("vertices", ev)
    for k in range(0, len(ev), 2):
        a, b = find(ev[k]), find(ev[k + 1])
        if a != b:
            par[a] = b
    co = [0.0] * (n * 3)
    me.vertices.foreach_get("co", co)
    roots = [find(i) for i in range(n)]
    box = {}
    for i, r in enumerate(roots):
        x, y, z = co[3 * i], co[3 * i + 1], co[3 * i + 2]
        b = box.get(r)
        if b is None:
            box[r] = [x, y, z, x, y, z]
        else:
            if x < b[0]: b[0] = x
            if y < b[1]: b[1] = y
            if z < b[2]: b[2] = z
            if x > b[3]: b[3] = x
            if y > b[4]: b[4] = y
            if z > b[5]: b[5] = z
    return roots, box


def _group_of(b):
    lo, hi = Vector(b[:3]), Vector(b[3:])
    c = (lo + hi) * 0.5
    if hi.y < ENGINE_Y0 + 0.035:
        return "engine"
    if lo.z > SPINE_Z - 0.03 and abs(c.x) < 3.3 and -13.0 < c.y < -4.0:
        return "spine"
    if lo.z > HOOD_Z - 0.012 and abs(c.x) < 2.9 and 4.8 < c.y < 12.4 and lo.z < 4.5:
        return "hood"
    return None


def split_hull(hull):
    """Returns {group: new object} with the hull's islands for each moving section."""
    me = hull.data
    roots, box = _islands(me)
    gid = {r: _group_of(b) for r, b in box.items()}
    vgroup = [gid[r] for r in roots]
    out = {}
    names = {"engine": "Engine Section", "spine": "Dorsal Spine", "hood": "Gun Hood"}
    for g, nm in names.items():
        ob = hull.copy()
        ob.data = me.copy()
        ob.name = ob.data.name = nm
        for col in hull.users_collection:
            col.objects.link(ob)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if vgroup[v.index] != g], context="VERTS")
        bm.to_mesh(ob.data)
        bm.free()
        ob["sb_piece"] = "hs_" + g
        ob["hs_part"] = g
        out[g] = ob
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if vgroup[v.index] is not None], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    return out


def _attach(ob, piv):
    """Re-parent a static body-space object under a pivot without moving it."""
    mw = ob.matrix_basis.copy()
    ob.parent = piv
    ob.matrix_parent_inverse = piv.matrix_basis.inverted()
    ob.matrix_basis = mw


def _bbox(ob):
    v = [ob.matrix_basis @ p.co for p in ob.data.vertices]
    return Vector((min(p.x for p in v), min(p.y for p in v), min(p.z for p in v))), \
        Vector((max(p.x for p in v), max(p.y for p in v), max(p.z for p in v)))


# ---------------------------------------------------------------------------
def engine_section(c, body, root, mats, sect):
    piv = geo.empty("Engine Section Slide", c, body, (0, 0, 0), "SINGLE_ARROW", 1.5)
    drv(piv, "location", "-%.3f*e" % ENGINE_TRAVEL, root, {"e": "engine_extend"}, 1)
    _attach(sect, piv)
    for nm in ("Main Engines", "Engine Glow", "Plume Main 0", "Plume Main 1", "Plume Main 2", "Beacon 2"):
        ob = bpy.data.objects.get(nm)
        if ob:
            _attach(ob, piv)
            if nm in ("Main Engines", "Engine Glow"):
                ob["sb_piece"] = "hs_engine"
    # drive core on the aft block's back face: shows in the gap as the section slides away
    bm = bmesh.new()
    rot = Matrix.Rotation(math.pi / 2, 4, "X")
    y0 = -14.032
    geo.add_cyl(bm, (0, y0, 0.12), (0, y0 - 0.018, 0.12), 2.25, segs=48)
    _mat(bm, set(), B.DARK)
    b0 = len(bm.faces)
    geo.add_cyl(bm, (0, y0 - 0.018, 0.12), (0, y0 - 0.026, 0.12), 1.85, segs=48)
    _mat(bm, b0, B.GLOW)
    for k in range(8):  # spokes
        a = k * math.pi / 4
        p = Vector((math.cos(a) * 1.05, y0 - 0.03, 0.12 + math.sin(a) * 1.05))
        b0 = len(bm.faces)
        geo.add_box(bm, p, (0.16, 0.012, 0.16), rot=Matrix.Rotation(a, 4, "Y"))
        _mat(bm, b0, B.DARK)
    core = _part("Drive Core", bm, c, body, mats, "hs_airframe")
    core["hyper"] = 0.0
    drv(core, '["hyper"]', "max(h,e*0.35)", root, {"h": "hyper", "e": "engine_extend"})
    return piv


def spine(c, body, root, mats, sect):
    piv = geo.empty("Dorsal Spine Lift", c, body, (0, -8.5, SPINE_Z), "SINGLE_ARROW", 1.5)
    drv(piv, "location", "%.3f+%.3f*s" % (SPINE_Z, SPINE_TRAVEL), root, {"s": "spine_lift"}, 2)
    _attach(sect, piv)
    for nm in ("Spine Masts", "Dish Pivot", "Beacon 0", "Beacon 1"):
        ob = bpy.data.objects.get(nm)
        if ob:
            _attach(ob, piv)
    # heat vent grille on the deck under the spine (glows as it lifts)
    bm = bmesh.new()
    geo.add_box(bm, Vector((0, -8.45, 3.0065)), (4.5, 6.9, 0.009))
    _mat(bm, set(), B.DARK)
    for k in range(17):
        y = -11.6 + k * 0.4
        b0 = len(bm.faces)
        geo.add_box(bm, Vector((0, y, 3.0125)), (4.1, 0.14, 0.004))
        _mat(bm, b0, B.GLOW)
    vg = _part("Spine Vents", bm, c, body, mats, "hs_airframe")
    vg["hyper"] = 0.0
    drv(vg, '["hyper"]', "max(h*0.6,s*0.8)", root, {"h": "hyper", "s": "spine_lift"})
    # four rams: grow with the lift (scaled from their base on the vent grille)
    for i, (x, y) in enumerate(((1.75, -5.6), (-1.75, -5.6), (1.75, -11.3), (-1.75, -11.3))):
        bm = bmesh.new()
        geo.add_cyl(bm, (0, 0, 0), (0, 0, 1.0), 0.11, segs=14)
        _mat(bm, set(), B.DARK)
        ram = _part(f"Spine Ram {i}", bm, c, body, mats, "hs_spine_ram")
        ram.location = (x, y, 3.0155)
        drv(ram, "scale", "0.001+%.3f*s" % SPINE_TRAVEL, root, {"s": "spine_lift"}, 2)
        ram.scale[2] = 0.001
    return piv


def gun_hood(c, body, root, mats, sect):
    lo, hi = _bbox(sect)
    # hinge axis runs through the knuckles, just behind and above the hood's back-bottom edge
    hinge = (0.0, lo.y - 0.07, HOOD_Z + 0.07)
    piv = geo.empty("Gun Hood Hinge", c, body, hinge, "SINGLE_ARROW", 1.2)
    piv.rotation_mode = "XYZ"
    drv(piv, "rotation_euler", "%.5f*%s" % (math.radians(HOOD_OPEN_DEG), HOOD_EXPR), root, {"g": "guns"}, 0)
    _attach(sect, piv)
    for nm in ("Hood Spikes", "Beacon 4"):
        ob = bpy.data.objects.get(nm)
        if ob:
            _attach(ob, piv)
    # hinge knuckles at the back edge
    bm = bmesh.new()
    for x in (-1.6, 0.0, 1.6):
        geo.add_cyl(bm, (x - 0.3, hinge[1], hinge[2]), (x + 0.3, hinge[1], hinge[2]), 0.06, segs=12)
    _mat(bm, set(), B.DARK)
    _part("Gun Hood Knuckles", bm, c, piv, mats, "hs_hood").location = (-hinge[0], -hinge[1], -hinge[2])
    return piv


def turret(c, body, root, mats):
    x0, y0 = TURRET
    # lift column (static, grows) and the rising turret
    bm = bmesh.new()
    geo.add_cyl(bm, (0, 0, 0), (0, 0, 1.0), 0.30, segs=24)
    _mat(bm, set(), B.DARK)
    col = _part("Turret Column", bm, c, body, mats, "hs_turret")
    col.location = (x0, y0, TURRET_BASE)
    drv(col, "scale", "0.001+%.3f*%s" % (TURRET_RISE, RISE_EXPR), root, {"g": "guns"}, 2)
    col.scale[2] = 0.001
    lift = geo.empty("Turret Lift", c, body, (x0, y0, TURRET_BASE), "SINGLE_ARROW", 0.8)
    drv(lift, "location", "%.4f+%.3f*%s" % (TURRET_BASE, TURRET_RISE, RISE_EXPR), root, {"g": "guns"}, 2)
    yaw = geo.empty("Turret Yaw", c, lift, (0, 0, 0), "PLAIN_AXES", 0.6)
    yaw.rotation_mode = "XYZ"
    drv(yaw, "rotation_euler", "-y*0.01745329*" + AIM_GATE, root, {"y": "gun_yaw", "g": "guns"}, 2)
    # head: base ring, armoured body, cheek ammo boxes, sensor block
    bm = bmesh.new()
    geo.add_cyl(bm, (0, 0, 0.004), (0, 0, 0.12), 0.62, segs=32)
    _mat(bm, set(), B.DARK)
    b0 = len(bm.faces)
    geo.add_box(bm, Vector((0, -0.05, 0.33)), (1.55, 1.75, 0.42), bevel=0.07)
    geo.add_box(bm, Vector((0, 0.78, 0.27)), (1.30, 0.36, 0.28), rot=Matrix.Rotation(math.radians(-28), 4, "X"),
                bevel=0.04)
    _mat(bm, b0, B.PAINT)
    b0 = len(bm.faces)
    geo.add_box(bm, Vector((0, -0.2, 0.565)), (1.2, 1.1, 0.05), bevel=0.015)
    _mat(bm, b0, B.ACCENT)
    b0 = len(bm.faces)
    for s in (1, -1):
        geo.add_box(bm, Vector((s * 0.89, -0.15, 0.30)), (0.24, 1.15, 0.32), bevel=0.03)
        geo.add_cyl(bm, (s * 0.89, -0.76, 0.30), (s * 0.89, -0.86, 0.30), 0.07, segs=10)
    geo.add_box(bm, Vector((0.42, -0.42, 0.66)), (0.28, 0.34, 0.15), bevel=0.02)
    _mat(bm, b0, B.DARK)
    b0 = len(bm.faces)
    geo.add_cyl(bm, (0.42, -0.25, 0.66), (0.42, -0.23, 0.66), 0.05, segs=12)
    _mat(bm, b0, B.GLASS)
    b0 = len(bm.faces)
    for k in range(5):
        geo.add_cyl(bm, (-0.45, -0.55 + k * 0.12, 0.592), (-0.45, -0.55 + k * 0.12, 0.60), 0.02, segs=6)
    _mat(bm, b0, B.DARK)
    _part("Turret Head", bm, c, yaw, mats, "hs_turret", bevel=0.0)
    # pitch trunnion and mantlet
    pitch = geo.empty("Turret Pitch", c, yaw, (0, 0.72, 0.32), "PLAIN_AXES", 0.4)
    pitch.rotation_mode = "XYZ"
    drv(pitch, "rotation_euler", "p*0.01745329*" + AIM_GATE, root, {"p": "gun_pitch", "g": "guns"}, 0)
    bm = bmesh.new()
    geo.add_cyl(bm, (-0.7, 0, 0), (0.7, 0, 0), 0.10, segs=14)
    geo.add_box(bm, Vector((0, 0.16, 0)), (1.05, 0.22, 0.32), bevel=0.04)
    _mat(bm, set(), B.DARK)
    _part("Turret Mantlet", bm, c, pitch, mats, "hs_turret")
    from .presets import _fx_mat
    for s, side in ((1, "R"), (-1, "L")):
        rec = geo.empty(f"Barrel Recoil {side}", c, pitch, (s * 0.32, 0.27, 0), "SINGLE_ARROW", 0.3)
        drv(rec, "location", "0.27-0.26*f", root, {"f": "gun_fire"}, 1)
        bm = bmesh.new()
        geo.add_cyl(bm, (0, -0.05, 0), (0, 0.55, 0), 0.12, segs=16)
        geo.add_cyl(bm, (0, 0.55, 0), (0, 2.22, 0), 0.068, segs=14)
        for k in range(5):
            yy = 0.8 + k * 0.27
            geo.add_cyl(bm, (0, yy, 0), (0, yy + 0.07, 0), 0.08, segs=14)
        _mat(bm, set(), B.DARK)
        b0 = len(bm.faces)
        geo.add_cyl(bm, (0, 2.18, 0), (0, 2.46, 0), 0.10, segs=14)
        _mat(bm, b0, B.HEAT)
        _part(f"Gun Barrel {side}", bm, c, rec, mats, "hs_turret")
        # muzzle flash: additive glow, sized by gun_fire
        fb = bmesh.new()
        bmesh.ops.create_uvsphere(fb, u_segments=16, v_segments=8, radius=1.0)
        bmesh.ops.translate(fb, vec=(0, 1.0, 0), verts=fb.verts)
        me = bpy.data.meshes.new(f"Muzzle Flash {side}")
        fb.to_mesh(me)
        fb.free()
        me.materials.append(_fx_mat())
        fl = bpy.data.objects.new(f"Muzzle Flash {side}", me)
        c.objects.link(fl)
        fl.parent = rec
        fl.location = (0, 2.47, 0)
        fl["fx"] = 0.0
        fl["fx_color"] = [1.0, 0.55, 0.18, 1.0]
        fl["sb_haze"] = 1
        fl.visible_shadow = False
        drv(fl, '["fx"]', "f*1.6", root, {"f": "gun_fire"})
        for ax, k in ((0, 0.18), (1, 0.55), (2, 0.18)):
            drv(fl, "scale", "0.001+%.2f*f" % k, root, {"f": "gun_fire"}, ax)
    return lift


def canards(c, body, root, mats, mods):
    out = []
    cab = mods["cab"]
    y, z = CANARD["y"], CANARD["z"]
    hw = cab.p(y)[0]
    sp, ch = CANARD["span"], CANARD["chord"]
    for s, side in ((1, "R"), (-1, "L")):
        piv = geo.empty(f"Canard Hinge {side}", c, body, (s * (hw + 0.05), y, z), "PLAIN_AXES", 0.4)
        piv.rotation_mode = "XYZ"
        # stowed: span lies back along the hull (rotated 90 deg), deployed: straight out
        drv(piv, "rotation_euler", "%d*1.5708*(1-k)" % (-s), root, {"k": "canards"}, 2)
        bm = bmesh.new()
        # tapered fin in hinge space: span +x*s, chord from the hinge forward (+y)
        pts = [(0.0, 0.0), (0.0, ch), (sp, ch * 0.78), (sp, ch * 0.30)]
        top = [bm.verts.new((s * (0.08 + px), py, 0.045)) for px, py in pts]
        bot = [bm.verts.new((s * (0.08 + px), py, -0.045)) for px, py in pts]
        if s < 0:
            top, bot = top[::-1], bot[::-1]
        bm.faces.new(top)
        bm.faces.new(bot[::-1])
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((bot[i], bot[j], top[j], top[i]))
        _mat(bm, set(), B.PAINT)
        b0 = len(bm.faces)
        geo.add_box(bm, Vector((s * (0.08 + sp * 0.62), ch * 0.60, 0.05)), (sp * 0.55, 0.10, 0.012))
        _mat(bm, b0, B.ACCENT)
        b0 = len(bm.faces)
        geo.add_cyl(bm, (s * 0.07, 0.07, -0.08), (s * 0.07, 0.07, 0.08), 0.065, segs=12)  # hinge pin
        geo.add_cyl(bm, (s * (sp + 0.08), ch * 0.3, 0), (s * (sp + 0.08), ch * 0.78, 0), 0.05, segs=10)
        _mat(bm, b0, B.DARK)
        ob = _part(f"Canard {side}", bm, c, piv, mats, "hs_canard", bevel=0.02)
        bm2 = bmesh.new()
        lp = Matrix.Translation((s * (sp + 0.08), ch * 0.55, 0))
        geo.lathe(bm2, [(0.0, -0.05), (0.06, -0.05), (0.06, 0.03), (0.0, 0.08)], segs=12, mat=lp)
        for f in bm2.faces:
            f.material_index = B.NAV_G if s > 0 else B.NAV_R
        tip = geo.obj_from_bm(f"Canard Light {side}", bm2, c, parent=piv, mats=mats)
        tip["sb_piece"] = "hs_canard"
        tip["lights"] = 1.0
        drv(tip, '["lights"]', "l*k", root, {"l": "lights", "k": "canards"})
        out += [piv, ob, tip]
    return out


def build(c, body, root, mats, hull, mods):
    sect = split_hull(hull)
    engine_section(c, body, root, mats, sect["engine"])
    spine(c, body, root, mats, sect["spine"])
    gun_hood(c, body, root, mats, sect["hood"])
    turret(c, body, root, mats)
    canards(c, body, root, mats, mods)
    return sect
