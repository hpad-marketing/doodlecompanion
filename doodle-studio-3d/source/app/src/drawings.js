// Drawings: imported SVGs (or lines drawn by hand) on their own layer, apart from the
// characters, as in the 2D studio. Two layers:
//   screen  sits on the frame, over everything, like the 2D Storytime cutaways. Drawn by the
//           editor into PNGs that the render lays on top (post.drawings), so what the view
//           shows is what the video shows.
//   scene   stands in the 3D world at a depth, so the character can walk in front of it or
//           behind it. Blender draws it (host/blender/lib/drawings.py).
// Both draw on stroke by stroke (build) and boil like a hand-drawn line (noise). Every line is
// one width, Bunny's ink, and only ink or mustard: never white, no fills, no boxes.
export const COLOURS = { ink: '#1F1F1D', mustard: '#E0A64B' };
export const INK_PX_1920 = 12.73;      // Bunny's line on a 1920 px tall frame (Blender's ink_px)
export const BOIL_PX_1920 = 4;         // line boil at noise 1, in px on a 1920 px tall frame
export const WAVE_PX_1920 = 140;       // the boil's wave length along the line, same units
const MAX_STROKES = 400, MAX_POINTS = 6000;

// ---------------------------------------------------------------- SVG -> strokes
// Every visible shape becomes ink lines: stroked paths become their line, filled shapes their
// outline. Text, images and fills are left out (convert text to outlines first).
// Returns { strokes: [[[x, y], ...], ...] in a 0..1 box (y down), aspect: width / height }.
export function parseSvg(text, doc = globalThis.document) {
  const src = new DOMParser().parseFromString(String(text || ''), 'image/svg+xml');
  const root = src.documentElement;
  if (!root || root.nodeName.toLowerCase() !== 'svg' || src.querySelector('parsererror')) throw Error('That file is not an SVG');
  // measure in a hidden live SVG, so transforms, arcs and curves are the browser's own
  const host = doc.createElement('div');
  host.style.cssText = 'position:fixed;left:-99999px;top:0;width:10px;height:10px;overflow:hidden;visibility:hidden';
  const svg = doc.importNode(root, true);
  for (const s of svg.querySelectorAll('script,foreignObject')) s.remove();
  host.append(svg); doc.body.append(host);
  try {
    const geo = [...svg.querySelectorAll('path,line,polyline,polygon,rect,circle,ellipse')].filter(el => !el.closest('defs,clipPath,mask,marker,pattern,symbol') && visible(el));
    const raw = [];
    const lens = geo.map(el => { try { return el.getTotalLength(); } catch { return 0; } });
    const big = Math.max(1e-6, ...lens);
    for (const [i, el] of geo.entries()) {
      const L = lens[i];
      if (!(L > 0)) continue;
      const m = el.getCTM() || svg.createSVGMatrix();
      const step = Math.max(L / 600, big / 900);
      let cur = [], last = null;
      for (let s = 0; s <= L + step * 0.5; s += step) {
        const p = el.getPointAtLength(Math.min(s, L)), q = [m.a * p.x + m.c * p.y + m.e, m.b * p.x + m.d * p.y + m.f];
        // a jump much longer than the step is a move to a new subpath: start a new stroke
        if (last && Math.hypot(q[0] - last[0], q[1] - last[1]) > step * 4 * Math.hypot(m.a, m.b) + 1e-9) { if (cur.length > 1) raw.push(cur); cur = []; }
        cur.push(q); last = q;
      }
      if (cur.length > 1) raw.push(cur);
    }
    if (!raw.length) throw Error('No lines found in that SVG (text and images are left out: convert text to outlines)');
    return normalise(raw);
  } finally { host.remove(); }
}
function visible(el) {
  for (let e = el; e && e.nodeType === 1; e = e.parentNode) {
    if (e.getAttribute('display') === 'none' || e.getAttribute('visibility') === 'hidden' || /display\s*:\s*none/.test(e.getAttribute('style') || '')) return false;
  }
  const cs = getComputedStyle(el);
  return !(cs.fill === 'none' && cs.stroke === 'none');
}

// any strokes (any units) -> a 0..1 box, simplified and capped
export function normalise(raw) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const s of raw) for (const [x, y] of s) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  const w = Math.max(1e-6, x1 - x0), h = Math.max(1e-6, y1 - y0), k = Math.max(w, h);
  let strokes = raw.map(s => simplify(s.map(([x, y]) => [(x - x0) / k, (y - y0) / k]), 0.0015)).filter(s => s.length > 1 && strokeLen(s) > 0.004);
  // biggest strokes first when there are too many
  if (strokes.length > MAX_STROKES) strokes = strokes.map((s, i) => [s, i, strokeLen(s)]).sort((a, b) => b[2] - a[2]).slice(0, MAX_STROKES).sort((a, b) => a[1] - b[1]).map(a => a[0]);
  let n = strokes.reduce((a, s) => a + s.length, 0);
  for (let tol = 0.003; n > MAX_POINTS && tol < 0.05; tol *= 1.6) { strokes = strokes.map(s => simplify(s, tol)); n = strokes.reduce((a, s) => a + s.length, 0); }
  // into a 0..1 box on both sides (y down), keeping the shape through aspect
  const sx = k / w, sy = k / h;
  return { strokes: strokes.map(s => s.map(([x, y]) => [+(x * sx).toFixed(4), +(y * sy).toFixed(4)])), aspect: +(w / h).toFixed(4) };
}
const strokeLen = s => { let L = 0; for (let i = 1; i < s.length; i++) L += Math.hypot(s[i][0] - s[i - 1][0], s[i][1] - s[i - 1][1]); return L; };
// Ramer-Douglas-Peucker
function simplify(pts, tol) {
  if (pts.length < 3) return pts;
  const keep = new Uint8Array(pts.length); keep[0] = keep[pts.length - 1] = 1;
  const stack = [[0, pts.length - 1]];
  while (stack.length) {
    const [a, b] = stack.pop(); let best = -1, bi = -1;
    const [ax, ay] = pts[a], [bx, by] = pts[b], dx = bx - ax, dy = by - ay, L = Math.hypot(dx, dy);
    for (let i = a + 1; i < b; i++) { const d = L > 1e-6 ? Math.abs((pts[i][0] - ax) * dy - (pts[i][1] - ay) * dx) / L : Math.hypot(pts[i][0] - ax, pts[i][1] - ay); if (d > best) { best = d; bi = i; } }
    if (best > tol) { keep[bi] = 1; stack.push([a, bi], [bi, b]); }
  }
  return pts.filter((_, i) => keep[i]);
}

// ---------------------------------------------------------------- the layer on a shot
let seq = 0;
const uid = () => 'dr' + Date.now().toString(36) + (seq++).toString(36);
export const drawingsOf = p => p.drawings || [];
export function add(p, art, o = {}) {
  if (!art?.strokes?.length) throw Error('Nothing to draw');
  const d = {
    id: uid(), name: String(o.name || 'Drawing').slice(0, 60), strokes: art.strokes, aspect: art.aspect || 1,
    layer: o.layer === 'scene' ? 'scene' : 'screen',
    x: o.x ?? 0.5, y: o.y ?? 0.3, size: o.size ?? 0.3, rot: o.rot ?? 0,
    frame: Math.max(0, Math.round(o.frame ?? 0)), build: Math.max(0, Math.round(o.build ?? 18)), until: o.until ?? null,
    noise: clamp01(o.noise ?? 0.5), boil: Math.max(1, Math.round(o.boil ?? 2)), colour: COLOURS[o.colour] ? o.colour : 'ink',
  };
  if (d.layer === 'scene') d.depth = +(o.depth ?? 1);
  (p.drawings ||= []).push(d);
  return d;
}
const clamp01 = v => Math.max(0, Math.min(1, +v || 0));
// change what can be changed; returns the drawing
export function set(p, index, o = {}) {
  const d = drawingsOf(p)[index];
  if (!d) throw Error(`No drawing ${index} on this shot (it has ${drawingsOf(p).length})`);
  if (o.name != null) d.name = String(o.name).slice(0, 60);
  if (o.layer != null) { d.layer = o.layer === 'scene' ? 'scene' : 'screen'; if (d.layer === 'scene') d.depth ??= 1; else { delete d.world; delete d.depth; } }
  for (const k of ['x', 'y', 'size', 'rot', 'depth']) if (o[k] != null && Number.isFinite(+o[k])) d[k] = +o[k];
  d.size = Math.max(0.02, Math.min(3, d.size));
  if (o.frame != null) d.frame = Math.max(0, Math.round(+o.frame));
  if (o.build != null) d.build = Math.max(0, Math.round(+o.build));
  if (o.until !== undefined) d.until = o.until == null || o.until === '' ? null : Math.max(d.frame + 1, Math.round(+o.until));
  if (o.noise != null) d.noise = clamp01(o.noise);
  if (o.boil != null) d.boil = Math.max(1, Math.min(12, Math.round(+o.boil)));
  if (o.colour != null) { if (!COLOURS[o.colour]) throw Error('colour must be ink or mustard (brand colours only)'); d.colour = o.colour; }
  return d;
}
export function remove(p, index) {
  const a = drawingsOf(p);
  if (!a[index]) throw Error(`No drawing ${index} on this shot`);
  a.splice(index, 1);
  if (!a.length) delete p.drawings;
}
// a scene drawing stands where the camera saw it: centre, facing the camera, size in metres
// view: { unproject(x, y, depth) -> [x, y, z], camera (THREE) }
export function place(d, view) {
  if (d.layer !== 'scene') return d;
  const c = view.unproject(d.x, d.y, d.depth ?? 1), top = view.unproject(d.x, d.y - d.size / 2, d.depth ?? 1), bot = view.unproject(d.x, d.y + d.size / 2, d.depth ?? 1);
  if (!c || !top || !bot) throw Error('The camera does not see that depth: try a smaller depth');
  const e = view.camera.matrixWorld.elements;
  const r = [e[0], e[1], e[2]], u = [e[4], e[5], e[6]], n = v => { const l = Math.hypot(...v) || 1; return v.map(x => +(x / l).toFixed(5)); };
  d.world = { at: c, r: n(r), u: n(u), h: +Math.hypot(top[0] - bot[0], top[1] - bot[1], top[2] - bot[2]).toFixed(4) };
  return d;
}

// ---------------------------------------------------------------- timing and boil
// what part shows at frame t: null (not yet / gone), else { p: drawn fraction 0..1, v: boil variant 0..2 }
export function stateAt(d, t) {
  if (d.hidden || t < d.frame || (d.until != null && t >= d.until)) return null;
  const p = d.build > 0 ? Math.min(1, (t - d.frame + 1) / d.build) : 1;
  return { p, v: d.noise > 0 ? Math.floor((t - d.frame) / Math.max(1, d.boil)) % 3 : 0 };
}
// strokes in local units (height 1, centred, y up), turned by rot
export function local(d) {
  const a = (d.rot || 0) * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), k = d.aspect || 1;
  return densify(d.strokes.map(st => st.map(([x, y]) => { const lx = (x - 0.5) * k, ly = 0.5 - y; return [lx * c - ly * s, lx * s + ly * c]; })));
}
// long straight runs get in-between points, so the boil bends them like a hand-drawn line
export function densify(strokes, step = 0.01) {
  return strokes.map(s => {
    const out = [s[0]];
    for (let j = 1; j < s.length; j++) {
      const [ax, ay] = s[j - 1], [bx, by] = s[j], n = Math.min(200, Math.floor(Math.hypot(bx - ax, by - ay) / step));
      for (let k = 1; k <= n; k++) out.push([ax + (bx - ax) * k / (n + 1), ay + (by - ay) * k / (n + 1)]);
      out.push(s[j]);
    }
    return out;
  });
}
// the drawn part of each stroke for fraction p (strokes draw one after another, at even speed)
export function partial(strokes, p) {
  if (p >= 1) return strokes;
  const lens = strokes.map(strokeLen), total = lens.reduce((a, b) => a + b, 0);
  let left = total * p; const out = [];
  for (const [i, s] of strokes.entries()) {
    if (left <= 0) break;
    if (lens[i] <= left) { out.push(s); left -= lens[i]; continue; }
    const part = [s[0]];
    for (let j = 1; j < s.length && left > 0; j++) {
      const L = Math.hypot(s[j][0] - s[j - 1][0], s[j][1] - s[j - 1][1]);
      if (L <= left) { part.push(s[j]); left -= L; }
      else { const f = left / L; part.push([s[j - 1][0] + (s[j][0] - s[j - 1][0]) * f, s[j - 1][1] + (s[j][1] - s[j - 1][1]) * f]); left = 0; }
    }
    if (part.length > 1) out.push(part);
    break;
  }
  return out;
}
// a smooth hand-drawn wobble: low-frequency waves along the line, a fresh set per variant.
// amp is in the same units as the points; it bends the line, never breaks it.
export function boil(strokes, v, amp, seed = 1, wave = amp * 30) {
  if (!(amp > 0)) return strokes;
  return strokes.map((s, i) => {
    const r = k => { const x = Math.sin((seed * 97.13 + i * 13.7 + v * 41.9 + k * 7.31)) * 43758.5453; return x - Math.floor(x); };
    const f1 = 3 + r(1) * 3, f2 = 2 + r(2) * 3, p1 = r(3) * 6.283, p2 = r(4) * 6.283, ox = (r(5) - 0.5) * 0.6, oy = (r(6) - 0.5) * 0.6;
    let acc = 0;
    return s.map((pt, j) => {
      if (j) acc += Math.hypot(pt[0] - s[j - 1][0], pt[1] - s[j - 1][1]);
      const u = acc / Math.max(1e-9, wave);
      return [pt[0] + amp * (Math.sin(u * f1 + p1) * 0.7 + ox), pt[1] + amp * (Math.cos(u * f2 + p2) * 0.7 + oy)];
    });
  });
}
export const hash = s => { let h = 7; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) % 100003; return h; };

// ---------------------------------------------------------------- the screen layer
// draws every screen drawing of shot p at frame t onto a W x H canvas; ink = line width in px
export function drawScreen(g, W, H, p, t, inkPx) {
  let n = 0;
  for (const d of drawingsOf(p)) {
    if (d.layer !== 'screen') continue;
    const st = stateAt(d, t);
    if (!st) continue;
    const S = d.size * H, cx = d.x * W, cy = d.y * H, L = Math.max(W, H);
    let pts = partial(local(d), st.p).map(s => s.map(([x, y]) => [cx + x * S, cy - y * S]));
    pts = boil(pts, st.v, d.noise * BOIL_PX_1920 * L / 1920, hash(d.id), WAVE_PX_1920 * L / 1920);
    g.save(); g.strokeStyle = COLOURS[d.colour] || COLOURS.ink; g.lineWidth = inkPx; g.lineCap = g.lineJoin = 'round';
    g.beginPath();
    for (const s of pts) { g.moveTo(s[0][0], s[0][1]); for (let j = 1; j < s.length; j++) g.lineTo(s[j][0], s[j][1]); }
    g.stroke(); g.restore(); n++;
  }
  return n;
}
// a key for what the screen layer looks like at t, so equal frames share one PNG
export function screenSig(p, t) {
  const parts = [];
  for (const d of drawingsOf(p)) {
    if (d.layer !== 'screen') continue;
    const st = stateAt(d, t);
    if (st) parts.push(`${d.id}:${st.p < 1 ? st.p.toFixed(4) : 1}:${st.v}`);
  }
  return parts.join('|');
}
// the screen layer as runs of equal frames: [{ sig, start, length, t }]
export function screenRuns(p, length) {
  const runs = [];
  for (let t = 0; t < length; t++) {
    const sig = screenSig(p, t), last = runs[runs.length - 1];
    if (!sig) continue;
    if (last && last.sig === sig && last.start + last.length === t) last.length++;
    else runs.push({ sig, start: t, length: 1, t });
  }
  return runs;
}
// what Blender gets: scene drawings only, placed in the world
export function forBridge(p) {
  const a = drawingsOf(p).filter(d => d.layer === 'scene' && d.world && !d.hidden).map(d => ({ id: d.id, strokes: d.strokes, aspect: d.aspect, rot: d.rot || 0, world: d.world, frame: d.frame, build: d.build, until: d.until, noise: d.noise, boil: d.boil, colour: d.colour }));
  return a.length ? a : null;
}
// a small picture of a drawing for lists (data URL), in its own colour on the background
export function thumb(d, size = 64, doc = globalThis.document) {
  const c = doc.createElement('canvas'); c.width = c.height = size;
  const g = c.getContext('2d');
  g.fillStyle = d.colour === 'mustard' ? COLOURS.ink : COLOURS.mustard; g.fillRect(0, 0, size, size);
  const k = (size - 8) / Math.max(1, d.aspect || 1), w = k * (d.aspect || 1);
  g.strokeStyle = COLOURS[d.colour] || COLOURS.ink; g.lineWidth = 1.6; g.lineCap = g.lineJoin = 'round'; g.beginPath();
  for (const s of d.strokes) { s.forEach(([x, y], j) => (j ? g.lineTo : g.moveTo).call(g, (size - w) / 2 + x * w, (size - k) / 2 + y * k)); }
  g.stroke();
  return c.toDataURL('image/png');
}
