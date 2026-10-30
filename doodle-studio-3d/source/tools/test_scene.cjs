// Scene render with the fake Blender: three short shots, joined; then again to check reuse.
const path = require('path'), fs = require('fs');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
let done;
const r = require('../host/render.cjs')({ appDir, settings: { get: () => ({ rendersRoot: root, blender: path.join(__dirname, 'fakeblender.sh') }) },
  notify: j => { console.log('NOTIFY', j.id, j.state, j.rules, j.detail || '', j.video, JSON.stringify((j.shots || []).map(s => [s.code, !!s.reused]))); done(); } });
const cam = i => ({ yaw: i * 3, pitch: 5, dist: 3, lens: 35, roll: 0, tx: 0, ty: 0, tz: 0.52 });
const shot = (n, f) => ({ fps: 30, width: 1080, height: 1920, frames: Array.from({ length: n }, (_, i) => ({ ...f(i), cam: cam(i) })) });
const shots = [
  { code: 'sh010', shot: shot(6, i => ({ armL: 20 + i * 8 })) },
  { code: 'sh020', shot: shot(6, i => ({ headYaw: i * 5, turn: 30 })) },
  { code: 'sh030', shot: shot(6, i => ({ earLFold: -i * 5 })) },
];
const run = req => new Promise(ok => { done = ok; console.log(r.renderScene(req)); });
(async () => {
  const req = { name: 'Scene Test', fps: 30, width: 1080, height: 1920, preview: true, shots };
  await run(req);
  shots[1].shot.frames[0].headYaw = 40;            // change one shot only
  await run(req);
  console.log(fs.readdirSync(path.join(root, 'Scene Test', 'work', 'renders')).join(' '));
  console.log(fs.readdirSync(path.join(root, 'Scene Test', 'work', 'checks')).join(' '));
})();
