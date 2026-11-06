"""Corridor: the short connecting module between two rooms.

A pressure door at each end, lockers and a bench niche on the back wall, pipes
and cable runs overhead, floor guide lights. It is kept clear down the middle so
characters can walk straight through from one door to the other.
"""
import math

from .. import kit as K
from .. import mats as M
from .. import lighting as Li
from . import common as C
from .. import wear as Wr
from .. import arch as A

INFO = {"label": "Corridor", "size": (3.6, 3.9, 2.8), "doors": {"left": 1.5, "right": 1.5}}


def lockers(room, x, n=2, w=0.42):
    D = room.D
    pal = room.pal
    body = M.painted_metal("SB Locker", (0.16, 0.2, 0.19, 1), 0.45)
    for k in range(n):
        cx = x + (k - (n - 1) / 2) * (w + 0.01)
        K.box("Locker", (w, 0.36, 1.84), (cx, D - 0.32, 0.92 + 0.004), body, room.dress, bevel=0.012)
        for z in (1.62, 1.68, 1.74):  # vent slots
            K.box("Locker Slot", (w * 0.6, 0.004, 0.012), (cx, D - 0.32 - 0.181, z), pal["dark_steel"], room.dress, bevel=0.001, segs=1)
        K.box("Locker Handle", (0.02, 0.025, 0.16), (cx + w / 2 - 0.06, D - 0.32 - 0.1925, 1.0), pal["steel"], room.dress, bevel=0.004)
        K.box("Locker Tag", (0.12, 0.003, 0.05), (cx, D - 0.32 - 0.1815, 1.45), M.hazard(), room.dress, bevel=0.0005, segs=1)


def bench(room, x, w=0.9):
    D = room.D
    pal = room.pal
    K.box("Bench Seat", (w, 0.34, 0.05), (x, D - 0.32, 0.45), pal["steel"], room.dress, bevel=0.006)
    for sx in (-1, 1):
        K.box("Bench Leg", (0.04, 0.3, 0.425), (x + sx * (w / 2 - 0.06), D - 0.32, 0.2125), pal["dark_steel"], room.dress, bevel=0.004)


def build(room_name="Corridor", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(0.8, 0.7), chamfer=0.3)
    K.ceiling(room, light_rows=1, color=(0.9, 0.95, 1.0, 1), power=22, cols=1, cove=0.22, cove_color=(1.0, 0.55, 0.25, 1), cove_power=4)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Lockers", 0.0, 0):
        lockers(room, -0.45)
    with K.piece(room, "Bench", 0.03, 3):
        bench(room, 0.55, 0.8)
    # floor guide lights along the walkway
    for sy in (0.55, 2.45):
        K.light_strip(room, (0, sy, 0.045), W - 1.0, "X", (0, 0, 1), (1.0, 0.55, 0.25, 1), 2, role="practical", width=0.02)
    K.pipe(room, [(-W / 2 + 0.75, D - 0.18, H - 0.32), (W / 2 - 0.75, D - 0.18, H - 0.32)], 0.04)
    K.pipe(room, [(-W / 2 + 0.75, D - 0.3, H - 0.3), (W / 2 - 0.75, D - 0.3, H - 0.3)], 0.025, M.painted_metal("SB Pipe Oxide", (0.4, 0.13, 0.05, 1), 0.4))
    K.stencil(room, "< CREW LOUNGE", (-0.75, D - 0.035, 2.12), (math.radians(90), 0, 0), 0.07)
    K.stencil(room, "BRIDGE >", (0.85, D - 0.035, 2.12), (math.radians(90), 0, 0), 0.07)
    for x in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x, 0.35, 0.25), (1.0, 0.35, 0.1), 8, 0.03, role="emergency")
    Li.haze(room, 0.014)
    Li.camera(room, "Walkthrough", 20, (0.0, -1.4, 1.45), (0.0, D * 0.6, 1.1), 4.0)
    room.arch = A.detail(room, seed=wear_seed, density=0.6, accent=(1.0, 0.55, 0.25, 1), frame_step=1.2,
                         frame_avoid=[(-0.95, 1.0)])
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    return room
