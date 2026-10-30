const start = require('../host/server.cjs');
const path = require('node:path'), fs = require('node:fs');
const out = path.join(__dirname, '..', 'devout'); fs.mkdirSync(out, { recursive: true });
start({ root: path.join(__dirname, '..', 'app'), port: Number(process.argv[2] || 54190), api: {
  save: ({ project, path: p }) => { const f = p || path.join(out, (project.name || 'shot') + '.ds3d.json'); fs.writeFileSync(f, JSON.stringify(project, null, 1)); return { path: f }; },
  open: () => ({}),
  render: ({ name }) => ({ message: 'dev server: render queued for ' + name }), 'render-status': () => ({ state: 'idle' }), settings: () => ({ blenderFound: null }),
  'export-bridge': ({ shot, name }) => { const f = path.join(out, name + '.shot.json'); fs.writeFileSync(f, JSON.stringify(shot)); return { path: f }; },
} }).then(() => console.log('dev server up'));
