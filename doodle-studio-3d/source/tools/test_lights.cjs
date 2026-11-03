// Shadows, 3-point light and per-object outlines in the editor: the default stays flat, the bands
// reach Bunny and the set, a slider previews without saving, the Outline strip, the MCP calls.
// Run: node tools/test_lights.cjs [folder for stills] (needs DSL_LIBRARY and DS3D_BPY for the park set)
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54393, stills = process.argv[2];
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 900));
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1032 } })).newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error' && !/404|Failed to load resource/.test(m.text())) errs.push(m.text()); });
  p.on('dialog', d => d.accept());
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 90000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const wait = ms => new Promise(r => setTimeout(r, ms));
  // how many different colours the frame has: flat mustard and ink stay few, bands add steps of them
  const shot = async name => { await wait(350); if (stills) await p.locator('#frame').screenshot({ path: path.join(stills, name + '.png') }); };
  const bunnyColours = () => ev(() => {
    const c = document.querySelector('#view'), g = document.createElement('canvas'); g.width = c.width; g.height = c.height;
    const x = g.getContext('2d'); x.drawImage(c, 0, 0);
    const d = x.getImageData(c.width * 0.35, c.height * 0.35, c.width * 0.3, c.height * 0.4).data, s = new Map();
    for (let i = 0; i < d.length; i += 4) { const k = (d[i] >> 3) + ',' + (d[i + 1] >> 3) + ',' + (d[i + 2] >> 3); s.set(k, (s.get(k) || 0) + 1); }
    return [...s.values()].filter(n => n > 200).length;
  });
  const call = (fn, ...a) => p.evaluate(([f, x]) => window.ds3d[f](...x), [fn, a]);
  const flat = await bunnyColours();
  await p.click('#tabs button:has-text("Stage")');
  await p.click('#subtabs button:text-is("Light")');
  await wait(200);
  await call('setStage', { set: 'park' }, false);
  await p.waitForFunction(() => { const s = ds3d.stageInfo?.(); return s ? s.ready : true; }, null, { timeout: 90000 }).catch(() => {});
  await wait(1500);
  await shot('1-flat');
  ok((await call('lighting', {})).shadows === false, 'shadows are off by default');
  await p.click('.light-ctl button:has-text("Shadows")');
  ok(await ev(() => !!ds3d.scene.stage.shadows), 'the Shadows button turns them on for the scene');
  await shot('2-shadows');
  ok(await bunnyColours() > flat || !!process.env.NO_COUNT, 'bands reach the character when shadows are on');
  await p.click('.light-ctl button:has-text("Dramatic")');
  ok(await ev(() => ds3d.scene.stage.lighting?.preset === 'dramatic' && document.querySelectorAll('.light-ctl input[type=range]').length === 8), 'a preset saves on the scene and shows its eight sliders');
  await shot('3-dramatic');
  ok(await ev(() => document.querySelectorAll('.light-ctl .chips button').length) >= 16, 'all the film lighting presets are there');
  await p.click('.light-ctl button:has-text("Rembrandt")');
  await ev(() => { const i = document.querySelector('.light-ctl input[type=text]'); i.value = 'My noir'; });
  await p.click('.light-ctl button:has-text("Save preset")');
  ok(await ev(() => !![...document.querySelectorAll('.my-light button')].find(b => b.textContent === 'My noir')), 'a setup saves as your own preset');
  await shot('3b-rembrandt');
  await p.click('.light-ctl button:has-text("Classic")');
  await shot('4-classic');
  // a slider drag previews and saves only on release
  const before = await ev(() => ds3d.scene.stage.lighting.key);
  await ev(() => { const r = document.querySelector('.light-ctl input[aria-label=Key]'); r.value = 2.5; r.dispatchEvent(new Event('input', { bubbles: true })); });
  ok(await ev(() => ds3d.scene.stage.lighting.key) === before, 'dragging a slider does not touch the saved shot');
  await ev(() => document.querySelector('.light-ctl input[aria-label=Key]').dispatchEvent(new Event('change', { bubbles: true })));
  ok(await ev(() => ds3d.scene.stage.lighting.key) === 2.5, 'letting go saves it');
  // outlines
  await call('setInk', 'flowers', 40, false);
  ok((await ev(() => ds3d.scene.stage.inks)).flowers === 40, 'set_ink stores the flowers at 40%');
  await shot('5-flowers-40');
  // click the flowers in the Stage: the Outline strip follows the selection, its slider saves on release
  await call('setInk', 'flowers', 100, false);
  const box = await p.locator('#view').boundingBox();
  await p.mouse.click(box.x + box.width * 0.075, box.y + box.height * 0.69);
  await p.waitForSelector('#ink-bar', { timeout: 4000 });
  ok(/Flowers/.test(await p.textContent('#ink-bar')), 'clicking the flowers shows their Outline strip');
  await ev(() => { const r = document.querySelector('#ink-bar input'); r.value = 40; r.dispatchEvent(new Event('input', { bubbles: true })); });
  ok(!(await ev(() => ds3d.scene.stage.inks)), 'dragging the strip previews without saving');
  await ev(() => document.querySelector('#ink-bar input').dispatchEvent(new Event('change', { bubbles: true })));
  ok((await ev(() => ds3d.scene.stage.inks))?.flowers === 40, 'letting go saves it');
  await wait(400);
  if (stills) await p.screenshot({ path: path.join(stills, '6-app.png') });
  await p.keyboard.press('Escape');
  await call('setInk', 'flowers', 100, false);
  // outlines off in a look: the Stage follows, the colours stay
  await call('materials', { action: 'apply', target: 'scene', look: 'felt', palette: 'dusk', ink: false });
  await call('materials', { action: 'apply', target: 'scene', look: 'felt', palette: 'dusk', ink: false, bunny: '#B9A9E6', outfit: '#D9744F' });
  await wait(500); await shot('7-felt-no-outlines');
  await p.click('#tabs button:has-text("Materials")'); await wait(400);
  if (stills) await p.screenshot({ path: path.join(stills, '8-materials.png') });
  ok(await ev(() => [...document.querySelectorAll('.mat-row .sub-label')].some(x => x.textContent === 'Outfit')), 'Bunny and Outfit colour rows show in Materials');
  await p.click('#tabs button:has-text("Stage")');
  const off = await ev(() => { const v = ds3d.view || null; return v ? v.objects.filter(o => o.outline).every(o => !o.outline.visible) : true; });
  ok(off, 'outlines off reaches the Stage ' + JSON.stringify(await ev(() => [ds3d.scene.materials, ds3d.project?.materials, ds3d.view?.objects?.filter(o => o.outline).map(o => o.outline.visible).slice(0, 3)])));
  // pieces and parts: the flowers from the Materials list
  await p.click('#tabs button:has-text("Materials")'); await wait(300);
  await p.waitForSelector('.part-row:has-text("Flowers")');
  ok(await p.locator('.part-row:has-text("Flowers") .part').count() === 3, 'the flowers list petals, stems and centres');
  await ev(() => { const c = document.querySelector('[aria-label="Flowers Stems"]'); c.value = '#2E8B57'; c.dispatchEvent(new Event('change', { bubbles: true })); });
  ok((await ev(() => ds3d.scene.materials.parts?.flowers?.['1'])) === '#2E8B57', 'picking a colour saves that part');
  await wait(400); await shot('9-flower-stems');
  if (stills) await p.screenshot({ path: path.join(stills, '10-parts.png') });
  await p.locator('.part-row:has-text("Flowers") button:has-text("Reset")').click();
  ok(!(await ev(() => ds3d.scene.materials.parts)), 'Reset goes back to the palette');
  await p.click('#tabs button:has-text("Stage")');
  await call('materials', { action: 'clear', target: 'scene' });
  ok(!(await ev(() => ds3d.scene.stage.inks)), '100% clears it');
  await call('lighting', { preset: 'off', shadows: false });
  ok(!(await ev(() => ds3d.scene.stage.lighting)), 'the preset goes off');
  await wait(300);
  ok(await bunnyColours() <= flat + 2, 'flat again with everything off');
  ok(!errs.length, 'no page errors ' + errs.slice(0, 3).join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e.message); process.exitCode = 1; dev.kill(); process.exit(1); });
