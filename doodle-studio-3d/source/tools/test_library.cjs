// Library tab and characters in the real UI (dev server + Chromium): switch to the Koala,
// insert a motion (mirrored) and a face, place props and effects, set the stage, and check
// what goes to Blender. Run: node tools/test_library.cjs  (starts tools/dev.cjs on 54291)
const { spawn } = require('child_process'), path = require('path');
const { chromium } = require('playwright');
const port = 54291;
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'inherit' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);

  // character
  let r = await ev(() => ds3d.setCharacter('koala'));
  ok(r.character === 'koala' && r.controls.includes('Nose'), 'Koala on stage with nose controls');
  ok(await ev(() => ds3d.view.rig.bones.has('nose')), 'viewport rig rebuilt from koala.json');
  await ev(() => ds3d.setValues({ noseWiggle: 60, legReach: 40, earLScale: 120 }, 0, true));
  // motion, mirrored
  r = await ev(() => ds3d.libraryUse('motion-wave-hello', { frame: 10, mirror: true }));
  ok(r.to === 70 && r.mirrored, 'motion inserted at 10..70: ' + JSON.stringify(r));
  let st = await ev(() => ds3d.state());
  ok(st.keyed.armL && !st.keyed.armR, 'mirrored wave keys the left arm, not the right');
  r = await ev(() => ds3d.libraryUse('mocap-cmu-02-01-walk', { frame: 0 }));
  ok(r.length >= 84, 'mocap walk inserted; shot length ' + r.length);
  // face (story beat by name)
  r = await ev(() => ds3d.libraryUse('face-beat-duck-pout', { frame: 5 }));
  ok(r.keyed.expression != null && r.keyed.earLFold === -30, 'story-beat face keyed: ' + JSON.stringify(r.keyed));
  // items
  await ev(() => ds3d.libraryUse('prop-letter_envelope', { frame: 0, hold: 'R' }));
  await ev(() => ds3d.libraryUse('fx:rain', { frame: 0 }));
  await ev(() => ds3d.libraryUse('story:time_skip', { frame: 30, text: '3 hours later' }));
  // stage
  r = await ev(() => ds3d.setStage({ set: 'bedroom', time: 'golden', outfit: 'raincoat', accessories: ['bowtie'], mouthSet: 'mouths-bouncy' }));
  ok(r.stage.set === 'bedroom' && r.stage.outfit === 'raincoat', 'scene stage set');
  r = await ev(() => ds3d.setStage({ setProps: { rug: false }, time: 'night' }, true));
  ok(r.stage.time === 'night' && r.stage.setProps.rug === false && r.scope === 'sh010', 'shot override on top of the scene');
  // what Blender gets
  const shot = await ev(() => { const s = ds3d.state(); return null; });
  const bridge = await ev(() => new Promise(res => { const orig = window.fetch; window.fetch = (u, o) => { if (String(u).includes('/api/export-bridge')) { res(JSON.parse(o.body).shot); window.fetch = orig; } return orig(u, o); }; document.querySelectorAll('#menubar .menu-list button').forEach(b => { if (b.textContent.startsWith('Export Blender shot')) b.click(); }); }));
  ok(bridge.character === 'koala', 'bridge shot names the Koala');
  ok(bridge.stage.set === 'bedroom' && bridge.stage.time === 'night' && bridge.stage.accessories[0] === 'bowtie', 'bridge stage merged: ' + JSON.stringify(bridge.stage));
  ok(bridge.items.length === 3 && bridge.items.find(i => i.hold === 'R'), 'bridge carries 3 items');
  ok(bridge.frames[0].noseWiggle === 60 && bridge.frames[0].legReach === 40 && bridge.frames[0].earRScale === 100, 'species tracks in frames');
  // UI tab
  await p.click('#tabs button:has-text("Library")');
  await p.waitForTimeout(400);
  ok(await p.locator('.lib-item').count() > 10, 'Library tab lists motions');
  await p.fill('.library input[type=search]', 'wave');
  ok(await p.locator('.lib-item').count() >= 1, 'search finds wave');
  await p.fill('.library input[type=search]', '');
  await p.click('.library .chips button:has-text("Props")');
  ok(await p.locator('.lib-item').count() > 10, 'props listed');
  await p.screenshot({ path: path.join(__dirname, '..', 'devout', 'library-tab.png') });
  // undo back to Bunny
  r = await ev(() => ds3d.setCharacter('frog'));
  ok(r.character === 'frog' && !r.controls.includes('Nose'), 'Frog: no nose controls');
  await p.screenshot({ path: path.join(__dirname, '..', 'devout', 'library-frog.png') });
  for (let i = 0; i < 12; i++) await ev(() => ds3d.undo());
  await p.waitForTimeout(500);
  st = await ev(() => ds3d.state());
  ok(st.character === 'bunny' && !(await ev(() => ds3d.view.rig.bones.has('nose'))), 'undo all the way: Bunny back in the viewport');
  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
