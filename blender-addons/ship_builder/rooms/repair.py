"""Repair bay: droid doctor scenes.

A 12 cm diamond-plate dais with the repair table on it (the back contact lands on
the table pad), a ceiling arm with a tool head and a work lamp reaching down over
the table, a parts cart beside it, a tool wall, and a scanner arch just inside the
left door that everyone has to walk through (and it beeps).

Use points: step up, lie on the table, hand over parts at the cart, walk through
the scanner (a trigger volume), stand at the tool wall.
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

INFO = {"label": "Repair bay", "size": (7.0, 6.0, 3.2), "doors": {"left": 1.5, "right": 1.5}}

DAIS = (0.6, 3.95, 2.7, 1.9, 0.12)   # centre x, y, width, depth, height
TABLE_Z = 0.74                       # pad top above the deck


def dais(room):
    x, y, w, d, h = DAIS
    pal = room.pal
    dp = M.diamond_plate()
    top = K.box("Dais", (w, d, h), (x, y, h / 2), dp, room.dress, bevel=0.006)
    top["sb_surface"] = "metal"
    hz = M.hazard()
    K.box("Dais Edge Stripe", (w - 0.04, 0.003, h - 0.03), (x, y - d / 2 - 0.0016, h / 2), hz, room.dress, bevel=0, segs=1)
    for sx in (-1, 1):
        K.box("Dais Side Trim", (0.003, d - 0.04, h - 0.03), (x + sx * (w / 2 + 0.0016), y, h / 2), pal["dark_steel"], room.dress, bevel=0, segs=1)
    return h


def table(room, z0):
    x, y = DAIS[0], DAIS[1] + 0.05
    pal = room.pal
    K.cyl("Table Pedestal", 0.16, TABLE_Z - 0.08 - z0, (x, y, z0 + (TABLE_Z - 0.08 - z0) / 2), pal["dark_steel"], room.dress, verts=32, bevel=0.01)
    K.cyl("Table Foot", 0.32, 0.03, (x, y, z0 + 0.015), pal["steel"], room.dress, verts=40, bevel=0.008)
    K.box("Table Top", (1.95, 0.72, 0.06), (x, y, TABLE_Z - 0.05), pal["hull"], room.dress, bevel=0.015)
    pad = K.box("Table Pad", (1.75, 0.56, 0.02), (x, y, TABLE_Z - 0.01), M.rubber("SB Table Pad", (0.05, 0.07, 0.075, 1), 0.65), room.dress, bevel=0.006)
    pad["sb_surface"] = "rubber"
    glow = M.emissive("SB Table Glow", (0.4, 0.9, 1.0, 1), 3.0)
    K.box("Table Glow Edge", (1.9, 0.004, 0.012), (x, y - 0.362, TABLE_Z - 0.05), glow, room.dress, bevel=0, segs=1)
    for sx in (-1, 1):
        K.box("Table Strap", (0.06, 0.6, 0.004), (x + sx * 0.45, y, TABLE_Z + 0.002), M.plastic("SB Strap", (0.25, 0.2, 0.08, 1), 0.7), room.dress, bevel=0, segs=1)
    return Vector((x, y, TABLE_Z))


def arm(room, over):
    """Ceiling arm: mount between two ceiling ribs, a column, an angled forearm and a tool head with a lamp."""
    H = room.H
    pal = room.pal
    my = 3.55                      # between the ribs at y 3.06 and 4.06
    mx = over.x - 0.2
    K.box("Arm Mount", (0.36, 0.36, 0.06), (mx, my, H - 0.03), pal["dark_steel"], room.dress, bevel=0.008)
    K.cyl("Arm Column", 0.06, 0.62, (mx, my, H - 0.06 - 0.31), pal["steel"], room.dress, verts=24, bevel=0.006)
    K.cyl("Arm Elbow", 0.085, 0.16, (mx, my, H - 0.72), pal["accent"], room.dress, verts=32, rot=(0, math.radians(90), 0), bevel=0.01)
    # forearm from the elbow down to the head over the table
    a = Vector((mx, my, H - 0.72))
    b = Vector((over.x + 0.1, over.y, over.z + 0.78))
    L = (b - a).length
    K.box("Arm Forearm", (0.09, L - 0.1, 0.09), (a + b) / 2, pal["steel"], room.dress, bevel=0.012,
          rot=Vector((0, 1, 0)).rotation_difference((b - a).normalized()).to_euler())
    K.cyl("Tool Head", 0.11, 0.12, (b.x, b.y, b.z - 0.04), pal["accent"], room.dress, verts=32, bevel=0.012)
    lens = M.emissive("SB Work Lamp", (1.0, 0.92, 0.8, 1), 8.0)
    K.cyl("Work Lamp Lens", 0.07, 0.006, (b.x, b.y, b.z - 0.103), lens, room.dress, verts=32, bevel=0.001)
    for k, ang in enumerate((0, 120, 240)):
        r = math.radians(ang + 30)
        tx, ty = b.x + 0.085 * math.cos(r), b.y + 0.085 * math.sin(r)
        K.cyl("Tool Bit", 0.008 + 0.003 * k, 0.12 - 0.02 * k, (tx, ty, b.z - 0.1 - (0.06 - 0.01 * k)), pal["steel"], room.dress, verts=12, bevel=0.002)
    K.point_glow(room, (b.x, b.y, b.z - 0.16), (1.0, 0.92, 0.8), 45, 0.06, role="practical")


def cart(room, x, y):
    pal = room.pal
    w, d = 0.55, 0.42
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.cyl("Cart Post", 0.012, 0.78, (x + sx * (w / 2 - 0.02), y + sy * (d / 2 - 0.02), 0.07 + 0.39), pal["steel"], room.dress, verts=12, bevel=0.002)
            K.cyl("Cart Wheel", 0.035, 0.025, (x + sx * (w / 2 - 0.02), y + sy * (d / 2 - 0.02), 0.035), pal["rubber"], room.dress, verts=20, rot=(0, math.radians(90), 0), bevel=0.004)
    for z in (0.3, 0.84):
        K.box("Cart Shelf", (w, d, 0.02), (x, y, z), pal["steel"], room.dress, bevel=0.004)
    tray = K.box("Parts Tray", (0.44, 0.32, 0.04), (x, y, 0.87), pal["dark_steel"], room.dress, bevel=0.004)
    # loose parts in the tray, each resting on the tray floor
    parts = [("Spare Servo", (0.06, 0.04, 0.035)), ("Spare Board", (0.09, 0.06, 0.006)), ("Spare Lens", None), ("Spare Bolt Bag", (0.07, 0.05, 0.02))]
    for i, (nm, sz) in enumerate(parts):
        px, py = x - 0.14 + i * 0.095, y + (0.05 if i % 2 else -0.05)
        if sz is None:
            K.cyl(nm, 0.025, 0.02, (px, py, 0.85 + 0.01 + 0.01), M.glass("SB Lens Glass", (0.6, 0.8, 0.9, 1), 0.05), room.dress, verts=24, bevel=0.003)
        else:
            K.box(nm, sz, (px, py, 0.85 + 0.01 + sz[2] / 2), pal["plastic_grey"] if i % 2 else pal["accent"], room.dress, bevel=0.003)
    return tray


def scanner(room, x, yc, width=1.3, height=2.25):
    pal = room.pal
    body = M.painted_metal("SB Scanner", (0.6, 0.6, 0.58, 1), 0.4)
    beam = M.emissive("SB Scanner Beam", (0.35, 1.0, 0.6, 1), 4.0)
    beam["sb_role"] = "practical"
    for s in (-1, 1):
        y = yc + s * (width / 2 + 0.07)
        K.box("Scanner Post", (0.22, 0.14, height), (x, y, height / 2), body, room.dress, bevel=0.02)
        K.box("Scanner Emitter", (0.04, 0.006, height - 0.4), (x, y - s * 0.073, height / 2), beam, room.dress, bevel=0, segs=1)
    K.box("Scanner Beam Top", (0.26, width + 0.28, 0.16), (x, yc, height + 0.08), body, room.dress, bevel=0.02)
    K.box("Scanner Lamp", (0.04, width - 0.1, 0.006), (x, yc, height - 0.003), beam, room.dress, bevel=0, segs=1)
    K.stencil(room, "SCAN", (x - 0.131, yc, height + 0.08), (math.radians(90), 0, math.radians(-90)), 0.06)
    return C.use_point(room, "Scanner arch", (x, yc, 0.0), math.radians(-90), "walk_through",
                       approach=(x - 0.9, yc, 0.0), contact=None, who="any", trigger=[0.3, width, height])


def tool_wall(room, x, w=2.0):
    """Pegboard on the back wall with tools on hooks."""
    D = room.D
    pal = room.pal
    peg = M.plastic("SB Peg Board", (0.3, 0.24, 0.16, 1), 0.7)
    y = D - 0.032
    K.box("Tool Wall", (w, 0.012, 1.0), (x, y - 0.006, 1.45), peg, room.dress, bevel=0.003)
    yf = y - 0.012
    tools = [(-0.8, "Wrench", (0.04, 0.012, 0.32)), (-0.55, "Wrench", (0.035, 0.012, 0.26)), (-0.3, "Driver", (0.025, 0.02, 0.24)),
             (-0.1, "Driver", (0.022, 0.02, 0.2)), (0.15, "Pliers", (0.06, 0.015, 0.22)), (0.45, "Saw", (0.12, 0.01, 0.3)),
             (0.75, "Multimeter", (0.1, 0.04, 0.16))]
    for dx, nm, (tw, td, th) in tools:
        K.box("Peg Hook", (0.008, 0.04, 0.008), (x + dx, yf - 0.02, 1.75), pal["steel"], room.dress, bevel=0.002, segs=1)
        K.box(nm, (tw, td, th), (x + dx, yf - 0.03 - td / 2 + 0.004, 1.74 - th / 2 - 0.006), pal["dark_steel"] if nm != "Multimeter" else pal["accent"], room.dress, bevel=0.004)
    return C.use_point(room, "Tool wall", (x, D - 0.75, 0.0), math.radians(180), "take_tool",
                       approach=(x, D - 1.4, 0.0), contact="hand -> tool on hook", who="walker")


def build(room_name="Repair bay", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(1.0, 0.7), chamfer=0.4)
    K.ceiling(room, light_rows=2, color=(0.92, 0.96, 1.0, 1), power=24, cols=2, cove=0.3, cove_color=(0.4, 0.9, 1.0, 1), cove_power=3)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Dais", 0.0, 0):
        h = dais(room)
        top = table(room, h)
    with K.piece(room, "Repair arm", 0.0, 0):
        arm(room, top)
    with K.piece(room, "Parts cart", 0.06, 8):
        cart(room, DAIS[0] + DAIS[2] / 2 + 0.45, 3.6)
    with K.piece(room, "Scanner", 0.0, 0):
        room.uses = [scanner(room, -W / 2 + 1.25, dr["left"])]
    room.uses.append(tool_wall(room, -2.0))
    x, y = DAIS[0], DAIS[1]
    room.uses += [
        C.use_point(room, "Step up to the table", (x - 0.9, y - DAIS[3] / 2 + 0.3, DAIS[4]), 0.0, "step_up",
                    approach=(x - 0.9, y - DAIS[3] / 2 - 0.5, 0.0), who="walker", step=DAIS[4]),
        C.use_point(room, "Repair table", (x, y + 0.05, TABLE_Z), 0.0, "lie_on",
                    approach=(x - 0.9, y - DAIS[3] / 2 + 0.3, DAIS[4]), contact="back -> table pad", who="walker"),
        C.use_point(room, "Hand over parts", (DAIS[0] + DAIS[2] / 2 + 0.45, 3.6 - 0.55, 0.0), 0.0, "hand_over",
                    approach=(DAIS[0] + DAIS[2] / 2 + 0.45, 2.4, 0.0), contact="hand -> part in tray", who="walker"),
    ]
    K.screen(room, (1.9, D - 0.04, 1.75), (1, 0, 0), (0, 0, 1), (0, -1, 0), 0.9, 0.55, (0.4, 0.9, 1.0, 1), "ui", name="Diagnostic Screen", strength=1.4)
    K.stencil(room, "REPAIR BAY - NO SPARE PARTS", (-0.2, D - 0.035, 2.75), (math.radians(90), 0, 0), 0.08)
    for x0 in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x0, 0.35, 0.25), (1.0, 0.35, 0.1), 8, 0.03, role="emergency")
    Li.haze(room, 0.012)
    Li.camera(room, "Wide master", 24, (0.3, -1.2, 1.5), (0.3, D * 0.68, 1.0), 5.0)
    Li.camera(room, "Table close", 40, (-0.9, 1.6, 1.55), (0.6, 4.0, 0.85), 2.4)
    room.arch = A.detail(room, seed=wear_seed, density=0.8, accent=(0.4, 0.9, 1.0, 1), frame_step=1.6,
                         frame_avoid=[(-3.1, -0.9), (1.3, 2.5)], walkway=(-1.6, 3.1, 0.3, 2.6))
    room.dressing = Dr.dress(room, "repair", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
