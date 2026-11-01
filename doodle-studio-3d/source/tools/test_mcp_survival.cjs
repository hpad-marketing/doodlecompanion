// MCP survival check (runs on every pull request): no update may disconnect or break the
// Doodle Studio 3D MCP. Checks, without a window:
//  - the endpoint stays http://127.0.0.1:54190/mcp, server name doodle-studio-3d
//  - no tool an assistant relies on disappears or gains a required argument (mcp_tools_baseline.json)
//  - the update safety probe (initialize + tools/list after an update) is still wired up
//  - nothing in the 3D host touches the 2D Doodle Studio's MCP ports or config
//  - bad calls come back as plain sentences, never as a crash or a hang
const fs = require('fs'), path = require('path');
const host = path.join(__dirname, '..', 'host');
const read = f => fs.readFileSync(path.join(host, f), 'utf8');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };

(async () => {
  // ---- the endpoint
  const main = read('main.cjs'), server = read('server.cjs'), mcpSrc = read('mcp.cjs');
  ok(/const PORT = 54190;/.test(main), 'port stays 54190');
  ok(/server\.listen\(port, '127\.0\.0\.1'/.test(server), 'server binds 127.0.0.1 only');
  ok(/url\.pathname === '\/mcp'/.test(server), 'endpoint path stays /mcp');
  ok(/name: 'doodle-studio-3d'/.test(mcpSrc), "server name stays doodle-studio-3d");
  ok(/updates\?\.verify\(/.test(main) && /method: 'initialize'/.test(main) && /tools\/list/.test(main), 'update safety probe still calls initialize + tools/list');
  ok(/async function verify\(/.test(read('updater.cjs')) && /rollback/.test(read('updater.cjs')), 'updater still rolls back a build whose MCP fails');
  // the 2D app's MCP is separate: its ports, config and Assistant switch are never touched from here
  const all = fs.readdirSync(host).filter(f => f.endsWith('.cjs')).map(f => [f, read(f)]);
  const touches2d = all.filter(([f, s]) => /\b5418[0-9]\b/.test(s.replace(/^\/\/.*$/gm, '')) || /claude_desktop_config|Doodle Studio Window\.exe|DoodleStudio[\\/]+settings/i.test(s));
  ok(!touches2d.length, '3D host never touches the 2D app\'s ports or MCP config' + (touches2d.length ? ': ' + touches2d.map(x => x[0]).join(', ') : ''));

  // ---- the tool list, through the real handler
  const calls = [];
  let editor = async js => { calls.push(js); return { ok: true }; };
  const handle = require('../host/mcp.cjs')({ call: js => editor(js), api: { 'render-status': async () => ({ state: 'idle' }) } });
  const post = (body, headers = {}) => new Promise(resolve => {
    const res = { code: 200, writeHead(c) { this.code = c; }, end(b) { let j = null; try { j = b ? JSON.parse(b) : null; } catch {} resolve({ code: this.code, body: j, text: b }); } };
    handle({ method: 'POST', headers }, res, typeof body === 'string' ? body : JSON.stringify(body));
  });
  const rpc = async (method, params) => (await post({ jsonrpc: '2.0', id: 1, method, params })).body;
  const tool = async (name, args) => (await rpc('tools/call', { name, arguments: args })).result;

  const init = await rpc('initialize', { protocolVersion: '2025-06-18' });
  ok(init.result.serverInfo.name === 'doodle-studio-3d' && init.result.capabilities.tools, 'initialize answers');
  const tools = (await rpc('tools/list')).result.tools;
  const byName = Object.fromEntries(tools.map(t => [t.name, t]));
  const base = JSON.parse(fs.readFileSync(path.join(__dirname, 'mcp_tools_baseline.json'), 'utf8')).tools;
  const gone = Object.keys(base).filter(n => !byName[n]);
  ok(!gone.length, `every baseline tool is still there (${Object.keys(base).length})` + (gone.length ? '; missing: ' + gone.join(', ') : ''));
  const newReq = Object.keys(base).filter(n => byName[n]).flatMap(n => (byName[n].inputSchema.required || []).filter(r => !base[n].includes(r)).map(r => n + '.' + r));
  ok(!newReq.length, 'no tool gained a required argument' + (newReq.length ? ': ' + newReq.join(', ') : ''));
  const added = tools.filter(t => !base[t.name]).map(t => t.name);
  if (added.length) console.log('note new tools not in the baseline yet (fine; add them once shipped):', added.join(', '));
  ok(tools.every(t => t.description && t.inputSchema.type === 'object' && t.inputSchema.properties.force), 'every tool has a description, an object schema and force');

  // ---- bad calls: clear words, no crash
  let r = await tool('delete_key', { id: 'armL' });
  ok(r.isError && /delete_key needs id \(string\), frame \(integer\)\. Missing: frame\./.test(r.content[0].text), 'missing argument named: ' + r.content[0].text);
  r = await tool('set_ease', { id: 'armL', frame: 3, ease: 'bounce' });
  ok(r.isError && /ease must be one of ease, linear, in, out, hold/.test(r.content[0].text), 'wrong enum lists the choices');
  r = await tool('goto', { frame: -5 });
  ok(r.isError && /frame must be 0 or more/.test(r.content[0].text), 'below minimum explained');
  r = await tool('set_values', { values: 'armL=5' });
  ok(r.isError && /values must be object/.test(r.content[0].text), 'wrong type explained');
  r = await tool('goto', 'frame 5');
  ok(r.isError && /arguments must be a JSON object/.test(r.content[0].text), 'arguments that are not an object explained');
  calls.length = 0;
  r = await tool('goto', { frame: '12' });
  ok(!r.isError && calls.some(c => c.includes('ds3d.goto(12)')), 'a number sent as text is accepted');
  r = await tool('set_ease', { id: 'armL', frame: 3, ease: 'Linear' });
  ok(!r.isError && calls.some(c => c.includes('"linear"')), 'enum in another case is accepted');
  r = await tool('blender_live', {});
  ok(!r.isError, 'a call with no arguments still works');
  let e = await rpc('tools/call', { name: 'set_value', arguments: {} });
  ok(e.error && /Did you mean set_values/.test(e.error.message), 'unknown tool suggests the nearest: ' + e.error.message);
  let p = await post('{not json');
  ok(p.code === 400 && p.body.error.code === -32700, 'bad JSON gets a JSON-RPC parse error');
  p = await post([null, 5, { jsonrpc: '2.0', id: 3, method: 'ping' }]);
  ok(p.code === 200 && p.body.length === 3 && p.body[0].error.code === -32600 && p.body[2].result, 'junk inside a batch is answered, the rest still runs');
  p = await post({}, { origin: 'https://evil.example' });
  ok(p.code === 403, 'other web pages are refused');
  // editor-side failures in words
  editor = async js => { if (js.startsWith('window.ds3dClaude')) return; throw Error('The Doodle Studio 3D window is closed'); };
  r = await tool('get_state', {});
  ok(r.isError && /window is closed\. Open the app/.test(r.content[0].text), 'closed window explained');
  editor = async js => { if (js.startsWith('window.ds3dClaude')) return; throw Error('ds3d is not defined'); };
  r = await tool('get_state', {});
  ok(r.isError && /still loading/.test(r.content[0].text), 'loading editor explained');
  editor = async js => { if (js.startsWith('window.ds3dClaude')) return; throw Error("Cannot read properties of undefined (reading 'frames')"); };
  r = await tool('anim_tool', { action: 'loop_check' });
  ok(r.isError && /internal error in the editor/.test(r.content[0].text) && /get_state/.test(r.content[0].text), 'internal error explained with a next step');
  editor = async js => { if (js.startsWith('window.ds3dClaude')) return; throw Error('Needs a yes first: unsaved changes'); };
  r = await tool('new_scene', {});
  ok(r.isError && r.content[0].text === 'Needs a yes first: unsaved changes', "the app's own messages pass through unchanged");
  // macros replay through the same checks
  let thrown = null; try { await handle.replay('delete_key', { id: 'x' }); } catch (x) { thrown = x; }
  ok(thrown && /Missing: frame/.test(thrown.message), 'macro replay is checked too');

  // ---- the tool reference the guide shows
  const ref = handle.reference();
  ok(tools.every(t => ref.includes('### ' + t.name + '\n')), `tool reference covers all ${tools.length} tools`);
  editor = async js => (js.includes("fetch('guide.md')") ? '# Guide\n\n## 3. Camera\n\ntext' : undefined);
  r = JSON.parse((await tool('get_guide', { section: 'tool reference' })).content[0].text);
  ok(/## MCP tool reference/.test(r.guide) && /### set_values/.test(r.guide), 'get_guide section="tool reference" returns the reference');
})().catch(e => { console.log('FAIL', e); process.exit(1); });
