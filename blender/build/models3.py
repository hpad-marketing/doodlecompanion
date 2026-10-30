"""Asset packs (approved 2026-10-30): props, effects pieces, rides, kits and camera helpers.

Same rules as models.py: metres, z up, front faces -y, chunky shapes so one stroke weight
reads, mustard with ink only for small accents (no big black fills).

Hand props (HOLD) are sized to Bunny (his mitten is ~8 cm); everything else is scenery and
gets the room scale (rooms.WORLD) like the other sets.

A model can return (piece, parts): parts move on their own (a lid that opens, a wheel that
spins). Each part is {name, piece, pivot, kind: hinge|wheel|spin|slide, axis, amount}; the
piece is drawn in the model's space and the builder moves its origin to the pivot.
"""
import math

from kit import Piece
from models import M

M3 = {}      # every pack model
HOLD = {}    # hand props: name -> (grip kind, axis, extra) for grips.GRIPS
PACK = {}    # name -> pack id


def pack(pid, hold=None):
    def deco(fn):
        M3[fn.__name__] = fn
        PACK[fn.__name__] = pid
        if hold:
            HOLD[fn.__name__] = hold
        return fn
    return deco


def part(name, piece, pivot, kind='hinge', axis='X', amount=100.0):
    return {'name': name, 'piece': piece, 'pivot': pivot, 'kind': kind, 'axis': axis, 'amount': amount}


def _star(n, r1, r2, phase=math.pi / 2):
    return [((r1 if i % 2 == 0 else r2) * math.cos(phase + math.pi * i / n),
             (r1 if i % 2 == 0 else r2) * math.sin(phase + math.pi * i / n)) for i in range(2 * n)]


def _circle(n, r, cx=0.0, cz=0.0):
    return [(cx + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _wheel(name, r, w, x, y, z, seg=20):
    w_ = Piece(name)
    w_.cyl(r, w, x, y - w / 2, z, rx=-90, seg=seg, mat='i')
    w_.cyl(r * 0.45, w + 0.01, x, y - w / 2 - 0.005, z, rx=-90, seg=seg)
    return part(name, w_, (x, y, z), 'wheel', 'Y', r)


# ================================================================== story: reveal props
@pack('reveal')
def gift_box():
    p = Piece('gift_box')
    p.box(0.5, 0.5, 0.4, bevel=0.01, seg=1)
    p.box(0.08, 0.51, 0.401, mat='m')
    lid = Piece('gift_box_lid')
    lid.box(0.54, 0.54, 0.1, 0, 0, 0.4, bevel=0.01, seg=1)
    lid.box(0.08, 0.55, 0.101, 0, 0, 0.4)
    lid.torus(0.07, 0.022, -0.06, 0, 0.53, ry=60, seg=16, seg2=6)
    lid.torus(0.07, 0.022, 0.06, 0, 0.53, ry=-60, seg=16, seg2=6)
    return p, [part('lid', lid, (0, 0.27, 0.4), 'hinge', 'X', 110)]


@pack('reveal')
def treasure_chest():
    p = Piece('treasure_chest')
    p.box(0.7, 0.45, 0.35, bevel=0.015, seg=1)
    for x in (-0.25, 0.25):
        p.box(0.05, 0.46, 0.351, x, 0, 0)
    p.box(0.08, 0.02, 0.1, 0, -0.235, 0.26, mat='i')
    lid = Piece('treasure_chest_lid')
    lid.cyl(0.225, 0.7, -0.35, 0, 0.35, ry=90, seg=20)
    for x in (-0.25, 0.25):
        lid.cyl(0.228, 0.05, x - 0.025, 0, 0.35, ry=90, seg=20)
    return p, [part('lid', lid, (0, 0.225, 0.35), 'hinge', 'X', 100)]


@pack('reveal', hold=('pinch', 'x', ''))
def letter_envelope():
    p = Piece('letter_envelope')
    p.box(0.22, 0.012, 0.14)
    p.prism([(-0.11, 0.14), (0, 0.07), (0.11, 0.14)], 0.004, y=-0.007)
    flap = Piece('letter_envelope_flap')
    flap.prism([(-0.11, 0.14), (0, 0.06), (0.11, 0.14)], 0.004, y=-0.009)
    note = Piece('letter_envelope_note')
    note.box(0.19, 0.004, 0.12, 0, 0, 0.01)
    return p, [part('flap', flap, (0, -0.009, 0.14), 'hinge', 'X', -170),
               part('note', note, (0, 0, 0.01), 'slide', 'Z', 0.12)]


@pack('reveal')
def mystery_crate():
    p = Piece('mystery_crate')
    p.box(0.6, 0.6, 0.55, bevel=0.01, seg=1)
    for z in (0.12, 0.42):
        p.box(0.61, 0.61, 0.06, 0, 0, z)
    p.prism([(-0.06, 0.2), (-0.06, 0.24), (0.04, 0.32), (-0.02, 0.36), (-0.06, 0.33), (-0.08, 0.37), (0, 0.41),
             (0.08, 0.36), (0.02, 0.28), (0.02, 0.2)], 0.01, y=-0.305, mat='i')  # question mark
    p.box(0.04, 0.01, 0.04, -0.02, -0.305, 0.13, mat='i')
    lid = Piece('mystery_crate_lid')
    lid.box(0.64, 0.64, 0.06, 0, 0, 0.55, bevel=0.01, seg=1)
    return p, [part('lid', lid, (0, 0.32, 0.55), 'hinge', 'X', 95)]


@pack('reveal')
def stage_curtain():
    p = Piece('stage_curtain')
    p.box(3.4, 0.12, 0.25, 0, 0, 2.4)
    l, r = Piece('stage_curtain_left'), Piece('stage_curtain_right')
    for side, pc in ((-1, l), (1, r)):
        for i in range(5):
            pc.cyl(0.09, 2.4, side * (0.18 + i * 0.32), 0.05, 0, r2=0.11, seg=10)
    return p, [part('left', l, (-0.1, 0.05, 0), 'slide', 'X', -1.3), part('right', r, (0.1, 0.05, 0), 'slide', 'X', 1.3)]


@pack('reveal')
def trap_door():
    p = Piece('trap_door')
    p.box(1.0, 1.0, 0.03)
    p.box(0.8, 0.8, 0.031, mat='i')
    d = Piece('trap_door_lid')
    d.box(0.8, 0.8, 0.04, 0, 0, 0.0)
    for y in (-0.25, 0, 0.25):
        d.box(0.8, 0.02, 0.041, 0, y, 0.0, mat='i')
    d.torus(0.05, 0.012, 0, -0.32, 0.045, seg=12, seg2=6)
    return p, [part('lid', d, (0, 0.4, 0.0), 'hinge', 'X', 110)]


# ================================================================== story: explainer boards
@pack('boards')
def chalkboard():
    p = Piece('chalkboard')
    p.box(1.5, 0.05, 1.0, 0, 0, 0.8, bevel=0.01, seg=1)
    p.box(1.38, 0.02, 0.88, 0, -0.03, 0.86)
    p.box(1.4, 0.1, 0.03, 0, -0.06, 0.78)
    for x in (-0.65, 0.65):
        p.box(0.05, 0.05, 0.8, x, 0, 0)
    p['surface'] = (1.38, 0.88, 0, -0.045, 1.30)
    return p


@pack('boards')
def flip_chart():
    p = Piece('flip_chart')
    for x, ry in ((-0.3, 8), (0.3, -8)):
        p.cyl(0.02, 1.5, x, -0.1, 0, ry=ry, seg=8)
    p.cyl(0.02, 1.5, 0, 0.3, 0, rx=-14, seg=8)
    p.box(0.75, 0.04, 0.95, 0, -0.11, 0.65)
    p.box(0.8, 0.06, 0.06, 0, -0.11, 1.58)
    p['surface'] = (0.72, 0.92, 0, -0.135, 1.12)
    page = Piece('flip_chart_page')
    page.box(0.74, 0.01, 0.93, 0, -0.14, 0.66)
    return p, [part('page', page, (0, -0.14, 1.59), 'hinge', 'X', -180)]


@pack('boards', hold=('pinch', 'z', ''))
def marker():
    p = Piece('marker')
    p.cyl(0.012, 0.11)
    p.cyl(0.0125, 0.035, 0, 0, 0.11, mat='i')
    p.cyl(0.006, 0.012, 0, 0, -0.012, r2=0.012)
    return p


@pack('boards', hold=('fist', 'z', ''))
def pointer_stick():
    p = Piece('pointer_stick')
    p.cyl(0.008, 0.5, 0, 0, -0.08, r2=0.004, seg=10)
    p.cyl(0.012, 0.09, 0, 0, -0.1, seg=10)
    p.sphere(0.007, 0, 0, 0.42, mat='i', seg=8)
    return p


@pack('boards')
def sticky_notes():
    p = Piece('sticky_notes')
    for i, (x, z, rz) in enumerate(((-0.12, 0.1, 6), (0.04, 0.14, -4), (0.18, 0.06, 9), (-0.04, -0.06, -7))):
        p.box(0.12, 0.004, 0.12, x, 0, z, ry=rz)
        p.box(0.08, 0.002, 0.008, x, -0.003, z + 0.07, ry=rz, mat='i')
    p['place'] = 'wall'
    return p


# ================================================================== story: signs and placards
@pack('signs')
def stop_sign():
    p = Piece('stop_sign')
    p.cyl(0.03, 1.8, seg=10)
    p.prism([(0.3 * math.cos(math.pi / 8 + i * math.pi / 4), 1.8 + 0.3 * math.sin(math.pi / 8 + i * math.pi / 4))
             for i in range(8)], 0.03, y=-0.04)
    p.prism([(0.25 * math.cos(math.pi / 8 + i * math.pi / 4), 1.8 + 0.25 * math.sin(math.pi / 8 + i * math.pi / 4))
             for i in range(8)], 0.005, y=-0.058)
    p['text'] = ('STOP', (0, -0.065, 1.8), 0.14)
    return p


@pack('signs', hold=('fist', 'z', 'upright'))
def placard():
    p = Piece('placard')
    p.cyl(0.012, 0.42, 0, 0, -0.12, seg=10)
    p.box(0.42, 0.015, 0.28, 0, -0.02, 0.28, bevel=0.005, seg=1)
    p['text'] = ('YES!', (0, -0.03, 0.42), 0.09)
    return p


@pack('signs')
def a_frame_sign():
    p = Piece('a_frame_sign')
    p.box(0.55, 0.03, 0.85, 0, -0.14, 0, rx=-10)
    p.box(0.55, 0.03, 0.85, 0, 0.14, 0, rx=10)
    p.box(0.45, 0.005, 0.6, 0, -0.17, 0.15, rx=-10, mat='m')
    p['text'] = ('OPEN', (0, -0.21, 0.52), 0.1)
    return p


@pack('signs')
def hanging_sign():
    p = Piece('hanging_sign')
    p.box(0.6, 0.04, 0.04, 0.25, 0, 0)
    p.box(0.04, 0.04, 0.12, -0.03, 0, -0.08)
    for x in (0.12, 0.48):
        p.tube([(x, 0, 0), (x, 0, -0.12)], 0.005, mat='i')
    p.box(0.46, 0.03, 0.26, 0.3, 0, -0.38, bevel=0.01, seg=1)
    p['text'] = ('CAFE', (0.3, -0.02, -0.25), 0.08)
    p['place'] = 'wall'
    return p


# ================================================================== story: speech bubbles (3D)
def _bubble_outline(kind):
    if kind == 'speech':
        pts = [(0.42 * math.cos(a), 0.26 * math.sin(a)) for a in [2 * math.pi * i / 36 for i in range(36)]]
        k = 30  # tail at lower left
        pts = pts[:k] + [(-0.22, -0.2), (-0.34, -0.42), (-0.06, -0.25)] + pts[k + 2:]
        return pts
    if kind == 'shout':
        return [((0.46 if i % 2 == 0 else 0.34) * math.cos(2 * math.pi * i / 22), (0.32 if i % 2 == 0 else 0.22) *
                 math.sin(2 * math.pi * i / 22)) for i in range(22)]
    if kind == 'whisper':
        return [(0.38 * math.cos(2 * math.pi * i / 32), 0.22 * math.sin(2 * math.pi * i / 32)) for i in range(32)]
    return [(0.4 * math.cos(2 * math.pi * i / 32), 0.26 * math.sin(2 * math.pi * i / 32)) for i in range(32)]


@pack('bubbles')
def bubble_speech():
    p = Piece('bubble_speech')
    p.prism(_bubble_outline('speech'), 0.04)
    p['text'] = ('Hi!', (0, -0.03, 0), 0.12)
    p['place'] = 'free'
    return p


@pack('bubbles')
def bubble_thought():
    p = Piece('bubble_thought')
    for i in range(14):
        a = 2 * math.pi * i / 14
        p.sphere(0.1, 0.34 * math.cos(a), 0, 0.2 * math.sin(a), sy=0.25, seg=12)
    p.prism(_circle(28, 0.3), 0.05)
    for r, x, z in ((0.05, -0.3, -0.3), (0.03, -0.4, -0.42)):
        p.sphere(r, x, 0, z, sy=0.4, seg=12)
    p['text'] = ('Hmm...', (0, -0.04, 0), 0.1)
    p['place'] = 'free'
    return p


@pack('bubbles')
def bubble_shout():
    p = Piece('bubble_shout')
    p.prism(_bubble_outline('shout'), 0.05)
    p['text'] = ('WHAT?!', (0, -0.04, 0), 0.12)
    p['place'] = 'free'
    return p


@pack('bubbles')
def bubble_whisper():
    p = Piece('bubble_whisper')
    pts = _bubble_outline('whisper')
    for i in range(0, len(pts), 2):  # dashed rim: whispers are quiet
        a, b = pts[i], pts[(i + 1) % len(pts)]
        p.tube([(a[0], 0, a[1]), (b[0], 0, b[1])], 0.012, mat='i')
    p.prism([(x * 0.94, z * 0.94) for x, z in pts], 0.02)
    p['text'] = ('psst', (0, -0.02, 0), 0.09)
    p['place'] = 'free'
    return p


@pack('bubbles')
def bubble_dots():
    p = Piece('bubble_dots')
    p.prism([(0.2 * math.cos(2 * math.pi * i / 24), 0.12 * math.sin(2 * math.pi * i / 24)) for i in range(24)], 0.04)
    for x in (-0.08, 0, 0.08):
        p.sphere(0.022, x, -0.025, 0, sy=0.5, mat='i', seg=8)
    p['place'] = 'free'
    return p


# ================================================================== story: reaction symbols
def _sym(name, outline, depth=0.03):
    p = Piece(name)
    p.prism(outline, depth)
    p['place'] = 'free'
    p['reaction'] = True
    return p


@pack('reactions')
def react_question():
    p = _sym('react_question', [(-0.05, 0.1), (-0.09, 0.16), (-0.05, 0.22), (0.03, 0.24), (0.09, 0.2), (0.09, 0.13),
                                (0.02, 0.07), (0.02, 0.03), (-0.03, 0.03), (-0.03, 0.09), (0.04, 0.14), (0.04, 0.18),
                                (0.0, 0.2), (-0.04, 0.18)])
    p.sphere(0.025, 0, 0, -0.02, sy=0.6, seg=12)
    return p


@pack('reactions')
def react_exclaim():
    p = _sym('react_exclaim', [(-0.035, 0.24), (0.035, 0.24), (0.02, 0.04), (-0.02, 0.04)])
    p.sphere(0.028, 0, 0, -0.02, sy=0.6, seg=12)
    return p


@pack('reactions')
def react_sweat():
    pts = [(0, 0.16)] + [(0.07 * math.cos(a), 0.07 * math.sin(a)) for a in [math.pi * (-0.15 + 1.3 * i / 16) for i in range(17)]]
    return _sym('react_sweat', [(x, z) for x, z in pts][::-1])


@pack('reactions')
def react_heart():
    pts = []
    for i in range(40):
        t = 2 * math.pi * i / 40
        pts.append((0.0075 * 16 * math.sin(t) ** 3, 0.0075 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))))
    return _sym('react_heart', pts)


@pack('reactions')
def react_anger():
    p = Piece('react_anger')
    for a in range(4):
        r = math.radians(a * 90 + 45)
        c, s = math.cos(r), math.sin(r)
        p.prism([(0.03 * c - 0.02 * s, 0.03 * s + 0.02 * c), (0.11 * c - 0.03 * s, 0.11 * s + 0.03 * c),
                 (0.11 * c + 0.03 * s, 0.11 * s - 0.03 * c), (0.03 * c + 0.02 * s, 0.03 * s - 0.02 * c)], 0.03)
    p['place'] = 'free'
    p['reaction'] = True
    return p


@pack('reactions')
def react_zzz():
    p = Piece('react_zzz')
    for i, s in enumerate((0.06, 0.08, 0.1)):
        x, z = i * 0.09, i * 0.11
        p.prism([(x, z + s), (x + s, z + s), (x + s, z + s * 0.8), (x + s * 0.3, z + s * 0.2), (x + s, z + s * 0.2),
                 (x + s, z), (x, z), (x, z + s * 0.2), (x + s * 0.7, z + s * 0.8), (x, z + s * 0.8)], 0.025)
    p['place'] = 'free'
    p['reaction'] = True
    return p


@pack('reactions')
def react_star():
    return _sym('react_star', _star(5, 0.12, 0.05))


@pack('reactions')
def react_lightbulb():
    p = Piece('react_lightbulb')
    p.sphere(0.09, 0, 0, 0.14, sy=0.35, seg=16)
    p.box(0.07, 0.03, 0.06, 0, 0, 0.02)
    for a in (-60, -30, 0, 30, 60):
        r = math.radians(a + 90)
        p.tube([(0.14 * math.cos(r), 0, 0.14 + 0.14 * math.sin(r)), (0.19 * math.cos(r), 0, 0.14 + 0.19 * math.sin(r))],
               0.01, mat='i')
    p['place'] = 'free'
    p['reaction'] = True
    return p


@pack('reactions')
def react_note():
    p = Piece('react_note')
    p.sphere(0.04, 0, 0, 0.03, sx=1.3, sy=0.4, seg=12)
    p.box(0.018, 0.02, 0.19, 0.04, 0, 0.03)
    p.prism([(0.04, 0.22), (0.11, 0.17), (0.11, 0.13), (0.049, 0.17)], 0.02)
    p['place'] = 'free'
    p['reaction'] = True
    return p


@pack('reactions')
def react_dizzy():
    p = Piece('react_dizzy')
    path = [(0.012 * t * math.cos(t), 0, 0.012 * t * math.sin(t)) for t in [i * 0.35 for i in range(4, 34)]]
    p.tube(path, 0.012, mat='i')
    p['place'] = 'free'
    p['reaction'] = True
    return p


@pack('reactions')
def react_tear():
    p = _sym('react_tear', [(0, 0.12)] + [(0.045 * math.cos(a), 0.045 * math.sin(a)) for a in
                                          [math.pi * (-0.2 + 1.4 * i / 14) for i in range(15)]][::-1])
    return p


@pack('reactions')
def react_sparkle():
    return _sym('react_sparkle', _star(4, 0.12, 0.03))


# ================================================================== story: screens and frames
def _screen(p, w, h, x, y, z):
    """The face that shows your clip or image (its own material slot at set time)."""
    p.box(w, 0.004, h, x, y, z)
    p['screen'] = (w, h, x, y - 0.003, z + h / 2)


@pack('screens', hold=('palm', 'z', 'upright'))
def phone_screen():
    p = Piece('phone_screen')
    p.box(0.07, 0.009, 0.14, bevel=0.008, seg=2)
    _screen(p, 0.06, 0.12, 0, -0.005, 0.01)
    return p


@pack('screens')
def tv_screen():
    p = Piece('tv_screen')
    p.box(1.3, 0.06, 0.76, 0, 0, 0.5, bevel=0.01, seg=1)
    _screen(p, 1.22, 0.68, 0, -0.031, 0.54)
    p.box(0.08, 0.06, 0.5, 0, 0.02, 0)
    p.box(0.5, 0.25, 0.03, 0, 0.02, 0)
    return p


@pack('screens')
def cinema_screen():
    p = Piece('cinema_screen')
    p.box(4.2, 0.08, 2.4, 0, 0, 0.8)
    _screen(p, 4.0, 2.2, 0, -0.041, 0.9)
    for x in (-2.2, 2.2):
        p.box(0.3, 0.2, 3.3, x, 0, 0)
    return p


@pack('screens')
def billboard():
    p = Piece('billboard')
    for x in (-1.2, 1.2):
        p.box(0.12, 0.12, 2.6, x, 0.1, 0)
    p.box(3.2, 0.12, 1.8, 0, 0, 2.4)
    _screen(p, 3.0, 1.6, 0, -0.061, 2.5)
    p.box(3.2, 0.5, 0.05, 0, -0.2, 2.35)
    return p


@pack('screens')
def laptop_screen():
    p = Piece('laptop_screen')
    p.box(0.34, 0.24, 0.02, bevel=0.005, seg=1)
    lid = Piece('laptop_screen_lid')
    lid.box(0.34, 0.015, 0.23, 0, 0.12, 0.02, bevel=0.005, seg=1)
    _screen(lid, 0.3, 0.19, 0, 0.111, 0.04)
    p['screen'] = lid['screen']
    return p, [part('lid', lid, (0, 0.12, 0.02), 'hinge', 'X', -95)]


def _frame(name, w, h, border=0.04, mat_border=0.0):
    p = Piece(name)
    p.box(w, 0.03, h, 0, 0, 0, bevel=0.005, seg=1)
    _screen(p, w - 2 * border, h - 2 * border, 0, -0.016, border)
    p['place'] = 'wall'
    return p


@pack('frames')
def frame_small():
    return _frame('frame_small', 0.25, 0.32)


@pack('frames')
def frame_square():
    return _frame('frame_square', 0.4, 0.4)


@pack('frames')
def frame_wide():
    return _frame('frame_wide', 0.8, 0.5)


@pack('frames')
def frame_tall():
    return _frame('frame_tall', 0.5, 0.8)


@pack('frames')
def frame_big():
    return _frame('frame_big', 1.2, 0.8, 0.06)


@pack('frames')
def frame_round():
    p = Piece('frame_round')
    p.cyl(0.22, 0.03, 0, 0.015, 0.22, rx=90, seg=32)
    _screen(p, 0.36, 0.36, 0, -0.016, 0.04)
    p['place'] = 'wall'
    return p


@pack('frames')
def poster():
    p = Piece('poster')
    _screen(p, 0.6, 0.85, 0, 0, 0)
    for x, z in ((-0.27, 0.82), (0.27, 0.82), (-0.27, 0.03), (0.27, 0.03)):
        p.sphere(0.012, x, -0.006, z, sy=0.4, mat='i', seg=8)
    p['place'] = 'wall'
    return p


@pack('frames', hold=('pinch', 'x', ''))
def polaroid():
    p = Piece('polaroid')
    p.box(0.1, 0.003, 0.12)
    _screen(p, 0.085, 0.085, 0, -0.002, 0.028)
    return p


@pack('frames')
def corkboard():
    p = Piece('corkboard')
    p.box(1.0, 0.03, 0.7, bevel=0.01, seg=1)
    p.box(0.92, 0.01, 0.62, 0, -0.02, 0.04)
    for x, z, rz in ((-0.3, 0.42, 5), (0.05, 0.38, -6), (0.3, 0.2, 4), (-0.15, 0.12, -3)):
        p.box(0.18, 0.004, 0.14, x, -0.027, z, ry=rz)
        p.sphere(0.012, x, -0.03, z + 0.12, sy=0.5, mat='i', seg=8)
    p['place'] = 'wall'
    return p


# ================================================================== effects: particles (tiny instance shapes)
# fx.py scatters these through the air with a looping geometry-nodes setup, so a whole
# downpour is one object and a few hundred faces.
@pack('weather')
def fx_drop():
    p = Piece('fx_drop')
    p.cyl(0.006, 0.07, r2=0.0, seg=6)
    return p


@pack('weather')
def fx_splash():
    p = Piece('fx_splash')
    p.torus(0.05, 0.006, seg=16, seg2=4)
    return p


@pack('weather')
def puddle():
    p = Piece('puddle')
    pts = [((0.45 + 0.06 * math.sin(3 * a)) * math.cos(a), (0.3 + 0.04 * math.cos(5 * a)) * math.sin(a))
           for a in [2 * math.pi * i / 28 for i in range(28)]]
    p.prism(pts, 0.006, z=0)
    return p


@pack('weather', hold=('fist', 'z', 'upright'))
def umbrella():
    p = Piece('umbrella')
    p.cyl(0.008, 0.62, 0, 0, -0.06, seg=8)
    p.tube([(0, 0, -0.06), (0, 0, -0.1), (0.025, 0, -0.12), (0.05, 0, -0.1)], 0.009)
    canopy = [(0.0, 0.62), (0.12, 0.6), (0.24, 0.55), (0.33, 0.47), (0.36, 0.42)]
    p.lathe(canopy, seg=8)
    p.lathe([(0.36, 0.42), (0.0, 0.5)], seg=8)
    p.sphere(0.012, 0, 0, 0.63, mat='i', seg=8)
    return p


@pack('snowwind')
def fx_flake():
    p = Piece('fx_flake')
    for a in (0, 60, 120):
        p.box(0.05, 0.004, 0.008, 0, 0, -0.004, ry=a)
    return p


@pack('snowwind')
def fx_leaf():
    p = Piece('fx_leaf')
    p.prism([(0, -0.03), (0.02, -0.01), (0.022, 0.012), (0, 0.035), (-0.022, 0.012), (-0.02, -0.01)], 0.003)
    return p


@pack('snowwind')
def fx_petal():
    p = Piece('fx_petal')
    p.sphere(0.018, sx=1.0, sy=0.15, sz=0.6, seg=8)
    return p


@pack('snowwind')
def fx_wind_line():
    p = Piece('fx_wind_line')
    p.tube([(-0.3, 0, 0), (-0.1, 0, 0.02), (0.1, 0, 0.0), (0.25, 0, 0.03), (0.3, 0, 0.06)], 0.006, mat='i')
    return p


@pack('party')
def fx_confetti():
    p = Piece('fx_confetti')
    p.box(0.03, 0.002, 0.018)
    return p


@pack('party')
def fx_streamer():
    p = Piece('fx_streamer')
    p.tube([(0.03 * math.sin(i * 1.3), 0.0, -i * 0.025) for i in range(8)], 0.004)
    return p


@pack('party', hold=('pinch', 'z', ''))
def balloon_bunch():
    p = Piece('balloon_bunch')
    for x, z, s in ((0, 0.62, 1.0), (-0.12, 0.55, 0.9), (0.12, 0.56, 0.95), (-0.05, 0.75, 0.85), (0.08, 0.72, 0.9)):
        p.sphere(0.09 * s, x, 0, z, sz=1.2, seg=16)
        p.tube([(0, 0, 0.0), (x * 0.9, 0, z - 0.1 * s)], 0.002, mat='i')
    p.cyl(0.008, 0.03, 0, 0, -0.015, mat='i', seg=8)
    return p


@pack('party')
def fx_firework():
    p = Piece('fx_firework')
    for i in range(12):
        a = 2 * math.pi * i / 12
        p.tube([(0.04 * math.cos(a), 0, 0.04 * math.sin(a)), (0.16 * math.cos(a), 0, 0.16 * math.sin(a))], 0.006, mat='i')
        p.sphere(0.012, 0.19 * math.cos(a), 0, 0.19 * math.sin(a), seg=8)
    return p


@pack('party')
def bunting():
    p = Piece('bunting')
    path = [(x * 0.2 - 1.0, 0, -0.12 * (1 - (x / 5.0 - 1) ** 2)) for x in range(11)]
    p.tube(path, 0.006, mat='i')
    for i in range(10):
        x0, z0 = path[i][0], path[i][2]
        x1, z1 = path[i + 1][0], path[i + 1][2]
        p.prism([(x0 + 0.02, z0), (x1 - 0.02, z1), ((x0 + x1) / 2, (z0 + z1) / 2 - 0.16)], 0.004)
    p['place'] = 'wall'
    return p


@pack('impact')
def fx_speed_line():
    p = Piece('fx_speed_line')
    p.cyl(0.008, 0.6, 0, 0, 0, r2=0.0, rx=0, ry=90, seg=6, mat='i')
    return p


@pack('impact')
def fx_dust():
    p = Piece('fx_dust')
    for x, z, r in ((0, 0.04, 0.05), (0.05, 0.03, 0.04), (-0.05, 0.03, 0.04), (0.02, 0.07, 0.035)):
        p.sphere(r, x, 0, z, seg=12)
    return p


@pack('impact')
def impact_star():
    p = Piece('impact_star')
    p.prism(_star(8, 0.3, 0.14), 0.03)
    p.prism(_star(8, 0.18, 0.08, phase=math.pi / 2 + 0.2), 0.035)
    p['place'] = 'free'
    return p


@pack('impact')
def whoosh_trail():
    p = Piece('whoosh_trail')
    for i, z in enumerate((-0.12, 0, 0.12)):
        p.tube([(-0.6 + 0.1 * abs(i - 1), 0, z), (-0.2, 0, z * 1.1), (0.15, 0, z * 0.6), (0.35, 0, z * 0.2)], 0.012, mat='i')
    p['place'] = 'free'
    return p


@pack('smoke')
def fx_puff():
    p = Piece('fx_puff')
    for x, z, r in ((0, 0, 0.06), (0.05, 0.02, 0.045), (-0.05, 0.02, 0.045), (0, 0.05, 0.045)):
        p.sphere(r, x, 0, z, seg=12)
    return p


@pack('smoke')
def poof_cloud():
    p = Piece('poof_cloud')
    for i in range(9):
        a = 2 * math.pi * i / 9
        p.sphere(0.16, 0.28 * math.cos(a), 0, 0.3 + 0.2 * math.sin(a), sy=0.7, seg=14)
    p.sphere(0.25, 0, 0, 0.3, sy=0.7, seg=16)
    for a in (20, 100, 200, 300):
        r = math.radians(a)
        p.sphere(0.04, 0.5 * math.cos(r), 0, 0.3 + 0.38 * math.sin(r), seg=8)
    p['place'] = 'free'
    return p


@pack('lights')
def spotlight():
    p = Piece('spotlight')
    p.cyl(0.02, 1.6, seg=8)
    for a in (0, 120, 240):
        p.cyl(0.015, 0.5, 0, 0, 0, ry=35, rz=a, seg=6)
    p.cyl(0.13, 0.32, 0, 0.0, 1.62, r2=0.17, rx=-70, seg=16)
    p.cyl(0.15, 0.01, 0, -0.3, 1.73, rx=-70, seg=16, mat='i')
    p['light'] = ('SPOT', (0, -0.3, 1.73), (math.radians(-20), 0, 0), 400.0)
    return p


@pack('lights')
def window_beams():
    p = Piece('window_beams')
    for i in range(3):
        x = -0.4 + i * 0.4
        p.prism([(x - 0.12, 2.0), (x + 0.12, 2.0), (x + 0.5, 0.0), (x + 0.2, 0.0)], 0.005)
    p['beams'] = True
    return p


@pack('lights')
def neon_sign():
    p = Piece('neon_sign')
    p.box(1.1, 0.03, 0.5, 0, 0.02, 0, bevel=0.01, seg=1)
    p['text'] = ('OPEN', (0, -0.02, 0.25), 0.22)
    p['neon'] = True
    p['place'] = 'wall'
    return p


@pack('lights')
def fairy_lights():
    p = Piece('fairy_lights')
    path = [(x * 0.15 - 1.2, 0, -0.1 * math.sin(x * math.pi / 8)) for x in range(17)]
    p.tube(path, 0.004, mat='i')
    for x, y, z in path[1:-1]:
        p.sphere(0.022, x, 0, z - 0.03, sz=1.3, seg=8)
    p['neon'] = True
    p['place'] = 'wall'
    return p


@pack('magic')
def fx_sparkle():
    p = Piece('fx_sparkle')
    p.prism(_star(4, 0.04, 0.01), 0.004)
    return p


@pack('magic')
def teleport_ring():
    p = Piece('teleport_ring')
    for i, (r, z) in enumerate(((0.45, 0.0), (0.38, 0.4), (0.3, 0.8))):
        p.torus(r, 0.012, 0, 0, z, seg=36, seg2=6)
    p['place'] = 'floor'
    return p


@pack('magic', hold=('fist', 'z', ''))
def glow_wand():
    p = Piece('glow_wand')
    p.cyl(0.008, 0.3, 0, 0, -0.05, seg=8, mat='i')
    p.prism(_star(5, 0.05, 0.022), 0.012, z=0.28)
    p['neon'] = True
    return p


@pack('magic')
def idea_bulb():
    p = Piece('idea_bulb')
    p.sphere(0.16, 0, 0, 0.3, seg=20)
    p.cyl(0.08, 0.12, 0, 0, 0.06, seg=16)
    for z in (0.08, 0.12):
        p.torus(0.082, 0.008, 0, 0, z, seg=16, seg2=4, mat='i')
    p.tube([(-0.05, 0, 0.2), (-0.02, 0, 0.3), (0.0, 0, 0.24), (0.02, 0, 0.3), (0.05, 0, 0.2)], 0.008, mat='i')
    for a in (-70, -35, 0, 35, 70):
        r = math.radians(a + 90)
        p.tube([(0.24 * math.cos(r), 0, 0.3 + 0.24 * math.sin(r)), (0.32 * math.cos(r), 0, 0.3 + 0.32 * math.sin(r))],
               0.012, mat='i')
    p['place'] = 'free'
    p['neon'] = True
    return p


# ================================================================== life: background crowd
def _figure(name, pose):
    """A simple ink-outlined extra, about Bunny's height, so they never compete with him."""
    p = Piece(name)
    sit = pose == 'sit'
    hip = 0.42 if sit else 0.5
    p.sphere(0.13, 0, 0, hip + 0.48, seg=16)                       # head
    p.cyl(0.14, 0.38, 0, 0, hip, r2=0.11, seg=12)                   # body
    if sit:
        for x in (-0.06, 0.06):
            p.cyl(0.045, 0.3, x, 0.0, hip, rx=90, seg=8)
            p.cyl(0.04, hip, x, -0.3, 0, seg=8)
    else:
        step = 0.08 if pose == 'walk' else 0.0
        for x, s in ((-0.06, 1), (0.06, -1)):
            p.cyl(0.045, hip, x, s * step, 0, rx=s * (12 if step else 0), seg=8)
    if pose == 'cheer':
        for x in (-1, 1):
            p.cyl(0.035, 0.32, x * 0.14, 0, hip + 0.32, ry=x * -25, seg=8)
    else:
        for x in (-1, 1):
            p.cyl(0.035, 0.3, x * 0.15, 0, hip + 0.04, ry=x * 8, seg=8)
    return p


@pack('crowd')
def extra_stand():
    return _figure('extra_stand', 'stand')


@pack('crowd')
def extra_sit():
    return _figure('extra_sit', 'sit')


@pack('crowd')
def extra_walk():
    return _figure('extra_walk', 'walk')


@pack('crowd')
def extra_cheer():
    return _figure('extra_cheer', 'cheer')


# ================================================================== life: small critters
@pack('critters')
def sill_bird():
    p = Piece('sill_bird')
    p.sphere(0.06, 0, 0, 0.06, sx=1.3, seg=14)
    p.sphere(0.04, 0.06, 0, 0.12, seg=12)
    p.cyl(0.012, 0.03, 0.1, 0, 0.12, r2=0.0, ry=90, seg=6, mat='i')
    p.sphere(0.008, 0.075, -0.03, 0.13, mat='i', seg=6)
    p.prism([(-0.07, 0.07), (-0.14, 0.11), (-0.12, 0.05)], 0.02)
    return p


@pack('critters')
def goldfish_bowl():
    p = Piece('goldfish_bowl')
    p.lathe([(0.06, 0), (0.14, 0.05), (0.16, 0.14), (0.13, 0.24), (0.1, 0.27)], seg=24)
    fish = Piece('goldfish_bowl_fish')
    fish.sphere(0.03, 0, 0, 0.13, sx=1.4, sy=0.6, seg=10)
    fish.prism([(-0.04, 0.13), (-0.07, 0.16), (-0.07, 0.1)], 0.01)
    return p, [part('fish', fish, (0, 0, 0.13), 'spin', 'Z', 360)]


@pack('critters')
def butterfly():
    p = Piece('butterfly')
    p.cyl(0.006, 0.05, 0, 0, -0.025, seg=6, mat='i')
    wl, wr = Piece('butterfly_wing_l'), Piece('butterfly_wing_r')
    wl.prism([(0, 0), (-0.05, 0.04), (-0.04, -0.01), (-0.035, -0.035), (0, -0.01)], 0.003)
    wr.prism([(0, 0), (0.05, 0.04), (0.04, -0.01), (0.035, -0.035), (0, -0.01)], 0.003)
    p['place'] = 'free'
    return p, [part('wing_l', wl, (0, 0, 0), 'flap', 'Z', 60), part('wing_r', wr, (0, 0, 0), 'flap', 'Z', -60)]


@pack('critters')
def snail():
    p = Piece('snail')
    p.sphere(0.03, 0, 0, 0.015, sx=2.4, sy=0.8, sz=0.5, seg=12)
    p.torus(0.035, 0.022, -0.01, 0, 0.055, rx=90, seg=16, seg2=8)
    for x in (0.06, 0.07):
        p.tube([(x, 0, 0.02), (x + 0.01, 0, 0.06)], 0.003, mat='i')
    return p


@pack('critters')
def sleeping_cat():
    p = Piece('sleeping_cat')
    p.sphere(0.18, 0, 0, 0.09, sx=1.3, sz=0.55, seg=18)
    p.sphere(0.09, 0.16, -0.06, 0.12, seg=14)
    for x in (0.12, 0.2):
        p.prism([(x - 0.03, 0.18), (x, 0.24), (x + 0.03, 0.18)], 0.02, y=-0.06)
    p.tube([(0.12, -0.14, 0.13), (0.14, -0.15, 0.125)], 0.004, mat='i')
    p.tube([(0.18, -0.14, 0.13), (0.2, -0.15, 0.125)], 0.004, mat='i')
    p.tube([(-0.2, 0, 0.05), (-0.22, -0.12, 0.03), (-0.1, -0.2, 0.02)], 0.03)
    p['breathe'] = True
    return p


# ================================================================== life: talking objects (eyes + mouth spot)
def _talker(p, z, w=0.06, y=-0.01):
    """Eyes drawn on; the mouth is a spot the mouth-set system fills and lip-syncs."""
    for x in (-w, w):
        p.sphere(0.022, x, y, z, sx=0.8, sy=0.3, sz=1.0, mat='i', seg=10)
    p['mouth'] = (0, y - 0.004, z - 0.07, 0.07)
    p['talker'] = True
    return p


@pack('talkobj')
def talking_mug():
    p = Piece('talking_mug')
    p.cyl(0.11, 0.24, seg=24)
    p.torus(0.07, 0.018, 0.12, 0, 0.12, rx=90, seg=16, seg2=6)
    return _talker(p, 0.17, 0.045, -0.112)


@pack('talkobj')
def talking_phone():
    p = Piece('talking_phone')
    p.box(0.16, 0.02, 0.32, bevel=0.02, seg=2)
    return _talker(p, 0.22, 0.04, -0.012)


@pack('talkobj')
def talking_plant():
    p = Piece('talking_plant')
    p.cyl(0.12, 0.2, r2=0.15, seg=20)
    for a, l in ((0, 0.3), (40, 0.24), (-40, 0.26), (80, 0.18), (-80, 0.2)):
        r = math.radians(a)
        p.sphere(0.05, math.sin(r) * l * 0.6, 0.02, 0.2 + math.cos(r) * l, sx=0.6, sy=0.3, sz=1.2, seg=10)
    return _talker(p, 0.14, 0.045, -0.13)


@pack('talkobj')
def talking_clock():
    p = Piece('talking_clock')
    p.cyl(0.14, 0.08, 0, 0.04, 0.16, rx=90, seg=28)
    for x in (-0.1, 0.1):
        p.sphere(0.05, x, 0, 0.3, sy=0.6, seg=12)
        p.cyl(0.012, 0.06, x * 0.9, 0, 0.02, seg=6, mat='i')
    p.tube([(-0.1, 0, 0.3), (0, 0, 0.33), (0.1, 0, 0.3)], 0.008, mat='i')
    return _talker(p, 0.2, 0.05, -0.045)


# ================================================================== rides: cars and city rides
def _car_body(p, L, W, H, cab):
    p.box(L, W, H, 0, 0, 0.12, bevel=0.06, seg=3)
    p.box(L * cab, W * 0.9, H * 0.8, -L * 0.05, 0, 0.12 + H, bevel=0.06, seg=3)


@pack('cars')
def car():
    p = Piece('car')
    _car_body(p, 2.4, 1.2, 0.45, 0.55)
    p.box(1.1, 0.02, 0.28, -0.12, -0.6, 0.66)
    parts = [_wheel('wheel_%d' % i, 0.22, 0.14, x, s * 0.6, 0.22) for i, (x, s) in
             enumerate(((-0.75, -1), (0.75, -1), (-0.75, 1), (0.75, 1)))]
    p['seat'] = (-0.1, 0, 0.42)
    return p, parts


@pack('cars')
def auto_rickshaw():
    p = Piece('auto_rickshaw')
    p.box(1.7, 1.0, 0.35, 0, 0, 0.2, bevel=0.06, seg=2)
    p.box(1.2, 1.02, 0.08, -0.1, 0, 1.45, bevel=0.04, seg=2)
    p.lathe([(0.0, 1.45), (0.5, 1.45), (0.55, 1.35)], -0.1, 0, 0, seg=6)
    for x, y in ((-0.6, -0.48), (-0.6, 0.48), (0.4, -0.48), (0.4, 0.48)):
        p.cyl(0.025, 0.9, x, y, 0.55, seg=8)
    p.box(0.08, 0.6, 0.5, 0.75, 0, 0.55)
    p.tube([(0.7, -0.25, 1.0), (0.8, 0, 1.05), (0.7, 0.25, 1.0)], 0.015, mat='i')
    parts = [_wheel('wheel_%d' % i, 0.18, 0.1, x, y, 0.18) for i, (x, y) in
             enumerate(((0.75, 0.0), (-0.55, -0.5), (-0.55, 0.5)))]
    p['seat'] = (-0.3, 0, 0.55)
    return p, parts


@pack('cars')
def taxi():
    p = Piece('taxi')
    _car_body(p, 2.4, 1.2, 0.45, 0.55)
    p.box(0.4, 0.2, 0.12, -0.1, 0, 0.98, bevel=0.03, seg=2)
    p['text'] = ('TAXI', (-0.1, -0.105, 1.04), 0.07)
    parts = [_wheel('wheel_%d' % i, 0.22, 0.14, x, s * 0.6, 0.22) for i, (x, s) in
             enumerate(((-0.75, -1), (0.75, -1), (-0.75, 1), (0.75, 1)))]
    p['seat'] = (-0.1, 0, 0.42)
    return p, parts


@pack('cars')
def city_scooter():
    p = Piece('city_scooter')
    p.box(0.9, 0.3, 0.12, 0, 0, 0.22, bevel=0.04, seg=2)
    p.box(0.5, 0.3, 0.25, -0.2, 0, 0.32, bevel=0.08, seg=2)
    p.box(0.42, 0.28, 0.07, -0.22, 0, 0.58, bevel=0.03, seg=2)
    p.cyl(0.025, 0.65, 0.38, 0, 0.25, ry=-15, seg=8)
    p.cyl(0.018, 0.5, 0.55, -0.25, 0.88, rx=-90, seg=8)
    p.box(0.18, 0.3, 0.45, 0.32, 0, 0.22, bevel=0.06, seg=2)
    parts = [_wheel('wheel_%d' % i, 0.16, 0.1, x, 0, 0.16) for i, x in enumerate((-0.45, 0.45))]
    p['seat'] = (-0.22, 0, 0.65)
    return p, parts


# ================================================================== rides: bikes and boards
@pack('bikes')
def skateboard_ride():
    p = Piece('skateboard_ride')
    p.box(0.8, 0.22, 0.03, 0, 0, 0.09, bevel=0.1, seg=3)
    for x in (-0.28, 0.28):
        p.box(0.04, 0.16, 0.03, x, 0, 0.06)
    parts = [_wheel('wheel_%d' % i, 0.035, 0.04, x, y, 0.035, seg=12) for i, (x, y) in
             enumerate(((-0.28, -0.09), (-0.28, 0.09), (0.28, -0.09), (0.28, 0.09)))]
    p['seat'] = (0, 0, 0.12)
    return p, parts


@pack('bikes')
def office_chair_ride():
    p = Piece('office_chair_ride')
    p.box(0.5, 0.5, 0.08, 0, 0, 0.45, bevel=0.03, seg=2)
    p.box(0.48, 0.07, 0.55, 0, 0.24, 0.55, bevel=0.03, seg=2, rx=-8)
    p.cyl(0.03, 0.35, 0, 0, 0.1, seg=10)
    for a in range(5):
        p.box(0.32, 0.04, 0.03, 0.16 * math.cos(math.radians(a * 72)), 0.16 * math.sin(math.radians(a * 72)), 0.07,
              rz=a * 72)
    parts = [_wheel('wheel_%d' % a, 0.035, 0.03, 0.31 * math.cos(math.radians(a * 72)),
                    0.31 * math.sin(math.radians(a * 72)), 0.035, seg=10) for a in range(5)]
    p['seat'] = (0, 0, 0.53)
    return p, parts


@pack('bikes')
def cycle():
    p = Piece('cycle')
    for a, b in (((-0.5, 0.35), (0.0, 0.35)), ((0.0, 0.35), (0.12, 0.85)), ((-0.5, 0.35), (-0.12, 0.8)),
                 ((-0.12, 0.8), (0.45, 0.85)), ((0.45, 0.85), (0.5, 0.35)), ((0.0, 0.35), (-0.12, 0.8))):
        p.tube([(a[0], 0, a[1]), (b[0], 0, b[1])], 0.018)
    p.box(0.22, 0.08, 0.04, -0.14, 0, 0.85, bevel=0.02, seg=2)
    p.tube([(0.42, -0.25, 1.0), (0.45, 0, 0.98), (0.42, 0.25, 1.0)], 0.015, mat='i')
    p.tube([(0.45, 0, 0.85), (0.45, 0, 0.98)], 0.015)
    parts = [part('wheel_%d' % i, _ring_wheel('cycle_wheel_%d' % i, x), (x, 0, 0.35), 'wheel', 'Y', 0.33)
             for i, x in enumerate((-0.5, 0.5))]
    parts.append(part('pedals', _pedals(), (0, 0, 0.35), 'spin', 'Y', 360))
    p['seat'] = (-0.14, 0, 0.9)
    return p, parts


def _ring_wheel(name, x):
    w = Piece(name)
    w.torus(0.33, 0.025, x, 0, 0.35, rx=90, seg=32, seg2=6, mat='i')
    for a in range(0, 180, 30):
        r = math.radians(a)
        w.tube([(x - 0.31 * math.cos(r), 0, 0.35 - 0.31 * math.sin(r)), (x + 0.31 * math.cos(r), 0, 0.35 + 0.31 * math.sin(r))],
               0.004, mat='i')
    return w


def _pedals():
    w = Piece('cycle_pedals')
    w.cyl(0.08, 0.02, 0, 0.01, 0.35, rx=90, seg=16)
    w.tube([(0, -0.05, 0.35), (0.0, -0.05, 0.2)], 0.012, mat='i')
    w.box(0.08, 0.05, 0.02, 0, -0.08, 0.19)
    return w


@pack('bikes')
def shopping_trolley():
    p = Piece('shopping_trolley')
    p.box(0.75, 0.5, 0.45, 0, 0, 0.45)
    for x in (-0.3, -0.1, 0.1, 0.3):
        p.box(0.012, 0.51, 0.44, x, 0, 0.455, mat='i')
    p.tube([(-0.4, -0.3, 0.95), (-0.4, 0.3, 0.95)], 0.02, mat='i')
    for x, y in ((-0.3, -0.2), (0.3, -0.2), (-0.3, 0.2), (0.3, 0.2)):
        p.cyl(0.015, 0.4, x, y, 0.06, seg=6)
    parts = [_wheel('wheel_%d' % i, 0.05, 0.03, x, y, 0.05, seg=12) for i, (x, y) in
             enumerate(((-0.3, -0.2), (0.3, -0.2), (-0.3, 0.2), (0.3, 0.2)))]
    p['seat'] = (0, 0, 0.5)
    return p, parts


# ================================================================== rides: fantasy
@pack('fantasy')
def rocket():
    p = Piece('rocket')
    p.lathe([(0.0, 0.3), (0.4, 0.35), (0.45, 1.2), (0.4, 1.9), (0.25, 2.4), (0.0, 2.7)], seg=24)
    for a in (0, 120, 240):
        r = math.radians(a)
        p.prism([(0.38, 0.3), (0.75, 0.0), (0.75, 0.25), (0.42, 0.9)], 0.05, rz=a)
    p.cyl(0.16, 0.05, 0, -0.43, 1.6, rx=90, seg=24, mat='i')
    p.cyl(0.13, 0.06, 0, -0.44, 1.6, rx=90, seg=24)
    p['seat'] = (0, 0, 1.2)
    flame = Piece('rocket_flame')
    flame.cyl(0.28, 0.5, 0, 0, -0.2, r2=0.0, rx=180, seg=12)
    return p, [part('flame', flame, (0, 0, 0.3), 'flicker', 'Z', 0.25)]


@pack('fantasy')
def hot_air_balloon():
    p = Piece('hot_air_balloon')
    p.lathe([(0.0, 1.2), (0.45, 1.25), (0.95, 1.7), (1.2, 2.3), (1.15, 2.9), (0.85, 3.4), (0.4, 3.65), (0.0, 3.7)], seg=12)
    p.box(0.8, 0.8, 0.6, bevel=0.03, seg=1)
    for x, y in ((-0.38, -0.38), (0.38, -0.38), (-0.38, 0.38), (0.38, 0.38)):
        p.tube([(x, y, 0.6), (x * 1.2, y * 1.2, 1.25)], 0.008, mat='i')
    p['seat'] = (0, 0, 0.1)
    return p


@pack('fantasy')
def paper_plane():
    p = Piece('paper_plane')
    p.prism([(0, 0), (1.6, 0.2), (0, 0.5)], 0.02, rz=0)
    p.box(1.6, 0.6, 0.02, 0.8, 0, 0.2, bevel=0.0)
    p.prism([(0, 0.2), (1.6, 0.2), (0.2, -0.2)], 0.02)
    p['seat'] = (0.6, 0, 0.22)
    return p


@pack('fantasy')
def magic_carpet():
    p = Piece('magic_carpet')
    rows = []
    for j in range(6):
        y = -0.6 + j * 0.24
        p.box(1.8, 0.24, 0.025, 0, y, 0.4 + 0.04 * math.sin(j * 1.3), bevel=0.0)
    for x in (-0.92, 0.92):
        for j in range(6):
            p.tube([(x, -0.6 + j * 0.24, 0.41), (x * 1.08, -0.6 + j * 0.24, 0.39)], 0.008, mat='i')
    p['seat'] = (0, 0, 0.44)
    p['float'] = True
    return p


# ================================================================== kits: food and chai
@pack('food', hold=('pinch', 'x', ''))
def samosa():
    p = Piece('samosa')
    p.prism([(-0.05, 0), (0.05, 0), (0, 0.08)], 0.035)
    return p


@pack('food', hold=('palm', 'z', 'upright'))
def vada_pav():
    p = Piece('vada_pav')
    p.sphere(0.05, 0, 0, 0.02, sz=0.45, seg=16)
    p.sphere(0.045, 0, 0, 0.045, sz=0.5, seg=14)
    p.sphere(0.05, 0, 0, 0.065, sz=0.45, seg=16)
    p.cyl(0.035, 0.005, 0.0, -0.0, 0.043, seg=8, mat='i')
    return p


@pack('food', hold=('palm', 'z', 'upright'))
def noodle_box():
    p = Piece('noodle_box')
    p.cyl(0.05, 0.1, r2=0.065, seg=4, rz=45)
    p.tube([(0.03, 0, 0.08), (0.06, 0, 0.2)], 0.004, mat='i')
    p.tube([(0.015, 0.01, 0.08), (0.04, 0.01, 0.2)], 0.004, mat='i')
    p['steam'] = (0, 0, 0.11)
    return p


@pack('food', hold=('fist', 'z', 'upright'))
def cutting_chai():
    p = Piece('cutting_chai')
    p.cyl(0.025, 0.07, r2=0.032, seg=10)
    p.cyl(0.026, 0.045, 0, 0, 0.002, r2=0.03, seg=10)
    p['steam'] = (0, 0, 0.075)
    return p


@pack('food')
def chai_kettle():
    p = Piece('chai_kettle')
    p.lathe([(0.0, 0.0), (0.12, 0.0), (0.14, 0.08), (0.1, 0.18), (0.05, 0.2), (0.0, 0.21)], seg=20)
    p.tube([(0.12, 0, 0.06), (0.2, 0, 0.14), (0.24, 0, 0.18)], 0.015)
    p.tube([(-0.1, 0, 0.16), (-0.18, 0, 0.2), (-0.1, 0, 0.06)], 0.01, mat='i')
    p['steam'] = (0.24, 0, 0.19)
    return p


# ================================================================== kits: festivals
@pack('festival')
def sky_lantern():
    p = Piece('sky_lantern')
    p.cyl(0.18, 0.06, 0, 0, 0.0, seg=8)
    p.prism([(0.18 * math.cos(2 * math.pi * i / 8), 0.06 + 0.4 * (i % 2 == 0)) for i in range(8)], 0.0)
    p.lathe([(0.18, 0.06), (0.26, 0.2), (0.0, 0.46)], seg=8)
    for a in range(0, 360, 60):
        r = math.radians(a)
        p.tube([(0.15 * math.cos(r), 0.15 * math.sin(r), 0.0), (0.15 * math.cos(r), 0.15 * math.sin(r), -0.25)], 0.004, mat='i')
    p.tube([(0, 0, 0.46), (0, 0, 0.7)], 0.004, mat='i')
    p['neon'] = True
    p['place'] = 'wall'
    return p


@pack('festival')
def rangoli():
    p = Piece('rangoli')
    p.cyl(0.5, 0.004, seg=40)
    p.prism([(x, z) for x, z in _star(8, 0.45, 0.25)], 0.004, z=0)
    for i in range(8):
        a = 2 * math.pi * i / 8
        p.cyl(0.05, 0.006, 0.32 * math.cos(a), 0.32 * math.sin(a), 0.0, seg=12, mat='i')
    p.cyl(0.08, 0.006, seg=16, mat='i')
    p['place'] = 'floor'
    return p


@pack('festival')
def pumpkin():
    p = Piece('pumpkin')
    for a in range(0, 360, 45):
        r = math.radians(a)
        p.sphere(0.12, 0.08 * math.cos(r), 0.08 * math.sin(r), 0.12, sx=0.7, sz=0.9, seg=14)
    p.cyl(0.025, 0.08, 0, 0, 0.22, r2=0.015, seg=8, mat='i')
    p.prism([(-0.08, 0.15), (-0.03, 0.18), (-0.05, 0.12)], 0.02, y=-0.17, mat='i')
    p.prism([(0.08, 0.15), (0.03, 0.18), (0.05, 0.12)], 0.02, y=-0.17, mat='i')
    p.prism([(-0.08, 0.07), (0.08, 0.07), (0.04, 0.04), (0, 0.06), (-0.04, 0.04)], 0.02, y=-0.17, mat='i')
    return p


@pack('festival')
def ghost_cutout():
    p = Piece('ghost_cutout')
    pts = [(0.3 * math.cos(a), 0.9 + 0.3 * math.sin(a)) for a in [math.pi * i / 16 for i in range(17)]]
    pts += [(-0.3, 0.0), (-0.2, 0.08), (-0.1, 0.0), (0.0, 0.08), (0.1, 0.0), (0.2, 0.08), (0.3, 0.0)][::-1][::-1]
    p.prism(pts[:17] + [(-0.3, 0.0), (-0.2, 0.08), (-0.1, 0.0), (0.0, 0.08), (0.1, 0.0), (0.2, 0.08), (0.3, 0.0)][::-1][::-1][::-1], 0.02)
    for x in (-0.1, 0.1):
        p.cyl(0.035, 0.01, x, -0.015, 0.9, rx=90, seg=10, mat='i')
    return p


@pack('festival')
def xmas_tree():
    p = Piece('xmas_tree')
    p.cyl(0.08, 0.2, seg=8)
    for i, (r, z) in enumerate(((0.6, 0.2), (0.48, 0.65), (0.35, 1.05))):
        p.cyl(r, 0.6, 0, 0, z, r2=0.05, seg=12)
    p.prism(_star(5, 0.12, 0.05), 0.03, z=1.72)
    for a, z in ((20, 0.5), (140, 0.6), (260, 0.45), (80, 0.95), (200, 0.9), (320, 1.0), (30, 1.3)):
        r = math.radians(a)
        rr = 0.55 - 0.3 * (z - 0.4)
        p.sphere(0.035, rr * math.cos(r) * 0.9, rr * math.sin(r) * 0.9 - 0.02, z, seg=8, mat='i')
    return p


@pack('festival')
def new_year_sign():
    p = Piece('new_year_sign')
    p.box(1.4, 0.04, 0.45, bevel=0.02, seg=1)
    p['text'] = ('HAPPY NEW YEAR', (0, -0.03, 0.22), 0.1)
    p['place'] = 'wall'
    return p


# ================================================================== kits: music
@pack('music')
def mic_stand():
    p = Piece('mic_stand')
    p.cyl(0.16, 0.03, seg=20)
    p.cyl(0.012, 1.4, 0, 0, 0.03, seg=8, mat='i')
    p.cyl(0.03, 0.12, 0, -0.02, 1.4, rx=-70, seg=10)
    p.sphere(0.04, 0, -0.14, 1.45, seg=12)
    return p


@pack('music')
def keyboard_stand():
    p = Piece('keyboard_stand')
    for a in (35, -35):
        p.box(0.04, 0.04, 0.95, 0, 0, 0, ry=a)
    p.box(1.1, 0.35, 0.08, 0, 0, 0.75, bevel=0.02, seg=1)
    for i in range(14):
        p.box(0.06, 0.18, 0.01, -0.5 + i * 0.077, -0.07, 0.83)
    for i in (0, 1, 3, 4, 5, 7, 8, 10, 11, 12):
        p.box(0.035, 0.1, 0.02, -0.46 + i * 0.077, -0.03, 0.835, mat='i')
    return p


@pack('music')
def drum_kit():
    p = Piece('drum_kit')
    p.cyl(0.3, 0.35, 0, 0, 0.3, rx=90, seg=24)
    p.cyl(0.32, 0.02, 0, -0.18, 0.3, rx=90, seg=24)
    for x, r, z in ((-0.45, 0.17, 0.55), (0.45, 0.2, 0.45)):
        p.cyl(r, 0.18, x, -0.1, z, seg=20)
        p.cyl(0.01, z, x, -0.1, 0, seg=6, mat='i')
    for x in (-0.7, 0.7):
        p.cyl(0.01, 0.95, x, 0.1, 0, seg=6, mat='i')
        p.cyl(0.2, 0.01, x, 0.1, 0.95, seg=20)
    return p


@pack('music')
def speaker_pair():
    p = Piece('speaker_pair')
    for x in (-0.6, 0.6):
        p.box(0.35, 0.3, 0.6, x, 0, 0, bevel=0.02, seg=1)
        p.cyl(0.12, 0.02, x, -0.15, 0.22, rx=90, seg=20, mat='i')
        p.cyl(0.05, 0.02, x, -0.15, 0.48, rx=90, seg=14, mat='i')
    return p


@pack('music')
def turntable():
    p = Piece('turntable')
    p.box(0.5, 0.38, 0.08, bevel=0.01, seg=1)
    rec = Piece('turntable_record')
    rec.cyl(0.16, 0.01, -0.05, 0, 0.08, seg=28, mat='i')
    rec.cyl(0.05, 0.012, -0.05, 0, 0.08, seg=16)
    p.tube([(0.2, 0.14, 0.1), (0.18, -0.05, 0.1), (0.08, -0.08, 0.1)], 0.008)
    return p, [part('record', rec, (-0.05, 0, 0.08), 'spin', 'Z', 360)]


# ================================================================== kits: creator desk
@pack('creator')
def ring_light():
    p = Piece('ring_light')
    for a in (0, 120, 240):
        p.cyl(0.012, 0.5, 0, 0, 0, ry=25, rz=a, seg=6)
    p.cyl(0.015, 1.5, 0, 0, 0.1, seg=8)
    p.torus(0.22, 0.03, 0, 0, 1.7, rx=90, seg=32, seg2=8)
    p['neon'] = True
    return p


@pack('creator')
def camera_tripod():
    p = Piece('camera_tripod')
    for a in (0, 120, 240):
        p.cyl(0.012, 1.25, 0, 0, 0, ry=18, rz=a, seg=6)
    p.box(0.22, 0.12, 0.14, 0, 0, 1.2, bevel=0.02, seg=2)
    p.cyl(0.05, 0.1, 0, -0.06, 1.27, rx=90, seg=16)
    p.cyl(0.04, 0.01, 0, -0.16, 1.27, rx=90, seg=16, mat='i')
    return p


@pack('creator')
def podcast_mic():
    p = Piece('podcast_mic')
    p.cyl(0.08, 0.02, seg=16)
    p.tube([(0, 0, 0.02), (0.02, 0, 0.3), (-0.05, -0.15, 0.45)], 0.012, mat='i')
    p.cyl(0.045, 0.16, -0.05, -0.15, 0.4, rx=-20, seg=14)
    p.torus(0.06, 0.008, -0.05, -0.15, 0.47, rx=70, seg=16, seg2=4, mat='i')
    return p


@pack('creator')
def pen_display():
    p = Piece('pen_display')
    p.box(0.5, 0.32, 0.02, 0, 0, 0.1, rx=-20, bevel=0.01, seg=1)
    _screen(p, 0.44, 0.27, 0, -0.012, 0.0)
    p.box(0.06, 0.06, 0.12, 0, 0.12, 0)
    p.cyl(0.006, 0.15, 0.3, -0.05, 0.12, ry=80, seg=6, mat='i')
    return p


# ================================================================== kits: sports
@pack('sports', hold=('palm', 'z', 'upright'))
def cricket_ball():
    p = Piece('cricket_ball')
    p.sphere(0.035, 0, 0, 0.035, seg=16)
    p.torus(0.0355, 0.003, 0, 0, 0.035, rx=90, seg=20, seg2=4, mat='i')
    return p


@pack('sports', hold=('palm', 'z', 'upright'))
def football():
    p = Piece('football')
    p.sphere(0.11, 0, 0, 0.11, seg=20)
    p.prism([(0.04 * math.cos(math.pi / 2 + i * 2 * math.pi / 5), 0.11 + 0.04 * math.sin(math.pi / 2 + i * 2 * math.pi / 5))
             for i in range(5)], 0.01, y=-0.108, mat='i')
    return p


@pack('sports')
def basketball_hoop():
    p = Piece('basketball_hoop')
    p.cyl(0.05, 2.6, 0, 0.4, 0, seg=10)
    p.box(1.0, 0.04, 0.6, 0, 0.3, 2.3, bevel=0.01, seg=1)
    p.box(0.4, 0.01, 0.3, 0, 0.275, 2.35)
    p.torus(0.2, 0.012, 0, 0.05, 2.35, seg=24, seg2=6, mat='i')
    for i in range(8):
        a = 2 * math.pi * i / 8
        p.tube([(0.2 * math.cos(a), 0.05 + 0.2 * math.sin(a), 2.35), (0.12 * math.cos(a), 0.05 + 0.12 * math.sin(a), 2.0)],
               0.004, mat='i')
    return p


@pack('sports', hold=('fist', 'z', ''))
def dumbbell_pair():
    p = Piece('dumbbell_pair')
    p.cyl(0.012, 0.16, 0, 0, -0.08, ry=90, seg=8, mat='i')
    for x in (-0.08, 0.06):
        p.cyl(0.04, 0.03, x, 0, 0, ry=90, seg=6)
    return p


# ================================================================== camera: foreground framing
# Pieces that sit close to the camera for frame-within-a-frame shots. fx.frame_shot()
# snaps them onto the left or right third and keeps them out of Bunny's face band.
def _fg(name):
    p = Piece(name)
    p['foreground'] = True
    return p


@pack('foreground')
def fg_door_frame():
    p = _fg('fg_door_frame')
    p.box(0.12, 0.12, 2.4, -1.0, 0, 0)
    p.box(0.12, 0.12, 2.4, 1.0, 0, 0)
    p.box(2.12, 0.12, 0.14, 0, 0, 2.3)
    return p


@pack('foreground')
def fg_plant():
    p = _fg('fg_plant')
    for a, l in ((-30, 0.9), (-10, 1.1), (15, 1.0), (35, 0.8), (55, 0.6)):
        r = math.radians(a)
        p.sphere(0.12, math.sin(r) * l * 0.5, 0, math.cos(r) * l, sx=0.6, sy=0.25, sz=1.6, seg=12)
        p.tube([(0, 0, 0), (math.sin(r) * l * 0.45, 0, math.cos(r) * l * 0.9)], 0.01, mat='i')
    return p


@pack('foreground')
def fg_window_edge():
    p = _fg('fg_window_edge')
    p.box(0.16, 0.14, 2.4)
    p.box(0.6, 0.14, 0.12, 0.3, 0, 0.9)
    for z in (0.95, 1.5):
        p.box(0.05, 0.05, 0.05, 0.12, -0.08, z, mat='i')
    return p


@pack('foreground')
def fg_curtain():
    p = _fg('fg_curtain')
    for i in range(4):
        p.cyl(0.07, 2.4, i * 0.12, 0, 0, r2=0.09, seg=10)
    p.box(0.7, 0.08, 0.06, 0.15, 0, 2.4)
    return p


@pack('foreground')
def fg_shelf_edge():
    p = _fg('fg_shelf_edge')
    p.box(0.06, 0.3, 1.8)
    for z in (0.3, 0.8, 1.3):
        p.box(0.5, 0.3, 0.04, 0.25, 0, z)
    p.box(0.08, 0.15, 0.24, 0.15, 0, 0.84)
    p.box(0.07, 0.15, 0.2, 0.25, 0, 0.84)
    return p


@pack('foreground')
def fg_leaves():
    p = _fg('fg_leaves')
    for i in range(7):
        a = math.radians(-60 + i * 20)
        p.sphere(0.1, 0.5 * math.sin(a), 0, 0.5 * math.cos(a), sx=0.5, sy=0.2, sz=1.3, seg=10)
    p.tube([(0, 0, 0), (0, 0, 0.5)], 0.012, mat='i')
    return p


@pack('foreground')
def fg_fence():
    p = _fg('fg_fence')
    for x in range(4):
        p.prism([(x * 0.2 - 0.06, 0), (x * 0.2 + 0.06, 0), (x * 0.2 + 0.06, 0.8), (x * 0.2, 0.88), (x * 0.2 - 0.06, 0.8)], 0.04)
    for z in (0.2, 0.6):
        p.box(0.8, 0.03, 0.06, 0.3, 0.03, z)
    return p


@pack('foreground')
def fg_lamp():
    p = _fg('fg_lamp')
    p.cyl(0.015, 1.5, seg=8, mat='i')
    p.cyl(0.18, 0.25, 0, 0, 1.45, r2=0.08, seg=16)
    return p


@pack('foreground')
def fg_railing():
    p = _fg('fg_railing')
    p.box(1.6, 0.05, 0.05, 0, 0, 0.9)
    for i in range(9):
        p.box(0.03, 0.03, 0.9, -0.8 + i * 0.2, 0, 0)
    return p


@pack('foreground')
def fg_arch():
    p = _fg('fg_arch')
    pts = [(-1.2, 0), (-1.2, 2.0)] + [(-0.9 * math.cos(a), 2.0 + 0.6 * math.sin(a)) for a in
                                      [math.pi * i / 12 for i in range(13)]] + [(1.2, 2.0), (1.2, 0), (0.9, 0), (0.9, 2.0)]
    pts += [(0.75 * math.cos(a), 2.0 + 0.45 * math.sin(a)) for a in [math.pi * i / 12 for i in range(13)]] + [(-0.9, 2.0), (-0.9, 0)]
    p.prism(pts, 0.12)
    return p


# ================================================================== camera: clean backdrops + skies
@pack('backdrop')
def cyc_backdrop():
    p = Piece('cyc_backdrop')
    prof = [(0, -5.0), (0, 0.8)] + [(1.2 - 1.2 * math.cos(a), 0.8 + 1.2 * math.sin(a)) for a in
                                    [math.pi / 2 * i / 8 for i in range(1, 9)]] + [(3.6, 2.0)]
    rows = [(y, z) for z, y in prof]
    for (y0, z0), (y1, z1) in zip(rows, rows[1:]):
        p.box(14.0, abs(y1 - y0) + 0.001, 0.001, 0, (y0 + y1) / 2, (z0 + z1) / 2,
              rx=-math.degrees(math.atan2(z1 - z0, y1 - y0)))
    return p


@pack('backdrop')
def corner_flats():
    p = Piece('corner_flats')
    p.box(3.0, 0.05, 2.6, 0.3, 1.6, 0)
    p.box(0.05, 2.6, 2.6, -1.2, 0.3, 0)
    return p


@pack('skydomes')
def sky_dome():
    p = Piece('sky_dome')
    seg = 24
    rings = []
    for j in range(7):
        a = math.pi / 2 * j / 6
        rings.append((60 * math.cos(a), 60 * math.sin(a) - 4))
    p.lathe(rings, seg=seg)
    p['sky'] = True
    return p


@pack('skyline')
def far_sea():
    p = Piece('far_sea')
    p.box(6.8, 0.02, 0.02, 0, 0, 0.0)
    for i in range(7):
        p.tube([(-3 + i * 0.9, 0, 0.06), (-2.8 + i * 0.9, 0, 0.09), (-2.6 + i * 0.9, 0, 0.06)], 0.01, mat='i')
    return p


@pack('skyline')
def far_forest():
    p = Piece('far_forest')
    pts = [(-3.4, 0)]
    for i in range(35):
        x = -3.4 + i * 0.2
        pts += [(x, 0.3 + 0.08 * math.sin(i * 1.7)), (x + 0.1, 0.5 + 0.12 * math.sin(i * 2.3))]
    pts += [(3.4, 0.3), (3.4, 0)]
    p.prism(pts, 0.02)
    return p
