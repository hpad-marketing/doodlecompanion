// Packaged file paths: builds resources/app with tools/package.cjs into a temp folder and checks
// that every file the app reaches for at run time is really in the package. Catches the
// "works from source, breaks when installed" kind of bug (a new host module, Blender script,
// editor module or data file that package.cjs doesn't copy). Runs on every pull request.
const fs = require('fs'), path = require('path'), os = require('os'), { execFileSync } = require('child_process');
const src = path.join(__dirname, '..');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'ds3d-pkg-'));
try {
  execFileSync(process.execPath, [path.join(__dirname, 'package.cjs'), out], { stdio: 'pipe' });
  const has = rel => fs.existsSync(path.join(out, rel));
  const files = [];
  const walk = d => { for (const n of fs.readdirSync(d)) { const p = path.join(d, n); fs.statSync(p).isDirectory() ? walk(p) : files.push(path.relative(out, p).split(path.sep).join('/')); } };
  walk(out);
  const read = rel => fs.readFileSync(path.join(out, rel), 'utf8');
  const missing = (label, list) => { const m = [...new Set(list)].filter(r => !has(r)); ok(!m.length, `${label} (${new Set(list).size})` + (m.length ? ': missing ' + m.join(', ') : '')); };

  // Electron entry point
  const pkg = JSON.parse(read('package.json'));
  ok(pkg.main && has(pkg.main), 'package.json main is packaged: ' + pkg.main);

  // host modules: every require('./x') and every all-literal path.join(appDir, ...)
  const host = files.filter(f => /^[^/]+\.cjs$/.test(f));
  const reqs = host.flatMap(f => [...read(f).matchAll(/require\('\.\/([^']+)'\)/g)].map(m => m[1]));
  missing('host modules required by the host', reqs);
  const srcHost = fs.readdirSync(path.join(src, 'host')).filter(f => f.endsWith('.cjs'));
  missing('every host/*.cjs is packaged', srcHost);
  const joins = host.flatMap(f => [...read(f).matchAll(/path\.join\(appDir((?:,\s*'[^']+')+)\)/g)].map(m => [...m[1].matchAll(/'([^']+)'/g)].map(x => x[1]).join('/')));
  missing('files the host opens by fixed path (path.join(appDir, ...))', joins);
  missing('character rigs', ['koala', 'frog'].map(c => `blender/chars/${c}.blend`));

  // Blender scripts: sibling modules they import from blender/lib
  const libMods = new Set(fs.readdirSync(path.join(src, 'host', 'blender', 'lib')).filter(f => f.endsWith('.py')).map(f => f.slice(0, -3)));
  const pyFiles = files.filter(f => /^blender\/[^/]+\.py$|^blender\/lib\/[^/]+\.py$/.test(f));
  const pyImports = pyFiles.flatMap(f => [...read(f).matchAll(/^\s*(?:import|from)\s+([\w, ]+?)(?:\s+import\b|\s*(?:#|$))/gm)].flatMap(m => m[1].split(',').map(s => s.trim().split(' ')[0])))
    .filter(m => libMods.has(m)).map(m => `blender/lib/${m}.py`);
  missing('Blender lib modules the scripts import', pyImports);
  ok(!files.some(f => /__pycache__|\.pyc$/.test(f)), 'no Python caches in the package');

  // editor: index.html assets, ES module imports, workers and fixed fetches
  const html = read('ui/index.html');
  const htmlRefs = [...html.matchAll(/(?:src|href)="(?!data:|https?:)([^"]+)"/g)].map(m => 'ui/' + m[1]);
  const imap = JSON.parse((html.match(/<script type="importmap">([\s\S]*?)<\/script>/) || [, '{"imports":{}}'])[1]).imports;
  missing('files index.html loads', [...htmlRefs, ...Object.values(imap).filter(v => !v.endsWith('/')).map(v => 'ui/' + v.replace(/^\.\//, ''))]);
  const js = files.filter(f => /^ui\/src\/.+\.js$/.test(f));
  const rel = (from, to) => path.posix.normalize(path.posix.join(path.posix.dirname(from), to));
  const imports = js.flatMap(f => [...read(f).matchAll(/(?:from\s+|import\()\s*'(\.{1,2}\/[^']+)'/g)].map(m => rel(f, m[1])));
  missing('editor modules imported by the editor', imports);
  const workers = js.flatMap(f => [...read(f).matchAll(/new Worker\(\s*(?:new URL\()?\s*'([^']+)'/g)].map(m => rel(f, m[1])));
  missing('editor web workers', workers);
  const fetches = js.flatMap(f => [...read(f).matchAll(/fetch\('([a-z0-9_\-]+\.(?:json|md))'\)/gi)].map(m => 'ui/' + m[1]));
  missing('data files the editor fetches by name (guide, rig, characters)', [...fetches, 'ui/chars/koala.json', 'ui/chars/frog.json']);

  // nothing from the dev tree leaks into the install
  ok(!files.some(f => /^(tools|devout|node_modules)\//.test(f)), 'no dev folders in the package');
  console.log(`package: ${files.length} files`);
} finally { fs.rmSync(out, { recursive: true, force: true }); }
