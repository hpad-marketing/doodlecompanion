// Batch 1 tools in the real UI: squash, rack focus, horizon lock, pose mirror / blend, line weight, storyboard.
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54293;
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const bridge = () => ev(() => new Promise(res => { const orig = window.fetch; window.fetch = (u, o) => { if (String(u).includes('/api/export-bridge')) { res(JSON.parse(o.body).shot); window.fetch = orig; } return orig(u, o); }; document.querySelectorAll('#menubar .menu-list button').forEach(b => { if (b.textContent.startsWith('Export Blender shot')) b.click(); }); }));
  // pose mirror
  await ev(() => ds3d.setValues({ armL: 80, headYaw: 20 }, 0, true));
  let st = await ev(() => ds3d.mirrorPose(0));
  ok(Math.round(st.values.armR) === 80 && Math.round(st.values.headYaw) === -20 && Math.round(st.values.armL) === 0, 'mirror pose swaps arms and turns the head');
  st = await ev(() => ds3d.blendPoses({ armL: 0, elbowL: 0 }, { armL: 100, elbowL: 40 }, 25, 10));
  ok(Math.round(st.values.armL) === 25 && Math.round(st.values.elbowL) === 10, 'blend 25% from A to B');
  // camera
  await ev(() => ds3d.setValues({ 'cam.focus': 3, 'cam.fstop': 1.4, 'cam.roll': 12 }, 0, true));
  let r = await ev(() => ds3d.setShotLook({ horizonLock: true, ink: 150 }));
  ok(r.horizonLock && r.ink === 150, 'shot look set');
  const sh = await bridge();
  ok(sh.frames[0].cam.focus === 3 && sh.frames[0].cam.fstop === 1.4, 'rack focus reaches Blender');
  ok(sh.frames[0].cam.roll === 0, 'horizon lock zeroes the roll');
  ok(Math.abs(sh.settings.ink_px - 19.095) < 0.01, 'line weight 150% -> ink_px ' + sh.settings.ink_px);
  // storyboard
  await ev(() => { ds3d.addShot(false); ds3d.setShot({ name: 'reveal' }); });
  r = await ev(() => ds3d.storyboard());
  ok(r.shots === 2 && fs.existsSync(r.path), 'storyboard sheet saved: ' + r.path);
  if (r.path) fs.copyFileSync(r.path, path.join(__dirname, '..', 'devout', 'storyboard.png'));
  await p.click('#tabs button:has-text("Pose")');
  await p.screenshot({ path: path.join(__dirname, '..', 'devout', 'pose-tools.png') });
  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
