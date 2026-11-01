// The live stage in the 3D view: the set with its pieces, props (held or standing), scenery,
// effects, reaction pops and storytime pieces, drawn in the Doodle look (mustard fill, ink
// line) so a shot can be composed by eye, without Blender. Click anything to select it; the
// gizmo moves, turns and scales it, and the change is saved on the shot so the Blender render
// puts it in the same place. Models are the library's own, converted once by Blender on this
// PC (Library › 3D models) and cached.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { outlineVS, outlineFS, INK, MUSTARD } from './viewport.js';
import { glyphOf } from './libview.js';
import { LIT, litPars } from './lit.js';

const D2R = Math.PI / 180;
const REACT_FRAMES = 36;          // a reaction pop stays this long
const STORY_FRAMES = { time_skip: 60, chat: 75, label: 90, journey: 120, end_screen: 150 };
const DS_TO_BLENDER = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1);
const FX = {
  rain: { kind: 'fall', n: 260, speed: 4.5, len: 0.12 }, downpour: { kind: 'fall', n: 520, speed: 6, len: 0.2 }, splashes: { kind: 'burst', n: 60, speed: 0.6 },
  snow: { kind: 'fall', n: 220, speed: 0.6, dot: 0.018 }, leaves: { kind: 'fall', n: 60, speed: 0.7, dot: 0.035, sway: 0.25 }, petals: { kind: 'fall', n: 80, speed: 0.6, dot: 0.025, sway: 0.2 },
  confetti: { kind: 'fall', n: 180, speed: 1.1, dot: 0.02, sway: 0.15 }, streamers: { kind: 'fall', n: 40, speed: 0.9, len: 0.18, sway: 0.2 },
  wind: { kind: 'drift', n: 30, speed: 2, len: 0.35 }, speed_lines: { kind: 'drift', n: 50, speed: 6, len: 0.6 }, steam: { kind: 'rise', n: 26, speed: 0.3, dot: 0.05 }, smoke: { kind: 'rise', n: 30, speed: 0.25, dot: 0.09 },
  dust: { kind: 'rise', n: 80, speed: 0.08, dot: 0.012 }, sparkles: { kind: 'twinkle', n: 40, dot: 0.03 }, fireworks: { kind: 'burst', n: 120, speed: 1.6, high: 1.8 }, poof: { kind: 'burst', n: 40, speed: 0.5, dot: 0.06 },
  sparkle_burst: { kind: 'burst', n: 50, speed: 0.9, dot: 0.03, high: 0.6 },
};
const STAGE_BIAS = 1.2;            // outline push behind a set piece, in ink widths
const CREASE_DEG = 32;            // edges sharper than this get a line, as the library's crease lines in Blender
// Fills read the scene's light and shadow when they are on (lit.js), flat mustard otherwise.
const fillVS = `varying vec3 vN; varying vec3 vP; void main(){ vN = normalize(mat3(modelMatrix) * normal); vec4 w = modelMatrix * vec4(position, 1.0); vP = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const fillFS = `uniform vec3 base; uniform vec3 floorC; uniform vec3 roofC; uniform float room; varying vec3 vN; varying vec3 vP;
${litPars}
void main(){
  vec3 c = room > 0.5 && abs(vN.z) > 0.7 ? (vP.z < 1.0 ? floorC : roofC) : base;   // a room shell: walls, floor and ceiling
  gl_FragColor = vec4(mix(c, litInk, litBand(normalize(gl_FrontFacing ? vN : -vN), vP)), 1.0);
#include <colorspace_fragment>
}`;
const rnd = s => { let x = Math.sin(s * 127.1) * 43758.5453; return x - Math.floor(x); };

export class Stage {
  constructor(view, ctx) {
    this.view = view; this.ctx = ctx;
    this.root = new THREE.Group(); this.root.name = 'stage';
    view.scene.add(this.root);
    this.models = new Map();      // id -> { state: 'loading'|'ready'|'missing', gltf }
    this.setGroup = null; this.setId = null;
    this.items = [];              // index -> { id, obj, kind }
    this.loader = new GLTFLoader();
    this.selected = null;         // { type: 'item', index } | { type: 'piece', id } | { type: 'bunny' }
    this.waiting = new Set(); this.polling = false;
    this.inkMats = { mustard: new THREE.MeshBasicMaterial({ color: MUSTARD }), ink: new THREE.MeshBasicMaterial({ color: INK }), line: new THREE.LineBasicMaterial({ color: INK }) };
    // set pieces sit on the floor: a smaller push behind keeps their outline above the ground (Bunny's own stays as it is)
    this.outline = new THREE.ShaderMaterial({ vertexShader: outlineVS, fragmentShader: outlineFS, uniforms: { ...view.outlineUniforms, bias: { value: STAGE_BIAS } }, side: THREE.BackSide });
    this.fill = new THREE.ShaderMaterial({ vertexShader: fillVS, fragmentShader: fillFS, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1,
      uniforms: { ...LIT, base: { value: MUSTARD.clone() }, floorC: { value: MUSTARD.clone() }, roofC: { value: MUSTARD.clone() }, room: { value: 0 } } });
    this.fills = new Map();       // palette colour -> fill
    // crease and border lines: one ink width on screen, the same width as Bunny's outline
    this.lineMat = new LineMaterial({ color: INK.getHex(), linewidth: 4, worldUnits: false });
    this.lineMat.polygonOffset = true; this.lineMat.polygonOffsetFactor = -1; this.lineMat.polygonOffsetUnits = -2;
    const U = view.outlineUniforms;
    this.inkSync = (r, s, c, g, m) => { m.resolution.copy(U.res.value); m.linewidth = U.inkPx.value * (m.userData.inkK ?? 1); };
    this.inks = new Map();        // percent -> { hull, line }: a piece's own outline thickness
    this.gizmo = new TransformControls(view.camera, view.canvas);
    this.gizmo.setSize(0.85);
    this.helper = this.gizmo.getHelper();
    // brand colours on the gizmo: ink handles, the one under the pointer at full strength
    const gz = this.gizmo._gizmo;
    if (gz) {
      const up = gz.updateMatrixWorld.bind(gz);
      gz.updateMatrixWorld = force => {
        up(force);
        gz.traverse(o => { const m = o.material; if (!m?.color) return; const hot = m.color.getHex() === 0xffff00; m.color.copy(INK); if (!hot) m.opacity = Math.min(m.opacity, 0.7); });
      };
    }
    view.scene.add(this.helper);
    this.gizmo.addEventListener('dragging-changed', e => { this.dragging = e.value; if (e.value) ctx.pushUndo('Move in the 3D view'); else this.commit(); });
    this.gizmo.addEventListener('objectChange', () => this.live());
    this.proxy = new THREE.Object3D(); view.scene.add(this.proxy);   // stands in for the character when moving him
  }

  busy() { return !!this.dragging || this.gizmo.axis != null; }

  // ---------------------------------------------------------------- models
  async want(ids) {
    const need = ids.filter(id => !this.models.has(id));
    if (!need.length) return;
    for (const id of need) this.models.set(id, { state: 'loading' });
    let r;
    try { r = await this.ctx.api('stage-models', { ids: need }); } catch (e) { for (const id of need) this.models.set(id, { state: 'missing', error: e.message }); this.ctx.changed(); return; }
    for (const id of need) {
      const url = r.models?.[id];
      if (url) this.fetch(id, url);
      else if ((r.pending || []).includes(id)) { this.models.set(id, { state: 'baking' }); this.waiting.add(id); }
      else this.models.set(id, { state: 'missing', error: r.errors?.[id] || r.error || 'no model' });
    }
    if (r.error && !this.warned) { this.warned = true; this.ctx.toast(r.error, 6000); }
    if (this.waiting.size) this.poll();
    this.ctx.changed();
  }
  poll() {
    if (this.polling) return;
    this.polling = true;
    const tick = async () => {
      const ids = [...this.waiting];
      if (!ids.length) { this.polling = false; return; }
      try {
        const r = await this.ctx.api('stage-models', { ids, wait: true });
        for (const id of ids) {
          if (r.models?.[id]) { this.waiting.delete(id); this.fetch(id, r.models[id]); }
          else if (!(r.pending || []).includes(id)) { this.waiting.delete(id); this.models.set(id, { state: 'missing', error: r.errors?.[id] || 'could not be converted' }); }
        }
      } catch {}
      this.ctx.changed();
      setTimeout(tick, 1200);
    };
    setTimeout(tick, 900);
  }
  fetch(id, url) {
    this.models.set(id, { state: 'loading' });
    this.loader.load(url, g => { this.models.set(id, { state: 'ready', scene: g.scene }); this.dirty = true; this.ctx.changed(); },
      undefined, e => { this.models.set(id, { state: 'missing', error: String(e?.message || e) }); this.ctx.changed(); });
  }
  status() {
    const v = [...this.models.values()];
    return { loading: v.filter(m => m.state === 'loading' || m.state === 'baking').length, missing: v.filter(m => m.state === 'missing').length };
  }
  // a copy of a model in the Doodle look; meshes keep their names and extras for picking
  doodle(src) {
    const g = src.clone(true);
    const meshes = [];
    g.traverse(o => { if (o.isMesh) meshes.push(o); });
    const inShell = o => { for (; o && o !== g; o = o.parent) if (o.userData?.ds_shell) return true; return false; };
    meshes.forEach(o => {
      const ink = (Array.isArray(o.material) ? o.material : [o.material]).every(m => m?.userData?.ds_ink || /ink/i.test(m?.name || ''));
      if (!o.geometry.attributes.normal) o.geometry.computeVertexNormals();
      const shell = inShell(o);
      o.material = ink ? this.inkMats.ink : this.fill;
      o.userData.isFill = !ink;
      if (!shell) o.layers.enable(1);   // casts in the shadow pass; the room only catches
      if (o.userData.noInk) return;
      const { hull, edges } = this.inkGeometry(o.geometry, shell);
      // silhouette: the screen-constant hull, on smooth normals so it never cracks at hard
      // edges (cracked hulls were the uneven thick and thin lines). Ink parts get it too, as in Blender.
      if (!shell) { const line = new THREE.Mesh(hull, this.outline); line.userData.isInk = true; line.raycast = () => {}; o.add(line); }
      // creases and open borders as lines one ink wide: flat shapes (a far moon, a flag) keep their edge
      if (edges && !ink) o.add(this.inkLines(edges));
    });
    return g;
  }

  // the hull (smooth normals, welded) and the crease/border edges of a model's geometry, cached per geometry
  inkGeometry(geo, shell) {
    this.inkCache ||= new WeakMap();
    let c = this.inkCache.get(geo);
    if (c) return c;
    const pos = new THREE.BufferGeometry();
    pos.setAttribute('position', geo.attributes.position);
    if (geo.index) pos.setIndex(geo.index);
    const welded = mergeVertices(pos, 1e-4);
    welded.computeVertexNormals();
    const e = new THREE.EdgesGeometry(welded, CREASE_DEG);
    const arr = e.attributes.position.array;
    c = { hull: shell ? null : welded, edges: arr.length ? arr : null };
    e.dispose();
    this.inkCache.set(geo, c);
    return c;
  }
  inkLines(arr) {
    const g = new LineSegmentsGeometry(); g.setPositions(arr);
    const l = new LineSegments2(g, this.lineMat);
    l.userData.isInk = true; l.raycast = () => {};
    l.onBeforeRender = this.inkSync;
    return l;
  }
  // a fill in a palette colour; shell = a room, with its own floor and ceiling
  fillFor(hex, shell) {
    if (!hex) return this.fill;
    const k = shell ? shell.wall + shell.floor + shell.ceiling : hex;
    let m = this.fills.get(k);
    if (!m) {
      m = this.fill.clone();
      m.uniforms = { ...LIT, base: { value: new THREE.Color(hex) }, floorC: { value: new THREE.Color(shell?.floor || hex) }, roofC: { value: new THREE.Color(shell?.ceiling || hex) }, room: { value: shell ? 1 : 0 } };
      this.fills.set(k, m);
    }
    return m;
  }
  setFill(root, m) { root.traverse(o => { if (o.userData.isFill) o.material = m; }); }
  // one object's outline as a percent of Bunny's line; 0 takes it off
  inkFor(pct) {
    if (pct === 100) return { hull: this.outline, line: this.lineMat };
    let m = this.inks.get(pct);
    if (!m) {
      const line = new LineMaterial({ color: INK.getHex(), linewidth: 4, worldUnits: false });
      line.polygonOffset = true; line.polygonOffsetFactor = -1; line.polygonOffsetUnits = -2; line.userData.inkK = pct / 100;
      m = { line, hull: new THREE.ShaderMaterial({ vertexShader: outlineVS, fragmentShader: outlineFS, uniforms: { ...this.view.outlineUniforms, bias: { value: STAGE_BIAS }, inkK: { value: pct / 100 } }, side: THREE.BackSide }) };
      this.inks.set(pct, m);
    }
    return m;
  }
  setInk(root, pct) {
    const m = this.inkFor(pct);
    root.traverse(o => { if (o.userData.isInk) { o.material = o.isLineSegments2 ? m.line : m.hull; o.visible = pct > 0; } });
  }

  // ---------------------------------------------------------------- what is on stage this frame
  // st: stageOf(scene, shot); items: shot.items; f: frame; rows: library rows by id
  sync({ stage: st, noInk = {}, paint = null, items = [], frame: f, length, rows, playing }) {
    this.frame = f;
    // set
    const setId = st.set ? 'set-' + st.set : null;
    if (setId !== this.setId || (setId && this.setGroup?.userData.pending && this.models.get(setId)?.state === 'ready')) {
      if (this.setGroup) this.root.remove(this.setGroup);
      this.setGroup = null; this.setId = setId;
      if (this.selected?.type === 'piece') this.select(null);
      if (setId) {
        const m = this.models.get(setId);
        if (!m) this.want([setId]);
        this.setGroup = m?.state === 'ready' ? this.doodle(m.scene) : new THREE.Group();
        this.setGroup.userData.pending = m?.state !== 'ready';
        this.root.add(this.setGroup);
      }
    }
    if (this.setGroup && !this.setGroup.userData.pending) {
      const row = rows.get(setId), def = Object.fromEntries((row?.data?.props || []).map(p => [p.id, p.on !== false]));
      const on = { ...def, ...(st.setProps || {}) };
      this.setGroup.traverse(o => {
        const u = o.userData || {};
        if (u.ds_prop && !u.ds_shell) {
          o.visible = on[u.ds_prop] !== false && !(u.ds_on && on[u.ds_on] === false);
          const moved = st.pieces?.[u.ds_prop] || (u.ds_on ? st.pieces?.[u.ds_on] : null);
          if (!u.base) u.base = { p: o.position.clone(), r: o.rotation.clone(), s: o.scale.clone() };
          o.position.copy(u.base.p); o.rotation.copy(u.base.r); o.scale.copy(u.base.s);
          if (moved && !(this.dragging && this.selected?.type === 'piece' && this.selected.id === u.ds_prop && o === this.gizmo.object)) {
            if (moved.at) o.position.add(new THREE.Vector3(...moved.at));
            if (moved.rot) o.rotation.z += moved.rot * D2R;
            if (moved.scale) o.scale.multiplyScalar(moved.scale);
          }
        }
      });
    }
    const inks = st.inks || {}, inkSig = JSON.stringify(st.inks || null) + !!noInk.set + (this.setGroup?.uuid || '') + !!this.setGroup?.userData.pending;
    if (inkSig !== this.inkSig && this.setGroup) {
      this.inkSig = inkSig;
      this.setGroup.traverse(o => { const u = o.userData; if (u.ds_prop) this.setInk(o, noInk.set ? 0 : u.ds_shell ? 100 : inks[u.ds_prop] ?? 100); });
    }
    if (this.view.inkK) this.view.inkK.value = (inks['@lead'] ?? 100) / 100;
    (this.view.actors || []).forEach((a, i) => { if (a.inkK) a.inkK.value = (inks['@costar' + i] ?? 100) / 100; });
    for (const who of [this.view, ...(this.view.actors || [])]) for (const o of who.objects) if (o.outline) o.outline.visible = !noInk.character && (who.inkK?.value ?? 1) > 0;
    const paintSig = (paint?.sig || '') + (this.setGroup?.uuid || '') + !!this.setGroup?.userData.pending;
    if (paintSig !== this.paintSig && this.setGroup) {
      this.paintSig = paintSig;
      const set = paint?.set;
      this.setGroup.traverse(o => { const u = o.userData; if (u.ds_prop) this.setFill(o, !set ? this.fill : u.ds_shell ? this.fillFor(set.wall, set) : this.fillFor(set.piece(u.ds_prop))); });
      this.view.scene.background.set(set ? set.ceiling : MUSTARD);
    }
    // items
    const want = [];
    items.forEach((it, i) => {
      const kind = it.id.split(':')[0], cat = rows.get(it.id)?.category;
      let rec = this.items[i];
      const sig = it.id + '|' + (it.text || '') + '|' + (it.stops || []).join(',') + '|' + (this.models.get(it.id)?.state || '');
      if (!rec || rec.sig !== sig) {
        if (rec) this.root.remove(rec.obj);
        rec = this.items[i] = { id: it.id, sig, obj: this.build(it, kind, cat, want), kind, cat };
        if (this.models.get(it.id)?.state === 'ready' && it.at && this.ctx.autoFit) { const bb = new THREE.Box3().setFromObject(rec.obj); this.ctx.autoFit(it, i, (bb.max.x - bb.min.x) / 2 * (it.scale?.[0] || 1)); }
        rec.obj.userData.item = i;
        rec.obj.traverse(o => { o.userData.item = i; });
        this.root.add(rec.obj);
      }
      const fill = paint?.item(it) || null;
      if (rec.fill !== fill) { rec.fill = fill; this.setFill(rec.obj, this.fillFor(fill)); }
      const ink = noInk.item?.(it) ? 0 : it.ink ?? 100;
      if (rec.ink !== ink) { rec.ink = ink; this.setInk(rec.obj, ink); }
      const end = it.until ?? (kind === 'react' ? it.frame + REACT_FRAMES : kind === 'story' && STORY_FRAMES[it.id.split(':')[1]] ? it.frame + STORY_FRAMES[it.id.split(':')[1]] : length);
      rec.obj.visible = f >= it.frame && f <= end;
      if (!(this.dragging && this.gizmo.object === rec.obj)) this.place(rec, it, f - it.frame);
    });
    while (this.items.length > items.length) { const r = this.items.pop(); this.root.remove(r.obj); }
    if (this.selected?.type === 'item' && !items[this.selected.index]) this.select(null);
    // the selected item was rebuilt (its model arrived): the gizmo moves to the new object
    else if (this.selected?.type === 'item' && this.gizmo.object && this.gizmo.object !== this.items[this.selected.index]?.obj) this.select(this.selected);
    if (this.selected?.type === 'piece' && this.gizmo.object && !this.setGroup?.getObjectById(this.gizmo.object.id)) this.select(null);
    if (want.length) this.want([...new Set(want)]);
    if (this.selected?.type === 'bunny' && !this.dragging) this.placeProxy();
    // the gizmo stays on its object, but hides while playing
    this.helper.visible = !!this.gizmo.object && !playing && (this.gizmo.object.visible !== false);
  }

  build(it, kind, cat, want) {
    const name = it.id.split(':')[1];
    if (cat === 'prop' || cat === 'scenery') {
      const m = this.models.get(it.id);
      if (!m) want.push(it.id);
      if (m?.state === 'ready') return this.doodle(m.scene);
      // until the model arrives: its picture, standing up
      return this.card(this.ctx.picture(it.id), 0.35, true);
    }
    if (kind === 'fx') return this.effect(name);
    if (kind === 'react') return this.textSprite(glyphOf(it.id), 0.26, { round: true });
    if (kind === 'story' || kind === 'text') {
      const t = { time_skip: it.text || 'Later', chat: it.text || 'hi', label: it.text || 'Label', journey: (it.stops || []).join(' → ') || 'Journey', end_screen: 'SUBSCRIBE', horror: 'Horror light' }[name] ?? it.text ?? 'Text';
      return this.textSprite(t, name === 'time_skip' || name === 'end_screen' ? 0.32 : 0.16, { box: name !== 'headline', bubble: name === 'chat', bold: name === 'headline' || name === 'time_skip' });
    }
    return new THREE.Group();   // sounds: nothing to see (the timeline shows them)
  }

  // where an item is this frame (held props ride on the hand; effects follow the camera's aim)
  place(rec, it, t) {
    const o = rec.obj, v = this.view;
    o.matrixAutoUpdate = true;
    if (it.hold && (rec.cat === 'prop')) {
      const bone = 'DEF-hand.' + (it.hold === 'L' ? 'L' : 'R'), b = v.rig.bones.get(bone);
      if (b) {
        const A = v.rig.A.get(bone) || new THREE.Matrix4();
        const head = b.tailV ? b.headV.clone().lerp(b.tailV, 0.6) : b.headV.clone();
        const hold = rec.holdM ||= (() => { const ori = this.ctx.rows().get(it.id)?.data?.hold?.orientation; const R = new THREE.Matrix4(); if (ori) R.set(ori[0][0], ori[0][1], ori[0][2], 0, ori[1][0], ori[1][1], ori[1][2], 0, ori[2][0], ori[2][1], ori[2][2], 0, 0, 0, 0, 1); return DS_TO_BLENDER.clone().multiply(R); })();
        v.group.updateMatrixWorld();
        const M = v.group.matrixWorld.clone().multiply(A).multiply(new THREE.Matrix4().makeTranslation(head.x, head.y, head.z)).multiply(hold);
        if (it.scale) M.multiply(new THREE.Matrix4().makeScale(...it.scale));
        M.decompose(o.position, o.quaternion, o.scale);
        return;
      }
    }
    if (rec.kind === 'fx') { const c = v.cam; o.position.set(c.tx, c.ty, 0); o.userData.tick?.(t, v); return; }
    if (rec.kind === 'react') { const p = v.headPoint(); o.position.set(p.x + 0.12, p.y, p.z + 0.32 + Math.min(1, t / 6) * 0.05); const s = 0.26 * (t < 4 ? 0.4 + 0.15 * t : 1); o.scale.set(s * o.userData.aspect, s, 1); return; }
    if (rec.kind === 'story' || rec.kind === 'text') {
      const name = it.id.split(':')[1];
      if (it.at && name !== 'time_skip' && name !== 'end_screen') { o.position.set(...it.at); return; }
      if (name === 'time_skip' || name === 'end_screen') {
        // a card filling the middle of the frame, just in front of the camera
        const cam = v.camera, d = 1.2;
        cam.updateMatrixWorld();
        o.position.copy(new THREE.Vector3(0, 0, -d).applyMatrix4(cam.matrixWorld));
        const h = 2 * d * Math.tan(cam.fov * D2R / 2) * 0.22;
        o.scale.set(h * o.userData.aspect, h, 1);
        return;
      }
      const p = v.headPoint();
      o.position.set(p.x + (name === 'chat' ? 0.45 : name === 'label' ? -0.35 : 0), p.y, p.z + (name === 'headline' ? 0.75 : 0.3));
      return;
    }
    const at = it.at || [0, 0, 0], rot = it.rot || [0, 0, 0], sc = it.scale || [1, 1, 1];
    o.position.set(at[0], at[1], at[2]);
    o.rotation.set(rot[0] * D2R, rot[1] * D2R, rot[2] * D2R, 'XYZ');
    o.scale.set(sc[0], sc[1], sc[2]);
  }

  // ---------------------------------------------------------------- drawn pieces
  card(url, h, standing) {
    const tex = new THREE.TextureLoader().load(url || '', t => { t.colorSpace = THREE.SRGBColorSpace; const a = t.image.width / t.image.height; g.children[0].scale.set(h * a, h, 1); });
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: true });
    const s = new THREE.Sprite(mat);
    s.scale.set(h, h, 1);
    if (standing) s.position.z = h / 2;
    const g = new THREE.Group(); g.add(s); g.userData.placeholder = true;
    return g;
  }
  textSprite(text, height, { round = false, box = false, bubble = false, bold = false } = {}) {
    const c = document.createElement('canvas'), g = c.getContext('2d'), px = 96, pad = round ? 36 : 28;
    g.font = `${bold ? 900 : 800} ${px}px Impact, 'Arial Black', system-ui, sans-serif`;
    const lines = String(text).split('|');
    const w = Math.max(...lines.map(l => g.measureText(l).width)) + pad * 2, hh = lines.length * px * 1.1 + pad * 2;
    c.width = Math.ceil(round ? Math.max(w, hh) : w); c.height = Math.ceil(round ? Math.max(w, hh) : hh);
    g.font = `${bold ? 900 : 800} ${px}px Impact, 'Arial Black', system-ui, sans-serif`;
    g.lineWidth = 9; g.strokeStyle = '#1F1F1D'; g.fillStyle = '#E0A64B'; g.lineJoin = 'round';
    if (round) { g.beginPath(); g.arc(c.width / 2, c.height / 2, c.width / 2 - 6, 0, 7); g.fill(); g.stroke(); }
    else if (box || bubble) { g.beginPath(); g.roundRect(5, 5, c.width - 10, c.height - 10, bubble ? 40 : 10); g.fill(); g.stroke(); }
    g.fillStyle = '#1F1F1D'; g.textAlign = 'center'; g.textBaseline = 'middle';
    lines.forEach((l, i) => g.fillText(l, c.width / 2, c.height / 2 + (i - (lines.length - 1) / 2) * px * 1.1));
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
    s.renderOrder = 10;
    s.userData.aspect = c.width / c.height;
    s.scale.set(height * s.userData.aspect, height, 1);
    return s;
  }
  effect(name) {
    const P = FX[name] || { kind: 'twinkle', n: 30, dot: 0.03 };
    const lines = !!P.len, n = P.n, pos = new Float32Array(n * (lines ? 6 : 3));
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    const obj = lines ? new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: INK })) : new THREE.Points(geo, new THREE.PointsMaterial({ color: INK, size: (P.dot || 0.02) * 1.6, sizeAttenuation: true }));
    obj.frustumCulled = false;
    const W = 3.2, H = 2.6, D = 2.2;
    obj.userData.tick = t => {
      const s = t / 30;
      for (let i = 0; i < n; i++) {
        const a = rnd(i + 1), b = rnd(i + 7.3), c = rnd(i + 13.1);
        let x = (a - 0.5) * W, y = (b - 0.5) * D - 0.4, z;
        if (P.kind === 'fall') { z = H - ((c * H + s * P.speed) % H); x += Math.sin(s * 2 + i) * (P.sway || 0); }
        else if (P.kind === 'rise') { z = (c * H * 0.6 + s * P.speed) % (H * 0.6); x = (a - 0.5) * 0.8 + Math.sin(s + i) * 0.1; }
        else if (P.kind === 'drift') { z = 0.2 + c * H * 0.7; x = ((a * W + s * P.speed) % W) - W / 2; }
        else if (P.kind === 'burst') { const r = Math.min(1, s * 1.4) * P.speed, th = a * 6.283, ph = (b - 0.2) * 3.14; x = Math.cos(th) * Math.cos(ph) * r; y = Math.sin(th) * Math.cos(ph) * r * 0.6 - 0.2; z = (P.high || 0.5) + Math.sin(ph) * r - s * s * 0.3; }
        else { z = 0.2 + c * H * 0.6; }
        if (lines) {
          const dx = P.kind === 'drift' ? P.len : 0, dz = P.kind === 'drift' ? 0 : P.len;
          pos.set([x, y, z, x - dx, y, z + dz], i * 6);
        } else pos.set([x, y, z], i * 3);
      }
      if (P.kind === 'twinkle') obj.material.size = (P.dot || 0.03) * (1.2 + Math.sin(s * 8) * 0.6);
      geo.attributes.position.needsUpdate = true;
    };
    obj.userData.tick(0);
    const g = new THREE.Group(); g.add(obj); g.userData.tick = obj.userData.tick;
    return g;
  }

  // ---------------------------------------------------------------- picking and the gizmo
  pick(nx, ny) {
    const ray = new THREE.Raycaster();
    ray.setFromCamera(new THREE.Vector2(nx * 2 - 1, 1 - ny * 2), this.view.camera);
    const targets = [];
    for (const r of this.items) if (r.obj.visible && r.kind !== 'fx') targets.push(r.obj);
    if (this.setGroup) targets.push(this.setGroup);
    const hits = ray.intersectObjects(targets, true).filter(h => h.object.visible && !h.object.userData.isInk && this.visibleUp(h.object));
    for (const h of hits) {
      let o = h.object;
      if (o.userData.item != null) return { type: 'item', index: o.userData.item, dist: h.distance };
      while (o && !o.userData.ds_prop) o = o.parent;
      if (o?.userData.ds_prop && !o.userData.ds_shell) return { type: 'piece', id: o.userData.ds_prop, obj: o, dist: h.distance };
    }
    return null;
  }
  visibleUp(o) { for (; o; o = o.parent) if (!o.visible) return false; return true; }
  select(sel, mode) {
    this.selected = sel;
    this.gizmo.detach();
    if (mode) this.mode = mode;
    if (!sel) return;
    let obj = null;
    if (sel.type === 'item') { const r = this.items[sel.index], it = this.ctx.items()[sel.index]; if (!r || it?.hold || r.kind === 'fx' || r.kind === 'react') return; obj = r.obj; }
    else if (sel.type === 'piece') { obj = sel.obj || this.pieceObj(sel.id); if (!obj) return; }
    else if (sel.type === 'bunny') { this.placeProxy(); obj = this.proxy; }
    const sn = !!this.ctx.snap?.();   // View › Snapping: 5 cm, 5°, 5 %
    this.gizmo.setTranslationSnap(sn ? 0.05 : null); this.gizmo.setRotationSnap(sn ? 5 * D2R : null); this.gizmo.setScaleSnap(sn ? 0.05 : null);
    this.gizmo.setMode(this.mode || 'translate');
    if (sel.type === 'bunny' && this.gizmo.mode === 'scale') this.gizmo.setMode('translate');
    this.gizmo.showX = this.gizmo.showY = this.gizmo.showZ = true;
    if (this.gizmo.mode === 'rotate' && sel.type !== 'item') { this.gizmo.showX = this.gizmo.showY = false; }   // pieces and the character turn about the floor's up axis
    this.gizmo.attach(obj);
  }
  setMode(mode) { this.mode = mode; if (this.selected) this.select(this.selected); }
  pieceObj(id) { let f = null; this.setGroup?.traverse(o => { if (!f && o.userData.ds_prop === id && !o.userData.ds_on) f = o; }); return f; }
  placeProxy() {
    const v = this.view, vals = v.values || {}, S = v.rig.S, U = 100 * 0.00205066345 * 490 * 0.4;
    this.proxy.position.set(Number(vals.bodyX || 0) / U * S, Number(vals.depth || 0) * S, -Number(vals.bodyY || 0) / U * S);
    this.proxy.rotation.set(0, 0, -(Number(vals.turn || 0)) * D2R);
    this.proxy.scale.set(1, 1, 1);
  }
  // while dragging: only the dragged object moves (the shot updates when the drag ends)
  live() {
    const sel = this.selected;
    if (sel?.type === 'bunny') {
      const v = this.view, S = v.rig.S, U = 100 * 0.00205066345 * 490 * 0.4, p = this.proxy.position;
      this.ctx.setBunny({ bodyX: p.x / S * U, depth: p.y / S, bodyY: -p.z / S * U, turn: -this.proxy.rotation.z / D2R });
    }
    if (sel?.type === 'piece') {
      // things standing on the piece follow it
      const o = this.gizmo.object, b = o.userData.base;
      const d = o.position.clone().sub(b.p);
      this.setGroup.traverse(x => { if (x.userData.ds_on === sel.id && x.userData.base) x.position.copy(x.userData.base.p).add(d); });
    }
  }
  commit() {
    const sel = this.selected, o = this.gizmo.object;
    if (!sel || !o) return;
    const r3 = v => +v.toFixed(3);
    if (sel.type === 'item') {
      this.ctx.editItem(sel.index, { at: o.position.toArray().map(r3), rot: [o.rotation.x, o.rotation.y, o.rotation.z].map(a => Math.round(a / D2R)), scale: o.scale.toArray().map(r3) }, null);
    } else if (sel.type === 'piece') {
      const b = o.userData.base;
      this.ctx.editPiece(sel.id, { at: o.position.clone().sub(b.p).toArray().map(r3), rot: Math.round((o.rotation.z - b.r.z) / D2R), scale: r3(o.scale.x / b.s.x) });
    } else if (sel.type === 'bunny') this.ctx.setBunny(null, true);
  }
}
