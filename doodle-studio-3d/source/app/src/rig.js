// Bunny's rig for the live viewport. Reproduces the Blender rig's FK from the
// exported rest data: every Doodle Studio control rotates its bone about the
// world axes of the rest pose, around the bone's pivot, in list order, clamped
// to the control's range. Skinning matrices are rest-space deltas (pose * rest^-1).
import { Matrix4, Vector3, Quaternion } from 'three';

export const TRACK_IDS = {
  'TURN 360': 'turn', 'VIEW Above': 'view', 'HEAD Yaw': 'headYaw', 'HEAD Nod': 'headNod', 'HEAD Tilt': 'rot',
  'BODY Tilt': 'bodyTilt', 'TORSO Bow': 'torsoBow', 'TORSO Twist': 'torsoTwist',
  'ARM L Raise': 'armL', 'ARM L Forward': 'armLForward', 'ELBOW L Bend': 'elbowL', 'WRIST L Roll': 'wristL',
  'LEG L Lift': 'legL', 'LEG L Out': 'legLOut', 'KNEE L Bend': 'kneeL', 'FOOT L Roll': 'footL',
  'ARM R Raise': 'armR', 'ARM R Forward': 'armRForward', 'ELBOW R Bend': 'elbowR', 'WRIST R Roll': 'wristR',
  'LEG R Lift': 'legR', 'LEG R Out': 'legROut', 'KNEE R Bend': 'kneeR', 'FOOT R Roll': 'footR',
  'EAR L Fold': 'earLFold', 'EAR L Forward': 'earLForward', 'EAR R Fold': 'earRFold', 'EAR R Forward': 'earRForward',
  'STYLE Line boil': 'lineBoil', 'BODY Breath': 'breath', 'FACE Speech mode': 'speechMode',
};

// Doodle Studio native bone -> the bone it turns here
const OWNER_BONE = {
  ROOT: 'body', TORSO: 'torso', HEAD: 'head', 'EAR.L': 'ear.L', 'EAR.R': 'ear.R',
  'UPPER_ARM.L': 'upper_arm_fk.L', 'FOREARM.L': 'forearm_fk.L', 'WRIST.L': 'hand_fk.L',
  'UPPER_ARM.R': 'upper_arm_fk.R', 'FOREARM.R': 'forearm_fk.R', 'WRIST.R': 'hand_fk.R',
  'THIGH.L': 'thigh_fk.L', 'SHIN.L': 'shin_fk.L', 'ANKLE.L': 'foot_fk.L',
  'THIGH.R': 'thigh_fk.R', 'SHIN.R': 'shin_fk.R', 'ANKLE.R': 'foot_fk.R',
};

// deform bones that copy an FK control's motion (sockets in the Blender rig)
const FOLLOWS = {};
for (const s of ['L', 'R']) {
  for (const [d, c] of [['upper_arm', 'upper_arm_fk'], ['forearm', 'forearm_fk'], ['hand', 'hand_fk'],
    ['thigh', 'thigh_fk'], ['shin', 'shin_fk'], ['foot', 'foot_fk']]) FOLLOWS[`DEF-${d}.${s}`] = `${c}.${s}`;
}

const STAGE_BODY_UNIT = 100 * 0.00205066345 * 490 * 0.4;
const AXIS = { 1: new Vector3(1, 0, 0), 2: new Vector3(0, 1, 0), 3: new Vector3(0, 0, 1) };
const RAD = Math.PI / 180;

const b64 = (s, T) => {
  const bin = typeof atob === 'function' ? Uint8Array.from(atob(s), c => c.charCodeAt(0)) : new Uint8Array(Buffer.from(s, 'base64'));
  return new T(bin.buffer, bin.byteOffset, bin.byteLength / T.BYTES_PER_ELEMENT);
};

export function decodeMesh(m) {
  return {
    ...m,
    cage: b64(m.cage, Float32Array), skinIndex: b64(m.skinIndex, Uint16Array), skinWeight: b64(m.skinWeight, Float32Array),
    index: b64(m.index, Uint32Array), material: b64(m.material, Uint8Array),
    stencilOffset: b64(m.stencilOffset, Uint32Array), stencilIndex: b64(m.stencilIndex, Uint32Array), stencilWeight: b64(m.stencilWeight, Float32Array),
    morphs: Object.fromEntries(Object.entries(m.morphs || {}).map(([k, v]) => [k, b64(v, Float32Array)])),
  };
}

// Blender's subdivision as a fixed linear map from cage to surface
export function subdivide(mesh, cage, out = new Float32Array(mesh.count * 3)) {
  const O = mesh.stencilOffset, I = mesh.stencilIndex, W = mesh.stencilWeight;
  for (let i = 0; i < mesh.count; i++) {
    let x = 0, y = 0, z = 0;
    for (let k = O[i]; k < O[i + 1]; k++) {
      const j = 3 * I[k], w = W[k];
      x += w * cage[j]; y += w * cage[j + 1]; z += w * cage[j + 2];
    }
    out[3 * i] = x; out[3 * i + 1] = y; out[3 * i + 2] = z;
  }
  return out;
}

export class BunnyRig {
  constructor(data) {
    this.data = data;
    this.S = data.S;
    this.bones = new Map(data.bones.map(b => [b.name, {
      ...b, restM: new Matrix4().fromArray(b.rest), headV: new Vector3(...b.head), tailV: new Vector3(...b.tail),
    }]));
    this.controls = data.controls.map(c => ({ ...c, id: TRACK_IDS[c.name] }));
    this.byOwner = {};
    for (const c of this.controls) if (c.owner) (this.byOwner[c.owner] ||= []).push(c);
    this.skinBones = data.skinBones;
    this.earCurl = data.ear_curl ?? 0.6;
    this.A = new Map();          // bone -> rest-space delta matrix
    this.extra = new Map();      // bone -> extra local delta (springs), applied about the bone head
    this.skin = new Float32Array(this.skinBones.length * 16);
  }

  range(id) {
    const c = this.controls.find(c => c.id === id);
    return c ? [c.min, c.max] : null;
  }

  // world-axis rotation Doodle Studio applies at a native bone
  dsRotation(owner, values) {
    const M = new Matrix4();
    for (const c of this.byOwner[owner] || []) {
      let deg = Number(values[c.id] ?? 0);
      deg = Math.max(c.min, Math.min(c.max, deg));
      if (deg) M.multiply(new Matrix4().makeRotationAxis(AXIS[c.axis], deg * c.sign * RAD));
    }
    return M;
  }

  about(p, R) {
    return new Matrix4().makeTranslation(p.x, p.y, p.z).multiply(R).multiply(new Matrix4().makeTranslation(-p.x, -p.y, -p.z));
  }

  pose(values = {}) {
    const A = this.A;
    A.clear();
    const local = new Map();
    for (const [owner, bone] of Object.entries(OWNER_BONE)) local.set(bone, this.dsRotation(owner, values));
    // whole-character turn, placement and scale (root)
    const rootB = this.bones.get('root');
    const turn = Number(values.turn ?? 0), s = Number(values.s ?? 1) || 1;
    const off = new Vector3(Number(values.bodyX ?? 0) / STAGE_BODY_UNIT, Number(values.depth ?? 0), -Number(values.bodyY ?? 0) / STAGE_BODY_UNIT).multiplyScalar(this.S);
    const rootR = new Matrix4().makeRotationZ(turn * RAD).multiply(new Matrix4().makeScale(s, s, s));
    local.set('root', new Matrix4().makeTranslation(off.x, off.y, off.z).multiply(this.about(rootB.headV, rootR)));
    local.set('body_rot', new Matrix4().makeRotationY(Number(values.bodyRot ?? 0) * RAD));
    // breathing lifts the hoodie mass
    const breath = Math.max(0, Math.min(1, Number(values.breath ?? 0) / 90));
    const torsoT = new Vector3(0, -0.015 * breath, 0.07 * breath).multiplyScalar(this.S);
    // the ear tip carries part of the root's fold, for a smooth curl
    for (const side of ['L', 'R']) {
      const q = new Quaternion().setFromRotationMatrix(local.get(`ear.${side}`));
      const curl = new Quaternion().slerp(q, this.earCurl);
      local.set(`ear_tip.${side}`, new Matrix4().makeRotationFromQuaternion(curl));
    }
    const resolve = name => {
      if (A.has(name)) return A.get(name);
      const b = this.bones.get(name);
      if (!b) return new Matrix4();
      let M;
      if (FOLLOWS[name]) M = resolve(FOLLOWS[name]).clone();
      else {
        const parent = b.parent ? resolve(b.parent) : new Matrix4();
        M = parent.clone();
        if (name === 'root') M.multiply(local.get('root'));
        else {
          if (name === 'torso') M.multiply(new Matrix4().makeTranslation(torsoT.x, torsoT.y, torsoT.z));
          const R = local.get(name);
          if (R) M.multiply(this.about(b.headV, R));
        }
        const ex = this.extra.get(name);
        if (ex) M.multiply(this.about(b.headV, ex));
      }
      A.set(name, M);
      return M;
    };
    // DEF-ear follows ear, DEF-ear_tip follows ear_tip (both children of their control)
    for (const name of this.bones.keys()) resolve(name);
    this.writeSkin();
    this.morphWeights = this.sleeveWeights();
    return A;
  }

  // bendy ear: Blender's B-bone, as N+1 joint frames along an equal-length cubic
  // (handles from the neighbouring bendy bone give one smooth curve through the joint)
  bendySegments(name) {
    const b = this.bones.get(name);
    const n = b.segments;
    const isTip = name.includes('ear_tip');
    const prev = isTip ? name.replace('DEF-ear_tip', 'DEF-ear') : null;
    const next = isTip ? null : name.replace('DEF-ear', 'DEF-ear_tip');
    const curve = posed => {
      const A = k => posed ? (this.A.get(k) || new Matrix4()) : new Matrix4();
      const pose = A(name).clone().multiply(b.restM);           // bone matrix (posed or rest)
      const inv = pose.clone().invert();
      const L = b.length;
      const local = (bn, which) => this.bones.get(bn)[which].clone().applyMatrix4(A(bn)).applyMatrix4(inv);
      let h1 = new Vector3(0, 1, 0), h2 = new Vector3(0, 1, 0), roll1 = 0, roll2 = 0;
      // roll at each end follows the neighbouring bone's twist (Blender: mat3_vec_to_roll)
      const vecRoll = (v, roll) => new Matrix4().makeRotationFromQuaternion(new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), v))
        .multiply(new Matrix4().makeRotationY(roll));
      const rot3 = m => new Matrix4().extractRotation(m);
      if (prev) {
        h1 = new Vector3(0, L, 0).sub(local(prev, 'headV')).normalize();   // average direction across both bones
        const m = rot3(inv.clone().multiply(A(prev).clone().multiply(this.bones.get(prev).restM))).multiply(vecRoll(h1, 0).invert());
        roll1 = Math.atan2(m.elements[8], m.elements[10]);
      }
      if (next) {
        h2 = local(next, 'tailV').normalize();
        const m = vecRoll(h2, 0).invert().multiply(rot3(inv.clone().multiply(A(next).clone().multiply(this.bones.get(next).restM))));
        roll2 = Math.atan2(m.elements[8], m.elements[10]);
      }
      const dot = Math.max(-1, Math.min(1, h1.dot(h2)));
      let f = 1 / 3;
      if (dot < -1 + 1e-7) f = 0.5;
      else if (dot < 1 - 1e-7) { const a = Math.acos(dot) / 2; f = ((1 - Math.cos(a)) / (Math.sin(a) * 2)) / Math.sin(a); }
      const hl = L * f / 0.75;
      const p0 = new Vector3(), p3 = new Vector3(0, L, 0);
      const p1 = h1.clone().multiplyScalar(hl * (b.ease_in ?? 1)), p2 = p3.clone().addScaledVector(h2, -hl * (b.ease_out ?? 1));
      const bez = u => new Vector3().addScaledVector(p0, (1 - u) ** 3).addScaledVector(p1, 3 * u * (1 - u) ** 2)
        .addScaledVector(p2, 3 * u * u * (1 - u)).addScaledVector(p3, u ** 3);
      const tan = u => new Vector3().addScaledVector(p1.clone().sub(p0), 3 * (1 - u) ** 2)
        .addScaledVector(p2.clone().sub(p1), 6 * u * (1 - u)).addScaledVector(p3.clone().sub(p2), 3 * u * u).normalize();
      // equal arc length samples
      const M = 64, us = [0], acc = [0];
      let prevP = bez(0);
      for (let i = 1; i <= M; i++) { const u = i / M, P = bez(u); acc.push(acc[i - 1] + P.distanceTo(prevP)); us.push(u); prevP = P; }
      const total = acc[M];
      const uAt = s => { let i = 1; while (i < M && acc[i] < s) i++; const t = (s - acc[i - 1]) / ((acc[i] - acc[i - 1]) || 1); return us[i - 1] + t * (us[i] - us[i - 1]); };
      const out = [];
      for (let i = 0; i <= n; i++) {
        const u = i === 0 ? 0 : i === n ? 1 : uAt(total * i / n);
        const roll = roll1 + (roll2 - roll1) * (i / n);
        out.push(pose.clone().multiply(vecRoll(tan(u), roll).setPosition(bez(u))));
      }
      return out;
    };
    const rest = curve(false), out = curve(true).map((m, i) => m.multiply(rest[i].clone().invert()));
    return out;
  }

  writeSkin() {
    const bendy = new Map();
    this.skinBones.forEach((name, i) => {
      let M;
      const hash = name.indexOf('#');
      if (hash > 0) {
        const base = name.slice(0, hash);
        if (!bendy.has(base)) bendy.set(base, this.bendySegments(base));
        M = bendy.get(base)[Number(name.slice(hash + 1))];
      } else M = this.A.get(name) || new Matrix4();
      M.toArray(this.skin, i * 16);
    });
  }

  // garment.py: sleeves bunch as the arm rises (upper) or the elbow bends (fore)
  sleeveWeights() {
    const ang = (a, b) => {
      const qa = new Quaternion().setFromRotationMatrix(this.A.get(a) || new Matrix4());
      const qb = new Quaternion().setFromRotationMatrix(this.A.get(b) || new Matrix4());
      return qa.angleTo(qb);
    };
    const ramp = (x, lo, hi) => Math.min(1, Math.max(0, (x - lo * RAD) / ((hi - lo) * RAD)));
    const w = {};
    for (const s of ['L', 'R']) {
      w[`BUNNY_sleeve_up.${s}`] = ramp(ang(`DEF-upper_arm.${s}`, 'chest'), 30, 130);
      w[`BUNNY_sleeve_fore.${s}`] = ramp(ang(`DEF-forearm.${s}`, `DEF-upper_arm.${s}`), 35, 130);
    }
    return w;
  }

  // CPU skinning of the cage, then Blender's subdivision on top
  deformCage(mesh, out = new Float32Array(mesh.cage.length)) {
    const P = mesh.cage, I = mesh.skinIndex, W = mesh.skinWeight, sk = this.skin;
    const morph = mesh.morphs?.Bunch, mw = this.morphWeights?.[mesh.name] || 0;
    for (let v = 0; v < mesh.cageCount; v++) {
      let x = P[3 * v], y = P[3 * v + 1], z = P[3 * v + 2];
      if (morph && mw) { x += morph[3 * v] * mw; y += morph[3 * v + 1] * mw; z += morph[3 * v + 2] * mw; }
      let ox = 0, oy = 0, oz = 0;
      for (let k = 0; k < 4; k++) {
        const w = W[4 * v + k];
        if (!w) continue;
        const o = I[4 * v + k] * 16;
        ox += w * (sk[o] * x + sk[o + 4] * y + sk[o + 8] * z + sk[o + 12]);
        oy += w * (sk[o + 1] * x + sk[o + 5] * y + sk[o + 9] * z + sk[o + 13]);
        oz += w * (sk[o + 2] * x + sk[o + 6] * y + sk[o + 10] * z + sk[o + 14]);
      }
      out[3 * v] = ox; out[3 * v + 1] = oy; out[3 * v + 2] = oz;
    }
    return out;
  }

  deform(mesh, out) {
    return subdivide(mesh, this.deformCage(mesh), out);
  }
}
