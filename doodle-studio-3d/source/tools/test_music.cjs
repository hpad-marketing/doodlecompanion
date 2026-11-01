// Music workspace: engine, MIDI routing, looper, mapping, puppet, animation tools, bounce and the MCP tool.
// node tools/test_music.cjs  (headless Chromium, dev server on 54193, a fake host)
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
const out = '/tmp/ds3d-music-test'; fs.rmSync(out, { recursive: true, force: true }); fs.mkdirSync(out, { recursive: true });
let fails = 0; const ok = (c, m) => { console.log((c ? 'ok   ' : 'FAIL ') + m); if (!c) fails++; };
(async () => {
  let page; const written = [];
  const api = {
    'render-status': async () => ({ state: 'idle' }), settings: async () => ({ rendersRoot: out }),
    'write-file': async ({ path: p, data }) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, Buffer.from(data, 'base64')); written.push(p); return { path: p }; },
    'read-audio': async ({ path: p }) => ({ data: fs.readFileSync(p).toString('base64') }),
    'music-sounds': async () => ({ sounds: {} }),
  };
  const mcp = require('../host/mcp.cjs')({ call: js => page.evaluate(`Promise.resolve(${js})`), api });
  await require('../host/server.cjs')({ root: path.join(__dirname, '..', 'app'), port: 54193, api, mcp });
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  page = await b.newPage({ viewport: { width: 1700, height: 1000 } });
  const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  await page.goto('http://127.0.0.1:54193/');
  await page.waitForSelector('body[data-ready="1"]', { timeout: 60000 });
  let id = 0;
  const rpc = async (method, params) => (await (await fetch('http://127.0.0.1:54193/mcp', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', id: ++id, method, params }) })).json());
  const tool = async (name, args) => { const r = await rpc('tools/call', { name, arguments: args }); if (r.result.isError) throw Error(r.result.content[0].text); return JSON.parse(r.result.content[0].text); };
  const names = (await rpc('tools/list')).result.tools.map(t => t.name);
  ok(names.includes('music') && names.includes('get_state') && names.includes('babble') && names.includes('set_values'), `MCP lists music and the old tools (${names.length} tools)`);

  // the Music tab opens with the studio
  await page.click('#tabs button:has-text("Music")');
  await page.waitForSelector('#mus-root');
  ok(await page.$('.mus-transport') && await page.$('#mus-roll, #mus-steps'), 'Music workspace shows the transport and an editor');
  await page.screenshot({ path: path.join(out, 'studio.png') });
  ok(await page.evaluate(() => !!window.Tone && !!window.Midi), 'Tone.js and @tonejs/midi load');

  // MCP: build a song
  let s = await tool('music', { action: 'set', bpm: 120, key: 'D', scale: 'minor' });
  ok(s.bpm === 120 && s.key === 'D' && s.scale === 'minor', 'set tempo, key and scale');
  await tool('music', { action: 'drums', track: 'Drums', style: 'hiphop' });
  await tool('music', { action: 'progression', track: 'Keys', progression: 'sad', style: 'block' });
  await tool('music', { action: 'add_track', name: 'Lead', sound: 'syn:lead' });
  const n = await tool('music', { action: 'add_notes', track: 'Lead', notes: [{ t: 0, d: 1, note: 'D5' }, { t: 1, d: 1, note: 'F5', v: 0.9 }, { t: 2, d: 2, note: 74 }] });
  ok(n.notes === 3, 'add_notes writes three notes');
  s = await tool('music', { action: 'song' });
  ok(s.tracks.length === 3 && s.tracks[0].notes['Loop A'] > 20 && s.tracks[1].notes['Loop A'] > 6, `song has 3 tracks with notes (${JSON.stringify(s.tracks.map(t => t.notes['Loop A']))})`);

  // live playing through MIDI: notes reach the engine with no transport running
  const live = await page.evaluate(async () => {
    const MI = await import('/src/music/midi.js'), E = await import('/src/music/engine.js');
    await E.start(); const got = []; window.ds3d.scene.song.sel = window.ds3d.scene.song.tracks[1].id;
    const off = E.on((w, x) => { if (w === 'note') got.push(x); });
    MI.inject([0x90, 60, 100]); MI.inject([0x80, 60, 0]); MI.inject([0x99, 36, 120]); MI.inject([0x89, 36, 0]);
    await new Promise(r => setTimeout(r, 200)); off();
    return { list: got.map(g => g.n + (g.on ? '+' : '-')), got: got.length, started: E.engine.started, lat: E.latencyMs(), ctxState: window.Tone.getContext().state };
  });
  ok(live.started && live.got >= 3, JSON.stringify(live.list) + ' ' + `MIDI key and pad play at once (${live.got} note events, audio ${live.ctxState}, output latency ${live.lat} ms)`);

  // looper: record two passes, each pass is a layer; undo removes the last
  const loop = await page.evaluate(async () => {
    const MI = await import('/src/music/midi.js'), E = await import('/src/music/engine.js'), S = await import('/src/music/song.js');
    const s = window.ds3d.scene.song; s.bpm = 240; s.sections[0].bars = 1; E.sync(s);
    s.sel = s.tracks.find(t => t.name === 'Lead').id;
    const clip = () => s.tracks.find(t => t.name === 'Lead').clips[s.sections[0].id].notes;
    clip().length = 0;
    await E.record(true, { countIn: 0 });
    const wait = ms => new Promise(r => setTimeout(r, ms));
    await wait(150); MI.inject([0x90, 62, 90]); await wait(80); MI.inject([0x80, 62, 0]);
    await wait(1100);                                   // next pass (1 bar at 240 BPM = 1 s)
    MI.inject([0x90, 65, 90]); await wait(80); MI.inject([0x80, 65, 0]);
    await wait(300); await E.record(false); E.stop();
    const takes = [...new Set(clip().map(n => n.take))];
    const before = clip().length; const removed = E.undoTake(s.tracks.find(t => t.name === 'Lead'), s.sections[0]);
    return { before, takes: takes.length, removed, after: clip().length };
  });
  ok(loop.before === 2 && loop.takes === 2 && loop.removed === 1 && loop.after === 1, `looper: 2 passes = 2 layers, undo layer removes one (${JSON.stringify(loop)})`);

  // capture with Record off
  const cap = await page.evaluate(async () => {
    const MI = await import('/src/music/midi.js'), E = await import('/src/music/engine.js');
    const s = window.ds3d.scene.song, t = s.tracks.find(x => x.name === 'Lead'), c = t.clips[s.sections[0].id];
    const wait = ms => new Promise(r => setTimeout(r, ms)); await wait(2800); const before = c.notes.length;
    for (const k of [67, 69, 71]) { MI.inject([0x90, k, 90]); await wait(60); MI.inject([0x80, k, 0]); await wait(60); }
    return { got: E.capture(t), before, after: c.notes.length };
  });
  ok(cap.got === 3 && cap.after === cap.before + 3, 'Capture keeps what was just played ' + JSON.stringify(cap));

  // helpers: scale lock + chords
  const hp = await page.evaluate(async () => {
    const E = await import('/src/music/engine.js'); const h = E.engine.helpers, was = { ...h };
    h.scaleLock = true; h.chord = 'triad'; const r = E.expand(61); Object.assign(h, was); return r;
  });
  ok(JSON.stringify(hp) === JSON.stringify([60, 64, 67]), `scale lock + chord in D minor: C# snaps to C, C chord = C E G → ${JSON.stringify(hp)}`);

  // mapping: learn a knob onto the metronome, then use it
  const map = await page.evaluate(async () => {
    const MI = await import('/src/music/midi.js'), E = await import('/src/music/engine.js');
    MI.learn('act:music.metronome'); MI.inject([0xb0, 20, 127]);
    const rule = MI.midi.map.rules.find(r => r.src === 'cc:0:20');
    const m0 = E.engine.metro; MI.inject([0xb0, 20, 0]); MI.inject([0xb0, 20, 127]);
    // a key mapped to a pad sound
    MI.learn('pad:2'); MI.inject([0x90, 84, 100]); MI.inject([0x80, 84, 0]);
    const keyRule = MI.midi.map.rules.find(r => r.src === 'note:0:84');
    const res = { rule: rule?.target, toggled: E.engine.metro !== m0, keyRule: keyRule?.target };
    MI.midi.map.rules = []; MI.saveMap(); E.engine.metro = false;
    return res;
  });
  ok(map.rule === 'act:music.metronome' && map.toggled && map.keyRule === 'pad:2', `Learn maps a knob to an action and a key to a pad (${JSON.stringify(map)})`);

  // knobs drive Bunny controls; puppet keys open the mouth
  const pup = await page.evaluate(async () => {
    const MI = await import('/src/music/midi.js');
    const m = MI.midi.map; m.knobTargets[7] = 'ctl:headYaw';
    MI.inject([0xb0, m.knobs[7], 127]);
    const yaw = window.ds3d.state().values.headYaw;
    m.puppet = true; MI.inject([0x90, 60, 127]);
    const mouthOpen = window.ds3d.state().values.mouth; MI.inject([0x80, 60, 0]);
    const mouthRest = window.ds3d.state().values.mouth; m.puppet = false; MI.saveMap();
    return { yaw, mouthOpen, mouthRest };
  });
  ok(pup.yaw > 10 && pup.mouthOpen === 2 && pup.mouthRest === 1, `knob turns the head, puppet keys open/close the mouth (${JSON.stringify(pup)})`);

  // music drives animation keys
  await tool('music', { action: 'set', bpm: 120 });
  const bm = await tool('music', { action: 'beat_moves', track: 'Drums', pad: 0, moves: ['nod', 'ears'], scope: 'shot' });
  ok(bm.keys > 0 && bm.hits > 0, `beat moves keyed (${bm.hits} kicks, ${bm.keys} keys)`);
  const sg = await tool('music', { action: 'sing', track: 'Lead' });
  ok(sg.keys > 0, `singing mouth keyed (${sg.keys})`);
  const st = await tool('get_state', {});
  ok(st.keyed.headNod?.length > 2 && st.keyed.mouth?.length > 1, 'keys are on the shot (headNod, mouth)');

  // bounce to the music bed, MIDI out, stems
  const bo = await tool('music', { action: 'bounce' });
  const wav = fs.readFileSync(bo.path);
  ok(wav.slice(0, 4).toString() === 'RIFF' && wav.length > 100000, `bounce wrote a WAV (${(wav.length / 1e6).toFixed(1)} MB, ${bo.seconds} s)`);
  // the WAV is not silent
  let peak = 0; for (let i = 44; i < wav.length; i += 2) peak = Math.max(peak, Math.abs(wav.readInt16LE(i)));
  ok(peak > 1000, `bounced audio has sound (peak ${peak})`);
  const bed = await page.evaluate(() => window.ds3d.scene.music);
  ok(bed?.fromSong && bed.path === bo.path, 'the bounce is the scene\'s music bed');
  const mid = await tool('music', { action: 'export_midi' });
  ok(fs.readFileSync(mid.path).slice(0, 4).toString() === 'MThd', 'MIDI export writes a .mid');
  const back = await page.evaluate(async p => { const MF = await import('/src/music/midifile.js'), S = await import('/src/music/song.js'); await MF.loadGmNames(); const s2 = S.newSong(); s2.tracks = []; return MF.importMidi(s2, Uint8Array.from(atob(p), c => c.charCodeAt(0))); }, fs.readFileSync(mid.path).toString('base64'));
  ok(back.tracks.length === 3, `MIDI import reads it back (${back.tracks.join(', ')})`);

  // every view renders
  for (const v of ['Mixer & effects', 'Sounds', 'MiniLab & mapping', 'Music → animation', 'Bounce & files', 'Studio']) {
    await page.click(`#subtabs button:has-text("${v}")`); await page.waitForTimeout(150);
    await page.screenshot({ path: path.join(out, v.replace(/\W+/g, '_') + '.png') });
  }
  ok(await page.$('#mus-root'), 'all six music views render');
  // a real instrument loads and the timeline shows the song
  const gm = await page.evaluate(async () => { const I = await import('/src/music/instruments.js'); await I.loadCatalog(async () => ({ sounds: {} })); const x = I.makeInstrument('gm:acoustic_grand_piano'); await x.ready; await window.Tone.loaded(); x.dispose(); return I.catalog().length; });
  ok(gm > 150, `grand piano samples load; ${gm} sounds in the browser`);
  ok(!!(await page.$('#tracks .song-block')), 'the animation timeline shows a Song row');
  // Space plays the animation and the song follows it
  await page.click('#tracks .ruler'); await page.keyboard.press('Escape');
  await page.evaluate(() => document.activeElement?.blur());
  await page.keyboard.press('Space'); await page.waitForTimeout(400);
  const fol = await page.evaluate(async () => { const E = await import('/src/music/engine.js'); return { playing: E.engine.playing, follow: E.engine.follow, loop: E.engine.loop }; });
  await page.keyboard.press('Space'); await page.waitForTimeout(200);
  const after = await page.evaluate(async () => (await import('/src/music/engine.js')).engine.playing);
  ok(fol.playing && fol.follow && !fol.loop && !after, `Space plays the song with the animation and stops it (${JSON.stringify(fol)}, after ${after})`);
  // big studio fills the window
  await page.click('#tabs button:has-text("Music")'); await page.click('button:has-text("Big studio")'); await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(out, 'big-studio.png') });
  const big = await page.evaluate(() => document.getElementById('dock-tools').getBoundingClientRect().width);
  ok(big > 1600, `Big studio fills the window (${Math.round(big)} px)`);
  await page.keyboard.press('Escape');
  const keep = errors.filter(e => !/favicon|404|ERR_|WebGL|MIDI/i.test(e));
  ok(!keep.length, 'no page errors' + (keep.length ? ': ' + keep.slice(0, 3).join(' | ') : ''));
  await b.close();
  console.log(fails ? `${fails} FAILED` : 'all music checks passed');
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
