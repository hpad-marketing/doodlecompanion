"""Cover + grid preview, Carousel maker, Smart reframe, BTS Maker, Post package (+ optional Postiz)."""
import datetime
import glob
import json
import math
import os
import shutil

import bpy
import numpy as np
from mathutils import Vector

from . import core, text_tools

SIZES = {'REEL': ('Reels 9:16', 1080, 1920), 'FEED': ('Feed 4:5', 1080, 1350),
         'SQUARE': ('Square 1:1', 1080, 1080), 'WIDE': ('YouTube 16:9', 1920, 1080)}


# ================================================================== render helpers
class Keep:
    """Remember and restore render settings around a temporary render."""

    def __init__(self, sc):
        self.sc = sc
        r = sc.render
        self.v = (r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath, sc.camera, sc.frame_current,
                  r.image_settings.file_format, sc.frame_start, sc.frame_end, sc.frame_step)
        self.media = getattr(r.image_settings, 'media_type', None)

    def restore(self):
        r = self.sc.render
        (r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath, cam, f, fmt,
         self.sc.frame_start, self.sc.frame_end, self.sc.frame_step) = self.v
        if self.media and hasattr(r.image_settings, 'media_type'):
            try:
                r.image_settings.media_type = self.media
            except Exception:
                pass
        try:
            r.image_settings.file_format = fmt
        except Exception:
            pass
        self.sc.camera = cam
        self.sc.frame_set(f)
        core.layout(cam, self.sc)


def set_png(sc):
    s = sc.render.image_settings
    if hasattr(s, 'media_type'):
        try:
            s.media_type = 'IMAGE'
        except Exception:
            pass
    s.file_format = 'PNG'
    s.color_mode = 'RGB'


def set_mp4(sc):
    s = sc.render.image_settings
    if hasattr(s, 'media_type'):
        s.media_type = 'VIDEO'
    s.file_format = 'FFMPEG'
    ff = sc.render.ffmpeg
    ff.format = 'MPEG4'
    ff.codec = 'H264'
    ff.constant_rate_factor = 'HIGH'
    ff.audio_codec = 'AAC'
    ff.audio_bitrate = 192


def render_still(path, frame, w=None, h=None, cam=None, pct=100, show=()):
    sc = bpy.context.scene
    k = Keep(sc)
    try:
        if w:
            sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.resolution_percentage = pct
        if cam:
            sc.camera = cam
        sc.frame_set(frame)
        core.layout(sc.camera, sc)
        for r in show:
            core.pop_of(r).scale = (1, 1, 1)
        set_png(sc)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
    finally:
        for r in show:
            core.pop_of(r).scale = (0.0001,) * 3
        k.restore()
    return path


def final_video(sc=None):
    sc = sc or bpy.context.scene
    cands = []
    try:
        p = bpy.path.abspath(sc.render.frame_path(frame=sc.frame_start))
        if os.path.exists(p):
            cands.append(p)
    except Exception:
        pass
    d = core.project_dir(sc)
    cands += sorted(glob.glob(os.path.join(d, '*.mp4')), key=os.path.getmtime, reverse=True)
    cands = [c for c in cands if 'BTS' not in os.path.basename(c) and '_feed' not in c and '_square' not in c
             and '_wide' not in c]
    return cands[0] if cands else None


# ================================================================== cover
def _face_parts(rig):
    out = []
    if rig is None:
        return out
    for pb in rig.pose.bones:
        n = pb.name.lower()
        if any(w in n for w in ('mouth', 'jaw', 'brow', 'eye', 'lid', 'face')):
            out.append(pb.name)
    return out


def score_frames(step=None):
    """Frames where the face is clear, big and mid-expression."""
    sc = bpy.context.scene
    lead = core.lead_character(sc)
    cam = sc.camera
    if not cam:
        return []
    step = step or max(1, int(core.fps(sc) // 3))
    keyed = set()
    if lead:
        parts = _face_parts(lead)
        for fc in core.fcurves(lead):
            if any('"%s"' % p in fc.data_path for p in parts):
                keyed.update(int(k.co.x) for k in fc.keyframe_points)
        for o in lead.children:
            if o.type == 'MESH' and o.data.shape_keys:
                for fc in core.fcurves(o.data.shape_keys):
                    keyed.update(int(k.co.x) for k in fc.keyframe_points)
    caps = [(r.get('ss_start', 0), r.get('ss_end', 0)) for r in core.items('caption', sc)]
    keep = sc.frame_current
    out = []
    dg = bpy.context.evaluated_depsgraph_get()
    for f in range(sc.frame_start, sc.frame_end + 1, step):
        if any(r.get('ss_start', -1) <= f < r.get('ss_end', -1) for r in core.items(sc=sc)
               if r['ss_kind'] in ('endcard', 'titlecard', 'seriesend')):
            continue
        sc.frame_set(f)
        s = 0.0
        if lead:
            u0, v0, u1, v1 = core.head_rect(lead, cam, sc)
            inside = u0 > 0.02 and u1 < 0.98 and v0 > 0.02 and v1 < 0.98
            s += (v1 - v0) * 2 + (0.6 if inside else -1)
            s -= abs((u0 + u1) / 2 - 0.5)
            hc = core.head_center(lead)
            org = cam.matrix_world.translation
            d = hc - org
            hit, loc, nor, idx, ob, mx = sc.ray_cast(dg, org, d.normalized(), distance=d.length)
            if hit and ob and ob != lead and ob.parent != lead and not (ob.parent and ob.parent.parent == lead):
                s -= 0.8
            if any(abs(f - k) <= 4 for k in keyed):
                s += 0.35
        if any(a <= f < b for a, b in caps):
            s -= 0.05
        out.append((s, f))
    sc.frame_set(keep)
    out.sort(reverse=True)
    picks, gap = [], core.sec(1.0)
    for s, f in out:
        if all(abs(f - p) >= gap for p in picks):
            picks.append(f)
        if len(picks) == 3:
            break
    return picks


def suggest_covers():
    sc = bpy.context.scene
    st = core.settings(sc)
    frames = score_frames()
    d = core.work_dir(sc, 'cover')
    for i, f in enumerate(frames):
        p = os.path.join(d, 'candidate_%d.png' % (i + 1))
        render_still(p, f, pct=25)
        name = 'SS Cover %d' % (i + 1)
        im = bpy.data.images.get(name)
        if im:
            im.filepath = p
            im.reload()
        else:
            im = bpy.data.images.load(p)
            im.name = name
        im.preview_ensure()
        try:
            im.preview.reload()
        except Exception:
            pass
    st.cover_candidates = ','.join(str(f) for f in frames)
    if frames and st.cover_frame < 0:
        st.cover_frame = frames[0]
    return frames


def cover_title(text):
    for r in core.items('cover_title'):
        text_tools._delete_tree(r)
    if not text.strip():
        return None
    top = core.safe()[0]
    root, pop = core.item('Cover title', 0.5, top + 0.1, kind='cover_title')
    lines = text_tools._wrap(text.strip(), 12)
    core.text('\n'.join(lines[:3]), pop, size=0.08, kind='headline', fill='mustard', outline='ink', name='Cover title text')
    pop.scale = (0.0001,) * 3
    return root


def make_cover():
    sc = bpy.context.scene
    st = core.settings(sc)
    f = st.cover_frame if st.cover_frame >= 0 else sc.frame_current
    t = cover_title(st.cover_title)
    p = os.path.join(core.project_dir(sc), 'cover.png')
    render_still(p, f, 1080, 1920, show=[t] if t else [])
    grid = grid_preview(p)
    return p, grid


def _load_px(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    a = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)[::-1]  # top row first


def _tile(px, tw, th):
    h, w = px.shape[:2]
    ch = int(w * 4 / 3)  # IG profile grid shows a 3:4 crop from the middle
    if ch < h:
        y0 = (h - ch) // 2
        px = px[y0:y0 + ch]
    h, w = px.shape[:2]
    ys = (np.arange(th) * h / th).astype(int)
    xs = (np.arange(tw) * w / tw).astype(int)
    return px[ys][:, xs]


def grid_preview(cover):
    """Your new cover next to your last posts, as they'd sit on your profile."""
    ready = os.path.join(core.root_dir(), 'Ready to post')
    prev = sorted(glob.glob(os.path.join(ready, '*', 'cover.png')), key=os.path.getmtime, reverse=True)
    prev = [p for p in prev if os.path.abspath(p) != os.path.abspath(cover)][:5]
    tiles = [cover] + prev
    tw, th, gap = 360, 480, 6
    rows = max(1, math.ceil(len(tiles) / 3))
    W, H = 3 * tw + 2 * gap, rows * th + (rows - 1) * gap
    canvas = np.ones((H, W, 4), dtype=np.float32)
    canvas[..., :3] = core.hex_lin(core.INK)[:3]
    for i, p in enumerate(tiles):
        r, c = divmod(i, 3)
        try:
            t = _tile(_load_px(p), tw, th)
        except Exception:
            continue
        canvas[r * (th + gap):r * (th + gap) + th, c * (tw + gap):c * (tw + gap) + tw] = t
    out = os.path.join(core.project_dir(), 'grid_preview.png')
    name = 'SS Grid preview'
    im = bpy.data.images.get(name)
    if im:
        bpy.data.images.remove(im)
    im = bpy.data.images.new(name, W, H, alpha=False)
    im.pixels.foreach_set(canvas[::-1].reshape(-1))
    im.filepath_raw = out
    im.file_format = 'PNG'
    im.save()
    return out


# ================================================================== carousel
def carousel_lines():
    t = bpy.data.texts.get('Carousel')
    if t:
        return [l.strip() for l in t.as_string().split('\n') if l.strip()]
    return []


def make_carousel(count=None, position='BOTTOM', swipe=True):
    sc = bpy.context.scene
    st = core.settings(sc)
    lines = carousel_lines()
    n = max(4, min(10, count or st.carousel_count or len(lines) or 5))
    marks = sorted(m.frame for m in sc.timeline_markers if m.name.lower().startswith('slide'))
    if len(marks) >= n:
        frames = marks[:n]
    else:
        span = sc.frame_end - sc.frame_start
        frames = [int(sc.frame_start + span * (i + 0.5) / n) for i in range(n)]
    d = os.path.join(core.project_dir(sc), 'carousel')
    os.makedirs(d, exist_ok=True)
    for old in glob.glob(os.path.join(d, 'slide_*.png')):
        os.remove(old)
    k = Keep(sc)
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
    out = []
    try:
        top, bottom = core.safe(sc)[:2]
        for i, f in enumerate(frames):
            show = []
            line = lines[i] if i < len(lines) else ''
            if line:
                v = (1 - bottom - 0.1) if position == 'BOTTOM' else top + 0.08
                root, pop = core.item('Slide text %d' % (i + 1), 0.5, v, kind='slide_text')
                core.text('\n'.join(text_tools._wrap(line, 22)[:3]), pop, size=0.055, kind='headline',
                          fill='mustard', outline='ink')
                pop.scale = (0.0001,) * 3
                show.append(root)
            if swipe and i == 0:
                root, pop = core.item('Swipe arrow', 0.9, 0.5, kind='slide_text')
                core.poly(None, pop, splines=[[(x * 0.1, y * 0.1) for x, y in s] for s in text_tools._arrow()])
                pop.scale = (0.0001,) * 3
                show.append(root)
            p = os.path.join(d, 'slide_%02d.png' % (i + 1))
            sc.render.resolution_x, sc.render.resolution_y = 1080, 1350
            render_still(p, f, 1080, 1350, show=show)
            out.append(p)
    finally:
        for r in core.items('slide_text', sc):
            text_tools._delete_tree(r)
        k.restore()
    return out


# ================================================================== smart reframe
def _lens_for(cam_data, w, h):
    a = w / h
    return cam_data.lens * (9 / 16) if a > 1.01 else cam_data.lens


def twin(cam, kind):
    name = '%s · %s' % (cam.name, kind.lower())
    t = bpy.data.objects.get(name)
    if t:
        return t
    t = cam.copy()
    t.data = cam.data.copy()
    t.name = name
    if cam.animation_data and cam.animation_data.action:
        t.animation_data.action = cam.animation_data.action.copy()
        if hasattr(cam.animation_data, 'action_slot') and cam.animation_data.action_slot:
            try:
                t.animation_data.action_slot = t.animation_data.action.slots[0]
            except Exception:
                pass
    _, w, h = SIZES[kind]
    t.data.sensor_fit = 'AUTO'
    t.data.lens = _lens_for(cam.data, w, h)
    if cam.data.type == 'ORTHO':
        # AUTO fit puts ortho_scale on the longer side: keep the same frame height in every size
        k = (w / h) if w > h else 1.0
        t.data.ortho_scale = cam.data.ortho_scale * k
        ad = cam.data.animation_data
        if ad and ad.action:
            t.data.animation_data.action = ad.action.copy()
            try:
                if hasattr(ad, 'action_slot') and ad.action_slot:
                    t.data.animation_data.action_slot = t.data.animation_data.action.slots[0]
            except Exception:
                pass
            for fc in core.fcurves(t.data):
                if fc.data_path == 'ortho_scale':
                    for kp in fc.keyframe_points:
                        kp.co.y *= k
                        kp.handle_left.y *= k
                        kp.handle_right.y *= k
    t['ss_reframe'] = kind
    core.coll('Reframe cameras').objects.link(t)
    return t


def make_reframe_cameras(kinds):
    sc = bpy.context.scene
    main = core.ensure_camera(sc)
    cams = {main} | {m.camera for m in sc.timeline_markers if m.camera}
    made = []
    for k in kinds:
        if k == 'REEL':
            continue
        for c in cams:
            if not c.get('ss_reframe'):
                made.append(twin(c, k))
    return made


def render_sizes(kinds):
    sc = bpy.context.scene
    main = core.ensure_camera(sc)
    make_reframe_cameras(kinds)
    base = os.path.join(core.project_dir(sc), core.project_name(sc))
    k = Keep(sc)
    marks = [(m, m.camera) for m in sc.timeline_markers if m.camera]
    out = []
    try:
        for kind in kinds:
            _, w, h = SIZES[kind]
            sc.render.resolution_x, sc.render.resolution_y = w, h
            sc.render.resolution_percentage = 100
            get = (lambda c: c) if kind == 'REEL' else (lambda c: bpy.data.objects.get('%s · %s' % (c.name, kind.lower())) or c)
            for m, c in marks:
                m.camera = get(c)
            sc.camera = get(main)
            core.layout(sc.camera, sc)
            set_mp4(sc)
            path = base + ('' if kind == 'REEL' else '_' + kind.lower()) + '.mp4'
            sc.render.filepath = path
            sc.render.use_file_extension = False
            bpy.ops.render.render(animation=True)
            out.append(path)
    finally:
        for m, c in marks:
            m.camera = c
        k.restore()
    return out


# ================================================================== follow the active camera
def camera_at(sc, f):
    ms = [m for m in sc.timeline_markers if m.camera and m.frame <= f]
    return max(ms, key=lambda m: m.frame).camera if ms else sc.camera


@bpy.app.handlers.persistent
def follow_camera(sc, *args):
    try:
        its = core.items(sc=sc)
        if not its:
            return
        cam = camera_at(sc, sc.frame_current)
        if cam and its[0].parent != cam:
            for r in its:
                if r.get('ss_anchor') == 'caption':
                    continue
                core.place(r, cam, sc)
            for r in its:
                if r.get('ss_anchor') == 'caption':
                    core.place(r, cam, sc)
    except Exception:
        pass


# ================================================================== BTS
def _bts_cam(sc, lead):
    cam = bpy.data.objects.get('BTS front view')
    if cam:
        return cam
    cd = bpy.data.cameras.new('BTS front view')
    cd.lens = 24
    cam = bpy.data.objects.new('BTS front view', cd)
    core.coll('Reframe cameras').objects.link(cam)
    tgt = core.head_center(lead) if lead else Vector((0, 0, 1))
    main = sc.camera
    fwd = main.matrix_world.to_quaternion() @ Vector((0, 0, -1)) if main else Vector((0, 1, 0))
    side = fwd.cross(Vector((0, 0, 1))).normalized()
    cam.location = tgt - fwd * 4.5 + side * 1.6 + Vector((0, 0, 1.2))
    d = (tgt - cam.location)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return cam


def _screens(top_dir, bot_dir, step):
    """Inside Blender's window: grab the real interface, from the front and through the camera."""
    sc = bpy.context.scene
    win = bpy.context.window
    if not win:
        return False
    areas = [a for a in win.screen.areas if a.type == 'VIEW_3D']
    if not areas:
        return False
    area = max(areas, key=lambda a: a.width * a.height)
    space = area.spaces.active
    r3d = space.region_3d
    keep = (r3d.view_perspective, r3d.view_matrix.copy(), r3d.view_distance, r3d.view_location.copy(),
            r3d.view_rotation.copy(), space.shading.type)
    lead = core.lead_character(sc)
    tgt = core.head_center(lead) if lead else Vector((0, 0, 1))
    i = 0
    try:
        space.shading.type = 'SOLID'
        for f in range(sc.frame_start, sc.frame_end + 1, step):
            sc.frame_set(f)
            r3d.view_perspective = 'PERSP'
            r3d.view_location = tgt
            r3d.view_distance = 6.0
            main = sc.camera
            q = main.matrix_world.to_quaternion() if main else r3d.view_rotation
            r3d.view_rotation = q
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                bpy.ops.screen.screenshot_area(filepath=os.path.join(top_dir, '%05d.png' % i))
            r3d.view_perspective = 'CAMERA'
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                bpy.ops.screen.screenshot_area(filepath=os.path.join(bot_dir, '%05d.png' % i))
            i += 1
    finally:
        (r3d.view_perspective, _, r3d.view_distance, r3d.view_location, r3d.view_rotation, space.shading.type) = keep
    return i > 0


def _workbench(top_dir, bot_dir, step):
    """No window (or no 3D view): plain gray solid renders from the front and through the camera."""
    sc = bpy.context.scene
    k = Keep(sc)
    eng = sc.render.engine
    lead = core.lead_character(sc)
    front = _bts_cam(sc, lead)
    vl = bpy.context.view_layer
    keep_override = vl.material_override
    try:
        if bpy.app.background:   # no GPU window: render with the scene engine and a plain gray clay
            gray = bpy.data.materials.get('SS BTS gray') or bpy.data.materials.new('SS BTS gray')
            gray.diffuse_color = (0.42, 0.42, 0.42, 1)
            vl.material_override = gray
            if sc.render.engine != 'CYCLES':
                sc.render.engine = 'CYCLES'
        else:
            sc.render.engine = 'BLENDER_WORKBENCH'
            sc.display.shading.light = 'STUDIO'
            sc.display.shading.color_type = 'SINGLE'
        set_png(sc)
        i = 0
        for f in range(sc.frame_start, sc.frame_end + 1, step):
            for cam, d, (w, h) in ((front, top_dir, (1080, 960)), (k.v[4] or sc.camera, bot_dir, (540, 960))):
                sc.render.resolution_x, sc.render.resolution_y = w, h
                sc.camera = cam
                sc.frame_set(f)
                sc.render.filepath = os.path.join(d, '%05d.png' % i)
                bpy.ops.render.render(write_still=True)
            i += 1
    finally:
        vl.material_override = keep_override
        sc.render.engine = eng
        k.restore()
    return True


def _new_effect(st, name, typ, ch, start, length):
    try:
        return st.new_effect(name, typ, ch, start, length=length)
    except TypeError:
        return st.new_effect(name, typ, ch, start, frame_end=start + length)


def make_bts(step=None, card_text=None, card_seconds=2.0):
    sc = bpy.context.scene
    st = core.settings(sc)
    step = step or st.bts_speed
    work = core.work_dir(sc, 'bts')
    top_dir, bot_dir = os.path.join(work, 'top'), os.path.join(work, 'bottom')
    for d in (top_dir, bot_dir):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    ok = False
    if not bpy.app.background and st.bts_use_interface:
        try:
            ok = _screens(top_dir, bot_dir, step)
        except Exception:
            ok = False
    if not ok:
        _workbench(top_dir, bot_dir, step)
    tops = sorted(os.listdir(top_dir))
    bots = sorted(os.listdir(bot_dir))
    n = min(len(tops), len(bots))
    # compose in a throwaway scene with the Video Sequencer
    comp = bpy.data.scenes.new('SS BTS compose')
    try:
        comp.render.resolution_x, comp.render.resolution_y = 1080, 1920
        comp.render.resolution_percentage = 100
        comp.view_settings.view_transform = 'Standard'   # brand colours exactly, no film look
        comp.render.fps, comp.render.fps_base = sc.render.fps, sc.render.fps_base
        card = core.sec(card_seconds, sc)
        comp.frame_start, comp.frame_end = 1, n + card
        se = core.strips(comp)
        bg = _new_effect(se, 'BTS bg', 'COLOR', 1, 1, n)
        bg.color = (0.18, 0.18, 0.18)
        for d, files, ch, off in ((top_dir, tops, 2, 480), (bot_dir, bots, 3, -480)):
            s = se.new_image('BTS ' + str(ch), os.path.join(d, files[0]), ch, 1)
            for fname in files[1:n]:
                s.elements.append(fname)
            try:
                s.fit_method = 'ORIGINAL'
            except Exception:
                pass
            probe = bpy.data.images.load(os.path.join(d, files[0]), check_existing=False)
            img_w, img_h = probe.size[:] if probe.size[0] else (1080, 960)
            bpy.data.images.remove(probe)
            scale = min(1080 / max(1, img_w), 960 / max(1, img_h))
            s.transform.scale_x = s.transform.scale_y = scale
            s.transform.offset_y = off
        cs = _new_effect(se, 'BTS card', 'COLOR', 4, n + 1, card)
        cs.color = tuple(int(core.MUSTARD[i:i + 2], 16) / 255 for i in (1, 3, 5))
        ts = _new_effect(se, 'BTS card text', 'TEXT', 5, n + 1, card)
        ts.text = card_text or st.bts_card
        ts.font = core.font('card')
        ts.font_size = 92
        ts.color = tuple(int(core.INK[i:i + 2], 16) / 255 for i in (1, 3, 5)) + (1.0,)
        ts.location = (0.5, 0.5)
        try:
            ts.alignment_x = 'CENTER'
            ts.anchor_x, ts.anchor_y = 'CENTER', 'CENTER'
        except Exception:
            pass
        try:
            ts.wrap_width = 0.84
        except Exception:
            pass
        snd, at = None, None
        for s in core.all_strips(sc):
            if s.type == 'SOUND' and not s.name.startswith('SFX'):
                snd, at = bpy.path.abspath(s.sound.filepath), s.frame_start - sc.frame_start + 1
                break
        if snd and step == 1:
            se.new_sound('BTS audio', snd, 6, int(at))
        set_mp4(comp)
        out = os.path.join(core.project_dir(sc), core.project_name(sc) + ' BTS.mp4')
        comp.render.filepath = out
        comp.render.use_file_extension = False
        comp.render.use_sequencer = True
        with bpy.context.temp_override(scene=comp):
            bpy.ops.render.render(animation=True, scene=comp.name)
    finally:
        bpy.data.scenes.remove(comp)
    return out


# ================================================================== post package
def caption_text(sc=None):
    sc = sc or bpy.context.scene
    st = core.settings(sc)
    t = bpy.data.texts.get('Post Caption')
    body = t.as_string().strip() if t else ''
    if not body:
        lines = [l.strip() for l in (bpy.data.texts['Reel Script'].as_string().split('\n')
                                     if bpy.data.texts.get('Reel Script') else []) if l.strip()]
        body = lines[0] if lines else core.project_name(sc)
    tags = [w.strip().lstrip('#') for w in st.hashtags.replace(',', ' ').split() if w.strip()]
    tags = ['#' + t for t in dict.fromkeys(tags)][:5]
    return body + ('\n\n' + ' '.join(tags) if tags else '')


def package_post(include=('video', 'cover', 'caption', 'bts', 'carousel', 'sizes')):
    sc = bpy.context.scene
    st = core.settings(sc)
    date = datetime.date.today().isoformat()
    name = core.project_name(sc)
    dest = os.path.join(core.root_dir(), 'Ready to post', '%s %s' % (date, name))
    os.makedirs(dest, exist_ok=True)
    pdir = core.project_dir(sc)
    got, missing = [], []

    def cp(src, dst_name=None):
        if src and os.path.exists(src):
            shutil.copy2(src, os.path.join(dest, dst_name or os.path.basename(src)))
            got.append(dst_name or os.path.basename(src))
            return True
        return False
    if 'video' in include and not cp(final_video(sc), name + '.mp4'):
        missing.append('final video (render it first)')
    if 'cover' in include and not cp(os.path.join(pdir, 'cover.png'), 'cover.png'):
        missing.append('cover (use Cover and grid preview)')
    if 'bts' in include:
        cp(os.path.join(pdir, name + ' BTS.mp4'))
    if 'sizes' in include:
        for k in ('feed', 'square', 'wide'):
            cp(os.path.join(pdir, '%s_%s.mp4' % (name, k)))
    if 'carousel' in include and os.path.isdir(os.path.join(pdir, 'carousel')):
        cd = os.path.join(dest, 'carousel')
        os.makedirs(cd, exist_ok=True)
        for p in sorted(glob.glob(os.path.join(pdir, 'carousel', 'slide_*.png'))):
            shutil.copy2(p, cd)
        got.append('carousel/')
    if 'caption' in include:
        with open(os.path.join(dest, 'caption.txt'), 'w', encoding='utf-8') as fh:
            fh.write(caption_text(sc) + '\n')
        got.append('caption.txt')
    st.last_package = dest
    return dest, got, missing


# ================================================================== Postiz (optional, always confirmed first)
def postiz_schedule(folder, when_iso, integration_id):
    """Upload the video and schedule it. Called only after the user confirms in the dialog."""
    import urllib.request
    import uuid
    p = core.prefs()
    base = p.postiz_url.rstrip('/')
    key = p.postiz_key
    video = next((os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.mp4') and 'BTS' not in f
                  and not any(s in f for s in ('_feed', '_square', '_wide'))), None)
    if not video:
        raise RuntimeError('No video in the package folder.')
    boundary = uuid.uuid4().hex
    with open(video, 'rb') as fh:
        data = fh.read()
    body = (('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\nContent-Type: video/mp4\r\n\r\n'
             % (boundary, os.path.basename(video))).encode() + data + ('\r\n--%s--\r\n' % boundary).encode())
    req = urllib.request.Request(base + '/public/v1/upload', data=body, method='POST',
                                 headers={'Authorization': key, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
    with urllib.request.urlopen(req, timeout=300) as r:
        up = json.loads(r.read().decode())
    with open(os.path.join(folder, 'caption.txt'), encoding='utf-8') as fh:
        caption = fh.read().strip()
    post = {'type': 'schedule', 'date': when_iso, 'shortLink': False, 'tags': [],
            'posts': [{'integration': {'id': integration_id},
                       'value': [{'content': caption, 'image': [{'id': up.get('id'), 'path': up.get('path')}]}],
                       'settings': {}}]}
    req = urllib.request.Request(base + '/public/v1/posts', data=json.dumps(post).encode(), method='POST',
                                 headers={'Authorization': key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode()[:300]
