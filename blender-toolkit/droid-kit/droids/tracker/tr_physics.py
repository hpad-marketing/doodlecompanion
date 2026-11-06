"""Tracked droid physics: one small rigid-body model shared by the motion library (baked) and Drive mode (live).
Pure Python (no bpy), so the same numbers drive both.

What it models
- Drive: each track is a motor with a speed lag, an acceleration limit set by motor torque AND by traction
  (mu * g * the weight on that track), and a harder braking limit. Ground speed = mean of the tracks,
  yaw rate = difference / track gauge, with a skid-steer scrub loss when the tracks counter-rotate.
- Chassis on four coil-over struts: pitch, roll and heave are damped springs. Accelerating squats the tail, braking
  dives the nose, turning rolls the chassis outward, a load in the scoop pushes the nose down and compresses the struts.
- Body on its motors: the lean and sway motors are stiff but not rigid. The body's own inertia makes it lag behind
  the chassis (tips back when the droid sets off, pitches forward when it stops) and then settle.
- Stalk caps (springs), tow hook (pendulum): driven by the real acceleration of the point they hang from.
- Servos: every driven joint moves with a trapezoid speed profile (max speed, max acceleration), slower when loaded.
Units: metres, seconds, kilograms, radians.
"""
import math

G = 9.81
MASS = {'tracks': 16.0, 'chassis': 11.0, 'body': 13.0, 'scoop': 3.0}
M_TOTAL = sum(MASS.values())           # 43 kg porter
GAUGE = 0.58                           # track centre to centre
MU = 0.85                              # rubber pads on deck plating
H_CG = 0.36                            # centre of gravity height (loaded body raises it)
TRACK_LAG = 0.10                       # motor speed lag (s)
A_DRIVE = 0.9                          # motor-limited acceleration (m/s^2)
A_BRAKE = 1.6                          # braking (motors reverse + friction)
V_MAX = 0.9


def clamp(x, lo, hi): return lo if x < lo else hi if x > hi else x


class Spring:
    """second-order spring-damper toward a moving target: x'' = w^2 (target - x) - 2 z w x'"""
    def __init__(self, hz, zeta, x=0.0):
        self.w = 2 * math.pi * hz; self.z = zeta; self.x = x; self.v = 0.0
    def step(self, target, dt, force=0.0):
        a = self.w * self.w * (target - self.x) - 2 * self.z * self.w * self.v + force
        self.v += a * dt; self.x += self.v * dt
        return self.x


class Servo:
    """trapezoid motor: accelerates at amax up to vmax, brakes in time to stop on the target"""
    def __init__(self, vmax, amax, x=0.0):
        self.vmax = vmax; self.amax = amax; self.x = x; self.v = 0.0; self.a = 0.0
    def step(self, target, dt, load=1.0):
        amax = self.amax / load; vmax = self.vmax / math.sqrt(load)
        e = target - self.x
        vd = math.copysign(min(vmax, math.sqrt(2 * amax * abs(e) * 0.92)), e) if abs(e) > 1e-6 else 0.0
        a = clamp((vd - self.v) / dt, -amax, amax)
        self.a = a; self.v += a * dt; self.x += self.v * dt
        if abs(e) < 1e-5 and abs(self.v) < 1e-4: self.x = target; self.v = 0.0
        return self.x


class Track:
    def __init__(self):
        self.v = 0.0; self.dist = 0.0
    def step(self, cmd, dt, normal_load):
        cmd = clamp(cmd, -V_MAX, V_MAX)
        want = (cmd - self.v) / max(TRACK_LAG, dt)
        braking = (cmd * self.v < 0) or abs(cmd) < abs(self.v)
        a_motor = A_BRAKE if braking else A_DRIVE
        a_trac = MU * G * normal_load            # traction limit for this track's share of the weight
        a = clamp(want, -min(a_motor, a_trac), min(a_motor, a_trac))
        self.v += a * dt; self.dist += self.v * dt
        return self.v


SERVOS = {  # joint: (max speed, max accel) in rad/s, rad/s^2 (m/s for slides)
    'waist': (2.4, 7.0), 'lean': (1.4, 6.0), 'sway': (1.0, 5.0),
    'scoop_lift': (1.1, 4.0), 'scoop_tilt': (1.8, 7.0), 'bin_lid': (2.5, 9.0),
    'stalk_roll.L': (4.0, 22.0), 'stalk_roll.R': (4.0, 22.0), 'stalk_pitch.L': (4.0, 22.0), 'stalk_pitch.R': (4.0, 22.0),
    'stalk_ext.L': (0.35, 2.5), 'stalk_ext.R': (0.35, 2.5),
}


class Droid:
    """state of the whole droid; call step(cmd, dt) at 240 Hz"""
    def __init__(self):
        self.x = 0.0; self.y = 0.0; self.yaw = 0.0
        self.tl, self.tr = Track(), Track()
        self.v = 0.0; self.w = 0.0; self.a_fwd = 0.0; self.a_left = 0.0
        self.pitch = Spring(1.9, 0.32); self.roll = Spring(2.1, 0.35); self.heave = Spring(2.4, 0.38)
        self.lean_flex = Spring(1.7, 0.22); self.sway_flex = Spring(1.9, 0.22)
        self.tip = {S: (Spring(2.6, 0.10), Spring(2.6, 0.10)) for S in 'LR'}
        self.hook = 0.0; self.hook_v = 0.0
        self.servo = {k: Servo(*v) for k, v in SERVOS.items()}
        self.load = 0.0
        self._v_prev = 0.0; self._lean_v_prev = 0.0; self._pitch_v_prev = 0.0

    def step(self, cmd, dt):
        """cmd: dict with 'vl', 'vr' (track speed commands, m/s), servo targets by joint name, 'load' (kg in the scoop)"""
        self.load = cmd.get('load', self.load)
        m = M_TOTAL + self.load
        # weight share per track shifts with acceleration and turning (load transfer), floor at 20 %
        share_l = clamp(0.5 - self.a_left * H_CG / (GAUGE * G), 0.2, 0.8)
        share_r = 1.0 - share_l
        vl = self.tl.step(cmd.get('vl', 0.0), dt, share_l * 2)
        vr = self.tr.step(cmd.get('vr', 0.0), dt, share_r * 2)
        v = 0.5 * (vl + vr)
        scrub = 0.82 if vl * vr < 0 else 0.92      # skid steer loses some yaw to pad scrub
        w = (vr - vl) / GAUGE * scrub
        self.a_fwd = (v - self._v_prev) / dt; self._v_prev = v
        self.a_left = v * w                          # centripetal accel points to the turn centre (left for +w)
        self.v, self.w = v, w
        self.yaw += w * dt
        self.x += v * math.sin(self.yaw) * dt; self.y += -v * math.cos(self.yaw) * dt
        # servos (scoop slows down when loaded; waist slows with a full bin)
        sv = {}
        for k, s in self.servo.items():
            load = 1.0 + (self.load / 6.0 if k.startswith('scoop') else 0.0)
            sv[k] = s.step(cmd.get(k, s.x), dt, load)
        # chassis on its struts: + pitch = nose down, + roll = toward the droid's right, heave + = up
        load_moment = self.load * G * 0.30            # load sits ~0.30 m ahead of the strut centre
        lift_react = -self.servo['scoop_lift'].a * (1.0 + self.load) * 0.004
        p_ss = (m * self.a_fwd * H_CG * -1.0 + load_moment) / 600.0 + lift_react
        r_ss = (m * self.a_left * H_CG) / 700.0
        h_ss = -self.load * G / 26000.0
        p = self.pitch.step(p_ss, dt); r = self.roll.step(r_ss, dt); h = self.heave.step(h_ss, dt)
        # body: accel at the lean pivot in the body frame (chassis accel + chassis pitch spin x height)
        wa = sv['waist']
        a_f = self.a_fwd - self.pitch.v * 0 + 0.30 * ((self.pitch.v - self._pitch_v_prev) / dt) * -1.0
        self._pitch_v_prev = self.pitch.v
        a_bf = a_f * math.cos(wa) + self.a_left * math.sin(wa)
        a_bl = -a_f * math.sin(wa) + self.a_left * math.cos(wa)
        lean_servo_acc = self.servo['lean'].a
        lf = self.lean_flex.step(-a_bf * 0.030 - lean_servo_acc * 0.006, dt)
        sf = self.sway_flex.step(a_bl * 0.026 - self.servo['waist'].a * 0.0015, dt)
        # stalk caps: lag behind the accel at the stalk top (body accel + lean/sway spin x 0.55 m)
        top_f = a_bf + 0.55 * (self.lean_flex.v - self._lean_v_prev) / dt
        self._lean_v_prev = self.lean_flex.v
        tips = {}
        for S in 'LR':
            px, pz = self.tip[S]
            sp = self.servo[f'stalk_pitch.{S}'].a * 0.010
            tips[S] = (px.step(-top_f * 0.05 - sp, dt), pz.step(a_bl * 0.05, dt))
        # tow hook pendulum (L = 6 cm): forward accel swings it back (+)
        L = 0.06
        acc = (-G * math.sin(self.hook) + self.a_fwd * math.cos(self.hook)) / L - 2 * 0.07 * math.sqrt(G / L) * self.hook_v
        self.hook_v += acc * dt; self.hook += self.hook_v * dt
        self.hook = clamp(self.hook, math.radians(-26), math.radians(60))
        return dict(x=self.x, y=self.y, yaw=self.yaw, track_L=self.tl.dist, track_R=self.tr.dist,
                    sus_pitch=p, sus_roll=r, sus_heave=h, lean=sv['lean'] + lf, sway=sv['sway'] + sf, waist=wa,
                    scoop_lift=sv['scoop_lift'], scoop_tilt=sv['scoop_tilt'], bin_lid=sv['bin_lid'],
                    stalk={S: dict(roll=sv[f'stalk_roll.{S}'], pitch=sv[f'stalk_pitch.{S}'], ext=sv[f'stalk_ext.{S}'],
                                   tip_x=tips[S][0], tip_z=tips[S][1]) for S in 'LR'},
                    hook=self.hook, v=v, w=w, a_fwd=self.a_fwd, a_left=self.a_left,
                    whirr={k: abs(s.v) for k, s in self.servo.items()}, track_speed=(vl, vr))
