// Ripple delete on the scene voice: drag across the Voice row, press Delete, and the stretch is
// cut out with the gap closed. Keys, markers, items, captions, Babble lines and transcript words
// after it slide left, the shot gets shorter, the voice file gets shorter, and Ctrl+Z puts it all
// back. Shift+Delete leaves silence and moves nothing. Run: node tools/test_ripple.cjs
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54396, wav = path.join(__dirname, '..', 'devout', 'ripple.wav');
fs.mkdirSync(path.dirname(wav), { recursive: true });
{ // four seconds: loud tone, a second of silence, loud tone (24 fps -> 96 frames)
  const sr = 44100, n = sr * 4, b = Buffer.alloc(44 + n * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + n * 2, 4); b.write('WAVEfmt ', 8); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(sr, 24); b.writeUInt32LE(sr * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) { const t = i / sr; b.writeInt16LE(t >= 1.5 && t < 2.5 ? 0 : Math.round(12000 * Math.sin(i * 0.05)), 44 + i * 2); }
  fs.writeFileSync(wav, b);
}
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  // the pure part first: everything timed in the shot moves with the cut
  const RP = await import(path.join(__dirname, '..', 'app', 'src', 'ripple.js'));
  const sc = { fps: 24, active: 0, shots: [{ uid: 'a', code: 'sh010', length: 96, tracks: { armL: [{ f: 0, v: 0 }, { f: 40, v: 50 }, { f: 80, v: 90 }], expression: [{ f: 0, v: 1 }, { f: 44, v: 3 }] }, markers: [{ f: 70, note: 'beat' }, { f: 40, note: 'gone' }], items: [{ id: 'x', frame: 60 }] }, { uid: 'b', code: 'sh020', length: 24, tracks: {} }],
    babble: [{ shot: 'a', f: 70, say: 'hi' }, { shot: 'a', f: 40, say: 'cut' }, { shot: 'b', f: 5, say: 'later' }],
    captions: { active: 'en', tracks: { en: [{ shot: 'a', f: 30, to: 50, text: 'spans' }, { shot: 'a', f: 60, to: 80, text: 'after' }, { shot: 'b', f: 1, to: 10, text: 'other shot' }], hi: [] } },
    transcript: { text: '', words: [{ text: 'one', t0: 0.5, t1: 1 }, { text: 'two', t0: 1.6, t1: 1.9 }, { text: 'three', t0: 3, t1: 3.4 }] } };
  const r = RP.rippleShot(sc, 0, 36, 60);
  const s0 = sc.shots[0];
  ok(r.frames === 24 && s0.length === 72 && sc.shots[1].length === 24, 'the shot loses the 24 cut frames, the next shot keeps its length');
  ok(JSON.stringify(s0.tracks.armL.map(k => [k.f, k.v])) === '[[0,0],[36,70],[56,90]]', 'keys after the cut slide left, the pose at the cut end is kept: ' + JSON.stringify(s0.tracks.armL.map(k => [k.f, k.v])));
  ok(s0.tracks.expression.some(k => k.f === 36 && k.v === 3), 'a face held across the cut stays the same after it');
  ok(s0.markers.length === 1 && s0.markers[0].f === 46 && s0.items[0].frame === 36, 'markers inside are removed, later ones and items move');
  ok(sc.babble.length === 2 && sc.babble[0].f === 46 && sc.babble[1].f === 5, 'Babble lines move with their shot only');
  const en = sc.captions.tracks.en;
  ok(en[0].f === 30 && en[0].to === 36 && en[1].f === 36 && en[1].to === 56 && en[2].f === 1, 'captions are trimmed and moved: ' + JSON.stringify(en));
  ok(sc.transcript.words.length === 2 && sc.transcript.words[1].t0 === 2 && sc.transcript.text === 'one three', 'transcript words in the cut go, later ones move up a second');
  let threw = false; try { RP.rippleShot(sc, 0, 0, 72); } catch { threw = true; }
  ok(threw, 'cutting a whole shot is refused');
  const ch = RP.cutSamples([new Float32Array(1000).fill(1)], 1000, 0.2, 0.5, true);
  ok(ch[0].length === 700, 'samples: ripple removes 0.3 s');
  const li = RP.cutSamples([new Float32Array(1000).fill(1)], 1000, 0.2, 0.5, false);
  ok(li[0].length === 1000 && li[0][300] === 0 && li[0][100] === 1, 'samples: lift silences and keeps the length');

  // the real editor
  await new Promise(r => setTimeout(r, 900));
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1032 } })).newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 90000 });
  await p.evaluate(f => ds3d.importAudio(f), wav);
  await p.waitForSelector('#tracks .trow.audio canvas.wave', { timeout: 8000 });
  await p.evaluate(() => { ds3d.setValues({ armL: 10 }, 0, true); ds3d.setValues({ armL: 60 }, 80, true); ds3d.addMarker(84, 'after'); });
  const st0 = await p.evaluate(() => ds3d.state());
  const len0 = st0.shots[st0.shots.findIndex(s => s.active)].length;
  // drag across 1.5 s .. 2.5 s on the Voice row
  const lane = p.locator('#tracks .trow.audio .voice-lane').first();
  const box = await lane.boundingBox(), ppf = (await lane.evaluate(el => el.querySelector('canvas.wave').width)) / len0;
  await p.mouse.move(box.x + 36 * ppf + 0.5, box.y + 20); await p.mouse.down(); await p.mouse.move(box.x + 50 * ppf, box.y + 20, { steps: 4 }); await p.mouse.move(box.x + 60 * ppf + 0.5, box.y + 20, { steps: 4 }); await p.mouse.up();
  ok(await p.locator('#tracks .audio-sel').count() === 1, 'dragging across the voice shows a selection');
  await p.keyboard.press('Delete');
  await p.waitForFunction(n => ds3d.state().shots.find(s => s.active).length === n - 24, len0, { timeout: 15000 }).catch(() => {});
  const st1 = await p.evaluate(() => ds3d.state());
  ok(st1.shots.find(s => s.active).length === len0 - 24, `Delete cuts 24 frames: shot ${len0} -> ${st1.shots.find(s => s.active).length}`);
  ok(st1.keyed.armL?.some(k => k[0] === 56 && k[1] === 60), 'the key at 80 is now at 56: ' + JSON.stringify(st1.keyed.armL));
  ok(st1.markers.some(m => m.f === 60), 'the marker at 84 is now at 60');
  const fps = await p.evaluate(() => ds3d.state().fps ?? 24);
  const dur = await p.evaluate(async () => { const r = await ds3d.audioCut({ from: 0, to: 0 }).catch(e => e.message); return r; });
  ok(typeof dur === 'string' && /Select part/.test(dur), 'a cut with nothing selected says what to do');
  const wavs = fs.readdirSync(path.join(__dirname, '..', 'devout'), { recursive: true }).filter(f => /_edit_.*\.wav$/.test(f));
  const made = wavs.map(f => path.join(__dirname, '..', 'devout', f)).sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
  ok(made && Math.abs(fs.statSync(made).size - 44 - Math.round((4 - 24 / fps) * 44100) * 2) < 2000, `the voice file is ${(24 / fps).toFixed(2)} s shorter: ` + (made && fs.statSync(made).size));
  await p.keyboard.press('Control+z');
  await p.waitForTimeout(600);
  const st2 = await p.evaluate(() => ds3d.state());
  ok(st2.shots.find(s => s.active).length === len0 && st2.keyed.armL?.some(k => k[0] === 80), 'Ctrl+Z brings the cut back');
  // Shift+Delete: silence, nothing moves
  await p.mouse.move(box.x + 10 * ppf + 0.5, box.y + 20); await p.mouse.down(); await p.mouse.move(box.x + 20 * ppf + 0.5, box.y + 20, { steps: 4 }); await p.mouse.up();
  await p.keyboard.press('Shift+Delete');
  await p.waitForTimeout(1500);
  const st3 = await p.evaluate(() => ds3d.state());
  ok(st3.shots.find(s => s.active).length === len0 && st3.keyed.armL?.some(k => k[0] === 80), 'Shift+Delete leaves silence and moves nothing');
  // MCP route
  const r2 = await p.evaluate(() => ds3d.audioCut({ from: 12, to: 24 }));
  ok(r2.frames === 12 && r2.ripple === true, 'ds3d.audioCut (the MCP audio action cut) ripples by frames');
  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e.message); dev.kill(); process.exit(1); });
