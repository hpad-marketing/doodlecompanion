"""Tracked droid motion library, baked from the physics model (tr_physics.py), plus one-click poses.
python3 tr_library.py in.blend out.blend
Each motion is a list of COMMANDS (track speeds, servo targets, scoop load), the way a puppeteer would drive the droid.
The physics model turns them into motion: the tracks accelerate as torque and traction allow, the chassis squats,
dives and rolls on its struts, the body lags and settles, stalk caps and the tow hook swing from real accelerations.
Then every frame is checked: no part touches another or the floor, struts and ram stay inside their stroke.
"""
import bpy, sys, math, json
from bpy_extras import anim_utils
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import tr_physics as P
from trcheck import Checker
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene; sc.render.fps = 24
FPS = 24; SUB = 10                     # 240 Hz physics
arm = bpy.data.objects['TrackerRig']; pbs = arm.pose.bones
r = math.radians

# springs are baked from the physics now; keep the spring constraints for Drive mode only
for pb in pbs:
    c = pb.constraints.get('spring')
    if c: c.mute = True

LIM = {}
for pb in pbs:
    for c in pb.constraints:
        if c.type == 'LIMIT_ROTATION':
            LIM[pb.name] = {a: (getattr(c, f'min_{a}'), getattr(c, f'max_{a}')) for a in 'xyz'}
        if c.type == 'LIMIT_LOCATION':
            LIM[pb.name + ':loc'] = {a: (getattr(c, f'min_{a}'), getattr(c, f'max_{a}')) for a in 'xyz' if getattr(c, f'use_min_{a}')}
def lim(b, a, v, loc=False):
    L = LIM.get(b + (':loc' if loc else ''), {}).get(a)
    return P.clamp(v, *L) if L else v

# ---------------------------------------------------------------- command timelines
class Cmd:
    """step commands over time: cmd.at(t, key=value, ...) holds until changed; drive(t, vl, vr)"""
    def __init__(self, base=None):
        self.ev = []; self.base = dict(base or {})
    def at(self, t, **kw):
        self.ev.append((t, kw)); return self
    def state(self, t):
        s = dict(self.base)
        for tt, kw in sorted(self.ev, key=lambda e: e[0]):
            if tt <= t + 1e-9: s.update(kw)
        return s

CARRY = dict(scoop_lift=r(-6), scoop_tilt=r(-8))
def droop(S, v): return -v if S == 'L' else v          # outward droop: L negative, R positive (roll about the forward axis)

def stalks(**kw):
    """stalk servo targets: droop (outward, deg), pitch (deg, + forward), ext (m); suffix _L/_R for one side"""
    d = {}
    for S in 'LR':
        dr = kw.get('droop_' + S, kw.get('droop'))
        pt = kw.get('pitch_' + S, kw.get('pitch'))
        ex = kw.get('ext_' + S, kw.get('ext'))
        if dr is not None: d[f'stalk_roll.{S}'] = r(droop(S, dr))
        if pt is not None: d[f'stalk_pitch.{S}'] = r(pt)
        if ex is not None: d[f'stalk_ext.{S}'] = ex
    return d

FACE_PROPS = ['eyes_' + k for k in ('blink', 'happy', 'sad', 'angry', 'wide', 'heart', 'x')] + \
             ['mouth_' + k for k in ('smile', 'frown', 'oh', 'wavy')] + ['talk', 'face_glow', 'lamps', 'led_glow', 'stalk_glow', 'screen_mode', 'screen_value', 'scan', 'vent_puff']
REST_FACE = dict(face_glow=1.0, lamps=0.0, led_glow=1.0, stalk_glow=1.0, screen_mode=0, screen_value=0.7)

M = []
def motion(name, label, dur, loop=False, start_load=0.0, start=None):
    def deco(fn): M.append(dict(name=name, label=label, dur=dur, loop=loop, fn=fn, load=start_load, start=start or {})); return fn
    return deco

def blinks(F, times):
    for t in times:
        F.key('eyes_blink', t - 0.06, 0.0); F.key('eyes_blink', t, 1.0); F.key('eyes_blink', t + 0.10, 0.0)

class Face:
    """face/eye keys (not physics): key(prop, t, value); look(t, x, z) moves both eyes on the screen"""
    def __init__(self): self.k = {}; self.eye = []
    def key(self, prop, t, v): self.k.setdefault(prop, []).append((t, v)); return self
    def set(self, t, **kw):
        for p, v in kw.items(): self.key(p, t, v)
        return self
    def look(self, t, x, z): self.eye.append((t, x, z)); return self

def talk(F, t0, t1, rate=7.5, seed=1):
    """syllable pattern for the voice slot: open/close at speech rate with phrase gaps"""
    import random
    rnd = random.Random(seed); t = t0
    while t < t1:
        n = rnd.randint(2, 5)
        for _ in range(n):
            if t >= t1: break
            F.key('talk', t, 0.0); F.key('talk', t + 0.5 / rate, rnd.uniform(0.45, 1.0)); t += 1.0 / rate
        F.key('talk', t, 0.0); t += rnd.uniform(0.18, 0.4)
    F.key('talk', t1, 0.0)

# ---------------------------------------------------------------- motions
@motion('TR_idle', 'Idle (loop)', 6.0, loop=True)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=4, pitch=0, ext=0.02))
    C.at(1.2, **stalks(pitch_L=8, ext_L=0.035)).at(2.4, **stalks(pitch=0, ext=0.02)).at(3.6, waist=r(12), **stalks(droop_R=8))
    C.at(4.6, waist=0.0, **stalks(droop=4))
    blinks(F, (1.8, 4.9)); F.look(0, 0, 0).look(1.1, 0.012, 0.004).look(2.5, 0, 0).look(3.5, -0.016, 0).look(4.8, 0, 0)

@motion('TR_drive_forward', 'Drive forward and stop', 6.5)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.5, vl=0.6, vr=0.6, **stalks(ext=0.05, pitch=-6)).at(4.2, vl=0.0, vr=0.0).at(4.6, **stalks(ext=0.03, pitch=4))
    F.set(0.3, eyes_wide=0.0, mouth_smile=0.0).set(0.6, eyes_wide=0.4, mouth_smile=0.6).set(4.3, eyes_wide=0.8, mouth_oh=0.0)
    F.set(4.5, mouth_oh=0.5, mouth_smile=0.0).set(5.3, eyes_wide=0.0, mouth_oh=0.0, eyes_happy=0.0).set(5.8, eyes_happy=0.7, mouth_smile=0.5)
    blinks(F, (2.6,))

@motion('TR_reverse', 'Reverse, looking back', 5.5)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.2, waist=r(-35), lean=r(-4), **stalks(pitch=-12, ext=0.05)).at(0.9, vl=-0.32, vr=-0.32).at(3.9, vl=0.0, vr=0.0)
    C.at(4.4, waist=0.0, lean=0.0, **stalks(pitch=0, ext=0.02))
    F.look(0, 0, 0).look(0.5, -0.02, 0.0).look(4.4, -0.02, 0.0).look(4.9, 0, 0); blinks(F, (2.2,))

def turn(sign):
    def fn(C, F):
        C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
        # look first, then the body follows: eyes lead, stalks lean into the turn, tracks counter-rotate
        C.at(0.2, waist=r(25 * sign), **stalks(droop_L=2 + (8 if sign < 0 else -2), droop_R=2 + (8 if sign > 0 else -2)))
        C.at(0.6, vl=-0.32 * sign, vr=0.32 * sign, waist=r(10 * sign))
        C.at(2.45, vl=0.0, vr=0.0, waist=0.0, **stalks(droop=2))
        F.look(0, 0, 0).look(0.25, 0.022 * sign * -1, 0).look(2.4, 0.01 * -sign, 0).look(3.0, 0, 0); blinks(F, (1.4,))
    return fn
motion('TR_turn_left', 'Turn on the spot, left', 4.0)(turn(1))
motion('TR_turn_right', 'Turn on the spot, right', 4.0)(turn(-1))

@motion('TR_arc_left', 'Drive a curve to the left', 6.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.03))
    C.at(0.4, vl=0.38, vr=0.62, waist=r(15)).at(4.4, vl=0.0, vr=0.0, waist=0.0)
    F.look(0, 0, 0).look(0.4, -0.014, 0).look(4.5, 0, 0).set(1.0, mouth_smile=0.4); blinks(F, (2.8,))

@motion('TR_emergency_stop', 'Emergency stop', 5.5)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=0, pitch=-4, ext=0.05))
    C.at(0.3, vl=0.8, vr=0.8).at(2.3, vl=0.0, vr=0.0, **stalks(ext=0.085, pitch=-10)).at(2.7, lean=r(-6)).at(3.6, lean=0.0, **stalks(ext=0.02, pitch=6, droop=10))
    F.set(0.3, eyes_wide=0.0).set(2.2, eyes_wide=0.0, mouth_oh=0.0).set(2.35, eyes_wide=1.0, mouth_oh=1.0)
    F.set(3.4, eyes_wide=0.0, mouth_oh=0.0, eyes_sad=0.0, mouth_wavy=0.0).set(3.8, eyes_sad=0.5, mouth_wavy=0.8).set(5.2, eyes_sad=0.3)
    F.look(3.6, 0, -0.012)

@motion('TR_scoop_pickup', 'Scoop something up', 9.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=0, pitch=0, ext=0.02))
    C.at(0.3, **stalks(pitch=22, ext=0.04), lean=r(8)).at(0.9, scoop_lift=r(8), scoop_tilt=r(4))       # look down, lower the scoop
    C.at(2.2, vl=0.14, vr=0.14).at(3.6, vl=0.0, vr=0.0)                                              # creep forward, under the item
    C.at(4.0, scoop_tilt=r(-55), load=P.SCRAP_KG).at(4.9, scoop_lift=r(-26)).at(5.4, lean=r(0), **stalks(pitch=0, ext=0.06))
    C.at(7.0, scoop_lift=r(-18), **stalks(ext=0.03))
    F.look(0.3, 0, -0.02).set(0.3, eyes_happy=0.0).set(4.1, eyes_happy=0.0).set(4.6, eyes_happy=1.0, mouth_smile=0.0).set(5.0, mouth_smile=1.0)
    F.look(5.4, 0, 0); blinks(F, (2.0, 7.6))

@motion('TR_scoop_dump', 'Tip the scoop out', 7.0, start_load=P.SCRAP_KG,
        start=dict(scoop_lift=r(-18), scoop_tilt=r(-55)))
def _(C, F):
    C.base.update(scoop_lift=r(-18), scoop_tilt=r(-55), load=P.SCRAP_KG, **stalks(droop=0, pitch=0, ext=0.03))
    C.at(0.4, scoop_lift=r(-36), **stalks(pitch=15)).at(1.6, scoop_tilt=r(18)).at(2.25, load=0.0)
    C.at(3.4, scoop_tilt=r(-8)).at(3.8, scoop_lift=r(-6), **stalks(pitch=0))
    F.look(0.4, 0, -0.015).set(2.2, eyes_happy=0.0, mouth_smile=0.0).set(2.6, eyes_happy=1.0, mouth_smile=1.0).look(3.8, 0, 0); blinks(F, (5.0,))

@motion('TR_look_around', 'Look around', 7.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.3, waist=r(-70), **stalks(ext=0.06, droop_R=-4, droop_L=10)).at(2.2, waist=r(70), **stalks(droop_L=-4, droop_R=10))
    C.at(4.3, waist=r(0), lean=r(-6), **stalks(droop=0, pitch=-15, ext=0.085)).at(5.6, lean=0.0, **stalks(droop=2, pitch=0, ext=0.02))
    F.look(0.2, 0.022, 0).look(2.0, 0.022, 0).look(2.3, -0.022, 0).look(4.1, -0.022, 0).look(4.4, 0, 0.018).look(5.6, 0, 0)
    blinks(F, (2.25, 6.3))

@motion('TR_happy_wiggle', 'Happy wiggle', 4.5)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=0, pitch=0, ext=0.02))
    C.at(0.2, **stalks(ext=0.085, droop=-6))
    t = 0.5
    for k in range(6):   # short opposite track jolts rock the whole droid on its struts
        s = 1 if k % 2 == 0 else -1
        C.at(t, vl=0.30 * s, vr=-0.30 * s, sway=r(4 * s)); t += 0.22
        C.at(t, vl=0.0, vr=0.0); t += 0.12
    C.at(t, sway=0.0).at(t + 0.6, **stalks(ext=0.04, droop=2))
    F.set(0.2, eyes_happy=0.0, mouth_smile=0.0).set(0.4, eyes_happy=1.0, mouth_smile=1.0).set(4.0, eyes_happy=1.0).set(4.4, eyes_happy=0.6)

@motion('TR_sad', 'Sad', 6.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.4, **stalks(droop=35, pitch=24, ext=0.0), lean=r(9)).at(4.6, **stalks(droop=28, pitch=18), lean=r(7))
    for S in 'LR': P.SERVOS[f'stalk_roll.{S}'] = (1.2, 4.0)
    F.set(0.3, eyes_sad=0.0, mouth_frown=0.0, face_glow=1.0).set(1.3, eyes_sad=1.0, mouth_frown=0.8, face_glow=0.65).look(1.3, 0, -0.016)
    blinks(F, (3.2,))

@motion('TR_surprised', 'Surprised', 4.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.5, vl=-0.35, vr=-0.35, **stalks(ext=0.085, pitch=-14, droop=-6), lean=r(-9)).at(0.8, vl=0.0, vr=0.0)
    C.at(2.4, lean=0.0, **stalks(ext=0.03, pitch=0, droop=2))
    F.set(0.45, eyes_wide=0.0, mouth_oh=0.0).set(0.55, eyes_wide=1.0, mouth_oh=1.0).set(2.4, eyes_wide=1.0, mouth_oh=1.0).set(2.9, eyes_wide=0.2, mouth_oh=0.0)

@motion('TR_talk', 'Talking', 6.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.6, **stalks(pitch_L=-10, ext_L=0.05), lean=r(3)).at(1.6, **stalks(pitch_L=0, ext_L=0.02, droop_R=12)).at(2.8, sway=r(4), lean=r(-2))
    C.at(3.9, sway=r(-3), **stalks(droop_R=2, ext=0.05)).at(5.0, sway=0.0, lean=0.0, **stalks(ext=0.02))
    talk(F, 0.4, 5.4, seed=3); F.set(0.4, mouth_smile=0.3).look(1.5, 0.01, 0).look(3.0, -0.01, 0.004).look(4.4, 0, 0); blinks(F, (2.2, 4.7))

@motion('TR_show_stash', 'Show off the salvage bin', 8.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.3, waist=r(150)).at(2.2, bin_lid=r(100), **stalks(pitch=-25, ext=0.06)).at(5.2, bin_lid=0.0).at(6.0, waist=0.0, **stalks(pitch=0, ext=0.02))
    F.set(0.3, eyes_happy=0.0, mouth_smile=0.0).set(2.4, eyes_heart=0.0).set(2.8, eyes_heart=1.0, mouth_smile=1.0).set(5.0, eyes_heart=1.0).set(5.4, eyes_heart=0.0, eyes_happy=0.6)

@motion('TR_power_down', 'Power down', 5.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.6, **stalks(ext=0.0, droop=14, pitch=18), lean=r(10), scoop_lift=r(8))
    F.set(0.4, face_glow=1.0, eyes_blink=0.0, led_glow=1.0, stalk_glow=1.0).set(2.6, eyes_blink=0.85, face_glow=0.25, stalk_glow=0.2)
    F.set(3.6, face_glow=0.02, led_glow=0.08, stalk_glow=0.0, eyes_blink=1.0).set(2.0, screen_mode=0).set(2.6, screen_mode=7)

@motion('TR_power_up', 'Power up', 5.0, start=dict(scoop_lift=r(8), lean=r(10), **stalks(ext=0.0, droop=14, pitch=18)))
def _(C, F):
    C.base.update(scoop_lift=r(8), scoop_tilt=r(-8), lean=r(10), **stalks(ext=0.0, droop=14, pitch=18))
    C.at(1.4, lean=0.0, **stalks(droop=0, pitch=0, ext=0.05)).at(2.2, scoop_lift=r(-6)).at(2.6, **stalks(pitch_L=-8, pitch_R=8))
    C.at(2.9, **stalks(pitch_L=8, pitch_R=-8)).at(3.2, **stalks(pitch=0, ext=0.02))
    F.set(0.0, face_glow=0.02, led_glow=0.08, stalk_glow=0.0, eyes_blink=1.0, eyes_wide=0.0)
    for k, (t, v) in enumerate(((0.5, 0.6), (0.62, 0.05), (0.75, 0.9), (0.85, 0.3), (1.0, 1.0))): F.key('face_glow', t, v); F.key('led_glow', t, v)
    F.set(1.0, eyes_blink=1.0, stalk_glow=0.0).set(1.3, eyes_blink=0.0, eyes_wide=1.0, stalk_glow=1.0).set(2.4, eyes_wide=0.0); blinks(F, (3.4,))

@motion('TR_shake_off', 'Shake off dust', 4.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.03))
    t = 0.4
    for k in range(6):
        C.at(t, sway=r(7 if k % 2 == 0 else -7)); t += 0.2
    C.at(t, sway=0.0)
    F.set(0.3, eyes_x=0.0, mouth_wavy=0.0).set(0.5, eyes_x=0.8, mouth_wavy=1.0).set(t + 0.2, eyes_x=0.8).set(t + 0.6, eyes_x=0.0, mouth_wavy=0.0, eyes_happy=0.6)

# ---- screen modes and secondary functions
@motion('TR_scan', 'Scan the room', 7.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.4, **stalks(ext=0.085, pitch=10)).at(1.2, **stalks(droop_L=-14, droop_R=14)).at(2.4, **stalks(droop_L=10, droop_R=-10))
    C.at(3.6, waist=r(40), **stalks(droop_L=-8, droop_R=8)).at(4.8, waist=r(-30)).at(5.8, waist=0.0, **stalks(droop=2, ext=0.02, pitch=0))
    F.set(0.3, screen_mode=0, scan=0.0).set(0.6, screen_mode=1).set(0.6, scan=0.0).set(1.0, scan=1.0).set(5.6, scan=1.0).set(5.9, scan=0.0).set(6.0, screen_mode=0)
    F.set(6.0, eyes_happy=0.0).set(6.3, eyes_happy=0.8, mouth_smile=0.6)

@motion('TR_low_battery', 'Low battery', 6.0)
def _(C, F):
    for k in list(P.SERVOS): P.SERVOS[k] = (P.SERVOS[k][0] * 0.45, P.SERVOS[k][1] * 0.45)   # tired motors
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.5, **stalks(droop=24, pitch=14, ext=0.0), lean=r(6)).at(1.5, vl=0.12, vr=0.12).at(3.4, vl=0.0, vr=0.0)
    F.set(0.4, screen_mode=0, eyes_sad=0.0).set(0.9, eyes_sad=0.8, eyes_blink=0.0).set(1.8, screen_mode=2, screen_value=0.15)
    F.set(4.6, screen_mode=2).set(4.8, screen_mode=0).set(5.0, eyes_blink=0.5, face_glow=0.5)

@motion('TR_error', 'Error glitch', 4.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    t = 0.5
    for k in range(5):
        C.at(t, **stalks(pitch_L=14 if k % 2 else -14, pitch_R=-14 if k % 2 else 14), sway=r(3 if k % 2 else -3)); t += 0.14
    C.at(t, sway=0.0, **stalks(pitch=0, droop=12))
    F.set(0.4, screen_mode=0).set(0.5, screen_mode=3).set(2.6, screen_mode=3).set(2.7, screen_mode=0, eyes_x=0.0).set(2.8, eyes_x=1.0, mouth_wavy=1.0).set(3.8, eyes_x=0.6)

@motion('TR_navigate', 'Follow the arrow', 7.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.03))
    C.at(0.9, vl=0.35, vr=0.35).at(2.4, vl=0.25, vr=0.55).at(4.2, vl=0.35, vr=0.35).at(5.4, vl=0.0, vr=0.0)
    F.set(0.2, screen_mode=0).set(0.4, screen_mode=5, screen_value=0.0).set(2.2, screen_value=0.0).set(2.5, screen_value=55.0)
    F.set(4.0, screen_value=55.0).set(4.4, screen_value=0.0).set(5.6, screen_mode=5).set(5.8, screen_mode=0, eyes_happy=0.0).set(6.1, eyes_happy=0.8)

@motion('TR_ramp', 'Lower the scoop as a ramp', 7.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.4, **stalks(pitch=20), lean=r(6)).at(0.8, scoop_lift=r(6), scoop_tilt=r(6)).at(4.6, scoop_lift=r(-6), scoop_tilt=r(-8)).at(5.0, lean=0.0, **stalks(pitch=0))
    F.look(0.4, 0, -0.02).set(1.8, mouth_smile=0.0).set(2.2, mouth_smile=0.8).look(4.8, 0, 0); blinks(F, (3.0,))

@motion('TR_vent_dust', 'Vent the dust', 5.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.6, **stalks(droop=-4, ext=0.05), lean=r(-3)).at(3.2, lean=0.0, **stalks(droop=2, ext=0.02))
    F.set(0.5, vent_puff=0.0).set(0.9, vent_puff=1.0).set(2.9, vent_puff=1.0).set(3.6, vent_puff=0.0)
    F.set(0.6, eyes_blink=0.0).set(0.8, eyes_happy=0.0, eyes_blink=0.7).set(3.4, eyes_blink=0.0, eyes_happy=0.7)

@motion('TR_show_stickers', 'Show the sticker collection', 6.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.4, lean=r(-4), **stalks(ext=0.07, droop=-6)).at(4.6, lean=0.0, **stalks(ext=0.02, droop=2))
    F.set(0.5, screen_mode=0).set(0.7, screen_mode=6).set(4.8, screen_mode=6).set(5.0, screen_mode=0, eyes_heart=0.0).set(5.3, eyes_heart=1.0, mouth_smile=1.0)

@motion('TR_work_lights', 'Work lights on, creep forward', 6.0)
def _(C, F):
    C.base.update(CARRY, **stalks(droop=2, pitch=0, ext=0.02))
    C.at(0.8, vl=0.15, vr=0.15, **stalks(pitch=8, ext=0.05)).at(4.2, vl=0.0, vr=0.0, **stalks(pitch=0, ext=0.02))
    for t, v in ((0.3, 0.0), (0.4, 1.0), (0.48, 0.2), (0.6, 1.0)): F.key('lamps', t, v)
    F.set(5.4, lamps=1.0).set(5.8, lamps=0.0).look(1.0, 0, -0.012).look(4.4, 0, 0)

POSES = {   # one-click poses (static, physics at rest)
    'Rest': dict(),
    'Carry': dict(CARRY, **stalks(droop=2, ext=0.02)),
    'Happy': dict(CARRY, **stalks(droop=-6, ext=0.085), face=dict(eyes_happy=1, mouth_smile=1)),
    'Sad': dict(CARRY, lean=r(9), **stalks(droop=35, pitch=24, ext=0.0), face=dict(eyes_sad=1, mouth_frown=0.8, face_glow=0.65)),
    'Alert': dict(CARRY, lean=r(-5), **stalks(droop=-4, pitch=-12, ext=0.085), face=dict(eyes_wide=1)),
    'Curious': dict(CARRY, lean=r(10), sway=r(5), **stalks(droop_L=-4, droop_R=20, pitch_L=10, pitch_R=-6, ext_L=0.06, ext_R=0.02), face=dict(mouth_oh=0.5)),
    'Sleep': dict(scoop_lift=r(8), scoop_tilt=r(-8), lean=r(10), **stalks(ext=0.0, droop=14, pitch=18), face=dict(eyes_blink=1, face_glow=0.02, led_glow=0.08, stalk_glow=0.0)),
    'Scoop up': dict(scoop_lift=r(-38), scoop_tilt=r(-60), **stalks(pitch=10, ext=0.04), face=dict(eyes_happy=0.6)),
}

# ---------------------------------------------------------------- baking
def fcurves(act):
    return anim_utils.action_get_channelbag_for_slot(act, act.slots[0]).fcurves

CH = []    # (bone, path, index) keyed per frame
def key_bone(b, path, i, f, v):
    pb = pbs[b]; getattr(pb, path)[i] = v; pb.keyframe_insert(path, index=i, frame=f, group=b)
def key_prop(p, f, v):
    arm[p] = v; arm.keyframe_insert(f'["{p}"]', frame=f, group='Props')

def apply_state(st, f):
    key_bone('root', 'location', 0, f, -st['x']); key_bone('root', 'location', 1, f, -st['y']); key_bone('root', 'rotation_euler', 2, f, st['yaw'])
    key_prop('track_L', f, st['track_L']); key_prop('track_R', f, st['track_R'])
    key_bone('suspension', 'location', 1, f, lim('suspension', 'y', st['sus_heave'], True))
    key_bone('suspension', 'rotation_euler', 0, f, lim('suspension', 'x', st['sus_pitch']))
    key_bone('suspension', 'rotation_euler', 2, f, lim('suspension', 'z', st['sus_roll']))
    key_bone('lean', 'rotation_euler', 0, f, lim('lean', 'x', st['lean']))
    key_bone('body', 'rotation_euler', 1, f, lim('body', 'y', st['sway']))
    key_bone('waist', 'rotation_euler', 1, f, lim('waist', 'y', st['waist']))
    key_bone('scoop_lift', 'rotation_euler', 0, f, lim('scoop_lift', 'x', st['scoop_lift']))
    key_bone('scoop_tilt', 'rotation_euler', 0, f, lim('scoop_tilt', 'x', st['scoop_tilt']))
    key_bone('bin_lid', 'rotation_euler', 0, f, lim('bin_lid', 'x', st['bin_lid']))
    key_bone('tow_hook', 'rotation_euler', 0, f, lim('tow_hook', 'x', st['hook']))
    for S in 'LR':
        s = st['stalk'][S]
        key_bone(f'stalk_roll.{S}', 'rotation_euler', 2, f, lim(f'stalk_roll.{S}', 'z', s['roll']))
        key_bone(f'stalk_pitch.{S}', 'rotation_euler', 0, f, lim(f'stalk_pitch.{S}', 'x', s['pitch']))
        key_bone(f'stalk_ext.{S}', 'location', 1, f, lim(f'stalk_ext.{S}', 'y', s['ext'], True))
        key_bone(f'stalk_tip.{S}', 'rotation_euler', 0, f, lim(f'stalk_tip.{S}', 'x', s['tip_x']))
        key_bone(f'stalk_tip.{S}', 'rotation_euler', 2, f, lim(f'stalk_tip.{S}', 'z', s['tip_z']))

def reset_pose():
    for pb in pbs: pb.location = (0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.scale = (1, 1, 1)
    for p in FACE_PROPS: arm[p] = REST_FACE.get(p, 0.0)
    arm['track_L'] = arm['track_R'] = 0.0

def new_action(name):
    old = bpy.data.actions.get(name)
    if old: bpy.data.actions.remove(old)
    act = bpy.data.actions.new(name); arm.animation_data_create(); arm.animation_data.action = act
    return act

def bake(mo, idx):
    reset_pose()
    act = new_action(mo['name'])
    C = Cmd(); F = Face()
    saved = dict(P.SERVOS)
    mo['fn'](C, F)
    d = P.Droid(); d.load = mo['load']
    for k, v in d.servo.items():
        if k in P.SERVOS: v.vmax, v.amax = P.SERVOS[k]
    init = dict(C.base); init.update(mo['start'])
    for k, v in init.items():
        if k in d.servo: d.servo[k].x = v
    jmap = {'sway': 'sway'}
    n = int(round(mo['dur'] * FPS)); dt = 1.0 / (FPS * SUB)
    # settle the struts under the start load before frame 1
    for _ in range(FPS * SUB * 2): d.step(dict(C.state(0.0), vl=0.0, vr=0.0), dt)
    d.x = d.y = d.yaw = 0.0; d.tl.dist = d.tr.dist = 0.0
    whirr = []
    for fr in range(1, n + 1):
        t = (fr - 1) / FPS
        for k in range(SUB):
            st = d.step(C.state(t + k * dt), dt)
        apply_state(st, fr)
        whirr.append({k: round(v, 3) for k, v in st['whirr'].items() if v > 0.02})
    for p in FACE_PROPS:
        keys = F.k.get(p)
        if not keys:
            key_prop(p, 1, REST_FACE.get(p, 0.0)); continue
        if keys[0][0] > 0: key_prop(p, 1, REST_FACE.get(p, 0.0) if p != 'eyes_blink' else 0.0)
        for t, v in sorted(keys): key_prop(p, max(1, int(round(t * FPS)) + 1), v)
    for t, x, z in (F.eye or [(0, 0, 0)]):
        fr = max(1, int(round(t * FPS)) + 1)
        for S in 'LR':
            key_bone(f'eye.{S}', 'location', 0, fr, x); key_bone(f'eye.{S}', 'location', 2, fr, z)
    P.SERVOS.clear(); P.SERVOS.update(saved)
    for c in fcurves(act):
        if c.data_path == '["screen_mode"]':
            for k in c.keyframe_points: k.interpolation = 'CONSTANT'
    act['tracker_motion'] = 1; act['label'] = mo['label']; act['loop'] = int(mo['loop']); act['order'] = idx
    act['frames'] = n; act['whirr'] = json.dumps(whirr)          # servo speeds per frame, for the servo-whirr sounds
    act.use_fake_user = True; act.frame_range = (1, n); act.use_frame_range = True
    return act, n

def bake_pose(name, spec, idx):
    reset_pose()
    act = new_action('TRP_' + name.replace(' ', '_'))
    face = spec.get('face', {})
    d = P.Droid()
    for k, v in spec.items():
        if k in d.servo: d.servo[k].x = v
    for _ in range(FPS * SUB * 2): st = d.step({k: v for k, v in spec.items() if k != 'face'}, 1.0 / (FPS * SUB))
    st['x'] = st['y'] = st['yaw'] = 0.0; st['track_L'] = st['track_R'] = 0.0
    apply_state(st, 1)
    for p in FACE_PROPS: key_prop(p, 1, face.get(p, REST_FACE.get(p, 0.0)))
    act['tracker_pose'] = 1; act['label'] = name; act['order'] = idx; act.use_fake_user = True
    return act

ck = Checker(arm)
def floor_fix_scoop(act, n):
    """the scoop may rest ON the floor but never in it: raise the lift on any frame where a tooth dips"""
    fixed = 0
    fc = next(c for c in fcurves(act) if c.data_path == 'pose.bones["scoop_lift"].rotation_euler' and c.array_index == 0)
    ft = next((c for c in fcurves(act) if c.data_path == 'pose.bones["scoop_tilt"].rotation_euler' and c.array_index == 0), None)
    parts = [o for o in ck.parts if o['rig_bone'] in ('scoop_lift', 'scoop_tilt')]
    for fr in range(1, n + 1):
        sc.frame_set(fr)
        for _ in range(30):
            low = min(ck.world(o)[:, 2].min() for o in parts)
            if low >= 0.0006: break
            kp = next(k for k in fc.keyframe_points if int(round(k.co.x)) == fr)
            kp.co.y = max(kp.co.y - r(0.25), r(-41)); kp.handle_left.y = kp.handle_right.y = kp.co.y; fc.update()
            if ft:  # tip the lip back up too, so the teeth rest flat instead of digging in
                kt = next((k for k in ft.keyframe_points if int(round(k.co.x)) == fr), None)
                if kt: kt.co.y = max(kt.co.y - r(0.4), r(-75)); kt.handle_left.y = kt.handle_right.y = kt.co.y; ft.update()
            sc.frame_set(fr); fixed += 1
    return fixed

report = {}
for i, mo in enumerate(M):
    act, n = bake(mo, i)
    fx = floor_fix_scoop(act, n)
    hits = {}
    for fr in range(1, n + 1):
        sc.frame_set(fr)
        for h in ck.hits():
            hits.setdefault(' | '.join(map(str, h[:2])), fr)
    report[mo['name']] = dict(frames=n, scoop_floor_fixes=fx, clashes=hits,
                              max_pitch_deg=round(max(abs(math.degrees(k.co.y)) for c in fcurves(act) if c.data_path.endswith('"suspension"].rotation_euler') and c.array_index == 0 for k in c.keyframe_points), 2))
    print('MOTION', mo['name'], n, 'floorfix', fx, 'clashes', len(hits), list(hits.items())[:3])
for i, (nm, spec) in enumerate(POSES.items()):
    act = bake_pose(nm, spec, i)
    sc.frame_set(1); h = ck.hits()
    report['pose ' + nm] = dict(clashes=[' | '.join(map(str, x[:2])) for x in h])
    print('POSE', nm, 'clashes', len(h), h[:3])
arm.animation_data.action = bpy.data.actions['TR_idle']
sc.frame_start, sc.frame_end = 1, bpy.data.actions['TR_idle']['frames']
json.dump(report, open('out/library_report.json', 'w'), indent=1)
bad = sum(len(v['clashes']) for v in report.values())
print('LIBRARY', len(M), 'motions', len(POSES), 'poses', 'clash entries', bad)
bpy.ops.wm.save_as_mainfile(filepath=out)
