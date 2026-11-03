"""Shared pieces: brand colours, fonts, the on-screen overlay layer, safe zones, characters.

Everything on screen (captions, stickers, cards, bubbles, clips) is an *overlay item*: an empty
pinned in front of the active camera at a normalised frame position (u from the left, v from the
top, 0..1). Its content is built in frame units (1.0 = frame height), so the same item lays out
again for any camera or frame size. layout() re-pins every item; Smart reframe calls it per size.
"""
import math
import os
import random

import bpy
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

ADDON = __package__
HERE = os.path.dirname(__file__)

INK = '#1F1F1D'
MUSTARD = '#E0A64B'

FONTS = {'hand': 'PatrickHand-Regular.ttf', 'headline': 'Bangers-Regular.ttf', 'card': 'Anton-Regular.ttf'}

# fractions of the frame kept clear of platform buttons (top, bottom, left, right)
SAFE = {
    'reel': (0.12, 0.20, 0.06, 0.14),   # 9:16 Reels / Shorts / TikTok
    'feed': (0.06, 0.08, 0.06, 0.06),   # 4:5
    'square': (0.06, 0.06, 0.06, 0.06),
    'wide': (0.08, 0.10, 0.06, 0.06),   # 16:9 YouTube
}
CAPTION_MAX_V = 0.79   # never lower than this: the very bottom is off limits

OVERLAY = 'Social Overlay'


# ------------------------------------------------------------------ small utils
def hex_lin(h, a=1.0):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, a)


def settings(sc=None):
    return (sc or bpy.context.scene).social_studio


def prefs():
    a = bpy.context.preferences.addons.get(ADDON)
    return a.preferences if a else None


def font(kind='hand'):
    name = FONTS.get(kind, kind)
    for f in bpy.data.fonts:
        if f.get('ss_font') == kind:
            return f
    path = os.path.join(HERE, 'fonts', name)
    f = bpy.data.fonts.load(path, check_existing=True)
    f['ss_font'] = kind
    return f


def font_path(kind='hand'):
    return os.path.join(HERE, 'fonts', FONTS.get(kind, kind))


def root_dir():
    p = prefs()
    d = p.renders_dir if p and p.renders_dir else os.path.join(os.path.expanduser('~'), 'Documents', 'DeepInDoodles')
    return bpy.path.abspath(d)


def safe_name(s):
    keep = ''.join(c if c.isalnum() or c in ' -_' else ' ' for c in s).strip()
    return ' '.join(keep.split()) or 'Reel'


def project_name(sc=None):
    sc = sc or bpy.context.scene
    st = settings(sc)
    if st.series_name and st.episode > 0:
        return safe_name('%s %s' % (st.series_name, episode_label(st, st.episode)))
    if bpy.data.filepath:
        return safe_name(os.path.splitext(os.path.basename(bpy.data.filepath))[0])
    return safe_name(sc.name)


def episode_label(st, n):
    return {'EP': 'Ep %d', 'PART': 'Part %d', 'HASH': '#%d'}.get(st.numbering, 'Ep %d') % n


def project_dir(sc=None):
    d = os.path.join(root_dir(), project_name(sc))
    os.makedirs(os.path.join(d, 'work'), exist_ok=True)
    return d


def work_dir(sc=None, *sub):
    d = os.path.join(project_dir(sc), 'work', *sub)
    os.makedirs(d, exist_ok=True)
    return d


def fps(sc=None):
    sc = sc or bpy.context.scene
    return sc.render.fps / sc.render.fps_base


def sec(s, sc=None):
    return int(round(s * fps(sc)))


def coll(name='Social Studio', parent=None):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    elif parent is None and c.name not in bpy.context.scene.collection.children and \
            not any(c.name in p.children for p in bpy.data.collections):
        bpy.context.scene.collection.children.link(c)
    return c


def mat(kind):
    """Flat brand colours (no shading, no shadows)."""
    name = 'SS ' + kind.title()
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    col = {'ink': INK, 'mustard': MUSTARD}.get(kind, kind)
    m.diffuse_color = hex_lin(col)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = hex_lin(col)
    nt.links.new(em.outputs[0], out.inputs[0])
    try:
        m.shadow_method = 'NONE'
    except Exception:
        pass
    return m


# ------------------------------------------------------------------ camera + frame
def ensure_camera(sc=None):
    sc = sc or bpy.context.scene
    if sc.camera:
        return sc.camera
    cd = bpy.data.cameras.new('Reel Camera')
    cam = bpy.data.objects.new('Reel Camera', cd)
    sc.collection.objects.link(cam)
    lead = lead_character(sc)
    tgt = head_center(lead) if lead else Vector((0, 0, 1))
    cam.location = tgt + Vector((0, -4.0, 0))
    cam.rotation_euler = (math.radians(90), 0, 0)
    cd.lens = 50
    sc.camera = cam
    return cam


def set_vertical(sc=None, w=1080, h=1920):
    sc = sc or bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1


def frame_kind(sc=None):
    sc = sc or bpy.context.scene
    a = sc.render.resolution_x / max(1, sc.render.resolution_y)
    if a < 0.7:
        return 'reel'
    if a < 0.95:
        return 'feed'
    if a < 1.2:
        return 'square'
    return 'wide'


def safe(sc=None):
    return SAFE[frame_kind(sc)]


def frame_half(depth, cam=None, sc=None):
    """Half width and half height of the frame at `depth` metres in front of the lens."""
    sc = sc or bpy.context.scene
    cam = cam or sc.camera
    cd = cam.data
    a = sc.render.resolution_x / max(1, sc.render.resolution_y)
    if cd.type == 'ORTHO':
        long_half = cd.ortho_scale / 2
    else:
        sensor = cd.sensor_width if cd.sensor_fit in ('AUTO', 'HORIZONTAL') else cd.sensor_height
        long_half = sensor / 2 / cd.lens * depth
        if cd.sensor_fit == 'VERTICAL':
            return long_half * a, long_half
        if cd.sensor_fit == 'HORIZONTAL':
            return long_half, long_half / a
    return (long_half * a, long_half) if a < 1 else (long_half, long_half / a)


def to_frame(co, cam=None, sc=None):
    """World point -> (u from left, v from top, depth)."""
    sc = sc or bpy.context.scene
    cam = cam or sc.camera
    p = world_to_camera_view(sc, cam, co)
    return p.x, 1.0 - p.y, p.z


def move_camera(cam, delta):
    """Move a camera everywhere in the shot: shifts its location keys when it's animated."""
    fcs = [fc for fc in fcurves(cam) if fc.data_path == 'location']
    if not fcs:
        cam.location += delta
        return
    for fc in fcs:
        d = delta[fc.array_index]
        for k in fc.keyframe_points:
            k.co.y += d
            k.handle_left.y += d
            k.handle_right.y += d
        fc.update()
    cam.location += delta


# ------------------------------------------------------------------ characters
CAST_WORDS = ('bunny', 'frog', 'koala')


def characters(sc=None):
    sc = sc or bpy.context.scene
    return [o for o in sc.objects if o.type == 'ARMATURE' and o.visible_get()]


def lead_character(sc=None):
    sc = sc or bpy.context.scene
    rigs = characters(sc)
    if not rigs:
        return None
    named = [r for r in rigs if any(w in r.name.lower() for w in CAST_WORDS)]
    pool = [r for r in (named or rigs) if not r.get('ss_cameo')] or (named or rigs)
    cam = sc.camera
    if not cam:
        return pool[0]

    def score(r):
        u, v, z = to_frame(head_center(r), cam, sc)
        return abs(u - 0.5) + (0 if z > 0 else 10)
    return min(pool, key=score)


def _head_bone(rig):
    for n in ('head', 'Head', 'HEAD', 'DEF-head', 'head.x', 'mixamorig:Head'):
        if n in rig.pose.bones:
            return rig.pose.bones[n]
    for pb in rig.pose.bones:
        if 'head' in pb.name.lower():
            return pb
    return None


def _head_meshes(rig):
    out = []
    for o in rig.children_recursive if hasattr(rig, 'children_recursive') else rig.children:
        if o.type == 'MESH' and 'head' in o.name.lower() and o.visible_get():
            out.append(o)
    return out


def head_points(rig):
    """World points around the head: mesh corners when there's a head mesh, else the bone."""
    if rig is None:
        return [Vector((0, 0, 1))]
    meshes = _head_meshes(rig)
    if meshes:
        pts = []
        dg = bpy.context.evaluated_depsgraph_get()
        for m in meshes:
            me = m.evaluated_get(dg)
            pts += [me.matrix_world @ Vector(c) for c in me.bound_box]
        return pts
    pb = _head_bone(rig)
    if pb is None:
        c = rig.matrix_world.translation
        return [c + Vector((0, 0, 1.2)), c + Vector((0, 0, 0.6))]
    h = rig.matrix_world @ pb.head
    t = rig.matrix_world @ pb.tail
    r = max((t - h).length * 0.9, 0.05)
    mid = (h + t) / 2
    pts = []
    for dx in (-r, r):
        for dy in (-r, r):
            for dz in (-r, r):
                pts.append(mid + Vector((dx, dy, dz)))
    return pts


def head_center(rig):
    pts = head_points(rig)
    return sum(pts, Vector()) / len(pts)


def head_rect(rig, cam=None, sc=None, frame=None):
    """Screen rectangle of the face (u0, v0, u1, v1) at `frame`."""
    sc = sc or bpy.context.scene
    keep = sc.frame_current
    if frame is not None and frame != keep:
        sc.frame_set(frame)
    uv = [to_frame(p, cam, sc) for p in head_points(rig)]
    if frame is not None and frame != keep:
        sc.frame_set(keep)
    us, vs = [p[0] for p in uv], [p[1] for p in uv]
    return min(us), min(vs), max(us), max(vs)


def body_rect(rig, cam=None, sc=None):
    sc = sc or bpy.context.scene
    pts = []
    dg = bpy.context.evaluated_depsgraph_get()
    kids = rig.children_recursive if hasattr(rig, 'children_recursive') else rig.children
    for o in kids:
        if o.type == 'MESH' and o.visible_get():
            e = o.evaluated_get(dg)
            pts += [e.matrix_world @ Vector(c) for c in e.bound_box]
    if not pts:
        return head_rect(rig, cam, sc)
    uv = [to_frame(p, cam, sc) for p in pts]
    return min(p[0] for p in uv), min(p[1] for p in uv), max(p[0] for p in uv), max(p[1] for p in uv)


# ------------------------------------------------------------------ overlay items
def overlay_root(sc=None):
    sc = sc or bpy.context.scene
    return coll(OVERLAY)


def stroke(sc=None):
    """Line width in frame units (frame height = 1), from the px setting at 1920 tall."""
    return settings(sc).stroke_px / 1920.0


def item(name, u=0.5, v=0.5, kind='item', depth=None, start=None, end=None, anchor=''):
    """Create an overlay item. Returns (root, pop). Build content under `pop` in frame units."""
    sc = bpy.context.scene
    c = overlay_root(sc)
    root = bpy.data.objects.new(name, None)
    root.empty_display_size = 0.02
    root['ss_kind'] = kind
    root['ss_u'], root['ss_v'] = float(u), float(v)
    root['ss_depth'] = float(depth or settings(sc).overlay_depth)
    root['ss_anchor'] = anchor
    if start is not None:
        root['ss_start'] = int(start)
    if end is not None:
        root['ss_end'] = int(end)
    c.objects.link(root)
    pop = bpy.data.objects.new(name + ' ·pop', None)
    pop.empty_display_size = 0.01
    pop.parent = root
    c.objects.link(pop)
    root['ss_pop'] = pop.name
    place(root)
    return root, pop


def pop_of(root):
    return bpy.data.objects.get(root.get('ss_pop', '')) or root


def items(kind=None, sc=None):
    c = bpy.data.collections.get(OVERLAY)
    if not c:
        return []
    return [o for o in c.objects if 'ss_kind' in o and (kind is None or o['ss_kind'] == kind)]


def place(root, cam=None, sc=None):
    sc = sc or bpy.context.scene
    cam = cam or sc.camera or ensure_camera(sc)
    d = root.get('ss_depth', 1.0)
    last = root.get('ss_last')
    if last is not None and root.parent and root.parent == cam and cam.data.type != 'ORTHO':
        # the item was moved by hand since the last layout: keep where the user put it
        hw0, hh0 = frame_half(d, cam, sc)
        if (Vector(root.location) - Vector(last)).length > 1e-5:
            root['ss_u'] = root.location.x / (2 * hw0) + 0.5
            root['ss_v'] = 0.5 - root.location.y / (2 * hh0)
    hw, hh = frame_half(d, cam, sc)
    for path in ('location', 'scale'):
        root.driver_remove(path)
    root.parent = cam
    root.matrix_parent_inverse = Matrix.Identity(4)
    root.rotation_euler = (0, 0, 0)
    root.location = ((root['ss_u'] - 0.5) * 2 * hw, (0.5 - root['ss_v']) * 2 * hh, -d)
    s = 2 * hh
    root.scale = (s, s, s)
    if cam.data.type == 'ORTHO':
        _ortho_drivers(root, cam, sc)
        root['ss_last'] = None
        return
    root['ss_last'] = list(root.location)


def _ortho_drivers(root, cam, sc):
    """A flat camera that zooms (keyed ortho scale) carries its overlays along: drive them from it.
    Move an item by editing its ss_u / ss_v custom properties."""
    a = sc.render.resolution_x / max(1, sc.render.resolution_y)
    h = 'os' if a < 1 else 'os/%.6f' % a          # frame height
    exprs = {('location', 0): '(u-0.5)*%s*%.6f' % (h, a), ('location', 1): '(0.5-v)*%s' % h,
             ('scale', 0): h, ('scale', 1): h, ('scale', 2): h}
    for (path, i), e in exprs.items():
        fc = root.driver_add(path, i)
        dr = fc.driver
        dr.type = 'SCRIPTED'
        for v in list(dr.variables):
            dr.variables.remove(v)
        var = dr.variables.new()
        var.name = 'os'
        var.targets[0].id_type = 'CAMERA'
        var.targets[0].id = cam.data
        var.targets[0].data_path = 'ortho_scale'
        if path == 'location':
            for nm in ('u', 'v'):
                vv = dr.variables.new()
                vv.name = nm
                vv.targets[0].id = root
                vv.targets[0].data_path = '["ss_%s"]' % nm
        dr.expression = e


def layout(cam=None, sc=None):
    sc = sc or bpy.context.scene
    from . import text_tools
    for r in items(sc=sc):
        if r.get('ss_anchor') == 'caption':
            text_tools.anchor_caption(r, cam, sc)
        place(r, cam, sc)


def key_pop(root, start, end=None, length=6, style='pop'):
    """Show `root` from start to end (frames) with a little pop. Scale 0 = hidden."""
    p = pop_of(root)
    tiny = 0.0001
    p.animation_data_clear()
    pts = [(start - 1, tiny)]
    if style == 'pop':  # visible from its first frame, overshoot, settle
        pts += [(start, 0.7), (start + max(1, length // 2), 1.12), (start + length, 1.0)]
    else:
        pts += [(start, 1.0)]
    if end is not None:
        pts += [(end - 1, 1.0), (end, tiny)]
    for f, s in pts:
        p.scale = (s, s, s)
        p.keyframe_insert('scale', frame=f)
    for fc in fcurves(p):
        for k in fc.keyframe_points:
            k.interpolation = 'CONSTANT' if style != 'pop' or k.co[1] <= tiny * 2 or k.co[0] >= (end or 10 ** 9) - 1 \
                else 'BEZIER'
    root['ss_start'] = int(start)
    if end is not None:
        root['ss_end'] = int(end)
    p.scale = (1, 1, 1) if start <= bpy.context.scene.frame_current < (end or 10 ** 9) else (tiny,) * 3
    return p


def boil(ob, start, end, amount=1.0, every=3, seed=0):
    """Hand-drawn line boil: tiny stepped wobble, never a distortion."""
    rnd = random.Random(seed or hash(ob.name) & 0xffff)
    base = ob.rotation_euler.z
    loc = ob.location.copy()
    f = start
    while f <= end:
        ob.rotation_euler.z = base + math.radians(rnd.uniform(-1.2, 1.2) * amount)
        ob.location = loc + Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)) * 0.0012 * amount
        ob.keyframe_insert('rotation_euler', index=2, frame=f)
        ob.keyframe_insert('location', frame=f)
        f += every
    for fc in fcurves(ob):
        for k in fc.keyframe_points:
            k.interpolation = 'CONSTANT'
    ob.rotation_euler.z = base
    ob.location = loc


# ------------------------------------------------------------------ geometry helpers (frame units)
def link(ob, parent):
    overlay_root().objects.link(ob)
    ob.parent = parent
    return ob


def text(body, parent, size=0.05, kind='hand', fill='ink', outline=None, align='CENTER', loc=(0, 0, 0),
         bold_kind=None, width=None, name=None):
    """Flat text in frame units. outline='mustard'/'ink' adds a thick outline copy behind it."""
    cu = bpy.data.curves.new(name or 'SS Text', 'FONT')
    cu.body = body
    cu.font = font(kind)
    if bold_kind:
        cu.font_bold = font(bold_kind)
    cu.size = size
    cu.align_x = align
    cu.align_y = 'CENTER'
    cu.space_line = 0.95
    if width:
        cu.text_boxes[0].width = width
        cu.text_boxes[0].x = -width / 2 if align == 'CENTER' else 0
    cu.materials.append(mat(fill))
    cu.materials.append(mat('mustard' if fill == 'ink' else 'ink'))
    ob = link(bpy.data.objects.new(name or 'SS Text', cu), parent)
    ob.location = loc
    if outline:
        cu2 = cu.copy()
        cu2.materials.clear()
        cu2.materials.append(mat(outline))
        cu2.materials.append(mat('ink' if outline == 'mustard' else 'mustard'))
        cu2.bevel_depth = size * 0.07   # a clean, even outline (offset makes blotches)
        cu2.bevel_resolution = 3
        o2 = link(bpy.data.objects.new((name or 'SS Text') + ' outline', cu2), parent)
        o2.location = (loc[0], loc[1], loc[2] - size * 0.2)   # fully behind the fill, bevel included
        ob['ss_outline'] = o2.name
    return ob


def text_dims(ob):
    """Width and height of an object in its own (frame) units, ignoring parent scale."""
    bpy.context.view_layer.update()
    bb = [Vector(c) for c in ob.bound_box]
    return (max(c.x for c in bb) - min(c.x for c in bb)) * ob.scale.x, (max(c.y for c in bb) - min(c.y for c in bb)) * ob.scale.y


def poly(points, parent, width=None, cyclic=False, fill='ink', name='SS Line', splines=None):
    """Ink stroke(s) in frame units. points: [(x, y)], or splines=[[(x, y)...], ...]."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'   # a 2D curve fills closed shapes; we only want the ink line
    cu.fill_mode = 'FULL'
    cu.bevel_depth = (width or stroke()) / 2
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    for pts in (splines or [points]):
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for p, (x, y) in zip(sp.points, pts):
            p.co = (x, y, 0, 1)
        sp.use_cyclic_u = cyclic
    cu.materials.append(mat(fill))
    return link(bpy.data.objects.new(name, cu), parent)


def rounded_rect(w, h, r, seg=6):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def fill_shape(points, parent, fill='mustard', z=-0.001, name='SS Fill'):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x, y, 0) for x, y in points], [], [list(range(len(points)))])
    me.materials.append(mat(fill))
    ob = link(bpy.data.objects.new(name, me), parent)
    ob.location.z = z
    return ob


def panel(w, h, parent, fill='mustard', outline=True, r=None, tail=None, name='SS Panel'):
    r = min(w, h) * 0.18 if r is None else r
    pts = rounded_rect(w, h, r)
    if tail:  # (x, direction) speech tail on the bottom edge
        tx, sgn = tail
        i = min(range(len(pts)), key=lambda k: (pts[k][0] - tx) ** 2 + (pts[k][1] + h / 2) ** 2)
        tip = (tx + sgn * h * 0.25, -h / 2 - h * 0.35)
        pts = pts[:i] + [(tx + h * 0.12, -h / 2), tip, (tx - h * 0.12, -h / 2)] + pts[i + 1:]
    f = fill_shape(pts, parent, fill, name=name)
    if outline:
        poly(pts, parent, cyclic=True, name=name + ' line')
    return f


# ------------------------------------------------------------------ animation compat (4.5 legacy + 5.x slotted actions)
def fcurves(idb):
    ad = getattr(idb, 'animation_data', None)
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, 'layers') and len(act.layers):
        out = []
        slot = getattr(ad, 'action_slot', None)
        for layer in act.layers:
            for strip in layer.strips:
                try:
                    cb = strip.channelbag(slot) if slot else None
                except Exception:
                    cb = None
                if cb:
                    out += list(cb.fcurves)
        if out:
            return out
    return list(getattr(act, 'fcurves', []))


def strips(sc=None):
    sc = sc or bpy.context.scene
    se = sc.sequence_editor or sc.sequence_editor_create()
    return se.strips if hasattr(se, 'strips') else se.sequences


def all_strips(sc=None):
    sc = sc or bpy.context.scene
    se = sc.sequence_editor
    if not se:
        return []
    return list(se.strips_all if hasattr(se, 'strips_all') else se.sequences_all)


def report(op, msg, level='INFO'):
    op.report({level}, msg)
    return {'FINISHED'} if level != 'ERROR' else {'CANCELLED'}


# ------------------------------------------------------------------ optional Doodle Library
def doodle_library():
    try:
        import importlib
        for name in ('doodle_library', 'bl_ext.user_default.doodle_library'):
            try:
                return importlib.import_module(name + '.api')
            except Exception:
                continue
    except Exception:
        pass
    return None


def lib_find(category, words):
    dl = doodle_library()
    if not dl:
        return None
    try:
        rows = dl.items(category)
    except Exception:
        return None
    for w in words:
        for r in rows:
            name = (r.get('name', '') + ' ' + r.get('id', '')).lower()
            if w in name:
                return r.get('id')
    return None
