// Vocal separation and lip-sync alignment, offline (no network, no models): pure DSP on the
// scene audio, so a voice over a beat (a rap track) drives the mouth and the drums, bass and
// hats don't. Steps:
//   1. the centre of the stereo mix (vocals sit there; wide pads and panned parts drop)
//   2. harmonic/percussive split by median filtering the spectrogram: kicks, snares and hats
//      are short and broadband (vertical), sung and spoken vowels hold their partials (horizontal)
//   3. the voice band (bass and sub cut below ~150 Hz, sibilance kept softer up top)
// The result is a vocal estimate to read the mouths from, plus a syllable-onset curve
// (spectral flux of that estimate) to snap each word start onto the frame the voice starts.

const N = 1024, HOP = 256, TARGET_SR = 22050;

function fft(re, im) {
  const n = re.length;
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const a = -2 * Math.PI / len, wr = Math.cos(a), wi = Math.sin(a);
    for (let i = 0; i < n; i += len) {
      let cr = 1, ci = 0;
      for (let k = 0; k < len / 2; k++) {
        const p = i + k, q = p + len / 2;
        const tr = re[q] * cr - im[q] * ci, ti = re[q] * ci + im[q] * cr;
        re[q] = re[p] - tr; im[q] = im[p] - ti; re[p] += tr; im[p] += ti;
        const t = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = t;
      }
    }
  }
}

function down(x, d) {
  if (d <= 1) return x;
  const out = new Float32Array(Math.floor(x.length / d));
  for (let i = 0; i < out.length; i++) { let s = 0; for (let k = 0; k < d; k++) s += x[i * d + k]; out[i] = s / d; }
  return out;
}

// running median along one axis of a [frames x bins] Float32Array (window w, odd)
function median(S, T, B, w, alongTime) {
  const out = new Float32Array(S.length), h = w >> 1, win = new Float32Array(w);
  const len = alongTime ? T : B, other = alongTime ? B : T;
  for (let o = 0; o < other; o++) {
    for (let i = 0; i < len; i++) {
      let c = 0;
      for (let k = i - h; k <= i + h; k++) if (k >= 0 && k < len) win[c++] = alongTime ? S[k * B + o] : S[o * B + k];
      const v = win.subarray(0, c).sort();
      out[alongTime ? i * B + o : o * B + i] = v[c >> 1];
    }
  }
  return out;
}

// left/right channels (Float32Array; right may be null) at sample rate sr -> vocal estimate
export function vocalStem(L, R, sr) {
  const d = Math.max(1, Math.round(sr / TARGET_SR)), fs = sr / d;
  const l = down(L, d), r = R ? down(R, d) : l;
  const T = Math.max(1, Math.ceil((l.length - N) / HOP) + 1), B = N / 2 + 1;
  const win = new Float32Array(N).map((_, i) => 0.5 - 0.5 * Math.cos(2 * Math.PI * i / N));
  const mre = new Float32Array(T * B), mim = new Float32Array(T * B), S = new Float32Array(T * B), C = new Float32Array(T * B);
  const ar = new Float32Array(N), ai = new Float32Array(N), br = new Float32Array(N), bi = new Float32Array(N);
  for (let t = 0; t < T; t++) {
    for (let i = 0; i < N; i++) { const s = t * HOP + i; ar[i] = (l[s] || 0) * win[i]; br[i] = (r[s] || 0) * win[i]; ai[i] = bi[i] = 0; }
    fft(ar, ai); fft(br, bi);
    for (let k = 0; k < B; k++) {
      const j = t * B + k, xr = (ar[k] + br[k]) / 2, xi = (ai[k] + bi[k]) / 2;
      const pl = ar[k] * ar[k] + ai[k] * ai[k], pr = br[k] * br[k] + bi[k] * bi[k], pm = xr * xr + xi * xi;
      mre[j] = xr; mim[j] = xi; S[j] = Math.sqrt(pm);
      // 1 for a centred, in-phase sound; 0 for a hard-panned or out-of-phase one
      C[j] = Math.max(0, Math.min(1, (2 * pm / ((pl + pr) / 2 + 1e-12) - 1)));
    }
  }
  const H = median(S, T, B, 17, true), P = median(S, T, B, 17, false);
  const hz = k => k * fs / N;
  const out = new Float32Array(l.length), norm = new Float32Array(l.length);
  const flux = new Float32Array(T), prev = new Float32Array(B), form = new Float32Array(T);
  for (let t = 0; t < T; t++) {
    let lg = 0, nb = 0;
    for (let k = 0; k < B; k++) {
      const j = t * B + k, f = hz(k), h2 = H[j] * H[j], p2 = P[j] * P[j], harm = h2 / (h2 + p2 + 1e-12);
      const band = f < 120 ? 0 : f < 250 ? (f - 120) / 130 : f <= 4000 ? 1 : 0.6;
      // sibilance is percussive by nature: up top the centre decides more than the split
      const m = band * (f <= 4000 ? harm * (0.4 + 0.6 * C[j]) : (0.5 + 0.5 * harm) * C[j]);
      ar[k] = mre[j] * m; ai[k] = mim[j] * m;
      // formant band: where vowels live and kicks, bass and snare bodies don't
      if (f >= 400 && f <= 4000) {
        const pw = S[j] * S[j] * m * m + 1e-14;
        form[t] += pw; lg += Math.log(pw); nb++;
      }
      if (f >= 250 && f <= 4000) {
        const v = Math.log1p(100 * S[j] * m);
        flux[t] += Math.max(0, v - prev[k]); prev[k] = v;
      }
    }
    // voiced or noise? a vowel's partials stand out of the band (low flatness); a snare, hat or
    // breath fills it evenly. Only voiced sound counts as the voice's loudness.
    const flat = nb ? Math.exp(lg / nb) / (form[t] / nb) : 1;
    form[t] *= Math.max(0, Math.min(1, (0.55 - flat) / 0.3));
    // inverse: conjugate symmetric spectrum, then overlap-add with the same window
    for (let k = 1; k < N / 2; k++) { ar[N - k] = ar[k]; ai[N - k] = -ai[k]; }
    for (let k = 0; k < N; k++) ai[k] = -ai[k];
    fft(ar, ai);
    for (let i = 0; i < N; i++) {
      const s = t * HOP + i;
      if (s >= out.length) break;
      out[s] += (ar[i] / N) * win[i]; norm[s] += win[i] * win[i];
    }
  }
  for (let i = 0; i < out.length; i++) if (norm[i] > 1e-6) out[i] /= norm[i];
  return { x: out, sr: fs, flux, form, hopSec: HOP / fs };
}

// the loud end of a curve, ignoring a few spikes (a stray hit must not set the scale)
function loud(a, q = 0.97) {
  const v = Array.from(a).filter(x => x > 0).sort((x, y) => x - y);
  return v.length ? Math.max(1e-9, v[Math.min(v.length - 1, Math.floor(v.length * q))]) : 1;
}
// the video frame a hop reports on: a sound starts showing once it enters the window's late part
const frameOf = (stem, t, fps) => Math.floor((t * stem.hopSec + (N - HOP) / stem.sr) * fps);

// voice loudness per video frame from the formant band, 0..1 (1 = the voice's loud end)
export function voicePerFrame(stem, fps, n) {
  const sum = new Float32Array(n), cnt = new Float32Array(n);
  for (let t = 0; t < stem.form.length; t++) { const f = frameOf(stem, t, fps); if (f < n) { sum[f] += stem.form[t]; cnt[f]++; } }
  const out = sum.map((v, f) => Math.sqrt(v / Math.max(1, cnt[f])));
  const top = loud(out);
  return out.map(v => Math.min(1, v / top));
}

// syllable-onset strength per video frame, 0..1 (peak flux inside each frame)
export function onsetsPerFrame(stem, fps, n) {
  const out = new Float32Array(n);
  let max = 1e-9;
  for (let t = 0; t < stem.flux.length; t++) {
    const f = frameOf(stem, t, fps);
    if (f < n && stem.flux[t] > out[f]) out[f] = stem.flux[t];
  }
  max = loud(out);
  for (let f = 0; f < n; f++) out[f] = Math.min(1, out[f] / max);
  return out;
}

export const VISEME = { rest: 1, AI: 2, E: 3, O: 4, U: 5, WQ: 6, MBP: 7, FV: 8, L: 9, etc: 10 };

// speech mouths per video frame from a mono signal (see audio.js lipsync)
export function visemesFrom(x, sr, fps, { gate = 0.1, hold = 2, level = null } = {}) {
  const per = sr / fps, n = Math.ceil(x.length / per);
  const k = hz => 1 - Math.exp(-2 * Math.PI * hz / sr);
  const kL = k(500), kM = k(2200), kH = k(3800);
  let l = 0, m = 0, hp = 0, prev = 0;
  const E = new Float32Array(n), LOW = new Float32Array(n), MID = new Float32Array(n), HI = new Float32Array(n), Z = new Float32Array(n);
  let max = 1e-6;
  for (let f = 0; f < n; f++) {
    const a = Math.floor(f * per), b = Math.min(x.length, Math.floor((f + 1) * per));
    let e = 0, el = 0, em = 0, eh = 0, z = 0;
    for (let i = a; i < b; i++) {
      const s = x[i];
      l += kL * (s - l); m += kM * (s - m); hp += kH * (s - hp);
      const mid = m - l, hi = s - hp;
      e += s * s; el += l * l; em += mid * mid; eh += hi * hi;
      if ((s >= 0) !== (prev >= 0)) z++;
      prev = s;
    }
    const c = Math.max(1, b - a);
    E[f] = Math.sqrt(e / c); LOW[f] = el; MID[f] = em; HI[f] = eh; Z[f] = z / c;
    max = Math.max(max, E[f]);
  }
  const out = new Uint8Array(n);
  for (let f = 0; f < n; f++) {
    const e = level ? (level[f] || 0) : E[f] / max, tot = LOW[f] + MID[f] + HI[f] + 1e-12, lo = LOW[f] / tot, hi = HI[f] / tot, z = Z[f] * sr;
    let v;
    if (e < gate) v = VISEME.rest;
    else if (hi > 0.45 || z > 3500) v = z > 5000 ? VISEME.etc : VISEME.FV;      // s, sh, t / f, v
    else if (lo > 0.7) v = e > 0.55 ? VISEME.O : e > 0.3 ? VISEME.U : VISEME.WQ;  // dark, rounded vowels
    else if (lo < 0.35) v = e > 0.5 ? VISEME.E : VISEME.L;                       // bright vowels, l
    else v = e > 0.45 ? VISEME.AI : VISEME.E;                                    // open vowels
    out[f] = v;
  }
  return out;
}

// the gaps between syllables: over a beat the voice rarely falls to silence between words (a
// snare or the room fills it), so a dip well below the syllables on both sides closes the mouth too
export function closures(level, { reach = 4, depth = 0.4, ceiling = 0.45, rise = 0.5 } = {}) {
  const n = level.length, out = new Uint8Array(n);
  const peak = (f, dir) => { let m = 0; for (let k = 1; k <= reach; k++) m = Math.max(m, level[f + dir * k] || 0); return m; };
  for (let f = 1; f < n - 1; f++) {
    if (out[f] || level[f] >= ceiling || level[f] >= depth * Math.min(peak(f, -1), peak(f, 1))) continue;
    // the dip itself, then out to where the voice is half-way back up on each side
    let a = f, b = f;
    while (b + 1 < n && !out[b + 1] && level[b + 1] < depth * Math.min(peak(b + 1, -1) || 1, peak(b + 1, 1))) b++;
    const up = peak(b, 1), down = peak(a, -1);
    while (b + 1 < n && level[b + 1] < rise * up) b++;
    while (a - 1 > 0 && !out[a - 1] && level[a - 1] < rise * down && level[a - 1] < level[a - 2]) a--;
    for (let g = a; g <= b; g++) out[g] = 1;
    f = b;
  }
  return out;
}

// word starts (silence -> sound) snapped onto the nearest syllable onset within `reach` frames
export function alignToOnsets(out, onset, level, { reach = 2, min = 0.2, gate = 0.1 } = {}) {
  const n = out.length, R = VISEME.rest;
  for (let f = 1; f < n; f++) {
    if (out[f] === R || out[f - 1] !== R) continue;
    let p = f, best = onset[f] || 0;
    // a drum hit just before a word is an onset too: only one the voice carries on from counts
    for (let k = Math.max(1, f - reach); k <= Math.min(n - 1, f + reach); k++) {
      if ((onset[k] || 0) > best + 1e-6 && (level[k] || 0) >= gate * 0.6 && (level[k + 1] || 0) >= gate) { best = onset[k]; p = k; }
    }
    // only ever earlier: a drum hit inside the vowel must not push the word late
    if (best < min || p >= f) continue;
    for (let i = p; i < f; i++) out[i] = out[f];
  }
  return out;
}

// the finishing passes: lips meet before a word, no one-frame flickers
export function finishMouths(out, { hold = 2 } = {}) {
  const n = out.length;
  for (let f = 1; f < n; f++) if (out[f] !== VISEME.rest && out[f - 1] === VISEME.rest && out[f] !== VISEME.FV && out[f] !== VISEME.etc) out[f - 1] = VISEME.MBP;
  for (let f = 0; f < n;) {
    let g = f + 1;
    while (g < n && out[g] === out[f]) g++;
    if (g - f < hold && f > 0 && out[f] !== VISEME.MBP) for (let i = f; i < g; i++) out[i] = out[f - 1];
    f = g;
  }
  return out;
}

// is there music under the voice? A dry voice falls to near silence between words; a beat,
// a bass line or a pad keeps the gaps loud. Returns the gap level, 0..1 of the loud end.
export function bedLevel(L, R, sr, fps) {
  const per = Math.floor(sr / fps), n = Math.floor(L.length / per), e = new Float32Array(n);
  for (let f = 0; f < n; f++) {
    let s = 0;
    for (let i = f * per; i < (f + 1) * per; i++) { const v = R ? (L[i] + R[i]) / 2 : L[i]; s += v * v; }
    e[f] = Math.sqrt(s / per);
  }
  const top = loud(e), sorted = Array.from(e).sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length * 0.2)] / top;
}

// the whole pipeline: channels in, mouths per frame out. vocals: 'auto' separates only when
// music sits under the voice; true always; false reads the plain signal (a dry voice track)
export function mouthsFor(L, R, sr, fps, { gate = 0.1, hold = 2, vocals = 'auto' } = {}) {
  const n = Math.ceil(L.length / sr * fps);
  if (vocals === 'auto') vocals = bedLevel(L, R, sr, fps) > 0.06;
  if (!vocals) return finishMouths(visemesFrom(L, sr, fps, { gate, hold }).slice(0, n), { hold });
  const stem = vocalStem(L, R, sr);
  const level = voicePerFrame(stem, fps, n);
  const v = visemesFrom(stem.x, stem.sr, fps, { gate, hold, level });
  const out = new Uint8Array(n).fill(VISEME.rest);
  out.set(v.subarray(0, n));
  // a short dip is the lips meeting between syllables (kept by the flicker pass), a long one is rest
  const shut = closures(level);
  for (let f = 0; f < n;) {
    if (!shut[f]) { f++; continue; }
    let g = f;
    while (g < n && shut[g]) g++;
    for (let i = f; i < g; i++) out[i] = g - f <= 2 && out[f - 1] !== VISEME.rest ? VISEME.MBP : VISEME.rest;
    f = g;
  }
  // a run that never gets loud is what's left of a drum or a breath, not a syllable
  for (let f = 0; f < n;) {
    if (out[f] === VISEME.rest || out[f] === VISEME.MBP) { f++; continue; }
    let g = f, top = 0;
    while (g < n && out[g] !== VISEME.rest && out[g] !== VISEME.MBP) top = Math.max(top, level[g++]);
    if (top < 0.22) for (let i = f; i < g; i++) out[i] = VISEME.rest;
    f = g;
  }
  alignToOnsets(out, onsetsPerFrame(stem, fps, n), level, { gate, min: 0.6 });
  return finishMouths(out, { hold });
}
