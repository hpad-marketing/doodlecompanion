// Scene audio, waveform, audio-driven control, turntable, 3D headline item.
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54296, out = path.join(__dirname, '..', 'devout'), wav = path.join(out, 'beat.wav');
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.accept());
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  let r = await ev(w => ds3d.importAudio(w), wav);
  ok(r && Math.abs(r.seconds - 4) < 0.05, 'audio imported: ' + JSON.stringify(r));
  ok(await p.locator('#tracks canvas.wave').count() === 1, 'waveform row on the timeline');
  r = await ev(() => ds3d.audioDrive('bodyY', 0, 12, { step: 3 }));
  const st = await ev(() => ds3d.state());
  const k = Object.fromEntries(st.keyed.bodyY.map(x => [x[0], x[1]]));
  ok(k[6] > 10 && k[21] < 1 && k[33] > 10, `bodyY follows the beat (f6=${k[6]}, f21=${k[21]}, f33=${k[33]})`);
  await ev(() => ds3d.animTool({ action: 'turntable' }));
  const yaw = (await ev(() => ds3d.state())).keyed['cam.yaw'];
  ok(yaw.length === 2 && yaw[1][1] - yaw[0][1] === 360, 'turntable keys a full circle');
  r = await ev(() => ds3d.libraryUse('text:headline', { frame: 0, text: 'WAIT WHAT' }));
  ok(r.added.text === 'WAIT WHAT', '3D headline placed');
  // the scene render request carries the audio
  const req = await ev(() => new Promise(res => { const o = window.fetch; window.fetch = (u, x) => { if (String(u).includes('/api/render-scene')) { res(JSON.parse(x.body)); window.fetch = o; } return o(u, x); }; ds3d.renderScene({ preview: true }); }));
  ok(req.audio && req.audio.endsWith('beat.wav'), 'scene render gets the audio');
  // play starts and stops without errors
  await ev(() => document.querySelector('#play-btn').click()); await p.waitForTimeout(400); await ev(() => document.querySelector('#play-btn').click());
  // storytime: retention, chapters, loop back, gags
  await ev(() => { ds3d.setShot({ length: 600 }); });
  let rr = await ev(() => ds3d.story({ action: 'retention' }));
  ok(rr.lulls.length >= 1 && rr.lulls[0].seconds >= 4, 'retention check finds a 4 s lull: ' + JSON.stringify(rr.lulls[0]));
  await ev(() => { ds3d.addMarker(0, 'Chapter: Cold open'); ds3d.addMarker(330, 'Chapter: The tea'); ds3d.addMarker(500, '# Payoff'); ds3d.addMarker(100, 'gag: tea spill'); ds3d.addMarker(520, 'gag: tea spill'); });
  rr = await ev(() => ds3d.story({ action: 'chapters' }));
  ok(rr.text === '0:00 Cold open\n0:11 The tea\n0:16 Payoff' && fs.existsSync(rr.path), 'chapters exported: ' + JSON.stringify(rr.text));
  rr = await ev(() => ds3d.story({ action: 'gags' }));
  ok(rr[0].count === 2, 'running gag counted twice');
  await ev(() => { ds3d.setValues({ armR: 50 }, 0, true); ds3d.addShot(false); ds3d.setValues({ armR: 120 }, 0, true); });
  rr = await ev(() => ds3d.story({ action: 'loop_back' }));
  const s2 = await ev(() => ds3d.state());
  ok(s2.keyed.armR.find(k => k[0] === s2.length - 1)?.[1] === 50, 'loop back: the last shot ends on the opening pose');
  rr = await ev(() => ds3d.story({ action: 'bible', bible: { premise: 'Bunny vs chai' } }));
  ok(rr.premise === 'Bunny vs chai', 'story bible saved');
  await ev(() => [...document.querySelectorAll('#menubar .menu > button')].find(b => b.textContent === 'Story').click());
  await ev(() => [...document.querySelectorAll('#menubar button')].find(b => b.textContent.startsWith('Story bible')).click());
  ok(await p.locator('.ds-modal textarea').count() === 3, 'story bible dialog opens');
  await p.screenshot({ path: path.join(out, 'batch4.png') });
  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
