"""The physics rules the user asked for, checked without Blender.

  python tests/test_rules.py      (from blender-addons/)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
from ship_foley import synth as S, profiles as P


def level(h, seeds=6):
    return np.mean([S.peak_db(S.render(S.Hit(h.kind, h.mass, h.speed, h.a_mat, h.a_size, h.b_mat, h.b_size,
                                              h.b_hollow, h.b_mass, seed=k), room_wet=0)) for k in range(seeds)])


def step(d, v, floor="deck"):
    p = P.DROIDS[d]
    return S.Hit("step", p["mass_kg"] * p["leg"], v, p["foot"], p["foot_size"], floor, 1.0)


def grab(d, v):
    p = P.DROIDS[d]
    return S.Hit("grab", p["mass_kg"] * p["arm"], v, p["hand"], p["hand_size"], "metal_thin", 0.3, 0.7, 2.5)


ok = True
def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + ("  " + detail if detail else ""))


for d in ("rx07", "hazard", "hover_drone"):
    a, b, c = level(step(d, 0.15)), level(step(d, 0.4)), level(step(d, 1.0))
    check(f"{d}: faster step is louder", a < b < c, f"{a:.1f} < {b:.1f} < {c:.1f} dB")
r, h, dr = level(step("rx07", 0.4)), level(step("hazard", 0.4)), level(step("hover_drone", 0.4))
check("heavier droid is louder at the same speed", r > h > dr, f"RX-07 {r:.1f} > hazard {h:.1f} > drone {dr:.1f} dB")
slow, fast = level(grab("rx07", 0.08)), level(grab("rx07", 1.2))
check("fast hard grab is louder than a slow pickup", fast - slow > 8, f"{slow:.1f} vs {fast:.1f} dB")
check("fast strike is shorter (brighter) than slow", S.contact_time(grab("rx07", 1.2)) < S.contact_time(grab("rx07", 0.08)))
check("heavier foot strikes longer (deeper)", S.contact_time(step("rx07", 0.4)) > S.contact_time(step("hover_drone", 0.4)))
rug, deck = level(step("rx07", 0.4, "fabric")), level(step("rx07", 0.4, "deck"))
check("rug muffles a step", rug < deck - 6, f"rug {rug:.1f} vs deck {deck:.1f} dB")
f_big = S._modes("metal", 1.0, 0, np.random.default_rng(0))[0][0]
f_small = S._modes("metal", 0.1, 0, np.random.default_rng(0))[0][0]
check("bigger objects ring lower", f_big < f_small, f"{f_big:.0f} Hz vs {f_small:.0f} Hz")
t_hollow = S._modes("metal", 0.5, 0.8, np.random.default_rng(0))[0][2]
t_solid = S._modes("metal", 0.5, 0.0, np.random.default_rng(0))[0][2]
check("hollow things ring longer", t_hollow > t_solid)
x = S.render(step("rx07", 2.5))
check("never clips", np.max(np.abs(x)) <= 1.0)
sys.exit(0 if ok else 1)
