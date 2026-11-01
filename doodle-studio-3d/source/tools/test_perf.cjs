// Viewport speed: the 3D view draws only when something changed, an unchanged pose costs next to
// nothing, a timeline step stays cheap, and drawing on demand shows exactly what drawing every
// frame shows (pixel-identical stills after a pose change, a camera move, a co-star and a stage edit).
// Run: DSL_LIBRARY=<Doodle Library folder> node tools/test_perf.cjs   (writes devout/perf.json)
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54298, S = path.join(__dirname, '..');
const dev = spawn('node', [path.join(S, 'tools/dev.cjs'), String(port)], { stdio: 'ignore', env: { ...process.env, DSL_LIBRARY: process.env.DSL_LIBRARY || path.join(S, '..', 'lib') } });
const ok = (c, m) => { console.log(c ? 'ok  ' : 'FAIL', m); if (!c) process.exitCode = 1; };
// budgets (software GL in CI is far slower than the RTX 5080, so the GPU draw itself is reported, not budgeted)
const BUDGET = { idleDrawsPerSec: 2, samePoseMs: 0.5, gotoMs: 3, sigMs: 0.5 };
(async () => {
  await new Promise(r => setTimeout(r, 900));
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  await p.waitForTimeout(2500);
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  // a busy shot: keys on several controls over 48 frames
  await ev(() => { for (const [f, a] of [[0, 0], [24, 60], [47, -30]]) ds3d.setValues({ armL: a, elbowL: a / 2, headYaw: a / 3, turn: a / 4 }, f, true); ds3d.goto(0); });
  await p.waitForTimeout(500);

  const r = await ev(async () => {
    const v = ds3d.view, out = {}, wait = ms => new Promise(r => setTimeout(r, ms));
    let draws = 0; const real = v.renderer.render.bind(v.renderer); v.renderer.render = (...a) => { draws++; return real(...a); };
    // idle: nothing changes for 3 s
    await wait(300); draws = 0; await wait(3000); out.idleDrawsPerSec = draws / 3;
    // a change draws on the next frame
    draws = 0; ds3d.setValues({ armR: 40 }); await wait(120); out.drawsAfterChange = draws;
    draws = 0; v.setCamera({ yaw: 15 }); await wait(120); out.drawsAfterCamera = draws; v.setCamera({ yaw: 0 }); await wait(120);
    // playback draws every new frame
    draws = 0; ds3d.goto(0); const t0 = performance.now(); for (let f = 0; f < 20; f++) { ds3d.goto(f); await new Promise(r => requestAnimationFrame(r)); } out.drawsPerSteppedFrame = draws / 20; out.stepFrameMs = (performance.now() - t0) / 20;
    v.renderer.render = real;
    // costs
    const T = (n, fn) => { const t = performance.now(); for (let i = 0; i < n; i++) fn(i); return +((performance.now() - t) / n).toFixed(3); };
    const vals = { ...v.values };
    out.samePoseMs = T(50, () => v.pose({ ...vals }));
    out.newPoseMs = T(30, i => v.pose({ ...vals, armL: i }));
    out.gotoMs = T(30, i => ds3d.goto(i % 48));
    out.sigMs = T(100, () => v.frameSig());
    const gl = v.renderer.getContext(), px = new Uint8Array(4);
    out.drawMs = T(20, () => { v.render(); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px); });
    let n = 0; v.scene.traverse(() => n++); out.sceneObjects = n;
    return out;
  });
  console.log(JSON.stringify(r));
  ok(r.idleDrawsPerSec <= BUDGET.idleDrawsPerSec, `idle: ${r.idleDrawsPerSec} draws/s (was every frame; budget ${BUDGET.idleDrawsPerSec})`);
  ok(r.drawsAfterChange >= 1, 'a pose change draws: ' + r.drawsAfterChange);
  ok(r.drawsAfterCamera >= 1, 'a camera move draws: ' + r.drawsAfterCamera);
  ok(r.drawsPerSteppedFrame >= 0.9, 'every timeline step draws: ' + r.drawsPerSteppedFrame);
  ok(r.samePoseMs <= BUDGET.samePoseMs, `unchanged pose ${r.samePoseMs} ms (budget ${BUDGET.samePoseMs})`);
  ok(r.gotoMs <= BUDGET.gotoMs, `timeline step ${r.gotoMs} ms (budget ${BUDGET.gotoMs})`);
  ok(r.sigMs <= BUDGET.sigMs, `change check ${r.sigMs} ms (budget ${BUDGET.sigMs})`);

  // the picture is the same either way: on-demand frame vs a forced draw, after each kind of change
  const same = async label => {
    await p.waitForTimeout(250);
    const a = await ev(() => ds3d.view.renderer.domElement.toDataURL());
    const c = await ev(() => { ds3d.view.render(); return ds3d.view.renderer.domElement.toDataURL(); });
    ok(a === c, 'on-demand frame matches a forced draw: ' + label);
  };
  await ev(() => ds3d.setValues({ armL: 75, elbowL: 40, expression: 3 })); await same('pose + face');
  await ev(() => ds3d.view.setCamera({ yaw: 25, dist: 2.4 })); await same('camera');
  await ev(() => ds3d.goto(30)); await same('timeline step');
  await ev(() => { ds3d.view.grid.visible = false; }); await same('grid hidden');
  await ev(() => { ds3d.view.grid.visible = true; ds3d.view.inkScale = 1.4; }); await same('ink width');
  await ev(() => { ds3d.view.inkScale = 1; }); await same('ink back');
  const costar = await ev(async () => { try { await ds3d.cast({ action: 'add', character: 'koala' }); return true; } catch (e) { return e.message; } });
  if (costar === true) { await p.waitForTimeout(1500); await same('co-star added'); }
  else console.log('skip co-star check:', costar);
  // the pose cache never hides a change made through the rig directly (motion paths, mirror tools)
  const cacheSafe = await ev(() => {
    const v = ds3d.view, vals = { ...v.values }, before = v.objects[0].buf.slice();
    v.rig.pose({ ...vals, armL: -80 });           // someone else poses the rig...
    v.pose(vals);                                  // ...then the view asks for the same pose again
    const after = v.objects[0].buf;
    return before.every((x, i) => Math.abs(x - after[i]) < 1e-6);
  });
  ok(cacheSafe, 're-posing after a direct rig pose restores the buffers');
  const normalsSame = await ev(() => {
    const v = ds3d.view; v.pose({ ...v.values, armL: 33, elbowL: 50 });
    let worst = 0;
    for (const o of v.objects.filter(o => o.outline)) { const mine = o.g.attributes.normal.array.slice(); o.g.computeVertexNormals(); const ref = o.g.attributes.normal.array; for (let i = 0; i < ref.length; i++) worst = Math.max(worst, Math.abs(ref[i] - mine[i])); }
    return worst;
  });
  ok(normalsSame < 1e-5, 'fast outline normals match three.js computeVertexNormals (worst diff ' + normalsSame.toExponential(1) + ')');
  fs.writeFileSync(path.join(S, 'devout', 'perf.json'), JSON.stringify({ at: new Date().toISOString(), ...r }, null, 1));
  ok(!errs.length, 'no page errors ' + errs.slice(0, 3).join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.error(e); dev.kill(); process.exit(1); });
