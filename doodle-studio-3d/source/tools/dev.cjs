const start = require('../host/server.cjs');
const path = require('node:path'), fs = require('node:fs');
const out = path.join(__dirname, '..', 'devout'); fs.mkdirSync(out, { recursive: true });
// every dev run starts clean: a recovery file left by an earlier test would restore its scene mid-test
fs.rmSync(path.join(out, 'recovery.json'), { force: true });
const lib = require('../host/library.cjs')({ settings: { get: () => ({ libraryDir: process.env.DSL_LIBRARY || path.join(__dirname, '..', '..', 'lib') }) } });
const libDir = () => process.env.DSL_LIBRARY || path.join(__dirname, '..', '..', 'lib');
// 3D view models: DS3D_BPY is a Python with the bpy module (pip install bpy), standing in for Blender
const models = require('../host/models.cjs')({ libraryDir: libDir, cacheDir: () => path.join(out, 'models'),
  command: (ids, dir) => (process.env.DS3D_BPY ? [process.env.DS3D_BPY, [path.join(__dirname, '..', 'host', 'blender', 'preview_export.py'), '--', libDir(), dir, ...ids]] : null) });
// Open in Blender: a bpy stand-in for the Blender window (fakeblender_live.sh) when DS3D_BPY is set
const PORT = Number(process.argv[2] || 54190);
const mirror = require('../host/mirror.cjs')({ appDir: path.join(__dirname, '..', 'host'), port: PORT,
  blender: () => process.env.DS3D_BLENDER || (process.env.DS3D_BPY ? path.join(__dirname, 'fakeblender_live.sh') : null),  // DS3D_BLENDER: a real Blender for window tests
  blendFor: s => (s.character && s.character !== 'bunny' ? path.join(__dirname, '..', 'host', 'blender', 'chars', s.character + '.blend') : path.join(__dirname, '..', 'host', 'blender', 'Bunny3D_v2.blend')),
  withMaster: s => s, folders: n => { const work = path.join(out, 'DeepInDoodles', String(n || 'scene'), 'work'); fs.mkdirSync(work, { recursive: true }); return { work }; },
  env: () => ({ DSL_LIBRARY: libDir(), DSL_BUNNY: path.join(__dirname, '..', 'host', 'blender') }) });
start({ root: path.join(__dirname, '..', 'app'), statics: { lib: libDir, models: () => path.join(out, 'models') }, port: PORT, mcp: require('../host/mcp.cjs')({ call: async () => { throw Error('dev server: no app window to drive'); }, api: {} }), api: { ...mirror.api,
  save: ({ project, path: p }) => { const f = p || path.join(out, (project.name || 'shot') + '.ds3d.json'); fs.writeFileSync(f, JSON.stringify(project, null, 1)); return { path: f }; },
  open: () => ({}),
  'save-at': ({ project, path: p }) => { const f = p.endsWith('.ds3d') ? p : p + '.ds3d'; fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, JSON.stringify(project, null, 1)); return { path: f }; },
  'render-carousel': req => { fs.writeFileSync(path.join(out, 'carousel-req.json'), JSON.stringify(req)); return { message: 'dev server: carousel with ' + req.slides.length + ' slides' }; },
  'read-png': ({ path: p }) => ({ data: fs.readFileSync(p).toString('base64') }),
  'write-png': ({ path: p, data }) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, Buffer.from(data, 'base64')); return { path: p }; },
  render: ({ name, post, width, height, shot }) => { fs.writeFileSync(path.join(out, 'render-req.json'), JSON.stringify({ width, height, shot })); if (post) fs.writeFileSync(path.join(out, 'post-shot.json'), JSON.stringify(post)); return { message: 'dev server: render queued for ' + name }; }, 'render-scene': ({ name, shots, preview, post }) => { if (post) fs.writeFileSync(path.join(out, 'post-scene.json'), JSON.stringify(post)); fs.appendFileSync(path.join(out, 'scene-log.txt'), name + (preview ? ' preview' : ' full') + '\n'); fs.writeFileSync(path.join(out, 'scene-req.json'), JSON.stringify(shots.map(s => [s.code, s.shot.frames.length]))); return { message: 'dev server: scene ' + name + ' with ' + shots.length + ' shots' }; }, 'render-status': () => ({ state: 'idle' }), settings: () => ({ blenderFound: null, rendersRoot: path.join(out, 'DeepInDoodles') }),
  library: () => lib.items(), 'stage-models': req => models.models(req), 'models-info': () => models.info(), 'library-motion': ({ id }) => lib.motion(id), 'pick-library': () => lib.items(),
  autosave: ({ project, keep, frame, file }) => { const d = path.join(out, 'autosave'); fs.mkdirSync(d, { recursive: true }); fs.writeFileSync(path.join(d, 'a' + Date.now() + '.ds3d'), JSON.stringify(project)); fs.writeFileSync(path.join(out, 'recovery.json'), JSON.stringify({ at: new Date().toISOString(), file, frame, project })); return { keep }; },
  recovery: () => (fs.existsSync(path.join(out, 'recovery.json')) ? JSON.parse(fs.readFileSync(path.join(out, 'recovery.json'))) : null), 'recovery-clear': () => { fs.rmSync(path.join(out, 'recovery.json'), { force: true }); return {}; },
  'save-version': ({ project, label }) => { const f = path.join(out, 'versions', `${project.name}_${label}.ds3d`); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, JSON.stringify(project)); return { path: f }; },
  'list-versions': () => { const d = path.join(out, 'versions'); return { versions: fs.existsSync(d) ? fs.readdirSync(d).map(n => ({ file: path.join(d, n), name: n, at: new Date().toISOString() })) : [] }; },
  'open-file': ({ file }) => ({ project: JSON.parse(fs.readFileSync(file, 'utf8')), path: file }), disk: () => ({ root: out, freeGB: 3, totalGB: 100 }),
  'write-file': ({ path: p, data }) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, Buffer.from(data, 'base64')); return { path: p }; },
  'pick-image': () => ({ path: process.env.DS3D_IMAGE || null }), 'read-image': ({ path: p }) => ({ data: fs.readFileSync(p).toString('base64'), type: /png$/i.test(p) ? 'image/png' : 'image/jpeg' }),
  'read-svg': ({ path: p }) => ({ text: fs.readFileSync(p, 'utf8') }),
  'pick-video': () => ({ path: process.env.DS3D_VIDEO || null }), 'ref-video': ({ path: p }) => start.registerRef(p),
  'pick-audio': () => ({ path: process.env.DS3D_AUDIO || null }), 'read-audio': ({ path: p }) => ({ data: fs.readFileSync(p).toString('base64') }),
  'render-estimate': () => ({ full: 2.5, preview: 0.6 }), 'sleep-when-done': ({ on }) => { fs.writeFileSync(path.join(out, 'sleep.json'), JSON.stringify({ on })); return { on }; },
  'pick-scenes': () => ({ scenes: [] }),
  health: ({ audio = [] }) => ({ blender: null, library: { dir: 'lib', found: true }, renders: { root: out, writable: true }, disk: { freeGB: 3 }, mcp: { ok: true, port: 54190 }, audioMissing: audio.filter(a => !fs.existsSync(a)).map(a => path.basename(a)), cacheGB: 0.01 }),
  'cache-info': () => ({ old: { count: 2, gb: 0.01 }, tests: { gb: 0 } }), 'cache-clean': () => ({ gb: 0.01 }),
  'pick-blender': () => ({ blender: null }), 'pick-library': () => lib.items(),
  'pack-project': ({ project }) => { const d = path.join(out, 'pack'); fs.mkdirSync(d, { recursive: true }); const f = path.join(d, project.name + '.ds3d'); fs.writeFileSync(f, JSON.stringify({ ...project, packed: true })); return { dir: d, files: [f], missing: [] }; },
  'pick-master': ({ path: p }) => { if (!p) return { masterBlend: null }; if (!fs.existsSync(p)) throw Error('Pick a .blend file'); fs.writeFileSync(path.join(out, 'master.json'), JSON.stringify({ masterBlend: p })); return { masterBlend: p }; },
  'open-master': () => ({ opened: null }),
  'export-bridge': ({ shot, name }) => { const f = path.join(out, name + '.shot.json'); fs.writeFileSync(f, JSON.stringify(shot)); return { path: f }; },
} }).then(() => console.log('dev server up'));
