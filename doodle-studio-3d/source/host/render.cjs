// Background renders in Blender, one job at a time. Everything lands in
// DeepInDoodles\<Scene>\work\, never the top level (only the approved final goes there):
//   work\renders\<Scene>_sh020_v002.mp4   one shot
//   work\renders\<Scene>_v003.mp4         the whole scene, shots joined in order
//   work\checks\<render name>\             shot data, Blender log, rule report
// A scene render reuses any shot whose content hasn't changed since its last render.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), { spawn } = require('node:child_process');

const BLENDER_GUESSES = [
  'C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe',
  'C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe',
  'C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe',
];

module.exports = ({ appDir, settings, notify }) => {
  let job = null;
  const queue = [];
  const blender = () => [settings.get().blender, ...BLENDER_GUESSES].find(p => p && fs.existsSync(p));
  const safe = n => String(n || 'Untitled scene').replace(/[<>:"/\\|?*\x00-\x1f]/g, '').trim() || 'Untitled scene';
  const base = name => safe(name).replace(/\s+/g, '_');

  function folders(name) {
    const root = path.join(settings.get().rendersRoot, safe(name));
    const work = path.join(root, 'work');
    for (const d of ['renders', 'checks']) fs.mkdirSync(path.join(work, d), { recursive: true });
    return { root, work, renders: path.join(work, 'renders'), checks: path.join(work, 'checks') };
  }

  function nextVersion(dir, stem) {
    let v = 1;
    const tag = () => `${stem}_v${String(v).padStart(3, '0')}`;
    while (fs.existsSync(path.join(dir, tag() + '.mp4')) || fs.existsSync(path.join(dir, tag() + '.png'))) v++;
    return tag();
  }

  // shots whose content is unchanged since their last render are reused
  const cacheFile = f => path.join(f.renders, '.shot-cache.json');
  const readCache = f => { try { return JSON.parse(fs.readFileSync(cacheFile(f), 'utf8')); } catch { return {}; } };
  const shotHash = (s, preview) => crypto.createHash('sha256').update(JSON.stringify([s.shot, s.audio || null, !!preview, fs.statSync(path.join(appDir, 'blender', 'Bunny3D_v2.blend')).mtimeMs])).digest('hex').slice(0, 16);

  // one Blender run; resolves with the step's result
  function runBlender(j, args, logFile) {
    return new Promise(resolve => {
      const exe = blender();
      if (!exe) return resolve({ code: -1, error: 'Blender was not found. Set its path in Render › Blender location.' });
      const log = fs.createWriteStream(logFile);
      const p = spawn(exe, args, { windowsHide: true });
      j.proc = p;
      let rules = null;
      const onData = d => {
        const s = d.toString();
        log.write(s);
        for (const m of s.matchAll(/Fra:(\d+)/g)) j.frame = Math.max(j.frame, j.frameBase + Number(m[1]));
        const r = s.match(/RULES (PASS|FAIL[^\n]*)/);
        if (r) rules = r[1].trim();
      };
      p.stdout.on('data', onData);
      p.stderr.on('data', onData);
      p.on('error', e => { log.end(); resolve({ code: -1, error: String(e.message || e) }); });
      p.on('close', code => { log.end(); j.proc = null; resolve({ code, rules }); });
    });
  }

  async function renderShot(j, f, s, opts) {
    const tag = nextVersion(f.renders, `${base(j.name)}${s.code ? '_' + s.code : ''}`);
    const check = path.join(f.checks, tag);
    fs.mkdirSync(check, { recursive: true });
    const shotFile = path.join(check, 'shot.json');
    fs.writeFileSync(shotFile, JSON.stringify(s.shot));
    const args = ['-b', path.join(appDir, 'blender', 'Bunny3D_v2.blend'), '--python', path.join(appDir, 'blender', 'ds_bridge.py'), '--', shotFile, check, '--check'];
    let out = null;
    if (opts.still) args.push('--still', String(opts.still));
    else { out = path.join(f.renders, tag + '.mp4'); args.push('--video', out); }
    if (opts.preview) args.push('--scale', '50', '--no-cloth');
    if (s.audio && fs.existsSync(s.audio)) args.push('--audio', s.audio);
    j.step = s.code ? `${s.code}` : tag;
    const r = await runBlender(j, args, path.join(check, 'blender.log'));
    if (opts.still && r.code === 0) {
      const png = path.join(f.renders, tag + '.png');
      try { fs.copyFileSync(path.join(check, 'still.png'), png); out = png; } catch {}
    }
    let report = null;
    try { report = JSON.parse(fs.readFileSync(path.join(check, 'rules.json'), 'utf8')); } catch {}
    return { ...r, tag, out, check, report };
  }

  async function runJob(j) {
    const f = folders(j.name);
    const shots = j.req.shots;
    const cache = readCache(f);
    const done = [];
    let failed = null;
    for (const s of shots) {
      if (j.state === 'cancelled') break;
      const hash = shotHash(s, j.req.preview);
      const hit = !j.req.still && cache[hash] && fs.existsSync(cache[hash]) ? cache[hash] : null;
      if (hit && j.scene) { done.push({ code: s.code, out: hit, reused: true, rules: 'PASS' }); j.frameBase += s.shot.frames.length; j.frame = j.frameBase; continue; }
      const r = await renderShot(j, f, s, { still: j.req.still, preview: j.req.preview });
      j.frameBase += s.shot.frames.length; j.frame = j.frameBase;
      done.push({ code: s.code, out: r.out, rules: r.rules, check: r.check });
      if (r.code !== 0) { failed = { code: s.code, rules: r.rules, error: r.error, check: r.check }; break; }
      if (r.out && !j.req.still) { cache[hash] = r.out; fs.writeFileSync(cacheFile(f), JSON.stringify(cache, null, 1)); }
    }
    j.shots = done;
    if (j.state === 'cancelled') return;
    if (failed) {
      j.state = failed.rules && failed.rules.startsWith('FAIL') ? 'rules failed' : 'failed';
      j.rules = failed.rules || null;
      j.out = failed.check;
      j.detail = `${failed.code || 'shot'}: ${failed.error || failed.rules || 'see blender.log'}`;
      return;
    }
    j.rules = done.every(d => !d.rules || d.rules === 'PASS') ? 'PASS' : done.map(d => d.rules).find(r => r && r !== 'PASS');
    if (!j.scene) { j.state = 'done'; j.video = done[0]?.out; j.id = path.basename(done[0]?.out || j.id); return; }
    // join the shots in order
    const tag = nextVersion(f.renders, base(j.name));
    const out = path.join(f.renders, tag + '.mp4');
    const check = path.join(f.checks, tag);
    fs.mkdirSync(check, { recursive: true });
    fs.writeFileSync(path.join(check, 'scene.json'), JSON.stringify({ shots: done, audio: j.req.audio || null }, null, 1));
    j.step = 'joining shots';
    const k = j.req.preview ? 0.5 : 1;   // quick previews render at half size
    const args = ['-b', '--factory-startup', '--python', path.join(appDir, 'blender', 'ds_concat.py'), '--', out, String(j.req.fps), String(Math.round(j.req.width * k)), String(Math.round(j.req.height * k))];
    if (j.req.audio && fs.existsSync(j.req.audio)) args.push('--audio', j.req.audio);
    args.push('--', ...done.map(d => d.out));
    j.frameBase = 0;
    const r = await runBlender(j, args, path.join(check, 'blender.log'));
    j.id = tag;
    j.out = check;
    if (r.code !== 0) { j.state = 'failed'; j.detail = 'Joining the shots failed: see blender.log'; return; }
    j.video = out;
    j.state = 'done';
  }

  // carousel: full-quality stills, one Blender run per shot (physics still run over the
  // whole shot), copied to work\carousel\<Scene>_carousel_v###\<Scene>_carousel_01.png ...
  async function runCarousel(j) {
    const f = folders(j.name);
    const dir = path.join(f.work, 'carousel');
    fs.mkdirSync(dir, { recursive: true });
    let v = 1;
    while (fs.existsSync(path.join(dir, `${base(j.name)}_carousel_v${String(v).padStart(3, '0')}`))) v++;
    const tag = `${base(j.name)}_carousel_v${String(v).padStart(3, '0')}`;
    const out = path.join(dir, tag);
    fs.mkdirSync(out, { recursive: true });
    const groups = new Map();
    j.req.slides.forEach((s, i) => { if (!groups.has(s.code)) groups.set(s.code, { shot: s.shot, items: [] }); groups.get(s.code).items.push({ i, frame: s.frame }); });
    const slides = [];
    for (const [code, g] of groups) {
      if (j.state === 'cancelled') return;
      const check = path.join(f.checks, `${tag}_${code}`);
      fs.mkdirSync(check, { recursive: true });
      const shotFile = path.join(check, 'shot.json');
      fs.writeFileSync(shotFile, JSON.stringify({ ...g.shot, width: j.req.width, height: j.req.height }));
      const frames = [...new Set(g.items.map(x => x.frame + 1))];
      j.step = `${code}: ${frames.length} slide${frames.length > 1 ? 's' : ''}`;
      const args = ['-b', path.join(appDir, 'blender', 'Bunny3D_v2.blend'), '--python', path.join(appDir, 'blender', 'ds_bridge.py'), '--', shotFile, check, '--check', '--frames', frames.join(',')];
      const r = await runBlender(j, args, path.join(check, 'blender.log'));
      if (r.code !== 0 && !(r.rules || '').startsWith('FAIL')) { j.state = 'failed'; j.detail = `${code}: see blender.log`; j.out = check; return; }
      if (r.rules && r.rules !== 'PASS') j.rules = r.rules;
      for (const x of g.items) {
        const src = path.join(check, `still_${String(x.frame + 1).padStart(4, '0')}.png`);
        const dst = path.join(out, `${base(j.name)}_carousel_${String(x.i + 1).padStart(2, '0')}.png`);
        if (fs.existsSync(src)) { fs.copyFileSync(src, dst); slides[x.i] = dst; }
      }
      j.frame = slides.filter(Boolean).length;
    }
    j.slides = slides;
    j.out = out;
    j.id = tag;
    j.rules = j.rules || 'PASS';
    j.state = slides.filter(Boolean).length === j.req.slides.length ? 'done' : 'failed';
    if (j.state === 'failed') j.detail = 'Some slides did not render: see work\\checks';
  }

  function start(req, scene) {
    if (!blender()) throw Error('Blender was not found. Set its path in Render › Blender location.');
    if (scene === 'carousel') {
      const j = { id: `${base(req.name)} carousel`, name: req.name, req, scene, frames: req.slides.length, frame: 0, frameBase: -1e9, state: 'rendering', rules: null, started: Date.now(), shots: [] };
      job = j;
      runCarousel(j).catch(e => { j.state = 'failed'; j.detail = String(e && e.message || e); }).finally(() => {
        j.ended = Date.now(); notify(j); job = null;
        if (queue.length) { const [r, s] = queue.shift(); try { start(r, s); } catch {} }
      });
      return j;
    }
    const shots = req.shots;
    const j = { id: scene ? `${base(req.name)} scene` : `${base(req.name)}_${shots[0].code || 'shot'}`, name: req.name, req, scene, frames: shots.reduce((n, s) => n + (req.still ? 1 : s.shot.frames.length), 0),
      frame: 0, frameBase: 0, state: 'rendering', rules: null, started: Date.now(), shots: [] };
    job = j;
    runJob(j).catch(e => { j.state = 'failed'; j.detail = String(e && e.message || e); }).finally(() => {
      j.ended = Date.now();
      notify(j);
      job = null;
      if (queue.length) { const [r, s] = queue.shift(); try { start(r, s); } catch {} }
    });
    return j;
  }

  function enqueue(req, scene) {
    if (job) { queue.push([req, scene]); return { message: `Queued behind ${job.id} (${queue.length} waiting)` }; }
    const j = start(req, scene);
    if (scene === 'carousel') return { message: `Rendering ${req.slides.length} carousel slides in Blender…`, id: j.id };
    return { message: scene ? `Rendering ${req.shots.length} shots of ${safe(req.name)} in Blender…` : `Rendering ${j.id} in Blender…`, id: j.id };
  }

  // ---- Blender versions: a new Blender is used only after it renders a test frame
  const ROOT = 'C:\\Program Files\\Blender Foundation';
  function findBlenders() {
    const found = [];
    try {
      for (const d of fs.readdirSync(ROOT)) {
        const exe = path.join(ROOT, d, 'blender.exe');
        const m = d.match(/(\d+)\.(\d+)/);
        if (fs.existsSync(exe)) found.push({ path: exe, version: m ? `${m[1]}.${m[2]}` : d });
      }
    } catch {}
    const custom = settings.get().blender;
    if (custom && fs.existsSync(custom) && !found.some(f => f.path === custom)) found.push({ path: custom, version: '?' });
    const verified = settings.get().blenderVerified || {};
    return found.map(f => ({ ...f, verified: verified[f.path] || null, inUse: f.path === blender() }))
      .sort((a, b) => parseFloat(b.version) - parseFloat(a.version));
  }

  function verify(exe, dataDir) {
    return new Promise(resolve => {
      const dir = path.join(dataDir, 'blender-check', String(Date.now()));
      fs.mkdirSync(dir, { recursive: true });
      const shot = { fps: 30, width: 270, height: 480, frames: [0, 1, 2].map(i => ({ armL: 40 + i * 20, headYaw: i * 10, earLFold: -i * 10, expression: 1, cam: { yaw: 0, pitch: 4, dist: 3, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.52 } })) };
      const shotFile = path.join(dir, 'shot.json');
      fs.writeFileSync(shotFile, JSON.stringify(shot));
      const args = ['-b', path.join(appDir, 'blender', 'Bunny3D_v2.blend'), '--python', path.join(appDir, 'blender', 'ds_bridge.py'), '--', shotFile, dir, '--check', '--still', '2', '--no-cloth'];
      let log = '', version = null;
      let p;
      try { p = spawn(exe, args, { windowsHide: true }); } catch (e) { return resolve({ ok: false, error: String(e.message || e) }); }
      const timer = setTimeout(() => p.kill(), 5 * 60000);
      const onData = d => { log += d.toString(); const m = log.match(/Blender (\d+\.\d+(\.\d+)?)/); if (m) version = m[1]; };
      p.stdout.on('data', onData);
      p.stderr.on('data', onData);
      p.on('error', e => { clearTimeout(timer); resolve({ ok: false, error: String(e.message || e) }); });
      p.on('close', code => {
        clearTimeout(timer);
        fs.writeFileSync(path.join(dir, 'blender.log'), log);
        const still = fs.existsSync(path.join(dir, 'still.png'));
        const rules = (log.match(/RULES (PASS|FAIL[^\n]*)/) || [])[1] || null;
        const tb = log.lastIndexOf('Traceback');
        const ok = code === 0 && still && rules === 'PASS';
        resolve({ ok, version, rules, log: path.join(dir, 'blender.log'), error: ok ? null : (tb >= 0 ? log.slice(tb).split('\n').slice(-3).join(' ').trim() : `exit ${code}${still ? '' : ', no test frame'}`) });
      });
    });
  }

  return {
    folders,
    findBlenders,
    // switch only if the test frame renders and passes the rule check
    async tryBlender(exe, dataDir) {
      if (!exe || !fs.existsSync(exe)) return { ok: false, error: 'That blender.exe was not found' };
      if (job) return { ok: false, error: 'Wait for the current render to finish, then try again' };
      const r = await verify(exe, dataDir);
      const v = settings.get().blenderVerified || {};
      v[exe] = { ok: r.ok, version: r.version, at: new Date().toISOString(), error: r.error };
      const patch = { blenderVerified: v };
      if (r.ok) patch.blender = exe;
      settings.set(patch);
      return { ...r, inUse: blender() };
    },
    // one shot: {name, shot, code, audio, still, preview}
    render(req) { return enqueue({ ...req, shots: [{ code: req.code || '', shot: req.shot, audio: req.audio }] }, false); },
    // a whole scene: {name, fps, width, height, audio, preview, shots: [{code, shot, audio}]}
    // carousel: {name, width, height, slides: [{code, frame, shot}]}
    renderCarousel(req) {
      if (!req.slides || !req.slides.length) throw Error('The carousel has no slides yet');
      return enqueue(req, 'carousel');
    },
    renderScene(req) {
      if (!req.shots || !req.shots.length) throw Error('This scene has no shots');
      return enqueue(req, true);
    },
    status() {
      if (!job) return { state: 'idle', queued: queue.length };
      const el = (Date.now() - job.started) / 1000;
      const eta = job.frame > 2 ? Math.round(el / job.frame * (job.frames - job.frame)) : null;
      return { state: job.state, id: job.id, step: job.step, frame: Math.min(job.frame, job.frames), frames: job.frames, eta, queued: queue.length };
    },
    cancel() {
      if (!job) return { message: 'Nothing is rendering' };
      job.state = 'cancelled';
      if (job.proc) job.proc.kill();
      return { message: 'Render cancelled' };
    },
    blender,
  };
};
