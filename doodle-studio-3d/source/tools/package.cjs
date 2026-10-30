// Assemble resources/app for Doodle Studio 3D: node tools/package.cjs OUT_DIR
const fs = require('fs'), path = require('path');
const here = path.join(__dirname, '..'), out = path.resolve(process.argv[2] || path.join(here, 'build', 'app'));
fs.rmSync(out, { recursive: true, force: true });
const copy = (from, to) => fs.cpSync(path.join(here, from), path.join(out, to), { recursive: true });
for (const f of ['package.json', 'main.cjs', 'preload.cjs', 'updater.cjs', 'server.cjs', 'mcp.cjs', 'render.cjs']) copy('host/' + f, f);
copy('host/blender/Bunny3D_v2.blend', 'blender/Bunny3D_v2.blend');
copy('host/blender/ds_bridge.py', 'blender/ds_bridge.py');
for (const f of fs.readdirSync(path.join(here, 'host/blender/lib')).filter(f => f.endsWith('.py'))) copy('host/blender/lib/' + f, 'blender/lib/' + f);
copy('app/index.html', 'ui/index.html');
copy('app/src', 'ui/src');
copy('app/vendor/three.module.js', 'ui/vendor/three.module.js');
copy('app/bunny3d.json', 'ui/bunny3d.json');
if (fs.existsSync(path.join(here, 'app/icon.png'))) copy('app/icon.png', 'ui/icon.png');
const files = [];
const walk = d => { for (const n of fs.readdirSync(d)) { const p = path.join(d, n); fs.statSync(p).isDirectory() ? walk(p) : files.push(path.relative(out, p)); } };
walk(out);
console.log(out, files.length, 'files');
