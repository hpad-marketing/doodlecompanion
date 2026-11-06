"""Moving parts and their fixed mounts, plus the rig that drives them.

Every moving part hangs off a pivot empty placed on its real hinge, and is
driven from custom properties on the ship root ("Hero Ship"):

    gear 0..1          doors open (0-0.35), struts swing down (0.25-0.95)
    gear_compress m    shock struts slide up (touchdown squash), 0..0.3
    ramp 0..1          belly ramp lowers until its lip meets the ground
    nacelle_tilt 0..1  engine pods rotate 0 = cruise .. 1 = exhaust straight down
    radiators 0..1     spine radiator panels fold flat (0) or stand up (1)
    dish_rpm           comms dish spin speed (turns per minute)
    scan_deg           chin scanner yaw (degrees)
    engine 0..1        main and pod engine glow
    hyper 0..1         hyperdrive charge glow (teal rings, flicker)
    lights 0..1        nav lights and beacons on/off
"""
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from . import geo, body as B
from .layout import GROUND_Z, RAMP_Y

PROPS = {
    "gear": (1.0, 0.0, 1.0), "gear_compress": (0.0, 0.0, 0.3), "ramp": (0.0, 0.0, 1.0),
    "nacelle_tilt": (0.0, 0.0, 1.0), "radiators": (1.0, 0.0, 1.0), "dish_rpm": (6.0, -60.0, 60.0),
    "scan_deg": (0.0, -180.0, 180.0), "engine": (0.25, 0.0, 1.0), "hyper": (0.0, 0.0, 1.0),
    "lights": (1.0, 0.0, 1.0),
}
NACELLE = {"x": 8.65, "y": -8.75, "z": 0.6, "r": 1.45, "len": 8.6}
GEAR = {
    "n": {"pivot": (0.0, 11.1, -2.85), "bottom": -3.30, "half": 0.58},
    "1": {"pivot": (3.0, -11.4, -3.42), "bottom": -3.85, "half": 0.58},
    "-1": {"pivot": (-3.0, -11.4, -3.42), "bottom": -3.85, "half": 0.58},
}
RAD = {"hinge_x": 1.62, "z": 1.97, "y": (-2.5, 3.1), "w": 2.3, "open_deg": 65.0}
DISH = (0.0, -6.4, 3.85)


def drv(ob, path, expr, root, names, index=-1):
    """names: {variable: root property}."""
    fc = ob.driver_add(path, index) if index >= 0 else ob.driver_add(path)
    d = fc.driver
    d.type = "SCRIPTED"
    for var, n in names.items():
        v = d.variables.new()
        v.name = var
        v.type = "SINGLE_PROP"
        v.targets[0].id_type = "OBJECT"
        v.targets[0].id = root
        v.targets[0].data_path = f'["{n}"]'
    d.expression = expr
    return fc


def add_props(root):
    for k, (v, lo, hi) in PROPS.items():
        root[k] = v
        ui = root.id_properties_ui(k)
        ui.update(min=lo, max=hi, soft_min=lo, soft_max=hi)


def _part(name, bm, c, parent, mats, piece, bevel=0.0):
    ob = B.finish_object(name, bm, c, parent, mats, set(), bevel_w=bevel)
    if bevel <= 0:
        ob.modifiers.remove(ob.modifiers["Bevel"])
    ob["sb_piece"] = piece
    ob["hs_part"] = piece
    return ob


def _mat(bm, before, m):
    B._mat_new(bm, before, m)


# ---------------------------------------------------------------------------
def nacelles(c, body, root, mats):
    out = []
    N = NACELLE
    for s in (1, -1):
        side = "R" if s > 0 else "L"
        # fixed pylon + collar (airframe)
        bm = bmesh.new()
        geo.add_box(bm, Vector((s * 6.2, N["y"], 0.62)), (1.3, 2.5, 0.75), bevel=0.12)
        _mat(bm, set(), B.PAINT)
        b0 = set(bm.faces)
        geo.add_cyl(bm, (s * 6.8, N["y"], N["z"]), (s * 7.1, N["y"], N["z"]), 0.92, segs=32)
        _mat(bm, b0, B.DARK)
        b0 = set(bm.faces)
        for dz in (-0.25, 0.25):
            geo.add_box(bm, Vector((s * 6.2, N["y"] + 1.3, 0.62 + dz)), (1.1, 0.1, 0.12))
        B.bolts_row(bm, (s * 5.9, N["y"] - 1.0, 1.0), (s * 6.8, N["y"] - 1.0, 1.0), 4, (0, 0, 1))
        B.bolts_row(bm, (s * 5.9, N["y"] + 1.0, 1.0), (s * 6.8, N["y"] + 1.0, 1.0), 4, (0, 0, 1))
        _mat(bm, b0, B.DARK)
        py = _part(f"Pylon {side}", bm, c, body, mats, "hs_airframe")
        # pivot on the collar axis
        piv = geo.empty(f"Nacelle Pivot {side}", c, body, (s * N["x"], N["y"], N["z"]), "ARROWS", 1.0)
        piv.rotation_mode = "XYZ"
        drv(piv, "rotation_euler", "tilt*1.5707963", root, {"tilt": "nacelle_tilt"}, 0)
        bm = bmesh.new()
        r, h = N["r"], N["len"] / 2
        prof = [(r * 0.80, h + 0.05), (r * 0.92, h + 0.12), (r * 0.98, h), (r, h - 0.6), (r, -h + 1.2),
                (r * 0.93, -h + 0.55), (r * 0.80, -h + 0.25), (r * 0.78, -h + 0.2)]
        m = Matrix.Rotation(-math.pi / 2, 4, "X")  # lathe Z -> +Y
        geo.lathe(bm, prof, segs=40, mat=m)
        _mat(bm, set(), B.PAINT)
        b0 = set(bm.faces)
        # intake lip inside + fan
        geo.lathe(bm, [(r * 0.80, h + 0.05), (r * 0.74, h - 0.5)], segs=40, mat=m)
        _mat(bm, b0, B.DARK)
        b0 = set(bm.faces)
        geo.lathe(bm, [(0.0, h - 0.95), (0.25, h - 0.75), (r * 0.74, h - 0.5)], segs=40, mat=m)
        _mat(bm, b0, B.DARK)
        b0 = set(bm.faces)
        for k in range(14):
            a = 2 * math.pi * k / 14
            ca, sa = math.cos(a), math.sin(a)
            geo.add_box(bm, Vector((ca * 0.62, h - 0.62, sa * 0.62)), (0.06, 0.03, 0.75),
                        rot=Matrix.Rotation(-a + math.pi / 2, 4, "Y") @ Matrix.Rotation(0.5, 4, "Z"))
        _mat(bm, b0, B.HEAT)
        # band rings (raised), accent band
        for yy, mat, w in ((h - 0.85, B.DARK, 0.12), (h - 2.0, B.ACCENT, 0.5), (-h + 2.0, B.DARK, 0.12)):
            b0 = set(bm.faces)
            geo.add_cyl(bm, (0, yy - w / 2, 0), (0, yy + w / 2, 0), r + 0.03, segs=40)
            _mat(bm, b0, mat)
        # hub on the inner side (rotates with the pod, coaxial with the collar)
        b0 = set(bm.faces)
        geo.add_cyl(bm, (-s * (r + 0.05), 0, 0), (-s * (r - 0.3), 0, 0), 0.86, segs=32)
        _mat(bm, b0, B.DARK)
        # nozzle bell
        b0 = set(bm.faces)
        geo.lathe(bm, [(r * 0.78, -h + 0.2), (r * 0.80, -h - 0.35), (r * 0.86, -h - 0.7),
                       (r * 0.80, -h - 0.7), (r * 0.72, -h - 0.3), (r * 0.66, -h + 0.25)], segs=40, mat=m)
        _mat(bm, b0, B.HEAT)
        # dorsal fin with a nav light, vents on top, outer conduit
        b0 = set(bm.faces)
        geo.add_box(bm, Vector((0, -h + 2.6, r + 0.35)), (0.12, 1.6, 0.8),
                    rot=Matrix.Rotation(math.radians(-20), 4, "X"), bevel=0.04)
        _mat(bm, b0, B.PAINT)
        b0 = set(bm.faces)
        xc = math.sqrt(r * r - 0.09) + 0.05
        B.tube(bm, [(s * xc, h - 1.2, 0.3), (s * xc, -h + 1.4, 0.3)], 0.06, segs=8)
        for yy in (h - 1.4, 0.0, -h + 1.6):
            geo.add_box(bm, Vector((s * xc, yy, 0.3)), (0.14, 0.14, 0.2))
        _mat(bm, b0, B.DARK)
        nb = _part(f"Nacelle {side}", bm, c, piv, mats, f"hs_nacelle_{side}")
        nb["sb_group"] = f"nacelle_{side}"
        # glow disc + hyper ring + nav light (separate emissive objects, same pivot)
        g = bmesh.new()
        geo.lathe(g, [(0.0, -h + 0.15), (r * 0.66, -h + 0.15)], segs=40, mat=m)
        for f in g.faces:
            f.material_index = B.ENGINE
        go = geo.obj_from_bm(f"Nacelle Glow {side}", g, c, parent=piv, mats=mats)
        go["engine"] = 0.2
        go["sb_group"] = f"nacelle_{side}"
        drv(go, '["engine"]', "e", root, {"e": "engine"})
        hr = bmesh.new()
        for yy in (h - 2.9, h - 3.4):
            geo.add_cyl(hr, (0, yy - 0.04, 0), (0, yy + 0.04, 0), r + 0.045, segs=40, caps=True)
        for f in hr.faces:
            f.material_index = B.GLOW
        ho = geo.obj_from_bm(f"Hyper Rings {side}", hr, c, parent=piv, mats=mats)
        ho["sb_group"] = f"nacelle_{side}"
        ho["hyper"] = 0.0
        drv(ho, '["hyper"]', "hy", root, {"hy": "hyper"})
        nl = bmesh.new()
        geo.add_cyl(nl, (s * (r + 0.0), 0.6, 0), (s * (r + 0.12), 0.6, 0), 0.1, segs=12)
        for f in nl.faces:
            f.material_index = B.NAV_G if s > 0 else B.NAV_R
        lo = geo.obj_from_bm(f"Nav Light {side}", nl, c, parent=piv, mats=mats)
        lo["sb_group"] = f"nacelle_{side}"
        lo["lights"] = 1.0
        drv(lo, '["lights"]', "l", root, {"l": "lights"})
        out += [py, piv, nb, go, ho, lo]
    return out


# ---------------------------------------------------------------------------
def strut_len(key):
    p = GEAR[key]["pivot"]
    return p[2] - GROUND_Z


def gear(c, body, root, mats):
    out = []
    for key, G in GEAR.items():
        px, py, pz = G["pivot"]
        bot, half = G["bottom"], G["half"]
        L = strut_len(key)
        # doors: hinge on the bay's long edges
        for s in (1, -1):
            hinge = (px + s * half, py, bot)
            dp = geo.empty(f"Gear Door Pivot {key}{'R' if s > 0 else 'L'}", c, body, hinge, "PLAIN_AXES", 0.2)
            y0, y1 = (8.45, 11.55) if key == "n" else (-13.85, -10.95)
            bm = bmesh.new()
            geo.add_box(bm, Vector((-s * (half / 2 + 0.003), (y0 + y1) / 2 - py, 0.03)), (half - 0.012, y1 - y0 - 0.02, 0.05))
            _mat(bm, set(), B.PAINT)
            b0 = set(bm.faces)
            for yy in (y0 + 0.4 - py, y1 - 0.4 - py):
                geo.add_cyl(bm, (-s * 0.03, yy - 0.15, 0.03), (-s * 0.03, yy + 0.15, 0.03), 0.025, segs=8)
            geo.add_box(bm, Vector((-s * half / 2, (y0 + y1) / 2 - py, 0.075)), (0.06, y1 - y0 - 0.5, 0.04))
            _mat(bm, b0, B.DARK)
            do = _part(f"Gear Door {key}{'R' if s > 0 else 'L'}", bm, c, dp, mats, f"hs_door_{key}_{s}")
            drv(dp, "rotation_euler", f"{-s}*1.745*min(max(g/0.35,0),1)", root, {"g": "gear"}, 1)
            out += [dp, do]
        # strut: rest pose points straight down; stowed = -90 deg about X (points aft)
        sp = geo.empty(f"Gear Pivot {key}", c, body, (px, py, pz), "PLAIN_AXES", 0.3)
        drv(sp, "rotation_euler", "-1.5707963*(1-min(max((g-0.25)/0.7,0),1))", root, {"g": "gear"}, 0)
        bm = bmesh.new()
        geo.add_cyl(bm, (-0.2, 0, 0), (0.2, 0, 0), 0.15, segs=16)
        _mat(bm, set(), B.DARK)
        b0 = set(bm.faces)
        geo.add_cyl(bm, (0, 0, -0.05), (0, 0, -(L * 0.55)), 0.12, segs=14)
        geo.add_cyl(bm, (0, 0, -(L * 0.5)), (0, 0, -(L * 0.58)), 0.15, segs=14)
        _mat(bm, b0, B.PAINT)
        b0 = set(bm.faces)
        geo.add_box(bm, Vector((0, 0.13, -L * 0.25)), (0.06, 0.06, L * 0.4))   # hydraulic line
        _mat(bm, b0, B.RUBBER)
        so = _part(f"Gear Strut {key}", bm, c, sp, mats, f"hs_gear_{key}")
        # piston + foot slide up the strut by gear_compress
        pp = geo.empty(f"Gear Piston Slide {key}", c, sp, (0, 0, 0), "PLAIN_AXES", 0.2)
        drv(pp, "location", "k", root, {"k": "gear_compress"}, 2)
        bm = bmesh.new()
        geo.add_cyl(bm, (0, 0, -L * 0.45), (0, 0, -L + 0.2), 0.085, segs=14)
        _mat(bm, set(), B.HEAT)
        b0 = set(bm.faces)
        geo.add_cyl(bm, (-0.12, 0, -L + 0.2), (0.12, 0, -L + 0.2), 0.08, segs=12)   # ankle
        _mat(bm, b0, B.DARK)
        b0 = set(bm.faces)
        geo.lathe(bm, [(0.0, -L + 0.12), (0.2, -L + 0.12), (0.26, -L + 0.06), (0.26, -L), (0.0, -L)],
                  segs=24)
        _mat(bm, b0, B.RUBBER)
        fo = _part(f"Gear Foot {key}", bm, c, pp, mats, f"hs_gear_{key}")
        fo["sb_group"] = f"gear_{key}"
        so["sb_group"] = f"gear_{key}"
        out += [sp, so, pp, fo]
    return out


# ---------------------------------------------------------------------------
def ramp(c, body, root, mats, ramp_pts, bay_depth=1.75):
    xs = [p[0] for f in ramp_pts for p in f]
    ys = [p[1] for f in ramp_pts for p in f]
    zs = [p[2] for f in ramp_pts for p in f]
    x0, ya, yf, zb = max(abs(x) for x in xs) - 0.03, min(ys) + 0.03, max(ys) - 0.03, min(zs)
    Lr = yf - ya
    piv = geo.empty("Ramp Pivot", c, body, (0, ya, zb), "PLAIN_AXES", 0.4)
    drop = zb - GROUND_Z
    ang = math.asin(min(1.0, drop / Lr))
    drv(piv, "rotation_euler", f"-{ang:.5f}*r", root, {"r": "ramp"}, 0)
    bm = bmesh.new()
    geo.add_box(bm, Vector((0, Lr / 2, 0.09)), (2 * x0, Lr, 0.18))
    _mat(bm, set(), B.PAINT)
    b0 = set(bm.faces)
    for k in range(9):
        yy = 0.5 + k * (Lr - 1.0) / 8
        geo.add_box(bm, Vector((0, yy, 0.2)), (2 * x0 - 0.5, 0.08, 0.05))
    for s in (1, -1):
        geo.add_box(bm, Vector((s * (x0 - 0.1), Lr / 2, 0.24)), (0.12, Lr - 0.2, 0.12))
    geo.add_cyl(bm, (-x0 + 0.1, 0.1, 0.09), (x0 - 0.1, 0.1, 0.09), 0.09, segs=12)
    _mat(bm, b0, B.DARK)
    b0 = set(bm.faces)
    for s in (1, -1):
        geo.add_box(bm, Vector((s * (x0 - 0.35), Lr - 0.25, 0.005)), (0.5, 0.35, 0.01))
    _mat(bm, b0, B.ACCENT)
    ro = _part("Ramp", bm, c, piv, mats, "hs_ramp")
    # bay lights: a strip in the ceiling and a warm area light
    lb = bmesh.new()
    geo.add_box(lb, Vector((0, (ya + yf) / 2, zb + bay_depth - 0.03)), (0.25, Lr - 1.2, 0.05))
    for f in lb.faces:
        f.material_index = B.WHITE
    lo = geo.obj_from_bm("Bay Light Strip", lb, c, parent=body, mats=mats)
    lo["sb_piece"] = "hs_airframe"
    lo["lights"] = 1.0
    drv(lo, '["lights"]', "l", root, {"l": "lights"})
    la = bpy.data.lights.new("Bay Light", "AREA")
    la.energy = 900
    la.color = (1.0, 0.78, 0.55)
    la.shape = "RECTANGLE"
    la.size, la.size_y = 2 * x0 - 0.4, Lr - 0.6
    lob = bpy.data.objects.new("Bay Light", la)
    c.objects.link(lob)
    lob.parent = body
    lob.location = (0, (ya + yf) / 2, zb + bay_depth - 0.12)
    return [piv, ro, lo, lob], ang


# ---------------------------------------------------------------------------
def radiators(c, body, root, mats):
    out = []
    R = RAD
    y0, y1 = R["y"]
    # fixed hinge rods on posts from the keel
    bm = bmesh.new()
    for s in (1, -1):
        geo.add_cyl(bm, (s * R["hinge_x"], y0 - 0.1, R["z"]), (s * R["hinge_x"], y1 + 0.1, R["z"]), 0.075, segs=12)
        for yy in (y0 + 0.2, (y0 + y1) / 2, y1 - 0.2):
            geo.add_box(bm, Vector((s * R["hinge_x"], yy, (R["z"] - 0.07 + 0.75) / 2)), (0.12, 0.12, R["z"] - 0.07 - 0.75))
    _mat(bm, set(), B.DARK)
    ho = _part("Radiator Hinges", bm, c, body, mats, "hs_airframe")
    out.append(ho)
    for s in (1, -1):
        side = "R" if s > 0 else "L"
        piv = geo.empty(f"Radiator Pivot {side}", c, body, (s * R["hinge_x"], 0, R["z"]), "PLAIN_AXES", 0.3)
        drv(piv, "rotation_euler", f"{-s}*{math.radians(R['open_deg']):.5f}*r", root, {"r": "radiators"}, 1)
        bm = bmesh.new()
        w = R["w"]
        geo.add_box(bm, Vector((s * (w / 2 + 0.1), (y0 + y1) / 2, 0)), (w, y1 - y0, 0.07), bevel=0.02)
        _mat(bm, set(), B.PAINT)
        b0 = set(bm.faces)
        n = 14
        for k in range(n):
            yy = y0 + 0.25 + k * (y1 - y0 - 0.5) / (n - 1)
            geo.add_box(bm, Vector((s * (w / 2 + 0.15), yy, 0.075)), (w - 0.25, 0.03, 0.08))
        _mat(bm, b0, B.HEAT)
        b0 = set(bm.faces)
        geo.add_box(bm, Vector((s * 0.16, (y0 + y1) / 2, 0.0)), (0.12, y1 - y0 - 0.1, 0.12))
        for yy in (y0 + 0.5, y1 - 0.5):
            geo.lathe(bm, [(0.085, -0.2), (0.12, -0.2), (0.12, 0.2), (0.085, 0.2)], segs=16,
                      mat=Matrix.Translation((0, yy, 0)) @ Matrix.Rotation(-math.pi / 2, 4, "X"),
                      cap_start=False)
            geo.add_box(bm, Vector((s * 0.11, yy, 0)), (0.06, 0.36, 0.06))
        _mat(bm, b0, B.DARK)
        b0 = set(bm.faces)
        geo.add_box(bm, Vector((s * (w + 0.06), (y0 + y1) / 2, 0)), (0.05, y1 - y0 - 0.4, 0.05))
        _mat(bm, b0, B.ACCENT)
        ob = _part(f"Radiator {side}", bm, c, piv, mats, f"hs_radiator_{side}")
        out += [piv, ob]
    return out


# ---------------------------------------------------------------------------
def dish_and_masts(c, body, root, mats):
    out = []
    x, y, z = DISH
    bm = bmesh.new()
    geo.lathe(bm, [(0.55, -0.02), (0.55, 0.12), (0.42, 0.25), (0.0, 0.25)], segs=24,
              mat=Matrix.Translation((x, y, z)))
    _mat(bm, set(), B.DARK)
    # masts on the aft deck's back corners + small spikes up front
    b0 = set(bm.faces)
    for s in (1, -1):
        geo.add_cyl(bm, (s * 1.6, -11.6, 3.8), (s * 1.6, -11.6, 4.3), 0.12, segs=10)
        geo.add_cyl(bm, (s * 1.6, -11.6, 4.3), (s * 1.6, -11.6, 6.1), 0.04, segs=8)
        geo.add_cyl(bm, (s * 1.6, -11.6, 5.2), (s * 1.6, -11.6, 5.25), 0.15, segs=10)
        geo.add_cyl(bm, (s * 1.0, 10.8, 3.24), (s * 1.0, 10.8, 3.5), 0.1, segs=8)
        geo.add_cyl(bm, (s * 1.0, 10.8, 3.5), (s * 1.0, 10.5, 4.6), 0.035, segs=8)
    _mat(bm, b0, B.DARK)
    b0 = set(bm.faces)
    # survey booms out of the chin
    for s in (1, -1):
        geo.add_cyl(bm, (s * 0.85, 18.9, -2.05), (s * 0.85, 24.6, -2.05), 0.1, segs=12)
        geo.add_cyl(bm, (s * 0.85, 19.9, -2.05), (s * 0.85, 20.4, -2.05), 0.16, segs=12)
        geo.add_cyl(bm, (s * 0.85, 23.0, -2.05), (s * 0.85, 23.2, -2.05), 0.14, segs=12)
    _mat(bm, b0, B.DARK)
    b0 = set(bm.faces)
    for s in (1, -1):
        geo.add_cyl(bm, (s * 0.85, 24.6, -2.05), (s * 0.85, 25.0, -2.05), 0.12, r1=0.04, segs=12)
    _mat(bm, b0, B.HEAT)
    # chin scanner housing
    b0 = set(bm.faces)
    geo.add_cyl(bm, (0, 17.0, -2.66), (0, 17.0, -2.5), 0.5, segs=24)
    _mat(bm, b0, B.DARK)
    mo = _part("Masts and Booms", bm, c, body, mats, "hs_airframe")
    out.append(mo)
    # dish: spins about Z
    piv = geo.empty("Dish Pivot", c, body, (x, y, z + 0.25), "PLAIN_AXES", 0.4)
    piv.rotation_mode = "XYZ"
    drv(piv, "rotation_euler", "frame*rpm*0.004363323", root, {"rpm": "dish_rpm"}, 2)
    bm = bmesh.new()
    geo.add_cyl(bm, (0, 0, 0.005), (0, 0, 0.55), 0.14, segs=12)
    geo.add_box(bm, Vector((0, 0, 0.6)), (0.5, 0.14, 0.14))
    for s in (1, -1):
        geo.add_box(bm, Vector((s * 0.25, 0, 0.78)), (0.06, 0.12, 0.42))
    _mat(bm, set(), B.DARK)
    b0 = set(bm.faces)
    tilt = Matrix.Translation((0, 0, 0.95)) @ Matrix.Rotation(math.radians(-55), 4, "X")
    geo.lathe(bm, [(0.06, -0.12), (0.4, -0.08), (0.75, 0.04), (0.95, 0.22), (0.92, 0.24), (0.72, 0.08),
                   (0.38, -0.04), (0.06, -0.08)], segs=36, mat=tilt)
    _mat(bm, b0, B.PAINT)
    b0 = set(bm.faces)
    for k in range(3):
        a = 2 * math.pi * k / 3
        p0 = tilt @ Vector((0.85 * math.cos(a), 0.85 * math.sin(a), 0.2))
        p1 = tilt @ Vector((0, 0, 0.75))
        geo.add_cyl(bm, p0, p1, 0.02, segs=6)
    geo.add_cyl(bm, tilt @ Vector((0, 0, 0.7)), tilt @ Vector((0, 0, 0.85)), 0.08, segs=10)
    _mat(bm, b0, B.DARK)
    do = _part("Comms Dish", bm, c, piv, mats, "hs_dish")
    out += [piv, do]
    # chin scanner ball: yaws with scan_deg
    sp = geo.empty("Scanner Pivot", c, body, (0, 17.0, -2.66), "PLAIN_AXES", 0.3)
    drv(sp, "rotation_euler", "d*0.01745329", root, {"d": "scan_deg"}, 2)
    bm = bmesh.new()
    geo.lathe(bm, [(0.0, -0.02), (0.44, -0.04), (0.47, -0.25), (0.40, -0.5), (0.0, -0.62)], segs=28)
    _mat(bm, set(), B.PAINT)
    b0 = set(bm.faces)
    geo.add_cyl(bm, (0, 0.3, -0.33), (0, 0.48, -0.33), 0.16, segs=16)
    _mat(bm, b0, B.GLASS)
    so = _part("Chin Scanner", bm, c, sp, mats, "hs_scanner")
    out += [sp, so]
    return out


# ---------------------------------------------------------------------------
def nav_lights(c, body, root, mats):
    """Blinking beacons: tail strobes, mast tips, belly beacon."""
    pts = [((1.6, -11.6, 6.15), B.WHITE, "strobe"), ((-1.6, -11.6, 6.15), B.WHITE, "strobe"),
           ((0, -18.4, 2.64), B.WHITE, "strobe"), ((0.45, 0.4, -1.5), B.NAV_R, "beacon"),
           ((0, 6.0, 3.31), B.NAV_R, "beacon")]
    out = []
    for i, (p, m, kind) in enumerate(pts):
        bm = bmesh.new()
        if p[2] < 0:
            geo.lathe(bm, [(0.0, 0.0), (0.12, 0.0), (0.12, -0.08), (0.0, -0.2)], segs=16,
                      mat=Matrix.Translation(p))
        elif kind == "strobe" and abs(p[1]) > 15:
            geo.lathe(bm, [(0.0, 0.0), (0.1, 0.0), (0.1, 0.06), (0.0, 0.16)], segs=16,
                      mat=Matrix.Translation(p))
        else:
            geo.lathe(bm, [(0.0, -0.05), (0.1, -0.05), (0.1, 0.06), (0.0, 0.16)], segs=16,
                      mat=Matrix.Translation(p))
        for f in bm.faces:
            f.material_index = m
        ob = geo.obj_from_bm(f"Beacon {i}", bm, c, parent=body, mats=mats)
        ob["sb_piece"] = "hs_airframe"
        ob["lights"] = 1.0
        if kind == "strobe":
            expr = "l*(1.0 if sin(frame*0.2618+%d) > 0.97 else 0.04)" % i
        else:
            expr = "l*(0.25+0.75*max(sin(frame*0.1309+%d),0))" % i
        drv(ob, '["lights"]', expr, root, {"l": "lights"})
        out.append(ob)
    return out


# ---------------------------------------------------------------------------
def _plume_mat():
    m = bpy.data.materials.get("HS Plume")
    if m:
        return m
    from .mats import N
    m = bpy.data.materials.new("HS Plume")
    n = N(m)
    tc = n("ShaderNodeTexCoord")
    sep = n("ShaderNodeSeparateXYZ")
    n.set(sep.inputs[0], tc.outputs["Generated"])
    along = sep.outputs["Y"]                 # 0 at the tail, 1 at the nozzle
    lw = n("ShaderNodeLayerWeight", Blend=0.5)
    core = n.math("POWER", n.math("SUBTRACT", 1.0, lw.outputs["Facing"]), 2.5)
    e = n.attr("engine", "OBJECT").outputs["Fac"]
    flick = n.noise(tc.outputs["Object"], 2.0, 3, 0.5, stretch=(1, 0.25, 1))
    k = n.math("MULTIPLY", n.math("MULTIPLY", core, n.math("POWER", along, 1.6)), e)
    k = n.math("MULTIPLY", k, n.math("MULTIPLY_ADD", flick, 0.6, 0.7))
    em = n("ShaderNodeEmission", Color=(0.45, 0.80, 1.0, 1))
    n.set(em.inputs["Strength"], n.math("MULTIPLY", k, 14.0))
    tr = n("ShaderNodeBsdfTransparent")
    ad = n("ShaderNodeAddShader")
    n.set(ad.inputs[0], tr)
    n.set(ad.inputs[1], em)
    n.out(ad)
    return m


def _plume_bm(r0, length):
    bm = bmesh.new()
    prof = [(0.0, 0.0), (r0 * 0.95, 0.0), (r0 * 1.05, -length * 0.15), (r0 * 0.8, -length * 0.55),
            (r0 * 0.35, -length * 0.9), (0.0, -length)]
    geo.lathe(bm, [(r, -z) for r, z in prof], segs=32, mat=Matrix.Rotation(math.pi / 2, 4, "X"))
    return bm


def plumes(c, body, root):
    """Exhaust plumes: transparent glow cones whose length follows the engine power."""
    out = []
    pm = _plume_mat()
    for i, (x, z, r) in enumerate(((0.0, 0.95, 1.0), (2.0, -0.9, 0.9), (-2.0, -0.9, 0.9))):
        bm = _plume_bm(r * 0.95, 9.0)
        ob = geo.obj_from_bm(f"Plume Main {i}", bm, c, parent=body, mats=[pm], loc=(x, -20.9, z))
        out.append(ob)
    for side in ("L", "R"):
        piv = bpy.data.objects.get(f"Nacelle Pivot {side}")
        bm = _plume_bm(NACELLE["r"] * 0.66, 6.0)
        ob = geo.obj_from_bm(f"Plume Pod {side}", bm, c, parent=piv, mats=[pm],
                             loc=(0, -NACELLE["len"] / 2 - 0.3, 0))
        out.append(ob)
    for ob in out:
        ob["engine"] = 0.2
        ob["hs_plume"] = 1
        ob.visible_shadow = False
        ob.visible_diffuse = False
        drv(ob, '["engine"]', "e", root, {"e": "engine"})
        if ob.name.startswith("Plume Pod"):
            # pointing down over a pad (z = 0): the plume stops just above the ground
            fc = drv(ob, "scale", "0.02+min(e, max(z-4.45,0)/6.0+(1-t)*2)", root,
                     {"e": "engine", "t": "nacelle_tilt"}, 1)
            v = fc.driver.variables.new()
            v.name = "z"
            v.type = "TRANSFORMS"
            v.targets[0].id = root
            v.targets[0].transform_type = "LOC_Z"
            v.targets[0].transform_space = "WORLD_SPACE"
        else:
            drv(ob, "scale", "0.08+e*1.0", root, {"e": "engine"}, 1)
        for ax in (0, 2):
            drv(ob, "scale", "0.7+e*0.35", root, {"e": "engine"}, ax)
    return out
