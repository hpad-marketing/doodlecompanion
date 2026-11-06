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


def shell(room, back_holes=(), left_holes=(), right_holes=(), pal_key="panel", panel=(1.0, 0.75)):
    W, D, H = room.W, room.D, room.H
    K.floor(room)
    # back wall: origin bottom-left at (-W/2, D), u = +x, normal = -y
    K.wall(room, (-W / 2, D, 0), (1, 0, 0), (0, 0, 1), W, H, (0, -1, 0), pal_key, panel,
           any_of(*[opening(r) for r in back_holes]), "Back")
    # left wall: origin at (-W/2, 0), u = +y, normal = +x
    K.wall(room, (-W / 2, 0, 0), (0, 1, 0), (0, 0, 1), D, H, (1, 0, 0), pal_key, panel,
           any_of(*[opening(r) for r in left_holes]), "Left")
    # right wall: origin at (W/2, D), u = -y, normal = -x
    K.wall(room, (W / 2, D, 0), (0, -1, 0), (0, 0, 1), D, H, (-1, 0, 0), pal_key, panel,
           any_of(*[opening(r) for r in right_holes]), "Right")
    # corner posts hide panel ends
    for x in (-W / 2 + 0.08, W / 2 - 0.08):
        K.box("Corner Post", (0.16, 0.16, H), (x, D - 0.08, H / 2), room.pal["hull"], room.shell, bevel=0.01)
    # fourth wall: camera-transparent, keeps the room closed for light
    fw = K.box("Fourth Wall", (W, 0.05, H), (0, -0.03, H / 2), room.pal["hull"], room.shell, bevel=0)
    fw.visible_camera = False
    fw.visible_glossy = True
    fw["sb_fourth_wall"] = 1
    # skirting + top trim
    for (a, b) in (((-W / 2, D - 0.02), (W / 2, D - 0.02)),):
        pass
    K.box("Skirting Back", (W, 0.05, 0.12), (0, D - 0.06, 0.06), room.pal["dark_steel"], room.shell, bevel=0.004)
    K.box("Skirting Left", (0.05, D, 0.12), (-W / 2 + 0.06, D / 2, 0.06), room.pal["dark_steel"], room.shell, bevel=0.004)
    K.box("Skirting Right", (0.05, D, 0.12), (W / 2 - 0.06, D / 2, 0.06), room.pal["dark_steel"], room.shell, bevel=0.004)


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
        g = K.box(f"{name} Glass", (w, h, 0.012), c + n * z, room.pal["glass"], room.shell, bevel=0.002)
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
