"""Physics for the ship: settle props onto surfaces, zero-g, and a contact check.

Props are active rigid bodies; furniture, counters and the deck are passive.
settle() runs the simulation for a moment, then bakes each prop's resting
place as its real position, so a shot starts with everything sitting naturally.
"""
import bpy
from mathutils import Vector


def _rbw(scene):
    if scene.rigidbody_world is None:
        with bpy.context.temp_override(scene=scene):
            bpy.ops.rigidbody.world_add()
    return scene.rigidbody_world


def ensure_floor(scene=None):
    sc = scene or bpy.context.scene
    for ob in sc.objects:
        if ob.name.startswith("Deck") and ob.rigid_body is None:
            from . import kit as K
            K.rigid(ob, passive=True, shape="BOX")


def settle(scene=None, frames=50):
    sc = scene or bpy.context.scene
    ensure_floor(sc)
    w = _rbw(sc)
    props = [o for o in sc.objects if o.get("sb_physics") == "prop"]
    if not props:
        return 0
    start = sc.frame_current
    w.point_cache.frame_start = start
    w.point_cache.frame_end = start + frames
    w.substeps_per_frame = 20
    w.solver_iterations = 20
    for f in range(start, start + frames + 1):
        sc.frame_set(f)
    rest = {o.name: o.matrix_world.copy() for o in props}
    sc.frame_set(start)
    # bake: move each prop to where it came to rest
    for o in props:
        o.matrix_world = rest[o.name]
    w.point_cache.frame_end = start + 250
    sc.frame_set(start)
    return len(props)


def zero_g(on=True, scene=None, drift=0.15):
    """Gravity off and a gentle turbulence so loose things drift and tumble."""
    sc = scene or bpy.context.scene
    _rbw(sc)
    sc.use_gravity = not on
    sc.gravity = (0, 0, 0 if on else -9.81)
    f = bpy.data.objects.get("SB Zero-G Drift")
    if on and f is None:
        fd = bpy.data.objects.new("SB Zero-G Drift", None)
        sc.collection.objects.link(fd)
        fd.field.type = "TURBULENCE"
        fd.field.strength = drift
        fd.field.size = 1.5
        fd.field.flow = 0.0
    elif not on and f is not None:
        bpy.data.objects.remove(f)
    sc["sb_zero_g"] = bool(on)


def contacts(scene=None, tol=0.002):
    """Lists props whose bounding boxes sink into another prop (rough, fast)."""
    sc = scene or bpy.context.scene
    props = [o for o in sc.objects if o.get("sb_physics") == "prop"]
    boxes = {}
    for o in props:
        cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
        boxes[o.name] = (Vector([min(c[i] for c in cs) for i in range(3)]), Vector([max(c[i] for c in cs) for i in range(3)]))
    hits = []
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            (a0, a1), (b0, b1) = boxes[a], boxes[b]
            if all(a0[k] < b1[k] - tol and b0[k] < a1[k] - tol for k in range(3)):
                hits.append((a, b))
    return hits
