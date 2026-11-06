// Front-on wardrobe cards: every outfit and accessory in the Doodle Library, worn by Bunny, the
// Koala and the Frog, rendered straight on by Blender (the real render, not the 3D view) and
// saved to app/cards/<character>/<id>.png with app/cards/index.json. The Wardrobe shows these
// instead of the library's small side-on previews; anything without a card keeps the library picture.
// Run after the clothing studio adds an outfit or accessory:
//   DSL_LIBRARY=<Doodle Library> DS3D_BLENDER=<blender.exe> node tools/wardrobe_cards.cjs [character ...]
// (tests: DS3D_BLENDER unset and DS3D_BPY=<python with bpy 4.5> uses tools/fakeblender.sh)
const path = require('path'), fs = require('fs'), { execFileSync } = require('child_process');
const S = path.join(__dirname, '..'), OUT = path.join(S, 'app', 'cards');
const libraryDir = process.env.DSL_LIBRARY || path.join(S, '..', 'lib');
const blender = process.env.DS3D_BLENDER || path.join(__dirname, 'fakeblender.sh');
const root = path.join(S, 'devout', 'cards');
const chars = process.argv.slice(2).length ? process.argv.slice(2) : ['bunny', 'koala', 'frog'];
const lib = JSON.parse(fs.readFileSync(path.join(libraryDir, 'library.json'), 'utf8')).items;
const pieces = lib.filter(r => r.category === 'outfit' || r.category === 'accessory');
// straight on at eye level: the whole body for outfits, head and shoulders for accessories
const CAM = { outfit: { yaw: 0, pitch: 3, dist: 1.95, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.42 }, accessory: { yaw: 0, pitch: 3, dist: 1.5, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.6 } };
const r = require('../host/render.cjs')({ appDir: path.join(S, 'host'), settings: { set: () => {}, get: () => ({ rendersRoot: root, libraryDir, blender }) }, notify: () => {} });
const idle = () => new Promise(res => { const t = setInterval(() => { if (r.status().state === 'idle') { clearInterval(t); res(); } }, 1000); });
(async () => {
  const index = fs.existsSync(path.join(OUT, 'index.json')) ? JSON.parse(fs.readFileSync(path.join(OUT, 'index.json'), 'utf8')) : {};
  for (const c of chars) for (const row of pieces) {
    const stage = row.category === 'outfit' ? { outfit: row.data.outfit } : { accessories: [row.data.accessory] };
    const name = `card ${c} ${row.id}`;
    const shot = { fps: 30, width: 720, height: 960, character: c, frames: [{ cam: CAM[row.category] }], stage };
    const t = Date.now();
    r.render({ name, shot, still: 1 });
    await idle();
    const dir = path.join(root, name, 'work');
    const png = fs.readdirSync(dir, { recursive: true }).map(f => path.join(dir, f)).filter(f => /still\.png$/.test(f)).sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
    if (!png) { console.log('FAIL', c, row.id, '(no still: see', dir, ')'); process.exitCode = 1; continue; }
    const out = path.join(OUT, c, row.id + '.png');
    fs.mkdirSync(path.dirname(out), { recursive: true });
    execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-i', png, '-vf', 'scale=360:480:flags=lanczos', out]);
    (index[c] ||= {})[row.id] = `cards/${c}/${row.id}.png`;
    console.log('ok  ', c, row.id, `${((Date.now() - t) / 1000).toFixed(0)} s`);
  }
  fs.writeFileSync(path.join(OUT, 'index.json'), JSON.stringify(index, null, 1));
})().catch(e => { console.error(e); process.exit(1); });
