// Live 3D viewport: Bunny in the Doodle Studio look (flat mustard and ink,
// screen-constant outline, the face drawn on the head) with a real camera.
// Final frames come from Blender; this is the fast, interactive preview.
import * as THREE from 'three';
import { BunnyRig, decodeMesh, subdivide } from './rig.js';

export const INK = new THREE.Color('#1F1F1D');
export const MUSTARD = new THREE.Color('#E0A64B');
const INK_PX_1920 = 12.73;          // Blender's outline width on a 1920 px tall frame
const DEPTH_BIAS = 4.5;              // outline pushed away from the camera by this many ink widths

const outlineVS = `
uniform float inkPx; uniform vec2 res; uniform float bias; uniform float ortho; uniform float worldPerPxOrtho;
void main(){
  vec4 vp = modelViewMatrix * vec4(position, 1.0);
  vec3 vn = normalize(normalMatrix * normal);
  float wpp = ortho > 0.5 ? worldPerPxOrtho : (2.0 * -vp.z / projectionMatrix[1][1]) / res.y;
  vec3 away = ortho > 0.5 ? vec3(0.0, 0.0, -1.0) : normalize(vp.xyz);
  vp.xyz += vn * inkPx * wpp + away * bias * inkPx * wpp;
  gl_Position = projectionMatrix * vp;
}`;
const outlineFS = `uniform vec3 color; void main(){ gl_FragColor = vec4(color, 1.0);
#include <colorspace_fragment>
}`;

const headVS = `
attribute vec3 restPos; attribute vec3 restNrm; attribute float faceMask;
varying vec3 vRest; varying float vFront;
void main(){
  vRest = restPos;
  vFront = faceMask * smoothstep(0.02, 0.25, -restNrm.y);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;
const headFS = `
uniform sampler2D face; uniform vec4 box; uniform vec3 base; uniform vec3 ink;
varying vec3 vRest; varying float vFront;
void main(){
  vec2 uv = vec2((vRest.x - box.x) / (box.z - box.x), (vRest.z - box.y) / (box.w - box.y));
  float a = 0.0;
  if (vFront > 0.0 && uv.x > 0.0 && uv.x < 1.0 && uv.y > 0.0 && uv.y < 1.0) a = texture2D(face, uv).a * step(0.5, vFront);
  gl_FragColor = vec4(mix(base, ink, a), 1.0);
#include <colorspace_fragment>
}`;

export class Viewport {
  constructor(canvas, data) {
    this.canvas = canvas;
    this.data = data;
    this.rig = new BunnyRig(data);
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.scene = new THREE.Scene();
    this.scene.background = MUSTARD.clone();
    this.camera = new THREE.PerspectiveCamera(30, 9 / 16, 0.01, 200);
    this.camera.up.set(0, 0, 1);
    this.cam = { yaw: 0, pitch: 4, dist: 3.0, lens: 50, roll: 0, tx: 0, ty: 0, tz: 0.52 };
    this.aspect = 9 / 16;
    this.inkScale = 1;
    this.faceState = { expression: 0, gaze: 0, mouth: 0, blink: 0 };
    this.meshes = data.meshes.map(decodeMesh);
    this.objects = [];
    this.outlineUniforms = { inkPx: { value: 8 }, res: { value: new THREE.Vector2(1, 1) }, bias: { value: DEPTH_BIAS },
      ortho: { value: 0 }, worldPerPxOrtho: { value: 0.001 }, color: { value: INK.clone() } };
    this.buildFace();
    this.buildBunny();
    this.buildStage();
    this.pose({});
  }

  // ---------- Bunny
  buildBunny() {
    this.group = new THREE.Group();
    this.scene.add(this.group);
    const headBone = this.data.skinBones.indexOf('head');
    // the Frog's eyes sit on its rigid eye bumps, which the ear bones carry
    const faceBones = new Set([headBone, ...(this.data.ear_width_lock ? this.data.skinBones.flatMap((n, i) => /^DEF-ear/.test(n) ? [i] : []) : [])]);
    for (const m of this.meshes) {
      const g = new THREE.BufferGeometry();
      const pos = subdivide(m, m.cage);
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3).setUsage(THREE.DynamicDrawUsage));
      g.setIndex(new THREE.BufferAttribute(m.index, 1));
      // per-vertex colour from the part's material slots
      const col = new Float32Array(m.count * 3);
      for (let i = 0; i < m.count; i++) {
        const c = (m.materials[m.material[i]] || m.materials[0] || '').includes('ink') ? INK : MUSTARD;
        col[3 * i] = c.r; col[3 * i + 1] = c.g; col[3 * i + 2] = c.b;
      }
      g.setAttribute('color', new THREE.BufferAttribute(col, 3));
      g.computeVertexNormals();
      let mat;
      if (m.name === 'BUNNY_head') {
        g.setAttribute('restPos', new THREE.BufferAttribute(pos.slice(), 3));
        g.setAttribute('restNrm', new THREE.BufferAttribute(g.getAttribute('normal').array.slice(), 3));
        // face only on the part of the head the head bone owns (never on the ears)
        const cageMask = new Float32Array(m.cageCount * 3);
        for (let v = 0; v < m.cageCount; v++) {
          let w = 0;
          for (let k = 0; k < 4; k++) if (faceBones.has(m.skinIndex[4 * v + k])) w += m.skinWeight[4 * v + k];
          cageMask[3 * v] = w;
        }
        const sub = subdivide(m, cageMask);
        const mask = new Float32Array(m.count);
        for (let i = 0; i < m.count; i++) mask[i] = sub[3 * i] > 0.98 ? 1 : 0;
        g.setAttribute('faceMask', new THREE.BufferAttribute(mask, 1));
        mat = new THREE.ShaderMaterial({ vertexShader: headVS, fragmentShader: headFS,
          uniforms: { face: { value: this.faceTex }, box: { value: this.faceBox }, base: { value: MUSTARD.clone() }, ink: { value: INK.clone() } } });
      } else {
        mat = new THREE.MeshBasicMaterial({ vertexColors: true });
      }
      const mesh = new THREE.Mesh(g, mat);
      mesh.frustumCulled = false;
      this.group.add(mesh);
      let outline = null;
      if (m.outline) {
        outline = new THREE.Mesh(g, new THREE.ShaderMaterial({ vertexShader: outlineVS, fragmentShader: outlineFS,
          uniforms: this.outlineUniforms, side: THREE.BackSide }));
        outline.frustumCulled = false;
        this.group.add(outline);
      }
      this.objects.push({ m, g, mesh, outline, buf: pos });
    }
  }

  // Bunny, the Koala or the Frog: same rig code, their own rest data, meshes and faces
  setCharacter(data) {
    if (data === this.data) return;
    this.scene.remove(this.group);
    for (const o of this.objects) { o.g.dispose(); o.mesh.material.dispose(); o.outline?.material.dispose(); }
    this.faceTex.dispose();
    this.data = data;
    this.rig = new BunnyRig(data);
    this.meshes = data.meshes.map(decodeMesh);
    this.objects = [];
    this._faceInk = 0;
    this.faceState = { expression: 0, gaze: 0, mouth: 0, blink: 0 };
    this.buildFace();
    this.buildBunny();
    this.grid.position.z = data.floor_z || 0;
    this.pose(this.values || {});
  }

  pose(values) {
    this.values = values;
    this.rig.pose(values);
    for (const o of this.objects) {
      this.rig.deform(o.m, o.buf);
      o.g.attributes.position.needsUpdate = true;
      o.g.computeVertexNormals();
    }
    const fs = { expression: values.expression ?? 0, gaze: values.gaze ?? 0, mouth: values.mouth ?? 0, blink: values.blink ?? 0 };
    if (Object.keys(fs).some(k => Math.round(fs[k]) !== this.faceState[k])) {
      for (const k in fs) this.faceState[k] = Math.round(fs[k]);
      this.drawFace();
    }
  }

  // ---------- face: Doodle Studio's own drawings, in the head's front plane
  buildFace() {
    const F = this.data.face, S = this.data.S;
    let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
    for (const it of F.items) for (const p of (it.pts || it.outer)) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); z0 = Math.min(z0, p[1]); z1 = Math.max(z1, p[1]); }
    const pad = 0.6;
    x0 -= pad; x1 += pad; z0 -= pad; z1 += pad;
    this.faceBoxDS = [x0, z0, x1, z1];
    this.faceBox = new THREE.Vector4(x0 * S, z0 * S, x1 * S, z1 * S);
    this.faceCanvas = document.createElement('canvas');
    this.faceCanvas.width = 2048;
    this.faceCanvas.height = Math.round(2048 * (z1 - z0) / (x1 - x0));
    this.faceTex = new THREE.CanvasTexture(this.faceCanvas);
    this.faceTex.anisotropy = 4;
    this.facePx = 0.1132;  // stroke width in Doodle Studio units (11.32 source px)
  }

  drawFace() {
    const F = this.data.face, c = this.faceCanvas, ctx = c.getContext('2d');
    const [x0, z0, x1, z1] = this.faceBoxDS;
    const sx = c.width / (x1 - x0), sz = c.height / (z1 - z0);
    const X = x => (x - x0) * sx, Z = z => c.height - (z - z0) * sz;   // canvas y runs down; the texture is flipped back by the sampler
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.fillStyle = ctx.strokeStyle = '#1F1F1D';
    ctx.lineCap = ctx.lineJoin = 'round';
    const { expression: e, gaze, mouth, blink } = this.faceState;
    const eyesFace = blink > 0 ? 32 + blink : e;
    const off = F.speech_offsets_px[e] || [0, 0];
    const dx = off[0] * 0.01, dz = -off[1] * 0.01;
    for (const it of F.items) {
      const role = it.role;
      let keep = false, sp = false;
      if (role === 'eyes') keep = it.face === eyesFace && (it.gaze === -1 || it.gaze === gaze);
      else if (role === 'mouth') keep = mouth === 0 && it.face === e;
      else if (role === 'speech') { keep = mouth > 0 && it.speech === mouth; sp = true; }
      if (!keep) continue;
      const ox = sp ? dx : 0, oz = sp ? dz : 0;
      const path = new Path2D();
      const loop = (pts, close) => { pts.forEach((p, i) => (i ? path.lineTo : path.moveTo).call(path, X(p[0] + ox), Z(p[1] + oz))); if (close) path.closePath(); };
      if (it.kind === 'fill') { loop(it.outer, true); for (const h of it.holes || []) loop(h, true); ctx.fill(path, 'evenodd'); }
      else { loop(it.pts, it.closed); ctx.lineWidth = (it.width || 11.32) * 0.01 * sx * this.faceInkScale(); ctx.stroke(path); }
    }
    this.faceTex.needsUpdate = true;
  }

  // face strokes keep the outline's screen width, as Blender draws them
  faceInkScale() {
    return this._faceInk || 1;
  }

  // ---------- stage: floor grid for orientation (viewport only)
  buildStage() {
    const grid = new THREE.GridHelper(8, 32, 0x1F1F1D, 0x1F1F1D);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = this.data.floor_z || 0;
    grid.material.transparent = true;
    grid.material.opacity = 0.12;
    this.grid = grid;
    this.scene.add(grid);
  }

  // ---------- camera: same model as the Blender bridge (yaw, pitch, dist, lens, roll, target)
  setCamera(c) {
    Object.assign(this.cam, c);
    const { yaw, pitch, dist, lens, roll, tx, ty, tz } = this.cam;
    const r = Math.PI / 180;
    const T = new THREE.Vector3(tx, ty, tz);
    const d = new THREE.Vector3(Math.sin(yaw * r) * Math.cos(pitch * r), -Math.cos(yaw * r) * Math.cos(pitch * r), Math.sin(pitch * r));
    const cam = this.camera;
    cam.position.copy(T).addScaledVector(d, dist);
    cam.up.set(0, 0, 1);
    cam.lookAt(T);
    cam.rotateZ(roll * r);
    // Blender sensor fit AUTO on a portrait frame: the 36 mm sensor spans the long side (height)
    const longSide = 36;
    const vfov = 2 * Math.atan(longSide / 2 / lens) / r;
    cam.fov = this.aspect < 1 ? vfov : 2 * Math.atan(Math.tan(vfov * r / 2) / this.aspect) / r;
    cam.aspect = this.aspect;
    cam.updateProjectionMatrix();
  }

  resize(w, h) {
    this.renderer.setSize(w, h, false);
    this.aspect = w / h;
    this.size = [w, h];
    this.setCamera({});
  }

  render() {
    const [w, h] = this.size || [this.canvas.width, this.canvas.height];
    const pr = this.renderer.getPixelRatio();
    this.outlineUniforms.res.value.set(w * pr, h * pr);
    this.outlineUniforms.inkPx.value = INK_PX_1920 * (h * pr / 1920) * this.inkScale;
    // face strokes: same screen width as the outline at the head's distance
    const headDist = this.camera.position.distanceTo(new THREE.Vector3(0, -0.3, 0.55));
    const wpp = 2 * headDist * Math.tan(this.camera.fov * Math.PI / 360) / (h * pr);
    const want = (this.outlineUniforms.inkPx.value * wpp) / (0.1132 * this.data.S);
    if (!this._faceInk || Math.abs(want / this._faceInk - 1) > 0.08) { this._faceInk = want; this.drawFace(); }
    this.renderer.render(this.scene, this.camera);
  }
}
