// Viewport-only render of a pose at a given size: node vshot.cjs out.png W H 'js to run'
const { chromium } = require('playwright');
(async () => {
  const [out, W, H, js] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  p.on('pageerror', e => console.log('pageerror', e.message));
  await p.goto('http://127.0.0.1:54190/');
  await p.waitForSelector('body[data-ready="1"]');
  await p.evaluate(([w, h]) => { const v = ds3d.view; v.renderer.setPixelRatio(1); v.resize(+w, +h); v.grid.visible = false; }, [W, H]);
  if (js) await p.evaluate(js);
  await p.evaluate(() => { ds3d.view.render(); });
  const url = await p.evaluate(() => { ds3d.view.render(); return ds3d.view.canvas.toDataURL('image/png'); });
  require('fs').writeFileSync(out, Buffer.from(url.split(',')[1], 'base64'));
  await b.close();
})();
