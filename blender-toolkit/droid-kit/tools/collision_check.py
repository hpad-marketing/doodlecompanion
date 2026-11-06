"""Full collision test: every droid part against every other part AND against everything in the scene,
plus scene parts against each other, in every pose preset and every library motion. Nothing may pass through anything.
DROID=<id> python3 collision_check.py in.blend [report.json] [frame_step]
   or (render queue / nightly): blender -b in.blend --python collision_check.py -- [report.json] [frame_step]
Designed contacts that are NOT failures:
  - parts on the same bone; joint pairs listed in the rig's rest_contacts
  - a bolt / decal / detail against the one part it sits on (its parent)
  - a hose against the parts on the bones its ends are hooked to
  - scene pieces of one assembly (same name stem, e.g. Prop_pallet_block0 + Prop_pallet_slat2)
  - extra pairs in settings collision.allow: [["regex_a", "regex_b"], ...]
Effects never count: volumes, dust/haze, rig widgets (settings collision.ignore adds name prefixes).
Prints one CHECK_SUMMARY line, writes a JSON report, exits 1 if anything intersects."""
import bpy, sys, os, json, re, math, collections
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'kit'))
import kit
if '--' in sys.argv: a = sys.argv[sys.argv.index('--') + 1:]
else:
    a = sys.argv[1:]; bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.pop(0)))
rep_path = a[0] if a else ''; step = int(a[1]) if len(a) > 1 else 2
C = kit.get('collision', {}) or {}
IGN = tuple(C.get('ignore', [])) + ('dust', 'Dust', 'Haze', 'WGT_', 'Lookdev_Light')
ALLOW = [(re.compile(x), re.compile(y)) for x, y in C.get('allow', [])]
sc = bpy.context.scene; rig = bpy.data.objects[kit.rig_name()]
def in_droid(o):
    while o:
        if o == rig or 'rig_bone' in o: return True
        o = o.parent
    return False
def bone_of(o):
    while o:
        if 'rig_bone' in o: return o['rig_bone']
        o = o.parent
    return None
objs = [o for o in bpy.data.objects if o.type in ('MESH', 'CURVE') and not o.hide_render and not o.name.startswith(IGN)
        and o.visible_get() is not None]
droid = [o for o in objs if in_droid(o) or any(m.type == 'HOOK' and m.object == rig for m in o.modifiers)]
scene = [o for o in objs if o not in droid and o.type == 'MESH']
skip = {frozenset(p) for p in json.loads(rig.get('rest_contacts', '[]'))}
def stem(n): return re.sub(r'(_?[A-Za-z]*\d+|_[A-Z])$', '', n)
def hook_bones(o): return {m.subtarget.replace('DEF-', '') for m in o.modifiers if m.type == 'HOOK' and m.object == rig}
def allowed(x, y):
    if frozenset((x.name, y.name)) in skip: return True
    bx, by = bone_of(x), bone_of(y)
    if bx and by and bx == by: return True
    if x.parent == y or y.parent == x: return True
    for h, other in ((x, y), (y, x)):   # hose ends sit inside the parts they are hooked to
        ob_ = bone_of(other)
        if ob_ and ob_.replace('DEF-', '') in hook_bones(h): return True
    if x in scene and y in scene and stem(x.name) == stem(y.name): return True
    return any((ra.search(x.name) and rb.search(y.name)) or (ra.search(y.name) and rb.search(x.name)) for ra, rb in ALLOW)
pairs = []
for i, x in enumerate(droid):
    for y in droid[i + 1:] + scene:
        if not allowed(x, y): pairs.append((x, y))
for i, x in enumerate(scene):
    for y in scene[i + 1:]:
        if not allowed(x, y): pairs.append((x, y))
print('OBJECTS droid', len(droid), 'scene', len(scene), 'PAIRS', len(pairs), flush=True)
TOL = C.get('touch_mm', 0.5) / 1000   # resting contact (a foot on the floor, a crate on the ground) is not an intersection
def depth(vs, t):
    """How far any vertex of one mesh sits inside the other (0 if none)."""
    m = 0.0
    for v in vs:
        loc, nrm, _, dist = t.find_nearest(v)
        if loc is not None and dist < 0.2 and (v - loc).dot(nrm) < 0: m = max(m, dist)
    return m
def snapshot():
    dg = bpy.context.evaluated_depsgraph_get(); cache = {}
    def get(o):
        if o.name not in cache:
            e = o.evaluated_get(dg); me = e.to_mesh(); M = e.matrix_world
            vs = [M @ v.co for v in me.vertices]; fs = [tuple(p.vertices) for p in me.polygons]; e.to_mesh_clear()
            lo = Vector([min(v[k] for v in vs) for k in range(3)]) if vs else Vector((1e9,) * 3)
            hi = Vector([max(v[k] for v in vs) for k in range(3)]) if vs else Vector((-1e9,) * 3)
            cache[o.name] = [vs, fs, lo, hi, None]
        return cache[o.name]
    def tree(o):
        c = get(o)
        if c[4] is None: c[4] = BVHTree.FromPolygons(c[0], c[1])
        return c[4]
    hits = []
    for x, y in pairs:
        cx, cy = get(x), get(y)
        if any(cx[2][k] > cy[3][k] or cx[3][k] < cy[2][k] for k in range(3)): continue
        if tree(x).overlap(tree(y)):
            d = max(depth(cx[0], tree(y)), depth(cy[0], tree(x)))
            if d > TOL: hits.append((x.name, y.name, round(d * 1000, 1)))
    return hits
found = collections.OrderedDict(); checked = 0
def record(where, hits):
    for x, y, mm in hits: found.setdefault((x, y), []).append((where, mm))
ad = rig.animation_data or rig.animation_data_create(); keep = ad.action
ad.action = None
P = json.loads(rig.get('pose_presets', '{}'))
for name, pose in P.items():
    for p in rig.pose.bones:
        if not p.name.startswith(('SPR-', 'DEF-', 'MCH-', 'GIM')): p.location = (0, 0, 0); p.rotation_euler = (0, 0, 0)
    for b, (rot, loc) in pose.items():
        if b in rig.pose.bones: rig.pose.bones[b].rotation_euler = [math.radians(v) for v in rot]; rig.pose.bones[b].location = loc
    bpy.context.view_layer.update(); record('pose ' + name, snapshot()); checked += 1
acts = [x for x in bpy.data.actions if x.name.startswith(C.get('action_prefix', 'RM_'))]
for act in acts:
    ad.action = act
    if act.slots: ad.action_slot = act.slots[0]
    f0, f1 = map(int, act.frame_range)
    for f in sorted(set(list(range(f0, f1 + 1, step)) + [f1])):
        sc.frame_set(f); record(f'{act.name} f{f}', snapshot()); checked += 1
    print('ACTION', act.name, 'hits so far', len(found), flush=True)
ad.action = keep
rep = {'droid': kit.get('name', ''), 'checked_frames': checked, 'pairs': len(pairs), 'actions': len(acts), 'step': step,
       'touch_mm': TOL * 1000,
       'intersections': [{'a': x, 'b': y, 'count': len(w), 'first': w[0][0], 'max_mm': max(m for _, m in w)} for (x, y), w in found.items()]}
for r in rep['intersections']: print('HIT', r)
if rep_path: json.dump(rep, open(rep_path, 'w'), indent=1)
print(f"CHECK_SUMMARY: {rep['droid']} {checked} poses/frames, {len(pairs)} part pairs, {len(found)} intersecting pairs")
sys.exit(1 if found else 0)
