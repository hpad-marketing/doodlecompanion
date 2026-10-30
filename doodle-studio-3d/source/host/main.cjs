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
    const body = j.state === 'done' ? `Rule check: ${j.rules || 'PASS'}. Saved in ${path.basename(path.dirname(path.dirname(j.out)))}\\work\\renders.`
      : j.state === 'rules failed' ? `The rule check failed: ${j.rules}. See rules.json in the render folder.` : `Render ${j.state}. See blender.log in the render folder.`;
    try { new Notification({ title: ok ? `${j.id} is ready` : `${j.id}: ${j.state}`, body, icon }).show(); } catch {}
    shell.beep();
    if (main && !main.isDestroyed()) main.webContents.executeJavaScript(`window.ds3dRenderDone && window.ds3dRenderDone(${JSON.stringify({ id: j.id, state: j.state, rules: j.rules, video: j.video, out: j.out })})`).catch(() => {});
  },
});

const api = {
  async save({ project, path: p, auto }) {
    let file = p;
    if (!file && auto) file = path.join(renders.folders(project.name).work, (project.name || 'shot') + '.ds3d.json');
    if (!file) {
      const { work } = renders.folders(project.name);
      const r = await dialog.showSaveDialog(main, { title: 'Save shot', defaultPath: path.join(work, (project.name || 'shot') + '.ds3d.json'), filters: [{ name: 'Doodle Studio 3D shot', extensions: ['json'] }] });
      if (r.canceled || !r.filePath) return {};
      file = r.filePath;
    }
    atomicWrite(file, JSON.stringify(project, null, 1));
    return { path: file };
  },
  async open() {
    const r = await dialog.showOpenDialog(main, { title: 'Open shot', defaultPath: settings.get().rendersRoot, filters: [{ name: 'Doodle Studio 3D shot', extensions: ['json'] }], properties: ['openFile'] });
    if (r.canceled || !r.filePaths[0]) return {};
    const project = JSON.parse(fs.readFileSync(r.filePaths[0], 'utf8'));
    if (project.app !== 'doodle-studio-3d') throw Error('That file is not a Doodle Studio 3D shot');
    return { project, path: r.filePaths[0] };
  },
  async 'export-bridge'({ shot, name }) {
    const { work } = renders.folders(name);
    const file = path.join(work, (name || 'shot') + '.shot.json');
    atomicWrite(file, JSON.stringify(shot));
    return { path: file };
  },
  async render(req) { return renders.render(req); },
  async 'render-status'() { return renders.status(); },
  async 'render-cancel'() { return renders.cancel(); },
  async settings(patch) { if (patch && Object.keys(patch).length) settings.set(patch); return { ...settings.get(), blenderFound: renders.blender() || null }; },
  async 'pick-blender'() {
    const r = await dialog.showOpenDialog(main, { title: 'Find blender.exe', defaultPath: 'C:\\Program Files\\Blender Foundation', filters: [{ name: 'Blender', extensions: ['exe'] }], properties: ['openFile'] });
    if (!r.canceled && r.filePaths[0]) settings.set({ blender: r.filePaths[0] });
    return { blender: renders.blender() || null };
  },
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
