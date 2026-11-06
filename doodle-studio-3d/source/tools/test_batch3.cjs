// Animator tools in the real UI.
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54295, out = path.join(__dirname, '..', 'devout');
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.accept());
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const tool = a => ev(a => ds3d.animTool(a), a);
  await ev(() => { ds3d.setValues({ armL: 0, elbowL: 0, wristL: 0 }, 0, true); ds3d.setValues({ armL: 100, elbowL: 60, wristL: 20 }, 20, true); });
  let r = await tool({ action: 'breakdown', amount: 25, frame: 10 });
  let st = await ev(() => ds3d.state());
  ok(r.keyed.includes('armL') && Math.round(st.values.armL) === 25, 'breakdown 25% keys armL=25 at frame 10');
  r = await tool({ action: 'overlap', part: 'armL', amount: 2 });
  st = await ev(() => ds3d.state());
  ok(st.keyed.elbowL.map(k => k[0]).join() === '2,12,22' && st.keyed.wristL.map(k => k[0]).join() === '4,14,24', 'overlap lags elbow 2 and wrist 4 frames');
  // simplify: a dense straight ramp collapses
  await ev(() => { for (let f = 30; f <= 60; f++) ds3d.setValues({ headYaw: f - 30 }, f, true); ds3d.setEase('headYaw', 30, 'linear'); });
  await ev(() => { const s = ds3d.state(); for (const [f] of s.keyed.headYaw) ds3d.setEase('headYaw', f, 'linear'); });
  r = await tool({ action: 'simplify' });
  st = await ev(() => ds3d.state());
  ok(st.keyed.headYaw.length <= 3 && r.removed >= 28, `simplify removed ${r.removed} keys (headYaw now ${st.keyed.headYaw.length})`);
  r = await tool({ action: 'loop_check' });
  ok(!r.seamless, 'loop check spots the mismatch');
  r = await tool({ action: 'make_loop' });
  ok(r.seamless, 'make loop makes it seamless');
  const len0 = (await ev(() => ds3d.state())).length;
  r = await tool({ action: 'retime', amount: 0.5, frame: 0 });
  st = await ev(() => ds3d.state());
  ok(st.length === len0 * 2 - 1 && st.keyed.armL.some(k => k[0] === 40), `retime at half speed doubles the timing (length ${st.length})`);
  await tool({ action: 'stepped', on: true });
  await ev(() => ds3d.goto(30));
  st = await ev(() => ds3d.state());
  ok(Math.round(st.values.armL) === 25, 'stepped holds the previous key');
  await tool({ action: 'stepped', on: false });
  // ease presets
  ok(await ev(() => [...document.querySelectorAll('#ease-select option')].map(o => o.value).join()).then(s => s.includes('overshoot') && s.includes('bounce')), 'overshoot and bounce eases listed');
  // views
  await tool({ action: 'onion', on: true, frame: 30 });
  const ink = await ev(() => { const c = document.querySelector('#onion-layer'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i]) n++; return n; });
  ok(ink > 500, `onion skin draws ghosts (${ink} px)`);
  await tool({ action: 'silhouette', on: true });
  await p.waitForTimeout(200);
  await p.locator('#frame').screenshot({ path: path.join(out, 'silhouette.png') });
  await tool({ action: 'silhouette', on: false }); await tool({ action: 'onion', on: false });
  r = await tool({ action: 'mirror_view', on: true });
  ok(await ev(() => document.querySelector('#frame').classList.contains('mirrored')), 'mirror view flips the viewport');
  await tool({ action: 'mirror_view', on: false });
  // filter
  await ev(() => { const s = [...document.querySelectorAll('#timeline-tools select')].find(x => x.getAttribute('aria-label') === 'Key filter'); s.value = 'hands'; s.dispatchEvent(new Event('change')); });
  const names = await ev(() => [...document.querySelectorAll('#tracks .tname')].map(e => e.textContent));
  ok(!names.some(n => /Turn|Head/.test(n)) && names.some(n => /Elbow/.test(n)), 'key filter shows arms only');
  // playblast (short shot)
  await ev(() => ds3d.setShot({ length: 30 }));
  r = await tool({ action: 'playblast' });
  ok(r.path && fs.statSync(r.path).size > 1000, `playblast saved ${r.bytes} bytes`);
  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
