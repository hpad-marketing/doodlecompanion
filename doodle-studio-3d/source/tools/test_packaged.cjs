// Packaged smoke test: assembles resources/app with package.cjs, starts it in the real Electron
// runtime (headless, with a throwaway home folder) and drives it through its MCP the way an
// assistant would. Needs ELECTRON (the electron binary) and, on Linux, xvfb-run.
//   ELECTRON=node_modules/electron/dist/electron node tools/test_packaged.cjs
const fs = require('fs'), path = require('path'), os = require('os'), { spawn, execFileSync, spawnSync } = require('child_process');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
const ELECTRON = process.env.ELECTRON;
if (!ELECTRON || !fs.existsSync(ELECTRON)) { console.log('FAIL set ELECTRON to the electron binary'); process.exit(1); }
const T = fs.mkdtempSync(path.join(os.tmpdir(), 'ds3d-smoke-'));
const app = path.join(T, 'resources', 'app'), home = path.join(T, 'home');
fs.mkdirSync(path.join(home, 'Documents'), { recursive: true });   // Electron's documents folder on Linux
execFileSync(process.execPath, [path.join(__dirname, 'package.cjs'), app], { stdio: 'pipe' });
const URL = 'http://127.0.0.1:54190/mcp';
// renders and scenes go to a throwaway DeepInDoodles (Linux has no fixed Documents folder)
const renders = path.join(home, 'DeepInDoodles');
fs.mkdirSync(path.join(home, '.config', 'DoodleStudio3D'), { recursive: true });
fs.writeFileSync(path.join(home, '.config', 'DoodleStudio3D', 'settings.json'), JSON.stringify({ rendersRoot: renders }));
const env = { ...process.env, HOME: home, XDG_CONFIG_HOME: path.join(home, '.config'), ELECTRON_ENABLE_LOGGING: '1' };
const linux = process.platform === 'linux';
// software WebGL: CI machines have no GPU, and Chromium blocklists their GL
const flags = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', ...(linux ? ['--no-sandbox'] : [])];
const cmd = linux && spawnSync('which', ['xvfb-run']).status === 0 ? ['xvfb-run', ['-a', ELECTRON, ...flags, app]] : [ELECTRON, [...flags, app]];
const proc = spawn(cmd[0], cmd[1], { env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
let log = ''; proc.stdout.on('data', d => (log += d)); proc.stderr.on('data', d => (log += d));
const stop = () => { try { process.kill(-proc.pid, 'SIGKILL'); } catch {} };
process.on('exit', stop);
for (const sig of ['SIGTERM', 'SIGINT']) process.on(sig, () => { stop(); process.exit(1); });

let id = 0;
const post = async (body, headers = {}) => { const r = await fetch(URL, { signal: AbortSignal.timeout(30000), method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: typeof body === 'string' ? body : JSON.stringify(body) }); return { code: r.status, body: r.status === 200 || r.status === 400 ? await r.json() : null }; };
const rpc = async (method, params) => (await post({ jsonrpc: '2.0', id: ++id, method, params })).body;
const tool = async (name, args = {}) => { const r = (await rpc('tools/call', { name, arguments: args })).result; return r.isError ? { error: r.content[0].text } : JSON.parse(r.content[0].text); };

(async () => {
  // wait for the window and its MCP (the editor's ds3d.state answers once the page is ready)
  let state = null;
  for (let i = 0; i < 90 && !state; i++) {
    await new Promise(r => setTimeout(r, 1000));
    try { const s = await tool('get_state'); if (s && s.values) state = s; } catch {}
  }
  ok(state, 'packaged app starts and its MCP answers get_state');
  if (!state) { console.log(log.split('\n').slice(-30).join('\n')); process.exit(1); }

  const init = await rpc('initialize', { protocolVersion: '2025-06-18' });
  ok(init.result.serverInfo.name === 'doodle-studio-3d', 'initialize: doodle-studio-3d');
  const tools = (await rpc('tools/list')).result.tools;
  const base = Object.keys(JSON.parse(fs.readFileSync(path.join(__dirname, 'mcp_tools_baseline.json'), 'utf8')).tools);
  ok(base.every(n => tools.some(t => t.name === n)), `every baseline tool answers in the packaged app (${tools.length} tools)`);

  let s = await tool('set_values', { values: { armL: 60 }, frame: 0, key: true });
  ok(s.values && Math.round(s.values.armL) === 60, 'set_values poses Bunny');
  s = await tool('set_shot', { scene: 'Smoke Scene' });
  ok(!s.error, 'set_shot names the scene');
  s = await tool('add_shot', { duplicate: false });
  ok(!s.error, 'add_shot: ' + JSON.stringify(s).slice(0, 80));
  s = await tool('save_version', { label: 'smoke' });
  ok(!s.error, 'save_version');
  const copy = path.join(renders, 'Smoke Scene', 'work', 'Smoke Copy.ds3d');
  s = await tool('save_as', { path: copy });
  ok(!s.error && fs.existsSync(copy), 'save_as writes the scene file' + (s.error ? ': ' + s.error : ''));
  s = await tool('open_scene', { path: copy, force: true });
  ok(!s.error, 'open_scene reads it back');
  s = await tool('open_scene', { path: copy.replace(/\.ds3d$/, '.txt'), force: true });
  ok(s.error, 'opening a missing file is a clear error, not a crash: ' + String(s.error).slice(0, 80));
  const g = await tool('get_guide', { section: 'tool reference' });
  ok(/## MCP tool reference/.test(g.guide) && /### set_values/.test(g.guide), 'get_guide serves the tool reference from the packaged guide');
  // bad input: words, not a crash, and the app keeps answering
  s = await tool('delete_key', { id: 'armL' });
  ok(/Missing: frame/.test(s.error || ''), 'missing argument named in the packaged app');
  ok((await post('{oops')).code === 400, 'bad JSON refused with 400');
  ok((await post({}, { origin: 'https://evil.example' })).code === 403, 'other web pages refused');
  ok((await tool('get_state')).values, 'still answering after the bad calls');
  // crash-proofing: kill the editor page; the window reloads it and the MCP answers again
  if (linux) {
    const pids = spawnSync('pgrep', ['-f', `type=renderer.*${path.basename(T)}`]).stdout.toString().trim().split('\n').filter(Boolean);
    ok(pids.length, 'found the editor page process');
    for (const p of pids) try { process.kill(Number(p), 'SIGKILL'); } catch {}
    let back = null;
    for (let i = 0; i < 60 && !back; i++) { await new Promise(r => setTimeout(r, 1000)); try { const s = await tool('get_state'); if (s && s.values) back = s; } catch {} }
    ok(back, 'after the editor page crashes it reloads and the MCP answers again');
    ok(fs.existsSync(path.join(home, '.config', 'DoodleStudio3D', 'crash.log')) && /editor page gone/.test(fs.readFileSync(path.join(home, '.config', 'DoodleStudio3D', 'crash.log'), 'utf8')), 'the crash is written to crash.log');
  }
})().catch(e => { console.log('FAIL', e); console.log(log.split('\n').slice(-20).join('\n')); process.exitCode = 1; })
  .finally(() => { stop(); setTimeout(() => { try { fs.rmSync(T, { recursive: true, force: true }); } catch {} process.exit(); }, 500); });
