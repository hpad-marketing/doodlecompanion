"""Materials tab: put a look (clay, cel toon, felt... or one from a look add-on such as
ClayDoh) on the whole scene, the characters, the set or chosen props, in a colour palette.

shot['materials'] = {
  'layers': {'scene': L, 'character': L, 'set': L, 'props': L},   # any of them; narrower wins
  'light': {'key': 3.2, 'fill': 0.3, 'ambient': 0.5, 'angle': 40, 'height': 28, 'softness': 0.5, 'shadows': False},
  'addons': {'claydoh': 'C:/.../looks'},   # folder that holds each add-on package, for imports
}
shot['items'][i]['material'] = L        # one prop on its own (wins over the props layer)

L = {'look': 'clay', 'addon': 'doodle_looks', 'params': {...}, 'palette': 'teal-coral' | {...},
     'ink': True, 'keepCharacter': True, 'color': '#hex' (optional: every fill in one colour)}

Nothing here runs unless the shot has a layer, so older shots render exactly as before.
The ink outline is the studio's own (a geometry-nodes hull with its own material), so a
look only replaces the fill slots; 'ink': False switches the outline off for that target.
A look that fails (an add-on missing on this PC, an error inside it) leaves that target in
Ink & Mustard and says so in the log, so a render never stops for a material.
"""
import importlib
import json
import math
import os
import re
import sys
import zlib

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ADDONS = os.path.join(os.path.dirname(HERE), 'addons')
PALETTES = {p['id']: p for p in json.load(open(os.path.join(HERE, 'palettes.json'), encoding='utf-8'))['palettes']}
MUSTARD = '#E0A64B'
INK_MODS = ('DS Ink', 'DSL Ink')
FLOWER_HEAD = 0.06   # metres: a fill part this close to a flower's centre is a petal
LUMP = 0.3
SHAPE_STEP, MAX_PARTS = 2.0, 4000   # parts within this size ratio share a colour; past MAX_PARTS a model keeps one
OUTFIT = re.compile(r'_(shirt|sleeve|cuff|hood|pelvis)')


def _srgb(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(hexcol):
    h = hexcol.lstrip('#')
    return tuple(_srgb(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))


def palette(spec):
    if isinstance(spec, dict):
        base = dict(PALETTES['brand'])
        base.update(spec)
        return base
    return PALETTES.get(spec or 'brand', PALETTES['brand'])


def _luma(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _hash(s):
    return zlib.crc32(str(s).encode())


# ---------------------------------------------------------------- what is what
def _rig_of(ob):
    p = ob.parent
    while p is not None:
        if p.type == 'ARMATURE':
            return p
        p = p.parent
    for m in ob.modifiers:
        if m.type == 'ARMATURE' and m.object is not None:
            return m.object
    return None


def _item_of(ob):
    while ob is not None:
        if 'ds_item' in ob.keys():
            return int(ob['ds_item'])
        ob = ob.parent
    return None


def classify():
    """{'character': [...], 'set': [...], 'props': {item index: [...]}} for the render's mesh objects"""
    out = {'character': [], 'set': [], 'props': {}}
    for ob in bpy.data.objects:
        if ob.type not in ('MESH', 'CURVE', 'SURFACE', 'META') or not ob.material_slots:
            continue
        if any(m.type == 'NODES' and m.name == 'DS Face' for m in ob.modifiers):
            continue   # the face drawings keep their ink and fill
        if any(c.name in ('Bunny internals', 'Widgets') for c in ob.users_collection):
            continue
        it = _item_of(ob)
        if it is not None:
            out['props'].setdefault(it, []).append(ob)
        elif ob.get('dsl_set'):
            out['set'].append(ob)
        elif _rig_of(ob) is not None:
            out['character'].append(ob)
    return out


# ---------------------------------------------------------------- looks from add-ons
_mods = {}


def _look_fn(layer, addons, log):
    """the add-on's material(look, rgb, params) function, or None for the flat repaint"""
    look = layer.get('look') or 'ink-mustard'
    mod_name = layer.get('addon') or 'doodle_looks'
    if mod_name == 'doodle_looks' and look == 'ink-mustard':
        return None
    if mod_name not in _mods:
        where = (addons or {}).get(mod_name) or ADDONS
        if where not in sys.path:
            sys.path.insert(0, where)
        mod = importlib.import_module(mod_name)
        man = {}
        mp = os.path.join(os.path.dirname(mod.__file__), 'doodle_look.json')
        if os.path.exists(mp):
            man = json.load(open(mp, encoding='utf-8'))
        _mods[mod_name] = (mod, man)
    mod, man = _mods[mod_name]
    flat = next((lk for lk in man.get('looks', []) if lk.get('id') == look and lk.get('flat')), None)
    if flat:
        return None
    fn = getattr(mod, man.get('material') or 'material', None)
    if fn is None:
        raise AttributeError(f'{mod_name} has no {man.get("material") or "material"}() function')
    return lambda c: fn(look, c, dict(layer.get('params') or {}))


def _flat(c):
    """Ink & Mustard in another colour: the same flat, unlit fill"""
    key = '%.4f_%.4f_%.4f' % c[:3]
    name = 'DSM flat ' + key
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = tuple(c[:3]) + (1.0,)
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    m.diffuse_color = tuple(c[:3]) + (1.0,)
    m['dsm_look'] = 'ink-mustard'
    return m


# ---------------------------------------------------------------- painting
def _lumps(parts):
    """parts that sit inside each other are one form (the blobs of a tree's crown): their boxes
    share over LUMP of the smaller box. app/src/stage3d.js does the same."""
    if len(parts) > 600:
        return [[p] for p in parts]
    top = list(range(len(parts)))

    def find(i):
        while top[i] != i:
            top[i] = top[top[i]]
            i = top[i]
        return i
    vol = [max(1e-12, (p['hi'][0] - p['lo'][0]) * (p['hi'][1] - p['lo'][1]) * (p['hi'][2] - p['lo'][2])) for p in parts]
    for i, p in enumerate(parts):
        for j in range(i):
            q, v = parts[j], 1.0
            for a in range(3):
                v *= max(0.0, min(p['hi'][a], q['hi'][a]) - max(p['lo'][a], q['lo'][a]))
            if v > LUMP * min(vol[i], vol[j]):
                top[find(i)] = find(j)
    out = {}
    for i, p in enumerate(parts):
        out.setdefault(find(i), []).append(p)
    return list(out.values())


def _fur_of(layer, addons):
    """fur settings for a look whose manifest entry says "fur": true (strands grown on the fill)"""
    mod_name = layer.get('addon') or 'doodle_looks'
    man = (_mods.get(mod_name) or (None, {}))[1]
    lk = next((x for x in man.get('looks', []) if x.get('id') == layer.get('look')), None)
    if not lk or not lk.get('fur'):
        return None
    P = {q['id']: q.get('default') for q in lk.get('params', []) if q.get('id')}
    P.update(layer.get('params') or {})
    return {'length': float(P.get('furLength', 1.2)) / 100.0, 'density': float(P.get('furDensity', 0.6)),
            'tilt': float(P.get('furTilt', 0.35))}


def _face_objects(rig):
    return [o for o in bpy.data.objects if o.type == 'MESH' and _rig_of(o) is rig
            and any(m.type == 'NODES' and m.name == 'DS Face' for m in o.modifiers)]


def _fur_group(fill_mat, faces, fur):
    """geometry nodes: short strands on the faces that wear fill_mat, kept clear of the face drawings"""
    g = bpy.data.node_groups.new('DSM Fur', 'GeometryNodeTree')
    g.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = g.nodes, g.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    sel = N.new('GeometryNodeMaterialSelection')
    sel.inputs['Material'].default_value = fill_mat
    keep = sel.outputs['Selection']
    if faces:
        join_f = N.new('GeometryNodeJoinGeometry')
        for f in faces:
            oi = N.new('GeometryNodeObjectInfo')
            oi.transform_space = 'RELATIVE'
            oi.inputs['Object'].default_value = f
            L.new(oi.outputs['Geometry'], join_f.inputs['Geometry'])
        prox = N.new('GeometryNodeProximity')
        L.new(join_f.outputs['Geometry'], prox.inputs[0])
        far = N.new('FunctionNodeCompare')
        far.data_type, far.operation = 'FLOAT', 'GREATER_THAN'
        L.new(prox.outputs['Distance'], far.inputs[0])
        far.inputs[1].default_value = fur['length'] * 1.6 + 0.004
        both = N.new('FunctionNodeBooleanMath')
        both.operation = 'AND'
        L.new(keep, both.inputs[0])
        L.new(far.outputs[0], both.inputs[1])
        keep = both.outputs[0]
    dist = N.new('GeometryNodeDistributePointsOnFaces')
    dist.distribute_method = 'RANDOM'
    L.new(gi.outputs[0], dist.inputs['Mesh'])
    L.new(keep, dist.inputs['Selection'])
    dist.inputs['Density'].default_value = 4000 + 36000 * fur['density']
    line = N.new('GeometryNodeCurvePrimitiveLine')
    line.inputs['Start'].default_value = (0, 0, 0)
    line.inputs['End'].default_value = (0, 0, fur['length'])
    res = N.new('GeometryNodeResampleCurve')
    res.inputs['Count'].default_value = 3
    L.new(line.outputs[0], res.inputs['Curve'])
    tilt = N.new('FunctionNodeRandomValue')
    tilt.data_type = 'FLOAT_VECTOR'
    tilt.inputs['Min'].default_value = (-fur['tilt'], -fur['tilt'], -3.14)
    tilt.inputs['Max'].default_value = (fur['tilt'], fur['tilt'], 3.14)
    rot = N.new('FunctionNodeRotateRotation')
    L.new(dist.outputs['Rotation'], rot.inputs['Rotation'])
    e2r = N.new('FunctionNodeEulerToRotation')
    L.new(tilt.outputs['Value'], e2r.inputs[0])
    L.new(e2r.outputs[0], rot.inputs['Rotate By'])
    size = N.new('FunctionNodeRandomValue')
    size.data_type = 'FLOAT'
    size.inputs[2].default_value, size.inputs[3].default_value = 0.55, 1.15
    inst = N.new('GeometryNodeInstanceOnPoints')
    L.new(dist.outputs['Points'], inst.inputs['Points'])
    L.new(res.outputs[0], inst.inputs['Instance'])
    L.new(rot.outputs[0], inst.inputs['Rotation'])
    L.new(size.outputs[1], inst.inputs['Scale'])
    real = N.new('GeometryNodeRealizeInstances')
    L.new(inst.outputs[0], real.inputs[0])
    # strands taper from root to tip
    rad = N.new('GeometryNodeSetCurveRadius')
    L.new(real.outputs[0], rad.inputs['Curve'])
    par = N.new('GeometryNodeSplineParameter')
    taper = N.new('ShaderNodeMapRange')
    L.new(par.outputs['Factor'], taper.inputs['Value'])
    taper.inputs['To Min'].default_value = 1.0
    taper.inputs['To Max'].default_value = 0.35
    L.new(taper.outputs['Result'], rad.inputs['Radius'])
    prof = N.new('GeometryNodeCurvePrimitiveCircle')
    prof.inputs['Resolution'].default_value = 3
    prof.inputs['Radius'].default_value = max(0.0008, fur['length'] * 0.14)
    c2m = N.new('GeometryNodeCurveToMesh')
    L.new(rad.outputs[0], c2m.inputs['Curve'])
    L.new(prof.outputs[0], c2m.inputs['Profile Curve'])
    sm = N.new('GeometryNodeSetMaterial')
    L.new(c2m.outputs[0], sm.inputs['Geometry'])
    sm.inputs['Material'].default_value = fill_mat
    join = N.new('GeometryNodeJoinGeometry')
    L.new(gi.outputs[0], join.inputs[0])
    L.new(sm.outputs[0], join.inputs[0])
    L.new(join.outputs[0], go.inputs[0])
    return g


def _grow_fur(ob, fill_mat, fur):
    if fill_mat is None or any(m.name == 'DSM Fur' for m in ob.modifiers):
        return
    md = ob.modifiers.new('DSM Fur', 'NODES')
    md.node_group = _fur_group(fill_mat, _face_objects(_rig_of(ob)) if _rig_of(ob) else [], fur)


class _Painter:
    def __init__(self, layer, addons, log):
        self.layer = layer
        self.pal = palette(layer.get('palette'))
        self.make = _look_fn(layer, addons, log) or _flat
        self.cache = {}
        # one material up front: an add-on that errors fails here, so the target stays Ink & Mustard
        probe = self.make(rgb(MUSTARD))
        if not isinstance(probe, bpy.types.Material):
            raise TypeError('the look returned %r, not a material' % (probe,))
        self.lit = self.make is not _flat and not self._flat_emission(probe)
        # body outline: textured looks go without it unless it is switched on (face lines always stay)
        self.ink = layer.get('ink') if layer.get('ink') is not None else self.make is _flat
        self.fur = _fur_of(layer, addons) if self.make is not _flat else None

    @staticmethod
    def _flat_emission(m):
        """unlit looks (an emission straight to the output) need no light rig"""
        try:
            out = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial')
            src = out.inputs['Surface'].links[0].from_node if out.inputs['Surface'].is_linked else None
            # emission fed by a shader-to-RGB still reads the light (cel, paper)
            return src is not None and src.bl_idname == 'ShaderNodeEmission' and not any(n.bl_idname == 'ShaderNodeShaderToRGB' for n in m.node_tree.nodes)
        except Exception:
            return False

    def mat(self, hexcol):
        if self.layer.get('color'):
            hexcol = self.layer['color'] if hexcol != self.pal['ink'] else hexcol
        if hexcol not in self.cache:
            self.cache[hexcol] = self.make(rgb(hexcol))
        return self.cache[hexcol]

    def paint(self, ob, fill_hex, ink_hex=None):
        """fill slots get fill_hex, ink slots the palette's ink. The swap happens on the object's
        own copy of its mesh data: the ink modifier joins its line geometry onto the mesh, so
        object-linked slots would land on the wrong faces."""
        if ob.data is None or not hasattr(ob.data, 'materials'):
            return 0
        if not ob.data.get('dsm_copy'):
            ob.data = ob.data.copy()
            ob.data['dsm_copy'] = 1
        changed, fill_mat = 0, None
        for slot in ob.material_slots:
            m = slot.material
            if m is None or m.get('dsm_look'):
                continue
            ink = _luma(m.diffuse_color) < 0.05
            new = self.raw(ink_hex) if ink and ink_hex else self.mat(self.pal['ink'] if ink else fill_hex)
            if slot.link == 'OBJECT':
                slot.material = new
            else:
                ob.data.materials[slot.slot_index] = new
            changed += 1
            if not ink:
                fill_mat = new
        if ob.type == 'MESH' and _rig_of(ob) is None:
            self.segment(ob, fill_hex)
        if self.fur and ob.type == 'MESH' and _rig_of(ob) is not None:   # characters only: a furry room would be millions of strands
            _grow_fur(ob, fill_mat, self.fur)
        if not self.ink:
            for md in ob.modifiers:
                if md.type == 'NODES' and md.name in INK_MODS:
                    md.show_render = md.show_viewport = False
        return changed

    def raw(self, hexcol):
        """this colour exactly, whatever the layer's One colour says"""
        k = 'raw' + hexcol
        if k not in self.cache:
            self.cache[k] = self.make(rgb(hexcol))
        return self.cache[k]

    def segment(self, ob, fill_hex):
        """a model is many separate parts in one mesh: parts of the same shape share a colour, and
        each shape takes the palette's next one, so a repaint never turns a whole tree one colour.
        Flowers: stems and leaves are told from petals by being away from a centre, and the centres
        take the accent. app/src/stage3d.js does the same, so the Stage matches."""
        pieces = self.pal.get('pieces') or []
        if len(pieces) < 2:
            return
        import bmesh
        me = ob.data
        ink_slots = {i for i, s in enumerate(ob.material_slots) if s.material is not None and _luma(s.material.diffuse_color) < 0.016}
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        seen, parts = set(), []
        for f in bm.faces:
            if f.index in seen:
                continue
            seen.add(f.index)
            todo, faces = [f], []
            while todo:
                x = todo.pop()
                faces.append(x.index)
                for e in x.edges:
                    for y in e.link_faces:
                        if y.index not in seen:
                            seen.add(y.index)
                            todo.append(y)
            vs = list({v.index: v.co.copy() for i in faces for v in bm.faces[i].verts}.values())
            parts.append({'faces': faces, 'verts': vs, 'ink': f.material_index in ink_slots, 'mid': sum(vs, type(vs[0])()) / len(vs)})
        bm.free()
        fills = [p for p in parts if not p['ink']]
        if not 2 <= len(parts) <= MAX_PARTS or not fills:
            return
        s = pieces.index(fill_hex) if fill_hex in pieces else 0
        colours = [pieces[(s + i) % len(pieces)] for i in range(len(pieces))]
        centres = [p['mid'] for p in parts if p['ink']] if 'flower' in (str(ob.get('dsl_model') or '') + ob.name).lower() else []
        if centres:
            for p in fills:
                p['part'] = 0 if min((p['mid'] - c).length for c in centres) < FLOWER_HEAD else 1
        else:
            for p in fills:
                p['lo'] = [min(v[a] for v in p['verts']) for a in range(3)]
                p['hi'] = [max(v[a] for v in p['verts']) for a in range(3)]
            span = max(max(p['hi'][a] for p in fills) - min(p['lo'][a] for p in fills) for a in range(3)) or 1.0
            lumps = _lumps(fills)
            groups = {}
            for lump in lumps:
                dims = sorted(max(p['hi'][a] for p in lump) - min(p['lo'][a] for p in lump) for a in range(3))
                key = tuple(math.floor(math.log(max(d / span, 1e-3)) / math.log(SHAPE_STEP)) for d in dims)
                groups.setdefault(key, []).extend(lump)
            order = sorted(groups, key=lambda k: (-sum(len(p['verts']) for p in groups[k]), k))
            if len(order) < 2:
                return
            for i, k in enumerate(order):
                for p in groups[k]:
                    p['part'] = i % len(colours)
        slots = {}
        for p in fills:
            i = p['part']
            if i:
                if i not in slots:
                    me.materials.append(self.raw(colours[i]))
                    slots[i] = len(me.materials) - 1
                for n in p['faces']:
                    me.polygons[n].material_index = slots[i]
        if centres:
            me.materials.append(self.raw(self.pal['accent']))
            for p in parts:
                if p['ink']:
                    for n in p['faces']:
                        me.polygons[n].material_index = len(me.materials) - 1

    def paint_shell(self, ob):
        """the room shell is one mesh: walls, floor and ceiling each take their own colour"""
        me = ob.data = ob.data.copy()
        roles = ('wall', 'floor', 'ceiling')
        mats = [self.mat(self.pal[r]) for r in roles]
        me.materials.clear()
        for m in mats:
            me.materials.append(m)
        rot, mw = ob.matrix_world.to_3x3(), ob.matrix_world
        zs = [(mw @ poly.center).z for poly in me.polygons]
        mid = (min(zs) + max(zs)) / 2 if zs else 0.0
        for poly, z in zip(me.polygons, zs):
            # level faces are the floor (low) or the ceiling (high), whichever way they face
            level = abs((rot @ poly.normal).normalized().z) > 0.7
            poly.material_index = (1 if z <= mid else 2) if level else 0   # <=: an outdoor shell is one flat ground
        for slot in ob.material_slots:
            slot.link = 'DATA'
        if not self.ink:
            for md in ob.modifiers:
                if md.type == 'NODES' and md.name in INK_MODS:
                    md.show_render = md.show_viewport = False
        return len(me.polygons)


def _piece_colour(pal, key, name=''):
    n = name.lower()
    if any(w in n for w in ('rug', 'carpet', 'mat', 'cushion', 'pillow', 'vase', 'clock', 'lamp')):
        return pal['accent']
    pieces = pal['pieces'] or [pal['accent']]
    return pieces[_hash(key) % len(pieces)]


# ---------------------------------------------------------------- light for lit looks
def light(spec, pal, backdrop=None):
    """A key, a soft fill and an even ambient for looks that read light (clay, felt...). Flat
    looks ignore it. The set's own sun (DSL_Sun) becomes the key, so there is one sun, not two.
    Shadows stay off unless asked for: the doodle rule is no cast shadows."""
    import mathutils
    spec = spec or {}
    sc = bpy.context.scene
    cam = sc.camera
    yaw0 = 0.0
    if cam is not None:
        f = cam.matrix_world.to_3x3() @ mathutils.Vector((0, 0, -1))
        yaw0 = math.atan2(f.x, -f.y)
    key_e = float(spec.get('key', 3.2))
    made = []
    for name, energy, yaw, h, shadow in (
            ('DSL_Sun', key_e, math.radians(float(spec.get('angle', 40))), math.radians(float(spec.get('height', 28))), bool(spec.get('shadows'))),
            ('DSM_Fill', key_e * float(spec.get('fill', 0.3)), -math.radians(float(spec.get('angle', 40))) * 1.5, math.radians(15), False)):
        ob = bpy.data.objects.get(name)
        if ob is None or ob.type != 'LIGHT':
            ob = bpy.data.objects.new(name if name != 'DSL_Sun' else 'DSM_Key', bpy.data.lights.new(name, 'SUN'))
            sc.collection.objects.link(ob)
        ob.hide_render = False
        ob.data.energy = energy
        ob.data.color = (1.0, 1.0, 1.0) if name == 'DSL_Sun' else tuple(rgb(pal.get('ambient', '#FFFFFF')))
        ob.data.angle = math.radians(5 + 60 * float(spec.get('softness', 0.5)))
        if hasattr(ob.data, 'use_shadow'):
            ob.data.use_shadow = shadow
        # a sun shines down its -Z: from in front of the subject, off to one side, from above
        ob.rotation_mode = 'XYZ'
        ob.rotation_euler = (math.pi / 2 - h, 0, yaw0 + math.pi + yaw)
        if ob.animation_data:
            ob.animation_data_clear()
        made.append(ob.name)
    _world(pal, float(spec.get('ambient', 0.5)), backdrop)
    return made


def _world(pal, ambient, backdrop=None):
    """The camera still sees the backdrop colour; everything lit sees an even ambient light in
    the palette's ambient colour instead (Light Path › Is Camera Ray)."""
    sc = bpy.context.scene
    old = sc.world
    seen = None
    if old is not None and old.use_nodes:
        bg = next((n for n in old.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground'), None)
        if bg is not None:
            seen = tuple(bg.inputs['Color'].default_value)
    if backdrop:
        seen = tuple(rgb(backdrop)) + (1.0,)
    w = bpy.data.worlds.new('DSM world')
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    cam_bg = nt.nodes.new('ShaderNodeBackground')
    cam_bg.inputs['Color'].default_value = seen or (0.745, 0.381, 0.07, 1.0)
    amb = nt.nodes.new('ShaderNodeBackground')
    amb.inputs['Color'].default_value = tuple(rgb(pal.get('ambient', '#FFFFFF'))) + (1.0,)
    amb.inputs['Strength'].default_value = ambient
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(amb.outputs[0], mix.inputs[1])
    nt.links.new(cam_bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    sc.world = w


# ---------------------------------------------------------------- entry point
def apply(shot, cam, log, out_dir=None):
    spec = shot.get('materials') or {}
    layers = spec.get('layers') or {}
    per_item = {i: it['material'] for i, it in enumerate(shot.get('items') or []) if isinstance(it, dict) and it.get('material')}
    if not any(layers.values()) and not per_item:
        return None
    addons = spec.get('addons') or {}
    groups = classify()
    painters, report, lit = {}, {'targets': {}, 'failed': []}, []

    def painter(layer, what):
        k = json.dumps(layer, sort_keys=True)
        if k not in painters:
            try:
                painters[k] = _Painter(layer, addons, log)
            except Exception as e:
                painters[k] = None
                report['failed'].append({'target': what, 'look': layer.get('look'), 'addon': layer.get('addon'), 'error': str(e)})
                log(f'materials: {layer.get("look")} could not be made for {what} ({e}); it stays Ink & Mustard')
        return painters[k]

    def pick(*names):
        for n in names:
            if layers.get(n):
                return layers[n], n
        return None, None

    # characters (the lead and co-stars, outfits included)
    lay, src = pick('character', 'scene')
    if lay and groups['character']:
        p = painter(lay, 'character')
        if p:
            pal = p.pal
            fill = lay.get('bunny') or (MUSTARD if lay.get('keepCharacter', True) else pal['character'])
            fit = lay.get('outfit')
            # the outfit: Bunny's own hoodie is ink-coloured fills, a library outfit is any other mesh on the rig
            worn = lambda ob: bool(OUTFIT.search(ob.name)) or not ob.name.startswith('BUNNY_')
            n = sum(p.paint(ob, fit if fit and worn(ob) else fill, fit if worn(ob) else None) for ob in groups['character'])
            report['targets']['character'] = {'look': lay.get('look'), 'from': src, 'slots': n}
            lit.append(p)
    # the set
    lay, src = pick('set', 'scene')
    if lay and groups['set']:
        p = painter(lay, 'set')
        if p:
            n = 0
            for ob in groups['set']:
                if ob.get('dsl_shell'):
                    p.paint_shell(ob)
                    n += 1
                else:
                    n += p.paint(ob, _piece_colour(p.pal, ob.get('dsl_prop') or ob.name, ob.get('dsl_prop') or ob.name))
            report['targets']['set'] = {'look': lay.get('look'), 'from': src, 'slots': n}
            lit.append(p)
    # props: each its own (from the Materials tab's Selected props), else the props layer, else the scene
    for idx, obs in groups['props'].items():
        lay, src = (per_item[idx], 'item') if idx in per_item else pick('props', 'scene')
        if not lay:
            continue
        p = painter(lay, f'prop {idx}')
        if p:
            n = sum(p.paint(ob, _piece_colour(p.pal, (shot['items'][idx] or {}).get('id', idx) if idx < len(shot.get('items') or []) else idx, ob.name)) for ob in obs)
            report['targets'][f'prop {idx}'] = {'look': lay.get('look'), 'from': src, 'slots': n}
            lit.append(p)
    if any(p.lit for p in lit):
        set_layer = layers.get('set') or layers.get('scene')
        sp = palette(set_layer.get('palette')) if set_layer else None
        report['lights'] = light(spec.get('light'), lit[0].pal, sp['ceiling'] if sp and groups['set'] else None)
    elif groups['set'] and (layers.get('set') or layers.get('scene')):
        # a flat repaint of the set: the open sky above the walls takes the palette too
        sp = palette((layers.get('set') or layers.get('scene')).get('palette'))
        if sp.get('id') != 'brand':
            w = bpy.context.scene.world
            bg = w and w.use_nodes and next((n for n in w.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground'), None)
            if bg:
                w = w.copy()
                bpy.context.scene.world = w
                next(n for n in w.node_tree.nodes if n.bl_idname == 'ShaderNodeBackground').inputs['Color'].default_value = tuple(rgb(sp['ceiling'])) + (1.0,)
    log('materials: ' + (', '.join(f'{k} {v["look"]}' for k, v in report['targets'].items()) or 'nothing changed'))
    if out_dir:
        try:
            json.dump(report, open(os.path.join(out_dir, 'materials.json'), 'w'), indent=1)
        except OSError:
            pass
    return report
