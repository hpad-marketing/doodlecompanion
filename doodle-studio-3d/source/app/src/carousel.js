// Snapshot carousels: pick still frames from any shot, order them as slides, add
// speech bubbles, and export numbered PNGs (Blender quality) for an Instagram carousel.
// Slides live in the scene file: scene.carousel = { size, slides: [{ id, shot, frame, bubbles }] }
// where shot is the shot's uid and each bubble is { assetId, text, x, y, tail } (x, y are
// fractions of the slide; assetId matches the asset library's bubbles/manifest.json).
// Bubbles are drawn over the Blender render, ink #1F1F1D at Bunny's stroke weight, mustard
// fill (never white). Until the library's SVG bubbles arrive, a built-in hand-drawn bubble
// of the same kinds is used.

export const SIZES = { '4:5': [1080, 1350], '1:1': [1080, 1080], '9:16': [1080, 1920] };
export const KINDS = { speech: 'Speech', thought: 'Thought', shout: 'Shout', whisper: 'Whisper' };
export const TAILS = { 'down-left': 'Down left', 'down-right': 'Down right', left: 'Left', right: 'Right', none: 'No tail' };
const INK = '#1F1F1D', MUSTARD = '#E0A64B';
const INK_PX_1920 = 12.73;   // Bunny's stroke at 1920 px tall

export function carouselOf(scene) {
  if (!scene.carousel) scene.carousel = { size: '4:5', slides: [] };
  return scene.carousel;
}

const uid = () => Math.random().toString(36).slice(2, 10);

// ---------------------------------------------------------------- bubble drawing
function wrap(ctx, text, maxW) {
  const words = String(text).trim().split(/\s+/).filter(Boolean);
  // 1–3 word captions stay on one line (user rule)
  if (words.length <= 3) return [words.join(' ')];
  const lines = [''];
  for (const w of words) {
    const t = lines[lines.length - 1] ? lines[lines.length - 1] + ' ' + w : w;
    if (ctx.measureText(t).width <= maxW || !lines[lines.length - 1]) lines[lines.length - 1] = t;
    else lines.push(w);
  }
  return lines;
}

// draws one bubble on a 2D canvas of size W x H
export function drawBubble(ctx, b, W, H) {
  const ink = INK_PX_1920 * H / 1920;
  const fontMax = Math.round(H * 0.034), fontMin = Math.round(H * 0.022);
  const maxW = W * 0.5;
  let size = fontMax, lines;
  // shrink to fit two lines, down to the minimum size
  for (; size >= fontMin; size -= 2) {
    ctx.font = `800 ${size}px Nunito, 'Segoe UI', system-ui, sans-serif`;
    lines = wrap(ctx, b.text || '…', maxW);
    if (lines.length <= 2 && Math.max(...lines.map(l => ctx.measureText(l).width)) <= maxW * 1.15) break;
  }
  size = Math.max(size, fontMin);
  ctx.font = `800 ${size}px Nunito, 'Segoe UI', system-ui, sans-serif`;
  lines = lines.slice(0, 2);
  const tw = Math.max(...lines.map(l => ctx.measureText(l).width)), th = lines.length * size * 1.15;
  const padX = size * 0.9, padY = size * 0.7;
  const bw = tw + padX * 2, bh = th + padY * 2;
  const cx = b.x * W, cy = b.y * H;
  const x0 = cx - bw / 2, y0 = cy - bh / 2;
  ctx.save();
  ctx.lineWidth = ink * 2;   // the fill covers the inner half, so the visible line is one ink width
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.strokeStyle = INK;
  ctx.fillStyle = MUSTARD;
  const kind = b.assetId || 'speech';
  const path = new Path2D();
  if (kind === 'shout') {
    // spiky burst
    const n = 14, rx = bw / 2 * 1.12, ry = bh / 2 * 1.25;
    for (let i = 0; i <= n * 2; i++) {
      const a = i / (n * 2) * Math.PI * 2, r = i % 2 ? 1 : 1.18;
      const px = cx + Math.cos(a) * rx * r, py = cy + Math.sin(a) * ry * r;
      i ? path.lineTo(px, py) : path.moveTo(px, py);
    }
    path.closePath();
  } else if (kind === 'thought') {
    // cloud of bumps
    const n = 10, rx = bw / 2, ry = bh / 2;
    for (let i = 0; i < n; i++) {
      const a = i / n * Math.PI * 2;
      path.moveTo(cx + Math.cos(a) * rx + bh * 0.22, cy + Math.sin(a) * ry);
      path.arc(cx + Math.cos(a) * rx, cy + Math.sin(a) * ry, bh * 0.22, 0, Math.PI * 2);
    }
    path.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  } else {
    const r = Math.min(bh / 2, size * 1.2);
    path.roundRect(x0, y0, bw, bh, r);
  }
  // tail
  const tail = b.tail || 'none';
  const tailPath = new Path2D();
  if (tail !== 'none' && kind !== 'thought') {
    const left = tail.includes('left'), down = tail.startsWith('down');
    const bx = down ? cx + (left ? -bw * 0.18 : bw * 0.18) : (left ? x0 + ink : x0 + bw - ink);
    const by = down ? y0 + bh - ink : cy;
    const w = size * 0.55;
    const tip = down ? [bx + (left ? -size * 0.6 : size * 0.6), by + size * 1.5] : [bx + (left ? -size * 1.5 : size * 1.5), by + size * 0.6];
    tailPath.moveTo(down ? bx - w : bx, down ? by : by - w);
    tailPath.lineTo(tip[0], tip[1]);
    tailPath.lineTo(down ? bx + w : bx, down ? by : by + w);
  } else if (kind === 'thought' && tail !== 'none') {
    const left = tail.includes('left');
    for (const [k, rr] of [[1, 0.28], [1.9, 0.18]]) {
      const px = cx + (left ? -1 : 1) * (bw * 0.3 + k * size * 0.5), py = y0 + bh + k * size * 0.6;
      tailPath.moveTo(px + size * rr, py);
      tailPath.arc(px, py, size * rr, 0, Math.PI * 2);
    }
  }
  // one continuous outline: stroke both, then fill both so the joint has no line
  ctx.stroke(tailPath);
  ctx.stroke(path);
  ctx.fill(tailPath);
  ctx.fill(path);
  if (kind === 'whisper') {
    ctx.setLineDash([ink * 1.6, ink * 1.4]);
    ctx.stroke(path);
    ctx.setLineDash([]);
  }
  ctx.fillStyle = INK;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  lines.forEach((l, i) => ctx.fillText(l, cx, cy + (i - (lines.length - 1) / 2) * size * 1.15));
  ctx.restore();
}

export function drawBubbles(ctx, bubbles, W, H) { for (const b of bubbles || []) drawBubble(ctx, b, W, H); }

// ---------------------------------------------------------------- panel
export function carouselPanel(ctx) {
  const { h, scene, project, frame, selectShot, goto, pushUndo, toast, api, refreshOverlay } = ctx;
  const sc = scene(), car = carouselOf(sc);
  const wrapEl = h('div', {});
  const sel = ctx.selected();
  const slideOf = id => car.slides.find(s => s.id === id);
  const shotOf = s => sc.shots.find(x => x.uid === s.shot);
  const rebuild = () => ctx.rebuild();

  wrapEl.append(h('h3', {}, 'Carousel size'), h('div', { class: 'chips' }, ...Object.keys(SIZES).map(k => h('button', {
    'aria-pressed': String(car.size === k), title: `${SIZES[k][0]}×${SIZES[k][1]}`, onclick: () => { pushUndo(); car.size = k; ctx.layout(); rebuild(); } }, k))));
  wrapEl.append(h('div', { class: 'row', style: 'margin-top:8px' },
    h('button', { class: 'primary', title: 'Add the frame under the playhead as the next slide', onclick: () => {
      pushUndo();
      const s = { id: uid(), shot: project().uid, frame: frame(), bubbles: [] };
      car.slides.push(s);
      ctx.thumbs.set(s.id, ctx.thumb());
      ctx.select(s.id);
      toast(`Slide ${car.slides.length}: ${project().code} frame ${frame()}`);
      rebuild();
    } }, '+ Snap this frame'),
    h('button', { onclick: () => exportCarousel(ctx), title: 'Render every slide in Blender and save numbered PNGs with their bubbles' }, 'Export carousel')));

  wrapEl.append(h('h3', {}, `Slides (${car.slides.length})`));
  if (!car.slides.length) wrapEl.append(h('p', { class: 'hint' }, 'Move to a frame you like in any shot and press Snap. Each snap becomes the next slide.'));
  const list = h('div', { class: 'slides' });
  car.slides.forEach((s, i) => {
    const shot = shotOf(s);
    const t = ctx.thumbs.get(s.id);
    const mv = d => { const j = i + d; if (j < 0 || j >= car.slides.length) return; pushUndo(); car.slides.splice(i, 1); car.slides.splice(j, 0, s); rebuild(); };
    list.append(h('div', { class: 'slide' + (sel === s.id ? ' on' : '') },
      h('button', { class: 'thumb', title: 'Edit this slide', onclick: () => { ctx.select(s.id); if (shot) { selectShot(sc.shots.indexOf(shot)); goto(s.frame); } rebuild(); } },
        t ? h('img', { src: t, alt: '' }) : h('span', {}, String(i + 1))),
      h('div', { class: 'meta' }, h('b', {}, `${i + 1}. ${shot ? shot.code : '(deleted shot)'}`), h('span', {}, `frame ${s.frame}${s.bubbles.length ? ` · ${s.bubbles.length} bubble${s.bubbles.length > 1 ? 's' : ''}` : ''}`)),
      h('button', { class: 'icon', title: 'Earlier', onclick: () => mv(-1) }, '↑'), h('button', { class: 'icon', title: 'Later', onclick: () => mv(1) }, '↓'),
      h('button', { class: 'icon', title: 'Remove slide', onclick: () => { pushUndo(); car.slides.splice(i, 1); rebuild(); } }, '×')));
  });
  wrapEl.append(list);

  const cur = slideOf(sel);
  if (cur) {
    const i = car.slides.indexOf(cur);
    wrapEl.append(h('h3', {}, `Bubbles on slide ${i + 1}`));
    cur.bubbles.forEach((b, k) => {
      const text = h('input', { type: 'text', value: b.text, 'aria-label': 'Bubble text', style: 'flex:1;min-width:0' });
      text.addEventListener('change', () => { pushUndo(); b.text = text.value; refreshOverlay(); });
      text.addEventListener('input', () => { b.text = text.value; refreshOverlay(); });
      const kind = h('select', { 'aria-label': 'Bubble kind' }, ...Object.entries(KINDS).map(([v, n]) => h('option', { value: v }, n)));
      kind.value = b.assetId; kind.addEventListener('change', () => { pushUndo(); b.assetId = kind.value; refreshOverlay(); });
      const tail = h('select', { 'aria-label': 'Tail' }, ...Object.entries(TAILS).map(([v, n]) => h('option', { value: v }, n)));
      tail.value = b.tail; tail.addEventListener('change', () => { pushUndo(); b.tail = tail.value; refreshOverlay(); });
      wrapEl.append(h('div', { class: 'row bubble-row' }, text, kind, tail,
        h('button', { class: 'icon', title: 'Remove bubble', onclick: () => { pushUndo(); cur.bubbles.splice(k, 1); rebuild(); } }, '×')));
    });
    wrapEl.append(h('div', { class: 'row', style: 'margin-top:6px' },
      h('button', { onclick: () => { pushUndo(); cur.bubbles.push({ assetId: 'speech', text: 'Hello!', x: cur.bubbles.length % 2 ? 0.7 : 0.3, y: 0.18, tail: cur.bubbles.length % 2 ? 'down-left' : 'down-right' }); rebuild(); } }, '+ Speech bubble')));
    wrapEl.append(h('p', { class: 'hint' }, 'Drag a bubble in the viewport to place it. Short 1–3 word lines stay on one line; longer ones wrap to two and shrink to fit.'));
  }
  return wrapEl;
}

// ---------------------------------------------------------------- export
export async function exportCarousel(ctx) {
  const sc = ctx.scene(), car = carouselOf(sc);
  if (!car.slides.length) return ctx.toast('Snap at least one frame first');
  const [width, height] = SIZES[car.size];
  const slides = [];
  for (const s of car.slides) {
    const shot = sc.shots.find(x => x.uid === s.shot);
    if (!shot) return ctx.toast('A slide points at a deleted shot. Remove it first.');
    slides.push({ code: shot.code, frame: Math.min(s.frame, shot.length - 1), shot: ctx.bridgeShot(shot) });
  }
  pendingBubbles = car.slides.map(s => JSON.parse(JSON.stringify(s.bubbles)));
  try {
    const r = await ctx.api('render-carousel', { name: sc.name, width, height, slides });
    ctx.toast(r.message || 'Carousel render started');
    ctx.poll();
  } catch (e) { ctx.toast('Carousel failed to start: ' + e.message, 5000); }
}

// once Blender has rendered the slides, draw each slide's bubbles on top and save
let pendingBubbles = null;
export async function finishCarousel(ctx, job) {
  const bubbles = pendingBubbles || [];
  pendingBubbles = null;
  if (!job.slides) return;
  let n = 0;
  for (let i = 0; i < job.slides.length; i++) {
    const file = job.slides[i];
    if (!file || !bubbles[i] || !bubbles[i].length) continue;
    const { data } = await ctx.api('read-png', { path: file });
    const img = new Image();
    img.src = 'data:image/png;base64,' + data;
    await img.decode();
    const cv = document.createElement('canvas');
    cv.width = img.naturalWidth; cv.height = img.naturalHeight;
    const g = cv.getContext('2d');
    g.drawImage(img, 0, 0);
    drawBubbles(g, bubbles[i], cv.width, cv.height);
    await ctx.api('write-png', { path: file, data: cv.toDataURL('image/png').split(',')[1] });
    n++;
  }
  ctx.toast(`Carousel saved: ${job.slides.length} PNGs${n ? `, ${n} with bubbles` : ''}, in work\\carousel\\${job.id}`, 6000);
}

// live bubble overlay over the viewport, draggable
export function bindOverlay(ctx) {
  const frameEl = document.querySelector('#frame');
  const cv = document.createElement('canvas');
  cv.id = 'bubble-layer';
  frameEl.append(cv);
  let drag = null;
  const active = () => { const s = ctx.currentSlide(); return s && ctx.tab() === 'carousel' ? s : null; };
  const draw = () => {
    const r = frameEl.getBoundingClientRect(), pr = Math.min(2, devicePixelRatio || 1);
    cv.width = Math.round(r.width * pr); cv.height = Math.round(r.height * pr);
    const g = cv.getContext('2d');
    g.clearRect(0, 0, cv.width, cv.height);
    const s = active();
    cv.style.pointerEvents = s && s.bubbles.length ? 'auto' : 'none';
    if (s) drawBubbles(g, s.bubbles, cv.width, cv.height);
  };
  const hit = e => {
    const s = active(); if (!s) return null;
    const r = cv.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    let best = null, bd = 0.12;
    for (const b of s.bubbles) { const d = Math.hypot(b.x - x, (b.y - y) * r.height / r.width); if (d < bd) { bd = d; best = b; } }
    return best && { b: best, dx: best.x - x, dy: best.y - y, r };
  };
  cv.addEventListener('pointerdown', e => {
    const hh = hit(e);
    if (!hh) { cv.style.pointerEvents = 'none'; return; }
    e.stopPropagation(); ctx.pushUndo(); drag = hh; cv.setPointerCapture(e.pointerId);
  });
  cv.addEventListener('pointermove', e => {
    if (!drag) return;
    const x = (e.clientX - drag.r.left) / drag.r.width, y = (e.clientY - drag.r.top) / drag.r.height;
    drag.b.x = Math.max(0.05, Math.min(0.95, x + drag.dx)); drag.b.y = Math.max(0.05, Math.min(0.95, y + drag.dy));
    draw();
  });
  const end = () => { drag = null; };
  cv.addEventListener('pointerup', end);
  cv.addEventListener('pointercancel', end);
  // let viewport orbiting through where there is no bubble
  frameEl.addEventListener('pointermove', e => { if (!drag && active()) cv.style.pointerEvents = hit(e) ? 'auto' : 'none'; });
  new ResizeObserver(draw).observe(frameEl);
  return draw;
}
