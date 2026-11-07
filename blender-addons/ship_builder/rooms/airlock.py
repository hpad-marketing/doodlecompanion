"""Airlock: the way out.

A round outer hatch set in the back wall: a heavy collar ring with clamp dogs,
the door disc with a porthole and a locking wheel, a hazard square painted on
the deck in front of it and a red beacon above. A pressure panel beside the
hatch, an EVA suit hanging on the wall with its helmet, and a bench to sit on
while suiting up.

Use points: cycle the airlock at the panel, stand on the hatch mark, sit on the
bench, take the suit.
"""
import math
from mathutils import Vector

from .. import kit as K
from .. import dressing as Dr
from .. import surfaces as Sf
from .. import mats as M
from .. import lighting as Li
from .. import screens as Sc
from . import common as C
from .. import wear as Wr
from .. import arch as A

INFO = {"label": "Airlock", "size": (5.2, 4.6, 3.0), "doors": {"left": 1.5, "right": 1.5}}

HATCH_Z = 1.3
HATCH_R = 0.95
WALL = 0.034      # back wall face, in from D


def hatch(room):
    D = room.D
    pal = room.pal
    yf = D - WALL
    rx = (math.radians(90), 0, 0)
    K.cyl("Hatch Collar", HATCH_R, 0.12, (0, yf - 0.06, HATCH_Z), pal["hull"], room.dress, verts=64, rot=rx, bevel=0.025)
    K.cyl("Hatch Collar Ring", HATCH_R - 0.1, 0.03, (0, yf - 0.135, HATCH_Z), pal["warm"], room.dress, verts=64, rot=rx, bevel=0.008)
    door = M.painted_metal("SB Hatch Door", (0.36, 0.37, 0.35, 1), 0.45)
    K.cyl("Hatch Door", HATCH_R - 0.2, 0.06, (0, yf - 0.15, HATCH_Z), door, room.dress, verts=64, rot=rx, bevel=0.02)
    for k in range(8):  # clamp dogs around the door
        a = math.radians(22.5 + 45 * k)
        K.box("Hatch Dog", (0.07, 0.06, 0.16), (math.cos(a) * (HATCH_R - 0.16), yf - 0.17, HATCH_Z + math.sin(a) * (HATCH_R - 0.16)),
              pal["dark_steel"], room.dress, bevel=0.01, rot=(0, -a + math.radians(90), 0))
    # porthole and locking wheel
    pz = HATCH_Z + 0.36
    K.cyl("Porthole Rim", 0.15, 0.04, (0, yf - 0.195, pz), pal["dark_steel"], room.dress, verts=40, rot=rx, bevel=0.01)
    K.cyl("Porthole Glass", 0.11, 0.006, (0, yf - 0.216, pz), M.emissive("SB Porthole Dark", (0.02, 0.03, 0.06, 1), 0.5), room.dress, verts=40, rot=rx, bevel=0)
    wc = Vector((0, yf - 0.23, HATCH_Z - 0.05))
    K.cyl("Lock Hub", 0.06, 0.08, wc, pal["dark_steel"], room.dress, verts=24, rot=rx, bevel=0.008)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        K.box("Lock Handle", (0.03, 0.03, 0.3), wc + Vector((math.cos(a) * 0.15, -0.01, math.sin(a) * 0.15)), pal["warm"], room.dress,
              bevel=0.008, rot=(0, -a + math.radians(90), 0))
    # beacon on a bracket above the hatch
    K.box("Beacon Bracket", (0.16, 0.12, 0.06), (0, yf - 0.06, HATCH_Z + HATCH_R + 0.2), pal["dark_steel"], room.dress, bevel=0.006)
    beacon = M.emissive("SB Beacon", (1.0, 0.12, 0.05, 1), 8.0)
    K.cyl("Beacon Lens", 0.06, 0.1, (0, yf - 0.08, HATCH_Z + HATCH_R + 0.28), beacon, room.dress, verts=24, bevel=0.02)
    K.point_glow(room, (0, yf - 0.3, HATCH_Z + HATCH_R + 0.28), (1.0, 0.15, 0.06), 25, 0.04, role="practical")
    # deck paint
    for k, (w, d, mat) in enumerate(((1.9, 1.0, M.hazard()), (1.6, 0.7, room.pal["deck"]))):
        s = K.box("Hatch Floor Paint" if not k else "Hatch Floor Inner", (w, d, 0.0004), (0, D - 0.12 - 0.5, 0.0003 + 0.0002 * k), mat, room.dress, bevel=0, segs=1)
        s["sb_decal"] = True
    return C.use_point(room, "Hatch mark", (0, D - 0.75, 0.0), math.radians(180), "stand",
                       approach=(0, D - 1.6, 0.0), who="any")


def panel(room, x):
    D = room.D
    pal = room.pal
    yf = D - WALL
    K.box("Pressure Panel", (0.42, 0.06, 0.6), (x, yf - 0.03, 1.35), pal["accent"], room.dress, bevel=0.012)
    scr = K.screen(room, (x, yf - 0.06, 1.48), (1, 0, 0), (0, 0, 1), (0, -1, 0), 0.3, 0.18, (1.0, 0.35, 0.15, 1), "ui", light=False,
                   name="Pressure Readout", strength=1.5, depth=0.01, margin=0.012)
    Sc.lock(scr, "BARS")
    big = M.emissive("SB Cycle Button", (1.0, 0.6, 0.1, 1), 3.0)
    K.cyl("Cycle Button", 0.05, 0.03, (x, yf - 0.075, 1.22), big, room.dress, verts=24, rot=(math.radians(90), 0, 0), bevel=0.006)
    K.box("Button Guard", (0.16, 0.03, 0.02), (x, yf - 0.075, 1.29), pal["dark_steel"], room.dress, bevel=0.004)
    K.stencil(room, "CYCLE", (x, yf - 0.061, 1.12), (math.radians(90), 0, 0), 0.04)
    return C.use_point(room, "Cycle the airlock", (x - 0.1, D - 0.85, 0.0), math.radians(180), "press_button",
                       approach=(x - 0.2, D - 1.5, 0.0), contact="hand -> cycle button", who="walker")


def suit(room, x):
    D = room.D
    pal = room.pal
    yf = D - WALL
    fabric = M.fabric("SB EVA Suit", (0.55, 0.5, 0.42, 1))
    K.box("Suit Rail", (0.7, 0.05, 0.05), (x, yf - 0.025, 2.05), pal["dark_steel"], room.dress, bevel=0.008)
    K.box("Suit Hook", (0.03, 0.12, 0.03), (x, yf - 0.1, 2.0), pal["steel"], room.dress, bevel=0.006)
    y = yf - 0.21
    K.rounded("Suit Torso", (0.5, 0.26, 0.62), (x, y, 1.62), fabric, room.dress, soft=2, wrinkle=0.006)
    K.rounded("Suit Pack", (0.38, 0.1, 0.45), (x, yf - 0.06, 1.66), pal["plastic_grey"], room.dress, soft=2)
    for sx in (-1, 1):
        K.rounded("Suit Arm", (0.13, 0.15, 0.6), (x + sx * 0.3, y, 1.5), fabric, room.dress, soft=2, wrinkle=0.006)
        K.rounded("Suit Glove", (0.1, 0.1, 0.13), (x + sx * 0.3, y, 1.13), pal["rubber"], room.dress, soft=2)
        K.rounded("Suit Leg", (0.17, 0.19, 0.7), (x + sx * 0.12, y, 0.98), fabric, room.dress, soft=2, wrinkle=0.006)
        K.rounded("Suit Boot", (0.16, 0.24, 0.14), (x + sx * 0.12, y - 0.02, 0.6), pal["rubber"], room.dress, soft=2)
    K.box("Helmet Shelf", (0.36, 0.3, 0.03), (x, yf - 0.15, 2.32), pal["dark_steel"], room.dress, bevel=0.006)
    K.rounded("EVA Helmet", (0.3, 0.3, 0.32), (x, yf - 0.16, 2.335 + 0.16), pal["cream"], room.dress, soft=3)
    K.rounded("Helmet Visor", (0.22, 0.03, 0.15), (x, yf - 0.31, 2.52), M.glass("SB Visor", (0.4, 0.32, 0.12, 1), 0.05), room.dress, soft=2)
    return C.use_point(room, "Take the suit", (x, D - 0.85, 0.0), math.radians(180), "take",
                       approach=(x, D - 1.6, 0.0), contact="hands -> suit shoulders", who="walker")


def bench(room, x):
    D = room.D
    pal = room.pal
    y = D - 0.09 - 0.21
    for sx in (-1, 1):
        K.box("Bench Bracket", (0.05, 0.4, 0.42), (x + sx * 0.32, y, 0.21), pal["dark_steel"], room.dress, bevel=0.006)
    seat = K.box("Bench Seat", (0.8, 0.42, 0.05), (x, y, 0.445), pal["hull"], room.dress, bevel=0.01)
    seat["sb_surface"] = "metal"
    return C.use_point(room, "Suit-up bench", (x, y, 0.47), 0.0, "sit",
                       approach=(x, y - 0.8, 0.0), contact="seat -> bench", who="walker")


def build(room_name="Airlock", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(0.8, 0.7), chamfer=0.3)
    K.ceiling(room, light_rows=1, color=(0.85, 0.9, 1.0, 1), power=14, cols=2, cove=0.2, cove_color=(1.0, 0.3, 0.12, 1), cove_power=2)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Hatch", 0.0, 0):
        room.uses = [hatch(room)]
    with K.piece(room, "Pressure panel", 0.0, 0):
        room.uses.append(panel(room, 1.2))
    with K.piece(room, "EVA suit", 0.0, 0):
        room.uses.append(suit(room, -1.55))
    with K.piece(room, "Bench", 0.02, 0):
        room.uses.append(bench(room, 1.65))
    K.stencil(room, "OUTER HATCH - CHECK SEALS", (0.0, D - 0.035, 2.72), (math.radians(90), 0, 0), 0.06)
    for x0 in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x0, 0.35, 0.25), (1.0, 0.35, 0.1), 6, 0.03, role="emergency")
    Li.haze(room, 0.01)
    Li.camera(room, "Wide master", 24, (0.0, -1.1, 1.45), (0.0, D * 0.75, 1.25), 4.0)
    Li.camera(room, "Hatch close", 35, (-0.9, 1.6, 1.2), (0.0, D - 0.2, 1.3), 2.2)
    room.arch = A.detail(room, seed=wear_seed, density=0.6, accent=(1.0, 0.3, 0.1, 1), frame_step=1.4,
                         frame_avoid=[(-2.0, 2.3)], walkway=(-1.8, 1.8, 0.5, 2.5))
    room.dressing = Dr.dress(room, "airlock", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
