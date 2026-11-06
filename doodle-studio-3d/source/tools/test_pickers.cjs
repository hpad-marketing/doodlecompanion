// The last text pickers are pictures: Co-stars › library motions are animated motion cards (search,
// family chips, pick + play, double-click plays), and the Wardrobe shows front-on cards rendered by
// Blender for the lead character, falling back to the library picture.
// Run: DSL_LIBRARY=<Doodle Library folder> node tools/test_pickers.cjs
const { spawn } = require('child_process'), path = require('path');
const { chromium } = require('playwright');
const port = 54299, S = path.join(__dirname, '..');
const dev = spawn('node', [path.join(S, 'tools/dev.cjs'), String(port)], { stdio: 'ignore', env: { ...process.env, DSL_LIBRARY: process.env.DSL_LIBRARY || path.join(S, '..', 'lib') } });
const ok = (c, m) => { console.log(c ? 'ok  ' : 'FAIL', m); if (!c) process.exitCode = 1; };
(async () => {
  await new Promise(r => setTimeout(r, 900));
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.accept());
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  await p.waitForTimeout(2000);
  const ev = (fn, ...a) => p.evaluate(fn, ...a);

  // ---- Co-stars: motions as moving pictures
  await ev(() => ds3d.cast({ action: 'add', character: 'koala' }));
  await p.click('#tabs button:has-text("Stage")'); await p.waitForTimeout(600);
  await p.click('#subtabs button:has-text("Co-stars")'); await p.waitForTimeout(600);
  await p.click('#panel-content button:has-text("Co-stars…")'); await p.waitForTimeout(1500);
  ok(!(await p.$('.ds-modal select[aria-label="Motion"]')), 'no motion dropdown left in the Co-stars dialog');
  const n = await p.$$eval('.ds-modal .motion-picker .libx-card', a => a.length);
  const anim = await p.$$eval('.ds-modal .motion-picker .libx-card .anim', a => a.length);
  ok(n >= 12, 'motion cards shown: ' + n);
  ok(anim === n, `every card on the first page moves: ${anim} of ${n}`);
  const h0 = await p.$eval('.ds-modal .motion-picker .libx-card .anim', a => a.getBoundingClientRect().height);
  ok(h0 >= 100, 'motion pictures are big enough to read: ' + Math.round(h0) + ' px tall');
  await p.screenshot({ path: path.join(S, 'devout', 'pickers-costar.png') });
  await p.fill('.ds-modal .motion-picker input[type=search]', 'wave'); await p.waitForTimeout(400);
  const waves = await p.$$eval('.ds-modal .motion-picker .libx-card', a => a.map(x => x.textContent));
  ok(waves.length > 0 && waves.every(t => /wave/i.test(t)), 'search narrows to waves: ' + waves.slice(0, 4).join(', '));
  const chips = await p.$$eval('.ds-modal .motion-picker .chips button', a => a.map(x => x.textContent));
  ok(chips[0] === 'All' && chips.length >= 2, 'family chips ' + chips.join(' / '));
  await p.click('.ds-modal .motion-picker .libx-card >> nth=0'); await p.waitForTimeout(200);
  const label = await p.textContent('.ds-modal .costar-motions button.primary');
  ok(/^Play “.+” from the playhead$/.test(label), 'picking a card names it on the play button: ' + label);
  const before = await ev(() => JSON.stringify(ds3d.project.costars?.[0]?.tracks || {}).length);
  await p.click('.ds-modal .costar-motions button.primary'); await p.waitForTimeout(1500);
  const after = await ev(() => JSON.stringify(ds3d.project.costars?.[0]?.tracks || {}).length);
  ok(after > before, `the picked motion is keyed on the co-star (${before} → ${after} chars of keys)`);
  ok(!(await p.$('.ds-modal')), 'the dialog closes after playing');

  // ---- Wardrobe: front-on cards for the lead
  await p.click('#subtabs button:has-text("Wardrobe")'); await p.waitForTimeout(2500);
  const ward = await p.$$eval('.wardrobe-card', a => a.map(x => ({ id: x.dataset.id, src: x.querySelector('img')?.getAttribute('src') || '', w: x.querySelector('img')?.naturalWidth || 0 })));
  const outfits = ward.filter(x => /^outfit-/.test(x.id)), accs = ward.filter(x => /^accessory-/.test(x.id));
  ok(outfits.length >= 1 && accs.length >= 1, `outfit and accessory cards: ${outfits.length} + ${accs.length}`);
  const fromCards = await ev(async () => { const r = await fetch('cards/index.json'); return r.ok ? r.json() : {}; });
  const expected = ward.filter(x => fromCards.bunny?.[x.id]).length;
  ok(expected === outfits.length + accs.length, `every wardrobe piece has a front-on card (${expected} of ${outfits.length + accs.length})`);
  ok(ward.every(x => x.w > 0), 'every wardrobe card has a picture');
  ok(await p.$eval('.wardrobe-card[data-id=""] img', i => i.naturalWidth > 0), 'the default look shows the character itself');
  const tall = await p.$$eval('.ds-modal .motion-picker .anim', a => a.length);
  ok(tall === 0, 'dialog closed');
  await p.screenshot({ path: path.join(S, 'devout', 'pickers-wardrobe.png') });
  ok(!errs.length, 'no page errors ' + errs.slice(0, 3).join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.error(e); dev.kill(); process.exit(1); });
