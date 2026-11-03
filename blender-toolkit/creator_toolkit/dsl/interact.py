"""Bunny uses the room: sit, lie and lean spots on furniture, grab spots on tables, and
bouncy physics props.

  auto_anchors()          give every chair, couch, bed, counter and table in the scene its
                          spots (done for you when a set is switched)
  sit(spot, frame)        Bunny sits on it: pose, height and facing all line up, no clipping
  put_on(ob, spot)        a prop rests on a grab spot (a mug on the table)
  physics(ob, 'ball')     ball / paper / pillow / book / beanbag, then simulate(1, 120)
"""
import math

import bpy
from mathutils import Matrix, Vector

SIT = {'sofa', 'armchair', 'dining_chair', 'stool', 'swivel_chair', 'cafe_chair', 'school_chair', 'park_bench',
       'platform_bench', 'waiting_seats', 'workout_bench', 'wooden_bench', 'plastic_chair', 'museum_bench', 'log_seat',
       'garden_chair', 'barber_chair', 'throne', 'captain_chair', 'berths', 'plane_seats', 'office_chair_ride', 'car',
       'taxi', 'auto_rickshaw', 'city_scooter', 'cycle', 'rocket', 'hot_air_balloon', 'paper_plane', 'magic_carpet',
       'skateboard_ride', 'shopping_trolley', 'swings', 'seesaw', 'chair_rows', 'haystack'}
LIE = {'bed', 'sun_lounger'}
LEAN = {'kitchen_counter', 'cafe_counter', 'bank_counter', 'checkout_counter', 'railing', 'parapet', 'host_stand'}
GRAB = {'coffee_table', 'dining_table', 'desk', 'cafe_table', 'conference_table', 'nightstand', 'lab_bench', 'workbench',
        'school_desk', 'kitchen_counter', 'cafe_counter', 'tv_stand', 'wall_shelf', 'bank_counter', 'checkout_counter'}
SIT_MOTION = 'motion-sit-for-story'


def _model(ob):
    m = ob.get('dsl_model') or ob.get('dsl_id', '')
    for pre in ('scenery-', 'prop-'):
        if m.startswith(pre):
            m = m[len(pre):]
    return m


def add_anchor(ob, kind, local, facing=0.0):
    """An empty on the piece marking where Bunny sits / lies / leans or a prop can rest."""
    name = '%s %s spot' % (ob.name, kind)
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old)
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'SINGLE_ARROW' if kind != 'grab' else 'CIRCLE'
    e.empty_display_size = 0.12
    e.hide_render = True
    e['dsl_anchor'] = kind
    (ob.users_collection[0] if ob.users_collection else bpy.context.scene.collection).objects.link(e)
    e.parent = ob
    e.matrix_parent_inverse = Matrix.Identity(4)
    s = ob.matrix_world.to_scale()[0] or 1.0
    e.location = Vector(local)
    e.rotation_euler = (math.radians(-90), 0, facing) if kind != 'grab' else (0, 0, 0)
    e.scale = (1 / s,) * 3
    return e


def _up_surfaces(ob):
    """Upward faces of the evaluated mesh in object space, grouped by height: [(z, area, centre)]."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.original.data if ev.type != 'MESH' else ev.data
    groups = {}
    for p in me.polygons:
        if p.normal.z > 0.9:
            k = round(p.center.z, 2)
            a, c = groups.get(k, (0.0, Vector()))
            groups[k] = (a + p.area, c + p.center * p.area)
    return sorted(((z, a, c / max(a, 1e-9)) for z, (a, c) in groups.items()), key=lambda t: t[0])


def auto_anchors(objs=None):
    """Sit, lie, lean and grab spots for every piece of furniture in `objs` (default: scene)."""
    objs = objs if objs is not None else [o for o in bpy.context.scene.objects if o.type == 'MESH']
    made = 0
    for ob in objs:
        m = _model(ob)
        if not m or ob.get('dsl_seat') or not ob.visible_get():
            continue
        surf = _up_surfaces(ob)
        if not surf:
            continue
        top = max(z for z, a, c in surf)
        if m in SIT or m in LIE:
            # the seat: the biggest upward surface below two thirds of the piece's height
            low = [t for t in surf if t[0] < top * 0.67 + 1e-6 and t[0] > 0.12] or surf
            z, a, c = max(low, key=lambda t: t[1])
            add_anchor(ob, 'lie' if m in LIE else 'sit', (c.x, c.y - 0.05, z))
            made += 1
        if m in LEAN:
            add_anchor(ob, 'lean', (0, -0.35, top))
            made += 1
        if m in GRAB:
            z, a, c = max([t for t in surf if t[0] > top - 0.05], key=lambda t: t[1])
            add_anchor(ob, 'grab', (c.x, c.y, z))
            made += 1
    return made


def anchors(kind=None):
    return [o for o in bpy.context.scene.objects if o.get('dsl_anchor') and (kind is None or o['dsl_anchor'] == kind)]


def nearest(kind='sit', to=None):
    to = to or Vector((0, 0, 0))
    a = anchors(kind)
    return min(a, key=lambda e: (e.matrix_world.translation - to).length) if a else None


def _rig():
    return bpy.data.objects.get('BUNNY_rig')


def _seat_drop(arm):
    """How far below the rig origin Bunny's seat (bottom of the pelvis/legs) is right now."""
    zs = []
    for n in ('BUNNY_pelvis', 'BUNNY_leg.L', 'BUNNY_leg.R'):
        o = bpy.data.objects.get(n)
        if o:
            dg = bpy.context.evaluated_depsgraph_get()
            ev = o.evaluated_get(dg)
            zs += [(ev.matrix_world @ v.co).z for v in ev.data.vertices]
    return (min(zs) - arm.matrix_world.translation.z) if zs else 0.0


def sit(spot=None, frame=None, motion=SIT_MOTION):
    """Sit Bunny on a sit spot (nearest one if none given): plays the sit pose, then lines his
    seat up with the spot and turns him the way the seat faces. Keyed at `frame`."""
    from . import api
    arm = _rig()
    if arm is None:
        raise RuntimeError('Bunny (BUNNY_rig) is not in this file.')
    spot = spot or nearest('sit', arm.matrix_world.translation)
    if spot is None:
        raise RuntimeError('No sit spot in the scene: switch to a set with seats, or run auto_anchors().')
    sc = bpy.context.scene
    f = sc.frame_current if frame is None else frame
    if motion and api.get(motion):
        api.insert(motion, frame=f)
    sc.frame_set(f)
    bpy.context.view_layer.update()
    M = spot.matrix_world
    fwd = (M.to_3x3() @ Vector((0, 0, 1)))
    arm.rotation_euler[2] = math.atan2(fwd.x, -fwd.y) if fwd.length > 1e-6 else 0.0
    arm.location.x, arm.location.y = M.translation.x, M.translation.y
    arm.location.z = 0.0
    bpy.context.view_layer.update()
    arm.location.z = M.translation.z - _seat_drop(arm) + 0.004
    for path in ('location', 'rotation_euler'):
        arm.keyframe_insert(path, frame=f)
    return spot


def put_on(ob, spot=None):
    """Rest a prop on a grab spot (nearest to it when none is given)."""
    spot = spot or nearest('grab', ob.matrix_world.translation)
    if spot is None:
        raise RuntimeError('No grab spot in the scene.')
    from .placement import _local_bounds
    mn, mx = _local_bounds(ob)
    s = ob.matrix_world.to_scale()
    p = spot.matrix_world.translation
    ob.location = (p.x, p.y, p.z - mn.z * s.z + 0.001)
    return ob


# ---------------------------------------------------------------- physics props
PHYSICS = {  # mass kg, bounciness, friction, linear / angular damping, shape
    'ball': (0.4, 0.75, 0.5, 0.05, 0.1, 'SPHERE'),
    'paper': (0.01, 0.05, 0.6, 0.92, 0.6, 'BOX'),
    'pillow': (0.5, 0.15, 0.9, 0.4, 0.5, 'CONVEX_HULL'),
    'book': (0.6, 0.15, 0.7, 0.1, 0.2, 'BOX'),
    'beanbag': (2.0, 0.02, 1.0, 0.5, 0.8, 'CONVEX_HULL'),
}


def _world():
    sc = bpy.context.scene
    if not sc.rigidbody_world:
        with bpy.context.temp_override(scene=sc):
            bpy.ops.rigidbody.world_add()
    return sc.rigidbody_world


def _add_body(ob, kind='ACTIVE'):
    _world()
    if not ob.rigid_body:
        sc = bpy.context.scene
        sc.rigidbody_world.collection = sc.rigidbody_world.collection or bpy.data.collections.new('RigidBodyWorld')
        if ob.name not in sc.rigidbody_world.collection.objects:
            sc.rigidbody_world.collection.objects.link(ob)
    ob.rigid_body.type = kind
    return ob.rigid_body


def physics(ob, kind='ball'):
    """Make a prop fall, bounce and settle. Floors, furniture and Bunny become colliders."""
    mass, bounce, fric, ld, ad, shape = PHYSICS[kind]
    rb = _add_body(ob)
    rb.mass, rb.restitution, rb.friction = mass, bounce, fric
    rb.linear_damping, rb.angular_damping = ld, ad
    rb.collision_shape = shape
    rb.collision_margin = 0.002
    colliders()
    ob['dsl_physics'] = kind
    return rb


def colliders():
    """Set shells, furniture and every character part become passive colliders; Bunny's
    parts follow his animation (animated) so props bounce off him, never through."""
    from .collide import body_objects
    n = 0
    for o in bpy.context.scene.objects:
        if o.type != 'MESH' or o.get('dsl_physics') or not o.visible_get():
            continue
        is_body = o in body_objects()
        if o.get('dsl_set') or is_body:
            rb = _add_body(o, 'PASSIVE')
            rb.collision_shape = 'MESH'
            rb.kinematic = is_body
            rb.restitution = 0.4
            n += 1
    return n


def simulate(start=None, end=None):
    sc = bpy.context.scene
    w = _world()
    w.point_cache.frame_start = start or sc.frame_start
    w.point_cache.frame_end = end or sc.frame_end
    return w


def squish(ob, frame, amount=0.35, length=6):
    """Pillow / beanbag squash when Bunny sits on it, then it springs back."""
    s = ob.scale.copy()
    for df, k in ((0, 0.0), (2, 1.0), (length, 0.3), (length + 4, 0.0)):
        ob.scale = (s.x * (1 + amount * 0.5 * k), s.y * (1 + amount * 0.5 * k), s.z * (1 - amount * k))
        ob.keyframe_insert('scale', frame=frame + df)
    ob.scale = s
    return ob
