"""Loose props the cast can pick up or knock over. Each one builds at a point.

    props.PROPS -> {id: (label, builder)}
    props.add(id, location) -> the new prop's main object
"""
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


PROPS = {
    "mug": ("Oil mug", _mug),
    "oil_can": ("Oil can", _can),
    "oil_can_red": ("Oil can, red", _can_red),
    "datapad": ("Datapad", _pad),
    "crate": ("Cargo crate", _crate),
    "toolbox": ("Toolbox", _toolbox),
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
