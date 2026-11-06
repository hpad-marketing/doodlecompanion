// Speech bubbles in the studio: the Library shelf, placing on the Stage, the timing and the render.
// The drawing is bubbles.js. Bubbles sit on their own canvas over the view; only the render bakes them.
import * as THREE from 'three';
import * as B from './bubbles.js';
import * as BB from './babblescene.js';

const SHELVES = [['Speech bubbles', 'bubble'], ['Bursts', 'burst'], ['Dialogue box', 'box']];
const OVER = 0.13;   // how far above the head a new bubble sits
const VW = 1080, VH = 1920;

export function bubbleUi(ctx) {
  const { h, $, toast } = ctx;
  let sel = null, drag = null, editor = null, tiles = [], ticking = false;
  const shot = () => ctx.project(), list = () => shot().bubbles || [], fps = () => shot().fps || ctx.scene().fps || 30;
  const byId = id => list().find(b => b.id === id);
  const measure = document.createElement('canvas').getContext('2d');
  const size = () => { const s = ctx.scene(); return [s.width || 1080, s.height || 1920]; };
  B.loadFonts().then(() => draw());

  // ---------------------------------------------------------------- where a head is on the frame
  const actorOf = sp => (sp === 'lead' ? ctx.view() : ctx.view().actors?.[Number(String(sp).slice(1))]);
  function head(sp) {
    const v = ctx.view(), a = actorOf(sp);
    if (!a) return null;
    try {
      const cam = v.camera; cam.updateMatrixWorld();
      const p = v.headPoint.call(a), right = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0), up = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1);
      const scr = q => { const n = q.clone().project(cam); return [(n.x + 1) / 2, (1 - n.y) / 2]; };
      const c = scr(p), e = scr(p.clone().addScaledVector(right, ctx.headRadius)), t = scr(p.clone().addScaledVector(up, ctx.headRadius));
      return { x: c[0], y: c[1], rx: Math.hypot(e[0] - c[0], e[1] - c[1]), ry: Math.hypot(t[0] - c[0], t[1] - c[1]) };
    } catch { return null; }
  }
  // the eyes and mouth: the middle of the head, not the ears or the top of it
  const faceOf = c => ({ x0: c.x - c.rx * 0.82, x1: c.x + c.rx * 0.82, y0: c.y - c.ry * 0.5, y1: c.y + c.ry * 0.62 });
  const faces = () => ['lead', ...(shot().costars || []).map((_, i) => 'c' + i)].map(head).filter(Boolean).map(faceOf);

  function linked() {
    for (const b of list()) {
      if (!b.babble) continue;
      const l = BB.linesOf(ctx.scene()).find(x => x.id === b.babble);
      if (!l || l.shot !== shot().uid) { delete b.babble; delete b.match; continue; }
      b.f = l.f; b.len = Math.max(2, Math.min(shot().length - b.f, ctx.babbleLen(l) + B.REST + 6));
    }
  }
  // what is drawn at this frame, with the head where it is now
  function resolve(b, f, opts = {}) {
    const [W, H] = size(), kind = B.PRESETS[b.preset].kind, sp = kind === 'bubble' ? b.speaker : null, c = sp != null ? head(sp) : null;
    const it = { preset: b.preset, text: b.text, fill: b.fill, pop: b.pop, font: b.font, w: b.w, name: b.name, boil: b.boil, fps: fps(), len: b.len, x: b.x ?? 0.5, y: b.y ?? 0.3, tip: null };
    if (c && b.follow !== false) { it.x = c.x + (b.dx ?? 0); it.y = c.y + (b.dy ?? -(c.ry + OVER)); }
    if (b.snap !== false && !opts.free) Object.assign(it, B.place(measure, it, W, H, faces()));
    if (c) {
      const L = B.layout(measure, it, W, H), a = Math.atan2((it.y - c.y) / c.ry, (it.x - c.x) / c.rx);
      for (let k = 1; k >= 0.6; k -= 0.1) { it.tip = { x: c.x + Math.cos(a) * c.rx * k, y: c.y + Math.sin(a) * c.ry * k }; if (Math.hypot((it.tip.x - it.x) * W / L.rx, (it.tip.y - it.y) * H / L.ry) > 1.3) break; }
    }
    if (b.sync) it.reveal = wordsAt(b, f - b.f);
    return it;
  }
  function wordsAt(b, t) {
    const n = b.text.split(/\s+/).filter(Boolean).length, words = ctx.scene().transcript?.words;
    if (b.match === 'voice' && words?.length) { const a0 = (ctx.shotStart() + b.f) / fps(), at = a0 + t / fps(); return Math.max(1, words.filter(w => w.t0 <= at && w.t0 >= a0 - 0.1).length); }
    return Math.max(1, Math.ceil(n * (t + 1) / Math.max(1, b.len - B.REST - 6)));
  }
  const showing = (b, f) => !b.hidden && !ctx.isolated('b:' + b.id) && f >= b.f && f < b.f + b.len;

  // ---------------------------------------------------------------- on the Stage
  function draw() {
    linked();
    const fr = $('#frame'), f = ctx.frame(), now = list().filter(b => showing(b, f));
    let c = document.getElementById('bubble-layer');
    if (!fr) return;
    if (!now.length) { c?.remove(); return; }
    if (!c) { c = h('canvas', { id: 'bubble-layer' }); fr.insertBefore(c, $('#hud')); }
    const pr = Math.min(2, window.devicePixelRatio || 1), W = c.width = Math.round(fr.clientWidth * pr), H = c.height = Math.round(fr.clientHeight * pr), g = c.getContext('2d');
    for (const b of now) B.drawBubbleItem(g, W, H, resolve(b, f, { free: drag?.b === b }), f - b.f);
    const s = byId(sel);
    if (s && now.includes(s) && !editor && B.PRESETS[s.preset].kind === 'bubble') {
      const it = resolve(s, f, { free: drag?.b === s }), [sw, sh] = size(), L = B.layout(measure, it, sw, sh);
      g.beginPath(); g.arc((it.x + L.rx / sw) * W, it.y * H, Math.max(6 * pr, H * 0.012), 0, Math.PI * 2); g.fillStyle = B.MUSTARD; g.fill(); g.lineWidth = Math.max(2 * pr, B.inkPx(W, H) * 0.8); g.strokeStyle = B.INK; g.stroke();
    }
  }
  function hitAt(e) {
    const r = $('#frame').getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height, [W, H] = size(), f = ctx.frame();
    const s = byId(sel);
    if (s && showing(s, f) && B.PRESETS[s.preset].kind === 'bubble') { const it = resolve(s, f), L = B.layout(measure, it, W, H), hx = it.x + L.rx / W; if (Math.hypot((x - hx) * W / H, y - it.y) < 0.03) return { b: s, it, mode: 'pull', x, y }; }
    for (const b of [...list()].reverse()) {
      if (!showing(b, f)) continue;
      const it = resolve(b, f), { hw, hh } = B.extent(measure, it, W, H);
      if (Math.abs(x - it.x) <= hw && Math.abs(y - it.y) <= hh) return { b, it, mode: 'move', x, y };
    }
    return null;
  }
  function bind() {
    const fr = $('#frame');
    fr.addEventListener('pointerdown', e => {
      if (e.button || editor) return;
      const hit = hitAt(e);
      if (!hit) { if (sel) { sel = null; draw(); ctx.refresh(); } return; }
      e.stopPropagation(); e.preventDefault();
      const b = hit.b, was = sel; sel = b.id;
      drag = { b, mode: hit.mode, ox: hit.x - hit.it.x, oy: hit.y - hit.it.y, undone: false };
      const w = fr.ownerDocument.defaultView;
      const move = ev => {
        const r = fr.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width, y = (ev.clientY - r.top) / r.height, [W, H] = size();
        if (!drag.undone) { ctx.pushUndo(drag.mode === 'pull' ? 'Resize bubble' : 'Move bubble'); drag.undone = true; }
        if (drag.mode === 'pull') { const it = resolve(b, ctx.frame(), { free: true }), L = B.layout(measure, it, W, H); b.w = Math.max(0.14, Math.min(0.76, 2 * (Math.abs(x - it.x) - L.size * 1.05 / W))); }
        else put(b, x - drag.ox, y - drag.oy);
        draw();
      };
      const up = () => { w.removeEventListener('pointermove', move); w.removeEventListener('pointerup', up); const moved = drag.undone; drag = null; if (moved) ctx.dirty(); draw(); if (moved || was !== b.id) ctx.refresh(); };
      w.addEventListener('pointermove', move); w.addEventListener('pointerup', up);
      draw(); if (was !== b.id) ctx.refresh();
    }, true);
    fr.addEventListener('dblclick', e => { const hit = hitAt(e); if (hit) { e.stopPropagation(); e.preventDefault(); sel = hit.b.id; edit(hit.b); } }, true);
    fr.addEventListener('dragover', e => { if (e.dataTransfer.types.includes('text/ds3d-bubble')) e.preventDefault(); });
    fr.addEventListener('drop', e => { const p = e.dataTransfer.getData('text/ds3d-bubble'); if (!p) return; e.preventDefault(); const r = fr.getBoundingClientRect(), b = addAt(p, ctx.frame()); put(b, (e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height); ctx.dirty(); draw(); });
    const tr = $('#tracks');
    tr.addEventListener('dragover', e => { if (e.dataTransfer.types.includes('text/ds3d-bubble')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; } });
    tr.addEventListener('drop', e => { const p = e.dataTransfer.getData('text/ds3d-bubble'); if (!p) return; e.preventDefault(); const f = ctx.frameAtX(e.clientX); addAt(p, f); ctx.goto(Math.min(f + 12, shot().length - 1)); });
  }
  // the bubble goes where it is dropped, and a speech bubble keeps its place by its speaker
  function put(b, x, y) {
    const c = B.PRESETS[b.preset].kind === 'bubble' && b.speaker != null && b.follow !== false ? head(b.speaker) : null;
    if (c) { b.dx = x - c.x; b.dy = y - c.y; } else { b.x = x; b.y = y; }
  }
  function addAt(preset, f, o = {}) {
    ctx.pushUndo('Add speech bubble');
    const b = B.addBubble(shot(), preset, { fps: fps(), ...o, f });
    sel = b.id; ctx.changed(); return b;
  }
  // the text box over the bubble: Enter is a new line, Esc or clicking away keeps it
  function edit(b) {
    if (editor) return;
    if (ctx.frame() < b.f + 10) ctx.goto(Math.min(b.f + 12, b.f + b.len - 1));
    const it = resolve(b, ctx.frame()), fr = $('#frame'), [W, H] = size(), L = B.layout(measure, it, W, H), scale = fr.clientWidth / W;
    ctx.pushUndo('Edit bubble text');
    const ta = h('textarea', { class: 'bubble-edit', 'aria-label': 'Bubble text', style: `left:${(it.x * 100).toFixed(2)}%;top:${(it.y * 100).toFixed(2)}%;width:${Math.max(120, (L.tw + L.size * 2) * scale)}px;font-size:${Math.max(13, L.size * scale)}px` });
    ta.value = b.text;
    const fit = () => { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; };
    ta.addEventListener('input', () => { b.text = ta.value; draw(); fit(); });
    const done = () => { if (!editor) return; editor = null; ta.remove(); ctx.dirty(); spoken(b); draw(); ctx.refresh(); ctx.tracks(); };
    ta.addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Escape') done(); });
    ta.addEventListener('blur', done);
    editor = ta; fr.append(ta); fit(); ta.focus(); ta.select(); draw();
  }
  // a bubble tied to a Babble line says what it shows
  async function spoken(b) {
    if (!b.babble) return;
    const l = BB.linesOf(ctx.scene()).find(x => x.id === b.babble), t = b.text.replace(/\s+/g, ' ').trim();
    if (l && t && l.text !== t) { l.text = t; await ctx.babble({ action: 'rebuild' }); draw(); ctx.refresh(); }
  }

  // ---------------------------------------------------------------- timing
  async function speak(b) {
    const who = b.speaker == null || b.speaker === 'lead' ? 'lead' : Number(String(b.speaker).slice(1));
    const r = await ctx.babble({ action: 'add', frame: b.f, text: b.text.replace(/\s+/g, ' ').trim(), who });
    b.babble = r.line.id; b.match = 'babble'; linked(); ctx.changed();
    return b;
  }
  function matchVoice(b) {
    const start = ctx.shotStart(), env = ctx.envelope(), words = ctx.scene().transcript?.words;
    if (!env) throw Error('Import a voice for the scene first, or use Babble');
    let a = start + b.f;
    if (words?.length) {
      const near = words.filter(w => w.t1 * fps() >= a).sort((x, y) => x.t0 - y.t0)[0];
      if (near) { let i = words.indexOf(near); a = Math.round(near.t0 * fps()); while (words[i + 1] && words[i + 1].t0 - words[i].t1 < 0.5) i++; return setSpan(b, a - start, Math.round(words[i].t1 * fps()) - start); }
    }
    while (a < env.length && env[a] < 0.12) a++;
    if (a >= env.length) throw Error('No voice after this bubble');
    let z = a, quiet = 0;
    for (; z < env.length && quiet < fps() * 0.4; z++) quiet = env[z] < 0.12 ? quiet + 1 : 0;
    return setSpan(b, a - start, z - quiet - start);
  }
  function setSpan(b, f, end) {
    b.f = Math.max(0, Math.min(shot().length - 2, f)); b.len = Math.max(2, Math.min(shot().length - b.f, end - b.f + B.REST + 2)); b.match = 'voice'; delete b.babble;
    ctx.changed(); return b;
  }

  // ---------------------------------------------------------------- the Library shelf
  function tick(now) {
    tiles = tiles.filter(t => t.c.isConnected);
    if (!tiles.length) { ticking = false; return; }
    for (const t of tiles) {
      const w = t.c.clientWidth || 96, d = Math.min(2, window.devicePixelRatio || 1), g = t.c.getContext('2d');
      if (t.c.width !== Math.round(w * d)) { t.c.width = Math.round(w * d); t.c.height = Math.round(w * 0.75 * d); }
      const k = t.c.width / (t.box ? VW : VW * 0.92), vw = t.c.width / k, vh = t.c.height / k;
      g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, t.c.width, t.c.height);
      g.setTransform(k, 0, 0, k, (vw / 2 - VW * 0.5) * k, (vh * (t.tail ? 0.4 : 0.5) - VH * 0.5) * k);
      B.drawBubbleItem(g, VW, VH, { ...t.it, x: 0.5, y: 0.5, tip: t.tail ? { x: 0.5, y: 0.5 + vh * 0.44 / VH } : null, len: 80, fps: 30 }, Math.floor((now - t.t0) / 33.3) % 96);
    }
    requestAnimationFrame(tick);
  }
  function card(id) {
    const p = B.PRESETS[id], c = h('canvas', { 'aria-hidden': 'true' });
    tiles.push({ c, it: { preset: id, text: p.sample, fill: p.fill || 'mustard', pop: 'soft' }, box: p.kind === 'box', tail: p.kind === 'bubble', t0: performance.now() - Math.random() * 800 });
    const b = h('button', { class: 'lib-item libx-card bubble-card', draggable: 'true', 'data-bubble': id, title: `${p.name}. Drag onto the timeline or the Stage. Double-click to add at the playhead.`, ondblclick: () => addAt(id, ctx.frame()) }, h('span', { class: 'pic' }, c), h('span', {}, p.name));
    b.addEventListener('dragstart', e => { e.dataTransfer.setData('text/ds3d-bubble', id); e.dataTransfer.effectAllowed = 'copy'; });
    return b;
  }
  function panel() {
    tiles = [];
    const box = h('div', { class: 'libx bubbles' }), main = h('div', {});
    for (const [name, kind] of SHELVES) main.append(h('h3', {}, name), h('div', { class: 'libx-grid', role: 'list' }, ...Object.keys(B.PRESETS).filter(k => B.PRESETS[k].kind === kind).map(card)));
    box.append(main, editorPanel());
    if (!ticking) { ticking = true; requestAnimationFrame(tick); }
    return box;
  }
  function editorPanel() {
    const side = h('div', { class: 'libx-side' }), b = byId(sel);
    if (!b) { side.append(h('p', { class: 'hint' }, 'Drag a bubble onto the timeline, or double-click it to add it at the playhead. Click a bubble on the Stage to change it.')); return side; }
    const p = B.PRESETS[b.preset], set = (k, v) => { ctx.pushUndo('Change bubble'); if (v === undefined) delete b[k]; else b[k] = v; ctx.changed(); };
    const row = (label, el, tip) => h('label', { class: 'row', title: tip }, h('span', { style: 'flex:1' }, label), el);
    const select = (k, opts, on) => h('select', { 'aria-label': k }, ...opts.map(([v, n]) => h('option', { value: v, selected: on === v }, n)));
    const ta = h('textarea', { rows: 3, 'aria-label': 'Bubble text', style: 'width:100%' }); ta.value = b.text;
    let began = false;
    ta.addEventListener('input', () => { if (!began) { ctx.pushUndo('Edit bubble text'); began = true; } b.text = ta.value; draw(); });
    ta.addEventListener('change', () => { ctx.dirty(); spoken(b); ctx.tracks(); });
    ta.addEventListener('keydown', e => e.stopPropagation());
    const secs = h('input', { type: 'number', min: 0.1, step: 0.1, value: +(b.len / fps()).toFixed(2), style: 'width:64px', 'aria-label': 'Duration in seconds' });
    secs.addEventListener('change', () => { ctx.pushUndo('Bubble duration'); b.len = Math.max(2, Math.min(shot().length - b.f, Math.round(Number(secs.value) * fps()))); delete b.match; delete b.babble; ctx.changed(); });
    const end = select('Ends with', [['', 'The time I set'], ['babble', 'The Babble line'], ['voice', 'The voice']], b.match || '');
    end.addEventListener('change', () => run(async () => {
      if (end.value === 'babble') await speak(b);
      else if (end.value === 'voice') { ctx.pushUndo('Match bubble to the voice'); matchVoice(b); }
      else { ctx.pushUndo('Bubble timing'); delete b.match; delete b.babble; ctx.changed(); }
    }));
    const color = select('Colour', [['mustard', 'Mustard'], ['ink', 'Ink']], b.fill); color.addEventListener('change', () => set('fill', color.value));
    const pop = select('Pop', [['soft', 'Soft'], ['bouncy', 'Bouncy'], ['snap', 'Snap']], b.pop); pop.addEventListener('change', () => set('pop', pop.value));
    const font = select('Lettering', [['', 'As designed'], ['hand', 'Handwriting'], ['chunky', 'Chunky'], ['pixel', 'Pixel'], ['term', 'Terminal']], b.font || ''); font.addEventListener('change', () => set('font', font.value || undefined));
    const check = (label, on, fn, tip) => { const c = h('input', { type: 'checkbox' }); c.checked = on; c.addEventListener('change', () => fn(c.checked)); return h('label', { class: 'row', title: tip }, c, ' ' + label); };
    const who = p.kind === 'bubble' ? select('Speaker', [['lead', ctx.castName('lead')], ...(shot().costars || []).map((_, i) => ['c' + i, ctx.castName(i)]), ['', 'Nobody (no tail)']], b.speaker ?? '') : null;
    who?.addEventListener('change', () => set('speaker', who.value || null));
    let nameIn = null;
    if (p.tab) { nameIn = h('input', { type: 'text', value: b.name ?? 'BUNNY', style: 'width:96px', 'aria-label': 'Name on the tab' }); nameIn.addEventListener('change', () => set('name', nameIn.value)); nameIn.addEventListener('keydown', e => e.stopPropagation()); }
    side.append(...[h('h4', {}, p.name), ta, h('p', { class: 'hint' }, 'Enter starts a new line. Double-click the bubble on the Stage to type there.'),
      row('Seconds', secs, 'How long it stays up, pop and exit included'), row('Ends with', end, 'Set a time, or end when the Babble line or the voice ends'), who ? row('Speaker', who, 'The tail stays on this character') : null, row('Colour', color), row('Pop', pop), row('Lettering', font),
      nameIn ? row('Name tab', nameIn) : null,
      check('Stay off the face and in the safe zone', b.snap !== false, v => set('snap', v ? undefined : false), 'Off keeps it exactly where you drop it'),
      p.kind === 'bubble' && b.speaker != null ? check('Follow the character', b.follow !== false, v => { const it = resolve(b, ctx.frame()); ctx.pushUndo('Follow'); if (v) delete b.follow; else { b.follow = false; b.x = it.x; b.y = it.y; } ctx.changed(); }, 'Off: it stays where it is, and the tail still reaches them') : null,
      p.kind === 'bubble' ? check('Words appear with the voice', !!b.sync, v => set('sync', v || undefined)) : null,
      check('Line boil', !!b.boil, v => set('boil', v || undefined), 'The outline redraws every few frames'),
      h('div', { class: 'row', style: 'margin-top:6px' }, b.babble ? null : h('button', { title: 'Also say this as Babble at this spot', onclick: () => run(() => speak(b)) }, 'Speak it'), h('button', { title: 'Remove this bubble', onclick: () => { ctx.pushUndo('Remove bubble'); B.removeBubble(shot(), b.id); sel = null; ctx.changed(); } }, 'Remove'))].filter(Boolean));
    return side;
  }
  const run = async fn => { try { await fn(); } catch (e) { toast(e.message, 5000); ctx.refresh(); } };

  // ---------------------------------------------------------------- the render: one picture for every look, held as long as it lasts
  async function bake(s, at, W, H, write, post) {
    const all = (s.bubbles || []).filter(b => !b.hidden);
    if (!all.length) return;
    await B.loadFonts();
    const keep = [ctx.scene().active, ctx.frame()], runs = [];
    try {
      ctx.showFrame(s, 0); linked();
      const from = Math.min(...all.map(b => b.f)), to = Math.min(s.length, Math.max(...all.map(b => b.f + b.len)));
      for (let f = from; f < to; f++) {
        const now = all.filter(b => f >= b.f && f < b.f + b.len);
        if (!now.length) continue;
        ctx.showFrame(s, f);
        const items = now.map(b => [resolve(b, f), f - b.f]), sig = JSON.stringify(items.map(([it, t]) => [it.preset, it.text, it.fill, it.font, it.w, +it.x.toFixed(3), +it.y.toFixed(3), it.tip && [+it.tip.x.toFixed(3), +it.tip.y.toFixed(3)], it.reveal, B.settleFrame(it, t)]));
        const last = runs[runs.length - 1];
        if (last && last.sig === sig && last.start + last.length === f) last.length++; else runs.push({ sig, start: f, length: 1, items });
      }
    } finally { ctx.showFrame(ctx.scene().shots[keep[0]], keep[1]); }
    const made = new Map();
    for (const r of runs) {
      if (!made.has(r.sig)) made.set(r.sig, await write(g => { for (const [it, t] of r.items) B.drawBubbleItem(g, W, H, it, t); }, 'bubble'));
      post.overlays.push({ path: made.get(r.sig), start: at + r.start, length: r.length });
    }
  }

  // ---------------------------------------------------------------- MCP tool "bubbles"
  const row = b => { const it = resolve(b, Math.max(ctx.frame(), b.f)); return { ...b, placed: { x: +it.x.toFixed(3), y: +it.y.toFixed(3), tip: it.tip } }; };
  async function change(b, o) {
    for (const k of ['text', 'fill', 'pop', 'font', 'w', 'name', 'boil', 'sync', 'snap', 'follow', 'speaker']) if (o[k] !== undefined) b[k] = o[k];
    if (o.preset != null) { if (!B.PRESETS[o.preset]) throw Error('No preset ' + o.preset); b.preset = o.preset; }
    if (o.frame != null && o.action !== 'add') b.f = o.frame;
    if (o.seconds != null) b.len = Math.max(2, Math.round(o.seconds * fps())); else if (o.length != null) b.len = o.length;
    if (o.seconds != null || o.length != null || o.frame != null) { if (o.action !== 'add') { delete b.match; delete b.babble; } }
    if (o.x != null || o.y != null) { const it = resolve(b, b.f); put(b, o.x ?? it.x, o.y ?? it.y); }
    ctx.changed(); await spoken(b); return row(b);
  }
  async function act(a = {}) {
    const one = () => { const b = a.id ? byId(a.id) : list()[a.index ?? list().length - 1]; if (!b) throw Error('No such bubble on this shot'); return b; };
    switch (a.action || 'list') {
      case 'presets': return { presets: Object.entries(B.PRESETS).map(([id, p]) => ({ id, name: p.name, kind: p.kind, sample: p.sample })), pops: Object.keys(B.POPS), fonts: Object.keys(B.FONTS) };
      case 'list': return { bubbles: list().map(row) };
      case 'add': return change(addAt(a.preset || 'talk', a.frame ?? ctx.frame(), { text: a.text, speaker: a.speaker }), a);
      case 'set': { const b = one(); ctx.pushUndo('Change bubble'); return change(b, a); }
      case 'match': { const b = one(); if (a.to === 'babble') await speak(b); else if (a.to === 'voice') { ctx.pushUndo('Match bubble to the voice'); matchVoice(b); } else throw Error('to must be babble or voice'); return row(b); }
      case 'remove': { const b = one(); ctx.pushUndo('Remove bubble'); B.removeBubble(shot(), b.id); if (sel === b.id) sel = null; ctx.changed(); return { bubbles: list().map(row) }; }
      case 'clear': ctx.pushUndo('Clear bubbles'); delete shot().bubbles; sel = null; ctx.changed(); return { bubbles: [] };
      default: throw Error('action must be presets, list, add, set, match, remove or clear');
    }
  }
  return { bind, draw, panel, bake, act, list, select: id => { sel = id; }, selected: () => sel, split: (id, f) => B.splitBubble(shot(), id, f), remove: id => { B.removeBubble(shot(), id); if (sel === id) sel = null; }, edit: id => { const b = byId(id); if (b) { sel = id; edit(b); } }, sync: linked };
}
