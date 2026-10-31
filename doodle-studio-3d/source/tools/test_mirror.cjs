// Open in Blender, live both ways, in the real UI (dev server + Chromium) with a bpy stand-in
// for the Blender window (fakeblender_live.sh). Needs DS3D_BPY (a Python with bpy) and
// DSL_LIBRARY (the Doodle Library folder). Run: node tools/test_mirror.cjs  (dev server on 54293)
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54293;
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'inherit' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const liveDir = name => path.join(__dirname, '..', 'devout', 'DeepInDoodles', name, 'work', 'blender-live');
// run python inside the stand-in Blender (the harness execs it; `result` comes back)
async function inBlender(dir, code) {
  const f = path.join(dir, 'cmd.json');
  try { fs.unlinkSync(f + '.done'); } catch {}
  fs.writeFileSync(f, JSON.stringify({ code }));
  for (let i = 0; i < 400; i++) {
    await sleep(50);
    if (fs.existsSync(f + '.done')) { const r = JSON.parse(fs.readFileSync(f + '.done', 'utf8')); fs.unlinkSync(f + '.done'); if (!r.ok) throw Error(r.error); return r.result; }
  }
  throw Error('Blender stand-in did not answer');
}
async function until(fn, ms = 8000) { const t = Date.now(); let v; while (Date.now() - t < ms) { v = await fn(); if (v) return v; await sleep(100); } return v; }

(async () => {
  await sleep(800);
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const name = 'Mirror Test ' + Date.now().toString(36);
  await ev(n => { ds3d.scene.name = n; }, name);
  await ev(() => ds3d.setShot({ length: 40 }));
  await ev(() => ds3d.libraryUse('prop-mug', { frame: 0, at: [0.6, 0, 0] }));
  await ev(() => ds3d.setValues({ armL: 30 }, 0, true));

  ok(await p.isVisible('#blender-live'), 'Open in Blender button above the canvas');
  ok((await p.textContent('#blender-live')).includes('Open in Blender'), 'button reads "Open in Blender"');
  await p.click('#blender-live');
  const live = await until(async () => (await p.textContent('#blender-live')).includes('Blender live'), 90000);
  ok(live, 'button turns to "● Blender live" once Blender has the shot');
  const dirs = fs.readdirSync(liveDir(name));
  const dir = path.join(liveDir(name), dirs[0]);
  ok(fs.existsSync(path.join(dir, dirs[0] + '_live.blend')), 'Blender works on its own copy in work\\blender-live');

  // app -> Blender: a pose value, the camera, the playhead
  await ev(() => ds3d.setValues({ armL: 90, headYaw: 20 }, 0, true));
  let v = await until(() => inBlender(dir, 'import mirror\nresult = mirror.rig_values(mirror.S["ctx"])').then(r => (Math.abs(r.armL - 90) < 0.5 && Math.abs(r.headYaw - 20) < 0.5 ? r : null)));
  ok(v, 'app pose shows up on the Blender rig: armL ' + (v && v.armL.toFixed(2)) + ', headYaw ' + (v && v.headYaw.toFixed(2)));
  await ev(() => ds3d.setValues({ 'cam.yaw': 30 }, 0, true));
  v = await until(() => inBlender(dir, 'import mirror\nresult = mirror.cam_values(mirror.S["ctx"], {"dist": 3})').then(r => (Math.abs(r.yaw - 30) < 0.5 ? r : null)));
  ok(v, 'app camera orbit shows up on the Blender camera: yaw ' + (v && v.yaw.toFixed(2)));
  await ev(() => ds3d.goto(12));
  v = await until(() => inBlender(dir, 'result = bpy.context.scene.frame_current').then(f => (f === 13 ? f : null)));
  ok(v === 13, 'app playhead 12 = Blender frame 13');
  // keys reached every frame: frame 0 still has armL 90 in Blender after scrubbing back
  await ev(() => ds3d.goto(0));
  v = await until(() => inBlender(dir, 'import mirror\nresult = mirror.rig_values(mirror.S["ctx"])').then(r => (Math.abs(r.armL - 90) < 0.5 ? r : null)));
  ok(v, 'Blender keys follow the app keys (armL 90 back at frame 0)');

  // Blender -> app: turn a bone, move the prop, move the camera, change frame
  await inBlender(dir, 'import mirror, ds_map\nc = mirror.S["ctx"]\nvals = dict(mirror.frame_values(bpy.context.scene.frame_current)); vals["armR"] = 60; vals["elbowR"] = 45\nc["apply"](vals)\nresult = 1');
  let st = await until(() => ev(() => ds3d.state()).then(s => (Math.abs(s.values.armR - 60) < 1 && Math.abs(s.values.elbowR - 45) < 1 ? s : null)));
  ok(st, 'a bone turned in Blender becomes the app\'s control values: armR ' + (st && st.values.armR) + ', elbowR ' + (st && st.values.elbowR));
  ok(st && st.keyed.armR?.some(k => k[0] === 0), 'and is keyed at the playhead (Keys: Auto)');
  await inBlender(dir, 'ob = [o for o in bpy.data.objects if "ds_item" in o.keys()][0]\nob.location.x += 0.5\nob.rotation_euler.z = 0.5\nresult = list(ob.location)');
  st = await until(() => ev(() => ds3d.state()).then(s => (s.items[0]?.at && Math.abs(s.items[0].at[0] - 1.1) < 0.01 ? s : null)));
  if (!st) console.log('debug items', JSON.stringify(await ev(() => ds3d.state().items)), JSON.stringify(await inBlender(dir, 'import mirror\nob = [o for o in bpy.data.objects if "ds_item" in o.keys()][0]\nresult = [list(ob.location), ob.name, {k: list(v) for k, v in mirror.S["item_off"].items()}]')));
  ok(st, 'prop moved in Blender moves in the app: at ' + JSON.stringify(st && st.items[0].at) + ' rot ' + JSON.stringify(st && st.items[0].rot));
  await inBlender(dir, 'import mirror\nfrom mathutils import Vector\ncam = mirror.S["ctx"]["cam"]\ncam.location += Vector((0, 0, 0.4))\nbpy.context.view_layer.update()\nresult = 1');
  st = await until(() => ev(() => ds3d.state()).then(s => (Math.abs(s.values['cam.tz'] - 0.92) < 0.02 ? s : null)));
  ok(st, 'camera raised in Blender raises the app camera aim: cam.tz ' + (st && st.values['cam.tz']));
  await inBlender(dir, 'bpy.context.scene.frame_set(21)\nresult = 1');
  st = await until(() => ev(() => ds3d.state()).then(s => (s.frame === 20 ? s : null)));
  ok(st, 'Blender frame 21 = app playhead 20');
  // one undo step per burst of Blender edits
  const hist = await ev(() => ds3d.production({ action: 'history' }));
  ok(JSON.stringify(hist).includes('Blender:'), 'Blender edits are named in the undo history');

  // no echo: after things settle, nothing keeps flowing
  await sleep(1500);
  const before = await ev(() => JSON.stringify(ds3d.project.tracks));
  await sleep(1500);
  ok(before === (await ev(() => JSON.stringify(ds3d.project.tracks))), 'no feedback loop: the keys stay still once both sides agree');

  // a new prop is a rebuild: Blender builds the shot again with both
  await ev(() => ds3d.libraryUse('prop-book', { frame: 0, at: [-0.6, 0, 0] }));
  v = await until(() => inBlender(dir, 'result = len([o for o in bpy.data.objects if "ds_item" in o.keys()])').then(n => (n === 2 ? n : null)).catch(() => null), 60000);
  ok(v === 2, 'a prop added in the app appears in Blender (shot rebuilt)');
  v = await until(() => inBlender(dir, 'import mirror\nresult = mirror.rig_values(mirror.S["ctx"])').then(r => (Math.abs(r.armR - 60) < 0.5 ? r : null)).catch(() => null), 20000);
  ok(v, 'the rebuilt shot keeps the pose made in Blender');

  // a set: its pieces move both ways, and the sun turned in Blender is kept for the render
  await ev(() => ds3d.setStage({ set: 'bedroom' }));
  const pieces = await until(() => inBlender(dir, 'import mirror\nps = mirror._pieces()\nresult = sorted({o["dsl_prop"] for o in ps}) if ps else None').catch(() => null), 90000);
  ok(pieces && pieces.length > 2, 'the set is built in Blender: ' + (pieces || []).length + ' pieces');
  const pid = pieces && pieces[0];
  await inBlender(dir, `import mirror\nfor o in mirror._pieces():\n    if o["dsl_prop"] == ${JSON.stringify(pid)}:\n        o.location.y += 0.3\n        break\nresult = 1`);
  st = await until(() => ev(() => ds3d.state()).then(s => { const xf = s.stage.pieces?.[pid]; return xf && Math.abs(xf.at[1] - 0.3) < 0.01 ? s : null; }));
  ok(st, `set piece ${pid} moved in Blender moves in the app: ${JSON.stringify(st && st.stage.pieces[pid])}`);
  // as the Move gizmo does it (editPiece): the scene's stage pieces
  await ev(id => { const st = ds3d.project.stage?.pieces ? ds3d.project.stage : ds3d.scene.stage; st.pieces = { ...(st.pieces || {}), [id]: { at: [0.5, 0.3, 0], rot: 0, scale: 1 } }; ds3d.goto(ds3d.frame); }, pid);
  v = await until(() => inBlender(dir, `import mirror\nb = [(o.location - mirror.S["piece_base"][o.name][0]).x for o in mirror._pieces() if o["dsl_prop"] == ${JSON.stringify(pid)}]\nresult = b`).then(r => (r.length && r.every(x => Math.abs(x - 0.5) < 0.01) ? r : null)).catch(() => null), 15000);
  ok(v, 'set piece moved in the app moves every part of it in Blender');
  const sun = await inBlender(dir, 'import mirror\ns = mirror._sun()\nif s:\n    s.rotation_euler.x += 0.3\nresult = bool(s)');
  if (sun) {
    st = await until(() => ev(() => ds3d.state()).then(s => (s.stage.sun?.rot ? s : null)));
    ok(st, 'the sun turned in Blender is saved with the stage: ' + JSON.stringify(st && st.stage.sun));
    const br = await ev(() => ds3d.bridgeShot());
    ok(br.stage?.sun?.rot, 'and goes to the render');
  } else console.log('note: this set has no DSL_Sun');

  // stop: Blender is told and the button goes back
  await p.click('#blender-live');
  ok(await until(async () => (await p.textContent('#blender-live')).includes('Open in Blender')), 'clicking the live button stops the link');
  ok(!errs.length, 'no page errors' + (errs.length ? ': ' + errs.slice(0, 3).join(' | ') : ''));
  await p.screenshot({ path: path.join(__dirname, '..', 'devout', 'mirror-test.png') });
  await b.close();
  dev.kill();
  setTimeout(() => process.exit(), 300);
})().catch(e => { console.log('FAIL', e.stack); dev.kill(); process.exit(1); });
