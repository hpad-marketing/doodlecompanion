// Materials tab, host side: the look list (built-in + an add-on dropped in <library>\looks), the
// one-frame test before an add-on look can be used (pass and fail), and the bridge shot carrying
// the add-on folders. Needs DS3D_BPY (bpy 4.5) and DSL_LIBRARY. Run: node tools/test_looks.cjs
const path = require('path'), fs = require('fs'), os = require('os');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const lib = process.env.DSL_LIBRARY;
const host = path.join(__dirname, '..', 'host');
fs.mkdirSync(path.join(lib, 'looks'), { recursive: true });
fs.cpSync(path.join(__dirname, 'fixtures', 'looks', 'test_look'), path.join(lib, 'looks', 'test_look'), { recursive: true });
const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ds3d-looks-'));
const L = require('../host/looks.cjs')({ appDir: host, settings: { get: () => ({ libraryDir: lib }) }, dataDir, blender: () => path.join(__dirname, 'fakeblender.sh') });
const wait = key => new Promise(r => { const t = setInterval(() => { const l = L.list().looks.find(x => x.key === key); if (l.status !== 'testing') { clearInterval(t); r(l); } }, 1000); });
(async () => {
  const a = L.list();
  ok(a.looks.filter(l => l.source === 'built-in').length === 9, 'nine built-in looks (plush included)');
  ok(a.looks.every(l => l.source !== 'built-in' || l.preview?.startsWith('data:image/png')), 'built-in looks have pictures');
  ok(a.palettes.length === 16, 'sixteen palettes');
  const g = a.looks.find(l => l.key === 'test_look:glow');
  ok(g && g.status === 'untested' && g.source === 'library', 'an add-on dropped in the library looks folder is found, untested');
  ok(L.addonDirs().test_look === path.join(lib, 'looks'), 'the bridge learns where the add-on lives');
  L.test({ key: 'test_look:glow' });
  const g2 = await wait('test_look:glow');
  ok(g2.status === 'ok' && g2.preview, 'its test frame passes and becomes its picture ' + (g2.error || ''));
  L.test({ key: 'test_look:broken' });
  const b2 = await wait('test_look:broken');
  ok(b2.status === 'failed' && /broken on purpose/.test(b2.error || ''), 'a look that errors fails its test and says why: ' + b2.error);
  const r = require('../host/render.cjs')({ appDir: host, settings: { get: () => ({ libraryDir: lib, rendersRoot: dataDir }) }, notify: () => {} });
  const s = r.withMaster({ frames: [], materials: { layers: { scene: { look: 'glow', addon: 'test_look' } } } });
  ok(s.materials.addons.test_look && s.materials.addons.doodle_looks, 'render shots carry the add-on folders');
  ok(r.withMaster({ frames: [] }).materials === undefined, 'shots without materials are unchanged (render cache holds)');
  fs.rmSync(path.join(lib, 'looks', 'test_look'), { recursive: true, force: true });
})();
