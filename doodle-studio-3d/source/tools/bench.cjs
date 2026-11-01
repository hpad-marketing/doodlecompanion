// Headless bench: the real editor in Chromium, its MCP on a port, and real Blender renders through
// render.cjs with the bpy stand-in (fakeblender.sh). An assistant can drive it exactly as it drives
// the installed app, so the guide can be tested from a fresh start.
//   DS3D_BPY=<python with bpy> DSL_LIBRARY=<library folder> node tools/bench.cjs [port]
// MCP: http://127.0.0.1:<port>/mcp (default 54250). Renders land in devout/bench/DeepInDoodles.
// It reuses every dev.cjs handler and swaps in a page-driven MCP and real renders; dev.cjs is unchanged.
const path = require('node:path'), fs = require('node:fs');
const { chromium } = require('playwright');
const PORT = Number(process.argv[2] || 54250);
const root = path.join(__dirname, '..', 'devout', 'bench', 'DeepInDoodles');
fs.mkdirSync(root, { recursive: true });

let page = null;
const serverPath = require.resolve('../host/server.cjs');
const realStart = require(serverPath);
const settingsData = { rendersRoot: root, blender: path.join(__dirname, 'fakeblender.sh'), libraryDir: process.env.DSL_LIBRARY };
const settings = { get: () => settingsData, set: p => Object.assign(settingsData, p) };
const renders = require('../host/render.cjs')({ appDir: path.join(__dirname, '..', 'host'), settings,
  notify: j => {
    console.log('render', j.id, j.state, j.rules || '', j.video || j.detail || '');
    if (page) page.evaluate(`window.ds3dRenderDone && window.ds3dRenderDone(${JSON.stringify({ id: j.id, kind: j.scene === 'carousel' ? 'carousel' : j.scene ? 'scene' : 'shot', state: j.state, rules: j.rules, detail: j.detail || null, video: j.video })})`).catch(() => {});
  } });

function benchStart(opts) {
  const api = { ...opts.api,
    render: req => renders.render(req), 'render-scene': req => renders.renderScene(req), 'render-carousel': req => renders.renderCarousel(req),
    'render-status': () => renders.status(), 'render-cancel': () => renders.cancel(), 'render-estimate': () => renders.rate(),
    settings: patch => { if (patch && typeof patch === 'object') settings.set(patch); return { ...settingsData, blenderFound: settingsData.blender }; },
    // scene files go where the app puts them: DeepInDoodles\<Scene>\work\<Scene>.ds3d
    save: ({ project, path: p }) => { const f = p || path.join(renders.folders(project.name).work, String(project.name || 'Untitled scene').replace(/[<>:"/\\|?*\x00-\x1f]/g, '').trim() + '.ds3d'); fs.writeFileSync(f, JSON.stringify(project, null, 1)); return { path: f }; },
    'save-at': ({ project, path: p }) => { const f = path.isAbsolute(p) ? p : path.join(root, p); const out = f.endsWith('.ds3d') ? f : f + '.ds3d'; fs.mkdirSync(path.dirname(out), { recursive: true }); fs.writeFileSync(out, JSON.stringify(project, null, 1)); return { path: out }; },
  };
  const mcp = require('../host/mcp.cjs')({ call: js => page.evaluate(`Promise.resolve(${js})`), api });
  return realStart({ ...opts, port: PORT, api, mcp }).then(async () => {
    const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
    page = await b.newPage({ viewport: { width: 1600, height: 950 } });
    page.on('pageerror', e => console.log('pageerror', e.message));
    await page.goto(`http://127.0.0.1:${PORT}/`);
    await page.waitForSelector('body[data-ready="1"]', { timeout: 120000 });
    console.log(`bench up: MCP at http://127.0.0.1:${PORT}/mcp, renders in ${root}`);
  });
}
Object.assign(benchStart, realStart);
require.cache[serverPath].exports = benchStart;
process.argv[2] = String(PORT);  // dev.cjs (and its Open in Blender relay) use the same port
require('./dev.cjs');
