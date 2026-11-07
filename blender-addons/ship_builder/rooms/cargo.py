"""Cargo hold: crates, a gantry hoist and the big roll-up door.

A three-metre roll-up cargo door fills the middle of the back wall (closed, slats
in their guide rails, hazard header above, a door control box beside it). A
floor-standing gantry spans the hold with a trolley and a hook hanging on its
chain. Crate stacks fill the back corners and a pallet of crates waits under
the hook. Cold, flat work light.

Use points: hook a crate on the pallet, work the door control, check the stacks.
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
from .. import wear as Wr
from .. import arch as A

INFO = {"label": "Cargo hold", "size": (7.6, 6.5, 3.6), "doors": {"left": 1.5, "right": 1.5}}

DOOR = (2.3, 5.3, 0.0, 2.7)   # along the back wall from its left edge
GANTRY_Y = 3.6
GANTRY_X = 2.75
HOOK_X = -0.6
PALLET = (-0.6, 3.6)


def roll_door(room):
    W, D = room.W, room.D
    pal = room.pal
    x0, x1 = -W / 2 + DOOR[0], -W / 2 + DOOR[1]
    w, h = x1 - x0, DOOR[3]
    slat = M.painted_metal("SB Roll Door", (0.32, 0.33, 0.3, 1), 0.45)
    n = int(h / 0.15)
    for k in range(n):
        K.box("Door Slat", (w - 0.02, 0.03, 0.142), ((x0 + x1) / 2, D + 0.015, 0.075 + k * (h - 0.01) / n), slat, room.shell, bevel=0.01)
    K.box("Door Bottom Bar", (w - 0.02, 0.05, 0.05), ((x0 + x1) / 2, D + 0.01, 0.027), pal["rubber"], room.shell, bevel=0.006)
    yf = D - 0.034
    for sx in (-1, 1):
        K.box("Door Guide Rail", (0.1, 0.06, h + 0.05), ((x0 + x1) / 2 + sx * (w / 2 + 0.05), yf - 0.03, (h + 0.05) / 2), pal["dark_steel"], room.dress, bevel=0.008)
    K.box("Door Header", (w + 0.4, 0.1, 0.26), ((x0 + x1) / 2, yf - 0.05, h + 0.18), pal["hull"], room.dress, bevel=0.012)
    K.box("Header Stripe", (w + 0.36, 0.003, 0.12), ((x0 + x1) / 2, yf - 0.1015, h + 0.18), M.hazard(), room.dress, bevel=0, segs=1)
    lamp = M.emissive("SB Door Lamp", (1.0, 0.45, 0.1, 1), 6.0)
    for sx in (-1, 1):
        K.cyl("Door Lamp", 0.05, 0.06, ((x0 + x1) / 2 + sx * (w / 2 - 0.1), yf - 0.13, h + 0.18), lamp, room.dress, verts=20,
              rot=(math.radians(90), 0, 0), bevel=0.006)
    # floor paint in front of the door
    stripe = K.box("Door Floor Hazard", (w, 0.35, 0.0004), ((x0 + x1) / 2, D - 0.4, 0.0003), M.hazard(), room.dress, bevel=0, segs=1)
    stripe["sb_decal"] = True
    # control box on the wall, right of the door
    cx = x1 + 0.3
    K.box("Door Control Box", (0.28, 0.08, 0.38), (cx, yf - 0.04, 1.3), pal["accent"], room.dress, bevel=0.01)
    for k, col in enumerate(((0.2, 1.0, 0.3, 1), (1.0, 0.15, 0.08, 1))):
        K.cyl("Door Button", 0.03, 0.02, (cx, yf - 0.09, 1.38 - k * 0.12), M.emissive(f"SB Button {k}", col, 3.0), room.dress, verts=16,
              rot=(math.radians(90), 0, 0), bevel=0.004)
    return C.use_point(room, "Cargo door control", (cx, D - 0.75, 0.0), math.radians(180), "press_button",
                       approach=(cx - 0.3, D - 1.6, 0.0), contact="hand -> green button", who="walker")


def gantry(room):
    pal = room.pal
    yellow = M.painted_metal("SB Gantry Yellow", (0.6, 0.42, 0.04, 1), 0.45)
    top = 2.85
    for sx in (-1, 1):
        x = sx * GANTRY_X
        K.box("Gantry Foot", (0.36, 0.95, 0.03), (x, GANTRY_Y, 0.015), pal["dark_steel"], room.dress, bevel=0.006)
        for dy in (-0.35, 0.35):
            K.box("Gantry Leg", (0.12, 0.12, top - 0.03), (x, GANTRY_Y + dy, 0.03 + (top - 0.03) / 2), yellow, room.dress, bevel=0.01)
        K.box("Gantry Cross", (0.08, 0.7, 0.08), (x, GANTRY_Y, 1.2), yellow, room.dress, bevel=0.008)
        K.box("Gantry Head", (0.2, 0.9, 0.12), (x, GANTRY_Y, top + 0.06), yellow, room.dress, bevel=0.01)
    K.box("Gantry Beam", (2 * GANTRY_X + 0.2, 0.18, 0.24), (0, GANTRY_Y, top + 0.24), yellow, room.dress, bevel=0.012)
    K.box("Beam Stripe", (2 * GANTRY_X - 0.2, 0.003, 0.08), (0, GANTRY_Y - 0.0915, top + 0.24), M.hazard(), room.dress, bevel=0, segs=1)
    K.stencil(room, "SWL 2T", (1.4, GANTRY_Y - 0.093, top + 0.24), (math.radians(90), 0, 0), 0.06)
    # trolley under the beam, chain, block and hook
    K.box("Hoist Trolley", (0.34, 0.3, 0.18), (HOOK_X, GANTRY_Y, top + 0.03), pal["dark_steel"], room.dress, bevel=0.012)
    K.box("Hoist Motor", (0.2, 0.2, 0.2), (HOOK_X, GANTRY_Y, top - 0.16), pal["accent"], room.dress, bevel=0.012)
    z = top - 0.26
    k = 0
    while z > 1.75:
        K.box("Chain Link", (0.025, 0.045 if k % 2 else 0.012, 0.07), (HOOK_X, GANTRY_Y, z - 0.035), pal["steel"], room.dress, bevel=0.004)
        z -= 0.06
        k += 1
    K.box("Hook Block", (0.14, 0.1, 0.2), (HOOK_X, GANTRY_Y, z - 0.1), yellow, room.dress, bevel=0.015)
    K.box("Hook Shank", (0.04, 0.04, 0.14), (HOOK_X, GANTRY_Y, z - 0.27), pal["steel"], room.dress, bevel=0.008)
    K.box("Hook Bend", (0.16, 0.04, 0.04), (HOOK_X + 0.06, GANTRY_Y, z - 0.33), pal["steel"], room.dress, bevel=0.012)
    K.box("Hook Tip", (0.04, 0.04, 0.08), (HOOK_X + 0.12, GANTRY_Y, z - 0.29), pal["steel"], room.dress, bevel=0.012)
    return z - 0.35


def crate(room, name, size, loc, yaw, mat, trim):
    w, d, h = size
    K.box(name, size, loc, mat, room.dress, bevel=0.012, rot=(0, 0, yaw))
    # corner battens
    c, s = math.cos(yaw), math.sin(yaw)
    for sx in (-1, 1):
        for sy in (-1, 1):
            dx, dy = sx * (w / 2 - 0.02), sy * (d / 2 - 0.02)
            K.box(f"{name} Batten", (0.05, 0.05, h - 0.004), (loc[0] + dx * c - dy * s, loc[1] + dx * s + dy * c, loc[2]), trim, room.dress,
                  bevel=0.006, rot=(0, 0, yaw))


def stacks(room, rng):
    W, D = room.W, room.D
    pal = room.pal
    mats = [M.painted_metal("SB Crate Olive", (0.16, 0.18, 0.1, 1), 0.55), M.painted_metal("SB Crate Rust", (0.32, 0.12, 0.05, 1), 0.6),
            M.painted_metal("SB Crate Grey", (0.2, 0.21, 0.22, 1), 0.5)]
    out = []
    for cx in (-2.75, 2.75):
        y0 = D - 0.55
        z = 0.0
        sizes = [(1.1, 0.95, 0.9), (0.95, 0.85, 0.75), (0.7, 0.6, 0.5)]
        for i, (w, d, h) in enumerate(sizes):
            yaw = math.radians(rng.uniform(-5, 5)) if i else 0.0
            with K.piece(room, "Crate", 0.02 if i else 0.0, 4 if i else 0):
                crate(room, "Cargo Crate", (w, d, h), (cx + rng.uniform(-0.03, 0.03), y0 - 0.5, z + h / 2), yaw, mats[(i + int(cx > 0)) % 3], pal["dark_steel"])
            z += h
        out.append(cx)
    return out


def pallet(room, rng):
    x, y = PALLET
    pal = room.pal
    wood = M.painted_metal("SB Pallet", (0.2, 0.14, 0.08, 1), 0.7)
    with K.piece(room, "Pallet", 0.0, 0):
        for dx in (-0.5, 0.0, 0.5):
            K.box("Pallet Runner", (0.1, 1.0, 0.1), (x + dx, y, 0.05), wood, room.dress, bevel=0.006)
        for k in range(7):
            K.box("Pallet Board", (1.2, 0.11, 0.025), (x, y - 0.45 + k * 0.15, 0.1125), wood, room.dress, bevel=0.004)
    with K.piece(room, "Pallet crate", 0.02, 3):
        crate(room, "Cargo Crate", (0.55, 0.8, 0.5), (x - 0.3, y, 0.125 + 0.25), 0.0, M.painted_metal("SB Crate Olive", (0.16, 0.18, 0.1, 1), 0.55), pal["dark_steel"])
    with K.piece(room, "Pallet crate", 0.02, 3):
        K.box("Strapped Drum", (0.5, 0.5, 0.6), (x + 0.3, y, 0.125 + 0.3), pal["warm"], room.dress, bevel=0.06)
        K.box("Drum Strap", (0.52, 0.52, 0.03), (x + 0.3, y, 0.125 + 0.42), pal["rubber"], room.dress, bevel=0.01)
    return C.use_point(room, "Hook a crate", (x - 0.3, y - 0.95, 0.0), math.radians(180), "hook_load",
                       approach=(x - 0.3, y - 1.7, 0.0), contact="hand -> crate lifting eye", who="walker")


def build(room_name="Cargo hold", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    rng = random.Random(wear_seed * 7 + 3)
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, back_holes=[DOOR], left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(1.2, 0.9), chamfer=0.35)
    K.ceiling(room, light_rows=2, color=(0.9, 0.95, 1.0, 1), power=26, cols=2, cove=0.22, cove_color=(0.8, 0.9, 1.0, 1), cove_power=3)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Cargo door", 0.0, 0):
        room.uses = [roll_door(room)]
    with K.piece(room, "Gantry", 0.0, 0):
        gantry(room)
    stacks(room, rng)
    room.uses.append(pallet(room, rng))
    room.uses.append(C.use_point(room, "Check the stacks", (2.75, D - 1.85, 0.0), math.radians(180), "inspect",
                                 approach=(W / 2 - 1.3, 2.6, 0.0), who="any"))
    K.stencil(room, "HOLD B - SECURE ALL LOADS", (-2.6, D - 0.035, 2.85), (math.radians(90), 0, 0), 0.08)
    for x0 in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x0, 0.35, 0.25), (1.0, 0.35, 0.1), 8, 0.03, role="emergency")
    Li.haze(room, 0.012)
    Li.camera(room, "Wide master", 22, (0.0, -1.4, 1.6), (0.0, D * 0.68, 1.3), 5.0)
    Li.camera(room, "Hook close", 35, (1.4, 1.6, 1.3), (PALLET[0], PALLET[1], 1.0), 2.6)
    room.arch = A.detail(room, seed=wear_seed, density=0.7, accent=(1.0, 0.55, 0.15, 1), frame_step=1.8,
                         frame_avoid=[(-1.75, 1.75)], walkway=(-2.4, 2.4, 0.5, 2.4))
    room.dressing = Dr.dress(room, "cargo", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
