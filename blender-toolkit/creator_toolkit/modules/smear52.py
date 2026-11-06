"""Speed lines and smear trails from bones (Blender 5.2 Bone Info node + a simulation zone).

Pick bones (hands, feet, tail tip) and a trail follows each one, thick when it moves fast and
gone when it stops. Works with the Simple Rig Builder or any armature."""
import bpy
from . import _util
from ._nodes import Tree, O, I, set_input, draw_modifier_inputs
from .. import uxfit

LABEL, ICON, GROUP = 'Speed lines from bones', 'MOD_CURVE', 'Animation'


def available():
    return hasattr(bpy.types, 'GeometryNodeBoneInfo')


def _m(t, op, a, b=None):
    n = t.n('ShaderNodeMath', operation=op)
    for k, v in ((0, a), (1, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[k].default_value = v
        else:
            t.link(v, n.inputs[k])
    return n.outputs[0]


def build():
    t = Tree('CTK Speed Trail')
    if not t.fresh:
        return t.tree
    t.socket('Geometry', 'INPUT', 'NodeSocketGeometry')
    t.socket('Geometry', 'OUTPUT', 'NodeSocketGeometry')
    t.socket('Armature', 'INPUT', 'NodeSocketObject')
    t.socket('Bone', 'INPUT', 'NodeSocketString')
    t.socket('Trail length (frames)', 'INPUT', 'NodeSocketInt', 6, 2, 60)
    t.socket('Width', 'INPUT', 'NodeSocketFloat', 0.06, 0.0, 5.0)
    t.socket('Speed for full width', 'INPUT', 'NodeSocketFloat', 0.3, 0.001, 50.0)
    t.socket('Material', 'INPUT', 'NodeSocketMaterial')
    # tip of the bone, in this object's space
    bi = t.n('GeometryNodeBoneInfo')
    bi.transform_space = 'RELATIVE'
    t.link(t.i('Armature'), I(bi, 'Armature'))
    t.link(t.i('Bone'), I(bi, 'Bone Name'))
    tipv = t.n('ShaderNodeCombineXYZ')
    t.link(O(bi, 'Rest Length'), I(tipv, 'Y'))
    tp = t.n('FunctionNodeTransformPoint')
    t.link(O(tipv, 'Vector'), I(tp, 'Vector'))
    t.link(O(bi, 'Pose'), I(tp, 'Transform'))
    newpt = t.n('GeometryNodePoints')
    I(newpt, 'Count').default_value = 1
    t.link(O(tp, 'Vector'), I(newpt, 'Position'))
    # simulation: keep the last N tip positions, each with an age
    si = t.n('GeometryNodeSimulationInput')
    so = t.n('GeometryNodeSimulationOutput')
    si.pair_with_output(so)
    ag = t.n('GeometryNodeInputNamedAttribute', data_type='FLOAT')
    I(ag, 'Name').default_value = 'age'
    older = t.n('GeometryNodeStoreNamedAttribute', data_type='FLOAT', domain='POINT')
    I(older, 'Name').default_value = 'age'
    t.link(O(si, 'Geometry'), I(older, 'Geometry'))
    t.link(_m(t, 'ADD', O(ag, 'Attribute'), 1.0), I(older, 'Value'))
    ag2 = t.n('GeometryNodeInputNamedAttribute', data_type='FLOAT')
    I(ag2, 'Name').default_value = 'age'
    dele = t.n('GeometryNodeDeleteGeometry')
    t.link(O(older, 'Geometry'), I(dele, 'Geometry'))
    t.link(_m(t, 'GREATER_THAN', O(ag2, 'Attribute'), t.i('Trail length (frames)')), I(dele, 'Selection'))
    j = t.n('GeometryNodeJoinGeometry')
    t.link(O(newpt, 'Points'), I(j, 'Geometry'))
    t.link(O(dele, 'Geometry'), I(j, 'Geometry'))
    t.link(O(j, 'Geometry'), I(so, 'Geometry'))
    # points -> one curve ordered by age
    ag3 = t.n('GeometryNodeInputNamedAttribute', data_type='FLOAT')
    I(ag3, 'Name').default_value = 'age'
    p2c = t.n('GeometryNodePointsToCurves')
    t.link(O(so, 'Geometry'), I(p2c, 'Points'))
    t.link(O(ag3, 'Attribute'), I(p2c, 'Weight'))
    # width: taper to the tail, scaled by how far the tip travels per frame (speed)
    ln = t.n('GeometryNodeCurveLength')
    t.link(O(p2c, 'Curves'), I(ln, 'Curve'))
    speed = _m(t, 'DIVIDE', O(ln, 'Length'), t.i('Trail length (frames)'))
    k = _m(t, 'MINIMUM', _m(t, 'DIVIDE', speed, t.i('Speed for full width')), 1.0)
    par = t.n('GeometryNodeSplineParameter')
    taper = _m(t, 'SUBTRACT', 1.0, O(par, 'Factor'))
    rad = _m(t, 'MULTIPLY', _m(t, 'MULTIPLY', taper, k), t.i('Width'))
    sr = t.n('GeometryNodeSetCurveRadius')
    t.link(O(p2c, 'Curves'), I(sr, 'Curve'))
    t.link(rad, I(sr, 'Radius'))
    prof = t.n('GeometryNodeCurvePrimitiveCircle')
    I(prof, 'Resolution').default_value = 6
    I(prof, 'Radius').default_value = 1.0
    c2m = t.n('GeometryNodeCurveToMesh')
    t.link(O(sr, 'Curve'), I(c2m, 'Curve'))
    t.link(O(prof, 'Curve'), I(c2m, 'Profile Curve'))
    if any(x.name == 'Scale' for x in c2m.inputs):  # 4.4+: profile size comes from Scale, not radius
        t.link(rad, I(c2m, 'Scale'))
    sm = t.n('GeometryNodeSetMaterial')
    t.link(O(c2m, 'Mesh'), I(sm, 'Geometry'))
    t.link(t.i('Material'), I(sm, 'Material'))
    t.out(O(sm, 'Geometry'))
    return t.tree


def add_trail(context, arm, bone, colour='#1F1F1D'):
    me = bpy.data.meshes.new('Speed trail')
    o = bpy.data.objects.new('Speed trail ' + bone, me)
    context.scene.collection.objects.link(o)
    o.matrix_world = arm.matrix_world.copy()
    o.parent = arm
    o.matrix_parent_inverse = arm.matrix_world.inverted()
    m = o.modifiers.new('CTK Speed trail', 'NODES')
    m.node_group = build()
    set_input(m, 'Armature', arm)
    set_input(m, 'Bone', bone)
    mat = bpy.data.materials.get('CTK Speed line')
    if not mat:
        mat = bpy.data.materials.new('CTK Speed line')
        mat.use_nodes = True
        b = mat.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (*_util.hex_to_linear(colour), 1)
        b.inputs['Emission Color'].default_value = (*_util.hex_to_linear(colour), 1)
        b.inputs['Emission Strength'].default_value = 1.0
    set_input(m, 'Material', mat)
    return o


class CTK_OT_speed_trail(bpy.types.Operator):
    """Add speed lines behind the selected bones (Pose Mode)"""
    bl_idname = 'ctk.speed_trail'
    bl_label = 'Speed lines'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return available()

    def execute(self, context):
        bones = list(context.selected_pose_bones or [])
        if not bones:
            self.report({'ERROR'}, 'Select bones in Pose Mode (hands, feet, tail tip)')
            return {'CANCELLED'}
        arm = bones[0].id_data
        for pb in bones:
            add_trail(context, arm, pb.name)
        self.report({'INFO'}, f'{len(bones)} speed trails. Play the animation to see them')
        return {'FINISHED'}


class CTK_OT_speed_trail_bake(bpy.types.Operator):
    """Cache the trails so scrubbing back and forth shows them correctly"""
    bl_idname = 'ctk.speed_trail_bake'
    bl_label = 'Cache trails'

    def execute(self, context):
        sel = [o for o in context.scene.objects if 'CTK Speed trail' in o.modifiers]
        if not sel:
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        for o in sel:
            o.select_set(True)
        try:
            bpy.ops.object.simulation_nodes_cache_bake(selected=True)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        return {'FINISHED'}


CLASSES = (CTK_OT_speed_trail, CTK_OT_speed_trail_bake)


def draw(layout, context):
    if not available():
        uxfit.wrap(layout, context, 'Needs Blender 5.2 (Bone Info node)', icon='INFO')
        return
    row = layout.row(align=True)
    row.operator('ctk.speed_trail', icon='MOD_CURVE')
    row.operator('ctk.speed_trail_bake', icon='FILE_CACHE')
    o = context.active_object
    if o and 'CTK Speed trail' in o.modifiers:
        draw_modifier_inputs(layout.box(), o.modifiers['CTK Speed trail'])
