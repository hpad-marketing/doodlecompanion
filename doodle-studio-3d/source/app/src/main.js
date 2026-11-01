// Doodle Studio 3D: editor shell. Same look as Doodle Studio; 3D-specific workflow.
import * as THREE from 'three';
import { Viewport } from './viewport.js';
import { cameraPresetsPanel, bindCameraPresets } from './camera-presets.js';
import { carouselPanel, bindOverlay, finishCarousel, carouselOf, exportCarousel, SIZES, KINDS, TAILS } from './carousel.js';
import { TRACK_IDS } from './rig.js';
import { newScene, newShotData, migrate, nextCode, bindShot, valueAt, frameValues, setKey, deleteKey, hasKey, toBridgeShot, idleFor, stageOf, materialsOf, CAM_DEFAULT, EASES, DISCRETE, defaults } from './project.js';
import { autosaveSettings, setAutosave, startAutosave, autosaveNow, offerRecovery, saveVersion, versionsDialog, commandSearch, addMarker, markerEls, chime, diskOk, toggleFps, fpsTick, fpsText } from './polish.js';
import { breakdown, overlap, simplify, loopCheck, makeLoop, retime, view3, drawOnion, setSilhouette, setMirror, FILTERS, filterIds, playblast } from './animtools.js';
import { loadAudio, audioInfo, play as playAudio, stop as stopAudio, waveform, audioDrive, lipsync as audioLipsync, loadStem, envelope as audioEnvelope, streamFrom as audioStreamFrom, wavBase64, processVoice, decodeChannels, playSamples } from './audio.js';
import { retention, chapters, loopBack, gags, bibleDialog } from './storytime.js';
import { libraryRows, libraryInfo, loadLibrary, useItem, setStage, removeItem, CHARACTERS, CATEGORIES, EXTRA } from './library.js';
import { idleOf, IDLE_DEFAULT, IDLE_RANGE } from './idle.js';
import { modal, historyDialog, claude, changeLogDialog, presets, presetsDialog, applyPreset, estimate, preflight, recordModeratorPass, projector, preflightDialog, batchDialog, runBatch, health, fix as healthFix, healthDialog, pack, cacheDialog } from './production.js';
import { keys as myKeys, comboOf, cmdId, hotkeyDialog, layouts, saveLayout, useLayout, restoreLastLayout, bindResizers, popOut, popOpen, popDraw, noteRun, toggleFav, recentIds, isFav, quickbar, snap, snapValue, perf, heavy, STATUS, statusOf, setStatus, nextStatus, TEMPLATES, fromTemplate, templateDialog, drawNote, showNotes, detectBeats, splitShotAt, splitBySentences } from './workflow.js';
import * as A2 from './animtools2.js';
import * as S2 from './storytime2.js';
import * as P from './post.js';
import * as F2 from './features2.js';
import * as PW from './powers.js';
import * as DR from './drawings.js';
import { DrawingStage } from './drawings3d.js';
import * as CS from './cast.js';
import * as DOCK from './ux2d.js';
import * as ST from './stage3d.js';
import * as MR from './mirror.js';
import * as BB from './babblescene.js';
import * as BK from './blocks.js';
import * as VF from './voicefx.js';
import * as STT from './transcribe.js';
import * as MAT from './materials.js';
import { VOICES as BB_VOICES, STYLES as BB_STYLES, DIALS as BB_DIALS, MOODS as BB_MOODS, speak as bbSpeak, voiceFor as bbVoiceFor } from './babble.js';
import { updateLit, LIGHT_PRESETS } from './lit.js';
import { inkBar, makeLighting } from './lightpanel.js';
import { libraryBrowser, faceGrid, mouthGrid, setPanel, wardrobePanel, itemsPanel, libUi, glyphOf } from './libview.js';

const $ = s => document.querySelector(s) || DOCK.query(s);
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
  bubble: 'M4 5h16v11H10l-5 4v-4H4zM8 10h.01M12 10h.01M16 10h.01',
  sync: 'M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3M18 3v4h-4M6 21v-4h4',
  start: 'M5 4v16M19 4 8 12l11 8z', play: 'M7 4v16l13-8z', pause: 'M7 4h4v16H7zM13 4h4v16h-4z', end: 'M19 4v16M5 4l11 8-11 8z',
  prev: 'M15 5l-7 7 7 7', next: 'M9 5l7 7-7 7', key: 'M12 3l9 9-9 9-9-9z', trash: 'M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13',
  orbit: 'M12 5a9 4 0 1 0 0.1 0M4 9l-1 3 3 0', pan: 'M12 3v18M3 12h18M12 3l-3 3M12 3l3 3M12 21l-3-3M12 21l3-3M3 12l3-3M3 12l3 3M21 12l-3-3M21 12l-3 3',
  frame: 'M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4', grid: 'M4 4h16v16H4zM4 12h16M12 4v16',
  prevkey: 'M17 5l-7 7 7 7M7 5v14', nextkey: 'M7 5l7 7-7 7M17 5v14', loop: 'M4 11a7 7 0 0 1 13-4l2 2M20 13a7 7 0 0 1-13 4l-2-2M19 4v5h-5M5 20v-5h5',
  box: 'M4 4h4M12 4h4M20 4v4M20 12v4M20 20h-4M12 20H8M4 20v-4M4 12V8', copy: 'M9 9h11v11H9zM5 15H4V4h11v1', paste: 'M9 3h6v4H9zM7 5H5v16h14V5h-2',
  undo: 'M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-4', redo: 'M15 14l5-5-5-5M20 9H9a5 5 0 0 0 0 10h4', cut: 'M6 4v16M18 4v16M10 12h4',
  mic: 'M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM5 11a7 7 0 0 0 14 0M12 18v3', minus: 'M5 12h14', plus: 'M5 12h14M12 5v14',
  fit: 'M4 12h16M4 12l4-4M4 12l4 4M20 12l-4-4M20 12l-4 4', select: 'M5 3l13 8-6 1.5L9 19z', move: 'M12 3v18M3 12h18M12 3l-3 3M12 3l3 3M12 21l-3-3M12 21l3-3M3 12l3-3M3 12l3 3M21 12l-3-3M21 12l-3 3',
  rotate: 'M20 12a8 8 0 1 1-2.4-5.7M20 4v4h-4', scale: 'M4 20h8v-8H4zM13 11l7-7M14 4h6v6', ik: 'M5 20l5-7 4 3 5-9M19 7a1.5 1.5 0 1 0 .1 0',
  onion: 'M12 4a8 8 0 1 0 .1 0M12 8a4 4 0 1 0 .1 0', popout: 'M14 4h6v6M20 4l-8 8M18 14v6H4V6h6', hand: 'M8 12V5a1.6 1.6 0 0 1 3.2 0v6M11 10V4a1.6 1.6 0 0 1 3.2 0v7M14 10V6a1.6 1.6 0 0 1 3.2 0v8a6 6 0 0 1-12 0v-2l-1.5-2.5a1.5 1.5 0 0 1 2.6-1.5L8 12',
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
  ['body', 'Body', ['bodyTilt', 'torsoBow', 'torsoTwist', 'squashBody']],
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
  'cam.tx': 'Aim left / right', 'cam.ty': 'Aim near / far', 'cam.tz': 'Aim height', 'cam.focus': 'Focus distance', 'cam.fstop': 'Aperture (f-stop)', squash: 'Squash / stretch', squashBody: 'Squash / stretch',
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
  squashBody: 'The belly: plus squashes down and out, minus stretches up and thin. Volume stays the same, the feet stay planted and the face never changes size. Animate › Squash and stretch keys a whole hit for you.',
};
const EXTRA_RANGE = { legReach: [0, 100, 1], earLScale: [50, 150, 1], earRScale: [50, 150, 1], earLSquash: [-50, 30, 1], earRSquash: [-50, 30, 1], noseWiggle: [-100, 100, 1], noseSniff: [0, 100, 1],
  bodyX: [-400, 400, 1], bodyY: [-200, 200, 1], depth: [-4, 4, 0.05], s: [0.3, 2, 0.01], bodyRot: [-45, 45, 1], breath: [0, 90, 1],
  'cam.yaw': [-180, 180, 1], 'cam.pitch': [-60, 89, 1], 'cam.dist': [0.2, 60, 0.05], 'cam.lens': [12, 200, 1], 'cam.roll': [-45, 45, 1],
  'cam.tx': [-10, 10, 0.01], 'cam.ty': [-10, 10, 0.01], 'cam.tz': [-0.5, 10, 0.01], 'cam.focus': [0, 60, 0.05], 'cam.fstop': [0.7, 22, 0.1], squash: [-30, 30, 1], squashBody: [-30, 30, 1] };
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
  const st = $('#statusline'); if (st) { st.textContent = msg; st.title = msg; }
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
  syncReferenceFile();
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
  cameraYaw: () => view.cam.yaw, characterName: () => CHARACTERS.find(c => c[0] === character())?.[1] || 'Character', selectedTarget: selectedLightTarget, itemName: id => libRowMap().get(id)?.name, previewLighting: l => { litPreview = l; apply(); },
  h, api, toast, pushUndo, goto, scene: () => scene, project: () => project, frame: () => frame, data: () => data, lib: libraryInfo,
  trackIds: () => BUNNY_IDS.concat(FACE_IDS), setCharacter: c => setCharacter(c).catch(e => toast(e.message, 5000)),
  changed: keys => { dirty = true; apply(); drawTracks(); if (keys) buildTimelineTools(); updateHud(); },
  rebuild: () => { if (['library', 'stage', 'animate', 'face'].includes(tab)) buildPanel(); },
  // hover previews on the character (nothing is keyed until you add it)
  preview: row => libPreviewStart(row), previewFace: i => libPreviewStart({ face: i }), previewEnd: () => libPreviewStop(),
  added: (row, res) => { if (res?.added && project.items) { const i = project.items.indexOf(res.added); if (i >= 0 && !res.added.hold && ['prop', 'scenery'].includes(row.category)) selectItem(i); } },
  defaultSpot, selectedItem: () => (stage?.selected?.type === 'item' ? stage.selected.index : null), selectItem, editItem, itemTransform, dropItem, duplicateItem,
});
// Materials tab (materials.js): looks on the scene, characters, set or props, drawn by Blender
const matCtx = () => ({ h, api, toast, pushUndo, scene: () => scene, project: () => project, selectedItem: () => (stage?.selected?.type === 'item' ? stage.selected.index : null), selectItem,
  changed: () => { dirty = true; apply(); updateHud(); }, rebuild: () => { if (tab === 'materials') buildPanel(); }, renderFrame: () => render(true), openBlender: () => MR.open() });
// ---------------------------------------------------------------- live stage (stage3d.js): pick, place and move what is in the shot
let stage = null;
const libRowMap = () => { const rows = libraryRows(); if (rowMapFor !== rows) { rowMap = new Map(rows.map(r => [r.id, r])); rowMapFor = rows; } return rowMap; };
let rowMap = new Map(), rowMapFor = null;
// the shadow button and each object's outline. A slider drag previews here; the shot saves when it is let go
let litPreview = null, inkPreview = null;
function toggleShadows(on) {
  const was = !!stageOf(scene, project).shadows;
  on ??= !was;
  setStage(libCtx(), on ? { shadows: true } : { shadows: false, halftone: null }, libUi.shotOnly);
  if (tab === 'stage') buildPanel();
  toast(on ? 'Shadows on: the whole scene, characters included' : 'Shadows off: flat Doodle look');
}
function inkTarget() {
  const s = stage?.selected, st = stageOf(scene, project);
  if (s?.type === 'piece') return { id: 'piece:' + s.id, key: s.id, name: s.obj?.userData?.dsl_label || s.id, value: inkPreview?.id === 'piece:' + s.id ? inkPreview.value : st.inks?.[s.id] ?? 100 };
  if (s?.type === 'bunny') return { id: 'lead', key: '@lead', name: CHARACTERS.find(c => c[0] === character())?.[1] || 'Character', value: inkPreview?.id === 'lead' ? inkPreview.value : st.inks?.['@lead'] ?? 100 };
  if (s?.type === 'item') { const it = project.items?.[s.index]; if (it && stage.items[s.index]?.cat) return { id: 'item:' + s.index, index: s.index, name: libRowMap().get(it.id)?.name || it.id, value: inkPreview?.id === 'item:' + s.index ? inkPreview.value : it.ink ?? 100 }; }
  return null;
}
function setInk(key, value, save) {
  inkPreview = save ? null : { id: key.id, value };
  if (save) {
    if (key.index != null) editItem(key.index, { ink: value === 100 ? null : value }, 'Outline');
    else {
      const inks = { ...(stageOf(scene, project).inks || {}), [key.key]: value };
      if (value === 100) delete inks[key.key];
      setStage(libCtx(), { inks: Object.keys(inks).length ? inks : null }, libUi.shotOnly);
    }
  }
  apply();
}
const selectedLightTarget = () => { const s = stage?.selected; return s?.type === 'bunny' ? 'lead' : s?.type === 'item' ? 'item:' + s.index : null; };
function liveStage() {
  const st = stageOf(scene, project);
  if (litPreview) st.lighting = litPreview;
  if (inkPreview && !inkPreview.id.startsWith('item:')) st.inks = { ...(st.inks || {}), [inkPreview.id === 'lead' ? '@lead' : inkPreview.id.slice(6)]: inkPreview.value };
  return st;
}
const liveItems = () => { const n = inkPreview?.id.startsWith('item:') ? +inkPreview.id.slice(5) : -1, all = project.items || []; return n < 0 ? all : all.map((it, i) => (i === n ? { ...it, ink: inkPreview.value } : it)); };
const stageCtx = () => ({ api, toast, snap: () => snap.on, rows: libRowMap, items: () => project.items || [], picture: id => { const r = libRowMap().get(id); return r?.preview ? '/lib/' + r.preview : null; },
  changed: () => requestAnimationFrame(() => { apply(); updateHud(); }), pushUndo: l => pushUndo(l),
  editItem: (i, patch, label) => editItem(i, patch, label, true), editPiece,
  // once a new item's model is in: stand it beside the character (level with him, never in front), clear of his body
  autoFit: (it, i, half) => {
    if (!autoPlaced.has(it)) return;
    autoPlaced.delete(it);
    const pts = view.bodyPoints(null, 20), xs = pts.map(p => p.x), cx = (Math.min(...xs) + Math.max(...xs)) / 2, bh = (Math.max(...xs) - Math.min(...xs)) / 2;
    const side = Math.sign(it.at[0] - cx) || 1, others = (project.items || []).filter(o => o !== it && o.at && !o.hold && Math.sign(o.at[0] - cx) === side).length;
    const x = cx + side * (bh + half + 0.06 + others * (half * 2 + 0.06));
    it.at = [+x.toFixed(3), it.at[1], it.at[2]];
    requestAnimationFrame(() => { apply(); drawTracks(); if (tab === 'stage') buildPanel(); });
  },
  setBunny: (v, done) => { if (done) { dirty = true; drawTracks(); buildPanel(); return; } const was = autoKey; for (const [id, x] of Object.entries(v)) setValue(id, round(x), { now: false }); apply(); } });
const autoPlaced = new WeakSet();   // added items still to be spaced out once their model's size is known
function defaultSpot(item) {
  if (item) autoPlaced.add(item);
  // beside the character, on the floor, a little apart from what is already there
  const n = (project.items || []).filter(i => i.at && !i.hold).length, S = data.S || 1, U = 100 * 0.00205066345 * 490 * 0.4;
  const x0 = current('bodyX') / U * S, y0 = current('depth') * S;
  // inside the frame: no further out than 3/4 of the half-width the camera sees at his distance
  const cam = view.camera, halfW = current('cam.dist') * Math.tan(cam.fov * Math.PI / 360) * cam.aspect;
  const side = n % 2 ? -1 : 1, step = Math.min(0.36 + 0.16 * Math.floor(n / 2), Math.max(0.3, halfW * 0.75));
  return [+(x0 + side * step).toFixed(3), +y0.toFixed(3), 0];
}
function selectItem(i, mode) {
  if (!stage) return;
  stage.select(i == null ? null : { type: 'item', index: i }, mode);
  if (tab === 'stage' && sub.stage === 'items') buildPanel();
  drawTracks();
  updateHud();
}
function editItem(i, patch, label = 'Place item', undoDone = false) {
  const it = project.items?.[i];
  if (!it) return;
  if (!undoDone && label !== null) pushUndo(label);
  for (const [k, v] of Object.entries(patch)) if (v === undefined || v === null) delete it[k]; else it[k] = v;
  if ('frame' in patch) project.items.sort((a, b) => a.frame - b.frame);
  dirty = true;
  apply(); drawTracks();
  if (tab === 'stage') buildPanel();
}
function itemTransform(i) { const it = project.items?.[i] || {}; return { at: it.at || [0, 0, 0], rot: it.rot || [0, 0, 0], scale: it.scale || [1, 1, 1] }; }
function dropItem(i) { const xf = itemTransform(i); editItem(i, { at: [xf.at[0], xf.at[1], 0] }, 'Drop to floor'); }
function duplicateItem(i) {
  const it = project.items?.[i];
  if (!it) return;
  pushUndo('Duplicate item');
  const copy = JSON.parse(JSON.stringify(it));
  if (!copy.hold) { const a = copy.at || [0, 0, 0]; copy.at = [+(a[0] + 0.4).toFixed(3), a[1], a[2]]; }
  project.items.push(copy);
  project.items.sort((a, b) => a.frame - b.frame);
  dirty = true; apply(); drawTracks();
  selectItem(project.items.indexOf(copy));
}
function editPiece(id, xf) {
  // the shot's own stage when it has its own pieces (or the stage scope is this shot), else the scene's
  const target = libUi.shotOnly || project.stage?.pieces ? (project.stage ||= {}) : (scene.stage ||= {});
  const p = { ...(stageOf(scene, project).pieces || {}) };
  if (!xf || (!xf.at?.some(Boolean) && !xf.rot && (xf.scale ?? 1) === 1)) delete p[id]; else p[id] = xf;
  if (Object.keys(p).length) target.pieces = p; else delete target.pieces;
  dirty = true; apply();
}
// the sun as turned in Blender over the live link (stage.sun, applied by stage.py at render)
function setSun(sun) {
  const target = libUi.shotOnly || project.stage?.sun || project.stage?.pieces ? (project.stage ||= {}) : (scene.stage ||= {});
  target.sun = { rot: sun.rot, energy: sun.energy };
  dirty = true;
}
// Open in Blender (mirror.js): what the live link may read and change
const mirrorCtx = () => ({ api, toast, bridge: () => bridge(project), code: () => project.code, frame: () => frame, project: () => project, scene: () => scene,
  stage: () => stageOf(scene, project), character: () => character(), playing: () => playing, goto, pushUndo,
  setValue: (id, v) => setValue(id, v, { now: false }), editPiece: (id, xf) => editPiece(id, xf), setSun, markDirty: () => { dirty = true; },
  reapply: () => apply(), refresh: () => { drawTracks(); if (tab === 'stage' || tab === 'pose' || tab === 'camera') buildPanel(); } });
function openInBlender() { if (playing) togglePlay(); return MR.open(); }

// library hover preview: the motion plays (or the face shows) on the character, keyed nowhere
let libPrev = null;
async function libPreviewStart(row) {
  libPreviewStop();
  if (playing) return;
  if (row.face != null) { libPrev = { values: () => ({ expression: row.face }) }; apply(); return; }
  if (row.category === 'expression') {
    const d = row.data || {}, F = data.face, e = F.faces.findIndex(x => x.toLowerCase() === String(d.expression_name || row.name).toLowerCase());
    const v = {}; if (e >= 0) v.expression = e; else if (d.expression != null) v.expression = d.expression; if (d.gaze >= 0) v.gaze = d.gaze; if (d.blink != null) v.blink = d.blink;
    libPrev = { values: () => v }; apply(); return;
  }
  if (row.category !== 'motion') return;
  const token = libPrev = { values: () => ({}) };
  let m;
  try { m = await api('library-motion', { id: row.id }); } catch { return; }
  if (libPrev !== token) return;
  const poses = m.poses, n = Math.max(1, m.frames || (poses.length ? poses[poses.length - 1][0] + 1 : 1)), t0 = performance.now();
  const base = { bodyX: current('bodyX'), bodyY: current('bodyY'), depth: current('depth'), turn: current('turn') }, first = poses[0]?.[1] || {};
  const held = {};
  token.values = () => {
    const f = Math.floor((performance.now() - t0) / 1000 * scene.fps) % (n + 12);
    const out = {};
    for (const [pf, vals] of poses) { if (pf > f) break; Object.assign(held, vals); }
    for (const [id, v] of Object.entries(held)) out[id] = id in base ? base[id] + v - (first[id] ?? v) : v;
    return out;
  };
  token.timer = setInterval(() => { if (libPrev === token) apply(); }, 1000 / scene.fps);
  $('#frame')?.append(h('div', { class: 'preview-badge', id: 'preview-badge' }, 'Preview: ' + row.name));
}
function libPreviewStop() {
  if (!libPrev) return;
  clearInterval(libPrev.timer);
  libPrev = null;
  $('#preview-badge')?.remove();
  apply();
}
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

function setValue(id, v, { record = true, now = true } = {}) {
  const [lo, hi] = range(id);
  if (!DISCRETE.has(id)) v = snapValue(id, v, LENSES);
  if (!DISCRETE.has(id)) v = Math.max(lo, Math.min(hi, v));
  if (autoKey && record) { keyAt(id, v); delete preview[id]; dirty = true; scheduleTracks(); }
  else preview[id] = v;
  if (now) apply();
}

// a key at the playhead in the base or the layer being edited, so the final pose shows v
function keyAt(id, v) {
  const t = DISCRETE.has(id) ? project : T();
  setKey(t, id, frame, project.layers?.length ? +A2.keyValue(project, t, id, frame, v).toFixed(3) : v);
}
let tracksQueued = false;
function scheduleTracks() { if (tracksQueued) return; tracksQueued = true; requestAnimationFrame(() => { tracksQueued = false; drawTracks(); }); }

function apply() {
  const vals = {};
  for (const id of BUNNY_IDS.concat(FACE_IDS)) vals[id] = current(id);
  // idle life plays in the viewport too, except on a value being tried out unkeyed
  const idle = idleNow()?.frames[frame];
  if (idle) for (const [id, v] of Object.entries(idle)) if (!(id in preview)) vals[id] = v;
  if (libPrev) Object.assign(vals, libPrev.values());
  if (pathWhat && !playing) {
    const sig = JSON.stringify([project.tracks, project.layers, project.length, loadedChar]);
    if (sig !== pathSig) { const t = performance.now(); pathPts = A2.pathOf(anim2Ctx(), pathWhat); pathPops = A2.arcCheck(pathPts); pathSig = sig; perf('motion path', performance.now() - t); }
  }
  view.pose(vals);
  view.group.visible = !isolated('lead') && BK.visibleAt(project, frame, project.length);
  syncCostars();
  const cam = {};
  for (const id of CAM_IDS) cam[id.slice(4)] = current(id);
  if (project.horizonLock) cam.roll = 0;
  view.setCamera(cam);
  MR.onApply(frame, vals, cam);
  if (stage) { const t = performance.now(), st = liveStage(); stage.sync({ stage: st, noInk: MAT.outlinesOff(materialsOf(scene, project)), paint: MAT.stagePaint(materialsOf(scene, project), project.items || [], api, () => apply()), items: liveItems(), frame, length: project.length, rows: libRowMap(), playing }); updateLit(view, stage, st); perf('stage', performance.now() - t); }
  // live checks first, so the HUD below shows this frame's lights
  if (ruleLights) { const t = performance.now(); rules = view.ruleCheck(); perf('rule lights', performance.now() - t); }
  if (balanceOn) { balanceNow = A2.balance(view); drawCog(); }
  syncPanel();
  drawPlayhead();
  updateHud();
  overlayDraw?.();
  drawDrawings();
  drawPost();
  if (view3.onion || onionShown) { const t = performance.now(); drawOnion(animCtx()); onionShown = view3.onion; perf('onion skin', performance.now() - t); }
  showNotes(project, frame);
  if (pathWhat && pathPts) A2.drawPath(anim2Ctx(), pathPts, pathKeys(), pathPops);
  A2.syncReference(sceneStart() / scene.fps + frame / project.fps, playing);
}
let ruleLights = true, rules = null;
let onionShown = false;

// ---------------------------------------------------------------- storytime part 2 (storytime2.js)
const s2Ctx = () => ({ ...anim2Ctx(), faces: () => data.face.faces, gazes: () => data.face.gazes, envelope: envelopeNow, sceneStart, selectShot: i => selectShot(i),
  changed: lengthToo => { dirty = true; apply(); drawTracks(); if (lengthToo) buildTimelineTools(); updateHud(); } });
const safeName = n => String(n || 'Untitled').replace(/[\\/:*?"<>|]/g, '_').trim();
async function storyRun(action, a = {}) {
  try { const r = await story2({ action, ...a }); if (r?.message) toast(r.message, 5000); return r; } catch (e) { toast(e.message, 5000); return null; }
}
async function story2(a) {
  const c = s2Ctx(), F = a.frame ?? frame;
  const done = (r, message) => ({ ...r, message });
  switch (a.action) {
    case 'cold_open': { pushUndo('Cold open'); const r = S2.coldOpen(scene, a.shot != null ? shotIndex(a.shot) : scene.active, { seconds: a.seconds ?? 3, card: a.text || 'Earlier that day...' }); dirty = true; useScene(scene); return done(r, `Cold open: the last ${r.seconds} s of ${r.from} now opens the video, then "${r.card}"`); }
    case 'beat_map': return S2.beatMap(scene);
    case 'add_beat': { pushUndo('Beat marker'); const r = S2.addBeat(scene, a.beat); dirty = true; drawTracks(); return r; }
    case 'mood': { pushUndo('Mood'); const i = a.shot != null ? shotIndex(a.shot) : scene.active; const r = S2.setMood(scene.shots[i], a.mood || null, a.light !== false); dirty = true; useScene(scene); return r; }
    case 'moods': return scene.shots.map(s => ({ shot: s.code, mood: s.mood || null }));
    case 'genre': return done(S2.genreMoment(c, a.genre, F), `${S2.GENRES[a.genre]?.name} at frame ${F}`);
    case 'gestures': { const r = S2.gesturesFromVoice(c, { strength: a.strength ?? 1 }); buildTimelineTools(); return done(r, `${r.gestures} gestures on the "Gestures" layer (head and body only)`); }
    case 'eye_darts': { const r = S2.eyeDarts(c, { every: a.every ?? 1.4, seed: a.seed ?? 7 }); return done(r, `${r.darts} eye darts`); }
    case 'jump_scare': return done(S2.jumpScare(c, F), `Jump scare at frame ${F}: quiet second before, sting, fast eased push in`);
    case 'foley': { const r = S2.autoFoley(c); return done(r, `Auto foley: ${r.sounds.length} sounds (re-run replaces them)`); }
    case 'freeze_label': return done(S2.freezeLabel(c, F, a.text, a.seconds ?? 1.5), 'Freeze-frame label added');
    case 'chapter_cards': { pushUndo('Chapter cards'); const r = S2.chapterCards(scene); dirty = true; apply(); return done(r, `${r.cards} chapter card${r.cards === 1 ? '' : 's'} added`); }
    case 'sponsor': { pushUndo('Sponsor segue'); const r = S2.sponsorSegue(scene, scene.active, a.name, a.seconds ?? 8); scene.active += 1; dirty = true; useScene(scene); return done(r, `Sponsor segue ${r.shot} added`); }
    case 'shorts_plan': return S2.shortsPlan(scene).map(x => ({ ...x, seconds: +((x.to - x.from) / scene.fps).toFixed(1) }));
    case 'shorts': {
      const plan = S2.shortsPlan(scene);
      if (!plan.length) throw Error('Add markers like "short: The fall" (or Chapter markers) where each Short starts');
      const root = (await api('settings', {})).rendersRoot, made = [];
      for (const seg of plan) {
        const sh = S2.makeShort(scene, seg);
        if (audioInfo()) {
          const sec0 = seg.from / scene.fps, sec1 = seg.to / scene.fps;
          const w = await api('write-file', { path: `${root}/${safeName(sh.name)}/work/${safeName(sh.name)}_voice.wav`, data: wavBase64(sec0, sec1) });
          sh.audio = { path: w.path };
        }
        const r = await api('save', { project: sh, auto: true });
        made.push({ name: sh.name, shots: sh.shots.length, seconds: +((seg.to - seg.from) / scene.fps).toFixed(1), path: r.path });
      }
      return done({ shorts: made }, `${made.length} Short${made.length > 1 ? 's' : ''} saved as 9:16 scenes: ${made.map(m => m.name).join(', ')}`);
    }
    case 'retention': {
      const sec = sceneFrames() / scene.fps, r = S2.parseRetention(a.csv || '', sec);
      pushUndo('Retention overlay'); scene.retention = r; dirty = true; drawTracks();
      return done({ points: r.points.length, drops: r.drops }, r.drops.length ? `Biggest drop: ${r.drops[0].lost}% at ${r.drops[0].at} s (marked mustard on the timeline)` : 'Retention curve on the timeline');
    }
    case 'retention_clear': { if (scene.retention) { pushUndo('Clear retention'); delete scene.retention; dirty = true; drawTracks(); } return { retention: null }; }
  }
  throw Error('action must be cold_open, beat_map, add_beat, mood, moods, genre, gestures, eye_darts, jump_scare, foley, freeze_label, chapter_cards, sponsor, shorts_plan, shorts, retention or retention_clear');
}
function retentionImport() {
  const inp = h('input', { type: 'file', accept: '.csv,text/csv' });
  inp.addEventListener('change', async () => { const f = inp.files[0]; if (f) storyRun('retention', { csv: await f.text() }); });
  inp.click();
}
function beatMapDialog() {
  const m = S2.beatMap(scene);
  modal({ h }, 'Story beat map', close => [
    h('p', { class: 'hint' }, `Mark a beat with a marker note like "beat: Climax". ${m.seconds} s in all; suggested times follow a classic storytime shape.`),
    h('div', { class: 'beat-bar' }, ...m.beats.map(b => h('i', { class: b.at != null ? 'on' : '', style: `left:${(100 * (b.at ?? b.suggested) / Math.max(1, m.seconds)).toFixed(1)}%`, title: `${b.name}: ${b.at != null ? b.at + ' s' : 'missing, suggested ' + b.suggested + ' s'}` }))),
    h('div', { class: 'ds-list' }, ...m.beats.map(b => h('div', { class: 'row' }, h('b', { style: 'min-width:9em' }, b.name), h('span', {}, b.at != null ? `${b.at} s · ${b.where}` : `missing (try ${b.suggested} s)`),
      b.at == null ? h('button', { onclick: () => { close(); storyRun('add_beat', { beat: b.id }).then(() => beatMapDialog()); } }, 'Add marker') : null))),
    h('button', { onclick: close }, 'Close')]);
}

// ---------------------------------------------------------------- storytime part 3 (post.js): looks, cut-ins, captions, music bed, bleeps, voices
// Laid over and under the rendered shots when Blender joins them. Cut-ins live on the shot
// (shot.cuts), the look too (shot.look); captions and the music bed on the scene.
const shotStarts = () => { let n = 0; return scene.shots.map(s => { const a = n; n += s.length; return a; }); };
const imgCache = new Map(), imgReady = new Map();
function photoImage(p) {
  if (!imgCache.has(p)) imgCache.set(p, api('read-image', { path: p }).then(r => { const im = new Image(); im.src = `data:${r.type || 'image/png'};base64,${r.data}`; return im.decode().then(() => { imgReady.set(p, im); return im; }); }));
  return imgCache.get(p);
}
const cutRect = (c, W, H) => c.kind === 'bubble' ? { cx: c.x ?? 0.64, cy: c.y ?? 0.22, w: c.size ?? 0.3, h: (c.size ?? 0.3) * H / W }
  : P.pipRect(c, c.shotRef ? W / H : (c.aspect || 16 / 9));
const cutsAt = (s, f) => (s.cuts || []).filter(c => f >= c.frame && f < c.frame + c.length);
function captionWord(l, f) { const n = P.captionLines(l.text).flat().length; return Math.min(n - 1, Math.floor((f - l.f) / Math.max(1, l.to - l.f) * n)); }
// the head's screen height (0 top, 1 bottom) in the live view, for caption placement
function liveHeadY() { try { view.camera.updateMatrixWorld(); return (1 - view.headPoint().project(view.camera).y) / 2; } catch { return null; } }
// ---------------------------------------------------------------- drawings (drawings.js): SVGs and hand lines on their own layer
let drawStage = null, drawSel = 0, solo = null;
const isolated = key => solo != null && solo !== key;
function drawDrawings() {
  const list = (project.drawings || []).filter(d => !d.hidden && !isolated('d:' + d.id));
  drawStage?.sync(list, frame);
  const fr = $('#frame');
  let c = document.getElementById('drawing-layer');
  if (!list.some(d => d.layer === 'screen')) { c?.remove(); return; }
  if (!c) { c = h('canvas', { id: 'drawing-layer' }); fr.insertBefore(c, $('#post-layer') || $('#hud')); }
  const pr = Math.min(2, window.devicePixelRatio || 1), W = c.width = Math.round(fr.clientWidth * pr), H = c.height = Math.round(fr.clientHeight * pr);
  // the same line the render lays on: Bunny's ink for this frame size, never under 3 px on screen
  DR.drawScreen(c.getContext('2d'), W, H, { drawings: list }, frame, Math.max(3 * pr, DR.INK_PX_1920 * Math.max(W, H) / 1920 * (project.ink ?? 100) / 100));
}
async function drRun(a) { try { const r = await dr(a); if (r?.message) toast(r.message, 5000); return r; } catch (e) { toast(e.message, 5000); return null; } }
async function dr(a = {}) {
  const done = (r, message) => ({ ...r, message });
  const changed = () => { dirty = true; apply(); updateHud(); drawTracks(); if (tab === 'draw') buildPanel(); };
  const list = () => DR.drawingsOf(project).map((d, i) => ({ index: i, id: d.id, name: d.name, layer: d.layer, x: d.x, y: d.y, size: d.size, rot: d.rot, depth: d.depth, frame: d.frame, build: d.build, until: d.until, noise: d.noise, boil: d.boil, colour: d.colour, strokes: d.strokes.length, placed: d.layer === 'scene' ? !!d.world : undefined }));
  const fit = (art, size) => Math.min(size ?? 0.35, 0.85 * (scene.width / scene.height) / Math.max(0.1, art.aspect || 1));
  switch (a.action || 'list') {
    case 'list': return { drawings: list() };
    case 'import': {
      let text = a.svg;
      if (!text && a.path) text = (await api('read-svg', { path: a.path })).text;
      if (!text) throw Error('Give svg (the SVG text) or path (an .svg file on this PC)');
      const art = DR.parseSvg(text);
      pushUndo('Import SVG drawing');
      const d = DR.add(project, art, { ...a, name: a.name || (a.path ? a.path.split(/[\\/]/).pop().replace(/\.svg$/i, '') : 'Drawing'), frame: a.frame ?? frame, size: fit(art, a.size) });
      if (d.layer === 'scene') DR.place(d, view);
      drawSel = DR.drawingsOf(project).length - 1; changed();
      return done({ index: drawSel, strokes: d.strokes.length, layer: d.layer }, `"${d.name}" drawn on ${d.layer === 'scene' ? 'in the 3D scene' : 'over the screen'} from frame ${d.frame} (${d.strokes.length} lines)`);
    }
    case 'draw': {
      // strokes: [[[x, y], ...], ...] frame fractions, y down: hand lines become one drawing where they were drawn
      const raw = (a.strokes || []).map(s => s.map(([x, y]) => [x * scene.width / scene.height, y])).filter(s => s.length > 1);
      if (!raw.length) throw Error('Draw at least one line');
      let x0 = 9, y0 = 9, x1 = -9, y1 = -9;
      for (const s of raw) for (const [x, y] of s) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
      const art = DR.normalise(raw);
      pushUndo('Draw on the screen');
      const d = DR.add(project, art, { ...a, name: a.name || 'Hand drawing', frame: a.frame ?? frame, x: (x0 + x1) / 2 / (scene.width / scene.height), y: (y0 + y1) / 2, size: Math.max(0.02, y1 - y0) });
      if (d.layer === 'scene') DR.place(d, view);
      drawSel = DR.drawingsOf(project).length - 1; changed();
      return done({ index: drawSel, strokes: d.strokes.length }, `Hand drawing draws on from frame ${d.frame}`);
    }
    case 'set': {
      const i = a.index ?? drawSel;
      pushUndo('Change drawing');
      const was = DR.drawingsOf(project)[i]?.layer;
      const d = DR.set(project, i, a);
      // a scene drawing moves when its spot changes: placed again from this camera
      if (d.layer === 'scene' && (was !== 'scene' || ['x', 'y', 'size', 'depth', 'place'].some(k => a[k] != null) || !d.world)) DR.place(d, view);
      changed(); return done({ drawing: list()[i] }, null);
    }
    case 'place': { const d = DR.drawingsOf(project)[a.index ?? drawSel]; if (!d) throw Error('No such drawing'); pushUndo('Place drawing'); if (d.layer !== 'scene') DR.set(project, a.index ?? drawSel, { layer: 'scene' }); DR.place(d, view); changed(); return done({ world: d.world }, `"${d.name}" stands where this camera sees it`); }
    case 'remove': { pushUndo('Remove drawing'); DR.remove(project, a.index ?? drawSel); drawSel = Math.max(0, Math.min(drawSel, DR.drawingsOf(project).length - 1)); changed(); return done({ drawings: list() }, 'Drawing removed'); }
    case 'clear': { pushUndo('Clear drawings'); delete project.drawings; changed(); return done({}, 'Drawings cleared'); }
    default: throw Error('action must be list, import, draw, set, place, remove or clear');
  }
}
function importSvg(layer = 'screen') {
  const inp = h('input', { type: 'file', accept: '.svg,image/svg+xml' });
  inp.addEventListener('change', async () => { const f = inp.files[0]; if (!f) return; await drRun({ action: 'import', svg: await f.text(), name: f.name.replace(/\.svg$/i, ''), layer, noise: drawNew.noise, boil: drawNew.boil }); showDrawing(); });
  inp.click();
}
// draw by hand on the frame: the lines become a drawing that draws on from the playhead
function drawOnScreen() {
  const fr = $('#frame');
  document.getElementById('stick-layer')?.remove(); document.querySelector('.stick-bar')?.remove();
  const cv = h('canvas', { id: 'stick-layer' }), strokes = [];
  fr.append(cv);
  const redraw = () => { const g = cv.getContext('2d'); g.clearRect(0, 0, cv.width, cv.height); g.strokeStyle = DR.COLOURS.ink; g.lineWidth = Math.max(3, DR.INK_PX_1920 * Math.max(cv.width, cv.height) / 1920); g.lineCap = g.lineJoin = 'round'; for (const s of strokes) { g.beginPath(); s.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke(); } };
  let cur = null;
  const xy = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.addEventListener('pointerdown', e => { cv.setPointerCapture(e.pointerId); cur = [xy(e)]; strokes.push(cur); });
  cv.addEventListener('pointermove', e => { if (cur) { cur.push(xy(e)); redraw(); } });
  cv.addEventListener('pointerup', () => { cur = null; });
  const layer = h('select', { 'aria-label': 'Which layer' }, h('option', { value: 'screen' }, 'On the screen (over everything)'), h('option', { value: 'scene' }, 'In the 3D scene (1 m behind)'));
  const close = () => { cv.remove(); bar.remove(); };
  const bar = h('div', { class: 'stick-bar' }, h('span', {}, 'Draw: the lines draw on from the playhead and boil like the 2D cutaways'), layer,
    h('button', { class: 'primary', onclick: async () => { const W = cv.width, H = cv.height; close(); await drRun({ action: 'draw', layer: layer.value, depth: 1, noise: drawNew.noise, boil: drawNew.boil, strokes: strokes.map(s => s.map(([x, y]) => [x / W, y / H])) }); showDrawing(); } }, 'Make it a drawing'),
    h('button', { onclick: () => { strokes.length = 0; redraw(); } }, 'Clear'), h('button', { onclick: close }, 'Cancel'));
  fr.append(bar);
  cv.width = fr.clientWidth; cv.height = fr.clientHeight; redraw();
}
// the noise a new drawing starts with, and the named amounts of line boil
const drawNew = { noise: 0.5, boil: 2 };
const NOISE_STEPS = [['Still', 0, 2], ['Soft', 0.25, 3], ['Hand drawn', 0.5, 2], ['Shaky', 1, 2]];
// open the Draw workspace on the newest drawing, finished, so its line and noise show at once
function showDrawing() {
  setTab('draw');
  const d = DR.drawingsOf(project)[drawSel];
  if (d) goto(d.frame + Math.max(0, d.build));
}
// Noise row: a slider that moves the line live, how often it boils, and the named amounts.
// set(patch) keeps a change (noise, boil); live(v) follows the slider, live(null) when it is picked up
function noiseRow(value, boilEvery, set, live) {
  const out = h('span', { class: 'hint', style: 'min-width:3em;display:inline-block' }, `${Math.round(value * 100)}%`);
  const sl = h('input', { type: 'range', min: 0, max: 100, step: 1, value: Math.round(value * 100), 'aria-label': 'Noise', style: 'width:180px', title: 'Line boil: how much the hand-drawn line wobbles (0 = still)',
    onpointerdown: () => live?.(null), oninput: e => { out.textContent = `${e.target.value}%`; live?.(Number(e.target.value) / 100); }, onchange: e => set({ noise: Number(e.target.value) / 100 }) });
  const every = h('input', { type: 'number', min: 1, max: 12, step: 1, value: boilEvery, style: 'width:56px', 'aria-label': 'Boil every', title: 'A new wobble every this many frames (2 = on twos)', onchange: e => set({ boil: Math.max(1, Math.min(12, Math.round(Number(e.target.value) || 1))) }) });
  return h('div', { class: 'row dr-row' }, h('b', { class: 'dr-grp' }, 'Noise'), sl, out, h('label', { class: 'dr-f' }, 'Boil every', every),
    ...NOISE_STEPS.map(([n, v, b]) => h('button', { 'aria-pressed': String(value === v && boilEvery === b), title: `${n}: noise ${Math.round(v * 100)}%, a new wobble every ${b} frames`, onclick: () => set({ noise: v, boil: b }) }, n)));
}
// Draw workspace: a picture of each drawing, and its settings in rows
function drawingsPanel() {
  const all = DR.drawingsOf(project);
  drawSel = Math.max(0, Math.min(drawSel, all.length - 1));
  const head = h('div', { class: 'row', style: 'flex-wrap:wrap;gap:6px' },
    h('button', { class: 'primary', title: 'Import an SVG: every line and shape outline becomes an ink line that draws on from the playhead', onclick: () => importSvg('screen') }, 'Import SVG…'),
    h('button', { title: 'Draw lines by hand on the frame', onclick: () => drawOnScreen() }, 'Draw on the screen…'),
    all.length ? h('button', { onclick: () => drRun({ action: 'clear' }) }, 'Clear all') : null,
    h('span', { class: 'hint' }, 'Drawings sit on their own layer, apart from the characters, like the 2D studio. One line weight (Bunny\'s), ink or mustard only.'));
  if (!all.length) return h('div', {}, head, h('p', { class: 'hint' }, 'No drawings on this shot yet. New drawings start with this noise:'), noiseRow(drawNew.noise, drawNew.boil, o => { Object.assign(drawNew, o); buildPanel(); }));
  const cards = h('div', { class: 'char-cards', role: 'list' }, ...all.map((d, i) => h('button', { class: 'libx-card', role: 'listitem', 'aria-pressed': String(i === drawSel), title: `${d.name}: ${d.layer === 'scene' ? 'in the 3D scene' : 'on the screen'}, from frame ${d.frame}`, onclick: () => { drawSel = i; goto(d.frame + Math.max(0, d.build)); buildPanel(); } },
    h('img', { src: DR.thumb(d, 64), alt: '', width: 64, height: 64 }), h('span', {}, d.name))));
  const d = all[drawSel], i = drawSel;
  const setv = (k, v) => drRun({ action: 'set', index: i, [k]: v });
  const num = (label, k, v, min, max, step, tip, scale = 1) => { const inp = h('input', { type: 'number', min, max, step, value: v == null ? '' : +(v * scale).toFixed(1), style: 'width:64px', 'aria-label': label, title: tip }); inp.addEventListener('change', () => setv(k, inp.value === '' ? null : Number(inp.value) / scale)); return h('label', { class: 'dr-f', title: tip }, label, inp); };
  const sel = (label, k, opts, tip) => { const s = h('select', { 'aria-label': label, title: tip }, ...opts.map(([v, n]) => h('option', { value: v, selected: d[k] === v }, n))); s.addEventListener('change', () => setv(k, s.value)); return h('label', { class: 'dr-f', title: tip }, label, s); };
  const grp = (name, ...kids) => h('div', { class: 'row dr-row' }, h('b', { class: 'dr-grp' }, name), ...kids.filter(Boolean));
  // the slider moves the line as it goes; letting go keeps it as one undo step
  let noiseWas = d.noise;
  const noiseLive = v => {
    if (v == null) { noiseWas = d.noise; if (!DR.stateAt(d, frame)) goto(d.frame + Math.max(0, d.build)); return; }
    d.noise = v; apply();
  };
  const noiseSet = o => { Object.assign(drawNew, o); d.noise = noiseWas; drRun({ action: 'set', index: i, ...o }); };
  return h('div', {}, head, cards, noiseRow(d.noise, d.boil, noiseSet, noiseLive),
    grp('Where',
      sel('Layer', 'layer', [['screen', 'On the screen'], ['scene', 'In the 3D scene']], 'On the screen: over everything, like a 2D cutaway. In the 3D scene: stands in the world, so characters can pass in front of it.'),
      sel('Colour', 'colour', [['ink', 'Ink'], ['mustard', 'Mustard']], 'Brand colours only'),
      num('Across %', 'x', d.x, -50, 150, 1, 'Centre, left to right across the frame', 100), num('Down %', 'y', d.y, -50, 150, 1, 'Centre, top to bottom', 100),
      num('Size %', 'size', d.size, 2, 300, 1, 'Height as a percent of the frame height', 100), num('Turn °', 'rot', d.rot, -180, 180, 1, 'Turn it'),
      d.layer === 'scene' ? num('Depth m', 'depth', d.depth ?? 1, -3, 20, 0.1, 'Metres behind the character (minus is in front)') : null,
      d.layer === 'scene' ? h('button', { title: 'Stand it where this camera sees it now', onclick: () => drRun({ action: 'place', index: i }) }, 'Place from this camera') : null),
    grp('When',
      num('Starts at frame', 'frame', d.frame, 0, 100000, 1, 'Frame it starts drawing on'),
      h('button', { title: 'Start drawing on at the playhead', onclick: () => setv('frame', frame) }, 'Start at playhead'),
      num('Draws on over', 'build', d.build, 0, 600, 1, 'Frames to draw every line, one after another (0 = appears at once)'),
      num('Gone at frame', 'until', d.until, 0, 100000, 1, 'Frame it disappears (empty = stays to the end of the shot)'),
      h('button', { title: 'Disappear at the playhead', onclick: () => setv('until', Math.max(d.frame + 1, frame)) }, 'Gone at playhead')),
    h('div', { class: 'row', style: 'margin-top:8px' }, h('button', { title: `Remove ${d.name} (Ctrl+Z brings it back)`, onclick: () => drRun({ action: 'remove', index: i }) }, 'Remove')));
}
function drawPost() {
  const fr = $('#frame'), s = project, cap = P.captionAt(scene, s, frame), cuts = cutsAt(s, frame);
  let c = document.getElementById('post-layer');
  if (!s.look && !cuts.length && !cap) { c?.remove(); return; }
  if (!c) { c = h('canvas', { id: 'post-layer' }); fr.insertBefore(c, $('#hud')); }
  const W = c.width = fr.clientWidth, H = c.height = fr.clientHeight, g = c.getContext('2d');
  if (s.look) P.drawLook(g, W, H, s.look);
  for (const k of cuts) {
    const r = cutRect(k, W, H);
    if (k.kind === 'photo') { const im = imgReady.get(k.path); if (im) P.drawPhoto(g, W, H, im, k); else photoImage(k.path).then(() => drawPost()).catch(() => {}); }
    else if (k.kind === 'pip') P.drawOutline(g, W, H, r);
    else P.drawBubble(g, W, H, r);
    if (k.kind !== 'photo') { g.font = `${Math.round(H * 0.025)}px system-ui`; g.textAlign = 'center'; g.fillStyle = '#1F1F1D'; g.fillText(k.shotRef || (k.path || '').split(/[\\/]/).pop(), r.cx * W, r.cy * H); }
  }
  if (cap) P.drawCaption(g, W, H, cap.text, P.captionY(scene, cap.text, liveHeadY()), scene.captions.highlight ? captionWord(cap, frame) : -1, scene.captions.snap !== false);
}
const pngOf = (W, H, draw) => { const c = document.createElement('canvas'); c.width = W; c.height = H; draw(c.getContext('2d')); return c.toDataURL('image/png').split(',')[1]; };
// what one render lays on top: indices are the shots in it, in order; full adds the sound side
async function buildPost(indices, full) {
  const shots = indices.map(i => scene.shots[i]), caps = scene.captions ? scene.captions.tracks[scene.captions.active] || [] : [];
  const markers = full ? (() => { const st = shotStarts(); return scene.shots.flatMap((s, i) => (s.markers || []).map(m => ({ F: st[i] + m.f, note: String(m.note || '') }))).sort((a, b) => a.F - b.F); })() : [];
  const spans = P.markerSpans(markers, scene.fps);
  const trans = full ? PW.transitionsOf(scene.shots) : [];
  const any = shots.some(s => s.look || s.cuts?.length || s.drawings?.some(d => d.layer === 'screen') || caps.some(l => l.shot === s.uid)) || (full && (scene.music?.path || spans.bleeps.length || spans.voices.length || scene.paper || trans.length));
  if (!any) return null;
  await P.loadFont();
  const W = scene.width, H = scene.height, safe = safeName(scene.name), dir = `${(await api('settings', {})).rendersRoot}/${safe}/work/post`;
  let n = 0;
  const write = async (draw, name = 'layer') => (await api('write-file', { path: `${dir}/${String(++n).padStart(3, '0')}_${name}.png`, data: pngOf(W, H, draw) })).path;
  const post = { looks: [], overlays: [], movies: [], drawings: [] };
  let at = 0;
  for (const [k, s] of shots.entries()) {
    // screen drawings: one PNG per distinct look of the layer, held for as long as it lasts
    if (s.drawings?.some(d => d.layer === 'screen')) {
      const made = new Map(), ink = DR.INK_PX_1920 * Math.max(W, H) / 1920 * (s.ink ?? 100) / 100;
      for (const run of DR.screenRuns(s, s.length)) {
        if (!made.has(run.sig)) made.set(run.sig, await write(g => DR.drawScreen(g, W, H, s, run.t, ink), 'drawing'));
        post.drawings.push({ path: made.get(run.sig), start: at + run.start, length: run.length });
      }
    }
    if (s.look && P.LOOK_STRIP[s.look]) {
      const ov = [{ path: await write(g => P.drawLook(g, W, H, s.look), s.look), blend: 'ALPHA_OVER', alpha: 1 }];
      if (s.look === 'flashback') ov.unshift({ path: await write(g => { g.fillStyle = P.MUSTARD; g.fillRect(0, 0, W, H); }, 'warm'), blend: 'MULTIPLY', alpha: 0.45 });
      post.looks.push({ shot: k, saturation: P.LOOK_STRIP[s.look].saturation, overlays: ov });
    }
    for (const c of s.cuts || []) {
      const len = Math.min(c.length, s.length - c.frame), start = at + c.frame;
      if (len <= 0) continue;
      if (c.kind === 'photo') { const im = await photoImage(c.path); post.overlays.push({ path: await write(g => P.drawPhoto(g, W, H, im, c), 'photo'), start, length: len }); continue; }
      const r = cutRect(c, W, H);
      post.movies.push({ path: c.path || null, shotRef: c.shotRef || undefined, start, length: len, rect: { cx: r.cx, cy: r.cy, w: r.w } });
      post.overlays.push({ path: await write(g => (c.kind === 'pip' ? P.drawOutline : P.drawBubble)(g, W, H, r), c.kind), start, length: len });
    }
    for (const l of caps.filter(x => x.shot === s.uid)) {
      const fit = scene.captions.snap !== false, words = P.captionLines(l.text).flat().length;
      let headY = null;
      if (fit) try { headY = projector(prodCtx())(s, { frame: l.f })?.headY ?? null; } catch {}
      const y = P.captionY(scene, l.text, headY);
      if (!scene.captions.highlight) { post.overlays.push({ path: await write(g => P.drawCaption(g, W, H, l.text, y, -1, fit), 'caption'), start: at + l.f, length: l.to - l.f }); continue; }
      for (let w = 0; w < words; w++) {
        const a = l.f + Math.round(w * (l.to - l.f) / words), b = l.f + Math.round((w + 1) * (l.to - l.f) / words);
        if (b > a) post.overlays.push({ path: await write(g => P.drawCaption(g, W, H, l.text, y, w, fit), 'caption'), start: at + a, length: b - a });
      }
    }
    at += s.length;
  }
  if (full) {
    if (scene.paper) post.paper = { path: await write(g => PW.drawPaper(g, W, H, scene.paper), 'paper'), alpha: +Math.min(1, 0.35 + scene.paper * 0.65).toFixed(2) };
    if (trans.length) post.transitions = trans.map(t => ({ ...t, color: t.kind === 'flash' ? P.MUSTARD : P.INK }));
    post.bleeps = spans.bleeps;
    if (spans.voices.length && audioInfo()) {
      const buf = processVoice(spans.voices.map(v => ({ from: v.from, to: v.to, factor: P.VOICES[v.preset] })), scene.fps);
      if (buf) post.voice = (await api('write-file', { path: `${dir}/${safe.replace(/ /g, '_')}_voices.wav`, data: wavBase64(0, buf.duration, buf) })).path;
    }
    if (scene.music?.path) post.music = { path: scene.music.path, keys: P.duckKeys(envelopeNow(), 0, sceneFrames(), { volume: scene.music.volume ?? 0.35, duck: scene.music.duck ?? 0.35, quiet: spans.quiet }) };
  }
  return post;
}
function cutsDialog() {
  modal({ h }, 'Cut-ins on this shot', close => [
    h('p', { class: 'hint' }, 'A real photo, a narrator picture-in-picture or an imagination bubble, laid over the shot from the playhead when the scene is joined. Ink outlines only, never a box.'),
    h('div', { class: 'ds-list' }, ...(project.cuts || []).map((c, i) => h('div', { class: 'row' }, h('b', { style: 'min-width:7em' }, { photo: 'Photo', pip: 'Narrator PiP', bubble: 'Imagination bubble' }[c.kind]),
      h('span', {}, `frame ${c.frame}, ${(c.length / scene.fps).toFixed(1)} s · ${c.shotRef || (c.path || '').split(/[\\/]/).pop()}`), h('button', { onclick: () => { close(); postRun({ action: 'remove_cut', index: i }); } }, 'Remove')))),
    h('div', { class: 'row', style: 'flex-wrap:wrap' },
      h('button', { onclick: () => { close(); postRun({ action: 'photo' }); } }, 'Add photo…'),
      h('button', { onclick: () => { close(); postRun({ action: 'pip' }); } }, 'Add narrator PiP (video)…'),
      h('button', { onclick: () => { close(); pick2('Imagination bubble plays', [['', 'A video file…'], ...scene.shots.filter((s, i) => i !== scene.active).map(s => [s.code, shotName(s)])], r => postRun({ action: 'bubble', clip_shot: r || undefined })); } }, 'Add imagination bubble…'),
      h('button', { onclick: close }, 'Close'))]);
}
// The animation rules, built in as defaults the render applies while it poses each frame
// (host/blender/lib/constraints.py). Nothing is checked or blocked; each one can be switched
// off for a shot when the idea needs to break it.
const RULES = [
  ['armInFront', 'Arms in front', 'A hand never hides behind the head from the camera: the arm takes the smallest turn, forward first, that brings it in front of the face or clear of the head. Off: hands go exactly where keyed.'],
  ['faceClear', 'Face clear', 'A set piece or placed prop that would block the face or body from the camera slides sideways just enough. Off: everything stays where it was put.'],
  ['propsOnFloor', 'Props on floor', 'Props and set pieces standing on the floor rest their stroke a hair above it, like the characters. Off: they keep their exact height.'],
  ['eyeSize', 'Same eye size', 'Eyes keep one size: the Frog\'s eye bumps ignore EAR Scale and Squash. Off: the eye bumps scale with those values.'],
];
function rulesRow() {
  return h('div', { class: 'row', style: 'flex-wrap:wrap;gap:6px', title: 'Built-in rules: applied while the render poses each frame. Switch one off for this shot when the idea needs it.' },
    h('b', {}, 'Built-in rules'),
    ...RULES.map(([k, label, tip]) => h('button', { 'aria-pressed': String(project.rules?.[k] !== false), title: tip, onclick: () => { pushUndo(); project.rules ||= {}; if (project.rules[k] === false) delete project.rules[k]; else project.rules[k] = false; buildPanel(); } }, label)));
}
function captionsDialog() {
  const c = P.captionsOf(scene);
  modal({ h }, 'Captions', close => {
    const text = h('input', { type: 'text', placeholder: 'Caption at the playhead', style: 'flex:1' }), secs = h('input', { type: 'number', min: 0.3, step: 0.1, value: 1.5, style: 'width:56px', 'aria-label': 'Seconds' });
    const lines = (c.tracks[c.active] || []).filter(l => l.shot === project.uid);
    return [h('div', { class: 'row' }, ...Object.entries(P.LANGS).map(([k, n]) => h('button', { 'aria-pressed': String(c.active === k), onclick: () => { close(); postRun({ action: 'caption_lang', lang: k }).then(() => captionsDialog()); } }, n))),
      h('p', { class: 'hint' }, 'Below the face, inside the safe zone. One to three words stay on one line; longer ones take two. The render uses the language picked here.'),
      h('label', { class: 'row', title: 'On: each caption snaps inside the Instagram safe zone, below the face, and shrinks to fit the width. Off: captions sit exactly at the height set.' }, h('input', { type: 'checkbox', checked: c.snap !== false, onchange: e => { pushUndo(); c.snap = e.target.checked ? undefined : false; drawPost(); } }), ' Keep captions in the safe zone, below the face'),
      h('div', { class: 'row' }, text, secs, h('button', { onclick: () => { if (text.value.trim()) { close(); postRun({ action: 'caption', text: text.value, seconds: Number(secs.value) }).then(() => captionsDialog()); } } }, 'Add')),
      h('div', { class: 'ds-list' }, ...lines.map(l => h('div', { class: 'row' }, h('span', { style: 'min-width:7em' }, `${l.f}–${l.to}`), h('span', {}, l.text)))),
      h('label', { class: 'row' }, h('input', { type: 'checkbox', checked: c.highlight, onchange: e => postRun({ action: 'highlight', on: e.target.checked }) }), ' Highlight each word as it is said'),
      h('div', { class: 'row' }, h('button', { onclick: () => postRun({ action: 'srt_export' }) }, 'Export SRT'),
        h('button', { onclick: () => { const inp = h('input', { type: 'file', accept: '.srt' }); inp.addEventListener('change', async () => { const f = inp.files[0]; if (f) { close(); await postRun({ action: 'srt_import', srt: await f.text() }); captionsDialog(); } }); inp.click(); } }, 'Import SRT…'),
        h('button', { onclick: close }, 'Close'))];
  });
}
function musicDialog() {
  const m = scene.music || {};
  modal({ h }, 'Music bed', close => {
    const vol = h('input', { type: 'range', min: 0, max: 1, step: 0.05, value: m.volume ?? 0.35 }), duck = h('input', { type: 'range', min: 0, max: 1, step: 0.05, value: m.duck ?? 0.35 });
    return [h('p', { class: 'hint' }, `${m.path ? 'Now: ' + m.path.split(/[\\/]/).pop() + '. ' : ''}Plays under the whole scene and dips while the voice talks; a "quiet" marker silences it until the scare.`),
      h('label', { class: 'row' }, 'Volume ', vol), h('label', { class: 'row' }, 'Under the voice ', duck),
      h('div', { class: 'row' }, h('button', { onclick: () => { close(); postRun({ action: 'music', volume: Number(vol.value), duck: Number(duck.value) }); } }, m.path ? 'Keep this track' : 'Pick a track…'),
        m.path ? h('button', { onclick: () => { close(); postRun({ action: 'music', pick: true, volume: Number(vol.value), duck: Number(duck.value) }); } }, 'Pick another…') : null,
        m.path ? h('button', { onclick: () => { close(); postRun({ action: 'music', path: null }); } }, 'Remove') : null, h('button', { onclick: close }, 'Cancel'))];
  });
}
async function postRun(a) { try { const r = await postAct(a); if (r?.message) toast(r.message, 5000); return r; } catch (e) { toast(e.message, 5000); return null; } }
async function postAct(a) {
  const F = a.frame ?? frame, len = Math.max(1, Math.round((a.seconds ?? 2) * scene.fps)), done = (r, message) => ({ ...r, message });
  const changed = () => { dirty = true; drawPost(); drawTracks(); };
  const addCut = c => { pushUndo('Cut-in'); (project.cuts ||= []).push({ ...c, frame: F, length: Math.min(len, project.length - F) }); changed(); return { cuts: project.cuts.length }; };
  switch (a.action) {
    case 'look': { if (a.look && !P.LOOKS[a.look]) throw Error('look must be ' + Object.keys(P.LOOKS).join(' or ') + ', or null'); pushUndo('Shot look'); project.look = a.look || null; changed(); return done({ look: project.look }, a.look ? `${P.LOOKS[a.look]} look on this shot` : 'Look removed'); }
    case 'photo': {
      const p = a.path || (await api('pick-image', {})).path; if (!p) return null;
      await photoImage(p);
      return done(addCut({ kind: 'photo', path: p, x: a.x ?? 0.5, y: a.y ?? 0.32, size: a.size ?? 0.5, tilt: a.tilt ?? -3 }), 'Photo cut-in added');
    }
    case 'pip': case 'bubble': {
      const ref = a.clip_shot != null ? scene.shots[shotIndex(a.clip_shot)].code : null;
      const p = ref ? null : a.path || (await api('pick-video', {})).path; if (!ref && !p) return null;
      const c = a.action === 'pip' ? { kind: 'pip', corner: a.corner || 'tr', size: a.size ?? 0.34 } : { kind: 'bubble', x: a.x ?? 0.64, y: a.y ?? 0.22, size: a.size ?? 0.3 };
      return done(addCut({ ...c, path: p, shotRef: ref || undefined }), a.action === 'pip' ? 'Narrator picture-in-picture added' : 'Imagination bubble added');
    }
    case 'cuts': return (project.cuts || []).map((c, index) => ({ index, ...c }));
    case 'remove_cut': { if (!project.cuts?.[a.index]) throw Error('No cut-in ' + a.index); pushUndo('Remove cut-in'); project.cuts.splice(a.index, 1); changed(); return { cuts: project.cuts.length }; }
    case 'music': {
      pushUndo('Music bed');
      if (a.path === null) { scene.music = null; changed(); return done({ music: null }, 'Music bed removed'); }
      const p = a.path || (!a.pick && scene.music?.path) || (await api('pick-audio', {})).path; if (!p) return null;
      scene.music = { path: p, volume: a.volume ?? scene.music?.volume ?? 0.35, duck: a.duck ?? scene.music?.duck ?? 0.35 }; changed();
      return done({ music: scene.music }, 'Music bed set: it dips under the voice');
    }
    case 'caption': { pushUndo('Caption'); const l = P.addCaption(scene, project, F, F + len, a.text, a.lang); changed(); return done({ line: l }, 'Caption added'); }
    case 'captions': { const c = P.captionsOf(scene), st = shotStarts(); return { active: c.active, highlight: c.highlight, lines: (c.tracks[a.lang || c.active] || []).map(l => ({ ...l, shotIndex: scene.shots.findIndex(s => s.uid === l.shot), sceneFrame: st[scene.shots.findIndex(s => s.uid === l.shot)] + l.f })) }; }
    case 'caption_lang': { if (!P.LANGS[a.lang]) throw Error('lang must be ' + Object.keys(P.LANGS).join(' or ')); P.captionsOf(scene).active = a.lang; changed(); return { active: a.lang }; }
    case 'highlight': { P.captionsOf(scene).highlight = a.on !== false; changed(); return { highlight: scene.captions.highlight }; }
    case 'clear_captions': { pushUndo('Clear captions'); P.captionsOf(scene).tracks[a.lang || scene.captions.active] = []; changed(); return { cleared: true }; }
    case 'srt_import': { pushUndo('Import captions'); const n = P.parseSrt(scene, a.srt || '', a.lang || P.captionsOf(scene).active); changed(); return done({ lines: n }, `${n} caption lines imported`); }
    case 'srt_export': {
      const lang = a.lang || P.captionsOf(scene).active, safe = safeName(scene.name), root = (await api('settings', {})).rendersRoot;
      const w = await api('write-file', { path: `${root}/${safe}/work/${safe.replace(/ /g, '_')}_${lang}.srt`, data: btoa(unescape(encodeURIComponent(P.srt(scene, lang)))) });
      return done({ path: w.path }, 'Wrote ' + w.path);
    }
    case 'build': return buildPost(a.all === false ? [scene.active] : scene.shots.map((_, i) => i), a.all !== false);
    default: throw Error('Unknown post action ' + a.action);
  }
}

// ---------------------------------------------------------------- feature picks part 2 (features2.js)
let previzOn = false;
const f2Ctx = () => ({ ...anim2Ctx(), charName, detectBeats: () => detectBeats(envelopeNow(), sceneStart(), project.length, scene.fps) });
async function featRun(a) { try { const r = await feat(a); if (r?.message) toast(r.message, 5000); return r; } catch (e) { toast(e.message, 5000); return null; } }
async function feat(a) {
  const c = f2Ctx(), F = a.frame ?? frame, done = (r, message) => ({ ...r, message });
  const changed = () => { dirty = true; apply(); drawTracks(); updateHud(); };
  switch (a.action) {
    case 'squash': { pushUndo('Squash and stretch'); const r = F2.squashMove(c, a.kind || 'land', F, a.amount ?? 20); changed(); return done(r, `${F2.SQUASH_MOVES[r.kind]} squash at frame ${F}: anticipation, hit, overshoot, settle`); }
    case 'contact': {
      const limb = a.limb || 'armL', to = Math.min(project.length - 1, a.to ?? F + 24);
      pushUndo('Hand contact'); const r = F2.handContact(c, limb, a.where || 'hip', a.from ?? F, to); changed();
      return done(r, `${F2.CONTACTS[r.where]} (${limb === 'armL' ? 'left' : 'right'}), frames ${r.from}–${r.to}${r.worstErrorCm > 1.5 ? `, off by up to ${r.worstErrorCm} cm: the arm is at its limit` : ''}`);
    }
    case 'beat_cam': { pushUndo('Beat camera'); const r = F2.beatCamera(c, a.style || 'punch', { amount: a.amount ?? 0.08, angles: a.angles || null }); changed(); return done(r, `${F2.BEAT_STYLES[r.style]}: ${r.beats} beats`); }
    case 'save_angle': { const r = F2.saveAngle(c, a.name); dirty = true; return done(r, `Angle "${r.angle}" saved`); }
    case 'angles': return { angles: scene.angles || {} };
    case 'delete_angle': { if (scene.angles) delete scene.angles[a.name]; dirty = true; return { angles: Object.keys(scene.angles || {}) }; }
    case 'cut_to': { pushUndo('Cut to angle'); const r = F2.cutTo(c, a.name, F); changed(); return done(r, `Cut to ${r.angle} at frame ${F}`); }
    case 'cam_markers': { pushUndo('Camera cuts'); const r = F2.camMarkers(c); changed(); return done(r, `${r.cuts.length} cuts from "cam:" markers`); }
    case 'plan_path': { pushUndo('Floor-plan path'); const r = F2.floorPath(c, a.points, a.from ?? F, Math.min(project.length - 1, a.to ?? project.length - 1), a.step ?? 3); changed(); return done(r, `Camera path keyed: ${r.metres} m over frames ${r.from}–${r.to}`); }
    case 'plan_info': return F2.camPlanPos(project, F);
    case 'previz': { previzOn = a.on ?? !previzOn; F2.setPreviz(view, previzOn); apply(); return done({ previz: previzOn }, previzOn ? 'Previz grey: blocking in plain grey' : 'Previz off'); }
    case 'render_previz': { const r = await (a.scene ? renderScene(true, false, true) : render(false, true, null, true)); return { started: !!r }; }
    case 'stick': { pushUndo('Pose from stick figure'); const r = F2.poseFromStick(c, a.strokes || [], a.aspect || view.camera.aspect, F); changed(); return done(r, `Posed from the stick figure (${Object.keys(r.limbs).length} limbs, lean ${r.bodyTilt}°)`); }
    case 'script': return scriptToBlocking(a.text || '', { captions: !!a.captions });
    case 'measure': { const r = F2.measure(view, valuesNow()); apply(); return r; }
    default: throw Error('Unknown action ' + a.action);
  }
}
async function scriptToBlocking(text, { captions = false } = {}) {
  const parsed = F2.parseScript(text, scene.fps);
  if (!parsed.length) throw Error('Paste a script: scene headings (INT. / EXT. or #), lines like "BUNNY: hi", actions in (brackets)');
  await loadLibrary(api);
  const rows = libraryRows(), made = [], missed = [];
  pushUndo('Script to blocking');
  for (const sh of parsed) {
    const code = nextCode(scene, scene.shots.length - 1), s = newShotData(code, Math.max(sh.frames, scene.fps));
    s.label = sh.name.slice(0, 40);
    scene.shots.push(s); scene.active = scene.shots.length - 1; frame = 0; useScene(scene);
    let moves = 0;
    for (const l of sh.lines) {
      if (l.say) {
        project.markers.push({ f: l.f, note: (l.who ? l.who + ': ' : '') + l.say });
        if (captions) P.addCaption(scene, project, l.f, l.f + l.length, l.say, 'en');
      }
      for (const act of l.acts) {
        const r = F2.actionFor(rows, act);
        if (!r) { missed.push(act); continue; }
        try { await useItem(libCtx(), r.id, { frame: l.f, prompt: false }); moves++; } catch { missed.push(act); }
      }
    }
    project.markers.sort((x, y) => x.f - y.f);
    made.push({ shot: s.code, name: s.label, lines: sh.lines.length, moves, seconds: +(s.length / scene.fps).toFixed(1) });
  }
  dirty = true; useScene(scene);
  return { shots: made, missed, message: `${made.length} shot${made.length > 1 ? 's' : ''} blocked from the script${missed.length ? `; no library match for: ${missed.slice(0, 4).join(', ')}` : ''}` };
}
// ---------------------------------------------------------------- Blender powers (powers.js; rendered by powers.py)
const macroRec = PW.recorder();
async function pwRun(a) { try { const r = await pw(a); if (r?.message) toast(r.message, 5000); return r; } catch (e) { toast(e.message, 5000); return null; } }
async function pw(a) {
  const F = a.frame ?? frame, done = (r, message) => ({ ...r, message });
  const changed = (label) => { dirty = true; apply(); drawTracks(); updateHud(); return label; };
  const unproject = (x, y, d) => view.unproject(x, y, d);
  switch (a.action) {
    case 'info': return { powers: project.powers || {}, paper: scene.paper || 0, transition: project.transition || null, links: project.links || [], macros: Object.keys(PW.macros.all()), master: (await api('settings', {})).masterBlend || null };
    case 'doodle': { pushUndo('3D doodle'); const r = PW.addDoodles(project, a.strokes, unproject, { frame: F, draw: a.draw ?? 12, depth: a.depth ?? 0 }); changed(); return done(r, `${r.added} ink doodle${r.added > 1 ? 's' : ''} drawn on from frame ${F}`); }
    case 'clear_doodles': { pushUndo('Clear doodles'); changed(PW.setPower(project, 'doodles', null)); return done({}, '3D doodles cleared'); }
    case 'scatter': { pushUndo('Scatter'); const r = PW.addScatter(project, a.kind || 'grass', a); changed(); return done(r, `${PW.SCATTER[a.kind || 'grass']} scattered (Blender render)`); }
    case 'clear_scatter': { pushUndo('Clear scatter'); PW.setPower(project, 'scatter', null); changed(); return done({}, 'Scatter cleared'); }
    case 'crowd': { pushUndo('Crowd'); const r = PW.setCrowd(project, a.off ? null : a); changed(); return done(r, r.crowd ? `A crowd of ${r.crowd.count} behind ${charName()}, never touching` : 'Crowd removed'); }
    case 'liquid': { pushUndo('Liquid'); const r = PW.addLiquid(project, a.kind || 'splash', F, a.at); changed(); return done(r, `${PW.LIQUIDS[a.kind || 'splash']} at frame ${F}`); }
    case 'clear_liquids': { pushUndo('Clear liquids'); PW.setPower(project, 'liquids', null); changed(); return done({}, 'Liquids cleared'); }
    case 'fisheye': { pushUndo('Fisheye'); const v = Math.max(0, Math.min(1, +(a.amount ?? 0.5))); const r = PW.setPower(project, 'fisheye', v || null); changed(); return done(r, v ? `Fisheye lens ${Math.round(v * 100)}%` : 'Fisheye off'); }
    case 'pano360': { pushUndo('360 video'); const w = a.on === false ? null : Math.max(960, Math.min(7680, Math.round((a.width ?? 3840) / 2) * 2)); const r = PW.setPower(project, 'pano360', w); changed(); return done(r, w ? `360 video: ${w}×${w / 2} equirectangular, tagged for YouTube and VR players` : '360 video off'); }
    case 'autoink': { pushUndo('Auto-ink'); const on = a.on ?? !project.powers?.autoink; const r = PW.setPower(project, 'autoink', on || null); changed(); return done(r, on ? 'Auto-ink: every model without an outline gets Bunny\'s ink' : 'Auto-ink off'); }
    case 'jelly': {
      const it = (project.items || [])[a.item ?? (project.items || []).length - 1];
      if (!it) throw Error('Add a prop from the Library first');
      pushUndo('Jelly prop'); it.jelly = a.on ?? !it.jelly; if (!it.jelly) delete it.jelly; changed();
      return done({ item: it.id, jelly: !!it.jelly }, it.jelly ? `${it.id.replace(/^prop-/, '')} wobbles like jelly from its frame` : 'Jelly off');
    }
    case 'paper': { pushUndo('Paper finish'); const v = Math.max(0, Math.min(1, +(a.amount ?? 0.5))); scene.paper = v || undefined; if (!v) delete scene.paper; dirty = true; return done({ paper: v }, v ? `Paper finish ${Math.round(v * 100)}% on the joined scene` : 'Paper finish off'); }
    case 'transition': {
      if (a.kind && !PW.TRANSITIONS[a.kind]) throw Error('kind must be ' + Object.keys(PW.TRANSITIONS).join(' or ') + ', or null');
      if (a.kind && scene.active === 0) throw Error('The first shot has nothing to transition from');
      pushUndo('Transition'); project.transition = a.kind ? { kind: a.kind, frames: Math.max(2, Math.min(60, Math.round(a.frames ?? 12))) } : null; if (!a.kind) delete project.transition; dirty = true; drawTracks();
      return done({ transition: project.transition || null }, a.kind ? `${PW.TRANSITIONS[a.kind]} into ${shotName(project)}` : 'Hard cut');
    }
    case 'link': { if (!(a.from in LABEL || a.from?.startsWith('cam.')) || !(a.to in LABEL || a.to?.startsWith('cam.'))) throw Error(`from and to must be control ids, e.g. armL, headYaw, cam.yaw (${!(a.from in LABEL || a.from?.startsWith('cam.')) ? a.from : a.to} is not one; list_controls gives them all)`); pushUndo('Link controls'); const r = PW.addLink(project, a.from, a.to, a.factor ?? 1, a.offset ?? 0); changed(); return done(r, `${LABEL[a.to] || a.to} now follows ${LABEL[a.from] || a.from} ×${a.factor ?? 1}`); }
    case 'unlink': { pushUndo('Unlink'); const r = PW.removeLink(project, a.index ?? 0); changed(); return done(r, 'Link removed'); }
    case 'links': return { links: project.links || [] };
    case 'master': { const r = await api(a.path === null ? 'settings' : 'pick-master', a.path === null ? { masterBlend: '' } : { path: a.path }); return done({ master: r.masterBlend || r.master || null }, (r.masterBlend || r.master) ? `Renders use the master Bunny file ${(r.masterBlend || r.master).split(/[\\/]/).pop()}` : 'Renders use the built-in Bunny'); }
    case 'open_master': { const r = await api('open-master', {}); return done(r, r.opened ? `Opened ${r.opened.split(/[\\/]/).pop()} in Blender` : 'No Blender found'); }
    case 'macro_start': { macroRec.start(frame); updateHud(); return done({ recording: true }, 'Recording a macro: menu commands and Claude tool calls, then Blender › Macros › Stop and save'); }
    case 'macro_stop': { const steps = macroRec.stop(); updateHud(); if (!steps.length) throw Error('Nothing was recorded, so no macro was saved. Run menu commands or tool calls between macro_start and macro_stop.'); const name = a.name || `Macro ${Object.keys(PW.macros.all()).length + 1}`; PW.macros.save(name, steps); return done({ name, steps: steps.length }, `Saved "${name}" (${steps.length} steps)`); }
    case 'macros': return { macros: PW.macros.all() };
    case 'macro_play': {
      const steps = PW.macros.all()[a.name];
      if (!steps) throw Error(`No macro "${a.name}"`);
      const start = F, all = menus().flatMap(([g, items]) => items.filter(it => Array.isArray(it)).map(([label, fn]) => ({ g, label, fn })));
      let ran = 0;
      for (const s of steps) {
        goto(Math.max(0, Math.min(project.length - 1, start + s.offset)));
        if (s.tool) { await api('mcp-replay', { name: s.tool, args: s.args }); ran++; continue; }
        const c = all.find(x => x.g === s.group && x.label === s.label);
        if (!c) continue;
        await c.fn(); ran++;
      }
      return done({ name: a.name, ran }, `Played "${a.name}": ${ran} of ${steps.length} steps`);
    }
    case 'macro_delete': { PW.macros.remove(a.name); return { macros: Object.keys(PW.macros.all()) }; }
    default: throw Error('action must be info, doodle, clear_doodles, scatter, clear_scatter, crowd, liquid, clear_liquids, fisheye, pano360, autoink, jelly, paper, transition, link, unlink, links, master, open_master, macro_start, macro_stop, macros, macro_play or macro_delete');
  }
}
function doodleMode() {
  const fr = $('#frame');
  document.getElementById('stick-layer')?.remove(); document.querySelector('.stick-bar')?.remove();
  const cv = h('canvas', { id: 'stick-layer' }), strokes = [];
  fr.append(cv);
  const size = () => { cv.width = fr.clientWidth; cv.height = fr.clientHeight; redraw(); };
  const redraw = () => { const g = cv.getContext('2d'); g.clearRect(0, 0, cv.width, cv.height); g.strokeStyle = '#1F1F1D'; g.lineWidth = 4; g.lineCap = g.lineJoin = 'round'; for (const s of strokes) { g.beginPath(); s.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke(); } };
  let cur = null;
  const xy = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.addEventListener('pointerdown', e => { cv.setPointerCapture(e.pointerId); cur = [xy(e)]; strokes.push(cur); });
  cv.addEventListener('pointermove', e => { if (cur) { cur.push(xy(e)); redraw(); } });
  cv.addEventListener('pointerup', () => { cur = null; });
  const depth = h('select', { 'aria-label': 'Where the doodle sits' }, h('option', { value: '0' }, 'Beside the character'), h('option', { value: '1' }, 'Behind (1 m)'), h('option', { value: '-0.5' }, 'In front (0.5 m)'));
  const draw = h('input', { type: 'number', min: 1, max: 120, value: 12, style: 'width:52px', title: 'Frames it takes to draw on', 'aria-label': 'Draw-on frames' });
  const close = () => { cv.remove(); bar.remove(); };
  const bar = h('div', { class: 'stick-bar' }, h('span', {}, 'Draw ink lines: they stand in 3D space and draw on from the playhead'), depth, h('label', {}, 'draw on ', draw, ' frames'),
    h('button', { class: 'primary', onclick: () => { const W = cv.width, H = cv.height; pwRun({ action: 'doodle', strokes: strokes.map(s => s.map(([x, y]) => [x / W, y / H])), depth: Number(depth.value), draw: Number(draw.value) }); close(); } }, 'Place in 3D'),
    h('button', { onclick: () => { strokes.length = 0; redraw(); } }, 'Clear'), h('button', { onclick: close }, 'Cancel'));
  fr.append(bar);
  size();
}
function powersDialog() {
  const pw0 = project.powers || {};
  modal({ h }, 'Blender powers on this shot', close => {
    const num = (v, min, max, step, w = 56, label) => h('input', { type: 'number', min, max, step, value: v, style: `width:${w}px`, 'aria-label': label });
    const kind = h('select', { 'aria-label': 'Scatter kind' }, ...Object.entries(PW.SCATTER).map(([k, n]) => h('option', { value: k }, n))), count = num(30, 1, 400, 1, 60, 'How many'), radius = num(1.2, 0.2, 6, 0.1, 56, 'Radius in metres');
    const crowdN = num(pw0.crowd?.count ?? 14, 1, 80, 1, 56, 'Crowd size'), fish = num(Math.round((pw0.fisheye || 0) * 100), 0, 100, 5, 56, 'Fisheye percent');
    const liq = h('select', { 'aria-label': 'Liquid' }, ...Object.entries(PW.LIQUIDS).map(([k, n]) => h('option', { value: k }, n)));
    const act = (a) => () => { close(); pwRun(a()); };
    return [
      h('p', { class: 'hint' }, 'These render in Blender. Everything uses ink and mustard at Bunny\'s line weight, and nothing touches the character.'),
      h('div', { class: 'row' }, h('b', { style: 'min-width:6em' }, 'Doodles'), h('button', { onclick: () => { close(); doodleMode(); } }, 'Draw in 3D…'), h('span', { class: 'hint' }, `${(pw0.doodles || []).length} on this shot`), (pw0.doodles || []).length ? h('button', { onclick: act(() => ({ action: 'clear_doodles' })) }, 'Clear') : null),
      h('div', { class: 'row' }, h('b', { style: 'min-width:6em' }, 'Scatter'), kind, count, radius, h('span', { class: 'hint' }, 'm'), h('button', { onclick: act(() => ({ action: 'scatter', kind: kind.value, count: Number(count.value), radius: Number(radius.value) })) }, 'Scatter'), (pw0.scatter || []).length ? h('button', { onclick: act(() => ({ action: 'clear_scatter' })) }, `Clear ${(pw0.scatter || []).length}`) : null),
      h('div', { class: 'row' }, h('b', { style: 'min-width:6em' }, 'Crowd'), crowdN, h('button', { onclick: act(() => ({ action: 'crowd', count: Number(crowdN.value) })) }, pw0.crowd ? 'Update' : 'Add a cheering crowd'), pw0.crowd ? h('button', { onclick: act(() => ({ action: 'crowd', off: true })) }, 'Remove') : null),
      h('div', { class: 'row' }, h('b', { style: 'min-width:6em' }, 'Liquids'), liq, h('button', { onclick: act(() => ({ action: 'liquid', kind: liq.value })) }, 'At the playhead'), (pw0.liquids || []).length ? h('button', { onclick: act(() => ({ action: 'clear_liquids' })) }, `Clear ${(pw0.liquids || []).length}`) : null),
      h('div', { class: 'row', style: 'flex-wrap:wrap' }, h('b', { style: 'min-width:6em' }, 'Lens'), fish, h('span', { class: 'hint' }, '% fisheye'), h('button', { onclick: act(() => ({ action: 'fisheye', amount: Number(fish.value) / 100 })) }, 'Set'),
        h('button', { onclick: act(() => ({ action: 'pano360', on: !pw0.pano360 })) }, pw0.pano360 ? '360 video: on (turn off)' : '360 video'), h('button', { onclick: act(() => ({ action: 'autoink' })) }, pw0.autoink ? 'Auto-ink: on (turn off)' : 'Auto-ink imported models')),
      h('div', { class: 'row' }, h('b', { style: 'min-width:6em' }, 'Props'), h('button', { onclick: act(() => ({ action: 'jelly' })) }, 'Jelly wobble on the last prop'), h('button', { onclick: close }, 'Close')),
    ];
  });
}
function transitionDialog() {
  pick2(`Transition into ${shotName(project)}`, [...Object.entries(PW.TRANSITIONS), ['', 'Hard cut']], k => pwRun({ action: 'transition', kind: k || null }));
}
function linkDialog() {
  const ids = BUNNY_IDS.concat(FACE_IDS, CAM_IDS).filter(id => !DISCRETE.has(id));
  modal({ h }, 'Linked controls', close => {
    const sel = lab => h('select', { 'aria-label': lab }, ...ids.map(id => h('option', { value: id }, LABEL[id] || id)));
    const from = sel('Driver'), to = sel('Follows'), factor = h('input', { type: 'number', step: 0.1, value: 1, style: 'width:56px', 'aria-label': 'Factor' });
    to.selectedIndex = 1;
    return [h('p', { class: 'hint' }, 'One control drives another: the follower moves by the driver\'s change times the factor, on top of its own keys.'),
      h('div', { class: 'ds-list' }, ...(project.links || []).map((l, i) => h('div', { class: 'row' }, h('span', {}, `${LABEL[l.to] || l.to} follows ${LABEL[l.from] || l.from} ×${l.factor}${l.offset ? ` + ${l.offset}` : ''}`), h('button', { onclick: () => { close(); pwRun({ action: 'unlink', index: i }).then(linkDialog); } }, 'Remove')))),
      h('div', { class: 'row', style: 'flex-wrap:wrap' }, to, h('span', {}, 'follows'), from, h('span', {}, '×'), factor, h('button', { class: 'primary', onclick: () => { close(); pwRun({ action: 'link', from: from.value, to: to.value, factor: Number(factor.value) }).then(linkDialog); } }, 'Link'), h('button', { onclick: close }, 'Close'))];
  });
}
function macroDialog() {
  const all = PW.macros.all();
  modal({ h }, 'Macros', close => [h('p', { class: 'hint' }, 'A macro replays menu commands at the same playhead offsets, starting from wherever the playhead is now.'),
    h('div', { class: 'ds-list' }, ...Object.entries(all).map(([n, st]) => h('div', { class: 'row' }, h('b', { style: 'min-width:8em' }, n), h('span', { class: 'hint' }, `${st.length} steps`), h('button', { onclick: () => { close(); pwRun({ action: 'macro_play', name: n }); } }, 'Play here'), h('button', { onclick: () => { close(); pwRun({ action: 'macro_delete', name: n }).then(macroDialog); } }, 'Delete')))),
    h('div', { class: 'row' }, macroRec.on ? h('button', { class: 'primary', onclick: () => { close(); const n = prompt('Name this macro:', `Macro ${Object.keys(all).length + 1}`); pwRun({ action: 'macro_stop', name: n || undefined }); } }, 'Stop and save') : h('button', { class: 'primary', onclick: () => { close(); pwRun({ action: 'macro_start' }); } }, 'Start recording'), h('button', { onclick: close }, 'Close'))]);
}
async function masterDialog() {
  const cur = (await api('settings', {})).masterBlend || '';
  modal({ h }, 'Master Bunny file', close => [h('p', { class: 'hint' }, cur ? `Renders use ${cur}` : 'Renders use the built-in Bunny. A master file is your own copy of Bunny3D_v2.blend with your tweaks; every Bunny render uses it.'),
    h('div', { class: 'row', style: 'flex-wrap:wrap' }, h('button', { class: 'primary', onclick: () => { close(); pwRun({ action: 'master' }); } }, cur ? 'Pick another…' : 'Pick the master .blend…'), h('button', { onclick: () => { close(); pwRun({ action: 'open_master' }); } }, 'Open master in Blender'), cur ? h('button', { onclick: () => { close(); pwRun({ action: 'master', path: null }); } }, 'Use the built-in Bunny') : null, h('button', { onclick: close }, 'Close'))]);
}
// ---------------------------------------------------------------- co-stars (cast.js; Blender side lib/cast.py)
const costarLoading = new Set();
const castName = c => (CHARACTERS.find(x => x[0] === c) || [0, c])[1];
function syncCostars() {
  const list = CS.costarsOf(project), ids = BUNNY_IDS.concat(FACE_IDS), out = [], shown = [];
  for (const [i, c] of list.entries()) {
    const d = c.character === loadedChar ? data : charData[c.character];
    if (!d) {
      if (!costarLoading.has(c.character)) {
        costarLoading.add(c.character);
        fetch(c.character === 'bunny' ? 'bunny3d.json' : `chars/${c.character}.json`).then(r => r.json()).then(j => { charData[c.character] = j; costarLoading.delete(c.character); apply(); }).catch(e => toast(e.message, 5000));
      }
      continue;
    }
    out.push({ data: d, values: CS.costarValues(project, i, ids, frame), x: c.x, y: c.y, turn: c.turn });
    shown.push(!isolated('c' + i) && BK.visibleAt(c, frame, project.length));
  }
  if (out.length || view.actors?.length) view.setCostars(out);
  view.actors?.forEach((a, k) => { a.group.visible = shown[k] !== false; });
}
async function castRun(a) { try { const r = await castAct(a); if (r?.message) toast(r.message, 5000); return r; } catch (e) { toast(e.message, 5000); return null; } }
async function castAct(a) {
  const F = a.frame ?? frame, done = (r, message) => ({ ...r, message }), i = a.index ?? 0;
  const changed = () => { dirty = true; apply(); drawTracks(); updateHud(); };
  const who = () => { const c = CS.costarsOf(project)[i]; if (!c) throw Error(`No co-star ${i}: add one first`); return castName(c.character); };
  switch (a.action) {
    case 'list': return { lead: character(), costars: CS.costarsOf(project).map((c, k) => ({ index: k, character: c.character, x: c.x, y: c.y, turn: c.turn, keyed: Object.keys(c.tracks || {}) })) };
    case 'add': {
      const ch = a.character || CHARACTERS.find(c => c[0] !== character())[0];
      if (!CHARACTERS.some(c => c[0] === ch)) throw Error('character must be one of ' + CHARACTERS.map(c => c[0]).join(', '));
      pushUndo('Add co-star'); const r = CS.addCostar(project, ch, a); changed();
      return done(r, `${castName(ch)} joins ${charName()} in this shot. Renders keep them from ever touching`);
    }
    case 'remove': { const n = who(); pushUndo('Remove co-star'); const r = CS.removeCostar(project, i); changed(); return done(r, `${n} left the shot`); }
    case 'place': { if (a.character && !CHARACTERS.some(c => c[0] === a.character)) throw Error('Unknown character'); pushUndo('Place co-star'); const r = CS.placeCostar(project, i, a); changed(); return done(r, `${who()} at ${r.costar.x} m, ${r.costar.y} m, turned ${r.costar.turn}°`); }
    case 'key': { who(); if (!a.values || typeof a.values !== 'object') throw Error('values: { control: value }'); pushUndo('Key co-star'); const r = CS.keyCostar(project, i, a.values, F); changed(); return done(r, `${who()} keyed at frame ${F}`); }
    case 'copy': { who(); pushUndo('Copy the lead'); const r = CS.copyLead(project, i, BUNNY_IDS.concat(FACE_IDS), a.mirror ?? true, mirrorValues); changed(); return done(r, `${who()} copies ${charName()}'s moves${r.mirrored ? ', mirrored' : ''}`); }
    case 'motion': {
      who();
      const sp = CS.costarProject(project, i);
      const r = await useItem({ ...libCtx(), project: () => sp, frame: () => F }, a.id, { frame: F, mirror: !!a.mirror, blend: a.blend || 0 });
      if (sp.length > project.length) project.length = sp.length;
      changed();
      return done(r, `${who()}: ${r?.name || a.id} from frame ${F}`);
    }
    case 'clear_keys': { who(); pushUndo('Clear co-star keys'); CS.costarsOf(project)[i].tracks = {}; changed(); return done({ index: i }, `${who()} back to rest`); }
    default: throw Error('action must be list, add, remove, place, key, copy, motion or clear_keys');
  }
}
async function castDialog() {
  await loadLibrary(api).catch(() => {});
  const motions = libraryRows().filter(r => r.category === 'motion');
  modal({ h }, 'Co-stars in this shot', close => {
    const rows = CS.costarsOf(project).map((c, i) => {
      const num = (v, step, label) => h('input', { type: 'number', step, value: v, style: 'width:60px', 'aria-label': label });
      const x = num(c.x, 0.05, 'Left / right in metres'), y = num(c.y, 0.05, 'Near / far in metres'), t = num(c.turn, 5, 'Turn in degrees');
      const q = h('input', { type: 'search', placeholder: 'Find a motion', style: 'width:9em', 'aria-label': 'Find a motion' });
      const sel = h('select', { 'aria-label': 'Motion', style: 'max-width:14em' }, ...motions.slice(0, 400).map(m => h('option', { value: m.id }, m.name)));
      q.addEventListener('input', () => { const s = q.value.toLowerCase(); sel.replaceChildren(...motions.filter(m => m.name.toLowerCase().includes(s)).slice(0, 200).map(m => h('option', { value: m.id }, m.name))); });
      return h('div', { class: 'ds-list' },
        h('div', { class: 'row', style: 'flex-wrap:wrap' }, h('b', { style: 'min-width:5em' }, castName(c.character)), h('span', { class: 'hint' }, 'x'), x, h('span', { class: 'hint' }, 'y'), y, h('span', { class: 'hint' }, 'turn'), t,
          h('button', { onclick: () => { close(); castRun({ action: 'place', index: i, x: Number(x.value), y: Number(y.value), turn: Number(t.value) }).then(castDialog); } }, 'Place'),
          h('button', { onclick: () => { close(); castRun({ action: 'remove', index: i }).then(castDialog); } }, 'Remove')),
        h('div', { class: 'row', style: 'flex-wrap:wrap' }, h('button', { onclick: () => { close(); castRun({ action: 'copy', index: i, mirror: true }); } }, `Copy ${charName()}'s moves (mirrored)`),
          h('button', { onclick: () => { close(); castRun({ action: 'copy', index: i, mirror: false }); } }, 'Copy as is'), q, sel,
          h('button', { onclick: () => { close(); castRun({ action: 'motion', index: i, id: sel.value }); } }, 'Play from the playhead'),
          h('button', { onclick: () => { close(); castRun({ action: 'clear_keys', index: i }); } }, 'Clear keys')));
    });
    return [h('p', { class: 'hint' }, `Co-stars share ${charName()}'s rig, look and rules. In the render they are pushed apart, eased, whenever two bodies would touch.`), ...rows,
      CS.costarsOf(project).length < CS.MAX_COSTARS ? h('div', { class: 'row' }, h('div', { class: 'char-cards' }, ...CHARACTERS.map(([id, n]) => h('button', { class: 'libx-card', title: `Add the ${n} as a co-star`, onclick: () => { close(); castRun({ action: 'add', character: id }).then(castDialog); } }, h('span', { class: 'pic', style: 'aspect-ratio:2/3' }, h('img', { src: `chars/${id}.png`, alt: '', draggable: 'false' })), h('span', {}, `Add ${n}`)))), h('button', { onclick: close }, 'Close')) : h('button', { onclick: close }, 'Close')];
  });
}
function stickMode() {
  const fr = $('#frame');
  document.getElementById('stick-layer')?.remove(); document.querySelector('.stick-bar')?.remove();
  const cv = h('canvas', { id: 'stick-layer' }), strokes = [];
  fr.append(cv);
  const size = () => { cv.width = fr.clientWidth; cv.height = fr.clientHeight; redraw(); };
  const redraw = () => { const g = cv.getContext('2d'); g.clearRect(0, 0, cv.width, cv.height); g.strokeStyle = '#1F1F1D'; g.lineWidth = 4; g.lineCap = g.lineJoin = 'round'; for (const s of strokes) { g.beginPath(); s.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke(); } };
  let cur = null;
  const xy = e => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  cv.addEventListener('pointerdown', e => { cv.setPointerCapture(e.pointerId); cur = [xy(e)]; strokes.push(cur); });
  cv.addEventListener('pointermove', e => { if (cur) { cur.push(xy(e)); redraw(); } });
  cv.addEventListener('pointerup', () => { cur = null; });
  const close = () => { cv.remove(); bar.remove(); };
  const bar = h('div', { class: 'stick-bar' }, h('span', {}, 'Draw a stick figure: a head circle, a body line, then arms and legs'),
    h('button', { class: 'primary', onclick: () => { const W = cv.width, H = cv.height; featRun({ action: 'stick', strokes: strokes.map(s => s.map(([x, y]) => [x / W, y / H])), aspect: W / H }); close(); } }, 'Pose it'),
    h('button', { onclick: () => { strokes.length = 0; redraw(); } }, 'Clear'), h('button', { onclick: close }, 'Cancel'));
  fr.append(bar);
  size();
}
function contactDialog() {
  modal({ h }, 'Hand contact', close => {
    const to = h('input', { type: 'number', min: frame, max: project.length - 1, value: Math.min(project.length - 1, frame + 24), style: 'width:64px', 'aria-label': 'To frame' });
    const limb = h('select', { 'aria-label': 'Which hand' }, h('option', { value: 'armL' }, 'Left hand'), h('option', { value: 'armR' }, 'Right hand'));
    return [h('p', { class: 'hint' }, `The paw rests on the ${charName()}'s body and stays on that spot as he moves, a paw's thickness off the hoodie. It never goes into the head.`),
      h('div', { class: 'row' }, limb, h('label', { class: 'row' }, ` from frame ${frame} to `, to)),
      h('div', { class: 'row', style: 'flex-wrap:wrap' }, ...Object.entries(F2.CONTACTS).map(([k, n]) => h('button', { onclick: () => { close(); featRun({ action: 'contact', limb: limb.value, where: k, to: Number(to.value) }); } }, n)), h('button', { onclick: close }, 'Cancel'))];
  });
}
function angleDialog() {
  const names = Object.keys(scene.angles || {});
  modal({ h }, 'Multi-cam angles', close => {
    const name = h('input', { type: 'text', value: String.fromCharCode(65 + names.length), style: 'width:80px', 'aria-label': 'Angle name' });
    return [h('p', { class: 'hint' }, 'Save the camera as a named angle, then cut to it at the playhead, on the beat, or with markers like "cam: B".'),
      h('div', { class: 'row' }, name, h('button', { onclick: () => { close(); featRun({ action: 'save_angle', name: name.value }).then(() => angleDialog()); } }, 'Save this angle')),
      h('div', { class: 'ds-list' }, ...names.map(n => h('div', { class: 'row' }, h('b', { style: 'min-width:5em' }, n),
        h('button', { onclick: () => { close(); featRun({ action: 'cut_to', name: n }); } }, 'Cut to it here'), h('button', { onclick: () => { close(); featRun({ action: 'delete_angle', name: n }).then(() => angleDialog()); } }, 'Delete')))),
      h('div', { class: 'row' }, h('button', { onclick: () => { close(); featRun({ action: 'cam_markers' }); } }, 'Cuts from "cam:" markers'), h('button', { onclick: close }, 'Close'))];
  });
}
function scriptDialog() {
  modal({ h }, 'Script to blocking', close => {
    const ta = h('textarea', { rows: 12, style: 'width:100%', placeholder: 'INT. KITCHEN\nBUNNY: (waves) Hi, I made toast.\n(shocked) It is on fire.\n\n# The fix\nBUNNY: (shrug) Cereal it is.' });
    const caps = h('input', { type: 'checkbox' });
    return [h('p', { class: 'hint' }, 'Each scene heading becomes a shot. Each line gets a marker and its length from the words; actions in (brackets) pick a motion or a face from the library. Undo puts it all back.'),
      ta, h('label', { class: 'row' }, caps, ' Also add each line as a caption'),
      h('div', { class: 'row' }, h('button', { class: 'primary', onclick: () => { close(); featRun({ action: 'script', text: ta.value, captions: caps.checked }); } }, 'Block it'), h('button', { onclick: close }, 'Cancel'))];
  });
}

// ---------------------------------------------------------------- animator tools part 2 (animtools2.js)
let ikOn = false, pathWhat = null, pathPts = null, pathSig = '', pathPops = [], curves = false, editLayer = -1, balanceOn = false, balanceNow = null, multi = [], refLoaded = null;
const graphSel = {};
const T = () => (editLayer >= 0 && project.layers?.[editLayer]) || project;
const valuesNow = () => Object.fromEntries(BUNNY_IDS.concat(FACE_IDS).map(id => [id, current(id)]));
const PATHS = [['armL', 'Left hand'], ['armR', 'Right hand'], ['legL', 'Left foot'], ['legR', 'Right foot'], ['head', 'Head']];
const POSE_PART_NAMES = { face: 'Face', hands: 'Hands', ears: 'Ears', upper: 'Upper body', whole: 'Whole pose' };
const anim2Ctx = () => ({
  ...animCtx(), range, current, character, label: id => LABEL[id] || id, trackIds: () => BUNNY_IDS.concat(FACE_IDS),
  putPose: v => putPose(Object.fromEntries(Object.entries(v).filter(([id]) => BUNNY_IDS.includes(id) || FACE_IDS.includes(id)))),
  popUndo: () => undoStack.pop(), selectKey: (id, f) => { selected = { id, f }; },
});
const pathKeys = () => new Set((pathWhat === 'head' ? ['headYaw', 'headNod', 'rot'] : A2.LIMB[pathWhat].ids).flatMap(id => (project.tracks[id] || []).map(k => k.f)));
function showPath(what) {
  pathWhat = what || null; pathSig = ''; pathPts = null; pathPops = [];
  if (!pathWhat) A2.drawPath(anim2Ctx(), null);
  apply();
  if (pathWhat) toast(pathPops.length ? `${PATHS.find(p => p[0] === pathWhat)[1]} path: ${pathPops.length} popping arc${pathPops.length > 1 ? 's' : ''} (marked ×). Animate › Fix popping arcs smooths them.` : `${PATHS.find(p => p[0] === pathWhat)[1]} path: arcs are clean`, 5000);
  return { what: pathWhat, pops: pathPops };
}
function fixArcs(what = pathWhat || 'armR') {
  const c = anim2Ctx(), pops = A2.arcCheck(A2.pathOf(c, what));
  if (!pops.length) { apply(); toast('No popping arcs on that path'); return { fixed: 0, popsBefore: 0, popsAfter: 0 }; }
  const r = A2.arcFix(c, what, pops), after = A2.arcCheck(A2.pathOf(c, what));
  pathSig = ''; apply();
  toast(`Smoothed ${pops.length} popping arc${pops.length > 1 ? 's' : ''}${after.length ? `, ${after.length} left` : ''}`, 4000);
  return { ...r, popsBefore: pops.length, popsAfter: after.length };
}
function drawCog() {
  const fr = $('#frame');
  let c = document.getElementById('cog-layer');
  if (!balanceOn || !balanceNow) { c?.remove(); return; }
  if (!c) { c = document.createElement('canvas'); c.id = 'cog-layer'; fr.insertBefore(c, $('#hud')); }
  c.width = fr.clientWidth; c.height = fr.clientHeight;
  const g = c.getContext('2d'), w = balanceNow.cog.clone(), floor = balanceNow.cog.clone();
  floor.z = 0;
  const P = v => { v.project(view.camera); return [(v.x + 1) / 2 * c.width, (1 - v.y) / 2 * c.height]; };
  const [x, y] = P(w), [fx, fy] = P(floor);
  g.strokeStyle = '#1F1F1D'; g.lineWidth = 2; g.setLineDash([5, 4]); g.beginPath(); g.moveTo(x, y); g.lineTo(fx, fy); g.stroke(); g.setLineDash([]);
  g.fillStyle = balanceNow.balanced === false ? '#1F1F1D' : '#E0A64B'; g.beginPath(); g.arc(x, y, 7, 0, Math.PI * 2); g.fill(); g.stroke();
  g.beginPath(); g.moveTo(fx - 8, fy); g.lineTo(fx + 8, fy); g.stroke();
}
function toggleIk(on = !ikOn) { ikOn = on; $('#view')?.classList.toggle('ik', ikOn); toast(ikOn ? 'IK drag: drag a hand or foot in the viewport. It keys the arm or leg controls, so FK stays in step. Shift+drag still moves the camera aim.' : 'IK drag off: dragging orbits the camera', 4000); if (tab === 'pose') buildPanel(); return { ik: ikOn }; }
function newLayer(name) { pushUndo('Add layer'); editLayer = A2.addLayer(project, name); dirty = true; buildTimelineTools(); drawTracks(); apply(); toast(`Keys now go to ${T().name}. Pick Base in the timeline to edit the base animation.`, 4000); return layersInfo(); }
const layersInfo = () => ({ editing: editLayer >= 0 && project.layers?.[editLayer] ? T().name : 'Base', layers: (project.layers || []).map((L, i) => ({ index: i, name: L.name, on: L.on !== false, weight: L.weight ?? 1, controls: Object.keys(L.tracks).length })) });
function copyKeysNow(opts) { const r = A2.copyKeys(anim2Ctx(), opts); toast(`Copied ${r.controls} controls, ${r.frames} frames. Paste in any shot or character (Ctrl+Shift+V).`, 4000); return r; }
function pasteKeysNow(at) { const r = A2.pasteKeys(anim2Ctx(), at); toast(`Pasted ${r.keys} keys at frame ${r.at}${r.skipped.length ? `; ${r.skipped.length} controls this character does not have were left out` : ''}`, 4000); return r; }
async function retargetTo(c) {
  if (!CHARACTERS.some(x => x[0] === c)) throw Error('character must be one of ' + CHARACTERS.map(x => x[0]).join(', '));
  pushUndo('Retarget to ' + c);
  scene.character = c;
  await ensureCharacter();
  const known = new Set(ALL_IDS().filter(id => !/^nose/.test(id) || view.rig.bones.has('nose'))), dropped = new Set();
  let clamped = 0;
  for (const s of scene.shots) {
    const before = JSON.stringify(s.tracks), r = A2.retargetTracks(s.tracks, known, range);
    s.tracks = r.tracks; r.dropped.forEach(d => dropped.add(d));
    if (JSON.stringify(s.tracks) !== before) clamped++;
    for (const L of s.layers || []) L.tracks = A2.retargetTracks(L.tracks, known, range).tracks;
  }
  dirty = true; refreshAll();
  toast(`Retargeted to the ${charName()}: every shot keeps its animation inside the ${charName()}'s joint limits`, 4000);
  return { character: c, shots: scene.shots.length, shotsAdjusted: clamped, dropped: [...dropped] };
}
async function referenceVideo(p, opts = {}) {
  if (p === undefined) p = (await api('pick-video', {})).path;
  if (!p) return null;
  const r = await api('ref-video', { path: p });
  pushUndo('Reference video');
  scene.reference = { path: p, offset: Number(opts.offset ?? scene.reference?.offset ?? 0), opacity: Math.max(0.1, Math.min(1, Number(opts.opacity ?? 0.6))) };
  dirty = true;
  const ref = A2.setReference(view, r.url, scene.reference);
  refLoaded = p;
  await Promise.race([ref.ready, new Promise(ok => setTimeout(ok, 4000))]);
  apply();
  toast('Reference video behind the character. It plays with the timeline and never renders.', 4000);
  return { reference: scene.reference, ...A2.referenceInfo() };
}
function clearReference() { A2.clearReference(view); refLoaded = null; if (scene.reference) { pushUndo('Remove reference video'); delete scene.reference; dirty = true; } return { reference: null }; }
// shown again when a scene that has one is opened
function syncReferenceFile() {
  const p = scene.reference?.path || null;
  if (p === refLoaded) return;
  if (!p) { A2.clearReference(view); refLoaded = null; return; }
  refLoaded = p;
  api('ref-video', { path: p }).then(r => { A2.setReference(view, r.url, scene.reference); }).catch(e => toast('Reference video: ' + e.message, 5000));
}
const pick2 = (title, items, run) => modal({ h }, title, close => [h('div', { class: 'row', style: 'flex-wrap:wrap' }, ...items.map(([id, n]) => h('button', { onclick: () => { close(); run(id); } }, n))), h('button', { onclick: close }, 'Cancel')]);
function pinDialog() {
  modal({ h }, 'Pin a hand or foot', close => {
    const to = h('input', { type: 'number', min: frame + 1, max: project.length - 1, value: Math.min(project.length - 1, frame + 24), style: 'width:64px', 'aria-label': 'To frame' });
    return [h('p', { class: 'hint' }, `Keeps it where it is at frame ${frame} while the body moves: a planted foot, a hand on a table or a wall. Keys the arm or leg every 2 frames up to the frame below.`),
      h('label', { class: 'row' }, 'Up to frame ', to),
      h('div', { class: 'row', style: 'flex-wrap:wrap' }, ...PATHS.slice(0, 4).map(([id, n]) => h('button', { onclick: () => { close(); const r = A2.pin(anim2Ctx(), id, frame, Number(to.value)); toast(`${n} pinned, ${r.keys} keys, drift at most ${r.worstErrorCm} cm`, 5000); } }, n))),
      h('button', { onclick: close }, 'Cancel')];
  });
}
function warpDialog() {
  modal({ h }, 'Time warp', close => {
    const amt = h('input', { type: 'range', min: 0, max: 2, step: 0.1, value: 1, 'aria-label': 'Strength' });
    return [h('p', { class: 'hint' }, 'Speed ramp for the whole shot: keys, markers and items slide in time. Undo puts them back.'),
      h('label', { class: 'ctl' }, h('span', { class: 'name' }, 'Strength'), amt),
      h('div', { class: 'row', style: 'flex-wrap:wrap' }, ...Object.keys(A2.WARPS).map(w => h('button', { onclick: () => { close(); A2.timeWarp(anim2Ctx(), w, Number(amt.value)); toast('Time warp: ' + w); } }, w[0].toUpperCase() + w.slice(1)))),
      h('button', { onclick: close }, 'Cancel')];
  });
}
function holdPrompt() {
  const n = prompt('Moving hold: the pose keeps drifting the way it was moving, so it never goes dead. How many frames from the playhead?', '12');
  if (!n) return;
  const r = A2.movingHold(anim2Ctx(), frame, Math.min(project.length - 1, frame + Math.max(2, Number(n) || 12)));
  toast(r.drifting ? `Moving hold on ${r.drifting} controls` : 'Nothing was moving into this frame, so nothing drifts', 4000);
}
function poseLibraryPanel() {
  const name = h('input', { type: 'text', placeholder: 'Pose name', style: 'width:9em', 'aria-label': 'Pose name', maxlength: 40 });
  const pp = h('select', { 'aria-label': 'Which part to save' }, ...Object.entries(POSE_PART_NAMES).map(([k, n]) => h('option', { value: k }, n)));
  const list = A2.poses();
  return h('div', {}, h('h3', {}, 'Pose library'),
    h('div', { class: 'row' }, name, pp, h('button', { onclick: () => { if (!name.value.trim()) return toast('Name the pose first'); const r = A2.savePose(anim2Ctx(), name.value.trim(), pp.value); buildPanel(); toast(`Saved ${r.name} (${POSE_PART_NAMES[r.part]}, ${Object.keys(r.values).length} controls)`); } }, 'Save pose')),
    list.length ? h('div', { class: 'chips pose-lib' }, ...list.map(p => h('button', { title: `${POSE_PART_NAMES[p.part]}, saved on the ${p.character}. Click to key it at the playhead (only those controls); right-click to delete.`,
      onclick: () => { A2.applyPose(anim2Ctx(), p.name); toast(`${p.name} keyed`); }, oncontextmenu: e => { e.preventDefault(); if (confirm(`Delete the pose "${p.name}"?`)) { A2.deletePose(p.name); buildPanel(); } } }, p.name, h('small', {}, ' · ' + POSE_PART_NAMES[p.part]))))
      : h('p', { class: 'hint' }, 'Save just the face, hands, ears, upper body or the whole pose, then key it in any shot, on any character.'));
}
// dope sheet: shift-click several keys, drag one to move them all
function moveKeys(list, by) {
  const tr = T().tracks, group = list.map(({ id, f }) => ({ id, k: tr[id]?.find(k => k.f === f) })).filter(g => g.k);
  if (!group.length) throw Error('None of those keys exist');
  pushUndo(`Move ${group.length} keys`);
  const d = Math.max(-Math.min(...group.map(g => g.k.f)), Math.min(project.length - 1 - Math.max(...group.map(g => g.k.f)), Math.round(by)));
  for (const g of group) g.k.f += d;
  settleKeys(group);
  apply(); drawTracks();
  return { moved: group.length, by: d };
}
function settleKeys(group) {
  const tr = T().tracks, moving = new Set(group.map(g => g.k));
  for (const id of new Set(group.map(g => g.id))) tr[id] = Object.values(Object.fromEntries([...tr[id].filter(x => !moving.has(x)), ...tr[id].filter(x => moving.has(x))].map(x => [x.f, x]))).sort((a, b) => a.f - b.f);
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
  ['File', [['New scene', newShot, 'Ctrl+N'], ['New from template…', () => templateDialog(wfCtx())], ['Open…', openShot, 'Ctrl+O'], ['Save', () => saveShot(false), 'Ctrl+S'], ['Save as…', () => saveShot(true), 'Ctrl+Shift+S'], ['Save version…', () => saveVersion(polCtx())], ['Versions…', () => versionsDialog(polCtx())], '-', ['Import audio for the scene…', () => importAudio()], ['Remove scene audio', () => importAudio(null)], ['Babble voice (type a line)…', () => openBabble()], ['Import SVG drawing…', () => importSvg()], '-',
    ['Render scene (all shots)', () => renderScene(), 'Ctrl+Shift+E'], ['Render this shot', () => render(), 'Ctrl+R'], ['Render this frame', () => render(true), 'Ctrl+Shift+R'], '-', ['Export Blender shot file…', exportBridge]]],
  ['Shot', [['Storyboard sheet (PNG)', () => storyboard()], '-', ...STATUS.map(([id, n]) => [`Status: ${n}`, () => shotStatus(id)]), ['Split shot at the playhead', () => splitHere()], '-', ['Add shot after this one', () => addShot(false), 'Ctrl+T'], ['Duplicate this shot', () => addShot(true), 'Ctrl+Shift+T'], ['Name this shot…', () => labelShot()], ['Co-stars (more characters)…', () => castDialog()],
    '-', ['Move earlier', () => moveShot(-1), 'Alt+←'], ['Move later', () => moveShot(1), 'Alt+→'], '-', ['Previous shot', () => selectShot(Math.max(0, scene.active - 1)), 'PgUp'],
    ['Next shot', () => selectShot(Math.min(scene.shots.length - 1, scene.active + 1)), 'PgDn'], '-', ['Delete this shot', () => deleteShot()]]],
  ['Edit', [['Undo', undo, 'Ctrl+Z'], ['Redo', redo, 'Ctrl+Shift+Z'], ['Undo history…', () => historyDialog(prodCtx()), 'Ctrl+H'], '-', ['Key Bunny pose', () => keyGroup(BUNNY_IDS.concat(FACE_IDS)), 'K'], ['Key camera', () => keyGroup(CAM_IDS), 'Shift+K'],
    ['Delete selected key', deleteSelected, 'Delete'], ['Clear all keys', clearAll], '-', ['Add marker with a note', () => addMarker(polCtx()), 'M'], ['Draw a review note on this frame', () => reviewNote(), 'N'], ['Tap a beat marker', () => tapBeat(), 'B']]],
  ['View', [['Command search', () => commandSearch(polCtx()), 'Ctrl+K'], ['Show fps', () => { toggleFps(); updateHud(); }], ['Pop out the viewport (second screen)', () => popOut(wfCtx())], ['Snapping on / off', () => toggleSnap()], ['Shadows on / off', () => toggleShadows()], ['Rule lights on / off', () => { ruleLights = !ruleLights; updateHud(); }], ['Balance marker on / off', () => { balanceOn = !balanceOn; if (!balanceOn) { balanceNow = null; drawCog(); } apply(); }], ['Graph editor (curves) on / off', () => toggleCurves()], '-',
    ...DOCK.LAYOUTS.map(([id, n]) => [`Panels: ${n}`, () => DOCK.setLayout(id)]), ['Detach the timeline (another window)', () => DOCK.detach('timeline')], ['Detach the tools panel (another window)', () => DOCK.detach('tools')], ['Dock everything back', () => DOCK.dockAll()], ['Hide the tools panel', () => (DOCK.toggleHidden('tools') ? toast('Tools panel hidden: Ctrl+Shift+H brings it back') : toast('Tools panel shown')), 'Ctrl+Shift+H'], '-',
    ['Save layout…', () => saveLayout(wfCtx())], 'layouts', '-',
    ['Onion skin', () => { view3.onion = !view3.onion; apply(); }, 'O'], ['Silhouette check', () => setSilhouette(view, !view3.silhouette)], ['Mirror view', () => setMirror(!view3.mirror)], '-', ['Dark mode', toggleDark, 'Ctrl+D'], ['Floor grid', () => { view.grid.visible = !view.grid.visible; }, 'G'], ['Frame Bunny', frameBunny, 'F']]],
  ['Camera', [...LENSES.map(l => [`${l} mm lens`, () => camSet({ lens: l })]), '-', ...VIEWS.map(([n, c]) => [n, () => camSet(c)]), '-', ['Dolly zoom: wide, keep size', () => dollyTo(18)], ['Dolly zoom: long, keep size', () => dollyTo(100)], '-',
    ['Multi-cam angles…', () => angleDialog()], ['Beat-synced camera…', () => pick2('Beat-synced camera', Object.entries(F2.BEAT_STYLES), st => featRun({ action: 'beat_cam', style: st }))],
    ['Floor-plan camera path…', () => F2.planDialog(f2Ctx(), { h, modal }, (pts, a, b) => featRun({ action: 'plan_path', points: pts, from: a, to: b }))], '-',
    ['Previz grey on / off', () => featRun({ action: 'previz' })], ['Render a previz of this shot', () => featRun({ action: 'render_previz' })]]],
  ['Animate', [['Breakdown halfway (tween)', () => breakdown(animCtx(), 50)], ['Stepped blocking on / off', () => toggleStepped()], '-',
    ['Simplify keys', () => toast(`Removed ${simplify(animCtx()).removed} keys the curves did not need`, 4000)],
    ['Loop check', () => { const r = loopCheck(animCtx()); toast(r.seamless ? 'Seamless: the last frame matches the first' : `Not seamless: ${r.mismatched.map(m => LABEL[m.id] || m.id).slice(0, 4).join(', ')}${r.mismatched.length > 4 ? '…' : ''}`, 5000); }],
    ['Make seamless loop', () => { makeLoop(animCtx()); toast('Last frame keyed to match the first'); }],
    ['Lip sync from the voice (this shot)', () => lipsyncFromAudio().catch(e => toast(e.message, 5000))], ['Lip sync from the voice (every shot)', () => lipsyncFromAudio({ all: true }).catch(e => toast(e.message, 5000))],
    ['Audio drives a control…', () => audioDriveDialog()], ['Mark beats from the audio', () => markBeats()],
    ['Retime shot…', () => { const x = prompt('Speed: below 1 is slower, above 1 is faster (e.g. 0.8 or 1.25). Keys after the playhead move.', '1'); if (x) retime(animCtx(), 1 / Number(x), frame); }], '-',
    ['Playblast (viewport video)', () => playblast(animCtx()).catch(e => toast(e.message, 5000))], '-',
    ['IK drag on / off', () => toggleIk(), 'I'], ['Pin a hand or foot…', () => pinDialog()], ['Motion path…', () => pick2('Motion path', [...PATHS, ['', 'Off']], showPath)], ['Fix popping arcs on the path', () => fixArcs()], '-',
    ['Time warp…', () => warpDialog()], ['Moving hold from the playhead…', () => holdPrompt()], ['Euler filter (no 360° flips)', () => toast(`Euler filter: ${A2.eulerFilter(anim2Ctx()).fixed} flips unwound`)], '-',
    ['Add animation layer', () => newLayer()], ['Copy keys (this shot)', () => copyKeysNow(), 'Ctrl+Shift+C'], ['Paste keys at the playhead', () => { try { pasteKeysNow(); } catch (e) { toast(e.message); } }, 'Ctrl+Shift+V'],
    ['Retarget the scene to…', () => pick2('Retarget the scene to', CHARACTERS.map(c => [c[0], c[1]]), c => retargetTo(c).catch(e => toast(e.message, 5000)))], '-',
    ['Reference video…', () => referenceVideo().catch(e => toast(e.message, 5000))], ['Remove reference video', () => clearReference()], '-',
    ['Squash and stretch at the playhead…', () => pick2('Squash and stretch', Object.entries(F2.SQUASH_MOVES), k => featRun({ action: 'squash', kind: k }))], ['Hand contact (hip, belly, chest)…', () => contactDialog()], ['Pose from a stick figure (draw it)', () => stickMode()]]],
  // Story tab and its storytime workflow removed (user, 2026-10-31). The voice and finishing tools it held stay, in Post.
  ['Post', [['Captions…', () => captionsDialog()], ['Music bed…', () => musicDialog()], '-', ['Shot look…', () => pick2('Shot look', [...Object.entries(P.LOOKS), ['', 'None']], l => postRun({ action: 'look', look: l || null }))], ['Cut-ins: photo, narrator PiP, bubble…', () => cutsDialog()], '-',
    ['Import SVG drawing…', () => importSvg()], ['Draw on the screen…', () => drawOnScreen()], ['Drawings on this shot…', () => setTab('draw')], '-',
    ['Gestures from the voice', () => storyRun('gestures')], ['Eye darts', () => storyRun('eye_darts')], ['Auto foley (sound effects)', () => storyRun('foley')], ['Split the voice into sentences…', () => sentenceDialog()], ['Voice effects…', () => setTab('audio', 'effects')], ['Transcribe the voice…', () => setTab('audio', 'transcribe')]]],
  ['Blender', [['Open in Blender (live)', () => openInBlender(), 'Ctrl+B'], ['Stop the live Blender link', () => MR.close()], '-', ['Powers on this shot (doodles, scatter, crowd, liquids, lens, 360)…', () => powersDialog()], ['Draw ink doodles in 3D', () => doodleMode()], '-',
    ['Transition into this shot…', () => transitionDialog()], ['Paper finish…', () => { const v = prompt('Paper finish on the joined scene, 0 to 100 (0 is off):', String(Math.round((scene.paper || 0) * 100))); if (v != null) pwRun({ action: 'paper', amount: Number(v) / 100 }); }], '-',
    ['Linked controls…', () => linkDialog()], ['Macros…', () => macroDialog()], ['Master Bunny file…', () => masterDialog()]]],
  ['Tools', [['Check before export (preflight)', () => runPreflight(false)], ['Health check…', () => healthDialog(prodCtx())], ['Claude change log…', () => changeLogDialog(prodCtx())], '-',
    ['Overnight batch…', () => batchDialog(prodCtx())], ['Cancel sleep after renders', () => api('sleep-when-done', { on: false }).then(() => toast('The PC will stay awake'))], '-',
    ['Render presets…', () => presetsDialog(prodCtx())], ['Pack project…', () => pack(prodCtx()).catch(e => toast(e.message, 5000))], ['Clean up cache…', () => cacheDialog(prodCtx()).catch(e => toast(e.message, 5000))]]],
  ['Help', [['Guide…', () => guideDialog()], ['Controls and shortcuts', showHelp, 'F1'], ['Keyboard shortcuts and cheat sheet…', () => hotkeyDialog(wfCtx())]]],
];

// saved layouts are listed live in the View menu
const menus = () => MENUS.map(([name, items]) => [name, items.flatMap(it => (it === 'layouts' ? Object.keys(layouts.get()).map(n => [`Layout: ${n}`, () => useLayout(wfCtx(), n)]) : [it]))]);
function buildMenu() {
  const bar = $('#menubar');
  bar.replaceChildren();
  for (const [name, items] of menus()) {
    // long menus open as columns (split where the menu already has separators), so nothing scrolls
    const n = items.filter(it => it !== '-').length, ncol = n > 16 ? Math.min(3, Math.ceil(n / 14)) : 1;
    const list = h('div', { class: 'menu-list' + (ncol > 1 ? ' cols' : ''), role: 'menu' });
    const groups = [[]];
    for (const it of items) if (it === '-') groups.push([]); else groups.at(-1).push(it);
    const per = Math.ceil(n / ncol);
    let col = h('div', { class: 'mcol' }), inCol = 0;
    const cols = [col];
    for (const [gi, grp] of groups.entries()) {
      if (!grp.length) continue;
      if (ncol > 1 && inCol && inCol + grp.length / 2 > per && cols.length < ncol) { col = h('div', { class: 'mcol' }); cols.push(col); inCol = 0; }
      else if (inCol) col.append(h('hr'));
      inCol += grp.length;
      for (const it of grp) {
      const [label, fn, key] = it;
      col.append(h('button', { role: 'menuitem', title: 'Right-click to pin it to the favourites bar', oncontextmenu: e => { e.preventDefault(); const on = toggleFav(`${name} › ${label}`); refreshQuickbar(); toast(on ? `Pinned "${label}"` : `Unpinned "${label}"`); }, onclick: () => { closeMenus(); runCommand({ group: name, label, run: fn }); } }, h('span', {}, label), key ? h('kbd', {}, key) : null));
      }
    }
    if (ncol > 1) list.append(...cols); else list.append(...col.childNodes);
    const btn = h('button', { 'aria-haspopup': 'true', 'aria-expanded': 'false', onclick: e => { const m = e.currentTarget.parentElement; const open = !m.classList.contains('open'); closeMenus(); if (open) { m.classList.add('open'); e.currentTarget.setAttribute('aria-expanded', 'true'); } } }, name);
    bar.append(h('div', { class: 'menu' }, btn, list));
  }
  bar.append(h('div', { id: 'quickbar', role: 'toolbar', 'aria-label': 'Favourites and recent commands' }), h('div', { class: 'spacer' }), h('span', { class: 'status', id: 'status' }, ''));
  refreshQuickbar();
  if (!buildMenu.bound) { buildMenu.bound = true; document.addEventListener('pointerdown', e => { if (!e.target.closest('#menubar')) closeMenus(); }); }
}
// every command run from a menu, the bar, Ctrl+K or a custom key goes through here
function runCommand(c) {
  if (!c) return;
  macroRec.note(c.group, c.label, frame);
  nextLabel = c.label.replace(/…$/, '');
  try { const r = c.run(); if (r?.catch) r.catch(e => toast(e.message, 5000)); } catch (e) { toast(e.message, 5000); } finally { nextLabel = null; }
  noteRun(cmdId(c)); refreshQuickbar();
}
function refreshQuickbar() { const q = $('#quickbar'); if (q) q.replaceChildren(...quickbar(wfCtx())); }
function closeMenus() { document.querySelectorAll('#menubar .menu.open').forEach(m => { m.classList.remove('open'); m.querySelector('button').setAttribute('aria-expanded', 'false'); }); }

// ---------------------------------------------------------------- side panel: workspaces, each with a section row (as in the 2D app)
const TABS = [['pose', 'Pose'], ['face', 'Face'], ['animate', 'Animate'], ['camera', 'Camera'], ['stage', 'Stage'], ['library', 'Library'], ['carousel', 'Carousel'], ['render', 'Render'], ['materials', 'Materials'], ['audio', 'Audio'], ['draw', 'Draw']];
const sub = { face: 'expressions', animate: 'motions', camera: 'lens', stage: 'set', library: 'prop', render: 'output', audio: 'babble' };
const SUBS = {
  pose: () => shownParts().map(([id, n]) => [id, n]),
  face: () => [['expressions', 'Expressions'], ['eyes', 'Gaze, blink & mouth'], ['idle', 'Idle life']],
  animate: () => [['motions', 'Motion library'], ['keys', 'Keys & timing'], ['body', 'IK, paths & contact'], ['layers', 'Layers & copy'], ['loops', 'Loops & beats'], ['reference', 'Reference']],
  camera: () => [['lens', 'Lens & angle'], ['presets', 'Shot presets'], ['moves', 'Camera moves'], ['view', 'View & checks']],
  stage: () => [['set', 'Set & light'], ['wardrobe', 'Wardrobe'], ['items', 'In this shot'], ['cast', 'Co-stars']],
  library: () => CATEGORIES.filter(c => !['motion', 'outfit', 'accessory'].includes(c[0])),
  carousel: () => [],
  materials: () => [],
  audio: () => [['babble', 'Babble voice'], ['effects', 'Voice effects'], ['transcribe', 'Transcribe'], ['voice', 'Voice & lip sync'], ['music', 'Music & beats']],
  draw: () => [],
  render: () => [['output', 'Shot & output'], ['post', 'Look & finish'], ['blender', 'Blender, autosave & cache']],
};
// menu commands shown as buttons in a section (same commands, same undo, also in Ctrl+K)
const SHELVES = {
  'audio:voice': [['Voice', 'File', ['Import audio for the scene…', 'Remove scene audio']], ['Lip sync', 'Animate', ['Lip sync from the voice (this shot)', 'Lip sync from the voice (every shot)']], ['From the voice', 'Post', ['Gestures from the voice', 'Eye darts', 'Split the voice into sentences…']]],
  'audio:music': [['Music', 'Post', ['Music bed…', 'Auto foley (sound effects)']], ['Beats', 'Animate', ['Mark beats from the audio', 'Audio drives a control…']], ['Captions', 'Post', ['Captions…']]],
  'animate:keys': [['Keys', 'Edit', ['Key Bunny pose', 'Key camera', 'Delete selected key', 'Clear all keys']], ['Timing', 'Animate', ['Breakdown halfway (tween)', 'Stepped blocking on / off', 'Simplify keys', 'Retime shot…', 'Time warp…', 'Moving hold from the playhead…', 'Euler filter (no 360° flips)']], ['Markers', 'Edit', ['Add marker with a note', 'Draw a review note on this frame', 'Tap a beat marker']]],
  'animate:body': [['Limbs', 'Animate', ['IK drag on / off', 'Pin a hand or foot…', 'Motion path…', 'Fix popping arcs on the path']], ['Body', 'Animate', ['Squash and stretch at the playhead…', 'Hand contact (hip, belly, chest)…', 'Pose from a stick figure (draw it)']], ['Checks', 'View', ['Balance marker on / off', 'Rule lights on / off', 'Silhouette check', 'Onion skin']]],
  'animate:layers': [['Layers', 'Animate', ['Add animation layer']], ['Copy', 'Animate', ['Copy keys (this shot)', 'Paste keys at the playhead', 'Retarget the scene to…']], ['Curves', 'View', ['Graph editor (curves) on / off']]],
  'animate:loops': [['Loops', 'Animate', ['Loop check', 'Make seamless loop']], ['Check', 'Animate', ['Playblast (viewport video)']]],
  'animate:reference': [['Reference video', 'Animate', ['Reference video…', 'Remove reference video']]],
  'camera:moves': [['Dolly', 'Camera', ['Dolly zoom: wide, keep size', 'Dolly zoom: long, keep size']], ['Moves', 'Camera', ['Multi-cam angles…', 'Beat-synced camera…', 'Floor-plan camera path…']], ['Previz', 'Camera', ['Previz grey on / off', 'Render a previz of this shot']]],
  'camera:view': [['View', 'View', ['Floor grid', 'Frame Bunny', 'Mirror view', 'Silhouette check', 'Onion skin', 'Snapping on / off', 'Show fps', 'Dark mode']], ['Checks', 'View', ['Rule lights on / off', 'Balance marker on / off']], ['Second screen', 'View', ['Pop out the viewport (second screen)']]],
  'render:post': [['Look', 'Post', ['Shot look…', 'Cut-ins: photo, narrator PiP, bubble…']], ['Finish', 'Blender', ['Transition into this shot…', 'Paper finish…']]],
  'render:blender': [['Production', 'Tools', ['Check before export (preflight)', 'Health check…', 'Overnight batch…', 'Cancel sleep after renders', 'Render presets…', 'Pack project…', 'Clean up cache…', 'Claude change log…']], ['Files', 'File', ['Save version…', 'Versions…', 'Export Blender shot file…']]],
};
function shelf(group, menu, labels) {
  const all = menus().find(m => m[0] === menu)?.[1] || [];
  const btns = labels.map(l => all.find(it => Array.isArray(it) && it[0] === l)).filter(Boolean)
    .map(([label, fn, key]) => h('button', { title: label + (key ? ` (${key})` : ''), onclick: () => runCommand({ group: menu, label, run: fn }) }, label.replace(/ on \/ off$/, '')));
  return h('div', { class: 'shelf-group' }, h('h3', {}, group), h('div', { class: 'shelf' }, ...btns));
}
const shelves = key => (SHELVES[key] || []).map(([g, m, l]) => shelf(g, m, l));
const subOf = t => (t === 'pose' ? part : sub[t]);
function setTab(id, s) {
  tab = id;
  if (s != null) { if (id === 'pose') part = s; else sub[id] = s; }
  buildTabs(); buildPanel(); layout(); overlayDraw?.();
  return { tab, section: subOf(tab) };
}
function buildTabs() {
  $('#tabs').replaceChildren(...TABS.map(([id, name]) => h('button', { role: 'tab', 'aria-pressed': String(tab === id), title: `${name} workspace${TABS.findIndex(t => t[0] === id) < 9 ? ` (${TABS.findIndex(t => t[0] === id) + 1})` : ''}`, onclick: () => setTab(id) }, name)));
  const subs = SUBS[tab]?.() || [];
  if (subs.length && !subs.some(s => s[0] === subOf(tab))) { if (tab === 'pose') part = subs[0][0]; else sub[tab] = subs[0][0]; }
  const label = tab === 'pose' ? h('span', { class: 'sub-label' }, 'Part:') : null;
  $('#subtabs .sub-chips').replaceChildren(...[label, ...subs.map(([id, n]) => h('button', { role: 'tab', 'aria-pressed': String(subOf(tab) === id), onclick: () => setTab(tab, id) }, n))].filter(Boolean));
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
    const tt = DISCRETE.has(id) ? project : T();
    if (hasKey(tt, id, frame)) deleteKey(tt, id, frame); else keyAt(id, current(id));
    delete preview[id]; apply(); drawTracks();
  });
  const name = h('span', { class: 'name', title: 'Double-click to reset this control to rest' }, dot, LABEL[id] || id);
  name.addEventListener('dblclick', e => { e.preventDefault(); pushUndo('Reset ' + (LABEL[id] || id)); setValue(id, defaults(id)); drawTracks(); buildPanel(); });
  const row = h('label', { class: 'ctl', 'data-id': id, title: TIPS[id] || '' }, name, slider, num);
  return row;
}
const round = v => Math.round(v * 100) / 100;
const cols = (cls, ...c) => h('div', { class: 'ws ' + cls }, ...c.map(x => h('div', { class: 'col' }, ...[x].flat())));

function buildPanel() {
  const c = $('#panel-content');
  const y = c.scrollTop, same = c.dataset.view === tab + ':' + subOf(tab);
  c.replaceChildren();
  c.dataset.view = tab + ':' + subOf(tab);
  const s = subOf(tab);
  if (tab === 'pose') {
    const ids = PARTS.find(p => p[0] === part)[2];
    c.append(cols('two', [h('h3', {}, PARTS.find(p => p[0] === part)[1]), h('div', { class: 'ctl-grid' }, ...ids.map(control)),
      h('div', { class: 'row', style: 'margin-top:10px' },
        h('button', { onclick: () => keyGroup(ids), title: 'Set a key on every control of this part' }, 'Key this part'),
        h('button', { onclick: () => { pushUndo(); for (const id of ids) setValue(id, defaults(id)); }, title: 'Back to rest for this part' }, 'Reset this part'),
        h('button', { onclick: () => { pushUndo(); for (const id of BUNNY_IDS) setValue(id, defaults(id)); }, title: 'Back to rest for the whole body' }, 'Reset whole pose'),
        h('button', { 'aria-pressed': String(ikOn), onclick: () => toggleIk(), title: 'Drag a hand or foot in the viewport; the arm or leg follows inside its joint limits (I)' }, 'IK drag'),
        h('button', { onclick: () => pinDialog(), title: 'Keep a hand or foot where it is while the body moves' }, 'Pin hand or foot…'),
        h('button', { 'aria-pressed': String(!!pathWhat), onclick: () => (pathWhat ? showPath(null) : pick2('Motion path', PATHS, showPath)), title: 'Show a motion path with a dot per frame; popping arcs are marked ×' }, 'Motion path')),
      h('p', { class: 'hint' }, `Every joint stops at the ${charName()}'s limits. Click a part of the character in the 3D view to jump to it. Left and right follow Doodle Studio.${part === 'ears' && data.ear_width_lock ? ' The Frog\'s eye bumps are rigid, so they grow and squash only a little.' : ''}`)],
      [posePanel(), poseLibraryPanel()]));
  } else if (tab === 'face') {
    const F = data.face;
    const sel = (id, names) => {
      const el = h('select', { 'aria-label': LABEL[id] }, ...names.map((n, i) => h('option', { value: i }, n)));
      el.value = String(Math.round(current(id)));
      el.addEventListener('change', () => { pushUndo(); setValue(id, Number(el.value)); drawTracks(); });
      return h('label', { class: 'ctl', 'data-id': id, style: 'grid-template-columns:8.5em 1fr' }, LABEL[id], el);
    };
    if (s === 'expressions') {
      c.append(cols('two', [h('h3', {}, 'Expression'), faceGrid(libCtx(), Math.round(current('expression')), i => { pushUndo('Expression'); setValue('expression', i); drawTracks(); buildPanel(); })],
        [h('h3', {}, 'Now'), sel('expression', F.faces), sel('blink', ['Open', 'Half', 'Closed', 'Squeeze', 'Wink']),
          h('h3', {}, 'Mouth'), mouthGrid(libCtx(), Math.round(current('mouth')), i => { pushUndo('Mouth'); setValue('mouth', i); drawTracks(); buildPanel(); }),
          h('h3', {}, 'Gaze'), gazePad(), h('p', { class: 'hint' }, 'Point at a face to see it on the character; click to key it at the playhead. Faces are Doodle Studio\'s own drawings; eyes and mouth keep a constant size. Look at the camera with the middle gaze for direct address.')]));
    } else if (s === 'eyes') {
      c.append(cols('two', [h('h3', {}, 'Gaze'), gazePad(), h('h3', {}, 'Blink'), sel('blink', ['Open', 'Half', 'Closed', 'Squeeze', 'Wink']), h('h3', {}, 'Mouth'), mouthGrid(libCtx(), Math.round(current('mouth')), i => { pushUndo('Mouth'); setValue('mouth', i); drawTracks(); buildPanel(); })],
        [h('h3', {}, 'Expression'), sel('expression', F.faces), h('p', { class: 'hint' }, 'Gaze keys hold until the next one. Middle = straight at the camera.')]));
    } else if (s === 'idle') c.append(cols('two', idlePanel(), h('p', { class: 'hint' }, 'Idle life keeps him alive between your keys: natural blinks and ear flicks, the same in the 3D view and the Blender render.')));
  } else if (tab === 'audio') {
    if (s === 'babble') c.append(babblePanel());
    else if (s === 'effects') c.append(voiceFxPanel());
    else if (s === 'transcribe') c.append(transcribePanel());
    else c.append(h('div', { class: 'ws three' }, ...shelves('audio:' + s).map(x => h('div', { class: 'col' }, x))));
  } else if (tab === 'draw') {
    c.append(drawingsPanel());
  } else if (tab === 'animate') {
    if (s === 'motions') c.append(libraryBrowser(libCtx(), { cats: [['motion', 'Motions'], ['expression', 'Faces']], cat: ['motion', 'expression'].includes(libUi.cat) ? libUi.cat : 'motion', side: true }));
    else c.append(h('div', { class: 'ws three' }, ...shelves('animate:' + s).map(x => h('div', { class: 'col' }, x))));
  } else if (tab === 'camera') {
    if (s === 'lens') {
      c.append(cols('two', [h('h3', {}, 'Camera'), h('div', { class: 'ctl-grid' }, ...CAM_IDS.map(control)),
        h('div', { class: 'row', style: 'margin-top:10px' }, h('button', { onclick: () => keyGroup(CAM_IDS) }, 'Key camera'), h('button', { onclick: frameBunny }, 'Frame Bunny'),
          h('button', { onclick: () => { pushUndo(); setValue('cam.focus', round(current('cam.dist'))); drawTracks(); }, title: 'Rack focus: put the sharp plane on what the camera aims at. Key it at two frames to pull focus.' }, 'Focus on aim'),
          h('button', { onclick: () => window.ds3d.turntable(), title: '360° turntable: the camera circles once over the whole shot' }, 'Turntable'),
          h('button', { 'aria-pressed': String(!!project.horizonLock), onclick: () => { pushUndo(); project.horizonLock = !project.horizonLock; apply(); buildPanel(); }, title: 'Keep the horizon level in this shot: roll and Dutch presets are ignored' }, 'Horizon lock'))],
        [h('h3', {}, 'Lens'), h('div', { class: 'chips' }, ...LENSES.map(l => h('button', { 'aria-pressed': String(Math.round(current('cam.lens')) === l), onclick: () => camSet({ lens: l }) }, `${l} mm`)),
          h('button', { onclick: () => dollyTo(18), title: 'Dolly zoom: go wide while moving in, so Bunny keeps his size and the room stretches' }, 'Dolly wide'),
          h('button', { onclick: () => dollyTo(100), title: 'Dolly zoom: go long while moving out, so Bunny keeps his size and the room flattens' }, 'Dolly long')),
          h('p', { class: 'hint' }, 'In the 3D view: drag to orbit, Shift+drag or the Pan tool to move the aim, wheel to move in and out, Alt+wheel for the lens. The set moves with the camera, so angles stay physically true.')]));
    } else if (s === 'presets') c.append(cameraPresetsPanel(presetCtx()));
    else c.append(h('div', { class: 'ws three' }, ...shelves('camera:' + s).map(x => h('div', { class: 'col' }, x))));
  } else if (tab === 'stage') {
    if (s === 'set') c.append(setPanel(libCtx()));
    else if (s === 'wardrobe') c.append(wardrobePanel(libCtx()));
    else if (s === 'items') c.append(itemsPanel(libCtx()));
    else c.append(cols('two', [h('h3', {}, 'Co-stars'), h('p', { class: 'hint' }, 'More characters in this shot, each on the same rig with its own keys. They collide with the lead in the render.'), h('div', { class: 'row' }, h('button', { onclick: () => castDialog() }, 'Co-stars…'))],
      [h('h3', {}, 'Lead character'), h('div', { class: 'char-cards', role: 'list' }, ...CHARACTERS.map(([id, n]) => h('button', { class: 'libx-card', role: 'listitem', 'aria-pressed': String(character() === id), title: `Make the ${n} the lead character`, onclick: () => setCharacter(id).catch(e => toast(e.message, 5000)) }, h('span', { class: 'pic', style: 'aspect-ratio:2/3' }, h('img', { src: `chars/${id}.png`, alt: '', draggable: 'false' })), h('span', {}, n))))]));
  } else if (tab === 'library') {
    c.append(libraryBrowser(libCtx(), { cats: SUBS.library(), cat: s, noChips: true, side: true }));
    c.append(h('div', { class: 'row', style: 'margin-top:10px' }, h('span', { class: 'hint', id: 'models-info', style: 'flex:1' }, ''), h('button', { title: 'Convert every set, prop and scenery piece now, so they all show at once later (about a minute in Blender)', onclick: () => api('stage-models', { all: true }).then(r => toast(`Making ${r.pending.length} 3D models in the background`, 4000)).catch(e => toast(e.message)) }, 'Make 3D models for the whole library')));
    api('models-info').then(r => { const el = $('#models-info'); if (el) el.textContent = `${r.models} pieces ready to show in the 3D view${r.queued ? `, ${r.queued} being made` : ''}.`; }).catch(() => {});
  } else if (tab === 'carousel') {
    c.append(carouselPanel(carCtx()));
  } else if (tab === 'materials') {
    c.append(MAT.materialsPanel(matCtx()));
  } else if (tab === 'render') {
    if (s === 'post') c.append(h('div', { class: 'ws three' }, ...shelves('render:post').map(x => h('div', { class: 'col' }, x))));
    else if (s === 'blender') {
      c.append(h('div', { class: 'ws three' }, h('div', { class: 'col' }, h('h3', {}, 'Blender location'), h('div', { class: 'row' }, h('span', { id: 'blender-path', class: 'hint', style: 'flex:1;overflow-wrap:anywhere' }, '…'), h('button', { onclick: pickBlender }, 'Change…'))),
        h('div', { class: 'col' }, autosavePanel()), h('div', { class: 'col' }, ...shelves('render:blender'))));
      api('settings', {}).then(st => { const el = $('#blender-path'); if (el) el.textContent = st.blenderFound || 'Not found. Install Blender 4.5 LTS, or point to blender.exe.'; }).catch(() => {});
    } else {
      const field = (label, obj, key, attrs) => { const i = h('input', { ...attrs, value: obj[key] }); i.addEventListener('change', () => { pushUndo(); obj[key] = attrs.type === 'number' ? Number(i.value) : i.value; buildTimelineTools(); drawTracks(); updateHud(); }); return h('label', { class: 'ctl', style: 'grid-template-columns:8.5em 1fr' }, label, i); };
      c.append(cols('two', [h('h3', {}, `Shot ${project.code}`), field('Name', project, 'label', { type: 'text', placeholder: 'optional, e.g. intro' }), field('Length (frames)', project, 'length', { type: 'number', min: 1, max: 54000 }),
        h('span', { title: 'Line weight for this shot in Blender, as a percent of Doodle Studio\'s ink (100 = Bunny\'s usual weight). Every line in the shot changes together, so weights stay equal.' }, field('Line weight (%)', project, 'ink', { type: 'number', min: 40, max: 250, placeholder: '100' })),
        rulesRow(),
        h('h3', {}, `Scene: ${scene.shots.length} shot${scene.shots.length > 1 ? 's' : ''}, ${(sceneFrames() / scene.fps).toFixed(1)} s`),
        field('Frame rate', scene, 'fps', { type: 'number', min: 12, max: 60 }),
        field('Width (px)', scene, 'width', { type: 'number', min: 64, max: 3840 }), field('Height (px)', scene, 'height', { type: 'number', min: 64, max: 3840 }),
        h('div', { class: 'chips', style: 'margin:6px 0' }, ...presets().map(p =>
          h('button', { 'aria-pressed': String(scene.width === p.width && scene.height === p.height && scene.fps === p.fps), title: `${p.width}×${p.height}, ${p.fps} fps`, onclick: () => applyPreset(prodCtx(), p.name) }, p.name)),
          h('button', { title: 'Add, rename or change presets', onclick: () => presetsDialog(prodCtx()) }, 'Edit…'))],
        [h('h3', {}, 'Blender render'),
          h('div', { class: 'row' }, h('button', { class: 'primary', onclick: () => renderScene() }, 'Render scene'), h('button', { onclick: () => render() }, `Render ${project.code}`), h('button', { onclick: () => render(true) }, 'This frame')),
          h('div', { class: 'row', style: 'margin-top:6px' }, h('button', { onclick: () => renderScene(true), title: 'Every shot at half size without cloth: a fast check of timing and cuts' }, 'Quick preview scene'),
            h('button', { onclick: () => render(false, true), title: 'This shot at half size without cloth' }, 'Quick preview shot'), h('button', { onclick: () => render(false, true, null, true), title: 'Grey clay blocking pass: fastest, no cloth, no springs' }, 'Previz (grey)'), h('button', { onclick: cancelRender }, 'Cancel')),
          h('div', { class: 'row', style: 'margin-top:6px' }, h('button', { onclick: () => runPreflight(false), title: 'Audio, lip sync and captions, before the final export' }, 'Check before export')),
          h('div', { id: 'render-estimate', class: 'hint' }, ''), h('div', { id: 'render-status', class: 'hint' }, ''),
          h('p', { class: 'hint' }, 'Renders run in the background in Blender: hoodie cloth, ear and tail springs, the collision solver, then the 3D rule checks. Render scene renders every shot in order and joins them into one video; unchanged shots are reused. Everything goes to DeepInDoodles\\<scene>\\work: videos in renders, logs and rule reports in checks.')]));
      pollRender();
      estimate(prodCtx(), sceneFrames()).then(e => { const el = $('#render-estimate'); if (el) el.textContent = 'Scene: ' + e.text; });
    }
  }
  if (same) c.scrollTop = y;
}
function gazePad() {
  const F = data.face;
  return h('div', { class: 'gaze' }, ...GAZE_ORDER.map(i => h('button', { 'aria-pressed': String(Math.round(current('gaze')) === i), title: F.gazes[i], onclick: () => { pushUndo(); setValue('gaze', i); buildPanel(); drawTracks(); } }, F.gazes[i].replace('Center', '•').replace(/Up|Down|Left|Right/g, m => ({ Up: '↑', Down: '↓', Left: '←', Right: '→' })[m]).replace(' ', ''))));
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
  viewState: () => ({ tab, part, theme: document.body.dataset.theme || 'light', grid: view.grid.visible, onion: view3.onion, silhouette: view3.silhouette, mirror: view3.mirror, keyFilter, snap: snap.on, sub: { ...sub }, tlZoom, rowsMode, docks: DOCK.layoutState() }),
  setViewState: L => {
    if (L.tab) tab = L.tab; if (L.part) part = L.part;
    if (L.theme) { document.body.dataset.theme = L.theme; try { localStorage.setItem('ds3d.theme', L.theme); } catch {} }
    if (L.grid != null) view.grid.visible = L.grid;
    if (L.onion != null) view3.onion = L.onion;
    if (L.silhouette != null) setSilhouette(view, L.silhouette);
    if (L.mirror != null) setMirror(L.mirror);
    if (L.keyFilter) keyFilter = L.keyFilter;
    if (L.snap != null) snap.on = L.snap;
    if (L.sub) Object.assign(sub, L.sub);
    if (L.tlZoom) tlZoom = L.tlZoom;
    if (L.rowsMode) rowsMode = L.rowsMode;
    if (L.docks) DOCK.setLayoutState(L.docks);
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
function toggleSnap() { snap.on = !snap.on; if (stage?.selected) stage.select(stage.selected); toast(snap.on ? 'Snapping: angles to 5°, distances to 5 cm, lens to the presets' : 'Snapping off'); updateHud(); }
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
  bridgeFor: (sc, s) => toBridgeShot(bindShot(sc, s), ALL_IDS(), data.face.faces, sc.character || 'bunny', stageOf(sc, s), materialsOf(sc, s)),
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
window.ds3dClaude = { begin: (tool, n, force, args) => { mcpCall = { force: !!force }; macroRec.tool(tool, args, frame); claude.begin(prodCtx(), tool, n); }, end: (n, failed) => { mcpCall = null; claude.end(prodCtx(), n, failed); updateHud(); } };
// during a Claude (MCP) call nothing may open a blocking dialog: a yes/no needs force: true
// in the call, a typed answer has to come in the call's arguments, and alerts become toasts
let mcpCall = null;
const nativeConfirm = window.confirm.bind(window), nativePrompt = window.prompt.bind(window), nativeAlert = window.alert.bind(window);
window.confirm = msg => { if (!mcpCall) return nativeConfirm(msg); if (mcpCall.force) return true; throw Error(`Needs a yes first: "${msg}" Ask the user, then repeat the call with force: true.`); };
window.prompt = (msg, def) => { if (!mcpCall) return nativePrompt(msg, def); throw Error(`This step asks for typed input ("${msg}"). Pass the value in the tool's arguments instead.`); };
window.alert = msg => { if (!mcpCall) return nativeAlert(msg); toast(String(msg), 5000); };

// ---------------------------------------------------------------- polish.js: autosave, versions, command search, markers
const polCtx = () => ({
  h, api, toast, pushUndo, goto, scene: () => scene, project: () => project, frame: () => frame, file: () => filePath, dirty: () => dirty, recentIds, isFav, cmdId, toggleFav, refreshQuickbar,
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
  // babble lines stay: they are mixed over the new voice (or play alone when it is removed)
  if (BB.linesOf(scene).length) await rebuildBabble({ quiet: true }); else await buildVoiceFx();
  drawTracks(); audioPanelRefresh();
  if (p) toast(`Audio: ${p.split(/[\\/]/).pop()} (${audioInfo().seconds} s). It plays with the timeline and goes into scene renders.`, 5000);
  return audioInfo();
}
// ---------------------------------------------------------------- babble.js: typed lines spoken as cute gibberish
// Every sound is synthesised here (babble.js), nothing is sampled. A rebuild renders all the
// scene's lines into one voice file, mixed over the recorded voice if there is one, keys each
// speaker's mouth from the syllables and writes timed captions. The file name carries a hash
// of what made it, so Undo goes back to the matching older file.
const bbHash = str => { let x = 2166136261; for (let i = 0; i < str.length; i++) { x ^= str.charCodeAt(i); x = Math.imul(x, 16777619); } return (x >>> 0).toString(36); };
async function rebuildBabble({ quiet = false } = {}) {
  const lines = BB.linesOf(scene), basePath = scene.audio?.babble ? scene.audio.base || null : scene.audio?.dry || scene.audio?.path || null, stem = scene.audio?.stem;
  if (!lines.length) {
    if (scene.audio?.babble) { scene.audio = basePath ? { path: basePath, ...(stem ? { stem } : {}) } : null; await loadAudio(api, null); await loadAudio(api, basePath); await buildVoiceFx(); }
    if (scene.captions) for (const k of Object.keys(scene.captions.tracks)) scene.captions.tracks[k] = scene.captions.tracks[k].filter(c => !c.babble);
    dirty = true; apply(); drawTracks(); drawPost();
    return { lines: [], audio: scene.audio?.path || null };
  }
  let base = null, sr = 48000;
  if (basePath) { const d = await decodeChannels(api, basePath); base = d.channels; sr = d.sr; }
  const caps = P.captionsOf(scene);
  const r = BB.build(scene, { leadChar: character(), fps: scene.fps, setKey, base, sr, captionTrack: caps.tracks[caps.active] });
  const tag = bbHash(JSON.stringify([scene.babble, scene.voices, basePath, scene.fps, scene.shots.map(s => [s.uid, s.length]), character()]));
  const root = (await api('settings', {})).rendersRoot, nm = safeName(scene.name);
  const w = await api('write-file', { path: `${root}/${nm}/work/audio/${nm.replace(/ /g, '_')}_babble_${tag}.wav`, data: BB.wavChannelsBase64(r.channels, r.sr) });
  scene.audio = { path: w.path, babble: true, base: basePath, ...(stem ? { stem } : {}) };
  await loadAudio(api, null); await loadAudio(api, w.path);
  await buildVoiceFx();
  dirty = true; apply(); drawTracks(); drawPost();
  const over = r.lines.filter(l => l.pastShotEnd);
  audioPanelRefresh();
  if (!quiet) toast(`Babble: ${r.lines.length} line${r.lines.length > 1 ? 's' : ''}, ${r.keys} mouth keys${base ? ', mixed over your voice' : ''}${over.length ? `. ${over.length} line${over.length > 1 ? 's run' : ' runs'} past the end of the shot: make the shot longer or the line shorter` : ''}`, 6000);
  return { lines: r.lines, keys: r.keys, audio: w.path, mixedOver: basePath };
}
const bbLead = () => character();
const bbIcon = n => { const x = icon(n); x.style.cssText = 'width:14px;height:14px;vertical-align:-2px'; return x; };
const bbDraft = { text: '', who: 'lead', mood: 'neutral' };
function bbHearAll() {
  const text = bbDraft.text || 'Hello there! This is my voice.'; let t = 0;
  for (const k of Object.keys(BB_VOICES)) { const d = BB.dialsOf(scene, k); setTimeout(() => bbPreview(text, 'voice:' + k, bbDraft.mood), t); t += bbSpeak(text, bbVoiceFor(k, d, bbDraft.mood), { style: d.style }).seconds * 1000 + 300; }
}
function bbVoiceOf(who) { return BB.speakerChar(scene, project, who, bbLead()); }
function bbPreview(text, who, mood) {
  const ch = bbVoiceOf(who), d = BB.dialsOf(scene, ch);
  const r = bbSpeak(text || 'Hello there! This is my voice.', bbVoiceFor(ch, d, mood), { style: d.style });
  playSamples(r.samples, r.sr);
  return { char: ch, seconds: +r.seconds.toFixed(2) };
}
async function babbleAct(a = {}) {
  const shotOf = x => (x == null ? project : scene.shots[shotIndex(x)]);
  switch (a.action || 'list') {
    case 'list': return { lines: BB.linesOf(scene).map(l => ({ ...l, shot: scene.shots.find(s => s.uid === l.shot)?.code })), voices: Object.fromEntries(Object.keys(BB_VOICES).map(k => [k, { ...BB_VOICES[k], ...BB.dialsOf(scene, k) }])), audio: scene.audio || null };
    case 'add': {
      const sh = shotOf(a.shot);
      if (a.who != null && a.who !== 'lead' && !BB_VOICES[BB.speakerChar(scene, sh, a.who, bbLead())]) throw Error('who must be lead, a co-star index, or voice:' + Object.keys(BB_VOICES).join(', voice:'));
      if (a.mood && !BB_MOODS[a.mood]) throw Error('mood must be ' + Object.keys(BB_MOODS).join(', '));
      if (a.style && !BB_STYLES[a.style]) throw Error('style must be ' + Object.keys(BB_STYLES).join(', '));
      pushUndo('Babble line');
      const line = BB.addLine(scene, sh, a.frame ?? (sh === project ? frame : 0), a.text, { who: a.who ?? 'lead', mood: a.mood || 'neutral', style: a.style });
      return { line, ...(await rebuildBabble()) };
    }
    case 'remove': { pushUndo('Remove babble line'); BB.removeLine(scene, a.id); return rebuildBabble(); }
    case 'clear': { pushUndo('Clear babble'); scene.babble = []; return rebuildBabble(); }
    case 'voice': {
      const ch = a.character || bbLead();
      if (!BB_VOICES[ch]) throw Error('character must be ' + Object.keys(BB_VOICES).join(', '));
      pushUndo('Babble voice');
      const d = BB.dialsOf(scene, ch);
      if (a.reset) for (const k of Object.keys(d)) delete d[k];
      if (a.style) { if (!BB_STYLES[a.style]) throw Error('style must be ' + Object.keys(BB_STYLES).join(', ')); d.style = a.style; }
      for (const [k, [lo, hi]] of Object.entries(BB_DIALS)) if (a[k] != null) d[k] = Math.max(lo, Math.min(hi, Number(a[k])));
      const out = { character: ch, voice: { ...BB_VOICES[ch], ...d } };
      if (BB.linesOf(scene).length) Object.assign(out, await rebuildBabble({ quiet: true }));
      return out;
    }
    case 'preview': return bbPreview(a.text, a.who ?? 'lead', a.mood || 'neutral');
    case 'rebuild': return rebuildBabble();
    default: throw Error('action must be list, add, remove, clear, voice, preview or rebuild');
  }
}
async function bbRun(a) { try { return await babbleAct(a); } catch (e) { toast(e.message, 5000); return null; } finally { audioPanelRefresh(); } }
const audioPanelRefresh = () => { if (tab === 'audio') buildPanel(); };
function openBabble() { setTab('audio', 'babble'); const inp = document.querySelector('input[aria-label="Line"]'); inp?.focus(); inp?.setSelectionRange(inp.value.length, inp.value.length); }
// Audio workspace › Babble voice: who, mood and the line on the left; their voice and this shot's lines on the right
function babblePanel() {
  const who = [['lead', `${(BB_VOICES[bbLead()] || {}).name || bbLead()} (lead)`], ...CS.costarsOf(project).map((c, i) => [String(i), `${(BB_VOICES[c.character] || {}).name || c.character} (co-star ${i + 1})`])];
  // everyone else can still be heard, and speak off screen: the line plays, no mouth moves
  for (const k of Object.keys(BB_VOICES)) if (k !== bbLead() && !CS.costarsOf(project).some(c => c.character === k)) who.push(['voice:' + k, `${BB_VOICES[k].name} (voice only)`]);
  if (!who.some(w => w[0] === String(bbDraft.who))) bbDraft.who = 'lead';
  const ch = bbVoiceOf(bbDraft.who), d = BB.dialsOf(scene, ch), v = { ...BB_VOICES[ch], ...d };
  const pick = (opts, cur, set) => opts.map(([k, label]) => h('button', { 'aria-pressed': String(String(cur) === String(k)), onclick: () => { set(k); buildPanel(); } }, label));
  const add = async () => { const r = await bbRun({ action: 'add', text: bbDraft.text, who: bbDraft.who, mood: bbDraft.mood, frame }); if (r) { bbDraft.text = ''; openBabble(); } };
  const text = h('input', { type: 'text', value: bbDraft.text, placeholder: 'Type what the character says… (? lifts the end, ! punches it)', style: 'flex:1;min-width:12em', 'aria-label': 'Line', oninput: e => { bbDraft.text = e.target.value; }, onkeydown: e => { e.stopPropagation(); if (e.key === 'Enter' && bbDraft.text.trim()) add(); } });
  const dials = Object.entries(BB_DIALS).map(([k, [lo, hi, step, label]]) => {
    const out = h('span', { class: 'hint', style: 'min-width:3.2em;display:inline-block' }, String(+(+v[k]).toFixed(2)));
    const sl = h('input', { type: 'range', min: lo, max: hi, step, value: v[k], 'aria-label': label, style: 'width:84px', oninput: e => { out.textContent = String(+(+e.target.value).toFixed(2)); }, onchange: e => { bbRun({ action: 'voice', character: ch, [k]: Number(e.target.value) }); } });
    return h('label', { class: 'row', style: 'gap:4px', title: `${label} for ${v.name}. Changes every ${v.name} line in this scene.` }, { 'Pitch (Hz)': 'Pitch', 'Pitch range': 'Range' }[label] || label, sl, out);
  });
  const lines = BB.linesOf(scene).filter(l => l.shot === project.uid);
  return cols('two', [
    h('p', { class: 'hint' }, 'Type a line and the character speaks it as cute gibberish, made from scratch here. The mouth moves on every syllable and the line becomes a timed caption. Lines mix over a recorded voice if the scene has one.'),
    h('div', { class: 'row', style: 'flex-wrap:wrap;gap:6px' }, h('b', {}, 'Who '), ...pick(who, bbDraft.who, k => { bbDraft.who = k; }).map((b, i) => { b.classList.add('bb-who'); b.prepend(h('img', { src: `chars/${bbVoiceOf(who[i][0])}.png`, alt: '', draggable: 'false' })); return b; })),
    h('div', { class: 'row', style: 'flex-wrap:wrap;gap:6px;margin-top:6px' }, h('b', {}, 'Mood '), ...pick(Object.entries(BB_MOODS).map(([k, m]) => [k, m.label]), bbDraft.mood, k => { bbDraft.mood = k; })),
    h('div', { class: 'row', style: 'gap:6px;margin-top:6px;flex-wrap:wrap' }, text,
      h('button', { title: 'Hear this line in this voice (nothing is added)', onclick: () => { try { bbPreview(bbDraft.text, bbDraft.who, bbDraft.mood); } catch (e) { toast(e.message, 4000); } } }, bbIcon('play'), ' Hear it'),
      h('button', { title: 'Hear this line in every character\'s voice, one after another', onclick: () => bbHearAll() }, 'Hear all voices'),
      h('button', { class: 'primary', title: 'Add the line at the playhead of this shot (Enter)', onclick: add }, 'Add at playhead'))],
  [
    h('div', { class: 'row', style: 'flex-wrap:wrap;gap:6px' }, h('b', {}, `${v.name}'s voice `), ...Object.entries(BB_STYLES).map(([k, label]) => h('button', { 'aria-pressed': String(v.style === k), title: { syllables: 'One soft sound per syllable, closest to speech', letters: 'A quick blip per letter, chattery', tones: 'Pure musical beeps' }[k], onclick: () => bbRun({ action: 'voice', character: ch, style: k }) }, label))),
    h('div', { class: 'row', style: 'flex-wrap:wrap;gap:12px;white-space:nowrap;margin-top:6px' }, ...dials, h('button', { title: `Back to ${v.name}'s own voice`, onclick: () => bbRun({ action: 'voice', character: ch, reset: true }) }, 'Reset')),
    h('h3', {}, lines.length ? `Lines on this shot (${lines.length})` : 'No lines on this shot yet'),
    h('div', { class: 'ds-list' }, ...lines.map(l => h('div', { class: 'row', style: 'gap:6px' },
      h('button', { class: 'bb-at', title: `Go to frame ${l.f}`, onclick: () => goto(l.f) }, `frame ${l.f}`), h('span', { style: 'min-width:7em' }, who.find(w => w[0] === String(l.who))?.[1] || l.who), h('span', { class: 'hint' }, BB_MOODS[l.mood]?.label || ''),
      h('span', { style: 'flex:1' }, l.text),
      h('button', { title: 'Hear it', onclick: () => bbPreview(l.text, l.who, l.mood) }, bbIcon('play')),
      h('button', { title: 'Remove this line (Ctrl+Z brings it back)', onclick: () => bbRun({ action: 'remove', id: l.id }) }, bbIcon('trash'))))),
    h('div', { class: 'row', style: 'gap:6px;margin-top:6px' }, h('button', { title: 'Render every line in the scene again', onclick: () => bbRun({ action: 'rebuild' }) }, 'Rebuild voice'))]);
}
// ---------------------------------------------------------------- blocks.js: layers on the timeline, as in the 2D studio
// 'lead', 'c0'.. (co-stars) and 'd:<id>' (drawings). Isolate is for looking only: it never reaches a render.
let cutMode = false;
function layerOf(key) {
  if (key == null || key === 'lead') return { key: 'lead', kind: 'char', owner: project, name: charName(), tracks: () => [project.tracks, ...(project.layers || []).map(L => L.tracks)] };
  const m = /^c?(\d+)$/.exec(String(key));
  if (m) { const c = CS.costarsOf(project)[Number(m[1])]; if (!c) throw Error(`No co-star ${m[1]} on this shot`); return { key: 'c' + m[1], kind: 'char', owner: c, name: castName(c.character), tracks: () => [c.tracks] }; }
  const id = String(key).replace(/^d:/, ''), i = DR.drawingsOf(project).findIndex(d => d.id === id);
  if (i < 0) throw Error(`No layer ${key} on this shot`);
  return { key: 'd:' + id, kind: 'draw', d: project.drawings[i], index: i, name: project.drawings[i].name };
}
const allLayers = () => ['lead', ...CS.costarsOf(project).map((_, i) => 'c' + i), ...DR.drawingsOf(project).map(d => 'd:' + d.id)];
function blocksChanged() { dirty = true; apply(); updateHud(); drawTracks(); if (tab === 'draw') buildPanel(); }
function blocksAct(a = {}) {
  const len = project.length, L = () => layerOf(a.layer);
  switch (a.action || 'list') {
    case 'list': return { layers: allLayers().map(k => { const l = layerOf(k); return { layer: k, name: l.name, kind: l.kind, shown: !(l.owner || l.d).hidden, isolated: solo === k, ...(l.kind === 'char' ? { blocks: BK.clipsOf(l.owner, len) } : { blocks: [{ id: l.d.id, start: BK.drawingSpan(l.d, len)[0], end: BK.drawingSpan(l.d, len)[1] }], place: BK.placeOf(l.d) }) }; }) };
    case 'split': {
      const l = L(), f = a.frame ?? frame;
      pushUndo('Cut block');
      try { if (l.kind === 'char') BK.split(l.owner, len, f); else BK.splitDrawing(project, l.index, f, len, () => 'dr' + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36)); }
      catch (e) { undoStack.pop(); throw e; }
      blocksChanged(); return blocksAct({ action: 'list' });
    }
    case 'move': {
      const l = L(); pushUndo('Move block');
      if (l.kind === 'char') { BK.move(l.owner, len, a.id ?? 'all', a.start, l.tracks()); BK.tidy(l.owner, len); } else BK.moveDrawing(l.d, len, a.start);
      blocksChanged(); return blocksAct({ action: 'list' });
    }
    case 'trim': {
      const l = L(); pushUndo('Trim block');
      if (l.kind === 'char') { BK.resize(l.owner, len, a.id ?? 'all', a.start, a.end); BK.tidy(l.owner, len); } else BK.resizeDrawing(l.d, len, a.start, a.end);
      blocksChanged(); return blocksAct({ action: 'list' });
    }
    case 'remove': {
      const l = L(); pushUndo('Remove block');
      if (l.kind === 'char') BK.remove(l.owner, len, a.id ?? 'all'); else { DR.remove(project, l.index); drawSel = 0; if (solo === l.key) solo = null; }
      blocksChanged(); return blocksAct({ action: 'list' });
    }
    case 'fill': { const l = L(); if (l.kind !== 'char') throw Error('Only a character has gaps to fill'); pushUndo('Add block'); BK.fillGap(l.owner, len, a.frame ?? frame); BK.tidy(l.owner, len); blocksChanged(); return blocksAct({ action: 'list' }); }
    case 'show': { const l = L(), o = l.owner || l.d; pushUndo(a.on === false ? 'Hide layer' : 'Show layer'); if (a.on === false) o.hidden = true; else delete o.hidden; blocksChanged(); return blocksAct({ action: 'list' }); }
    case 'isolate': { solo = a.layer == null ? null : L().key; apply(); drawTracks(); return { isolated: solo }; }
    case 'place': {
      const l = L(), p = BK.PLACES.find(x => x[0] === a.place);
      if (l.kind !== 'draw' || !p) throw Error('place needs a drawing layer and one of ' + BK.PLACES.map(x => x[0]).join(', '));
      return dr({ action: 'set', index: l.index, layer: p[0] === 'screen' ? 'screen' : 'scene', ...(p[0] === 'screen' ? {} : { depth: p[2] }) }).then(r => { drawTracks(); return r; });
    }
    default: throw Error('action must be list, split, move, trim, remove, fill, show, isolate or place');
  }
}
async function blRun(a) { try { return await blocksAct(a); } catch (e) { toast(e.message, 4000); return null; } }
// one block: drag the middle to move it, the ends to trim, right-click for more
function blockEl({ a, b, label, ppf, title, cls = '', ends = true, commit, click, menu, cut }) {
  const el = h('div', { class: 'block ' + cls, style: `left:${a * ppf + 1}px;width:${Math.max(6, (b - a) * ppf - 2)}px`, title }, ends ? h('i', { class: 'l' }) : null, h('span', {}, label), ends ? h('i', { class: 'r' }) : null);
  el.addEventListener('pointerdown', e => {
    if (e.button) return;
    e.stopPropagation();
    if (cutMode && cut) { const r = el.parentElement.getBoundingClientRect(); cut(Math.round((e.clientX - r.left) / ppf)); return; }
    const mode = e.target.classList.contains('l') ? 'l' : e.target.classList.contains('r') ? 'r' : 'm', w = DOCK.winOf(el), x0 = e.clientX;
    let na = a, nb = b, moved = false;
    const mv = ev => {
      const d = Math.round((ev.clientX - x0) / ppf); if (d) moved = true;
      if (mode === 'm') { na = Math.max(0, Math.min(project.length - (b - a), a + d)); nb = na + b - a; }
      else if (mode === 'l') na = Math.max(0, Math.min(b - 1, a + d)); else nb = Math.min(project.length, Math.max(a + 1, b + d));
      el.style.left = `${na * ppf + 1}px`; el.style.width = `${Math.max(6, (nb - na) * ppf - 2)}px`;
    };
    const up = () => { w.removeEventListener('pointermove', mv); w.removeEventListener('pointerup', up); if (moved) commit?.(na, nb, mode); else click?.(); };
    w.addEventListener('pointermove', mv); w.addEventListener('pointerup', up);
  });
  if (menu) el.addEventListener('contextmenu', e => { e.preventDefault(); e.stopPropagation(); ctxMenu(e, menu); });
  return el;
}
function layerName(key, name, title, extra) {
  const l = layerOf(key), o = l.owner || l.d, off = !!o.hidden;
  return h('div', { class: 'tname layer-name', title }, h('span', { class: 'tn' }, name), extra,
    h('button', { class: 'lb', 'aria-pressed': String(!off), title: off ? 'Hidden, in the render too. Click to show.' : 'Showing. Click to hide this layer, in the render too.', 'aria-label': `Show ${name}`, onclick: () => blRun({ action: 'show', layer: key, on: off }) }, off ? '○' : '●'),
    h('button', { class: 'lb', 'aria-pressed': String(solo === key), title: 'Isolate: see only this layer while you work. It never changes the render.', 'aria-label': `Isolate ${name}`, onclick: () => blRun({ action: 'isolate', layer: solo === key ? null : key }) }, 'S'));
}
function layerRows(ppf) {
  const out = [], len = project.length;
  if (solo && !allLayers().includes(solo)) solo = null;
  const lane2 = kids => h('div', { class: 'lane' }, ...kids);
  // what the character is on screen for
  const charRow = key => {
    const l = layerOf(key), blocks = BK.clipsOf(l.owner, len);
    const row = lane2(blocks.map(c => blockEl({ a: c.start, b: c.end, label: l.name, ppf, title: `${l.name}: frames ${c.start} to ${c.end}. Drag to move it with its keys, drag an end to trim. A gap hides ${l.name}. Right-click for more.`,
      commit: (a, b, mode) => (mode === 'm' ? blRun({ action: 'move', layer: key, id: c.id, start: a }) : blRun({ action: 'trim', layer: key, id: c.id, start: a, end: b })),
      cut: f => blRun({ action: 'split', layer: key, frame: f }),
      menu: [['Cut here (at the playhead)', () => blRun({ action: 'split', layer: key, frame })], ['Take this block away (a gap)', () => blRun({ action: 'remove', layer: key, id: c.id })]] })));
    row.addEventListener('contextmenu', e => { e.preventDefault(); const r = row.getBoundingClientRect(), f = Math.round((e.clientX - r.left) / ppf); ctxMenu(e, [['Fill this gap with a block', () => blRun({ action: 'fill', layer: key, frame: f })]]); });
    return h('div', { class: 'trow block-row' }, layerName(key, l.name, `${l.name}'s layer`), row);
  };
  out.push(charRow('lead'));
  CS.costarsOf(project).forEach((_, i) => out.push(charRow('c' + i)));
  DR.drawingsOf(project).forEach((d, i) => {
    const key = 'd:' + d.id, [a, b] = BK.drawingSpan(d, len);
    const place = h('select', { class: 'lsel', 'aria-label': `Where ${d.name} sits`, title: 'Where it sits against the characters: over everything, in front, through them, or behind', onclick: e => e.stopPropagation() }, ...BK.PLACES.map(([k, n]) => h('option', { value: k, selected: BK.placeOf(d) === k }, n)));
    place.addEventListener('change', () => blRun({ action: 'place', layer: key, place: place.value }));
    out.push(h('div', { class: 'trow block-row' }, layerName(key, d.name, `${d.name}: a drawing layer`, place),
      lane2([blockEl({ a, b, label: d.name, ppf, cls: 'draw' + (tab === 'draw' && i === drawSel ? ' sel' : ''), title: `${d.name}: frames ${a} to ${b}. Drag to move, drag an end to trim. Click to edit it in Draw.`,
        commit: (na, nb, mode) => (mode === 'm' ? blRun({ action: 'move', layer: key, start: na }) : blRun({ action: 'trim', layer: key, start: na, end: nb })),
        cut: f => blRun({ action: 'split', layer: key, frame: f }), click: () => { drawSel = i; setTab('draw'); drawTracks(); },
        menu: [['Cut here (at the playhead)', () => blRun({ action: 'split', layer: key, frame })], ['Remove this drawing', () => blRun({ action: 'remove', layer: key })]] })])));
  });
  // Babble lines as blocks: drag one to change when it is said
  const lines = BB.linesOf(scene).filter(l => l.shot === project.uid);
  if (lines.length) out.push(h('div', { class: 'trow block-row' }, h('div', { class: 'tname', title: 'Babble lines on this shot. Drag one to change when it is said.' }, h('span', { class: 'tn' }, 'Babble')),
    lane2(lines.map(l => { const [a, b] = bbSpan(l); return blockEl({ a, b: Math.min(len, b), label: l.text, ppf, cls: 'voice', ends: false, title: `"${l.text}" at frame ${l.f}. Drag to retime.`, commit: na => bbRetime(l, na), click: () => goto(l.f) }); }))));
  return out;
}
const bbLens = new Map();
function bbSpan(l) {
  const k = JSON.stringify([l.text, l.who, l.mood, l.style, scene.voices, scene.fps]);
  if (!bbLens.has(k)) bbLens.set(k, Math.ceil(BB.render(scene, l, character()).r.seconds * scene.fps));
  return [l.f, l.f + bbLens.get(k)];
}
async function bbRetime(l, f) {
  pushUndo('Move babble line');
  const [a, b] = bbSpan(l), tracks = l.who == null || l.who === 'lead' ? project.tracks : CS.costarsOf(project)[Number(l.who)]?.tracks;
  if (tracks?.mouth) tracks.mouth = tracks.mouth.filter(k => k.f < a || k.f > b);
  l.f = f;
  await rebuildBabble({ quiet: true });
}
// ---------------------------------------------------------------- voicefx.js: voice effects on the scene voice
// the recording stays untouched: scene.audio.dry keeps it, scene.audio.path is the processed copy
async function buildVoiceFx() {
  const a = scene.audio, dry = a?.dry || a?.path;
  if (!dry) return null;
  if (!VF.isActive(scene.voiceFx)) {
    if (a.dry) { const { dry: d, ...rest } = a; scene.audio = { ...rest, path: d }; await loadAudio(api, null); await loadAudio(api, d); }
    return null;
  }
  const d = await decodeChannels(api, dry), out = VF.processChannels(d.channels, d.sr, scene.voiceFx);
  const root = (await api('settings', {})).rendersRoot, nm = safeName(scene.name);
  const w = await api('write-file', { path: `${root}/${nm}/work/audio/${nm.replace(/ /g, '_')}_fx_${bbHash(JSON.stringify([dry, scene.voiceFx]))}.wav`, data: BB.wavChannelsBase64(out, d.sr) });
  scene.audio = { ...a, path: w.path, dry };
  await loadAudio(api, null); await loadAudio(api, w.path);
  return w.path;
}
async function voiceFxAct(a = {}) {
  if ((a.action || 'set') === 'list') return { current: scene.voiceFx || null, presets: VF.PRESETS, effects: VF.EFFECTS };
  if (!(scene.audio?.dry || scene.audio?.path)) throw Error('Add a voice first: import audio, or add a Babble line');
  pushUndo('Voice effect');
  if (a.action === 'reset') delete scene.voiceFx;
  else {
    const P0 = a.preset ? VF.PRESETS[a.preset] : null;
    if (a.preset && !P0) throw Error('preset must be ' + Object.keys(VF.PRESETS).join(', '));
    const n = VF.normalize({ ...scene.voiceFx, ...a, ...(P0 ? { pitch: P0[1], effect: P0[2] } : {}) });
    const preset = a.preset || (a.pitch == null && a.effect == null ? scene.voiceFx?.preset : null);
    scene.voiceFx = { ...n, ...(preset ? { preset } : {}) };
  }
  toast('Working on the voice…'); await new Promise(r => setTimeout(r, 30));
  const path = await buildVoiceFx();
  dirty = true; apply(); drawTracks(); audioPanelRefresh();
  toast(path ? 'Voice effect on. It plays with the timeline and goes into scene renders.' : 'Voice effect off', 4000);
  return { fx: scene.voiceFx || null, audio: scene.audio?.path || null };
}
async function fxRun(a) { try { return await voiceFxAct(a); } catch (e) { toast(e.message, 5000); return null; } }
function voiceFxPanel() {
  const fx = VF.normalize(scene.voiceFx || {}), cur = scene.voiceFx?.preset || (scene.voiceFx ? null : 'natural');
  const slider = (label, k, lo, hi, step, v, show) => { const out = h('span', { class: 'hint', style: 'min-width:3.6em;display:inline-block' }, show(v)); return h('label', { class: 'row', style: 'gap:8px;margin-top:8px', title: label }, h('b', { style: 'min-width:4.5em' }, label), h('input', { type: 'range', min: lo, max: hi, step, value: v, 'aria-label': label, style: 'flex:1;max-width:320px', oninput: e => { out.textContent = show(Number(e.target.value)); }, onchange: e => fxRun({ [k]: Number(e.target.value) }) }), out); };
  return cols('two', [
    h('h3', {}, 'Voice'), h('div', { class: 'chips' }, ...Object.entries(VF.PRESETS).map(([k, [n]]) => h('button', { 'aria-pressed': String(cur === k), onclick: () => fxRun({ preset: k }) }, n))),
    h('p', { class: 'hint' }, 'The effect goes over the whole scene voice, Babble lines included. Your recording stays as it is, and lip sync and captions keep their timing.')],
  [ h('h3', {}, 'Fine tune'), slider('Pitch', 'pitch', -12, 12, 1, fx.pitch, v => `${v > 0 ? '+' : ''}${v} st`), slider('Amount', 'mix', 0, 1, 0.05, fx.mix, v => `${Math.round(v * 100)}%`),
    h('h3', {}, 'Effect'), h('div', { class: 'chips' }, ...Object.entries(VF.EFFECTS).map(([k, n]) => h('button', { 'aria-pressed': String(fx.effect === k), onclick: () => fxRun({ effect: k }) }, n))),
    h('div', { class: 'row', style: 'gap:6px;margin-top:10px' }, h('button', { 'aria-pressed': String(fx.on), title: 'Compare with the dry voice', onclick: () => fxRun({ on: !fx.on }) }, fx.on ? 'Effect on' : 'Effect off'), h('button', { onclick: () => fxRun({ action: 'reset' }) }, 'Reset'))]);
}
// ---------------------------------------------------------------- transcribe.js: the scene voice to timed words and captions
const stt = { busy: false, status: '', language: 'auto' };
async function transcribeAct(a = {}) {
  const A = scene.audio, path = A?.babble ? A.base : A?.dry || A?.path;
  if (!path) throw Error(A?.babble ? 'Babble is gibberish, so there is nothing to transcribe. Import a recorded voice first.' : 'Import the voice for the scene first (Add voice in this workspace)');
  if (stt.busy) throw Error('Already transcribing');
  stt.busy = true; stt.status = 'Getting ready…'; audioPanelRefresh();
  try {
    const d = await decodeChannels(api, path);
    const r = await STT.transcribe(STT.to16k(d.channels, d.sr), { language: a.language || stt.language, onStatus: t => { stt.status = t; toast(t); const n = document.querySelector('#stt-status'); if (n) n.textContent = t; } });
    pushUndo('Transcribe'); scene.transcript = r; dirty = true;
    toast(`Transcribed ${r.words.length} words`, 4000);
    return { text: r.text, words: r.words.length };
  } finally { stt.busy = false; stt.status = ''; audioPanelRefresh(); }
}
function transcriptCaptions() {
  const words = scene.transcript?.words;
  if (!words?.length) throw Error('Transcribe the voice first');
  pushUndo('Captions from the transcript');
  const caps = P.captionsOf(scene), t = caps.tracks[caps.active];
  caps.tracks[caps.active] = t.filter(c => !c.stt);
  let n = 0;
  for (const c of STT.captionsFrom(words)) {
    let start = 0;
    const F = Math.round(c.t0 * scene.fps), shot = scene.shots.find(s => { if (F < start + s.length) return true; start += s.length; return false; });
    if (!shot) continue;
    P.addCaption(scene, shot, F - start, Math.round(c.t1 * scene.fps) - start + Math.round(scene.fps * 0.15), c.text).stt = true;
    n++;
  }
  dirty = true; apply(); drawPost(); toast(`${n} timed captions from the transcript`, 4000);
  return { captions: n };
}
const sttRun = async fn => { try { return await fn(); } catch (e) { toast(e.message, 6000); return null; } };
function transcribePanel() {
  const T0 = scene.transcript;
  return cols('two', [
    h('h3', {}, 'Transcribe the scene voice'),
    h('div', { class: 'row', style: 'flex-wrap:wrap;gap:6px' }, h('b', {}, 'Language '), ...STT.LANGUAGES.map(([k, n]) => h('button', { 'aria-pressed': String(stt.language === k), onclick: () => { stt.language = k; buildPanel(); } }, n))),
    h('div', { class: 'row', style: 'gap:6px;margin-top:10px' }, h('button', { class: 'primary', disabled: stt.busy, onclick: () => sttRun(transcribeAct) }, stt.busy ? 'Transcribing…' : T0 ? 'Transcribe again' : 'Transcribe')),
    h('p', { class: 'hint', id: 'stt-status' }, stt.status || 'Runs on this PC, so your audio stays here. The speech model downloads once, about 90 MB, the first time.')],
  [ h('h3', {}, 'Transcript'), T0 ? h('div', { class: 'stt-text' }, T0.text) : h('p', { class: 'hint' }, 'The words show here, with their timing kept.'),
    T0 ? h('div', { class: 'row', style: 'gap:6px;margin-top:10px' }, h('button', { title: 'Timed captions from these words, replacing the last set made here', onclick: () => sttRun(transcriptCaptions) }, 'Make timed captions'), h('button', { title: 'One shot per sentence', onclick: () => sttRun(() => splitSentences(T0.text)) }, 'Split into shots')) : null]);
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
// lip sync from the scene voice: mouth keys on one shot, or on every shot (all)
async function lipsyncFromAudio({ shot = null, all = false, gate, hold, stem, engine } = {}) {
  // right after opening a scene the voice may still be decoding: wait for it rather than fail
  if (scene.audio?.path && audioInfo()?.path !== scene.audio.path) await loadAudio(api, scene.audio.path);
  if (!audioInfo()) throw Error('Import the voice for the scene first (File › Import audio…)');
  // a separated vocal (stem) is kept with the scene audio, so later lip syncs read it too; '' clears it
  if (stem != null && scene.audio) { if (stem) scene.audio.stem = stem; else delete scene.audio.stem; }
  await loadStem(api, scene.audio?.stem || null);
  pushUndo('Lip sync from the voice');
  const opts = { ...(gate != null ? { gate: Number(gate) } : {}), ...(hold != null ? { hold: Number(hold) } : {}), ...(engine ? { engine } : {}) };
  const st = shotStarts(), which = all ? scene.shots.map((_, i) => i) : [shot ?? scene.active];
  const out = which.map(i => { const s = scene.shots[i]; if (!s) throw Error('No shot ' + i); return { shot: i, code: s.code, keys: audioLipsync(s, st[i], setKey, opts) }; });
  // babble lines key their own mouths again over the voice's lip sync
  if (BB.linesOf(scene).length) await rebuildBabble({ quiet: true });
  dirty = true; apply(); drawTracks();
  toast(`Lip sync: ${out.reduce((n, o) => n + o.keys, 0)} mouth keys on ${out.length} shot${out.length > 1 ? 's' : ''}`);
  return { shots: out };
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
  h, api, toast, pushUndo, goto, audioStream: () => (audioInfo() ? audioStreamFrom(sceneStart() / scene.fps) : null), view: () => view, scene: () => scene, project: () => project, frame: () => frame,
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
// a whole pose: every control keyed first, then one redraw (a redraw per control took seconds)
function putPose(v) { pushUndo(); for (const [id, x] of Object.entries(v)) setValue(id, x, { now: false }); apply(); drawTracks(); buildPanel(); }
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
const presetCtx = () => ({ view, project: () => project, frame: () => frame, current, setValue, pushUndo, toast, refresh: () => { apply(); drawTracks(); }, costarFraming: () => { apply(); return view.costarFraming(); } });
function frameBunny() { camSet({ tx: 0, ty: 0, tz: 0.52, dist: 3.0 * current('cam.lens') / 50 }); }

// ---------------------------------------------------------------- viewport interaction
// canvas tools (the rail on the canvas's right edge, as in the 2D app). Select: click picks a
// prop, a set piece or Bunny; dragging empty space orbits. Move / Rotate / Scale: the same, with
// that gizmo. Orbit and Pan: dragging always moves the camera.
let tool = 'select';
const GIZMO = { select: 'translate', move: 'translate', rotate: 'rotate', scale: 'scale' };
function setTool(t) {
  tool = t;
  if (stage && GIZMO[t]) stage.setMode(GIZMO[t]);
  if (stage && (t === 'orbit' || t === 'pan')) { stage.select(null); }
  buildRail(); updateHud();
  return tool;
}
function selectBunny() { if (!stage) return; stage.select({ type: 'bunny' }, GIZMO[tool] || 'translate'); updateHud(); }
function clearSelection() { if (stage?.selected) { stage.select(null); if (tab === 'stage') buildPanel(); drawTracks(); updateHud(); return true; } return false; }
function bindViewport() {
  const cv = $('#view');
  let drag = null;
  cv.addEventListener('pointerdown', e => {
    if (e.button === 2) return;
    if (stage?.busy()) return;   // the gizmo has this drag
    cv.setPointerCapture(e.pointerId); cv.classList.add('dragging');
    if (ikOn && !e.shiftKey) {
      const hit = A2.pick(view, e.clientX, e.clientY);
      if (hit && A2.LIMB[hit.part]) { pushUndo('IK drag'); drag = { x: e.clientX, y: e.clientY, ik: A2.ikDrag(view, valuesNow(), hit.part, range), limb: hit.part }; return; }
    }
    pushUndo('Camera'); drag = { x: e.clientX, y: e.clientY, shift: e.shiftKey || tool === 'pan' || e.button === 1, cam: Object.fromEntries(CAM_IDS.map(id => [id, current(id)])) };
  });
  cv.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (Math.hypot(dx, dy) > 3) drag.moved = true;
    if (!drag.moved) return;
    if (drag.ik) { const r = drag.ik(e.clientX, e.clientY); if (r) for (const [id, v] of Object.entries(r.values)) setValue(id, v); return; }
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
  const end = (e, cancel) => {
    if (!drag) return;
    const was = drag;
    drag = null; cv.classList.remove('dragging');
    if (!was.moved) { undoStack.pop(); if (!cancel && !was.ik) canvasClick(was.x, was.y, e); }
    drawTracks();
  };
  cv.addEventListener('pointerup', e => end(e, false));
  cv.addEventListener('pointercancel', e => end(e, true));
  cv.addEventListener('contextmenu', e => {
    e.preventDefault();
    const r = cv.getBoundingClientRect(), hit = stage?.pick((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height);
    if (hit?.type === 'item') { selectItem(hit.index); const i = hit.index; ctxMenu(e, [['Move (W)', () => { setTool('move'); selectItem(i); }], ['Rotate (E)', () => { setTool('rotate'); selectItem(i); }], ['Scale (R)', () => { setTool('scale'); selectItem(i); }], '-', ['Drop to the floor', () => dropItem(i)], ['Duplicate', () => duplicateItem(i)], ['Open in Stage › Items', () => setTab('stage', 'items')], '-', ['Remove', () => { stage.select(null); removeItem(libCtx(), i); apply(); drawTracks(); buildPanel(); }]]); }
    else if (hit?.type === 'piece') { const id = hit.id; ctxMenu(e, [['Reset this piece', () => { pushUndo('Reset piece'); editPiece(id, null); buildPanel(); }], ['Hide this piece', () => { const st = stageOf(scene, project); pushUndo('Hide piece'); setStage(libCtx(), { setProps: { ...(st.setProps || {}), [id]: false } }, !!libUi.shotOnly); apply(); buildPanel(); }]]); }
    else ctxMenu(e, [['Select Bunny (move him on the floor)', selectBunny], ['Frame Bunny (F)', frameBunny], ['Floor grid (G)', () => { view.grid.visible = !view.grid.visible; }], ['Onion skin (O)', () => { view3.onion = !view3.onion; apply(); }]]);
  });
  cv.addEventListener('wheel', e => {
    e.preventDefault();
    pushUndo();
    if (e.altKey) setValue('cam.lens', Math.round(current('cam.lens') * Math.exp(-e.deltaY * 0.001)));
    else setValue('cam.dist', current('cam.dist') * Math.exp(e.deltaY * 0.001));
    drawTracks();
  }, { passive: false });
}
// a click in the 3D view: a prop or set piece gets the gizmo, a click on the character opens that
// part's controls (and Alt+click selects him to move him on the floor); empty space clears
function canvasClick(x, y, e = {}) {
  if (tool === 'orbit' || tool === 'pan') return clickPick(x, y);
  const r = $('#view').getBoundingClientRect();
  const body = A2.pick(view, x, y), hit = stage?.pick((x - r.left) / r.width, (y - r.top) / r.height);
  const bodyDist = body?.point ? body.point.distanceTo(view.camera.position) : Infinity;
  if (hit && (!body || hit.dist < bodyDist)) {
    if (hit.type === 'item') { selectItem(hit.index, GIZMO[tool]); toast(`${libRowMap().get(project.items[hit.index].id)?.name || 'Item'} selected: drag the arrows to move it (W move, E rotate, R scale, Esc clears)`); }
    else { stage.select({ type: 'piece', id: hit.id, obj: hit.obj }, GIZMO[tool]); toast(`Set piece ${hit.id} selected: drag to move it for this ${libUi.shotOnly || project.stage?.pieces ? 'shot' : 'scene'}`); }
    updateHud(); return hit;
  }
  if (body) { if (e.altKey || tool !== 'select' || tab === 'stage') { selectBunny(); return { bunny: true }; } clearSelection(); return clickPick(x, y); }
  clearSelection();
  return null;
}

// a click on the character opens that part's controls
const PICKED = { ears: 'ears', head: 'head', body: 'body', armL: 'armL', armR: 'armR', legL: 'legL', legR: 'legR', whole: 'whole' };
function clickPick(x, y) {
  const hit = A2.pick(view, x, y);
  if (!hit) return null;
  part = PICKED[hit.part] || 'whole';
  if (tab !== 'pose') { tab = 'pose'; layout(); }
  buildTabs(); buildPanel();
  return { part, mesh: hit.mesh };
}

function buildRail() {
  const b = (id, label, ic, title, fn, on) => h('button', { id: 'tool-' + id, title, 'aria-label': title, 'aria-pressed': on == null ? null : String(!!on), onclick: fn }, icon(ic), label);
  const t = (id, label, ic, title) => b(id, label, ic, title, () => setTool(id), tool === id);
  $('#rail').replaceChildren(
    t('select', 'Select', 'select', 'Select (Q): click a prop, set piece or Bunny\'s part. Drag empty space to orbit.'),
    t('move', 'Move', 'move', 'Move (W): click a prop, a set piece or Bunny, then drag an arrow'),
    t('rotate', 'Rotate', 'rotate', 'Rotate (E): click a prop, a set piece or Bunny, then drag a ring'),
    t('scale', 'Scale', 'scale', 'Scale (R): click a prop or set piece, then drag a handle'),
    h('hr'),
    t('orbit', 'Orbit', 'orbit', 'Orbit: dragging always turns the camera around the aim'),
    t('pan', 'Pan', 'hand', 'Pan: dragging always moves the camera aim (Shift+drag does it with any tool)'),
    b('ik', 'IK', 'ik', 'IK drag (I): drag a hand or foot', () => toggleIk(), ikOn),
    h('hr'),
    b('frame', 'Frame', 'frame', 'Frame Bunny (F)', frameBunny),
    b('grid', 'Grid', 'grid', 'Floor grid (G)', () => { view.grid.visible = !view.grid.visible; buildRail(); }, view.grid.visible),
    b('onion', 'Onion', 'onion', 'Onion skin (O)', () => { view3.onion = !view3.onion; apply(); buildRail(); }, view3.onion),
    );
}

// the format row above the canvas (as in the 2D app): frame size, lens, quick angles
const FORMATS = [['1080x1920', '9:16 Reel'], ['1080x1350', '4:5 Post'], ['1080x1080', '1:1 Square'], ['1920x1080', '16:9 YouTube'], ['3840x2160', '16:9 4K']];
function buildCanvasTop() {
  const fmt = h('select', { id: 'format-select', title: 'Frame size of the whole scene', 'aria-label': 'Format' }, ...FORMATS.map(([v, n]) => h('option', { value: v }, n)));
  const now = `${scene.width}x${scene.height}`;
  if (!FORMATS.some(f => f[0] === now)) fmt.append(h('option', { value: now }, `${scene.width}×${scene.height}`));
  fmt.value = now;
  fmt.addEventListener('change', () => { const [w, hh] = fmt.value.split('x').map(Number); pushUndo('Format'); scene.width = w; scene.height = hh; dirty = true; layout(); apply(); updateHud(); });
  const lens = h('select', { id: 'lens-select', title: 'Camera lens (Alt+wheel over the view)', 'aria-label': 'Lens' }, ...LENSES.map(l => h('option', { value: l }, l + ' mm')));
  const L = Math.round(current('cam.lens')); if (!LENSES.includes(L)) lens.append(h('option', { value: L }, L + ' mm')); lens.value = String(L);
  lens.addEventListener('change', () => camSet({ lens: Number(lens.value) }));
  const st = stage?.status() || { loading: 0, missing: 0 };
  // row 1: format, lens, Open in Blender (right); row 2: camera angles (wraps under in the narrow canvas dock)
  $('#canvas-top').replaceChildren(...[fmt, lens,
    h('span', { style: 'flex:1' }),
    mirrorButton(),
    angleSelect(),
    st.loading ? h('span', { class: 'of', title: 'Blender is turning the library pieces in this shot into 3D view models (once per piece)' }, `Making ${st.loading} 3D model${st.loading > 1 ? 's' : ''}…`) : null,
    stage?.selected ? h('button', { title: 'Clear the selection (Esc)', onclick: () => clearSelection() }, 'Deselect') : null].filter(Boolean));
}

function angleSelect() {
  const s = h('select', { title: 'Jump the camera to an angle', 'aria-label': 'Camera angle' }, h('option', { value: '' }, 'Angle…'), ...VIEWS.map(([n], i) => h('option', { value: i }, n)));
  s.addEventListener('change', () => { if (s.value !== '') camSet(VIEWS[Number(s.value)][1]); s.value = ''; });
  return s;
}
// Open in Blender: one button, its state in its label (Live / connecting), click again to stop
function mirrorButton() {
  const m = MR.state();
  if (!m.on) return h('button', { id: 'blender-live', title: 'Open this shot in a full Blender window. Moves, turns, poses, camera and frame changes on either side show up on the other (Ctrl+B).', onclick: () => openInBlender() }, icon('sync'), 'Open in Blender');
  return h('button', { id: 'blender-live', 'aria-pressed': 'true', class: m.connected ? 'live' : '', title: m.connected ? `Live with Blender ${m.blender || ''}. Click to stop the link (the Blender window stays open).` : 'Blender is opening the shot…', onclick: () => MR.close() },
    icon('sync'), m.connected ? '● Blender live' : 'Blender opening…');
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
  inkBar({ h, inkTarget, setInk, host: () => $('#frame') });
  const st = stageOf(scene, project), setName = st.set && (libraryRows().find(r => r.category === 'set' && (r.data?.room === st.set))?.name || st.set);
  $('#hud').replaceChildren(h('span', {}, charName() + (setName ? ' · ' + setName : '') + (st.outfit ? ' · ' + st.outfit : '') + (project.items?.length ? ` · ${project.items.length} item${project.items.length > 1 ? 's' : ''}` : '')),
    h('span', {}, `${Math.round(current('cam.lens'))} mm`), h('span', {}, tab === 'carousel' ? `Carousel ${SIZES[carouselOf(scene).size].join('×')}` : `${project.width}×${project.height}`),
    h('span', {}, `F${frame}`), ...(macroRec.on ? [h('span', { class: 'rule bad', title: 'Menu commands are being recorded' }, '● Recording macro')] : []), ...(fpsText() ? [h('span', {}, fpsText() + (parseInt(fpsText()) < 30 && heavy() ? ' · heavy: ' + heavy() : ''))] : []),
    ...(ruleLights && rules ? [
      h('span', { class: 'rule ' + (rules.clips.length ? 'bad' : 'ok'), title: rules.clips.length ? 'Inside the head: ' + rules.clips.join(', ') : 'Hands and arms clear of the head' }, rules.clips.length ? '✗ Arm in head' : '✓ No clip'),
      h('span', { class: 'rule ' + (rules.belowFloor || rules.inAir ? 'bad' : 'ok'), title: `Lowest foot ${Math.round(rules.feet * 100)} cm from the floor` }, rules.belowFloor ? '✗ Feet in floor' : rules.inAir ? '✗ In the air' : '✓ Grounded'),
      h('span', { class: 'rule ' + ((project.ink ?? 100) === 100 ? 'ok' : 'bad'), title: 'Line weight equals Bunny\'s everywhere' }, (project.ink ?? 100) === 100 ? '✓ Line weight' : `✗ Line ${project.ink}%`)] : []),
    ...(balanceOn && balanceNow ? [h('span', { class: 'rule ' + (balanceNow.balanced === false ? 'bad' : 'ok'), title: 'Centre of gravity over the feet' }, balanceNow.balanced == null ? 'Balance: off the floor' : balanceNow.balanced ? '✓ Balanced' : `✗ Off balance ${balanceNow.offCm} cm`)] : []),
    ...(editLayer >= 0 && project.layers?.[editLayer] ? [h('span', {}, 'Keying: ' + T().name)] : []), ...(ikOn ? [h('span', {}, 'IK drag')] : []),
    ...(snap.on ? [h('span', {}, 'Snap')] : []));
  $('#status').textContent = (filePath ? filePath.split(/[\\/]/).pop() : 'Not saved') + (dirty ? ' •' : '');
  const ss = stage?.status() || {}, sig = [scene.width, scene.height, Math.round(current("cam.lens")), ss.loading, !!stage?.selected].join("|");
  if (sig !== buildCanvasTop.sig) { buildCanvasTop.sig = sig; buildCanvasTop(); }
}

// ---------------------------------------------------------------- timeline (the 2D app's two rows of labelled groups)
let tlZoom = (() => { try { return Math.max(1, Number(localStorage.getItem('ds3d.tlzoom')) || 1); } catch { return 1; } })();
let rowsMode = (() => { try { return localStorage.getItem('ds3d.rows') || 'keyed'; } catch { return 'keyed'; } })();
let rowSel = new Set(), keyClip = null, lastCopy = null, lastZone = 'canvas';
const NAME_W = 200;
const hiddenRows = () => new Set(scene.hiddenTracks || []);
const folded = g => !!scene.folded?.[g];
function setZoom(z) { tlZoom = Math.max(1, Math.min(40, z)); try { localStorage.setItem('ds3d.tlzoom', String(tlZoom)); } catch {} const zs = $('#tl-zoom'); if (zs) zs.value = String(Math.log2(tlZoom)); drawTracks(); centreOn(frame); return tlZoom; }
function centreOn(f) { const box = $('#tracks'); if (!box) return; const x = NAME_W + f * pxPerFrame(); if (x < box.scrollLeft + NAME_W || x > box.scrollLeft + box.clientWidth - 30) box.scrollLeft = Math.max(0, x - NAME_W - (box.clientWidth - NAME_W) / 2); }
function fitKeys() {
  const sel = multi.length ? multi.map(m => m.k.f) : null;
  if (!sel) return setZoom(1);
  const a = Math.min(...sel), b = Math.max(...sel), box = $('#tracks');
  setZoom(Math.max(1, project.length / Math.max(8, b - a + 8)));
  box.scrollLeft = Math.max(0, a * pxPerFrame() - 20);
}
function stepKey(dir) {
  const fs = new Set();
  for (const id of visibleRowIds()) for (const k of T().tracks[id] || []) fs.add(k.f);
  const list = [...fs].sort((a, b) => a - b), f = dir < 0 ? list.filter(x => x < frame).pop() : list.find(x => x > frame);
  if (f == null) return toast(dir < 0 ? 'No earlier key' : 'No later key');
  goto(f); centreOn(f);
}
function rowIdsOf(group) {
  const TR = T().tracks, all = group === 'Bunny' ? BUNNY_IDS.concat(FACE_IDS) : CAM_IDS, hid = hiddenRows();
  let ids = filterIds(keyFilter, all);
  if (rowsMode === 'keyed') ids = ids.filter(id => TR[id]);
  else if (rowsMode === 'part' && group === 'Bunny') { const p = PARTS.find(x => x[0] === part)?.[2] || []; ids = ids.filter(id => p.includes(id) || TR[id]); }
  else if (rowsMode === 'part') ids = ids.filter(id => TR[id]);
  return ids.filter(id => !hid.has(id));
}
const visibleRowIds = () => ['Bunny', 'Camera'].flatMap(g => folded(g.toLowerCase()) ? [] : rowIdsOf(g));

function buildTimelineTools() {
  if (!project.layers?.[editLayer]) editLayer = -1;
  const g = (name, ...kids) => h('div', { class: 'ux-group' }, h('span', { class: 'ux-group-name' }, name), ...kids);
  const ib = (n, title, fn, id, on) => h('button', { class: 'icon' + (on ? ' on' : ''), title, 'aria-label': title, onclick: fn, id, 'aria-pressed': on == null ? null : String(!!on) }, icon(n));
  const box = h('input', { id: 'frame-box', type: 'number', min: 0, title: 'Current frame: type a number to jump there' });
  box.addEventListener('change', () => goto(Number(box.value)));
  const ease = h('select', { id: 'ease-select', title: 'Easing from the selected key(s) to the next one' }, ...Object.entries(EASES).map(([k, n]) => h('option', { value: k }, n)));
  ease.addEventListener('change', () => {
    const list = multi.length ? multi.map(m => m.k) : selected ? [T().tracks[selected.id]?.find(k => k.f === selected.f)].filter(Boolean) : [];
    if (!list.length) return toast('Select a key first');
    pushUndo(list.length > 1 ? `Ease on ${list.length} keys` : 'Ease'); for (const k of list) k.ease = ease.value; apply();
  });
  const zoom = h('input', { id: 'tl-zoom', class: 'zoom', type: 'range', min: 0, max: 5.3, step: 0.1, value: Math.log2(tlZoom), title: 'Timeline zoom (Ctrl+wheel over the timeline, = and - while the pointer is on it)', 'aria-label': 'Timeline zoom' });
  zoom.addEventListener('input', () => setZoom(2 ** Number(zoom.value)));
  const rows = h('select', { title: 'Which property rows the timeline shows', 'aria-label': 'Rows' }, h('option', { value: 'keyed' }, 'Keyed rows'), h('option', { value: 'part' }, 'Selected part'), h('option', { value: 'all' }, 'All rows'));
  rows.value = rowsMode;
  rows.addEventListener('change', () => { rowsMode = rows.value; try { localStorage.setItem('ds3d.rows', rowsMode); } catch {} drawTracks(); });
  const filter = h('select', { title: 'Show only these keys on the timeline', 'aria-label': 'Key filter' }, ...Object.entries(FILTERS).map(([k, n]) => h('option', { value: k }, n)));
  filter.value = keyFilter; filter.addEventListener('change', () => { keyFilter = filter.value; drawTracks(); });
  const layer = h('select', { title: 'Where new keys go: the base animation or a layer on top of it', 'aria-label': 'Keys go to' }, h('option', { value: -1 }, 'Base'), ...(project.layers || []).map((L, i) => h('option', { value: i }, L.name + (L.on === false ? ' (muted)' : ''))));
  layer.value = String(editLayer);
  layer.addEventListener('change', () => { editLayer = Number(layer.value); selected = null; multi = []; buildTimelineTools(); drawTracks(); apply(); });
  const chips = scene.shots.map((s, i) => h('button', { class: 'shot-chip status-' + statusOf(s), style: s.mood ? `box-shadow:inset 0 -4px 0 ${S2.moodColour(s.mood)}` : null, 'aria-pressed': String(i === scene.active), title: `${shotName(s)}: ${(s.length / scene.fps).toFixed(1)} s, ${STATUS.find(x => x[0] === statusOf(s))[1]}. Click to edit, double-click to name, right-click for the next status.`,
    onclick: () => selectShot(i), ondblclick: () => labelShot(i), oncontextmenu: e => { e.preventDefault(); shotStatus(nextStatus(s), i); } }, shotName(s), h('small', {}, ` ${(s.length / scene.fps).toFixed(1)}s`), h('i', { class: 'status-tag' }, STATUS.find(x => x[0] === statusOf(s))[1])));
  const L = editLayer >= 0 ? project.layers?.[editLayer] : null;
  const lw = L && (() => { const w = h('input', { type: 'number', min: 0, max: 200, step: 5, value: Math.round((L.weight ?? 1) * 100), style: 'width:56px', title: 'How strongly this layer adds on top, in percent', 'aria-label': 'Layer weight percent' }); w.addEventListener('change', () => { pushUndo('Layer weight'); L.weight = Math.max(0, Math.min(2, Number(w.value) / 100)); dirty = true; apply(); }); return w; })();
  $('#timeline-tools').replaceChildren(
    h('div', { class: 'tl-row' },
      g('Play', ib('start', 'First frame (Home)', () => goto(0)), ib('prevkey', 'Previous key (↑ or ;)', () => stepKey(-1)), ib('prev', 'Previous frame (← or ,)', () => goto(frame - 1)), ib('play', 'Play / pause (Space)', togglePlay, 'play-btn'),
        ib('next', 'Next frame (→ or .)', () => goto(frame + 1)), ib('nextkey', 'Next key (↓ or \')', () => stepKey(1)), ib('end', 'Last frame (End)', () => goto(project.length - 1)),
        ib('loop', 'Loop playback (L)', () => { loopPlay = !loopPlay; buildTimelineTools(); toast(loopPlay ? 'Playback loops' : 'Playback stops at the end'); }, 'loop-btn', loopPlay)),
      g('Frame', box, h('span', { class: 'of', id: 'clock' })),
      g('Edit', ib('key', 'Key the whole pose and face (K). Shift+K keys the camera.', () => keyGroup(BUNNY_IDS.concat(FACE_IDS))), ease,
        ib('cut', 'Scissors: click a block to cut it in two', () => { cutMode = !cutMode; $('#tracks').classList.toggle('cutting', cutMode); buildTimelineTools(); }, 'scissors-btn', cutMode),
        h('button', { id: 'curves-btn', 'aria-pressed': String(curves), onclick: () => toggleCurves(), title: 'Graph editor: the curves of this part\'s keys, with a spacing chart for the selected key' }, 'Curves'),
        h('button', { 'aria-pressed': String(!!project.stepped), onclick: toggleStepped, title: 'Stepped blocking: every key holds until the next one, in the viewport and the render. Turn it off for smooth in-betweens.' }, 'Stepped')),
      g('Zoom', zoom, ib('fit', 'Fit the whole shot (\\). Shift-click: fit the selected keys', e => (e.shiftKey ? fitKeys() : setZoom(1)))),
      g('Rows', rows, filter),
      g('Shots', ...chips, h('button', { onclick: () => addShot(false), title: 'Add a shot after this one (Ctrl+T)' }, '+ Shot')),
      g('Keys go to', layer, h('button', { onclick: () => newLayer(), title: 'Add an animation layer: its keys add on top of the base, so you can push a whole move without touching its keys' }, '+ Layer'),
        ...(L ? [h('button', { 'aria-pressed': String(L.on === false), onclick: () => { pushUndo('Mute layer'); L.on = L.on === false; dirty = true; buildTimelineTools(); apply(); }, title: 'Mute this layer to compare with the base' }, 'Mute'), lw, h('span', {}, '%')] : []))));
}

function toggleCurves(on = !curves) { curves = on; buildTimelineTools(); drawTracks(); return { curves }; }
const pxPerFrame = () => Math.max(3, (($('#tracks')?.clientWidth || 900) - NAME_W - 14) / Math.max(1, project.length)) * tlZoom;

function drawTracks() {
  const box = $('#tracks');
  if (!box) return;
  const ppf = pxPerFrame(), W = Math.ceil(project.length * ppf) + 24;
  const lane = (kids = []) => h('div', { class: 'lane' }, ...kids);
  const ruler = lane();
  const step = project.fps * (ppf * project.fps < 50 ? 2 : 1), fine = ppf * project.fps > 260 ? Math.max(1, Math.round(project.fps / Math.floor(ppf * project.fps / 50))) : 0;
  for (let f = 0; f <= project.length; f += step) ruler.append(h('div', { class: 'tick', style: `left:${f * ppf}px` }, `${f / project.fps}s`));
  if (fine) for (let f = 0; f <= project.length; f += fine) if (f % project.fps) ruler.append(h('div', { class: 'tick', style: `left:${f * ppf}px;opacity:.3;font-size:9px` }, String(f)));
  ruler.addEventListener('pointerdown', e => {
    const r = ruler.getBoundingClientRect(), w = DOCK.winOf(ruler);
    const go = ev => goto(Math.round((ev.clientX - r.left) / ppf));
    go(e);
    const mv = ev => go(ev), up = () => { w.removeEventListener('pointermove', mv); w.removeEventListener('pointerup', up); };
    w.addEventListener('pointermove', mv); w.addEventListener('pointerup', up);
  });
  ruler.append(...markerEls(polCtx(), ppf));
  const rows = [h('div', { class: 'ruler' }, h('div', { class: 'tname' }, 'TIME'), ruler)];
  const wave = audioInfo() && waveform(scene.fps, sceneStart(), project.length, ppf);
  if (wave) rows.push(h('div', { class: 'trow' }, h('div', { class: 'tname', title: audioInfo().path }, 'Voice'), lane([wave])));
  rows.push(...layerRows(ppf));
  const ret = S2.retentionLane(h, scene, sceneStart(), project.length, ppf);
  if (ret) rows.push(h('div', { class: 'trow' }, h('div', { class: 'tname', title: 'Audience retention from YouTube Studio (story2 MCP tool, action retention). Mustard bars are the biggest drops.' }, 'Retention'), lane([ret])));
  // what is placed in the shot: drag a piece along to change when it appears
  if (project.items?.length) {
    const sel = stage?.selected?.type === 'item' ? stage.selected.index : -1;
    // pieces that start close together stack on their own rows, so every one can be seen and dragged
    const ends = [], marks = project.items.map((it, i) => {
      const name = libRowMap().get(it.id)?.name || it.id.split(':')[1] || it.id, x = it.frame * ppf + 2, w = Math.min(140, name.length * 6.4 + 16);
      let r = ends.findIndex(e => e <= x); if (r < 0) { r = ends.length; ends.push(0); } ends[r] = x + w + 3;
      const el = itemMark(it, i, ppf, i === sel); el.style.top = (2 + r * 19) + 'px'; return el;
    });
    rows.push(h('div', { class: 'trow', style: `height:${Math.max(22, 4 + ends.length * 19)}px` }, h('div', { class: 'tname', title: 'Props, effects and storytime pieces in this shot. Drag one along to change when it appears; click to select it in the 3D view.' }, 'Items'),
      lane(marks)));
  }
  if (curves) {
    const live = id => project.tracks[id]?.length && !DISCRETE.has(id);
    let ids = (PARTS.find(p => p[0] === part)?.[2] || []).filter(live), what = PARTS.find(p => p[0] === part)?.[1];
    if (!ids.length) { ids = filterIds(keyFilter, BUNNY_IDS).filter(live); what = 'all keyed'; }
    const wrap = h('div', { class: 'graph-wrap' });
    rows.push(h('div', { class: 'trow graph-row' }, h('div', { class: 'tname group', title: 'Pick a part on the Pose tab (or click it in the viewport) to see its curves' }, 'Curves · ' + (ids.length ? what : 'no keys')), wrap));
    box.replaceChildren(...rows, h('div', { id: 'playhead' }));
    const gctx = { ...anim2Ctx(), changed: () => { dirty = true; apply(); } };
    wrap.append(A2.graphEditor(gctx, wrap, ids, graphSel).canvas);
    drawPlayhead();
    return;
  }
  const TR = T().tracks;
  for (const [gname, all] of [['Bunny', BUNNY_IDS.concat(FACE_IDS)], ['Camera', CAM_IDS]]) {
    const key = gname.toLowerCase(), fold = folded(key), ids = rowIdsOf(gname);
    const label = gname === 'Bunny' ? charName() : gname;
    const gn = h('div', { class: 'tname group', title: `Double-click to ${fold ? 'show' : 'fold'} ${label}'s rows` }, h('span', { class: 'fold', 'aria-hidden': 'true' }, fold ? '▸' : '▾'), h('span', { class: 'tn' }, label + (gname === 'Bunny' && T() !== project ? ' · ' + T().name : '')));
    gn.addEventListener('dblclick', () => toggleFold(key));
    gn.querySelector('.fold').addEventListener('click', e => { e.stopPropagation(); toggleFold(key); });
    rows.push(h('div', { class: 'trow' }, gn, lane(summaryKeys(filterIds(keyFilter, all).filter(id => TR[id]), ppf))));
    const idle = gname === 'Bunny' && idleNow();
    if (idle && !fold) rows.push(h('div', { class: 'trow' }, h('div', { class: 'tname', title: 'Auto blinks (top) and twitches (bottom). Click one to go there; settings are on Face › Idle life.' }, 'Idle life'),
      lane(idle.events.map(e => h('div', { class: 'idle-mark ' + e.kind, style: `left:${e.f * ppf + 2}px`, title: `${e.kind === 'blink' ? 'Blink' + (e.why === 'turn' ? ' on a head turn' : e.why === 'double' ? ' (double)' : '') : 'Twitch ' + (e.sides === 'LR' ? 'both' : e.sides === 'L' ? 'left' : 'right')} at frame ${e.f}`, onclick: () => goto(e.f) })))));
    if (fold) continue;
    for (const id of ids) {
      const full = rowLabel(id);
      const rm = h('button', { class: 'rm', title: 'Remove this row from the timeline (its keys stay and still animate)', 'aria-label': 'Remove row ' + full, onclick: e => { e.stopPropagation(); removeRows(rowSel.has(id) ? [...rowSel] : [id]); } }, '×');
      const nameEl = h('div', { class: 'tname', title: full + '. Click to select the row (Ctrl/Shift for more), right-click for row actions.' }, h('span', { class: 'tn' }, full), rm);
      nameEl.addEventListener('click', e => {
        if (e.ctrlKey || e.metaKey || e.shiftKey) { rowSel.has(id) ? rowSel.delete(id) : rowSel.add(id); }
        else { rowSel = new Set([id]); const p = PARTS.find(x => x[2].includes(id)); if (p && p[0] !== part && tab === 'pose') { part = p[0]; buildTabs(); buildPanel(); } }
        drawTracks();
      });
      nameEl.addEventListener('contextmenu', e => { e.preventDefault(); if (!rowSel.has(id)) rowSel = new Set([id]); drawTracks(); rowMenu(e); });
      rows.push(h('div', { class: 'trow' + (rowSel.has(id) ? ' rsel' : ''), 'data-id': id }, nameEl, lane((TR[id] || []).map(k => keyEl(id, k, ppf)))));
    }
  }
  const hid = (scene.hiddenTracks || []).length;
  if (hid) {
    const r = h('div', { class: 'tname', title: 'Rows you removed from the timeline. Their keys still animate. Click to bring them back.' }, `+ ${hid} removed`);
    r.addEventListener('click', e => restoreMenu(e));
    rows.push(h('div', { class: 'trow restore' }, r, lane()));
  }
  const ph = h('div', { id: 'playhead' });
  const inner = h('div', { class: 'lanes-x', style: `width:${NAME_W + W}px;min-width:100%` }, ...rows, ph);
  const sx = box.scrollLeft;
  box.replaceChildren(inner);
  box.scrollLeft = sx;
  for (const r of inner.querySelectorAll('.trow:not(.graph-row) .lane')) r.addEventListener('pointerdown', laneDown);
  drawPlayhead();
}
function rowLabel(id) { const nm = PARTS.find(p => p[2].includes(id) && p[0] !== 'whole')?.[1]; return (nm ? nm + ' · ' : '') + (LABEL[id] || id); }
function toggleFold(key) { scene.folded = { ...(scene.folded || {}), [key]: !folded(key) }; if (!scene.folded[key]) delete scene.folded[key]; dirty = true; drawTracks(); }
function removeRows(ids) {
  if (!ids.length) return;
  pushUndo(ids.length > 1 ? `Remove ${ids.length} rows` : 'Remove row');
  scene.hiddenTracks = [...new Set([...(scene.hiddenTracks || []), ...ids])];
  for (const id of ids) rowSel.delete(id);
  multi = multi.filter(m => !ids.includes(m.id));
  dirty = true; drawTracks();
  toast(`Removed ${ids.length > 1 ? ids.length + ' rows' : LABEL[ids[0]] || ids[0]} from the timeline. The keys still animate; "+ removed" brings ${ids.length > 1 ? 'them' : 'it'} back.`, 4000);
}
function restoreRows(ids) {
  pushUndo('Bring back rows');
  const back = new Set(ids);
  scene.hiddenTracks = (scene.hiddenTracks || []).filter(id => !back.has(id));
  if (!scene.hiddenTracks.length) delete scene.hiddenTracks;
  dirty = true; drawTracks();
  toast('Back on the timeline: ' + ids.map(id => LABEL[id] || id).join(', '));
}
function ctxMenu(e, items) {
  const d = e.target.ownerDocument;
  d.querySelectorAll('.ctx-menu').forEach(m => m.remove());
  const m = h('div', { class: 'ctx-menu', role: 'menu' });
  for (const it of items) if (it === '-') m.append(h('hr')); else m.append(h('button', { role: 'menuitem', onclick: () => { m.remove(); it[1](); } }, it[0]));
  d.body.append(d.adoptNode(m));
  const w = d.defaultView;
  m.style.left = Math.min(e.clientX, w.innerWidth - m.offsetWidth - 4) + 'px';
  m.style.top = Math.min(e.clientY, w.innerHeight - m.offsetHeight - 4) + 'px';
  const off = ev => { if (!m.contains(ev.target)) { m.remove(); w.removeEventListener('pointerdown', off, true); } };
  setTimeout(() => w.addEventListener('pointerdown', off, true));
}
function rowMenu(e) {
  const ids = [...rowSel], n = ids.length, TR = T().tracks;
  ctxMenu(e, [
    [`Select the keys on ${n > 1 ? 'these ' + n + ' rows' : 'this row'}`, () => { multi = ids.flatMap(id => (TR[id] || []).map(k => ({ id, k }))); selected = multi[0] ? { id: multi[0].id, f: multi[0].k.f } : null; drawTracks(); }],
    ['Copy their keys', () => { multi = ids.flatMap(id => (TR[id] || []).map(k => ({ id, k }))); copySelectedKeys(); drawTracks(); }],
    [`Clear the keys on ${n > 1 ? 'these rows' : 'this row'}`, () => { pushUndo('Clear row keys'); for (const id of ids) delete TR[id]; multi = []; selected = null; apply(); drawTracks(); toast(`Cleared ${n > 1 ? n + ' rows' : LABEL[ids[0]] || ids[0]}`); }],
    '-',
    [`Remove ${n > 1 ? 'these rows' : 'this row'} from the timeline`, () => removeRows(ids)],
    ...((scene.hiddenTracks || []).length ? [['Bring back removed rows…', () => restoreMenu(e)]] : []),
  ]);
}
function restoreMenu(e) {
  const hid = scene.hiddenTracks || [];
  if (!hid.length) return toast('No rows are removed');
  ctxMenu(e, [['Bring back all', () => restoreRows(hid)], '-', ...hid.map(id => ['Bring back ' + rowLabel(id), () => restoreRows([id])])]);
}
function itemMark(it, i, ppf, sel) {
  const row = libRowMap().get(it.id);
  const el = h('div', { class: 'item-mark' + (sel ? ' sel' : ''), style: `left:${it.frame * ppf + 2}px`, title: `${row?.name || it.id} at frame ${it.frame}. Drag to retime, click to select.` }, (row ? '' : glyphOf(it.id) + ' ') + (row?.name || it.id.split(':')[1]));
  el.addEventListener('pointerdown', e => {
    e.stopPropagation();
    const w = DOCK.winOf(el), x0 = e.clientX, f0 = it.frame;
    let moved = false;
    const mv = ev => { const f = Math.max(0, Math.min(project.length - 1, f0 + Math.round((ev.clientX - x0) / ppf))); if (f !== it.frame) { if (!moved) pushUndo('Retime item'); moved = true; it.frame = f; el.style.left = `${f * ppf + 2}px`; } };
    const up = () => { w.removeEventListener('pointermove', mv); w.removeEventListener('pointerup', up); if (moved) { project.items.sort((a, b) => a.frame - b.frame); dirty = true; apply(); drawTracks(); } else { selectItem(i); if (tab !== 'stage' || sub.stage !== 'items') setTab('stage', 'items'); } };
    w.addEventListener('pointermove', mv); w.addEventListener('pointerup', up);
  });
  return el;
}
// blank lane: click seeks, drag draws a box that selects keys (Shift adds, Ctrl toggles)
function laneDown(e) {
  if (e.button !== 0 || e.target.closest('.key,.item-mark,.idle-mark,.marker')) return;
  const box = $('#tracks'), inner = box.querySelector('.lanes-x'), w = DOCK.winOf(box), ppf = pxPerFrame();
  const r0 = inner.getBoundingClientRect(), x0 = e.clientX - r0.left, y0 = e.clientY - r0.top;
  let rect = null;
  const add = e.shiftKey, toggle = e.ctrlKey || e.metaKey, before = multi.slice();
  const mv = ev => {
    const r = inner.getBoundingClientRect(), x1 = ev.clientX - r.left, y1 = ev.clientY - r.top;
    if (!rect && Math.hypot(x1 - x0, y1 - y0) < 5) return;
    if (!rect) { rect = h('div', { class: 'box-sel' }); inner.append(rect); box.classList.add('boxing'); }
    const L = Math.min(x0, x1), T0 = Math.min(y0, y1), Wd = Math.abs(x1 - x0), Ht = Math.abs(y1 - y0);
    Object.assign(rect.style, { left: L + 'px', top: T0 + 'px', width: Wd + 'px', height: Ht + 'px' });
    const fa = Math.floor((L - NAME_W) / ppf), fb = Math.ceil((L + Wd - NAME_W) / ppf), hit = [];
    for (const row of inner.querySelectorAll('.trow[data-id]')) {
      const rr = row.getBoundingClientRect(), top = rr.top - r.top;
      if (top + rr.height < T0 || top > T0 + Ht) continue;
      for (const k of T().tracks[row.dataset.id] || []) if (k.f >= fa && k.f <= fb) hit.push({ id: row.dataset.id, k });
    }
    if (toggle) { const s = new Set(before.map(m => m.k)); multi = [...before.filter(m => !hit.some(x => x.k === m.k)), ...hit.filter(x => !s.has(x.k))]; }
    else multi = add ? [...before, ...hit.filter(x => !before.some(m => m.k === x.k))] : hit;
    for (const el of inner.querySelectorAll('.trow[data-id] .key')) el.classList.toggle('sel', multi.some(m => m.k === el._k));
  };
  const up = ev => {
    w.removeEventListener('pointermove', mv); w.removeEventListener('pointerup', up);
    box.classList.remove('boxing');
    if (!rect) { if (!add && !toggle) { multi = []; selected = null; rowSel.clear(); } goto(Math.round((ev.clientX - inner.getBoundingClientRect().left - NAME_W) / ppf)); drawTracks(); return; }
    rect.remove();
    selected = multi[0] ? { id: multi[0].id, f: multi[0].k.f } : null;
    if (multi.length) toast(`${multi.length} key${multi.length > 1 ? 's' : ''} selected: drag one to move them all, Delete removes, Ctrl+C copies`);
    drawTracks();
  };
  w.addEventListener('pointermove', mv); w.addEventListener('pointerup', up);
}
function selectAllKeys() {
  const TR = T().tracks;
  multi = visibleRowIds().flatMap(id => (TR[id] || []).map(k => ({ id, k })));
  selected = multi[0] ? { id: multi[0].id, f: multi[0].k.f } : null;
  drawTracks();
  toast(`${multi.length} keys selected`);
  return multi.length;
}
function copySelectedKeys() {
  const list = multi.length ? multi : selected ? [{ id: selected.id, k: T().tracks[selected.id]?.find(k => k.f === selected.f) }].filter(m => m.k) : [];
  if (!list.length) return toast('Select keys to copy: click one, or drag a box across the timeline');
  const f0 = Math.min(...list.map(m => m.k.f));
  keyClip = list.map(m => ({ id: m.id, df: m.k.f - f0, v: m.k.v, ease: m.k.ease }));
  lastCopy = 'keys';
  toast(`Copied ${keyClip.length} key${keyClip.length > 1 ? 's' : ''}. Ctrl+V pastes them at the playhead, in this or another shot.`);
  return keyClip.length;
}
function pasteSelectedKeys(at = frame) {
  if (!keyClip?.length) return toast('Copy keys first (select them, then Ctrl+C)');
  pushUndo(`Paste ${keyClip.length} keys`);
  const known = new Set(BUNNY_IDS.concat(FACE_IDS, CAM_IDS)), tr = T().tracks;
  let n = 0;
  multi = [];
  for (const c of keyClip) {
    if (!known.has(c.id)) continue;
    const f = at + c.df;
    if (f >= project.length) continue;
    setKey(DISCRETE.has(c.id) ? project : T(), c.id, f, c.v, c.ease);
    const k = (DISCRETE.has(c.id) ? project : T()).tracks[c.id]?.find(x => x.f === f);
    if (k) multi.push({ id: c.id, k });
    n++;
  }
  dirty = true; apply(); drawTracks();
  toast(`Pasted ${n} keys at frame ${at}`);
  return n;
}

function summaryKeys(ids, ppf) {
  const fs = new Set();
  for (const id of ids) for (const k of T().tracks[id]) fs.add(k.f);
  return [...fs].map(f => h('div', { class: 'key', style: `left:${f * ppf + 2}px;opacity:.55`, title: `Frame ${f}. Click to go there; Shift+click selects every key on this frame.`, onclick: e => { goto(f); if (e.shiftKey) { multi = ids.flatMap(id => T().tracks[id].filter(k => k.f === f).map(k => ({ id, k }))); drawTracks(); } } }));
}

function keyEl(id, k, ppf) {
  const inMulti = multi.some(m => m.k === k);
  const el = h('div', { class: 'key' + ((selected && selected.id === id && selected.f === k.f) || inMulti ? ' sel' : ''), style: `left:${k.f * ppf + 2}px`, title: `${LABEL[id] || id}: ${round(k.v)} at frame ${k.f} (${EASES[k.ease || 'ease']}). Drag to move; Shift or Ctrl+click to select several and move them together.` });
  el._k = k;
  el.addEventListener('pointerdown', e => {
    e.stopPropagation();
    const tr = T().tracks, w = DOCK.winOf(el);
    if (e.shiftKey || e.ctrlKey || e.metaKey) {
      const i = multi.findIndex(m => m.k === k);
      if (i >= 0) multi.splice(i, 1);
      else {
        const sk = selected && tr[selected.id]?.find(x => x.f === selected.f);
        if (!multi.length && sk && sk !== k) multi.push({ id: selected.id, k: sk });
        multi.push({ id, k });
      }
      selected = { id, f: k.f };
      drawTracks();
      return;
    }
    if (!inMulti) multi = [];
    selected = { id, f: k.f };
    const es = $('#ease-select'); if (es) es.value = k.ease || 'ease';
    const group = (multi.length ? multi : [{ id, k }]).map(m => ({ ...m, f0: m.k.f }));
    const x0 = e.clientX, lo = -Math.min(...group.map(g => g.f0)), hi = project.length - 1 - Math.max(...group.map(g => g.f0));
    let moved = false;
    pushUndo(group.length > 1 ? `Move ${group.length} keys` : 'Move key');
    const mv = ev => {
      const d = Math.max(lo, Math.min(hi, Math.round((ev.clientX - x0) / ppf)));
      if (group.length === 1) {
        const nf = group[0].f0 + d;
        if (nf !== k.f && !tr[id].some(o => o !== k && o.f === nf)) { k.f = nf; tr[id].sort((a, b) => a.f - b.f); selected.f = nf; moved = true; el.style.left = `${nf * ppf + 2}px`; }
      } else if (group.some(g => g.k.f !== g.f0 + d)) { for (const g of group) g.k.f = g.f0 + d; moved = true; selected.f = k.f; scheduleTracks(); }
    };
    const up = () => { w.removeEventListener('pointermove', mv); w.removeEventListener('pointerup', up); if (group.length > 1) settleKeys(group); if (!moved) undoStack.pop(); goto(k.f); drawTracks(); };
    w.addEventListener('pointermove', mv); w.addEventListener('pointerup', up);
  });
  return el;
}

function drawPlayhead() {
  const ph = $('#playhead');
  if (ph) ph.style.left = `${NAME_W + frame * pxPerFrame() + 2}px`;
  const box = $('#frame-box');
  if (box && box.ownerDocument.activeElement !== box) box.value = frame;
  const clk = $('#clock');
  if (clk) clk.textContent = `of ${project.length} · ${(frame / project.fps).toFixed(2)} s`;
  if (playing) centreOn(frame);
}

function goto(f) {
  frame = Math.max(0, Math.min(project.length - 1, Math.round(f)));
  for (const k of Object.keys(preview)) delete preview[k];
  apply();
}

function keyGroup(ids) {
  pushUndo();
  const vals = ids.map(id => [id, current(id)]);
  for (const [id, v] of vals) if (T() === project || !DISCRETE.has(id)) keyAt(id, v);
  for (const id of ids) delete preview[id];
  apply(); drawTracks();
  toast(`Keyed ${ids.length} values at frame ${frame}`);
}

function deleteSelected() {
  if (!selected && !multi.length) return toast('Select a key first');
  pushUndo(multi.length > 1 ? `Delete ${multi.length} keys` : 'Delete key');
  if (multi.length > 1) { const tr = T().tracks; for (const m of multi) { const i = tr[m.id]?.indexOf(m.k); if (i >= 0) tr[m.id].splice(i, 1); if (tr[m.id] && !tr[m.id].length) delete tr[m.id]; } multi = []; }
  else deleteKey(T(), selected.id, selected.f);
  selected = null; apply(); drawTracks();
}
function clearAll() {
  const n = Object.values(project.tracks).reduce((a, t) => a + t.length, 0) + (project.layers || []).reduce((a, L) => a + Object.values(L.tracks || {}).reduce((b, t) => b + t.length, 0), 0);
  if (!n) return toast('This shot has no keys');
  if (!confirm(`Clear all ${n} keys in ${project.code}? Ctrl+Z brings them back.`)) return;
  pushUndo('Clear all keys'); project.tracks = {}; for (const L of project.layers || []) L.tracks = {}; multi = []; selected = null; apply(); drawTracks();
  toast(`Cleared ${n} keys`);
}

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
const bridge = s => toBridgeShot(s, ALL_IDS(), data.face.faces, character(), stageOf(scene, s), materialsOf(scene, s));
const idleNow = () => idleFor(project, data.face.faces, character());
// a 360 shot renders equirectangular (2:1), so the joined video takes its size
const frameSize = shots => { const w = shots.map(s => s.powers?.pano360).find(Boolean); return w ? { width: w, height: w / 2, pano360: true } : { width: scene.width, height: scene.height }; };
async function render(still = false, preview = false, stillFrame = null, previz = false) {
  if (!still && !preview && !(await diskOk(polCtx()))) return null;
  scene.name = $('#shot-name').value || scene.name;
  try {
    const post = still ? null : await buildPost([scene.active], false);
    const r = await api('render', { name: scene.name, code: project.code, still: still ? (stillFrame ?? frame) + 1 : null, preview, audio: project.audio?.path || null, shot: previz ? { ...bridge(project), previz: true } : bridge(project), fps: scene.fps, ...frameSize([project]), post });
    toast(r.message || 'Render started');
    pollRender();
    return r;
  } catch (e) { toast('Render failed to start: ' + e.message, 5000); throw e; }
}
async function renderScene(preview = false, checked = false, previz = false) {
  if (!preview && !checked) return runPreflight(true);
  if (!preview && !(await diskOk(polCtx(), 10))) return null;
  scene.name = $('#shot-name').value || scene.name;
  try {
    const shots = scene.shots.map(s => ({ code: s.code, audio: s.audio?.path || null, shot: previz ? { ...bridge(bindShot(scene, s)), previz: true } : bridge(bindShot(scene, s)) }));
    const post = await buildPost(scene.shots.map((_, i) => i), true);
    const r = await api('render-scene', { name: scene.name, fps: scene.fps, ...frameSize(scene.shots), audio: scene.audio?.path || null, preview, shots, post });
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

// Help › Guide: the full guide (app/guide.md), with a search box that jumps to matching sections
async function guideDialog() {
  const md = await fetch('guide.md').then(r => r.text()).catch(() => 'The guide could not be loaded.');
  const esc = t => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = t => esc(t).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  const html = [];
  let list = false;
  for (const l of md.split('\n')) {
    const m = l.match(/^(#{1,4}) (.*)/);
    if (!/^\s*[-*] /.test(l) && list) { html.push('</ul>'); list = false; }
    if (m) html.push(`<h${Math.min(4, m[1].length + 1)}>${inline(m[2])}</h${Math.min(4, m[1].length + 1)}>`);
    else if (/^\s*[-*] /.test(l)) { if (!list) { html.push('<ul>'); list = true; } html.push(`<li>${inline(l.replace(/^\s*[-*] /, ''))}</li>`); }
    else if (/^\|/.test(l)) { if (!/^\|\s*-/.test(l)) html.push(`<p class="hint">${inline(l.replace(/^\||\|$/g, '').split('|').map(c => c.trim()).join(' · '))}</p>`); }
    else if (l.trim() === '---') html.push('<hr>');
    else if (l.trim()) html.push(`<p>${inline(l)}</p>`);
  }
  if (list) html.push('</ul>');
  const body = h('div', { class: 'guide-body', style: 'max-height:70vh;overflow:auto;max-width:760px' });
  body.innerHTML = html.join('');
  const find = h('input', { type: 'search', placeholder: 'Find in the guide', style: 'width:100%;margin-bottom:8px' });
  find.addEventListener('input', () => {
    const q = find.value.trim().toLowerCase();
    if (!q) return;
    const hit = [...body.children].find(el => el.textContent.toLowerCase().includes(q));
    if (hit) hit.scrollIntoView({ block: 'start' });
  });
  const d = h('dialog', { style: 'max-width:820px' }, h('h2', {}, 'Guide'), find, body, h('div', { class: 'row', style: 'margin-top:8px' }, h('button', { onclick: () => d.close() }, 'Close')));
  d.addEventListener('close', () => d.remove());
  document.body.append(d); d.showModal();
  return { open: true };
}

function showHelp() {
  const d = h('dialog', {}, h('h2', {}, 'Controls'), h('p', { class: 'hint' },
    'Viewport: drag to orbit, Shift+drag to move the aim, wheel to dolly, Alt+wheel for the lens. Space plays. ← → step frames. K keys the pose, Shift+K keys the camera. Delete removes the selected key. Ctrl+Z / Ctrl+Shift+Z undo and redo. Ctrl+S saves. Ctrl+D switches dark mode.'),
    h('p', { class: 'hint' }, 'Idle life (Face tab): Auto blink and Auto ear twitch keep him alive through the whole shot at natural, random moments. Same seed, same render. Keyed blinks and ear moves always win.'),
    h('button', { onclick: () => d.close() }, 'Close'));
  document.body.append(d); d.showModal();
}

function zoneOf(t) { return t?.closest?.('#dock-timeline,#timeline') ? 'timeline' : t?.closest?.('#dock-tools,#panel') ? 'tools' : 'canvas'; }
function pointerdownIn(e) { lastZone = zoneOf(e.target); }
function bindTimelineWheel() {
  const tr = $('#tracks');
  if (!tr || tr.dataset.wheel) return;
  tr.dataset.wheel = '1';
  tr.addEventListener('wheel', e => { if (!(e.ctrlKey || e.metaKey)) return; e.preventDefault(); setZoom(tlZoom * Math.exp(-e.deltaY * 0.002)); }, { passive: false });
}
function onKey(e) { return keyHandler(e); }
function bindKeys() {
  addEventListener('pointerdown', pointerdownIn, true);
  addEventListener('keydown', onKey);
}
function keyHandler(e) {
  {
    if (e.target?.matches?.('input,select,textarea')) return;
    const k = e.key, c = e.ctrlKey || e.metaKey;
    // your own shortcuts win (Help › Keyboard shortcuts)
    const mine = myKeys.get()[comboOf(e)];
    if (mine) { const cmd = polCtx().commands().find(x => cmdId(x) === mine); if (cmd) { e.preventDefault(); runCommand(cmd); return; } }
    const lk = k.toLowerCase(), inTl = lastZone === 'timeline';
    // the 2D app's keys: Ctrl+Shift+H hides the side panel, Ctrl+A / C / V on timeline keys, ; ' and ↑ ↓ step keys, , . step frames, \ fits
    if (c && e.shiftKey && lk === 'h') { e.preventDefault(); DOCK.toggleHidden('tools') ? toast('Tools panel hidden: Ctrl+Shift+H brings it back') : toast('Tools panel shown'); return; }
    if (c && !e.shiftKey && lk === 'b') { e.preventDefault(); MR.state().on ? toast('Blender is already live: Blender › Stop the live Blender link ends it') : openInBlender(); return; }
    if (c && !e.shiftKey && lk === 'a') { e.preventDefault(); selectAllKeys(); return; }
    if (c && !e.shiftKey && lk === 'c' && (multi.length || (inTl && selected))) { e.preventDefault(); copySelectedKeys(); return; }
    if (c && !e.shiftKey && lk === 'v' && lastCopy === 'keys' && keyClip?.length) { e.preventDefault(); pasteSelectedKeys(); return; }
    if (!c && !e.altKey && (k === ';' || k === 'ArrowUp')) { e.preventDefault(); stepKey(-1); return; }
    if (!c && !e.altKey && (k === "'" || k === 'ArrowDown')) { e.preventDefault(); stepKey(1); return; }
    if (!c && k === ',') { goto(frame - 1); return; }
    if (!c && k === '.') { goto(frame + 1); return; }
    if (!c && k === '\\') { setZoom(1); return; }
    if (c && (k === '=' || k === '+' || k === '-') && inTl) { e.preventDefault(); setZoom(tlZoom * (k === '-' ? 1 / 1.5 : 1.5)); return; }
    if (!c && !e.shiftKey && !e.altKey && /^[1-9]$/.test(k) && TABS[Number(k) - 1]) { setTab(TABS[Number(k) - 1][0]); return; }
    if (!c && !e.shiftKey && !e.altKey && ['q', 'w', 'e', 'r'].includes(lk)) { setTool({ q: 'select', w: 'move', e: 'rotate', r: 'scale' }[lk]); return; }
    if (k === 'Escape') { if (multi.length || selected) { multi = []; selected = null; drawTracks(); } clearSelection(); return; }
    if ((k === 'Delete' || k === 'Backspace') && !multi.length && !selected && stage?.selected?.type === 'item') { const i = stage.selected.index; stage.select(null); removeItem(libCtx(), i); apply(); drawTracks(); buildPanel(); toast('Item removed (Ctrl+Z brings it back)'); return; }
    // Keydial keys, same as Doodle Studio: Shift+arrows 10 frames, [ ] dial steps, = - dolly, L loop
    if (e.shiftKey && !c && (k === 'ArrowLeft' || k === 'ArrowRight')) { e.preventDefault(); goto(frame + (k === 'ArrowLeft' ? -10 : 10)); return; }
    if (k === '[' || k === ']') { goto(frame + (k === '[' ? -1 : 1)); return; }
    if (!c && (k === '=' || k === '+' || k === '-') && inTl) { setZoom(tlZoom * (k === '-' ? 1 / 1.5 : 1.5)); return; }
    if (!c && (k === '=' || k === '+' || k === '-')) { pushUndo('Dolly'); setValue('cam.dist', current('cam.dist') * (k === '-' ? 1.1 : 1 / 1.1)); drawTracks(); return; }
    if (!c && k.toLowerCase() === 'l') { loopPlay = !loopPlay; toast(loopPlay ? 'Playback loops' : 'Playback stops at the end'); return; }
    if (!c && k.toLowerCase() === 'n') { reviewNote(); return; }
    if (!c && k.toLowerCase() === 'b') { tapBeat(); return; }
    if (c && e.shiftKey && k.toLowerCase() === 'c') { e.preventDefault(); copyKeysNow(); return; }
    if (c && e.shiftKey && k.toLowerCase() === 'v') { e.preventDefault(); try { pasteKeysNow(); } catch (er) { toast(er.message); } return; }
    if (!c && !e.shiftKey && k.toLowerCase() === 'i') { toggleIk(); return; }
    if (c && k.toLowerCase() === 'c' && !e.shiftKey) { poseBuf.copy = poseNow(); lastCopy = 'pose'; toast('Pose copied (select keys first to copy keys instead)'); return; }
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
  }
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
  stage = new ST.Stage(view, stageCtx());
  drawStage = new DrawingStage(view);
  buildMenu(); buildTabs(); buildRail(); buildCanvasTop(); bindViewport(); bindKeys(); bindTimelineWheel(); bindCameraPresets(presetCtx());
  DOCK.init({ resized: () => { layout(); drawTracks(); }, toast, busy: () => playing || !!stage?.busy(), popOut: () => popOut(wfCtx()), pointerdownIn });
  // "group": frames the lead and every co-star together
  window.ds3dCameraPresets.register({ id: 'group', label: 'Everyone', points: () => [...view.bodyPoints(null, 12), ...(view.actors || []).flatMap(a => view.bodyPoints(a, 12))], facing: () => current('turn') });
  overlayDraw = bindOverlay(carCtx());
  MR.init(mirrorCtx());
  MR.onChange(() => { buildCanvasTop(); updateHud(); });
  $('#auto-key').addEventListener('click', e => { autoKey = !autoKey; e.currentTarget.setAttribute('aria-pressed', String(autoKey)); e.currentTarget.textContent = autoKey ? 'Keys: Auto' : 'Keys: Manual'; toast(autoKey ? 'Auto key: every change sets a key at the playhead' : 'Manual: changes are a preview until you press Key (K)'); });
  $('#render-btn').addEventListener('click', () => renderScene());
  $('#save-btn').addEventListener('click', () => saveShot(false));
  $('#shots-btn').addEventListener('click', e => ctxMenu(e, menus().find(m => m[0] === 'Shot')[1].map(it => (it === '-' ? '-' : [it[0] + (it[2] ? '   ' + it[2] : ''), () => runCommand({ group: 'Shot', label: it[0], run: it[1] })]))));
  new ResizeObserver(() => { const p = $('#panel'); p.classList.toggle('wide', p.clientWidth >= 900); }).observe($('#panel'));
  $('#shot-name').addEventListener('change', e => { scene.name = e.target.value; dirty = true; });
  new ResizeObserver(() => { if (!window.__fixedSize) { layout(); drawTracks(); } }).observe($('#canvas-wrap'));
  refreshAll();
  // the library loads at start-up, so the Stage tab's sets, outfits and items are there on first open
  loadLibrary(api).then(() => { if (['stage', 'library', 'animate', 'face'].includes(tab)) buildPanel(); apply(); }).catch(() => {});
  if (scene.audio?.path) loadAudio(api, scene.audio.path).then(drawTracks).catch(() => {});
  window.ds3dLibraryExtra = () => EXTRA.map(({ ask, def, ...r }) => r);
  window.ds3d = {
    get project() { return project; }, get scene() { return scene; }, set scene(s) { useScene(migrate(s)); }, goto, setValue, keyGroup, view, get frame() { return frame; }, get stage3d() { return stage; },
    // MCP surface (called by the desktop host)
    controls: () => [...BUNNY_IDS, ...FACE_IDS, ...CAM_IDS].map(id => {
      const [min, max] = DISCRETE.has(id) ? [0, ({ expression: data.face.faces.length, gaze: data.face.gazes.length, mouth: data.face.speech.length, blink: 5 })[id] - 1] : range(id);
      return { id, label: LABEL[id] || id, min, max, group: id.startsWith('cam.') ? 'camera' : FACE_IDS.includes(id) ? 'face' : PARTS.find(p => p[2].includes(id))?.[1] };
    }),
    names: () => ({ expressions: data.face.faces, gazes: data.face.gazes, mouths: data.face.speech }),
    bridgeShot: () => bridge(project),   // the active shot as Blender receives it
    async blenderLive(action) { if (action === 'open') await openInBlender(); else if (action === 'close') await MR.close(); return MR.state(); },
    state: () => ({ scene: scene.name, character: character(), stage: stageOf(scene, project), items: project.items || [], markers: project.markers || [], shot: project.code, shotName: project.label, shots: scene.shots.map((s, i) => ({ index: i, code: s.code, name: s.label, length: s.length, active: i === scene.active })),
      frame, length: project.length, fps: scene.fps, width: scene.width, height: scene.height, autoKey, file: filePath, unsaved: dirty,
      values: Object.fromEntries([...BUNNY_IDS, ...FACE_IDS, ...CAM_IDS].map(id => [id, round(current(id))])),
      idle: { ...idleOf(project), events: idleNow()?.events || [] },
      keyed: Object.fromEntries(Object.entries(project.tracks).map(([id, ks]) => [id, ks.map(k => [k.f, round(k.v), k.ease])])) }),
    setValues(values, at, key) {
      pushUndo('Set ' + Object.keys(values).map(id => LABEL[id] || id).slice(0, 3).join(', ') + (Object.keys(values).length > 3 ? '…' : ''));
      if (at != null) goto(at);
      const was = autoKey; if (key != null) autoKey = !!key;
      try { for (const [id, v] of Object.entries(values)) setValue(id, Number(v), { now: false }); } finally { autoKey = was; }
      apply(); drawTracks(); buildPanel();
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
      const bad = Object.keys(patch).filter(k => !['set', 'setProps', 'time', 'sky', 'shadows', 'halftone', 'lighting', 'inks', 'outfit', 'accessories', 'mouthSet'].includes(k));
      if (bad.length) throw Error('Unknown stage keys: ' + bad.join(', '));
      const r = setStage(libCtx(), patch, !!shotOnly);
      if (tab === 'library') buildPanel();
      return r;
    },
    // shadows and the 3-point light: { shadows, halftone, preset (id or null), target, key, fill, back, turn, height, distance, soft, shade, shotOnly }
    lighting(a = {}) {
      const st = stageOf(scene, project), patch = {};
      if (a.shadows != null) patch.shadows = !!a.shadows;
      if (a.halftone != null) { patch.halftone = a.halftone ? true : null; if (a.halftone) patch.shadows = true; }
      if (a.preset === null || a.preset === 'off') patch.lighting = null;
      else {
        if (a.preset && !LIGHT_PRESETS.some(p => p[0] === a.preset)) throw Error('preset is one of ' + LIGHT_PRESETS.map(p => p[0]).join(', '));
        const base = a.preset ? makeLighting(a.preset, a.turn ?? st.lighting?.turn ?? view.cam.yaw, st.lighting?.target) : st.lighting;
        const nums = Object.fromEntries(['key', 'fill', 'back', 'turn', 'height', 'distance', 'soft', 'shade'].filter(k => a[k] != null).map(k => [k, Number(a[k])]));
        if (Object.keys(nums).length || a.target != null || a.preset) { if (!base) throw Error('Pick a preset first: ' + LIGHT_PRESETS.map(p => p[0]).join(', ')); patch.lighting = { ...base, ...nums, ...(a.target != null ? { target: String(a.target) } : {}) }; }
      }
      if (Object.keys(patch).length) setStage(libCtx(), patch, !!a.shotOnly);
      if (tab === 'stage') buildPanel();
      const now = stageOf(scene, project);
      return { shadows: !!now.shadows, halftone: !!now.halftone, lighting: now.lighting || null, presets: LIGHT_PRESETS.map(p => ({ id: p[0], name: p[1], about: p[2] })) };
    },
    // one object's outline, percent of Bunny's line (0 takes it off, 100 is the default): piece id, '@lead', '@costar0', or item index
    setInk(target, percent, shotOnly) {
      const v = Math.max(0, Math.min(300, Math.round(Number(percent))));
      if (typeof target === 'number') { if (!project.items?.[target]) throw Error('No item ' + target); editItem(target, { ink: v === 100 ? null : v }, 'Outline'); return { item: target, ink: v }; }
      const inks = { ...(stageOf(scene, project).inks || {}), [target]: v };
      if (v === 100) delete inks[target];
      setStage(libCtx(), { inks: Object.keys(inks).length ? inks : null }, !!shotOnly);
      return { inks: stageOf(scene, project).inks || {} };
    },
    storyboard: () => storyboard(),
    importAudio: p => importAudio(p ?? null),
    audioDrive: (id, a, b, opts) => driveFromAudio(id, a, b, opts),
    lipsync: (o = {}) => lipsyncFromAudio(o),
    babble: (a = {}) => babbleAct(a),
    blocks: (a = {}) => blocksAct(a),
    voiceFx: (a = {}) => voiceFxAct(a),
    transcribe: (a = {}) => (a.action === 'captions' ? transcriptCaptions() : a.action === 'get' ? scene.transcript || null : transcribeAct(a)),
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
    // Materials tab (materials.js): list looks and palettes, apply a look to a target, clear it, set the light
    materials(a) { return MAT.mcp(matCtx(), a || {}); },
    setShotLook(p) {
      pushUndo(); if (p.horizonLock != null) project.horizonLock = !!p.horizonLock; if (p.ink != null) project.ink = Math.max(40, Math.min(250, Number(p.ink)));
      for (const [k, v] of Object.entries(p.rules || {})) if (RULES.some(r => r[0] === k)) { project.rules ||= {}; if (v === false) project.rules[k] = false; else delete project.rules[k]; }
      if (p.captionSnap != null) { P.captionsOf(scene).snap = p.captionSnap ? undefined : false; drawPost(); }
      apply(); buildPanel();
      return { shot: project.code, horizonLock: !!project.horizonLock, ink: project.ink ?? 100, rules: Object.fromEntries(RULES.map(([k]) => [k, project.rules?.[k] !== false])), captionSnap: scene.captions?.snap !== false };
    },
    removeItem(i) { const r = removeItem(libCtx(), i); if (tab === 'library') buildPanel(); return r; },
    stage: () => ({ character: character(), stage: stageOf(scene, project), sceneStage: scene.stage || {}, shotStage: project.stage || {}, items: project.items || [] }),
    save: () => saveShot(false, true),
    // scene files (MCP tools new_scene, open_scene, save_as)
    newScene(a = {}) {
      if (dirty && !confirm('Start a new blank scene? Unsaved changes are lost (the autosave keeps a copy).')) return null;
      const sc = newScene(String(a.name || 'Untitled scene'));
      if (a.character) sc.character = String(a.character);
      if (a.width && a.height) { sc.width = Number(a.width); sc.height = Number(a.height); }
      if (a.fps) sc.fps = Number(a.fps);
      filePath = null; undoStack = []; redoStack = []; dirty = false; frame = 0;
      useScene(sc);
      return this.state();
    },
    async openScene(file) {
      if (!file) throw Error('Give the path of a .ds3d scene inside the renders folder');
      if (dirty && !confirm('Open another scene? Unsaved changes are lost (the autosave keeps a copy).')) return null;
      const r = await api('open-file', { file });
      filePath = r.path; undoStack = []; redoStack = []; dirty = false; frame = 0;
      useScene(migrate(r.project));
      return { path: filePath, ...this.state() };
    },
    async saveAs(a = {}) {
      if (!a.name && !a.path) throw Error('Give a new scene name (saves to DeepInDoodles\\<name>\\work\\) or a .ds3d path inside the renders folder');
      if (a.name) { scene.name = String(a.name); $('#shot-name').value = scene.name; }
      if (a.path) {
        const r = await api('save-at', { project: scene, path: a.path });
        filePath = r.path; dirty = false; updateHud();
        return r;
      }
      filePath = null;
      return saveShot(false, true);
    },
    undo, redo,
    // cast.js (MCP tool "cast")
    async cast(a = {}) { if (a.shot != null) selectShot(a.shot); if (a.frame != null) goto(a.frame); const r = await castAct(a); if (r && typeof r === 'object' && !Array.isArray(r)) delete r.message; return r; },
    // drawings.js (MCP tool "drawings")
    async drawings(a = {}) { if (a.shot != null) selectShot(a.shot); if (a.at_frame != null) goto(a.at_frame); return dr(a); },
    // powers.js (MCP tool "powers")
    async powers(a = {}) { if (a.shot != null) selectShot(a.shot); if (a.frame != null) goto(a.frame); const r = await pw(a); if (r && typeof r === 'object' && !Array.isArray(r)) delete r.message; return r; },
    // features2.js (MCP tool "features")
    async features(a = {}) { if (a.shot != null) selectShot(a.shot); if (a.frame != null) goto(a.frame); const r = await feat(a); if (r && typeof r === 'object' && !Array.isArray(r)) delete r.message; return r; },
    // post.js (MCP tool "post")
    async post(a = {}) { if (a.shot != null) selectShot(a.shot); if (a.frame != null) goto(a.frame); const r = await postAct(a); if (r && typeof r === 'object' && !Array.isArray(r)) delete r.message; return r; },
    // storytime2.js (MCP tool "story2")
    async story2(a = {}) { if (a.shot != null && !['cold_open', 'mood'].includes(a.action)) selectShot(a.shot); if (a.frame != null) goto(a.frame); const r = await story2(a); if (r && typeof r === 'object') delete r.message; return r; },
    // animtools2.js (MCP tool "anim2")
    async anim2(a = {}) {
      const c = anim2Ctx();
      if (a.shot != null) selectShot(a.shot);
      if (a.frame != null) goto(a.frame);
      const limb = () => { if (!A2.LIMB[a.limb]) throw Error('limb must be armL, armR, legL or legR'); return a.limb; };
      const out = {
        pick: () => { const r = view.renderer.domElement.getBoundingClientRect(); return clickPick(r.left + (a.x ?? 0.5) * r.width, r.top + (a.y ?? 0.5) * r.height); },
        ik_mode: () => toggleIk(a.on ?? !ikOn),
        ik: () => {
          const L = limb(), base = valuesNow(), side = L.endsWith('L') ? '.L' : '.R';
          const want = a.target ? new THREE.Vector3(...a.target) : A2.endPoint(view, base, L).add(new THREE.Vector3(...(a.offset || [0, 0, 0])));
          // solve against the head: if the arm would pass through it, the target moves out
          // from the head 3 cm at a time (up to 30 cm) until the arm clears it
          const clipsAt = vals => { view.pose(vals); view.group.updateMatrixWorld(); return (view.ruleCheck()?.clips || []).filter(n => n.endsWith(side)); };
          let r = A2.ikMove(view, base, L, { target: want.toArray() }, range), moved = 0, clips = L.startsWith('arm') ? clipsAt({ ...base, ...r.values }) : [];
          if (clips.length && !a.allowClip) {
            // away from the head, out to his side, towards the camera, or up: the nearest clear spot wins
            const hp = view.headPoint(), sx = Math.sign(A2.endPoint(view, base, L).x - hp.x) || 1, away = want.clone().sub(hp);
            const dirs = [...(away.length() > 0.02 ? [away.normalize()] : []), [sx, 0, 0], [sx, -1, 0], [0, -1, 0], [sx, 0, 1], [sx, -1, 1]].map(d => (d.isVector3 ? d : new THREE.Vector3(...d)).normalize());
            let best = null;
            for (let k = 1; k <= 10 && !best; k++) for (const d of dirs) {
              const t = want.clone().addScaledVector(d, 0.03 * k), r2 = A2.ikMove(view, base, L, { target: t.toArray() }, range), c2 = clipsAt({ ...base, ...r2.values });
              if (!c2.length) { best = { r: r2, k }; break; }
            }
            if (best) { r = best.r; clips = []; moved = 3 * best.k; }
          }
          pushUndo('IK ' + L); for (const [id, v] of Object.entries(r.values)) setValue(id, v, { now: false }); apply(); drawTracks();
          const res = { limb: L, values: r.values, missedCm: +(r.error * 100).toFixed(1), end: A2.v3(A2.endPoint(view, valuesNow(), L)) };
          if (moved) res.note = `Moved the target ${moved} cm out from the head so the arm clears it`;
          if (clips.length) res.warning = `The ${clips.join(', ')} still pass${clips.length === 1 ? 'es' : ''} through the head in this pose (rule 1). Pick another target.`;
          return res;
        },
        end_point: () => { const L = limb(), p = A2.endPoint(view, valuesNow(), L); apply(); const q = p.clone().project(view.camera); return { limb: L, frame, at: A2.v3(p), screen: [+((q.x + 1) / 2).toFixed(4), +((1 - q.y) / 2).toFixed(4)] }; },
        pin: () => A2.pin(c, limb(), a.from ?? frame, a.to ?? project.length - 1, a.step ?? 2),
        path: () => { const r = showPath(a.what === undefined ? 'armR' : a.what); return { ...r, frames: pathPts?.length || 0, points: a.points && pathPts ? pathPts.map(A2.v3) : undefined }; },
        fix_arcs: () => fixArcs(a.what || pathWhat || 'armR'),
        curves: () => toggleCurves(a.on ?? !curves),
        time_warp: () => A2.timeWarp(c, a.warp, a.amount ?? 1),
        moving_hold: () => A2.movingHold(c, a.from ?? frame, a.to ?? Math.min(project.length - 1, frame + 12), a.amount ?? 0.06),
        save_pose: () => { const r = A2.savePose(c, a.name || 'Pose', a.part || 'whole'); if (tab === 'pose') buildPanel(); return r; },
        poses: () => A2.poses(),
        apply_pose: () => A2.applyPose(c, a.name),
        delete_pose: () => { A2.deletePose(a.name); if (tab === 'pose') buildPanel(); return A2.poses().map(p => p.name); },
        copy_keys: () => A2.copyKeys(c, { from: a.from ?? 0, to: a.to ?? project.length - 1, part: a.part || 'whole' }),
        paste_keys: () => A2.pasteKeys(c, a.at ?? frame),
        move_keys: () => moveKeys(a.keys || [], a.by || 0),
        add_layer: () => newLayer(a.name),
        layers: () => layersInfo(),
        layer: () => {
          const i = a.index ?? editLayer, L = project.layers?.[i];
          if (i >= 0 && !L) throw Error('No layer ' + i + '; add_layer makes one');
          pushUndo('Layer');
          if (L && a.on != null) L.on = !!a.on;
          if (L && a.weight != null) L.weight = Math.max(0, Math.min(2, Number(a.weight)));
          if (L && a.name) L.name = String(a.name).slice(0, 30);
          if (a.edit != null) editLayer = a.edit ? i : -1;
          dirty = true; buildTimelineTools(); drawTracks(); apply();
          return layersInfo();
        },
        euler_filter: () => A2.eulerFilter(c),
        balance: () => { const b = A2.balance(view); if (a.on != null) { balanceOn = !!a.on; apply(); if (!balanceOn) drawCog(); } return { balanced: b.balanced, grounded: b.grounded, offCm: b.offCm, cog: A2.v3(b.cog) }; },
        reference: () => (a.clear ? clearReference() : referenceVideo(a.path, a)),
        reference_info: () => ({ reference: scene.reference || null, video: A2.referenceInfo() }),
        retarget: () => retargetTo(a.character),
        playblast: () => playblast(animCtx()),
      }[a.action];
      if (!out) throw Error('action must be pick, ik_mode, ik, end_point, pin, path, fix_arcs, curves, time_warp, moving_hold, save_pose, poses, apply_pose, delete_pose, copy_keys, paste_keys, move_keys, add_layer, layers, layer, euler_filter, balance, reference, reference_info, retarget or playblast');
      return out();
    },
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
