// Stress-test fixes: lip sync from the voice, preflight reads the caption tracks and the
// horizon, no blocking dialogs during Claude calls, new/open/save-as scenes, macros record
// tool calls, IK solves against the head. Run: node tools/test_batch13.cjs
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54310, out = path.join(__dirname, '..', 'devout'), voice = path.join(out, 'voice13.wav');
fs.mkdirSync(out, { recursive: true });
{
  // a "voice": 0.3 s silence, then words: dark vowel, bright vowel, hiss, open vowel, with gaps
  const sr = 16000, n = sr * 4, d = Buffer.alloc(44 + n * 2);
  d.write('RIFF', 0); d.writeUInt32LE(36 + n * 2, 4); d.write('WAVEfmt ', 8); d.writeUInt32LE(16, 16); d.writeUInt16LE(1, 20); d.writeUInt16LE(1, 22);
  d.writeUInt32LE(sr, 24); d.writeUInt32LE(sr * 2, 28); d.writeUInt16LE(2, 32); d.writeUInt16LE(16, 34); d.write('data', 36); d.writeUInt32LE(n * 2, 40);
  const seg = [[0.3, 0.7, 'dark'], [0.75, 1.1, 'bright'], [1.1, 1.35, 'hiss'], [1.35, 1.8, 'open'], [2.3, 2.7, 'open'], [2.7, 2.95, 'hiss'], [2.95, 3.4, 'dark']];
  let seed = 7; const rnd = () => ((seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff) * 2 - 1;
  for (let i = 0; i < n; i++) {
    const t = i / sr, s = seg.find(([a, b]) => t >= a && t < b);
    let v = 0;
    if (s) {
      const env = Math.min(1, (t - s[0]) / 0.03, (s[1] - t) / 0.03);
      v = s[2] === 'dark' ? Math.sin(2 * Math.PI * 150 * t) * 0.9 + Math.sin(2 * Math.PI * 300 * t) * 0.3
        : s[2] === 'bright' ? Math.sin(2 * Math.PI * 160 * t) * 0.3 + Math.sin(2 * Math.PI * 2000 * t) * 0.5 + Math.sin(2 * Math.PI * 1200 * t) * 0.4
        : s[2] === 'hiss' ? rnd() * 0.5
        : Math.sin(2 * Math.PI * 180 * t) * 0.6 + Math.sin(2 * Math.PI * 900 * t) * 0.6;
      v *= env;
    }
    d.writeInt16LE(Math.round(12000 * Math.max(-1, Math.min(1, v))), 44 + i * 2);
  }
  fs.writeFileSync(voice, d);
}
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  let dialogs = 0; p.on('dialog', d => { dialogs++; d.accept(); });
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);

  // B1 lip sync
  await ev(() => { ds3d.setShot({ length: 120 }); ds3d.addShot(); ds3d.setShot({ length: 60 }); ds3d.selectShot(0); });
  await ev(w => ds3d.importAudio(w), voice);
  let r = await ev(() => ds3d.lipsync({ all: true }));
  ok(r.shots.length === 2 && r.shots[0].keys > 3 && r.shots[1].keys >= 1, 'lip sync keys the mouth on every shot (the second is silent): ' + r.shots.map(s => s.keys).join(', '));
  const m = await ev(() => { const s = ds3d.scene.shots[0]; return Array.from({ length: 120 }, (_, f) => { ds3d.goto(f); return Math.round(ds3d.state().values.mouth); }); });
  const at = s => m[Math.round(s * 30)];
  ok(at(0.15) === 1 && at(2.1) === 1, `rest mouth in the silences (${at(0.15)}, ${at(2.1)})`);
  ok([8, 10].includes(at(1.22)) && [8, 10].includes(at(2.82)), `teeth on the hiss (${at(1.22)}, ${at(2.82)})`);
  ok([4, 5, 6].includes(at(0.5)), `rounded mouth on the dark vowel (${at(0.5)})`);
  ok([2, 3, 9].includes(at(0.9)) && [2, 3].includes(at(1.55)), `open or wide mouth on the bright and open vowels (${at(0.9)}, ${at(1.55)})`);
  ok(m.slice(5, 12).includes(7) && m.slice(64, 72).includes(7), 'lips close (MBP) just before a word starts');
  let runs = [], k0 = 0; for (let f = 1; f <= m.length; f++) if (f === m.length || m[f] !== m[k0]) { runs.push(f - k0); k0 = f; }
  ok(runs.slice(1, -1).filter(x => x < 2).length <= 2, 'no one-frame mouth flicker (MBP may be one frame)');
  r = await ev(() => ds3d.production({ action: 'preflight' }));
  ok(r.checks.find(c => c.id === 'lipsync').ok, 'preflight lip sync check passes: ' + r.checks.find(c => c.id === 'lipsync').detail);

  // B2 caption tracks in the preflight
  await ev(() => { ds3d.selectShot(0); ds3d.goto(10); });
  await ev(() => ds3d.post({ action: 'caption', text: 'Dell well', length: 30 }));
  await ev(() => ds3d.post({ action: 'caption', text: 'this caption is far far far too long to ever fit inside the safe zone of a reel', length: 30, frame: 50 }));
  r = await ev(() => ds3d.production({ action: 'preflight' }));
  let cap = r.checks.find(c => c.id === 'captions');
  ok(!cap.ok && /too wide/.test(cap.detail) && !/No captions/.test(cap.detail), 'preflight reads the post caption tracks: ' + cap.detail.slice(0, 120));
  await ev(() => { const c = ds3d.scene.captions; c.tracks.en.splice(1, 1); c.y = 0.1; });
  r = await ev(() => ds3d.production({ action: 'preflight' }));
  cap = r.checks.find(c => c.id === 'captions');
  ok(!cap.ok && /safe zone/.test(cap.detail), 'a caption too high is outside the safe zone');
  await ev(() => { ds3d.scene.captions.y = 0.72; });
  r = await ev(() => ds3d.production({ action: 'preflight' }));
  cap = r.checks.find(c => c.id === 'captions');
  ok(cap.ok && /1 caption OK/.test(cap.detail), 'a short caption below the face passes: ' + cap.detail);
  // horizon and cuts
  const hz = r.checks.find(c => c.id === 'horizon'), cuts = r.checks.find(c => c.id === 'cuts');
  ok(hz && hz.ok, 'same camera on both shots: one horizon height (' + hz?.detail + ')');
  ok(cuts && cuts.ok && cuts.block === false, 'hard cut count reported, not blocking: ' + cuts?.detail);
  await ev(() => { ds3d.selectShot(1); ds3d.setValues({ 'cam.pitch': 25 }, 0, true); ds3d.selectShot(0); });
  r = await ev(() => ds3d.production({ action: 'preflight' }));
  ok(!r.checks.find(c => c.id === 'horizon').ok, 'tilting one shot\'s camera moves its horizon: ' + r.checks.find(c => c.id === 'horizon').detail);

  // B3 no blocking dialogs inside a Claude call
  await ev(() => ds3d.setValues({ armL: 30 }, 0, true));
  const d0 = dialogs;
  r = await ev(() => { ds3dClaude.begin('workflow', 10, false, {}); try { return { r: ds3d.workflow({ action: 'from_template', template: 'quick-take' }) }; } catch (e) { return { err: e.message }; } finally { ds3dClaude.end(0, false); } });
  ok(r.err && /Needs a yes first/.test(r.err) && dialogs === d0, 'from_template on an unsaved scene fails with "Needs a yes first", no dialog');
  r = await ev(() => { ds3dClaude.begin('workflow', 10, true, {}); try { return ds3d.workflow({ action: 'from_template', template: 'quick-take' }); } finally { ds3dClaude.end(0, false); } });
  ok(r && r.template === 'quick-take' && dialogs === d0, 'force: true goes ahead without a dialog');
  r = await ev(() => { ds3dClaude.begin('x', 1, false, {}); try { prompt('Name?'); return 'no'; } catch (e) { return e.message; } finally { ds3dClaude.end(0, false); } });
  ok(/Pass the value/.test(r) && dialogs === d0, 'prompt() during a Claude call fails instead of waiting');
  await ev(() => confirm('UI still asks?'));
  ok(dialogs === d0 + 1, 'outside Claude calls the app still asks the user');
  r = await ev(async () => { ds3dClaude.begin('render', 1, false, {}); try { await ds3d.render({ }); return 'started'; } catch (e) { return e.message; } finally { ds3dClaude.end(0, false); } });
  ok(/Needs a yes first/.test(r) && /GB free/.test(r), 'low disk before a render fails the call instead of a dialog');

  // B4 new / save as / open
  r = await ev(() => { ds3dClaude.begin('new_scene', 1, false, {}); try { return ds3d.newScene({ name: 'Blank test' }); } catch (e) { return e.message; } finally { ds3dClaude.end(0, false); } });
  ok(typeof r === 'string' && /Needs a yes/.test(r), 'new_scene with unsaved changes needs force');
  r = await ev(() => ds3d.newScene({ name: 'Blank test', character: 'koala' }));
  r = await ev(() => ds3d.state());
  ok(r.shots.length === 1 && (await ev(() => ds3d.scene.name)) === 'Blank test' && (await ev(() => ds3d.scene.character)) === 'koala', 'new_scene starts a blank koala scene');
  await ev(() => ds3d.setValues({ armR: 44 }, 0, true));
  const file = path.join(out, 'saveas13', 'Copy13.ds3d');
  r = await ev(f => ds3d.saveAs({ path: f }), file);
  ok(fs.existsSync(file) && JSON.parse(fs.readFileSync(file, 'utf8')).shots[0].tracks.armR[0].v === 44, 'save_as writes the scene to the new path');
  await ev(() => ds3d.newScene({ name: 'Other' }));
  r = await ev(f => ds3d.openScene(f), file);
  ok(r.path === file && (await ev(() => ds3d.scene.shots[0].tracks.armR[0].v)) === 44, 'open_scene loads it back');
  r = await ev(() => ds3d.saveAs({ name: 'Renamed13' }));
  ok(r.path && /Renamed13/.test(r.path) && (await ev(() => ds3d.scene.name)) === 'Renamed13', 'save_as with a name saves under that name: ' + r.path);

  // B7 macros record Claude tool calls; link error names real controls
  await ev(() => ds3d.powers({ action: 'macro_start' }));
  await ev(() => { ds3dClaude.begin('set_values', 5, false, { values: { armL: 12 }, frame: 0 }); ds3dClaude.end(5, false); ds3dClaude.begin('get_state', 1, false, {}); ds3dClaude.end(1, false); });
  r = await ev(() => ds3d.powers({ action: 'macro_stop', name: 'm13' }));
  const steps = await ev(() => JSON.parse(localStorage.getItem('ds3d.macros'))['m13']);
  ok(r.steps === 1 && steps[0].tool === 'set_values' && steps[0].args.values.armL === 12, 'tool calls are recorded (read-only ones left out)');
  await ev(() => ds3d.powers({ action: 'macro_start' }));
  r = await ev(async () => { try { await ds3d.powers({ action: 'macro_stop', name: 'empty' }); return 'saved'; } catch (e) { return e.message; } });
  ok(/Nothing was recorded/.test(r), 'an empty recording says so and saves nothing');
  r = await ev(async () => { try { await ds3d.powers({ action: 'link', from: 'headTurn', to: 'armL' }); return 'linked'; } catch (e) { return e.message; } });
  ok(/headYaw/.test(r) && /headTurn is not one/.test(r), 'link error names real controls: ' + r);

  // B6 IK against the head
  await ev(() => { ds3d.newScene({ name: 'IK13', force: true }); });
  // a target in the middle of the face: the solver must not leave the arm in the head
  r = await ev(async () => { const e = (await ds3d.anim2({ action: 'end_point', limb: 'armR' })).at; return ds3d.anim2({ action: 'ik', limb: 'armR', target: [0, e[1], 0.4] }); });
  const rules = await ev(() => ds3d.workflow({ action: 'rules' }));
  const clipR = (rules.clips || []).filter(c => c.endsWith('.R'));
  ok(!clipR.length ? !!r.note : !!r.warning, `IK toward the face: ${r.note || r.warning || 'no change needed'} (clips now: ${clipR.join(', ') || 'none'})`);
  r = await ev(async () => ds3d.anim2({ action: 'ik', limb: 'armR', offset: [0.05, 0, 0] }));
  ok(!r.warning, 'an ordinary IK move gives no warning');

  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
