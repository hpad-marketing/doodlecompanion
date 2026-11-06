"""Joint motors: whir, whine and grind while a droid's parts turn.

Every bone that carries parts and isn't passive (antennas, cables and springs
swing freely) is treated as a motor. Each sample reads its rotation relative
to the part it hangs from, so a shin turning on the knee is the knee motor.

How a motor sounds:
* Pitch follows turning speed through the gearbox. It rises as the joint
  speeds up and drops back as it slows. Heavy droids have big, slow, low
  motors; the drone has small, quick, high servos. Leg motors are bigger than
  arm motors, and finger servos are tiny.
* Level follows speed and load. A leg carrying the body strains harder than
  an arm waving, and the motors of the leg that just landed strain hardest as
  it takes the weight.
* Gear mesh. The teeth make a rough buzz on the whine. Under load there's
  grind noise, and a quick hydraulic hiss when a joint starts or stops.
* A clunk when a joint stops hard (stop events, from the impact model).

Tracks are rendered per limb group (leg.L, arm.R, torso ...) for the whole
shot and laid in as one strip each.
"""
import math
import re

import numpy as np

from . import synth as S

PASSIVE = re.compile(r"^(SPR-|MCH-|WGT|IK_|IK-|pole|roll_|root$|COG$)|antenna_[LR]?_?\d|cable|hose|spring|tether", re.I)
GROUPS = (
    ("hand", re.compile(r"^f_|claw|grip|thumb|finger", re.I), 0.33, 0.04),
    ("leg", re.compile(r"thigh|shin|knee|foot|toe|ankle|hip(?!s)|leg", re.I), 1.0, 1.0),
    ("arm", re.compile(r"upper_arm|forearm|shoulder|elbow|wrist|hand|arm_|pauldron", re.I), 0.65, 0.25),
    ("head", re.compile(r"head|sensor|eye|neck|visor|lid|brow|iris|focus|radar|louvre|thruster|vector|antenna_fold|hatch", re.I), 0.45, 0.06),
    ("torso", re.compile(r"waist|hips|spine|body|chest|pelvis|turntable", re.I), 0.85, 0.6),
)
OMEGA_REF = 3.0          # rad/s: a brisk joint move


def _group(name):
    side = re.search(r"\.([LR])$", name)
    for g, rx, size, load in GROUPS:
        if rx.search(name):
            return ("%s.%s" % (g, side.group(1)) if side else g), size, load
    return None, 0, 0


class Joint:
    __slots__ = ("bone", "parent", "group", "size", "load", "q", "omega", "pos")

    def __init__(self, bone, parent, group, size, load):
        self.bone, self.parent, self.group, self.size, self.load = bone, parent, group, size, load
        self.q, self.omega, self.pos = None, [], []


def joints(arm):
    """Motor joints of a droid: part-carrying bones, minus passive ones."""
    carriers = {o.parent_bone for o in arm.children_recursive if o.parent_type == "BONE" and o.parent_bone}
    out = []
    for name in sorted(carriers):
        if PASSIVE.search(name):
            continue
        g, size, load = _group(name)
        if g is None:
            continue
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        par = pb.parent
        while par is not None and par.name not in carriers:
            par = par.parent
        out.append(Joint(pb, par, g, size, load))
    return out


def sample(arm, js, t, span=1.0 / 24):
    """Record each joint's turning speed (rad/s) at time t, measured over one
    frame (sub-frame steps of keyed or jittered motion would read as buzz)."""
    mw = arm.matrix_world
    for j in js:
        m = j.bone.matrix if j.parent is None else j.parent.matrix.inverted_safe() @ j.bone.matrix
        q = m.to_quaternion()
        if j.q is None:
            j.q = []
        j.q.append((t, q))
        while len(j.q) > 1 and j.q[0][0] < t - span - 1e-6:
            j.q.pop(0)
        t0, q0 = j.q[0]
        w = q.rotation_difference(q0).angle / (t - t0) if t > t0 else 0.0
        if w > 40:
            w = 0.0
        j.omega.append((t, w))
        j.pos.append((mw @ j.bone.head).copy())


def stop_clunks(arm_label, js, prof, fps, f0):
    """Joints that were moving briskly and stop dead make a short clunk.
    One per limb group within 80 ms, at most one per joint every 0.3 s."""
    raw = []
    for j in js:
        om = j.omega
        last = -9.0
        for i in range(4, len(om) - 2):
            before = [w for _, w in om[i - 4:i]]
            after = [w for _, w in om[i:i + 3]]
            w_prev = sum(before) / len(before)
            if min(before) > 1.5 and max(after) < 0.25 * w_prev and om[i][0] - last > 0.3:
                last = t = om[i][0]
                lever = 0.18 * j.size
                raw.append(dict(
                    frame=f0 + t * fps, time=t, kind="clunk", who=arm_label, limb=j.group,
                    loc=tuple(j.pos[i]), surface=j.bone.name, pan=0.0, dist=3.0, on_screen=True,
                    hit=dict(kind="bump", mass=max(prof["mass_kg"] * j.load * 0.08, 0.05), speed=w_prev * lever,
                             a_mat="metal", a_size=0.08 * j.size + 0.02, b_mat="metal",
                             b_size=0.2 * j.size + 0.04, b_hollow=0.3, b_mass=None)))
    raw.sort(key=lambda e: e["time"])
    out = []
    for e in raw:
        o = next((o for o in reversed(out) if o["limb"] == e["limb"] and e["time"] - o["time"] < 0.08), None)
        if o is None:
            out.append(e)
        elif e["hit"]["speed"] > o["hit"]["speed"]:
            o.update(e)
    return out


def _lp_noise(rng, n, hz):
    x = S._lowpass(rng.standard_normal(n), hz)
    return x / (np.max(np.abs(x)) + 1e-12)


def _env(times, vals, n, t0):
    t = t0 + np.arange(n) / S.RATE
    return np.interp(t, times, vals, left=0.0, right=0.0)


def render_group(js, prof, duration, strain=(), seed=0, level=1.0):
    """One limb group's motor track (float32 mono) for `duration` seconds.

    strain: [(time, amount)] load spikes, e.g. a foot taking the body's weight."""
    n = int(duration * S.RATE) + 1
    if n < 16 or not js:
        return np.zeros(max(n, 1), np.float32)
    rng = np.random.default_rng(seed)
    mass = prof["mass_kg"]
    base = 190.0 * (240.0 / max(mass, 1.0)) ** 0.33         # Hz: RX-07 190, hazard 270, drone 570
    # (a 55 Hz fundamental was below what phone and laptop speakers play)
    tt = np.arange(n) / S.RATE
    strain_env = np.ones(n)
    for ts, amt in strain:
        k = tt >= ts
        strain_env[k] += amt * np.exp(-(tt[k] - ts) / 0.28)
    out = np.zeros(n)
    for ji, j in enumerate(js):
        times = np.array([o[0] for o in j.omega])
        w = np.array([o[1] for o in j.omega])
        if len(times) < 2 or w.max() < 0.08:
            continue
        # light smoothing on the control rate so tiny jitters don't buzz
        w = np.convolve(w, np.ones(3) / 3, mode="same")
        wa = _env(times, w, n, 0.0)
        x = np.clip(wa / OMEGA_REF, 0, 2.5)
        size_pitch = 1.0 / max(j.size, 0.15) ** 0.9
        f = base * size_pitch * (0.7 + 3.2 * x) * (1 + rng.uniform(-0.04, 0.04))
        phase = 2 * math.pi * np.cumsum(f) / S.RATE
        # real motors aren't clean tones: jitter the phase and roughen the level
        jit = _lp_noise(rng, n, 30.0)
        phase = phase + 0.6 * jit
        whine = sum(np.sin(k * phase) / k ** 1.15 for k in range(1, 7)) * (1 + 0.5 * _lp_noise(rng, n, 60.0))
        whine = 0.6 * whine + 0.9 * S._bandnoise(rng, n, float(np.median(f)) * 2.2, q=1.5)
        teeth = 9 + ji % 5
        mesh = 1.0 + 0.45 * np.sign(np.sin(phase * teeth / 3.0)) * np.abs(np.sin(phase * teeth / 3.0)) ** 4
        load = (mass * j.load / 100.0) ** 0.3 * strain_env if j.group.startswith("leg") else (mass * j.load / 100.0) ** 0.3
        grind_c = min(900 + 1400 * size_pitch, 7000)
        grind = S._bandnoise(rng, n, grind_c, q=0.9) * np.abs(np.sin(phase * teeth / 2.0)) ** 2
        # hiss when the joint speeds up or slows down quickly
        dw = np.abs(np.gradient(w, times)) if len(times) > 2 else np.zeros_like(w)
        acc = np.clip(_env(times, dw, n, 0.0) / 25.0, 0, 1.5)
        hiss = S._bandnoise(rng, n, 5200, q=0.6) * acc * 0.35
        amp = x ** 0.7
        # the gear-mesh whine: teeth x shaft speed, the high servo sing you hear
        # on any robot arm; it rises and falls with the joint
        gph = phase * (teeth * 0.5)
        sing = (np.sin(gph) + 0.35 * np.sin(2 * gph)) * (1 + 0.3 * _lp_noise(rng, n, 40.0))
        sing = np.where(f * teeth * 0.5 < 9000, sing, 0.0)
        out += amp * load * (0.55 * whine * mesh + 0.45 * sing + 0.3 * grind * np.minimum(load, 2.0)) + hiss * load
    # level: an RX-07 leg moving briskly sits about 6-8 dB under a walking step
    out *= 0.11 * level
    out = np.tanh(out * 1.6) / 1.6
    fade = min(n, int(0.01 * S.RATE))
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out.astype(np.float32)
