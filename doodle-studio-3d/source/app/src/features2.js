// Feature picks, part 2: belly squash and stretch with anticipation and overshoot, hand
// contact with the body, a beat-synced camera, multi-cam angles with cuts, a floor-plan camera path,
// previz grey, posing from a pen stick figure and script-to-blocking. Halftone shadows
// live on the stage (stage.halftone) and are built by Blender.
import * as THREE from 'three';
import { setKey, valueAt } from './project.js';
import { solve, endPoint, LIMB } from './animtools2.js';

const CAM = ['yaw', 'pitch', 'dist', 'lens', 'roll', 'tx', 'ty', 'tz'];
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

// ---------------------------------------------------------------- squash and stretch (SQUASH Body, volume kept, the face never changes size)
export const SQUASH_MOVES = { land: 'Landing', jump: 'Jump take-off', bounce: 'Bouncy settle', recoil: 'Recoil (surprise)' };
const SQUASH_SEQ = {
  // [frames from the hit, share of the amount, ease]: anticipation first, then the hit, overshoot, settle
  land: [[-6, 0, 'ease'], [-2, -0.6, 'linear'], [0, 1, 'out'], [4, -0.3, 'ease'], [9, 0.08, 'ease'], [13, 0, 'ease']],
  jump: [[-9, 0, 'ease'], [-3, 0.8, 'ease'], [0, -0.7, 'out'], [5, 0.15, 'ease'], [10, 0, 'ease']],
  bounce: [[0, 1, 'out'], [4, -0.5, 'ease'], [8, 0.25, 'ease'], [12, -0.1, 'ease'], [16, 0, 'ease']],
  recoil: [[-4, 0, 'ease'], [-1, 0.4, 'ease'], [2, -0.9, 'out'], [6, 0.2, 'ease'], [11, 0, 'ease']],
};
export function squashMove(ctx, kind, F, amount = 20) {
  const seq = SQUASH_SEQ[kind];
  if (!seq) throw Error('kind must be ' + Object.keys(SQUASH_SEQ).join(', '));
  const p = ctx.project(), a = clamp(amount, 2, 30), keys = [];
  for (const [df, k, ease] of seq) {
    const f = F + df;
    if (f < 0 || f >= p.length) continue;
    setKey(p, 'squashBody', f, +(a * k).toFixed(1), ease);
    keys.push(f);
  }
  return { kind, frame: F, keys };
}

// ---------------------------------------------------------------- hand contact: a paw resting on the body (hip, belly, chest)
// The arms are short and swing mostly sideways, so contact is with the near side of the body.
// The spot is picked at f0 on the hoodie mesh within reach; every frame after, the paw follows
// that same spot as the body moves, a paw's thickness off the surface. Never into the head.
export const CONTACTS = { hip: 'Hand on hip', belly: 'Hand on belly', chest: 'Hand on chest' };
const BODY_MESH = /_(shirt|pelvis)$/;
function bodyVerts(view) {
  const out = [];
  for (const o of view.objects) if (BODY_MESH.test(o.m.name)) out.push(o);
  return out;
}
function contactSpot(view, v, limb, where, range) {
  view.pose(v);
  const side = limb.slice(-1), sh = boneAt(view, `upper_arm_fk.${side}`), reach = endPoint(view, { ...v, [`elbow${side}`]: 0 }, limb).distanceTo(sh) * 0.95;
  const hip = boneAt(view, `thigh_fk.${side}`), t = boneAt(view, 'torso'), turn = (Number(v.turn) || 0) * Math.PI / 180;
  const fwd = new THREE.Vector3(Math.sin(turn), -Math.cos(turn), 0), across = new THREE.Vector3(Math.cos(turn), Math.sin(turn), 0), mine = Math.sign(sh.clone().sub(t).dot(across));
  const score = { hip: q => q.z, belly: q => -q.clone().sub(t).dot(fwd) + Math.abs(q.z - (sh.z + hip.z) / 2) * 0.5, chest: q => -q.clone().sub(t).dot(fwd) + Math.abs(q.z - sh.z) * 0.5 }[where];
  const cands = [];
  for (const o of bodyVerts(view)) for (let i = 0; i < o.buf.length; i += 3) {
    const q = new THREE.Vector3(o.buf[i], o.buf[i + 1], o.buf[i + 2]);
    if (q.distanceTo(sh) > reach || q.z > sh.z || Math.sign(q.clone().sub(t).dot(across)) !== mine) continue;
    cands.push({ s: score(q), o, i, q });
  }
  if (!cands.length) throw Error(`The ${limb === 'armL' ? 'left' : 'right'} arm cannot reach the body there`);
  cands.sort((a, b) => a.s - b.s);
  // the best-scoring spots the joint limits really let the paw reach (a few, 1 cm apart)
  const paw = boneAt(view, `DEF-hand.${side}`).distanceTo(boneAt(view, `DEF-hand.${side}`, true)), tried = [];
  let best = null;
  for (const c of cands) {
    if (tried.length >= 14) break;
    if (tried.some(x => x.distanceTo(c.q) < 0.01)) continue;
    tried.push(c.q);
    const err = solve(view, v, limb, spotTarget(view, c, paw), range, 14).error;
    if (!best || err < best.err - 0.004) best = { ...c, err };
    if (err < 0.008) break;
  }
  view.pose(v);
  return { o: best.o, i: best.i };
}
function spotTarget(view, spot, paw) {
  const b = spot.o.buf, q = new THREE.Vector3(b[spot.i], b[spot.i + 1], b[spot.i + 2]);
  const t = boneAt(view, 'torso'), out = new THREE.Vector3(q.x - t.x, q.y - t.y, 0);
  if (out.lengthSq() < 1e-8) out.set(1, 0, 0);
  return q.addScaledVector(out.normalize(), paw * 0.5);
}
// the arm part that clips into the head lowers until it does not
function unclip(view, v, ctx) {
  for (let k = 0; k < 24; k++) {
    view.pose(v);
    const c = view.ruleCheck().clips.filter(n => /arm|hand|cuff|sleeve/.test(n));
    if (!c.length) return v;
    for (const side of ['L', 'R']) if (c.some(n => n.endsWith('.' + side))) { const id = 'arm' + side, [lo] = ctx.range(id); v = { ...v, [id]: Math.max(lo, v[id] - 5) }; }
  }
  return v;
}
export function handContact(ctx, limb, where, f0, f1, step = 2) {
  if (!CONTACTS[where]) throw Error('where must be ' + Object.keys(CONTACTS).join(', '));
  const p = ctx.project(), view = ctx.view(), side = limb.slice(-1);
  const spot = contactSpot(view, ctx.valuesAt(f0), limb, where, ctx.range);
  let worst = 0, n = 0;
  for (let f = f0; f <= f1; f = f === f1 ? f1 + 1 : Math.min(f1, f + step)) {
    let v = ctx.valuesAt(f);
    view.pose(v);
    const paw = boneAt(view, `DEF-hand.${side}`).distanceTo(boneAt(view, `DEF-hand.${side}`, true));
    const r = solve(view, v, limb, spotTarget(view, spot, paw), ctx.range, 24);
    v = unclip(view, { ...v, ...r.values }, ctx);
    for (const id of LIMB[limb].ids) setKey(p, id, f, +v[id].toFixed(2), 'linear');
    worst = Math.max(worst, r.error); n++;
  }
  view.pose(ctx.valuesAt(ctx.frame()));
  return { limb, where, from: f0, to: f1, keys: n, worstErrorCm: +(worst * 100).toFixed(1) };
}

// ---------------------------------------------------------------- beat-synced camera and multi-cam
export const BEAT_STYLES = { punch: 'Push in on every other beat', sway: 'Sway the orbit on the beat', cut: 'Cut between saved angles' };
export function beatsOf(ctx) {
  const m = (ctx.project().markers || []).filter(x => /^\s*beat\b/i.test(x.note || '')).map(x => x.f);
  return m.length ? m : ctx.detectBeats();
}
export function beatCamera(ctx, style = 'punch', { amount = 0.08, angles = null } = {}) {
  const p = ctx.project(), beats = beatsOf(ctx).filter(f => f > 0 && f < p.length);
  if (!beats.length) throw Error('No beats: tap beat markers (B) or import the music first');
  if (style === 'cut') {
    const names = angles || Object.keys(ctx.scene().angles || {});
    if (names.length < 2) throw Error('Save at least two camera angles first (Camera › Save this angle as…)');
    beats.forEach((f, i) => cutTo(ctx, names[(i + 1) % names.length], f));
    if (beats[0] > 0) cutTo(ctx, names[0], 0);
    return { style, beats: beats.length };
  }
  const id = style === 'sway' ? 'cam.yaw' : 'cam.dist', base = valueAt(p, id, beats[0]);
  // eased both ways, never a jump: every beat lands on a key and the camera breathes between them
  beats.forEach((f, i) => {
    const v = style === 'sway' ? base + (i % 2 ? -1 : 1) * amount * 60 : base * (1 - (i % 2 ? 0 : amount));
    setKey(p, id, f, +v.toFixed(3), 'ease');
  });
  return { style, beats: beats.length, control: id };
}
export function saveAngle(ctx, name) {
  name = String(name || '').trim();
  if (!name) throw Error('Name the angle');
  const sc = ctx.scene(), p = ctx.project(), f = ctx.frame();
  (sc.angles ||= {})[name] = Object.fromEntries(CAM.map(k => [k, valueAt(p, 'cam.' + k, f)]));
  return { angle: name, angles: Object.keys(sc.angles) };
}
// a hard cut: hold the old angle up to the frame before, the new one from the frame
export function cutTo(ctx, name, F) {
  const a = ctx.scene().angles?.[name];
  if (!a) throw Error(`No angle "${name}". Saved: ${Object.keys(ctx.scene().angles || {}).join(', ') || 'none'}`);
  const p = ctx.project();
  for (const k of CAM) {
    if (F > 0) setKey(p, 'cam.' + k, F - 1, valueAt(p, 'cam.' + k, F - 1), 'hold');
    setKey(p, 'cam.' + k, F, a[k], 'hold');
  }
  p.camCuts = [...new Set([...(p.camCuts || []), F])].filter(f => f > 0).sort((x, y) => x - y);
  return { angle: name, frame: F };
}
// markers like "cam: B" cut to that saved angle
export function camMarkers(ctx) {
  const done = [];
  for (const m of ctx.project().markers || []) {
    const r = /^\s*cam\s*:\s*(.+?)\s*$/i.exec(m.note || '');
    if (r) done.push(cutTo(ctx, r[1], m.f));
  }
  return { cuts: done };
}

// ---------------------------------------------------------------- floor-plan camera path (top view, metres; Bunny at 0,0, the front is -y)
export function camPlanPos(p, f) {
  const c = Object.fromEntries(CAM.map(k => [k, valueAt(p, 'cam.' + k, f)])), y = c.yaw * Math.PI / 180, pi = c.pitch * Math.PI / 180;
  return { x: c.tx + Math.sin(y) * Math.cos(pi) * c.dist, y: c.ty - Math.cos(y) * Math.cos(pi) * c.dist, cam: c };
}
// the camera glides along the drawn path, eased at both ends, still aimed where it was
export function floorPath(ctx, pts, f0, f1, step = 3) {
  if (!pts || pts.length < 2) throw Error('Draw a path with at least two points');
  const p = ctx.project(), { cam } = camPlanPos(p, f0), cp = Math.cos(cam.pitch * Math.PI / 180);
  const seg = [0];
  for (let i = 1; i < pts.length; i++) seg.push(seg[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const total = seg[seg.length - 1] || 1;
  const at = s => { let i = 1; while (i < seg.length - 1 && seg[i] < s) i++; const k = (s - seg[i - 1]) / Math.max(1e-9, seg[i] - seg[i - 1]); return [pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * k, pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * k]; };
  let lastYaw = null, n = 0;
  for (let f = f0; f <= f1; f = f === f1 ? f1 + 1 : Math.min(f1, f + step)) {
    const t = (f - f0) / Math.max(1, f1 - f0), e = t * t * (3 - 2 * t);
    const [x, y] = at(e * total), rx = x - cam.tx, ry = y - cam.ty;
    let yaw = Math.atan2(rx, -ry) * 180 / Math.PI;
    if (lastYaw != null) while (yaw - lastYaw > 180) yaw -= 360;
    if (lastYaw != null) while (yaw - lastYaw < -180) yaw += 360;
    lastYaw = yaw;
    const ease = f === f0 || f >= f1 ? 'ease' : 'linear';
    setKey(p, 'cam.yaw', f, +yaw.toFixed(2), ease);
    setKey(p, 'cam.dist', f, +Math.max(0.3, Math.hypot(rx, ry) / cp).toFixed(3), ease);
    n++;
  }
  return { from: f0, to: f1, keys: n, metres: +total.toFixed(2) };
}
export function planDialog(ctx, { h, modal }, onDone) {
  const p = ctx.project(), R = 6, S = 360, cur = camPlanPos(p, ctx.frame());
  const toPx = ([x, y]) => [S / 2 + x / R * S / 2, S / 2 - y / R * S / 2], toM = (px, py) => [(px - S / 2) / (S / 2) * R, -(py - S / 2) / (S / 2) * R];
  const cv = h('canvas', { width: S, height: S, class: 'plan-canvas', style: 'touch-action:none;cursor:crosshair' });
  let pts = [];
  const draw = () => {
    const g = cv.getContext('2d');
    g.fillStyle = '#E0A64B'; g.fillRect(0, 0, S, S);
    g.strokeStyle = 'rgba(31,31,29,0.25)'; g.lineWidth = 1;
    for (let m = -R; m <= R; m++) { const [a] = toPx([m, 0]), [, b] = toPx([0, m]); g.beginPath(); g.moveTo(a, 0); g.lineTo(a, S); g.moveTo(0, b); g.lineTo(S, b); g.stroke(); }
    g.fillStyle = '#1F1F1D'; g.font = '13px system-ui'; g.fillText('front', S / 2 - 14, S - 6);
    const [bx, by] = toPx([0, 0]); g.beginPath(); g.arc(bx, by, 7, 0, Math.PI * 2); g.fill(); g.fillText(ctx.charName(), bx + 10, by + 4);
    const [cx, cy] = toPx([cur.x, cur.y]); g.strokeStyle = '#1F1F1D'; g.lineWidth = 3; g.strokeRect(cx - 7, cy - 5, 14, 10);
    if (pts.length) { g.beginPath(); pts.map(toPx).forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke(); }
  };
  const xy = e => { const r = cv.getBoundingClientRect(); return toM((e.clientX - r.left) * S / r.width, (e.clientY - r.top) * S / r.height); };
  let down = false;
  cv.addEventListener('pointerdown', e => { down = true; cv.setPointerCapture(e.pointerId); pts = [xy(e)]; draw(); });
  cv.addEventListener('pointermove', e => { if (!down) return; const q = xy(e), l = pts[pts.length - 1]; if (Math.hypot(q[0] - l[0], q[1] - l[1]) > 0.05) { pts.push(q); draw(); } });
  cv.addEventListener('pointerup', () => { down = false; });
  draw();
  modal({ h }, 'Floor-plan camera path', close => {
    const to = h('input', { type: 'number', min: ctx.frame() + 1, max: p.length - 1, value: p.length - 1, style: 'width:64px', 'aria-label': 'To frame' });
    return [h('p', { class: 'hint' }, `Top view, 1 m squares, ${ctx.charName()} in the middle and the front at the bottom. Draw where the camera travels; it keeps aiming where it aims now and eases in and out.`),
      cv, h('label', { class: 'row' }, `From frame ${ctx.frame()} to `, to),
      h('div', { class: 'row' }, h('button', { class: 'primary', onclick: () => { if (pts.length > 1) { close(); onDone(pts, ctx.frame(), Number(to.value)); } } }, 'Key the path'), h('button', { onclick: close }, 'Cancel'))];
  });
}

// ---------------------------------------------------------------- previz grey (viewport) - renders use the shot's previz flag
const GREY = new THREE.Color(0x8c8c88), WHITE = new THREE.Color(0xffffff), MUSTARD = new THREE.Color(0xe0a64b);
export function setPreviz(view, on) {
  for (const o of view.objects) {
    const m = o.mesh.material;
    if (m.uniforms?.base) { m.userData.base ||= m.uniforms.base.value.clone(); m.uniforms.base.value.copy(on ? GREY : m.userData.base); }
    else if (m.color) { m.color.copy(on ? GREY : WHITE); m.vertexColors = !on; m.needsUpdate = true; }
  }
  return { previz: on };
}
export { MUSTARD };

// ---------------------------------------------------------------- pose from a pen stick figure
const V = () => new THREE.Vector3();
function boneAt(view, name, tail = false) {
  const b = view.rig.bones.get(name);
  if (!b) return null;
  view.group.updateMatrixWorld();
  return (tail ? b.tailV : b.headV).clone().applyMatrix4(view.rig.A.get(name) || new THREE.Matrix4()).applyMatrix4(view.group.matrixWorld);
}
const scr = (view, v, aspect) => { const q = v.clone().project(view.camera); return [(q.x + 1) / 2 * aspect, (1 - q.y) / 2]; };
function fromScreen(view, [x, y], aspect, through) {
  const n = V(); view.camera.getWorldDirection(n);
  const ray = new THREE.Raycaster();
  ray.setFromCamera(new THREE.Vector2(x / aspect * 2 - 1, -(y * 2 - 1)), view.camera);
  return ray.ray.intersectPlane(new THREE.Plane().setFromNormalAndCoplanarPoint(n, through), V());
}
const sub = (a, b) => [a[0] - b[0], a[1] - b[1]], len = a => Math.hypot(a[0], a[1]), ang = a => Math.atan2(a[0], -a[1]);
const angDiff = (a, b) => Math.abs(((a - b + 3 * Math.PI) % (2 * Math.PI)) - Math.PI);
// strokes: arrays of [x, y] as fractions of the frame (y down); aspect = width / height
export function classifyStick(strokes, aspect) {
  const S = strokes.filter(s => s.length > 1).map(s => s.map(([x, y]) => [x * aspect, y]));
  const box = s => { const xs = s.map(p => p[0]), ys = s.map(p => p[1]); return { w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys), cx: (Math.max(...xs) + Math.min(...xs)) / 2, cy: (Math.max(...ys) + Math.min(...ys)) / 2 }; };
  const closed = s => { const b = box(s); return len(sub(s[0], s[s.length - 1])) < 0.35 * Math.hypot(b.w, b.h) && b.w > 0.01 && b.h > 0.01 && Math.max(b.w / b.h, b.h / b.w) < 2.2; };
  const heads = S.filter(closed).sort((a, b) => box(a).cy - box(b).cy);
  const head = heads[0] || null, rest = S.filter(s => s !== head);
  const spine = rest.slice().sort((a, b) => box(b).h - box(a).h)[0];
  if (!spine) throw Error('Draw at least a body line (and a head circle, arms and legs)');
  const [e0, e1] = [spine[0], spine[spine.length - 1]], neck = e0[1] < e1[1] ? e0 : e1, hip = neck === e0 ? e1 : e0;
  const limbs = rest.filter(s => s !== spine).map(s => {
    const a = s[0], b = s[s.length - 1], na = Math.min(len(sub(a, neck)), len(sub(a, hip))), nb = Math.min(len(sub(b, neck)), len(sub(b, hip)));
    const root = na <= nb ? a : b, end = root === a ? b : a;
    return { kind: len(sub(root, neck)) <= len(sub(root, hip)) ? 'arm' : 'leg', end };
  });
  return { head: head ? [box(head).cx, box(head).cy] : null, neck, hip, arms: limbs.filter(l => l.kind === 'arm').map(l => l.end), legs: limbs.filter(l => l.kind === 'leg').map(l => l.end) };
}
export function poseFromStick(ctx, strokes, aspect, F = ctx.frame()) {
  const st = classifyStick(strokes, aspect), view = ctx.view(), p = ctx.project();
  let v = ctx.valuesAt(F);
  const spineOf = vals => { view.rig.pose(vals); const n = scr(view, boneAt(view, 'head'), aspect), hl = boneAt(view, 'thigh_fk.L'), hr = boneAt(view, 'thigh_fk.R'); return { n, h: scr(view, hl.add(hr).multiplyScalar(0.5), aspect) }; };
  // lean: the body tilt whose neck-to-hip line matches the drawing best
  const want = ang(sub(st.neck, st.hip));
  let best = [1e9, 0];
  for (let t = -25; t <= 25; t += 2.5) { const s = spineOf({ ...v, bodyTilt: t }), d = angDiff(ang(sub(s.n, s.h)), want); if (d < best[0]) best = [d, t]; }
  v = { ...v, bodyTilt: best[1] };
  const sp = spineOf(v), k = len(sub(sp.n, sp.h)) / Math.max(1e-6, len(sub(st.neck, st.hip)));
  // head tilt from where the head circle sits on the neck
  if (st.head) {
    const hw = ang(sub(st.head, st.neck));
    let hb = [1e9, 0];
    for (let t = -20; t <= 20; t += 2.5) { view.rig.pose({ ...v, rot: t }); const d = angDiff(ang(sub(scr(view, view.headPoint(), aspect), scr(view, boneAt(view, 'head'), aspect))), hw); if (d < hb[0]) hb = [d, t]; }
    v.rot = hb[1];
  }
  // arms and legs: each drawn line goes to the hand or foot on that side of the screen
  const ends = { arm: ['armL', 'armR'], leg: ['legL', 'legR'] }, out = {};
  for (const kind of ['arm', 'leg']) {
    const drawn = (kind === 'arm' ? st.arms : st.legs).slice(0, 2).sort((a, b) => a[0] - b[0]);
    const limbs = ends[kind].map(l => ({ l, x: scr(view, endPoint(view, v, l), aspect)[0] })).sort((a, b) => a.x - b.x);
    const pair = drawn.length === 1 ? [[drawn[0], limbs.reduce((m, c) => (Math.abs(c.x - drawn[0][0]) < Math.abs(m.x - drawn[0][0]) ? c : m)).l]] : drawn.map((d, i) => [d, limbs[i].l]);
    for (const [d, limb] of pair) {
      view.rig.pose(v);
      const rootB = kind === 'arm' ? `upper_arm_fk.${limb.slice(-1)}` : `thigh_fk.${limb.slice(-1)}`, rootW = boneAt(view, rootB), rootS = scr(view, rootW, aspect);
      const rel = sub(d, kind === 'arm' ? st.neck : st.hip), target = [rootS[0] + rel[0] * k, rootS[1] + rel[1] * k];
      const t = fromScreen(view, target, aspect, endPoint(view, v, limb));
      if (!t) continue;
      const r = solve(view, v, limb, t, ctx.range, 24);
      v = { ...v, ...r.values };
      out[limb] = +(r.error * 100).toFixed(1);
    }
  }
  v = unclip(view, v, ctx);   // arms above the shoulders must never cut into the head
  const ids = ['bodyTilt', 'rot', ...Object.keys(out).flatMap(l => LIMB[l].ids)];
  for (const id of ids) setKey(p, id, F, +Number(v[id]).toFixed(2), 'ease');
  view.rig.pose(ctx.valuesAt(ctx.frame()));
  return { frame: F, bodyTilt: v.bodyTilt, headTilt: v.rot, limbs: out, keyed: ids.length };
}

// ---------------------------------------------------------------- script to blocking
// Scene headings (INT./EXT. or # lines) start shots; "NAME: line" or plain lines are spoken;
// (actions) and [actions] pick a motion or a face from the library.
const FACE_WORDS = ['happy', 'sad', 'angry', 'scared', 'shocked', 'surprised', 'smug', 'confused', 'bored', 'excited', 'nervous', 'panic', 'dread', 'laugh', 'cry', 'pout', 'proud', 'tired', 'love', 'disgust'];
export function parseScript(text, fps = 30) {
  const shots = [];
  let cur = null;
  const open = name => { cur = { name, lines: [], frames: 0 }; shots.push(cur); };
  for (let raw of String(text).replace(/\r/g, '').split('\n')) {
    raw = raw.trim();
    if (!raw) continue;
    if (/^(#+\s*|(INT|EXT|INT\/EXT)[.\s])/i.test(raw)) { open(raw.replace(/^#+\s*/, '')); continue; }
    if (!cur) open('Scene 1');
    const acts = [...raw.matchAll(/[([*]([^)\]*]+)[)\]*]/g)].map(m => m[1].trim());
    let say = raw.replace(/[([*][^)\]*]+[)\]*]/g, ' ').replace(/\s+/g, ' ').trim();
    const who = /^([A-Z][A-Za-z ]{0,20}):\s*/.exec(say);
    if (who) say = say.slice(who[0].length);
    const words = say ? say.split(' ').length : 0;
    const length = Math.max(Math.round(fps * (words ? Math.max(1.2, words / 2.7 + 0.3) : 1.5)), Math.round(fps * 0.8));
    cur.lines.push({ who: who?.[1] || null, say, acts, f: cur.frames, length });
    cur.frames += length;
  }
  return shots;
}
export function actionFor(rows, act) {
  const words = act.toLowerCase().split(/[^a-z]+/).filter(w => w.length > 2);
  const face = words.find(w => FACE_WORDS.includes(w));
  const byWord = (cat, w) => rows.find(r => r.category === cat && (r.name + ' ' + (r.tags || []).join(' ') + ' ' + r.id).toLowerCase().includes(w));
  if (face) { const r = byWord('expression', face); if (r) return r; }
  for (const w of words) { const r = byWord('motion', w); if (r) return r; }
  return null;
}

// where the body parts are now (metres, world): head size, neck and hip height, hands
export function measure(view, values) {
  view.pose(values);
  const h0 = boneAt(view, 'head'), h1 = boneAt(view, 'head', true), r = view.ruleCheck();
  const out = { headSize: +h0.distanceTo(h1).toFixed(4), neckZ: +h0.z.toFixed(4), hipZ: +boneAt(view, 'thigh_fk.L').z.toFixed(4),
    handL: endPoint(view, values, 'armL').toArray().map(x => +x.toFixed(3)), handR: endPoint(view, values, 'armR').toArray().map(x => +x.toFixed(3)), feet: r.feet, clips: r.clips };
  return out;
}
