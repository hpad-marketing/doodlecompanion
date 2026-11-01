// The 2D studio's layout in Doodle Studio 3D: docks, section chips, timeline editing, the live
// stage (models, picking, gizmo) and library previews. Run: node tools/test_ux2d.cjs
// Needs the Doodle Library (DSL_LIBRARY) and, for the 3D models, bpy (DS3D_BPY).
const { spawn } = require('child_process'), path = require('path');
const { chromium } = require('playwright');
const port = 54311;
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1032 } })).newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('dialog', d => d.accept());
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const keys = () => ev(() => Object.fromEntries(Object.entries(ds3d.project.tracks).map(([k, v]) => [k, v.map(x => x.f)])));

  // every workspace and section has content
  const empty = await ev(async () => {
    const out = [];
    for (const t of document.querySelectorAll('#tabs button')) {
      t.click(); await new Promise(r => setTimeout(r, 120));
      const chips = [...document.querySelectorAll('#subtabs .sub-chips button')];
      for (const c of chips.length ? chips : [null]) { c?.click(); await new Promise(r => setTimeout(r, 120)); if (document.querySelector('#panel-content').textContent.trim().length < 5) out.push(t.textContent + ' › ' + (c?.textContent || '')); }
    }
    return out;
  });
  ok(!empty.length, 'every tab and section shows its controls ' + empty.join(', '));
  ok(!(await ev(() => document.body.innerText.includes('nullnull'))), 'no stray "null" text');
  await p.click('#tabs button:has-text("Pose")');

  // timeline: box select, copy and paste, Clear all and undo, row remove and restore, fold
  await ev(() => { ds3d.setValues({ armR: 40, headYaw: 10 }, 0, true); ds3d.setValues({ armR: -30, headYaw: -15 }, 30, true); ds3d.setValues({ armR: 20 }, 60, true); ds3d.goto(0); });
  const row = await ev(() => { const r = document.querySelector('#tracks .trow[data-id=armR]').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; });
  const top = await ev(() => document.querySelector('#tracks .trow[data-id=headYaw]').getBoundingClientRect().top);
  await p.mouse.move(row[0] + 300, top + 4); await p.mouse.down(); await p.mouse.move(row[2] - 10, row[3] - 4, { steps: 6 }); await p.mouse.up();
  ok(await ev(() => document.querySelectorAll('#tracks .key.sel').length) === 3, 'box select picks the 3 keys after frame 0');
  await p.keyboard.press('Control+c'); await ev(() => ds3d.goto(70)); await p.mouse.click(row[0] + 200, row[3] + 60); await p.keyboard.press('Control+v');
  let k = await keys();
  ok(k.armR.join() === '0,30,60,70,100' && k.headYaw.join() === '0,30,70', 'Ctrl+C / Ctrl+V pastes the keys at the playhead');
  await p.keyboard.press('Control+a');
  ok(await ev(() => document.querySelectorAll('#tracks .key.sel').length) === 8, 'Ctrl+A selects every key');
  await p.click('#menubar .menu > button:text-is("Edit")'); await p.click('#menubar .menu-list button:has-text("Clear all keys")');
  ok(!Object.keys(await keys()).length, 'Clear all empties the shot');
  await p.keyboard.press('Control+z');
  ok((await keys()).armR?.length === 5, 'undo brings the keys back');
  await p.click('#tracks .trow[data-id=headYaw] .tname'); await p.click('#tracks .trow[data-id=headYaw] .rm');
  ok(!(await ev(() => !!document.querySelector('#tracks .trow[data-id=headYaw]'))) && await ev(() => !!document.querySelector('#tracks .trow.restore')), 'row × removes it and shows "+ 1 removed"');
  await p.click('#tracks .trow.restore .tname'); await p.click('.ctx-menu button:has-text("Bring back all")');
  ok(await ev(() => !!document.querySelector('#tracks .trow[data-id=headYaw]')), 'the removed row comes back');
  await p.dblclick('#tracks .tname.group');
  ok(!(await ev(() => !!document.querySelector('#tracks .trow[data-id=armR]'))), 'double-click folds the Bunny rows');
  await p.dblclick('#tracks .tname.group');

  // docks: detach the timeline into its own window, keys still work there, close to dock back
  const [pop] = await Promise.all([p.waitForEvent('popup'), p.click('#dock-timeline .dock-btns button')]);
  await pop.waitForTimeout(500);
  ok(await pop.evaluate(() => !!document.querySelector('#tracks .trow')), 'timeline detaches into its own window');
  await pop.click('#timeline-tools button[title^="First frame"]'); await pop.click('#timeline-tools button[title^="Next key"]');
  ok(await ev(() => ds3d.frame) === 30, 'its buttons drive the editor');
  await pop.close(); await p.waitForTimeout(400);
  ok(await ev(() => !!document.querySelector('#workspace #dock-timeline #tracks')), 'closing the window docks it back');
  await p.mouse.click(300, 600); await p.keyboard.press('Control+Shift+H');
  ok(await ev(() => document.getElementById('dock-tools').hidden), 'Ctrl+Shift+H hides the tools panel');
  await p.keyboard.press('Control+Shift+H');

  // live stage: a prop shows as a 3D model, beside Bunny, and can be picked and moved
  await ev(() => ds3d.libraryUse('scenery-gift_box'));
  await p.waitForFunction(() => ds3d.stage3d.models.get('scenery-gift_box')?.state === 'ready' || ds3d.stage3d.models.get('scenery-gift_box')?.state === 'missing', null, { timeout: 180000 });
  const state = await ev(() => ds3d.stage3d.models.get('scenery-gift_box').state);
  ok(state === 'ready', 'the gift box is converted and shown as a 3D model (' + state + ')');
  await p.waitForTimeout(300);
  const at0 = await ev(() => ds3d.project.items[0].at);
  ok(Math.abs(at0[0]) > 0.3, 'it stands beside Bunny, clear of him (x ' + at0[0] + ')');
  const pt = await ev(() => { const v = ds3d.view, o = ds3d.stage3d.items[0].obj, q = o.position.clone(); q.z += 0.15; q.project(v.camera); const r = v.canvas.getBoundingClientRect(); return [r.left + (q.x + 1) / 2 * r.width, r.top + (1 - q.y) / 2 * r.height]; });
  await p.mouse.click(pt[0], pt[1]);
  ok(await ev(() => ds3d.stage3d.selected?.type === 'item'), 'clicking it in the 3D view selects it');
  const org = await ev(() => { const v = ds3d.view, q = ds3d.stage3d.items[0].obj.position.clone().project(v.camera); const r = v.canvas.getBoundingClientRect(); return [r.left + (q.x + 1) / 2 * r.width, r.top + (1 - q.y) / 2 * r.height]; });
  // the X arrow points to screen left from the front camera
  await p.mouse.move(org[0] - 50, org[1]); await p.mouse.down(); await p.mouse.move(org[0] - 110, org[1], { steps: 6 }); await p.mouse.up();
  const at1 = await ev(() => ds3d.project.items[0].at);
  ok(Math.abs(at1[0] - at0[0]) > 0.05, `dragging the gizmo moves it (${at0[0]} → ${at1[0]})`);
  await p.keyboard.press('Control+z');
  ok((await ev(() => ds3d.project.items[0].at))[0] === at0[0], 'undo puts it back');
  await p.keyboard.press('Escape');
  ok(await ev(() => !ds3d.stage3d.selected), 'Esc clears the selection');

  // library: pointing at a motion plays it on Bunny without keying anything
  await ev(() => ds3d.setValues({}, 0, false));
  const before = Object.keys(await keys()).length;
  await p.click('#tabs button:has-text("Animate")'); await p.click('#subtabs .sub-chips button:has-text("Motion library")');
  await p.locator('#panel-content .lib-item').nth(2).hover(); await p.waitForTimeout(900);
  ok(/Preview/.test(await ev(() => document.querySelector('#preview-badge')?.textContent || '')), 'hovering a motion previews it on Bunny');
  await p.mouse.move(10, 600); await p.waitForTimeout(200);
  ok(Object.keys(await keys()).length === before, 'the preview keys nothing');

  ok(!errs.length, 'no page errors ' + [...new Set(errs)].slice(0, 3).join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e.message); process.exitCode = 1; dev.kill(); });
