// Storytime part 2: cold-open flash-forward, story beat map, mood strip, genre moment
// presets, gestures from the voice (head and body only, never the jaw), eye darts,
// jump-scare timing, auto foley, freeze-frame name labels, chapter cards, a sponsor
// segue, long video to Shorts and the offline retention overlay (YouTube Studio CSV).
// Everything is built from the app's own keys, layers and library pieces: no services.
import { valueAt, setKey, newShotData, nextCode, DISCRETE } from './project.js';
import { splitShotAt } from './workflow.js';
import { addLayer, endPoint } from './animtools2.js';
import { chapters } from './storytime.js';

const clone = x => JSON.parse(JSON.stringify(x));
const rand = seed => () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;

// frames a..b of a shot as a new shot (keys baked across the cuts, like Split shot)
export function cutRange(scene, shot, a, b) {
  const tmp = { fps: scene.fps, shots: [clone(shot)] };
  if (b < shot.length) splitShotAt(tmp, 0, b);
  if (a > 0) { splitShotAt(tmp, 0, a); tmp.shots.shift(); }
  const s = tmp.shots[0];
  s.uid = newShotData('x').uid;
  return s;
}

// ---------------------------------------------------------------- cold open: flash forward, then rewind
export function coldOpen(scene, i, { seconds = 3, card = 'Earlier that day...' } = {}) {
  const s = scene.shots[i], n = Math.min(s.length, Math.max(1, Math.round(seconds * scene.fps)));
  const open = cutRange(scene, s, s.length - n, s.length);
  open.code = nextCode(scene);
  open.label = 'Cold open';
  open.coldOpenOf = s.code;
  scene.shots.unshift(open);
  const next = scene.shots[1];
  (next.items ||= []).push({ id: 'story:time_skip', frame: 0, text: card });
  next.items.sort((a, b) => a.frame - b.frame);
  scene.active = 0;
  return { coldOpen: open.code, from: s.code, seconds: +(n / scene.fps).toFixed(2), card };
}

// ---------------------------------------------------------------- story beat map
export const BEATS = [['hook', 'Hook', 0], ['setup', 'Setup', 0.08], ['rising', 'Rising action', 0.25], ['turn', 'Turn', 0.5], ['climax', 'Climax', 0.75], ['payoff', 'Payoff', 0.9], ['cta', 'Call to action', 0.97]];
export function beatMap(scene) {
  const total = scene.shots.reduce((n, s) => n + s.length, 0), found = {};
  let t0 = 0;
  for (const s of scene.shots) {
    for (const m of s.markers || []) {
      const b = /^\s*beat\s*:\s*(.+)$/i.exec(m.note || '');
      if (!b) continue;
      const key = BEATS.find(x => x[0] === b[1].trim().toLowerCase() || x[1].toLowerCase() === b[1].trim().toLowerCase());
      if (key) (found[key[0]] ||= []).push({ shot: s.code, f: m.f, at: +((t0 + m.f) / scene.fps).toFixed(1) });
    }
    t0 += s.length;
  }
  return {
    seconds: +(total / scene.fps).toFixed(1),
    beats: BEATS.map(([id, name, k]) => ({ id, name, at: found[id]?.[0]?.at ?? null, where: found[id]?.[0] ? `${found[id][0].shot} F${found[id][0].f}` : null, suggested: +(k * total / scene.fps).toFixed(1) })),
    missing: BEATS.filter(([id]) => !found[id]).map(x => x[1]),
  };
}
// scene frame -> shot index and frame in it
export function locate(scene, F) {
  let n = Math.max(0, Math.round(F));
  for (let i = 0; i < scene.shots.length; i++) { if (n < scene.shots[i].length) return [i, n]; n -= scene.shots[i].length; }
  const i = scene.shots.length - 1;
  return [i, scene.shots[i].length - 1];
}
export function addBeat(scene, id) {
  const b = BEATS.find(x => x[0] === id);
  if (!b) throw Error('beat must be ' + BEATS.map(x => x[0]).join(', '));
  const total = scene.shots.reduce((n, s) => n + s.length, 0), [i, f] = locate(scene, b[2] * total);
  const s = scene.shots[i];
  (s.markers ||= []).push({ f, note: 'beat: ' + b[1] });
  s.markers.sort((x, y) => x.f - y.f);
  return { beat: b[1], shot: s.code, frame: f };
}

// ---------------------------------------------------------------- mood strip (colour script in ink and mustard)
export const MOODS = {
  calm: { name: 'Calm', mustard: 35, time: 'day', sky: 'day' },
  happy: { name: 'Happy', mustard: 85, time: 'golden', sky: 'day' },
  tense: { name: 'Tense', mustard: 55, time: 'golden', sky: 'sunset' },
  sad: { name: 'Sad', mustard: 20, time: 'night', sky: 'storm' },
  scary: { name: 'Scary', mustard: 8, time: 'night', sky: 'storm' },
  dreamy: { name: 'Dreamy', mustard: 70, time: 'golden', sky: 'stars' },
};
export const moodColour = m => `color-mix(in srgb, #E0A64B ${MOODS[m]?.mustard ?? 50}%, #1F1F1D)`;
export function setMood(shot, mood, light = true) {
  if (mood && !MOODS[mood]) throw Error('mood must be ' + Object.keys(MOODS).join(', '));
  if (!mood) { delete shot.mood; return { shot: shot.code, mood: null }; }
  shot.mood = mood;
  if (light) shot.stage = { ...(shot.stage || {}), time: MOODS[mood].time, sky: MOODS[mood].sky };
  return { shot: shot.code, mood, light: light ? { time: MOODS[mood].time, sky: MOODS[mood].sky } : null };
}
export function moodStripDialog(ctx) {
  const { h } = ctx, sc = ctx.scene(), total = sc.shots.reduce((n, s) => n + s.length, 0);
  const close = () => box.remove();
  const strip = h('div', { class: 'mood-strip' }, ...sc.shots.map((s, i) => {
    const sel = h('select', { 'aria-label': `Mood of ${s.code}` }, h('option', { value: '' }, 'No mood'), ...Object.entries(MOODS).map(([k, m]) => h('option', { value: k }, m.name)));
    sel.value = s.mood || '';
    sel.addEventListener('change', () => { ctx.pushUndo('Mood'); setMood(s, sel.value || null, true); ctx.changed(); close(); moodStripDialog(ctx); });
    return h('div', { class: 'mood-cell', style: `flex:${s.length / total}` },
      h('button', { class: 'mood-swatch', style: `background:${s.mood ? moodColour(s.mood) : 'transparent'}`, title: `${s.code}${s.label ? ' · ' + s.label : ''}: click to edit this shot`, onclick: () => { close(); ctx.selectShot(i); } }, s.code), sel);
  }));
  const box = h('div', { class: 'ds-modal', role: 'dialog', 'aria-label': 'Mood strip' }, h('div', { class: 'ds-modal-card', style: 'width:min(900px,92vw)' },
    h('h3', {}, 'Mood strip'), h('p', { class: 'hint' }, 'A colour script for the scene, in ink and mustard only: more mustard is warmer. Picking a mood also sets that shot\'s light and sky; you can still change them on the Library tab.'),
    strip, h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: close }, 'Close'))));
  box.addEventListener('pointerdown', e => { if (e.target === box) close(); });
  document.body.append(box);
}

// ---------------------------------------------------------------- genre moment presets
const face = (names, re) => names.findIndex(n => re.test(n));
export const GENRES = {
  horror: { name: 'Horror sting', items: [['sound:horror_drone', 0], ['sound:sting', 1]], push: [0.82, 2], face: /scared|fear|panic|dread|terrified/i },
  action: { name: 'Action hit', items: [['fx:speed_lines', 0], ['sound:whoosh', 0]], push: [0.85, 0.5], face: /determined|angry|fierce|focus/i },
  romance: { name: 'Romance', items: [['fx:petals', 0], ['react:heart', 0.3], ['sound:bell', 0.3]], push: [0.9, 1.5], face: /love|blush|dreamy|smitten/i },
  comedy: { name: 'Comedy beat', items: [['react:sweat', 0], ['sound:boing', 0]], push: [0.88, 0.4], face: /awkward|nervous|sheepish|embarrass/i },
  sad: { name: 'Sad moment', items: [['fx:rain', 0]], push: [1.12, 2.5], face: /sad|cry|tear|upset/i },
  mystery: { name: 'Mystery', items: [['react:question', 0], ['sound:click', 0]], push: [0.9, 1.2], face: /suspicious|curious|thinking|confused/i },
  triumph: { name: 'Triumph', items: [['fx:confetti', 0], ['react:star', 0.2], ['sound:bell', 0]], push: [0.92, 0.8], face: /proud|happy|excited|joy/i },
};
// the camera move is always eased (never an abrupt zoom): a push in (<1) or pull out (>1)
function easedPush(p, f, factor, seconds, fps, cur) {
  const n = Math.max(4, Math.round(seconds * fps)), d = cur('cam.dist');
  setKey(p, 'cam.dist', f, d, 'ease');
  setKey(p, 'cam.dist', Math.min(p.length - 1, f + n), +(d * factor).toFixed(3), 'ease');
}
export function genreMoment(ctx, genre, f = ctx.frame()) {
  const g = GENRES[genre];
  if (!g) throw Error('genre must be ' + Object.keys(GENRES).join(', '));
  const p = ctx.project(), fps = ctx.scene().fps;
  ctx.pushUndo(g.name);
  for (const [id, sec] of g.items) (p.items ||= []).push({ id, frame: Math.min(p.length - 1, f + Math.round(sec * fps)) });
  p.items.sort((a, b) => a.frame - b.frame);
  easedPush(p, f, g.push[0], g.push[1], fps, id => valueAt(p, id, f));
  const e = face(ctx.faces(), g.face);
  if (e >= 0) setKey(p, 'expression', f, e);
  ctx.changed();
  return { genre: g.name, frame: f, items: g.items.map(x => x[0]), face: e >= 0 ? ctx.faces()[e] : null };
}

// ---------------------------------------------------------------- gestures from the voice
// Emphasis peaks in the scene voice nod the head and lean the body a little, on a layer
// named "Gestures" so the base animation stays untouched. The mouth and jaw are never keyed.
export function gesturesFromVoice(ctx, { strength = 1, minGap = 8 } = {}) {
  const env = ctx.envelope();
  if (!env) throw Error('Import the voice first (File › Import audio)');
  const p = ctx.project(), start = ctx.sceneStart(), k = Math.max(0.2, Math.min(2, strength));
  const at = f => env[start + f] || 0, peaks = [];
  for (let f = 3; f < p.length - 3; f++) {
    const v = at(f);
    if (v > 0.5 && v >= at(f - 1) && v >= at(f + 1) && v - Math.min(at(f - 3), at(f - 2)) > 0.18 && (!peaks.length || f - peaks.at(-1) >= minGap)) peaks.push(f);
  }
  ctx.pushUndo('Gestures from voice');
  let i = (p.layers || []).findIndex(L => L.name === 'Gestures');
  if (i < 0) i = addLayer(p, 'Gestures');
  const L = p.layers[i];
  L.tracks = {};
  const key = (id, f, v) => { if (f >= 0 && f < p.length) setKey(L, id, f, +v.toFixed(2), 'ease'); };
  peaks.forEach((f, n) => {
    const side = n % 2 ? 1 : -1, amp = k * (0.6 + 0.6 * at(f));
    key('headNod', f - 4, 0); key('headNod', f, 6 * amp); key('headNod', f + 9, 0);
    key('rot', f - 4, 0); key('rot', f + 1, 3 * amp * side); key('rot', f + 12, 0);
    key('bodyTilt', f - 5, 0); key('bodyTilt', f + 2, 1.5 * amp * side); key('bodyTilt', f + 14, 0);
  });
  ctx.changed();
  return { layer: L.name, gestures: peaks.length, frames: peaks };
}

// ---------------------------------------------------------------- eye darts (the eyes keep their size: only the gaze moves)
export function eyeDarts(ctx, { every = 1.4, seed = 7 } = {}) {
  const p = ctx.project(), fps = ctx.scene().fps, names = ctx.gazes(), r = rand(seed * 977 + 13);
  const side = names.map((n, i) => [n, i]).filter(([n]) => /^(Left|Right|Up Left|Up Right|Down Left|Down Right)$/i.test(n)).map(x => x[1]);
  if (!side.length) throw Error('This character has no side gazes');
  const keyed = new Set((p.tracks.gaze || []).map(k => k.f));
  const near = f => [...keyed].some(x => Math.abs(x - f) < 10);
  ctx.pushUndo('Eye darts');
  let f = Math.round(fps * (0.4 + r() * every)), n = 0;
  while (f < p.length - 6) {
    if (!near(f)) {
      const base = valueAt(p, 'gaze', f), hold = 4 + Math.round(r() * 5);
      setKey(p, 'gaze', f, side[Math.floor(r() * side.length)]);
      setKey(p, 'gaze', Math.min(p.length - 1, f + hold), base);
      n++;
    }
    f += Math.round(fps * every * (0.6 + r() * 0.8));
  }
  ctx.changed();
  return { darts: n };
}

// ---------------------------------------------------------------- jump scare: quiet, then the hit
export function jumpScare(ctx, f = ctx.frame()) {
  const p = ctx.project(), fps = ctx.scene().fps;
  if (f < 6) throw Error('Leave a little quiet before the scare: pick a frame after 6');
  ctx.pushUndo('Jump scare');
  (p.items ||= []).push({ id: 'sound:sting', frame: f, volume: 1 }, { id: 'react:exclaim', frame: f });
  p.items.sort((a, b) => a.frame - b.frame);
  (p.markers ||= []).push({ f: Math.max(0, f - Math.round(fps)), note: 'quiet: music ducks before the scare' }, { f, note: 'scare' });
  p.markers.sort((a, b) => a.f - b.f);
  easedPush(p, f, 0.7, 4 / fps, fps, id => valueAt(p, id, f));   // a fast push in, still eased
  const e = face(ctx.faces(), /scared|fear|panic|shock|terrified/i);
  if (e >= 0) setKey(p, 'expression', f, e);
  ctx.changed();
  return { frame: f, quietFrom: Math.max(0, f - fps), face: e >= 0 ? ctx.faces()[e] : null };
}

// ---------------------------------------------------------------- auto foley: whooshes on fast swings, landings
export function autoFoley(ctx) {
  const p = ctx.project(), view = ctx.view(), fps = ctx.scene().fps;
  ctx.pushUndo('Auto foley');
  p.items = (p.items || []).filter(it => !it.auto);
  const hands = [], feet = [];
  for (let f = 0; f < p.length; f++) {
    const v = ctx.valuesAt(f);
    hands.push(['armL', 'armR'].map(l => endPoint(view, v, l)));
    feet.push(Math.min(endPoint(view, v, 'legL').z, endPoint(view, v, 'legR').z));
  }
  view.rig.pose(ctx.valuesAt(ctx.frame()));
  const add = (id, f, volume) => { if (!p.items.some(it => it.auto && Math.abs(it.frame - f) < fps / 3)) p.items.push({ id, frame: f, volume, auto: true }); };
  for (let f = 1; f < p.length; f++) {
    const speed = Math.max(...[0, 1].map(s => hands[f][s].distanceTo(hands[f - 1][s])));
    if (speed > 0.045) add('sound:whoosh', f, 0.45);
    if (feet[f - 1] > feet[0] + 0.05 && feet[f] <= feet[0] + 0.015) add('sound:boing', f, 0.5);
  }
  p.items.sort((a, b) => a.frame - b.frame);
  ctx.changed();
  return { sounds: p.items.filter(it => it.auto).map(it => ({ id: it.id, frame: it.frame })) };
}

// ---------------------------------------------------------------- freeze-frame name label
// Holds every control for a moment at f (the picture freezes) and pins a name label.
export function freezeLabel(ctx, f, text, seconds = 1.5) {
  const p = ctx.project(), n = Math.max(6, Math.round(seconds * ctx.scene().fps));
  if (!text) throw Error('Write the label, e.g. "Bunny: professional napper"');
  ctx.pushUndo('Freeze-frame label');
  const shiftList = (arr, key) => { for (const x of arr || []) if (x[key] > f) x[key] += n; };
  for (const tracks of [p.tracks, ...(p.layers || []).map(L => L.tracks)]) {
    for (const [id, ks] of Object.entries(tracks)) {
      const v = DISCRETE.has(id) ? valueAt({ tracks }, id, f) : valueAt({ tracks, layer: tracks !== p.tracks }, id, f);
      for (const k of ks) if (k.f > f) k.f += n;
      setKey({ tracks }, id, f, v, 'linear');
      setKey({ tracks }, id, f + n, v, 'ease');
    }
  }
  shiftList(p.items, 'frame'); shiftList(p.markers, 'f');
  p.length += n;
  (p.items ||= []).push({ id: 'story:label', frame: f, text: String(text).slice(0, 60), freeze: n });
  p.items.sort((a, b) => a.frame - b.frame);
  ctx.changed(true);
  return { frame: f, frames: n, text };
}

// ---------------------------------------------------------------- chapter cards
export function chapterCards(scene) {
  let made = 0;
  for (const s of scene.shots) for (const m of s.markers || []) {
    const t = /^\s*(?:chapter\s*:|#)\s*(.+)$/i.exec(m.note || '');
    if (!t || (s.items || []).some(it => it.chapter && it.frame === m.f)) continue;
    (s.items ||= []).push({ id: 'story:time_skip', frame: m.f, text: t[1].trim(), chapter: true });
    s.items.sort((a, b) => a.frame - b.frame);
    made++;
  }
  return { cards: made, chapters: chapters(scene).chapters.length };
}

// ---------------------------------------------------------------- sponsor segue kit
export function sponsorSegue(scene, after, name, seconds = 8) {
  if (!name) throw Error('Name the sponsor');
  const fps = scene.fps, s = newShotData(nextCode(scene, after), Math.round(seconds * fps)), prev = scene.shots[after];
  for (const [id, ks] of Object.entries(prev.tracks)) s.tracks[id] = [{ f: 0, v: valueAt(prev, id, prev.length - 1), ease: 'ease' }];
  s.label = 'Sponsor';
  s.items = [{ id: 'sound:whoosh', frame: 0 }, { id: 'story:time_skip', frame: 0, text: `A quick word from ${name}` }, { id: 'story:time_skip', frame: s.length - Math.round(1.4 * fps), text: 'Back to the story' }];
  s.markers = [{ f: 0, note: 'Chapter: Sponsor: ' + name }];
  scene.shots.splice(after + 1, 0, s);
  return { shot: s.code, seconds, sponsor: name };
}

// ---------------------------------------------------------------- long video to Shorts
// Segments come from markers "short: title" (to the next marker or 60 s) or, without
// any, from the chapters. Each becomes its own 9:16 scene, at most 60 s.
export function shortsPlan(scene) {
  const fps = scene.fps, total = scene.shots.reduce((n, s) => n + s.length, 0), marks = [];
  let t0 = 0;
  for (const s of scene.shots) { for (const m of s.markers || []) { const x = /^\s*short\s*:\s*(.+)$/i.exec(m.note || ''); if (x) marks.push({ F: t0 + m.f, title: x[1].trim() }); } t0 += s.length; }
  const src = marks.length ? marks : chapters(scene).chapters.map(c => ({ F: Math.round(c.t * fps), title: c.title }));
  return src.sort((a, b) => a.F - b.F).map((m, i, a) => ({ title: m.title, from: m.F, to: Math.min(total, a[i + 1]?.F ?? total, m.F + 60 * fps) }))
    .filter(x => x.to - x.from >= fps * 3);
}
export function makeShort(scene, seg) {
  const out = { ...clone({ ...scene, shots: [] }), name: `${scene.name} - Short - ${seg.title}`.slice(0, 80), width: 1080, height: 1920, shots: [], active: 0 };
  delete out.meter; delete out.moderator; delete out.overrides;
  let t0 = 0;
  for (const s of scene.shots) {
    const a = Math.max(seg.from, t0), b = Math.min(seg.to, t0 + s.length);
    if (b > a) { const part = cutRange(scene, s, a - t0, b - t0); part.code = s.code; out.shots.push(part); }
    t0 += s.length;
  }
  return out;
}

// ---------------------------------------------------------------- offline retention overlay (YouTube Studio CSV)
export function parseRetention(csv, seconds) {
  const rows = String(csv).trim().split(/\r?\n/).map(l => l.split(',').map(x => x.replace(/^"|"$/g, '').trim()));
  const head = rows[0].map(x => x.toLowerCase());
  const pos = head.findIndex(x => /position|time|second|moment/.test(x)), ret = head.findIndex(x => /retention|audience|watch/.test(x) && !/position/.test(x));
  if (pos < 0 || ret < 0) throw Error('The CSV needs a video position column and an audience retention column (YouTube Studio › Analytics › Audience retention › Export)');
  const pts = [];
  for (const r of rows.slice(1)) {
    let t = r[pos], v = parseFloat(r[ret]);
    t = /^\d+:\d+/.test(t) ? t.split(':').reduce((a, b) => a * 60 + Number(b), 0) : parseFloat(t);
    if (isFinite(t) && isFinite(v)) pts.push([t, v]);
  }
  // position as a percentage or 0-1 fraction of the video, or in seconds
  const maxT = Math.max(...pts.map(q => q[0])), isPct = /%|percent/.test(head[pos]);
  const scaleT = isPct ? (maxT <= 1.0001 ? seconds : seconds / 100) : 1, scaleV = Math.max(...pts.map(q => q[1])) <= 1.5 ? 100 : 1;
  for (const q of pts) { q[0] = +(q[0] * scaleT).toFixed(2); q[1] = +(q[1] * scaleV).toFixed(1); }
  if (pts.length < 2) throw Error('No retention rows found in that CSV');
  pts.sort((a, b) => a[0] - b[0]);
  const drops = [];
  for (let i = 1; i < pts.length; i++) {
    const dt = pts[i][0] - pts[i - 1][0], dv = pts[i - 1][1] - pts[i][1];
    if (dt > 0 && dv / dt > 1.5 && pts[i][0] > 3) drops.push({ at: pts[i - 1][0], lost: +dv.toFixed(1) });
  }
  return { points: pts, drops: drops.sort((a, b) => b.lost - a.lost).slice(0, 5) };
}
// the curve under one shot's timeline, as an SVG polyline
export function retentionLane(h, scene, shotStart, length, ppf) {
  const R = scene.retention;
  if (!R?.points?.length) return null;
  const fps = scene.fps, H = 22, svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', String(length * ppf)); svg.setAttribute('height', String(H)); svg.classList.add('retention');
  const pts = R.points.filter(([t]) => t * fps >= shotStart - fps && t * fps <= shotStart + length + fps)
    .map(([t, v]) => `${((t * fps - shotStart) * ppf).toFixed(1)},${(H - 2 - (Math.min(100, v) / 100) * (H - 4)).toFixed(1)}`);
  const pl = document.createElementNS(svg.namespaceURI, 'polyline');
  pl.setAttribute('points', pts.join(' ')); pl.setAttribute('fill', 'none'); pl.setAttribute('stroke', 'currentColor'); pl.setAttribute('stroke-width', '2');
  svg.append(pl);
  for (const d of R.drops || []) {
    const x = (d.at * fps - shotStart) * ppf;
    if (x < 0 || x > length * ppf) continue;
    const m = document.createElementNS(svg.namespaceURI, 'rect');
    m.setAttribute('x', String(x - 1)); m.setAttribute('y', '0'); m.setAttribute('width', '3'); m.setAttribute('height', String(H)); m.setAttribute('fill', '#E0A64B');
    const t = document.createElementNS(svg.namespaceURI, 'title'); t.textContent = `Viewers dropped ${d.lost}% here (${d.at}s)`; m.append(t);
    svg.append(m);
  }
  return svg;
}
