// Look at camera vs a motion clip's head keys and a hard camera cut (Bambi render, 31 Oct):
// the head must follow only the look on every frame, snap with the cut (no one-frame blend),
// and the clip's head keys must come back when Look at camera is switched off.
// Run: node tools/test_lookcam.cjs
const { spawn } = require('child_process'), path = require('path');
const { chromium } = require('playwright');
const port = 54318;
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
  await ev(() => {
    ds3d.setShot({ length: 60 });
    // a "motion clip": head keys swinging +-40 on odd frames
    for (let f = 1; f < 60; f += 2) ds3d.setValues({ headYaw: f % 4 === 1 ? 40 : -40, headNod: 10 }, f, true);
    // camera: front for 30 frames, then a hard cut to 35 degrees off to his side
    ds3d.setValues({ 'cam.yaw': 0 }, 0, true); ds3d.setEase('cam.yaw', 0, 'hold');
    ds3d.setValues({ 'cam.yaw': 35 }, 30, true); ds3d.setEase('cam.yaw', 30, 'hold');
    ds3d.setValues({ 'cam.yaw': 35 }, 59, true);
  });
  const read = () => ev(() => Array.from({ length: 60 }, (_, f) => { ds3d.goto(f); return ds3d.state().values.headYaw; }));
  await ev(() => ds3dCameraPresets.apply({ lookAtCamera: true }));
  const y = await read();
  const jumps = y.slice(1).map((v, i) => [i + 1, Math.abs(v - y[i])]).filter(([, d]) => d > 3);
  ok(jumps.every(([f]) => f === 30), 'head moves smoothly except at the cut: ' + JSON.stringify(jumps.map(([f, d]) => [f, Math.round(d)])));
  ok(Math.abs(y[29] - y[28]) < 1 && Math.abs(y[31] - y[30]) < 1, `no in-between frame at the cut (${y.slice(27, 33).map(Math.round).join(', ')})`);
  ok(!y.some(v => Math.abs(Math.abs(v) - 40) < 0.5), 'none of the clip\'s +-40 head keys show through');
  await ev(() => ds3dCameraPresets.apply({ lookAtCamera: false }));
  const back = await read();
  ok(Math.round(back[1]) === 40 && Math.round(back[3]) === -40, `clip head keys come back when it is off (${Math.round(back[1])}, ${Math.round(back[3])})`);
  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e.message); dev.kill(); process.exit(1); });
