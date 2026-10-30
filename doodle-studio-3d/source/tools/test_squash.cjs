// Squash + rack focus + line weight through Blender (fake launcher = bpy), one still.
const path = require('path');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const r = require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, libraryDir: path.join(__dirname, '..', '..', 'lib'), blender: path.join(__dirname, 'fakeblender.sh') }) }, notify: j => console.log('NOTIFY', j.id, j.state, j.rules, j.video || j.out) });
const cam = { yaw: 20, pitch: 5, dist: 2.2, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.45, focus: 2.2, fstop: 1.2 };
const shot = { fps: 30, width: 1080, height: 1920, settings: { boil_step: 3, ink_px: 19.1 }, frames: Array.from({ length: 3 }, () => ({ armL: 40, expression: 1, cam })), stage: { set: 'park' } };
console.log(r.render({ name: 'Squash Test', shot, preview: true, still: 2 }).message);
