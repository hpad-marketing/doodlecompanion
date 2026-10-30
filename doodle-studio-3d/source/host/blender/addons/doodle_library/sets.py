"""Room sets around Bunny and parallax cameras.

A set is a closed block (floor and three walls, or ground to the horizon) dressed
by hand at real scale to Bunny, stored as one collection in sets/sets.blend.
switch_set swaps the whole room; set_prop ticks single pieces on or off, and the
choices are remembered per room in scene["dsl_set_state"].
"""
import math

import bpy
from mathutils import Vector

from . import assets, index, paths, style

WALL_Y = 2.2           # back wall distance behind Bunny (m)
CAM_FOV = 30.0          # degrees, vertical (portrait)
FRAME_H = 17.07 * 0.125  # Doodle Studio frame height at the subject, camZoom 1
PIVOT_Z = 4.145 * 0.125


def cam_distance(fov=CAM_FOV, zoom=1.0):
    return (FRAME_H / zoom / 2) / math.tan(math.radians(fov) / 2)


def setup_camera(fov=CAM_FOV, zoom=1.0):
    """Turn the scene camera into an eye-level perspective camera framed like Doodle Studio."""
    sc = bpy.context.scene
    cam = sc.camera
    if not cam:
        cam = bpy.data.objects.new('CAM', bpy.data.cameras.new('CAM'))
        sc.collection.objects.link(cam)
        sc.camera = cam
    cam.data.type = 'PERSP'
    # AUTO fit: the sensor width spans the long side, which is what Bunny's ink maths assumes
    cam.data.sensor_fit = 'AUTO'
    cam.data.angle = math.radians(fov)
    cam.data.clip_end = 400
    d = cam_distance(fov, zoom)
    cam.location = (0, -d, PIVOT_Z)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    return cam


def long_fov(cam):
    """Field of view across the frame's long side, in degrees."""
    return math.degrees(2 * math.atan(cam.data.sensor_width / 2 / cam.data.lens))


def half_width_at(y, cam):
    """Half the visible frame width at depth y (portrait 9:16)."""
    d = y - cam.location.y
    sc = bpy.context.scene
    aspect = sc.render.resolution_x / max(1, sc.render.resolution_y)
    return math.tan(math.radians(long_fov(cam)) / 2) * d * min(aspect, 1 / aspect)


def bunny_height():
    zs = [(o.matrix_world @ Vector(c)).z for o in bpy.data.objects
          if o.type == 'MESH' and o.name.startswith('BUNNY_') and o.visible_get() for c in o.bound_box]
    return (max(zs) - min(zs)) if zs else 1.02


def sets():
    """[{id, name, kind, props:[{id, label, on}]}] for every room set in the library."""
    out = []
    for it in index.items('set'):
        d = it.get('data') or {}
        out.append({'id': d.get('room', it['id'][4:]), 'name': it['name'], 'kind': d.get('kind'),
                    'sub': it.get('sub'), 'props': d.get('props', [])})
    return out


def current_collection():
    return bpy.data.collections.get('Doodle Set')


def set_objects():
    coll = current_collection()
    return [o for o in coll.all_objects if o.get('dsl_set')] if coll else []


def clear_set():
    coll = current_collection()
    if not coll:
        return
    for child in list(coll.children):
        for ob in list(child.all_objects):
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and getattr(me, 'users', 1) == 0:
                bpy.data.meshes.remove(me)
        bpy.data.collections.remove(child)
    for ob in list(coll.objects):
        bpy.data.objects.remove(ob)


def switch_set(room_id, keep_choices=True, shadows=None):
    """Swap the whole room. Prop ticks you made for a room are remembered per room."""
    item = index.get('set-' + room_id)
    if not item:
        raise RuntimeError('Unknown set: ' + room_id)
    sc = bpy.context.scene
    state = dict(sc.get('dsl_set_state', {}) or {})
    choices = {k: dict(v) for k, v in dict(state.get('choices', {})).items()}
    cam = sc.camera if (sc.camera and sc.camera.data.type == 'PERSP') else setup_camera()
    clear_set()
    root = assets.target_collection('Doodle Set')
    with bpy.data.libraries.load(paths.lib_path(item['file']), link=False) as (src, dst):
        dst.collections = [item['datablock']]
    coll = dst.collections[0]
    root.children.link(coll)
    mats = style.materials()
    mine = choices.get(room_id, {}) if keep_choices else {}
    for ob in list(coll.all_objects):
        if ob.type != 'MESH':
            continue
        style.apply_style(ob, cam, mats, seed=(hash(ob.name) % 89) * 0.11)
        on = bool(ob.get('dsl_shell')) or mine.get(ob.get('dsl_prop'), bool(ob.get('dsl_default', 1)))
        ob.hide_viewport = ob.hide_render = not on
    state['set'] = room_id
    state['choices'] = choices
    sc['dsl_set_state'] = state
    if shadows is not None:
        style.set_shadows(shadows)
    try:  # seats, beds, counters and tables get their sit / lie / lean / grab spots
        from . import interact
        interact.auto_anchors([o for o in coll.all_objects if o.type == 'MESH' and not o.get('dsl_shell')])
    except Exception as e:
        print('Doodle Library: spots not added:', e)
    if sc.get('dsl_time', 'day') != 'day':  # keep the time of day: the new room's lamps switch on too
        from . import lighting
        lighting.set_time(sc['dsl_time'])
    index.mark_used(item['id'])
    return coll


def set_prop(prop_id, on):
    """Show or hide one piece of the current set (things standing on it follow when hidden)."""
    sc = bpy.context.scene
    state = dict(sc.get('dsl_set_state', {}) or {})
    room = state.get('set')
    if not room:
        raise RuntimeError('No set loaded')
    for ob in set_objects():
        if ob.get('dsl_prop') == prop_id or (not on and ob.get('dsl_on') == prop_id):
            ob.hide_viewport = ob.hide_render = not on
    choices = {k: dict(v) for k, v in dict(state.get('choices', {})).items()}
    choices.setdefault(room, {})[prop_id] = bool(on)
    state['choices'] = choices
    sc['dsl_set_state'] = state


def set_state():
    state = dict(bpy.context.scene.get('dsl_set_state', {}) or {})
    props = {o['dsl_prop']: not o.hide_render for o in set_objects() if not o.get('dsl_shell')}
    return {'set': state.get('set'), 'props': props}


def declutter(keep=4):
    """Keep the biggest few pieces of the current set, hide the rest."""
    obs = [o for o in set_objects() if not o.get('dsl_shell') and not o.hide_render]
    obs.sort(key=lambda o: -(o.dimensions.x * o.dimensions.y * o.dimensions.z))
    for o in obs[keep:]:
        set_prop(o['dsl_prop'], False)


# ------------------------------------------------------------------ parallax camera
def parallax_camera(mode='orbit', frames=72, amount=1.0, start=None):
    """Key an eased camera move that shows depth: orbit (Bunny stays centred, the
    room turns with the camera), truck (slide sideways) or push (dolly in).
    The camera stays at eye level and never tilts."""
    from .motions import smooth, _fcurves
    sc = bpy.context.scene
    cam = sc.camera if (sc.camera and sc.camera.data.type == 'PERSP') else setup_camera()
    start = sc.frame_current if start is None else start
    d = cam_distance(long_fov(cam))
    pivot = Vector((0, 0, PIVOT_Z))

    def pose(t):
        if mode == 'truck':
            return Vector((-0.6 * amount + 1.2 * amount * t, -d, PIVOT_Z)), 0.0
        if mode == 'push':
            return Vector((0, -d * (1 - 0.35 * amount * t), PIVOT_Z)), 0.0
        a = math.radians(-18 * amount + 36 * amount * t)
        return pivot + Vector((math.sin(a) * d, -math.cos(a) * d, 0)), a

    # replace any camera keys already in the range
    for fc in _fcurves(cam):
        if fc.data_path in ('location', 'rotation_euler'):
            idx = [i for i, kp in enumerate(fc.keyframe_points) if start <= kp.co[0] <= start + frames]
            for i in reversed(idx):
                fc.keyframe_points.remove(fc.keyframe_points[i], fast=True)
            fc.update()
    step = 3
    fs = list(range(0, frames, step)) + [frames]
    for i in fs:
        loc, yaw = pose(smooth(i / frames))
        cam.location = loc
        cam.rotation_euler = (math.pi / 2, 0, yaw)
        cam.keyframe_insert('location', frame=start + i)
        cam.keyframe_insert('rotation_euler', frame=start + i)
    for fc in _fcurves(cam):
        for kp in fc.keyframe_points:
            if start <= kp.co[0] <= start + frames:
                kp.interpolation = 'LINEAR'  # dense keys already carry the ease
    return cam
