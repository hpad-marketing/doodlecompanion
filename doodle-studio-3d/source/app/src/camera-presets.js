// Camera presets: pick a target (Bunny, his face, eyes, hands, feet or a registered object),
// then one click frames it in a named shot size and angle, or keys a named camera move
// from the playhead. Everything is written to the cam.* tracks, so a preset renders the
// same in Blender as in the viewport.
//
// Hook-up (main.js): bindCameraPresets(ctx) once at boot, and cameraPresetsPanel(ctx) in the
// Camera tab. ctx = { view, project(), frame(), current(id), setValue(id, v), pushUndo(), refresh(), toast(msg) }.
// The desktop MCP calls window.ds3dCameraPresets.apply({...}).
import * as THREE from 'three';
import { BunnyRig } from './rig.js';
import { setKey, valueAt, CAM_DEFAULT } from './project.js';

const RAD = Math.PI / 180;
const CAM_KEYS = Object.keys(CAM_DEFAULT);
const STAGE_BODY_UNIT = 100 * 0.00205066345 * 490 * 0.4;   // same as rig.js

// ---------------------------------------------------------------- the presets (our own wording)
// Shot sizes. For Bunny the frame edges land on his own landmarks; for anything else
// `fill` is how much of the frame height the target takes.
export const SIZES = [
  ['ews', 'Extreme wide', 'Tiny in a big world. Sets the place before anything happens.', 0.06],
  ['ws', 'Wide', 'Whole body small in the frame with plenty of room around. Shows where he is.', 0.2],
  ['fs', 'Full', 'Head to feet, filling the frame top to bottom. Body language reads best here.', 0.85],
  ['mfs', 'Medium full', 'Cut at the legs (the "cowboy" framing). Room for gestures and a prop.', 1.15],
  ['ms', 'Medium', 'Waist up. The everyday talking shot: face and hands both read.', 1.45],
  ['mcu', 'Medium close-up', 'Chest up, ear tips leaving the frame. Personal, but still shows the hands at the chest.', 2.0],
  ['cu', 'Close-up', 'The face fills the frame. For a reaction or a line that matters.', 2.6],
  ['ecu', 'Extreme close-up', 'Just the eyes. Pure intensity; use it once, not often.', 5.0],
];

// Angles: where the camera sits. `height` puts the lens at a body landmark and keeps it level;
// `pitch` tilts the camera itself (the set tilts with it, so it stays physically true).
export const ANGLES = [
  ['eye', 'Eye level', 'Lens at his eye height, looking straight on. Neutral and honest.', { height: 'eyes' }],
  ['shoulder', 'Shoulder level', 'Lens at shoulder height. A touch lower than the eyes, so he feels a bit stronger.', { height: 'shoulder' }],
  ['hip', 'Hip level', 'Lens at the hips. Great for hands, props and a walk.', { height: 'waist' }],
  ['knee', 'Knee level', 'Lens at the knees. Makes him look taller and the floor bigger.', { height: 'legMid' }],
  ['ground', 'Ground level', 'Lens resting on the floor. Feet and floor become the foreground.', { height: 'ground' }],
  ['low', 'Low angle', 'Below him, looking up. Power, confidence, a hero beat.', { pitch: -20 }],
  ['worm', "Worm's-eye", 'Right down by the floor looking steeply up on a wide lens. Huge and dramatic.', { pitch: -48, lens: 24 }],
  ['high', 'High angle', 'Above him, looking down. Small, unsure, outnumbered.', { pitch: 30 }],
  ['overhead', "Bird's-eye", 'Straight down from above. A map of the moment; turns him into a shape.', { pitch: 88 }],
  ['dutch-l', 'Dutch tilt left', 'Frame rolled anticlockwise. Something is off.', { height: 'eyes', roll: -15 }],
  ['dutch-r', 'Dutch tilt right', 'Frame rolled clockwise. Unease, madness, a twist.', { height: 'eyes', roll: 15 }],
  ['tq-l', '¾ from left', 'Camera swung to screen left of his front. Rounder and more natural than straight on.', { height: 'eyes', yaw: -40 }],
  ['tq-r', '¾ from right', 'Camera swung to screen right of his front.', { height: 'eyes', yaw: 40 }],
  ['profile-l', 'Profile left', 'Side view from screen left. Clean silhouette, good for walks and face-offs.', { height: 'eyes', yaw: -90 }],
  ['profile-r', 'Profile right', 'Side view from screen right.', { height: 'eyes', yaw: 90 }],
  ['back', 'From behind', 'Behind him, looking where he looks. Mystery, or showing what he faces.', { height: 'eyes', yaw: 180 }],
];

// Framings that place the camera on or beside the character.
export const VIEWS = [
  ['pov', 'Point of view', 'The camera is his eyes, looking where he faces.'],
  ['ots-l', 'Over the shoulder, him on left', 'Behind his shoulder looking past him; his head in the left foreground.'],
  ['ots-r', 'Over the shoulder, him on right', 'Behind his shoulder looking past him; his head in the right foreground.'],
  ['oth', 'Over the hip', 'Low over his hip looking past him. Casual, like a bystander.'],
];

export const PLACES = [['center', 'Centre', 0], ['left', 'Left third', -1 / 3], ['right', 'Right third', 1 / 3]];

// Moves: [id, name, what it does, default seconds, group]
export const MOVES = [
  ['hold', 'Locked off', 'No movement. Keys the camera at the start and end so nothing drifts.', 3, 'Static'],
  ['push-in', 'Slow push in', 'Glides toward the target, one shot size tighter. Builds focus and tension.', 4, 'Push and pull'],
  ['pull-out', 'Slow pull out', 'Glides back, one shot size wider. Lets a moment breathe or isolates him.', 4, 'Push and pull'],
  ['push-cu', 'Push in to close-up', 'Travels from here into a close-up of the target.', 3, 'Push and pull'],
  ['pull-reveal', 'Pull back reveal', 'Starts here and backs out to a wide, revealing the place.', 4, 'Push and pull'],
  ['crash-push', 'Crash push', 'A quick, eased lunge toward him for a punchline.', 0.5, 'Push and pull'],
  ['zoom-in', 'Slow zoom in', 'Lens zooms in while the camera stays put. Flatter and more watchful than a push.', 3, 'Zoom'],
  ['zoom-out', 'Slow zoom out', 'Lens zooms out while the camera stays put.', 3, 'Zoom'],
  ['snap-zoom', 'Snap zoom', 'A very fast, eased zoom in for a comic hit.', 0.35, 'Zoom'],
  ['vertigo-in', 'Dolly zoom in', 'Moves in while zooming out: he keeps his size and the room stretches away. The vertigo feeling.', 3, 'Zoom'],
  ['vertigo-out', 'Dolly zoom out', 'Moves out while zooming in: he keeps his size and the room closes in on him.', 3, 'Zoom'],
  ['pan-l', 'Pan left', 'Camera stays put and turns to screen left.', 3, 'Pan and tilt'],
  ['pan-r', 'Pan right', 'Camera stays put and turns to screen right.', 3, 'Pan and tilt'],
  ['tilt-up', 'Tilt up', 'Camera stays put and looks up.', 2.5, 'Pan and tilt'],
  ['tilt-down', 'Tilt down', 'Camera stays put and looks down.', 2.5, 'Pan and tilt'],
  ['tilt-reveal', 'Tilt up reveal', 'Starts on his feet and tilts up to the current framing.', 3, 'Pan and tilt'],
  ['whip-in-l', 'Whip pan in from left', 'A blur of a pan that lands on the target from screen left. Great for cuts between beats.', 0.35, 'Whip'],
  ['whip-in-r', 'Whip pan in from right', 'A whip that lands on the target from screen right.', 0.35, 'Whip'],
  ['whip-out', 'Whip pan away', 'Whips off the target to screen right, to hand over to the next shot.', 0.35, 'Whip'],
  ['whip-tilt', 'Whip tilt in', 'A fast tilt that drops onto the target from above.', 0.35, 'Whip'],
  ['truck-l', 'Truck left', 'Slides sideways to screen left, still facing the same way. Parallax shows depth.', 3, 'Slide'],
  ['truck-r', 'Truck right', 'Slides sideways to screen right.', 3, 'Slide'],
  ['ped-up', 'Pedestal up', 'Rises straight up without tilting.', 3, 'Slide'],
  ['ped-down', 'Pedestal down', 'Sinks straight down without tilting.', 3, 'Slide'],
  ['crane-up', 'Crane up', 'Rises and tilts down to keep him framed. Ends a scene or shows scale.', 4, 'Crane and drone'],
  ['crane-down', 'Crane down', 'Descends from above to his eye level. Brings us into the scene.', 4, 'Crane and drone'],
  ['boom-over', 'Boom over the top', 'Climbs up and over until looking straight down on him.', 4, 'Crane and drone'],
  ['drone-reveal', 'Drone rise reveal', 'Lifts high and backs away: he shrinks into the world.', 5, 'Crane and drone'],
  ['drone-land', 'Drone descent', 'Flies down from high and far into the current framing.', 5, 'Crane and drone'],
  ['arc-l', 'Arc left', 'Circles a quarter way around him toward screen left.', 4, 'Orbit'],
  ['arc-r', 'Arc right', 'Circles toward screen right.', 4, 'Orbit'],
  ['orbit', 'Full orbit', 'One full circle around him at a steady speed. A hero or a reveal.', 8, 'Orbit'],
  ['spiral', 'Spiral push', 'Circles and pushes in at once. Rising energy.', 5, 'Orbit'],
  ['dutch-roll', 'Roll into Dutch', 'Rolls the frame into a tilt while holding him. Things are going wrong.', 2, 'Roll'],
  ['barrel', 'Barrel roll', 'The frame turns a full circle. Dizzy, dreamlike, a transition.', 3, 'Roll'],
  ['follow', 'Tracking follow', 'Keeps the current framing locked on him as he moves (bake over his keyed moves).', 4, 'Follow'],
  ['snorricam', 'Body-locked', 'Camera rigged to his body: he stays still in frame while the world moves and turns.', 4, 'Follow'],
  ['handheld', 'Handheld', 'Gentle human wobble, as if someone is holding the camera. Documentary feel.', 4, 'Handheld'],
  ['steadicam', 'Steadicam float', 'A smooth floating drift with a slight creep in. Dreamy, gliding.', 4, 'Handheld'],
  ['impact', 'Impact shake', 'A short shake that dies away. For a landing, a slam or a bass hit.', 0.5, 'Handheld'],
  ['quake', 'Heavy shake', 'A strong rumble for big moments.', 2, 'Handheld'],
  ['dread', 'Dread push', 'A very slow, barely-there push two sizes in. For tension that creeps up in a storytime.', 10, 'Combos'],
  ['scale-reveal', 'Scale reveal', 'Pulls far back and up until he is tiny against something huge. The cosmic-horror "how small we are" beat.', 8, 'Combos'],
  ['hero', 'Hero push', 'Low angle pushing in from a wide to a medium. The entrance shot.', 4, 'Combos'],
];

// ---------------------------------------------------------------- camera maths (same model as Viewport.setCamera)
const dirOf = (yaw, pitch) => new THREE.Vector3(Math.sin(yaw * RAD) * Math.cos(pitch * RAD), -Math.cos(yaw * RAD) * Math.cos(pitch * RAD), Math.sin(pitch * RAD));
const aimOf = c => new THREE.Vector3(c.tx, c.ty, c.tz);
const posOf = c => aimOf(c).addScaledVector(dirOf(c.yaw, c.pitch), c.dist);
function vfov(lens, aspect) {
  const v = 2 * Math.atan(36 / 2 / lens) / RAD;
  return aspect < 1 ? v : 2 * Math.atan(Math.tan(v * RAD / 2) / aspect) / RAD;
}
function makeCam(c, aspect, cam = new THREE.PerspectiveCamera()) {
  cam.position.copy(posOf(c));
  cam.up.set(0, 0, 1);
  cam.lookAt(aimOf(c));
  cam.rotateZ(c.roll * RAD);
  cam.fov = vfov(c.lens, aspect);
  cam.aspect = aspect;
  cam.near = 0.01; cam.far = 500;
  cam.updateProjectionMatrix();
  cam.updateMatrixWorld();
  return cam;
}
// camera at P looking at T, keeping lens and roll from base
function lookFrom(P, T, base) {
  const d = P.clone().sub(T), dist = d.length();
  d.divideScalar(dist);
  return { ...base, tx: T.x, ty: T.y, tz: T.z, dist, pitch: Math.asin(Math.max(-1, Math.min(1, d.z))) / RAD, yaw: Math.atan2(d.x, -d.y) / RAD };
}
const wrapYaw = y => ((y + 180) % 360 + 360) % 360 - 180;

// Frame `points` so they fill `box` (NDC y range) and, if given, `xPoints` fit `xBox`.
// The camera keeps its yaw, lens and roll; pitch is kept, or set so the lens sits at `heightZ`.
function solve(base, { points, xPoints, box, xBox = [-1, 1], anchor = 'center', placeX = 0 }, aspect, { heightZ = null, floorZ = 0 } = {}) {
  const c = { ...base };
  const C = new THREE.Box3().setFromPoints(points).getCenter(new THREE.Vector3());
  c.tx = C.x; c.ty = C.y; c.tz = C.z;
  const sizeY = new THREE.Box3().setFromPoints(points).getSize(new THREE.Vector3()).length();
  c.dist = Math.max(0.3, sizeY / (2 * Math.tan(vfov(c.lens, aspect) * RAD / 2)) / ((box[1] - box[0]) / 2) * 1.2);
  const cam = new THREE.PerspectiveCamera(), v = new THREE.Vector3();
  const fitPitch = () => {
    if (heightZ != null) c.pitch = Math.asin(Math.max(-0.99, Math.min(0.99, (heightZ - c.tz) / c.dist))) / RAD;
    const minP = Math.asin(Math.max(-0.99, Math.min(0.99, (floorZ + 0.03 - c.tz) / c.dist))) / RAD;   // never under the floor
    c.pitch = Math.max(c.pitch, minP);
  };
  const extent = pts => {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (const p of pts) {
      v.copy(p).applyMatrix4(cam.matrixWorldInverse);
      if (v.z > -0.01) v.z = -0.01;   // behind the lens: treat as at the lens plane
      v.applyMatrix4(cam.projectionMatrix);
      x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y);
    }
    return { x0, x1, y0, y1 };
  };
  for (let i = 0; i < 40; i++) {
    fitPitch();
    makeCam(c, aspect, cam);
    let e = extent(points), ex = xPoints ? extent(xPoints) : null;
    const s = Math.max((e.y1 - e.y0) / (box[1] - box[0]), ex ? (ex.x1 - ex.x0) / (xBox[1] - xBox[0]) : 0);
    c.dist = Math.max(0.12, c.dist * (0.35 + 0.65 * s));
    fitPitch();
    makeCam(c, aspect, cam);
    e = extent(points); ex = xPoints ? extent(xPoints) : e;
    const dy = anchor === 'top' ? e.y1 - box[1] : anchor === 'bottom' ? e.y0 - box[0] : (e.y0 + e.y1) / 2 - (box[0] + box[1]) / 2;
    const dx = (ex.x0 + ex.x1) / 2 - placeX;
    const half = c.dist * Math.tan(cam.fov * RAD / 2);
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(cam.quaternion), right = new THREE.Vector3(1, 0, 0).applyQuaternion(cam.quaternion);
    const T = aimOf(c).addScaledVector(up, dy * half).addScaledVector(right, dx * half * aspect);
    c.tx = T.x; c.ty = T.y; c.tz = T.z;
    if (Math.abs(s - 1) < 0.002 && Math.abs(dx) < 0.002 && Math.abs(dy) < 0.002) break;
  }
  fitPitch();
  return c;
}

// ---------------------------------------------------------------- targets
// A target gives world points for a slice of itself (by rest height), its landmarks and the way it faces.
const BUNNY_PARTS = [['bunny', 'Bunny'], ['face', 'Face'], ['hands', 'Hands'], ['feet', 'Feet']];
const SKULL = 1, EYES = 2, HANDS = 4, FEET = 8;

function bunnyModel(view) {
  const rig = new BunnyRig(view.data);
  rig.pose({});
  const objs = view.objects, oi = [], vi = [], rz = [], tag = [];
  const rest = objs.map(o => rig.deform(o.m));
  const zOf = (name, f) => { const k = objs.findIndex(o => o.m.name === name); let z = f === 'max' ? -Infinity : Infinity; for (let i = 2; i < rest[k].length; i += 3) z = Math[f](z, rest[k][i]); return z; };
  let floor = Infinity, top = -Infinity, skullTop = -Infinity, skullBot = Infinity, eyeZ = 0, eyeN = 0;
  const legTop = zOf('BUNNY_leg.L', 'max');
  objs.forEach((o, k) => {
    const R = rest[k], n = R.length / 3, mask = o.g.getAttribute('faceMask')?.array;
    const hand = /hand|cuff/.test(o.m.name), leg = /leg/.test(o.m.name);
    const step = o.m.name === 'BUNNY_head' ? 2 : 3;
    for (let v = 0; v < n; v++) {
      const x = R[3 * v], y = R[3 * v + 1], z = R[3 * v + 2];
      let t = 0;
      if (mask && mask[v] > 0.5) {
        t |= SKULL; skullTop = Math.max(skullTop, z); skullBot = Math.min(skullBot, z);
        if (y < -0.05 && Math.abs(x) < 0.23 && z > 0.45 && z < 0.58) { t |= EYES; eyeZ += z; eyeN++; }
      }
      if (hand) t |= HANDS;
      if (leg && z < legTop * 0.55) t |= FEET;
      if (!t && v % step) continue;
      oi.push(k); vi.push(v); rz.push(z); tag.push(t);
      floor = Math.min(floor, z); top = Math.max(top, z);
    }
  });
  const marks = { floor, ground: floor + 0.04, legMid: (floor + legTop) / 2, waist: zOf('BUNNY_pelvis', 'max'), chest: zOf('BUNNY_shirt', 'max') - 0.04,
    shoulder: zOf('BUNNY_sleeve_up.L', 'max'), chin: skullBot, eyes: eyeZ / Math.max(1, eyeN), skullTop, top };
  const world = i => { const b = objs[oi[i]].buf, v = vi[i]; return new THREE.Vector3(b[3 * v], b[3 * v + 1], b[3 * v + 2]); };
  const pick = (test) => { const out = []; for (let i = 0; i < oi.length; i++) if (test(rz[i], tag[i])) out.push(world(i)); return out; };
  return { marks, pick };
}

function makeBunnyTarget(view, ctx, part) {
  const B = (view.__camPresetsBunny ||= bunnyModel(view));
  const m = B.marks;
  const vals = () => ({ turn: ctx.current('turn'), s: ctx.current('s') || 1 });
  // landmarks in world height follow his scale and placement: measure from posed points
  const partPts = { face: (z, t) => t & SKULL, hands: (z, t) => t & HANDS, feet: (z, t) => t & FEET }[part];
  const worldZ = name => {
    if (partPts && name !== 'ground') {   // a part's own eye level is its centre; lower angles go below it
      const b = new THREE.Box3().setFromPoints(B.pick(partPts)), c = b.getCenter(new THREE.Vector3()).z, h = b.max.z - b.min.z;
      const lift = part === 'feet' ? 0.08 * vals().s : 0;   // look a little down onto the feet
      return Math.max(floorZ() + 0.04, c + lift - h * ({ shoulder: 0.15, waist: 0.4, legMid: 0.7 }[name] || 0));
    }
    if (name === 'ground') return Math.min(...B.pick((z, t) => t & FEET).map(p => p.z)) + 0.04 * vals().s;
    const band = B.pick(z => Math.abs(z - m[name]) < 0.03);
    return band.length ? band.reduce((a, p) => a + p.z, 0) / band.length : m[name];
  };
  function floorZ() { return Math.min(view.data.floor_z || 0, ...B.pick((z, t) => t & FEET).map(p => p.z)); }
  return {
    id: part, label: BUNNY_PARTS.find(p => p[0] === part)[1], facing: () => vals().turn, worldZ, floorZ,
    eyePoint: () => {   // between the eyes, on the front of the face
      const e = B.pick((z, t) => t & EYES), t = vals().turn * RAD, f = new THREE.Vector3(Math.sin(t), -Math.cos(t), 0);
      const c = e.reduce((a, p) => a.add(p), new THREE.Vector3()).divideScalar(e.length);
      return c.addScaledVector(f, Math.max(...e.map(p => p.clone().sub(c).dot(f))));
    },
    region(size) {
      const skull = B.pick((z, t) => t & SKULL), eyes = B.pick((z, t) => t & EYES);
      if (part === 'face' && size === 'cu') return { points: skull, xPoints: eyes, box: [-1.05, 1.05], xBox: [-1.15, 1.15] };
      if (part === 'face' && size === 'ecu') return { points: eyes, xPoints: eyes, box: [-0.35, 0.35], xBox: [-1.5, 1.5] };
      // feet sit under the hoodie hem, so keep them smaller in frame with floor around them
      if (part !== 'bunny') return fillRegion(B.pick(partPts), SIZES.find(s => s[0] === size)[3] / (part === 'feet' ? 4.5 : 2.6));
      // Bunny's head is wider than a 9:16 frame at medium sizes, so the head's sides may crop a little more each size up
      switch (size) {
        case 'ews': return { points: B.pick(() => true), box: [-0.6, -0.48] };
        case 'ws': return { points: B.pick(() => true), box: [-0.62, 0.02] };
        case 'fs': return { points: B.pick(() => true), xPoints: B.pick(() => true), box: [-0.86, 0.86], xBox: [-0.9, 0.9] };
        case 'mfs': return { points: B.pick(z => z >= m.legMid), xPoints: skull, box: [-1, 0.86], xBox: [-1, 1], anchor: 'top' };
        case 'ms': return { points: B.pick(z => z >= m.waist), xPoints: skull, box: [-1, 0.86], xBox: [-1.08, 1.08], anchor: 'top' };
        case 'mcu': return { points: B.pick(z => z >= m.chest && z <= m.skullTop), xPoints: skull, box: [-1, 0.74], xBox: [-1.18, 1.18], anchor: 'top' };
        case 'cu': return { points: skull, xPoints: eyes, box: [-1.05, 1.05], xBox: [-1.15, 1.15] };
        case 'ecu': return { points: eyes, xPoints: eyes, box: [-0.35, 0.35], xBox: [-1.5, 1.5] };
      }
    },
  };
}

// A generic object: `fill` of the frame on its longest screen side
function fillRegion(points, fill) {
  return { points, xPoints: points, box: [-fill, fill].map(v => v * 0.9), xBox: [-fill, fill].map(v => v * 0.9) };
}

// Props and other characters register here: { id, label, points(): Vector3[], facing(): deg }
const extraTargets = new Map();
export function registerCameraTarget(t) { extraTargets.set(t.id, t); }
function makeObjectTarget(t, view) {
  const zs = () => { const b = new THREE.Box3().setFromPoints(t.points()); return [b.min.z, b.max.z]; };
  return {
    id: t.id, label: t.label, facing: () => (t.facing ? t.facing() : 0), floorZ: () => view.data.floor_z || 0,
    worldZ: name => { const [z0, z1] = zs(); return z0 + (z1 - z0) * ({ ground: 0.05, legMid: 0.15, waist: 0.4, shoulder: 0.7, eyes: 0.85 }[name] ?? 0.5); },
    eyePoint: () => new THREE.Box3().setFromPoints(t.points()).getCenter(new THREE.Vector3()),
    region: size => fillRegion(t.points(), { ews: 0.05, ws: 0.18, fs: 0.75, mfs: 0.9, ms: 1, mcu: 1.3, cu: 1.7, ecu: 3 }[size]),
  };
}

// ---------------------------------------------------------------- state and apply
const state = { target: 'bunny', size: 'ms', angle: 'eye', place: 'center', seconds: {} };
let ctx = null;

function target(id = state.target) {
  if (extraTargets.has(id)) return makeObjectTarget(extraTargets.get(id), ctx.view);
  return makeBunnyTarget(ctx.view, ctx, BUNNY_PARTS.some(p => p[0] === id) ? id : 'bunny');
}
const camNow = () => Object.fromEntries(CAM_KEYS.map(k => [k, ctx.current('cam.' + k)]));
const camAt = f => Object.fromEntries(CAM_KEYS.map(k => [k, valueAt(ctx.project(), 'cam.' + k, f)]));

// The still framing for (target, size, angle, placement), from a starting camera
function framing({ size = state.size, angle = state.angle, place = state.place, tgt = target(), from = camNow() } = {}) {
  const A = (ANGLES.find(a => a[0] === angle) || ANGLES[0])[3];
  const base = { ...from, yaw: wrapYaw(tgt.facing() + (A.yaw || 0)), roll: A.roll || 0, lens: A.lens || from.lens, pitch: A.pitch ?? 2 };
  if (A.height) base.pitch = 0;
  const reg = { ...tgt.region(size), placeX: (PLACES.find(p => p[0] === place) || PLACES[0])[2] };
  return solve(base, reg, ctx.view.aspect, { heightZ: A.height ? tgt.worldZ(A.height) : null, floorZ: tgt.floorZ() });
}

function viewCam(id, tgt = target()) {
  const E = tgt.eyePoint(), t = tgt.facing() * RAD;
  const f = new THREE.Vector3(Math.sin(t), -Math.cos(t), 0), r = new THREE.Vector3(-Math.cos(t), -Math.sin(t), 0), up = new THREE.Vector3(0, 0, 1);
  const base = { ...camNow(), roll: 0 };
  if (id === 'pov') return lookFrom(E.clone().addScaledVector(f, 0.15), E.clone().addScaledVector(f, 1.6), { ...base, lens: 24 });
  // behind and beside him, far enough back that his big head sits in the foreground third, not across the lens
  const side = id === 'ots-r' ? -1 : 1, low = id === 'oth';
  const P = E.clone().addScaledVector(f, low ? -1.3 : -1.35).addScaledVector(r, side * (low ? 0.42 : 0.36)).addScaledVector(up, low ? -0.3 : 0.12);
  return lookFrom(P, E.clone().addScaledVector(f, 1.5).addScaledVector(r, -side * 0.25).addScaledVector(up, low ? -0.2 : -0.1), { ...base, lens: low ? 28 : 35 });
}

function writeStill(c) {
  ctx.pushUndo();
  for (const k of CAM_KEYS) ctx.setValue('cam.' + k, k === 'yaw' ? wrapYaw(c[k]) : c[k]);
  ctx.refresh();
}

// keys: [{f, cam, ease}] — clears camera keys strictly inside the move first
function writeKeys(keys) {
  const p = ctx.project(), f0 = keys[0].f, f1 = keys[keys.length - 1].f;
  ctx.pushUndo();
  for (const k of CAM_KEYS) { const t = p.tracks['cam.' + k]; if (t) p.tracks['cam.' + k] = t.filter(q => q.f <= f0 || q.f >= f1); }
  if (f1 >= p.length) p.length = f1 + 1;
  for (const { f, cam, ease } of keys) for (const k of CAM_KEYS) setKey(p, 'cam.' + k, f, cam[k], ease || 'ease');
  ctx.refresh();
}

function rnd(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296 - 0.5; }; }
// smooth noise: random values every `step` frames, cosine-blended
function noise(seed, step) { const r = rnd(seed), pts = []; return f => { const i = Math.floor(f / step); while (pts.length <= i + 1) pts.push(r()); const t = (1 - Math.cos((f / step - i) * Math.PI)) / 2; return pts[i] * (1 - t) + pts[i + 1] * t; }; }

function rootAt(f) {
  const p = ctx.project(), S = ctx.view.data.S, val = id => valueAt(p, id, f);
  const M = new THREE.Matrix4().makeTranslation(val('bodyX') / STAGE_BODY_UNIT * S, val('depth') * S, -val('bodyY') / STAGE_BODY_UNIT * S);
  return M.multiply(new THREE.Matrix4().makeRotationZ(val('turn') * RAD).multiply(new THREE.Matrix4().makeScale(val('s') || 1, val('s') || 1, val('s') || 1)));
}

function moveKeys(id, f0, n) {
  const c0 = camAt(f0), f1 = f0 + n, tgt = target();
  const k2 = (a, b, ease = 'ease') => [{ f: f0, cam: a, ease }, { f: f1, cam: b }];
  const with_ = (c, o) => ({ ...c, ...o });
  const P0 = posOf(c0), T0 = aimOf(c0);
  const turnTo = (c, dyaw, dpitch) => { const P = posOf(c), d = dirOf(c.yaw + dyaw, c.pitch + dpitch); return { ...c, yaw: c.yaw + dyaw, pitch: c.pitch + dpitch, tx: P.x - d.x * c.dist, ty: P.y - d.y * c.dist, tz: P.z - d.z * c.dist }; };
  const slide = (c, v) => ({ ...c, tx: c.tx + v.x, ty: c.ty + v.y, tz: c.tz + v.z });
  const right = new THREE.Vector3(Math.cos(c0.yaw * RAD), Math.sin(c0.yaw * RAD), 0);
  const sizeStep = d => { const i = SIZES.findIndex(s => s[0] === state.size); return SIZES[Math.max(0, Math.min(SIZES.length - 1, i + d))][0]; };
  const frameFrom = (size, extra = {}) => framing({ size, from: c0, ...extra });
  // distance factor that takes the current framing `steps` sizes tighter (negative: wider), keeping this camera's direction
  const stepDist = steps => c0.dist * frameFrom(sizeStep(steps)).dist / framing({ from: c0 }).dist;
  // dolly zoom keeps the size at the front of the target (the face), not at the aim point behind it
  // dolly zoom: the lens eases to L while the distance is solved every few frames so the target's
  // projected height never changes (the room alone stretches or squeezes)
  const vertigo = L => {
    const pts = tgt.region('fs').points, cam = new THREE.PerspectiveCamera(), v = new THREE.Vector3();
    const height = c => { makeCam(c, ctx.view.aspect, cam); let y0 = Infinity, y1 = -Infinity; for (const p of pts) { v.copy(p).project(cam); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y); } return y1 - y0; };
    const want = height(c0), ease = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    return bake(3, f => {
      const c = with_(c0, { lens: c0.lens + (L - c0.lens) * ease((f - f0) / n) });
      c.dist = c0.dist * c.lens / c0.lens;
      for (let i = 0; i < 6; i++) c.dist = Math.max(0.12, c.dist * height(c) / want);
      return c;
    });
  };
  const seq = (cams, eases) => cams.map((cam, i) => ({ f: Math.round(f0 + n * i / (cams.length - 1)), cam, ease: eases ? eases[Math.min(i, eases.length - 1)] : 'ease' }));
  const bake = (step, fn) => { const out = []; for (let f = f0; f < f1; f += step) out.push({ f, cam: fn(f), ease: 'linear' }); out.push({ f: f1, cam: fn(f1), ease: 'linear' }); return out; };
  switch (id) {
    case 'hold': return k2(c0, c0, 'hold');
    case 'push-in': return k2(c0, with_(c0, { dist: stepDist(1) }));
    case 'pull-out': return k2(c0, with_(c0, { dist: stepDist(-1) }));
    case 'push-cu': return k2(c0, frameFrom('cu', { angle: state.angle }));
    case 'pull-reveal': return k2(c0, frameFrom('ws'));
    case 'crash-push': return k2(c0, with_(c0, { dist: stepDist(2) }));
    case 'zoom-in': return k2(c0, with_(c0, { lens: Math.min(200, c0.lens * 1.8) }));
    case 'zoom-out': return k2(c0, with_(c0, { lens: Math.max(12, c0.lens / 1.8) }));
    case 'snap-zoom': return k2(c0, with_(c0, { lens: Math.min(200, c0.lens * 2.2) }));
    case 'vertigo-in': return vertigo(Math.max(12, c0.lens / 2.5));
    case 'vertigo-out': return vertigo(Math.min(200, c0.lens * 2.5));
    case 'pan-l': return k2(c0, turnTo(c0, 25, 0));
    case 'pan-r': return k2(c0, turnTo(c0, -25, 0));
    case 'tilt-up': return k2(c0, turnTo(c0, 0, -15));
    case 'tilt-down': return k2(c0, turnTo(c0, 0, 15));
    case 'tilt-reveal': { const F = new THREE.Box3().setFromPoints(target('feet').region('fs').points).getCenter(new THREE.Vector3()); return k2(lookFrom(P0, F, c0), c0); }
    case 'whip-in-l': return k2(turnTo(c0, 75, 0), c0);
    case 'whip-in-r': return k2(turnTo(c0, -75, 0), c0);
    case 'whip-out': return k2(c0, turnTo(c0, -75, 0));
    case 'whip-tilt': return k2(turnTo(c0, 0, -55), c0);
    case 'truck-l': return k2(c0, slide(c0, right.clone().multiplyScalar(-0.35 * c0.dist)));
    case 'truck-r': return k2(c0, slide(c0, right.clone().multiplyScalar(0.35 * c0.dist)));
    case 'ped-up': return k2(c0, slide(c0, new THREE.Vector3(0, 0, 0.25 * c0.dist)));
    case 'ped-down': { const P = posOf(c0), floor = tgt.floorZ() + 0.04; const dz = Math.max(-0.25 * c0.dist, floor - P.z); return k2(c0, slide(c0, new THREE.Vector3(0, 0, Math.min(0, dz)))); }
    case 'crane-up': return k2(c0, with_(c0, { pitch: Math.min(80, c0.pitch + 35), dist: c0.dist * 1.3 }));
    case 'crane-down': return k2(with_(c0, { pitch: Math.min(80, c0.pitch + 40), dist: c0.dist * 1.4 }), c0);
    case 'boom-over': return k2(c0, with_(c0, { pitch: 88 }));
    case 'drone-reveal': return k2(c0, with_(c0, { pitch: 50, dist: c0.dist * 4.5, yaw: c0.yaw + 25 }));
    case 'drone-land': return k2(with_(c0, { pitch: 50, dist: c0.dist * 4.5, yaw: c0.yaw - 25 }), c0);
    case 'arc-l': return k2(c0, with_(c0, { yaw: c0.yaw - 90 }));
    case 'arc-r': return k2(c0, with_(c0, { yaw: c0.yaw + 90 }));
    case 'orbit': return seq([0, 1, 2, 3, 4].map(i => with_(c0, { yaw: c0.yaw + 90 * i })), ['in', 'linear', 'linear', 'out']);
    case 'spiral': return k2(c0, with_(c0, { yaw: c0.yaw + 120, dist: stepDist(2) }));
    case 'dutch-roll': return k2(c0, with_(c0, { roll: c0.roll + 15 }));
    case 'barrel': return k2(c0, with_(c0, { roll: c0.roll + 360 }));
    case 'follow': case 'snorricam': {
      const M0inv = rootAt(f0).invert(), turn0 = valueAt(ctx.project(), 'turn', f0);
      return bake(id === 'follow' ? 2 : 1, f => {
        const M = rootAt(f).multiply(M0inv);
        if (id === 'follow') { const T = T0.clone().applyMatrix4(M); return slide(c0, T.sub(T0)); }
        return lookFrom(P0.clone().applyMatrix4(M), T0.clone().applyMatrix4(M), c0);
      });
    }
    case 'handheld': case 'steadicam': case 'impact': case 'quake': {
      const [amp, step, every, creep] = { handheld: [0.7, 9, 3, 1], steadicam: [1.4, 40, 10, 0.9], impact: [2.2, 2, 1, 1], quake: [3, 3, 1, 1] }[id];
      const nY = noise(f0 * 7 + 1, step), nP = noise(f0 * 7 + 2, step), nR = noise(f0 * 7 + 3, step);
      const fade = id === 'impact' ? f => Math.pow(1 - (f - f0) / n, 2) : f => Math.min(1, (f - f0) / Math.max(1, n * 0.08), (f1 - f) / Math.max(1, n * 0.08));
      const keys = bake(every, f => { const a = amp * fade(f); return with_(turnTo(c0, nY(f) * 2 * a, nP(f) * 1.4 * a), { roll: c0.roll + nR(f) * 1.6 * a, dist: c0.dist * (1 + (creep - 1) * (f - f0) / n) }); });
      if (id === 'steadicam') keys.forEach(k => { k.ease = 'ease'; });
      return keys;
    }
    case 'dread': return k2(c0, with_(c0, { dist: stepDist(2) }));
    case 'scale-reveal': return k2(c0, with_(frameFrom('ews', { angle: 'high' }), { lens: Math.max(12, c0.lens * 0.7) }));
    case 'hero': {
      const a = framing({ size: 'ws', angle: 'low', from: c0 }), b = framing({ size: 'ms', angle: 'low', from: c0 });
      return k2(a, b);
    }
  }
  throw Error('Unknown camera move ' + id);
}

// One entry point for the panel and the MCP tool
export function applyCameraPreset(o = {}) {
  if (!ctx) throw Error('Camera presets are not ready yet');
  if (o.target) {
    if (!BUNNY_PARTS.some(p => p[0] === o.target) && !extraTargets.has(o.target)) throw Error('Unknown target ' + o.target + '. Targets: ' + targetList().map(t => t[0]).join(', '));
    state.target = o.target;
  }
  if (o.placement) state.place = o.placement;
  const done = [];
  if (o.view) {
    if (!VIEWS.some(v => v[0] === o.view)) throw Error('Unknown view ' + o.view);
    writeStill(viewCam(o.view)); done.push(o.view);
  } else if (o.size || o.angle || o.placement) {
    if (o.size) { if (!SIZES.some(s => s[0] === o.size)) throw Error('Unknown size ' + o.size); state.size = o.size; }
    if (o.angle) { if (!ANGLES.some(a => a[0] === o.angle)) throw Error('Unknown angle ' + o.angle); state.angle = o.angle; }
    writeStill(framing()); done.push(state.size, state.angle);
  }
  if (o.move) {
    const M = MOVES.find(m => m[0] === o.move);
    if (!M) throw Error('Unknown move ' + o.move);
    const secs = o.seconds ?? state.seconds[o.move] ?? M[3];
    const f0 = o.frame ?? ctx.frame(), n = Math.max(2, Math.round(secs * ctx.project().fps));
    writeKeys(moveKeys(o.move, f0, n)); done.push(`${o.move} ${f0}–${f0 + n}`);
  }
  return { applied: done, target: state.target, size: state.size, angle: state.angle, placement: state.place, camera: camNow() };
}

function targetList() { return [...BUNNY_PARTS, ...[...extraTargets.values()].map(t => [t.id, t.label])]; }

export function bindCameraPresets(c) {
  ctx = c;
  window.ds3dCameraPresets = {
    apply: applyCameraPreset,
    list: () => ({ targets: targetList(), sizes: SIZES.map(s => [s[0], s[1]]), angles: ANGLES.map(a => [a[0], a[1]]), views: VIEWS.map(v => [v[0], v[1]]), placements: PLACES.map(p => [p[0], p[1]]), moves: MOVES.map(m => [m[0], m[1], m[3]]) }),
    register: registerCameraTarget,
  };
}

// ---------------------------------------------------------------- panel (Camera tab)
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) { if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (v != null && v !== false) e.setAttribute(k, v); }
  for (const k of kids.flat()) if (k != null) e.append(k);
  return e;
};

export function cameraPresetsPanel(c) {
  bindCameraPresets(c);
  const box = el('div', { class: 'camera-presets' });
  const draw = () => {
    const run = o => { try { applyCameraPreset(o); } catch (e) { ctx.toast(e.message); } draw(); };
    const chip = (on, title, label, o) => el('button', { 'aria-pressed': String(on), title, onclick: () => run(o) }, label);
    const secs = el('input', { type: 'number', min: 0.1, max: 60, step: 0.1, value: state.seconds._ ?? '', placeholder: 'auto', style: 'width:64px', title: 'How long a move takes, in seconds. Leave empty for each move\'s own default.', 'aria-label': 'Move length in seconds' });
    secs.addEventListener('change', () => { state.seconds._ = secs.value === '' ? undefined : Number(secs.value); });
    const groups = [...new Set(MOVES.map(m => m[4]))];
    box.replaceChildren(
      el('h3', {}, 'Shot presets'),
      el('p', { class: 'hint' }, 'Pick what to frame, then click a size or angle: the camera frames it at the playhead.'),
      el('div', { class: 'chips', role: 'group', 'aria-label': 'Frame on' }, ...targetList().map(([id, name]) => chip(state.target === id, 'Frame on ' + name, name, { target: id }))),
      el('h3', {}, 'Size'),
      el('div', { class: 'chips' }, ...SIZES.map(([id, name, tip]) => chip(state.size === id, tip, name, { size: id }))),
      el('h3', {}, 'Angle'),
      el('div', { class: 'chips' }, ...ANGLES.map(([id, name, tip]) => chip(state.angle === id, tip, name, { angle: id }))),
      el('h3', {}, 'Placement'),
      el('div', { class: 'chips' }, ...PLACES.map(([id, name]) => chip(state.place === id, 'Where the target sits across the frame', name, { placement: id })),
        ...VIEWS.map(([id, name, tip]) => chip(false, tip, name, { view: id }))),
      el('h3', {}, 'Camera moves'),
      el('div', { class: 'row' }, el('label', {}, 'Length (s)'), secs, el('span', { class: 'hint', style: 'margin:0' }, 'Moves start at the playhead and are eased.')),
      ...groups.flatMap(g => [el('div', { class: 'hint', style: 'margin:8px 0 3px;font-weight:800' }, g),
        el('div', { class: 'chips' }, ...MOVES.filter(m => m[4] === g).map(([id, name, tip, s]) => el('button', { title: `${tip} (${s} s)`, onclick: () => run({ move: id, seconds: state.seconds._ }) }, name)))]),
    );
  };
  draw();
  return box;
}
