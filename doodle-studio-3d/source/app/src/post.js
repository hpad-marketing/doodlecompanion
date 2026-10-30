// Storytime part 3, render side: what is laid over and under the rendered shots when
// they are joined in Blender's video editor (ds_concat.py). Flashback and VHS looks,
// real photo cut-ins and a narrator picture-in-picture with an ink outline (never a box),
// the imagination bubble, caption tracks (English / Hindi, opt-in word highlight), a music
// bed that ducks under the voice, bleeps and opt-in character voices. All local.
import { setKey } from './project.js';

export const INK = '#1F1F1D', MUSTARD = '#E0A64B';
export const LOOKS = { flashback: 'Flashback', vhs: 'VHS tape' };
export const VOICES = { high: 1.45, chipmunk: 1.9, low: 0.78, giant: 0.6, robot: 'robot' };
export const CORNERS = { tl: [0.2, 0.17], tr: [0.8, 0.17], bl: [0.2, 0.62], br: [0.8, 0.62] };
const FONT = '"Patrick Hand", "Nirmala UI", "Noto Sans Devanagari", "Segoe Print", system-ui, sans-serif';
const inkPx = (W, H) => Math.max(3, Math.round(10.5 * Math.min(W, H) / 1080));   // Bunny's line weight

let fontReady = null;
export function loadFont() {
  fontReady ||= (async () => { try { const f = new FontFace('Patrick Hand', 'url(lib/storytime/fonts/PatrickHand-Regular.ttf)'); await f.load(); document.fonts.add(f); } catch {} })();
  return fontReady;
}

// ---------------------------------------------------------------- caption tracks
export const LANGS = { en: 'English', hi: 'Hindi' };
export function captionsOf(scene) {
  scene.captions ||= { active: 'en', highlight: false, y: 0.7, tracks: { en: [], hi: [] } };
  for (const k of Object.keys(LANGS)) scene.captions.tracks[k] ||= [];
  return scene.captions;
}
// lines carry the shot uid and frames in it, so they move with their shot
export function addCaption(scene, shot, f, to, text, lang = captionsOf(scene).active) {
  const t = captionsOf(scene).tracks[lang];
  if (!t) throw Error('lang must be ' + Object.keys(LANGS).join(' or '));
  const line = { shot: shot.uid, f: Math.max(0, f), to: Math.min(shot.length, Math.max(f + 1, to)), text: String(text).trim() };
  t.push(line);
  return line;
}
// a short caption (1-3 words) stays on one line; longer ones break into two
export function captionLines(text) {
  const w = String(text).trim().split(/\s+/).filter(Boolean);
  if (w.length <= 3) return [w];
  const half = Math.ceil(w.length / 2);
  return [w.slice(0, half), w.slice(half)];
}
export function captionAt(scene, shot, f) {
  const c = scene.captions;
  if (!c) return null;
  return (c.tracks[c.active] || []).find(l => l.shot === shot.uid && f >= l.f && f < l.to) || null;
}
const srtTime = s => { const ms = Math.round(s * 1000); return `${String(Math.floor(ms / 3600000)).padStart(2, '0')}:${String(Math.floor(ms / 60000) % 60).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`; };
export function srt(scene, lang) {
  const t = captionsOf(scene).tracks[lang] || [], starts = {};
  let n = 0;
  for (const s of scene.shots) { starts[s.uid] = n; n += s.length; }
  return t.filter(l => starts[l.shot] != null).map(l => [(starts[l.shot] + l.f) / scene.fps, (starts[l.shot] + l.to) / scene.fps, l.text]).sort((a, b) => a[0] - b[0])
    .map(([a, b, x], i) => `${i + 1}\n${srtTime(a)} --> ${srtTime(b)}\n${x}\n`).join('\n');
}
export function parseSrt(scene, text, lang) {
  const blocks = String(text).replace(/\r/g, '').split(/\n\s*\n/), out = [];
  const sec = t => { const m = /(\d+):(\d+):(\d+)[,.](\d+)/.exec(t); return m ? +m[1] * 3600 + +m[2] * 60 + +m[3] + +m[4] / 1000 : null; };
  for (const b of blocks) {
    const lines = b.trim().split('\n'), tl = lines.findIndex(l => l.includes('-->'));
    if (tl < 0) continue;
    const [a, z] = lines[tl].split('-->').map(sec), text2 = lines.slice(tl + 1).join(' ').trim();
    if (a == null || z == null || !text2) continue;
    let F = Math.round(a * scene.fps), n = 0;
    for (const s of scene.shots) { if (F < n + s.length) { out.push({ shot: s.uid, f: F - n, to: Math.min(s.length, F - n + Math.max(1, Math.round((z - a) * scene.fps))), text: text2 }); break; } n += s.length; }
  }
  captionsOf(scene).tracks[lang] = out;
  return out.length;
}
// one caption drawn on a transparent full frame; `hi` is the highlighted word (or -1)
export function drawCaption(g, W, H, text, y, hi = -1) {
  const rows = captionLines(text), size = Math.round(H * 0.045), lw = inkPx(W, H);
  g.font = `${size}px ${FONT}`; g.textAlign = 'center'; g.textBaseline = 'middle'; g.lineJoin = 'round';
  let k = 0;
  rows.forEach((words, r) => {
    const line = words.join(' '), total = g.measureText(line).width, yy = y * H + (r - (rows.length - 1) / 2) * size * 1.15;
    let x = W / 2 - total / 2;
    for (const w of words) {
      const ww = g.measureText(w).width, on = k === hi;
      g.lineWidth = lw * 1.6; g.strokeStyle = on ? INK : MUSTARD; g.strokeText(w, x + ww / 2, yy);
      g.fillStyle = on ? MUSTARD : INK; g.fillText(w, x + ww / 2, yy);
      x += ww + g.measureText(' ').width; k++;
    }
  });
}

// ---------------------------------------------------------------- cut-ins: photo, picture-in-picture, bubble
function roundRect(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
export function drawPhoto(g, W, H, img, it) {
  const w = (it.size ?? 0.5) * W, h = w * img.height / img.width, lw = inkPx(W, H);
  g.save(); g.translate((it.x ?? 0.5) * W, (it.y ?? 0.35) * H); g.rotate((it.tilt ?? -3) * Math.PI / 180);
  roundRect(g, -w / 2, -h / 2, w, h, lw * 1.5); g.save(); g.clip(); g.drawImage(img, -w / 2, -h / 2, w, h); g.restore();
  roundRect(g, -w / 2, -h / 2, w, h, lw * 1.5); g.lineWidth = lw; g.strokeStyle = INK; g.stroke();   // the ink outline, no box
  g.restore();
}
export const pipRect = (it, aspect = 16 / 9) => { const [cx, cy] = CORNERS[it.corner || 'tr'] || CORNERS.tr, w = it.size ?? 0.34; return { cx: it.x ?? cx, cy: it.y ?? cy, w, h: w / aspect }; };
export function drawOutline(g, W, H, r) {
  const lw = inkPx(W, H), w = r.w * W, h = r.h * W;
  roundRect(g, r.cx * W - w / 2, r.cy * H - h / 2, w, h, lw * 1.5); g.lineWidth = lw; g.strokeStyle = INK; g.stroke();
}
// a thought cloud whose mustard rim covers the corners of the clip playing under it
export function drawBubble(g, W, H, r) {
  const lw = inkPx(W, H), cx = r.cx * W, cy = r.cy * H, rx = r.w * W / 2, ry = r.h * W / 2;
  const bumps = 11, R = (a, k) => [cx + Math.cos(a) * (rx * 1.28) * k, cy + Math.sin(a) * (ry * 1.32) * k];
  const cloud = () => { g.beginPath(); for (let i = 0; i < bumps; i++) { const a = i / bumps * Math.PI * 2, [x, y] = R(a, 1); g.moveTo(x + rx * 0.3, y); g.arc(x, y, rx * 0.3, 0, Math.PI * 2); } g.ellipse(cx, cy, rx * 1.28, ry * 1.32, 0, 0, Math.PI * 2); };
  g.save();
  cloud(); g.fillStyle = MUSTARD; g.fill();
  g.globalCompositeOperation = 'destination-out'; g.beginPath(); g.ellipse(cx, cy, rx * 0.98, ry * 0.98, 0, 0, Math.PI * 2); g.fill();
  g.globalCompositeOperation = 'source-over';
  g.lineWidth = lw; g.strokeStyle = INK; g.beginPath(); g.ellipse(cx, cy, rx * 0.98, ry * 0.98, 0, 0, Math.PI * 2); g.stroke();
  // outer outline: each bump's outside arc
  for (let i = 0; i < bumps; i++) { const a = i / bumps * Math.PI * 2, [x, y] = R(a, 1); g.beginPath(); g.arc(x, y, rx * 0.3, a - 1.6, a + 1.6); g.stroke(); }
  // the trail of little puffs toward the character
  for (const [k, s] of [[1.55, 0.12], [1.8, 0.07]]) { const [x, y] = [cx - rx * 0.9 * (k - 0.9), cy + ry * k]; g.beginPath(); g.arc(x, y, rx * s, 0, Math.PI * 2); g.fillStyle = MUSTARD; g.fill(); g.stroke(); }
  g.restore();
}

// ---------------------------------------------------------------- looks
export function drawLook(g, W, H, look) {
  if (look === 'flashback') {
    // warm mustard wash multiplied over a grey picture, ink vignette at the edges
    const v = g.createRadialGradient(W / 2, H / 2, Math.min(W, H) * 0.35, W / 2, H / 2, Math.hypot(W, H) * 0.55);
    v.addColorStop(0, 'rgba(31,31,29,0)'); v.addColorStop(1, 'rgba(31,31,29,0.75)');
    g.fillStyle = v; g.fillRect(0, 0, W, H);
  } else if (look === 'vhs') {
    g.fillStyle = 'rgba(31,31,29,0.18)';
    for (let y = 0; y < H; y += 4) g.fillRect(0, y, W, 1.5);
    const s = Math.round(H * 0.035);
    g.font = `${s}px ${FONT}`; g.textBaseline = 'top'; g.fillStyle = MUSTARD; g.strokeStyle = INK; g.lineWidth = inkPx(W, H);
    g.strokeText('PLAY ▶', W * 0.06, H * 0.05); g.fillText('PLAY ▶', W * 0.06, H * 0.05);
  }
}
export const LOOK_STRIP = { flashback: { saturation: 0, multiply: [1.0, 0.86, 0.6] }, vhs: { saturation: 1.25, multiply: [1, 1, 1] } };

// ---------------------------------------------------------------- music bed ducking + voice ranges from markers
export function duckKeys(env, from, length, { volume = 0.35, duck = 0.35, quiet = [] } = {}) {
  const out = [];
  let level = volume, last = null;
  for (let f = 0; f < length; f++) {
    const talking = (env?.[from + f] || 0) > 0.15, hush = quiet.some(([a, b]) => f >= a && f <= b);
    const want = hush ? 0 : talking ? volume * duck : volume;
    level += (want - level) * (want < level ? 0.35 : 0.08);   // fast attack, slow release
    const v = +level.toFixed(3);
    if (last == null || Math.abs(v - last) > 0.01 || f === length - 1) { out.push([f, v]); last = v; }
  }
  return out;
}
// markers like "bleep: 0.6" (seconds), "voice: chipmunk" ... "voice: normal"
export function markerSpans(list, fps) {
  const bleeps = [], voices = [], quiet = [];
  let open = null;
  for (const { F, note } of list) {
    const b = /^\s*bleep\s*:?\s*([\d.]*)/i.exec(note);
    if (b) bleeps.push([F, F + Math.max(2, Math.round((parseFloat(b[1]) || 0.5) * fps))]);
    const v = /^\s*voice\s*:\s*(\w+)/i.exec(note);
    if (v) { if (open) voices.push({ ...open, to: F }); open = VOICES[v[1].toLowerCase()] ? { from: F, preset: v[1].toLowerCase() } : null; }
    if (/^\s*quiet\b/i.test(note)) { const sc = list.find(x => x.F > F && /^\s*scare/i.test(x.note)); quiet.push([F, sc ? sc.F : F + fps]); }
  }
  if (open) voices.push({ ...open, to: Infinity });
  return { bleeps, voices, quiet };
}
