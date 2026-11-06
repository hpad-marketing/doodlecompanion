// Animator tools: breakdown (tween) slider, overlap down a chain, key simplify, loop
// check and seamless loop, retime, stepped blocking, onion skin, silhouette and mirror
// view, timeline key filters and a playblast with a frame counter.
import { valueAt, setKey, DISCRETE } from './project.js';
import { MUSTARD, INK } from './viewport.js';
import { LIT } from './lit.js';

// ---------------------------------------------------------------- breakdown: in-between of the keys either side
export function breakdown(ctx, t, ids = ctx.poseIds()) {
  const p = ctx.project(), f = ctx.frame(), k = Math.max(-0.25, Math.min(1.25, t / 100));   // a little past either side
  const done = [];
  ctx.pushUndo();
  for (const id of ids) {
    const keys = p.tracks[id];
    if (!keys) continue;
    const a = [...keys].reverse().find(x => x.f < f), b = keys.find(x => x.f > f);
    if (!a || !b) continue;
    setKey(p, id, f, DISCRETE.has(id) ? (k < 0.5 ? a.v : b.v) : a.v + (b.v - a.v) * k);
    done.push(id);
  }
  ctx.changed();
  return { frame: f, keyed: done, favour: t < 50 ? 'previous' : t > 50 ? 'next' : 'even' };
}

// ---------------------------------------------------------------- overlap: each control down a chain lags the one above
export function overlap(ctx, ids, step = 2) {
  const p = ctx.project();
  ctx.pushUndo();
  const moved = [];
  ids.filter(id => p.tracks[id]).forEach((id, i) => {
    if (!i) return;
    for (const k of p.tracks[id]) k.f = Math.min(p.length - 1, k.f + i * step);
    // keys pushed onto the same frame keep the later value
    p.tracks[id] = Object.values(Object.fromEntries(p.tracks[id].map(k => [k.f, k]))).sort((a, b) => a.f - b.f);
    moved.push([id, i * step]);
  });
  ctx.changed();
  return { offsets: moved };
}

// ---------------------------------------------------------------- key simplify: drop keys the curve does not need
export function simplify(ctx, tol = 0.75) {
  const p = ctx.project();
  ctx.pushUndo();
  let before = 0, after = 0;
  for (const [id, keys] of Object.entries(p.tracks)) {
    before += keys.length;
    if (DISCRETE.has(id) || keys.length < 3) { after += keys.length; continue; }
    const orig = Array.from({ length: p.length }, (_, f) => valueAt(p, id, f));
    const lim = id.startsWith('cam.') ? tol * 0.02 : tol;
    for (let i = 1; i < p.tracks[id].length - 1;) {
      const ks = p.tracks[id], [a, k, b] = [ks[i - 1], ks[i], ks[i + 1]];
      ks.splice(i, 1);
      let worst = 0;
      for (let f = a.f; f <= b.f && f < p.length; f++) worst = Math.max(worst, Math.abs(valueAt(p, id, f) - orig[f]));
      if (worst > lim) { ks.splice(i, 0, k); i++; }
    }
    after += p.tracks[id].length;
  }
  ctx.changed();
  return { before, after, removed: before - after };
}

// ---------------------------------------------------------------- loops
export function loopCheck(ctx) {
  const p = ctx.project(), last = p.length - 1, off = [];
  for (const id of Object.keys(p.tracks)) {
    if (id.startsWith('cam.')) continue;
    const d = Math.abs(valueAt(p, id, 0) - valueAt(p, id, last));
    if (d > 0.5) off.push({ id, first: +valueAt(p, id, 0).toFixed(2), last: +valueAt(p, id, last).toFixed(2) });
  }
  return { seamless: !off.length, mismatched: off };
}
export function makeLoop(ctx) {
  const p = ctx.project(), last = p.length - 1;
  ctx.pushUndo();
  for (const id of Object.keys(p.tracks)) if (!id.startsWith('cam.')) setKey(p, id, last, valueAt(p, id, 0));
  ctx.changed();
  return loopCheck(ctx);
}

// ---------------------------------------------------------------- retime: scale the shot's timing from a frame
export function retime(ctx, factor, from = 0) {
  const p = ctx.project();
  factor = Math.max(0.1, Math.min(10, Number(factor) || 1));
  const map = f => (f <= from ? f : Math.round(from + (f - from) * factor));
  ctx.pushUndo();
  for (const id of Object.keys(p.tracks)) p.tracks[id] = Object.values(Object.fromEntries(p.tracks[id].map(k => [map(k.f), { ...k, f: map(k.f) }]))).sort((a, b) => a.f - b.f);
  for (const m of p.markers || []) m.f = map(m.f);
  for (const it of p.items || []) it.frame = map(it.frame);
  p.length = Math.max(1, map(p.length - 1) + 1);
  ctx.changed(true);
  return { length: p.length, factor, from };
}

// ---------------------------------------------------------------- onion skin, silhouette, mirror view
export const view3 = { onion: false, onionMode: 'keys', onionStep: 4, silhouette: false, mirror: false };
let layer = null;
function onionLayer() {
  if (layer) return layer;
  layer = document.createElement('canvas');
  layer.id = 'onion-layer';
  document.querySelector('#frame').insertBefore(layer, document.querySelector('#hud'));
  return layer;
}
// ghosts: the pose at the previous and next key (or N frames either side), as faint ink
export function drawOnion(ctx) {
  const L = onionLayer(), v = ctx.view(), src = v.renderer.domElement;
  L.width = src.width; L.height = src.height;
  const g = L.getContext('2d', { willReadFrequently: true });
  g.clearRect(0, 0, L.width, L.height);
  if (!view3.onion) return;
  const p = ctx.project(), f = ctx.frame();
  let around;
  if (view3.onionMode === 'keys') {
    const fs = [...new Set(ctx.poseIds().flatMap(id => (p.tracks[id] || []).map(k => k.f)))].sort((a, b) => a - b);
    around = [[...fs].reverse().find(x => x < f), fs.find(x => x > f)];
  } else around = [f - view3.onionStep, f + view3.onionStep];
  const now = v.values, grid = v.grid.visible;
  v.grid.visible = false;
  const shade = LIT.litShade.value; LIT.litShade.value = 0;   // ghosts are keyed off flat mustard
  const W = L.width, H = L.height, mr = 0xE0, mg = 0xA6, mb = 0x4B;   // brand mustard / ink as drawn (sRGB)
  around.forEach((gf, i) => {
    if (gf == null || gf < 0 || gf >= p.length) return;
    v.pose(ctx.valuesAt(gf));
    v.renderer.render(v.scene, v.camera);
    const tmp = document.createElement('canvas'); tmp.width = W; tmp.height = H;
    const tg = tmp.getContext('2d', { willReadFrequently: true });
    tg.drawImage(src, 0, 0);
    const img = tg.getImageData(0, 0, W, H), d = img.data;
    // keep the ink, drop the mustard: previous pose stronger than the next one
    const a = i === 0 ? 110 : 60;
    for (let j = 0; j < d.length; j += 4) {
      const dist = Math.abs(d[j] - mr) + Math.abs(d[j + 1] - mg) + Math.abs(d[j + 2] - mb);
      d[j + 3] = dist > 120 ? a : 0;
      d[j] = 0x1F; d[j + 1] = 0x1F; d[j + 2] = 0x1D;
    }
    tg.putImageData(img, 0, 0);
    g.drawImage(tmp, 0, 0);
  });
  v.grid.visible = grid; LIT.litShade.value = shade;
  v.pose(now);
}
export function setSilhouette(view, on) {
  view3.silhouette = on;
  for (const o of view.objects) {
    if (o.mesh.material.uniforms?.base) o.mesh.material.uniforms.base.value.copy(on ? INK : MUSTARD);
    else o.mesh.material.color?.set(on ? INK : 0xffffff), o.mesh.material.vertexColors = !on, o.mesh.material.needsUpdate = true;
  }
}
export function setMirror(on) {
  view3.mirror = on;
  document.querySelector('#frame').classList.toggle('mirrored', on);
}

// ---------------------------------------------------------------- timeline key filters
export const FILTERS = { all: 'All keys', body: 'Body', hands: 'Arms and hands', face: 'Face and ears', camera: 'Camera' };
export function filterIds(filter, ids) {
  const is = {
    body: id => /^(body|depth|s$|turn|torso|breath|leg|knee|foot|head|rot$)/.test(id),
    hands: id => /^(arm|elbow|wrist)/.test(id),
    face: id => /^(expression|gaze|mouth|blink|ear|nose)/.test(id),
    camera: id => id.startsWith('cam.'),
  }[filter];
  return is ? ids.filter(is) : ids;
}

// ---------------------------------------------------------------- playblast: the viewport, frame by frame, with a counter
export async function playblast(ctx) {
  const v = ctx.view(), src = v.renderer.domElement, p = ctx.project(), scene = ctx.scene();
  const comp = document.createElement('canvas');
  comp.width = src.width - (src.width % 2); comp.height = src.height - (src.height % 2);
  const g = comp.getContext('2d');
  const stream = comp.captureStream(0), track = stream.getVideoTracks()[0];   // one video frame per timeline frame
  // the scene audio rides along, from this shot's start in the scene
  const sound = ctx.audioStream?.();
  if (sound) stream.addTrack(sound.track);
  const type = (sound ? ['video/webm;codecs=vp8,opus'] : []).concat(['video/webm;codecs=vp8', 'video/webm']).find(t => MediaRecorder.isTypeSupported(t));
  const rec = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 8e6 });
  const chunks = [];
  rec.ondataavailable = e => e.data.size && chunks.push(e.data);
  const stopped = new Promise(r => { rec.onstop = r; });
  rec.start(250);
  const keep = ctx.frame(), dt = 1000 / scene.fps;
  let t0 = performance.now();
  for (let f = 0; f < p.length; f++) {
    ctx.goto(f);
    v.render();
    g.drawImage(src, 0, 0, comp.width, comp.height);
    const label = `${scene.name} · ${p.code}   F${String(f).padStart(4, '0')} / ${p.length - 1}   ${(f / scene.fps).toFixed(2)} s`;
    g.font = `700 ${Math.round(comp.height / 48)}px system-ui, sans-serif`;
    const w = g.measureText(label).width + 16, hh = Math.round(comp.height / 30);
    g.fillStyle = '#1F1F1D'; g.fillRect(8, comp.height - hh - 8, w, hh);
    g.fillStyle = '#E0A64B'; g.fillText(label, 16, comp.height - 8 - hh * 0.3);
    track.requestFrame();
    const wait = t0 + (f + 1) * dt - performance.now();
    await new Promise(r => setTimeout(r, Math.max(4, wait)));   // always yield, or the recorder only sees the last frame
  }
  await new Promise(r => setTimeout(r, 300));   // let the encoder flush the last frames
  rec.stop();
  sound?.stop();
  await stopped;
  ctx.goto(keep);
  const blob = new Blob(chunks, { type: 'video/webm' });
  const b64 = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(String(fr.result).split(',')[1]); fr.readAsDataURL(blob); });
  const root = (await ctx.api('settings', {})).rendersRoot;
  const safe = (scene.name || 'Untitled').replace(/[\\/:*?"<>|]/g, '_');
  const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '');
  const r = await ctx.api('write-file', { path: `${root}/${safe}/work/playblast/${safe.replace(/ /g, '_')}_${p.code}_playblast_${stamp}.webm`, data: b64 });
  ctx.toast('Playblast saved: ' + r.path, 6000);
  return { path: r.path, frames: p.length, bytes: blob.size, audio: !!sound };
}
