// Scene audio (voice or music): imported once for the whole scene, played in sync with
// the timeline, drawn as a waveform under the shot, rendered into the scene video, and
// able to drive any control (music drives a bounce, the voice drives the ears...).

let ctxA = null, buf = null, bufPath = null, src = null, env = null, envKey = '';
const ac = () => (ctxA ||= new AudioContext());

export async function loadAudio(api, path) {
  if (!path) { buf = null; bufPath = null; return null; }
  if (bufPath === path && buf) return buf;
  const { data } = await api('read-audio', { path });
  const bytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
  buf = await ac().decodeAudioData(bytes.buffer);
  bufPath = path;
  env = null;
  return buf;
}
export const audioInfo = () => (buf ? { path: bufPath, seconds: +buf.duration.toFixed(2) } : null);

// loudness per video frame, 0..1 (RMS, normalised to the loudest frame)
export function envelope(fps) {
  if (!buf) return null;
  const key = bufPath + '|' + fps;
  if (env && envKey === key) return env;
  const ch = buf.getChannelData(0), per = buf.sampleRate / fps, n = Math.ceil(buf.duration * fps);
  const out = new Float32Array(n);
  let max = 1e-6;
  for (let f = 0; f < n; f++) {
    let s = 0;
    const a = Math.floor(f * per), b = Math.min(ch.length, Math.floor((f + 1) * per));
    for (let i = a; i < b; i++) s += ch[i] * ch[i];
    out[f] = Math.sqrt(s / Math.max(1, b - a));
    max = Math.max(max, out[f]);
  }
  for (let f = 0; f < n; f++) out[f] /= max;
  env = out; envKey = key;
  return env;
}

export function play(atSeconds) {
  stop();
  if (!buf || atSeconds >= buf.duration) return;
  src = ac().createBufferSource();
  src.buffer = buf;
  src.connect(ac().destination);
  src.start(0, Math.max(0, atSeconds));
}
// the scene audio as a live track, for the playblast recorder
export function streamFrom(atSeconds) {
  if (!buf) return null;
  ac().resume?.();
  const dest = ac().createMediaStreamDestination(), s = ac().createBufferSource();
  s.buffer = buf; s.connect(dest); s.start(0, Math.max(0, atSeconds));
  return { track: dest.stream.getAudioTracks()[0], stop: () => { try { s.stop(); } catch {} } };
}
// part of the scene audio (or a processed copy) as a 16-bit WAV, base64, for Shorts and voices
export function wavBase64(from = 0, to = buf ? buf.duration : 0, source = buf) {
  if (!source) return null;
  const sr = source.sampleRate, ch = Math.min(2, source.numberOfChannels), a = Math.max(0, Math.floor(from * sr)), b = Math.min(source.length, Math.ceil(to * sr)), n = Math.max(0, b - a);
  const d = new DataView(new ArrayBuffer(44 + n * ch * 2)), w = (o, t) => [...t].forEach((c, i) => d.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); d.setUint32(4, 36 + n * ch * 2, true); w(8, 'WAVEfmt '); d.setUint32(16, 16, true); d.setUint16(20, 1, true); d.setUint16(22, ch, true);
  d.setUint32(24, sr, true); d.setUint32(28, sr * ch * 2, true); d.setUint16(32, ch * 2, true); d.setUint16(34, 16, true); w(36, 'data'); d.setUint32(40, n * ch * 2, true);
  const data = [...Array(ch)].map((_, c) => source.getChannelData(c));
  for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) d.setInt16(44 + (i * ch + c) * 2, Math.max(-1, Math.min(1, data[c][a + i])) * 32767, true);
  const bytes = new Uint8Array(d.buffer);
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s);
}
// opt-in character voices: a copy of the scene audio with some spans pitch-shifted
// (a two-tap delay-line shifter, crossfaded) or ring-modulated for a robot
export function processVoice(spans, fps) {
  if (!buf || !spans.length) return null;
  const sr = buf.sampleRate, out = new AudioBuffer({ length: buf.length, numberOfChannels: buf.numberOfChannels, sampleRate: sr });
  const W = Math.round(sr * 0.045);
  for (let c = 0; c < buf.numberOfChannels; c++) {
    const x = buf.getChannelData(c), y = out.getChannelData(c);
    y.set(x);
    const at = t => { const i = Math.floor(t), k = t - i; return i < 0 ? 0 : (x[i] || 0) * (1 - k) + (x[i + 1] || 0) * k; };
    for (const sp of spans) {
      const a = Math.max(0, Math.floor(sp.from / fps * sr)), b = Math.min(x.length, isFinite(sp.to) ? Math.floor(sp.to / fps * sr) : x.length);
      const fade = Math.min(Math.round(sr * 0.01), Math.floor((b - a) / 2));
      for (let i = a; i < b; i++) {
        let v;
        if (sp.factor === 'robot') v = x[i] * (0.6 + 0.4 * Math.sin(2 * Math.PI * 55 * i / sr)) * Math.sin(2 * Math.PI * 30 * i / sr) * 1.6;
        else {
          const ph = ((((i - a) * (1 - sp.factor)) / W) % 1 + 1) % 1, ph2 = (ph + 0.5) % 1;
          const g1 = 1 - Math.abs(2 * ph - 1);
          v = at(i - ph * W) * g1 + at(i - ph2 * W) * (1 - g1);
        }
        const e = Math.min(1, (i - a) / Math.max(1, fade), (b - 1 - i) / Math.max(1, fade));   // no clicks at the edges
        y[i] = x[i] * (1 - e) + v * e;
      }
    }
  }
  return out;
}
export function stop() { try { src?.stop(); } catch {} src = null; }

// waveform strip for one shot of the scene (scene frames from..from+length)
export function waveform(fps, from, length, ppf) {
  const e = envelope(fps);
  if (!e) return null;
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(length * ppf)); c.height = 22;
  c.className = 'wave';
  const g = c.getContext('2d');
  g.fillStyle = getComputedStyle(document.body).getPropertyValue('--fg') || '#1F1F1D';
  for (let f = 0; f < length; f++) {
    const v = e[from + f] || 0, hh = Math.max(1, v * 20);
    g.fillRect(f * ppf, 11 - hh / 2, Math.max(1, ppf - 1), hh);
  }
  return c;
}

// keys a control from the loudness: quiet = min, loud = max; every `step` frames, smoothed
export function audioDrive(project, from, id, min, max, { step = 2, smooth = 2, gate = 0.08 } = {}, setKey) {
  const e = envelope(project.fps);
  if (!e) throw Error('Import audio for the scene first (File › Import audio…)');
  let n = 0;
  for (let f = 0; f < project.length; f += step) {
    let s = 0, c = 0;
    for (let k = -smooth; k <= smooth; k++) { const v = e[from + f + k]; if (v != null) { s += v; c++; } }
    const v = c ? s / c : 0, t = v < gate ? 0 : (v - gate) / (1 - gate);
    setKey(project, id, f, +(min + (max - min) * t).toFixed(2), 'linear');
    n++;
  }
  return n;
}

// ---------------------------------------------------------------- lip sync
// Speech mouths from the voice, per video frame (indices into face.speech:
// 1 rest, 2 AI, 3 E, 4 O, 5 U, 6 WQ, 7 MBP, 8 FV, 9 L, 10 etc). Reads loudness, how bright
// the sound is (band energies) and the zero-crossing rate, so vowels open wide or round,
// hiss and buzz get teeth, and the lips close for a beat before a word starts. No network.
export const VISEME = { rest: 1, AI: 2, E: 3, O: 4, U: 5, WQ: 6, MBP: 7, FV: 8, L: 9, etc: 10 };
let lips = null, lipsKey = '';
export function visemes(fps, { gate = 0.1, hold = 2 } = {}) {
  if (!buf) return null;
  const key = bufPath + '|' + fps + '|' + gate + '|' + hold;
  if (lips && lipsKey === key) return lips;
  const sr = buf.sampleRate, x = buf.getChannelData(0), per = sr / fps, n = Math.ceil(buf.duration * fps);
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
    const e = E[f] / max, tot = LOW[f] + MID[f] + HI[f] + 1e-12, lo = LOW[f] / tot, hi = HI[f] / tot, z = Z[f] * sr;
    let v;
    if (e < gate) v = VISEME.rest;
    else if (hi > 0.45 || z > 3500) v = z > 5000 ? VISEME.etc : VISEME.FV;      // s, sh, t / f, v
    else if (lo > 0.7) v = e > 0.55 ? VISEME.O : e > 0.3 ? VISEME.U : VISEME.WQ;  // dark, rounded vowels
    else if (lo < 0.35) v = e > 0.5 ? VISEME.E : VISEME.L;                       // bright vowels, l
    else v = e > 0.45 ? VISEME.AI : VISEME.E;                                    // open vowels
    out[f] = v;
  }
  // lips meet for a frame just before a word starts (m, b, p land there too)
  for (let f = 1; f < n; f++) if (out[f] !== VISEME.rest && out[f - 1] === VISEME.rest && out[f] !== VISEME.FV && out[f] !== VISEME.etc) out[f - 1] = VISEME.MBP;
  // no one-frame flickers: every mouth holds at least `hold` frames
  for (let f = 0; f < n;) {
    let g = f + 1;
    while (g < n && out[g] === out[f]) g++;
    if (g - f < hold && f > 0 && out[f] !== VISEME.MBP) for (let i = f; i < g; i++) out[i] = out[f - 1];
    f = g;
  }
  lips = out; lipsKey = key;
  return out;
}
// keys the mouth over one shot (scene frames from..from+project.length); returns the keys made
export function lipsync(project, from, setKey, opts = {}) {
  const v = visemes(project.fps, opts);
  if (!v) throw Error('Import the voice for the scene first (File › Import audio…)');
  const keep = (project.tracks.mouth || []).filter(k => k.f < 0 || k.f >= project.length);
  project.tracks.mouth = keep;
  let n = 0, last = -1;
  for (let f = 0; f < project.length; f++) {
    const m = v[from + f] ?? VISEME.rest;
    if (m !== last) { setKey(project, 'mouth', f, m, 'hold'); last = m; n++; }
  }
  return n;
}
