// Animator tools part 2: click-to-pick, IK drag + IK over MCP, pinning, motion path + arc fixer,
// graph editor, time warp, moving hold, pose library, copy / paste keys across shots and
// characters, retarget, layers, Euler filter, balance, reference video (Range served),
// clip blending, playblast with audio, multi-key moves, per-control reset.
const { spawn, execFileSync } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54301, out = path.join(__dirname, '..', 'devout'), wav = path.join(out, 'tone7.wav'), vid = path.join(out, 'ref7.webm');
{
  const sr = 16000, n = sr * 2, d = Buffer.alloc(44 + n * 2);
  d.write('RIFF', 0); d.writeUInt32LE(36 + n * 2, 4); d.write('WAVEfmt ', 8); d.writeUInt32LE(16, 16); d.writeUInt16LE(1, 20); d.writeUInt16LE(1, 22);
  d.writeUInt32LE(sr, 24); d.writeUInt32LE(sr * 2, 28); d.writeUInt16LE(2, 32); d.writeUInt16LE(16, 34); d.write('data', 36); d.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) d.writeInt16LE(Math.round(9000 * Math.sin(i / sr * 2 * Math.PI * 330)), 44 + i * 2);
  fs.writeFileSync(wav, d);
  if (!fs.existsSync(vid)) execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=size=320x180:rate=30:duration=4', '-c:v', 'libvpx', '-b:v', '300k', vid]);
}
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.accept(d.type() === 'prompt' ? d.defaultValue() : undefined));
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const A = a => ev(x => ds3d.anim2(x), a);
  const val = (id, f) => ev(([id, f]) => { ds3d.goto(f); return ds3d.state().values[id]; }, [id, f]);
  const vbox = await p.locator('#view').boundingBox();
  const scr = s => [vbox.x + s[0] * vbox.width, vbox.y + s[1] * vbox.height];

  // click-to-pick: clicking the right hand opens the right arm's controls
  let e = await A({ action: 'end_point', limb: 'armR' });
  let [x, y] = scr(e.screen);
  await p.mouse.click(x, y);
  ok(await p.locator('#subtabs .sub-chips button[aria-pressed="true"]').first().textContent() === 'Right arm', 'clicking the hand picks the right arm');
  ok((await A({ action: 'pick', x: 0.5, y: 0.02 })) === null, 'clicking empty sky picks nothing');

  // IK drag in the viewport
  await p.keyboard.press('i');
  e = await A({ action: 'end_point', limb: 'armR' }); [x, y] = scr(e.screen);
  await p.mouse.move(x, y); await p.mouse.down(); await p.mouse.move(x, y - 40, { steps: 5 }); await p.mouse.move(x, y - 70, { steps: 5 }); await p.mouse.up();
  const e2 = await A({ action: 'end_point', limb: 'armR' });
  ok(e2.at[2] > e.at[2] + 0.03, `IK drag lifts the hand ${((e2.at[2] - e.at[2]) * 100).toFixed(1)} cm`);
  let st = await ev(() => ds3d.state());
  ok(st.keyed.armR || st.keyed.elbowR || st.keyed.armRForward, 'and keys the FK arm controls (IK and FK agree)');
  await p.keyboard.press('i');
  // IK over MCP
  let r = await A({ action: 'ik', limb: 'armL', offset: [0, -0.04, 0.06] });
  ok(r.missedCm < 1.5, `IK to a point: missed by ${r.missedCm} cm`);
  await ev(() => ds3d.setShot({ length: 40 }));

  // pin a foot while the body sways
  await ev(() => { ds3d.setValues({ bodyX: 0 }, 0, true); ds3d.setValues({ bodyX: 12 }, 30, true); });
  r = await A({ action: 'pin', limb: 'legL', from: 0, to: 30 });
  const f0 = (await A({ action: 'end_point', limb: 'legL', frame: 0 })).at, f30 = (await A({ action: 'end_point', limb: 'legL', frame: 30 })).at;
  ok(r.worstErrorCm < 2 && Math.hypot(f0[0] - f30[0], f0[1] - f30[1], f0[2] - f30[2]) < 0.02, `pinned foot stays put (drift ${r.worstErrorCm} cm) while the body moves`);
  await ev(() => ds3d.undo()); await ev(() => ds3d.undo()); await ev(() => ds3d.undo());

  // motion path + arc fixer: a linear there-and-back pops at the turn
  await ev(() => { ds3d.setValues({ armR: 0 }, 0, true); ds3d.setValues({ armR: 90, armRForward: 30 }, 12, true); ds3d.setValues({ armR: 10, armRForward: -20 }, 24, true); for (const id of ['armR', 'armRForward']) ds3d.project.tracks[id].forEach(k => { k.ease = 'linear'; }); });
  r = await A({ action: 'path', what: 'armR' });
  ok(r.frames === 40 && r.pops.length >= 1, 'motion path shows popping arcs: ' + JSON.stringify(r.pops));
  ok(await p.locator('#path-layer').count() === 1, 'path drawn over the viewport');
  await p.screenshot({ path: path.join(out, 'motion-path.png') });
  r = await A({ action: 'fix_arcs', what: 'armR' });
  ok(r.popsAfter < r.popsBefore, `arc fixer smooths them (${r.popsBefore} → ${r.popsAfter})`);
  await A({ action: 'path', what: null });
  ok(await p.locator('#path-layer').count() === 0, 'path hidden again');

  // graph editor: drag a key down
  await ev(() => { ds3d.project.tracks = {}; ds3d.setValues({ armL: 0 }, 0, true); ds3d.setValues({ armL: 80 }, 20, true); ds3d.setValues({ armL: 10 }, 39, true); });
  await p.click('#subtabs .sub-chips button:has-text("Left arm")');
  await p.click('#curves-btn');
  const g = p.locator('#tracks canvas.graph');
  ok(await g.count() === 1, 'Curves shows the graph editor');
  const gb = await g.boundingBox(), W = await g.evaluate(c => c.width);
  const kx = gb.x + 40 + 20 * (W - 50) / 39, ky = gb.y + 14;
  await p.mouse.move(kx, ky); await p.mouse.down(); await p.mouse.move(kx, ky + 30, { steps: 4 }); await p.mouse.up();
  const v20 = await val('armL', 20);
  ok(v20 < 75 && v20 > 30, `dragging the key down lowers it (80 → ${v20})`);
  await p.screenshot({ path: path.join(out, 'graph-editor.png') });
  await p.click('#curves-btn');

  // time warp and moving hold
  await ev(() => { ds3d.project.tracks = {}; ds3d.setValues({ armL: 0 }, 0, true); ds3d.setValues({ armL: 60 }, 20, true); ds3d.setValues({ armL: 0 }, 39, true); });
  await A({ action: 'time_warp', warp: 'slow start', amount: 1 });
  st = await ev(() => ds3d.project.tracks.armL.map(k => k.f));
  ok(st[1] === Math.round(39 * Math.pow(20 / 39, 0.7)), 'slow-start warp slides the middle key later: ' + st);
  await ev(() => { ds3d.project.tracks = {}; ds3d.setValues({ armL: 0 }, 0, true); ds3d.setValues({ armL: 60 }, 10, true); });
  r = await A({ action: 'moving_hold', from: 10, to: 22 });
  ok(r.drifting >= 1 && (await val('armL', 22)) > 60, 'moving hold keeps drifting past 60: ' + (await val('armL', 22)));

  // pose library (face only)
  await ev(() => ds3d.setValues({ expression: 3, earLFold: -20 }, 5, true));
  await A({ action: 'save_pose', name: 'Shock', part: 'face' });
  await ev(() => ds3d.setValues({ expression: 0, earLFold: 15 }, 5, true));
  r = await A({ action: 'apply_pose', name: 'Shock', frame: 5 });
  ok((await val('expression', 5)) === 3 && (await val('earLFold', 5)) === 15, 'face pose keys the face only, ears untouched');
  await p.click('#tabs button:has-text("Pose")');
  ok(await p.locator('.pose-lib button:has-text("Shock")').count() === 1, 'pose library chip on the Pose tab');

  // copy keys to another shot, then retarget the scene to the Koala
  await ev(() => { ds3d.project.tracks = {}; ds3d.setValues({ armR: 40 }, 0, true); ds3d.setValues({ armR: 120 }, 15, true); });
  r = await A({ action: 'copy_keys', from: 0, to: 20 });
  await ev(() => ds3d.addShot(false));
  r = await A({ action: 'paste_keys', at: 0 });
  ok(r.keys >= 2 && (await val('armR', 15)) === 120, 'keys pasted into the new shot');
  r = await A({ action: 'retarget', character: 'koala' });
  st = await ev(() => ds3d.state());
  ok(r.character === 'koala' && st.character === 'koala', 'scene retargeted to the Koala: ' + JSON.stringify(r));

  // layers
  await ev(() => { ds3d.project.tracks = {}; ds3d.setValues({ armL: 30 }, 0, true); ds3d.setValues({ armL: 30 }, 30, true); });
  await A({ action: 'add_layer', name: 'Push' });
  await ev(() => ds3d.setValues({ armL: 50 }, 15, true));
  st = await ev(() => ({ base: ds3d.project.tracks.armL.map(k => k.v), layer: ds3d.project.layers[0].tracks.armL.map(k => k.v) }));
  ok(st.base.every(v => v === 30) && st.layer[0] === 20 && (await val('armL', 15)) === 50, 'keying on a layer leaves the base keys alone: ' + JSON.stringify(st));
  await A({ action: 'layer', index: 0, weight: 0.5 });
  ok((await val('armL', 15)) === 40, 'half weight halves the push');
  await A({ action: 'layer', index: 0, on: false, edit: false });
  ok((await val('armL', 15)) === 30, 'muting shows the base');
  ok(await p.locator('#timeline-tools select[aria-label="Keys go to"] option').count() === 2, 'Layers picker in the timeline');

  // Euler filter
  await ev(() => { ds3d.project.tracks.turn = [{ f: 0, v: 170, ease: 'ease' }, { f: 10, v: -170, ease: 'ease' }]; });
  r = await A({ action: 'euler_filter' });
  ok(r.fixed === 1 && (await ev(() => ds3d.project.tracks.turn[1].v)) === 190, 'Euler filter unwinds the 340° flip');
  await ev(() => { delete ds3d.project.tracks.turn; });

  // balance
  await ev(() => { ds3d.project.tracks = {}; ds3d.goto(0); });
  r = await A({ action: 'balance', on: true });
  ok(r.grounded && r.balanced === true, 'rest pose is balanced');
  ok(await p.locator('#hud span:has-text("Balanced")').count() === 1 && await p.locator('#cog-layer').count() === 1, 'balance light and marker');
  await A({ action: 'balance', on: false });

  // reference video, served with Range
  r = await A({ action: 'reference', path: vid, opacity: 0.5 });
  ok(r.reference.path === vid && r.duration > 3, 'reference video loaded: ' + JSON.stringify({ d: r.duration, w: r.width }));
  const tok = await ev(async x => (await (await fetch('/api/ref-video', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ path: x }) })).json()).url, vid);
  const part = await ev(async u => { const r = await fetch(u, { headers: { Range: 'bytes=0-99' } }); return [r.status, (await r.arrayBuffer()).byteLength, r.headers.get('content-range')]; }, tok);
  ok(part[0] === 206 && part[1] === 100, 'served in byte ranges for seeking: ' + part);
  ok((await ev(() => fetch('/ref/0000').then(r => r.status))) === 404, 'unregistered files are not served');
  await ev(() => { ds3d.selectShot(0); ds3d.goto(30); });
  await p.waitForTimeout(400);
  r = await A({ action: 'reference_info' });
  ok(Math.abs(r.video.time - 1) < 0.1, 'video follows the playhead: ' + r.video.time.toFixed(2) + ' s at frame 30');
  await p.screenshot({ path: path.join(out, 'reference-video.png') });
  r = await A({ action: 'reference', clear: true });
  ok(r.reference === null, 'reference removed');

  // clip blending
  await ev(() => { ds3d.project.tracks = {}; ds3d.setValues({ armR: 100, armL: -20 }, 0, true); });
  const snap = await ev(() => JSON.stringify(ds3d.project.tracks));
  r = await ev(() => ds3d.libraryUse('motion-wave-hello', { frame: 10 }));
  const cut = await val('armR', 10);
  await ev(s => { ds3d.project.tracks = JSON.parse(s); }, snap);
  r = await ev(() => ds3d.libraryUse('motion-wave-hello', { frame: 10, blend: 10 }));
  const blended = await val('armR', 10), endB = await val('armR', 30);
  await ev(s => { ds3d.project.tracks = JSON.parse(s); }, snap);
  await ev(() => ds3d.libraryUse('motion-wave-hello', { frame: 10 }));
  ok(r.blend === 10 && Math.abs(blended - 100) < 1 && Math.abs(cut - 100) > 5, `blend starts from the old pose (${blended}) where a cut jumps (${cut})`);
  ok(Math.abs(endB - (await val('armR', 30))) < 0.5, 'and lands fully on the clip after the blend');

  // multi-key move: MCP and shift-click
  await ev(() => { ds3d.project.tracks = {}; ds3d.setValues({ armL: 10 }, 4, true); ds3d.setValues({ armR: 10 }, 8, true); });
  r = await A({ action: 'move_keys', keys: [{ id: 'armL', f: 4 }, { id: 'armR', f: 8 }], by: 5 });
  st = await ev(() => [ds3d.project.tracks.armL[0].f, ds3d.project.tracks.armR[0].f]);
  ok(st[0] === 9 && st[1] === 13, 'two keys moved together by 5: ' + st);
  const keys = p.locator('#tracks .trow .lane .key:not([style*="opacity"])');
  await keys.nth(0).click(); await keys.nth(1).click({ modifiers: ['Shift'] });
  ok(await p.locator('#tracks .key.sel').count() === 2, 'shift-click selects two keys');
  await p.keyboard.press('Escape');

  // per-control reset (double-click the name)
  await p.click('#subtabs .sub-chips button:has-text("Left arm")');
  await ev(() => ds3d.setValues({ elbowL: 70 }, 0, true));
  await p.locator('#panel-content label.ctl[data-id="elbowL"] .name').dblclick();
  ok((await val('elbowL', 0)) === 0, 'double-click resets one control');

  // playblast with the scene audio
  await ev(w => ds3d.importAudio(w), wav);
  await ev(() => ds3d.setShot({ length: 20 }));
  r = await A({ action: 'playblast' });
  ok(r.audio && fs.readFileSync(r.path).includes('A_OPUS'), 'playblast carries the audio track');

  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
