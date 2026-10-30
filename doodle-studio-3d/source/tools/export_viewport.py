"""Export Bunny3D for Doodle Studio 3D's live viewport.

blender -b Bunny3D_v2.blend --python export_viewport.py -- out.json [subdiv_level]

Writes rest meshes (Subdivision applied, no armature/cloth/outline), skin
weights (bendy ear bones expanded into their segments), sleeve shape keys,
the bone hierarchy with rest matrices, Doodle Studio controls and the face
library. The viewport's JS rig reproduces Blender's FK from this data.
"""
import bpy, sys, json, base64, array, os, math

argv = sys.argv[sys.argv.index('--') + 1:]
if argv[0].endswith('.blend'):
    bpy.ops.wm.open_mainfile(filepath=argv[0])
    argv = argv[1:]
OUT = argv[0]
LEVEL = int(argv[1]) if len(argv) > 1 else 1
arm = bpy.data.objects['BUNNY_rig']
meta = json.loads(bpy.data.texts['DOODLE_STUDIO_RIG.json'].as_string())
HERE = os.path.dirname(bpy.data.filepath)


def b64(kind, values):
    return base64.b64encode(array.array(kind, values).tobytes()).decode()


def mat(m):
    return [m[r][c] for c in range(4) for r in range(4)]  # column-major, as three.js expects


# ---- bones
bones = []
for b in arm.data.bones:
    if b.name.startswith('WGT'):
        continue
    bones.append({
        'name': b.name, 'parent': b.parent.name if b.parent else None,
        'head': list(arm.matrix_world @ b.head_local), 'tail': list(arm.matrix_world @ b.tail_local),
        'rest': mat(arm.matrix_world @ b.matrix_local), 'deform': b.use_deform,
        'segments': b.bbone_segments, 'ease_in': b.bbone_easein, 'ease_out': b.bbone_easeout,
        'length': b.length,
    })
bmap = {b['name']: b for b in bones}

# bendy bones become N virtual segment bones '<name>#k'
BENDY = [b.name for b in arm.data.bones if b.use_deform and b.bbone_segments > 1]


def segment_weights(bone_name, co):
    """Blender blends a bendy-bone vertex between the two segment joints around it (rest pose, straight mapping)."""
    b = arm.data.bones[bone_name]
    m = (arm.matrix_world @ b.matrix_local).inverted()
    n = b.bbone_segments
    t = max(0.0, min(1.0, (m @ co).y / b.length)) * n
    i0 = min(n - 1, math.floor(t))
    f = t - i0
    return [(f'{bone_name}#{i0}', 1 - f), (f'{bone_name}#{i0 + 1}', f)]


# ---- meshes
dg = bpy.context.evaluated_depsgraph_get()
meshes = []
skin_names = []
skin_index = {}


def sidx(name):
    if name not in skin_index:
        skin_index[name] = len(skin_names)
        skin_names.append(name)
    return skin_index[name]


SKIP = {'BUNNY_face', 'BUNNY_head_surface'}


def subdivision_stencils(cage_me, sub_mod, mw):
    """Blender's own subdivision as a fixed linear map: subdivided = S @ cage.
    Skinning the cage and then applying S matches Blender's deform-then-subdivide."""
    tmp_me = cage_me.copy()
    tmp = bpy.data.objects.new('_stencil', tmp_me)
    bpy.context.scene.collection.objects.link(tmp)
    m = tmp.modifiers.new('sub', 'SUBSURF')
    for k in ('levels', 'quality', 'boundary_smooth', 'use_creases', 'use_custom_normals', 'use_limit_surface'):
        if hasattr(sub_mod, k):
            setattr(m, k, getattr(sub_mod, k))
    m.levels = LEVEL
    n = len(tmp_me.vertices)
    cols = {}
    sub_count = None
    faces = None
    sub_mat = None
    for j0 in range(0, n, 3):
        co = [0.0] * (3 * n)
        for k in range(3):
            if j0 + k < n:
                co[3 * (j0 + k) + k] = 1.0
        tmp_me.vertices.foreach_set('co', co)
        tmp_me.update()
        dg.update()
        e = tmp.evaluated_get(dg)
        me = e.to_mesh()
        if sub_count is None:
            sub_count = len(me.vertices)
            me.calc_loop_triangles()
            faces = [i for t in me.loop_triangles for i in t.vertices]
            sub_mat = [0] * sub_count
            for t in me.loop_triangles:
                for vi in t.vertices:
                    sub_mat[vi] = max(sub_mat[vi], t.material_index)
        out = [0.0] * (3 * sub_count)
        me.vertices.foreach_get('co', out)
        for k in range(3):
            j = j0 + k
            if j >= n:
                continue
            for i in range(sub_count):
                w = out[3 * i + k]
                if abs(w) > 1e-7:
                    cols.setdefault(i, []).append((j, w))
        e.to_mesh_clear()
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(tmp_me)
    offs, idx, wts = [0], [], []
    for i in range(sub_count):
        for j, w in cols.get(i, []):
            idx.append(j)
            wts.append(w)
        offs.append(len(idx))
    return sub_count, faces, sub_mat, offs, idx, wts


for ob in bpy.data.objects:
    if ob.type != 'MESH' or not ob.name.startswith('BUNNY_') or ob.hide_render or ob.name in SKIP:
        continue
    saved = {}
    sub_mod = None
    for m in ob.modifiers:
        saved[m.name] = m.show_viewport
        if m.type in ('ARMATURE', 'CLOTH', 'NODES', 'COLLISION', 'SUBSURF', 'CORRECTIVE_SMOOTH'):
            m.show_viewport = False
        if m.type == 'SUBSURF':
            sub_mod = m
    keys = ob.data.shape_keys.key_blocks if ob.data.shape_keys else []
    for k in keys:
        k.value = 0.0
    dg.update()
    e = ob.evaluated_get(dg)
    cage = bpy.data.meshes.new_from_object(e)   # rest cage, Solidify applied, vertex groups kept
    mw = ob.matrix_world
    pos = []
    for v in cage.vertices:
        pos += list(mw @ v.co)
    groups = {g.index: g.name for g in ob.vertex_groups}
    si, sw = [], []
    for v in cage.vertices:
        ws = []
        co = mw @ v.co
        for g in v.groups:
            name = groups.get(g.group)
            if not name or name not in bmap or g.weight <= 1e-4 or not arm.data.bones[name].use_deform:
                continue
            if name in BENDY:
                ws += [(nm, g.weight * f) for nm, f in segment_weights(name, co) if f > 0]
            else:
                ws.append((name, g.weight))
        acc = {}
        for nm, w in ws:
            acc[nm] = acc.get(nm, 0) + w
        ws = sorted(acc.items(), key=lambda x: -x[1])[:4]
        tot = sum(w for _, w in ws) or 1.0
        ws = [(nm, w / tot) for nm, w in ws] + [(None, 0.0)] * (4 - len(ws))
        for nm, w in ws:
            si.append(sidx(nm) if nm else 0)
            sw.append(w)
    n_cage = len(cage.vertices)
    morphs = {}
    for k in keys[1:]:
        k.value = 1.0
        dg.update()
        m2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        if len(m2.vertices) == n_cage:
            d = []
            for v0, v1 in zip(cage.vertices, m2.vertices):
                d += list(mw.to_3x3() @ (v1.co - v0.co))
            morphs[k.name] = b64('f', d)
        bpy.data.meshes.remove(m2)
        k.value = 0.0
    smooth = None
    cs = next((m for m in ob.modifiers if m.type == 'CORRECTIVE_SMOOTH'), None)
    if cs is not None:
        gi = ob.vertex_groups[cs.vertex_group].index if cs.vertex_group else None
        cw = [next((g.weight for g in v.groups if g.group == gi), 0.0) if gi is not None else 1.0 for v in cage.vertices]
        cage.calc_loop_triangles()
        smooth = {'factor': cs.factor, 'iterations': cs.iterations, 'weights': b64('f', cw),
                  'edges': b64('I', [i for e in cage.edges for i in e.vertices]),
                  'tris': b64('I', [i for t in cage.loop_triangles for i in t.vertices])}
    if sub_mod is not None:
        sub_count, faces, sub_mat, offs, idx, wts = subdivision_stencils(cage, sub_mod, mw)
    else:
        cage.calc_loop_triangles()
        sub_count = n_cage
        faces = [i for t in cage.loop_triangles for i in t.vertices]
        sub_mat = [0] * n_cage
        for t in cage.loop_triangles:
            for vi in t.vertices:
                sub_mat[vi] = max(sub_mat[vi], t.material_index)
        offs, idx, wts = list(range(n_cage + 1)), list(range(n_cage)), [1.0] * n_cage
    bpy.data.meshes.remove(cage)
    for m in ob.modifiers:
        m.show_viewport = saved[m.name]
    meshes.append({
        'name': ob.name, 'materials': [m.name for m in ob.data.materials],
        'outline': any(m.type == 'NODES' and m.name == 'DS Ink' for m in ob.modifiers),
        'cageCount': n_cage, 'cage': b64('f', pos), 'skinIndex': b64('H', si), 'skinWeight': b64('f', sw), 'morphs': morphs,
        'count': sub_count, 'index': b64('I', faces), 'material': b64('B', sub_mat),
        'stencilOffset': b64('I', offs), 'stencilIndex': b64('I', idx), 'stencilWeight': b64('f', wts),
        'smooth': smooth,
    })
    print('mesh', ob.name, n_cage, '->', sub_count, 'stencil nnz', len(idx), list(morphs), flush=True)

# ---- settings
st = bpy.data.objects['BUNNY_settings']
settings = {k: st[k] for k in st.keys() if isinstance(st[k], (int, float))}
face_lib = json.load(open(os.path.join(HERE, 'face_library.json')))
head_surface = bpy.data.objects['BUNNY_head_surface']
out = {
    'version': 1, 'S': meta['S'], 'controls': meta['controls'], 'ds_bones': meta.get('bones'),
    'bones': bones, 'skinBones': skin_names, 'meshes': meshes, 'settings': settings,
    'floor_z': arm.get('floor_z', 0.0), 'ear_curl': arm.get('ear_curl', 0.6),
    'colors': {'ink': '#1F1F1D', 'mustard': '#E0A64B'},
    'face': {k: face_lib[k] for k in ('units', 'plane', 'faces', 'speech', 'gazes', 'speech_offsets_px', 'items')},
}
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB', len(skin_names), 'skin bones')
