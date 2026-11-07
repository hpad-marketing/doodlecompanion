"""Moving parts: every hinge, motor, piston and spinner makes its own noise.

Every bone that carries parts is a mechanism, and so is every animated ship
part (doors, hatches, ramps, landing gear, turrets, dishes). Each one gets
the sound its kind of mechanism makes:

  motor    driven joints (hips, knees, shoulders, wrists, necks, fingers):
           gear whine and sing that rise with speed, grind under load
  hinge    pins with no motor of their own (armour plates, hatches, doors,
           antennas, cables, skirts, flaps): stick-slip creak whose rate
           follows the swing, with a pin groan on big parts
  piston   things that slide or extend (piston rods, lids, sliders, struts,
           landing legs): hydraulic hiss and pump chug that follow speed
  spinner  things that turn round and round (radar, fans, rotors, wheels,
           gyros): bearing hum at the blade rate
A tag `foley_mech` on a pose bone or object overrides the guess; `none`
silences it. Any mechanism that stops hard clunks.

Motors in detail: Each sample reads its rotation relative
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

SKIP = re.compile(r"^(MCH-|WGT|IK_|IK-|pole|roll_)", re.I)
GROUPS = (
    ("hand", re.compile(r"^f_|claw|grip|thumb|finger", re.I), 0.33, 0.04),
    ("leg", re.compile(r"thigh|shin|knee|foot|toe|ankle|hip(?!s)|leg|track|tread|wheel", re.I), 1.0, 1.0),
    ("arm", re.compile(r"upper_arm|forearm|shoulder|elbow|wrist|hand|arm_|pauldron|spear|tool", re.I), 0.65, 0.25),
    ("head", re.compile(r"head|sensor|eye|neck|visor|lid|brow|iris|focus|radar|louvre|thruster|vector|antenna|hatch|beacon|mast|dome|lens", re.I), 0.45, 0.06),
    ("torso", re.compile(r"waist|hips|spine|body|chest|pelvis|turntable|cable|hose|tether|pack|skirt", re.I), 0.85, 0.6),
)
MECH = (
    ("spinner", re.compile(r"radar|rotor|fan|wheel|turbine|propell|gyro|spin(?!e)|reel|drum_spin|dish_spin", re.I)),
    ("piston", re.compile(r"piston|rod|slide|slider|telescop|ram\b|strut|extend|plunger|lid_|lid\.|shutter|iris_blade|gear_leg|landing", re.I)),
    ("hinge", re.compile(r"^SPR-|antenna|cable|hose|spring|tether|pauldron|skirt|plate|flap|hatch|door|panel|cover|louvre|brow|hinge|ramp|visor", re.I)),
)
OMEGA_REF = 3.0          # rad/s: a brisk joint move
LIN_REF = 0.3            # m/s: a brisk piston stroke


def _group(name):
    side = re.search(r"\.([FB]?[LR])$", name)
    for g, rx, size, load in GROUPS:
        if rx.search(name):
            return ("%s.%s" % (g, side.group(1)) if side else g), size, load
    return ("body.%s" % side.group(1) if side else "body"), 0.5, 0.1


def mech_kind(name, tag=None):
    if tag:
        return str(tag).lower()
    for kind, rx in MECH:
        if rx.search(name):
            return kind
    return "motor"


class Joint:
    __slots__ = ("bone", "parent", "group", "size", "load", "q", "omega", "pos", "kind", "lin", "obj")

    def __init__(self, bone, parent, group, size, load, kind="motor", obj=None):
        self.bone, self.parent, self.group, self.size, self.load = bone, parent, group, size, load
        self.kind, self.obj = kind, obj
        self.q, self.omega, self.pos, self.lin = None, [], [], []

    @property
    def name(self):
        return self.obj.name if self.obj is not None else self.bone.name

    def local(self):
        if self.obj is not None:
            return self.obj.matrix_local
        return self.bone.matrix if self.parent is None else self.parent.matrix.inverted_safe() @ self.bone.matrix

    def head(self, mw):
        return self.obj.matrix_world.translation if self.obj is not None else mw @ self.bone.head


def joints(arm):
    """Every mechanism of a droid: all part-carrying bones (motors, hinges,
    pistons, spinners), minus helper bones and anything tagged none."""
    carriers = {o.parent_bone for o in arm.children_recursive if o.parent_type == "BONE" and o.parent_bone}
    out = []
    for name in sorted(carriers):
        if SKIP.search(name):
            continue
        pb = arm.pose.bones.get(name)
        if pb is None:
            continue
        kind = mech_kind(name, pb.get("foley_mech") or arm.data.bones[name].get("foley_mech"))
        if kind == "none":
            continue
        g, size, load = _group(name)
        par = pb.parent
        while par is not None and par.name not in carriers:
            par = par.parent
        out.append(Joint(pb, par, g, size, load, kind))
    return out


SHIP_MECH = re.compile(r"door|hatch|gear|ramp|flap|lift|elevator|turret|dish|crane|arm|shutter|vent|airlock|piston|fan|rotor|radar|panel|lever|valve|landing", re.I)


def ship_joints(objects):
    """Animated ship parts (doors, ramps, landing gear, turrets ...)."""
    out = []
    for ob in objects:
        tag = ob.get("foley_mech")
        if tag == "none" or not (tag or SHIP_MECH.search(ob.name)):
            continue
        dims = ob.dimensions
        size = max(min(max(dims) / 1.5, 3.0), 0.2)
        out.append(Joint(None, None, ob.name[:24], size, min(max(dims.x * dims.y * dims.z * 40, 0.05), 4.0),
                         mech_kind(ob.name, tag), obj=ob))
    return out


def sample(arm, js, t, span=1.0 / 24):
    """Record each mechanism's turning speed (rad/s) and sliding speed (m/s)
    at time t, measured over one frame (sub-frame steps of keyed or jittered
    motion would read as buzz)."""
    mw = arm.matrix_world if arm is not None else None
    for j in js:
        m = j.local()
        q, p = m.to_quaternion(), m.translation.copy()
        if j.q is None:
            j.q = []
        j.q.append((t, q, p))
        while len(j.q) > 1 and j.q[0][0] < t - span - 1e-6:
            j.q.pop(0)
        t0, q0, p0 = j.q[0]
        w = q.rotation_difference(q0).angle / (t - t0) if t > t0 else 0.0
        v = (p - p0).length / (t - t0) if t > t0 else 0.0
        if w > 60:
            w = 0.0
        j.omega.append((t, w))
        j.lin.append((t, v))
        j.pos.append(j.head(mw).copy())


def stop_clunks(arm_label, js, prof, fps, f0):
    """Joints that were moving briskly and stop dead make a short clunk.
    One per limb group within 80 ms, at most one per joint every 0.3 s."""
    raw = []
    for j in js:
        if j.kind == "spinner":
            continue
        om = [(a[0], a[1] + b[1] / 0.15) for a, b in zip(j.omega, j.lin)]   # slides count too
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
                    loc=tuple(j.pos[i]), surface=j.name, pan=0.0, dist=3.0, on_screen=True,
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


def _motor(j, ji, x, w, times, n, base, load, rng):
    size_pitch = 1.0 / max(j.size, 0.15) ** 0.9
    f = base * size_pitch * (0.7 + 3.2 * x) * (1 + rng.uniform(-0.04, 0.04))
    phase = 2 * math.pi * np.cumsum(f) / S.RATE
    # real motors aren't clean tones: jitter the phase and roughen the level
    phase = phase + 0.6 * _lp_noise(rng, n, 30.0)
    whine = sum(np.sin(k * phase) / k ** 1.15 for k in range(1, 7)) * (1 + 0.5 * _lp_noise(rng, n, 60.0))
    whine = 0.6 * whine + 0.9 * S._bandnoise(rng, n, float(np.median(f)) * 2.2, q=1.5)
    teeth = 9 + ji % 5
    mesh = 1.0 + 0.45 * np.sign(np.sin(phase * teeth / 3.0)) * np.abs(np.sin(phase * teeth / 3.0)) ** 4
    grind_c = min(900 + 1400 * size_pitch, 7000)
    grind = S._bandnoise(rng, n, grind_c, q=0.9) * np.abs(np.sin(phase * teeth / 2.0)) ** 2
    # the gear-mesh sing: teeth x shaft speed, rising and falling with the joint
    gph = phase * (teeth * 0.5)
    sing = (np.sin(gph) + 0.35 * np.sin(2 * gph)) * (1 + 0.3 * _lp_noise(rng, n, 40.0))
    sing = np.where(f * teeth * 0.5 < 9000, sing, 0.0)
    return x ** 0.7 * load * (0.55 * whine * mesh + 0.45 * sing + 0.3 * grind * np.minimum(load, 2.0))


def _hinge(j, x, n, load, rng):
    """Stick-slip creak: a train of tiny ticks whose rate follows the swing,
    rung through the pin's small metal modes, plus a groan on big parts."""
    rate = 25.0 + 380.0 * np.clip(x, 0, 2)                 # ticks per second
    prob = rate / S.RATE * (x > 0.03)
    ticks = (rng.random(n) < prob) * rng.uniform(0.3, 1.0, n)
    kl = int(0.012 * S.RATE)
    tk = np.arange(kl) / S.RATE
    f1 = 1800.0 / max(j.size, 0.2) ** 0.5
    kern = sum(np.sin(2 * math.pi * f1 * r * tk) * np.exp(-tk / 0.004) for r in (1.0, 1.7, 2.6))
    creak = np.convolve(ticks, kern, mode="full")[:n]
    creak /= np.max(np.abs(creak)) + 1e-12
    groan_f = 220.0 / max(j.size, 0.2) ** 0.6
    groan = S._bandnoise(rng, n, groan_f, q=3.0) * (1 + 0.8 * _lp_noise(rng, n, 9.0))
    groan /= np.max(np.abs(groan)) + 1e-12
    big = min(j.size, 1.5)
    return x ** 0.8 * load * (0.55 * creak + 0.35 * big * groan)


def _piston(j, xl, n, load, rng):
    """Hydraulic stroke: fluid hiss plus a low pump chug, both with speed."""
    hiss = S._bandnoise(rng, n, 3600.0, q=0.7)
    chug_rate = 9.0 + 14.0 * np.clip(xl, 0, 2)
    ph = 2 * math.pi * np.cumsum(chug_rate) / S.RATE
    chug = S._bandnoise(rng, n, 170.0 / max(j.size, 0.2) ** 0.4, q=1.2) * (0.5 + 0.5 * np.sin(ph)) ** 2
    seal = S._bandnoise(rng, n, 900.0, q=2.5) * _lp_noise(rng, n, 6.0) ** 2
    return xl ** 0.75 * load * (0.5 * hiss + 0.6 * chug + 0.3 * seal)


def _spinner(j, w, n, load, rng):
    """Bearing hum at the blade or spoke rate, with a little rumble."""
    blades = 6
    f = np.clip(w / (2 * math.pi) * blades * 12.0 + 90.0, 60.0, 4000.0)   # geared up, always audible
    ph = 2 * math.pi * np.cumsum(f) / S.RATE
    hum = np.sin(ph) + 0.4 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)
    rumble = S._bandnoise(rng, n, 400.0, q=0.8)
    x = np.clip(w / OMEGA_REF, 0, 2)
    return x ** 0.6 * load * (0.5 * hum * (1 + 0.2 * _lp_noise(rng, n, 20.0)) + 0.3 * rumble)


def render_group(js, prof, duration, strain=(), seed=0, level=1.0):
    """One group's mechanism track (float32 mono) for `duration` seconds.

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
        v = np.array([o[1] for o in j.lin])
        if len(times) < 2 or (w.max() < 0.08 and v.max() < 0.01):
            continue
        # light smoothing on the control rate so tiny jitters don't buzz
        w = np.convolve(w, np.ones(3) / 3, mode="same")
        v = np.convolve(v, np.ones(3) / 3, mode="same")
        wa = _env(times, w, n, 0.0)
        va = _env(times, v, n, 0.0)
        x = np.clip(wa / OMEGA_REF, 0, 2.5)
        xl = np.clip(va / LIN_REF, 0, 2.5)
        load = (mass * j.load / 100.0) ** 0.3
        if j.group.startswith("leg"):
            load = load * strain_env
        kind = j.kind
        if kind == "hinge" and va.max() / LIN_REF > wa.max() / OMEGA_REF:
            kind = "piston"                          # a sliding door or panel, not a swing
        if kind == "hinge":
            out += _hinge(j, np.maximum(x, xl), n, load, rng) * 0.8
        elif kind == "piston":
            out += _piston(j, np.maximum(xl, x * 0.5), n, load, rng)
        elif kind == "spinner":
            out += _spinner(j, wa, n, load, rng) * 0.6
        else:
            out += _motor(j, ji, np.maximum(x, xl), w, times, n, base, load, rng)
            if va.max() > 0.01:                      # a driven slide: motor plus fluid
                out += 0.5 * _piston(j, xl, n, load, rng)
        # hiss when the part speeds up or slows down quickly
        dw = np.abs(np.gradient(w, times)) if len(times) > 2 else np.zeros_like(w)
        acc = np.clip(_env(times, dw, n, 0.0) / 25.0, 0, 1.5)
        out += S._bandnoise(rng, n, 5200, q=0.6) * acc * 0.35 * load * (j.kind != "spinner")
    # level: an RX-07 leg moving briskly sits about 6-8 dB under a walking step
    out *= 0.11 * level
    out = np.tanh(out * 1.6) / 1.6
    fade = min(n, int(0.01 * S.RATE))
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out.astype(np.float32)
