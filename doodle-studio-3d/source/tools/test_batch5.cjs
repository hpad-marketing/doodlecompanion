// Polish part 2: undo history, Claude change log + per-change undo + token meter, render
// presets, export preflight (blocks, then passes), moderator PASS voided by an edit, health
// check fixes, pack project, overnight batch. Run: node tools/test_batch5.cjs
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54297, out = path.join(__dirname, '..', 'devout'), wav = path.join(out, 'beat.wav');
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  fs.rmSync(path.join(out, 'scene-log.txt'), { force: true });
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.accept());
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const prod = a => ev(x => ds3d.production(x), a);

  // undo history with labels
  await ev(() => ds3d.setValues({ armL: 40 }, 0, true));
  await ev(() => ds3d.setValues({ headYaw: 20 }, 10, true));
  let hist = await prod({ action: 'history' });
  ok(hist.length >= 2, 'history lists changes: ' + hist.map(x => x.label).join(', '));
  await p.click('#menubar .menu button:has-text("Edit")');
  await p.click('#menubar .menu-list button:has-text("Undo history")');
  ok(await p.locator('.ds-modal[aria-label="Undo history"] .ds-list button').count() === hist.length + 1, 'Undo history panel shows every change plus Now');
  await p.locator('.ds-modal[aria-label="Undo history"] .ds-list button').nth(1).click();   // just before the newest change
  let st = await ev(() => ds3d.state());
  ok(!st.keyed.headYaw && st.keyed.armL, 'clicking an entry goes back to just before it');
  await ev(() => ds3d.redo());

  // Claude change log: two changes, undo the first only
  await ev(() => { ds3dClaude.begin('set_values', 40); ds3d.setValues({ armR: 70 }, 5, true); ds3dClaude.end(900); });
  await ev(() => { ds3dClaude.begin('set_values', 40); ds3d.setValues({ earLFold: -20 }, 5, true); ds3dClaude.end(900); });
  await ev(() => { ds3dClaude.begin('get_state', 2); ds3dClaude.end(4000); });
  let log = await prod({ action: 'change_log' });
  ok(log.changes.length === 2, 'read-only calls are not logged as changes');
  ok(log.meter.calls === 3 && log.meter.tokens === Math.round((82 + 5800) / 4), 'token meter counts every call: ' + JSON.stringify(log.meter));
  let r = await prod({ action: 'revert_change', index: 0 });
  st = await ev(() => ds3d.state());
  ok(!st.keyed.armR && st.keyed.earLFold, 'per-change undo removes only that change: ' + JSON.stringify(r));
  hist = await prod({ action: 'history' });
  ok(hist.at(-1).label === 'Undo Claude: set values', 'the per-change undo is itself undoable');
  await p.click('#menubar .menu button:has-text("Tools")');
  await p.click('#menubar .menu-list button:has-text("Claude change log")');
  ok(await p.locator('.ds-modal[aria-label="Claude change log"] button:has-text("Undone")').count() === 1, 'change log dialog marks it undone');
  await p.keyboard.press('Escape'); await ev(() => document.querySelectorAll('.ds-modal').forEach(m => m.remove()));

  // presets
  r = await prod({ action: 'preset', name: 'YouTube 16:9' });
  st = await ev(() => ds3d.state());
  ok(st.width === 1920 && st.height === 1080, 'preset applied to the scene');
  await prod({ action: 'preset', name: 'Reel' });
  await p.click('#tabs button:has-text("Render")');
  ok(await p.locator('#panel-content .chips button:has-text("Draft")').count() === 1, 'Render tab lists the presets');
  await p.waitForTimeout(300);
  ok(/s per frame/.test(await p.locator('#render-estimate').textContent()), 'render time estimate shown: ' + await p.locator('#render-estimate').textContent());

  // preflight: blocked without audio, lip sync, moderator
  let pf = await prod({ action: 'preflight' });
  ok(!pf.ok && pf.checks.find(c => c.id === 'audio').ok === false, 'preflight blocks: no audio');
  let threw = await ev(() => ds3d.renderScene({}).then(() => null, e => e.message));
  ok(threw && /preflight/.test(threw), 'MCP final render refused while the preflight fails');
  await ev(w => ds3d.importAudio(w), wav);
  // talk: mouth keys across the shot
  await ev(() => { const s = ds3d.project; for (let f = 0; f < s.length; f += 4) ds3d.setValues({ mouth: 1 + (f / 4) % 5 }, f, true); });
  await ev(() => ds3d.libraryUse('text:headline', { frame: 0, text: 'Dell\nwell' }));
  pf = await prod({ action: 'preflight' });
  const cap = pf.checks.find(c => c.id === 'captions');
  ok(!cap.ok && /one line/.test(cap.detail), 'short caption split over two lines fails: ' + cap.detail);
  await ev(() => { ds3d.removeItem(0); return ds3d.libraryUse('text:headline', { frame: 0, text: 'Dell well', at: [0, 0.8, 0.15] }); });
  pf = await prod({ action: 'preflight' });
  ok(pf.checks.find(c => c.id === 'lipsync').ok, 'lip sync sampled: ' + pf.checks.find(c => c.id === 'lipsync').detail);
  ok(pf.checks.find(c => c.id === 'captions').ok, 'caption below the face passes: ' + pf.checks.find(c => c.id === 'captions').detail);
  ok(!pf.checks.find(c => c.id === 'moderator').ok, 'still blocked: no moderator PASS');
  await prod({ action: 'moderator_pass', note: 'test' });
  pf = await prod({ action: 'preflight' });
  ok(pf.ok, 'everything passes after the moderator PASS');
  await ev(() => ds3d.setValues({ armL: 55 }, 3, true));
  pf = await prod({ action: 'preflight' });
  ok(!pf.checks.find(c => c.id === 'moderator').ok, 'an edit after the PASS voids it');
  await prod({ action: 'moderator_pass' });
  await ev(() => ds3d.selectShot(0));
  ok((await prod({ action: 'preflight' })).ok, 'just selecting a shot keeps the PASS');
  await ev(() => ds3d.renderScene({}));
  await p.waitForTimeout(300);
  ok(/full/.test(fs.readFileSync(path.join(out, 'scene-log.txt'), 'utf8')), 'final render goes out once the preflight passes');
  // UI: the button shows the dialog
  await p.click('#panel-content button:has-text("Check before export")');
  await p.waitForSelector('.ds-modal .preflight');
  ok(await p.locator('.ds-modal .preflight.ok').count() === 4, 'preflight dialog: four green checks');
  await p.screenshot({ path: path.join(out, 'preflight.png') });
  await ev(() => document.querySelectorAll('.ds-modal').forEach(m => m.remove()));

  // health check + fixes
  await ev(() => { const s = ds3d.project; s.tracks.armL.push({ f: s.length + 5, v: 10 }); ds3d.scene.shots.push(JSON.parse(JSON.stringify(s))); ds3d.scene = ds3d.scene; });
  let hc = await prod({ action: 'health' });
  ok(!hc.items.find(i => i.id === 'keys').ok && !hc.items.find(i => i.id === 'codes').ok, 'health check finds keys past the end and repeated shot codes');
  await prod({ action: 'fix', fix: 'trim-keys' });
  await prod({ action: 'fix', fix: 'renumber' });
  hc = await prod({ action: 'health' });
  ok(hc.items.find(i => i.id === 'keys').ok && hc.items.find(i => i.id === 'codes').ok, 'one-click fixes clear both');
  await p.click('#menubar .menu button:has-text("Tools")');
  await p.click('#menubar .menu-list button:has-text("Health check")');
  await p.waitForSelector('.ds-modal[aria-label="Health check"]');
  ok(await p.locator('.ds-modal[aria-label="Health check"] .preflight').count() >= 8, 'health check dialog lists the checks');
  await p.screenshot({ path: path.join(out, 'health.png') });
  await ev(() => document.querySelectorAll('.ds-modal').forEach(m => m.remove()));

  // pack + batch
  r = await prod({ action: 'pack' });
  ok(r.files.length && JSON.parse(fs.readFileSync(r.files[0], 'utf8')).packed, 'pack project writes a packed scene');
  r = await prod({ action: 'batch', preview: true });
  ok(r.queued.length === 1, 'batch queues the scene');

  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
