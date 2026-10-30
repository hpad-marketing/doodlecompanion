// Update safety check: a version whose MCP does not answer rolls back to the previous
// files and is skipped. Runs the real updater.cjs against a fake install tree.
const fs = require('fs'), path = require('path'), os = require('os');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const T = fs.mkdtempSync(path.join(os.tmpdir(), 'ds3d-upd-'));
const res = path.join(T, 'resources', 'app');
fs.mkdirSync(res, { recursive: true });
fs.copyFileSync(path.join(__dirname, '..', 'host', 'updater.cjs'), path.join(res, 'updater.cjs'));
fs.writeFileSync(path.join(T, 'Doodle Studio 3D.exe'), 'exe');
fs.writeFileSync(path.join(res, 'main.cjs'), 'NEW BROKEN');
// state after an install of v2 on top of v1: v1's main.cjs was set aside in .update/old
const work = path.join(T, '.update');
fs.mkdirSync(path.join(work, 'old', 'files', 'resources', 'app'), { recursive: true });
fs.writeFileSync(path.join(work, 'old', 'files', 'resources', 'app', 'main.cjs'), 'OLD GOOD');
fs.writeFileSync(path.join(work, 'old', 'version.json'), JSON.stringify({ version: 'v1', replacedBy: 'v2' }));
fs.writeFileSync(path.join(work, 'state.json'), JSON.stringify({ version: 'v2', probation: true, launches: 0 }));
let exited = false, dialogs = 0;
const app = { on() {}, relaunch() {}, exit() { exited = true; } };
const dialog = { showMessageBox: async () => { dialogs++; return { response: 0 }; } };
global.setTimeout = (f => (fn, ms) => (ms > 30000 ? 0 : f(fn, ms)))(setTimeout);
global.setInterval = () => 0;
(async () => {
  const u = require(path.join(res, 'updater.cjs'))({ app, dialog, net: {}, window: () => ({ isDestroyed: () => false }), logDir: T });
  ok(fs.existsSync(path.join(work, 'previous', 'files', 'resources', 'app', 'main.cjs')), 'set-aside v1 files kept as the rollback copy');
  let r = await u.verify(async () => false);
  ok(r === 'rolled back', 'MCP did not answer: ' + r);
  ok(fs.readFileSync(path.join(res, 'main.cjs'), 'utf8') === 'OLD GOOD', 'previous version files are back');
  const st = JSON.parse(fs.readFileSync(path.join(work, 'state.json'), 'utf8'));
  ok(st.version === 'v1' && st.skip.includes('v2'), 'state back on v1 and v2 is skipped: ' + JSON.stringify(st));
  ok(exited && dialogs === 1, 'told the user and restarted');
  // a good version passes and leaves probation
  fs.writeFileSync(path.join(work, 'state.json'), JSON.stringify({ version: 'v3', probation: true, launches: 1 }));
  r = await u.verify(async () => true);
  ok(r === 'verified' && !JSON.parse(fs.readFileSync(path.join(work, 'state.json'), 'utf8')).probation, 'a version whose MCP answers is verified');
  fs.rmSync(T, { recursive: true, force: true });
})().catch(e => { console.log('FAIL', e); process.exit(1); });
