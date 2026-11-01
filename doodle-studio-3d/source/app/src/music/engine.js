// Music workspace sound engine: live playing with no wait, the looper and recorder, the song
// player (follows the animation timeline), metronome, and offline bounces to WAV.
import * as S from './song.js';
import { makeInstrument, makeFx, setFx, FX } from './instruments.js';
const T = () => window.Tone;

const E = {
  song: null, api: null, started: false, playing: false, recording: false, follow: false, loop: true,
  t0: 0, from: 0, scheduled: 0, timer: null, until: Infinity, countIn: 0, countBeats: 0,
  metro: false, preRoll: 1, rec: null, take: 0, passNotes: 0, lastPass: -1,
  chains: new Map(), master: null, masterSig: '', held: new Map(), sustain: false, sustained: new Set(),
  history: [], listeners: new Set(), arpHeld: [], arpIndex: 0, arpNext: 0, repeatPads: new Map(),
  helpers: { scaleLock: false, chord: 'off', arp: 'off', arpRate: 0.25, arpOct: 1, octave: 0, transpose: 0, repeat: 0, fixedVel: 0, quant: 0.25, quantOn: true, mode: 'overdub' },
};
try { Object.assign(E.helpers, JSON.parse(localStorage.getItem('ds3d.music.helpers') || '{}')); } catch {}
export const engine = E;
export const saveHelpers = () => { try { localStorage.setItem('ds3d.music.helpers', JSON.stringify(E.helpers)); } catch {} };
const emit = (what, x) => { for (const f of E.listeners) try { f(what, x); } catch {} };
export const on = f => (E.listeners.add(f), () => E.listeners.delete(f));

export function init({ api }) { E.api = api; }
// audio can only start after a click or key press; MIDI input counts in Electron
export async function start() {
  if (E.started) return;
  const Tone = T();
  if (!Tone) throw Error('The sound engine did not load');
  try { Tone.setContext(new Tone.Context({ latencyHint: 'interactive', lookAhead: 0.03 })); } catch {}
  await Tone.start();
  E.started = true;
  E.click = new Tone.Synth({ oscillator: { type: 'square' }, envelope: { attack: 0.001, decay: 0.03, sustain: 0, release: 0.01 } }).toDestination();
  E.click.volume.value = -12;
  if (E.song) sync(E.song);
}
export const latencyMs = () => { const c = T()?.getContext?.().rawContext; return c ? Math.round(((c.baseLatency || 0) + (c.outputLatency || 0)) * 1000) : null; };

// ---------------------------------------------------------------- the track chains
const sigOf = t => JSON.stringify([t.inst, t.fx.map(f => [f.type, f.on]), t.inst === 'kit:user' ? t.samples : 0]);
function buildMaster(song) {
  const Tone = T();
  const sig = JSON.stringify(song.master.fx.map(f => [f.type, f.on]));
  if (E.master && E.masterSig === sig) { E.master.ch.volume.value = song.master.vol; return; }
  if (E.master) for (const n of E.master.nodes) try { n.dispose(); } catch {}
  const ch = new Tone.Channel(song.master.vol, 0), meter = new Tone.Meter({ smoothing: 0.8 }), fx = song.master.fx.filter(f => f.on).map(makeFx).filter(Boolean);
  ch.chain(...fx, Tone.getDestination()); ch.connect(meter);
  E.master = { ch, meter, fx, nodes: [ch, meter, ...fx] }; E.masterSig = sig;
  for (const c of E.chains.values()) c.ch.connect(ch);
}
function buildChain(t, dest, api = E.api) {
  const Tone = T();
  const inst = makeInstrument(t.inst, { api, track: t });
  const tone = new Tone.Filter(20000, 'lowpass');
  const fx = t.fx.filter(f => f.on).map(f => { const n = makeFx(f); if (n) n._def = f; return n; }).filter(Boolean);
  const ch = new Tone.Channel(t.vol, t.pan), meter = new Tone.Meter({ smoothing: 0.8 });
  inst.out.chain(tone, ...fx, ch); ch.connect(dest); ch.connect(meter);
  return { inst, tone, fx, ch, meter, sig: sigOf(t), nodes: [tone, ...fx, ch, meter] };
}
// make the audio graph match the song (cheap when nothing changed)
export function sync(song) {
  E.song = song;
  if (!E.started || !song) return;
  const Tone = T();
  buildMaster(song);
  Tone.getTransport().bpm.value = song.bpm;
  const ids = new Set(song.tracks.map(t => t.id));
  for (const [id, c] of E.chains) if (!ids.has(id)) { dropChain(c); E.chains.delete(id); }
  const solo = song.tracks.some(t => t.solo);
  for (const t of song.tracks) {
    let c = E.chains.get(t.id);
    if (!c || c.sig !== sigOf(t)) { if (c) dropChain(c); c = buildChain(t, E.master.ch); E.chains.set(t.id, c); c.inst.ready.catch(e => emit('error', e.message)); }
    c.ch.volume.value = t.vol; c.ch.pan.value = t.pan; c.ch.mute = !!t.mute || (solo && !t.solo);
    t.fx.filter(f => f.on).forEach((f, i) => { const n = c.fx[i]; if (n) for (const [k, v] of Object.entries(f.p || {})) setFx(n, k, v); });
  }
}
function dropChain(c) { try { c.inst.releaseAll(); } catch {} setTimeout(() => { try { c.inst.dispose(); } catch {} for (const n of c.nodes) try { n.dispose(); } catch {} }, 600); }
export const meterOf = id => { const c = id === 'master' ? E.master : E.chains.get(id); if (!c) return -Infinity; const v = c.meter.getValue(); return Array.isArray(v) ? Math.max(...v) : v; };
export const chainOf = id => E.chains.get(id);
export function setTone(trackId, x) { const c = E.chains.get(trackId); if (c) c.tone.frequency.rampTo(80 * Math.pow(250, Math.max(0, Math.min(1, x))), 0.03); }

// ---------------------------------------------------------------- clock
const spb = () => 60 / E.song.bpm;
const now = () => T().immediate();
export const beatAt = time => (time - E.t0) / spb();
export const beatNow = () => (E.playing ? beatAt(now()) : E.from);
export const loopBeats = () => S.sectionBeats(E.song, S.curSection(E.song));
// where the playhead is: in loop mode wrapped into the loop
export function position() {
  if (!E.song) return { beat: 0, bar: 1, beatInBar: 1 };
  const b = beatNow(), lb = E.loop ? ((b % loopBeats()) + loopBeats()) % loopBeats() : b;
  return { beat: b, pos: lb, bar: Math.floor(lb / E.song.sig) + 1, beatInBar: Math.floor(lb % E.song.sig) + 1, counting: E.playing && b < 0 && E.countBeats > 0, playing: E.playing, recording: E.recording };
}
export function setBpm(bpm) {
  bpm = Math.max(30, Math.min(300, +bpm));
  if (E.playing) { const b = beatNow(); E.song.bpm = bpm; E.t0 = now() - b * spb(); E.scheduled = b; }
  else E.song.bpm = bpm;
  if (E.started) T().getTransport().bpm.value = bpm;
  emit('bpm', bpm);
}
let taps = [];
export function tap() {
  const t = performance.now(); taps = taps.filter(x => t - x < 2500); taps.push(t);
  if (taps.length >= 3) { const d = (taps[taps.length - 1] - taps[0]) / (taps.length - 1); setBpm(Math.round(60000 / d)); }
  return E.song.bpm;
}

// play from a beat. loop: the current section repeats; else the arrangement (to `until` beats)
export async function play({ from = null, loop = E.loop, until = Infinity, countIn = 0, follow = false } = {}) {
  await start();
  if (E.playing) stop(true);
  if (follow && !E.follow) E.loopBefore = E.loop;
  E.loop = loop; E.until = until; E.follow = follow;
  E.countBeats = countIn * E.song.sig;
  const b = (from ?? (loop ? 0 : E.from)) - E.countBeats;
  E.t0 = now() + 0.05 - b * spb(); E.scheduled = b; E.playing = true; E.lastPass = -1;
  E.timer = setInterval(pump, 20); pump();
  emit('play', true);
}
export function stop(quiet = false) {
  if (!E.playing && !quiet) return;
  clearInterval(E.timer); E.timer = null; E.playing = false; E.from = 0;
  for (const c of E.chains.values()) try { c.inst.releaseAll(); } catch {}
  if (E.recording) finishRecording();
  if (E.follow && E.loopBefore != null) { E.loop = E.loopBefore; E.loopBefore = null; }
  E.follow = false;
  if (!quiet) emit('play', false);
}
export const toggle = () => (E.playing ? stop() : play());
function pump() {
  if (!E.playing || !E.song) return;
  const ahead = beatAt(now() + 0.12), from = E.scheduled, to = ahead;
  if (to <= from) return;
  const s = E.song;
  // count-in clicks and the metronome
  for (let b = Math.ceil(from); b < to; b++) {
    if (b < 0 || E.metro) { const bar = ((b % s.sig) + s.sig) % s.sig === 0; E.click?.triggerAttackRelease(bar ? 1760 : 1100, 0.03, E.t0 + b * spb(), b < 0 ? 1 : 0.6); }
  }
  if (to > 0) {
    for (const e of S.eventsIn(s, Math.max(0, from), to, { loop: E.loop, until: E.until })) {
      const c = E.chains.get(e.track.id); if (!c) continue;
      // notes being recorded in this pass are not played back over themselves
      c.inst.hit?.(e.n, e.v, E.t0 + e.at * spb(), Math.max(0.03, e.d * spb()));
      emit('hit', { track: e.track.id, n: e.n, v: e.v, at: E.t0 + e.at * spb() });
    }
  }
  if (!E.loop && to >= Math.min(E.until, s.fill ? Infinity : S.songBeats(s)) && !E.follow) { stop(); return; }
  // a new loop pass starts a new layer (take) while recording
  if (E.recording && E.loop && to > 0) { const pass = Math.floor(Math.max(0, from) / loopBeats()); if (pass !== E.lastPass) { if (E.lastPass >= 0 && E.passNotes) E.take++; E.passNotes = 0; E.lastPass = pass; } }
  arpTick(from, to);
  E.scheduled = to;
}

// ---------------------------------------------------------------- live playing
export const selTrack = () => E.song?.tracks.find(t => t.id === E.song.sel) || E.song?.tracks.find(t => t.kind !== 'drum') || E.song?.tracks[0];
export const drumTrack = () => (selTrack()?.kind === 'drum' ? selTrack() : E.song?.tracks.find(t => t.kind === 'drum'));
function sound(track, n, v, time = now()) { const c = E.chains.get(track.id); if (!c) return; c.inst.on(n, v, time); emit('note', { track: track.id, n, v, on: true }); }
function silence(track, n, time = now()) { const c = E.chains.get(track.id); if (!c) return; c.inst.off(n, time); emit('note', { track: track.id, n, on: false }); }
const vel = v => (E.helpers.fixedVel ? E.helpers.fixedVel : v);
// what one key press turns into (scale lock, octave, transpose, chord)
export function expand(n) {
  const h = E.helpers, s = E.song;
  let m = n + h.octave * 12 + h.transpose;
  if (h.scaleLock) m = S.snapToScale(m, s.key, s.scale);
  return S.chordNotes(m, h.chord, s.key, s.scale).map(x => Math.max(0, Math.min(127, x)));
}
// a key on the keyboard (or the on-screen keys): plays the selected track, records if recording
// before the first sound the audio has to start; a key released meanwhile must not get stuck
const downs = new Set();
function whenStarted(n, fn) { downs.add(n); (E.startQ ||= start()).then(() => { if (downs.has(n)) fn(); }).catch(e => emit('error', e.message)); }
export function press(n, v = 0.8, track = selTrack()) {
  if (!E.started) return whenStarted('k' + n, () => press(n, v, track));
  if (!track) return;
  if (track.kind === 'drum') return pad((((n - S.PAD_BASE) % 16) + 16) % 16, v, track);
  if (E.helpers.arp !== 'off') { if (!E.arpHeld.includes(n)) E.arpHeld.push(n); E.arpTrack = track; if (!E.playing && !E.arpTimer) startFreeArp(); return; }
  const notes = expand(n), t = now();
  E.held.set(n, { notes, v: vel(v), t, track });
  E.sustained.delete(n);
  for (const m of notes) sound(track, m, vel(v), t);
}
export function release(n) {
  downs.delete('k' + n);
  if (E.helpers.arp !== 'off' || E.arpHeld.includes(n)) { E.arpHeld = E.arpHeld.filter(x => x !== n); if (!E.arpHeld.length) stopFreeArp(); return; }
  const h = E.held.get(n); if (!h) return;
  if (E.sustain) { E.sustained.add(n); return; }
  E.held.delete(n);
  const t = now();
  for (const m of h.notes) { silence(h.track, m, t); remember(h.track, m, h.v, h.t, t); }
}
export function setSustain(on) {
  E.sustain = !!on;
  if (!on) { for (const n of [...E.sustained]) { E.sustained.delete(n); const h = E.held.get(n); if (h) { E.held.delete(n); const t = now(); for (const m of h.notes) { silence(h.track, m, t); remember(h.track, m, h.v, h.t, t); } } } }
}
// a pad: a drum sound on the drum track (note repeat retriggers while held)
export function pad(i, v = 0.9, track = drumTrack()) {
  if (!E.started) return whenStarted('p' + i, () => pad(i, v, track));
  if (!track) return;
  const n = S.PAD_BASE + i, t = now(), c = E.chains.get(track.id);
  c?.inst.on(n, vel(v), t); emit('note', { track: track.id, n, v, on: true, pad: i });
  remember(track, n, vel(v), t, t + 0.1);
  if (E.helpers.repeat) { E.repeatPads.set(i, { v, track, next: t + E.helpers.repeat * spb() }); if (!E.arpTimer) startFreeArp(); }
}
export function padUp(i) { downs.delete('p' + i); E.repeatPads.delete(i); if (!E.repeatPads.size && !E.arpHeld.length) stopFreeArp(); }
export function bend(semis) { const c = E.chains.get(selTrack()?.id); c?.inst.bend(semis); }
export function mod(x) { const t = selTrack(); if (t) setTone(t.id, 1 - x * 0.85); }
export function panic() { E.held.clear(); E.sustained.clear(); E.arpHeld = []; E.repeatPads.clear(); stopFreeArp(); for (const c of E.chains.values()) try { c.inst.releaseAll(); } catch {} emit('panic'); }

// arpeggiator and note repeat: locked to the song clock while playing, to the tempo when stopped
function arpTick(from, to) {
  const h = E.helpers, rate = h.arp !== 'off' ? h.arpRate : 0;
  if (rate && E.arpHeld.length && E.arpTrack) for (let b = Math.ceil(from / rate) * rate; b < to; b += rate) arpFire(E.t0 + b * spb(), rate * spb());
  for (const [i, r] of E.repeatPads) for (let b = Math.ceil(from / h.repeat) * h.repeat; b < to; b += h.repeat) { const t = E.t0 + b * spb(); if (t <= now()) continue; E.chains.get(r.track.id)?.inst.on(S.PAD_BASE + i, r.v * 0.85, t); remember(r.track, S.PAD_BASE + i, r.v * 0.85, t, t + 0.08); }
}
function arpFire(time, len) {
  const notes = S.arpStep(E.arpHeld, E.helpers.arp, E.arpIndex++, E.helpers.arpOct, E.arpIndex);
  for (const n of notes) for (const m of expand(n)) { const c = E.chains.get(E.arpTrack.id); c?.inst.hit?.(m, 0.75, time, len * 0.9); remember(E.arpTrack, m, 0.75, time, time + len * 0.9); emit('note', { track: E.arpTrack.id, n: m, v: 0.75, on: true, arp: true }); }
}
function startFreeArp() {
  if (E.playing) return;
  E.arpNext = now() + 0.02;
  E.arpTimer = setInterval(() => {
    if (E.playing) return;
    const h = E.helpers;
    while (E.arpNext < now() + 0.1) {
      if (h.arp !== 'off' && E.arpHeld.length && E.arpTrack) arpFire(E.arpNext, h.arpRate * spb());
      for (const [i, r] of E.repeatPads) { E.chains.get(r.track.id)?.inst.on(S.PAD_BASE + i, r.v * 0.85, E.arpNext); remember(r.track, S.PAD_BASE + i, r.v * 0.85, E.arpNext, E.arpNext + 0.08); }
      E.arpNext += (h.arp !== 'off' && E.arpHeld.length ? h.arpRate : h.repeat || 0.25) * spb();
    }
  }, 20);
}
function stopFreeArp() { clearInterval(E.arpTimer); E.arpTimer = null; }

// ---------------------------------------------------------------- recording, layers and capture
// every note played is remembered for Capture; while recording it also lands in the clip
function remember(track, n, v, t1, t2) {
  E.history.push({ track: track.id, n, v, t1, t2 }); if (E.history.length > 600) E.history.splice(0, 100);
  if (!E.recording || !E.playing || !E.rec) return;
  const b1 = beatAt(t1), b2 = beatAt(t2);
  if (b1 < -0.25) return;                      // during the count-in
  if (track.id !== E.rec.track && !E.rec.any) return;
  writeNote(track, n, v, Math.max(0, b1), Math.max(0.05, b2 - b1));
}
function writeNote(track, n, v, b, d) {
  const s = E.song, h = E.helpers;
  let sec, t;
  if (E.loop) { sec = S.curSection(s); t = b % loopBeats(); }
  else { const p = S.layout(s).find(x => b >= x.start && b < x.start + x.beats) || S.layout(s).at(-1); sec = p.sec; t = b - p.start; }
  if (h.quantOn && h.quant) { const q = Math.round(t / h.quant) * h.quant; t = q >= S.sectionBeats(s, sec) ? 0 : q; }
  const c = S.clipOf(track, sec, true);
  c.notes.push({ t: +t.toFixed(4), d: +d.toFixed(4), n, v: +v.toFixed(3), take: E.take });
  E.passNotes++;
  emit('recorded', { track: track.id, sec: sec.id });
}
export async function record(on = !E.recording, { countIn = E.preRoll } = {}) {
  if (!on) { E.recording = false; finishRecording(); emit('record', false); return false; }
  const t = selTrack(); if (!t) throw Error('Add a track first');
  // whatever you play lands on the track that played it (pads on the drums, keys on the selected track)
  E.rec = { track: t.id, any: true };
  const secId = S.curSection(E.song).id;
  E.take = Math.max(0, ...E.song.tracks.flatMap(x => x.clips[secId]?.notes.map(n => (n.take ?? 0) + 1) || []));
  if (E.helpers.mode === 'replace' && E.loop) { const c = S.clipOf(t, S.curSection(E.song)); if (c) c.notes = []; }
  E.recording = true;
  if (!E.playing) await play({ loop: E.loop, countIn });
  emit('record', true);
  return true;
}
function finishRecording() { E.recording = false; E.rec = null; emit('recorded', {}); }
// take away the last layer recorded into this clip
// take away the last layer recorded into this loop (on whichever tracks it landed)
export function undoTake(track = null, sec = S.curSection(E.song)) {
  const clips = (track ? [track] : E.song.tracks).map(t => S.clipOf(t, sec)).filter(c => c?.notes.length);
  if (!clips.length) return 0;
  const last = Math.max(...clips.flatMap(c => c.notes.map(n => n.take ?? 0)));
  let removed = 0;
  for (const c of clips) { const b = c.notes.length; c.notes = c.notes.filter(n => (n.take ?? 0) !== last); removed += b - c.notes.length; }
  return removed;
}
// Capture: keep what you just played even though Record was off
export function capture(track = selTrack()) {
  const s = E.song, sec = S.curSection(s), lb = loopBeats(), hist = E.history.filter(h => h.track === track?.id);
  if (!track || !hist.length) return 0;
  let notes;
  if (E.playing) {
    const fromB = beatNow() - lb;
    notes = hist.filter(h => beatAt(h.t1) >= fromB).map(h => ({ t: ((beatAt(h.t1) % lb) + lb) % lb, d: Math.max(0.05, (h.t2 - h.t1) / spb()), n: h.n, v: h.v }));
  } else {
    // the last phrase: everything after the last pause longer than 2.5 seconds
    let i = hist.length - 1; while (i > 0 && hist[i].t1 - hist[i - 1].t1 < 2.5) i--;
    const phrase = hist.slice(i), t0 = Math.floor(phrase[0].t1 / spb() * 4) / 4 * spb();
    notes = phrase.map(h => ({ t: (h.t1 - t0) / spb(), d: Math.max(0.05, (h.t2 - h.t1) / spb()), n: h.n, v: h.v }));
    const span = Math.max(...notes.map(n => n.t + n.d));
    while (S.sectionBeats(s, sec) < span && sec.bars < 32) sec.bars *= 2;
  }
  if (E.helpers.quantOn && E.helpers.quant) S.quantize(notes, E.helpers.quant, 1);
  const c = S.clipOf(track, sec, true), take = Math.max(0, ...c.notes.map(n => (n.take ?? 0) + 1));
  for (const n of notes) c.notes.push({ ...n, t: +(n.t % S.sectionBeats(s, sec)).toFixed(4), d: +n.d.toFixed(4), take });
  return notes.length;
}

// ---------------------------------------------------------------- the animation timeline drives the song
export function followStart(sceneSeconds, sceneLength) {
  if (!E.song || !S.hasNotes(E.song)) return;
  const b = S.secToBeat(E.song, sceneSeconds);
  play({ from: b, loop: false, until: S.secToBeat(E.song, sceneLength), follow: true }).catch(() => {});
}
export function followStop() { if (E.follow) stop(); }

// ---------------------------------------------------------------- bounce: the song (or one track) to audio, faster than real time
export async function bounce({ seconds, only = null, sampleRate = 48000, onProgress } = {}) {
  await start();
  const Tone = T(), s = E.song;
  if (!S.hasNotes(s)) throw Error('There are no notes to bounce yet');
  const len = seconds ?? Math.max(1, S.songSeconds(s) + s.offset + 2);
  const untilBeat = S.secToBeat(s, len);
  const buf = await Tone.Offline(async () => {
    const master = new Tone.Channel(s.master.vol, 0), mfx = s.master.fx.filter(f => f.on).map(makeFx).filter(Boolean);
    master.chain(...mfx, Tone.getDestination());
    const solo = s.tracks.some(t => t.solo), chains = {};
    for (const t of s.tracks) {
      if (only ? t.id !== only : (t.mute || (solo && !t.solo))) continue;
      chains[t.id] = buildChain(t, master);
    }
    await Promise.all(Object.values(chains).map(c => c.inst.ready));
    await Tone.loaded();
    for (const c of Object.values(chains)) for (const n of c.fx) if (n.ready) await n.ready;
    for (const e of S.eventsIn({ ...s, tracks: s.tracks.map(t => (only ? { ...t, mute: t.id !== only, solo: false } : t)) }, 0, untilBeat, { loop: false, until: untilBeat })) {
      const c = chains[e.track.id]; if (!c) continue;
      c.inst.hit?.(e.n, e.v, s.offset + e.at * spb(), Math.max(0.03, e.d * spb()));
    }
  }, len, 2, sampleRate);
  onProgress?.(1);
  const ab = buf.get();
  return { channels: [ab.getChannelData(0), ab.numberOfChannels > 1 ? ab.getChannelData(1) : ab.getChannelData(0)], sr: ab.sampleRate, seconds: len };
}
export function wavBase64(channels, sr) {
  const n = channels[0].length, ch = channels.length, data = new DataView(new ArrayBuffer(44 + n * ch * 2));
  const w = (o, s) => { for (let i = 0; i < s.length; i++) data.setUint8(o + i, s.charCodeAt(i)); };
  w(0, 'RIFF'); data.setUint32(4, 36 + n * ch * 2, true); w(8, 'WAVE'); w(12, 'fmt '); data.setUint32(16, 16, true); data.setUint16(20, 1, true); data.setUint16(22, ch, true);
  data.setUint32(24, sr, true); data.setUint32(28, sr * ch * 2, true); data.setUint16(32, ch * 2, true); data.setUint16(34, 16, true); w(36, 'data'); data.setUint32(40, n * ch * 2, true);
  let o = 44; for (let i = 0; i < n; i++) for (let c = 0; c < ch; c++) { const v = Math.max(-1, Math.min(1, channels[c][i])); data.setInt16(o, v < 0 ? v * 0x8000 : v * 0x7fff, true); o += 2; }
  const bytes = new Uint8Array(data.buffer); let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}
export { FX };
