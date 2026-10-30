// Background renders in Blender. One job at a time; each job writes its shot,
// log, rule report and video into DeepInDoodles\<Name>\work\, never the top level
// (only the approved final goes there).
const fs = require('node:fs'), path = require('node:path'), { spawn } = require('node:child_process');

const BLENDER_GUESSES = [
  'C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe',
  'C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe',
  'C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe',
];

module.exports = ({ appDir, settings, notify }) => {
  let job = null;
  const queue = [];
  const blender = () => [settings.get().blender, ...BLENDER_GUESSES].find(p => p && fs.existsSync(p));
  const safe = n => String(n || 'Untitled shot').replace(/[<>:"/\\|?*\x00-\x1f]/g, '').trim() || 'Untitled shot';

  function folders(name) {
    const root = path.join(settings.get().rendersRoot, safe(name));
    const work = path.join(root, 'work');
    fs.mkdirSync(work, { recursive: true });
    return { root, work };
  }

  function nextVersion(dir, base) {
    let v = 1;
    while (fs.existsSync(path.join(dir, `${base}_v${String(v).padStart(3, '0')}.mp4`)) || fs.existsSync(path.join(dir, `${base}_v${String(v).padStart(3, '0')}`))) v++;
    return `${base}_v${String(v).padStart(3, '0')}`;
  }

  function start(req) {
    const exe = blender();
    if (!exe) throw Error('Blender 4.5 was not found. Set its path in Render › Blender location.');
    const { work } = folders(req.name);
    const base = safe(req.name).replace(/\s+/g, '_');
    const tag = nextVersion(path.join(work, 'renders'), base);
    const out = path.join(work, 'renders', tag);
    fs.mkdirSync(out, { recursive: true });
    const shotFile = path.join(out, 'shot.json');
    fs.writeFileSync(shotFile, JSON.stringify(req.shot));
    const args = ['-b', path.join(appDir, 'blender', 'Bunny3D_v2.blend'), '--python', path.join(appDir, 'blender', 'ds_bridge.py'), '--', shotFile, out, '--check'];
    let video = null;
    if (req.still) args.push('--still', String(req.still));
    else { video = path.join(work, 'renders', tag + '.mp4'); args.push('--video', video); }
    if (req.preview) args.push('--scale', '50', '--no-cloth');
    if (req.audio && fs.existsSync(req.audio)) args.push('--audio', req.audio);
    const j = { id: tag, name: req.name, out, video, still: req.still, frames: req.shot.frames.length, frame: 0, state: 'rendering', rules: null, started: Date.now(), log: path.join(out, 'blender.log') };
    const log = fs.createWriteStream(j.log);
    const p = spawn(exe, args, { windowsHide: true });
    j.proc = p;
    const onData = d => {
      const s = d.toString();
      log.write(s);
      for (const m of s.matchAll(/Fra:(\d+)/g)) j.frame = Math.max(j.frame, Number(m[1]));
      const r = s.match(/RULES (PASS|FAIL[^\n]*)/);
      if (r) j.rules = r[1].trim();
    };
    p.stdout.on('data', onData);
    p.stderr.on('data', onData);
    p.on('close', code => {
      log.end();
      j.proc = null;
      j.ended = Date.now();
      j.state = j.state === 'cancelled' ? 'cancelled' : (code === 0 ? 'done' : (j.rules && j.rules.startsWith('FAIL') ? 'rules failed' : 'failed'));
      try { j.report = JSON.parse(fs.readFileSync(path.join(out, 'rules.json'), 'utf8')); } catch {}
      notify(j);
      job = null;
      if (queue.length) start(queue.shift());
    });
    job = j;
    return j;
  }

  return {
    folders,
    render(req) {
      if (job) { queue.push(req); return { message: `Queued behind ${job.id} (${queue.length} waiting)` }; }
      const j = start(req);
      return { message: `Rendering ${j.id} in Blender…`, id: j.id };
    },
    status() {
      if (!job) return { state: 'idle', queued: queue.length };
      const el = (Date.now() - job.started) / 1000;
      const eta = job.frame > 2 ? Math.round(el / job.frame * (job.frames - job.frame)) : null;
      return { state: job.state, id: job.id, frame: job.frame, frames: job.frames, eta, queued: queue.length };
    },
    cancel() {
      if (!job || !job.proc) return { message: 'Nothing is rendering' };
      job.state = 'cancelled';
      job.proc.kill();
      return { message: 'Render cancelled' };
    },
    blender,
  };
};
