// Timeline blocks, as in the 2D studio. Every character and every drawing on a shot is a layer
// with blocks you can drag, trim and cut. A gap between a character's blocks hides them there,
// in the view and the render. Keys stay editable in the property rows below.
//   owner.clips = [{ id, start, end }]   frames [start, end), sorted, never overlapping; none = the whole shot
//   owner.hidden = true                  the whole layer is off (the eye), in the render too
// owner is the shot (the lead) or a co-star. A drawing's block is its own frame .. until.
let seq = 0;
const uid = () => 'c' + Date.now().toString(36) + (seq++).toString(36);
const whole = len => [{ id: 'all', start: 0, end: len }];
const clampF = (f, len) => Math.max(0, Math.min(len, Math.round(f)));

// the blocks that fall inside the shot (a shot can get shorter after they were made)
export function clipsOf(owner, len) {
  if (!owner.clips) return whole(len);
  return owner.clips.filter(c => c.start < len).map(c => ({ ...c, end: Math.min(c.end, len) }));
}
function ensure(owner, len) {
  if (!owner.clips) owner.clips = [{ id: uid(), start: 0, end: len }];
  return owner.clips;
}
export const visibleAt = (owner, f, len) => !owner.hidden && clipsOf(owner, len).some(c => f >= c.start && f < c.end);
// frames [a, b) where the layer is hidden, for the render; null when it always shows
export function hiddenSpans(owner, len) {
  if (owner.hidden) return [[0, len]];
  if (!owner.clips) return null;
  const out = []; let at = 0;
  for (const c of clipsOf(owner, len)) { if (c.start > at) out.push([at, c.start]); at = Math.max(at, c.end); }
  if (at < len) out.push([at, len]);
  return out.length ? out : null;
}
// cut the block under frame `at` in two
export function split(owner, len, at) {
  const list = ensure(owner, len), f = Math.round(at), c = list.find(x => f > x.start && f < x.end);
  if (!c) throw Error('Put the playhead inside a block to cut it');
  const next = { id: uid(), start: f, end: c.end };
  c.end = f;
  list.splice(list.indexOf(c) + 1, 0, next);
  return next;
}
// trim one block, stopping at its neighbours
export function resize(owner, len, id, start, end) {
  const list = ensure(owner, len), c = byId(owner, len, id), i = list.indexOf(c);
  const lo = i ? list[i - 1].end : 0, hi = i < list.length - 1 ? list[i + 1].start : len;
  c.start = Math.max(lo, Math.min(clampF(start, len), c.end - 1));
  c.end = Math.min(hi, Math.max(clampF(end, len), c.start + 1));
  return c;
}
function byId(owner, len, id) {
  const list = ensure(owner, len);
  // 'all' is the block of a layer that had none yet: the one block there is
  const c = id === 'all' ? list[0] : list.find(x => x.id === id);
  if (!c) throw Error('No such block');
  return c;
}
// a block moves with its keys, as in the 2D studio. tracksList: the key tables of this layer.
// Camera keys stay put. Keys already under the block's new place are replaced.
export function move(owner, len, id, start, tracksList = []) {
  const list = ensure(owner, len), c = byId(owner, len, id), i = list.indexOf(c), size = c.end - c.start;
  const lo = i ? list[i - 1].end : 0, hi = (i < list.length - 1 ? list[i + 1].start : len) - size;
  const to = Math.max(lo, Math.min(hi, Math.round(start))), delta = to - c.start;
  if (!delta) return c;
  for (const tracks of tracksList) for (const [k, keys] of Object.entries(tracks)) {
    if (k.startsWith('cam.')) continue;
    const moving = keys.filter(x => x.f >= c.start && x.f < c.end), rest = keys.filter(x => x.f < to || x.f >= to + size).filter(x => !moving.includes(x));
    for (const x of moving) x.f += delta;
    tracks[k] = [...rest, ...moving].sort((a, b) => a.f - b.f);
  }
  c.start = to; c.end = to + size;
  return c;
}
// take a block away: a gap, so the layer is hidden there. The keys under it stay.
export function remove(owner, len, id) {
  const list = ensure(owner, len), c = byId(owner, len, id);
  list.splice(list.indexOf(c), 1);
}
// put a block into a gap: fills from `f` up to the next block
export function fillGap(owner, len, f) {
  const list = ensure(owner, len), at = Math.round(f);
  if (list.some(c => at >= c.start && at < c.end)) throw Error('There is already a block here');
  const start = Math.max(0, ...list.filter(c => c.end <= at).map(c => c.end)), end = Math.min(len, ...list.filter(c => c.start > at).map(c => c.start));
  const c = { id: uid(), start, end };
  list.push(c); list.sort((a, b) => a.start - b.start);
  return c;
}
// drop the blocks when they are back to one over the whole shot, so old renders stay cached
export function tidy(owner, len) {
  const c = owner.clips;
  if (c?.length === 1 && c[0].start === 0 && c[0].end >= len) delete owner.clips;
}

// ---------------------------------------------------------------- drawings
export const drawingSpan = (d, len) => [d.frame, Math.min(len, d.until ?? len)];
export function moveDrawing(d, len, start) {
  const [a, b] = drawingSpan(d, len), size = b - a, to = Math.max(0, Math.min(len - size, Math.round(start)));
  d.frame = to;
  if (d.until != null) d.until = to + size;
  return d;
}
export function resizeDrawing(d, len, start, end) {
  const a = Math.max(0, Math.min(Math.round(start), len - 1)), b = Math.max(a + 1, Math.min(Math.round(end), len));
  d.frame = a; d.until = b >= len ? null : b;
  return d;
}
// cut a drawing in two at frame `at`: the second part is already drawn, it does not draw on again
export function splitDrawing(p, index, at, len, makeId) {
  const d = p.drawings[index], [a, b] = drawingSpan(d, len), f = Math.round(at);
  if (f <= a || f >= b) throw Error('Put the playhead inside the drawing to cut it');
  const next = { ...d, id: makeId(), frame: f, build: 0 };
  d.until = f;
  p.drawings.splice(index + 1, 0, next);
  return next;
}
// where a drawing sits against the characters: over everything, in front, through them, behind
export const PLACES = [['screen', 'Over all', null], ['front', 'In front', -0.5], ['through', 'Through', 0], ['behind', 'Behind', 1]];
export const placeOf = d => (d.layer !== 'scene' ? 'screen' : (d.depth ?? 1) < -0.05 ? 'front' : Math.abs(d.depth ?? 1) <= 0.05 ? 'through' : 'behind');
