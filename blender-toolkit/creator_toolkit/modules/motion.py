"""Motion presets: pop, bounce, wiggle, float, spin, drop & settle... on any object, with stagger."""
import math
import random
import bpy
from ..compat import fcurves_of
from .. import uxfit

LABEL, ICON, GROUP = 'Motion presets', 'ANIM', 'Animation'
PRESETS = [('POP_IN', 'Pop in'), ('POP_OUT', 'Pop out'), ('BOUNCE_IN', 'Bounce in'), ('SLIDE_IN', 'Slide in'),
           ('DROP_SETTLE', 'Drop & settle'), ('WIGGLE', 'Wiggle'), ('FLOAT', 'Float (loop)'), ('SPIN', 'Spin'),
           ('PULSE', 'Pulse (loop)'), ('SHAKE', 'Nervous shake'), ('OVERSHOOT', 'Turn with overshoot'),
           ('JUMP', 'Hop')]


class Keys:
    def __init__(self, o):
        self.o = o
        self.marks = []  # (path, index, frame, interp, easing)

    def key(self, path, index, frame, value, interp='BEZIER', easing='AUTO'):
        getattr(self.o, path)[index] = value
        self.o.keyframe_insert(path, index=index, frame=frame)
        self.marks.append((path, index, frame, interp, easing))

    def finish(self, cyclic_paths=()):
        fcs = {(fc.data_path, fc.array_index): fc for fc in fcurves_of(self.o)}
        for path, idx, frame, interp, easing in self.marks:
            fc = fcs.get((path, idx))
            if not fc:
                continue
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 0.01:
                    kp.interpolation = interp
                    kp.easing = easing
        for path, idx in cyclic_paths:
            fc = fcs.get((path, idx))
            if fc and not any(m.type == 'CYCLES' for m in fc.modifiers):
                fc.modifiers.new('CYCLES')


def apply(o, kind, f0, dur, strength=1.0, seed=0):
    k = Keys(o)
    L, R, S = o.location.copy(), o.rotation_euler.copy(), o.scale.copy()
    size = max(max(o.dimensions), 0.2)
    f1 = f0 + dur
    if kind in ('POP_IN', 'POP_OUT'):
        a, b = (0.0, 1.0) if kind == 'POP_IN' else (1.0, 0.0)
        for i in range(3):
            k.key('scale', i, f0, S[i] * a, 'BACK', 'EASE_OUT' if kind == 'POP_IN' else 'EASE_IN')
            k.key('scale', i, f1, S[i] * b)
    elif kind == 'BOUNCE_IN':
        k.key('location', 2, f0, L.z + size * 2 * strength, 'BOUNCE', 'EASE_OUT')
        k.key('location', 2, f1, L.z)
    elif kind == 'SLIDE_IN':
        k.key('location', 0, f0, L.x - size * 3 * strength, 'BACK', 'EASE_OUT')
        k.key('location', 0, f1, L.x)
    elif kind == 'DROP_SETTLE':
        land = f0 + int(dur * 0.45)
        k.key('location', 2, f0, L.z + size * 2 * strength, 'QUAD', 'EASE_IN')
        k.key('location', 2, land, L.z)
        k.key('scale', 2, land - 1, S.z * 1.15)
        k.key('scale', 0, land - 1, S.x * 0.9)
        k.key('scale', 1, land - 1, S.y * 0.9)
        k.key('scale', 2, land + 1, S.z * (1 - 0.3 * strength), 'ELASTIC', 'EASE_OUT')
        k.key('scale', 0, land + 1, S.x * (1 + 0.15 * strength), 'ELASTIC', 'EASE_OUT')
        k.key('scale', 1, land + 1, S.y * (1 + 0.15 * strength), 'ELASTIC', 'EASE_OUT')
        for i in range(3):
            k.key('scale', i, f1, S[i])
    elif kind == 'WIGGLE':
        n = 6
        for j in range(n + 1):
            amp = math.radians(18) * strength * (1 - j / n) * (1 if j % 2 else -1)
            k.key('rotation_euler', 2, f0 + round(dur * j / n), R.z + (0 if j in (0, n) else amp))
    elif kind == 'FLOAT':
        k.key('location', 2, f0, L.z, 'SINE', 'EASE_IN_OUT')
        k.key('location', 2, f0 + dur // 2, L.z + size * 0.15 * strength, 'SINE', 'EASE_IN_OUT')
        k.key('location', 2, f0 + dur, L.z, 'SINE', 'EASE_IN_OUT')
        k.finish([('location', 2)])
        return
    elif kind == 'SPIN':
        k.key('rotation_euler', 2, f0, R.z, 'CUBIC', 'EASE_IN_OUT')
        k.key('rotation_euler', 2, f1, R.z + math.tau * max(1, round(strength)))
    elif kind == 'PULSE':
        for i in range(3):
            k.key('scale', i, f0, S[i], 'SINE', 'EASE_IN_OUT')
            k.key('scale', i, f0 + dur // 4, S[i] * (1 + 0.12 * strength), 'SINE', 'EASE_IN_OUT')
            k.key('scale', i, f0 + dur // 2, S[i], 'SINE', 'EASE_IN_OUT')
            k.key('scale', i, f0 + dur, S[i], 'SINE', 'EASE_IN_OUT')
        k.finish([('scale', 0), ('scale', 1), ('scale', 2)])
        return
    elif kind == 'SHAKE':
        rnd = random.Random(seed)
        for j in range(0, dur + 1, 2):
            for i in range(2):
                off = 0 if j in (0, dur) else rnd.uniform(-1, 1) * size * 0.03 * strength
                k.key('location', i, f0 + j, L[i] + off, 'LINEAR')
    elif kind == 'OVERSHOOT':
        k.key('rotation_euler', 2, f0, R.z, 'ELASTIC', 'EASE_OUT')
        k.key('rotation_euler', 2, f1, R.z + math.radians(90) * strength)
    elif kind == 'JUMP':
        top = f0 + dur // 2
        k.key('location', 2, f0, L.z, 'QUAD', 'EASE_OUT')
        k.key('location', 2, top, L.z + size * 1.2 * strength, 'QUAD', 'EASE_IN')
        k.key('location', 2, f1, L.z)
        k.key('scale', 2, f0 - 2, S.z, 'BEZIER')
        k.key('scale', 2, f0, S.z * 0.8)
        k.key('scale', 2, f0 + 3, S.z * 1.15)
        k.key('scale', 2, top, S.z)
        k.key('scale', 2, f1, S.z * 0.85)
        k.key('scale', 2, f1 + 4, S.z)
    k.finish()


class CTK_OT_motion_preset(bpy.types.Operator):
    """Animate the selected objects with a ready-made motion. Several objects get a stagger"""
    bl_idname = 'ctk.motion_preset'
    bl_label = 'Motion preset'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(name='Motion', items=[(k, n, '') for k, n in PRESETS])
    duration: bpy.props.IntProperty(name='Length (frames)', default=18, min=2, max=1000)
    strength: bpy.props.FloatProperty(name='Strength', default=1.0, min=0.1, max=5)
    stagger: bpy.props.IntProperty(name='Stagger (frames)', default=3, min=0, max=100)
    order: bpy.props.EnumProperty(name='Stagger order', items=[('X', 'Left to right', ''), ('Z', 'Bottom to top', ''),
                                                               ('Y', 'Front to back', ''), ('RANDOM', 'Random', '')])

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type != 'ARMATURE']
        if not obs:
            self.report({'WARNING'}, 'Select objects first')
            return {'CANCELLED'}
        if self.order == 'RANDOM':
            random.Random(7).shuffle(obs)
        else:
            i = 'XYZ'.index(self.order)
            obs.sort(key=lambda o: o.matrix_world.translation[i])
        f = context.scene.frame_current
        for n, o in enumerate(obs):
            if o.rotation_mode not in ('XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'):
                o.rotation_mode = 'XYZ'
            apply(o, self.kind, f + n * self.stagger, self.duration, self.strength, seed=n)
        return {'FINISHED'}


CLASSES = (CTK_OT_motion_preset,)


def draw(layout, context):
    grid = uxfit.flow(layout, context, [str(_t[1]) for _t in PRESETS], most=2)
    grid.operator_context = 'EXEC_DEFAULT'  # buttons run at once; the Shift+Alt+M shortcut asks first
    for k, n in PRESETS:
        grid.operator('ctk.motion_preset', text=n).kind = k
    uxfit.wrap(layout, context, 'Starts at the playhead. Tweak in the Adjust panel', icon='INFO')
