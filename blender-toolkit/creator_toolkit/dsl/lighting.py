"""One-click time of day for every set, doodle skies, lightning and flickering bulbs.

  set_time('day')      flat Doodle Studio look (the default)
  set_time('golden')   low warm sun, long ink shadows
  set_time('night')    the room sinks toward ink; every lamp in the set switches on and
                       lights a pool around itself (brand colours only: no blue night)
  sky('stars')         a sky behind outdoor sets: day, sunset, stars, storm
  lightning(48)        a flash at frame 48 (storm sky, spooky sets)
  flicker(ob)          a bulb that stutters
"""
import math

import bpy
from mathutils import Vector

from . import style

TIMES = ('day', 'golden', 'night')
LAMPS = {  # model -> (bulb height in model metres, light power W, radius m)
    'table_lamp': (0.45, 40, 0.05), 'floor_lamp': (1.45, 60, 0.06), 'lamp_post': (3.1, 160, 0.1),
    'pendant_lamp': (-0.25, 60, 0.06), 'ceiling_light': (-0.1, 80, 0.08), 'bare_bulb': (-0.95, 50, 0.04),
    'camp_lantern': (0.2, 30, 0.04), 'campfire': (0.15, 90, 0.15), 'fg_lamp': (1.5, 40, 0.06),
    'light_strings': (2.2, 40, 0.3), 'marigold_strings': (2.0, 0, 0), 'diyas': (0.06, 15, 0.03),
    'fairy_lights': (0.0, 25, 0.3), 'neon_sign': (0.25, 40, 0.2), 'sky_lantern': (0.15, 20, 0.08),
    'spotlight': (1.73, 0, 0),
}
LAMP_TAG = 'dsl_lamp_light'


def _model(ob):
    m = ob.get('dsl_model') or ob.get('dsl_id', '')
    for pre in ('scenery-', 'prop-'):
        if m.startswith(pre):
            m = m[len(pre):]
    return m


def lamps():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH' and _model(o) in LAMPS and o.visible_get()]


def _lamp_light(ob, on):
    old = [c for c in ob.children if c.get(LAMP_TAG)]
    for c in old:
        bpy.data.objects.remove(c)
    if not on:
        return None
    z, power, radius = LAMPS[_model(ob)]
    if power <= 0:
        return None
    ld = bpy.data.lights.new(ob.name + ' lamp', 'POINT')
    ld.energy = power
    ld.shadow_soft_size = radius
    ld.color = (1.0, 0.85, 0.55)
    lo = bpy.data.objects.new(ob.name + ' lamp', ld)
    (ob.users_collection[0] if ob.users_collection else bpy.context.scene.collection).objects.link(lo)
    lo.parent = ob
    lo.location = (0, -0.05, z)
    lo[LAMP_TAG] = True
    return lo


def set_time(kind='day', frame=None):
    """Switch the lighting of the whole scene. With `frame`, it is keyed (cut to night)."""
    if kind not in TIMES:
        raise KeyError('Pick one of: ' + ', '.join(TIMES))
    st = style.settings()
    sun = style.ensure_sun()
    style.materials()  # make sure the toon shader is the current version
    for m in bpy.data.materials:
        if m.get('dsl_toon') and m.get('dsl_toon') < style.TOON_VERSION:
            style.toon_material(m.name, style.MUSTARD_HEX)
    if kind == 'day':
        st['night'], st['shadows'] = 0.0, 0.0
        sun.data.energy = 6.0
        sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
        sun.data.color = (1, 1, 1)
    elif kind == 'golden':
        st['night'], st['shadows'], st['shade_mix'], st['form'] = 0.0, 1.0, 0.38, 0.35
        sun.data.energy = 5.0
        sun.rotation_euler = (math.radians(74), 0, math.radians(-58))  # low, raking from the side
        sun.data.color = (1.0, 0.88, 0.7)
    else:
        st['night'], st['shadows'] = 1.0, 0.0
        sun.data.energy = 0.0
    for ob in lamps():
        _lamp_light(ob, kind == 'night')
        if kind == 'night':
            from .packs import glow
            glow(ob, 3.0)
    _world(kind)
    if frame is not None:
        for k in ('night', 'shadows', 'shade_mix', 'form'):
            st.keyframe_insert('["%s"]' % k, frame=frame)
        sun.data.keyframe_insert('energy', frame=frame)
        sun.keyframe_insert('rotation_euler', frame=frame)
        from .motions import action_curves  # 5.x has no Action.fcurves
        for fc in action_curves(st.animation_data.action if st.animation_data else None):
            for k in fc.keyframe_points:
                k.interpolation = 'CONSTANT'
    bpy.context.scene['dsl_time'] = kind
    return kind


def _world(kind):
    w = bpy.context.scene.world
    if not w or not w.use_nodes:
        return
    bg = next((n for n in w.node_tree.nodes if n.type == 'BACKGROUND'), None)
    if not bg:
        return
    if 'dsl_day_color' not in w:
        w['dsl_day_color'] = list(bg.inputs['Color'].default_value)
    day = Vector(w['dsl_day_color'][:3])
    ink = Vector((0.0137, 0.0137, 0.0123))
    k = {'day': 0.0, 'golden': 0.12, 'night': style.NIGHT_DIM}[kind]
    c = day.lerp(ink, k)
    bg.inputs['Color'].default_value = (c.x, c.y, c.z, 1.0)


# ---------------------------------------------------------------- skies
SKIES = ('day', 'sunset', 'stars', 'storm')


def sky(kind='day'):
    """A hand-drawn sky behind outdoor sets: far cards placed on a big dome (cheap: a few
    hundred faces) so it reads at the same size from any lens."""
    from . import assets, index
    if kind not in SKIES:
        raise KeyError('Pick one of: ' + ', '.join(SKIES))
    for o in [o for o in bpy.context.scene.objects if o.get('dsl_sky')]:
        bpy.data.objects.remove(o)
    put = []

    def add(item_id, loc, s=1.0):
        it = index.get(item_id)
        if not it:
            return None
        ob = assets.insert_object(it, loc)
        ob.scale = (s, s, s)
        ob['dsl_sky'] = kind
        put.append(ob)
        return ob
    if kind in ('day', 'storm'):
        for x, y, z, s in ((-9, 40, 9, 9), (7, 46, 11, 10), (-1, 55, 14, 12), (14, 60, 8, 11)):
            add('scenery-cloud', (x, y, z), s)
    if kind == 'sunset':
        add('scenery-sun', (6, 80, 1.5), 16)
        for x, y, z, s in ((-12, 60, 6, 10), (10, 70, 9, 12)):
            add('scenery-cloud', (x, y, z), s)
    if kind == 'stars':
        add('scenery-starfield', (0, 70, -2), 18)
    if kind == 'storm':
        set_time('night')
        style.settings()['night'] = 0.55
    elif kind == 'stars':
        set_time('night')
    elif kind == 'sunset':
        set_time('golden')
    return put


def lightning(frame, flashes=2):
    """Flash the whole scene back to full light for a couple of frames."""
    st = style.settings()
    base = st.get('night', 0.0)
    f = frame
    for i in range(flashes):
        for df, v in ((0, base), (1, 0.0), (2, base * 0.6), (3, 0.0), (5, base)):
            st['night'] = v
            st.keyframe_insert('["night"]', frame=f + df)
        f += 9
    st['night'] = base
    return st


def flicker(ob, strength=0.8):
    """A bulb that stutters: its light and glow follow an uneven beat."""
    lights = [c for c in ob.children if c.type == 'LIGHT'] or ([ob] if ob.type == 'LIGHT' else [])
    for lo in lights:
        e = lo.data.energy or 50.0
        fc = lo.data.driver_add('energy')
        fc.driver.type = 'SCRIPTED'
        fc.driver.expression = '%f * (1 - %f * (sin(frame * 1.7) * sin(frame * 0.43) > 0.35))' % (e, strength)
    return lights
