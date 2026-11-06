// Multi-character: co-stars in the viewport and in the Blender shot, keys, copying the lead,
// library motions, the Co-stars dialog. Run: node tools/test_batch12.cjs
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54305, out = path.join(__dirname, '..', 'devout');
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
  const C = a => ev(x => ds3d.cast(x), a);
  const bridge = () => ev(() => ds3d.bridgeShot());

  ok(!(await bridge()).costars, 'a shot without co-stars sends none (render cache unchanged)');
  let r = await C({ action: 'add', character: 'koala' });
  ok(r.index === 0 && r.costar.x > 0 && r.costar.turn < 0, `the Koala stands beside Bunny, turned in: ${JSON.stringify(r.costar)}`);
  r = await C({ action: 'add', character: 'frog' });
  ok(r.costar.x < 0 && r.costar.turn > 0, 'the Frog takes the other side');
  await p.waitForFunction(() => (ds3d.view.actors || []).length === 2, null, { timeout: 20000 });
  ok(true, 'both co-stars appear in the viewport');
  await p.screenshot({ path: path.join(out, 'costars.png') });

  // keys on a co-star are its own
  await C({ action: 'key', index: 0, values: { armR: 80, expression: 3 }, frame: 10 });
  await C({ action: 'key', index: 0, values: { armR: 0 }, frame: 0 });
  let br = await bridge();
  ok(br.costars.length === 2 && br.costars[0].character === 'koala' && br.costars[0].frames.length === br.frames.length, 'co-stars reach Blender with a value per frame');
  ok(Math.abs(br.costars[0].frames[10].armR - 80) < 0.01 && br.costars[0].frames[10].expression === 3 && Math.abs(br.costars[0].frames[5].armR - 40) < 25, 'co-star keys interpolate on their own');
  ok(Math.abs(br.frames[10].armR - (await ev(() => { ds3d.goto(10); return ds3d.state().values.armR; }))) < 0.01 && br.frames[10].armR !== 80, "the lead's arm is untouched");
  ok(!('cam' in br.costars[0].frames[0]) && !Object.keys(br.costars[0].frames[0]).some(k => k.startsWith('cam.')), 'one camera for the shot: co-stars carry none');

  // copy the lead, mirrored
  await ev(() => { ds3d.setValues({ armL: 0 }, 0, true); ds3d.setValues({ armL: 90 }, 20, true); });
  r = await C({ action: 'copy', index: 1, mirror: true });
  br = await bridge();
  ok(r.mirrored && Math.abs(br.costars[1].frames[20].armR - 90) < 0.01, "the Frog copies Bunny's left arm on its right (mirrored)");

  // a library motion on a co-star
  const lib = require('../host/library.cjs')({ settings: { get: () => ({ libraryDir: process.env.DSL_LIBRARY || path.join(__dirname, '..', '..', 'lib') }) } });
  const motion = ((lib.items().items) || []).find(x => x.category === 'motion')?.id || null;
  if (motion) {
    const leadKeys = await ev(() => JSON.stringify(ds3d.project.tracks));
    r = await C({ action: 'motion', index: 0, id: motion, frame: 0 });
    ok(r && r.from === 0 && (await ev(() => JSON.stringify(ds3d.project.tracks))) === leadKeys, `library motion ${motion} lands on the co-star, the lead's keys untouched`);
  } else ok(true, 'library motion (no motion rows in this dev library)');

  // place, remove, limits
  r = await C({ action: 'place', index: 0, x: 1.2, y: 0.3, turn: -45 });
  ok(r.costar.x === 1.2 && (await bridge()).costars[0].turn === -45, 'placed by number');
  for (const c of ['bunny', 'koala', 'frog']) await C({ action: 'add', character: c });
  ok(await ev(async () => { try { await ds3d.cast({ action: 'add', character: 'koala' }); return false; } catch (e) { return /up to 5/.test(e.message); } }), 'five co-stars at most');
  for (let i = 0; i < 3; i++) await C({ action: 'remove', index: 2 });
  r = await C({ action: 'list' });
  ok(r.costars.length === 2 && r.costars[0].keyed.includes('armR'), 'list shows each co-star and its keys');
  await p.waitForFunction(() => (ds3d.view.actors || []).length === 2, null, { timeout: 5000 });

  // undo brings a removed co-star back
  await C({ action: 'remove', index: 1 });
  await ev(() => ds3d.undo());
  ok((await C({ action: 'list' })).costars.length === 2, 'undo restores a removed co-star');

  // dialog
  await p.click('#menubar .menu > button:text-is("Shot")');
  await p.click('#menubar .menu-list button:has-text("Co-stars")');
  ok(await p.locator('.ds-modal :text("Co-stars in this shot")').count() >= 1 && await p.locator('.ds-modal button:has-text("Copy Bunny")').count() === 2, 'Co-stars dialog lists both');
  await p.screenshot({ path: path.join(out, 'costars-dialog.png') });

  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
