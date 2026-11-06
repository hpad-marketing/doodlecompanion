// Music workspace instruments, all on Tone.js (MIT, vendor/tone):
//   gm:<name>     real recorded instruments (FluidR3 General MIDI, CC-BY 3.0). 24 come with the app,
//                 the other 104 download once into the app's data folder (Sounds › Get).
//   syn:<preset>  synths made in the app
//   kit:<kit>     drum kits made in the app: 16 pads each, including cartoon hits for animation
//   sing:<who>    Bunny, Koala or Frog singing "ooh / la" at the note you play
//   smp:<path>    one of your own sounds played across the keys; kit:user uses your sounds on pads
import { PADS, PAD_BASE, noteName } from './song.js';
const T = () => window.Tone;

export const CATS = [['keys', 'Keys'], ['mallets', 'Bells & mallets'], ['organ', 'Organ'], ['guitar', 'Guitars'], ['bass', 'Bass'], ['strings', 'Strings'], ['ensemble', 'Choir & orchestra'], ['brass', 'Brass'], ['reed', 'Sax & reeds'], ['pipe', 'Flutes'], ['synth', 'Synths'], ['pad', 'Pads'], ['fx', 'Synth FX'], ['world', 'World'], ['perc', 'Percussion'], ['sfx', 'Sound effects'], ['drums', 'Drum kits'], ['voice', 'Characters sing'], ['mine', 'Your sounds']];
const GM_CAT = ['keys', 'mallets', 'organ', 'guitar', 'bass', 'strings', 'ensemble', 'brass', 'reed', 'pipe', 'synth', 'pad', 'fx', 'world', 'perc', 'sfx'];
const nice = s => s.replace(/_/g, ' ').replace(/\b1\b/, '').replace(/\s+/g, ' ').trim().replace(/^./, c => c.toUpperCase());

let gmIndex = null, gmNames = [], downloaded = {};
export async function loadCatalog(api) {
  await ensureIndex();
  try { downloaded = (await api('music-sounds', {})).sounds || {}; } catch { downloaded = {}; }
  return catalog();
}
export const SYNTHS = {
  softkeys: ['Soft keys', 'keys', { type: 'FMSynth', o: { harmonicity: 2, modulationIndex: 1.5, envelope: { attack: 0.005, decay: 0.8, sustain: 0.2, release: 0.8 } } }],
  pluck: ['Pluck', 'synth', { type: 'Synth', o: { oscillator: { type: 'triangle8' }, envelope: { attack: 0.002, decay: 0.25, sustain: 0, release: 0.2 } } }],
  lead: ['Square lead', 'synth', { type: 'Synth', o: { oscillator: { type: 'square' }, envelope: { attack: 0.01, decay: 0.1, sustain: 0.6, release: 0.15 } } }],
  saw: ['Saw lead', 'synth', { type: 'Synth', o: { oscillator: { type: 'fatsawtooth', count: 3, spread: 25 }, envelope: { attack: 0.01, decay: 0.2, sustain: 0.6, release: 0.3 } } }],
  chip: ['Chiptune', 'synth', { type: 'Synth', o: { oscillator: { type: 'pulse', width: 0.25 }, envelope: { attack: 0.001, decay: 0.05, sustain: 0.5, release: 0.05 } } }],
  pad: ['Warm pad', 'pad', { type: 'AMSynth', o: { harmonicity: 1.5, oscillator: { type: 'fatsine' }, envelope: { attack: 0.6, decay: 0.5, sustain: 0.8, release: 2 } } }],
  glass: ['Glass pad', 'pad', { type: 'FMSynth', o: { harmonicity: 3.01, modulationIndex: 4, envelope: { attack: 0.4, decay: 1, sustain: 0.6, release: 2.5 } } }],
  bell: ['Bell', 'mallets', { type: 'FMSynth', o: { harmonicity: 3.01, modulationIndex: 14, envelope: { attack: 0.001, decay: 1.6, sustain: 0, release: 1.6 }, modulationEnvelope: { attack: 0.002, decay: 0.4, sustain: 0, release: 0.3 } } }],
  bass: ['Synth bass', 'bass', { type: 'MonoSynth', o: { oscillator: { type: 'sawtooth' }, filter: { Q: 2, type: 'lowpass' }, filterEnvelope: { attack: 0.005, decay: 0.2, sustain: 0.3, baseFrequency: 80, octaves: 3 }, envelope: { attack: 0.005, decay: 0.2, sustain: 0.7, release: 0.15 } } }],
  sub: ['808 sub bass', 'bass', { type: 'MembraneSynth', o: { pitchDecay: 0.02, octaves: 1.5, envelope: { attack: 0.002, decay: 1.2, sustain: 0.4, release: 0.8 } } }],
  wobble: ['Wobble bass', 'bass', { type: 'MonoSynth', o: { oscillator: { type: 'fatsawtooth' }, filter: { Q: 6, type: 'lowpass' }, filterEnvelope: { attack: 0.08, decay: 0.15, sustain: 0.9, baseFrequency: 60, octaves: 4 }, envelope: { attack: 0.01, decay: 0.2, sustain: 0.9, release: 0.2 } } }],
  strings: ['Synth strings', 'strings', { type: 'Synth', o: { oscillator: { type: 'fatsawtooth', count: 5, spread: 40 }, envelope: { attack: 0.35, decay: 0.3, sustain: 0.8, release: 1.2 } } }],
  organ: ['Toy organ', 'organ', { type: 'Synth', o: { oscillator: { type: 'custom', partials: [1, 0.5, 0.33, 0.25, 0.2] }, envelope: { attack: 0.01, decay: 0.05, sustain: 1, release: 0.08 } } }],
  kazoo: ['Kazoo', 'fx', { type: 'Synth', o: { oscillator: { type: 'fatsquare', count: 2, spread: 12 }, envelope: { attack: 0.03, decay: 0.1, sustain: 0.8, release: 0.1 } } }],
  theremin: ['Spooky theremin', 'fx', { type: 'MonoSynth', o: { portamento: 0.12, oscillator: { type: 'sine' }, envelope: { attack: 0.2, decay: 0.1, sustain: 1, release: 0.6 }, filterEnvelope: { baseFrequency: 2000, octaves: 0 } } }],
};
export const KITS = { '808': 'Classic 808', '909': 'Dance 909', lofi: 'Lo-fi dusty', chip: '8-bit', acoustic: 'Acoustic-ish', doodle: 'Doodle cartoon hits', user: 'Your own samples' };
export const SINGERS = { bunny: 'Bunny sings', koala: 'Koala sings', frog: 'Frog sings' };

// the full sound list, for the browser
export function catalog() {
  const out = [];
  gmNames.forEach((n, i) => out.push({ id: 'gm:' + n, name: nice(n), cat: GM_CAT[Math.floor(i / 8)], program: i, bundled: !!gmIndex?.[n], ready: !!gmIndex?.[n] || !!downloaded[n] }));
  for (const [k, [name, cat]] of Object.entries(SYNTHS)) out.push({ id: 'syn:' + k, name, cat, ready: true, made: true });
  for (const [k, name] of Object.entries(KITS)) out.push({ id: 'kit:' + k, name, cat: 'drums', ready: true, made: true, drum: true });
  for (const [k, name] of Object.entries(SINGERS)) out.push({ id: 'sing:' + k, name, cat: 'voice', ready: true, made: true });
  return out;
}
export const instName = id => catalog().find(c => c.id === id)?.name || (id.startsWith('smp:') ? 'Sample: ' + id.split(/[\\/]/).pop() : id);
export const gmReady = n => !!gmIndex?.[n] || !!downloaded[n];

// ---------------------------------------------------------------- shared sample buffers (so offline bounces reuse them)
const bufs = new Map();
async function buffer(url) {
  if (!bufs.has(url)) bufs.set(url, (async () => { const r = await fetch(url); if (!r.ok) throw Error('Missing sound ' + url); return await T().getContext().rawContext.decodeAudioData(await r.arrayBuffer()); })());
  return bufs.get(url);
}
const fileBufs = new Map();
export async function fileBuffer(api, path) {
  if (!fileBufs.has(path)) fileBufs.set(path, (async () => { const { data } = await api('read-audio', { path }); return await T().getContext().rawContext.decodeAudioData(Uint8Array.from(atob(data), c => c.charCodeAt(0)).buffer); })());
  return fileBufs.get(path);
}
export function putFileBuffer(path, audioBuffer) { fileBufs.set(path, Promise.resolve(audioBuffer)); }
async function ensureIndex() {
  if (gmIndex) return;
  gmIndex = await (await fetch('vendor/sounds/fluidr3/index.json')).json();
  gmNames = await (await fetch('vendor/sounds/fluidr3/names.json')).json();
}
async function gmUrls(name) {
  await ensureIndex();
  const notes = gmIndex?.[name] || downloaded[name];
  if (!notes) throw Error(`${nice(name)} is not downloaded yet. Get it in Music › Sounds.`);
  const base = gmIndex?.[name] ? `vendor/sounds/fluidr3/${name}/` : `sounds/fluidr3/${name}/`;
  const urls = {};
  await Promise.all(notes.map(async n => { urls[n] = await buffer(base + n + '.mp3'); }));
  return urls;
}

// ---------------------------------------------------------------- the instrument object every track gets
// inst.out: Tone node to connect; on/off/hit; bend (semitones); releaseAll; dispose; ready (Promise)
export function makeInstrument(id, { api, track } = {}) {
  const Tone = T(), out = new Tone.Gain(1);
  const inst = { id, out, drum: false, ready: Promise.resolve(), on() {}, off() {}, bend() {}, releaseAll() {}, dispose() { try { inner?.dispose?.(); } catch {} for (const d of extra) try { d.dispose(); } catch {} out.dispose(); } };
  let inner = null; const extra = [];
  const [kind, name] = [id.slice(0, id.indexOf(':')), id.slice(id.indexOf(':') + 1)];
  const midiNote = n => Tone.Frequency(n, 'midi').toFrequency();
  if (kind === 'gm' || kind === 'smp') {
    inst.ready = (async () => {
      const urls = kind === 'gm' ? await gmUrls(name) : { C4: await fileBuffer(api, name) };
      inner = new Tone.Sampler({ urls, release: kind === 'gm' && /piano|guitar|harp|pizz|mallet|marimba|vibra|music_box|kalimba|bell|celesta|glock|xylo|steel|sitar|banjo|koto|shamisen/.test(name) ? 1 : 0.4 }).connect(out);
    })();
    inst.on = (n, v, time) => inner?.triggerAttack(midiNote(n), time, v);
    inst.off = (n, time) => inner?.triggerRelease(midiNote(n), time);
    inst.hit = (n, v, time, dur) => inner?.triggerAttackRelease(midiNote(n), dur, time, v);
    inst.releaseAll = time => inner?.releaseAll(time);
  } else if (kind === 'syn') {
    const p = SYNTHS[name]?.[2] || SYNTHS.softkeys[2];
    inner = new Tone.PolySynth(Tone[p.type], p.o).connect(out);
    inner.maxPolyphony = 24;
    inner.volume.value = p.type === 'MembraneSynth' ? 0 : -8;
    inst.on = (n, v, time) => inner.triggerAttack(midiNote(n), time, v);
    inst.off = (n, time) => inner.triggerRelease(midiNote(n), time);
    inst.hit = (n, v, time, dur) => inner.triggerAttackRelease(midiNote(n), dur, time, v);
    inst.bend = semis => inner.set({ detune: semis * 100 });
    inst.releaseAll = time => inner.releaseAll(time);
  } else if (kind === 'sing') {
    // a buzzy voice through three vowel formant filters: each note sings the next vowel (oo, la, lo, ee...)
    const shift = { bunny: 1.18, koala: 0.95, frog: 0.8 }[name] || 1;
    inner = new Tone.PolySynth(Tone.Synth, { oscillator: { type: 'fatsawtooth', count: 2, spread: 10 }, envelope: { attack: 0.05, decay: 0.2, sustain: 0.7, release: 0.35 } });
    inner.volume.value = -6;
    const vib = new Tone.Vibrato({ frequency: name === 'frog' ? 7 : 5.5, depth: name === 'frog' ? 0.25 : 0.12 });
    const sum = new Tone.Gain(1.6).connect(out), fs = [new Tone.Filter(700 * shift, 'bandpass'), new Tone.Filter(1200 * shift, 'bandpass'), new Tone.Filter(2600 * shift, 'bandpass')];
    fs.forEach((f, i) => { f.Q.value = 6 + i * 2; vib.connect(f); f.connect(sum); });
    inner.connect(vib); extra.push(vib, sum, ...fs);
    const VOWELS = [[300, 870, 2240], [730, 1090, 2440], [570, 840, 2410], [270, 2290, 3010], [530, 1840, 2480]];
    let k = 0;
    const vowel = time => { const v = VOWELS[k++ % VOWELS.length]; fs.forEach((f, i) => f.frequency.setValueAtTime(v[i] * shift, time ?? Tone.immediate())); };
    inst.on = (n, v, time) => { vowel(time); inner.triggerAttack(midiNote(n), time, v); };
    inst.off = (n, time) => inner.triggerRelease(midiNote(n), time);
    inst.hit = (n, v, time, dur) => { vowel(time); inner.triggerAttackRelease(midiNote(n), dur, time, v); };
    inst.bend = semis => inner.set({ detune: semis * 100 });
    inst.releaseAll = time => inner.releaseAll(time);
  } else if (kind === 'kit') {
    inst.drum = true;
    const kit = makeKit(name, out, api, track);
    inst.ready = kit.ready; extra.push(kit);
    inst.on = (n, v, time) => kit.hit(n - PAD_BASE, v, time ?? Tone.immediate());
    inst.hit = (n, v, time) => kit.hit(n - PAD_BASE, v, time);
  }
  return inst;
}
export const noteLabel = (inst, n) => (String(inst).startsWith('kit:') ? PADS[n - PAD_BASE] || noteName(n) : noteName(n));

// ---------------------------------------------------------------- drum kits made from synth voices
const KIT_TUNE = {
  '808': { kick: [45, 0.08, 6, 0.9], snare: [3200, 0.18], hat: [7000, 0.04], tone: 1, crush: 0 },
  '909': { kick: [55, 0.03, 5, 0.45], snare: [4500, 0.14], hat: [9000, 0.03], tone: 1.15, crush: 0 },
  lofi: { kick: [50, 0.05, 4, 0.5], snare: [2200, 0.16], hat: [5000, 0.035], tone: 0.9, crush: 6 },
  chip: { kick: [70, 0.02, 3, 0.25], snare: [3000, 0.08], hat: [8000, 0.02], tone: 1.3, crush: 4 },
  acoustic: { kick: [60, 0.04, 3, 0.35], snare: [1800, 0.22], hat: [8500, 0.06], tone: 1, crush: 0 },
  doodle: { kick: [52, 0.05, 5, 0.4], snare: [2800, 0.15], hat: [7500, 0.04], tone: 1.1, crush: 0 },
};
function makeKit(name, out, api, track) {
  const Tone = T(), k = KIT_TUNE[name] || KIT_TUNE['808'], nodes = [];
  const bus = k.crush ? new Tone.BitCrusher(k.crush) : new Tone.Gain(1); bus.connect(out); nodes.push(bus);
  const mk = n => { nodes.push(n); n.connect(bus); return n; };
  const kick = mk(new Tone.MembraneSynth({ pitchDecay: k.kick[1], octaves: k.kick[2], envelope: { attack: 0.001, decay: k.kick[3], sustain: 0, release: 0.1 } }));
  const tom = mk(new Tone.MembraneSynth({ pitchDecay: 0.05, octaves: 2, envelope: { attack: 0.001, decay: 0.35, sustain: 0, release: 0.1 } }));
  const snF = mk(new Tone.Filter(k.snare[0], 'bandpass')); snF.Q.value = 0.8;
  const snN = new Tone.NoiseSynth({ noise: { type: 'white' }, envelope: { attack: 0.001, decay: k.snare[1], sustain: 0 } }).connect(snF); nodes.push(snN);
  const snB = mk(new Tone.MembraneSynth({ pitchDecay: 0.01, octaves: 1, envelope: { attack: 0.001, decay: 0.1, sustain: 0 } }));
  const hatF = mk(new Tone.Filter(k.hat[0], 'highpass'));
  const hat = new Tone.NoiseSynth({ noise: { type: 'white' }, envelope: { attack: 0.001, decay: k.hat[1], sustain: 0 } }).connect(hatF); nodes.push(hat);
  const ohat = new Tone.NoiseSynth({ noise: { type: 'white' }, envelope: { attack: 0.001, decay: 0.35, sustain: 0 } }).connect(hatF); nodes.push(ohat);
  const metal = mk(new Tone.MetalSynth({ envelope: { attack: 0.001, decay: 1.2, release: 0.4 }, harmonicity: 5.1, modulationIndex: 32, resonance: 4000, octaves: 1.5 }));
  metal.volume.value = -14;
  const bell = mk(new Tone.MetalSynth({ envelope: { attack: 0.001, decay: 0.3, release: 0.1 }, harmonicity: 1.4, modulationIndex: 4, resonance: 800, octaves: 0.5 }));
  bell.volume.value = -10;
  const clapF = mk(new Tone.Filter(1500, 'bandpass')); clapF.Q.value = 1.2;
  const clap = new Tone.NoiseSynth({ noise: { type: 'pink' }, envelope: { attack: 0.001, decay: 0.03, sustain: 0 } }).connect(clapF); nodes.push(clap);
  const fx = mk(new Tone.Synth({ oscillator: { type: 'sine' }, envelope: { attack: 0.002, decay: 0.3, sustain: 0, release: 0.1 } }));
  const whF = mk(new Tone.Filter(400, 'bandpass')); whF.Q.value = 2;
  const wh = new Tone.NoiseSynth({ noise: { type: 'pink' }, envelope: { attack: 0.15, decay: 0.3, sustain: 0 } }).connect(whF); nodes.push(wh);
  let user = {}, players = [];
  const ready = (async () => {
    if (name !== 'user') return;
    for (const [pad, path] of Object.entries(track?.samples || {})) { try { const p = new Tone.Player(await fileBuffer(api, path)).connect(bus); players.push(p); user[pad] = p; } catch {} }
  })();
  const t = k.tone;
  const hit = (i, v, time) => {
    if (name === 'user') { const p = user[i]; if (p) { p.volume.value = Tone.gainToDb(Math.max(0.05, v)); p.start(time); } return; }
    switch (i) {
      case 0: kick.triggerAttackRelease(k.kick[0] * t, '8n', time, v); break;
      case 1: snN.triggerAttackRelease(k.snare[1], time, v); snB.triggerAttackRelease(180 * t, '16n', time, v * 0.6); break;
      case 2: [0, 0.012, 0.025].forEach(d => clap.triggerAttackRelease(0.03, time + d, v)); break;
      case 3: hat.triggerAttackRelease(k.hat[1], time, v * 0.7); break;
      case 4: ohat.triggerAttackRelease(0.3, time, v * 0.6); break;
      case 5: tom.triggerAttackRelease(90 * t, '8n', time, v); break;
      case 6: tom.triggerAttackRelease(160 * t, '8n', time, v); break;
      case 7: metal.triggerAttackRelease(300, 1.2, time, v); break;
      case 8: bell.triggerAttackRelease(1800 * t, 0.05, time, v); break;
      case 9: hat.triggerAttackRelease(0.06, time, v * 0.4); break;
      case 10: bell.triggerAttackRelease(560 * t, 0.15, time, v); break;
      case 11: metal.triggerAttackRelease(500, 0.6, time, v * 0.6); break;
      case 12: fx.triggerAttack(220, time, v); fx.frequency.setValueAtTime(220, time); fx.frequency.exponentialRampToValueAtTime(880, time + 0.12); fx.frequency.exponentialRampToValueAtTime(330, time + 0.3); fx.triggerRelease(time + 0.32); break; // boing
      case 13: fx.triggerAttack(1400, time, v); fx.frequency.setValueAtTime(1400, time); fx.frequency.exponentialRampToValueAtTime(500, time + 0.05); fx.triggerRelease(time + 0.06); break;     // pop
      case 14: whF.frequency.setValueAtTime(300, time); whF.frequency.exponentialRampToValueAtTime(3000, time + 0.4); wh.triggerAttackRelease(0.4, time, v); break;                        // whoosh
      case 15: kick.triggerAttackRelease(38, '8n', time, v); snN.triggerAttackRelease(0.05, time, v * 0.4); break;                                                                         // thud
    }
  };
  return { hit, ready, dispose() { for (const n of [...nodes, ...players]) try { n.dispose(); } catch {} } };
}

// ---------------------------------------------------------------- effects (per track and on the master)
export const FX = {
  reverb: ['Reverb', () => new (T().Reverb)({ decay: 2.5, wet: 0.3 }), { decay: [0.2, 10, 'Room size'], wet: [0, 1, 'Amount'] }],
  delay: ['Echo', () => new (T().FeedbackDelay)({ delayTime: '8n', feedback: 0.35, wet: 0.25 }), { feedback: [0, 0.9, 'Repeats'], wet: [0, 1, 'Amount'] }],
  pingpong: ['Ping-pong echo', () => new (T().PingPongDelay)({ delayTime: '8n', feedback: 0.3, wet: 0.25 }), { feedback: [0, 0.9, 'Repeats'], wet: [0, 1, 'Amount'] }],
  chorus: ['Chorus', () => new (T().Chorus)({ frequency: 1.5, delayTime: 3.5, depth: 0.6, wet: 0.5 }).start(), { depth: [0, 1, 'Depth'], wet: [0, 1, 'Amount'] }],
  phaser: ['Phaser', () => new (T().Phaser)({ frequency: 0.5, octaves: 3, baseFrequency: 400, wet: 0.5 }), { frequency: [0.05, 8, 'Speed'], wet: [0, 1, 'Amount'] }],
  filter: ['Filter sweep', () => new (T().AutoFilter)({ frequency: '2n', depth: 0.8, baseFrequency: 200, octaves: 4, wet: 1 }).start(), { depth: [0, 1, 'Depth'], baseFrequency: [40, 4000, 'Low point'] }],
  lowpass: ['Low-pass (muffle)', () => new (T().Filter)(18000, 'lowpass'), { frequency: [80, 18000, 'Cutoff'], Q: [0.1, 12, 'Resonance'] }],
  highpass: ['High-pass (thin)', () => new (T().Filter)(20, 'highpass'), { frequency: [20, 6000, 'Cutoff'], Q: [0.1, 12, 'Resonance'] }],
  wah: ['Auto-wah', () => new (T().AutoWah)({ baseFrequency: 150, octaves: 5, sensitivity: -20, wet: 0.8 }), { octaves: [1, 8, 'Range'], wet: [0, 1, 'Amount'] }],
  distortion: ['Distortion', () => new (T().Distortion)({ distortion: 0.4, wet: 0.6 }), { distortion: [0, 1, 'Drive'], wet: [0, 1, 'Amount'] }],
  crusher: ['Bit crusher (8-bit)', () => new (T().BitCrusher)(6), { bits: [1, 16, 'Bits'], wet: [0, 1, 'Amount'] }],
  tremolo: ['Tremolo', () => new (T().Tremolo)({ frequency: 6, depth: 0.6 }).start(), { frequency: [0.5, 20, 'Speed'], depth: [0, 1, 'Depth'] }],
  vibrato: ['Vibrato', () => new (T().Vibrato)({ frequency: 5, depth: 0.15 }), { frequency: [0.5, 12, 'Speed'], depth: [0, 1, 'Depth'] }],
  pitch: ['Pitch shift', () => new (T().PitchShift)({ pitch: 12, wet: 1 }), { pitch: [-24, 24, 'Semitones'], wet: [0, 1, 'Amount'] }],
  wide: ['Stereo widener', () => new (T().StereoWidener)(0.7), { width: [0, 1, 'Width'] }],
  eq: ['EQ', () => new (T().EQ3)({ low: 0, mid: 0, high: 0 }), { low: [-24, 12, 'Low'], mid: [-24, 12, 'Mid'], high: [-24, 12, 'High'] }],
  compressor: ['Compressor', () => new (T().Compressor)({ threshold: -20, ratio: 4 }), { threshold: [-60, 0, 'Threshold'], ratio: [1, 20, 'Ratio'] }],
  pump: ['Pump (sidechain feel)', () => { const g = new (T().Gain)(1), l = new (T().LFO)({ frequency: '4n', min: 0.25, max: 1, type: 'sawtooth' }).start(); l.connect(g.gain); g._lfo = l; return g; }, { }],
  limiter: ['Limiter', () => new (T().Limiter)(-1), { threshold: [-24, 0, 'Ceiling'] }],
};
export function makeFx(f) {
  const def = FX[f.type]; if (!def) return null;
  const node = def[1]();
  for (const [k, v] of Object.entries(f.p || {})) setFx(node, k, v);
  return node;
}
export function setFx(node, k, v) {
  try {
    const p = node[k];
    if (p && typeof p === 'object' && 'value' in p) p.value = v;
    else node[k] = v;
  } catch {}
}
