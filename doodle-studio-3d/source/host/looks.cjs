// Materials tab: the looks a shot can wear (clay, cel toon, felt... and any look add-on such as
// ClayDoh) and the colour palettes. A look add-on is a Blender add-on package with a
// doodle_look.json next to its __init__.py (see blender/addons/doodle_looks/CONTRACT.md).
// Found in three places:
//   1. the built-in Doodle Looks (blender/addons/doodle_looks, ships with the app)
//   2. the Doodle Library's looks folder: <library>\looks\<add-on>\ (a folder, or a .zip dropped there)
//   3. Blender's own add-on folders on this PC (%APPDATA%\Blender Foundation\Blender\<ver>\scripts\addons
//      and ...\extensions\<repo>\), so an add-on installed in Blender shows up by itself
// A look from 2 or 3 is tried once with a test frame before it can be picked; the result is kept.
const fs = require('node:fs'), path = require('node:path'), os = require('node:os'), { spawn, spawnSync } = require('node:child_process');

const BUILTIN = appDir => path.join(appDir, 'blender', 'addons');

// previews travel inside the list as data URLs: add-ons live in several folders on the PC
function dataUrl(f) {
  try { if (f && /\.(png|jpg|jpeg|webp)$/i.test(f) && fs.statSync(f).size < 1.5e6) return `data:image/${path.extname(f).slice(1).toLowerCase().replace('jpg', 'jpeg')};base64,` + fs.readFileSync(f).toString('base64'); } catch {}
  return null;
}

function readJson(f) { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return null; } }

function blenderAddonRoots() {
  const out = [];
  const base = process.env.APPDATA ? path.join(process.env.APPDATA, 'Blender Foundation', 'Blender') : path.join(os.homedir(), '.config', 'blender');
  let vers = [];
  try { vers = fs.readdirSync(base); } catch { return out; }
  for (const v of vers) {
    out.push(path.join(base, v, 'scripts', 'addons'));
    try { for (const repo of fs.readdirSync(path.join(base, v, 'extensions'))) if (!repo.startsWith('.')) out.push(path.join(base, v, 'extensions', repo)); } catch {}
  }
  return out;
}

// a .zip dropped in <library>\looks is unpacked next to it once (Windows: Expand-Archive)
function unpackZips(dir) {
  let names = [];
  try { names = fs.readdirSync(dir); } catch { return; }
  for (const z of names.filter(n => /\.zip$/i.test(n))) {
    const zip = path.join(dir, z), mark = zip + '.unpacked';
    try { if (fs.existsSync(mark) && fs.statSync(mark).mtimeMs >= fs.statSync(zip).mtimeMs) continue; } catch {}
    const r = process.platform === 'win32'
      ? spawnSync('powershell', ['-NoProfile', '-Command', `Expand-Archive -LiteralPath '${zip.replace(/'/g, "''")}' -DestinationPath '${dir.replace(/'/g, "''")}' -Force`], { windowsHide: true, timeout: 60000 })
      : spawnSync('unzip', ['-o', '-q', zip, '-d', dir], { timeout: 60000 });
    if (r.status === 0) fs.writeFileSync(mark, new Date().toISOString());
  }
}

// every add-on package with a doodle_look.json: { module, root (folder to import from), dir, manifest, source }
function addons({ appDir, libraryDir }) {
  const found = new Map();
  const scan = (root, source) => {
    let names = [];
    try { names = fs.readdirSync(root); } catch { return; }
    for (const n of names) {
      const dir = path.join(root, n), man = readJson(path.join(dir, 'doodle_look.json'));
      if (!man || !Array.isArray(man.looks) || !fs.existsSync(path.join(dir, '__init__.py'))) continue;
      const module = man.module || n;
      if (module !== n || found.has(module)) continue;   // the package folder is what Blender imports
      found.set(module, { module, root, dir, manifest: man, source });
    }
  };
  scan(BUILTIN(appDir), 'built-in');
  const lib = libraryDir && path.join(libraryDir, 'looks');
  if (lib) { unpackZips(lib); scan(lib, 'library'); }
  for (const r of blenderAddonRoots()) scan(r, 'blender');
  return [...found.values()];
}

// module -> folder Blender imports it from, for the shot the bridge renders
function addonDirs(o) { return Object.fromEntries(addons(o).map(a => [a.module, a.root])); }

const statusFile = dataDir => path.join(dataDir, 'looks', 'status.json');

module.exports = ({ appDir, settings, dataDir, blender }) => {
  const opts = () => ({ appDir, libraryDir: settings.get().libraryDir });
  const status = () => readJson(statusFile(dataDir)) || {};
  const palettes = () => readJson(path.join(appDir, 'blender', 'lib', 'palettes.json'))?.palettes || [];
  const testing = new Map();

  function list() {
    const st = status();
    const looks = [];
    for (const a of addons(opts())) {
      for (const lk of a.manifest.looks) {
        if (!lk || !lk.id) continue;
        const key = `${a.module}:${lk.id}`;
        const shipped = lk.preview && path.join(a.dir, lk.preview);
        const tested = path.join(dataDir, 'looks', `${a.module}-${lk.id}.png`);
        const s = a.source === 'built-in' ? { state: 'ok' } : testing.has(key) ? { state: 'testing' } : (st[key] || { state: 'untested' });
        looks.push({
          key, addon: a.module, id: lk.id, name: lk.name || lk.id, about: lk.about || '', flat: !!lk.flat, source: a.source, addonName: a.manifest.name || a.module,
          params: (lk.params || []).filter(p => p && p.id), status: s.state, error: s.error || null,
          preview: dataUrl(shipped) || dataUrl(tested),
        });
      }
    }
    return { looks, palettes: palettes() };
  }

  // a test frame for one look: Bunny close up wearing it. Passing makes the look pickable.
  function test({ key }) {
    const look = list().looks.find(l => l.key === key);
    if (!look) return { ok: false, error: 'No such look on this PC' };
    if (look.source === 'built-in') return { ok: true };
    const exe = blender();
    if (!exe) return { ok: false, error: 'Blender was not found' };
    if (testing.has(key)) return { ok: true, state: 'testing' };
    const dir = path.join(dataDir, 'looks', 'test-' + key.replace(/[^a-z0-9_-]+/gi, '_'));
    fs.mkdirSync(dir, { recursive: true });
    const cam = { yaw: 15, pitch: 4, dist: 1.9, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.45 };
    const shot = { fps: 30, width: 400, height: 600, frames: [{ armR: 35, elbowR: 70, armL: 20, expression: 2, cam }],
      materials: { layers: { scene: { look: look.id, addon: look.addon, params: {} } }, addons: addonDirs(opts()) } };
    fs.writeFileSync(path.join(dir, 'shot.json'), JSON.stringify(shot));
    const args = ['-b', path.join(appDir, 'blender', 'Bunny3D_v2.blend'), '--python', path.join(appDir, 'blender', 'ds_bridge.py'), '--', path.join(dir, 'shot.json'), dir, '--still', '1', '--no-cloth', '--no-springs'];
    testing.set(key, true);
    let log = '';
    const done = (state, error) => {
      testing.delete(key);
      const st = status();
      st[key] = { state, error: error || null, at: new Date().toISOString() };
      fs.mkdirSync(path.dirname(statusFile(dataDir)), { recursive: true });
      fs.writeFileSync(statusFile(dataDir), JSON.stringify(st, null, 1));
      fs.writeFileSync(path.join(dir, 'blender.log'), log);
    };
    let p;
    try { p = spawn(exe, args, { windowsHide: true, env: { ...process.env, DSL_LIBRARY: settings.get().libraryDir || '', DSL_BUNNY: path.join(appDir, 'blender') } }); } catch (e) { done('failed', String(e.message || e)); return { ok: false, error: String(e.message || e) }; }
    const timer = setTimeout(() => p.kill(), 4 * 60000);
    p.stdout.on('data', d => { log += d; });
    p.stderr.on('data', d => { log += d; });
    p.on('error', e => { clearTimeout(timer); done('failed', String(e.message || e)); });
    p.on('close', code => {
      clearTimeout(timer);
      const still = path.join(dir, 'still.png');
      const rep = readJson(path.join(dir, 'materials.json'));
      const failed = rep?.failed?.[0]?.error || (!fs.existsSync(still) ? `Blender stopped (exit ${code}), no test frame` : null) || (rep && !Object.keys(rep.targets || {}).length ? 'The look did not change anything' : null);
      if (!failed) fs.copyFileSync(still, path.join(dataDir, 'looks', `${look.addon}-${look.id}.png`));
      done(failed ? 'failed' : 'ok', failed);
    });
    return { ok: true, state: 'testing' };
  }

  return {
    list, test, addonDirs: () => addonDirs(opts()),
    api: {
      'looks-list': () => list(),
      'looks-test': req => test(req),
    },
  };
};
module.exports.addons = addons;
module.exports.addonDirs = addonDirs;
