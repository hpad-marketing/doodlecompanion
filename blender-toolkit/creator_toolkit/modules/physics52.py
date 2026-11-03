"""Ropes, cables, strings of lights, cloth and hair presets on Blender 5.2's XPBD node solver.

The solvers are Blender's own bundled node assets (Cloth Dynamics, Hair Dynamics). We wrap them so
the simulation runs in world space: things swing when the character or prop moves."""
import math
import os
import bmesh
import bpy
from mathutils import Matrix, Vector
from . import _util

LABEL, ICON, GROUP = 'Ropes, cloth + hair', 'MOD_CLOTH', 'Animation'
ASSET = os.path.join('assets', 'nodes', 'geometry_nodes_dynamics_assets.blend')

ROPES = {
    'ROPE': ('Rope', 0.03, 8, '#7A6A4F', 0.25),
    'CABLE': ('Cable', 0.012, 6, '#1F1F1D', 0.15),
    'STRING': ('String', 0.004, 4, '#F2E6CF', 0.1),
    'LIGHTS': ('String of lights', 0.006, 4, '#1F1F1D', 0.2),
}
CLOTHS = {
    'CAPE': ('Cape', 0.9, 1.2, 'TOP'),
    'SCARF': ('Scarf', 0.18, 1.1, 'TOP'),
    'FLAG': ('Flag', 1.2, 0.8, 'LEFT'),
    'RIBBON': ('Ribbon', 0.06, 0.9, 'TOP'),
}
HAIRS = {
    'PONYTAIL': ('Ponytail', 14, 0.45, 0.025, 0.06),
    'TUFT': ('Grass tuft', 12, 0.25, 0.006, 0.05),
    'ANTENNA': ('Antenna', 1, 0.35, 0.01, 0.0),
    'FRINGE': ('Fringe', 9, 0.18, 0.012, 0.12),
}


def available():
    return bpy.app.version >= (5, 2, 0) and os.path.exists(_asset_path())


def _asset_path():
    return os.path.join(bpy.utils.system_resource('DATAFILES'), ASSET)


def solver(name):
    g = bpy.data.node_groups.get(name)
    if g:
        return g
    with bpy.data.libraries.load(_asset_path(), link=False) as (src, dst):
        dst.node_groups = [name]
    return dst.node_groups[0]


def _mat(name, hexcol, emit=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    col = (*_util.hex_to_linear(hexcol), 1)
    b.inputs['Base Color'].default_value = col
    b.inputs['Roughness'].default_value = 0.6
    if emit:
        b.inputs['Emission Color'].default_value = col
        b.inputs['Emission Strength'].default_value = emit
    return m


def wrapper(kind):
    """Modifier group: world-space input -> solver -> back to object space, pin attribute 'ctk_pin'."""
    name = 'CTK %s sim' % kind.title()
    g = bpy.data.node_groups.get(name)
    if g:
        return g
    g = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    g.is_modifier = True
    io = g.interface
    io.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    io.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    for nm, t, dv, lo, hi in (('Stiffness', 'NodeSocketFloat', 0.3, 0.0, 1.0),
                              ('Stretch', 'NodeSocketFloat', 0.0, 0.0, 1.0),
                              ('Floppiness', 'NodeSocketFloat', 3.0, 0.0, 50.0),
                              ('Gravity', 'NodeSocketFloat', 1.0, 0.0, 5.0),
                              ('Quality', 'NodeSocketInt', 6, 1, 40)):
        s = io.new_socket(nm, in_out='INPUT', socket_type=t)
        s.default_value, s.min_value, s.max_value = dv, lo, hi
    N, L = g.nodes, g.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    so = N.new('GeometryNodeSelfObject')
    oi = N.new('GeometryNodeObjectInfo')
    L.new(so.outputs[0], oi.inputs['Object'])
    t1, t2 = N.new('GeometryNodeTransform'), N.new('GeometryNodeTransform')
    for t in (t1, t2):
        if hasattr(t, 'mode'):
            t.mode = 'MATRIX'
        else:
            t.inputs['Mode'].default_value = 'Matrix'
    inv = N.new('FunctionNodeInvertMatrix')
    L.new(oi.outputs['Transform'], t1.inputs['Transform'])
    L.new(oi.outputs['Transform'], inv.inputs[0])
    L.new(inv.outputs[0], t2.inputs['Transform'])
    L.new(gi.outputs['Geometry'], t1.inputs['Geometry'])
    sv = N.new('GeometryNodeGroup')
    grav = N.new('ShaderNodeVectorMath')
    grav.operation = 'SCALE'
    grav.inputs[0].default_value = (0, 0, -9.81)
    L.new(gi.outputs['Gravity'], grav.inputs['Scale'])
    if kind == 'HAIR':
        sv.node_tree = solver('Hair Dynamics')
        sv.inputs['Mode'].default_value = 'Physics (Experimental)'
        L.new(t1.outputs[0], sv.inputs['Hair'])
        L.new(gi.outputs['Stiffness'], sv.inputs['Bendiness'])
        L.new(gi.outputs['Stretch'], sv.inputs['Stretchiness'])
        L.new(gi.outputs['Floppiness'], sv.inputs['Linear'])
        L.new(gi.outputs['Quality'], sv.inputs['Substeps'])
        out = sv.outputs['Hair']
    else:
        sv.node_tree = solver('Cloth Dynamics (Experimental)')
        na = N.new('GeometryNodeInputNamedAttribute')
        na.data_type = 'FLOAT'
        na.inputs['Name'].default_value = 'ctk_pin'
        L.new(t1.outputs[0], sv.inputs['Geometry'])
        L.new(na.outputs['Attribute'], sv.inputs['Pin Group'])
        L.new(gi.outputs['Stiffness'], sv.inputs['Bendiness'])
        L.new(gi.outputs['Stretch'], sv.inputs['Stretchiness'])
        L.new(gi.outputs['Floppiness'], sv.inputs['Linear Damping'])
        L.new(gi.outputs['Quality'], sv.inputs['Substeps'])
        out = sv.outputs['Geometry']
    gv = [s for s in sv.inputs if s.name == 'Gravity' and s.type == 'VECTOR']
    if gv:
        L.new(grav.outputs[0], gv[0])
    L.new(out, t2.inputs['Geometry'])
    L.new(t2.outputs[0], go.inputs['Geometry'])
    return g


def _add_sim(obj, kind, **vals):
    from ._nodes import set_input
    m = obj.modifiers.new('CTK %s sim' % kind.title(), 'NODES')
    m.node_group = wrapper(kind)
    for k, v in vals.items():
        set_input(m, k, v)
    return m


def _pin_attr(me, idx):
    a = me.attributes.get('ctk_pin') or me.attributes.new('ctk_pin', 'FLOAT', 'POINT')
    for i in idx:
        a.data[i].value = 1.0


def _hook(obj, target, idx, name):
    vg = obj.vertex_groups.new(name=name)
    vg.add(list(idx), 1.0, 'REPLACE')
    h = obj.modifiers.new('Hook ' + target.name, 'HOOK')
    h.object = target
    h.vertex_group = vg.name
    h.matrix_inverse = (obj.matrix_world.inverted() @ target.matrix_world).inverted()
    return h


def make_rope(context, a, b, kind='ROPE', sag=None, segments=32):
    label, r, sides, col, dsag = ROPES[kind]
    sag = dsag if sag is None else sag
    context.view_layer.update()
    pa, pb = a.matrix_world.translation.copy(), b.matrix_world.translation.copy()
    length = (pb - pa).length
    bm = bmesh.new()
    rings = []
    d = (pb - pa).normalized() if length > 1e-6 else Vector((1, 0, 0))
    u = d.cross(Vector((0, 0, 1)))
    if u.length < 1e-4:
        u = d.cross(Vector((0, 1, 0)))
    u.normalize()
    v = d.cross(u)
    for i in range(segments + 1):
        t = i / segments
        c = pa.lerp(pb, t)
        c.z -= sag * length * math.sin(math.pi * t)
        rings.append([bm.verts.new(c + r * (math.cos(k * math.tau / sides) * u + math.sin(k * math.tau / sides) * v))
                      for k in range(sides)])
    for i in range(segments):
        for k in range(sides):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % sides], rings[i + 1][(k + 1) % sides], rings[i + 1][k]))
    me = bpy.data.meshes.new(label)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(label, me)
    context.scene.collection.objects.link(ob)
    first = range(sides)
    last = range(segments * sides, (segments + 1) * sides)
    _pin_attr(me, list(first) + list(last))
    _hook(ob, a, first, 'pin_start')
    _hook(ob, b, last, 'pin_end')
    me.materials.append(_mat('CTK ' + label, col))
    _add_sim(ob, 'CLOTH', Stiffness=0.05 if kind != 'ROPE' else 0.2, Quality=6)
    if kind == 'LIGHTS':
        _bulbs(ob, sides, segments)
    ob['ctk_rope'] = kind
    return ob


def _bulbs(ob, sides, segments, every=3):
    """Glowing bulbs hanging on every few rings of a string."""
    me = ob.data
    a = me.attributes.new('ctk_bulb', 'BOOLEAN', 'POINT')
    for i in range(every, segments, every):
        a.data[i * sides].value = True
    g = bpy.data.node_groups.get('CTK Bulbs')
    if not g:
        from ._nodes import Tree, O, I
        t = Tree('CTK Bulbs')
        t.geo_io()
        t.socket('Bulb size', 'INPUT', 'NodeSocketFloat', 0.035, 0.0, 1.0)
        t.socket('Bulb material', 'INPUT', 'NodeSocketMaterial')
        na = t.n('GeometryNodeInputNamedAttribute', data_type='BOOLEAN')
        I(na, 'Name').default_value = 'ctk_bulb'
        mp = t.n('GeometryNodeMeshToPoints')
        t.link(t.i('Geometry'), I(mp, 'Mesh'))
        t.link(O(na, 'Attribute'), I(mp, 'Selection'))
        ico = t.n('GeometryNodeMeshUVSphere')
        I(ico, 'Segments').default_value = 10
        I(ico, 'Rings').default_value = 6
        t.link(t.i('Bulb size'), I(ico, 'Radius'))
        sm = t.n('GeometryNodeSetMaterial')
        t.link(O(ico, 'Mesh'), I(sm, 'Geometry'))
        t.link(t.i('Bulb material'), I(sm, 'Material'))
        inst = t.n('GeometryNodeInstanceOnPoints')
        t.link(O(mp, 'Points'), I(inst, 'Points'))
        t.link(O(sm, 'Geometry'), I(inst, 'Instance'))
        j = t.n('GeometryNodeJoinGeometry')
        t.link(t.i('Geometry'), I(j, 'Geometry'))
        t.link(O(inst, 'Instances'), I(j, 'Geometry'))
        t.out(O(j, 'Geometry'))
        g = t.tree
    m = ob.modifiers.new('CTK Bulbs', 'NODES')
    m.node_group = g
    from ._nodes import set_input
    set_input(m, 'Bulb material', _mat('CTK Bulb glow', '#E0A64B', emit=6.0))


def make_cloth(context, target, kind='CAPE', res=14):
    label, w, h, pin = CLOTHS[kind]
    context.view_layer.update()
    dims = target.dimensions if target else Vector((1, 1, 1))
    scale = max(0.3, max(dims.x, dims.z) / 1.5) if target and target.type == 'MESH' else 1.0
    w, h = w * scale, h * scale
    nx, ny = max(2, int(res * w / max(w, h))), max(2, int(res * h / max(w, h)))
    if kind == 'RIBBON':
        nx = 2
    me = bpy.data.meshes.new(label)
    bm = bmesh.new()
    grid = [[bm.verts.new((-w / 2 + w * i / nx, 0, -h * j / ny)) for i in range(nx + 1)] for j in range(ny + 1)]
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(label, me)
    context.scene.collection.objects.link(ob)
    if target:
        top = target.matrix_world.translation.copy()
        if target.type == 'MESH':
            top.z += target.dimensions.z * (0.35 if kind in ('CAPE', 'SCARF') else 0.5)
            top.y += target.dimensions.y * (0.5 if kind == 'CAPE' else -0.5 if kind == 'SCARF' else 0)
        ob.location = top
    stride = nx + 1
    pins = list(range(stride)) if pin == 'TOP' else [j * stride for j in range(ny + 1)]
    _pin_attr(me, pins)
    if target:
        mw = ob.matrix_world.copy()
        ob.parent = target
        ob.matrix_parent_inverse = target.matrix_world.inverted()
        ob.matrix_world = mw
    me.materials.append(_mat('CTK ' + label, '#B5523B' if kind != 'FLAG' else '#E0A64B'))
    sol = ob.modifiers.new('Thickness', 'SOLIDIFY')
    sol.thickness = 0.01
    _add_sim(ob, 'CLOTH', Stiffness=0.02, Floppiness=1.0, Quality=5)
    ob.modifiers.move(ob.modifiers.find('Thickness'), len(ob.modifiers) - 1)
    return ob


def make_hair(context, target, kind='PONYTAIL', seed=0):
    import random
    rnd = random.Random(seed)
    label, n, length, radius, spread = HAIRS[kind]
    cv = bpy.data.hair_curves.new(label)
    pts = 10
    cv.add_curves([pts] * n)
    for ci, c in enumerate(cv.curves):
        a = rnd.uniform(0, math.tau)
        rr = spread * math.sqrt(rnd.random())
        base = Vector((rr * math.cos(a), rr * math.sin(a), 0))
        out = Vector((math.cos(a), math.sin(a), 0)) * (0.3 if kind == 'TUFT' else 0.05)
        ln = length * rnd.uniform(0.75, 1.1)
        down = -1 if kind in ('PONYTAIL', 'FRINGE') else 1
        for i, p in enumerate(c.points):
            t = i / (pts - 1)
            p.position = base + out * t * ln + Vector((0, 0, down * t * ln))
            p.radius = radius * (1 - 0.7 * t)
    ob = bpy.data.objects.new(label, cv)
    context.scene.collection.objects.link(ob)
    if target:
        context.view_layer.update()
        loc = target.matrix_world.translation.copy()
        if target.type == 'MESH':
            loc.z += target.dimensions.z * (0.5 if kind in ('ANTENNA', 'TUFT') else 0.2)
            loc.y += target.dimensions.y * (0.5 if kind == 'PONYTAIL' else -0.45 if kind == 'FRINGE' else 0)
        ob.location = loc
        mw = ob.matrix_world.copy()
        ob.parent = target
        ob.matrix_parent_inverse = target.matrix_world.inverted()
        ob.matrix_world = mw
    cv.materials.append(_mat('CTK Hair', '#1F1F1D' if kind != 'TUFT' else '#8FA67A'))
    _add_sim(ob, 'HAIR', Stiffness=0.6 if kind == 'ANTENNA' else 0.35, Floppiness=4.0, Quality=8)
    return ob


def sim_objects(context):
    return [o for o in context.selected_objects
            if any(m.type == 'NODES' and m.name.startswith('CTK ') and m.name.endswith(' sim') for m in o.modifiers)]


class _Needs52:
    @classmethod
    def poll(cls, context):
        return available()


class CTK_OT_rope(_Needs52, bpy.types.Operator):
    """Hang a rope, cable, string or string of lights between the two selected objects"""
    bl_idname = 'ctk.rope'
    bl_label = 'Rope between'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[(k, v[0], '') for k, v in ROPES.items()])
    sag: bpy.props.FloatProperty(name='Sag', default=-1.0, min=-1.0, max=1.0, description='-1 uses the preset')

    def execute(self, context):
        sel = [o for o in context.selected_objects]
        if len(sel) != 2:
            self.report({'ERROR'}, 'Select exactly two objects (the rope hangs between them)')
            return {'CANCELLED'}
        b = context.active_object if context.active_object in sel else sel[1]
        a = sel[0] if sel[0] is not b else sel[1]
        make_rope(context, a, b, self.kind, None if self.sag < 0 else self.sag)
        return {'FINISHED'}


class CTK_OT_cloth(_Needs52, bpy.types.Operator):
    """Add a cape, scarf, flag or ribbon that follows the active object and swings"""
    bl_idname = 'ctk.cloth_preset'
    bl_label = 'Cloth'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[(k, v[0], '') for k, v in CLOTHS.items()])

    def execute(self, context):
        make_cloth(context, context.active_object, self.kind)
        return {'FINISHED'}


class CTK_OT_hair(_Needs52, bpy.types.Operator):
    """Add a ponytail, grass tuft, antenna or fringe that follows the active object and bounces"""
    bl_idname = 'ctk.hair_preset'
    bl_label = 'Hair'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[(k, v[0], '') for k, v in HAIRS.items()])

    def execute(self, context):
        make_hair(context, context.active_object, self.kind)
        return {'FINISHED'}


class CTK_OT_sim_cache(bpy.types.Operator):
    """Bake (cache) or clear the simulation of the selected ropes, cloth and hair for smooth playback"""
    bl_idname = 'ctk.sim_cache'
    bl_label = 'Cache simulation'
    clear: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        if not sim_objects(context):
            self.report({'WARNING'}, 'Select ropes, cloth or hair first')
            return {'CANCELLED'}
        try:
            if self.clear:
                bpy.ops.object.simulation_nodes_cache_delete(selected=True)
            else:
                bpy.ops.object.simulation_nodes_cache_bake(selected=True)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


CLASSES = (CTK_OT_rope, CTK_OT_cloth, CTK_OT_hair, CTK_OT_sim_cache)


def draw(layout, context):
    if not available():
        layout.label(text='Needs Blender 5.2 (node physics)', icon='INFO')
        return
    layout.label(text='Select 2 objects:')
    g = layout.grid_flow(columns=2, align=True)
    for k, v in ROPES.items():
        g.operator('ctk.rope', text=v[0]).kind = k
    layout.label(text='On the active object:')
    g = layout.grid_flow(columns=2, align=True)
    for k, v in CLOTHS.items():
        g.operator('ctk.cloth_preset', text=v[0]).kind = k
    for k, v in HAIRS.items():
        g.operator('ctk.hair_preset', text=v[0]).kind = k
    row = layout.row(align=True)
    row.operator('ctk.sim_cache', text='Cache', icon='FILE_CACHE').clear = False
    row.operator('ctk.sim_cache', text='Clear cache', icon='TRASH').clear = True
    o = context.active_object
    if o:
        from ._nodes import draw_modifier_inputs
        for m in o.modifiers:
            if m.type == 'NODES' and m.name.endswith(' sim') and m.name.startswith('CTK '):
                draw_modifier_inputs(layout.box(), m)
    layout.label(text='CPU: preview at low Quality, cache before rendering', icon='INFO')
