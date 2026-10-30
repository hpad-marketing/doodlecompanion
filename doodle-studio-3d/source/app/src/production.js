// Production polish: undo history, Claude's change log with per-change undo and a token
// meter, editable render presets with a time estimate, the export preflight, an overnight
// batch, the health check with one-click fixes, pack project and cache cleanup.
import * as THREE from 'three';

const modal = (ctx, title, body) => {
  const { h } = ctx;
  const close = () => box.remove();
  const box = h('div', { class: 'ds-modal', role: 'dialog', 'aria-label': title }, h('div', { class: 'ds-modal-card' }, h('h3', {}, title), ...body(close)));
  box.addEventListener('pointerdown', e => { if (e.target === box) close(); });
  document.body.append(box);
  return { box, close };
};
const when = t => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

// ---------------------------------------------------------------- undo history panel
export function historyDialog(ctx) {
  const { h } = ctx, list = ctx.history();
  const m = modal(ctx, 'Undo history', close => [
    h('p', { class: 'hint' }, 'Every change since the scene opened, newest first. Click one to go back to just before it; Redo brings the later changes back.'),
    list.length ? h('div', { class: 'ds-list' }, h('button', { disabled: true }, h('span', {}, 'Now'), h('small', {}, 'current state')),
      ...list.map((e, i) => ({ e, i })).reverse().map(({ e, i }) => h('button', { onclick: () => { ctx.jumpTo(i); close(); ctx.toast(`Back to before "${e.label}"`); } }, h('span', {}, e.label), h('small', {}, when(e.at)))))
      : h('p', { class: 'hint' }, 'Nothing to undo yet.'),
    h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: close }, 'Close'))]);
  return m;
}

// ---------------------------------------------------------------- Claude's change log + token meter
// Every MCP call that changes the scene is logged with the scene before and after it. Undoing
// one change puts back only what that change touched, and only where nothing changed it since.
const changes = [];
let pending = null;
const strip = s => { const { meter, ...rest } = s; return rest; };
const isObj = x => x && typeof x === 'object' && !Array.isArray(x);
const isUidArr = a => Array.isArray(a) && a.length > 0 && a.every(x => isObj(x) && x.uid);
function diffPaths(a, b, path = [], out = []) {
  if (JSON.stringify(a) === JSON.stringify(b)) return out;
  if (isObj(a) && isObj(b)) { for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) diffPaths(a[k], b[k], [...path, k], out); return out; }
  if ((isUidArr(a) || isUidArr(b)) && (Array.isArray(a) || a == null) && (Array.isArray(b) || b == null)) {
    const m = x => new Map((x || []).map(e => [e.uid, e])), A = m(a), B = m(b);
    for (const u of new Set([...A.keys(), ...B.keys()])) diffPaths(A.get(u), B.get(u), [...path, '#' + u], out);
    if (JSON.stringify((a || []).map(e => e.uid)) !== JSON.stringify((b || []).map(e => e.uid))) out.push([...path, '@order']);
    return out;
  }
  out.push(path);
  return out;
}
function getAt(root, path) {
  let x = root;
  for (const k of path) {
    if (x == null) return undefined;
    if (k === '@order') return Array.isArray(x) ? x.map(e => e.uid) : undefined;
    x = k[0] === '#' && Array.isArray(x) ? x.find(e => e.uid === k.slice(1)) : x[k];
  }
  return x;
}
function setAt(root, path, v) {
  const parent = getAt(root, path.slice(0, -1)), k = path[path.length - 1];
  if (parent == null || typeof parent !== 'object') return false;
  if (k === '@order') { parent.sort((p, q) => v.indexOf(p.uid) - v.indexOf(q.uid)); return true; }
  if (k[0] === '#' && Array.isArray(parent)) {
    const i = parent.findIndex(e => e.uid === k.slice(1));
    if (v === undefined) { if (i >= 0) parent.splice(i, 1); } else if (i >= 0) parent[i] = v; else parent.push(v);
    return true;
  }
  if (v === undefined) delete parent[k]; else parent[k] = v;
  return true;
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export const claude = {
  begin(ctx, tool, inChars = 0) {
    pending = { tool, at: Date.now(), before: JSON.stringify(strip(ctx.scene())), inChars };
    ctx.setLabel('Claude: ' + tool.replace(/_/g, ' '));
  },
  end(ctx, outChars = 0, failed = false) {
    if (!pending) return;
    const sc = ctx.scene(), p = pending;
    pending = null;
    ctx.setLabel(null);
    sc.meter ||= { calls: 0, inChars: 0, outChars: 0, since: new Date().toISOString() };
    sc.meter.calls++; sc.meter.inChars += p.inChars; sc.meter.outChars += outChars;
    const after = JSON.stringify(strip(sc));
    if (!failed && after !== p.before) changes.push({ tool: p.tool, at: p.at, before: p.before, after, undone: false, paths: diffPaths(JSON.parse(p.before), JSON.parse(after)).length });
  },
  list: () => changes.map((c, i) => ({ index: i, tool: c.tool, at: new Date(c.at).toISOString(), changed: c.paths, undone: c.undone })),
  revert(ctx, i) {
    const c = changes[i];
    if (!c) throw Error('No change ' + i);
    if (c.undone) throw Error('That change is already undone');
    const before = JSON.parse(c.before), after = JSON.parse(c.after), now = JSON.parse(JSON.stringify(ctx.scene()));
    const paths = diffPaths(before, after).sort((a, b) => (a.at(-1) === '@order') - (b.at(-1) === '@order'));
    let put = 0, kept = 0;
    for (const p of paths) {
      if (!same(getAt(now, p), getAt(after, p))) { kept++; continue; }   // changed again since: leave it
      const v = getAt(before, p);
      if (setAt(now, p, v === undefined ? undefined : JSON.parse(JSON.stringify(v)))) put++;
    }
    now.active = Math.max(0, Math.min(now.shots.length - 1, now.active | 0));
    ctx.pushUndo('Undo Claude: ' + c.tool.replace(/_/g, ' '));
    ctx.replaceScene(now);
    c.undone = true;
    return { tool: c.tool, restored: put, keptBecauseChangedSince: kept };
  },
  meter(sc) {
    const m = sc.meter || { calls: 0, inChars: 0, outChars: 0 };
    return { calls: m.calls, tokensIn: Math.round(m.inChars / 4), tokensOut: Math.round(m.outChars / 4), tokens: Math.round((m.inChars + m.outChars) / 4), since: m.since || null,
      note: 'Estimate from the MCP traffic of this scene (about 4 characters per token). The chat itself uses more; the full count is in Claude Code\'s usage stats.' };
  },
};
export function changeLogDialog(ctx) {
  const { h } = ctx, m = claude.meter(ctx.scene());
  return modal(ctx, 'Claude change log', close => [
    h('p', {}, h('b', {}, `Token meter: about ${m.tokens.toLocaleString()} tokens`), ` over ${m.calls} Claude call${m.calls === 1 ? '' : 's'} on this scene.`),
    h('p', { class: 'hint' }, m.note),
    changes.length ? h('div', { class: 'ds-list' }, ...claude.list().reverse().map(c => h('div', { class: 'row' },
      h('span', { style: 'flex:1' }, h('b', {}, c.tool.replace(/_/g, ' ')), ` · ${when(c.at)} · ${c.changed} change${c.changed === 1 ? '' : 's'}`),
      h('button', { disabled: c.undone, title: 'Put back what this change touched. Anything changed again since is left alone.', onclick: () => { const r = claude.revert(ctx, c.index); ctx.toast(`Undid ${r.tool}: ${r.restored} restored${r.keptBecauseChangedSince ? `, ${r.keptBecauseChangedSince} left as they are (changed since)` : ''}`, 5000); close(); changeLogDialog(ctx); } }, c.undone ? 'Undone' : 'Undo this'))))
      : h('p', { class: 'hint' }, 'Claude has not changed this scene since the app opened.'),
    h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: close }, 'Close'))]);
}

// ---------------------------------------------------------------- render presets + time estimate
const PRESETS_DEFAULT = [
  { name: 'Reel', width: 1080, height: 1920, fps: 30 },
  { name: 'Short', width: 1080, height: 1920, fps: 30 },
  { name: 'YouTube 16:9', width: 1920, height: 1080, fps: 30 },
  { name: 'Square 1:1', width: 1080, height: 1080, fps: 30 },
  { name: 'Draft', width: 540, height: 960, fps: 24 },
];
export function presets() {
  try { const p = JSON.parse(localStorage.getItem('ds3d.presets') || 'null'); if (Array.isArray(p) && p.length) return p; } catch {}
  return PRESETS_DEFAULT.map(p => ({ ...p }));
}
export function savePresets(list) {
  const clean = list.filter(p => p.name).map(p => ({ name: String(p.name).slice(0, 30), width: clamp(p.width, 64, 3840), height: clamp(p.height, 64, 3840), fps: clamp(p.fps, 12, 60) }));
  try { localStorage.setItem('ds3d.presets', JSON.stringify(clean)); } catch {}
  return clean;
}
const clamp = (v, a, b) => Math.max(a, Math.min(b, Math.round(Number(v) || a)));
export function applyPreset(ctx, name) {
  const p = presets().find(x => x.name.toLowerCase() === String(name).toLowerCase());
  if (!p) throw Error('No preset ' + name + '. Presets: ' + presets().map(x => x.name).join(', '));
  ctx.pushUndo('Preset: ' + p.name);
  const sc = ctx.scene();
  sc.width = p.width; sc.height = p.height; sc.fps = p.fps;
  ctx.changed(true);
  return p;
}
export function presetsDialog(ctx) {
  const { h } = ctx;
  let list = presets();
  const m = modal(ctx, 'Render presets', close => {
    const rows = h('div', { class: 'ds-list' });
    const draw = () => rows.replaceChildren(...list.map((p, i) => h('div', { class: 'row' },
      ...['name', 'width', 'height', 'fps'].map(k => { const inp = h('input', { type: k === 'name' ? 'text' : 'number', value: p[k], 'aria-label': `${p.name || 'preset'} ${k}`, style: k === 'name' ? 'width:9em' : 'width:5.5em', title: { name: 'Name', width: 'Width (px)', height: 'Height (px)', fps: 'Frames per second' }[k] }); inp.addEventListener('change', () => { p[k] = k === 'name' ? inp.value : Number(inp.value); }); return inp; }),
      h('button', { title: 'Remove this preset', onclick: () => { list.splice(i, 1); draw(); } }, '×'))));
    draw();
    return [h('p', { class: 'hint' }, 'Name, width, height and frame rate. Click a preset on the Render tab to use it for the scene.'), rows,
      h('div', { class: 'row', style: 'margin-top:10px' },
        h('button', { onclick: () => { list.push({ name: 'New preset', width: 1080, height: 1920, fps: 30 }); draw(); } }, 'Add preset'),
        h('button', { onclick: () => { list = PRESETS_DEFAULT.map(p => ({ ...p })); draw(); } }, 'Back to defaults'),
        h('span', { class: 'spacer', style: 'flex:1' }),
        h('button', { class: 'primary', onclick: () => { savePresets(list); close(); ctx.rebuild(); ctx.toast('Presets saved'); } }, 'Save'), h('button', { onclick: close }, 'Cancel'))];
  });
  return m;
}
// minutes for a render at this PC's measured speed (seconds per frame, learned from past renders)
export async function estimate(ctx, frames, preview = false) {
  let rate = null;
  try { rate = (await ctx.api('render-estimate', {}))[preview ? 'preview' : 'full']; } catch {}
  if (!rate) return { minutes: null, text: 'No estimate yet: the first render measures this PC\'s speed.' };
  const min = frames * rate / 60;
  return { minutes: +min.toFixed(1), secPerFrame: +rate.toFixed(2), text: `About ${min < 1 ? 'under a minute' : Math.ceil(min) + ' min'} (${rate.toFixed(1)} s per frame on this PC).` };
}

// ---------------------------------------------------------------- export preflight
// Blocks a final export that breaks the rules: audio imported, lip sync sampled across the
// video, captions short and inside the Instagram safe zone below the face, moderator PASS.
export const contentHash = sc => { const s = JSON.stringify(strip({ ...sc, moderator: undefined, overrides: undefined, active: undefined })); let x = 5381; for (let i = 0; i < s.length; i++) x = ((x << 5) + x + s.charCodeAt(i)) | 0; return (x >>> 0).toString(36); };
export function preflight(ctx, sc = ctx.scene(), { envelope = null, project2d = null } = {}) {
  const checks = [];
  const add = (id, label, ok, detail, block = true) => checks.push({ id, label, ok: !!ok, detail, block });
  add('audio', 'Voice or music imported', !!sc.audio?.path, sc.audio?.path ? sc.audio.path.split(/[\\/]/).pop() : 'File › Import audio for the scene…');
  // lip sync: where the audio is loud, the mouth must be moving
  if (sc.audio?.path) {
    let loud = 0, open = 0, t0 = 0, values = new Set();
    for (const s of sc.shots) {
      for (let f = 0; f < s.length; f += 3) {
        const m = ctx.valueAt(s, 'mouth', f);
        values.add(Math.round(m));
        if (envelope ? (envelope[t0 + f] || 0) > 0.25 : true) { loud++; if (Math.round(m) > 0) open++; }
      }
      t0 += s.length;
    }
    const share = loud ? open / loud : 0;
    add('lipsync', 'Lip sync sampled across the video', values.size >= 3 && share >= 0.5, `${Math.round(share * 100)}% of loud frames have a speech mouth, ${values.size} different mouths used`);
  } else add('lipsync', 'Lip sync sampled across the video', false, 'Needs the voice imported first');
  // captions
  const caps = [];
  sc.shots.forEach(s => (s.items || []).filter(it => it.text != null).forEach(it => caps.push({ s, it })));
  const bad = [];
  for (const { s, it } of caps) {
    const words = it.text.trim().split(/\s+/).filter(Boolean), lines = it.text.split('\n').length;
    if (words.length <= 3 && lines > 1) bad.push(`${s.code} "${it.text}": 1–3 words stay on one line`);
    else if (lines > 2) bad.push(`${s.code} "${it.text}": two lines at most`);
    if (project2d) {
      const p = project2d(s, it);
      if (p && (p.x < 0.06 || p.x > 0.94 || p.y < 0.14 || p.y > 0.8)) bad.push(`${s.code} "${it.text}": outside the Instagram safe zone`);
      else if (p && p.headY != null && p.y < p.headY + 0.05) bad.push(`${s.code} "${it.text}": over the face (captions go below his mouth and eyes)`);
    }
  }
  add('captions', 'Captions short, in the safe zone, below the face', !bad.length, caps.length ? (bad.length ? bad.join('; ') : `${caps.length} caption${caps.length > 1 ? 's' : ''} OK`) : 'No captions in this scene');
  const h = contentHash(sc);
  add('moderator', 'Moderator PASS for this exact version', sc.moderator?.hash === h, sc.moderator?.hash === h ? `PASS recorded ${new Date(sc.moderator.at).toLocaleString()}${sc.moderator.note ? ': ' + sc.moderator.note : ''}` : sc.moderator ? 'The scene changed after the PASS: submit it again' : 'Submit the scene to the moderator first');
  return { ok: checks.every(c => c.ok || !c.block), checks, hash: h };
}
export function recordModeratorPass(sc, note = '') {
  sc.moderator = { hash: contentHash(sc), at: new Date().toISOString(), note: String(note).slice(0, 200) };
  return sc.moderator;
}
// screen position (0..1) of a caption at its frame, and where the head is, from the live camera
export function projector(ctx) {
  return (s, it) => {
    const view = ctx.view(), keep = { shot: ctx.scene().active, frame: ctx.frame() };
    try {
      ctx.showFrame(s, it.frame || 0);
      view.camera.updateMatrixWorld();
      const at = it.at || [0, 0.8, 1.25];
      const p = new THREE.Vector3(...at).project(view.camera);
      const hp = view.headPoint().project(view.camera);
      return { x: (p.x + 1) / 2, y: (1 - p.y) / 2, headY: (1 - hp.y) / 2 };
    } finally { ctx.showFrame(ctx.scene().shots[keep.shot], keep.frame); }
  };
}
export function preflightDialog(ctx, r, onGo) {
  const { h } = ctx;
  return modal(ctx, r.ok ? 'Ready to export' : 'Export blocked', close => [
    h('div', { class: 'ds-list' }, ...r.checks.map(c => h('div', { class: 'row preflight ' + (c.ok ? 'ok' : 'bad') }, h('b', {}, c.ok ? '✓' : '✗'), h('span', { style: 'flex:1' }, h('b', {}, c.label), h('br'), h('small', {}, c.detail || ''))))),
    r.estimate ? h('p', { class: 'hint' }, r.estimate) : null,
    h('div', { class: 'row', style: 'margin-top:10px' },
      ...(r.checks.some(c => c.id === 'moderator' && !c.ok) ? [h('button', { title: 'Use only once the moderator thread gave this version an overall PASS', onclick: () => { ctx.pushUndo('Moderator PASS'); recordModeratorPass(ctx.scene(), 'marked in the app'); close(); ctx.toast('Moderator PASS recorded for this version'); } }, 'Moderator gave PASS')] : []),
      h('span', { style: 'flex:1' }),
      r.ok ? h('button', { class: 'primary', onclick: () => { close(); onGo(); } }, 'Render') : h('button', { title: 'Your call: renders anyway and notes the override in the scene', onclick: () => { const sc = ctx.scene(); (sc.overrides ||= []).push({ at: new Date().toISOString(), failed: r.checks.filter(c => !c.ok).map(c => c.id) }); close(); onGo(); } }, 'Override and render'),
      h('button', { onclick: close }, 'Cancel'))]);
}

// ---------------------------------------------------------------- overnight batch
export function batchDialog(ctx) {
  const { h } = ctx;
  const jobs = [{ name: ctx.scene().name, scene: ctx.scene(), path: ctx.file() }];
  let sleep = true, preview = false;
  return modal(ctx, 'Overnight batch', close => {
    const list = h('div', { class: 'ds-list' });
    const draw = () => list.replaceChildren(...jobs.map((j, i) => h('div', { class: 'row' }, h('span', { style: 'flex:1' }, j.name, h('small', {}, ` · ${j.scene.shots.length} shots`)), h('button', { onclick: () => { jobs.splice(i, 1); draw(); } }, '×'))));
    draw();
    const cb = (label, get, set, tip) => { const c = h('input', { type: 'checkbox' }); c.checked = get(); c.addEventListener('change', () => set(c.checked)); return h('label', { class: 'row', title: tip }, c, label); };
    return [h('p', { class: 'hint' }, 'Queue several scenes and leave them rendering. Each scene goes to its own DeepInDoodles folder; scenes that fail the preflight are skipped and listed.'), list,
      h('div', { class: 'row' }, h('button', { onclick: async () => { const r = await ctx.api('pick-scenes', {}); for (const s of r.scenes || []) if (!jobs.some(j => j.path === s.path)) jobs.push({ name: s.project.name, scene: s.project, path: s.path }); draw(); } }, 'Add scenes…')),
      cb('Put the PC to sleep when all renders are done', () => sleep, v => { sleep = v; }, 'Two minutes after the last render the PC sleeps. Cancel from the notification or Tools › Cancel sleep.'),
      cb('Quick preview quality (half size, no cloth)', () => preview, v => { preview = v; }),
      h('div', { class: 'row', style: 'margin-top:10px' }, h('span', { style: 'flex:1' }),
        h('button', { class: 'primary', onclick: async () => { close(); const r = await runBatch(ctx, jobs, { preview, sleep }); ctx.toast(`${r.queued.length} scene${r.queued.length === 1 ? '' : 's'} queued${r.skipped.length ? `; skipped (preflight): ${r.skipped.map(s => s.name).join(', ')}` : ''}${sleep ? '. The PC sleeps when they are done.' : ''}`, 8000); } }, 'Start batch'),
        h('button', { onclick: close }, 'Cancel'))];
  });
}
export async function runBatch(ctx, jobs, { preview = false, sleep = false } = {}) {
  const queued = [], skipped = [];
  for (const j of jobs) {
    const sc = j.scene;
    if (!preview) {
      const pf = preflight(ctx, sc, sc === ctx.scene() ? { envelope: ctx.envelope(), project2d: projector(ctx) } : {});
      if (!pf.ok) { skipped.push({ name: sc.name, failed: pf.checks.filter(c => !c.ok).map(c => c.id) }); continue; }
    }
    await ctx.api('render-scene', { name: sc.name, fps: sc.fps, width: sc.width, height: sc.height, audio: sc.audio?.path || null, preview, shots: sc.shots.map(s => ({ code: s.code, audio: s.audio?.path || null, shot: ctx.bridgeFor(sc, s) })) });
    queued.push(sc.name);
  }
  if (queued.length && sleep) await ctx.api('sleep-when-done', { on: true });
  return { queued, skipped, sleep: !!(queued.length && sleep) };
}

// ---------------------------------------------------------------- health check with one-click fixes
export async function health(ctx) {
  const sc = ctx.scene(), host = await ctx.api('health', { audio: [sc.audio?.path, ...sc.shots.map(s => s.audio?.path)].filter(Boolean) });
  const items = [];
  const add = (id, label, ok, detail, fix) => items.push({ id, label, ok: !!ok, detail, fix: ok ? null : fix || null });
  add('blender', 'Blender found', host.blender, host.blender || 'Not found', 'pick-blender');
  add('library', 'Doodle Library found', host.library.found, host.library.dir, 'pick-library');
  add('renders', 'DeepInDoodles folder writable', host.renders.writable, host.renders.root);
  add('disk', 'Disk space for renders', host.disk.freeGB >= 10, `${host.disk.freeGB} GB free`, 'cache');
  add('mcp', 'Doodle Studio 3D MCP is serving', host.mcp.ok, `port ${host.mcp.port}`);
  add('autosave', 'Autosave on', ctx.autosaveMinutes() > 0, ctx.autosaveMinutes() ? `every ${ctx.autosaveMinutes()} min` : 'off', 'autosave');
  const missing = (host.audioMissing || []);
  add('audio', 'Scene audio file is there', !missing.length, missing.length ? 'Missing: ' + missing.join(', ') : sc.audio?.path ? 'OK' : 'No audio imported', 'relink-audio');
  const past = [];
  for (const s of sc.shots) for (const [id, ks] of Object.entries(s.tracks)) if (ks.some(k => k.f >= s.length)) past.push(`${s.code} ${id}`);
  add('keys', 'No keys past the end of a shot', !past.length, past.length ? past.slice(0, 6).join(', ') + (past.length > 6 ? '…' : '') : 'OK', 'trim-keys');
  const codes = sc.shots.map(s => s.code), dup = codes.filter((c, i) => codes.indexOf(c) !== i);
  add('codes', 'Shot codes are unique', !dup.length, dup.length ? 'Repeated: ' + [...new Set(dup)].join(', ') : `${codes.length} shots`, 'renumber');
  return { ok: items.every(i => i.ok), items, cacheGB: host.cacheGB };
}
export async function fix(ctx, id) {
  const sc = ctx.scene();
  switch (id) {
    case 'pick-blender': return ctx.api('pick-blender', {});
    case 'pick-library': return ctx.api('pick-library', {});
    case 'autosave': return ctx.setAutosave({ minutes: 3 });
    case 'relink-audio': return ctx.importAudio();
    case 'cache': return cacheDialog(ctx);
    case 'trim-keys': {
      ctx.pushUndo('Trim keys past shot ends');
      let n = 0;
      for (const s of sc.shots) for (const id of Object.keys(s.tracks)) { const k = s.tracks[id].length; s.tracks[id] = s.tracks[id].filter(x => x.f < s.length); n += k - s.tracks[id].length; if (!s.tracks[id].length) delete s.tracks[id]; }
      ctx.changed(true);
      return { removed: n };
    }
    case 'renumber': {
      ctx.pushUndo('Renumber shots');
      sc.shots.forEach((s, i) => { s.code = 'sh' + String((i + 1) * 10).padStart(3, '0'); });
      ctx.changed(true);
      return { codes: sc.shots.map(s => s.code) };
    }
  }
  throw Error('No fix ' + id);
}
export async function healthDialog(ctx) {
  const { h } = ctx, r = await health(ctx);
  return modal(ctx, 'Health check', close => [
    h('div', { class: 'ds-list' }, ...r.items.map(i => h('div', { class: 'row preflight ' + (i.ok ? 'ok' : 'bad') }, h('b', {}, i.ok ? '✓' : '✗'), h('span', { style: 'flex:1' }, h('b', {}, i.label), h('br'), h('small', {}, i.detail || '')),
      i.fix ? h('button', { onclick: async () => { try { await fix(ctx, i.fix); } catch (e) { ctx.toast(e.message, 4000); } close(); if (i.fix !== 'cache') healthDialog(ctx); } }, 'Fix') : null))),
    h('p', { class: 'hint' }, `Render cache: ${r.cacheGB} GB (Tools › Clean up cache…).`),
    h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: close }, 'Close'))]);
}

// ---------------------------------------------------------------- pack project, cache cleanup
export async function pack(ctx) {
  const r = await ctx.api('pack-project', { project: ctx.scene() });
  ctx.toast(`Packed into ${r.dir} (${r.files.length} files)`, 6000);
  return r;
}
export async function cacheDialog(ctx) {
  const { h } = ctx;
  let days = 14;
  const info = await ctx.api('cache-info', { days });
  return modal(ctx, 'Clean up cache', close => [
    h('p', {}, `Render check folders (logs, shot data, frame checks) older than ${days} days: ${info.old.count} folders, ${info.old.gb} GB. Blender test frames: ${info.tests.gb} GB.`),
    h('p', { class: 'hint' }, 'Your renders, finals, versions, autosaves and scene files are never touched. Rule reports from the last two weeks stay for the moderator.'),
    h('div', { class: 'row', style: 'margin-top:10px' }, h('span', { style: 'flex:1' }),
      h('button', { class: 'primary', disabled: !info.old.count && !info.tests.gb, onclick: async () => { const r = await ctx.api('cache-clean', { days }); close(); ctx.toast(`Freed ${r.gb} GB`, 4000); } }, 'Clean up'),
      h('button', { onclick: close }, 'Cancel'))]);
}
