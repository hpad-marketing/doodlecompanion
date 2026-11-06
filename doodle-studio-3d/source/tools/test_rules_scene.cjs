// The wider 3D rule check in Blender (fake launcher = bpy): a park with the camera turned so
// set pieces are cut by the frame edge, a mug in the right hand. rules.json must list the
// scenery, held props, slivers/tangents and the horizon height. Run with DS3D_BPY and DSL_LIBRARY.
const path = require('path'), fs = require('fs');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const libraryDir = process.env.DSL_LIBRARY || path.join(__dirname, '..', '..', 'lib');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const r = require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, libraryDir, blender: path.join(__dirname, 'fakeblender.sh') }) }, notify: j => {
  if (j.state === 'rendering') return;
  const rep = JSON.parse(fs.readFileSync(path.join(j.out && fs.statSync(j.out).isDirectory() ? j.out : path.join(root, 'Rules Scene Test', 'work', 'checks', fs.readdirSync(path.join(root, 'Rules Scene Test', 'work', 'checks')).sort().pop()), 'rules.json'), 'utf8'));
  const f = rep.frames[0];
  console.log(JSON.stringify({ shot: rep.shot, frame: { slivers: f.slivers, tangents: f.tangents, scenery_touch: f.scenery_touch, scenery_near: f.scenery_near, held_in_body: f.held_in_body }, violations: rep.violations }, null, 1));
  ok(rep.shot.scenery.length >= 2, `park pieces count as scenery (${rep.shot.scenery.length})`);
  ok(rep.shot.held.some(n => /mug/i.test(n)), 'the held mug is a held prop, not scenery');
  ok(!rep.shot.scenery.some(n => /BUNNY_/.test(n)), 'the character is not scenery');
  ok(typeof rep.shot.horizon_y === 'number' && rep.shot.horizon_y > 0 && rep.shot.horizon_y < 1, 'horizon height measured: ' + rep.shot.horizon_y);
  ok(Array.isArray(f.slivers) && Array.isArray(f.tangents) && Array.isArray(f.scenery_touch) && Array.isArray(f.held_in_body), 'every frame reports slivers, tangents, touches, held props');
  // B16: the set hides the pieces this camera would crop to slivers, so none are left
  ok(f.slivers.length === 0, 'pieces the turned camera would crop to slivers are hidden: ' + (f.slivers.join('; ') || 'none left'));
  ok(f.held_in_body.every(t => !/head/i.test(t)), 'the held mug stays out of his head: ' + (f.held_in_body.join('; ') || 'clear'));
} });
const cam = { yaw: 35, pitch: 4, dist: 3.2, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.52 };
const shot = { fps: 30, width: 1080, height: 1920, character: 'bunny',
  frames: Array.from({ length: 3 }, () => ({ armR: 30, elbowR: 60, expression: 1, earLScale: 100, earRScale: 100, cam })),
  stage: { set: 'park' }, items: [{ id: 'prop-mug', frame: 0, hold: 'R' }] };
console.log(r.render({ name: 'Rules Scene Test', shot, preview: true, still: 2, check: true }).message);
const t = setInterval(() => { if (r.status().state === 'idle') clearInterval(t); }, 2000);
