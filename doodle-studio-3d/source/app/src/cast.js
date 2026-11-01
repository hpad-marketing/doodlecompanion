// Co-stars: up to five more characters in a shot, on the same rig (Bunny, the Koala, the Frog).
// Each keeps its own keys (costar.tracks, same control ids as the lead) and stands at (x, y)
// metres turned `turn` degrees. Blender (lib/cast.py) appends their rigs into the lead's scene,
// keeps their arms out of their own heads and pushes them apart so no two bodies ever touch.
import { valueAt, setKey } from './project.js';
import { hiddenSpans } from './blocks.js';

export const MAX_COSTARS = 5;
export const costarsOf = p => p.costars || [];

// a stand-in project, so valueAt, setKey and the library's motion code work on a co-star's keys
export const costarProject = (p, i) => {
  const c = costarsOf(p)[i];
  if (!c) throw Error(`No co-star ${i}`);
  return { tracks: c.tracks, length: p.length, fps: p.fps, stepped: p.stepped };
};

export function addCostar(p, character, { x, y = 0, turn } = {}) {
  const list = p.costars || (p.costars = []);
  if (list.length >= MAX_COSTARS) throw Error(`A shot holds up to ${MAX_COSTARS} co-stars`);
  // alternate sides of the lead, each a step further out, turned in towards them
  const side = list.length % 2 ? -1 : 1, step = 0.8 + Math.floor(list.length / 2) * 0.7;
  const c = { character, x: +(x ?? side * step).toFixed(3), y: +(+y).toFixed(3), turn: 0, tracks: {} };
  c.turn = turn ?? (c.x > 0 ? -30 : 30);
  list.push(c);
  return { index: list.length - 1, costar: c };
}
export function removeCostar(p, i) {
  costarsOf(p).splice(i, 1);
  if (p.costars && !p.costars.length) delete p.costars;
  return { costars: costarsOf(p).length };
}
export function placeCostar(p, i, { x, y, turn, character }) {
  const c = costarsOf(p)[i];
  if (!c) throw Error(`No co-star ${i}`);
  if (x != null) c.x = +(+x).toFixed(3);
  if (y != null) c.y = +(+y).toFixed(3);
  if (turn != null) c.turn = +(+turn).toFixed(1);
  if (character) c.character = character;
  return { index: i, costar: { character: c.character, x: c.x, y: c.y, turn: c.turn } };
}
export function keyCostar(p, i, values, f) {
  const sp = costarProject(p, i);
  for (const [id, v] of Object.entries(values)) setKey(sp, id, f, Number(v));
  return { index: i, frame: f, keyed: Object.keys(values) };
}
// copy the lead's performance; mirror swaps left and right (mirrorValues maps one pose)
export function copyLead(p, i, ids, mirror, mirrorValues) {
  const c = costarsOf(p)[i];
  if (!c) throw Error(`No co-star ${i}`);
  c.tracks = {};
  for (const id of ids) {
    for (const k of p.tracks[id] || []) {
      const [[to, v]] = Object.entries(mirror ? mirrorValues({ [id]: k.v }) : { [id]: k.v });
      (c.tracks[to] ||= []).push({ ...k, v });
    }
  }
  for (const ks of Object.values(c.tracks)) ks.sort((a, b) => a.f - b.f);
  // the lead's placement stays the lead's: the co-star keeps its own spot
  for (const id of ['bodyX', 'bodyY', 'depth']) delete c.tracks[id];
  return { index: i, tracks: Object.keys(c.tracks).length, mirrored: !!mirror };
}
export const costarValues = (p, i, ids, f) => { const sp = costarProject(p, i); return Object.fromEntries(ids.map(id => [id, valueAt(sp, id, f)])); };

// what Blender receives: per-frame values like the lead's (no camera; the shot has one camera)
export function costarsForBridge(p, ids) {
  const own = ids.filter(id => !id.startsWith('cam.'));
  return costarsOf(p).map((c, i) => { const hide = hiddenSpans(c, p.length); return { character: c.character, x: c.x, y: c.y, turn: c.turn,
    frames: Array.from({ length: p.length }, (_, f) => costarValues(p, i, own, f)), ...(hide ? { hide } : {}) }; });
}
