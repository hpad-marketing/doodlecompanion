// Storytime helpers: hook and retention check, YouTube chapters from markers,
// loop-back ending for Reels, and the story bible with its running-gag tracker.
import { valueAt, setKey } from './project.js';

// ---------------------------------------------------------------- hook and retention check
// "Visual change" per frame: how far the pose, face and camera moved, plus cuts and
// library items landing. A weak first 2 s or 4+ s with nothing changing gets flagged.
const WEIGHT = id => (id.startsWith('cam.') ? (/dist|tx|ty|tz/.test(id) ? 40 : /focus|fstop/.test(id) ? 0 : 1) : /^(expression|gaze|mouth|blink)$/.test(id) ? 0 : 1);
export function retention(scene) {
  const fps = scene.fps, change = [];
  for (const [si, s] of scene.shots.entries()) {
    const ids = Object.keys(s.tracks);
    for (let f = 0; f < s.length; f++) {
      let c = 0;
      if (f > 0) for (const id of ids) c += Math.abs(valueAt(s, id, f) - valueAt(s, id, f - 1)) * WEIGHT(id);
      if (f > 0) for (const id of ['expression', 'gaze', 'mouth']) if (s.tracks[id] && valueAt(s, id, f) !== valueAt(s, id, f - 1)) c += 4;
      if (f === 0 && si > 0) c += 20;                                          // a cut
      if ((s.items || []).some(it => it.frame === f)) c += 10;                 // something new appears
      change.push(c);
    }
  }
  const quiet = c => c < 0.6;   // degrees-ish per frame: a held pose with boil and blinks only
  const hook = change.slice(0, 2 * fps);
  const hookScore = hook.reduce((a, b) => a + b, 0) / Math.max(1, hook.length);
  const lulls = [];
  let start = null;
  change.forEach((c, f) => {
    if (quiet(c)) { if (start == null) start = f; }
    else { if (start != null && f - start >= 4 * fps) lulls.push([start, f]); start = null; }
  });
  if (start != null && change.length - start >= 4 * fps) lulls.push([start, change.length]);
  const where = f => { let n = f; for (const s of scene.shots) { if (n < s.length) return `${s.code} F${n}`; n -= s.length; } return 'end'; };
  return {
    hook: hookScore >= 2 ? 'strong' : hookScore >= 0.8 ? 'ok' : 'weak',
    hookScore: +hookScore.toFixed(2),
    lulls: lulls.map(([a, b]) => ({ from: where(a), to: where(b - 1), seconds: +((b - a) / fps).toFixed(1), at: +(a / fps).toFixed(1) })),
  };
}

// ---------------------------------------------------------------- YouTube chapters from markers
// Markers whose note starts with "Chapter:" (or "#") become chapters; the first one is 0:00.
export function chapters(scene) {
  const out = [];
  let t0 = 0;
  for (const s of scene.shots) {
    for (const m of s.markers || []) {
      const mm = /^\s*(?:chapter\s*:|#)\s*(.+)$/i.exec(m.note || '');
      if (mm) out.push({ t: (t0 + m.f) / scene.fps, title: mm[1].trim() });
    }
    t0 += s.length;
  }
  out.sort((a, b) => a.t - b.t);
  if (!out.length || out[0].t > 0) out.unshift({ t: 0, title: 'Intro' });
  const ts = t => { const s = Math.floor(t); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
  const text = out.map(c => `${ts(c.t)} ${c.title}`).join('\n');
  const problems = [];
  if (out.length < 3) problems.push('YouTube needs at least 3 chapters');
  for (let i = 1; i < out.length; i++) if (out[i].t - out[i - 1].t < 10) problems.push(`"${out[i - 1].title}" is under 10 s (YouTube's minimum)`);
  return { text, chapters: out, problems };
}

// ---------------------------------------------------------------- loop-back ending (Reels replay seamlessly)
export function loopBack(scene) {
  const first = scene.shots[0], last = scene.shots[scene.shots.length - 1], f = last.length - 1;
  const ids = new Set([...Object.keys(first.tracks), ...Object.keys(last.tracks)]);
  for (const id of ids) setKey(last, id, f, valueAt(first, id, 0), 'ease');
  return { shot: last.code, frame: f, controls: ids.size };
}

// ---------------------------------------------------------------- story bible + running gags
export function gags(scene) {
  const out = {};
  for (const s of scene.shots) for (const m of s.markers || []) {
    const g = /^\s*gag\s*:\s*(.+)$/i.exec(m.note || '');
    if (g) (out[g[1].trim().toLowerCase()] ||= []).push(`${s.code} F${m.f}`);
  }
  return Object.entries(out).map(([gag, at]) => ({ gag, count: at.length, at }));
}
export function bibleDialog(ctx) {
  const { h } = ctx, sc = ctx.scene();
  sc.bible ||= { premise: '', characters: '', rules: '' };
  const area = (key, label, tip) => {
    const t = h('textarea', { rows: 3, 'aria-label': label, placeholder: tip, style: 'width:100%;resize:vertical' });
    t.value = sc.bible[key] || '';
    t.addEventListener('change', () => { ctx.pushUndo(); sc.bible[key] = t.value; ctx.changed(); });
    return h('label', { style: 'display:block;margin:6px 0' }, h('b', {}, label), t);
  };
  const g = gags(sc);
  const close = () => box.remove();
  const box = h('div', { class: 'ds-modal', role: 'dialog', 'aria-label': 'Story bible' }, h('div', { class: 'ds-modal-card' },
    h('h3', {}, `Story bible: ${sc.name}`),
    area('premise', 'Premise', 'One line: what happens and why it is funny'),
    area('characters', 'Characters', 'Who is in it, how each one talks and moves'),
    area('rules', 'World rules and callbacks', 'Things that must stay true from video to video'),
    h('h3', {}, 'Running gags'),
    g.length ? h('div', { class: 'ds-list' }, ...g.map(x => h('div', { class: 'row' }, h('b', {}, x.gag), h('span', {}, `×${x.count}: ${x.at.join(', ')}`))))
      : h('p', { class: 'hint' }, 'Add a marker with a note like "gag: tea spill" wherever a running gag happens; they are counted here.'),
    h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: close }, 'Close'))));
  box.addEventListener('pointerdown', e => { if (e.target === box) close(); });
  document.body.append(box);
}
