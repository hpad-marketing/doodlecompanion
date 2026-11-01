// Light and shadow in the live 3D view: one set of bands on everything, Bunny, co-stars, set and
// props, so the Stage shows what Blender renders (lib/lights.py uses the same numbers). Off by
// default: the doodle rule is flat fills and no shadows until the Shadows button or a 3-point
// light is switched on.
//   stage.shadows   the key casts shadows, a sun when there is no 3-point light
//   stage.lighting  { preset, target, turn, height, distance, key, fill, back, keyA, fillA, backA, amb, shade, soft }
import * as THREE from 'three';

const D2R = Math.PI / 180;
export const BAND_MID = 0.55, BAND_DARK = 0.22;   // light levels under which a surface steps darker (lib/lights.py has the same)
const SUN_ROT = { day: [50, 0, -35], golden: [74, 0, -58] }, SUN_ENERGY = { day: 3, golden: 3, night: 0 };
const AMBIENT = 0.15, SHADE = 0.32, MAP = 2048;

// a = degrees round the target, seen from above: 0 is the camera's side at turn 0, minus is camera left
export const LIGHT_PRESETS = [
  ['classic', 'Classic', 'Key on one side, soft fill on the other, a back light to lift the shape off the set',
    { key: 1, fill: 0.2, back: 0.4, keyA: -35, fillA: 45, backA: 145, height: 1.9, distance: 2.6, soft: 0.35, shade: 0.32 }],
  ['soft', 'Soft', 'Low contrast: nearly even, a gentle step on the far side',
    { key: 0.8, fill: 0.3, back: 0.3, keyA: -25, fillA: 40, backA: 160, height: 1.7, distance: 3, soft: 0.8, shade: 0.22 }],
  ['dramatic', 'Dramatic', 'Hard side light and almost no fill: half the face falls dark',
    { key: 1.3, fill: 0.08, back: 0.4, keyA: -70, fillA: 60, backA: 150, height: 1.6, distance: 2.4, soft: 0.15, shade: 0.5 }],
  ['rim', 'Rim', 'The light is behind: dark in the middle, bright round the edges',
    { key: 0.3, fill: 0.15, back: 1.8, keyA: -30, fillA: 40, backA: 165, height: 1.8, distance: 2.4, soft: 0.3, shade: 0.5 }],
  ['top', 'Top', 'From above, like a street lamp or a stage spot',
    { key: 1.2, fill: 0.12, back: 0.3, keyA: -10, fillA: 90, backA: 170, height: 3.4, distance: 0.9, soft: 0.3, shade: 0.45 }],
];

export const LIT = {
  litShade: { value: 0 }, litP: { value: [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()] }, litI: { value: [0, 0, 0] }, litR: { value: [1, 1, 1] },
  litAmb: { value: AMBIENT }, litCast: { value: 0 }, litMap: { value: null }, litMat: { value: new THREE.Matrix4() }, litInk: { value: new THREE.Color('#1F1F1D') },
};

export const litPars = `uniform float litShade, litAmb, litCast; uniform vec3 litP[3]; uniform float litI[3]; uniform float litR[3]; uniform sampler2D litMap; uniform mat4 litMat; uniform vec3 litInk;
float litBand(vec3 N, vec3 P){
  if (litShade <= 0.0) return 0.0;
  float seen = 1.0;
  if (litCast > 0.5) {
    vec4 q = litMat * vec4(P + N * 0.012, 1.0); vec3 s = q.xyz / q.w * 0.5 + 0.5;
    if (s.x > 0.0 && s.x < 1.0 && s.y > 0.0 && s.y < 1.0 && s.z < 1.0 && s.z > texture2D(litMap, s.xy).r) seen = 0.0;
  }
  float v = litAmb;
  for (int i = 0; i < 3; i++) {
    vec3 d = litP[i] - P; float r = length(d);
    float a = litI[i] * min(2.5, litR[i] * litR[i] / (r * r)) * max(0.0, dot(N, d / r));
    v += i == 0 ? a * seen : a;
  }
  return v < ${BAND_DARK.toFixed(2)} ? litShade : (v < ${BAND_MID.toFixed(2)} ? litShade * 0.45 : 0.0);
}`;

// the same bands on a flat MeshBasicMaterial (Bunny's body): colours and the onion skin keep working
export function litBasic(mat) {
  mat.onBeforeCompile = s => {
    Object.assign(s.uniforms, LIT);
    s.vertexShader = s.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vLitN; varying vec3 vLitP;')
      .replace('#include <project_vertex>', '#include <project_vertex>\nvLitN = normalize(mat3(modelMatrix) * normal); vLitP = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    s.fragmentShader = s.fragmentShader.replace('#include <common>', '#include <common>\nvarying vec3 vLitN; varying vec3 vLitP;\n' + litPars)
      .replace('#include <opaque_fragment>', 'outgoingLight = mix(outgoingLight, litInk, litBand(normalize(gl_FrontFacing ? vLitN : -vLitN), vLitP));\n#include <opaque_fragment>');
  };
  return mat;
}

// the sun the render uses when there is no 3-point light: pointing direction from Blender's Euler
function sunOf(st) {
  const rot = st.sun?.rot || SUN_ROT[st.time] || SUN_ROT.day;
  const dir = new THREE.Vector3(0, 0, 1).applyEuler(new THREE.Euler(rot[0] * D2R, rot[1] * D2R, rot[2] * D2R, 'ZYX'));
  return { dir, level: (st.sun?.energy ?? SUN_ENERGY[st.time] ?? SUN_ENERGY.day) / Math.PI };
}

// where the 3-point light is centred this frame (at waist height, as Blender's target)
export function lightTarget(view, stage, st) {
  const t = String(st.lighting?.target ?? 'lead'), m = /^(costar|item):(\d+)$/.exec(t);
  if (m?.[1] === 'item') { const o = stage?.items?.[+m[2]]?.obj; if (o) return o.position.clone().setZ(Math.max(0.3, o.position.z)); }
  const who = m?.[1] === 'costar' ? view.actors?.[+m[2]] || view : view;
  return who.headPoint().setZ(0.5);
}

export const lightPos = (T, L, a) => new THREE.Vector3(T.x + L.distance * Math.sin((L.turn + a) * D2R), T.y - L.distance * Math.cos((L.turn + a) * D2R), L.height);

// every frame: the bands and the light positions from the stage
export function updateLit(view, stage, st) {
  const L = st.lighting, cast = !!(st.shadows || st.halftone), on = cast || !!L;
  LIT.litShade.value = on ? (L?.shade ?? SHADE) : 0;
  LIT.litCast.value = on && cast ? 1 : 0;
  if (!on) return;
  LIT.litAmb.value = L?.amb ?? AMBIENT;
  if (L) {
    const T = lightTarget(view, stage, st);
    [[L.keyA, L.key], [L.fillA, L.fill], [L.backA, L.back]].forEach(([a, level], i) => {
      const p = lightPos(T, L, a); LIT.litP.value[i].copy(p); LIT.litI.value[i] = level; LIT.litR.value[i] = p.distanceTo(T);
    });
    view.litAim = T;
  } else {
    const { dir, level } = sunOf(st);
    view.litAim = new THREE.Vector3(0, 0, 0.5);
    LIT.litP.value[0].copy(view.litAim).addScaledVector(dir, 40); LIT.litI.value[0] = level; LIT.litR.value[0] = 40;
    LIT.litI.value[1] = LIT.litI.value[2] = 0;
  }
}

// what the key sees, for cast shadows: every solid body on layer 1 (no outlines, no room shell)
let rt = null, keyCam = null, depthOnly = null;
export function shadowPass(view) {
  if (!LIT.litCast.value || !LIT.litI.value[0]) return;
  if (!rt) {
    rt = new THREE.WebGLRenderTarget(MAP, MAP, { depthTexture: new THREE.DepthTexture(MAP, MAP), minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
    keyCam = new THREE.PerspectiveCamera(50, 1, 0.1, 50); keyCam.layers.set(1); keyCam.up.set(0, 0, 1);
    depthOnly = new THREE.MeshBasicMaterial({ colorWrite: false, side: THREE.DoubleSide });
    LIT.litMap.value = rt.depthTexture;
  }
  const from = LIT.litP.value[0], aim = view.litAim, r = from.distanceTo(aim);
  keyCam.position.copy(from); keyCam.lookAt(aim);
  keyCam.fov = Math.min(140, 2 * Math.atan(4.5 / r) / D2R); keyCam.near = Math.max(0.05, r - 9); keyCam.far = r + 9;
  keyCam.updateProjectionMatrix(); keyCam.updateMatrixWorld();
  LIT.litMat.value.multiplyMatrices(keyCam.projectionMatrix, keyCam.matrixWorldInverse);
  const R = view.renderer, was = R.getRenderTarget(), over = view.scene.overrideMaterial, bg = view.scene.background;
  view.scene.overrideMaterial = depthOnly; view.scene.background = null;
  R.setRenderTarget(rt); R.clear(); R.render(view.scene, keyCam);
  R.setRenderTarget(was); view.scene.overrideMaterial = over; view.scene.background = bg;
}
