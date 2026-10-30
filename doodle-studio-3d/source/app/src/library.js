// Library tab: the character, the stage (set, light, outfit, accessories, mouth set)
// and the Doodle Library on this PC (motions, faces, props, scenery, effects,
// storytime pieces). Motions and faces become keys on the timeline; everything else
// is stored on the shot and built in Blender by the library's own add-on, so the
// render matches what the add-on makes in Blender.
import { valueAt, setKey, stageOf, DISCRETE } from './project.js';

export const CHARACTERS = [['bunny', 'Bunny'], ['koala', 'Koala'], ['frog', 'Frog']];
const TIMES = ['day', 'golden', 'night'];
const SKIES = ['day', 'sunset', 'stars', 'storm'];
const cap = s => s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');

// Blender-side pieces that are not library rows (lists match the add-on)
export const EXTRA = [
  ...['rain', 'downpour', 'splashes', 'snow', 'leaves', 'petals', 'wind', 'speed_lines', 'steam', 'smoke', 'sparkles', 'confetti', 'streamers', 'fireworks', 'dust', 'poof', 'sparkle_burst']
    .map(k => ({ id: 'fx:' + k, name: cap(k), category: 'effect', sub: 'Effects' })),
  ...['question', 'exclaim', 'sweat', 'heart', 'anger', 'zzz', 'star', 'lightbulb', 'note', 'dizzy', 'tear', 'sparkle']
    .map(k => ({ id: 'react:' + k, name: cap(k), category: 'reaction', sub: 'Reaction pops' })),
  { id: 'story:time_skip', name: 'Time skip card', category: 'story', sub: 'Storytime', ask: 'Card text', def: '3 hours later' },
  { id: 'story:chat', name: 'Chat bubbles', category: 'story', sub: 'Storytime', ask: 'Message', def: 'hi' },
  { id: 'story:label', name: 'Pinned label', category: 'story', sub: 'Storytime', ask: 'Label text', def: 'Me' },
  { id: 'story:journey', name: 'Journey map', category: 'story', sub: 'Storytime', ask: 'Stops, separated by commas', def: 'Home, School' },
  { id: 'text:headline', name: '3D headline', category: 'story', sub: 'Storytime', ask: 'Headline text', def: 'WAIT WHAT' },
  { id: 'story:end_screen', name: 'End screen', category: 'story', sub: 'Storytime' },
  { id: 'story:horror', name: 'Horror mode', category: 'story', sub: 'Storytime' },
  ...['pop', 'message', 'typing', 'whoosh', 'boing', 'click', 'bell', 'pin', 'draw', 'horror_drone', 'thunder', 'sting']
    .map(k => ({ id: 'sound:' + k, name: cap(k), category: 'sound', sub: 'Story sounds' })),
];
export const CATEGORIES = [['motion', 'Motions'], ['expression', 'Faces'], ['prop', 'Props'], ['scenery', 'Scenery'], ['effect', 'Effects'], ['reaction', 'Reactions'], ['story', 'Storytime'], ['sound', 'Sounds']];

let lib = null, loading = null;
const ui = { cat: 'motion', q: '', mirror: false, blend: 0, hold: '', shotOnly: false };

export async function loadLibrary(api, force = false) {
  if (lib && !force) return lib;
  if (!loading || force) loading = api('library').then(r => { lib = { ...r, items: [...r.items, ...EXTRA] }; return lib; }).catch(e => { lib = { found: false, error: e.message, items: EXTRA, mouthSets: [] }; return lib; }).finally(() => { loading = null; });
  return loading;
}
export const libraryRows = () => lib?.items || [];

export function search(rows, { category, query, limit = 60 } = {}) {
  const words = String(query || '').toLowerCase().split(/\s+/).filter(Boolean);
  return rows.filter(r => (!category || r.category === category) &&
    words.every(w => (r.name + ' ' + (r.sub || '') + ' ' + (r.tags || []).join(' ') + ' ' + r.id).toLowerCase().includes(w))).slice(0, limit);
}

// ---------------------------------------------------------------- using an item
const SWAP = /^(arm|elbow|wrist|leg|knee|foot|ear)([LR])(.*)$/;
const NEGATE = new Set(['turn', 'headYaw', 'rot', 'bodyTilt', 'torsoTwist', 'bodyX', 'bodyRot']);
const RELATIVE = new Set(['bodyX', 'bodyY', 'depth', 'turn']);   // a motion moves from wherever the character stands

export async function useItem(ctx, ref, opts = {}) {
  await loadLibrary(ctx.api);
  const row = typeof ref === 'string' ? libraryRows().find(r => r.id === ref) : ref;
  if (!row) throw Error(`No library item ${ref}. library_list finds ids.`);
  const project = ctx.project(), f0 = opts.frame ?? ctx.frame();
  if (row.category === 'motion') return useMotion(ctx, row, f0, !!opts.mirror, Math.max(0, Math.round(opts.blend || 0)));
  if (row.category === 'expression') return useFace(ctx, row, f0);
  if (row.category === 'set') return setStage(ctx, { set: row.data?.room || row.id.replace(/^set-/, '') }, opts.shotOnly);
  if (row.category === 'outfit') return setStage(ctx, { outfit: row.data?.outfit }, opts.shotOnly);
  if (row.category === 'accessory') {
    const st = stageOf(ctx.scene(), project), a = new Set(st.accessories || []);
    a.has(row.data.accessory) ? a.delete(row.data.accessory) : a.add(row.data.accessory);
    return setStage(ctx, { accessories: [...a] }, opts.shotOnly);
  }
  const item = { id: row.id, frame: f0 };
  if (row.category === 'prop' && (opts.hold === 'L' || opts.hold === 'R')) item.hold = opts.hold;
  if (opts.at) item.at = opts.at;
  if (row.ask) {
    let text = opts.text ?? (opts.prompt === false ? row.def : prompt(row.ask, row.def));
    if (text == null) return null;
    text = String(text);
    if (row.id === 'story:journey') item.stops = text.split(',').map(s => s.trim()).filter(Boolean);
    else item.text = text;
  } else if (opts.text) item.text = String(opts.text);
  ctx.pushUndo();
  (project.items ||= []).push(item);
  project.items.sort((a, b) => a.frame - b.frame);
  ctx.changed();
  return { added: item, items: project.items };
}

// blend > 0 crossfades the clip in over that many frames from whatever was already
// animated there (clip blending), instead of cutting straight to its first pose
async function useMotion(ctx, row, f0, mirror, blend = 0) {
  const m = await ctx.api('library-motion', { id: row.id });
  const project = ctx.project(), known = new Set(ctx.trackIds()), names = ctx.data().face.gazes;
  ctx.pushUndo();
  const base = {};
  for (const id of RELATIVE) base[id] = valueAt(project, id, f0);
  let first = null;
  const was = {}, mix = f => { const t = Math.min(1, f / blend); return t * t * (3 - 2 * t); };
  if (blend) for (const id of known) if (project.tracks[id]?.length && !DISCRETE.has(id)) was[id] = Array.from({ length: blend + 1 }, (_, i) => valueAt(project, id, f0 + i));
  const written = new Set();
  for (const [f, vals] of m.poses) {
    for (let [id, v] of Object.entries(vals)) {
      if (mirror) {
        const s = SWAP.exec(id);
        if (s) id = s[1] + (s[2] === 'L' ? 'R' : 'L') + s[3];
        if (NEGATE.has(id)) v = -v;
        if (id === 'gaze') { const n = names[v] || ''; const j = names.indexOf(n.replace(/Left|Right/, w => w === 'Left' ? 'Right' : 'Left')); if (j >= 0) v = j; }
      }
      if (!known.has(id)) continue;
      if (RELATIVE.has(id)) { first ??= {}; if (!(id in first)) first[id] = v; v = base[id] + v - first[id]; }
      setKey(project, id, f0 + f, v);
      written.add(id);
    }
  }
  // crossfade, baked frame by frame over the window so sparse clip keys blend evenly
  for (const id of written) {
    if (!was[id]) continue;
    const clipV = was[id].map((_, f) => valueAt(project, id, f0 + f));
    clipV.forEach((v, f) => setKey(project, id, f0 + f, +(was[id][f] + (v - was[id][f]) * mix(f)).toFixed(3), 'linear'));
  }
  const end = f0 + m.frames;
  if (end > project.length) project.length = end;
  ctx.changed(true);
  return { motion: row.id, name: row.name, from: f0, to: end, mirrored: mirror, blend, length: project.length };
}

function useFace(ctx, row, f) {
  const d = row.data || {}, F = ctx.data().face, project = ctx.project();
  const byName = n => F.faces.findIndex(x => x.toLowerCase() === String(n || '').toLowerCase());
  ctx.pushUndo();
  const set = {};
  let e = byName(d.expression_name);
  if (e < 0 && d.expression != null) e = d.expression;
  if (e < 0) e = byName(row.name);
  if (e >= 0 && e < F.faces.length) set.expression = e;
  if (d.gaze != null && d.gaze >= 0) set.gaze = d.gaze;
  if (d.blink != null) set.blink = d.blink;
  if (d.speech_mouth != null) set.mouth = d.speech_mouth;
  Object.assign(set, d.ears || {});
  for (const [id, v] of Object.entries(set)) setKey(project, id, f, v, id in (d.ears || {}) ? 'ease' : 'hold');
  ctx.changed(true);
  return { face: row.id, keyed: set, frame: f };
}

// ---------------------------------------------------------------- stage
export function setStage(ctx, patch, shotOnly = false) {
  const scene = ctx.scene(), project = ctx.project();
  const target = shotOnly ? (project.stage ||= {}) : (scene.stage ||= {});
  ctx.pushUndo();
  for (const [k, v] of Object.entries(patch)) {
    if (k === 'set' && v !== target.set) delete target.setProps;   // pieces belong to their room
    if (v == null || v === '' || v === false && k !== 'shadows') delete target[k]; else target[k] = v;
  }
  ctx.changed();
  return { stage: stageOf(scene, project), scope: shotOnly ? project.code : 'scene' };
}

export function removeItem(ctx, i) {
  const project = ctx.project();
  if (!project.items?.[i]) throw Error('No item ' + i);
  ctx.pushUndo();
  project.items.splice(i, 1);
  ctx.changed();
  return { items: project.items };
}

// ---------------------------------------------------------------- panel
export function libraryPanel(ctx) {
  const { h } = ctx;
  const box = h('div', { class: 'library' });
  const scene = ctx.scene(), project = ctx.project(), st = stageOf(scene, project);
  const rows = libraryRows();
  const rebuild = () => ctx.rebuild();

  // character
  box.append(h('h3', {}, 'Character'), h('div', { class: 'chips' }, ...CHARACTERS.map(([id, n]) =>
    h('button', { 'aria-pressed': String((scene.character || 'bunny') === id), onclick: () => ctx.setCharacter(id) }, n))));

  // stage
  const sel = (label, key, opts, value, title) => {
    const s = h('select', { 'aria-label': label }, ...opts.map(([v, n]) => h('option', { value: v }, n)));
    s.value = value ?? '';
    s.addEventListener('change', () => { setStage(ctx, { [key]: s.value || null }, ui.shotOnly); rebuild(); });
    return h('label', { class: 'ctl', style: 'grid-template-columns:6.5em 1fr', title: title || '' }, label, s);
  };
  const sets = rows.filter(r => r.category === 'set');
  const scope = h('div', { class: 'chips' }, h('button', { 'aria-pressed': String(!ui.shotOnly), onclick: () => { ui.shotOnly = false; rebuild(); }, title: 'Changes apply to every shot' }, 'Whole scene'),
    h('button', { 'aria-pressed': String(ui.shotOnly), onclick: () => { ui.shotOnly = true; rebuild(); }, title: 'Changes apply to this shot only, on top of the scene' }, `${project.code} only`));
  box.append(h('h3', {}, 'Stage'), scope,
    sel('Set', 'set', [['', 'None (plain backdrop)'], ...sets.map(r => [r.data?.room || r.id.replace(/^set-/, ''), `${r.name} · ${r.sub}`])], st.set));
  const setRow = sets.find(r => (r.data?.room || r.id.replace(/^set-/, '')) === st.set);
  if (setRow?.data?.props?.length) {
    const on = { ...Object.fromEntries(setRow.data.props.map(p => [p.id, p.on !== false])), ...(st.setProps || {}) };
    box.append(h('div', { class: 'chips', title: 'Pieces of this set: switch off what the shot does not need' }, ...setRow.data.props.map(p =>
      h('button', { 'aria-pressed': String(!!on[p.id]), onclick: () => { setStage(ctx, { setProps: { ...(st.setProps || {}), [p.id]: !on[p.id] } }, ui.shotOnly); rebuild(); } }, p.label))));
  }
  box.append(h('div', { class: 'row' },
    sel('Time', 'time', [['', 'Default'], ...TIMES.map(t => [t, cap(t)])], st.time),
    sel('Sky', 'sky', [['', 'Default'], ...SKIES.map(t => [t, cap(t)])], st.sky)));
  const shadow = h('input', { type: 'checkbox' });
  shadow.checked = !!st.shadows;
  shadow.addEventListener('change', () => { setStage(ctx, { shadows: shadow.checked }, ui.shotOnly); rebuild(); });
  box.append(h('label', { class: 'ctl', style: 'grid-template-columns:auto 1fr', title: 'Flat cel shadows on the set. Off unless you turn it on.' }, shadow, 'Cel shadows'));
  const outfits = rows.filter(r => r.category === 'outfit'), accs = rows.filter(r => r.category === 'accessory');
  box.append(sel('Outfit', 'outfit', [['', 'None'], ...outfits.map(r => [r.data.outfit, r.name])], st.outfit, 'Brand black outfits from the clothing studio'));
  if (accs.length) box.append(h('div', { class: 'chips', title: 'Accessories: click to wear or take off' }, ...accs.map(r =>
    h('button', { 'aria-pressed': String((st.accessories || []).includes(r.data.accessory)), onclick: () => useItem(ctx, r, { shotOnly: ui.shotOnly }).then(rebuild) }, r.name))));
  box.append(sel('Mouths', 'mouthSet', [['', 'Doodle Studio\'s own'], ...(lib?.mouthSets || []).map(m => [m.id, m.name])], st.mouthSet, 'Speech mouth set for lip sync'));

  // library
  box.append(h('h3', {}, 'Library'));
  if (lib && !lib.found) {
    box.append(h('p', { class: 'hint' }, `The Doodle Library was not found${lib.dir ? ' at ' + lib.dir : ''}. Effects, reactions, storytime pieces and sounds still work.`),
      h('div', { class: 'row' }, h('button', { onclick: () => ctx.api('pick-library', {}).then(() => loadLibrary(ctx.api, true)).then(rebuild).catch(e => ctx.toast(e.message)) }, 'Find library folder…')));
  }
  box.append(h('div', { class: 'chips' }, ...CATEGORIES.map(([id, n]) => h('button', { 'aria-pressed': String(ui.cat === id), onclick: () => { ui.cat = id; rebuild(); } }, n))));
  const q = h('input', { type: 'search', placeholder: 'Search, e.g. wave, walk, mug', value: ui.q, 'aria-label': 'Search the library' });
  const list = h('div', { class: 'lib-list', role: 'list' });
  const opts = h('div', { class: 'row' });
  if (ui.cat === 'motion') {
    const m = h('input', { type: 'checkbox' }); m.checked = ui.mirror; m.addEventListener('change', () => { ui.mirror = m.checked; });
    const b = h('input', { type: 'number', min: 0, max: 60, step: 1, value: ui.blend, style: 'width:52px', 'aria-label': 'Blend in frames' }); b.addEventListener('change', () => { ui.blend = Math.max(0, Number(b.value) || 0); });
    opts.append(h('label', { class: 'hint', title: 'Swap left and right' }, m, ' Mirror'), h('label', { class: 'hint', title: 'Clip blending: crossfade from the animation already there into the clip over this many frames. 0 cuts straight in.' }, 'Blend in ', b, ' frames'));
  }
  if (ui.cat === 'prop') {
    const s = h('select', { 'aria-label': 'Hold' }, h('option', { value: '' }, 'Not held'), h('option', { value: 'L' }, 'In left hand'), h('option', { value: 'R' }, 'In right hand'));
    s.value = ui.hold; s.addEventListener('change', () => { ui.hold = s.value; });
    opts.append(s);
  }
  const fill = () => {
    const found = search(rows, { category: ui.cat, query: ui.q });
    list.replaceChildren(...found.map(r => h('button', { class: 'lib-item', role: 'listitem', title: (r.description || r.sub || '') + '\nClick to add at the playhead',
      onclick: () => useItem(ctx, r, { mirror: ui.mirror, blend: ui.blend, hold: ui.hold, shotOnly: ui.shotOnly }).then(res => { if (res) ctx.toast(`Added ${r.name}`); rebuild(); }).catch(e => ctx.toast(e.message, 4000)) },
      r.preview ? h('img', { src: '/lib/' + r.preview, alt: '', loading: 'lazy' }) : null, h('span', {}, r.name, h('small', {}, r.sub || '', r.frames ? ` · ${r.frames} f` : '')))));
    if (!found.length) list.append(h('p', { class: 'hint' }, lib ? 'Nothing matches.' : 'Loading the library…'));
  };
  q.addEventListener('input', () => { ui.q = q.value; fill(); });
  box.append(q, opts, list);
  fill();
  if (!lib) loadLibrary(ctx.api).then(rebuild);

  // items in this shot
  const items = project.items || [];
  box.append(h('h3', {}, `In ${project.code}`));
  if (!items.length) box.append(h('p', { class: 'hint' }, 'Props, effects and storytime pieces you add show here. They are built in Blender when the shot renders.'));
  for (const [i, it] of items.entries()) {
    const row = rows.find(r => r.id === it.id);
    box.append(h('div', { class: 'row lib-placed' }, h('span', { style: 'flex:1' }, `F${it.frame} · ${row?.name || it.id}${it.hold ? ` (${it.hold === 'L' ? 'left' : 'right'} hand)` : ''}${it.text ? ` “${it.text}”` : ''}`),
      h('button', { onclick: () => ctx.goto(it.frame), title: 'Go to its frame' }, 'Go'), h('button', { onclick: () => { removeItem(ctx, i); rebuild(); }, title: 'Remove' }, '×')));
  }
  box.append(h('p', { class: 'hint' }, 'Motions and faces become keys you can edit. Sets, outfits, props and effects come from the Doodle Library and show in the Blender render; the viewport shows the character and camera.'));
  return box;
}
