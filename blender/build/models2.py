"""Scenery for the second batch of locations (open-sky outdoors, everyday India, more rooms).

Same rules as models.py: metres, z up, front faces -y, chunky shapes so one stroke weight
reads. Models named far_* are distance cards: drawn at the size they should LOOK from the
default camera, then scaled up with distance by build_sets.py (like the clouds), so a
mountain range 80 m away costs a handful of faces.
"""
import math

from kit import Piece
from models import model


def _ring(n, r, z=0.0, phase=0.0):
    return [(r * math.cos(phase + 2 * math.pi * i / n), r * math.sin(phase + 2 * math.pi * i / n), z) for i in range(n)]


# ------------------------------------------------------------------ distance cards
@model
def far_hills():
    p = Piece('far_hills')
    pts = [(-3.2, 0)] + [(x / 10.0, 0.35 + 0.22 * math.sin(x / 7.0) + 0.12 * math.sin(x / 3.1)) for x in range(-32, 33, 2)] + [(3.2, 0)]
    p.prism(pts, 0.02)
    return p


@model
def far_mountains():
    p = Piece('far_mountains')
    p.prism([(-3.4, 0), (-2.6, 0.9), (-2.1, 0.55), (-1.3, 1.35), (-0.6, 0.7), (0.2, 1.1), (0.9, 0.5), (1.7, 1.25),
             (2.5, 0.6), (3.4, 0)], 0.02)
    p.prism([(-1.55, 1.08), (-1.3, 1.35), (-1.05, 1.08), (-1.2, 1.12), (-1.3, 1.02), (-1.42, 1.12)], 0.03)  # snow cap
    return p


@model
def far_city():
    p = Piece('far_city')
    x = -3.0
    import random
    rnd = random.Random(7)
    while x < 3.0:
        w = rnd.uniform(0.18, 0.4)
        h = rnd.uniform(0.3, 0.9)
        p.box(w, 0.02, h, x + w / 2, 0, 0)
        x += w + rnd.uniform(0.0, 0.06)
    return p


@model
def far_treeline():
    p = Piece('far_treeline')
    pts = [(-3.2, 0)]
    for i in range(33):
        x = -3.2 + i * 0.2
        pts += [(x + 0.05, 0.28 + 0.06 * math.sin(i * 1.7)), (x + 0.1, 0.42 + 0.08 * math.sin(i * 2.3)), (x + 0.15, 0.3)]
    pts.append((3.2, 0))
    p.prism(pts, 0.02)
    return p


@model
def far_island():
    p = Piece('far_island')
    p.prism([(-0.9, 0), (-0.6, 0.12), (-0.2, 0.18), (0.3, 0.14), (0.8, 0)], 0.02)
    p.tube([(0.0, 0, 0.16), (0.05, 0, 0.42)], 0.012)
    for a in (-60, -20, 20, 60):
        r = math.radians(a)
        p.tube([(0.05, 0, 0.42), (0.05 + 0.16 * math.sin(r), 0, 0.42 - 0.06 + 0.06 * math.cos(r))], 0.01)
    return p


@model
def far_volcano():
    p = Piece('far_volcano')
    p.prism([(-1.6, 0), (-0.35, 1.0), (-0.15, 0.94), (0.0, 1.0), (0.15, 0.94), (0.35, 1.0), (1.6, 0)], 0.02)
    for i, (x, z, r) in enumerate(((0.0, 1.15, 0.13), (0.12, 1.35, 0.17), (-0.05, 1.6, 0.21))):
        p.sphere(r, x, 0, z, sy=0.15, seg=12)  # smoke puffs
    return p


@model
def far_dino():
    p = Piece('far_dino')
    p.prism([(-0.9, 0.55), (-0.55, 0.5), (-0.3, 0.42), (0.0, 0.45), (0.25, 0.42), (0.35, 0.0), (0.42, 0.0), (0.45, 0.34),
             (0.6, 0.6), (0.68, 1.2), (0.72, 1.32), (0.9, 1.34), (0.92, 1.26), (0.8, 1.22), (0.78, 0.95), (0.7, 0.55),
             (0.6, 0.35), (0.55, 0.0), (0.62, 0.0), (0.68, 0.3), (0.5, 0.25), (0.05, 0.3), (-0.05, 0.0), (0.02, 0.0),
             (-0.1, 0.32), (-0.5, 0.4)], 0.02)
    return p


@model
def far_stands():
    p = Piece('far_stands')
    p.prism([(-3.2, 0), (-3.2, 0.35), (-2.0, 0.6), (2.0, 0.6), (3.2, 0.35), (3.2, 0)], 0.02)
    for x in (-2.4, 2.4):
        p.box(0.03, 0.02, 0.6, x, 0, 0.6)
        p.box(0.22, 0.03, 0.12, x, 0, 1.2)  # floodlights
    return p


@model
def far_crane():
    p = Piece('far_crane')
    p.box(0.06, 0.02, 1.4, 0, 0, 0)
    p.box(1.3, 0.02, 0.05, 0.35, 0, 1.4)
    p.box(0.14, 0.03, 0.12, -0.25, 0, 1.3)
    p.tube([(0.9, 0, 1.4), (0.9, 0, 1.0)], 0.006)
    p.box(0.08, 0.02, 0.06, 0.9, 0, 0.95)
    return p


@model
def far_ferris_wheel():
    p = Piece('far_ferris_wheel')
    p.torus(0.6, 0.012, 0, 0, 0.75, rx=90, seg=40, seg2=6)
    for i in range(8):
        a = 2 * math.pi * i / 8
        x, z = 0.6 * math.cos(a), 0.75 + 0.6 * math.sin(a)
        p.tube([(0, 0, 0.75), (x, 0, z)], 0.006)
        p.box(0.08, 0.02, 0.07, x, 0, z - 0.08)
    p.tube([(-0.25, 0, 0), (0, 0, 0.75), (0.25, 0, 0)], 0.012)
    return p


@model
def birds():
    p = Piece('birds')
    for x, z, s in ((0, 0, 1.0), (0.35, 0.12, 0.8), (-0.3, 0.18, 0.7)):
        p.tube([(x - 0.08 * s, 0, z + 0.03 * s), (x - 0.03 * s, 0, z + 0.04 * s), (x, 0, z)], 0.006)
        p.tube([(x, 0, z), (x + 0.03 * s, 0, z + 0.04 * s), (x + 0.08 * s, 0, z + 0.03 * s)], 0.006)
    return p


@model
def sun():
    p = Piece('sun')
    p.cyl(0.25, 0.02, 0, 0, 0, rx=90, seg=32)
    return p


@model
def starfield():
    """A spray of small stars on a far shell (one mesh, cheap)."""
    import random
    rnd = random.Random(3)
    p = Piece('starfield')
    for _ in range(110):
        x, z = rnd.uniform(-4.5, 4.5), rnd.uniform(-1.0, 4.0)
        r = rnd.uniform(0.012, 0.03)
        p.prism([(x - r, z), (x, z + r * 2.4), (x + r, z), (x, z - r * 2.4)], 0.01)
    return p


@model
def ringed_planet():
    p = Piece('ringed_planet')
    p.sphere(0.5, 0, 0, 0.5, seg=24)
    p.torus(0.78, 0.035, 0, 0, 0.5, rx=72, ry=-18, seg=48, seg2=6)
    return p


@model
def comet():
    p = Piece('comet')
    p.sphere(0.06, 0, 0, 0)
    for k, (dz, ln) in enumerate(((0.0, 0.6), (0.04, 0.45), (-0.04, 0.4))):
        p.tube([(0.05, 0, dz * 0.5), (0.05 + ln, 0, dz + 0.12 * ln)], 0.01)
    return p


@model
def floating_rock():
    p = Piece('floating_rock')
    p.sphere(0.28, 0, 0, 0.2, sx=1.3, sy=1.0, sz=0.55, seg=12)
    p.sphere(0.1, 0.42, 0.1, 0.38, sx=1.2, sz=0.7, seg=12)
    return p


# ------------------------------------------------------------------ open-sky pieces
@model
def big_hill():
    p = Piece('big_hill')
    p.lathe([(0, 1.3), (1.2, 1.2), (2.4, 0.95), (3.6, 0.55), (4.6, 0.2), (5.4, 0.0)], seg=40)
    return p


@model
def tree_swing():
    p = Piece('tree_swing')
    p.cyl(0.16, 1.5, 0, 0, 0, r2=0.1, seg=16)
    p.tube([(0, 0, 1.2), (0.7, 0, 1.55)], 0.05)
    for x, y, z, r in ((0, 0, 2.0, 0.7), (-0.55, 0.05, 1.75, 0.5), (0.6, -0.05, 1.75, 0.55), (0.25, 0.15, 2.45, 0.5),
                       (-0.3, -0.1, 2.35, 0.45)):
        p.sphere(r, x, y, z, seg=20)
    for dx in (-0.1, 0.1):
        p.tube([(0.62 + dx, 0, 1.5), (0.62 + dx, 0, 0.45)], 0.008, mat='i')
    p.box(0.32, 0.12, 0.03, 0.62, 0, 0.43, bevel=0.01, seg=2)
    return p


@model
def falling_leaves():
    import random
    rnd = random.Random(11)
    p = Piece('falling_leaves')
    for _ in range(9):
        x, y, z = rnd.uniform(-1.2, 1.2), rnd.uniform(-0.3, 0.3), rnd.uniform(0.2, 1.6)
        p.sphere(0.04, x, y, z, sx=1.0, sy=0.25, sz=0.55, seg=8)
    return p


@model
def railing():
    p = Piece('railing')
    for i in range(9):
        p.box(0.05, 0.05, 0.85, -2.0 + i * 0.5, 0, 0, bevel=0.01, seg=2)
    p.box(4.1, 0.07, 0.06, 0, 0, 0.85, bevel=0.02, seg=2)
    p.box(4.1, 0.04, 0.04, 0, 0, 0.45)
    return p


@model
def jetty():
    p = Piece('jetty')
    for i in range(12):
        p.box(1.1, 0.34, 0.05, 0, -1.8 + i * 0.38, -0.05, bevel=0.01, seg=1)
    for y in (-1.8, -0.2, 1.4, 2.4):
        for x in (-0.5, 0.5):
            p.cyl(0.05, 0.75, x, y, -0.7)
    p.cyl(0.06, 0.3, 0.5, 2.4, 0.0)  # mooring post
    return p


@model
def rowboat():
    p = Piece('rowboat')
    p.lathe([(0, 0), (0.25, 0.02), (0.38, 0.12), (0.42, 0.22), (0.4, 0.24)], seg=24)
    p.box(0.7, 0.1, 0.03, 0, 0, 0.16, bevel=0.01, seg=1)
    p.tube([(-0.2, -0.1, 0.22), (-0.55, -0.25, 0.05)], 0.012)
    return p


@model
def reeds():
    p = Piece('reeds')
    for i, (x, h, lean) in enumerate(((-0.12, 0.6, -0.05), (-0.05, 0.75, 0.0), (0.04, 0.68, 0.06), (0.12, 0.55, 0.1))):
        p.tube([(x, 0, -0.2), (x + lean, 0, h)], 0.008)
        p.cyl(0.018, 0.12, x + lean, 0, h - 0.18, seg=8, mat='i')
    return p


@model
def fishing_rod():
    p = Piece('fishing_rod')
    p.tube([(0, 0, 0.02), (1.1, 0.0, 0.3)], 0.012)
    p.cyl(0.035, 0.03, 0.12, 0, 0.0, rx=90)
    return p


@model
def ripples():
    p = Piece('ripples')
    for R, x in ((0.25, 0), (0.4, 0), (0.18, 0.9)):
        p.torus(R, 0.006, x, 0, 0.0, seg=32, seg2=4)
    return p


@model
def road_strip():
    p = Piece('road_strip')
    p.box(2.4, 260, 0.008, 0, 126, 0)
    for i in range(70):
        y = -3.0 + i * 3.6
        p.box(0.1, 1.4, 0.004, 0, y, 0.008)
    return p


@model
def signpost():
    p = Piece('signpost')
    p.cyl(0.035, 1.6, 0, 0, 0, seg=12)
    p.prism([(0, 1.35), (0.55, 1.35), (0.65, 1.45), (0.55, 1.55), (0, 1.55)], 0.03)
    p.prism([(0, 1.05), (-0.5, 1.05), (-0.6, 1.15), (-0.5, 1.25), (0, 1.25)], 0.03)
    return p


@model
def power_pole():
    p = Piece('power_pole')
    p.cyl(0.06, 3.2, 0, 0, 0, r2=0.045, seg=12)
    p.box(0.9, 0.06, 0.06, 0, 0, 2.9)
    for x in (-0.35, 0.0, 0.35):
        p.cyl(0.025, 0.08, x, 0, 2.96, seg=8, mat='i')
    return p


@model
def tent():
    p = Piece('tent')
    p.prism([(-0.75, 0), (0, 1.0), (0.75, 0)], 1.5, rz=90)
    p.prism([(-0.22, 0), (0, 0.55), (0.22, 0)], 0.02, y=-0.76, mat='i', rz=0)
    return p


@model
def campfire():
    p = Piece('campfire')
    for a in (0, 60, 120):
        p.cyl(0.05, 0.55, -0.27 * math.cos(math.radians(a)), -0.27 * math.sin(math.radians(a)), 0.05, rx=90, rz=a, seg=10)
    for i in range(7):
        a = 2 * math.pi * i / 7
        p.sphere(0.07, 0.32 * math.cos(a), 0.32 * math.sin(a), 0.04, sz=0.7, seg=10)
    p.prism([(-0.14, 0.08), (-0.08, 0.32), (-0.02, 0.22), (0.03, 0.46), (0.09, 0.26), (0.14, 0.08)], 0.06)
    return p


@model
def log_seat():
    p = Piece('log_seat')
    p.cyl(0.16, 0.9, 0, 0, 0.16, rx=90, rz=90, seg=20)
    return p


@model
def camp_lantern():
    p = Piece('camp_lantern')
    p.cyl(0.07, 0.03, 0, 0, 0, seg=16)
    p.cyl(0.055, 0.14, 0, 0, 0.03, seg=16)
    p.cyl(0.075, 0.04, 0, 0, 0.17, r2=0.03, seg=16)
    p.torus(0.04, 0.006, 0, 0, 0.24, rx=90, seg=16, seg2=4)
    return p


@model
def sailboat():
    p = Piece('sailboat')
    p.prism([(-1.3, 0), (1.3, 0), (1.0, -0.45), (-0.9, -0.45)], 0.9)  # hull, deck at z 0
    p.box(2.4, 0.8, 0.02, 0, 0, 0)
    p.cyl(0.035, 2.3, 0.2, 0.1, 0)
    p.prism([(0.25, 0.3), (0.25, 2.2), (1.15, 0.35)], 0.01, y=0.1)
    p.prism([(0.15, 0.4), (0.15, 1.8), (-0.6, 0.4)], 0.01, y=0.1)
    return p


@model
def cloud_floor():
    p = Piece('cloud_floor')
    for x, y, r in ((0, 0, 0.9), (-0.9, 0.3, 0.7), (0.9, 0.25, 0.75), (0.2, 0.9, 0.7), (-0.5, -0.6, 0.6), (0.6, -0.6, 0.55)):
        p.sphere(r, x, y, -0.32 * r, sx=1.0, sy=1.0, sz=0.38, seg=16)
    return p


@model
def floating_stairs():
    p = Piece('floating_stairs')
    for i in range(7):
        p.box(0.6, 0.28, 0.16, 0, i * 0.26, i * 0.16, bevel=0.01, seg=1)
    return p


@model
def giant_clock():
    p = Piece('giant_clock')
    p.cyl(0.45, 0.08, 0, 0, 0.45, rx=90, seg=40)
    p.box(0.04, 0.02, 0.3, 0, -0.06, 0.45, mat='i')
    p.box(0.22, 0.02, 0.04, 0.1, -0.06, 0.45, mat='i', ry=20)
    for i in range(12):
        a = 2 * math.pi * i / 12
        p.box(0.02, 0.02, 0.06, 0.36 * math.cos(a), -0.05, 0.42 + 0.36 * math.sin(a), mat='i')
    return p


@model
def dream_shapes():
    p = Piece('dream_shapes')
    p.box(0.25, 0.25, 0.25, -0.6, 0, 0.9, rz=25, rx=20, bevel=0.02, seg=2)
    p.sphere(0.14, 0.5, 0.2, 1.2)
    p.torus(0.16, 0.05, 0.1, -0.1, 1.6, rx=60)
    p.cyl(0.08, 0.3, 0.9, 0.0, 0.6, rx=40)
    return p


@model
def fern():
    p = Piece('fern')
    for a in range(0, 360, 45):
        r = math.radians(a)
        p.tube([(0, 0, 0), (0.25 * math.cos(r), 0.25 * math.sin(r), 0.35), (0.45 * math.cos(r), 0.45 * math.sin(r), 0.25)], 0.02)
    return p


@model
def cycad():
    p = Piece('cycad')
    p.cyl(0.12, 0.6, 0, 0, 0, r2=0.1, seg=12)
    for a in range(0, 360, 40):
        r = math.radians(a)
        p.tube([(0, 0, 0.6), (0.4 * math.cos(r), 0.4 * math.sin(r), 0.85), (0.7 * math.cos(r), 0.7 * math.sin(r), 0.6)], 0.025)
    return p


# ------------------------------------------------------------------ outdoor places
@model
def barn():
    p = Piece('barn')
    p.prism([(-1.4, 0), (-1.4, 1.6), (-0.9, 2.3), (0, 2.75), (0.9, 2.3), (1.4, 1.6), (1.4, 0)], 2.0)
    p.box(1.0, 0.04, 1.4, 0, -1.01, 0)
    p.box(0.04, 0.03, 1.4, 0, -1.04, 0)
    p.box(0.5, 0.04, 0.4, 0, -1.01, 1.8)
    return p


@model
def haystack():
    p = Piece('haystack')
    p.box(0.8, 0.5, 0.45, 0, 0, 0, bevel=0.08)
    p.box(0.8, 0.5, 0.45, 0.2, 0.1, 0.45, bevel=0.08, rz=10)
    return p


@model
def tractor():
    p = Piece('tractor')
    p.box(1.0, 0.6, 0.45, 0.2, 0, 0.35, bevel=0.06)
    p.box(0.5, 0.6, 0.55, -0.35, 0, 0.6, bevel=0.03)
    p.cyl(0.4, 0.22, -0.4, -0.38, 0.4, rx=90, seg=24, mat='i')
    p.cyl(0.4, 0.22, -0.4, 0.38 + 0.22, 0.4, rx=90, seg=24, mat='i')
    p.cyl(0.22, 0.16, 0.55, -0.34, 0.22, rx=90, seg=20, mat='i')
    p.cyl(0.22, 0.16, 0.55, 0.34 + 0.16, 0.22, rx=90, seg=20, mat='i')
    p.cyl(0.03, 0.35, 0.5, 0, 0.8, seg=8)
    return p


@model
def scarecrow():
    p = Piece('scarecrow')
    p.cyl(0.03, 1.5, 0, 0, 0, seg=8)
    p.box(0.9, 0.05, 0.05, 0, 0, 1.15)
    p.box(0.36, 0.16, 0.45, 0, 0, 0.75, bevel=0.04)
    p.sphere(0.14, 0, 0, 1.4)
    p.cyl(0.24, 0.02, 0, 0, 1.48, seg=20)
    p.cyl(0.1, 0.14, 0, 0, 1.5, r2=0.07, seg=16)
    return p


@model
def crop_rows():
    p = Piece('crop_rows')
    for r in range(5):
        p.box(4.0, 0.18, 0.06, 0, r * 0.5, 0, bevel=0.03, seg=2)
        for i in range(10):
            p.sphere(0.08, -1.8 + i * 0.4, r * 0.5, 0.1, sz=1.2, seg=8)
    return p


@model
def swings():
    p = Piece('swings')
    for x in (-0.9, 0.9):
        p.tube([(x - 0.35, 0, 0), (x, 0, 1.8), (x + 0.35 * (1 if x < 0 else -1) * -1, 0, 0)], 0.035)
        p.tube([(x, 0.35, 0), (x, 0, 1.8)], 0.035)
    p.tube([(-0.9, 0, 1.8), (0.9, 0, 1.8)], 0.04)
    for x in (-0.4, 0.4):
        for dx in (-0.14, 0.14):
            p.tube([(x + dx, 0, 1.78), (x + dx, 0, 0.45)], 0.007, mat='i')
        p.box(0.34, 0.14, 0.03, x, 0, 0.43)
    return p


@model
def slide():
    p = Piece('slide')
    for x in (-0.25, 0.25):
        p.tube([(x, 0.6, 0), (x, 0.6, 1.2)], 0.03)
        p.tube([(x, 0.9, 0), (x, 0.9, 1.2)], 0.03)
    p.box(0.55, 0.35, 0.05, 0, 0.75, 1.15)
    p.box(0.45, 1.6, 0.03, 0, -0.05, 0.6, rx=-35)
    for i in range(4):
        p.box(0.5, 0.04, 0.04, 0, 1.0, 0.25 + i * 0.28)
    return p


@model
def seesaw():
    p = Piece('seesaw')
    p.prism([(-0.15, 0), (0, 0.32), (0.15, 0)], 0.3)
    p.box(2.2, 0.18, 0.04, 0, 0, 0.3, ry=8)
    for x in (-0.95, 0.95):
        p.tube([(x, -0.12, 0.3 + x * 0.14 + 0.04), (x, -0.12, 0.3 + x * 0.14 + 0.2), (x, 0.12, 0.3 + x * 0.14 + 0.2),
                (x, 0.12, 0.3 + x * 0.14 + 0.04)], 0.012)
    return p


@model
def sandbox():
    p = Piece('sandbox')
    for x, y, w, d in ((0, -0.6, 1.4, 0.1), (0, 0.6, 1.4, 0.1), (-0.65, 0, 0.1, 1.3), (0.65, 0, 0.1, 1.3)):
        p.box(w, d, 0.18, x, y, 0)
    p.box(1.2, 1.1, 0.08, 0, 0, 0, bevel=0.03, seg=2)
    p.lathe([(0, 0.08), (0.12, 0.08), (0.08, 0.22), (0, 0.24)], x=0.2, y=0.1, seg=16)
    return p


@model
def picket_fence():
    p = Piece('picket_fence')
    for i in range(13):
        x = -2.4 + i * 0.4
        p.prism([(x - 0.06, 0), (x - 0.06, 0.7), (x, 0.8), (x + 0.06, 0.7), (x + 0.06, 0)], 0.03)
    for z in (0.2, 0.55):
        p.box(5.0, 0.03, 0.06, 0, 0.035, z)
    return p


@model
def flower_bed():
    p = Piece('flower_bed')
    p.box(1.4, 0.5, 0.18, 0, 0, 0, bevel=0.02, seg=2)
    for i in range(7):
        x = -0.6 + i * 0.2
        p.tube([(x, 0, 0.18), (x, 0, 0.42 + 0.05 * (i % 2))], 0.008)
        p.sphere(0.06, x, 0, 0.44 + 0.05 * (i % 2), seg=10)
    return p


@model
def hose_reel():
    p = Piece('hose_reel')
    p.cyl(0.2, 0.08, 0, 0, 0.3, rx=90, seg=24)
    p.torus(0.14, 0.03, 0, -0.04, 0.3, rx=90, seg=24, seg2=6, mat='i')
    p.tube([(-0.15, 0, 0), (0, 0, 0.3), (0.15, 0, 0)], 0.015)
    return p


@model
def birdhouse():
    p = Piece('birdhouse')
    p.cyl(0.03, 1.3, 0, 0, 0, seg=8)
    p.box(0.22, 0.2, 0.22, 0, 0, 1.3)
    p.prism([(-0.15, 1.52), (0, 1.66), (0.15, 1.52)], 0.24)
    p.cyl(0.04, 0.02, 0, -0.11, 1.42, rx=90, mat='i', seg=12)
    return p


@model
def garden_chair():
    p = Piece('garden_chair')
    p.box(0.5, 0.5, 0.05, 0, 0, 0.4, bevel=0.02, seg=2)
    p.box(0.5, 0.05, 0.5, 0, 0.24, 0.42, rx=-10, bevel=0.02, seg=2)
    for x in (-0.22, 0.22):
        for y in (-0.22, 0.22):
            p.cyl(0.02, 0.4, x, y, 0, seg=8)
    return p


@model
def house_back():
    p = Piece('house_back')
    p.prism([(-3.0, 0), (-3.0, 2.4), (0, 3.6), (3.0, 2.4), (3.0, 0)], 0.2)
    p.box(0.9, 0.04, 1.9, 1.4, -0.12, 0)
    p.box(1.0, 0.04, 0.8, -1.3, -0.12, 1.0)
    p.box(0.04, 0.05, 0.8, -1.3, -0.15, 1.0)
    return p


@model
def game_stall():
    p = Piece('game_stall')
    p.box(1.6, 0.7, 0.9, 0, 0, 0, bevel=0.02, seg=2)
    for x in (-0.78, 0.78):
        p.cyl(0.03, 1.2, x, -0.32, 0.9, seg=8)
    p.prism([(-0.95, 2.1), (-0.95, 2.25), (0.95, 2.25), (0.95, 2.1), (0.75, 1.95), (0.5, 2.1), (0.25, 1.95), (0, 2.1),
             (-0.25, 1.95), (-0.5, 2.1), (-0.75, 1.95)], 0.9)
    for i in range(3):
        p.cyl(0.05, 0.12, -0.4 + i * 0.4, 0.0, 0.9, seg=12, mat='i')
    return p


@model
def candy_cart():
    p = Piece('candy_cart')
    p.box(0.8, 0.5, 0.7, 0, 0, 0.18, bevel=0.03)
    p.cyl(0.16, 0.06, -0.3, -0.27, 0.0, rx=90, mat='i', seg=16)
    p.cyl(0.16, 0.06, 0.3, -0.27, 0.0, rx=90, mat='i', seg=16)
    p.lathe([(0, 0.88), (0.25, 0.9), (0.28, 1.0), (0, 1.02)], seg=24)
    for x in (-0.25, 0.25):
        p.tube([(x, 0.1, 0.88), (x, 0.1, 1.25)], 0.012)
        p.sphere(0.1, x, 0.1, 1.32, seg=12)
    return p


@model
def light_strings():
    p = Piece('light_strings')
    pts = [(-2.0 + i * 0.2, 0, 2.2 - 0.25 * math.sin(math.pi * i / 20)) for i in range(21)]
    p.tube(pts, 0.006, mat='i')
    for x, y, z in pts[1:-1:2]:
        p.sphere(0.04, x, y, z - 0.05, sz=1.3, seg=8)
    return p


@model
def traffic_cone():
    p = Piece('traffic_cone')
    p.box(0.32, 0.32, 0.03, 0, 0, 0)
    p.cyl(0.12, 0.45, 0, 0, 0.03, r2=0.03, seg=20)
    p.cyl(0.095, 0.07, 0, 0, 0.16, r2=0.075, seg=20, mat='i')
    return p


@model
def girders():
    p = Piece('girders')
    for i, (y, z) in enumerate(((0, 0), (0.25, 0), (0.12, 0.18))):
        p.box(2.2, 0.18, 0.04, 0, y, z)
        p.box(2.2, 0.18, 0.04, 0, y, z + 0.14)
        p.box(2.2, 0.03, 0.14, 0, y, z + 0.02)
    return p


@model
def cement_mixer():
    p = Piece('cement_mixer')
    p.lathe([(0, 0), (0.3, 0.05), (0.38, 0.35), (0.26, 0.65), (0.16, 0.7), (0.16, 0.74)], x=0, y=0, z=0.35, seg=24)
    p.tube([(-0.4, 0, 0.0), (0, 0, 0.45), (0.4, 0, 0.0)], 0.03)
    p.cyl(0.14, 0.06, 0.45, -0.1, 0.0, rx=90, mat='i', seg=16)
    return p


@model
def barrier():
    p = Piece('barrier')
    p.box(1.5, 0.08, 0.25, 0, 0, 0.6, bevel=0.02, seg=2)
    for i in range(4):
        p.prism([(-0.6 + i * 0.4, 0.6), (-0.5 + i * 0.4, 0.85), (-0.38 + i * 0.4, 0.85), (-0.48 + i * 0.4, 0.6)], 0.09, mat='i')
    for x in (-0.6, 0.6):
        p.tube([(x - 0.15, 0, 0), (x, 0, 0.6), (x + 0.15, 0, 0)], 0.025)
    return p


@model
def hard_hat():
    p = Piece('hard_hat')
    p.lathe([(0, 0.18), (0.12, 0.16), (0.16, 0.06), (0.16, 0.02)], seg=24)
    p.cyl(0.21, 0.02, 0, 0, 0.0, seg=24)
    return p


@model
def cricket_pitch():
    p = Piece('cricket_pitch')
    p.box(1.2, 8.0, 0.006, 0, 2.0, 0)
    for y in (-1.4, 5.4):
        p.box(1.0, 0.03, 0.004, 0, y, 0.006, mat='i')
    return p


@model
def stumps():
    p = Piece('stumps')
    for x in (-0.09, 0, 0.09):
        p.cyl(0.018, 0.65, x, 0, 0, seg=8)
    p.box(0.22, 0.02, 0.02, 0, 0, 0.66)
    return p


@model
def sight_screen():
    p = Piece('sight_screen')
    p.box(3.0, 0.1, 1.8, 0, 0, 0.3)
    for x in (-1.3, 1.3):
        p.cyl(0.18, 0.1, x, 0, 0.0, rx=90, mat='i', seg=16)
    return p


@model
def boundary_rope():
    p = Piece('boundary_rope')
    p.torus(9.0, 0.04, 0, 0, 0.04, seg=96, seg2=6)
    return p


# ------------------------------------------------------------------ everyday India
@model
def chai_stall():
    p = Piece('chai_stall')
    p.box(1.6, 0.7, 0.9, 0, 0, 0, bevel=0.02, seg=2)
    p.box(1.7, 0.75, 0.04, 0, 0, 0.9)
    for x in (-0.8, 0.8):
        for y in (-0.33, 0.33):
            p.cyl(0.03, 1.2, x, y, 0.9, seg=8)
    p.box(2.0, 1.1, 0.04, 0, -0.1, 2.1, rx=-8)
    p.box(1.0, 0.04, 0.35, 0, -0.38, 1.68)  # signboard
    return p


@model
def stove_kettle():
    p = Piece('stove_kettle')
    p.cyl(0.16, 0.1, 0, 0, 0, seg=20, mat='i')
    p.lathe([(0, 0.1), (0.14, 0.11), (0.15, 0.24), (0.1, 0.32), (0.03, 0.34), (0, 0.36)], seg=24)
    p.tube([(0.12, 0, 0.18), (0.25, 0, 0.32)], 0.018)
    p.tube([(-0.1, 0, 0.3), (0, 0, 0.42), (0.1, 0, 0.3)], 0.01, mat='i')
    return p


@model
def glass_tray():
    p = Piece('glass_tray')
    p.box(0.4, 0.26, 0.02, 0, 0, 0, bevel=0.01, seg=1)
    for x in (-0.12, 0, 0.12):
        for y in (-0.06, 0.06):
            p.cyl(0.03, 0.08, x, y, 0.02, r2=0.035, seg=12)
    return p


@model
def wooden_bench():
    p = Piece('wooden_bench')
    p.box(1.4, 0.35, 0.05, 0, 0, 0.42, bevel=0.01, seg=1)
    for x in (-0.6, 0.6):
        p.box(0.06, 0.3, 0.42, x, 0, 0)
    return p


@model
def scooter():
    p = Piece('scooter')
    p.cyl(0.18, 0.1, -0.5, 0.05, 0.18, rx=90, seg=20, mat='i')
    p.cyl(0.18, 0.1, 0.5, 0.05, 0.18, rx=90, seg=20, mat='i')
    p.box(0.75, 0.32, 0.12, -0.05, 0, 0.3, bevel=0.04)
    p.box(0.55, 0.36, 0.3, -0.35, 0, 0.42, bevel=0.1)
    p.box(0.5, 0.3, 0.08, -0.3, 0, 0.72, bevel=0.04, mat='i')
    p.tube([(0.45, 0, 0.3), (0.5, 0, 0.95)], 0.05)
    p.tube([(0.5, -0.25, 0.95), (0.5, 0.25, 0.95)], 0.02)
    return p


@model
def market_stall():
    p = Piece('market_stall')
    p.box(1.4, 0.7, 0.7, 0, 0, 0, bevel=0.02, seg=2)
    for x in (-0.68, 0.68):
        p.cyl(0.025, 1.5, x, -0.3, 0.7, seg=8)
        p.cyl(0.025, 1.7, x, 0.32, 0.7, seg=8)
    p.box(1.7, 1.0, 0.03, 0, -0.1, 2.2, rx=-12)
    for i in range(4):
        p.box(0.3, 0.3, 0.12, -0.5 + i * 0.33, -0.1, 0.7, bevel=0.02, seg=2)
        for k in range(3):
            p.sphere(0.05, -0.55 + i * 0.33 + k * 0.05, -0.12, 0.84, seg=8)
    return p


@model
def fruit_crates():
    p = Piece('fruit_crates')
    for x, y, z in ((0, 0, 0), (0.42, 0.05, 0), (0.2, 0.02, 0.26)):
        p.box(0.4, 0.3, 0.26, x, y, z, bevel=0.01, seg=1)
    return p


@model
def bus_shelter():
    p = Piece('bus_shelter')
    for x in (-1.2, 1.2):
        p.box(0.08, 0.08, 2.1, x, 0.3, 0)
    p.box(2.6, 0.04, 1.6, 0, 0.32, 0.4)
    p.box(2.8, 1.0, 0.08, 0, 0.0, 2.1, bevel=0.02, seg=2)
    p.box(2.0, 0.3, 0.05, 0, 0.15, 0.45)
    return p


@model
def bus_sign():
    p = Piece('bus_sign')
    p.cyl(0.03, 1.9, 0, 0, 0, seg=8)
    p.cyl(0.22, 0.03, 0, 0, 1.9, rx=90, seg=24, mat='i')
    return p


@model
def bus():
    p = Piece('bus')
    p.box(4.2, 1.1, 1.3, 0, 0, 0.3, bevel=0.15)
    for x in (-1.5, -0.5, 0.5, 1.5):
        p.box(0.75, 0.04, 0.45, x, -0.56, 0.9)
    for x in (-1.4, 1.4):
        p.cyl(0.3, 0.12, x, -0.5, 0.3, rx=90, seg=20, mat='i')
    return p


@model
def ghat_steps():
    p = Piece('ghat_steps')
    for i in range(8):
        p.box(6.0, 0.36, 0.12, 0, 1.4 + i * 0.36, -0.12 * (i + 1))
    return p


@model
def temple_top():
    p = Piece('temple_top')
    p.box(1.2, 1.2, 1.0, 0, 0, 0)
    p.lathe([(0.62, 1.0), (0.55, 1.4), (0.45, 1.9), (0.3, 2.3), (0.12, 2.55), (0.05, 2.7), (0, 2.75)], seg=8)
    p.tube([(0, 0, 2.7), (0, 0, 3.05)], 0.01, mat='i')
    p.prism([(0, 3.05), (0.22, 2.97), (0, 2.9)], 0.01, mat='i')
    return p


@model
def diyas():
    p = Piece('diyas')
    for i in range(5):
        x = -0.5 + i * 0.25
        p.lathe([(0, 0), (0.05, 0.0), (0.06, 0.03), (0.0, 0.03)], x=x, seg=12)
        p.prism([(x - 0.012, 0.03), (x, 0.08), (x + 0.012, 0.03)], 0.012, mat='i')
    return p


@model
def water_tank():
    p = Piece('water_tank')
    p.cyl(0.55, 1.0, 0, 0, 0.25, seg=28)
    p.cyl(0.22, 0.1, 0, 0, 1.25, seg=20)
    p.box(1.1, 1.1, 0.25, 0, 0, 0)
    for i in range(4):
        p.torus(0.555, 0.01, 0, 0, 0.4 + i * 0.22, seg=28, seg2=4, mat='i')
    return p


@model
def clothesline():
    p = Piece('clothesline')
    for x in (-1.6, 1.6):
        p.cyl(0.025, 1.6, x, 0, 0, seg=8)
    pts = [(-1.6 + i * 0.32, 0, 1.55 - 0.08 * math.sin(math.pi * i / 10)) for i in range(11)]
    p.tube(pts, 0.006, mat='i')
    for i, (x, w, h) in enumerate(((-1.0, 0.36, 0.5), (-0.3, 0.3, 0.4), (0.35, 0.4, 0.55), (1.0, 0.28, 0.3))):
        z = 1.55 - 0.08 * math.sin(math.pi * (x + 1.6) / 3.2)
        p.box(w, 0.02, h, x, 0, z - h, mat='i' if i % 2 else 'm')
    return p


@model
def kites():
    p = Piece('kites')
    for x, z, s in ((0, 0, 1.0), (0.9, 0.35, 0.7)):
        p.prism([(x, z - 0.2 * s), (x + 0.15 * s, z), (x, z + 0.22 * s), (x - 0.15 * s, z)], 0.01)
        p.tube([(x, 0, z - 0.2 * s), (x + 0.05, 0, z - 0.45 * s), (x - 0.05, 0, z - 0.7 * s)], 0.004, mat='i')
    return p


@model
def parapet():
    p = Piece('parapet')
    p.box(6.0, 0.18, 0.7, 0, 0, 0)
    p.box(0.18, 5.0, 0.7, -3.0, -2.5, 0)
    p.box(0.18, 5.0, 0.7, 3.0, -2.5, 0)
    return p


@model
def mandap():
    p = Piece('mandap')
    p.box(2.6, 2.0, 0.2, 0, 0, 0, bevel=0.02, seg=2)
    for x in (-1.15, 1.15):
        for y in (-0.85, 0.85):
            p.cyl(0.07, 2.1, x, y, 0.2, seg=12)
    p.box(2.7, 2.1, 0.12, 0, 0, 2.3, bevel=0.03)
    p.lathe([(1.0, 2.42), (0.6, 2.75), (0.2, 2.95), (0, 3.0)], seg=4)
    return p


@model
def marigold_strings():
    p = Piece('marigold_strings')
    for x in (-1.1, -0.55, 0, 0.55, 1.1):
        for k in range(7):
            p.sphere(0.045, x, 0, 2.2 - k * 0.11, seg=8)
    return p


@model
def plastic_chair():
    p = Piece('plastic_chair')
    p.box(0.42, 0.42, 0.04, 0, 0, 0.42, bevel=0.02, seg=2)
    p.box(0.42, 0.04, 0.42, 0, 0.2, 0.46, rx=-8, bevel=0.03, seg=2)
    for x in (-0.18, 0.18):
        for y in (-0.18, 0.18):
            p.cyl(0.02, 0.42, x, y, 0, r2=0.025, seg=8)
    return p


@model
def chair_rows():
    p = Piece('chair_rows')
    for r in range(2):
        for i in range(5):
            x, y = -1.0 + i * 0.5, r * 0.7
            p.box(0.4, 0.4, 0.04, x, y, 0.42, bevel=0.015, seg=1)
            p.box(0.4, 0.04, 0.38, x, y + 0.19, 0.46)
            for dx in (-0.16, 0.16):
                p.cyl(0.018, 0.42, x + dx, y, 0, seg=6)
    return p


# ------------------------------------------------------------------ indoor everyday
@model
def drying_rack():
    p = Piece('drying_rack')
    p.tube([(-0.45, -0.25, 0), (-0.45, 0, 0.9), (-0.45, 0.25, 0)], 0.015)
    p.tube([(0.45, -0.25, 0), (0.45, 0, 0.9), (0.45, 0.25, 0)], 0.015)
    for z in (0.5, 0.7, 0.9):
        p.tube([(-0.45, 0, z), (0.45, 0, z)], 0.01)
    p.box(0.3, 0.02, 0.32, -0.15, 0, 0.58)
    p.box(0.24, 0.02, 0.25, 0.2, 0, 0.65, mat='i')
    return p


@model
def balcony_wall():
    p = Piece('balcony_wall')
    p.box(0.25, 3.0, 2.6, 0, 0, 0)
    p.box(0.05, 0.9, 1.9, 0.15, 0.6, 0)  # door back into the flat
    return p


@model
def workbench():
    p = Piece('workbench')
    p.box(1.6, 0.6, 0.06, 0, 0, 0.82, bevel=0.01, seg=1)
    for x in (-0.72, 0.72):
        for y in (-0.25, 0.25):
            p.box(0.06, 0.06, 0.82, x, y, 0)
    p.box(1.5, 0.5, 0.03, 0, 0, 0.2)
    p.box(0.2, 0.14, 0.12, -0.55, -0.05, 0.88, mat='i')  # vice
    return p


@model
def tool_wall():
    p = Piece('tool_wall')
    p.box(1.6, 0.03, 0.9, 0, 0, 0)
    p.tube([(-0.6, -0.03, 0.75), (-0.6, -0.03, 0.35)], 0.015, mat='i')
    p.box(0.12, 0.03, 0.06, -0.6, -0.04, 0.75, mat='i')
    p.torus(0.08, 0.012, -0.25, -0.04, 0.55, rx=90, seg=16, seg2=4, mat='i')
    p.tube([(0.1, -0.03, 0.8), (0.1, -0.03, 0.3)], 0.012, mat='i')
    p.box(0.2, 0.03, 0.1, 0.45, -0.04, 0.6, mat='i')
    p.tube([(0.45, -0.03, 0.6), (0.45, -0.03, 0.3)], 0.015, mat='i')
    return p


@model
def shutter():
    p = Piece('shutter')
    p.box(2.4, 0.06, 2.0, 0, 0, 0)
    for i in range(10):
        p.box(2.4, 0.08, 0.02, 0, -0.01, 0.2 * i + 0.1, mat='i')
    return p


@model
def metal_shelves():
    p = Piece('metal_shelves')
    for x in (-0.45, 0.45):
        for y in (-0.18, 0.18):
            p.box(0.04, 0.04, 1.8, x, y, 0)
    for z in (0.1, 0.6, 1.1, 1.6):
        p.box(0.95, 0.4, 0.03, 0, 0, z)
    p.box(0.3, 0.3, 0.25, -0.2, 0, 0.63, bevel=0.01, seg=1)
    p.box(0.4, 0.3, 0.2, 0.15, 0, 1.13, bevel=0.01, seg=1)
    return p


@model
def bicycle():
    p = Piece('bicycle')
    for x in (-0.48, 0.48):
        p.torus(0.3, 0.025, x, 0, 0.32, rx=90, seg=28, seg2=6, mat='i')
    p.tube([(-0.48, 0, 0.32), (-0.1, 0, 0.32), (0.25, 0, 0.7), (-0.2, 0, 0.7), (-0.1, 0, 0.32)], 0.02)
    p.tube([(-0.48, 0, 0.32), (-0.2, 0, 0.7)], 0.018)
    p.tube([(0.48, 0, 0.32), (0.3, 0, 0.82)], 0.02)
    p.tube([(0.3, -0.2, 0.84), (0.3, 0.2, 0.84)], 0.018)
    p.box(0.22, 0.1, 0.05, -0.22, 0, 0.76, bevel=0.02, seg=2)
    return p


@model
def stairs():
    p = Piece('stairs')
    for i in range(9):
        p.box(1.0, 0.3, 0.18 * (i + 1), 0, i * 0.3, 0)
    p.tube([(-0.5, -0.1, 0.9), (-0.5, 2.6, 2.5)], 0.025)
    for i in range(5):
        p.tube([(-0.5, i * 0.6, 0.18 * (i * 2 + 1)), (-0.5, i * 0.6, 0.18 * (i * 2 + 1) + 0.8)], 0.012)
    return p


@model
def letterboxes():
    p = Piece('letterboxes')
    for r in range(3):
        for c in range(4):
            p.box(0.24, 0.12, 0.18, -0.39 + c * 0.26, 0, 0.9 + r * 0.2, bevel=0.01, seg=1)
            p.box(0.14, 0.02, 0.02, -0.39 + c * 0.26, -0.06, 1.03 + r * 0.2, mat='i')
    return p


@model
def lift_door():
    p = Piece('lift_door')
    p.box(1.3, 0.1, 2.2, 0, 0, 0)
    p.box(1.0, 0.04, 1.9, 0, -0.05, 0)
    p.box(0.02, 0.05, 1.9, 0, -0.08, 0)
    p.box(0.1, 0.04, 0.24, 0.8, -0.03, 1.0)
    p.box(0.3, 0.04, 0.12, 0, -0.05, 2.0)
    return p


@model
def big_window_view():
    p = Piece('big_window_view')
    p.box(2.0, 0.08, 1.4, 0, 0, 0)
    p.box(1.8, 0.1, 1.2, 0, 0, 0.1)
    p.box(0.04, 0.12, 1.2, 0, -0.01, 0.1)
    import random
    rnd = random.Random(5)
    x = -0.85
    while x < 0.85:  # little city inside the pane
        w, h = rnd.uniform(0.1, 0.22), rnd.uniform(0.25, 0.8)
        p.box(w, 0.02, h, x + w / 2, -0.06, 0.12)
        x += w + 0.04
    return p


@model
def room_service():
    p = Piece('room_service')
    p.box(0.6, 0.45, 0.04, 0, 0, 0.75, bevel=0.01, seg=1)
    for x in (-0.25, 0.25):
        for y in (-0.18, 0.18):
            p.cyl(0.015, 0.75, x, y, 0, seg=6)
    p.lathe([(0, 0.79), (0.14, 0.79), (0.13, 0.86), (0.07, 0.92), (0, 0.93)], seg=20)
    p.sphere(0.015, 0, 0, 0.94)
    return p


@model
def barber_chair():
    p = Piece('barber_chair')
    p.cyl(0.25, 0.04, 0, 0, 0, seg=24)
    p.cyl(0.06, 0.35, 0, 0, 0.04, seg=12, mat='i')
    p.box(0.55, 0.55, 0.15, 0, 0, 0.4, bevel=0.05)
    p.box(0.55, 0.15, 0.6, 0, 0.22, 0.52, bevel=0.06, rx=-10)
    for x in (-0.3, 0.3):
        p.box(0.08, 0.5, 0.08, x, 0, 0.62, bevel=0.03)
    p.box(0.4, 0.08, 0.04, 0, -0.38, 0.2)
    return p


@model
def salon_mirror():
    p = Piece('salon_mirror')
    p.box(1.4, 0.4, 0.06, 0, 0, 0.85, bevel=0.01, seg=1)
    p.box(1.3, 0.35, 0.8, 0, 0, 0.05)
    p.box(1.0, 0.04, 1.0, 0, 0.18, 1.15)
    p.box(0.9, 0.05, 0.9, 0, 0.15, 1.2)
    p.cyl(0.035, 0.18, -0.4, 0, 0.91, seg=12)
    p.cyl(0.03, 0.12, -0.3, 0, 0.91, seg=12, mat='i')
    return p


@model
def barber_pole():
    p = Piece('barber_pole')
    p.cyl(0.08, 0.7, 0, 0, 1.0, seg=20)
    p.sphere(0.09, 0, 0, 1.75, seg=12)
    p.cyl(0.1, 0.06, 0, 0, 0.95, seg=20)
    for i in range(5):
        p.tube([(0.081 * math.cos(a), 0.081 * math.sin(a), 1.0 + a * 0.06) for a in
                [i * 1.25 + k * 0.4 for k in range(12)]], 0.012, mat='i')
    return p


@model
def hood_dryer():
    p = Piece('hood_dryer')
    p.cyl(0.22, 0.04, 0, 0, 0, seg=20)
    p.cyl(0.03, 1.1, 0, 0, 0.04, seg=8)
    p.lathe([(0.18, 1.1), (0.26, 1.15), (0.26, 1.35), (0.15, 1.45), (0, 1.46)], x=0, y=-0.1, seg=20)
    return p


@model
def bank_counter():
    p = Piece('bank_counter')
    p.box(3.0, 0.6, 1.0, 0, 0, 0)
    p.box(3.1, 0.7, 0.05, 0, 0, 1.0)
    for x in (-1.0, 0.0, 1.0):
        p.box(0.05, 0.05, 0.7, x - 0.48, 0, 1.05)
    p.box(3.0, 0.04, 0.05, 0, 0, 1.72)
    p.box(0.4, 0.04, 0.12, 0, -0.02, 1.05, mat='i')  # window slot
    return p


@model
def token_display():
    p = Piece('token_display')
    p.box(0.7, 0.08, 0.3, 0, 0, 0, bevel=0.02, seg=2)
    p.box(0.6, 0.04, 0.2, 0, -0.04, 0.05)
    return p


@model
def stanchions():
    p = Piece('stanchions')
    for x in (-0.9, 0.0, 0.9):
        p.cyl(0.13, 0.03, x, 0, 0, seg=20)
        p.cyl(0.025, 0.9, x, 0, 0.03, seg=10)
        p.sphere(0.04, x, 0, 0.95)
    for x0 in (-0.9, 0.0):
        p.tube([(x0 + i * 0.1, 0, 0.88 - 0.12 * math.sin(math.pi * i / 9)) for i in range(10)], 0.015, mat='i')
    return p


@model
def atm():
    p = Piece('atm')
    p.box(0.7, 0.6, 1.5, 0, 0, 0, bevel=0.03)
    p.box(0.5, 0.05, 0.35, 0, -0.3, 1.05)
    p.box(0.5, 0.2, 0.05, 0, -0.35, 0.85, rx=20)
    p.box(0.2, 0.03, 0.03, 0.12, -0.31, 0.7, mat='i')
    return p


@model
def statue_plinth():
    p = Piece('statue_plinth')
    p.box(0.5, 0.5, 0.9, 0, 0, 0)
    p.box(0.6, 0.6, 0.06, 0, 0, 0.9)
    p.cyl(0.08, 0.5, 0, 0, 0.96, r2=0.13, seg=16)
    p.sphere(0.13, 0, 0, 1.6, sz=1.2, seg=16)
    p.box(0.42, 0.18, 0.12, 0, 0, 1.4, bevel=0.05)
    return p


@model
def museum_bench():
    p = Piece('museum_bench')
    p.box(1.4, 0.45, 0.12, 0, 0, 0.32, bevel=0.04)
    for x in (-0.55, 0.55):
        p.box(0.1, 0.4, 0.32, x, 0, 0)
    return p


@model
def easel():
    p = Piece('easel')
    p.tube([(-0.3, -0.1, 0), (0, 0, 1.6)], 0.022)
    p.tube([(0.3, -0.1, 0), (0, 0, 1.6)], 0.022)
    p.tube([(0, 0.45, 0), (0, 0, 1.5)], 0.02)
    p.box(0.6, 0.05, 0.04, 0, -0.06, 0.65)
    p.box(0.55, 0.03, 0.7, 0, -0.07, 0.69)
    return p


@model
def crates():
    p = Piece('crates')
    for x, y, z, s in ((0, 0, 0, 0.45), (0.5, 0.1, 0, 0.4), (0.15, 0.05, 0.45, 0.35)):
        p.box(s, s, s, x, y, z, bevel=0.01, seg=1)
        p.box(s * 1.02, 0.02, 0.04, x, y - s / 2, z + s * 0.45, mat='i')
    return p


@model
def round_window():
    p = Piece('round_window')
    p.torus(0.4, 0.05, 0, 0, 0.4, rx=90, seg=36, seg2=8)
    p.cyl(0.36, 0.03, 0, 0.02, 0.4, rx=90, seg=36, mat='i')
    p.box(0.72, 0.04, 0.04, 0, -0.02, 0.38)
    p.box(0.04, 0.04, 0.72, 0, -0.02, 0.04)
    return p


# ------------------------------------------------------------------ inside things that move
@model
def berths():
    p = Piece('berths')
    for z in (0.45, 1.25):
        p.box(1.9, 0.6, 0.12, 0, 0, z, bevel=0.04)
    p.box(1.9, 0.05, 1.9, 0, 0.32, 0)
    p.box(0.05, 0.6, 1.9, -0.95, 0, 0)
    p.tube([(0.9, -0.3, 0.2), (0.9, -0.3, 1.5)], 0.015)
    for i in range(5):
        p.tube([(0.86, -0.3, 0.3 + i * 0.25), (0.94, -0.3, 0.3 + i * 0.25)], 0.01)
    return p


@model
def train_window():
    p = Piece('train_window')
    p.box(1.4, 0.08, 1.0, 0, 0, 0, bevel=0.05)
    p.box(1.2, 0.1, 0.8, 0, 0, 0.1)
    for i in range(5):
        p.box(1.2, 0.12, 0.03, 0, -0.01, 0.2 + i * 0.15)  # window bars
    return p


@model
def scenery_card():
    """Hills and poles seen through a moving train or plane window (slide it along x)."""
    p = Piece('scenery_card')
    pts = [(-4, 0)] + [(x / 5.0, 0.3 + 0.15 * math.sin(x / 3.0)) for x in range(-20, 21)] + [(4, 0)]
    p.prism(pts, 0.02)
    for x in (-3, -1.5, 0, 1.5, 3):
        p.box(0.04, 0.02, 0.9, x, -0.02, 0)
    return p


@model
def plane_seats():
    p = Piece('plane_seats')
    for r in range(3):
        for c in range(3):
            x, y = -0.5 + c * 0.5, r * 0.85
            p.box(0.46, 0.45, 0.14, x, y, 0.3, bevel=0.05)
            p.box(0.46, 0.14, 0.75, x, y + 0.24, 0.35, bevel=0.06, rx=-8)
            p.box(0.46, 0.15, 0.05, x, y + 0.27, 1.12, bevel=0.02, seg=2, mat='i')
    return p


@model
def overhead_bins():
    p = Piece('overhead_bins')
    p.box(1.6, 3.0, 0.4, 0, 0, 0, bevel=0.06)
    for y in (-1.0, 0.0, 1.0):
        p.box(1.62, 0.02, 0.32, 0, y, 0.04)
    return p


@model
def plane_window():
    p = Piece('plane_window')
    p.box(0.42, 0.08, 0.6, 0, 0, 0, bevel=0.18)
    p.box(0.3, 0.1, 0.46, 0, 0, 0.07, bevel=0.13, mat='i')
    return p


@model
def trolley():
    p = Piece('trolley')
    p.box(0.4, 0.75, 0.95, 0, 0, 0.06, bevel=0.03)
    for y in (-0.3, 0.3):
        for x in (-0.15, 0.15):
            p.cyl(0.04, 0.03, x, y, 0, rx=90, seg=12, mat='i')
    p.box(0.42, 0.02, 0.02, 0, -0.38, 0.5, mat='i')
    p.cyl(0.04, 0.12, 0.05, 0.1, 1.01, seg=12)
    return p


@model
def seatbelt_sign():
    p = Piece('seatbelt_sign')
    p.box(0.4, 0.08, 0.16, 0, 0, 0, bevel=0.03, mat='i')
    p.box(0.3, 0.03, 0.08, 0, -0.04, 0.04)
    return p


# ------------------------------------------------------------------ story and genre rooms
@model
def lab_bench():
    p = Piece('lab_bench')
    p.box(1.8, 0.7, 0.9, 0, 0, 0)
    p.box(1.9, 0.75, 0.05, 0, 0, 0.9)
    p.box(0.3, 0.3, 0.06, -0.5, 0, 0.95)  # sink
    p.tube([(-0.5, 0.2, 0.95), (-0.5, 0.2, 1.25), (-0.5, 0.05, 1.25), (-0.5, 0.05, 1.15)], 0.015)
    return p


@model
def flasks():
    p = Piece('flasks')
    p.lathe([(0, 0), (0.1, 0), (0.1, 0.02), (0.03, 0.16), (0.03, 0.24), (0, 0.24)], seg=20)
    p.lathe([(0, 0), (0.06, 0), (0.06, 0.12), (0.025, 0.16), (0.025, 0.22), (0, 0.22)], x=0.25, seg=16)
    for i in range(4):
        p.cyl(0.018, 0.16, 0.45 + i * 0.05, 0, 0.0, seg=10)
    p.box(0.25, 0.06, 0.02, 0.52, 0, 0.08, mat='i')
    return p


@model
def microscope():
    p = Piece('microscope')
    p.box(0.2, 0.25, 0.04, 0, 0, 0, bevel=0.01, seg=1)
    p.tube([(0, 0.08, 0.04), (0, 0.08, 0.2), (0, -0.02, 0.32)], 0.025)
    p.cyl(0.03, 0.2, 0, -0.02, 0.18, rx=-25, seg=12, mat='i')
    p.box(0.14, 0.12, 0.02, 0, -0.03, 0.14)
    return p


@model
def server_rack():
    p = Piece('server_rack')
    for i, x in enumerate((-0.7, 0.0, 0.7)):
        p.box(0.6, 0.8, 2.0, x, 0, 0, bevel=0.01, seg=1)
        for k in range(8):
            p.box(0.5, 0.02, 0.12, x, -0.41, 0.2 + k * 0.22)
            p.sphere(0.012, x + 0.18, -0.43, 0.26 + k * 0.22, seg=6)
    return p


@model
def cable_tray():
    p = Piece('cable_tray')
    p.box(0.4, 4.0, 0.06, 0, 0, 0)
    for x in (-0.12, 0.0, 0.12):
        p.tube([(x, -2.0, 0.08), (x, 2.0, 0.08)], 0.02, mat='i')
    return p


@model
def bare_bulb():
    p = Piece('bare_bulb')
    p.tube([(0, 0, 0), (0, 0, -0.9)], 0.006, mat='i')
    p.cyl(0.025, 0.05, 0, 0, -0.95, seg=12, mat='i')
    p.sphere(0.06, 0, 0, -1.02, sz=1.2, seg=16)
    return p


@model
def boiler():
    p = Piece('boiler')
    p.cyl(0.35, 1.5, 0, 0, 0, seg=24)
    p.tube([(0, 0, 1.5), (0, 0, 1.8), (0.4, 0, 2.0), (1.0, 0, 2.0)], 0.06)
    p.cyl(0.08, 0.04, 0.1, -0.35, 0.9, rx=90, seg=16, mat='i')
    return p


@model
def cave_shell():
    p = Piece('cave_shell')
    import random
    rnd = random.Random(2)
    for i in range(16):
        a = math.pi * (0.05 + 0.9 * i / 15)
        x, y = 2.6 * math.cos(a), 1.2 + 1.6 * math.sin(a)
        p.sphere(rnd.uniform(0.7, 1.1), x, y, rnd.uniform(0.4, 1.4), sx=1.0, sy=0.8, sz=1.5, seg=12)
    for x in (-1.6, -0.5, 0.6, 1.5):
        p.cyl(0.12, 0.6, x, 1.6 + 0.3 * math.sin(x), 2.0, r2=0.0, rx=180, seg=10)  # stalactites
    return p


@model
def cave_paint():
    p = Piece('cave_paint')
    p.tube([(-0.5, 0, 0.0), (-0.2, 0, 0.15), (0.1, 0, 0.05)], 0.012, mat='i')
    p.tube([(-0.35, 0, 0.1), (-0.38, 0, -0.1)], 0.012, mat='i')
    p.tube([(-0.05, 0, 0.08), (-0.02, 0, -0.1)], 0.012, mat='i')
    p.tube([(0.3, 0, -0.1), (0.3, 0, 0.12), (0.4, 0, 0.2)], 0.012, mat='i')
    p.cyl(0.04, 0.01, 0.3, 0, 0.2, rx=90, mat='i')
    return p


@model
def throne():
    p = Piece('throne')
    p.box(0.8, 0.7, 0.45, 0, 0, 0.2, bevel=0.03)
    p.box(1.0, 0.9, 0.2, 0, 0, 0, bevel=0.03)
    p.prism([(-0.4, 0.65), (-0.4, 1.6), (-0.2, 1.75), (0, 1.9), (0.2, 1.75), (0.4, 1.6), (0.4, 0.65)], 0.15, y=0.3)
    for x in (-0.42, 0.42):
        p.box(0.12, 0.6, 0.3, x, -0.02, 0.65, bevel=0.04)
    p.box(0.6, 0.5, 0.08, 0, -0.05, 0.65, bevel=0.03)
    return p


@model
def banner():
    p = Piece('banner')
    p.cyl(0.02, 0.9, -0.45, 0, 0, rx=0, ry=90, seg=8)
    p.prism([(-0.4, 0), (0.4, 0), (0.4, -1.4), (0, -1.2), (-0.4, -1.4)], 0.02, z=-0.02)
    p.prism([(-0.12, -0.5), (0, -0.3), (0.12, -0.5), (0, -0.7)], 0.03, z=-0.02)
    return p


@model
def arches():
    p = Piece('arches')
    for x in (-1.6, 0.0, 1.6):
        outline = [(x - 0.75, 0), (x - 0.75, 3.0), (x + 0.75, 3.0), (x + 0.75, 0), (x + 0.55, 0), (x + 0.55, 1.9)]
        outline += [(x + 0.55 * math.cos(math.pi * k / 8), 1.9 + 0.55 * math.sin(math.pi * k / 8)) for k in range(1, 8)]
        outline += [(x - 0.55, 1.9), (x - 0.55, 0)]
        p.prism(outline, 0.35)
    return p


@model
def red_carpet():
    p = Piece('red_carpet')
    p.box(1.2, 4.5, 0.01, 0, 0, 0)
    p.box(1.0, 4.4, 0.004, 0, 0, 0.01)
    return p


@model
def captain_chair():
    p = Piece('captain_chair')
    p.cyl(0.3, 0.05, 0, 0, 0, seg=24)
    p.cyl(0.07, 0.35, 0, 0, 0.05, seg=12)
    p.box(0.65, 0.6, 0.14, 0, 0, 0.4, bevel=0.06)
    p.box(0.65, 0.14, 0.75, 0, 0.25, 0.5, bevel=0.08, rx=-10)
    for x in (-0.36, 0.36):
        p.box(0.1, 0.5, 0.12, x, 0, 0.58, bevel=0.04)
        p.box(0.08, 0.1, 0.03, x, -0.2, 0.71, mat='i')
    return p


@model
def consoles():
    p = Piece('consoles')
    for x, rz in ((-1.1, 20), (1.1, -20)):
        p.box(1.2, 0.6, 0.85, x, 0, 0, rz=rz, bevel=0.04)
        p.box(1.1, 0.5, 0.04, x, -0.06, 0.88, rz=rz, rx=20)
        for k in range(4):
            p.sphere(0.03, x - 0.3 + k * 0.2, -0.2, 0.95, seg=8)
    return p


@model
def space_window():
    p = Piece('space_window')
    p.prism([(-2.0, 0.0), (-2.2, 1.3), (-1.4, 2.0), (1.4, 2.0), (2.2, 1.3), (2.0, 0.0)], 0.12)
    p.prism([(-1.8, 0.15), (-1.95, 1.2), (-1.3, 1.8), (1.3, 1.8), (1.95, 1.2), (1.8, 0.15)], 0.14)
    import random
    rnd = random.Random(9)
    for _ in range(26):
        x, z, r = rnd.uniform(-1.7, 1.7), rnd.uniform(0.3, 1.7), rnd.uniform(0.01, 0.025)
        p.prism([(x - r, z), (x, z + r * 2.5), (x + r, z), (x, z - r * 2.5)], 0.16)
    p.sphere(0.22, 1.1, -0.02, 1.3, sy=0.15, seg=16)
    return p


@model
def box_flaps():
    p = Piece('box_flaps')
    w, h = 4.4, 2.6
    p.box(w, 0.06, 1.3, 0, 2.2, h, rx=-25)      # back flap, open
    p.box(0.06, 3.0, 1.3, -w / 2, 0.6, h, ry=30)
    p.box(0.06, 3.0, 1.3, w / 2, 0.6, h, ry=-30)
    p.box(w, 0.02, 0.12, 0, 2.17, 1.2)  # tape line
    return p


@model
def giant_eye():
    p = Piece('giant_eye')
    p.sphere(0.9, 0, 0, 0.9, sy=0.25, seg=20)
    p.sphere(0.42, 0, -0.2, 0.85, sy=0.1, seg=16, mat='i')
    p.tube([(-1.0, 0, 1.25), (0, 0, 1.55), (1.0, 0, 1.25)], 0.04, mat='i')
    return p
