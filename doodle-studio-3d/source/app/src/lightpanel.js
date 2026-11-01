// Stage › Set & light: the Shadows button, the 3-point presets with their sliders, and the Outline
// strip that shows over the 3D view for whatever is selected. Every change shows in the Stage at
// once; the shot only saves (and Blender only rebuilds) when a slider is let go.
import { LIGHT_PRESETS } from './lit.js';
import { setStage } from './library.js';
import { stageOf } from './project.js';

const SLIDERS = [['key', 'Key', 0, 3, 0.05], ['fill', 'Fill', 0, 2, 0.05], ['back', 'Back', 0, 3, 0.05], ['turn', 'Turn (°)', -180, 180, 1],
  ['height', 'Height (m)', 0.3, 5, 0.05], ['distance', 'Distance (m)', 0.5, 6, 0.05], ['soft', 'Softness', 0, 1, 0.05], ['shade', 'Shadow depth', 0.05, 0.8, 0.01]];

export const makeLighting = (id, turn, target = 'lead') => ({ preset: id, target, turn: Math.round(turn), ...LIGHT_PRESETS.find(p => p[0] === id)[3] });

// who the light can centre on: the character(s), then the props and text in the shot
function targets(ctx, project) {
  const name = id => ctx.itemName?.(id) || id;
  return [['lead', ctx.characterName()], ...(project.costars || []).map((c, i) => [`costar:${i}`, `${c.character || 'Co-star'} ${i + 1}`]),
    ...(project.items || []).map((it, i) => [it, i]).filter(([it]) => !/^(fx|react|sound):/.test(it.id)).map(([it, i]) => [`item:${i}`, name(it.id)])];
}

export function lightControls(ctx, shotOnly) {
  const { h } = ctx, scene = ctx.scene(), project = ctx.project(), st = stageOf(scene, project), L = st.lighting;
  const put = patch => { setStage(ctx, patch, shotOnly); ctx.rebuild(); };
  const toggle = (label, on, patch, title) => h('button', { 'aria-pressed': String(!!on), title, onclick: () => put(patch(!on)) }, label);
  const box = h('div', { class: 'light-ctl' },
    h('div', { class: 'chips' },
      toggle('Shadows', st.shadows, v => (v ? { shadows: true } : { shadows: false, halftone: null }), 'Light and shadow on the whole scene, characters included. Off by default.'),
      toggle('Halftone dots', st.halftone, v => (v ? { halftone: true, shadows: true } : { halftone: null }), 'Comic-book halftone: the shadows print as ink dots in the render. Turns Shadows on.')),
    h('h3', {}, '3-point light'),
    h('div', { class: 'chips' }, h('button', { 'aria-pressed': String(!L), title: 'No 3-point light', onclick: () => put({ lighting: null }) }, 'Off'),
      ...LIGHT_PRESETS.map(([id, name, tip]) => h('button', { 'aria-pressed': String(L?.preset === id), title: tip, onclick: () => put({ lighting: makeLighting(id, L?.turn ?? ctx.cameraYaw(), ctx.selectedTarget() ?? L?.target) }) }, name))));
  if (L) {
    const pick = h('select', { 'aria-label': 'Centre the light on' }, ...targets(ctx, project).map(([v, n]) => h('option', { value: v }, n)));
    pick.value = L.target || 'lead';
    pick.addEventListener('change', () => put({ lighting: { ...L, target: pick.value } }));
    box.append(h('label', { class: 'lbl-row', title: 'The three lights stay centred on this, and follow it as it moves' }, h('span', { class: 'lbl' }, 'Centre on'), pick));
    const live = { ...L };
    for (const [k, label, lo, hi, step] of SLIDERS) {
      const r = h('input', { type: 'range', min: lo, max: hi, step, 'aria-label': label }), out = h('span', { class: 'val' }, String(L[k]));
      r.value = L[k];
      r.addEventListener('input', () => { live[k] = Number(r.value); out.textContent = r.value; ctx.previewLighting(live, shotOnly); });
      r.addEventListener('change', () => { ctx.previewLighting(null); put({ lighting: { ...live } }); });
      box.append(h('label', { class: 'ctl' }, h('span', {}, label), r, out));
    }
  }
  box.append(h('p', { class: 'hint' }, 'The Stage shows the light and shadow live. Blender builds the same lights in the render: with the Tri-lighting add-on, its TriLamp lights. A plain background has no floor to catch a shadow: pick a set to see it land.'));
  return box;
}

// the strip over the 3D view: what is selected and how thick its outline is
let bar = null, sig = '';
export function inkBar(ctx) {
  const key = ctx.inkTarget();
  const now = key ? key.id + '|' + key.value : '';
  if (now === sig) return;
  sig = now;
  if (!key) { bar?.remove(); bar = null; return; }
  const { h } = ctx;
  const r = h('input', { type: 'range', min: 0, max: 200, step: 5, 'aria-label': 'Outline thickness' }), out = h('span', { class: 'val' }, key.value + '%');
  r.value = key.value;
  r.addEventListener('input', () => { out.textContent = r.value + '%'; ctx.setInk(key, Number(r.value), false); sig = key.id + '|' + r.value; });
  r.addEventListener('change', () => ctx.setInk(key, Number(r.value), true));
  const fresh = h('div', { id: 'ink-bar', title: 'This object\'s outline, as a percent of Bunny\'s line. 0 takes it off. Saved with the scene and used in the render.' }, h('b', {}, key.name), h('span', {}, 'Outline'), r, out,
    h('button', { onclick: () => ctx.setInk(key, 100, true) }, 'Reset'));
  if (bar) bar.replaceWith(fresh); else ctx.host().append(fresh);
  bar = fresh;
}
