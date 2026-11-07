"""Engine room: the reactor and everything that keeps it from exploding.

A reactor column on a plinth behind a ring of safety rail (open at the front so
a droid can step in to check it), glowing through a glass sleeve with clamp
rings. Two coolant tanks in the back left corner feed it through an overhead
pipe. A run of pipe along the back wall carries a big valve wheel, and a slanted
control lectern faces the core. Warm work light, cold reactor glow.

Use points: read the lectern, turn the valve wheel, step in and check the core.
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

INFO = {"label": "Engine room", "size": (7.0, 6.0, 3.6), "doors": {"left": 1.5, "right": 1.5}}

CORE = (0.7, 3.75)
RAIL_R = 1.25
TANKS = ((-2.55, 4.95), (-1.65, 5.2))
VALVE_X = 2.2


def core(room):
    x, y = CORE
    pal = room.pal
    glow = M.emissive("SB Core Glow", (0.45, 0.8, 1.0, 1), 9.0)
    glow["sb_role"] = "practical"
    K.cyl("Core Plinth", 0.78, 0.25, (x, y, 0.125), pal["hull"], room.dress, verts=48, bevel=0.015)
    K.cyl("Core Plinth Lip", 0.82, 0.03, (x, y, 0.015), pal["dark_steel"], room.dress, verts=48, bevel=0.006)
    K.cyl("Core Base Ring", 0.55, 0.2, (x, y, 0.35), pal["dark_steel"], room.dress, verts=48, bevel=0.012)
    K.cyl("Core Light", 0.32, 2.2, (x, y, 0.45 + 1.1), glow, room.dress, verts=40, bevel=0)
    gl = K.cyl("Core Sleeve", 0.38, 2.2, (x, y, 0.45 + 1.1), pal["glass"], room.dress, verts=48, bevel=0.002)
    gl.visible_shadow = False
    for z in (0.75, 1.45, 2.15):
        K.cyl("Core Clamp", 0.44, 0.09, (x, y, z), pal["accent"], room.dress, verts=48, bevel=0.012)
        for k in range(6):
            a = math.radians(k * 60 + 15)
            K.box("Clamp Bolt Block", (0.06, 0.06, 0.12), (x + 0.45 * math.cos(a), y + 0.45 * math.sin(a), z), pal["dark_steel"], room.dress,
                  bevel=0.008, rot=(0, 0, a))
    K.cyl("Core Cap", 0.6, 0.28, (x, y, 2.65 + 0.14), pal["hull"], room.dress, verts=48, bevel=0.02)
    K.cyl("Core Cap Ring", 0.64, 0.05, (x, y, 2.66), pal["warm"], room.dress, verts=48, bevel=0.008)
    K.cyl("Core Cap Lens", 0.2, 0.01, (x, y, 2.935), glow, room.dress, verts=32, bevel=0)
    for k in range(8):  # cooling fins on the cap
        a = math.radians(k * 45)
        K.box("Cap Fin", (0.2, 0.02, 0.22), (x + 0.68 * math.cos(a), y + 0.68 * math.sin(a), 2.79), pal["dark_steel"], room.dress,
              bevel=0.004, rot=(0, 0, a))
    K.point_glow(room, (x, y - 0.6, 1.5), (0.45, 0.8, 1.0), 120, 0.08, role="practical")


def rail(room):
    """Ring of safety rail around the core, open over the front 70 degrees."""
    x, y = CORE
    pal = room.pal
    yellow = M.painted_metal("SB Rail Yellow", (0.62, 0.45, 0.05, 1), 0.45)
    gap = math.radians(70)
    start = -math.pi / 2 + gap / 2
    n = 10
    span = math.tau - gap
    pts = [start + span * k / n for k in range(n + 1)]
    for a in pts:
        px, py = x + RAIL_R * math.cos(a), y + RAIL_R * math.sin(a)
        K.cyl("Rail Post", 0.025, 1.05, (px, py, 0.525), yellow, room.dress, verts=16, bevel=0.004)
        K.cyl("Rail Foot", 0.05, 0.012, (px, py, 0.006), pal["dark_steel"], room.dress, verts=16, bevel=0.002)
    for z, r in ((1.05, 0.024), (0.55, 0.016)):
        for a0, a1 in zip(pts, pts[1:]):
            p0 = Vector((x + RAIL_R * math.cos(a0), y + RAIL_R * math.sin(a0), z))
            p1 = Vector((x + RAIL_R * math.cos(a1), y + RAIL_R * math.sin(a1), z))
            d = p1 - p0
            K.cyl("Rail Bar", r, d.length + 0.02, (p0 + p1) / 2, yellow, room.dress, verts=12, bevel=0.002,
                  rot=Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler())
    # floor ring: painted keep-out line just outside the rail
    paint = M.painted_metal("SB Floor Paint Yellow", (0.55, 0.4, 0.05, 1), 0.6)
    for k in range(36):
        a0, a1 = math.tau * k / 36, math.tau * (k + 1) / 36
        am = (a0 + a1) / 2
        if abs(math.remainder(am + math.pi / 2, math.tau)) < gap / 2:
            continue
        r = RAIL_R + 0.12
        s = K.box("Keep Out Line", (0.06, 2 * r * math.sin((a1 - a0) / 2) - 0.03, 0.0004), (x + r * math.cos(am), y + r * math.sin(am), 0.0003),
                  paint, room.dress, bevel=0, segs=1, rot=(0, 0, am))
        s["sb_decal"] = True


def tanks(room):
    pal = room.pal
    tank = M.painted_metal("SB Coolant Tank", (0.2, 0.3, 0.32, 1), 0.4)
    tops = []
    for x, y in TANKS:
        K.cyl("Tank Skirt", 0.34, 0.12, (x, y, 0.06), pal["dark_steel"], room.dress, verts=40, bevel=0.008)
        K.cyl("Coolant Tank", 0.36, 1.9, (x, y, 0.12 + 0.95), tank, room.dress, verts=48, bevel=0.03)
        for z in (0.5, 1.6):
            K.cyl("Tank Band", 0.37, 0.05, (x, y, z), pal["dark_steel"], room.dress, verts=48, bevel=0.006)
        K.cyl("Tank Dome", 0.26, 0.12, (x, y, 2.08), tank, room.dress, verts=40, bevel=0.05)
        gauge = M.emissive("SB Tank Gauge", (0.3, 0.9, 1.0, 1), 2.0)
        K.box("Tank Sight Glass", (0.04, 0.004, 0.9), (x, y - 0.362, 1.1), gauge, room.dress, bevel=0, segs=1)
        tops.append(Vector((x, y, 2.14)))
    # overhead feed: up from each tank, across, down onto the core cap
    cx, cy = CORE
    for i, t in enumerate(tops):
        z = 3.05 - 0.14 * i
        K.pipe(room, [t, Vector((t.x, t.y, z)), Vector((cx - 0.3 + 0.2 * i, t.y, z)), Vector((cx - 0.3 + 0.2 * i, cy + 0.25, z)),
                      Vector((cx - 0.3 + 0.2 * i, cy + 0.25, 2.9))], 0.045, pal["steel"], name="Coolant Pipe")


def valve_run(room):
    """Pipe along the back wall at knee and head height, with a big valve wheel."""
    D = room.D
    pal = room.pal
    y = D - 0.17
    for z in (0.55, 1.95):
        K.pipe(room, [Vector((0.3, y, z)), Vector((2.75, y, z))], 0.06, pal["warm"] if z < 1 else pal["steel"], name="Back Pipe")
        for x in (0.6, 1.6, 2.6):
            K.box("Pipe Clamp", (0.05, 0.12, 0.16), (x, D - 0.09, z), pal["dark_steel"], room.dress, bevel=0.006)
    # riser to the valve and the wheel
    K.pipe(room, [Vector((VALVE_X, y, 0.55)), Vector((VALVE_X, y, 1.2))], 0.05, pal["warm"], flanges=False, name="Valve Riser")
    K.cyl("Valve Body", 0.1, 0.22, (VALVE_X, y, 1.28), pal["dark_steel"], room.dress, verts=24, bevel=0.012)
    K.cyl("Valve Stem", 0.018, 0.18, (VALVE_X, y - 0.18, 1.28), pal["steel"], room.dress, verts=12, rot=(math.radians(90), 0, 0), bevel=0.002)
    wheel = M.painted_metal("SB Valve Red", (0.5, 0.06, 0.04, 1), 0.45)
    wc = Vector((VALVE_X, y - 0.28, 1.28))
    K.cyl("Valve Wheel Hub", 0.04, 0.05, wc, wheel, room.dress, verts=16, rot=(math.radians(90), 0, 0), bevel=0.004)
    for k in range(16):
        a0, a1 = math.tau * k / 16, math.tau * (k + 1) / 16
        p0 = wc + Vector((0.2 * math.cos(a0), 0, 0.2 * math.sin(a0)))
        p1 = wc + Vector((0.2 * math.cos(a1), 0, 0.2 * math.sin(a1)))
        d = p1 - p0
        K.cyl("Valve Wheel Rim", 0.016, d.length + 0.012, (p0 + p1) / 2, wheel, room.dress, verts=10, bevel=0.002,
              rot=Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler())
    for k in range(4):
        a = math.radians(45 + 90 * k)
        K.box("Valve Spoke", (0.012, 0.012, 0.18), wc + Vector((0.1 * math.cos(a), 0, 0.1 * math.sin(a))), wheel, room.dress,
              bevel=0.003, rot=(0, -a + math.radians(90), 0))
    return C.use_point(room, "Valve wheel", (VALVE_X, D - 1.0, 0.0), math.radians(180), "turn_valve",
                       approach=(VALVE_X, D - 1.7, 0.0), contact="both hands -> wheel rim", who="walker")


def lectern(room, x, y):
    pal = room.pal
    K.box("Lectern Foot", (0.6, 0.45, 0.04), (x, y, 0.02), pal["dark_steel"], room.dress, bevel=0.006)
    K.box("Lectern Body", (0.42, 0.3, 0.95), (x, y + 0.03, 0.04 + 0.475), pal["hull"], room.dress, bevel=0.012)
    a = math.radians(35)
    n = Vector((0, -math.sin(a), math.cos(a)))
    v = Vector((0, math.cos(a), math.sin(a)))
    top = Vector((x, y - 0.02, 1.08))
    K.box("Lectern Desk", (0.62, 0.48, 0.05), top - n * 0.025, pal["panel"], room.dress, bevel=0.01, rot=(a, 0, 0))
    scr = K.screen(room, top + v * 0.04, (1, 0, 0), v, n, 0.44, 0.26, (1.0, 0.6, 0.25, 1), "ui", light=False,
                   name="Reactor Readout", strength=1.6, depth=0.012, margin=0.015)
    Sc.lock(scr, "BARS")
    for k in range(5):
        K.box("Lectern Key", (0.05, 0.035, 0.012), top - v * 0.17 + Vector((-0.12 + 0.06 * k, 0, 0)) + n * 0.006,
              pal["warm"] if k == 2 else pal["plastic_grey"], room.dress, bevel=0.003, rot=(a, 0, 0))
    return C.use_point(room, "Reactor lectern", (x, y - 0.6, 0.0), math.radians(180), "use_console",
                       approach=(x - 0.2, y - 1.3, 0.0), contact="hands -> lectern keys", who="walker")


def build(room_name="Engine room", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(0.9, 0.8), chamfer=0.4)
    K.ceiling(room, light_rows=2, color=(1.0, 0.78, 0.55, 1), power=20, cols=2, cove=0.25, cove_color=(1.0, 0.55, 0.25, 1), cove_power=4)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Reactor", 0.0, 0):  # the feed pipes plug into the cap, so tanks and core are one assembly
        core(room)
        tanks(room)
    with K.piece(room, "Core rail", 0.0, 0):
        rail(room)
    with K.piece(room, "Valve run", 0.0, 0):
        room.uses = [valve_run(room)]
    with K.piece(room, "Lectern", 0.02, 4):
        room.uses.append(lectern(room, -1.35, 3.35))
    x, y = CORE
    room.uses.append(C.use_point(room, "Check the core", (x, y - 0.85, 0.0), math.radians(180), "inspect",
                                 approach=(x, y - RAIL_R - 0.6, 0.0), contact=None, who="any"))
    K.stencil(room, "REACTOR 2 - KEEP CLEAR", (-0.6, D - 0.035, 2.6), (math.radians(90), 0, 0), 0.09)
    for x0 in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x0, 0.35, 0.25), (1.0, 0.35, 0.1), 8, 0.03, role="emergency")
    Li.haze(room, 0.016)
    Li.camera(room, "Wide master", 22, (0.2, -1.3, 1.55), (0.3, D * 0.66, 1.3), 5.0)
    Li.camera(room, "Core low", 28, (-1.6, 1.5, 0.75), (0.7, 3.75, 1.6), 3.0)
    room.arch = A.detail(room, seed=wear_seed, density=0.9, accent=(1.0, 0.55, 0.25, 1), frame_step=1.5,
                         frame_avoid=[(0.1, 3.0)], walkway=(-2.8, 2.8, 0.5, 2.3))
    room.dressing = Dr.dress(room, "engine", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
