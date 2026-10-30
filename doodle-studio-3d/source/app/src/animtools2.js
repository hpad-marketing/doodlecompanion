// Animator tools, part 2: click-to-pick, IK drag that keys FK (IK/FK snap), pinning a hand
// or foot (space switching, foot planting), motion paths with an arc check and fixer,
// the graph editor with spacing charts, time warp, moving holds, the partial pose library,
// copy / paste keys across shots and characters, animation layers, Euler filter, the
// balance marker, a reference video on a plane and retargeting.
import * as THREE from 'three';
import { valueAt, setKey, layerValue, DISCRETE, EASES } from './project.js';

const V = () => new THREE.Vector3();
export const v3 = a => a.toArray().map(x => +x.toFixed(3));

// ---------------------------------------------------------------- picker: which part is under the pointer
const PART_OF = [[/hand|cuff|sleeve_fore|sleeve_up|arm/, m => 'arm' + m], [/leg|foot/, m => 'leg' + m], [/shirt|pelvis|neck|hood|tail|body/, () => 'body']];
export function pick(view, clientX, clientY) {
  const r = view.renderer.domElement.getBoundingClientRect();
  const ray = new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1), view.camera);
  const meshes = view.objects.map(o => o.mesh);
  for (const o of view.objects) { o.mesh.geometry.computeBoundingSphere(); o.mesh.geometry.computeBoundingBox(); }
  const hit = ray.intersectObjects(meshes, false)[0];
  if (!hit) return null;
  const o = view.objects.find(x => x.mesh === hit.object), name = o.m.name.replace(/^[A-Z]+_/, '');
  const side = /\.(L|R)$/.exec(name)?.[1] || '';
  if (/head/.test(name)) {
    // the head mesh holds the ears: above the skull top they are the ears
    const top = view.rig.bones.get('head').tailV.clone().applyMatrix4(view.rig.A.get('head') || new THREE.Matrix4());
    return { part: hit.point.z > top.z - 0.02 ? 'ears' : 'head', mesh: name, point: hit.point };
  }
  for (const [re, fn] of PART_OF) if (re.test(name)) return { part: fn(side), mesh: name, point: hit.point };
  return { part: 'whole', mesh: name, point: hit.point };
}

// ---------------------------------------------------------------- IK: move a hand or foot, key the FK controls
export const LIMB = {
  armL: { end: 'DEF-hand.L', ids: ['armL', 'armLForward', 'elbowL'] },
  armR: { end: 'DEF-hand.R', ids: ['armR', 'armRForward', 'elbowR'] },
  legL: { end: 'DEF-foot.L', ids: ['legL', 'legLOut', 'kneeL'] },
  legR: { end: 'DEF-foot.R', ids: ['legR', 'legROut', 'kneeR'] },
};
// world position of a limb's end (wrist / ankle) for a full set of values
export function endPoint(view, values, limb) {
  view.rig.pose(values);
  const b = view.rig.bones.get(LIMB[limb].end);
  view.group.updateMatrixWorld();
  return b.headV.clone().applyMatrix4(view.rig.A.get(LIMB[limb].end) || new THREE.Matrix4()).applyMatrix4(view.group.matrixWorld);
}
// damped least squares over the limb's three controls, inside the joint limits: controls
// pinned at a limit drop out, every step must reduce the miss (halving it if not), and a
// straight elbow or knee gets a second try from a bent start (a straight limb is singular)
export function solve(view, values, limb, target, range, iters = 14) {
  const ids = LIMB[limb].ids;
  const run = start => {
    const v = { ...start };
    let p = endPoint(view, v, limb), err = target.clone().sub(p);
    for (let it = 0; it < iters && err.length() > 0.002; it++) {
      const Jc = ids.map(id => endPoint(view, { ...v, [id]: v[id] + 1 }, limb).sub(p).multiplyScalar(100));   // cm per degree
      const ec = err.clone().multiplyScalar(100);
      const free = ids.map((id, i) => { const [lo, hi] = range(id), g = Jc[i].dot(ec); return !((v[id] <= lo + 1e-6 && g < 0) || (v[id] >= hi - 1e-6 && g > 0)); });
      const tr = Jc.reduce((n, c, i) => n + (free[i] ? c.lengthSq() : 0), 0) / 3, lam = 0.02 * tr + 1e-9;
      const A = [0, 1, 2].map(i => [0, 1, 2].map(j => (free[i] && free[j] ? Jc[i].dot(Jc[j]) : 0) + (i === j ? (free[i] ? lam : 1) : 0)));
      const dx = solve3(A, Jc.map((c, i) => (free[i] ? c.dot(ec) : 0)));
      let step = 1, better = false;
      for (let k = 0; k < 6 && !better; k++, step /= 2) {
        const t = { ...v };
        ids.forEach((id, i) => { const [lo, hi] = range(id); t[id] = Math.max(lo, Math.min(hi, v[id] + step * Math.max(-25, Math.min(25, dx[i])))); });
        const q = endPoint(view, t, limb), e2 = target.clone().sub(q);
        if (e2.length() < err.length() - 1e-6) { Object.assign(v, t); p = q; err = e2; better = true; }
      }
      if (!better) break;
    }
    return { v, miss: err.length() };
  };
  let best = run(values);
  const bend = ids[2], [blo, bhi] = range(bend);
  if (best.miss > 0.004 && Math.abs(values[bend] ?? 0) < 10) {
    const again = run({ ...values, [bend]: Math.max(blo, Math.min(bhi, (values[bend] ?? 0) + (bhi > 0 ? 35 : -35))) });
    if (again.miss < best.miss) best = again;
  }
  return { values: Object.fromEntries(ids.map(id => [id, +best.v[id].toFixed(2)])), error: +best.miss.toFixed(4) };
}
function solve3(A, b) {
  const det = m => m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]);
  const D = det(A);
  if (!(Math.abs(D) > 1e-30)) return [0, 0, 0];
  return [0, 1, 2].map(k => det(A.map((row, i) => row.map((x, j) => (j === k ? b[i] : x)))) / D);
}
// move a hand or foot to a world point, or by an offset in metres (MCP, tests)
export function ikMove(view, values, limb, { target, offset } = {}, range) {
  const t = target ? new THREE.Vector3(...target) : endPoint(view, values, limb).add(new THREE.Vector3(...(offset || [0, 0, 0])));
  return solve(view, values, limb, t, range, 24);
}
// drag a hand or foot across the camera plane; returns the solver per pointer move
export function ikDrag(view, values, limb, range) {
  const start = endPoint(view, values, limb);
  const normal = new THREE.Vector3(); view.camera.getWorldDirection(normal);
  const plane = new THREE.Plane().setFromNormalAndCoplanarPoint(normal, start);
  const ray = new THREE.Raycaster();
  return (clientX, clientY) => {
    const r = view.renderer.domElement.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1), view.camera);
    const hit = ray.ray.intersectPlane(plane, V());
    return hit ? solve(view, values, limb, hit, range) : null;
  };
}

// ---------------------------------------------------------------- space switching / planting: keep a hand or foot where it is
// From f0 to f1 the limb's end stays at its world position at f0 (world space), even as the
// body moves; keys every `step` frames, linear. Pinning to the body is plain FK already.
export function pin(ctx, limb, f0, f1, step = 2) {
  const p = ctx.project(), view = ctx.view();
  const target = endPoint(view, ctx.valuesAt(f0), limb);
  let worst = 0, n = 0;
  ctx.pushUndo('Pin ' + limb);
  for (let f = f0; f <= f1; f += step) {
    const r = solve(view, ctx.valuesAt(f), limb, target, ctx.range);
    for (const [id, x] of Object.entries(r.values)) setKey(p, id, f, x, 'linear');
    worst = Math.max(worst, r.error); n++;
    if (f + step > f1 && f !== f1) step = f1 - f;
  }
  ctx.changed();
  return { limb, from: f0, to: f1, keys: n, worstErrorCm: +(worst * 100).toFixed(1) };
}

// ---------------------------------------------------------------- motion paths, spacing dots and the arc check
export function pathOf(ctx, what) {
  const view = ctx.view(), p = ctx.project(), pts = [];
  for (let f = 0; f < p.length; f++) pts.push(what === 'head' ? (view.rig.pose(ctx.valuesAt(f)), view.headPoint()) : endPoint(view, ctx.valuesAt(f), what));
  view.rig.pose(ctx.valuesAt(ctx.frame()));
  return pts;
}
// frames where the path kinks (direction turns sharply while moving): arcs that pop
export function arcCheck(pts, minMove = 0.004, maxTurn = 50) {
  const pops = [];
  for (let f = 1; f < pts.length - 1; f++) {
    const a = pts[f].clone().sub(pts[f - 1]), b = pts[f + 1].clone().sub(pts[f]);
    if (a.length() < minMove || b.length() < minMove) continue;
    const turn = THREE.MathUtils.radToDeg(a.angleTo(b));
    if (turn > maxTurn) pops.push({ f, turn: Math.round(turn) });
  }
  return pops;
}
// smooth the limb's controls around each pop (baked, 5-frame window)
export function arcFix(ctx, what, pops) {
  const p = ctx.project(), ids = what === 'head' ? ['headYaw', 'headNod', 'rot'] : LIMB[what].ids;
  ctx.pushUndo('Fix arcs');
  const orig = Object.fromEntries(ids.map(id => [id, Array.from({ length: p.length }, (_, f) => valueAt(p, id, f))]));
  for (const { f } of pops) for (let x = Math.max(0, f - 2); x <= Math.min(p.length - 1, f + 2); x++) for (const id of ids) {
    let s = 0, w = 0;
    for (let k = -2; k <= 2; k++) { const y = orig[id][x + k]; if (y != null) { const wt = 3 - Math.abs(k); s += y * wt; w += wt; } }
    setKey(p, id, x, +(s / w).toFixed(2), 'linear');
  }
  ctx.changed();
  return { fixed: pops.length };
}
export function drawPath(ctx, pts, keysAt, pops = []) {
  const fr = document.querySelector('#frame'), view = ctx.view();
  let c = document.getElementById('path-layer');
  if (!pts) { c?.remove(); return; }
  if (!c) { c = document.createElement('canvas'); c.id = 'path-layer'; fr.insertBefore(c, document.querySelector('#hud')); }
  c.width = fr.clientWidth; c.height = fr.clientHeight;
  const g = c.getContext('2d'), sp = pts.map(q => { const v = q.clone().project(view.camera); return [(v.x + 1) / 2 * c.width, (1 - v.y) / 2 * c.height]; });
  g.lineWidth = 2; g.strokeStyle = '#1F1F1D'; g.beginPath(); sp.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke();
  sp.forEach(([x, y], f) => {   // one dot per frame: spacing reads straight off the path
    g.fillStyle = '#1F1F1D';
    if (keysAt.has(f)) { g.save(); g.translate(x, y); g.rotate(Math.PI / 4); g.fillRect(-5, -5, 10, 10); g.restore(); } else g.fillRect(x - 1.5, y - 1.5, 3, 3);
    if (f === ctx.frame()) { g.strokeStyle = '#1F1F1D'; g.lineWidth = 2; g.beginPath(); g.arc(x, y, 7, 0, Math.PI * 2); g.stroke(); }
  });
  for (const { f } of pops) { const [x, y] = sp[f]; g.strokeStyle = '#1F1F1D'; g.lineWidth = 3; g.beginPath(); g.moveTo(x - 7, y - 7); g.lineTo(x + 7, y + 7); g.moveTo(x + 7, y - 7); g.lineTo(x - 7, y + 7); g.stroke(); }
  return sp;
}

// ---------------------------------------------------------------- graph editor (with spacing charts)
export function graphEditor(ctx, box, ids, sel) {
  const p = ctx.project(), W = box.clientWidth - 4, H = Math.max(140, box.clientHeight - 4);
  const c = document.createElement('canvas');
  c.className = 'graph'; c.width = W; c.height = H;
  const keyed = ids.filter(id => p.tracks[id]?.length && !DISCRETE.has(id));
  let lo = Infinity, hi = -Infinity;
  for (const id of keyed) for (let f = 0; f < p.length; f++) { const v = valueAt(p, id, f); lo = Math.min(lo, v); hi = Math.max(hi, v); }
  if (!isFinite(lo)) { lo = -10; hi = 10; }
  if (hi - lo < 1) { hi += 1; lo -= 1; }
  const pad = 14, X = f => 40 + f * (W - 50) / Math.max(1, p.length - 1), Y = v => pad + (hi - v) * (H - 2 * pad) / (hi - lo);
  const F = x => Math.round((x - 40) * Math.max(1, p.length - 1) / (W - 50)), Vv = y => hi - (y - pad) * (hi - lo) / (H - 2 * pad);
  const g = c.getContext('2d');
  const draw = () => {
    g.clearRect(0, 0, W, H);
    g.fillStyle = '#1F1F1D'; g.font = '700 10px system-ui';
    g.fillText(String(Math.round(hi)), 4, pad + 4); g.fillText(String(Math.round(lo)), 4, H - pad + 4);
    g.globalAlpha = .25; g.fillRect(X(ctx.frame()), 0, 1, H); g.globalAlpha = 1;
    keyed.forEach((id, n) => {
      const isSel = sel.id === id;
      g.strokeStyle = '#1F1F1D'; g.lineWidth = isSel ? 3 : 1.5; g.setLineDash(n % 2 ? [6, 3] : []);
      g.beginPath();
      for (let f = 0; f < p.length; f++) { const x = X(f), y = Y(valueAt(p, id, f)); f ? g.lineTo(x, y) : g.moveTo(x, y); }
      g.stroke(); g.setLineDash([]);
      for (const k of p.tracks[id]) {
        g.save(); g.translate(X(k.f), Y(k.v)); g.rotate(Math.PI / 4);
        g.fillStyle = isSel && sel.f === k.f ? '#1F1F1D' : '#E0A64B'; g.fillRect(-5, -5, 10, 10); g.strokeRect(-5, -5, 10, 10); g.restore();
      }
      g.fillText(ctx.label(id), X(p.tracks[id][0].f) + 8, Y(p.tracks[id][0].v) - 8);
    });
    // spacing chart for the selected key's segment: ticks where each in-between lands
    const ks = sel.id && p.tracks[sel.id], i = ks ? ks.findIndex(k => k.f === sel.f) : -1;
    if (i >= 0 && ks[i + 1]) {
      const a = ks[i], b = ks[i + 1], x0 = X(a.f), x1 = X(b.f), y = H - 6;
      g.fillRect(x0, y, x1 - x0, 1.5);
      for (let f = a.f; f <= b.f; f++) { const t = b.v === a.v ? (f - a.f) / (b.f - a.f) : (valueAt(p, sel.id, f) - a.v) / (b.v - a.v); const x = x0 + t * (x1 - x0); g.fillRect(x - 0.75, y - (f === a.f || f === b.f ? 8 : 5), 1.5, f === a.f || f === b.f ? 10 : 7); }
    }
  };
  draw();
  const near = (mx, my) => { for (const id of keyed) for (const k of p.tracks[id]) if (Math.abs(X(k.f) - mx) < 7 && Math.abs(Y(k.v) - my) < 7) return { id, k }; return null; };
  c.addEventListener('pointerdown', e => {
    const r = c.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top, hit = near(mx, my);
    if (!hit) { ctx.goto(F(mx)); draw(); return; }
    sel.id = hit.id; sel.f = hit.k.f; ctx.selectKey(hit.id, hit.k.f);
    c.setPointerCapture(e.pointerId);
    ctx.pushUndo('Graph edit');
    let moved = false;
    const mv = ev => {
      const x = ev.clientX - r.left, y = ev.clientY - r.top;
      const nf = Math.max(0, Math.min(p.length - 1, F(x)));
      if (!ev.shiftKey && nf !== hit.k.f && !p.tracks[hit.id].some(o => o !== hit.k && o.f === nf)) { hit.k.f = nf; p.tracks[hit.id].sort((a, b) => a.f - b.f); sel.f = nf; }
      if (!ev.altKey) { const [l, h2] = ctx.range(hit.id); hit.k.v = +Math.max(l, Math.min(h2, Vv(y))).toFixed(2); }
      moved = true; ctx.changed(true); draw();
    };
    const up = () => { c.removeEventListener('pointermove', mv); c.removeEventListener('pointerup', up); if (!moved) ctx.popUndo(); ctx.goto(hit.k.f); draw(); };
    c.addEventListener('pointermove', mv); c.addEventListener('pointerup', up);
  });
  c.title = 'Drag a key: up/down changes its value, left/right its frame (hold Shift for value only, Alt for frame only). The bar at the bottom is the spacing chart of the selected key.';
  return { canvas: c, draw };
}

// ---------------------------------------------------------------- time warp (speed ramps) and moving holds
export const WARPS = {
  'slow start': (t, a) => Math.pow(t, 1 - 0.3 * a),
  'slow end': (t, a) => 1 - Math.pow(1 - t, 1 - 0.3 * a),
  'slow middle': (t, a) => t - 0.12 * a * Math.sin(2 * Math.PI * t),
  'fast middle': (t, a) => t + 0.12 * a * Math.sin(2 * Math.PI * t),
};
export function timeWarp(ctx, name, amount = 1) {
  const w = WARPS[name];
  if (!w) throw Error('warp must be ' + Object.keys(WARPS).join(', '));
  const p = ctx.project(), L = p.length - 1, map = f => Math.round(L * w(f / L, Math.max(0, Math.min(2, amount))));
  ctx.pushUndo('Time warp');
  for (const id of Object.keys(p.tracks)) p.tracks[id] = Object.values(Object.fromEntries(p.tracks[id].map(k => [map(k.f), { ...k, f: map(k.f) }]))).sort((a, b) => a.f - b.f);
  for (const m of p.markers || []) m.f = map(m.f);
  for (const it of p.items || []) it.frame = map(it.frame);
  ctx.changed(true);
  return { warp: name, amount };
}
// a held pose keeps drifting a little in the direction it was moving, so it never goes dead
export function movingHold(ctx, f0, f1, amount = 0.06) {
  const p = ctx.project();
  if (f1 <= f0) throw Error('The hold needs an end frame after its start');
  ctx.pushUndo('Moving hold');
  let n = 0;
  for (const id of ctx.poseIds()) {
    if (DISCRETE.has(id) || !p.tracks[id]) continue;
    const v0 = valueAt(p, id, f0), before = valueAt(p, id, Math.max(0, f0 - 6));
    const [lo, hi] = ctx.range(id);
    let drift = (v0 - before) * amount * 4;
    if (Math.abs(drift) < 0.2) continue;
    setKey(p, id, f0, v0, 'out');
    setKey(p, id, f1, +Math.max(lo, Math.min(hi, v0 + drift)).toFixed(2), 'ease');
    n++;
  }
  ctx.changed();
  return { from: f0, to: f1, drifting: n };
}

// ---------------------------------------------------------------- partial pose library
export const POSE_PARTS = { face: ['expression', 'gaze', 'mouth', 'blink'], hands: ['wristL', 'wristR', 'elbowL', 'elbowR'], ears: [/^ear/], upper: [/^(arm|elbow|wrist|head|rot$|torso|bodyTilt)/], whole: [/.*/] };
const store = { get() { try { return JSON.parse(localStorage.getItem('ds3d.poses') || '[]'); } catch { return []; } }, set(v) { try { localStorage.setItem('ds3d.poses', JSON.stringify(v)); } catch {} return v; } };
export const partIds = (part, ids) => { const m = POSE_PARTS[part]; if (!m) throw Error('part must be ' + Object.keys(POSE_PARTS).join(', ')); return ids.filter(id => m.some(x => (x instanceof RegExp ? x.test(id) : x === id))); };
export function savePose(ctx, name, part = 'whole') {
  const ids = partIds(part, ctx.poseIds().filter(id => !['bodyX', 'bodyY', 'depth', 's'].includes(id)));
  const pose = { name: String(name).slice(0, 40), part, character: ctx.character(), values: Object.fromEntries(ids.map(id => [id, +ctx.current(id).toFixed(2)])) };
  store.set([...store.get().filter(x => x.name !== pose.name), pose]);
  return pose;
}
export const poses = () => store.get();
export function applyPose(ctx, name) {
  const pose = store.get().find(x => x.name === name);
  if (!pose) throw Error('No saved pose ' + name);
  ctx.putPose(pose.values);
  return pose;
}
export function deletePose(name) { store.set(store.get().filter(x => x.name !== name)); }

// ---------------------------------------------------------------- copy / paste keys across frames, shots and characters
let clip = null;
export function copyKeys(ctx, { from = 0, to = ctx.project().length - 1, part = 'whole' } = {}) {
  const p = ctx.project(), ids = partIds(part, Object.keys(p.tracks).filter(id => !id.startsWith('cam.')));
  clip = { length: to - from + 1, character: ctx.character(), tracks: {} };
  for (const id of ids) {
    const ks = p.tracks[id].filter(k => k.f >= from && k.f <= to).map(k => ({ ...k, f: k.f - from }));
    if (!ks.some(k => k.f === 0)) ks.unshift({ f: 0, v: valueAt(p, id, from), ease: 'ease' });
    clip.tracks[id] = ks;
  }
  return { controls: Object.keys(clip.tracks).length, frames: clip.length };
}
export function pasteKeys(ctx, at = ctx.frame()) {
  if (!clip) throw Error('Copy keys first');
  const p = ctx.project(), known = new Set(ctx.trackIds());
  ctx.pushUndo('Paste keys');
  let n = 0, skipped = [];
  for (const [id, ks] of Object.entries(clip.tracks)) {
    if (!known.has(id)) { skipped.push(id); continue; }
    const [lo, hi] = ctx.range(id);
    for (const k of ks) { setKey(p, id, at + k.f, DISCRETE.has(id) ? k.v : Math.max(lo, Math.min(hi, k.v)), k.ease); n++; }
  }
  if (at + clip.length > p.length) p.length = at + clip.length;
  ctx.changed(true);
  return { keys: n, at, skipped, from: clip.character };
}

// ---------------------------------------------------------------- animation layers
export function addLayer(p, name) { (p.layers ||= []).push({ layer: true, name: name || `Layer ${p.layers.length + 1}`, on: true, weight: 1, tracks: {} }); return p.layers.length - 1; }
// the value to store in the edited track so the final pose equals v
export function keyValue(p, target, id, f, v) {
  if (DISCRETE.has(id)) return v;
  const total = valueAt(p, id, f);
  if (target === p) return v - (total - valueAt({ tracks: p.tracks, stepped: p.stepped }, id, f));
  const w = target.on === false ? 0 : (target.weight ?? 1);
  return w ? (v - (total - w * layerValue(target, id, f))) / w : 0;
}

// ---------------------------------------------------------------- Euler filter: no 360° flips between keys
export function eulerFilter(ctx) {
  const p = ctx.project();
  ctx.pushUndo('Euler filter');
  let n = 0;
  for (const [id, ks] of Object.entries(p.tracks)) {
    if (!/yaw|turn|rot|roll|Rot/i.test(id) || DISCRETE.has(id)) continue;
    for (let i = 1; i < ks.length; i++) while (Math.abs(ks[i].v - ks[i - 1].v) > 180) { ks[i].v += ks[i].v > ks[i - 1].v ? -360 : 360; n++; }
  }
  ctx.changed();
  return { fixed: n };
}

// ---------------------------------------------------------------- balance: centre of gravity over the feet
const MASS = [[/head/, 0.32], [/shirt|pelvis|neck|hood/, 0.38], [/leg/, 0.08], [/hand|cuff|sleeve/, 0.035], [/tail/, 0.01]];
export function balance(view) {
  const cog = V(), feet = [];
  let total = 0;
  for (const o of view.objects) {
    const m = MASS.find(([re]) => re.test(o.m.name));
    if (!m) continue;
    const c = V();
    for (let i = 0; i < o.buf.length; i += 3) c.x += o.buf[i], c.y += o.buf[i + 1], c.z += o.buf[i + 2];
    c.multiplyScalar(3 / o.buf.length);
    cog.addScaledVector(c, m[1]); total += m[1];
    if (/leg/.test(o.m.name)) for (let i = 0; i < o.buf.length; i += 3) if (o.buf[i + 2] < 0.06) feet.push([o.buf[i], o.buf[i + 1]]);
  }
  cog.multiplyScalar(1 / total);
  if (!feet.length) return { cog, grounded: false, balanced: null };
  const xs = feet.map(q => q[0]), ys = feet.map(q => q[1]), m = 0.02;
  const inside = cog.x > Math.min(...xs) - m && cog.x < Math.max(...xs) + m && cog.y > Math.min(...ys) - m && cog.y < Math.max(...ys) + m;
  return { cog, grounded: true, balanced: inside, offCm: inside ? 0 : +(100 * Math.max(Math.min(...xs) - m - cog.x, cog.x - Math.max(...xs) - m, Math.min(...ys) - m - cog.y, cog.y - Math.max(...ys) - m, 0)).toFixed(1) };
}

// ---------------------------------------------------------------- reference video on a plane behind the character
let ref = null;
export function setReference(view, url, opts = {}) {
  clearReference(view);
  if (!url) return null;
  const video = document.createElement('video');
  video.src = url; video.muted = true; video.playsInline = true; video.crossOrigin = 'anonymous'; video.preload = 'auto';
  const tex = new THREE.VideoTexture(video);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: opts.opacity ?? 0.6, depthWrite: false });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), mat);
  mesh.rotation.x = Math.PI / 2;   // stands up, facing the front camera
  const place = () => { const ar = (video.videoWidth || 16) / (video.videoHeight || 9), hgt = opts.height ?? 1.3; mesh.scale.set(hgt * ar, hgt, 1); mesh.position.set(opts.x ?? 0, opts.y ?? 0.9, hgt / 2 + (opts.z ?? 0)); };
  video.addEventListener('loadedmetadata', place);
  place();
  mesh.renderOrder = -1;
  view.scene.add(mesh);
  ref = { video, mesh, opts, ready: new Promise(r => video.addEventListener('loadeddata', () => r(true), { once: true })) };
  return ref;
}
export function clearReference(view) { if (!ref) return; view.scene.remove(ref.mesh); ref.mesh.material.map.dispose(); ref.mesh.material.dispose(); ref.video.removeAttribute('src'); ref.video.load(); ref = null; }
export function syncReference(seconds, playing) {
  if (!ref) return;
  const t = Math.max(0, seconds + (ref.opts.offset || 0));
  if (playing) { if (ref.video.paused) { ref.video.currentTime = t; ref.video.play().catch(() => {}); } }
  else { if (!ref.video.paused) ref.video.pause(); if (Math.abs(ref.video.currentTime - t) > 0.02) ref.video.currentTime = t; }
}
export const referenceInfo = () => (ref ? { duration: ref.video.duration || null, time: ref.video.currentTime, width: ref.video.videoWidth, height: ref.video.videoHeight } : null);

// ---------------------------------------------------------------- retargeting: the same animation on another character
export function retargetTracks(tracks, known, range) {
  const out = {}, dropped = [];
  for (const [id, ks] of Object.entries(tracks)) {
    if (!known.has(id)) { dropped.push(id); continue; }
    const [lo, hi] = range(id);
    out[id] = ks.map(k => ({ ...k, v: DISCRETE.has(id) ? k.v : Math.max(lo, Math.min(hi, k.v)) }));
  }
  return { tracks: out, dropped };
}
export { EASES };
