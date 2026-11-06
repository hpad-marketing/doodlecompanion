"""Realism 3 detail: hex bolts on panel corners, panel-line grooves on the body, back conduits with clamps, status LEDs.
Every piece is raycast-placed on a flat, uncovered face at rest, sunk 1.5 mm into it, joined per part and parented to it.
python3 detail.py in.blend out.blend"""
import bpy, bmesh, sys, math
from mathutils import Vector, Matrix
blend, out = sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=blend)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
arm.data.pose_position = 'REST'; bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); sc = bpy.context.scene
col = bpy.data.collections.get('Details') or bpy.data.collections.new('Details')
if col.name not in sc.collection.children: sc.collection.children.link(col)
STEEL = bpy.data.materials['RB_metal_bare']; POLY = bpy.data.materials['RB_polymer']

def flat_ok(ob, c, n, r):
    """all rays in a disk of radius r hit ob first, on one plane facing n"""
    t1 = n.orthogonal().normalized(); t2 = n.cross(t1)
    ds = []
    for k in range(9):
        a = k * math.tau / 8
        p = c if k == 8 else c + (t1 * math.cos(a) + t2 * math.sin(a)) * r
        ok, loc, nor, i, h, _ = sc.ray_cast(dg, p + n * 0.3, -n, distance=0.5)
        if not ok or h.name != ob.name or nor.dot(n) < 0.998: return None
        ds.append((loc - c).dot(n))
    if max(ds) - min(ds) > 0.0005: return None
    return c + n * (sum(ds) / len(ds))

def add_geo(bm, M, kind, size):
    """kind 'bolt': hex head + washer; 'led': bezel ring + lens (lens faces get material 1)"""
    if kind == 'bolt':
        r = size; geo = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r * 1.45, radius2=r * 1.45, depth=0.0025 + 0.0015, matrix=M @ Matrix.Translation((0, 0, 0.0005)))
        geo = bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=r, radius2=r, depth=0.004 + 0.0015, matrix=M @ Matrix.Translation((0, 0, 0.0015)))
    elif kind == 'led':
        r = size
        bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=r * 1.5, radius2=r * 1.35, depth=0.005, matrix=M @ Matrix.Translation((0, 0, 0.001)))
        g = bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=r, matrix=M @ Matrix.Translation((0, 0, 0.0025)) @ Matrix.Diagonal((1, 1, 0.45, 1)))
        for v in g['verts']:
            for f in v.link_faces: f.material_index = 1

def frame_at(p, n):
    z = n.normalized(); x = z.orthogonal().normalized(); y = z.cross(x)
    M = Matrix((x, y, z)).transposed().to_4x4(); M.translation = p; return M

def finish(ob, bm, name, mats):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in mats: me.materials.append(m)
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    o.parent = ob; o.matrix_parent_inverse = Matrix.Identity(4); o.matrix_basis = ob.matrix_world.inverted()
    o['rb_detail'] = ob.name
    for p in me.polygons: p.use_smooth = True
    return o

# rest-pose BVH of every part, to reject a bolt that would touch a neighbour
from mathutils.bvhtree import BVHTree
PB = {}
for o in bpy.data.objects:
    if o.type == 'MESH' and 'rig_bone' in o:
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        PB[o.name] = (BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in o.data.polygons]),
                      Vector([min(v[i] for v in vs) for i in range(3)]), Vector([max(v[i] for v in vs) for i in range(3)]))
def clear_of_others(M, kind, size, owner):
    t = bmesh.new(); add_geo(t, M, kind, size); t.verts.ensure_lookup_table()
    lo = Vector([min(v.co[i] for v in t.verts) for i in range(3)]) - Vector((0.003,) * 3)
    hi = Vector([max(v.co[i] for v in t.verts) for i in range(3)]) + Vector((0.003,) * 3)
    tb = BVHTree.FromBMesh(t); t.free()
    for nm, (bv, plo, phi) in PB.items():
        if nm == owner or any(lo[i] > phi[i] or hi[i] < plo[i] for i in range(3)): continue
        if tb.overlap(bv): return False
    return True

# ---------------------------------------------------------------- bolts
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__))); import kit
PANELS = kit.get('bolt_panels', [])
DET = kit.get('details', {})
AX = [Vector(v) for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1))]
nb = 0; made = []
for base in PANELS:
    for ob in [o for o in bpy.data.objects if o.type == 'MESH' and 'rig_bone' in o and (o.name == base or o.name.startswith(base + '.'))]:
        cs = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        bm = bmesh.new(); cnt = 0
        big = max(ob.dimensions) > 0.6
        r = 0.009 if big else 0.0065
        for n in AX:
            t1 = Vector((0, 0, 1)) if abs(n.z) < 0.5 else Vector((1, 0, 0)); t2 = n.cross(t1)
            a1 = [p.dot(t1) for p in cs]; a2 = [p.dot(t2) for p in cs]; top = max(p.dot(n) for p in cs)
            span1 = max(a1) - min(a1); span2 = max(a2) - min(a2)
            if span1 < 0.09 or span2 < 0.09: continue
            ins = max(0.032, min(span1, span2) * 0.15)
            for s1 in (0, 1):
                for s2 in (0, 1):
                    q1 = min(a1) + ins + s1 * (span1 - 2 * ins); q2 = min(a2) + ins + s2 * (span2 - 2 * ins)
                    guess = t1 * q1 + t2 * q2 + n * top
                    ok, loc, nor, i, h, _ = sc.ray_cast(dg, guess + n * 0.3, -n, distance=0.6)
                    if not ok or h.name != ob.name: continue
                    p = flat_ok(ob, loc, n, r * 2.0)
                    if p is None: continue
                    Mb = frame_at(p - n * 0.0015, n)
                    if not clear_of_others(Mb, 'bolt', r, ob.name): continue
                    add_geo(bm, Mb, 'bolt', r); cnt += 1
        if cnt: made.append(finish(ob, bm, 'bolts_' + ob.name, [STEEL])); nb += cnt; print('  bolts', ob.name, cnt)
        else: bm.free()
print('BOLTS', nb, 'on', len(made), 'parts')

# ---------------------------------------------------------------- panel-line grooves (decal-style, dark + bumped)
def groove_mat():
    m = bpy.data.materials.get('RB_panel_line') or bpy.data.materials.new('RB_panel_line'); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF'); b.inputs['Base Color'].default_value = (0.012, 0.011, 0.01, 1)
    b.inputs['Roughness'].default_value = 0.85; b.inputs['Metallic'].default_value = 0.3
    return m
GM = groove_mat(); nl = 0
body = bpy.data.objects[DET.get('body', 'body_box')]
for n, segs in (() if not DET.get('panel_lines', True) else ((1, 0, 0), [((0, 0.5, 0.0), (0, 0.5, 1.0)), ((0, 0.0, 0.62), (0, 1.0, 0.62))]),
                ((-1, 0, 0), [((0, 0.5, 0.0), (0, 0.5, 1.0)), ((0, 0.0, 0.62), (0, 1.0, 0.62))])):
    n = Vector(n); cs = [body.matrix_world @ Vector(c) for c in body.bound_box]
    lo = Vector([min(c[i] for c in cs) for i in range(3)]); hi = Vector([max(c[i] for c in cs) for i in range(3)])
    bm = bmesh.new()
    for a, b in segs:
        # walk along the segment and keep the runs whose every step is a clear, flat hit
        A = Vector((0, lo.y + a[1] * (hi.y - lo.y), lo.z + a[2] * (hi.z - lo.z))); B = Vector((0, lo.y + b[1] * (hi.y - lo.y), lo.z + b[2] * (hi.z - lo.z)))
        steps = 60; run = []
        def flush(run):
            if len(run) < 4: return
            p0, p1 = run[0], run[-1]; d = (p1 - p0); L = d.length; t = d.normalized(); w = n.cross(t)
            M = Matrix((t * L, w * 0.003, n)).transposed().to_4x4(); M.translation = (p0 + p1) / 2 + n * 0.0004
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5, matrix=M)
        for k in range(steps + 1):
            q = A.lerp(B, k / steps); q.x = (hi.x if n.x > 0 else lo.x)
            ok, loc, nor, i, h, _ = sc.ray_cast(dg, q + n * 0.3, -n, distance=0.6)
            good = ok and h.name == body.name and nor.dot(n) > 0.998
            if good: run.append(loc)
            else: flush(run); run = []
        flush(run)
    if len(bm.faces): finish(body, bm, 'panel_lines_%+d' % n.x, [GM]); nl += 1
    else: bm.free()
print('PANEL LINES', nl)

# ---------------------------------------------------------------- back conduits with clamps
cs = [body.matrix_world @ Vector(c) for c in body.bound_box]
lo = Vector([min(c[i] for c in cs) for i in range(3)]); hi = Vector([max(c[i] for c in cs) for i in range(3)])
nconds = 0
for z, r in (((lo.z + 0.14, 0.011), (lo.z + 0.19, 0.008)) if DET.get('conduits', True) else ()):
    n = Vector((0, 1, 0)); xs = [lo.x + 0.1 + k * (hi.x - lo.x - 0.2) / 20 for k in range(21)]
    hits = []
    for x in xs:
        ok, loc, nor, i, h, _ = sc.ray_cast(dg, Vector((x, hi.y + 0.3, z)), -n, distance=0.6)
        hits.append(loc if ok and h.name == body.name and nor.dot(n) > 0.998 else None)
    if any(h is None for h in hits) or max(h.y for h in hits) - min(h.y for h in hits) > 0.0005:
        print('CONDUIT SKIP z', round(z, 3)); continue
    face_y = hits[0].y; off = r + 0.004
    bm = bmesh.new()
    # straight run + elbows dropping into the face at both ends
    x0, x1 = hits[0].x + 0.03, hits[-1].x - 0.03
    pipe = Matrix.Translation(((x0 + x1) / 2, face_y + off, z)) @ Matrix.Rotation(math.pi / 2, 4, 'Y')
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r, radius2=r, depth=x1 - x0, matrix=pipe)
    for xe in (x0, x1):
        M = Matrix.Translation((xe, face_y + off / 2 - 0.0015 / 2, z)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r, radius2=r, depth=off + 0.0015, matrix=M)
        bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=r, matrix=Matrix.Translation((xe, face_y + off, z)))
        # gland ring where it enters the body
        M2 = Matrix.Translation((xe, face_y + 0.002, z)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=r * 1.6, radius2=r * 1.4, depth=0.007, matrix=M2)
    cl = bmesh.new()
    for k in range(4):
        xc = x0 + (x1 - x0) * (k + 0.5) / 4
        # saddle clamp: a strap over the pipe whose feet sit on the face
        M = Matrix.Translation((xc, face_y + off / 2 + 0.0005, z)) @ Matrix.Rotation(-math.pi / 2, 4, 'X') @ Matrix.Diagonal((0.016, (r + 0.003) * 2, off + 0.004, 1))
        bmesh.ops.create_cube(cl, size=1.0, matrix=M)
    me_m = [POLY, STEEL]
    for f in cl.faces: f.material_index = 1
    tmp = bpy.data.meshes.new('tmp'); cl.to_mesh(tmp); cl.free(); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    finish(body, bm, 'conduit_%d' % nconds, me_m); nconds += 1
print('CONDUITS', nconds)

# ---------------------------------------------------------------- status LEDs below the serial
serial = bpy.data.objects.get((DET.get('status_leds') or {}).get('under_decal', '')) if DET.get('status_leds') else None
leds = 0
if serial:
    Ms = serial.matrix_world; n = (Ms.to_3x3() @ Vector((0, 0, 1))).normalized(); right = (Ms.to_3x3() @ Vector((1, 0, 0)))
    base = Ms.translation - n * 0.0005 - (Ms.to_3x3() @ Vector((0, 1, 0))) * 0.78 - right * 0.35
    bm = bmesh.new(); placed = []
    for k in range(3):
        c = base + right * (0.17 * k)
        ok, loc, nor, i, h, _ = sc.ray_cast(dg, c + n * 0.3, -n, distance=0.6)
        if not ok or h.name != 'body_box': continue
        p = flat_ok(body, loc, n, 0.013)
        if p is None: continue
        add_geo(bm, frame_at(p - n * 0.0015, n), 'led', 0.0085); placed.append(k)
    if placed:
        lm = []
        for k, (nm, colr, expr) in enumerate((('green', (0.1, 1.0, 0.2, 1), '3.0'),
                                              ('amber', (1.0, 0.45, 0.05, 1), '2.5+2.5*sin(frame*0.26)'),
                                              ('red', (1.0, 0.06, 0.03, 1), '4.0*(sin(frame*0.9)>0.6)'))):
            m = bpy.data.materials.get('RB_led_' + nm) or bpy.data.materials.new('RB_led_' + nm); m.use_nodes = True
            b = m.node_tree.nodes.get('Principled BSDF'); b.inputs['Base Color'].default_value = colr
            b.inputs['Emission Color'].default_value = colr; b.inputs['Roughness'].default_value = 0.15
            b.inputs['Transmission Weight'].default_value = 0.3
            d = b.inputs['Emission Strength'].driver_add('default_value'); d.driver.type = 'SCRIPTED'; d.driver.expression = expr
            lm.append(m)
        # one object per LED colour so each lens gets its own material
        tmp = bpy.data.meshes.new('tmp'); bm.to_mesh(tmp); bm.free()
        for j, k in enumerate(placed):
            b2 = bmesh.new(); b2.from_mesh(tmp)
            # keep only geometry of LED j (each LED = bezel + lens, built in order)
            per = len(b2.verts) // len(placed)
            b2.verts.ensure_lookup_table()
            kill = [v for idx, v in enumerate(b2.verts) if not (j * per <= idx < (j + 1) * per)]
            bmesh.ops.delete(b2, geom=kill, context='VERTS')
            finish(body, b2, 'led_' + ('green', 'amber', 'red')[k], [POLY, lm[k]]); leds += 1
        bpy.data.meshes.remove(tmp)
print('LEDS', leds)
arm.data.pose_position = 'POSE'
bpy.ops.wm.save_as_mainfile(filepath=out)
