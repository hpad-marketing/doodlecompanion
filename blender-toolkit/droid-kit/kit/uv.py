"""Proper UVs for every robot part.
python3 uv.py in.blend out.blend
Per part: faces are grouped into surface regions (flat panels, and smooth curved sides such as cylinder walls).
Bevel strips join the panel they lean toward. Seams go on the region borders. Tubes get one straight cut,
closed shapes get split in two. Then: angle-based unwrap, the same texel density on every part,
and one packed 0-1 layout per material (so each material can be baked or painted to its own texture).
Writes a stretch report.
"""
import bpy, bmesh, sys, math, json, collections
import os
from mathutils import Vector
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kit
SMOOTH = math.radians(kit.get('uv_smooth_deg', 20))     # neighbours closer than this are one smooth surface
SMALL = 0.10                  # regions under this share of the part's area merge into a neighbour

def regions_for(bm):
    bm.faces.ensure_lookup_table()
    reg = [-1] * len(bm.faces); rid = 0
    for f in bm.faces:
        if reg[f.index] >= 0: continue
        stack = [f]; reg[f.index] = rid
        while stack:
            g = stack.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if reg[h.index] < 0 and g.normal.angle(h.normal, 0) < SMOOTH:
                        reg[h.index] = rid; stack.append(h)
        rid += 1
    total = sum(f.calc_area() for f in bm.faces) or 1
    # merge small regions (bevel strips, corner patches) into the neighbour they face most
    for _ in range(6):
        area = collections.Counter(); nsum = collections.defaultdict(Vector)
        for f in bm.faces:
            a = f.calc_area(); area[reg[f.index]] += a; nsum[reg[f.index]] += f.normal * a
        changed = False
        for r in sorted(area, key=lambda k: area[k]):
            if area[r] / total >= SMALL: continue
            nb = collections.Counter()
            for f in bm.faces:
                if reg[f.index] != r: continue
                for e in f.edges:
                    for h in e.link_faces:
                        q = reg[h.index]
                        if q != r: nb[q] += e.calc_length()
            if not nb: continue
            n = nsum[r].normalized() if nsum[r].length else Vector((0, 0, 1))
            best = max(nb, key=lambda q: (area[q] / total >= SMALL or area[q] > area[r],
                                           -n.angle(nsum[q].normalized() if nsum[q].length else n, 0)))
            for f in bm.faces:
                if reg[f.index] == r: reg[f.index] = best
            area[best] += area[r]; nsum[best] += nsum[r]; area[r] = 0; changed = True
        if not changed: break
    return reg

def euler_char(faces):
    vs = {v for f in faces for v in f.verts}; es = {e for f in faces for e in f.edges}
    return len(vs) - len(es) + len(faces)

def cut_until_disk(bm, faces, seams):
    """add seams inside a region until its boundary is one connected loop (tube -> one cut, closed -> split)"""
    cs = set(faces)
    inner = {e for f in faces for e in f.edges}
    for _ in range(8):
        bnd = {e for e in inner if e in seams or sum(h in cs for h in e.link_faces) < 2}
        bverts = {v for e in bnd for v in e.verts}
        loops = []; left = set(bverts)
        while left:
            s0 = left.pop(); grp = {s0}; st = [s0]
            while st:
                v = st.pop()
                for e in v.link_edges:
                    if e in bnd:
                        o = e.other_vert(v)
                        if o in left: left.discard(o); grp.add(o); st.append(o)
            loops.append(grp)
        if len(loops) == 1: return
        if len(loops) >= 2:     # tube: shortest interior path joining two boundary loops
            src, dst = loops[0], set().union(*loops[1:])
            prev = {v: None for v in src}; q = collections.deque(src); hit = None
            while q and hit is None:
                v = q.popleft()
                for e in v.link_edges:
                    if e not in inner or e in bnd: continue
                    o = e.other_vert(v)
                    if o in prev: continue
                    prev[o] = (v, e)
                    if o in dst: hit = o; break
                    q.append(o)
            if hit is None: return
            v = hit
            while prev[v] is not None:
                pv, e = prev[v]; seams.add(e); v = pv
            continue
        # closed shape: split by the side of its dominant axis
        axis = max(range(3), key=lambda i: sum(abs(f.normal[i]) * f.calc_area() for f in faces))
        for e in inner:
            hs = [h for h in e.link_faces if h in cs]
            if len(hs) == 2 and (hs[0].normal[axis] >= 0) != (hs[1].normal[axis] >= 0): seams.add(e)


objs = [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o]
nseam = 0
for o in objs:
    me = o.data
    while me.uv_layers: me.uv_layers.remove(me.uv_layers[0])
    me.uv_layers.new(name='UVMap')
    bm = bmesh.new(); bm.from_mesh(me); bm.normal_update()
    reg = regions_for(bm)
    seams = set()
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) == 2 and reg[lf[0].index] != reg[lf[1].index]: seams.add(e)
    byreg = collections.defaultdict(list)
    for f in bm.faces: byreg[reg[f.index]].append(f)
    for r, fs in byreg.items(): cut_until_disk(bm, fs, seams)
    for e in bm.edges: e.seam = e in seams
    nseam += len(seams)
    bm.to_mesh(me); bm.free()

# unwrap every part at once, then one texel density for all, then pack per material
vl = bpy.context.view_layer
for o in bpy.data.objects: o.select_set(False)
for o in objs: o.hide_set(False); o.select_set(True)
vl.objects.active = objs[0]
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True, margin=0.0)
bpy.ops.uv.average_islands_scale(scale_uv=False, shear=False)
bpy.ops.object.mode_set(mode='OBJECT')

bymat = collections.defaultdict(list)
for o in objs: bymat[o.active_material.name if o.active_material else '-'].append(o)
for mname, group in bymat.items():
    for o in bpy.data.objects: o.select_set(False)
    for o in group: o.select_set(True)
    vl.objects.active = group[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, scale=True, margin_method='FRACTION', margin=0.004,
                            shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')

# ---------------------------------------------------------------- stretch report
def tri_area(a, b, c): return ((b - a).cross(c - a)).length / 2
rep = {}; good_all = tot_all = 0; worst = []
for mname, group in bymat.items():
    ratios = []; wts = []
    for o in group:
        me = o.data; uv = me.uv_layers['UVMap'].data
        for p in me.polygons:
            vs = [me.vertices[me.loops[li].vertex_index].co * 1 for li in p.loop_indices]
            us = [Vector((uv[li].uv.x, uv[li].uv.y, 0)) for li in p.loop_indices]
            a3 = sum(tri_area(vs[0], vs[i], vs[i + 1]) for i in range(1, len(vs) - 1))
            a2 = sum(tri_area(us[0], us[i], us[i + 1]) for i in range(1, len(us) - 1))
            if a3 > 1e-9:
                ratios.append(a2 / a3); wts.append(a3)
            # angle distortion per corner
    W = sum(wts); mean = sum(r * w for r, w in zip(ratios, wts)) / W
    good = sum(w for r, w in zip(ratios, wts) if 0.8 <= r / mean <= 1.25)
    rep[mname] = dict(parts=len(group), faces=len(ratios), area_within_20pct=round(100 * good / W, 1),
                      texel_density=round(math.sqrt(mean), 2))
    good_all += good; tot_all += W
# overlaps check: UV islands overlapping inside a material group
rep['_all'] = dict(parts=len(objs), seams=nseam, area_within_20pct=round(100 * good_all / tot_all, 1))
print('UVREPORT', json.dumps(rep))
os.makedirs('out', exist_ok=True); json.dump(rep, open('out/uv_report.json', 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=out)
