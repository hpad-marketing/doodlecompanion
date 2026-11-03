"""Reel Formats, Reaction and Duet layouts, Cast cameos and the Series Kit."""
import json
import math
import os

import bpy
from mathutils import Vector

from . import core, text_tools

# slot: (label, seconds, shot, headline placeholder or None)
FORMATS = {
    'STORYTIME': ('Storytime', [('Hook', 2.5, 'CLOSE', 'The day I...'), ('Setup', 8, 'MEDIUM', None),
                                ('Build', 14, 'MEDIUM', None), ('Twist', 6, 'CLOSE', None),
                                ('Payoff', 8, 'WIDE', None), ('Button', 3, 'CLOSE', None)]),
    'POV': ('POV skit', [('POV line', 2.5, 'MEDIUM', 'POV: you...'), ('Beat 1', 4, 'CLOSE', None),
                         ('Beat 2', 4, 'WIDE', None), ('Punchline', 4, 'CLOSE', None)]),
    'THREE': ('3 things', [('Hook', 2.5, 'CLOSE', '3 things that...'), ('Thing 1', 7, 'MEDIUM', '1'),
                           ('Thing 2', 7, 'MEDIUM', '2'), ('Thing 3', 7, 'CLOSE', '3'),
                           ('Wrap up', 4, 'WIDE', None)]),
    'MYTH': ('Myth vs fact', [('Myth', 3, 'MEDIUM', 'Myth:'), ('Why people think it', 6, 'MEDIUM', None),
                              ('Fact', 3, 'CLOSE', 'Fact:'), ('Proof', 8, 'MEDIUM', None), ('Button', 3, 'CLOSE', None)]),
    'BEFORE_AFTER': ('Before and after', [('Before', 4, 'WIDE', 'Before'), ('The change', 3, 'CLOSE', None),
                                          ('After', 5, 'WIDE', 'After'), ('Reaction', 2.5, 'CLOSE', None)]),
    'HOT_TAKE': ('Hot take', [('The take', 2.5, 'CLOSE', 'Hot take:'), ('Why', 8, 'MEDIUM', None),
                              ('Pushback', 4, 'WIDE', None), ('Double down', 4, 'CLOSE', None)]),
}
SHOT_FILL = {'WIDE': 0.22, 'MEDIUM': 0.30, 'CLOSE': 0.40}  # head height as a share of the frame
HEAD_V = 0.36   # face sits in the upper third, leaving room for captions below


def script_lines(sc=None):
    t = bpy.data.texts.get('Reel Script')
    if not t:
        return []
    return [l.strip() for l in t.as_string().split('\n') if l.strip()]


def frame_shot(cam, lead, shot, frame, sc=None, key=True):
    """Move the camera (no tilt) so the head fills SHOT_FILL of the frame at HEAD_V."""
    sc = sc or bpy.context.scene
    if lead is None:
        return
    pts = core.head_points(lead)
    zs = [p.z for p in pts]
    head_h = max(0.15, max(zs) - min(zs))
    target = core.head_center(lead)
    rot = cam.matrix_world.to_quaternion()
    fwd = rot @ Vector((0, 0, -1))
    up = rot @ Vector((0, 1, 0))
    if cam.data.type == 'ORTHO':
        aspect = sc.render.resolution_x / max(1, sc.render.resolution_y)
        frame_h = head_h / SHOT_FILL[shot]
        cam.data.ortho_scale = frame_h if aspect < 1 else frame_h * aspect
        dist = max(1.0, (target - cam.location).dot(fwd))
        cam.location = target - fwd * dist - up * ((0.5 - HEAD_V) * frame_h)
        if key:
            cam.keyframe_insert('location', frame=frame)
            cam.data.keyframe_insert('ortho_scale', frame=frame)
        return
    hw, hh = core.frame_half(1.0, cam, sc)
    dist = head_h / (SHOT_FILL[shot] * 2 * hh)
    loc = target - fwd * dist - up * ((0.5 - HEAD_V) * 2 * hh * dist)
    cam.location = loc
    if key:
        cam.keyframe_insert('location', frame=frame)


def build_format(kind, use_script=True):
    sc = bpy.context.scene
    st = core.settings(sc)
    label, slots = FORMATS[kind]
    core.set_vertical(sc)
    cam = core.ensure_camera(sc)
    cam.data.sensor_fit = 'AUTO'
    lead = core.lead_character(sc)
    lines = script_lines(sc) if use_script else []
    for m in [m for m in sc.timeline_markers if m.name.startswith('Slot: ')]:
        sc.timeline_markers.remove(m)
    for r in core.items('slot_text', sc):
        text_tools._delete_tree(r)
    f = sc.frame_start
    for i, (name, secs, shot, head) in enumerate(slots):
        line = lines[i] if i < len(lines) else ''
        if line:  # time the slot to the line: about 2 words a second, never shorter than the template
            secs = max(secs * 0.6, len(line.split()) / 2.0 + 0.6)
        n = core.sec(secs)
        sc.timeline_markers.new('Slot: ' + name, frame=f)
        frame_shot(cam, lead, shot, f, sc)
        if head:
            words = head if not line or head in ('1', '2', '3') else line
            if head in ('Myth:', 'Fact:', 'Hot take:', 'Before', 'After') and line:
                words = head + ' ' + line if head.endswith(':') else head
            r = headline(words, f, f + n)
            r['ss_slot'] = name
            if lead:
                _clear_headline(cam, lead, sc, f, r)
        f += n
    # hard cuts between shots
    for fc in core.fcurves(cam) + core.fcurves(cam.data):
        for k in fc.keyframe_points:
            k.interpolation = 'CONSTANT'
    sc.frame_end = f - 1
    st.reel_format = kind
    return label, len(slots), (f - sc.frame_start) / core.fps(sc)


def _clear_headline(cam, lead, sc, f, root):
    """Lower the character in this slot until the ears clear the headline (camera stays level)."""
    sc.frame_set(f)
    bottom = root['ss_v'] + core.text_dims(next(o for o in root.children_recursive if o.type == 'FONT'))[1] * 0.5 + 0.02
    u0, v0, u1, v1 = core.body_rect(lead, cam, sc)
    need = bottom - v0
    if need <= 0:
        return
    up = cam.matrix_world.to_quaternion() @ Vector((0, 1, 0))
    _, _, z = core.to_frame(core.head_center(lead))
    cam.location += up * (need * 2 * core.frame_half(z, cam, sc)[1])
    cam.keyframe_insert('location', frame=f)


def headline(words, start, end):
    sc = bpy.context.scene
    top = core.safe(sc)[0]
    root, pop = core.item('Headline', 0.5, max(top + 0.07, 0.19), kind='slot_text', start=start, end=end)
    aspect = sc.render.resolution_x / sc.render.resolution_y
    lines = text_tools._wrap(words, 14)
    t = core.text('\n'.join(lines[:2]), pop, size=0.09, kind='headline', fill='mustard', outline='ink', name='Headline text')
    w, h = core.text_dims(t)
    if w > aspect * 0.84:
        s = aspect * 0.84 / w
        t.data.size *= s
        o = bpy.data.objects.get(t.get('ss_outline', ''))
        if o:
            o.data.size *= s
            o.data.bevel_depth *= s
    core.key_pop(root, start, end, length=5)
    return root


# ================================================================== reaction / duet
def _media_plane(path, parent, h, border=True):
    img = bpy.data.images.load(path, check_existing=True)
    movie = img.source == 'MOVIE'
    w0, h0 = img.size[:] if img.size[0] else (1080, 1920)
    w = h * w0 / max(1, h0)
    me = bpy.data.meshes.new('Clip')
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [], [[0, 1, 2, 3]])
    uv = me.uv_layers.new()
    for loop, co in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = co
    m = bpy.data.materials.new('SS Clip')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = img
    if movie:
        tx.image_user.frame_duration = img.frame_duration
        tx.image_user.frame_start = bpy.context.scene.frame_current
        tx.image_user.use_auto_refresh = True
    nt.links.new(tx.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], out.inputs[0])
    me.materials.append(m)
    ob = core.link(bpy.data.objects.new('Clip', me), parent)
    if border:
        core.poly(core.rounded_rect(w, h, 0.004, 1), parent, cyclic=True, name='Clip border')
    return ob, w


def add_reaction(path, layout='PIP', side='AUTO', border=True, react_at=None):
    """Put a clip/screenshot on screen and keep the character clear of it."""
    sc = bpy.context.scene
    core.set_vertical(sc)
    cam = core.ensure_camera(sc)
    lead = core.lead_character(sc)
    for r in core.items('react', sc):
        text_tools._delete_tree(r)
    aspect = sc.render.resolution_x / sc.render.resolution_y
    top, bottom, left, right = core.safe(sc)
    if layout == 'SPLIT':
        root, pop = core.item('Reaction clip', 0.5, 0.25, kind='react', depth=core.settings(sc).overlay_depth * 1.02)
        ob, w = _media_plane(path, pop, 0.5, border)
        if w > aspect:
            s = aspect / w
            for c in pop.children:
                c.scale = (s, s, 1)
        if lead:   # character in the lower half
            _frame_lower(cam, lead, sc)
    elif layout == 'PIP':
        if side == 'AUTO' and lead:
            u0, v0, u1, v1 = core.body_rect(lead)
            side = 'LEFT' if (u0 + u1) / 2 > 0.5 else 'RIGHT'
        side = 'LEFT' if side == 'AUTO' else side
        h = 0.24
        root, pop = core.item('Reaction clip', 0.5, 0.5, kind='react')
        ob, w = _media_plane(path, pop, h, border)
        maxw = aspect * 0.46   # never wider than about half the frame
        if w > maxw:
            s = maxw / w
            for c in pop.children:
                c.scale = (s, s, 1)
            w, h = w * s, h * s
        root['ss_v'] = top + h / 2 + 0.015
        root['ss_u'] = left + w / aspect / 2 + 0.01 if side == 'LEFT' else 1 - right - w / aspect / 2 - 0.01
        core.place(root)
        if lead:
            _clear_face(cam, lead, sc, root['ss_u'] - w / aspect / 2, root['ss_u'] + w / aspect / 2, top + h + 0.03)
    else:  # BOARD: a doodle board in the set, beside the character
        root, pop = core.item('Reaction board', 0.68 if side != 'LEFT' else 0.32, 0.42, kind='react',
                              depth=core.settings(sc).overlay_depth * 2.5)
        ob, w = _media_plane(path, pop, 0.3, True)
        core.panel(w * 1.12, 0.3 * 1.15, pop, fill='mustard', name='Board')
        for c in pop.children:
            if c.name.startswith('Board'):
                c.location.z = -0.004
        if lead and react_at is None:
            pid = core.lib_find('motion', ('point',))
            if pid:
                try:
                    core.doodle_library().insert(pid, frame=sc.frame_current)
                except Exception:
                    pass
    if react_at is not None and lead:
        fid = core.lib_find('expression', ('surpris', 'shock', 'gasp', 'wow'))
        if fid:
            try:
                core.doodle_library().insert(fid, frame=react_at)
            except Exception:
                pass
        text_tools.add_sticker('BURST', frame=react_at)
    root['ss_layout'] = layout
    return root


def _shift_needed(cam, lead, sc, cu0, cu1, cv1):
    """How far (in frame heights) the face must drop to clear a box at the top, over the whole shot."""
    need = 0.0
    step = max(1, core.sec(0.5, sc))
    for f in range(sc.frame_start, sc.frame_end + 1, step):
        u0, v0, u1, v1 = core.head_rect(lead, cam, sc, frame=f)
        eye_top = v0 + (v1 - v0) * 0.3   # ear tips may tuck under the clip; eyes and mouth never
        if not (u1 < cu0 or u0 > cu1):
            need = max(need, cv1 - eye_top)
    return need


def _clear_face(cam, lead, sc, cu0, cu1, cv1):
    need = _shift_needed(cam, lead, sc, cu0, cu1, cv1)
    if need <= 0:
        return 0.0
    up = cam.matrix_world.to_quaternion() @ Vector((0, 1, 0))
    _, _, z = core.to_frame(core.head_center(lead))
    core.move_camera(cam, up * (need * 2 * core.frame_half(z, cam, sc)[1]))
    return need


def _frame_lower(cam, lead, sc):
    rot = cam.matrix_world.to_quaternion()
    up = rot @ Vector((0, 1, 0))
    u0, v0, u1, v1 = core.head_rect(lead)
    _, _, z = core.to_frame(core.head_center(lead))
    hw, hh = core.frame_half(z, cam, sc)
    want = 0.66
    core.move_camera(cam, up * ((((v0 + v1) / 2) - want) * 2 * hh))


# ================================================================== cameos
CAMEO_REACTIONS = {
    'SIDE_EYE': ('Side-eye', ('side eye', 'side-eye', 'suspicious', 'skeptic', 'unimpressed')),
    'GASP': ('Gasp', ('gasp', 'shock', 'surpris', 'wow')),
    'SLOW_CLAP': ('Slow clap', ('slow clap', 'clap')),
    'LAUGH': ('Laugh', ('laugh', 'lol', 'giggle')),
}


def cast_files():
    p = core.prefs()
    tca = os.path.join(os.path.expanduser('~'), 'Documents', 'Talking Character App')
    dirs = [bpy.path.abspath(p.cast_dir)] if p and p.cast_dir else []
    dirs += [os.environ.get('SS_CAST_DIR', ''), os.path.join(tca, 'animal-cast'), os.path.join(tca, 'blender-cast'),
             os.path.join(tca, 'blender-bunny', 'animal-cast')]
    out = {}
    for d in [d for d in dirs if d and os.path.isdir(d)]:
        for f in sorted(os.listdir(d)):
            if f.lower().endswith('.blend') and f[:-6].lower() not in out:
                out[f[:-6].lower()] = os.path.join(d, f)
    return out


def _append_character(path):
    """Append every object of a character file (not its cameras or lights) into a Cameos collection."""
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    c = core.coll('Cameos')
    obs = []
    main = bpy.context.scene.camera
    for o in dst.objects:
        if o is None:
            continue
        if o.type in ('CAMERA', 'LIGHT'):
            if o.type == 'CAMERA' and main:
                o.user_remap(main)   # the ink outline looks at "the camera": point it at ours
            bpy.data.objects.remove(o)
            continue
        c.objects.link(o)
        obs.append(o)
    rig = next((o for o in obs if o.type == 'ARMATURE' and o.parent is None), None) or \
        next((o for o in obs if o.type == 'ARMATURE'), None)
    return rig, obs


def add_cameo(character, reaction='SIDE_EYE', seconds=1.2, frame=None):
    sc = bpy.context.scene
    f = sc.frame_current if frame is None else frame
    n = core.sec(seconds)
    main = core.ensure_camera(sc)
    lead = core.lead_character(sc)
    rig = next((o for o in sc.objects if o.type == 'ARMATURE' and o.get('ss_cameo') == character), None)
    if rig is None:
        files = cast_files()
        if character not in files:
            raise RuntimeError('%s.blend not found in the cast folder (set it in the add-on preferences).' % character.title())
        rig, obs = _append_character(files[character])
        if rig is None:
            raise RuntimeError('No rig found in %s.blend.' % character)
        rig['ss_cameo'] = character
        # every cameo gets its own spot, alternating sides, so the cast never overlap
        n_cast = sum(1 for o in sc.objects if o.type == 'ARMATURE' and o.get('ss_cameo')) - 1
        x = 1.8 * (1 + n_cast // 2) * (1 if n_cast % 2 == 0 else -1)
        side = Vector((x, 0.4, 0)) if lead else Vector((x, 0, 0))
        base = lead.matrix_world.translation if lead else Vector()
        rig.location = base + side
        rig.rotation_euler = lead.rotation_euler.copy() if lead else rig.rotation_euler
    bpy.context.view_layer.update()
    cam = bpy.data.objects.get('Cameo cam ' + character)
    if not cam:
        cam = bpy.data.objects.new('Cameo cam ' + character, main.data.copy())
        cam.data.animation_data_clear()   # its own framing, not the main camera's keyed zoom
        core.coll('Cameos').objects.link(cam)
    cam.rotation_euler = main.rotation_euler.copy()
    cam.location = main.location.copy()
    frame_shot(cam, rig, 'MEDIUM', f, sc, key=False)   # whole head in frame, ears included
    # the cut: cameo camera, then straight back to the main shot
    keep = [m for m in sc.timeline_markers if m.camera]
    if not any(m.frame == sc.frame_start for m in keep):
        m0 = sc.timeline_markers.new('Main', frame=sc.frame_start)
        m0.camera = main
    m1 = sc.timeline_markers.new('Cameo: ' + character.title(), frame=f)
    m1.camera = cam
    back = max((m for m in keep if m.frame <= f), key=lambda m: m.frame, default=None)
    m2 = sc.timeline_markers.new('Back', frame=f + n)
    m2.camera = back.camera if back else main
    # the reaction itself, from the Doodle Library when it's installed
    label, words = CAMEO_REACTIONS[reaction]
    used = None
    dl = core.doodle_library()
    if dl:
        prev = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = rig
        for cat in (('motion', 'expression') if reaction == 'SLOW_CLAP' else ('expression', 'motion')):
            iid = core.lib_find(cat, words)
            if iid:
                try:
                    dl.insert(iid, frame=f)
                    used = iid
                    break
                except Exception:
                    continue
        bpy.context.view_layer.objects.active = prev
    if used is None:
        _fallback_reaction(rig, reaction, f, n)
    return label, used


def _fallback_reaction(rig, reaction, f, n):
    pb = core._head_bone(rig)
    if not pb:
        return
    pb.rotation_mode = 'XYZ'
    base = pb.rotation_euler.copy()
    turn = {'SIDE_EYE': (0, 0, math.radians(14)), 'GASP': (math.radians(-8), 0, 0),
            'SLOW_CLAP': (math.radians(4), 0, 0), 'LAUGH': (math.radians(-6), 0, math.radians(4))}[reaction]
    for fr, amt in ((f, 0.0), (f + 4, 1.0), (f + n - 2, 1.0), (f + n, 0.0)):
        pb.rotation_euler = (base.x + turn[0] * amt, base.y + turn[1] * amt, base.z + turn[2] * amt)
        pb.keyframe_insert('rotation_euler', frame=fr)
    pb.rotation_euler = base


# ================================================================== series kit
def series_file():
    d = bpy.utils.user_resource('CONFIG', path='social_studio', create=True)
    return os.path.join(d, 'series.json')


def load_series():
    try:
        with open(series_file()) as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_series(data):
    with open(series_file(), 'w') as fh:
        json.dump(data, fh, indent=1)


def capture_look(sc):
    w = sc.world
    look = {'view_transform': sc.view_settings.view_transform, 'look': sc.view_settings.look,
            'exposure': sc.view_settings.exposure, 'fps': sc.render.fps, 'engine': sc.render.engine}
    if w and w.use_nodes and w.node_tree.nodes.get('Background'):
        look['world'] = list(w.node_tree.nodes['Background'].inputs[0].default_value)
    if sc.camera:
        look['lens'] = sc.camera.data.lens
    return look


def apply_look(sc, look):
    for k in ('view_transform', 'look', 'exposure'):
        if k in look:
            try:
                setattr(sc.view_settings, k, look[k])
            except Exception:
                pass
    if 'fps' in look:
        sc.render.fps = look['fps']
    if 'engine' in look:
        try:
            sc.render.engine = look['engine']
        except Exception:
            pass
    w = sc.world
    if 'world' in look and w and w.use_nodes and w.node_tree.nodes.get('Background'):
        w.node_tree.nodes['Background'].inputs[0].default_value = look['world']
    if 'lens' in look and sc.camera:
        sc.camera.data.lens = look['lens']


def save_current_series():
    sc = bpy.context.scene
    st = core.settings(sc)
    name = st.series_name.strip()
    if not name:
        raise RuntimeError('Give the series a name first.')
    data = load_series()
    s = data.get(name, {'episode': 0})
    s.update({'intro': st.series_intro, 'intro_seconds': st.series_intro_seconds, 'end': st.series_end,
              'numbering': st.numbering, 'look': capture_look(sc)})
    data[name] = s
    save_series(data)
    return s


def new_episode():
    sc = bpy.context.scene
    st = core.settings(sc)
    data = load_series()
    name = st.series_name.strip()
    if name not in data:
        save_current_series()
        data = load_series()
    s = data[name]
    s['episode'] = int(s.get('episode', 0)) + 1
    save_series(data)
    st.episode = s['episode']
    st.numbering = s.get('numbering', 'EP')
    apply_look(sc, s.get('look', {}))
    old_end_card = core.items('seriesend', sc)
    end_start = int(old_end_card[0]['ss_start']) if old_end_card else sc.frame_end + 1
    for k in ('titlecard', 'seriesend'):
        for r in core.items(k, sc):
            text_tools._delete_tree(r)
    ep = core.episode_label(st, st.episode)
    intro = core.sec(s.get('intro_seconds', 1.2))
    title = (s.get('intro') or '{series}').format(series=name, ep=ep)
    title = title if ep in title else '%s\n%s' % (title, ep)
    tc = text_tools.add_card(title, sc.frame_start, intro, kind='titlecard')
    try:
        from . import timing
        core.strips(sc).new_sound('SFX intro', timing.sfx_path('whoosh'), timing.CHANNEL - 1, sc.frame_start)
    except Exception:
        pass
    end_text = (s.get('end') or 'Part {next} next').format(series=name, next=st.episode + 1, ep=ep)
    length = core.sec(1.5)
    ec = text_tools.add_card(end_text, end_start, length, kind='seriesend')
    sc.frame_end = end_start + length - 1
    sc.name = core.project_name(sc)[:60]
    return ep, tc, ec
