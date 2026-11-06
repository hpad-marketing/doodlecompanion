"""Per-frame voice curve for the droid's lights (visor, LEDs, antenna, jaw
plates). The add-on's light lip sync reads these; nothing here needs bpy."""
import numpy as np


def curve(audio, sr, fps=24, attack=0.5, release=0.25, floor=0.04):
    """-> {"fps", "level": [0..1 per frame], "on": [bool], "accents": [frame...]}.
    level is smoothed loudness (fast attack, slower release, like a VU meter);
    accents are stressed syllables, for gestures-from-voice."""
    a = np.asarray(audio, dtype=np.float64)
    hop = sr / fps
    n = int(np.ceil(len(a) / hop)) if len(a) else 0
    rms = np.array([np.sqrt(np.mean(a[int(i * hop):int((i + 1) * hop)] ** 2)) if int(i * hop) < len(a) else 0.0
                    for i in range(n)])
    if n == 0:
        return {"fps": fps, "level": [], "on": [], "accents": []}
    rms = rms / (np.percentile(rms, 95) or rms.max() or 1)
    lvl, cur = np.zeros(n), 0.0
    for i, v in enumerate(np.clip(rms, 0, 1)):
        cur += (v - cur) * (attack if v > cur else release)
        lvl[i] = cur
    on = lvl > floor
    rise = np.diff(lvl, prepend=0)
    acc, last = [], -999
    for i in range(n):
        if lvl[i] > 0.6 and rise[i] > 0.12 and i - last > fps * 0.2:
            acc.append(i)
            last = i
    return {"fps": fps, "level": [round(float(x), 3) for x in lvl], "on": [bool(x) for x in on], "accents": acc}
