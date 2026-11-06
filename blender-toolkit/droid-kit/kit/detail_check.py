"""Check details/decals never touch any part except the one they sit on, in every library motion (every 2nd frame)."""
import bpy, sys, collections
from mathutils import Vector
from mathutils.bvhtree import BVHTree
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
sc = bpy.context.scene; rig = bpy.data.objects['RobotRig']; ad = rig.animation_data
det = [o for o in bpy.data.objects if o.type == 'MESH' and ('rb_detail' in o or 'rb_decal' in o)]
parts = [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o and o.parent == rig]
print('DETAILS', len(det), 'PARTS', len(parts))
hits = collections.Counter(); ex = {}
acts = [a for a in bpy.data.actions if a.name.startswith('RM_')]
for a in acts:
    ad.action = a; ad.action_slot = a.slots[0]
    f0, f1 = map(int, a.frame_range)
    for f in range(f0, f1 + 1, 2):
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
        def world(o):
            e = o.evaluated_get(dg); M = e.matrix_world; me = e.data
            vs = [M @ v.co for v in me.vertices]; return vs, [tuple(p.vertices) for p in me.polygons]
        cache = {}
        def box(o):
            if o.name not in cache:
                vs, fs = world(o); lo = Vector([min(v[i] for v in vs) for i in range(3)]); hi = Vector([max(v[i] for v in vs) for i in range(3)])
                cache[o.name] = (vs, fs, lo, hi, None)
            return cache[o.name]
        def bvh(o):
            vs, fs, lo, hi, t = box(o)
            if t is None: t = BVHTree.FromPolygons(vs, fs); cache[o.name] = (vs, fs, lo, hi, t)
            return t
        for d in det:
            vs, fs, lo, hi, _ = box(d)
            for p in parts:
                if p == d.parent: continue
                _, _, plo, phi, _ = box(p)
                if any(lo[i] > phi[i] or hi[i] < plo[i] for i in range(3)): continue
                if bvh(d).overlap(bvh(p)):
                    k = (d.name, p.name); hits[k] += 1; ex.setdefault(k, (a.name, f))
for k, n in hits.most_common(): print('HIT', k, n, ex[k])
print('ACTIONS', len(acts), 'TOTAL HITS', sum(hits.values()))
