// The Music workspace: a small studio of its own. Transport, looper, loops grid (clip launcher),
// song order over the animation, piano roll and drum steps, mixer and effects, sound browser,
// the MiniLab 3 on screen with mapping, music-to-animation tools, and bounce/export.
import * as S from './song.js';
import * as E from './engine.js';
import * as I from './instruments.js';
import * as MI from './midi.js';
import * as MF from './midifile.js';
import * as AN from './anim.js';

let ctx = null, h = null, view = 'studio', sel = { track: null, sec: null }, noteSel = new Set(), drawLen = 1, snap = 0.25, catSel = 'keys', typing = false, full = false, rafOn = false;
const st = { top: 84, rows: 26, lastBounce: null, msg: '' };
export const VIEWS = [['studio', 'Studio'], ['mixer', 'Mixer & effects'], ['sounds', 'Sounds'], ['controller', 'MiniLab & mapping'], ['animate', 'Music → animation'], ['export', 'Bounce & files']];
const song = () => ctx.scene().song;
const colour = () => { const cs = getComputedStyle(document.body); return { bg: cs.getPropertyValue('--bg').trim() || '#E0A64B', fg: cs.getPropertyValue('--fg').trim() || '#1F1F1D' }; };

export function init(c) {
  ctx = c; h = c.h;
  E.init({ api: c.api });
  I.loadCatalog(c.api).then(() => { if (ctx.visible()) render(); }).catch(() => {});
  MI.connect(midiCtx());
  E.on((what, x) => {
    if (what === 'recorded' && view === 'studio') queueEditor();
    if (what === 'note') lightKey(x);
    if (what === 'error') ctx.toast(x, 5000);
    if (what === 'play' || what === 'record') { if (ctx.visible()) refreshTransport(); if (what === 'record' && !x) { touched(); ctx.changed(); if (ctx.visible()) render(); } }
  });
  MI.onMidi((what, x) => {
    if (what === 'status' && ctx.visible()) refreshTransport();
    if (what === 'activity') { activity(x); if (!E.engine.started) E.start().catch(() => {}); }
    if (what === 'learned') { ctx.toast(`Mapped ${srcName(x.src)} → ${MI.targetName(x.target, names())}`, 3500); if (ctx.visible()) render(); }
    if (what === 'unmapped' && view === 'controller') { const el = document.getElementById('mus-unmapped'); if (el) el.textContent = `Last unassigned control: ${srcName(x.src)}. Pick what it should do below, then press Learn and move it.`; }
  });
  addEventListener('keydown', typeKeys, true); addEventListener('keyup', typeKeys, true);
  addEventListener('keydown', e => { if (e.key === 'Escape' && full) setFull(false); });
}
// the scene changed (open, undo, new): bring the engine along
export function sceneChanged() {
  const sc = ctx.scene();
  if (sc.song) { S.migrateSong(sc.song); E.sync(sc.song); }
  else E.engine.song = null;
  if (ctx.visible()) render();
}
export const ensureSong = () => { const sc = ctx.scene(); if (!sc.song) { sc.song = S.newSong(); S.drumPattern(sc.song, sc.song.tracks[0], sc.song.sections[0], 'basic'); } S.migrateSong(sc.song); E.sync(sc.song); return sc.song; };
function editV(label, fn) { ctx.pushUndo(label); const r = fn(); touched(); ctx.changed(); E.sync(song()); return r; }
function edit(label, fn) { editV(label, fn); }
const quiet = () => { touched(); ctx.changedQuiet(); };
const names = () => ({ action: id => ACTIONS[id]?.[0] || id, control: id => ctx.controlLabel(id) });
const srcName = src => { const [t, ch, n] = src.split(':'); return t === 'note' ? (+ch === MI.midi.map.padCh ? `Pad ${n}` : `Key ${S.noteName(+n)}`) : t === 'cc' ? (MI.midi.map.knobs.indexOf(+n) >= 0 ? `Knob ${MI.midi.map.knobs.indexOf(+n) + 1}` : MI.midi.map.faders.indexOf(+n) >= 0 ? `Fader ${MI.midi.map.faders.indexOf(+n) + 1}` : `Control CC ${n}`) : t === 'pb' ? 'Pitch strip' : 'Key pressure'; };

// ---------------------------------------------------------------- actions any pad, key or knob can run
export const ACTIONS = {
  'music.play': ['Play / stop the loop', () => E.toggle()],
  'music.playSong': ['Play the song from the start', () => E.play({ loop: false, from: 0 })],
  'music.stop': ['Stop', () => E.stop()],
  'music.record': ['Record on / off', () => toggleRecord()],
  'music.capture': ['Capture what I just played', () => doCapture()],
  'music.undoTake': ['Undo the last layer', () => { const n = editV('Undo layer', () => E.undoTake()); ctx.toast(n ? `Removed the last layer (${n} notes)` : 'Nothing to undo in this loop'); queueEditor(); }],
  'music.newLayer': ['New layer (new track, same sound)', () => newLayer()],
  'music.nextSound': ['Next sound on this track', () => cycleSound(1)],
  'music.prevSound': ['Previous sound on this track', () => cycleSound(-1)],
  'music.metronome': ['Metronome on / off', () => { E.engine.metro = !E.engine.metro; refreshTransport(); }],
  'music.tap': ['Tap tempo', () => { E.tap(); quiet(); refreshTransport(); }],
  'music.nextTrack': ['Next track', () => stepTrack(1)],
  'music.prevTrack': ['Previous track', () => stepTrack(-1)],
  'music.octUp': ['Octave up', () => { E.engine.helpers.octave = Math.min(4, E.engine.helpers.octave + 1); E.saveHelpers(); rerenderLight(); }],
  'music.octDown': ['Octave down', () => { E.engine.helpers.octave = Math.max(-4, E.engine.helpers.octave - 1); E.saveHelpers(); rerenderLight(); }],
  'music.scaleLock': ['Scale lock on / off', () => { E.engine.helpers.scaleLock = !E.engine.helpers.scaleLock; E.saveHelpers(); rerenderLight(); }],
  'music.chord': ['Next chord mode', () => { const k = Object.keys(S.CHORDS); E.engine.helpers.chord = k[(k.indexOf(E.engine.helpers.chord) + 1) % k.length]; E.saveHelpers(); ctx.toast('Chords: ' + (S.CHORDS[E.engine.helpers.chord] || 'off')); rerenderLight(); }],
  'music.arp': ['Next arpeggiator mode', () => { const k = Object.keys(S.ARPS); E.engine.helpers.arp = k[(k.indexOf(E.engine.helpers.arp) + 1) % k.length]; E.saveHelpers(); ctx.toast('Arpeggiator: ' + S.ARPS[E.engine.helpers.arp]); rerenderLight(); }],
  'music.nextLoop': ['Next loop', () => launch(song().cur + 1)],
  'music.prevLoop': ['Previous loop', () => launch(song().cur - 1)],
  'music.panic': ['Stop stuck notes', () => E.panic()],
  'music.puppet': ['Puppet mode on / off', () => { MI.midi.map.puppet = !MI.midi.map.puppet; MI.saveMap(); ctx.toast(MI.midi.map.puppet ? 'Puppet mode: your playing moves the character' : 'Puppet mode off'); rerenderLight(); }],
  'anim.play': ['Animation: play / pause', () => ctx.anim('play')],
  'anim.key': ['Animation: key the pose', () => ctx.anim('key')],
  'anim.prevShot': ['Animation: previous shot', () => ctx.anim('prevShot')],
  'anim.nextShot': ['Animation: next shot', () => ctx.anim('nextShot')],
  'anim.prevFrame': ['Animation: previous frame', () => ctx.anim('prevFrame')],
  'anim.nextFrame': ['Animation: next frame', () => ctx.anim('nextFrame')],
  'anim.undo': ['Undo', () => ctx.anim('undo')],
  'anim.redo': ['Redo', () => ctx.anim('redo')],
};
export function runAction(id) {
  if (!id) return;
  if (id.startsWith('music.launch:')) return launch(+id.split(':')[1]);
  const a = ACTIONS[id]; if (!a) return;
  try { const r = a[1](); r?.catch?.(e => ctx.toast(e.message, 4000)); } catch (e) { ctx.toast(e.message, 4000); }
}
function midiCtx() {
  return {
    runAction, puppet: (kind, v, n) => AN.puppet(puppetCtx(), kind, v, n),
    setControl: (id, x) => ctx.setControl(id, x, { record: true }),
    mixer: (a, b, c, v) => {
      const s = song(); if (!s) return;
      if (a === 'trk') { const t = E.selTrack(); if (!t) return; if (b === 'tone') E.setTone(t.id, v); else if (b === 'pan') t.pan = +(v * 2 - 1).toFixed(2); else if (b === 'vol') t.vol = volFrom(v); else if (b === 'fx') { let f = t.fx.find(x => x.type === c); if (!f) { f = { type: c, on: true, p: {} }; t.fx.push(f); } f.p.wet = +v.toFixed(2); } }
      else if (a === 'mix') { const t = s.tracks[+b]; if (t) t.vol = volFrom(v); }
      else if (a === 'master') s.master.vol = volFrom(v);
      else if (a === 'song' && b === 'swing') s.swing = +(v * 0.6).toFixed(2);
      else if (a === 'song' && b === 'bpm') E.setBpm(Math.round(60 + v * 120));
      E.sync(s); quiet(); if (view === 'mixer') queueMixer();
    },
  };
}
const volFrom = v => (v < 0.02 ? -60 : +(Math.log10(v) * 30 + 6 * v).toFixed(1));
const puppetCtx = () => ({ setControl: (id, x, o) => ctx.setControl(id, x, o), puppetRecord: () => ctx.puppetRecord() });

async function toggleRecord() {
  ensureSong();
  if (!E.engine.recording) ctx.pushUndo('Record music');
  await E.record();
  refreshTransport();
}
function doCapture() {
  ensureSong();
  ctx.pushUndo('Capture');
  const n = E.capture(); touched(); ctx.changed();
  ctx.toast(n ? `Captured ${n} notes into ${S.curSection(song()).name}` : 'Play something first, then Capture keeps it');
  queueEditor(); if (ctx.visible()) render();
}
function newLayer() {
  const s = ensureSong(), cur = E.selTrack();
  edit('New layer', () => { const t = S.newTrack(`Layer ${s.tracks.length + 1}`, cur?.inst || 'gm:acoustic_grand_piano'); s.tracks.push(t); s.sel = t.id; });
  ctx.toast('New layer: play on top. Pads can change its sound (Next sound).'); if (ctx.visible()) render();
}
function cycleSound(d) {
  const t = E.selTrack(); if (!t) return;
  const list = I.catalog().filter(c => c.ready && (t.kind === 'drum' ? c.drum : !c.drum));
  const i = list.findIndex(c => c.id === t.inst), nx = list[(i + d + list.length) % list.length];
  edit('Change sound', () => { t.inst = nx.id; t.name = nx.name; });
  ctx.toast(`${t.name}`); if (ctx.visible()) render();
}
function stepTrack(d) { const s = ensureSong(), i = s.tracks.findIndex(t => t.id === E.selTrack()?.id); const t = s.tracks[(i + d + s.tracks.length) % s.tracks.length]; s.sel = t.id; sel.track = t.id; ctx.toast('Playing: ' + t.name); if (ctx.visible()) render(); }
function launch(i) { const s = ensureSong(); if (i < 0 || i >= s.sections.length) return; s.cur = i; sel.sec = s.sections[i].id; quiet(); if (!E.engine.playing) E.play({ loop: true }); ctx.toast('Loop: ' + s.sections[i].name); if (ctx.visible()) render(); }

// ---------------------------------------------------------------- the panel
export function panel(sub) {
  view = sub || view;
  ensureSong();
  const root = h('div', { class: 'mus', id: 'mus-root' });
  root.append(transportBar());
  const body = h('div', { class: 'mus-body' });
  root.append(body);
  ({ studio: studioView, mixer: mixerView, sounds: soundsView, controller: controllerView, animate: animateView, export: exportView })[view]?.(body);
  if (!rafOn) { rafOn = true; requestAnimationFrame(loop); }
  return root;
}
function render() { ctx.rebuild(); }
let lightQ = false;
function rerenderLight() { if (lightQ || !ctx.visible()) return; lightQ = true; requestAnimationFrame(() => { lightQ = false; render(); }); }

function sel2(label, value, opts, on, title) {
  const s = h('select', { 'aria-label': label, title: title || label }, ...opts.map(([v, n]) => h('option', { value: v }, n)));
  s.value = String(value); s.addEventListener('change', () => on(s.value)); return s;
}
const grp = (name, ...kids) => h('div', { class: 'mus-grp' }, h('span', { class: 'mus-grp-name' }, name), ...kids);
const btn = (label, title, fn, on) => h('button', { title, onclick: fn, 'aria-pressed': on == null ? null : String(!!on) }, label);

function transportBar() {
  const s = song(), x = E.engine, hp = x.helpers;
  const bpm = h('input', { type: 'number', min: 30, max: 300, step: 1, value: s.bpm, id: 'mus-bpm', title: 'Tempo in beats per minute', 'aria-label': 'Tempo' });
  bpm.addEventListener('change', () => { ctx.pushUndo('Tempo'); E.setBpm(+bpm.value); ctx.changed(); });
  const swing = h('input', { type: 'range', min: 0, max: 0.6, step: 0.02, value: s.swing, title: 'Swing: pushes every off-beat a little later for a bouncy groove', 'aria-label': 'Swing', style: 'width:80px' });
  swing.addEventListener('change', () => edit('Swing', () => { s.swing = +swing.value; }));
  return h('div', { class: 'mus-transport' },
    grp('Play', btn(x.playing ? '■ Stop' : '▶ Play', 'Play or stop (Space plays the animation; this plays the music)', () => runAction('music.play'), x.playing),
      h('button', { class: 'mus-rec' + (x.recording ? ' on' : ''), id: 'mus-rec', title: 'Record onto the selected track. In Loop mode the loop keeps going and every pass adds a layer.', onclick: () => runAction('music.record'), 'aria-pressed': String(x.recording) }, '● Rec'),
      btn('Capture', 'Keep what you just played, even with Record off', () => runAction('music.capture')),
      btn('Undo layer', 'Remove the last layer recorded into this loop', () => runAction('music.undoTake'))),
    grp('Mode', btn('Loop', 'Looper: the current loop repeats while you build it up', () => { x.loop = true; refreshTransport(); }, x.loop), btn('Song', 'Play the song order from the start, as it will sit under the animation', () => { x.loop = false; refreshTransport(); }, !x.loop),
      sel2('Record mode', hp.mode, [['overdub', 'Overdub (add)'], ['replace', 'Replace']], v => { hp.mode = v; E.saveHelpers(); }, 'Overdub adds to what is there; Replace clears this track\'s loop when you start recording')),
    grp('Click', btn('Metronome', 'Click on every beat', () => runAction('music.metronome'), x.metro),
      sel2('Count-in', x.preRoll, [[0, 'No count-in'], [1, 'Count-in 1 bar'], [2, 'Count-in 2 bars']], v => { x.preRoll = +v; })),
    grp('Tempo', bpm, btn('Tap', 'Tap 3 or more times to set the tempo', () => runAction('music.tap')),
      sel2('Time signature', s.sig, [[3, '3/4'], [4, '4/4'], [5, '5/4'], [6, '6/8'], [7, '7/8']], v => edit('Time signature', () => { s.sig = +v; }) || render())),
    grp('Key', sel2('Key', s.key, S.NOTE_NAMES.map((n, i) => [i, n]), v => edit('Key', () => { s.key = +v; }) || render()),
      sel2('Scale', s.scale, Object.entries(S.SCALE_NAMES), v => edit('Scale', () => { s.scale = v; }) || render())),
    grp('Swing', swing),
    h('span', { class: 'mus-pos', id: 'mus-pos' }, posText()),
    h('span', { class: 'mus-midi ' + (MI.midi.status === 'on' ? 'on' : ''), id: 'mus-midi', title: MI.statusText() || '' }, MI.midi.status === 'on' ? (MI.midi.isMiniLab ? 'MiniLab 3' : MI.midi.device) : 'No MIDI'),
    btn(full ? 'Exit big studio' : 'Big studio', 'Fill the window with the Music workspace (Esc to leave)', () => setFull(!full), full));
}
function posText() { const p = E.position(); return p.counting ? 'Count-in…' : `Bar ${p.bar} · beat ${p.beatInBar}${E.engine.recording ? ' · REC' : ''}`; }
function refreshTransport() { const old = document.querySelector('.mus-transport'); if (old) old.replaceWith(transportBar()); }
export function setFull(on) { full = on; document.body.classList.toggle('music-full', on); refreshTransport(); ctx.resized?.(); }
function loop() {
  if (!ctx.visible()) { rafOn = false; return; }
  const p = document.getElementById('mus-pos'); if (p) p.textContent = posText();
  const r = document.getElementById('mus-rec'); if (r) r.classList.toggle('blink', E.engine.recording && E.position().counting);
  for (const el of document.querySelectorAll('[data-meter]')) { const db = E.meterOf(el.dataset.meter); el.style.width = Math.max(0, Math.min(100, (db + 60) / 60 * 100)) + '%'; }
  const ph = document.getElementById('mus-playhead');
  if (ph) { const pos = E.position(), s = song(), sec = s.sections.find(x => x.id === sel.sec); const on = E.engine.playing && sec && (E.engine.loop ? sec === S.curSection(s) : true); ph.style.display = on ? 'block' : 'none'; if (on) { const beats = S.sectionBeats(s, sec), b = E.engine.loop ? pos.pos : pos.beat - (S.layout(s).find(x => x.sec === sec)?.start ?? 0); ph.style.left = `calc(${ph.dataset.left}px + (100% - ${ph.dataset.left}px) * ${Math.max(0, Math.min(1, b / beats))})`; } }
  requestAnimationFrame(loop);
}

// ---------------------------------------------------------------- Studio: helpers, loops grid, song order, editor, keyboard
function studioView(body) {
  const s = song(), hp = E.engine.helpers;
  if (s.sel && s.tracks.find(t => t.id === s.sel)) sel.track = s.sel;
  if (!s.tracks.find(t => t.id === sel.track)) sel.track = s.tracks[0]?.id;
  if (!s.sections.find(x => x.id === sel.sec)) sel.sec = S.curSection(s).id;
  s.sel = sel.track;
  body.append(h('div', { class: 'mus-row' },
    grp('Octave', btn('−', 'Octave down', () => runAction('music.octDown')), h('b', {}, (hp.octave > 0 ? '+' : '') + hp.octave), btn('+', 'Octave up', () => runAction('music.octUp'))),
    grp('Help me play', btn('Scale lock', `Every key plays a note of ${S.NOTE_NAMES[s.key]} ${S.SCALE_NAMES[s.scale]}, so nothing sounds wrong`, () => runAction('music.scaleLock'), hp.scaleLock),
      sel2('Chords', hp.chord, Object.entries(S.CHORDS).map(([k, v]) => [k, v || 'Chords off']), v => { hp.chord = v; E.saveHelpers(); }, 'One finger plays a whole chord'),
      sel2('Arpeggiator', hp.arp, Object.entries(S.ARPS).map(([k, v]) => [k, k === 'off' ? 'Arp off' : 'Arp: ' + v]), v => { hp.arp = v; E.saveHelpers(); }, 'Hold a chord and it plays as a pattern in time'),
      sel2('Arp speed', hp.arpRate, [[1, '1/4'], [0.5, '1/8'], [0.25, '1/16'], [1 / 3, '1/8 triplet']], v => { hp.arpRate = +v; E.saveHelpers(); }),
      sel2('Arp octaves', hp.arpOct, [[1, '1 oct'], [2, '2 oct'], [3, '3 oct']], v => { hp.arpOct = +v; E.saveHelpers(); }),
      sel2('Note repeat', hp.repeat, [[0, 'Repeat off'], [1, 'Repeat 1/4'], [0.5, 'Repeat 1/8'], [0.25, 'Repeat 1/16'], [0.125, 'Repeat 1/32']], v => { hp.repeat = +v; E.saveHelpers(); }, 'Hold a pad and it repeats in time (great for hi-hat rolls)'),
      btn('Even velocity', 'Every note plays at the same loudness', () => { hp.fixedVel = hp.fixedVel ? 0 : 0.85; E.saveHelpers(); render(); }, !!hp.fixedVel)),
    grp('Recording', btn('Snap timing', 'Pull recorded notes onto the grid', () => { hp.quantOn = !hp.quantOn; E.saveHelpers(); render(); }, hp.quantOn),
      sel2('Snap grid', hp.quant, [[1, '1/4'], [0.5, '1/8'], [0.25, '1/16'], [0.125, '1/32'], [1 / 3, '1/8 triplet']], v => { hp.quant = +v; E.saveHelpers(); }),
      btn('Type to play', 'Play notes with the computer keyboard too: A W S E D F T G Y H U J K (Z X change octave)', () => { typing = !typing; render(); }, typing))));
  body.append(loopsGrid());
  body.append(songOrder());
  body.append(editor());
  body.append(keyboardWidget());
}
function miniClip(t, sec, w = 120, hgt = 30) {
  const c = h('canvas', { width: w, height: hgt, class: 'mus-mini' }), g = c.getContext('2d'), clip = t.clips[sec.id], { fg } = colour();
  if (clip?.notes.length) {
    const beats = S.sectionBeats(song(), sec), ns = clip.notes.map(n => n.n), lo = Math.min(...ns), hi = Math.max(...ns) + 1;
    g.fillStyle = fg;
    for (const n of clip.notes) g.fillRect(n.t / beats * w, hgt - 3 - (n.n - lo + 1) / (hi - lo + 1) * (hgt - 6), Math.max(2, n.d / beats * w), 3);
  }
  return c;
}
function loopsGrid() {
  const s = song();
  const head = h('div', { class: 'mus-grid-row head' }, h('div', { class: 'mus-tname' }, h('b', {}, 'Tracks'), h('span', { class: 'hint' }, ' · loops →')),
    ...s.sections.map((sec, i) => {
      const bars = sel2('Bars', sec.bars, [1, 2, 4, 8, 16, 32].map(b => [b, b + (b > 1 ? ' bars' : ' bar')]), v => edit('Loop length', () => { sec.bars = +v; }) || render(), 'Loop length');
      return h('div', { class: 'mus-sec' + (i === s.cur ? ' cur' : ''), title: 'Double-click the name to rename' },
        h('div', { class: 'row' }, btn(i === s.cur && E.engine.playing ? '■' : '▶', 'Make this the loop and play it (Loop mode)', () => (i === s.cur && E.engine.playing ? E.stop() : launch(i))),
          h('b', { ondblclick: () => { const n = prompt('Loop name', sec.name); if (n) edit('Rename loop', () => { sec.name = n; }) || render(); } }, sec.name)),
        h('div', { class: 'row' }, bars, btn('×2', 'Double the loop, copying what is in it', () => edit('Double loop', () => S.double(s, sec)) || render()),
          btn('Copy', 'Duplicate this loop as a new one (to make a variation)', () => edit('Duplicate loop', () => { const nx = { id: S.uid('s'), name: sec.name + ' 2', bars: sec.bars }; s.sections.splice(i + 1, 0, nx); for (const t of s.tracks) if (t.clips[sec.id]) t.clips[nx.id] = JSON.parse(JSON.stringify(t.clips[sec.id])); }) || render()),
          s.sections.length > 1 ? btn('×', 'Delete this loop', () => { if (confirm(`Delete ${sec.name}?`)) edit('Delete loop', () => { s.sections.splice(i, 1); for (const t of s.tracks) delete t.clips[sec.id]; s.arr = s.arr.filter(x => x !== sec.id); s.cur = Math.min(s.cur, s.sections.length - 1); }) || render(); }) : null));
    }),
    h('div', { class: 'mus-sec add' }, btn('+ Loop', 'Add an empty loop (verse, chorus, bridge…)', () => edit('Add loop', () => { s.sections.push({ id: S.uid('s'), name: 'Loop ' + String.fromCharCode(65 + s.sections.length), bars: S.curSection(s).bars }); }) || render())));
  const rows = s.tracks.map((t, ti) => {
    const vol = h('input', { type: 'range', min: -40, max: 6, step: 0.5, value: t.vol, title: `Volume ${t.vol} dB`, 'aria-label': t.name + ' volume', style: 'width:70px' });
    vol.addEventListener('input', () => { t.vol = +vol.value; E.sync(s); quiet(); });
    return h('div', { class: 'mus-grid-row' + (t.id === sel.track ? ' sel' : '') },
      h('div', { class: 'mus-tname', onclick: e => { if (e.target.closest('button,input,select')) return; sel.track = t.id; s.sel = t.id; render(); } },
        h('div', { class: 'row' }, h('b', { title: 'Double-click to rename. Click to play this track from the keyboard.', ondblclick: () => { const n = prompt('Track name', t.name); if (n) edit('Rename track', () => { t.name = n; }) || render(); } }, `${ti + 1}. ${t.name}`)),
        h('div', { class: 'row' }, btn(I.instName(t.inst).slice(0, 16), 'Change the sound', () => { sel.track = t.id; s.sel = t.id; catSel = I.catalog().find(c => c.id === t.inst)?.cat || catSel; ctx.section('sounds'); }),
          btn('M', 'Mute', () => edit('Mute', () => { t.mute = !t.mute; }) || render(), t.mute), btn('S', 'Solo', () => edit('Solo', () => { t.solo = !t.solo; }) || render(), t.solo), vol,
          h('span', { class: 'mus-meter' }, h('i', { 'data-meter': t.id })))),
      ...s.sections.map(sec => h('div', { class: 'mus-cell' + (sec.id === sel.sec && t.id === sel.track ? ' sel' : '') + (s.sections.indexOf(sec) === s.cur ? ' cur' : ''), title: 'Click to edit this part. Double-click to play this loop.',
        onclick: () => { sel.track = t.id; sel.sec = sec.id; s.sel = t.id; render(); }, ondblclick: () => launch(s.sections.indexOf(sec)) }, miniClip(t, sec))),
      h('div', { class: 'mus-cell add' }, ti === 0 ? null : btn('↑', 'Move track up', () => edit('Move track', () => { s.tracks.splice(ti - 1, 0, s.tracks.splice(ti, 1)[0]); }) || render()),
        btn('×', 'Delete track', () => { if (confirm(`Delete track ${t.name}?`)) edit('Delete track', () => { s.tracks.splice(ti, 1); }) || render(); })));
  });
  const QUICK = [['Drums', 'kit:808'], ['Piano', 'gm:acoustic_grand_piano'], ['Bass', 'gm:electric_bass_finger'], ['Strings', 'gm:string_ensemble_1'], ['Synth', 'syn:saw'], ['Pad', 'syn:pad'], ['Bunny sings', 'sing:bunny']];
  const add = h('div', { class: 'mus-addrow row' }, h('b', {}, '+ Track:'), ...QUICK.map(([n, id]) => btn(n, `Add a ${n} track`, () => { edit('Add track', () => { const t = S.newTrack(n, id); s.tracks.push(t); s.sel = t.id; sel.track = t.id; }); render(); })), btn('More sounds…', 'Browse every sound', () => ctx.section('sounds')));
  return h('div', { class: 'mus-grid' }, head, ...rows, add);
}
function songOrder() {
  const s = song(), secs = ctx.sceneSeconds();
  const off = h('input', { type: 'number', min: 0, step: 0.1, value: s.offset, title: 'Seconds into the scene where the music starts', 'aria-label': 'Music starts at seconds', style: 'width:64px' });
  off.addEventListener('change', () => edit('Music start', () => { s.offset = Math.max(0, +off.value); }));
  return h('div', { class: 'mus-row mus-arr' },
    grp('Song order', ...(s.arr.length ? s.arr.map((id, i) => { const sec = s.sections.find(x => x.id === id); return h('span', { class: 'mus-chip' }, i ? btn('←', 'Move earlier', () => edit('Song order', () => { s.arr.splice(i - 1, 0, s.arr.splice(i, 1)[0]); }) || render()) : null, h('b', {}, sec?.name || '?'), btn('×', 'Take out of the song', () => edit('Song order', () => { s.arr.splice(i, 1); }) || render())); }) : [h('span', { class: 'hint' }, 'Empty: the current loop repeats under the whole scene.')]),
      sel2('Add to song', '', [['', '+ Add loop…'], ...s.sections.map(x => [x.id, x.name])], v => { if (v) edit('Song order', () => { s.arr.push(v); }) || render(); })),
    grp('Under the animation', btn('Fill scene', 'Repeat the song so it lasts the whole scene', () => edit('Fill', () => { s.fill = !s.fill; }) || render(), s.fill),
      btn('Fit tempo to scene', `Change the tempo so the song order ends exactly when the scene ends (${secs.toFixed(1)} s)`, () => { try { const b = editV('Fit tempo', () => S.fitTempo(s, secs)); ctx.toast(`Tempo ${b} BPM: the song now lasts the scene`); render(); } catch (e) { ctx.toast(e.message); } }),
      h('label', {}, 'Starts at ', off, ' s'),
      btn('Play with the animation', 'Play the animation timeline; the music follows it (also when you press Space)', () => ctx.anim('playFromStart')),
      h('span', { class: 'hint' }, `${S.songSeconds(s).toFixed(1)} s of music · scene ${secs.toFixed(1)} s`)));
}

// ---------------------------------------------------------------- editor: piano roll or drum steps
function editor() {
  const s = song(), t = s.tracks.find(x => x.id === sel.track), sec = s.sections.find(x => x.id === sel.sec);
  if (!t || !sec) return h('p', { class: 'hint' }, 'Add a track to start.');
  const clip = () => S.clipOf(t, sec, true), notes = () => clip().notes;
  const chosen = () => (noteSel.size ? notes().filter(n => noteSel.has(n)) : notes());
  const tools = h('div', { class: 'mus-row' },
    h('b', {}, `${t.name} · ${sec.name}`),
    grp('Draw', sel2('Note length', drawLen, [[0.25, '1/16'], [0.5, '1/8'], [1, '1/4'], [2, '1/2'], [4, 'Whole']], v => { drawLen = +v; }, 'Length of notes you draw'),
      sel2('Grid', snap, [[1, 'Grid 1/4'], [0.5, 'Grid 1/8'], [0.25, 'Grid 1/16'], [0.125, 'Grid 1/32'], [1 / 3, 'Grid 1/8T'], [0, 'No grid']], v => { snap = +v; })),
    grp(noteSel.size ? `${noteSel.size} selected` : 'All notes',
      btn('Quantize', 'Snap the notes onto the grid', () => edit('Quantize', () => S.quantize(chosen(), snap || 0.25, 1)) || queueEditor()),
      btn('Quantize 50%', 'Pull halfway to the grid: tidier but still human', () => edit('Quantize', () => S.quantize(chosen(), snap || 0.25, 0.5)) || queueEditor()),
      btn('Humanize', 'Tiny random changes in timing and loudness', () => edit('Humanize', () => S.humanize(chosen(), 0.6, Date.now() % 997)) || queueEditor()),
      btn('−1', 'Down a semitone', () => edit('Transpose', () => S.transpose(chosen(), -1)) || queueEditor()), btn('+1', 'Up a semitone', () => edit('Transpose', () => S.transpose(chosen(), 1)) || queueEditor()),
      btn('−8ve', 'Down an octave', () => edit('Transpose', () => S.transpose(chosen(), -12)) || queueEditor()), btn('+8ve', 'Up an octave', () => edit('Transpose', () => S.transpose(chosen(), 12)) || queueEditor()),
      btn('Legato', 'Stretch every note to the next one', () => edit('Legato', () => S.legato(chosen())) || queueEditor()),
      btn('Louder', 'Velocity up', () => edit('Velocity', () => chosen().forEach(n => { n.v = Math.min(1, +(n.v + 0.1).toFixed(2)); })) || queueEditor()),
      btn('Softer', 'Velocity down', () => edit('Velocity', () => chosen().forEach(n => { n.v = Math.max(0.05, +(n.v - 0.1).toFixed(2)); })) || queueEditor()),
      btn('Select all', 'Select every note', () => { notes().forEach(n => noteSel.add(n)); queueEditor(); render(); }),
      btn('Delete', 'Delete the selected notes (Delete key)', () => { if (!noteSel.size) return ctx.toast('Click notes to select them first'); edit('Delete notes', () => { clip().notes = notes().filter(n => !noteSel.has(n)); noteSel.clear(); }); render(); }),
      btn('Clear', 'Clear this part', () => edit('Clear part', () => { clip().notes = []; noteSel.clear(); }) || render())),
    t.kind === 'drum'
      ? grp('Beat maker', sel2('Drum style', '', [['', 'Write a beat…'], ...Object.entries(S.DRUM_STYLES).map(([k, v]) => [k, v[0]])], v => { if (v) edit('Drum pattern', () => S.drumPattern(s, t, sec, v)) || render(); }))
      : grp('Chords', sel2('Progression', '', [['', 'Write chords…'], ...Object.entries(S.PROGRESSIONS).map(([k, v]) => [k, v[0]])], v => { if (!v) return; const style = document.getElementById('mus-chstyle')?.value || 'block'; edit('Chord progression', () => S.progression(s, t, sec, v, style)) || render(); }),
        (() => { const x = sel2('Chord style', 'block', [['block', 'Held chords'], ['stabs', 'Off-beat stabs'], ['arp', 'Broken (arpeggio)']], () => {}); x.id = 'mus-chstyle'; return x; })()));
  return h('div', { class: 'mus-editor' }, tools, t.kind === 'drum' ? stepGrid(t, sec) : pianoRoll(t, sec));
}
let edQ = false;
function queueEditor() { if (edQ) return; edQ = true; requestAnimationFrame(() => { edQ = false; const el = document.getElementById('mus-roll') || document.getElementById('mus-steps'); if (el?.redraw) el.redraw(); else if (ctx.visible() && view === 'studio') render(); }); }

function pianoRoll(t, sec) {
  const s = song(), KW = 44, RH = 12, VH = 46;
  const wrap = h('div', { class: 'mus-rollwrap' });
  const cv = h('canvas', { id: 'mus-roll', tabindex: 0, class: 'mus-roll', title: 'Click to add a note, drag to move, drag its right end to stretch, right-click to delete. Wheel scrolls up and down; Shift+click selects several.' });
  const ph = h('div', { id: 'mus-playhead', class: 'mus-playhead', 'data-left': KW });
  wrap.append(cv, ph);
  const beats = S.sectionBeats(s, sec);
  const notes = () => S.clipOf(t, sec, true).notes;
  const g = cv.getContext('2d');
  const geo = () => ({ W: cv.clientWidth || 800, H: RH * st.rows + VH });
  const ppb = () => (geo().W - KW) / beats;
  const yOf = n => (st.top - n) * RH, nOf = y => st.top - Math.floor(y / RH);
  const sn = b => (snap ? Math.round(b / snap) * snap : b);
  function draw() {
    const { W, H } = geo(), dpr = devicePixelRatio || 1, { bg, fg } = colour();
    if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); cv.style.height = H + 'px'; }
    g.setTransform(dpr, 0, 0, dpr, 0, 0); g.fillStyle = bg; g.fillRect(0, 0, W, H);
    const sc = S.SCALES[s.scale] || S.SCALES.major;
    for (let r = 0; r < st.rows; r++) {
      const n = st.top - r, inScale = sc.includes(((n - s.key) % 12 + 12) % 12), black = [1, 3, 6, 8, 10].includes(n % 12);
      g.globalAlpha = inScale ? 0.1 : 0.22; g.fillStyle = fg; if (!inScale || black) g.fillRect(KW, r * RH, W - KW, RH);
      g.globalAlpha = 1; g.fillStyle = black ? fg : bg; g.fillRect(0, r * RH, KW - 2, RH - 1);
      g.fillStyle = black ? bg : fg; g.font = '9px system-ui'; if (n % 12 === 0 || !black) g.fillText(S.noteName(n), 3, r * RH + 9);
    }
    for (let b = 0; b <= beats; b += snap || 0.25) { const x = KW + b * ppb(); g.globalAlpha = b % s.sig === 0 ? 0.9 : b % 1 === 0 ? 0.35 : 0.12; g.fillStyle = fg; g.fillRect(x, 0, b % s.sig === 0 ? 2 : 1, RH * st.rows); }
    g.globalAlpha = 1;
    for (const n of notes()) {
      if (n.n > st.top || n.n <= st.top - st.rows) continue;
      const x = KW + n.t * ppb(), y = yOf(n.n), w = Math.max(3, n.d * ppb());
      g.fillStyle = fg; g.globalAlpha = 0.45 + n.v * 0.55; g.fillRect(x, y + 1, w, RH - 2); g.globalAlpha = 1;
      if (noteSel.has(n)) { g.strokeStyle = bg; g.lineWidth = 2; g.strokeRect(x + 1.5, y + 2.5, w - 3, RH - 5); }
    }
    // velocity lane
    const vy = RH * st.rows; g.fillStyle = fg; g.fillRect(0, vy, W, 2); g.font = '10px system-ui'; g.fillText('Velocity', 3, vy + 14);
    for (const n of notes()) { const x = KW + n.t * ppb(), hh = (VH - 8) * n.v; g.fillRect(x, vy + VH - hh, 3, hh); }
  }
  let drag = null;
  cv.addEventListener('pointerdown', e => {
    cv.focus(); const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    if (x < KW) { const n = nOf(y); E.press(n, 0.8, t); setTimeout(() => E.release(n), 250); return; }
    const b = (x - KW) / ppb();
    if (y > RH * st.rows) { // velocity lane: drag sets loudness of notes under the pointer
      ctx.pushUndo('Velocity'); drag = { vel: true };
      const setV = ev => { const xx = ev.clientX - r.left, v = Math.max(0.05, Math.min(1, 1 - (ev.clientY - r.top - RH * st.rows - 4) / (VH - 8))); for (const n of notes()) if (Math.abs(KW + n.t * ppb() - xx) < 5) n.v = +v.toFixed(2); draw(); };
      setV(e); cv.setPointerCapture(e.pointerId); cv.onpointermove = setV; return;
    }
    const n = nOf(y), hit = notes().find(m => m.n === n && b >= m.t && b <= m.t + m.d);
    if (e.button === 2) { if (hit) { edit('Delete note', () => { S.clipOf(t, sec).notes = notes().filter(m => m !== hit); noteSel.delete(hit); }); draw(); } return; }
    ctx.pushUndo(hit ? 'Edit note' : 'Add note');
    let note = hit;
    if (!note) { note = { t: Math.max(0, Math.min(beats - (snap || 0.25), Math.floor(b / (snap || 0.25)) * (snap || 0.25))), d: drawLen, n, v: 0.8 }; notes().push(note); }
    if (!e.shiftKey && !noteSel.has(note)) noteSel.clear();
    noteSel.add(note);
    E.press(note.n, note.v, t); setTimeout(() => E.release(note.n), 200);
    const resize = hit && x > KW + (hit.t + hit.d) * ppb() - 6;
    const group = [...noteSel].map(m => ({ m, t: m.t, n: m.n, d: m.d }));
    drag = { b, n, resize, group };
    cv.setPointerCapture(e.pointerId);
    cv.onpointermove = ev => {
      const bb = (ev.clientX - r.left - KW) / ppb(), dn = nOf(ev.clientY - r.top) - drag.n, db = bb - drag.b;
      for (const q of drag.group) {
        if (drag.resize) q.m.d = Math.max(snap || 0.05, +sn(q.d + db).toFixed(4));
        else { q.m.t = Math.max(0, Math.min(beats - 0.01, +sn(q.t + db).toFixed(4))); q.m.n = Math.max(0, Math.min(127, q.n + dn)); }
      }
      draw();
    };
    draw();
  });
  const end = () => { if (drag) { drag = null; cv.onpointermove = null; ctx.changed(); } };
  cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', end);
  cv.addEventListener('contextmenu', e => e.preventDefault());
  cv.addEventListener('wheel', e => { e.preventDefault(); st.top = Math.max(st.rows, Math.min(127, st.top + (e.deltaY > 0 ? -2 : 2))); draw(); }, { passive: false });
  cv.addEventListener('keydown', e => { if ((e.key === 'Delete' || e.key === 'Backspace') && noteSel.size) { e.preventDefault(); e.stopPropagation(); edit('Delete notes', () => { S.clipOf(t, sec).notes = notes().filter(m => !noteSel.has(m)); noteSel.clear(); }); draw(); } });
  // show the notes that are there
  const ns = notes().map(n => n.n); if (ns.length && (Math.max(...ns) > st.top || Math.min(...ns) <= st.top - st.rows)) st.top = Math.min(127, Math.max(...ns) + 4);
  cv.redraw = draw;
  requestAnimationFrame(draw);
  new ResizeObserver(draw).observe(wrap);
  return wrap;
}
function stepGrid(t, sec) {
  const s = song(), beats = S.sectionBeats(s, sec), steps = Math.round(beats * 4);
  const wrap = h('div', { class: 'mus-stepwrap' }), grid = h('div', { class: 'mus-steps', id: 'mus-steps', style: `grid-template-columns:96px repeat(${steps}, minmax(16px, 1fr))` });
  const ph = h('div', { id: 'mus-playhead', class: 'mus-playhead', 'data-left': 96 });
  function draw() {
    const notes = S.clipOf(t, sec, true).notes;
    grid.replaceChildren();
    S.PADS.forEach((name, pi) => {
      const n = S.PAD_BASE + pi;
      grid.append(h('button', { class: 'mus-padname', title: 'Click to hear it', onclick: () => E.pad(pi, 0.9, t) }, t.inst === 'kit:user' ? (t.samples?.[pi] ? String(t.samples[pi]).split(/[\\/]/).pop().slice(0, 12) : `Pad ${pi + 1} (empty)`) : name));
      for (let k = 0; k < steps; k++) {
        const at = k / 4, hit = notes.find(m => m.n === n && Math.abs(m.t - at) < 0.125);
        grid.append(h('button', { class: 'mus-step' + (hit ? ' on' : '') + (hit && hit.v > 0.95 ? ' accent' : '') + (k % 4 === 0 ? ' beat' : '') + (k % (s.sig * 4) === 0 ? ' bar' : ''), title: `${name}, step ${k + 1}. Shift-click for an accent.`,
          onclick: e => { edit(hit ? 'Remove hit' : 'Add hit', () => { const c = S.clipOf(t, sec, true); if (hit && !e.shiftKey) c.notes = c.notes.filter(m => m !== hit); else if (hit) hit.v = hit.v > 0.95 ? 0.8 : 1; else { c.notes.push({ t: at, d: 0.2, n, v: e.shiftKey ? 1 : 0.85 }); E.pad(pi, 0.85, t); } }); draw(); } }));
      }
    });
  }
  grid.redraw = draw; draw();
  wrap.append(grid, ph);
  return wrap;
}

// on-screen keys and pads: click to play, and they light up with the MiniLab
function keyboardWidget() {
  const t = E.selTrack(), lo = 48 + E.engine.helpers.octave * 12, keys = h('div', { class: 'mus-keys', id: 'mus-keys' });
  if (t?.kind === 'drum') {
    S.PADS.forEach((p, i) => keys.append(h('button', { class: 'mus-pad', 'data-n': S.PAD_BASE + i, onpointerdown: () => E.pad(i, 0.9), onpointerup: () => E.padUp(i) }, p)));
    return h('div', { class: 'mus-kbd' }, h('h3', {}, 'Pads (the MiniLab pads play these)'), keys);
  }
  for (let n = lo; n < lo + 25; n++) {
    const black = [1, 3, 6, 8, 10].includes(n % 12);
    keys.append(h('button', { class: 'mus-key' + (black ? ' black' : ''), 'data-n': n, title: S.noteName(n), onpointerdown: e => { e.currentTarget.setPointerCapture(e.pointerId); E.press(n, 0.8); }, onpointerup: () => E.release(n), onpointercancel: () => E.release(n) }, n % 12 === 0 ? S.noteName(n) : ''));
  }
  return h('div', { class: 'mus-kbd' }, h('h3', {}, `Keys (25, like the MiniLab) · playing ${t ? t.name : 'nothing'}`), keys);
}
function lightKey(x) {
  const el = document.querySelector(`#mus-keys [data-n="${x.n}"]`); if (!el) return;
  el.classList.toggle('lit', !!x.on); if (x.on && (x.pad != null || x.arp)) setTimeout(() => el.classList.remove('lit'), 140);
}
const TYPE = 'awsedftgyhujkolp;';
function typeKeys(e) {
  if (!typing || !ctx.visible() || e.target?.matches?.('input,select,textarea') || e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (e.type === 'keydown' && (k === 'z' || k === 'x')) { e.preventDefault(); e.stopPropagation(); runAction(k === 'z' ? 'music.octDown' : 'music.octUp'); return; }
  const i = TYPE.indexOf(k); if (i < 0) return;
  e.preventDefault(); e.stopPropagation();
  const n = 60 + i; if (e.type === 'keydown') { if (!e.repeat) E.press(n, 0.8); } else E.release(n);
}

// ---------------------------------------------------------------- Mixer & effects
let mixQ = false;
function queueMixer() { if (mixQ) return; mixQ = true; setTimeout(() => { mixQ = false; if (ctx.visible() && view === 'mixer' && !document.activeElement?.matches?.('input[type=range]')) render(); }, 250); }
function fxBox(list, i, onChange) {
  const f = list[i], def = I.FX[f.type];
  return h('div', { class: 'mus-fx' + (f.on ? '' : ' off') },
    h('div', { class: 'row' }, btn(f.on ? 'On' : 'Off', 'Switch this effect on or off', () => edit('Effect on/off', () => { f.on = !f.on; }) || onChange(), f.on), h('b', {}, def?.[0] || f.type),
      i ? btn('↑', 'Earlier in the chain', () => edit('Move effect', () => { list.splice(i - 1, 0, list.splice(i, 1)[0]); }) || onChange()) : null,
      btn('×', 'Remove', () => edit('Remove effect', () => { list.splice(i, 1); }) || onChange())),
    ...Object.entries(def?.[2] || {}).map(([k, [lo, hi, label]]) => {
      const cur = f.p?.[k] ?? defaultParam(f.type, k, lo, hi);
      const r = h('input', { type: 'range', min: lo, max: hi, step: (hi - lo) / 100, value: cur, 'aria-label': label });
      r.addEventListener('input', () => { f.p = { ...(f.p || {}), [k]: +r.value }; E.sync(song()); quiet(); });
      return h('label', { class: 'mus-param' }, label, r);
    }));
}
const defaultParam = (type, k, lo, hi) => ({ wet: 0.3, decay: 2.5, feedback: 0.35, depth: 0.6, frequency: type === 'lowpass' ? 18000 : type === 'highpass' ? 20 : 5, distortion: 0.4, bits: 6, pitch: 12, width: 0.7, threshold: -20, ratio: 4, Q: 1, baseFrequency: 200, octaves: 4 })[k] ?? (lo + hi) / 2;
function mixerView(body) {
  const s = song();
  const strip = (name, id, obj, isMaster, t) => {
    const vol = h('input', { type: 'range', min: -40, max: 6, step: 0.5, value: obj.vol, class: 'mus-vfader', 'aria-label': name + ' volume', title: 'Volume (dB)' });
    vol.addEventListener('input', () => { obj.vol = +vol.value; E.sync(s); quiet(); });
    const pan = !isMaster && h('input', { type: 'range', min: -1, max: 1, step: 0.05, value: obj.pan, 'aria-label': name + ' pan', title: 'Left / right' });
    pan && pan.addEventListener('input', () => { obj.pan = +pan.value; E.sync(s); quiet(); });
    const addFx = sel2('Add effect', '', [['', '+ Effect…'], ...Object.entries(I.FX).map(([k, v]) => [k, v[0]])], v => { if (v) edit('Add effect', () => obj.fx.push({ type: v, on: true, p: {} })) || render(); });
    return h('div', { class: 'mus-strip' + (t?.id === sel.track ? ' sel' : '') },
      h('b', {}, name), !isMaster ? h('span', { class: 'hint' }, I.instName(t.inst)) : null,
      h('span', { class: 'mus-meter tall' }, h('i', { 'data-meter': id })),
      h('label', {}, 'Volume', vol), pan ? h('label', {}, 'Pan', pan) : null,
      !isMaster ? h('div', { class: 'row' }, btn('M', 'Mute', () => edit('Mute', () => { t.mute = !t.mute; }) || render(), t.mute), btn('S', 'Solo', () => edit('Solo', () => { t.solo = !t.solo; }) || render(), t.solo)) : null,
      ...obj.fx.map((_, i) => fxBox(obj.fx, i, render)), addFx);
  };
  body.append(h('p', { class: 'hint' }, 'Every track runs through its own effects, then the master. Knobs on the MiniLab can drive any of these (MiniLab & mapping).'),
    h('div', { class: 'mus-mixer' }, ...s.tracks.map(t => strip(t.name, t.id, t, false, t)), strip('Master', 'master', s.master, true)));
}

// ---------------------------------------------------------------- Sounds
const GLYPH = {
  keys: 'M3 6h18v12H3zM7 6v7M11 6v7M15 6v7M19 6v7', mallets: 'M4 18l8-8M12 10l3-3a2 2 0 1 1 3 3l-3 3M4 21h16', organ: 'M5 20V8M9 20V5M13 20V9M17 20V6M3 20h18', guitar: 'M14 4l6 6M17 7l-6 6M9 11a4 4 0 1 0 4 4', bass: 'M15 3l6 6M18 6l-8 8M8 12a5 5 0 1 0 4 4',
  strings: 'M6 3c4 4 4 14 0 18M10 3v18M18 3c-4 4-4 14 0 18', ensemble: 'M8 8a3 3 0 1 0 0-.1M16 8a3 3 0 1 0 0-.1M3 20c1-5 9-5 10 0M11 20c1-5 9-5 10 0', brass: 'M3 12h10l6-5v10l-6-5', reed: 'M8 3v12a4 4 0 0 0 8 0M8 7h3M8 11h3', pipe: 'M3 12h18M7 10v4M11 10v4M15 10v4',
  synth: 'M3 12h3l2-6 3 12 3-9 2 3h5', pad: 'M3 14c3-6 6 6 9 0s6 6 9 0', fx: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3', world: 'M12 3a9 9 0 1 0 .1 0M3 12h18M12 3c-3 3-3 15 0 18M12 3c3 3 3 15 0 18', perc: 'M5 9h14v8H5zM5 9l7-5 7 5',
  sfx: 'M4 12h2l3-6 3 12 3-12 3 6h2', drums: 'M4 10a8 3 0 1 0 16 0 8 3 0 1 0-16 0M4 10v6a8 3 0 0 0 16 0v-6M17 3l-4 6', voice: 'M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0', mine: 'M12 5v14M5 12h14',
};
const glyph = cat => { const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', '0 0 24 24'); const p = document.createElementNS(NS, 'path'); p.setAttribute('d', GLYPH[cat] || GLYPH.synth); svg.append(p); return svg; };
function soundsView(body) {
  const s = song(), t = E.selTrack();
  const list = I.catalog().filter(c => c.cat === catSel);
  const file = h('input', { type: 'file', accept: 'audio/*', style: 'display:none' });
  file.addEventListener('change', () => addOwnSound(file.files[0]).catch(e => ctx.toast(e.message, 5000)));
  body.append(h('p', { class: 'hint' }, `Pick a sound for ${t ? `track ${t.name}` : 'a new track'}. ▶ previews it. Real instruments are recordings (FluidR3 General MIDI, CC-BY 3.0); 24 come with the app, the rest download once.`),
    h('div', { class: 'chips' }, ...I.CATS.map(([id, n]) => btn(n, n, () => { catSel = id; render(); }, catSel === id))));
  if (catSel === 'mine') {
    body.append(h('div', { class: 'mus-row' }, btn('Add a sound file…', 'Use your own WAV or MP3: played across the keys, or put on a pad of the "Your own samples" kit', () => file.click()), file),
      h('p', { class: 'hint' }, 'Your sound is copied into the scene\'s work folder, so the scene keeps it. To build a drum kit from your own sounds, pick the "Your own samples" kit in Drum kits, then drop sounds on its pads below.'));
    const ut = s.tracks.find(x => x.inst === 'kit:user');
    if (ut) body.append(h('div', { class: 'mus-userpads' }, ...S.PADS.map((_, i) => { const z = h('div', { class: 'mus-userpad', title: 'Drop a sound file here' }, `Pad ${i + 1}`, h('small', {}, ut.samples?.[i] ? String(ut.samples[i]).split(/[\\/]/).pop() : 'empty')); z.addEventListener('dragover', e => e.preventDefault()); z.addEventListener('drop', e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) addOwnSound(f, { track: ut, pad: i }).catch(er => ctx.toast(er.message, 5000)); }); return z; })));
    return;
  }
  body.append(h('div', { class: 'mus-cards' }, ...list.map(c => h('div', { class: 'mus-card' + (t?.inst === c.id ? ' on' : '') + (c.ready ? '' : ' get') },
    h('span', { class: 'pic' }, glyph(c.cat)), h('b', {}, c.name), h('small', {}, c.bundled ? 'Recorded · with the app' : c.made ? 'Made in the app' : c.ready ? 'Recorded · downloaded' : 'Recorded · download'),
    h('div', { class: 'row' },
      c.ready ? btn('▶', 'Preview', () => preview(c.id)) : btn('Get', 'Download this instrument once (about 0.6 MB)', () => getSound(c)),
      c.ready ? btn(t ? 'Use' : 'New track', t ? `Use on ${t.name}` : 'Add a track with this sound', () => useSound(c)) : null,
      c.ready && t ? btn('+ Track', 'Add a new track with this sound', () => useSound(c, true)) : null)))));
}
async function preview(id) {
  await E.start();
  const tmp = I.makeInstrument(id, { api: ctx.api }); tmp.out.toDestination(); await tmp.ready; await window.Tone.loaded();
  const now = window.Tone.immediate();
  if (tmp.drum) [0, 3, 1, 3, 0, 0, 1, 2].forEach((p, i) => tmp.hit(S.PAD_BASE + p, 0.85, now + i * 0.2));
  else [60, 64, 67, 72].forEach((n, i) => tmp.hit(n, 0.8, now + i * 0.22, 0.4));
  setTimeout(() => tmp.dispose(), 4000);
}
async function getSound(c) {
  ctx.toast(`Downloading ${c.name}…`, 6000);
  const r = await ctx.api('music-get-sound', { name: c.id.slice(3) });
  await I.loadCatalog(ctx.api);
  ctx.toast(`${c.name} is ready (${r.notes} notes)`); render();
}
function useSound(c, asNew = false) {
  const s = song(); let t = E.selTrack();
  edit('Sound', () => {
    if (!t || asNew || (c.drum !== (t.kind === 'drum'))) { t = S.newTrack(c.name, c.id); s.tracks.push(t); }
    else { t.inst = c.id; t.kind = c.drum ? 'drum' : 'inst'; if (/^\d+\. |Track|Layer|Keys|Drums|Piano|Bass|Synth|Pad|Strings/.test(t.name) || true) t.name = c.name; }
    s.sel = t.id; sel.track = t.id;
  });
  ctx.toast(`${t.name}: play it on the keys`); render();
}
async function addOwnSound(f, { track = null, pad = null } = {}) {
  if (!f) return;
  const b64 = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.onerror = rej; r.readAsDataURL(f); });
  const root = await ctx.workDir('music/sounds'), safe = f.name.replace(/[^\w.\- ]+/g, '_');
  const w = await ctx.api('write-file', { path: `${root}/${safe}`, data: b64 });
  const s = song();
  edit('Your sound', () => {
    if (track) { track.samples = { ...(track.samples || {}), [pad]: w.path }; }
    else { const t = S.newTrack(safe.replace(/\.\w+$/, ''), 'smp:' + w.path); s.tracks.push(t); s.sel = t.id; sel.track = t.id; }
  });
  ctx.toast(track ? `Pad ${pad + 1}: ${safe}` : `New track playing ${safe} across the keys`); render();
}

// ---------------------------------------------------------------- MiniLab & mapping
function targetOptions() {
  const o = [['', 'Nothing']];
  o.push(...Object.entries(ACTIONS).map(([k, v]) => ['act:' + k, '▶ ' + v[0]]));
  o.push(['trk:tone', 'Selected track: filter (brightness)'], ['trk:pan', 'Selected track: left/right'], ['trk:vol', 'Selected track: volume'], ['trk:fx:reverb', 'Selected track: reverb amount'], ['trk:fx:delay', 'Selected track: echo amount'], ['trk:fx:distortion', 'Selected track: distortion amount']);
  o.push(...[0, 1, 2, 3, 4, 5, 6, 7].map(i => ['mix:' + i, `Track ${i + 1} volume`]), ['master:vol', 'Master volume'], ['song:swing', 'Swing'], ['song:bpm', 'Tempo (60–180)']);
  o.push(...S.PADS.map((p, i) => ['pad:' + i, 'Drum: ' + p]));
  o.push(...ctx.controls().map(c => ['ctl:' + c.id, 'Bunny: ' + c.label + ` (${c.group})`]));
  return o;
}
function targetPicker(value, onPick, learnSrc) {
  const s = sel2('Does', value || '', targetOptions(), onPick, 'What this control does');
  s.classList.add('mus-target');
  return s;
}
function controllerView(body) {
  const m = MI.midi.map, x = MI.midi;
  body.append(h('div', { class: 'mus-row' },
    h('b', { class: x.status === 'on' ? '' : 'warn' }, MI.statusText()),
    btn('Look again', 'Search for MIDI devices again', () => MI.connect(midiCtx()).then(render)),
    btn('Set up my MiniLab', 'Learn which numbers your knobs and faders send: move each one when asked (20 seconds)', () => wizard()),
    btn('Reset mapping', 'Back to the MiniLab 3 factory layout', () => { if (confirm('Reset every mapping to the MiniLab 3 defaults?')) { MI.resetMap(); render(); } })));
  body.append(h('p', { class: 'hint', id: 'mus-unmapped' }, 'Click any control on the picture to choose what it does. Learn: pick a job, press Learn, then move or press the control on your MiniLab. No Arturia software needed; close it (and any DAW) so Windows lets this app use the MiniLab.'));
  // the MiniLab on screen
  const knob = i => h('div', { class: 'ml-knob', id: 'ml-k' + i }, h('span', { class: 'dial' }), h('small', {}, `Knob ${i + 1}`), targetPicker(m.knobTargets[i], v => { m.knobTargets[i] = v; MI.saveMap(); render(); }), btn('Learn', 'Move this knob on the MiniLab now', () => { MI.learn('knob:' + i); ctx.toast(`Turn knob ${i + 1} on the MiniLab…`, 4000); }));
  const fader = i => h('div', { class: 'ml-fader', id: 'ml-f' + i }, h('span', { class: 'slot' }, h('i', {})), h('small', {}, `Fader ${i + 1}`), targetPicker(m.faderTargets[i], v => { m.faderTargets[i] = v; MI.saveMap(); render(); }), btn('Learn', 'Move this fader on the MiniLab now', () => { MI.learn('fader:' + i); ctx.toast(`Move fader ${i + 1}…`, 4000); }));
  const padCell = i => {
    const mode = m.padMode;
    const pick = mode === 'actions' ? sel2('Pad action', m.padActions[i] || '', [['', 'Nothing'], ...Object.entries(ACTIONS).map(([k, v]) => [k, v[0]])], v => { m.padActions[i] = v; MI.saveMap(); })
      : mode === 'faces' ? sel2('Pad face', m.faceSlots[i], ctx.names().expressions.map((n, k) => [k, n]), v => { m.faceSlots[i] = +v; MI.saveMap(); })
      : mode === 'clips' ? h('small', {}, song().sections[i]?.name || '—') : h('small', {}, S.PADS[i]);
    return h('div', { class: 'ml-pad', id: 'ml-p' + i, onpointerdown: e => { if (e.target.closest('select')) return; MI.inject([0x99, m.padBase + i, 110]); }, onpointerup: e => { if (!e.target.closest('select')) MI.inject([0x89, m.padBase + i, 0]); } }, h('b', {}, `Pad ${i + 1}`), pick);
  };
  body.append(h('div', { class: 'ml' },
    h('div', { class: 'ml-top' },
      h('div', { class: 'ml-strips' }, h('div', { class: 'ml-strip', id: 'ml-pb', title: 'Pitch strip: bends the note (±' + m.bendRange + ' semitones). In puppet mode it turns the head.' }, 'Pitch'), h('div', { class: 'ml-strip', id: 'ml-mod', title: 'Mod strip: darkens the sound. In puppet mode it nods the head.' }, 'Mod')),
      h('div', { class: 'ml-pads' }, h('div', { class: 'chips' }, h('span', { class: 'hint' }, 'Pads do:'), ...Object.entries(MI.PAD_MODES).map(([k, n]) => btn(n, n, () => { m.padMode = k; MI.saveMap(); render(); }, m.padMode === k))), h('div', { class: 'ml-padgrid' }, ...[...Array(16).keys()].map(padCell))),
      h('div', { class: 'ml-knobs' }, ...[...Array(8).keys()].map(knob)),
      h('div', { class: 'ml-faders' }, ...[...Array(4).keys()].map(fader))),
    keyboardWidget()));
  // keyboard split and bend
  const s = song();
  body.append(h('div', { class: 'mus-row' },
    grp('Split the keys', sel2('Split at', m.split?.at ?? '', [['', 'No split'], ...[48, 53, 55, 60, 65].map(n => [n, 'Below ' + S.noteName(n)])], v => { m.split = v ? { at: +v, low: m.split?.low || s.tracks.find(t => /bass/i.test(t.inst))?.id || s.tracks[0]?.id } : null; MI.saveMap(); render(); }, 'Left hand plays one track, right hand another'),
      m.split ? sel2('Left hand plays', m.split.low, s.tracks.filter(t => t.kind !== 'drum').map(t => [t.id, t.name]), v => { m.split.low = v; MI.saveMap(); }) : null,
      m.split ? h('span', { class: 'hint' }, 'Right hand plays the selected track.') : null),
    grp('Pitch strip range', sel2('Bend range', m.bendRange, [[1, '±1'], [2, '±2'], [7, '±7'], [12, '±12']], v => { m.bendRange = +v; MI.saveMap(); }))));
  // your own rules: any key, pad, knob, fader or strip
  const newTarget = h('select', { 'aria-label': 'New mapping does' }, ...targetOptions().map(([v, n]) => h('option', { value: v }, n)));
  body.append(h('h3', {}, 'Your own mappings (they win over everything above)'),
    h('div', { class: 'mus-row' }, h('span', {}, 'Make a control do:'), newTarget, btn('Learn', 'Then press a key or pad, or move a knob, fader or strip', () => { if (!newTarget.value) return ctx.toast('Pick what it should do first'); MI.learn(newTarget.value); ctx.toast('Now press or move the control on the MiniLab…', 5000); })),
    h('div', { class: 'mus-rules' }, ...(m.rules.length ? m.rules.map((r, i) => h('div', { class: 'row' }, h('b', { style: 'min-width:120px' }, srcName(r.src)), h('span', {}, '→'), targetPicker(r.target, v => { r.target = v; MI.saveMap(); }), btn('×', 'Remove this mapping', () => { m.rules.splice(i, 1); MI.saveMap(); render(); }))) : [h('p', { class: 'hint' }, 'None yet. Example: make the top C key start recording, or a pad add a key to the animation.')])));
}
function activity(a) {
  if (view !== 'controller' || !ctx.visible()) return;
  const m = MI.midi.map, flash = id => { const el = document.getElementById(id); if (el) { el.classList.add('hit'); clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove('hit'), 160); } };
  if (a.kind === 'cc') { const k = m.knobs.indexOf(a.num), f = m.faders.indexOf(a.num); if (k >= 0) { flash('ml-k' + k); const d = document.querySelector('#ml-k' + k + ' .dial'); if (d) d.style.setProperty('--a', (a.value * 270 - 135) + 'deg'); } if (f >= 0) { flash('ml-f' + f); const d = document.querySelector('#ml-f' + f + ' .slot i'); if (d) d.style.bottom = a.value * 100 + '%'; } if (a.num === 1) flash('ml-mod'); }
  if (a.kind === 'bend') flash('ml-pb');
  if (a.kind === 'noteon' && a.ch === m.padCh) flash('ml-p' + (a.num - m.padBase));
}
async function wizard() {
  const steps = [...[...Array(8).keys()].map(i => ['knob:' + i, `Turn knob ${i + 1}`]), ...[...Array(4).keys()].map(i => ['fader:' + i, `Move fader ${i + 1}`]), ['pads', 'Hit pad 1']];
  for (const [target, say] of steps) {
    ctx.toast(`${say} on the MiniLab (Esc skips)…`, 8000);
    const ok = await new Promise(res => { MI.learn(target, () => res(true)); const esc = e => { if (e.key === 'Escape') { MI.learn(null); removeEventListener('keydown', esc, true); res(false); } }; addEventListener('keydown', esc, true); setTimeout(() => { if (MI.midi.learn) { MI.learn(null); res(false); } }, 8000); });
    if (!ok) break;
  }
  ctx.toast('MiniLab set up. Every knob, fader and pad is listed in this view.', 4000); render();
}

// ---------------------------------------------------------------- Music → animation
function animateView(body) {
  const s = song(), m = MI.midi.map, tracks = s.tracks.map(t => [t.id, t.name]);
  const trk = sel2('Track', s.tracks.find(t => t.kind === 'drum')?.id || s.tracks[0]?.id, tracks, () => {}); trk.id = 'mus-bt';
  const note = sel2('Which notes', '', [['', 'Every note'], ...S.PADS.map((p, i) => [S.PAD_BASE + i, 'Only ' + p])], () => {}); note.id = 'mus-bn';
  const amt = h('input', { type: 'range', min: 0.2, max: 2, step: 0.1, value: 1, 'aria-label': 'Strength' });
  const every = sel2('Every', 1, [[1, 'Every hit'], [2, 'Every 2nd hit'], [4, 'Every 4th hit']], () => {});
  const scope = sel2('Where', 'shot', [['shot', 'This shot'], ['scene', 'Every shot']], () => {});
  const boxes = Object.entries(AN.BEAT_MOVES).map(([k, [n]]) => { const c = h('input', { type: 'checkbox', value: k }); if (k === 'nod') c.checked = true; return h('label', { class: 'mus-check' }, c, n); });
  const singTrk = sel2('Melody track', s.tracks.find(t => t.kind !== 'drum')?.id || '', tracks, () => {});
  const singScope = sel2('Where', 'shot', [['shot', 'This shot'], ['scene', 'Every shot']], () => {});
  body.append(
    h('h3', {}, 'Animate to the beat'),
    h('p', { class: 'hint' }, 'Keys a move on every hit of a track, from the exact note times. Eased up on the hit and back before the next one. Undo removes it all.'),
    h('div', { class: 'mus-row' }, trk, note, every, scope, h('label', {}, 'Strength ', amt)),
    h('div', { class: 'mus-row' }, ...boxes, h('button', { class: 'primary', onclick: () => { try { const moves = boxes.map(b => b.querySelector('input')).filter(c => c.checked).map(c => c.value); const r = ctx.animEdit('Beat moves', c => AN.beatMoves(c, { track: trk.value, note: note.value ? +note.value : null, moves, amount: +amt.value, scope: scope.value, every: +every.value })); ctx.toast(`${r.keys} beat moves on ${r.shots.join(', ')}`); } catch (e) { ctx.toast(e.message, 5000); } } }, 'Key the beat moves')),
    h('h3', {}, 'The character sings the melody'),
    h('p', { class: 'hint' }, 'Mouth opens on every note (loud notes wide, soft ones round) and rests between notes. Pair it with a "Bunny sings" track to hear him.'),
    h('div', { class: 'mus-row' }, singTrk, singScope, h('button', { class: 'primary', onclick: () => { try { const r = ctx.animEdit('Sing', c => AN.sing(c, { track: singTrk.value, scope: singScope.value })); ctx.toast(`${r.keys} mouth keys`); } catch (e) { ctx.toast(e.message, 5000); } } }, 'Key the singing mouth')),
    h('h3', {}, 'Puppet mode (perform the character live)'),
    h('p', { class: 'hint' }, 'Keys open the mouth by how hard you play, pads switch faces (set Pads do: Faces), the mod strip nods the head, the pitch strip turns it, key pressure squashes. With Record keys on, press Space to play the animation and perform: every move becomes a normal key you can edit.'),
    h('div', { class: 'mus-row' }, btn(m.puppet ? 'Puppet mode: on' : 'Puppet mode: off', 'Your playing moves the character', () => runAction('music.puppet'), m.puppet),
      btn('Record keys', 'Write keys while the animation plays (otherwise it is only a preview)', () => { ctx.setPuppetRecord(!ctx.puppetRecord()); render(); }, ctx.puppetRecord()),
      btn('Keys move the mouth', 'Turn off if you only want pads and strips to move him', () => { m.puppetKeys = !m.puppetKeys; MI.saveMap(); render(); }, m.puppetKeys),
      btn('Pads switch faces', 'Set the pads to faces', () => { m.padMode = 'faces'; MI.saveMap(); ctx.toast('Pads now switch faces; pick the 16 faces in MiniLab & mapping'); render(); }, m.padMode === 'faces')));
}

// ---------------------------------------------------------------- Bounce & files
function exportView(body) {
  const s = song(), bed = ctx.scene().music;
  const vol = h('input', { type: 'range', min: 0.05, max: 1, step: 0.05, value: bed?.volume ?? 0.6, 'aria-label': 'Music volume under the voice' });
  const duck = h('input', { type: 'range', min: 0, max: 1, step: 0.05, value: bed?.duck ?? 0.35, 'aria-label': 'How much it dips under the voice' });
  const mid = h('input', { type: 'file', accept: '.mid,.midi,audio/midi', style: 'display:none' });
  mid.addEventListener('change', async () => { const f = mid.files[0]; if (!f) return; const bytes = new Uint8Array(await f.arrayBuffer()); await MF.loadGmNames(); const r = editV('Import MIDI', () => MF.importMidi(s, bytes)); ctx.toast(`Imported ${r.tracks.length} tracks into "${r.section}" (${r.bars} bars, ${r.bpm} BPM)`, 5000); ctx.section('studio'); });
  body.append(
    h('h3', {}, 'Put the music under the animation'),
    h('p', { class: 'hint' }, `Bounce turns the song into one WAV in the scene's work folder and makes it the music bed: it plays under the voice, dips while someone talks, and goes into the final render. ${bed?.fromSong ? (bed.rev === s.rev ? 'The music bed is up to date.' : 'The song changed since the last bounce; renders bounce it again automatically.') : ''}`),
    h('div', { class: 'mus-row' }, h('label', {}, 'Music volume ', vol), h('label', {}, 'Dip under the voice ', duck),
      h('button', { class: 'primary', onclick: () => bounceToBed({ volume: +vol.value, duck: +duck.value }).catch(e => ctx.toast(e.message, 6000)) }, 'Bounce to the music bed')),
    h('h3', {}, 'Files'),
    h('div', { class: 'mus-row' },
      btn('Export WAV', 'The whole song as a WAV file in the scene\'s work folder', () => exportWav().catch(e => ctx.toast(e.message, 5000))),
      btn('Export stems', 'One WAV per track (drums, bass, keys…), for mixing elsewhere', () => exportStems().catch(e => ctx.toast(e.message, 5000))),
      btn('Export MIDI', 'The notes as a .mid file, for any other music program', () => exportMid().catch(e => ctx.toast(e.message, 5000))),
      btn('Import MIDI…', 'Bring in a .mid file: one track per part, with the closest sounds', () => mid.click()), mid),
    st.msg ? h('p', { class: 'hint' }, st.msg) : null);
}
const sceneLen = () => ctx.sceneSeconds();
async function writeWav(name, r) { const root = await ctx.workDir('music'); return ctx.api('write-file', { path: `${root}/${name}`, data: E.wavBase64(r.channels, r.sr) }); }
export async function bounceToBed({ volume = 0.6, duck = 0.35, quiet = false } = {}) {
  const s = ensureSong();
  if (!S.hasNotes(s)) throw Error('There are no notes yet. Record or draw some in the Studio first.');
  if (!quiet) ctx.toast('Bouncing the music…', 8000);
  s.rev = (s.rev || 0) + 1;
  const r = await E.bounce({ seconds: sceneLen() });
  const w = await writeWav(`${ctx.safeName()}_music_v${String(s.rev).padStart(3, '0')}.wav`, r);
  await ctx.setMusicBed({ path: w.path, volume, duck, fromSong: true, rev: s.rev });
  st.msg = `Music bed: ${w.path}`;
  if (!quiet) { ctx.toast(`Music bed ready: ${r.seconds.toFixed(1)} s, dips under the voice`, 5000); if (ctx.visible()) render(); }
  return { path: w.path, seconds: +r.seconds.toFixed(2) };
}
// before a render: bounce again if the song changed since the last bounce
export async function ensureBounced() {
  const sc = ctx.scene(), s = sc.song;
  if (!s || !S.hasNotes(s) || !sc.music?.fromSong || sc.music.rev === s.rev) return null;
  return bounceToBed({ volume: sc.music.volume, duck: sc.music.duck, quiet: true });
}
// any song edit marks the bounce out of date
export function touched() { const s = ctx.scene().song; if (s) s.rev = (s.rev || 0) + 0.001; }
async function exportWav() { const r = await E.bounce({}); const w = await writeWav(`${ctx.safeName()}_song.wav`, r); st.msg = 'Wrote ' + w.path; ctx.toast(st.msg, 5000); render(); return w; }
async function exportStems() {
  const s = song(), out = [];
  for (const t of s.tracks) { if (!Object.values(t.clips).some(c => c.notes.length)) continue; ctx.toast(`Bouncing ${t.name}…`, 4000); const r = await E.bounce({ only: t.id }); out.push((await writeWav(`stems/${ctx.safeName()}_${t.name.replace(/[^\w-]+/g, '_')}.wav`, r)).path); }
  st.msg = `${out.length} stems in the work folder's music\\stems`; ctx.toast(st.msg, 5000); render(); return out;
}
async function exportMid() {
  await MF.loadGmNames();
  const bytes = MF.exportMidi(song(), {}); let bin = ''; for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  const root = await ctx.workDir('music'), w = await ctx.api('write-file', { path: `${root}/${ctx.safeName()}.mid`, data: btoa(bin) });
  st.msg = 'Wrote ' + w.path; ctx.toast(st.msg, 5000); render(); return w;
}
export { exportWav, exportStems, exportMid };
export const selected = () => ({ ...sel });
export const puppetOn = () => !!MI.midi.map.puppet;
