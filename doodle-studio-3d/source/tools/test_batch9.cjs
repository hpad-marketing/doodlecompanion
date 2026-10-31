// Storytime part 3: looks, photo cut-in, narrator PiP, imagination bubble, captions
// (English / Hindi, one line for short ones, word highlight, SRT), music bed ducking,
// bleeps and character voices. Run: node tools/test_batch9.cjs
const { spawn, execFileSync } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54304, out = path.join(__dirname, '..', 'devout'), voice = path.join(out, 'voice9.wav'), photo = path.join(out, 'photo9.png'), clip = path.join(out, 'clip9.mp4');
fs.mkdirSync(out, { recursive: true });
{
  const sr = 16000, n = sr * 4, d = Buffer.alloc(44 + n * 2);
  d.write('RIFF', 0); d.writeUInt32LE(36 + n * 2, 4); d.write('WAVEfmt ', 8); d.writeUInt32LE(16, 16); d.writeUInt16LE(1, 20); d.writeUInt16LE(1, 22);
  d.writeUInt32LE(sr, 24); d.writeUInt32LE(sr * 2, 28); d.writeUInt16LE(2, 32); d.writeUInt16LE(16, 34); d.write('data', 36); d.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) { const t = i / sr, a = t > 1 && t < 2.5 ? 1 : 0.02; d.writeInt16LE(Math.round(14000 * a * Math.sin(t * 2 * Math.PI * 180)), 44 + i * 2); }
  fs.writeFileSync(voice, d);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=0xE0A64B:s=320x240', '-frames:v', '1', photo]);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=0x1F1F1D:s=320x180:d=1', clip]);
}
for (const f of ['post-scene.json', 'post-shot.json']) fs.rmSync(path.join(out, f), { force: true });
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.accept());
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const P = a => ev(x => ds3d.post(x), a);
  await ev(() => { ds3d.setShot({ length: 90 }); ds3d.addShot(); });
  await ev(() => ds3d.selectShot(0));

  // looks
  let r = await P({ action: 'look', look: 'flashback' });
  ok(r.look === 'flashback' && await p.locator('#post-layer').count() === 1, 'flashback look on the shot, previewed in the viewport');

  // cut-ins
  r = await P({ action: 'photo', path: photo, frame: 10, seconds: 1 });
  ok(r.cuts === 1, 'photo cut-in added');
  r = await P({ action: 'pip', path: clip, frame: 20, seconds: 1, corner: 'tl' });
  r = await P({ action: 'bubble', clip_shot: 1, frame: 40, seconds: 1 });
  const cuts = await P({ action: 'cuts' });
  ok(cuts.length === 3 && cuts[2].shotRef === 'sh020' && cuts[1].corner === 'tl', 'narrator PiP and an imagination bubble playing shot 2');
  await ev(() => ds3d.goto(45));
  await p.waitForTimeout(200);
  await p.screenshot({ path: path.join(out, 'post-bubble.png') });

  // captions: short ones on one line, long ones on two, both languages
  await P({ action: 'caption', text: 'Dell well', frame: 0, seconds: 1 });
  await P({ action: 'caption', text: 'and then the whole room went completely quiet', frame: 30, seconds: 2 });
  const lines = await ev(() => import('./src/post.js').then(P => [P.captionLines('Dell well').length, P.captionLines('and then the whole room went completely quiet').length]));
  ok(lines[0] === 1 && lines[1] === 2, `1-3 word caption stays on one line, longer takes two (${lines})`);
  await P({ action: 'caption_lang', lang: 'hi' });
  await P({ action: 'caption', text: 'फिर सब चुप', frame: 0, seconds: 1 });
  r = await P({ action: 'captions' });
  ok(r.active === 'hi' && r.lines.length === 1, 'Hindi track kept apart from English');
  await P({ action: 'caption_lang', lang: 'en' });
  r = await P({ action: 'srt_export' });
  const srt = fs.readFileSync(r.path, 'utf8');
  ok(/00:00:00,000 --> 00:00:01,000\nDell well/.test(srt) && srt.includes('00:00:01,000 --> 00:00:03,000'), 'SRT export with scene times');
  await P({ action: 'clear_captions' });
  r = await P({ action: 'srt_import', srt });
  ok(r.lines === 2, 'SRT import round-trips');
  await P({ action: 'highlight', on: true });

  // sound side: music bed, bleep, voice
  await ev(w => ds3d.importAudio(w), voice);
  await P({ action: 'music', path: voice, volume: 0.4, duck: 0.25 });
  await ev(() => { ds3d.addMarker(36, 'bleep: 0.5'); ds3d.addMarker(45, 'voice: chipmunk'); ds3d.addMarker(60, 'voice: normal'); ds3d.addMarker(70, 'quiet'); ds3d.addMarker(85, 'scare'); });
  r = await P({ action: 'build' });
  ok(r.looks.length === 1 && r.looks[0].saturation === 0 && r.looks[0].overlays.some(o => o.blend === 'MULTIPLY') && r.looks[0].overlays.every(o => fs.existsSync(o.path)), 'flashback: grey picture, warm multiply, vignette PNG');
  ok(r.movies.length === 2 && r.movies[0].path === clip && r.movies[1].shotRef === 'sh020' && r.movies[1].rect.w > 0, 'PiP and bubble clips placed');
  const caps = r.overlays.filter(o => /caption/.test(o.path));
  ok(caps.length === 2 + 8 && caps.every(o => fs.existsSync(o.path)), `word highlight: one caption image per word (${caps.length})`);
  ok(r.bleeps.length === 1 && r.bleeps[0][0] === 36 && r.bleeps[0][1] === 51, 'bleep marker becomes a bleep span ' + JSON.stringify(r.bleeps));
  ok(r.voice && fs.existsSync(r.voice) && fs.statSync(r.voice).size > 100000, 'character voice written as a processed copy of the scene audio');
  const keys = r.music.keys, at = f => keys.filter(k => k[0] <= f).pop()?.[1];
  ok(at(10) > 0.35 && at(65) < 0.2 && at(84) < 0.02, `music dips under the voice and goes quiet before the scare (${at(10)}, ${at(65)}, ${at(84)})`);
  await p.screenshot({ path: path.join(out, 'post-caption.png') });

  const png = fs.readFileSync(caps[0].path);
  ok(png.length > 1000, 'caption image written');

  // the renders carry it
  await ev(() => ds3d.renderScene({ preview: true }));
  await p.waitForTimeout(1500);
  const ps = JSON.parse(fs.readFileSync(path.join(out, 'post-scene.json'), 'utf8'));
  ok(ps.music && ps.looks.length === 1 && ps.movies.length === 2, 'scene render sends the post plan');
  await ev(() => ds3d.render({ preview: true }));
  await p.waitForTimeout(1500);
  const pshot = JSON.parse(fs.readFileSync(path.join(out, 'post-shot.json'), 'utf8'));
  ok(!pshot.music && !pshot.bleeps && pshot.looks.length === 1, 'single shot render: looks and cut-ins, no scene sound side');

  // menu
  await p.click('#menubar .menu > button:text-is("Post")');
  await p.click('#menubar .menu-list button:has-text("Captions…")');
  ok(await p.locator('.ds-modal button:text-is("Hindi")').count() === 1, 'captions dialog with language tabs');
  await ev(() => document.querySelectorAll('.ds-modal').forEach(m => m.remove()));

  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
