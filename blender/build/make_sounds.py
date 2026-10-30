"""Synthesise the storytime sound kit (pure tones and noise, written here, so CC0 / public
domain with no attribution needed). 22.05 kHz mono 16-bit WAV.

  python3 make_sounds.py OUT_DIR
"""
import os
import sys
import wave

import numpy as np

SR = 22050
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
rng = np.random.default_rng(7)


def t(sec):
    return np.arange(int(SR * sec)) / SR


def env(n, a=0.005, r=0.1, sec=None):
    x = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        x[:na] = np.linspace(0, 1, na)
    if nr:
        x[-nr:] *= np.linspace(1, 0, nr) ** 2
    return x


def write(name, y, gain=0.8):
    y = np.asarray(y, dtype=float)
    y = y / (np.max(np.abs(y)) + 1e-9) * gain
    with wave.open(os.path.join(out, name + '.wav'), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype('<i2').tobytes())


def sweep(f0, f1, sec):
    tt = t(sec)
    f = np.geomspace(f0, f1, len(tt))
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def noise(sec):
    return rng.standard_normal(int(SR * sec))


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, mode='same')


# pop: reaction symbols, bubbles appearing
y = sweep(300, 900, 0.09) * env(int(SR * 0.09), 0.002, 0.07)
write('pop', y)
# message: chat bubble ding (two soft bells)
tt = t(0.5)
y = (np.sin(2 * np.pi * 1320 * tt) * np.exp(-tt * 9) + 0.6 * np.sin(2 * np.pi * 1760 * tt) * np.exp(-(tt - 0.09).clip(0) * 9) * (tt > 0.09))
write('message', y, 0.6)
# typing: three soft ticks (typing dots)
y = np.zeros(int(SR * 0.6))
for i, s in enumerate((0.0, 0.18, 0.36)):
    k = int(s * SR)
    n = int(0.02 * SR)
    y[k:k + n] += lowpass(noise(0.02), 3) * np.linspace(1, 0, n)
write('typing', y, 0.5)
# whoosh: time-skip cards, camera moves
n = noise(0.6)
y = np.concatenate([lowpass(n[:len(n) // 2], 9), lowpass(n[len(n) // 2:], 30)]) * np.sin(np.linspace(0, np.pi, len(n))) ** 2
write('whoosh', y, 0.7)
# boing: bouncy props, comic beats
tt = t(0.45)
y = np.sin(2 * np.pi * (180 + 90 * np.sin(2 * np.pi * 9 * tt) * np.exp(-tt * 5)) * tt) * np.exp(-tt * 6)
write('boing', y)
# click: subscribe button press
y = np.concatenate([lowpass(noise(0.008), 2) * np.linspace(1, 0, int(SR * 0.008)), np.zeros(int(SR * 0.06)),
                    0.6 * lowpass(noise(0.006), 2) * np.linspace(1, 0, int(SR * 0.006))])
write('click', y, 0.7)
# bell: notification bell
tt = t(1.2)
y = sum(a * np.sin(2 * np.pi * f * tt) * np.exp(-tt * d) for f, a, d in ((880, 1, 3), (1760, 0.5, 4), (2640, 0.25, 6)))
write('bell', y, 0.6)
# pin: map pin drop / label stick
y = sweep(1400, 500, 0.12) * env(int(SR * 0.12), 0.001, 0.1)
write('pin', y, 0.6)
# draw: marker squeak for map paths and boards
tt = t(0.8)
y = lowpass(noise(0.8), 4) * (0.6 + 0.4 * np.sin(2 * np.pi * 7 * tt)) * env(len(tt), 0.05, 0.2)
write('draw', y, 0.4)
# horror: low drone with a slow beat (opt-in horror kit)
tt = t(6.0)
y = (np.sin(2 * np.pi * 55 * tt) + 0.7 * np.sin(2 * np.pi * 55.7 * tt) + 0.3 * np.sin(2 * np.pi * 82.5 * tt)) * \
    (0.7 + 0.3 * np.sin(2 * np.pi * 0.25 * tt)) * env(len(tt), 1.0, 1.5)
write('horror_drone', y, 0.6)
# thunder: lightning flashes
n = noise(2.5)
y = lowpass(n, 60) * np.exp(-t(2.5) * 1.6) + 0.5 * lowpass(noise(2.5), 15) * np.exp(-t(2.5) * 6)
write('thunder', y, 0.8)
# sting: end-screen / reveal sting (rising major arpeggio)
y = np.concatenate([np.sin(2 * np.pi * f * t(0.14)) * env(int(SR * 0.14), 0.005, 0.08) for f in (523, 659, 784, 1047)])
write('sting', y, 0.6)
open(os.path.join(out, 'LICENSE.txt'), 'w').write(
    'These sounds were synthesised from scratch by make_sounds.py for the Doodle Library.\n'
    'They are dedicated to the public domain under CC0 1.0 Universal:\n'
    'https://creativecommons.org/publicdomain/zero/1.0/\n')
print('sounds written to', out)
