// Floor contact: the lowest ink stroke of every character rests on the floor, never in it and
// never floating above it. Bunny, the Koala and the Frog stand, sink, kneel and dig a toe in,
// as lead and co-star, at eye level, from overhead and in a crowd of Bunnies; a jump keeps
// its height. A run with floorCollision off proves the check sees strokes in the floor.
// Run with DS3D_BPY and DSL_LIBRARY.
const path = require('path'), fs = require('fs');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const POSES = [
  {},                                                   // standing
  { bodyY: 40 },                                        // the whole body pushed down
  { bodyY: 25, legL: 70, kneeL: 120, kneeR: 90 },        // a deep kneel
  { bodyY: 15, footL: 35, footR: -35, bodyTilt: 12 },    // toes and heels dug in, leaning
];
const JUMP = 4;                                         // frame 5: off the ground
const OVERHEAD = { yaw: 20, pitch: 62, dist: 4.2, lens: 35, roll: 0, tx: 0.3, ty: 0, tz: 0.3 };
const shotOf = (lead, costars, extra = {}, cam = null) => ({ fps: 30, width: 540, height: 960, character: lead, ...extra,
  frames: [...POSES, { bodyY: -30 }].map(p => ({ expression: 1, ...p, ...(cam ? { cam } : {}) })),
  costars: costars.map((c, i) => ({ character: c, x: 0.9 * (i % 2 ? -1 : 1) * (1 + (i >> 1)), y: 0.2 + 0.5 * (i >> 1), turn: -20,
    frames: [...POSES, { bodyY: -30 }].map(p => ({ expression: 2, ...p })) })) });
const runs = [
  ['bunny', ['koala'], {}, null, 'eye level'],
  ['koala', ['frog'], {}, null, 'eye level'],
  ['frog', ['bunny'], {}, null, 'eye level'],
  ['bunny', ['bunny', 'bunny'], {}, OVERHEAD, 'overhead, three Bunnies'],
  ['bunny', [], { floorCollision: false }, null, 'collision off'],
];
let k = 0;
const next = () => {
  if (k >= runs.length) return;
  const [lead, costars, extra, cam, label] = runs[k++];
  const name = `Floor ${k} ${lead}`;
  const r = require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, blender: path.join(__dirname, 'fakeblender.sh') }) }, notify: j => {
    if (j.state === 'rendering') return;
    const dir = path.join(root, name, 'work', 'checks'), last = fs.readdirSync(dir).sort().pop();
    const rep = JSON.parse(fs.readFileSync(path.join(dir, last, 'rules.json'), 'utf8')), F = rep.frames;
    const gaps = F.map(f => f.floor_gap), lows = F.map(f => f.floor_low);
    const cGaps = F.map(f => f.costar_floor_gap || []), cLows = F.map(f => f.costar_floor_low || []);
    console.log(`${label} (${lead} + ${costars.join(', ') || 'none'})`, JSON.stringify({ lows, gaps, cLows, cGaps }));
    if (extra.floorCollision === false) {
      ok(F.some(f => f.stroke_in_floor), 'with floor collision off the check catches strokes in the floor');
    } else {
      const ground = F.filter((f, i) => i !== JUMP);
      ok(F.length === POSES.length + 1, `${label}: every frame checked`);
      ok(F.every(f => !f.stroke_in_floor && !f.below_floor), `${label}: no leg or ink stroke under the floor`);
      ok(ground.every(f => f.floor_low >= 0 && f.floor_low < 0.003), `${label}: ${lead}'s lowest stroke rests on the floor, no float gap (${lows})`);
      ok(F.every(f => !f.floating) && ground.every(f => Math.abs(f.floor_gap) < 0.003), `${label}: ${lead} never floats (gaps ${gaps})`);
      ok(F[JUMP].floor_low > 0.05, `${label}: a jump keeps its height (${F[JUMP].floor_low})`);
      costars.forEach((c, n) => {
        const lo = cLows.map(x => x[n]), gp = cGaps.map(x => x[n]);
        ok(lo.every((z, i) => i === JUMP || (z >= 0 && z < 0.003)) && gp.every((g, i) => i === JUMP || Math.abs(g) < 0.003), `${label}: co-star ${n + 1} (${c}) rests on the floor too (${lo})`);
      });
    }
    next();
  } });
  r.render({ name, shot: shotOf(lead, costars, extra, cam), preview: true, check: true });
};
next();
