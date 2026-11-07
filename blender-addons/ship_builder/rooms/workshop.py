"""Workshop: where the crew builds, bodges and breaks things.

A three-metre workbench along the back wall with a vice, a clamp lamp and a
pegboard of tools above it, a pillar drill to its right, a welding cart with two
gas bottles chained on, and a parts shelf by the right door with labelled bins.
Warm bench light against a cooler room.

Use points: work at the vice, run the drill, pick up the welder, take a bin.
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
from . import repair as R
from .. import wear as Wr
from .. import arch as A

INFO = {"label": "Workshop", "size": (7.0, 5.6, 3.2), "doors": {"left": 1.5, "right": 1.5}}

BENCH = (-1.2, 3.0, 0.75, 0.92)   # centre x, length, depth, top height
DRILL_X = 1.0
WELD = (2.1, 0.0)                 # x, (y set from D)
SHELF_Y = (3.45, 4.55)


def bench(room):
    D = room.D
    x, L, d, top = BENCH
    pal = room.pal
    y = D - 0.09 - d / 2
    wood = M.painted_metal("SB Bench Top", (0.22, 0.16, 0.1, 1), 0.65)
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.box("Bench Leg", (0.07, 0.07, top - 0.06), (x + sx * (L / 2 - 0.08), y + sy * (d / 2 - 0.06), (top - 0.06) / 2), pal["dark_steel"], room.dress, bevel=0.006)
    K.box("Bench Shelf", (L - 0.1, d - 0.06, 0.03), (x, y, 0.22), pal["steel"], room.dress, bevel=0.004)
    t = K.box("Bench Top", (L, d, 0.06), (x, y, top - 0.03), wood, room.dress, bevel=0.008)
    t["sb_surface"] = "wood"
    K.box("Bench Lip", (L, 0.03, 0.08), (x, y - d / 2 - 0.015, top - 0.05), pal["dark_steel"], room.dress, bevel=0.004)
    # vice at the left end
    vx = x - L / 2 + 0.45
    vy = y - d / 2 + 0.12
    K.box("Vice Base", (0.2, 0.16, 0.05), (vx, vy, top + 0.025), pal["accent"], room.dress, bevel=0.008)
    K.box("Vice Body", (0.14, 0.26, 0.1), (vx, vy, top + 0.1), pal["accent"], room.dress, bevel=0.01)
    for dy in (-0.06, 0.06):
        K.box("Vice Jaw", (0.16, 0.025, 0.06), (vx, vy + dy, top + 0.18), pal["steel"], room.dress, bevel=0.004)
    K.cyl("Vice Screw", 0.012, 0.28, (vx, vy - 0.2, top + 0.11), pal["steel"], room.dress, verts=12, rot=(math.radians(90), 0, 0), bevel=0.002)
    K.cyl("Vice Handle", 0.008, 0.22, (vx, vy - 0.33, top + 0.11), pal["steel"], room.dress, verts=10, rot=(0, math.radians(90), 0), bevel=0.002)
    # clamp lamp at the right end: post, arm, shade
    lx = x + L / 2 - 0.35
    ly = y + d / 2 - 0.12
    K.box("Lamp Clamp", (0.08, 0.1, 0.08), (lx, ly, top + 0.04), pal["dark_steel"], room.dress, bevel=0.006)
    K.cyl("Lamp Post", 0.012, 0.6, (lx, ly, top + 0.38), pal["steel"], room.dress, verts=12, bevel=0.002)
    a = Vector((lx, ly, top + 0.68))
    b = Vector((lx - 0.45, ly - 0.25, top + 0.55))
    dv = b - a
    K.cyl("Lamp Arm", 0.01, dv.length, (a + b) / 2, pal["steel"], room.dress, verts=10, bevel=0.002,
          rot=Vector((0, 0, 1)).rotation_difference(dv.normalized()).to_euler())
    K.cyl("Lamp Shade", 0.08, 0.1, b - Vector((0, 0, 0.04)), pal["warm"], room.dress, verts=24, bevel=0.01)
    K.cyl("Lamp Bulb", 0.05, 0.004, b - Vector((0, 0, 0.092)), M.emissive("SB Bench Lamp", (1.0, 0.8, 0.55, 1), 10.0), room.dress, verts=24, bevel=0)
    K.point_glow(room, b - Vector((0, 0, 0.16)), (1.0, 0.8, 0.55), 35, 0.05, role="practical")
    # things on the bench
    K.box("Bench Part Board", (0.22, 0.15, 0.006), (x + 0.1, y, top + 0.003), M.plastic("SB Board Green", (0.05, 0.22, 0.1, 1), 0.4), room.dress, bevel=0.001)
    K.box("Bench Servo", (0.08, 0.05, 0.05), (x - 0.3, y + 0.15, top + 0.025), pal["plastic_grey"], room.dress, bevel=0.006)
    K.cyl("Solder Spool", 0.04, 0.03, (x + 0.45, y + 0.12, top + 0.015), pal["steel"], room.dress, verts=20, bevel=0.003)
    return C.use_point(room, "Work at the vice", (vx, vy - 0.62, 0.0), math.radians(180), "work_bench",
                       approach=(vx + 0.2, vy - 1.3, 0.0), contact="hands -> vice jaws", who="walker")


def drill(room, x):
    D = room.D
    pal = room.pal
    y = D - 0.09 - 0.25
    body = M.painted_metal("SB Drill Green", (0.12, 0.2, 0.14, 1), 0.45)
    K.box("Drill Base", (0.42, 0.5, 0.08), (x, y, 0.04), body, room.dress, bevel=0.012)
    K.cyl("Drill Column", 0.035, 1.5, (x, y + 0.12, 0.08 + 0.75), pal["steel"], room.dress, verts=20, bevel=0.003)
    K.box("Drill Table", (0.3, 0.3, 0.03), (x, y - 0.05, 0.85), body, room.dress, bevel=0.006)
    K.box("Table Collar", (0.1, 0.1, 0.1), (x, y + 0.12, 0.85), body, room.dress, bevel=0.01)
    K.box("Drill Head", (0.24, 0.42, 0.26), (x, y + 0.02, 1.35), body, room.dress, bevel=0.03)
    K.box("Drill Motor", (0.2, 0.2, 0.22), (x, y + 0.2, 1.6), pal["dark_steel"], room.dress, bevel=0.03)
    K.cyl("Drill Quill", 0.03, 0.18, (x, y - 0.1, 1.13), pal["steel"], room.dress, verts=16, bevel=0.003)
    K.cyl("Drill Chuck", 0.022, 0.06, (x, y - 0.1, 1.01), pal["dark_steel"], room.dress, verts=16, bevel=0.003)
    for k in range(3):
        a = math.radians(-30 + 120 * k)
        K.cyl("Feed Handle", 0.008, 0.2, (x + 0.12 + 0.1 * math.cos(a) * 0.0, y + 0.02 + 0.1 * math.sin(a), 1.35 + 0.1 * math.cos(a)),
              pal["steel"], room.dress, verts=10, rot=(a, 0, 0), bevel=0.002)
    return C.use_point(room, "Pillar drill", (x, y - 0.65, 0.0), math.radians(180), "use_machine",
                       approach=(x, y - 1.3, 0.0), contact="hand -> feed handle", who="walker")


def welder(room, x):
    D = room.D
    pal = room.pal
    y = D - 0.09 - 0.3
    K.box("Weld Cart Base", (0.6, 0.5, 0.04), (x, y, 0.13), pal["dark_steel"], room.dress, bevel=0.006)
    for sx in (-1, 1):
        K.cyl("Cart Wheel", 0.09, 0.04, (x + sx * 0.24, y + 0.12, 0.09), pal["rubber"], room.dress, verts=24, rot=(0, math.radians(90), 0), bevel=0.008)
        K.cyl("Cart Caster", 0.035, 0.03, (x + sx * 0.24, y - 0.18, 0.035), pal["rubber"], room.dress, verts=16, rot=(0, math.radians(90), 0), bevel=0.004)
        K.box("Caster Fork", (0.05, 0.04, 0.08), (x + sx * 0.24, y - 0.18, 0.08), pal["dark_steel"], room.dress, bevel=0.004)
    K.box("Cart Handle Post", (0.03, 0.03, 0.85), (x, y + 0.23, 0.15 + 0.425), pal["dark_steel"], room.dress, bevel=0.004)
    gas = (M.painted_metal("SB Bottle Blue", (0.06, 0.12, 0.3, 1), 0.4), M.painted_metal("SB Bottle Maroon", (0.3, 0.05, 0.05, 1), 0.4))
    for k, sx in enumerate((-1, 1)):
        bx = x + sx * 0.14
        K.cyl("Gas Bottle", 0.1, 1.0, (bx, y + 0.08, 0.15 + 0.5), gas[k], room.dress, verts=32, bevel=0.04)
        K.cyl("Bottle Valve", 0.025, 0.1, (bx, y + 0.08, 1.2), pal["steel"], room.dress, verts=16, bevel=0.004)
    K.box("Bottle Chain Bar", (0.5, 0.03, 0.03), (x, y + 0.2, 0.95), pal["steel"], room.dress, bevel=0.004)
    K.box("Welder Unit", (0.4, 0.3, 0.28), (x, y - 0.1, 0.15 + 0.14), pal["warm"], room.dress, bevel=0.02)
    K.box("Welder Face", (0.3, 0.004, 0.16), (x, y - 0.252, 0.3), pal["plastic"], room.dress, bevel=0, segs=1)
    K.cyl("Welder Dial", 0.03, 0.02, (x - 0.08, y - 0.26, 0.32), pal["plastic_grey"], room.dress, verts=16, rot=(math.radians(90), 0, 0), bevel=0.003)
    K.box("Welding Torch", (0.04, 0.04, 0.22), (x + 0.12, y - 0.28, 0.5), pal["plastic"], room.dress, bevel=0.01)
    K.box("Torch Holster", (0.06, 0.05, 0.08), (x + 0.12, y - 0.27, 0.43), pal["dark_steel"], room.dress, bevel=0.006)
    return C.use_point(room, "Pick up the welder", (x - 0.1, y - 0.85, 0.0), math.radians(180), "take",
                       approach=(x - 0.3, y - 1.5, 0.0), contact="hand -> torch", who="walker")


def shelf(room, rng):
    W = room.W
    pal = room.pal
    x = W / 2 - 0.09 - 0.2
    y0, y1 = SHELF_Y
    for y in (y0 + 0.03, y1 - 0.03):
        for dx in (-0.17, 0.17):
            K.box("Shelf Upright", (0.035, 0.035, 1.9), (x + dx, y, 0.95), pal["dark_steel"], room.dress, bevel=0.004)
    bins = [M.plastic("SB Bin Blue", (0.05, 0.15, 0.35, 1), 0.5), M.plastic("SB Bin Orange", (0.5, 0.2, 0.04, 1), 0.5),
            M.plastic("SB Bin Grey", (0.25, 0.26, 0.27, 1), 0.5)]
    for k, z in enumerate((0.15, 0.6, 1.05, 1.5)):
        K.box("Shelf Deck", (0.4, y1 - y0, 0.025), (x, (y0 + y1) / 2, z), pal["steel"], room.dress, bevel=0.004)
        n = 3
        for j in range(n):
            by = y0 + 0.12 + j * ((y1 - y0 - 0.24) / (n - 1))
            h = rng.choice((0.16, 0.2, 0.24))
            K.box("Parts Bin", (0.3, 0.26, h), (x - 0.02, by, z + 0.0125 + h / 2), bins[(j + k) % 3], room.dress, bevel=0.01)
            K.box("Bin Label", (0.004, 0.12, 0.05), (x - 0.172, by, z + 0.0125 + h * 0.6), M.plastic("SB Label", (0.75, 0.72, 0.62, 1), 0.6), room.dress, bevel=0, segs=1)
    return C.use_point(room, "Take a bin", (x - 0.75, (y0 + y1) / 2, 0.0), math.radians(-90), "take",
                       approach=(x - 1.4, (y0 + y1) / 2 - 0.3, 0.0), contact="hands -> bin", who="walker")


def build(room_name="Workshop", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    rng = random.Random(wear_seed * 13 + 1)
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(1.0, 0.7), chamfer=0.4)
    K.ceiling(room, light_rows=2, color=(0.88, 0.93, 1.0, 1), power=20, cols=2, cove=0.26, cove_color=(1.0, 0.6, 0.25, 1), cove_power=3)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Workbench", 0.0, 0):
        room.uses = [bench(room)]
    R.tool_wall(room, BENCH[0] + 0.1, w=2.2)
    for ob in [o for o in room.props.objects if o.name.startswith("Use: Tool wall")]:
        import bpy
        bpy.data.objects.remove(ob)  # the bench stands under it, so tools are reached from the vice spot
    with K.piece(room, "Pillar drill", 0.02, 3):
        room.uses.append(drill(room, DRILL_X))
    with K.piece(room, "Weld cart", 0.06, 8):
        room.uses.append(welder(room, WELD[0]))
    with K.piece(room, "Parts shelf", 0.0, 0):
        room.uses.append(shelf(room, rng))
    K.stencil(room, "WORKSHOP - EYES AND OPTICS ON", (-1.1, D - 0.035, 2.55), (math.radians(90), 0, 0), 0.07)
    for x0 in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x0, 0.35, 0.25), (1.0, 0.35, 0.1), 6, 0.03, role="emergency")
    Li.haze(room, 0.012)
    Li.camera(room, "Wide master", 24, (0.0, -1.2, 1.5), (0.0, D * 0.7, 1.15), 4.5)
    Li.camera(room, "Bench close", 35, (0.2, 2.6, 1.45), (BENCH[0] - 0.6, D - 0.4, 1.05), 2.4)
    room.arch = A.detail(room, seed=wear_seed, density=0.8, accent=(1.0, 0.6, 0.25, 1), frame_step=1.6,
                         frame_avoid=[(-2.8, 2.5)], walkway=(-2.6, 2.6, 0.5, 2.5))
    room.dressing = Dr.dress(room, "workshop", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
