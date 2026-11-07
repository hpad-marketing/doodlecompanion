"""Charging stations: the droids' bedroom.

Four charge alcoves along the back wall, each with a raised charge pad (2 cm, it
counts as floor, so feet land on it), a back socket with its charge lead hanging
in a holster, a battery gauge and a bay number. A docking cradle on the left wall
for the hover drone. Night-time light: low blue from under the alcove hoods.

Use points: back into an alcove and plug in (walkers), dock on the cradle (hover).
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

INFO = {"label": "Charging stations", "size": (6.6, 5.0, 3.0), "doors": {"left": 1.5, "right": 1.5}}

BAY_W = 1.24       # centre to centre
FIN_T = 0.08
DEPTH = 0.75       # alcove depth
HOOD_Z = 2.35
BACK = 0.09        # in front of the skirting and wall plating
PAD_H = 0.02


def bays(room):
    n = 4
    return [(-(n - 1) / 2 + i) * BAY_W for i in range(n)]


def alcoves(room):
    W, D = room.W, room.D
    pal = room.pal
    body = M.painted_metal("SB Alcove", (0.13, 0.15, 0.16, 1), 0.5)
    pad = M.rubber("SB Charge Pad", (0.03, 0.032, 0.035, 1), 0.7)
    glow = M.emissive("SB Charge Glow", (0.25, 0.75, 1.0, 1), 4.0)
    glow["sb_role"] = "practical"
    led = M.emissive("SB Socket LED", (0.3, 1.0, 0.45, 1), 6.0)
    lead = M.rubber("SB Charge Lead", (0.06, 0.06, 0.065, 1), 0.55)
    xs = bays(room)
    y_back = D - BACK
    y_front = y_back - DEPTH
    fins = [xs[0] - BAY_W / 2] + [x + BAY_W / 2 for x in xs]
    for fx in fins:
        K.box("Alcove Fin", (FIN_T, DEPTH, HOOD_Z), (fx, (y_back + y_front) / 2, HOOD_Z / 2), body, room.dress, bevel=0.01)
        K.box("Fin Edge Trim", (FIN_T + 0.012, 0.03, HOOD_Z - 0.1), (fx, y_front - 0.015, HOOD_Z / 2), pal["dark_steel"], room.dress, bevel=0.006)
    span = fins[-1] - fins[0] + FIN_T
    K.box("Alcove Hood", (span, DEPTH + 0.06, 0.12), (0, (y_back + y_front) / 2 - 0.03, HOOD_Z + 0.06), body, room.dress, bevel=0.012)
    K.box("Hood Lip", (span, 0.05, 0.05), (0, y_front - 0.085, HOOD_Z + 0.095), pal["dark_steel"], room.dress, bevel=0.008)
    out = []
    for i, x in enumerate(xs):
        inner = BAY_W - FIN_T - 0.006
        # back board, sockets and gauge
        K.box("Alcove Backboard", (inner, 0.02, HOOD_Z - 0.01), (x, y_back - 0.01, (HOOD_Z - 0.01) / 2 + 0.005), pal["panel"], room.dress, bevel=0.004)
        bf = y_back - 0.02  # board front face
        K.box("Charge Socket", (0.16, 0.04, 0.2), (x - 0.18, bf - 0.02, 0.98), pal["dark_steel"], room.dress, bevel=0.008)
        K.cyl("Socket Port", 0.035, 0.006, (x - 0.18, bf - 0.043, 1.0), pal["plastic"], room.dress, verts=24, rot=(math.radians(90), 0, 0), bevel=0.002)
        K.box("Socket LED", (0.02, 0.004, 0.008), (x - 0.18, bf - 0.042, 0.9), led, room.dress, bevel=0, segs=1)
        # the lead: socket bottom down in a loop to the holster on the right
        K.box("Lead Holster", (0.08, 0.05, 0.12), (x + 0.3, bf - 0.025, 1.18), pal["dark_steel"], room.dress, bevel=0.008)
        K.cable(room, (x - 0.18, bf - 0.045, 0.875), (x + 0.3, bf - 0.055, 1.115), 0.35, 0.014, lead, name="Charge Lead")
        K.cyl("Lead Plug", 0.022, 0.09, (x + 0.3, bf - 0.055, 1.27), pal["plastic"], room.dress, verts=20, bevel=0.004)
        gauge = K.screen(room, (x, bf, 1.72), (1, 0, 0), (0, 0, 1), (0, -1, 0), 0.34, 0.18, (0.3, 1.0, 0.45, 1), "ui",
                         light=False, name="Battery Gauge", strength=1.2, depth=0.03, margin=0.02)
        Sc.lock(gauge, "BARS")
        K.stencil(room, f"{i + 1:02d}", (x, y_front - 0.111, HOOD_Z + 0.06), (math.radians(90), 0, 0), 0.08)
        # the charge pad, a glowing strip along its front edge and two foot marks
        pd = K.box("Charge Pad", (inner - 0.08, DEPTH - 0.1, PAD_H), (x, (y_back + y_front) / 2 - 0.02, PAD_H / 2), pad, room.dress, bevel=0.004)
        pd["sb_surface"] = "rubber"
        K.box("Charge Pad Glow", (inner - 0.16, 0.025, 0.002), (x, y_front + 0.05, PAD_H + 0.001), glow, room.dress, bevel=0, segs=1)
        K.light_strip(room, (x, (y_back + y_front) / 2, HOOD_Z - 0.03), inner - 0.2, "X", (0, 0, -1), (0.35, 0.65, 1.0, 1), 5,
                      role="practical", width=0.03)
        out.append(C.use_point(room, f"Charge bay {i + 1}", (x, (y_back + y_front) / 2 - 0.02, PAD_H), 0.0, "back_in_plug",
                               approach=(x, y_front - 0.9, 0.0), contact="back charge port -> socket lead", who="walker"))
    return out


def cradle(room, y, z):
    """Wall cradle the hover drone docks on: two padded prongs and a charge ring."""
    W = room.W
    pal = room.pal
    x0 = -W / 2 + 0.032
    K.box("Cradle Plate", (0.02, 0.5, 0.42), (x0 + 0.01, y, z), pal["dark_steel"], room.dress, bevel=0.006)
    for dy in (-0.14, 0.14):
        K.box("Cradle Prong", (0.3, 0.05, 0.05), (x0 + 0.0205 + 0.15, y + dy, z - 0.12), pal["steel"], room.dress, bevel=0.012)
        K.box("Prong Pad", (0.2, 0.046, 0.012), (x0 + 0.02 + 0.18, y + dy, z - 0.12 + 0.0315), pal["rubber"], room.dress, bevel=0.004)
    ring = M.emissive("SB Cradle Ring", (0.25, 0.75, 1.0, 1), 3.0)
    K.cyl("Cradle Ring", 0.09, 0.008, (x0 + 0.024, y, z + 0.08), ring, room.dress, verts=32, rot=(0, math.radians(90), 0), bevel=0.002)
    return C.use_point(room, "Drone cradle", (x0 + 0.2, y, z - 0.12 + 0.037), math.radians(90), "dock",
                       approach=(x0 + 0.9, y, z + 0.2), contact="belly -> prong pads", who="hover")


def build(room_name="Charging stations", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    C.shell(room, left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(0.9, 0.7), chamfer=0.3)
    K.ceiling(room, light_rows=1, color=(0.55, 0.65, 1.0, 1), power=8, cols=2, cove=0.22, cove_back=False, cove_color=(0.35, 0.65, 1.0, 1), cove_power=2)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Alcoves", 0.0, 0):
        room.uses = alcoves(room)
    room.uses.append(cradle(room, 3.55, 1.55))
    K.stencil(room, "CHARGING - QUIET HOURS", (0.0, D - 0.035, HOOD_Z + 0.33), (math.radians(90), 0, 0), 0.07)
    for x in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x, 0.35, 0.25), (1.0, 0.35, 0.1), 6, 0.03, role="emergency")
    Li.haze(room, 0.012)
    Li.camera(room, "Wide master", 24, (0.0, -1.1, 1.4), (0.0, D * 0.75, 1.05), 4.5)
    Li.camera(room, "Alcove two-shot", 35, (1.2, 1.2, 1.3), (0.0, D - 0.4, 1.0), 2.8)
    room.arch = A.detail(room, seed=wear_seed, density=0.7, accent=(0.35, 0.65, 1.0, 1), frame_step=1.4,
                         frame_avoid=[(-2.7, 2.7)])
    room.dressing = Dr.dress(room, "charging", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
