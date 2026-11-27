// Ripple delete: cut frames [f0, f1) out of one shot so everything after the cut slides left
// and the gap closes, the way an editor's ripple delete works. The scene voice is cut by the
// caller (main.js); this moves everything that is timed against it, so lip sync, captions and
// Babble lines stay on the words:
//   keys (the shot, its animation layers and its co-stars), markers, placed items, drawings,
//   cut-ins and camera cuts, Babble lines, captions and headlines of this shot, and the
//   transcript's words (scene seconds). The shot gets shorter by the cut, so later shots start
//   earlier by the same amount and stay in sync with the voice too.
// A pose that was held across the cut stays as it was after the cut: if keys inside the cut
// are removed, the value at f1 is keyed at f0.
import { valueAt, DISCRETE } from './project.js';

// keys of one track list; returns the new list
function cutKeys(keys, id, f0, f1) {
  if (!keys?.length) return keys;
  const n = f1 - f0, hadInside = keys.some(k => k.f >= f0 && k.f < f1);
  const after = hadInside && !keys.some(k => k.f === f1) && keys.some(k => k.f > f1) ? valueAt({ tracks: { [id]: keys } }, id, f1) : null;
  const before = hadInside && !keys.some(k => k.f > f1) && !keys.some(k => k.f === f1) ? valueAt({ tracks: { [id]: keys } }, id, f1) : null;
  const out = keys.filter(k => k.f < f0 || k.f >= f1).map(k => (k.f >= f1 ? { ...k, f: k.f - n } : k));
  const hold = after ?? before;
  if (hold != null && !out.some(k => k.f === f0)) {
    const ease = DISCRETE.has(id) ? 'hold' : keys.find(k => k.f >= f0 && k.f < f1)?.ease || 'ease';
    out.push({ f: f0, v: hold, ease });
    out.sort((a, b) => a.f - b.f);
  }
  return out;
}
const cutTracks = (tracks, f0, f1) => { if (tracks) for (const id of Object.keys(tracks)) tracks[id] = cutKeys(tracks[id], id, f0, f1); };
// a frame number: inside the cut goes to the cut point, after it slides left
const shift = (f, f0, f1) => (f == null ? f : f >= f1 ? f - (f1 - f0) : f >= f0 ? f0 : f);
// a span [a, b): the part inside the cut is removed; null when nothing is left
function span(a, b, f0, f1) {
  const A = shift(a, f0, f1), B = shift(b, f0, f1);
  return B > A ? [A, B] : null;
}

export function rippleShot(scene, index, from, to) {
  const shot = scene.shots[index];
  if (!shot) throw Error('No shot ' + index);
  const f0 = Math.max(0, Math.round(Math.min(from, to))), f1 = Math.min(shot.length, Math.round(Math.max(from, to)));
  const n = f1 - f0;
  if (n <= 0) throw Error('Select part of the voice first: drag across the Voice row');
  if (n >= shot.length) throw Error('That would remove the whole shot. Delete the shot instead (Shot menu).');
  const start = scene.shots.slice(0, index).reduce((s, x) => s + x.length, 0);

  cutTracks(shot.tracks, f0, f1);
  for (const L of shot.layers || []) cutTracks(L.tracks, f0, f1);
  for (const c of shot.costars || []) cutTracks(c.tracks, f0, f1);
  if (shot.markers) shot.markers = shot.markers.filter(m => m.f < f0 || m.f >= f1).map(m => ({ ...m, f: shift(m.f, f0, f1) }));
  for (const it of shot.items || []) it.frame = shift(it.frame || 0, f0, f1);
  for (const d of shot.drawings || []) { d.frame = shift(d.frame || 0, f0, f1); if (d.until != null) d.until = Math.max(d.frame + 1, shift(d.until, f0, f1)); }
  if (shot.cuts) shot.cuts = shot.cuts.map(c => { const s = span(c.frame, c.frame + c.length, f0, f1); return s && { ...c, frame: s[0], length: s[1] - s[0] }; }).filter(Boolean);
  if (shot.camCuts) shot.camCuts = [...new Set(shot.camCuts.filter(f => f < f0 || f >= f1).map(f => shift(f, f0, f1)))].filter(f => f > 0);
  shot.length -= n;

  // scene-level things timed inside this shot
  if (scene.babble) scene.babble = scene.babble.filter(l => l.shot !== shot.uid || l.f < f0 || l.f >= f1).map(l => (l.shot === shot.uid ? { ...l, f: shift(l.f, f0, f1) } : l));
  const spans = list => list.map(c => { if (c.shot !== shot.uid) return c; const s = span(c.f, c.to ?? c.f + 1, f0, f1); return s && { ...c, f: s[0], ...(c.to != null ? { to: s[1] } : {}) }; }).filter(Boolean);
  if (scene.captions?.tracks) for (const k of Object.keys(scene.captions.tracks)) scene.captions.tracks[k] = spans(scene.captions.tracks[k] || []);
  if (scene.headlines) scene.headlines = spans(scene.headlines);
  if (scene.transcript?.words) {
    const t0 = (start + f0) / scene.fps, t1 = (start + f1) / scene.fps, d = t1 - t0;
    scene.transcript = { ...scene.transcript, words: scene.transcript.words.filter(w => w.t1 <= t0 || w.t0 >= t1).map(w => (w.t0 >= t1 ? { ...w, t0: +(w.t0 - d).toFixed(3), t1: +(w.t1 - d).toFixed(3) } : w)) };
    scene.transcript.text = scene.transcript.words.map(w => w.text).join(' ').replace(/\s+([,.!?])/g, '$1').trim();
  }
  return { shot: shot.code, from: f0, to: f1, frames: n, seconds: +(n / scene.fps).toFixed(2), length: shot.length, sceneFrom: start + f0, sceneTo: start + f1 };
}

// audio samples: remove [t0, t1) seconds (ripple) or silence it (lift), with a 5 ms fade at
// each join so the cut never clicks
export function cutSamples(channels, sr, t0, t1, ripple = true) {
  const a = Math.max(0, Math.round(t0 * sr)), len = channels[0].length, b = Math.min(len, Math.round(t1 * sr));
  if (b <= a) return channels;
  const fade = Math.round(sr * 0.005);
  return channels.map(ch => {
    let out;
    if (ripple) { out = new Float32Array(len - (b - a)); out.set(ch.subarray(0, a), 0); out.set(ch.subarray(b), a); }
    else { out = Float32Array.from(ch); out.fill(0, a, b); }
    const join = a;   // ripple: the join is at a; lift: both edges of the silence
    for (let i = 0; i < fade; i++) {
      const g = i / fade;
      if (join - 1 - i >= 0) out[join - 1 - i] *= g;
      const j = ripple ? join + i : b + i;
      if (j < out.length) out[j] *= g;
    }
    return out;
  });
}
