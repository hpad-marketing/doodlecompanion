// Feature picks part 2: belly squash, hand contact, beat camera, multi-cam, floor-plan path,
// previz, halftone stage, stick-figure posing, script to blocking. Run: node tools/test_batch10.cjs
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54305, out = path.join(__dirname, '..', 'devout');
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
  const X = a => ev(x => ds3d.features(x), a);
  const val = (id, f) => ev(([id, f]) => { ds3d.goto(f); return ds3d.state().values[id]; }, [id, f]);
  await ev(() => ds3d.setShot({ length: 120 }));

  // belly squash: shorter body, same head size, feet planted
  const m0 = await X({ action: 'measure', frame: 0 });
  await ev(() => ds3d.setValues({ squashBody: 25 }, 0, true));
  const m1 = await X({ action: 'measure', frame: 0 });
  ok(m1.neckZ < m0.neckZ - 0.01 && Math.abs(m1.headSize - m0.headSize) < 1e-4 && Math.abs(m1.feet - m0.feet) < 0.003, `squash lowers the neck ${m0.neckZ}→${m1.neckZ}, head stays ${m0.headSize}→${m1.headSize}, feet ${m0.feet}→${m1.feet}`);
  await ev(() => ds3d.setValues({ squashBody: -25 }, 0, true));
  const m2 = await X({ action: 'measure', frame: 0 });
  ok(m2.neckZ > m0.neckZ + 0.01 && Math.abs(m2.headSize - m0.headSize) < 1e-4, 'stretch raises it, head unchanged');
  await ev(() => ds3d.setValues({ squashBody: 0 }, 0, true));
  let r = await X({ action: 'squash', kind: 'land', frame: 40, amount: 20 });
  ok(r.keys.length === 6 && (await val('squashBody', 40)) === 20 && (await val('squashBody', 38)) < 0 && (await val('squashBody', 44)) < 0, 'landing: stretch before, squash on contact, overshoot after');

  // hand contact: the paw rests on the hip and follows it
  r = await X({ action: 'contact', limb: 'armL', where: 'hip', from: 60, to: 70 });
  const mh = await X({ action: 'measure', frame: 65 });
  ok(r.worstErrorCm < 1.5 && !mh.clips.length && mh.handL[2] < mh.neckZ, `left paw on the hip, ${r.worstErrorCm} cm off, no head clip`);
  r = await X({ action: 'contact', limb: 'armR', where: 'belly', from: 60, to: 70 });
  ok(r.worstErrorCm < 2, `right paw on the belly, ${r.worstErrorCm} cm off`);
  // stick figure: arms up and out, lean to screen right
  await ev(() => ds3d.goto(100));
  const strokes = [
    [[0.5, 0.2], [0.53, 0.17], [0.5, 0.14], [0.47, 0.17], [0.5, 0.2]],          // head
    [[0.5, 0.22], [0.52, 0.42]],                                               // body, leaning
    [[0.5, 0.25], [0.38, 0.15]], [[0.5, 0.25], [0.62, 0.15]],                  // arms up
    [[0.52, 0.42], [0.46, 0.55]], [[0.52, 0.42], [0.58, 0.55]],                // legs
  ];
  r = await X({ action: 'stick', strokes, aspect: 9 / 16, frame: 100 });
  const ms = await X({ action: 'measure', frame: 100 });
  ok(Object.keys(r.limbs).length === 4 && r.bodyTilt !== 0, `stick figure posed 4 limbs, lean ${r.bodyTilt}°`);
  ok(ms.handL[2] > 0.25 && ms.handR[2] > 0.25 && !ms.clips.length, `both hands raised above the shoulders, never into the head (${ms.handL[2]}, ${ms.handR[2]}; clips: ${ms.clips})`);

  // beats -> camera punch, eased
  await ev(() => { for (const f of [10, 30, 50, 70]) ds3d.addMarker(f, 'beat'); });
  r = await X({ action: 'beat_cam', style: 'punch' });
  const cam = await ev(() => ds3d.project.tracks['cam.dist']);
  ok(r.beats === 4 && cam.length >= 4 && cam.every(k => k.ease === 'ease') && cam.find(k => k.f === 10).v < cam.find(k => k.f === 30).v, 'beat punch-ins keyed and eased on every other beat');

  // multi-cam
  await ev(() => ds3d.goto(0));
  await X({ action: 'save_angle', name: 'A' });
  await ev(() => ds3d.setValues({ 'cam.yaw': 40, 'cam.lens': 85 }, 0, true));
  await X({ action: 'save_angle', name: 'B' });
  r = await X({ action: 'cut_to', name: 'B', frame: 90 });
  ok(Math.abs((await val('cam.yaw', 90)) - 40) < 0.01 && Math.abs((await val('cam.lens', 90)) - 85) < 0.01 && Math.abs((await val('cam.lens', 89)) - (await val('cam.lens', 88))) < 0.01, 'cut to angle B: holds until the cut, then jumps');
  ok(await ev(() => ds3d.project.camCuts.includes(90)), 'cut frame recorded for the render (no blur across it)');

  // floor-plan path: start where the camera is, end on its right
  const pos = await X({ action: 'plan_info', frame: 0 });
  await ev(() => { ds3d.project.tracks['cam.yaw'] = []; ds3d.project.tracks['cam.dist'] = []; });
  r = await X({ action: 'plan_path', points: [[pos.x, pos.y], [pos.x + 1.5, pos.y + 0.5], [3, 0]], from: 0, to: 60 });
  const end = await X({ action: 'plan_info', frame: 60 }), mid = await X({ action: 'plan_info', frame: 3 });
  ok(Math.abs(end.x - 3) < 0.05 && Math.abs(end.y) < 0.05, `camera ends on the drawn point (${end.x.toFixed(2)}, ${end.y.toFixed(2)})`);
  ok(Math.hypot(mid.x - pos.x, mid.y - pos.y) < 0.15, 'and eases out of its start');

  // previz + halftone stage
  r = await X({ action: 'previz', on: true });
  ok(r.previz === true, 'previz grey in the viewport');
  await p.screenshot({ path: path.join(out, 'previz.png') });
  await X({ action: 'previz', on: false });
  r = await ev(() => ds3d.setStage({ halftone: true }));
  ok(r.stage.halftone === true, 'halftone on the stage');

  // script to blocking
  r = await X({ action: 'script', text: 'INT. KITCHEN\nBUNNY: (wave) Hi, I made toast.\n(shocked) It is on fire.\n\n# The fix\nBUNNY: (shrug) Cereal it is.', captions: true });
  const st = await ev(() => ds3d.state());
  ok(r.shots.length === 2 && st.shots.length === 3 && st.shots[1].name === 'INT. KITCHEN', 'two shots blocked from the script: ' + JSON.stringify(r.shots));
  ok(st.markers.length === 1 && /Cereal/.test(st.markers[0].note), 'lines become markers');
  ok(await ev(() => ds3d.post({ action: 'captions' }).then(c => c.lines.length === 3)), 'and captions when asked');
  await p.screenshot({ path: path.join(out, 'script-blocking.png') });

  // dialogs open
  await p.click('#menubar .menu > button:text-is("Camera")');
  await p.click('#menubar .menu-list button:has-text("Floor-plan camera path")');
  ok(await p.locator('.plan-canvas').count() === 1, 'floor-plan dialog');
  await ev(() => document.querySelectorAll('.ds-modal').forEach(m => m.remove()));
  await p.click('#menubar .menu > button:text-is("Animate")');
  await p.click('#menubar .menu-list button:has-text("Pose from a stick figure")');
  ok(await p.locator('#stick-layer').count() === 1, 'stick-figure drawing layer');
  await p.click('.stick-bar button:text-is("Cancel")');

  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
