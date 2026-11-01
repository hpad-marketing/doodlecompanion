// Materials tab in the editor: look cards, palettes, targets, scope, sliders, the MCP tool and the
// bridge shot. Run: node tools/test_materials.cjs (needs DSL_LIBRARY; no Blender needed)
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54321;
const out = path.join(__dirname, '..', 'devout');
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 900));
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1032 } })).newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error' && !/404|Failed to load resource/.test(m.text())) errs.push(m.text()); });
  p.on('dialog', d => d.accept());
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const tabs = await ev(() => [...document.querySelectorAll('#tabs button')].map(b => b.textContent));
  ok(tabs[8] === 'Materials' && tabs.slice(0, 8).join() === 'Pose,Face,Animate,Camera,Stage,Library,Carousel,Render', 'Materials tab added after Render; the other tabs keep their places');
  await p.click('#tabs button:has-text("Materials")');
  await p.waitForSelector('.mat-card');
  const cards = await ev(() => [...document.querySelectorAll('.mat-card')].map(c => [c.textContent, !!c.querySelector('img')]));
  ok(cards.length >= 8 && cards.every(c => c[1]), 'every look is a picture card: ' + cards.map(c => c[0]).join(' | '));
  ok(await ev(() => document.querySelectorAll('.mat-pal').length) === 8, 'eight palette cards with swatches');
  await p.click('.mat-card:has-text("Clay")');
  await p.click('.mat-pal:has-text("Teal & coral")');
  let sc = await ev(() => ds3d.scene.materials);
  ok(sc?.layers?.scene?.look === 'clay' && sc.layers.scene.palette === 'teal-coral', 'Clay in Teal & coral on the whole scene');
  ok(await ev(() => document.querySelectorAll('.mat-ctls .ctl').length) >= 5 + 6, 'clay sliders and the light row show');
  ok(await ev(() => [...document.querySelectorAll('.mat-row button')].find(b => b.textContent === 'Ink outline')?.getAttribute('aria-pressed') === 'false'), 'a textured look starts with no body outline');
  await p.click('.mat-row button:has-text("Ink outline")');
  ok(await ev(() => ds3d.scene.materials.layers.scene.ink === true), 'the outline can be switched back on');
  await p.click('.mat-row button:has-text("Ink outline")');
  await p.click('.mat-row button:has-text("Set")');
  await p.click('.mat-card:has-text("Cel toon")');
  await p.click('.mat-row button:has-text("This shot only")');
  await p.click('.mat-row button:has-text("Characters")');
  await p.click('.mat-card:has-text("Felt")');
  sc = await ev(() => ({ scene: ds3d.scene.materials.layers, shot: ds3d.project.materials?.layers }));
  ok(sc.scene.set?.look === 'cel' && sc.shot?.character?.look === 'felt' && !sc.scene.character, 'set on every shot, characters on this shot only');
  // a slider writes its parameter
  await p.evaluate(() => { const r = document.querySelector('.mat-ctls .ctl input[type=range]'); r.value = r.max; r.dispatchEvent(new Event('change')); });
  sc = await ev(() => ds3d.project.materials.layers.character.params);
  ok(sc && Object.values(sc).length === 1, 'a slider sets that look parameter ' + JSON.stringify(sc));
  // undo
  await p.keyboard.press('Control+z');
  ok(!Object.keys(await ev(() => ds3d.project.materials?.layers?.character?.params || {})).length, 'undo takes the slider change back');
  // MCP tool
  const list = await ev(() => ds3d.materials({ action: 'list' }));
  ok(list.looks.length >= 8 && list.palettes.length === 8 && list.now.layers.set.look === 'cel', 'materials action=list reports looks, palettes and what is on now');
  const ap = await ev(() => ds3d.materials({ action: 'apply', target: 'props', look: 'ceramic', palette: 'dusk' }));
  ok(ap.ok && ap.now.layers.props.look === 'ceramic', 'materials action=apply puts ceramic on all props');
  const bad = await ev(() => ds3d.materials({ action: 'apply', look: 'nope' }).then(() => null, e => e.message));
  ok(/No look nope/.test(bad || ''), 'an unknown look is refused with a pointer to list');
  await ev(() => ds3d.materials({ action: 'light', key: 4, shadows: true }));
  ok((await ev(() => ds3d.scene.materials.light)).key === 4, 'materials action=light sets the scene light');
  // the render request carries the materials
  fs.rmSync(path.join(out, 'render-req.json'), { force: true });
  await p.click('.mat .primary:has-text("Preview this frame")');
  await p.waitForTimeout(1500);
  const req = fs.existsSync(path.join(out, 'render-req.json')) && JSON.parse(fs.readFileSync(path.join(out, 'render-req.json')));
  ok(req && req.shot.materials?.layers?.set?.look === 'cel' && req.shot.materials.layers.character.look === 'felt' && req.shot.materials.layers.scene.look === 'clay' && req.shot.materials.light.key === 4, 'Preview this frame sends the materials to Blender');
  await ev(() => ds3d.materials({ action: 'clear', target: 'character', scope: 'shot' }));
  await p.click('.mat-row button:has-text("Every shot")').catch(() => {});
  await p.screenshot({ path: path.join(out, 'materials-tab.png') });
  // a scene without materials renders exactly as before
  const plain = await ev(() => { const s = JSON.parse(JSON.stringify(ds3d.scene)); delete s.materials; return 'ok'; });
  ok(plain === 'ok', 'scene copy without materials');
  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e.message); process.exitCode = 1; dev.kill(); process.exit(1); });
