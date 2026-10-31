// Open in Blender: the active shot in a full Blender window, live-linked both ways.
// The app and Blender never talk directly; both long-poll this host (127.0.0.1 only):
//   app     -> mirror-open, mirror-send (frame, pose, shot), mirror-wait (Blender's messages), mirror-close
//   Blender -> mirror-pull (the app's messages), mirror-push (hello, frame, edit, rebuilt)
// Blender's calls carry a random token. A shot message whose props, set or character changed
// becomes a rebuild (Blender reopens the clean file and builds the shot again); anything else
// only rewrites keys and placement, which takes a fraction of a second.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), { spawn } = require('node:child_process');

module.exports = ({ appDir, port, blender, blendFor, folders, withMaster, env = () => ({}), spawnBlender = null }) => {
  let link = null;   // { token, proc, code, name, sig, toBlender: [], seq, blenderWait, fromBlender: [], appWait, hello, closed }
  const waitFor = (holder, key, ms) => new Promise(ok => { const t = setTimeout(() => { holder[key] = null; ok(); }, ms); holder[key] = () => { clearTimeout(t); holder[key] = null; ok(); }; });
  const wake = (holder, key) => holder && holder[key] && holder[key]();

  // what needs Blender to build the shot again (vs. only new keys and placement)
  function structure(shot) {
    const st = { ...(shot.stage || {}) }; delete st.pieces; delete st.sun;
    const items = (shot.items || []).map(i => { const { at, rot, scale, ...rest } = i; return rest; });
    return JSON.stringify([shot.character || 'bunny', st, items, shot.costars || null, shot.powers || null, shot.rules || null, shot.materials || null]);
  }

  function toBlender(msg) {
    if (!link || link.closed) return;
    // only the newest frame, pose and shot matter: older ones still queued are dropped
    if (['frame', 'pose', 'shot'].includes(msg.t)) link.toBlender = link.toBlender.filter(m => m.t !== msg.t && !(msg.t === 'shot' && m.t === 'pose'));
    if (msg.t === 'rebuild') link.toBlender = link.toBlender.filter(m => !['shot', 'rebuild', 'pose'].includes(m.t));
    msg.seq = ++link.seq;
    link.toBlender.push(msg);
    wake(link, 'blenderWait');
  }
  function toApp(msg) {
    if (!link) return;
    if (msg.t === 'frame') link.fromBlender = link.fromBlender.filter(m => m.t !== 'frame');
    link.fromBlender.push(msg);
    if (link.fromBlender.length > 500) link.fromBlender.splice(0, link.fromBlender.length - 500);
    wake(link, 'appWait');
  }
  const status = () => (link ? { open: !link.closed, connected: !!link.hello && !link.closed, blender: link.hello?.blender || null, shot: link.code, name: link.name, file: link.liveBlend, pid: link.proc?.pid || null } : { open: false, connected: false });

  function writeShot(dir, shot) {
    const f = path.join(dir, 'shot.json');
    fs.writeFileSync(f, JSON.stringify(withMaster(shot)));
    return f;
  }

  const api = {
    'mirror-status': () => status(),
    async 'mirror-open'({ shot, name, code, frame = 0 }) {
      if (!shot?.frames?.length) throw Error('This shot has no frames');
      // the same shot already open: bring it up to date instead of a second window
      if (link && !link.closed && link.name === name && link.code === code) { api['mirror-send']({ msg: { t: 'shot', shot, f: frame } }); return { ...status(), reused: true }; }
      if (link && !link.closed) api['mirror-close']({ quiet: true });
      const exe = blender();
      if (!exe) throw Error('Blender was not found. Set its path in Render › Blender location.');
      const blend = blendFor(shot);
      const tag = `${String(name || 'scene').replace(/[<>:"/\\|?*\x00-\x1f]/g, '').trim().replace(/\s+/g, '_') || 'scene'}${code ? '_' + code : ''}`;
      const dir = path.join(folders(name).work, 'blender-live', tag);
      fs.mkdirSync(dir, { recursive: true });
      const shotFile = writeShot(dir, shot);
      const liveBlend = path.join(dir, tag + '_live.blend');
      const token = crypto.randomBytes(16).toString('hex');
      link = { token, code, name, sig: structure(shot), toBlender: [], seq: 0, fromBlender: [], blenderWait: null, appWait: null, hello: null, closed: false, liveBlend, dir, shotFile };
      const args = [blend, '--python', path.join(appDir, 'blender', 'ds_bridge.py'), '--', shotFile, dir, '--live', `http://127.0.0.1:${port}`, token, '--frame', String(frame | 0), '--save-live', liveBlend];
      const log = fs.openSync(path.join(dir, 'blender.log'), 'w');
      const me = link;
      const p = (spawnBlender || spawn)(exe, args, { detached: true, stdio: ['ignore', log, log], env: { ...process.env, ...env() } });
      link.proc = p;
      p.on('exit', code => { try { fs.closeSync(log); } catch {} if (link === me) { me.closed = true; toApp({ t: 'closed', code }); wake(me, 'blenderWait'); } });
      p.on('error', e => { if (link === me) { me.closed = true; toApp({ t: 'closed', error: String(e.message || e) }); } });
      p.unref?.();
      return status();
    },
    // the app's side: frame, pose (shown at once), shot (keys and placement), bye
    'mirror-send'({ msg }) {
      if (!link || link.closed || !msg?.t) return status();
      if (msg.t === 'shot') {
        const sig = structure(msg.shot);
        if (sig !== link.sig || (msg.code && msg.code !== link.code)) {
          link.sig = sig; if (msg.code) link.code = msg.code;
          writeShot(link.dir, msg.shot);
          return toBlender({ ...msg, shot: withMaster(msg.shot), t: 'rebuild' }), { ...status(), rebuild: true };
        }
      }
      toBlender(msg);
      return status();
    },
    // the app waits here for what changed in Blender
    async 'mirror-wait'({ since = 0, ms = 20000 } = {}) {
      if (!link) return { msgs: [], ...status() };
      const me = link;
      if (!me.fromBlender.length && !me.closed) await waitFor(me, 'appWait', Math.min(25000, ms));
      const msgs = me.fromBlender.splice(0);
      return { msgs, ...status() };
    },
    'mirror-close'({ quiet } = {}) {
      if (!link) return status();
      const me = link;
      if (!me.closed) { toBlender({ t: 'bye' }); me.closed = true; }
      if (!quiet) toApp({ t: 'closed', by: 'app' });
      return status();
    },
    // Blender's side
    async 'mirror-pull'({ token, since = 0 }) {
      const me = link;
      if (!me || token !== me.token) return { closed: true };
      const fresh = () => me.toBlender.filter(m => m.seq > since);
      if (!fresh().length && !me.closed) await waitFor(me, 'blenderWait', 20000);
      const msgs = fresh();
      me.toBlender = me.toBlender.filter(m => m.seq > since);
      if (me.closed && !msgs.length) return { closed: true };
      return { msgs };
    },
    'mirror-push'({ token, msgs }) {
      if (!link || token !== link.token) return { closed: true };
      for (const m of msgs || []) {
        if (m.t === 'hello') link.hello = m;
        toApp(m);
      }
      return { ok: true };
    },
  };
  return { api, status, structure };
};
