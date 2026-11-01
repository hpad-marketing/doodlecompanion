// Speed and planning: hotkey editor + cheat sheet, saved layouts, viewport pop-out,
// favourites / recents bar, snapping, an fps meter that names the heavy item, shot status,
// reel templates, draw-over review notes, beat markers and splitting the voice by sentence.
import { valueAt, setKey, nextCode, newShotData } from './project.js';

const store = (key, def) => ({
  get() { try { return JSON.parse(localStorage.getItem(key) || 'null') ?? def(); } catch { return def(); } },
  set(v) { try { localStorage.setItem(key, JSON.stringify(v)); } catch {} return v; },
});
const modal = (ctx, title, body) => {
  const { h } = ctx;
  const close = () => box.remove();
  const box = h('div', { class: 'ds-modal', role: 'dialog', 'aria-label': title }, h('div', { class: 'ds-modal-card' }, h('h3', {}, title), ...body(close)));
  box.addEventListener('pointerdown', e => { if (e.target === box) close(); });
  document.body.append(box);
  return { box, close };
};

// ---------------------------------------------------------------- hotkeys
export const keys = store('ds3d.keys', () => ({}));   // combo -> command id ("Edit › Undo")
export function comboOf(e) {
  let k = e.key;
  if (['Control', 'Shift', 'Alt', 'Meta'].includes(k)) return null;
  if (k === ' ') k = 'Space'; else if (k.length === 1) k = k.toUpperCase();
  return [(e.ctrlKey || e.metaKey) && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift', k].filter(Boolean).join('+');
}
export const cmdId = c => `${c.group} › ${c.label}`;
export function hotkeyDialog(ctx) {
  const { h } = ctx, cmds = ctx.commands().filter(c => c.group !== 'Pose' && c.group !== 'Character');
  let map = keys.get();
  return modal(ctx, 'Keyboard shortcuts', close => {
    const list = h('div', { class: 'ds-list hotkeys' });
    const keyOf = c => Object.entries(map).find(([, id]) => id === cmdId(c))?.[0];
    const draw = () => {
      const groups = [...new Set(cmds.map(c => c.group))];
      list.replaceChildren(...groups.flatMap(g => [h('h4', {}, g), ...cmds.filter(c => c.group === g).map(c => {
        const mine = keyOf(c);
        return h('div', { class: 'row' }, h('span', { style: 'flex:1' }, c.label),
          c.key ? h('kbd', { title: 'Built-in shortcut' }, c.key) : null, mine ? h('kbd', { class: 'mine', title: 'Your shortcut' }, mine) : null,
          h('button', { title: 'Press the new key combination next', onclick: e => {
            const b = e.currentTarget; b.textContent = 'Press keys…';
            const grab = ev => {
              ev.preventDefault(); ev.stopPropagation();
              if (ev.key === 'Escape') { removeEventListener('keydown', grab, true); draw(); return; }
              const combo = comboOf(ev);
              if (!combo) return;
              removeEventListener('keydown', grab, true);
              const taken = map[combo] || cmds.find(x => x.key === combo && cmdId(x) !== cmdId(c));
              if (taken && !confirm(`${combo} already runs "${typeof taken === 'string' ? taken : cmdId(taken)}". Use it for "${c.label}" instead?`)) return draw();
              for (const [k, id] of Object.entries(map)) if (id === cmdId(c)) delete map[k];
              map[combo] = cmdId(c);
              draw();
            };
            addEventListener('keydown', grab, true);
          } }, mine ? 'Change' : 'Set'),
          mine ? h('button', { title: 'Remove your shortcut', onclick: () => { delete map[mine]; draw(); } }, '×') : null);
      })]));
    };
    draw();
    return [h('p', { class: 'hint' }, 'Every command with its shortcut: this list is the cheat sheet. Set your own keys; yours win over the built-in ones. Your Keydial sends the same keys as in Doodle Studio.'), list,
      h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: () => { map = {}; draw(); } }, 'Clear my shortcuts'), h('span', { style: 'flex:1' }),
        h('button', { class: 'primary', onclick: () => { keys.set(map); close(); ctx.toast('Shortcuts saved'); } }, 'Save'), h('button', { onclick: close }, 'Cancel'))];
  });
}

// ---------------------------------------------------------------- layouts (panel width, timeline height, tab, view toggles)
export const layouts = store('ds3d.layouts', () => ({}));
export function layoutNow(ctx) { return { ...ctx.viewState(), panelW: parseInt(getComputedStyle(document.body).getPropertyValue('--panel-width')) || 380, timelineH: parseInt(getComputedStyle(document.body).getPropertyValue('--timeline-height')) || 230 }; }
export function applyLayout(ctx, L) {
  if (L.panelW) document.body.style.setProperty('--panel-width', Math.max(300, Math.min(700, L.panelW)) + 'px');
  if (L.timelineH) document.body.style.setProperty('--timeline-height', Math.max(150, Math.min(600, L.timelineH)) + 'px');
  ctx.setViewState(L);
  store('ds3d.layout.last', () => null).set(L);
}
export function saveLayout(ctx, name) {
  name ??= prompt('Name this layout (e.g. "Posing", "Timing", "Review")', '');
  if (!name) return null;
  const all = layouts.get();
  all[name] = layoutNow(ctx);
  layouts.set(all);
  ctx.refreshMenu?.();
  ctx.toast(`Layout "${name}" saved`);
  return all[name];
}
export function useLayout(ctx, name) {
  const L = layouts.get()[name];
  if (!L) throw Error('No layout ' + name + '. Saved: ' + Object.keys(layouts.get()).join(', '));
  applyLayout(ctx, L);
  return L;
}
export function restoreLastLayout(ctx) { const L = store('ds3d.layout.last', () => null).get(); if (L) applyLayout(ctx, L); }
// drag handles: the panel's left edge and the timeline's top edge
export function bindResizers(ctx) {
  const handle = (cls, onMove) => {
    const el = document.createElement('div');
    el.className = 'resizer ' + cls;
    el.addEventListener('pointerdown', e => {
      e.preventDefault(); el.setPointerCapture(e.pointerId);
      const mv = ev => onMove(ev);
      const up = () => { el.removeEventListener('pointermove', mv); el.removeEventListener('pointerup', up); store('ds3d.layout.last', () => null).set(layoutNow(ctx)); ctx.resized(); };
      el.addEventListener('pointermove', mv); el.addEventListener('pointerup', up);
    });
    return el;
  };
  document.querySelector('#panel').append(handle('panel-edge', ev => { document.body.style.setProperty('--panel-width', Math.max(300, Math.min(700, innerWidth - ev.clientX)) + 'px'); ctx.resized(); }));
  document.querySelector('#timeline').append(handle('timeline-edge', ev => { document.body.style.setProperty('--timeline-height', Math.max(150, Math.min(600, innerHeight - ev.clientY)) + 'px'); ctx.resized(); }));
}

// ---------------------------------------------------------------- viewport pop-out (to the second screen; the Kamvas stays primary)
let pop = null;
export function popOut(ctx) {
  if (pop && !pop.closed) { pop.focus(); return true; }
  pop = window.open('', 'ds3d-viewport', 'width=900,height=1000');
  if (!pop) { ctx.toast('The pop-out window was blocked'); return false; }
  pop.document.title = 'Doodle Studio 3D: viewport';
  pop.document.body.style.cssText = 'margin:0;background:#E0A64B;display:grid;place-items:center;height:100vh;overflow:hidden';
  const c = pop.document.createElement('canvas');
  c.id = 'mirror';
  pop.document.body.append(c);
  pop.addEventListener('keydown', e => { if (e.key === ' ') { e.preventDefault(); ctx.togglePlay(); } else if (e.key === 'ArrowLeft') ctx.step(-1); else if (e.key === 'ArrowRight') ctx.step(1); });
  return true;
}
export const popOpen = () => !!(pop && !pop.closed);
export function popDraw(src) {
  if (!pop || pop.closed) return 0;
  const t = performance.now(), c = pop.document.getElementById('mirror');
  const W = pop.innerWidth, H = pop.innerHeight, k = Math.min(W / src.width, H / src.height);
  const w = Math.max(1, Math.floor(src.width * k)), hh = Math.max(1, Math.floor(src.height * k));
  if (c.width !== w || c.height !== hh) { c.width = w; c.height = hh; }
  c.getContext('2d').drawImage(src, 0, 0, w, hh);
  return performance.now() - t;
}
export function closePop() { if (pop && !pop.closed) pop.close(); pop = null; }

// ---------------------------------------------------------------- favourites and recents
const favs = store('ds3d.favs', () => []), recents = store('ds3d.recents', () => []);
export function noteRun(id) { recents.set([id, ...recents.get().filter(x => x !== id)].slice(0, 12)); }
export const recentIds = () => recents.get();
export const isFav = id => favs.get().includes(id);
export function toggleFav(id) { const f = favs.get(); const on = !f.includes(id); favs.set(on ? [...f, id] : f.filter(x => x !== id)); return on; }
export function quickbar(ctx) {
  const { h } = ctx, cmds = new Map(ctx.commands().map(c => [cmdId(c), c]));
  // only what you pinned sits on the bar; recent tools stay in Ctrl+K, out of the way
  return favs.get().filter(id => cmds.has(id)).map(id => h('button', { class: 'fav', title: `${id} (favourite: right-click to unpin)`,
    onclick: () => ctx.runCommand(cmds.get(id)), oncontextmenu: e => { e.preventDefault(); toggleFav(id); ctx.refreshQuickbar(); } }, '★ ' + cmds.get(id).label.replace(/…$/, '')));
}

// ---------------------------------------------------------------- snapping
export const snap = { on: false };
export function snapValue(id, v, lenses) {
  if (!snap.on) return v;
  if (id === 'cam.lens') return lenses.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a));
  if (/^cam\.(dist|tx|ty|tz|focus)$/.test(id)) return Math.round(v / 0.05) * 0.05;
  if (id === 'cam.fstop') return Math.round(v * 2) / 2;
  if (id === 's') return Math.round(v / 0.05) * 0.05;
  return Math.round(v / 5) * 5;
}

// ---------------------------------------------------------------- fps meter that names the heavy item
const cost = {};
export function perf(name, ms) { cost[name] = cost[name] == null ? ms : cost[name] * 0.9 + ms * 0.1; }
export function heavy() {
  const [name, ms] = Object.entries(cost).sort((a, b) => b[1] - a[1])[0] || [];
  return name && ms > 4 ? `${name} ${ms.toFixed(0)} ms` : null;
}

// ---------------------------------------------------------------- shot status
export const STATUS = [['blocking', 'Blocking'], ['splined', 'Splined'], ['polish', 'Polish'], ['approved', 'Approved']];
export const statusOf = s => s.status || 'blocking';
export function setStatus(s, st) {
  if (!STATUS.some(x => x[0] === st)) throw Error('status must be ' + STATUS.map(x => x[0]).join(', '));
  s.status = st;
  return st;
}
export const nextStatus = s => STATUS[(STATUS.findIndex(x => x[0] === statusOf(s)) + 1) % STATUS.length][0];

// ---------------------------------------------------------------- reel templates
export const TEMPLATES = [
  { id: 'storytime-reel', name: 'Storytime reel (9:16, 60 s)', size: [1080, 1920], shots: [['Hook', 3], ['Setup', 12], ['Build', 20], ['Twist', 15], ['Payoff and loop back', 10]] },
  { id: 'quick-take', name: 'Quick take (9:16, 30 s)', size: [1080, 1920], shots: [['Hook', 2], ['Point', 18], ['Punchline', 7], ['Loop back', 3]] },
  { id: 'music-reel', name: 'Music reel (9:16, 15 s)', size: [1080, 1920], shots: [['Intro', 2], ['Verse', 9], ['Drop', 4]] },
  { id: 'youtube-storytime', name: 'YouTube storytime (16:9, 3 min)', size: [1920, 1080], chapters: true, shots: [['Cold open', 10], ['Intro', 15], ['Story', 120], ['Payoff', 25], ['Outro', 10]] },
  { id: 'carousel', name: 'Carousel (4:5, 5 slides)', size: [1080, 1350], shots: [['Slides', 5]] },
];
export function fromTemplate(tpl, scene) {
  scene.width = tpl.size[0]; scene.height = tpl.size[1];
  scene.shots = [];
  for (const [label, sec] of tpl.shots) {
    const s = newShotData(nextCode(scene), Math.round(sec * scene.fps));
    s.label = label;
    if (tpl.chapters) s.markers = [{ f: 0, note: 'Chapter: ' + label }];
    scene.shots.push(s);
  }
  scene.active = 0;
  scene.template = tpl.id;
  return scene;
}
export function templateDialog(ctx) {
  const { h } = ctx;
  return modal(ctx, 'New scene from a template', close => [
    h('p', { class: 'hint' }, 'Shots come named and timed for the format; change anything after.'),
    h('div', { class: 'ds-list' }, ...TEMPLATES.map(t => h('button', { onclick: () => { close(); ctx.newFromTemplate(t.id); } }, h('span', {}, t.name), h('small', {}, t.shots.map(s => `${s[0]} ${s[1]}s`).join(' · '))))),
    h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: close }, 'Cancel'))]);
}

// ---------------------------------------------------------------- draw-over review notes (a marker with a sketch)
export function drawNote(ctx, done) {
  const fr = document.querySelector('#frame');
  const c = document.createElement('canvas');
  c.id = 'note-draw';
  c.width = fr.clientWidth; c.height = fr.clientHeight;
  fr.append(c);
  const g = c.getContext('2d'), strokes = [];
  let cur = null;
  const pt = e => { const r = c.getBoundingClientRect(); return [+((e.clientX - r.left) / r.width).toFixed(4), +((e.clientY - r.top) / r.height).toFixed(4)]; };
  const paint = () => { g.clearRect(0, 0, c.width, c.height); paintSketch(g, strokes, c.width, c.height); };
  c.addEventListener('pointerdown', e => { c.setPointerCapture(e.pointerId); cur = [pt(e)]; strokes.push(cur); paint(); });
  c.addEventListener('pointermove', e => { if (cur) { cur.push(pt(e)); paint(); } });
  c.addEventListener('pointerup', () => { cur = null; });
  const bar = ctx.h('div', { class: 'note-bar' }, 'Draw your note on the frame, then ',
    ctx.h('button', { class: 'primary', onclick: () => finish(true) }, 'Done'), ctx.h('button', { onclick: () => finish(false) }, 'Cancel'));
  fr.append(bar);
  const key = e => { if (e.key === 'Escape') finish(false); else if (e.key === 'Enter') finish(true); };
  addEventListener('keydown', key, true);
  function finish(keep) {
    removeEventListener('keydown', key, true);
    c.remove(); bar.remove();
    if (keep && strokes.length) done(strokes);
  }
  return { strokes, finish, canvas: c };
}
export function paintSketch(g, strokes, W, H) {
  g.lineCap = g.lineJoin = 'round';
  for (const [w, col] of [[9, '#E0A64B'], [4, '#1F1F1D']]) {   // ink line with a mustard halo, so it reads over Bunny
    g.lineWidth = w; g.strokeStyle = col;
    for (const s of strokes) { g.beginPath(); s.forEach(([x, y], i) => (i ? g.lineTo(x * W, y * H) : g.moveTo(x * W, y * H))); if (s.length === 1) g.lineTo(s[0][0] * W + 0.5, s[0][1] * H); g.stroke(); }
  }
}
export function showNotes(project, frame) {
  const fr = document.querySelector('#frame');
  let c = document.getElementById('note-layer');
  const near = (project.markers || []).filter(m => m.sketch && Math.abs(m.f - frame) <= 2);
  if (!near.length) { c?.remove(); return; }
  if (!c) { c = document.createElement('canvas'); c.id = 'note-layer'; fr.insertBefore(c, document.querySelector('#hud')); }
  c.width = fr.clientWidth; c.height = fr.clientHeight;
  const g = c.getContext('2d');
  for (const m of near) paintSketch(g, m.sketch, c.width, c.height);
}

// ---------------------------------------------------------------- beats from the audio
export function detectBeats(env, from, length, fps) {
  if (!env) throw Error('Import audio for the scene first (File › Import audio…)');
  const out = [], gap = Math.round(fps * 0.25);
  let last = -1e9;
  for (let f = 1; f < length; f++) {
    const e = env[from + f] || 0, p = env[from + f - 1] || 0;
    let mean = 0, n = 0;
    for (let k = -8; k <= 0; k++) { const v = env[from + f + k]; if (v != null) { mean += v; n++; } }
    mean /= Math.max(1, n);
    if (e > 0.3 && e - p > 0.12 && e > mean * 1.3 && f - last >= gap) { out.push(f); last = f; }
  }
  return out;
}

// ---------------------------------------------------------------- split a shot, and split the voice into sentences
export function splitShotAt(scene, i, f) {
  const s = scene.shots[i];
  if (f <= 0 || f >= s.length) throw Error(`Split inside the shot: frame 1 to ${s.length - 1}`);
  const b = newShotData(nextCode(scene, i), s.length - f);
  b.label = s.label ? s.label + ' (2)' : '';
  for (const [k, v] of Object.entries(s)) if (!['uid', 'code', 'label', 'length', 'tracks', 'markers', 'items'].includes(k)) b[k] = JSON.parse(JSON.stringify(v));
  // the key segment that crosses the cut is baked frame by frame (linear), so the motion
  // plays exactly as before on both sides; Animate › Simplify keys thins it out later
  for (const [id, ks] of Object.entries(s.tracks)) {
    const prev = [...ks].reverse().find(k => k.f < f), next = ks.find(k => k.f >= f);
    const bake = prev && next && next.f > f && prev.ease !== 'hold';
    const vals = {};
    if (bake) for (let x = prev.f; x <= next.f; x++) vals[x] = valueAt(s, id, x);
    const at = valueAt(s, id, f), end = valueAt(s, id, f - 1);
    b.tracks[id] = ks.filter(k => k.f >= f).map(k => ({ ...k, f: k.f - f }));
    s.tracks[id] = ks.filter(k => k.f < f);
    if (bake) {
      for (let x = prev.f; x < f; x++) setKey(s, id, x, vals[x], 'linear');
      for (let x = f; x < next.f; x++) setKey(b, id, x - f, vals[x], 'linear');
    } else {
      if (!b.tracks[id].some(k => k.f === 0)) b.tracks[id].unshift({ f: 0, v: at, ease: prev?.ease || 'ease' });
      if (!s.tracks[id].some(k => k.f === f - 1)) setKey(s, id, f - 1, end, prev?.ease || 'ease');
    }
  }
  b.markers = (s.markers || []).filter(m => m.f >= f).map(m => ({ ...m, f: m.f - f }));
  s.markers = (s.markers || []).filter(m => m.f < f);
  b.items = (s.items || []).filter(it => it.frame >= f).map(it => ({ ...it, frame: it.frame - f }));
  s.items = (s.items || []).filter(it => it.frame < f);
  s.length = f;
  scene.shots.splice(i + 1, 0, b);
  return b;
}
// pauses in the voice (quiet for 0.3 s or more), as frame numbers inside the shot
export function pauses(env, from, length, fps, minSec = 0.3) {
  const out = [];
  let start = null;
  for (let f = 0; f <= length; f++) {
    const q = f < length && (env[from + f] || 0) < 0.06;
    if (q) { if (start == null) start = f; }
    else if (start != null) { if (f - start >= minSec * fps && start > 0 && f < length) out.push({ at: Math.round((start + f) / 2), len: f - start }); start = null; }
  }
  return out;
}
export function sentences(text) { return String(text || '').replace(/\s+/g, ' ').match(/[^.!?…]+[.!?…]*/g)?.map(s => s.trim()).filter(Boolean) || []; }
export function splitBySentences(scene, i, env, from, transcript = '') {
  const s = scene.shots[i], fps = scene.fps;
  const ps = pauses(env, from, s.length, fps);
  const said = sentences(transcript);
  let cuts = ps;
  if (said.length > 1) cuts = [...ps].sort((a, b) => b.len - a.len).slice(0, said.length - 1);
  cuts = cuts.map(p => p.at).sort((a, b) => a - b);
  if (!cuts.length) throw Error('No pause long enough to split at (0.3 s of quiet)');
  for (let k = cuts.length - 1; k >= 0; k--) splitShotAt(scene, i, cuts[k]);
  const made = scene.shots.slice(i, i + cuts.length + 1);
  made.forEach((x, k) => { x.label = said[k] ? said[k].split(' ').slice(0, 5).join(' ') + (said[k].split(' ').length > 5 ? '…' : '') : `Line ${k + 1}`; if (said[k]) x.line = said[k]; });
  return made.map(x => ({ code: x.code, label: x.label, seconds: +(x.length / fps).toFixed(2) }));
}
