"""Contact sounds made from physics, so there is nothing to license.

A hit is modelled the way it happens:

* Energy. Loudness follows the kinetic energy of the moving part,
  E = 1/2 m v^2. A heavy droid's foot or a fast hand is loud; a slow, careful
  pickup is quiet.
* Strike. Hertz contact: how long the two surfaces press together depends on
  mass, speed and stiffness. A short, hard strike excites the high modes and
  sounds bright; a slow or soft one smears into a dull knock.
* Ring. Both bodies ring at their own modes. Bigger objects ring lower,
  hollow ones ring longer, metal rings for a second, polymer for a blink, and a
  rug barely at all.
* Weight. Heavy impacts flex the deck: a low thud that drops in pitch, deeper
  and stronger the heavier the droid.
* Grit. A short scuff of noise, coloured by the surface.

Every event gets a little seeded variation, so a walk never machine-guns the
same sample. Pure numpy; no Blender needed.
"""
import math
import wave
import zlib

import numpy as np

from .profiles import MATERIALS

RATE = 48000
E_REF = 9.6          # joules: RX-07 putting a foot down at a normal walk
A_REF = 0.42         # peak level of that reference step before the room tail


class Hit:
    """One contact. Speeds in m/s, masses in kg, sizes in metres.

    kind:      'step' | 'grab' | 'release' | 'place' | 'bump' | 'slide'
    mass:      effective moving mass behind the contact
    speed:     approach speed along the contact normal
    a_mat/a_size:  the moving part (sole, fingertip, prop corner)
    b_mat/b_size:  the thing it lands on
    b_hollow:  0 solid .. 1 thin hollow shell (crates, cans, lockers)
    b_mass:    mass of the struck thing (None = fixed to the ship)
    slide:     for 'slide' events, seconds of contact and the speed envelope
    offset:    seconds of silence before the hit (sub-frame placement)
    seed:      variation seed
    """

    def __init__(self, kind, mass, speed, a_mat="metal", a_size=0.3, b_mat="deck",
                 b_size=1.0, b_hollow=0.0, b_mass=None, slide=None, offset=0.0, seed=0):
        self.kind, self.mass, self.speed = kind, float(mass), float(speed)
        self.a_mat, self.a_size = a_mat, float(a_size)
        self.b_mat, self.b_size, self.b_hollow = b_mat, float(b_size), float(b_hollow)
        self.b_mass = b_mass
        self.slide = slide
        self.offset = max(0.0, float(offset))
        self.seed = int(seed)

    def key(self):
        r = lambda x: round(float(x), 3)
        return "_".join(str(x) for x in (self.kind, r(self.mass), r(self.speed), self.a_mat, r(self.a_size),
                                         self.b_mat, r(self.b_size), r(self.b_hollow), r(self.b_mass or 0),
                                         r(self.offset), self.seed,
                                         r(self.slide[0]) if self.slide else 0))


def energy(mass, speed):
    return 0.5 * mass * speed * speed


def loudness(h):
    """Linear peak gain of a hit before the room: energy scaled to the
    reference step, compressed the way ears hear it (about a cube root), times
    how well the two materials turn the hit into sound."""
    rad = math.sqrt(MATERIALS[h.a_mat]["radiate"] * MATERIALS[h.b_mat]["radiate"])
    e = max(energy(h.mass, h.speed), 1e-9)
    return A_REF * (e / E_REF) ** 0.32 * rad * (max(h.mass, 0.05) / 120.0) ** 0.08


def contact_time(h):
    """Hertz: tau ~ m^(2/5) v^(-1/5) / stiffness. Seconds."""
    hard = 2.0 / (1.0 / MATERIALS[h.a_mat]["hard"] + 1.0 / MATERIALS[h.b_mat]["hard"])
    m = h.mass if h.b_mass is None else h.mass * h.b_mass / (h.mass + h.b_mass)
    tau = 0.0004 * (max(m, 0.01) / 10.0) ** 0.4 * max(h.speed, 0.01) ** -0.2 / hard
    return min(max(tau, 0.00008), 0.02)


def _modes(mat, size, hollow, rng, n_max=12):
    p = MATERIALS[mat]
    f0 = p["k"] / max(size, 0.01) * (1.0 - 0.25 * hollow)
    f0 = min(max(f0, 45.0), 7000.0)
    t60 = p["t60"] * (1.0 + 1.2 * hollow)
    out = []
    for i, r in enumerate(p["ratios"][:n_max]):
        f = f0 * r * (1.0 + rng.uniform(-0.035, 0.035))
        if f > 16000:
            break
        amp = rng.uniform(0.55, 1.0) / math.sqrt(i + 1)
        decay = t60 / (1.0 + 0.6 * i) * rng.uniform(0.85, 1.15)
        out.append((f, amp, decay))
    return out


def _strike_filter(f, tau):
    """How much a half-sine strike of width tau excites frequency f."""
    x = f * tau * 1.6
    return 1.0 / (1.0 + x * x)


def _bank(modes, tau, n, t):
    sig = np.zeros(n)
    for f, a, t60 in modes:
        g = a * _strike_filter(f, tau)
        if g < 1e-4:
            continue
        sig += g * np.exp(-6.91 * t / t60) * np.sin(2 * math.pi * f * t)
    return sig


def _strike(tau, n):
    """The force pulse itself: a half sine tau long."""
    m = max(2, int(tau * RATE))
    p = np.zeros(n)
    p[:min(m, n)] = np.sin(np.linspace(0, math.pi, m))[:n]
    return p


def _bandnoise(rng, n, centre, q=1.2):
    """Noise around a centre frequency (FFT band-pass, no scipy)."""
    x = rng.standard_normal(n)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / RATE)
    bw = centre / q
    X *= np.exp(-0.5 * ((f - centre) / bw) ** 2)
    y = np.fft.irfft(X, n)
    return y / (np.max(np.abs(y)) + 1e-12)


def _lowpass(x, cutoff):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / RATE)
    X *= 1.0 / np.sqrt(1.0 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def _thud(h, n, t, rng):
    """Deck flex under a heavy impact: low, dropping in pitch, longer when heavy."""
    m = h.mass if h.b_mass is None else min(h.mass, h.b_mass * 4)
    share = min(max(math.log10(max(m, 0.1)) / 2.0, 0.03), 1.1)
    f_start = min(max(150.0 * (max(m, 0.5) / 20.0) ** -0.3, 32.0), 190.0)
    f_end = f_start * 0.65
    dur = 0.05 + 0.14 * min(share, 1.0)
    freq = f_end + (f_start - f_end) * np.exp(-t / (dur * 0.6))
    phase = 2 * math.pi * np.cumsum(freq) / RATE
    body = np.sin(phase) * np.exp(-t / dur)
    rumble = _lowpass(rng.standard_normal(n), f_start * 1.4) * np.exp(-t / (dur * 0.7))
    rumble /= np.max(np.abs(rumble)) + 1e-12
    soft = MATERIALS[h.b_mat]["hard"]
    out = share * (0.8 * body + 0.35 * rumble) * (0.35 + 0.65 * soft)
    if m > 60:   # the whole frame of a heavy droid booms under the deck
        boom_f = 30.0 + 25.0 * (60.0 / m) ** 0.5
        boom = np.sin(2 * math.pi * boom_f * t * (1 - 0.15 * t)) * (1 - np.exp(-t / 0.006)) * np.exp(-t / 0.22)
        out += min((m - 60) / 120.0, 1.0) * 0.9 * boom
    return out


def _settle(h, gain, rng):
    """A heavy leg taking the body's weight: hydraulic hiss and a low creak
    as the struts compress, just after the foot lands."""
    m = h.mass
    n = int(0.45 * RATE)
    t = np.arange(n) / RATE
    lvl = gain * 0.22 * min((m / 120.0) ** 0.5, 1.4)
    env = (1 - np.exp(-t / 0.035)) * np.exp(-t / 0.16)
    hiss = _bandnoise(rng, n, 3000 + rng.uniform(-400, 400), q=0.7) * env
    f = 95 + 40 * (120.0 / max(m, 10)) ** 0.4
    creak_ph = 2 * math.pi * np.cumsum(f * (1 + 0.04 * np.sin(2 * math.pi * 23 * t))) / RATE
    creak = (np.sin(creak_ph) + 0.4 * np.sin(2 * creak_ph)) * (1 - np.exp(-t / 0.05)) * np.exp(-t / 0.12)
    out = lvl * (0.6 * hiss + 0.5 * creak)
    pre = np.zeros(int(0.025 * RATE))
    return np.concatenate([pre, out])


def _rattle(h, gain, rng, room_wet, room_rt60):
    """Loose armour plates and fittings clattering for a moment after a big hit."""
    e = energy(h.mass, h.speed)
    count = int(min(e / 2.5, 7))
    if count < 1:
        return None
    n = int(0.5 * RATE)
    out = np.zeros(n)
    for k in range(count):
        d = rng.uniform(0.018, 0.16) * (1 + 0.2 * k)
        sub = Hit("rattle", 0.4, rng.uniform(0.25, 0.8) * min(h.speed, 1.2), "metal_thin", rng.uniform(0.04, 0.09),
                  "metal_thin", rng.uniform(0.12, 0.35), 0.6, seed=rng.integers(1 << 30))
        x = render(sub, room_wet=0.0)
        x = x / (np.max(np.abs(x)) + 1e-12) * gain * rng.uniform(0.12, 0.3) * math.exp(-d * 6)
        i = int(d * RATE)
        j = min(n, i + len(x))
        out[i:j] += x[:j - i]
    return out


def _room(x, rng, rt60=0.45, wet=0.12):
    """A small steel room: a few early reflections and a short damped tail."""
    if wet <= 0:
        return x
    n_ir = int(rt60 * RATE)
    t = np.arange(n_ir) / RATE
    ir = rng.standard_normal(n_ir) * np.exp(-6.91 * t / rt60)
    ir = _lowpass(ir, 5500.0)
    for d, g in ((0.007, 0.5), (0.011, 0.38), (0.017, 0.3), (0.023, 0.22)):
        i = int(d * RATE)
        if i < n_ir:
            ir[i] += g * 6
    ir /= np.sqrt(np.sum(ir * ir)) + 1e-12
    out = np.zeros(len(x) + n_ir - 1)
    L = 1 << int(math.ceil(math.log2(len(out))))
    out = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[:len(x) + n_ir - 1]
    y = np.zeros(len(out))
    y[:len(x)] += x
    return y + wet * out


def render(h, room_wet=0.12, room_rt60=0.45):
    """Float32 mono samples at RATE for one Hit."""
    rng = np.random.default_rng(zlib.crc32(h.key().encode()))
    if h.kind == "slide":
        return _render_slide(h, rng, room_wet, room_rt60)
    gain = loudness(h) * 10 ** (rng.uniform(-1.5, 1.5) / 20)
    tau = contact_time(h)
    b_modes = _modes(h.b_mat, h.b_size, h.b_hollow, rng)
    a_modes = _modes(h.a_mat, h.a_size, 0.3 if h.a_mat.startswith("metal") else 0.0, rng, 8)
    longest = max([d for _, _, d in b_modes + a_modes] + [0.12])
    dur = min(longest * 1.1 + 0.15, 3.0)
    n = int(dur * RATE)
    t = np.arange(n) / RATE

    sig = _bank(b_modes, tau, n, t) + 0.55 * _bank(a_modes, tau, n, t)
    sig /= np.max(np.abs(sig)) + 1e-12

    # the strike itself carries the attack; slow hits barely click
    click = _strike(tau, n) * (0.25 + 0.5 * min(h.speed / 1.5, 1.0))
    sig = sig + click

    g_amt, g_c = MATERIALS[h.b_mat]["grit"]
    g_amt *= min(0.4 + h.speed, 1.6)
    g_len = 0.012 + 0.03 * MATERIALS[h.b_mat]["grit"][0]
    grit = _bandnoise(rng, n, g_c * (0.8 + 0.4 * min(h.speed, 1.0))) * np.exp(-t / g_len)
    sig = sig + g_amt * grit

    if h.kind in ("step", "place", "bump") or h.mass > 20:
        sig = sig + _thud(h, n, t, rng)

    if h.kind == "release":
        sig *= 0.5
    if h.kind == "rattle":
        sig = _lowpass(sig, 9000.0)
    # soft strikes lose their top end
    cutoff = min(16000.0, 4.0 / tau)
    if cutoff < 15000:
        sig = _lowpass(sig, cutoff)
    sig /= np.max(np.abs(sig)) + 1e-12
    sig *= gain

    if h.kind in ("step", "bump", "place") and h.mass > 15:
        extra = [_rattle(h, gain, rng, room_wet, room_rt60)]
        if h.kind == "step" and h.mass > 30:
            extra.append(_settle(h, gain, rng))
        for x in extra:
            if x is None:
                continue
            if len(x) > len(sig):
                sig = np.concatenate([sig, np.zeros(len(x) - len(sig))])
            sig[:len(x)] += x

    sig = _room(sig, rng, room_rt60, room_wet)
    pre = np.zeros(int(h.offset * RATE))
    out = np.concatenate([pre, sig])
    fade = min(len(out), int(0.02 * RATE))
    out[-fade:] *= np.linspace(1, 0, fade)
    return np.clip(out, -1, 1).astype(np.float32)


def _render_slide(h, rng, room_wet, room_rt60):
    """Scrape: friction noise pushed through the struck surface's modes,
    following the speed envelope; louder with load and speed."""
    seconds, env = h.slide
    n = max(int(seconds * RATE), 256)
    env = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(env)), np.asarray(env, float))
    noise = rng.standard_normal(n)
    modes = _modes(h.b_mat, h.b_size, h.b_hollow, rng, 8)
    X = np.fft.rfft(noise)
    f = np.fft.rfftfreq(n, 1.0 / RATE)
    shape = np.full(len(f), 0.15)
    for fm, a, t60 in modes:
        bw = max(6.91 / (math.pi * t60), 8.0)
        shape += a * np.exp(-0.5 * ((f - fm) / bw) ** 2)
    g_amt, g_c = MATERIALS[h.b_mat]["grit"]
    shape += g_amt * np.exp(-0.5 * ((f - g_c) / (g_c / 1.5)) ** 2)
    y = np.fft.irfft(X * shape, n)
    y /= np.max(np.abs(y)) + 1e-12
    speed = max(float(np.max(env)), 1e-3)
    y *= env / speed
    load = Hit("bump", h.mass, speed, h.a_mat, h.a_size, h.b_mat, h.b_size, h.b_hollow)
    y *= loudness(load) * 0.45
    fade = min(n // 4, int(0.03 * RATE))
    y[:fade] *= np.linspace(0, 1, fade)
    y[-fade:] *= np.linspace(1, 0, fade)
    y = _room(y, rng, room_rt60, room_wet)
    pre = np.zeros(int(h.offset * RATE))
    return np.clip(np.concatenate([pre, y]), -1, 1).astype(np.float32)


def write_wav(path, samples, rate=RATE):
    s = np.clip(np.asarray(samples, dtype=np.float64), -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((s * 32767).astype("<i2").tobytes())


def peak_db(samples):
    return 20 * math.log10(max(float(np.max(np.abs(samples))), 1e-9))


def centroid(samples):
    X = np.abs(np.fft.rfft(samples))
    f = np.fft.rfftfreq(len(samples), 1.0 / RATE)
    return float(np.sum(f * X) / (np.sum(X) + 1e-12))
