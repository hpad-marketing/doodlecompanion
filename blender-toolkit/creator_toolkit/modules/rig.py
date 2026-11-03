"""Simple Rig Builder: snap markers, press Build. FK/IK, springy ears/tail, click-to-pick panel."""
import bpy
from mathutils import Vector

LABEL, ICON, GROUP = 'Simple Rig Builder', 'ARMATURE_DATA', 'Rigging'
MARKER_COLL = 'CTK Rig Markers'

# marker: (x, y, z) in a unit box: x = -1..1 half width, y = -1..1 half depth, z = 0..1 height
BIPED = {
    'root': (0, 0, 0), 'hips': (0, 0, .50), 'chest': (0, 0, .68), 'neck': (0, 0, .80), 'head': (0, 0, .84),
    'head_top': (0, 0, 1.0),
    'shoulder.L': (.18, 0, .78), 'elbow.L': (.38, .05, .65), 'wrist.L': (.55, 0, .52), 'hand_tip.L': (.63, 0, .46),
    'hip.L': (.10, 0, .48), 'knee.L': (.10, -.08, .26), 'ankle.L': (.10, 0, .05), 'toe.L': (.10, -.35, .0),
    'ear.L': (.10, 0, .97), 'ear_tip.L': (.18, 0, 1.18),
    'tail': (0, .3, .47), 'tail_tip': (0, .8, .55),
}
QUAD = {
    'root': (0, 0, 0), 'hips': (0, .45, .62), 'chest': (0, -.35, .64), 'neck': (0, -.55, .72), 'head': (0, -.7, .82),
    'head_top': (0, -1.0, .95),
    'shoulder.L': (.2, -.35, .58), 'elbow.L': (.2, -.30, .32), 'wrist.L': (.2, -.35, .06), 'hand_tip.L': (.2, -.5, .0),
    'hip.L': (.2, .45, .58), 'knee.L': (.2, .55, .32), 'ankle.L': (.2, .45, .06), 'toe.L': (.2, .30, .0),
    'ear.L': (.12, -.75, .92), 'ear_tip.L': (.2, -.7, 1.1),
    'tail': (0, .6, .62), 'tail_tip': (0, 1.0, .75),
}
TEMPLATES = {'BIPED': BIPED, 'QUAD': QUAD}
PARTS = {'arms': ('shoulder', 'elbow', 'wrist', 'hand_tip'), 'legs': ('hip', 'knee', 'ankle', 'toe'),
         'ears': ('ear', 'ear_tip'), 'tail': ('tail', 'tail_tip')}


def _wanted(props):
    keep = []
    tpl = TEMPLATES[props.kind]
    for k in tpl:
        base = k.split('.')[0]
        part = next((p for p, names in PARTS.items() if base in names), None)
        if part and not getattr(props, 'use_' + part):
            continue
        keep.append(k)
    return keep


class CTK_RigProps(bpy.types.PropertyGroup):
    kind: bpy.props.EnumProperty(name='Body', items=[('BIPED', 'Two legs', 'People, mascots, bunnies'),
                                                     ('QUAD', 'Four legs', 'Dogs, cats, horses')])
    use_arms: bpy.props.BoolProperty(name='Arms', default=True)
    use_legs: bpy.props.BoolProperty(name='Legs', default=True)
    use_ears: bpy.props.BoolProperty(name='Ears', default=False)
    use_tail: bpy.props.BoolProperty(name='Tail', default=False)
    mirror: bpy.props.BoolProperty(name='Mirror left to right', default=True)
    springy: bpy.props.BoolProperty(name='Springy ears and tail', default=True)


def _bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def place_markers(context, mesh, props):
    coll = bpy.data.collections.get(MARKER_COLL) or bpy.data.collections.new(MARKER_COLL)
    if coll.name not in context.scene.collection.children:
        context.scene.collection.children.link(coll)
    for o in list(coll.objects):
        bpy.data.objects.remove(o)
    lo, hi = _bbox(mesh)
    c = (lo + hi) / 2
    half = (hi - lo) / 2
    size = max(half.length * 0.04, 0.01)
    for k in _wanted(props):
        if k.endswith('.R'):
            continue
        x, y, z = TEMPLATES[props.kind][k]
        e = bpy.data.objects.new('M:' + k, None)
        e.empty_display_type = 'SPHERE'
        e.empty_display_size = size
        e.show_in_front = True
        e.location = (c.x + x * half.x, c.y + y * half.y, lo.z + z * (hi.z - lo.z))
        coll.objects.link(e)
    coll['ctk_mesh'] = mesh.name
    coll['ctk_kind'] = props.kind


def _m(name):
    o = bpy.data.objects.get('M:' + name)
    return o.matrix_world.translation.copy() if o else None


def _mirror(v):
    return Vector((-v.x, v.y, v.z)) if v else None


def _widget(name, kind='CIRCLE'):
    w = bpy.data.objects.get(name)
    if w:
        return w
    me = bpy.data.meshes.new(name)
    import math
    if kind == 'CIRCLE':
        n = 24
        verts = [(math.cos(i / n * 6.2832), 0, math.sin(i / n * 6.2832)) for i in range(n)]
        edges = [(i, (i + 1) % n) for i in range(n)]
    else:  # BOX
        verts = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        edges = [(0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7)]
    me.from_pydata(verts, edges, [])
    w = bpy.data.objects.new(name, me)
    w.use_fake_user = True
    return w


def build_rig(context, props):
    coll = bpy.data.collections.get(MARKER_COLL)
    mesh = bpy.data.objects.get(coll['ctk_mesh']) if coll else None
    if not mesh:
        raise RuntimeError('Place markers first')
    lo, hi = _bbox(mesh)
    height = hi.z - lo.z
    P = {}
    for k in _wanted(props):
        P[k] = _m(k)
    sides = ['L']
    if props.mirror:
        sides.append('R')
        for k in list(P):
            if k.endswith('.L') and P[k] is not None:
                c = mesh.matrix_world.translation.x
                v = P[k].copy(); v.x = 2 * c - v.x
                P[k[:-2] + '.R'] = v
    arm = bpy.data.armatures.new(mesh.name + ' Rig')
    rig = bpy.data.objects.new(mesh.name + ' Rig', arm)
    context.scene.collection.objects.link(rig)
    rig.show_in_front = True
    for o in context.selected_objects:
        o.select_set(False)
    context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    ctl = []  # (name, kind)

    def bone(name, head, tail, parent=None, deform=True, connect=False):
        if head is None or tail is None:
            return None
        if (tail - head).length < 1e-4:
            tail = head + Vector((0, 0, height * 0.05))
        b = eb.new(name)
        b.head, b.tail = head, tail
        b.use_deform = deform
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect
        return b

    root = bone('root', P['root'], P['root'] + Vector((0, -height * 0.25, 0)), deform=False)
    ctl.append(('root', 'BOX'))
    bone('hips', P['hips'], P['chest'], 'root'); ctl.append(('hips', 'CIRCLE'))
    bone('chest', P['chest'], P['neck'], 'hips', connect=True); ctl.append(('chest', 'CIRCLE'))
    bone('neck', P['neck'], P['head'], 'chest', connect=True); ctl.append(('neck', 'CIRCLE'))
    bone('head', P['head'], P['head_top'], 'neck', connect=True); ctl.append(('head', 'CIRCLE'))
    springs = []
    for s in sides:
        if props.use_arms and P.get('shoulder.' + s) is not None:
            bone('upper_arm.' + s, P['shoulder.' + s], P['elbow.' + s], 'chest')
            bone('forearm.' + s, P['elbow.' + s], P['wrist.' + s], 'upper_arm.' + s, connect=True)
            bone('hand.' + s, P['wrist.' + s], P['hand_tip.' + s], 'forearm.' + s, connect=True)
            ik = bone('IK_hand.' + s, P['wrist.' + s], P['wrist.' + s] + (P['hand_tip.' + s] - P['wrist.' + s]), 'root', deform=False)
            back = Vector((0, 1, 0)) * height * 0.3
            bone('pole_arm.' + s, P['elbow.' + s] + back, P['elbow.' + s] + back + Vector((0, 0, height * 0.04)), 'root', deform=False)
            ctl += [('upper_arm.' + s, 'CIRCLE'), ('forearm.' + s, 'CIRCLE'), ('hand.' + s, 'CIRCLE'),
                    ('IK_hand.' + s, 'BOX'), ('pole_arm.' + s, 'BOX')]
        if props.use_legs and P.get('hip.' + s) is not None:
            bone('thigh.' + s, P['hip.' + s], P['knee.' + s], 'hips')
            bone('shin.' + s, P['knee.' + s], P['ankle.' + s], 'thigh.' + s, connect=True)
            bone('foot.' + s, P['ankle.' + s], P['toe.' + s], 'shin.' + s, connect=True)
            bone('IK_foot.' + s, P['ankle.' + s], P['toe.' + s], 'root', deform=False)
            front = Vector((0, -1, 0)) * height * 0.3
            bone('pole_leg.' + s, P['knee.' + s] + front, P['knee.' + s] + front + Vector((0, 0, height * 0.04)), 'root', deform=False)
            ctl += [('thigh.' + s, 'CIRCLE'), ('shin.' + s, 'CIRCLE'), ('foot.' + s, 'CIRCLE'),
                    ('IK_foot.' + s, 'BOX'), ('pole_leg.' + s, 'BOX')]
        if props.use_ears and P.get('ear.' + s) is not None:
            a, b = P['ear.' + s], P['ear_tip.' + s]
            mid = (a + b) / 2
            bone('ear.' + s, a, mid, 'head')
            bone('ear_tip.' + s, mid, b, 'ear.' + s, connect=True)
            ctl += [('ear.' + s, 'CIRCLE'), ('ear_tip.' + s, 'CIRCLE')]
            springs += ['ear.' + s, 'ear_tip.' + s]
    if props.use_tail and P.get('tail') is not None:
        a, b = P['tail'], P['tail_tip']
        prev = 'hips'
        for i in range(3):
            n = f'tail.{i + 1}'
            bone(n, a.lerp(b, i / 3), a.lerp(b, (i + 1) / 3), prev, connect=i > 0)
            prev = n
            ctl.append((n, 'CIRCLE'))
            springs.append(n)
    bpy.ops.object.mode_set(mode='POSE')
    pbs = rig.pose.bones
    for s in sides:
        if 'forearm.' + s in pbs:
            c = pbs['forearm.' + s].constraints.new('IK')
            c.name = 'CTK IK'
            c.target, c.subtarget = rig, 'IK_hand.' + s
            c.pole_target, c.pole_subtarget = rig, 'pole_arm.' + s
            c.pole_angle = -1.5708
            c.chain_count = 2
            cr = pbs['hand.' + s].constraints.new('COPY_ROTATION')
            cr.name = 'CTK IK'
            cr.target, cr.subtarget = rig, 'IK_hand.' + s
            _switch(rig, 'IK arm ' + s, [c, cr])
        if 'shin.' + s in pbs:
            c = pbs['shin.' + s].constraints.new('IK')
            c.name = 'CTK IK'
            c.target, c.subtarget = rig, 'IK_foot.' + s
            c.pole_target, c.pole_subtarget = rig, 'pole_leg.' + s
            c.pole_angle = -1.5708
            c.chain_count = 2
            cr = pbs['foot.' + s].constraints.new('COPY_ROTATION')
            cr.name = 'CTK IK'
            cr.target, cr.subtarget = rig, 'IK_foot.' + s
            _switch(rig, 'IK leg ' + s, [c, cr])
    for n, kind in ctl:
        if n in pbs:
            pbs[n].custom_shape = _widget('CTK_WGT_' + kind.lower(), kind)
            pbs[n].custom_shape_scale_xyz = (0.6, 0.6, 0.6) if kind == 'CIRCLE' else (0.15, 0.15, 0.15)
            pbs[n].rotation_mode = 'XYZ'
    if props.springy:
        for n in springs:
            pbs[n]['ctk_spring'] = 1
            pbs[n]['ctk_stiffness'] = 0.25
            pbs[n]['ctk_damping'] = 0.75
            pbs[n]['ctk_gravity'] = 0.0
        if springs:
            rig['dm_phys_kind'] = 'SPRING'
    bpy.ops.object.mode_set(mode='OBJECT')
    rig['ctk_rig'] = props.kind
    # skin it
    for o in context.selected_objects:
        o.select_set(False)
    mesh.select_set(True)
    rig.select_set(True)
    context.view_layer.objects.active = rig
    msg = 'Automatic weights'
    try:
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')
        if not any(len(g.name) for g in mesh.vertex_groups):
            raise RuntimeError
    except Exception:
        bpy.ops.object.parent_set(type='ARMATURE_ENVELOPE')
        msg = 'Envelope weights (automatic weights failed: check the mesh is closed)'
    if coll:
        coll.hide_viewport = True
    return rig, msg


def _switch(rig, prop, cons):
    rig[prop] = 1.0
    try:
        ui = rig.id_properties_ui(prop)
        ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description='0 = FK, 1 = IK')
    except Exception:
        pass
    for c in cons:
        d = c.driver_add('influence').driver
        d.type = 'AVERAGE'
        v = d.variables.new()
        v.targets[0].id = rig
        v.targets[0].data_path = f'["{prop}"]'


class CTK_OT_rig_markers(bpy.types.Operator):
    """Place markers on the selected character mesh. Move them onto the joints, then press Build"""
    bl_idname = 'ctk.rig_markers'
    bl_label = 'Place markers'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mesh = context.active_object
        if not mesh or mesh.type != 'MESH':
            self.report({'WARNING'}, 'Select the character mesh first')
            return {'CANCELLED'}
        place_markers(context, mesh, context.scene.ctk_rig)
        return {'FINISHED'}


class CTK_OT_rig_build(bpy.types.Operator):
    """Build bones, controls, IK and weights from the markers"""
    bl_idname = 'ctk.rig_build'
    bl_label = 'Build rig'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            rig, msg = build_rig(context, context.scene.ctk_rig)
        except RuntimeError as e:
            self.report({'WARNING'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Built {rig.name}: {msg}')
        return {'FINISHED'}


class CTK_OT_rig_pick(bpy.types.Operator):
    """Select this control"""
    bl_idname = 'ctk.rig_pick'
    bl_label = 'Pick control'
    bone: bpy.props.StringProperty()
    extend: bpy.props.BoolProperty(default=False)

    def invoke(self, context, event):
        self.extend = event.shift
        return self.execute(context)

    def execute(self, context):
        rig = context.active_object if context.active_object and context.active_object.get('ctk_rig') else \
            next((o for o in context.scene.objects if o.get('ctk_rig')), None)
        if not rig:
            return {'CANCELLED'}
        context.view_layer.objects.active = rig
        if context.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        def sel(name, on):
            pb = rig.pose.bones.get(name)
            if pb is not None and hasattr(pb, 'select'):  # 5.x: selection lives on pose bones
                pb.select = on
            elif name in rig.data.bones:
                rig.data.bones[name].select = on
        if not self.extend:
            for b in rig.data.bones:
                sel(b.name, False)
        b = rig.data.bones.get(self.bone)
        if b:
            sel(b.name, True)
            rig.data.bones.active = b
        return {'FINISHED'}


class CTK_OT_rig_reset(bpy.types.Operator):
    """Put every control back to its rest pose"""
    bl_idname = 'ctk.rig_reset'
    bl_label = 'Reset pose'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig = context.active_object
        if not rig or rig.type != 'ARMATURE':
            return {'CANCELLED'}
        for pb in rig.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_euler = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.scale = (1, 1, 1)
        return {'FINISHED'}


class CTK_OT_rigify(bpy.types.Operator):
    """Advanced: turn on Rigify and add its human or animal template"""
    bl_idname = 'ctk.rigify'
    bl_label = 'Rigify (advanced)'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[('HUMAN', 'Human', ''), ('BASIC', 'Basic human', ''), ('QUAD', 'Animal', '')])

    def execute(self, context):
        import addon_utils
        for mod in ('rigify', 'bl_ext.blender_org.rigify'):
            try:
                addon_utils.enable(mod, default_set=True)
                break
            except Exception:
                continue
        try:
            if self.kind == 'HUMAN':
                bpy.ops.object.armature_human_metarig_add()
            elif self.kind == 'BASIC':
                bpy.ops.object.armature_basic_human_metarig_add()
            else:
                bpy.ops.object.armature_quadruped_metarig_add() if hasattr(bpy.ops.object, 'armature_quadruped_metarig_add') else bpy.ops.object.armature_human_metarig_add()
        except Exception as e:
            self.report({'WARNING'}, f'Rigify not available: {e}')
            return {'CANCELLED'}
        self.report({'INFO'}, 'Fit the metarig, then Armature properties › Rigify › Generate Rig')
        return {'FINISHED'}


CLASSES = (CTK_RigProps, CTK_OT_rig_markers, CTK_OT_rig_build, CTK_OT_rig_pick, CTK_OT_rig_reset, CTK_OT_rigify)


def register_extra():
    bpy.types.Scene.ctk_rig = bpy.props.PointerProperty(type=CTK_RigProps)


def unregister_extra():
    del bpy.types.Scene.ctk_rig


def _pick(layout, rig, name, text=None):
    if name in rig.pose.bones:
        b = rig.data.bones[name]
        layout.operator('ctk.rig_pick', text=text or name, depress=b.select).bone = name
    else:
        layout.label(text='')


def draw(layout, context):
    p = context.scene.ctk_rig
    rig = context.active_object if context.active_object and context.active_object.get('ctk_rig') else None
    if rig:
        col = layout.column(align=True)
        col.label(text=f'{rig.name}: click to pick (Shift adds)', icon='RESTRICT_SELECT_OFF')
        row = col.row(align=True)
        _pick(row, rig, 'ear.R', 'Ear R'); _pick(row, rig, 'head', 'Head'); _pick(row, rig, 'ear.L', 'Ear L')
        row = col.row(align=True); row.label(text=''); _pick(row, rig, 'neck', 'Neck'); row.label(text='')
        row = col.row(align=True)
        _pick(row, rig, 'IK_hand.R', 'Hand R'); _pick(row, rig, 'chest', 'Chest'); _pick(row, rig, 'IK_hand.L', 'Hand L')
        row = col.row(align=True)
        _pick(row, rig, 'upper_arm.R', 'Arm R'); _pick(row, rig, 'hips', 'Hips'); _pick(row, rig, 'upper_arm.L', 'Arm L')
        row = col.row(align=True)
        _pick(row, rig, 'IK_foot.R', 'Foot R'); _pick(row, rig, 'tail.1', 'Tail'); _pick(row, rig, 'IK_foot.L', 'Foot L')
        row = col.row(align=True); row.label(text=''); _pick(row, rig, 'root', 'Root (move all)'); row.label(text='')
        sw = [k for k in rig.keys() if k.startswith('IK ')]
        if sw:
            box = layout.box()
            box.label(text='FK (0) or IK (1)')
            for k in sw:
                box.prop(rig, f'["{k}"]', text=k[3:], slider=True)
        layout.operator('ctk.rig_reset', icon='LOOP_BACK')
        return
    col = layout.column(align=True)
    col.prop(p, 'kind', expand=True)
    row = col.row(align=True)
    for k in ('arms', 'legs', 'ears', 'tail'):
        row.prop(p, 'use_' + k, toggle=True)
    col.prop(p, 'mirror')
    col.prop(p, 'springy')
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator('ctk.rig_markers', text='1  Place markers', icon='EMPTY_DATA')
    row.operator('ctk.rig_build', text='2  Build', icon='ARMATURE_DATA')
    layout.operator_menu_enum('ctk.rigify', 'kind', text='Rigify (advanced)', icon='OUTLINER_OB_ARMATURE')
