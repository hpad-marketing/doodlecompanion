"""Hoodie cloth and colliders.

The hood bag and the hoodie hem are real cloth: pinned where they attach,
free where they hang, colliding with the legs, hands and head. Cloth follows
the rig (armature first), so it settles back into the authored shape.
"""
import bpy
from skin import vgroup, smoothstep


def _pin(ob, name, fn):
    g = vgroup(ob, name)
    for v in ob.data.vertices:
        w = max(0.0, min(1.0, fn(v.co)))
        g.add([v.index], w, 'REPLACE')
    return g


def _cloth(ob, pin, mass=0.12, stiff=12.0, bend=0.4, enabled=True):
    # cloth goes right after the armature so it rides on the rig
    md = ob.modifiers.new('Hoodie cloth', 'CLOTH')
    order = [m.name for m in ob.modifiers]
    idx = order.index('Armature') + 1 if 'Armature' in order else 0
    while ob.modifiers.find(md.name) > idx:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_move_up(modifier=md.name)
    s = md.settings
    s.quality = 6
    s.mass = mass
    s.air_damping = 2.0
    s.tension_stiffness = stiff
    s.compression_stiffness = stiff
    s.shear_stiffness = stiff * 0.5
    s.bending_stiffness = bend
    s.tension_damping = 5
    s.compression_damping = 5
    s.shear_damping = 5
    s.bending_damping = 1.0
    s.vertex_group_mass = pin
    s.pin_stiffness = 2.0
    s.use_internal_springs = False
    s.use_pressure = False
    cs = md.collision_settings
    cs.use_collision = True
    cs.distance_min = 0.004
    cs.use_self_collision = False
    md.point_cache.frame_start = 1
    md.point_cache.frame_end = 250
    md.show_viewport = enabled
    md.show_render = enabled
    return md


def _collider(ob):
    md = ob.modifiers.new('Collision', 'COLLISION')
    order = [m.name for m in ob.modifiers]
    idx = order.index('Armature') + 1 if 'Armature' in order else 0
    while ob.modifiers.find(md.name) > idx:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_move_up(modifier=md.name)
    ob.collision.thickness_outer = 0.004
    ob.collision.damping = 0.5
    ob.collision.cloth_friction = 5
    return md


def setup_cloth(objs, head, legs, arm, S):
    hood = objs['hood']
    ys = [v.co.y for v in hood.data.vertices]
    zs = [v.co.z for v in hood.data.vertices]
    y0, y1 = min(ys), max(ys)
    z0, z1 = min(zs), max(zs)
    # front rim (towards the neck) and the top are sewn on; the back of the bag swings
    pin = _pin(hood, 'pin', lambda c: max(1 - smoothstep(0.0, 0.55, (c.y - y0) / (y1 - y0)),
                                          smoothstep(0.75, 1.0, (c.z - z0) / (z1 - z0))))
    _cloth(hood, pin.name, mass=0.08, stiff=10.0, bend=0.3)
    shirt = objs['shirt']
    zs = [v.co.z for v in shirt.data.vertices]
    sz0, sz1 = min(zs), max(zs)
    # everything above the waist is held by the body; the open hem softens to 30 % pinned so it drapes on the legs
    pin = _pin(shirt, 'pin', lambda c: 0.3 + 0.7 * smoothstep(0.05, 0.45, (c.z - sz0) / (sz1 - sz0)))
    _cloth(shirt, pin.name, mass=0.15, stiff=18.0, bend=2.0)
    for s in 'LR':
        _collider(legs[s][0])
        _collider(objs[f'hand.{s}'])
    _collider(head)
    if 'pelvis' in objs:
        _collider(objs['pelvis'])
    _collider(objs['neck'])
