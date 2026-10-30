// Publish a Doodle Studio 3D build to this update channel.
//   node doodle-studio-3d/publish.js <resources/app folder> <version> "notes" <runtime>
// Only resources/app/* is published (the Electron runtime is copied from the 2D
// Doodle Studio install and only its version is recorded). Files are stored gzip'd
// and named by content hash, so unchanged files cost nothing on the next publish.
const fs = require('fs'), path = require('path'), crypto = require('crypto'), zlib = require('zlib');
const [appDir, version, notes = '', runtime] = process.argv.slice(2);
if (!appDir || !version || !runtime) throw Error('usage: publish.js <resources/app folder> <version> "notes" <runtime>');
const here = __dirname, files = {};
const list = fs.readdirSync(appDir, { recursive: true }).map(f => f.split(path.sep).join('/')).filter(f => fs.statSync(path.join(appDir, f)).isFile());
fs.mkdirSync(path.join(here, 'files'), { recursive: true });
for (const f of list) {
  const data = fs.readFileSync(path.join(appDir, f)), sha256 = crypto.createHash('sha256').update(data).digest('hex'), gz = 'files/' + sha256 + '.gz';
  if (!fs.existsSync(path.join(here, gz))) fs.writeFileSync(path.join(here, gz), zlib.gzipSync(data, { level: 9 }));
  files['resources/app/' + f] = { sha256, size: data.length, gz };
}
const keep = new Set(Object.values(files).map(f => path.basename(f.gz)));
for (const name of fs.readdirSync(path.join(here, 'files'))) if (!keep.has(name)) fs.unlinkSync(path.join(here, 'files', name));
fs.writeFileSync(path.join(here, 'manifest.json'), JSON.stringify({ version, notes, runtime, published: new Date().toISOString(), files }, null, 1) + '\n');
console.log(version, Object.keys(files).length + ' files');
