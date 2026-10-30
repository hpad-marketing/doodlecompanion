// Polish batch in the real UI: command search, markers, versions, autosave + crash recovery, disk check.
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54294, out = path.join(__dirname, '..', 'devout');
fs.rmSync(path.join(out, 'recovery.json'), { force: true }); fs.rmSync(path.join(out, 'versions'), { recursive: true, force: true });
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = [], dialogs = []; p.on('pageerror', e => errs.push(e.message));
  p.on('dialog', d => { dialogs.push(d.message()); d.type() === 'prompt' ? d.accept('beat drop') : d.accept(); });
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  // command search
  await ev(() => ds3d.setValues({ armL: 70 }, 0, true));
  await p.keyboard.press('Control+k');
  ok(await p.locator('.ds-cmd input').isVisible(), 'Ctrl+K opens command search');
  await p.keyboard.type('mirror pose');
  await p.keyboard.press('Enter');
  let st = await ev(() => ds3d.state());
  ok(Math.round(st.values.armR) === 70, 'command search ran Mirror pose');
  // markers
  await ev(() => ds3d.goto(30));
  await p.keyboard.press('m');
  st = await ev(() => ds3d.state());
  ok(st.markers.length === 1 && st.markers[0].f === 30 && st.markers[0].note === 'beat drop', 'M adds a marker with a note');
  ok(await p.locator('#tracks .marker').count() === 1, 'marker drawn on the ruler');
  // versions
  const v = await ev(() => ds3d.saveVersion('before retime'));
  ok(fs.existsSync(v.path), 'named version saved');
  await ev(() => ds3d.setValues({ armL: 10 }, 0, true));
  await p.click('#menubar .menu > button:has-text("File")');
  await p.click('#menubar button:has-text("Versions…")');
  ok(await p.locator('.ds-modal .ds-list button').count() === 1, 'Versions dialog lists it');
  await p.click('.ds-modal .ds-list button');
  await p.waitForTimeout(300);
  st = await ev(() => ds3d.state());
  ok(Math.round(st.values.armR) === 70 && Math.round(st.values.armL) === 0, 'opening the version brings its pose back');
  // autosave + recovery after a "crash" (reload without a clean close)
  await ev(() => { ds3d.setShot({ scene: 'Crash Test' }); ds3d.setValues({ headYaw: 33 }, 12, true); });
  await ev(() => ds3d.autosave({ minutes: 2, keep: 4 }));
  await ev(async () => { const m = await import('./src/polish.js'); return m.autosaveNow({ api: (pth, body) => fetch('/api/' + pth, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json()), scene: () => ds3d.scene, file: () => null, frame: () => 12 }, true); });
  ok(fs.existsSync(path.join(out, 'recovery.json')), 'autosave wrote the recovery file');
  dialogs.length = 0;
  await p.reload();
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  await p.waitForTimeout(800);
  st = await ev(() => ds3d.state());
  ok(dialogs.some(d => d.includes('did not close properly')) && st.scene === 'Crash Test' && st.frame === 12 && Math.round(st.values.headYaw) === 33, `recovery offered and restored at frame ${st.frame}`);
  // disk check (dev server reports 3 GB free)
  dialogs.length = 0;
  await ev(() => ds3d.render({}));
  ok(dialogs.some(d => d.includes('GB free')), 'low disk space warns before a full render');
  await p.screenshot({ path: path.join(out, 'batch2.png') });
  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
