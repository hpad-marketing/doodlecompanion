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
  if (k >= runs.length) {
    // the floor you see is the base (a raised set floor counts; props, tables and outlines never do), straight in Blender
    const py = require('child_process').spawnSync(process.env.DS3D_BPY || 'python3', [path.join(__dirname, 'floor_raised.py')], { encoding: 'utf8' });
    for (const line of (py.stdout || '').split('\n')) if (/^(ok|FAIL)/.test(line)) { console.log(line); if (line.startsWith('FAIL')) process.exitCode = 1; }
    ok(py.status === 0, 'raised-floor checks ran');
    return;
  }
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
      ok(F.some(f => f.shell_low < -0.002), 'and it sees the shell under the floor too');
    } else {
      const dug = [1, 2, 3];   // the poses that would go into the floor
      ok(F.length === POSES.length + 1, `${label}: every frame checked`);
      ok(F.every(f => !f.stroke_in_floor && !f.below_floor), `${label}: no leg or ink stroke under the floor`);
      const shells = F.map(f => f.shell_low);
      ok(shells.every(z => z != null && z >= -0.002), `${label}: the outline shell, as it renders, stays on top of the floor too (${shells})`);
      ok(dug.every(i => F[i].floor_low >= 0 && F[i].floor_low < 0.003), `${label}: ${lead} is lifted only by the depth it went in, no float (${lows})`);
      const lifts = JSON.parse(fs.readFileSync(path.join(dir, last, 'floor.json'), 'utf8'));
      const moved = f => (lifts.lead || []).some(x => x.frame === f && x.cm !== 0) || (lifts.costars || []).some(c => (c.lifts || []).some(x => x.frame === f && x.cm !== 0));
      ok(F[0].floor_low > 0.005 && !moved(1) && !moved(JUMP + 1), `${label}: standing and jumping are never moved (stroke ${F[0].floor_low} above the floor)`);
      ok(F[JUMP].floor_low > 0.05, `${label}: a jump keeps its height (${F[JUMP].floor_low})`);
      costars.forEach((c, n) => {
        const lo = cLows.map(x => x[n]);
        ok(dug.every(i => lo[i] >= 0 && lo[i] < 0.003) && lo[0] > 0.005, `${label}: co-star ${n + 1} (${c}) lifted only where it dug in (${lo})`);
      });
    }
    next();
  } });
  r.render({ name, shot: shotOf(lead, costars, extra, cam), preview: true, check: true });
};
next();
