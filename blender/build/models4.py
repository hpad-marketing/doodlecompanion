"""Scenery for the 'More worlds' packs (approved 2026-10-30): spooky, adventure, show and
everyday sets, plus the clean backdrops. Same rules as models.py."""
import math
import random

from kit import Piece
from models import model


def sweep_shell(p, prof, width, t=0.02, x=0.0, y=0.0):
    """One seamless piece from a side profile [(y, z)] (floor -> curve -> wall): extruded
    across `width`, `t` thick. One mesh, so no seams get inked between the segments."""
    import math as _m
    back = []
    for i, (py, pz) in enumerate(prof):
        a = prof[max(0, i - 1)]
        b = prof[min(len(prof) - 1, i + 1)]
        dy, dz = b[0] - a[0], b[1] - a[1]
        L = _m.hypot(dy, dz) or 1.0
        back.append((py + dz / L * t, pz - dy / L * t))  # outward: under the floor, behind the wall
    outline = list(prof) + back[::-1]
    p.prism([(py + y, pz) for py, pz in outline], width, x=x, rz=90)
    return p


# ------------------------------------------------------------------ spooky
@model
def dead_tree():
    p = Piece('dead_tree')
    p.cyl(0.14, 1.6, r2=0.08, seg=10)
    for a, l, z in ((40, 0.7, 1.2), (-35, 0.8, 1.4), (70, 0.5, 0.9), (-80, 0.45, 1.0), (10, 0.6, 1.6)):
        r = math.radians(a)
        p.tube([(0, 0, z), (math.sin(r) * l * 0.6, 0, z + math.cos(r) * l * 0.6), (math.sin(r) * l, 0, z + math.cos(r) * l * 0.8)],
               0.035)
    return p


@model
def fog_bank():
    p = Piece('fog_bank')
    rnd = random.Random(4)
    for i in range(9):
        p.sphere(rnd.uniform(0.35, 0.6), -2.4 + i * 0.6, rnd.uniform(-0.2, 0.2), 0.05, sx=1.8, sy=0.6, sz=0.35, seg=12)
    return p


@model
def gravestone():
    p = Piece('gravestone')
    p.prism([(-0.25, 0)] + [(0.25 * math.cos(a), 0.55 + 0.25 * math.sin(a)) for a in
                            [math.pi * i / 10 for i in range(11)]][::-1][::-1] + [(0.25, 0)], 0.1)
    p.box(0.18, 0.01, 0.03, 0, -0.055, 0.5, mat='i')
    p.box(0.03, 0.01, 0.18, 0, -0.055, 0.38, mat='i')
    return p


@model
def cobweb():
    p = Piece('cobweb')
    for a in range(0, 91, 18):
        r = math.radians(a)
        p.tube([(0, 0, 0), (0.6 * math.cos(r), 0, -0.6 * math.sin(r))], 0.004, mat='i')
    for k in (0.2, 0.38, 0.56):
        pts = [(k * math.cos(math.radians(a)), 0, -k * math.sin(math.radians(a))) for a in range(0, 91, 18)]
        p.tube(pts, 0.004, mat='i')
    return p


@model
def creaky_door():
    p = Piece('creaky_door')
    p.box(1.04, 0.08, 0.07, 0, -0.04, 2.02)
    for x in (-0.52, 0.52):
        p.box(0.07, 0.08, 2.02, x, -0.04, 0)
    p.box(0.9, 0.04, 2.0, 0.18, -0.25, 0, rz=-28)  # left ajar
    p.sphere(0.035, 0.52, -0.5, 1.0)
    return p


@model
def hall_frames():
    p = Piece('hall_frames')
    for x, z, w, h in ((-0.9, 1.3, 0.4, 0.55), (-0.2, 1.45, 0.35, 0.45), (0.6, 1.25, 0.5, 0.4)):
        p.box(w, 0.04, h, x, 0, z, rz=0, ry=random.Random(int(x * 10)).uniform(-6, 6))
        p.sphere(0.06, x, -0.03, z + h * 0.6, sy=0.3, seg=10)       # portrait head
        p.cyl(0.1, h * 0.35, x, -0.03, z + 0.03, r2=0.05, rx=0, seg=10)
    return p


@model
def candelabra():
    p = Piece('candelabra')
    p.cyl(0.08, 0.02, seg=12)
    p.cyl(0.015, 0.35, seg=8)
    p.tube([(-0.15, 0, 0.42), (-0.15, 0, 0.33), (0.15, 0, 0.33), (0.15, 0, 0.42)], 0.012)
    for x in (-0.15, 0, 0.15):
        p.cyl(0.018, 0.12, x, 0, 0.42 if x else 0.35, seg=8)
        p.sphere(0.015, x, 0, (0.56 if x else 0.49), sz=1.6, seg=8, mat='i')
    return p


@model
def sheet_ghost_chair():
    p = Piece('sheet_ghost_chair')
    p.box(0.5, 0.5, 0.45, bevel=0.06, seg=2)
    p.box(0.5, 0.12, 0.6, 0, 0.2, 0.45, bevel=0.05, seg=2)
    for x in (-0.25, 0.25):
        p.prism([(x - 0.05, 0), (x + 0.05, 0), (x, -0.06)], 0.5, y=0)
    return p


# ------------------------------------------------------------------ adventure
@model
def moon_dome():
    p = Piece('moon_dome')
    p.lathe([(1.4, 0), (1.35, 0.4), (1.15, 0.8), (0.8, 1.1), (0.4, 1.25), (0, 1.3)], seg=20)
    p.box(0.6, 0.6, 0.9, 0, -1.3, 0, bevel=0.06, seg=2)
    p.cyl(0.18, 0.03, 0, -1.6, 0.55, rx=90, seg=18, mat='i')
    return p


@model
def moon_rocks():
    p = Piece('moon_rocks')
    rnd = random.Random(7)
    for i in range(5):
        p.sphere(rnd.uniform(0.12, 0.3), rnd.uniform(-1.2, 1.2), rnd.uniform(-0.3, 0.3), 0.05, sx=1.3, sz=0.6, seg=10)
    return p


@model
def crater():
    p = Piece('crater')
    p.torus(0.8, 0.12, 0, 0, 0.0, seg=28, seg2=8)
    p.cyl(0.8, 0.005, 0, 0, -0.02, seg=28)
    return p


@model
def flag_pole():
    p = Piece('flag_pole')
    p.cyl(0.02, 1.6, seg=8, mat='i')
    p.box(0.5, 0.01, 0.32, 0.25, 0, 1.25)
    return p


@model
def far_earth():
    p = Piece('far_earth')
    p.cyl(0.3, 0.02, 0, 0, 0.3, rx=90, seg=32)
    p.prism([(-0.15, 0.4), (0.05, 0.48), (0.1, 0.35), (-0.05, 0.25), (-0.18, 0.3)], 0.025)
    return p


@model
def seaweed():
    p = Piece('seaweed')
    for x in (-0.15, 0.0, 0.15):
        p.tube([(x + 0.05 * math.sin(i), 0, i * 0.18) for i in range(8)], 0.03)
    return p


@model
def coral():
    p = Piece('coral')
    p.cyl(0.05, 0.3, seg=8)
    for a in (-40, 0, 40):
        r = math.radians(a)
        p.tube([(0, 0, 0.25), (math.sin(r) * 0.25, 0, 0.5)], 0.035)
        p.sphere(0.05, math.sin(r) * 0.25, 0, 0.52, seg=8)
    return p


@model
def bubbles_column():
    p = Piece('bubbles_column')
    for i in range(7):
        p.sphere(0.03 + 0.01 * (i % 3), 0.05 * math.sin(i * 1.7), 0, i * 0.3, seg=10)
    return p


@model
def fish_school():
    p = Piece('fish_school')
    rnd = random.Random(3)
    for i in range(6):
        x, z = rnd.uniform(-0.8, 0.8), rnd.uniform(-0.3, 0.3)
        p.sphere(0.07, x, 0, z, sx=1.6, sy=0.5, seg=10)
        p.prism([(x - 0.1, z), (x - 0.18, z + 0.06), (x - 0.18, z - 0.06)], 0.02)
    return p


@model
def treasure_sand():
    p = Piece('treasure_sand')
    p.box(0.6, 0.4, 0.35, 0, 0, -0.05, rz=12, ry=-8, bevel=0.02, seg=1)
    p.sphere(0.6, 0, 0, -0.45, sx=1.6, sz=0.6, seg=14)
    return p


@model
def jungle_leaves():
    p = Piece('jungle_leaves')
    for i, a in enumerate(range(-70, 80, 20)):
        r = math.radians(a)
        l = 0.9 + 0.2 * math.sin(i)
        p.sphere(0.16, math.sin(r) * l * 0.55, 0, math.cos(r) * l * 0.7 + 0.3, sx=0.5, sy=0.18, sz=1.6, seg=10)
    p.cyl(0.06, 0.35, seg=8)
    return p


@model
def vines():
    p = Piece('vines')
    for x in (-0.6, -0.1, 0.5):
        p.tube([(x + 0.06 * math.sin(i), 0, -i * 0.22) for i in range(9)], 0.015)
        for i in (2, 4, 6):
            p.sphere(0.04, x + 0.06 * math.sin(i) + 0.05, 0, -i * 0.22, sx=1.3, sy=0.3, seg=8)
    return p


@model
def cactus():
    p = Piece('cactus')
    p.cyl(0.13, 1.3, r2=0.11, seg=12)
    p.sphere(0.11, 0, 0, 1.3, seg=12)
    for x, z, h in ((-0.25, 0.5, 0.45), (0.25, 0.7, 0.35)):
        p.tube([(0, 0, z), (x, 0, z), (x, 0, z + h)], 0.07)
    return p


@model
def dunes():
    p = Piece('dunes')
    for x, s in ((-3, 1.0), (0.5, 1.4), (4, 1.1)):
        p.sphere(1.6 * s, x, 0, -0.9 * s, sx=2.2, sy=0.8, sz=0.8, seg=16)
    return p


@model
def skull_rock():
    p = Piece('skull_rock')
    p.sphere(0.3, 0, 0, 0.2, sx=1.2, sz=0.8, seg=12)
    return p


@model
def snow_peak():
    p = Piece('snow_peak')
    p.prism([(-3.0, 0), (-0.6, 2.4), (0.0, 2.0), (0.8, 2.9), (3.2, 0)], 0.02)
    p.prism([(-0.4, 2.2), (-0.6, 2.4), (-0.75, 2.25)], 0.03)
    p.prism([(0.6, 2.7), (0.8, 2.9), (1.05, 2.6), (0.85, 2.55)], 0.03)
    return p


@model
def snow_drift():
    p = Piece('snow_drift')
    for x in (-1.0, 0.0, 1.1):
        p.sphere(0.6, x, 0, -0.35, sx=1.6, sy=0.8, sz=0.6, seg=14)
    return p


@model
def pine_snow():
    p = Piece('pine_snow')
    p.cyl(0.07, 0.3, seg=8)
    for r, z in ((0.55, 0.3), (0.42, 0.75), (0.3, 1.15)):
        p.cyl(r, 0.55, 0, 0, z, r2=0.03, seg=10)
        p.cyl(r * 0.85, 0.08, 0, 0, z + 0.04, r2=r * 0.7, seg=10)
    return p


@model
def summit_flag():
    p = Piece('summit_flag')
    p.cyl(0.02, 1.1, seg=8, mat='i')
    p.prism([(0.0, 1.1), (0.4, 1.0), (0.0, 0.88)], 0.01)
    p.sphere(0.25, 0, 0, -0.1, sx=1.6, sz=0.5, seg=12)
    return p


# ------------------------------------------------------------------ show sets
@model
def podcast_desk():
    p = Piece('podcast_desk')
    p.box(1.8, 0.7, 0.06, 0, 0, 0.74, bevel=0.02, seg=1)
    p.box(1.7, 0.05, 0.7, 0, 0.3, 0.04)
    for x in (-0.45, 0.45):
        p.cyl(0.06, 0.02, x, -0.1, 0.8, seg=12)
        p.tube([(x, -0.1, 0.82), (x, -0.15, 1.0), (x, -0.3, 1.06)], 0.01, mat='i')
        p.cyl(0.04, 0.13, x, -0.33, 1.02, rx=-30, seg=12)
    return p


@model
def acoustic_panels():
    p = Piece('acoustic_panels')
    for i in range(5):
        for j in range(2):
            p.box(0.5, 0.06, 0.5, -1.1 + i * 0.55, 0, 0.9 + j * 0.55, bevel=0.04, seg=2)
    return p


@model
def on_air_sign():
    p = Piece('on_air_sign')
    p.box(0.6, 0.06, 0.2, bevel=0.03, seg=2)
    p.box(0.5, 0.01, 0.12, 0, -0.035, 0.04)
    return p


@model
def news_desk():
    p = Piece('news_desk')
    p.prism([(-1.3, 0), (1.3, 0), (1.1, 0.78), (-1.1, 0.78)], 0.6)
    p.box(2.4, 0.7, 0.05, 0, 0.0, 0.78, bevel=0.02, seg=1)
    p.box(1.6, 0.01, 0.18, 0, -0.31, 0.3)
    return p


@model
def news_wall():
    p = Piece('news_wall')
    p.box(3.2, 0.06, 1.8, 0, 0, 0.4)
    p.box(1.4, 0.02, 0.8, 0.7, -0.04, 1.0)
    for i in range(4):
        p.box(1.0, 0.02, 0.04, -0.9, -0.04, 1.6 - i * 0.18, mat='i')
    p.cyl(0.3, 0.02, -0.9, -0.04, 0.7, rx=90, seg=28)
    return p


@model
def concert_stage():
    p = Piece('concert_stage')
    p.box(5.0, 3.0, 0.4, 0, 0.6, -0.4)
    p.box(5.0, 0.04, 0.4, 0, -0.9, -0.4)
    for x in (-2.2, 2.2):
        p.box(0.15, 0.15, 3.2, x, 1.9, 0)
    p.box(4.6, 0.15, 0.15, 0, 1.9, 3.1)
    for x in (-1.5, -0.5, 0.5, 1.5):
        p.cyl(0.1, 0.18, x, 1.8, 2.9, rx=160, seg=10)
    return p


@model
def amp_stack():
    p = Piece('amp_stack')
    for z in (0, 0.55):
        p.box(0.7, 0.4, 0.55, 0, 0, z, bevel=0.02, seg=1)
        p.cyl(0.2, 0.01, 0, -0.2, z + 0.27, rx=90, seg=20, mat='i')
    return p


@model
def crowd_heads():
    p = Piece('crowd_heads')
    rnd = random.Random(5)
    for i in range(14):
        x = -3.0 + i * 0.45 + rnd.uniform(-0.1, 0.1)
        z = 0.35 + rnd.uniform(-0.05, 0.08)
        p.sphere(0.16, x, 0, z, seg=12)
        p.sphere(0.22, x, 0, z - 0.3, sx=1.1, sz=0.8, seg=12)
    return p


@model
def game_podium():
    p = Piece('game_podium')
    p.prism([(-0.4, 0), (0.4, 0), (0.32, 1.0), (-0.32, 1.0)], 0.5)
    p.box(0.7, 0.45, 0.05, 0, 0, 1.0, bevel=0.02, seg=1)
    p.cyl(0.08, 0.04, 0, -0.05, 1.05, seg=16, mat='i')
    p.box(0.5, 0.01, 0.25, 0, -0.26, 0.55)
    return p


@model
def big_wheel():
    p = Piece('big_wheel')
    p.cyl(1.0, 0.06, 0, 0, 1.2, rx=90, seg=36)
    for i in range(8):
        a = 2 * math.pi * i / 8
        p.tube([(0, -0.04, 1.2), (math.cos(a), -0.04, 1.2 + math.sin(a))], 0.012, mat='i')
    p.prism([(-0.08, 2.3), (0.08, 2.3), (0, 2.1)], 0.05)
    p.box(0.1, 0.1, 0.2, 0, 0.05, 0)
    return p


@model
def stage_lights():
    p = Piece('stage_lights')
    p.box(4.0, 0.08, 0.08, 0, 0, 0)
    for x in (-1.6, -0.8, 0, 0.8, 1.6):
        p.cyl(0.12, 0.22, x, 0, -0.25, r2=0.16, seg=12)
    return p


@model
def rap_cyc():
    """The curved mustard rap studio from the staging guide: no corners, just a sweep."""
    p = Piece('rap_cyc')
    prof = [(-4.0, 0.0), (0.6, 0.0)] + [(0.6 + 1.6 * math.sin(a), 1.6 - 1.6 * math.cos(a))
                                        for a in [math.pi / 2 * i / 12 for i in range(1, 13)]] + [(2.2, 3.4)]
    return sweep_shell(p, prof, 10.0)


# ------------------------------------------------------------------ everyday extras
@model
def car_interior():
    p = Piece('car_interior')
    p.box(2.2, 0.4, 0.5, 0, 1.0, 0.45, bevel=0.06, seg=2)          # dashboard
    p.torus(0.2, 0.025, 0.55, 0.75, 0.95, rx=70, seg=24, seg2=6, mat='i')
    p.box(2.2, 0.05, 0.9, 0, 1.25, 0.95, rx=-25)                       # windscreen frame
    p.box(2.0, 0.02, 0.75, 0, 1.22, 1.0, rx=-25)
    for x in (-0.55, 0.55):
        p.box(0.6, 0.55, 0.15, x, -0.2, 0.3, bevel=0.05, seg=2)
        p.box(0.6, 0.15, 0.7, x, -0.5, 0.4, bevel=0.05, seg=2, rx=-10)
    p.box(0.5, 0.04, 0.12, 0, 0.9, 1.45)                               # mirror
    return p


@model
def bus_interior():
    p = Piece('bus_interior')
    for y in (0.0, 0.9, 1.8):
        for x in (-1.0, 1.0):
            p.box(0.8, 0.45, 0.12, x, y, 0.42, bevel=0.04, seg=2)
            p.box(0.8, 0.1, 0.55, x, y + 0.22, 0.5, bevel=0.04, seg=2)
            p.box(0.06, 0.06, 0.42, x, y, 0)
    p.cyl(0.02, 2.4, -0.45, -0.5, 0, seg=8, mat='i')
    p.cyl(0.02, 2.4, 0.45, 1.3, 0, seg=8, mat='i')
    p.cyl(0.02, 3.2, -0.45, -0.4, 2.1, rx=-90, seg=8, mat='i')
    for y in (0.0, 0.7, 1.4):
        p.torus(0.06, 0.01, -0.45, y, 1.95, ry=90, seg=12, seg2=4, mat='i')
    return p


@model
def lift_walls():
    p = Piece('lift_walls')
    p.box(0.3, 0.1, 0.5, 0.95, 0.9, 1.0, bevel=0.02, seg=1)
    for i in range(6):
        p.cyl(0.03, 0.01, 0.9 + 0.1 * (i % 2), 0.84, 1.08 + 0.12 * (i // 2), rx=90, seg=10, mat='i')
    p.box(1.8, 0.04, 0.04, 0, 0.9, 0.95)
    p.box(0.5, 0.02, 0.16, 0, 0.9, 2.1)
    return p


@model
def hospital_bed():
    p = Piece('hospital_bed')
    p.box(0.95, 2.0, 0.12, 0, 0, 0.55, bevel=0.03, seg=1)
    p.box(0.9, 0.5, 0.15, 0, 0.7, 0.7, rx=20, bevel=0.05, seg=2)
    for x in (-0.48, 0.48):
        p.tube([(x, -0.6, 0.6), (x, -0.6, 0.85), (x, 0.4, 0.85), (x, 0.4, 0.6)], 0.012, mat='i')
    for x, y in ((-0.4, -0.9), (0.4, -0.9), (-0.4, 0.9), (0.4, 0.9)):
        p.cyl(0.02, 0.5, x, y, 0.05, seg=6)
        p.sphere(0.04, x, y, 0.04, seg=8, mat='i')
    p.box(0.9, 0.05, 0.4, 0, -1.0, 0.6)
    return p


@model
def iv_stand():
    p = Piece('iv_stand')
    p.cyl(0.18, 0.03, seg=5)
    p.cyl(0.012, 1.8, seg=8, mat='i')
    p.tube([(-0.12, 0, 1.75), (0.12, 0, 1.75)], 0.01, mat='i')
    p.box(0.1, 0.03, 0.18, 0.1, 0, 1.52, bevel=0.03, seg=2)
    p.tube([(0.1, 0, 1.52), (0.12, 0, 1.0), (0.2, 0, 0.8)], 0.004, mat='i')
    return p


@model
def heart_monitor():
    p = Piece('heart_monitor')
    p.box(0.4, 0.25, 0.3, 0, 0, 1.0, bevel=0.02, seg=1)
    p.tube([(-0.15, -0.13, 1.15), (-0.06, -0.13, 1.15), (-0.03, -0.13, 1.23), (0.0, -0.13, 1.08), (0.03, -0.13, 1.15),
            (0.15, -0.13, 1.15)], 0.006, mat='i')
    p.cyl(0.02, 1.0, seg=6)
    p.cyl(0.15, 0.03, seg=8)
    return p


@model
def library_stacks():
    p = Piece('library_stacks')
    rnd = random.Random(9)
    p.box(2.4, 0.4, 2.2, bevel=0.01, seg=1)
    for z in (0.05, 0.6, 1.15, 1.7):
        p.box(2.3, 0.36, 0.03, 0, -0.03, z + 0.45)
        x = -1.1
        while x < 1.05:
            w = rnd.uniform(0.04, 0.09)
            h = rnd.uniform(0.3, 0.42)
            p.box(w, 0.28, h, x + w / 2, -0.06, z + 0.02, ry=rnd.choice((0, 0, 0, 8)))
            x += w + 0.01
    return p


@model
def reading_table():
    p = Piece('reading_table')
    p.box(1.4, 0.7, 0.05, 0, 0, 0.74, bevel=0.01, seg=1)
    for x in (-0.62, 0.62):
        p.box(0.06, 0.6, 0.74, x, 0, 0)
    p.cyl(0.08, 0.03, -0.4, 0.15, 0.79, seg=12)
    p.tube([(-0.4, 0.15, 0.8), (-0.4, 0.15, 1.05), (-0.3, 0.1, 1.1)], 0.01, mat='i')
    p.cyl(0.07, 0.08, -0.28, 0.08, 1.02, r2=0.04, rx=30, seg=12)
    p.box(0.3, 0.22, 0.03, 0.2, -0.05, 0.79, rz=12)
    return p


@model
def cinema_seats():
    p = Piece('cinema_seats')
    for r, (y, z) in enumerate(((0, 0), (0.9, 0.25), (1.8, 0.5))):
        p.box(4.4, 0.8, z + 0.01, 0, y, 0) if z else None
        for i in range(6):
            x = -2.0 + i * 0.8
            p.box(0.62, 0.5, 0.12, x, y, z + 0.4, bevel=0.04, seg=2)
            p.box(0.62, 0.12, 0.6, x, y + 0.28, z + 0.45, bevel=0.05, seg=2, rx=-10)
            p.box(0.08, 0.5, 0.25, x + 0.35, y, z + 0.4)
    return p


@model
def popcorn_tub():
    p = Piece('popcorn_tub')
    p.cyl(0.08, 0.18, r2=0.1, seg=12)
    for i in range(6):
        p.box(0.025, 0.002, 0.18, 0.09 * math.cos(i * math.pi / 3), 0.09 * math.sin(i * math.pi / 3), 0.0,
              rz=math.degrees(i * math.pi / 3) + 90, mat='i')
    for i in range(7):
        a = i * 0.9
        p.sphere(0.035, 0.05 * math.cos(a), 0.05 * math.sin(a), 0.2 + 0.015 * (i % 2), seg=8)
    return p


@model
def rooftop_tank():
    p = Piece('rooftop_tank')
    p.cyl(0.6, 1.1, 0, 0, 0.6, seg=16)
    p.cyl(0.62, 0.06, 0, 0, 1.7, r2=0.1, seg=16)
    for x, y in ((-0.4, -0.4), (0.4, -0.4), (-0.4, 0.4), (0.4, 0.4)):
        p.box(0.06, 0.06, 0.6, x, y, 0)
    return p


@model
def antenna():
    p = Piece('antenna')
    p.cyl(0.02, 1.6, seg=8, mat='i')
    for z, w in ((1.2, 0.8), (1.4, 0.6), (1.55, 0.4)):
        p.box(w, 0.02, 0.02, 0, 0, z, mat='i')
    return p


@model
def string_lights_roof():
    p = Piece('string_lights_roof')
    path = [(x * 0.3 - 2.4, 0, 2.2 - 0.3 * math.sin(x * math.pi / 16)) for x in range(17)]
    p.tube(path, 0.006, mat='i')
    for x, y, z in path[1:-1:2]:
        p.sphere(0.04, x, 0, z - 0.05, sz=1.3, seg=8)
    for x in (-2.4, 2.4):
        p.cyl(0.03, 2.2, x, 0, 0, seg=8)
    return p


# ------------------------------------------------------------------ clean backdrops
@model
def cyc_sweep():
    p = Piece('cyc_sweep')
    prof = [(-4.0, 0.0), (0.4, 0.0)] + [(0.4 + 1.2 * math.sin(a), 1.2 - 1.2 * math.cos(a))
                                        for a in [math.pi / 2 * i / 12 for i in range(1, 13)]] + [(1.6, 3.4)]
    return sweep_shell(p, prof, 12.0)


@model
def corner_walls():
    p = Piece('corner_walls')
    p.box(3.0, 0.05, 2.6, 0.3, 1.6, 0)
    p.box(0.05, 2.6, 2.6, -1.2, 0.3, 0)
    return p
