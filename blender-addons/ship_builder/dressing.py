"""Story dressing: the props that make each room look lived in rather than built
from a template (the props list the user approved, 2026-11-07).

    dress(room, key, seed)   # called by each room build, after arch.detail, before wear

Every item is placed with the same collision check as the architecture
(arch._place): if it would touch anything, that spot is dropped and the next
candidate is tried. Items that stand on furniture join that furniture's piece,
so the wear pass moves them together and nothing is left floating.

Wall pass (all rooms): welded patch plates, louvre vents, ribbed plates,
valve wheels, ID tags, clipped cable bundles, small readouts, warning decals,
overhead pipe runs with hangers, taped papers and sticky notes.
"""
import math
import random

import bpy
from mathutils import Vector, Matrix

from . import kit as K
from . import mats as M
from . import arch as A
from .wear import Collider

UP = Vector((0, 0, 1))


# ---------------------------------------------------------------- local frames
class F:
    """Build in a local frame: a along u, b along v (up the wall), c out of the wall."""

    def __init__(self, room, P, u, v, n):
        self.room, self.P, self.u, self.v, self.n = room, Vector(P), Vector(u), Vector(v), Vector(n)
        self.rot = Matrix((self.u, self.v, self.n)).transposed()

    def at(self, a, b, c):
        return self.P + self.u * a + self.v * b + self.n * c

    def box(self, name, size, abc, mat, bevel=0.004, tilt=0.0):
        R = self.rot @ Matrix.Rotation(math.radians(tilt), 3, "Z") if tilt else self.rot
        return K.box(name, size, self.at(*abc), mat, self.room.dress, bevel=bevel, rot=R.to_euler())

    def disc(self, name, r, h, abc, mat, verts=32, bevel=0.003):
        """A cylinder whose axis points out of the surface."""
        return K.cyl(name, r, h, self.at(*abc), mat, self.room.dress, verts=verts, bevel=bevel, rot=self.rot.to_euler())

    def post(self, name, r, h, abc, mat, verts=24, bevel=0.003):
        """A cylinder standing along v."""
        R = self.rot @ Matrix.Rotation(math.radians(-90), 3, "X")
        return K.cyl(name, r, h, self.at(*abc), mat, self.room.dress, verts=verts, bevel=bevel, rot=R.to_euler())


def floor_frame(room, x, y, z, yaw):
    """Local frame lying on a surface: u along the item, v away from it, n up."""
    c, s = math.cos(yaw), math.sin(yaw)
    return F(room, (x, y, z), (c, s, 0), (-s, c, 0), (0, 0, 1))


def _mats(room):
    pal = room.pal
    return dict(
        steel=pal["steel"], dark=pal["dark_steel"], plastic=pal["plastic"], grey=pal["plastic_grey"],
        rubber=pal["rubber"], cream=pal["cream"], accent=pal["accent"], glass=pal["glass"],
        paper=M.plastic("SB Paper", (0.62, 0.6, 0.53, 1), 0.85),
        paper_y=M.plastic("SB Sticky Yellow", (0.75, 0.6, 0.12, 1), 0.8),
        paper_p=M.plastic("SB Sticky Pink", (0.7, 0.25, 0.32, 1), 0.8),
        tape=M.plastic("SB Duct Tape", (0.3, 0.3, 0.29, 1), 0.62),
        red=M.painted_metal("SB Fire Red", (0.45, 0.025, 0.02, 1), 0.3),
        green=M.painted_metal("SB Med Green", (0.08, 0.3, 0.12, 1), 0.4),
        oil=M.liquid("SB Oil", (0.03, 0.018, 0.008, 1)),
        jar=M.glass("SB Jar Glass", (0.75, 0.62, 0.4, 1), 0.06),
        brass=M.brushed_steel("SB Brass", (0.55, 0.4, 0.18, 1), 0.35),
        cloth=M.fabric("SB Rag Cloth", (0.22, 0.18, 0.12, 1)),
        jacket=M.fabric("SB Jacket", (0.12, 0.13, 0.11, 1)),
        rubber_y=M.plastic("SB Yellow Plastic", (0.62, 0.45, 0.04, 1), 0.45),
        blue=M.plastic("SB Blue Plastic", (0.05, 0.16, 0.35, 1), 0.4),
        card=M.plastic("SB Cardboard", (0.32, 0.22, 0.12, 1), 0.9),
        wood=M.plastic("SB Peg Board", (0.3, 0.24, 0.16, 1), 0.7),
        hazard=M.hazard(),
    )


# ---------------------------------------------------------------- placement
class Placer:
    def __init__(self, room, seed):
        self.room = room
        self.rng = random.Random(seed * 131 + len(room.name))
        self.col = Collider(room)
        self.m = _mats(room)
        self.done, self.missed = [], []

    def _support(self, x, y, z_hint):
        """Top surface under (x, y) below z_hint, and the piece that owns it."""
        dg = bpy.context.evaluated_depsgraph_get()
        sc = bpy.context.scene
        hit, loc, _n, _i, ob, _m = sc.ray_cast(dg, Vector((x, y, z_hint)), Vector((0, 0, -1)), distance=z_hint + 0.1)
        if not hit:
            return 0.0, None
        return loc.z, ob

    def try_spots(self, key, spots, build, ignore=("Deck", "Bolt")):
        """spots: callables returning a local frame (or None); build(frame) makes the item."""
        for spot in spots:
            fr = spot()
            if fr is None:
                continue
            made = A._place(self.col, lambda fr=fr: build(fr), ignore=ignore)
            if made:
                self.done.append(key)
                return made
        self.missed.append(key)
        return []

    def on_top(self, x, y, yaw, z_hint=2.6):
        """A frame on whatever surface is under (x, y); joins that furniture's piece afterwards."""
        z, ob = self._support(x, y, z_hint)
        fr = floor_frame(self.room, x, y, z + 0.0004, yaw)
        fr.support = ob
        return fr

    def wall_spots(self, z0, z1, tries=40, walls=None, s_pad=0.5):
        out = []
        wl = [w for w in A.walls(self.room) if walls is None or w[0] in walls]
        for _ in range(tries):
            name, origin, u, n, L = self.rng.choice(wl)
            s = self.rng.uniform(s_pad, L - s_pad)
            z = self.rng.uniform(z0, z1)

            def make(origin=origin, u=u, n=n, s=s, z=z):
                p = origin + u * s + UP * z
                if not A._on_panel(self.room, p + n * 0.02, n):
                    return None
                P, uu, vv, nn = A._frame(origin, u, n, s, z)
                return F(self.room, P, uu, vv, nn)
            out.append(make)
        return out


def _join_support(objs, fr):
    """Items standing on furniture move with it in the wear pass."""
    sup = getattr(fr, "support", None)
    if sup is None:
        return
    pid = sup.get("sb_piece")
    if not pid:
        return
    for o in objs:
        o["sb_piece"] = pid
        o["sb_shift"], o["sb_yaw"] = sup.get("sb_shift", 0.04), sup.get("sb_yaw", 3.0)


# ---------------------------------------------------------------- wall pass (w3 - w12)
def patch_plate(P, m, rng):
    w, h = rng.uniform(0.18, 0.42), rng.uniform(0.14, 0.34)
    P.box("Patch Plate", (w, h, 0.006), (0, 0, 0.003), m["dark"], bevel=0.002, tilt=rng.uniform(-6, 6))
    # weld bead around the edge, then a few rivets
    for a, b, sw, sh in ((0, h / 2, w, 0.008), (0, -h / 2, w, 0.008), (w / 2, 0, 0.008, h), (-w / 2, 0, 0.008, h)):
        P.box("Weld Bead", (sw + 0.006, sh + 0.006, 0.004), (a, b, 0.004), m["steel"], bevel=0.002)


def louvre(P, m, rng):
    w, h = rng.choice(((0.3, 0.22), (0.42, 0.18), (0.24, 0.3)))
    P.box("Louvre Frame", (w, h, 0.02), (0, 0, 0.01), m["dark"], bevel=0.003)
    k = int(h / 0.03)
    for i in range(k):
        P.box("Louvre Slat", (w - 0.03, 0.012, 0.022), (0, -h / 2 + 0.02 + i * (h - 0.04) / max(1, k - 1), 0.016), m["steel"], bevel=0.001, tilt=0)


def ribbed(P, m, rng):
    w, h = rng.uniform(0.3, 0.55), rng.uniform(0.25, 0.45)
    P.box("Ribbed Plate", (w, h, 0.006), (0, 0, 0.003), m["steel"], bevel=0.002)
    for i in range(int(w / 0.04)):
        P.box("Plate Rib", (0.01, h - 0.03, 0.008), (-w / 2 + 0.025 + i * 0.04, 0, 0.009), m["steel"], bevel=0.002)


def valve(P, m, rng):
    """A short pipe stub out of the wall with a hand-wheel valve on it."""
    P.disc("Valve Flange", 0.05, 0.012, (0, 0, 0.006), m["dark"])
    P.post("Valve Pipe", 0.018, 0.36, (0, -0.16, 0.06), m["steel"])
    P.box("Valve Elbow", (0.045, 0.06, 0.06), (0, 0, 0.04), m["steel"], bevel=0.01)
    P.box("Valve Body", (0.07, 0.07, 0.07), (0, -0.2, 0.06), m["brass"], bevel=0.01)
    P.disc("Valve Stem", 0.008, 0.05, (0, -0.2, 0.12), m["steel"])
    wheel = P.disc("Valve Wheel Rim", 0.06, 0.012, (0, -0.2, 0.15), m["red"], verts=32)
    for k in range(3):
        a = k * math.pi / 3
        P.box("Valve Spoke", (0.11, 0.008, 0.006), (0, -0.2, 0.15), m["red"], bevel=0.001, tilt=math.degrees(a))
    P.disc("Valve Hub", 0.014, 0.02, (0, -0.2, 0.152), m["red"])


TAGS = ["B-114", "V3", "HX-2", "LN 07", "C-22", "PWR 4", "AUX", "Q-19", "R/7", "DK-3"]


def id_tag(P, m, rng):
    t = rng.choice(TAGS)
    w = 0.05 + 0.03 * len(t)
    P.box("ID Tag", (w, 0.055, 0.003), (0, 0, 0.0015), m["cream"] if rng.random() < 0.6 else m["accent"], bevel=0.001)
    st = K.stencil(P.room, t, P.at(0, -0.014, 0.0032), P.rot.to_euler(), 0.032, (0.03, 0.03, 0.03, 1))
    st.data.extrude = 0.0003
    for a in (-w / 2 + 0.008, w / 2 - 0.008):
        P.disc("Tag Rivet", 0.004, 0.003, (a, 0.0, 0.0035), m["steel"], verts=12)


def readout(P, m, rng):
    w, h = rng.choice(((0.14, 0.09), (0.2, 0.08), (0.1, 0.1)))
    col = rng.choice(((0.4, 1.0, 0.5, 1), (1.0, 0.65, 0.2, 1), (0.35, 0.85, 1.0, 1)))
    K.screen(P.room, P.at(0, 0, 0), P.u, P.v, P.n, w, h, col, "ui", light=False, name="Readout", strength=1.0, depth=0.03, margin=0.015)


def decal(P, m, rng):
    kind = rng.choice(("hazard", "arrow", "label"))
    if kind == "hazard":
        P.box("Warning Decal", (rng.uniform(0.2, 0.4), 0.06, 0.0015), (0, 0, 0.0008), m["hazard"], bevel=0.0004)
    elif kind == "arrow":
        P.box("Warning Decal", (0.16, 0.05, 0.0015), (0, 0, 0.0008), m["accent"], bevel=0.0004)
        st = K.stencil(P.room, ">>", P.at(0, -0.016, 0.0016), P.rot.to_euler(), 0.04, (0.03, 0.03, 0.03, 1))
        st.data.extrude = 0.0003
    else:
        t = rng.choice(("NO STEP", "HOT", "LIVE 400V", "KEEP CLEAR", "EARTH"))
        P.box("Warning Decal", (0.05 + 0.028 * len(t), 0.055, 0.0015), (0, 0, 0.0008), m["paper_y"], bevel=0.0004)
        st = K.stencil(P.room, t, P.at(0, -0.013, 0.0016), P.rot.to_euler(), 0.03, (0.03, 0.03, 0.03, 1))
        st.data.extrude = 0.0003


def papers(P, m, rng):
    """Taped-up papers and sticky notes, never perfectly square."""
    for k in range(rng.randint(1, 3)):
        a, b = rng.uniform(-0.12, 0.12), rng.uniform(-0.08, 0.08)
        if rng.random() < 0.5:
            P.box("Taped Paper", (0.15, 0.21, 0.0008), (a, b, 0.0004 + k * 0.0009), m["paper"], bevel=0, tilt=rng.uniform(-8, 8))
            P.box("Tape Strip", (0.05, 0.016, 0.0006), (a, b + 0.1, 0.0012 + k * 0.0009), m["tape"], bevel=0, tilt=rng.uniform(-15, 15))
        else:
            P.box("Sticky Note", (0.065, 0.065, 0.0008), (a, b, 0.0004 + k * 0.0009), rng.choice((m["paper_y"], m["paper_p"])), bevel=0, tilt=rng.uniform(-12, 12))


def cable_bundle(room, origin, u, n, s0, s1, z, m, rng):
    """Three or four loose cables clipped to the wall every 40-60 cm, sagging between clips."""
    cols = [m["rubber"], M.plastic("SB Cable Red", (0.35, 0.03, 0.02, 1), 0.45), M.plastic("SB Cable Yellow", (0.6, 0.42, 0.04, 1), 0.45),
            M.plastic("SB Cable Blue", (0.04, 0.12, 0.3, 1), 0.45)]
    k = rng.randint(3, 4)
    clips = [s0]
    while clips[-1] < s1 - 0.3:
        clips.append(min(s1, clips[-1] + rng.uniform(0.4, 0.6)))
    for i in range(k):
        off = 0.035 + i * 0.022
        for a, b in zip(clips, clips[1:]):
            pa = origin + u * a + UP * (z + i * 0.012) + n * off
            pb = origin + u * b + UP * (z + i * 0.012) + n * off
            K.cable(room, pa, pb, sag=rng.uniform(0.01, 0.04), r=0.006, mat=cols[i % len(cols)], name="Bundle Cable")
    for s in clips:
        P = F(room, origin + u * s + UP * z, u, UP, n)
        P.box("Cable Clip", (0.03, 0.07, 0.11), (0, 0.016, 0.055), m["dark"], bevel=0.003)


def overhead_pipes(room, pl):
    """A run of two or three pipes across the ceiling on hangers, with a valve wheel."""
    W, D, H = room.W, room.D, room.H
    m, rng = pl.m, pl.rng
    cv = getattr(room, "cove", 0.0)
    for attempt in range(8):
        y = rng.uniform(1.0, D - 1.2)
        z = H - cv - rng.uniform(0.32, 0.5)
        x0, x1 = -W / 2 + 0.35, W / 2 - 0.35
        n_p = rng.randint(2, 3)

        def build(y=y, z=z, x0=x0, x1=x1, n_p=n_p):
            for i in range(n_p):
                yy = y + i * 0.11
                K.pipe(room, [(x0, yy, z - i * 0.02), (x1, yy, z - i * 0.02)], rng.choice((0.022, 0.03, 0.04)),
                       rng.choice((m["steel"], m["dark"], M.painted_metal("SB Pipe Green", (0.1, 0.18, 0.1, 1), 0.5))), flanges=True, name="Overhead Pipe")
            hx = x0 + 0.4
            while hx < x1 - 0.2:
                K.box("Pipe Hanger", (0.02, n_p * 0.11 + 0.06, 0.02), (hx, y + (n_p - 1) * 0.055, z - 0.06), m["dark"], room.dress, bevel=0.003)
                K.cyl("Hanger Rod", 0.006, H - cv - (z - 0.06), (hx, y + (n_p - 1) * 0.055, (H - cv + z - 0.06) / 2), m["steel"], room.dress, verts=12)
                hx += rng.uniform(0.9, 1.3)
            vx = rng.uniform(x0 + 0.6, x1 - 0.6)
            P = F(room, (vx, y, z), (1, 0, 0), (0, 1, 0), (0, 0, -1))
            P.disc("Valve Wheel Rim", 0.07, 0.012, (0, 0, 0.07), m["red"])
            P.disc("Valve Stem", 0.008, 0.06, (0, 0, 0.04), m["steel"])
            for k in range(3):
                P.box("Valve Spoke", (0.13, 0.008, 0.006), (0, 0, 0.07), m["red"], bevel=0.001, tilt=60 * k)
        if A._place(pl.col, build, ignore=("Bolt", "Hanger Rod", "Air Duct", "Cable Tray")):
            pl.done.append("w11")
            return
    pl.missed.append("w11")


def wall_pass(room, pl, density=1.0):
    m, rng = pl.m, pl.rng
    H = room.H - getattr(room, "cove", 0.0)
    jobs = [("w3", patch_plate, (0.3, 2.2), 4), ("w4", louvre, (0.25, 0.6), 3), ("w5", ribbed, (0.3, 1.9), 3),
            ("w6", valve, (0.9, 1.6), 2), ("w7", id_tag, (1.2, 2.1), 6), ("w9", readout, (1.2, 1.7), 3),
            ("w10", decal, (0.2, 2.0), 5), ("w12", papers, (1.1, 1.7), 4)]
    for key, fn, (z0, z1), n in jobs:
        for i in range(max(1, int(round(n * density)))):
            pl.try_spots(key, pl.wall_spots(z0, min(z1, H - 0.4)), lambda fr, fn=fn: fn(fr, m, rng),
                         ignore=("Deck", "Bolt", "Rivets"))
    # clipped cable bundles along the walls (w8)
    wl = A.walls(room)
    for k in range(max(1, int(2 * density))):
        for attempt in range(12):
            name, origin, u, n, L = rng.choice(wl)
            s0 = rng.uniform(0.4, max(0.5, L - 1.6))
            s1 = min(L - 0.3, s0 + rng.uniform(0.9, 1.6))
            z = rng.uniform(0.55, 1.0) if rng.random() < 0.5 else rng.uniform(2.0, min(2.3, H - 0.4))
            if A._place(pl.col, lambda origin=origin, u=u, n=n, s0=s0, s1=s1, z=z: cable_bundle(room, origin, u, n, s0, s1, z, m, rng),
                        ignore=("Deck", "Bolt", "Rivets")):
                pl.done.append("w8")
                break
    overhead_pipes(room, pl)


# ---------------------------------------------------------------- props: shared builders
def jar(P, m, a, b, r, h, crack=False):
    P.post("Oil Jar", r, h, (a, b + h / 2, r + 0.004), m["jar"], verts=24)
    P.post("Jar Oil", r * 0.86, h * 0.6, (a, b + h * 0.3 + 0.003, r + 0.004), m["oil"], verts=24)
    lid = P.post("Jar Lid", r * 1.05, 0.016, (a, b + h + 0.008, r + 0.004), m["dark"], verts=24)
    if crack:
        lid.rotation_euler.rotate_axis("X", math.radians(9))


def shelf_of_jars(P, m, rng):
    P.box("Shelf Board", (0.8, 0.02, 0.18), (0, 0, 0.09), m["dark"], bevel=0.003)
    for a in (-0.3, 0.3):
        P.box("Shelf Bracket", (0.02, 0.12, 0.14), (a, -0.07, 0.07), m["steel"], bevel=0.002)
    x = -0.33
    for i in range(5):
        r, h = rng.uniform(0.03, 0.045), rng.uniform(0.09, 0.16)
        jar(P, m, x + r, 0.01, r, h, crack=(i == 2))
        x += 2 * r + rng.uniform(0.02, 0.05)


def poster(P, m, rng, text, crooked=0.0, col=(0.2, 0.35, 0.55, 1)):
    t = crooked
    P.box("Poster Frame", (0.5, 0.7, 0.012), (0, 0, 0.006), m["dark"], bevel=0.003, tilt=t)
    P.box("Poster Print", (0.46, 0.66, 0.002), (0, 0, 0.013), M.plastic(f"SB Poster {text[:6]}", col, 0.8), bevel=0, tilt=t)
    R = (P.rot @ Matrix.Rotation(math.radians(t), 3, "Z")).to_euler()
    st = K.stencil(P.room, text, P.at(0, -0.22, 0.0146), R, 0.05, (0.85, 0.75, 0.5, 1))
    st.data.extrude = 0.0003


def clock(P, m, rng):
    P.disc("Clock Body", 0.13, 0.04, (0, 0, 0.02), m["dark"], verts=48)
    P.disc("Clock Face", 0.115, 0.004, (0, 0, 0.042), m["cream"], verts=48, bevel=0)
    P.box("Clock Hand", (0.006, 0.08, 0.002), (0.02, 0.03, 0.046), m["dark"], bevel=0, tilt=-35)
    P.box("Clock Hand", (0.005, 0.1, 0.002), (-0.03, 0.03, 0.047), m["dark"], bevel=0, tilt=50)
    P.disc("Clock Glass", 0.118, 0.003, (0, 0, 0.05), m["glass"], verts=48, bevel=0)
    P.box("Glass Crack", (0.002, 0.15, 0.0005), (0.03, -0.01, 0.0517), m["paper"], bevel=0, tilt=28)


def tool_rack(P, m, rng):
    P.box("Peg Board", (0.6, 0.45, 0.012), (0, 0, 0.006), m["wood"], bevel=0.002)
    for i in range(3):
        P.box("Peg", (0.008, 0.008, 0.05), (-0.2 + i * 0.2, 0.12, 0.037), m["steel"], bevel=0.001)
    P.box("Wrench", (0.03, 0.26, 0.008), (-0.2, 0.0, 0.03), m["steel"], bevel=0.003)
    P.box("Wrench", (0.026, 0.2, 0.008), (0.0, 0.03, 0.03), m["steel"], bevel=0.003)
    P.box("Hammer Handle", (0.03, 0.26, 0.022), (0.2, 0.0, 0.03), m["rubber_y"], bevel=0.006)
    P.box("Hammer Head", (0.12, 0.035, 0.035), (0.2, 0.14, 0.03), m["dark"], bevel=0.006)


def coat_hook(P, m, rng):
    P.box("Hook Plate", (0.08, 0.04, 0.008), (0, 0, 0.004), m["steel"], bevel=0.002)
    P.box("Hook", (0.012, 0.012, 0.07), (0, 0, 0.04), m["steel"], bevel=0.004)
    P.box("Hook Tip", (0.012, 0.03, 0.012), (0, 0.012, 0.075), m["steel"], bevel=0.004)
    r = K.rounded("Hanging Rag", (0.16, 0.34, 0.012), P.at(0, -0.15, 0.088), m["cloth"], P.room.dress, rot=P.rot.to_euler(), wrinkle=0.006)


def first_aid(P, m, rng):
    P.box("First Aid Box", (0.3, 0.26, 0.11), (0, 0, 0.0555), m["green"], bevel=0.01)
    P.box("First Aid Cross", (0.09, 0.028, 0.002), (0, 0.02, 0.112), m["cream"], bevel=0)
    P.box("First Aid Cross", (0.028, 0.09, 0.002), (0, 0.02, 0.112), m["cream"], bevel=0)
    P.box("First Aid Latch", (0.04, 0.02, 0.012), (0.12, 0, 0.117), m["steel"], bevel=0.002)


def hose_reel(P, m, rng):
    P.box("Reel Bracket", (0.3, 0.3, 0.02), (0, 0, 0.01), m["red"], bevel=0.003)
    P.disc("Reel Drum", 0.13, 0.12, (0, 0, 0.09), m["red"], verts=40)
    for d in (0.03, 0.15):
        P.disc("Reel Flange", 0.16, 0.008, (0, 0, d), m["red"], verts=40)
    for k in range(4):
        P.disc("Hose Wrap", 0.137 + k * 0.001, 0.025, (0, 0, 0.05 + k * 0.026), m["rubber"], verts=40, bevel=0.008)
    P.post("Hose Nozzle", 0.014, 0.12, (0.15, -0.12, 0.1), m["brass"])


def fuse_box(P, m, rng):
    P.box("Fuse Box", (0.32, 0.42, 0.1), (0, 0, 0.05), m["grey"], bevel=0.006)
    P.box("Fuse Box Inside", (0.28, 0.38, 0.004), (0, 0, 0.098), m["dark"], bevel=0)
    for i in range(6):
        P.box("Breaker", (0.03, 0.06, 0.02), (-0.1 + i * 0.04, 0.06, 0.105), m["plastic"], bevel=0.002)
        P.box("Breaker Toggle", (0.01, 0.02, 0.012), (-0.1 + i * 0.04, 0.07 if i != 3 else 0.05, 0.118), m["accent"] if i == 3 else m["dark"], bevel=0.001)
    # the door hangs ajar on its left hinge
    door = P.box("Fuse Box Door", (0.32, 0.42, 0.012), (0, 0, 0.106), m["grey"], bevel=0.003)
    hinge = P.at(-0.16, 0, 0.106)
    T = Matrix.Translation(hinge) @ Matrix.Rotation(math.radians(-35), 4, P.v) @ Matrix.Translation(-hinge)
    door.matrix_world = T @ door.matrix_world


def notice_board(P, m, rng):
    P.box("Notice Board", (0.7, 0.5, 0.015), (0, 0, 0.0075), m["card"], bevel=0.003)
    P.box("Board Frame", (0.74, 0.54, 0.008), (0, 0, 0.004), m["dark"], bevel=0.002)
    for k in range(6):
        a, b = rng.uniform(-0.26, 0.26), rng.uniform(-0.17, 0.17)
        P.box("Pinned Paper", (rng.uniform(0.08, 0.15), rng.uniform(0.1, 0.19), 0.0008), (a, b, 0.016 + k * 0.0009),
              rng.choice((m["paper"], m["paper_y"], m["paper_p"])), bevel=0, tilt=rng.uniform(-10, 10))
        P.disc("Pin", 0.006, 0.008, (a, b + 0.05, 0.022 + k * 0.0009), m["red"], verts=10, bevel=0.001)


def headset_hook(P, m, rng):
    P.box("Hook Plate", (0.06, 0.06, 0.008), (0, 0, 0.004), m["steel"], bevel=0.002)
    P.box("Hook", (0.014, 0.014, 0.08), (0, 0, 0.044), m["steel"], bevel=0.004)
    P.box("Headset Band", (0.16, 0.025, 0.03), (0, -0.01, 0.07), m["dark"], bevel=0.008)
    for a in (-0.08, 0.08):
        P.disc("Headset Cup", 0.04, 0.03, (a, -0.07, 0.07), m["rubber"], verts=24)
    P.box("Headset Mic", (0.008, 0.11, 0.008), (0.09, -0.13, 0.08), m["dark"], bevel=0.003, tilt=25)


def blanket_box(P, m, rng):
    P.box("Fire Blanket Box", (0.26, 0.3, 0.08), (0, 0, 0.04), m["red"], bevel=0.008)
    P.box("Blanket Tabs", (0.04, 0.05, 0.01), (-0.06, -0.15, 0.04), m["cream"], bevel=0.002)
    P.box("Blanket Tabs", (0.04, 0.05, 0.01), (0.06, -0.15, 0.04), m["cream"], bevel=0.002)
    st = K.stencil(P.room, "FIRE", P.at(0, 0.03, 0.0805), P.rot.to_euler(), 0.05, (0.9, 0.9, 0.85, 1))
    st.data.extrude = 0.0003


def star_chart(P, m, rng):
    poster(P, m, rng, "SECTOR 7", crooked=rng.uniform(-2, 2), col=(0.02, 0.03, 0.08, 1))
    for k in range(4):  # corners curling: little lifted triangles
        a, b = (-0.22 if k % 2 else 0.22), (-0.32 if k < 2 else 0.32)
        P.box("Curled Corner", (0.05, 0.05, 0.002), (a, b, 0.017), m["paper"], bevel=0, tilt=45)


# ---------------------------------------------------------------- props on floors and furniture
def parts_bin(P, m, rng):
    w, d, h = 0.4, 0.3, 0.26
    P.box("Bin Floor", (w, d, 0.012), (0, 0, 0.006), m["dark"], bevel=0.002)
    for a, b, sw, sd in ((0, d / 2, w, 0.012), (0, -d / 2, w, 0.012), (w / 2, 0, 0.012, d), (-w / 2, 0, 0.012, d)):
        P.box("Bin Wall", (sw, sd, h), (a, b, h / 2), m["dark"], bevel=0.002)
    for k in range(6):
        P.disc("Spare Gear", rng.uniform(0.025, 0.05), 0.012, (rng.uniform(-0.12, 0.12), rng.uniform(-0.08, 0.08), h - 0.03 + k * 0.004), m["steel"], verts=16)
    P.box("Loose Servo", (0.06, 0.04, 0.035), (0.08, 0.05, h - 0.0), m["blue"], bevel=0.004)


def spool(P, m, rng):
    for d in (0.0125, 0.2375):
        P.box("Spool Flange", (0.012, 0.36, 0.36), (d, 0, 0.18), m["wood"], bevel=0.003)
    P.box("Spool Core", (0.22, 0.2, 0.2), (0.125, 0, 0.18), m["rubber"], bevel=0.02)
    # the loose end runs out across the floor
    a = P.at(0.125, -0.1, 0.09)
    pts = [a, P.at(0.15, -0.3, 0.008), P.at(0.25, -0.6, 0.008), P.at(0.5, -0.75, 0.008)]
    cu = bpy.data.curves.new("Floor Cable", "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.008, 4
    sp = cu.splines.new("NURBS")
    sp.points.add(len(pts) - 1)
    for p, q in zip(sp.points, pts):
        p.co = (*q, 1)
    sp.use_endpoint_u, sp.order_u = True, 3
    ob = bpy.data.objects.new("Floor Cable", cu)
    P.room.dress.objects.link(ob)
    cu.materials.append(m["rubber"])


def pad_stack(P, m, rng):
    for k in range(4):
        P.box("Magazine" if k % 2 else "Old Datapad", (0.2, 0.27, 0.008 if k % 2 else 0.012),
              (rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01), 0.006 + k * 0.012), m["paper"] if k % 2 else m["dark"], bevel=0.002, tilt=rng.uniform(-9, 9))


def bottle_crate(P, m, rng):
    P.box("Bottle Crate", (0.42, 0.3, 0.2), (0, 0, 0.1), m["rubber_y"], bevel=0.01)
    for i in range(3):
        for j in range(2):
            P.post("Oil Bottle", 0.032, 0.22, (-0.12 + i * 0.12, -0.06 + j * 0.12, 0.11), m["oil"], verts=16)
            P.post("Bottle Cap", 0.016, 0.02, (-0.12 + i * 0.12, -0.06 + j * 0.12, 0.23), m["red"], verts=12)


def snack_bowl(P, m, rng):
    P.disc("Snack Bowl", 0.08, 0.04, (0, 0, 0.02), m["steel"], verts=32)
    for k in range(7):
        P.box("Snack Bolt", (0.012, 0.035, 0.012), (rng.uniform(-0.04, 0.04), rng.uniform(-0.04, 0.04), 0.046 + k * 0.003), m["steel"], bevel=0.003, tilt=rng.uniform(0, 180))


def board_game(P, m, rng):
    P.box("Game Board", (0.36, 0.36, 0.008), (0, 0, 0.004), m["cream"], bevel=0.002)
    P.box("Game Lid", (0.3, 0.2, 0.03), (0.33, 0.05, 0.015), m["blue"], bevel=0.003, tilt=14)
    for k in range(6):
        P.post("Game Piece", 0.009, 0.03, (rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), 0.008 + 0.015), rng.choice((m["red"], m["blue"], m["rubber_y"])), verts=12)


def console_set(P, m, rng):
    P.box("Game Console", (0.3, 0.22, 0.06), (0, 0, 0.03), m["dark"], bevel=0.008)
    P.box("Console LED", (0.03, 0.004, 0.004), (0.1, -0.111, 0.04), M.emissive("SB Console LED", (0.3, 1.0, 0.5, 1), 4), bevel=0)


def controller(P, m, rng):
    P.box("Game Controller", (0.16, 0.1, 0.035), (0, 0, 0.0175), m["dark"], bevel=0.015)
    for a in (-0.035, 0.035):
        P.disc("Thumbstick", 0.01, 0.014, (a, -0.01, 0.042), m["rubber"], verts=12)


def binders(P, m, rng):
    for k in range(3):
        P.box("Binder", (0.24, 0.31, 0.045), (rng.uniform(-0.015, 0.015), 0, 0.0225 + k * 0.046),
              rng.choice((m["blue"], m["red"], m["dark"])), bevel=0.004, tilt=rng.uniform(-8, 8))
    P.box("Manual", (0.2, 0.28, 0.02), (0.02, 0.01, 0.148), m["paper"], bevel=0.002, tilt=17)


def cups(P, m, rng):
    for k in range(rng.randint(3, 4)):
        a, b = rng.uniform(-0.1, 0.1), rng.uniform(-0.07, 0.07)
        P.post("Coffee Cup", 0.035, 0.09, (a, b, 0.045), rng.choice((m["cream"], m["steel"], m["grey"])), verts=20)


def clipboard(P, m, rng):
    P.box("Clipboard", (0.23, 0.32, 0.006), (0, 0, 0.003), m["wood"], bevel=0.002)
    P.box("Checklist", (0.21, 0.28, 0.001), (0, -0.01, 0.0065), m["paper"], bevel=0)
    P.box("Board Clip", (0.09, 0.03, 0.012), (0, 0.15, 0.012), m["steel"], bevel=0.003)


def nameplate(P, m, rng):
    P.box("Nameplate", (0.24, 0.05, 0.06), (0, 0, 0.03), m["brass"], bevel=0.004)
    st = K.stencil(P.room, "CAPTAIN", P.at(0, -0.026, 0.03), (P.rot @ Matrix.Rotation(math.radians(90), 3, "X")).to_euler(), 0.028, (0.05, 0.03, 0.01, 1))
    st.data.extrude = 0.0003


def bobblehead(P, m, rng):
    P.box("Bobble Base", (0.05, 0.05, 0.012), (0, 0, 0.006), m["dark"], bevel=0.003)
    P.box("Bobble Body", (0.035, 0.03, 0.05), (0, 0, 0.037), m["rubber_y"], bevel=0.008)
    P.post("Bobble Spring", 0.004, 0.015, (0, 0, 0.07), m["steel"], verts=8)
    K.rounded("Bobble Head", (0.06, 0.055, 0.05), P.at(0, 0, 0.1), m["rubber_y"], P.room.dress)


def monitor_box(P, m, rng):
    w, d, h = 0.62, 0.22, 0.46
    P.box("Box Floor", (w, d, 0.006), (0, 0, 0.003), m["card"], bevel=0.001)
    for a, b, sw, sd in ((0, d / 2, w, 0.006), (0, -d / 2, w, 0.006), (w / 2, 0, 0.006, d), (-w / 2, 0, 0.006, d)):
        P.box("Box Wall", (sw, sd, h), (a, b, h / 2), m["card"], bevel=0.001)
    P.box("Box Flap", (w, 0.006, 0.18), (0, d / 2 + 0.07, h + 0.05), m["card"], bevel=0.001)
    P.box("Spare Monitor", (0.56, 0.06, 0.4), (0, 0, 0.21 + 0.03), m["dark"], bevel=0.008)


def toolbox(P, m, rng):
    P.box("Toolbox", (0.46, 0.22, 0.2), (0, 0, 0.1), m["red"], bevel=0.008)
    lid = P.box("Toolbox Lid", (0.46, 0.22, 0.012), (0, 0.13, 0.25), m["red"], bevel=0.003)
    lid.rotation_euler.rotate_axis("X", math.radians(-60))
    P.box("Tool Tray", (0.42, 0.18, 0.02), (0, 0, 0.19), m["dark"], bevel=0.002)
    P.box("Screwdriver", (0.02, 0.18, 0.02), (-0.1, 0, 0.21), m["rubber_y"], bevel=0.006)
    P.box("Spanner", (0.025, 0.2, 0.008), (0.08, 0, 0.205), m["steel"], bevel=0.003)


def floor_cables(P, m, rng):
    """Zip-tied bundle along the floor, one loose end."""
    for i in range(3):
        y = -0.03 + i * 0.02
        pts = [P.at(-0.5, y, 0.009), P.at(-0.1, y + 0.01, 0.009), P.at(0.3, y, 0.009), P.at(0.55, y + (0.12 if i == 2 else 0), 0.009)]
        cu = bpy.data.curves.new("Floor Bundle", "CURVE")
        cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.008, 4
        sp = cu.splines.new("NURBS")
        sp.points.add(len(pts) - 1)
        for p, q in zip(sp.points, pts):
            p.co = (*q, 1)
        sp.use_endpoint_u, sp.order_u = True, 3
        ob = bpy.data.objects.new("Floor Bundle", cu)
        P.room.dress.objects.link(ob)
        cu.materials.append([m["rubber"], M.plastic("SB Cable Red", (0.35, 0.03, 0.02, 1), 0.45), m["blue"]][i])
    for a in (-0.3, 0.1):
        P.box("Zip Tie", (0.012, 0.09, 0.03), (a, 0.0, 0.015), m["dark"], bevel=0.003)


def boots(P, m, rng):
    for a in (-0.08, 0.08):
        P.box("Boot Sole", (0.1, 0.28, 0.03), (a, 0, 0.015), m["rubber"], bevel=0.008, tilt=rng.uniform(-8, 8))
        K.rounded("Boot Upper", (0.1, 0.16, 0.18), P.at(a, 0.05, 0.12), m["jacket"], P.room.dress, rot=P.rot.to_euler())


def wet_sign(P, m, rng):
    for s in (-1, 1):
        b = P.box("Sign Board", (0.3, 0.012, 0.6), (0, s * 0.1, 0.3), m["rubber_y"], bevel=0.004)
        b.rotation_euler.rotate_axis("X", math.radians(s * 9.5))
    st = K.stencil(P.room, "WET", P.at(0, -0.112, 0.4), (P.rot @ Matrix.Rotation(math.radians(80), 3, "X")).to_euler(), 0.06, (0.03, 0.03, 0.03, 1))
    st.data.extrude = 0.0003


def mop_bucket(P, m, rng):
    P.box("Bucket Body", (0.34, 0.28, 0.3), (0, 0, 0.17), m["rubber_y"], bevel=0.03)
    P.box("Bucket Water", (0.3, 0.24, 0.004), (0, 0, 0.27), m["oil"], bevel=0)
    for a in (-0.13, 0.13):
        for b in (-0.1, 0.1):
            P.post("Caster", 0.02, 0.02, (a, b, 0.01), m["dark"], verts=12)
    P.post("Mop Handle", 0.012, 1.25, (0.06, 0.02, 0.27 + 0.62), m["wood"], verts=12)


def crates(P, m, rng):
    P.box("Cargo Crate", (0.6, 0.45, 0.45), (0, 0, 0.225), m["dark"], bevel=0.012)
    P.box("Cargo Crate", (0.46, 0.4, 0.34), (0.02, 0.01, 0.62), m["accent"], bevel=0.012, tilt=4)
    P.box("Crate Strap", (0.62, 0.04, 0.82), (0, 0, 0.41), m["rubber_y"], bevel=0.003)
    st = K.stencil(P.room, "C-22", P.at(0, -0.228, 0.25), (P.rot @ Matrix.Rotation(math.radians(90), 3, "X")).to_euler(), 0.07)
    st.data.extrude = 0.0003


def jacket_on_hook(P, m, rng):
    P.box("Hook Plate", (0.05, 0.05, 0.006), (0, 0, 0.0035), m["steel"], bevel=0.002)
    P.box("Hook", (0.012, 0.012, 0.05), (0, 0, 0.031), m["steel"], bevel=0.004)
    K.rounded("Hanging Jacket", (0.28, 0.6, 0.07), P.at(0, -0.28, 0.072), m["jacket"], P.room.dress, rot=P.rot.to_euler(), wrinkle=0.01)


# ---------------------------------------------------------------- per room
def _floor(pl, region, z_hint=0.5, yaw=None, tries=30):
    (x0, x1), (y0, y1) = region
    out = []
    for _ in range(tries):
        x, y = pl.rng.uniform(x0, x1), pl.rng.uniform(y0, y1)
        a = pl.rng.uniform(-math.pi, math.pi) if yaw is None else yaw + math.radians(pl.rng.uniform(-12, 12))
        out.append(lambda x=x, y=y, a=a: pl.on_top(x, y, a, z_hint))
    return out


def _on(pl, region, z_hint, tries=25, yaw=0.0):
    return _floor(pl, region, z_hint, yaw, tries)


def _put_on(pl, key, spots, fn):
    """Place the item at the first clear spot; it joins the piece it stands on."""
    for spot in spots:
        fr = spot()
        if fr is None:
            continue
        made = A._place(pl.col, lambda fr=fr: fn(fr, pl.m, pl.rng), ignore=("Deck", "Bolt"))
        if made:
            _join_support(made, fr)
            pl.done.append(key)
            return made
    pl.missed.append(key)
    return []


def lounge(room, pl):
    W, D = room.W, room.D
    walls_hi = lambda z0, z1, w=None: pl.wall_spots(z0, z1, walls=w)
    pl.try_spots("l1", walls_hi(1.45, 1.7, ("left", "right")), lambda f: shelf_of_jars(f, pl.m, pl.rng))
    _put_on(pl, "l2", _floor(pl, ((W / 2 - 1.2, W / 2 - 0.4), (3.2, D - 0.6)), 0.6), parts_bin)
    _put_on(pl, "l3", _floor(pl, ((1.0, 2.6), (2.6, 3.9)), 0.6), spool)
    _put_on(pl, "l4", _on(pl, ((2.05, 2.36), (4.75, 5.05)), 0.9), pad_stack)
    pl.try_spots("l5", walls_hi(1.5, 1.8, ("back", "right")), lambda f: poster(f, pl.m, pl.rng, "VISIT RING 9", crooked=0, col=(0.45, 0.2, 0.1, 1)))
    pl.try_spots("l5", walls_hi(1.5, 1.8, ("back", "right")), lambda f: poster(f, pl.m, pl.rng, "OIL IS LIFE", crooked=pl.rng.choice((-6, 7)), col=(0.1, 0.2, 0.3, 1)))
    pl.try_spots("l6", walls_hi(1.55, 1.75, ("right", "left")), lambda f: coat_hook(f, pl.m, pl.rng))
    _put_on(pl, "l7", _floor(pl, ((-W / 2 + 0.3, -W / 2 + 0.9), (4.5, D - 0.4)), 0.6), bottle_crate)
    _put_on(pl, "l8", _on(pl, ((-0.2, 0.3), (3.25, 3.7)), 0.8), snack_bowl)
    _put_on(pl, "l9", _on(pl, ((0.1, 0.75), (3.25, 3.7)), 0.8), board_game)
    pl.try_spots("l10", walls_hi(2.1, 2.35), lambda f: clock(f, pl.m, pl.rng))
    pl.try_spots("l11", walls_hi(1.2, 1.5, ("right", "back")), lambda f: tool_rack(f, pl.m, pl.rng))
    _put_on(pl, "l12", _on(pl, ((-0.2, 0.8), (3.25, 3.7)), 0.35, yaw=0.0), console_set)  # on the table's lower shelf
    _put_on(pl, "l12", _on(pl, ((-0.25, 0.85), (3.2, 3.75)), 0.8), controller)


def bridge(room, pl):
    W, D = room.W, room.D
    walls_hi = lambda z0, z1, w=None: pl.wall_spots(z0, z1, walls=w)
    desk = lambda: _on(pl, ((-3.5, -1.65), (5.42, 5.6)), 1.4)  # the front lip of the console desks
    _put_on(pl, "b1", desk(), binders)
    pl.try_spots("b2", walls_hi(1.4, 1.7, ("left", "right")), lambda f: headset_hook(f, pl.m, pl.rng))
    # sticky notes on the console screen bezels
    for scr in [o for o in room.dress.objects if o.name.startswith("Console Screen Bezel")][:3]:
        mw = scr.matrix_world
        u, v, n = (mw.to_3x3() @ Vector(a) for a in ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        hx, hy, hz = scr.dimensions.x / 2, scr.dimensions.y / 2, scr.dimensions.z / 2
        for k in range(2):
            P = F(room, mw.translation + n * (hz + 0.0006) + u * (pl.rng.choice((-1, 1)) * (hx - 0.03)) + v * (pl.rng.uniform(-hy, hy) * 0.6), u, v, n)
            made = A._place(pl.col, lambda P=P: P.box("Sticky Note", (0.05, 0.05, 0.0008), (0, 0, 0), pl.rng.choice((pl.m["paper_y"], pl.m["paper_p"])), bevel=0, tilt=pl.rng.uniform(-12, 12)),
                            ignore=("Console Screen", "Bolt"))
            if made:
                _join_support(made, type("S", (), {"support": scr})())
                pl.done.append("b3")
    _put_on(pl, "b4", _floor(pl, ((W / 2 - 1.6, W / 2 - 0.5), (2.2, 4.8)), 0.8), monitor_box)
    _put_on(pl, "b5", desk(), cups)
    _put_on(pl, "b6", desk(), clipboard)
    _put_on(pl, "b7", _floor(pl, ((-3.4, -1.8), (5.05, 5.3)), 0.3, yaw=0.0), floor_cables)
    pl.try_spots("b8", walls_hi(1.2, 1.5, ("left", "right")), lambda f: blanket_box(f, pl.m, pl.rng))
    pl.try_spots("b9", walls_hi(1.4, 1.8, ("left", "right")), lambda f: star_chart(f, pl.m, pl.rng))
    _put_on(pl, "b10", desk(), nameplate)
    _put_on(pl, "b11", desk(), bobblehead)
    _put_on(pl, "b12", _floor(pl, ((-1.4, 0.2), (5.0, 6.4)), 0.5), toolbox)


def corridor(room, pl):
    W, D = room.W, room.D
    walls_hi = lambda z0, z1, w=None, t=60: pl.wall_spots(z0, z1, walls=w, tries=t)
    pl.try_spots("c1", walls_hi(1.3, 1.6, ("back",)), lambda f: notice_board(f, pl.m, pl.rng))
    _put_on(pl, "c2", _floor(pl, ((0.3, 0.85), (3.45, 3.62)), 0.38, yaw=0.0), boots)  # under the bench seat
    # the jacket hangs on the locker's side
    tall = [o for o in room.dress.objects if o.name.startswith("Locker") and o.dimensions.z > 1.5]
    lk = max(tall, key=lambda o: o.matrix_world.translation.x, default=None)  # the outer one
    if lk:
        bb = [lk.matrix_world @ Vector(c) for c in lk.bound_box]
        x1 = max(v.x for v in bb)
        y0, y1 = min(v.y for v in bb), max(v.y for v in bb)
        P = F(room, (x1, (y0 + y1) / 2, 1.62), (0, 1, 0), (0, 0, 1), (1, 0, 0))
        made = A._place(pl.col, lambda: jacket_on_hook(P, pl.m, pl.rng), ignore=("Bolt",))
        if made:
            _join_support(made, type("S", (), {"support": lk})())
        (pl.done if made else pl.missed).append("c3")
    _put_on(pl, "c4", _floor(pl, ((-0.9, 1.0), (2.45, 2.8)), 0.8, yaw=0.0), wet_sign)
    _put_on(pl, "c5", _floor(pl, ((1.0, 1.5), (2.7, 3.6)), 0.8), mop_bucket)
    _put_on(pl, "c6", _floor(pl, ((-1.6, -1.0), (2.8, 3.5)), 1.6, yaw=0.0), crates)
    pl.try_spots("c7", walls_hi(0.9, 1.8, t=300), lambda f: first_aid(f, pl.m, pl.rng))
    pl.try_spots("c8", walls_hi(0.9, 1.3), lambda f: hose_reel(f, pl.m, pl.rng))
    pl.try_spots("c9", walls_hi(1.2, 1.9, t=200), lambda f: fuse_box(f, pl.m, pl.rng))


def charging(room, pl):
    W, D = room.W, room.D
    walls_hi = lambda z0, z1, w=None: pl.wall_spots(z0, z1, walls=w, tries=80)
    pl.try_spots("ch1", walls_hi(1.5, 1.8, ("right",)), lambda f: poster(f, pl.m, pl.rng, "REST = UPTIME", crooked=pl.rng.choice((-4, 5)), col=(0.12, 0.2, 0.38, 1)))
    pl.try_spots("ch2", walls_hi(2.0, 2.3, ("right", "left")), lambda f: clock(f, pl.m, pl.rng))
    _put_on(pl, "ch3", _floor(pl, ((W / 2 - 1.1, W / 2 - 0.45), (2.8, 3.9)), 0.6), parts_bin)
    _put_on(pl, "ch4", _floor(pl, ((-W / 2 + 0.5, -W / 2 + 1.2), (2.8, 3.2)), 0.6), spool)
    pl.try_spots("ch5", walls_hi(1.1, 1.6), lambda f: tool_rack(f, pl.m, pl.rng))


def repair(room, pl):
    W, D = room.W, room.D
    walls_hi = lambda z0, z1, w=None: pl.wall_spots(z0, z1, walls=w, tries=80)
    _put_on(pl, "r1", _floor(pl, ((-3.25, -2.95), (4.5, 5.4)), 0.6, yaw=0.0), toolbox)  # clear of the tool wall stance
    _put_on(pl, "r2", _floor(pl, ((2.4, 3.0), (5.0, 5.5)), 1.6, yaw=0.0), crates)
    pl.try_spots("r3", walls_hi(1.5, 1.8, ("right",)), lambda f: poster(f, pl.m, pl.rng, "HAVE YOU TRIED A REBOOT", crooked=pl.rng.choice((-5, 6)), col=(0.4, 0.15, 0.1, 1)))
    pl.try_spots("r4", walls_hi(2.1, 2.4, ("left", "right")), lambda f: clock(f, pl.m, pl.rng))
    _put_on(pl, "r5", _floor(pl, ((1.95, 2.5), (5.05, 5.5)), 0.6), parts_bin)  # out of the walk to the cart
    pl.try_spots("r6", walls_hi(1.3, 1.6, ("left",)), lambda f: first_aid(f, pl.m, pl.rng))
    _put_on(pl, "r7", _floor(pl, ((2.6, 3.0), (4.25, 4.6)), 0.6), spool)


ROOMS = {"lounge": lounge, "bridge": bridge, "corridor": corridor, "charging": charging, "repair": repair}


def dress(room, key, seed=1, density=1.0):
    """Story props for the room, then the wall pass. Returns {'placed': [...], 'missed': [...]}."""
    pl = Placer(room, seed)
    fn = ROOMS.get(key)
    if fn:
        fn(room, pl)
    wall_pass(room, pl, density)
    return {"placed": pl.done, "missed": pl.missed}
