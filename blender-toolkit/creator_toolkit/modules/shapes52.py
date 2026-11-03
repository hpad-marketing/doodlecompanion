"""Blob + clay modeler, toon smoke and puffs, soft-toy rounding.

Blobs and smoke use Blender 5.2's SDF grid nodes. Soft-toy rounding uses the 5.2 Mesh Bevel node
(4.x falls back to the Bevel + Subdivision modifiers)."""
import math
import bpy
from . import _util
from ._nodes import Tree, O, I, set_input, draw_modifier_inputs

LABEL, ICON, GROUP = 'Blobs, smoke + soft toys', 'META_BALL', 'Procedural & 2D'
SMOKES = [('TRAIL', 'Smoke trail', 'A rising column of puffs'), ('STEAM', 'Steam', 'Thin wisps from a cup or pot'),
          ('PUFF', 'Dust puff', 'A burst that grows and fades (landings, pops)'),
          ('CLOUD', 'Cartoon cloud', 'A slow drifting cloud')]
SMOKE_PRESETS = {  # count, life (s), height, r0, r1, spread, drift
    'TRAIL': (14, 3.0, 2.5, 0.15, 0.45, 0.1, 0.4),
    'STEAM': (10, 2.5, 1.2, 0.05, 0.18, 0.04, 0.25),
    'PUFF': (12, 0.9, 0.25, 0.1, 0.4, 0.9, 0.1),
    'CLOUD': (16, 12.0, 0.0, 0.5, 0.6, 1.4, 0.15),
}


def sdf_available():
    return hasattr(bpy.types, 'GeometryNodeSDFGridFillet') and hasattr(bpy.types, 'GeometryNodeMeshToSDFGrid')


def bevel_available():
    return hasattr(bpy.types, 'GeometryNodeMeshBevel')


def _m(t, op, a, b=None, c=None):
    n = t.n('ShaderNodeMath', operation=op)
    for k, v in ((0, a), (1, b), (2, c)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[k].default_value = v
        else:
            t.link(v, n.inputs[k])
    return n.outputs[0]


def toon_material(name, hexcol):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    dif = nt.nodes.new('ShaderNodeBsdfDiffuse')
    s2r = nt.nodes.new('ShaderNodeShaderToRGB')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'CONSTANT'
    lit = _util.hex_to_linear(hexcol)
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (*[c * 0.72 for c in lit], 1)
    els[1].position, els[1].color = 0.08, (*lit, 1)
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(dif.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs['Color'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], em.inputs['Color'])
    nt.links.new(em.outputs[0], out.inputs['Surface'])
    return m


# ---------------------------------------------------------- blobs

def build_blob():
    t = Tree('CTK Blob')
    if not t.fresh:
        return t.tree
    t.socket('Geometry', 'INPUT', 'NodeSocketGeometry')
    t.socket('Geometry', 'OUTPUT', 'NodeSocketGeometry')
    t.socket('Parts', 'INPUT', 'NodeSocketCollection')
    t.socket('Detail', 'INPUT', 'NodeSocketFloat', 0.03, 0.004, 1.0)
    t.socket('Melt', 'INPUT', 'NodeSocketInt', 8, 0, 60)
    t.socket('Smooth', 'INPUT', 'NodeSocketInt', 1, 0, 20)
    t.socket('Puff', 'INPUT', 'NodeSocketFloat', 0.0, -1.0, 1.0)
    t.socket('Material', 'INPUT', 'NodeSocketMaterial')
    ci = t.n('GeometryNodeCollectionInfo', transform_space='RELATIVE')
    t.link(t.i('Parts'), I(ci, 'Collection'))
    real = t.n('GeometryNodeRealizeInstances')
    t.link(O(ci, 'Instances'), I(real, 'Geometry'))
    sdf = t.n('GeometryNodeMeshToSDFGrid')
    t.link(O(real, 'Geometry'), I(sdf, 'Mesh'))
    t.link(t.i('Detail'), I(sdf, 'Voxel Size'))
    I(sdf, 'Band Width').default_value = 6
    fil = t.n('GeometryNodeSDFGridFillet')
    t.link(O(sdf, 'SDF Grid'), I(fil, 'Grid'))
    t.link(t.i('Melt'), I(fil, 'Iterations'))
    mean = t.n('GeometryNodeSDFGridMean') if hasattr(bpy.types, 'GeometryNodeSDFGridMean') else None
    g = O(fil, 'Grid')
    if mean:
        t.link(g, I(mean, 'Grid'))
        t.link(t.i('Smooth'), I(mean, 'Iterations'))
        g = O(mean, 'Grid')
    off = t.n('GeometryNodeSDFGridOffset')
    t.link(g, I(off, 'Grid'))
    t.link(_m(t, 'MULTIPLY', t.i('Puff'), -1.0), I(off, 'Distance'))
    tm = t.n('GeometryNodeGridToMesh')
    t.link(O(off, 'Grid'), I(tm, 'Grid'))
    sm = t.n('GeometryNodeSetShadeSmooth')
    t.link(O(tm, 'Mesh'), I(sm, 'Geometry'))
    mat = t.n('GeometryNodeSetMaterial')
    t.link(O(sm, 'Geometry'), I(mat, 'Geometry'))
    t.link(t.i('Material'), I(mat, 'Material'))
    t.out(O(mat, 'Geometry'))
    return t.tree


def make_blob(context, parts):
    sc = context.scene
    coll = bpy.data.collections.new('Blob parts')
    sc.collection.children.link(coll)
    for o in parts:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        o.display_type = 'WIRE'
        o.hide_render = True
    me = bpy.data.meshes.new('Blob')
    blob = bpy.data.objects.new('Blob', me)
    sc.collection.objects.link(blob)
    m = blob.modifiers.new('CTK Blob', 'NODES')
    m.node_group = build_blob()
    set_input(m, 'Parts', coll)
    set_input(m, 'Material', toon_material('CTK Clay pink', '#E8A0A0'))
    blob['ctk_blob_parts'] = coll.name
    return blob


# ---------------------------------------------------------- toon smoke

def build_smoke():
    t = Tree('CTK Toon Smoke')
    if not t.fresh:
        return t.tree
    t.socket('Geometry', 'INPUT', 'NodeSocketGeometry')
    t.socket('Geometry', 'OUTPUT', 'NodeSocketGeometry')
    for nm, typ, dv, lo, hi in (('Puffs', 'NodeSocketInt', 14, 1, 400), ('Life (seconds)', 'NodeSocketFloat', 3.0, 0.1, 60.0),
                                ('Rise', 'NodeSocketFloat', 2.5, -10.0, 50.0), ('Start size', 'NodeSocketFloat', 0.15, 0.0, 10.0),
                                ('End size', 'NodeSocketFloat', 0.45, 0.0, 10.0), ('Spread', 'NodeSocketFloat', 0.1, 0.0, 10.0),
                                ('Swirl', 'NodeSocketFloat', 0.4, 0.0, 10.0), ('Detail', 'NodeSocketFloat', 0.04, 0.005, 1.0),
                                ('Seed', 'NodeSocketInt', 0, 0, 10000)):
        t.socket(nm, 'INPUT', typ, dv, lo, hi)
    t.socket('Material', 'INPUT', 'NodeSocketMaterial')
    pts = t.n('GeometryNodePoints')
    t.link(t.i('Puffs'), I(pts, 'Count'))
    idx = t.n('GeometryNodeInputIndex')
    st = t.n('GeometryNodeInputSceneTime')
    # age 0..1, each puff offset in time so they leave one after another
    phase = _m(t, 'DIVIDE', O(idx, 'Index'), t.i('Puffs'))
    age = _m(t, 'FRACT', _m(t, 'ADD', _m(t, 'DIVIDE', O(st, 'Seconds'), t.i('Life (seconds)')), phase))
    rnd = t.n('FunctionNodeRandomValue', data_type='FLOAT_VECTOR')
    I(rnd, 'Min', 'VECTOR').default_value = (-1, -1, -1)
    I(rnd, 'Max', 'VECTOR').default_value = (1, 1, 1)
    t.link(t.i('Seed'), I(rnd, 'Seed'))
    spread = t.n('ShaderNodeVectorMath', operation='SCALE')
    t.link(O(rnd, 'Value', 'VECTOR'), spread.inputs[0])
    t.link(_m(t, 'MULTIPLY', t.i('Spread'), _m(t, 'ADD', 0.3, age)), I(spread, 'Scale'))
    up = t.n('ShaderNodeCombineXYZ')
    t.link(_m(t, 'MULTIPLY', age, t.i('Rise')), I(up, 'Z'))
    # swirl: drifting noise
    nz = t.n('ShaderNodeTexNoise', noise_dimensions='4D')
    t.link(O(up, 'Vector'), I(nz, 'Vector'))
    t.link(_m(t, 'ADD', O(st, 'Seconds'), _m(t, 'MULTIPLY', O(idx, 'Index'), 3.7)), I(nz, 'W'))
    I(nz, 'Scale').default_value = 0.8
    cen = t.n('ShaderNodeVectorMath', operation='SUBTRACT')
    t.link(O(nz, 'Color'), cen.inputs[0])
    cen.inputs[1].default_value = (0.5, 0.5, 0.0)
    sw = t.n('ShaderNodeVectorMath', operation='SCALE')
    t.link(cen.outputs[0], sw.inputs[0])
    t.link(_m(t, 'MULTIPLY', t.i('Swirl'), age), I(sw, 'Scale'))
    a1 = t.n('ShaderNodeVectorMath', operation='ADD')
    t.link(spread.outputs[0], a1.inputs[0])
    t.link(O(up, 'Vector'), a1.inputs[1])
    a2 = t.n('ShaderNodeVectorMath', operation='ADD')
    t.link(a1.outputs[0], a2.inputs[0])
    t.link(sw.outputs[0], a2.inputs[1])
    t.link(a2.outputs[0], I(pts, 'Position'))
    # grows, then shrinks away at the end of its life
    size = _m(t, 'ADD', t.i('Start size'), _m(t, 'MULTIPLY', age, _m(t, 'SUBTRACT', t.i('End size'), t.i('Start size'))))
    fade = _m(t, 'SUBTRACT', 1.0, _m(t, 'POWER', age, 6.0))
    t.link(_m(t, 'MULTIPLY', size, fade), I(pts, 'Radius'))
    sdf = t.n('GeometryNodePointsToSDFGrid')
    t.link(O(pts, 'Points'), I(sdf, 'Points'))
    rad = t.n('GeometryNodeInputRadius')
    t.link(O(rad, 'Radius'), I(sdf, 'Radius'))
    t.link(t.i('Detail'), I(sdf, 'Voxel Size'))
    fil = t.n('GeometryNodeSDFGridFillet')
    t.link(O(sdf, 'SDF Grid'), I(fil, 'Grid'))
    I(fil, 'Iterations').default_value = 6
    tm = t.n('GeometryNodeGridToMesh')
    t.link(O(fil, 'Grid'), I(tm, 'Grid'))
    sm = t.n('GeometryNodeSetShadeSmooth')
    t.link(O(tm, 'Mesh'), I(sm, 'Geometry'))
    mat = t.n('GeometryNodeSetMaterial')
    t.link(O(sm, 'Geometry'), I(mat, 'Geometry'))
    t.link(t.i('Material'), I(mat, 'Material'))
    t.out(O(mat, 'Geometry'))
    return t.tree


def make_smoke(context, kind):
    me = bpy.data.meshes.new('Toon smoke')
    o = bpy.data.objects.new(dict((k, l) for k, l, _ in SMOKES)[kind], me)
    context.scene.collection.objects.link(o)
    src = context.active_object
    o.location = src.matrix_world.translation if src and src.select_get() else context.scene.cursor.location
    m = o.modifiers.new('CTK Toon smoke', 'NODES')
    m.node_group = build_smoke()
    n, life, rise, r0, r1, spread, swirl = SMOKE_PRESETS[kind]
    for k, v in (('Puffs', n), ('Life (seconds)', life), ('Rise', rise), ('Start size', r0), ('End size', r1),
                 ('Spread', spread), ('Swirl', swirl)):
        set_input(m, k, v)
    col = '#F2E6CF' if kind != 'CLOUD' else '#E8F1F2'
    set_input(m, 'Material', toon_material('CTK Toon ' + kind.title(), col))
    return o


# ---------------------------------------------------------- soft toy

def build_soft():
    t = Tree('CTK Soft Toy')
    if not t.fresh:
        return t.tree
    t.geo_io()
    t.socket('Roundness', 'INPUT', 'NodeSocketFloat', 0.08, 0.0, 10.0)
    t.socket('Smoothness', 'INPUT', 'NodeSocketInt', 4, 1, 16)
    t.socket('Puff', 'INPUT', 'NodeSocketFloat', 0.5, 0.0, 1.0)
    bv = t.n('GeometryNodeMeshBevel')
    t.link(t.i('Geometry'), I(bv, 'Mesh'))
    for nm in ('Affect Kind',):
        s = next((x for x in bv.inputs if x.name == nm), None)
        if s is not None:
            for cand in ('Edges', 'EDGES'):
                try:
                    s.default_value = cand
                    break
                except (TypeError, ValueError):
                    pass
    t.link(t.i('Roundness'), I(bv, 'Offset'))
    t.link(t.i('Smoothness'), I(bv, 'Segments'))
    t.link(t.i('Puff'), I(bv, 'Shape'))
    ss = t.n('GeometryNodeSetShadeSmooth')
    t.link(O(bv, 'Mesh'), I(ss, 'Geometry'))
    t.out(O(ss, 'Geometry'))
    return t.tree


def soft_toy(obj, roundness=None):
    size = max(obj.dimensions) or 1.0
    r = roundness if roundness is not None else size * 0.08
    if bevel_available():
        m = obj.modifiers.new('CTK Soft toy', 'NODES')
        m.node_group = build_soft()
        set_input(m, 'Roundness', r)
        return m
    b = obj.modifiers.new('CTK Soft toy', 'BEVEL')  # 4.x fallback, same look
    b.width = r
    b.segments = 4
    b.limit_method = 'ANGLE'
    b.profile = 0.6
    s = obj.modifiers.new('CTK Soft toy smooth', 'SUBSURF')
    s.levels = s.render_levels = 1
    for p in obj.data.polygons:
        p.use_smooth = True
    return b


# ---------------------------------------------------------- operators

class CTK_OT_blob(bpy.types.Operator):
    """Melt the selected shapes together like clay (they stay editable as parts)"""
    bl_idname = 'ctk.blob'
    bl_label = 'Make blob'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return sdf_available()

    def execute(self, context):
        parts = [o for o in context.selected_objects if o.type == 'MESH']
        if not parts:
            self.report({'ERROR'}, 'Select a few shapes (spheres, cubes, cylinders) to melt together')
            return {'CANCELLED'}
        b = make_blob(context, parts)
        for o in context.selected_objects:
            o.select_set(False)
        b.select_set(True)
        context.view_layer.objects.active = b
        return {'FINISHED'}


class CTK_OT_blob_apply(bpy.types.Operator):
    """Turn the blob into a normal mesh you can sculpt (removes the parts)"""
    bl_idname = 'ctk.blob_apply'
    bl_label = 'Make it a real mesh'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        o = context.active_object
        if not o or 'CTK Blob' not in o.modifiers:
            self.report({'ERROR'}, 'Select a blob')
            return {'CANCELLED'}
        dg = context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        o.modifiers.clear()
        old = o.data
        o.data = me
        bpy.data.meshes.remove(old)
        coll = bpy.data.collections.get(o.get('ctk_blob_parts', ''))
        if coll:
            for p in list(coll.objects):
                bpy.data.objects.remove(p)
            bpy.data.collections.remove(coll)
        return {'FINISHED'}


class CTK_OT_smoke(bpy.types.Operator):
    """Add looping toon smoke, steam, a dust puff or a cartoon cloud at the selection or cursor"""
    bl_idname = 'ctk.toon_smoke'
    bl_label = 'Toon smoke'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=SMOKES)

    @classmethod
    def poll(cls, context):
        return sdf_available()

    def execute(self, context):
        make_smoke(context, self.kind)
        return {'FINISHED'}


class CTK_OT_soft(bpy.types.Operator):
    """Round and puff the edges of the selected models like a plush or vinyl toy (non-destructive)"""
    bl_idname = 'ctk.soft_toy'
    bl_label = 'Soft toy'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type == 'MESH']
        if not obs:
            self.report({'ERROR'}, 'Select a model')
            return {'CANCELLED'}
        for o in obs:
            if not any(m.name.startswith('CTK Soft toy') for m in o.modifiers):
                soft_toy(o)
        return {'FINISHED'}


CLASSES = (CTK_OT_blob, CTK_OT_blob_apply, CTK_OT_smoke, CTK_OT_soft)


def draw(layout, context):
    if sdf_available():
        row = layout.row(align=True)
        row.operator('ctk.blob', icon='META_BALL')
        row.operator('ctk.blob_apply', icon='MESH_DATA')
        g = layout.grid_flow(columns=2, align=True)
        for k, l, _ in SMOKES:
            g.operator('ctk.toon_smoke', text=l).kind = k
    else:
        layout.label(text='Blobs and smoke need Blender 5.2', icon='INFO')
    layout.operator('ctk.soft_toy', icon='MOD_BEVEL')
    o = context.active_object
    if o:
        for m in o.modifiers:
            if m.type == 'NODES' and m.name in ('CTK Blob', 'CTK Toon smoke', 'CTK Soft toy'):
                draw_modifier_inputs(layout.box(), m)
