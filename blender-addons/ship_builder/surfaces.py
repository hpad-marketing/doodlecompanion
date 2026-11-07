"""Surface tags for footsteps and contact sounds (the foley contract).

Every mesh in a built room gets:
    ob["sb_surface"]    one of SURFACES, read from its material and name
    ob["foley_hollow"]  0..1: how hollow it sounds when stepped on or knocked (crate 0.7, solid 0)

feet.Planter's ON_PLANT callbacks pass the surface object, so a footstep sound
can read these straight off it. Tags set by hand are kept.
"""
import bpy

SURFACES = ("deck", "grate", "metal", "metal_thin", "polymer", "rubber", "fabric",
            "glass", "ceramic", "wood", "stone")

# first match wins: (words in the object or material name, surface)
_BY_NAME = (
    (("grate", "trench", "grille", "louvre"), "grate"),
    (("deck plate", "deck"), "deck"),
    (("rug", "mat ", "vinyl", "fabric", "cloth", "rag", "jacket", "blanket", "cushion", "couch", "seat pad",
      "towel", "felt", "canvas"), "fabric"),
    (("glass", "lens", "screen", "jar", "bottle", "hologram"), "glass"),
    (("mug", "ceramic", "cup", "bowl"), "ceramic"),
    (("peg board", "wood", "plank"), "wood"),
    (("rubber", "tyre", "tire", "hose", "boot", "cable", "seal", "duct tape"), "rubber"),
    (("plastic", "paper", "sticky", "cardboard", "poster", "label", "decal", "button", "knob", "binder",
      "clipboard", "controller", "game", "case"), "polymer"),
    (("planet", "rock", "stone", "concrete"), "stone"),
)

_HOLLOW = (("crate", 0.7), ("locker", 0.75), ("box", 0.6), ("bin", 0.55), ("bucket", 0.5), ("drum", 0.5),
           ("cabinet", 0.6), ("bench", 0.35), ("desk", 0.4), ("console", 0.4), ("bar", 0.4), ("table", 0.3),
           ("panel", 0.25), ("duct", 0.5), ("pipe", 0.4), ("door", 0.45))


def _guess(ob):
    mat = ob.active_material.name.lower() if ob.active_material else ""
    name = ob.name.lower()
    for words, surf in _BY_NAME:
        if any(w in name or w in mat for w in words):
            return surf
    thin = min(ob.dimensions) < 0.004
    return "metal_thin" if thin else "metal"


def _hollow(ob, surf):
    if surf in ("fabric", "stone", "deck"):
        return 0.0
    name = ob.name.lower()
    for word, h in _HOLLOW:
        if word in name:
            return h
    return 0.0


def tag(objects=None):
    """Tag every mesh (or the given ones). Returns {surface: count}."""
    obs = objects if objects is not None else [o for o in bpy.data.objects if o.type == "MESH"]
    count = {}
    for ob in obs:
        if ob.type != "MESH":
            continue
        if "sb_surface" not in ob:
            ob["sb_surface"] = _guess(ob)
        if "foley_hollow" not in ob:
            ob["foley_hollow"] = _hollow(ob, ob["sb_surface"])
        count[ob["sb_surface"]] = count.get(ob["sb_surface"], 0) + 1
    return count


def tag_room(room):
    return tag([o for o in room.root.all_objects if o.type == "MESH"])
