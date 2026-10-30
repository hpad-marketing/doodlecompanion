"""Build sets/sets.blend (one collection per room) and scenery/scenery.blend (one object per model).

  python build_sets.py OUT_LIBRARY_DIR
"""
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import models  # noqa: E402
import rooms as R  # noqa: E402
import models2  # noqa: E402,F401  (registers the second batch of models)
import models3  # noqa: E402  (asset-pack pieces: a few dress the new sets too)
import models4  # noqa: E402,F401  (worlds packs: spooky, adventure, show, everyday)
from rooms2 import ROOMS2  # noqa: E402
from rooms3 import ROOMS3  # noqa: E402

ALL_ROOMS = dict(R.ROOMS)
ALL_ROOMS.update(ROOMS2)
ALL_ROOMS.update(ROOMS3)
# pack pieces used in a set get a mesh here, but stay out of the scenery list (they live in packs.blend)
SET_ONLY = {e[2]: models3.M3[e[2]] for rm in ALL_ROOMS.values() for e in rm['props']
            if e[2] not in models.M and e[2] in models3.M3}
INDOOR = ('indoor', 'attic', 'cabin', 'box', 'cave', 'corner')
# far things are drawn at their real look; scale them with distance so they read at their drawn size
FAR = ('cloud', 'birds', 'sun', 'starfield', 'ringed_planet', 'comet', 'kites')

out = (sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])[0]
bpy.ops.wm.read_factory_settings(use_empty=True)
mats = common.placeholder_materials()
CAM_Y = -3.98  # default camera distance (see doodle_library.sets)


# ------------------------------------------------------------------ meshes, one per model
meshes = {}
for name, fn in list(models.M.items()) + list(SET_ONLY.items()):
    piece = fn()
    piece = piece[0] if isinstance(piece, tuple) else piece  # moving parts stay with the pack version
    ob = piece.build(mats)
    me = ob.data
    me.name = 'DSL_' + name
    common.finish_mesh(me, merge=0.00005)
    bpy.data.objects.remove(ob)
    meshes[name] = me


def surface_height(me):
    """Height of the biggest upward-facing face: where things stand on this piece."""
    best, z = 0, max(v.co.z for v in me.vertices)
    areas = {}
    for p in me.polygons:
        if p.normal.z > 0.95:
            key = round(p.center.z, 2)
            areas[key] = areas.get(key, 0) + p.area
    if areas:
        z = max(areas.items(), key=lambda kv: kv[1])[0]
    return z


# ------------------------------------------------------------------ shells
def shell(kind, room_id):
    bm = bmesh.new()
    grp = bm.faces.layers.int.new('dsl_group')
    V = lambda x, y, z: bm.verts.new((x, y, z))

    def quad(a, b, c, d, g):
        f = bm.faces.new((a, b, c, d))
        f[grp] = g
        return f
    hw = R.ROOM_W / 2

    def room(hw, h, back=R.WALL_Y):
        f0, f1, f2, f3 = V(-hw, R.ROOM_FRONT, 0), V(hw, R.ROOM_FRONT, 0), V(hw, back, 0), V(-hw, back, 0)
        t1, t2, t3, t0 = V(hw, R.ROOM_FRONT, h), V(hw, back, h), V(-hw, back, h), V(-hw, R.ROOM_FRONT, h)
        quad(f0, f1, f2, f3, 0)              # floor
        quad(f3, f2, t2, t3, 1)              # back wall
        quad(f1, t1, t2, f2, 2)              # right wall
        quad(f0, f3, t3, t0, 3)              # left wall
        return t0, t1, t2, t3

    def strip(rows, x0=-150, x1=150, g0=0):
        """Ground made of rows (y, z) running across the whole view."""
        prev = None
        for i, (y, z) in enumerate(rows):
            l, r = V(x0, y, z), V(x1, y, z)
            if prev:
                quad(prev[0], prev[1], r, l, g0 + i)
            prev = (l, r)
    if kind == 'indoor':
        room(hw, R.WALL_H)
    elif kind == 'box':        # cardboard box: walls a bit taller, flaps are a prop
        room(hw, 2.6)
    elif kind == 'cabin':      # train / plane: narrow, low
        room(1.3, 2.2)
    elif kind == 'attic':      # low side walls, roof slopes up to a ridge, gable at the back
        t0, t1, t2, t3 = room(hw, 1.1)
        r0, r1 = V(0, R.ROOM_FRONT, 2.9), V(0, R.WALL_Y, 2.9)
        quad(t3, r1, r0, t0, 4)
        quad(r1, t2, t1, r0, 5)
        f = bm.faces.new((t3, t2, r1))     # gable
        f[grp] = 6
    elif kind == 'corner':     # floor, back wall and one side wall: a clean half-room
        f0, f1, f2, f3 = V(-hw, R.ROOM_FRONT, 0), V(hw, R.ROOM_FRONT, 0), V(hw, R.WALL_Y, 0), V(-hw, R.WALL_Y, 0)
        t2, t3, t0 = V(hw, R.WALL_Y, R.WALL_H), V(-hw, R.WALL_Y, R.WALL_H), V(-hw, R.ROOM_FRONT, R.WALL_H)
        quad(f0, f1, f2, f3, 0)
        quad(f3, f2, t2, t3, 1)
        quad(f0, f3, t3, t0, 3)
    elif kind == 'cave':       # just the floor: the rock walls are a prop
        quad(V(-6, -6, 0), V(6, -6, 0), V(6, 6, 0), V(-6, 6, 0), 0)
    elif kind == 'none':       # nothing to stand on: clouds, space
        pass
    elif kind == 'open':       # flat ground to the horizon, no edges anywhere
        quad(V(-150, -6, 0), V(150, -6, 0), V(150, 300, 0), V(-150, 300, 0), 0)
    elif kind == 'hills':      # flat where Bunny stands, rolling swells further back
        xs = [-150 + i * 10 for i in range(31)]
        ys = [-6, 0, 2, 4] + [4 + 3 * 1.32 ** i for i in range(16)]
        rows = []
        for y in ys:
            k = max(0.0, min(1.0, (y - 4) / 20))
            rows.append([V(x, y, k * k * (1.6 * math.sin(x * 0.11 + y * 0.05) + 1.1 * math.sin(y * 0.09))) for x in xs])
        for j in range(len(rows) - 1):
            for i in range(len(xs) - 1):
                quad(rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i], 0)
    elif kind == 'cliff':      # plateau, sheer drop, valley far below
        strip([(-6, 0), (1.5, 0), (1.62, -30), (300, -30)], x0=-60, x1=60)
    elif kind == 'lake':       # bank, low edge, still water
        strip([(-6, 0), (0.6, 0), (0.7, -0.3), (300, -0.3)])
    elif kind == 'sea':        # water everywhere, the boat is the floor
        quad(V(-150, -6, -0.3), V(150, -6, -0.3), V(150, 300, -0.3), V(-150, 300, -0.3), 0)
    elif kind == 'ghat':       # ground, then the steps (a prop) go down to the river
        strip([(-6, 0), (1.22, 0), (1.22, -1.0), (300, -1.0)])
    elif kind == 'balcony':    # balcony slab, street far below
        strip([(-6, 0), (1.25, 0), (1.25, -0.25)], x0=-2.6, x1=2.6)
        quad(V(-150, -6, -12), V(150, -6, -12), V(150, 300, -12), V(-150, 300, -12), 9)
    elif kind == 'platform':
        a, b = V(-12, -6, 0), V(12, -6, 0)
        c, d = V(12, 2.45, 0), V(-12, 2.45, 0)
        e, f = V(12, 2.45, -0.6), V(-12, 2.45, -0.6)
        g, h = V(12, 40, -0.6), V(-12, 40, -0.6)
        quad(a, b, c, d, 0)
        quad(d, c, e, f, 1)
        quad(f, e, g, h, 2)
    elif kind == 'street':
        pts = [(-6, 0), (1.9, 0), (1.9, -0.12), (3.5, -0.12), (3.5, 0), (40, 0)]
        prev = None
        for i, (y, z) in enumerate(pts):
            l, r = V(-20, y, z), V(20, y, z)
            if prev:
                quad(prev[0], prev[1], r, l, i)
            prev = (l, r)
    elif kind == 'beach':
        a, b, c, d = V(-20, -6, 0), V(20, -6, 0), V(20, 4.0, 0), V(-20, 4.0, 0)
        e, f = V(20, 4.0, -0.02), V(-20, 4.0, -0.02)
        g, h = V(20, 40, -0.02), V(-20, 40, -0.02)
        quad(a, b, c, d, 0)
        quad(d, c, e, f, 1)
        quad(f, e, g, h, 2)
    else:  # outdoor ground to the horizon
        quad(V(-20, -6, 0), V(20, -6, 0), V(20, 40, 0), V(-20, 40, 0), 0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # face normals point into the room / up
    for fc in bm.faces:
        c = fc.calc_center_median()
        if fc[grp] in (4, 5) and kind == 'attic':
            inward = Vector((0, 0, -1))   # roof faces down into the room
        else:
            inward = Vector((0, 0, 1)) if abs(fc.normal.z) > 0.5 else Vector((-c.x, -c.y + 0.2, 0)).normalized()
        if fc.normal.dot(inward) < 0:
            fc.normal_flip()
    me = bpy.data.meshes.new('DSL_shell_' + room_id)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mats['DSL_mustard'])
    common.finish_mesh(me, merge=0)
    return me


# ------------------------------------------------------------------ street extras: lane dashes
def lane_dashes():
    p = models.Piece('lane_dashes')
    for i in range(-8, 9):
        p.box(0.6, 0.12, 0.004, i * 1.2, 2.7, -0.12)
    ob = p.build(mats)
    common.finish_mesh(ob.data, merge=0)
    return ob


set_objs, rows = [], []
scene_root = bpy.context.scene.collection
for room_id, room in ALL_ROOMS.items():
    coll = bpy.data.collections.new('SET_' + room_id)
    scene_root.children.link(coll)
    sh = bpy.data.objects.new('%s:shell' % room_id, shell(room['kind'], room_id))
    sh['dsl_set'], sh['dsl_prop'], sh['dsl_label'], sh['dsl_shell'] = room_id, 'shell', 'Room', 1
    coll.objects.link(sh)
    if room['kind'] == 'street':
        ld = lane_dashes()
        ld.name = '%s:lanes' % room_id
        ld['dsl_set'], ld['dsl_prop'], ld['dsl_label'], ld['dsl_default'] = room_id, 'lanes', 'Road markings', 1
        coll.objects.link(ld)
    placed = {}
    plist = [{'id': 'lanes', 'label': 'Road markings', 'on': True}] if room['kind'] == 'street' else []
    for e in room['props']:
        slug, label, model, x, y, rz = e[:6]
        z = e[6] if len(e) > 6 else 0.0
        on = e[7] if len(e) > 7 else True
        on_top = e[8] if len(e) > 8 else None
        me = meshes[model]
        ob = bpy.data.objects.new('%s:%s' % (room_id, slug), me)
        s = R.WORLD
        if model in FAR or model.startswith('far_'):  # far away: scale with distance so they read at their drawn size
            s *= (y - CAM_Y) / (-CAM_Y)
        ob.scale = (s, s, s)
        if on_top and on_top in placed:
            base = placed[on_top]
            z = base.location.z + surface_height(base.data) * base.scale.z
        ob.location = (x, y, z)
        ob.rotation_euler = (0, 0, math.radians(rz))
        if room.get('ink'):  # the ink backdrop: same sweep, ink material
            ob.data = me.copy()
            ob.data.materials[0] = mats['DS_ink']
        ob['dsl_set'], ob['dsl_prop'], ob['dsl_label'], ob['dsl_model'] = room_id, slug, label, model
        ob['dsl_default'] = 1 if on else 0
        if on_top:
            ob['dsl_on'] = on_top
        ob.hide_viewport = ob.hide_render = not on
        coll.objects.link(ob)
        placed[slug] = ob
        plist.append({'id': slug, 'label': label, 'on': bool(on), 'model': model})
    set_objs.append(coll)
    rows.append({'id': 'set-' + room_id, 'name': room['name'], 'category': 'set', 'kind': 'room',
                 'sub': 'Indoor' if room['kind'] in INDOOR else 'Outdoor', 'file': 'sets/sets.blend',
                 'datablock': 'SET_' + room_id, 'tags': [room['kind']], 'source': 'doodle-library',
                 'data': {'room': room_id, 'kind': room['kind'], 'props': plist}})

os.makedirs(os.path.join(out, 'sets'), exist_ok=True)
bpy.data.libraries.write(os.path.join(out, 'sets', 'sets.blend'), set(set_objs), fake_user=True, compress=True)

# scenery: every model on its own, marked as an asset
scen, srows = [], []
for name, me in meshes.items():
    if name in SET_ONLY:
        continue
    ob = bpy.data.objects.new('scenery-' + name, me)
    ob.scale = (R.WORLD,) * 3
    ob['dsl_id'] = 'scenery-' + name
    ob['dsl_kind'] = 'scenery'
    ob.asset_mark()
    ob.asset_data.tags.new('Doodle scenery')
    scen.append(ob)
    label = name.replace('_', ' ').capitalize()
    srows.append({'id': 'scenery-' + name, 'name': label, 'category': 'scenery', 'kind': 'object',
                  'sub': next((rm['name'] for rm in ALL_ROOMS.values() if any(e[2] == name for e in rm['props'])), 'Extra'),
                  'file': 'scenery/scenery.blend', 'datablock': 'scenery-' + name, 'tags': [], 'source': 'doodle-library'})
common.save_blend(os.path.join(out, 'scenery', 'scenery.blend'), scen)
common.write_part(out, 'sets_rooms', rows)
common.write_part(out, 'scenery', srows)
print('sets', len(rows), 'scenery', len(srows))
