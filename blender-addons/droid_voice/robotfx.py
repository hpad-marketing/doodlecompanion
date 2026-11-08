"""Robot voice processing. numpy only, so it runs inside Blender's Python.

Every chain keeps the cadence of the source line: the timing, stresses and
pauses come from the speech, only the timbre becomes a machine.

Public entry point: ``process(audio, chain, **dials)``.
"""
import numpy as np

SR = 24000


# ---------------------------------------------------------------- helpers

def norm(x, peak=0.89):
    m = float(np.max(np.abs(x))) if len(x) else 0.0
    return (x / m * peak).astype(np.float32) if m > 0 else x.astype(np.float32)


def bandpass(x, lo, hi, sr=SR):
    if not len(x):
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    w = np.clip((f - lo * 0.8) / (lo * 0.2 + 1e-9), 0, 1) * np.clip((hi * 1.2 - f) / (hi * 0.2), 0, 1)
    return np.fft.irfft(X * w, len(x))


def comb(x, ms, fb=0.55, sr=SR, taps=8):
    """Feed-forward approximation of a feedback comb (metal tube ring)."""
    d = max(1, int(sr * ms / 1000))
    y = np.array(x, dtype=np.float64)
    g = 1.0
    for k in range(1, taps):
        g *= fb
        if k * d >= len(x):
            break
        y[k * d:] += g * x[:-k * d]
    return y


def bitcrush(x, bits=6, hold_sr=8000, sr=SR):
    step = max(1, int(round(sr / hold_sr)))
    h = np.repeat(x[::step], step)[: len(x)]
    q = 2 ** (bits - 1)
    return np.round(h * q) / q


def ringmod(x, hz, mix=0.5, sr=SR):
    t = np.arange(len(x)) / sr
    return x * (1 - mix) + x * np.sin(2 * np.pi * hz * t) * mix


def resample(x, ratio):
    """ratio > 1 shortens and raises pitch (tape-speed change)."""
    n = max(1, int(len(x) / ratio))
    return np.interp(np.arange(n) * ratio, np.arange(len(x)), x)


def to_rate(x, sr_in, sr_out=SR):
    return x if sr_in == sr_out else resample(np.asarray(x, dtype=np.float64), sr_in / sr_out)


def pitch_shift(x, semitones, sr=SR, grain_ms=40.0):
    """Granular pitch shift that keeps duration (and so the cadence)."""
    if abs(semitones) < 1e-3 or not len(x):
        return np.asarray(x, dtype=np.float64)
    r = 2 ** (semitones / 12)
    g = int(sr * grain_ms / 1000)
    hop = g // 4
    win = np.hanning(g)
    out = np.zeros(len(x) + g)
    wsum = np.zeros(len(x) + g)
    src = np.asarray(x, dtype=np.float64)
    for i in range(0, len(src), hop):
        seg = src[i:i + int(g * r) + 1]
        if len(seg) < 4:
            break
        gr = np.interp(np.arange(g) * r, np.arange(len(seg)), seg, right=0.0)
        out[i:i + g] += gr * win
        wsum[i:i + g] += win
    wsum[wsum < 1e-3] = 1.0
    return (out / wsum)[: len(x)]


def envelope(x, win):
    k = np.ones(max(1, win)) / max(1, win)
    return np.sqrt(np.convolve(np.asarray(x) ** 2, k, mode="same"))


def vocoder(x, carrier_hz=110.0, bands=18, sr=SR):
    """Channel vocoder: buzzy carrier at one pitch shaped by the speech."""
    n = len(x)
    ph = np.cumsum(np.full(n, carrier_hz)) / sr
    car = 0.6 * (2 * (ph % 1.0) - 1) + 0.15 * np.random.default_rng(1).standard_normal(n)
    edges = np.geomspace(120, 7000, bands + 1)
    out = np.zeros(n)
    for lo, hi in zip(edges[:-1], edges[1:]):
        out += bandpass(car, lo, hi, sr) * envelope(bandpass(x, lo, hi, sr), int(sr * 0.012))
    return out


def pitch_track(x, sr=SR, hop=0.01):
    """Per-10 ms (f0, rms). f0 = 0 when unvoiced."""
    h = int(sr * hop)
    w = h * 4
    f0, en = [], []
    lo, hi = int(sr / 400), int(sr / 70)
    win = np.hanning(w)
    for i in range(0, max(0, len(x) - w), h):
        fr = x[i:i + w] * win
        e = float(np.sqrt(np.mean(fr * fr)))
        spec = np.fft.rfft(fr, 2 * w)
        ac = np.fft.irfft(spec * np.conj(spec))[:w]
        lag = lo + int(np.argmax(ac[lo:hi]))
        f0.append(sr / lag if ac[0] > 0 and ac[lag] > 0.35 * ac[0] else 0.0)
        en.append(e)
    return np.array(f0), np.array(en), h


def cadence_beeps(x, base=520.0, sr=SR, scale=(0, 2, 4, 7, 9, 12), spread=2.2, wave="square"):
    """Emotive-only speech: the line's pitch and loudness drive chirps, so the
    beeps rise, fall and pause exactly where the words would."""
    f0, en, h = pitch_track(x, sr)
    if not len(en):
        return np.zeros(len(x))
    en = en / (en.max() or 1)
    voiced = f0 > 0
    med = float(np.median(f0[voiced])) if voiced.any() else 150.0
    out = np.zeros(len(x))
    phase, note = 0.0, None
    t = np.arange(h)
    for i in range(len(f0)):
        gate = en[i] > 0.12
        if gate:
            semis = 12 * np.log2(max(f0[i] / med if f0[i] > 0 else 1.0, 0.25)) * spread
            target = base * 2 ** (min(scale, key=lambda s: abs(semis - s)) / 12)
            if note is None or abs(target - note) > 1:
                note = target
        else:
            note = None
        if note:
            inc = 2 * np.pi * note / sr
            ph = phase + inc * t
            phase = float(ph[-1] + inc)
            s = np.sin(ph)
            if wave == "square":
                s = 0.5 * np.sign(s) + 0.5 * s
            out[i * h:(i + 1) * h] = s * en[i]
    k = np.hanning(int(sr * 0.006))
    return np.convolve(out, k / k.sum(), mode="same")


def stressed_onsets(x, sr=SR, thresh=0.6, min_gap=0.18):
    """Sample indices of loud syllable onsets (stressed words)."""
    _, en, h = pitch_track(x, sr)
    if not len(en):
        return []
    en = en / (en.max() or 1)
    rise = np.diff(en, prepend=0)
    hits, last = [], -1e9
    for i in range(len(en)):
        if en[i] > thresh and rise[i] > 0.04 and (i - last) * h > min_gap * sr:
            hits.append(i * h)
            last = i
    return hits


def glitch(x, amount=0.3, seed=0, sr=SR):
    """Damaged speaker: some stressed syllables stutter, drop out or repeat."""
    if amount <= 0:
        return x
    rng = np.random.default_rng(seed)
    y = np.array(x, dtype=np.float64)
    for at in stressed_onsets(x, sr):
        if rng.random() > amount:
            continue
        kind = rng.choice(["stutter", "drop", "crush"])
        g = int(sr * rng.uniform(0.035, 0.07))
        if at + g * 3 >= len(y):
            continue
        if kind == "stutter":
            grain = y[at:at + g].copy() * np.hanning(g)
            for k in range(1, int(rng.integers(2, 4))):
                y[at + k * g:at + (k + 1) * g] = grain
        elif kind == "drop":
            y[at:at + g * 2] *= 0.05
        else:
            y[at:at + g * 3] = bitcrush(y[at:at + g * 3], bits=3, hold_sr=2500)
    return y


def body_resonance(x, size_m=1.5, hollow=0.6, sr=SR):
    """Ring of the droid's shell from its size: big hollow bodies boom,
    small ones rattle. Resonant peaks at the shell's first modes."""
    if hollow <= 0 or not len(x):
        return x
    base = 343.0 / (2.0 * max(0.15, size_m))          # half-wave mode of the shell
    modes = [base * m for m in (1.0, 2.76, 5.4)] + [1200.0 / max(0.3, size_m) ** 0.5]
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    gain = np.ones_like(f)
    for i, fc in enumerate(modes):
        bw = fc * 0.08
        gain += hollow * (2.5 / (i + 1)) / (1 + ((f - fc) / bw) ** 2)
    y = np.fft.irfft(X * gain, len(x))
    return comb(y, 1000.0 * size_m / 343.0, 0.25 * hollow, sr, taps=5)


# ---------------------------------------------------------------- chains

def chain_crush(x, bits=6, hold_sr=9000, ring_hz=38.0, ring_mix=0.45, lo=280, hi=3800, echo_ms=2.2, **_):
    y = bitcrush(x, bits=bits, hold_sr=hold_sr)
    y = ringmod(y, ring_hz, mix=ring_mix)
    y = bandpass(y, lo, hi)
    return comb(y, echo_ms, 0.35)


def chain_chirp(x, semitones=3.4, ring_hz=520.0, ring_mix=0.3, echo_ms=1.1, **_):
    y = pitch_shift(x, semitones)
    y = ringmod(y, ring_hz, mix=ring_mix)
    y = comb(y, echo_ms, 0.45)
    return bandpass(y, 400, 7500)


def chain_vocoder(x, carrier_hz=98.0, dry=0.15, room_ms=18.0, **_):
    y = vocoder(x, carrier_hz=carrier_hz)
    y = norm(y) * (1 - dry) + norm(bandpass(x, 300, 3400)) * dry
    return comb(y, room_ms, 0.25, taps=4)


def chain_beeps(x, base_hz=330.0, wave="square", echo_ms=3.0, **_):
    y = cadence_beeps(x, base=base_hz, wave=wave)
    return comb(y, echo_ms, 0.3)


def chain_clean(x, **_):
    return np.asarray(x, dtype=np.float64)


CHAINS = {
    "crush": chain_crush,       # bit-crushed talker
    "chirp": chain_chirp,       # pitch-up + ring mod
    "vocoder": chain_vocoder,   # machine vocoder, one pitch
    "beeps": chain_beeps,       # cadence beeps, emotive-only
    "clean": chain_clean,
}


def process(x, chain="crush", strength=1.0, size_m=None, hollow=0.0, glitch_amount=0.0,
            seed=0, sr=SR, **dials):
    """Run a chain on mono float audio at ``sr``. ``strength`` blends the
    robot sound with the dry voice (beeps ignore it: they replace speech)."""
    x = to_rate(np.asarray(x, dtype=np.float64), sr, SR)
    y = CHAINS[chain](x, **dials)
    if chain != "beeps" and strength < 1.0:
        y = norm(y) * strength + norm(x) * (1 - strength)
    if glitch_amount > 0:
        y = glitch(y, glitch_amount, seed=seed)
    if size_m and hollow > 0:
        y = body_resonance(y, size_m, hollow)
    return norm(y, 0.75 if chain == "beeps" else 0.89)
