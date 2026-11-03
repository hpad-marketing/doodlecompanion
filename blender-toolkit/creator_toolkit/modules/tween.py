"""Tweening and easing: breakdown slider, ease presets, stepped/smooth switch (AnimAide-style)."""
import bpy
from ..compat import fcurves_of

LABEL, ICON, GROUP = 'Tween + ease', 'IPO_EASE_IN_OUT', 'Animation'


def _targets(context):
    """(owner id, data_path prefix) for selected pose bones or objects."""
    out = []
    if context.mode == 'POSE' and context.selected_pose_bones:
        for pb in context.selected_pose_bones:
            out.append((pb.id_data, f'pose.bones["{pb.name}"].'))
    else:
        for o in context.selected_objects:
            out.append((o, ''))
    return out


def _fcurves(context):
    res = []
    for owner, prefix in _targets(context):
        for fc in fcurves_of(owner):
            if prefix and not fc.data_path.startswith(prefix):
                continue
            if not prefix and fc.data_path.startswith('pose.bones'):
                continue
            res.append(fc)
    return res


def breakdown(context, factor):
    f = context.scene.frame_current
    n = 0
    for fc in _fcurves(context):
        kps = sorted(fc.keyframe_points, key=lambda k: k.co.x)
        prev = [k for k in kps if k.co.x < f - 0.01]
        nxt = [k for k in kps if k.co.x > f + 0.01]
        if not prev or not nxt:
            continue
        a, b = prev[-1].co.y, nxt[0].co.y
        val = a + (b - a) * factor
        existing = [k for k in kps if abs(k.co.x - f) <= 0.01]
        if existing:
            existing[0].co.y = val
            existing[0].handle_left_type = existing[0].handle_right_type = 'AUTO_CLAMPED'
        else:
            kp = fc.keyframe_points.insert(f, val, options={'FAST'})
            kp.type = 'BREAKDOWN'
        fc.update()
        n += 1
    return n


class CTK_OT_breakdown(bpy.types.Operator):
    """Breakdown slider: drag left to favour the previous pose, right for the next (0.5 = halfway). Values past the ends overshoot"""
    bl_idname = 'ctk.breakdown'
    bl_label = 'Breakdown'
    bl_options = {'REGISTER', 'UNDO', 'GRAB_CURSOR', 'BLOCKING'}
    factor: bpy.props.FloatProperty(name='Favour', default=0.5, min=-0.5, max=1.5, subtype='FACTOR')

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            dx = (event.mouse_x - self._x) / 300.0
            self.factor = max(-0.5, min(1.5, 0.5 + dx))
            breakdown(context, self.factor)
            context.area.header_text_set(f'Breakdown: {self.factor * 100:.0f}% toward the next pose  (click to confirm, Esc to cancel)') if context.area else None
            return {'RUNNING_MODAL'}
        if event.type in ('LEFTMOUSE', 'RET', 'NUMPAD_ENTER'):
            context.area.header_text_set(None) if context.area else None
            return {'FINISHED'}
        if event.type in ('RIGHTMOUSE', 'ESC'):
            context.area.header_text_set(None) if context.area else None
            bpy.ops.ed.undo()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self._x = event.mouse_x
        bpy.ops.ed.undo_push(message='Breakdown')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        n = breakdown(context, self.factor)
        if not n:
            self.report({'WARNING'}, 'Put the playhead between two keys on the selected objects or bones')
        return {'FINISHED'}


EASES = [('SLOW_IN_OUT', 'Slow in & out', 'SINE', 'EASE_IN_OUT'), ('SLOW_OUT', 'Slow out', 'CUBIC', 'EASE_OUT'),
         ('SLOW_IN', 'Slow in', 'CUBIC', 'EASE_IN'), ('SNAP', 'Snap (stepped)', 'CONSTANT', 'AUTO'),
         ('OVERSHOOT', 'Overshoot', 'BACK', 'EASE_OUT'), ('BOUNCE', 'Bounce', 'BOUNCE', 'EASE_OUT'),
         ('ELASTIC', 'Elastic', 'ELASTIC', 'EASE_OUT'), ('LINEAR', 'Linear', 'LINEAR', 'AUTO'),
         ('SMOOTH', 'Smooth (spline)', 'BEZIER', 'AUTO')]


class CTK_OT_ease(bpy.types.Operator):
    """Set the easing of the selected keys (or all keys of the selected objects/bones)"""
    bl_idname = 'ctk.ease'
    bl_label = 'Ease'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[(e[0], e[1], '') for e in EASES])
    only_selected_keys: bpy.props.BoolProperty(name='Only selected keys', default=True)

    def execute(self, context):
        _, _, interp, easing = next(e for e in EASES if e[0] == self.kind)
        n = 0
        for fc in _fcurves(context):
            kps = list(fc.keyframe_points)
            sel = [k for k in kps if k.select_control_point] if self.only_selected_keys else kps
            for k in (sel or kps):
                k.interpolation = interp
                k.easing = easing
                n += 1
            fc.update()
        self.report({'INFO'}, f'{n} keys eased')
        return {'FINISHED'}


class CTK_OT_key_pose(bpy.types.Operator):
    """Key everything that moves on the selection at the playhead"""
    bl_idname = 'ctk.key_pose'
    bl_label = 'Key the whole pose'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        f = context.scene.frame_current
        if context.mode == 'POSE':
            for pb in context.selected_pose_bones or []:
                for p in ('location', 'rotation_quaternion' if pb.rotation_mode == 'QUATERNION' else 'rotation_euler', 'scale'):
                    pb.keyframe_insert(p, frame=f, group=pb.name)
        else:
            for o in context.selected_objects:
                for p in ('location', 'rotation_euler', 'scale'):
                    o.keyframe_insert(p, frame=f)
        return {'FINISHED'}


CLASSES = (CTK_OT_breakdown, CTK_OT_ease, CTK_OT_key_pose)

_km = []


def register_extra():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        for space, name in (('EMPTY', 'Object Mode'), ('EMPTY', 'Pose')):
            km = kc.keymaps.new(name=name, space_type=space)
            kmi = km.keymap_items.new('ctk.breakdown', 'E', 'PRESS', shift=True, alt=True)
            _km.append((km, kmi))


def unregister_extra():
    for km, kmi in _km:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _km.clear()


def draw(layout, context):
    row = layout.row(align=True)
    row.scale_y = 1.3
    row.operator('ctk.breakdown', text='Breakdown slider (Shift+Alt+E)', icon='IPO_EASE_IN_OUT')
    row = layout.row(align=True)
    row.operator_context = 'EXEC_DEFAULT'
    for v, label in ((0.0, '0'), (0.25, '¼'), (0.5, '½'), (0.75, '¾'), (1.0, '1')):
        o = row.operator('ctk.breakdown', text=label)
        o.factor = v
    grid = layout.grid_flow(columns=3, align=True)
    for k, label, *_ in EASES:
        grid.operator('ctk.ease', text=label).kind = k
    layout.operator('ctk.key_pose', icon='KEYINGSET')
