// Real Blender stills of the park: flat, shadows, Classic 3-point, flowers at 40%.
// Run: node tools/lights_still.cjs <blender.exe> (DSL_LIBRARY set)
const path = require('path'), fs = require('fs');
const appDir = path.join(__dirname, '..', 'host'), root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const libraryDir = process.env.DSL_LIBRARY, blender = process.argv[2];
const cam = { yaw: 0, pitch: 4, dist: 4.4, lens: 35, roll: 0, tx: 0, ty: 0, tz: 0.6 };
const classic = { preset: 'classic', target: 'lead', turn: 0, key: 1, fill: 0.2, back: 0.4, keyA: -35, fillA: 45, backA: 145, height: 1.9, distance: 2.6, soft: 0.35, shade: 0.32 };
const cases = {
  flat: { set: 'park' }, shadows: { set: 'park', shadows: true }, classic: { set: 'park', shadows: true, lighting: classic },
  inks: { set: 'park', inks: { flowers: 40 } }, dusk: { set: 'park', shadows: true, halftone: true },
  felt: { set: 'park' }, feltlit: { set: 'park', shadows: true, lighting: classic }, flatnoink: { set: 'park' },
};
const r = require('../host/render.cjs')({ appDir, settings: { set: () => {}, get: () => ({ rendersRoot: root, libraryDir, blender }) },
  notify: j => { if (j.state === 'done' || j.state === 'error') console.log(j.state, j.message || '', j.out || j.file || ''); } });
const names = (process.argv[3] || Object.keys(cases).join(',')).split(',');
(async () => {
  for (const n of names) {
    const shot = { fps: 30, width: 720, height: 1280, character: 'bunny', frames: [{ expression: 1, earLScale: 100, earRScale: 100, cam }], stage: cases[n] };
    const addons = { doodle_looks: path.join(appDir, 'blender', 'addons') }, L = o => ({ layers: { scene: { palette: 'dusk', addon: 'doodle_looks', ...o } }, addons });
    shot.materials = { dusk: L({ look: 'ink-mustard' }), felt: L({ look: 'felt', ink: false }), feltlit: L({ look: 'felt', ink: false }), flatnoink: L({ look: 'ink-mustard', ink: false }) }[n];
    r.render({ name: 'Lights ' + n, shot, preview: true, still: 1 });
    await new Promise(res => { const t = setInterval(() => { if (r.status().state === 'idle') { clearInterval(t); res(); } }, 1500); });
  }
})();
