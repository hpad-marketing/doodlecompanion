// Scene drawings in the live 3D view: the same lines Blender draws (host/blender/lib/drawings.py),
// standing in the world, drawing on and boiling at the playhead, one ink wide.
import * as THREE from 'three';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { COLOURS, BOIL_PX_1920, WAVE_PX_1920, stateAt, local, partial, boil, hash } from './drawings.js';

export class DrawingStage {
  constructor(view) {
    this.view = view;
    this.root = new THREE.Group(); this.root.name = 'drawings';
    view.scene.add(this.root);
    this.mats = Object.fromEntries(Object.entries(COLOURS).map(([k, c]) => {
      const m = new LineMaterial({ color: new THREE.Color(c).getHex(), linewidth: 4, worldUnits: false });
      m.polygonOffset = true; m.polygonOffsetFactor = -1; m.polygonOffsetUnits = -2;
      return [k, m];
    }));
    this.recs = new Map();
    const U = view.outlineUniforms;
    this.inkSync = () => { for (const m of Object.values(this.mats)) { m.resolution.copy(U.res.value); m.linewidth = U.inkPx.value; } };
  }
  // drawings: the shot's drawings; t: frame
  sync(drawings = [], t = 0) {
    const live = new Set();
    for (const d of drawings) {
      if (d.layer !== 'scene' || !d.world) continue;
      live.add(d.id);
      let rec = this.recs.get(d.id);
      const key = JSON.stringify([d.world, d.rot, d.aspect, d.strokes.length, d.colour]);
      if (!rec || rec.key !== key) {
        if (rec) this.root.remove(rec.obj);
        const g = new LineSegmentsGeometry(), obj = new LineSegments2(g, this.mats[d.colour] || this.mats.ink);
        obj.onBeforeRender = this.inkSync; obj.raycast = () => {}; obj.frustumCulled = false;
        rec = { key, obj, sig: null, base: local(d) };
        this.root.add(obj); this.recs.set(d.id, rec);
      }
      const st = stateAt(d, t);
      rec.obj.visible = !!st;
      if (!st) continue;
      const sig = `${st.p.toFixed(4)}:${st.v}:${d.noise}`;
      if (sig === rec.sig) continue;
      rec.sig = sig;
      // local units are drawing heights; the boil is in px on a 1920 frame, so per drawing height
      const per = 1 / Math.max(0.02, d.size || 0.3) / 1920;
      const pts = boil(partial(rec.base, st.p), st.v, d.noise * BOIL_PX_1920 * per, hash(d.id), WAVE_PX_1920 * per);
      const { at, r, u, h } = d.world, arr = [];
      const W = ([x, y]) => [at[0] + (r[0] * x + u[0] * y) * h, at[1] + (r[1] * x + u[1] * y) * h, at[2] + (r[2] * x + u[2] * y) * h];
      for (const s of pts) for (let j = 1; j < s.length; j++) arr.push(...W(s[j - 1]), ...W(s[j]));
      if (!arr.length) { rec.obj.visible = false; continue; }
      rec.obj.geometry.setPositions(arr);
    }
    for (const [id, rec] of this.recs) if (!live.has(id)) { this.root.remove(rec.obj); rec.obj.geometry.dispose(); this.recs.delete(id); }
  }
}
