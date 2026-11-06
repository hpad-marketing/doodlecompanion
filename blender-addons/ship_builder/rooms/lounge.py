"""Oil lounge: the main sitcom set.

Couch against the back wall facing the camera (the big TV sits on the fourth
wall, so its glow lights the cast), a wide space window above the couch, an oil
bar along the left wall, the door and a porthole on the right. Loose props are
physical and settle onto the surfaces they sit on.
"""
import math
from mathutils import Vector

from .. import kit as K
from .. import mats as M
from .. import lighting as Li
from . import common as C
from .. import wear as Wr
from .. import arch as A

INFO = {"label": "Oil lounge", "size": (7.0, 5.5, 3.0)}


def couch(room, x, y, width=3.0, fab=None):
    pal = room.pal
    fab = fab or M.fabric("SB Couch Fabric", (0.12, 0.055, 0.042, 1), 0.35)
    frame = M.brushed_steel("SB Couch Frame", (0.35, 0.35, 0.36, 1), 0.32)
    parts = []
    # steel sled frame
    for sx in (-1, 1):
        K.box("Couch Sled", (0.05, 0.9, 0.05), (x + sx * (width / 2 - 0.15), y, 0.025), frame, room.dress, bevel=0.01)
        K.box("Couch Riser", (0.05, 0.05, 0.22), (x + sx * (width / 2 - 0.15), y - 0.3, 0.13), frame, room.dress, bevel=0.01)
        K.box("Couch Riser", (0.05, 0.05, 0.22), (x + sx * (width / 2 - 0.15), y + 0.3, 0.13), frame, room.dress, bevel=0.01)
    base = K.box("Couch Base", (width, 0.95, 0.2), (x, y, 0.33), pal["hull"], room.dress, bevel=0.02)
    parts.append(base)
    n = 3
    cw = (width - 0.36) / n
    for i in range(n):
        cx = x - (width - 0.36) / 2 + cw * (i + 0.5)
        s = K.rounded("Seat Cushion", (cw - 0.02, 0.78, 0.18), (cx, y - 0.06, 0.52), fab, room.dress, wrinkle=0.028)
        s.rotation_euler = (math.radians(-1.5 + i), 0, math.radians((i - 1) * 0.6))
        b = K.rounded("Back Cushion", (cw - 0.03, 0.2, 0.5), (cx, y + 0.32, 0.82), fab, room.dress, wrinkle=0.03)
        b.rotation_euler = (math.radians(-12 + i * 1.5), 0, 0)
        parts += [s, b]
        # piping along the seat front edge
        K.pipe(room, [(cx - (cw - 0.06) / 2, y - 0.45, 0.6), (cx + (cw - 0.06) / 2, y - 0.45, 0.6)], 0.007, fab, flanges=False, name="Piping")
    for sx in (-1, 1):
        a = K.rounded("Couch Arm", (0.18, 0.95, 0.3), (x + sx * (width / 2 - 0.09), y, 0.58), fab, room.dress, wrinkle=0.018)
        parts.append(a)
    back = K.box("Couch Back Shell", (width, 0.12, 0.6), (x, y + 0.42, 0.72), pal["hull"], room.dress, bevel=0.02)
    parts.append(back)
    # a throw cushion, slightly slumped
    t = K.rounded("Throw Cushion", (0.42, 0.14, 0.4), (x + width / 2 - 0.45, y + 0.12, 0.82), M.fabric("SB Cushion Mustard", (0.42, 0.27, 0.06, 1)), room.dress, wrinkle=0.02)
    t.rotation_euler = (math.radians(-20), math.radians(12), math.radians(-14))
    for p in parts:
        K.rigid(p, passive=True, shape="MESH")
    return parts


def coffee_table(room, x, y, z0=0.0):
    pal = room.pal
    top = K.box("Table Top", (1.3, 0.65, 0.05), (x, y, 0.42 + z0), M.painted_metal("SB Table Top", (0.16, 0.17, 0.17, 1), 0.3), room.dress, bevel=0.012)
    K.rigid(top, passive=True, shape="BOX")
    K.box("Table Lip", (1.34, 0.69, 0.02), (x, y, 0.392 + z0), pal["steel"], room.dress, bevel=0.005)
    for sx in (-1, 1):
        for sy in (-1, 1):
            K.cyl("Table Leg", 0.022, 0.39, (x + sx * 0.56, y + sy * 0.25, 0.195 + z0), pal["steel"], room.dress, verts=20)
            K.cyl("Table Foot", 0.04, 0.012, (x + sx * 0.56, y + sy * 0.25, 0.006 + z0), pal["rubber"], room.dress, verts=20)
    K.box("Table Shelf", (1.18, 0.55, 0.02), (x, y, 0.12 + z0), pal["dark_steel"], room.dress, bevel=0.004)
    return top


def mug(room, loc, mat, name="Mug"):
    m = K.cyl(name, 0.042, 0.095, (loc[0], loc[1], loc[2] + 0.0475), mat, room.props, verts=32, bevel=0.003)
    h = K.box(f"{name} Handle", (0.012, 0.016, 0.06), (loc[0] + 0.05, loc[1], loc[2] + 0.05), mat, room.props, bevel=0.005)
    ob = K.join([m, h], name)
    inner = K.cyl(f"{name} Oil", 0.036, 0.004, (loc[0], loc[1], loc[2] + 0.08), M.liquid("SB Oil", (0.02, 0.012, 0.004, 1)), room.props, verts=32, bevel=0)
    inner.parent = ob
    inner.matrix_parent_inverse = ob.matrix_world.inverted()
    K.rigid(ob, 0.35, friction=0.8)
    return ob


def oil_can(room, loc, colour, name="Oil Can"):
    body = K.cyl(name, 0.033, 0.12, (loc[0], loc[1], loc[2] + 0.06), M.painted_metal(f"SB Can {colour}", colour, 0.35), room.props, verts=32, bevel=0.004)
    top = K.cyl(f"{name} Top", 0.03, 0.006, (loc[0], loc[1], loc[2] + 0.123), room.pal["steel"], room.props, verts=32, bevel=0.002)
    ob = K.join([body, top], name)
    K.rigid(ob, 0.4)
    return ob


def datapad(room, loc, rot=0.0):
    pad = K.box("Datapad", (0.24, 0.17, 0.012), (loc[0], loc[1], loc[2] + 0.006), room.pal["plastic"], room.props, bevel=0.006)
    pad.rotation_euler = (0, 0, rot)
    K.rigid(pad, 0.5, shape="BOX")
    me_scr = K.screen(room, (loc[0], loc[1], loc[2] + 0.0122), (math.cos(rot), math.sin(rot), 0), (-math.sin(rot), math.cos(rot), 0), (0, 0, 1), 0.2, 0.13, (0.95, 0.65, 0.25, 1), "ui", light=False, name="Datapad Screen")
    for o in [o for o in room.dress.objects if o.name.startswith("Datapad Screen")]:
        o.parent = pad
        o.matrix_parent_inverse = pad.matrix_world.inverted()
    return pad


def oil_bar(room):
    pal = room.pal
    W, D = room.W, room.D
    x = -W / 2 + 0.35
    y0, y1 = 1.4, 4.4
    L = y1 - y0
    yc = (y0 + y1) / 2
    body = K.box("Bar Body", (0.55, L, 0.95), (x + 0.02, yc, 0.475), pal["accent"], room.dress, bevel=0.015)
    top = K.box("Bar Top", (0.65, L + 0.08, 0.05), (x + 0.05, yc, 0.975), pal["steel"], room.dress, bevel=0.01)
    K.rigid(top, passive=True, shape="BOX")
    K.box("Bar Kick", (0.5, L, 0.1), (x, yc, 0.05), pal["hull"], room.dress, bevel=0.005)
    # under-counter glow
    K.light_strip(room, (x + 0.33, yc, 0.9), L - 0.1, "Y", (0, 0, -1), (1.0, 0.55, 0.2, 1), 20, role="practical", width=0.025)
    # vertical panel seams on the bar front
    for k in range(1, 4):
        K.box("Bar Seam", (0.006, 0.006, 0.8), (x + 0.3, y0 + L * k / 4, 0.5), M.painted_metal("SB Seam", (0.01, 0.01, 0.01, 1)), room.dress, bevel=0)
    # dispenser tower against the wall
    tower = K.box("Dispenser Tower", (0.3, 1.4, 1.2), (x - 0.12, yc, 1.6), pal["hull"], room.dress, bevel=0.02)
    for k, col in enumerate(((0.05, 0.03, 0.01, 1), (0.25, 0.12, 0.02, 1), (0.08, 0.08, 0.09, 1))):
        yy = yc - 0.45 + k * 0.45
        tank = K.cyl("Oil Tank", 0.11, 0.55, (x + 0.04, yy, 1.75), M.glass("SB Tank Glass", (0.95, 0.9, 0.8, 1), 0.05), room.dress, verts=40)
        K.cyl("Oil Level", 0.1, 0.3 + 0.08 * k, (x + 0.04, yy, 1.5 + (0.3 + 0.08 * k) / 2), M.liquid(f"SB Oil {k}", col), room.dress, verts=40, bevel=0)
        K.cyl("Tank Cap", 0.125, 0.05, (x + 0.04, yy, 2.05), pal["steel"], room.dress, verts=40)
        K.cyl("Tank Base", 0.125, 0.06, (x + 0.04, yy, 1.45), pal["steel"], room.dress, verts=40)
        K.cyl("Nozzle", 0.015, 0.16, (x + 0.15, yy, 1.32), pal["steel"], room.dress, verts=16, rot=(0, math.radians(90), 0))
        K.cyl("Tap", 0.012, 0.08, (x + 0.22, yy, 1.28), pal["dark_steel"], room.dress, verts=16)
        K.point_glow(room, (x + 0.04, yy, 1.47), (1.0, 0.6, 0.25), 3, role="practical")
    K.screen(room, (x - 0.12 + 0.151, yc, 2.35), (0, 1, 0), (0, 0, 1), (1, 0, 0), 0.9, 0.22, (1.0, 0.55, 0.18, 1), "ticker", name="Bar Menu", strength=0.9)
    # stools
    for k in range(3):
        yy = y0 + 0.5 + k * 1.0
        sx = x + 0.75
        with K.piece(room, "Stool", 0.08, 40):
            K.cyl("Stool Seat", 0.19, 0.06, (sx, yy, 0.72), M.fabric("SB Stool Vinyl", (0.06, 0.06, 0.065, 1), 0.2), room.dress, verts=40, bevel=0.02)
            K.cyl("Stool Post", 0.03, 0.66, (sx, yy, 0.36), pal["steel"], room.dress, verts=20)
            K.cyl("Stool Ring", 0.15, 0.02, (sx, yy, 0.3), pal["steel"], room.dress, verts=32)
            K.cyl("Stool Foot", 0.2, 0.025, (sx, yy, 0.0125), pal["dark_steel"], room.dress, verts=40)
    # things on the counter
    for k, y in enumerate((y0 + 0.3, y0 + 0.42, y1 - 0.6)):
        mug(room, (x + 0.08 + 0.03 * k, y, 1.0), M.plastic("SB Mug Cream", (0.62, 0.58, 0.48, 1), 0.3) if k != 1 else M.painted_metal("SB Mug Steel", (0.35, 0.36, 0.37, 1), 0.3), f"Bar Mug {k}")
    oil_can(room, (x + 0.12, y1 - 0.3, 1.0), (0.45, 0.16, 0.06, 1), "Bar Can")
    # cable from tower to the floor trench
    K.cable(room, (x - 0.1, y1 - 0.2, 1.0), (x + 0.1, D - 0.4, 0.02), 0.15, 0.014)


def build(room_name="Oil lounge", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    room = K.Room(room_name, W, D, H)
    pal = room.pal
    win = (2.0, 5.0, 0.75, 2.25)  # along back wall from its left edge
    C.shell(room, back_holes=[win], right_holes=[(3.0, 5.0, 0.0, 2.25)], chamfer=0.55)
    C.window(room, (-W / 2 + 3.5, D, 1.5), 3.0 - 0.244, 1.5 - 0.244, (0, -1, 0))
    K.ceiling(room, light_rows=2, color=(1.0, 0.82, 0.62, 1), power=35, cove=0.28, cove_color=(1.0, 0.62, 0.32, 1), cove_power=5)
    K.stencil(room, "DECK 3 - CREW LOUNGE", (-1.4, D - 0.035, 2.55), (math.radians(90), 0, 0), 0.11)
    K.stencil(room, "AIRLOCK 2 >", (W / 2 - 0.035, 3.4, 2.45), (math.radians(90), 0, math.radians(-90)), 0.09)
    K.stencil(room, "NO OIL PAST THIS LINE", (-W / 2 + 0.035, 4.9, 0.4), (math.radians(90), 0, math.radians(90)), 0.06)
    C.door(room, 1.5)
    # pipe runs along the back/ceiling edge and down the right corner
    zp = H - 0.38
    K.pipe(room, [(-2.7, D - 0.2, H - 0.19), (-2.6, D - 0.2, zp), (2.6, D - 0.2, zp), (2.7, D - 0.2, H - 0.19)], 0.045)
    K.pipe(room, [(-W / 2 + 0.85, D - 0.32, H - 0.18), (W / 2 - 0.85, D - 0.32, H - 0.18)], 0.03, M.painted_metal("SB Pipe Oxide", (0.4, 0.13, 0.05, 1), 0.4))
    for k in range(5):
        K.cable(room, (-2.5 + k * 1.2, D - 0.3, H - 0.3), (-1.9 + k * 1.2, D - 0.3, H - 0.3), 0.18 + 0.05 * (k % 2), 0.01 + 0.004 * (k % 3))
    # couch, rug, table, side pieces
    with K.piece(room, "Couch", 0.06, 3):
        couch(room, 0.3, D - 0.75, 3.0)
    with K.piece(room, "Rug and table", 0.08, 6):  # the table stands on the rug, so they move together
        K.box("Rug", (2.6, 1.7, 0.012), (0.3, D - 2.15, 0.006), M.rug(), room.dress, bevel=0.005)
        coffee_table(room, 0.3, D - 2.05, z0=0.0125)
    with K.piece(room, "Side crate", 0.05, 8):
        side = K.box("Side Crate", (0.5, 0.5, 0.5), (2.25, D - 0.65, 0.25), pal["warm"], room.dress, bevel=0.02)
        K.rigid(side, passive=True, shape="BOX")
        K.box("Crate Stencil Band", (0.505, 0.505, 0.06), (2.25, D - 0.65, 0.4), M.hazard(), room.dress, bevel=0.003)
    # the plant nobody needs, under its own grow light
    plant = K.piece(room, "Plant", 0.05, 15)
    plant.__enter__()
    K.cyl("Plant Pot", 0.17, 0.32, (-1.65, D - 0.55, 0.16), pal["cream"], room.dress, verts=40, bevel=0.01)
    K.cyl("Soil", 0.155, 0.01, (-1.65, D - 0.55, 0.31), M.rubber("SB Soil", (0.05, 0.035, 0.02, 1), 0.95), room.dress, verts=40, bevel=0)
    leaf = M.plastic("SB Leaf", (0.06, 0.18, 0.05, 1), 0.45)
    for k in range(9):
        a = k / 9 * 6.283
        lf = K.rounded("Leaf", (0.06, 0.32, 0.012), (-1.65 + 0.08 * math.cos(a), D - 0.55 + 0.08 * math.sin(a), 0.52 + 0.04 * (k % 3)), leaf, room.dress, soft=1)
        lf.rotation_euler = (math.radians(35 + 10 * (k % 2)), 0, a + math.radians(90))
    K.point_glow(room, (-1.65, D - 0.55, 1.2), (0.85, 0.5, 1.0), 25, 0.05, role="practical")
    plant.__exit__()
    # props on the table: physics settles them
    mug(room, (0.0, D - 2.0, 0.46), M.plastic("SB Mug Cream", (0.62, 0.58, 0.48, 1), 0.3), "Table Mug")
    datapad(room, (0.55, D - 2.1, 0.46), 0.35)
    oil_can(room, (0.75, D - 1.9, 0.46), (0.08, 0.2, 0.21, 1), "Table Can")
    oil_can(room, (2.2, D - 0.6, 0.52), (0.45, 0.16, 0.06, 1), "Crate Can")
    with K.piece(room, "Bar", 0, 0):
        oil_bar(room)
    # the big TV is on the fourth wall: we only see its light on the cast
    L = __import__("bpy").data.lights.new("SB TV", "AREA")
    L.shape = "RECTANGLE"
    L.size, L.size_y = 2.2, 1.2
    L.color = (0.45, 0.7, 1.0)
    L.energy = 220
    import bpy
    lo = bpy.data.objects.new("SB TV Light", L)
    room.lights.objects.link(lo)
    lo.location = (0.3, 0.05, 1.4)
    lo.rotation_euler = (math.radians(-90), 0, 0)
    lo["sb_light"] = "screen"
    lo["sb_energy"] = L.energy
    lo["sb_color"] = list(L.color)
    lo.visible_glossy = False
    # red alert beacons (off unless the mood is red alert)
    for x in (-W / 2 + 1.3, W / 2 - 1.3):
        K.cyl("Alert Beacon", 0.06, 0.1, (x, D - 0.12, H - 0.6), M.emissive("SB Alert Lens", (1.0, 0.08, 0.05, 1), 0.0), room.dress, verts=24, rot=(math.radians(90), 0, 0))
        K.point_glow(room, (x, D - 0.25, H - 0.6), (1.0, 0.1, 0.05), 60, 0.05, role="alert")
    for x in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x, 0.6, 0.25), (1.0, 0.35, 0.1), 12, 0.03, role="emergency")
    C.planet(room, loc=(14, 150, -10), radius=30)
    Li.haze(room, 0.012)
    Li.camera(room, "Wide master", 26, (0.9, -1.0, 1.25), (-0.3, D * 0.7, 1.0), 5.6)
    Li.camera(room, "Couch two-shot", 40, (0.6, 0.9, 1.25), (0.3, D - 0.75, 0.9), 2.8)
    Li.camera(room, "Bar single", 50, (0.6, 2.0, 1.4), (-W / 2 + 0.4, 3.2, 1.3), 2.0)
    room.arch = A.detail(room, seed=wear_seed, accent=(1.0, 0.6, 0.3, 1), frame_avoid=[(-1.6, 1.6)])
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    return room
