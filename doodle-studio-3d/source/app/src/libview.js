// The library and stage as pictures: every asset shows a large preview, hovering a motion or a
// face plays it on the character in the 3D view before you add it, and the stage (set, pieces,
// light, wardrobe) and the items in the shot are picked and edited from their pictures.
import { libraryRows, libraryInfo, loadLibrary, useItem, setStage, removeItem, search, CATEGORIES, CHARACTERS } from './library.js';
import { stageOf } from './project.js';
import { lightControls } from './lightpanel.js';

const cap = s => s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');
const TIMES = ['day', 'golden', 'night'];
const SKIES = ['day', 'sunset', 'stars', 'storm'];
// pictures for the pieces that are built in Blender from code (no library preview image)
export const GLYPH = {
  rain: '╱╱╱', downpour: '║║║', splashes: '◡◡', snow: '❄', leaves: '❦', petals: '✿', wind: '≋', speed_lines: '═══', steam: '§', smoke: '☁', sparkles: '✦✧', confetti: '✶✷', streamers: '〰', fireworks: '✺',
  dust: '∴', poof: '❂', sparkle_burst: '✸', question: '?', exclaim: '!', sweat: '٥', heart: '♥', anger: '✱', zzz: 'Zz', star: '★', lightbulb: '☼', note: '♪', dizzy: '@', tear: '◖', sparkle: '✦',
  time_skip: '⧗', chat: '❝❞', label: '➘', journey: '⤳', headline: 'Aa', end_screen: '▣', horror: '☾',
  pop: '♪', message: '♪', typing: '♪', whoosh: '♪', boing: '♪', click: '♪', bell: '♪', pin: '♪', draw: '♪', horror_drone: '♪', thunder: '♪', sting: '♪',
};
export const glyphOf = id => GLYPH[String(id).split(':')[1]] || '◆';
const ui = { cat: 'prop', q: '', mirror: false, blend: 0, hold: '', shotOnly: false, sel: null, page: 1 };
export const libUi = ui;

// ---------------------------------------------------------------- pictures for every library row
// Motions play as small looping sprite sheets (Doodle Library previews/motion_anim, made from the
// Doodle Studio rig); faces without a library picture are drawn from the character's own face
// drawings; outfit and accessory pictures are trimmed to the character so they fill the card.
let animIdx = null, pictureData = null;
export const hasAnim = id => !!animIdx?.items?.[id];
function animPic(h, id) {
  const A = animIdx, [s, r] = A.items[id], sh = A.sheets[s];
  return h('span', { class: 'anim', 'aria-hidden': 'true', style: `--n:${A.n};aspect-ratio:${A.fw}/${A.fh};background-image:url('/lib/previews/motion_anim/${sh.file}');background-size:${A.n * 100}% ${sh.rows * 100}%;background-position-y:${sh.rows > 1 ? (r / (sh.rows - 1)) * 100 : 0}%` });
}
const trimCache = new Map();
function trimmed(h, src) {
  const img = h('img', { src: trimCache.get(src) || src, alt: '', loading: 'lazy', draggable: 'false' });
  if (trimCache.has(src)) return img;
  const once = () => {
    img.removeEventListener('load', once);
    try {
      const w = img.naturalWidth, ht = img.naturalHeight, c = document.createElement('canvas'); c.width = w; c.height = ht;
      const g = c.getContext('2d'); g.drawImage(img, 0, 0); const d = g.getImageData(0, 0, w, ht).data;
      let x0 = w, y0 = ht, x1 = -1, y1 = -1;
      for (let y = 0; y < ht; y += 2) for (let x = 0; x < w; x += 2) { const i = (y * w + x) * 4; if (d[i + 3] > 128 && d[i] < 110) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; } }
      if (x1 < 0) { trimCache.set(src, src); return; }
      const side = Math.max(x1 - x0, y1 - y0) * 1.12 + 8, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, o = document.createElement('canvas'); o.width = o.height = 256;
      const og = o.getContext('2d'); og.fillStyle = '#E0A64B'; og.fillRect(0, 0, 256, 256); og.drawImage(img, cx - side / 2, cy - side / 2, side, side, 0, 0, 256, 256);
      const url = o.toDataURL(); trimCache.set(src, url); img.src = url;
    } catch { trimCache.set(src, src); }
  };
  img.addEventListener('load', once);
  return img;
}
function faceIndexOf(row) {
  const F = pictureData?.face; if (!F) return -1;
  const n = String(row.data?.expression_name || row.name).toLowerCase();
  return Number.isInteger(row.data?.expression) ? row.data.expression : F.faces.findIndex(x => x.toLowerCase() === n);
}
export function picture(h, row, big = false) {
  if (!animIdx && libraryInfo()?.anim) animIdx = libraryInfo().anim;
  if (row?.category === 'motion' && hasAnim(row.id)) return animPic(h, row.id);
  if (row?.preview && ['outfit', 'accessory'].includes(row.category)) return trimmed(h, '/lib/' + row.preview);
  if (row?.preview) return h('img', { src: '/lib/' + row.preview, alt: '', loading: 'lazy', draggable: 'false' });
  if (row?.category === 'expression') { const i = faceIndexOf(row); if (i >= 0) return h('img', { src: faceThumb(pictureData, i, row.data?.gaze > 0 ? row.data.gaze : 0, big ? 240 : 120), alt: '', draggable: 'false' }); }
  if (row?.category === 'expression' && /^(Frog|Koala|Bunny)\b/.test(row.name)) { const c = row.name.split(' ')[0].toLowerCase(); return h('img', { src: `chars/${c}.png`, alt: '', draggable: 'false', title: `A ${row.name.split(' ')[0]} face` }); }
  if (row?.category === 'motion') return h('span', { class: 'glyph', 'aria-hidden': 'true', title: 'A Blender action: no picture yet' }, '▶');
  return h('span', { class: 'glyph', 'aria-hidden': 'true' }, row ? glyphOf(row.id) : '⊘');
}

// ---------------------------------------------------------------- the browser (Library tab, Animate › Motion library)
// opts.cats: the categories this browser offers (chips); opts.cat: start category
export function libraryBrowser(ctx, opts = {}) {
  const { h } = ctx;
  const cats = opts.cats || CATEGORIES.filter(c => c[0] !== 'motion').map(c => c);
  if (opts.cat) ui.cat = opts.cat;
  if (!cats.some(c => c[0] === ui.cat)) ui.cat = cats[0][0];
  const rows = libraryRows();
  if (ctx.data) pictureData = ctx.data();
  if (ctx.lib?.()?.anim) animIdx = ctx.lib().anim;
  const box = h('div', { class: 'libx library' });
  const main = h('div', {}), side = h('div', { class: 'libx-side' });
  const lib = ctx.lib?.();
  if (lib && !lib.found) main.append(h('p', { class: 'hint' }, `The Doodle Library was not found${lib.dir ? ' at ' + lib.dir : ''}. Effects, reactions, storytime pieces and sounds still work.`),
    h('div', { class: 'row' }, h('button', { onclick: () => ctx.api('pick-library', {}).then(() => loadLibrary(ctx.api, true)).then(ctx.rebuild).catch(e => ctx.toast(e.message)) }, 'Find library folder…')));
  const q = h('input', { type: 'search', placeholder: ui.cat === 'motion' ? 'Search motions, e.g. wave, walk, shrug' : 'Search, e.g. mug, tree, rain', value: ui.q, 'aria-label': 'Search the library' });
  const top = h('div', { class: 'libx-top' }, q);
  if (cats.length > 1 && !opts.noChips) top.append(h('div', { class: 'chips' }, ...cats.map(([id, n]) => h('button', { 'aria-pressed': String(ui.cat === id), onclick: () => { ui.cat = id; ui.sel = null; ui.page = 1; ctx.rebuild(); } }, n))));
  let catRows = null;
  if (ui.cat === 'motion') {
    // motion families and categories as two horizontal chip rows (hand-made, performance, mocap)
    const fam = r => (/^Mocap/.test(r.sub || '') ? 'Mocap' : /^Performance/.test(r.sub || '') ? 'Performance' : r.kind === 'ds' ? 'Doodle' : 'Blender');
    const mot = rows.filter(r => r.category === 'motion'), fams = ['All', ...['Doodle', 'Performance', 'Mocap', 'Blender'].filter(f => mot.some(r => fam(r) === f))];
    ui.fam ||= 'All'; ui.sub ||= 'All';
    const pool = mot.filter(r => ui.fam === 'All' || fam(r) === ui.fam), subs = [...new Set(pool.map(r => r.sub || 'Other'))];
    if (ui.sub !== 'All' && !subs.includes(ui.sub)) ui.sub = 'All';
    const chip = (on, label, n, fn) => h('button', { 'aria-pressed': String(on), onclick: fn }, label, h('small', { class: 'n' }, ' ' + n));
    const short = s => (ui.fam === 'All' ? s : s.replace(/^(Mocap|Performance) · /, ''));
    catRows = h('div', { class: 'libx-cats' },
      h('div', { class: 'chips', role: 'tablist', 'aria-label': 'Motion family' }, ...fams.map(f => chip(ui.fam === f, f === 'Doodle' ? 'Hand-made' : f, f === 'All' ? mot.length : mot.filter(r => fam(r) === f).length, () => { ui.fam = f; ui.sub = 'All'; ui.page = 1; ctx.rebuild(); }))),
      h('div', { class: 'chips', role: 'tablist', 'aria-label': 'Motion category' }, chip(ui.sub === 'All', 'All categories', pool.length, () => { ui.sub = 'All'; ui.page = 1; ctx.rebuild(); }),
        ...subs.map(s => chip(ui.sub === s, short(s), pool.filter(r => (r.sub || 'Other') === s).length, () => { ui.sub = s; ui.page = 1; ctx.rebuild(); }))));
    ui.motionFilter = r => (ui.fam === 'All' || fam(r) === ui.fam) && (ui.sub === 'All' || (r.sub || 'Other') === ui.sub);
    const m = h('input', { type: 'checkbox' }); m.checked = ui.mirror; m.addEventListener('change', () => { ui.mirror = m.checked; });
    const b = h('input', { type: 'number', min: 0, max: 60, step: 1, value: ui.blend, style: 'width:56px', 'aria-label': 'Blend in frames' }); b.addEventListener('change', () => { ui.blend = Math.max(0, Number(b.value) || 0); });
    top.append(h('label', { class: 'hint', title: 'Swap left and right' }, m, ' Mirror'), h('label', { class: 'hint', title: 'Clip blending: crossfade from the animation already there into the clip over this many frames. 0 cuts straight in.' }, 'Blend in ', b, ' frames'));
  }
  if (ui.cat === 'prop') {
    const s = h('select', { 'aria-label': 'Hold' }, h('option', { value: '' }, 'Stands in the scene'), h('option', { value: 'L' }, 'In the left hand'), h('option', { value: 'R' }, 'In the right hand'));
    s.value = ui.hold; s.addEventListener('change', () => { ui.hold = s.value; });
    top.append(s);
  }
  const grid = h('div', { class: 'libx-grid', role: 'list' });
  const add = r => useItem(ctx, r, { mirror: ui.mirror, blend: ui.blend, hold: ui.hold, shotOnly: ui.shotOnly }).then(res => { if (res) { ctx.toast(`Added ${r.name}${r.category === 'motion' ? ' at frame ' + ctx.frame() : ''}`); ctx.added?.(r, res); } ctx.rebuild(); }).catch(e => ctx.toast(e.message, 4000));
  const showSide = r => {
    side.replaceChildren();
    if (!r) { side.append(h('div', { class: 'big' }, h('span', { class: 'glyph' }, '◆')), h('p', { class: 'hint' }, ui.cat === 'motion' || ui.cat === 'expression' ? 'Point at a picture to play it on the character in the 3D view. Click to pick it, then Add.' : 'Point at a picture to see it large. Click to pick it, then Add. Props and scenery appear in the 3D view at once, where you can drag them into place.')); return; }
    side.append(...[h('div', { class: 'big' }, picture(h, r, true)), h('h4', {}, r.name), h('p', { class: 'hint' }, [r.sub, r.frames ? `${r.frames} frames${r.loop ? ', loops' : ''}` : null].filter(Boolean).join(' · ')),
      r.description ? h('p', {}, r.description) : null, r.data?.grip ? h('p', { class: 'hint' }, 'Held: ' + r.data.grip) : null,
      h('div', { class: 'row', style: 'margin-top:6px' },
        h('button', { class: 'primary', onclick: () => add(r), title: 'Add it at the playhead' }, r.category === 'motion' ? 'Add at playhead' : r.category === 'sound' ? 'Add sound here' : 'Add to the shot'),
        r.category === 'motion' || r.category === 'expression' ? h('button', { onclick: () => ctx.preview?.(r), title: 'Play it on the character again' }, 'Play preview') : null)].filter(Boolean));
  };
  const LIMIT = 120 * ui.page;
  const fill = () => {
    const found = ui.cat === 'motion' && ui.motionFilter ? search(rows, { category: 'motion', query: ui.q, limit: 1e5 }).filter(ui.motionFilter).slice(0, LIMIT + 1) : search(rows, { category: ui.cat, query: ui.q, limit: LIMIT + 1 });
    grid.replaceChildren(...found.slice(0, LIMIT).map(r => {
      const b = h('button', { class: 'lib-item libx-card', role: 'listitem', 'aria-pressed': String(ui.sel === r.id), 'data-id': r.id, title: `${r.name}${r.sub ? ' · ' + r.sub : ''}\nClick to pick, double-click to add at the playhead`,
        onclick: () => { ui.sel = r.id; grid.querySelectorAll('.libx-card').forEach(x => x.setAttribute('aria-pressed', String(x === b))); showSide(r); if (!opts.side) add(r); },
        ondblclick: () => { if (opts.side !== false) add(r); } },
        h('span', { class: 'pic' }, picture(h, r)), h('span', {}, r.name), h('small', {}, (r.sub || '') + (r.frames ? ` · ${r.frames} f` : '')));
      b.addEventListener('mouseenter', () => { showSide(r); ctx.preview?.(r); });
      b.addEventListener('mouseleave', () => { ctx.previewEnd?.(); showSide(rows.find(x => x.id === ui.sel)); });
      return b;
    }));
    if (found.length > LIMIT) grid.append(h('button', { class: 'libx-more', onclick: () => { ui.page++; fill(); } }, 'Show more'));
    if (!found.length) grid.append(h('p', { class: 'hint' }, lib || rows.length ? 'Nothing matches.' : 'Loading the library…'));
  };
  q.addEventListener('input', () => { ui.q = q.value; ui.page = 1; fill(); });
  main.append(...[top, catRows, grid].filter(Boolean));
  box.append(main, side);
  fill();
  showSide(rows.find(x => x.id === ui.sel));
  if (!rows.length || !lib) loadLibrary(ctx.api).then(() => ctx.rebuild());
  return box;
}

// ---------------------------------------------------------------- stage: set and light
export function setPanel(ctx) {
  const { h } = ctx;
  const scene = ctx.scene(), project = ctx.project(), st = stageOf(scene, project), rows = libraryRows();
  const re = () => ctx.rebuild();
  if (!rows.length) loadLibrary(ctx.api).then(re);
  const scope = h('div', { class: 'chips' }, h('button', { 'aria-pressed': String(!ui.shotOnly), onclick: () => { ui.shotOnly = false; re(); }, title: 'Changes apply to every shot' }, 'Whole scene'),
    h('button', { 'aria-pressed': String(ui.shotOnly), onclick: () => { ui.shotOnly = true; re(); }, title: 'Changes apply to this shot only, on top of the scene' }, `${project.code} only`));
  const chars = h('div', { class: 'char-cards', role: 'list' }, ...CHARACTERS.map(([id, n]) => h('button', { class: 'libx-card', role: 'listitem', 'aria-pressed': String((scene.character || 'bunny') === id), title: `Make the ${n} the lead character`, onclick: () => ctx.setCharacter(id) }, h('span', { class: 'pic', style: 'aspect-ratio:2/3' }, h('img', { src: `chars/${id}.png`, alt: '', draggable: 'false' })), h('span', {}, n))));
  const sel = (label, key, opts, value, title) => {
    const s = h('select', { 'aria-label': label }, ...opts.map(([v, n]) => h('option', { value: v }, n)));
    s.value = value ?? '';
    s.addEventListener('change', () => { setStage(ctx, { [key]: s.value || null }, ui.shotOnly); re(); });
    return h('label', { class: 'lbl-row', title: title || '' }, h('span', { class: 'lbl' }, label), s);
  };
  const check = (label, on, patch, title) => { const c = h('input', { type: 'checkbox' }); c.checked = !!on; c.addEventListener('change', () => { setStage(ctx, patch(c.checked), ui.shotOnly); re(); }); return h('label', { class: 'lbl-row', title }, c, label); };
  const sets = rows.filter(r => r.category === 'set');
  const roomOf = r => r.data?.room || r.id.replace(/^set-/, '');
  const q = h('input', { type: 'search', placeholder: 'Find a set, e.g. kitchen, beach, space', 'aria-label': 'Find a set', value: ui.setQ || '' });
  const grid = h('div', { class: 'libx-grid', style: 'grid-template-columns:repeat(auto-fill,minmax(104px,1fr));max-height:430px;overflow:auto' });
  const fill = () => {
    const words = (ui.setQ || '').toLowerCase().split(/\s+/).filter(Boolean);
    grid.replaceChildren(h('button', { class: 'libx-card', 'aria-pressed': String(!st.set), onclick: () => { setStage(ctx, { set: null }, ui.shotOnly); re(); }, title: 'No set: the plain mustard backdrop' }, h('span', { class: 'pic' }, h('span', { class: 'glyph' }, '▢')), h('span', {}, 'Plain backdrop')),
      ...sets.filter(r => words.every(w => (r.name + ' ' + r.sub + ' ' + (r.tags || []).join(' ')).toLowerCase().includes(w))).map(r =>
        h('button', { class: 'libx-card', 'aria-pressed': String(st.set === roomOf(r)), title: `${r.name} · ${r.sub}. Click to build it in the 3D view.`, onclick: () => { setStage(ctx, { set: roomOf(r) }, ui.shotOnly); re(); } },
          h('span', { class: 'pic' }, picture(h, r)), h('span', {}, r.name), h('small', {}, r.sub || ''))),
      ...(rows.length ? [] : [h('p', { class: 'hint' }, 'Loading the library…')]));
  };
  q.addEventListener('input', () => { ui.setQ = q.value; fill(); });
  fill();
  const setRow = sets.find(r => roomOf(r) === st.set);
  const pieces = setRow?.data?.props?.length ? (() => {
    const on = { ...Object.fromEntries(setRow.data.props.map(p => [p.id, p.on !== false])), ...(st.setProps || {}) };
    return h('div', {}, h('h3', {}, `Pieces of the ${setRow.name.toLowerCase()}`), h('div', { class: 'chips', title: 'Switch off what the shot does not need. Click a piece in the 3D view to move it.' }, ...setRow.data.props.map(p =>
      h('button', { 'aria-pressed': String(!!on[p.id]), onclick: () => { setStage(ctx, { setProps: { ...(st.setProps || {}), [p.id]: !on[p.id] } }, ui.shotOnly); re(); } }, p.label))),
      h('div', { class: 'row', style: 'margin-top:6px' }, h('button', { title: 'Put every moved piece back where the set has it', onclick: () => { setStage(ctx, { pieces: null }, ui.shotOnly); re(); } }, 'Reset moved pieces')));
  })() : h('p', { class: 'hint' }, 'Pick a set: it is built in the 3D view, and every piece can be clicked and moved.');
  const left = h('div', { class: 'col' }, h('h3', {}, 'Set'), h('div', { class: 'row', style: 'margin-bottom:6px' }, q, scope), grid);
  const right = h('div', { class: 'col' }, h('h3', {}, 'Character'), chars, pieces);
  return h('div', { class: 'ws two' }, left, right);
}

// Stage › Light: time and sky, the Shadows button, the lighting presets and their sliders
export function lightPanel(ctx) {
  const { h } = ctx, re = () => ctx.rebuild(), st = stageOf(ctx.scene(), ctx.project());
  const sel = (label, key, opts) => {
    const s = h('select', { 'aria-label': label }, ...opts.map(([v, n]) => h('option', { value: v }, n)));
    s.value = st[key] ?? '';
    s.addEventListener('change', () => { setStage(ctx, { [key]: s.value || null }, ui.shotOnly); re(); });
    return h('label', { class: 'lbl-row' }, h('span', { class: 'lbl' }, label), s);
  };
  const scope = h('div', { class: 'chips' }, h('button', { 'aria-pressed': String(!ui.shotOnly), onclick: () => { ui.shotOnly = false; re(); }, title: 'Changes apply to every shot' }, 'Whole scene'),
    h('button', { 'aria-pressed': String(ui.shotOnly), onclick: () => { ui.shotOnly = true; re(); }, title: 'Changes apply to this shot only, on top of the scene' }, `${ctx.project().code} only`));
  const { main, tune } = lightControls(ctx, ui.shotOnly);
  return h('div', { class: 'ws two' }, h('div', { class: 'col' }, h('h3', {}, 'Time and sky'), scope, sel('Time', 'time', [['', 'Default'], ...TIMES.map(t => [t, cap(t)])]), sel('Sky', 'sky', [['', 'Default'], ...SKIES.map(t => [t, cap(t)])]), main), h('div', { class: 'col' }, tune));
}

// front-on wardrobe cards (app/cards, made by tools/wardrobe_cards.cjs from real Blender renders of
// each outfit and accessory on each character); the library's side-on picture is the fallback
let cards = null;
const loadCards = () => (cards ||= fetch('cards/index.json').then(r => (r.ok ? r.json() : {})).catch(() => ({})));
export const wardrobeCard = (character, id) => (cards && typeof cards.then !== 'function' ? cards[character]?.[id] || cards.bunny?.[id] || null : null);
export function wardrobePanel(ctx) {
  const { h } = ctx;
  const scene = ctx.scene(), project = ctx.project(), st = stageOf(scene, project), rows = libraryRows(), lib = ctx.lib?.();
  const re = () => ctx.rebuild();
  if (!rows.length) loadLibrary(ctx.api).then(re);
  if (!cards) loadCards().then(c => { cards = c; re(); });
  const who = ctx.character?.() || 'bunny';
  const pic = r => { const c = r && wardrobeCard(who, r.id); return c ? trimmed(h, c) : picture(h, r); };
  const outfits = rows.filter(r => r.category === 'outfit'), accs = rows.filter(r => r.category === 'accessory');
  const card = (r, on, fn, title) => h('button', { class: 'libx-card wardrobe-card', 'aria-pressed': String(on), onclick: fn, title, 'data-id': r?.id || '' }, h('span', { class: 'pic' }, r ? pic(r) : trimmed(h, `chars/${who}.png`)), h('span', {}, r?.name || 'Default look'));
  return h('div', { class: 'ws three' },
    h('div', { class: 'col' }, h('h3', {}, 'Outfit'), h('div', { class: 'libx-grid' },
      card(null, !st.outfit, () => { setStage(ctx, { outfit: null }, ui.shotOnly); re(); }, 'No outfit'),
      ...outfits.map(r => card(r, st.outfit === r.data?.outfit, () => { setStage(ctx, { outfit: r.data?.outfit }, ui.shotOnly); re(); }, 'Brand black outfits from the clothing studio'))),
      outfits.length ? null : h('p', { class: 'hint' }, 'No outfits in this library yet.')),
    h('div', { class: 'col' }, h('h3', {}, 'Accessories'), accs.length ? h('div', { class: 'libx-grid' }, ...accs.map(r => card(r, (st.accessories || []).includes(r.data?.accessory), () => useItem(ctx, r, { shotOnly: ui.shotOnly }).then(re), 'Click to wear or take off'))) : h('p', { class: 'hint' }, 'No accessories in this library yet.')),
    h('div', { class: 'col' }, h('h3', {}, 'Mouth set'), (() => {
      const bare = id => String(id).replace(/^(mouthset|mouths?)-/, '');
      const mrow = id => rows.find(r => r.category === 'mouth_set' && (r.id === id || bare(r.id) === bare(id) || r.data?.set === id || r.data?.id === id));
      const pick = id => { setStage(ctx, { mouthSet: id }, ui.shotOnly); re(); };
      const mcard = (id, name, row, note) => h('button', { class: 'libx-card', 'aria-pressed': String((st.mouthSet || null) === id), onclick: () => pick(id), title: (note ? note + '. ' : '') + 'Speech mouth set for lip sync' },
        h('span', { class: 'pic' }, row ? picture(h, row) : h('span', { class: 'glyph' }, '◡')), h('span', {}, name));
      return h('div', { class: 'libx-grid', role: 'list' }, mcard(null, 'Doodle Studio\'s own', mrow('builtin')), ...(lib?.mouthSets || []).filter(m => bare(m.id) !== 'builtin').map(m => mcard(m.id, m.name, mrow(m.id), m.note)));
    })(), h('p', { class: 'hint' }, 'Outfits, accessories and mouth sets render in Blender. Scope (whole scene or this shot) follows the Set tab.')));
}

// ---------------------------------------------------------------- items in the shot: pick, place, move, time
export function itemsPanel(ctx) {
  const { h } = ctx;
  const project = ctx.project(), rows = libraryRows(), items = project.items || [];
  if (!rows.length) loadLibrary(ctx.api).then(() => ctx.rebuild());
  const selIdx = ctx.selectedItem();
  const list = h('div', { class: 'item-list' });
  if (!items.length) list.append(h('p', { class: 'hint' }, 'Nothing added yet. Add props, scenery, effects, reactions and storytime pieces from the Library tab: they show in the 3D view at once.'));
  for (const [i, it] of items.entries()) {
    const r = rows.find(x => x.id === it.id);
    const frameBox = h('input', { type: 'number', min: 0, max: project.length - 1, value: it.frame, style: 'width:62px', title: 'Frame it appears on', 'aria-label': 'Appears at frame' });
    frameBox.addEventListener('click', e => e.stopPropagation());
    frameBox.addEventListener('change', () => ctx.editItem(i, { frame: Math.max(0, Math.min(project.length - 1, Number(frameBox.value) || 0)) }, 'Item frame'));
    list.append(h('div', { class: 'item-row' + (selIdx === i ? ' sel' : ''), onclick: () => ctx.selectItem(i) },
      r?.preview ? h('img', { src: '/lib/' + r.preview, alt: '' }) : h('span', { class: 'glyph' }, glyphOf(it.id)),
      h('span', {}, h('b', {}, r?.name || it.id), h('br'), h('small', {}, `${it.hold ? (it.hold === 'L' ? 'Left hand' : 'Right hand') : it.at ? 'Placed' : 'Default spot'}${it.text ? ` · “${it.text}”` : ''}`)),
      h('span', { class: 'btns' }, h('span', { class: 'hint' }, 'F'), frameBox, h('button', { title: 'Go to its frame', onclick: e => { e.stopPropagation(); ctx.goto(it.frame); } }, 'Go'),
        h('button', { title: 'Remove it from the shot', onclick: e => { e.stopPropagation(); removeItem(ctx, i); ctx.selectItem(null); ctx.rebuild(); } }, '×'))));
  }
  const detail = h('div', { class: 'col' });
  const it = items[selIdx];
  if (it) {
    const r = rows.find(x => x.id === it.id);
    const xf = ctx.itemTransform(selIdx);
    const num = (k, i, step, tip) => { const n = h('input', { type: 'number', step, value: +(xf[k][i]).toFixed(k === 'rot' ? 0 : 3), title: tip }); n.addEventListener('change', () => { const v = xf[k].slice(); v[i] = Number(n.value) || 0; ctx.editItem(selIdx, { [k]: v }, 'Place item'); }); return n; };
    const holdSel = h('select', { 'aria-label': 'Held' }, h('option', { value: '' }, 'Stands in the scene'), h('option', { value: 'L' }, 'Left hand'), h('option', { value: 'R' }, 'Right hand'));
    holdSel.value = it.hold || ''; holdSel.addEventListener('change', () => ctx.editItem(selIdx, { hold: holdSel.value || undefined }, 'Hold'));
    const until = h('input', { type: 'number', min: 0, max: project.length, value: it.until ?? '', placeholder: 'end', style: 'width:62px', title: 'Last frame it shows on. Empty: to the end of the shot.' });
    until.addEventListener('change', () => ctx.editItem(selIdx, { until: until.value === '' ? undefined : Number(until.value) }, 'Item end'));
    detail.append(...[h('h3', {}, r?.name || it.id),
      r?.category === 'prop' ? h('label', { class: 'lbl-row' }, h('span', { class: 'lbl' }, 'Held'), holdSel) : null,
      it.hold ? h('p', { class: 'hint' }, 'Held props follow the hand. Pose the arm to move it; Blender fits the exact grip.') : h('div', { class: 'xform' },
        h('span', {}), h('span', {}, 'X'), h('span', {}, 'Y (depth)'), h('span', {}, 'Z (up)'),
        h('span', { title: 'Metres from the middle of the stage' }, 'Position'), num('at', 0, 0.05), num('at', 1, 0.05), num('at', 2, 0.05),
        h('span', { title: 'Degrees' }, 'Turn'), num('rot', 0, 5), num('rot', 1, 5), num('rot', 2, 5),
        h('span', {}, 'Size'), num('scale', 0, 0.05), num('scale', 1, 0.05), num('scale', 2, 0.05)),
      h('div', { class: 'lbl-row' }, h('span', { class: 'lbl' }, 'Shows from'), h('span', {}, `frame ${it.frame} to`), until),
      h('div', { class: 'row' }, it.hold ? null : h('button', { onclick: () => ctx.editItem(selIdx, { at: undefined, rot: undefined, scale: undefined }, 'Reset place'), title: 'Back to its default spot, turn and size' }, 'Reset place'),
        it.hold ? null : h('button', { onclick: () => ctx.dropItem(selIdx), title: 'Put it down on the floor' }, 'Drop to floor'),
        h('button', { onclick: () => ctx.duplicateItem(selIdx), title: 'Add another one beside it' }, 'Duplicate')),
      h('p', { class: 'hint' }, 'In the 3D view: drag the arrows to move, use the rail\'s Rotate and Scale tools (or W, E, R). View › Snapping makes moves step 5 cm and 5°.')].filter(Boolean));
  } else detail.append(h('h3', {}, 'Selected'), h('p', { class: 'hint' }, 'Click an item here or in the 3D view to place it.'));
  return h('div', { class: 'ws two' }, h('div', { class: 'col' }, h('h3', {}, `In ${project.code}`), list), detail);
}

// ---------------------------------------------------------------- speech mouth pictures (lip-sync shapes)
const speechCache = new Map();
export function speechThumb(data, sp, w = 96) {
  const key = data.species + ':s' + sp + ':' + w;
  if (speechCache.has(key)) return speechCache.get(key);
  const its = data.face.items.filter(it => it.role === 'speech' && it.speech === sp), c = document.createElement('canvas');
  c.width = w; c.height = Math.round(w / 1.25);
  const g = c.getContext('2d'); g.fillStyle = '#E0A64B'; g.fillRect(0, 0, c.width, c.height);
  let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
  for (const it of its) for (const p of it.outer || it.pts || []) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); z0 = Math.min(z0, p[1]); z1 = Math.max(z1, p[1]); }
  if (isFinite(x0)) {
    const span = Math.max(x1 - x0, (z1 - z0) * 1.25) * 2.2, k = c.width / span, cx = (x0 + x1) / 2, cz = (z0 + z1) / 2;
    g.fillStyle = '#1F1F1D';
    for (const it of its) { const p = new Path2D(); const loop = pts => pts.forEach((q, i) => (i ? p.lineTo : p.moveTo).call(p, c.width / 2 + (q[0] - cx) * k, c.height / 2 - (q[1] - cz) * k)); loop(it.outer || it.pts); p.closePath(); for (const hl of it.holes || []) { loop(hl); p.closePath(); } g.fill(p, 'evenodd'); }
  }
  const url = c.toDataURL(); speechCache.set(key, url); return url;
}
export function mouthGrid(ctx, current, pick) {
  const { h } = ctx, data = ctx.data(), S = data.face.speech;
  return h('div', { class: 'face-grid mouth-grid', role: 'list' }, ...S.map((n, i) => h('button', { 'aria-pressed': String(current === i), title: `${i === 0 ? 'The expression\'s own mouth' : n}. Click to key it at the playhead.`, onclick: () => pick(i) },
    i === 0 ? h('span', { class: 'glyph', style: 'aspect-ratio:1.25;display:grid;place-items:center;border:1px solid color-mix(in srgb,var(--fg) 30%,transparent);background:#E0A64B;color:#1F1F1D;font-size:30px' }, '☺') : h('img', { src: speechThumb(data, i), alt: '', style: 'width:100%;aspect-ratio:1.25;border:1px solid color-mix(in srgb,var(--fg) 30%,transparent)' }),
    h('span', {}, i === 0 ? 'Face default' : n))));
}

// ---------------------------------------------------------------- face pictures (the character's own drawings)
const faceCache = new Map();
export function faceThumb(data, e, gaze = 0, w = 120) {
  const key = data.species + ':' + e + ':' + gaze + ':' + w;
  if (faceCache.has(key)) return faceCache.get(key);
  const F = data.face, c = document.createElement('canvas');
  let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
  for (const it of F.items) if (it.face === e || it.face === undefined) for (const p of (it.pts || it.outer || [])) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); z0 = Math.min(z0, p[1]); z1 = Math.max(z1, p[1]); }
  if (!isFinite(x0)) { x0 = -1; x1 = 1; z0 = -1; z1 = 1; }
  const pad = 0.25 * (x1 - x0);
  x0 -= pad; x1 += pad; z0 -= pad; z1 += pad;
  c.width = w; c.height = Math.round(w / 1.25);
  const k = Math.min(c.width / (x1 - x0), c.height / (z1 - z0)), ox = (c.width - (x1 - x0) * k) / 2, oz = (c.height - (z1 - z0) * k) / 2;
  const X = x => ox + (x - x0) * k, Z = z => c.height - oz - (z - z0) * k;
  const g = c.getContext('2d');
  g.fillStyle = '#E0A64B'; g.fillRect(0, 0, c.width, c.height);
  g.fillStyle = g.strokeStyle = '#1F1F1D'; g.lineCap = g.lineJoin = 'round';
  for (const it of F.items) {
    const keep = it.role === 'eyes' ? it.face === e && (it.gaze === -1 || it.gaze === gaze) : it.role === 'mouth' ? it.face === e : false;
    if (!keep) continue;
    const p = new Path2D(), loop = (pts, close) => { pts.forEach((q, i) => (i ? p.lineTo : p.moveTo).call(p, X(q[0]), Z(q[1]))); if (close) p.closePath(); };
    if (it.kind === 'fill') { loop(it.outer, true); for (const hl of it.holes || []) loop(hl, true); g.fill(p, 'evenodd'); }
    else { loop(it.pts, it.closed); g.lineWidth = Math.max(1.2, (it.width || 11.32) * 0.01 * k); g.stroke(p); }
  }
  const url = c.toDataURL();
  faceCache.set(key, url);
  return url;
}
export function faceGrid(ctx, current, pick) {
  const { h } = ctx, data = ctx.data();
  return h('div', { class: 'face-grid', role: 'list' }, ...data.face.faces.map((n, i) => {
    const b = h('button', { 'aria-pressed': String(current === i), title: `${n}. Click to key it at the playhead.`, onclick: () => pick(i) }, h('img', { src: faceThumb(data, i), alt: '', style: 'width:100%;aspect-ratio:1.25;border:1px solid color-mix(in srgb,var(--fg) 30%,transparent)' }), h('span', {}, n));
    b.addEventListener('mouseenter', () => ctx.previewFace?.(i));
    b.addEventListener('mouseleave', () => ctx.previewEnd?.());
    return b;
  }));
}

// ---------------------------------------------------------------- a motion picker made of moving pictures
// (Co-stars › play a library motion): search, family chips and a grid of animated motion cards.
// Returns { el, value() }; onPick(row) runs when a card is picked, onUse(row) on a double click.
export const motionFamily = r => (/^Mocap/.test(r.sub || '') ? 'Mocap' : /^Performance/.test(r.sub || '') ? 'Performance' : r.kind === 'ds' ? 'Doodle' : 'Blender');
export function motionPicker(h, motions, opts = {}) {
  const st = { q: '', fam: 'All', sel: opts.value || null, n: opts.page || 24 };
  const fams = ['All', ...['Doodle', 'Performance', 'Mocap', 'Blender'].filter(f => motions.some(r => motionFamily(r) === f))];
  const q = h('input', { type: 'search', placeholder: 'Find a motion, e.g. wave, walk, shrug', 'aria-label': 'Find a motion', style: 'flex:1;min-width:10em' });
  const chips = h('div', { class: 'chips', role: 'tablist', 'aria-label': 'Motion family' });
  const grid = h('div', { class: 'libx-grid motion-pick', role: 'listbox', 'aria-label': 'Motions' });
  const more = h('button', { class: 'more', onclick: () => { st.n += 48; fill(); } }, 'Show more');
  const el = h('div', { class: 'motion-picker' }, h('div', { class: 'row', style: 'flex-wrap:wrap;gap:6px' }, q, chips), grid, more);
  const pool = () => { const s = st.q.toLowerCase(); return motions.filter(r => (st.fam === 'All' || motionFamily(r) === st.fam) && (!s || r.name.toLowerCase().includes(s) || (r.sub || '').toLowerCase().includes(s))); };
  // animated cards first: a motion with a moving picture reads at a glance
  const order = rs => [...rs.filter(r => hasAnim(r.id)), ...rs.filter(r => !hasAnim(r.id))];
  function fill() {
    chips.replaceChildren(...fams.map(f => h('button', { 'aria-pressed': String(st.fam === f), onclick: () => { st.fam = f; st.n = opts.page || 24; fill(); } }, f === 'Doodle' ? 'Hand-made' : f)));
    const rs = order(pool());
    grid.replaceChildren(...rs.slice(0, st.n).map(r => h('button', { class: 'libx-card', role: 'option', 'aria-pressed': String(st.sel === r.id), 'aria-selected': String(st.sel === r.id), title: `${r.name}${r.frames ? ` · ${r.frames} frames` : ''}. Click to pick, double-click to play it now`, 'data-id': r.id,
      onclick: () => { st.sel = r.id; for (const b of grid.children) b.setAttribute('aria-pressed', String(b.dataset.id === r.id)); opts.onPick?.(r); },
      ondblclick: () => { st.sel = r.id; opts.onUse?.(r); } }, h('span', { class: 'pic' }, picture(h, r)), h('span', {}, r.name))));
    if (!rs.length) grid.append(h('p', { class: 'hint' }, 'No motion matches. Try another word.'));
    more.style.display = rs.length > st.n ? '' : 'none';
    more.textContent = `Show more (${rs.length - st.n} left)`;
  }
  q.addEventListener('input', () => { st.q = q.value; st.n = opts.page || 24; fill(); });
  fill();
  return { el, value: () => st.sel };
}
