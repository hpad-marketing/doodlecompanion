"""Beat Sync, Pacing check, Loop ending and Sound effects on cuts."""
import math
import os
import random
import struct
import wave

import bpy
import numpy as np

from . import core

BEAT = 'beat'


# ================================================================== audio
def first_sound_path(sc=None):
    for s in core.all_strips(sc):
        if s.type == 'SOUND' and not s.name.startswith('SFX'):
            return bpy.path.abspath(s.sound.filepath), s.frame_start
    return None, None


def load_mono(path, rate=11025):
    import aud
    snd = aud.Sound(path).rechannel(1).resample(rate, False)
    a = np.asarray(snd.data(), dtype=np.float32).reshape(-1)
    return a, rate


def onset_envelope(x, rate, hop=256, win=1024):
    n = 1 + max(0, (len(x) - win) // hop)
    if n < 4:
        return np.zeros(1), rate / hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    frames = x[idx] * np.hanning(win)[None, :]
    spec = np.log1p(np.abs(np.fft.rfft(frames, axis=1)) * 10)
    flux = np.maximum(spec[1:] - spec[:-1], 0).sum(axis=1)
    flux = np.concatenate([[0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, mode='same')
    flux = np.maximum(flux, 0)
    m = flux.max()
    return (flux / m if m > 0 else flux), rate / hop


def find_beats(path, every=1, sensitivity=0.5, steady=True):
    """Seconds of each beat. steady=True fits a tempo grid (best for music)."""
    x, rate = load_mono(path)
    env, fr = onset_envelope(x, rate)
    if len(env) < 8:
        return [], 0
    lo, hi = int(fr * 60 / 180), int(fr * 60 / 70)
    ac = np.correlate(env, env, mode='full')[len(env) - 1:]
    if hi >= len(ac):
        hi = len(ac) - 1
    lag = lo + int(np.argmax(ac[lo:hi + 1])) if hi > lo else lo
    # sub-frame tempo: parabolic peak, then refine over the whole track
    if 0 < lag < len(ac) - 1:
        a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
        den = a - 2 * b + c
        lagf = lag + (0.5 * (a - c) / den if den else 0)
    else:
        lagf = float(lag)
    t = np.arange(len(env))
    best_s, best_l = -1, lagf
    for L in np.linspace(lagf - 0.6, lagf + 0.6, 25):
        ph = np.arange(0, L, 0.5)
        sc_ = max(env[np.clip(np.round(p + L * np.arange(int((len(env) - p) / L))).astype(int), 0, len(env) - 1)].sum()
                  for p in ph)
        if sc_ > best_s:
            best_s, best_l = sc_, L
    lagf = best_l
    bpm = 60 * fr / max(lagf, 1e-6)
    if steady:
        best, ph = -1, 0.0
        for p in np.arange(0, lagf, 0.5):
            idx = np.clip(np.round(p + lagf * np.arange(int((len(env) - p) / lagf))).astype(int), 0, len(env) - 1)
            s = env[idx].sum()
            if s > best:
                best, ph = s, p
        beats = [(ph + i * lagf) / fr for i in range(int((len(env) - ph) / lagf) + 1)]
    else:
        thr = 1.0 - sensitivity
        beats, last = [], -1e9
        for i in range(1, len(env) - 1):
            if env[i] > thr * 0.6 and env[i] >= env[i - 1] and env[i] >= env[i + 1] and i - last > fr * 0.12:
                beats.append(i / fr)
                last = i
    return beats[::max(1, every)], bpm


def mark_beats(path=None, every=1, offset=0, sensitivity=0.5, steady=True):
    sc = bpy.context.scene
    start = sc.frame_start
    if not path:
        path, start = first_sound_path(sc)
        if not path:
            raise RuntimeError('No music found. Add the track in the Video Sequencer, or pick a file in Advanced.')
    clear_beats(sc)
    beats, bpm = find_beats(path, every, sensitivity, steady)
    frames = sorted(set(int(round(start + b * core.fps(sc))) + offset for b in beats))
    for f in frames:
        if f <= sc.frame_end:
            sc.timeline_markers.new(BEAT, frame=f)
    core.settings(sc).bpm = bpm
    return len(frames), bpm


def clear_beats(sc=None):
    sc = sc or bpy.context.scene
    for m in [m for m in sc.timeline_markers if m.name == BEAT]:
        sc.timeline_markers.remove(m)


def beat_frames(sc=None):
    sc = sc or bpy.context.scene
    return sorted(m.frame for m in sc.timeline_markers if m.name == BEAT)


def _nearest(f, beats):
    return min(beats, key=lambda b: abs(b - f)) if beats else f


def shift_object_keys(ob, delta):
    for idb in (ob, getattr(ob, 'data', None)):
        if idb is None:
            continue
        for fc in core.fcurves(idb):
            for k in fc.keyframe_points:
                k.co.x += delta
                k.handle_left.x += delta
                k.handle_right.x += delta
            fc.update()


def snap_to_beats(cuts=True, overlays=True, captions=True, max_shift=4):
    sc = bpy.context.scene
    beats = beat_frames(sc)
    if not beats:
        raise RuntimeError('Find Beats first.')
    moved = 0
    if cuts:
        for m in sc.timeline_markers:
            if m.camera and m.name != BEAT:
                n = _nearest(m.frame, beats)
                if n != m.frame and abs(n - m.frame) <= max_shift * 2:
                    m.frame = n
                    moved += 1
    for r in core.items(sc=sc):
        k = r['ss_kind']
        if k == 'caption' and not captions:
            continue
        if k not in ('caption', 'sticker', 'comment') or not overlays and k != 'caption':
            continue
        s = r.get('ss_start')
        if s is None:
            continue
        n = _nearest(s, beats)
        d = n - s
        if k == 'caption' and d < 0:   # never start before the previous caption has gone
            prev = [c.get('ss_end', 0) for c in core.items('caption', sc) if c.get('ss_start', 0) < s]
            if prev and s + d < max(prev):
                d = 0
        if d and abs(d) <= max_shift:
            if k == 'sticker':
                pop = core.pop_of(r)
                shift_object_keys(pop, d)
                for c in pop.children:
                    shift_object_keys(c, d)
                if 'ss_end' in r:
                    r['ss_end'] = r['ss_end'] + d
            else:   # the pop lands on the beat; it still leaves when the line ends
                end = r.get('ss_end')
                core.key_pop(r, s + d, max(end, s + d + 3) if end is not None else None, length=4)
            r['ss_start'] = s + d
            moved += 1
    return moved


# ================================================================== pacing
TARGETS = {'STORYTIME': 60, 'POV': 20, 'THREE': 30, 'MYTH': 25, 'BEFORE_AFTER': 15, 'HOT_TAKE': 20, 'NONE': 30}


def change_frames(sc=None):
    """Every frame where something visibly changes: cuts, camera/character keys, text and stickers."""
    sc = sc or bpy.context.scene
    ev = set()
    for m in sc.timeline_markers:
        if m.name != BEAT:
            ev.add(m.frame)
    for r in core.items(sc=sc):
        if 'ss_start' in r:
            ev.add(int(r['ss_start']))
    ov = bpy.data.collections.get(core.OVERLAY)
    skip = set(ov.all_objects) if ov else set()
    for ob in sc.objects:
        if ob in skip:
            continue
        idbs = [ob]
        if ob.type == 'MESH' and ob.data.shape_keys:
            idbs.append(ob.data.shape_keys)
        for idb in idbs:
            for fc in core.fcurves(idb):
                pts = fc.keyframe_points
                for i, k in enumerate(pts):
                    if i and abs(k.co.y - pts[i - 1].co.y) < 1e-4:
                        continue
                    ev.add(int(round(k.co.x)))
    for s in core.all_strips(sc):
        if s.type not in ('SOUND',):
            ev.add(int(s.frame_final_start))
    return sorted(f for f in ev if sc.frame_start <= f <= sc.frame_end)


def check_pacing(sc=None):
    sc = sc or bpy.context.scene
    st = core.settings(sc)
    fps = core.fps(sc)
    ev = change_frames(sc)
    gaps, issues = [], []
    pts = [sc.frame_start] + ev + [sc.frame_end]
    lim = st.dead_air_seconds * fps
    for a, b in zip(pts, pts[1:]):
        if b - a > lim:
            gaps.append((a, b))
            issues.append(('DEAD', a, 'Nothing changes for %.1f s' % ((b - a) / fps)))
    first = next((f for f in ev if f > sc.frame_start), None)
    if first is None or first - sc.frame_start > 1.5 * fps:
        issues.insert(0, ('HOOK', sc.frame_start, 'Slow hook: first change after %.1f s (aim for under 1.5 s)'
                          % (((first or sc.frame_end) - sc.frame_start) / fps)))
    length = (sc.frame_end - sc.frame_start + 1) / fps
    target = st.target_seconds or TARGETS.get(st.reel_format, 30)
    if length > target * 1.25:
        issues.append(('LONG', sc.frame_end, 'Runs %.0f s; this format works best around %d s' % (length, target)))
    st.pacing_report = '\n'.join('%s|%d|%s' % i for i in issues)
    _GAPS[sc.name] = gaps
    _redraw()
    return issues


_GAPS = {}
_HANDLES = []


def _draw():
    import gpu
    from gpu_extras.batch import batch_for_shader
    ctx = bpy.context
    sc = ctx.scene
    gaps = _GAPS.get(sc.name)
    if not gaps or not core.settings(sc).show_pacing:
        return
    region = ctx.region
    v2d = region.view2d
    sh = gpu.shader.from_builtin('UNIFORM_COLOR')
    y1 = region.height - 2
    y0 = y1 - 7
    x0, _ = v2d.view_to_region(sc.frame_start, 0, clip=False)
    x1, _ = v2d.view_to_region(sc.frame_end, 0, clip=False)
    gpu.state.blend_set('ALPHA')

    def rect(a, b, col):
        verts = ((a, y0), (b, y0), (b, y1), (a, y1))
        batch = batch_for_shader(sh, 'TRIS', {'pos': verts}, indices=((0, 1, 2), (0, 2, 3)))
        sh.bind()
        sh.uniform_float('color', col)
        batch.draw(sh)
    rect(x0, x1, (0.56, 0.75, 0.48, 0.85))
    for a, b in gaps:
        xa, _ = v2d.view_to_region(a, 0, clip=False)
        xb, _ = v2d.view_to_region(b, 0, clip=False)
        rect(xa, xb, (0.85, 0.30, 0.25, 0.95))
    gpu.state.blend_set('NONE')


def _redraw():
    wm = bpy.context.window_manager
    for w in wm.windows:
        for a in w.screen.areas:
            if a.type in ('DOPESHEET_EDITOR', 'SEQUENCE_EDITOR', 'GRAPH_EDITOR'):
                a.tag_redraw()


def register_draw():
    for space in (bpy.types.SpaceDopeSheetEditor, bpy.types.SpaceSequenceEditor, bpy.types.SpaceGraphEditor):
        _HANDLES.append((space, space.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')))


def unregister_draw():
    for space, h in _HANDLES:
        try:
            space.draw_handler_remove(h, 'WINDOW')
        except Exception:
            pass
    _HANDLES.clear()


# ================================================================== loop
def make_loop(blend_seconds=1.0, include_camera=True):
    """Blend the last second back to the first frame so the replay looks like one take."""
    sc = bpy.context.scene
    s, e = sc.frame_start, sc.frame_end
    b = max(1, core.sec(blend_seconds))
    ov = bpy.data.collections.get(core.OVERLAY)
    skip = set(ov.all_objects) if ov else set()
    done = 0
    for ob in sc.objects:
        if ob in skip or (ob.type == 'CAMERA' and not include_camera):
            continue
        idbs = [ob, getattr(ob, 'data', None)]
        if ob.type == 'MESH' and ob.data.shape_keys:
            idbs.append(ob.data.shape_keys)
        for idb in idbs:
            if idb is None:
                continue
            for fc in core.fcurves(idb):
                if not len(fc.keyframe_points):
                    continue
                v0 = fc.evaluate(s)
                vb = fc.evaluate(e - b)
                for k in [k for k in fc.keyframe_points if k.co.x > e - b]:
                    fc.keyframe_points.remove(k, fast=True)
                fc.keyframe_points.insert(e - b, vb, options={'FAST'})
                fc.keyframe_points.insert(e, v0, options={'FAST'})
                fc.update()
                done += 1
    return done


# ================================================================== sound effects
SFX_RATE = 44100


def _write(path, data):
    data = np.clip(data, -1, 1)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SFX_RATE)
        w.writeframes((data * 32000).astype('<i2').tobytes())


def _env(n, attack=0.005, release=None):
    t = np.arange(n) / SFX_RATE
    a = np.minimum(1, t / max(attack, 1e-4))
    r = np.exp(-t / (release or (n / SFX_RATE / 4)))
    return a * r


def _make(kind):
    rnd = np.random.default_rng(7)
    if kind == 'pop':
        n = int(0.12 * SFX_RATE)
        t = np.arange(n) / SFX_RATE
        f = 900 * np.exp(-t * 30) + 260
        return 0.8 * np.sin(2 * np.pi * np.cumsum(f) / SFX_RATE) * _env(n, 0.001, 0.025)
    if kind == 'whoosh':
        n = int(0.45 * SFX_RATE)
        x = rnd.standard_normal(n)
        t = np.arange(n) / n
        out, y, cut = np.zeros(n), 0.0, 0.02 + 0.25 * np.sin(np.pi * t) ** 2
        for i in range(n):
            y += cut[i] * (x[i] - y)
            out[i] = y
        return out / (np.abs(out).max() + 1e-9) * 0.7 * np.sin(np.pi * t) ** 1.5
    if kind == 'boing':
        n = int(0.6 * SFX_RATE)
        t = np.arange(n) / SFX_RATE
        f = 180 + 120 * np.exp(-t * 4) * np.sin(2 * np.pi * 9 * t)
        return 0.7 * np.sin(2 * np.pi * np.cumsum(f) / SFX_RATE) * _env(n, 0.002, 0.25)
    if kind == 'scratch':
        n = int(0.35 * SFX_RATE)
        t = np.arange(n) / SFX_RATE
        x = rnd.standard_normal(n)
        rate = 1 + 0.9 * np.sin(2 * np.pi * 7 * t)
        y = np.interp(np.cumsum(rate) % n, np.arange(n), x)
        return 0.5 * y * np.sin(np.pi * t / t[-1]) * (0.6 + 0.4 * np.sin(2 * np.pi * 14 * t))
    if kind == 'ding':
        n = int(0.9 * SFX_RATE)
        t = np.arange(n) / SFX_RATE
        y = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((1318, 0.5), (2637, 0.2), (3951, 0.1)))
        return 0.7 * y * _env(n, 0.002, 0.22)
    if kind == 'tick':
        n = int(0.04 * SFX_RATE)
        return 0.6 * rnd.standard_normal(n) * _env(n, 0.0005, 0.006)
    raise KeyError(kind)


SFX_KINDS = ('pop', 'whoosh', 'boing', 'scratch', 'ding', 'tick')


def sfx_path(kind):
    d = os.path.join(bpy.utils.user_resource('DATAFILES', path='social_studio_sfx', create=True))
    p = os.path.join(d, kind + '.wav')
    if not os.path.exists(p):
        _write(p, _make(kind))
    return p


EVENT_SFX = {'cut': 'whoosh', 'sticker': 'pop', 'word': 'boing', 'comment': 'pop', 'endcard': 'ding',
             'titlecard': 'ding', 'react': 'pop'}
CHANNEL = 28


def auto_sfx(volume=0.6, limit=40, cut_sound='whoosh', sticker_sound='pop'):
    """Suggest a sound on each cut and sticker hit. Suggestions start with 'SFX?'; keep or delete each."""
    sc = bpy.context.scene
    clear_sfx(suggested_only=True)
    events = []
    for m in sc.timeline_markers:
        if m.camera and m.frame > sc.frame_start:
            events.append((m.frame, cut_sound))
    for r in core.items(sc=sc):
        k = r['ss_kind']
        if 'ss_start' not in r:
            continue
        if k == 'sticker':
            word = r.get('ss_sticker', '') in ('BONK', 'BOING', 'WHOOSH', 'POP', 'WOW')
            events.append((int(r['ss_start']), 'boing' if word else sticker_sound))
        elif k in EVENT_SFX:
            events.append((int(r['ss_start']), EVENT_SFX[k]))
    events = sorted(set(events))[:limit]
    st = core.strips(sc)
    used = {}
    for f, kind in events:
        ch = CHANNEL
        while used.get((ch, f)):
            ch += 1
        s = st.new_sound('SFX? %s' % kind, sfx_path(kind), ch, f)
        s.volume = volume
        used[(ch, f)] = True
    return len(events)


def keep_sfx():
    n = 0
    for s in core.all_strips():
        if s.name.startswith('SFX?'):
            s.name = 'SFX ' + s.name[5:]
            n += 1
    return n


def clear_sfx(suggested_only=True):
    sc = bpy.context.scene
    st = core.strips(sc)
    n = 0
    for s in list(core.all_strips(sc)):
        if s.name.startswith('SFX?') or (not suggested_only and s.name.startswith('SFX')):
            st.remove(s)
            n += 1
    return n
