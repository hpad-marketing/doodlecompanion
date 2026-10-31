// Doodle Studio 3D: the window, the local editor server and background Blender renders.
// Separate from the 2D Doodle Studio: its own port (54190), its own profile, and it never
// touches the 2D app's MCP config, ports or Assistant switch.
const { app, BrowserWindow, dialog, ipcMain, Notification, shell, session, net, screen } = require('electron');
const fs = require('node:fs'), path = require('node:path');
const PORT = 54190;
const appDir = __dirname;
const docs = app.getPath('documents');
const dataDir = path.join(app.getPath('appData'), 'DoodleStudio3D');
fs.mkdirSync(dataDir, { recursive: true });
app.setName('Doodle Studio 3D');
app.setPath('userData', path.join(dataDir, 'session'));
app.setAppUserModelId('DoodleStudio3D');

const settingsFile = path.join(dataDir, 'settings.json');
const settings = {
  get() {
    let s = {};
    try { s = JSON.parse(fs.readFileSync(settingsFile, 'utf8')); } catch {}
    return { rendersRoot: path.join(docs, 'DeepInDoodles'), blender: '', libraryDir: path.join(docs, 'Talking Character App', 'blender-library'), ...s };
  },
  set(patch) { fs.writeFileSync(settingsFile, JSON.stringify({ ...settings.get(), ...patch }, null, 2)); },
};

let main = null, allowClose = false, updates = null;
const icon = path.join(appDir, 'ui', 'icon.png');

function atomicWrite(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = file + '.' + process.pid + '.tmp';
  fs.writeFileSync(tmp, text);
  fs.renameSync(tmp, file);
}

const library = require('./library.cjs')({ settings });
// overnight batch: when the last queued render finishes, the PC sleeps two minutes later (cancellable)
let sleepWhenDone = false, sleepTimer = null;
function idle() {
  if (!sleepWhenDone) return;
  sleepWhenDone = false;
  try { new Notification({ title: 'All renders are done', body: 'The PC goes to sleep in 2 minutes. Tools › Cancel sleep after renders keeps it awake.', icon }).show(); } catch {}
  clearTimeout(sleepTimer);
  sleepTimer = setTimeout(() => {
    sleepTimer = null;
    if (renders.busy() || process.platform !== 'win32') return;
    try { require('node:child_process').spawn('rundll32.exe', ['powrprof.dll,SetSuspendState', '0', '1', '0'], { detached: true, windowsHide: true }).unref(); } catch {}
  }, 120000);
}
const dirBytes = d => { let n = 0; try { for (const e of fs.readdirSync(d, { withFileTypes: true })) { const f = path.join(d, e.name); n += e.isDirectory() ? dirBytes(f) : fs.statSync(f).size; } } catch {} return n; };
const gb = n => +(n / 1e9).toFixed(2);
// render check folders (logs, shot data, frame checks) in every scene's work\checks, oldest first
function oldChecks(days) {
  const root = settings.get().rendersRoot, cut = Date.now() - days * 864e5, out = [];
  let scenes = [];
  try { scenes = fs.readdirSync(root, { withFileTypes: true }).filter(e => e.isDirectory()); } catch {}
  for (const e of scenes) {
    const dir = path.join(root, e.name, 'work', 'checks');
    let kids = [];
    try { kids = fs.readdirSync(dir, { withFileTypes: true }).filter(k => k.isDirectory()); } catch { continue; }
    for (const k of kids) { const f = path.join(dir, k.name); try { if (fs.statSync(f).mtimeMs < cut) out.push(f); } catch {} }
  }
  return out;
}
// nightly backup: every scene file in DeepInDoodles\<Scene>\work, one folder per day, kept 7 days
function nightlyBackup() {
  try {
    const dir = path.join(dataDir, 'backups'), day = new Date().toISOString().slice(0, 10), today = path.join(dir, day);
    fs.mkdirSync(dir, { recursive: true });
    if (!fs.existsSync(today)) {
      const root = settings.get().rendersRoot;
      let n = 0;
      for (const e of fs.readdirSync(root, { withFileTypes: true }).filter(e => e.isDirectory())) {
        const work = path.join(root, e.name, 'work');
        let files = [];
        try { files = fs.readdirSync(work).filter(f => f.endsWith('.ds3d')); } catch { continue; }
        for (const f of files) { fs.mkdirSync(path.join(today, e.name), { recursive: true }); fs.copyFileSync(path.join(work, f), path.join(today, e.name, f)); n++; }
      }
      fs.writeFileSync(path.join(today, 'backup.json'), JSON.stringify({ at: new Date().toISOString(), scenes: n }));
    }
    const cut = Date.now() - 7 * 864e5;
    for (const d of fs.readdirSync(dir)) if (/^\d{4}-\d{2}-\d{2}$/.test(d) && Date.parse(d) < cut) fs.rmSync(path.join(dir, d), { recursive: true, force: true });
  } catch {}
}
// a packed scene keeps its audio next to it: paths are relative to the .ds3d file
function unpack(project, file) {
  if (!project.packed || !file) return project;
  const abs = p => (p && !path.isAbsolute(p) ? path.join(path.dirname(file), p) : p);
  if (project.audio?.path) project.audio.path = abs(project.audio.path);
  for (const s of project.shots || []) if (s.audio?.path) s.audio.path = abs(s.audio.path);
  return project;
}
const renders = require('./render.cjs')({
  appDir, settings, onIdle: () => idle(),
  notify(j) {
    const ok = j.state === 'done';
    const reused = (j.shots || []).filter(s => s.reused).length;
    const body = j.scene === 'carousel' && j.state === 'done' ? `${(j.slides || []).length} slides saved in work\\carousel\\${j.id}. Rule check: ${j.rules || 'PASS'}.`
      : j.state === 'done' ? `Rule check: ${j.rules || 'PASS'}.${reused ? ` ${reused} unchanged shot${reused > 1 ? 's' : ''} reused.` : ''} Saved in ${path.basename(j.video || '')}, in work\\renders.`
      : j.state === 'cancelled' ? 'Render cancelled.'
      : j.state === 'rules failed' ? `The rule check failed (${j.detail || j.rules}). See rules.json in work\\checks.` : `Render ${j.state}: ${j.detail || 'see blender.log in work\\checks'}.`;
    try { new Notification({ title: ok ? `${j.id} is ready` : `${j.id}: ${j.state}`, body, icon }).show(); } catch {}
    shell.beep();
    if (main && !main.isDestroyed()) main.webContents.executeJavaScript(`window.ds3dRenderDone && window.ds3dRenderDone(${JSON.stringify({ id: j.id, kind: j.scene === 'carousel' ? 'carousel' : j.scene ? 'scene' : 'shot', state: j.state, rules: j.rules, detail: j.detail || null, video: j.video, out: j.out, shots: j.shots, slides: j.slides || null })})`).catch(() => {});
  },
});

// Open in Blender: the active shot in a full Blender window, live-linked both ways (mirror.cjs)
const mirror = require('./mirror.cjs')({ appDir, port: PORT, blender: () => renders.blender(), blendFor: s => renders.blendFor(s), withMaster: s => renders.withMaster(s),
  folders: n => renders.folders(n), env: () => renders.env() });

// 3D view models of library sets, props and scenery (models.cjs): Blender converts each once
const stageModels = require('./models.cjs')({ libraryDir: () => settings.get().libraryDir, cacheDir: () => path.join(dataDir, 'models'),
  command: (ids, dir) => { const exe = renders.blender(); return exe ? [exe, ['-b', '--factory-startup', '--python', path.join(appDir, 'blender', 'preview_export.py'), '--', settings.get().libraryDir, dir, ...ids]] : null; } });

// a path the app (or Claude) may read or write: inside DeepInDoodles, with one of the given extensions
function insideRenders(p, exts = ['.png']) {
  const root = path.resolve(settings.get().rendersRoot), f = path.resolve(String(p || ''));
  if (!f.startsWith(root + path.sep)) throw Error('Only files inside DeepInDoodles');
  if (!exts.includes(path.extname(f).toLowerCase())) throw Error(`Only ${exts.join(', ')} files here`);
  return f;
}

const api = {
  ...mirror.api,
  'stage-models': req => stageModels.models(req),
  'models-info': () => stageModels.info(),
  // the scene file lives at DeepInDoodles\<Scene>\work\<Scene>.ds3d
  async save({ project, path: p, auto }) {
    let file = p;
    const fname = String(project.name || 'Untitled scene').replace(/[<>:"/\\|?*\x00-\x1f]/g, '').trim() + '.ds3d';
    if (!file && auto) file = path.join(renders.folders(project.name).work, fname);
    if (!file) {
      const { work } = renders.folders(project.name);
      const r = await dialog.showSaveDialog(main, { title: 'Save scene', defaultPath: path.join(work, fname), filters: [{ name: 'Doodle Studio 3D scene', extensions: ['ds3d'] }] });
      if (r.canceled || !r.filePath) return {};
      file = r.filePath;
    }
    atomicWrite(file, JSON.stringify(project, null, 1));
    return { path: file };
  },
  // Save as for Claude: only to a .ds3d inside the renders folder, never a dialog
  async 'save-at'({ project, path: p }) {
    const file = insideRenders(String(p).endsWith('.ds3d') ? p : p + '.ds3d', ['.ds3d']);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    atomicWrite(file, JSON.stringify(project, null, 1));
    return { path: file };
  },
  async open() {
    const r = await dialog.showOpenDialog(main, { title: 'Open scene', defaultPath: settings.get().rendersRoot, filters: [{ name: 'Doodle Studio 3D scene', extensions: ['ds3d', 'json'] }], properties: ['openFile'] });
    if (r.canceled || !r.filePaths[0]) return {};
    const project = JSON.parse(fs.readFileSync(r.filePaths[0], 'utf8'));
    if (project.app !== 'doodle-studio-3d') throw Error('That file is not a Doodle Studio 3D scene');
    return { project: unpack(project, r.filePaths[0]), path: r.filePaths[0] };
  },
  // never lose work: rolling autosaves, a recovery file for crashes, named versions
  async autosave({ project, file, frame, keep = 5 }) {
    const dir = path.join(dataDir, 'autosave'); fs.mkdirSync(dir, { recursive: true });
    const base = String(project.name || 'Untitled scene').replace(/[<>:"/\\|?*\x00-\x1f]/g, '').trim();
    const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15);
    atomicWrite(path.join(dir, `${base}_${stamp}.ds3d`), JSON.stringify(project));
    const mine = fs.readdirSync(dir).filter(f => f.startsWith(base + '_') && f.endsWith('.ds3d')).sort();
    for (const f of mine.slice(0, Math.max(0, mine.length - Math.max(1, Math.min(50, keep | 0))))) fs.unlinkSync(path.join(dir, f));
    atomicWrite(path.join(dataDir, 'recovery.json'), JSON.stringify({ at: new Date().toISOString(), file: file || null, frame: frame | 0, project }));
    return { kept: Math.min(mine.length, keep), dir };
  },
  async recovery() {
    const f = path.join(dataDir, 'recovery.json');
    try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return null; }
  },
  async 'recovery-clear'() { try { fs.unlinkSync(path.join(dataDir, 'recovery.json')); } catch {} return {}; },
  async 'save-version'({ project, label }) {
    const { work } = renders.folders(project.name);
    const clean = s => String(s || '').replace(/[<>:"/\\|?*\x00-\x1f]/g, '').trim();
    const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 13);
    const file = path.join(work, 'versions', `${clean(project.name) || 'Untitled'}_${clean(label).replace(/ +/g, '-') || 'version'}_${stamp}.ds3d`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    atomicWrite(file, JSON.stringify(project, null, 1));
    return { path: file };
  },
  async 'list-versions'({ name }) {
    const dir = path.join(renders.folders(name).work, 'versions');
    if (!fs.existsSync(dir)) return { versions: [] };
    return { versions: fs.readdirSync(dir).filter(f => f.endsWith('.ds3d')).sort().reverse().map(f => ({ file: path.join(dir, f), name: f, at: fs.statSync(path.join(dir, f)).mtime.toISOString() })) };
  },
  async 'open-file'({ file }) {
    const project = JSON.parse(fs.readFileSync(insideRenders(file, ['.ds3d', '.json']), 'utf8'));
    if (project.app !== 'doodle-studio-3d') throw Error('That file is not a Doodle Studio 3D scene');
    return { project: unpack(project, file), path: file };
  },
  // free space where renders go: warn before a render can fill the disk
  async disk() {
    const root = settings.get().rendersRoot;
    fs.mkdirSync(root, { recursive: true });
    const s = fs.statfsSync(root);
    return { root, freeGB: +(s.bavail * s.bsize / 1e9).toFixed(1), totalGB: +(s.blocks * s.bsize / 1e9).toFixed(1) };
  },
  async 'export-bridge'({ shot, name, code }) {
    const { checks } = renders.folders(name);
    const file = path.join(checks, `${String(name || 'scene').replace(/\s+/g, '_')}${code ? '_' + code : ''}.shot.json`);
    atomicWrite(file, JSON.stringify(shot));
    return { path: file };
  },
  async render(req) { return renders.render(req); },
  async 'render-scene'(req) { return renders.renderScene(req); },
  async 'render-carousel'(req) { return renders.renderCarousel(req); },
  // carousel bubbles are drawn in the window, so it reads and writes the slide PNGs, inside DeepInDoodles only
  async 'read-png'({ path: p }) { return { data: fs.readFileSync(insideRenders(p)).toString('base64') }; },
  async 'write-png'({ path: p, data }) { const f = insideRenders(p); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, Buffer.from(String(data), 'base64')); return { path: f }; },
  async 'write-file'({ path: p, data }) {
    if (!/[.](webm|mp4|png|json|txt|wav|srt|csv)$/i.test(String(p))) throw Error('Only video, image, sound and text files');
    const f = insideRenders(p, ['.webm', '.mp4', '.png', '.json', '.txt', '.wav', '.srt', '.csv']); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, Buffer.from(String(data), 'base64')); return { path: f };
  },
  // scene audio: any voice or music file the user picks
  async 'pick-audio'() {
    const r = await dialog.showOpenDialog(main, { title: 'Import audio for this scene', defaultPath: path.join(settings.get().rendersRoot, 'Audio'), filters: [{ name: 'Audio', extensions: ['wav', 'mp3', 'm4a', 'aac', 'ogg', 'flac'] }], properties: ['openFile'] });
    return { path: r.canceled ? null : r.filePaths[0] || null };
  },
  // reference video for the animator: shown on a plane in the viewport, never rendered
  async 'pick-video'() {
    const r = await dialog.showOpenDialog(main, { title: 'Reference video', filters: [{ name: 'Video', extensions: ['mp4', 'm4v', 'webm', 'mov'] }], properties: ['openFile'] });
    return { path: r.canceled ? null : r.filePaths[0] || null };
  },
  // a real photo for a cut-in: any image the user picks, read once
  async 'pick-image'() {
    const r = await dialog.showOpenDialog(main, { title: 'Photo for a cut-in', filters: [{ name: 'Image', extensions: ['png', 'jpg', 'jpeg', 'webp'] }], properties: ['openFile'] });
    return { path: r.canceled ? null : r.filePaths[0] || null };
  },
  async 'read-image'({ path: p }) {
    if (!/[.](png|jpe?g|webp)$/i.test(String(p))) throw Error('Not an image file');
    if (fs.statSync(p).size > 30e6) throw Error('Image over 30 MB');
    return { data: fs.readFileSync(p).toString('base64'), type: /png$/i.test(p) ? 'image/png' : /webp$/i.test(p) ? 'image/webp' : 'image/jpeg' };
  },
  // an SVG drawing for the drawings layer: read as text, never run
  async 'read-svg'({ path: p }) {
    if (!/[.]svg$/i.test(String(p))) throw Error('Not an .svg file');
    if (fs.statSync(p).size > 8e6) throw Error('SVG over 8 MB');
    return { text: fs.readFileSync(p, 'utf8') };
  },
  async 'ref-video'({ path: p }) { return require('./server.cjs').registerRef(p); },
  async 'read-audio'({ path: p }) {
    if (!/[.](wav|mp3|m4a|aac|ogg|flac)$/i.test(String(p))) throw Error('Not an audio file');
    if (fs.statSync(p).size > 300e6) throw Error('Audio file over 300 MB');
    return { data: fs.readFileSync(p).toString('base64') };
  },
  async 'render-status'() { return renders.status(); },
  async 'render-estimate'() { return renders.rate(); },
  async 'sleep-when-done'({ on }) { sleepWhenDone = !!on; if (!on) { clearTimeout(sleepTimer); sleepTimer = null; } return { on: sleepWhenDone }; },
  async 'pick-scenes'() {
    const r = await dialog.showOpenDialog(main, { title: 'Add scenes to the batch', defaultPath: settings.get().rendersRoot, filters: [{ name: 'Doodle Studio 3D scene', extensions: ['ds3d'] }], properties: ['openFile', 'multiSelections'] });
    if (r.canceled) return { scenes: [] };
    const scenes = [];
    for (const f of r.filePaths) { try { const p = JSON.parse(fs.readFileSync(f, 'utf8')); if (p.app === 'doodle-studio-3d') scenes.push({ path: f, project: unpack(p, f) }); } catch {} }
    return { scenes };
  },
  // health check: everything the app needs on this PC
  async health({ audio = [] } = {}) {
    const root = settings.get().rendersRoot;
    let writable = false;
    try { fs.mkdirSync(root, { recursive: true }); const t = path.join(root, '.ds3d-write-test'); fs.writeFileSync(t, 'ok'); fs.unlinkSync(t); writable = true; } catch {}
    let freeGB = 0;
    try { const st = fs.statfsSync(root); freeGB = +(st.bavail * st.bsize / 1e9).toFixed(1); } catch {}
    const lib = settings.get().libraryDir;
    return { blender: renders.blender() || null, library: { dir: lib, found: fs.existsSync(path.join(lib, 'library.json')) }, renders: { root, writable }, disk: { freeGB },
      mcp: { ok: true, port: PORT }, audioMissing: audio.filter(a => !fs.existsSync(a)).map(a => path.basename(a)),
      cacheGB: gb(oldChecks(0).reduce((n, f) => n + dirBytes(f), 0) + dirBytes(path.join(dataDir, 'blender-check'))) };
  },
  async 'cache-info'({ days = 14 }) {
    const old = oldChecks(days);
    return { old: { count: old.length, gb: gb(old.reduce((n, f) => n + dirBytes(f), 0)) }, tests: { gb: gb(dirBytes(path.join(dataDir, 'blender-check'))) } };
  },
  // only app-made check folders older than `days` and Blender test frames; never renders, finals, versions or scenes
  async 'cache-clean'({ days = 14 }) {
    let n = 0;
    for (const f of oldChecks(Math.max(7, Number(days) || 14))) { n += dirBytes(f); fs.rmSync(f, { recursive: true, force: true }); }
    const t = path.join(dataDir, 'blender-check'); n += dirBytes(t); fs.rmSync(t, { recursive: true, force: true });
    return { gb: gb(n) };
  },
  // pack project: the scene plus its audio in one folder (work\pack\<Scene>_pack_<stamp>) that opens anywhere
  async 'pack-project'({ project }) {
    const { work } = renders.folders(project.name);
    const clean = String(project.name || 'Untitled scene').replace(/[<>:"/\\|?*\x00-\x1f]/g, '').trim() || 'Untitled scene';
    const stamp = new Date().toISOString().replace(/[-:]/g, '').slice(0, 13);
    const dir = path.join(work, 'pack', `${clean.replace(/\s+/g, '_')}_pack_${stamp}`);
    fs.mkdirSync(path.join(dir, 'audio'), { recursive: true });
    const p = JSON.parse(JSON.stringify(project)), files = [], missing = [];
    const take = a => {
      if (!a?.path) return;
      if (!fs.existsSync(a.path)) { missing.push(a.path); return; }
      const name = path.basename(a.path), dst = path.join(dir, 'audio', name);
      if (!fs.existsSync(dst)) { fs.copyFileSync(a.path, dst); files.push(dst); }
      a.path = 'audio/' + name;
    };
    take(p.audio);
    for (const s of p.shots || []) take(s.audio);
    p.packed = true;
    const file = path.join(dir, clean + '.ds3d');
    atomicWrite(file, JSON.stringify(p, null, 1));
    files.unshift(file);
    return { dir, files, missing };
  },
  async 'render-cancel'() { return renders.cancel(); },
  async settings(patch) { if (patch && Object.keys(patch).length) settings.set(patch); return { ...settings.get(), blenderFound: renders.blender() || null }; },
  // a new Blender is only switched to after it renders a test frame that passes the rule check
  async 'pick-blender'() {
    const r = await dialog.showOpenDialog(main, { title: 'Find blender.exe', defaultPath: 'C:\\Program Files\\Blender Foundation', filters: [{ name: 'Blender', extensions: ['exe'] }], properties: ['openFile'] });
    if (r.canceled || !r.filePaths[0]) return { blender: renders.blender() || null };
    const t = await renders.tryBlender(r.filePaths[0], dataDir);
    return { blender: renders.blender() || null, test: t };
  },
  // the master Bunny file: the user's own copy of Bunny3D_v2.blend, used by every Bunny render
  async 'pick-master'({ path: given } = {}) {
    let f = given;
    if (!f) {
      const r = await dialog.showOpenDialog(main, { title: 'Pick the master Bunny .blend', defaultPath: settings.get().masterBlend || settings.get().rendersRoot, filters: [{ name: 'Blender file', extensions: ['blend'] }], properties: ['openFile'] });
      if (r.canceled || !r.filePaths[0]) return { masterBlend: settings.get().masterBlend || null };
      f = r.filePaths[0];
    }
    if (!/\.blend$/i.test(f) || !fs.existsSync(f)) throw Error('Pick a .blend file');
    settings.set({ masterBlend: f });
    return { masterBlend: f };
  },
  async 'open-master'() {
    const exe = renders.blender(), f = settings.get().masterBlend && fs.existsSync(settings.get().masterBlend) ? settings.get().masterBlend : path.join(appDir, 'blender', 'Bunny3D_v2.blend');
    if (!exe) return { opened: null };
    require('node:child_process').spawn(exe, [f], { detached: true, stdio: 'ignore' }).unref();
    return { opened: f };
  },
  async 'blender-versions'() { return { versions: renders.findBlenders(), inUse: renders.blender() || null }; },
  async 'try-blender'({ path: exe }) { const t = await renders.tryBlender(exe, dataDir); return { blender: renders.blender() || null, test: t, versions: renders.findBlenders() }; },
  async reveal({ file }) { if (file && fs.existsSync(file)) shell.showItemInFolder(file); return {}; },
  // the Doodle Library on this PC (motions, faces, props, sets, outfits): read-only here
  async library() { return library.items(); },
  async 'library-motion'({ id }) { return library.motion(id); },
  async 'pick-library'() {
    const r = await dialog.showOpenDialog(main, { title: 'Find the Doodle Library folder (it holds library.json)', defaultPath: settings.get().libraryDir, properties: ['openDirectory'] });
    if (r.canceled || !r.filePaths[0]) return library.items();
    if (!fs.existsSync(path.join(r.filePaths[0], 'library.json'))) throw Error('That folder has no library.json');
    settings.set({ libraryDir: r.filePaths[0] });
    return library.items();
  },
};

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (main) { if (main.isMinimized()) main.restore(); main.focus(); } });
  ipcMain.handle('ds3d:check-updates', () => updates ? updates.check(true) : 'unavailable');
  ipcMain.on('ds3d:close-window', () => { allowClose = true; main?.close(); });
  app.whenReady().then(async () => {
    const call = js => new Promise((ok, fail) => {
      if (!main || main.isDestroyed()) return fail(Error('The Doodle Studio 3D window is closed'));
      // the renderer's own error message comes back (Electron otherwise reports only 'Script failed to execute')
      main.webContents.executeJavaScript(`Promise.resolve().then(() => (${js})).then(v => ({ ok: v }), e => ({ err: String((e && e.message) || e) }))`)
        .then(r => (r && 'err' in r ? fail(Error(r.err)) : ok(r && r.ok)), fail);
    });
    const mcp = require('./mcp.cjs')({ call, api });
    api['mcp-replay'] = ({ name, args }) => mcp.replay(name, args);
    await require('./server.cjs')({ root: path.join(appDir, 'ui'), port: PORT, api, mcp, statics: { lib: () => settings.get().libraryDir, models: () => path.join(dataDir, 'models') } });
    let saved = {};
    try { saved = JSON.parse(fs.readFileSync(path.join(dataDir, 'window.json'), 'utf8')); } catch {}
    const valid = saved.bounds && screen.getAllDisplays().some(d => saved.bounds.x < d.workArea.x + d.workArea.width && saved.bounds.x + saved.bounds.width > d.workArea.x);
    main = new BrowserWindow({ ...(valid ? saved.bounds : { width: 1500, height: 940 }), minWidth: 900, minHeight: 600, title: 'Doodle Studio 3D', icon,
      backgroundColor: '#E0A64B', show: false, autoHideMenuBar: true,
      webPreferences: { preload: path.join(appDir, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, backgroundThrottling: false } });
    main.removeMenu();
    main.webContents.on('will-navigate', (e, url) => { if (!url.startsWith(`http://127.0.0.1:${PORT}/`)) e.preventDefault(); });
    // only the viewport pop-out may open, and it goes to the second screen: the Kamvas pen display stays the primary
    main.webContents.setWindowOpenHandler(({ frameName, features }) => {
      // detached Tools and Timeline docks (ux2d.js): their own windows, where they were last left
      if (/^ds3d-panel-(tools|timeline)$/.test(frameName)) {
        const f = Object.fromEntries(String(features || '').split(',').map(x => x.split('=').map(s => s.trim())).filter(x => x[0]).map(([k, v]) => [k, Number(v)]));
        const primary = screen.getPrimaryDisplay(), other = screen.getAllDisplays().filter(d => d.id !== primary.id)[0], wa = (other || primary).workArea;
        const w = Math.min(f.width || 1400, wa.width), hh = Math.min(f.height || 600, wa.height);
        const on = Number.isFinite(f.left) && screen.getAllDisplays().some(d => f.left >= d.workArea.x - 20 && f.left < d.workArea.x + d.workArea.width && f.top >= d.workArea.y - 20 && f.top < d.workArea.y + d.workArea.height);
        return { action: 'allow', overrideBrowserWindowOptions: { x: on ? f.left : wa.x + Math.round((wa.width - w) / 2), y: on ? f.top : wa.y + Math.round((wa.height - hh) / 2), width: w, height: hh,
          title: 'Doodle Studio 3D', icon, backgroundColor: '#E0A64B', autoHideMenuBar: true, webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true } } };
      }
      if (frameName !== 'ds3d-viewport') return { action: 'deny' };
      const primary = screen.getPrimaryDisplay(), other = screen.getAllDisplays().filter(d => d.id !== primary.id).sort((a, b) => b.workArea.width * b.workArea.height - a.workArea.width * a.workArea.height)[0];
      const wa = (other || primary).workArea, w = Math.min(1100, wa.width), hh = Math.min(1300, wa.height);
      return { action: 'allow', overrideBrowserWindowOptions: { x: wa.x + Math.round((wa.width - w) / 2), y: wa.y + Math.round((wa.height - hh) / 2), width: w, height: hh, title: 'Doodle Studio 3D: viewport', icon, backgroundColor: '#E0A64B', autoHideMenuBar: true,
        webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true } } };
    });
    main.webContents.on('did-create-window', w => { w.removeMenu(); w.webContents.on('will-navigate', e => e.preventDefault()); });
    main.on('close', e => {
      // a clean close leaves nothing to recover; a crash leaves recovery.json for the next start
      if (allowClose) { try { fs.unlinkSync(path.join(dataDir, 'recovery.json')); } catch {} return; }
      e.preventDefault();
      main.webContents.executeJavaScript('window.ds3dRequestClose ? window.ds3dRequestClose() : true').then(ok => { if (ok) { allowClose = true; main.close(); } }).catch(() => { allowClose = true; main.close(); });
    });
    const remember = () => { try { fs.writeFileSync(path.join(dataDir, 'window.json'), JSON.stringify({ bounds: main.getNormalBounds(), maximized: main.isMaximized() })); } catch {} };
    main.on('resize', remember); main.on('move', remember);
    await main.loadURL(`http://127.0.0.1:${PORT}/`);
    if (saved.maximized !== false) main.maximize();
    main.show();
    try { updates = require('./updater.cjs')({ app, dialog, net, window: () => main, logDir: dataDir }); } catch {}
    // update safety check: the MCP must answer initialize and list its tools
    updates?.verify(async () => {
      const r = await net.fetch(`http://127.0.0.1:${PORT}/mcp`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify([{ jsonrpc: '2.0', id: 1, method: 'initialize', params: {} }, { jsonrpc: '2.0', id: 2, method: 'tools/list' }]) });
      const j = await r.json();
      return Array.isArray(j) && j[0]?.result?.serverInfo && (j[1]?.result?.tools || []).length > 10;
    }).catch(() => {});
    nightlyBackup(); setInterval(nightlyBackup, 60 * 60000);
  }).catch(e => { dialog.showErrorBox('Doodle Studio 3D could not open', String(e && e.stack || e)); app.exit(1); });
  app.on('window-all-closed', () => app.quit());
  // an open Blender window is told the link has ended (it stays open with its own copy)
  app.on('before-quit', () => { try { mirror.api['mirror-close']({ quiet: true }); } catch {} });
}
