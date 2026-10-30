// The library and stage as pictures: every asset shows a large preview, hovering a motion or a
// face plays it on the character in the 3D view before you add it, and the stage (set, pieces,
// light, wardrobe) and the items in the shot are picked and edited from their pictures.
import { libraryRows, loadLibrary, useItem, setStage, removeItem, search, CATEGORIES, CHARACTERS } from './library.js';
import { stageOf } from './project.js';

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

export function picture(h, row, big = false) {
  if (row?.preview) return h('img', { src: '/lib/' + row.preview, alt: '', loading: 'lazy', draggable: 'false' });
  return h('span', { class: 'glyph', 'aria-hidden': 'true' }, row ? glyphOf(row.id) : '·');
}

// ---------------------------------------------------------------- the browser (Library tab, Animate › Motion library)
// opts.cats: the categories this browser offers (chips); opts.cat: start category
export function libraryBrowser(ctx, opts = {}) {
  const { h } = ctx;
  const cats = opts.cats || CATEGORIES.filter(c => c[0] !== 'motion').map(c => c);
  if (opts.cat) ui.cat = opts.cat;
  if (!cats.some(c => c[0] === ui.cat)) ui.cat = cats[0][0];
  const rows = libraryRows();
  const box = h('div', { class: 'libx library' });
  const main = h('div', {}), side = h('div', { class: 'libx-side' });
  const lib = ctx.lib?.();
  if (lib && !lib.found) main.append(h('p', { class: 'hint' }, `The Doodle Library was not found${lib.dir ? ' at ' + lib.dir : ''}. Effects, reactions, storytime pieces and sounds still work.`),
    h('div', { class: 'row' }, h('button', { onclick: () => ctx.api('pick-library', {}).then(() => loadLibrary(ctx.api, true)).then(ctx.rebuild).catch(e => ctx.toast(e.message)) }, 'Find library folder…')));
  const q = h('input', { type: 'search', placeholder: ui.cat === 'motion' ? 'Search motions, e.g. wave, walk, shrug' : 'Search, e.g. mug, tree, rain', value: ui.q, 'aria-label': 'Search the library' });
  const top = h('div', { class: 'libx-top' }, q);
  if (cats.length > 1 && !opts.noChips) top.append(h('div', { class: 'chips' }, ...cats.map(([id, n]) => h('button', { 'aria-pressed': String(ui.cat === id), onclick: () => { ui.cat = id; ui.sel = null; ui.page = 1; ctx.rebuild(); } }, n))));
  if (ui.cat === 'motion') {
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
    const found = search(rows, { category: ui.cat, query: ui.q, limit: LIMIT + 1 });
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
  main.append(top, grid);
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
  const scope = h('div', { class: 'chips' }, h('button', { 'aria-pressed': String(!ui.shotOnly), onclick: () => { ui.shotOnly = false; re(); }, title: 'Changes apply to every shot' }, 'Whole scene'),
    h('button', { 'aria-pressed': String(ui.shotOnly), onclick: () => { ui.shotOnly = true; re(); }, title: 'Changes apply to this shot only, on top of the scene' }, `${project.code} only`));
  const chars = h('div', { class: 'chips' }, ...CHARACTERS.map(([id, n]) => h('button', { 'aria-pressed': String((scene.character || 'bunny') === id), onclick: () => ctx.setCharacter(id) }, n)));
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
          h('span', { class: 'pic' }, picture(h, r)), h('span', {}, r.name), h('small', {}, r.sub || ''))));
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
  const right = h('div', { class: 'col' }, h('h3', {}, 'Character'), chars, pieces, h('h3', {}, 'Light'),
    sel('Time', 'time', [['', 'Default'], ...TIMES.map(t => [t, cap(t)])], st.time), sel('Sky', 'sky', [['', 'Default'], ...SKIES.map(t => [t, cap(t)])], st.sky),
    check('Cel shadows', st.shadows, v => ({ shadows: v }), 'Flat cel shadows on the set. Off unless you turn it on.'),
    check('Halftone dots in the shadows', st.halftone, v => (v ? { halftone: true, shadows: true } : { halftone: false }), 'Comic-book halftone: the cel shadows become ink dots. Turns cel shadows on.'),
    h('p', { class: 'hint' }, 'Light, sky and shadows show in the Blender render; the 3D view keeps the flat Doodle look so posing stays readable.'));
  return h('div', { class: 'ws two' }, left, right);
}

export function wardrobePanel(ctx) {
  const { h } = ctx;
  const scene = ctx.scene(), project = ctx.project(), st = stageOf(scene, project), rows = libraryRows(), lib = ctx.lib?.();
  const re = () => ctx.rebuild();
  const outfits = rows.filter(r => r.category === 'outfit'), accs = rows.filter(r => r.category === 'accessory');
  const card = (r, on, fn, title) => h('button', { class: 'libx-card', 'aria-pressed': String(on), onclick: fn, title }, h('span', { class: 'pic' }, picture(h, r)), h('span', {}, r?.name || 'None'));
  return h('div', { class: 'ws three' },
    h('div', { class: 'col' }, h('h3', {}, 'Outfit'), h('div', { class: 'libx-grid' },
      card(null, !st.outfit, () => { setStage(ctx, { outfit: null }, ui.shotOnly); re(); }, 'No outfit'),
      ...outfits.map(r => card(r, st.outfit === r.data?.outfit, () => { setStage(ctx, { outfit: r.data?.outfit }, ui.shotOnly); re(); }, 'Brand black outfits from the clothing studio'))),
      outfits.length ? null : h('p', { class: 'hint' }, 'No outfits in this library yet.')),
    h('div', { class: 'col' }, h('h3', {}, 'Accessories'), accs.length ? h('div', { class: 'libx-grid' }, ...accs.map(r => card(r, (st.accessories || []).includes(r.data?.accessory), () => useItem(ctx, r, { shotOnly: ui.shotOnly }).then(re), 'Click to wear or take off'))) : h('p', { class: 'hint' }, 'No accessories in this library yet.')),
    h('div', { class: 'col' }, h('h3', {}, 'Mouths'), (() => {
      const s = h('select', { 'aria-label': 'Mouths' }, h('option', { value: '' }, 'Doodle Studio\'s own'), ...(lib?.mouthSets || []).map(m => h('option', { value: m.id }, m.name)));
      s.value = st.mouthSet || ''; s.addEventListener('change', () => { setStage(ctx, { mouthSet: s.value || null }, ui.shotOnly); re(); });
      return h('label', { class: 'lbl-row', title: 'Speech mouth set for lip sync' }, h('span', { class: 'lbl' }, 'Mouth set'), s);
    })(), h('p', { class: 'hint' }, 'Outfits, accessories and mouth sets render in Blender. Scope (whole scene or this shot) follows the Set & light section.')));
}

// ---------------------------------------------------------------- items in the shot: pick, place, move, time
export function itemsPanel(ctx) {
  const { h } = ctx;
  const project = ctx.project(), rows = libraryRows(), items = project.items || [];
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
