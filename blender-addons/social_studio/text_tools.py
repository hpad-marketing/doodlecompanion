"""Captions, doodle stickers, comment bubbles, end cards and title cards."""
import math
import os
import re

import bpy
from mathutils import Vector

from . import core

STOP = set('a an and are as at be but by for from had has have he her his i if in into is it its just me my of on or '
           'our so than that the their them then there they this to too up us was we were what when which who will '
           'with you your yeah okay like really very'.split())


# ================================================================== captions
def parse_srt(src):
    cues = []
    blocks = re.split(r'\n\s*\n', src.replace('\r', '').strip())
    t = re.compile(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)')
    for b in blocks:
        lines = [l for l in b.split('\n') if l.strip()]
        for i, l in enumerate(lines):
            m = t.search(l)
            if m:
                g = [int(x) for x in m.groups()]
                a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 10 ** len(m.group(4))
                e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 10 ** len(m.group(8))
                body = ' '.join(lines[i + 1:]).strip()
                body = re.sub(r'<[^>]+>', '', body)
                if body:
                    cues.append((a, e, body))
                break
    return cues


def plain_to_cues(src, start_s, end_s):
    """A transcript without timings: spread its sentences over the voice, by word count."""
    parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+|\n+', src) if p.strip()]
    total = sum(len(p.split()) for p in parts) or 1
    t, cues = start_s, []
    for p in parts:
        d = (end_s - start_s) * len(p.split()) / total
        cues.append((t, t + d, p))
        t += d
    return cues


def condense(cues, max_words=6):
    """Split long cues into short chunks, timed by word count."""
    out = []
    for a, e, body in cues:
        words = body.split()
        if len(words) <= max_words:
            out.append((a, e, words))
            continue
        n = math.ceil(len(words) / max_words)
        per = math.ceil(len(words) / n)
        chunks, i = [], 0
        while i < len(words):
            j = min(len(words), i + per)
            # don't end a chunk on a little word ("the", "that"): move it to the next chunk
            while j < len(words) and j - i > 2 and _clean(words[j - 1]).lower() in STOP:
                j -= 1
            chunks.append(words[i:j])
            i = j
        t = a
        for c in chunks:
            d = (e - a) * len(c) / len(words)
            out.append((t, t + d, c))
            t += d
    return out


def _clean(w):
    return re.sub(r'[^\w\'’-]', '', w)


def key_flags(words, always=(), auto=True):
    """Which words get the headline treatment: *starred*, ALL CAPS, your list, else the strongest word."""
    flags, out = [], []
    for w in words:
        star = w.startswith('*') and w.rstrip('.,!?;:').endswith('*') and len(w) > 2
        bare = w.replace('*', '')
        c = _clean(bare)
        caps = len(c) > 1 and c.isupper()
        flags.append(star or caps or c.lower() in always)
        out.append(bare)
    if auto and not any(flags):
        cand = [(len(_clean(w)), i) for i, w in enumerate(out) if _clean(w).lower() not in STOP and len(_clean(w)) >= 5]
        if cand:
            flags[max(cand)[1]] = True
    return out, flags


def lines_for(words):
    """1-3 words stay on one line; longer captions go to two balanced lines."""
    if len(words) <= 3:
        return [words]
    best, cut = 1e9, 1
    txt = [w[0] if isinstance(w, tuple) else w for w in words]
    for i in range(1, len(words)):
        d = abs(len(' '.join(txt[:i])) - len(' '.join(txt[i:])))
        if d < best:
            best, cut = d, i
    return [words[:cut], words[cut:]]


def clear_captions():
    for r in core.items('caption'):
        _delete_tree(r)


def _delete_tree(root):
    obs = [root] + list(root.children_recursive if hasattr(root, 'children_recursive') else root.children)
    for o in obs:
        data = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)
            elif isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)


def build_caption(words, flags, start, end, idx=0):
    """One caption: each word is its own text object, so headline key words never overlap their neighbours."""
    sc = bpy.context.scene
    st = core.settings(sc)
    lines = lines_for(list(zip(words, flags)))
    body = '\n'.join(' '.join(w for w, _ in ln) for ln in lines)
    root, pop = core.item('Caption %03d' % idx, 0.5, 0.7, kind='caption', anchor='caption', start=start, end=end)
    size = st.caption_size
    line_h = size * 1.12
    gap = size * 0.3
    rows = []
    for ln in lines:
        objs = []
        for w, key in ln:
            ob = core.text(w.upper() if key else w, pop, size=size * (1.12 if key else 1.0),
                           kind='headline' if key else 'hand', fill='mustard' if key else 'ink',
                           outline='ink' if key else 'mustard', align='LEFT', name='Caption %03d %s' % (idx, w[:10]))
            objs.append((ob, core.text_dims(ob)[0]))
        rows.append(objs)
    widths = [sum(w for _, w in r) + gap * (len(r) - 1) for r in rows]
    aspect = sc.render.resolution_x / sc.render.resolution_y
    s = min(1.0, aspect * 0.82 / max(widths + [1e-6]))
    for i, (r, tw) in enumerate(zip(rows, widths)):
        x = -tw / 2
        y = ((len(rows) - 1) / 2 - i) * line_h
        for ob, w in r:
            for o in (ob, bpy.data.objects.get(ob.get('ss_outline', ''))):
                if o:
                    o.location.x, o.location.y = x * s, y * s
                    o.scale = (s, s, 1)
            x += w + gap
    h = len(rows) * line_h * s
    root['ss_half'] = h / 2 + size * 0.15
    root['ss_text'] = body
    core.key_pop(root, start, end, length=4)
    anchor_caption(root)
    core.place(root)
    return root


def anchor_caption(root, cam=None, sc=None):
    """Below the face, inside the safe zone, never over the eyes or mouth, never at the very bottom."""
    sc = sc or bpy.context.scene
    st = core.settings(sc)
    top, bottom, _, _ = core.safe(sc)
    half = root.get('ss_half', 0.04)
    lo = max(top + half, 0.0)
    hi = min(core.CAPTION_MAX_V, 1 - bottom) - half
    lead = core.lead_character(sc)
    v = 0.7 + st.caption_nudge
    root['ss_warn'] = 0
    if lead:
        f = root.get('ss_start', sc.frame_current)
        u0, v0, u1, v1 = core.head_rect(lead, cam, sc, frame=f)
        gap = 0.025
        want = v1 + gap + half + st.caption_nudge
        mouth = v0 + (v1 - v0) * 0.66      # the mouth sits about two thirds down the head
        if want <= hi:
            v = max(want, lo)
        elif hi - half >= mouth + 0.01:
            v = hi                    # tucked as low as allowed: over the chin at most, never the mouth
        elif v0 - gap - half >= lo and not _top_busy(root, sc, v0 - gap - 2 * half):
            v = v0 - gap - half       # no room under the face: go above it, if nothing else is up there
        else:
            v = hi
            root['ss_warn'] = 1
    root['ss_v'] = min(max(v, lo), hi)
    root['ss_u'] = 0.5


def _top_busy(root, sc, below):
    """Is a clip, comment or headline already showing in the top band while this caption is up?"""
    a, b = root.get('ss_start', 0), root.get('ss_end', 10 ** 9)
    for r in core.items(sc=sc):
        if r['ss_kind'] in ('react', 'comment', 'slot_text') and r.get('ss_v', 1) < below + 0.15:
            if r['ss_kind'] == 'react' or not (r.get('ss_end', 10 ** 9) <= a or r.get('ss_start', 0) >= b):
                return True
    return False


def place_captions(src, is_srt=True):
    sc = bpy.context.scene
    st = core.settings(sc)
    clear_captions()
    f0 = sc.frame_start
    if is_srt:
        cues = parse_srt(src)
    else:
        cues = plain_to_cues(src, 0.0, (sc.frame_end - f0) / core.fps(sc))
    cues = condense(cues, st.caption_max_words)
    always = set(w.strip().lower() for w in st.key_words.split(',') if w.strip())
    made = []
    for i, (a, e, words) in enumerate(cues):
        ws, fl = key_flags(words, always, st.auto_key_words)
        s, en = f0 + core.sec(a), f0 + max(core.sec(e), core.sec(a) + 3)
        made.append(build_caption(ws, fl, s, en, i))
    return made


# ================================================================== stickers
def _arrow():
    return [[(-0.5, -0.15), (-0.15, 0.02), (0.2, 0.1), (0.45, 0.12)], [(0.25, 0.3), (0.47, 0.12), (0.28, -0.08)]]


def _circle():
    pts = []
    for i in range(38):
        a = math.radians(100 + i * 10.4)
        r = 1 + 0.04 * math.sin(i * 1.3)
        pts.append((0.5 * r * math.cos(a), 0.32 * r * math.sin(a)))
    return [pts]


def _underline():
    return [[(-0.5 + i / 12, 0.03 * math.sin(i * 1.1) - 0.01 * i / 12) for i in range(13)]]


def _sparkle():
    s = []
    for a in (0, 90, 45, 135):
        r = 0.5 if a % 90 == 0 else 0.28
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        s.append([(-r * ca, -r * sa), (r * ca, r * sa)])
    return s


def _lines3():  # three "surprise" dashes
    return [[(0.12 * math.cos(math.radians(a)), 0.12 * math.sin(math.radians(a))),
             (0.45 * math.cos(math.radians(a)), 0.45 * math.sin(math.radians(a)))] for a in (60, 90, 120)]


SHAPES = {'ARROW': _arrow, 'CIRCLE': _circle, 'UNDERLINE': _underline, 'SPARKLE': _sparkle, 'BURST': _lines3}
GLYPHS = {'QUESTION': '?', 'EXCLAIM': '!'}
WORDS = {'BONK': 'BONK!', 'WHOOSH': 'WHOOSH', 'POP': 'POP!', 'BOING': 'BOING', 'WOW': 'WOW'}

STICKER_ITEMS = [
    ('ARROW', 'Arrow', ''), ('CIRCLE', 'Circle', ''), ('UNDERLINE', 'Underline', ''), ('SPARKLE', 'Sparkle', ''),
    ('BURST', 'Surprise lines', ''), ('QUESTION', 'Question mark', ''), ('EXCLAIM', 'Exclamation', ''),
    ('BONK', 'BONK!', ''), ('WHOOSH', 'WHOOSH', ''), ('POP', 'POP!', ''), ('BOING', 'BOING', ''), ('WOW', 'WOW', ''),
]


def add_sticker(kind, frame=None, u=None, v=None):
    sc = bpy.context.scene
    st = core.settings(sc)
    f = sc.frame_current if frame is None else frame
    length = core.sec(st.sticker_seconds)
    size = st.sticker_size
    if u is None or v is None:
        u, v = 0.72, 0.32
        lead = core.lead_character(sc)
        if lead:
            u0, v0, u1, v1 = core.head_rect(lead)
            u = min(0.86, u1 + 0.1) if u1 < 0.78 else max(0.14, u0 - 0.1)
            v = max(0.16, min(0.55, v0 + 0.05))
    root, pop = core.item('Sticker ' + kind.title(), u, v, kind='sticker', start=f, end=f + length)
    root['ss_sticker'] = kind
    parts = []
    if kind in SHAPES:
        ob = core.poly(None, pop, splines=[[(x * size, y * size) for x, y in s] for s in SHAPES[kind]()],
                       cyclic=False, name='Sticker ' + kind.title())
        ob.data.bevel_factor_mapping_end = 'SPLINE'
        draw = core.sec(st.draw_seconds)
        ob.data.bevel_factor_end = 0.0
        ob.data.keyframe_insert('bevel_factor_end', frame=f)
        ob.data.bevel_factor_end = 1.0
        ob.data.keyframe_insert('bevel_factor_end', frame=f + max(1, draw))
        parts.append(ob)
        core.key_pop(root, f, f + length, style='cut')
    else:
        body = GLYPHS.get(kind) or WORDS.get(kind, kind)
        fill = 'ink' if kind in GLYPHS else 'mustard'
        t = core.text(body, pop, size=size * (0.9 if kind in GLYPHS else 0.45), kind='headline', fill=fill,
                      outline='ink' if fill == 'mustard' else 'mustard', name='Sticker ' + kind.title())
        parts.append(t)
        core.key_pop(root, f, f + length, length=6)
    if st.line_boil > 0:
        for p in parts:
            core.boil(p, f, f + length, amount=st.line_boil)
    return root


# ================================================================== comment bubbles
def _wrap(text, n):
    if '\n' in text:
        return [l for para in text.split('\n') for l in _wrap(para, n)]
    out, line = [], ''
    for w in text.split():
        if len(line) + len(w) + 1 > n and line:
            out.append(line)
            line = w
        else:
            line = (line + ' ' + w).strip()
    if line:
        out.append(line)
    return out


def add_comment(username, comment, frame=None, where='TOP', seconds=None, show_user=True, style='MUSTARD'):
    sc = bpy.context.scene
    st = core.settings(sc)
    f = sc.frame_current if frame is None else frame
    length = core.sec(seconds or st.comment_seconds)
    small = where == 'BESIDE'
    u, v = (0.5, 0.24) if not small else (0.7, 0.3)
    if small:
        lead = core.lead_character(sc)
        if lead:
            u0, v0, u1, v1 = core.head_rect(lead)
            u = 0.73 if (u0 + u1) / 2 < 0.5 else 0.27
            v = max(0.2, v0 + 0.06)
    root, pop = core.item('Comment bubble', u, v, kind='comment', start=f, end=f + length)
    lead_rig = core.lead_character(sc)
    aspect = sc.render.resolution_x / sc.render.resolution_y
    w = aspect * (0.84 if not small else 0.44)
    size = 0.04 if not small else 0.03
    lines = _wrap(comment.strip() or '...', int(w / (size * 0.5)))
    head = 0.0
    hlines = []
    if show_user and username:
        name = username if username.startswith('@') else '@' + username
        hlines = ['Replying to ' + name]
        head = size * 1.15
    h = head + len(lines) * size * 1.2 + size * 1.2
    fill = 'mustard' if style == 'MUSTARD' else 'ink'
    tail_x = -w * 0.25 if u > 0.5 else w * 0.25
    core.panel(w, h, pop, fill=fill, tail=(tail_x, 1 if u <= 0.5 else -1) if small else None, name='Comment panel')
    ink = 'ink' if fill == 'mustard' else 'mustard'
    y = h / 2 - size * 0.9
    if hlines:
        core.text(hlines[0], pop, size=size * 0.75, kind='hand', fill=ink, align='LEFT', loc=(-w / 2 + size * 0.7, y, 0.001))
        y -= head
    core.text('\n'.join(lines), pop, size=size, kind='hand', fill=ink, align='LEFT',
              loc=(-w / 2 + size * 0.7, y - (len(lines) - 1) * size * 0.6, 0.001))
    if lead_rig and not small:
        # sit at the top of the safe zone, and shrink rather than cover the eyes
        top = core.safe(sc)[0]
        u0, v0, u1, v1 = core.head_rect(lead_rig, frame=f)
        eye_top = v0 + (v1 - v0) * 0.42
        room = eye_top - 0.02 - top
        s = min(1.0, max(0.45, room / h)) if room > 0 else 0.45
        if s < 1.0:
            for c in pop.children:
                c.scale = (s, s, 1)
                c.location = (c.location.x * s, c.location.y * s, c.location.z)
        root['ss_v'] = top + h * s / 2
        core.place(root)
    core.key_pop(root, f, f + length, length=6)
    return root


# ================================================================== cards
CARDS = {
    'FOLLOW': 'Follow for part 2',
    'COMMENT': 'Comment "{word}" and I\'ll send it',
    'PROFILE': 'Full video on my profile',
    'SAVE': 'Save this for later',
}


def _sentence(s):
    s = s.strip()
    return s[:1].upper() + s[1:] if s else s


def add_card(text, start, length, kind='endcard', behind_character=False, v_text=None):
    """A brand mustard card with black sentence-case headline text."""
    sc = bpy.context.scene
    st = core.settings(sc)
    depth = st.overlay_depth * 0.6
    lead = core.lead_character(sc)
    if behind_character and lead:
        _, _, z = core.to_frame(core.head_center(lead))
        depth = max(z * 1.6, depth)
    root, pop = core.item(kind.title() + ' card', 0.5, 0.5, kind=kind, depth=depth, start=start, end=start + length)
    aspect = sc.render.resolution_x / sc.render.resolution_y
    # wide enough to cover any frame size (Reels, feed, square or 16:9)
    core.fill_shape(core.rounded_rect(4.0, 1.1, 0.001, 1), pop, 'mustard', z=-0.03, name='Card fill')
    lines = _wrap(_sentence(text), 16 if aspect < 1 else 26)
    size = 0.095 if aspect < 1 else 0.13
    yoff = 0.0 if v_text is None else (0.5 - v_text)
    if behind_character and v_text is None:
        yoff = 0.25
    core.text('\n'.join(lines), pop, size=size, kind='card', fill='ink', loc=(0, yoff, 0.0))
    core.key_pop(root, start, start + length, style='cut')
    return root


def add_end_card(kind='FOLLOW', word='LINK', seconds=None, behind_character=False, custom=''):
    sc = bpy.context.scene
    st = core.settings(sc)
    length = core.sec(seconds or st.card_seconds)
    text = custom.strip() or CARDS[kind].format(word=word.strip() or 'LINK')
    old = core.items('endcard')
    start = int(old[0].get('ss_start', sc.frame_end + 1)) if old else sc.frame_end + 1
    for r in old:
        _delete_tree(r)
    sc.frame_end = start + length - 1
    r = add_card(text, start, length, 'endcard', behind_character)
    r['ss_card'] = kind
    return r
