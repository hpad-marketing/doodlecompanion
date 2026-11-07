"""Observation deck: the ship's big window.

A five-metre armoured window across the back wall, a 12 cm viewing step in front
of it with a hazard edge, an old brass-and-steel telescope on a tripod on the
step, two benches facing the glass and a round holo star table by the right
door. Quiet, cool light so the view outside does the work.

Use points: sit on either bench, step up and look through the telescope, work
the star table.
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

INFO = {"label": "Observation deck", "size": (7.0, 5.6, 3.4), "doors": {"left": 1.5, "right": 1.5}}

STEP_H = 0.12
STEP_D = 1.1
BENCH_Y = 3.25
BENCH_X = 1.2
BENCH_L = 1.5
SEAT_Z = 0.46
TABLE = (2.75, 3.45, 0.4)


def step(room):
    W, D = room.W, room.D
    plate = M.deck_plate("SB Step Plate", (0.06, 0.063, 0.066, 1), 0.8)
    y = D - 0.09 - STEP_D / 2
    s = K.box("Viewing Step", (5.6, STEP_D, STEP_H), (0, y, STEP_H / 2), plate, room.dress, bevel=0.006)
    s["sb_surface"] = "metal"
    K.box("Step Edge Stripe", (5.56, 0.003, STEP_H - 0.03), (0, y - STEP_D / 2 - 0.0016, STEP_H / 2), M.hazard(), room.dress, bevel=0, segs=1)
    glow = M.emissive("SB Step Glow", (0.4, 0.7, 1.0, 1), 2.5)
    K.box("Step Nose Light", (5.5, 0.012, 0.004), (0, y - STEP_D / 2 + 0.03, STEP_H + 0.002), glow, room.dress, bevel=0, segs=1)
    return y - STEP_D / 2


def telescope(room, x, y):
    pal = room.pal
    z0 = STEP_H
    brass = M.painted_metal("SB Old Brass", (0.42, 0.3, 0.12, 1), 0.35)
    head = Vector((x, y, z0 + 1.12))
    for k in range(3):
        a = math.radians(90 + k * 120)
        foot = Vector((x + 0.38 * math.cos(a), y + 0.38 * math.sin(a), z0 + 0.012))
        d = head - Vector((0, 0, 0.06)) - foot
        K.box("Tripod Leg", (0.03, 0.03, d.length), (foot + head - Vector((0, 0, 0.06))) / 2, pal["dark_steel"], room.dress,
              bevel=0.006, rot=Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler())
        K.cyl("Tripod Foot", 0.03, 0.024, foot, pal["rubber"], room.dress, verts=16, bevel=0.004)
    K.cyl("Tripod Head", 0.06, 0.08, head, pal["dark_steel"], room.dress, verts=24, bevel=0.01)
    # the tube leans up and back towards the glass
    tilt = math.radians(62)
    axis = Vector((0, math.sin(tilt), math.cos(tilt)))
    c = head + Vector((0, 0, 0.1)) + axis * 0.12
    rot = Vector((0, 0, 1)).rotation_difference(axis).to_euler()
    K.cyl("Telescope Tube", 0.075, 0.95, c, brass, room.dress, verts=32, rot=rot, bevel=0.006)
    K.cyl("Telescope Dew Cap", 0.09, 0.2, c + axis * 0.5, pal["hull"], room.dress, verts=32, rot=rot, bevel=0.006)
    K.cyl("Telescope Lens", 0.07, 0.004, c + axis * 0.6, pal["glass"], room.dress, verts=32, rot=rot, bevel=0.001)
    K.cyl("Telescope Eyepiece", 0.022, 0.12, c - axis * 0.5, pal["plastic"], room.dress, verts=16, rot=rot, bevel=0.004)
    K.cyl("Finder Scope", 0.02, 0.3, c + Vector((0.09, 0, 0)), pal["dark_steel"], room.dress, verts=16, rot=rot, bevel=0.003)
    K.box("Finder Bracket", (0.08, 0.03, 0.03), c + Vector((0.05, 0, 0)), pal["dark_steel"], room.dress, bevel=0.004, rot=rot)
    return c - axis * 0.56


def bench(room, x):
    pal = room.pal
    seat = M.fabric("SB Bench Cushion", (0.12, 0.16, 0.2, 1))
    y = BENCH_Y
    for sx in (-1, 1):
        K.box("Bench Leg", (0.06, 0.42, SEAT_Z - 0.05), (x + sx * (BENCH_L / 2 - 0.12), y, (SEAT_Z - 0.05) / 2), pal["dark_steel"], room.dress, bevel=0.008)
        K.box("Bench Foot", (0.1, 0.46, 0.015), (x + sx * (BENCH_L / 2 - 0.12), y, 0.0075), pal["rubber"], room.dress, bevel=0.003)
    K.box("Bench Rail", (BENCH_L - 0.3, 0.04, 0.04), (x, y, 0.12), pal["dark_steel"], room.dress, bevel=0.006)
    K.box("Bench Frame", (BENCH_L, 0.5, 0.05), (x, y, SEAT_Z - 0.025), pal["hull"], room.dress, bevel=0.01)
    c = K.rounded("Bench Cushion", (BENCH_L - 0.06, 0.46, 0.07), (x, y, SEAT_Z + 0.035), seat, room.dress, soft=2, wrinkle=0.004)
    c["sb_surface"] = "fabric"
    return C.use_point(room, f"Bench {'left' if x < 0 else 'right'}", (x, y, SEAT_Z + 0.07), math.radians(180), "sit",
                       approach=(x, y - 0.75, 0.0), contact="seat -> cushion", who="walker")


def star_table(room):
    x, y, r = TABLE
    pal = room.pal
    K.cyl("Star Table Base", r * 0.55, 0.04, (x, y, 0.02), pal["dark_steel"], room.dress, verts=40, bevel=0.008)
    K.cyl("Star Table Column", 0.09, 0.78, (x, y, 0.04 + 0.39), pal["hull"], room.dress, verts=24, bevel=0.008)
    K.cyl("Star Table Top", r, 0.06, (x, y, 0.85), pal["hull"], room.dress, verts=48, bevel=0.012)
    disc = M.emissive("SB Star Disc", (0.35, 0.65, 1.0, 1), 1.6)
    K.cyl("Star Table Glass", r - 0.05, 0.004, (x, y, 0.882), disc, room.dress, verts=48, bevel=0)
    # the hologram: thin glowing rings standing above the table (not solid, no collision)
    holo = M.emissive("SB Holo", (0.4, 0.75, 1.0, 1), 1.2)
    for k, (rr, z) in enumerate(((0.22, 1.05), (0.16, 1.18), (0.08, 1.26))):
        h = K.cyl("Holo Ring", rr, 0.003, (x, y, z), holo, room.dress, verts=48, bevel=0, rot=(math.radians(12 * k), 0, 0))
        h.visible_shadow = False
        h["sb_decal"] = True
    K.point_glow(room, (x, y, 1.15), (0.4, 0.75, 1.0), 12, 0.04, role="practical")
    return C.use_point(room, "Star table", (x, y - r - 0.42, 0.0), math.radians(180), "use_console",
                       approach=(x - 0.3, y - r - 1.1, 0.0), contact="hand -> table glass", who="walker")


def build(room_name="Observation deck", wear=1.0, wear_seed=1):
    W, D, H = INFO["size"]
    room = K.Room(room_name, W, D, H)
    dr = INFO["doors"]
    win = (1.0, 6.0, 0.7, 2.95)
    C.shell(room, back_holes=[win], left_holes=[C.door_hole(room, dr["left"], "left")],
            right_holes=[C.door_hole(room, dr["right"], "right")], panel=(1.0, 0.75), chamfer=0.5)
    C.window(room, (0.0, D, (win[2] + win[3]) / 2), 5.0 - 0.244, (win[3] - win[2]) - 0.244, (0, -1, 0), frame=0.12, name="Big Window", tilt=-5)
    K.ceiling(room, light_rows=2, color=(0.75, 0.85, 1.0, 1), power=14, cols=2, cove=0.28, cove_color=(0.35, 0.6, 1.0, 1), cove_power=4)
    C.door(room, dr["left"], side="left")
    C.door(room, dr["right"], side="right")
    with K.piece(room, "Viewing step", 0.0, 0):
        front = step(room)
    with K.piece(room, "Telescope", 0.02, 6):
        eye = telescope(room, 1.9, D - 0.62)
    room.uses = []
    for sx in (-1, 1):
        with K.piece(room, "Bench", 0.04, 3):
            room.uses.append(bench(room, sx * BENCH_X))
    with K.piece(room, "Star table", 0.02, 0):
        room.uses.append(star_table(room))
    room.uses += [
        C.use_point(room, "Step up to the window", (0.0, front + 0.35, STEP_H), math.radians(180), "step_up",
                    approach=(0.0, front - 0.5, 0.0), who="walker", step=STEP_H),
        C.use_point(room, "Telescope", (1.9, eye.y - 0.32, STEP_H), math.radians(180), "look_through",
                    approach=(1.9, front - 0.5, 0.0), contact="eye -> eyepiece", who="walker", step=STEP_H),
    ]
    K.stencil(room, "OBSERVATION - QUIET PLEASE", (0.0, D - 0.035, 0.42), (math.radians(90), 0, 0), 0.07)
    for x0 in (-W / 2 + 0.3, W / 2 - 0.3):
        K.point_glow(room, (x0, 0.35, 0.25), (1.0, 0.35, 0.1), 6, 0.03, role="emergency")
    C.planet(room, loc=(18, 150, 14), radius=40, color=(0.32, 0.42, 0.6, 1), ring=True)
    Li.haze(room, 0.01)
    Li.camera(room, "Wide master", 22, (0.0, -1.3, 1.45), (0.0, D * 0.7, 1.4), 5.0)
    Li.camera(room, "Window two-shot", 32, (-1.4, 1.6, 1.25), (0.6, D - 0.6, 1.45), 3.0)
    room.arch = A.detail(room, seed=wear_seed, density=0.6, accent=(0.35, 0.6, 1.0, 1), frame_step=1.6,
                         frame_avoid=[(-2.75, 2.75)], walkway=(-2.4, 2.4, 0.5, 2.5))
    room.dressing = Dr.dress(room, "observation", seed=wear_seed)
    if wear:
        room.wear = Wr.apply(room, seed=wear_seed, amount=wear)
    room.surfaces = Sf.tag_room(room)
    return room
