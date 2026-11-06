// Blender powers: 3D doodles, scatter, crowd, liquids, fisheye, 360 video, auto-ink, jelly props,
// paper finish, transitions, linked controls, macros, master Bunny file. Run: node tools/test_batch11.cjs
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54304, out = path.join(__dirname, '..', 'devout');
for (const f of ['post-scene.json', 'render-req.json', 'master.json']) fs.rmSync(path.join(out, f), { force: true });
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.accept(d.type() === 'prompt' ? 'Toggle twice' : undefined));
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const PW = a => ev(x => ds3d.powers(x), a);
  const bridge = () => ev(() => ds3d.bridgeShot());

  let r = await PW({ action: 'info' });
  ok(!Object.keys(r.powers).length && !(await bridge()).powers, 'a fresh shot carries no powers (render cache unchanged)');

  // doodles: drawn on the frame, placed in 3D on the character's plane
  r = await PW({ action: 'doodle', strokes: [[[0.2, 0.3], [0.25, 0.25], [0.3, 0.3], [0.35, 0.25]]], frame: 5, draw: 10 });
  let pw = (await bridge()).powers;
  const d0 = pw.doodles[0];
  ok(r.added === 1 && d0.frame === 5 && d0.draw === 10 && d0.points.length >= 3 && d0.points.every(q => Math.abs(q[1]) < 1e-3 && q[2] > 0), `doodle stands upright on the character's plane: ${JSON.stringify(d0.points[0])}`);
  r = await PW({ action: 'doodle', strokes: [[[0.2, 0.3], [0.3, 0.3]]], depth: 1 });
  ok((await bridge()).powers.doodles[1].points.every(q => Math.abs(q[1] - 1) < 1e-3), 'a doodle can sit 1 m behind');

  // scatter, crowd, liquids, lens
  await PW({ action: 'scatter', kind: 'grass', count: 25, radius: 1.5 });
  await PW({ action: 'scatter', kind: 'flowers', count: 6 });
  await PW({ action: 'crowd', count: 12 });
  await PW({ action: 'liquid', kind: 'splash', frame: 8 });
  await PW({ action: 'fisheye', amount: 0.4 });
  await PW({ action: 'autoink', on: true });
  pw = (await bridge()).powers;
  ok(pw.scatter.length === 2 && pw.scatter[0].kind === 'grass' && pw.scatter[0].count === 25 && pw.crowd.count === 12 && pw.liquids[0].frame === 8 && pw.fisheye === 0.4 && pw.autoink === true, 'scatter, crowd, splash, fisheye and auto-ink reach the Blender shot');
  ok(await ev(async () => { try { await ds3d.powers({ action: 'scatter', kind: 'lava' }); return false; } catch { return true; } }), 'unknown scatter kinds are refused');
  await PW({ action: 'crowd', off: true }); await PW({ action: 'fisheye', amount: 0 }); await PW({ action: 'clear_scatter' });
  pw = (await bridge()).powers;
  ok(!pw.crowd && !pw.fisheye && !pw.scatter && pw.doodles.length === 2, 'turning powers off leaves no trace');

  // jelly prop
  ok(await ev(async () => { try { await ds3d.powers({ action: 'jelly' }); return false; } catch (e) { return /Library/.test(e.message); } }), 'jelly needs a prop first');
  await ev(() => { ds3d.project.items = [{ id: 'prop-mug', frame: 0, at: [0.5, -0.2, 0] }]; });
  r = await PW({ action: 'jelly' });
  ok(r.jelly && (await bridge()).items[0].jelly === true, 'the prop wobbles like jelly');

  // 360 video: the render goes out equirectangular
  r = await PW({ action: 'pano360', on: true });
  ok((await bridge()).powers.pano360 === 3840, '360 video on: 3840 wide');
  await ev(() => ds3d.render({ preview: true }));
  await p.waitForTimeout(300);
  const rq = JSON.parse(fs.readFileSync(path.join(out, 'render-req.json'), 'utf8'));
  ok(rq.width === 3840 && rq.height === 1920 && rq.shot.powers.pano360 === 3840, `a 360 shot renders 2:1 (${rq.width}×${rq.height})`);
  await PW({ action: 'pano360', on: false });

  // linked controls
  await ev(() => { ds3d.setValues({ armL: 0 }, 0, true); ds3d.setValues({ armL: 40 }, 20, true); });
  const base = await ev(() => { ds3d.goto(20); return ds3d.state().values.armR; });
  r = await PW({ action: 'link', from: 'armL', to: 'armR', factor: 0.5 });
  const linked = await ev(() => { ds3d.goto(20); return ds3d.state().values.armR; });
  ok(r.links.length === 1 && Math.abs(linked - base - 0.5 * (40 - (0))) < 0.6, `right arm follows the left at half: ${base.toFixed(1)} → ${linked.toFixed(1)}`);
  ok(await ev(async () => { try { await ds3d.powers({ action: 'link', from: 'armR', to: 'armL' }); return false; } catch (e) { return /loop/.test(e.message); } }), 'a loop of links is refused');
  ok(((await bridge()).frames[20].armR - linked) < 0.01, 'the render sees the linked value');
  await PW({ action: 'unlink', index: 0 });
  ok(Math.abs((await ev(() => { ds3d.goto(20); return ds3d.state().values.armR; })) - base) < 0.01, 'unlinking restores the arm');

  // transitions and paper finish on the joined scene
  await ev(() => ds3d.addShot ? ds3d.addShot() : null);
  const shots = await ev(() => ds3d.state().shots.length);
  if (shots < 2) await p.keyboard.press('Control+t');
  await ev(() => ds3d.selectShot(1));
  ok(await ev(async () => { ds3d.selectShot(0); try { await ds3d.powers({ action: 'transition', kind: 'dip' }); return false; } catch { return true; } finally { ds3d.selectShot(1); } }), 'the first shot cannot transition in');
  await PW({ action: 'transition', kind: 'dip', frames: 10, shot: 1 });
  await PW({ action: 'paper', amount: 0.5 });
  await ev(() => ds3d.renderScene({ preview: true }));
  await p.waitForTimeout(500);
  const ps = JSON.parse(fs.readFileSync(path.join(out, 'post-scene.json'), 'utf8'));
  const len0 = await ev(() => ds3d.scene.shots[0].length);
  ok(ps.transitions?.length === 1 && ps.transitions[0].at === len0 && ps.transitions[0].frames === 10 && ps.transitions[0].color === '#1F1F1D', 'dip to ink across the cut: ' + JSON.stringify(ps.transitions));
  ok(ps.paper && fs.existsSync(ps.paper.path) && ps.paper.alpha > 0.3, 'paper grain PNG written for the joined scene');

  // macros: record two menu commands, play them back
  await PW({ action: 'macro_start' });
  ok(await p.locator('#hud :text("Recording macro")').count() === 1, 'the HUD shows a macro is recording');
  const stepped0 = await ev(() => !!ds3d.project.stepped);
  for (let i = 0; i < 1; i++) {
    await p.click('#menubar .menu > button:text-is("Animate")');
    await p.click('#menubar .menu-list button:has-text("Stepped blocking on / off")');
  }
  r = await PW({ action: 'macro_stop', name: 'Toggle' });
  ok(r.steps === 1 && (await ev(() => !!ds3d.project.stepped)) !== stepped0, 'one menu command recorded');
  r = await PW({ action: 'macro_play', name: 'Toggle' });
  ok(r.ran === 1 && (await ev(() => !!ds3d.project.stepped)) === stepped0, 'playing the macro runs it again');
  r = await PW({ action: 'macros' });
  ok(r.macros.Toggle?.[0].group === 'Animate', 'macros are kept on this PC');

  // master Bunny file
  const fake = path.join(out, 'master-test.blend'); fs.writeFileSync(fake, 'BLENDER');
  r = await PW({ action: 'master', path: fake });
  ok(r.master === fake && JSON.parse(fs.readFileSync(path.join(out, 'master.json'))).masterBlend === fake, 'master Bunny file set');

  // the Blender menu and the powers dialog
  await p.click('#menubar .menu > button:text-is("Blender")');
  await p.click('#menubar .menu-list button:has-text("Powers on this shot")');
  ok(await p.locator('.ds-modal :text("Blender powers on this shot")').count() >= 1, 'powers dialog opens');
  await p.screenshot({ path: path.join(out, 'powers-dialog.png') });
  await ev(() => document.querySelectorAll('.ds-modal').forEach(m => m.remove()));
  await p.click('#menubar .menu > button:text-is("Blender")');
  await p.click('#menubar .menu-list button:has-text("Draw ink doodles in 3D")');
  ok(await p.locator('#stick-layer').count() === 1, 'doodle drawing layer opens');
  const box = await p.locator('#stick-layer').boundingBox();
  await p.mouse.move(box.x + box.width * 0.2, box.y + box.height * 0.2); await p.mouse.down();
  await p.mouse.move(box.x + box.width * 0.3, box.y + box.height * 0.25, { steps: 6 }); await p.mouse.up();
  await p.click('.stick-bar button:has-text("Place in 3D")');
  ok((await ev(() => ds3d.project.powers.doodles.length)) === 1 || (await ev(() => ds3d.project.powers?.doodles?.length)) >= 1, 'a drawn line becomes a 3D doodle');

  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
