// Doodle Studio 3D "Babble" voice: an original formant synthesiser that turns typed
// dialogue into cute gibberish speech. No recorded or sampled audio: every sound is
// built here from a pulse source, three formant resonators and filtered noise.
// Same text + same voice always gives the same sound (seeded by the text).

export const VISEME = { rest: 1, AI: 2, E: 3, O: 4, U: 5, WQ: 6, MBP: 7, FV: 8, L: 9, etc: 10 };

// one voice per character; every field is a dial in the Voice row
export const VOICES = {
  bunny: { name: 'Bunny', style: 'syllables', pitch: 430, range: 5, speed: 1.0, tract: 1.32, breath: 0.05, bright: 0.9, croak: 0, wobble: 0.15 },
  koala: { name: 'Koala', style: 'syllables', pitch: 215, range: 3, speed: 0.78, tract: 1.05, breath: 0.22, bright: 0.45, croak: 0, wobble: 0.08 },
  frog:  { name: 'Frog',  style: 'syllables', pitch: 290, range: 4, speed: 0.9, tract: 0.92, breath: 0.08, bright: 0.6, croak: 0.55, wobble: 0.35 },
};
export const STYLES = { syllables: 'Syllables', letters: 'Letters', tones: 'Chirps' };
// the dials the user can turn per character (min, max, step, label)
export const DIALS = { pitch: [80, 900, 5, 'Pitch (Hz)'], speed: [0.4, 2, 0.05, 'Speed'], range: [0, 12, 0.5, 'Pitch range'], breath: [0, 0.5, 0.01, 'Breath'], croak: [0, 1, 0.05, 'Croak'] };
// moods bend the character's own voice: pitch ×, range ×, speed ×, extra breath, loudness ×
export const MOODS = {
  neutral: { label: 'Neutral', pitch: 1, range: 1, speed: 1, breath: 0, gain: 1 },
  happy: { label: 'Happy', pitch: 1.12, range: 1.35, speed: 1.1, breath: 0, gain: 1 },
  sad: { label: 'Sad', pitch: 0.86, range: 0.55, speed: 0.78, breath: 0.06, gain: 0.8 },
  angry: { label: 'Angry', pitch: 0.94, range: 1.6, speed: 1.22, breath: 0.03, gain: 1.15, croak: 0.25 },
  sleepy: { label: 'Sleepy', pitch: 0.84, range: 0.45, speed: 0.62, breath: 0.16, gain: 0.75 },
  shocked: { label: 'Shocked', pitch: 1.28, range: 1.9, speed: 1.15, breath: 0, gain: 1.1 },
};
// a character's voice with the user's dials and a mood applied
export function voiceFor(char, dials = {}, mood = 'neutral') {
  const base = { ...(VOICES[char] || VOICES.bunny), ...dials }, m = MOODS[mood] || MOODS.neutral;
  return { ...base, pitch: base.pitch * m.pitch, range: base.range * m.range, speed: base.speed * m.speed, breath: Math.min(0.6, base.breath + m.breath), croak: Math.min(1, base.croak + (m.croak || 0)), gain: m.gain };
}

const VOWELS = { a: [800, 1200, 2500], e: [520, 1850, 2600], i: [300, 2250, 3000], o: [520, 860, 2400], u: [340, 800, 2300], y: [300, 2100, 2900] };
const VIS_V = { a: 'AI', e: 'E', i: 'E', o: 'O', u: 'U', y: 'E' };
// letters → the vowel their blip sings (for the letter style) and the onset they start with
const LETTER_VOWEL = { b: 'e', c: 'i', d: 'e', f: 'e', g: 'i', h: 'a', j: 'a', k: 'a', l: 'e', m: 'e', n: 'e', p: 'i', q: 'u', r: 'a', s: 'e', t: 'i', v: 'i', w: 'u', x: 'e', z: 'e' };
const ONSET = { p: 'plo', b: 'plo', t: 'plo', d: 'plo', k: 'plo', g: 'plo', c: 'plo', q: 'plo', s: 'fri', z: 'fri', f: 'fri', v: 'fri', h: 'asp', x: 'fri', j: 'fri', m: 'nas', n: 'nas', l: 'liq', r: 'liq', w: 'liq' };
const PLACE = { p: 900, b: 700, t: 4200, d: 3600, k: 2200, g: 1900, c: 2200, q: 2000, s: 6500, z: 5500, f: 3200, v: 2600, x: 5000, j: 3000, h: 1500 };
const VIS_C = { m: 'MBP', b: 'MBP', p: 'MBP', f: 'FV', v: 'FV', l: 'L', w: 'WQ', q: 'WQ' };

function rng(seed) { let s = seed >>> 0 || 1; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296); }
function hash(str) { let h = 2166136261; for (const c of str) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }

// text → units: { kind:'syl', onset, vowel, word, stress } | { kind:'gap', len, tone }
export function units(text, style = 'syllables') {
  const out = [], words = [];
  const re = /([A-Za-zÀ-ɏ']+|[0-9]+)|([.!?…]+)|([,;:\-–—]+)/g;
  let m, wi = -1, sentence = 0;
  while ((m = re.exec(text))) {
    if (m[1]) {
      const w = m[1].toLowerCase().normalize('NFD').replace(/[^a-z0-9]/g, '');
      if (!w) continue;
      wi++; words.push({ text: m[1], sentence, units: [] });
      const parts = style === 'letters' ? letterUnits(w) : sylUnits(w);
      parts.forEach((p, i) => { p.word = wi; p.first = i === 0; p.kind = 'syl'; words[wi].units.push(out.length); out.push(p); });
      out.push({ kind: 'gap', len: 0.045 });
    } else if (m[2]) {
      if (words.length && words[words.length - 1].sentence === sentence) words[words.length - 1].text += m[2];
      out.push({ kind: 'gap', len: 0.32, tone: m[2].includes('?') ? '?' : m[2].includes('!') ? '!' : '.' }); sentence++;
    } else { if (words.length && /^[,;:]/.test(m[3])) words[words.length - 1].text += m[3][0]; out.push({ kind: 'gap', len: 0.16, tone: ',' }); }
  }
  return { units: out, words };
}
function sylUnits(w) {
  const digits = { 0: 'o', 1: 'a', 2: 'u', 3: 'i', 4: 'o', 5: 'a', 6: 'i', 7: 'e', 8: 'a', 9: 'a' };
  w = w.replace(/[0-9]/g, d => 'n' + digits[d]);
  const out = [], re = /([^aeiouy]*)([aeiouy]+)/g;
  let m, last = 0;
  while ((m = re.exec(w))) { out.push({ onset: m[1].slice(-1) || '', vowel: m[2][0] === 'y' && m[2].length > 1 ? m[2][1] : m[2][0], long: m[2].length > 1 }); last = re.lastIndex; }
  if (!out.length) out.push({ onset: w[0] || '', vowel: LETTER_VOWEL[w[0]] || 'a' });
  else if (last < w.length && out.length) out[out.length - 1].coda = w[w.length - 1];
  return out;
}
function letterUnits(w) {
  return [...w].map(c => /[aeiouy]/.test(c) ? { onset: '', vowel: c, short: true } : { onset: c, vowel: LETTER_VOWEL[c] || 'a', short: true });
}

// the voice: returns { samples: Float32Array, sr, visemes(fps), words:[{text,t0,t1}] }
export function speak(text, voice = VOICES.bunny, { sr = 48000, style, seed = 0 } = {}) {
  const v = { ...VOICES.bunny, ...voice };
  style = style || v.style || 'syllables';
  const tones = style === 'tones';
  if (tones) style = 'letters';
  const { units: U, words } = units(text, style);
  const R = rng(hash(text) ^ seed ^ hash(v.name || ''));
  const sylLen = (style === 'letters' ? 0.062 : 0.115) / v.speed;
  // timeline
  let t = 0.06; const ev = [];
  const sentEnd = [];
  for (let i = 0; i < U.length; i++) {
    const u = U[i];
    if (u.kind === 'gap') { t += u.len / Math.sqrt(v.speed); if (u.tone) sentEnd.push({ i, tone: u.tone }); continue; }
    const len = sylLen * (u.long ? 1.35 : 1) * (0.85 + R() * 0.3) * (u.coda ? 1.12 : 1);
    ev.push({ ...u, t0: t, t1: t + len, i });
    t += len;
  }
  const total = t + 0.12, n = Math.ceil(total * sr), out = new Float32Array(n);
  // intonation per syllable: random hop around the base, declination, sentence-end shape
  for (const e of ev) {
    const end = sentEnd.find(s => s.i > e.i);
    const lastOfSentence = end && !ev.some(o => o.i > e.i && o.i < end.i);
    let semi = (R() * 2 - 1) * v.range + (e.first ? 1.5 : 0);
    if (end?.tone === '!') semi += 2.5;
    let glide = -0.6;
    if (lastOfSentence && end.tone === '?') { semi += 3; glide = 4; }
    if (lastOfSentence && end.tone === '.') { semi -= 2; glide = -2.5; }
    e.f0 = v.pitch * 2 ** (semi / 12); e.f1 = e.f0 * 2 ** (glide / 12);
  }
  // render each syllable additively
  for (const e of ev) {
    const a = Math.floor(e.t0 * sr), b = Math.min(n, Math.floor(e.t1 * sr)), L = b - a;
    const F = VOWELS[e.vowel] || VOWELS.a, oc = e.onset, kind = ONSET[oc];
    const vStart = kind === 'plo' ? 0.018 : kind === 'fri' ? 0.035 : kind === 'asp' ? 0.025 : 0;
    const vs = Math.floor(vStart * sr / Math.max(.6, v.speed));
    // consonant noise
    if (kind === 'plo' || kind === 'fri' || kind === 'asp') {
      const len = kind === 'plo' ? Math.floor(0.009 * sr) : vs, fc = (PLACE[oc] || 2500) * Math.sqrt(v.tract);
      const bp = res(fc, fc * 0.5, sr); const amp = kind === 'plo' ? 0.5 : kind === 'asp' ? 0.12 : 0.18;
      for (let k = 0; k < len && a + k < n; k++) { const env = kind === 'plo' ? Math.exp(-k / (0.003 * sr)) : Math.sin(Math.PI * k / len); out[a + k] += bp((R() * 2 - 1)) * amp * env; }
    }
    // voiced part through three formants
    const startF = kind === 'liq' ? (oc === 'w' ? VOWELS.u : oc === 'r' ? [400, 1300, 1700] : [380, 1500, 2700]) : kind === 'nas' ? [280, 1000, 2300] : F;
    const fr = [0, 1, 2].map(j => resDyn(sr));
    let ph = 0, sub = 0;
    const att = Math.floor(0.006 * sr), rel = Math.floor(0.03 * sr);
    for (let k = vs; k < L; k++) {
      const x = k / L, idx = a + k; if (idx >= n) break;
      const f0 = (e.f0 + (e.f1 - e.f0) * x) * (1 + v.wobble * 0.02 * Math.sin(2 * Math.PI * 5.5 * (idx / sr)));
      ph += f0 / sr; if (ph >= 1) { ph -= 1; sub ^= 1; }
      let src;
      if (tones) src = Math.sin(2 * Math.PI * ph) * 0.6 + Math.sin(4 * Math.PI * ph) * 0.15;
      else {
        // soft glottal pulse (Rosenberg-like), brighter voices get a sharper closing edge
        const op = 0.6 - 0.2 * v.bright;
        src = ph < op ? 0.5 * (1 - Math.cos(Math.PI * ph / op)) : Math.cos(Math.PI * (ph - op) / (2 * (1 - op)));
        src = src * 2 - 1;
        if (v.croak) src *= 1 - v.croak * 0.6 * sub * (0.5 + 0.5 * Math.sin(2 * Math.PI * 28 * idx / sr));
        src += (R() * 2 - 1) * v.breath;
      }
      const glideT = Math.min(1, (k - vs) / (0.035 * sr));
      const nas = kind === 'nas' && k - vs < 0.03 * sr;
      let y = 0;
      if (tones) y = src;
      else for (let j = 0; j < 3; j++) {
        const f = (startF[j] + (F[j] - startF[j]) * glideT) * v.tract;
        y += fr[j](src, f, [70, 110, 160][j] * v.tract, sr) * [1, 0.7 * (0.6 + v.bright * 0.5), 0.25 * v.bright][j];
      }
      if (nas) y *= 0.5;
      const env = Math.min(1, (k - vs) / att) * Math.min(1, (L - k) / rel) * (e.first ? 1 : 0.88);
      out[idx] += y * env * (tones ? 0.35 : 0.22);
    }
    // a soft coda click for words ending in a stop
    if (e.coda && ONSET[e.coda] === 'plo') { const bp = res(PLACE[e.coda] || 2500, 1200, sr); for (let k = 0; k < 0.006 * sr && b + k < n; k++) out[b + k] += bp(R() * 2 - 1) * 0.2 * Math.exp(-k / (0.002 * sr)); }
  }
  // DC blocker, normalise, then a gentle soft-knee limiter to −1 dBFS
  let xp = 0, yp = 0; for (let i = 0; i < n; i++) { const y = out[i] - xp + 0.995 * yp; xp = out[i]; yp = y; out[i] = y; }
  let peak = 1e-6; for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(out[i]));
  for (let i = 0; i < n; i++) { const x = out[i] / peak * 0.95; out[i] = Math.abs(x) < 0.6 ? x : Math.sign(x) * (0.6 + 0.3 * Math.tanh((Math.abs(x) - 0.6) / 0.3)); }
  peak = 1e-6; for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(out[i]));
  const g = 0.89 / peak * Math.min(1.12, v.gain ?? 1) / 1.12; for (let i = 0; i < n; i++) out[i] *= g;
  const wordTimes = words.map(w => { const es = ev.filter(e => w.units.includes(e.i)); return { text: w.text, sentence: w.sentence, t0: es[0]?.t0 ?? 0, t1: es[es.length - 1]?.t1 ?? 0 }; });
  return {
    samples: out, sr, seconds: total, words: wordTimes,
    // mouth shape per video frame, straight from the syllables (no audio analysis needed)
    visemes(fps) {
      const nf = Math.ceil(total * fps), m = new Array(nf).fill(VISEME.rest);
      for (const e of ev) {
        const f0 = Math.floor(e.t0 * fps), f1 = Math.max(f0 + 1, Math.round(e.t1 * fps));
        const on = VIS_C[e.onset], vow = VISEME[VIS_V[e.vowel] || 'AI'];
        for (let f = f0; f < f1 && f < nf; f++) m[f] = on && f === f0 && f1 - f0 > 2 ? VISEME[on] : vow;
      }
      return m;
    },
  };
}
// fixed two-pole resonator
function res(f, bw, sr) { const r = Math.exp(-Math.PI * bw / sr), a1 = 2 * r * Math.cos(2 * Math.PI * f / sr), a2 = -r * r, g = 1 - r; let y1 = 0, y2 = 0; return x => { const y = g * x + a1 * y1 + a2 * y2; y2 = y1; y1 = y; return y; }; }
// resonator whose frequency can move every sample
function resDyn() { let y1 = 0, y2 = 0; return (x, f, bw, sr) => { const r = Math.exp(-Math.PI * bw / sr), a1 = 2 * r * Math.cos(2 * Math.PI * Math.min(f, sr * 0.45) / sr), a2 = -r * r, y = (1 - r) * x + a1 * y1 + a2 * y2; y2 = y1; y1 = y; return y * 3; }; }

// 16-bit mono WAV bytes
export function wav(samples, sr) {
  const n = samples.length, d = new DataView(new ArrayBuffer(44 + n * 2)), w = (o, t) => [...t].forEach((c, i) => d.setUint8(o + i, c.charCodeAt(0)));
  w(0, 'RIFF'); d.setUint32(4, 36 + n * 2, true); w(8, 'WAVEfmt '); d.setUint32(16, 16, true); d.setUint16(20, 1, true); d.setUint16(22, 1, true);
  d.setUint32(24, sr, true); d.setUint32(28, sr * 2, true); d.setUint16(32, 2, true); d.setUint16(34, 16, true); w(36, 'data'); d.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) d.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 32767, true);
  return new Uint8Array(d.buffer);
}

// caption chunks from the timed words: one per sentence, long sentences split into
// near-even pieces of at most `max` words (so captions stay short, two lines at most)
export function captionChunks(words, max = 6) {
  const out = [], bySent = [];
  for (const w of words) (bySent[w.sentence] ||= []).push(w);
  for (const s of bySent.filter(Boolean)) {
    const parts = Math.ceil(s.length / max), per = Math.ceil(s.length / parts);
    for (let i = 0; i < s.length; i += per) { const c = s.slice(i, i + per); out.push({ text: c.map(w => w.text).join(' '), t0: c[0].t0, t1: c[c.length - 1].t1 }); }
  }
  return out;
}
