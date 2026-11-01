// MCP tool `music`: Claude can read and write the song like the user does in the Music workspace.
import * as S from './song.js';
import * as E from './engine.js';
import * as I from './instruments.js';
import * as MI from './midi.js';
import * as MF from './midifile.js';
import * as AN from './anim.js';
import * as UI from './ui.js';

const trackOf = (s, ref) => { const t = typeof ref === 'number' ? s.tracks[ref] : s.tracks.find(x => x.id === ref || x.name === ref); if (!t) throw Error(`No track ${ref}. Tracks: ${s.tracks.map((x, i) => `${i} ${x.name}`).join(', ')}`); return t; };
const secOf = (s, ref) => { if (ref == null) return S.curSection(s); const x = typeof ref === 'number' ? s.sections[ref] : s.sections.find(q => q.id === ref || q.name === ref); if (!x) throw Error(`No loop ${ref}. Loops: ${s.sections.map((q, i) => `${i} ${q.name}`).join(', ')}`); return x; };
const summary = s => ({ bpm: s.bpm, sig: s.sig, key: S.NOTE_NAMES[s.key], scale: s.scale, swing: s.swing, fill: s.fill, offset: s.offset, seconds: +S.songSeconds(s).toFixed(2), current: s.sections[s.cur].name,
  loops: s.sections.map((x, i) => ({ index: i, name: x.name, bars: x.bars })), order: s.arr.map(id => s.sections.find(x => x.id === id)?.name),
  tracks: s.tracks.map((t, i) => ({ index: i, name: t.name, sound: t.inst, kind: t.kind, vol: t.vol, pan: t.pan, mute: t.mute, solo: t.solo, fx: t.fx.map(f => f.type), notes: Object.fromEntries(s.sections.map(x => [x.name, t.clips[x.id]?.notes.length || 0])) })) });

export async function musicTool(ctx, a) {
  const act = a.action || 'status';
  if (act === 'status') return { midi: { status: MI.midi.status, device: MI.midi.device, miniLab: MI.midi.isMiniLab, text: MI.statusText() }, song: ctx.scene().song ? summary(ctx.scene().song) : null, playing: E.engine.playing, recording: E.engine.recording };
  if (act === 'sounds') { await I.loadCatalog(ctx.api); return { sounds: I.catalog().filter(c => !a.category || c.cat === a.category).map(c => ({ id: c.id, name: c.name, category: c.cat, ready: c.ready })), categories: I.CATS.map(c => c[0]), effects: Object.keys(I.FX), drumStyles: Object.keys(S.DRUM_STYLES), progressions: Object.keys(S.PROGRESSIONS), scales: Object.keys(S.SCALES), pads: S.PADS };
  }
  const s = UI.ensureSong();
  const edit = (label, fn) => { ctx.pushUndo('Music: ' + label); const r = fn(); UI.touched(); ctx.changed(); E.sync(s); if (ctx.visible()) ctx.rebuild(); return r; };
  switch (act) {
    case 'song': return summary(s);
    case 'notes': { const t = trackOf(s, a.track), sec = secOf(s, a.loop); return { track: t.name, loop: sec.name, beats: S.sectionBeats(s, sec), notes: (t.clips[sec.id]?.notes || []).map(n => ({ t: n.t, d: n.d, note: S.noteName(n.n), n: n.n, v: n.v })) }; }
    case 'set': return edit('Song settings', () => {
      if (a.bpm != null) E.setBpm(a.bpm);
      if (a.sig != null) s.sig = Math.max(2, Math.min(12, +a.sig));
      if (a.key != null) { const k = typeof a.key === 'number' ? a.key : S.NOTE_NAMES.indexOf(String(a.key).replace('Db', 'C#').replace('Gb', 'F#').replace('D#', 'Eb').replace('G#', 'Ab').replace('A#', 'Bb')); if (k < 0) throw Error('key: C, C#, D, Eb, E, F, F#, G, Ab, A, Bb, B'); s.key = k; }
      if (a.scale != null) { if (!S.SCALES[a.scale]) throw Error('scale: ' + Object.keys(S.SCALES).join(', ')); s.scale = a.scale; }
      if (a.swing != null) s.swing = Math.max(0, Math.min(0.6, +a.swing));
      if (a.fill != null) s.fill = !!a.fill;
      if (a.offset != null) s.offset = Math.max(0, +a.offset);
      if (a.order) s.arr = a.order.map(r => secOf(s, r).id);
      if (a.fit_scene) S.fitTempo(s, ctx.sceneSeconds());
      return summary(s);
    });
    case 'add_track': return edit('Add track', () => { const t = S.newTrack(a.name || I.instName(a.sound || 'gm:acoustic_grand_piano'), a.sound || 'gm:acoustic_grand_piano'); s.tracks.push(t); return summary(s); });
    case 'set_track': return edit('Track', () => {
      const t = trackOf(s, a.track);
      if (a.sound) { t.inst = a.sound; t.kind = a.sound.startsWith('kit:') ? 'drum' : 'inst'; }
      for (const k of ['name', 'vol', 'pan', 'mute', 'solo']) if (a[k] != null) t[k] = a[k];
      if (a.add_fx) { if (!I.FX[a.add_fx]) throw Error('fx: ' + Object.keys(I.FX).join(', ')); t.fx.push({ type: a.add_fx, on: true, p: a.fx_params || {} }); }
      if (a.remove_fx != null) t.fx.splice(a.remove_fx, 1);
      return summary(s);
    });
    case 'remove_track': return edit('Remove track', () => { const t = trackOf(s, a.track); s.tracks.splice(s.tracks.indexOf(t), 1); return summary(s); });
    case 'add_loop': return edit('Add loop', () => { const x = { id: S.uid('s'), name: a.name || 'Loop ' + String.fromCharCode(65 + s.sections.length), bars: a.bars || 4 }; s.sections.push(x); if (a.copy_from != null) { const src = secOf(s, a.copy_from); for (const t of s.tracks) if (t.clips[src.id]) t.clips[x.id] = JSON.parse(JSON.stringify(t.clips[src.id])); } return summary(s); });
    case 'set_loop': return edit('Loop', () => { const x = secOf(s, a.loop); if (a.name) x.name = a.name; if (a.bars) x.bars = a.bars; if (a.current) s.cur = s.sections.indexOf(x); return summary(s); });
    case 'add_notes': return edit('Add notes', () => {
      const t = trackOf(s, a.track), sec = secOf(s, a.loop), c = S.clipOf(t, sec, true);
      if (a.replace) c.notes = [];
      for (const n of a.notes || []) {
        const nn = n.pad != null ? S.PAD_BASE + (typeof n.pad === 'number' ? n.pad : S.PADS.findIndex(p => p.toLowerCase() === String(n.pad).toLowerCase())) : S.parseNote(n.note ?? n.n);
        if (!(nn >= 0 && nn <= 127)) throw Error('Each note needs note (C4, F#3, 60) or pad (0-15 or a pad name)');
        c.notes.push({ t: +(+n.t || 0).toFixed(4), d: +(+n.d || 0.5).toFixed(4), n: nn, v: Math.max(0.05, Math.min(1, n.v ?? 0.8)) });
      }
      return { track: t.name, loop: sec.name, notes: c.notes.length };
    });
    case 'clear': return edit('Clear part', () => { const t = trackOf(s, a.track), sec = secOf(s, a.loop); S.clipOf(t, sec, true).notes = []; return { cleared: true }; });
    case 'progression': return edit('Chords', () => { const t = trackOf(s, a.track), c = S.progression(s, t, secOf(s, a.loop), a.progression || 'pop', a.style || 'block', !!a.seventh); return { notes: c.notes.length }; });
    case 'drums': return edit('Drum pattern', () => { const t = trackOf(s, a.track ?? s.tracks.findIndex(x => x.kind === 'drum')), c = S.drumPattern(s, t, secOf(s, a.loop), a.style || 'basic'); return { notes: c.notes.length }; });
    case 'quantize': return edit('Quantize', () => { const t = trackOf(s, a.track), c = S.clipOf(t, secOf(s, a.loop), true); S.quantize(c.notes, a.grid || 0.25, a.strength ?? 1); if (a.humanize) S.humanize(c.notes, a.humanize); return { notes: c.notes.length }; });
    case 'transpose': return edit('Transpose', () => { const t = trackOf(s, a.track), c = S.clipOf(t, secOf(s, a.loop), true); S.transpose(c.notes, a.semitones || 0); return { notes: c.notes.length }; });
    case 'play': await E.play({ loop: a.loop !== false, from: 0 }); return { playing: true };
    case 'stop': E.stop(); return { playing: false };
    case 'bounce': return UI.bounceToBed({ volume: a.volume ?? 0.6, duck: a.duck ?? 0.35 });
    case 'export_wav': return UI.exportWav();
    case 'export_stems': return { stems: await UI.exportStems() };
    case 'export_midi': return UI.exportMid();
    case 'import_midi': {
      if (!a.data) throw Error('data: the .mid file as base64');
      await MF.loadGmNames();
      return edit('Import MIDI', () => MF.importMidi(s, Uint8Array.from(atob(a.data), c => c.charCodeAt(0))));
    }
    case 'beat_moves': return ctx.animEdit('Beat moves', c => AN.beatMoves(c, { track: trackOf(s, a.track ?? s.tracks.findIndex(x => x.kind === 'drum')).id, note: a.pad != null ? S.PAD_BASE + a.pad : a.note != null ? S.parseNote(a.note) : null, moves: a.moves || ['nod'], amount: a.amount ?? 1, scope: a.scope || 'shot', every: a.every || 1 }));
    case 'sing': return ctx.animEdit('Sing', c => AN.sing(c, { track: trackOf(s, a.track ?? s.tracks.findIndex(x => x.kind !== 'drum')).id, scope: a.scope || 'shot' }));
    case 'mapping': return { map: MI.midi.map, actions: Object.keys(UI.ACTIONS) };
    case 'map': {
      const m = MI.midi.map;
      if (a.pad_mode) { if (!MI.PAD_MODES[a.pad_mode]) throw Error('pad_mode: ' + Object.keys(MI.PAD_MODES).join(', ')); m.pad_mode = undefined; m.padMode = a.pad_mode; }
      if (a.knob != null) m.knobTargets[a.knob] = a.target;
      if (a.fader != null) m.faderTargets[a.fader] = a.target;
      if (a.pad != null && a.action) m.padActions[a.pad] = a.action;
      if (a.src && a.target) { m.rules = m.rules.filter(r => r.src !== a.src); m.rules.push({ src: a.src, target: a.target }); }
      if (a.puppet != null) m.puppet = !!a.puppet;
      MI.saveMap(); if (ctx.visible()) ctx.rebuild();
      return { map: m };
    }
    default: throw Error('action: status, sounds, song, notes, set, add_track, set_track, remove_track, add_loop, set_loop, add_notes, clear, progression, drums, quantize, transpose, play, stop, bounce, export_wav, export_stems, export_midi, import_midi, beat_moves, sing, mapping, map');
  }
}
