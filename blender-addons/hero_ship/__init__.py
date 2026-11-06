"""Hero Ship: the exterior ship for the droid spaceship sitcom.

Plain Python package (no UI of its own). The sitcom add-on imports it:

    import hero_ship
    root = hero_ship.build()                        # "Hero Ship" root empty
    hero_ship.presets.apply(root, "hyperdrive_jump", frame_start=1)
    hero_ship.stage.build("space")                  # backdrop for a preset

Root custom properties drive every moving part (see parts.PROPS).
"""
import bpy
from . import geo, mats, layout, parts, decals, moving

VERSION = (1, 1, 0)
ROOT_NAME = "Hero Ship"


def build(collection=None, wear=1.0, seed=1):
    c = collection or geo.coll("Hero Ship")
    M = mats.build_all(wear=wear, seed=seed)
    root = geo.empty(ROOT_NAME, c, kind="ARROWS", size=4.0)
    root["hero_ship"] = ".".join(map(str, VERSION))
    parts.add_props(root)
    body = geo.empty("Ship Body", c, root, kind="PLAIN_AXES", size=2.0)
    hull, ramp_pts, mods = layout.build_hull(c, body, M, seed=seed)
    layout.build_mechanics(c, body, M)
    eng, glow = layout.build_engines(c, body, M)
    parts.drv(glow, '["engine"]', "e", root, {"e": "engine"})
    parts.nacelles(c, body, root, M)
    parts.gear(c, body, root, M)
    parts.ramp(c, body, root, M, ramp_pts)
    parts.radiators(c, body, root, M)
    parts.dish_and_masts(c, body, root, M)
    parts.nav_lights(c, body, root, M)
    parts.plumes(c, body, root)
    decals.apply(c, body, M, hull)
    moving.build(c, body, root, M, hull, mods)
    hull["soot"], hull["soot_y"] = 1.0, -16.5
    eng["soot"], eng["soot_y"] = 1.0, -20.0
    for side in ("L", "R"):
        nb = bpy.data.objects.get(f"Nacelle {side}")
        if nb:
            nb["soot"], nb["soot_y"] = 1.0, -3.6
    for ob in c.all_objects:
        if ob is not root:
            ob["hero_ship_part"] = 1
    return root


def ship_objects(root):
    out = []

    def walk(o):
        for ch in o.children:
            out.append(ch)
            walk(ch)
    walk(root)
    return out
