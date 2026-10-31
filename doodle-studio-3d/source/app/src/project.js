// A Doodle Studio 3D shot: keyed tracks for Bunny and the camera.
// Track ids are Doodle Studio's own (armL, headYaw, ...) plus cam.* for the 3D camera,
// so a shot exports straight to the Blender bridge.

import { idleLayer, idleOn } from './idle.js';
import { costarsForBridge } from './cast.js';
import { forBridge as drawingsForBridge } from './drawings.js';

export const DISCRETE = new Set(['expression', 'gaze', 'mouth', 'blink']);
export const CAM_DEFAULT = { yaw: 0, pitch: 4, dist: 3.0, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.52, focus: 0, fstop: 2.8 };   // focus 0 = everything sharp
export const EASES = { ease: 'Ease in and out', linear: 'Linear', in: 'Ease in (slow start)', out: 'Ease out (slow in)', snap: 'Snap', overshoot: 'Overshoot', bounce: 'Bounce', hold: 'Hold' };

const easeFn = {
  ease: t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  linear: t => t,
  in: t => t * t * t,
  out: t => 1 - Math.pow(1 - t, 3),
  hold: () => 0,
  snap: t => 1 - Math.pow(1 - t, 6),                       // gets there almost at once, then settles
  overshoot: t => { const c = 1.9; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },   // past the key, then back
  bounce: t => {                                           // lands and bounces twice
    const n = 7.5625, d = 2.75;
    if (t < 1 / d) return n * t * t;
    if (t < 2 / d) return n * (t -= 1.5 / d) * t + 0.75;
    if (t < 2.5 / d) return n * (t -= 2.25 / d) * t + 0.9375;
    return n * (t -= 2.625 / d) * t + 0.984375;
  },
};

// A scene holds its shots in play order, like the 2D Doodle Studio. Shots are
// coded sh010, sh020, ... so renders name themselves (Bambi_sh020_v003).
// fps and frame size belong to the scene; each shot has its own timeline.
export function newScene(name = 'Untitled scene') {
  return { app: 'doodle-studio-3d', version: 2, name, fps: 30, width: 1080, height: 1920, audio: null, active: 0, shots: [newShotData('sh010')] };
}

export function newShotData(code, length = 120) {
  return { uid: Math.random().toString(36).slice(2, 10), code, label: '', length, tracks: {}, audio: null, markers: [] };
}

// older single-shot files open as a one-shot scene
export function migrate(p) {
  if (p && Array.isArray(p.shots)) {
    p.active = Math.max(0, Math.min(p.shots.length - 1, p.active | 0));
    return p;
  }
  const scene = newScene(p?.name || 'Untitled scene');
  for (const k of ['fps', 'width', 'height']) if (p?.[k]) scene[k] = p[k];
  scene.shots[0] = { ...newShotData('sh010', p?.length || 120), tracks: p?.tracks || {}, audio: p?.audio || null, markers: p?.markers || [] };
  return scene;
}

export function nextCode(scene, after = scene.shots.length - 1) {
  const num = s => Number(String(s.code).replace(/\D/g, '')) || 0;
  const used = new Set(scene.shots.map(num));
  const a = scene.shots[after] ? num(scene.shots[after]) : 0;
  const b = scene.shots[after + 1] ? num(scene.shots[after + 1]) : null;
  // the next free multiple of 10, or a number between two shots when inserting
  let n = b == null ? Math.ceil((a + 1) / 10) * 10 : Math.floor((a + b) / 2);
  if (b != null && (n <= a || used.has(n))) n = Math.max(...used) + 10;
  while (used.has(n)) n += 10;
  return 'sh' + String(n).padStart(3, '0');
}

// the editor works on one shot at a time; fps and size read through to the scene
export function bindShot(scene, shot) {
  for (const k of ['fps', 'width', 'height']) Object.defineProperty(shot, k, { get: () => scene[k], set: v => { scene[k] = v; }, enumerable: false, configurable: true });
  return shot;
}

export const shotSeconds = (scene, shot) => shot.length / scene.fps;

export function defaults(id) {
  if (id.startsWith('cam.')) return CAM_DEFAULT[id.slice(4)] ?? 0;
  if (id === 's') return 1;
  if (id === 'earLScale' || id === 'earRScale') return 100;   // percent of the character's own ear size
  return 0;
}

// base keys plus every animation layer that is on (layers add an offset, times their weight)
export function valueAt(project, id, f, depth = 0) {
  let v = trackValue(project, id, f);
  if (project.layers && !DISCRETE.has(id)) for (const L of project.layers) if (L.on !== false && L.tracks?.[id]?.length) v += (L.weight ?? 1) * trackValue(L, id, f);
  // linked controls: another control drives this one (a loop is refused when linking; depth guards old files)
  if (project.links && depth < 6 && !DISCRETE.has(id)) for (const L of project.links) if (L.to === id && L.on !== false) v += (L.factor ?? 1) * (valueAt(project, L.from, f, depth + 1) - defaults(L.from)) + (L.offset || 0);
  return v;
}
export const layerValue = (L, id, f) => (L.tracks?.[id]?.length ? trackValue(L, id, f) : 0);
function trackValue(project, id, f) {
  const keys = project.tracks[id];
  if (!keys || !keys.length) return project.layer ? 0 : defaults(id);
  if (f <= keys[0].f) return keys[0].v;
  const last = keys[keys.length - 1];
  if (f >= last.f) return last.v;
  let i = 1;
  while (keys[i].f < f) i++;
  const a = keys[i - 1], b = keys[i];
  if (f === b.f) return b.v;
  if (DISCRETE.has(id) || project.stepped) return a.v;   // stepped: blocking pass, every key holds
  const t = (f - a.f) / (b.f - a.f);
  return a.v + (b.v - a.v) * easeFn[a.ease || 'ease'](t);
}

export function frameValues(project, f, ids) {
  const out = {};
  for (const id of ids || Object.keys(project.tracks)) out[id] = valueAt(project, id, f);
  return out;
}

export function setKey(project, id, f, v, ease) {
  const keys = (project.tracks[id] ||= []);
  const k = keys.find(k => k.f === f);
  if (k) { k.v = v; if (ease) k.ease = ease; }
  else { keys.push({ f, v, ease: ease || 'ease' }); keys.sort((a, b) => a.f - b.f); }
}

export function deleteKey(project, id, f) {
  const keys = project.tracks[id];
  if (!keys) return;
  const i = keys.findIndex(k => k.f === f);
  if (i >= 0) keys.splice(i, 1);
  if (!keys.length) delete project.tracks[id];
}

export function hasKey(project, id, f) {
  return !!project.tracks[id]?.some(k => k.f === f);
}

// Idle life (auto blink / ear twitch) for a shot, worked out once per change of the
// keys it reads or of its settings. The same layer feeds the viewport and Blender.
const IDLE_READS = ['blink', 'expression', 'turn', 'headYaw', 'earLFold', 'earRFold', 'earLForward', 'earRForward', 'earLScale', 'earRScale', 'earLSquash', 'earRSquash'];
const idleCache = new WeakMap();
export function idleFor(project, faceNames = [], character = 'bunny') {
  if (!idleOn(project)) return null;
  const sig = JSON.stringify([project.idle, project.uid, project.length, project.fps, character, faceNames.length, IDLE_READS.map(id => project.tracks[id] || 0)]);
  const hit = idleCache.get(project);
  if (hit && hit.sig === sig) return hit.layer;
  const layer = idleLayer(project, project.fps, (id, f) => valueAt(project, id, f), faceNames, character);
  idleCache.set(project, { sig, layer });
  return layer;
}

// The stage a shot renders on: the scene's set, light, outfit and so on, with this
// shot's own overrides on top. Library items placed in the shot ride along.
export const STAGE_KEYS = ['set', 'setProps', 'time', 'sky', 'shadows', 'outfit', 'accessories', 'mouthSet'];
export function stageOf(scene, shot) {
  const st = { ...(scene.stage || {}), ...(shot.stage || {}) };
  for (const k of Object.keys(st)) if (st[k] == null || st[k] === '' || (Array.isArray(st[k]) && !st[k].length)) delete st[k];
  return st;
}

// Materials tab: the scene's looks (scene, character, set, props) with this shot's own on top.
// A shot layer set to null clears the scene's one for that shot. Props picked one by one carry
// their own look on the item (item.material) and travel with the items.
export const MATERIAL_TARGETS = ['scene', 'character', 'set', 'props'];
export function materialsOf(scene, shot) {
  const S = scene.materials || {}, T = shot.materials || {};
  const layers = {};
  for (const k of MATERIAL_TARGETS) {
    const v = T.layers && k in T.layers ? T.layers[k] : S.layers?.[k];
    if (v && v.look) layers[k] = v;
  }
  const light = { ...(S.light || {}), ...(T.light || {}) };
  return Object.keys(layers).length ? { layers, ...(Object.keys(light).length ? { light } : {}) } : null;
}

// Blender bridge shot: one entry per frame, cam block per frame
export function toBridgeShot(project, allIds, faceNames, character, stage = {}, materials = null) {
  const frames = [];
  const idle = idleFor(project, faceNames, character);
  for (let f = 0; f < project.length; f++) {
    const v = frameValues(project, f, allIds);
    if (idle?.frames[f]) Object.assign(v, idle.frames[f]);
    const cam = {};
    for (const k of Object.keys(CAM_DEFAULT)) cam[k] = valueAt(project, 'cam.' + k, f);
    if (project.horizonLock) cam.roll = 0;   // the horizon stays level whatever the keys say
    for (const k of Object.keys(v)) if (k.startsWith('cam.')) delete v[k];
    v.cam = cam;
    frames.push(v);
  }
  const out = { fps: project.fps, width: project.width, height: project.height, frames, settings: { boil_step: 3, ...(project.ink && project.ink !== 100 ? { ink_px: +(12.73 * project.ink / 100).toFixed(3) } : {}) } };
  // Bunny-only shots with no stage stay byte-identical to older builds, so their render cache holds
  if (character && character !== 'bunny') out.character = character;
  if (Object.keys(stage).length) out.stage = stage;
  if (project.items?.length) out.items = project.items;
  if (materials) out.materials = materials;   // Materials tab (materials.py); none = Ink & Mustard as before
  if (project.powers && Object.keys(project.powers).length) out.powers = project.powers;   // Blender powers (powers.py)
  // scene drawings stand in the 3D world (drawings.py); screen drawings are laid on top as PNGs
  const dr = drawingsForBridge(project);
  if (dr) out.drawings = dr;
  if (project.costars?.length) out.costars = costarsForBridge(project, allIds);   // co-stars (cast.py)   // Blender powers (powers.py)
  // the built-in rule defaults (arm in front, face clear, props on the floor, eye size) are on
  // unless this shot turns one off; only the switches that are off travel, so caches hold
  const off = Object.entries(project.rules || {}).filter(([, v]) => v === false);
  if (off.length) out.rules = Object.fromEntries(off);
  if (project.camCuts?.length) out.cuts = project.camCuts.map(f => +(f / project.fps).toFixed(4));   // multi-cam: no blur across a cut
  return out;
}
