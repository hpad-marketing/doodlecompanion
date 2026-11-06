// The 2D Doodle Studio's panel organisation for Doodle Studio 3D: three docks (Canvas, Tools,
// Timeline) with title bars. Drag a title onto another dock to swap them, pull it outside the
// window to detach it into its own window (a second screen), close that window to dock it back.
// Detached docks keep the same DOM, model, undo and autosave: nothing is copied.
const KEY = 'ds3d.docks.v1';
const NAMES = { canvas: 'Canvas', tools: 'Tools', timeline: 'Timeline' };
const AREAS = ['canvas', 'tools', 'timeline'];
const DEFAULT = { layout: 'classic', areas: { canvas: 'canvas', tools: 'tools', timeline: 'timeline' }, canvasW: null, timelineH: null, detached: {}, bounds: {} };
export const LAYOUTS = [['classic', 'Canvas left'], ['canvas-right', 'Canvas right'], ['timeline-wide', 'Timeline full width'], ['timeline-wide-right', 'Canvas right, timeline full width']];

let state = load(), ctx = null, quitting = false;
const pops = {};   // dock -> window
function load() { try { return { ...DEFAULT, ...JSON.parse(localStorage.getItem(KEY) || '{}') }; } catch { return { ...DEFAULT }; } }
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch {} }
const dockEl = name => (pops[name] && !pops[name].closed ? pops[name].document : document).getElementById('dock-' + name);

// every document the docks live in (the main window and any detached windows)
export const docs = () => [document, ...Object.values(pops).filter(w => w && !w.closed).map(w => w.document)];
export function query(sel) { for (const d of docs()) { const el = d.querySelector(sel); if (el) return el; } return null; }
export const isDetached = name => !!(pops[name] && !pops[name].closed);
export const winOf = el => el?.ownerDocument?.defaultView || window;

export function apply() {
  const ws = document.getElementById('workspace');
  ws.dataset.layout = state.layout;
  for (const n of AREAS) { const el = document.getElementById('dock-' + n); if (el) el.style.gridArea = state.areas[n] || n; }
  if (state.canvasW) document.body.style.setProperty('--canvas-width', state.canvasW + 'px');
  if (state.timelineH) document.body.style.setProperty('--timeline-height', state.timelineH + 'px');
  for (const n of AREAS) {
    const hide = !isDetached(n) && !!state.hidden?.[n];
    ws.classList.toggle('no-' + (state.areas[n] || n), isDetached(n) || hide);
    const el = document.getElementById('dock-' + n); if (el) el.hidden = hide;
  }
  ctx?.resized();
}
// hide a dock for more room (Ctrl+Shift+H hides the tools panel, as Hide Assistant does in Doodle Studio)
export function toggleHidden(name, on) {
  if (name === 'canvas') return false;
  state.hidden = { ...(state.hidden || {}), [name]: on ?? !state.hidden?.[name] };
  save(); apply();
  return state.hidden[name];
}
export const isHidden = name => !!state.hidden?.[name];
export function setLayout(name) {
  if (!LAYOUTS.some(l => l[0] === name)) throw Error('Layout must be one of ' + LAYOUTS.map(l => l[0]).join(', '));
  state.layout = name; state.areas = { ...DEFAULT.areas }; save(); apply();
  return name;
}
export function swap(a, b) {
  if (a === b) return;
  const t = state.areas[a]; state.areas[a] = state.areas[b]; state.areas[b] = t;
  save(); apply();
  ctx?.toast(`${NAMES[a]} and ${NAMES[b]} swapped places`);
}
export const layoutState = () => JSON.parse(JSON.stringify(state));
export function setLayoutState(L) { if (!L) return; state = { ...DEFAULT, ...L, detached: state.detached, bounds: state.bounds }; save(); apply(); }
export function setSizes({ canvasW, timelineH }) {
  if (canvasW != null) state.canvasW = Math.round(Math.max(260, Math.min(innerWidth - 420, canvasW)));
  if (timelineH != null) state.timelineH = Math.round(Math.max(140, Math.min(innerHeight - 220, timelineH)));
  save(); apply();
}

// ---------------------------------------------------------------- detach / dock back
export function detach(name) {
  // the 3D view keeps its GPU context in the main window: its second-screen window is a live mirror
  if (name === 'canvas') { ctx?.popOut(); return true; }
  if (isDetached(name)) { pops[name].focus(); return true; }
  if (ctx?.busy?.()) { ctx.toast('Finish playback, the render check or the current drag before detaching'); return false; }
  const el = document.getElementById('dock-' + name);
  const b = state.bounds[name] || {};
  const feat = `width=${b.w || (name === 'timeline' ? 1600 : 1000)},height=${b.h || (name === 'timeline' ? 460 : 900)}${b.x != null ? `,left=${b.x},top=${b.y}` : ''}`;
  const w = window.open('', 'ds3d-panel-' + name, feat);
  if (!w) { ctx?.toast('The window was blocked'); return false; }
  const d = w.document;
  d.open(); d.write('<!doctype html><html><head><meta charset="utf-8"><title>Doodle Studio 3D — ' + NAMES[name] + '</title></head><body></body></html>'); d.close();
  for (const l of document.querySelectorAll('link[rel=stylesheet],style')) d.head.append(d.importNode(l, true));
  for (const l of d.querySelectorAll('link[rel=stylesheet]')) l.href = new URL(l.getAttribute('href'), location.href).href;
  d.body.className = document.body.className + ' detached-body';
  if (document.body.dataset.theme) d.body.dataset.theme = document.body.dataset.theme;
  d.documentElement.style.height = '100%';
  d.body.style.cssText = 'display:grid;grid-template-rows:minmax(0,1fr);grid-template-areas:none;height:100%';
  el.style.gridArea = 'auto';
  d.body.append(d.adoptNode(el));
  pops[name] = w;
  state.detached[name] = true; save();
  document.getElementById('workspace').classList.add('no-' + (state.areas[name] || name));
  const back = () => dockBack(name, true);
  w.addEventListener('pagehide', back);
  w.addEventListener('beforeunload', back);
  // keys typed in a detached window work as in the main one
  w.addEventListener('keydown', e => {
    if (e.target.matches?.('input,select,textarea')) return;
    const ev = new KeyboardEvent('keydown', { key: e.key, code: e.code, ctrlKey: e.ctrlKey, shiftKey: e.shiftKey, altKey: e.altKey, metaKey: e.metaKey, bubbles: true, cancelable: true });
    document.body.dispatchEvent(ev);
    if (ev.defaultPrevented) e.preventDefault();
  });
  w.addEventListener('resize', () => ctx?.resized());
  w.addEventListener('pointerdown', e => ctx?.pointerdownIn?.(e), true);
  markButtons();
  apply();
  ctx?.toast(`${NAMES[name]} detached. Move its window to another screen; close it to dock it back.`, 4000);
  return true;
}
export function dockBack(name, closing = false) {
  const w = pops[name];
  if (!w) return false;
  delete pops[name];
  if (quitting) return true;
  try { state.bounds[name] = { x: w.screenX, y: w.screenY, w: w.outerWidth, h: w.outerHeight }; } catch {}
  const el = w.document.getElementById('dock-' + name);
  if (el) document.getElementById('workspace').append(document.adoptNode(el));
  state.detached[name] = false; save();
  if (!closing) try { w.close(); } catch {}
  markButtons();
  apply();
  return true;
}
export function dockAll() { for (const n of AREAS) dockBack(n); }
function markButtons() {
  for (const n of AREAS) {
    const el = dockEl(n);
    const box = el?.querySelector('.dock-btns');
    if (!box) continue;
    box.replaceChildren();
    const d = el.ownerDocument, b = d.createElement('button');
    b.textContent = n === 'canvas' ? 'Pop out' : isDetached(n) ? 'Dock back' : 'Detach';
    b.title = n === 'canvas' ? 'Show the 3D view in its own window too, for a second screen (it mirrors this one)' : isDetached(n) ? `Put the ${NAMES[n]} back into the main window` : `Open the ${NAMES[n]} in its own window, for a second screen`;
    b.addEventListener('click', () => (isDetached(n) ? dockBack(n) : detach(n)));
    box.append(b);
  }
}

// ---------------------------------------------------------------- dragging titles
function bindTitles() {
  for (const n of AREAS) {
    const el = document.getElementById('dock-' + n), t = el.querySelector('.dock-title');
    t.addEventListener('pointerdown', e => {
      if (e.button !== 0 || e.target.closest('button')) return;
      if (isDetached(n)) return;   // a detached window is moved by its own title bar
      e.preventDefault();
      t.setPointerCapture(e.pointerId);
      const ghost = Object.assign(document.createElement('div'), { className: 'dock-ghost', textContent: NAMES[n] });
      let target = null, out = false, moved = false;
      const x0 = e.clientX, y0 = e.clientY;
      const mv = ev => {
        if (!moved && Math.hypot(ev.clientX - x0, ev.clientY - y0) < 6) return;
        if (!moved) { moved = true; document.body.append(ghost); document.body.classList.add('dock-dragging'); }
        ghost.style.left = ev.clientX + 12 + 'px'; ghost.style.top = ev.clientY + 8 + 'px';
        out = ev.clientX < 2 || ev.clientY < 2 || ev.clientX > innerWidth - 3 || ev.clientY > innerHeight - 3;
        ghost.classList.toggle('out', out);
        ghost.textContent = out ? `Release to detach ${NAMES[n]}` : NAMES[n];
        const over = document.elementsFromPoint(ev.clientX, ev.clientY).find(x => x.classList?.contains('dock'));
        const tn = over && over !== el ? over.dataset.dock : null;
        if (tn !== target) { document.querySelectorAll('.dock.drop-target').forEach(d => d.classList.remove('drop-target')); target = tn; if (tn) over.classList.add('drop-target'); }
        if (target) ghost.textContent = `Swap with ${NAMES[target]}`;
      };
      const up = () => {
        t.removeEventListener('pointermove', mv); t.removeEventListener('pointerup', up); t.removeEventListener('pointercancel', up);
        ghost.remove(); document.body.classList.remove('dock-dragging');
        document.querySelectorAll('.dock.drop-target').forEach(d => d.classList.remove('drop-target'));
        if (!moved) return;
        if (out) detach(n); else if (target) swap(n, target);
      };
      t.addEventListener('pointermove', mv); t.addEventListener('pointerup', up); t.addEventListener('pointercancel', up);
    });
  }
}

// resize handles: the canvas column edge and the timeline's top edge
function bindResizers() {
  const mk = (cls, el, onMove) => {
    const r = document.createElement('div');
    r.className = 'resizer ' + cls;
    r.addEventListener('pointerdown', e => {
      e.preventDefault(); r.setPointerCapture(e.pointerId);
      const mv = ev => onMove(ev), up = () => { r.removeEventListener('pointermove', mv); r.removeEventListener('pointerup', up); save(); };
      r.addEventListener('pointermove', mv); r.addEventListener('pointerup', up);
    });
    el.append(r);
  };
  const canvas = document.getElementById('dock-canvas'), tl = document.getElementById('dock-timeline');
  mk('canvas-edge', canvas, ev => {
    const right = /right/.test(state.layout) !== (state.areas.canvas !== 'canvas' && state.areas.canvas === 'tools');
    const r = canvas.getBoundingClientRect();
    setSizes({ canvasW: right ? r.right - ev.clientX : ev.clientX - r.left });
  });
  mk('timeline-edge', tl, ev => { const ws = document.getElementById('workspace').getBoundingClientRect(); setSizes({ timelineH: ws.bottom - ev.clientY }); });
}

export function init(c) {
  ctx = c;
  bindTitles();
  bindResizers();
  markButtons();
  apply();
  // detached windows from last time open again (Electron allows it at start; a browser may block it)
  for (const n of ['tools', 'timeline']) if (state.detached[n]) setTimeout(() => { if (!detach(n)) { state.detached[n] = false; save(); } }, 600);
  addEventListener('beforeunload', () => { quitting = true; for (const w of Object.values(pops)) try { w.close(); } catch {} });
}
