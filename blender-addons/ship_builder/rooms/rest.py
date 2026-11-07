"""Rest pods: bunk capsules for the small crew.

A bank of four sleep capsules against the back wall, two up and two down, each a
padded tube with a mattress, a pillow, a reading light and a privacy shutter
(one half drawn). A ladder between the columns reaches the top pods. A locker
column on the left wall. Dim, warm night light.

Use points: lie in a lower pod, climb the ladder into an upper pod, open the locker.
"""
import math
from mathutils import Vector

from .. import kit as K
from .. import dressing as Dr
from .. import surfaces as Sf
from .. import mats as M
from .. import lighting as Li
from . import common as C
from .. import wear as Wr
from .. import arch as A

INFO = {"label": "Rest pods", "size": (6.0, 5.0, 3.2), "doors": {"left": 1.5, "right": 1.5}}

POD_L = 1.9       # inside length
POD_H = 0.82      # inside height
POD_D = 0.92      # inside depth
WALL_T = 0.06
FLOORS = (0.34, 0.34 + POD_H + WALL_T)
COLS = (-1.03, 1.03)


def bank(room):
    D = room.D
    pal = room.pal
    shell = M.painted_metal("SB Pod Shell", (0.5, 0.48, 0.42, 1), 0.4)
    pad = M.fabric("SB Pod Padding", (0.16, 0.2, 0.24, 1))
    sheet = M.fabric("SB Pod Sheet", (0.45, 0.42, 0.36, 1))
    glow = M.emissive("SB Pod Light", (1.0, 0.72, 0.42, 1), 3.0)
    glow["sb_role"] = "practical"
    yb = D - 0.09
    depth = POD_D + WALL_T
    yc = yb - depth / 2
    total = FLOORS[1] + POD_H + WALL_T
    x0 = COLS[0] - POD_L / 2 - WALL_T
    x1 = COLS[1] + POD_L / 2 + WALL_T
    K.box("Pod Back", (x1 - x0, WALL_T, total), ((x0 + x1) / 2, yb - WALL_T / 2, total / 2), shell, room.dress, bevel=0.01)
    K.box("Pod Plinth", (x1 - x0, depth, FLOORS[0] - WALL_T), ((x0 + x1) / 2, yc, (FLOORS[0] - WALL_T) / 2), pal["hull"], room.dress, bevel=0.01)
    for x in (x0 + WALL_T / 2, x1 - WALL_T / 2, 0.0):
        w = WALL_T if x else COLS[1] - COLS[0] - POD_L
        K.box("Pod Divider", (w, depth, total - FLOORS[0] + WALL_T), (x, yc, (total + FLOORS[0] - WALL_T) / 2), shell, room.dress, bevel=0.012)
    for z in (FLOORS[0] - WALL_T / 2, FLOORS[1] - WALL_T / 2, total - WALL_T / 2):
        K.box("Pod Deck", (x1 - x0, depth, WALL_T), ((x0 + x1) / 2, yc, z), shell, room.dress, bevel=0.01)
    out = []
    for r, fz in enumerate(FLOORS):
        for c, cx in enumerate(COLS):
            K.box("Pod Lining", (POD_L - 0.02, 0.03, POD_H - 0.04), (cx, yb - WALL_T - 0.015, fz + POD_H / 2), pad, room.dress, bevel=0.01)
            m = K.rounded("Pod Mattress", (POD_L - 0.06, POD_D - 0.1, 0.12), (cx, yc + 0.0, fz + 0.06), sheet, room.dress, soft=2, wrinkle=0.006)
            m["sb_surface"] = "fabric"
            K.rounded("Pod Pillow", (0.38, 0.5, 0.1), (cx - POD_L / 2 + 0.28, yc + 0.1, fz + 0.12 + 0.05), sheet, room.dress, soft=3, wrinkle=0.005)
            K.box("Pod Reading Light", (0.5, 0.06, 0.012), (cx - 0.4, yb - WALL_T - 0.2, fz + POD_H - 0.006), glow, room.dress, bevel=0, segs=1)
            K.point_glow(room, (cx - 0.4, yb - 0.4, fz + POD_H - 0.12), (1.0, 0.72, 0.42), 6, 0.03, role="practical")
            K.box("Pod Number", (0.14, 0.004, 0.06), (cx + POD_L / 2 - 0.15, yc - depth / 2 - 0.002, fz + POD_H + 0.03), M.emissive(f"SB Pod Tag", (0.4, 0.8, 1.0, 1), 1.5), room.dress, bevel=0, segs=1)
            # privacy shutter rolled up under the lid, one pulled half down
            half = (r, c) == (1, 1)
            sh = 0.45 if half else 0.08
            K.box("Pod Shutter", (POD_L - 0.04, 0.012, sh), (cx, yc - depth / 2 + 0.03, fz + POD_H - sh / 2), M.fabric("SB Shutter", (0.3, 0.12, 0.06, 1)), room.dress, bevel=0.003)
            K.cyl("Shutter Roll", 0.03, POD_L - 0.04, (cx, yc - depth / 2 + 0.035, fz + POD_H - 0.03), pal["dark_steel"], room.dress, verts=16, rot=(0, math.radians(90), 0), bevel=0.003)
            if r == 0:
                out.append(C.use_point(room, f"Lower pod {c + 1}", (cx, yc, fz + 0.12), math.radians(90 if c else -90), "lie_in",
                                       approach=(cx, yc - depth / 2 - 0.7, 0.0), contact="back -> mattress", who="walker"))
            else:
                out.append(C.use_point(room, f"Upper pod {c + 1}", (cx, yc, fz + 0.12), math.radians(90 if c else -90), "lie_in",
                                       approach=(0.0, yc - depth / 2 - 0.55, 0.0), contact="back -> mattress", who="walker", via="ladder"))
    # ladder between the columns, standing on the deck and hooked over the top pod rim
    lx = 0.0
    ly = yc - depth / 2 - 0.06
    for sx in (-1, 1):
        K.box("Ladder Rail", (0.03, 0.03, total + 0.05), (lx + sx * 0.18, ly, (total + 0.05) / 2), pal["steel"], room.dress, bevel=0.006)
        K.box("Ladder Hook", (0.03, 0.09, 0.03), (lx + sx * 0.18, ly + 0.045, total + 0.015), pal["steel"], room.dress, bevel=0.006)
    k = 0
    z = 0.3
    while z < total - 0.05:
        K.cyl("Ladder Rung", 0.014, 0.36, (lx, ly, z), pal["steel"], room.dress, verts=12, rot=(0, math.radians(90), 0), bevel=0.002)
        z += 0.3
        k += 1
    return out


def lockers(room):
    W, D = room.W, room.D
    pal = room.pal
    x = -W / 2 + 0.09 + 0.22
    y0 = 3.4
    paint = M.painted_metal("SB Locker", (0.12, 0.2, 0.22, 1), 0.45)
    for k in range(2):
        y = y0 + 0.26 + k * 0.5
        K.box("Locker", (0.44, 0.48, 1.85), (x, y, 0.925 + 0.06), paint, room.dress, bevel=0.01)
        K.box("Locker Vent", (0.004, 0.24, 0.12), (x + 0.222, y, 1.65), pal["dark_steel"], room.dress, bevel=0, segs=1)
        K.box("Locker Handle", (0.03, 0.02, 0.14), (x + 0.235, y - 0.17, 1.05), pal["steel"], room.dress, bevel=0.004)
    K.box("Locker Plinth", (0.44, 1.0, 0.06), (x, y0 + 0.51, 0.03), pal["hull"], room.dress, bevel=0.006)
    return C.use_point(room, "Open the locker", (x + 0.75, y0 + 0.26, 0.0), math.radians(-90 + 180), "open",
                       approach=(x + 1.3, y0 + 0.26 - 0.4, 0.0), contact="hand -> locker handle", who="walker")


def build(room_name="Rest pods", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(0.9, 0.7), chamfer=0.3)
    K.ceiling(room, light_rows=1, color=(1.0, 0.75, 0.5, 1), power=10, cols=2, cove=0.24, cove_color=(1.0, 0.6, 0.3, 1), cove_power=3)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Pod bank", 0.0, 0):
        room.uses = bank(room)
    with K.piece(room, "Lockers", 0.0, 0):
        room.uses.append(lockers(room))
    K.stencil(room, "REST PODS - LIGHTS DOWN AT 2200", (0.0, D - 0.035, 2.75), (math.radians(90), 0, 0), 0.06)
    for x0 in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x0, 0.35, 0.25), (1.0, 0.35, 0.1), 5, 0.03, role="emergency")
    Li.haze(room, 0.01)
    Li.camera(room, "Wide master", 24, (0.0, -1.1, 1.45), (0.0, D * 0.75, 1.2), 4.5)
    Li.camera(room, "Pod close", 35, (1.3, 2.0, 1.0), (COLS[0], D - 0.6, 0.7), 2.4)
    room.arch = A.detail(room, seed=wear_seed, density=0.6, accent=(1.0, 0.6, 0.3, 1), frame_step=1.5,
                         frame_avoid=[(-2.6, 2.6)], walkway=(-2.2, 2.2, 0.5, 2.5))
    room.dressing = Dr.dress(room, "rest", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
