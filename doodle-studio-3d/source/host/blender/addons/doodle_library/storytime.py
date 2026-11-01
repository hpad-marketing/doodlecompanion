"""Storytime kit: text chats, pinned labels and arrows, journey maps, time-skip cards, an
opt-in horror light kit, and the end screen with a subscribe card.

Everything is ink and mustard, uses the open-source fonts that ship in the library
(Patrick Hand, Gochi Hand, Bangers: SIL Open Font License) and the library's own CC0 sounds,
all read from the library folder: nothing is ever downloaded.

    st.chat([('them', 'you up?'), ('me', 'no')], frame=24)
    st.label(bpy.data.objects['prop-mug'], 'still hot', frame=30)
    st.journey(['Pune', 'Goa', 'Hampi'], frame=1, length=96)
    st.time_skip('3 hours later', frame=120)
    st.horror(True, frame=200)          # off unless you turn it on
    st.end_screen(frame=900)
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

from . import paths, style, text3d
from . import gnodes

FONTS = {'hand': 'PatrickHand-Regular.ttf', 'marker': 'GochiHand-Regular.ttf', 'headline': 'Bangers-Regular.ttf'}
SOUNDS = ('pop', 'message', 'typing', 'whoosh', 'boing', 'click', 'bell', 'pin', 'draw', 'horror_drone', 'thunder',
          'sting')
TAG = 'dsl_story'


# ---------------------------------------------------------------- shared bits
def font_path(kind='hand'):
    return paths.lib_path(os.path.join('storytime', 'fonts', FONTS.get(kind, kind)))


def sound(name, frame, channel=None, volume=0.8):
    """Drop one of the kit's CC0 sounds into the video sequencer at `frame`."""
    sc = bpy.context.scene
    p = paths.lib_path(os.path.join('storytime', 'sounds', name + '.wav'))
    if not os.path.exists(p):
        print('Doodle Library: no sound', p)
        return None
    se = sc.sequence_editor or sc.sequence_editor_create()
    strips = se.strips if hasattr(se, 'strips') else se.sequences  # an empty 5.x strips list is falsy
    ch = channel or (3 + len([s for s in strips if s.get(TAG)]) % 6)
    s = strips.new_sound('%s %d' % (name, int(frame)), p, ch, int(frame))
    s.volume = volume
    s[TAG] = name
    return s


def _coll():
    from .assets import target_collection
    return target_collection('Doodle Story')


def _mat(kind):
    m = style.materials()
    return m['ink'] if kind == 'ink' else m['mustard']


def _rounded(w, h, r, seg=6):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def panel(name, w, h, fill='mustard', r=None, depth=0.01, tail=None):
    """A flat rounded card standing up (front faces -y), ink outlined like everything else."""
    r = min(w, h) * 0.18 if r is None else r
    pts = _rounded(w, h, r)
    if tail:  # little speech tail at the bottom left or right
        sx = -1 if tail == 'left' else 1
        k = len(pts) * 3 // 4 if tail == 'right' else len(pts) // 2
        pts = pts[:k] + [(sx * (w / 2 - r * 0.5), -h / 2 - r * 0.8)] + pts[k:]
    me = bpy.data.meshes.new(name)
    vs = [(x, -depth / 2, z) for x, z in pts] + [(x, depth / 2, z) for x, z in pts]
    n = len(pts)
    faces = [list(range(n))[::-1], list(range(n, 2 * n))]
    faces += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    me.from_pydata(vs, [], faces)
    me.validate()
    me.materials.append(_mat(fill))
    ob = bpy.data.objects.new(name, me)
    _coll().objects.link(ob)
    style.apply_style(ob, bpy.context.scene.camera, seed=0.4)
    ob[TAG] = name
    return ob


def words(text, size=0.08, fill='ink', font='hand', name=None):
    t = text3d.add_text(text, kind='flat', name=name or ('Text ' + text[:16]), fill=fill, font=font_path(font))
    mod = text3d.text_modifier(t)
    ids = text3d._ids(mod)
    gnodes.gn_set(mod, ids['Size'], size)
    gnodes.gn_set(mod, ids['Depth'], size * 0.08)
    gnodes.gn_set(mod, ids['Wobble'], 0.0)
    ink = t.modifiers.get(style.MOD_NAME)
    if ink:  # flat letters read cleaner without the ink shell (it fills small counters in)
        t.modifiers.remove(ink)
    t[TAG] = 'text'
    return t


def _stick(child, parent, loc):
    child.parent = parent
    child.matrix_parent_inverse = Matrix.Identity(4)
    child.location = loc


def pop(ob, frame, length=6, sfx='pop'):
    """Grow in past full size and settle (keys scale); plays a pop."""
    s = ob.scale.copy()
    for df, k in ((-1, 0.0), (0, 0.01), (length * 0.6, 1.15), (length, 1.0)):
        ob.scale = s * k
        ob.keyframe_insert('scale', frame=frame + df)
    ob.scale = s
    if sfx:
        sound(sfx, frame)
    return ob


def hide_after(ob, frame):
    for f, v in ((frame - 1, False), (frame, True)):
        ob.hide_render = ob.hide_viewport = v
        ob.keyframe_insert('hide_render', frame=f)
        ob.keyframe_insert('hide_viewport', frame=f)
    ob.hide_render = ob.hide_viewport = False


def show_between(root, start, end=None):
    """Key the whole card (and everything stuck on it) to show only from `start` to `end`."""
    for o in [root] + list(root.children_recursive):
        keys = [(start - 1, True), (start, False)] + ([(end, False), (end + 1, True)] if end else [])
        for f, v in keys:
            o.hide_render = o.hide_viewport = v
            o.keyframe_insert('hide_render', frame=f)
            o.keyframe_insert('hide_viewport', frame=f)
        o.hide_render = o.hide_viewport = False
        if o.animation_data and o.animation_data.action:
            from .motions import _fcurves
            for fc in _fcurves(o):
                if fc.data_path.startswith('hide_'):
                    for k in fc.keyframe_points:
                        k.interpolation = 'CONSTANT'


def on_camera(ob, depth=None, x=0.0, z=0.0, cam=None):
    """Pin a card to the camera so it stays put on screen whatever the camera does.
    x and z are fractions of the half frame (-1..1)."""
    cam = cam or bpy.context.scene.camera
    d = depth or 1.0
    sc = bpy.context.scene
    aspect = sc.render.resolution_x / max(1, sc.render.resolution_y)
    long_half = math.tan(cam.data.angle / 2) * d
    hw, hh = (long_half * aspect, long_half) if aspect < 1 else (long_half, long_half / aspect)
    ob.parent = cam
    ob.matrix_parent_inverse = Matrix.Identity(4)
    # camera looks down its -Z; our cards face -y, so turn them to face the lens (-y -> +z)
    ob.rotation_euler = (math.radians(-90), 0, 0)
    ob.location = (x * hw, z * hh, -d)
    return hw, hh


def frame_size(depth=1.0, cam=None):
    cam = cam or bpy.context.scene.camera
    sc = bpy.context.scene
    aspect = sc.render.resolution_x / max(1, sc.render.resolution_y)
    long_half = math.tan(cam.data.angle / 2) * depth
    return (long_half * aspect, long_half) if aspect < 1 else (long_half, long_half / aspect)


# ---------------------------------------------------------------- 1. text chat scenes
def chat(messages, frame=None, gap=18, title='', typing=True, depth=1.2, hold=48):
    """A phone chat that fills in message by message. messages: [(who, text)], who is 'me'
    (mustard bubble, right) or anyone else (ink bubble, left). Pinned to the camera."""
    sc = bpy.context.scene
    f = sc.frame_current if frame is None else frame
    hw, hh = frame_size(depth)
    pw, ph = hw * 1.3, hh * 1.5
    phone = panel('Chat phone', pw, ph, 'ink', r=pw * 0.12, depth=0.02)
    on_camera(phone, depth, 0, 0.05)
    screen = panel('Chat screen', pw * 0.9, ph * 0.86, 'mustard', r=pw * 0.06, depth=0.004)
    _stick(screen, phone, (0, -0.013, 0))
    if title:
        tt = words(title, size=ph * 0.04, font='hand')
        _stick(tt, phone, (0, -0.02, ph * 0.38))
    y = ph * 0.32
    out = [phone]
    for i, (who, text) in enumerate(messages):
        me = who == 'me'
        size = ph * 0.035
        lines = max(1, math.ceil(len(text) / 22))
        bw = min(pw * 0.7, size * 0.55 * min(len(text), 22) + size * 1.4)
        bh = size * (1.5 * lines + 0.9)
        y -= bh / 2
        b = panel('Chat %d' % i, bw, bh, 'mustard' if me else 'ink', depth=0.004, tail='right' if me else 'left')
        x = (pw * 0.4 - bw / 2) if me else (-pw * 0.4 + bw / 2)
        _stick(b, phone, (x, -0.02, y))
        if me:  # mustard on a mustard screen: a solid ink rim so it reads at phone size
            rim = panel('Chat rim %d' % i, bw + size * 0.35, bh + size * 0.35, 'ink', depth=0.003, tail='right')
            _stick(rim, b, (0, 0.0025, 0))
        wrapped = '|'.join(_wrap(text, 22))
        t = words(wrapped, size=size, fill='ink' if me else 'mustard')
        _stick(t, b, (0, -0.004, -size * 0.3))
        at = f + i * gap
        if typing and not me:
            dots = panel('Typing %d' % i, size * 2.6, size * 1.3, 'ink', depth=0.004)
            _stick(dots, phone, (-pw * 0.4 + size * 1.3, -0.02, y))
            pop(dots, at - 10, sfx='typing')
            hide_after(dots, at)
        pop(b, at, sfx='message' if not me else 'pop')
        y -= bh / 2 + size * 0.6
        out.append(b)
    show_between(phone, f - 12, f + (len(messages) - 1) * gap + hold)
    return out


def _wrap(text, n):
    lines, line = [], ''
    for w in text.split():
        if len(line) + len(w) + 1 > n and line:
            lines.append(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    if line:
        lines.append(line)
    return lines


# ---------------------------------------------------------------- 2. pinned labels and arrows
def label(target, text, frame=None, side='right', distance=0.35, size=0.07):
    """A hand-lettered label with a curved arrow pointing at an object (or a point).
    It follows the object if the object moves."""
    sc = bpy.context.scene
    f = sc.frame_current if frame is None else frame
    tp = target.matrix_world.translation if hasattr(target, 'matrix_world') else Vector(target)
    sx = 1 if side == 'right' else -1
    at = tp + Vector((sx * distance, -0.05, distance * 0.6))
    t = words(text, size=size, font='marker')
    t.location = at
    # arrow: a gentle curve from the label to just short of the target, with a head
    a = at + Vector((-sx * size * 0.4 * len(text) * 0.25, 0, -size * 0.6))
    b = tp + (a - tp).normalized() * 0.06
    mid = (a + b) / 2 + Vector((0, -0.02, 0.08))
    cu = bpy.data.curves.new('Arrow ' + text[:12], 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.006
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(2)
    for p, co in zip(sp.bezier_points, (a, mid, b)):
        p.co = co
        p.handle_left_type = p.handle_right_type = 'AUTO'
    cu.materials.append(_mat('ink'))
    arrow = bpy.data.objects.new('Arrow ' + text[:12], cu)
    _coll().objects.link(arrow)
    d = (b - mid).normalized()
    head = bpy.data.meshes.new('Arrow head')
    side_v = d.cross(Vector((0, -1, 0))).normalized() * 0.03
    head.from_pydata([b, b - d * 0.05 + side_v, b - d * 0.05 - side_v], [], [(0, 1, 2)])
    head.materials.append(_mat('ink'))
    ho = bpy.data.objects.new('Arrow head', head)
    _coll().objects.link(ho)
    ho.parent = arrow
    # the arrow draws on from the label to the target
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert('bevel_factor_end', frame=f)
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert('bevel_factor_end', frame=f + 8)
    if hasattr(target, 'matrix_world'):
        for o in (t, arrow):
            c = o.constraints.new('CHILD_OF')
            c.name = 'DSL follow'
            c.target = target
            c.inverse_matrix = target.matrix_world.inverted()
    pop(t, f, sfx='pin')
    ho.hide_render = True
    ho.keyframe_insert('hide_render', frame=f + 7)
    ho.hide_render = False
    ho.keyframe_insert('hide_render', frame=f + 8)
    for o in (t, arrow, ho):
        o[TAG] = 'label'
    return t, arrow


# ---------------------------------------------------------------- 3. journey map
def journey(stops, frame=None, length=96, depth=1.4, seed=3, hold=36):
    """A paper map with a dashed path that draws itself from stop to stop, a pin and a
    hand-written name at each stop, and a little marker travelling along. Camera-pinned."""
    import random
    rnd = random.Random(seed)
    sc = bpy.context.scene
    f = sc.frame_current if frame is None else frame
    hw, hh = frame_size(depth)
    W_, H_ = hw * 1.7, hh * 1.4
    paper = panel('Journey map', W_, H_, 'ink', r=W_ * 0.03, depth=0.004)
    on_camera(paper, depth, 0, 0)
    sheet = panel('Journey paper', W_ * 0.96, H_ * 0.96, 'mustard', r=W_ * 0.025, depth=0.004)
    _stick(sheet, paper, (0, -0.003, 0))
    n = max(2, len(stops))
    pts = []
    for i in range(n):
        u = i / (n - 1)
        x = -W_ * 0.36 + u * W_ * 0.72 + rnd.uniform(-0.05, 0.05) * W_
        z = H_ * (0.3 - 0.6 * u) + rnd.uniform(-0.12, 0.12) * H_ * (0 < i < n - 1)
        pts.append(Vector((x, -0.006, z)))
    cu = bpy.data.curves.new('Journey path', 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = W_ * 0.004
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(n - 1)
    for p, co in zip(sp.bezier_points, pts):
        p.co = co
        p.handle_left_type = p.handle_right_type = 'AUTO'
    cu.materials.append(_mat('ink'))
    path = bpy.data.objects.new('Journey path', cu)
    _coll().objects.link(path)
    _stick(path, paper, (0, -0.002, 0))
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert('bevel_factor_end', frame=f + 6)
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert('bevel_factor_end', frame=f + 6 + length)
    sound('draw', f + 6)
    marker = panel('Journey marker', W_ * 0.05, W_ * 0.05, 'ink', r=W_ * 0.025, depth=0.006)
    _stick(marker, paper, (0, -0.008, 0))
    c = marker.constraints.new('FOLLOW_PATH')
    c.target = path
    c.use_fixed_location = True
    c.offset_factor = 0.0
    c.keyframe_insert('offset_factor', frame=f + 6)
    c.offset_factor = 1.0
    c.keyframe_insert('offset_factor', frame=f + 6 + length)
    for i, (name, p) in enumerate(zip(stops, pts)):
        pin = panel('Pin %s' % name, W_ * 0.03, W_ * 0.045, 'ink', r=W_ * 0.015, depth=0.006, tail='left')
        _stick(pin, paper, p + Vector((0, -0.004, W_ * 0.03)))
        t = words(name, size=W_ * 0.045, font='marker')
        _stick(t, paper, p + Vector((0, -0.006, -W_ * 0.06)))
        at = f + 6 + int(length * i / (n - 1))
        pop(pin, at, sfx='pin')
        pop(t, at + 2, sfx=None)
    show_between(paper, f, f + 6 + length + hold)
    return paper


# ---------------------------------------------------------------- 4. time-skip cards
def time_skip(text='Later...', frame=None, length=36, fill='mustard'):
    """A full-frame card that wipes in, holds the words, and wipes out (whoosh both ways)."""
    sc = bpy.context.scene
    f = sc.frame_current if frame is None else frame
    depth = 0.6
    hw, hh = frame_size(depth)
    card = panel('Time skip', hw * 2.2, hh * 2.2, fill, r=0.001, depth=0.002)
    on_camera(card, depth)
    t = words(text, size=hh * 0.16, fill='ink' if fill == 'mustard' else 'mustard', font='headline')
    _stick(t, card, (0, -0.003, -hh * 0.05))
    for df, sx in ((-1, 0.0), (0, 0.001), (6, 1.0), (length - 6, 1.0), (length, 0.001)):
        card.scale = (sx, 1, 1)
        card.keyframe_insert('scale', frame=f + df)
    card.scale = (1, 1, 1)
    show_between(card, f, f + length)
    sound('whoosh', f)
    sound('whoosh', f + length - 6)
    return card


# ---------------------------------------------------------------- 5. horror light kit (opt-in)
def horror(on=True, frame=None, flicker=True):
    """Off by default. Turns the scene to night, lights Bunny from below, flickers every lamp,
    adds an ink vignette pinned to the camera and the low drone. on=False removes it all."""
    from . import lighting
    sc = bpy.context.scene
    for o in [o for o in bpy.data.objects if o.get(TAG) == 'horror']:
        bpy.data.objects.remove(o)
    if not on:
        lighting.set_time('day')
        sc['dsl_horror'] = False
        return None
    f = sc.frame_current if frame is None else frame
    lighting.set_time('night')
    ld = bpy.data.lights.new('Horror under-light', 'SPOT')
    ld.energy = 120
    ld.spot_size = math.radians(55)
    ld.color = (1.0, 0.85, 0.6)
    lo = bpy.data.objects.new('Horror under-light', ld)
    _coll().objects.link(lo)
    lo.location = (0, -0.6, 0.05)
    lo.rotation_euler = (math.radians(-60), 0, 0)  # aims up at his face
    lo[TAG] = 'horror'
    if flicker:
        for lamp in lighting.lamps():
            lighting.flicker(lamp, 0.85)
        lighting.flicker(lo, 0.5)
    depth = 0.7
    hw, hh = frame_size(depth)
    ring = bpy.data.meshes.new('Horror vignette')
    outer = [(hw * 1.8 * math.cos(a), hh * 1.8 * math.sin(a)) for a in [2 * math.pi * i / 48 for i in range(48)]]
    inner = [(hw * 1.18 * math.cos(a), hh * 1.15 * math.sin(a)) for a in [2 * math.pi * i / 48 for i in range(48)]]
    vs = [(x, 0, z) for x, z in outer] + [(x, 0, z) for x, z in inner]
    ring.from_pydata(vs, [], [(i, (i + 1) % 48, 48 + (i + 1) % 48, 48 + i) for i in range(48)])
    ring.materials.append(_mat('ink'))
    vo = bpy.data.objects.new('Horror vignette', ring)
    _coll().objects.link(vo)
    on_camera(vo, depth)
    vo[TAG] = 'horror'
    s = sound('horror_drone', f, volume=0.5)
    sc['dsl_horror'] = True
    return lo


# ---------------------------------------------------------------- 6. end screen and subscribe card
def end_screen(frame=None, length=240, channel='DeepInDoodles', subscribe_at=24):
    """YouTube-style end screen: two video slots, the channel name and a subscribe button
    that gets pressed (click + bell). Camera-pinned, ink and mustard."""
    sc = bpy.context.scene
    f = sc.frame_current if frame is None else frame
    depth = 0.9
    hw, hh = frame_size(depth)
    bg = panel('End screen', hw * 2.2, hh * 2.2, 'mustard', r=0.001, depth=0.002)
    on_camera(bg, depth)
    vw = hw * 1.5
    vh = vw * 9 / 16
    slots = []
    for i, z in enumerate((hh * 0.45, -hh * 0.05)):
        s = panel('Video slot %d' % (i + 1), vw, vh, 'ink', r=vw * 0.04, depth=0.004)
        _stick(s, bg, (0, -0.004, z))
        tri = bpy.data.meshes.new('Play %d' % (i + 1))
        k = vh * 0.18
        tri.from_pydata([(-k * 0.7, 0, -k), (-k * 0.7, 0, k), (k, 0, 0)], [], [(0, 1, 2)])
        tri.materials.append(_mat('mustard'))
        play = bpy.data.objects.new('Play %d' % (i + 1), tri)
        _coll().objects.link(play)
        _stick(play, s, (0, -0.004, 0))
        pop(s, f + 6 + i * 4, sfx=None)
        slots.append(s)
    name = words(channel, size=hh * 0.09, font='headline')
    _stick(name, bg, (0, -0.004, -hh * 0.48))
    btn = panel('Subscribe', hw * 1.0, hh * 0.13, 'ink', r=hh * 0.06, depth=0.006)
    _stick(btn, bg, (0, -0.006, -hh * 0.72))
    bt = words('SUBSCRIBE', size=hh * 0.06, fill='mustard', font='headline')
    _stick(bt, btn, (0, -0.004, -hh * 0.02))
    bell = panel('Bell', hh * 0.11, hh * 0.11, 'ink', r=hh * 0.05, depth=0.006)
    _stick(bell, bg, (hw * 0.62, -0.006, -hh * 0.72))
    pop(bg, f, sfx='sting')
    pop(btn, f + subscribe_at - 8, sfx=None)
    # the press: squash, release, then the bell rings
    p = f + subscribe_at
    for df, k in ((0, 1.0), (2, 0.86), (5, 1.04), (8, 1.0)):
        btn.scale = (k, 1, k)
        btn.keyframe_insert('scale', frame=p + df)
    btn.scale = (1, 1, 1)
    sound('click', p)
    for df, r in ((10, 0), (12, 18), (14, -15), (16, 10), (18, -6), (20, 0)):
        bell.rotation_euler[1] = math.radians(r)
        bell.keyframe_insert('rotation_euler', index=1, frame=p + df)
    sound('bell', p + 10)
    show_between(bg, f, f + length)
    return bg
