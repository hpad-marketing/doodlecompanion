// UX pass: every tab and sub-tab at a laptop size and a full-HD size, with a park scene in Dusk
// shadows, Classic light. Reports text cut off, controls off their panel, and the same button twice
// in one panel, and keeps a screenshot of each. Run: node tools/ux_pass.cjs <folder>
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54394, dir = process.argv[2] || 'devout/ux';
fs.mkdirSync(dir, { recursive: true });
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
(async () => {
  await new Promise(r => setTimeout(r, 900));
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  for (const [w, h] of [[1366, 768], [1920, 1032]]) {
    const p = await (await b.newContext({ viewport: { width: w, height: h } })).newPage();
    const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error' && !/404|Failed to load/.test(m.text())) errs.push(m.text()); });
    p.on('dialog', d => d.accept());
    await p.goto(`http://127.0.0.1:${port}/`);
    await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 90000 });
    const call = (fn, ...a) => p.evaluate(([f, x]) => window.ds3d[f](...x), [fn, a]);
    await call('setStage', { set: 'park' }, false);
    await call('materials', { action: 'apply', target: 'scene', look: 'ink-mustard', palette: 'dusk' });
    await call('lighting', { shadows: true, preset: 'classic' });
    await new Promise(r => setTimeout(r, 2500));
    const tabs = await p.evaluate(() => [...document.querySelectorAll('#tabs button')].map(x => x.textContent));
    for (const t of tabs) {
      await p.click(`#tabs button:text-is("${t}")`);
      await new Promise(r => setTimeout(r, 450));
      const subs = await p.evaluate(() => [...document.querySelectorAll('.subtabs button, #subtabs button, .chips[role=tablist] button')].map(x => x.textContent.trim()).filter(Boolean).slice(0, 8));
      for (const s of subs.length ? subs : ['']) {
        if (s) { await p.locator(`.subtabs button, #subtabs button`, { hasText: s }).first().click({ timeout: 1500 }).catch(() => {}); await new Promise(r => setTimeout(r, 300)); }
        const name = `${w}-${t}${s ? '-' + s : ''}`.replace(/[^\w-]+/g, '_');
        await p.screenshot({ path: path.join(dir, name + '.png') });
        const rep = await p.evaluate(() => {
          const out = [], seen = new Map(), vw = innerWidth;
          for (const e of document.querySelectorAll('#tools-panel button, #panel button, .ws button, button, label, h3, select, input[type=range]')) {
            const r = e.getBoundingClientRect();
            if (!r.width || !r.height || getComputedStyle(e).visibility === 'hidden') continue;
            const t = (e.textContent || '').trim().slice(0, 40);
            if (r.right > vw + 1) out.push('off screen: ' + t);
            if (e.tagName === 'BUTTON' && e.scrollWidth > e.clientWidth + 2) out.push('cut off: ' + t);
            if (e.tagName === 'BUTTON' && t.length > 2) { const k = t; seen.set(k, (seen.get(k) || 0) + 1); }
          }
          for (const [k, n] of seen) if (n > 1) out.push(`twice (${n}): ${k}`);
          return [...new Set(out)];
        });
        if (rep.length) console.log(name, JSON.stringify(rep.slice(0, 14)));
      }
    }
    console.log(w + ' errors:', JSON.stringify(errs.slice(0, 5)));
    await p.context().close();
  }
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e.message); dev.kill(); process.exit(1); });
