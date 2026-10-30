"""Props never go inside a character: held, floating or resting.

Bodies: every object with the custom property dsl_body = True, plus character parts by name
(<PREFIX>_head, _hood, _shirt, _pelvis, _leg.L/R, _neck, _hand.L/R, _tail) for any prefix
that has a <PREFIX>_rig or <PREFIX>_head, so Bunny, the Koala, the Frog and any later animal
are all covered.

How a prop gets out of a body:
  free prop   pushed out along the surface normal of the deepest point, plus a small margin
  held prop   turned about its grip point (twist, then tilt), then slid along its handle,
              all inside its grip limits, so the hand keeps holding it; the holding hand
              itself is allowed to touch (that's the grip)
Bake keys the fixes over the frame range. The live guard fixes the current frame on every
frame change while you scrub (off by default: it costs time on heavy scenes).
"""
import math

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

PARTS = ('head', 'hood', 'shirt', 'pelvis', 'leg.L', 'leg.R', 'neck', 'hand.L', 'hand.R', 'tail', 'body', 'torso',
         'arm.L', 'arm.R', 'sleeve_up.L', 'sleeve_up.R', 'sleeve_fore.L', 'sleeve_fore.R', 'cuff.L', 'cuff.R')
MARGIN = 0.002  # 2 mm clear of the surface


def characters():
    """Object name prefixes of every character in the file (BUNNY, KOALA, FROG ...)."""
    pre = set()
    for o in bpy.data.objects:
        n = o.name
        if n.endswith('_rig') and o.type == 'ARMATURE':
            pre.add(n[:-4])
        elif n.endswith('_head'):
            pre.add(n[:-5])
    return sorted(pre)


def body_objects(exclude=()):
    ex = set(o.name for o in exclude)
    out = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.name in ex or not o.visible_get():
            continue
        if o.get('dsl_body'):
            out.append(o)
            continue
        for pre in characters():
            if o.name.startswith(pre + '_') and o.name[len(pre) + 1:] in PARTS:
                out.append(o)
                break
    return out


def _mesh_world(ob):
    from .grips import _mesh_points
    return _mesh_points(ob)


class Bodies:
    def __init__(self, exclude=()):
        self.items = []
        for o in body_objects(exclude):
            pts, tris = _mesh_world(o)
            if not tris:
                continue
            mn = Vector([min(p[i] for p in pts) for i in range(3)]) - Vector((MARGIN,) * 3)
            mx = Vector([max(p[i] for p in pts) for i in range(3)]) + Vector((MARGIN,) * 3)
            self.items.append((o.name, BVHTree.FromPolygons(pts, tris), mn, mx))

    def count(self, pts):
        from .grips import _inside
        n = 0
        for _, bvh, mn, mx in self.items:
            for p in pts:
                if all(mn[i] <= p[i] <= mx[i] for i in range(3)) and _inside(bvh, p)[0]:
                    n += 1
        return n

    def inside(self, pts):
        """[(point, nearest surface point, outward normal, body name)] for points inside a body."""
        from .grips import _inside
        hits = []
        for name, bvh, mn, mx in self.items:
            for p in pts:
                if all(mn[i] <= p[i] <= mx[i] for i in range(3)) and _inside(bvh, p)[0]:
                    loc, nrm, _, _ = bvh.find_nearest(p)
                    if loc is not None:
                        n = (loc - p)
                        n = n.normalized() if n.length > 1e-6 else nrm
                        hits.append((p, loc, n, name))
        return hits


def _prop_points(ob, n=900):
    from .grips import _mesh_points, _sample
    pts, _ = _mesh_points(ob)
    return _sample(pts, n)


def holder_parts(pre, sides):
    """The holding hand(s), cuff and forearm sleeve: allowed to touch the prop."""
    names = ['%s_%s.%s' % (pre, part, s) for s in sides for part in ('hand', 'cuff', 'sleeve_fore')]
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects]


def _holder_hands(ob):
    side = ob.get('dsl_held_side')
    if not side:
        return ()
    sides = ('L', 'R') if side == 'both' else (side,)
    return holder_parts(ob.get('dsl_holder', 'BUNNY'), sides)


def resolve(ob, bodies=None, key=False, frame=None):
    """Move `ob` out of every character body at the current frame. Returns mm of overlap left."""
    excl = list(_holder_hands(ob))
    bodies = bodies or Bodies(exclude=excl)
    held = bool(ob.get('dsl_held_side'))
    hits = bodies.inside(_prop_points(ob))
    if not hits:
        return 0.0
    before = (ob.matrix_basis.copy(), len(hits))
    if ob.get('dsl_grip_kind') == 'wear':
        # worn: a glove can't move off the hand; only report other bodies
        return 0.0 if not hits else max((h[1] - h[0]).length for h in hits) * 1000
    if held and ob.get('dsl_grip_kind') != 'two':
        ok = _resolve_held(ob, bodies)
    else:
        ok = _resolve_free(ob, bodies)
    if not ok and bodies.count(_prop_points(ob)) >= before[1]:
        ob.matrix_basis = before[0]  # never leave it worse than it was
        bpy.context.view_layer.update()
    if key:
        f = bpy.context.scene.frame_current if frame is None else frame
        rp = {'QUATERNION': 'rotation_quaternion', 'AXIS_ANGLE': 'rotation_axis_angle'}.get(ob.rotation_mode, 'rotation_euler')
        ob.keyframe_insert('location', frame=f, group='DSL collision')
        ob.keyframe_insert(rp, frame=f, group='DSL collision')
    left = bodies.inside(_prop_points(ob))
    return 0.0 if not left else max((h[1] - h[0]).length for h in left) * 1000


def _depth(hits):
    return max(((h[1] - h[0]).length for h in hits), default=0.0)


def _resolve_free(ob, bodies):
    """Push out along the normal of the deepest point; repeat a few times (corners, two bodies)."""
    for _ in range(8):
        hits = bodies.inside(_prop_points(ob))
        if not hits:
            return True
        p, loc, n, _ = max(hits, key=lambda h: (h[1] - h[0]).length)
        push = (loc - p) + n * MARGIN
        mw = ob.matrix_world.copy()
        mw.translation += push
        _set_world(ob, mw)
    return not bodies.inside(_prop_points(ob))


def _resolve_held(ob, bodies):
    """Turn the prop about its grip (the socket origin), smallest turn first, within the limits
    stored on its 'DSL hold twist' constraint; then slide along the handle."""
    base = ob.matrix_basis.copy()
    lim = ob.constraints.get('DSL hold twist')
    lims = [math.degrees(getattr(lim, 'max_' + a)) if lim else 30.0 for a in 'xyz']
    cands = []
    for ax, top in enumerate(lims):
        steps = [s for s in (8, 15, 22, 30, 45, 60, 90, 135, 180) if s <= top + 1e-3]
        for s in steps:
            for sg in (1, -1):
                cands.append((s, ax, sg))
    cands.sort(key=lambda c: c[0])
    best = (_depth(bodies.inside(_prop_points(ob))), base)
    for s, ax, sg in cands:
        axis = Vector([1.0 if i == ax else 0.0 for i in range(3)])
        R = Quaternion(axis, math.radians(s * sg)).to_matrix().to_4x4()
        ob.matrix_basis = base @ R
        bpy.context.view_layer.update()
        d = _depth(bodies.inside(_prop_points(ob)))
        if d == 0.0:
            return True
        if d < best[0]:
            best = (d, ob.matrix_basis.copy())
    # slide along the handle (its limit is on 'DSL hold reach')
    lo = ob.constraints.get('DSL hold reach')
    if lo:
        for a in 'xyz':
            mn, mx = getattr(lo, 'min_' + a), getattr(lo, 'max_' + a)
            if mx - mn < 0.02:
                continue
            for t in (0.25, 0.5, 0.75, 1.0):
                for v in (mn * t, mx * t):
                    M = best[1].copy()
                    M.translation['xyz'.index(a)] = v
                    ob.matrix_basis = M
                    bpy.context.view_layer.update()
                    d = _depth(bodies.inside(_prop_points(ob)))
                    if d == 0.0:
                        return True
                    if d < best[0]:
                        best = (d, ob.matrix_basis.copy())
    ob.matrix_basis = best[1]
    bpy.context.view_layer.update()
    return False


def _set_world(ob, mw):
    ob.matrix_world = mw
    bpy.context.view_layer.update()


def library_objects():
    """Props, scenery pieces and text the library put in the scene (not set pieces)."""
    return [o for o in bpy.context.scene.objects
            if o.type == 'MESH' and (o.get('dsl_id') or o.get('dsl_text')) and not o.get('dsl_set')
            and not o.get('dsl_body')]


def bake(frames=None, objs=None, report=None):
    """Key collision fixes on every frame. Returns {object: [frames still overlapping]}."""
    sc = bpy.context.scene
    frames = frames or range(sc.frame_start, sc.frame_end + 1)
    objs = objs or library_objects()
    cur = sc.frame_current
    left = {}
    for f in frames:
        sc.frame_set(f)
        for ob in objs:
            mm = resolve(ob, key=True, frame=f)
            if mm > 0.5:
                left.setdefault(ob.name, []).append(f)
    sc.frame_set(cur)
    return left


_guard_busy = [False]


def _guard(scene, depsgraph=None):
    if _guard_busy[0] or not scene.get('dsl_collision_guard'):
        return
    if bpy.context.screen and bpy.context.screen.is_animation_playing:
        return  # live playback stays smooth: bake for final shots
    _guard_busy[0] = True
    try:
        for ob in library_objects():
            resolve(ob)
    except Exception as e:
        print('Doodle Library collision guard:', e)
    finally:
        _guard_busy[0] = False


def set_guard(on):
    bpy.context.scene['dsl_collision_guard'] = bool(on)
    return on


class DSL_OT_bake_collision(bpy.types.Operator):
    """Key collision fixes over the scene range so no prop or text ever sits inside a character"""
    bl_idname = 'dsl.bake_collision'
    bl_label = 'Bake collisions'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        left = bake()
        if left:
            name, fr = next(iter(left.items()))
            self.report({'WARNING'}, '%d objects still touch a body on some frames (e.g. %s at frame %d)' %
                        (len(left), name, fr[0]))
        else:
            self.report({'INFO'}, 'No prop is inside a character on any frame')
        return {'FINISHED'}


class DSL_OT_collision_guard(bpy.types.Operator):
    """Fix collisions live on every frame change while you scrub (playback stays fast)"""
    bl_idname = 'dsl.collision_guard'
    bl_label = 'Live collision guard'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        on = set_guard(not context.scene.get('dsl_collision_guard', False))
        self.report({'INFO'}, 'Collision guard on' if on else 'Collision guard off')
        return {'FINISHED'}


classes = (DSL_OT_bake_collision, DSL_OT_collision_guard)


def register():
    if _guard not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(_guard)


def unregister():
    if _guard in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(_guard)
