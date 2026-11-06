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
  // a restart question left open must not block later checks (seen on the PC 2026-11-01)
  const zlib = require('zlib'), crypto = require('crypto');
  const T2 = fs.mkdtempSync(path.join(os.tmpdir(), 'ds3d-upd2-')), res2 = path.join(T2, 'resources', 'app');
  fs.mkdirSync(res2, { recursive: true });
  fs.copyFileSync(path.join(__dirname, '..', 'host', 'updater.cjs'), path.join(res2, 'updater.cjs'));
  fs.writeFileSync(path.join(T2, 'Doodle Studio 3D.exe'), 'exe');
  fs.mkdirSync(path.join(T2, '.update'), { recursive: true });
  fs.writeFileSync(path.join(T2, '.update', 'state.json'), JSON.stringify({ version: 'v1' }));
  let ver = 'v2';
  const body = v => Buffer.from('main ' + v);
  const net = { fetch: async url => {
    const v = /manifest/.test(url) ? null : url.split('/').pop().replace('.gz', '');
    if (!v) return { ok: true, json: async () => ({ version: ver, files: { 'resources/app/main.cjs': { sha256: crypto.createHash('sha256').update(body(ver)).digest('hex'), gz: ver + '.gz' } } }) };
    return { ok: true, arrayBuffer: async () => zlib.gzipSync(body(v)) };
  } };
  let asked = 0, answer;
  const dialog2 = { showMessageBox: () => { asked++; return new Promise(r => { if (!answer) answer = r; }); } };
  const u2 = require(path.join(res2, 'updater.cjs'))({ app, dialog: dialog2, net, window: () => ({ isDestroyed: () => false, close() {} }), logDir: T2 });
  const first = u2.check();
  await new Promise(r => setTimeout(r, 200));
  ok(asked === 1, 'first check installed v2 and asked to restart');
  ver = 'v3';
  r = await u2.check();
  ok(r === 'installed', 'next check still runs with the question open: ' + r);
  ok(fs.readFileSync(path.join(res2, 'main.cjs'), 'utf8') === 'main v3', 'v3 files installed');
  ok(asked === 1, 'no second dialog stacked on the open one');
  answer({ response: 1 }); await first;
  fs.writeFileSync(path.join(T2, '.update', 'lock'), String(process.pid));
  // the late answer must not have freed anything a newer check holds; a fresh check now sees the lock
  r = await u2.check();
  ok(r === 'busy', 'lock held by someone else is respected: ' + r);
  fs.unlinkSync(path.join(T2, '.update', 'lock'));
  r = await u2.check();
  ok(r === 'current', 'after that, checks run normally: ' + r);
  fs.rmSync(T2, { recursive: true, force: true });
  fs.rmSync(T, { recursive: true, force: true });
})().catch(e => { console.log('FAIL', e); process.exit(1); });
