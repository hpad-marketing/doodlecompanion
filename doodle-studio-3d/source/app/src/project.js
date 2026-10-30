// A Doodle Studio 3D shot: keyed tracks for Bunny and the camera.
// Track ids are Doodle Studio's own (armL, headYaw, ...) plus cam.* for the 3D camera,
// so a shot exports straight to the Blender bridge.

export const DISCRETE = new Set(['expression', 'gaze', 'mouth', 'blink']);
export const CAM_DEFAULT = { yaw: 0, pitch: 4, dist: 3.0, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.52 };
export const EASES = { ease: 'Ease in and out', linear: 'Linear', in: 'Ease in', out: 'Ease out', hold: 'Hold' };

const easeFn = {
  ease: t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  linear: t => t,
  in: t => t * t * t,
  out: t => 1 - Math.pow(1 - t, 3),
  hold: () => 0,
};

export function newProject(name = 'Untitled shot') {
  return { app: 'doodle-studio-3d', version: 1, name, fps: 30, length: 120, width: 1080, height: 1920, tracks: {}, audio: null, markers: [] };
}

export function defaults(id) {
  if (id.startsWith('cam.')) return CAM_DEFAULT[id.slice(4)] ?? 0;
  if (id === 's') return 1;
  return 0;
}

export function valueAt(project, id, f) {
  const keys = project.tracks[id];
  if (!keys || !keys.length) return defaults(id);
  if (f <= keys[0].f) return keys[0].v;
  const last = keys[keys.length - 1];
  if (f >= last.f) return last.v;
  let i = 1;
  while (keys[i].f < f) i++;
  const a = keys[i - 1], b = keys[i];
  if (f === b.f) return b.v;
  if (DISCRETE.has(id)) return a.v;
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

// Blender bridge shot: one entry per frame, cam block per frame
export function toBridgeShot(project, allIds) {
  const frames = [];
  for (let f = 0; f < project.length; f++) {
    const v = frameValues(project, f, allIds);
    const cam = {};
    for (const k of Object.keys(CAM_DEFAULT)) cam[k] = valueAt(project, 'cam.' + k, f);
    for (const k of Object.keys(v)) if (k.startsWith('cam.')) delete v[k];
    v.cam = cam;
    frames.push(v);
  }
  return { fps: project.fps, width: project.width, height: project.height, frames, settings: { boil_step: 3 } };
}
