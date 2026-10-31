// Open in Blender: the active shot in a full Blender window, kept in step both ways.
// Here: the button's state, what the app sends (the playhead, the pose being edited, the whole
// shot once it settles) and what it does with Blender's edits (pose and camera values, item and
// set-piece placement, the sun), each burst of Blender edits being one undo step.
let C = null;               // the editor's hooks (main.js)
let on = false, connected = false, info = {};
let lastFrame = null, lastPose = '', lastSig = '', poseTimer = 0, sigTimer = null, waiting = false;
let fromBlender = 0;        // > 0 while applying Blender's edit (nothing is echoed back)
let lastEdit = 0;           // when Blender's last edit came in (one undo step per burst)
const listeners = new Set();

export function init(ctx) { C = ctx; }
export const state = () => ({ on, connected, ...info });
export const onChange = fn => (listeners.add(fn), () => listeners.delete(fn));
const changed = () => { for (const fn of listeners) try { fn(state()); } catch {} };

// the shot as Blender builds it, plus what decides whether the keys alone can follow
function shotMsg() { return { t: 'shot', shot: C.bridge(), code: C.code(), f: C.frame() }; }
function signature() {
  const p = C.project(), s = C.scene();
  return JSON.stringify([s.active, p.code, p.tracks, p.layers || null, p.items || null, C.stage(), p.length, p.fps, p.width, p.height, p.costars || null, p.powers || null, p.idle || null, p.rules || null, p.horizonLock || false, p.ink || 100, C.character()]);
}

export async function open() {
  if (!C) return;
  try {
    const r = await C.api('mirror-open', { shot: C.bridge(), name: C.scene().name, code: C.code(), frame: C.frame() });
    on = true; connected = !!r.connected; info = r;
    lastSig = signature(); lastFrame = C.frame();
    C.toast(r.reused ? 'Blender already has this shot open: brought up to date' : 'Opening the shot in Blender… it stays in step with this window', 4000);
    if (!sigTimer) sigTimer = setInterval(watch, 250);
    listen();
    changed();
  } catch (e) { C.toast(e.message, 6000); }
}

export async function close() {
  if (!on) return;
  try { await C.api('mirror-close', {}); } catch {}
  stop('Live Blender link closed. The Blender window stays open with its own copy.');
}

function stop(msg) {
  on = false; connected = false;
  clearInterval(sigTimer); sigTimer = null;
  if (msg) C.toast(msg, 5000);
  changed();
}

function send(msg) { if (on) C.api('mirror-send', { msg }).then(r => { if (r && r.connected !== connected) { connected = r.connected; changed(); } }).catch(() => {}); }

// every 250 ms: has the shot changed (keys, items, set, length)? then Blender gets all of it
function watch() {
  if (!on || C.playing()) return;
  const sig = signature();
  if (sig === lastSig) return;
  lastSig = sig;
  send(shotMsg());
}

// called at the end of every apply(): the playhead, and the pose and camera being edited
export function onApply(frame, vals, cam) {
  if (!on || fromBlender) return;
  if (frame !== lastFrame) { lastFrame = frame; lastPose = ''; send({ t: 'frame', f: frame }); return; }
  if (C.playing()) return;
  const sig = JSON.stringify([vals, cam]);
  if (sig === lastPose) return;
  const first = !lastPose;
  lastPose = sig;
  if (first) return;
  // at most 30 a second; the shot message that follows keys it in Blender
  const now = performance.now();
  if (now - poseTimer < 33) { clearTimeout(onApply.t); onApply.t = setTimeout(() => { lastPose = ''; C.reapply(); }, 40); return; }
  poseTimer = now;
  send({ t: 'pose', f: frame, values: vals, cam });
}

async function listen() {
  if (waiting) return;
  waiting = true;
  try {
    while (on) {
      let r;
      try { r = await C.api('mirror-wait', { ms: 20000 }); } catch { await new Promise(ok => setTimeout(ok, 1500)); continue; }
      if (!on) break;
      if (r.connected !== connected || r.blender !== info.blender) { connected = r.connected; info = { ...info, ...r }; changed(); }
      for (const m of r.msgs || []) handle(m);
    }
  } finally { waiting = false; }
}

function handle(m) {
  if (m.t === 'hello') { connected = true; info = { ...info, blender: m.blender }; C.toast(`Blender ${m.blender} is live: move, turn or pose things on either side`, 5000); changed(); return; }
  if (m.t === 'closed') return stop(m.by === 'app' ? null : 'Blender was closed: the live link has ended');
  if (m.t === 'rebuilt') return;
  if (m.t === 'frame') {
    if (m.f === C.frame()) return;
    fromBlender++;
    try { lastFrame = m.f; C.goto(m.f); } finally { fromBlender--; }
    lastPose = '';
    return;
  }
  if (m.t === 'edit') applyEdit(m);
}

function applyEdit(m) {
  const now = performance.now();
  const label = m.values ? 'Blender: pose' : m.items ? 'Blender: move item' : m.pieces ? 'Blender: move set piece' : 'Blender: edit';
  if (now - lastEdit > 900) C.pushUndo(label);
  lastEdit = now;
  fromBlender++;
  try {
    if (m.f != null && m.f !== C.frame()) { lastFrame = m.f; C.goto(m.f); }
    if (m.values) for (const [id, v] of Object.entries(m.values)) C.setValue(id, Number(v));
    if (m.items) {
      const items = C.project().items || [];
      for (const [i, xf] of Object.entries(m.items)) {
        const it = items[Number(i)];
        if (!it || it.hold) continue;
        it.at = xf.at; it.rot = xf.rot.some(Boolean) ? xf.rot : undefined; it.scale = xf.scale.every(s => Math.abs(s - 1) < 1e-3) ? undefined : xf.scale;
        if (it.rot === undefined) delete it.rot;
        if (it.scale === undefined) delete it.scale;
      }
    }
    if (m.pieces) for (const [id, xf] of Object.entries(m.pieces)) C.editPiece(id, xf);
    if (m.sun) C.setSun(m.sun);
    C.markDirty();
    C.reapply();
    // the edit came from Blender: the shot Blender gets next carries it, nothing else echoes
    lastPose = '';
  } finally { fromBlender--; }
  C.refresh();
}
