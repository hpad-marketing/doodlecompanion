// Every library is visual: animated motion cards (sprite sheets in previews/motion_anim) with family and
// category chip rows, pictures for every face, speech mouth shapes, mouth sets and characters.
// Run: DSL_LIBRARY=<Doodle Library folder> node tools/test_visual_library.cjs
const { spawn } = require('child_process'), path = require('path');
const { chromium } = require('playwright');
const port = 54297, S = path.join(__dirname, '..');
const dev = spawn('node', [path.join(S, 'tools/dev.cjs'), String(port)], { stdio: 'inherit', env: { ...process.env, DSL_LIBRARY: process.env.DSL_LIBRARY || path.join(S, '..', 'lib') } });
const ok = (c, m) => { console.log(c ? 'ok  ' : 'FAIL', m); if (!c) process.exitCode = 1; };
(async () => {
  await new Promise(r => setTimeout(r, 900));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('response', r => { if (r.status() >= 400 && !/\/lib\/previews\/(motion|expression|prop|scenery|set|mouth_set|outfit|accessory)\//.test(r.url())) errs.push('HTTP ' + r.status() + ' ' + r.url()); }); p.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(m.text()); });
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const tab = async (t, s) => { await p.evaluate(([t, s]) => ds3d.setTab ? ds3d.setTab(t, s) : null, [t, s]); await p.waitForTimeout(1500); };
  const click = async sel => { await p.click(sel); await p.waitForTimeout(1200); };
  // Animate › Motion library
  await p.click('#tabs button:has-text("Animate")'); await p.waitForTimeout(2500);
  const n = await p.$$eval('.libx-card .anim', a => a.length); ok(n > 50, 'animated motion cards: ' + n);
  const chips = await p.$$eval('.libx-cats .chips', c => c.map(x => x.children.length)); ok(chips.length === 2 && chips[0] >= 4, 'family/category chip rows ' + chips);
  await p.screenshot({ path: '/tmp/ds3d-visual-motions.png' });
  await p.click('.libx-cats .chips:first-child button:has-text("Mocap")'); await p.waitForTimeout(800);
  const subs = await p.$$eval('.libx-cats .chips:nth-child(2) button', c => c.map(x => x.textContent).slice(0, 4)); ok(subs.some(s => /Walks/.test(s)), 'mocap categories ' + subs);
  await p.click('.libx-cats .chips:nth-child(2) button:has-text("Dance")'); await p.waitForTimeout(800);
  const dn = await p.$$eval('.libx-grid .libx-card', a => a.length); ok(dn > 0 && dn < 20, 'Mocap › Dance cards ' + dn);
  // Faces chip in the same browser: story-beat faces have pictures
  await p.click('.libx-top .chips button:has-text("Faces")'); await p.waitForTimeout(1200);
  const glyph = await p.$$eval('.libx-grid .libx-card', a => a.filter(x => x.querySelector('.glyph')).map(x => x.textContent).slice(0, 5)); ok(!glyph.length, 'every face card has a picture ' + glyph);
  await p.fill('.libx-top input[type=search]', 'pout'); await p.waitForTimeout(800);
  await p.screenshot({ path: '/tmp/ds3d-visual-faces.png' });
  // Face › Expressions: mouth pictures
  await p.click('#tabs button:has-text("Face")'); await p.waitForTimeout(1500);
  const mg = await p.$$eval('.mouth-grid button', a => a.length); ok(mg >= 19, 'mouth shape pictures ' + mg);
  await p.screenshot({ path: '/tmp/ds3d-visual-face.png' });
  // Stage › Wardrobe
  await p.click('#tabs button:has-text("Stage")'); await p.waitForTimeout(1000);
  await p.click('#subtabs button:has-text("Wardrobe")'); await p.waitForTimeout(2500);
  const mc = await p.$$eval('.ws .col:nth-child(3) .libx-card img', a => a.length); ok(mc >= 5, 'mouth set pictures ' + mc);
  await p.screenshot({ path: '/tmp/ds3d-visual-wardrobe.png' });
  await p.click('#subtabs button:has-text("Co-stars")'); await p.waitForTimeout(1200);
  const cc = await p.$$eval('.char-cards .libx-card img', a => a.length); ok(cc === 3, 'character pictures ' + cc);
  await p.screenshot({ path: '/tmp/ds3d-visual-cast.png' });
  ok(!errs.length, 'no page errors ' + errs.slice(0, 3).join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.error(e); dev.kill(); process.exit(1); });
