import fs from 'node:fs';
import { BunnyRig, decodeMesh } from '../app/src/rig.js';
const [dataPath, refPath, posesPath] = process.argv.slice(2);
const data = JSON.parse(fs.readFileSync(dataPath));
const ref = JSON.parse(fs.readFileSync(refPath));
const poses = JSON.parse(fs.readFileSync(posesPath));
const rig = new BunnyRig(data);
const meshes = data.meshes.map(decodeMesh);
let worst = 0;
for (const [name, vals] of Object.entries(poses)) {
  rig.pose(vals);
  const row = [];
  for (const m of meshes) {
    const b = Buffer.from(ref[name][m.name], 'base64');
    const R = new Float32Array(b.buffer, b.byteOffset, b.byteLength / 4);
    if (R.length !== m.count * 3) { row.push(`${m.name}:count ${R.length / 3} vs ${m.count}`); continue; }
    const D = rig.deform(m);
    let mx = 0, at = -1;
    for (let v = 0; v < m.count; v++) {
      const d = Math.hypot(D[3 * v] - R[3 * v], D[3 * v + 1] - R[3 * v + 1], D[3 * v + 2] - R[3 * v + 2]);
      if (d > mx) { mx = d; at = v; }
    }
    worst = Math.max(worst, mx);
    if (mx > 0.001) row.push(`${m.name.replace('BUNNY_', '')}:${(mx * 1000).toFixed(1)}mm`);
  }
  console.log(name.padEnd(6), row.join('  ') || 'all < 1 mm');
}
console.log('worst', (worst * 1000).toFixed(2), 'mm');
