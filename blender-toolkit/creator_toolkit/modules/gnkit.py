"""Geometry Nodes toolkit: one-click node setups with sliders (no node editing needed)."""
import bpy
from ._nodes import Tree, O, I, draw_modifier_inputs, set_input
from .. import uxfit

LABEL, ICON, GROUP = 'Geometry Nodes kit', 'GEOMETRY_NODES', 'Procedural & 2D'

KINDS = [
    ('SCATTER', 'Scatter', 'Scatter copies of another object over this surface (select the copy object too)'),
    ('ARRAY_CURVE', 'Array along curve', 'Copies of another object along this curve (select the copy object too)'),
    ('WOBBLE', 'Line boil / wobble', 'Hand-drawn wobble that changes every few frames'),
    ('GRASS', 'Squiggle grass', 'Doodle grass blades growing from this surface'),
    ('DOTTED', 'Dotted path', 'Dots along this curve, with a Grow slider to animate'),
    ('CLOUD', 'Puffy cloud', 'Turns this mesh into a soft merged cloud'),
]


def _rand_vec(t, lo, hi, seed_sock=None):
    r = t.n('FunctionNodeRandomValue', data_type='FLOAT_VECTOR')
    I(r, 'Min', 'VECTOR').default_value = lo
    I(r, 'Max', 'VECTOR').default_value = hi
    if seed_sock is not None:
        t.link(seed_sock, I(r, 'Seed'))
    return O(r, 'Value', 'VECTOR')


def _rand_float(t, lo, hi, seed_sock=None):
    r = t.n('FunctionNodeRandomValue', data_type='FLOAT')
    I(r, 'Min', 'VALUE').default_value = lo
    I(r, 'Max', 'VALUE').default_value = hi
    if seed_sock is not None:
        t.link(seed_sock, I(r, 'Seed'))
    return O(r, 'Value', 'VALUE')


def _math(t, op, a, b=None, vec=False):
    m = t.n('ShaderNodeVectorMath' if vec else 'ShaderNodeMath', operation=op)
    for k, v in ((0, a), (1, b)):
        if v is None:
            continue
        if isinstance(v, (int, float, tuple)):
            m.inputs[k].default_value = v
        else:
            t.link(v, m.inputs[k])
    return m.outputs[0]


def _object_geo(t, sock_name):
    oi = t.n('GeometryNodeObjectInfo', transform_space='RELATIVE')
    t.link(t.i(sock_name), I(oi, 'Object'))
    return O(oi, 'Geometry')


def build_scatter():
    t = Tree('CTK Scatter')
    if not t.fresh:
        return t.tree
    t.geo_io()
    t.socket('Copy object', 'INPUT', 'NodeSocketObject')
    t.socket('Density', 'INPUT', 'NodeSocketFloat', 10.0, 0.0, 10000.0)
    t.socket('Spacing', 'INPUT', 'NodeSocketFloat', 0.1, 0.0, 100.0)
    t.socket('Size', 'INPUT', 'NodeSocketFloat', 1.0, 0.0, 100.0)
    t.socket('Size variation', 'INPUT', 'NodeSocketFloat', 0.4, 0.0, 1.0)
    t.socket('Random turn', 'INPUT', 'NodeSocketFloat', 1.0, 0.0, 1.0)
    t.socket('Seed', 'INPUT', 'NodeSocketInt', 0)
    d = t.n('GeometryNodeDistributePointsOnFaces', distribute_method='POISSON')
    t.link(t.i('Geometry'), I(d, 'Mesh'))
    t.link(t.i('Density'), I(d, 'Density Max'))
    t.link(t.i('Spacing'), I(d, 'Distance Min'))
    t.link(t.i('Seed'), I(d, 'Seed'))
    inst = t.n('GeometryNodeInstanceOnPoints')
    t.link(O(d, 'Points'), I(inst, 'Points'))
    t.link(_object_geo(t, 'Copy object'), I(inst, 'Instance'))
    # rotation: align to normal then random spin around Z
    turn = _math(t, 'MULTIPLY', _rand_float(t, 0.0, 6.2832, t.i('Seed')), t.i('Random turn'))
    comb = t.n('ShaderNodeCombineXYZ')
    t.link(turn, I(comb, 'Z'))
    t.link(O(comb, 'Vector'), I(inst, 'Rotation'))
    var = _rand_float(t, -1.0, 1.0, t.i('Seed'))
    s = _math(t, 'MULTIPLY_ADD', var, t.i('Size variation'))
    s.node.inputs[2].default_value = 1.0
    sc = _math(t, 'MULTIPLY', s, t.i('Size'))
    t.link(sc, I(inst, 'Scale'))
    j = t.n('GeometryNodeJoinGeometry')
    t.link(O(inst, 'Instances'), I(j, 'Geometry'))
    t.link(t.i('Geometry'), I(j, 'Geometry'))
    t.out(O(j, 'Geometry'))
    return t.tree


def build_array_curve():
    t = Tree('CTK Array Along Curve')
    if not t.fresh:
        return t.tree
    t.geo_io()
    t.socket('Copy object', 'INPUT', 'NodeSocketObject')
    t.socket('Count', 'INPUT', 'NodeSocketInt', 12, 1, 10000)
    t.socket('Size', 'INPUT', 'NodeSocketFloat', 1.0, 0.0, 100.0)
    t.socket('Keep curve', 'INPUT', 'NodeSocketBool', False)
    rs = t.n('GeometryNodeResampleCurve', mode='COUNT')
    t.link(t.i('Geometry'), I(rs, 'Curve'))
    t.link(t.i('Count'), I(rs, 'Count'))
    cp = t.n('GeometryNodeCurveToPoints', mode='EVALUATED')
    t.link(O(rs, 'Curve'), I(cp, 'Curve'))
    inst = t.n('GeometryNodeInstanceOnPoints')
    t.link(O(cp, 'Points'), I(inst, 'Points'))
    t.link(O(cp, 'Rotation'), I(inst, 'Rotation'))
    t.link(_object_geo(t, 'Copy object'), I(inst, 'Instance'))
    t.link(t.i('Size'), I(inst, 'Scale'))
    sw = t.n('GeometryNodeSwitch', input_type='GEOMETRY')
    keep = t.n('GeometryNodeJoinGeometry')
    t.link(O(inst, 'Instances'), I(keep, 'Geometry'))
    t.link(t.i('Geometry'), I(keep, 'Geometry'))
    t.link(t.i('Keep curve'), I(sw, 'Switch'))
    t.link(O(inst, 'Instances'), I(sw, 'False'))
    t.link(O(keep, 'Geometry'), I(sw, 'True'))
    t.out(O(sw, 'Output'))
    return t.tree


def _boil_offset(t, amount_sock, scale_sock, rate_sock):
    """Noise offset that jumps to a new pattern every <rate> frames."""
    st = t.n('GeometryNodeInputSceneTime')
    step = _math(t, 'FLOOR', _math(t, 'DIVIDE', O(st, 'Frame'), rate_sock))
    pos = t.n('GeometryNodeInputPosition')
    nz = t.n('ShaderNodeTexNoise', noise_dimensions='4D')
    t.link(O(pos, 'Position'), I(nz, 'Vector'))
    t.link(step, I(nz, 'W'))
    t.link(scale_sock, I(nz, 'Scale'))
    centred = _math(t, 'SUBTRACT', O(nz, 'Color'), (0.5, 0.5, 0.5), vec=True)
    sc = t.n('ShaderNodeVectorMath', operation='SCALE')
    t.link(centred, sc.inputs[0])
    t.link(amount_sock, I(sc, 'Scale'))
    return sc.outputs[0]


def build_wobble():
    t = Tree('CTK Line Boil')
    if not t.fresh:
        return t.tree
    t.geo_io()
    t.socket('Amount', 'INPUT', 'NodeSocketFloat', 0.03, 0.0, 10.0)
    t.socket('Detail', 'INPUT', 'NodeSocketFloat', 2.0, 0.0, 100.0)
    t.socket('Frames per change', 'INPUT', 'NodeSocketFloat', 3.0, 1.0, 60.0)
    sp = t.n('GeometryNodeSetPosition')
    t.link(t.i('Geometry'), I(sp, 'Geometry'))
    t.link(_boil_offset(t, t.i('Amount'), t.i('Detail'), t.i('Frames per change')), I(sp, 'Offset'))
    t.out(O(sp, 'Geometry'))
    return t.tree


def build_grass():
    t = Tree('CTK Squiggle Grass')
    if not t.fresh:
        return t.tree
    t.geo_io()
    t.socket('Density', 'INPUT', 'NodeSocketFloat', 60.0, 0.0, 100000.0)
    t.socket('Height', 'INPUT', 'NodeSocketFloat', 0.25, 0.0, 100.0)
    t.socket('Thickness', 'INPUT', 'NodeSocketFloat', 0.008, 0.0, 1.0)
    t.socket('Squiggle', 'INPUT', 'NodeSocketFloat', 0.04, 0.0, 10.0)
    t.socket('Frames per change', 'INPUT', 'NodeSocketFloat', 4.0, 1.0, 60.0)
    t.socket('Material', 'INPUT', 'NodeSocketMaterial')
    t.socket('Seed', 'INPUT', 'NodeSocketInt', 0)
    d = t.n('GeometryNodeDistributePointsOnFaces', distribute_method='RANDOM')
    t.link(t.i('Geometry'), I(d, 'Mesh'))
    t.link(t.i('Density'), I(d, 'Density'))
    t.link(t.i('Seed'), I(d, 'Seed'))
    line = t.n('GeometryNodeCurvePrimitiveLine')
    comb = t.n('ShaderNodeCombineXYZ')
    t.link(t.i('Height'), I(comb, 'Z'))
    t.link(O(comb, 'Vector'), I(line, 'End'))
    rs = t.n('GeometryNodeResampleCurve', mode='COUNT')
    I(rs, 'Count').default_value = 6
    t.link(O(line, 'Curve'), I(rs, 'Curve'))
    inst = t.n('GeometryNodeInstanceOnPoints')
    t.link(O(d, 'Points'), I(inst, 'Points'))
    t.link(O(rs, 'Curve'), I(inst, 'Instance'))
    t.link(_rand_vec(t, (-0.25, -0.25, 0.0), (0.25, 0.25, 6.28), t.i('Seed')), I(inst, 'Rotation'))
    t.link(_rand_float(t, 0.6, 1.3, t.i('Seed')), I(inst, 'Scale'))
    real = t.n('GeometryNodeRealizeInstances')
    t.link(O(inst, 'Instances'), I(real, 'Geometry'))
    sp = t.n('GeometryNodeSetPosition')
    t.link(O(real, 'Geometry'), I(sp, 'Geometry'))
    t.link(_boil_offset(t, t.i('Squiggle'), _const(t, 4.0), t.i('Frames per change')), I(sp, 'Offset'))
    prof = t.n('GeometryNodeCurvePrimitiveCircle')
    I(prof, 'Resolution').default_value = 5
    t.link(t.i('Thickness'), I(prof, 'Radius'))
    c2m = t.n('GeometryNodeCurveToMesh')
    t.link(O(sp, 'Geometry'), I(c2m, 'Curve'))
    t.link(O(prof, 'Curve'), I(c2m, 'Profile Curve'))
    sm = t.n('GeometryNodeSetMaterial')
    t.link(O(c2m, 'Mesh'), I(sm, 'Geometry'))
    t.link(t.i('Material'), I(sm, 'Material'))
    j = t.n('GeometryNodeJoinGeometry')
    t.link(O(sm, 'Geometry'), I(j, 'Geometry'))
    t.link(t.i('Geometry'), I(j, 'Geometry'))
    t.out(O(j, 'Geometry'))
    return t.tree


def _const(t, v):
    n = t.n('ShaderNodeValue')
    n.outputs[0].default_value = v
    return n.outputs[0]


def build_dotted():
    t = Tree('CTK Dotted Path')
    if not t.fresh:
        return t.tree
    t.geo_io()
    t.socket('Spacing', 'INPUT', 'NodeSocketFloat', 0.15, 0.001, 100.0)
    t.socket('Dot size', 'INPUT', 'NodeSocketFloat', 0.03, 0.0, 10.0)
    t.socket('Grow', 'INPUT', 'NodeSocketFloat', 1.0, 0.0, 1.0)
    t.socket('Material', 'INPUT', 'NodeSocketMaterial')
    tr = t.n('GeometryNodeTrimCurve', mode='FACTOR')
    t.link(t.i('Geometry'), I(tr, 'Curve'))
    t.link(t.i('Grow'), I(tr, 'End', 'VALUE'))
    rs = t.n('GeometryNodeResampleCurve', mode='LENGTH')
    t.link(O(tr, 'Curve'), I(rs, 'Curve'))
    t.link(t.i('Spacing'), I(rs, 'Length'))
    cp = t.n('GeometryNodeCurveToPoints', mode='EVALUATED')
    t.link(O(rs, 'Curve'), I(cp, 'Curve'))
    ico = t.n('GeometryNodeMeshIcoSphere')
    I(ico, 'Subdivisions').default_value = 2
    t.link(t.i('Dot size'), I(ico, 'Radius'))
    inst = t.n('GeometryNodeInstanceOnPoints')
    t.link(O(cp, 'Points'), I(inst, 'Points'))
    t.link(O(ico, 'Mesh'), I(inst, 'Instance'))
    real = t.n('GeometryNodeRealizeInstances')
    t.link(O(inst, 'Instances'), I(real, 'Geometry'))
    sm = t.n('GeometryNodeSetMaterial')
    t.link(O(real, 'Geometry'), I(sm, 'Geometry'))
    t.link(t.i('Material'), I(sm, 'Material'))
    t.out(O(sm, 'Geometry'))
    return t.tree


def build_cloud():
    t = Tree('CTK Puffy Cloud')
    if not t.fresh:
        return t.tree
    t.geo_io()
    t.socket('Puffs', 'INPUT', 'NodeSocketFloat', 40.0, 0.0, 10000.0)
    t.socket('Puff size', 'INPUT', 'NodeSocketFloat', 0.35, 0.0, 100.0)
    t.socket('Smoothness', 'INPUT', 'NodeSocketFloat', 0.06, 0.005, 10.0)
    t.socket('Seed', 'INPUT', 'NodeSocketInt', 0)
    d = t.n('GeometryNodeDistributePointsOnFaces', distribute_method='RANDOM')
    t.link(t.i('Geometry'), I(d, 'Mesh'))
    t.link(t.i('Puffs'), I(d, 'Density'))
    t.link(t.i('Seed'), I(d, 'Seed'))
    ico = t.n('GeometryNodeMeshIcoSphere')
    I(ico, 'Subdivisions').default_value = 2
    inst = t.n('GeometryNodeInstanceOnPoints')
    t.link(O(d, 'Points'), I(inst, 'Points'))
    t.link(O(ico, 'Mesh'), I(inst, 'Instance'))
    t.link(_math(t, 'MULTIPLY', _rand_float(t, 0.5, 1.4, t.i('Seed')), t.i('Puff size')), I(inst, 'Scale'))
    real = t.n('GeometryNodeRealizeInstances')
    t.link(O(inst, 'Instances'), I(real, 'Geometry'))
    j = t.n('GeometryNodeJoinGeometry')
    t.link(O(real, 'Geometry'), I(j, 'Geometry'))
    t.link(t.i('Geometry'), I(j, 'Geometry'))
    mv = t.n('GeometryNodeMeshToVolume', resolution_mode='VOXEL_SIZE')
    t.link(O(j, 'Geometry'), I(mv, 'Mesh'))
    t.link(t.i('Smoothness'), I(mv, 'Voxel Size'))
    vm = t.n('GeometryNodeVolumeToMesh', resolution_mode='GRID')
    t.link(O(mv, 'Volume'), I(vm, 'Volume'))
    ss = t.n('GeometryNodeSetShadeSmooth')
    t.link(O(vm, 'Mesh'), I(ss, 'Geometry'))
    t.out(O(ss, 'Geometry'))
    return t.tree


BUILDERS = {'SCATTER': build_scatter, 'ARRAY_CURVE': build_array_curve, 'WOBBLE': build_wobble,
            'GRASS': build_grass, 'DOTTED': build_dotted, 'CLOUD': build_cloud}
NEEDS_CURVE = {'ARRAY_CURVE', 'DOTTED'}
NEEDS_COPY = {'SCATTER', 'ARRAY_CURVE'}


def add(obj, kind, copy=None):
    group = BUILDERS[kind]()
    mod = obj.modifiers.new('CTK ' + dict((k, l) for k, l, _ in KINDS)[kind], 'NODES')
    mod.node_group = group
    if copy is not None:
        set_input(mod, 'Copy object', copy)
        copy.hide_render = True
        copy.hide_set(True)
    obj.update_tag()
    return mod


class CTK_OT_gn_add(bpy.types.Operator):
    """Add a ready-made Geometry Nodes setup to the active object"""
    bl_idname = 'ctk.gn_add'
    bl_label = 'Add node setup'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=KINDS)

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type not in ('MESH', 'CURVE'):
            self.report({'ERROR'}, 'Select a mesh or a curve first')
            return {'CANCELLED'}
        if self.kind in NEEDS_CURVE and obj.type != 'CURVE':
            self.report({'ERROR'}, 'This one needs a curve as the active object')
            return {'CANCELLED'}
        if self.kind not in NEEDS_CURVE and obj.type != 'MESH':
            self.report({'ERROR'}, 'This one needs a mesh as the active object')
            return {'CANCELLED'}
        copy = None
        if self.kind in NEEDS_COPY:
            others = [o for o in context.selected_objects if o is not obj]
            if not others:
                self.report({'ERROR'}, 'Also select the object to copy (click it, then Shift-click the target)')
                return {'CANCELLED'}
            copy = others[0]
        add(obj, self.kind, copy)
        return {'FINISHED'}


CLASSES = (CTK_OT_gn_add,)


def draw(layout, context):
    g = uxfit.flow(layout, context, [str(_t[1]) for _t in KINDS], most=2)
    for k, l, _ in KINDS:
        g.operator('ctk.gn_add', text=l).kind = k
    obj = context.active_object
    if obj:
        for m in obj.modifiers:
            if m.type == 'NODES' and m.name.startswith('CTK '):
                box = layout.box()
                box.label(text=m.name[4:], icon='GEOMETRY_NODES')
                draw_modifier_inputs(box, m)
