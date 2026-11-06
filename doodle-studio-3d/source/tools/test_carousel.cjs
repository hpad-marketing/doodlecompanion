// Carousel render with the fake Blender: three slides from two shots.
const path = require('path'), fs = require('fs');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const r = require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, blender: path.join(__dirname, process.argv[2] || 'fakeblender.sh') }) },
  notify: j => console.log('NOTIFY', j.id, j.state, j.rules, j.detail || '', JSON.stringify((j.slides || []).map(f => f && path.basename(f)))) });
const cam = i => ({ yaw: i * 3, pitch: 5, dist: 3, lens: 35, roll: 0, tx: 0, ty: 0, tz: 0.52 });
const shot = (n, f) => ({ fps: 30, width: 1080, height: 1920, frames: Array.from({ length: n }, (_, i) => ({ ...f(i), cam: cam(i) })) });
const a = shot(10, i => ({ armL: 20 + i * 8 })), b = shot(10, i => ({ headYaw: i * 4, expression: 2 }));
console.log(r.renderCarousel({ name: 'Carousel Test', width: 540, height: 675, slides: [{ code: 'sh020', frame: 9, shot: b }, { code: 'sh010', frame: 3, shot: a }, { code: 'sh010', frame: 9, shot: a }] }));
