// Six characters on stage (the lead plus five co-stars): one still for a visual check.
const path = require('path');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const chars = ['koala', 'frog', 'bunny', 'koala', 'frog'];
const costars = chars.map((character, n) => {
  const side = n % 2 ? -1 : 1, x = side * (0.8 + Math.floor(n / 2) * 0.7);
  return { character, x, y: 0.15 * Math.floor(n / 2), turn: -side * 20, frames: [{ expression: 1 + n * 7 }] };
});
const shot = { fps: 30, width: 1080, height: 1920, character: 'bunny',
  frames: [{ expression: 1, earLScale: 100, earRScale: 100, cam: { yaw: 0, pitch: 0, dist: 11, lens: 35, roll: 0, tx: 0, ty: 0, tz: 0.55 } }], costars };
require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, blender: path.join(__dirname, 'fakeblender.sh') }) },
  notify: j => console.log(j.state || '', j.message || '', j.out || j.file || '') }).render({ name: 'Six on stage', shot, preview: true, still: 1 });
