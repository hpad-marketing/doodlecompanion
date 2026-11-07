"""Clash checker for the tracked droid: every part (tread links too) vs every part on another bone, plus the floor (z=0).
Designed contacts at rest (pin in knuckle, rod in housing) are stored in rig['rest_contacts']. Stroke checks for struts and the ram."""
import bpy, json
import numpy as np
from mathutils.bvhtree import BVHTree
FLOOR_TOL = 0.0005
class Checker:
    def __init__(self, arm):
        self.arm = arm
        self.parts = [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o and not o.hide_render]
        self.co = {}; self.polys = {}
        for o in self.parts:
            me = o.data
            a = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', a)
            self.co[o.name] = np.c_[a.reshape(-1, 3), np.ones(len(me.vertices))]
            self.polys[o.name] = [tuple(p.vertices) for p in me.polygons]
        self.skip = {tuple(p) for p in json.loads(arm.get('rest_contacts', '[]'))}
        self.static = {}
    def world(self, o):
        return (self.co[o.name] @ np.array(o.matrix_world).T)[:, :3]
    def strokes(self):
        p = self.arm.pose.bones; out = []
        for pb in p:
            if pb.name.startswith('MCH-strut_lo.'):
                k = pb.name.split('.')[-1]
                d = (p[f'MCH-strut_hi.{k}'].head - pb.head).length
                if not (0.085 <= d <= 0.135): out.append(('strut stroke ' + k, round(d, 4)))
        d = (p['MCH-ramA'].head - p['MCH-ramB'].head).length
        lo, hi = self.arm['ram_stroke']
        if not (lo <= d <= hi): out.append(('ram stroke', round(d, 4)))
        return out
    def hits(self, only=None, limit=None, floor=True):
        """only: set of bone names; then only pairs with exactly one side in it (plus pairs inside it) are tested"""
        data = []
        for o in self.parts:
            w = self.world(o)
            data.append((o.name, o['rig_bone'], w, w.min(0), w.max(0)))
        out = []
        if floor:
            for nm, bn, w, mn, mx in data:
                if (only is None or bn in only) and mn[2] < -FLOOR_TOL: out.append((nm, 'FLOOR', round(float(mn[2]), 4)))
        mins = np.array([d[3] for d in data]); maxs = np.array([d[4] for d in data])
        trees = {}; n = len(data)
        for i in range(n):
            ov = np.all((maxs[i + 1:] >= mins[i] - 1e-6) & (mins[i + 1:] <= maxs[i] + 1e-6), axis=1)
            for j in np.nonzero(ov)[0] + i + 1:
                a, b = data[i], data[j]
                if a[1] == b[1]: continue
                if only is not None and a[1] not in only and b[1] not in only: continue
                k = (a[0], b[0]) if a[0] < b[0] else (b[0], a[0])
                if k in self.skip: continue
                ta = trees.get(a[0]) or trees.setdefault(a[0], BVHTree.FromPolygons(a[2].tolist(), self.polys[a[0]]))
                tb = trees.get(b[0]) or trees.setdefault(b[0], BVHTree.FromPolygons(b[2].tolist(), self.polys[b[0]]))
                if ta.overlap(tb):
                    out.append(k)
                    if limit and len(out) >= limit: return out
        return out + self.strokes()
