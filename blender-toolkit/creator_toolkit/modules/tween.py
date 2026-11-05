"""Tweening and easing: breakdown slider, ease presets, key the pose, and anim offset
(change the pose on one frame and the same change carries across the existing keys)."""
import bpy
from bpy.app.handlers import persistent
from ..compat import fcurves_of
from .. import uxfit

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



# ---------------- anim offset ----------------
OFFSET_RANGES = [('ALL', 'Every key', 'The change moves every key of the selection'),
                 ('PREVIEW', 'Frame range', 'Only keys inside the preview range (or the scene range)'),
                 ('AROUND', 'Around the playhead', 'Full change near the playhead, fading out over the blend frames')]


class CTK_OffsetProps(bpy.types.PropertyGroup):
    live: bpy.props.BoolProperty(name='Anim offset', default=False,
                                 description='While on, moving the selection offsets its existing keys instead of making new ones')
    span: bpy.props.EnumProperty(name='Affect', items=OFFSET_RANGES, default='ALL')
    hold: bpy.props.IntProperty(name='Full', default=0, min=0, max=10000,
                                description='Frames on each side of the playhead that get the full change')
    blend: bpy.props.IntProperty(name='Blend', default=10, min=0, max=10000,
                                 description='Frames over which the change fades out after that')


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def offset_weight(scene, x, f):
    p = scene.ctk_offset
    if p.span == 'ALL':
        return 1.0
    if p.span == 'PREVIEW':
        a = scene.frame_preview_start if scene.use_preview_range else scene.frame_start
        b = scene.frame_preview_end if scene.use_preview_range else scene.frame_end
        return 1.0 if a - 0.01 <= x <= b + 0.01 else 0.0
    d = abs(x - f) - p.hold
    if d <= 0:
        return 1.0
    if p.blend <= 0:
        return 0.0
    return 1.0 - _smooth(d / p.blend)


def _current(owner, fc):
    try:
        v = owner.path_resolve(fc.data_path)
    except Exception:
        return None
    try:
        return float(v[fc.array_index])
    except TypeError:
        try:
            return float(v)
        except Exception:
            return None
    except Exception:
        return None


def offset_pairs(context):
    out = []
    for owner, prefix in _targets(context):
        for fc in fcurves_of(owner):
            if prefix and not fc.data_path.startswith(prefix):
                continue
            if not prefix and fc.data_path.startswith('pose.bones'):
                continue
            if fc.lock or fc.mute or len(fc.keyframe_points) == 0:
                continue
            out.append((owner, fc))
    return out


def apply_offset(context, eps=1e-6):
    """Shift keys by (pose now - animation at this frame). Returns how many curves moved."""
    scene = context.scene
    f = scene.frame_current + scene.frame_subframe
    moved = 0
    for owner, fc in offset_pairs(context):
        now = _current(owner, fc)
        if now is None:
            continue
        delta = now - fc.evaluate(f)
        if abs(delta) <= eps:
            continue
        for kp in fc.keyframe_points:
            w = offset_weight(scene, kp.co.x, f)
            if w <= 0:
                continue
            d = delta * w
            kp.co.y += d
            kp.handle_left.y += d
            kp.handle_right.y += d
        fc.update()
        moved += 1
    return moved


_busy = [False]


@persistent
def _offset_handler(scene, depsgraph=None):
    p = getattr(scene, 'ctk_offset', None)
    if not p or not p.live or _busy[0] or bpy.app.is_job_running('RENDER'):
        return
    ctx = bpy.context
    if getattr(ctx, 'scene', None) is not scene:
        return
    _busy[0] = True
    try:
        apply_offset(ctx)
    except Exception:
        pass
    finally:
        _busy[0] = False


class CTK_OT_anim_offset(bpy.types.Operator):
    """Carry the change you just made on this frame across the selection's existing keys"""
    bl_idname = 'ctk.anim_offset'
    bl_label = 'Offset keys by this change'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = apply_offset(context)
        self.report({'INFO'}, f'Offset {n} curves' if n else 'Nothing changed on this frame')
        return {'FINISHED'}


def draw_offset(layout, context):
    p = context.scene.ctk_offset
    box = layout.box()
    row = box.row(align=True)
    row.scale_y = 1.2
    row.prop(p, 'live', toggle=True, icon='MOD_OFFSET')
    row.operator('ctk.anim_offset', text='', icon='CHECKMARK')
    box.prop(p, 'span', text='')
    if p.span == 'AROUND':
        r = box.row(align=True)
        r.prop(p, 'hold')
        r.prop(p, 'blend')
    if p.live and context.scene.tool_settings.use_keyframe_insert_auto:
        uxfit.wrap(box, context, 'Turn off auto-key while offsetting', icon='ERROR')


# ---------------- silhouette view ----------------
SIL_SHADING = {'type': 'SOLID', 'light': 'FLAT', 'color_type': 'SINGLE', 'background_type': 'VIEWPORT',
               'show_cavity': False, 'show_object_outline': False, 'show_shadows': False,
               'show_xray': False, 'show_specular_highlight': False, 'show_backface_culling': False}
SIL_INK, SIL_BG = '#1F1F1D', '#E0A64B'
_sil_store = {}


def _srgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def silhouette(shading, on, key, overlay=None):
    """Flat ink shapes on mustard for pose checks; on=False puts back what was there."""
    if on:
        keep = {k: getattr(shading, k) for k in SIL_SHADING if hasattr(shading, k)}
        keep['single_color'] = tuple(shading.single_color)
        keep['background_color'] = tuple(shading.background_color)
        if overlay is not None:
            keep['_overlays'] = overlay.show_overlays
        _sil_store[key] = keep
        for k, v in SIL_SHADING.items():
            if hasattr(shading, k):
                try:
                    setattr(shading, k, v)
                except Exception:
                    pass
        shading.single_color = _srgb(SIL_INK)
        shading.background_color = _srgb(SIL_BG)
        if overlay is not None:
            overlay.show_overlays = False
        return True
    keep = _sil_store.pop(key, None)
    if not keep:
        return False
    if overlay is not None and '_overlays' in keep:
        overlay.show_overlays = keep.pop('_overlays')
    keep.pop('_overlays', None)
    # type first so the solid-only settings stick
    for k in sorted(keep, key=lambda k: k != 'type'):
        try:
            setattr(shading, k, keep[k])
        except Exception:
            pass
    return True


def _views(context):
    scr = context.screen
    return [a.spaces.active for a in (scr.areas if scr else []) if a.type == 'VIEW_3D']


def silhouette_on(context):
    return any(sp.as_pointer() in _sil_store for sp in _views(context))


class CTK_OT_silhouette(bpy.types.Operator):
    """Silhouette view: every object as a flat ink shape on mustard, to read poses at a glance. Click again to go back"""
    bl_idname = 'ctk.silhouette'
    bl_label = 'Silhouette'

    def execute(self, context):
        views = _views(context)
        if not views:
            self.report({'WARNING'}, 'No 3D viewport here')
            return {'CANCELLED'}
        turn_on = not silhouette_on(context)
        for sp in views:
            silhouette(sp.shading, turn_on, sp.as_pointer(), sp.overlay)
        for a in context.screen.areas:
            if a.type == 'VIEW_3D':
                a.tag_redraw()
        return {'FINISHED'}


CLASSES = (CTK_OT_breakdown, CTK_OT_ease, CTK_OT_key_pose, CTK_OffsetProps, CTK_OT_anim_offset,
           CTK_OT_silhouette)

_km = []


def register_extra():
    bpy.types.Scene.ctk_offset = bpy.props.PointerProperty(type=CTK_OffsetProps)
    if _offset_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_offset_handler)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        for space, name in (('EMPTY', 'Object Mode'), ('EMPTY', 'Pose')):
            km = kc.keymaps.new(name=name, space_type=space)
            kmi = km.keymap_items.new('ctk.breakdown', 'E', 'PRESS', shift=True, alt=True)
            _km.append((km, kmi))


def unregister_extra():
    if _offset_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_offset_handler)
    if hasattr(bpy.types.Scene, 'ctk_offset'):
        del bpy.types.Scene.ctk_offset
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
    row = uxfit.flow(layout, context, [str(_t[1]) for _t in ((0.0, '0'), (0.25, '¼'), (0.5, '½'), (0.75, '¾'), (1.0, '1'))], most=5)
    row.operator_context = 'EXEC_DEFAULT'
    for v, label in ((0.0, '0'), (0.25, '¼'), (0.5, '½'), (0.75, '¾'), (1.0, '1')):
        o = row.operator('ctk.breakdown', text=label)
        o.factor = v
    grid = uxfit.flow(layout, context, [str(_t[1]) for _t in EASES], most=3)
    for k, label, *_ in EASES:
        grid.operator('ctk.ease', text=label).kind = k
    row = layout.row(align=True)
    row.operator('ctk.key_pose', icon='KEYINGSET')
    try:
        on = silhouette_on(context)
    except Exception:
        on = False
    row.operator('ctk.silhouette', icon='HIDE_ON' if on else 'HIDE_OFF', depress=on)
    draw_offset(layout, context)
