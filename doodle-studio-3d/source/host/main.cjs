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
    return { rendersRoot: path.join(docs, 'DeepInDoodles'), blender: '', ...s };
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

const renders = require('./render.cjs')({
  appDir, settings,
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

function insideRenders(p) {
  const root = path.resolve(settings.get().rendersRoot), f = path.resolve(String(p || ''));
  if (!f.startsWith(root + path.sep) || path.extname(f).toLowerCase() !== '.png') throw Error('Only PNGs inside DeepInDoodles');
  return f;
}

const api = {
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
  async open() {
    const r = await dialog.showOpenDialog(main, { title: 'Open scene', defaultPath: settings.get().rendersRoot, filters: [{ name: 'Doodle Studio 3D scene', extensions: ['ds3d', 'json'] }], properties: ['openFile'] });
    if (r.canceled || !r.filePaths[0]) return {};
    const project = JSON.parse(fs.readFileSync(r.filePaths[0], 'utf8'));
    if (project.app !== 'doodle-studio-3d') throw Error('That file is not a Doodle Studio 3D scene');
    return { project, path: r.filePaths[0] };
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
  async 'write-png'({ path: p, data }) { fs.writeFileSync(insideRenders(p), Buffer.from(String(data), 'base64')); return {}; },
  async 'render-status'() { return renders.status(); },
  async 'render-cancel'() { return renders.cancel(); },
  async settings(patch) { if (patch && Object.keys(patch).length) settings.set(patch); return { ...settings.get(), blenderFound: renders.blender() || null }; },
  // a new Blender is only switched to after it renders a test frame that passes the rule check
  async 'pick-blender'() {
    const r = await dialog.showOpenDialog(main, { title: 'Find blender.exe', defaultPath: 'C:\\Program Files\\Blender Foundation', filters: [{ name: 'Blender', extensions: ['exe'] }], properties: ['openFile'] });
    if (r.canceled || !r.filePaths[0]) return { blender: renders.blender() || null };
    const t = await renders.tryBlender(r.filePaths[0], dataDir);
    return { blender: renders.blender() || null, test: t };
  },
  async 'blender-versions'() { return { versions: renders.findBlenders(), inUse: renders.blender() || null }; },
  async 'try-blender'({ path: exe }) { const t = await renders.tryBlender(exe, dataDir); return { blender: renders.blender() || null, test: t, versions: renders.findBlenders() }; },
  async reveal({ file }) { if (file && fs.existsSync(file)) shell.showItemInFolder(file); return {}; },
};

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (main) { if (main.isMinimized()) main.restore(); main.focus(); } });
  ipcMain.handle('ds3d:check-updates', () => updates ? updates.check(true) : 'unavailable');
  ipcMain.on('ds3d:close-window', () => { allowClose = true; main?.close(); });
  app.whenReady().then(async () => {
    const call = js => new Promise((ok, fail) => {
      if (!main || main.isDestroyed()) return fail(Error('The Doodle Studio 3D window is closed'));
      main.webContents.executeJavaScript(`Promise.resolve(${js})`).then(ok, fail);
    });
    const mcp = require('./mcp.cjs')({ call, api });
    await require('./server.cjs')({ root: path.join(appDir, 'ui'), port: PORT, api, mcp });
    let saved = {};
    try { saved = JSON.parse(fs.readFileSync(path.join(dataDir, 'window.json'), 'utf8')); } catch {}
    const valid = saved.bounds && screen.getAllDisplays().some(d => saved.bounds.x < d.workArea.x + d.workArea.width && saved.bounds.x + saved.bounds.width > d.workArea.x);
    main = new BrowserWindow({ ...(valid ? saved.bounds : { width: 1500, height: 940 }), minWidth: 900, minHeight: 600, title: 'Doodle Studio 3D', icon,
      backgroundColor: '#E0A64B', show: false, autoHideMenuBar: true,
      webPreferences: { preload: path.join(appDir, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true, backgroundThrottling: false } });
    main.removeMenu();
    main.webContents.on('will-navigate', (e, url) => { if (!url.startsWith(`http://127.0.0.1:${PORT}/`)) e.preventDefault(); });
    main.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
    main.on('close', e => {
      if (allowClose) return;
      e.preventDefault();
      main.webContents.executeJavaScript('window.ds3dRequestClose ? window.ds3dRequestClose() : true').then(ok => { if (ok) { allowClose = true; main.close(); } }).catch(() => { allowClose = true; main.close(); });
    });
    const remember = () => { try { fs.writeFileSync(path.join(dataDir, 'window.json'), JSON.stringify({ bounds: main.getNormalBounds(), maximized: main.isMaximized() })); } catch {} };
    main.on('resize', remember); main.on('move', remember);
    await main.loadURL(`http://127.0.0.1:${PORT}/`);
    if (saved.maximized !== false) main.maximize();
    main.show();
    try { updates = require('./updater.cjs')({ app, dialog, net, window: () => main, logDir: dataDir }); } catch {}
  }).catch(e => { dialog.showErrorBox('Doodle Studio 3D could not open', String(e && e.stack || e)); app.exit(1); });
  app.on('window-all-closed', () => app.quit());
}
