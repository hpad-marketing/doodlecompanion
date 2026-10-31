// Polish part 3: rule lights, snapping, shot status, templates, split shot, sentence split,
// beats, review notes, custom shortcut, favourites bar, layouts, pop-out, Keydial keys.
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54299, out = path.join(__dirname, '..', 'devout'), wav = path.join(out, 'beat.wav'), voice = path.join(out, 'voice.wav');
if (!fs.existsSync(wav)) { fs.mkdirSync(out, { recursive: true }); fs.copyFileSync(path.join(__dirname, 'fixtures', 'beat.wav'), wav); }   // fresh clone
// a "voice": three phrases of tone with 0.5 s pauses (0-1.2, 1.7-2.6, 3.1-4.0 s)
{
  const sr = 16000, n = sr * 4.2, d = Buffer.alloc(44 + n * 2);
  d.write('RIFF', 0); d.writeUInt32LE(36 + n * 2, 4); d.write('WAVEfmt ', 8); d.writeUInt32LE(16, 16); d.writeUInt16LE(1, 20); d.writeUInt16LE(1, 22);
  d.writeUInt32LE(sr, 24); d.writeUInt32LE(sr * 2, 28); d.writeUInt16LE(2, 32); d.writeUInt16LE(16, 34); d.write('data', 36); d.writeUInt32LE(n * 2, 40);
  const on = t => (t < 1.2) || (t > 1.7 && t < 2.6) || (t > 3.1 && t < 4.0);
  for (let i = 0; i < n; i++) d.writeInt16LE(on(i / sr) ? Math.round(12000 * Math.sin(i / sr * 2 * Math.PI * 220)) : 0, 44 + i * 2);
  fs.writeFileSync(voice, d);
}
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.accept(d.type() === 'prompt' ? d.defaultValue() : undefined));
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const wf = a => ev(x => ds3d.workflow(x), a);

  // rule lights: rest pose is clean, a hand pushed into the head is caught
  let r = await wf({ action: 'rules', frame: 0 });
  ok(!r.clips.length && !r.belowFloor && !r.inAir, 'rest pose: no clip, grounded ' + JSON.stringify(r));
  ok(r.lifted < 0 && r.feet > 0.005 && r.feet < 0.03, 'standing: set down so the stroke rests on the floor (feet ' + r.feet + ')');
  const restFeet = r.feet;
  ok(await p.locator('#hud .rule.ok').count() === 3, 'three green rule lights in the HUD');
  await ev(() => ds3d.setValues({ armR: 170, elbowR: 150 }, 0, true));
  r = await wf({ action: 'rules' });
  ok(r.clips.some(c => /hand\.R/.test(c)), 'a hand pushed into the head is caught: ' + JSON.stringify(r.clips));
  await p.screenshot({ path: path.join(out, 'rules-bad.png') });
  ok(await p.locator('#hud .rule.bad').count() >= 1, 'a red light shows in the HUD');
  await ev(() => ds3d.undo());
  await ev(() => ds3d.setValues({ armR: 60 }, 0, true));
  ok(!(await wf({ action: 'rules' })).clips.length, 'a raised arm clear of the head stays green');
  await ev(() => ds3d.setValues({ bodyY: -30 }, 0, true));
  r = await wf({ action: 'rules' });
  ok(r.inAir && !r.belowFloor, 'lifting the body shows "in the air": feet ' + r.feet);
  await ev(() => ds3d.setValues({ bodyY: 30 }, 0, true));
  r = await wf({ action: 'rules' });
  ok(!r.belowFloor && r.feet >= 0, 'pushing him down stops at the floor (floor collision): feet ' + r.feet);
  ok(await ev(() => ds3d.view.lift > 0.05), 'the viewport lifted him back onto the floor');
  ok(Math.abs(r.feet - restFeet) < 0.002, 'and he stands at the same height as when standing normally');
  await ev(() => { ds3d.undo(); ds3d.undo(); ds3d.undo(); });

  // snapping
  await wf({ action: 'snap', on: true });
  await ev(() => ds3d.setValues({ headYaw: 13 }, 0, true));
  ok((await ev(() => ds3d.state())).values.headYaw === 15, 'snapping rounds 13° to 15°');
  await wf({ action: 'snap', on: false });

  // shot status
  r = await wf({ action: 'status', status: 'polish' });
  ok(r.status === 'polish' && await p.locator('.shot-chip.status-polish').count() === 1, 'shot status on the chip');
  await p.locator('.shot-chip').first().click({ button: 'right' });
  ok((await wf({ action: 'status' }))[0].status === 'approved', 'right-click moves it to the next status');

  // split shot keeps the motion continuous
  await ev(() => { ds3d.setValues({ armL: 0 }, 0, true); ds3d.setValues({ armL: 100 }, 100, true); });
  const before = await ev(() => [40, 60].map(f => { ds3d.goto(f); return ds3d.state().values.armL; }));
  r = await wf({ action: 'split', frame: 50 });
  let st = await ev(() => ds3d.state());
  ok(st.shots.length === 2 && st.shots[0].length === 50 && st.shots[1].length === 70, 'split at 50 makes 50 + 70 frames');
  const after = await ev(() => { ds3d.selectShot(0); ds3d.goto(40); const a = ds3d.state().values.armL; ds3d.selectShot(1); ds3d.goto(10); return [a, ds3d.state().values.armL]; });
  ok(Math.abs(after[0] - before[0]) < 0.5 && Math.abs(after[1] - before[1]) < 0.5, `motion unchanged across the split (${before} vs ${after})`);

  // templates
  r = await wf({ action: 'from_template', template: 'quick-take' });
  st = await ev(() => ds3d.state());
  ok(st.shots.length === 4 && st.shots[0].name === 'Hook' && st.shots[1].length === 540, 'quick-take template: 4 named, timed shots');

  // sentence split on a voice with two pauses
  await ev(w => ds3d.importAudio(w), voice);
  await ev(() => { ds3d.selectShot(0); ds3d.setShot({ length: 126 }); });
  r = await wf({ action: 'split_sentences', transcript: 'So I went out. It was raining. Obviously.' });
  ok(r.length === 3 && r[0].label === 'So I went out.' && Math.abs(r[0].seconds - 1.45) < 0.15 && Math.abs(r[1].seconds - 1.4) < 0.15, 'voice split into three sentence shots: ' + JSON.stringify(r));

  // beats on the beat track
  await ev(w => ds3d.importAudio(w), wav);
  await ev(() => ds3d.selectShot(0));
  r = await wf({ action: 'beats' });
  ok(r.beats.length >= 1, 'beats marked from the audio: ' + r.beats.join(','));

  // review note: draw on the frame
  await ev(() => ds3d.goto(5));
  await p.keyboard.press('n');
  const box = await p.locator('#note-draw').boundingBox();
  await p.mouse.move(box.x + 50, box.y + 60); await p.mouse.down(); await p.mouse.move(box.x + 140, box.y + 120, { steps: 6 }); await p.mouse.up();
  await p.click('.note-bar button:has-text("Done")');
  st = await ev(() => ds3d.state());
  ok(st.markers.some(m => m.f === 5 && m.sketch?.length === 1), 'review note saved as a marker with its sketch');
  ok(await p.locator('#note-layer').count() === 1, 'the note shows on its frame');
  await ev(() => ds3d.goto(20));
  ok(await p.locator('#note-layer').count() === 0, 'and hides away from it');

  // custom shortcut + favourites bar
  await ev(() => localStorage.setItem('ds3d.keys', JSON.stringify({ 'Alt+Y': 'View › Snapping on / off' })));
  await p.keyboard.press('Alt+y');
  ok((await wf({ action: 'snap', on: undefined })).snap === false, 'custom Alt+Y ran the command (then toggled back)');
  ok(await p.locator('#quickbar button').count() >= 1, 'recent command on the favourites bar');
  await p.locator('#quickbar button').first().click({ button: 'right' });
  ok(await p.locator('#quickbar button.fav').count() === 1, 'right-click pins it as a favourite');
  await p.click('#menubar .menu > button:has-text("Help")');
  await p.click('#menubar .menu-list button:has-text("Keyboard shortcuts")');
  ok(await p.locator('.ds-modal .hotkeys kbd.mine').count() === 1, 'shortcut editor shows your key');
  await p.screenshot({ path: path.join(out, 'hotkeys.png') });
  await ev(() => document.querySelectorAll('.ds-modal').forEach(m => m.remove()));

  // layouts
  await ev(() => document.body.style.setProperty('--panel-width', '520px'));
  await wf({ action: 'save_layout', name: 'Wide panel' });
  await ev(() => document.body.style.setProperty('--panel-width', '380px'));
  await wf({ action: 'use_layout', name: 'Wide panel' });
  ok(await ev(() => document.querySelector('#panel').getBoundingClientRect().width) > 500, 'saved layout restores the panel width');
  ok(await ev(() => [...document.querySelectorAll('#menubar .menu-list button')].some(b => b.textContent.includes('Layout: Wide panel'))), 'layout listed in the View menu');

  // pop-out
  const [popup] = await Promise.all([p.waitForEvent('popup'), ev(() => [...document.querySelectorAll('#menubar .menu-list button')].find(b => b.textContent.startsWith('Pop out')).click())]);
  await p.waitForTimeout(500);
  ok(await popup.evaluate(() => document.getElementById('mirror')?.width > 10), 'pop-out window mirrors the viewport');

  // Keydial keys
  await ev(() => ds3d.goto(30));
  await p.keyboard.press('Shift+ArrowRight');
  await p.keyboard.press(']');
  ok((await ev(() => ds3d.frame)) === 41, 'Shift+→ steps 10 frames and ] steps one');
  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
