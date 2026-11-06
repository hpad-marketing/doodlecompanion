"""Tracked porter droid: N-panel > Tracker. Motion library, poses, screen modes, lights, stickers, voice hook,
and Drive mode (DualSense / Xbox pad / keyboard) running the same physics model the motion library was baked from."""
import bpy, math, json, random
from mathutils import Vector

RIG = 'TrackerRig'
CAT = 'Tracker'
r = math.radians


def rig(ctx):
    ob = ctx.active_object
    if ob and ob.type == 'ARMATURE' and ob.get('droid') == 'tracker': return ob
    return bpy.data.objects.get(RIG)


FACE_PROPS = ['eyes_' + k for k in ('blink', 'happy', 'sad', 'angry', 'wide', 'heart', 'x')] + \
             ['mouth_' + k for k in ('smile', 'frown', 'oh', 'wavy')] + ['talk', 'face_glow', 'lamps', 'led_glow', 'stalk_glow',
                                                                        'screen_mode', 'screen_value', 'scan', 'vent_puff']
REST_FACE = dict(face_glow=1.0, lamps=0.0, led_glow=1.0, stalk_glow=1.0, screen_mode=0, screen_value=0.7)
SCREEN_MODES = ['Face', 'Scan', 'Battery', 'Error', 'Loading', 'Arrow', 'Sticker gallery', 'Sleep']


def reset_pose(ob):
    for pb in ob.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_mode = 'XYZ'; pb.rotation_euler = (0, 0, 0); pb.scale = (1, 1, 1)
    for p in FACE_PROPS:
        if p in ob: ob[p] = REST_FACE.get(p, 0.0)
    ob['track_L'] = ob['track_R'] = 0.0


def set_action(ob, act):
    ad = ob.animation_data or ob.animation_data_create()
    ad.action = act
    if act is not None and hasattr(ad, 'action_slot') and act.slots: ad.action_slot = act.slots[0]


def motions(kind='tracker_motion'):
    return sorted([a for a in bpy.data.actions if a.get(kind)], key=lambda a: a.get('order', 0))


class TRACKER_OT_motion(bpy.types.Operator):
    """Play a motion from the library (baked from the physics model: real acceleration, squat, dive, sway)"""
    bl_idname = 'tracker.motion'; bl_label = 'Play motion'; bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.StringProperty()
    play: bpy.props.BoolProperty(default=True)

    def execute(self, ctx):
        ob = rig(ctx); act = bpy.data.actions.get(self.action)
        if not (ob and act): return {'CANCELLED'}
        set_action(ob, act)
        sc = ctx.scene; n = int(act.get('frames', act.frame_range[1]))
        sc.frame_start, sc.frame_end = 1, n; sc.frame_set(1)
        if self.play and act.get('tracker_motion') and not ctx.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
        return {'FINISHED'}


class TRACKER_OT_reset(bpy.types.Operator):
    """Clear the motion and put every joint back to rest"""
    bl_idname = 'tracker.reset'; bl_label = 'Rest pose'; bl_options = {'REGISTER', 'UNDO'}

    def execute(self, ctx):
        ob = rig(ctx)
        if not ob: return {'CANCELLED'}
        if ctx.screen.is_animation_playing: bpy.ops.screen.animation_cancel(restore_frame=False)
        set_action(ob, None); reset_pose(ob); ctx.view_layer.update()
        return {'FINISHED'}


class TRACKER_OT_screen(bpy.types.Operator):
    """Show this mode on the screen (the face lights only in Face mode)"""
    bl_idname = 'tracker.screen'; bl_label = 'Screen mode'; bl_options = {'REGISTER', 'UNDO'}
    mode: bpy.props.IntProperty()

    def execute(self, ctx):
        ob = rig(ctx)
        if not ob: return {'CANCELLED'}
        ob['screen_mode'] = self.mode; ob.update_tag(); ctx.view_layer.update()
        return {'FINISHED'}


class TRACKER_PT_main(bpy.types.Panel):
    bl_label = 'Tracked porter droid'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = CAT

    @classmethod
    def poll(cls, ctx): return rig(ctx) is not None

    def draw(self, ctx):
        ob = rig(ctx); lay = self.layout
        row = lay.row(align=True)
        row.operator('tracker.reset', icon='LOOP_BACK')
        row.operator('tracker.drive', icon='PLAY', text='Drive')
        lay.label(text='Motions (physics-baked)', icon='ACTION')
        g = lay.grid_flow(columns=2, align=True)
        for a in motions():
            g.operator('tracker.motion', text=a.get('label', a.name)).action = a.name
        lay.label(text='Poses', icon='ARMATURE_DATA')
        g = lay.grid_flow(columns=4, align=True)
        for a in motions('tracker_pose'):
            op = g.operator('tracker.motion', text=a.get('label', a.name)); op.action = a.name; op.play = False


class TRACKER_PT_screen(bpy.types.Panel):
    bl_label = 'Screen, lights, stickers'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = CAT
    bl_parent_id = 'TRACKER_PT_main'

    def draw(self, ctx):
        ob = rig(ctx); lay = self.layout
        g = lay.grid_flow(columns=4, align=True)
        for i, n in enumerate(SCREEN_MODES):
            g.operator('tracker.screen', text=n, depress=int(ob.get('screen_mode', 0)) == i).mode = i
        col = lay.column(align=True)
        col.prop(ob, '["screen_value"]', text='Screen value (battery, loading, arrow)')
        row = lay.row(align=True)
        for k, t in (('eyes_happy', 'Happy'), ('eyes_sad', 'Sad'), ('eyes_angry', 'Cross'), ('eyes_wide', 'Wide'),
                     ('eyes_heart', 'Heart'), ('eyes_x', 'X'), ('eyes_blink', 'Blink')):
            row.prop(ob, f'["{k}"]', text=t)
        row = lay.row(align=True)
        for k, t in (('mouth_smile', 'Smile'), ('mouth_frown', 'Frown'), ('mouth_oh', 'Oh'), ('mouth_wavy', 'Wavy'), ('talk', 'Talk')):
            row.prop(ob, f'["{k}"]', text=t)
        row = lay.row(align=True)
        for k, t in (('lamps', 'Work lights'), ('scan', 'Scanner beams'), ('vent_puff', 'Vent dust'), ('power', 'Power')):
            row.prop(ob, f'["{k}"]', text=t)
        row = lay.row(align=True)
        for k, t in (('face_glow', 'Face glow'), ('led_glow', 'LEDs'), ('stalk_glow', 'Stalk caps')):
            row.prop(ob, f'["{k}"]', text=t)
        if 'stickers_shown' in ob: lay.prop(ob, '["stickers_shown"]', text='Souvenir stickers shown')


class TRACKER_PT_voice(bpy.types.Panel):
    bl_label = 'Voice'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = CAT
    bl_parent_id = 'TRACKER_PT_main'; bl_options = {'DEFAULT_CLOSED'}

    def draw(self, ctx):
        ob = rig(ctx); lay = self.layout
        lay.label(text='Droid Voice keys dv_level / dv_accent on this rig:')
        lay.label(text='the mouth opens with the level, the screen flickers on accents.')
        lay.prop(ob, '["dv_level"]', text='Voice level'); lay.prop(ob, '["dv_accent"]', text='Accent')
        try:
            import droid_voice  # noqa: F401
            lay.label(text='Droid Voice found: speaker "tracker" (crush chain)', icon='CHECKMARK')
        except ImportError:
            lay.label(text='Droid Voice add-on not installed here; lines from it still drive the face', icon='INFO')


# @@PAD@@

# @@PHYSICS@@

# ================================================================== tracker drive core
class DriveInput:
    def __init__(self):
        self.thr = self.steer = self.waist = self.look = 0.0
        self.lift = self.tilt = self.ext = 0.0
        self.fire = set()       # one-shots: talk happy scan dump surprised lights power vent screen+ screen- record follow exit


KEY_FIRE = {'T': 'talk', 'H': 'happy', 'G': 'scan', 'B': 'dump', 'N': 'surprised', 'L': 'lights', 'P': 'power',
            'V': 'vent', 'RIGHT_BRACKET': 'screen+', 'LEFT_BRACKET': 'screen-', 'R': 'record', 'F': 'follow', 'ESC': 'exit'}
PAD_FIRE = {'A': 'talk', 'B': 'happy', 'X': 'scan', 'Y': 'dump', 'R3': 'surprised', 'L3': 'lights', 'START': 'power',
            'MIC': 'vent', 'RIGHT': 'screen+', 'LEFT': 'screen-', 'BACK': 'record', 'PAD': 'follow', 'PS': 'exit'}
FACE_MOTIONS = {'happy': 'TR_happy_wiggle', 'scan': 'TR_scan', 'surprised': 'TR_surprised', 'talk': 'TR_talk'}
OVERLAY_BONES = ('eye.', 'mouth', 'stalk_')
OVERLAY_PROPS = set(FACE_PROPS) - {'lamps', 'screen_mode', 'screen_value', 'vent_puff'}


def action_fcurves(act):
    if hasattr(act, 'layers') and len(act.layers):
        for layer in act.layers:
            for st in layer.strips:
                for cb in st.channelbags:
                    yield from cb.fcurves
    elif hasattr(act, 'fcurves'):
        yield from act.fcurves


def _sm(cur, tgt, rate, dt): return cur + (tgt - cur) * min(1.0, rate * dt)


# ---- servo whirr: one synthesized motor voice per joint group, pitch and volume follow the real servo speeds
WHIRR = {  # group: (servo keys, waveform, base Hz, full-speed value, volume)
    'tracks': (('track',), 'sawtooth', 70.0, 0.9, 0.22),
    'waist': (('waist',), 'square', 150.0, 2.4, 0.10),
    'lean': (('lean', 'sway'), 'square', 120.0, 1.4, 0.08),
    'scoop': (('scoop_lift', 'scoop_tilt'), 'sawtooth', 105.0, 1.8, 0.14),
    'lid': (('bin_lid',), 'square', 210.0, 2.5, 0.06),
    'stalks': (('stalk_roll.L', 'stalk_roll.R', 'stalk_pitch.L', 'stalk_pitch.R', 'stalk_ext.L', 'stalk_ext.R'), 'square', 380.0, 4.0, 0.05),
}


class Whirr:
    def __init__(self):
        self.h = {}; self.dev = None
        try:
            import aud
            self.dev = aud.Device()
            for g, (_, wave, hz, _, _) in WHIRR.items():
                s = getattr(aud.Sound, wave)(hz).lowpass(hz * 6).mix(aud.Sound.square(hz * 2.01).volume(0.12))
                h = self.dev.play(s); h.volume = 0.0; self.h[g] = h
        except Exception:
            self.h = {}

    def set(self, speeds):
        for g, (keys, _, _, full, vol) in WHIRR.items():
            h = self.h.get(g)
            if not h: continue
            s = min(1.0, max(speeds.get(k, 0.0) for k in keys) / full)
            h.volume = vol * min(1.0, s * 3.0) ** 1.5
            h.pitch = 0.55 + 0.9 * s

    def chirp(self, n=3, seed=None):
        """short bit-crushed chatter for the Talk button when no voice line is loaded"""
        if not self.dev: return
        try:
            import aud
            rnd = random.Random(seed); s = None
            for i in range(n):
                hz = rnd.choice((330, 392, 440, 523, 587, 659)) * rnd.uniform(0.95, 1.05)
                b = aud.Sound.square(hz).limit(0, rnd.uniform(0.06, 0.14)).fadeout(0.04, 0.04).volume(0.18)
                s = b if s is None else s.join(aud.Sound.silence().limit(0, 0.03)).join(b)
            self.dev.play(s)
        except Exception:
            pass

    def stop(self):
        for h in self.h.values():
            try: h.stop()
            except Exception: pass
        self.h = {}


class DriveCore:
    """Drives the porter through tr_physics.Droid at 240 Hz: track motors with lag and traction limits, struts that
    squat, dive and roll, body inertia, sprung stalk caps, a swinging tow hook and trapezoid servos that slow down
    under load. Drive the scoop low and forward to pick up scrap (4 kg): the nose drops and everything gets heavier."""
    SUB = 10

    def __init__(self, ob):
        self.ob = ob; pb = ob.pose.bones
        self.d = Droid()
        self.d.x = -pb['root'].location.x; self.d.y = -pb['root'].location.y; self.d.yaw = pb['root'].rotation_euler.z
        self.d.tl.dist = ob.get('track_L', 0.0); self.d.tr.dist = ob.get('track_R', 0.0)
        self.tg = dict(waist=0.0, lean=0.0, sway=0.0, scoop_lift=r(-6), scoop_tilt=r(-8), bin_lid=0.0)
        for S in 'LR':
            self.tg[f'stalk_roll.{S}'] = r(-2 if S == 'L' else 2); self.tg[f'stalk_pitch.{S}'] = 0.0; self.tg[f'stalk_ext.{S}'] = 0.02
        for k, v in self.tg.items(): self.d.servo[k].x = v
        tbl = json.loads(ob.get('scoop_floor', '[]'))
        self.floor_tbl = sorted(tbl) if tbl else [[-75.0, 8.0], [20.0, 8.0]]
        self.floor_k = json.loads(ob.get('scoop_floor_k', '[-0.25, -0.4, 1.0]'))
        self.t = 0.0; self.powered = True; self.follow = True; self.lights = False
        self.overlay = None; self.face = {}; self.blink_t = 2.0; self.scan_t = -9; self.vent_t = -9; self.wiggle_t = -9
        self.dump = None; self.ch = {}; self.whirr_log = []; self.st = None
        self.screen = int(ob.get('screen_mode', 0))

    def sm(self, k, tgt, rate, dt, start=0.0):
        v = _sm(self.ch.get(k, start), tgt, rate, dt); self.ch[k] = v; return v

    def max_lift(self, tilt):
        """lowest the scoop may go (rad) at this tilt before its teeth touch the floor (2 mm margin), corrected for the
        chassis pitching and bobbing on its struts right now: a nose dive brings the teeth down with it"""
        gl, gp, gh = self.floor_k
        drop = gp * self.d.pitch.x + gh * self.d.heave.x - 0.002          # teeth height change (m), negative = lower
        return self._tbl(tilt) + drop / -gl if gl < 0 else self._tbl(tilt)

    def _tbl(self, tilt):
        t = math.degrees(tilt); T = self.floor_tbl
        if t <= T[0][0]: v = T[0][1]
        elif t >= T[-1][0]: v = T[-1][1]
        else:
            for (a, va), (b, vb) in zip(T, T[1:]):
                if a <= t <= b: v = va + (vb - va) * (t - a) / max(1e-6, b - a); break
        return r(v)

    def play(self, name):
        act = bpy.data.actions.get(name)
        if not act: return
        fps = bpy.context.scene.render.fps or 24
        import re
        pat = re.compile(r'pose\.bones\["([^"]+)"\]\.(rotation_euler|location)')
        chans, props = [], []
        for fc in action_fcurves(act):
            m = pat.match(fc.data_path)
            if m and m.group(1).startswith(OVERLAY_BONES) and not m.group(1).startswith('stalk_tip'):
                chans.append((m.group(1), m.group(2), fc.array_index, fc))
            elif fc.data_path.startswith('["') and fc.data_path[2:-2] in OVERLAY_PROPS:
                props.append((fc.data_path[2:-2], fc))
        n = (act.frame_range[1] - act.frame_range[0]) / fps
        self.overlay = dict(n=n, t0=self.t, chans=chans, props=props, f0=act.frame_range[0], name=name)

    def tick(self, inp, dt, whirr=None):
        ob = self.ob; pb = ob.pose.bones; d = self.d; tg = self.tg
        self.t += dt
        for f in inp.fire:
            if f == 'power':
                self.powered = not self.powered
            elif not self.powered:
                continue
            elif f in FACE_MOTIONS:
                self.play(FACE_MOTIONS[f])
                if f == 'talk' and whirr: whirr.chirp(random.randint(2, 5))
                if f == 'happy': self.wiggle_t = self.t
                if f == 'scan': self.scan_t = self.t
            elif f == 'dump' and self.dump is None: self.dump = self.t
            elif f == 'lights': self.lights = not self.lights
            elif f == 'vent': self.vent_t = self.t
            elif f in ('screen+', 'screen-'):
                self.screen = (self.screen + (1 if f == 'screen+' else -1)) % 8
        # ---- servo targets from the sticks (rates in rad/s or m/s; the servos then move at their own real speed)
        if self.powered:
            tg['waist'] = max(r(-150), min(r(150), tg['waist'] + inp.waist * 1.8 * dt))
            tg['lean'] = r(14) * inp.look
            tg['scoop_lift'] = max(r(-41), min(r(8), tg['scoop_lift'] + inp.lift * 1.0 * dt))
            tg['scoop_tilt'] = max(r(-75), min(r(20), tg['scoop_tilt'] + inp.tilt * 1.4 * dt))
            for S in 'LR':
                tg[f'stalk_ext.{S}'] = max(0.0, min(0.085, tg[f'stalk_ext.{S}'] + inp.ext * 0.08 * dt))
                tg[f'stalk_pitch.{S}'] = r(-18) * inp.look + r(8) * max(0.0, -d.a_fwd)
                tg[f'stalk_roll.{S}'] = r(-2 if S == 'L' else 2)
        else:   # power down: body slumps forward, stalks fold, scoop rests low
            tg.update(lean=r(10), scoop_lift=r(4), scoop_tilt=r(-8))
            for S in 'LR':
                tg[f'stalk_ext.{S}'] = 0.0; tg[f'stalk_pitch.{S}'] = r(18); tg[f'stalk_roll.{S}'] = r(-14 if S == 'L' else 14)
        # happy wiggle: the waist rocks +-12 deg for a second
        wt = self.t - self.wiggle_t
        wig = r(12) * math.sin(wt * 2 * math.pi * 2.0) if wt < 1.0 else 0.0
        # tip scrap into the bin: scoop up and over, lid opens, scrap goes in, lid closes, scoop comes back
        lid = 0.0; lift_t, tilt_t = tg['scoop_lift'], tg['scoop_tilt']
        if self.dump is not None:
            k = self.t - self.dump
            if k < 1.6: lift_t, tilt_t = r(-38), r(-60)
            if 0.6 < k < 2.6: lid = r(110)
            if k > 1.8 and d.load > 0: d.load = 0.0
            if k > 3.2: self.dump = None
        lift_t = min(lift_t, self.max_lift(d.servo['scoop_tilt'].x))
        # scrap pickup: scoop low and driving forward fills it (4 kg of scrap)
        if d.load == 0 and d.servo['scoop_lift'].x > self.max_lift(d.servo['scoop_tilt'].x) - r(3) and d.v > 0.12 and self.dump is None: d.load = 4.0
        v_cmd = inp.thr * V_MAX if self.powered else 0.0
        turn = inp.steer * 0.55 if self.powered else 0.0
        cmd = dict(vl=v_cmd + turn * (1 - 0.4 * abs(inp.thr)), vr=v_cmd - turn * (1 - 0.4 * abs(inp.thr)),
                   waist=tg['waist'] + wig, lean=tg['lean'], sway=0.0, scoop_lift=lift_t, scoop_tilt=tilt_t, bin_lid=lid)
        for S in 'LR':
            for k in ('stalk_roll', 'stalk_pitch', 'stalk_ext'): cmd[f'{k}.{S}'] = tg[f'{k}.{S}']
        hdt = dt / self.SUB
        for _ in range(self.SUB):
            st = d.step(cmd, hdt)
            s = d.servo['scoop_lift']; ml = self.max_lift(d.servo['scoop_tilt'].x)   # load cell end-stop: never into the floor
            if s.x > ml: s.x = ml; s.v = min(0.0, s.v)
        self.st = st
        self.apply(st)
        # ---- face: blinks, eyes lead the turn, a start at hard stops, glow follows power
        f = self.face
        self.blink_t -= dt
        if self.blink_t < 0: self.blink_t = random.uniform(2.2, 5.0); f['blink_until'] = self.t + 0.12
        blink = 1.0 if self.t < f.get('blink_until', -1) else 0.0
        startle = 1.0 if st['a_fwd'] < -1.1 else 0.0
        f['wide'] = _sm(f.get('wide', 0.0), startle, 10 if startle else 1.5, dt)
        f['smile'] = _sm(f.get('smile', 0.0), 0.5 if abs(st['v']) > 0.4 else 0.15, 2.0, dt)
        f['oh'] = _sm(f.get('oh', 0.0), 0.6 * startle + (0.35 if d.load > 0 else 0.0), 6.0, dt)
        pw = self.sm('power', 1.0 if self.powered else 0.03, 2.0, dt, 1.0)
        props = dict(eyes_blink=max(blink, 0.0 if self.powered else 1.0), eyes_wide=f['wide'], mouth_smile=f['smile'],
                     mouth_oh=f['oh'], face_glow=pw, led_glow=pw, stalk_glow=pw, power=pw,
                     lamps=self.sm('lamps', 1.0 if (self.lights and self.powered) else 0.0, 12, dt),
                     scan=1.0 if self.t - self.scan_t < 6.0 else 0.0,
                     vent_puff=self.sm('vent', 1.0 if self.t - self.vent_t < 2.0 else 0.0, 5, dt),
                     screen_mode=7 if not self.powered else (1 if self.t - self.scan_t < 6.0 else self.screen),
                     talk=0.0, eyes_happy=0.0, eyes_sad=0.0, mouth_frown=0.0)
        look_x = max(-0.012, min(0.012, -0.012 * st['w'] / 1.5 + 0.004 * inp.waist))
        eye = (look_x, -0.006 * inp.look)
        # ---- one-shot overlay from the motion library (face, eyes, stalks), blended in and out
        ov = self.overlay
        if ov:
            lt = self.t - ov['t0']
            if lt >= ov['n']: self.overlay = None
            else:
                fps = bpy.context.scene.render.fps or 24
                fr = ov['f0'] + lt * fps; w = max(0.0, min(1.0, lt / 0.2, (ov['n'] - lt) / 0.2))
                for b, prop, i, fc in ov['chans']:
                    p = pb[b]; vec = list(getattr(p, prop)); vec[i] += (fc.evaluate(fr) - vec[i]) * w; setattr(p, prop, vec)
                for k, fc in ov['props']:
                    props[k] = props.get(k, 0.0) + (fc.evaluate(fr) - props.get(k, 0.0)) * w
                eye = None
        if eye is not None:
            for S in 'LR': pb[f'eye.{S}'].location = (eye[0], 0.0, eye[1])
        lvl = ob.get('dv_level', 0.0)
        if lvl > 0.01: props['talk'] = max(props['talk'], lvl)
        for k, v in props.items():
            if k in ob: ob[k] = int(round(v)) if k == 'screen_mode' else v
        sp = dict(st['whirr']); sp['track'] = max(abs(st['track_speed'][0]), abs(st['track_speed'][1]))
        if whirr: whirr.set(sp)
        self.whirr_log.append({k: round(v, 3) for k, v in sp.items() if v > 0.02})
        return st

    def apply(self, st):
        pb = self.ob.pose.bones; ob = self.ob
        pb['root'].location = (-st['x'], -st['y'], 0.0); pb['root'].rotation_euler = (0, 0, st['yaw'])
        ob['track_L'] = st['track_L']; ob['track_R'] = st['track_R']
        pb['suspension'].location = (0, st['sus_heave'], 0); pb['suspension'].rotation_euler = (st['sus_pitch'], 0, st['sus_roll'])
        pb['lean'].rotation_euler = (max(r(-16), min(r(16), st['lean'])), 0, 0)
        pb['body'].rotation_euler = (0, max(r(-8), min(r(8), st['sway'])), 0)
        pb['waist'].rotation_euler = (0, st['waist'], 0)
        pb['scoop_lift'].rotation_euler = (st['scoop_lift'], 0, 0); pb['scoop_tilt'].rotation_euler = (st['scoop_tilt'], 0, 0)
        pb['bin_lid'].rotation_euler = (st['bin_lid'], 0, 0); pb['tow_hook'].rotation_euler = (st['hook'], 0, 0)
        for S in 'LR':
            s = st['stalk'][S]
            pb[f'stalk_roll.{S}'].rotation_euler = (0, 0, s['roll']); pb[f'stalk_pitch.{S}'].rotation_euler = (s['pitch'], 0, 0)
            pb[f'stalk_ext.{S}'].location = (0, s['ext'], 0); pb[f'stalk_tip.{S}'].rotation_euler = (s['tip_x'], 0, s['tip_z'])

    KEYED = ['root', 'suspension', 'lean', 'body', 'waist', 'scoop_lift', 'scoop_tilt', 'bin_lid', 'tow_hook', 'eye.L', 'eye.R'] + \
            [f'{b}.{S}' for S in 'LR' for b in ('stalk_roll', 'stalk_pitch', 'stalk_ext', 'stalk_tip')]


_HUD = {'h': None, 'lines': []}


def _draw_hud():
    import blf
    y = 60
    for i, (txt, col) in enumerate(reversed(_HUD['lines'])):
        blf.size(0, 15); blf.color(0, *col); blf.position(0, 24, y + i * 22, 0); blf.draw(0, txt)


def control_lines(pad):
    if pad and pad.get('sony'):
        return ['Left stick: drive and steer (tracks)   Right stick: turn the waist, look up / down',
                'R2 / L2: scoop up / down   R1 / L1: tilt the scoop   D-pad up / down: stalks out / in   D-pad left / right: screen mode',
                'Cross: talk   Circle: happy wiggle   Square: scan   Triangle: tip scrap into the bin   R3: surprised',
                'L3: work lights   Mic: vent dust   Options: power   Create: record a take   Touchpad: follow camera   PS: stop',
                'Lower the scoop and drive forward to pick up scrap (4 kg): it gets heavier']
    return ['Drive W/S   Steer A/D   Waist Q/E   Look I/K   Scoop up/down Up/Down arrows   Tilt Left/Right arrows',
            'Stalks out/in U/J   Talk T   Happy H   Scan G   Tip into bin B   Surprised N   Lights L   Vent dust V',
            'Screen mode [ ]   Power P   Record R   Follow cam F   Stop Esc']


class TRACKER_OT_drive(bpy.types.Operator):
    """Drive the porter live with a DualSense, Xbox pad or the keyboard. Same physics as the motion library.
    R / Create records a take into the motion library, Esc / PS stops."""
    bl_idname = 'tracker.drive'; bl_label = 'Drive the porter'

    def invoke(self, ctx, event):
        ob = rig(ctx)
        if not ob: return {'CANCELLED'}
        if ctx.area is None or ctx.area.type != 'VIEW_3D':
            self.report({'WARNING'}, 'Start it from the 3D viewport'); return {'CANCELLED'}
        if ctx.mode not in ('POSE', 'OBJECT'): bpy.ops.object.mode_set(mode='OBJECT')
        if ctx.screen.is_animation_playing: bpy.ops.screen.animation_cancel(restore_frame=False)
        ad = ob.animation_data or ob.animation_data_create()
        self.saved = dict(action=ad.action, nla=ad.use_nla, frame=ctx.scene.frame_current)
        ad.action = None; ad.use_nla = False
        reset_pose(ob)
        self.core = DriveCore(ob); self.keys = set(); self.prev_b = 0; self.rec = None; self.ob = ob; self.fired = set()
        self.area = ctx.area; self.pad = None; self.whirr = Whirr()
        wm = ctx.window_manager; self.timer = wm.event_timer_add(1 / 24, window=ctx.window)
        wm.modal_handler_add(self)
        if _HUD['h'] is None:
            _HUD['h'] = bpy.types.SpaceView3D.draw_handler_add(_draw_hud, (), 'WINDOW', 'POST_PIXEL')
        return {'RUNNING_MODAL'}

    def gather(self):
        i = DriveInput(); k = self.keys
        ax = lambda a, b: (1.0 if a in k else 0.0) - (1.0 if b in k else 0.0)
        i.thr = ax('W', 'S'); i.steer = ax('D', 'A'); i.waist = ax('Q', 'E'); i.look = ax('K', 'I')
        i.lift = ax('DOWN_ARROW', 'UP_ARROW'); i.tilt = ax('RIGHT_ARROW', 'LEFT_ARROW'); i.ext = ax('U', 'J')
        i.fire |= self.fired; self.fired = set()
        p = read_pad(); self.pad = p
        if p:
            b = p['b']
            if abs(p['ly']) > abs(i.thr): i.thr = p['ly']
            if abs(p['lx']) > abs(i.steer): i.steer = p['lx']
            if abs(p['rx']) > abs(i.waist): i.waist = -p['rx']
            if abs(p['ry']) > abs(i.look): i.look = -p['ry']
            i.lift = max(-1.0, min(1.0, i.lift + p['lt'] - p['rt']))
            i.tilt = max(-1.0, min(1.0, i.tilt + (1.0 if b & XB['LB'] else 0) - (1.0 if b & XB['RB'] else 0)))
            i.ext = max(-1.0, min(1.0, i.ext + (1.0 if b & XB['UP'] else 0) - (1.0 if b & XB['DOWN'] else 0)))
            new = b & ~self.prev_b; self.prev_b = b
            for name, act in PAD_FIRE.items():
                if new & XB[name]: i.fire.add(act)
        return i

    def modal(self, ctx, ev):
        if ev.type == 'TIMER':
            inp = self.gather()
            if 'exit' in inp.fire: return self.finish(ctx)
            if 'record' in inp.fire: self.toggle_rec(ctx)
            if 'follow' in inp.fire: self.core.follow = not self.core.follow
            self.core.tick(inp, 1 / 24, self.whirr)
            sc = ctx.scene
            if self.rec:
                f = self.rec['f']; sc.frame_current = f
                for b in self.core.KEYED:
                    p = self.ob.pose.bones[b]
                    p.keyframe_insert('rotation_euler', frame=f, group=b); p.keyframe_insert('location', frame=f, group=b)
                for k in FACE_PROPS + ['track_L', 'track_R']:
                    if k in self.ob: self.ob.keyframe_insert(f'["{k}"]', frame=f, group='Props')
                self.rec['whirr'].append(self.core.whirr_log[-1]); self.rec['f'] += 1
            ctx.view_layer.update()
            if self.core.follow and self.area:
                rv = self.area.spaces.active.region_3d
                tgt = self.ob.matrix_world @ self.ob.pose.bones['root'].head + Vector((0, 0, 0.45))
                tgt = self.ob.matrix_world @ (self.ob.pose.bones['body'].head)
                rv.view_location = rv.view_location.lerp(tgt, 0.12)
            src = (self.pad.get('name', 'Gamepad') if self.pad else 'Keyboard (no gamepad found)')
            st = self.core.st or {}
            info = '   %.2f m/s   load %d kg' % (st.get('v', 0.0), self.core.d.load)
            _HUD['lines'] = [
                (('● REC  take frame %d' % self.rec['f']) if self.rec else 'DRIVE MODE   ' + src + info,
                 (1, .3, .25, 1) if self.rec else (0.55, 0.9, 0.95, 1)),
                *[(t, (0.9, 0.9, 0.85, 1)) for t in control_lines(self.pad)]]
            if self.area: self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if ev.type in ('LEFTMOUSE', 'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MOUSEMOVE', 'TRACKPADPAN', 'TRACKPADZOOM'):
            return {'PASS_THROUGH'}
        if ev.value == 'PRESS':
            if ev.type in KEY_FIRE and not ev.is_repeat: self.fired.add(KEY_FIRE[ev.type])
            self.keys.add(ev.type)
        elif ev.value == 'RELEASE':
            self.keys.discard(ev.type)
        if ev.type == 'RIGHTMOUSE' and ev.value == 'PRESS': return self.finish(ctx)
        return {'RUNNING_MODAL'}

    def toggle_rec(self, ctx):
        ad = self.ob.animation_data
        if self.rec is None:
            n = 1 + sum(1 for a in bpy.data.actions if a.name.startswith('TR_take_'))
            act = bpy.data.actions.new(f'TR_take_{n:02d}'); act.use_fake_user = True
            act['tracker_motion'] = 1; act['label'] = f'Drive take {n}'; act['order'] = 200 + n; act['loop'] = 0
            set_action(self.ob, act)
            self.rec = dict(act=act, f=1, whirr=[])
        else:
            act = self.rec['act']; end = self.rec['f'] - 1
            act.frame_range = (1, max(2, end)); act.use_frame_range = True; act['frames'] = max(2, end)
            act['whirr'] = json.dumps(self.rec['whirr'])
            for fc in action_fcurves(act):
                if fc.data_path == '["screen_mode"]':
                    for kp in fc.keyframe_points: kp.interpolation = 'CONSTANT'
            ctx.scene.frame_start, ctx.scene.frame_end = 1, max(2, end)
            self.saved['action'] = act; self.saved['frame'] = 1
            ad.action = None; self.rec = None
            self.report({'INFO'}, f'{act.get("label")} saved to the motion library ({end} frames)')

    def finish(self, ctx):
        if self.rec: self.toggle_rec(ctx)
        self.whirr.stop()
        ctx.window_manager.event_timer_remove(self.timer)
        if _HUD['h'] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_HUD['h'], 'WINDOW'); _HUD['h'] = None
        ob = self.ob; ad = ob.animation_data
        set_action(ob, self.saved['action']); ad.use_nla = self.saved['nla']
        if not ad.action: reset_pose(ob)
        ctx.scene.frame_set(self.saved['frame'])
        if self.area: self.area.tag_redraw()
        return {'FINISHED'}


class TRACKER_PT_drive(bpy.types.Panel):
    bl_label = 'Drive mode (DualSense / keyboard)'; bl_space_type = 'VIEW_3D'; bl_region_type = 'UI'; bl_category = CAT
    bl_parent_id = 'TRACKER_PT_main'

    def draw(self, ctx):
        lay = self.layout
        lay.operator('tracker.drive', icon='PLAY', text='Drive the porter')
        p = read_pad()
        lay.label(text=(f'{p.get("name", "Gamepad")} connected' if p else 'No gamepad found: keyboard works. Plug in the DualSense (USB or Bluetooth)'),
                  icon='CHECKMARK' if p else 'INFO')
        col = lay.column(align=True)
        for t in control_lines(p if p else {'sony': True}): col.label(text=t)
        col.separator()
        for t in control_lines(None): col.label(text=t)
        takes = [a for a in bpy.data.actions if a.name.startswith('TR_take_')]
        if takes: lay.label(text=f'{len(takes)} recorded take(s) in the Motion library', icon='REC')


CLASSES = (TRACKER_OT_motion, TRACKER_OT_reset, TRACKER_OT_screen, TRACKER_OT_drive,
           TRACKER_PT_main, TRACKER_PT_screen, TRACKER_PT_drive, TRACKER_PT_voice)


def register():
    for c in CLASSES:
        try: bpy.utils.register_class(c)
        except ValueError: pass


register()
