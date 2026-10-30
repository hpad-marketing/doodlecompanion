const start = require('../host/server.cjs');
const path = require('node:path'), fs = require('node:fs');
const out = path.join(__dirname, '..', 'devout'); fs.mkdirSync(out, { recursive: true });
const lib = require('../host/library.cjs')({ settings: { get: () => ({ libraryDir: process.env.DSL_LIBRARY || path.join(__dirname, '..', '..', 'lib') }) } });
start({ root: path.join(__dirname, '..', 'app'), statics: { lib: () => process.env.DSL_LIBRARY || path.join(__dirname, '..', '..', 'lib') }, port: Number(process.argv[2] || 54190), api: {
  save: ({ project, path: p }) => { const f = p || path.join(out, (project.name || 'shot') + '.ds3d.json'); fs.writeFileSync(f, JSON.stringify(project, null, 1)); return { path: f }; },
  open: () => ({}),
  'render-carousel': req => { fs.writeFileSync(path.join(out, 'carousel-req.json'), JSON.stringify(req)); return { message: 'dev server: carousel with ' + req.slides.length + ' slides' }; },
  'read-png': ({ path: p }) => ({ data: fs.readFileSync(p).toString('base64') }),
  'write-png': ({ path: p, data }) => { fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, Buffer.from(data, 'base64')); return { path: p }; },
  render: ({ name }) => ({ message: 'dev server: render queued for ' + name }), 'render-scene': ({ name, shots }) => { fs.writeFileSync(path.join(out, 'scene-req.json'), JSON.stringify(shots.map(s => [s.code, s.shot.frames.length]))); return { message: 'dev server: scene ' + name + ' with ' + shots.length + ' shots' }; }, 'render-status': () => ({ state: 'idle' }), settings: () => ({ blenderFound: null, rendersRoot: path.join(out, 'DeepInDoodles') }),
  library: () => lib.items(), 'library-motion': ({ id }) => lib.motion(id), 'pick-library': () => lib.items(),
  'export-bridge': ({ shot, name }) => { const f = path.join(out, name + '.shot.json'); fs.writeFileSync(f, JSON.stringify(shot)); return { path: f }; },
} }).then(() => console.log('dev server up'));
