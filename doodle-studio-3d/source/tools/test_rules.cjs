// Built-in rules (defaults, not checks): the per-shot switches reach the render, the Render tab
// shows them, the MCP sets them, captions snap into the safe zone below the face and shrink to
// fit. With DS3D_BPY set, Blender runs too: the rules shape a shot, and with every switch off
// the shot renders exactly as keyed. Run: node tools/test_rules.cjs
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs'), { spawnSync } = require('child_process');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  let page, last = null;
  const api = { 'render-status': async () => ({ state: 'idle' }), save: async ({ project }) => ({ path: '/tmp/x/' + project.name + '.ds3d.json' }), render: async r => { last = r; return { message: 'queued' }; }, settings: async () => ({}) };
  const mcp = require('../host/mcp.cjs')({ call: js => page.evaluate(`Promise.resolve(${js})`), api });
  const srv = await require('../host/server.cjs')({ root: path.join(__dirname, '..', 'app'), port: 54197, api, mcp });
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  page = await b.newPage({ viewport: { width: 1600, height: 950 } });
  page.on('pageerror', e => console.log('pageerror', e.message));
  await page.goto('http://127.0.0.1:54197/');
  await page.waitForSelector('body[data-ready="1"]');
  let id = 0;
  const rpc = async (method, params) => (await (await fetch('http://127.0.0.1:54197/mcp', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ jsonrpc: '2.0', id: ++id, method, params }) })).json());
  const tool = async (name, args) => { const r = await rpc('tools/call', { name, arguments: args }); return r.result.isError ? 'ERROR ' + r.result.content[0].text : JSON.parse(r.result.content[0].text); };
  await rpc('initialize', { protocolVersion: '2025-06-18' });

  // defaults: nothing extra travels to Blender (older shots keep their render cache)
  await tool('render', { preview: true });
  ok(last && !('rules' in last.shot), 'all rules on: the shot carries no rules block');
  let r = await tool('set_shot_look', {});
  ok(r.rules && Object.values(r.rules).every(v => v === true) && r.captionSnap === true, 'every rule and caption snapping is on by default');
  r = await tool('set_shot_look', { rules: { armInFront: false, propsOnFloor: false } });
  ok(r.rules.armInFront === false && r.rules.propsOnFloor === false && r.rules.faceClear === true, 'set_shot_look switches single rules off');
  await tool('render', { preview: true });
  ok(JSON.stringify(last.shot.rules) === JSON.stringify({ armInFront: false, propsOnFloor: false }), 'the switched-off rules reach the render');
  r = await tool('set_shot_look', { rules: { armInFront: true, propsOnFloor: true } });
  await tool('render', { preview: true });
  ok(!('rules' in last.shot), 'switching them back on removes the block again');

  // the Render tab shows the switches as one row of toggles
  await page.click('#tabs button:has-text("Render")');
  const labels = await page.$$eval('button[aria-pressed]', bs => bs.map(x => x.textContent));
  ok(['Arms in front', 'Face clear', 'Props on floor', 'Same eye size'].every(l => labels.includes(l)), 'Render tab has the Built-in rules row');
  await page.click('button:has-text("Face clear")');
  ok(await page.evaluate(() => ds3d.project.rules?.faceClear === false), 'clicking a toggle turns that rule off for the shot');
  await page.click('button:has-text("Face clear")');
  ok(await page.evaluate(() => ds3d.project.rules?.faceClear !== false), 'and on again');

  // captions: snapped inside 14%-80% and below the face, whatever height is asked for
  const cap = await page.evaluate(async () => {
    const P = await import('./src/post.js');
    return { low: P.safeCaptionY('one two three four five six', 0.97), high: P.safeCaptionY('hi', 0.02), face: P.safeCaptionY('hi', 0.5, 0.6), short: P.captionLines('so very cool').length, off: P.captionY({ captions: { y: 0.95, snap: false } }, 'x') };
  });
  ok(cap.low + 2 * 0.045 * 1.15 / 2 <= 0.8, `a caption asked at 97% sits inside the bottom of the safe zone (${cap.low.toFixed(3)})`);
  ok(cap.high - 0.045 * 1.15 / 2 >= 0.14, `a caption asked at 2% sits inside the top (${cap.high.toFixed(3)})`);
  ok(cap.face >= 0.6 + 0.05, `a caption over the face moves below it (${cap.face.toFixed(3)})`);
  ok(cap.short === 1, 'one to three words stay on one line');
  ok(cap.off === 0.95, 'snapping off keeps the exact height');
  r = await tool('set_shot_look', { captionSnap: false });
  ok(r.captionSnap === false, 'set_shot_look turns caption snapping off');
  await tool('set_shot_look', { captionSnap: true });
  await b.close();
  srv.close?.();

  // Blender: the rules shape the shot; with every switch off it renders as keyed
  const PY = process.env.DS3D_BPY;
  if (!PY) { console.log('skip Blender part (set DS3D_BPY)'); process.exit(); }
  const B = path.join(__dirname, '..', 'host', 'blender'), out = fs.mkdtempSync('/tmp/rules-');
  const cam = { yaw: 0, pitch: 5, dist: 4.5, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.6 };
  const frames = Array.from({ length: 3 }, () => ({ expression: 1, armL: 140, armLForward: -40, elbowL: 60, cam }));
  const run = (tag, extra) => {
    const shot = path.join(out, tag + '.json');
    fs.writeFileSync(shot, JSON.stringify({ fps: 30, width: 120, height: 200, frames, ...extra }));
    const p = spawnSync(PY, ['-I', path.join(B, 'ds_bridge.py'), '--', path.join(B, 'Bunny3D_v2.blend'), shot, path.join(out, tag), '--no-cloth', '--no-springs', '--frames', '2'], { encoding: 'utf8', cwd: '/tmp', env: { ...process.env, DSL_BUNNY: B } });
    return (p.stdout || '') + (p.stderr || '');
  };
  const on = run('on', {}), off = run('off', { rules: { armInFront: false, faceClear: false, propsOnFloor: false, eyeSize: false } });
  ok(/rules: arm brought clear of the head on 3 frames/.test(on), 'rules on: a hand peeking from behind the head is brought clear');
  ok(!/rules:/.test(off), 'rules off: nothing is changed');
  // speed: an overhead camera sees hands under the head naturally, so the arm rule stays out of it
  const t0 = Date.now(), oh = run('overhead', { frames: frames.map(f => ({ ...f, cam: { ...cam, pitch: 62, dist: 4.2, lens: 35 } })) }), secs = (Date.now() - t0) / 1000;
  ok(!/arm brought clear/.test(oh) && secs < 120, `overhead: the arm rule stays out and the shot is quick (${secs.toFixed(0)} s)`);
})();
