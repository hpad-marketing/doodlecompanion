// Materials tab: choose a look (Ink & Mustard, clay, cel toon, soft vinyl, felt, paper, ceramic, or
// one from a look add-on such as ClayDoh), a colour palette, and what wears it: the whole scene,
// the characters, the set, every prop, or the prop picked in the 3D view. The look is drawn by
// Blender (lib/materials.py) in renders and in Open in Blender; the 3D view keeps its ink look.
//
// Data: scene.materials = { layers: { scene, character, set, props }, light } for every shot;
// shot.materials.layers[k] overrides one target for one shot (null = clear it for this shot);
// item.material = a layer for one prop. A layer: { look, addon, params, palette, ink, color, bunny, outfit }.
import { myPalettes, dropPalette, paletteMaker } from './palettes.js';
import { MATERIAL_TARGETS, materialsOf } from './project.js';

export const TARGETS = [['scene', 'Whole scene', 'Every character, the set and every prop'], ['character', 'Characters', 'The lead and co-stars, outfits included'],
  ['set', 'Set', 'The room or place: walls, floor and every set piece'], ['props', 'All props', 'Every prop and scenery piece placed in the shot'],
  ['item', 'Picked prop', 'Only the prop picked in the 3D view (click it there first)']];
const LIGHT = [['key', 'Key light', 0, 8, 0.1, 3.2], ['fill', 'Fill', 0, 1, 0.05, 0.3], ['ambient', 'Ambient', 0, 1.5, 0.05, 0.5],
  ['height', 'Light height (°)', 5, 85, 1, 28], ['angle', 'Light side (°)', -90, 90, 1, 40], ['softness', 'Softness', 0, 1, 0.05, 0.5]];

export const ui = { target: 'scene', scope: 'scene' };
let cache = null, loading = null;

export function loadLooks(api, force = false) {
  if (cache && !force) return Promise.resolve(cache);
  if (!loading || force) loading = api('looks-list', {}).then(r => (cache = r)).finally(() => { loading = null; });
  return loading;
}
export const looksInfo = () => cache;

// where a target's layer lives for the current scope; item = the picked prop
function slot(ctx, target) {
  const scene = ctx.scene(), shot = ctx.project();
  if (target === 'item') {
    const i = ctx.selectedItem();
    const it = i != null ? (shot.items || [])[i] : null;
    return { get: () => it?.material || null, set: v => { if (!it) return; if (v) it.material = v; else delete it.material; }, ok: !!it };
  }
  if (ui.scope === 'shot') {
    return { get: () => (shot.materials?.layers && target in shot.materials.layers ? shot.materials.layers[target] : scene.materials?.layers?.[target] || null),
      set: v => { shot.materials = shot.materials || {}; shot.materials.layers = shot.materials.layers || {}; shot.materials.layers[target] = v; }, ok: true };
  }
  return { get: () => scene.materials?.layers?.[target] || null,
    set: v => { scene.materials = scene.materials || {}; scene.materials.layers = scene.materials.layers || {}; if (v) scene.materials.layers[target] = v; else delete scene.materials.layers[target]; }, ok: true };
}

// the layer that would apply to a target in this shot (narrower wins), for the chips
function effective(ctx, target) {
  const m = materialsOf(ctx.scene(), ctx.project());
  if (target === 'item') { const s = slot(ctx, 'item'); return s.get() || m?.layers.props || m?.layers.scene || null; }
  return m?.layers[target] || (target !== 'scene' ? m?.layers.scene : null) || null;
}

const lookName = (layer) => {
  if (!layer?.look) return 'Ink & Mustard';
  const l = cache?.looks.find(x => x.id === layer.look && x.addon === (layer.addon || 'doodle_looks'));
  return l ? l.name : layer.look;
};

// textured looks have no body outline unless it is switched on; the flat look keeps it unless switched off
export const inkOn = (layer, look) => layer.ink != null ? layer.ink !== false : (look?.id ?? 'ink-mustard') === 'ink-mustard';

// which targets have their outline off, as the render does it (lib/materials.py): the 3D view follows
const outlineOff = L => !!L?.look && (L.ink != null ? L.ink === false : L.look !== 'ink-mustard');
export function outlinesOff(m) {
  const l = m?.layers || {}, props = outlineOff(l.props || l.scene);
  return { character: outlineOff(l.character || l.scene), set: outlineOff(l.set || l.scene), item: it => (it.material ? outlineOff(it.material) : props) };
}

// the palette in the 3D view: the same colour for each piece as the render (_piece_colour in lib/materials.py)
const crc32 = s => { let c = ~0; for (let i = 0; i < s.length; i++) { c ^= s.charCodeAt(i); for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xEDB88320 & -(c & 1)); } return ~c >>> 0; };
const FIRST_COLOUR = ['rug', 'carpet', 'mat', 'cushion', 'pillow', 'vase', 'clock', 'lamp'];
const pieceColour = (pal, key) => {
  if (FIRST_COLOUR.some(w => String(key).toLowerCase().includes(w))) return pal.accent;
  const list = pal.pieces?.length ? pal.pieces : [pal.accent];
  return list[crc32(String(key)) % list.length];
};
export function stagePaint(m, items, api, ready) {
  const l = m?.layers || {};
  const parts = m?.parts || {};
  if (!Object.values(l).some(Boolean) && !items.some(it => it.material || it.parts) && !Object.keys(parts).length) return null;
  if (!cache) { loadLooks(api).then(ready, () => {}); return null; }
  const pal = L => { const brand = cache.palettes.find(p => p.id === 'brand'); return typeof L.palette === 'object' && L.palette ? { ...brand, ...L.palette } : cache.palettes.find(p => p.id === (L.palette || 'brand')) || brand; };
  const S = l.set || l.scene || (Object.keys(parts).length ? { palette: 'brand' } : null), P = pal(S || {});
  const set = S ? { wall: S.color || P.wall, floor: S.color || P.floor, ceiling: S.color || P.ceiling, piece: id => S.color || pieceColour(P, id) } : null;
  const item = it => { const L = it.material || l.props || l.scene; return L ? L.color || pieceColour(pal(L), it.id) : null; };
  // a model's parts take the palette in turn, from its own colour (Painter.segment in lib/materials.py)
  const turn = (p, hex) => { const list = p.pieces || [], i = list.indexOf(hex); return list.length < 2 ? null : list.map((_, n) => list[(Math.max(i, 0) + n) % list.length]); };
  const itemParts = it => { const L = it.material || l.props || l.scene; if (!L) return null; const p = pal(L), hex = pieceColour(p, it.id); return { colours: turn(p, hex), accent: turn(p, hex) && p.accent }; };
  const C = l.character || l.scene, cp = C && pal(C);
  return { parts, set: set && { ...set, accent: turn(P, P.pieces?.[0]) && P.accent, colours: hex => turn(P, S.color ? pieceColour(P, 'x') : hex) }, item, itemParts, char: C && { body: C.bunny || cp.character, outfit: C.outfit || (cp.outfit !== cp.ink ? cp.outfit : null) },
    sig: JSON.stringify([S?.palette, S?.color, l.props, l.scene?.palette, C?.palette, parts]) };
}

export function setLayer(ctx, target, patch, label = 'Material') {
  const s = slot(ctx, target);
  if (!s.ok) throw Error('Pick a prop in the 3D view first');
  ctx.pushUndo(label);
  const cur = s.get();
  const next = patch === null ? null : { palette: 'brand', ...(cur || {}), ...patch };
  if (next && next.look === 'ink-mustard' && (next.palette || 'brand') === 'brand' && !next.color && next.ink == null && !next.bunny && !next.outfit) s.set(target === 'scene' || ui.scope === 'scene' ? null : next);
  else s.set(next);
  ctx.changed();
  return next;
}

function swatches(h, p) {
  const cols = [p.wall, p.floor, ...(p.pieces || []).slice(0, 3), p.accent, p.character];
  return h('span', { class: 'mat-swatch' }, ...cols.map(c => h('i', { style: `background:${c}` })));
}

export function materialsPanel(ctx) {
  const { h } = ctx;
  const root = h('div', { class: 'mat' });
  if (!cache) {
    root.append(h('p', { class: 'hint' }, 'Loading the looks…'));
    loadLooks(ctx.api).then(() => ctx.rebuild()).catch(e => { root.replaceChildren(h('p', { class: 'hint' }, 'Could not list the looks: ' + e.message)); });
    return root;
  }
  if (ui.target === 'item' && ctx.selectedItem() == null) ui.target = 'scene';
  const s = slot(ctx, ui.target);
  const layer = s.get() || {};
  const cur = cache.looks.find(l => l.id === (layer.look || 'ink-mustard') && l.addon === (layer.addon || 'doodle_looks')) || cache.looks[0];
  const set = (patch, label) => { try { setLayer(ctx, ui.target, patch, label); ctx.rebuild(); } catch (e) { ctx.toast(e.message); } };

  // 1. what wears it, and for how long
  const picked = ctx.selectedItem();
  const targets = h('div', { class: 'chips mat-row', role: 'tablist', 'aria-label': 'What wears the material' },
    h('span', { class: 'sub-label' }, 'Apply to:'),
    ...TARGETS.map(([id, name, tip]) => h('button', { role: 'tab', 'aria-pressed': String(ui.target === id), disabled: id === 'item' && picked == null,
      title: `${tip}. Now: ${lookName(effective(ctx, id))}`, onclick: () => { ui.target = id; ctx.rebuild(); } },
    name, h('small', { class: 'mat-now' }, ' · ' + lookName(effective(ctx, id))))),
    h('span', { class: 'sub-label', style: 'margin-left:12px' }, 'For:'),
    ...[['scene', 'Every shot'], ['shot', 'This shot only']].map(([id, n]) => h('button', { 'aria-pressed': String(ui.scope === id), disabled: ui.target === 'item',
      title: id === 'shot' ? 'Only this shot changes; the other shots keep the scene\'s materials' : 'All shots in the scene', onclick: () => { ui.scope = id; ctx.rebuild(); } }, n)));
  root.append(targets);
  const own = s.get();
  const eff = effective(ctx, ui.target);
  root.append(h('p', { class: 'hint' }, !own && ui.target !== 'scene' && eff
    ? `${TARGETS.find(t => t[0] === ui.target)[1]} wear the ${ui.target === 'item' ? 'props\' or scene\'s' : 'Whole scene\'s'} look (${lookName(eff)}) until you pick one here.`
    : 'Blender draws the material in renders and in Open in Blender; the 3D view shows the colours and outlines, not the texture.'));

  // 2. looks, as pictures
  const lookCard = l => {
    const off = l.status === 'failed' || l.status === 'testing';
    const btn = h('button', { class: 'libx-card mat-card', role: 'listitem', 'aria-pressed': String(cur && l.key === cur.key), disabled: off,
      title: `${l.name}${l.source !== 'built-in' ? ` (from ${l.addonName})` : ''}. ${l.about}${l.status === 'failed' ? `\nIts test frame failed: ${l.error}` : ''}`,
      onclick: () => {
        if (l.status === 'untested') return testLook(ctx, l);
        const patch = { look: l.id, addon: l.addon };
        if (!cur || l.key !== cur.key) patch.params = {};
        set(patch, `Material: ${l.name}`);
      } },
    h('span', { class: 'pic', style: 'aspect-ratio:2/3' }, l.preview ? h('img', { src: l.preview, alt: '', draggable: 'false' }) : h('span', { class: 'glyph' }, l.status === 'testing' ? '…' : '?')),
    h('span', {}, l.name), h('small', {}, l.source === 'built-in' ? (l.flat ? 'flat, unlit' : 'lit') : l.status === 'ok' ? l.addonName : l.status === 'untested' ? 'Click to test it' : l.status === 'testing' ? 'Testing in Blender…' : 'Test failed'));
    return btn;
  };
  root.append(h('h3', {}, 'Look'), h('div', { class: 'mat-cards', role: 'list' }, ...cache.looks.map(lookCard)));

  // 3. colour palettes
  const palId = typeof layer.palette === 'string' ? layer.palette : layer.palette?.id || 'brand';
  const usePal = p => set({ palette: p, look: layer.look || 'ink-mustard', addon: layer.addon || 'doodle_looks' }, 'Colours: ' + (p.name || p));
  const yours = myPalettes(), inUse = typeof layer.palette === 'object' && layer.palette && !yours.some(p => p.id === layer.palette.id) ? [layer.palette] : [];
  const palCard = (p, click, del) => h('div', { class: 'mat-pal-wrap' }, h('button', { class: 'mat-pal', role: 'listitem', 'aria-pressed': String(palId === p.id), title: p.name + ': ' + p.theory, onclick: click }, swatches(h, p), h('span', {}, p.name), h('small', {}, p.theory.split(':')[0])), del ? h('button', { class: 'pal-x', title: 'Delete ' + p.name, 'aria-label': 'Delete ' + p.name, onclick: del }, '×') : null);
  root.append(h('h3', {}, 'Colours'), h('div', { class: 'mat-pals', role: 'list' }, ...cache.palettes.map(p => palCard(p, () => usePal(p.id))),
    ...[...yours, ...inUse].map(p => palCard(p, () => usePal(p), yours.includes(p) ? () => { dropPalette(p.id); ctx.rebuild(); } : null)),
    h('button', { class: 'mat-pal mat-pal-new', 'aria-expanded': String(!!ui.makePal), title: 'Pick your own colours, paste hex codes, or import a palette file', onclick: () => { ui.makePal = !ui.makePal; ctx.rebuild(); } }, h('span', {}, '+ Your palette'), h('small', {}, 'Picker, hex or file'))),
    ui.makePal ? paletteMaker(ctx, cache.palettes.find(p => p.id === palId) || (typeof layer.palette === 'object' && layer.palette) || cache.palettes[0], p => { ui.makePal = false; usePal(p); }) : '');

  // every piece and prop in the shot, part by part: no need to find it in the 3D view
  const pieces = ctx.pieces();
  if (pieces.length) {
    const put = (row, key, hex, label) => {
      ctx.pushUndo(label);
      const sc = ctx.scene(), hold = row.item != null ? ctx.project().items[row.item] : ((sc.materials ||= {}).parts ||= {});
      const own = row.item != null ? (hold.parts ||= {}) : (hold[row.piece] ||= {});
      if (hex) own[key] = hex; else delete own[key];
      if (!Object.keys(own).length) { if (row.item != null) delete hold.parts; else { delete hold[row.piece]; if (!Object.keys(hold).length) delete sc.materials.parts; } }
      ctx.changed(); ctx.rebuild();
    };
    root.append(h('h3', {}, 'Pieces and parts'), h('p', { class: 'hint' }, 'Change one part of one thing here, for the whole scene. Colours you pick win over the palette.'),
      h('div', { class: 'part-list' }, ...pieces.map(row => {
        const mine = (row.item != null ? ctx.project().items[row.item]?.parts : ctx.scene().materials?.parts?.[row.piece]) || {};
        return h('div', { class: 'part-row' }, h('b', {}, row.name), ...row.parts.map(p => {
          const c = h('input', { type: 'color', value: p.colour, 'aria-label': row.name + ' ' + p.label, title: row.name + ' ' + p.label });
          c.addEventListener('change', () => put(row, p.key, c.value.toUpperCase(), row.name + ' colour'));
          return h('label', { class: 'part' }, c, h('span', {}, p.label));
        }), Object.keys(mine).length ? h('button', { title: 'Back to the palette', onclick: () => { for (const k of Object.keys(mine)) put(row, k, null, 'Reset ' + row.name); } }, 'Reset') : '');
      })));
  }
  // 4. this look's settings, and the switches every look has
  const params = cur?.params || [];
  const P = layer.params || {};
  const ctl = (p) => {
    const v = P[p.id] ?? p.default;
    if (p.type === 'bool') return h('button', { 'aria-pressed': String(!!v), onclick: () => set({ params: { ...P, [p.id]: !v } }, p.label || p.id) }, p.label || p.id);
    if (p.type === 'color') { const i = h('input', { type: 'color', value: v || '#E0A64B' }); i.addEventListener('change', () => set({ params: { ...P, [p.id]: i.value } }, p.label || p.id)); return h('label', { class: 'ctl' }, h('span', { class: 'name' }, p.label || p.id), i, h('span')); }
    const step = p.type === 'int' ? 1 : p.step || Math.max(0.01, +((p.max - p.min) / 100).toFixed(3));
    const r = h('input', { type: 'range', min: p.min, max: p.max, step, value: v, 'aria-label': p.label || p.id });
    const n = h('input', { type: 'number', min: p.min, max: p.max, step, value: v, 'aria-label': (p.label || p.id) + ' value' });
    r.addEventListener('input', () => { n.value = r.value; });
    r.addEventListener('change', () => set({ params: { ...P, [p.id]: Number(r.value) } }, p.label || p.id));
    n.addEventListener('change', () => set({ params: { ...P, [p.id]: Number(n.value) } }, p.label || p.id));
    const name = h('span', { class: 'name', title: 'Double-click for the default' }, p.label || p.id);
    name.addEventListener('dblclick', () => { const q = { ...P }; delete q[p.id]; set({ params: q }, p.label || p.id); });
    return h('label', { class: 'ctl' }, name, r, n);
  };
  const colour = h('input', { type: 'color', value: layer.color || '#E0A64B', 'aria-label': 'One colour for every fill' });
  colour.addEventListener('change', () => set({ color: colour.value }, 'One colour'));
  root.append(h('h3', {}, `${cur?.name || 'Ink & Mustard'} settings`),
    params.length ? h('div', { class: 'mat-ctls' }, ...params.map(ctl)) : h('p', { class: 'hint' }, 'Flat brand fills and the ink line, exactly as Doodle Studio draws them. Pick colours above to repaint the flat look.'),
    h('div', { class: 'row mat-row' },
      h('button', { 'aria-pressed': String(inkOn(layer, cur)), title: 'The ink outline around bodies, set and props on this target, in any look: the colours stay. Face lines always stay. Textured looks start without it. The 3D view follows.', onclick: () => set({ ink: !inkOn(layer, cur), look: layer.look || 'ink-mustard', addon: layer.addon || 'doodle_looks' }, 'Outlines') }, inkOn(layer, cur) ? 'Outlines: on' : 'Outlines: off'),      h('label', { class: 'row', title: 'Paint this target\'s main colour; its other parts keep the palette' }, 'One colour', colour),
      layer.color ? h('button', { onclick: () => { const q = { ...layer }; delete q.color; set({ ...q, color: undefined }, 'Palette colours'); } }, 'Use palette colours') : null,
      h('button', { title: 'Back to Ink & Mustard for this target', onclick: () => set(null, 'Ink & Mustard') }, 'Reset'),
      h('button', { class: 'primary', title: 'Render the frame at the playhead in Blender to see the material for real (Ctrl+Shift+R)', onclick: () => ctx.renderFrame() }, 'Preview this frame'),));

  // Bunny and the outfit: palette swatches, any colour, or the brand mustard and black
  if (ui.target === 'scene' || ui.target === 'character') {
    const pal = cache.palettes.find(p => p.id === palId) || (typeof layer.palette === 'object' && layer.palette) || cache.palettes[0];
    const colours = [...new Set([pal.character, pal.outfit, pal.accent, ...(pal.pieces || []), pal.wall, '#E0A64B', '#1F1F1D'])];
    const picker = (label, key, brand) => {
      const any = h('input', { type: 'color', value: layer[key] || brand, 'aria-label': label + ': any colour' });
      any.addEventListener('change', () => set({ [key]: any.value, look: layer.look || 'ink-mustard', addon: layer.addon || 'doodle_looks' }, label));
      return h('div', { class: 'row mat-row' }, h('span', { class: 'sub-label', style: 'min-width:64px' }, label),
        h('button', { 'aria-pressed': String(!layer[key]), title: 'Follow the palette picked above', onclick: () => { const q = { ...layer }; delete q[key]; set({ ...q, [key]: undefined }, label); } }, 'Palette'),
        ...colours.map(c => h('button', { class: 'swatch', 'aria-pressed': String(layer[key] === c), title: c, 'aria-label': label + ' ' + c, style: 'background:' + c + ';width:30px', onclick: () => set({ [key]: c, look: layer.look || 'ink-mustard', addon: layer.addon || 'doodle_looks' }, label) })), any);
    };
    root.append(h('h3', {}, 'Character colours'), h('p', { class: 'hint' }, 'A palette dresses the characters too. Pick a colour here only to change them by hand; Palette goes back to it. Mustard and black are always in the row.'), picker('Bunny', 'bunny', pal.character), picker('Outfit', 'outfit', pal.outfit || pal.ink));
  }
  // 5. light for lit looks (scene-wide)
  const L = ctx.scene().materials?.light || {};
  const lightCtl = ([id, label, lo, hi, step, def]) => {
    const v = L[id] ?? def;
    const r = h('input', { type: 'range', min: lo, max: hi, step, value: v, 'aria-label': label });
    const n = h('input', { type: 'number', min: lo, max: hi, step, value: v, 'aria-label': label + ' value' });
    const put = val => { ctx.pushUndo(label); const sc = ctx.scene(); sc.materials = sc.materials || {}; sc.materials.light = { ...(sc.materials.light || {}), [id]: Number(val) }; ctx.changed(); };
    r.addEventListener('input', () => { n.value = r.value; });
    r.addEventListener('change', () => put(r.value));
    n.addEventListener('change', () => put(n.value));
    return h('label', { class: 'ctl' }, h('span', { class: 'name' }, label), r, n);
  };
  root.append(h('h3', {}, 'Light for lit looks (every shot)'), h('div', { class: 'mat-ctls' }, ...LIGHT.map(lightCtl)),
  h('p', { class: 'hint' }, 'For clay, vinyl, felt, paper and ceramic. A lighting preset in Stage › Light replaces these lights.'));

  // 6. look add-ons
  const extra = cache.looks.filter(l => l.source !== 'built-in');
  root.append(h('h3', {}, 'Look add-ons'), h('p', { class: 'hint' }, extra.length
    ? `${new Set(extra.map(l => l.addonName)).size} add-on${extra.length > 1 ? 's' : ''} found: ${[...new Set(extra.map(l => l.addonName))].join(', ')}. A new look is tried once with a test frame before you can pick it.`
    : 'Add a look add-on (for example ClayDoh): drop its folder or .zip into the Doodle Library\'s "looks" folder, or install it in Blender. It needs a doodle_look.json (see CONTRACT.md in Doodle Looks).'),
  h('div', { class: 'row' }, h('button', { onclick: () => loadLooks(ctx.api, true).then(() => { ctx.rebuild(); ctx.toast(`${cache.looks.length} looks`); }) }, 'Look again for add-ons')));
  return root;
}

export async function testLook(ctx, l) {
  ctx.toast(`Testing ${l.name} in Blender: one frame, about a minute`, 5000);
  await ctx.api('looks-test', { key: l.key });
  await loadLooks(ctx.api, true); ctx.rebuild();
  const poll = setInterval(async () => {
    await loadLooks(ctx.api, true);
    const now = cache.looks.find(x => x.key === l.key);
    if (!now || now.status !== 'testing') {
      clearInterval(poll); ctx.rebuild();
      ctx.toast(now?.status === 'ok' ? `${l.name} passed its test frame: ready to use` : `${l.name} failed its test frame: ${now?.error || 'see the log'}`, 7000);
    }
  }, 3000);
}

// MCP: materials { action: list | apply | clear | light, target, look, addon, params, palette, ink, color, bunny, outfit, scope, item }
export async function mcp(ctx, a = {}) {
  await loadLooks(ctx.api, a.action === 'list');
  const act = a.action || 'list';
  if (act === 'list') return { looks: cache.looks.map(({ preview, ...l }) => ({ ...l, hasPreview: !!preview })), palettes: cache.palettes.map(p => ({ id: p.id, name: p.name, theory: p.theory })), targets: TARGETS.map(t => t[0]), now: current(ctx) };
  const target = a.target || 'scene';
  if (!TARGETS.some(t => t[0] === target)) throw Error(`target is one of ${TARGETS.map(t => t[0]).join(', ')}`);
  const before = { ...ui };
  ui.scope = a.scope === 'shot' ? 'shot' : 'scene';
  if (target === 'item' && a.item != null) ctx.selectItem(a.item);
  try {
    if (act === 'clear') { setLayer(ctx, target, null, 'Ink & Mustard'); return { ok: true, now: current(ctx) }; }
    if (act === 'light') {
      const sc = ctx.scene(); ctx.pushUndo('Light');
      sc.materials = sc.materials || {};
      sc.materials.light = { ...(sc.materials.light || {}), ...Object.fromEntries(Object.entries({ ...(a.light && typeof a.light === 'object' ? a.light : {}), ...a }).filter(([k]) => ['key', 'fill', 'ambient', 'height', 'angle', 'softness', 'shadows'].includes(k))) };
      ctx.changed(); return { ok: true, light: sc.materials.light };
    }
    if (act !== 'apply') throw Error('action is list, apply, clear or light');
    const addon = a.addon || 'doodle_looks';
    const look = cache.looks.find(l => l.id === (a.look || 'ink-mustard') && l.addon === addon);
    if (!look) throw Error(`No look ${a.look} in ${addon}. Call materials action=list.`);
    if (look.status === 'failed') throw Error(`${look.name} failed its test frame: ${look.error}`);
    if (look.status === 'untested') { testLook(ctx, look); throw Error(`${look.name} is being tested in Blender first (about a minute); apply it again after`); }
    if (a.palette && typeof a.palette === 'string' && !cache.palettes.some(p => p.id === a.palette)) throw Error(`palette is one of ${cache.palettes.map(p => p.id).join(', ')}`);
    const patch = { look: look.id, addon };
    for (const k of ['params', 'palette', 'ink', 'color', 'bunny', 'outfit']) if (a[k] !== undefined) patch[k] = a[k];
    const layer = setLayer(ctx, target, patch, `Material: ${look.name}`);
    ctx.rebuild();
    return { ok: true, target, layer, now: current(ctx) };
  } finally { Object.assign(ui, before); }
}

export function current(ctx) {
  const m = materialsOf(ctx.scene(), ctx.project());
  return { layers: m?.layers || {}, light: m?.light || {}, items: (ctx.project().items || []).map((it, i) => (it.material ? { index: i, id: it.id, material: it.material } : null)).filter(Boolean) };
}

export { MATERIAL_TARGETS };
