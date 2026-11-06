// Stills for review: Open in Blender, live both ways, in the real UI (dev server + Chromium) with a bpy stand-in
// for the Blender window (fakeblender_live.sh). Needs DS3D_BPY (a Python with bpy) and
// DSL_LIBRARY (the Doodle Library folder). Run: node tools/test_mirror.cjs  (dev server on 54293)
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54294;
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
  // pictures: the app's canvas, and Blender's camera view of the same frame (Cycles, few samples)
  const outDir = path.join(__dirname, '..', 'devout', 'mirror-stills'); fs.mkdirSync(outDir, { recursive: true });
  // a set, then the arm, prop and camera moved on the Blender side only
  await ev(() => ds3d.setStage({ set: 'bedroom' }));
  await until(() => inBlender(dir, 'import mirror\nresult = len(mirror._pieces()) or None').catch(() => null), 90000);
  await ev(() => ds3d.goto(0)); await sleep(2500);
  await inBlender(dir, 'import mirror\nfrom mathutils import Vector\nc = mirror.S["ctx"]\nvals = dict(mirror.frame_values(1)); vals.update({"armR": 120, "elbowR": 30, "armL": 10, "headYaw": -15})\nc["apply"](vals)\nob = [o for o in bpy.data.objects if "ds_item" in o.keys()][0]\nob.location = Vector((0.42, -0.1, 0))\nc["cam"].location -= Vector((0, 0, 0.4))\nresult = 1');
  await until(() => ev(() => ds3d.state()).then(s => (Math.abs(s.values.armR - 120) < 1 && Math.abs(s.items[0].at[0] - 0.42) < 0.01 ? s : null)));
  await sleep(2500);
  await p.screenshot({ path: path.join(outDir, 'app-full.png') });
  await (await p.$('#dock-canvas')).screenshot({ path: path.join(outDir, 'app-canvas.png') });
  const png = path.join(outDir, 'blender.png');
  await inBlender(dir, `sc = bpy.context.scene\nsc.frame_set(1)\nsc.render.engine = 'CYCLES'\nsc.cycles.samples = 8\nsc.cycles.device = 'CPU'\nsc.render.resolution_percentage = 40\nsc.render.filepath = ${JSON.stringify(png)}\nbpy.ops.render.render(write_still=True)\nresult = 1`);
  console.log('stills in', outDir);
  await b.close(); dev.kill(); setTimeout(() => process.exit(), 300);
})().catch(e => { console.log('FAIL', e.stack); dev.kill(); process.exit(1); });
