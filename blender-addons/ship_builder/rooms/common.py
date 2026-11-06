"""Shared room shell: deck, three panelled walls, ceiling, the hidden fourth wall
(it still bounces light and blocks space light, but the camera sees through it),
and optional window / door openings."""
import math
import bpy
from mathutils import Vector

from .. import kit as K
from .. import mats as M


def opening(rect):
    """rect = (u0, u1, z0, z1) in metres along the wall. Returns a skip() test."""
    u0, u1, z0, z1 = rect

    def skip(i, j, pw, ph):
        a0, a1, b0, b1 = i * pw, (i + 1) * pw, j * ph, (j + 1) * ph
        return a1 > u0 + 0.01 and a0 < u1 - 0.01 and b1 > z0 + 0.01 and b0 < z1 - 0.01
    return skip


def any_of(*tests):
    tests = [t for t in tests if t]
    return (lambda i, j, pw, ph: any(t(i, j, pw, ph) for t in tests)) if tests else None


def _flat(holes):
    """Door holes reach the floor: their sliding leaves need flush plates beside them."""
    return [(h[0] - 0.62, h[1] + 0.62) for h in holes if h[2] < 0.12]


def shell(room, back_holes=(), left_holes=(), right_holes=(), pal_key="panel", panel=(1.0, 0.75), chamfer=0.0):
    W, D, H = room.W, room.D, room.H
    room.chamfer = chamfer
    K.floor(room)
    # back wall: origin bottom-left at (-W/2, D), u = +x, normal = -y
    K.wall(room, (-W / 2, D, 0), (1, 0, 0), (0, 0, 1), W, H, (0, -1, 0), pal_key, panel,
           None, "Back", holes=back_holes, flat=_flat(back_holes))
    # left wall: origin at (-W/2, 0), u = +y, normal = +x
    K.wall(room, (-W / 2, 0, 0), (0, 1, 0), (0, 0, 1), D, H, (1, 0, 0), pal_key, panel,
           None, "Left", holes=left_holes, flat=_flat(left_holes), trim_end=0.045)
    # right wall: origin at (W/2, D), u = -y, normal = -x
    K.wall(room, (W / 2, D, 0), (0, -1, 0), (0, 0, 1), D, H, (-1, 0, 0), pal_key, panel,
           None, "Right", holes=right_holes, flat=_flat(right_holes), trim_start=0.045)
    # corner posts hide panel ends
    for x in (() if chamfer else (-W / 2 + 0.08, W / 2 - 0.08)):
        K.box("Corner Post", (0.16, 0.16, H), (x, D - 0.08, H / 2), room.pal["hull"], room.shell, bevel=0.01)
    # fourth wall: camera-transparent, keeps the room closed for light
    fw = K.box("Fourth Wall", (W, 0.05, H), (0, -0.03, H / 2), room.pal["hull"], room.shell, bevel=0)
    fw.visible_camera = False
    fw.visible_glossy = True
    fw["sb_fourth_wall"] = 1
    # skirting + top trim
    # skirting stops short of the chamfered corner columns
    cut = chamfer + 0.12 if chamfer else 0.0
    # ... and leaves gaps where a door or floor-level opening cuts the wall
    def spans(L, holes, c0, c1):
        # floor-level openings are doors: the skirting also clears their sliding pockets
        cuts = sorted((h[0] - 0.55, h[1] + 0.55) for h in holes if h[2] < 0.12)
        out, s = [], c0
        for a, b in cuts:
            if a > s:
                out.append((s, a - 0.02))
            s = max(s, b + 0.02)
        if s < L - c1:
            out.append((s, L - c1))
        return [(a, b) for a, b in out if b - a > 0.1]
    sk = room.pal["dark_steel"]
    for a, b in spans(W, back_holes, cut, cut):
        K.box("Skirting Back", (b - a, 0.05, 0.12), (-W / 2 + (a + b) / 2, D - 0.06, 0.06), sk, room.shell, bevel=0.004)
    for a, b in spans(D, left_holes, 0.0, cut):  # left wall runs +y from the front
        K.box("Skirting Left", (0.05, b - a, 0.12), (-W / 2 + 0.06, (a + b) / 2, 0.06), sk, room.shell, bevel=0.004)
    for a, b in spans(D, right_holes, cut, 0.0):  # right wall runs -y from the back
        K.box("Skirting Right", (0.05, b - a, 0.12), (W / 2 - 0.06, D - (a + b) / 2, 0.06), sk, room.shell, bevel=0.004)


def window(room, centre, w, h, normal=(0, -1, 0), frame=0.12, name="Window", tilt=-9):
    """Thick armoured window frame with double glass, set into a wall opening."""
    c, n = Vector(centre), Vector(normal)
    up = Vector((0, 0, 1))
    side = up.cross(n).normalized()
    rot = __import__("mathutils").Matrix((side, up, n)).transposed().to_euler()
    depth = 0.28
    parts = []
    for (dx, dz, sw, sh) in ((0, (h + frame) / 2, w + 2 * frame, frame), (0, -(h + frame) / 2, w + 2 * frame, frame),
                             ((w + frame) / 2, 0, frame, h), (-(w + frame) / 2, 0, frame, h)):
        p = K.box(f"{name} Frame", (sw, sh, depth), c + side * dx + up * dz - n * (depth / 2 - 0.06), room.pal["hull"], room.shell, bevel=0.02)
        p.rotation_euler = rot
        parts.append(p)
    # inner bevelled reveal
    for k, z in enumerate((-0.1,)):
        g = K.box(f"{name} Glass", (w - 0.012, h - 0.03, 0.012), c + n * z, room.pal["glass"], room.shell, bevel=0.002)
        g.rotation_euler = rot
        g.rotation_euler.rotate_axis("X", math.radians(tilt))  # armoured glass leans in
        g.visible_shadow = False
    # bolts around the frame
    if K.DETAIL["level"] >= 2:
        for k in range(14):
            t = k / 14
            per = 2 * (w + h)
            d = t * per
            if d < w:
                p = c + side * (d - w / 2) + up * (h / 2 + frame / 2)
            elif d < w + h:
                p = c + side * (w / 2 + frame / 2) + up * (h / 2 - (d - w))
            elif d < 2 * w + h:
                p = c + side * (w / 2 - (d - w - h)) - up * (h / 2 + frame / 2)
            else:
                p = c - side * (w / 2 + frame / 2) - up * (h / 2 - (d - 2 * w - h))
            K.bolt(p + n * 0.062, n, room.dress)
    return parts


def planet(room, loc=(-40, 160, 30), radius=34, color=(0.55, 0.32, 0.18, 1), ring=True):
    """A distant planet outside, lit by the local star."""
    import bmesh
    me = bpy.data.meshes.new("SB Planet")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=radius)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    m, new = M._get("SB Planet Surface")
    if new:
        g = M.G(m)
        v = g.coord((1, 1, 6))
        n1 = g.noise(0.08, 10, 0.6, vec=v)
        n2 = g.noise(0.6, 12, 0.7)
        bands = g.math("ADD", n1.outputs[0], g.math("MULTIPLY", n2.outputs[0], 0.35))
        col = g.mix(g.ramp(bands, 0.35, 0.75), color, (0.85, 0.7, 0.5, 1))
        col = g.mix(g.ramp(n2.outputs[0], 0.6, 0.7), col, (0.25, 0.12, 0.08, 1))
        bsdf = g.node("ShaderNodeBsdfPrincipled")
        g._in(bsdf.inputs["Base Color"], col)
        bsdf.inputs["Roughness"].default_value = 0.9
        g.out(bsdf)
    me.materials.append(m)
    ob = bpy.data.objects.new("Planet", me)
    room.dress.objects.link(ob)
    ob.location = loc
    ob.visible_shadow = False
    ob.visible_diffuse = False
    if ring:
        rme = bpy.data.meshes.new("SB Ring")
        verts, faces = [], []
        for i in range(128):
            a = i / 128 * 6.2832
            for r in (radius * 1.45, radius * 2.1):
                verts.append((r * math.cos(a), r * math.sin(a), 0))
        for i in range(128):
            j = (i + 1) % 128
            faces.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
        rme.from_pydata(verts, [], faces)
        rm, new = M._get("SB Planet Ring")
        if new:
            g = M.G(rm)
            gc = g.node("ShaderNodeTexCoord")
            grad = g.node("ShaderNodeTexGradient", _gradient_type="SPHERICAL")
            sc = g.node("ShaderNodeMapping")
            g.link(gc.outputs["Object"], sc.inputs["Vector"])
            sc.inputs["Scale"].default_value = (1 / (radius * 2.1),) * 3
            g.link(sc.outputs[0], grad.inputs["Vector"])
            wv = g.node("ShaderNodeTexWave", _wave_type="RINGS")
            g.link(sc.outputs[0], wv.inputs["Vector"])
            wv.inputs["Scale"].default_value = 18
            wv.inputs["Distortion"].default_value = 2
            alpha = g.ramp(wv.outputs["Fac"], 0.3, 0.9)
            bsdf = g.node("ShaderNodeBsdfPrincipled")
            bsdf.inputs["Base Color"].default_value = (0.8, 0.7, 0.55, 1)
            g._in(bsdf.inputs["Alpha"], g.math("MULTIPLY", alpha, 0.8))
            g.out(bsdf)
        rme.materials.append(rm)
        ro = bpy.data.objects.new("Planet Ring", rme)
        room.dress.objects.link(ro)
        ro.location = loc
        ro.rotation_euler = (math.radians(74), math.radians(-18), 0)
        ro.visible_shadow = False
    # local star: a sun that also slants through the window
    L = bpy.data.lights.new("SB Star", "SUN")
    L.energy = 2.2
    L.color = (1.0, 0.9, 0.78)
    L.angle = math.radians(0.6)
    so = bpy.data.objects.new("SB Star", L)
    room.lights.objects.link(so)
    so.rotation_euler = (math.radians(58), math.radians(12), math.radians(200))
    so["sb_light"] = "star"
    so["sb_energy"] = L.energy
    so["sb_color"] = list(L.color)
    return ob


def door(room, yc, x=None, name=None, side="right"):
    """Two-leaf pressure door in a side-wall opening, centred on yc.

    side is "right" (wall at +W/2) or "left" (wall at -W/2). The leaves slide
    sideways into pockets behind wide jambs, so a moving door never passes
    through anything. Open/close with the "open" property (0..1) on the door's
    control empty; the leaves follow through drivers, so it can be keyed.
    room.doors gets a socket entry, used to connect rooms into a ship."""
    W = room.W
    pal = room.pal
    s = 1 if side == "right" else -1           # s points out through the wall
    x = s * W / 2 if x is None else x
    did = name or f"{room.name} Door {len(getattr(room, 'doors', [])) + 1}"
    half, leaf_w, pocket = 0.74, 0.7385, 0.75
    jf, jb = x - s * 0.32, x - s * 0.125         # jamb room face / back
    lf_, lb = x - s * 0.12, x - s * 0.06        # leaf track
    jc, jw = (jf + jb) / 2, abs(jb - jf)
    lc, lw = (lf_ + lb) / 2, abs(lb - lf_)
    with K.piece(room, "Door", 0, 0):
        K.box("Door Lintel", (jw, 2 * (half + pocket), 0.3), (jc, yc, 2.1), pal["hull"], room.shell, bevel=0.02)
        K.box("Door Header", (lw + 0.004, 2 * half, 0.29), (lc, yc, 2.1), pal["dark_steel"], room.shell, bevel=0.004)
        for sd in (-1, 1):
            K.box("Door Jamb", (jw, pocket, 1.948), (jc, yc + sd * (half + pocket / 2), 0.974), pal["hull"], room.shell, bevel=0.02)
        back = K.box("Door Back", (0.04, 2 * half, 1.928), (x + s * 0.02, yc, 0.021 + 0.964), M.painted_metal("SB Backing", (0.02, 0.021, 0.023, 1), 0.6), room.shell, bevel=0)
        back["sb_door_back"] = did
        K.box("Door Sill", (0.4, 2 * half - 0.006, 0.02), (x - s * 0.2, yc, 0.0105), M.hazard(), room.shell, bevel=0.003)
        K.box("Door Hazard", (0.004, 2 * (half + pocket) - 0.02, 0.08), (jf - s * 0.0025, yc, 2.1), M.hazard(), room.shell, bevel=0.001, segs=1)
        K.screen(room, (jf - s * 0.001, yc - half - pocket / 2, 1.3), (0, -s, 0), (0, 0, 1), (-s, 0, 0), 0.16, 0.22, (0.4, 1.0, 0.5, 1), "ui", light=False, name="Door Keypad")
        K.light_strip(room, (x - s * 0.3, yc, 2.29), 1.4, "Y", (0, 0, -1), (0.4, 1.0, 0.6, 1), 6, role="practical", width=0.02)
    # control + leaves (not part of the static piece: they move)
    ctl = bpy.data.objects.new(did, None)
    room.shell.objects.link(ctl)
    ctl.empty_display_type = "ARROWS"
    ctl.empty_display_size = 0.3
    ctl.location = (x - s * 0.4, yc, 1.0)
    ctl["open"] = 0.0
    ctl.id_properties_ui("open").update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description="0 closed, 1 open")
    ctl["sb_door"] = did
    ctl["sb_door_side"] = side
    for sd in (-1, 1):
        lf = K.box("Door Leaf", (lw, leaf_w, 1.924), (lc, yc + sd * (half - leaf_w / 2 - 0.0005), 0.022 + 0.962), pal["warm"], room.shell, bevel=0.01)
        lf["sb_door"] = did
        lf["sb_group"] = f"door:{did}"
        if sd < 0:
            win = K.box("Door Window", (lw + 0.006, 0.12, 0.5), lf.location + Vector((0, 0.02, 0.45)), M.painted_metal("SB Door Slot", (0.01, 0.01, 0.01, 1), 0.2), room.shell, bevel=0.004)
            win.parent = lf                      # rides the leaf: local offset, no inverse
            win.location = (0.0, 0.02, 0.45)
            win["sb_group"] = f"door:{did}"
        rest = lf.location.y
        fc = lf.driver_add("location", 1)
        drv = fc.driver
        drv.type = "SCRIPTED"
        v = drv.variables.new()
        v.name = "o"
        v.targets[0].id = ctl
        v.targets[0].data_path = '["open"]'
        drv.expression = f"{rest:.5f} + {sd * (leaf_w + 0.0105):.5f} * o"
    # invisible sweep volume: later passes (fixtures, wear) treat the whole path of
    # the sliding leaves as occupied, so an open door never hits anything either
    sw = K.box("Door Sweep", (lw + 0.003, 2 * (half + pocket), 1.93), (lc, yc, 0.022 + 0.962), pal["hull"], room.shell, bevel=0)
    sw.hide_render = True
    sw.display_type = "WIRE"
    sw["sb_ghost"] = did
    room.doors = getattr(room, "doors", []) + [dict(id=did, x=x, yc=yc, half=half, side=side, normal=(-s, 0, 0))]
    return ctl


def door_hole(room, yc, side="right", half=1.0, h=2.25):
    """The shell opening for a door at yc, in that wall's own u coordinates."""
    if side == "right":   # right wall runs -y from the back
        return (room.D - yc - half, room.D - yc + half, 0.0, h)
    return (yc - half, yc + half, 0.0, h)


def set_door(ctl, value, frame=None):
    """Open (1) or close (0) a door; with frame, the state is keyed there."""
    ctl["open"] = float(value)
    if frame is not None:
        ctl.keyframe_insert('["open"]', frame=frame)
