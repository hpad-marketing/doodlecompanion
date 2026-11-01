// Reel templates and script to scene. Checks the planner (parsing, speakers, moods, captions,
// headlines, camera), then the app: every template builds a scene whose every third frame passes
// the rule check (no arm in the head, feet on the floor), with babble lip sync, captions inside the
// safe zone, headlines, Fill: markers, co-stars framed when they talk, the File menu picture cards,
// the script dialog, and the MCP tool. Run: node tools/test_reels.cjs
const path = require('path'), { spawn } = require('child_process'), { pathToFileURL } = require('url');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  const R = await import(pathToFileURL(path.join(__dirname, '..', 'app', 'src', 'reels.js')).href);
  const faces = require('../app/bunny3d.json').face.faces;
  ok(Object.values(R.MOODS).every(m => faces.includes(m.face)), 'every mood face is in Bunny\'s face library');
  ok(R.REELS.length === 5 && R.REELS.every(t => t.slots.length >= 4), 'five templates, four or more slots each');
  for (const t of R.REELS) {
    const p = R.fromTemplate(t.id);
    ok(p.beats.length >= 4 && p.seconds >= 10 && p.seconds <= 60, `${t.id}: ${p.beats.length} shots, ${p.seconds} s`);
    ok(p.beats.every(b => b.captions.every(c => c.split(' ').length <= 6)), `${t.id}: captions ≤ 6 words`);
    ok(p.beats.every(b => R.FRAMINGS[b.cam.size] && (b.cam.angle === 'eye' || b.cam.angle === 'low')), `${t.id}: reel framings, eye level or a low hero angle only`);
    ok(p.beats.filter(b => b.cam.angle === 'low').length <= 1, `${t.id}: at most one low angle`);
    ok(p.beats[0].headline, `${t.id}: the opening shot has a headline (${p.beats[0].headline})`);
  }
  const filled = R.fromTemplate('reel-myth-fact', { myth: 'Cats *hate* water.' });
  ok(filled.beats[0].text === 'Cats hate water.' && filled.unfilled.length === 3 && !filled.beats[0].fill && filled.beats[1].fill, 'a filled slot uses the line; the rest keep examples with a fill hint');
  const s = R.fromScript('# Cold open\nBUNNY: You will not believe what my *toaster* did. [points]\nKOALA: Did it burn the bread again?\nBUNNY: No. It started talking. It said my name, twice, at three in the morning, and then it asked me for butter.\nHot take: toast is bread that tried. [close-up] [snap zoom]');
  ok(s.lead === 'bunny' && s.costars.length === 1 && s.costars[0].character === 'koala', 'KOALA: makes the Koala a co-star');
  ok(s.beats[0].gesture === 'point' && s.beats[0].mood === 'shocked' && s.beats[0].headline === 'TOASTER' && s.beats[0].section === 'Cold open', 'directions, mood words, *key word* and # section');
  ok(s.beats[1].speaker === 0 && s.beats[1].cam.target === 'costar0' && s.beats[0].cam.target === 'group', 'the co-star\'s line frames the co-star; the opening frames everyone');
  ok(s.beats.filter(b => b.text.includes('butter') || b.text.includes('talking')).length === 2 && s.beats.every(b => b.text.split(' ').length <= 16), 'a long line splits into shots of ≤ 16 words, no one-word shot');
  ok(s.beats[s.beats.length - 1].who === null && s.beats[s.beats.length - 1].text.startsWith('Hot take:'), '"Hot take:" is a line, not a speaker');
  ok(s.beats[s.beats.length - 1].cam.size === 'medium' && s.beats[s.beats.length - 1].cam.move === 'snap-zoom', '[close-up] [snap zoom] steer the camera');
  let threw = false; try { R.fromScript('   \n  '); } catch { threw = true; }
  ok(threw, 'an empty script says what to paste');

  // the app
  const port = 54318, dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
  const { chromium } = require('playwright');
  await new Promise(r => setTimeout(r, 900));
  const br = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  try {
    const p = await (await br.newContext({ viewport: { width: 1920, height: 1032 } })).newPage();
    const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
    p.on('dialog', d => d.accept());
    await p.goto(`http://127.0.0.1:${port}/`);
    await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
    const ev = (fn, ...x) => p.evaluate(fn, ...x);
    for (const t of R.REELS) {
      const r = await ev(id => ds3d.reels({ action: 'fill', template: id, force: true }), t.id);
      const sc = await ev(() => { const s = ds3d.scene; return { n: s.shots.length, w: s.width, h: s.height, babble: (s.babble || []).length, caps: s.captions.tracks.en.length, capY: s.captions.y, heads: (s.headlines || []).length, fills: s.shots.flatMap(x => x.markers || []).filter(m => /^Fill:/.test(m.note)).length, mouth: s.shots.every(x => (x.tracks.mouth || []).length >= 3 || (x.costars || []).some(c => (c.tracks.mouth || []).length >= 3)), idle: s.shots.every(x => x.idle && x.idle.blink), audio: s.audio && s.audio.babble }; });
      ok(sc.n === r.shots.length && sc.w === 1080 && sc.h === 1920, `${t.id}: ${sc.n} shots at 1080×1920`);
      ok(sc.babble === sc.n && sc.mouth && sc.audio, `${t.id}: babble voice on every shot, mouths keyed`);
      ok(sc.caps >= sc.n && sc.capY === R.CAPTION_Y, `${t.id}: ${sc.caps} captions, low in the safe zone`);
      ok(sc.heads >= 1 && sc.fills === t.slots.length - (t.slots.some(x => x.headlineOnly) ? 1 : 0) && sc.idle, `${t.id}: ${sc.heads} headlines, Fill: markers, blinks on`);
      const bad = await ev(() => { const out = []; const s = ds3d.scene; for (let i = 0; i < s.shots.length; i++) { s.active = i; ds3d.scene = s; const len = ds3d.project.length; for (let f = 0; f < len; f += 3) { const r = ds3d.workflow({ action: 'rules', frame: f }); if (r.clips.length || r.belowFloor || r.inAir) out.push([ds3d.project.code, f, r.clips]); } } return out; });
      ok(!bad.length, `${t.id}: every third frame passes the rule check${bad.length ? ' ' + JSON.stringify(bad.slice(0, 3)) : ''}`);
      const cam = await ev(() => ds3d.scene.shots.map(s => (s.tracks['cam.roll'] || []).every(k => k.v === 0)));
      ok(cam.every(Boolean), `${t.id}: no camera roll`);
    }
    // the co-star talks: framed on the co-star (camera aimed beside the lead)
    await ev(() => ds3d.reels({ action: 'fill', template: 'reel-pov-skit', force: true }));
    const tx = await ev(() => ds3d.scene.shots.map(s => s.tracks['cam.tx'][0].v));
    ok(Math.abs(tx[1]) < 0.05 && Math.abs(tx[2]) > 0.3, `two-hander: Bunny's line on Bunny, the Koala's on the Koala (aim x ${tx.map(x => x.toFixed(2)).join(', ')})`);
    const last = await ev(() => { const s = ds3d.scene.shots.at(-1); return Object.entries(s.tracks).filter(([k]) => k.startsWith('cam.')).every(([k, v]) => k === 'cam.lens' || v.length === 1); });
    ok(last, 'the loop back leaves the last shot\'s camera alone');
    // script with captions only
    const r2 = await ev(() => ds3d.reels({ action: 'script', text: 'BUNNY: I tried to draw a *cat*. [proud]\nIt looks like a potato. [sigh]', voice: 'captions', force: true }));
    const sc2 = await ev(() => ({ babble: (ds3d.scene.babble || []).length, caps: ds3d.scene.captions.tracks.en.length, say: ds3d.scene.shots.flatMap(s => s.markers).filter(m => /^Say:/.test(m.note)).length }));
    ok(r2.shots.length === 2 && sc2.babble === 0 && sc2.caps >= 2 && sc2.say === 2, 'captions-only script: timed captions and Say: markers, no babble');
    ok(r2.shots[1].gesture === 'slump' && r2.shots[0].headline === 'CAT', '[sigh] slumps, *cat* is the headline');
    // headlines draw in the viewport
    await ev(() => ds3d.goto(5));
    ok(await ev(() => !!document.getElementById('post-layer')), 'the headline draws on the viewport');
    // dirty scene asks first
    await ev(() => ds3d.setValues({ armL: 20 }, 0, true));
    const asked = await p.evaluate(() => ds3d.reels({ action: 'fill', template: 'reel-hot-take' }).then(() => 'built', e => e.message));
    ok(asked === 'built' || /yes first/i.test(asked), 'unsaved changes: asks (MCP needs force) before a new scene');
    // File menu picture cards and the fill dialog
    await p.click('#menubar .menu > button:text-is("File")');
    await p.click('#menubar .menu-list button:has-text("New reel from a template")');
    ok(await p.locator('.ds-modal[aria-label="New reel from a template"] img[src^="reels/"]').count() === 5, 'File › New reel from a template shows five picture cards');
    const imgsOk = await p.waitForFunction(() => [...document.querySelectorAll('.ds-modal img[src^="reels/"]')].every(i => i.complete && i.naturalWidth > 0), null, { timeout: 5000 }).then(() => true, () => false);
    ok(imgsOk, 'the template pictures load');
    await p.click('.ds-modal button:has-text("Myth vs fact")');
    await p.fill('input[aria-label="Myth"]', 'Bunnies only eat *carrots*.');
    await p.click('.ds-modal button:has-text("Make the reel")');
    await p.waitForFunction(() => ds3d.scene.name === 'Myth vs fact' && (ds3d.scene.babble || []).length === 4, null, { timeout: 30000 });
    ok(await ev(() => ds3d.scene.babble[0].text === 'Bunnies only eat carrots.'), 'the fill dialog builds the reel with the typed line');
    await p.click('#menubar .menu > button:text-is("File")');
    await p.click('#menubar .menu-list button:has-text("Script to scene")');
    ok(await p.locator('.ds-modal[aria-label="Script to scene"] textarea').count() === 1, 'File › Script to scene opens');
    await p.keyboard.press('Escape');
    // the MCP tool is listed with its actions
    const mcp = require('../host/mcp.cjs');
    const handle = mcp({ call: async () => ({}) });
    const res = await new Promise(resolve => { const out = { writeHead() {}, end: b => resolve(JSON.parse(b)) }; handle({ method: 'POST', headers: {} }, out, JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/list' })); });
    const tool = res.result.tools.find(t => t.name === 'reels');
    ok(tool && tool.inputSchema.properties.action.enum.includes('script') && tool.inputSchema.properties.fills, 'MCP lists the reels tool');
    ok(!errs.length, 'no page errors' + (errs.length ? ': ' + errs.slice(0, 3).join(' | ') : ''));
  } finally { await br.close(); dev.kill(); }
})();
