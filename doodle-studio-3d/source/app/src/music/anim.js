// Music drives the animation: beat moves keyed from the notes you played (exact times, no guessing
// from audio), Bunny singing the melody (mouth keys), and live puppeteering from the controller.
import * as S from './song.js';

// scene seconds -> { shot index, frame } (null past the end)
export function shotFrameAt(scene, sec) {
  let at = 0, f = Math.round(sec * scene.fps);
  for (let i = 0; i < scene.shots.length; i++) { const L = scene.shots[i].length; if (f < at + L) return { i, f: f - at }; at += L; }
  return null;
}
export const BEAT_MOVES = {
  nod: ['Head nod', [['headNod', 9]]],
  ears: ['Ear bounce', [['earLFold', 22], ['earRFold', 22]]],
  bob: ['Body bob', [['bodyY', -10]]],
  squash: ['Squash on the hit', [['squashBody', 12]]],
  sway: ['Side sway (every other hit)', [['bodyTilt', 6]]],
  cam: ['Camera punch-in', [['cam.dist', -0.06]]],
};
// key a move on every hit of one track: up on the hit, eased back before the next hit
export function beatMoves(ctx, { track, note = null, moves = ['nod'], amount = 1, scope = 'shot', every = 1 } = {}) {
  const scene = ctx.scene(), song = scene.song, secs = ctx.sceneSeconds();
  const hits = S.hitTimes(song, track, { note, seconds: secs, loop: !song.arr.length && !song.fill ? true : false }).filter((_, i) => i % Math.max(1, every) === 0);
  if (!hits.length) throw Error('That track has no notes in the scene. Record or draw some first.');
  let keyed = 0;
  const byShot = new Map();
  for (const h of hits) { const at = shotFrameAt(scene, h.at); if (!at) continue; if (scope === 'shot' && at.i !== scene.active) continue; if (!byShot.has(at.i)) byShot.set(at.i, []); byShot.get(at.i).push(at.f); }
  for (const [i, frames] of byShot) {
    const p = ctx.shotData(i), uniq = [...new Set(frames)].sort((a, b) => a - b);
    for (const mv of moves) {
      const def = BEAT_MOVES[mv]; if (!def) throw Error('moves: ' + Object.keys(BEAT_MOVES).join(', '));
      for (const [id, size] of def[1]) {
        if (!ctx.hasControl(id)) continue;
        const base = new Map(uniq.map(f => [f, ctx.valueAt(p, id, f)]));
        uniq.forEach((f, k) => {
          const gap = (uniq[k + 1] ?? f + 12) - f, back = Math.max(2, Math.min(8, Math.floor(gap / 2)));
          const b = base.get(f), sign = mv === 'sway' ? (k % 2 ? -1 : 1) : 1;
          const peak = id === 'cam.dist' ? b * (1 + size * amount) : b + size * amount * sign;
          ctx.setKey(p, id, Math.max(0, f - 1), +b.toFixed(3), 'out');
          ctx.setKey(p, id, f, +ctx.clamp(id, peak).toFixed(3), 'ease');
          if (f + back < p.length) ctx.setKey(p, id, f + back, +b.toFixed(3), 'ease');
          keyed++;
        });
      }
    }
  }
  return { hits: hits.length, keys: keyed, shots: [...byShot.keys()].map(i => scene.shots[i].code) };
}
// Bunny sings: open mouth on each note (loud notes wide, soft ones round), rest between notes
export function sing(ctx, { track, scope = 'shot' } = {}) {
  const scene = ctx.scene(), song = scene.song, hits = S.hitTimes(song, track, { seconds: ctx.sceneSeconds() });
  if (!hits.length) throw Error('That track has no notes in the scene');
  const shapes = { loud: 2, mid: 4, soft: 5, rest: 1 };
  let keys = 0;
  for (const h of hits) {
    const a = shotFrameAt(scene, h.at), b = shotFrameAt(scene, h.at + Math.max(0.08, h.d * 0.9));
    if (!a || (scope === 'shot' && a.i !== scene.active)) continue;
    const p = ctx.shotData(a.i);
    ctx.setKey(p, 'mouth', a.f, h.v > 0.75 ? shapes.loud : h.v > 0.45 ? shapes.mid : shapes.soft, 'hold');
    if (b && b.i === a.i && b.f > a.f) ctx.setKey(p, 'mouth', b.f, shapes.rest, 'hold');
    keys++;
  }
  return { notes: hits.length, keys };
}
// live puppeteering: kind = key | face | mod | bend | pressure
export function puppet(ctx, kind, value, n) {
  const rec = ctx.puppetRecord();
  if (kind === 'key') return ctx.setControl('mouth', value > 0 ? (value > 0.75 ? 2 : value > 0.45 ? 4 : 5) : 1, { raw: true, record: rec });
  if (kind === 'face') return ctx.setControl('expression', value, { raw: true, record: rec });
  if (kind === 'mod') return ctx.setControl('headNod', 0.25 + value * 0.5, { record: rec });
  if (kind === 'bend') return ctx.setControl('headYaw', 0.3 + value * 0.4, { record: rec });
  if (kind === 'pressure') return ctx.setControl('squashBody', 0.5 + value * 0.3, { record: rec });
}
