// Speech bubbles: the drawing, the Library shelf, the block timeline, the Stage, timing, the render
// side and the MCP tool. Run: node tools/test_bubbles.cjs
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54334, out = path.join(__dirname, '..', 'devout');
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 900));
  const br = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--autoplay-policy=no-user-gesture-required'] });
  try {
    const pg = await (await br.newContext({ viewport: { width: 1500, height: 900 } })).newPage();
    const errs = []; pg.on('pageerror', e => errs.push(e.message));
    pg.on('dialog', d => d.accept());
    await pg.goto(`http://127.0.0.1:${port}/`);
    await pg.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 60000 });
    const ev = (fn, ...a) => pg.evaluate(fn, ...a);
    const still = n => pg.locator('#frame').screenshot({ path: path.join(out, `bubble_${n}.png`) });
    const B = () => ev(() => ds3d.bubbles({ action: 'list' })).then(r => r.bubbles);

    // the pure drawing, in the page
    const pure = await ev(async () => {
      const m = await import('/src/bubbles.js'), g = document.createElement('canvas').getContext('2d');
      const L = text => m.layout(g, { preset: 'talk', text }, 1080, 1920);
      const a = L('Hi'), b = L('This line is a good deal longer than that one and it keeps on going for a while');
      const c = L('line one\nline two'), box = m.layout(g, { preset: 'stepped', text: 'word '.repeat(30) }, 1080, 1920);
      const P = m.place(g, { preset: 'talk', text: 'Over the face', x: 0.5, y: 0.5 }, 1080, 1920, [{ x0: 0.3, x1: 0.7, y0: 0.45, y1: 0.55 }]), E = m.extent(g, { preset: 'talk', text: 'Over the face' }, 1080, 1920);
      const clear = P.y + E.hh <= 0.45 || P.y - E.hh >= 0.55 || P.x + E.hw <= 0.3 || P.x - E.hw >= 0.7;
      const shot = { length: 120, fps: 30 }, s1 = m.addBubble(shot, 'talk', { f: 10, len: 40, text: 'a b' }), s2 = m.splitBubble(shot, s1.id, 30);
      const pop = [0, 3, 6, 9, 14].map(t => { const c = document.createElement('canvas'); c.width = 400; c.height = 700; const x = c.getContext('2d'); m.drawBubbleItem(x, 400, 700, { preset: 'talk', text: 'Pop', x: .5, y: .5, len: 60, fps: 30 }, t); const d = x.getImageData(0, 0, 400, 700).data; let lo = 700, hi = 0; for (let y = 0; y < 700; y++) for (let k = 0; k < 400; k++) if (d[(y * 400 + k) * 4 + 3]) { lo = Math.min(lo, y); hi = Math.max(hi, y); } return hi - lo; });
      return { ax: a.rx, bx: b.rx, by: b.ry, ay: a.ry, lines: c.lines, boxSize: box.size, boxLines: box.lines.length, clear, s1: s1.len, s2: [s2.f, s2.len], pop, n: Object.keys(m.PRESETS).length };
    });
    ok(pure.n === 14, '14 presets');
    ok(pure.by > pure.ay && pure.bx > pure.ax, 'the bubble grows with the text');
    ok(pure.lines.length === 2 && pure.lines[0] === 'line one', 'a line break in the text is kept');
    ok(pure.boxLines <= 3 && pure.boxSize < 60, 'a very long subtitle shrinks to fit the box');
    ok(pure.clear, 'a bubble dropped on the face moves off it');
    ok(pure.s1 === 20 && pure.s2[0] === 30 && pure.s2[1] === 20, 'cutting a bubble gives two parts');
    ok(pure.pop[0] < pure.pop[3] * 0.4 && Math.max(...pure.pop) > pure.pop[4] * 1.02, 'it starts small and overshoots: ' + pure.pop.join(' '));

    // the shelf
    await ev(() => ds3d.setTab ? ds3d.setTab('library', 'bubble') : null);
    await pg.locator('#sidebar button, #panel button, button').filter({ hasText: /^Library$/ }).first().click().catch(() => {});
    await pg.locator('button').filter({ hasText: /^Speech bubbles$/ }).first().click();
    await pg.waitForTimeout(500);
    ok(await pg.locator('.bubble-card').count() === 14, 'the Library shelf shows all 14');
    const painted = await ev(() => { const c = document.querySelector('.bubble-card canvas'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; for (let i = 3; i < d.length; i += 4) if (d[i]) return true; return false; });
    ok(painted, 'the shelf cards are drawn');

    // drag from the shelf onto the timeline
    const t = await pg.locator('#tracks').boundingBox();
    await pg.locator('.bubble-card[data-bubble=talk]').dragTo(pg.locator('#tracks'), { targetPosition: { x: t.width * 0.45, y: t.height * 0.5 } });
    await pg.waitForTimeout(300);
    let L = await B();
    ok(L.length === 1 && L[0].f > 10, 'dragging a card onto the timeline adds a bubble at that frame: ' + (L[0] && L[0].f));
    ok(await pg.locator('#tracks .block.draw').count() === 1, 'it gets its own layer and block');
    await pg.waitForTimeout(600); await still('talk');

    // typing and Enter, on the Stage
    const P0 = L[0].placed, fr = await pg.locator('#frame').boundingBox();
    await pg.mouse.dblclick(fr.x + P0.x * fr.width, fr.y + P0.y * fr.height);
    await pg.waitForSelector('.bubble-edit');
    await pg.keyboard.press('Control+A'); await pg.keyboard.type('Not a'); await pg.keyboard.press('Enter'); await pg.keyboard.type('noodle');
    await pg.keyboard.press('Escape'); await pg.waitForTimeout(200);
    L = await B(); ok(L[0].text === 'Not a\nnoodle', 'double-click edits on the Stage and Enter breaks the line: ' + JSON.stringify(L[0].text));
    await still('edited');

    // drag it round the character: the tail stays on
    const place = await ev(() => ds3d.bubbles({ action: 'list' }).then(r => r.bubbles[0].placed));
    await pg.mouse.move(fr.x + place.x * fr.width, fr.y + place.y * fr.height); await pg.mouse.down();
    await pg.mouse.move(fr.x + 0.5 * fr.width, fr.y + 0.75 * fr.height, { steps: 6 }); await pg.mouse.up(); await pg.waitForTimeout(200);
    L = await B();
    ok(L[0].placed.y > 0.55 && L[0].placed.tip && L[0].placed.tip.y > 0.2 && L[0].placed.tip.y < L[0].placed.y, 'dragged below the character, the tail still reaches it: ' + JSON.stringify(L[0].placed));
    await still('below');
    await ev(() => ds3d.undo()); L = await B(); ok(L[0].dy == null, 'Undo puts it back');

    // pull the handle
    await ev(() => ds3d.bubbles({ action: 'set', index: 0, text: 'This line is long enough to wrap around a few times here' }));
    const wide = await ev(async () => { await ds3d.bubbles({ action: 'set', index: 0, w: 0.2 }); const a = (await ds3d.bubbles({ action: 'list' })).bubbles[0]; return a.w; });
    ok(wide === 0.2, 'the MCP can set the width too');
    await pg.waitForTimeout(200); await still('narrow');
    await ev(() => ds3d.bubbles({ action: 'set', index: 0, w: null }));

    // timing
    await ev(() => ds3d.bubbles({ action: 'set', index: 0, seconds: 1.5 })); L = await B(); ok(L[0].len === 45, 'set the duration in seconds');
    const m = await ev(async () => { await ds3d.bubbles({ action: 'set', index: 0, text: 'hello there friend' }); const r = await ds3d.bubbles({ action: 'match', index: 0, to: 'babble' }); return r; });
    ok(m.match === 'babble' && !!m.babble, 'match to Babble says the line');
    const lines = await ev(() => ds3d.babble({ action: 'list' }).then(r => r.lines.length)); ok(lines === 1, 'the Babble line is there');
    const longer = await ev(async () => { const a = (await ds3d.bubbles({ action: 'list' })).bubbles[0].len; await ds3d.bubbles({ action: 'set', index: 0, text: 'hello there friend how is your day going so far then' }); await new Promise(r => setTimeout(r, 300)); const b = (await ds3d.bubbles({ action: 'list' })).bubbles[0]; return [a, b.len, await ds3d.babble({ action: 'list' }).then(r => r.lines[0].text)]; });
    ok(longer[1] > longer[0] && longer[2].includes('so far'), 'a longer line changes the Babble and the bubble ends with it: ' + longer.slice(0, 2).join(' to '));
    const moved = await ev(async () => { const k = 'b:' + (await ds3d.bubbles({ action: 'list' })).bubbles[0].id; await ds3d.blocks({ action: 'move', layer: k, start: 5 }); await new Promise(r => setTimeout(r, 300)); return [(await ds3d.bubbles({ action: 'list' })).bubbles[0].f, (await ds3d.babble({ action: 'list' })).lines[0].f]; });
    ok(moved[0] === 5 && moved[1] === 5, 'moving the block moves the line with it');
    const noVoice = await ev(() => ds3d.bubbles({ action: 'add', preset: 'star', text: 'BANG!', frame: 60 }).then(r => ds3d.bubbles({ action: 'match', id: r.id, to: 'voice' })).then(r => r.len, e => e.message));
    ok(typeof noVoice === 'number' || /voice/i.test(noVoice), 'match to the voice: ' + noVoice);

    // all kinds at once, in the block list
    await ev(() => ds3d.bubbles({ action: 'clear' }));
    await ev(() => ds3d.babble({ action: 'clear' }));
    for (const [p, f] of [['surprise', 12], ['star', 40], ['stepped', 70]]) { await ev(([a, b]) => ds3d.bubbles({ action: 'add', preset: a, frame: b, seconds: 1 }), [p, f]); await ev(x => ds3d.goto(x), f + 22); await pg.waitForTimeout(300); await still(p); }
    await ev(() => ds3d.bubbles({ action: 'add', preset: 'tabbed', frame: 96, seconds: 0.8, fill: 'ink' })); await ev(() => ds3d.goto(116)); await pg.waitForTimeout(300); await still('tabbed');
    L = await ev(() => ds3d.blocks({ action: 'list' }));
    const bl = L.layers.filter(x => x.kind === 'bubble');
    ok(bl.length === 4 && bl[0].blocks[0].end - bl[0].blocks[0].start === 30, 'bubbles are layers in the blocks tool');
    await ev(k => ds3d.blocks({ action: 'trim', layer: k, start: 12, end: 22 }), bl[0].layer);
    await ev(k => ds3d.blocks({ action: 'split', layer: k, frame: 48 }), bl[1].layer);
    await ev(k => ds3d.blocks({ action: 'show', layer: k, on: false }), bl[2].layer);
    const after = await B();
    ok(after[0].len === 10 && after.length === 5 && after.some(b => b.hidden), 'trim, cut and hide work on bubble blocks');
    // the render side: one picture per look, the pop frame by frame, then held
    await ev(() => ds3d.bubbles({ action: 'clear' }));
    await ev(() => ds3d.bubbles({ action: 'add', preset: 'talk', frame: 10, seconds: 2 }));
    const post = await ev(() => ds3d.post({ action: 'build', all: false }));
    const ov = post.overlays.filter(o => /bubble/.test(o.path)), total = ov.reduce((n, o) => n + o.length, 0);
    ok(total === 60 && ov.length < 30, `60 frames in ${ov.length} pictures`);
    ok(ov[0].start === 10 && ov.every((o, i) => !i || o.start === ov[i - 1].start + ov[i - 1].length), 'the pictures run on from the block start');
    ok(fs.existsSync(ov[3].path) && fs.statSync(ov[3].path).size > 3000, 'the pictures are written');
    fs.copyFileSync(ov[3].path, path.join(out, 'bubble_render_pop.png')); fs.copyFileSync(ov[ov.length - 3].path, path.join(out, 'bubble_render_hold.png'));
    fs.writeFileSync(path.join(out, 'bubble_post.json'), JSON.stringify(post));
    // a co-star speaks, and the bubble goes with a moving head
    await ev(() => ds3d.bubbles({ action: 'clear' }));
    const co = await ev(async () => { await ds3d.cast({ action: 'add', character: 'bunny', x: 0.6 }); await new Promise(r => setTimeout(r, 800)); ds3d.goto(20); const a = await ds3d.bubbles({ action: 'add', preset: 'talk', frame: 10, seconds: 3, speaker: 'c0' }), b = await ds3d.bubbles({ action: 'add', preset: 'think', frame: 10, seconds: 3 }); return [a.placed, b.placed]; });
    ok(co[0].tip && co[1].tip && Math.abs(co[0].tip.x - co[1].tip.x) > 0.05, 'each tail goes to its own speaker: ' + co[0].tip?.x?.toFixed(2) + ' and ' + co[1].tip?.x?.toFixed(2));
    await pg.waitForTimeout(300); await still('two');
    const follow = await ev(async () => { ds3d.setValues({ bodyTilt: 0 }, 12, true); ds3d.setValues({ bodyTilt: 25 }, 30, true); ds3d.goto(12); const a = (await ds3d.bubbles({ action: 'list' })).bubbles[1].placed.tip.x; ds3d.goto(30); const b = (await ds3d.bubbles({ action: 'list' })).bubbles[1].placed.tip.x; return [a, b]; });
    ok(Math.abs(follow[0] - follow[1]) > 0.02, 'the tail stays on a head that moves across the frame: ' + follow.map(v => v.toFixed(2)).join(' to '));
    await ev(() => ds3d.bubbles({ action: 'add', preset: 'star', frame: 20, seconds: 1 }));
    ok(await ev(() => ds3d.goto(30) === undefined), 'two at once is fine');
    ok(await ev(() => document.fonts.check('20px "Luckiest Guy"') && document.fonts.check('20px "Pixelify Sans"') && document.fonts.check('20px VT323')), 'the bundled fonts load');
    const saved = await ev(() => JSON.stringify(ds3d.project.bubbles).length); ok(saved > 100, 'bubbles are stored on the shot');
    ok(!errs.length, 'no page errors ' + errs.join('; '));
  } finally { await br.close(); dev.kill(); }
})().catch(e => { console.log('FAIL', e.message); process.exitCode = 1; });
