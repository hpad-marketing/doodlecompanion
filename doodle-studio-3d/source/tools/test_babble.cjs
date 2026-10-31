// Babble voice: typed lines spoken as synthesised gibberish. Checks the synth (deterministic,
// no clipping, per-character pitch, mouth on every syllable), the scene build (mix over a
// recorded voice, mouth keys only inside the line, captions tagged and replaced), then the app
// itself (Babble button, dialog, add/remove, Undo, voice dials, MCP-shaped ds3d.babble).
// Run: node tools/test_babble.cjs
const path = require('path'), fs = require('fs'), { spawn } = require('child_process');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  const B = await import(path.join(__dirname, '..', 'app', 'src', 'babble.js'));
  const S = await import(path.join(__dirname, '..', 'app', 'src', 'babblescene.js'));
  const line = 'Hi there! Did you see my new doodle? I drew it all by myself.';
  const a = B.speak(line, B.voiceFor('bunny')), b = B.speak(line, B.voiceFor('bunny'));
  ok(a.samples.length === b.samples.length && a.samples.every((x, i) => x === b.samples[i]), 'same line, same voice → identical sound');
  let peak = 0, nan = false; for (const x of a.samples) { peak = Math.max(peak, Math.abs(x)); if (!Number.isFinite(x)) nan = true; }
  ok(!nan && peak <= 0.9 && peak > 0.5, `no clipping or NaN (peak ${peak.toFixed(3)})`);
  // pitch: median autocorrelation f0 over loud 40 ms windows; Bunny > Frog > Koala
  const f0 = r => { const W = Math.round(r.sr * 0.04), out = []; for (let a = 0; a + W * 2 < r.samples.length; a += W) { let e = 0; for (let i = 0; i < W; i++) e += r.samples[a + i] ** 2; if (Math.sqrt(e / W) < 0.08) continue; let best = 0, lag = 0; for (let L = Math.floor(r.sr / 1000); L < r.sr / 90; L++) { let c = 0; for (let i = 0; i < W; i++) c += r.samples[a + i] * r.samples[a + i + L]; if (c > best) { best = c; lag = L; } } if (lag) out.push(r.sr / lag); } out.sort((x, y) => x - y); return out[out.length >> 1]; };
  const zb = f0(B.speak(line, B.voiceFor('bunny'), { style: 'tones' })), zk = f0(B.speak(line, B.voiceFor('koala'), { style: 'tones' })), zf = f0(B.speak(line, B.voiceFor('frog'), { style: 'tones' }));
  ok(zb > zf && zf > zk, `Bunny higher than Frog higher than Koala (median ${zb | 0} / ${zf | 0} / ${zk | 0} Hz)`);
  ok(B.speak(line, B.voiceFor('koala')).seconds > a.seconds, 'Koala speaks slower than Bunny');
  for (const st of ['syllables', 'letters', 'tones']) { const r = B.speak('Okay okay, listen!', B.voiceFor('frog'), { style: st }); ok(r.samples.length > 4800 && r.words.length === 3, `style ${st} renders`); }
  const vis = a.visemes(30), opens = vis.filter((m, i) => m !== B.VISEME.rest && vis[i - 1] !== m).length;
  ok(opens >= 12, `mouth changes on the syllables (${opens} changes)`);
  ok(vis[0] === B.VISEME.rest && vis[vis.length - 1] === B.VISEME.rest, 'mouth at rest before and after');
  const caps = B.captionChunks(a.words);
  ok(caps.length === 3 && caps.every(c => c.text.split(' ').length <= 6), 'captions: one per sentence, ≤ 6 words: ' + caps.map(c => c.text).join(' | '));
  ok(B.captionChunks(B.speak('one two three four five six seven eight nine ten eleven twelve thirteen', B.voiceFor('bunny')).words).length === 3, 'a 13-word sentence splits into 3 captions');
  ok(B.speak('Hmm?!', B.voiceFor('bunny')).samples.length > 0 && B.speak('42', B.voiceFor('frog')).words.length === 1, 'odd lines (Hmm?!, 42) still speak');
  const happy = B.voiceFor('bunny', {}, 'happy'), sad = B.voiceFor('bunny', {}, 'sad');
  ok(happy.pitch > 430 && sad.pitch < 430 && sad.speed < 1, 'moods bend pitch and speed');
  ok(B.voiceFor('koala', { pitch: 300 }).pitch === 300, 'dials override the character');

  // scene build
  const shot = (uid, len) => ({ uid, code: uid, length: len, fps: 30, tracks: { mouth: [{ f: 0, v: 1 }, { f: 5, v: 4 }, { f: 95, v: 3 }] } });
  const scene = { fps: 30, shots: [shot('s1', 120), shot('s2', 90)], captions: { active: 'en', tracks: { en: [{ shot: 's1', f: 100, to: 110, text: 'mine' }], hi: [] } } };
  scene.shots[1].costars = [{ character: 'frog', tracks: {} }];
  const setKey = (p, id, f, v, ease) => { const k = (p.tracks[id] ||= []); const e = k.find(x => x.f === f); if (e) e.v = v; else { k.push({ f, v, ease }); k.sort((x, y) => x.f - y.f); } };
  S.addLine(scene, scene.shots[0], 10, 'Hello friend!');
  S.addLine(scene, scene.shots[1], 0, 'Ribbit ribbit, hi.', { who: 0, mood: 'happy' });
  const base = [new Float32Array(48000 * 7).fill(0.1)];
  let r = S.build(scene, { leadChar: 'bunny', fps: 30, setKey, base, sr: 48000, captionTrack: scene.captions.tracks.en });
  ok(r.lines.length === 2 && r.lines[1].char === 'frog', 'co-star line uses the co-star\'s voice');
  ok(r.channels[0].length >= 48000 * 7 && Math.abs(r.channels[0][100] - 0.1) < 1e-6, 'recorded voice kept under the babble');
  const m1 = scene.shots[0].tracks.mouth;
  ok(m1.some(k => k.f === 0) && m1.some(k => k.f === 95 && k.v === 3) && !m1.some(k => k.f === 5 && k.v === 4) === false, 'keys outside the line stay (frames 0, 5, 95)');
  ok(m1.filter(k => k.f >= 10 && k.f < 60).length >= 4, 'lead mouth keyed inside the line');
  ok((scene.shots[1].costars[0].tracks.mouth || []).length >= 4 && !(scene.shots[1].tracks.mouth || []).some(k => k.f > 5 && k.f < 40 && k.v !== 1 && k.v !== 4 && k.v !== 3), 'co-star line keys the co-star mouth, not the lead');
  const n1 = scene.captions.tracks.en.length;
  ok(scene.captions.tracks.en.some(c => c.text === 'mine') && scene.captions.tracks.en.filter(c => c.babble).length === 2, 'babble captions added, the user caption kept');
  r = S.build(scene, { leadChar: 'bunny', fps: 30, setKey, base: null, sr: 48000, captionTrack: scene.captions.tracks.en });
  ok(scene.captions.tracks.en.length === n1 && r.channels.length === 1, 'rebuild replaces its own captions, no duplicates');
  const wavB64 = S.wavChannelsBase64(r.channels, r.sr);
  ok(Buffer.from(wavB64, 'base64').toString('ascii', 0, 4) === 'RIFF', 'writes a WAV');
  S.removeLine(scene, scene.babble[0].id);
  ok(scene.babble.length === 1, 'remove a line');

  // the app
  const port = 54317, dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
  const { chromium } = require('playwright');
  await new Promise(r => setTimeout(r, 900));
  const br = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  try {
    const p = await (await br.newContext({ viewport: { width: 1920, height: 1032 } })).newPage();
    const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    p.on('dialog', d => d.accept());
    await p.goto(`http://127.0.0.1:${port}/`);
    await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
    const ev = (fn, ...x) => p.evaluate(fn, ...x);
    const btn = p.locator('button', { hasText: /^\s*Babble$/ });
    ok(await btn.count() === 1, 'Babble button in the timeline Voice group');
    await btn.click();
    await p.waitForSelector('input[aria-label="Line"]');
    await p.fill('input[aria-label="Line"]', 'Hi there! Did you see my new doodle?');
    await p.click('button:has-text("Hear it")');
    await p.keyboard.press('Escape');
    await ev(() => ds3d.goto(12));
    await btn.click();
    await p.waitForSelector('button:has-text("Add at frame 12")', { timeout: 5000 });
    ok((await p.inputValue('input[aria-label="Line"]')) === 'Hi there! Did you see my new doodle?', 'typed line kept when the dialog reopens');
    await ev(() => { window.__toasts = []; new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => n.classList?.contains('toast') && __toasts.push(n.textContent)))).observe(document.body, { childList: true }); });
    await p.click('button:has-text("Add at frame 12")');
    await p.waitForFunction(() => ds3d.babble({ action: 'list' }).then(r => r.audio?.babble), null, { timeout: 15000 });
    const st = await ev(() => ds3d.babble({ action: 'list' }));
    ok(st.lines.length === 1 && st.lines[0].f === 12, 'line added at the playhead (frame 12)');
    ok(st.audio?.babble && /_babble_\w+\.wav$/.test(st.audio.path) && fs.existsSync(st.audio.path), 'voice file written: ' + (st.audio?.path || '').split(/[\\/]/).pop());
    const mouth = await ev(() => (ds3d.project.tracks.mouth || []).map(k => k.f));
    ok(mouth.filter(f => f >= 12).length >= 6, `mouth keyed on the line (${mouth.length} keys)`);
    const sl = await ev(() => __toasts.join(' / '));
    ok(/Babble: 1 line/.test(sl), 'toast reports the build: ' + sl);
    const r2 = await ev(() => ds3d.babble({ action: 'voice', character: 'bunny', pitch: 380, style: 'letters' }));
    ok(r2.voice.pitch === 380 && r2.voice.style === 'letters' && r2.audio !== st.audio.path, 'voice dials rebuild into a new file');
    const r3 = await ev(() => ds3d.babble({ action: 'add', text: 'Okay, bye!', frame: 70, mood: 'shocked' }));
    ok(r3.lines.length === 2, 'MCP-shaped add');
    const ids = (await ev(() => ds3d.babble({ action: 'list' }))).lines.map(l => l.id);
    await ev(id => ds3d.babble({ action: 'remove', id }), ids[1]);
    ok((await ev(() => ds3d.babble({ action: 'list' }))).lines.length === 1, 'remove');
    const c = await ev(() => ds3d.babble({ action: 'clear' }));
    ok(!c.audio, 'clearing every line removes the babble voice (no recorded voice → no scene audio)');
    let bad = await ev(() => ds3d.babble({ action: 'add', text: '   ' }).then(() => 'no error', e => e.message));
    ok(/Type the line/.test(bad), 'empty line refused: ' + bad);
    bad = await ev(() => ds3d.babble({ action: 'add', text: 'hi', who: 3 }).then(() => 'no error', e => e.message));
    ok(/co-star/.test(bad), 'unknown co-star refused: ' + bad);
    await p.screenshot({ path: path.join(__dirname, '..', 'devout', 'babble-ui.png') });
    // reopen the dialog for a screenshot with a line in it
    await ev(() => ds3d.babble({ action: 'add', text: 'Hello friend, nice day!', frame: 5, mood: 'happy' }));
    await p.keyboard.press('Escape').catch(() => {});
    await p.locator('button', { hasText: /^\s*Babble$/ }).click();
    await p.waitForTimeout(300);
    await p.screenshot({ path: path.join(__dirname, '..', 'devout', 'babble-dialog.png') });
    ok(!errs.filter(e => !/favicon|404|WebGL|GPU/i.test(e)).length, 'no page errors ' + errs.join(' | '));
  } finally { await br.close(); dev.kill(); }
})();
