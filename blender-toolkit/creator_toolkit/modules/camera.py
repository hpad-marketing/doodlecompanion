"""Camera Moves library + handheld shake (Shakify-style), with beat snapping."""
import math
import random
import bpy
from mathutils import Vector
from . import motion
from ..compat import fcurves_of
from .. import uxfit

LABEL, ICON, GROUP = 'Camera moves + shake', 'VIEW_CAMERA', 'Motion design'
MOVES = [('PUSH_IN', 'Push in'), ('PULL_OUT', 'Pull out'), ('ORBIT', 'Orbit'), ('DOLLY_ZOOM', 'Dolly zoom'),
         ('WHIP_PAN', 'Whip pan'), ('CRANE_UP', 'Crane up'), ('HERO_SWEEP', 'Hero sweep'), ('LOW_ANGLE', 'Low angle rise'),
         ('TRUCK', 'Slide sideways'), ('PEDESTAL_DOWN', 'Drop down')]
SHAKES = {'Subtle handheld': (0.004, 0.25, 1.2), 'Walking': (0.012, 0.8, 2.0), 'Running': (0.03, 1.8, 3.5),
          'Car / drone': (0.006, 0.4, 0.6), 'Earthquake': (0.05, 3.0, 8.0), 'Beat hit': (0.02, 1.5, 6.0)}


def _target(context):
    sel = [o for o in context.selected_objects if o.type not in ('CAMERA', 'LIGHT')]
    if sel:
        pts = [o.matrix_world @ Vector(c) for o in sel for c in o.bound_box]
        return sum(pts, Vector()) / len(pts)
    return context.scene.cursor.location.copy()


def ensure_camera(context):
    cam = context.scene.camera
    if not cam:
        cd = bpy.data.cameras.new('Camera')
        cam = bpy.data.objects.new('Camera', cd)
        context.scene.collection.objects.link(cam)
        cam.location = (0, -8, 1.6)
        cam.rotation_euler = (math.radians(88), 0, 0)
        context.scene.camera = cam
    return cam


def _rig(context, cam, target):
    """Camera on a pivot empty that looks at the target."""
    piv = bpy.data.objects.new('CTK Camera Pivot', None)
    piv.empty_display_type = 'SPHERE'
    piv.empty_display_size = 0.2
    piv.location = target
    context.scene.collection.objects.link(piv)
    mw = cam.matrix_world.copy()
    cam.parent = piv
    cam.matrix_world = mw
    tr = cam.constraints.get('CTK Aim') or cam.constraints.new('TRACK_TO')
    tr.name = 'CTK Aim'
    tr.target = piv
    tr.track_axis = 'TRACK_NEGATIVE_Z'
    tr.up_axis = 'UP_Y'
    return piv


def beat_frame(scene, frame, bpm):
    if bpm <= 0:
        return frame
    fps = scene.render.fps / scene.render.fps_base
    beat = fps * 60.0 / bpm
    return int(round(round(frame / beat) * beat))


def apply_move(context, kind, f0, dur, strength=1.0):
    cam = ensure_camera(context)
    target = _target(context)
    f1 = f0 + dur
    d = (cam.matrix_world.translation - target)
    dist = max(d.length, 0.5)
    k = motion.Keys(cam)
    if kind in ('PUSH_IN', 'PULL_OUT', 'DOLLY_ZOOM'):
        _rig_none = cam.constraints.get('CTK Aim') or cam.constraints.new('TRACK_TO')
        _rig_none.name = 'CTK Aim'
        aim = bpy.data.objects.get('CTK Camera Aim') or bpy.data.objects.new('CTK Camera Aim', None)
        if aim.name not in context.scene.collection.objects:
            context.scene.collection.objects.link(aim)
        aim.location = target
        _rig_none.target = aim
        _rig_none.track_axis = 'TRACK_NEGATIVE_Z'; _rig_none.up_axis = 'UP_Y'
        a = cam.location.copy()
        frac = 0.45 * strength if kind != 'PULL_OUT' else -0.6 * strength
        b = a + (target - a).normalized() * dist * frac
        if kind == 'PULL_OUT':
            a, b = b, a
            cam.location = a
        for i in range(3):
            k.key('location', i, f0, a[i], 'SINE', 'EASE_IN_OUT')
            k.key('location', i, f1, b[i])
        if kind == 'DOLLY_ZOOM':
            lens0 = cam.data.lens
            cam.data.lens = lens0
            cam.data.keyframe_insert('lens', frame=f0)
            cam.data.lens = lens0 * (target - b).length / max((target - a).length, 1e-6)
            cam.data.keyframe_insert('lens', frame=f1)
            cam.data.lens = lens0
            for fc in fcurves_of(cam.data):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'SINE'; kp.easing = 'EASE_IN_OUT'
    elif kind in ('ORBIT', 'HERO_SWEEP', 'LOW_ANGLE', 'CRANE_UP'):
        piv = _rig(context, cam, target)
        kp = motion.Keys(piv)
        if kind == 'ORBIT':
            kp.key('rotation_euler', 2, f0, 0.0, 'LINEAR')
            kp.key('rotation_euler', 2, f1, math.radians(90) * strength)
        elif kind == 'HERO_SWEEP':
            kp.key('rotation_euler', 2, f0, math.radians(-50) * strength, 'SINE', 'EASE_OUT')
            kp.key('rotation_euler', 2, f1, 0.0)
            for a in range(3):
                kp.key('scale', a, f0, 1.35, 'SINE', 'EASE_OUT')
                kp.key('scale', a, f1, 1.0)
        elif kind == 'LOW_ANGLE':
            kp.key('rotation_euler', 0, f0, math.radians(-25) * strength, 'SINE', 'EASE_IN_OUT')
            kp.key('rotation_euler', 0, f1, math.radians(-5))
        else:
            kp.key('location', 2, f0, piv.location.z, 'SINE', 'EASE_IN_OUT')
            kp.key('location', 2, f1, piv.location.z + dist * 0.6 * strength)
        kp.finish()
        context.scene.frame_set(context.scene.frame_current)
        return cam
    elif kind == 'WHIP_PAN':
        r = cam.rotation_euler.z
        k.key('rotation_euler', 2, f0, r, 'EXPO', 'EASE_IN')
        k.key('rotation_euler', 2, f0 + dur // 2, r + math.radians(60) * strength, 'EXPO', 'EASE_OUT')
        k.key('rotation_euler', 2, f1, r + math.radians(90) * strength)
    elif kind == 'TRUCK':
        side = cam.matrix_world.to_3x3() @ Vector((1, 0, 0))
        a = cam.location.copy(); b = a + side * dist * 0.4 * strength
        for i in range(3):
            k.key('location', i, f0, a[i], 'SINE', 'EASE_IN_OUT')
            k.key('location', i, f1, b[i])
    elif kind == 'PEDESTAL_DOWN':
        z = cam.location.z
        k.key('location', 2, f0, z + dist * 0.3 * strength, 'CUBIC', 'EASE_OUT')
        k.key('location', 2, f1, z)
    k.finish()
    return cam


def add_shake(cam, preset, strength=1.0, seed=0):
    amp, rot_deg, freq = SHAKES[preset]
    if not cam.animation_data or not cam.animation_data.action:
        cam.keyframe_insert('location')
        cam.keyframe_insert('rotation_euler')
    for path, n, a in (('location', 3, amp * strength), ('rotation_euler', 3, math.radians(rot_deg) * strength)):
        for i in range(n):
            fc = next((f for f in fcurves_of(cam) if f.data_path == path and f.array_index == i), None)
            if fc is None:
                cam.keyframe_insert(path, index=i)
                fc = next(f for f in fcurves_of(cam) if f.data_path == path and f.array_index == i)
            for m in list(fc.modifiers):
                if m.type == 'NOISE':
                    fc.modifiers.remove(m)
            nm = fc.modifiers.new('NOISE')
            nm.scale = 24.0 / max(freq, 0.1)
            nm.strength = a * 2
            nm.phase = random.Random(seed * 10 + i + (0 if path == 'location' else 5)).uniform(0, 100)
            nm.blend_type = 'ADD'
    cam['ctk_shake'] = preset


def remove_shake(cam):
    for fc in fcurves_of(cam):
        for m in list(fc.modifiers):
            if m.type == 'NOISE':
                fc.modifiers.remove(m)
    if 'ctk_shake' in cam:
        del cam['ctk_shake']


class CTK_OT_camera_move(bpy.types.Operator):
    """Add a camera move toward the selected objects, starting at the playhead"""
    bl_idname = 'ctk.camera_move'
    bl_label = 'Camera move'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=[(k, n, '') for k, n in MOVES])
    seconds: bpy.props.FloatProperty(name='Seconds', default=2.0, min=0.1, max=60)
    strength: bpy.props.FloatProperty(name='Strength', default=1.0, min=0.1, max=4)
    bpm: bpy.props.FloatProperty(name='Snap end to beat (BPM, 0 = off)', default=0.0, min=0, max=300)

    def execute(self, context):
        sc = context.scene
        fps = sc.render.fps / sc.render.fps_base
        f0 = sc.frame_current
        f1 = beat_frame(sc, f0 + int(self.seconds * fps), self.bpm)
        apply_move(context, self.kind, f0, max(2, f1 - f0), self.strength)
        return {'FINISHED'}


class CTK_OT_camera_shake(bpy.types.Operator):
    """Add handheld-style shake to the scene camera (no keys needed)"""
    bl_idname = 'ctk.camera_shake'
    bl_label = 'Camera shake'
    bl_options = {'REGISTER', 'UNDO'}
    preset: bpy.props.EnumProperty(items=[(k, k, '') for k in SHAKES])
    strength: bpy.props.FloatProperty(name='Strength', default=1.0, min=0.0, max=5)
    remove: bpy.props.BoolProperty(default=False, options={'HIDDEN'})

    def execute(self, context):
        cam = ensure_camera(context)
        if self.remove:
            remove_shake(cam)
        else:
            add_shake(cam, self.preset, self.strength)
        return {'FINISHED'}


class CTK_OT_beat_markers(bpy.types.Operator):
    """Put a timeline marker on every beat, so moves and cuts can line up with the music"""
    bl_idname = 'ctk.beat_markers'
    bl_label = 'Beat markers'
    bl_options = {'REGISTER', 'UNDO'}
    bpm: bpy.props.FloatProperty(name='BPM', default=120, min=20, max=300)
    every: bpy.props.IntProperty(name='Every n beats', default=1, min=1, max=16)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        sc = context.scene
        for m in [m for m in sc.timeline_markers if m.name.startswith('♪')]:
            sc.timeline_markers.remove(m)
        fps = sc.render.fps / sc.render.fps_base
        beat = fps * 60 / self.bpm
        i = 0
        while True:
            f = sc.frame_start + round(i * beat * self.every)
            if f > sc.frame_end:
                break
            sc.timeline_markers.new(f'♪{i + 1}', frame=f)
            i += 1
        sc['ctk_bpm'] = self.bpm
        return {'FINISHED'}


class CTK_OT_pin_to_camera(bpy.types.Operator):
    """Keep labels, stickers, arrows and lower thirds in frame while the camera moves"""
    bl_idname = 'ctk.pin_to_camera'
    bl_label = 'Pin to camera'
    bl_options = {'REGISTER', 'UNDO'}
    how: bpy.props.EnumProperty(items=[
        ('FOLLOW', 'Follow camera', 'Parent to the camera: always pinned, edit anytime'),
        ('KEYS', 'Bake keys (5.2)', 'Blender 5.2 Fix to Camera: keys every frame, keeps your own keys'),
        ('FREE', 'Unpin', 'Stop following, stay where it is now')])

    def execute(self, context):
        cam = context.scene.camera
        obs = [o for o in context.selected_objects if o is not cam]
        if not cam or not obs:
            self.report({'ERROR'}, 'Needs a scene camera and selected objects')
            return {'CANCELLED'}
        context.view_layer.update()
        if self.how == 'KEYS':
            if not hasattr(bpy.ops.object, 'fix_to_camera'):
                self.report({'ERROR'}, 'Bake keys needs Blender 5.2; use Follow camera')
                return {'CANCELLED'}
            return bpy.ops.object.fix_to_camera()
        for o in obs:
            mw = o.matrix_world.copy()
            if self.how == 'FOLLOW':
                o.parent = cam
                o.matrix_parent_inverse = cam.matrix_world.inverted()
                o.matrix_world = mw
                o['ctk_pinned'] = 1
            else:
                o.parent = None
                o.matrix_world = mw
                o.pop('ctk_pinned', None)
        return {'FINISHED'}


CLASSES = (CTK_OT_camera_move, CTK_OT_camera_shake, CTK_OT_beat_markers, CTK_OT_pin_to_camera)


def draw(layout, context):
    grid = uxfit.flow(layout, context, [str(_t[1]) for _t in MOVES], most=2)
    for k, n in MOVES:
        op = grid.operator('ctk.camera_move', text=n)
        op.kind = k
        op.bpm = float(context.scene.get('ctk_bpm', 0.0))
    layout.label(text='Shake', icon='FORCE_TURBULENCE')
    grid = uxfit.flow(layout, context, [str(_t) for _t in SHAKES], most=3)
    for k in SHAKES:
        grid.operator('ctk.camera_shake', text=k).preset = k
    row = layout.row(align=True)
    op = row.operator('ctk.camera_shake', text='Remove shake', icon='X')
    op.remove = True
    row.operator('ctk.beat_markers', icon='MARKER_HLT')
    row = layout.row(align=True)
    row.operator('ctk.pin_to_camera', text='Pin to camera', icon='PINNED').how = 'FOLLOW'
    if hasattr(bpy.ops.object, 'fix_to_camera'):
        row.operator('ctk.pin_to_camera', text='Bake keys').how = 'KEYS'
    row.operator('ctk.pin_to_camera', text='', icon='UNPINNED').how = 'FREE'
