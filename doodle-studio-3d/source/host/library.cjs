// The Doodle Library on this PC, read-only: library.json rows for the Library tab and
// motion track data for inserting a motion into a shot. The Blender add-on owns the
// library; Doodle Studio 3D never writes to it.
const fs = require('node:fs'), path = require('node:path');

const KEEP = ['id', 'name', 'category', 'kind', 'sub', 'tags', 'description', 'preview', 'frames', 'loop', 'source', 'file', 'data'];

module.exports = ({ settings }) => {
  let cache = { file: null, mtime: 0, items: null };
  const blobs = new Map();
  const dir = () => settings.get().libraryDir;

  function items() {
    const file = path.join(dir(), 'library.json');
    if (!fs.existsSync(file)) return { dir: dir(), found: false, items: [] };
    const mtime = fs.statSync(file).mtimeMs;
    if (cache.file !== file || cache.mtime !== mtime) {
      const rows = JSON.parse(fs.readFileSync(file, 'utf8')).items || [];
      cache = { file, mtime, items: rows.map(r => Object.fromEntries(KEEP.filter(k => r[k] != null).map(k => [k, r[k]]))) };
      blobs.clear();
    }
    return { dir: dir(), found: true, items: cache.items, mouthSets: mouthSets(), anim: anim() };
  }

  // animated motion previews: sprite sheets plus an index (motion id -> sheet, row)
  function anim() {
    const f = path.join(dir(), 'previews', 'motion_anim', 'index.json');
    try {
      const mtime = fs.statSync(f).mtimeMs;
      if (cache.animMtime !== mtime) cache = { ...cache, animMtime: mtime, anim: JSON.parse(fs.readFileSync(f, 'utf8')) };
      return cache.anim;
    } catch { return null; }
  }

  // speech mouth sets live in their own file, not as library rows
  function mouthSets() {
    const f = path.join(dir(), 'mouths', 'mouth_sets.json');
    try {
      const mtime = fs.statSync(f).mtimeMs;
      if (cache.mouthMtime !== mtime) cache = { ...cache, mouthMtime: mtime, mouths: (JSON.parse(fs.readFileSync(f, 'utf8')).sets || []).map(s => ({ id: s.id, name: s.name, note: s.note || '' })) };
      return cache.mouths;
    } catch { return []; }
  }

  function motion(id) {
    const row = items().items.find(r => r.id === id);
    if (!row || row.category !== 'motion') throw Error(`No motion ${id} in the library`);
    if (row.kind !== 'ds') throw Error(`${row.name} is a Blender action; insert it from Blender's Doodle panel`);
    const rel = String(row.file || '').endsWith('.json') ? row.file : 'motions/doodle_studio.json';
    const f = path.resolve(dir(), rel);
    if (!f.startsWith(path.resolve(dir()) + path.sep)) throw Error('Bad motion file');
    if (!blobs.has(f)) blobs.set(f, JSON.parse(fs.readFileSync(f, 'utf8')).motions || {});
    const m = blobs.get(f)[id];
    if (!m) throw Error(`Motion ${id} is listed but missing from ${rel}`);
    return { id, name: row.name, loop: !!row.loop, ...m };
  }

  return { items, motion };
};
