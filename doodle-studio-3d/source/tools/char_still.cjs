// still of a character (eye/face checks). node tools/char_still.cjs NAME character [expression] [dist] [yaw]
const path = require('path');
const appDir = path.join(__dirname, '..', 'host'), root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const [name = 'Char', character = 'bunny'] = process.argv.slice(2), expr = Number(process.argv[4] || 0), dist = Number(process.argv[5] || 1.6), yaw = Number(process.argv[6] || 0);
const r = require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, blender: path.join(__dirname, 'fakeblender.sh') }) }, notify: j => { if (j.state !== 'rendering') console.log('DONE', j.state, j.video || j.out); } });
const cam = { yaw, pitch: 2, dist, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.5 };
r.render({ name, shot: { fps: 30, width: 1080, height: 1920, character, frames: [{ expression: expr, cam }, { expression: expr, cam }] }, preview: false, still: 1 });
