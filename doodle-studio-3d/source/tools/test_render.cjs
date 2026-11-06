const path = require('path'), fs = require('fs');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const r = require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, blender: path.join(__dirname, 'fakeblender.sh') }) }, notify: j => { console.log('NOTIFY', j.id, j.state, j.rules, j.video); } });
const shot = { fps: 30, width: 1080, height: 1920, frames: Array.from({ length: 12 }, (_, i) => ({ armL: 40 + i * 3, headYaw: i * 2, expression: 1, cam: { yaw: i * 2, pitch: 5, dist: 3, lens: 35, roll: 0, tx: 0, ty: 0, tz: 0.52 } })) };
console.log(r.render({ name: 'Test Shot', shot, preview: true }));
const t = setInterval(() => { const s = r.status(); console.log(JSON.stringify(s)); if (s.state === 'idle') { clearInterval(t); } }, 5000);
