"""Live screens: every display on the ship plays procedural feeds on its own and
cuts between them at random, each screen on its own clock, with a short glitch
at every cut. Feeds are shader-only (no image files), so they cost nothing to load.

    feeds(scene, seed=1)          # give every screen live feeds and key random cuts
    lock(ob, "RADAR")             # pin one screen to one feed (story beats)
    unlock(ob)

A screen is any object with ob["sb_light"] == "screen" (made by kit.screen).
The material reads two object properties through Attribute nodes:
    sb_feed    which feed is on (stepped keys)
    sb_glitch  0..1 burst at each cut
"""
import math
import random

import bpy

from . import mats as M

FEEDS = ["UI", "LOG", "RADAR", "WAVE", "BARS", "STARS", "SCHEMATIC", "STATIC", "FACE"]
# small screens (keypads, intercoms) keep to simple feeds; the face needs room
SMALL = ["UI", "LOG", "WAVE", "BARS", "STATIC"]


def _time(g):
    """Seconds, driven by the frame, so feeds play in renders and the viewport."""
    v = g.node("ShaderNodeValue")
    v.label = "SB Time"
    fc = v.outputs[0].driver_add("default_value")
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = "frame / 24"
    return v.outputs[0]


def _attr(g, name):
    a = g.node("ShaderNodeAttribute", _attribute_type="OBJECT", _attribute_name=name)
    return a.outputs["Fac"]


def _xy(g, vec):
    s = g.node("ShaderNodeSeparateXYZ")
    g.link(vec, s.inputs[0])
    return s.outputs[0], s.outputs[1]


def _vec(g, x, y, z=0.0):
    c = g.node("ShaderNodeCombineXYZ")
    for i, v in enumerate((x, y, z)):
        g._in(c.inputs[i], v)
    return c.outputs[0]


def feed_material(name, color, strength):
    m, new = M._get(name)
    if not new:
        return m
    g = M.G(m)
    t = _time(g)
    feed = _attr(g, "sb_feed")
    glitch = _attr(g, "sb_glitch")
    seed = g.node("ShaderNodeObjectInfo").outputs["Random"]
    tc = g.node("ShaderNodeTexCoord")
    u, v = _xy(g, tc.outputs["UV"])
    ts = g.math("ADD", t, g.math("MULTIPLY", seed, 100.0))  # each screen at its own point in the loop
    # glitch: horizontal tearing of the UVs at a cut
    tear = g.noise(1.0, 0, 0.5, vec=_vec(g, 0.0, g.math("MULTIPLY", v, 14.0), g.math("MULTIPLY", ts, 30.0)))
    u = g.math("ADD", u, g.math("MULTIPLY", g.math("SUBTRACT", tear.outputs[0], 0.5), g.math("MULTIPLY", glitch, 0.25)))

    out = []
    # 0 UI: framed cells, some live, slowly updating
    br = g.node("ShaderNodeTexBrick", _offset=0.0)
    g.link(_vec(g, u, v), br.inputs["Vector"])
    br.inputs["Scale"].default_value = 3
    br.inputs["Brick Width"].default_value = 0.6
    br.inputs["Row Height"].default_value = 0.22
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Color1"].default_value = (1, 1, 1, 1)
    br.inputs["Color2"].default_value = (0, 0, 0, 1)
    on = g.ramp(br.outputs["Color"], 0.62, 0.66)
    txt = g.ramp(g.noise(1.0, 1, 0.5, vec=_vec(g, g.math("MULTIPLY", u, 70), g.math("MULTIPLY", v, 9), g.math("FLOOR", g.math("MULTIPLY", ts, 2)))).outputs[0], 0.56, 0.6)
    out.append(g.math("ADD", g.math("MULTIPLY", br.outputs["Fac"], 0.35), g.math("MULTIPLY", on, txt)))
    # 1 LOG: text lines scrolling up
    vy = g.math("ADD", v, g.math("MULTIPLY", ts, 0.08))
    line = g.math("FLOOR", g.math("MULTIPLY", vy, 22))
    chars = g.ramp(g.noise(1.0, 1, 0.5, vec=_vec(g, g.math("MULTIPLY", u, 60), line, 0.0)).outputs[0], 0.5, 0.56)
    wn = g.node("ShaderNodeTexWhiteNoise", _noise_dimensions="2D")
    g._in(wn.inputs["Vector"], _vec(g, line, 3.0))
    length = g.math("LESS_THAN", u, g.math("ADD", 0.15, g.math("MULTIPLY", wn.outputs["Value"], 0.8)))
    gap = g.math("GREATER_THAN", g.math("FRACT", g.math("MULTIPLY", vy, 22)), 0.3)
    out.append(g.math("MULTIPLY", g.math("MULTIPLY", chars, length), gap))
    # 2 RADAR: rotating sweep with fading trail, range rings and blips
    cx, cy = g.math("SUBTRACT", u, 0.5), g.math("SUBTRACT", v, 0.5)
    r = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", cx, cx), g.math("MULTIPLY", cy, cy)))
    ang = g.math("DIVIDE", g.math("ARCTAN2", cy, cx), 2 * math.pi)
    sweep = g.math("FRACT", g.math("SUBTRACT", ang, g.math("MULTIPLY", ts, 0.3)))
    trail = g.math("POWER", sweep, 6.0)
    rings = g.ramp(g.math("FRACT", g.math("MULTIPLY", r, 8)), 0.93, 1.0)
    blips = g.ramp(g.node("ShaderNodeTexVoronoi", Scale=7.0, Vector=_vec(g, u, v)).outputs["Distance"], 0.05, 0.02)
    inside = g.math("LESS_THAN", r, 0.48)
    out.append(g.math("MULTIPLY", inside, g.math("ADD", g.math("ADD", g.math("MULTIPLY", trail, 0.8), g.math("MULTIPLY", rings, 0.4)), g.math("MULTIPLY", blips, trail))))
    # 3 WAVE: a voice waveform running across
    amp = g.math("MULTIPLY", g.noise(2.0, 2, 0.5, vec=_vec(g, g.math("ADD", g.math("MULTIPLY", u, 3), g.math("MULTIPLY", ts, 2)), 0.0, 0.0)).outputs[0], 0.5)
    wave = g.math("ADD", 0.5, g.math("MULTIPLY", g.math("SINE", g.math("ADD", g.math("MULTIPLY", u, 60), g.math("MULTIPLY", ts, 9))), g.math("SUBTRACT", amp, 0.1)))
    out.append(g.math("ADD", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", v, wave)), 0.02, 0.005),
                      g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", v, 0.5)), 0.003, 0.0), 0.3)))
    # 4 BARS: a bar graph whose bars rise and fall
    col_ = g.math("FLOOR", g.math("MULTIPLY", u, 14))
    hgt = g.noise(1.5, 0, 0.5, vec=_vec(g, col_, g.math("MULTIPLY", ts, 0.8), 0.0)).outputs[0]
    bar = g.math("MULTIPLY", g.math("LESS_THAN", v, g.ramp(hgt, 0.3, 0.75)), g.math("GREATER_THAN", g.math("FRACT", g.math("MULTIPLY", u, 14)), 0.2))
    out.append(g.math("ADD", bar, g.math("MULTIPLY", g.ramp(g.math("FRACT", g.math("MULTIPLY", v, 5)), 0.97, 1.0), 0.25)))
    # 5 STARS: a star chart drifting past, with a course line
    sv = _vec(g, g.math("ADD", g.math("MULTIPLY", u, 2.0), g.math("MULTIPLY", ts, 0.03)), g.math("MULTIPLY", v, 1.2), 0.0)
    vo = g.node("ShaderNodeTexVoronoi", Scale=14.0, Vector=sv)
    st = g.math("MULTIPLY", g.ramp(vo.outputs["Distance"], 0.07, 0.03), g.math("ADD", 0.4, g.math("MULTIPLY", g.node("ShaderNodeSeparateColor", Color=vo.outputs["Color"]).outputs[0], 1.2)))
    course = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", v, g.math("ADD", 0.5, g.math("MULTIPLY", g.math("SINE", g.math("MULTIPLY", u, 4)), 0.2)))), 0.006, 0.0)
    grid = g.math("MULTIPLY", g.ramp(g.math("FRACT", g.math("MULTIPLY", u, 8)), 0.98, 1.0), 0.15)
    out.append(g.math("ADD", g.math("ADD", st, g.math("MULTIPLY", course, 0.7)), grid))
    # 6 SCHEMATIC: ship outline rings with a scanning line
    ell = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", g.math("MULTIPLY", cx, 0.6), g.math("MULTIPLY", cx, 0.6)), g.math("MULTIPLY", g.math("MULTIPLY", cy, 1.8), g.math("MULTIPLY", cy, 1.8))))
    hull = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", g.math("FRACT", g.math("MULTIPLY", ell, 5)), 0.5)), 0.48, 0.5)
    scan = g.ramp(g.math("ABSOLUTE", g.math("SUBTRACT", u, g.math("FRACT", g.math("MULTIPLY", ts, 0.15)))), 0.01, 0.0)
    out.append(g.math("ADD", g.math("MULTIPLY", hull, g.math("LESS_THAN", ell, 0.42)), scan))
    # 7 STATIC: snow
    snow = g.node("ShaderNodeTexWhiteNoise", _noise_dimensions="3D")
    g._in(snow.inputs["Vector"], _vec(g, g.math("FLOOR", g.math("MULTIPLY", u, 160)), g.math("FLOOR", g.math("MULTIPLY", v, 100)), g.math("FLOOR", g.math("MULTIPLY", ts, 24))))
    out.append(g.math("MULTIPLY", g.math("POWER", snow.outputs["Value"], 2.0), 0.9))
    # 8 FACE: the ship's computer: two eyes that blink and a talking mouth line
    eye = lambda ex: g.ramp(g.math("SQRT", g.math("ADD", g.math("MULTIPLY", g.math("SUBTRACT", u, ex), g.math("SUBTRACT", u, ex)),
                                                     g.math("MULTIPLY", g.math("MULTIPLY", g.math("SUBTRACT", v, 0.62), 2.2), g.math("MULTIPLY", g.math("SUBTRACT", v, 0.62), 2.2)))), 0.07, 0.05)
    blink = g.math("GREATER_THAN", g.math("FRACT", g.math("MULTIPLY", ts, 0.27)), 0.04)
    talk = g.math("MULTIPLY", g.noise(4.0, 0, 0.5, vec=_vec(g, g.math("MULTIPLY", ts, 3), 0.0, 0.0)).outputs[0], 0.035)
    mouth = g.math("MULTIPLY", g.math("LESS_THAN", g.math("ABSOLUTE", g.math("SUBTRACT", v, 0.32)), g.math("ADD", talk, 0.004)),
                   g.math("LESS_THAN", g.math("ABSOLUTE", g.math("SUBTRACT", u, 0.5)), 0.16))
    out.append(g.math("ADD", g.math("MULTIPLY", g.math("ADD", eye(0.38), eye(0.62)), blink), mouth))

    # pick the feed that is on: weight_i = 1 when |feed - i| < 0.5
    lum = None
    for i, f in enumerate(out):
        w = g.math("LESS_THAN", g.math("ABSOLUTE", g.math("SUBTRACT", feed, float(i))), 0.5)
        term = g.math("MULTIPLY", f, w)
        lum = term if lum is None else g.math("ADD", lum, term)
    # scanlines, a dim base glow, and the glitch flash
    sc = g.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="Y")
    g.link(tc.outputs["UV"], sc.inputs["Vector"])
    sc.inputs["Scale"].default_value = 260
    lum = g.math("ADD", g.math("MULTIPLY", g.math("MINIMUM", lum, 1.2), g.mixf(g.ramp(sc.outputs["Fac"], 0.0, 0.6), 0.75, 1.0)), 0.015)
    lum = g.math("ADD", lum, g.math("MULTIPLY", glitch, g.ramp(tear.outputs[0], 0.55, 0.7)))
    em = g.math("MULTIPLY", lum, strength)
    bsdf = g.node("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.01, 0.012, 0.015, 1)
    bsdf.inputs["Roughness"].default_value = 0.08
    bsdf.inputs["Coat Weight"].default_value = 1.0
    bsdf.inputs["Coat Roughness"].default_value = 0.03
    bsdf.inputs["Emission Color"].default_value = color
    g._in(bsdf.inputs["Emission Strength"], em)
    bsdf.name = "SB_Emit"
    g.out(bsdf)
    m["sb_emit"] = 1
    m["sb_color"] = list(color)
    m["sb_strength"] = strength
    m["sb_role"] = "screen"
    m["sb_feeds"] = 1
    return m


def screens(scene=None):
    scene = scene or bpy.context.scene
    return [o for o in scene.objects if o.get("sb_light") == "screen" and o.type == "MESH"]


def _menu(ob):
    w, h = ob.dimensions.x, ob.dimensions.y
    return FEEDS if w * h > 0.04 and w > 0.25 else SMALL


def _key_cuts(ob, rng, f0, f1, fps, lo=4.0, hi=12.0):
    ob.animation_data_clear()  # screens carry no other animation
    menu = _menu(ob)
    f = f0 - int(rng.uniform(0, hi) * fps)  # start mid-cycle so screens never cut together at frame 1
    cur = rng.choice(menu)
    while f <= f1:
        ob["sb_feed"] = float(FEEDS.index(cur))
        ob.keyframe_insert('["sb_feed"]', frame=max(f, f0 - 1))
        for df, gv in ((-1, 0.0), (0, 1.0), (2, 0.0)):  # 2-frame glitch at the cut
            ob["sb_glitch"] = gv
            ob.keyframe_insert('["sb_glitch"]', frame=max(f + df, f0 - 1))
        f += max(2, int(rng.uniform(lo, hi) * fps))
        cur = rng.choice([x for x in menu if x != cur])
    _constant(ob)


def _constant(ob):
    from .wear import _fcurves
    for fc in _fcurves(ob.animation_data.action):
        if fc.data_path in ('["sb_feed"]', '["sb_glitch"]'):
            for k in fc.keyframe_points:
                k.interpolation = "CONSTANT"


def feeds(scene=None, seed=1, lo=4.0, hi=12.0):
    """Give every screen live feeds and random cuts over the scene's frame range."""
    scene = scene or bpy.context.scene
    fps = scene.render.fps / scene.render.fps_base
    n = 0
    for ob in screens(scene):
        old = ob.active_material
        col = tuple(old.get("sb_color", (0.3, 0.85, 1, 1))) if old else (0.3, 0.85, 1, 1)
        stg = float(old.get("sb_strength", 1.4)) if old else 1.4
        ob.data.materials.clear()
        ob.data.materials.append(feed_material(f"SB Feed {round(stg, 2)} {tuple(round(c, 2) for c in col)}", col, stg))
        ob["sb_glitch"] = 0.0
        if ob.get("sb_feed_lock") is not None:
            ob["sb_feed"] = float(FEEDS.index(ob["sb_feed_lock"]))
        else:
            rng = random.Random(f"{seed}|{ob.name}")
            _key_cuts(ob, rng, scene.frame_start, scene.frame_end, fps, lo, hi)
        n += 1
    return n


def lock(ob, feed):
    ob["sb_feed_lock"] = feed
    if ob.animation_data:
        ob.animation_data_clear()
    ob["sb_feed"] = float(FEEDS.index(feed))
    ob["sb_glitch"] = 0.0


def unlock(ob, seed=1):
    if "sb_feed_lock" in ob:
        del ob["sb_feed_lock"]
    sc = bpy.context.scene
    _key_cuts(ob, random.Random(f"{seed}|{ob.name}"), sc.frame_start, sc.frame_end, sc.render.fps / sc.render.fps_base)
