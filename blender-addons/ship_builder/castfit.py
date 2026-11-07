"""Fit each droid to the sets, and keep every droid dense.

User (2026-11-07): RX-07 was far too big for the rooms, so scale him down a lot,
but he stays dense; and all droids should be dense. So size comes from a set
height per droid, and mass does NOT fall with the cube of the scale: RX-07 keeps
his full weight in a body 60 % the size, and every other droid is half as heavy
again as its plain model says. The mass goes on the rig as "foley_mass_kg",
which both walk mode (momentum, braking, turning) and the contact sounds read.
A Droid Kit settings file can override either with "set_height" / "mass_kg".
"""
from mathutils import Vector

SET_HEIGHT = {"rx07": 1.5}       # metres, standing; others keep their modelled size
MASS = {"rx07": 240.0, "hazard": 85.0, "hover_drone": 9.0, "drone": 9.0, "tracker": 189.0,
        "beacon": 31.8, "computer": 400.0}
DENSE = 1.5                      # every droid is heavy for its size
KEEP_MASS = {"rx07"}             # shrunk, but keeps his whole weight


def height(rig):
    zs = [(o.matrix_world @ Vector(c)).z for o in [rig] + list(rig.children_recursive)
          if o.type == "MESH" and not o.hide_render for c in o.bound_box]
    return (max(zs) - min(zs)) if zs else 0.0


def fit(rig, droid_id, settings=None):
    """Scale the rig to its set height and set its mass. Returns (scale, kg)."""
    settings = settings or {}
    key = (droid_id or "").lower().replace("-", "")
    target = settings.get("set_height") or SET_HEIGHT.get(key)
    s = 1.0
    if target:
        h = height(rig)
        if h > 0.05:
            s = target / h * rig.scale.x
            rig.scale = (s, s, s)
    base = settings.get("mass_kg") or MASS.get(key)
    if base is None:
        kg = rig.get("foley_mass_kg")
    elif key in KEEP_MASS:
        kg = base
    else:
        kg = base * DENSE
    if kg:
        rig["foley_mass_kg"] = round(float(kg), 1)
    rig["sb_set_scale"] = round(s, 4)
    return s, kg
