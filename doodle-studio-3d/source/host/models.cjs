// 3D view models for library sets, props and scenery. Blender converts each one once
// (blender/preview_export.py) into a small GLB in the app's own cache folder; the editor shows
// them so a shot can be composed without opening Blender. A model is redone when the library
// file that holds it changes. Read-only for the library; nothing here touches renders or MCP.
const fs = require('node:fs'), path = require('node:path'), { spawn } = require('node:child_process');

module.exports = ({ libraryDir, cacheDir, command, log = () => {} }) => {
  // command(ids, outDir) -> [exe, args] or null when Blender is missing
  const queue = new Set(), errors = {};
  let running = false;
  const rowsCache = { file: null, mtime: 0, rows: null };
  function rows() {
    const f = path.join(libraryDir(), 'library.json');
    const m = fs.statSync(f).mtimeMs;
    if (rowsCache.file !== f || rowsCache.mtime !== m) Object.assign(rowsCache, { file: f, mtime: m, rows: new Map(JSON.parse(fs.readFileSync(f, 'utf8')).items.map(r => [r.id, r])) });
    return rowsCache.rows;
  }
  const safe = id => String(id).replace(/[^A-Za-z0-9_.-]/g, '_');
  function stamp(row) {
    try { return Math.round(fs.statSync(path.join(libraryDir(), row.file)).mtimeMs); } catch { return 0; }
  }
  const nameOf = row => `${safe(row.id)}--${stamp(row)}.glb`;

  function pump() {
    if (running || !queue.size) return;
    const ids = [...queue].slice(0, 120);
    const dir = cacheDir();
    fs.mkdirSync(dir, { recursive: true });
    const tmp = path.join(dir, 'bake');
    fs.mkdirSync(tmp, { recursive: true });
    const cmd = command(ids, tmp);
    if (!cmd) { for (const id of ids) { queue.delete(id); errors[id] = 'Blender was not found. Set it in Render › Blender location.'; } return; }
    running = true;
    let out = '';
    let p;
    try { p = spawn(cmd[0], cmd[1], { windowsHide: true, env: { ...process.env, DSL_LIBRARY: libraryDir() } }); }
    catch (e) { running = false; for (const id of ids) { queue.delete(id); errors[id] = String(e.message || e); } return; }
    p.stdout.on('data', d => { out += d; });
    p.stderr.on('data', d => { out += d; });
    p.on('close', () => {
      running = false;
      const r = rows();
      for (const id of ids) {
        queue.delete(id);
        const ok = new RegExp('^OK ' + id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ' ', 'm').test(out);
        const src = path.join(tmp, id + '.glb'), row = r.get(id);
        if (ok && row && fs.existsSync(src)) {
          for (const old of fs.readdirSync(dir)) if (old.startsWith(safe(id) + '--')) try { fs.unlinkSync(path.join(dir, old)); } catch {}
          fs.renameSync(src, path.join(dir, nameOf(row)));
          delete errors[id];
        } else errors[id] = (new RegExp('^FAIL ' + id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ': (.*)$', 'm').exec(out)?.[1]) || 'Blender stopped: ' + out.trim().split('\n').slice(-2).join(' ');
      }
      log(`3D view models: ${ids.length - ids.filter(i => errors[i]).length} of ${ids.length} converted`);
      pump();
    });
  }

  // ids -> { models: { id: url }, pending: [ids], errors: { id: why } }
  function models(req) {
    const ids = req.ids || [];
    let r;
    try { r = rows(); } catch { return { models: {}, pending: [], errors: {}, error: 'The Doodle Library was not found, so sets and props show as pictures.' }; }
    const dir = cacheDir(), have = fs.existsSync(dir) ? new Set(fs.readdirSync(dir)) : new Set();
    const out = { models: {}, pending: [], errors: {} };
    for (const id of (req.all ? ids : ids.slice(0, 400))) {
      const row = r.get(id);
      if (!row || !['set', 'prop', 'scenery'].includes(row.category)) { out.errors[id] = 'no model for this piece'; continue; }
      const n = nameOf(row);
      if (have.has(n)) { out.models[id] = '/models/' + encodeURIComponent(n); continue; }
      if (errors[id] && !queue.has(id)) { out.errors[id] = errors[id]; continue; }
      queue.add(id); out.pending.push(id);
    }
    pump();
    if (Object.values(out.errors).some(e => /Blender was not found/.test(e))) out.error = 'Blender was not found, so sets and props show as pictures. Set it in Render › Blender location.';
    return out;
  }
  // every set, prop and scenery piece at once (Library › Make 3D models for the whole library)
  function all() { const r = rows(); const ids = [...r.values()].filter(x => ['set', 'prop', 'scenery'].includes(x.category)).map(x => x.id); for (const id of ids) delete errors[id]; return models({ ids, all: true }); }
  function info() { const dir = cacheDir(); let n = 0, bytes = 0; if (fs.existsSync(dir)) for (const f of fs.readdirSync(dir)) if (f.endsWith('.glb')) { n++; bytes += fs.statSync(path.join(dir, f)).size; } return { models: n, mb: +(bytes / 1048576).toFixed(1), queued: queue.size, running }; }
  return { models: req => (req.all ? all() : models(req)), info, dir: cacheDir };
};
