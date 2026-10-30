// Doodle Studio 3D: editor shell. Same look as Doodle Studio; 3D-specific workflow.
import { Viewport } from './viewport.js';
import { cameraPresetsPanel, bindCameraPresets } from './camera-presets.js';
import { carouselPanel, bindOverlay, finishCarousel, carouselOf, exportCarousel, SIZES, KINDS, TAILS } from './carousel.js';
import { TRACK_IDS } from './rig.js';
import { newScene, newShotData, migrate, nextCode, bindShot, valueAt, frameValues, setKey, deleteKey, hasKey, toBridgeShot, idleFor, stageOf, CAM_DEFAULT, EASES, DISCRETE, defaults } from './project.js';
import { libraryPanel, libraryRows, useItem, setStage, removeItem, CHARACTERS, EXTRA } from './library.js';
import { idleOf, IDLE_DEFAULT, IDLE_RANGE } from './idle.js';

const $ = s => document.querySelector(s);
const h = (tag, attrs = {}, ...kids) => {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, '');
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null) el.append(c);
  return el;
};
const ICON = {
  start: 'M5 4v16M19 4 8 12l11 8z', play: 'M7 4v16l13-8z', pause: 'M7 4h4v16H7zM13 4h4v16h-4z', end: 'M19 4v16M5 4l11 8-11 8z',
  prev: 'M15 5l-7 7 7 7', next: 'M9 5l7 7-7 7', key: 'M12 3l9 9-9 9-9-9z', trash: 'M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13',
  orbit: 'M12 5a9 4 0 1 0 0.1 0M4 9l-1 3 3 0', pan: 'M12 3v18M3 12h18M12 3l-3 3M12 3l3 3M12 21l-3-3M12 21l3-3M3 12l3-3M3 12l3 3M21 12l-3-3M21 12l-3 3',
  frame: 'M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4', grid: 'M4 4h16v16H4zM4 12h16M12 4v16',
};
const icon = n => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 24 24'); s.innerHTML = `<path d="${ICON[n]}" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>`; return s; };

// ---------------------------------------------------------------- state
let data, view, scene = newScene(), project = bindShot(scene, scene.shots[0]), frame = 0, playing = false, tab = 'pose', part = 'whole';
let autoKey = true, selected = null, undoStack = [], redoStack = [], filePath = null, dirty = false;
const preview = {};   // unkeyed changes while Auto is off
let carouselSel = null, overlayDraw = null;
const thumbs = new Map();   // slide id -> small picture (not saved)

const PARTS = [
  ['whole', 'Whole', ['bodyX', 'bodyY', 'depth', 's', 'turn', 'bodyRot', 'breath', 'legReach']],
  ['body', 'Body', ['bodyTilt', 'torsoBow', 'torsoTwist']],
  ['head', 'Head', ['headYaw', 'headNod', 'rot']],
  ['ears', 'Ears', ['earLFold', 'earLForward', 'earLScale', 'earLSquash', 'earRFold', 'earRForward', 'earRScale', 'earRSquash']],
  ['nose', 'Nose', ['noseWiggle', 'noseSniff']],
  ['armL', 'Left arm', ['armL', 'armLForward', 'elbowL', 'wristL']],
  ['armR', 'Right arm', ['armR', 'armRForward', 'elbowR', 'wristR']],
  ['legL', 'Left leg', ['legL', 'legLOut', 'kneeL', 'footL']],
  ['legR', 'Right leg', ['legR', 'legROut', 'kneeR', 'footR']],
];
const LABEL = {
  bodyX: 'Left / right', bodyY: 'Up / down', depth: 'Near / far', s: 'Size', turn: 'Turn around', bodyRot: 'Rotate whole figure', breath: 'Breath',
  bodyTilt: 'Body tilt', torsoBow: 'Bow', torsoTwist: 'Twist', headYaw: 'Turn', headNod: 'Nod', rot: 'Tilt',
  earLFold: 'Left ear fold', earLForward: 'Left ear forward', earRFold: 'Right ear fold', earRForward: 'Right ear forward',
  earLScale: 'Left ear size %', earRScale: 'Right ear size %', earLSquash: 'Left ear squash', earRSquash: 'Right ear squash',
  legReach: 'Sitting leg reach', noseWiggle: 'Nose wiggle', noseSniff: 'Nose sniff',
  armL: 'Raise', armLForward: 'Forward', elbowL: 'Elbow bend', wristL: 'Wrist roll', armR: 'Raise', armRForward: 'Forward', elbowR: 'Elbow bend', wristR: 'Wrist roll',
  legL: 'Lift', legLOut: 'Out', kneeL: 'Knee bend', footL: 'Foot roll', legR: 'Lift', legROut: 'Out', kneeR: 'Knee bend', footR: 'Foot roll',
  'cam.yaw': 'Orbit', 'cam.pitch': 'Height angle', 'cam.dist': 'Distance', 'cam.lens': 'Lens (mm)', 'cam.roll': 'Roll (Dutch)',
  'cam.tx': 'Aim left / right', 'cam.ty': 'Aim near / far', 'cam.tz': 'Aim height',
  expression: 'Expression', gaze: 'Gaze', mouth: 'Speech mouth', blink: 'Blink',
};
const TIPS = {
  'cam.yaw': 'Swing the camera around Bunny. Positive moves it to screen right.',
  'cam.pitch': 'Positive looks down from above (high angle). Negative looks up from below (low angle). The whole set moves with the camera.',
  'cam.dist': 'How far the camera is from what it aims at, in metres.',
  'cam.lens': 'Focal length. 15–24 mm is wide and distorts; 85–135 mm is long and flattens.',
  'cam.roll': 'Tilts the frame for a Dutch angle.',
};
const EXTRA_RANGE = { legReach: [0, 100, 1], earLScale: [50, 150, 1], earRScale: [50, 150, 1], earLSquash: [-50, 30, 1], earRSquash: [-50, 30, 1], noseWiggle: [-100, 100, 1], noseSniff: [0, 100, 1],
  bodyX: [-400, 400, 1], bodyY: [-200, 200, 1], depth: [-4, 4, 0.05], s: [0.3, 2, 0.01], bodyRot: [-45, 45, 1], breath: [0, 90, 1],
  'cam.yaw': [-180, 180, 1], 'cam.pitch': [-60, 89, 1], 'cam.dist': [0.2, 60, 0.05], 'cam.lens': [12, 200, 1], 'cam.roll': [-45, 45, 1],
  'cam.tx': [-10, 10, 0.01], 'cam.ty': [-10, 10, 0.01], 'cam.tz': [-0.5, 10, 0.01] };
const LENSES = [15, 24, 35, 50, 85, 135];
const VIEWS = [['Front', { yaw: 0, pitch: 4 }], ['¾ left', { yaw: -40, pitch: 6 }], ['¾ right', { yaw: 40, pitch: 6 }], ['Side', { yaw: 90, pitch: 2 }],
  ['Back', { yaw: 180, pitch: 4 }], ['Low angle', { pitch: -25, tz: 0.45 }], ['High angle', { pitch: 45 }], ['Top down', { pitch: 85 }]];
const GAZE_ORDER = [5, 3, 6, 1, 0, 2, 7, 4, 8];   // Up Left, Up, Up Right / Left, Center, Right / Down...

let BUNNY_IDS = [];
const CAM_IDS = Object.keys(CAM_DEFAULT).map(k => 'cam.' + k);
const FACE_IDS = ['expression', 'gaze', 'mouth', 'blink'];

function range(id) {
  if (EXTRA_RANGE[id]) return EXTRA_RANGE[id];
  const c = data.controls.find(c => TRACK_IDS[c.name] === id);
  return c ? [c.min, c.max, 1] : [-180, 180, 1];
}

// ---------------------------------------------------------------- host bridge (Electron app or dev server)
async function api(path, body) {
  const r = await fetch('/api/' + path, { method: body === undefined ? 'GET' : 'POST', headers: { 'content-type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) throw Error((await r.text()) || r.statusText);
  return r.json();
}

function toast(msg, ms = 2200) {
  const t = h('div', { class: 'toast', role: 'status' }, msg);
  document.body.append(t);
  setTimeout(() => t.remove(), ms);
}

// ---------------------------------------------------------------- undo
function snapshot() { return JSON.stringify(scene); }
function pushUndo() { undoStack.push(snapshot()); if (undoStack.length > 200) undoStack.shift(); redoStack = []; dirty = true; }
function restore(json) { useScene(migrate(JSON.parse(json))); }
function undo() { if (!undoStack.length) return; redoStack.push(snapshot()); restore(undoStack.pop()); }
function redo() { if (!redoStack.length) return; undoStack.push(snapshot()); restore(redoStack.pop()); }

// ---------------------------------------------------------------- scene and shots (same model as the 2D app)
function useScene(sc) {
  scene = sc;
  project = bindShot(scene, scene.shots[scene.active]);
  frame = Math.max(0, Math.min(project.length - 1, frame));
  selected = null;
  refreshAll();
  if (character() !== loadedChar) ensureCharacter().then(refreshAll).catch(e => toast(e.message, 5000));
}

// ---------------------------------------------------------------- characters (library.js)
let loadedChar = 'bunny';
const charData = {};
const charName = () => (CHARACTERS.find(c => c[0] === character()) || [0, 'Bunny'])[1];
const shownParts = () => PARTS.filter(p => p[0] !== 'nose' || view.rig.bones.has('nose'));
async function ensureCharacter() {
  const c = character();
  if (c === loadedChar) return;
  charData[c] ||= await (await fetch(c === 'bunny' ? 'bunny3d.json' : `chars/${c}.json`)).json();
  data = charData[c];
  view.setCharacter(data);
  loadedChar = c;
}
async function setCharacter(c) {
  if (!CHARACTERS.some(x => x[0] === c)) throw Error('character must be one of ' + CHARACTERS.map(x => x[0]).join(', '));
  if (c === character()) return;
  pushUndo();
  scene.character = c;
  await ensureCharacter();
  refreshAll();
  toast(`${charName()} on stage`);
}
const libCtx = () => ({
  h, api, toast, pushUndo, goto, scene: () => scene, project: () => project, frame: () => frame, data: () => data,
  trackIds: () => BUNNY_IDS.concat(FACE_IDS), setCharacter: c => setCharacter(c).catch(e => toast(e.message, 5000)),
  changed: keys => { dirty = true; apply(); drawTracks(); if (keys) buildTimelineTools(); updateHud(); },
  rebuild: () => { if (tab === 'library') { const y = $('#panel-content').scrollTop; buildPanel(); $('#panel-content').scrollTop = y; } },
});
function shotIndex(ref) {
  if (ref == null) return scene.active;
  const i = typeof ref === 'number' ? ref : scene.shots.findIndex(s => s.code === ref || s.uid === ref);
  if (i < 0 || i >= scene.shots.length) throw Error(`No shot ${ref}`);
  return i;
}
function selectShot(ref) { const i = shotIndex(ref); if (i === scene.active) return; scene.active = i; frame = 0; useScene(scene); }
function addShot(duplicate = false) {
  pushUndo();
  const at = scene.active, code = nextCode(scene, at);
  const shot = duplicate ? { ...JSON.parse(JSON.stringify(scene.shots[at])), uid: newShotData(code).uid, code } : newShotData(code, project.length);
  // a new shot starts from where the last one ended, so the cut is clean to set up
  if (!duplicate) for (const [id, ks] of Object.entries(project.tracks)) shot.tracks[id] = [{ f: 0, v: valueAt(project, id, project.length - 1), ease: 'ease' }];
  if (!duplicate && project.idle) shot.idle = { ...project.idle };   // idle life carries on into the next shot
  scene.shots.splice(at + 1, 0, shot);
  scene.active = at + 1; frame = 0;
  useScene(scene);
  toast(`${duplicate ? 'Duplicated as' : 'Added'} ${code}`);
}
function moveShot(delta, ref) {
  const i = shotIndex(ref), j = Math.max(0, Math.min(scene.shots.length - 1, i + delta));
  if (i === j) return;
  pushUndo();
  const [s] = scene.shots.splice(i, 1);
  scene.shots.splice(j, 0, s);
  scene.active = j;
  useScene(scene);
}
function deleteShot(ref) {
  const i = shotIndex(ref);
  if (scene.shots.length === 1) return toast('A scene needs at least one shot');
  if (!confirm(`Delete ${scene.shots[i].code}${scene.shots[i].label ? ' (' + scene.shots[i].label + ')' : ''}? Undo brings it back.`)) return;
  pushUndo();
  scene.shots.splice(i, 1);
  scene.active = Math.min(i, scene.shots.length - 1);
  useScene(scene);
}
function labelShot(ref, text) {
  const i = shotIndex(ref), s = scene.shots[i];
  const v = text ?? prompt(`Name for ${s.code} (shown on its chip)`, s.label || '');
  if (v == null) return;
  pushUndo(); s.label = String(v).trim(); buildTimelineTools();
}
const shotName = s => s.code + (s.label ? ' · ' + s.label : '');
const sceneFrames = () => scene.shots.reduce((n, s) => n + s.length, 0);

// ---------------------------------------------------------------- values
function current(id) { return id in preview ? preview[id] : valueAt(project, id, frame); }

function setValue(id, v, { record = true } = {}) {
  const [lo, hi] = range(id);
  if (!DISCRETE.has(id)) v = Math.max(lo, Math.min(hi, v));
  if (autoKey && record) { setKey(project, id, frame, v); delete preview[id]; dirty = true; scheduleTracks(); }
  else preview[id] = v;
  apply();
}

let tracksQueued = false;
function scheduleTracks() { if (tracksQueued) return; tracksQueued = true; requestAnimationFrame(() => { tracksQueued = false; drawTracks(); }); }

function apply() {
  const vals = {};
  for (const id of BUNNY_IDS.concat(FACE_IDS)) vals[id] = current(id);
  // idle life plays in the viewport too, except on a value being tried out unkeyed
  const idle = idleNow()?.frames[frame];
  if (idle) for (const [id, v] of Object.entries(idle)) if (!(id in preview)) vals[id] = v;
  view.pose(vals);
  const cam = {};
  for (const id of CAM_IDS) cam[id.slice(4)] = current(id);
  view.setCamera(cam);
  syncPanel();
  drawPlayhead();
  updateHud();
  overlayDraw?.();
}

// ---------------------------------------------------------------- carousel (carousel.js)
function slideThumb() {
  const src = view.renderer.domElement, c = document.createElement('canvas');
  c.width = 90; c.height = Math.round(90 * src.height / src.width);
  c.getContext('2d').drawImage(src, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', 0.7);
}
const carCtx = () => ({
  h, api, toast, pushUndo, goto, layout, thumbs, thumb: slideThumb, poll: () => pollRender(),
  scene: () => scene, project: () => project, frame: () => frame, tab: () => tab,
  selectShot: i => selectShot(i), selected: () => carouselSel, select: id => { carouselSel = id; },
  rebuild: () => { buildPanel(); overlayDraw?.(); }, refreshOverlay: () => overlayDraw?.(),
  bridgeShot: s => bridge(bindShot(scene, s)),
  // bubbles show while the playhead sits on the selected slide
  currentSlide: () => { const s = carouselOf(scene).slides.find(x => x.id === carouselSel); return s && s.shot === project.uid && s.frame === frame ? s : null; },
});

// ---------------------------------------------------------------- menu bar
const MENUS = [
  ['File', [['New scene', newShot, 'Ctrl+N'], ['Open…', openShot, 'Ctrl+O'], ['Save', () => saveShot(false), 'Ctrl+S'], ['Save as…', () => saveShot(true), 'Ctrl+Shift+S'], '-',
    ['Render scene (all shots)', () => renderScene(), 'Ctrl+Shift+E'], ['Render this shot', () => render(), 'Ctrl+R'], ['Render this frame', () => render(true), 'Ctrl+Shift+R'], '-', ['Export Blender shot file…', exportBridge]]],
  ['Shot', [['Add shot after this one', () => addShot(false), 'Ctrl+T'], ['Duplicate this shot', () => addShot(true), 'Ctrl+Shift+T'], ['Name this shot…', () => labelShot()],
    '-', ['Move earlier', () => moveShot(-1), 'Alt+←'], ['Move later', () => moveShot(1), 'Alt+→'], '-', ['Previous shot', () => selectShot(Math.max(0, scene.active - 1)), 'PgUp'],
    ['Next shot', () => selectShot(Math.min(scene.shots.length - 1, scene.active + 1)), 'PgDn'], '-', ['Delete this shot', () => deleteShot()]]],
  ['Edit', [['Undo', undo, 'Ctrl+Z'], ['Redo', redo, 'Ctrl+Shift+Z'], '-', ['Key Bunny pose', () => keyGroup(BUNNY_IDS.concat(FACE_IDS)), 'K'], ['Key camera', () => keyGroup(CAM_IDS), 'Shift+K'],
    ['Delete selected key', deleteSelected, 'Delete'], ['Clear all keys', clearAll]]],
  ['View', [['Dark mode', toggleDark, 'Ctrl+D'], ['Floor grid', () => { view.grid.visible = !view.grid.visible; }, 'G'], ['Frame Bunny', frameBunny, 'F']]],
  ['Camera', [...LENSES.map(l => [`${l} mm lens`, () => camSet({ lens: l })]), '-', ...VIEWS.map(([n, c]) => [n, () => camSet(c)]), '-', ['Dolly zoom: wide, keep size', () => dollyTo(18)], ['Dolly zoom: long, keep size', () => dollyTo(100)]]],
  ['Help', [['Controls and shortcuts', showHelp, 'F1']]],
];

function buildMenu() {
  const bar = $('#menubar');
  bar.replaceChildren();
  for (const [name, items] of MENUS) {
    const list = h('div', { class: 'menu-list', role: 'menu' });
    for (const it of items) {
      if (it === '-') { list.append(h('hr')); continue; }
      const [label, fn, key] = it;
      list.append(h('button', { role: 'menuitem', onclick: () => { closeMenus(); fn(); } }, h('span', {}, label), key ? h('kbd', {}, key) : null));
    }
    const btn = h('button', { 'aria-haspopup': 'true', 'aria-expanded': 'false', onclick: e => { const m = e.currentTarget.parentElement; const open = !m.classList.contains('open'); closeMenus(); if (open) { m.classList.add('open'); e.currentTarget.setAttribute('aria-expanded', 'true'); } } }, name);
    bar.append(h('div', { class: 'menu' }, btn, list));
  }
  bar.append(h('div', { class: 'spacer' }), h('span', { class: 'status', id: 'status' }, ''));
  document.addEventListener('pointerdown', e => { if (!e.target.closest('#menubar')) closeMenus(); });
}
function closeMenus() { document.querySelectorAll('#menubar .menu.open').forEach(m => { m.classList.remove('open'); m.querySelector('button').setAttribute('aria-expanded', 'false'); }); }

// ---------------------------------------------------------------- side panel
const TABS = [['pose', 'Pose'], ['face', 'Face'], ['library', 'Library'], ['camera', 'Camera'], ['carousel', 'Carousel'], ['render', 'Render']];
function buildTabs() {
  $('#tabs').replaceChildren(...TABS.map(([id, name]) => h('button', { role: 'tab', 'aria-pressed': String(tab === id), onclick: () => { tab = id; buildTabs(); buildPanel(); layout(); overlayDraw?.(); } }, name)));
}

function control(id) {
  const [lo, hi, step] = range(id);
  const v = current(id);
  const slider = h('input', { type: 'range', min: lo, max: hi, step, value: v, 'aria-label': LABEL[id] || id });
  const num = h('input', { type: 'number', min: lo, max: hi, step, value: round(v), 'aria-label': (LABEL[id] || id) + ' value' });
  const dot = h('span', { class: 'keydot', title: 'Key this value at the playhead (click again to remove the key)' });
  slider.addEventListener('pointerdown', () => pushUndo());
  slider.addEventListener('input', () => { setValue(id, Number(slider.value)); num.value = round(Number(slider.value)); });
  num.addEventListener('change', () => { pushUndo(); setValue(id, Number(num.value)); });
  dot.addEventListener('click', () => {
    pushUndo();
    if (hasKey(project, id, frame)) deleteKey(project, id, frame); else setKey(project, id, frame, current(id));
    delete preview[id]; apply(); drawTracks();
  });
  const row = h('label', { class: 'ctl', 'data-id': id, title: TIPS[id] || '' }, h('span', { class: 'name' }, dot, LABEL[id] || id), slider, num);
  return row;
}
const round = v => Math.round(v * 100) / 100;

function buildPanel() {
  const c = $('#panel-content');
  c.replaceChildren();
  if (tab === 'pose') {
    const parts = shownParts();
    if (!parts.some(p => p[0] === part)) part = 'whole';
    c.append(h('div', { class: 'chips' }, ...parts.map(([id, name]) => h('button', { 'aria-pressed': String(part === id), onclick: () => { part = id; buildPanel(); } }, name))));
    const ids = PARTS.find(p => p[0] === part)[2];
    c.append(h('h3', {}, PARTS.find(p => p[0] === part)[1]), ...ids.map(control));
    c.append(h('div', { class: 'row', style: 'margin-top:10px' },
      h('button', { onclick: () => keyGroup(ids), title: 'Set a key on every control of this part' }, 'Key this part'),
      h('button', { onclick: () => { pushUndo(); for (const id of ids) setValue(id, defaults(id)); }, title: 'Back to rest for this part' }, 'Reset this part'),
      h('button', { onclick: () => { pushUndo(); for (const id of BUNNY_IDS) setValue(id, defaults(id)); }, title: 'Back to rest for the whole body' }, 'Reset whole pose')));
    c.append(h('p', { class: 'hint' }, `Every joint stops at the ${charName()}'s limits, so nothing can bend past its anatomy. Left and right follow Doodle Studio.${part === 'ears' && data.ear_width_lock ? ' The Frog\'s eye bumps are rigid, so they grow and squash only a little.' : ''}`));
  } else if (tab === 'face') {
    const F = data.face;
    const sel = (id, names) => {
      const s = h('select', { 'aria-label': LABEL[id] }, ...names.map((n, i) => h('option', { value: i }, n)));
      s.value = String(Math.round(current(id)));
      s.addEventListener('change', () => { pushUndo(); setValue(id, Number(s.value)); drawTracks(); });
      return h('label', { class: 'ctl', 'data-id': id, style: 'grid-template-columns:8.5em 1fr' }, LABEL[id], s);
    };
    c.append(h('h3', {}, 'Face'), sel('expression', F.faces), sel('mouth', F.speech.map((n, i) => i === 0 ? 'None (expression mouth)' : n)),
      sel('blink', ['Open', 'Half', 'Closed', 'Squeeze', 'Wink']));
    const pad = h('div', { class: 'gaze' }, ...GAZE_ORDER.map(i => h('button', { 'aria-pressed': String(Math.round(current('gaze')) === i), title: F.gazes[i], onclick: () => { pushUndo(); setValue('gaze', i); buildPanel(); drawTracks(); } }, F.gazes[i].replace('Center', '•').replace(/Up|Down|Left|Right/g, m => ({ Up: '↑', Down: '↓', Left: '←', Right: '→' })[m]).replace(' ', ''))));
    c.append(h('h3', {}, 'Gaze'), pad);
    c.append(h('p', { class: 'hint' }, 'Faces are Doodle Studio\'s own drawings, wrapped on the head. Eyes and mouth keep a constant size.'));
    c.append(idlePanel());
  } else if (tab === 'camera') {
    c.append(h('h3', {}, 'Lens'), h('div', { class: 'chips' }, ...LENSES.map(l => h('button', { 'aria-pressed': String(Math.round(current('cam.lens')) === l), onclick: () => camSet({ lens: l }) }, `${l} mm`)),
      h('button', { onclick: () => dollyTo(18), title: 'Dolly zoom: go wide while moving in, so Bunny keeps his size and the room stretches' }, 'Dolly wide'),
      h('button', { onclick: () => dollyTo(100), title: 'Dolly zoom: go long while moving out, so Bunny keeps his size and the room flattens' }, 'Dolly long')));
    c.append(h('h3', {}, 'Angle'), h('div', { class: 'chips' }, ...VIEWS.map(([n, v]) => h('button', { onclick: () => camSet(v) }, n))));
    c.append(h('h3', {}, 'Camera'), ...CAM_IDS.map(control));
    c.append(h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: () => keyGroup(CAM_IDS) }, 'Key camera'), h('button', { onclick: frameBunny }, 'Frame Bunny')));
    c.append(h('p', { class: 'hint' }, 'Drag in the viewport to orbit, Shift+drag to move the aim, wheel to move in and out, Alt+wheel to change the lens. The set moves with the camera, so angles stay physically true.'));
    c.append(cameraPresetsPanel(presetCtx()));
  } else if (tab === 'library') {
    c.append(libraryPanel(libCtx()));
  } else if (tab === 'carousel') {
    c.append(carouselPanel(carCtx()));
  } else if (tab === 'render') {
    const field = (label, obj, key, attrs) => { const i = h('input', { ...attrs, value: obj[key] }); i.addEventListener('change', () => { pushUndo(); obj[key] = attrs.type === 'number' ? Number(i.value) : i.value; buildTimelineTools(); drawTracks(); updateHud(); }); return h('label', { class: 'ctl', style: 'grid-template-columns:8.5em 1fr' }, label, i); };
    c.append(h('h3', {}, `Shot ${project.code}`), field('Name', project, 'label', { type: 'text', placeholder: 'optional, e.g. intro' }), field('Length (frames)', project, 'length', { type: 'number', min: 1, max: 54000 }),
      h('h3', {}, `Scene: ${scene.shots.length} shot${scene.shots.length > 1 ? 's' : ''}, ${(sceneFrames() / scene.fps).toFixed(1)} s`),
      field('Frame rate', scene, 'fps', { type: 'number', min: 12, max: 60 }),
      field('Width (px)', scene, 'width', { type: 'number', min: 64, max: 3840 }), field('Height (px)', scene, 'height', { type: 'number', min: 64, max: 3840 }));
    c.append(h('div', { class: 'chips', style: 'margin:6px 0' }, ...[['Reel 9:16', 1080, 1920], ['YouTube 16:9', 1920, 1080], ['Square 1:1', 1080, 1080]].map(([n, w, hh]) =>
      h('button', { 'aria-pressed': String(project.width === w && project.height === hh), onclick: () => { pushUndo(); project.width = w; project.height = hh; layout(); buildPanel(); } }, n))));
    c.append(h('h3', {}, 'Blender render'), h('p', { class: 'hint' }, 'Renders run in the background in Blender: hoodie cloth, ear and tail springs, the collision solver, then the 3D rule checks. Render scene renders every shot in order and joins them into one video; shots that have not changed since their last render are reused. Everything goes to DeepInDoodles\\<scene>\\work: videos in renders, logs and rule reports in checks. Only the approved final goes at the top.'),
      h('div', { class: 'row' }, h('button', { class: 'primary', onclick: () => renderScene() }, 'Render scene'), h('button', { onclick: () => render() }, `Render ${project.code}`),
        h('button', { onclick: () => render(true) }, 'This frame')),
      h('div', { class: 'row', style: 'margin-top:6px' }, h('button', { onclick: () => renderScene(true), title: 'Every shot at half size without cloth: a fast check of timing and cuts' }, 'Quick preview scene'),
        h('button', { onclick: () => render(false, true), title: 'This shot at half size without cloth' }, 'Quick preview shot'), h('button', { onclick: cancelRender }, 'Cancel')),
      h('div', { id: 'render-status', class: 'hint' }, ''), h('h3', {}, 'Blender location'), h('div', { class: 'row' }, h('span', { id: 'blender-path', class: 'hint', style: 'flex:1;overflow-wrap:anywhere' }, '…'),
        h('button', { onclick: pickBlender }, 'Change…')));
    api('settings', {}).then(s => { const el = $('#blender-path'); if (el) el.textContent = s.blenderFound || 'Not found. Install Blender 4.5 LTS, or point to blender.exe.'; }).catch(() => {});
    pollRender();
  }
}

function syncPanel() {
  for (const row of document.querySelectorAll('#panel-content .ctl[data-id]')) {
    const id = row.dataset.id, v = current(id);
    const slider = row.querySelector('input[type=range]'), num = row.querySelector('input[type=number]'), s = row.querySelector('select');
    if (slider && document.activeElement !== slider) slider.value = v;
    if (num && document.activeElement !== num) num.value = round(v);
    if (s && document.activeElement !== s) s.value = String(Math.round(v));
    const dot = row.querySelector('.keydot');
    if (dot) { dot.classList.toggle('has', !!project.tracks[id]); dot.classList.toggle('on', hasKey(project, id, frame)); }
  }
}

// ---------------------------------------------------------------- idle life (idle.js)
// Auto blink and auto ear twitch belong to the shot (saved with it, part of its render
// cache key). The seed makes every render of the shot blink at the same moments.
function setIdle(patch, all = false) {
  pushUndo();
  for (const s of all ? scene.shots : [project]) {
    const o = { ...idleOf(s), ...patch };
    for (const [k, [lo, hi]] of Object.entries(IDLE_RANGE)) o[k] = Math.max(lo, Math.min(hi, Number(o[k]) || IDLE_DEFAULT[k]));
    o.seed = Math.round(o.seed);
    s.idle = o;
  }
  apply(); drawTracks();
  if (tab === 'face') buildPanel();
}
function idlePanel() {
  const o = idleOf(project), frog = character() === 'frog';
  const twitchName = frog ? 'Auto eye-bump twitch' : 'Auto ear twitch';
  const every = (key, tip) => {
    const [lo, hi] = IDLE_RANGE[key];
    const i = h('input', { type: 'number', min: lo, max: hi, step: 0.5, value: o[key], style: 'width:58px', 'aria-label': tip });
    i.addEventListener('change', () => setIdle({ [key]: Number(i.value) }));
    return h('span', { class: 'row', title: tip }, 'about every', i, 's');
  };
  const toggle = (key, label, tip) => h('button', { 'aria-pressed': String(!!o[key]), title: tip, style: 'min-width:10.5em', onclick: () => setIdle({ [key]: !o[key] }) }, label);
  const seed = h('input', { type: 'number', min: 1, max: 9999, step: 1, value: o.seed, style: 'width:64px', 'aria-label': 'Seed' });
  seed.addEventListener('change', () => setIdle({ seed: Number(seed.value) }));
  const n = idleNow()?.events || [];
  const count = k => n.filter(e => e.kind === k).length;
  return h('div', {},
    h('h3', {}, 'Idle life'),
    h('div', { class: 'row' }, toggle('blink', 'Auto blink', 'Blinks on his own at natural, random moments for the whole shot. Keyed blinks always win.'),
      every('blinkEvery', 'Average time between blinks. Each gap is randomised around it, with the odd double blink and a blink on big head turns.')),
    h('div', { class: 'row', style: 'margin-top:4px' }, toggle('twitch', twitchName, frog ? 'The eye bumps pop up and settle now and then. Adds to any keyed bump moves.' : 'An ear flicks outward and springs back now and then, one ear or both. Adds to the keyed ear angles and never pulls the ears together.'),
      every('twitchEvery', 'Average time between twitches. Each gap is randomised around it.')),
    h('div', { class: 'row', style: 'margin-top:4px' }, h('span', { title: 'Same seed, same blinks: every render of this shot repeats exactly. Change it to reshuffle the timing.' }, 'Seed'), seed,
      h('button', { title: 'Reshuffle when the blinks and twitches happen', onclick: () => setIdle({ seed: 1 + Math.floor(Math.random() * 9999) }) }, 'New seed'),
      h('button', { title: 'Copy these idle settings to every shot of the scene (each shot still gets its own timing)', onclick: () => { setIdle({ ...o }, true); toast(`Idle life set on all ${scene.shots.length} shots`); } }, 'Use on every shot')),
    h('p', { class: 'hint' }, (o.blink || o.twitch) ? `This shot: ${count('blink')} blink${count('blink') === 1 ? '' : 's'}, ${count('twitch')} twitch${count('twitch') === 1 ? '' : 'es'}. They show on the Idle life row of the timeline and in the viewport, and render exactly the same in Blender. No blinks on faces with closed or special eyes.` : 'Off. Turn one on and it keeps happening through the whole shot.'));
}

// ---------------------------------------------------------------- camera helpers
function camSet(c) { pushUndo(); for (const [k, v] of Object.entries(c)) setValue('cam.' + k, v); buildPanel(); }
function dollyTo(lens) {
  // keep Bunny's size on screen: distance scales with focal length
  const l0 = current('cam.lens'), d0 = current('cam.dist');
  camSet({ lens, dist: Math.max(0.4, d0 * lens / l0) });
}
// camera-presets.js reaches the active shot through this
const presetCtx = () => ({ view, project: () => project, frame: () => frame, current, setValue, pushUndo, toast, refresh: () => { apply(); drawTracks(); } });
function frameBunny() { camSet({ tx: 0, ty: 0, tz: 0.52, dist: 3.0 * current('cam.lens') / 50 }); }

// ---------------------------------------------------------------- viewport interaction
function bindViewport() {
  const cv = $('#view');
  let drag = null;
  cv.addEventListener('pointerdown', e => { cv.setPointerCapture(e.pointerId); cv.classList.add('dragging'); pushUndo(); drag = { x: e.clientX, y: e.clientY, shift: e.shiftKey, cam: Object.fromEntries(CAM_IDS.map(id => [id, current(id)])) }; });
  cv.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (drag.shift) {
      const d = drag.cam['cam.dist'], yaw = drag.cam['cam.yaw'] * Math.PI / 180, k = d / cv.clientHeight * 0.8;
      setValue('cam.tx', drag.cam['cam.tx'] - dx * k * Math.cos(yaw));
      setValue('cam.ty', drag.cam['cam.ty'] - dx * k * Math.sin(yaw));
      setValue('cam.tz', drag.cam['cam.tz'] + dy * k);
    } else {
      setValue('cam.yaw', drag.cam['cam.yaw'] - dx * 0.4);
      setValue('cam.pitch', drag.cam['cam.pitch'] + dy * 0.3);
    }
  });
  const end = () => { if (drag) { drag = null; cv.classList.remove('dragging'); drawTracks(); } };
  cv.addEventListener('pointerup', end);
  cv.addEventListener('pointercancel', end);
  cv.addEventListener('wheel', e => {
    e.preventDefault();
    pushUndo();
    if (e.altKey) setValue('cam.lens', Math.round(current('cam.lens') * Math.exp(-e.deltaY * 0.001)));
    else setValue('cam.dist', current('cam.dist') * Math.exp(e.deltaY * 0.001));
    drawTracks();
  }, { passive: false });
}

function buildRail() {
  $('#rail').replaceChildren(
    h('button', { title: 'Frame Bunny (F)', onclick: frameBunny }, icon('frame'), 'Frame'),
    h('button', { title: 'Floor grid (G)', onclick: () => { view.grid.visible = !view.grid.visible; } }, icon('grid'), 'Grid'));
}

function layout() {
  const wrap = $('#canvas-wrap'), fr = $('#frame');
  const W = wrap.clientWidth - 24, H = wrap.clientHeight - 24;
  const [aw, ah] = tab === 'carousel' ? SIZES[carouselOf(scene).size] : [scene.width, scene.height];
  const ar = aw / ah;
  let w = W, hh = W / ar;
  if (hh > H) { hh = H; w = H * ar; }
  fr.style.width = Math.floor(w) + 'px';
  fr.style.height = Math.floor(hh) + 'px';
  view.resize(Math.floor(w), Math.floor(hh));
}

function updateHud() {
  const st = stageOf(scene, project), setName = st.set && (libraryRows().find(r => r.category === 'set' && (r.data?.room === st.set))?.name || st.set);
  $('#hud').replaceChildren(h('span', {}, charName() + (setName ? ' · ' + setName : '') + (st.outfit ? ' · ' + st.outfit : '') + (project.items?.length ? ` · ${project.items.length} item${project.items.length > 1 ? 's' : ''}` : '')),
    h('span', {}, `${Math.round(current('cam.lens'))} mm`), h('span', {}, tab === 'carousel' ? `Carousel ${SIZES[carouselOf(scene).size].join('×')}` : `${project.width}×${project.height}`),
    h('span', {}, `F${frame}`));
  $('#status').textContent = (filePath ? filePath.split(/[\\/]/).pop() : 'Not saved') + (dirty ? ' •' : '');
}

// ---------------------------------------------------------------- timeline
function buildTimelineTools() {
  const g = (name, ...kids) => h('div', { class: 'ux-group' }, h('span', { class: 'ux-group-name' }, name), ...kids);
  const ib = (n, title, fn, id) => h('button', { class: 'icon', title, 'aria-label': title, onclick: fn, id }, icon(n));
  const box = h('input', { id: 'frame-box', type: 'number', min: 0, title: 'Current frame' });
  box.addEventListener('change', () => goto(Number(box.value)));
  const ease = h('select', { id: 'ease-select', title: 'Easing from the selected key to the next one' }, ...Object.entries(EASES).map(([k, n]) => h('option', { value: k }, n)));
  ease.addEventListener('change', () => { if (!selected) return toast('Select a key first'); pushUndo(); const k = project.tracks[selected.id]?.find(k => k.f === selected.f); if (k) k.ease = ease.value; apply(); });
  const chips = scene.shots.map((s, i) => h('button', { class: 'shot-chip', 'aria-pressed': String(i === scene.active), title: `${shotName(s)}: ${(s.length / scene.fps).toFixed(1)} s. Click to edit, double-click to name.`,
    onclick: () => selectShot(i), ondblclick: () => labelShot(i) }, shotName(s), h('small', {}, ` ${(s.length / scene.fps).toFixed(1)}s`)));
  $('#timeline-tools').replaceChildren(
    g('Scene', ...chips, h('button', { onclick: () => addShot(false), title: 'Add a shot after this one (Ctrl+T)' }, '+ Shot'),
      h('button', { onclick: () => addShot(true), title: 'Duplicate this shot (Ctrl+Shift+T)' }, 'Duplicate'),
      ib('prev', 'Move this shot earlier (Alt+←)', () => moveShot(-1)), ib('next', 'Move this shot later (Alt+→)', () => moveShot(1)),
      ib('trash', 'Delete this shot', () => deleteShot())),
    g('Play', ib('start', 'First frame (Home)', () => goto(0)), ib('prev', 'Previous frame (←)', () => goto(frame - 1)), ib('play', 'Play / pause (Space)', togglePlay, 'play-btn'),
      ib('next', 'Next frame (→)', () => goto(frame + 1)), ib('end', 'Last frame (End)', () => goto(project.length - 1)), box, h('span', { class: 'clock', id: 'clock' })),
    g('Keys', h('button', { onclick: () => keyGroup(BUNNY_IDS.concat(FACE_IDS)), title: 'Key Bunny\'s whole pose and face (K)' }, 'Key pose'),
      h('button', { onclick: () => keyGroup(CAM_IDS), title: 'Key the camera (Shift+K)' }, 'Key camera'),
      ib('trash', 'Delete selected key (Delete)', deleteSelected), ease),
    g('Edit', h('button', { onclick: undo, title: 'Undo (Ctrl+Z)' }, 'Undo'), h('button', { onclick: redo, title: 'Redo (Ctrl+Shift+Z)' }, 'Redo')));
}

const pxPerFrame = () => Math.max(3, ($('#tracks').clientWidth - 170) / Math.max(1, project.length));

function drawTracks() {
  const box = $('#tracks');
  const ppf = pxPerFrame();
  const lane = (kids = []) => h('div', { class: 'lane' }, ...kids);
  const ruler = lane();
  const step = project.fps;
  for (let f = 0; f <= project.length; f += step) ruler.append(h('div', { class: 'tick', style: `left:${f * ppf}px` }, `${f / project.fps}s`));
  ruler.addEventListener('pointerdown', e => {
    const r = ruler.getBoundingClientRect();
    const go = ev => goto(Math.round((ev.clientX - r.left) / ppf));
    go(e);
    const mv = ev => go(ev), up = () => { removeEventListener('pointermove', mv); removeEventListener('pointerup', up); };
    addEventListener('pointermove', mv); addEventListener('pointerup', up);
  });
  const rows = [h('div', { class: 'ruler' }, h('div', { class: 'tname' }, 'TIME'), ruler)];
  const groups = [['Bunny', BUNNY_IDS.concat(FACE_IDS)], ['Camera', CAM_IDS]];
  for (const [gname, ids] of groups) {
    const keyed = ids.filter(id => project.tracks[id]);
    rows.push(h('div', { class: 'trow' }, h('div', { class: 'tname group' }, gname), lane(summaryKeys(keyed, ppf))));
    const idle = gname === 'Bunny' && idleNow();
    if (idle) rows.push(h('div', { class: 'trow' }, h('div', { class: 'tname', title: 'Auto blinks (top) and twitches (bottom). Click one to go there; settings are on the Face tab.' }, 'Idle life'),
      lane(idle.events.map(e => h('div', { class: 'idle-mark ' + e.kind, style: `left:${e.f * ppf + 2}px`, title: `${e.kind === 'blink' ? 'Blink' + (e.why === 'turn' ? ' on a head turn' : e.why === 'double' ? ' (double)' : '') : 'Twitch ' + (e.sides === 'LR' ? 'both' : e.sides === 'L' ? 'left' : 'right')} at frame ${e.f}`, onclick: () => goto(e.f) })))));
    for (const id of keyed) {
      const nm = (PARTS.find(p => p[2].includes(id) && p[0] !== 'whole')?.[1] || (id.startsWith('cam.') ? '' : '')) ;
      rows.push(h('div', { class: 'trow' }, h('div', { class: 'tname', title: id }, (nm ? nm + ' · ' : '') + (LABEL[id] || id)),
        lane(project.tracks[id].map(k => keyEl(id, k, ppf)))));
    }
  }
  const ph = h('div', { id: 'playhead' });
  box.replaceChildren(...rows, ph);
  drawPlayhead();
}

function summaryKeys(ids, ppf) {
  const fs = new Set();
  for (const id of ids) for (const k of project.tracks[id]) fs.add(k.f);
  return [...fs].map(f => h('div', { class: 'key', style: `left:${f * ppf + 2}px;opacity:.55`, title: `Frame ${f}`, onclick: () => goto(f) }));
}

function keyEl(id, k, ppf) {
  const el = h('div', { class: 'key' + (selected && selected.id === id && selected.f === k.f ? ' sel' : ''), style: `left:${k.f * ppf + 2}px`, title: `${LABEL[id] || id}: ${round(k.v)} at frame ${k.f} (${EASES[k.ease || 'ease']}). Drag to move.` });
  el.addEventListener('pointerdown', e => {
    e.stopPropagation();
    selected = { id, f: k.f };
    $('#ease-select').value = k.ease || 'ease';
    const x0 = e.clientX, f0 = k.f;
    let moved = false;
    pushUndo();
    const mv = ev => {
      const nf = Math.max(0, Math.min(project.length - 1, f0 + Math.round((ev.clientX - x0) / ppf)));
      if (nf !== k.f && !project.tracks[id].some(o => o !== k && o.f === nf)) { k.f = nf; project.tracks[id].sort((a, b) => a.f - b.f); selected.f = nf; moved = true; el.style.left = `${nf * ppf + 2}px`; }
    };
    const up = () => { removeEventListener('pointermove', mv); removeEventListener('pointerup', up); if (!moved) undoStack.pop(); goto(k.f); drawTracks(); };
    addEventListener('pointermove', mv); addEventListener('pointerup', up);
  });
  return el;
}

function drawPlayhead() {
  const ph = $('#playhead');
  if (ph) ph.style.left = `${170 + frame * pxPerFrame() + 2}px`;
  const box = $('#frame-box');
  if (box && document.activeElement !== box) box.value = frame;
  const clk = $('#clock');
  if (clk) clk.textContent = `${(frame / project.fps).toFixed(2)} s / ${(project.length / project.fps).toFixed(1)} s`;
}

function goto(f) {
  frame = Math.max(0, Math.min(project.length - 1, Math.round(f)));
  for (const k of Object.keys(preview)) delete preview[k];
  apply();
}

function keyGroup(ids) {
  pushUndo();
  for (const id of ids) setKey(project, id, frame, current(id));
  for (const id of ids) delete preview[id];
  apply(); drawTracks();
  toast(`Keyed ${ids.length} values at frame ${frame}`);
}

function deleteSelected() {
  if (!selected) return toast('Select a key first');
  pushUndo(); deleteKey(project, selected.id, selected.f); selected = null; apply(); drawTracks();
}
function clearAll() { if (!confirm(`Clear every key in ${project.code}?`)) return; pushUndo(); project.tracks = {}; apply(); drawTracks(); }

let last = 0;
function togglePlay() {
  playing = !playing;
  $('#play-btn').replaceChildren(icon(playing ? 'pause' : 'play'));
  if (playing) { last = performance.now(); requestAnimationFrame(tick); }
}
function tick(t) {
  if (!playing) return;
  const adv = (t - last) * project.fps / 1000;
  if (adv >= 1) { last += Math.floor(adv) * 1000 / project.fps; frame = (frame + Math.floor(adv)) % project.length; for (const k of Object.keys(preview)) delete preview[k]; apply(); }
  requestAnimationFrame(tick);
}

// ---------------------------------------------------------------- files
function newShot() { if (dirty && !confirm('Discard unsaved changes?')) return; filePath = null; undoStack = []; redoStack = []; dirty = false; frame = 0; useScene(newScene()); }
async function saveShot(as, auto = false) {
  try {
    scene.name = $('#shot-name').value || scene.name;
    const r = await api('save', { project: scene, path: as ? null : filePath, auto });
    if (r.path) { filePath = r.path; dirty = false; toast('Saved ' + r.path.split(/[\\/]/).pop()); updateHud(); }
    return r;
  } catch (e) { toast('Could not save: ' + e.message, 4000); throw e; }
}
async function openShot() {
  try {
    const r = await api('open', {});
    if (!r.project) return;
    filePath = r.path; undoStack = []; redoStack = []; dirty = false; frame = 0; useScene(migrate(r.project));
  } catch (e) { toast('Could not open: ' + e.message, 4000); }
}
async function exportBridge() {
  try { const r = await api('export-bridge', { shot: bridge(project), name: scene.name, code: project.code }); if (r.path) toast('Wrote ' + r.path); }
  catch (e) { toast('Could not export: ' + e.message, 4000); }
}
const ALL_IDS = () => BUNNY_IDS.concat(FACE_IDS, CAM_IDS);
const character = () => scene.character || 'bunny';
const bridge = s => toBridgeShot(s, ALL_IDS(), data.face.faces, character(), stageOf(scene, s));
const idleNow = () => idleFor(project, data.face.faces, character());
async function render(still = false, preview = false, stillFrame = null) {
  scene.name = $('#shot-name').value || scene.name;
  try {
    const r = await api('render', { name: scene.name, code: project.code, still: still ? (stillFrame ?? frame) + 1 : null, preview, audio: project.audio?.path || null, shot: bridge(project) });
    toast(r.message || 'Render started');
    pollRender();
    return r;
  } catch (e) { toast('Render failed to start: ' + e.message, 5000); throw e; }
}
async function renderScene(preview = false) {
  scene.name = $('#shot-name').value || scene.name;
  try {
    const shots = scene.shots.map(s => ({ code: s.code, audio: s.audio?.path || null, shot: bridge(bindShot(scene, s)) }));
    const r = await api('render-scene', { name: scene.name, fps: scene.fps, width: scene.width, height: scene.height, audio: scene.audio?.path || null, preview, shots });
    toast(r.message || 'Scene render started');
    pollRender();
    return r;
  } catch (e) { toast('Scene render failed to start: ' + e.message, 5000); throw e; }
}
let pollTimer = null;
async function pollRender() {
  clearTimeout(pollTimer);
  try {
    const s = await api('render-status');
    const text = s.state === 'idle' ? (lastRender ? `Last render: ${lastRender.id}, ${lastRender.state}${lastRender.rules ? ', rules ' + lastRender.rules : ''}` : 'No render running.')
      : `${s.id}${s.step ? ' (' + s.step + ')' : ''}: frame ${s.frame} of ${s.frames}${s.eta != null ? `, about ${Math.ceil(s.eta / 60)} min left` : ''}${s.queued ? ` (${s.queued} queued)` : ''}`;
    const el = $('#render-status'); if (el) el.textContent = text;
    $('#status').textContent = s.state === 'idle' ? $('#status').textContent : `Rendering ${s.frame}/${s.frames}`;
    if (s.state !== 'idle') pollTimer = setTimeout(pollRender, 1000); else updateHud();
  } catch {}
}
let lastRender = null;
window.ds3dRenderDone = j => { lastRender = j; if (j.kind === 'carousel' && j.state === 'done') finishCarousel(carCtx(), j).catch(e => toast('Could not add the bubbles: ' + e.message, 5000)); toast(`${j.id}: ${j.state}${j.rules ? ' · rules ' + j.rules : ''}`, 5000); pollRender(); };
async function cancelRender() { try { toast((await api('render-cancel', {})).message); } catch (e) { toast(e.message); } }
async function pickBlender() { try { const r = await api('pick-blender', {}); const el = $('#blender-path'); if (el) el.textContent = r.blender || 'Not found'; } catch (e) { toast(e.message); } }
window.ds3dRequestClose = () => !dirty || confirm('This scene has unsaved changes. Close anyway?');

function toggleDark() {
  const dark = document.body.dataset.theme !== 'dark';
  document.body.dataset.theme = dark ? 'dark' : 'light';
  try { localStorage.setItem('ds3d.theme', dark ? 'dark' : 'light'); } catch {}
}

function showHelp() {
  const d = h('dialog', {}, h('h2', {}, 'Controls'), h('p', { class: 'hint' },
    'Viewport: drag to orbit, Shift+drag to move the aim, wheel to dolly, Alt+wheel for the lens. Space plays. ← → step frames. K keys the pose, Shift+K keys the camera. Delete removes the selected key. Ctrl+Z / Ctrl+Shift+Z undo and redo. Ctrl+S saves. Ctrl+D switches dark mode.'),
    h('p', { class: 'hint' }, 'Idle life (Face tab): Auto blink and Auto ear twitch keep him alive through the whole shot at natural, random moments. Same seed, same render. Keyed blinks and ear moves always win.'),
    h('button', { onclick: () => d.close() }, 'Close'));
  document.body.append(d); d.showModal();
}

function bindKeys() {
  addEventListener('keydown', e => {
    if (e.target.matches('input,select,textarea')) return;
    const k = e.key, c = e.ctrlKey || e.metaKey;
    if (c && k.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo(); }
    else if (c && k.toLowerCase() === 's') { e.preventDefault(); saveShot(e.shiftKey); }
    else if (c && k.toLowerCase() === 'o') { e.preventDefault(); openShot(); }
    else if (c && k.toLowerCase() === 'd') { e.preventDefault(); toggleDark(); }
    else if (c && k.toLowerCase() === 'r') { e.preventDefault(); render(e.shiftKey); }
    else if (c && e.shiftKey && k.toLowerCase() === 'e') { e.preventDefault(); renderScene(); }
    else if (c && k.toLowerCase() === 't') { e.preventDefault(); addShot(e.shiftKey); }
    else if (e.altKey && k === 'ArrowLeft') { e.preventDefault(); moveShot(-1); }
    else if (e.altKey && k === 'ArrowRight') { e.preventDefault(); moveShot(1); }
    else if (k === 'PageUp') { e.preventDefault(); selectShot(Math.max(0, scene.active - 1)); }
    else if (k === 'PageDown') { e.preventDefault(); selectShot(Math.min(scene.shots.length - 1, scene.active + 1)); }
    else if (k === ' ') { e.preventDefault(); togglePlay(); }
    else if (k === 'ArrowLeft') goto(frame - 1);
    else if (k === 'ArrowRight') goto(frame + 1);
    else if (k === 'Home') goto(0);
    else if (k === 'End') goto(project.length - 1);
    else if (k.toLowerCase() === 'k') e.shiftKey ? keyGroup(CAM_IDS) : keyGroup(BUNNY_IDS.concat(FACE_IDS));
    else if (k === 'Delete' || k === 'Backspace') deleteSelected();
    else if (k.toLowerCase() === 'f') frameBunny();
    else if (k.toLowerCase() === 'g') view.grid.visible = !view.grid.visible;
    else if (k === 'F1') { e.preventDefault(); showHelp(); }
  });
}

function refreshAll() {
  $('#shot-name').value = scene.name;
  layout(); buildPanel(); buildTimelineTools(); drawTracks(); apply();
}

function loop() { view.render(); requestAnimationFrame(loop); }

// ---------------------------------------------------------------- boot
(async () => {
  try { if (localStorage.getItem('ds3d.theme') === 'dark') document.body.dataset.theme = 'dark'; } catch {}
  data = charData.bunny = await (await fetch('bunny3d.json')).json();
  view = new Viewport($('#view'), data);
  BUNNY_IDS = PARTS.flatMap(p => p[2]);
  buildMenu(); buildTabs(); buildRail(); bindViewport(); bindKeys(); bindCameraPresets(presetCtx());
  overlayDraw = bindOverlay(carCtx());
  $('#auto-key').addEventListener('click', e => { autoKey = !autoKey; e.currentTarget.setAttribute('aria-pressed', String(autoKey)); e.currentTarget.textContent = autoKey ? 'Auto' : 'Manual'; });
  $('#render-btn').addEventListener('click', () => renderScene());
  $('#shot-name').addEventListener('change', e => { scene.name = e.target.value; dirty = true; });
  new ResizeObserver(() => { if (!window.__fixedSize) { layout(); drawTracks(); } }).observe($('#canvas-wrap'));
  refreshAll();
  window.ds3dLibraryExtra = () => EXTRA.map(({ ask, def, ...r }) => r);
  window.ds3d = {
    get project() { return project; }, get scene() { return scene; }, set scene(s) { useScene(migrate(s)); }, goto, setValue, keyGroup, view, get frame() { return frame; },
    // MCP surface (called by the desktop host)
    controls: () => [...BUNNY_IDS, ...FACE_IDS, ...CAM_IDS].map(id => {
      const [min, max] = DISCRETE.has(id) ? [0, ({ expression: data.face.faces.length, gaze: data.face.gazes.length, mouth: data.face.speech.length, blink: 5 })[id] - 1] : range(id);
      return { id, label: LABEL[id] || id, min, max, group: id.startsWith('cam.') ? 'camera' : FACE_IDS.includes(id) ? 'face' : PARTS.find(p => p[2].includes(id))?.[1] };
    }),
    names: () => ({ expressions: data.face.faces, gazes: data.face.gazes, mouths: data.face.speech }),
    state: () => ({ scene: scene.name, character: character(), stage: stageOf(scene, project), items: project.items || [], shot: project.code, shotName: project.label, shots: scene.shots.map((s, i) => ({ index: i, code: s.code, name: s.label, length: s.length, active: i === scene.active })),
      frame, length: project.length, fps: scene.fps, width: scene.width, height: scene.height, autoKey, file: filePath, unsaved: dirty,
      values: Object.fromEntries([...BUNNY_IDS, ...FACE_IDS, ...CAM_IDS].map(id => [id, round(current(id))])),
      idle: { ...idleOf(project), events: idleNow()?.events || [] },
      keyed: Object.fromEntries(Object.entries(project.tracks).map(([id, ks]) => [id, ks.map(k => [k.f, round(k.v), k.ease])])) }),
    setValues(values, at, key) {
      pushUndo();
      if (at != null) goto(at);
      const was = autoKey; if (key != null) autoKey = !!key;
      try { for (const [id, v] of Object.entries(values)) setValue(id, Number(v)); } finally { autoKey = was; }
      drawTracks(); buildPanel();
      return this.state();
    },
    key(ids, at) { if (at != null) goto(at); keyGroup(ids && ids.length ? ids : BUNNY_IDS.concat(FACE_IDS)); return this.state(); },
    deleteKey(id, at) { pushUndo(); deleteKey(project, id, at); apply(); drawTracks(); return this.state(); },
    setEase(id, at, ease) { pushUndo(); const k = project.tracks[id]?.find(k => k.f === at); if (!k) throw Error(`No key on ${id} at frame ${at}`); k.ease = ease; apply(); return this.state(); },
    setShot(p) {
      pushUndo();
      if (p.scene != null) scene.name = String(p.scene);
      if (p.name != null) project.label = String(p.name);
      for (const k of ['length', 'fps', 'width', 'height']) if (p[k] != null) project[k] = Number(p[k]);
      refreshAll(); return this.state();
    },
    addShot(duplicate) { addShot(!!duplicate); return this.state(); },
    setIdle(p = {}) {
      const { allShots, ...patch } = p;
      for (const k of Object.keys(patch)) if (!(k in IDLE_DEFAULT)) throw Error(`Unknown idle setting ${k}; use ${Object.keys(IDLE_DEFAULT).join(', ')}`);
      setIdle(patch, !!allShots);
      return { idle: { ...idleOf(project), events: idleNow()?.events || [] }, shot: project.code };
    },
    selectShot(ref) { selectShot(ref); return this.state(); },
    moveShot(ref, to) { const i = shotIndex(ref); moveShot(Math.max(0, Math.min(scene.shots.length - 1, to)) - i, i); return this.state(); },
    deleteShot(ref) { const i = shotIndex(ref); if (scene.shots.length === 1) throw Error('A scene needs at least one shot'); pushUndo(); scene.shots.splice(i, 1); scene.active = Math.min(i, scene.shots.length - 1); useScene(scene); return this.state(); },
    render: (opts = {}) => render(opts.still != null, !!opts.preview, opts.still),
    renderScene: (opts = {}) => renderScene(!!opts.preview),
    // carousel
    carousel() { const c = carouselOf(scene); return { size: c.size, slides: c.slides.map((s, i) => ({ index: i, id: s.id, shot: scene.shots.find(x => x.uid === s.shot)?.code || null, frame: s.frame, bubbles: s.bubbles })) }; },
    carouselSnap(shot, at) {
      if (shot != null) selectShot(shot);
      if (at != null) goto(at);
      pushUndo();
      const s = { id: Math.random().toString(36).slice(2, 10), shot: project.uid, frame, bubbles: [] };
      carouselOf(scene).slides.push(s); thumbs.set(s.id, slideThumb()); carouselSel = s.id;
      if (tab === 'carousel') buildPanel();
      return this.carousel();
    },
    carouselEdit(op) {
      const c = carouselOf(scene), i = op.slide ?? (c.slides.length - 1), s = c.slides[i];
      if (op.size) { if (!SIZES[op.size]) throw Error('size must be one of ' + Object.keys(SIZES).join(', ')); pushUndo(); c.size = op.size; layout(); }
      if (op.remove) { if (!s) throw Error('No slide ' + i); pushUndo(); c.slides.splice(i, 1); }
      else if (op.to != null) { if (!s) throw Error('No slide ' + i); pushUndo(); c.slides.splice(i, 1); c.slides.splice(Math.max(0, Math.min(c.slides.length, op.to)), 0, s); }
      if (op.bubble) {
        if (!s) throw Error('No slide ' + i);
        const b = op.bubble;
        if (b.assetId && !KINDS[b.assetId]) throw Error('kind must be one of ' + Object.keys(KINDS).join(', '));
        if (b.tail && !TAILS[b.tail]) throw Error('tail must be one of ' + Object.keys(TAILS).join(', '));
        pushUndo();
        if (b.index != null && s.bubbles[b.index]) { if (b.delete) s.bubbles.splice(b.index, 1); else Object.assign(s.bubbles[b.index], b); delete s.bubbles[b.index]?.index; }
        else s.bubbles.push({ assetId: b.assetId || 'speech', text: b.text || '', x: b.x ?? 0.5, y: b.y ?? 0.18, tail: b.tail || 'down-left' });
        carouselSel = s.id;
      }
      if (tab === 'carousel') buildPanel();
      overlayDraw?.();
      return this.carousel();
    },
    carouselExport: () => exportCarousel(carCtx()),
    // library, stage and characters (library.js)
    async setCharacter(c) { await setCharacter(c); return { character: character(), controls: shownParts().map(p => p[1]) }; },
    async libraryUse(id, opts = {}) {
      if (opts.shot != null) selectShot(opts.shot);
      const r = await useItem(libCtx(), id, { ...opts, prompt: false });
      if (tab === 'library') buildPanel();
      return r;
    },
    setStage(patch, shotOnly) {
      const bad = Object.keys(patch).filter(k => !['set', 'setProps', 'time', 'sky', 'shadows', 'outfit', 'accessories', 'mouthSet'].includes(k));
      if (bad.length) throw Error('Unknown stage keys: ' + bad.join(', '));
      const r = setStage(libCtx(), patch, !!shotOnly);
      if (tab === 'library') buildPanel();
      return r;
    },
    removeItem(i) { const r = removeItem(libCtx(), i); if (tab === 'library') buildPanel(); return r; },
    stage: () => ({ character: character(), stage: stageOf(scene, project), sceneStage: scene.stage || {}, shotStage: project.stage || {}, items: project.items || [] }),
    save: () => saveShot(false, true),
    undo, redo,
  };
  document.body.dataset.ready = '1';
  loop();
})().catch(e => { document.body.append(h('pre', { style: 'position:fixed;inset:40px;background:#1F1F1D;color:#E0A64B;padding:16px;z-index:999' }, 'Doodle Studio 3D could not start:\n' + (e.stack || e))); });
