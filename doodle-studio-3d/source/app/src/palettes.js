// Your own palettes: picked by hand or imported. A palette file is read here, in the app. It
// accepts .ase (Adobe), .aco (Photoshop), .gpl (GIMP, Krita, Inkscape), .pal (JASC, Paint Shop),
// .hex, .txt and .json (hex colours in any layout). Saved palettes live on this PC; the one in use
// is stored whole on the scene, so it still renders on a PC that has never seen it.
const KEY = 'ds3d.myPalettes';
export const myPalettes = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; } };
const store = list => { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch {} };
export const savePalette = p => store([...myPalettes().filter(x => x.id !== p.id), p]);
export const dropPalette = id => store(myPalettes().filter(x => x.id !== id));

const hex2 = v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0').toUpperCase();
const rgbHex = (r, g, b) => '#' + hex2(r) + hex2(g) + hex2(b);
const cmyk = (c, m, y, k) => rgbHex(255 * (1 - c) * (1 - k), 255 * (1 - m) * (1 - k), 255 * (1 - y) * (1 - k));
function lab(L, a, b) {   // CIE Lab (D50) to sRGB
  const fy = (L + 16) / 116, fx = fy + a / 500, fz = fy - b / 200, f = t => (t > 6 / 29 ? t ** 3 : 3 * (6 / 29) ** 2 * (t - 4 / 29));
  const X = 0.9642 * f(fx), Y = f(fy), Z = 0.8251 * f(fz), g = c => 255 * (c <= 0.0031308 ? 12.92 * c : 1.055 * Math.max(c, 0) ** (1 / 2.4) - 0.055);
  return rgbHex(g(3.1339 * X - 1.6170 * Y - 0.4906 * Z), g(-0.9785 * X + 1.9160 * Y + 0.0333 * Z), g(0.0720 * X - 0.2290 * Y + 1.4057 * Z));
}

function parseAse(buf) {
  const d = new DataView(buf), out = [];
  const count = d.getUint32(8);
  let at = 12;
  for (let i = 0; i < count && at < buf.byteLength; i++) {
    const type = d.getUint16(at), len = d.getUint32(at + 2);
    if (type === 1) {
      const chars = d.getUint16(at + 6), p = at + 8 + chars * 2, model = String.fromCharCode(d.getUint8(p), d.getUint8(p + 1), d.getUint8(p + 2), d.getUint8(p + 3)).trim(), f = n => d.getFloat32(p + 4 + n * 4);
      if (model === 'RGB') out.push(rgbHex(f(0) * 255, f(1) * 255, f(2) * 255));
      else if (model === 'CMYK') out.push(cmyk(f(0), f(1), f(2), f(3)));
      else if (model === 'LAB') out.push(lab(f(0) * 100, f(1), f(2)));
      else if (model === 'Gray') out.push(rgbHex(f(0) * 255, f(0) * 255, f(0) * 255));
    }
    at += 6 + len;
  }
  return out;
}

function parseAco(buf) {
  const d = new DataView(buf), out = [], n = d.getUint16(2);
  for (let i = 0; i < n; i++) {
    const p = 4 + i * 10, space = d.getUint16(p), w = k => d.getUint16(p + 2 + k * 2);
    if (space === 0) out.push(rgbHex(w(0) / 257, w(1) / 257, w(2) / 257));
    else if (space === 2) out.push(cmyk(1 - w(0) / 65535, 1 - w(1) / 65535, 1 - w(2) / 65535, 1 - w(3) / 65535));
    else if (space === 8) out.push(rgbHex(w(0) / 39.2157, w(0) / 39.2157, w(0) / 39.2157));
  }
  return out;
}

export function parseText(text) {
  const t = String(text).replace(/^﻿/, '');
  if (/^GIMP Palette/.test(t) || /^JASC-PAL/.test(t)) {
    const out = [];
    for (const l of t.split(/\r?\n/).slice(/^JASC/.test(t) ? 3 : 1)) { const m = /^\s*(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})/.exec(l); if (m) out.push(rgbHex(+m[1], +m[2], +m[3])); }
    return out;
  }
  return [...t.matchAll(/(?:#|0x|\b)([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g)].map(m => { const h = m[1].length === 3 ? [...m[1]].map(c => c + c).join('') : m[1]; return '#' + h.toUpperCase(); }).filter(h => /#/.test(h));
}

export function parsePalette(name, buf) {
  const sig = String.fromCharCode(...new Uint8Array(buf.slice(0, 4)));
  const list = sig === 'ASEF' ? parseAse(buf) : /\.aco$/i.test(name) ? parseAco(buf) : parseText(new TextDecoder().decode(buf));
  return [...new Set(list)];
}

const light = h => { const n = i => parseInt(h.slice(i, i + 2), 16); return 0.2126 * n(1) + 0.7152 * n(3) + 0.0722 * n(5); };
const vivid = h => { const c = [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)); return Math.max(...c) - Math.min(...c); };
// any list of colours becomes a palette: lightest for the sky, darkest for the ground, the most
// vivid for the accent, the rest for the pieces
export function fromColours(name, colours) {
  const by = [...colours].sort((a, b) => light(a) - light(b)), n = by.length;
  const accent = [...colours].sort((a, b) => vivid(b) - vivid(a))[0];
  const rest = colours.filter(c => c !== by[0] && c !== by[n - 1] && c !== accent);
  const pieces = (rest.length >= 2 ? rest : colours).slice(0, 8);
  return { id: 'my-' + Date.now().toString(36), name, theory: 'Your palette', character: pieces[0], outfit: accent, ink: '#1F1F1D', wall: by[Math.floor(n * 0.6)], floor: by[0], ceiling: by[n - 1],
    pieces, accent, ambient: '#FFFFFF' };
}

const ROLES = [['character', 'Character'], ['outfit', 'Outfit'], ['wall', 'Walls'], ['floor', 'Ground'], ['ceiling', 'Sky'], ['accent', 'Accent']];
// the maker: a starting palette, a colour picker for each role, paste or import
export function paletteMaker(ctx, start, use) {
  const { h } = ctx;
  let p = { ...start, pieces: [...start.pieces] };
  const box = h('div', { class: 'pal-maker' });
  const draw = () => {
    const name = h('input', { type: 'text', value: p.name, 'aria-label': 'Palette name', placeholder: 'Palette name' });
    name.addEventListener('change', () => { p.name = name.value; });
    const pick = (value, label, put) => { const c = h('input', { type: 'color', value, 'aria-label': label, title: label }); c.addEventListener('change', () => put(c.value.toUpperCase())); return c; };
    const paste = h('input', { type: 'text', placeholder: 'Paste hex colours: #1B998B #E84855 #FFFD82', 'aria-label': 'Paste hex colours' });
    const take = (nm, list) => { if (!list.length) { ctx.toast('No colours found in that'); return; } p = { ...fromColours(nm, list), id: p.id }; draw(); ctx.toast(`${list.length} colours in`); };
    paste.addEventListener('change', () => take(p.name, parseText(paste.value)));
    const file = h('input', { type: 'file', accept: '.ase,.aco,.gpl,.pal,.hex,.txt,.json', style: 'display:none' });
    file.addEventListener('change', async () => { const f = file.files[0]; if (!f) return; take(f.name.replace(/\.\w+$/, ''), parsePalette(f.name, await f.arrayBuffer())); });
    box.replaceChildren(h('div', { class: 'row mat-row' }, name, paste, h('button', { title: 'Adobe .ase, Photoshop .aco, GIMP or Krita .gpl, .pal, .hex, .txt, .json', onclick: () => file.click() }, 'Import file…'), file),
      h('div', { class: 'row mat-row' }, ...ROLES.flatMap(([k, n]) => [h('span', { class: 'sub-label' }, n), pick(p[k], n, v => { p[k] = v; })])),
      h('div', { class: 'row mat-row' }, h('span', { class: 'sub-label' }, 'Pieces'), ...p.pieces.map((c, i) => pick(c, 'Piece colour ' + (i + 1), v => { p.pieces[i] = v; })),
        p.pieces.length < 8 ? h('button', { title: 'Add a colour', onclick: () => { p.pieces.push(p.accent); draw(); } }, '+') : null,
        p.pieces.length > 2 ? h('button', { title: 'Remove the last colour', onclick: () => { p.pieces.pop(); draw(); } }, '−') : null,
        h('button', { class: 'primary', onclick: () => { p.name = name.value || 'My palette'; savePalette(p); use(p); } }, 'Save and use')));
  };
  draw();
  return box;
}
