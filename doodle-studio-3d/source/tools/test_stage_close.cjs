// A Koala shot on a library stage, rendered by Blender (fake launcher = bpy): bedroom set,
// golden light, raincoat + bow tie, a mug in the right hand, rain, a time-skip card.
const path = require('path');
const appDir = path.join(__dirname, '..', 'host');
const root = path.join(__dirname, '..', 'devout', 'DeepInDoodles');
const libraryDir = process.env.DSL_LIBRARY || path.join(__dirname, '..', '..', 'lib');
const r = require('../host/render.cjs')({ appDir, settings: { get: () => ({ rendersRoot: root, libraryDir, blender: path.join(__dirname, 'fakeblender.sh') }) }, notify: j => { console.log('NOTIFY', j.id, j.state, j.rules, j.video || j.out); } });
const cam = { yaw: 10, pitch: 5, dist: 1.6, lens: 35, roll: 0, tx: 0, ty: 0, tz: 0.35 };
const shot = { fps: 30, width: 1080, height: 1920, character: process.argv[2] || 'koala',
  frames: Array.from({ length: 4 }, (_, i) => ({ armR: 30, elbowR: 60, expression: 1, noseWiggle: i * 20, earLScale: 100, earRScale: 100, cam })),
  stage: { set: 'bedroom', setProps: { rug: false }, time: 'golden', outfit: 'raincoat', accessories: ['bowtie'], mouthSet: 'mouths-bouncy' },
  items: [{ id: 'prop-mug', frame: 0, hold: 'R' }, { id: 'fx:rain', frame: 0 }, { id: 'story:time_skip', frame: 2, text: 'Later' }] };
console.log(r.render({ name: 'Stage Close', shot, preview: true, still: 3 }));
const t = setInterval(() => { const s = r.status(); if (s.state === 'idle') clearInterval(t); }, 3000);
