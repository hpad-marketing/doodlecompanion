"""Backdrops for the ship presets: deep space and a planet landing site.

    stage.build("space")   starfield + nebula world, key/rim suns, distant planet
    stage.build("planet")  alien desert with a landing pad at the origin (pad top z = 0)
Everything goes in the "Hero Ship Stage" collection; building again replaces it.
"""
import math
import random
import bmesh
import bpy
from mathutils import Vector, noise
from . import geo
from .mats import N, _bsdf, _get

STAGE = "Hero Ship Stage"
PAD_R = 40.0


def clear():
    c = bpy.data.collections.get(STAGE)
    if c:
        for o in list(c.all_objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)


def _world_space(name="HS Space"):
    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    n = N(w)
    tc = n("ShaderNodeTexCoord")
    d = tc.outputs["Generated"]
    stars = None
    for scale, thr, gain in ((180.0, 0.05, 60.0), (420.0, 0.07, 20.0), (900.0, 0.09, 6.0)):
        vo = n("ShaderNodeTexVoronoi", Scale=scale, Randomness=1.0)
        vo.feature = "F1"
        n.set(vo.inputs["Vector"], d)
        pt = n.math("LESS_THAN", vo.outputs["Distance"], thr)
        sepc = n("ShaderNodeSeparateColor")
        n.set(sepc.inputs[0], vo.outputs["Color"])
        bright = n.math("POWER", sepc.outputs[0], 5.0)
        s = n.math("MULTIPLY", pt, n.math("MULTIPLY", bright, gain))
        stars = s if stars is None else n.math("ADD", stars, s)
    neb = n.noise(d, 1.6, 10, 0.62)
    nm = n("ShaderNodeValToRGB")
    n.set(nm.inputs[0], neb)
    el = nm.color_ramp.elements
    el[0].position, el[0].color = 0.45, (0.0, 0.0, 0.0, 1)
    el[1].position, el[1].color = 0.85, (0.10, 0.35, 0.40, 1)
    e = el.new(0.68)
    e.color = (0.12, 0.05, 0.18, 1)
    band = n.noise(d, 0.6, 3, 0.5)
    neb_c = n.mix(n.ramp(band, [(0.4, 0.0), (0.7, 1.0)]), (0, 0, 0), nm.outputs[0])
    starc = n("ShaderNodeCombineColor")
    n.set(starc.inputs[0], stars)
    n.set(starc.inputs[1], stars)
    n.set(starc.inputs[2], n.math("MULTIPLY", stars, 1.15))
    col = n.mix(1.0, neb_c, starc.outputs[0], "ADD")
    bg = n("ShaderNodeBackground", Strength=0.5)
    n.set(bg.inputs["Color"], col)
    o = n("ShaderNodeOutputWorld")
    n.set(o.inputs["Surface"], bg)
    return w


def _world_sky(name="HS Planet Sky"):
    w = bpy.data.worlds.get(name) or bpy.data.worlds.new(name)
    n = N(w)
    tc = n("ShaderNodeTexCoord")
    sep = n("ShaderNodeSeparateXYZ")
    n.set(sep.inputs[0], tc.outputs["Generated"])
    g = n("ShaderNodeValToRGB")
    n.set(g.inputs[0], n.math("MULTIPLY_ADD", sep.outputs["Z"], 0.5, 0.5))
    el = g.color_ramp.elements
    el[0].position, el[0].color = 0.45, (0.55, 0.33, 0.20, 1)
    el[1].position, el[1].color = 0.95, (0.30, 0.42, 0.55, 1)
    e = el.new(0.53)
    e.color = (0.90, 0.66, 0.46, 1)
    bg = n("ShaderNodeBackground", Strength=2.0)
    n.set(bg.inputs["Color"], g.outputs[0])
    o = n("ShaderNodeOutputWorld")
    n.set(o.inputs["Surface"], bg)
    return w


def aim_key(target=(0, 0, 0), cam=None, turn=55.0, elev=35.0):
    """Swings the key sun so it lights the ship from the camera's side (3/4)."""
    sun = bpy.data.objects.get("HS Key Sun")
    cam = cam or bpy.context.scene.camera
    if not sun or not cam:
        return
    from mathutils import Matrix
    d = cam.matrix_world.translation - Vector(target)
    d.z = 0
    if d.length < 1e-6:
        d = Vector((1, 0, 0))
    d = Matrix.Rotation(math.radians(turn), 3, "Z") @ d.normalized()
    L = Vector((d.x * math.cos(math.radians(elev)), d.y * math.cos(math.radians(elev)), math.sin(math.radians(elev))))
    sun.rotation_euler = (-L).to_track_quat("-Z", "Y").to_euler()


def _sun(c, name, rot, energy, color, angle=0.6):
    l = bpy.data.lights.new(name, "SUN")
    l.energy = energy
    l.color = color
    l.angle = math.radians(angle)
    ob = bpy.data.objects.new(name, l)
    c.objects.link(ob)
    ob.rotation_euler = [math.radians(a) for a in rot]
    return ob


def _planet(c, center, radius):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=radius)
    me = bpy.data.meshes.new("Planet")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Planet", me)
    c.objects.link(ob)
    ob.location = center
    m = _get("HS Planet Surface")
    n = N(m)
    tc = n("ShaderNodeTexCoord")
    h = n.noise(tc.outputs["Object"], 0.004 * 600 / radius * 2, 12, 0.6)
    col = n("ShaderNodeValToRGB")
    n.set(col.inputs[0], h)
    el = col.color_ramp.elements
    el[0].position, el[0].color = 0.35, (0.05, 0.10, 0.16, 1)
    el[1].position, el[1].color = 0.75, (0.70, 0.55, 0.40, 1)
    e = el.new(0.5)
    e.color = (0.32, 0.25, 0.20, 1)
    clouds = n.ramp(n.noise(tc.outputs["Object"], 0.01 * 600 / radius * 2, 8, 0.7, stretch=(1, 1, 3)), [(0.55, 0.0), (0.7, 1.0)])
    cc = n.mix(clouds, col.outputs[0], (0.9, 0.9, 0.92))
    lw = n("ShaderNodeLayerWeight", Blend=0.18)
    b = _bsdf(n, **{"Base Color": cc, "Roughness": 0.8, "Emission Color": (0.25, 0.55, 1.0, 1),
                    "Emission Strength": n.math("MULTIPLY", lw.outputs["Fresnel"], 3.0)})
    n.out(b)
    me.materials.append(m)
    ob["sb_skip"] = 1
    return ob


def build_space(c):
    sc = bpy.context.scene
    sc.world = _world_space()
    _sun(c, "HS Key Sun", (35, 15, 125), 5.0, (1.0, 0.93, 0.84), 0.5)
    _sun(c, "HS Rim Sun", (-30, 170, -60), 1.6, (0.55, 0.75, 1.0), 2.0)
    _planet(c, (-2600, 5200, -1500), 1900)


def _terrain_h(x, y):
    d = math.hypot(x, y)
    if d < PAD_R + 2:
        return -0.03
    t = min(1.0, (d - PAD_R - 2) / 40.0)
    t = t * t * (3 - 2 * t)
    v = Vector((x * 0.012, y * 0.012, 0.0))
    h = noise.fractal(v, 0.6, 2.0, 5) * 6.0
    h += noise.ridged_multi_fractal(Vector((x * 0.004, y * 0.004, 1.3)), 0.8, 2.0, 4, 0.9, 2.0) * 14.0 * min(1.0, d / 400.0)
    return -0.03 + t * h


def build_planet(c):
    sc = bpy.context.scene
    sc.world = _world_sky()
    _sun(c, "HS Key Sun", (52, 8, 140), 4.2, (1.0, 0.85, 0.68), 1.0)
    # terrain: a radial grid (dense near the pad, sparse far away)
    bm = bmesh.new()
    rings, segs = 90, 160
    rad = [PAD_R * 0.6 * (1.045 ** i) - PAD_R * 0.6 + 0.5 for i in range(rings)]
    rad = [r * 1600.0 / rad[-1] if i else 0.0 for i, r in enumerate(rad)]
    centre = bm.verts.new((0, 0, -0.03))
    prev = None
    for i, r in enumerate(rad[1:]):
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            x, y = r * math.cos(a), r * math.sin(a)
            ring.append(bm.verts.new((x, y, _terrain_h(x, y))))
        if prev is None:
            for k in range(segs):
                bm.faces.new((centre, ring[k], ring[(k + 1) % segs]))
        else:
            for k in range(segs):
                bm.faces.new((prev[k], ring[k], ring[(k + 1) % segs], prev[(k + 1) % segs]))
        prev = ring
    geo.box_uv(bm, scale=0.1)
    me = bpy.data.meshes.new("Terrain")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    t = bpy.data.objects.new("Terrain", me)
    c.objects.link(t)
    m = _get("HS Terrain")
    n = N(m)
    tc = n("ShaderNodeTexCoord")
    v = tc.outputs["Object"]
    big = n.noise(v, 0.02, 8, 0.6)
    col = n("ShaderNodeValToRGB")
    n.set(col.inputs[0], n.math("ADD", big, n.math("MULTIPLY", n.noise(v, 0.4, 6, 0.6), 0.25)))
    el = col.color_ramp.elements
    el[0].position, el[0].color = 0.35, (0.30, 0.17, 0.10, 1)
    el[1].position, el[1].color = 0.8, (0.62, 0.42, 0.28, 1)
    pebbles = n.ramp(n.noise(v, 6.0, 4, 0.6), [(0.6, 0.0), (0.68, 1.0)])
    cc = n.mix(n.math("MULTIPLY", pebbles, 0.5), col.outputs[0], (0.16, 0.10, 0.07))
    bump = n("ShaderNodeBump", Strength=0.5, Distance=0.05)
    n.set(bump.inputs["Height"], n.math("ADD", n.noise(v, 3.0, 8, 0.65), n.math("MULTIPLY", pebbles, 0.6)))
    b = _bsdf(n, **{"Base Color": cc, "Roughness": 0.92, "Normal": bump.outputs[0]})
    n.out(b)
    me.materials.append(m)
    # landing pad (top at z = 0): worn concrete disc with painted ring and arrows
    bm = bmesh.new()
    geo.lathe(bm, [(0.0, 0.0), (PAD_R, 0.0), (PAD_R + 0.4, -0.25), (PAD_R + 0.4, -0.6)], segs=96)
    for f in bm.faces:
        f.material_index = 0
    geo.lathe(bm, [(PAD_R - 2.6, 0.004), (PAD_R - 1.8, 0.004)], segs=96)
    for k in range(8):
        a = 2 * math.pi * k / 8
        geo.add_box(bm, Vector((math.cos(a) * 14.0, math.sin(a) * 14.0, 0.002)), (3.2, 0.5, 0.004),
                    rot=__import__("mathutils").Matrix.Rotation(a, 4, "Z"))
    for f in bm.faces:
        if f.calc_center_median().z > 0.001:
            f.material_index = 1
    geo.box_uv(bm, scale=0.15)
    me = bpy.data.meshes.new("Landing Pad")
    bm.to_mesh(me)
    bm.free()
    pad = bpy.data.objects.new("Landing Pad", me)
    c.objects.link(pad)
    pm = _get("HS Pad Concrete")
    n = N(pm)
    tc = n("ShaderNodeTexCoord")
    v = tc.outputs["Object"]
    cc = n.mix(n.ramp(n.noise(v, 0.15, 8, 0.6), [(0.3, 0.0), (0.8, 1.0)]), (0.42, 0.38, 0.33), (0.25, 0.20, 0.16))
    b = _bsdf(n, **{"Base Color": cc, "Roughness": 0.85})
    n.out(b)
    paint = _get("HS Pad Paint")
    n = N(paint)
    tc = n("ShaderNodeTexCoord")
    worn = n.ramp(n.noise(tc.outputs["Object"], 1.5, 8, 0.7), [(0.35, 0.0), (0.6, 1.0)])
    b = _bsdf(n, **{"Base Color": n.mix(worn, (0.30, 0.25, 0.20), (0.85, 0.55, 0.15)), "Roughness": 0.7})
    n.out(b)
    me.materials.append(pm)
    me.materials.append(paint)
    # rocks scattered outside the pad, sunk into the ground
    rnd = random.Random(7)
    rm = _get("HS Rock")
    n = N(rm)
    tc = n("ShaderNodeTexCoord")
    bump = n("ShaderNodeBump", Strength=0.6)
    n.set(bump.inputs["Height"], n.noise(tc.outputs["Object"], 4.0, 10, 0.7))
    b = _bsdf(n, **{"Base Color": (0.22, 0.14, 0.10), "Roughness": 0.9, "Normal": bump.outputs[0]})
    n.out(b)
    rb = bmesh.new()
    for i in range(140):
        d = rnd.uniform(PAD_R + 6, 260)
        a = rnd.uniform(0, 2 * math.pi)
        x, y = d * math.cos(a), d * math.sin(a)
        r = rnd.uniform(0.4, 2.8) * (1 + d / 200)
        res = bmesh.ops.create_icosphere(rb, subdivisions=2, radius=r)
        vs = res["verts"]
        for vv in vs:
            p = vv.co
            k = 1 + 0.35 * noise.noise(Vector((p.x * 0.8 + i, p.y * 0.8, p.z * 0.8)))
            vv.co = Vector((p.x * k, p.y * k * rnd.uniform(0.8, 1.2), p.z * k * 0.6))
        bmesh.ops.translate(rb, vec=(x, y, _terrain_h(x, y) - r * 0.25), verts=vs)
    me = bpy.data.meshes.new("Rocks")
    rb.to_mesh(me)
    rb.free()
    rk = bpy.data.objects.new("Rocks", me)
    c.objects.link(rk)
    me.materials.append(rm)
    for p in me.polygons:
        p.use_smooth = True
    return t, pad


def build(kind="space"):
    clear()
    c = geo.coll(STAGE)
    if kind == "planet":
        build_planet(c)
    else:
        build_space(c)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    return c
