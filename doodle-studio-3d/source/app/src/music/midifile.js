// .mid files in and out (@tonejs/midi, MIT, vendor/tonejs-midi). Export writes the arrangement as laid
// out over the scene; import makes one track per MIDI track with the closest General MIDI sound.
import * as S from './song.js';
const Mi = () => window.Midi?.Midi || window.Midi;

export function exportMidi(song, { seconds = null } = {}) {
  const midi = new (Mi())();
  midi.header.setTempo(song.bpm);
  midi.header.timeSignatures.push({ ticks: 0, timeSignature: [song.sig, 4] });
  const until = seconds ? S.secToBeat(song, seconds) : S.songBeats(song);
  song.tracks.forEach((t, i) => {
    const tr = midi.addTrack(); tr.name = t.name;
    if (t.kind === 'drum') tr.channel = 9;
    else { tr.channel = i >= 9 ? i + 1 : i; const p = /^gm:/.test(t.inst) ? GM.indexOf(t.inst.slice(3)) : 0; tr.instrument.number = Math.max(0, p); }
    const ev = S.eventsIn({ ...song, tracks: [{ ...t, mute: false, solo: false }] }, 0, until, { loop: false, until });
    for (const e of ev) tr.addNote({ midi: e.n, time: (song.offset + e.at * 60 / song.bpm), duration: Math.max(0.02, e.d * 60 / song.bpm), velocity: e.v });
  });
  return midi.toArray();
}
export function importMidi(song, bytes, { into = null } = {}) {
  const midi = new (Mi())(bytes);
  const bpm = midi.header.tempos[0]?.bpm; if (bpm && !into) song.bpm = Math.round(bpm * 100) / 100;
  const sig = midi.header.timeSignatures[0]?.timeSignature?.[0]; if (sig && !into) song.sig = sig;
  const spb = 60 / song.bpm, made = [];
  let maxBeat = 0;
  const sec = into ? song.sections.find(s => s.id === into) : { id: S.uid('s'), name: 'Imported', bars: 4 };
  for (const tr of midi.tracks) {
    if (!tr.notes.length) continue;
    const drum = tr.channel === 9 || tr.instrument?.percussion;
    const inst = drum ? 'kit:acoustic' : 'gm:' + (GM[tr.instrument?.number ?? 0] || 'acoustic_grand_piano');
    const t = S.newTrack(tr.name || tr.instrument?.name || (drum ? 'Drums' : 'Track'), inst);
    const c = S.clipOf(t, sec, true);
    for (const n of tr.notes) {
      const b = n.time / spb; maxBeat = Math.max(maxBeat, b + n.duration / spb);
      // General MIDI drum notes 35-81 folded onto the 16 pads
      const nn = drum ? S.PAD_BASE + (GM_DRUM[n.midi] ?? 3) : n.midi;
      c.notes.push({ t: +b.toFixed(4), d: +(n.duration / spb).toFixed(4), n: nn, v: +n.velocity.toFixed(3) });
    }
    song.tracks.push(t); made.push(t.name);
  }
  if (!into) { sec.bars = Math.max(1, Math.ceil(maxBeat / song.sig)); song.sections.push(sec); song.cur = song.sections.length - 1; }
  return { tracks: made, bars: sec.bars, bpm: song.bpm, section: sec.name };
}
const GM_DRUM = { 35: 0, 36: 0, 37: 8, 38: 1, 39: 2, 40: 1, 41: 5, 42: 3, 43: 5, 44: 3, 45: 5, 46: 4, 47: 6, 48: 6, 49: 7, 50: 6, 51: 11, 52: 7, 53: 11, 54: 9, 55: 7, 56: 10, 57: 7, 59: 11, 69: 9, 70: 9, 75: 8, 76: 8, 77: 8 };
export let GM = [];
export async function loadGmNames() { if (!GM.length) GM = await (await fetch('vendor/sounds/fluidr3/names.json')).json(); return GM; }
