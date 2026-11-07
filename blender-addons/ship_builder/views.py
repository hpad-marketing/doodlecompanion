"""Switchable views outside the windows. One world shader holds every view and
a sun light matches it, so the light through the windows changes with the view.

    build(scene)                   # make the world + sun (called by ship.build and room builds)
    set_view("SUNRISE")            # switch now
    set_view("HYPERSPACE", frame=120)   # switch on the timeline (stepped keys)

Views live in VIEWS; scene["sb_view"] holds the current index. Windows face +Y
(the back wall), so every view is composed around the +Y direction.
"""
import math

import bpy

from . import mats as M

VIEWS = {
    # key: (label, sun energy W/m2, sun colour, sun direction it shines TOWARD)
    # Deep space keeps each room's own planet and star (rooms/common.planet), so its sun is off
    "DEEP_SPACE": ("Deep space", 0.0, (0.85, 0.9, 1.0), (-0.3, -1.0, -0.35)),
    "RINGED_PLANET": ("Ringed planet", 1.2, (1.0, 0.88, 0.72), (-0.6, -1.0, -0.3)),
    "NEBULA": ("Nebula", 0.5, (0.85, 0.55, 1.0), (0.2, -1.0, -0.2)),
    "ASTEROIDS": ("Asteroid field", 0.9, (1.0, 0.95, 0.88), (0.5, -1.0, -0.4)),
    "HYPERSPACE": ("Hyperspace", 1.6, (0.65, 0.8, 1.0), (0.0, -1.0, 0.0)),
    "STATION": ("Docked at a station", 1.4, (0.95, 0.97, 1.0), (0.1, -1.0, -0.6)),
    "BLUE_PLANET": ("Orbiting a blue planet", 1.3, (0.75, 0.88, 1.0), (0.0, -1.0, 0.5)),
    "SUNRISE": ("Sunrise over a planet", 4.0, (1.0, 0.62, 0.32), (0.25, -1.0, 0.08)),
}
KEYS = list(VIEWS)
WORLD = "SB Outside"
SUN = "SB Outside Sun"


def _norm(v):
    l = math.sqrt(sum(c * c for c in v))
    return tuple(c / l for c in v)


class _W:
    """Lets mats.G build into a world node tree."""
    def __init__(self, w):
        self.node_tree = w.node_tree


def _dot(g, d, c):
    """dot(D, constant direction) using a Vector Math node."""
    nd = g.node("ShaderNodeVectorMath", _operation="DOT_PRODUCT")
    g._in(nd.inputs[0], d)
    nd.inputs[1].default_value = c
    return nd.outputs["Value"]


def _sub(g, d, c):
    nd = g.node("ShaderNodeVectorMath", _operation="SUBTRACT")
    g._in(nd.inputs[0], d)
    nd.inputs[1].default_value = c
    return nd.outputs[0]


def _sep(g, v):
    s = g.node("ShaderNodeSeparateXYZ")
    g._in(s.inputs[0], v)
    return s.outputs[0], s.outputs[1], s.outputs[2]


def _rgb(g, f, col):
    """A colour scaled by a float mask."""
    nd = g.node("ShaderNodeVectorMath", _operation="SCALE")
    nd.inputs[0].default_value = col[:3]
    g._in(nd.inputs["Scale"], f)
    return nd.outputs[0]


def _add(g, a, b):
    nd = g.node("ShaderNodeVectorMath", _operation="ADD")
    g._in(nd.inputs[0], a)
    g._in(nd.inputs[1], b)
    return nd.outputs[0]


def _disc(g, d, centre, radius):
    """(inside mask, offset vector from centre) for a round body seen at `centre`."""
    c = _norm(centre)
    inside = g.math("GREATER_THAN", _dot(g, d, c), math.cos(radius))
    return inside, _sub(g, d, c)


def _stars(g, d, scale=160, cut=0.05, gain=10.0):
    """Stars of many brightnesses; most faint, a few bright."""
    vo = g.node("ShaderNodeTexVoronoi")
    vo.inputs["Scale"].default_value = scale
    g._in(vo.inputs["Vector"], d)
    b = g.math("POWER", g.node("ShaderNodeSeparateColor", Color=vo.outputs["Color"]).outputs[0], 3.0)
    return g.math("MULTIPLY", g.math("MULTIPLY", g.ramp(vo.outputs["Distance"], cut, 0.0), gain), b)


def build(scene=None, ambient=0.03):
    scene = scene or bpy.context.scene
    w = bpy.data.worlds.get(WORLD) or bpy.data.worlds.new(WORLD)
    w.use_nodes = True
    w.node_tree.nodes.clear()
    g = M.G(_W(w))
    d = g.node("ShaderNodeTexCoord").outputs["Generated"]
    dx, dy, dz = _sep(g, d)
    sel = g.node("ShaderNodeValue")
    sel.name = sel.label = "SB View"
    sel.outputs[0].default_value = float(scene.get("sb_view", 0))
    stars = _stars(g, d)
    layers = []

    # 0 deep space: stars and a faint violet nebula
    neb = g.ramp(g.noise(1.4, 8, 0.6, vec=d).outputs[0], 0.55, 0.8)
    layers.append(_add(g, _rgb(g, g.math("MULTIPLY", neb, 0.02), (0.25, 0.1, 0.45)), _rgb(g, stars, (1, 1, 1))))

    # 1 ringed planet, lit from the right, banded, with a tilted ring
    r1 = 0.2
    ins, off = _disc(g, d, (-0.1, 1.0, 0.07), r1)  # framed by a window seen from across the room
    ox, oy, oz = _sep(g, off)
    lit = g.math("POWER", g.ramp(g.math("ADD", g.math("MULTIPLY", ox, 1.0), g.math("MULTIPLY", oz, 0.5)), -0.3, 0.25), 1.6)
    bands = g.noise(2.0, 4, 0.5, vec=_add(g, g.node("ShaderNodeCombineXYZ", Z=g.math("MULTIPLY", oz, 22.0)).outputs[0], (0, 0, 0)))
    pcol = g.mix(g.ramp(bands.outputs[0], 0.35, 0.65), (0.42, 0.24, 0.12, 1), (0.82, 0.66, 0.45, 1))
    planet = g.node("ShaderNodeVectorMath", _operation="SCALE")
    g._in(planet.inputs[0], pcol)
    g._in(planet.inputs["Scale"], g.math("MULTIPLY", g.math("MULTIPLY", lit, ins), 1.4))
    # ring: an ellipse around the planet (flattened in z, tilted by mixing in x)
    rz = g.math("ADD", g.math("MULTIPLY", oz, 4.2), g.math("MULTIPLY", ox, 0.9))
    rr = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", ox, ox), g.math("MULTIPLY", rz, rz)))
    ring = g.math("MULTIPLY", g.ramp(rr, r1 * 1.35, r1 * 1.45), g.ramp(rr, r1 * 2.2, r1 * 2.05))
    ring = g.math("MULTIPLY", ring, g.math("ADD", 0.5, g.math("MULTIPLY", g.node("ShaderNodeTexWave", _wave_type="RINGS", Scale=60.0, Vector=off).outputs["Fac"], 0.5)))
    front = g.math("MAXIMUM", g.math("SUBTRACT", 1.0, ins), g.math("LESS_THAN", rz, 0.0))  # ring hides behind the top half
    ringc = _rgb(g, g.math("MULTIPLY", g.math("MULTIPLY", ring, front), 0.9), (0.85, 0.78, 0.62))
    layers.append(_add(g, _add(g, planet.outputs[0], ringc), _rgb(g, g.math("MULTIPLY", stars, g.math("SUBTRACT", 1.0, ins)), (1, 1, 1))))

    # 2 nebula: bright clouds in magenta and teal
    n1 = g.noise(1.2, 10, 0.62, vec=d)
    n2 = g.noise(2.6, 8, 0.55, vec=d)
    c1 = _rgb(g, g.math("MULTIPLY", g.ramp(n1.outputs[0], 0.45, 0.75), 0.55), (0.9, 0.2, 0.6))
    c2 = _rgb(g, g.math("MULTIPLY", g.ramp(n2.outputs[0], 0.5, 0.78), 0.4), (0.1, 0.7, 0.8))
    layers.append(_add(g, _add(g, c1, c2), _rgb(g, g.math("MULTIPLY", stars, 1.5), (1, 0.95, 0.9))))

    # 3 asteroid field: lumpy rocks of many sizes in a band, lit from one side
    vo = g.node("ShaderNodeTexVoronoi", _feature="F1")
    vo.inputs["Scale"].default_value = 12.0
    lump = g.noise(14.0, 4, 0.6, vec=d)
    g._in(vo.inputs["Vector"], _add(g, d, _rgb(g, g.math("MULTIPLY", lump.outputs[0], 0.06), (1, 1, 1))))
    size = g.math("MULTIPLY", g.node("ShaderNodeSeparateColor", Color=vo.outputs["Color"]).outputs[0], 0.46)
    rock = g.math("LESS_THAN", vo.outputs["Distance"], size)
    band = g.ramp(g.math("ABSOLUTE", dz), 0.55, 0.15)
    rock = g.math("MULTIPLY", rock, band)
    shade = g.ramp(g.math("ADD", g.math("MULTIPLY", g.node("ShaderNodeTexNoise", Scale=40.0, Vector=d).outputs[0], 0.6), dx), 0.1, 1.0)
    rocks = _rgb(g, g.math("MULTIPLY", rock, g.math("MULTIPLY", shade, 1.6)), (0.42, 0.36, 0.3))
    layers.append(_add(g, rocks, _rgb(g, g.math("MULTIPLY", stars, g.math("SUBTRACT", 1.0, rock)), (1, 1, 1))))

    # 4 hyperspace: streaks rushing past the +Y axis, a bright tunnel at the centre
    phi = g.math("ARCTAN2", dz, dx)
    lane = g.node("ShaderNodeTexWhiteNoise", _noise_dimensions="1D")
    g._in(lane.inputs["W"], g.math("FLOOR", g.math("MULTIPLY", phi, 160.0)))
    streak = g.math("GREATER_THAN", lane.outputs["Value"], 0.82)
    along = g.ramp(dy, 0.2, 0.95)
    tunnel = g.math("POWER", g.ramp(dy, 0.96, 1.0), 2.0)
    flick = g.node("ShaderNodeTexWhiteNoise", _noise_dimensions="1D")
    g._in(flick.inputs["W"], g.math("ADD", g.math("FLOOR", g.math("MULTIPLY", phi, 160.0)), 0.37))
    hy = g.math("ADD", g.math("MULTIPLY", g.math("MULTIPLY", streak, g.math("POWER", along, 2.0)), g.math("MULTIPLY", flick.outputs["Value"], 1.4)), g.math("MULTIPLY", tunnel, 2.0))
    layers.append(_rgb(g, g.math("ADD", hy, g.math("MULTIPLY", along, 0.03)), (0.45, 0.65, 1.0)))

    # 5 docked at a station: a lit hull wall with panel lines, windows and docking lights
    py = g.math("MAXIMUM", dy, 0.05)
    pu, pv = g.math("DIVIDE", dx, py), g.math("DIVIDE", dz, py)
    br = g.node("ShaderNodeTexBrick", _offset=0.0)
    br.inputs["Scale"].default_value = 1.6
    br.inputs["Brick Width"].default_value = 1.7
    br.inputs["Row Height"].default_value = 0.33
    br.inputs["Mortar Size"].default_value = 0.006
    br.inputs["Color1"].default_value = (0.2, 0.21, 0.22, 1)
    br.inputs["Color2"].default_value = (0.13, 0.135, 0.145, 1)
    br.inputs["Mortar"].default_value = (0.02, 0.02, 0.025, 1)
    g._in(br.inputs["Vector"], g.node("ShaderNodeCombineXYZ", X=pu, Y=pv).outputs[0])
    wins = g.math("MULTIPLY", g.math("GREATER_THAN", g.node("ShaderNodeTexWhiteNoise", _noise_dimensions="2D",
                  Vector=g.node("ShaderNodeCombineXYZ", X=g.math("FLOOR", g.math("MULTIPLY", pu, 24)), Y=g.math("FLOOR", g.math("MULTIPLY", pv, 40))).outputs[0]).outputs["Value"], 0.9), 2.5)
    strip = g.math("LESS_THAN", g.math("FRACT", g.math("MULTIPLY", pv, 40)), 0.35)  # windows sit in thin rows
    wins = g.math("MULTIPLY", wins, g.math("MULTIPLY", strip, g.math("LESS_THAN", g.math("FRACT", g.math("MULTIPLY", pv, 4.0)), 0.25)))
    # the station is a big block with a curved top edge, space around it
    wall = g.math("MULTIPLY", g.math("GREATER_THAN", dy, 0.45), g.math("LESS_THAN", g.math("ADD", pv, g.math("MULTIPLY", g.math("MULTIPLY", pu, pu), 0.25)), 0.5))
    wall = g.math("MULTIPLY", wall, g.math("GREATER_THAN", pv, -1.2))
    hull = g.node("ShaderNodeVectorMath", _operation="SCALE")
    g._in(hull.inputs[0], br.outputs["Color"])
    g._in(hull.inputs["Scale"], g.math("MULTIPLY", wall, 1.2))
    layers.append(_add(g, _add(g, hull.outputs[0], _rgb(g, g.math("MULTIPLY", wins, wall), (1.0, 0.85, 0.55))),
                       _rgb(g, g.math("MULTIPLY", stars, g.math("SUBTRACT", 1.0, wall)), (1, 1, 1))))

    # 6 orbit over a blue planet: the planet fills the lower view, clouds and a glowing rim
    rb = 1.05
    ins6, off6 = _disc(g, d, (0.0, 1.0, -1.7), rb)
    edge = g.math("SUBTRACT", _dot(g, d, _norm((0.0, 1.0, -1.7))), math.cos(rb))  # 0 at the rim, grows inward
    warp = g.noise(2.0, 6, 0.6, vec=d)
    cloud = g.ramp(g.noise(7.0, 12, 0.68, vec=_add(g, d, _rgb(g, g.math("MULTIPLY", warp.outputs[0], 0.25), (1, 1, 1)))).outputs[0], 0.52, 0.72)
    land = g.ramp(g.noise(2.5, 8, 0.6, vec=d).outputs[0], 0.58, 0.6)
    ground = g.mix(land, (0.02, 0.09, 0.28, 1), (0.16, 0.2, 0.1, 1))
    sea = g.mix(cloud, ground, (0.85, 0.88, 0.92, 1))
    day = g.ramp(dx, 0.45, -0.3)  # terminator across the planet
    bp = g.node("ShaderNodeVectorMath", _operation="SCALE")
    g._in(bp.inputs[0], sea)
    g._in(bp.inputs["Scale"], g.math("MULTIPLY", ins6, g.math("ADD", 0.05, g.math("MULTIPLY", day, 0.9))))
    rim = g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", edge), 0.04, 0.0), 1.6)
    layers.append(_add(g, _add(g, bp.outputs[0], _rgb(g, rim, (0.35, 0.6, 1.0))),
                       _rgb(g, g.math("MULTIPLY", stars, g.math("SUBTRACT", 1.0, ins6)), (1, 1, 1))))

    # 7 sunrise: the planet's dark side below, an orange rim, and the sun breaking over it
    ins7, _ = _disc(g, d, (0.0, 1.0, -1.7), rb)
    sun_dir = _norm((-0.25, 1.0, -0.06))
    sun = g.math("POWER", g.math("MAXIMUM", _dot(g, d, sun_dir), 0.0), 900.0)
    glare = g.math("POWER", g.math("MAXIMUM", _dot(g, d, sun_dir), 0.0), 18.0)
    above = g.math("SUBTRACT", 1.0, ins7)
    dark = _rgb(g, g.math("MULTIPLY", ins7, g.math("MULTIPLY", glare, 0.25)), (0.25, 0.1, 0.05))
    rim7 = _rgb(g, g.math("MULTIPLY", g.ramp(g.math("ABSOLUTE", edge), 0.05, 0.0), g.math("ADD", 0.3, g.math("MULTIPLY", glare, 3.0))), (1.0, 0.45, 0.15))
    sky = _rgb(g, g.math("MULTIPLY", above, g.math("ADD", g.math("MULTIPLY", sun, 25.0), g.math("MULTIPLY", glare, 0.3))), (1.0, 0.75, 0.45))
    layers.append(_add(g, _add(g, dark, rim7), _add(g, sky, _rgb(g, g.math("MULTIPLY", stars, g.math("MULTIPLY", above, g.math("SUBTRACT", 1.0, glare))), (1, 1, 1)))))

    col = None
    for i, lay in enumerate(layers):
        wgt = g.math("LESS_THAN", g.math("ABSOLUTE", g.math("SUBTRACT", sel.outputs[0], float(i))), 0.5)
        term = g.node("ShaderNodeVectorMath", _operation="SCALE")
        g._in(term.inputs[0], lay)
        g._in(term.inputs["Scale"], wgt)
        col = term.outputs[0] if col is None else _add(g, col, term.outputs[0])
    bg = g.node("ShaderNodeBackground")
    g._in(bg.inputs["Color"], col)
    # camera rays, and rays seen through window glass, see the view; walls only get a faint ambient
    lp = g.node("ShaderNodeLightPath")
    see = g.math("MAXIMUM", lp.outputs["Is Camera Ray"], lp.outputs["Is Transmission Ray"])
    amb = g.node("ShaderNodeBackground")
    amb.inputs["Color"].default_value = (0.5, 0.55, 0.65, 1)
    amb.inputs["Strength"].default_value = ambient
    mix = g.node("ShaderNodeMixShader")
    g._in(mix.inputs[0], see)
    g.link(amb.outputs[0], mix.inputs[1])
    g.link(bg.outputs[0], mix.inputs[2])
    o = g.node("ShaderNodeOutputWorld")
    g.link(mix.outputs[0], o.inputs["Surface"])
    scene.world = w
    _sun(scene)
    set_view(KEYS[int(scene.get("sb_view", 0))], scene=scene)
    return w


def _sun(scene):
    ob = bpy.data.objects.get(SUN)
    if ob is None:
        L = bpy.data.lights.new(SUN, "SUN")
        L.angle = math.radians(1.5)
        ob = bpy.data.objects.new(SUN, L)
        ob["sb_light"] = "outside"
    if ob.name not in scene.collection.objects:
        scene.collection.objects.link(ob)
    return ob


def set_view(key, scene=None, frame=None):
    """Switch the outside view (key in VIEWS). With frame, key the switch on the timeline."""
    scene = scene or bpy.context.scene
    i = KEYS.index(key)
    _, energy, colour, toward = VIEWS[key]
    scene["sb_view"] = i
    w = bpy.data.worlds.get(WORLD)
    sel = w.node_tree.nodes.get("SB View") if w else None
    sun = _sun(scene)
    from mathutils import Vector
    sun.rotation_euler = Vector(toward).normalized().to_track_quat("-Z", "Y").to_euler()
    sun.data.energy = energy
    sun.data.color = colour
    if sel is not None:
        sel.outputs[0].default_value = float(i)
    # outside objects that belong to one view only (the rooms' distant planets live in Deep space)
    only = [o for o in scene.objects if o.get("sb_view_only")]
    for o in only:
        o.hide_render = o.hide_viewport = o["sb_view_only"] != key
    if frame is not None:
        for o in only:
            o.keyframe_insert("hide_render", frame=frame)
            o.keyframe_insert("hide_viewport", frame=frame)
        scene.keyframe_insert('["sb_view"]', frame=frame)
        if sel is not None:
            sel.outputs[0].keyframe_insert("default_value", frame=frame)
        sun.data.keyframe_insert("energy", frame=frame)
        sun.data.keyframe_insert("color", frame=frame)
        sun.keyframe_insert("rotation_euler", frame=frame)
        from .wear import _fcurves
        for idb in [scene, w.node_tree if w else None, sun, sun.data] + only:
            ad = getattr(idb, "animation_data", None)
            for fc in _fcurves(ad.action if ad else None):
                for k in fc.keyframe_points:
                    k.interpolation = "CONSTANT"
    return i
