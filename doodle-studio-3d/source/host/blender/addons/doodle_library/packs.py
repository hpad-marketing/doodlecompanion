"""Asset-pack pieces come alive when you insert them.

  moving parts   lids, doors, curtains, wheels, wings come in parented on their hinge;
                 set_open(ob, 0..1) keys them, wheels turn as the piece moves, wings flap
  typed text     signs, placards, bubbles and neon get editable 3D text (dsl.add_text rules)
  your clip      screens and frames show any image or MP4: set_screen(ob, path)
  lights         spotlights carry a real light; neon and fairy lights glow
  reactions      pop in over Bunny's head with a wobble: react('heart')
  bubbles        always turn to the camera
  seats          rides and chairs carry a sit spot (see interact.py)
  foreground     frame_shot(ob, 'left') parks framing pieces near the lens on a third
"""
import json
import math

import bpy
from mathutils import Matrix, Vector

from . import index, paths, style, text3d
from . import gnodes

SCREEN_MAT = 'DSL screen'
NEON_MAT = 'DSL_neon'


def meta(ob, key, default=None):
    v = ob.get('dsl_' + key)
    if v is None:
        return default
    try:
        return json.loads(v) if isinstance(v, str) else v
    except ValueError:
        return v


def _load(names, path):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in names if n in src.objects]
    return [o for o in dst.objects if o]


def dress(ob, cam=None):
    """Called by assets.insert_object for every pack piece."""
    cam = cam or bpy.context.scene.camera
    coll = ob.users_collection[0] if ob.users_collection else bpy.context.scene.collection
    parts = meta(ob, 'parts') or []
    if parts:
        it = index.get(ob.get('dsl_id', '')) or {}
        for p in _load(parts, paths.lib_path(it.get('file', 'packs/packs.blend'))):
            coll.objects.link(p)
            p.parent = ob
            p.matrix_parent_inverse = Matrix.Identity(4)
            p.location = Vector(p['dsl_pivot'])
            p['dsl_id'] = ob.get('dsl_id', '') + '/' + p.name.split('__')[-1]
            style.apply_style(p, cam, seed=0.21)
            _animate_part(ob, p)
    t = meta(ob, 'text')
    if t:
        words, at, size = t
        add_label(ob, words, at, size)
    if meta(ob, 'light'):
        kind, at, rot, power = meta(ob, 'light')
        ld = bpy.data.lights.new(ob.name + ' light', kind)
        ld.energy = power
        ld.color = (1.0, 0.86, 0.6)
        if kind == 'SPOT':
            ld.spot_size = math.radians(40)
            ld.spot_blend = 0.4
        lo = bpy.data.objects.new(ob.name + ' light', ld)
        coll.objects.link(lo)
        lo.parent = ob
        lo.location = Vector(at)
        lo.rotation_euler = rot
    if meta(ob, 'neon'):
        glow(ob)
    if meta(ob, 'place') == 'free' and cam and not ob.get('dsl_reaction'):
        face_camera(ob, cam)
    if meta(ob, 'seat'):
        from . import interact
        interact.add_anchor(ob, 'sit', meta(ob, 'seat'))
    if meta(ob, 'breathe'):
        _loop_scale(ob, (1, 1, 1.04), 60)
    if meta(ob, 'float'):
        _loop_offset(ob, 'location', 2, 0.04, 72)
    if meta(ob, 'steam'):
        from . import fx
        fx.add_effect('steam', location=ob.matrix_world @ Vector(meta(ob, 'steam')), parent=ob)
    return ob


# ---------------------------------------------------------------- moving parts
def parts_of(ob):
    return [c for c in ob.children if c.get('dsl_part')]


def _axis_index(p):
    return 'XYZ'.index(p.get('dsl_axis', 'X'))


def set_open(ob, amount=1.0, frame=None, part=None):
    """Open (1) or close (0) every hinge/slide part, or just `part`. Keys it at `frame`."""
    n = 0
    for p in parts_of(ob):
        if part and not p.name.endswith('__' + part):
            continue
        k = p['dsl_part']
        i = _axis_index(p)
        if k == 'hinge':
            r = list(p.rotation_euler)
            r[i] = math.radians(p['dsl_amount']) * amount
            p.rotation_euler = r
            path = 'rotation_euler'
        elif k == 'slide':
            loc = Vector(p['dsl_pivot'])
            loc[i] += p['dsl_amount'] * amount
            p.location = loc
            path = 'location'
        else:
            continue
        if frame is not None:
            p.keyframe_insert(path, frame=frame)
        n += 1
    return n


def _drive(target, path, index_, expr, vars_=()):
    fc = target.driver_add(path, index_)
    d = fc.driver
    d.type = 'SCRIPTED'
    for name, obj, dpath in vars_:
        v = d.variables.new()
        v.name = name
        v.type = 'SINGLE_PROP'
        v.targets[0].id = obj
        v.targets[0].data_path = dpath
    d.expression = expr
    return fc


def _animate_part(ob, p):
    k, i = p['dsl_part'], _axis_index(p)
    if k == 'wheel':  # rolls with the piece: angle = distance / radius
        r = max(p['dsl_amount'], 1e-3)
        _drive(p, 'rotation_euler', i, '-x / %f' % r, [('x', ob, 'location.x')])
    elif k == 'spin':
        _drive(p, 'rotation_euler', i, 'frame * %f' % (math.radians(p['dsl_amount']) / 48.0))
    elif k == 'flap':
        _drive(p, 'rotation_euler', i, 'sin(frame * 0.9) * %f' % math.radians(p['dsl_amount']))
    elif k == 'flicker':
        _drive(p, 'scale', 2, '1 + %f * sin(frame * 2.3) * sin(frame * 0.7)' % p['dsl_amount'])


# ---------------------------------------------------------------- text, screens, glow
def add_label(ob, words, at=(0, -0.02, 0), size=0.1, kind='flat'):
    """Editable 3D text stuck on a sign. Type a new one with set_label(ob, 'NEW')."""
    t = text3d.add_text(words, kind=kind, name=ob.name + ' text', fill='ink')
    mod = text3d.text_modifier(t)
    ids = text3d._ids(mod)
    s = ob.matrix_world.to_scale()[0] or 1.0
    gnodes.gn_set(mod, ids['Size'], size)
    gnodes.gn_set(mod, ids['Depth'], min(0.01, size * 0.12))
    t.parent = ob
    t.matrix_parent_inverse = Matrix.Identity(4)
    t.location = Vector(at) + Vector((0, -0.006, -size * 0.35))
    t.scale = (1, 1, 1)
    t['dsl_label_of'] = ob.name
    return t


def label_of(ob):
    return next((c for c in ob.children if c.get('dsl_label_of')), None)


def set_label(ob, words):
    t = label_of(ob)
    if not t:
        t = add_label(ob, words)
    return text3d.set_text(t, words)


def set_screen(ob, path):
    """Show an image or video (MP4, MOV, PNG, JPG) on a screen, frame or poster."""
    sc = meta(ob, 'screen')
    if not sc:
        raise RuntimeError('%s has no screen.' % ob.name)
    w, h, x, y, zc = sc
    old = next((c for c in ob.children if c.get('dsl_screen')), None)
    if old:
        bpy.data.objects.remove(old)
    me = bpy.data.meshes.new(ob.name + ' screen')
    me.from_pydata([(-w / 2, 0, -h / 2), (w / 2, 0, -h / 2), (w / 2, 0, h / 2), (-w / 2, 0, h / 2)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for i, c in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = c
    so = bpy.data.objects.new(ob.name + ' screen', me)
    (ob.users_collection[0] if ob.users_collection else bpy.context.scene.collection).objects.link(so)
    so.parent = ob
    so.location = (x, y - 0.002, zc)
    # a part that hinges (a laptop lid) carries its own screen spot
    for p in parts_of(ob):
        if meta(p, 'screen'):
            so.parent = p
    so['dsl_screen'] = True
    img = bpy.data.images.load(path, check_existing=True)
    movie = path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))
    if movie:
        img.source = 'MOVIE'
    m = bpy.data.materials.new('%s %s' % (SCREEN_MAT, ob.name))
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    if movie:
        tex.image_user.frame_duration = img.frame_duration
        tex.image_user.use_auto_refresh = True
        tex.image_user.use_cyclic = True
    em = nt.nodes.new('ShaderNodeEmission')
    outn = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tex.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], outn.inputs['Surface'])
    me.materials.append(m)
    return so


def glow(ob, strength=4.0):
    """Mustard neon: the piece lights up (bloom comes from the render's glare)."""
    m = bpy.data.materials.get(NEON_MAT)
    if not m:
        m = bpy.data.materials.new(NEON_MAT)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        em = nt.nodes.new('ShaderNodeEmission')
        em.inputs['Color'].default_value = (0.75, 0.38, 0.07, 1)
        em.inputs['Strength'].default_value = strength
        o = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(em.outputs[0], o.inputs['Surface'])
    for slot in ob.material_slots:
        if slot.material and 'mustard' in slot.material.name.lower():
            slot.link = 'OBJECT'
            slot.material = m
    return m


def face_camera(ob, cam):
    c = ob.constraints.new('DAMPED_TRACK')
    c.name = 'DSL face camera'
    c.target = cam
    c.track_axis = 'TRACK_NEGATIVE_Y'
    return c


# ---------------------------------------------------------------- loops
def _cycle(ob):
    ad = ob.animation_data
    if not ad or not ad.action:
        return
    from .motions import _fcurves
    for fc in _fcurves(ob):
        if not any(m.type == 'CYCLES' for m in fc.modifiers):
            fc.modifiers.new('CYCLES')


def _loop_scale(ob, peak, period):
    s0 = ob.scale.copy()
    for f, k in ((1, 0), (period // 2, 1), (period, 0)):
        ob.scale = Vector([a * (1 + (b - 1) * k) for a, b in zip(s0, peak)])
        ob.keyframe_insert('scale', frame=f)
    ob.scale = s0
    _cycle(ob)


def _loop_offset(ob, path, i, amp, period):
    v0 = getattr(ob, path)[i]
    for f, k in ((1, 0), (period // 2, 1), (period, 0)):
        getattr(ob, path)[i] = v0 + amp * k
        ob.keyframe_insert(path, index=i, frame=f)
    getattr(ob, path)[i] = v0
    _cycle(ob)


# ---------------------------------------------------------------- reactions over Bunny's head
REACTIONS = ('question', 'exclaim', 'sweat', 'heart', 'anger', 'zzz', 'star', 'lightbulb', 'note', 'dizzy', 'tear',
             'sparkle')


def head_top(holder='BUNNY'):
    head = bpy.data.objects.get(holder + '_head')
    if not head:
        return Vector((0, 0, 1.0))
    pts = [head.matrix_world @ Vector(c) for c in head.bound_box]
    top = max(p.z for p in pts)
    cx = sum(p.x for p in pts) / 8
    cy = min(p.y for p in pts)
    return Vector((cx, cy, top))


def react(name='question', frame=None, side=1, holder='BUNNY'):
    """Pop a reaction symbol over Bunny's head: grows past full size, settles, wobbles."""
    from . import assets
    it = index.get('scenery-react_' + name)
    if not it:
        raise KeyError('No reaction "%s". Pick one of: %s' % (name, ', '.join(REACTIONS)))
    ob = assets.insert_object(it)
    top = head_top(holder)
    ob.location = top + Vector((0.18 * side, -0.05, 0.02))
    ob['dsl_reaction'] = True
    pop_in(ob, frame)
    return ob


def pop_in(ob, frame=None, length=8):
    f = bpy.context.scene.frame_current if frame is None else frame
    s = ob.scale.copy()
    for df, k, rz in ((0, 0.01, 0), (length * 0.6, 1.25, 8), (length, 1.0, -5), (length * 1.6, 1.0, 3), (length * 2.2, 1.0, 0)):
        ob.scale = s * k
        ob.rotation_euler[1] = math.radians(rz)
        ob.keyframe_insert('scale', frame=f + df)
        ob.keyframe_insert('rotation_euler', index=1, frame=f + df)
    ob.scale = s
    return ob


# ---------------------------------------------------------------- foreground framing
FRAME_PIECES = ('fg_door_frame', 'fg_arch')  # these frame Bunny (frame within a frame); the rest peek in at an edge


def frame_shot(ob, side='left', cam=None):
    """Park a framing piece between the lens and Bunny for real parallax.

    Door frames and arches go dead centre, halfway to Bunny, so he stands inside them.
    Plants, leaves, curtains, lamps, fences, shelves and window edges peek in from the
    left or right edge and stay out of his face band."""
    cam = cam or bpy.context.scene.camera
    if not cam:
        raise RuntimeError('No camera.')
    from .sets import half_width_at
    cy = cam.location.y
    model = ob.get('dsl_id', '').replace('scenery-', '')
    if model in FRAME_PIECES:
        y = cy * 0.45
        ob.location = (0.0, y, 0.0)
    else:
        y = cy * 0.62
        hw = half_width_at(y, cam)
        ob.location = (hw * (0.92 if side == 'right' else -0.92), y, 0.0)
        ob.rotation_euler = (0, 0, math.pi if side == 'right' else 0)  # turn round to lean into the frame
    return ob
