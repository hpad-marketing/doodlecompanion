"""Animator playback helpers: loop / ping-pong / stop, jump by seconds or beats, mirror keys."""
import bpy
from .. import uxfit

LABEL, ICON, GROUP = 'Playback helpers', 'PLAY', 'Animation'
LOOPS = [('INFINITE', 'Loop', ''), ('BOUNCE', 'Ping-pong', ''), ('STOP_END_FRAME', 'Stop at end', ''),
         ('RESTORE', 'Play once, jump back', '')]


def jump(scene, amount, unit):
    fps = scene.render.fps / scene.render.fps_base
    if unit == 'BEAT':
        bpm = scene.get('ctk_bpm', 120)
        frames = amount * fps * 60.0 / bpm
    elif unit == 'SECOND':
        frames = amount * fps
    else:
        frames = amount
    scene.frame_set(int(round(scene.frame_current + frames)))
    return scene.frame_current


class CTK_OT_loop_mode(bpy.types.Operator):
    """How playback loops (Blender 5.2)"""
    bl_idname = 'ctk.loop_mode'
    bl_label = 'Playback'
    mode: bpy.props.EnumProperty(items=LOOPS)

    def execute(self, context):
        sc = context.scene
        if not hasattr(sc, 'playback_loop_mode'):
            self.report({'WARNING'}, 'Loop modes need Blender 5.2')
            return {'CANCELLED'}
        sc.playback_loop_mode = self.mode
        return {'FINISHED'}


class CTK_OT_jump(bpy.types.Operator):
    """Move the playhead by seconds, beats or frames"""
    bl_idname = 'ctk.jump'
    bl_label = 'Jump'
    amount: bpy.props.FloatProperty(default=1.0)
    unit: bpy.props.EnumProperty(items=[('SECOND', 'Seconds', ''), ('BEAT', 'Beats', ''), ('FRAME', 'Frames', '')])

    def execute(self, context):
        jump(context.scene, self.amount, self.unit)
        sc = context.scene
        if hasattr(sc, 'time_jump_unit') and self.unit in ('SECOND', 'FRAME'):
            sc.time_jump_unit = self.unit  # Up/Down arrow then jumps the same way (5.2)
            sc.time_jump_delta = abs(self.amount)
        return {'FINISHED'}


class CTK_OT_mirror_pose(bpy.types.Operator):
    """Copy the pose of the selected bones onto their mirror side (left <-> right) at this frame"""
    bl_idname = 'ctk.mirror_pose'
    bl_label = 'Mirror pose'
    bl_options = {'REGISTER', 'UNDO'}
    key: bpy.props.BoolProperty(name='Key it', default=True)

    def execute(self, context):
        ob = context.object
        if not ob or ob.type != 'ARMATURE' or context.mode != 'POSE':
            self.report({'ERROR'}, 'Select bones in Pose Mode')
            return {'CANCELLED'}
        bpy.ops.pose.copy()
        bpy.ops.pose.paste(flipped=True)
        if self.key:
            for pb in context.selected_pose_bones or []:
                for p in ('location', 'rotation_quaternion', 'rotation_euler', 'scale'):
                    try:
                        pb.keyframe_insert(p)
                    except Exception:
                        pass
        return {'FINISHED'}


CLASSES = (CTK_OT_loop_mode, CTK_OT_jump, CTK_OT_mirror_pose)


def draw(layout, context):
    sc = context.scene
    if hasattr(sc, 'playback_loop_mode'):
        row = uxfit.flow(layout, context, [str(_t[1]) for _t in LOOPS], most=4)
        for k, l, _ in LOOPS:
            row.operator('ctk.loop_mode', text=l, depress=sc.playback_loop_mode == k).mode = k
    row = uxfit.flow(layout, context, [str(_t[2]) for _t in ((-1, 'BEAT', '‹ beat'), (1, 'BEAT', 'beat ›'), (-1, 'SECOND', '‹ 1s'), (1, 'SECOND', '1s ›'))], most=4)
    for amt, unit, txt in ((-1, 'BEAT', '‹ beat'), (1, 'BEAT', 'beat ›'), (-1, 'SECOND', '‹ 1s'), (1, 'SECOND', '1s ›')):
        op = row.operator('ctk.jump', text=txt)
        op.amount, op.unit = amt, unit
    ts = context.tool_settings
    row = layout.row(align=True)
    row.operator('ctk.mirror_pose', icon='MOD_MIRROR')
    if hasattr(ts, 'anim_mirror_object'):
        row.prop(ts, 'anim_mirror_object', text='')
        row.prop(ts, 'anim_mirror_bone', text='')
