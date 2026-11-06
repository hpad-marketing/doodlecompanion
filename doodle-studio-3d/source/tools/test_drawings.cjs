// Drawings layer: SVG import, hand drawing, screen and scene layers, draw-on, boil, the render's
// post PNGs and the Blender bridge. Run: node tools/test_drawings.cjs [svg]
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54321, out = path.join(__dirname, '..', 'devout'), shots = path.join(out, 'drawings-test');
fs.mkdirSync(shots, { recursive: true });
const svg = process.argv[2] ? fs.readFileSync(process.argv[2], 'utf8') : `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 160"><g transform="translate(10,10)" stroke="#000" fill="none"><path d="M20 120 L60 30 L100 120 Z M40 90 L80 90"/><circle cx="150" cy="50" r="28"/></g><text x="10" y="150">ignored</text><defs><path d="M0 0 L500 500"/></defs></svg>`;
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 800));
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 950 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
  const ev = (fn, ...a) => p.evaluate(fn, ...a);
  await ev(() => ds3d.setShot({ length: 60 }));
  let r = await ev(s => ds3d.drawings({ action: 'import', svg: s, name: 'art', at_frame: 5, frame: 5, build: 20 }), svg);
  ok(r.index === 0 && r.strokes >= 3 && r.layer === 'screen', `SVG import makes a screen drawing (${r.strokes} lines)`);
  r = await ev(() => ds3d.drawings({ action: 'list' }));
  const d = r.drawings[0];
  ok(d.frame === 5 && d.build === 20 && d.noise === 0.5 && d.colour === 'ink', 'defaults: starts at the playhead, 20-frame draw-on, noise 0.5, ink');
  const px = async f => { await ev(f => ds3d.goto(f), f); return ev(() => { const c = document.getElementById('drawing-layer'); if (!c) return -1; const g = c.getContext('2d'), a = g.getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < a.length; i += 4) if (a[i] > 128) n++; return n; }); };
  const before = await px(4), mid = await px(14), full = await px(30);
  ok(before === 0 && mid > 0 && full > mid * 1.3, `draws on: ${before} px before, ${mid} halfway, ${full} drawn`);
  const boilA = await ev(() => { ds3d.goto(31); return document.getElementById('drawing-layer').toDataURL(); });
  const boilB = await ev(() => { ds3d.goto(33); return document.getElementById('drawing-layer').toDataURL(); });
  const boilC = await ev(() => { ds3d.goto(32); return document.getElementById('drawing-layer').toDataURL(); });
  ok(boilA !== boilB && boilA === boilC, 'the line boils on twos (a new wobble every 2 frames)');
  // colours: only ink or mustard pixels
  const cols = await ev(() => { const c = document.getElementById('drawing-layer'), a = c.getContext('2d').getImageData(0, 0, c.width, c.height).data, s = new Set(); for (let i = 0; i < a.length; i += 4) if (a[i + 3] > 250) s.add(a[i] + ',' + a[i + 1] + ',' + a[i + 2]); return [...s]; });
  ok(cols.length && cols.every(c => { const [r, g, b] = c.split(',').map(Number); return Math.abs(r - 31) + Math.abs(g - 31) + Math.abs(b - 29) < 8; }), 'solid pixels are ink only: ' + cols.slice(0, 3).join(' '));
  await ev(() => ds3d.goto(14)); await p.locator('#frame').screenshot({ path: path.join(shots, '1-screen-drawing-on.png') });
  await ev(() => ds3d.goto(30)); await p.locator('#frame').screenshot({ path: path.join(shots, '2-screen-drawn.png') });
  // the render: PNGs per distinct look, runs never overlap
  await ev(() => ds3d.render({ preview: true }));
  await new Promise(r => setTimeout(r, 1500));
  const post = JSON.parse(fs.readFileSync(path.join(out, 'post-shot.json'), 'utf8'));
  const runs = post.drawings || [];
  const uniq = new Set(runs.map(x => x.path));
  ok(runs.length > 0 && runs[0].start === 5 && runs.every((x, i) => !i || x.start >= runs[i - 1].start + runs[i - 1].length), `render gets ${runs.length} drawing strips from ${uniq.size} PNGs, starting at frame 5`);
  ok([...uniq].every(f => fs.existsSync(f)), 'every drawing PNG was written');
  ok(runs.reduce((a, x) => a + x.length, 0) === 55, 'the layer covers frames 5 to the end of the shot');
  // until + settings
  r = await ev(() => ds3d.drawings({ action: 'set', index: 0, until: 40, colour: 'mustard', noise: 0 }));
  ok(r.drawing.until === 40 && r.drawing.colour === 'mustard', 'gone-at frame and mustard set');
  ok(await px(45) === 0 && await px(35) > 0, 'gone after its until frame');
  r = await ev(() => ds3d.drawings({ action: 'set', index: 0, colour: 'white' }).then(() => 'took', e => e.message));
  ok(/brand/.test(r), 'white is refused: ' + r);
  // scene layer
  r = await ev(() => ds3d.drawings({ action: 'set', index: 0, layer: 'scene', depth: 1, until: null, colour: 'ink', noise: 0.5 }));
  ok(r.drawing.layer === 'scene' && r.drawing.placed, 'moved into the 3D scene and placed from the camera');
  ok(await px(30) === -1, 'the screen layer is gone when nothing is on it');
  await ev(() => ds3d.goto(30)); await p.locator('#frame').screenshot({ path: path.join(shots, '3-scene-drawing.png') });
  const br = await ev(() => { ds3d.render({ preview: true }); return true; });
  await new Promise(r => setTimeout(r, 1500));
  const req = JSON.parse(fs.readFileSync(path.join(out, 'render-req.json'), 'utf8'));
  ok(req.shot.drawings?.length === 1 && req.shot.drawings[0].world?.h > 0, `Blender gets the scene drawing (h ${req.shot.drawings?.[0]?.world?.h} m)`);
  // hand drawing
  r = await ev(() => ds3d.drawings({ action: 'draw', strokes: [[[0.2, 0.2], [0.4, 0.25], [0.5, 0.4]], [[0.6, 0.6], [0.7, 0.62]]], frame: 0, build: 0 }));
  ok(r.index === 1, 'hand lines become a drawing');
  r = await ev(() => ds3d.drawings({ action: 'list' }));
  const hd = r.drawings[1];
  ok(Math.abs(hd.y - 0.41) < 0.02 && Math.abs(hd.size - 0.42) < 0.02, `the hand drawing stays where it was drawn (y ${hd.y.toFixed(3)}, size ${hd.size.toFixed(3)})`);
  await p.click('#tabs button:text-is("Stage")');
  ok(await p.locator('#subtabs button:has-text("Drawings")').count() === 0, 'Stage no longer has a second Drawings section');
  await p.click('#tabs button:text-is("Draw")');
  ok(await p.locator('img[src^="data:image/png"]').count() >= 2, 'Draw workspace shows a picture of each drawing');
  const lastNoise = () => ev(() => ds3d.project.drawings.at(-1).noise);
  const noiseStart = await lastNoise();
  await p.locator('input[aria-label="Noise"]').evaluate(el => { el.dispatchEvent(new Event('pointerdown')); el.value = 80; el.dispatchEvent(new Event('input', { bubbles: true })); });
  ok(await lastNoise() === 0.8, 'the Noise slider moves the line live');
  await p.locator('input[aria-label="Noise"]').evaluate(el => el.dispatchEvent(new Event('change', { bubbles: true })));
  await p.click('.dr-row button:text-is("Shaky")');
  ok(await lastNoise() === 1 && await ev(() => ds3d.project.drawings.at(-1).boil) === 2, 'Shaky sets noise 100%, on twos');
  await ev(() => ds3d.undo()); ok(await lastNoise() === 0.8, 'Undo steps back to the slider value');
  await ev(() => ds3d.undo()); ok(await lastNoise() === noiseStart, 'the whole slider drag is one undo step');
  await p.screenshot({ path: path.join(shots, '4-panel.png') });
  // undo
  await ev(() => ds3d.undo && ds3d.undo());
  r = await ev(() => ds3d.drawings({ action: 'list' }));
  ok(r.drawings.length === 1, 'undo removes the hand drawing');
  ok(!errs.length, 'no page errors' + (errs.length ? ': ' + errs.join(' | ') : ''));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e.stack || e); dev.kill(); process.exit(1); });
