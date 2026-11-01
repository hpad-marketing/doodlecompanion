// Speech bubbles: talk and thought bubbles, onomatopoeia bursts and a retro dialogue box for
// subtitles. Everything is drawn from the text at the frame it is needed, on a 2D canvas, so the
// Stage, the library previews and the render share one drawing. Brand colours, Bunny's one line
// weight, no shadows, no boxes or frames except the dialogue box itself.
//   it = { preset, text, x, y, tip: { x, y } | null, fill: 'mustard' | 'ink', pop, len, fps, name, font }
// x, y and tip are 0..1 of the frame. f counts frames from the bubble's first frame.
export const INK = '#1F1F1D', MUSTARD = '#E0A64B';
export const inkPx = (W, H) => Math.max(3, Math.round(10.5 * Math.min(W, H) / 1080));   // Bunny's line weight
export const FONTS = {
  hand: '"Patrick Hand", "Nirmala UI", "Noto Sans Devanagari", "Segoe Print", system-ui, sans-serif',
  chunky: '"Luckiest Guy", "Patrick Hand", "Nirmala UI", system-ui, sans-serif',
  pixel: '"Pixelify Sans", "Patrick Hand", "Nirmala UI", monospace',
  term: '"VT323", "Patrick Hand", "Nirmala UI", monospace'
};
export const SAFE = { top: 0.14, bottom: 0.8, side: 0.06, gap: 0.012 };   // the same Instagram zone as captions

export const PRESETS = {
  talk: { kind: 'bubble', name: 'Talk', font: 'hand', sample: 'Hello there!' },
  whisper: { kind: 'bubble', name: 'Whisper', font: 'hand', sample: 'psst, over here', small: 0.82 },
  think: { kind: 'bubble', name: 'Think', font: 'hand', sample: 'What if I just left?' },
  surprise: { kind: 'bubble', name: 'Surprise', font: 'hand', sample: 'WHAT?!', big: 1.2 },
  shaky: { kind: 'bubble', name: 'Shaky', font: 'hand', sample: 'I am totally fine.' },
  star: { kind: 'burst', name: 'Star burst', font: 'chunky', sample: 'BANG!', small: 0.72 },
  slam: { kind: 'burst', name: 'Letter slam', font: 'chunky', sample: 'BOOM' },
  boing: { kind: 'burst', name: 'Boing', font: 'chunky', sample: 'BOING' },
  zoom: { kind: 'burst', name: 'Zoom', font: 'chunky', sample: 'ZOOM' },
  splat: { kind: 'burst', name: 'Splat', font: 'chunky', sample: 'SPLAT', small: 0.78 },
  drift: { kind: 'burst', name: 'Drift', font: 'hand', sample: 'zzz', small: 0.6 },
  stepped: { kind: 'box', name: 'Stepped box', font: 'pixel', fill: 'ink', sample: 'You found a carrot. It looks at you. You look at it.' },
  tabbed: { kind: 'box', name: 'Name tab box', font: 'pixel', sample: 'Nobody told me there would be stairs.', tab: true },
  doodlebox: { kind: 'box', name: 'Doodle box', font: 'hand', sample: 'And that was the last normal day.' }
};
export const POPS = { soft: { n: 9, over: 1.7 }, bouncy: { n: 14, over: 3.4 }, snap: { n: 5, over: 1.2 } };
const OUT = 5;   // frames to shrink away

const hash = s => { let h = 2166136261; for (const c of String(s)) h = Math.imul(h ^ c.codePointAt(0), 16777619); return h >>> 0; };
const rng = seed => () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const backOut = (t, c) => 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const letters = text => (typeof Intl !== 'undefined' && Intl.Segmenter ? [...new Intl.Segmenter().segment(text)].map(s => s.segment) : Array.from(text));

function wrap(g, text, maxW) {
  const out = [];
  for (const para of String(text).split('\n')) {
    let line = '';
    for (const w of para.split(/\s+/).filter(Boolean)) {
      const next = line ? line + ' ' + w : w;
      if (line && g.measureText(next).width > maxW) { out.push(line); line = w; } else line = next;
    }
    out.push(line);
  }
  return out;
}
// the bubble grows to the text; text that will not fit in the zone shrinks until it does
export function layout(g, it, W, H) {
  const p = PRESETS[it.preset] || PRESETS.talk, font = FONTS[it.font] || FONTS[p.font], text = it.text || '';
  const base = (p.kind === 'burst' ? 0.085 : p.kind === 'box' ? 0.034 : 0.038) * H * (p.small || 1) * (p.big || 1);
  // it.w: the text width the user pulled the bubble to; the height follows the text
  const pulled = p.kind === 'bubble' && it.w, maxW = (pulled ? clamp(it.w, 0.14, 0.76) : p.kind === 'box' ? 0.86 : p.kind === 'burst' ? 0.74 : 0.6) * W, maxLines = pulled ? 8 : p.kind === 'box' ? 3 : p.kind === 'burst' ? 2 : 4;
  let size = base, lines = [];
  for (; size > base * 0.4; size *= 0.94) {
    g.font = `${size}px ${font}`;
    lines = wrap(g, text, maxW - (p.kind === 'box' ? size * 1.6 : 0));
    if (lines.length <= maxLines && Math.max(...lines.map(l => g.measureText(l).width)) <= maxW) break;
  }
  g.font = `${size}px ${font}`;
  const tw = Math.max(1, ...lines.map(l => g.measureText(l).width)), lead = size * 1.12, th = lines.length * lead;
  let rx, ry;
  if (p.kind === 'box') { rx = 0.44 * W; ry = (Math.max(2, lines.length) * lead + size * 1.5) / 2; }
  else if (p.kind === 'burst') { rx = tw / 2 + size * 0.5; ry = th / 2 + size * 0.42; }
  else { rx = Math.max(tw / 2 + size * 1.05, size * 2.4); ry = Math.max(th / 2 + size * 0.85, size * 1.5); }
  return { p, font, size, lines, tw, th, lead, rx, ry };
}
// half size of the finished bubble as a fraction of the frame, with its spikes, for placement
export function extent(g, it, W, H) {
  const L = layout(g, it, W, H), k = it.preset === 'star' ? 1.62 : it.preset === 'surprise' ? 1.34 : it.preset === 'think' ? 1.2 : it.preset === 'splat' ? 1.5 : PRESETS[it.preset]?.kind === 'box' ? 1 : 1.06;
  return { hw: L.rx * k / W, hh: L.ry * k / H };
}
const hit = (r, x, y, hw, hh, gap) => x + hw + gap > r.x0 && x - hw - gap < r.x1 && y + hh + gap > r.y0 && y - hh - gap < r.y1;
// keeps a bubble in the zone and off the eyes and mouth. faces: [{ x0, y0, x1, y1 }] from the camera.
export function place(g, it, W, H, faces = []) {
  const area = (x, y, hw, hh) => faces.reduce((a, r) => a + Math.max(0, Math.min(x + hw, r.x1) - Math.max(x - hw, r.x0)) * Math.max(0, Math.min(y + hh, r.y1) - Math.max(y - hh, r.y0)), 0);
  const widths = it.w ? [1, 1.3, 1.7, 2.2, 3].map(k => Math.min(0.76, it.w * k)) : [it.w];   // a bubble with no room gets wider and so shorter
  let least = null;
  for (const w of widths) {
    const { hw, hh } = extent(g, { ...it, w }, W, H), x0 = SAFE.side + hw, x1 = 1 - x0, y0 = SAFE.top + hh, y1 = SAFE.bottom - hh;
    const kx = v => clamp(v, Math.min(x0, x1), Math.max(x0, x1)), ky = v => clamp(v, Math.min(y0, y1), Math.max(y0, y1)), clear = (x, y) => !faces.some(q => hit(q, x, y, hw, hh, SAFE.gap));
    const out = (x, y) => (w == null ? { x, y } : { x, y, w }), x = kx(it.x), y = ky(it.y);
    if (clear(x, y)) return out(x, y);
    let best = null, bestD = Infinity;
    for (let i = 0; i <= 12; i++) for (let j = 0; j <= 20; j++) {
      const a = kx(x0 + (x1 - x0) * i / 12), b = ky(y0 + (y1 - y0) * j / 20), d = Math.hypot(a - it.x, b - it.y), o = area(a, b, hw, hh);
      if (clear(a, b) && d < bestD) { bestD = d; best = [a, b]; }
      if (!least || o < least.o - 1e-6 || (Math.abs(o - least.o) <= 1e-6 && d < least.d)) least = { o, d, at: out(a, b) };
    }
    if (best) return out(best[0], best[1]);
  }
  return least.at;
}

function ringAt(a, rx, ry, e, wob) {
  const c = Math.cos(a), s = Math.sin(a), r = 1 + wob(a);
  return [Math.sign(c) * Math.abs(c) ** (2 / e) * rx * r, Math.sign(s) * Math.abs(s) ** (2 / e) * ry * r];
}
function wobbler(r, amt, wave = 0, phase = 0) {
  const p = [r() * 6.3, r() * 6.3, r() * 6.3];
  return a => amt * (Math.sin(a * 2 + p[0]) * 0.5 + Math.sin(a * 3 + p[1]) * 0.35 + Math.sin(a * 5 + p[2]) * 0.15) + wave * Math.sin(a * 13 + phase);
}
// a closed hand-drawn outline, with the tail growing out of it toward `tip`
function blobPath(g, rx, ry, e, wob, tip, baseW) {
  const n = 72, a0 = tip ? Math.atan2(tip[1], tip[0]) : 0, db = tip ? Math.min(0.5, baseW / Math.max(rx, ry) * 0.9) : 0, span = Math.PI * 2 - db * 2;
  const pts = [];
  for (let i = 0; i <= n; i++) pts.push(ringAt(a0 + db + span * i / n, rx, ry, e, wob));
  g.beginPath(); g.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length - 1; i++) g.quadraticCurveTo(pts[i][0], pts[i][1], (pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2);
  g.lineTo(pts[n][0], pts[n][1]);
  if (tip) {
    const end = pts[n], start = pts[0], bend = (b, k) => [(b[0] + tip[0]) / 2 + (b[1] - tip[1]) * k, (b[1] + tip[1]) / 2 - (b[0] - tip[0]) * k];
    const c1 = bend(end, 0.1), c2 = bend(start, 0.1);
    g.quadraticCurveTo(c1[0], c1[1], tip[0], tip[1]); g.quadraticCurveTo(c2[0], c2[1], start[0], start[1]);
  }
  g.closePath();
}
function spikePath(g, rx, ry, out, inn, n, r, tip) {
  const pts = [], at = tip ? Math.atan2(tip[1], tip[0]) : null;
  let best = -1, bestD = 9;
  for (let i = 0; i < n * 2; i++) {
    const a = i / (n * 2) * Math.PI * 2 + 0.2, k = i % 2 ? inn : out + (r() - 0.5) * 0.14;
    pts.push([Math.cos(a) * rx * k, Math.sin(a) * ry * k]);
    if (tip && !(i % 2)) { const d = Math.abs(Math.atan2(Math.sin(a - at), Math.cos(a - at))); if (d < bestD) { bestD = d; best = i; } }
  }
  if (tip) pts[best] = tip;
  g.beginPath(); pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.closePath();
}
function cloudPath(g, rx, ry, size) {
  const n = Math.max(8, Math.round((rx + ry) * 3.1 / (size * 1.5))), pts = [];
  for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2; pts.push([Math.cos(a) * rx, Math.sin(a) * ry]); }
  g.beginPath(); g.moveTo(pts[0][0], pts[0][1]);
  for (let i = 0; i < n; i++) {
    const p = pts[i], q = pts[(i + 1) % n], mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2, l = Math.hypot(mx / rx, my / ry) || 1;
    g.quadraticCurveTo(mx / l * 1.26, my / l * 1.26, q[0], q[1]);
  }
  g.closePath();
}
function steppedPath(g, hw, hh, st, steps) {
  const c = []; // the top right corner, walked as stairs, then mirrored round
  for (let i = 0; i < steps; i++) { c.push([hw - st * (steps - i), -hh + st * i], [hw - st * (steps - i - 1), -hh + st * i]); c.push([hw - st * (steps - i - 1), -hh + st * (i + 1)]); }
  const tr = [...new Set(c.map(String))].map(s => s.split(',').map(Number));
  const br = tr.map(([x, y]) => [x, -y]).reverse(), bl = tr.map(([x, y]) => [-x, -y]), tl = br.map(([x, y]) => [-x, -y]);
  const all = [...tr, ...br, ...bl, ...tl];
  g.beginPath(); all.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.closePath();
}
function outlined(g, s, x, y, lw, fill, line) {
  g.lineWidth = lw * 2; g.strokeStyle = line; g.strokeText(s, x, y);   // half hides under the fill, so the line reads as one weight
  g.fillStyle = fill; g.fillText(s, x, y);
}

function drawLetters(g, L, it, f, c, W, H, lw) {
  const n = POPS[it.pop] || POPS.soft, mode = it.preset, text = L.lines.join(' ');
  g.textAlign = 'center'; g.textBaseline = 'middle'; g.font = `${L.size}px ${L.font}`;
  const r = rng(hash(text + mode)), rows = L.lines.map(l => letters(l));
  rows.forEach((row, ri) => {
    const wid = row.map(s => g.measureText(s).width), total = wid.reduce((a, b) => a + b, 0);
    let x = -total / 2;
    const y0 = (ri - (rows.length - 1) / 2) * L.lead;
    row.forEach((s, i) => {
      const w = wid[i], cx = x + w / 2; x += w;
      const tilt = (r() - 0.5) * 0.2, tiltY = (r() - 0.5) * L.size * 0.1;
      if (s === ' ') return;
      let sc = 1, dx = 0, dy = tiltY, rot = tilt;
      if (mode === 'slam') { const t = clamp((f - i * 2) / n.n, 0, 1); sc = t <= 0 ? 0 : 0.2 + 0.8 * backOut(t, n.over + 1); }
      else if (mode === 'boing') { const u = Math.max(0, f - i * 2); sc = f - i * 2 < 0 ? 0 : 0.2 + 0.8 * backOut(clamp(u / n.n, 0, 1), n.over); dy -= L.size * 0.55 * Math.exp(-u / 14) * Math.abs(Math.sin(u / 2.6)); rot = tilt * 0.5; }
      else if (mode === 'drift') { const u = f - i * 5; sc = (u < 0 ? 0 : 0.2 + 0.8 * backOut(clamp(u / n.n, 0, 1), n.over)) * (0.75 + i * 0.25); dy = -i * L.size * 0.55 - Math.max(0, u) * L.size * 0.012 + Math.sin(u / 7 + i) * L.size * 0.1; dx = i * L.size * 0.16; }
      if (sc <= 0) return;
      g.save(); g.translate(cx + dx, y0 + dy); g.rotate(rot); g.scale(sc, sc);
      if (mode === 'star' || mode === 'splat') { g.fillStyle = c.text; g.fillText(s, 0, 0); }
      else outlined(g, s, 0, 0, lw, MUSTARD, INK);
      g.restore();
    });
  });
}

function drawBubbleShape(g, L, it, f, c, W, H, lw, tip) {
  const r = rng(hash(it.preset + (it.text || '') + (it.boil ? Math.floor(f / 4) : ''))), { size, rx, ry } = L, m = it.preset;
  g.lineJoin = 'round'; g.lineCap = 'round'; g.lineWidth = lw; g.strokeStyle = c.line; g.fillStyle = c.fill;
  const tail = tip && Math.hypot(tip[0] / rx, tip[1] / ry) > 1.12 ? tip : null;
  if (m === 'surprise') spikePath(g, rx, ry, 1.34, 1.03, Math.max(11, Math.round((rx + ry) / size * 1.5)), r, tail);
  else if (m === 'think') {
    if (tail) {
      const d = Math.hypot(tail[0], tail[1]), ux = tail[0] / d, uy = tail[1] / d, edge = Math.hypot(ux * rx, uy * ry) * 1.14;
      [[0.2, 0.26], [0.55, 0.18], [0.92, 0.11]].forEach(([t, s]) => { const k = edge + (d - edge) * t; g.beginPath(); g.arc(ux * k, uy * k, size * s * 1.3, 0, Math.PI * 2); g.fill(); g.stroke(); });
    }
    cloudPath(g, rx, ry, size);
  } else {
    const wob = wobbler(r, m === 'shaky' ? 0.012 : 0.02, m === 'shaky' ? 0.03 : 0, Math.floor(f / 2) * 2.4);
    blobPath(g, rx, ry, 2.4, wob, tail, size * 0.85);
    if (m === 'whisper') g.setLineDash([lw * 0.2, lw * 2.2]);
  }
  g.fill(); g.stroke(); g.setLineDash([]);
}
function drawBurstShape(g, L, it, f, c, lw) {
  const r = rng(hash(it.preset + (it.text || '') + (it.boil ? Math.floor(f / 4) : ''))), { size, rx, ry } = L;
  g.lineJoin = 'round'; g.lineCap = 'round'; g.lineWidth = lw; g.strokeStyle = c.line; g.fillStyle = c.fill;
  if (it.preset === 'star') {
    const n = 12, grow = clamp((f - 4) / 8, 0, 1), fade = clamp(1.5 - f / 16, 0, 1);   // action lines fly off and stop
    if (grow && fade) for (let i = 0; i < n; i++) {
      const a = (i + 0.5) / n * Math.PI * 2 + 0.2, a0 = 1.5 + grow * 0.2, a1 = a0 + (0.2 + 0.25 * (i % 2)) * fade;
      g.beginPath(); g.moveTo(Math.cos(a) * rx * a0, Math.sin(a) * ry * a0); g.lineTo(Math.cos(a) * rx * a1, Math.sin(a) * ry * a1); g.stroke();
    }
    spikePath(g, rx, ry, 1.55, 1.08, n, r, null); g.fill(); g.stroke();
  } else if (it.preset === 'splat') {
    const p = [r() * 6, r() * 6, r() * 6], wob = a => 0.14 * Math.sin(a * 3 + p[0]) + 0.1 * Math.sin(a * 5 + p[1]) + 0.05 * Math.sin(a * 9 + p[2]);
    blobPath(g, rx * 1.2, ry * 1.25, 2, wob, null, 0); g.fill(); g.stroke();
    for (let i = 0; i < 5; i++) { const a = r() * 6.3, k = 1.5 + r() * 0.3, s = size * (0.06 + r() * 0.08); g.beginPath(); g.arc(Math.cos(a) * rx * k, Math.sin(a) * ry * k, s, 0, Math.PI * 2); g.fill(); g.stroke(); }
  }
}
function drawBox(g, L, it, f, c, lw, H, fps) {
  const { size, rx: hw, ry: hh, lines, lead, font, p } = L, n = POPS[it.pop] || POPS.soft;
  // the window opens as a line across, then drops open with the overshoot
  const across = clamp(f / 4, 0, 1), down = f < 4 ? 0.06 : 0.06 + 0.94 * backOut(clamp((f - 4) / n.n, 0, 1), n.over), left = it.len ? it.len - f : 99;
  const sy = left < OUT ? Math.max(0.02, left / OUT) : down;
  g.save(); g.scale(left < OUT ? 1 : 0.1 + 0.9 * across, sy);
  g.lineJoin = it.preset === 'doodlebox' ? 'round' : 'miter'; g.lineCap = 'round'; g.lineWidth = lw; g.strokeStyle = c.line; g.fillStyle = c.fill;
  if (it.preset === 'doodlebox') blobPath(g, hw, hh, 7, wobbler(rng(hash(it.text || '')), 0.006), null, 0);
  else steppedPath(g, hw, hh, size * 0.36, it.preset === 'stepped' ? 2 : 1);
  g.fill(); g.stroke();
  if (p.tab && it.name !== '') {
    g.font = `${size * 0.72}px ${font}`;
    const label = it.name || 'BUNNY', w = g.measureText(label).width / 2 + size * 0.5, h = size * 0.56, x = -hw + w + size * 0.7, y = -hh;
    g.save(); g.translate(x, y); steppedPath(g, w, h, size * 0.2, 1); g.fillStyle = c.fill2; g.strokeStyle = c.line2; g.fill(); g.stroke();
    g.fillStyle = c.text2; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(label, 0, size * 0.03); g.restore();
  }
  g.restore();
  if (f < 4 + n.n * 0.5 || left < OUT) return;
  // typed on, one letter at a time
  const shown = Math.floor((f - 4 - n.n * 0.5) * (it.cps || 32) / (fps || 30)), total = lines.join('').length;
  g.font = `${size}px ${font}`; g.textAlign = 'left'; g.textBaseline = 'middle'; g.fillStyle = c.text;
  let used = 0;
  const top = -(lines.length - 1) / 2 * lead + (p.tab ? size * 0.12 : 0);
  lines.forEach((l, i) => { const take = clamp(shown - used, 0, l.length); used += l.length; if (take) g.fillText(l.slice(0, take), -hw + size * 0.8, top + i * lead); });
  if (shown >= total && Math.floor(f / 8) % 2 === 0) {   // the waiting mark
    const s = size * 0.3, x = hw - size * 0.9, y = hh - size * 0.6;
    g.beginPath(); g.moveTo(x - s, y - s * 0.6); g.lineTo(x + s, y - s * 0.6); g.lineTo(x, y + s * 0.6); g.closePath(); g.fill();
  }
}

// draws one frame of a bubble on a transparent or live canvas; nothing outside its life
export function drawBubbleItem(g, W, H, it, f) {
  const len = it.len || Infinity;
  if (f < 0 || f >= len || !it.text) return;
  const L = layout(g, it, W, H), lw = inkPx(W, H), P = POPS[it.pop] || POPS.soft, ink = it.fill === 'ink';
  const c = { fill: ink ? INK : MUSTARD, line: ink ? MUSTARD : INK, text: ink ? MUSTARD : INK, fill2: ink ? MUSTARD : INK, line2: ink ? MUSTARD : INK, text2: ink ? INK : MUSTARD };
  const x = it.x * W, y = it.y * H, kind = L.p.kind, tip = it.tip && kind === 'bubble' ? clampTip(it, L, W, H) : null;
  g.save(); g.translate(x, y); g.textBaseline = 'middle';
  if (kind === 'box') { drawBox(g, L, it, f, c, lw, H, it.fps); g.restore(); return; }
  const t = clamp(f / P.n, 0, 1), left = len - f;
  let sc = 0.15 + 0.85 * backOut(t, P.over);
  if (left < OUT) sc *= (left / OUT) ** 2;
  if (it.preset === 'surprise' || it.preset === 'star') {   // lands with a short shake
    const k = clamp(1 - (f - P.n) / 8, 0, 1) * (f >= P.n ? 1 : 0), w = L.size * 0.08;
    g.translate(Math.sin(f * 2.3) * w * k, Math.cos(f * 3.1) * w * k);
  }
  if (it.preset === 'zoom') {
    g.transform(1, 0, -0.24, 1, 0, 0);
    g.translate(-W * 0.45 * (1 - backOut(t, P.over)), 0);
    g.font = `${L.size}px ${L.font}`; g.textAlign = 'center';
    const u = clamp(1 - (f - P.n) / 10, 0, 1);
    if (u) { g.lineWidth = lw; g.strokeStyle = c.line; g.lineCap = 'round'; for (const k of [-0.3, 0, 0.3]) { const yy = k * L.size, x0 = -L.tw / 2 - L.size * 0.25; g.beginPath(); g.moveTo(x0, yy); g.lineTo(x0 - L.size * (1.3 + Math.abs(k)) * u, yy); g.stroke(); } }
    outlined(g, L.lines.join(' '), 0, 0, lw, MUSTARD, INK);
    g.restore(); return;
  }
  // a bubble grows out of the speaker's mouth; a burst out of its own middle
  const ox = tip ? tip[0] : 0, oy = tip ? tip[1] : 0;
  g.translate(ox, oy); g.scale(sc, sc); if (it.preset === 'star') g.rotate((1 - backOut(t, P.over)) * -0.5); g.translate(-ox, -oy);
  if (kind === 'burst') { drawBurstShape(g, L, it, f, c, lw); drawLetters(g, L, it, f, c, W, H, lw); g.restore(); return; }
  drawBubbleShape(g, L, it, f, c, W, H, lw, tip);
  g.fillStyle = c.text; g.font = `${L.size}px ${L.font}`; g.textAlign = 'center'; g.textBaseline = 'middle';
  const words = it.reveal == null ? Infinity : it.reveal;
  let k = 0;
  L.lines.forEach((l, i) => {
    const yy = (i - (L.lines.length - 1) / 2) * L.lead;
    if (words === Infinity) { g.fillText(l, 0, yy); return; }
    const ws = l.split(' '), full = g.measureText(l).width;   // word by word, keeping each word where it will end up
    let xx = -full / 2;
    g.textAlign = 'left';
    for (const w of ws) { if (k++ < words) g.fillText(w, xx, yy); xx += g.measureText(w + ' ').width; }
  });
  g.restore();
}
// the tail always reaches the speaker, wherever the bubble is dragged
const clampTip = (it, L, W, H) => [(it.tip.x - it.x) * W, (it.tip.y - it.y) * H];
export const lifeOf = (it, fps = 30) => ({ pop: (POPS[it.pop] || POPS.soft).n, out: OUT, min: Math.round(fps * 0.8) });
// the frames a render must write one by one: the pop, the typing and the exit. The rest can hold.
export const moving = it => { const p = PRESETS[it.preset] || PRESETS.talk; return p.kind === 'box' || p.kind === 'burst' || it.preset === 'shaky' || it.reveal != null; };

// ---------------------------------------------------------------- on the shot
//   shot.bubbles = [{ id, preset, text, f, len, speaker, dx, dy, x, y, w, fill, pop, font, name, snap, follow, sync, boil, babble, match, hidden }]
// speaker: 'lead', 'c0'.. or null. dx, dy: where the bubble sits from that head's middle (0..1 of the frame), or
// null to sit above it; follow = false keeps it at x, y while the tail still reaches the speaker.
let seq = 0;
const uid = () => 'sb' + Date.now().toString(36) + (seq++).toString(36);
export const bubblesOf = shot => (shot.bubbles ||= []);
export const readLen = (text, fps) => Math.round(clamp(0.9 + String(text).split(/\s+/).filter(Boolean).length * 0.33, 1.2, 6) * fps);
export function addBubble(shot, preset, o = {}) {
  const p = PRESETS[preset];
  if (!p) throw Error('preset must be ' + Object.keys(PRESETS).join(', '));
  const fps = o.fps || shot.fps || 30, text = o.text ?? p.sample, f = clamp(Math.round(o.f ?? 0), 0, shot.length - 1);
  const b = { id: uid(), preset, text, f, len: Math.max(2, Math.min(shot.length - f, Math.round(o.len ?? readLen(text, fps)))), fill: o.fill || p.fill || 'mustard', pop: POPS[o.pop] ? o.pop : 'soft' };
  if (p.kind === 'bubble') b.speaker = o.speaker === undefined ? 'lead' : o.speaker;
  else { b.x = o.x ?? 0.5; b.y = o.y ?? (p.kind === 'box' ? 0.72 : 0.3); }
  if (o.x != null && b.speaker != null) { b.x = o.x; b.y = o.y ?? 0.3; b.follow = false; }
  bubblesOf(shot).push(b);
  return b;
}
export function removeBubble(shot, id) { const l = bubblesOf(shot), i = l.findIndex(b => b.id === id); if (i < 0) throw Error('No bubble ' + id); return l.splice(i, 1)[0]; }
// the second half keeps playing, so it does not pop in again
export function splitBubble(shot, id, at) {
  const l = bubblesOf(shot), i = l.findIndex(b => b.id === id), b = l[i], f = Math.round(at);
  if (!b || f <= b.f || f >= b.f + b.len) throw Error('Put the playhead inside the bubble to cut it');
  const next = { ...b, id: uid(), f, len: b.f + b.len - f };
  delete next.babble; delete b.babble; delete b.match; delete next.match;
  b.len = f - b.f; l.splice(i + 1, 0, next);
  return next;
}
// frames that look alike share one picture in the render
export function settleFrame(it, f) {
  const p = PRESETS[it.preset], P = POPS[it.pop] || POPS.soft, n = letters(it.text || '').length;
  if (it.len && f >= it.len - OUT) return f;
  if (it.boil || it.preset === 'shaky' || it.preset === 'drift') return f;
  if (p.kind === 'box') { const typed = Math.ceil(4 + P.n * 0.5 + n * (it.fps || 30) / (it.cps || 32)); return f < typed ? f : typed + Math.floor(f / 8) % 2; }
  const rest = p.kind === 'burst' ? P.n + n * 2 + 40 : P.n + 9;
  return Math.min(f, rest);
}
export const REST = OUT;
export function loadFonts() {
  return (loadFonts.p ||= Promise.all([['Patrick Hand', 'PatrickHand-Regular.ttf'], ['Luckiest Guy', 'LuckiestGuy-Regular.ttf'], ['Pixelify Sans', 'PixelifySans.ttf'], ['VT323', 'VT323-Regular.ttf']]
    .map(async ([n, f]) => { try { const x = new FontFace(n, `url(fonts/${f})`); await x.load(); document.fonts.add(x); } catch {} })));
}
