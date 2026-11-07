"""Loose props the cast can pick up or knock over. Each one builds at a point.

    props.PROPS -> {id: (label, builder)}
    props.add(id, location) -> the new prop's main object
"""
import math

import bpy
from mathutils import Vector

from . import kit as K
from . import mats as M


def _shelf():
    """The collection set props go into (one per scene)."""
    r = getattr(_shelf, "room", None)
    try:
        alive = r is not None and r.root.name in bpy.data.collections and r.root.name in bpy.context.scene.collection.children
    except ReferenceError:  # the file was reloaded
        alive = False
    if not alive:
        r = K.Room("Loose props", 1, 1, 1)
        _shelf.room = r
    return r


def _mug(room, p):
    from .rooms.lounge import mug
    return mug(room, p, M.plastic("SB Mug Cream", (0.62, 0.58, 0.48, 1), 0.3), "Mug")


def _can(room, p):
    from .rooms.lounge import oil_can
    return oil_can(room, p, (0.08, 0.2, 0.21, 1), "Oil Can")


def _can_red(room, p):
    from .rooms.lounge import oil_can
    return oil_can(room, p, (0.45, 0.16, 0.06, 1), "Oil Can Red")


def _pad(room, p):
    from .rooms.lounge import datapad
    return datapad(room, p, 0.2)


def _crate(room, p):
    c = K.box("Crate", (0.5, 0.5, 0.5), (p[0], p[1], p[2] + 0.25), room.pal["warm"], room.props, bevel=0.02)
    band = K.box("Crate Stencil Band", (0.505, 0.505, 0.06), (p[0], p[1], p[2] + 0.4), M.hazard(), room.props, bevel=0.003)
    band.parent = c                      # painted on: rides with the crate
    band.location = (0, 0, 0.15)
    K.rigid(c, 4.0, shape="BOX")
    return c


def _toolbox(room, p):
    b = K.box("Toolbox", (0.42, 0.2, 0.18), (p[0], p[1], p[2] + 0.09), M.painted_metal("SB Toolbox Red", (0.42, 0.05, 0.03, 1), 0.4), room.props, bevel=0.012)
    h = K.box("Toolbox Handle", (0.26, 0.025, 0.03), (p[0], p[1], p[2] + 0.195), room.pal["steel"], room.props, bevel=0.006)
    h.parent = b
    h.location = (0, 0, 0.105)
    K.rigid(b, 2.5, shape="BOX")
    return b


def _furniture(build):
    """Wrap a room's own furniture builder as a prop: build it, then gather the new parts
    under one empty sitting at the piece's footprint centre, so it moves as one."""
    def make(room, p):
        before = set(bpy.data.objects)
        build(room)
        new = [o for o in bpy.data.objects if o not in before]
        tops = [o for o in new if o.parent is None or o.parent not in new]
        if not new:
            return None
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box] or \
              [o.matrix_world.translation for o in new]
        lo = Vector([min(q[i] for q in pts) for i in range(3)])
        hi = Vector([max(q[i] for q in pts) for i in range(3)])
        foot = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        hub = bpy.data.objects.new("Prop " + build.__name__.replace("_", " ").title(), None)
        hub.empty_display_type, hub.empty_display_size = "PLAIN_AXES", 0.15
        room.props.objects.link(hub)
        hub.location = foot
        bpy.context.view_layer.update()
        for o in tops:
            mw = o.matrix_world.copy()
            rbw = bpy.context.scene.rigidbody_world
            if o.rigid_body is not None and rbw and rbw.collection and o.name in rbw.collection.objects:
                rbw.collection.objects.unlink(o)  # a parented rigid body would fight its parent
            o.parent = hub
            o.matrix_world = mw
        hub.location = Vector(p)
        return hub
    return make


def _couch(room):
    from .rooms.lounge import couch
    couch(room, 0, 0, width=2.2)


def _coffee_table(room):
    from .rooms.lounge import coffee_table
    coffee_table(room, 0, 0)


def _pilot_chair(room):
    from .rooms.bridge import chair
    chair(room, 0, 0)


def _console(room):
    from .rooms.bridge import console
    console(room, 0, 0, 1.4)


def _holo_table(room):
    from .rooms.bridge import hologram
    hologram(room, 0, 0, 0.9)


def _wall_bench(room):
    from .rooms.corridor import bench
    bench(room, 0)


def _lockers(room):
    from .rooms.corridor import lockers
    lockers(room, 0, n=2)


def _lectern(room):
    from .rooms.engine import lectern
    lectern(room, 0, 0)


def _telescope(room):
    from .rooms.observation import telescope
    telescope(room, 0, 0)


def _tool_cart(room):
    from .rooms.repair import cart
    cart(room, 0, 0)


def _drill_press(room):
    from .rooms.workshop import drill
    drill(room, 0)


def _welder(room):
    from .rooms.workshop import welder
    welder(room, 0)


def _potted_plant(room):
    import random
    from .rooms.organic import greens, plant
    pal = room.pal
    K.cyl("Plant Pot", 0.11, 0.2, (0, 0, 0.1), M.painted_metal("SB Pot Teal", (0.08, 0.2, 0.21, 1), 0.5), room.dress, verts=32, bevel=0.01)
    K.cyl("Plant Soil", 0.1, 0.01, (0, 0, 0.195), pal["rubber"], room.dress, verts=32, bevel=0)
    rng = random.Random(7)
    g = greens()
    for k in range(5):
        a = k * 1.257
        plant(room, (0.04 * math.cos(a), 0.04 * math.sin(a), 0.2), rng.uniform(0.22, 0.38), rng, g[k % 2], name=f"Pot Plant {k}")


PROPS = {
    "mug": ("Oil mug", _mug),
    "oil_can": ("Oil can", _can),
    "oil_can_red": ("Oil can, red", _can_red),
    "datapad": ("Datapad", _pad),
    "crate": ("Cargo crate", _crate),
    "toolbox": ("Toolbox", _toolbox),
    "couch": ("Couch", _furniture(_couch)),
    "coffee_table": ("Coffee table", _furniture(_coffee_table)),
    "pilot_chair": ("Pilot chair", _furniture(_pilot_chair)),
    "console": ("Pilot console", _furniture(_console)),
    "holo_table": ("Holo table", _furniture(_holo_table)),
    "wall_bench": ("Bench", _furniture(_wall_bench)),
    "lockers": ("Lockers", _furniture(_lockers)),
    "lectern": ("Control lectern", _furniture(_lectern)),
    "telescope": ("Telescope", _furniture(_telescope)),
    "tool_cart": ("Tool cart", _furniture(_tool_cart)),
    "drill_press": ("Drill press", _furniture(_drill_press)),
    "welder": ("Welding cart", _furniture(_welder)),
    "potted_plant": ("Potted plant", _furniture(_potted_plant)),
}


def add(pid, location=None):
    loc = Vector(location if location is not None else bpy.context.scene.cursor.location)
    room = _shelf()
    before = set(bpy.data.objects)
    ob = PROPS[pid][1](room, tuple(loc))
    new = set(bpy.data.objects) - before
    for o in new:
        o["sb_prop"] = pid
    return ob
