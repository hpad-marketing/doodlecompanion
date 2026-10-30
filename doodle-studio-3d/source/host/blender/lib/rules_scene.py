"""Scene-level rule checks on the real 3D geometry (ANIMATION-RULES.md, 3D edition), on top
of rules3d's body checks:

- scenery touching the character (blocking) or within 2 cm of him (warning)
- a held prop passing through the body (it may touch the hands only)
- prop slivers: a set piece cropped by the frame edge to under 35% of itself
- tangents: a piece whose edge just kisses the frame edge
- see-through: a visible piece with no fill or a see-through material
- the horizon height on screen (compared across shots when the scene is joined)

The character (lead and co-stars), its outfit and accessories, held props, the room shell
(floor and walls), effects pinned to the camera and scatter tufts are not scenery here.
"""
import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import collision

SLIVER = 0.35       # a piece showing less than this share of itself is a sliver
KISS = 0.006        # an edge this close to the frame edge (share of the frame) is a tangent
NEAR = 0.02         # metres: closer than this to the character is a warning
HAND_PARTS = ('hand', 'cuff', 'sleeve_fore', 'finger')


def _rigs(arm, cast):
    return [arm] + [c['rig'] for c in cast or []]


def _belongs(ob, rigs):
    """True for the character's own pieces: parented to a rig, or deformed by one."""
    p = ob
    while p is not None:
        if p in rigs:
            return True
        p = p.parent
    return any(m.type == 'ARMATURE' and m.object in rigs for m in ob.modifiers)


def held(ob, rigs):
    """Held in a hand (the library marks grips with dsl_held_side; worn things are 'wear'),
    or pinned to a rig bone with a Child Of constraint."""
    p = ob
    while p is not None:
        if p.get('dsl_held_side') and p.get('dsl_grip_kind') != 'wear':
            return True
        if any(c.type == 'CHILD_OF' and c.target in rigs and c.influence > 0 for c in p.constraints):
            return True
        p = p.parent
    return False


def _on_camera(ob, cam):
    p = ob
    while p is not None:
        if p == cam:
            return True
        p = p.parent
    return any(c.type == 'CHILD_OF' and c.target == cam for c in ob.constraints)


def classify(arm, cast, char_objs):
    """(scenery, held props) visible in the render."""
    sc = bpy.context.scene
    rigs = _rigs(arm, cast)
    mine = set(char_objs)
    for c in cast or []:
        mine |= set(c['objs'].values())
    scenery, hold = [], []
    for ob in sc.objects:
        if ob.type != 'MESH' or ob.hide_render or ob in mine:
            continue
        if held(ob, rigs):
            hold.append(ob)
        elif _belongs(ob, rigs) or ob.get('dsl_shell') or _on_camera(ob, sc.camera) or ob.name.startswith(('DS_scatter', 'DS_doodle')):
            continue
        else:
            scenery.append(ob)
    return scenery, hold


def _world_bvh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(ob.matrix_world)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    ev.to_mesh_clear()
    return t


def _aabb(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def _gap(a, b):
    return max(0.0, max(a[0][i] - b[1][i] for i in range(3)), max(b[0][i] - a[1][i] for i in range(3)))


def _char_points(char_objs, every=8):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for ob in char_objs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        out += [mw @ v.co for v in me.vertices[::every]]
        ev.to_mesh_clear()
    return out


def contact(scenery, held_props, char_objs, cast):
    """Scenery touching or near the character, held props inside the body."""
    out = {'scenery_touch': [], 'scenery_near': [], 'held_in_body': []}
    bodies = [list(char_objs)] + [list(c['objs'].values()) for c in cast or []]
    boxes = [_aabb(o) for b in bodies for o in b]
    if not boxes:
        return out
    cbox = (Vector([min(b[0][i] for b in boxes) for i in range(3)]), Vector([max(b[1][i] for b in boxes) for i in range(3)]))
    pts = None
    cages = {}
    cage = lambda o: cages.setdefault(o.name, collision._cage_bvh(o))
    for ob in scenery:
        if _gap(_aabb(ob), cbox) > NEAR:
            continue
        t = _world_bvh(ob)
        hit = next((o for b in bodies for o in b if _gap(_aabb(ob), _aabb(o)) <= 0.001 and t.overlap(cage(o))), None)
        if hit is not None:
            out['scenery_touch'].append(f'{ob.name} touches {hit.name}')
            continue
        if pts is None:
            pts = [p for b in bodies for p in _char_points(b)]
        hits = [t.find_nearest(p) for p in pts]
        d = min((h[3] for h in hits if h[0] is not None), default=None)
        if d is not None and d < NEAR:
            out['scenery_near'].append(f'{ob.name} {d * 100:.1f} cm from the character')
    for ob in held_props:
        t = _world_bvh(ob)
        for b in bodies:
            for o in b:
                if any(h in o.name for h in HAND_PARTS):
                    continue
                if _gap(_aabb(ob), _aabb(o)) <= 0.001 and t.overlap(cage(o)):
                    out['held_in_body'].append(f'{ob.name} inside {o.name}')
    return out


def framing(scenery, cam):
    """Slivers and frame-edge tangents, from each piece's box as the camera sees it."""
    sc = bpy.context.scene
    slivers, kisses = [], []
    for ob in scenery:
        pts = [world_to_camera_view(sc, cam, ob.matrix_world @ Vector(c)) for c in ob.bound_box]
        pts = [p for p in pts if p.z > 0]
        if len(pts) < 2:
            continue
        x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
        y0, y1 = min(p.y for p in pts), max(p.y for p in pts)
        area = max(1e-9, (x1 - x0) * (y1 - y0))
        vx, vy = max(0.0, min(1.0, x1) - max(0.0, x0)), max(0.0, min(1.0, y1) - max(0.0, y0))
        if vx * vy <= 0:
            continue
        share = vx * vy / area
        # a piece bigger than the frame (a tree trunk filling the edge) is not a sliver
        if share < SLIVER and (x1 - x0) < 1.2 and (y1 - y0) < 1.2:
            slivers.append(f'{ob.name} shows {share * 100:.0f}%')
        for e, name in ((x0, 'left'), (1 - x1, 'right'), (y0, 'bottom'), (1 - y1, 'top')):
            if 0 <= e < KISS:
                kisses.append(f'{ob.name} kisses the {name} edge')
    return {'slivers': slivers, 'tangents': kisses}


def see_through(scenery):
    bad = []
    for ob in scenery:
        mats = [s.material for s in ob.material_slots if s.material]
        if not mats:
            bad.append(f'{ob.name} has no fill')
            continue
        for m in mats:
            alpha = 1.0
            if m.use_nodes:
                for n in m.node_tree.nodes:
                    if n.type == 'BSDF_PRINCIPLED' and not n.inputs['Alpha'].is_linked:
                        alpha = min(alpha, n.inputs['Alpha'].default_value)
            if alpha < 0.99:
                bad.append(f'{ob.name} ({m.name}) is see-through')
                break
    return bad


def horizon(cam):
    """Screen height of the horizon (0 top, 1 bottom), or None when the camera looks straight
    down or up, or is a 360 camera."""
    if cam is None or cam.data.type == 'PANO':
        return None
    d = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
    d.z = 0
    if d.length < 0.05:
        return None
    p = world_to_camera_view(bpy.context.scene, cam, cam.matrix_world.translation + d.normalized() * 1e4)
    return round(1 - p.y, 4)


def frame_bad(r):
    """A frame breaks a blocking rule (near-misses are warnings only)."""
    return bool(r.get('arm_head_clip') or r.get('below_floor') or r.get('ears_touch') or r.get('bodies_touch')
                or r.get('scenery_touch') or r.get('held_in_body') or r.get('slivers') or r.get('tangents'))
