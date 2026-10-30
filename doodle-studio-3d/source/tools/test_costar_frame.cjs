// A Koala co-star at x=0.8 with a tight camera on Bunny: the Blender rule check must flag
// the cut-off co-star (costar_cut), and a camera wide enough for both must pass it.
// Run with DS3D_BPY and DSL_LIBRARY.
const path = require('path'), fs = require('fs');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const shotOf = cam => ({ fps: 30, width: 1080, height: 1920, character: 'bunny',
  frames: Array.from({ length: 2 }, () => ({ expression: 1, earLScale: 100, earRScale: 100, cam })),
  costars: [{ character: 'koala', x: 0.8, y: 0, turn: -20, frames: Array.from({ length: 2 }, () => ({ expression: 1 })) }] });
const runs = [['tight', { yaw: 0, pitch: 4, dist: 2.6, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.52 }], ['wide', { yaw: 0, pitch: 4, dist: 6.5, lens: 35, roll: 0, tx: 0.4, ty: 0, tz: 0.52 }]];
let k = 0;
const next = () => {
  if (k >= runs.length) return;
  const [name, cam] = runs[k++];
  const r = require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, blender: path.join(__dirname, 'fakeblender.sh') }) }, notify: j => {
    if (j.state === 'rendering') return;
    const dir = path.join(root, 'Costar ' + name, 'work', 'checks'), last = fs.readdirSync(dir).sort().pop();
    const rep = JSON.parse(fs.readFileSync(path.join(dir, last, 'rules.json'), 'utf8')), f = rep.frames[0];
    console.log(name, JSON.stringify({ costar_cut: f.costar_cut, costar_cropped: f.costar_cropped }), j.rules);
    if (name === 'tight') ok(f.costar_cut.length === 1 && j.rules.startsWith('FAIL'), 'a co-star cut off by the frame fails the rules');
    else ok(!f.costar_cut.length, 'a framing with room for both keeps the co-star in');
    next();
  } });
  r.render({ name: 'Costar ' + name, shot: shotOf(cam), preview: true, still: 1 });
};
next();
