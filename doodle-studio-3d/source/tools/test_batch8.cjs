// Storytime part 2: cold open, beat map, mood strip, genre moments, gestures from voice,
// eye darts, jump scare, auto foley, freeze-frame label, chapter cards, sponsor segue,
// Shorts, retention overlay. Run: node tools/test_batch8.cjs
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54303, out = path.join(__dirname, '..', 'devout'), voice = path.join(out, 'voice8.wav');
{
  // a "voice": syllable bursts every 0.35 s for 4 s
  const sr = 16000, n = sr * 4, d = Buffer.alloc(44 + n * 2);
  d.write('RIFF', 0); d.writeUInt32LE(36 + n * 2, 4); d.write('WAVEfmt ', 8); d.writeUInt32LE(16, 16); d.writeUInt16LE(1, 20); d.writeUInt16LE(1, 22);
  d.writeUInt32LE(sr, 24); d.writeUInt32LE(sr * 2, 28); d.writeUInt16LE(2, 32); d.writeUInt16LE(16, 34); d.write('data', 36); d.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) { const t = i / sr, ph = t % 0.35, a = ph < 0.12 ? Math.sin(ph / 0.12 * Math.PI) : 0.05; d.writeInt16LE(Math.round(14000 * a * Math.sin(t * 2 * Math.PI * 180)), 44 + i * 2); }
  fs.writeFileSync(voice, d);
}
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('dialog', d => d.accept(d.type() === 'prompt' ? 'Acme Tea' : undefined));
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  const S = a => ev(x => ds3d.story2(x), a);
  const val = (id, f) => ev(([id, f]) => { ds3d.goto(f); return ds3d.state().values[id]; }, [id, f]);

  // cold open
  await ev(() => { ds3d.setShot({ length: 90 }); ds3d.setValues({ armL: 0 }, 0, true); ds3d.setValues({ armL: 90 }, 89, true); });
  let r = await S({ action: 'cold_open', seconds: 1 });
  let st = await ev(() => ds3d.state());
  ok(st.shots.length === 2 && st.shots[0].name === 'Cold open' && st.shots[0].length === 30, 'cold open: the last second leads the video');
  const c0 = await val('armL', 0), c15 = await val('armL', 15);
  await ev(() => ds3d.selectShot(1));
  const o60 = await val('armL', 60), o75 = await val('armL', 75);
  await ev(() => ds3d.selectShot(0));
  ok(Math.abs((await val('armL', 29)) - 90) < 0.5 && Math.abs(c0 - o60) < 0.05 && Math.abs(c15 - o75) < 0.05, `and plays the same motion (${c0.toFixed(1)} = ${o60.toFixed(1)})`);
  ok(await ev(() => ds3d.scene.shots[1].items.some(it => it.id === 'story:time_skip' && /Earlier/.test(it.text))), 'rewind card on the next shot');

  // beat map
  r = await S({ action: 'beat_map' });
  ok(r.missing.length === 7, 'beat map: all seven beats missing at first');
  await S({ action: 'add_beat', beat: 'climax' });
  r = await S({ action: 'beat_map' });
  ok(r.beats.find(x => x.id === 'climax').at != null && r.missing.length === 6, 'adding a beat marker fills it: ' + r.beats.find(x => x.id === 'climax').where);

  // mood strip
  r = await S({ action: 'mood', shot: 0, mood: 'scary' });
  st = await ev(() => ds3d.stage());
  ok(r.mood === 'scary' && st.stage.time === 'night', 'scary mood sets night light');
  ok(await p.locator('.shot-chip[style*="box-shadow"]').count() === 1, 'mood colour on the shot chip');
  await p.click('#menubar .menu > button:text-is("Story")');
  await p.click('#menubar .menu-list button:has-text("Mood strip")');
  ok(await p.locator('.mood-strip .mood-swatch').count() === 2, 'mood strip dialog shows each shot');
  await p.screenshot({ path: path.join(out, 'mood-strip.png') });
  await ev(() => document.querySelectorAll('.ds-modal').forEach(m => m.remove()));

  // genre moment
  await ev(() => ds3d.selectShot(1));
  r = await S({ action: 'genre', genre: 'horror', frame: 10 });
  st = await ev(() => ({ items: ds3d.project.items.map(i => i.id), cam: ds3d.project.tracks['cam.dist'] }));
  ok(st.items.includes('sound:sting') && st.cam.length === 2 && st.cam[1].v < st.cam[0].v && st.cam.every(k => k.ease === 'ease'), 'horror moment: sting, drone and an eased push in');

  // gestures and eye darts
  await ev(w => ds3d.importAudio(w), voice);
  r = await S({ action: 'gestures' });
  st = await ev(() => ds3d.project.layers.find(L => L.name === 'Gestures'));
  ok(r.gestures >= 3 && st && !st.tracks.mouth && !st.tracks.jaw && st.tracks.headNod, `${r.gestures} gestures on their own layer, head and body only`);
  r = await S({ action: 'eye_darts' });
  ok(r.darts >= 1 && (await ev(() => ds3d.project.tracks.gaze.length)) >= 2, `${r.darts} eye darts keyed on the gaze`);

  // jump scare
  r = await S({ action: 'jump_scare', frame: 60 });
  ok(await ev(() => ds3d.project.markers.some(m => /quiet/.test(m.note)) && ds3d.project.items.some(i => i.id === 'sound:sting' && i.frame === 60)), 'jump scare: quiet marker, sting on the frame');

  // auto foley
  await ev(() => { ds3d.setValues({ armR: 0 }, 30, true); ds3d.setValues({ armR: 140 }, 33, true); });
  r = await S({ action: 'foley' });
  ok(r.sounds.some(s => s.id === 'sound:whoosh' && s.frame >= 30 && s.frame <= 34), 'fast arm swing gets a whoosh: ' + JSON.stringify(r.sounds));
  const n1 = r.sounds.length;
  r = await S({ action: 'foley' });
  ok(r.sounds.length === n1, 're-running replaces the auto sounds instead of stacking them');

  // freeze-frame label
  const len0 = (await ev(() => ds3d.project.length));
  const a20 = await val('armR', 20);
  r = await S({ action: 'freeze_label', frame: 20, text: 'Bunny: professional napper' });
  ok((await ev(() => ds3d.project.length)) === len0 + 45 && Math.abs((await val('armR', 50)) - a20) < 0.01 && Math.abs((await val('armR', 33 + 45)) - 140) < 0.5, 'freeze holds the pose 1.5 s, then the motion carries on');
  ok(await ev(() => ds3d.project.items.some(i => i.id === 'story:label' && i.text.startsWith('Bunny'))), 'name label pinned');

  // chapter cards + sponsor
  await ev(() => { ds3d.addMarker(0, 'Chapter: The setup'); });
  r = await S({ action: 'chapter_cards' });
  ok(r.cards === 1, 'chapter card made from the chapter marker');
  r = await S({ action: 'sponsor', name: 'Acme Tea' });
  st = await ev(() => ds3d.state());
  ok(st.shots.length === 3 && st.shots[2].name === 'Sponsor' && st.shot === r.shot, 'sponsor segue shot added after the active one');

  // Shorts
  await ev(() => { ds3d.selectShot(0); ds3d.addMarker(0, 'short: The scare'); });
  r = await S({ action: 'shorts_plan' });
  ok(r.length >= 1 && r[0].title === 'The scare', 'shorts plan from the short: marker');
  r = await S({ action: 'shorts' });
  const sh = JSON.parse(fs.readFileSync(r.shorts[0].path, 'utf8'));
  ok(sh.width === 1080 && sh.height === 1920 && sh.shots.length >= 1 && fs.existsSync(sh.audio.path), `Short saved as a 9:16 scene with its voice: ${path.basename(r.shorts[0].path)} (${r.shorts[0].seconds} s)`);

  // retention overlay
  const csv = 'Video position (%),Absolute audience retention (%)\n0,100\n10,82\n20,78\n30,52\n40,50\n60,45\n80,40\n100,30\n';
  r = await S({ action: 'retention', csv });
  ok(r.points === 8 && r.drops.length && r.drops[0].lost >= 20, 'retention CSV parsed, biggest drop found: ' + JSON.stringify(r.drops[0]));
  ok(await p.locator('#tracks svg.retention polyline').count() === 1, 'retention curve on the timeline');
  await p.screenshot({ path: path.join(out, 'retention.png') });

  ok(!errs.length, 'no page errors ' + errs.join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e); dev.kill(); process.exit(1); });
