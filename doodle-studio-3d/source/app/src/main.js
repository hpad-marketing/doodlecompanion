// Doodle Studio 3D: editor shell. Same look as Doodle Studio; 3D-specific workflow.
import { Viewport } from './viewport.js';
import { cameraPresetsPanel, bindCameraPresets } from './camera-presets.js';
import { carouselPanel, bindOverlay, finishCarousel, carouselOf, exportCarousel, SIZES, KINDS, TAILS } from './carousel.js';
import { TRACK_IDS } from './rig.js';
import { newScene, newShotData, migrate, nextCode, bindShot, valueAt, frameValues, setKey, deleteKey, hasKey, toBridgeShot, idleFor, stageOf, CAM_DEFAULT, EASES, DISCRETE, defaults } from './project.js';
import { autosaveSettings, setAutosave, startAutosave, autosaveNow, offerRecovery, saveVersion, versionsDialog, commandSearch, addMarker, markerEls, chime, diskOk, toggleFps, fpsTick, fpsText } from './polish.js';
import { breakdown, overlap, simplify, loopCheck, makeLoop, retime, view3, drawOnion, setSilhouette, setMirror, FILTERS, filterIds, playblast } from './animtools.js';
import { loadAudio, audioInfo, play as playAudio, stop as stopAudio, waveform, audioDrive, envelope as audioEnvelope } from './audio.js';
import { retention, chapters, loopBack, gags, bibleDialog } from './storytime.js';
import { libraryPanel, libraryRows, useItem, setStage, removeItem, CHARACTERS, EXTRA } from './library.js';
import { idleOf, IDLE_DEFAULT, IDLE_RANGE } from './idle.js';
import { historyDialog, claude, changeLogDialog, presets, presetsDialog, applyPreset, estimate, preflight, recordModeratorPass, projector, preflightDialog, batchDialog, runBatch, health, fix as healthFix, healthDialog, pack, cacheDialog } from './production.js';
import { keys as myKeys, comboOf, cmdId, hotkeyDialog, layouts, saveLayout, useLayout, restoreLastLayout, bindResizers, popOut, popOpen, popDraw, noteRun, toggleFav, quickbar, snap, snapValue, perf, heavy, STATUS, statusOf, setStatus, nextStatus, TEMPLATES, fromTemplate, templateDialog, drawNote, showNotes, detectBeats, splitShotAt, splitBySentences } from './workflow.js';

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
  'cam.tx': 'Aim left / right', 'cam.ty': 'Aim near / far', 'cam.tz': 'Aim height', 'cam.focus': 'Focus distance', 'cam.fstop': 'Aperture (f-stop)', squash: 'Squash / stretch',
  expression: 'Expression', gaze: 'Gaze', mouth: 'Speech mouth', blink: 'Blink',
};
const TIPS = {
  'cam.yaw': 'Swing the camera around Bunny. Positive moves it to screen right.',
  'cam.pitch': 'Positive looks down from above (high angle). Negative looks up from below (low angle). The whole set moves with the camera.',
  'cam.dist': 'How far the camera is from what it aims at, in metres.',
  'cam.lens': 'Focal length. 15–24 mm is wide and distorts; 85–135 mm is long and flattens.',
  'cam.roll': 'Tilts the frame for a Dutch angle. Horizon lock keeps it level.',
  'cam.focus': 'Rack focus: metres from the camera to the sharp plane. 0 keeps everything sharp. Key it to pull focus between two things.',
  'cam.fstop': 'Lower is a shallower focus (more blur). Only used when Focus distance is above 0.',
  squash: 'Plus squashes down and out, minus stretches up and thin. Volume stays the same and the feet stay planted.',
};
const EXTRA_RANGE = { legReach: [0, 100, 1], earLScale: [50, 150, 1], earRScale: [50, 150, 1], earLSquash: [-50, 30, 1], earRSquash: [-50, 30, 1], noseWiggle: [-100, 100, 1], noseSniff: [0, 100, 1],
  bodyX: [-400, 400, 1], bodyY: [-200, 200, 1], depth: [-4, 4, 0.05], s: [0.3, 2, 0.01], bodyRot: [-45, 45, 1], breath: [0, 90, 1],
  'cam.yaw': [-180, 180, 1], 'cam.pitch': [-60, 89, 1], 'cam.dist': [0.2, 60, 0.05], 'cam.lens': [12, 200, 1], 'cam.roll': [-45, 45, 1],
  'cam.tx': [-10, 10, 0.01], 'cam.ty': [-10, 10, 0.01], 'cam.tz': [-0.5, 10, 0.01], 'cam.focus': [0, 60, 0.05], 'cam.fstop': [0.7, 22, 0.1], squash: [-30, 30, 1] };
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
// each entry is the scene before a change, with a name for the Undo history panel
let nextLabel = null;
const entry = label => ({ json: JSON.stringify(scene), label: label || nextLabel || 'Edit', at: Date.now() });
function pushUndo(label) { undoStack.push(entry(label)); if (undoStack.length > 200) undoStack.shift(); redoStack = []; dirty = true; }
function restore(e) { useScene(migrate(JSON.parse(e.json))); }
function undo() { if (!undoStack.length) return; const e = undoStack.pop(); redoStack.push({ ...entry(e.label) }); restore(e); }
function redo() { if (!redoStack.length) return; const e = redoStack.pop(); undoStack.push(entry(e.label)); restore(e); }
function jumpTo(i) { while (undoStack.length > i) undo(); }

// ---------------------------------------------------------------- scene and shots (same model as the 2D app)
function useScene(sc) {
  scene = sc;
  project = bindShot(scene, scene.shots[scene.active]);
  frame = Math.max(0, Math.min(project.length - 1, frame));
  selected = null;
  refreshAll();
  if ((scene.audio?.path || null) !== (audioInfo()?.path || null)) loadAudio(api, scene.audio?.path).then(drawTracks).catch(e => toast('Audio: ' + e.message, 5000));
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
  if (view3.silhouette) setSilhouette(view, true);
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
  if (!DISCRETE.has(id)) v = snapValue(id, v, LENSES);
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
  if (project.horizonLock) cam.roll = 0;
  view.setCamera(cam);
  syncPanel();
  drawPlayhead();
  updateHud();
  overlayDraw?.();
  if (view3.onion || onionShown) { const t = performance.now(); drawOnion(animCtx()); onionShown = view3.onion; perf('onion skin', performance.now() - t); }
  showNotes(project, frame);
  if (ruleLights) { const t = performance.now(); rules = view.ruleCheck(); perf('rule lights', performance.now() - t); }
}
let ruleLights = true, rules = null;
let onionShown = false;

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
  ['File', [['New scene', newShot, 'Ctrl+N'], ['New from template…', () => templateDialog(wfCtx())], ['Open…', openShot, 'Ctrl+O'], ['Save', () => saveShot(false), 'Ctrl+S'], ['Save as…', () => saveShot(true), 'Ctrl+Shift+S'], ['Save version…', () => saveVersion(polCtx())], ['Versions…', () => versionsDialog(polCtx())], '-', ['Import audio for the scene…', () => importAudio()], ['Remove scene audio', () => importAudio(null)], '-',
    ['Render scene (all shots)', () => renderScene(), 'Ctrl+Shift+E'], ['Render this shot', () => render(), 'Ctrl+R'], ['Render this frame', () => render(true), 'Ctrl+Shift+R'], '-', ['Export Blender shot file…', exportBridge]]],
  ['Shot', [['Storyboard sheet (PNG)', () => storyboard()], '-', ...STATUS.map(([id, n]) => [`Status: ${n}`, () => shotStatus(id)]), ['Split shot at the playhead', () => splitHere()], '-', ['Add shot after this one', () => addShot(false), 'Ctrl+T'], ['Duplicate this shot', () => addShot(true), 'Ctrl+Shift+T'], ['Name this shot…', () => labelShot()],
    '-', ['Move earlier', () => moveShot(-1), 'Alt+←'], ['Move later', () => moveShot(1), 'Alt+→'], '-', ['Previous shot', () => selectShot(Math.max(0, scene.active - 1)), 'PgUp'],
    ['Next shot', () => selectShot(Math.min(scene.shots.length - 1, scene.active + 1)), 'PgDn'], '-', ['Delete this shot', () => deleteShot()]]],
  ['Edit', [['Undo', undo, 'Ctrl+Z'], ['Redo', redo, 'Ctrl+Shift+Z'], ['Undo history…', () => historyDialog(prodCtx()), 'Ctrl+H'], '-', ['Key Bunny pose', () => keyGroup(BUNNY_IDS.concat(FACE_IDS)), 'K'], ['Key camera', () => keyGroup(CAM_IDS), 'Shift+K'],
    ['Delete selected key', deleteSelected, 'Delete'], ['Clear all keys', clearAll], '-', ['Add marker with a note', () => addMarker(polCtx()), 'M'], ['Draw a review note on this frame', () => reviewNote(), 'N'], ['Tap a beat marker', () => tapBeat(), 'B']]],
  ['View', [['Command search', () => commandSearch(polCtx()), 'Ctrl+K'], ['Show fps', () => { toggleFps(); updateHud(); }], ['Pop out the viewport (second screen)', () => popOut(wfCtx())], ['Snapping on / off', () => toggleSnap()], ['Rule lights on / off', () => { ruleLights = !ruleLights; updateHud(); }], '-',
    ['Save layout…', () => saveLayout(wfCtx())], 'layouts', '-',
    ['Onion skin', () => { view3.onion = !view3.onion; apply(); }, 'O'], ['Silhouette check', () => setSilhouette(view, !view3.silhouette)], ['Mirror view', () => setMirror(!view3.mirror)], '-', ['Dark mode', toggleDark, 'Ctrl+D'], ['Floor grid', () => { view.grid.visible = !view.grid.visible; }, 'G'], ['Frame Bunny', frameBunny, 'F']]],
  ['Camera', [...LENSES.map(l => [`${l} mm lens`, () => camSet({ lens: l })]), '-', ...VIEWS.map(([n, c]) => [n, () => camSet(c)]), '-', ['Dolly zoom: wide, keep size', () => dollyTo(18)], ['Dolly zoom: long, keep size', () => dollyTo(100)]]],
  ['Animate', [['Breakdown halfway (tween)', () => breakdown(animCtx(), 50)], ['Stepped blocking on / off', () => toggleStepped()], '-',
    ['Simplify keys', () => toast(`Removed ${simplify(animCtx()).removed} keys the curves did not need`, 4000)],
    ['Loop check', () => { const r = loopCheck(animCtx()); toast(r.seamless ? 'Seamless: the last frame matches the first' : `Not seamless: ${r.mismatched.map(m => LABEL[m.id] || m.id).slice(0, 4).join(', ')}${r.mismatched.length > 4 ? '…' : ''}`, 5000); }],
    ['Make seamless loop', () => { makeLoop(animCtx()); toast('Last frame keyed to match the first'); }],
    ['Audio drives a control…', () => audioDriveDialog()], ['Mark beats from the audio', () => markBeats()],
    ['Retime shot…', () => { const x = prompt('Speed: below 1 is slower, above 1 is faster (e.g. 0.8 or 1.25). Keys after the playhead move.', '1'); if (x) retime(animCtx(), 1 / Number(x), frame); }], '-',
    ['Playblast (viewport video)', () => playblast(animCtx()).catch(e => toast(e.message, 5000))]]],
  ['Story', [['Hook and retention check', () => retentionCheck()], ['Loop back to the opening (Reels)', () => { pushUndo(); const r = loopBack(scene); dirty = true; apply(); drawTracks(); toast(`${r.shot} now ends on the opening pose`); }],
    ['Export YouTube chapters', () => exportChapters()], ['Split the voice into sentences…', () => sentenceDialog()], ['Story bible…', () => bibleDialog(polCtx())]]],
  ['Tools', [['Check before export (preflight)', () => runPreflight(false)], ['Health check…', () => healthDialog(prodCtx())], ['Claude change log…', () => changeLogDialog(prodCtx())], '-',
    ['Overnight batch…', () => batchDialog(prodCtx())], ['Cancel sleep after renders', () => api('sleep-when-done', { on: false }).then(() => toast('The PC will stay awake'))], '-',
    ['Render presets…', () => presetsDialog(prodCtx())], ['Pack project…', () => pack(prodCtx()).catch(e => toast(e.message, 5000))], ['Clean up cache…', () => cacheDialog(prodCtx()).catch(e => toast(e.message, 5000))]]],
  ['Help', [['Controls and shortcuts', showHelp, 'F1'], ['Keyboard shortcuts and cheat sheet…', () => hotkeyDialog(wfCtx())]]],
];

// saved layouts are listed live in the View menu
const menus = () => MENUS.map(([name, items]) => [name, items.flatMap(it => (it === 'layouts' ? Object.keys(layouts.get()).map(n => [`Layout: ${n}`, () => useLayout(wfCtx(), n)]) : [it]))]);
function buildMenu() {
  const bar = $('#menubar');
  bar.replaceChildren();
  for (const [name, items] of menus()) {
    const list = h('div', { class: 'menu-list', role: 'menu' });
    for (const it of items) {
      if (it === '-') { list.append(h('hr')); continue; }
      const [label, fn, key] = it;
      list.append(h('button', { role: 'menuitem', title: 'Right-click to pin it to the favourites bar', oncontextmenu: e => { e.preventDefault(); const on = toggleFav(`${name} › ${label}`); refreshQuickbar(); toast(on ? `Pinned "${label}"` : `Unpinned "${label}"`); }, onclick: () => { closeMenus(); runCommand({ group: name, label, run: fn }); } }, h('span', {}, label), key ? h('kbd', {}, key) : null));
    }
    const btn = h('button', { 'aria-haspopup': 'true', 'aria-expanded': 'false', onclick: e => { const m = e.currentTarget.parentElement; const open = !m.classList.contains('open'); closeMenus(); if (open) { m.classList.add('open'); e.currentTarget.setAttribute('aria-expanded', 'true'); } } }, name);
    bar.append(h('div', { class: 'menu' }, btn, list));
  }
  bar.append(h('div', { class: 'spacer' }), h('span', { class: 'status', id: 'status' }, ''));
  document.addEventListener('pointerdown', e => { if (!e.target.closest('#menubar')) closeMenus(); });
}
// every command run from a menu, the bar, Ctrl+K or a custom key goes through here
function runCommand(c) {
  if (!c) return;
  nextLabel = c.label.replace(/…$/, '');
  try { const r = c.run(); if (r?.catch) r.catch(e => toast(e.message, 5000)); } catch (e) { toast(e.message, 5000); } finally { nextLabel = null; }
  noteRun(cmdId(c)); refreshQuickbar();
}
function refreshQuickbar() { const q = $('#quickbar'); if (q) q.replaceChildren(...quickbar(wfCtx())); }
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
  slider.addEventListener('pointerdown', () => pushUndo(LABEL[id] || id));
  slider.addEventListener('input', () => { setValue(id, Number(slider.value)); num.value = round(Number(slider.value)); });
  num.addEventListener('change', () => { pushUndo(LABEL[id] || id); setValue(id, Number(num.value)); });
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
    c.append(posePanel());
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
    c.append(h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: () => keyGroup(CAM_IDS) }, 'Key camera'), h('button', { onclick: frameBunny }, 'Frame Bunny'),
      h('button', { onclick: () => { pushUndo(); setValue('cam.focus', round(current('cam.dist'))); drawTracks(); }, title: 'Rack focus: put the sharp plane on what the camera aims at. Key it at two frames to pull focus.' }, 'Focus on aim'),
      h('button', { onclick: () => window.ds3d.turntable(), title: '360° turntable: the camera circles once over the whole shot' }, 'Turntable'),
      h('button', { 'aria-pressed': String(!!project.horizonLock), onclick: () => { pushUndo(); project.horizonLock = !project.horizonLock; apply(); buildPanel(); }, title: 'Keep the horizon level in this shot: roll and Dutch presets are ignored' }, 'Horizon lock')));
    c.append(h('p', { class: 'hint' }, 'Drag in the viewport to orbit, Shift+drag to move the aim, wheel to move in and out, Alt+wheel to change the lens. The set moves with the camera, so angles stay physically true.'));
    c.append(cameraPresetsPanel(presetCtx()));
  } else if (tab === 'library') {
    c.append(libraryPanel(libCtx()));
  } else if (tab === 'carousel') {
    c.append(carouselPanel(carCtx()));
  } else if (tab === 'render') {
    const field = (label, obj, key, attrs) => { const i = h('input', { ...attrs, value: obj[key] }); i.addEventListener('change', () => { pushUndo(); obj[key] = attrs.type === 'number' ? Number(i.value) : i.value; buildTimelineTools(); drawTracks(); updateHud(); }); return h('label', { class: 'ctl', style: 'grid-template-columns:8.5em 1fr' }, label, i); };
    c.append(h('h3', {}, `Shot ${project.code}`), field('Name', project, 'label', { type: 'text', placeholder: 'optional, e.g. intro' }), field('Length (frames)', project, 'length', { type: 'number', min: 1, max: 54000 }),
      h('span', { title: 'Line weight for this shot in Blender, as a percent of Doodle Studio\'s ink (100 = Bunny\'s usual weight). Every line in the shot changes together, so weights stay equal.' }, field('Line weight (%)', project, 'ink', { type: 'number', min: 40, max: 250, placeholder: '100' })),
      h('h3', {}, `Scene: ${scene.shots.length} shot${scene.shots.length > 1 ? 's' : ''}, ${(sceneFrames() / scene.fps).toFixed(1)} s`),
      field('Frame rate', scene, 'fps', { type: 'number', min: 12, max: 60 }),
      field('Width (px)', scene, 'width', { type: 'number', min: 64, max: 3840 }), field('Height (px)', scene, 'height', { type: 'number', min: 64, max: 3840 }));
    c.append(h('div', { class: 'chips', style: 'margin:6px 0' }, ...presets().map(p =>
      h('button', { 'aria-pressed': String(scene.width === p.width && scene.height === p.height && scene.fps === p.fps), title: `${p.width}×${p.height}, ${p.fps} fps`, onclick: () => applyPreset(prodCtx(), p.name) }, p.name)),
      h('button', { title: 'Add, rename or change presets', onclick: () => presetsDialog(prodCtx()) }, 'Edit…')));
    c.append(h('h3', {}, 'Blender render'), h('p', { class: 'hint' }, 'Renders run in the background in Blender: hoodie cloth, ear and tail springs, the collision solver, then the 3D rule checks. Render scene renders every shot in order and joins them into one video; shots that have not changed since their last render are reused. Everything goes to DeepInDoodles\\<scene>\\work: videos in renders, logs and rule reports in checks. Only the approved final goes at the top.'),
      h('div', { class: 'row' }, h('button', { class: 'primary', onclick: () => renderScene() }, 'Render scene'), h('button', { onclick: () => render() }, `Render ${project.code}`),
        h('button', { onclick: () => render(true) }, 'This frame')),
      h('div', { class: 'row', style: 'margin-top:6px' }, h('button', { onclick: () => renderScene(true), title: 'Every shot at half size without cloth: a fast check of timing and cuts' }, 'Quick preview scene'),
        h('button', { onclick: () => render(false, true), title: 'This shot at half size without cloth' }, 'Quick preview shot'), h('button', { onclick: cancelRender }, 'Cancel')),
      h('div', { class: 'row', style: 'margin-top:6px' }, h('button', { onclick: () => runPreflight(false), title: 'Audio, lip sync, captions and the moderator PASS, before the final export' }, 'Check before export')),
      h('div', { id: 'render-estimate', class: 'hint' }, ''), h('div', { id: 'render-status', class: 'hint' }, ''), autosavePanel(), h('h3', {}, 'Blender location'), h('div', { class: 'row' }, h('span', { id: 'blender-path', class: 'hint', style: 'flex:1;overflow-wrap:anywhere' }, '…'),
        h('button', { onclick: pickBlender }, 'Change…')));
    api('settings', {}).then(s => { const el = $('#blender-path'); if (el) el.textContent = s.blenderFound || 'Not found. Install Blender 4.5 LTS, or point to blender.exe.'; }).catch(() => {});
    pollRender();
    estimate(prodCtx(), sceneFrames()).then(e => { const el = $('#render-estimate'); if (el) el.textContent = 'Scene: ' + e.text; });
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

// ---------------------------------------------------------------- storyboard: every shot's start, middle and end on one sheet
async function storyboard() {
  const keep = { active: scene.active, frame };
  const cw = 220, ch = Math.round(cw * scene.height / scene.width), pad = 14, head = 26, title = 46;
  const sheet = document.createElement('canvas');
  sheet.width = pad + 3 * (cw + pad) + 200;
  sheet.height = title + scene.shots.length * (ch + head + pad) + pad;
  const g = sheet.getContext('2d');
  g.fillStyle = '#E0A64B'; g.fillRect(0, 0, sheet.width, sheet.height);
  g.fillStyle = g.strokeStyle = '#1F1F1D'; g.lineWidth = 3; g.font = '800 22px system-ui, sans-serif';
  g.fillText(`${scene.name}: ${scene.shots.length} shots, ${(sceneFrames() / scene.fps).toFixed(1)} s`, pad, 31);
  let t0 = 0;
  for (const [i, s] of scene.shots.entries()) {
    scene.active = i; project = bindShot(scene, s);
    const y = title + i * (ch + head + pad);
    g.font = '800 16px system-ui, sans-serif';
    g.fillText(`${shotName(s)}   ${(s.length / scene.fps).toFixed(1)} s   from ${(t0 / scene.fps).toFixed(1)} s`, pad, y + 18);
    for (const [k, f] of [0, Math.floor(s.length / 2), s.length - 1].entries()) {
      frame = f; apply(); view.render();
      const x = pad + k * (cw + pad);
      g.drawImage(view.renderer.domElement, x, y + head, cw, ch);
      g.strokeRect(x, y + head, cw, ch);
    }
    const st = stageOf(scene, s), notes = [st.set && 'Set: ' + st.set, st.outfit && 'Outfit: ' + st.outfit, s.items?.length && `${s.items.length} library items`, s.markers?.length && `${s.markers.length} markers`].filter(Boolean);
    g.font = '600 13px system-ui, sans-serif';
    notes.forEach((n, j) => g.fillText(n, pad + 3 * (cw + pad), y + head + 16 + j * 18));
    t0 += s.length;
  }
  scene.active = keep.active; project = bindShot(scene, scene.shots[keep.active]); frame = keep.frame; refreshAll();
  const root = (await api('settings', {})).rendersRoot;
  const safe = (scene.name || 'Untitled').replace(/[\\/:*?"<>|]/g, '_');
  const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
  const r = await api('write-png', { path: `${root}/${safe}/work/storyboard/${safe.replace(/ /g, '_')}_storyboard_${stamp}.png`, data: sheet.toDataURL('image/png').split(',')[1] });
  toast('Storyboard saved: ' + (r.path || 'work\\storyboard'), 5000);
  return { path: r.path, shots: scene.shots.length };
}

// ---------------------------------------------------------------- workflow.js: hotkeys, layouts, pop-out, quickbar, status, templates, notes, beats, sentences
const wfCtx = () => ({
  h, api, toast, scene: () => scene, project: () => project, frame: () => frame,
  commands: () => polCtx().commands(), runCommand, refreshQuickbar, refreshMenu: () => buildMenu(),
  togglePlay, step: d => goto(frame + d),
  viewState: () => ({ tab, part, theme: document.body.dataset.theme || 'light', grid: view.grid.visible, onion: view3.onion, silhouette: view3.silhouette, mirror: view3.mirror, keyFilter, snap: snap.on }),
  setViewState: L => {
    if (L.tab) tab = L.tab; if (L.part) part = L.part;
    if (L.theme) { document.body.dataset.theme = L.theme; try { localStorage.setItem('ds3d.theme', L.theme); } catch {} }
    if (L.grid != null) view.grid.visible = L.grid;
    if (L.onion != null) view3.onion = L.onion;
    if (L.silhouette != null) setSilhouette(view, L.silhouette);
    if (L.mirror != null) setMirror(L.mirror);
    if (L.keyFilter) keyFilter = L.keyFilter;
    if (L.snap != null) snap.on = L.snap;
    buildTabs(); buildPanel(); buildMenu(); layout(); buildTimelineTools(); drawTracks(); apply();
  },
  resized: () => { layout(); drawTracks(); },
  newFromTemplate: id => {
    const t = TEMPLATES.find(x => x.id === id);
    if (!t) throw Error('No template ' + id + '. Templates: ' + TEMPLATES.map(x => x.id).join(', '));
    if (dirty && !confirm('Start a new scene from this template? Unsaved changes are lost (the autosave keeps a copy).')) return null;
    filePath = null; undoStack = []; redoStack = []; dirty = true; frame = 0;
    const sc = fromTemplate(t, newScene(t.name.replace(/ \(.*/, '')));
    useScene(sc);
    return { template: t.id, shots: sc.shots.map(x => ({ code: x.code, label: x.label, length: x.length })) };
  },
});
function toggleSnap() { snap.on = !snap.on; toast(snap.on ? 'Snapping: angles to 5°, distances to 5 cm, lens to the presets' : 'Snapping off'); updateHud(); }
function shotStatus(st, i = scene.active) { pushUndo('Shot status'); setStatus(scene.shots[i], st); dirty = true; buildTimelineTools(); return { shot: scene.shots[i].code, status: st }; }
function splitHere(f = frame) { pushUndo('Split shot'); const b = splitShotAt(scene, scene.active, f); dirty = true; useScene(scene); return { split: project.code, new: b.code }; }
function reviewNote() {
  drawNote(wfCtx(), strokes => {
    const text = prompt('Note text (optional)', '') ?? '';
    pushUndo('Review note');
    project.markers ||= [];
    const m = project.markers.find(x => x.f === frame);
    if (m) { m.sketch = [...(m.sketch || []), ...strokes]; if (text) m.note = text; } else project.markers.push({ f: frame, note: '✎ ' + (text || 'review note'), sketch: strokes });
    project.markers.sort((a, b) => a.f - b.f);
    dirty = true; drawTracks(); apply();
  });
}
function tapBeat() { pushUndo('Beat'); project.markers ||= []; if (!project.markers.some(m => m.f === frame)) project.markers.push({ f: frame, note: 'beat' }); project.markers.sort((a, b) => a.f - b.f); dirty = true; drawTracks(); return frame; }
function markBeats() {
  const beats = detectBeats(envelopeNow(), sceneStart(), project.length, scene.fps);
  pushUndo('Beats from audio');
  project.markers ||= [];
  for (const f of beats) if (!project.markers.some(m => m.f === f)) project.markers.push({ f, note: 'beat' });
  project.markers.sort((a, b) => a.f - b.f);
  dirty = true; drawTracks();
  toast(`${beats.length} beats marked in ${project.code}`);
  return beats;
}
function sentenceDialog() {
  const text = prompt('Paste what is said in this shot (optional). With it, the shot splits into one shot per sentence; without it, at every pause in the voice.', '');
  if (text == null) return null;
  return splitSentences(text);
}
function splitSentences(text) {
  if (!envelopeNow()) throw Error('Import the voice for the scene first (File › Import audio…)');
  pushUndo('Split by sentences');
  const r = splitBySentences(scene, scene.active, envelopeNow(), sceneStart(), text);
  dirty = true; useScene(scene);
  toast(`Split into ${r.length} shots`);
  return r;
}

// ---------------------------------------------------------------- production.js: history, change log, presets, preflight, batch, health
function showFrame(s, f) {
  const i = scene.shots.indexOf(s);
  if (i >= 0 && i !== scene.active) { scene.active = i; project = bindShot(scene, s); }
  frame = Math.max(0, Math.min(project.length - 1, f | 0)); apply();
}
const prodCtx = () => ({
  h, api, toast, view: () => view, scene: () => scene, project: () => project, frame: () => frame, file: () => filePath, showFrame, valueAt,
  pushUndo, history: () => undoStack.map(e => ({ label: e.label, at: e.at })), jumpTo,
  setLabel: l => { nextLabel = l; },
  replaceScene: sc => { useScene(migrate(sc)); dirty = true; },
  changed: lengthToo => { dirty = true; if (lengthToo) { layout(); buildTimelineTools(); } apply(); drawTracks(); buildPanel(); updateHud(); },
  rebuild: () => buildPanel(),
  envelope: () => envelopeNow(),
  bridgeFor: (sc, s) => toBridgeShot(bindShot(sc, s), ALL_IDS(), data.face.faces, sc.character || 'bunny', stageOf(sc, s)),
  autosaveMinutes: () => autosaveSettings().minutes, setAutosave: p => { const r = setAutosave(p); startAutosave(polCtx()); return r; },
  importAudio: () => importAudio(),
});
const envelopeNow = () => (audioInfo() ? audioEnvelope(scene.fps) : null);
async function runPreflight(thenRender) {
  const r = preflight(prodCtx(), scene, { envelope: envelopeNow(), project2d: projector(prodCtx()) });
  r.estimate = (await estimate(prodCtx(), sceneFrames())).text;
  preflightDialog(prodCtx(), r, () => renderScene(false, true));
  return r;
}
window.ds3dClaude = { begin: (tool, n) => claude.begin(prodCtx(), tool, n), end: (n, failed) => { claude.end(prodCtx(), n, failed); updateHud(); } };

// ---------------------------------------------------------------- polish.js: autosave, versions, command search, markers
const polCtx = () => ({
  h, api, toast, pushUndo, goto, scene: () => scene, project: () => project, frame: () => frame, file: () => filePath, dirty: () => dirty,
  changed: () => { dirty = true; drawTracks(); updateHud(); },
  status: t => { const el = $('#status'); if (el) el.textContent = t; },
  restore: (p, file, f) => { undoStack = []; redoStack = []; filePath = file || null; frame = f | 0; useScene(migrate(p)); dirty = true; updateHud(); },
  commands: () => [
    ...menus().flatMap(([group, items]) => items.filter(i => i !== '-').map(([label, run, key]) => ({ group, label, run, key }))),
    ...TABS.map(([id, name]) => ({ group: 'Panel', label: `Open the ${name} tab`, run: () => { tab = id; buildTabs(); buildPanel(); layout(); } })),
    ...CHARACTERS.map(([id, name]) => ({ group: 'Character', label: `Put ${name} on stage`, run: () => setCharacter(id) })),
    ...shownParts().map(([id, name]) => ({ group: 'Pose', label: `Pose: ${name}`, run: () => { tab = 'pose'; part = id; buildTabs(); buildPanel(); } })),
    { group: 'Pose', label: 'Mirror pose', run: () => putPose(mirrorValues(poseNow())) },
    { group: 'Camera', label: 'Focus on aim (rack focus)', run: () => { pushUndo(); setValue('cam.focus', round(current('cam.dist'))); drawTracks(); } },
    { group: 'Camera', label: 'Horizon lock on / off', run: () => { pushUndo(); project.horizonLock = !project.horizonLock; apply(); buildPanel(); } },
    { group: 'File', label: 'Autosave now', run: () => autosaveNow(polCtx(), true).then(() => toast('Autosaved')) },
  ],
});
function autosavePanel() {
  const s = autosaveSettings();
  const num = (key, label, attrs, tip) => {
    const i = h('input', { type: 'number', value: s[key], style: 'width:64px', ...attrs, 'aria-label': label });
    i.addEventListener('change', () => { setAutosave({ [key]: Number(i.value) }); startAutosave(polCtx()); });
    return h('span', { class: 'row', title: tip }, label, i);
  };
  return h('div', {}, h('h3', {}, 'Autosave'), h('div', { class: 'row' },
    num('minutes', 'Every (min)', { min: 0, max: 60, step: 1 }, 'Saves a copy of the scene this often while it changes. 0 turns autosave off.'),
    num('keep', 'Keep', { min: 1, max: 50, step: 1 }, 'How many autosave copies to keep per scene; the oldest go first.')),
    h('p', { class: 'hint' }, 'Autosaves sit in the app\'s own folder, apart from your scene file. If the app ever closes without saving, it offers the last one back at the same shot and frame. File › Save version… keeps a named copy in work\\versions.'));
}

// ---------------------------------------------------------------- audio.js: scene audio, waveform, audio-driven controls
const sceneStart = () => scene.shots.slice(0, scene.active).reduce((n, s) => n + s.length, 0);
async function importAudio(pick) {
  const p = pick === null ? null : pick ?? (await api('pick-audio', {})).path;
  if (p === undefined || (pick !== null && !p)) return null;
  pushUndo();
  scene.audio = p ? { path: p } : null;
  await loadAudio(api, p);
  drawTracks();
  if (p) toast(`Audio: ${p.split(/[\\/]/).pop()} (${audioInfo().seconds} s). It plays with the timeline and goes into scene renders.`, 5000);
  return audioInfo();
}
function audioDriveDialog() {
  const id = prompt('Which control should follow the audio? e.g. bodyY (bounce), earLFold, headNod, cam.dist', 'bodyY');
  if (!id) return;
  const [lo, hi] = range(id);
  const r = prompt(`Value when quiet, value when loud (range ${lo} to ${hi})`, id === 'bodyY' ? '0, 12' : `0, ${Math.round(hi / 3)}`);
  if (!r) return;
  const [a, b] = r.split(',').map(Number);
  return driveFromAudio(id, a, b);
}
function driveFromAudio(id, a, b, opts) {
  if (!ALL_IDS().includes(id)) throw Error('No control ' + id);
  pushUndo();
  const n = audioDrive(project, sceneStart(), id, a, b, opts, setKey);
  dirty = true; apply(); drawTracks();
  toast(`${LABEL[id] || id} follows the audio: ${n} keys`);
  return { id, keys: n };
}

// ---------------------------------------------------------------- storytime.js
function retentionCheck() {
  const r = retention(scene);
  const msg = `Hook (first 2 s): ${r.hook}.` + (r.lulls.length ? ` ${r.lulls.length} stretch${r.lulls.length > 1 ? 'es' : ''} of 4+ s with nothing changing: ${r.lulls.map(l => `${l.from} (${l.seconds} s)`).join(', ')}.` : ' No 4 s stretch without something changing.');
  toast(msg, 9000);
  return r;
}
async function exportChapters() {
  const c = chapters(scene);
  const root = (await api('settings', {})).rendersRoot;
  const safe = (scene.name || 'Untitled').replace(/[\\/:*?"<>|]/g, '_');
  const r = await api('write-file', { path: `${root}/${safe}/work/${safe.replace(/ /g, '_')}_chapters.txt`, data: btoa(unescape(encodeURIComponent(c.text + '\n'))) });
  toast(`Chapters saved: ${r.path}${c.problems.length ? '. Note: ' + c.problems.join('; ') : ''}`, 8000);
  return { ...c, path: r.path };
}

// ---------------------------------------------------------------- animtools.js
let keyFilter = 'all';
function toggleStepped() { pushUndo(); project.stepped = !project.stepped; apply(); buildTimelineTools(); toast(project.stepped ? 'Stepped blocking: keys hold' : 'Smooth in-betweens'); }
const animCtx = () => ({
  h, api, toast, pushUndo, goto, view: () => view, scene: () => scene, project: () => project, frame: () => frame,
  poseIds: () => BUNNY_IDS.concat(FACE_IDS),
  valuesAt: f => { const v = {}; for (const id of BUNNY_IDS.concat(FACE_IDS)) v[id] = valueAt(project, id, f); return v; },
  changed: lengthToo => { dirty = true; apply(); drawTracks(); if (lengthToo) buildTimelineTools(); updateHud(); },
});

// ---------------------------------------------------------------- pose tools: mirror, copy / paste, blend A to B
const POSE_IDS = () => BUNNY_IDS.filter(id => !['bodyX', 'bodyY', 'depth', 's'].includes(id)).concat(FACE_IDS);
const poseNow = () => Object.fromEntries(POSE_IDS().map(id => [id, current(id)]));
const poseBuf = { copy: null, A: null, B: null, t: 50 };
function mirrorValues(v) {
  const out = {}, names = data.face.gazes;
  for (let [id, x] of Object.entries(v)) {
    const m = /^(arm|elbow|wrist|leg|knee|foot|ear)([LR])(.*)$/.exec(id);
    if (m) id = m[1] + (m[2] === 'L' ? 'R' : 'L') + m[3];
    if (['turn', 'headYaw', 'rot', 'bodyTilt', 'torsoTwist', 'bodyRot', 'noseWiggle'].includes(id)) x = -x;
    if (id === 'gaze') { const j = names.indexOf((names[x] || '').replace(/Left|Right/, w => w === 'Left' ? 'Right' : 'Left')); if (j >= 0) x = j; }
    out[id] = x;
  }
  return out;
}
function putPose(v) { pushUndo(); for (const [id, x] of Object.entries(v)) setValue(id, x); drawTracks(); buildPanel(); }
function blendPose(t) {
  const { A, B } = poseBuf;
  if (!A || !B) return toast('Set pose A and pose B first');
  const k = t / 100, v = {};
  for (const id of Object.keys(A)) v[id] = DISCRETE.has(id) ? (k < 0.5 ? A[id] : B[id]) : A[id] + (B[id] - A[id]) * k;
  putPose(v);
}
function posePanel() {
  const t = h('input', { type: 'range', min: 0, max: 100, step: 1, value: poseBuf.t, 'aria-label': 'Blend from A to B' });
  t.addEventListener('change', () => { poseBuf.t = Number(t.value); blendPose(poseBuf.t); });
  const slot = k => h('button', { 'aria-pressed': String(!!poseBuf[k]), onclick: () => { poseBuf[k] = poseNow(); buildPanel(); toast(`Pose ${k} set`); }, title: `Remember the pose at the playhead as ${k}` }, `Set ${k}`);
  return h('div', {}, h('h3', {}, 'Pose tools'),
    h('div', { class: 'row' },
      h('button', { onclick: () => putPose(mirrorValues(poseNow())), title: 'Swap left and right in the whole pose and face, keyed at the playhead' }, 'Mirror pose'),
      h('button', { onclick: () => { poseBuf.copy = poseNow(); toast('Pose copied'); }, title: 'Copy the whole pose and face' }, 'Copy pose'),
      h('button', { onclick: () => poseBuf.copy ? putPose(poseBuf.copy) : toast('Copy a pose first'), title: 'Key the copied pose at the playhead' }, 'Paste'),
      h('button', { onclick: () => poseBuf.copy ? putPose(mirrorValues(poseBuf.copy)) : toast('Copy a pose first'), title: 'Key the copied pose at the playhead, left and right swapped' }, 'Paste mirrored')),
    h('div', { class: 'row', style: 'margin-top:4px' }, slot('A'), slot('B'), h('span', {}, 'A'), t, h('span', {}, 'B')),
    h('p', { class: 'hint' }, 'Blend keys an in-between of poses A and B at the playhead. Faces switch at the halfway point.'),
    (() => {
      const b = h('input', { type: 'range', min: -25, max: 125, step: 1, value: 50, 'aria-label': 'Breakdown' });
      b.addEventListener('change', () => { breakdown(animCtx(), Number(b.value)); buildPanel(); });
      return h('label', { class: 'ctl', title: 'Breakdown: keys an in-between of the keys either side of the playhead. Left favours the previous pose, right the next; past the ends overshoots.' }, h('span', { class: 'name' }, 'Breakdown'), b, h('span', {}, 'prev · next'));
    })(),
    (() => {
      const n = h('input', { type: 'number', min: 1, max: 12, step: 1, value: 2, style: 'width:56px', 'aria-label': 'Frames of lag' });
      const ids = PARTS.find(p => p[0] === part)?.[2] || [];
      return h('div', { class: 'row', title: 'Overlap: each control of this part lags the one before it, so motion flows down the chain (shoulder, elbow, wrist).' },
        h('button', { onclick: () => { overlap(animCtx(), ids, Number(n.value)); toast('Overlap added down ' + (PARTS.find(p => p[0] === part)?.[1] || 'the part')); } }, 'Overlap this part'), n, h('span', {}, 'frames each'));
    })());
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
    h('span', {}, `F${frame}`), ...(fpsText() ? [h('span', {}, fpsText() + (parseInt(fpsText()) < 30 && heavy() ? ' · heavy: ' + heavy() : ''))] : []),
    ...(ruleLights && rules ? [
      h('span', { class: 'rule ' + (rules.clips.length ? 'bad' : 'ok'), title: rules.clips.length ? 'Inside the head: ' + rules.clips.join(', ') : 'Hands and arms clear of the head' }, rules.clips.length ? '✗ Arm in head' : '✓ No clip'),
      h('span', { class: 'rule ' + (rules.belowFloor || rules.inAir ? 'bad' : 'ok'), title: `Lowest foot ${Math.round(rules.feet * 100)} cm from the floor` }, rules.belowFloor ? '✗ Feet in floor' : rules.inAir ? '✗ In the air' : '✓ Grounded'),
      h('span', { class: 'rule ' + ((project.ink ?? 100) === 100 ? 'ok' : 'bad'), title: 'Line weight equals Bunny\'s everywhere' }, (project.ink ?? 100) === 100 ? '✓ Line weight' : `✗ Line ${project.ink}%`)] : []),
    ...(snap.on ? [h('span', {}, 'Snap')] : []));
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
  const chips = scene.shots.map((s, i) => h('button', { class: 'shot-chip status-' + statusOf(s), 'aria-pressed': String(i === scene.active), title: `${shotName(s)}: ${(s.length / scene.fps).toFixed(1)} s, ${STATUS.find(x => x[0] === statusOf(s))[1]}. Click to edit, double-click to name, right-click for the next status.`,
    onclick: () => selectShot(i), ondblclick: () => labelShot(i), oncontextmenu: e => { e.preventDefault(); shotStatus(nextStatus(s), i); } }, shotName(s), h('small', {}, ` ${(s.length / scene.fps).toFixed(1)}s`), h('i', { class: 'status-tag' }, STATUS.find(x => x[0] === statusOf(s))[1])));
  $('#timeline-tools').replaceChildren(
    g('Scene', ...chips, h('button', { onclick: () => addShot(false), title: 'Add a shot after this one (Ctrl+T)' }, '+ Shot'),
      h('button', { onclick: () => addShot(true), title: 'Duplicate this shot (Ctrl+Shift+T)' }, 'Duplicate'),
      ib('prev', 'Move this shot earlier (Alt+←)', () => moveShot(-1)), ib('next', 'Move this shot later (Alt+→)', () => moveShot(1)),
      ib('trash', 'Delete this shot', () => deleteShot())),
    g('Play', ib('start', 'First frame (Home)', () => goto(0)), ib('prev', 'Previous frame (←)', () => goto(frame - 1)), ib('play', 'Play / pause (Space)', togglePlay, 'play-btn'),
      ib('next', 'Next frame (→)', () => goto(frame + 1)), ib('end', 'Last frame (End)', () => goto(project.length - 1)), box, h('span', { class: 'clock', id: 'clock' })),
    g('Keys', h('button', { onclick: () => keyGroup(BUNNY_IDS.concat(FACE_IDS)), title: 'Key Bunny\'s whole pose and face (K)' }, 'Key pose'),
      h('button', { onclick: () => keyGroup(CAM_IDS), title: 'Key the camera (Shift+K)' }, 'Key camera'),
      ib('trash', 'Delete selected key (Delete)', deleteSelected), ease,
      h('button', { 'aria-pressed': String(!!project.stepped), onclick: toggleStepped, title: 'Stepped blocking: every key holds until the next one, in the viewport and the render. Turn it off for smooth in-betweens.' }, 'Stepped'),
      (() => { const s = h('select', { title: 'Show only these keys on the timeline', 'aria-label': 'Key filter' }, ...Object.entries(FILTERS).map(([k, n]) => h('option', { value: k }, n))); s.value = keyFilter; s.addEventListener('change', () => { keyFilter = s.value; drawTracks(); }); return s; })()),
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
  ruler.append(...markerEls(polCtx(), ppf));
  const rows = [h('div', { class: 'ruler' }, h('div', { class: 'tname' }, 'TIME'), ruler)];
  const wave = audioInfo() && waveform(scene.fps, sceneStart(), project.length, ppf);
  if (wave) rows.push(h('div', { class: 'trow' }, h('div', { class: 'tname', title: audioInfo().path }, 'Audio'), lane([wave])));
  const groups = [['Bunny', filterIds(keyFilter, BUNNY_IDS.concat(FACE_IDS))], ['Camera', filterIds(keyFilter, CAM_IDS)]].filter(g => g[1].length);
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

let last = 0, loopPlay = true;
function togglePlay() {
  playing = !playing;
  $('#play-btn').replaceChildren(icon(playing ? 'pause' : 'play'));
  if (playing) { last = performance.now(); playAudio(sceneStart() / scene.fps + frame / project.fps); requestAnimationFrame(tick); }
  else stopAudio();
}
function tick(t) {
  if (!playing) return;
  const adv = (t - last) * project.fps / 1000;
  if (adv >= 1) { last += Math.floor(adv) * 1000 / project.fps; const nf = frame + Math.floor(adv); if (nf >= project.length && !loopPlay) { frame = project.length - 1; apply(); togglePlay(); return; } if (nf >= project.length) playAudio(sceneStart() / scene.fps); frame = nf % project.length; for (const k of Object.keys(preview)) delete preview[k]; apply(); }
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
  if (!still && !preview && !(await diskOk(polCtx()))) return null;
  scene.name = $('#shot-name').value || scene.name;
  try {
    const r = await api('render', { name: scene.name, code: project.code, still: still ? (stillFrame ?? frame) + 1 : null, preview, audio: project.audio?.path || null, shot: bridge(project) });
    toast(r.message || 'Render started');
    pollRender();
    return r;
  } catch (e) { toast('Render failed to start: ' + e.message, 5000); throw e; }
}
async function renderScene(preview = false, checked = false) {
  if (!preview && !checked) return runPreflight(true);
  if (!preview && !(await diskOk(polCtx(), 10))) return null;
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
window.ds3dRenderDone = j => { lastRender = j; chime(j.state === 'done'); if (j.kind === 'carousel' && j.state === 'done') finishCarousel(carCtx(), j).catch(e => toast('Could not add the bubbles: ' + e.message, 5000)); toast(`${j.id}: ${j.state}${j.rules ? ' · rules ' + j.rules : ''}`, 5000); pollRender(); };
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
    // your own shortcuts win (Help › Keyboard shortcuts)
    const mine = myKeys.get()[comboOf(e)];
    if (mine) { const cmd = polCtx().commands().find(x => cmdId(x) === mine); if (cmd) { e.preventDefault(); runCommand(cmd); return; } }
    // Keydial keys, same as Doodle Studio: Shift+arrows 10 frames, [ ] dial steps, = - dolly, L loop
    if (e.shiftKey && !c && (k === 'ArrowLeft' || k === 'ArrowRight')) { e.preventDefault(); goto(frame + (k === 'ArrowLeft' ? -10 : 10)); return; }
    if (k === '[' || k === ']') { goto(frame + (k === '[' ? -1 : 1)); return; }
    if (!c && (k === '=' || k === '+' || k === '-')) { pushUndo('Dolly'); setValue('cam.dist', current('cam.dist') * (k === '-' ? 1.1 : 1 / 1.1)); drawTracks(); return; }
    if (!c && k.toLowerCase() === 'l') { loopPlay = !loopPlay; toast(loopPlay ? 'Playback loops' : 'Playback stops at the end'); return; }
    if (!c && k.toLowerCase() === 'n') { reviewNote(); return; }
    if (!c && k.toLowerCase() === 'b') { tapBeat(); return; }
    if (c && k.toLowerCase() === 'c' && !e.shiftKey) { poseBuf.copy = poseNow(); toast('Pose copied'); return; }
    if (c && k.toLowerCase() === 'v' && !e.shiftKey) { if (poseBuf.copy) putPose(poseBuf.copy); return; }
    if (c && k.toLowerCase() === 'k') { e.preventDefault(); commandSearch(polCtx()); }
    else if (c && k.toLowerCase() === 'h' && !e.shiftKey) { e.preventDefault(); historyDialog(prodCtx()); }
    else if (c && k.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo(); }
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
    else if (k.toLowerCase() === 'm' && !c) addMarker(polCtx());
    else if (k.toLowerCase() === 'o' && !c) { view3.onion = !view3.onion; apply(); }
    else if (k.toLowerCase() === 'g') view.grid.visible = !view.grid.visible;
    else if (k === 'F1') { e.preventDefault(); showHelp(); }
  });
}

function refreshAll() {
  $('#shot-name').value = scene.name;
  layout(); buildPanel(); buildTimelineTools(); drawTracks(); apply();
}

function loop() {
  const t = performance.now();
  view.render();
  perf('3D view', performance.now() - t);
  if (popOpen()) perf('pop-out window', popDraw(view.renderer.domElement));
  if (fpsTick() && fpsText()) updateHud();
  requestAnimationFrame(loop);
}

// ---------------------------------------------------------------- boot
(async () => {
  try { if (localStorage.getItem('ds3d.theme') === 'dark') document.body.dataset.theme = 'dark'; } catch {}
  data = charData.bunny = await (await fetch('bunny3d.json')).json();
  view = new Viewport($('#view'), data);
  BUNNY_IDS = PARTS.flatMap(p => p[2]);
  buildMenu(); buildTabs(); buildRail(); bindViewport(); bindKeys(); bindCameraPresets(presetCtx());
  $('.topbar h1').after(h('div', { id: 'quickbar', role: 'toolbar', 'aria-label': 'Favourites and recent commands' }));
  bindResizers(wfCtx());
  overlayDraw = bindOverlay(carCtx());
  $('#auto-key').addEventListener('click', e => { autoKey = !autoKey; e.currentTarget.setAttribute('aria-pressed', String(autoKey)); e.currentTarget.textContent = autoKey ? 'Auto' : 'Manual'; });
  $('#render-btn').addEventListener('click', () => renderScene());
  $('#shot-name').addEventListener('change', e => { scene.name = e.target.value; dirty = true; });
  new ResizeObserver(() => { if (!window.__fixedSize) { layout(); drawTracks(); } }).observe($('#canvas-wrap'));
  refreshAll();
  if (scene.audio?.path) loadAudio(api, scene.audio.path).then(drawTracks).catch(() => {});
  window.ds3dLibraryExtra = () => EXTRA.map(({ ask, def, ...r }) => r);
  window.ds3d = {
    get project() { return project; }, get scene() { return scene; }, set scene(s) { useScene(migrate(s)); }, goto, setValue, keyGroup, view, get frame() { return frame; },
    // MCP surface (called by the desktop host)
    controls: () => [...BUNNY_IDS, ...FACE_IDS, ...CAM_IDS].map(id => {
      const [min, max] = DISCRETE.has(id) ? [0, ({ expression: data.face.faces.length, gaze: data.face.gazes.length, mouth: data.face.speech.length, blink: 5 })[id] - 1] : range(id);
      return { id, label: LABEL[id] || id, min, max, group: id.startsWith('cam.') ? 'camera' : FACE_IDS.includes(id) ? 'face' : PARTS.find(p => p[2].includes(id))?.[1] };
    }),
    names: () => ({ expressions: data.face.faces, gazes: data.face.gazes, mouths: data.face.speech }),
    state: () => ({ scene: scene.name, character: character(), stage: stageOf(scene, project), items: project.items || [], markers: project.markers || [], shot: project.code, shotName: project.label, shots: scene.shots.map((s, i) => ({ index: i, code: s.code, name: s.label, length: s.length, active: i === scene.active })),
      frame, length: project.length, fps: scene.fps, width: scene.width, height: scene.height, autoKey, file: filePath, unsaved: dirty,
      values: Object.fromEntries([...BUNNY_IDS, ...FACE_IDS, ...CAM_IDS].map(id => [id, round(current(id))])),
      idle: { ...idleOf(project), events: idleNow()?.events || [] },
      keyed: Object.fromEntries(Object.entries(project.tracks).map(([id, ks]) => [id, ks.map(k => [k.f, round(k.v), k.ease])])) }),
    setValues(values, at, key) {
      pushUndo('Set ' + Object.keys(values).map(id => LABEL[id] || id).slice(0, 3).join(', ') + (Object.keys(values).length > 3 ? '…' : ''));
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
    async renderScene(opts = {}) {
      if (opts.preview) return renderScene(true);
      const r = preflight(prodCtx(), scene, { envelope: envelopeNow(), project2d: projector(prodCtx()) });
      if (!r.ok) throw Error('The export preflight blocks this render: ' + r.checks.filter(c => !c.ok).map(c => `${c.label} (${c.detail})`).join('; ') + '. Fix these, or the user can override in Tools › Check before export.');
      return renderScene(false, true);
    },
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
    storyboard: () => storyboard(),
    importAudio: p => importAudio(p ?? null),
    audioDrive: (id, a, b, opts) => driveFromAudio(id, a, b, opts),
    turntable() { pushUndo(); const y = current('cam.yaw'); setKey(project, 'cam.yaw', 0, y, 'linear'); setKey(project, 'cam.yaw', project.length - 1, y + 360, 'linear'); apply(); drawTracks(); return this.state(); },
    story(a = {}) {
      const out = { retention: () => retentionCheck(), chapters: () => exportChapters(), loop_back: () => { pushUndo(); const r = loopBack(scene); dirty = true; apply(); drawTracks(); return r; },
        gags: () => gags(scene), bible: () => { if (a.bible) { pushUndo(); scene.bible = { ...(scene.bible || {}), ...a.bible }; dirty = true; } return scene.bible || {}; } }[a.action];
      if (!out) throw Error('action must be retention, chapters, loop_back, gags or bible');
      return out();
    },
    animTool(a) {
      const c = animCtx();
      if (a.frame != null) goto(a.frame);
      const part = a.part && PARTS.find(p => p[0] === a.part);
      const out = {
        breakdown: () => breakdown(c, a.amount ?? 50),
        overlap: () => { if (!part) throw Error('part: ' + PARTS.map(p => p[0]).join(', ')); return overlap(c, part[2], a.amount ?? 2); },
        simplify: () => simplify(c, a.amount ?? 0.75),
        loop_check: () => loopCheck(c),
        make_loop: () => makeLoop(c),
        retime: () => retime(c, 1 / (a.amount || 1), a.frame ?? 0),
        stepped: () => { project.stepped = a.on ?? !project.stepped; apply(); buildTimelineTools(); return { stepped: project.stepped }; },
        onion: () => { view3.onion = a.on ?? !view3.onion; apply(); return { onion: view3.onion }; },
        silhouette: () => { setSilhouette(view, a.on ?? !view3.silhouette); return { silhouette: view3.silhouette }; },
        mirror_view: () => { setMirror(a.on ?? !view3.mirror); return { mirror: view3.mirror }; },
        playblast: () => playblast(c),
        turntable: () => window.ds3d.turntable(),
      }[a.action];
      if (!out) throw Error('action must be breakdown, overlap, simplify, loop_check, make_loop, retime, stepped, onion, silhouette, mirror_view, playblast or turntable');
      return out();
    },
    addMarker(f, note) { return addMarker(polCtx(), f ?? frame, note ?? ''); },
    saveVersion: label => saveVersion(polCtx(), label || 'version'),
    autosave: (p = {}) => { const s = setAutosave(p); startAutosave(polCtx()); return s; },
    mirrorPose(at) { if (at != null) goto(at); putPose(mirrorValues(poseNow())); return this.state(); },
    blendPoses(a, b, t, at) { if (at != null) goto(at); poseBuf.A = a; poseBuf.B = b; blendPose(Math.max(0, Math.min(100, Number(t)))); return this.state(); },
    setShotLook(p) { pushUndo(); if (p.horizonLock != null) project.horizonLock = !!p.horizonLock; if (p.ink != null) project.ink = Math.max(40, Math.min(250, Number(p.ink))); apply(); buildPanel(); return { shot: project.code, horizonLock: !!project.horizonLock, ink: project.ink ?? 100 }; },
    removeItem(i) { const r = removeItem(libCtx(), i); if (tab === 'library') buildPanel(); return r; },
    stage: () => ({ character: character(), stage: stageOf(scene, project), sceneStage: scene.stage || {}, shotStage: project.stage || {}, items: project.items || [] }),
    save: () => saveShot(false, true),
    undo, redo,
    // workflow.js (MCP tool "workflow")
    workflow(a = {}) {
      const c = wfCtx();
      const out = {
        templates: () => TEMPLATES.map(t => ({ id: t.id, name: t.name, shots: t.shots })),
        from_template: () => c.newFromTemplate(a.template),
        status: () => { if (a.status) { const i = a.shot != null ? shotIndex(a.shot) : scene.active; return shotStatus(a.status, i); } return scene.shots.map(s => ({ code: s.code, status: statusOf(s) })); },
        split: () => { if (a.shot != null) selectShot(a.shot); return splitHere(a.frame ?? frame); },
        split_sentences: () => { if (a.shot != null) selectShot(a.shot); return splitSentences(a.transcript || ''); },
        beats: () => { if (a.shot != null) selectShot(a.shot); return { beats: markBeats() }; },
        rules: () => { if (a.frame != null) goto(a.frame); return { frame, ...(view.ruleCheck() || {}), lineWeight: project.ink ?? 100 }; },
        snap: () => { snap.on = a.on ?? !snap.on; updateHud(); return { snap: snap.on }; },
        layouts: () => Object.keys(layouts.get()),
        save_layout: () => saveLayout(c, a.name || 'Claude'),
        use_layout: () => useLayout(c, a.name),
        shortcuts: () => ({ builtIn: c.commands().filter(x => x.key).map(x => ({ command: cmdId(x), key: x.key })), mine: myKeys.get() }),
      }[a.action];
      if (!out) throw Error('action must be templates, from_template, status, split, split_sentences, beats, rules, snap, layouts, save_layout, use_layout or shortcuts');
      return out();
    },
    // production.js (MCP tool "production")
    async production(a = {}) {
      const c = prodCtx();
      const out = {
        history: () => c.history().map((e, i) => ({ index: i, label: e.label, at: new Date(e.at).toISOString() })),
        undo_to: () => { if (a.index == null) throw Error('index from history'); jumpTo(Number(a.index)); return { undoLeft: undoStack.length }; },
        presets: () => presets(),
        preset: () => applyPreset(c, a.name),
        preflight: () => { const r = preflight(c, scene, { envelope: envelopeNow(), project2d: projector(c) }); return { ok: r.ok, checks: r.checks }; },
        moderator_pass: () => { pushUndo('Moderator PASS'); return recordModeratorPass(scene, a.note || 'recorded by the moderator over MCP'); },
        estimate: () => estimate(c, sceneFrames(), !!a.preview),
        health: () => health(c),
        fix: () => healthFix(c, a.fix),
        pack: () => pack(c),
        batch: async () => {
          const jobs = [{ name: scene.name, scene }];
          for (const f of a.files || []) { const r = await api('open-file', { file: f }); jobs.push({ name: r.project.name, scene: migrate(r.project) }); }
          return runBatch(c, jobs, { preview: !!a.preview, sleep: false });
        },
        change_log: () => ({ changes: claude.list(), meter: claude.meter(scene) }),
        revert_change: () => claude.revert(c, Number(a.index)),
        meter: () => claude.meter(scene),
      }[a.action];
      if (!out) throw Error('action must be history, undo_to, presets, preset, preflight, moderator_pass, estimate, health, fix, pack, batch, change_log, revert_change or meter');
      return out();
    },
  };
  refreshQuickbar();
  try { restoreLastLayout(wfCtx()); } catch {}
  document.body.dataset.ready = '1';
  loop();
  await offerRecovery(polCtx());
  startAutosave(polCtx());
})().catch(e => { document.body.append(h('pre', { style: 'position:fixed;inset:40px;background:#1F1F1D;color:#E0A64B;padding:16px;z-index:999' }, 'Doodle Studio 3D could not start:\n' + (e.stack || e))); });
