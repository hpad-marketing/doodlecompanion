// MIDI input for the Music workspace: finds the MiniLab 3 (or any USB MIDI keyboard) with Web MIDI,
// no Arturia software or driver needed, and routes every key, pad, knob, fader, strip and pedal.
// Everything can be re-mapped by the user: Learn, then move or press the control.
import * as E from './engine.js';
const KEY = 'ds3d.music.map.v1';

// MiniLab 3 factory settings (Arturia mode). If a knob or fader does something else on your unit,
// Music › Controller › "Set up my MiniLab" learns the real numbers in 20 seconds.
export const MINILAB = { knobs: [74, 71, 76, 77, 93, 18, 19, 16], faders: [82, 83, 85, 17], padCh: 9, padBase: 36, keysCh: 0 };
export const DEFAULT_KNOBS = ['trk:tone', 'trk:pan', 'trk:fx:reverb', 'trk:fx:delay', 'song:swing', 'master:vol', 'ctl:cam.dist', 'ctl:headYaw'];
export const DEFAULT_FADERS = ['mix:0', 'mix:1', 'mix:2', 'mix:3'];
export const PAD_MODES = { drums: 'Drums', actions: 'App actions', faces: 'Faces (puppet)', clips: 'Launch loops' };
export const FACE_SLOTS = [0, 1, 3, 4, 6, 9, 8, 11, 12, 15, 18, 2, 10, 14, 19, 7];
export const DEFAULT_PAD_ACTIONS = ['music.play', 'music.record', 'music.capture', 'music.undoTake', 'music.newLayer', 'music.metronome', 'anim.play', 'anim.key',
  'anim.prevShot', 'anim.nextShot', 'anim.undo', 'anim.redo', 'music.prevTrack', 'music.nextTrack', 'music.panic', 'music.tap'];

const M = {
  access: null, inputs: [], status: 'off', error: '', learn: null, ctx: null, last: null,
  map: { knobs: [...MINILAB.knobs], faders: [...MINILAB.faders], padCh: MINILAB.padCh, padBase: MINILAB.padBase, rules: [], padMode: 'drums', padActions: [...DEFAULT_PAD_ACTIONS], faceSlots: [...FACE_SLOTS], split: null, knobTargets: [...DEFAULT_KNOBS], faderTargets: [...DEFAULT_FADERS], bendRange: 2, puppet: false, puppetKeys: true },
  values: {}, listeners: new Set(),
};
try { Object.assign(M.map, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch {}
export const midi = M;
export const saveMap = () => { try { localStorage.setItem(KEY, JSON.stringify(M.map)); } catch {} emit('map'); };
const emit = (what, x) => { for (const f of M.listeners) try { f(what, x); } catch {} };
export const onMidi = f => (M.listeners.add(f), () => M.listeners.delete(f));
export function resetMap() { localStorage.removeItem(KEY); M.map = { ...M.map, knobs: [...MINILAB.knobs], faders: [...MINILAB.faders], padCh: 9, padBase: 36, rules: [], padActions: [...DEFAULT_PAD_ACTIONS], faceSlots: [...FACE_SLOTS], split: null, knobTargets: [...DEFAULT_KNOBS], faderTargets: [...DEFAULT_FADERS] }; saveMap(); }

export async function connect(ctx) {
  M.ctx = ctx;
  if (M.access) return refresh();
  if (!navigator.requestMIDIAccess) { M.status = 'unsupported'; M.error = 'This window has no Web MIDI'; emit('status'); return; }
  try {
    M.access = await navigator.requestMIDIAccess({ sysex: false });
    M.access.onstatechange = () => refresh();
    refresh();
  } catch (e) { M.status = 'blocked'; M.error = e.message; emit('status'); }
}
function refresh() {
  M.inputs = [...M.access.inputs.values()];
  for (const i of M.inputs) i.onmidimessage = ev => handle([...ev.data], i.name);
  const ml = M.inputs.find(i => /minilab/i.test(i.name));
  M.status = M.inputs.length ? 'on' : 'none';
  M.device = ml?.name || M.inputs[0]?.name || null;
  M.isMiniLab = !!ml;
  emit('status');
}
export const statusText = () => ({ on: M.isMiniLab ? 'MiniLab 3 connected' : `${M.device} connected`, none: 'No MIDI keyboard found. Plug in the MiniLab, and close Arturia apps or any DAW (Windows lets one app use it at a time).', blocked: 'MIDI was blocked: ' + M.error, unsupported: 'MIDI is not available here', off: 'MIDI starting…' })[M.status];

// test hook and on-screen controls: feed a raw MIDI message
export const inject = (bytes, from = 'screen') => handle(bytes, from);
export function learn(target, then) { M.learn = target ? { target, then } : null; emit('learn', target); }

const srcOf = (type, ch, num) => `${type}:${ch}:${num}`;
function handle([st, d1 = 0, d2 = 0], from) {
  const type = st & 0xf0, ch = st & 0x0f;
  let kind, src, value;
  if (type === 0x90 && d2 > 0) { kind = 'noteon'; src = srcOf('note', ch, d1); value = d2 / 127; }
  else if (type === 0x80 || (type === 0x90 && d2 === 0)) { kind = 'noteoff'; src = srcOf('note', ch, d1); value = 0; }
  else if (type === 0xb0) { kind = 'cc'; src = srcOf('cc', ch, d1); value = d2 / 127; }
  else if (type === 0xe0) { kind = 'bend'; src = srcOf('pb', ch, 0); value = ((d2 << 7) | d1) / 16383; }
  else if (type === 0xd0) { kind = 'pressure'; src = srcOf('at', ch, 0); value = d1 / 127; }
  else return;
  M.last = { kind, src, value, ch, num: d1, from, at: performance.now() };
  emit('activity', M.last);
  // Learn: the next control moved or pressed takes the target
  if (M.learn && kind !== 'noteoff') {
    const { target, then } = M.learn; M.learn = null;
    if (target.startsWith('knob:')) M.map.knobs[+target.slice(5)] = d1;
    else if (target.startsWith('fader:')) M.map.faders[+target.slice(6)] = d1;
    else if (target === 'pads') { M.map.padCh = ch; M.map.padBase = d1; }
    else { M.map.rules = M.map.rules.filter(r => r.src !== src && r.target !== target); M.map.rules.push({ src, target }); }
    saveMap(); emit('learned', { src, target }); then?.({ src, target });
    return;
  }
  const rule = M.map.rules.find(r => r.src === src);
  if (rule) return applyTarget(rule.target, kind, value, d1, rule);
  if (kind === 'cc') {
    const k = M.map.knobs.indexOf(d1), f = M.map.faders.indexOf(d1);
    if (d1 === 64) return E.setSustain(d2 >= 64);
    if (d1 === 1) { E.mod(value); if (M.map.puppet) M.ctx?.puppet?.('mod', value); return; }
    if (k >= 0 && ch !== M.map.padCh) return applyTarget(M.map.knobTargets[k], kind, value, d1);
    if (f >= 0 && ch !== M.map.padCh) return applyTarget(M.map.faderTargets[f], kind, value, d1);
    M.values[src] = value; emit('unmapped', { src, value });
    return;
  }
  if (kind === 'bend') { const semis = (value - 0.5) * 2 * M.map.bendRange; E.bend(semis); if (M.map.puppet) M.ctx?.puppet?.('bend', value); return; }
  if (kind === 'pressure') { if (M.map.puppet) M.ctx?.puppet?.('pressure', value); return; }
  // pads (channel 10 by default) or keys
  const isPad = ch === M.map.padCh && d1 >= M.map.padBase && d1 < M.map.padBase + 16;
  if (isPad) return padEvent(d1 - M.map.padBase, kind === 'noteon', value);
  keyEvent(d1, kind === 'noteon', value);
}
function keyEvent(n, down, v) {
  const sp = M.map.split, s = E.engine.song;
  const track = sp && n < sp.at ? s?.tracks.find(t => t.id === sp.low) : null;
  if (down) E.press(n, v, track || undefined); else E.release(n);
  if (M.map.puppet && M.map.puppetKeys) M.ctx?.puppet?.('key', down ? v : 0, n);
}
function padEvent(i, down, v) {
  const mode = M.map.padMode;
  if (mode === 'drums') { if (down) E.pad(i, v); else E.padUp(i); }
  else if (!down) return;
  else if (mode === 'actions') M.ctx?.runAction(M.map.padActions[i]);
  else if (mode === 'faces') M.ctx?.puppet?.('face', M.map.faceSlots[i]);
  else if (mode === 'clips') M.ctx?.runAction('music.launch:' + i);
  emit('pad', { i, down, v });
}
// one control value 0..1 (or a press) applied to a target
export function applyTarget(target, kind, value, num) {
  if (!target) return;
  const ctx = M.ctx, s = E.engine.song;
  const press = kind === 'noteon' || (kind === 'cc' && value > 0.5 && (M.values[target] ?? 0) <= 0.5);
  M.values[target] = value;
  const [a, b, c] = target.split(':');
  if (a === 'act') { if (kind === 'noteon' || (kind === 'cc' && press)) ctx?.runAction(target.slice(4)); return; }
  if (a === 'pad') { if (kind === 'noteon') E.pad(+b, value); else if (kind === 'noteoff') E.padUp(+b); return; }
  if (a === 'note') { if (kind === 'noteon') E.press(+b, value); else if (kind === 'noteoff') E.release(+b); return; }
  if (kind === 'noteoff') return;
  if (a === 'ctl') return ctx?.setControl(target.slice(4), value);
  if (a === 'face') return ctx?.puppet?.('face', +b);
  ctx?.mixer?.(a, b, c, value);
}
// a readable name for any target, for the controller view
export function targetName(t, names = {}) {
  if (!t) return 'Nothing';
  const [a, b, c] = t.split(':');
  if (a === 'act') return names.action?.(t.slice(4)) || t.slice(4);
  if (a === 'ctl') return 'Bunny: ' + (names.control?.(t.slice(4)) || t.slice(4));
  if (a === 'pad') return 'Pad sound ' + (+b + 1);
  if (a === 'note') return 'Note ' + b;
  if (a === 'face') return 'Face ' + b;
  if (a === 'trk') return 'Selected track: ' + ({ tone: 'filter (brightness)', pan: 'left/right', vol: 'volume', fx: (c === 'reverb' ? 'reverb amount' : c === 'delay' ? 'echo amount' : c) })[b];
  if (a === 'mix') return `Track ${+b + 1} volume`;
  if (a === 'master') return 'Master volume';
  if (a === 'song') return ({ swing: 'Swing', bpm: 'Tempo' })[b] || b;
  return t;
}
