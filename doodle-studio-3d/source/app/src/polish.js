// Never lose work and move faster: autosave, crash recovery, named versions, the Ctrl+K
// command search, timeline markers with notes, a chime when a render is done, a disk
// space check before renders, and an fps meter.

// ---------------------------------------------------------------- autosave + recovery
const AUTOSAVE_DEFAULT = { minutes: 3, keep: 10 };
export function autosaveSettings() {
  try { return { ...AUTOSAVE_DEFAULT, ...JSON.parse(localStorage.getItem('ds3d.autosave') || '{}') }; } catch { return { ...AUTOSAVE_DEFAULT }; }
}
export function setAutosave(patch) {
  const s = { ...autosaveSettings(), ...patch };
  s.minutes = Math.max(0, Math.min(60, Number(s.minutes) || 0));   // 0 = off
  s.keep = Math.max(1, Math.min(50, Math.round(Number(s.keep) || 1)));
  try { localStorage.setItem('ds3d.autosave', JSON.stringify(s)); } catch {}
  return s;
}

let lastSaved = null, timer = null;
export function startAutosave(ctx) {
  clearInterval(timer);
  const s = autosaveSettings();
  if (!s.minutes) return;
  timer = setInterval(() => autosaveNow(ctx).catch(() => {}), s.minutes * 60000);
}
export async function autosaveNow(ctx, force = false) {
  const snap = JSON.stringify(ctx.scene());
  if (!force && snap === lastSaved) return null;
  const r = await ctx.api('autosave', { project: ctx.scene(), file: ctx.file(), frame: ctx.frame(), keep: autosaveSettings().keep });
  lastSaved = snap;
  ctx.status?.(`Autosaved ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
  return r;
}

// after a crash: offer the last autosave, at the same shot and frame
export async function offerRecovery(ctx) {
  let r = null;
  try { r = await ctx.api('recovery'); } catch { return false; }
  if (!r?.project) return false;
  const when = new Date(r.at).toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' });
  if (!confirm(`Doodle Studio 3D did not close properly last time. Reopen "${r.project.name}" as it was at ${when}?`)) {
    await ctx.api('recovery-clear', {});
    return false;
  }
  ctx.restore(r.project, r.file, r.frame);
  ctx.toast('Recovered. Save it to keep it.', 5000);
  return true;
}

// ---------------------------------------------------------------- named versions
export async function saveVersion(ctx, label) {
  label ??= prompt('Name this version (e.g. "before re-timing")', '');
  if (label == null) return null;
  const r = await ctx.api('save-version', { project: ctx.scene(), label });
  ctx.toast('Version saved: ' + r.path.split(/[\\/]/).pop(), 4000);
  return r;
}
export async function versionsDialog(ctx) {
  const { versions } = await ctx.api('list-versions', { name: ctx.scene().name });
  const { h } = ctx;
  const close = () => box.remove();
  const box = h('div', { class: 'ds-modal', role: 'dialog', 'aria-label': 'Versions' },
    h('div', { class: 'ds-modal-card' }, h('h3', {}, `Versions of ${ctx.scene().name}`),
      versions.length ? h('div', { class: 'ds-list' }, ...versions.map(v => h('button', { onclick: async () => {
        if (ctx.dirty() && !confirm('Open this version? Unsaved changes in the open scene are lost (the autosave keeps a copy).')) return;
        const r = await ctx.api('open-file', { file: v.file });
        ctx.restore(r.project, null, 0);
        ctx.toast('Opened ' + v.name + '. Save as to keep it as the scene.', 5000);
        close();
      } }, v.name.replace(/\.ds3d$/, ''), h('small', {}, new Date(v.at).toLocaleString())))) : h('p', { class: 'hint' }, 'No versions yet. File › Save version… keeps one.'),
      h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: () => saveVersion(ctx).then(close) }, 'Save version now'), h('button', { onclick: close }, 'Close'))));
  box.addEventListener('pointerdown', e => { if (e.target === box) close(); });
  document.body.append(box);
}

// ---------------------------------------------------------------- Ctrl+K command search
export function commandSearch(ctx) {
  const { h } = ctx;
  if (document.querySelector('.ds-cmd')) return;
  const cmds = ctx.commands();
  const input = h('input', { type: 'search', placeholder: 'Type a command, e.g. render, mirror, focus, koala', 'aria-label': 'Command search' });
  const list = h('div', { class: 'ds-list', role: 'listbox' });
  let sel = 0, shown = [];
  const close = () => box.remove();
  const run = c => { close(); try { Promise.resolve(c.run()).catch(e => ctx.toast(e.message, 4000)); } catch (e) { ctx.toast(e.message, 4000); } };
  const fill = () => {
    const words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
    shown = cmds.filter(c => words.every(w => (c.group + ' ' + c.label).toLowerCase().includes(w))).slice(0, 14);
    sel = Math.min(sel, Math.max(0, shown.length - 1));
    list.replaceChildren(...shown.map((c, i) => h('button', { role: 'option', 'aria-selected': String(i === sel), onclick: () => run(c) }, h('span', {}, c.label), h('small', {}, c.group + (c.key ? ' · ' + c.key : '')))));
  };
  input.addEventListener('input', () => { sel = 0; fill(); });
  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { sel = Math.min(shown.length - 1, sel + 1); fill(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { sel = Math.max(0, sel - 1); fill(); e.preventDefault(); }
    else if (e.key === 'Enter' && shown[sel]) run(shown[sel]);
    else if (e.key === 'Escape') close();
    e.stopPropagation();
  });
  const box = h('div', { class: 'ds-modal ds-cmd' }, h('div', { class: 'ds-modal-card' }, input, list));
  box.addEventListener('pointerdown', e => { if (e.target === box) close(); });
  document.body.append(box);
  fill();
  input.focus();
}

// ---------------------------------------------------------------- markers with notes
export function addMarker(ctx, f = ctx.frame(), note) {
  note ??= prompt(`Note for the marker at frame ${f} (e.g. "beat", "cut here", "smile")`, '');
  if (note == null) return null;
  const p = ctx.project();
  ctx.pushUndo();
  p.markers ||= [];
  const m = p.markers.find(m => m.f === f);
  if (m) m.note = String(note); else p.markers.push({ f, note: String(note) });
  p.markers.sort((a, b) => a.f - b.f);
  ctx.changed();
  return p.markers;
}
export function markerEls(ctx, ppf) {
  const { h } = ctx;
  return (ctx.project().markers || []).map((m, i) => h('div', { class: 'marker', style: `left:${m.f * ppf}px`, title: `${m.note || 'Marker'} (frame ${m.f}). Click to go there, double-click to edit, right-click to remove.`,
    onpointerdown: e => { e.stopPropagation(); ctx.goto(m.f); },
    ondblclick: e => { e.stopPropagation(); addMarker(ctx, m.f, prompt('Marker note', m.note || '') ?? m.note); },
    oncontextmenu: e => { e.preventDefault(); ctx.pushUndo(); ctx.project().markers.splice(i, 1); ctx.changed(); } }, m.note ? m.note.slice(0, 18) : ''));
}

// ---------------------------------------------------------------- render done chime + disk check
export function chime(ok = true) {
  try {
    const a = new AudioContext(), t = a.currentTime;
    for (const [i, f] of (ok ? [660, 880] : [440, 330]).entries()) {
      const o = a.createOscillator(), g = a.createGain();
      o.frequency.value = f; o.type = 'sine';
      g.gain.setValueAtTime(0.0001, t + i * 0.16); g.gain.exponentialRampToValueAtTime(0.18, t + i * 0.16 + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + i * 0.16 + 0.3);
      o.connect(g).connect(a.destination); o.start(t + i * 0.16); o.stop(t + i * 0.16 + 0.32);
    }
    setTimeout(() => a.close(), 1200);
  } catch {}
}
export async function diskOk(ctx, needGB = 5) {
  try {
    const d = await ctx.api('disk', {});
    if (d.freeGB < needGB) return confirm(`Only ${d.freeGB} GB free where renders go (${d.root}). A render can need several GB. Render anyway?`);
  } catch {}
  return true;
}

// ---------------------------------------------------------------- fps meter
let fpsOn = false, frames = 0, since = performance.now(), fps = 0;
export const toggleFps = () => (fpsOn = !fpsOn);
export function fpsTick() {
  frames++;
  const now = performance.now();
  if (now - since >= 1000) { fps = Math.round(frames * 1000 / (now - since)); frames = 0; since = now; return true; }
  return false;
}
export const fpsText = () => (fpsOn ? `${fps} fps` : null);
