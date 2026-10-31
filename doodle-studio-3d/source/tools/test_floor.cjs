// Floor collision: Bunny, the Koala and the Frog pushed into the floor (body sunk, a deep
// kneel, a toe dug in) must come out standing on it, ink strokes included, lead and co-star
// alike. A run with floorCollision off proves the check sees a stroke in the floor.
// Run with DS3D_BPY and DSL_LIBRARY.
const path = require('path'), fs = require('fs');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const POSES = [
  { bodyY: 40 },                                        // the whole body pushed down
  { bodyY: 25, legL: 70, kneeL: 120, kneeR: 90 },        // a deep kneel
  { bodyY: 15, footL: 35, footR: -35, bodyTilt: 12 },    // toes and heels dug in, leaning
];
const shotOf = (lead, costar, extra = {}) => ({ fps: 30, width: 540, height: 960, character: lead, ...extra,
  frames: POSES.map(p => ({ expression: 1, ...p })),
  costars: costar ? [{ character: costar, x: 0.9, y: 0.2, turn: -20, frames: POSES.map(p => ({ expression: 2, ...p })) }] : [] });
const runs = [
  ['bunny', 'koala', {}],
  ['koala', 'frog', {}],
  ['frog', 'bunny', {}],
  ['bunny', null, { floorCollision: false }],
];
let k = 0;
const next = () => {
  if (k >= runs.length) return;
  const [lead, costar, extra] = runs[k++];
  const name = `Floor ${lead}${extra.floorCollision === false ? ' off' : ''}`;
  const r = require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, blender: path.join(__dirname, 'fakeblender.sh') }) }, notify: j => {
    if (j.state === 'rendering') return;
    const dir = path.join(root, name, 'work', 'checks'), last = fs.readdirSync(dir).sort().pop();
    const rep = JSON.parse(fs.readFileSync(path.join(dir, last, 'rules.json'), 'utf8'));
    const lows = rep.frames.map(f => f.floor_low), cLows = rep.frames.map(f => (f.costar_floor_low || [])[0]);
    console.log(name, JSON.stringify({ lows, cLows }));
    if (extra.floorCollision === false) {
      ok(rep.frames.some(f => f.stroke_in_floor), 'with floor collision off the check catches strokes in the floor');
    } else {
      ok(rep.frames.length === POSES.length, `${lead}: every frame checked`);
      ok(rep.frames.every(f => !f.stroke_in_floor && !f.below_floor), `${lead}: no leg or ink stroke under the floor`);
      ok(lows.every(z => z >= 0 && z < 0.01), `${lead}: the lowest stroke stands on the floor, not floating (${lows})`);
      ok(cLows.every(z => z >= 0 && z < 0.01), `${costar} co-star: stands on the floor too (${cLows})`);
    }
    next();
  } });
  r.render({ name, shot: shotOf(lead, costar, extra), preview: true, check: true });
};
next();
