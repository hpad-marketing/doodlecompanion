"""Ink lines that read at any camera angle and in any light, whenever the outline is on.

The geometry-nodes hull (DS Ink / DSL Ink) draws each object's silhouette by drawing its
back faces a stroke wider. Where two parts touch or overlap (a sofa arm on its seat, a
cushion against the back, a wall meeting the floor) whatever sits behind hides that hull,
so the line vanishes and the parts merge into one blob. This pass adds those lines back
in the compositor, from the render's own depth and part ids, at exactly the hull's width
in screen pixels:

  depth step   a part in front of another part of the same piece: the line goes on the
               far side, one stroke wide, like the hull, so silhouettes don't double up
  seam         two separate parts meet (a cushion and the seat, a cup on a table, the floor
               and a wall, Bunny on the sofa): a line one stroke wide on the seam

Both come from geometry, never from shading, so a light, a shadow or a lit look can't
move or hide them. Ink geometry (the hull itself, crease lines, face drawings, black
parts) is left alone, an object whose outline is switched off gets no new lines, and a
character is one part, so Bunny's own drawing stays as designed.

Default ON for any shot where an ink outline renders; shot['inkLines'] = False turns it
off. Width follows BUNNY_settings['ink_px'] (12.73 px at 1920).
"""
import bpy

AOV_INK = 'ds_ink'     # 1 on ink-coloured surfaces (hull, crease tubes, face lines, black parts)
AOV_LINE = 'ds_line'   # 1 on objects whose outline is on
AOV_CHAR = 'ds_char'   # 1 on characters: their own drawing stays as designed (no new inner lines)
AOV_PART = 'ds_part'   # an id per separate part (a cushion, a cup, a table top); a character is one part
INK_MODS = ('DS Ink', 'DSL Ink')
DEPTH_STEP = 0.03      # a part 4% nearer than what's behind it gets a line
TAG = 'ds_inklines'
STEP_ON = 0.0   # depth-step lines off: on wide lenses a wall seen edge-on fills with ink; seams cover parts
DEBUG = {}   # the intermediate masks, for tests


def _luma(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _is_ink(m):
    return _luma(m.diffuse_color) < 0.05


def _outlined(ob):
    return any(md.type == 'NODES' and md.name in INK_MODS and md.show_render for md in ob.modifiers)


def wanted(shot=None, scene=None):
    if shot is not None and shot.get('inkLines') is False:
        return False
    scene = scene or bpy.context.scene
    if scene.render.engine == 'BLENDER_WORKBENCH':
        return False
    return any(ob.type == 'MESH' and not ob.hide_render and _outlined(ob) for ob in scene.objects)


def tag_materials(scene):
    """AOV outputs on every material the shot uses: is this ink, and is the object outlined."""
    mats, inks = set(), set()
    for ob in scene.objects:
        if ob.type != 'MESH' or ob.hide_render:
            continue
        # an outlined object, or a black part of a character (its parent or rig has the ink)
        ob['ds_line'] = 1.0 if _outlined(ob) else 0.0
        ob['ds_char'] = 1.0 if _is_character(ob) else 0.0
        rig = _rig(ob)
        # whole numbers below 2048: render passes may be stored as half floats
        ob['ds_oid'] = float(100 * (_hash(rig.name if rig else ob.name) % 19))
        if rig is None:
            try:
                mark_parts(ob)
            except Exception as e:   # no part ids: the object is still one part
                print('ink lines: parts skipped on %s: %s' % (ob.name, e))
        for s in ob.material_slots:
            if s.material is not None:
                mats.add(s.material)
        for md in ob.modifiers:
            if md.type == 'NODES' and md.node_group is not None:
                for v in _gn_materials(md):
                    mats.add(v)
                    if md.name in INK_MODS or md.name == 'DS Face':
                        inks.add(v)   # the hull and line materials are ink whatever their viewport colour
    for m in mats:
        if not m.use_nodes:
            m.use_nodes = True
        nt = m.node_tree
        if any(n.get(TAG) for n in nt.nodes):
            continue
        a = nt.nodes.new('ShaderNodeOutputAOV')
        a.aov_name = AOV_INK
        a.inputs['Value'].default_value = 1.0 if (m in inks or _is_ink(m)) else 0.0
        a[TAG] = 1
        b = nt.nodes.new('ShaderNodeOutputAOV')
        b.aov_name = AOV_LINE
        b[TAG] = 1
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_type = 'OBJECT'
        at.attribute_name = 'ds_line'
        at[TAG] = 1
        nt.links.new(at.outputs['Fac'], b.inputs['Value'])
        c = nt.nodes.new('ShaderNodeOutputAOV')
        c.aov_name = AOV_CHAR
        c[TAG] = 1
        ac = nt.nodes.new('ShaderNodeAttribute')
        ac.attribute_type = 'OBJECT'
        ac.attribute_name = 'ds_char'
        ac[TAG] = 1
        nt.links.new(ac.outputs['Fac'], c.inputs['Value'])
        d = nt.nodes.new('ShaderNodeOutputAOV')
        d.aov_name = AOV_PART
        d[TAG] = 1
        pg = nt.nodes.new('ShaderNodeAttribute')
        pg.attribute_type = 'GEOMETRY'
        pg.attribute_name = 'ds_part'
        pg[TAG] = 1
        po = nt.nodes.new('ShaderNodeAttribute')
        po.attribute_type = 'OBJECT'
        po.attribute_name = 'ds_oid'
        po[TAG] = 1
        # an object too small on screen for detail (DSL Ink's ds_coarse) is a single part
        co = nt.nodes.new('ShaderNodeAttribute')
        co.attribute_type = 'GEOMETRY'
        co.attribute_name = 'ds_coarse'
        co[TAG] = 1
        keep = nt.nodes.new('ShaderNodeMath')
        keep.operation = 'SUBTRACT'
        keep.inputs[0].default_value = 1.0
        keep[TAG] = 1
        nt.links.new(co.outputs['Fac'], keep.inputs[1])
        fine = nt.nodes.new('ShaderNodeMath')
        fine.operation = 'MULTIPLY'
        fine[TAG] = 1
        nt.links.new(pg.outputs['Fac'], fine.inputs[0])
        nt.links.new(keep.outputs[0], fine.inputs[1])
        add = nt.nodes.new('ShaderNodeMath')
        add.operation = 'ADD'
        add[TAG] = 1
        nt.links.new(fine.outputs[0], add.inputs[0])
        nt.links.new(po.outputs['Fac'], add.inputs[1])
        nt.links.new(add.outputs[0], d.inputs['Value'])
        for n in (a, b, at, c, ac, d, pg, po, add, co, keep, fine):
            n.location = (-900, -900)
    return len(mats)


def _hash(t):
    h = 2166136261
    for ch in t.encode():
        h = ((h ^ ch) * 16777619) & 0xffffffff
    return h


def _rig(ob):
    p = ob
    while p is not None:
        if p.type == 'ARMATURE':
            return p
        p = p.parent
    return ob.find_armature()


def _flat_regions(me, angle=30.0):
    """a room shell's faces grouped across smooth edges only: a sharp corner (floor to wall,
    wall to wall) splits them, a curved cove or backdrop does not"""
    import bmesh
    import math
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    lim = math.radians(angle)
    reg = [-1] * len(bm.faces)
    n = 0
    for f0 in bm.faces:
        if reg[f0.index] >= 0:
            continue
        reg[f0.index] = n
        stack = [f0]
        while stack:
            f = stack.pop()
            for e in f.edges:
                lf = e.link_faces
                if len(lf) != 2 or e.calc_face_angle(0.0) > lim:
                    continue
                for g in lf:
                    if reg[g.index] < 0:
                        reg[g.index] = n
                        stack.append(g)
        n += 1
    bm.free()
    return reg


def _shell_sides(me):
    """floor, ceiling or which wall each face of a room shell is; a smooth cove or curved
    backdrop takes the side most of its faces have, so it never gets a line across it"""
    import math
    from collections import Counter

    def side(n):
        if abs(n.z) >= 0.7:
            return 1 if n.z > 0 else 2
        return 3 + int(round(math.atan2(n.y, n.x) / (math.pi / 2))) % 4
    reg = _flat_regions(me)
    sides = [side(p.normal) for p in me.polygons]
    votes = {}
    for r, sd in zip(reg, sides):
        votes.setdefault(r, Counter())[sd] += 1
    pick = {r: c.most_common(1)[0][0] for r, c in votes.items()}
    return [pick[r] for r in reg]


def mark_parts(ob):
    """a face attribute ds_part: one value per connected piece of the mesh, so a cushion,
    a pillow or the cup on a table each meet their neighbours along a line"""
    me = ob.data
    if me.get('ds_parts') is not None and 'ds_part' in me.attributes:
        return me['ds_parts']
    nv = len(me.vertices)
    parent = list(range(nv))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in me.edges:
        a, b = find(e.vertices[0]), find(e.vertices[1])
        if a != b:
            parent[a] = b
    roots = {}
    vals = []
    shell = bool(ob.get('dsl_shell'))
    walls = _shell_sides(me) if shell else None
    for poly in me.polygons:
        # a piece, a colour on it, and for a room shell the floor, walls and ceiling apart,
        # so the floor meets each wall along a line
        # a room shell is keyed by side alone (floor, ceiling, each wall): a wall built from
        # many strips is one part, so a corner seen edge-on can't fill up with seams
        r = ('shell', walls[poly.index]) if shell else (find(poly.vertices[0]), poly.material_index)
        if r not in roots:
            roots[r] = len(roots)
        vals.append(float(1 + (roots[r] * 37) % 97))
    a = me.attributes.get('ds_part')
    if a is not None:
        me.attributes.remove(a)
    # on face corners, not faces: a face value can reach the shader blended through shared
    # vertices (a big wall then shades from one id to the next); corners stay flat per face
    per_corner = [0.0] * len(me.loops)
    for poly, v in zip(me.polygons, vals):
        for li in poly.loop_indices:
            per_corner[li] = v
    a = me.attributes.new('ds_part', 'FLOAT', 'CORNER')
    a.data.foreach_set('value', per_corner)
    me['ds_parts'] = len(roots)
    return len(roots)


def _is_character(ob):
    p = ob
    while p is not None:
        if p.type == 'ARMATURE':
            return True
        p = p.parent
    return ob.find_armature() is not None or ob.name.startswith(('BUNNY_', 'KOALA_', 'FROG_'))


def _gn_materials(md):
    """the materials a geometry-nodes modifier is given (ID properties up to 5.1,
    mod.properties.inputs on 5.2)"""
    out = []
    try:
        import compat
        ids = [it.identifier for it in md.node_group.interface.items_tree
               if getattr(it, 'in_out', None) == 'INPUT' and getattr(it, 'socket_type', '') == 'NodeSocketMaterial']
        for i in ids:
            v = compat.gn_get(md, i)
            if isinstance(v, bpy.types.Material):
                out.append(v)
    except Exception:
        pass
    return out


def stroke_px(scene=None):
    scene = scene or bpy.context.scene
    r = scene.render
    s = bpy.data.objects.get('BUNNY_settings')
    ink = float(s['ink_px']) if s is not None and 'ink_px' in s.keys() else 12.73
    return max(1.0, ink * max(r.resolution_x, r.resolution_y) * r.resolution_percentage / 100.0 / 1920.0)


class _T:
    """compositor nodes by role, for Blender 4.x (CompositorNode*) and 5.x (shared nodes)"""
    def __init__(self, tree):
        self.t = tree
        self.N = tree.nodes
        self.L = tree.links

    def node(self, *kinds, **props):
        for k in kinds:
            try:
                n = self.N.new(k)
                break
            except RuntimeError:
                continue
        else:
            raise RuntimeError('no compositor node of ' + ', '.join(kinds))
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def math(self, op, a, b=None, clamp=False):
        n = self.node('CompositorNodeMath', 'ShaderNodeMath', operation=op)
        if hasattr(n, 'use_clamp'):
            n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.L.new(v, n.inputs[i])
        return n.outputs[0]

    def morph(self, src, dist):
        """max (dist > 0) or min (dist < 0) over a disc of |dist| pixels"""
        n = self.node('CompositorNodeDilateErode')
        _menu(n, 'mode', 'Type', 'DISTANCE')
        set_px(n, dist)
        self.L.new(src, n.inputs[0])
        n[TAG] = 1
        return n


def _menu(n, prop, sock, value):
    """a node option: a property in 4.x, a menu socket in 5.x"""
    if hasattr(n, prop):
        setattr(n, prop, value)
        return
    import re
    s = n.inputs[sock]
    try:
        s.default_value = value
        return
    except (TypeError, ValueError) as e:
        items = re.findall(r"'([^']*)'", str(e).split('not found in', 1)[-1])
    key = re.sub(r'[^a-z]', '', value.lower())
    s.default_value = next(i for i in items if re.sub(r'[^a-z]', '', i.lower()).startswith(key))


def set_px(n, dist, frame=None):
    """a Dilate/Erode's signed size, optionally keyed at a frame"""
    v = int(round(dist))
    if hasattr(n, 'distance'):
        n.distance = v
        if frame is not None:
            n.keyframe_insert('distance', frame=frame)
    else:
        n.inputs['Size'].default_value = v
        if frame is not None:
            n.inputs['Size'].keyframe_insert('default_value', frame=frame)


def _tree(scene):
    if hasattr(scene, 'compositing_node_group'):          # Blender 5.x
        g = scene.compositing_node_group
        if g is None:
            g = bpy.data.node_groups.new('DS Ink Lines', 'CompositorNodeTree')
            scene.compositing_node_group = g
        return g
    scene.use_nodes = True
    return scene.node_tree


def build(scene, px):
    vl = scene.view_layers[0]
    vl.use_pass_z = True
    for name in (AOV_INK, AOV_LINE, AOV_CHAR, AOV_PART):
        if name not in [a.name for a in vl.aovs]:
            a = vl.aovs.add()
            a.name = name
            a.type = 'VALUE'
    tree = _tree(scene)
    T = _T(tree)
    rl = next((n for n in tree.nodes if n.bl_idname == 'CompositorNodeRLayers'), None) or T.node('CompositorNodeRLayers')
    out_sock = None
    comp = next((n for n in tree.nodes if n.bl_idname == 'CompositorNodeComposite'), None)
    if comp is None:
        try:
            comp = T.node('CompositorNodeComposite')
        except RuntimeError:
            comp = T.node('NodeGroupOutput')
            if not tree.interface.items_tree:
                tree.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    for l in list(comp.inputs[0].links):
        tree.links.remove(l)
    image = rl.outputs['Image']
    depth = rl.outputs['Depth']
    ink = rl.outputs[AOV_INK]
    line = rl.outputs[AOV_LINE]
    char = rl.outputs[AOV_CHAR]
    r = max(1, int(round(px)))
    # antialiased AOVs: any trace of ink or of a switched-off outline counts
    inkm = T.math('GREATER_THAN', ink, 0.01)
    noline = T.math('LESS_THAN', line, 0.99)
    charm = T.math('GREATER_THAN', char, 0.01)
    # ---- depth steps: the nearest outlined, non-ink surface within one stroke
    block = T.math('ADD', inkm, noline, clamp=True)
    # sentinels stay small: the compositor's morphology misbehaves on huge values
    depth = T.math('MINIMUM', depth, 1000.0)
    dprime = T.math('ADD', depth, T.math('MULTIPLY', block, 4000.0))
    near = T.morph(dprime, -r)
    near['role'] = 'near'
    step = T.math('DIVIDE', T.math('SUBTRACT', depth, near.outputs[0]), T.math('MAXIMUM', depth, 1e-4))
    dline = T.math('GREATER_THAN', step, DEPTH_STEP)
    # a character's own parts overlapping (ears over the head) keep Bunny's approved drawing
    dline = T.math('MULTIPLY', dline, T.math('SUBTRACT', 1.0, charm))
    # ---- part meets part: a cup on a table, a pillow on the back, Bunny on the sofa. A line
    # one stroke wide is centred on the seam; within half a stroke of visible ink it stays off,
    # so where the hull already shows nothing doubles, and where the hull is hidden the seam reads
    part = rl.outputs[AOV_PART]
    h = max(1, r // 2)
    # ink (the hull, lines, face drawings) takes no part, nor does the pixel round it, whose
    # part value is blended with the line's
    inkx = T.morph(inkm, 1).outputs[0]
    pmax = T.morph(T.math('SUBTRACT', part, T.math('MULTIPLY', inkx, 4000.0)), h)
    pmin = T.morph(T.math('ADD', part, T.math('MULTIPLY', inkx, 4000.0)), -h)
    pmax['role'] = 'half'
    pmin['role'] = 'nhalf'
    seam = T.math('GREATER_THAN', T.math('SUBTRACT', pmax.outputs[0], pmin.outputs[0]), 0.5)
    by_ink = T.morph(inkm, h)
    by_ink['role'] = 'half1'
    seam = T.math('MULTIPLY', seam, T.math('SUBTRACT', 1.0, by_ink.outputs[0], clamp=True))
    seam = T.math('MULTIPLY', seam, T.math('SUBTRACT', 1.0, noline))
    # never painted onto a character: Bunny's feet on a rug get their line on the rug's side
    seam = T.math('MULTIPLY', seam, T.math('SUBTRACT', 1.0, charm))
    DEBUG.update(dline=dline, seam=seam, pmax=pmax.outputs[0], pmin=pmin.outputs[0], part=part, inkm=inkm)
    lines = T.math('MAXIMUM', T.math('MULTIPLY', dline, STEP_ON), seam)
    # drop slivers thinner than a third of a stroke (what's left of a seam beside the hull)
    k = max(1, r // 6)
    lines = T.morph(T.morph(lines, -k).outputs[0], k).outputs[0]
    lines = T.math('MULTIPLY', lines, T.math('SUBTRACT', 1.0, inkm))
    soft = T.node('CompositorNodeBlur')
    _menu(soft, 'filter_type', 'Type', 'GAUSS')
    if hasattr(soft, 'size_x'):
        soft.size_x = soft.size_y = 1
    else:
        soft.inputs['Size'].default_value = (1, 1)
    T.L.new(lines, soft.inputs[0])
    mix = T.node('CompositorNodeMixRGB', 'ShaderNodeMix', blend_type='MIX')
    if mix.bl_idname == 'ShaderNodeMix':
        mix.data_type = 'RGBA'
        fac, a, b, o = mix.inputs[0], mix.inputs[6], mix.inputs[7], mix.outputs[2]
    else:
        fac, a, b, o = mix.inputs[0], mix.inputs[1], mix.inputs[2], mix.outputs[0]
    T.L.new(soft.outputs[0], fac)
    T.L.new(image, a)
    b.default_value = ink_rgba()
    out_sock = o
    if hasattr(mix, 'use_alpha'):
        mix.use_alpha = False
    T.L.new(out_sock, comp.inputs[0])
    tree[TAG] = r
    return r


def ink_rgba():
    h = '1F1F1D'
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, 1.0)


def _widths(scene, ink):
    k = max(scene.render.resolution_x, scene.render.resolution_y) * scene.render.resolution_percentage / 100.0 / 1920.0
    r = max(1, int(round(ink * k)))
    h = max(1, r // 2)
    return {'near': -r, 'half': h, 'nhalf': -h, 'half1': h}


def _drive(scene, tree):
    """when ink follows the camera (ink_px is keyed), the line widths are keyed to match.
    Keys, not drivers: a Python driver on the compositor keeps Blender from quitting."""
    st = bpy.data.objects.get('BUNNY_settings')
    ad = st.animation_data if st is not None else None
    fc = next((f for f in (ad.action.fcurves if ad and ad.action and hasattr(ad.action, 'fcurves') else [])
               if f.data_path == '["ink_px"]'), None)
    if fc is None:
        return 0
    nodes = [n for n in tree.nodes if n.get('role') in ('near', 'half', 'nhalf', 'half1')]
    last = None
    for f in range(scene.frame_start, scene.frame_end + 1):
        w = _widths(scene, fc.evaluate(f))
        if w == last:
            continue
        for n in nodes:
            set_px(n, w[n['role']], frame=f)
        last = w
    return len(nodes)


def apply(shot, log=print, scene=None):
    scene = scene or bpy.context.scene
    if not wanted(shot, scene):
        log('ink lines: off (no outline in this shot)')
        return None
    n = tag_materials(scene)
    try:
        r = build(scene, stroke_px(scene))
    except Exception as e:  # a line pass never stops a render: the hull alone still draws
        log('ink lines: skipped (%s)' % e)
        return None
    try:
        _drive(scene, _tree(scene))
    except Exception as e:   # without drivers the width and rim test stay as built
        log('ink lines: width keys skipped (%s)' % e)
    log('ink lines: on, %d px, %d materials' % (r, n))
    return r
