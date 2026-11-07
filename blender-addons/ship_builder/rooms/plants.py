"""Plant room: hydroponics, and the gardener's pride.

Two three-shelf grow racks along the back wall, each shelf a tray of soil with a
row of leafy seedlings under a magenta grow light, a misting pipe along the top
rail. A raised bed in the middle with taller plants tied to stakes, and a water
tank with a hose reel by the right door. Leaves are real thin blades in two
greens, never balls of foliage.

Use points: water a rack, tend the raised bed, fill the can at the tank.
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

INFO = {"label": "Plant room", "size": (6.6, 5.2, 3.2), "doors": {"left": 1.5, "right": 1.5}}

RACKS = (-1.35, 1.35)
RACK_L, RACK_D = 2.2, 0.56
SHELVES = (0.32, 0.98, 1.64)
TOP = 2.2
BED = (0.0, 3.05, 1.7, 0.7, 0.55)   # centre x, y, length, depth, height
TANK = (2.75, 3.65, 0.34, 1.35)


def rack(room, x, rng, greens):
    D = room.D
    pal = room.pal
    y = D - 0.09 - RACK_D / 2
    soil = M.painted_metal("SB Soil", (0.05, 0.035, 0.025, 1), 0.95)
    tray = M.plastic("SB Grow Tray", (0.06, 0.07, 0.07, 1), 0.5)
    grow = M.emissive("SB Grow Light", (0.95, 0.25, 0.85, 1), 5.0)
    grow["sb_role"] = "practical"
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.box("Rack Post", (0.04, 0.04, TOP), (x + sx * (RACK_L / 2 - 0.02), y + sy * (RACK_D / 2 - 0.02), TOP / 2), pal["steel"], room.dress, bevel=0.004)
    K.box("Rack Top Rail", (RACK_L, RACK_D, 0.03), (x, y, TOP - 0.015), pal["steel"], room.dress, bevel=0.004)
    for k, z in enumerate(SHELVES):
        K.box("Rack Shelf", (RACK_L - 0.02, RACK_D - 0.02, 0.025), (x, y, z), pal["steel"], room.dress, bevel=0.004)
        K.box("Grow Tray", (RACK_L - 0.12, RACK_D - 0.1, 0.08), (x, y, z + 0.0125 + 0.04), tray, room.dress, bevel=0.008)
        K.box("Tray Soil", (RACK_L - 0.16, RACK_D - 0.14, 0.012), (x, y, z + 0.0125 + 0.074), soil, room.dress, bevel=0.002)
        base_z = z + 0.0125 + 0.08
        above = SHELVES[k + 1] - 0.0125 if k + 1 < len(SHELVES) else TOP - 0.03
        # grow light under the shelf above
        K.box("Grow Light Bar", (RACK_L - 0.2, 0.05, 0.025), (x, y, above - 0.0125), pal["dark_steel"], room.dress, bevel=0.004)
        K.box("Grow Light Diffuser", (RACK_L - 0.24, 0.035, 0.003), (x, y, above - 0.0265), grow, room.dress, bevel=0, segs=1)
        K.light_strip(room, (x, y - 0.12, above - 0.015), RACK_L - 0.4, "X", (0, 0, -1), (0.95, 0.3, 0.85, 1), 6, role="practical", width=0.02)
        n = 6
        room_h = above - 0.06 - base_z
        for j in range(n):
            px = x - (RACK_L - 0.4) / 2 + j * (RACK_L - 0.4) / (n - 1) + rng.uniform(-0.03, 0.03)
            for row, py in enumerate((y - 0.1, y + 0.1)):
                if rng.random() < 0.15:
                    continue
                h = min(room_h - 0.05, rng.uniform(0.12, 0.22))
                O.plant(room, (px + (0.05 if row else -0.05), py, base_z - 0.006), h, rng, greens[(j + row) % 2],
                        leaves=rng.randint(5, 8), leaf_len=0.075, name="Seedling")
    # misting pipe along the top with nozzles
    K.pipe(room, [Vector((x - RACK_L / 2 + 0.02, y - RACK_D / 2 + 0.02, TOP - 0.042)), Vector((x + RACK_L / 2 - 0.02, y - RACK_D / 2 + 0.02, TOP - 0.042))],
           0.012, pal["steel"], flanges=False, name="Mist Pipe")
    return C.use_point(room, f"Water rack {'left' if x < 0 else 'right'}", (x, y - RACK_D / 2 - 0.55, 0.0), math.radians(180), "water",
                       approach=(x, y - RACK_D / 2 - 1.2, 0.0), contact="hand -> watering can spout over tray", who="any")


def bed(room, rng, greens):
    x, y, L, d, h = BED
    pal = room.pal
    wood = M.painted_metal("SB Bed Planks", (0.24, 0.15, 0.08, 1), 0.7)
    soil = M.painted_metal("SB Soil", (0.05, 0.035, 0.025, 1), 0.95)
    t = 0.05
    K.box("Bed Floor", (L, d, 0.04), (x, y, 0.02), pal["dark_steel"], room.dress, bevel=0.004)
    for sx in (-1, 1):
        K.box("Bed Side", (L, t, h), (x, y + sx * (d / 2 - t / 2), h / 2), wood, room.dress, bevel=0.006)
        K.box("Bed End", (t, d - 2 * t, h), (x + sx * (L / 2 - t / 2), y, h / 2), wood, room.dress, bevel=0.006)
    K.box("Bed Soil", (L - 2 * t, d - 2 * t, h - 0.1), (x, y, 0.04 + (h - 0.1) / 2), soil, room.dress, bevel=0.003)
    top = 0.04 + h - 0.1
    for j in range(4):
        px = x - L / 2 + 0.25 + j * (L - 0.5) / 3
        sh = rng.uniform(0.75, 0.95)
        K.cyl("Plant Stake", 0.008, sh + 0.12, (px + 0.05, y, top - 0.12 + (sh + 0.12) / 2), M.painted_metal("SB Bamboo", (0.45, 0.36, 0.18, 1), 0.6), room.dress, verts=8, bevel=0.001)
        O.plant(room, (px - 0.02, y, top - 0.006), sh * 0.85, rng, greens[j % 2], leaves=rng.randint(9, 12), leaf_len=0.16, name="Bed Plant")
        K.cyl("Plant Tie", 0.02, 0.01, (px + 0.04, y, top + sh * 0.5), M.plastic("SB Tie", (0.4, 0.3, 0.1, 1), 0.6), room.dress, verts=12, bevel=0.002)
    return C.use_point(room, "Tend the raised bed", (x, y - d / 2 - 0.5, 0.0), math.radians(180), "tend",
                       approach=(x - 0.4, y - d / 2 - 1.1, 0.0), contact="hands -> leaves", who="any")


def tank(room):
    x, y, r, h = TANK
    pal = room.pal
    K.cyl("Water Tank Base", r + 0.03, 0.08, (x, y, 0.04), pal["dark_steel"], room.dress, verts=40, bevel=0.006)
    K.cyl("Water Tank", r, h, (x, y, 0.08 + h / 2), M.plastic("SB Tank Blue", (0.12, 0.22, 0.3, 1), 0.35), room.dress, verts=48, bevel=0.03)
    K.box("Tank Level Strip", (0.004, 0.05, h * 0.8), (x - r - 0.001, y, 0.08 + h / 2), M.emissive("SB Level", (0.3, 0.75, 1.0, 1), 1.5), room.dress, bevel=0, segs=1)
    K.cyl("Tank Tap", 0.02, 0.12, (x - r - 0.05, y, 0.3), pal["steel"], room.dress, verts=12, rot=(0, math.radians(90), 0), bevel=0.002)
    K.cyl("Hose Reel", 0.13, 0.08, (x - r - 0.05, y + r - 0.08, 0.95), M.plastic("SB Hose Green", (0.08, 0.25, 0.08, 1), 0.5), room.dress, verts=32,
          rot=(0, math.radians(90), 0), bevel=0.015)
    K.box("Reel Bracket", (0.18, 0.05, 0.06), (x - r + 0.06, y + r - 0.08, 0.95), pal["dark_steel"], room.dress, bevel=0.004)
    can = M.painted_metal("SB Watering Can", (0.5, 0.42, 0.1, 1), 0.45)
    K.cyl("Watering Can", 0.08, 0.2, (x - r - 0.3, y - 0.15, 0.1), can, room.dress, verts=24, bevel=0.01)
    K.cyl("Can Spout", 0.012, 0.22, (x - r - 0.42, y - 0.15, 0.17), can, room.dress, verts=12, rot=(0, math.radians(-55), 0), bevel=0.002)
    return C.use_point(room, "Fill the can", (x - r - 0.6, y, 0.0), math.radians(-90 + 180), "fill",
                       approach=(x - r - 1.2, y - 0.4, 0.0), contact="hand -> tank tap", who="walker")


def build(room_name="Plant room", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    rng = random.Random(wear_seed * 23 + 4)
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(0.9, 0.7), chamfer=0.4)
    K.ceiling(room, light_rows=1, color=(1.0, 0.92, 0.8, 1), power=16, cols=2, cove=0.24, cove_color=(0.9, 0.3, 0.8, 1), cove_power=3)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    greens = O.greens()
    room.uses = []
    for x in RACKS:
        with K.piece(room, "Grow rack", 0.0, 0):
            room.uses.append(rack(room, x, rng, greens))
    with K.piece(room, "Raised bed", 0.0, 0):
        room.uses.append(bed(room, rng, greens))
    with K.piece(room, "Water tank", 0.0, 0):
        room.uses.append(tank(room))
    K.stencil(room, "HYDROPONICS - TALK TO THEM", (0.0, D - 0.035, 2.55), (math.radians(90), 0, 0), 0.07)
    for x0 in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x0, 0.35, 0.25), (1.0, 0.35, 0.1), 6, 0.03, role="emergency")
    Li.haze(room, 0.014)
    Li.camera(room, "Wide master", 24, (0.0, -1.2, 1.5), (0.0, D * 0.72, 1.1), 4.5)
    Li.camera(room, "Rack close", 35, (-0.2, 2.2, 1.2), (RACKS[0], D - 0.4, 1.0), 2.3)
    room.arch = A.detail(room, seed=wear_seed, density=0.6, accent=(0.9, 0.3, 0.8, 1), frame_step=1.6,
                         frame_avoid=[(-2.6, 2.6)], walkway=(-2.4, 2.4, 0.5, 2.5))
    room.dressing = Dr.dress(room, "plants", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
