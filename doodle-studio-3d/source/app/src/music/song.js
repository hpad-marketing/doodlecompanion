// Music workspace: the song model and every pure operation on it (no audio here, so it runs in node tests).
// scene.song = {
//   v, bpm, sig (beats per bar), key (0-11, C=0), scale, swing (0-0.6),
//   sections: [{ id, name, bars }]          rows of the clip launcher (Intro, Verse, Chorus...)
//   cur: section index the looper works on
//   arr: [sectionId...]                     the song order over the animation; empty = cur repeats
//   fill: true                              repeat the song so it lasts the whole scene
//   offset: seconds                         where the song starts in the scene
//   tracks: [{ id, name, inst, kind: 'inst'|'drum', vol (dB), pan (-1..1), mute, solo, fx: [{ type, on, p: {} }],
//              clips: { [sectionId]: { notes: [{ t, d, n, v, take? }] } } }]
//   master: { vol, fx }
// }
// Times are in beats from the start of the clip. n is a MIDI note number, v velocity 0..1.

let seq = 0;
export const uid = p => (p || 'm') + Date.now().toString(36).slice(-5) + (seq++).toString(36);
export const NOTE_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B'];
export const noteName = n => NOTE_NAMES[((n % 12) + 12) % 12] + (Math.floor(n / 12) - 1);
export function parseNote(s) {
  if (typeof s === 'number') return s;
  const m = /^([A-Ga-g])([#b]?)(-?\d)$/.exec(String(s).trim());
  if (!m) throw Error(`Note "${s}" should look like C4, F#3 or Bb2 (or a MIDI number)`);
  const base = { c: 0, d: 2, e: 4, f: 5, g: 7, a: 9, b: 11 }[m[1].toLowerCase()];
  return base + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0) + (Number(m[3]) + 1) * 12;
}

export const SCALES = {
  major: [0, 2, 4, 5, 7, 9, 11], minor: [0, 2, 3, 5, 7, 8, 10], dorian: [0, 2, 3, 5, 7, 9, 10], mixolydian: [0, 2, 4, 5, 7, 9, 10],
  phrygian: [0, 1, 3, 5, 7, 8, 10], lydian: [0, 2, 4, 6, 7, 9, 11], harmonic: [0, 2, 3, 5, 7, 8, 11],
  pentatonic: [0, 2, 4, 7, 9], minorpenta: [0, 3, 5, 7, 10], blues: [0, 3, 5, 6, 7, 10], chromatic: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
  bhairav: [0, 1, 4, 5, 7, 8, 11], kafi: [0, 2, 3, 5, 7, 9, 10], japanese: [0, 1, 5, 7, 8],
};
export const SCALE_NAMES = { major: 'Major', minor: 'Minor', dorian: 'Dorian', mixolydian: 'Mixolydian', phrygian: 'Phrygian', lydian: 'Lydian', harmonic: 'Harmonic minor', pentatonic: 'Major pentatonic', minorpenta: 'Minor pentatonic', blues: 'Blues', chromatic: 'Chromatic (all notes)', bhairav: 'Bhairav (raag)', kafi: 'Kafi (raag)', japanese: 'Japanese (In)' };

export function newSong() {
  const verse = { id: uid('s'), name: 'Loop A', bars: 4 };
  return { v: 1, bpm: 100, sig: 4, key: 0, scale: 'major', swing: 0, sections: [verse], cur: 0, arr: [], fill: true, offset: 0,
    tracks: [newTrack('Drums', 'kit:808', 'drum'), newTrack('Keys', 'gm:acoustic_grand_piano')], master: { vol: 0, fx: [{ type: 'limiter', on: true, p: {} }] } };
}
export function newTrack(name, inst, kind = inst.startsWith('kit:') ? 'drum' : 'inst') {
  return { id: uid('t'), name, inst, kind, vol: -6, pan: 0, mute: false, solo: false, fx: [], clips: {} };
}
export function migrateSong(s) {
  if (!s) return null;
  s.v ??= 1; s.bpm ??= 100; s.sig ??= 4; s.key ??= 0; s.scale ??= 'major'; s.swing ??= 0; s.sections ??= [{ id: uid('s'), name: 'Loop A', bars: 4 }];
  s.cur = Math.max(0, Math.min(s.sections.length - 1, s.cur ?? 0)); s.arr ??= []; s.fill ??= true; s.offset ??= 0; s.tracks ??= []; s.master ??= { vol: 0, fx: [] };
  for (const t of s.tracks) { t.fx ??= []; t.clips ??= {}; t.vol ??= -6; t.pan ??= 0; t.kind ??= String(t.inst).startsWith('kit:') ? 'drum' : 'inst'; }
  s.arr = s.arr.filter(id => s.sections.some(x => x.id === id));
  return s;
}

export const secPerBeat = s => 60 / s.bpm;
export const sectionBeats = (s, sec) => sec.bars * s.sig;
export const curSection = s => s.sections[s.cur];
export function clipOf(t, sec, make = false) {
  const id = typeof sec === 'string' ? sec : sec.id;
  if (!t.clips[id] && make) t.clips[id] = { notes: [] };
  return t.clips[id] || null;
}
export const hasNotes = s => !!s?.tracks?.some(t => Object.values(t.clips).some(c => c.notes.length));

// the song laid out in time: [{ sec, start (beats), beats }]
export function layout(s) {
  const order = s.arr.length ? s.arr.map(id => s.sections.find(x => x.id === id)).filter(Boolean) : [curSection(s)];
  let at = 0;
  return order.map(sec => { const r = { sec, start: at, beats: sectionBeats(s, sec) }; at += r.beats; return r; });
}
export const songBeats = s => layout(s).reduce((a, x) => a + x.beats, 0);
export const songSeconds = s => songBeats(s) * secPerBeat(s);

// swing pushes every off-beat eighth later by up to a third of a beat
export function swung(s, t) {
  if (!s.swing) return t;
  const half = t * 2, i = Math.floor(half + 1e-9), frac = half - i;
  return i % 2 === 1 && frac < 1e-6 ? t + s.swing / 3 : t;
}

// every note to play in [from, to) beats of song time. loop: the section cur repeats forever;
// otherwise the arrangement (repeated when fill is on, up to `until` beats).
export function eventsIn(s, from, to, { loop = false, until = Infinity } = {}) {
  const out = [], solo = s.tracks.some(t => t.solo);
  const parts = loop ? [{ sec: curSection(s), start: 0, beats: sectionBeats(s, curSection(s)) }] : layout(s);
  const total = parts.reduce((a, x) => a + x.beats, 0);
  if (!total) return out;
  const repeat = loop || s.fill;
  for (let base = Math.floor(from / total) * total; base < to; base += total) {
    if (!repeat && base > 0) break;
    for (const p of parts) {
      const a = base + p.start, b = a + p.beats;
      if (b <= from || a >= to || a >= until) continue;
      for (const t of s.tracks) {
        if (t.mute || (solo && !t.solo)) continue;
        const c = t.clips[p.sec.id]; if (!c) continue;
        for (const nt of c.notes) {
          if (nt.t >= p.beats) continue;
          const at = a + swung(s, nt.t);
          if (at >= from && at < to && at < until) out.push({ track: t, at, d: Math.min(nt.d, p.beats - nt.t), n: nt.n, v: nt.v });
        }
      }
    }
  }
  return out.sort((x, y) => x.at - y.at);
}

// ---------------------------------------------------------------- note edits
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export function quantize(notes, grid = 0.25, strength = 1, ends = false) {
  for (const n of notes) {
    const q = Math.round(n.t / grid) * grid;
    n.t = +(n.t + (q - n.t) * strength).toFixed(4);
    if (ends) n.d = Math.max(grid, +(Math.round(n.d / grid) * grid).toFixed(4));
  }
  return notes;
}
// tiny random timing and loudness changes so a programmed part sounds played (seeded, so tests repeat)
export function humanize(notes, amount = 0.5, seed = 1) {
  let x = seed * 9301 + 49297;
  const rnd = () => ((x = (x * 9301 + 49297) % 233280) / 233280) - 0.5;
  for (const n of notes) { n.t = Math.max(0, +(n.t + rnd() * 0.06 * amount).toFixed(4)); n.v = clamp(+(n.v + rnd() * 0.25 * amount).toFixed(3), 0.05, 1); }
  return notes;
}
export const transpose = (notes, by) => { for (const n of notes) n.n = clamp(n.n + by, 0, 127); return notes; };
export function legato(notes) {
  const s = [...notes].sort((a, b) => a.t - b.t);
  s.forEach((n, i) => { const nx = s.slice(i + 1).find(m => m.t > n.t + 1e-6); if (nx) n.d = +(nx.t - n.t).toFixed(4); });
  return notes;
}
// make a loop twice as long, copying what is there
export function double(s, sec) {
  const beats = sectionBeats(s, sec);
  for (const t of s.tracks) { const c = t.clips[sec.id]; if (c) c.notes.push(...c.notes.map(n => ({ ...n, t: n.t + beats }))); }
  sec.bars *= 2;
  return sec;
}
export function snapToScale(n, key, scale) {
  const sc = SCALES[scale] || SCALES.major, pc = ((n - key) % 12 + 12) % 12;
  let best = 0, dist = 99;
  for (const d of sc) for (const o of [-12, 0, 12]) { const dd = Math.abs(d + o - pc); if (dd < dist || (dd === dist && d + o < best)) { dist = dd; best = d + o; } }
  return n - pc + best;
}

// ---------------------------------------------------------------- chords and progressions
export const CHORDS = { off: null, triad: 'Triad (in key)', seventh: '7th (in key)', power: 'Power (root + 5th)', octave: 'Octaves', sus: 'Sus4', major: 'Major', minor: 'Minor', add9: 'Add9 (in key)' };
// notes of a chord built on n
export function chordNotes(n, kind, key = 0, scale = 'major') {
  if (!kind || kind === 'off') return [n];
  if (kind === 'power') return [n, n + 7];
  if (kind === 'octave') return [n, n + 12];
  if (kind === 'major') return [n, n + 4, n + 7];
  if (kind === 'minor') return [n, n + 3, n + 7];
  if (kind === 'sus') return [n, n + 5, n + 7];
  const sc = (SCALES[scale] || SCALES.major), root = snapToScale(n, key, scale);
  const step = k => { const pc = ((root - key) % 12 + 12) % 12, i = sc.indexOf(pc), j = i + k; return root + (sc[j % sc.length] + 12 * Math.floor(j / sc.length)) - sc[i]; };
  if (kind === 'seventh') return [root, step(2), step(4), step(6)];
  if (kind === 'add9') return [root, step(2), step(4), step(7)];
  return [root, step(2), step(4)];
}
export const PROGRESSIONS = {
  pop: ['Pop (I–V–vi–IV)', [1, 5, 6, 4]], sad: ['Emotional (vi–IV–I–V)', [6, 4, 1, 5]], fifties: ['Fifties (I–vi–IV–V)', [1, 6, 4, 5]],
  jazz: ['Jazzy (ii–V–I–I)', [2, 5, 1, 1]], epic: ['Epic (i–VI–III–VII)', [1, 6, 3, 7]], lofi: ['Lo-fi (IVmaj7–iii7–ii7–I)', [4, 3, 2, 1]],
  comedy: ['Comedy bounce (I–IV–I–V)', [1, 4, 1, 5]], spooky: ['Spooky (i–iv–V–i)', [1, 4, 5, 1]], hope: ['Hopeful (IV–V–iii–vi)', [4, 5, 3, 6]], drone: ['One-chord groove (I)', [1]],
};
// chord on scale degree (1-7) in key/scale, root around octave 4
export function degreeChord(deg, key, scale, seventh = false, octave = 4) {
  const sc = SCALES[scale]?.length === 7 ? SCALES[scale] : SCALES.major;
  const root = 12 * (octave + 1) + key + sc[(deg - 1) % 7];
  return chordNotes(root, seventh ? 'seventh' : 'triad', key, SCALES[scale]?.length === 7 ? scale : 'major');
}
// write a progression into a clip: styles block (held chords), stabs (offbeat), arp (broken), and a bass line track optional
export function progression(s, track, sec, name = 'pop', style = 'block', seventh = false) {
  const p = PROGRESSIONS[name]; if (!p) throw Error('progression must be one of ' + Object.keys(PROGRESSIONS).join(', '));
  const beats = sectionBeats(s, sec), per = beats / p[1].length, c = clipOf(track, sec, true);
  c.notes = [];
  p[1].forEach((deg, i) => {
    const ch = degreeChord(deg, s.key, s.scale, seventh || name === 'lofi', track.kind === 'drum' ? 3 : (/bass/i.test(track.inst) ? 2 : 4)), t0 = i * per;
    if (/bass/i.test(track.inst)) { for (let b = 0; b < per; b += 1) c.notes.push({ t: t0 + b, d: 0.9, n: ch[0], v: b ? 0.7 : 0.9 }); return; }
    if (style === 'stabs') for (let b = 0.5; b < per; b += 1) ch.forEach(n => c.notes.push({ t: t0 + b, d: 0.35, n, v: 0.75 }));
    else if (style === 'arp') for (let b = 0, k = 0; b < per; b += 0.5, k++) c.notes.push({ t: t0 + b, d: 0.45, n: ch[[0, 1, 2, 1, 3 % ch.length, 2][k % 6] % ch.length] + (k % 6 === 4 ? 12 : 0), v: 0.7 });
    else ch.forEach(n => c.notes.push({ t: t0, d: per - 0.05, n, v: 0.7 }));
  });
  return c;
}

// ---------------------------------------------------------------- drums
// pad order of every kit: the MiniLab's pads send notes 36-51 on channel 10
export const PADS = ['Kick', 'Snare', 'Clap', 'Closed hat', 'Open hat', 'Low tom', 'High tom', 'Crash', 'Rim', 'Shaker', 'Cowbell', 'Ride', 'Boing', 'Pop', 'Whoosh', 'Thud'];
export const PAD_BASE = 36;
export const DRUM_STYLES = {
  basic: ['Basic rock', { 0: [0, 2], 1: [1, 3], 3: [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5] }],
  hiphop: ['Hip-hop', { 0: [0, 1.75, 2.5], 1: [1, 3], 3: [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5] }],
  trap: ['Trap', { 0: [0, 2.75], 1: [2], 3: [0, 0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.625, 1.75, 2, 2.5, 3, 3.25, 3.5, 3.75] }],
  house: ['Four on the floor', { 0: [0, 1, 2, 3], 2: [1, 3], 4: [0.5, 1.5, 2.5, 3.5] }],
  lofi: ['Lo-fi', { 0: [0, 2.5], 1: [1, 3], 9: [0.5, 1.5, 2.5, 3.5], 8: [3.75] }],
  bhangra: ['Dhol bounce', { 0: [0, 0.75, 1.5, 2, 2.75, 3.5], 8: [1, 3], 1: [1.25, 3.25] }],
  reggaeton: ['Dembow', { 0: [0, 1, 2, 3], 1: [0.75, 1.5, 2.75, 3.5] }],
  march: ['Comedy march', { 0: [0, 2], 1: [1, 3], 10: [0, 1, 2, 3] }],
};
export function drumPattern(s, track, sec, style = 'basic') {
  const p = DRUM_STYLES[style]; if (!p) throw Error('style must be one of ' + Object.keys(DRUM_STYLES).join(', '));
  const c = clipOf(track, sec, true), bars = sec.bars;
  c.notes = [];
  for (let b = 0; b < bars; b++) for (const [pad, hits] of Object.entries(p[1])) for (const h of hits) c.notes.push({ t: b * s.sig + h * s.sig / 4, d: 0.2, n: PAD_BASE + Number(pad), v: h % 1 ? 0.6 : 0.9 });
  return c;
}

// ---------------------------------------------------------------- arpeggiator (pure: held notes -> the next note)
export const ARPS = { off: 'Off', up: 'Up', down: 'Down', updown: 'Up and down', random: 'Random', order: 'As played', chord: 'Repeat chord' };
export function arpStep(held, mode, i, octaves = 1, seed = 0) {
  if (!held.length) return [];
  const base = mode === 'order' ? held : [...held].sort((a, b) => a - b);
  const span = []; for (let o = 0; o < octaves; o++) span.push(...base.map(n => n + 12 * o));
  if (mode === 'chord') return base;
  if (mode === 'down') return [span[span.length - 1 - (i % span.length)]];
  if (mode === 'updown') { const cyc = span.length > 1 ? [...span, ...span.slice(1, -1).reverse()] : span; return [cyc[i % cyc.length]]; }
  if (mode === 'random') return [span[Math.abs((i * 7919 + seed * 31) % span.length)]];
  return [span[i % span.length]];
}

// ---------------------------------------------------------------- time maps
// song beat -> scene seconds and back (offset = where the song starts in the scene)
export const beatToSec = (s, b) => s.offset + b * secPerBeat(s);
export const secToBeat = (s, t) => (t - s.offset) / secPerBeat(s);
// set the tempo so the arrangement fits the scene exactly (keeps the bars, changes speed)
export function fitTempo(s, sceneSeconds) {
  const beats = songBeats(s);
  if (!beats || sceneSeconds <= s.offset) throw Error('Nothing to fit');
  s.bpm = clamp(+(beats * 60 / (sceneSeconds - s.offset)).toFixed(2), 30, 300);
  return s.bpm;
}
// times in scene seconds of the hits of one track (optionally one note), over `seconds`
export function hitTimes(s, trackId, { note = null, seconds = 60, loop = false } = {}) {
  const t = s.tracks.find(x => x.id === trackId || x.name === trackId);
  if (!t) throw Error('No such track');
  const until = secToBeat(s, seconds);
  return eventsIn({ ...s, tracks: [{ ...t, mute: false, solo: false }] }, 0, until, { loop, until })
    .filter(e => note == null || e.n === note).map(e => ({ at: +beatToSec(s, e.at).toFixed(4), n: e.n, v: e.v, d: e.d * secPerBeat(s) }));
}
