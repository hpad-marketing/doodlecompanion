"""Doodle scenery models, built from kit primitives at Bunny scale (Bunny is ~1.02 m tall).

Every function returns a kit.Piece. Sizes follow Doodle Studio's background
heights (Bunny heights x 0.8 -> metres) and real furniture proportions, kept
chunky and simple so the one stroke weight reads cleanly.
"""
import math

from kit import Piece

M = {}


def model(fn):
    M[fn.__name__] = fn
    return fn


# ------------------------------------------------------------------ living room
@model
def sofa():
    p = Piece('sofa')
    p.box(1.5, 0.62, 0.2, 0, 0, 0.12, bevel=0.06)                   # base
    p.box(1.3, 0.5, 0.14, 0, -0.04, 0.32, bevel=0.06)               # seat cushion
    p.box(1.5, 0.2, 0.42, 0, 0.21, 0.32, bevel=0.08)                # back
    for s in (-1, 1):
        p.box(0.2, 0.62, 0.36, s * 0.75, 0, 0.12, bevel=0.09)       # arms
        for fy in (-0.24, 0.24):
            p.cyl(0.03, 0.12, s * 0.64, fy, 0, r2=0.02, mat='i')    # feet
    p.box(0.32, 0.12, 0.26, -0.38, 0.1, 0.44, bevel=0.06, rx=-12)   # pillows
    p.box(0.32, 0.12, 0.26, 0.38, 0.1, 0.44, bevel=0.06, rx=-12, rz=6)
    return p


@model
def armchair():
    p = Piece('armchair')
    p.box(0.72, 0.64, 0.2, 0, 0, 0.12, bevel=0.06)
    p.box(0.54, 0.5, 0.14, 0, -0.04, 0.32, bevel=0.06)
    p.box(0.72, 0.18, 0.46, 0, 0.23, 0.32, bevel=0.08)
    for s in (-1, 1):
        p.box(0.16, 0.64, 0.34, s * 0.36, 0, 0.12, bevel=0.07)
        for fy in (-0.24, 0.24):
            p.cyl(0.03, 0.12, s * 0.3, fy, 0, r2=0.02, mat='i')
    return p


@model
def coffee_table():
    p = Piece('coffee_table')
    p.box(0.9, 0.48, 0.05, 0, 0, 0.33, bevel=0.02, seg=2)
    for sx in (-0.38, 0.38):
        for sy in (-0.18, 0.18):
            p.cyl(0.022, 0.33, sx, sy, 0, r2=0.016, ry=8 * (1 if sx > 0 else -1))
    return p


@model
def rug():
    p = Piece('rug')
    p.cyl(0.9, 0.012, 0, 0, 0, seg=48)
    p.cyl(0.74, 0.004, 0, 0, 0.012, seg=48)   # inner border line
    m = p
    return m


@model
def floor_lamp():
    p = Piece('floor_lamp')
    p.cyl(0.16, 0.03, 0, 0, 0, seg=24)
    p.tube([(0, 0, 0.03), (0, 0, 1.15), (0.12, 0, 1.32), (0.26, 0, 1.3)], 0.016)
    p.cyl(0.13, 0.16, 0.3, 0, 1.1, r2=0.06, seg=24)
    return p


@model
def table_lamp():
    p = Piece('table_lamp')
    p.lathe([(0, 0), (0.07, 0), (0.08, 0.02), (0.05, 0.06), (0.06, 0.16), (0.02, 0.2), (0.012, 0.2), (0.012, 0.24), (0, 0.24)])
    p.cyl(0.13, 0.14, 0, 0, 0.22, r2=0.08, seg=24, caps=True)
    return p


@model
def plant():
    p = Piece('plant')
    p.lathe([(0, 0), (0.11, 0), (0.15, 0.24), (0.165, 0.26), (0.165, 0.29), (0, 0.29)])
    leaves = [(-25, 55, 0.62), (20, 40, 0.7), (60, 50, 0.52), (-65, 35, 0.5), (0, 15, 0.82), (140, 45, 0.58), (-130, 50, 0.6)]
    for rz, tilt, ln in leaves:
        a = math.radians(rz)
        t = math.radians(tilt)
        bx, by = math.sin(a), -math.cos(a)
        tip = (bx * math.sin(t) * ln, by * math.sin(t) * ln, 0.29 + math.cos(t) * ln)
        mid = (tip[0] * 0.55, tip[1] * 0.55, 0.29 + (tip[2] - 0.29) * 0.6)
        p.tube([(0, 0, 0.27), mid], 0.008)
        p.sphere(0.16, tip[0] * 0.8, tip[1] * 0.8, 0.29 + (tip[2] - 0.29) * 0.85, sx=0.55, sy=0.18, sz=1.0, seg=16)
    return p


@model
def small_plant():
    p = Piece('small_plant')
    p.lathe([(0, 0), (0.06, 0), (0.075, 0.11), (0, 0.11)])
    for i in range(5):
        a = i * 72
        p.sphere(0.05, 0.04 * math.sin(math.radians(a)), 0.04 * math.cos(math.radians(a)), 0.16, sx=0.6, sy=0.6, sz=1.2, seg=12)
    return p


@model
def wall_shelf():
    p = Piece('wall_shelf')
    p.box(0.9, 0.18, 0.04, 0, -0.09, 0)
    for s in (-0.32, 0.32):
        p.box(0.03, 0.12, 0.1, s, -0.06, -0.1)
    x = -0.38
    for w, h in ((0.05, 0.22), (0.04, 0.18), (0.06, 0.24), (0.04, 0.2)):
        p.box(w, 0.14, h, x, -0.09, 0.04)
        x += w + 0.005
    p.lathe([(0, 0), (0.05, 0), (0.06, 0.12), (0, 0.12)], x=0.26, y=-0.09, z=0.04)
    return p


@model
def window():
    p = Piece('window')
    w, h = 0.9, 1.0
    t = 0.06
    p.box(w + 0.1, 0.16, 0.05, 0, -0.08, -0.05)              # sill
    p.box(w, 0.06, t, 0, -0.03, 0)
    p.box(w, 0.06, t, 0, -0.03, h - t)
    p.box(t, 0.06, h, -w / 2 + t / 2, -0.03, 0)
    p.box(t, 0.06, h, w / 2 - t / 2, -0.03, 0)
    p.box(0.035, 0.05, h - 2 * t, 0, -0.025, t)               # mullions
    p.box(w - 2 * t, 0.05, 0.035, 0, -0.025, h / 2)
    p.box(w - 2 * t, 0.01, h - 2 * t, 0, -0.005, t)           # glass (flat, no fill line)
    return p


@model
def painting():
    p = Piece('painting')
    p.box(0.56, 0.04, 0.42, 0, -0.02, 0)
    p.box(0.44, 0.02, 0.3, 0, -0.045, 0.06)
    p.prism([(-0.16, 0.08), (-0.04, 0.24), (0.04, 0.14), (0.1, 0.2), (0.17, 0.08)], 0.012, y=-0.06)
    p.sphere(0.035, 0.12, -0.06, 0.28, sy=0.3)
    return p


@model
def tv_stand():
    p = Piece('tv_stand')
    p.box(1.1, 0.36, 0.38, 0, 0, 0.06)
    for s in (-0.5, 0.5):
        p.cyl(0.025, 0.06, s, 0, 0, mat='i')
    p.box(0.5, 0.02, 0.24, -0.25, -0.18, 0.1)                # doors
    p.box(0.5, 0.02, 0.24, 0.25, -0.18, 0.1)
    p.box(0.2, 0.12, 0.03, 0, 0, 0.44)                       # tv foot
    p.box(0.04, 0.04, 0.1, 0, 0.02, 0.46)
    p.box(0.96, 0.05, 0.56, 0, 0.02, 0.54, bevel=0.015, seg=2)
    p.box(0.88, 0.01, 0.48, 0, -0.005, 0.58)       # dark screen
    return p


@model
def bookcase():
    p = Piece('bookcase')
    w, d, h = 0.8, 0.3, 1.3
    p.box(w, d, 0.04, 0, 0, 0)
    p.box(w, d, 0.04, 0, 0, h - 0.04)
    p.box(0.04, d, h, -w / 2 + 0.02, 0, 0)
    p.box(0.04, d, h, w / 2 - 0.02, 0, 0)
    p.box(w, 0.02, h, 0, d / 2 - 0.01, 0)
    import random
    rnd = random.Random(4)
    for i, z in enumerate((0.04, 0.34, 0.66, 0.98)):
        if i:
            p.box(w - 0.08, d - 0.02, 0.03, 0, 0, z - 0.03)
        x = -w / 2 + 0.06
        while x < w / 2 - 0.12:
            bw = rnd.uniform(0.035, 0.06)
            bh = rnd.uniform(0.18, 0.26)
            if rnd.random() < 0.15:
                x += 0.08
                continue
            p.box(bw, d - 0.08, bh, x + bw / 2, 0, z, rx=0)
            x += bw + 0.006
    return p


# ------------------------------------------------------------------ bedroom
@model
def bed():
    p = Piece('bed')
    p.box(1.1, 1.9, 0.3, 0, 0, 0.1)                          # frame
    for sx in (-0.5, 0.5):
        for sy in (-0.88, 0.88):
            p.box(0.06, 0.06, 0.1, sx, sy, 0, mat='i')
    p.box(1.12, 0.08, 0.86, 0, 0.95, 0, bevel=0.035)         # headboard
    p.box(1.06, 1.84, 0.14, 0, 0, 0.4, bevel=0.05)           # mattress
    p.box(1.14, 1.3, 0.1, 0, -0.32, 0.47, bevel=0.05)        # duvet
    p.box(1.16, 0.2, 0.12, 0, 0.26, 0.48, bevel=0.06)        # duvet fold
    p.box(0.42, 0.26, 0.14, -0.26, 0.72, 0.54, bevel=0.07, rx=-15)
    p.box(0.42, 0.26, 0.14, 0.26, 0.72, 0.54, bevel=0.07, rx=-15)
    return p


@model
def nightstand():
    p = Piece('nightstand')
    p.box(0.42, 0.36, 0.44, 0, 0, 0.06, bevel=0.015, seg=2)
    for sx in (-0.17, 0.17):
        p.cyl(0.02, 0.06, sx, -0.12, 0, mat='i')
        p.cyl(0.02, 0.06, sx, 0.12, 0, mat='i')
    p.box(0.36, 0.02, 0.16, 0, -0.18, 0.3)
    p.sphere(0.018, 0, -0.2, 0.38)
    return p


@model
def wardrobe():
    p = Piece('wardrobe')
    p.box(0.9, 0.5, 1.6, 0, 0, 0.06)
    p.box(0.9, 0.5, 0.06, 0, 0, 1.66)
    for sx in (-0.4, 0.4):
        p.cyl(0.025, 0.06, sx, 0, 0, mat='i')
    p.box(0.43, 0.02, 1.5, -0.225, -0.25, 0.1)
    p.box(0.43, 0.02, 1.5, 0.225, -0.25, 0.1)
    for sx in (-0.05, 0.05):
        p.box(0.02, 0.03, 0.2, sx, -0.27, 0.8)
    return p


@model
def wall_clock():
    p = Piece('wall_clock')
    p.cyl(0.18, 0.04, 0, -0.02, 0, rx=90, seg=40)
    p.cyl(0.15, 0.01, 0, -0.045, 0, rx=90, seg=40)
    p.box(0.015, 0.01, 0.11, 0, -0.055, -0.0, mat='i')
    p.box(0.08, 0.01, 0.015, 0.035, -0.055, -0.0075, mat='i')
    return p


@model
def mug():
    p = Piece('mug')
    p.lathe([(0, 0), (0.045, 0), (0.047, 0.11), (0.04, 0.11), (0.04, 0.095), (0, 0.095)])
    p.torus(0.03, 0.009, 0.05, 0, 0.055, rx=90, seg=16, seg2=8)
    return p


@model
def book_stack():
    p = Piece('book_stack')
    p.box(0.26, 0.18, 0.05, 0, 0, 0, bevel=0.005, seg=1)
    p.box(0.22, 0.16, 0.045, 0.01, 0, 0.05, rz=8)
    p.box(0.24, 0.17, 0.04, -0.01, 0, 0.095, rz=-5)
    return p


# ------------------------------------------------------------------ kitchen
@model
def kitchen_counter():
    p = Piece('kitchen_counter')
    w = 2.2
    p.box(w, 0.6, 0.8, 0, 0, 0.06)
    p.box(w + 0.04, 0.64, 0.05, 0, -0.01, 0.86)
    p.box(w, 0.56, 0.06, 0, 0.02, 0, mat='i')                # kick plate
    n = 4
    for i in range(n):
        x = -w / 2 + w / n * (i + 0.5)
        p.box(w / n - 0.03, 0.02, 0.66, x, -0.3, 0.12)
        p.box(0.12, 0.025, 0.02, x, -0.32, 0.68)
    p.box(0.5, 0.42, 0.012, -0.5, -0.02, 0.91, mat='i')     # sink
    p.tube([(-0.5, 0.18, 0.91), (-0.5, 0.18, 1.12), (-0.5, 0.04, 1.12), (-0.5, 0.02, 1.06)], 0.014)
    for x in (0.45, 0.75):                                    # hob rings
        p.torus(0.08, 0.012, x, -0.08, 0.915, seg=24, seg2=6, mat='i')
    return p


@model
def upper_cabinets():
    p = Piece('upper_cabinets')
    w = 1.6
    p.box(w, 0.34, 0.6, 0, -0.17, 0)
    for i in range(3):
        x = -w / 2 + w / 3 * (i + 0.5)
        p.box(w / 3 - 0.03, 0.02, 0.54, x, -0.345, 0.03)
        p.box(0.02, 0.025, 0.1, x + (0.18 if i < 2 else -0.18), -0.36, 0.06)
    return p


@model
def fridge():
    p = Piece('fridge')
    p.box(0.7, 0.66, 1.7, 0, 0, 0.02, bevel=0.04, seg=3)
    p.box(0.66, 0.02, 0.5, 0, -0.335, 1.18)
    p.box(0.66, 0.02, 1.08, 0, -0.335, 0.06)
    p.box(0.03, 0.04, 0.32, 0.27, -0.36, 1.25)
    p.box(0.03, 0.04, 0.4, 0.27, -0.36, 0.6)
    return p


@model
def stool():
    p = Piece('stool')
    p.cyl(0.17, 0.05, 0, 0, 0.62, seg=28)
    for a in (45, 135, 225, 315):
        r = math.radians(a)
        p.tube([(math.cos(r) * 0.12, math.sin(r) * 0.12, 0.62), (math.cos(r) * 0.2, math.sin(r) * 0.2, 0)], 0.016)
    p.torus(0.155, 0.01, 0, 0, 0.22, seg=24, seg2=6)
    return p


@model
def dining_table():
    p = Piece('dining_table')
    p.box(1.2, 0.75, 0.05, 0, 0, 0.66, bevel=0.012, seg=2)
    for sx in (-0.52, 0.52):
        for sy in (-0.3, 0.3):
            p.box(0.06, 0.06, 0.66, sx, sy, 0)
    return p


@model
def dining_chair():
    p = Piece('dining_chair')
    p.box(0.44, 0.44, 0.05, 0, 0, 0.42)
    for sx in (-0.19, 0.19):
        for sy in (-0.19, 0.19):
            p.box(0.04, 0.04, 0.42, sx, sy, 0)
        p.box(0.04, 0.04, 0.5, sx, 0.2, 0.47)
    p.box(0.42, 0.04, 0.18, 0, 0.2, 0.74, bevel=0.015, seg=2)
    return p


# ------------------------------------------------------------------ bathroom
@model
def bathtub():
    p = Piece('bathtub')
    p.box(1.5, 0.72, 0.52, 0, 0, 0.08, bevel=0.12, seg=4)
    p.box(1.3, 0.54, 0.05, 0, 0, 0.57, bevel=0.1, seg=3, mat='i')
    for sx in (-0.6, 0.6):
        for sy in (-0.26, 0.26):
            p.sphere(0.06, sx, sy, 0.05)
    p.tube([(0.66, 0.3, 0.6), (0.66, 0.3, 0.78), (0.6, 0.3, 0.8), (0.56, 0.3, 0.74)], 0.014)
    return p


@model
def toilet():
    p = Piece('toilet')
    p.lathe([(0, 0), (0.13, 0), (0.12, 0.2), (0.19, 0.34), (0.2, 0.4), (0, 0.4)])
    p.box(0.42, 0.18, 0.4, 0, 0.2, 0.36, bevel=0.03, seg=3)
    p.box(0.44, 0.2, 0.04, 0, 0.2, 0.76, bevel=0.01, seg=1)
    p.cyl(0.2, 0.025, 0, 0, 0.4, seg=32)
    return p


@model
def sink_vanity():
    p = Piece('sink_vanity')
    p.box(0.7, 0.46, 0.7, 0, 0, 0.1)
    p.box(0.33, 0.02, 0.56, -0.17, -0.23, 0.17)
    p.box(0.33, 0.02, 0.56, 0.17, -0.23, 0.17)
    p.box(0.74, 0.5, 0.05, 0, 0, 0.8)
    p.cyl(0.18, 0.012, 0, -0.02, 0.85, seg=32, mat='i')
    p.tube([(0, 0.18, 0.85), (0, 0.18, 1.02), (0, 0.06, 1.02), (0, 0.04, 0.97)], 0.014)
    return p


@model
def mirror():
    p = Piece('mirror')
    p.cyl(0.3, 0.03, 0, -0.015, 0.3, rx=90, seg=40)
    p.cyl(0.26, 0.01, 0, -0.035, 0.3, rx=90, seg=40)
    return p


@model
def towel_rail():
    p = Piece('towel_rail')
    p.tube([(-0.3, -0.04, 0), (-0.3, -0.08, 0), (0.3, -0.08, 0), (0.3, -0.04, 0)], 0.012)
    p.box(0.36, 0.04, 0.5, 0, -0.1, -0.5, bevel=0.015, seg=2)
    p.box(0.38, 0.06, 0.06, 0, -0.1, -0.03, bevel=0.025, seg=3)
    return p


# ------------------------------------------------------------------ office / studio / school / meeting
@model
def desk():
    p = Piece('desk')
    p.box(1.3, 0.66, 0.05, 0, 0, 0.7)
    p.box(0.42, 0.62, 0.7, 0.42, 0, 0)                       # drawer pedestal
    for z in (0.08, 0.3, 0.5):
        p.box(0.38, 0.02, 0.16, 0.42, -0.31, z)
    for sy in (-0.28, 0.28):
        p.box(0.05, 0.05, 0.7, -0.6, sy, 0)
    return p


@model
def swivel_chair():
    p = Piece('swivel_chair')
    for i in range(5):
        a = math.radians(i * 72 + 90)
        p.tube([(0, 0, 0.07), (math.cos(a) * 0.28, math.sin(a) * 0.28, 0.06)], 0.018)
        p.sphere(0.035, math.cos(a) * 0.28, math.sin(a) * 0.28, 0.035, mat='i')
    p.cyl(0.025, 0.36, 0, 0, 0.06)
    p.box(0.5, 0.48, 0.08, 0, 0, 0.42, bevel=0.035, seg=3)
    p.tube([(0, 0.2, 0.46), (0, 0.27, 0.6)], 0.02)
    p.box(0.48, 0.08, 0.5, 0, 0.27, 0.56, bevel=0.035, seg=3, rx=-8)
    return p


@model
def monitor():
    p = Piece('monitor')
    p.box(0.22, 0.16, 0.02, 0, 0.02, 0)
    p.box(0.04, 0.03, 0.18, 0, 0.05, 0.02)
    p.box(0.62, 0.04, 0.38, 0, 0.02, 0.16, bevel=0.01, seg=2)
    p.box(0.56, 0.01, 0.32, 0, -0.002, 0.19)
    return p


@model
def laptop():
    p = Piece('laptop')
    p.box(0.36, 0.25, 0.02, 0, 0, 0)
    p.box(0.36, 0.015, 0.24, 0, 0.125, 0.015, rx=-14)
    p.box(0.3, 0.12, 0.004, 0, -0.03, 0.02, mat='i')
    return p


@model
def filing_cabinet():
    p = Piece('filing_cabinet')
    p.box(0.46, 0.56, 0.86, 0, 0, 0)
    for z in (0.04, 0.32, 0.6):
        p.box(0.42, 0.02, 0.24, 0, -0.28, z)
        p.box(0.12, 0.03, 0.025, 0, -0.3, z + 0.17)
    return p


@model
def cubicle_partition():
    p = Piece('cubicle_partition')
    p.box(2.0, 0.07, 1.2, 0, 0, 0.0, bevel=0.03, seg=3)
    p.box(2.04, 0.09, 0.05, 0, 0, 1.2)
    p.box(0.5, 0.01, 0.36, -0.45, -0.04, 0.72)               # pinned notes
    p.box(0.14, 0.01, 0.14, 0.25, -0.04, 0.84, rz=0, rx=0)
    p.box(0.12, 0.01, 0.12, 0.45, -0.04, 0.7)
    return p


@model
def pinboard():
    p = Piece('pinboard')
    p.box(0.8, 0.04, 0.56, 0, -0.02, 0)
    p.box(0.16, 0.01, 0.18, -0.22, -0.045, 0.28, rz=0)
    p.box(0.2, 0.01, 0.14, 0.05, -0.045, 0.32)
    p.box(0.14, 0.01, 0.16, 0.25, -0.045, 0.12)
    p.box(0.22, 0.01, 0.12, -0.15, -0.045, 0.06)
    return p


@model
def school_board():
    p = Piece('school_board')
    p.box(1.8, 0.05, 0.9, 0, -0.025, 0)
    p.box(1.68, 0.01, 0.78, 0, -0.055, 0.06)
    p.box(1.9, 0.12, 0.04, 0, -0.06, -0.04)
    return p


@model
def school_desk():
    p = Piece('school_desk')
    p.box(0.7, 0.5, 0.04, 0, 0, 0.64, rx=-4)
    p.box(0.66, 0.46, 0.1, 0, 0, 0.52)
    for sx in (-0.3, 0.3):
        p.tube([(sx, -0.2, 0), (sx, -0.2, 0.52)], 0.018)
        p.tube([(sx, 0.2, 0), (sx, 0.2, 0.52)], 0.018)
    return p


@model
def school_chair():
    p = Piece('school_chair')
    p.box(0.4, 0.38, 0.04, 0, 0, 0.4, bevel=0.015, seg=2)
    p.box(0.4, 0.04, 0.22, 0, 0.19, 0.6, bevel=0.015, seg=2, rx=-8)
    for sx in (-0.17, 0.17):
        p.tube([(sx, -0.16, 0), (sx, -0.16, 0.4)], 0.014)
        p.tube([(sx, 0.17, 0), (sx, 0.17, 0.6)], 0.014)
    return p


@model
def whiteboard_stand():
    p = Piece('whiteboard_stand')
    p.box(1.1, 0.04, 0.72, 0, 0, 0.66, bevel=0.012, seg=2)
    for sx in (-0.52, 0.52):
        p.tube([(sx, 0, 0.06), (sx, 0, 1.4)], 0.018)
        p.tube([(sx, -0.22, 0.03), (sx, 0.22, 0.03)], 0.018)
    p.box(1.0, 0.07, 0.03, 0, -0.04, 0.64)
    return p


@model
def wall_display():
    p = Piece('wall_display')
    p.box(1.2, 0.05, 0.7, 0, -0.025, 0, bevel=0.01, seg=2)
    p.box(1.12, 0.01, 0.62, 0, -0.052, 0.04)
    return p


@model
def conference_table():
    p = Piece('conference_table')
    p.box(2.2, 1.0, 0.06, 0, 0, 0.64, bevel=0.3, seg=6)
    p.box(0.3, 0.5, 0.64, -0.6, 0, 0)
    p.box(0.3, 0.5, 0.64, 0.6, 0, 0)
    return p


# ------------------------------------------------------------------ cafe / restaurant
@model
def cafe_counter():
    p = Piece('cafe_counter')
    p.box(2.0, 0.6, 0.94, 0, 0, 0)
    p.box(2.06, 0.66, 0.05, 0, 0, 0.94)
    for i in range(6):
        p.box(0.02, 0.02, 0.86, -0.85 + i * 0.34, -0.3, 0.04)  # panelling
    return p


@model
def pastry_display():
    p = Piece('pastry_display')
    p.box(0.7, 0.4, 0.1, 0, 0, 0)
    p.box(0.7, 0.4, 0.02, 0, 0, 0.36)
    p.prism([(-0.35, 0.1), (0.35, 0.1), (0.35, 0.36), (-0.35, 0.36)], 0.02, y=-0.19)
    for x in (-0.2, 0, 0.2):
        p.sphere(0.06, x, 0, 0.15, sz=0.6)
    return p


@model
def coffee_machine():
    p = Piece('coffee_machine')
    p.box(0.46, 0.36, 0.4, 0, 0, 0, bevel=0.03, seg=3)
    p.box(0.36, 0.02, 0.14, 0, -0.18, 0.22, mat='i')
    p.cyl(0.03, 0.06, -0.1, -0.2, 0.12)
    p.cyl(0.03, 0.06, 0.1, -0.2, 0.12)
    p.lathe([(0, 0), (0.035, 0), (0.037, 0.07), (0, 0.07)], x=-0.1, y=-0.2, z=0.02)
    return p


@model
def pendant_lamp():
    p = Piece('pendant_lamp')
    p.tube([(0, 0, 0.18), (0, 0, 2.6)], 0.006)
    p.lathe([(0.2, 0), (0.18, 0.06), (0.08, 0.16), (0.03, 0.2), (0, 0.2)], seg=32)
    p.sphere(0.05, 0, 0, 0.02, mat='m')
    return p


@model
def cafe_table():
    p = Piece('cafe_table')
    p.cyl(0.32, 0.04, 0, 0, 0.7, seg=40)
    p.cyl(0.03, 0.7, 0, 0, 0)
    p.cyl(0.2, 0.03, 0, 0, 0, seg=32)
    return p


@model
def cafe_chair():
    p = Piece('cafe_chair')
    p.cyl(0.21, 0.04, 0, 0, 0.44, seg=32)
    for a in (40, 140, 220, 320):
        r = math.radians(a)
        p.tube([(math.cos(r) * 0.14, math.sin(r) * 0.14, 0.44), (math.cos(r) * 0.2, math.sin(r) * 0.2, 0)], 0.014)
    p.tube([(-0.17, 0.12, 0.47), (-0.18, 0.2, 0.8), (0.18, 0.2, 0.8), (0.17, 0.12, 0.47)], 0.016)
    return p


@model
def menu_board():
    p = Piece('menu_board')
    p.box(1.0, 0.04, 0.6, 0, -0.02, 0)
    p.box(0.92, 0.01, 0.52, 0, -0.045, 0.04)
    return p


@model
def host_stand():
    p = Piece('host_stand')
    p.prism([(-0.25, 0), (0.25, 0), (0.22, 1.0), (-0.22, 1.0)], 0.4)
    p.box(0.56, 0.44, 0.04, 0, -0.02, 1.0, rx=-10)
    return p


# ------------------------------------------------------------------ gym
@model
def treadmill():
    p = Piece('treadmill')
    p.box(0.7, 1.5, 0.16, 0, 0, 0, bevel=0.04, seg=3)
    p.box(0.52, 1.36, 0.01, 0, 0, 0.16, mat='i')
    for sx in (-0.3, 0.3):
        p.tube([(sx, -0.62, 0.12), (sx, -0.7, 1.15)], 0.025)
    p.box(0.7, 0.2, 0.2, 0, -0.72, 1.08, bevel=0.04, seg=3, rx=20)
    p.tube([(-0.32, -0.66, 1.0), (-0.32, -0.3, 0.98)], 0.018)
    p.tube([(0.32, -0.66, 1.0), (0.32, -0.3, 0.98)], 0.018)
    return p


@model
def dumbbell_rack():
    p = Piece('dumbbell_rack')
    for sx in (-0.6, 0.6):
        p.box(0.06, 0.4, 0.7, sx, 0, 0)
    for z, y in ((0.32, -0.06), (0.62, 0.06)):
        p.box(1.26, 0.18, 0.03, 0, y, z, rx=-12)
        for i in range(4):
            x = -0.42 + i * 0.28
            p.cyl(0.012, 0.18, x - 0.09, y, z + 0.06, ry=90)
            p.cyl(0.05, 0.05, x - 0.09, y, z + 0.06, ry=90, mat='i')
            p.cyl(0.05, 0.05, x + 0.04, y, z + 0.06, ry=90, mat='i')
    return p


@model
def workout_bench():
    p = Piece('workout_bench')
    p.box(0.32, 1.1, 0.1, 0, 0, 0.36, bevel=0.04, seg=3)
    for sy in (-0.42, 0.42):
        p.box(0.06, 0.06, 0.36, 0, sy, 0)
        p.box(0.42, 0.08, 0.04, 0, sy, 0)
    return p


@model
def water_dispenser():
    p = Piece('water_dispenser')
    p.box(0.34, 0.34, 0.9, 0, 0, 0, bevel=0.02, seg=2)
    p.box(0.2, 0.02, 0.14, 0, -0.17, 0.56, mat='i')
    p.lathe([(0, 0.9), (0.1, 0.9), (0.15, 0.96), (0.15, 1.28), (0.06, 1.34), (0.03, 1.34), (0, 1.34)])
    return p


@model
def yoga_mat():
    p = Piece('yoga_mat')
    p.box(0.6, 1.5, 0.012, 0, 0, 0)
    p.cyl(0.08, 0.6, 0, 0.78, 0.08, ry=90, seg=24)
    return p


# ------------------------------------------------------------------ grocery
@model
def grocery_shelf():
    p = Piece('grocery_shelf')
    w = 1.6
    p.box(w, 0.5, 0.1, 0, 0, 0)
    p.box(w, 0.06, 1.5, 0, 0.22, 0)
    for z in (0.1, 0.5, 0.9, 1.3):
        p.box(w, 0.46, 0.03, 0, 0, z)
    import random
    rnd = random.Random(7)
    for z in (0.13, 0.53, 0.93):
        x = -w / 2 + 0.08
        while x < w / 2 - 0.1:
            kind = rnd.choice(('box', 'can', 'bottle'))
            if kind == 'box':
                bw = rnd.uniform(0.1, 0.16)
                p.box(bw, 0.18, rnd.uniform(0.2, 0.3), x + bw / 2, -0.08, z)
                x += bw + 0.02
            elif kind == 'can':
                p.cyl(0.045, 0.12, x + 0.045, -0.12, z, seg=14)
                p.cyl(0.045, 0.12, x + 0.045, -0.12, z + 0.12, seg=14)
                x += 0.11
            else:
                p.lathe([(0, 0), (0.04, 0), (0.04, 0.16), (0.015, 0.22), (0.015, 0.26), (0, 0.26)], x=x + 0.04, y=-0.1, z=z, seg=14)
                x += 0.1
    return p


@model
def produce_bin():
    p = Piece('produce_bin')
    p.prism([(-0.5, 0), (0.5, 0), (0.55, 0.5), (-0.55, 0.5)], 0.7)
    import random
    rnd = random.Random(3)
    for i in range(14):
        p.sphere(0.07, rnd.uniform(-0.42, 0.42), rnd.uniform(-0.25, 0.25), 0.5 + rnd.uniform(0, 0.06), seg=12)
    return p


@model
def checkout_counter():
    p = Piece('checkout_counter')
    p.box(1.4, 0.6, 0.86, 0, 0, 0)
    p.box(1.0, 0.5, 0.01, -0.15, 0, 0.86, mat='i')           # belt
    p.box(0.34, 0.3, 0.2, 0.48, 0.02, 0.86, bevel=0.02, seg=2)
    p.box(0.28, 0.04, 0.2, 0.48, 0.1, 1.06, rx=-20)
    return p


@model
def shopping_cart():
    p = Piece('shopping_cart')
    p.prism([(-0.28, 0.42), (0.32, 0.42), (0.36, 0.86), (-0.36, 0.86)], 0.46)
    p.box(0.72, 0.42, 0.01, 0, 0, 0.42)
    for sx, sy in ((-0.24, -0.16), (-0.24, 0.16), (0.24, -0.16), (0.24, 0.16)):
        p.tube([(sx, sy, 0.42), (sx, sy, 0.08)], 0.012)
        p.cyl(0.06, 0.03, sx, sy, 0.06, rx=90, mat='i')
    p.tube([(-0.36, -0.22, 0.86), (-0.46, -0.22, 0.98), (-0.46, 0.22, 0.98), (-0.36, 0.22, 0.86)], 0.016)
    return p


# ------------------------------------------------------------------ airport / station
@model
def terminal_window():
    p = Piece('terminal_window')
    w, h = 2.6, 1.3
    p.box(w, 0.08, 0.06, 0, -0.04, 0)
    p.box(w, 0.08, 0.06, 0, -0.04, h)
    for i in range(5):
        p.box(0.06, 0.08, h, -w / 2 + i * w / 4, -0.04, 0)
    # a plane far outside, flat on the glass plane
    p.prism([(-0.5, 0.55), (0.45, 0.55), (0.6, 0.62), (0.45, 0.7), (-0.5, 0.68), (-0.62, 0.86), (-0.68, 0.86), (-0.62, 0.62)], 0.01, y=0.02)
    p.prism([(-0.1, 0.62), (0.15, 0.62), (-0.2, 0.4), (-0.3, 0.4)], 0.01, y=0.01)
    return p


@model
def waiting_seats():
    p = Piece('waiting_seats')
    p.box(1.6, 0.08, 0.04, 0, 0, 0.36)
    for sx in (-0.6, 0.6):
        p.tube([(sx, 0, 0.36), (sx, 0, 0.02)], 0.022)
        p.box(0.08, 0.5, 0.03, sx, 0, 0)
    for i in range(3):
        x = -0.52 + i * 0.52
        p.box(0.46, 0.46, 0.08, x, 0, 0.4, bevel=0.035, seg=3)
        p.box(0.46, 0.08, 0.44, x, 0.22, 0.48, bevel=0.035, seg=3, rx=-8)
    return p


@model
def checkin_kiosk():
    p = Piece('checkin_kiosk')
    p.prism([(-0.26, 0), (0.26, 0), (0.24, 1.0), (0.3, 1.36), (-0.3, 1.36), (-0.24, 1.0)], 0.36)
    p.box(0.44, 0.02, 0.3, 0, -0.18, 1.02, rx=-15)
    p.box(0.2, 0.03, 0.02, 0, -0.19, 0.72, mat='i')
    p.box(0.64, 0.4, 0.04, 0, 0, 0)
    return p


@model
def suitcase():
    p = Piece('suitcase')
    p.box(0.42, 0.24, 0.58, 0, 0, 0.06, bevel=0.04, seg=3)
    for sx in (-0.12, 0.12):
        p.tube([(sx, 0.08, 0.64), (sx, 0.08, 0.86)], 0.01)
        p.cyl(0.03, 0.03, sx + 0.04 * (1 if sx > 0 else -1), 0.0, 0.03, ry=90, mat='i')
    p.tube([(-0.12, 0.08, 0.86), (0.12, 0.08, 0.86)], 0.014)
    for z in (0.2, 0.42):
        p.box(0.43, 0.25, 0.01, 0, 0, z)
    return p


@model
def train_carriage():
    p = Piece('train_carriage')
    p.box(6.0, 0.9, 1.6, 0, 0, 0.3, bevel=0.18, seg=4)
    p.box(6.0, 0.92, 0.1, 0, 0, 0.62)
    for i in range(6):
        p.box(0.6, 0.02, 0.42, -2.5 + i * 1.0, -0.46, 1.05, bevel=0.06, seg=3)
    p.box(0.7, 0.02, 1.15, 0.0, -0.462, 0.32)                # door
    for x in (-2.2, -1.6, 1.6, 2.2):
        p.cyl(0.22, 0.12, x, -0.38, 0.22, rx=90, mat='i', seg=24)
    return p


@model
def platform_bench():
    p = Piece('platform_bench')
    for z, y in ((0.42, 0), (0.6, 0.18), (0.76, 0.2)):
        p.box(1.4, 0.12 if z == 0.42 else 0.03, 0.04 if z == 0.42 else 0.1, 0, y, z)
    p.box(1.4, 0.36, 0.04, 0, -0.02, 0.42)
    for sx in (-0.58, 0.58):
        p.prism([(-0.2, 0), (0.2, 0), (0.2, 0.42), (0.22, 0.86), (0.18, 0.86), (0.14, 0.42), (-0.2, 0.42)], 0.04, x=sx, rz=90)
    return p


@model
def ticket_machine():
    p = Piece('ticket_machine')
    p.box(0.56, 0.42, 1.4, 0, 0, 0, bevel=0.03, seg=2)
    p.box(0.4, 0.02, 0.3, 0, -0.21, 0.96, mat='i')
    p.box(0.3, 0.03, 0.06, 0, -0.22, 0.6)
    p.box(0.16, 0.03, 0.12, 0, -0.22, 0.32)
    return p


@model
def station_clock():
    p = Piece('station_clock')
    p.tube([(0, 0, 0), (0, 0, 1.5)], 0.035)
    p.cyl(0.12, 0.04, 0, 0, 0)
    p.cyl(0.22, 0.1, 0, 0.05, 1.68, rx=90, seg=40)
    p.cyl(0.18, 0.01, 0, -0.005, 1.68, rx=90, seg=40)
    p.box(0.012, 0.01, 0.13, 0, -0.012, 1.68, mat='i')
    p.box(0.1, 0.01, 0.012, 0.05, -0.012, 1.674, mat='i')
    return p


@model
def departure_board():
    p = Piece('departure_board')
    p.box(1.3, 0.1, 0.5, 0, -0.05, 0)
    p.box(1.22, 0.01, 0.42, 0, -0.105, 0.04)
    p.tube([(-0.5, -0.05, 0.5), (-0.5, -0.05, 1.2)], 0.012)
    p.tube([(0.5, -0.05, 0.5), (0.5, -0.05, 1.2)], 0.012)
    return p


# ------------------------------------------------------------------ outdoors
@model
def tree():
    p = Piece('tree')
    p.cyl(0.13, 1.3, 0, 0, 0, r2=0.08, seg=16)
    p.tube([(0, 0, 0.9), (0.28, 0, 1.25)], 0.04)
    for x, y, z, r in ((0, 0, 1.75, 0.55), (-0.42, 0.05, 1.5, 0.4), (0.44, -0.05, 1.45, 0.42), (0.2, 0.15, 2.1, 0.42),
                       (-0.25, -0.1, 2.05, 0.38)):
        p.sphere(r, x, y, z, seg=20)
    return p


@model
def pine_tree():
    p = Piece('pine_tree')
    p.cyl(0.08, 0.5, 0, 0, 0, seg=12)
    for i, (r, z) in enumerate(((0.7, 0.4), (0.55, 0.95), (0.4, 1.45), (0.26, 1.9))):
        p.cyl(r, 0.75 - i * 0.08, 0, 0, z, r2=0.03, seg=20)
    return p


@model
def palm_tree():
    p = Piece('palm_tree')
    pts = [(0.03 * math.sin(i / 3) + 0.06 * i * i / 64, 0, i * 0.3) for i in range(9)]
    for a, b in zip(pts, pts[1:]):
        p.cyl(0.09 - 0.004 * pts.index(a), 0.3, a[0], 0, a[2], seg=12)
    top = pts[-1]
    for k in range(6):
        ang = math.radians(k * 60)
        p.sphere(0.5, top[0] + math.cos(ang) * 0.45, math.sin(ang) * 0.45, top[2] + 0.12, sx=1.0, sy=0.28, sz=0.12, seg=16)
    for k in range(3):
        p.sphere(0.07, top[0] + 0.06 * math.cos(k * 2.1), 0.06 * math.sin(k * 2.1), top[2] - 0.05, seg=10)
    return p


@model
def bush():
    p = Piece('bush')
    for x, z, r in ((0, 0.24, 0.3), (-0.3, 0.18, 0.22), (0.3, 0.2, 0.24), (0.1, 0.4, 0.2)):
        p.sphere(r, x, 0, z, seg=16)
    return p


@model
def park_bench():
    p = Piece('park_bench')
    for i in range(3):
        p.box(1.5, 0.11, 0.04, 0, -0.14 + i * 0.13, 0.44, bevel=0.01, seg=1)
    for i in range(2):
        p.box(1.5, 0.04, 0.11, 0, 0.24, 0.6 + i * 0.16, bevel=0.01, seg=1, rx=-10)
    for sx in (-0.62, 0.62):
        p.prism([(-0.2, 0), (-0.15, 0), (-0.13, 0.4), (0.18, 0.4), (0.16, 0), (0.21, 0), (0.23, 0.44), (0.27, 0.9), (0.22, 0.9), (0.18, 0.46), (-0.2, 0.46)],
                0.05, x=sx, rz=90, mat='i')
    return p


@model
def flowers():
    p = Piece('flowers')
    import random
    rnd = random.Random(5)
    for i in range(7):
        x, y = rnd.uniform(-0.3, 0.3), rnd.uniform(-0.12, 0.12)
        h = rnd.uniform(0.18, 0.34)
        p.tube([(x, y, 0), (x + rnd.uniform(-0.03, 0.03), y, h)], 0.006)
        for k in range(5):
            a = k * 72 + rnd.uniform(0, 30)
            p.sphere(0.022, x + 0.025 * math.cos(math.radians(a)), y + 0.025 * math.sin(math.radians(a)) * 0.4, h, sy=0.5, seg=8)
        p.sphere(0.014, x, y - 0.006, h, mat='i', seg=8)
    for x in (-0.18, 0.05, 0.22):
        p.sphere(0.05, x, 0.02, 0.06, sx=0.4, sy=0.15, sz=1.2, seg=10)
    return p


@model
def stone():
    p = Piece('stone')
    p.sphere(0.22, 0, 0, 0.06, sx=1.0, sy=0.8, sz=0.55, seg=14)
    p.sphere(0.12, 0.22, -0.05, 0.03, sx=1.0, sy=0.8, sz=0.6, seg=12)
    return p


@model
def cloud():
    p = Piece('cloud')
    for x, z, r in ((0, 0.12, 0.3), (-0.34, 0.04, 0.22), (0.34, 0.05, 0.24), (0.12, 0.28, 0.2), (-0.16, 0.24, 0.18)):
        p.sphere(r, x, 0, z, sy=0.45, seg=16)
    return p


@model
def lamp_post():
    p = Piece('lamp_post')
    p.cyl(0.11, 0.18, 0, 0, 0, r2=0.07, seg=20)
    p.tube([(0, 0, 0.1), (0, 0, 2.3), (0.06, 0, 2.44), (0.32, 0, 2.48)], 0.035)
    p.cyl(0.14, 0.14, 0.38, 0, 2.3, r2=0.05, seg=20)
    return p


@model
def fence():
    p = Piece('fence')
    for i in range(9):
        x = -1.6 + i * 0.4
        p.prism([(-0.05, 0), (0.05, 0), (0.05, 0.62), (0, 0.7), (-0.05, 0.62)], 0.03, x=x)
    p.box(3.4, 0.03, 0.07, 0, 0.03, 0.18)
    p.box(3.4, 0.03, 0.07, 0, 0.03, 0.48)
    return p


@model
def trash_bin():
    p = Piece('trash_bin')
    p.lathe([(0, 0), (0.17, 0), (0.2, 0.6), (0.22, 0.62), (0.22, 0.66), (0, 0.66)])
    for z in (0.18, 0.38):
        p.torus(0.185 + z * 0.05, 0.008, 0, 0, z, seg=28, seg2=6)
    return p


@model
def fire_hydrant():
    p = Piece('fire_hydrant')
    p.lathe([(0, 0), (0.14, 0), (0.14, 0.05), (0.1, 0.06), (0.1, 0.4), (0.12, 0.42), (0.12, 0.46), (0.08, 0.52), (0.03, 0.58), (0, 0.58)])
    for s in (-1, 1):
        p.cyl(0.045, 0.08, s * 0.1, 0, 0.3, ry=90 * s)
    return p


@model
def building_row():
    p = Piece('building_row')
    x = -3.0
    import random
    rnd = random.Random(11)
    while x < 3.0:
        w = rnd.uniform(1.1, 1.6)
        h = rnd.uniform(2.6, 4.2)
        p.box(w, 1.0, h, x + w / 2, 0, 0)
        p.box(w + 0.06, 1.04, 0.1, x + w / 2, 0, h)
        cols = max(2, int(w / 0.45))
        for r in range(1, int(h / 0.8)):
            for c in range(cols):
                p.box(0.22, 0.02, 0.3, x + (c + 0.5) * w / cols, -0.5, r * 0.8 - 0.1)
        p.box(0.4, 0.02, 0.7, x + w / 2, -0.505, 0)
        x += w + 0.02
    return p


@model
def street_sign():
    p = Piece('street_sign')
    p.tube([(0, 0, 0), (0, 0, 1.5)], 0.025)
    p.box(0.5, 0.03, 0.16, 0.18, 0, 1.36)
    return p


@model
def beach_umbrella():
    p = Piece('beach_umbrella')
    p.tube([(0, 0, 0), (0.06, 0, 1.7)], 0.02)
    p.cyl(0.85, 0.3, 0.06, 0, 1.52, r2=0.03, seg=12)
    p.sphere(0.03, 0.06, 0, 1.84)
    return p


@model
def sun_lounger():
    p = Piece('sun_lounger')
    p.box(0.56, 1.2, 0.05, 0, 0.1, 0.3)
    p.box(0.56, 0.7, 0.05, 0, -0.72, 0.3, rx=38)
    for sy in (-0.3, 0.5):
        p.box(0.6, 0.05, 0.3, 0, sy, 0)
    p.box(0.58, 0.9, 0.04, 0, 0.12, 0.34, bevel=0.02, seg=2)
    return p


@model
def beach_ball():
    p = Piece('beach_ball')
    p.sphere(0.16, 0, 0, 0.16, seg=24)
    p.torus(0.16, 0.004, 0, 0, 0.16, rx=90, seg=32, seg2=4, mat='i')
    p.torus(0.16, 0.004, 0, 0, 0.16, rx=90, rz=60, seg=32, seg2=4, mat='i')
    p.torus(0.16, 0.004, 0, 0, 0.16, rx=90, rz=120, seg=32, seg2=4, mat='i')
    return p


@model
def sandcastle():
    p = Piece('sandcastle')
    p.box(0.5, 0.36, 0.16, 0, 0, 0)
    for sx in (-0.2, 0.2):
        p.cyl(0.08, 0.3, sx, 0, 0, r2=0.07, seg=16)
        p.cyl(0.08, 0.06, sx, 0, 0.3, r2=0.06, seg=16)
    p.cyl(0.1, 0.36, 0, 0.02, 0.1, r2=0.08, seg=16)
    p.tube([(0, 0.02, 0.46), (0, 0.02, 0.62)], 0.006)
    p.prism([(0, 0.62), (0.1, 0.58), (0, 0.54)], 0.005, y=0.02)
    return p


@model
def wave():
    p = Piece('wave')
    pts = []
    for i in range(41):
        x = -3 + i * 0.15
        pts.append((x, 0.02 + 0.025 * math.sin(i * 0.9)))
    outline = pts + [(3, 0), (-3, 0)]
    p.prism(outline[::-1], 0.01, rz=0)
    return p


@model
def door():
    p = Piece('door')
    w, h = 0.9, 2.02
    p.box(w + 0.14, 0.08, 0.07, 0, -0.04, h)
    p.box(0.07, 0.08, h, -w / 2 - 0.035, -0.04, 0)
    p.box(0.07, 0.08, h, w / 2 + 0.035, -0.04, 0)
    p.box(w, 0.04, h, 0, -0.02, 0)
    p.box(w - 0.24, 0.01, 0.7, 0, -0.045, 1.1)
    p.box(w - 0.24, 0.01, 0.7, 0, -0.045, 0.2)
    p.sphere(0.035, w / 2 - 0.1, -0.07, 1.0)
    return p


@model
def ceiling_light():
    p = Piece('ceiling_light')
    p.lathe([(0.0, 0), (0.22, 0), (0.2, -0.05), (0.12, -0.09), (0, -0.1)], seg=32)
    return p
