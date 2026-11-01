// Scrubbing the timeline: the playhead lets go on release, nothing selects, audio is heard under
// it, and the voice and music each have a waveform row. Run: node tools/test_scrub.cjs
const { spawn } = require('child_process'), path = require('path'), fs = require('fs');
const { chromium } = require('playwright');
const port = 54395, wav = path.join(__dirname, '..', 'devout', 'scrub.wav');
fs.mkdirSync(path.dirname(wav), { recursive: true });
{ // two seconds of a falling tone
  const n = 88200, b = Buffer.alloc(44 + n * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + n * 2, 4); b.write('WAVEfmt ', 8); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22); b.writeUInt32LE(44100, 24); b.writeUInt32LE(88200, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(n * 2, 40);
  for (let i = 0; i < n; i++) b.writeInt16LE(Math.round(12000 * Math.sin(i * 0.05) * (1 - i / n)), 44 + i * 2);
  fs.writeFileSync(wav, b);
}
const dev = spawn('node', [path.join(__dirname, 'dev.cjs'), String(port)], { stdio: 'ignore' });
const ok = (c, m) => { if (!c) { console.log('FAIL', m); process.exitCode = 1; } else console.log('ok  ', m); };
(async () => {
  await new Promise(r => setTimeout(r, 900));
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1032 } })).newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto(`http://127.0.0.1:${port}/`);
  await p.waitForFunction(() => document.body.dataset.ready === '1', null, { timeout: 90000 });
  await p.evaluate(() => { window._sliced = 0; const st = AudioBufferSourceNode.prototype.start; AudioBufferSourceNode.prototype.start = function (...a) { if (a[2]) window._sliced++; return st.apply(this, a); }; });
  await p.evaluate(f => ds3d.importAudio(f), wav);
  await p.waitForSelector('#tracks .trow.audio canvas.wave', { timeout: 8000 });
  ok(await p.locator('#tracks .trow.audio .tname:has-text("Voice")').count() === 1, 'imported audio has its own waveform row');
  await p.evaluate(f => ds3d.post({ action: 'music', path: f }), wav);
  await p.waitForSelector('#tracks .trow.audio .tname:has-text("Music")', { timeout: 6000 });
  ok(true, 'a music bed gets its own row too');
  await new Promise(r => setTimeout(r, 4500));
  const box = await p.locator('#tracks .ruler .lane').boundingBox(), y = box.y + box.height / 2;
  await p.mouse.move(box.x + 60, y); await p.mouse.down();
  for (let x = 60; x < 400; x += 12) { await p.mouse.move(box.x + x, y); await new Promise(r => setTimeout(r, 20)); }
  ok(await p.evaluate(() => window._sliced) > 3, 'audio is heard while scrubbing: ' + await p.evaluate(() => window._sliced) + ' slices');
  const sel = await p.evaluate(() => getSelection().toString()); ok(sel === '', 'scrubbing selects nothing: ' + JSON.stringify(sel.slice(0, 60)));
  ok(await p.evaluate(() => +document.querySelector('#frame-box').value) > 10, 'the playhead follows the drag');
  await p.mouse.up();
  const f = await p.evaluate(() => +document.querySelector('#frame-box').value);
  await p.mouse.move(box.x + 900, y); await new Promise(r => setTimeout(r, 150));
  ok(await p.evaluate(() => +document.querySelector('#frame-box').value) === f, 'the playhead lets go on release');
  await p.mouse.move(box.x + 100, y); await p.mouse.down(); await p.mouse.up();
  const g = await p.evaluate(() => +document.querySelector('#frame-box').value);
  await p.mouse.move(box.x + 700, y); await new Promise(r => setTimeout(r, 150));
  ok(await p.evaluate(() => +document.querySelector('#frame-box').value) === g, 'a plain click on the ruler lets go too');
  await p.screenshot({ path: path.join(__dirname, '..', 'devout', 'scrub.png') });
  ok(!errs.length, 'no page errors ' + errs.slice(0, 3).join(' | '));
  await b.close(); dev.kill();
})().catch(e => { console.log('FAIL', e.message); dev.kill(); process.exit(1); });
