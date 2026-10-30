// Idle life: auto blinks and ear twitches at natural, random intervals, layered on
// top of a shot's keyed animation. Everything comes from a seeded random stream, so
// the same shot and seed always gives the same blinks, in the viewport and in Blender.
//
// Layering rules (so the idle layer never fights the animator):
//  - a keyed blink wins: no auto blink near one, and it restarts the blink clock
//  - no blink on faces whose eyes are already closed or special (hearts, stars, laughing...)
//  - ear twitches add to the keyed ear angles, always outward (ears never close up on
//    each other), and skip any moment the keyed ear is already moving
//  - Blender's ear springs and collision solver still run on top, so a twitch gets
//    real follow-through and can never cut into the head

export const IDLE_DEFAULT = { blink: false, blinkEvery: 4, twitch: false, twitchEvery: 7, seed: 1 };
export const IDLE_RANGE = { blinkEvery: [1.5, 12], twitchEvery: [2, 30], seed: [1, 9999] };

// How each character twitches. Bunny and the Koala flick an ear outward; the Frog has
// eye bumps instead of ears, so its bump pops up and settles (scale + squash tracks).
export const CHARACTERS = {
  bunny: { label: 'Bunny', twitch: 'ears', fold: [10, 16], forward: [2, 5] },
  koala: { label: 'Koala', twitch: 'ears', fold: [7, 11], forward: [1, 3] },
  frog: { label: 'Frog', twitch: 'bumps', scale: [7, 11], squash: [-8, -5] },
};
const TRACK_DEFAULT = { earLScale: 100, earRScale: 100 };
const LIMIT = { earLFold: [-35, 35], earRFold: [-35, 35], earLForward: [-35, 35], earRForward: [-35, 35],
  earLScale: [50, 150], earRScale: [50, 150], earLSquash: [-50, 12], earRSquash: [-50, 12] };

// Faces that must not blink: their eyes are already shut, squeezed or drawn as
// something else, or the look is a fixed stare. Matched by name, so new faces with
// the same words are covered too.
const NO_BLINK = /wink|blink|laugh|sleep|dizzy|love|starry|squee|bliss|cat smile|ears over eyes|eye roll|stare|soul leaves|crying|full scream|squint|villain laugh|puppy eyes/i;

// Blink drawing states (the Blink control, faces BLINK 1/4..4/4): 0 open, 1 half,
// 2 lids nearly shut, 3 fully shut (checked in a Blender render).
const OPEN = 0, HALF = 1, NEAR = 2, CLOSED = 3;

function mulberry32(a) {
  return () => {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function hash(s) {
  let h = 2166136261;
  for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return h >>> 0;
}

export function idleOf(shot) {
  return { ...IDLE_DEFAULT, ...(shot.idle || {}) };
}
export const idleOn = shot => !!(shot.idle && (shot.idle.blink || shot.idle.twitch));

// Per-frame overrides for one shot: an array (one entry per frame) of
// { id: value } to lay over the keyed values, plus the event list for the timeline.
// valueAt(id, f) reads the shot's keyed value; faceNames maps expression -> name;
// character picks the twitch style (CHARACTERS).
export function idleLayer(shot, fps, valueAt, faceNames = [], character = 'bunny') {
  const o = idleOf(shot), n = shot.length;
  const frames = Array.from({ length: n }, () => null);
  const events = [];
  if (!o.blink && !o.twitch) return { frames, events };
  const ch = CHARACTERS[character] || CHARACTERS.bunny;
  const sec = s => Math.max(1, Math.round(s * fps));
  const put = (f, id, v) => { if (f >= 0 && f < n) (frames[f] ||= {})[id] = v; };
  const val = (id, f) => shot.tracks?.[id]?.length ? valueAt(id, f) : (TRACK_DEFAULT[id] ?? 0);

  if (o.blink) {
    // separate random streams per feature, so turning twitches on keeps the same blinks
    const rnd = mulberry32(hash(`${o.seed}|${shot.uid}|blink`));
    const keyedBlink = f => Math.round(val('blink', f)) !== OPEN;
    const blinkable = f => !NO_BLINK.test(faceNames[Math.round(val('expression', f))] || '');
    const shape = [[HALF, sec(0.03)], [CLOSED, sec(0.06)], [NEAR, sec(0.03)], [HALF, sec(0.03)]];   // ~170 ms, opening slower than closing
    const len = shape.reduce((a, [, d]) => a + d, 0);
    const guard = sec(0.5);
    // head turns: animators blink on a big turn, so a fast turn pulls the next blink in
    const head = f => val('turn', f) + val('headYaw', f);
    const quickTurn = new Set();
    for (let f = 1, was = false; f < n; f++) {
      const fast = Math.abs(head(f) - head(f - 1)) * 30 / fps > 3.5;   // > ~105 deg/s
      if (fast && !was) quickTurn.add(f);
      was = fast;
    }
    const gap = () => o.blinkEvery * (0.45 + 1.1 * rnd());
    const free = (a, b) => { for (let f = a - guard; f <= b + guard; f++) if (f >= 0 && f < n && keyedBlink(f)) return false; return true; };
    const can = (a, b) => { for (let f = a; f <= b; f++) if (f < n && !blinkable(f)) return false; return true; };
    const place = (f0, why) => {
      let f = f0;
      for (const [state, d] of shape) for (let i = 0; i < d; i++) put(f++, 'blink', state);
      events.push({ f: f0, kind: 'blink', why });
    };
    // the first one comes early, so short shots get some life too
    let next = sec(0.25 + rnd() * o.blinkEvery * 0.5), last = -1e9;
    for (let f = 0; f < n; f++) {
      if (keyedBlink(f)) { last = f; next = f + sec(gap()); continue; }
      const turn = quickTurn.has(f) && f - last > sec(0.8);
      if (f < next && !turn) continue;
      if (f + len > n || !free(f, f + len) || !can(f, f + len)) { if (!turn) next = f + sec(0.2); continue; }
      place(f, turn ? 'turn' : 'idle');
      last = f;
      f += len;
      // about one blink in seven comes as a quick double
      if (rnd() < 0.14) {
        const g = f + sec(0.12 + rnd() * 0.1);
        if (g + len <= n && free(g, g + len) && can(g, g + len)) { place(g, 'double'); f = g + len; last = g; }
      }
      next = f + sec(gap());
    }
  }

  if (o.twitch) {
    const rnd = mulberry32(hash(`${o.seed}|${shot.uid}|twitch`));
    const between = ([a, b]) => a + (b - a) * rnd();
    // flick: snap out fast, a short hold, then ease back (the springs add the wobble)
    const env = t => t < 0.06 ? t / 0.06 : t < 0.09 ? 1 : t < 0.33 ? 1 - ease((t - 0.09) / 0.24) : 0;
    const ease = t => 1 - Math.pow(1 - t, 3);
    const span = sec(0.34);
    const ids = side => ch.twitch === 'bumps' ? [`ear${side}Scale`, `ear${side}Squash`] : [`ear${side}Fold`, `ear${side}Forward`];
    const busy = (side, a, b) => {
      for (const id of ids(side)) for (let f = Math.max(1, a); f <= Math.min(n - 1, b); f++)
        if (Math.abs(val(id, f) - val(id, f - 1)) * 30 / fps > 1.5) return true;
      return false;
    };
    const flick = (side, f0, amt) => {
      const [a, b] = ids(side);
      for (let i = 0; i < span; i++) {
        const k = env(i / fps), f = f0 + i;
        if (f >= n) break;
        for (const [id, d] of [[a, amt[0]], [b, amt[1]]]) {
          const base = val(id, f);
          const [lo, hi] = LIMIT[id];
          const prev = frames[f]?.[id];
          const v = (prev ?? base) + d * k;
          put(f, id, Math.max(lo, Math.min(hi, v)));
        }
      }
    };
    let f = sec(0.4 + rnd() * Math.min(3, o.twitchEvery * 0.5));
    while (f + span < n) {
      const r = rnd();
      const sides = r < 0.4 ? ['L'] : r < 0.8 ? ['R'] : ['L', 'R'];
      const double = rnd() < 0.3;
      if (!sides.some(s => busy(s, f - 2, f + span * (double ? 2 : 1)))) {
        for (const [i, side] of sides.entries()) {
          const lag = i * sec(0.05);   // both ears never move in lockstep
          const amt = ch.twitch === 'bumps' ? [between(ch.scale), between(ch.squash)] : [-between(ch.fold), between(ch.forward) * (rnd() < 0.5 ? -1 : 1)];
          flick(side, f + lag, amt);
          if (double) flick(side, f + lag + sec(0.16), amt.map(x => x * 0.6));
        }
        events.push({ f, kind: 'twitch', sides: sides.join('') });
      }
      f += sec(o.twitchEvery * (0.5 + 1.1 * rnd()));
    }
  }
  return { frames, events };
}
