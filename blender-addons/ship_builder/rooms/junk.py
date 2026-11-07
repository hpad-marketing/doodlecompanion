"""Junk room: the porter droid's kingdom.

A heap of scrap in the back left (plates, pipe offcuts, a dead droid's head,
cable coils, a wheel), a scrap compactor against the back wall with a hopper,
hazard stripes and a big red button, and three sorting bins along the right wall
labelled by somebody with strong opinions. One tired work light.

Use points: dump scrap in the hopper, press the compactor button, sort into the
bins, dig in the heap.
"""
import math
import random
from mathutils import Vector

from .. import kit as K
from .. import dressing as Dr
from .. import surfaces as Sf
from .. import mats as M
from .. import lighting as Li
from . import common as C
from . import organic as O
from .. import wear as Wr
from .. import arch as A

INFO = {"label": "Junk room", "size": (6.6, 5.6, 3.2), "doors": {"left": 1.5, "right": 1.5}}

HEAP = (-1.65, 4.35, 1.05, 0.8, 0.5)   # centre x, y, radius x, radius y, height
COMPACTOR = (1.25, 1.5, 1.05, 1.45)     # centre x, width, depth, height
BINS_X = 2.85
BINS_Y = (3.3, 3.85, 4.4)


def heap(room, rng):
    x, y, rx, ry, h = HEAP
    pal = room.pal
    grime = M.painted_metal("SB Scrap Grime", (0.08, 0.07, 0.06, 1), 0.85)
    O.mound(room, (x, y, 0.0), rx, ry, h, grime, name="Scrap Mound")
    rust = M.painted_metal("SB Scrap Rust", (0.3, 0.12, 0.05, 1), 0.75)
    mats = [rust, pal["dark_steel"], pal["hull"], pal["accent"], pal["warm"]]
    placed = []
    tries = 0
    while len(placed) < 26 and tries < 400:
        tries += 1
        a, r = rng.uniform(0, math.tau), math.sqrt(rng.uniform(0, 0.8))
        dx, dy = r * rx * math.cos(a), r * ry * math.sin(a)
        z = O.mound_z(dx, dy, rx, ry, h)
        p = Vector((x + dx, y + dy, z))
        if any((p - q).length < 0.2 for q in placed):
            continue
        placed.append(p)
        kind = rng.random()
        rot = (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(-math.pi, math.pi))
        if kind < 0.35:
            s = (rng.uniform(0.15, 0.35), rng.uniform(0.1, 0.25), 0.012)
            K.box("Scrap Plate", s, p + Vector((0, 0, 0.0)), rng.choice(mats), room.dress, bevel=0.003, rot=rot)
        elif kind < 0.6:
            K.cyl("Scrap Pipe", rng.uniform(0.02, 0.04), rng.uniform(0.2, 0.4), p, rng.choice(mats), room.dress, verts=16, rot=(math.radians(90) + rot[0] * 0.3, 0, rot[2]), bevel=0.003)
        elif kind < 0.8:
            s = rng.uniform(0.06, 0.12)
            K.box("Scrap Block", (s, s * 0.8, s * 0.6), p + Vector((0, 0, s * 0.1)), rng.choice(mats), room.dress, bevel=0.006, rot=rot)
        else:
            K.cyl("Scrap Coil", rng.uniform(0.06, 0.1), 0.03, p, pal["rubber"], room.dress, verts=24, rot=rot, bevel=0.01)
    # the dead droid head and a wheel lean on the heap's front
    hd = Vector((x + 0.3, y - ry * 0.55, O.mound_z(0.3, -ry * 0.55, rx, ry, h) + 0.05))
    K.rounded("Dead Droid Head", (0.3, 0.26, 0.24), hd, pal["cream"], room.dress, soft=3, rot=(0.25, 0.1, 0.4))
    K.cyl("Dead Droid Lens", 0.06, 0.02, hd + Vector((0.02, -0.13, 0.02)), M.glass("SB Dead Lens", (0.2, 0.08, 0.05, 1), 0.1), room.dress,
          verts=24, rot=(math.radians(80), 0, 0.4), bevel=0.004)
    wp = Vector((x - 0.55, y - ry * 0.4, O.mound_z(-0.55, -ry * 0.4, rx, ry, h) + 0.02))
    K.cyl("Scrap Wheel", 0.17, 0.07, wp, pal["rubber"], room.dress, verts=32, rot=(math.radians(70), 0, 0.3), bevel=0.015)
    return C.use_point(room, "Dig in the heap", (x + 0.2, y - ry - 0.45, 0.0), math.radians(180), "dig",
                       approach=(x + 0.4, y - ry - 1.2, 0.0), contact="hand -> scrap", who="any")


def compactor(room):
    D = room.D
    x, w, d, hgt = COMPACTOR
    pal = room.pal
    y = D - 0.09 - d / 2
    body = M.painted_metal("SB Compactor", (0.36, 0.3, 0.08, 1), 0.5)
    K.box("Compactor Body", (w, d, hgt), (x, y, hgt / 2), body, room.dress, bevel=0.02)
    K.box("Compactor Stripe", (w - 0.04, 0.003, 0.16), (x, y - d / 2 - 0.0016, 0.18), M.hazard(), room.dress, bevel=0, segs=1)
    K.box("Compactor Door", (w * 0.6, 0.02, hgt * 0.45), (x, y - d / 2 - 0.01, 0.34 + hgt * 0.225), pal["dark_steel"], room.dress, bevel=0.008)
    for sx in (-1, 1):
        K.box("Door Hinge", (0.04, 0.03, 0.12), (x + sx * w * 0.3, y - d / 2 - 0.025, 0.34 + hgt * 0.35), pal["steel"], room.dress, bevel=0.004)
    # hopper: four sloped walls opening up from the top
    top = hgt
    for sx in (-1, 1):
        K.box("Hopper Side", (0.04, d - 0.08, 0.42), (x + sx * (w / 2 - 0.12), y, top + 0.2), pal["dark_steel"], room.dress, bevel=0.006,
              rot=(0, sx * math.radians(14), 0))
    K.box("Hopper Front", (w - 0.2, 0.04, 0.3), (x, y - d / 2 + 0.12, top + 0.14), pal["dark_steel"], room.dress, bevel=0.006,
          rot=(math.radians(-18), 0, 0))
    K.box("Hopper Back", (w - 0.2, 0.04, 0.5), (x, y + d / 2 - 0.08, top + 0.24), pal["dark_steel"], room.dress, bevel=0.006)
    # ram housing on the back
    K.box("Ram Housing", (0.5, 0.3, 0.55), (x, y + d / 2 - 0.22, top + 0.5 + 0.275), body, room.dress, bevel=0.02)
    K.cyl("Ram Cylinder", 0.07, 0.4, (x, y + d / 2 - 0.22, top + 1.25), pal["steel"], room.dress, verts=24, bevel=0.006)
    # control post with the big red button
    px = x - w / 2 - 0.28
    K.box("Button Post", (0.14, 0.14, 1.0), (px, y - 0.2, 0.5), pal["dark_steel"], room.dress, bevel=0.01)
    K.box("Button Box", (0.22, 0.2, 0.16), (px, y - 0.2, 1.08), pal["hull"], room.dress, bevel=0.012)
    K.cyl("Big Red Button", 0.06, 0.05, (px, y - 0.2, 1.185), M.emissive("SB Big Red", (1.0, 0.08, 0.04, 1), 3.0), room.dress, verts=24, bevel=0.012)
    return [C.use_point(room, "Dump scrap in the hopper", (x, y - d / 2 - 0.5, 0.0), math.radians(180), "dump",
                        approach=(x, y - d / 2 - 1.2, 0.0), contact="hands -> scrap over the hopper lip", who="walker"),
            C.use_point(room, "Compactor button", (px, y - 0.75, 0.0), math.radians(180), "press_button",
                        approach=(px - 0.2, y - 1.4, 0.0), contact="hand -> big red button", who="walker")]


def bins(room):
    pal = room.pal
    cols = [M.plastic("SB Bin Green", (0.08, 0.2, 0.08, 1), 0.55), M.plastic("SB Bin Yellow", (0.5, 0.38, 0.05, 1), 0.55),
            M.plastic("SB Bin Red", (0.4, 0.06, 0.04, 1), 0.55)]
    labels = ["METAL", "BOARDS", "???"]
    w, d, h, t = 0.5, 0.5, 0.6, 0.025
    for k, y in enumerate(BINS_Y):
        x = BINS_X
        K.box("Sort Bin Floor", (w, d, t), (x, y, t / 2), cols[k], room.dress, bevel=0.004)
        for sx in (-1, 1):
            K.box("Sort Bin Wall", (t, d, h - t), (x + sx * (w / 2 - t / 2), y, t + (h - t) / 2), cols[k], room.dress, bevel=0.004)
            K.box("Sort Bin Wall", (w - 2 * t, t, h - t), (x, y + sx * (d / 2 - t / 2), t + (h - t) / 2), cols[k], room.dress, bevel=0.004)
        K.stencil(room, labels[k], (x - w / 2 - 0.001, y, h * 0.6), (math.radians(90), 0, math.radians(-90)), 0.05)
        for j in range(2):
            K.box("Sorted Part", (0.12, 0.08, 0.04), (x - 0.08 + 0.14 * j, y + 0.05 * (j - 0.5), t + 0.02), pal["dark_steel"] if k != 1 else
                  M.plastic("SB Board Green", (0.05, 0.22, 0.1, 1), 0.4), room.dress, bevel=0.004, rot=(0, 0, 0.4 * j))
    return C.use_point(room, "Sort into the bins", (BINS_X - 0.85, BINS_Y[1], 0.0), math.radians(-90 + 180), "sort",
                       approach=(BINS_X - 1.5, BINS_Y[1] - 0.4, 0.0), contact="hand -> part over a bin", who="walker")


def build(room_name="Junk room", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    rng = random.Random(wear_seed * 17 + 2)
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(0.9, 0.8), chamfer=0.4)
    K.ceiling(room, light_rows=1, color=(1.0, 0.85, 0.6, 1), power=14, cols=2, cove=0.24, cove_color=(1.0, 0.5, 0.2, 1), cove_power=2)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Scrap heap", 0.0, 0):
        room.uses = [heap(room, rng)]
    with K.piece(room, "Compactor", 0.0, 0):
        room.uses += compactor(room)
    with K.piece(room, "Sorting bins", 0.03, 3):
        room.uses.append(bins(room))
    K.stencil(room, "IF IN DOUBT, KEEP IT", (-1.6, D - 0.035, 2.5), (math.radians(90), 0, 0), 0.08)
    for x0 in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x0, 0.35, 0.25), (1.0, 0.35, 0.1), 6, 0.03, role="emergency")
    Li.haze(room, 0.016)
    Li.camera(room, "Wide master", 24, (0.0, -1.2, 1.5), (0.0, D * 0.7, 1.0), 4.5)
    Li.camera(room, "Heap low", 30, (0.3, 2.2, 0.6), (HEAP[0], HEAP[1], 0.35), 2.2)
    room.arch = A.detail(room, seed=wear_seed, density=0.9, accent=(1.0, 0.5, 0.2, 1), frame_step=1.5,
                         frame_avoid=[(-2.8, 2.1)], walkway=(-2.4, 2.4, 0.5, 2.5))
    room.dressing = Dr.dress(room, "junk", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
