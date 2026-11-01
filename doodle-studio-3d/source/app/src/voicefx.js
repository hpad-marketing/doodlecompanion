// Voice effects for the scene voice: a pitch shift (the 2D studio's own phase vocoder) and a
// character effect, mixed with the dry voice. Settings live on the scene (scene.voiceFx); the
// recording is never changed, the app writes a processed copy and plays that.
export const EFFECTS = { clean: 'None', robot: 'Robot', radio: 'Radio', phone: 'Phone', megaphone: 'Megaphone', echo: 'Echo', cave: 'Cave', underwater: 'Underwater', alien: 'Alien' };
export const PRESETS = {
  natural: ['Natural', 0, 'clean'], squeaky: ['Squeaky', 7, 'clean'], tiny: ['Tiny', 12, 'clean'], deep: ['Deep', -5, 'clean'], giant: ['Giant', -10, 'cave'],
  robot: ['Robot', -2, 'robot'], radio: ['Radio', 0, 'radio'], phone: ['Phone call', 0, 'phone'], megaphone: ['Megaphone', 0, 'megaphone'], echo: ['Echo', 0, 'echo'],
  cave: ['Cave', 0, 'cave'], underwater: ['Underwater', -2, 'underwater'], alien: ['Alien', 4, 'alien'],
};
export function normalize(raw = {}) {
  const pitch = Math.max(-12, Math.min(12, +(raw.pitch ?? 0) || 0)), mix = Math.max(0, Math.min(1, +(raw.mix ?? 1)));
  const effect = raw.effect ?? 'clean';
  if (!EFFECTS[effect]) throw Error('effect must be ' + Object.keys(EFFECTS).join(', '));
  return { on: raw.on !== false, pitch, effect, mix: Number.isFinite(mix) ? mix : 1 };
}
export const isActive = fx => !!fx && fx.on !== false && fx.mix > 0 && (fx.pitch !== 0 || fx.effect !== 'clean');

const TAU = Math.PI * 2, N = 2048, H = 256;
function fft(re, im, inverse) {
  for (let i = 1, j = 0; i < N; i++) { let b = N >> 1; for (; j & b; b >>= 1) j ^= b; j ^= b; if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; } }
  for (let size = 2; size <= N; size *= 2) {
    const angle = (inverse ? TAU : -TAU) / size, wr = Math.cos(angle), wi = Math.sin(angle);
    for (let a = 0; a < N; a += size) {
      let cr = 1, ci = 0;
      for (let j = 0; j < size / 2; j++) {
        const x = a + j, y = x + size / 2, tr = cr * re[y] - ci * im[y], ti = cr * im[y] + ci * re[y];
        re[y] = re[x] - tr; im[y] = im[x] - ti; re[x] += tr; im[x] += ti;
        const n = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = n;
      }
    }
  }
  if (inverse) for (let i = 0; i < N; i++) { re[i] /= N; im[i] /= N; }
}
function shift(input, ratio) {
  if (ratio === 1) return input.slice();
  const output = new Float32Array(input.length), weight = new Float32Array(input.length), win = Float64Array.from({ length: N }, (_, i) => (1 - Math.cos(TAU * i / N)) / 2);
  const prev = new Float64Array(N / 2 + 1), phase = new Float64Array(N / 2 + 1), re = new Float64Array(N), im = new Float64Array(N), mag = new Float64Array(N / 2 + 1), freq = new Float64Array(N / 2 + 1);
  for (let at = -N + H; at < input.length; at += H) {
    for (let j = 0; j < N; j++) { re[j] = (input[at + j] || 0) * win[j]; im[j] = 0; }
    fft(re, im, false); mag.fill(0); freq.fill(0);
    for (let k = 0; k <= N / 2; k++) {
      const p = Math.atan2(im[k], re[k]), amp = Math.hypot(re[k], im[k]);
      let delta = p - prev[k] - TAU * k * H / N; prev[k] = p; delta -= TAU * Math.round(delta / TAU);
      const omega = (TAU * k / N + delta / H) * ratio, dest = Math.round(k * ratio);
      if (dest <= N / 2) { mag[dest] += amp; freq[dest] += amp * omega; }
    }
    re.fill(0); im.fill(0);
    for (let k = 0; k <= N / 2; k++) {
      phase[k] += mag[k] ? freq[k] / mag[k] * H : TAU * k * H / N;
      re[k] = mag[k] * Math.cos(phase[k]); im[k] = mag[k] * Math.sin(phase[k]);
      if (k && k < N / 2) { re[N - k] = re[k]; im[N - k] = -im[k]; }
    }
    fft(re, im, true);
    for (let j = 0; j < N; j++) { const x = at + j; if (x >= 0 && x < input.length) { output[x] += re[j] * win[j]; weight[x] += win[j] * win[j]; } }
  }
  for (let i = 0; i < input.length; i++) output[i] /= Math.max(0.01, weight[i]);
  return output;
}
// one-pole band between lo and hi Hz; returns a function of one sample
function band(sr, lo, hi) {
  const a = 1 - Math.exp(-TAU * hi / sr), b = Math.exp(-TAU * lo / sr);
  let hp = 0, last = 0, out = 0;
  return v => { hp = b * (hp + v - last); last = v; out += a * (hp - out); return out; };
}
const delayed = (x, i, d) => (i >= d ? x[i - d] : 0);
function colour(x, sr, effect) {
  const y = x.slice();
  switch (effect) {
    case 'robot': for (let i = 0; i < y.length; i++) y[i] = x[i] * (0.2 + 0.8 * Math.sin(TAU * 70 * i / sr)); break;
    case 'radio': { const f = band(sr, 350, 3200); for (let i = 0; i < y.length; i++) y[i] = Math.tanh(f(x[i]) * 2) * 0.6; break; }
    case 'phone': { const f = band(sr, 500, 2600), g = band(sr, 500, 2600), step = Math.max(1, Math.round(sr / 8000)); let hold = 0; for (let i = 0; i < y.length; i++) { const v = g(f(x[i])) * 2.4; if (i % step === 0) hold = Math.round(v * 24) / 24; y[i] = hold; } break; }
    case 'megaphone': { const f = band(sr, 700, 3000); for (let i = 0; i < y.length; i++) y[i] = Math.max(-0.5, Math.min(0.5, f(x[i]) * 7)) * 1.3; break; }
    case 'echo': { const d = Math.round(sr * 0.14); for (let i = 0; i < y.length; i++) y[i] = x[i] + delayed(x, i, d) * 0.3 + delayed(x, i, d * 2) * 0.12; break; }
    case 'cave': { const taps = [[0.043, 0.34], [0.097, 0.28], [0.151, 0.22], [0.233, 0.17], [0.317, 0.12]].map(([t, g]) => [Math.round(sr * t), g]); for (let i = 0; i < y.length; i++) { let v = x[i]; for (const [d, g] of taps) v += delayed(y, i, d) * g; y[i] = v * 0.72; } break; }
    case 'underwater': { const a = 1 - Math.exp(-TAU * 420 / sr); let lo = 0, lo2 = 0; for (let i = 0; i < y.length; i++) { const w = 1 + 0.25 * Math.sin(TAU * 3.5 * i / sr); lo += a * (x[i] - lo); lo2 += a * w * (lo - lo2); y[i] = lo2 * 1.7; } break; }
    case 'alien': for (let i = 0; i < y.length; i++) { const d = Math.round(sr * (0.006 + 0.004 * Math.sin(TAU * 6 * i / sr))); y[i] = (x[i] * 0.6 + delayed(x, i, d) * 0.6) * (0.5 + 0.5 * Math.sin(TAU * 140 * i / sr)) * 1.5; } break;
  }
  return y;
}
// channels: Float32Array[]; same length out, so lip sync and captions keep their timing
export function processChannels(channels, sr, raw) {
  const fx = normalize(raw), ratio = 2 ** (fx.pitch / 12);
  return channels.map(input => {
    const wet = colour(shift(input, ratio), sr, fx.effect), out = new Float32Array(input.length);
    for (let i = 0; i < out.length; i++) { const v = input[i] + (wet[i] - input[i]) * fx.mix; out[i] = Number.isFinite(v) ? Math.max(-1, Math.min(1, v)) : 0; }
    return out;
  });
}
