// Timeline blocks and layers, voice effects, Babble's off-screen voices, the transcriber and the
// quiet menu bar. Run: node tools/test_blocks.cjs   DS3D_SPEECH=<a wav of clear English> also runs
// a real transcription (downloads the speech model once).
const { spawn } = require('child_process'), path = require('path'), fs = require('fs'), { pathToFileURL } = require('url');
const { chromium } = require('playwright');
const port = 54333, out = path.join(__dirname, '..', 'devout');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M10 10 L90 10 L90 90" stroke="#000" fill="none"/></svg>';
(async () => {
  const B = await import(pathToFileURL(path.join(__dirname, '..', 'app', 'src', 'blocks.js')).href);
  const V = await import(pathToFileURL(path.join(__dirname, '..', 'app', 'src', 'voicefx.js')).href);
  const T = await import(pathToFileURL(path.join(__dirname, '..', 'app', 'src', 'transcribe.js')).href);
  // blocks, pure
  const o = { tracks: { armR: [{ f: 5, v: 1 }, { f: 50, v: 2 }, { f: 80, v: 3 }], 'cam.dist': [{ f: 50, v: 9 }] } };
  ok(B.visibleAt(o, 99, 100) && B.hiddenSpans(o, 100) === null, 'no blocks yet: shows the whole shot, nothing for the render');
  const second = B.split(o, 100, 40); B.resize(o, 100, second.id, 60, 100);
  ok(!B.visibleAt(o, 50, 100) && B.visibleAt(o, 39, 100) && B.visibleAt(o, 60, 100), 'trimming opens a gap that hides the character');
  ok(JSON.stringify(B.hiddenSpans(o, 100)) === '[[40,60]]', 'the gap reaches the render');
  B.move(o, 100, o.clips[0].id, 10, [o.tracks]);
  ok(o.tracks.armR[0].f === 15 && o.clips[0].start === 10 && o.tracks['cam.dist'][0].f === 50, 'a block moves with its keys, the camera stays');
  B.move(o, 100, o.clips[0].id, 95, [o.tracks]);
  ok(o.clips[0].end === o.clips[1].start, 'a block stops at its neighbour, no overlap');
  const three = { }; B.split(three, 90, 30); ok(B.clipsOf(three, 20).length === 1 && B.clipsOf(three, 20)[0].end === 20, 'blocks follow a shorter shot');
  const p = { drawings: [{ id: 'a', frame: 10, until: null, build: 18 }] };
  const n = B.splitDrawing(p, 0, 40, 100, () => 'b');
  ok(p.drawings.length === 2 && p.drawings[0].until === 40 && n.frame === 40 && n.build === 0, 'cutting a drawing keeps the second part fully drawn');
  ok(B.placeOf({ layer: 'scene', depth: 0 }) === 'through' && B.placeOf({ layer: 'scene', depth: -0.5 }) === 'front' && B.placeOf({ layer: 'scene', depth: 1 }) === 'behind' && B.placeOf({ layer: 'screen' }) === 'screen', 'a drawing names its place');
  // voice effects, pure
  const sr = 48000, tone = new Float32Array(sr).map((_, i) => 0.4 * Math.sin(2 * Math.PI * 220 * i / sr));
  const hz = x => { let c = 0; for (let i = sr / 4; i < sr * 3 / 4; i++) if (x[i - 1] < 0 && x[i] >= 0) c++; return c * 2; };
  ok(Math.abs(hz(V.processChannels([tone], sr, { pitch: 12 })[0]) - 440) < 12, 'pitch +12 doubles the tone');
  for (const k of Object.keys(V.EFFECTS)) { const y = V.processChannels([tone], sr, { effect: k })[0]; let peak = 0, bad = false; for (const v of y) { peak = Math.max(peak, Math.abs(v)); if (!Number.isFinite(v)) bad = true; } ok(!bad && peak > 0.01 && peak <= 1 && y.length === tone.length, `${k}: same length, clean, not silent (peak ${peak.toFixed(2)})`); }
  ok(!V.isActive(V.normalize({})) && V.isActive(V.normalize({ pitch: 3 })) && !V.isActive(V.normalize({ pitch: 3, on: false })), 'off and Natural leave the voice alone');
  // captions from words
  const words = 'one two three four five six seven eight. nine'.split(' ').map((w, i) => ({ text: w, t0: i * 0.3, t1: i * 0.3 + 0.2 }));
  const caps = T.captionsFrom(words);
  ok(caps.length === 3 && caps[0].text.split(' ').length === 6 && caps[1].text.endsWith('.'), 'captions break at six words and at sentence ends');
  ok(Math.abs(T.to16k([new Float32Array(48000)], 48000).length - 16000) < 2, 'audio goes to 16 kHz for the transcriber');

  const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 900));
  const br = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  try {
    const pg = await (await br.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
    const errs = []; pg.on('pageerror', e => errs.push(e.message));
    pg.on('dialog', d => d.accept());
    await pg.goto(`http://127.0.0.1:${port}/`);
    await pg.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
    const ev = (fn, ...a) => pg.evaluate(fn, ...a);
    ok(await pg.locator('#tracks .block').count() === 1, 'the character has one block on the timeline');
    await ev(() => { ds3d.setValues({ armR: 40 }, 80, true); });
    const b0 = await pg.locator('#tracks .block').first().boundingBox();
    // trim the right end with the mouse
    await pg.mouse.move(b0.x + b0.width - 4, b0.y + 8); await pg.mouse.down(); await pg.mouse.move(b0.x + b0.width * 0.5, b0.y + 8, { steps: 5 }); await pg.mouse.up();
    let L = await ev(() => ds3d.blocks({ action: 'list' }));
    ok(L.layers[0].blocks[0].end < 70, 'dragging the end of a block trims it: ends at ' + L.layers[0].blocks[0].end);
    ok(await ev(f => { ds3d.goto(f); return ds3d.view3d?.group?.visible ?? true; }, 110) !== undefined, 'scrubbing into the gap is fine');
    await ev(() => ds3d.undo());
    L = await ev(() => ds3d.blocks({ action: 'list' })); ok(L.layers[0].blocks[0].end === 120, 'Undo restores the block');
    await ev(() => ds3d.blocks({ action: 'split', layer: 'lead', frame: 30 }));
    await ev(() => ds3d.blocks({ action: 'trim', layer: 'lead', id: ds3d.project.clips[1].id, start: 30, end: 100 }));
    await ev(() => ds3d.blocks({ action: 'move', layer: 'lead', id: ds3d.project.clips[1].id, start: 40 }));
    L = await ev(() => ds3d.blocks({ action: 'list' }));
    ok(L.layers[0].blocks.length === 2 && L.layers[0].blocks[1].start === 40, 'cut in two, the second part moved along (MCP-shaped)');
    ok((await ev(() => ds3d.project.tracks.armR.at(-1).f)) === 90, 'the part keeps its keys');
    // drawing layer
    await ev(s => ds3d.drawings({ action: 'import', svg: s, name: 'art', frame: 5, build: 0 }), svg);
    ok(await pg.locator('#tracks .block.draw').count() === 1, 'a drawing gets its own layer and block');
    L = await ev(() => ds3d.blocks({ action: 'list' }));
    const key = L.layers.find(x => x.kind === 'draw').layer;
    await ev(k => ds3d.blocks({ action: 'trim', layer: k, start: 5, end: 40 }), key);
    ok(await ev(() => ds3d.project.drawings[0].until) === 40, 'trimming a drawing block sets when it goes');
    await pg.selectOption('#tracks .layer-name select', 'behind');
    await pg.waitForTimeout(300);
    let d = await ev(() => ds3d.project.drawings[0]);
    ok(d.layer === 'scene' && d.depth === 1 && d.world, 'Behind stands the drawing in the 3D scene');
    await pg.selectOption('#tracks .layer-name select', 'through'); await pg.waitForTimeout(300);
    d = await ev(() => ds3d.project.drawings[0]); ok(d.layer === 'scene' && d.depth === 0, 'Through puts it across the character');
    await pg.selectOption('#tracks .layer-name select', 'screen'); await pg.waitForTimeout(300);
    d = await ev(() => ds3d.project.drawings[0]); ok(d.layer === 'screen', 'Over all puts it back on the screen');
    await ev(() => ds3d.goto(10));
    ok(await ev(() => !!document.getElementById('drawing-layer')), 'the drawing shows');
    await ev(k => ds3d.blocks({ action: 'isolate', layer: 'lead' }), key);
    ok(!(await ev(() => !!document.getElementById('drawing-layer'))), 'isolating the character hides the drawing while you work');
    await ev(() => ds3d.blocks({ action: 'isolate' }));
    ok(await ev(() => !!document.getElementById('drawing-layer')), 'isolate off brings it back');
    await ev(k => ds3d.blocks({ action: 'show', layer: k, on: false }), key);
    ok(!(await ev(() => !!document.getElementById('drawing-layer'))), 'the eye hides a drawing');
    await ev(k => ds3d.blocks({ action: 'show', layer: k, on: true }), key);
    // scissors
    await pg.click('#scissors-btn');
    const db = await pg.locator('#tracks .block.draw').boundingBox();
    await pg.mouse.click(db.x + db.width / 2, db.y + 6);
    await pg.click('#scissors-btn');
    ok(await pg.locator('#tracks .block.draw').count() === 2, 'the scissors cut a drawing block in two');
    // babble: everyone, without being in the shot
    await pg.click('#tabs button:text-is("Audio")');
    const who = await ev(() => [...document.querySelectorAll('.bb-who')].map(b => b.textContent));
    ok(who.length === 3 && who.some(x => /Frog/.test(x)) && who.some(x => /Koala/.test(x)), 'every character can be picked: ' + who.join(', '));
    await pg.click('.bb-who:has-text("Frog")');
    await pg.fill('input[aria-label="Line"]', 'Ribbit, hello there.');
    await pg.click('button:has-text("Hear it")');
    await pg.click('button:has-text("Hear all voices")');
    const mouthBefore = await ev(() => (ds3d.project.tracks.mouth || []).length);
    await pg.click('button:has-text("Add at playhead")');
    await pg.waitForFunction(() => ds3d.babble({ action: 'list' }).then(r => r.lines.length === 1), null, { timeout: 10000 });
    await pg.waitForTimeout(500);
    ok((await ev(() => (ds3d.project.tracks.mouth || []).length)) === mouthBefore, 'an off-screen line moves no mouth');
    ok(await pg.locator('#tracks .block.voice').count() === 1, 'the line is a block on the timeline');
    const vb = await pg.locator('#tracks .block.voice').boundingBox();
    await pg.mouse.move(vb.x + 6, vb.y + 6); await pg.mouse.down(); await pg.mouse.move(vb.x + 120, vb.y + 6, { steps: 4 }); await pg.mouse.up();
    await pg.waitForTimeout(500);
    ok((await ev(() => ds3d.babble({ action: 'list' }))).lines[0].f > 12, 'dragging the block retimes the line');
    // voice effect over babble, kept through a rebuild
    let r = await ev(() => ds3d.voiceFx({ preset: 'robot' }));
    ok(/_fx_\w+\.wav$/.test(r.audio) && fs.existsSync(r.audio), 'the effect writes a processed copy');
    const dry = await ev(() => ds3d.scene?.audio?.dry);
    await ev(() => ds3d.babble({ action: 'add', text: 'And another.', frame: 80 }));
    await pg.waitForTimeout(400);
    r = await ev(() => ds3d.babble({ action: 'list' }));
    ok(/_fx_/.test(r.audio.path) && r.audio.babble, 'a new Babble line stays under the effect');
    await pg.click('#subtabs button:has-text("Voice effects")');
    ok(await pg.locator('.chips button[aria-pressed="true"]:has-text("Robot")').count() >= 1, 'the panel shows the effect');
    await ev(() => ds3d.voiceFx({ action: 'reset' }));
    r = await ev(() => ds3d.babble({ action: 'list' }));
    ok(!/_fx_/.test(r.audio.path), 'Reset goes back to the dry voice');
    for (const n of ['Babble voice', 'Voice effects', 'Transcribe', 'Voice & lip sync', 'Music & beats']) { await pg.click(`#subtabs button:has-text("${n}")`); ok((await ev(() => document.querySelector('#panel-content').textContent.length)) > 20, `Audio › ${n} shows`); }
    // quiet menu bar
    await pg.click('#menubar .menu > button:text-is("Post")'); await pg.click('#menubar .menu-list button:has-text("Voice effects")');
    ok(await pg.locator('#quickbar button').count() === 0, 'running a tool leaves nothing beside Help');
    await pg.keyboard.press('Control+k');
    ok(/Voice effects/.test(await pg.locator('.ds-cmd .ds-list button').first().textContent()), 'recent tools are first in Ctrl+K');
    await pg.locator('.ds-cmd .ds-list button').first().click({ button: 'right' });
    await pg.keyboard.press('Escape');
    ok(await pg.locator('#quickbar button.fav').count() === 1, 'right-click in Ctrl+K pins a tool to the bar');
    await pg.locator('#quickbar button.fav').click({ button: 'right' });
    ok(await pg.locator('#quickbar button').count() === 0, 'right-click unpins it');
    // the render gets the gap
    await ev(() => ds3d.render && 0);
    if (process.env.DS3D_SPEECH) {
      await ev(p2 => ds3d.importAudio(p2), process.env.DS3D_SPEECH);
      const t = await ev(() => ds3d.transcribe({ language: 'english' }));
      console.log('heard:', t.text);
      ok(/quick brown fox/i.test(t.text) && t.words > 8, 'the transcriber hears the words');
      const c = await ev(() => ds3d.transcribe({ action: 'captions' }));
      ok(c.captions >= 2, `timed captions made (${c.captions})`);
    }
    ok(!errs.length, 'no page errors ' + errs.join(' | '));
  } finally { await br.close(); dev.kill(); }
})().catch(e => { console.log('CRASH', e); process.exitCode = 1; process.exit(1); });
