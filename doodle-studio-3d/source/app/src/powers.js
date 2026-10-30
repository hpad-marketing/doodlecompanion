// Blender powers. In Blender (host/blender/lib/powers.py, from shot.powers): ink doodles drawn
// in 3D space, auto-ink on any model, scatter (grass, pebbles, flowers, leaves), a cheering
// crowd, jelly props, toon liquids, a fisheye lens and 360 video. In the editor: a paper
// finish and shot transitions (laid on when the scene is joined), linked controls (one control
// drives another) and a macro recorder for menu commands. Brand colours only: ink and mustard.
import { INK, MUSTARD } from './post.js';

export const SCATTER = { grass: 'Grass tufts', pebbles: 'Pebbles', flowers: 'Flowers', leaves: 'Fallen leaves' };
export const LIQUIDS = { splash: 'Splash', pour: 'Pour', puddle: 'Puddle' };
export const TRANSITIONS = { dip: 'Dip to ink', flash: 'Mustard flash' };

export const powersOf = p => p.powers || (p.powers = {});
// empty powers leave no trace, so untouched shots keep their render cache
export function tidy(p) {
  const pw = p.powers;
  if (!pw) return;
  for (const k of Object.keys(pw)) if (pw[k] == null || pw[k] === false || pw[k] === 0 || (Array.isArray(pw[k]) && !pw[k].length)) delete pw[k];
  if (!Object.keys(pw).length) delete p.powers;
}

// ---------------------------------------------------------------- 3D doodles
// strokes: [[[x, y], ...], ...] in frame fractions (y down); unproject(x, y, depth) -> [x, y, z]
export function addDoodles(p, strokes, unproject, { frame = 0, draw = 12, depth = 0 } = {}) {
  const pw = powersOf(p), made = [];
  for (const s of strokes || []) {
    const pts = [];
    for (const [x, y] of s) {
      const q = unproject(x, y, depth);
      if (!q) continue;
      const l = pts[pts.length - 1];
      if (!l || Math.hypot(q[0] - l[0], q[1] - l[1], q[2] - l[2]) > 0.015) pts.push(q);
    }
    if (pts.length < 2) continue;
    made.push({ points: pts.slice(0, 200), frame, draw: Math.max(1, Math.round(draw)) });
  }
  if (!made.length) throw Error('Draw at least one line');
  pw.doodles = (pw.doodles || []).concat(made);
  return { doodles: pw.doodles.length, added: made.length, frame };
}

export function addScatter(p, kind = 'grass', { center = [0, 0.6], radius = 1.2, count = 30, seed = 1 } = {}) {
  if (!SCATTER[kind]) throw Error('kind must be ' + Object.keys(SCATTER).join(', '));
  const pw = powersOf(p);
  pw.scatter = (pw.scatter || []).concat([{ kind, center, radius: Math.max(0.2, Math.min(6, +radius)), count: Math.max(1, Math.min(400, Math.round(count))), seed }]);
  return { scatter: pw.scatter };
}

export function setCrowd(p, spec) {
  const pw = powersOf(p);
  pw.crowd = spec ? { count: Math.max(1, Math.min(80, Math.round(spec.count ?? 14))), rows: Math.max(1, Math.min(4, Math.round(spec.rows ?? 2))), distance: Math.max(1, +(spec.distance ?? 2.2)), seed: spec.seed ?? 3, cheer: spec.cheer !== false } : null;
  tidy(p);
  return { crowd: p.powers?.crowd || null };
}

export function addLiquid(p, kind = 'splash', frame = 0, at = [0.4, -0.3, 0]) {
  if (!LIQUIDS[kind]) throw Error('kind must be ' + Object.keys(LIQUIDS).join(', '));
  const pw = powersOf(p);
  pw.liquids = (pw.liquids || []).concat([{ kind, frame, at }]);
  return { liquids: pw.liquids };
}

export function setPower(p, key, value) {
  powersOf(p)[key] = value;
  tidy(p);
  return { [key]: p.powers?.[key] ?? null };
}

// ---------------------------------------------------------------- paper finish: ink grain and fibres, laid over the scene
export function drawPaper(g, W, H, amount = 0.5, seed = 7) {
  let s = seed >>> 0 || 7;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const k = Math.max(0, Math.min(1, amount)), n = Math.round(W * H / 90 * (0.4 + k));
  g.fillStyle = INK;
  for (let i = 0; i < n; i++) {
    g.globalAlpha = 0.04 + rnd() * 0.12 * k;
    const r = rnd() < 0.85 ? 1 : 2;
    g.fillRect(Math.floor(rnd() * W), Math.floor(rnd() * H), r, r);
  }
  g.strokeStyle = MUSTARD;
  g.lineWidth = 1;
  for (let i = 0; i < Math.round(n / 40); i++) {
    const x = rnd() * W, y = rnd() * H, a = rnd() * Math.PI, l = 4 + rnd() * 14;
    g.globalAlpha = 0.25 + rnd() * 0.35;
    g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + Math.cos(a + 0.4) * l / 2, y + Math.sin(a + 0.4) * l / 2, x + Math.cos(a) * l, y + Math.sin(a) * l); g.stroke();
  }
  g.globalAlpha = 1;
}

// transitions into each shot, in scene frames: the cut sits in the middle of the transition
export function transitionsOf(shots) {
  const out = [];
  let at = 0;
  shots.forEach((s, i) => {
    if (i && s.transition && TRANSITIONS[s.transition.kind]) out.push({ at, kind: s.transition.kind, frames: Math.max(2, Math.min(60, s.transition.frames || 12)) });
    at += s.length;
  });
  return out;
}

// ---------------------------------------------------------------- linked controls: from drives to (to += factor * change in from + offset)
export function addLink(p, from, to, factor = 1, offset = 0) {
  if (!from || !to || from === to) throw Error('Pick two different controls');
  const links = p.links || (p.links = []);
  // no loops: walking from `from` back through its own drivers must never reach `to`
  const feeds = id => links.filter(l => l.to === id).map(l => l.from);
  const seen = new Set(), stack = [from];
  while (stack.length) { const id = stack.pop(); if (id === to) throw Error('That would make a loop'); if (!seen.has(id)) { seen.add(id); stack.push(...feeds(id)); } }
  const old = links.findIndex(l => l.from === from && l.to === to);
  const link = { from, to, factor: +factor, offset: +offset };
  if (old >= 0) links[old] = link; else links.push(link);
  return { links };
}
export function removeLink(p, i) {
  (p.links || []).splice(i, 1);
  if (p.links && !p.links.length) delete p.links;
  return { links: p.links || [] };
}

// ---------------------------------------------------------------- macros: menu commands with their playhead offsets
const MACRO_KEY = 'ds3d.macros';
export const macros = {
  all() { try { return JSON.parse(localStorage.getItem(MACRO_KEY) || '{}'); } catch { return {}; } },
  save(name, steps) { const m = this.all(); m[name] = steps; try { localStorage.setItem(MACRO_KEY, JSON.stringify(m)); } catch {} return m; },
  remove(name) { const m = this.all(); delete m[name]; try { localStorage.setItem(MACRO_KEY, JSON.stringify(m)); } catch {} return m; },
};
export function recorder() {
  let steps = null, start = 0;
  return {
    get on() { return !!steps; },
    start(frame) { steps = []; start = frame; },
    note(group, label, frame) { if (steps && !/^Macro/.test(label)) steps.push({ group, label, offset: frame - start }); },
    stop() { const s = steps || []; steps = null; return s; },
  };
}
